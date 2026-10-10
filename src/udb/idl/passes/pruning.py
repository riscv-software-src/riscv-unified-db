# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Scope-aware pruning without mutation of a caller's tree or symbol table."""

from __future__ import annotations

from .. import ast
from ..errors import IdlValueUnknown
from ..symbols import SymbolTable, Var
from ..types import Type
from ._prune_expressions import UNKNOWN, expression, known
from ._tree import clone, isolated_symtab, rebuild
from ._walk import walk
from ._writes import WriteAnalysis


def _noop() -> ast.Noop:
    from ..source import IdlSource

    return ast.Noop(source=IdlSource("", label="<pruned>"), start=0, end=0)


def _terminates(node: ast.Node) -> bool:
    if isinstance(node, (ast.ReturnStatement, ast.ReturnExpression)):
        return True
    if isinstance(node, ast.Statement):
        return isinstance(node.action, ast.FunctionCallExpression) and node.action.name == "raise"
    if isinstance(node, (ast.IfBody, ast.FunctionBody)):
        return bool(node.children) and _terminates(node.children[-1])
    if isinstance(node, ast.If):
        if isinstance(node.if_cond, ast.TrueExpression):
            return _terminates(node.if_body)
        return (
            _terminates(node.if_body)
            and all(_terminates(branch.body) for branch in node.elseifs)
            and _terminates(node.final_else_body)
        )
    return False


def _nullify(node: ast.Node, symtab: SymbolTable, *, loop_carried: bool = False) -> None:
    WriteAnalysis(node, symtab).invalidate(loop_carried=loop_carried)


def _execute(node: ast.Node, symtab: SymbolTable, *, declaration: bool = False) -> None:
    if declaration:
        node.add_symbol(symtab)
        return
    if node.is_executable:
        try:
            node.execute(symtab)
        except IdlValueUnknown:
            pass


def _body(node: ast.Node, symtab: SymbolTable, *, restore: bool) -> ast.Node:
    if restore:
        symtab = isolated_symtab(symtab)
    symtab.push(node)
    try:
        children = []
        for child in node.children:
            result = _prune(child, symtab, None)
            if isinstance(result, ast.IfBody):
                children.extend(result.children)
            else:
                children.append(result)
            if _terminates(result):
                break
        return rebuild(node, tuple(children))
    finally:
        symtab.pop()


def _selected_body(node: ast.If, body: ast.IfBody, symtab: SymbolTable) -> ast.Node:
    result = _body(body, symtab, restore=False)
    if not any(
        (child.action if isinstance(child, ast.Statement) else child).is_declaration
        for child in result.children
    ):
        return result
    condition = ast.TrueExpression(source=node.source, start=node.start, end=node.start)
    empty = ast.IfBody(source=node.source, start=node.end, end=node.end)
    return rebuild(node, (condition, result, empty))


