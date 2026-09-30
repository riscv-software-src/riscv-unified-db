# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Statement rules: declarations, assignments, returns, if blocks, loops, and bodies."""

from __future__ import annotations

from typing import Any

from .. import ast


class _StatementRules:
    """Statement rules: declarations, assignments, returns, if blocks, loops, and bodies."""

    __slots__ = ()

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
            missing_first_at: int | None = None
            p1 = self._ws1(p)
            if p1 is not None:
                r = self._r_expression(p1)
                if r is None:
                    r = self._r_dontcare_return(p1)
                if r is not None:
                    first, p = r
                    vals.append(first)
            if not vals:
                missing_first_at = p
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
            node = ast.ReturnExpression(source=self.source, start=pos, end=p, children=tuple(vals))
            if missing_first_at is not None and vals:
                # The grammar admits `return , x`, but Ruby's lowering crashes on
                # it (see doc/python-migration-bugfixes.md). Reject it, but only
                # if this node survives into the final tree.
                self._invalid_nodes[id(node)] = (
                    missing_first_at,
                    "return value list is missing its first value",
                )
            result = (node, p)
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
