# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable parameter domains derived from the UDB JSON Schemas."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import product
from math import isfinite
from types import MappingProxyType
from typing import Any, ClassVar

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError as JsonSchemaError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT7

from .errors import DataError
from .schema import _BASE_URI, SchemaStore

DomainValue = bool | int | str | tuple["DomainValue", ...]

_ANNOTATIONS = {
    "$comment",
    "$defs",
    "$id",
    "$schema",
    "default",
    "definitions",
    "description",
    "examples",
    "readOnly",
    "title",
    "writeOnly",
}
_COMMON_KEYWORDS = _ANNOTATIONS | {"$ref", "allOf", "const", "enum", "not", "type"}
_SCALAR_KEYWORDS = _COMMON_KEYWORDS | {
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maximum",
    "minimum",
}
_ARRAY_KEYWORDS = _COMMON_KEYWORDS | {
    "additionalItems",
    "contains",
    "items",
    "maxItems",
    "minItems",
    "uniqueItems",
}
_ARRAY_ANALYSIS_MAX_ITEMS = 64
_ARRAY_ANALYSIS_MAX_CONTAINS = 12
_ARRAY_ANALYSIS_MAX_STATES = 100_000
_ENUMERATION_BASE_WORK = 10_000
_ENUMERATION_WORK_PER_RESULT = 1_000


class DomainError(DataError):
    """A parameter schema cannot be represented as a supported domain."""


class UnsupportedDomainError(DomainError):
    """A valid JSON Schema uses constraints outside the parameter-domain subset."""


class EnumerationLimitError(DomainError):
    """Complete finite-domain enumeration would exceed the caller's limit."""


class InfiniteDomainError(DomainError):
    """A caller requested complete enumeration of an infinite domain."""


class NotSingletonError(DomainError):
    """A caller requested the value of a domain that is not a singleton."""


class DomainKind(StrEnum):
    """Kinds of parameter values supported by UDB."""

    EMPTY = "empty"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"
    ARRAY = "array"


@dataclass(frozen=True, slots=True)
class Bound:
    """One integer-domain endpoint."""

    value: int
    inclusive: bool = True

    def __post_init__(self) -> None:
        if not _is_integer(self.value):
            raise DomainError(f"Integer bound must be an integer, not {self.value!r}")
        object.__setattr__(self, "value", int(self.value))


@dataclass(frozen=True, slots=True)
class ParameterDomain:
    """Base class for an immutable parameter value domain.

    Use :meth:`from_schema` rather than constructing a concrete domain directly.
    """

    schema: Mapping[str, Any] = field(repr=False)
    source: str = "<parameter schema>"
    _schema_store: SchemaStore | None = field(default=None, repr=False, compare=False)
    _expanded_schema: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)

    kind: ClassVar[DomainKind]

    def __post_init__(self) -> None:
        if not isinstance(self.schema, Mapping):
            raise DomainError("Parameter domain schema must be a mapping")
        if not isinstance(self.source, str) or not self.source:
            raise DomainError("Parameter domain source must be a non-empty string")
        if self._schema_store is not None and not isinstance(self._schema_store, SchemaStore):
            raise DomainError("Parameter domain schema store must be a SchemaStore")
        object.__setattr__(self, "schema", _freeze_schema(self.schema, source=self.source))
        expanded = self.schema if self._expanded_schema is None else self._expanded_schema
        object.__setattr__(
            self,
            "_expanded_schema",
            _freeze_schema(expanded, source=f"{self.source} expanded schema"),
        )

    @classmethod
    def from_schema(
        cls,
        schema: Mapping[str, Any],
        *,
        schema_store: SchemaStore | None = None,
        source: str = "<parameter schema>",
    ) -> ParameterDomain:
        """Create a domain from a supported Draft 7 schema fragment.

        References are resolved only through the explicitly supplied offline
        :class:`~udb.schema.SchemaStore`.
        """

        if cls is not ParameterDomain:
            raise TypeError("ParameterDomain.from_schema() must be called on ParameterDomain")
        frozen = _freeze_schema(schema, source=source)
        plain = _thaw(frozen)
        try:
            Draft7Validator.check_schema(plain)
        except JsonSchemaError as error:
            raise DomainError(
                f"{source}: invalid Draft 7 parameter schema: {error.message}"
            ) from error
        resolver, rooted = _root_resolver(plain, schema_store=schema_store, source=source)
        expanded = _materialize_schema(rooted, resolver, source=source)
        return _DomainParser(
            frozen,
            expanded_schema=_freeze_schema(expanded, source=f"{source} expanded schema"),
            schema_store=schema_store,
            source=source,
        ).parse()

    def accepts(self, value: object) -> bool:
        """Return whether *value* belongs to this domain."""

        raise NotImplementedError

    def __contains__(self, value: object) -> bool:
        return self.accepts(value)

    def intersection(self, other: ParameterDomain) -> ParameterDomain:
        """Return the exact conjunction of this domain and *other*."""

        if not isinstance(other, ParameterDomain):
            return NotImplemented
        if (
            self._schema_store is not None
            and other._schema_store is not None
            and self._schema_store is not other._schema_store
        ):
            raise DomainError("Cannot intersect domains backed by different SchemaStore instances")
        store = self._schema_store or other._schema_store
        schema = {"allOf": [_thaw(self.schema), _thaw(other.schema)]}
        expanded = {"allOf": [_thaw(self._expanded_schema), _thaw(other._expanded_schema)]}
        return _DomainParser(
            schema,
            expanded_schema=expanded,
            schema_store=store,
            source=f"intersection of {self.source} and {other.source}",
        ).parse()

    def __and__(self, other: ParameterDomain) -> ParameterDomain:
        return self.intersection(other)

    @property
    def is_empty(self) -> bool:
        """Whether the domain provably contains no values."""

        raise NotImplementedError

    @property
    def is_finite(self) -> bool:
        """Whether the domain contains finitely many values."""

        raise NotImplementedError

    @property
    def cardinality(self) -> int | None:
        """Return an inexpensive exact size, or ``None`` when not cheaply known.

        Use :attr:`is_finite` to distinguish an infinite domain from a finite
        domain whose enormous cardinality is intentionally not materialized.
        """

        raise NotImplementedError

    def enumerate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        """Return every value, raising rather than truncating at *limit*."""

        if not _is_python_int(limit) or limit < 0:
            raise ValueError("Enumeration limit must be a non-negative integer")
        if not self.is_finite:
            raise InfiniteDomainError(f"{self.source}: {self.kind} domain is infinite")
        values: list[DomainValue] = []
        for value in self._iter_values(limit=limit):
            if len(values) == limit:
                raise EnumerationLimitError(
                    f"{self.source}: domain contains more than {limit} values"
                )
            values.append(value)
        return tuple(values)

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        raise NotImplementedError

    def _candidate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        """Return up to *limit* deterministic members for internal witness search."""

        if limit <= 0:
            return ()
        try:
            return self.enumerate_values(limit=limit)
        except EnumerationLimitError:
            values: list[DomainValue] = []
            for value in self._iter_values(limit=limit):
                values.append(value)
                if len(values) == limit:
                    break
            return tuple(values)

    @property
    def is_singleton(self) -> bool:
        """Whether the domain contains exactly one value."""

        if not self.is_finite:
            return False
        try:
            return len(self.enumerate_values(limit=1)) == 1
        except EnumerationLimitError:
            return False

    @property
    def single_value(self) -> DomainValue:
        """Return the sole member, or raise :class:`NotSingletonError`."""

        if not self.is_singleton:
            raise NotSingletonError(f"{self.source}: domain is not a singleton")
        return self.enumerate_values(limit=1)[0]


