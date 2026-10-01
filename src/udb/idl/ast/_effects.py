# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Conservative write invalidation without executing uncertain paths."""

from __future__ import annotations

from collections.abc import Iterable

from ..symbols import SymbolTable, Var
from ..types import FunctionType, TypeKind
from ._assignments import (
    AryElementAssignment,
    AryRangeAssignment,
    FieldAssignment,
    MultiVariableAssignment,
    VariableAssignment,
)
from ._base import Node, extract_base_var_name
from ._declarations import (
    MultiVariableDeclaration,
    VariableDeclaration,
    VariableDeclarationWithInitialization,
)

_PURE_GENERATED = frozenset({"implemented?", "implemented_version?", "implemented_csr?", "xlen"})
_ALIASED_TYPES = frozenset({TypeKind.ARRAY, TypeKind.STRUCT})


def _declaration(node: Node) -> Node:
    return node.children[0] if node.kind == "stmt" and node.children else node


def _declared_names(node: Node) -> tuple[str, ...]:
    if isinstance(node, VariableDeclaration):
        return (node.id.name,)
    if isinstance(node, VariableDeclarationWithInitialization):
        return (node.id,)
    if isinstance(node, MultiVariableDeclaration):
        return tuple(name.name for name in node.var_names)
    node.internal_error(f"Unsupported scoped declaration: {node.kind}")


def _declaration_expressions(node: Node) -> tuple[Node, ...]:
    expressions = (node.type_name,)
    if isinstance(node, VariableDeclarationWithInitialization):
        expressions += (node.rhs,)
    if (
        isinstance(node, (VariableDeclaration, VariableDeclarationWithInitialization))
        and node.ary_size is not None
    ):
        expressions += (node.ary_size,)
    return expressions


def invalidate_expressions(nodes: Iterable[Node], symtab: SymbolTable) -> None:
    for node in nodes:
        declaration = _declaration(node)
        if declaration.is_declaration:
            invalidate_expressions(_declaration_expressions(declaration), symtab)
            dtype = declaration.type(symtab)
            for name in _declared_names(declaration):
                symtab.add(name, Var(name, dtype))
            continue
        if node.kind in ("stmt", "conditional_stmt"):
            invalidate_expressions(node.children, symtab)
            continue
        if node.is_executable:
            node.nullify_assignments(symtab)
            if node.kind in ("if_stmt", "if_body", "for_loop", "funcall_expr"):
                continue
        invalidate_expressions(node.children, symtab)


def invalidate_statements(nodes: Iterable[Node], symtab: SymbolTable, owner: Node) -> None:
    symtab.push(owner)
    try:
        invalidate_expressions(nodes, symtab)
    finally:
        symtab.pop()


def _global_binding(symtab: SymbolTable, name: str) -> object | None:
    return symtab.get(name) if symtab.at_global_scope else symtab.get_global(name)


def _invalidate_variable(variable: object) -> None:
    if (
        isinstance(variable, Var)
        and not variable.type.is_const
        and not variable.type.is_global
        and not variable.param
    ):
        variable.value = None


def _targets(node: Node) -> tuple[Node, ...]:
    if isinstance(node, (VariableAssignment, AryElementAssignment, AryRangeAssignment)):
        return (node.lhs,)
    if isinstance(node, FieldAssignment):
        return (node.id,)
    if isinstance(node, MultiVariableAssignment):
        return tuple(var for var in node.variables if var.kind != "dont_care_lval")
    if node.kind in ("post_increment_expr", "post_decrement_expr"):
        return (node.rval,)
    return ()


def _scan_globals(
    nodes: Iterable[Node],
    shadowed: set[str],
    targets: dict[str, None],
    ids: dict[str, None],
    calls: list[Node],
) -> None:
    local = set(shadowed)
    for node in nodes:
        declaration = _declaration(node)
        if declaration.is_declaration:
            _scan_globals(_declaration_expressions(declaration), local, targets, ids, calls)
            local.update(_declared_names(declaration))
            continue
        if node.kind == "for_loop":
            _scan_globals(
                (node.init, node.condition, *node.stmts, node.update),
                local,
                targets,
                ids,
                calls,
            )
            continue
        for target in _targets(node):
            name = extract_base_var_name(target)
            if name is not None and name not in local:
                targets[name] = None
        if node.kind == "id" and node.name not in local:
            ids[node.name] = None
        if node.kind == "funcall_expr":
            calls.append(node)
        _scan_globals(node.children, local, targets, ids, calls)


def _body_effects(definition: Node) -> tuple[tuple[str, ...], tuple[str, ...], tuple[Node, ...]]:
    """Global names a body may write or alias, and the calls it makes.

    The summary is purely syntactic, so it is computed once per definition;
    bindings are resolved against the caller's table on every use.
    """
    cached = definition._cache.get("global_effects")
    if cached is None:
        targets: dict[str, None] = {}
        ids: dict[str, None] = {}
        calls: list[Node] = []
        _scan_globals(
            definition.body.stmts,
            {argument.id.name for argument in definition.argument_nodes},
            targets,
            ids,
            calls,
        )
        cached = (tuple(targets), tuple(ids), tuple(calls))
        definition._cache["global_effects"] = cached
    return cached


def _mutable_global(variable: object) -> bool:
    return (
        isinstance(variable, Var)
        and not variable.type.is_const
        and not variable.type.is_global
        and not variable.param
    )


def invalidate_call(call: Node, symtab: SymbolTable) -> None:
    invalidate_expressions(call.children, symtab)
    for argument in call.children:
        pending_arguments = [argument]
        while pending_arguments:
            expression = pending_arguments.pop()
            if expression.kind == "id":
                variable = symtab.get(expression.name)
                if isinstance(variable, Var) and variable.type.kind in _ALIASED_TYPES:
                    _invalidate_variable(variable)
            pending_arguments.extend(expression.children)

    pending = [call]
    visited: set[str] = set()
    opaque = False
    while pending:
        current = pending.pop()
        if current.name in visited:
            continue
        visited.add(current.name)
        function = _global_binding(symtab, current.name)
        if not isinstance(function, FunctionType):
            current.type_error(f"{current.name} is not a global function")
        if function.is_generated and current.name in _PURE_GENERATED:
            continue
        if function.is_builtin or function.is_external or function.is_generated:
            if not opaque:
                opaque = True
                for name in symtab.global_names_where(_mutable_global):
                    if name not in ("true", "false"):
                        _invalidate_variable(_global_binding(symtab, name))
            continue
        definition = function.func_def_ast
        if definition.body is None:
            current.internal_error(f"Function {current.name} has no body")
        targets, ids, calls = _body_effects(definition)
        for name in targets:
            _invalidate_variable(_global_binding(symtab, name))
        for name in ids:
            variable = _global_binding(symtab, name)
            if isinstance(variable, Var) and variable.type.kind in _ALIASED_TYPES:
                # Global aggregates can escape through local aliases or returns.
                _invalidate_variable(variable)
        pending.extend(calls)
