# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exact, shared indexed-array encodings for the condition solver.

The length bounds describe the full array, not an allocated prefix. Quantified
predicates use the same Z3 array as indexed reads and concrete model extraction.
Solver incompleteness is reported as UNKNOWN; it never licenses an approximation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domains import ArrayDomain, ParameterDomain

MAX_MATERIALIZED_ARRAY_ITEMS = 4096
MAX_EXPLICIT_ARRAY_ITEMS = 64
MAX_INDEXED_SOLVER_RESOURCES = 10_000_000
MAX_ARRAY_WITNESS_RESOURCES = 25_000


@dataclass(slots=True)
class ArraySymbol:
    length: Any
    items: tuple[Any, ...]
    maximum: int
    tail: Any = None
    witness: Any = None
    axioms: list[Any] = field(default_factory=list)

    def item(self, z3: Any, index: Any) -> Any:
        if isinstance(index, int) and index < len(self.items):
            return self.items[index]
        return z3.Select(self.tail, index)

    def exists(self, owner: Any, predicate: Any) -> Any:
        z3 = owner._z3
        clauses = [
            z3.And(self.length > index, predicate(item)) for index, item in enumerate(self.items)
        ]
        if self.tail is not None:
            index = z3.FreshInt("udb_array_index", ctx=owner._z3_context)
            clauses.append(
                z3.Exists(
                    index,
                    z3.And(
                        index >= len(self.items),
                        index < self.length,
                        predicate(self.item(z3, index)),
                    ),
                )
            )
        return owner._or(*clauses)


def make_array(owner: Any, name: str, domain: ArrayDomain | None, value_hint: Any) -> ArraySymbol:
    # Imported at call time to avoid a module cycle and keep all scalar encodings
    # identical to the main solver's.
    from .solver import SolverError, _domain_kind, _make_scalar, _safe_name

    z3, context = owner._z3, owner._z3_context
    minimum = int(getattr(domain, "min_items", 0) or 0)
    maximum = domain.effective_max_items if domain is not None else None
    if maximum is None and isinstance(value_hint, (list, tuple)):
        maximum = len(value_hint)
    if maximum is None:
        raise SolverError(f"array parameter {name!r} needs a finite maxItems domain")
    maximum = int(maximum)
    if maximum < minimum:
        raise SolverError(f"array parameter {name!r} has an empty length domain")
    base = f"udb_param_{_safe_name(name)}"
    length = z3.Int(f"{base}_length", ctx=context)
    prefix = domain.prefix_items[:maximum] if domain is not None else ()
    if domain is None:
        prefix = (None,) * maximum
    tail_domain = domain.additional_items if domain is not None else None
    domains = (*prefix,)
    # Small domains retain the quantifier-free encoding, including mixed tuples.
    if maximum <= MAX_EXPLICIT_ARRAY_ITEMS:
        domains = tuple(
            domain.domain_for_index(index) if domain is not None else None
            for index in range(maximum)
        )
        tail_domain = None
    items = tuple(
        _make_scalar(
            z3,
            _domain_kind(
                item_domain,
                value_hint[index]
                if isinstance(value_hint, (list, tuple)) and index < len(value_hint)
                else None,
            ),
            f"{base}_{index}",
            context,
        )
        for index, item_domain in enumerate(domains)
    )
    tail = None
    if tail_domain is not None and len(items) < maximum:
        kind = _domain_kind(tail_domain, None)
        if kind not in {"boolean", "integer", "string", "empty"}:
            raise SolverError(f"array parameter {name!r} has unsupported nested item domains")
        scalar = _make_scalar(z3, kind, f"{base}_sort", context)
        tail = z3.Array(f"{base}_items", z3.IntSort(context), scalar.sort())
    symbol = ArraySymbol(length, items, maximum, tail)
    owner._solver.add(length >= minimum, length <= maximum)
    for index, (item, item_domain) in enumerate(zip(items, domains, strict=True)):
        if item_domain is not None:
            if _domain_kind(item_domain, None) == "array":
                raise SolverError(f"array parameter {name!r} has unsupported nested item domains")
            owner._solver.add(
                z3.Implies(length > index, owner._domain_expression(item, item_domain))
            )
    if tail is not None:
        index = z3.Int(f"{base}_index", ctx=context)
        active = z3.And(index >= len(items), index < length)
        symbol.axioms.append(
            z3.ForAll(index, z3.Implies(active, owner._domain_expression(tail[index], tail_domain)))
        )
    if getattr(domain, "unique_items", False):
        for left, item in enumerate(items):
            for right in range(left + 1, len(items)):
                if item.sort() == items[right].sort():
                    owner._solver.add(z3.Implies(length > right, item != items[right]))
            if tail is not None and item.sort() == tail.range():
                symbol.axioms.append(z3.ForAll(index, z3.Implies(active, item != tail[index])))
        if tail is not None:
            other = z3.Int(f"{base}_other_index", ctx=context)
            symbol.axioms.append(
                z3.ForAll(
                    [index, other],
                    z3.Implies(
                        z3.And(active, other > index, other < length),
                        tail[index] != tail[other],
                    ),
                )
            )
            symbol.witness = _interval_witness(owner, symbol, tail_domain, base)
    for required in getattr(domain, "contains", ()):
        owner._solver.add(
            symbol.exists(
                owner, lambda item, required=required: owner._domain_expression(item, required)
            )
        )
    return symbol


