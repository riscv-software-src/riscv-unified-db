# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Z3-backed solving for UDB condition expressions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from itertools import product
from types import MappingProxyType
from typing import Any

from .conditions import (
    AllOf,
    AnyOf,
    Condition,
    EvaluationContext,
    ExactlyOne,
    ExtensionTerm,
    FreeTerm,
    Implies,
    NoneOf,
    Not,
    ParameterOperator,
    ParameterTerm,
    TruthValue,
    UnresolvedIdlCondition,
    XlenTerm,
    parse_condition,
)
from .domains import (
    ArrayDomain,
    EnumerationLimitError,
    InfiniteDomainError,
    ParameterDomain,
)
from .solver_arrays import (
    MAX_INDEXED_SOLVER_RESOURCES,
    make_array,
    materializable_model,
    solve_witness,
)
from .solver_arrays import (
    MAX_MATERIALIZED_ARRAY_ITEMS as _MAX_MATERIALIZED_ARRAY_ITEMS,
)
from .solver_arrays import (
    ArraySymbol as _ArraySymbol,
)
from .versions import ExtensionVersionSet, Version


class SolverError(RuntimeError):
    """A condition cannot be represented by the configured solver context."""


class SolverUnknownError(SolverError):
    """A Boolean query is unresolved or cannot be decided by the solver."""


class SolverStatus(str, Enum):
    SAT = "sat"
    UNSAT = "unsat"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SolverContext:
    """Architecture-specific domains and concrete choices for one solver."""

    extension_versions: Mapping[str, ExtensionVersionSet | Sequence[Version | str]] = field(
        default_factory=dict
    )
    parameter_domains: Mapping[str, ParameterDomain] = field(default_factory=dict)
    fixed_extensions: Mapping[str, Version | str | None] = field(default_factory=dict)
    fixed_parameters: Mapping[str, Any] = field(default_factory=dict)
    fixed_free_terms: Mapping[str, bool] = field(default_factory=dict)
    xlen: int | None = None
    strict_extension_catalog: bool = True

    def __post_init__(self) -> None:
        if self.xlen not in (None, 32, 64):
            raise SolverError(f"XLEN must be 32, 64, or unknown; got {self.xlen!r}")
        if not all(isinstance(value, bool) for value in self.fixed_free_terms.values()):
            raise SolverError("fixed free-term values must be Boolean")
        for name, fixed in self.fixed_extensions.items():
            catalog = self.extension_versions.get(name)
            if catalog is None:
                if fixed is not None and self.strict_extension_catalog:
                    raise SolverError(f"fixed extension {name!r} has no version catalog")
                continue
            if fixed is not None:
                known = {_version_text(candidate) for candidate in _catalog_versions(catalog)}
                fixed_text = str(Version.coerce(fixed))
                if fixed_text not in known:
                    raise SolverError(f"fixed extension {name} has unknown version {fixed_text}")
        for name in (
            "extension_versions",
            "parameter_domains",
            "fixed_extensions",
            "fixed_parameters",
            "fixed_free_terms",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


@dataclass(frozen=True, slots=True)
class ConditionModel:
    xlen: int | None
    extensions: Mapping[str, str | None]
    parameters: Mapping[str, Any]
    free_terms: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "extensions", MappingProxyType(dict(self.extensions)))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "free_terms", MappingProxyType(dict(self.free_terms)))


