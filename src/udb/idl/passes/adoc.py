# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone IDL source and implementation-option AsciiDoc rendering."""

from __future__ import annotations

from .. import ast


def _link(kind: str, target: str, label: str) -> str:
    return f"%%UDB_DOC_LINK%{kind};{target};{label}%%"


def to_adoc(node: ast.Node, *, indent: int = 0, indent_spaces: int = 2) -> str:
    """Render the IDL documentation markup used by existing generators."""

    pad = " " * indent

    def render(child: ast.Node, level: int = 0) -> str:
        return to_adoc(child, indent=level, indent_spaces=indent_spaces)

    def joined(children: tuple[ast.Node, ...]) -> str:
        return ", ".join(render(child) for child in children)

    if isinstance(node, ast.Noop):
        return ""
    if isinstance(node, ast.BuiltinVariable):
        return node.name
    if isinstance(node, ast.FunctionBody):
        return "\n".join(pad + render(child) for child in node.stmts)
    if isinstance(node, (ast.IfBody, ast.ConstraintBody)):
        return "\n".join(render(child, indent) for child in node.children)
    if isinstance(node, ast.If):
        lines = [pad + f"if pass:[(]{render(node.if_cond)}) {{"]
        lines.extend(render(child, indent + indent_spaces) for child in node.if_body.stmts)
        for branch in node.elseifs:
            lines.append(pad + f"}} else if pass:[(]{render(branch.condition)}) {{")
            lines.extend(render(child, indent + indent_spaces) for child in branch.body.stmts)
        if node.final_else_body.stmts:
            lines.append(pad + "} else {")
            lines.extend(
                render(child, indent + indent_spaces) for child in node.final_else_body.stmts
            )
        return "\n".join((*lines, pad + "}"))
    if isinstance(node, ast.ForLoop):
        lines = [
            pad
            + f"for pass:[(]{render(node.init)}; {render(node.condition)}; "
            + f"{render(node.update)}) {{"
        ]
        lines.extend(render(child, indent + indent_spaces) for child in node.stmts)
        return "\n".join((*lines, pad + "}"))
    if isinstance(node, ast.ReturnStatement):
        return pad + render(node.return_expression) + ";"
    if isinstance(node, ast.ConditionalReturnStatement):
        return pad + render(node.return_expression, indent) + f" if ({render(node.condition)});"
    if isinstance(node, ast.ConditionalStatement):
        return pad + render(node.action) + f" if ({render(node.condition)});"
    if isinstance(node, ast.Statement):
        return pad + render(node.action) + ";"
    if isinstance(node, ast.ReturnExpression):
        return pad + "return " + joined(node.return_value_nodes)
    if isinstance(node, ast.BinaryExpression):
        op = node.op.replace("+", "pass:[+]", 1).replace("`", "pass:[`]", 1)
        return pad + f"{render(node.lhs)} {op} {render(node.rhs)}"
    if isinstance(node, ast.UnaryOperatorExpression):
        return pad + node.op + render(node.expression)
    if isinstance(node, ast.ParenExpression):
        return pad + f"({render(node.expression, indent)})"
    if isinstance(node, ast.TernaryOperatorExpression):
        return pad + (
            f"{render(node.condition)} ? {render(node.true_expression)} : "
            f"{render(node.false_expression)}"
        )
    if isinstance(node, ast.ArrayLiteral):
        return pad + f"[{joined(node.children)}]"
    if isinstance(node, ast.ConcatenationExpression):
        return pad + "{" + joined(node.children) + "}"
    if isinstance(node, ast.ReplicationExpression):
        return pad + "{" + render(node.n) + "{" + render(node.v, indent) + "}}"
    if isinstance(node, ast.AryElementAccess):
        return pad + f"{render(node.var, indent)}[{render(node.index)}]"
    if isinstance(node, ast.AryRangeAccess):
        return pad + f"{render(node.var, indent)}[{render(node.msb)}:{render(node.lsb)}]"
    if isinstance(node, ast.FunctionCallExpression):
        link = _link("func", node.name, node.name)
        return pad + link + f"pass:[(]{joined(node.args)})"
    if isinstance(node, (ast.PostIncrementExpression, ast.PostDecrementExpression)):
        op = "++" if isinstance(node, ast.PostIncrementExpression) else "--"
        return pad + render(node.rval, indent) + op
    if isinstance(node, ast.CsrFieldReadExpression):
        name = node.csr.csr_name
        return pad + (
            f"CSR[{_link('csr', name, name)}]."
            + _link("csr_field", name + "*" + node.field_name, node.field_name)
        )
    if isinstance(node, ast.CsrReadExpression):
        return pad + f"CSR[{_link('csr', node.csr_name, node.text or node.to_idl())}]"
    if isinstance(node, ast.CsrWrite):
        return pad + f"CSR[{render(node.idx)}]"
    if isinstance(node, ast.CsrFunctionCall):
        return pad + f"{render(node.csr, indent)}.{node.function_name}({joined(node.args)})"
    if isinstance(node, ast.CsrSoftwareWrite):
        return pad + f"{render(node.csr, indent)}.sw_write({render(node.expression)})"
    if isinstance(node, ast.CsrFieldAssignment):
        return pad + f"{render(node.csr_field, indent)} = {render(node.write_value)}"
    if isinstance(node, ast.FieldAccessExpression):
        return pad + f"{render(node.obj, indent)}.{node.field_name}"
    if isinstance(node, ast.FieldAssignment):
        return f"{render(node.id)}.{node.field_name} = {render(node.rhs)}"
    if isinstance(node, ast.VariableAssignment):
        return pad + f"{render(node.lhs)} = {render(node.rhs)}"
    if isinstance(node, ast.PcAssignment):
        return pad + f"$pc = {render(node.rhs)}"
    if isinstance(node, ast.AryElementAssignment):
        return pad + f"{render(node.lhs)}[{render(node.index)}] = {render(node.rhs)}"
    if isinstance(node, ast.AryRangeAssignment):
        return pad + (
            f"{render(node.variable, indent)}[{render(node.msb)}:{render(node.lsb)}]"
            + f" = {render(node.write_value)}"
        )
    if isinstance(node, ast.MultiVariableAssignment):
        call = render(node.function_call)
        if not node.function_call.args:
            call = call.removesuffix("pass:[(])") + "pass:[()]"
        return pad + f"({joined(node.variables)}) = {call}"
    if isinstance(node, ast.VariableDeclaration):
        return pad + f"{render(node.type_name)} {render(node.id)}"
    if isinstance(node, ast.MultiVariableDeclaration):
        return pad + f"{render(node.type_name)} {joined(node.var_names)}"
    if isinstance(node, ast.VariableDeclarationWithInitialization):
        size = f"[{render(node.ary_size)}]" if node.ary_size is not None else ""
        return pad + (f"{render(node.type_name)} {render(node.lhs)}{size} = {render(node.rhs)}")
    if isinstance(node, ast.BuiltinTypeName):
        return (
            pad + f"Bits<{render(node.bits_expression)}>"
            if node.type_name == "Bits"
            else node.to_idl()
        )
    if isinstance(node, ast.SignCast):
        return pad + f"$signed+++(+++{render(node.expression)})"
    if isinstance(node, ast.BitsCast):
        return pad + f"$bits({render(node.expression)})"
    if isinstance(node, ast.ArraySize):
        return pad + f"$array_size({render(node.array)})"
    if isinstance(node, ast.ArrayIncludes):
        return pad + f"$array_includes?({render(node.array)}, {render(node.expression)})"
    if isinstance(node, ast.EnumCast):
        return pad + f"$enum({render(node.children[0])}, {render(node.expression)})"
    if isinstance(node, (ast.EnumSize, ast.EnumElementSize, ast.EnumArrayCast)):
        name = {
            ast.EnumSize: "$enum_size",
            ast.EnumElementSize: "$enum_element_size",
            ast.EnumArrayCast: "$enum_to_a",
        }[type(node)]
        return pad + f"{name}({render(node.children[0])})"
    return pad + node.to_idl()


