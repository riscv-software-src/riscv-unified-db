# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Argument-specialized call graphs with complete, cycle-safe cached closures."""

from __future__ import annotations

from collections.abc import Hashable, MutableMapping
from dataclasses import dataclass, field
from typing import Any

from .. import ast
from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ._tree import clone, isolated_symtab

_UNKNOWN = object()


def _value(node: ast.Node, symtab: SymbolTable) -> Any:
    try:
        value = clone(node).value(symtab)
        return _UNKNOWN if isinstance(value, ast.UnknownLiteral) else value
    except IdlValueUnknown:
        return _UNKNOWN


def _hashable(value: Any) -> Hashable:
    if value is _UNKNOWN:
        return ("unknown",)
    if isinstance(value, (tuple, list)):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable(item)) for key, item in value.items()))
    return (type(value).__name__, value)


def function_definition(call: ast.FunctionCallExpression, symtab: SymbolTable) -> ast.FunctionDef:
    binding = symtab.get(call.name)
    definition = getattr(binding, "func_def_ast", binding)
    if not isinstance(definition, ast.FunctionDef):
        call.type_error(f"No function named {call.name}")
    return definition


def _arguments(
    call: ast.FunctionCallExpression, definition: ast.FunctionDef, symtab: SymbolTable
) -> tuple[SymbolTable, tuple[Hashable, ...]]:
    body_symtab = symtab.global_clone()
    body_symtab.push(definition)
    values: list[Hashable] = []
    if len(call.args) != len(definition.arguments):
        call.type_error(f"Wrong number of arguments for {call.name}")
    for argument, (argument_type, argument_name) in zip(
        call.args, definition.semantic_arguments(body_symtab), strict=True
    ):
        value = _value(argument, symtab)
        values.append(_hashable(value))
        body_symtab.add(
            argument_name,
            Var(
                argument_name,
                argument_type,
                None if value is _UNKNOWN else value,
            ),
        )
    return body_symtab, tuple(values)


def _execute(node: ast.Node, symtab: SymbolTable) -> None:
    """Use statement semantics supplied by the compiler, never global state."""

    if node.is_declaration:
        node.add_symbol(symtab)
    # A discarded call result cannot change caller-owned bindings. Its callees
    # are already queued; evaluating the call would recurse through cycles again.
    if isinstance(node, ast.FunctionCallExpression):
        return
    if node.is_executable:
        try:
            node.execute(symtab)
        except IdlValueUnknown:
            pass


@dataclass
class _Vertex:
    functions: dict[str, ast.FunctionDef] = field(default_factory=dict)
    mask: int = 0
    edges: set[Hashable] = field(default_factory=set)

    def merge(self, other: _Vertex) -> bool:
        old = (len(self.functions), self.mask)
        self.functions.update(other.functions)
        self.mask |= other.mask
        return old != (len(self.functions), self.mask)