class ConditionSolver:
    """An isolated incremental solver with labeled constraints and exact models.

    Indexed arrays do not allocate their maximum length. Quantified array
    solver attempts have deterministic resource budgets and may return UNKNOWN;
    Boolean helpers then raise SolverUnknownError. Model extraction retries an
    oversized witness against the original query with concrete lengths <=4096.
    If this is impossible it raises SolverError, without truncation. If the retry
    is undecidable it raises SolverUnknownError. These model-only bounds never
    restrict subsequent satisfiability queries.
    """

    def __init__(self, context: SolverContext | None = None) -> None:
        try:
            import z3  # type: ignore[import-not-found]
        except ImportError as error:  # pragma: no cover - exercised in artifact tests
            raise SolverError("condition solving requires the 'z3-solver' package") from error
        self._z3 = z3
        self._z3_context = z3.Context()
        self.context = context or SolverContext()
        self._solver = z3.Solver(ctx=self._z3_context)
        self._constraints: list[tuple[Condition, str | None]] = []
        self._labels: dict[str, str] = {}
        self._extension_symbols: dict[tuple[str, str], Any] = {}
        self._extension_catalogs: dict[str, tuple[Any, ...]] = {}
        self._uncataloged_extension_symbols: dict[str, Any] = {}
        self._parameter_symbols: dict[str, Any] = {}
        self._free_symbols: dict[str, Any] = {}
        self._unresolved_idl_symbols: dict[UnresolvedIdlCondition, Any] = {}
        self._base_has_unresolved = False
        self._xlen = z3.Int("udb_xlen", ctx=self._z3_context)
        self._solver.add(z3.Or(self._xlen == 32, self._xlen == 64))
        if self.context.xlen is not None:
            self._solver.add(self._xlen == self.context.xlen)
        self._last_status: SolverStatus | None = None
        self._last_model: Any = None
        self._last_assertions: tuple[Any, ...] = ()
        self._last_core: tuple[str, ...] = ()
        self._initialize_extensions()
        self._initialize_fixed_parameters()
        self._initialize_fixed_free_terms()

    def add(
        self, condition: Condition | bool | Mapping[str, Any], label: str | None = None
    ) -> None:
        parsed = parse_condition(condition)
        expression = self._encode(parsed)
        self._constraints.append((parsed, label))
        self._base_has_unresolved |= parsed.has_unresolved
        self._last_status = None
        self._last_model = None
        self._last_assertions = ()
        self._last_core = ()
        if label is None:
            self._solver.add(expression)
            return
        tag = f"udb_constraint_{len(self._labels)}"
        self._labels[tag] = label
        self._solver.assert_and_track(expression, self._z3.Bool(tag, ctx=self._z3_context))

    def check(
        self,
        extra: Iterable[Condition | bool | Mapping[str, Any]] = (),
    ) -> SolverStatus:
        parsed_extra = [parse_condition(condition) for condition in extra]
        expressions = [self._encode(condition) for condition in parsed_extra]
        has_unresolved = self._base_has_unresolved or any(
            condition.has_unresolved for condition in parsed_extra
        )
        self._solver.push()
        try:
            self._solver.add(*expressions)
            result, result_model, result_core = self._solve()
            if result == self._z3.sat:
                if has_unresolved:
                    definite = [
                        self._encode_truth_pair(condition)[0] for condition, _ in self._constraints
                    ]
                    definite.extend(
                        self._encode_truth_pair(condition)[0] for condition in parsed_extra
                    )
                    self._solver.push()
                    try:
                        self._solver.add(*definite)
                        definite_result, definite_model, _ = self._solve()
                        self._last_status = (
                            SolverStatus.SAT
                            if definite_result == self._z3.sat
                            else SolverStatus.UNKNOWN
                        )
                        self._last_model = (
                            definite_model if self._last_status is SolverStatus.SAT else None
                        )
                        self._last_assertions = (
                            tuple(self._solver.assertions())
                            if self._last_status is SolverStatus.SAT
                            else ()
                        )
                    finally:
                        self._solver.pop()
                else:
                    self._last_status = SolverStatus.SAT
                    self._last_model = result_model
                    self._last_assertions = tuple(self._solver.assertions())
                self._last_core = ()
            elif result == self._z3.unsat:
                self._last_status = SolverStatus.UNSAT
                self._last_model = None
                self._last_assertions = ()
                self._last_core = tuple(
                    self._labels.get(str(item), str(item)) for item in result_core
                )
            else:
                self._last_status = SolverStatus.UNKNOWN
                self._last_model = None
                self._last_assertions = ()
                self._last_core = ()
            return self._last_status
        finally:
            self._solver.pop()

    def _solve(self) -> tuple[Any, Any, tuple[Any, ...]]:
        """Try compact exact witnesses, falling back to the unrestricted theory."""
        arrays = [
            symbol
            for symbol in self._parameter_symbols.values()
            if isinstance(symbol, _ArraySymbol)
        ]
        indexed = any(symbol.tail is not None for symbol in arrays)
        self._solver.set(rlimit=MAX_INDEXED_SOLVER_RESOURCES if indexed else 0)
        witness_model = solve_witness(self, arrays)
        if witness_model is not None:
            return self._z3.sat, witness_model, ()
        self._solver.push()
        try:
            self._solver.add(*(axiom for symbol in arrays for axiom in symbol.axioms))
            result = self._solver.check()
            return (
                result,
                self._solver.model() if result == self._z3.sat else None,
                tuple(self._solver.unsat_core()) if result == self._z3.unsat else (),
            )
        finally:
            self._solver.pop()

    def satisfiable(
        self,
        *extra: Condition | bool | Mapping[str, Any],
    ) -> bool:
        status = self.check(extra)
        if status is SolverStatus.UNKNOWN:
            raise SolverUnknownError(
                "satisfiability is unresolved or the solver could not decide the theory"
            )
        return status is SolverStatus.SAT

    def model(self) -> ConditionModel:
        if self._last_status is not SolverStatus.SAT or self._last_model is None:
            raise SolverError("a model is available only after a satisfiable check")
        model = self._last_model
        if any(
            isinstance(symbol, _ArraySymbol)
            and model.eval(symbol.length, model_completion=True).as_long()
            > _MAX_MATERIALIZED_ARRAY_ITEMS
            for symbol in self._parameter_symbols.values()
        ):
            smaller_model = materializable_model(self, self._last_assertions)
            if smaller_model is not None:
                self._last_model = model = smaller_model
        xlen_value = model.eval(self._xlen, model_completion=True).as_long()
        extensions: dict[str, str | None] = {}
        for name, versions in self._extension_catalogs.items():
            selected = None
            for candidate in versions:
                symbol = self._extension_symbols[(name, _version_text(candidate))]
                if self._z3.is_true(model.eval(symbol, model_completion=True)):
                    selected = _version_text(candidate)
                    break
            extensions[name] = selected
        parameters = {
            name: self._model_value(symbol, model)
            for name, symbol in self._parameter_symbols.items()
        }
        free_terms = {
            name: self._z3.is_true(model.eval(symbol, model_completion=True))
            for name, symbol in self._free_symbols.items()
        }
        return ConditionModel(xlen_value, extensions, parameters, free_terms)

    def unsat_core(self) -> tuple[str, ...]:
        if self._last_status is not SolverStatus.UNSAT:
            raise SolverError("an unsat core is available only after an unsatisfiable check")
        return self._last_core

    def minimal_conflict(self) -> tuple[str, ...]:
        """Return a deterministic deletion-minimal subset of labeled constraints."""

        background = [(condition, None) for condition, label in self._constraints if label is None]
        labeled = [
            (condition, label) for condition, label in self._constraints if label is not None
        ]
        if not labeled:
            return ()
        active = list(labeled)
        if _check_constraints(self.context, background) is SolverStatus.UNSAT:
            return ()
        if _check_constraints(self.context, [*background, *active]) is not SolverStatus.UNSAT:
            return ()
        index = 0
        while index < len(active):
            candidate = active[:index] + active[index + 1 :]
            if _check_constraints(self.context, [*background, *candidate]) is SolverStatus.UNSAT:
                active = candidate
            else:
                index += 1
        return tuple(label for _, label in active if label is not None)

    def _initialize_extensions(self) -> None:
        z3 = self._z3
        for name, catalog in self.context.extension_versions.items():
            versions = _catalog_versions(catalog)
            self._extension_catalogs[name] = versions
            symbols = []
            for candidate in versions:
                text = _version_text(candidate)
                symbol = z3.Bool(
                    f"udb_ext_{_safe_name(name)}_{_safe_name(text)}",
                    ctx=self._z3_context,
                )
                self._extension_symbols[(name, text)] = symbol
                symbols.append(symbol)
            if len(symbols) > 1:
                self._solver.add(z3.AtMost(*symbols, 1))
            if name in self.context.fixed_extensions:
                fixed = self.context.fixed_extensions[name]
                if fixed is None:
                    self._solver.add(
                        z3.Not(z3.Or(*symbols))
                        if symbols
                        else z3.BoolVal(True, ctx=self._z3_context)
                    )
                else:
                    fixed_text = str(Version.coerce(fixed))
                    try:
                        self._solver.add(self._extension_symbols[(name, fixed_text)])
                    except KeyError as error:
                        raise SolverError(
                            f"fixed extension {name} has unknown version {fixed_text}"
                        ) from error

    def _initialize_fixed_parameters(self) -> None:
        for name, value in self.context.fixed_parameters.items():
            symbol = self._parameter_symbol(name, value_hint=value)
            self._solver.add(self._equals(symbol, value))

    def _initialize_fixed_free_terms(self) -> None:
        for name, value in self.context.fixed_free_terms.items():
            if not isinstance(value, bool):
                raise SolverError(f"fixed free term {name!r} must be Boolean")
            symbol = self._free_symbol(name)
            self._solver.add(symbol == value)

    def _encode(self, condition: Condition) -> Any:
        z3 = self._z3
        from .conditions import ConstantCondition

        if isinstance(condition, ConstantCondition):
            return z3.BoolVal(condition.value, ctx=self._z3_context)
        if isinstance(condition, AllOf):
            return self._and(*(self._encode(child) for child in condition.children))
        if isinstance(condition, AnyOf):
            return self._or(*(self._encode(child) for child in condition.children))
        if isinstance(condition, ExactlyOne):
            children = [self._encode(child) for child in condition.children]
            if not children:
                return z3.BoolVal(False, ctx=self._z3_context)
            return z3.PbEq([(child, 1) for child in children], 1)
        if isinstance(condition, NoneOf):
            return z3.Not(self._or(*(self._encode(child) for child in condition.children)))
        if isinstance(condition, Not):
            return z3.Not(self._encode(condition.child))
        if isinstance(condition, Implies):
            return z3.Implies(
                self._encode(condition.antecedent), self._encode(condition.consequent)
            )
        if isinstance(condition, XlenTerm):
            return self._xlen == condition.value
        if isinstance(condition, FreeTerm):
            return self._free_symbol(condition.name)
        if isinstance(condition, ExtensionTerm):
            return self._encode_extension(condition)
        if isinstance(condition, ParameterTerm):
            return self._encode_parameter(condition)
        if isinstance(condition, UnresolvedIdlCondition):
            return self._unresolved_idl_symbols.setdefault(
                condition,
                z3.Bool(
                    f"udb_unresolved_idl_{len(self._unresolved_idl_symbols)}",
                    ctx=self._z3_context,
                ),
            )
        raise SolverError(f"unsupported condition node {type(condition).__name__}")

    def _encode_truth_pair(self, condition: Condition) -> tuple[Any, Any]:
        """Encode when a three-valued condition is definitely true or false."""

        z3 = self._z3
        from .conditions import ConstantCondition

        if isinstance(condition, ConstantCondition):
            value = z3.BoolVal(condition.value, ctx=self._z3_context)
            return value, z3.Not(value)
        if isinstance(condition, UnresolvedIdlCondition):
            impossible = z3.BoolVal(False, ctx=self._z3_context)
            return impossible, impossible
        if isinstance(condition, Not):
            child_true, child_false = self._encode_truth_pair(condition.child)
            return child_false, child_true
        if isinstance(condition, Implies):
            left_true, left_false = self._encode_truth_pair(condition.antecedent)
            right_true, right_false = self._encode_truth_pair(condition.consequent)
            return self._or(left_false, right_true), self._and(left_true, right_false)
        if isinstance(condition, AllOf):
            pairs = [self._encode_truth_pair(child) for child in condition.children]
            return self._and(*(pair[0] for pair in pairs)), self._or(*(pair[1] for pair in pairs))
        if isinstance(condition, AnyOf):
            pairs = [self._encode_truth_pair(child) for child in condition.children]
            return self._or(*(pair[0] for pair in pairs)), self._and(*(pair[1] for pair in pairs))
        if isinstance(condition, NoneOf):
            pairs = [self._encode_truth_pair(child) for child in condition.children]
            return self._and(*(pair[1] for pair in pairs)), self._or(*(pair[0] for pair in pairs))
        if isinstance(condition, ExactlyOne):
            pairs = [self._encode_truth_pair(child) for child in condition.children]
            if not pairs:
                impossible = z3.BoolVal(False, ctx=self._z3_context)
                return impossible, z3.BoolVal(True, ctx=self._z3_context)
            definitely_true = self._or(
                *(
                    self._and(
                        pair[0],
                        *(
                            other[1]
                            for other_index, other in enumerate(pairs)
                            if other_index != index
                        ),
                    )
                    for index, pair in enumerate(pairs)
                )
            )
            at_least_two_true = (
                z3.PbGe([(pair[0], 1) for pair in pairs], 2)
                if len(pairs) >= 2
                else z3.BoolVal(False, ctx=self._z3_context)
            )
            definitely_false = self._or(at_least_two_true, self._and(*(pair[1] for pair in pairs)))
            return definitely_true, definitely_false
        expression = self._encode(condition)
        return expression, z3.Not(expression)

    def _free_symbol(self, name: str) -> Any:
        return self._free_symbols.setdefault(
            name,
            self._z3.Bool(f"udb_free_{_safe_name(name)}", ctx=self._z3_context),
        )

    def _encode_extension(self, term: ExtensionTerm) -> Any:
        z3 = self._z3
        catalog = self.context.extension_versions.get(term.name)
        if catalog is None:
            if self.context.strict_extension_catalog:
                raise SolverError(f"no version catalog for extension {term.name!r}")
            if len(term.requirements) != 1 or str(term.requirements[0]) != ">= 0.0.0":
                raise SolverError(
                    f"uncataloged extension {term.name!r} cannot evaluate version requirements"
                )
            return self._uncataloged_extension_symbols.setdefault(
                term.name,
                z3.Bool(
                    f"udb_ext_{_safe_name(term.name)}_uncataloged",
                    ctx=self._z3_context,
                ),
            )
        versions = self._extension_catalogs[term.name]
        matches = []
        for candidate in versions:
            candidate_version = getattr(candidate, "version", candidate)
            try:
                satisfies = all(
                    requirement.matches(
                        candidate_version,
                        versions=catalog if isinstance(catalog, ExtensionVersionSet) else None,
                    )
                    for requirement in term.requirements
                )
            except ValueError as error:
                raise SolverError(
                    f"extension {term.name!r} uses a compatibility requirement without "
                    "ExtensionVersionSet metadata"
                ) from error
            if satisfies:
                matches.append(self._extension_symbols[(term.name, _version_text(candidate))])
        return self._or(*matches)

    def _encode_parameter(self, term: ParameterTerm) -> Any:
        z3 = self._z3
        value_hint = term.value
        if (
            term.operator is ParameterOperator.ONE_OF
            and term.name not in self.context.parameter_domains
        ):
            value_hint = _one_of_scalar_hint(term.value)
        symbol = self._parameter_symbol(term.name, value_hint=value_hint)
        selected = symbol
        if term.index is not None:
            if not isinstance(symbol, _ArraySymbol):
                raise SolverError(f"parameter {term.name!r} is not an array")
            if term.index >= symbol.maximum:
                return z3.BoolVal(False, ctx=self._z3_context)
            selected = symbol.item(z3, term.index)
            in_range = symbol.length > term.index
        elif term.size:
            if not isinstance(symbol, _ArraySymbol):
                raise SolverError(f"parameter {term.name!r} is not an array")
            selected = symbol.length
            in_range = z3.BoolVal(True, ctx=self._z3_context)
        elif term.bit_range is not None:
            if isinstance(symbol, _ArraySymbol):
                raise SolverError(f"parameter {term.name!r} is not an integer")
            msb, lsb = term.bit_range
            selected = (symbol / (2**lsb)) % (2 ** (msb - lsb + 1))
            in_range = z3.BoolVal(True, ctx=self._z3_context)
        else:
            in_range = z3.BoolVal(True, ctx=self._z3_context)

        if term.operator is ParameterOperator.INCLUDES:
            if not isinstance(symbol, _ArraySymbol):
                raise SolverError(f"parameter {term.name!r} is not an array")
            comparison = symbol.exists(self, lambda item: self._scalar_equals(item, term.value))
        elif term.operator is ParameterOperator.ONE_OF:
            comparison = self._or(*(self._equals(selected, value) for value in term.value))
        elif term.operator is ParameterOperator.EQUAL:
            comparison = self._equals(selected, term.value)
        elif term.operator is ParameterOperator.NOT_EQUAL:
            comparison = z3.Not(self._equals(selected, term.value))
        elif term.operator is ParameterOperator.LESS_THAN:
            comparison = self._ordered_comparison(selected, term.value, "<")
        elif term.operator is ParameterOperator.GREATER_THAN:
            comparison = self._ordered_comparison(selected, term.value, ">")
        elif term.operator is ParameterOperator.LESS_THAN_OR_EQUAL:
            comparison = self._ordered_comparison(selected, term.value, "<=")
        elif term.operator is ParameterOperator.GREATER_THAN_OR_EQUAL:
            comparison = self._ordered_comparison(selected, term.value, ">=")
        else:  # pragma: no cover - exhaustive enum guard
            raise AssertionError(term.operator)
        return z3.And(in_range, comparison)

    def _parameter_symbol(self, name: str, value_hint: Any = None) -> Any:
        if name in self._parameter_symbols:
            return self._parameter_symbols[name]
        domain = self.context.parameter_domains.get(name)
        kind = _domain_kind(domain, value_hint)
        if kind == "array":
            symbol = self._array_symbol(name, domain, value_hint)
        elif kind == "boolean":
            symbol = self._z3.Bool(f"udb_param_{_safe_name(name)}", ctx=self._z3_context)
        elif kind == "string":
            symbol = self._z3.String(f"udb_param_{_safe_name(name)}", ctx=self._z3_context)
        else:
            symbol = self._z3.Int(f"udb_param_{_safe_name(name)}", ctx=self._z3_context)
        self._parameter_symbols[name] = symbol
        if domain is not None:
            self._constrain_domain(symbol, domain)
        if name == "MXLEN" and not isinstance(symbol, _ArraySymbol):
            self._solver.add(self._xlen <= symbol)
        return symbol

    def _array_symbol(self, name: str, domain: ArrayDomain | None, value_hint: Any) -> _ArraySymbol:
        return make_array(self, name, domain, value_hint)

    def _constrain_domain(self, symbol: Any, domain: Any) -> None:
        if isinstance(symbol, _ArraySymbol):
            return
        self._solver.add(self._domain_expression(symbol, domain))

    def _domain_expression(self, symbol: Any, domain: Any) -> Any:
        if getattr(domain, "is_empty", False):
            return self._z3.BoolVal(False, ctx=self._z3_context)
        expected_kind = _domain_kind(domain, None)
        if expected_kind != "empty" and expected_kind != _symbol_kind(self._z3, symbol):
            return self._z3.BoolVal(False, ctx=self._z3_context)
        clauses = []
        allowed = getattr(domain, "allowed_values", None)
        if allowed is not None:
            choices = tuple(self._scalar_equals(symbol, value) for value in allowed)
            clauses.append(self._or(*choices))
        minimum = getattr(domain, "minimum", None)
        if minimum is not None:
            value = getattr(minimum, "value", minimum)
            clauses.append(
                symbol >= value if getattr(minimum, "inclusive", True) else symbol > value
            )
        maximum = getattr(domain, "maximum", None)
        if maximum is not None:
            value = getattr(maximum, "value", maximum)
            clauses.append(
                symbol <= value if getattr(maximum, "inclusive", True) else symbol < value
            )
        clauses.extend(
            self._z3.Not(self._scalar_equals(symbol, value))
            for value in getattr(domain, "excluded_values", ())
        )
        return self._and(*clauses)

    def _equals(self, symbol: Any, value: Any) -> Any:
        if isinstance(symbol, _ArraySymbol):
            if not isinstance(value, (tuple, list)):
                return self._z3.BoolVal(False, ctx=self._z3_context)
            if len(value) > symbol.maximum:
                return self._z3.BoolVal(False, ctx=self._z3_context)
            return self._z3.And(
                symbol.length == len(value),
                *(
                    self._scalar_equals(symbol.item(self._z3, index), item)
                    for index, item in enumerate(value)
                ),
            )
        return self._scalar_equals(symbol, value)

    def _scalar_equals(self, symbol: Any, value: Any) -> Any:
        if _value_kind(value) != _symbol_kind(self._z3, symbol):
            return self._z3.BoolVal(False, ctx=self._z3_context)
        return symbol == _z3_value(self._z3, value, self._z3_context)

    def _ordered_comparison(self, symbol: Any, value: Any, operator: str) -> Any:
        if isinstance(symbol, _ArraySymbol) or _symbol_kind(self._z3, symbol) != "integer":
            return self._z3.BoolVal(False, ctx=self._z3_context)
        if _value_kind(value) != "integer":
            return self._z3.BoolVal(False, ctx=self._z3_context)
        return {
            "<": symbol < value,
            ">": symbol > value,
            "<=": symbol <= value,
            ">=": symbol >= value,
        }[operator]

    def _and(self, *expressions: Any) -> Any:
        if not expressions:
            return self._z3.BoolVal(True, ctx=self._z3_context)
        return self._z3.And(*expressions)

    def _or(self, *expressions: Any) -> Any:
        if not expressions:
            return self._z3.BoolVal(False, ctx=self._z3_context)
        return self._z3.Or(*expressions)

    def _model_value(self, symbol: Any, model: Any) -> Any:
        if isinstance(symbol, _ArraySymbol):
            length = model.eval(symbol.length, model_completion=True).as_long()
            if length > _MAX_MATERIALIZED_ARRAY_ITEMS:
                raise SolverError(
                    f"array model length {length} exceeds the solver limit of "
                    f"{_MAX_MATERIALIZED_ARRAY_ITEMS} concrete items"
                )
            return tuple(
                self._model_value(symbol.item(self._z3, index), model) for index in range(length)
            )
        value = model.eval(symbol, model_completion=True)
        if self._z3.is_true(value):
            return True
        if self._z3.is_false(value):
            return False
        if self._z3.is_int_value(value):
            return value.as_long()
        if self._z3.is_string_value(value):
            return value.as_string()
        return str(value)


