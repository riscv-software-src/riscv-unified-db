# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Literal construction and expression specialization for the pruning pass."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import ast
from ..errors import IdlValueUnknown
from ..parser import parse
from ..source import IdlSource
from ..symbols import SymbolTable
from ..types import WIDTH_UNKNOWN, Type, TypeKind
from ._tree import rebuild
from ._walk import walk

UNKNOWN = object()


def integer(text: str) -> ast.IntLiteral:
    return ast.IntLiteral(
        source=IdlSource(text, label="<pruned>"), start=0, end=len(text), raw_text=text
    )


def known(node: ast.Node, symtab: SymbolTable) -> Any:
    try:
        value = node.value(symtab)
        return UNKNOWN if isinstance(value, ast.UnknownLiteral) else value
    except IdlValueUnknown:
        return UNKNOWN


def literal(value: Any, type_: Type, forced_type: Type | None = None) -> ast.Node:
    if value is None or isinstance(value, ast.UnknownLiteral):
        raise IdlValueUnknown("Literal contains unknown values")
    if type_.kind == TypeKind.BOOLEAN:
        return parse("true" if value else "false", "expression")
    if type_.kind == TypeKind.ENUM_REF:
        enum = type_.enum_class
        return parse(
            f"{enum.name}::{enum.element_names[enum.element_values.index(value)]}", "expression"
        )
    if type_.kind == TypeKind.STRING:
        import json

        return parse(json.dumps(value), "expression")
    if type_.kind == TypeKind.ARRAY:
        children = tuple(literal(item, type_.sub_type) for item in value)
        leaves = [
            leaf for child in children for leaf in walk(child) if isinstance(leaf, ast.IntLiteral)
        ]
        if leaves:
            symtab = SymbolTable()
            width = max(leaf.type(symtab).width for leaf in leaves)
            forced = Type(TypeKind.BITS, width=width)

            def coerce(node: ast.Node) -> ast.Node:
                if isinstance(node, ast.IntLiteral):
                    return literal(node.value(symtab), forced, forced)
                return rebuild(node, tuple(coerce(child) for child in node.children))

            children = tuple(coerce(child) for child in children)
        source = IdlSource("pruned_literal_ary", label="<pruned>")
        return ast.ArrayLiteral(source=source, start=0, end=len(source.text), children=children)
    if type_.kind != TypeKind.BITS:
        raise IdlValueUnknown(f"No literal syntax for {type_.kind}")
    width = forced_type.width if forced_type is not None else max(1, value.bit_length())
    if width == WIDTH_UNKNOWN:
        raise IdlValueUnknown("Cannot prune integer with unknown width")
    text = (
        f"{width}'sd{value}"
        if value < 0
        else f"{width}'{value}"
        if value <= 512
        else f"{width}'h{value:x}"
    )
    return integer(text)


