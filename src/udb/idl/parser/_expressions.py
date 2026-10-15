# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Expression rules: operators, ternaries, implications, calls, access, and literals."""

from __future__ import annotations

from typing import Any

from .. import ast
from ._base import (
    _DOLLAR_BUILTINS,
    _DOLLAR_FUNC_NAME_RE,
    _P3_TEMPLATE_OPERATORS,
    _P_OPERATORS,
    _ruby_class_name,
)


class _ExpressionRules:
    """Expression rules: operators, ternaries, implications, calls, access, and literals."""

    __slots__ = ()

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