def is_satisfiable(
    condition: Condition | bool | Mapping[str, Any], context: SolverContext | None = None
) -> bool:
    finite_status = finite_check(condition, context)
    if finite_status is not None:
        if finite_status is SolverStatus.UNKNOWN:
            raise SolverUnknownError("satisfiability depends on an unresolved condition")
        return finite_status is SolverStatus.SAT
    solver = ConditionSolver(context)
    solver.add(condition)
    return solver.satisfiable()


def implies(
    antecedent: Condition | bool | Mapping[str, Any],
    consequent: Condition | bool | Mapping[str, Any],
    context: SolverContext | None = None,
) -> bool:
    from .conditions import all_of, negate

    counterexample = all_of(antecedent, negate(consequent))
    finite_status = finite_check(counterexample, context)
    if finite_status is not None:
        if finite_status is SolverStatus.UNKNOWN:
            solver = ConditionSolver(context)
            solver.add(counterexample)
            status = solver.check()
            if status is SolverStatus.UNKNOWN:
                raise SolverUnknownError("implication depends on an unresolved condition")
            return status is SolverStatus.UNSAT
        return finite_status is SolverStatus.UNSAT
    solver = ConditionSolver(context)
    solver.add(counterexample)
    status = solver.check()
    if status is SolverStatus.UNKNOWN:
        raise SolverUnknownError("implication depends on an unresolved condition")
    return status is SolverStatus.UNSAT