@dataclass(frozen=True, slots=True)
class EmptyDomain(ParameterDomain):
    """The result of contradictory domain constraints."""

    kind: ClassVar[DomainKind] = DomainKind.EMPTY

    def accepts(self, value: object) -> bool:
        return False

    @property
    def is_empty(self) -> bool:
        return True

    @property
    def is_finite(self) -> bool:
        return True

    @property
    def cardinality(self) -> int:
        return 0

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        return
        yield  # pragma: no cover

    def _candidate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class BooleanDomain(ParameterDomain):
    """A Boolean domain, possibly restricted by ``enum`` or ``const``."""

    allowed_values: tuple[bool, ...] = (False, True)
    kind: ClassVar[DomainKind] = DomainKind.BOOLEAN

    def __post_init__(self) -> None:
        ParameterDomain.__post_init__(self)
        values = _tuple_field(self.allowed_values, "allowed_values", self.source)
        if any(not isinstance(value, bool) for value in values):
            raise DomainError(f"{self.source}: Boolean allowed_values must contain Booleans")
        object.__setattr__(self, "allowed_values", tuple(dict.fromkeys(values)))

    def accepts(self, value: object) -> bool:
        return isinstance(value, bool) and value in self.allowed_values

    @property
    def is_empty(self) -> bool:
        return not self.allowed_values

    @property
    def is_finite(self) -> bool:
        return True

    @property
    def cardinality(self) -> int:
        return len(self.allowed_values)

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        yield from self.allowed_values

    def _candidate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        return self.allowed_values[:limit]


@dataclass(frozen=True, slots=True)
class IntegerDomain(ParameterDomain):
    """An integer domain with normalized bounds and value restrictions."""

    minimum: Bound | None = None
    maximum: Bound | None = None
    allowed_values: tuple[int, ...] | None = None
    excluded_values: tuple[int, ...] = ()
    kind: ClassVar[DomainKind] = DomainKind.INTEGER

    def __post_init__(self) -> None:
        ParameterDomain.__post_init__(self)
        if self.minimum is not None and not isinstance(self.minimum, Bound):
            raise DomainError(f"{self.source}: integer minimum must be a Bound")
        if self.maximum is not None and not isinstance(self.maximum, Bound):
            raise DomainError(f"{self.source}: integer maximum must be a Bound")
        allowed = (
            None
            if self.allowed_values is None
            else tuple(
                _as_integer(value, source=self.source)
                for value in _tuple_field(self.allowed_values, "allowed_values", self.source)
            )
        )
        excluded = tuple(
            _as_integer(value, source=self.source)
            for value in _tuple_field(self.excluded_values, "excluded_values", self.source)
        )
        object.__setattr__(
            self, "allowed_values", None if allowed is None else _deduplicate(allowed)
        )
        object.__setattr__(self, "excluded_values", _deduplicate(excluded))

    def accepts(self, value: object) -> bool:
        if not _is_integer(value):
            return False
        normalized = int(value)
        if not _within_bounds(normalized, self.minimum, self.maximum):
            return False
        if self.allowed_values is not None and normalized not in self.allowed_values:
            return False
        return normalized not in self.excluded_values

    @property
    def is_empty(self) -> bool:
        if self.allowed_values is not None:
            return not any(self.accepts(value) for value in self.allowed_values)
        endpoints = _effective_integer_endpoints(self.minimum, self.maximum)
        if endpoints is None:
            return False
        low, high = endpoints
        if low > high:
            return True
        return high - low + 1 <= len(
            {value for value in self.excluded_values if low <= value <= high}
        )

    @property
    def is_finite(self) -> bool:
        return self.allowed_values is not None or (
            self.minimum is not None and self.maximum is not None
        )

    @property
    def cardinality(self) -> int | None:
        if self.allowed_values is not None:
            return sum(self.accepts(value) for value in self.allowed_values)
        endpoints = _effective_integer_endpoints(self.minimum, self.maximum)
        if endpoints is None:
            return None
        low, high = endpoints
        if low > high:
            return 0
        excluded = {value for value in self.excluded_values if low <= value <= high}
        return high - low + 1 - len(excluded)

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        if self.allowed_values is not None:
            yield from (value for value in self.allowed_values if self.accepts(value))
            return
        endpoints = _effective_integer_endpoints(self.minimum, self.maximum)
        assert endpoints is not None
        low, high = endpoints
        if high >= low and high - low + 1 - len(self.excluded_values) > limit:
            raise EnumerationLimitError(f"{self.source}: domain contains more than {limit} values")
        for value in range(low, high + 1):
            if value not in self.excluded_values:
                yield value

    def _candidate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        if limit <= 0:
            return ()
        if self.allowed_values is not None:
            return tuple(value for value in self.allowed_values if self.accepts(value))[:limit]
        if self.is_empty:
            return ()
        if self.minimum is not None:
            value = self.minimum.value + (not self.minimum.inclusive)
            step = 1
        elif self.maximum is not None:
            value = self.maximum.value - (not self.maximum.inclusive)
            step = -1
        else:
            value = 0
            step = 1
        values: list[int] = []
        while len(values) < limit:
            if self.accepts(value):
                values.append(value)
            value += step
            if not _within_bounds(value, self.minimum, self.maximum):
                break
        return tuple(values)


