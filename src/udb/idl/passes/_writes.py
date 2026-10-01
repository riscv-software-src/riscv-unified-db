# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lexical write bindings and conservative loop-carried index evaluation."""

from __future__ import annotations

from collections.abc import Callable

from .. import ast
from ..symbols import SymbolTable, Var
from ._prune_expressions import UNKNOWN, known
from ._tree import clone, isolated_symtab
from ._walk import walk

Key = tuple[int, str]


def _root(node: ast.Node) -> ast.Node:
    while isinstance(node, (ast.AryElementAccess, ast.AryRangeAccess, ast.FieldAccessExpression)):
        node = node.obj if isinstance(node, ast.FieldAccessExpression) else node.var
    return node


class WriteAnalysis:
    def __init__(self, node: ast.Node, symtab: SymbolTable):
        self.node = clone(node)
        self.symtab = symtab
        self.scoped = {name for scope in symtab.keys_pretty()[1:] for name in scope}
        # Global originals are added on first use, which avoids copying every
        # global binding out of the shared frozen scope.
        self.originals = {
            (0, name): binding
            for name in self.scoped
            if isinstance(binding := symtab.get(name), Var)
        }
        self.changed: set[Key] = set()
        self.dependencies: dict[Key, set[Key]] = {}
        self._visit(lambda current, target, key, binding, table: self.changed.add(key))

    def _visit(
        self,
        action: Callable[[ast.Node, ast.Node, Key, Var, SymbolTable], None],
        *,
        unknown: set[Key] | None = None,
    ) -> None:
        table = isolated_symtab(self.symtab)
        keys = {id(table.get(name)): key for key in self.originals for name in (key[1],)}
        # Keep popped bindings alive so their identity keys cannot be reused.
        bindings = {id(table.get(name)): table.get(name) for _, name in self.originals}
        if unknown:
            for key in self.originals.keys() & unknown:
                table.get(key[1]).value = None

        def key_of(name: str, binding: Var) -> Key:
            key = keys.get(id(binding))
            if key is None and name not in self.scoped and binding is table.get_global(name):
                key = (0, name)
                original = self.symtab.get(name)
                if not isinstance(original, Var):
                    raise KeyError(id(binding))
                self.originals[key] = original
                keys[id(binding)] = key
                bindings[id(binding)] = binding
                if unknown and key in unknown:
                    binding.value = None
            return keys[id(binding)]

        def write(current: ast.Node, target: ast.Node) -> None:
            root = _root(target)
            if not isinstance(root, ast.Id):
                return
            binding = table.get(root.name)
            if binding is None:
                root.type_error(f"No symbol '{root.name}'")
            if isinstance(binding, Var):
                action(current, target, key_of(root.name, binding), binding, table)

        def visit(current: ast.Node) -> None:
            if isinstance(current, (ast.FunctionBody, ast.IfBody, ast.ForLoop)):
                table.push(current)
                try:
                    children = current.children
                    if current is self.node and isinstance(current, ast.ForLoop):
                        # The caller has already registered this loop's initializer.
                        children = children[1:]
                    for child in children:
                        visit(child)
                finally:
                    table.pop()
                return
            if current.is_declaration:
                dependencies = set()
                if isinstance(current, ast.VariableDeclarationWithInitialization):
                    dependencies = {
                        key_of(child.name, binding)
                        for child in walk(current.rhs)
                        if isinstance(child, ast.Id)
                        and isinstance(binding := table.get(child.name), Var)
                    }
                    names = (current.id,)
                elif isinstance(current, ast.VariableDeclaration):
                    names = (current.id.name,)
                elif isinstance(current, ast.MultiVariableDeclaration):
                    names = tuple(variable.name for variable in current.var_names)
                else:
                    names = ()
                current.add_symbol(table)
                for name in names:
                    binding = table.get(name)
                    key = (id(current), name)
                    keys[id(binding)] = key
                    bindings[id(binding)] = binding
                    self.dependencies[key] = dependencies
                    if unknown and key in unknown:
                        binding.value = None
            elif isinstance(
                current,
                (
                    ast.VariableAssignment,
                    ast.AryElementAssignment,
                    ast.AryRangeAssignment,
                    ast.FieldAssignment,
                ),
            ):
                write(current, current.children[0])
            elif isinstance(current, ast.MultiVariableAssignment):
                for target in current.variables:
                    write(current, target)
            elif isinstance(current, (ast.PostIncrementExpression, ast.PostDecrementExpression)):
                write(current, current.rval)
            for child in current.children:
                visit(child)

        visit(self.node)

    def invalidate(self, *, loop_carried: bool = False) -> None:
        unknown = set(self.changed) if loop_carried else set()
        if loop_carried:
            while True:
                affected = {
                    key for key, dependencies in self.dependencies.items() if dependencies & unknown
                }
                if affected <= unknown:
                    break
                unknown.update(affected)

        def apply(
            current: ast.Node, target: ast.Node, key: Key, binding: Var, table: SymbolTable
        ) -> None:
            original = self.originals.get(key)
            if original is None:
                binding.value = None
                return
            if isinstance(current, ast.AryElementAssignment):
                container = original.value
                accesses = []
                lhs = current.lhs
                while isinstance(lhs, ast.AryElementAccess):
                    accesses.append(lhs.index)
                    lhs = lhs.var
                if not isinstance(lhs, ast.Id):
                    original.value = None
                else:
                    for index_node in (*reversed(accesses), current.index):
                        index = known(index_node, table)
                        if not isinstance(container, list):
                            original.value = None
                            break
                        if index is UNKNOWN:
                            container[:] = [None] * len(container)
                            break
                        if not isinstance(index, int) or not 0 <= index < len(container):
                            original.value = None
                            break
                        if index_node is current.index:
                            container[index] = None
                        else:
                            container = container[index]
            else:
                original.value = None
            if not loop_carried:
                binding.value = original.clone().value

        self._visit(apply, unknown=unknown)


def written_names(node: ast.Node, symtab: SymbolTable) -> set[str]:
    analysis = WriteAnalysis(node, symtab)
    return {name for scope, name in analysis.changed if scope == 0}