def equivalent(
    left: Condition | bool | Mapping[str, Any],
    right: Condition | bool | Mapping[str, Any],
    context: SolverContext | None = None,
) -> bool:
    from .conditions import all_of, any_of, negate

    difference = any_of(all_of(left, negate(right)), all_of(negate(left), right))
    finite_status = finite_check(difference, context)
    if finite_status is not None:
        if finite_status is SolverStatus.UNKNOWN:
            solver = ConditionSolver(context)
            solver.add(difference)
            status = solver.check()
            if status is SolverStatus.UNKNOWN:
                raise SolverUnknownError("equivalence depends on an unresolved condition")
            return status is SolverStatus.UNSAT
        return finite_status is SolverStatus.UNSAT
    solver = ConditionSolver(context)
    solver.add(difference)
    status = solver.check()
    if status is SolverStatus.UNKNOWN:
        raise SolverUnknownError("equivalence depends on an unresolved condition")
    return status is SolverStatus.UNSAT


def finite_check(
    condition: Condition | bool | Mapping[str, Any],
    context: SolverContext | None = None,
    *,
    max_cases: int = 4096,
) -> SolverStatus | None:
    """Decide a small finite condition without importing or initializing Z3.

    ``None`` means that a required domain is missing, infinite, or would make
    the finite product exceed ``max_cases``. Unresolved IDL produces
    :attr:`SolverStatus.UNKNOWN` unless another term makes an assignment true
    or every assignment false independently of the unresolved value.
    """

    if max_cases < 1:
        raise ValueError("max_cases must be positive")
    parsed = parse_condition(condition)
    solver_context = context or SolverContext()
    for name, fixed in solver_context.fixed_parameters.items():
        domain = solver_context.parameter_domains.get(name)
        if domain is not None and not domain.accepts(fixed):
            return SolverStatus.UNSAT
    extension_names: set[str] = set()
    parameter_names: set[str] = set()
    free_names: set[str] = set()
    needs_xlen = _collect_terms(
        parsed,
        extension_names=extension_names,
        parameter_names=parameter_names,
        free_names=free_names,
    )
    dimensions: list[tuple[str, str, tuple[Any, ...]]] = []

    if needs_xlen or "MXLEN" in solver_context.fixed_parameters:
        xlens = (solver_context.xlen,) if solver_context.xlen is not None else (32, 64)
        dimensions.append(("xlen", "xlen", xlens))

    for name in sorted(extension_names):
        if name in solver_context.fixed_extensions:
            fixed = solver_context.fixed_extensions[name]
            catalog = solver_context.extension_versions.get(name)
            if fixed is not None and catalog is not None:
                known = {_version_text(candidate) for candidate in _catalog_versions(catalog)}
                if str(Version.coerce(fixed)) not in known:
                    return None
            values = (fixed,)
        else:
            catalog = solver_context.extension_versions.get(name)
            if catalog is None:
                return None
            values = (None, *(getattr(candidate, "version", candidate) for candidate in catalog))
        dimensions.append(("extension", name, values))

    for name in sorted(parameter_names):
        domain = solver_context.parameter_domains.get(name)
        if name in solver_context.fixed_parameters:
            fixed = solver_context.fixed_parameters[name]
            if domain is not None and not domain.accepts(fixed):
                return SolverStatus.UNSAT
            values = (fixed,)
        else:
            if domain is None or not domain.is_finite:
                return None
            try:
                values = domain.enumerate_values(limit=max_cases)
            except (EnumerationLimitError, InfiniteDomainError):
                return None
        if not values:
            return SolverStatus.UNSAT
        dimensions.append(("parameter", name, values))

    for name in sorted(free_names):
        if name in solver_context.fixed_free_terms:
            values = (solver_context.fixed_free_terms[name],)
        else:
            values = (False, True)
        dimensions.append(("free", name, values))

    case_count = 1
    for _, _, values in dimensions:
        case_count *= len(values)
        if case_count > max_cases:
            return None

    saw_unknown = False
    choices = (values for _, _, values in dimensions)
    assignments = product(*choices) if dimensions else ((),)
    version_sets = {
        name: catalog
        for name, catalog in solver_context.extension_versions.items()
        if isinstance(catalog, ExtensionVersionSet)
    }
    for assignment in assignments:
        extensions: dict[str, Version | str] = {}
        parameters: dict[str, Any] = {}
        free_terms: dict[str, bool] = {}
        xlen = solver_context.xlen
        for (kind, name, _), value in zip(dimensions, assignment, strict=True):
            if kind == "xlen":
                xlen = value
            elif kind == "extension" and value is not None:
                extensions[name] = value
            elif kind == "parameter":
                parameters[name] = value
            elif kind == "free":
                free_terms[name] = value
        mxlen = parameters.get("MXLEN", solver_context.fixed_parameters.get("MXLEN"))
        if (
            xlen is not None
            and isinstance(mxlen, int)
            and not isinstance(mxlen, bool)
            and xlen > mxlen
        ):
            continue
        value = parsed.evaluate(
            EvaluationContext(
                extensions=extensions,
                parameters=parameters,
                free_terms=free_terms,
                xlen=xlen,
                version_sets=version_sets,
                closed_world_extensions=True,
                closed_world_parameters=True,
                closed_world_free_terms=True,
            )
        )
        if value is TruthValue.TRUE:
            return SolverStatus.SAT
        if value is TruthValue.UNKNOWN:
            saw_unknown = True
    return SolverStatus.UNKNOWN if saw_unknown else SolverStatus.UNSAT


