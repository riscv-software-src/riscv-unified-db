# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Compile symbolic IDL constraints into the ordinary UDB condition language.

The caller supplies the IDL environment explicitly. Parameter references and
extension predicates remain symbolic even when that environment knows their
current values; only compile-time operands and local loop execution are evaluated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from .conditions import (
    FALSE,
    TRUE,
    AllOf,
    AnyOf,
    Condition,
    ConditionError,
    ExactlyOne,
    ExtensionTerm,
    Implies,
    NoneOf,
    Not,
    ParameterOperator,
    ParameterTerm,
    UnresolvedIdlCondition,
    XlenTerm,
    all_of,
    any_of,
    implies,
    negate,
)
from .idl import IdlSource, ast, parse_constraint_body
from .idl.errors import IdlValueUnknown
from .idl.symbols import SymbolTable, Var
from .idl.types import FunctionType
from .versions import parse_version_requirements

__all__ = ["compile_idl_condition", "resolve_idl_conditions"]

_OPERATORS = {
    "==": ParameterOperator.EQUAL,
    "!=": ParameterOperator.NOT_EQUAL,
    "<": ParameterOperator.LESS_THAN,
    "<=": ParameterOperator.LESS_THAN_OR_EQUAL,
    ">": ParameterOperator.GREATER_THAN,
    ">=": ParameterOperator.GREATER_THAN_OR_EQUAL,
}
_REVERSED = {"==": "==", "!=": "!=", "<": ">", "<=": ">=", ">": "<", ">=": "<="}


def compile_idl_condition(
    text: str,
    symtab: SymbolTable,
    *,
    source: IdlSource | str | None = None,
    max_loop_iterations: int = 1024,
) -> Condition:
    """Parse, type-check, and translate a ``constraint_body`` without caller mutation.

    ``max_loop_iterations`` bounds each statically expanded loop. Unknown operands,
    unsupported expressions, and unbounded loops raise source-aware IDL errors.
    Loop controls must be parameter-independent, including reads through helpers;
    configured parameter values are not compile-time loop constants.
    """

    if not isinstance(symtab, SymbolTable):
        raise TypeError("IDL condition compilation requires an explicit SymbolTable")
    if type(max_loop_iterations) is not int or max_loop_iterations < 1:
        raise ValueError("max_loop_iterations must be a positive integer")
    if not isinstance(source, IdlSource):
        source = IdlSource(text, label=source or "<idl-condition>")
    root = parse_constraint_body(text, source=source)
    checking = symtab.deep_clone(clone_values=True)
    checking.push(root)
    root.type_check(checking)
    working = symtab.deep_clone(clone_values=True)
    working.push(root)
    return _Translator(working, max_loop_iterations).translate(root)


def resolve_idl_conditions(
    condition: Condition,
    symtab: SymbolTable,
    *,
    source_for: Callable[[UnresolvedIdlCondition], IdlSource | str | None] | None = None,
) -> Condition:
    """Replace IDL leaves in a condition tree while retaining logical structure and metadata."""

    if isinstance(condition, UnresolvedIdlCondition):
        source = condition.source if source_for is None else source_for(condition)
        result = compile_idl_condition(condition.text, symtab, source=source)
        return replace(result, reason=condition.reason, source=condition.source)
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
        return replace(
            condition,
            children=tuple(
                resolve_idl_conditions(child, symtab, source_for=source_for)
                for child in condition.children
            ),
        )
    if isinstance(condition, Not):
        return replace(
            condition,
            child=resolve_idl_conditions(condition.child, symtab, source_for=source_for),
        )
    if isinstance(condition, Implies):
        return replace(
            condition,
            antecedent=resolve_idl_conditions(condition.antecedent, symtab, source_for=source_for),
            consequent=resolve_idl_conditions(condition.consequent, symtab, source_for=source_for),
        )
    return condition


