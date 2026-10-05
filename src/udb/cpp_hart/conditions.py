# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lower ordinary condition trees to Boolean or three-valued native guards."""

from udb import conditions as c

from .types import CppGenerationError, cpp_type, literal


def condition_cpp(condition, context, *, parent="this", parameter_result=False):
    def visit(node):
        if isinstance(node, c.ConstantCondition):
            return ("Yes" if node.value else "No") if parameter_result else str(node.value).lower()
        if isinstance(node, c.ExtensionTerm):
            tests = []
            for req in node.requirements:
                text = str(req)
                if parameter_result:
                    tests.append(
                        f'cfg.ext_req_is_met(ExtensionName::{node.name}, VersionRequirement("{text}"sv))'
                    )
                else:
                    tests.append(
                        f'{parent}->template _implemented_version_Q_<ExtensionName::{node.name}, "{text}">()'
                    )
            return "(" + " && ".join(tests) + ")"
        if isinstance(node, c.XlenTerm):
            if parameter_result:
                return visit(c.ParameterTerm("MXLEN", c.ParameterOperator.EQUAL, node.value))
            return f"({parent}->xlen() == {node.value}_b)"
        if isinstance(node, c.ParameterTerm):
            if parameter_result:
                dtype = context.table.get(node.name).type
                value = f'std::any_cast<const {cpp_type(dtype)}&>(cfg.param_value("{node.name}"))'
            else:
                value = f"{parent}->params().{node.name}.value()"
            if node.index is not None:
                value += f".at({node.index})"
            elif node.size:
                value += ".size()"
            elif node.bit_range is not None:
                high, low = node.bit_range
                value += f".template extract<{high}, {low}>()"
            ops = {
                c.ParameterOperator.EQUAL: "==",
                c.ParameterOperator.NOT_EQUAL: "!=",
                c.ParameterOperator.LESS_THAN: "<",
                c.ParameterOperator.LESS_THAN_OR_EQUAL: "<=",
                c.ParameterOperator.GREATER_THAN: ">",
                c.ParameterOperator.GREATER_THAN_OR_EQUAL: ">=",
            }
            if node.operator in ops:
                test = f"({value} {ops[node.operator]} {literal(node.value)})"
            elif node.operator is c.ParameterOperator.INCLUDES:
                test = f"_array_includes({value}, {literal(node.value)})"
            elif node.operator is c.ParameterOperator.ONE_OF:
                test = (
                    "(" + " || ".join(f"({value} == {literal(item)})" for item in node.value) + ")"
                )
            else:
                raise CppGenerationError(f"Unsupported native parameter comparison: {node}")
            if parameter_result:
                return f'(cfg.has_param_value("{node.name}") ? ({test} ? Yes : No) : Maybe)'
            return test
        if isinstance(node, c.Not):
            return f"!({visit(node.child)})"
        if isinstance(node, c.Implies):
            return f"(!({visit(node.antecedent)}) || ({visit(node.consequent)}))"
        if isinstance(node, (c.AllOf, c.AnyOf, c.NoneOf)):
            if not node.children:
                return visit(c.ConstantCondition(not isinstance(node, c.AnyOf)))
            op = " && " if isinstance(node, c.AllOf) else " || "
            value = "(" + op.join(visit(child) for child in node.children) + ")"
            return f"!{value}" if isinstance(node, c.NoneOf) else value
        if isinstance(node, c.ExactlyOne):
            if not node.children:
                return visit(c.ConstantCondition(False))
            terms = []
            for i in range(len(node.children)):
                terms.append(
                    "("
                    + " && ".join(
                        ("!" if j != i else "") + "(" + visit(other) + ")"
                        for j, other in enumerate(node.children)
                    )
                    + ")"
                )
            return "(" + " || ".join(terms) + ")"
        raise CppGenerationError(f"Unresolved/unsupported native condition: {node}")

    return visit(condition)