def _collect_terms(
    condition: Condition,
    *,
    extension_names: set[str],
    parameter_names: set[str],
    free_names: set[str],
) -> bool:
    if isinstance(condition, ExtensionTerm):
        extension_names.add(condition.name)
        return False
    if isinstance(condition, ParameterTerm):
        parameter_names.add(condition.name)
        return False
    if isinstance(condition, FreeTerm):
        free_names.add(condition.name)
        return False
    if isinstance(condition, XlenTerm):
        return True
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
        has_xlen = False
        for child in condition.children:
            has_xlen |= _collect_terms(
                child,
                extension_names=extension_names,
                parameter_names=parameter_names,
                free_names=free_names,
            )
        return has_xlen
    if isinstance(condition, Not):
        return _collect_terms(
            condition.child,
            extension_names=extension_names,
            parameter_names=parameter_names,
            free_names=free_names,
        )
    if isinstance(condition, Implies):
        left = _collect_terms(
            condition.antecedent,
            extension_names=extension_names,
            parameter_names=parameter_names,
            free_names=free_names,
        )
        right = _collect_terms(
            condition.consequent,
            extension_names=extension_names,
            parameter_names=parameter_names,
            free_names=free_names,
        )
        return left or right
    return False


def _check_constraints(
    context: SolverContext,
    constraints: Sequence[tuple[Condition, str | None]],
) -> SolverStatus:
    solver = ConditionSolver(context)
    for condition, label in constraints:
        solver.add(condition, label)
    return solver.check()