@dataclass(frozen=True, slots=True)
class StringDomain(ParameterDomain):
    """A string domain, unrestricted or constrained to explicit values."""

    allowed_values: tuple[str, ...] | None = None
    excluded_values: tuple[str, ...] = ()
    kind: ClassVar[DomainKind] = DomainKind.STRING

    def __post_init__(self) -> None:
        ParameterDomain.__post_init__(self)
        allowed = (
            None
            if self.allowed_values is None
            else _tuple_field(self.allowed_values, "allowed_values", self.source)
        )
        excluded = _tuple_field(self.excluded_values, "excluded_values", self.source)
        if allowed is not None and any(not isinstance(value, str) for value in allowed):
            raise DomainError(f"{self.source}: string allowed_values must contain strings")
        if any(not isinstance(value, str) for value in excluded):
            raise DomainError(f"{self.source}: string excluded_values must contain strings")
        object.__setattr__(
            self, "allowed_values", None if allowed is None else _deduplicate(allowed)
        )
        object.__setattr__(self, "excluded_values", _deduplicate(excluded))

    def accepts(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        if self.allowed_values is not None and value not in self.allowed_values:
            return False
        return value not in self.excluded_values

    @property
    def is_empty(self) -> bool:
        return self.allowed_values is not None and not any(
            self.accepts(value) for value in self.allowed_values
        )

    @property
    def is_finite(self) -> bool:
        return self.allowed_values is not None

    @property
    def cardinality(self) -> int | None:
        if self.allowed_values is None:
            return None
        return sum(self.accepts(value) for value in self.allowed_values)

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        assert self.allowed_values is not None
        yield from (value for value in self.allowed_values if self.accepts(value))

    def _candidate_values(self, *, limit: int) -> tuple[DomainValue, ...]:
        if self.allowed_values is not None:
            return tuple(value for value in self.allowed_values if self.accepts(value))[:limit]
        values: list[str] = []
        index = 0
        while len(values) < limit:
            value = "" if index == 0 else f"__udb_domain_candidate_{index}"
            if self.accepts(value):
                values.append(value)
            index += 1
        return tuple(values)


@dataclass(frozen=True, slots=True)
class ArrayDomain(ParameterDomain):
    """A bounded or unbounded array domain with typed item domains."""

    min_items: int = 0
    max_items: int | None = None
    item_domain: ParameterDomain | None = None
    prefix_items: tuple[ParameterDomain, ...] = ()
    additional_items: ParameterDomain | None = None
    contains: tuple[ParameterDomain, ...] = ()
    unique_items: bool = False
    kind: ClassVar[DomainKind] = DomainKind.ARRAY

    def __post_init__(self) -> None:
        ParameterDomain.__post_init__(self)
        if not _is_python_int(self.min_items) or self.min_items < 0:
            raise DomainError(f"{self.source}: min_items must be a non-negative integer")
        if self.max_items is not None and (
            not _is_python_int(self.max_items) or self.max_items < 0
        ):
            raise DomainError(f"{self.source}: max_items must be a non-negative integer or None")
        prefix = _tuple_field(self.prefix_items, "prefix_items", self.source)
        contains = _tuple_field(self.contains, "contains", self.source)
        domain_fields = (*prefix, *contains)
        if self.item_domain is not None:
            domain_fields = (*domain_fields, self.item_domain)
        if self.additional_items is not None:
            domain_fields = (*domain_fields, self.additional_items)
        if any(not isinstance(domain, ParameterDomain) for domain in domain_fields):
            raise DomainError(f"{self.source}: array item constraints must be parameter domains")
        if not isinstance(self.unique_items, bool):
            raise DomainError(f"{self.source}: unique_items must be Boolean")
        if prefix and self.item_domain is not None:
            raise DomainError(f"{self.source}: tuple arrays cannot also have item_domain")
        if not prefix and self.item_domain != self.additional_items:
            raise DomainError(
                f"{self.source}: uniform array item_domain must equal additional_items"
            )
        object.__setattr__(self, "prefix_items", prefix)
        object.__setattr__(self, "contains", contains)

    def accepts(self, value: object) -> bool:
        if not isinstance(value, list | tuple):
            return False
        if len(value) < self.min_items:
            return False
        if self.max_items is not None and len(value) > self.max_items:
            return False
        for index, item in enumerate(value):
            domain = self.domain_for_index(index)
            if domain is None or not domain.accepts(item):
                return False
        if self.unique_items and len({_json_key(item) for item in value}) != len(value):
            return False
        return all(any(required.accepts(item) for item in value) for required in self.contains)

    @property
    def effective_max_items(self) -> int | None:
        """Maximum realizable length after tuple ``additionalItems`` handling."""

        maximum = self.max_items
        for index, item in enumerate(self.prefix_items):
            if item.is_empty:
                maximum = index if maximum is None else min(maximum, index)
                break
        else:
            if self.additional_items is None or self.additional_items.is_empty:
                tuple_max = len(self.prefix_items)
                maximum = tuple_max if maximum is None else min(maximum, tuple_max)

        if self.unique_items:
            domains = list(self.prefix_items)
            if self.additional_items is not None:
                domains.append(self.additional_items)
            cardinalities = [domain.cardinality for domain in domains if not domain.is_empty]
            if cardinalities and all(value is not None for value in cardinalities):
                unique_max = sum(value for value in cardinalities if value is not None)
                maximum = unique_max if maximum is None else min(maximum, unique_max)
        return maximum

    def domain_for_index(self, index: int) -> ParameterDomain | None:
        """Return the item domain at *index*, or ``None`` if it is prohibited."""

        if not _is_python_int(index) or index < 0:
            raise IndexError("Array domain index must be a non-negative integer")
        if index < len(self.prefix_items):
            return self.prefix_items[index]
        return self.additional_items

    @property
    def is_empty(self) -> bool:
        maximum = self.effective_max_items
        if maximum is not None and self.min_items > maximum:
            return True
        if not self._length_has_nonempty_items(self.min_items):
            return True
        if self.min_items == 0 and not self.contains:
            return False
        if not self.contains and not self.unique_items:
            return False
        if not self.contains and not self.prefix_items and self.additional_items is not None:
            cardinality = self.additional_items.cardinality
            return cardinality is not None and cardinality < self.min_items
        if any(not self._contains_can_match(required) for required in self.contains):
            return True

        if len(self.contains) > _ARRAY_ANALYSIS_MAX_CONTAINS:
            raise UnsupportedDomainError(
                f"{self.source}: exact emptiness analysis supports at most "
                f"{_ARRAY_ANALYSIS_MAX_CONTAINS} contains constraints"
            )
        search_max = max(
            self.min_items,
            self.min_items + len(self.contains),
            len(self.prefix_items),
            len(self.prefix_items) + len(self.contains),
        )
        if maximum is not None:
            search_max = min(search_max, maximum)
        if search_max > _ARRAY_ANALYSIS_MAX_ITEMS:
            raise UnsupportedDomainError(
                f"{self.source}: exact uniqueItems/contains emptiness analysis supports "
                f"arrays up to {_ARRAY_ANALYSIS_MAX_ITEMS} items"
            )
        return not any(
            self._has_value_at_length(length) for length in range(self.min_items, search_max + 1)
        )

    @property
    def is_finite(self) -> bool:
        maximum = self.effective_max_items
        if maximum is None:
            return False
        if maximum == 0:
            return True
        prefix_limit = min(maximum, len(self.prefix_items))
        if any(not domain.is_finite for domain in self.prefix_items[:prefix_limit]):
            return False
        return not (
            maximum > len(self.prefix_items)
            and self.additional_items is not None
            and not self.additional_items.is_finite
        )

    @property
    def cardinality(self) -> int | None:
        if not self.is_finite:
            return None
        try:
            return sum(1 for _ in self._iter_candidate_values(limit=10_000))
        except EnumerationLimitError:
            return None

    def _iter_values(self, *, limit: int) -> Iterator[DomainValue]:
        yield from self._iter_candidate_values(limit=limit)

    def _iter_candidate_values(self, *, limit: int) -> Iterator[DomainValue]:
        maximum = self.effective_max_items
        if maximum is None:
            raise InfiniteDomainError(f"{self.source}: array domain is infinite")

        yielded = 0
        work = 0
        work_limit = _ENUMERATION_BASE_WORK + _ENUMERATION_WORK_PER_RESULT * (limit + 1)
        for length in range(self.min_items, maximum + 1):
            work += length + 1
            if work > work_limit:
                raise EnumerationLimitError(
                    f"{self.source}: complete array enumeration exceeded its bounded work "
                    f"for limit {limit}"
                )
            domains = [self.domain_for_index(index) for index in range(length)]
            if any(domain is None or domain.is_empty for domain in domains):
                continue
            item_values: list[tuple[DomainValue, ...]] = []
            for domain in domains:
                assert domain is not None
                cardinality = domain.cardinality
                if not domain.is_finite:
                    raise InfiniteDomainError(
                        f"{self.source}: array item domain at index {len(item_values)} is infinite"
                    )
                if cardinality is None or work + cardinality > work_limit:
                    raise EnumerationLimitError(
                        f"{self.source}: complete array enumeration exceeded its bounded work "
                        f"for limit {limit}"
                    )
                work += cardinality
                item_values.append(domain.enumerate_values(limit=cardinality))
            for value in product(*item_values):
                work += 1
                if work > work_limit:
                    raise EnumerationLimitError(
                        f"{self.source}: complete array enumeration exceeded its bounded work "
                        f"for limit {limit}"
                    )
                if not self.accepts(value):
                    continue
                if yielded == limit:
                    raise EnumerationLimitError(
                        f"{self.source}: domain contains more than {limit} values"
                    )
                yielded += 1
                yield value

    def _contains_can_match(self, required: ParameterDomain) -> bool:
        maximum = self.effective_max_items
        if maximum == 0:
            return False
        prefix_limit = (
            len(self.prefix_items) if maximum is None else min(len(self.prefix_items), maximum)
        )
        for item in self.prefix_items[:prefix_limit]:
            if not item.intersection(required).is_empty:
                return True
        if maximum is not None and maximum <= len(self.prefix_items):
            return False
        return (
            self.additional_items is not None
            and not self.additional_items.intersection(required).is_empty
        )

    def _length_has_nonempty_items(self, length: int) -> bool:
        prefix_limit = min(length, len(self.prefix_items))
        if any(item.is_empty for item in self.prefix_items[:prefix_limit]):
            return False
        return not (
            length > len(self.prefix_items)
            and (self.additional_items is None or self.additional_items.is_empty)
        )

    def _has_value_at_length(self, length: int) -> bool:
        if not self._length_has_nonempty_items(length):
            return False
        domains = [self.domain_for_index(index) for index in range(length)]
        assert all(domain is not None for domain in domains)
        candidate_count = length + len(self.contains) + 1
        candidates_by_index: list[tuple[DomainValue, ...]] = []
        for domain in domains:
            assert domain is not None
            candidates = list(domain._candidate_values(limit=candidate_count))
            for required in self.contains:
                overlap = domain.intersection(required)
                for value in overlap._candidate_values(limit=1):
                    if not _contains_json(candidates, value):
                        candidates.append(value)
            candidates_by_index.append(tuple(candidates))

        required_mask = (1 << len(self.contains)) - 1
        visited: set[tuple[int, frozenset[Any], int]] = set()

        def search(index: int, used: frozenset[Any], matched: int) -> bool:
            state = (index, used, matched)
            if state in visited:
                return False
            if len(visited) == _ARRAY_ANALYSIS_MAX_STATES:
                raise UnsupportedDomainError(
                    f"{self.source}: exact array emptiness analysis exceeded "
                    f"{_ARRAY_ANALYSIS_MAX_STATES} states"
                )
            visited.add(state)
            if index == length:
                return matched == required_mask
            for value in candidates_by_index[index]:
                key = _json_key(value)
                if self.unique_items and key in used:
                    continue
                next_matched = matched
                for required_index, required in enumerate(self.contains):
                    if required.accepts(value):
                        next_matched |= 1 << required_index
                next_used = used | {key} if self.unique_items else used
                if search(index + 1, next_used, next_matched):
                    return True
            return False

        return search(0, frozenset(), 0)


class _DomainParser:
    def __init__(
        self,
        schema: Mapping[str, Any],
        *,
        expanded_schema: Mapping[str, Any] | None = None,
        schema_store: SchemaStore | None,
        source: str,
    ) -> None:
        self.schema = _freeze_schema(schema, source=source)
        self.expanded_schema = (
            self.schema
            if expanded_schema is None
            else _freeze_schema(expanded_schema, source=f"{source} expanded schema")
        )
        self.schema_store = schema_store
        self.source = source

    def parse(self) -> ParameterDomain:
        atoms = tuple(self._flatten(self.expanded_schema))
        kinds = {_schema_kind(atom, source=self.source) for atom in atoms}
        kinds.discard(None)
        if len(kinds) > 1:
            return self._empty()
        if not kinds:
            raise UnsupportedDomainError(f"{self.source}: cannot infer parameter type from schema")
        kind = kinds.pop()
        self._check_keywords(atoms, kind)
        if kind is DomainKind.BOOLEAN:
            return self._boolean(atoms)
        if kind is DomainKind.INTEGER:
            return self._integer(atoms)
        if kind is DomainKind.STRING:
            return self._string(atoms)
        assert kind is DomainKind.ARRAY
        return self._array(atoms)

    def _flatten(self, schema: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
        siblings = {key: value for key, value in schema.items() if key != "allOf"}
        if any(key not in _ANNOTATIONS for key in siblings):
            yield siblings
        all_of = schema.get("allOf", ())
        if not isinstance(all_of, Sequence) or isinstance(all_of, str | bytes):
            raise DomainError(f"{self.source}: 'allOf' must be an array of schemas")
        for index, subschema in enumerate(all_of):
            if not isinstance(subschema, Mapping):
                raise DomainError(f"{self.source}: allOf[{index}] must be a schema object")
            yield from self._flatten(subschema)

    def _check_keywords(self, atoms: tuple[Mapping[str, Any], ...], kind: DomainKind) -> None:
        allowed = _ARRAY_KEYWORDS if kind is DomainKind.ARRAY else _SCALAR_KEYWORDS
        for atom in atoms:
            unsupported = sorted(set(atom) - allowed)
            if unsupported:
                joined = ", ".join(repr(keyword) for keyword in unsupported)
                raise UnsupportedDomainError(
                    f"{self.source}: unsupported {kind} domain keyword(s): {joined}"
                )

    def _boolean(self, atoms: tuple[Mapping[str, Any], ...]) -> ParameterDomain:
        allowed: tuple[bool, ...] = (False, True)
        excluded: list[bool] = []
        for atom in atoms:
            allowed = _restrict_values(allowed, atom, DomainKind.BOOLEAN, self.source)
            excluded.extend(_excluded_values(atom, DomainKind.BOOLEAN, self.source))
        allowed = tuple(value for value in allowed if value not in excluded)
        if not allowed:
            return self._empty()
        return BooleanDomain(
            schema=self.schema,
            source=self.source,
            _schema_store=self.schema_store,
            _expanded_schema=self.expanded_schema,
            allowed_values=allowed,
        )

    def _integer(self, atoms: tuple[Mapping[str, Any], ...]) -> ParameterDomain:
        allowed: tuple[int, ...] | None = None
        excluded: list[int] = []
        minimum: Bound | None = None
        maximum: Bound | None = None
        for atom in atoms:
            allowed = _merge_allowed_values(allowed, atom, DomainKind.INTEGER, source=self.source)
            excluded.extend(_excluded_values(atom, DomainKind.INTEGER, self.source))
            if "minimum" in atom:
                minimum = _stronger_minimum(
                    minimum, Bound(_integer_keyword(atom["minimum"], "minimum", self.source))
                )
            if "exclusiveMinimum" in atom:
                minimum = _stronger_minimum(
                    minimum,
                    Bound(
                        _integer_keyword(atom["exclusiveMinimum"], "exclusiveMinimum", self.source),
                        inclusive=False,
                    ),
                )
            if "maximum" in atom:
                maximum = _stronger_maximum(
                    maximum, Bound(_integer_keyword(atom["maximum"], "maximum", self.source))
                )
            if "exclusiveMaximum" in atom:
                maximum = _stronger_maximum(
                    maximum,
                    Bound(
                        _integer_keyword(atom["exclusiveMaximum"], "exclusiveMaximum", self.source),
                        inclusive=False,
                    ),
                )
        domain = IntegerDomain(
            schema=self.schema,
            source=self.source,
            _schema_store=self.schema_store,
            _expanded_schema=self.expanded_schema,
            minimum=minimum,
            maximum=maximum,
            allowed_values=allowed,
            excluded_values=tuple(dict.fromkeys(excluded)),
        )
        if domain.is_empty:
            return self._empty()
        if allowed is not None:
            domain = IntegerDomain(
                schema=self.schema,
                source=self.source,
                _schema_store=self.schema_store,
                _expanded_schema=self.expanded_schema,
                minimum=minimum,
                maximum=maximum,
                allowed_values=tuple(value for value in allowed if domain.accepts(value)),
                excluded_values=(),
            )
        return domain

    def _string(self, atoms: tuple[Mapping[str, Any], ...]) -> ParameterDomain:
        allowed: tuple[str, ...] | None = None
        excluded: list[str] = []
        for atom in atoms:
            allowed = _merge_allowed_values(allowed, atom, DomainKind.STRING, source=self.source)
            excluded.extend(_excluded_values(atom, DomainKind.STRING, self.source))
        domain = StringDomain(
            schema=self.schema,
            source=self.source,
            _schema_store=self.schema_store,
            _expanded_schema=self.expanded_schema,
            allowed_values=allowed,
            excluded_values=tuple(dict.fromkeys(excluded)),
        )
        if domain.is_empty:
            return self._empty()
        if allowed is not None:
            domain = StringDomain(
                schema=self.schema,
                source=self.source,
                _schema_store=self.schema_store,
                _expanded_schema=self.expanded_schema,
                allowed_values=tuple(value for value in allowed if domain.accepts(value)),
                excluded_values=(),
            )
        return domain

    def _array(self, atoms: tuple[Mapping[str, Any], ...]) -> ParameterDomain:
        min_items = 0
        max_items: int | None = None
        unique_items = False
        item_rules: list[tuple[tuple[ParameterDomain, ...], ParameterDomain | None]] = []
        contains: list[ParameterDomain] = []

        for atom in atoms:
            if "enum" in atom or "const" in atom or "not" in atom:
                raise UnsupportedDomainError(
                    f"{self.source}: array enum, const, and not constraints are not supported"
                )
            if "minItems" in atom:
                min_items = max(
                    min_items, _non_negative_integer(atom["minItems"], "minItems", self.source)
                )
            if "maxItems" in atom:
                candidate = _non_negative_integer(atom["maxItems"], "maxItems", self.source)
                max_items = candidate if max_items is None else min(max_items, candidate)
            if atom.get("uniqueItems") is True:
                unique_items = True
            elif "uniqueItems" in atom and atom["uniqueItems"] is not False:
                raise DomainError(f"{self.source}: 'uniqueItems' must be Boolean")
            if "items" in atom:
                item_rules.append(self._item_rule(atom))
            if "contains" in atom:
                contains_schema = atom["contains"]
                if not isinstance(contains_schema, Mapping):
                    raise DomainError(f"{self.source}: 'contains' must be a schema object")
                contains.append(self._subdomain(contains_schema, "contains"))

        if not item_rules:
            raise UnsupportedDomainError(
                f"{self.source}: array domains require a typed 'items' schema"
            )
        prefix_size = max((len(prefix) for prefix, _ in item_rules), default=0)
        prefix_items: list[ParameterDomain] = []
        for index in range(prefix_size):
            domains = [
                prefix[index] if index < len(prefix) else additional
                for prefix, additional in item_rules
            ]
            if any(domain is None for domain in domains):
                prefix_items.append(self._empty())
            else:
                prefix_items.append(_intersect_domains(domain for domain in domains if domain))

        additional_domains = [additional for _, additional in item_rules]
        additional = (
            None
            if any(domain is None for domain in additional_domains)
            else _intersect_domains(domain for domain in additional_domains if domain)
        )
        item_domain = additional if not prefix_items else None
        domain = ArrayDomain(
            schema=self.schema,
            source=self.source,
            _schema_store=self.schema_store,
            _expanded_schema=self.expanded_schema,
            min_items=min_items,
            max_items=max_items,
            item_domain=item_domain,
            prefix_items=tuple(prefix_items),
            additional_items=additional,
            contains=tuple(contains),
            unique_items=unique_items,
        )
        if domain.is_empty:
            return self._empty()
        return domain

    def _empty(self) -> EmptyDomain:
        return EmptyDomain(
            schema=self.schema,
            source=self.source,
            _schema_store=self.schema_store,
            _expanded_schema=self.expanded_schema,
        )

    def _item_rule(
        self, atom: Mapping[str, Any]
    ) -> tuple[tuple[ParameterDomain, ...], ParameterDomain | None]:
        items = atom["items"]
        if isinstance(items, Mapping):
            domain = self._subdomain(items, "items")
            return (), domain
        if not isinstance(items, Sequence) or isinstance(items, str | bytes):
            raise DomainError(f"{self.source}: 'items' must be a schema or array of schemas")
        prefix = tuple(
            self._subdomain(item, f"items[{index}]")
            if isinstance(item, Mapping)
            else self._invalid_item(index)
            for index, item in enumerate(items)
        )
        additional_schema = atom.get("additionalItems", {})
        if additional_schema is False:
            additional = None
        elif additional_schema is True or additional_schema == {}:
            raise UnsupportedDomainError(
                f"{self.source}: unconstrained tuple additionalItems are not supported"
            )
        elif isinstance(additional_schema, Mapping):
            additional = self._subdomain(additional_schema, "additionalItems")
        else:
            raise DomainError(f"{self.source}: 'additionalItems' must be Boolean or a schema")
        return prefix, additional

    def _invalid_item(self, index: int) -> ParameterDomain:
        raise DomainError(f"{self.source}: items[{index}] must be a schema object")

    def _subdomain(self, schema: Mapping[str, Any], label: str) -> ParameterDomain:
        domain = _DomainParser(
            _freeze_schema(schema, source=f"{self.source} {label}"),
            expanded_schema=schema,
            schema_store=self.schema_store,
            source=f"{self.source} {label}",
        ).parse()
        if isinstance(domain, ArrayDomain):
            raise UnsupportedDomainError(
                f"{self.source}: nested array domain in {label} is not supported"
            )
        return domain


def _schema_kind(schema: Mapping[str, Any], *, source: str) -> DomainKind | None:
    declared = schema.get("type")
    if declared is not None:
        if not isinstance(declared, str):
            raise UnsupportedDomainError(f"{source}: union-valued 'type' is not supported")
        try:
            return DomainKind(declared)
        except ValueError as error:
            raise UnsupportedDomainError(
                f"{source}: unsupported parameter type {declared!r}"
            ) from error
    values: list[Any] = []
    if "const" in schema:
        values.append(schema["const"])
    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, Sequence) or isinstance(enum, str | bytes):
            raise DomainError(f"{source}: 'enum' must be an array")
        values.extend(enum)
    kinds = {_value_kind(value) for value in values}
    if len(kinds) > 1:
        raise UnsupportedDomainError(f"{source}: heterogeneous enum domains are not supported")
    if kinds:
        return kinds.pop()
    return None


def _value_kind(value: object) -> DomainKind:
    if isinstance(value, bool):
        return DomainKind.BOOLEAN
    if _is_integer(value):
        return DomainKind.INTEGER
    if isinstance(value, str):
        return DomainKind.STRING
    if isinstance(value, list | tuple):
        return DomainKind.ARRAY
    raise UnsupportedDomainError(f"Unsupported parameter value {value!r}")


def _restrict_values(
    current: tuple[Any, ...], schema: Mapping[str, Any], kind: DomainKind, source: str
) -> tuple[Any, ...]:
    restricted = _merge_allowed_values(current, schema, kind, source=source)
    assert restricted is not None
    return restricted


def _merge_allowed_values(
    current: tuple[Any, ...] | None,
    schema: Mapping[str, Any],
    kind: DomainKind,
    *,
    source: str,
) -> tuple[Any, ...] | None:
    candidate: tuple[Any, ...] | None = None
    if "const" in schema:
        value = schema["const"]
        candidate = (_normalize_value(value, kind),) if _matches_kind(value, kind) else ()
    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, Sequence) or isinstance(enum, str | bytes):
            raise DomainError(f"{source}: 'enum' must be an array")
        enum_values = tuple(
            _normalize_value(value, kind) for value in enum if _matches_kind(value, kind)
        )
        enum_values = _deduplicate(enum_values)
        candidate = (
            enum_values
            if candidate is None
            else tuple(value for value in candidate if _contains_json(enum_values, value))
        )
    if candidate is None:
        return current
    if current is None:
        return candidate
    return tuple(value for value in current if _contains_json(candidate, value))