def _interval_witness(owner: Any, symbol: ArraySymbol, domain: ParameterDomain, base: str) -> Any:
    """A sufficient SAT witness, never an additional restriction for UNSAT.

    Cyclic rotations give Z3 a compact injective model even for enormous bounded
    integer domains. An unsuccessful witness is discarded before solving the
    unrestricted quantified theory. The rotation proves the item-domain and
    uniqueness axioms analytically: all values are in the interval and no two
    indices less than its cardinality have the same residue.
    """
    if symbol.items or domain.kind != "integer" or domain.allowed_values is not None:
        return None
    if domain.excluded_values or domain.minimum is None or domain.maximum is None:
        return None
    lower = domain.minimum.value + (not domain.minimum.inclusive)
    upper = domain.maximum.value - (not domain.maximum.inclusive)
    if upper < lower:
        return None
    z3 = owner._z3
    index = z3.Int(f"{base}_witness_index", ctx=owner._z3_context)
    offset = z3.Int(f"{base}_witness_offset", ctx=owner._z3_context)
    return z3.Lambda(index, lower + (index + offset) % (upper - lower + 1))


@dataclass(slots=True)
class _WitnessModel:
    z3: Any
    model: Any
    substitutions: tuple[Any, ...]

    def eval(self, expression: Any, *, model_completion: bool = False) -> Any:
        concrete = self.z3.simplify(self.z3.substitute(expression, *self.substitutions))
        return self.model.eval(concrete, model_completion=model_completion)


def solve_witness(owner: Any, arrays: list[ArraySymbol]) -> Any:
    """Solve a constructive subset; only a verified SAT result may be used."""
    substitutions = tuple(
        (symbol.tail, symbol.witness) for symbol in arrays if symbol.witness is not None
    )
    if not substitutions:
        return None
    z3 = owner._z3
    candidate = z3.Solver(ctx=owner._z3_context)
    candidate.set(rlimit=MAX_ARRAY_WITNESS_RESOURCES)
    expressions = [
        *owner._solver.assertions(),
        *(axiom for symbol in arrays if symbol.witness is None for axiom in symbol.axioms),
    ]
    candidate.add(
        *(z3.simplify(z3.substitute(expression, *substitutions)) for expression in expressions)
    )
    # assert_and_track exposes implications in assertions(); re-enable their
    # assumptions in this independent witness solver.
    candidate.add(*(z3.Bool(tag, ctx=owner._z3_context) for tag in owner._labels))
    if candidate.check() == z3.sat:
        return _WitnessModel(z3, candidate.model(), substitutions)
    return None


def materializable_model(owner: Any, assertions: tuple[Any, ...]) -> Any:
    """Find a small model of the last actual query without changing its theory."""
    from .solver import SolverUnknownError

    z3 = owner._z3
    arrays = [
        symbol for symbol in owner._parameter_symbols.values() if isinstance(symbol, ArraySymbol)
    ]
    candidate = z3.Solver(ctx=owner._z3_context)
    candidate.set(rlimit=MAX_INDEXED_SOLVER_RESOURCES)
    candidate.add(
        *assertions,
        *(axiom for symbol in arrays for axiom in symbol.axioms),
        *(symbol.length <= MAX_MATERIALIZED_ARRAY_ITEMS for symbol in arrays),
        *(z3.Bool(tag, ctx=owner._z3_context) for tag in owner._labels),
    )
    result = candidate.check()
    if result == z3.sat:
        return candidate.model()
    if result == z3.unknown:
        raise SolverUnknownError(
            "the solver could not decide whether a materializable model exists"
        )
    return None
