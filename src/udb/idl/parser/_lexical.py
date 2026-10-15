# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Identifiers, strings, numeric literals, type names, and enum references."""

from __future__ import annotations

from typing import Any

from .. import ast
from ._base import (
    _ALNUM_ASCII,
    _BINARY_DIGITS,
    _BUILTIN_TYPE_NAMES,
    _CSR_FIELD_NAME_RE,
    _CSR_NAME_RE,
    _DECIMAL_DIGITS,
    _DOLLAR_VAR_NAME_RE,
    _FIELD_NAME_RE,
    _FUNCTION_NAME_RE,
    _HEX_DIGITS,
    _ID_RE,
    _NONZERO_DECIMAL_DIGITS,
    _OCTAL_DIGITS,
    _UPPER_ID_RE,
    _VERSION_STRING_RE,
)


class _LexicalRules:
    """Identifiers, strings, numeric literals, type names, and enum references."""

    __slots__ = ()

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