def _excluded_values(schema: Mapping[str, Any], kind: DomainKind, source: str) -> tuple[Any, ...]:
    if "not" not in schema:
        return ()
    negated = schema["not"]
    if not isinstance(negated, Mapping):
        raise DomainError(f"{source}: 'not' must be a schema object")
    if set(negated) == {"const"}:
        value = negated["const"]
        return (_normalize_value(value, kind),) if _matches_kind(value, kind) else ()
    any_of = negated.get("anyOf")
    if set(negated) == {"anyOf"} and isinstance(any_of, Sequence):
        values: list[Any] = []
        for subschema in any_of:
            if not isinstance(subschema, Mapping) or set(subschema) != {"const"}:
                break
            value = subschema["const"]
            if _matches_kind(value, kind):
                values.append(_normalize_value(value, kind))
        else:
            return tuple(values)
    raise UnsupportedDomainError(
        f"{source}: only 'not' with const values is supported for parameter domains"
    )


def _normalize_value(value: Any, kind: DomainKind) -> Any:
    if kind is DomainKind.INTEGER:
        return int(value)
    if kind is DomainKind.ARRAY:
        return tuple(value)
    return value


def _matches_kind(value: Any, kind: DomainKind) -> bool:
    try:
        return _value_kind(value) is kind
    except UnsupportedDomainError:
        return False


