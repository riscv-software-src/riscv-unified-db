# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lexical binding and caller-owned state for syntactic register discovery."""

from __future__ import annotations

from collections.abc import Iterator

from .. import ast
from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ._tree import clone, isolated_symtab, merge_names
from ._writes import written_names


def _execute(node: ast.Node, table: SymbolTable) -> None:
    if node.is_declaration:
        node.add_symbol(table)
    elif node.is_executable and not isinstance(node, ast.FunctionCallExpression):
        try:
            node.execute(table)
        except IdlValueUnknown:
            pass


def register_nodes(node: ast.Node, symtab: SymbolTable) -> Iterator[tuple[ast.Node, SymbolTable]]:
    table = isolated_symtab(symtab)
    function = node.find_ancestor(ast.FunctionDef)
    if isinstance(node, ast.FunctionBody) and function is not None:
        table.push(function)
        for dtype, name in function.semantic_arguments(table):
            if table.get(name) is None:
                table.add(name, Var(name, dtype))

    def visit(current: ast.Node, local: SymbolTable):
        yield current, local
        if isinstance(current, ast.FunctionDef):
            if current.body is None:
                return
            scoped = local.global_clone()
            scoped.push(current)
            for dtype, name in current.semantic_arguments(scoped):
                scoped.add(name, Var(name, dtype))
            yield from visit(current.body, scoped)
        elif isinstance(current, (ast.FunctionBody, ast.IfBody)):
            local.push(current)
            try:
                for child in current.children:
                    yield from visit(child, local)
            finally:
                local.pop()
        elif isinstance(current, ast.If):
            alternatives = []
            for condition, body in (
                (current.if_cond, current.if_body),
                *((branch.condition, branch.body) for branch in current.elseifs),
            ):
                yield from visit(condition, local)
                branch = isolated_symtab(local)
                yield from visit(body, branch)
                alternatives.append(branch)
            branch = isolated_symtab(local)
            yield from visit(current.final_else_body, branch)
            alternatives.append(branch)
            for name in merge_names(local, alternatives):
                binding = local.get(name)
                if isinstance(binding, Var):
                    values = [branch.get(name).value for branch in alternatives]
                    binding.value = (
                        values[0] if all(value == values[0] for value in values) else None
                    )
        elif isinstance(current, ast.ForLoop):
            local.push(current)
            try:
                yield from visit(current.init, local)
                _execute(current.init, local)
                changed = written_names(current, local) | {current.init.lhs.name}
                for name in changed:
                    if isinstance(binding := local.get(name), Var):
                        binding.value = None
                for child in current.children[1:]:
                    yield from visit(child, local)
                for name in changed:
                    if isinstance(binding := local.get(name), Var):
                        binding.value = None
            finally:
                local.pop()
        elif isinstance(current, ast.Statement):
            yield from visit(current.action, local)
            _execute(current.action, local)
        else:
            for child in current.children:
                yield from visit(child, local)

    yield from visit(clone(node), table)