def _catalog_versions(catalog: ExtensionVersionSet | Sequence[Version | str]) -> tuple[Any, ...]:
    for attribute in ("versions", "all_versions", "entries"):
        value = getattr(catalog, attribute, None)
        if value is not None:
            return tuple(value)
    if isinstance(catalog, Sequence):
        return tuple(catalog)
    try:
        return tuple(catalog)  # type: ignore[arg-type]
    except TypeError as error:
        raise SolverError("extension version catalog is not iterable") from error


def _version_text(candidate: Any) -> str:
    version = getattr(candidate, "version", candidate)
    return str(Version.coerce(version))


def _domain_kind(domain: Any, value_hint: Any) -> str:
    if domain is not None:
        kind = getattr(domain, "kind", None)
        if kind is not None:
            return str(getattr(kind, "value", kind)).lower()
    if isinstance(value_hint, bool):
        return "boolean"
    if isinstance(value_hint, str):
        return "string"
    if isinstance(value_hint, (tuple, list)):
        return "array"
    return "integer"


def _one_of_scalar_hint(values: Any) -> bool | int | float | str:
    if not isinstance(values, tuple) or len(values) < 2:
        raise SolverError("parameter oneOf needs at least two values")
    kinds = {_value_kind(value) for value in values}
    if len(kinds) != 1 or not kinds <= {"boolean", "integer", "string"}:
        raise SolverError(
            "unconstrained parameter oneOf needs homogeneous scalar Boolean, integer, or string "
            "choices"
        )
    return values[0]