def _intersect_domains(domains: Iterator[ParameterDomain]) -> ParameterDomain:
    iterator = iter(domains)
    try:
        result = next(iterator)
    except StopIteration as error:
        raise DomainError("Cannot intersect an empty collection of domains") from error
    for domain in iterator:
        result = result.intersection(domain)
    return result


def _stronger_minimum(left: Bound | None, right: Bound) -> Bound:
    if left is None or right.value > left.value:
        return right
    if right.value < left.value:
        return left
    return Bound(left.value, left.inclusive and right.inclusive)


def _stronger_maximum(left: Bound | None, right: Bound) -> Bound:
    if left is None or right.value < left.value:
        return right
    if right.value > left.value:
        return left
    return Bound(left.value, left.inclusive and right.inclusive)


def _within_bounds(value: int, minimum: Bound | None, maximum: Bound | None) -> bool:
    if minimum is not None and (
        value < minimum.value or (value == minimum.value and not minimum.inclusive)
    ):
        return False
    return not (
        maximum is not None
        and (value > maximum.value or (value == maximum.value and not maximum.inclusive))
    )


def _effective_integer_endpoints(
    minimum: Bound | None, maximum: Bound | None
) -> tuple[int, int] | None:
    if minimum is None or maximum is None:
        return None
    low = minimum.value + (not minimum.inclusive)
    high = maximum.value - (not maximum.inclusive)
    return low, high


