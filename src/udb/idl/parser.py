# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

r"""Hand-written packrat PEG parser for IDL.

This module is a pure-Python port of the Treetop grammar
``tools/ruby-gems/idlc/lib/idlc/idl.treetop``. Every rule in that grammar has
a corresponding ``_r_<rule_name>`` method on :class:`_Parser` below, tried in
exactly the same alternative order, with exactly the same repetition and
lookahead (``&``/``!``) semantics. Results are memoized by ``(rule, position)``
(packrat parsing) so the whole grammar runs in linear time in the size of the
input.

Lowering (building :mod:`udb.idl.ast` nodes from a successful parse) happens
inline in each ``_r_*`` method, mirroring the corresponding ``SyntaxNode#to_ast``
method in ``tools/ruby-gems/idlc/lib/idlc/ast.rb``.

Grammar summary
----------------

Whitespace and comments
    Whitespace is *only* the literal characters ``' '`` (space) and ``'\n'``
    (newline) -- no tab, no carriage return. A comment starts with ``#`` and
    extends to (and consumes) the next ``'\n'``; a ``#`` with no following
    ``'\n'`` before the end of input does **not** count as whitespace at all
    (this is a faithfully-reproduced Treetop grammar quirk).

Numeric literals (``int``)
    Fourteen alternative forms, tried in this order:

    1. Plain decimal with an explicit width/signedness suffix:
       ``<width>'s<value>`` (e.g. ``32's5``) -- decimal ``value``, ``width``
       decimal digits, signed.
    2. Plain decimal: ``[0-9]+`` (unsigned, width is the natural width).
    3. C++-style signed hex/octal/binary: ``0x<hex>s``, ``0<octal>s``,
       ``0b<binary>s``.
    4. C++-style unsigned hex/octal/binary: ``0x<hex>``, ``0<octal>``,
       ``0b<binary>``.
    5. Bare ``0`` (optionally followed by ``s``, but not by a ``'`` -- that
       is reserved for the Verilog-style forms below).
    6. Verilog-style: ``[<width>|MXLEN]'[s]<radix><digits>`` where ``<radix>``
       is one of ``b``, ``o``, ``d``, ``h`` (unsigned) or ``sb``, ``so``,
       ``sd``, ``sh`` (signed), and ``<digits>`` may contain ``x``/``X`` to
       denote unknown bits (producing an :class:`~udb.idl.ast.UnknownLiteral`
       instead of an :class:`~udb.idl.ast.IntLiteral`). The width may be the
       literal identifier ``MXLEN`` instead of a decimal number, or omitted
       entirely (defaulting to the natural width of ``<digits>``).

Strings
    ``"..."`` with no escape processing at all: any run of non-``"``
    characters, terminated by the closing ``"``.

Identifiers
    * ``id``: ``[A-Za-z][A-Za-z_0-9]*`` (no leading underscore).
    * ``dollar_variable`` name: ``[a-zA-Z_][a-zA-Z0-9_]*`` (leading
      underscore *is* allowed, unlike ``id``).
    * ``dollar_function_call`` name: ``[a-zA-Z_][a-zA-Z0-9_?]*`` (allows a
      trailing ``?``, e.g. ``$array_includes?``).
    * ``field_name``: ``[a-zA-Z][a-zA-Z0-9_]*``.
    * ``csr_name``: ``[a-z][a-z0-9_.]*`` (lowercase only).
    * ``csr_field_name``: ``[a-zA-Z][a-zA-Z0-9]*`` (no underscore, unlike
      ``field_name``).
    * ``function_name``: ``[a-zA-Z][a-zA-Z0-9_]*'?'?``.
    * ``version_string``: ``[0-9]+'.'[0-9]+``.
    * ``type_name``: either ``Bits<template_safe_expression>`` or
      ``[A-Z][A-Za-z0-9_]*``.

Reserved words
    See ``ReservedWords`` in ``ast.rb``; these are rejected by
    :func:`udb.idl.ast.check_reserved` wherever an ``id`` is used as a
    binding name, not by the grammar itself.

Expression precedence (loosest to tightest)
    ``ternary_expression`` (``a ? b : c``, both branches always parsed as
    plain, never template-safe, ``expression``) and
    ``implication_expression`` (``[(] [antecedent] -> consequent [)]``, with a
    synthetic zero-width :class:`~udb.idl.ast.TrueExpression` substituted for
    a missing antecedent) sit above the binary-operator precedence chain,
    which runs ``p9`` (loosest) down to ``p0`` (tightest):

    =====  =================================================================
    Level  Operators
    =====  =================================================================
    p9     ``||``
    p8     ``&&``
    p7     ``|``
    p6     ``^``
    p5     ``&``
    p4     ``==``, ``!=``
    p3     ``<=``, ``>=``, ``<``, ``>``
    p2     ``<<``, ``>>``, ``>>>``
    p1     ``+``, ``-``
    p0     ``*``, ``/``, ``%``
    =====  =================================================================

    A "template-safe" parallel chain (``template_safe_p9_binary_expression``
    down to ``template_safe_p3_binary_expression`` -- there is no
    ``template_safe_p{0,1,2}``) exists so that a bare ``>`` inside a
    ``Bits<...>`` template argument is not misparsed as a right-shift or
    comparison operator; per the grammar, the *right-hand* operand of each
    ``template_safe_p{4..9}_binary_expression`` level is deliberately the
    **non**-template-safe ``p{n-1}_binary_expression`` (only the left operand
    stays template-safe), and ``template_safe_p3_binary_expression`` uses
    plain ``p2_binary_expression`` for *both* operands and only allows
    ``<=``/``<`` (not ``>=``/``>``, which would be ambiguous with the
    enclosing ``<...>``).

    Above the binary chain: unary ``-``, ``!``, ``~`` and post ``++``/``--``,
    array element/range access, field access, ``$``-builtins, ``csr[...]``
    access, function calls, enum references, replication (``{N{expr}}``),
    concatenation (``{a, b, c}``), array literals (``[a, b, c]``), and
    parenthesized expressions.

Entry points (``root=`` argument to :func:`parse`)
    ``isa``, ``function_body``, ``instruction_operation``, ``expression``,
    ``constraint_body``, ``for_loop``.
"""

from __future__ import annotations

import re
from typing import Any

from . import ast
from .errors import IdlSyntaxError
from .source import IdlSource

__all__ = [
    "ROOTS",
    "parse",
    "parse_constraint_body",
    "parse_expression",
    "parse_for_loop",
    "parse_function_body",
    "parse_instruction_operation",
    "parse_isa",
]

#: Entry points exposed by :func:`parse`, matching ``tools/ruby-gems/idlc/lib/idlc.rb``.
ROOTS: tuple[str, ...] = (
    "isa",
    "function_body",
    "instruction_operation",
    "expression",
    "constraint_body",
    "for_loop",
)

_BUILTIN_TYPE_NAMES = ast._BUILTIN_TYPE_NAMES


# ---------------------------------------------------------------------------
# Terminal regexes (all compiled with re.ASCII-agnostic default; IDL source is
# ASCII, so plain \w-free character classes are used throughout).
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"[A-Za-z][A-Za-z_0-9]*")
_FIELD_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")
_CSR_NAME_RE = re.compile(r"[a-z][a-z0-9_.]*")
_CSR_FIELD_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")
_FUNCTION_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*\??")
_VERSION_STRING_RE = re.compile(r"[0-9]+\.[0-9]+")
_DOLLAR_VAR_NAME_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_DOLLAR_FUNC_NAME_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_?]*")
_UPPER_ID_RE = re.compile(r"[A-Z][A-Za-z0-9_]*")
_ALNUM_ASCII = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")

# Binary operators per precedence level (loosest p9 .. tightest p0), tried in
# the exact order given in idl.treetop. `forbidden_next` implements the two
# rules with a negative lookahead against a doubled character (`&` must not
# be followed by another `&`, ditto `|`, so they aren't confused with `&&`/`||`).
_P_OPERATORS: dict[int, tuple[tuple[str, str | None], ...]] = {
    0: (("/", None), ("%", None), ("`*", None), ("*", None)),
    1: (("`+", None), ("`-", None), ("+", None), ("-", None)),
    2: (("`<<", None), ("<<", None), (">>>", None), (">>", None)),
    3: (("<=", None), (">=", None), ("<", None), (">", None)),
    4: (("!=", None), ("==", None)),
    5: (("&", "&"),),
    6: (("^", None),),
    7: (("|", "|"),),
    8: (("&&", None),),
    9: (("||", None),),
}
_P3_TEMPLATE_OPERATORS: tuple[tuple[str, str | None], ...] = (("<=", None), ("<", None))

#: ``$``-builtin dispatch table: ``dollar_name -> (ast_class, expected_arg_count, arg_validations)``.
#: ``arg_validations`` maps a 0-based argument index to ``(allowed_classes, description)``,
#: mirroring ``DollarFunctionCallSyntaxNode#to_ast``'s ``builtin_call_ast``/``enum_type_name_validation``.
_ENUM_TYPE_NAME_VALIDATION: dict[int, tuple[tuple[type, ...], str]] = {
    0: ((ast.Id, ast.UserTypeName), "an identifier or user type name")
}
_DOLLAR_BUILTINS: dict[str, tuple[type, int, dict[int, tuple[tuple[type, ...], str]]]] = {
    "$width": (ast.WidthReveal, 1, {}),
    "$signed": (ast.SignCast, 1, {}),
    "$bits": (ast.BitsCast, 1, {}),
    "$enum_size": (ast.EnumSize, 1, _ENUM_TYPE_NAME_VALIDATION),
    "$enum_element_size": (ast.EnumElementSize, 1, _ENUM_TYPE_NAME_VALIDATION),
    "$enum_to_a": (ast.EnumArrayCast, 1, _ENUM_TYPE_NAME_VALIDATION),
    "$enum": (ast.EnumCast, 2, _ENUM_TYPE_NAME_VALIDATION),
    "$array_size": (ast.ArraySize, 1, {}),
    "$array_includes?": (ast.ArrayIncludes, 2, {}),
}


def _ruby_class_name(node: Any) -> str:
    """Mirror Ruby's ``arg_ast.class.name.split("::").last`` for error messages.

    Every Ruby AST class name ends in ``Ast`` except ``ParseTimeDetectedTypeError``,
    which keeps its bare name; Python drops the ``Ast`` suffix from class names,
    so it must be added back here (except for that one class).
    """
    name = type(node).__name__
    if name == "ParseTimeDetectedTypeError":
        return name
    return f"{name}Ast"