def expression(
    node: ast.Node,
    symtab: SymbolTable,
    forced_type: Type | None,
    prune: Callable[[ast.Node, SymbolTable, Type | None], ast.Node],
) -> ast.Node:
    if isinstance(node, ast.IntLiteral):
        if forced_type is None:
            return node
        if forced_type.width == WIDTH_UNKNOWN:
            node.value_error("Cannot force an unknown literal width")
        value = node.value(symtab)
        return integer(
            f"{forced_type.width}'sd{value}" if value < 0 else f"{forced_type.width}'d{value}",
        )
    if isinstance(node, ast.ParenExpression):
        child = prune(node.expression, symtab, forced_type)
        if isinstance(
            child,
            (ast.ParenExpression, ast.IntLiteral, ast.TrueExpression, ast.FalseExpression, ast.Id),
        ):
            return child
        return rebuild(node, (child,))
    if isinstance(node, ast.TernaryOperatorExpression):
        condition = known(node.condition, symtab)
        if condition is not UNKNOWN:
            branch = node.true_expression if condition else node.false_expression
            return prune(branch, symtab, forced_type or node.type(symtab))
        return rebuild(node, tuple(prune(child, symtab, None) for child in node.children))
    if isinstance(node, ast.BitsCast):
        child = prune(node.expression, symtab, forced_type)
        return child if child.type(symtab).kind == TypeKind.BITS else rebuild(node, (child,))
    foldable = (
        ast.Id,
        ast.BinaryExpression,
        ast.UnaryOperatorExpression,
        ast.FunctionCallExpression,
        ast.ConcatenationExpression,
        ast.ReplicationExpression,
        ast.AryElementAccess,
        ast.AryRangeAccess,
        ast.FieldAccessExpression,
        ast.EnumRef,
        ast.CsrReadExpression,
        ast.CsrFieldReadExpression,
        ast.ArrayLiteral,
        ast.ArraySize,
        ast.ArrayIncludes,
        ast.EnumCast,
        ast.EnumSize,
        ast.EnumArrayCast,
        ast.EnumElementSize,
        ast.SignCast,
    )
    if isinstance(node, foldable):
        value = known(node, symtab)
        if value is not UNKNOWN:
            type_ = node.type(symtab)
            if type_.kind == TypeKind.CSR:
                bits = Type(TypeKind.BITS, width=type_.width)
                return literal(value, bits, forced_type or bits)
            if type_.kind != TypeKind.BITS or type_.width != WIDTH_UNKNOWN:
                try:
                    return literal(value, type_, forced_type or type_)
                except IdlValueUnknown:
                    pass
    if isinstance(node, ast.BinaryExpression):
        lhs, rhs = known(node.lhs, symtab), known(node.rhs, symtab)
        if node.op in ("&&", "||"):
            identity = node.op == "&&"
            if lhs is identity:
                return prune(node.rhs, symtab, None)
            if rhs is identity:
                return prune(node.lhs, symtab, None)
            if lhs is not UNKNOWN and lhs is not identity:
                return parse("false" if identity else "true", "expression")
            if rhs is not UNKNOWN and rhs is not identity:
                return parse("false" if identity else "true", "expression")
        if node.op in ("&", "|"):
            type_ = node.type(symtab)
            for value, other in ((lhs, node.rhs), (rhs, node.lhs)):
                width = other.type(symtab).width
                same_width = width != WIDTH_UNKNOWN and width == type_.width
                if value == 0 and node.op == "|" and same_width:
                    return prune(other, symtab, forced_type)
                if type_.width != WIDTH_UNKNOWN:
                    if value == 0 and node.op == "&":
                        return literal(0, type_, forced_type or type_)
                    if width != WIDTH_UNKNOWN and value == (1 << width) - 1:
                        if node.op == "|":
                            return literal(value, type_, forced_type or type_)
                        if same_width:
                            return prune(other, symtab, forced_type)
        propagate = forced_type if node.op in ("&", "|") else None
        return rebuild(node, tuple(prune(child, symtab, propagate) for child in node.children))
    children = tuple(prune(child, symtab, None) for child in node.children)
    result = rebuild(node, children)
    if isinstance(node, (ast.ConcatenationExpression, ast.ReplicationExpression)) and forced_type:
        width = node.type(symtab).width
        target = forced_type.width
        if target == WIDTH_UNKNOWN or width == WIDTH_UNKNOWN:
            node.value_error("Cannot resize expression with unknown width")
        if target < width:
            result = ast.AryRangeAccess(
                source=node.source,
                start=node.start,
                end=node.end,
                children=(result, parse(str(target - 1), "expression"), parse("0", "expression")),
            )
        elif target > width:
            zero = literal(
                0,
                Type(TypeKind.BITS, width=target - width),
                Type(TypeKind.BITS, width=target - width),
            )
            result = ast.ConcatenationExpression(
                source=node.source,
                start=node.start,
                end=node.end,
                children=(zero, result),
            )
            if isinstance(node, ast.ConcatenationExpression):
                result = rebuild(result, (zero, *children))
    return result