def _integer_keyword(value: Any, keyword: str, source: str) -> int:
    if not _is_integer(value):
        raise UnsupportedDomainError(
            f"{source}: integer domain {keyword!r} must be an integer, not {value!r}"
        )
    return int(value)


def _non_negative_integer(value: Any, keyword: str, source: str) -> int:
    value = _integer_keyword(value, keyword, source)
    if value < 0:
        raise DomainError(f"{source}: {keyword!r} must be non-negative")
    return value


def _is_integer(value: object) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and isfinite(value) and value.is_integer()
    )


def _is_python_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_integer(value: object, *, source: str) -> int:
    if not _is_integer(value):
        raise DomainError(f"{source}: integer values must be integral numbers, not {value!r}")
    return int(value)


def _tuple_field(value: Any, field_name: str, source: str) -> tuple[Any, ...]:
    if isinstance(value, str | bytes):
        raise DomainError(f"{source}: {field_name} must be an iterable of values")
    try:
        return tuple(value)
    except TypeError as error:
        raise DomainError(f"{source}: {field_name} must be an iterable of values") from error


def _contains_json(values: Sequence[Any], wanted: Any) -> bool:
    key = _json_key(wanted)
    return any(_json_key(value) == key for value in values)


def _deduplicate(values: tuple[Any, ...]) -> tuple[Any, ...]:
    result: list[Any] = []
    keys: set[Any] = set()
    for value in values:
        key = _json_key(value)
        if key not in keys:
            keys.add(key)
            result.append(value)
    return tuple(result)