_INVERTED_OPS = {"==": "!=", "!=": "==", "<": ">=", ">": "<=", "<=": ">", ">=": "<"}


def _inverted(node: ast.Node, *, adoc: bool) -> str:
    render = to_adoc if adoc else lambda n: n.to_idl()
    if isinstance(node, ast.ParenExpression):
        return _inverted(node.expression, adoc=adoc)
    if isinstance(node, ast.BinaryExpression) and node.op in _INVERTED_OPS:
        value = f"{render(node.lhs)} {_INVERTED_OPS[node.op]} {render(node.rhs)}"
        return value if adoc else f"({value})"
    if isinstance(node, ast.UnaryOperatorExpression) and node.op == "!":
        return render(node.expression)
    if isinstance(node, ast.BinaryExpression):
        return f"!({render(node)})"
    if isinstance(node, ast.UnaryOperatorExpression):
        return "!" + render(node)
    return f"!({render(node)})"


def to_option_adoc(node: ast.Node) -> str:
    """Render the implementation-option markup consumed by documents."""

    if isinstance(node, (ast.FunctionBody, ast.IfBody)):
        return "\n".join(to_option_adoc(child) for child in node.children)
    if isinstance(node, ast.If):
        result = f'[when,"{node.if_cond.to_idl()}"]\n{to_option_adoc(node.if_body)}\n'
        for branch in node.elseifs:
            result += f'[when,"{branch.condition.to_idl()}"]\n{to_option_adoc(branch.body)}\n'
        if node.final_else_body.stmts:
            condition = "else" if node.elseifs else _inverted(node.if_cond, adoc=False)
            result += f'[when,"{condition}"]\n{to_option_adoc(node.final_else_body)}\n'
        return result
    if isinstance(node, ast.ReturnStatement):
        return to_option_adoc(node.return_expression)
    if isinstance(node, ast.Statement):
        return to_option_adoc(node.action)
    if isinstance(node, ast.ReturnExpression):
        return ", ".join(to_option_adoc(child) for child in node.return_value_nodes)
    if isinstance(node, ast.TernaryOperatorExpression):
        condition = node.condition
        while isinstance(condition, ast.ParenExpression):
            condition = condition.expression
        positive = to_adoc(condition).replace('"', "&quot;")
        negative = _inverted(condition, adoc=True).replace('"', "&quot;")
        return (
            f'[when,"{positive}"]\n{to_option_adoc(node.true_expression)}\n\n'
            f'[when,"{negative}"]\n{to_option_adoc(node.false_expression)}\n\n'
        )
    if isinstance(node, ast.IntLiteral):
        value = node.value(None)
        return {
            1 << 65: "UNDEFINED_LEGAL",
            1 << 66: "UNDEFINED_LEGAL_DETERMINISTIC",
        }.get(value, node.to_idl())
    if isinstance(node, ast.EnumRef) and node.class_name == "CsrFieldType":
        return {
            "ROH": "RO-H",
            "RWR": "RW-R",
            "RWH": "RW-H",
            "RWRH": "RW-RH",
        }.get(node.member_name, node.member_name)
    if isinstance(node, (ast.ConditionalReturnStatement, ast.ConditionalStatement)):
        action = (
            node.return_expression
            if isinstance(node, ast.ConditionalReturnStatement)
            else node.action
        )
        return f'[when,"{node.condition.to_idl()}"]\n{to_option_adoc(action)}\n'
    return to_adoc(node)