class _Graph:
    def __init__(self, cache: MutableMapping, *, exceptions: bool) -> None:
        self.cache = cache
        self.exceptions = exceptions
        self.vertices: dict[Hashable, _Vertex] = {}
        self.pending: list[tuple[ast.FunctionBody, SymbolTable, _Vertex]] = []

    def call(self, node: ast.FunctionCallExpression, symtab: SymbolTable, vertex: _Vertex) -> None:
        for argument in node.args:
            self.visit(argument, symtab, vertex)
        if self.exceptions and node.name in ("raise", "raise_precise"):
            code = _value(node.args[0], symtab)
            if not isinstance(code, int) or isinstance(code, bool) or code < 0:
                node.value_error("Cannot determine value of exception code")
            vertex.mask |= 1 << code
            return
        definition = function_definition(node, symtab)
        if not self.exceptions:
            vertex.functions[definition.name] = definition
        if definition.builtin or definition.generated or definition.body is None:
            return
        body_symtab, values = _arguments(node, definition, symtab)
        globals_ = tuple(
            (name, _hashable(binding.value))
            for name in sorted(body_symtab.keys_pretty()[0])
            if isinstance(binding := body_symtab.get_global(name), Var)
        )
        key = (
            "exceptions" if self.exceptions else "functions",
            id(symtab._env),
            id(definition),
            values,
            globals_,
        )
        vertex.edges.add(key)
        if key in self.vertices:
            return
        cached = self.cache.get(key)
        child = _Vertex()
        self.vertices[key] = child
        if cached is not None:
            if self.exceptions:
                child.mask = cached
            else:
                child.functions = {fn.name: fn for fn in cached}
            return
        if len(self.vertices) > 4096:
            node.value_error("Unbounded argument-specialized recursion in reachability")
        if not self.exceptions:
            child.functions[definition.name] = definition
        self.pending.append((definition.body, body_symtab, child))

    def visit(self, node: ast.Node, symtab: SymbolTable, vertex: _Vertex) -> None:
        if isinstance(node, ast.FunctionCallExpression):
            self.call(node, symtab, vertex)
        elif isinstance(node, ast.If):
            alternatives = []
            for condition, body in (
                (node.if_cond, node.if_body),
                *((branch.condition, branch.body) for branch in node.elseifs),
            ):
                self.visit(condition, symtab, vertex)
                value = _value(condition, symtab)
                if value is not False:
                    alternative = isolated_symtab(symtab)
                    self.visit(body, alternative, vertex)
                    alternatives.append(alternative)
                if value is not _UNKNOWN and value:
                    break
            else:
                alternative = isolated_symtab(symtab)
                self.visit(node.final_else_body, alternative, vertex)
                alternatives.append(alternative)
            for name in {name for scope in symtab.keys_pretty() for name in scope}:
                binding = symtab.get(name)
                if isinstance(binding, Var):
                    values = [alternative.get(name).value for alternative in alternatives]
                    binding.value = (
                        values[0]
                        if all(_hashable(value) == _hashable(values[0]) for value in values)
                        else None
                    )
        elif isinstance(node, (ast.ConditionalStatement, ast.ConditionalReturnStatement)):
            self.visit(node.condition, symtab, vertex)
            value = _value(node.condition, symtab)
            if value is not False:
                action = (
                    node.return_expression
                    if isinstance(node, ast.ConditionalReturnStatement)
                    else node.action
                )
                self.visit(action, isolated_symtab(symtab) if value is _UNKNOWN else symtab, vertex)
                if value is _UNKNOWN:
                    from .pruning import _nullify

                    _nullify(action, symtab)
        elif isinstance(node, ast.ForLoop):
            local = isolated_symtab(symtab)
            bindings = [
                (binding, local.get(name))
                for name in {name for scope in symtab.keys_pretty() for name in scope}
                if isinstance(binding := symtab.get(name), Var)
            ]
            local.push(node)
            _execute(node.init, local)
            if isinstance(local.get(node.init.lhs.name), Var):
                local.get(node.init.lhs.name).value = None
            from .pruning import _nullify

            _nullify(node, local, loop_carried=True)
            for child in node.children:
                self.visit(child, local, vertex)

            _nullify(node, local, loop_carried=True)
            for original, copied in bindings:
                if local.get(original.name) is copied:
                    original.value = copied.value
        elif isinstance(node, (ast.FunctionBody, ast.IfBody)):
            symtab.push(node)
            try:
                for child in node.children:
                    self.visit(child, symtab, vertex)
            finally:
                symtab.pop()
        elif isinstance(node, ast.Statement):
            self.visit(node.action, symtab, vertex)
            _execute(node.action, symtab)
        else:
            for child in node.children:
                self.visit(child, symtab, vertex)

    def run(self, node: ast.Node, symtab: SymbolTable) -> _Vertex:
        root = _Vertex()
        local = isolated_symtab(symtab)
        function = (
            node if isinstance(node, ast.FunctionDef) else node.find_ancestor(ast.FunctionDef)
        )
        if isinstance(node, (ast.FunctionBody, ast.FunctionDef)) and function is not None:
            local.push(function)
            for argument_type, argument_name in function.semantic_arguments(local):
                if local.get(argument_name) is None:
                    local.add(
                        argument_name,
                        Var(argument_name, argument_type),
                    )
        if isinstance(node, ast.FunctionDef):
            if node.body is None:
                return root
            node = node.body
        self.visit(node, local, root)
        while self.pending:
            body, body_symtab, vertex = self.pending.pop()
            self.visit(body, body_symtab, vertex)
        # Solve strongly connected closures together; no partial recursion
        # sentinel ever leaks into a caller-owned cache.
        changed = True
        while changed:
            changed = False
            for vertex in reversed(tuple(self.vertices.values())):
                for edge in vertex.edges:
                    changed |= vertex.merge(self.vertices[edge])
        for key, vertex in self.vertices.items():
            self.cache[key] = vertex.mask if self.exceptions else tuple(vertex.functions.values())
        for edge in root.edges:
            root.merge(self.vertices[edge])
        return root


def reachable_functions(
    node: ast.Node,
    symtab: SymbolTable,
    *,
    cache: MutableMapping[Hashable, tuple[ast.FunctionDef, ...]] | None = None,
) -> tuple[ast.FunctionDef, ...]:
    """Return direct and transitive callees; reuse complete specialized closures."""

    result = _Graph({} if cache is None else cache, exceptions=False).run(node, symtab)
    return tuple(result.functions.values())


def reachable_exceptions(
    node: ast.Node,
    symtab: SymbolTable,
    *,
    cache: MutableMapping[Hashable, int] | None = None,
) -> int:
    """Return the bit mask of reachable exception codes."""

    return _Graph({} if cache is None else cache, exceptions=True).run(node, symtab).mask