def _json_key(value: Any) -> Any:
    if isinstance(value, bool):
        return ("boolean", value)
    if _is_integer(value):
        return ("integer", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, list | tuple):
        return ("array", tuple(_json_key(item) for item in value))
    raise UnsupportedDomainError(f"Unsupported parameter value {value!r}")


def _root_resolver(
    schema: Mapping[str, Any], *, schema_store: SchemaStore | None, source: str
) -> tuple[Any, Mapping[str, Any]]:
    registry: Registry[Any]
    if schema_store is None:
        registry = Registry()
    else:
        schema_store._load()
        loaded = schema_store._registry
        assert loaded is not None
        registry = loaded
    rooted = _thaw(schema)
    if not isinstance(rooted.get("$id"), str):
        rooted["$id"] = f"{_BASE_URI}parameter-domain-root.json"
    try:
        resource = Resource.from_contents(rooted, default_specification=DRAFT7)
    except Exception as error:
        raise DomainError(
            f"{source}: cannot create a parameter schema resource: {error}"
        ) from error
    root_uri = rooted["$id"]
    registry = registry.with_resource(root_uri, resource)
    return registry.resolver(root_uri), resource.contents


def _materialize_schema(
    schema: Any,
    resolver: Any,
    *,
    source: str,
    active: frozenset[int] = frozenset(),
) -> Any:
    if isinstance(schema, Mapping):
        if "$ref" in schema:
            ref = schema["$ref"]
            if not isinstance(ref, str) or not ref:
                raise DomainError(f"{source}: '$ref' must be a non-empty string")
            try:
                resolved = resolver.lookup(ref)
            except Unresolvable as error:
                store_hint = (
                    " (a non-local reference requires an explicit SchemaStore)"
                    if not ref.startswith("#")
                    else ""
                )
                raise DomainError(
                    f"{source}: cannot resolve parameter schema reference {ref!r}{store_hint}: "
                    f"{error}"
                ) from error
            if not isinstance(resolved.contents, Mapping):
                raise DomainError(
                    f"{source}: parameter schema reference {ref!r} does not select an object"
                )
            identity = id(resolved.contents)
            if identity in active:
                raise DomainError(
                    f"{source}: cyclic parameter schema reference detected at {ref!r}"
                )
            return _materialize_schema(
                resolved.contents,
                resolved.resolver,
                source=source,
                active=active | {identity},
            )
        materialized: dict[str, Any] = {}
        for key, value in schema.items():
            if key in {"$defs", "definitions"}:
                materialized[key] = value
            else:
                materialized[key] = _materialize_schema(
                    value, resolver, source=source, active=active
                )
        return materialized
    if isinstance(schema, list | tuple):
        return [
            _materialize_schema(value, resolver, source=source, active=active) for value in schema
        ]
    return schema


def _freeze_schema(value: Any, *, source: str, _active: set[int] | None = None) -> Any:
    active = set() if _active is None else _active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise DomainError(f"{source}: recursive schema containers are not supported")
        active.add(identity)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise DomainError(f"{source}: schema keys must be strings, not {key!r}")
                frozen[key] = _freeze_schema(item, source=source, _active=active)
            return MappingProxyType(frozen)
        finally:
            active.remove(identity)
    if isinstance(value, list | tuple):
        identity = id(value)
        if identity in active:
            raise DomainError(f"{source}: recursive schema containers are not supported")
        active.add(identity)
        try:
            return tuple(_freeze_schema(item, source=source, _active=active) for item in value)
        finally:
            active.remove(identity)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise DomainError(f"{source}: schema value {value!r} is not JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "ArrayDomain",
    "BooleanDomain",
    "Bound",
    "DomainError",
    "DomainKind",
    "DomainValue",
    "EmptyDomain",
    "EnumerationLimitError",
    "InfiniteDomainError",
    "IntegerDomain",
    "NotSingletonError",
    "ParameterDomain",
    "StringDomain",
    "UnsupportedDomainError",
]
