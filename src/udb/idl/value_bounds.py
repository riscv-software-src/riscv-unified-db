# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Port of Ruby's ``AstNode#max_value``/``#min_value`` (``idlc/lib/idlc/ast.rb``).

Ruby -> Python mapping
-----------------------

===================================================  ===============================
Ruby (``ast.rb``)                                    Python (this module)
===================================================  ===============================
``Rvalue#max_value``/``#min_value`` (generic default) :func:`max_value`/:func:`min_value` (unregistered fallback)
``IdAst#max_value``/``#min_value``                    ``Id`` dispatch
``ParenExpressionAst#max_value``/``#min_value``       ``ParenExpression`` dispatch
``TernaryOperatorExpressionAst#max_value``/``#min_value``  ``TernaryOperatorExpression`` dispatch
``BinaryExpressionAst#max_value``/``#min_value``      ``BinaryExpression`` dispatch
===================================================  ===============================

Sentinel: functions return an ``int``, or the string ``"unknown"`` (matching
this codebase's existing convention, e.g. ``udb.idl.types.WIDTH_UNKNOWN``,
rather than inventing a new sentinel type for Ruby's ``:unknown`` symbol).

This module deliberately lives *outside* ``udb.idl.ast`` (a new, standalone
module) rather than adding ``max_value``/``min_value`` methods to the AST
node classes themselves: another agent is concurrently editing
``udb.idl.ast`` on a separate slice, and adding methods there risks a merge
conflict. Dispatch is by node *type*, via :func:`functools.singledispatch`,
so this module only needs read access to the (frozen, ``slots=True``) node
classes already exported from ``udb.idl.ast``.

Function calls use the ordinary compiler's registered signatures and value semantics;
this module does not duplicate generated callback dispatch.
"""

from __future__ import annotations

from functools import singledispatch
from typing import Any, Final, Literal

from .ast import (
    BinaryExpression,
    Id,
    Node,
    ParenExpression,
    TernaryOperatorExpression,
)
from .errors import IdlInternalError, IdlValueUnknown
from .symbols import SymbolTable

__all__ = ["UNKNOWN", "Unknown", "max_value", "min_value"]

#: Sentinel returned when a bound cannot be determined at compile time.
#: Matches Ruby's ``:unknown`` symbol and this codebase's ``"unknown"`` string convention.
UNKNOWN: Final = "unknown"

Unknown = Literal["unknown"]


def _try_value(node: Node, symtab: SymbolTable) -> Any | None:
    """Return an ordinary compile-time value, or ``None`` for explicitly unknown."""
    try:
        return node.value(symtab)
    except IdlValueUnknown:
        return None


@singledispatch
def max_value(node: Node, symtab: SymbolTable) -> int | Unknown:
    """Port of ``Rvalue#max_value`` (the generic default, used by every AST node
    that doesn't override it in Ruby): the compile-time value if known, else
    :data:`UNKNOWN`.
    """
    value = _try_value(node, symtab)
    return UNKNOWN if value is None else value


@singledispatch
def min_value(node: Node, symtab: SymbolTable) -> int | Unknown:
    """Port of ``Rvalue#min_value`` (see :func:`max_value`)."""
    value = _try_value(node, symtab)
    return UNKNOWN if value is None else value


@max_value.register
def _max_value_paren(node: ParenExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``ParenExpressionAst#max_value``."""
    return max_value(node.expression, symtab)


@min_value.register
def _min_value_paren(node: ParenExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``ParenExpressionAst#min_value``."""
    return min_value(node.expression, symtab)


@max_value.register
def _max_value_id(node: Id, symtab: SymbolTable) -> int | Unknown:
    """Port of ``IdAst#max_value``: known value, else the referenced param's ``schema.max_val``."""
    value = _try_value(node, symtab)
    if value is not None:
        return value
    var = symtab.get(node.name)
    if var is not None and getattr(var, "param", False):
        param = symtab.param(node.name)
        if param is not None and param.schema.max_val_known:
            return param.schema.max_val
    return UNKNOWN


@min_value.register
def _min_value_id(node: Id, symtab: SymbolTable) -> int | Unknown:
    """Port of ``IdAst#min_value``: known value, else the referenced param's ``schema.min_val``."""
    value = _try_value(node, symtab)
    if value is not None:
        return value
    var = symtab.get(node.name)
    if var is not None and getattr(var, "param", False):
        param = symtab.param(node.name)
        if param is not None and param.schema.min_val_known:
            return param.schema.min_val
    return UNKNOWN


@max_value.register
def _max_value_ternary(node: TernaryOperatorExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``TernaryOperatorExpressionAst#max_value``: follow the decided branch
    if the condition is compile-time-known, else the max of *both* branches.
    """
    cond = _try_value(node.condition, symtab)
    if cond is not None:
        return max_value(node.true_expression if cond else node.false_expression, symtab)
    true_max = max_value(node.true_expression, symtab)
    false_max = max_value(node.false_expression, symtab)
    if true_max == UNKNOWN or false_max == UNKNOWN:
        return UNKNOWN
    return max(true_max, false_max)


@min_value.register
def _min_value_ternary(node: TernaryOperatorExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``TernaryOperatorExpressionAst#min_value``: follow the decided branch
    if the condition is compile-time-known, else the min of *both* branches.
    """
    cond = _try_value(node.condition, symtab)
    if cond is not None:
        return min_value(node.true_expression if cond else node.false_expression, symtab)
    true_min = min_value(node.true_expression, symtab)
    false_min = min_value(node.false_expression, symtab)
    if true_min == UNKNOWN or false_min == UNKNOWN:
        return UNKNOWN
    return min(true_min, false_min)


_ARITH_OPS: Final = frozenset({"+", "`+", "-", "`-", "*", "`*"})


def _bits_needed(value: int, signed: bool) -> int:
    """Port of ``BinaryExpressionAst#bits_needed``."""
    if signed:
        return value.bit_length() + 1
    if value < 0:
        raise IdlInternalError("unsigned value is negative")
    return 1 if value == 0 else value.bit_length()


def _binary_operand_bounds(node: Node, symtab: SymbolTable) -> tuple[int | Unknown, int | Unknown]:
    """``(max_value, min_value)`` of one operand, preferring its exact compile-time
    value (Ruby: ``value_try { lhs.value(symtab) }`` / ``value_else { lhs.max_value(symtab) }``).
    """
    value = _try_value(node, symtab)
    if value is not None:
        return value, value
    return max_value(node, symtab), min_value(node, symtab)


def _truncate_or_unknown(
    node: BinaryExpression,
    symtab: SymbolTable,
    result: int,
    width: int | str,
    signed: bool,
) -> int | Unknown:
    """Shared truncation-check tail of ``+``/``-``/``*`` (non-widening variants):
    if the result's width is known, truncate (with a warning) when it overflows;
    otherwise fall back to "does it fit in either operand's own width?"
    (Ruby: ``lhs.type(symtab).width``/``rhs.type(symtab).width``).
    """
    bits_needed = _bits_needed(result, signed)
    if isinstance(width, int):
        if bits_needed <= width:
            return result
        truncated = node.truncate(result, width, signed)
        node.truncation_warn(
            f"result is truncated from {result} to {truncated}. "
            "Did you mean to use the widening operator?"
        )
        return truncated
    lhs_width = node.lhs.type(symtab).width
    rhs_width = node.rhs.type(symtab).width
    if isinstance(lhs_width, int) and lhs_width >= bits_needed:
        return result
    if isinstance(rhs_width, int) and rhs_width >= bits_needed:
        return result
    return UNKNOWN


def _binary_bound(
    node: BinaryExpression,
    symtab: SymbolTable,
    *,
    lhs_bound: int | Unknown,
    rhs_bound: int | Unknown,
    combine: Any,
    other_lhs_bound: int | Unknown,
    other_rhs_bound: int | Unknown,
    pick_extreme: Any,
    include_cross_products: bool = False,
) -> int | Unknown:
    """Shared body of :func:`_max_value_binary`/:func:`_min_value_binary`: both
    follow the exact same op-dispatch/truncation shape in Ruby, differing only
    in which operand bound (max vs. min) feeds each operator and how ``*``
    breaks ties between the two candidate products.
    """
    if node.op not in _ARITH_OPS:
        raise IdlInternalError(f"value_bounds: not supported for operator {node.op!r}")

    result_type = node.type(symtab)
    width = result_type.width
    signed = result_type.is_signed

    if node.op in ("+", "`+", "-", "`-"):
        if lhs_bound == UNKNOWN or rhs_bound == UNKNOWN:
            return UNKNOWN
        total = combine(lhs_bound, rhs_bound)
        if total < 0 and not signed and isinstance(width, int):
            total &= (1 << width) - 1
        if node.op in ("`+", "`-"):
            return total
        return _truncate_or_unknown(node, symtab, total, width, signed)

    # "*" / "`*"
    if lhs_bound == UNKNOWN or rhs_bound == UNKNOWN:
        return UNKNOWN
    lhs_signed = node.lhs.type(symtab).is_signed
    rhs_signed = node.rhs.type(symtab).is_signed
    if include_cross_products:
        if lhs_signed and other_rhs_bound == UNKNOWN:
            return UNKNOWN
        if rhs_signed and other_lhs_bound == UNKNOWN:
            return UNKNOWN
    elif lhs_signed and rhs_signed and (other_lhs_bound == UNKNOWN or other_rhs_bound == UNKNOWN):
        return UNKNOWN
    prod = lhs_bound * rhs_bound
    if include_cross_products:
        if other_rhs_bound != UNKNOWN:
            prod = pick_extreme(prod, lhs_bound * other_rhs_bound)
        if other_lhs_bound != UNKNOWN:
            prod = pick_extreme(prod, other_lhs_bound * rhs_bound)
    if other_lhs_bound != UNKNOWN and other_rhs_bound != UNKNOWN:
        other_prod = other_lhs_bound * other_rhs_bound
        prod = pick_extreme(prod, other_prod)
    if prod < 0 and not signed and isinstance(width, int):
        prod &= (1 << width) - 1
    if node.op == "`*":
        return prod
    return _truncate_or_unknown(node, symtab, prod, width, signed)


@max_value.register
def _max_value_binary(node: BinaryExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``BinaryExpressionAst#max_value``. Only ``+``/``` + ```/``-``/``` - ```/``*``/``` * ```
    are handled (matching Ruby, which raises ``"TODO: #{op}"`` -- an
    unconditional internal error, not a graceful "unknown" -- for every
    other operator); any other operator raises :class:`IdlInternalError`.
    """
    lhs_max, lhs_min = _binary_operand_bounds(node.lhs, symtab)
    rhs_max, rhs_min = _binary_operand_bounds(node.rhs, symtab)
    if node.op in ("+", "`+"):
        return _binary_bound(
            node,
            symtab,
            lhs_bound=lhs_max,
            rhs_bound=rhs_max,
            combine=lambda a, b: a + b,
            other_lhs_bound=lhs_min,
            other_rhs_bound=rhs_min,
            pick_extreme=max,
        )
    if node.op in ("-", "`-"):
        return _binary_bound(
            node,
            symtab,
            lhs_bound=lhs_max,
            rhs_bound=rhs_min,
            combine=lambda a, b: a - b,
            other_lhs_bound=lhs_min,
            other_rhs_bound=rhs_max,
            pick_extreme=max,
        )
    return _binary_bound(
        node,
        symtab,
        lhs_bound=lhs_max,
        rhs_bound=rhs_max,
        combine=lambda a, b: a * b,
        other_lhs_bound=lhs_min,
        other_rhs_bound=rhs_min,
        pick_extreme=max,
    )


@min_value.register
def _min_value_binary(node: BinaryExpression, symtab: SymbolTable) -> int | Unknown:
    """Port of ``BinaryExpressionAst#min_value``: mirrors :func:`_max_value_binary`
    with min/max operand roles swapped per Ruby's own implementation.
    """
    lhs_max, lhs_min = _binary_operand_bounds(node.lhs, symtab)
    rhs_max, rhs_min = _binary_operand_bounds(node.rhs, symtab)
    if node.op in ("+", "`+"):
        return _binary_bound(
            node,
            symtab,
            lhs_bound=lhs_min,
            rhs_bound=rhs_min,
            combine=lambda a, b: a + b,
            other_lhs_bound=lhs_max,
            other_rhs_bound=rhs_max,
            pick_extreme=min,
        )
    if node.op in ("-", "`-"):
        return _binary_bound(
            node,
            symtab,
            lhs_bound=lhs_min,
            rhs_bound=rhs_max,
            combine=lambda a, b: a - b,
            other_lhs_bound=lhs_max,
            other_rhs_bound=rhs_min,
            pick_extreme=min,
        )
    return _binary_bound(
        node,
        symtab,
        lhs_bound=lhs_min,
        rhs_bound=rhs_min,
        combine=lambda a, b: a * b,
        other_lhs_bound=lhs_max,
        other_rhs_bound=rhs_max,
        pick_extreme=min,
        include_cross_products=True,
    )