_DECIMAL_DIGITS = frozenset("0123456789")
_NONZERO_DECIMAL_DIGITS = frozenset("123456789")
_OCTAL_DIGITS = frozenset("01234567")
_BINARY_DIGITS = frozenset("01")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class _Parser:
    """Packrat PEG parser state for a single input text.

    Every grammar rule in ``idl.treetop`` has a corresponding ``_r_<name>``
    method here. Each such method takes a starting position and returns
    either ``None`` (the rule failed to match at that position) or a
    ``(value, end)`` tuple holding the value it produced (an AST node, a
    plain string/int, or a small tuple/list of sub-results, as convenient
    for the caller) and the position immediately after the match. Results
    are memoized by ``(rule_name, position)`` so the whole grammar runs in
    time linear in the size of the input (packrat parsing).
    """

    __slots__ = ("_fail_expected", "_fail_pos", "_memo", "source", "text")

    def __init__(self, text: str, source: IdlSource) -> None:
        self.text = text
        self.source = source
        self._memo: dict[tuple[Any, ...], tuple[Any, int] | None] = {}
        self._fail_pos = -1
        self._fail_expected: set[str] = set()

    # -- failure tracking --------------------------------------------------

    def _fail(self, pos: int, expected: str) -> None:
        """Record that ``expected`` would have allowed matching to continue past ``pos``."""
        if pos > self._fail_pos:
            self._fail_pos = pos
            self._fail_expected = {expected}
        elif pos == self._fail_pos:
            self._fail_expected.add(expected)

    def error_at(self, pos: int, message: str) -> IdlSyntaxError:
        source = self.source
        return IdlSyntaxError(
            message,
            offset=pos,
            line=source.lineno(pos),
            column=source.column(pos),
            expected=sorted(self._fail_expected),
            source=source.label,
        )

    def furthest_failure_error(self) -> IdlSyntaxError:
        pos = max(self._fail_pos, 0)
        return self.error_at(pos, "syntax error")

    # -- whitespace --------------------------------------------------------

    def _ws0(self, pos: int) -> int:
        """Consume zero or more ``space`` (``' '``/``'\\n'``/``#...\\n`` comment) items."""
        text = self.text
        n = len(text)
        while pos < n:
            c = text[pos]
            if c == " " or c == "\n":
                pos += 1
                continue
            if c == "#":
                nl = text.find("\n", pos)
                if nl == -1:
                    # A comment with no trailing newline is *not* whitespace at
                    # all (the grammar's `comment` rule requires the "\n"), so
                    # stop without consuming the '#'.
                    break
                pos = nl + 1
                continue
            break
        return pos

    def _ws1(self, pos: int) -> int | None:
        """Consume one or more ``space`` items; ``None`` if zero were consumed."""
        end = self._ws0(pos)
        if end == pos:
            self._fail(pos, "whitespace")
            return None
        return end

    # -- generic terminal helpers -------------------------------------------

    def _lit(self, pos: int, literal: str) -> int | None:
        """Match a literal string exactly (no implicit word-boundary check)."""
        if self.text.startswith(literal, pos):
            return pos + len(literal)
        self._fail(pos, repr(literal))
        return None

    def _regex(self, pos: int, regex: re.Pattern[str], expected: str) -> re.Match[str] | None:
        m = regex.match(self.text, pos)
        if m is None:
            self._fail(pos, expected)
            return None
        return m

    # -- terminals -----------------------------------------------------------

    def _r_id(self, pos: int) -> tuple[Any, int] | None:
        key = ("id", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        m = self._regex(pos, _ID_RE, "identifier")
        result = (
            None
            if m is None
            else (ast.Id(source=self.source, start=pos, end=m.end(), name=m.group()), m.end())
        )
        memo[key] = result
        return result

    def _r_string(self, pos: int) -> tuple[Any, int] | None:
        key = ("string", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        end = self._match_string_len(pos)
        result = None
        if end is not None:
            result = (
                ast.StringLiteral(
                    source=self.source, start=pos, end=end, raw_text=self.text[pos:end]
                ),
                end,
            )
        memo[key] = result
        return result

    def _match_string_len(self, pos: int) -> int | None:
        """Mirror the `string` rule's `'"' (!'"' .)* '"'` structure directly.

        A plain one-shot regex match (as previously used) fails at `pos` for
        an unterminated string, losing Ruby's real failure position: Treetop
        would greedily consume every non-`"` character via the `(!'"' .)*`
        repetition and only then fail expecting the closing quote, at the
        position just past the last consumed character (EOF, for an
        unterminated string).
        """
        text = self.text
        n = len(text)
        if pos >= n or text[pos] != '"':
            self._fail(pos, "'\"'")
            return None
        p = pos + 1
        while p < n and text[p] != '"':
            p += 1
        if p >= n:
            self._fail(p, "'\"'")
            return None
        return p + 1

    def _r_dollar_variable(self, pos: int) -> tuple[Any, int] | None:
        key = ("dollar_variable", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        if self.text.startswith("$", pos):
            m = self._regex(pos + 1, _DOLLAR_VAR_NAME_RE, "'$' variable name")
            if m is not None:
                end = m.end()
                result = (
                    ast.BuiltinVariable(
                        source=self.source, start=pos, end=end, name=f"${m.group()}"
                    ),
                    end,
                )
        else:
            self._fail(pos, "'$'")
        memo[key] = result
        return result

    def _match_field_name(self, pos: int) -> tuple[str, int] | None:
        m = self._regex(pos, _FIELD_NAME_RE, "field name")
        return None if m is None else (m.group(), m.end())

    def _match_csr_name(self, pos: int) -> tuple[str, int] | None:
        m = self._regex(pos, _CSR_NAME_RE, "csr name")
        return None if m is None else (m.group(), m.end())

    def _match_csr_field_name(self, pos: int) -> tuple[str, int] | None:
        m = self._regex(pos, _CSR_FIELD_NAME_RE, "csr field name")
        return None if m is None else (m.group(), m.end())

    def _match_function_name(self, pos: int) -> tuple[str, int] | None:
        m = self._regex(pos, _FUNCTION_NAME_RE, "function name")
        return None if m is None else (m.group(), m.end())

    def _match_version_string(self, pos: int) -> int | None:
        m = self._regex(pos, _VERSION_STRING_RE, "version string")
        return None if m is None else m.end()

    # -- `int` (see module docstring for the full grammar) --------------------

    def _r_int(self, pos: int) -> tuple[Any, int] | None:
        key = ("int", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        end = self._match_int_len(pos)
        result = None
        if end is not None:
            result = (
                ast.IntLiteral(source=self.source, start=pos, end=end, raw_text=self.text[pos:end]),
                end,
            )
        else:
            self._fail(pos, "integer literal")
        memo[key] = result
        return result

    def _match_int_len(self, pos: int) -> int | None:
        text = self.text
        n = len(text)

        def at(p: int) -> str:
            return text[p] if p < n else ""

        # 1 & 2: plain decimal ([1-9][0-9]*), optionally suffixed with 's'
        # (signed), disjoint from the Verilog forms via the `!"'"` lookahead.
        # (`at(pos)` is `""` at EOF; checking membership in `_NONZERO_DECIMAL_DIGITS`
        # -- a `frozenset`, not a plain string -- keeps `""` from matching, since
        # `"" in "123456789"` is true in Python but `"" in frozenset(...)` is not.)
        if at(pos) in _NONZERO_DECIMAL_DIGITS:
            p = pos + 1
            while at(p) in _DECIMAL_DIGITS:
                p += 1
            if at(p) != "'":
                if at(p) == "s":
                    return p + 1
                return p
            # digits are immediately followed by a Verilog width-quote: both
            # decimal alternatives fail here, fall through to the forms below.

        # 3-8: C++-style '0b'/'0'/'0x', signed (with trailing 's') tried
        # before unsigned.
        for prefix, first_set, digit_name in (
            ("0b", _BINARY_DIGITS, "binary digit"),
            ("0", _OCTAL_DIGITS, "octal digit"),
            ("0x", _HEX_DIGITS, "hex digit"),
        ):
            if not text.startswith(prefix, pos):
                continue
            p = pos + len(prefix)
            if at(p) not in first_set:
                self._fail(p, digit_name)
                continue
            p += 1
            while at(p) in first_set or at(p) == "_":
                p += 1
            if at(p) == "s":
                return p + 1
        for prefix, first_set, digit_name in (
            ("0b", _BINARY_DIGITS, "binary digit"),
            ("0", _OCTAL_DIGITS, "octal digit"),
            ("0x", _HEX_DIGITS, "hex digit"),
        ):
            if not text.startswith(prefix, pos):
                continue
            p = pos + len(prefix)
            if at(p) not in first_set:
                self._fail(p, digit_name)
                continue
            p += 1
            while at(p) in first_set or at(p) == "_":
                p += 1
            return p

        # 9: bare '0', not followed by a Verilog width-quote, optional 's'.
        if at(pos) == "0" and at(pos + 1) != "'":
            return pos + 2 if at(pos + 1) == "s" else pos + 1

        # 10-17: Verilog-style, optionally signed, with an explicit or
        # 'MXLEN' bit width (or no width at all).
        for signed, radix in (
            (False, "b"),
            (False, "o"),
            (False, "d"),
            (False, "h"),
            (True, "b"),
            (True, "o"),
            (True, "d"),
            (True, "h"),
        ):
            end = self._match_verilog_int(pos, signed, radix)
            if end is not None:
                return end
        return None

    def _match_verilog_int(self, pos: int, signed: bool, radix: str) -> int | None:
        text = self.text
        n = len(text)

        def at(p: int) -> str:
            return text[p] if p < n else ""

        p = pos
        if at(p) in _DECIMAL_DIGITS:
            while at(p) in _DECIMAL_DIGITS:
                p += 1
        elif text.startswith("MXLEN", p):
            p += 5
        if at(p) != "'":
            self._fail(p, "'")
            return None
        p += 1
        if signed:
            if at(p) != "s":
                self._fail(p, "'s'")
                return None
            p += 1
        if radix == "b":
            if at(p) != "b":
                self._fail(p, "'b'")
                return None
            p += 1
            first_set = cont_extra = _BINARY_DIGITS | {"x", "X"}
            digit_name = "binary digit or 'x'/'X'"
        elif radix == "o":
            if at(p) != "o":
                self._fail(p, "'o'")
                return None
            p += 1
            first_set = cont_extra = _OCTAL_DIGITS | {"x", "X"}
            digit_name = "octal digit or 'x'/'X'"
        elif radix == "h":
            if at(p) != "h":
                self._fail(p, "'h'")
                return None
            p += 1
            first_set = cont_extra = _HEX_DIGITS | {"x", "X"}
            digit_name = "hex digit or 'x'/'X'"
        else:
            # decimal radix letter 'd' is optional; no x/X permitted.
            if at(p) == "d":
                p += 1
            first_set = cont_extra = _DECIMAL_DIGITS
            digit_name = "decimal digit"
        if at(p) not in first_set:
            self._fail(p, digit_name)
            return None
        p += 1
        while at(p) in cont_extra or at(p) == "_":
            p += 1
        return p

    # -- `type_name` / `enum_ref` ---------------------------------------------

    def _r_type_name(self, pos: int) -> tuple[Any, int] | None:
        key = ("type_name", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_type_name(pos)
        memo[key] = result
        return result

    def _match_type_name(self, pos: int) -> tuple[Any, int] | None:
        p = self._lit(pos, "Bits")
        if p is not None:
            p = self._ws0(p)
            p2 = self._lit(p, "<")
            if p2 is not None:
                p2 = self._ws0(p2)
                r = self._r_template_safe_expression(p2)
                if r is not None:
                    width_expr, p3 = r
                    p3 = self._ws0(p3)
                    p4 = self._lit(p3, ">")
                    if p4 is not None and not (
                        p4 < len(self.text) and self.text[p4] in _ALNUM_ASCII
                    ):
                        node = ast.BuiltinTypeName(
                            source=self.source,
                            start=pos,
                            end=p4,
                            children=(width_expr,),
                            type_name="Bits",
                        )
                        return (node, p4)
        m = self._regex(pos, _UPPER_ID_RE, "type name")
        if m is None:
            return None
        end = m.end()
        name = m.group()
        if name in _BUILTIN_TYPE_NAMES:
            node = ast.BuiltinTypeName(source=self.source, start=pos, end=end, type_name=name)
        else:
            node = ast.UserTypeName(source=self.source, start=pos, end=end, name=name)
        return (node, end)

    def _r_enum_ref(self, pos: int) -> tuple[Any, int] | None:
        key = ("enum_ref", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_type_name(pos)
        if r is not None:
            enum_class, p = r
            p = self._ws0(p)
            p2 = self._lit(p, "::")
            if p2 is not None:
                p2 = self._ws0(p2)
                r2 = self._r_type_name(p2)
                if r2 is not None:
                    member, end = r2
                    result = (
                        ast.EnumRef(
                            source=self.source,
                            start=pos,
                            end=end,
                            class_name=enum_class.text,
                            member_name=member.text,
                        ),
                        end,
                    )
        memo[key] = result
        return result

    # -- binary-operator precedence chain (p0..p9, template-safe p3..p9) -----

    def _match_operator(
        self, pos: int, ops: tuple[tuple[str, str | None], ...]
    ) -> tuple[str, int] | None:
        text = self.text
        n = len(text)
        for op_text, forbidden_next in ops:
            if text.startswith(op_text, pos):
                end = pos + len(op_text)
                if forbidden_next is not None and end < n and text[end] == forbidden_next:
                    continue
                return (op_text, end)
        return None

    def _climb(
        self, pos: int, left_fn: Any, right_fn: Any, ops: tuple[tuple[str, str | None], ...]
    ) -> tuple[Any, int] | None:
        r = left_fn(pos)
        if r is None:
            return None
        node, p = r
        while True:
            p2 = self._ws0(p)
            op_match = self._match_operator(p2, ops)
            if op_match is None:
                break
            op_text, p3 = op_match
            p4 = self._ws0(p3)
            r2 = right_fn(p4)
            if r2 is None:
                break
            right_node, p5 = r2
            node = ast.BinaryExpression(
                source=self.source, start=pos, end=p5, children=(node, right_node), op=op_text
            )
            p = p5
        return (node, p)

    def _r_p_binary(self, level: int, pos: int) -> tuple[Any, int] | None:
        key = ("p_binary", level, pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        if level == 0:
            operand = self._r_unary_expression
        else:
            operand = lambda p, lvl=level - 1: self._r_p_binary(lvl, p)
        result = self._climb(pos, operand, operand, _P_OPERATORS[level])
        memo[key] = result
        return result

    def _r_template_safe_p_binary(self, level: int, pos: int) -> tuple[Any, int] | None:
        key = ("ts_p_binary", level, pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        if level == 3:
            operand = lambda p: self._r_p_binary(2, p)
            result = self._climb(pos, operand, operand, _P3_TEMPLATE_OPERATORS)
        else:
            left = lambda p, lvl=level - 1: self._r_template_safe_p_binary(lvl, p)
            right = lambda p, lvl=level - 1: self._r_p_binary(lvl, p)
            result = self._climb(pos, left, right, _P_OPERATORS[level])
        memo[key] = result
        return result

    # -- `expression` / `template_safe_expression` roots, ternary -----------

    def _r_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_ternary(pos, template_safe=False)
        if result is None:
            result = self._r_p_binary(9, pos)
        memo[key] = result
        return result

    def _r_template_safe_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("template_safe_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_ternary(pos, template_safe=True)
        if result is None:
            result = self._r_template_safe_p_binary(9, pos)
        memo[key] = result
        return result

    def _try_ternary(self, pos: int, *, template_safe: bool) -> tuple[Any, int] | None:
        key = ("ternary", template_safe, pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_template_safe_p_binary(9, pos) if template_safe else self._r_p_binary(9, pos)
        if r is not None:
            cond, p = r
            p = self._ws0(p)
            p2 = self._lit(p, "?")
            if p2 is not None:
                p2 = self._ws0(p2)
                r2 = self._r_expression(p2)
                if r2 is not None:
                    t_node, p3 = r2
                    p3 = self._ws0(p3)
                    p4 = self._lit(p3, ":")
                    if p4 is not None:
                        p4 = self._ws0(p4)
                        r3 = self._r_expression(p4)
                        if r3 is not None:
                            f_node, end = r3
                            result = (
                                ast.TernaryOperatorExpression(
                                    source=self.source,
                                    start=pos,
                                    end=end,
                                    children=(cond, t_node, f_node),
                                ),
                                end,
                            )
        memo[key] = result
        return result

    # -- implication expressions / constraint bodies --------------------------

    def _match_implication_tail(self, pos: int) -> tuple[Any, Any, int] | None:
        """Match ``[antecedent] space* '->' space* consequent``.

        Shared by both alternatives of ``implication_expression``.
        ``antecedent`` is ``None`` when absent (the caller substitutes a
        synthetic zero-width :class:`~udb.idl.ast.TrueExpression`).
        """
        ant_result = self._r_p_binary(9, pos)
        if ant_result is not None:
            antecedent, p = ant_result
        else:
            antecedent, p = None, pos
        p = self._ws0(p)
        p2 = self._lit(p, "->")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        cons_result = self._r_p_binary(9, p3)
        if cons_result is None:
            return None
        consequent, end = cons_result
        return (antecedent, consequent, end)

    def _r_implication_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("implication_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        # Alt 1: leading '(' is mandatory, trailing ')' is optional.
        p = self._lit(pos, "(")
        if p is not None:
            tail = self._match_implication_tail(self._ws0(p))
            if tail is not None:
                antecedent, consequent, p2 = tail
                p3 = self._ws0(p2)
                p4 = self._lit(p3, ")")
                end = p4 if p4 is not None else p3
                result = self._make_implication(pos, end, antecedent, consequent)
        # Alt 2: no parens at all.
        if result is None:
            tail = self._match_implication_tail(pos)
            if tail is not None:
                antecedent, consequent, end = tail
                result = self._make_implication(pos, end, antecedent, consequent)
        memo[key] = result
        return result

    def _make_implication(
        self, pos: int, end: int, antecedent: Any, consequent: Any
    ) -> tuple[Any, int]:
        # A missing antecedent becomes a synthetic zero-width `TrueExpression`
        # located at the very start of the whole `implication_expression` match
        # (Ruby: `interval.first...interval.first`), not wherever the antecedent
        # would otherwise have started.
        if antecedent is None:
            antecedent = ast.TrueExpression(source=self.source, start=pos, end=pos)
        node = ast.ImplicationExpression(
            source=self.source, start=pos, end=end, children=(antecedent, consequent)
        )
        return (node, end)

    def _r_implication_statement(self, pos: int) -> tuple[Any, int] | None:
        key = ("implication_statement", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_implication_expression(pos)
        if r is not None:
            expr, p = r
            p = self._ws0(p)
            p2 = self._lit(p, ";")
            if p2 is not None:
                result = (
                    ast.ImplicationStatement(
                        source=self.source, start=pos, end=p2, children=(expr,)
                    ),
                    p2,
                )
        memo[key] = result
        return result

    def _r_implication_for_loop(self, pos: int) -> tuple[Any, int] | None:
        key = ("implication_for_loop", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_for_loop(
            pos, include_trailing_space=False, stmt_choice=self._implication_for_loop_stmt_choice
        )
        memo[key] = result
        return result

    def _implication_for_loop_stmt_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_implication_statement(pos)
        if r is not None:
            return r
        return self._r_implication_for_loop(pos)

    def _r_constraint_body(self, pos: int) -> tuple[Any, int] | None:
        key = ("constraint_body", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        start = self._ws0(pos)
        stmts: list[Any] = []
        p = start
        while True:
            r = self._implication_for_loop_stmt_choice(p)
            if r is None:
                break
            stmt, p2 = r
            stmts.append(stmt)
            p = self._ws0(p2)
        result = None
        if stmts:
            result = (
                ast.ConstraintBody(source=self.source, start=pos, end=p, children=tuple(stmts)),
                p,
            )
        else:
            self._fail(pos, "implication statement or for-loop")
        memo[key] = result
        return result

    # -- dontcare, array-size declarations ------------------------------------

    def _r_dontcare_lvalue(self, pos: int) -> tuple[Any, int] | None:
        key = ("dontcare_lvalue", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "-")
        if p is not None:
            result = (ast.DontCareLvalue(source=self.source, start=pos, end=p), p)
        memo[key] = result
        return result

    def _r_dontcare_return(self, pos: int) -> tuple[Any, int] | None:
        key = ("dontcare_return", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "-")
        if p is not None:
            result = (ast.DontCareReturn(source=self.source, start=pos, end=p), p)
        memo[key] = result
        return result

    def _r_ary_size_decl(self, pos: int) -> tuple[Any, int] | None:
        # No dedicated AST node: this rule just wraps a bracketed expression.
        key = ("ary_size_decl", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "[")
        if p is not None:
            p = self._ws0(p)
            r = self._r_expression(p)
            if r is not None:
                expr, p2 = r
                p2 = self._ws0(p2)
                p3 = self._lit(p2, "]")
                if p3 is not None:
                    result = (expr, p3)
        memo[key] = result
        return result

    # -- declarations ----------------------------------------------------------

    def _match_single_declaration_with_initialization(
        self, pos: int, *, for_iter_var: bool
    ) -> tuple[Any, int] | None:
        r = self._r_type_name(pos)
        if r is None:
            return None
        type_name, p = r
        p1 = self._ws1(p)
        if p1 is None:
            return None
        r = self._r_id(p1)
        if r is None:
            return None
        id_node, p = r
        p = self._ws0(p)
        ary_size = None
        r = self._r_ary_size_decl(p)
        if r is not None:
            ary_size, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "=")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r = self._r_expression(p3)
        if r is None:
            return None
        rhs, end = r
        children = (
            (type_name, id_node, rhs) if ary_size is None else (type_name, id_node, rhs, ary_size)
        )
        node = ast.VariableDeclarationWithInitialization(
            source=self.source, start=pos, end=end, children=children, for_iter_var=for_iter_var
        )
        return (node, end)

    def _r_single_declaration_with_initialization(self, pos: int) -> tuple[Any, int] | None:
        key = ("single_declaration_with_initialization", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_single_declaration_with_initialization(pos, for_iter_var=False)
        memo[key] = result
        return result

    def _r_for_loop_iteration_variable_declaration(self, pos: int) -> tuple[Any, int] | None:
        key = ("for_loop_iteration_variable_declaration", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_single_declaration_with_initialization(pos, for_iter_var=True)
        memo[key] = result
        return result

    def _r_single_declaration(self, pos: int) -> tuple[Any, int] | None:
        key = ("single_declaration", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_type_name(pos)
        if r is not None:
            type_name, p = r
            p1 = self._ws1(p)
            if p1 is not None:
                r2 = self._r_id(p1)
                if r2 is not None:
                    id_node, end = r2
                    ary_size = None
                    r3 = self._match_ws0_then(end, self._r_ary_size_decl)
                    if r3 is not None:
                        ary_size, end = r3
                    children = (
                        (type_name, id_node) if ary_size is None else (type_name, id_node, ary_size)
                    )
                    result = (
                        ast.VariableDeclaration(
                            source=self.source, start=pos, end=end, children=children
                        ),
                        end,
                    )
        memo[key] = result
        return result

    def _match_ws0_then(self, pos: int, rule: Any) -> tuple[Any, int] | None:
        """Try ``space* rule`` as a unit, backtracking fully to ``pos`` on failure."""
        p = self._ws0(pos)
        r = rule(p)
        return r

    def _r_declaration(self, pos: int) -> tuple[Any, int] | None:
        key = ("declaration", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_type_name(pos)
        if r is not None:
            type_name, p = r
            p1 = self._ws1(p)
            if p1 is not None:
                r2 = self._r_id(p1)
                if r2 is not None:
                    first, p2 = r2
                    names = [first]
                    p = p2
                    count = 0
                    while True:
                        p3 = self._ws0(p)
                        p4 = self._lit(p3, ",")
                        if p4 is None:
                            break
                        p5 = self._ws0(p4)
                        r3 = self._r_id(p5)
                        if r3 is None:
                            break
                        nxt, p6 = r3
                        names.append(nxt)
                        p = p6
                        count += 1
                    if count > 0:
                        end = self._ws0(p)
                        result = (
                            ast.MultiVariableDeclaration(
                                source=self.source, start=pos, end=end, children=(type_name, *names)
                            ),
                            end,
                        )
        if result is None:
            result = self._r_single_declaration(pos)
        memo[key] = result
        return result

    # -- assignments -------------------------------------------------------------

    def _match_lvalue_or_dontcare(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_id(pos)
        if r is not None:
            return r
        return self._r_dontcare_lvalue(pos)

    def _try_multi_variable_assignment(self, pos: int) -> tuple[Any, int] | None:
        p = self._lit(pos, "(")
        if p is None:
            return None
        r = self._match_lvalue_or_dontcare(p)
        if r is None:
            return None
        first, p = r
        p = self._ws0(p)
        variables = [first]
        count = 0
        while True:
            p2 = self._lit(p, ",")
            if p2 is None:
                break
            p3 = self._ws0(p2)
            r2 = self._match_lvalue_or_dontcare(p3)
            if r2 is None:
                break
            var, p4 = r2
            variables.append(var)
            p = self._ws0(p4)
            count += 1
        if count == 0:
            return None
        p2 = self._lit(p, ")")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        p4 = self._lit(p3, "=")
        if p4 is None:
            return None
        p5 = self._ws0(p4)
        r3 = self._r_function_call(p5)
        if r3 is None:
            return None
        call, end = r3
        node = ast.MultiVariableAssignment(
            source=self.source, start=pos, end=end, children=(*variables, call)
        )
        return (node, end)

    def _try_dollar_variable_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_dollar_variable(pos)
        if r is None:
            return None
        dvar, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "=")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._r_expression(p3)
        if r2 is None:
            return None
        rhs, end = r2
        dollar_name = dvar.name
        node: Any
        if dollar_name == "$pc":
            node = ast.PcAssignment(source=self.source, start=pos, end=end, children=(rhs,))
        else:
            node = ast.ParseTimeDetectedTypeError(
                source=self.source, start=pos, end=end, reason=f"{dollar_name} is not assignable"
            )
        return (node, end)

    def _try_var_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_id(pos)
        if r is None:
            return None
        id_node, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "=")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._r_expression(p3)
        if r2 is None:
            return None
        rhs, end = r2
        node = ast.VariableAssignment(
            source=self.source, start=pos, end=end, children=(id_node, rhs)
        )
        return (node, end)

    def _try_csr_field_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_csr_field_access_expression(pos)
        if r is None:
            return None
        csr_field, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "=")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._r_expression(p3)
        if r2 is None:
            return None
        rhs, end = r2
        node = ast.CsrFieldAssignment(
            source=self.source, start=pos, end=end, children=(csr_field, rhs)
        )
        return (node, end)

    def _try_field_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_id(pos)
        if r is None:
            return None
        id_node, p = r
        p = self._ws0(p)
        p2 = self._lit(p, ".")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._match_field_name(p3)
        if r2 is None:
            return None
        field_name, p4 = r2
        p5 = self._ws0(p4)
        p6 = self._lit(p5, "=")
        if p6 is None:
            return None
        p7 = self._ws0(p6)
        r3 = self._r_expression(p7)
        if r3 is None:
            return None
        rhs, end = r3
        node = ast.FieldAssignment(
            source=self.source, start=pos, end=end, children=(id_node, rhs), field_name=field_name
        )
        return (node, end)

    def _match_bracket_group(self, pos: int) -> tuple[Any, int] | None:
        """Match ``'[' space* msb:(expression space* ':' space*)? lsb:expression space* ']' space*``.

        Returns ``((msb_or_None, lsb), end)``.
        """
        p = self._lit(pos, "[")
        if p is None:
            return None
        p = self._ws0(p)
        msb = None
        r = self._r_expression(p)
        if r is not None:
            cand_msb, p2 = r
            p3 = self._ws0(p2)
            p4 = self._lit(p3, ":")
            if p4 is not None:
                msb = cand_msb
                p = self._ws0(p4)
        r2 = self._r_expression(p)
        if r2 is None:
            return None
        lsb, p5 = r2
        p6 = self._ws0(p5)
        p7 = self._lit(p6, "]")
        if p7 is None:
            return None
        end = self._ws0(p7)
        return ((msb, lsb), end)

    def _try_ary_range_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_ary_eligible_expression(pos)
        if r is None:
            return None
        var, p = r
        p = self._ws0(p)
        brackets = []
        while True:
            r2 = self._match_bracket_group(p)
            if r2 is None:
                break
            bracket, p2 = r2
            brackets.append(bracket)
            p = p2
        if not brackets:
            return None
        p2 = self._lit(p, "=")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r3 = self._r_expression(p3)
        if r3 is None:
            return None
        rhs, end = r3
        for msb, lsb in brackets[:-1]:
            if msb is None:
                var = ast.AryElementAccess(
                    source=self.source, start=pos, end=end, children=(var, lsb)
                )
            else:
                var = ast.AryRangeAccess(
                    source=self.source, start=pos, end=end, children=(var, msb, lsb)
                )
        last_msb, last_lsb = brackets[-1]
        node: Any
        if last_msb is None:
            node = ast.AryElementAssignment(
                source=self.source, start=pos, end=end, children=(var, last_lsb, rhs)
            )
        else:
            node = ast.AryRangeAssignment(
                source=self.source, start=pos, end=end, children=(var, last_msb, last_lsb, rhs)
            )
        return (node, end)

    def _r_assignment(self, pos: int) -> tuple[Any, int] | None:
        key = ("assignment", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_multi_variable_assignment(pos)
        if result is None:
            result = self._r_single_declaration_with_initialization(pos)
        if result is None:
            result = self._try_dollar_variable_assignment(pos)
        if result is None:
            result = self._try_var_assignment(pos)
        if result is None:
            result = self._try_csr_field_assignment(pos)
        if result is None:
            result = self._try_field_assignment(pos)
        if result is None:
            result = self._try_ary_range_assignment(pos)
        memo[key] = result
        return result

    # -- rval, csr access, paren/replication/concatenation --------------------

    def _r_rval(self, pos: int) -> tuple[Any, int] | None:
        key = ("rval", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._r_int(pos)
        if result is None:
            result = self._r_dollar_variable(pos)
        if result is None:
            result = self._r_string(pos)
        if result is None:
            result = self._r_id(pos)
        memo[key] = result
        return result

    def _r_csr_register_access_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("csr_register_access_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "CSR")
        if p is not None:
            p = self._ws0(p)
            p2 = self._lit(p, "[")
            if p2 is not None:
                p3 = self._ws0(p2)
                r = self._match_csr_name(p3)
                if r is not None:
                    csr_name, p4 = r
                    p5 = self._ws0(p4)
                    p6 = self._lit(p5, "]")
                    if p6 is not None:
                        result = (
                            ast.CsrReadExpression(
                                source=self.source, start=pos, end=p6, csr_name=csr_name
                            ),
                            p6,
                        )
        memo[key] = result
        return result

    def _r_csr_field_access_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("csr_field_access_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_csr_register_access_expression(pos)
        if r is not None:
            csr, p = r
            p = self._ws0(p)
            p2 = self._lit(p, ".")
            if p2 is not None:
                p3 = self._ws0(p2)
                r2 = self._match_csr_field_name(p3)
                if r2 is not None:
                    field_name, end = r2
                    result = (
                        ast.CsrFieldReadExpression(
                            source=self.source,
                            start=pos,
                            end=end,
                            children=(csr,),
                            field_name=field_name,
                        ),
                        end,
                    )
        memo[key] = result
        return result

    def _r_paren_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("paren_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "(")
        if p is not None:
            p = self._ws0(p)
            r = self._r_expression(p)
            if r is not None:
                expr, p2 = r
                p3 = self._ws0(p2)
                p4 = self._lit(p3, ")")
                if p4 is not None:
                    result = (
                        ast.ParenExpression(
                            source=self.source, start=pos, end=p4, children=(expr,)
                        ),
                        p4,
                    )
        memo[key] = result
        return result

    def _r_replication_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("replication_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "{")
        if p is not None:
            p = self._ws0(p)
            r = self._r_expression(p)
            if r is not None:
                n, p2 = r
                p3 = self._ws0(p2)
                p4 = self._lit(p3, "{")
                if p4 is not None:
                    p5 = self._ws0(p4)
                    r2 = self._r_expression(p5)
                    if r2 is not None:
                        v, p6 = r2
                        p7 = self._ws0(p6)
                        p8 = self._lit(p7, "}")
                        if p8 is not None:
                            p9 = self._ws0(p8)
                            p10 = self._lit(p9, "}")
                            if p10 is not None:
                                result = (
                                    ast.ReplicationExpression(
                                        source=self.source, start=pos, end=p10, children=(n, v)
                                    ),
                                    p10,
                                )
        memo[key] = result
        return result

    def _r_concatenation_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("concatenation_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "{")
        if p is not None:
            p = self._ws0(p)
            r = self._r_expression(p)
            if r is not None:
                first, p2 = r
                exprs = [first]
                p = p2
                while True:
                    p3 = self._ws0(p)
                    p4 = self._lit(p3, ",")
                    if p4 is None:
                        break
                    p5 = self._ws0(p4)
                    r2 = self._r_expression(p5)
                    if r2 is None:
                        break
                    nxt, p6 = r2
                    exprs.append(nxt)
                    p = p6
                p7 = self._ws0(p)
                p8 = self._lit(p7, "}")
                if p8 is not None:
                    result = (
                        ast.ConcatenationExpression(
                            source=self.source, start=pos, end=p8, children=tuple(exprs)
                        ),
                        p8,
                    )
        memo[key] = result
        return result

    def _r_post_dec(self, pos: int) -> tuple[Any, int] | None:
        key = ("post_dec", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_rval(pos)
        if r is not None:
            rval, p = r
            p = self._ws0(p)
            p2 = self._lit(p, "--")
            if p2 is not None:
                result = (
                    ast.PostDecrementExpression(
                        source=self.source, start=pos, end=p2, children=(rval,)
                    ),
                    p2,
                )
        memo[key] = result
        return result

    def _r_post_inc(self, pos: int) -> tuple[Any, int] | None:
        key = ("post_inc", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_rval(pos)
        if r is not None:
            rval, p = r
            p = self._ws0(p)
            p2 = self._lit(p, "++")
            if p2 is not None:
                result = (
                    ast.PostIncrementExpression(
                        source=self.source, start=pos, end=p2, children=(rval,)
                    ),
                    p2,
                )
        memo[key] = result
        return result

    def _r_field_access_eligible_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("field_access_eligible_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._r_paren_expression(pos)
        if result is None:
            result = self._r_function_call(pos)
        if result is None:
            result = self._r_rval(pos)
        memo[key] = result
        return result

    def _r_field_access_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("field_access_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_field_access_eligible_expression(pos)
        if r is not None:
            obj, p = r
            p = self._ws0(p)
            p2 = self._lit(p, ".")
            if p2 is not None:
                p3 = self._ws0(p2)
                r2 = self._match_field_name(p3)
                if r2 is not None:
                    field_name, end = r2
                    result = (
                        ast.FieldAccessExpression(
                            source=self.source,
                            start=pos,
                            end=end,
                            children=(obj,),
                            field_name=field_name,
                        ),
                        end,
                    )
        memo[key] = result
        return result

    # -- argument lists, function calls ---------------------------------------

    def _match_arg_list(self, pos: int) -> tuple[list[Any], int]:
        """Match ``first:expression? rest:(space* ',' space* expression)*``.

        Shared verbatim by ``function_arg_list`` and ``dollar_arg_list`` (the
        two grammar rules are textually identical). Never fails.
        """
        args: list[Any] = []
        p = pos
        r = self._r_expression(p)
        if r is not None:
            first, p = r
            args.append(first)
        while True:
            p2 = self._ws0(p)
            p3 = self._lit(p2, ",")
            if p3 is None:
                break
            p4 = self._ws0(p3)
            r2 = self._r_expression(p4)
            if r2 is None:
                break
            nxt, p5 = r2
            args.append(nxt)
            p = p5
        return (args, p)

    def _r_function_call(self, pos: int) -> tuple[Any, int] | None:
        key = ("function_call", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_plain_function_call(pos)
        if result is None:
            result = self._try_csr_software_write(pos)
        if result is None:
            result = self._try_csr_function_call(pos)
        memo[key] = result
        return result

    def _try_plain_function_call(self, pos: int) -> tuple[Any, int] | None:
        r = self._match_function_name(pos)
        if r is None:
            return None
        name, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "(")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        args, p4 = self._match_arg_list(p3)
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ")")
        if p6 is None:
            return None
        node = ast.FunctionCallExpression(
            source=self.source, start=pos, end=p6, children=tuple(args), name=name
        )
        return (node, p6)

    def _try_csr_software_write(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_csr_register_access_expression(pos)
        if r is None:
            return None
        csr, p = r
        p = self._ws0(p)
        p2 = self._lit(p, ".")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        p4 = self._lit(p3, "sw_write")
        if p4 is None:
            return None
        p5 = self._ws0(p4)
        p6 = self._lit(p5, "(")
        if p6 is None:
            return None
        p7 = self._ws0(p6)
        r2 = self._r_expression(p7)
        if r2 is None:
            return None
        value, p8 = r2
        p9 = self._ws0(p8)
        p10 = self._lit(p9, ")")
        if p10 is None:
            return None
        node = ast.CsrSoftwareWrite(source=self.source, start=pos, end=p10, children=(csr, value))
        return (node, p10)

    def _try_csr_function_call(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_csr_register_access_expression(pos)
        if r is None:
            return None
        csr, p = r
        p = self._ws0(p)
        p2 = self._lit(p, ".")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._match_function_name(p3)
        if r2 is None:
            return None
        function_name, p4 = r2
        p5 = self._ws0(p4)
        p6 = self._lit(p5, "(")
        if p6 is None:
            return None
        p7 = self._ws0(p6)
        args, p8 = self._match_arg_list(p7)
        p9 = self._ws0(p8)
        p10 = self._lit(p9, ")")
        if p10 is None:
            return None
        node = ast.CsrFunctionCall(
            source=self.source,
            start=pos,
            end=p10,
            children=(csr, *args),
            function_name=function_name,
        )
        return (node, p10)

    # -- array-eligible expressions, array access -----------------------------

    def _r_ary_eligible_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("ary_eligible_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._r_dollar_function_call(pos)
        if result is None:
            result = self._r_paren_expression(pos)
        if result is None:
            result = self._r_replication_expression(pos)
        if result is None:
            result = self._r_concatenation_expression(pos)
        if result is None:
            result = self._r_field_access_expression(pos)
        if result is None:
            result = self._r_function_call(pos)
        if result is None:
            result = self._r_csr_field_access_expression(pos)
        if result is None:
            result = self._r_csr_register_access_expression(pos)
        if result is None:
            result = self._r_rval(pos)
        memo[key] = result
        return result

    def _r_ary_access(self, pos: int) -> tuple[Any, int] | None:
        key = ("ary_access", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_ary_eligible_expression(pos)
        if r is not None:
            var, p = r
            p = self._ws0(p)
            brackets = []
            while True:
                r2 = self._match_bracket_group(p)
                if r2 is None:
                    break
                bracket, p2 = r2
                brackets.append(bracket)
                p = p2
            if brackets:
                end = p
                for msb, lsb in brackets:
                    if msb is None:
                        var = ast.AryElementAccess(
                            source=self.source, start=pos, end=end, children=(var, lsb)
                        )
                    else:
                        var = ast.AryRangeAccess(
                            source=self.source, start=pos, end=end, children=(var, msb, lsb)
                        )
                result = (var, end)
        memo[key] = result
        return result

    # -- `$`-builtin function calls -------------------------------------------

    def _r_dollar_function_call(self, pos: int) -> tuple[Any, int] | None:
        key = ("dollar_function_call", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "$")
        if p is not None:
            m = self._regex(p, _DOLLAR_FUNC_NAME_RE, "'$' function name")
            if m is not None:
                name = m.group()
                p2 = self._ws0(m.end())
                p3 = self._lit(p2, "(")
                if p3 is not None:
                    p4 = self._ws0(p3)
                    args, p5 = self._match_arg_list(p4)
                    p6 = self._ws0(p5)
                    p7 = self._lit(p6, ")")
                    if p7 is not None:
                        result = (self._build_dollar_call(pos, p7, name, args), p7)
        memo[key] = result
        return result

    def _build_dollar_call(self, pos: int, end: int, name: str, args: list[Any]) -> Any:
        dollar_name = f"${name}"
        spec = _DOLLAR_BUILTINS.get(dollar_name)
        if spec is None:
            return ast.ParseTimeDetectedTypeError(
                source=self.source,
                start=pos,
                end=end,
                reason=f"{dollar_name} is not a builtin function",
            )
        ast_class, expected_count, validations = spec
        if len(args) != expected_count:
            plural = "" if expected_count == 1 else "s"
            return ast.ParseTimeDetectedTypeError(
                source=self.source,
                start=pos,
                end=end,
                reason=f"{dollar_name} expects {expected_count} argument{plural}; {len(args)} given",
            )
        for arg_index, (classes, description) in validations.items():
            if not isinstance(args[arg_index], classes):
                return ast.ParseTimeDetectedTypeError(
                    source=self.source,
                    start=pos,
                    end=end,
                    reason=(
                        f"{dollar_name} expects argument {arg_index + 1} to be {description}; "
                        f"{_ruby_class_name(args[arg_index])} given"
                    ),
                )
        # `$enum_size`/`$enum_element_size`/`$enum_to_a`/`$enum` all normalize
        # a bare identifier argument (matched as plain `id`, since `enum_ref`
        # requires a `::member` suffix) into a `UserTypeName` node at
        # construction time (see e.g. `EnumSizeAst#initialize` in ast.rb).
        if validations:
            arg0 = args[0]
            if isinstance(arg0, ast.Id):
                args = [
                    ast.UserTypeName(
                        source=self.source, start=arg0.start, end=arg0.end, name=arg0.name
                    ),
                    *args[1:],
                ]
        return ast_class(source=self.source, start=pos, end=end, children=tuple(args))

    # -- `unary_expression` (17-way) -------------------------------------------

    def _r_unary_operator(self, pos: int) -> tuple[str, int] | None:
        key = ("unary_operator", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        for op in ("~", "-", "!"):
            p = self._lit(pos, op)
            if p is not None:
                result = (op, p)
                break
        memo[key] = result
        return result

    def _r_unary_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("unary_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "true")
        if p is not None:
            result = (ast.TrueExpression(source=self.source, start=pos, end=p), p)
        if result is None:
            p = self._lit(pos, "false")
            if p is not None:
                result = (ast.FalseExpression(source=self.source, start=pos, end=p), p)
        if result is None:
            result = self._try_array_literal(pos)
        if result is None:
            result = self._r_ary_access(pos)
        if result is None:
            result = self._r_dollar_function_call(pos)
        if result is None:
            result = self._r_paren_expression(pos)
        if result is None:
            result = self._try_unary_operator_expression(pos)
        if result is None:
            result = self._r_post_dec(pos)
        if result is None:
            result = self._r_post_inc(pos)
        if result is None:
            result = self._r_replication_expression(pos)
        if result is None:
            result = self._r_concatenation_expression(pos)
        if result is None:
            result = self._r_field_access_expression(pos)
        if result is None:
            result = self._r_function_call(pos)
        if result is None:
            result = self._r_csr_field_access_expression(pos)
        if result is None:
            result = self._r_csr_register_access_expression(pos)
        if result is None:
            result = self._r_enum_ref(pos)
        if result is None:
            result = self._r_rval(pos)
        memo[key] = result
        return result

    def _try_unary_operator_expression(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_unary_operator(pos)
        if r is None:
            return None
        op, p = r
        p = self._ws0(p)
        r2 = self._r_unary_expression(p)
        if r2 is None:
            return None
        expr, end = r2
        node = ast.UnaryOperatorExpression(
            source=self.source, start=pos, end=end, children=(expr,), op=op
        )
        return (node, end)

    def _try_array_literal(self, pos: int) -> tuple[Any, int] | None:
        p = self._lit(pos, "[")
        if p is None:
            return None
        p = self._ws0(p)
        r = self._r_expression(p)
        if r is None:
            return None
        first, p2 = r
        exprs = [first]
        p = p2
        while True:
            p3 = self._ws0(p)
            p4 = self._lit(p3, ",")
            if p4 is None:
                break
            p5 = self._ws0(p4)
            r2 = self._r_expression(p5)
            if r2 is None:
                break
            nxt, p6 = r2
            exprs.append(nxt)
            p = p6
        p7 = self._ws0(p)
        p8 = self._lit(p7, "]")
        if p8 is None:
            return None
        node = ast.ArrayLiteral(source=self.source, start=pos, end=p8, children=tuple(exprs))
        return (node, p8)

    # -- statements -------------------------------------------------------------

    def _match_call_or_assignment(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_function_call(pos)
        if r is not None:
            return r
        return self._r_assignment(pos)

    def _try_conditional_statement(self, pos: int) -> tuple[Any, int] | None:
        r = self._match_call_or_assignment(pos)
        if r is None:
            return None
        action, p = r
        p = self._ws0(p)
        p2 = self._lit(p, "if")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r2 = self._r_expression(p3)
        if r2 is None:
            return None
        cond, p4 = r2
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ";")
        if p6 is None:
            return None
        node = ast.ConditionalStatement(
            source=self.source, start=pos, end=p6, children=(action, cond)
        )
        return (node, p6)

    def _try_plain_statement(self, pos: int) -> tuple[Any, int] | None:
        r = self._match_call_or_assignment(pos)
        if r is None:
            r = self._r_declaration(pos)
        if r is None:
            return None
        action, p = r
        p = self._ws0(p)
        p2 = self._lit(p, ";")
        if p2 is None:
            return None
        node = ast.Statement(source=self.source, start=pos, end=p2, children=(action,))
        return (node, p2)

    def _r_statement(self, pos: int) -> tuple[Any, int] | None:
        key = ("statement", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_conditional_statement(pos)
        if result is None:
            result = self._try_plain_statement(pos)
        memo[key] = result
        return result

    def _r_return_expression(self, pos: int) -> tuple[Any, int] | None:
        key = ("return_expression", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "return")
        if p is not None:
            vals: list[Any] = []
            p1 = self._ws1(p)
            if p1 is not None:
                r = self._r_expression(p1)
                if r is None:
                    r = self._r_dontcare_return(p1)
                if r is not None:
                    first, p = r
                    vals.append(first)
            while True:
                p3 = self._ws0(p)
                p4 = self._lit(p3, ",")
                if p4 is None:
                    break
                p5 = self._ws0(p4)
                r2 = self._r_expression(p5)
                if r2 is None:
                    r2 = self._r_dontcare_return(p5)
                if r2 is None:
                    break
                nxt, p = r2
                vals.append(nxt)
            result = (
                ast.ReturnExpression(source=self.source, start=pos, end=p, children=tuple(vals)),
                p,
            )
        memo[key] = result
        return result

    def _r_return_statement(self, pos: int) -> tuple[Any, int] | None:
        key = ("return_statement", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        r = self._r_return_expression(pos)
        if r is not None:
            ret_expr, p = r
            # Alt 1: conditional return.
            p1 = self._ws0(p)
            p2 = self._lit(p1, "if")
            if p2 is not None:
                p3 = self._ws0(p2)
                r2 = self._r_expression(p3)
                if r2 is not None:
                    cond, p4 = r2
                    p5 = self._ws0(p4)
                    p6 = self._lit(p5, ";")
                    if p6 is not None:
                        result = (
                            ast.ConditionalReturnStatement(
                                source=self.source, start=pos, end=p6, children=(ret_expr, cond)
                            ),
                            p6,
                        )
            # Alt 2: plain return.
            if result is None:
                p1b = self._ws0(p)
                p2b = self._lit(p1b, ";")
                if p2b is not None:
                    result = (
                        ast.ReturnStatement(
                            source=self.source, start=pos, end=p2b, children=(ret_expr,)
                        ),
                        p2b,
                    )
        memo[key] = result
        return result

    # -- if blocks (shared by `function_if_block`/`execute_if_block`) --------

    def _match_stmt_block(self, pos: int, stmt_choice: Any) -> tuple[list[Any], int]:
        """Match ``(e:(...) space*)+`` (or ``*``): repeat ``stmt_choice`` then ``space*``.

        Never fails; callers enforce the ``+`` (at-least-one) requirement
        themselves by checking whether the returned list is empty.
        """
        stmts: list[Any] = []
        p = pos
        while True:
            r = stmt_choice(p)
            if r is None:
                break
            stmt, p2 = r
            stmts.append(stmt)
            p = self._ws0(p2)
        return (stmts, p)

    def _match_if_block(self, pos: int, stmt_choice: Any) -> tuple[Any, int] | None:
        p = self._lit(pos, "if")
        if p is None:
            return None
        p = self._ws0(p)
        p2 = self._lit(p, "(")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r = self._r_expression(p3)
        if r is None:
            return None
        if_cond, p4 = r
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ")")
        if p6 is None:
            return None
        p7 = self._ws0(p6)
        p8 = self._lit(p7, "{")
        if p8 is None:
            return None
        body_start = self._ws0(p8)
        if_body_stmts, body_end = self._match_stmt_block(body_start, stmt_choice)
        if not if_body_stmts:
            return None
        p9 = self._lit(body_end, "}")
        if p9 is None:
            return None
        if_body = ast.IfBody(
            source=self.source, start=body_start, end=body_end, children=tuple(if_body_stmts)
        )
        p = p9

        eifs: list[Any] = []
        while True:
            eif_start = p
            p2b = self._ws0(p)
            p3b = self._lit(p2b, "else")
            if p3b is None:
                break
            p4b = self._ws1(p3b)
            if p4b is None:
                break
            p5b = self._lit(p4b, "if")
            if p5b is None:
                break
            p6b = self._ws0(p5b)
            p7b = self._lit(p6b, "(")
            if p7b is None:
                break
            p8b = self._ws0(p7b)
            r2 = self._r_expression(p8b)
            if r2 is None:
                break
            eif_cond, p9b = r2
            p10b = self._ws0(p9b)
            p11b = self._lit(p10b, ")")
            if p11b is None:
                break
            p12b = self._ws0(p11b)
            p13b = self._lit(p12b, "{")
            if p13b is None:
                break
            eif_body_start = self._ws0(p13b)
            eif_stmts, eif_body_end = self._match_stmt_block(eif_body_start, stmt_choice)
            if not eif_stmts:
                break
            p14b = self._lit(eif_body_end, "}")
            if p14b is None:
                break
            eif_body = ast.IfBody(
                source=self.source,
                start=eif_body_start,
                end=eif_body_end,
                children=tuple(eif_stmts),
            )
            # The `ElseIf` node's own span is the *whole* labeled repetition
            # element (including the leading `space*` before `else` and the
            # closing `}`), distinct from its nested `IfBody`'s body-only span.
            eif_node = ast.ElseIf(
                source=self.source, start=eif_start, end=p14b, children=(eif_cond, eif_body)
            )
            eifs.append(eif_node)
            p = p14b

        final_else = None
        p2c = self._ws0(p)
        p3c = self._lit(p2c, "else")
        if p3c is not None:
            p4c = self._ws0(p3c)
            p5c = self._lit(p4c, "{")
            if p5c is not None:
                else_body_start = self._ws0(p5c)
                else_stmts, else_body_end = self._match_stmt_block(else_body_start, stmt_choice)
                if else_stmts:
                    p6c = self._lit(else_body_end, "}")
                    if p6c is not None:
                        final_else = ast.IfBody(
                            source=self.source,
                            start=else_body_start,
                            end=else_body_end,
                            children=tuple(else_stmts),
                        )
                        p = p6c
        if final_else is None:
            final_else = ast.IfBody(source=self.source, start=0, end=0, children=())

        end = p
        node = ast.If(
            source=self.source, start=pos, end=end, children=(if_cond, if_body, *eifs, final_else)
        )
        return (node, end)

    def _function_if_block_stmt_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_return_statement(pos)
        if r is not None:
            return r
        r = self._r_statement(pos)
        if r is not None:
            return r
        r = self._r_function_if_block(pos)
        if r is not None:
            return r
        return self._r_for_loop(pos)

    def _r_function_if_block(self, pos: int) -> tuple[Any, int] | None:
        key = ("function_if_block", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_if_block(pos, self._function_if_block_stmt_choice)
        memo[key] = result
        return result

    def _execute_if_block_stmt_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_statement(pos)
        if r is not None:
            return r
        r = self._r_execute_if_block(pos)
        if r is not None:
            return r
        return self._r_for_loop(pos)

    def _r_execute_if_block(self, pos: int) -> tuple[Any, int] | None:
        key = ("execute_if_block", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_if_block(pos, self._execute_if_block_stmt_choice)
        memo[key] = result
        return result

    # -- for loops -------------------------------------------------------------

    def _match_for_loop_action(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_assignment(pos)
        if r is not None:
            return r
        r = self._r_post_inc(pos)
        if r is not None:
            return r
        return self._r_post_dec(pos)

    def _match_for_loop(
        self, pos: int, *, include_trailing_space: bool, stmt_choice: Any
    ) -> tuple[Any, int] | None:
        p = self._lit(pos, "for")
        if p is None:
            return None
        p = self._ws0(p)
        p2 = self._lit(p, "(")
        if p2 is None:
            return None
        p3 = self._ws0(p2)
        r = self._r_for_loop_iteration_variable_declaration(p3)
        if r is None:
            return None
        init, p4 = r
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ";")
        if p6 is None:
            return None
        p7 = self._ws0(p6)
        r2 = self._r_expression(p7)
        if r2 is None:
            return None
        condition, p8 = r2
        p9 = self._ws0(p8)
        p10 = self._lit(p9, ";")
        if p10 is None:
            return None
        p11 = self._ws0(p10)
        r3 = self._match_for_loop_action(p11)
        if r3 is None:
            return None
        action, p12 = r3
        p13 = self._ws0(p12)
        p14 = self._lit(p13, ")")
        if p14 is None:
            return None
        p15 = self._ws0(p14)
        p16 = self._lit(p15, "{")
        if p16 is None:
            return None
        body_start = self._ws0(p16)
        stmts, body_end = self._match_stmt_block(body_start, stmt_choice)
        if not stmts:
            return None
        p17 = self._lit(body_end, "}")
        if p17 is None:
            return None
        end = self._ws0(p17) if include_trailing_space else p17
        node = ast.ForLoop(
            source=self.source, start=pos, end=end, children=(init, condition, action, *stmts)
        )
        return (node, end)

    def _for_loop_stmt_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_return_statement(pos)
        if r is not None:
            return r
        r = self._r_statement(pos)
        if r is not None:
            return r
        r = self._r_function_if_block(pos)
        if r is not None:
            return r
        return self._r_for_loop(pos)

    def _r_for_loop(self, pos: int) -> tuple[Any, int] | None:
        key = ("for_loop", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._match_for_loop(
            pos, include_trailing_space=True, stmt_choice=self._for_loop_stmt_choice
        )
        memo[key] = result
        return result

    # -- function/instruction-operation body roots ----------------------------

    def _function_statement_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_return_statement(pos)
        if r is not None:
            return r
        r = self._r_statement(pos)
        if r is not None:
            return r
        r = self._r_function_if_block(pos)
        if r is not None:
            return r
        return self._r_for_loop(pos)

    def _instruction_operation_choice(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_statement(pos)
        if r is not None:
            return r
        r = self._r_execute_if_block(pos)
        if r is not None:
            return r
        return self._r_for_loop(pos)

    def _r_function_body(self, pos: int) -> tuple[Any, int] | None:
        key = ("function_body", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        start = self._ws0(pos)
        stmts, end = self._match_stmt_block(start, self._function_statement_choice)
        result = (
            ast.FunctionBody(source=self.source, start=pos, end=end, children=tuple(stmts)),
            end,
        )
        memo[key] = result
        return result

    def _r_instruction_operation(self, pos: int) -> tuple[Any, int] | None:
        key = ("instruction_operation", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        start = self._ws0(pos)
        stmts, end = self._match_stmt_block(start, self._instruction_operation_choice)
        result = (
            ast.FunctionBody(source=self.source, start=pos, end=end, children=tuple(stmts)),
            end,
        )
        memo[key] = result
        return result

    # -- top-level definitions ---------------------------------------------------

    def _r_include_statement(self, pos: int) -> tuple[Any, int] | None:
        key = ("include_statement", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "include")
        if p is not None:
            p1 = self._ws1(p)
            if p1 is not None:
                r = self._r_string(p1)
                if r is not None:
                    string_node, p2 = r
                    p3 = self._ws1(p2)
                    if p3 is not None:
                        result = (
                            ast.IncludeStatement(
                                source=self.source, start=pos, end=p3, children=(string_node,)
                            ),
                            p3,
                        )
        memo[key] = result
        return result

    def _r_global_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("global_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_global_with_initialization(pos)
        if result is None:
            result = self._try_plain_global(pos)
        memo[key] = result
        return result

    def _try_global_with_initialization(self, pos: int) -> tuple[Any, int] | None:
        # const:('const'? space+)? -- an optional 'const' keyword (itself
        # optional) followed by mandatory whitespace; the flag is discarded.
        # If the mandatory `space+` fails, the *whole* optional group backs
        # off to `pos` (even a matched 'const' is un-consumed).
        p_const = self._lit(pos, "const")
        p_after_const = p_const if p_const is not None else pos
        p_ws = self._ws1(p_after_const)
        p = p_ws if p_ws is not None else pos
        r = self._r_single_declaration_with_initialization(p)
        if r is None:
            return None
        decl, p4 = r
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ";")
        if p6 is None:
            return None
        node = ast.GlobalWithInitialization(source=self.source, start=pos, end=p6, children=(decl,))
        return (node, p6)

    def _try_plain_global(self, pos: int) -> tuple[Any, int] | None:
        r = self._r_declaration(pos)
        if r is None:
            return None
        decl, p = r
        p = self._ws0(p)
        p2 = self._lit(p, ";")
        if p2 is None:
            return None
        node = ast.Global(source=self.source, start=pos, end=p2, children=(decl,))
        return (node, p2)

    def _r_enum_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("enum_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._try_builtin_enum_definition(pos)
        if result is None:
            result = self._try_plain_enum_definition(pos)
        memo[key] = result
        return result

    def _try_builtin_enum_definition(self, pos: int) -> tuple[Any, int] | None:
        p = self._lit(pos, "generated")
        if p is None:
            return None
        p1 = self._ws1(p)
        if p1 is None:
            return None
        p2 = self._lit(p1, "enum")
        if p2 is None:
            return None
        p3 = self._ws1(p2)
        if p3 is None:
            return None
        r = self._r_type_name(p3)
        if r is None:
            return None
        user_type, p4 = r
        p5 = self._ws0(p4)
        p6 = self._lit(p5, ";")
        if p6 is None:
            return None
        node = ast.BuiltinEnumDefinition(
            source=self.source, start=pos, end=p6, children=(user_type,)
        )
        return (node, p6)

    def _try_plain_enum_definition(self, pos: int) -> tuple[Any, int] | None:
        p = self._lit(pos, "enum")
        if p is None:
            return None
        p1 = self._ws1(p)
        if p1 is None:
            return None
        r = self._r_type_name(p1)
        if r is None:
            return None
        user_type, p2 = r
        p3 = self._ws1(p2)
        if p3 is None:
            return None
        p4 = self._lit(p3, "{")
        if p4 is None:
            return None
        p5 = self._ws0(p4)
        names: list[Any] = []
        values: list[Any] = []
        p = p5
        while True:
            r2 = self._r_type_name(p)
            if r2 is None:
                break
            name_node, p6 = r2
            p7 = self._ws1(p6)
            if p7 is None:
                break
            value = None
            r3 = self._r_int(p7)
            if r3 is not None:
                cand_value, p8 = r3
                p9 = self._ws1(p8)
                if p9 is not None:
                    value = cand_value
                    p = p9
                else:
                    p = p7
            else:
                p = p7
            names.append(name_node)
            values.append(value)
        if not names:
            return None
        p10 = self._ws0(p)
        p11 = self._lit(p10, "}")
        if p11 is None:
            return None
        real_values = tuple(v for v in values if v is not None)
        node = ast.EnumDefinition(
            source=self.source,
            start=pos,
            end=p11,
            children=(user_type, *names, *real_values),
            user_type=user_type,
            element_names=tuple(names),
            element_values=tuple(values),
        )
        return (node, p11)

    def _r_bitfield_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("bitfield_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "bitfield")
        if p is not None:
            p = self._ws0(p)
            p2 = self._lit(p, "(")
            if p2 is not None:
                p3 = self._ws0(p2)
                r = self._r_int(p3)
                if r is not None:
                    size, p4 = r
                    p5 = self._ws0(p4)
                    p6 = self._lit(p5, ")")
                    if p6 is not None:
                        p7 = self._ws0(p6)
                        r2 = self._r_type_name(p7)
                        if r2 is not None:
                            name_node, p8 = r2
                            p9 = self._ws0(p8)
                            p10 = self._lit(p9, "{")
                            if p10 is not None:
                                p11 = self._ws0(p10)
                                fields, p12 = self._match_bitfield_fields(p11)
                                if fields:
                                    p13 = self._ws0(p12)
                                    p14 = self._lit(p13, "}")
                                    if p14 is not None:
                                        result = (
                                            ast.BitfieldDefinition(
                                                source=self.source,
                                                start=pos,
                                                end=p14,
                                                children=(name_node, size, *fields),
                                            ),
                                            p14,
                                        )
        memo[key] = result
        return result

    def _match_bitfield_fields(self, pos: int) -> tuple[list[Any], int]:
        """Match ``e:(field_name space+ range:(int lsb:(space* '-' space* int)?) space+)+``.

        Each field element gets its **own** interval (not the whole rule's
        shared span, unlike ``ary_access``); returns ``([], pos)`` (never
        ``None``) if zero fields matched, so the caller can enforce the ``+``.
        """
        fields: list[Any] = []
        p = pos
        while True:
            field_start = p
            r = self._match_field_name(p)
            if r is None:
                break
            field_name, p2 = r
            p3 = self._ws1(p2)
            if p3 is None:
                break
            r2 = self._r_int(p3)
            if r2 is None:
                break
            msb, p4 = r2
            lsb = None
            p5 = self._ws0(p4)
            p6 = self._lit(p5, "-")
            if p6 is not None:
                p7 = self._ws0(p6)
                r3 = self._r_int(p7)
                if r3 is not None:
                    lsb, p8 = r3
                    p4 = p8
            p9 = self._ws1(p4)
            if p9 is None:
                break
            children = (msb,) if lsb is None else (msb, lsb)
            fields.append(
                ast.BitfieldFieldDefinition(
                    source=self.source,
                    start=field_start,
                    end=p9,
                    children=children,
                    field_name=field_name,
                )
            )
            p = p9
        return (fields, p)

    def _r_struct_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("struct_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "struct")
        if p is not None:
            p = self._ws0(p)
            r = self._r_type_name(p)
            if r is not None:
                name_node, p2 = r
                p3 = self._ws0(p2)
                p4 = self._lit(p3, "{")
                if p4 is not None:
                    p5 = self._ws0(p4)
                    member_types: list[Any] = []
                    member_names: list[str] = []
                    p = p5
                    while True:
                        r2 = self._r_type_name(p)
                        if r2 is None:
                            break
                        member_type, p6 = r2
                        p7 = self._ws1(p6)
                        if p7 is None:
                            break
                        r3 = self._r_id(p7)
                        if r3 is None:
                            break
                        member_id, p8 = r3
                        p9 = self._ws0(p8)
                        p10 = self._lit(p9, ";")
                        if p10 is None:
                            break
                        p11 = self._ws0(p10)
                        member_types.append(member_type)
                        member_names.append(member_id.name)
                        p = p11
                    if member_types:
                        p12 = self._lit(p, "}")
                        if p12 is not None:
                            result = (
                                ast.StructDefinition(
                                    source=self.source,
                                    start=pos,
                                    end=p12,
                                    children=tuple(member_types),
                                    name=name_node.text,
                                    member_names=tuple(member_names),
                                ),
                                p12,
                            )
        memo[key] = result
        return result

    def _match_function_common(
        self, pos: int, *, allow_multi_return: bool
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], str, int] | None:
        """Match the part shared by ``body_function_definition``/``builtin_function_definition``
        after the qualifier keyword and ``'function' space+``: ``function_name space* '{' space*``,
        the optional ``ret``/``args`` groups, and the mandatory ``description`` block.

        Returns ``(return_types, arguments, description_text, end_pos)`` where
        ``end_pos`` is the position right after the description block's own
        trailing ``space*`` (i.e. right before whichever of ``body_block``/``'}'``
        comes next).
        """
        p = self._ws0(pos)
        p2 = self._lit(p, "{")
        if p2 is None:
            return None
        p = self._ws0(p2)

        return_types: list[Any] = []
        p3 = self._lit(p, "returns")
        if p3 is not None:
            p4 = self._ws1(p3)
            if p4 is not None:
                r = self._r_type_name(p4)
                if r is not None:
                    first_ret, p5 = r
                    return_types.append(first_ret)
                    p = p5
                    if allow_multi_return:
                        while True:
                            p6 = self._ws0(p)
                            p7 = self._lit(p6, ",")
                            if p7 is None:
                                break
                            p8 = self._ws0(p7)
                            r2 = self._r_type_name(p8)
                            if r2 is None:
                                break
                            nxt, p9 = r2
                            return_types.append(nxt)
                            p = p9
                    p10 = self._ws1(p)
                    if p10 is None:
                        return None
                    p = p10

        arguments: list[Any] = []
        p11 = self._lit(p, "arguments")
        if p11 is not None:
            p12 = self._ws1(p11)
            if p12 is not None:
                r3 = self._r_single_declaration(p12)
                if r3 is not None:
                    first_arg, p13 = r3
                    arguments.append(first_arg)
                    p_args = p13
                    while True:
                        p14 = self._ws0(p_args)
                        p15 = self._lit(p14, ",")
                        if p15 is None:
                            break
                        p16 = self._ws0(p15)
                        r4 = self._r_single_declaration(p16)
                        if r4 is None:
                            break
                        nxt_arg, p17 = r4
                        arguments.append(nxt_arg)
                        p_args = p17
                    p18 = self._ws1(p_args)
                    if p18 is None:
                        return None
                    p = p18

        p19 = self._lit(p, "description")
        if p19 is None:
            return None
        p20 = self._ws0(p19)
        p21 = self._lit(p20, "{")
        if p21 is None:
            return None
        p22 = self._ws0(p21)
        desc_start = p22
        desc_end = self._match_description_content(p22)
        if desc_end is None:
            return None
        p23 = self._lit(desc_end, "}")
        if p23 is None:
            return None
        p24 = self._ws0(p23)
        return (tuple(return_types), tuple(arguments), self.text[desc_start:desc_end], p24)

    def _match_description_content(self, pos: int) -> int | None:
        """Match ``desc:([^}] / "\\n")+`` (mandatory, at least one character)."""
        text = self.text
        n = len(text)
        p = pos
        while p < n and text[p] != "}":
            p += 1
        if p == pos:
            self._fail(pos, "function description")
            return None
        return p

    def _r_body_function_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("body_function_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        qualifier = "normal"
        p = pos
        p1 = self._lit(pos, "external")
        if p1 is not None:
            p2 = self._ws1(p1)
            if p2 is not None:
                qualifier = "external"
                p = p2
        p3 = self._lit(p, "function")
        if p3 is not None:
            p4 = self._ws1(p3)
            if p4 is not None:
                r = self._match_function_name(p4)
                if r is not None:
                    name, p5 = r
                    common = self._match_function_common(p5, allow_multi_return=True)
                    if common is not None:
                        return_types, arguments, description, p6 = common
                        p7 = self._lit(p6, "body")
                        if p7 is not None:
                            p8 = self._ws0(p7)
                            p9 = self._lit(p8, "{")
                            if p9 is not None:
                                p10 = self._ws0(p9)
                                body_r = self._r_function_body(p10)
                                if body_r is not None:
                                    body, p11 = body_r
                                    p12 = self._ws0(p11)
                                    p13 = self._lit(p12, "}")
                                    if p13 is not None:
                                        p14 = self._ws0(p13)
                                        p15 = self._lit(p14, "}")
                                        if p15 is not None:
                                            children = (*return_types, *arguments, body)
                                            result = (
                                                ast.FunctionDef(
                                                    source=self.source,
                                                    start=pos,
                                                    end=p15,
                                                    children=children,
                                                    name=name,
                                                    qualifier=qualifier,
                                                    description=description,
                                                    num_return_types=len(return_types),
                                                    num_arguments=len(arguments),
                                                ),
                                                p15,
                                            )
        memo[key] = result
        return result

    def _r_builtin_function_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("builtin_function_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        qualifier = None
        p = self._lit(pos, "builtin")
        if p is not None:
            qualifier = "builtin"
        else:
            p = self._lit(pos, "generated")
            if p is not None:
                qualifier = "generated"
        if p is not None:
            p1 = self._ws1(p)
            if p1 is not None:
                p2 = self._lit(p1, "function")
                if p2 is not None:
                    p3 = self._ws1(p2)
                    if p3 is not None:
                        r = self._match_function_name(p3)
                        if r is not None:
                            name, p4 = r
                            common = self._match_function_common(p4, allow_multi_return=False)
                            if common is not None:
                                return_types, arguments, description, p5 = common
                                p6 = self._lit(p5, "}")
                                if p6 is not None:
                                    children = (*return_types, *arguments)
                                    result = (
                                        ast.FunctionDef(
                                            source=self.source,
                                            start=pos,
                                            end=p6,
                                            children=children,
                                            name=name,
                                            qualifier=qualifier,
                                            description=description,
                                            num_return_types=len(return_types),
                                            num_arguments=len(arguments),
                                        ),
                                        p6,
                                    )
        memo[key] = result
        return result

    def _r_function_definition(self, pos: int) -> tuple[Any, int] | None:
        key = ("function_definition", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = self._r_builtin_function_definition(pos)
        if result is None:
            result = self._r_body_function_definition(pos)
        memo[key] = result
        return result

    def _r_fetch(self, pos: int) -> tuple[Any, int] | None:
        key = ("fetch", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        result = None
        p = self._lit(pos, "fetch")
        if p is not None:
            p = self._ws0(p)
            p2 = self._lit(p, "{")
            if p2 is not None:
                p3 = self._ws0(p2)
                r = self._r_function_body(p3)
                if r is not None:
                    body, p4 = r
                    p5 = self._ws0(p4)
                    p6 = self._lit(p5, "}")
                    if p6 is not None:
                        result = (
                            ast.Fetch(source=self.source, start=pos, end=p6, children=(body,)),
                            p6,
                        )
        memo[key] = result
        return result

    def _r_isa(self, pos: int) -> tuple[Any, int] | None:
        key = ("isa", pos)
        memo = self._memo
        if key in memo:
            return memo[key]
        p = self._ws0(pos)
        p2 = self._lit(p, "%version:")
        if p2 is None:
            self._fail(p, "'%version:'")
            memo[key] = None
            return None
        p3 = self._ws1(p2)
        if p3 is None:
            memo[key] = None
            return None
        p4 = self._match_version_string(p3)
        if p4 is None:
            memo[key] = None
            return None
        p5 = self._ws1(p4)
        if p5 is None:
            memo[key] = None
            return None
        definitions: list[Any] = []
        p = p5
        while True:
            r = self._match_isa_definition(p)
            if r is None:
                break
            definition, p2b = r
            if definition is not None:
                definitions.append(definition)
            p = p2b
        node = ast.Isa(source=self.source, start=pos, end=p, children=tuple(definitions))
        result = (node, p)
        memo[key] = result
        return result

    def _match_isa_definition(self, pos: int) -> tuple[Any, int] | None:
        """One iteration of ``isa``'s ``definitions:(... / space+)*`` repetition.

        Returns ``(None, end)`` for the whitespace-only fallback alternative
        (dropped from the final children list, mirroring
        ``IsaSyntaxNode#to_ast``'s ``reject { |e| e.elements.all?(&:space?) }``),
        or ``None`` outright if nothing at all (not even whitespace) matched.
        """
        for rule in (
            self._r_include_statement,
            self._r_global_definition,
            self._r_enum_definition,
            self._r_bitfield_definition,
            self._r_struct_definition,
            self._r_function_definition,
            self._r_fetch,
        ):
            r = rule(pos)
            if r is not None:
                return r
        end = self._ws1(pos)
        if end is not None:
            return (None, end)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ROOT_RULES: dict[str, str] = {
    "isa": "_r_isa",
    "function_body": "_r_function_body",
    "instruction_operation": "_r_instruction_operation",
    "expression": "_r_expression",
    "constraint_body": "_r_constraint_body",
    "for_loop": "_r_for_loop",
}


def parse(
    text: str,
    root: str = "isa",
    *,
    source: IdlSource | None = None,
    label: str = "<idl>",
    starting_line: int = 0,
    starting_offset: int = 0,
    line_file_offsets: tuple[int, ...] | None = None,
) -> ast.Node:
    """Parse ``text`` starting at grammar rule ``root``, returning the resulting AST node.

    Mirrors ``Idl::Compiler#compile_*`` (``tools/ruby-gems/idlc/lib/idlc.rb``):
    the whole of ``text`` must be consumed (trailing, non-whitespace input
    after a structurally-complete match is a syntax error, matching
    Treetop's top-level ``parse`` requiring the root rule to consume all
    input), and a failure anywhere raises :class:`~udb.idl.errors.IdlSyntaxError`
    describing the *furthest* position any alternative got to, with the set
    of terminals that would have allowed parsing to continue from there.

    Args:
        text: The IDL source to parse.
        root: One of :data:`ROOTS` (``"isa"`` by default).
        source: An already-constructed :class:`~udb.idl.source.IdlSource` to
            use instead of building one from ``label``/``starting_line``/etc.
            When given, ``text`` must equal ``source.text``.
        label: Passed to :class:`~udb.idl.source.IdlSource` when ``source``
            is not given.
        starting_line: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.
        starting_offset: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.
        line_file_offsets: Passed to :class:`~udb.idl.source.IdlSource` when
            ``source`` is not given.

    Raises:
        ValueError: ``root`` is not one of :data:`ROOTS`.
        IdlSyntaxError: ``text`` could not be parsed as ``root``.
    """
    if root not in _ROOT_RULES:
        msg = f"unknown IDL parse root {root!r}; expected one of {ROOTS}"
        raise ValueError(msg)
    if source is None:
        source = IdlSource(
            text=text,
            label=label,
            starting_line=starting_line,
            starting_offset=starting_offset,
            line_file_offsets=line_file_offsets,
        )
    elif source.text != text:
        msg = "parse(): `text` must equal `source.text` when `source` is given"
        raise ValueError(msg)

    parser = _Parser(text, source)
    rule = getattr(parser, _ROOT_RULES[root])
    result = rule(0)
    if result is None:
        raise parser.furthest_failure_error()
    node, end = result
    # Mirror Treetop's real `consume_all_input` semantics exactly (see
    # `treetop/runtime/compiled_parser.rb`): the parse only succeeds if the
    # root rule's own match consumed the *entire* input; there is no special
    # leniency for trailing whitespace at this outer level. Whichever
    # trailing whitespace a given root tolerates (e.g. `isa`, `function_body`)
    # is intentionally consumed by that rule's own grammar production, not by
    # this wrapper.
    if text[end:] != "":
        parser._fail(end, "end of input")
        raise parser.furthest_failure_error()
    return node


def parse_isa(text: str, **kwargs: Any) -> ast.Isa:
    """Parse ``text`` as the ``isa`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "isa", **kwargs)
    assert isinstance(node, ast.Isa)
    return node


def parse_function_body(text: str, **kwargs: Any) -> ast.FunctionBody:
    """Parse ``text`` as the ``function_body`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "function_body", **kwargs)
    assert isinstance(node, ast.FunctionBody)
    return node


def parse_instruction_operation(text: str, **kwargs: Any) -> ast.FunctionBody:
    """Parse ``text`` as the ``instruction_operation`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "instruction_operation", **kwargs)
    assert isinstance(node, ast.FunctionBody)
    return node


def parse_expression(text: str, **kwargs: Any) -> ast.Node:
    """Parse ``text`` as the ``expression`` root. See :func:`parse` for keyword arguments."""
    return parse(text, "expression", **kwargs)


def parse_constraint_body(text: str, **kwargs: Any) -> ast.ConstraintBody:
    """Parse ``text`` as the ``constraint_body`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "constraint_body", **kwargs)
    assert isinstance(node, ast.ConstraintBody)
    return node


def parse_for_loop(text: str, **kwargs: Any) -> ast.ForLoop:
    """Parse ``text`` as the ``for_loop`` root. See :func:`parse` for keyword arguments."""
    node = parse(text, "for_loop", **kwargs)
    assert isinstance(node, ast.ForLoop)
    return node
