# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Standalone C++ hart analyses, without generator monkey patches."""

from __future__ import annotations

from .. import ast
from ..symbols import SymbolTable, Var
from ..types import Type
from .reachability import function_definition


def constexpr(node: ast.Node, symtab: SymbolTable) -> bool:
    """Conservatively decide whether a subtree can be a C++ constant expression."""

    if isinstance(node, ast.Id):
        binding = symtab.get(node.name)
        if binding is None or isinstance(binding, Type):
            return True
        if not isinstance(binding, Var) or binding.value is None:
            return False
        if binding.param:
            parameter = symtab.param(node.name)
            return parameter is not None and parameter.value_known
        return not binding.type.is_global
    if isinstance(
        node,
        (
            ast.PcAssignment,
            ast.FunctionCallExpression,
            ast.CsrFieldReadExpression,
            ast.CsrReadExpression,
            ast.CsrSoftwareWrite,
            ast.CsrWrite,
        ),
    ):
        return False
    if isinstance(node, ast.CsrFunctionCall):
        return node.function_name == "address"
    if isinstance(node, ast.FunctionDef):
        return (
            not node.builtin
            and not node.generated
            and node.body is not None
            and constexpr(node.body, symtab)
        )
    return all(constexpr(child, symtab) for child in node.children)


def control_flow(node: ast.Node, symtab: SymbolTable) -> bool:
    """Find explicit PC writes, including callees, but excluding exception raises."""

    active: set[int] = set()

    def visit(current: ast.Node) -> bool:
        if isinstance(current, ast.PcAssignment):
            return True
        if any(visit(child) for child in current.children):
            return True
        if isinstance(current, ast.FunctionCallExpression):
            if current.name.startswith("raise"):
                return False
            function = function_definition(current, symtab)
            if function.builtin or function.generated or function.body is None:
                return False
            identity = id(function)
            if identity in active:
                return False
            active.add(identity)
            try:
                return visit(function.body)
            finally:
                active.remove(identity)
        return False

    return visit(node)


def written(
    node: ast.Node, symtab: SymbolTable, varname: str, *, in_assignment: bool = False
) -> bool:
    """Whether a named location is assigned anywhere in the subtree.

    Index and range expressions are reads, not destination locations. Increment
    and decrement are writes even when embedded in a larger expression.
    """

    def location(current: ast.Node) -> bool:
        while isinstance(current, (ast.AryElementAccess, ast.AryRangeAccess)):
            current = current.var
        if isinstance(current, ast.FieldAccessExpression):
            return location(current.obj)
        return isinstance(current, ast.Id) and current.name == varname

    def visit(current: ast.Node, assignment: bool = False) -> bool:
        if isinstance(current, ast.Id):
            return assignment and current.name == varname
        if assignment and isinstance(current, (ast.AryElementAccess, ast.AryRangeAccess)):
            return location(current.var) or any(visit(child) for child in current.children[1:])
        if isinstance(
            current,
            (
                ast.VariableAssignment,
                ast.AryElementAssignment,
                ast.AryRangeAssignment,
                ast.FieldAssignment,
            ),
        ):
            return location(current.children[0]) or any(visit(child) for child in current.children)
        if isinstance(current, ast.MultiVariableAssignment):
            return any(location(child) for child in current.variables) or visit(
                current.function_call
            )
        if isinstance(current, (ast.PostIncrementExpression, ast.PostDecrementExpression)):
            return location(current.rval) or any(visit(child) for child in current.children)
        if isinstance(current, ast.PcAssignment) and varname == "$pc":
            return True
        return any(visit(child, assignment) for child in current.children)

    return visit(node, in_assignment)
