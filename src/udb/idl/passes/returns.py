# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Syntactic return alternatives, with ordered enclosing branch conditions."""

from __future__ import annotations

from dataclasses import dataclass

from ..ast import (
    ConditionalReturnStatement,
    ForLoop,
    FunctionBody,
    If,
    Node,
    ParenExpression,
    ReturnExpression,
    ReturnStatement,
    TernaryOperatorExpression,
    UnaryOperatorExpression,
)
from ..symbols import SymbolTable
from ._tree import clone


@dataclass(frozen=True)
class ConditionalReturnValue:
    expression: Node
    conditions: tuple[Node, ...]


def _negate(condition: Node) -> Node:
    return UnaryOperatorExpression(
        source=condition.source,
        start=condition.start,
        end=condition.end,
        op="!",
        children=(clone(condition),),
    )


def return_values(body: FunctionBody, symtab: SymbolTable) -> tuple[ConditionalReturnValue, ...]:
    """Find returns, including syntactically present unreachable returns.

    This is an option-analysis pass, not an execution pass. Prune first when
    known conditions or dead statements should be excluded.
    """

    result: list[ConditionalReturnValue] = []

    def expression(node: Node, conditions: tuple[Node, ...]) -> None:
        unwrapped = node
        while isinstance(unwrapped, ParenExpression):
            unwrapped = unwrapped.expression
        if isinstance(unwrapped, TernaryOperatorExpression):
            node = unwrapped
        if isinstance(node, TernaryOperatorExpression):
            expression(node.true_expression, (*conditions, node.condition))
            expression(node.false_expression, (*conditions, _negate(node.condition)))
        else:
            result.append(ConditionalReturnValue(node, conditions))

    def visit(node: Node, conditions: tuple[Node, ...]) -> None:
        if isinstance(node, ConditionalReturnStatement):
            condition = node.condition
            while isinstance(condition, ParenExpression):
                condition = condition.expression
            visit(node.return_expression, (*conditions, condition))
        elif isinstance(node, ReturnStatement):
            visit(node.return_expression, conditions)
        elif isinstance(node, ReturnExpression):
            for value in node.return_value_nodes:
                expression(value, conditions)
        elif isinstance(node, If):
            visit(node.if_body, (*conditions, node.if_cond))
            prior = (*conditions, _negate(node.if_cond))
            for branch in node.elseifs:
                visit(branch.body, (*prior, branch.condition))
                prior = (*prior, _negate(branch.condition))
            visit(node.final_else_body, prior)
        elif isinstance(node, ForLoop):
            for statement in node.stmts:
                visit(statement, (*conditions, node.condition))
        else:
            for child in node.children:
                visit(child, conditions)

    visit(body, ())
    return tuple(result)