def _make_scalar(z3: Any, kind: str, name: str, context: Any = None) -> Any:
    if kind == "boolean":
        return z3.Bool(name, ctx=context)
    if kind == "string":
        return z3.String(name, ctx=context)
    return z3.Int(name, ctx=context)


def _symbol_kind(z3: Any, symbol: Any) -> str:
    if z3.is_bool(symbol):
        return "boolean"
    if z3.is_int(symbol):
        return "integer"
    if symbol.sort().kind() == z3.Z3_SEQ_SORT:
        return "string"
    raise SolverError(f"unsupported Z3 parameter sort {symbol.sort()}")


def _value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    return "unsupported"


def _z3_value(z3: Any, value: Any, context: Any = None) -> Any:
    if isinstance(value, bool):
        return z3.BoolVal(value, ctx=context)
    if isinstance(value, int):
        return z3.IntVal(value, ctx=context)
    if isinstance(value, float) and value.is_integer():
        return z3.IntVal(int(value), ctx=context)
    if isinstance(value, str):
        return z3.StringVal(value, ctx=context)
    raise SolverError(f"unsupported scalar value {value!r}")


def _safe_name(value: str) -> str:
    return value.encode("utf-8").hex()


__all__ = [
    "ConditionModel",
    "ConditionSolver",
    "SolverContext",
    "SolverError",
    "SolverStatus",
    "SolverUnknownError",
    "equivalent",
    "finite_check",
    "implies",
    "is_satisfiable",
]
