# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Shared parser state, terminal tables, and low-level matching helpers."""

from __future__ import annotations

import re
from typing import Any

from .. import ast
from ..errors import IdlSyntaxError
from ..source import IdlSource

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


class _ParserBase:
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

    __slots__ = ("_fail_expected", "_fail_pos", "_invalid_nodes", "_memo", "source", "text")

    def __init__(self, text: str, source: IdlSource) -> None:
        self.text = text
        self.source = source
        self._memo: dict[tuple[Any, ...], tuple[Any, int] | None] = {}
        self._fail_pos = -1
        self._fail_expected: set[str] = set()
        # id(node) -> (offset, message) for nodes the grammar accepts but that
        # must be rejected if they end up in the final tree.
        self._invalid_nodes: dict[int, tuple[int, str]] = {}

    # -- failure tracking --------------------------------------------------

    def _fail(self, pos: int, expected: str) -> None:
        """Record that ``expected`` would have allowed matching to continue past ``pos``."""
        if pos > self._fail_pos:
            self._fail_pos = pos
            self._fail_expected = {expected}
        elif pos == self._fail_pos:
            self._fail_expected.add(expected)

    def error_at(
        self, pos: int, message: str, *, expected: list[str] | None = None
    ) -> IdlSyntaxError:
        source = self.source
        return IdlSyntaxError(
            message,
            offset=pos,
            line=source.failure_lineno(pos),
            column=source.column(pos),
            expected=sorted(self._fail_expected) if expected is None else expected,
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
                    # stop without consuming the '#'. Treetop's comment rule
                    # still scans to EOF looking for the "\n", so record the
                    # failure there to match its error position.
                    self._fail(n, repr("\n"))
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
