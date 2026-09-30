# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Top-level rules: includes, globals, enums, bitfields, structs, functions, and ``isa``."""

from __future__ import annotations

from typing import Any

from .. import ast


class _DefinitionRules:
    """Top-level rules: includes, globals, enums, bitfields, structs, functions, and ``isa``."""

    __slots__ = ()

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