def _prune(node: ast.Node, symtab: SymbolTable, forced_type: Type | None) -> ast.Node:
    if isinstance(node, ast.FunctionBody):
        return _body(node, symtab, restore=False)
    if isinstance(node, ast.IfBody):
        return _body(node, symtab, restore=True)
    if isinstance(node, ast.If):
        branches = [(node.if_cond, node.if_body), *((b.condition, b.body) for b in node.elseifs)]
        pending = []
        final = node.final_else_body
        for condition, body in branches:
            value = known(condition, symtab)
            if value is not UNKNOWN:
                if not value:
                    continue
                if not pending:
                    return _selected_body(node, body, symtab)
                final = body
                break
            pending.append((condition, body))
        if not pending:
            return _selected_body(node, final, symtab) if final.stmts else _noop()
        condition, body = pending[0]
        elseifs = tuple(
            ast.ElseIf(
                source=node.source,
                start=cond.start,
                end=other.end,
                children=(_prune(cond, symtab, None), _body(other, symtab, restore=True)),
            )
            for cond, other in pending[1:]
        )
        result = rebuild(
            node,
            (
                _prune(condition, symtab, None),
                _body(body, symtab, restore=True),
                *elseifs,
                _body(final, symtab, restore=True),
            ),
        )
        _nullify(result, symtab)
        return result
    if isinstance(node, (ast.ConditionalStatement, ast.ConditionalReturnStatement)):
        value = known(node.condition, symtab)
        action = node.children[0]
        if value is not UNKNOWN:
            if not value:
                return _noop()
            pruned = _prune(action, symtab, None)
            if isinstance(node, ast.ConditionalReturnStatement):
                return pruned
            return ast.Statement(
                source=node.source,
                start=node.start,
                end=node.end,
                children=(pruned,),
            )
        pruned = _prune(action, isolated_symtab(symtab), None)
        _nullify(action, symtab)
        return rebuild(node, (pruned, _prune(node.condition, symtab, None)))
    if isinstance(node, ast.ForLoop):
        symtab.push(node)
        try:
            initialization = _prune(node.init, symtab, None)
            _nullify(node, symtab, loop_carried=True)
            snapshot = symtab.snapshot_values()
            result = rebuild(
                node,
                (
                    initialization,
                    *(_prune(child, symtab, None) for child in node.children[1:]),
                ),
            )
            symtab.restore_values(snapshot)
            _nullify(node, symtab, loop_carried=True)
        finally:
            symtab.pop()
        return result
    if isinstance(node, (ast.VariableDeclaration, ast.MultiVariableDeclaration)):
        _execute(node, symtab, declaration=True)
        return node
    if isinstance(node, ast.VariableDeclarationWithInitialization):
        _execute(node, symtab, declaration=True)
        children = tuple(
            _prune(child, symtab, None) if child is node.rhs or child is node.ary_size else child
            for child in node.children
        )
        return rebuild(node, children)
    assignments = (
        ast.VariableAssignment,
        ast.AryElementAssignment,
        ast.AryRangeAssignment,
        ast.FieldAssignment,
        ast.MultiVariableAssignment,
        ast.CsrFieldAssignment,
        ast.PcAssignment,
        ast.CsrSoftwareWrite,
    )
    if isinstance(node, assignments):
        protected = (
            node.variables
            if isinstance(node, ast.MultiVariableAssignment)
            else ()
            if isinstance(node, ast.PcAssignment)
            else node.children[:1]
        )
        result = rebuild(
            node,
            tuple(
                child if any(child is item for item in protected) else _prune(child, symtab, None)
                for child in node.children
            ),
        )
        _execute(result, symtab)
        return result
    if isinstance(node, (ast.PostIncrementExpression, ast.PostDecrementExpression)):
        _execute(node, symtab)
        return node
    if isinstance(node, (ast.Statement, ast.ReturnStatement, ast.ReturnExpression)):
        return rebuild(node, tuple(_prune(child, symtab, None) for child in node.children))
    if isinstance(node, ast.FunctionDef):
        if node.body is None:
            return node
        local = symtab.global_clone()
        local.push(node)
        for argument_type, argument_name in node.semantic_arguments(local):
            local.add(argument_name, Var(argument_name, argument_type))
        return rebuild(node, (*node.children[:-1], _body(node.body, local, restore=False)))
    return expression(node, symtab, forced_type, _prune)


def prune(node: ast.Node, symtab: SymbolTable, *, forced_type: Type | None = None) -> ast.Node:
    """Specialize known expressions and branches, keeping unknown paths sound."""

    local = isolated_symtab(symtab)
    function = node.find_ancestor(ast.FunctionDef)
    if isinstance(node, ast.FunctionBody) and function is not None:
        local.push(function)
        for argument_type, argument_name in function.semantic_arguments(local):
            if local.get(argument_name) is None:
                local.add(
                    argument_name,
                    Var(argument_name, argument_type),
                )
    result = _prune(clone(node), local, forced_type)
    # Each returned subtree owns coherent parent links, independent of its input.
    for parent in walk(result):
        for child in parent.children:
            object.__setattr__(child, "parent", parent)
    object.__setattr__(result, "parent", None)
    return result