@dataclass(slots=True)
class _Translator:
    symtab: SymbolTable
    max_loop_iterations: int

    def translate(self, node: ast.Node) -> Condition:
        if isinstance(node, ast.ConstraintBody):
            return all_of(*(self.translate(stmt) for stmt in node.stmts))
        if isinstance(node, (ast.ImplicationStatement, ast.ParenExpression)):
            return self.translate(node.expression)
        if isinstance(node, ast.ImplicationExpression):
            return implies(self.translate(node.antecedent), self.translate(node.consequent))
        if isinstance(node, ast.ForLoop):
            return self._loop(node)
        if isinstance(node, ast.TrueExpression):
            return TRUE
        if isinstance(node, ast.FalseExpression):
            return FALSE
        selector = self._selector(node)
        if selector is not None:
            return ParameterTerm(selector.pop("name"), ParameterOperator.EQUAL, True, **selector)
        if isinstance(node, ast.UnaryOperatorExpression):
            if node.op == "!":
                return negate(self.translate(node.expression))
            node.type_error(f"unsupported unary operator in an IDL condition: {node.op}")
        if isinstance(node, ast.BinaryExpression):
            if node.op == "&&":
                return all_of(self.translate(node.lhs), self.translate(node.rhs))
            if node.op == "||":
                return any_of(self.translate(node.lhs), self.translate(node.rhs))
            if node.op in _OPERATORS:
                return self._comparison(node)
            node.type_error(f"unsupported operator in an IDL condition: {node.op}")
        if isinstance(node, ast.ArrayIncludes):
            parameter = self._parameter(node.array)
            if parameter is None:
                node.array.type_error("$array_includes? requires a parameter reference")
            return ParameterTerm(
                parameter.name,
                ParameterOperator.INCLUDES,
                self._known(node.expression, "array membership value"),
            )
        if isinstance(node, ast.FunctionCallExpression):
            return self._call(node)
        if isinstance(node, (ast.ReturnStatement, ast.ConditionalReturnStatement)):
            node.type_error("returns are not allowed in IDL constraints")
        if not self._symbolic(node):
            value = self._known(node, "Boolean expression")
            if type(value) is bool:
                return TRUE if value else FALSE
        node.type_error(f"unsupported expression in an IDL condition: {type(node).__name__}")

    @staticmethod
    def _unparen(node: ast.Node) -> ast.Node:
        while isinstance(node, ast.ParenExpression):
            node = node.expression
        return node

    def _parameter(self, node: ast.Node) -> Var | None:
        node = self._unparen(node)
        if isinstance(node, ast.Id):
            var = self.symtab.get(node.name)
            if isinstance(var, Var) and var.param:
                return var
        return None

    def _selector(self, node: ast.Node) -> dict[str, Any] | None:
        node = self._unparen(node)
        var = self._parameter(node)
        if var is not None:
            return {"name": var.name}
        if isinstance(node, (ast.AryElementAccess, ast.AryRangeAccess)):
            var = self._parameter(node.var)
            if var is None:
                return None
            if isinstance(node, ast.AryElementAccess):
                index = self._integer(node.index, "array index")
                if index < 0:
                    node.index.type_error("array index must be nonnegative")
                return {"name": var.name, "index": index}
            msb = self._integer(node.msb, "range upper endpoint")
            lsb = self._integer(node.lsb, "range lower endpoint")
            if not 0 <= lsb <= msb:
                node.type_error("parameter range must have nonnegative descending endpoints")
            return {"name": var.name, "bit_range": (msb, lsb)}
        if isinstance(node, ast.ArraySize):
            var = self._parameter(node.array)
            if var is not None:
                return {"name": var.name, "size": True}
        return None

    def _comparison(self, node: ast.BinaryExpression) -> Condition:
        lhs, rhs = self._unparen(node.lhs), self._unparen(node.rhs)
        for operand, value_node in ((lhs, rhs), (rhs, lhs)):
            if isinstance(operand, ast.FunctionCallExpression) and operand.name == "xlen":
                if operand.args or node.op not in ("==", "!="):
                    node.type_error("xlen() conditions support only equality and inequality")
                value = self._integer(value_node, "XLEN comparison value")
                if value not in (32, 64):
                    value_node.type_error("XLEN comparison value must be 32 or 64")
                result = XlenTerm(value)
                return result if node.op == "==" else negate(result)
        selector = self._selector(lhs)
        op = node.op
        value_node = rhs
        if selector is None:
            selector = self._selector(rhs)
            op = _REVERSED[op]
            value_node = lhs
        if selector is not None:
            value = self._known(value_node, "comparison value")
            try:
                return ParameterTerm(selector.pop("name"), _OPERATORS[op], value, **selector)
            except ConditionError as error:
                node.type_error(str(error))
        if not self._symbolic(node):
            value = self._known(node, "comparison")
            if type(value) is bool:
                return TRUE if value else FALSE
        node.type_error("comparison must select a parameter and a compile-time value")

    def _call(self, node: ast.FunctionCallExpression) -> Condition:
        counts = {"implemented?": 1, "implemented_version?": 2}
        if node.name not in counts:
            node.type_error(f"unsupported function in an IDL condition: {node.name}")
        if len(node.args) != counts[node.name]:
            node.type_error(f"{node.name} expects {counts[node.name]} arguments")
        extension = self._unparen(node.args[0])
        if not isinstance(extension, ast.EnumRef) or extension.class_name != "ExtensionName":
            node.args[0].type_error(f"{node.name} requires an ExtensionName enum member")
        requirements = None
        if node.name == "implemented_version?":
            requirement = self._known(node.args[1], "extension version requirement")
            if not isinstance(requirement, str):
                node.args[1].type_error("extension version requirement must be a string")
            try:
                requirements = parse_version_requirements(requirement)
            except ValueError as error:
                node.args[1].type_error(str(error))
        return ExtensionTerm(
            extension.member_name,
            requirements if requirements is not None else parse_version_requirements(None),
        )

    @staticmethod
    def _declared_ids(node: ast.Node) -> tuple[ast.Id, ...]:
        if isinstance(node, ast.Statement):
            node = node.action
        if isinstance(node, ast.VariableDeclarationWithInitialization):
            return (node.lhs,)
        if isinstance(node, ast.VariableDeclaration):
            return (node.id,)
        if isinstance(node, ast.MultiVariableDeclaration):
            return node.var_names
        return ()

    def _symbolic(
        self,
        node: ast.Node,
        *,
        shadowed: frozenset[str] = frozenset(),
        global_scope: bool = False,
        active_calls: frozenset[str] = frozenset(),
    ) -> bool:
        if isinstance(node, ast.Id):
            if node.name in shadowed:
                return False
            variable = (
                self.symtab.get_global(node.name) if global_scope else self.symtab.get(node.name)
            )
            return isinstance(variable, Var) and variable.param
        if isinstance(node, ast.FunctionCallExpression):
            if node.name in ("implemented?", "implemented_version?", "implemented_csr?", "xlen"):
                return True
            if any(
                self._symbolic(
                    argument,
                    shadowed=shadowed,
                    global_scope=global_scope,
                    active_calls=active_calls,
                )
                for argument in node.args
            ):
                return True
            function = self.symtab.get_global(node.name)
            if not isinstance(function, FunctionType):
                node.type_error("compile-time call requires a function binding")
            definition = function.func_def_ast
            if not isinstance(definition, ast.FunctionDef) or definition.body is None:
                return True
            if node.name in active_calls:
                return False
            arguments = frozenset(
                identifier.name
                for argument in definition.arguments
                for identifier in self._declared_ids(argument)
            )
            return any(
                self._symbolic(
                    expression,
                    shadowed=arguments,
                    global_scope=True,
                    active_calls=active_calls | {node.name},
                )
                for expression in (*definition.return_types, *definition.arguments, definition.body)
            )
        declaration = node.action if isinstance(node, ast.Statement) else node
        declared = self._declared_ids(declaration)
        local = shadowed
        for child in declaration.children:
            if any(child is identifier for identifier in declared):
                continue
            if self._symbolic(
                child, shadowed=local, global_scope=global_scope, active_calls=active_calls
            ):
                return True
            local = local | {identifier.name for identifier in self._declared_ids(child)}
        return False

    def _known(self, node: ast.Node, purpose: str) -> Any:
        self._reject_symbolic(node, purpose)
        try:
            value = node.value(self.symtab)
        except IdlValueUnknown as error:
            node.type_error(f"{purpose} must be compile-time evaluatable: {error.reason}")
        if not self._known_value(value):
            node.type_error(f"{purpose} contains an unknown or unsupported compile-time value")
        return value

    def _reject_symbolic(self, node: ast.Node, purpose: str) -> None:
        if self._symbolic(node):
            node.type_error(f"{purpose} must be compile-time evaluatable, not symbolic")

    @staticmethod
    def _known_value(value: Any) -> bool:
        if type(value) in (bool, int, str):
            return True
        if isinstance(value, (list, tuple)):
            return all(_Translator._known_value(item) for item in value)
        return False

    def _integer(self, node: ast.Node, purpose: str) -> int:
        value = self._known(node, purpose)
        if type(value) is not int:
            node.type_error(f"{purpose} must be an integer")
        return value

    def _loop(self, node: ast.ForLoop) -> Condition:
        self.symtab.push(node)
        try:
            self._reject_symbolic(node.init, "loop initialization")
            node.init.execute(self.symtab)
            self._reject_symbolic(node.update, "loop update")
            conditions: list[Condition] = []
            states: set[str] = set()
            iteration = 0
            while self._loop_condition(node.condition):
                state = repr([(var.name, value) for var, value in self.symtab.snapshot_values()])
                if state in states:
                    node.type_error("constraint loop repeats a state without terminating")
                states.add(state)
                if iteration >= self.max_loop_iterations:
                    node.type_error(
                        f"constraint loop exceeds max_loop_iterations={self.max_loop_iterations}"
                    )
                iteration += 1
                for stmt in node.stmts:
                    if isinstance(stmt, (ast.ImplicationStatement, ast.ForLoop)):
                        conditions.append(self.translate(stmt))
                    else:
                        self._reject_returns(stmt)
                        self._reject_symbolic(stmt, "loop statement")
                        try:
                            stmt.execute(self.symtab)
                        except IdlValueUnknown as error:
                            stmt.type_error(
                                f"constraint loop statement is not compile-time evaluatable: "
                                f"{error.reason}"
                            )
                node.update.execute(self.symtab)
            return all_of(*conditions)
        except IdlValueUnknown as error:
            node.type_error(f"constraint loop is not compile-time evaluatable: {error.reason}")
        finally:
            self.symtab.pop()

    def _loop_condition(self, node: ast.Node) -> bool:
        value = self._known(node, "loop condition")
        if type(value) is not bool:
            node.type_error("constraint loop condition must be Boolean")
        return value

    def _reject_returns(self, node: ast.Node) -> None:
        if isinstance(node, (ast.ReturnStatement, ast.ConditionalReturnStatement)):
            node.type_error("returns are not allowed in IDL constraints")
        for child in node.children:
            self._reject_returns(child)
