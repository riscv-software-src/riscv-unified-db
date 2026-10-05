# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Immutable condition expressions and three-valued concrete evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from .errors import DataError
from .versions import ExtensionVersionSet, Version, VersionRequirement, parse_version_requirements


class ConditionError(DataError, ValueError):
    """A condition document is malformed or cannot be evaluated."""


class UnresolvedConditionError(ConditionError):
    """A condition needs the Stage 4 IDL compiler before it can be decided."""


class TruthValue(Enum):
    """Truth value used while evaluating a partially configured architecture."""

    FALSE = 0
    UNKNOWN = 1
    TRUE = 2

    def __bool__(self) -> bool:
        if self is TruthValue.UNKNOWN:
            raise TypeError("an unknown condition has no Boolean value")
        return self is TruthValue.TRUE

    def negate(self) -> TruthValue:
        if self is TruthValue.TRUE:
            return TruthValue.FALSE
        if self is TruthValue.FALSE:
            return TruthValue.TRUE
        return TruthValue.UNKNOWN


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Concrete values known while evaluating a condition.

    ``closed_world_extensions`` and ``closed_world_parameters`` distinguish a
    fully configured implementation (an omitted value is false) from a partial
    configuration (an omitted value is unknown).
    """

    extensions: Mapping[str, Version | str] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    free_terms: Mapping[str, bool] = field(default_factory=dict)
    xlen: int | None = None
    version_sets: Mapping[str, ExtensionVersionSet] = field(default_factory=dict)
    closed_world_extensions: bool = False
    closed_world_parameters: bool = False
    closed_world_free_terms: bool = False

    def __post_init__(self) -> None:
        if self.xlen not in (None, 32, 64):
            raise ConditionError(f"XLEN must be 32, 64, or unknown; got {self.xlen!r}")
        object.__setattr__(self, "extensions", MappingProxyType(dict(self.extensions)))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        if not all(isinstance(value, bool) for value in self.free_terms.values()):
            raise ConditionError("free-term values must be Boolean")
        object.__setattr__(self, "free_terms", MappingProxyType(dict(self.free_terms)))
        object.__setattr__(self, "version_sets", MappingProxyType(dict(self.version_sets)))


class Condition:
    """Base class for immutable condition expressions."""

    @property
    def has_unresolved(self) -> bool:
        """Whether this expression contains an unresolved IDL condition."""

        return _contains_unresolved(self)

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        raise NotImplementedError

    def to_data(self) -> bool | dict[str, Any]:
        raise NotImplementedError

    def __and__(self, other: Condition) -> Condition:
        return all_of(self, other)

    def __or__(self, other: Condition) -> Condition:
        return any_of(self, other)

    def __invert__(self) -> Condition:
        return negate(self)

    def implies(self, other: Condition) -> Condition:
        return implies(self, other)


@dataclass(frozen=True, slots=True)
class ConstantCondition(Condition):
    value: bool

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        del context
        return TruthValue.TRUE if self.value else TruthValue.FALSE

    def to_data(self) -> bool:
        return self.value


TRUE = ConstantCondition(True)
FALSE = ConstantCondition(False)


@dataclass(frozen=True, slots=True)
class AllOf(Condition):
    children: tuple[Condition, ...]

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        result = TruthValue.TRUE
        for child in self.children:
            value = child.evaluate(context)
            if value is TruthValue.FALSE:
                return value
            if value is TruthValue.UNKNOWN:
                result = value
        return result

    def to_data(self) -> dict[str, Any]:
        return {"allOf": [child.to_data() for child in self.children]}


@dataclass(frozen=True, slots=True)
class AnyOf(Condition):
    children: tuple[Condition, ...]

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        result = TruthValue.FALSE
        for child in self.children:
            value = child.evaluate(context)
            if value is TruthValue.TRUE:
                return value
            if value is TruthValue.UNKNOWN:
                result = value
        return result

    def to_data(self) -> dict[str, Any]:
        return {"anyOf": [child.to_data() for child in self.children]}


@dataclass(frozen=True, slots=True)
class ExactlyOne(Condition):
    children: tuple[Condition, ...]

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        true_count = 0
        has_unknown = False
        for child in self.children:
            value = child.evaluate(context)
            if value is TruthValue.TRUE:
                true_count += 1
                if true_count > 1:
                    return TruthValue.FALSE
            elif value is TruthValue.UNKNOWN:
                has_unknown = True
        if has_unknown:
            return TruthValue.UNKNOWN
        return TruthValue.TRUE if true_count == 1 else TruthValue.FALSE

    def to_data(self) -> dict[str, Any]:
        return {"oneOf": [child.to_data() for child in self.children]}


@dataclass(frozen=True, slots=True)
class NoneOf(Condition):
    children: tuple[Condition, ...]

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        return AnyOf(self.children).evaluate(context).negate()

    def to_data(self) -> dict[str, Any]:
        return {"noneOf": [child.to_data() for child in self.children]}


@dataclass(frozen=True, slots=True)
class Not(Condition):
    child: Condition

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        return self.child.evaluate(context).negate()

    def to_data(self) -> dict[str, Any]:
        return {"not": self.child.to_data()}


@dataclass(frozen=True, slots=True)
class Implies(Condition):
    antecedent: Condition
    consequent: Condition

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        left = self.antecedent.evaluate(context)
        right = self.consequent.evaluate(context)
        if left is TruthValue.FALSE or right is TruthValue.TRUE:
            return TruthValue.TRUE
        if left is TruthValue.TRUE:
            return right
        return TruthValue.UNKNOWN

    def to_data(self) -> dict[str, Any]:
        return {"if": self.antecedent.to_data(), "then": self.consequent.to_data()}


@dataclass(frozen=True, slots=True)
class ExtensionTerm(Condition):
    name: str
    requirements: tuple[VersionRequirement, ...] = field(
        default_factory=lambda: parse_version_requirements(None)
    )

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        candidate = context.extensions.get(self.name)
        if candidate is None:
            return TruthValue.FALSE if context.closed_world_extensions else TruthValue.UNKNOWN
        versions = context.version_sets.get(self.name)
        return (
            TruthValue.TRUE
            if all(req.matches(candidate, versions=versions) for req in self.requirements)
            else TruthValue.FALSE
        )

    def to_data(self) -> dict[str, Any]:
        value: str | list[str]
        if len(self.requirements) == 1:
            value = str(self.requirements[0])
        else:
            value = [str(req) for req in self.requirements]
        return {"extension": {"name": self.name, "version": value}}


class ParameterOperator(str, Enum):
    EQUAL = "equal"
    NOT_EQUAL = "notEqual"
    LESS_THAN = "lessThan"
    GREATER_THAN = "greaterThan"
    LESS_THAN_OR_EQUAL = "lessThanOrEqual"
    GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"
    INCLUDES = "includes"
    ONE_OF = "oneOf"


@dataclass(frozen=True, slots=True)
class ParameterTerm(Condition):
    name: str
    operator: ParameterOperator
    value: Any = field(compare=False, hash=False)
    _value_identity: tuple[Any, ...] = field(init=False, repr=False)
    index: int | None = None
    size: bool = False
    bit_range: tuple[int, int] | None = None
    reason: str | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_value_identity", _json_identity(self.value))
        object.__setattr__(self, "value", _freeze_value(self.value))
        selector_count = sum((self.index is not None, self.size, self.bit_range is not None))
        if selector_count > 1:
            raise ConditionError(f"parameter {self.name!r} has multiple selectors")
        if self.index is not None and self.index < 0:
            raise ConditionError(f"parameter {self.name!r} has a negative array index")
        if self.bit_range is not None:
            msb, lsb = self.bit_range
            if lsb < 0 or msb < lsb:
                raise ConditionError(f"parameter {self.name!r} has invalid bit range {msb}-{lsb}")
        if self.operator is ParameterOperator.INCLUDES and selector_count:
            raise ConditionError("includes cannot be combined with index, size, or range")
        if self.operator is ParameterOperator.ONE_OF and (
            not isinstance(self.value, tuple) or len(self.value) < 2
        ):
            raise ConditionError("parameter oneOf needs at least two values")

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        if self.name not in context.parameters:
            return TruthValue.FALSE if context.closed_world_parameters else TruthValue.UNKNOWN
        candidate = context.parameters[self.name]
        try:
            if self.index is not None:
                if not isinstance(candidate, (list, tuple)) or self.index >= len(candidate):
                    return TruthValue.FALSE
                candidate = candidate[self.index]
            elif self.size:
                if not isinstance(candidate, (list, tuple)):
                    return TruthValue.FALSE
                candidate = len(candidate)
            elif self.bit_range is not None:
                if not isinstance(candidate, int) or isinstance(candidate, bool):
                    return TruthValue.FALSE
                msb, lsb = self.bit_range
                candidate = (candidate >> lsb) & ((1 << (msb - lsb + 1)) - 1)
            return TruthValue.TRUE if self._compare(candidate) else TruthValue.FALSE
        except (TypeError, ValueError):
            return TruthValue.FALSE

    def _compare(self, candidate: Any) -> bool:
        if self.operator is ParameterOperator.EQUAL:
            return _json_equal(candidate, self.value)
        if self.operator is ParameterOperator.NOT_EQUAL:
            return not _json_equal(candidate, self.value)
        if self.operator is ParameterOperator.LESS_THAN:
            return _ordered_values(candidate, self.value, "<")
        if self.operator is ParameterOperator.GREATER_THAN:
            return _ordered_values(candidate, self.value, ">")
        if self.operator is ParameterOperator.LESS_THAN_OR_EQUAL:
            return _ordered_values(candidate, self.value, "<=")
        if self.operator is ParameterOperator.GREATER_THAN_OR_EQUAL:
            return _ordered_values(candidate, self.value, ">=")
        if self.operator is ParameterOperator.INCLUDES:
            return isinstance(candidate, (list, tuple)) and any(
                _json_equal(item, self.value) for item in candidate
            )
        if self.operator is ParameterOperator.ONE_OF:
            return any(_json_equal(candidate, item) for item in self.value)
        raise AssertionError(f"unhandled parameter operator {self.operator}")

    def to_data(self) -> dict[str, Any]:
        term: dict[str, Any] = {"name": self.name}
        if self.index is not None:
            term["index"] = self.index
        elif self.size:
            term["size"] = True
        elif self.bit_range is not None:
            term["range"] = f"{self.bit_range[0]}-{self.bit_range[1]}"
        term[self.operator.value] = _mutable_value(self.value)
        if self.reason is not None:
            term["reason"] = self.reason
        return {"param": term}


@dataclass(frozen=True, slots=True)
class XlenTerm(Condition):
    value: int

    def __post_init__(self) -> None:
        if self.value not in (32, 64):
            raise ConditionError(f"XLEN must be 32 or 64; got {self.value!r}")

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        if context.xlen is None:
            return TruthValue.UNKNOWN
        return TruthValue.TRUE if context.xlen == self.value else TruthValue.FALSE

    def to_data(self) -> dict[str, Any]:
        return {"xlen": self.value}


@dataclass(frozen=True, slots=True)
class FreeTerm(Condition):
    """A named Boolean proposition used by normalization and solver clients."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ConditionError("free-term name must be a non-empty string")

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        if self.name not in context.free_terms:
            return TruthValue.FALSE if context.closed_world_free_terms else TruthValue.UNKNOWN
        return TruthValue.TRUE if context.free_terms[self.name] else TruthValue.FALSE

    def to_data(self) -> dict[str, Any]:
        return {"free": self.name}


@dataclass(frozen=True, slots=True)
class UnresolvedIdlCondition(Condition):
    text: str
    reason: str | None = field(default=None, compare=False, hash=False)
    source: str | None = field(default=None, compare=False, hash=False)

    def evaluate(self, context: EvaluationContext) -> TruthValue:
        del context
        return TruthValue.UNKNOWN

    def to_data(self) -> dict[str, Any]:
        result = {"idl()": self.text}
        if self.reason is not None:
            result["reason"] = self.reason
        return result


type ConditionLike = Condition | bool | Mapping[str, Any]

_LOGICAL_KEYS = ("allOf", "anyOf", "oneOf", "noneOf", "not")
_TERM_KEYS = ("extension", "param", "xlen", "free", "idl()")


def parse_condition(
    value: ConditionLike,
    *,
    source: str | None = None,
    path: Sequence[str | int] = (),
) -> Condition:
    """Parse the public condition YAML representation."""

    if isinstance(value, Condition):
        return value
    if isinstance(value, bool):
        return TRUE if value else FALSE
    if not isinstance(value, Mapping):
        raise _error(
            source, path, f"condition must be a mapping or boolean, got {type(value).__name__}"
        )
    keys = [key for key in (*_LOGICAL_KEYS, "if", *_TERM_KEYS) if key in value]
    if len(keys) != 1:
        raise _error(source, path, "condition must contain exactly one condition operator")
    key = keys[0]
    if key in ("allOf", "anyOf", "oneOf", "noneOf"):
        if set(value) != {key}:
            raise _error(source, path, f"{key} cannot be combined with other keys")
        children = _parse_children(value[key], source, (*path, key))
        constructors = {
            "allOf": AllOf,
            "anyOf": AnyOf,
            "oneOf": ExactlyOne,
            "noneOf": NoneOf,
        }
        return constructors[key](children)
    if key == "not":
        if set(value) != {"not"}:
            raise _error(source, path, "not cannot be combined with other keys")
        return Not(parse_condition(value[key], source=source, path=(*path, key)))
    if key == "if":
        if "then" not in value or set(value) != {"if", "then"}:
            raise _error(source, path, "an if condition must contain only 'if' and 'then'")
        return Implies(
            parse_condition(value["if"], source=source, path=(*path, "if")),
            parse_condition(value["then"], source=source, path=(*path, "then")),
        )
    if key == "extension":
        if set(value) != {"extension"}:
            raise _error(source, path, "extension cannot be combined with other keys")
        return _parse_extension(value[key], source, (*path, key))
    if key == "param":
        if set(value) != {"param"}:
            raise _error(source, path, "param cannot be combined with other keys")
        return _parse_parameter(value[key], source, (*path, key))
    if key == "xlen":
        if set(value) != {"xlen"}:
            raise _error(source, path, "xlen cannot be combined with other keys")
        return XlenTerm(value[key])
    if key == "free":
        if set(value) != {"free"}:
            raise _error(source, path, "free cannot be combined with other keys")
        try:
            return FreeTerm(value[key])
        except ConditionError as error:
            raise _error(source, (*path, key), str(error)) from error
    if set(value) - {"idl()", "reason"}:
        raise _error(source, path, "idl() can only be combined with reason")
    text = value[key]
    if not isinstance(text, str):
        raise _error(source, (*path, key), "IDL condition must be a string")
    reason = value.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise _error(source, (*path, "reason"), "condition reason must be a string")
    return UnresolvedIdlCondition(text, reason=reason, source=source)


def _parse_extension(value: Any, source: str | None, path: tuple[str | int, ...]) -> Condition:
    if not isinstance(value, Mapping):
        raise _error(source, path, "extension condition must be a mapping")
    if "name" in value:
        allowed = {"name", "version"}
        if extra := set(value) - allowed:
            raise _error(source, path, f"unexpected extension condition keys: {sorted(extra)}")
        name = value["name"]
        if not isinstance(name, str) or not name:
            raise _error(source, (*path, "name"), "extension name must be a non-empty string")
        try:
            requirements = parse_version_requirements(value.get("version"))
        except (TypeError, ValueError) as error:
            raise _error(source, (*path, "version"), str(error)) from error
        return ExtensionTerm(name, requirements)
    return _parse_local_expression(value, source, path, _parse_extension)


def _parse_parameter(value: Any, source: str | None, path: tuple[str | int, ...]) -> Condition:
    if not isinstance(value, Mapping):
        raise _error(source, path, "parameter condition must be a mapping")
    if "name" not in value:
        return _parse_local_expression(value, source, path, _parse_parameter)
    name = value["name"]
    if not isinstance(name, str) or not name:
        raise _error(source, (*path, "name"), "parameter name must be a non-empty string")
    operators = [operator for operator in ParameterOperator if operator.value in value]
    if len(operators) != 1:
        raise _error(source, path, "parameter condition must contain exactly one comparison")
    allowed = {"name", operators[0].value, "index", "size", "range", "reason"}
    if extra := set(value) - allowed:
        raise _error(source, path, f"unexpected parameter condition keys: {sorted(extra)}")
    index = value.get("index")
    if index is not None and (not isinstance(index, int) or isinstance(index, bool)):
        raise _error(source, (*path, "index"), "array index must be an integer")
    size = value.get("size", False)
    if "size" in value and size is not True:
        raise _error(source, (*path, "size"), "size selector must be true")
    reason = value.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise _error(source, (*path, "reason"), "condition reason must be a string")
    bit_range = _parse_range(value.get("range"), source, (*path, "range"))
    comparison_value = _freeze_value(value[operators[0].value])
    if operators[0] is ParameterOperator.ONE_OF and (
        not isinstance(comparison_value, tuple) or len(comparison_value) < 2
    ):
        raise _error(source, (*path, "oneOf"), "parameter oneOf needs at least two values")
    try:
        return ParameterTerm(
            name=name,
            operator=operators[0],
            value=comparison_value,
            index=index,
            size=size,
            bit_range=bit_range,
            reason=reason,
        )
    except ConditionError as error:
        raise _error(source, path, str(error)) from error


def _parse_local_expression(
    value: Mapping[str, Any], source: str | None, path: tuple[str | int, ...], leaf_parser: Any
) -> Condition:
    keys = [key for key in (*_LOGICAL_KEYS, "if") if key in value]
    if len(keys) != 1:
        raise _error(source, path, "nested condition must contain exactly one operator")
    key = keys[0]
    if key in ("allOf", "anyOf", "oneOf", "noneOf"):
        if set(value) != {key}:
            raise _error(source, path, f"{key} cannot be combined with other keys")
        raw = value[key]
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) < 2:
            raise _error(source, (*path, key), f"{key} needs at least two children")
        children = tuple(
            leaf_parser(item, source, (*path, key, index)) for index, item in enumerate(raw)
        )
        return {"allOf": AllOf, "anyOf": AnyOf, "oneOf": ExactlyOne, "noneOf": NoneOf}[key](
            children
        )
    if key == "not":
        if set(value) != {"not"}:
            raise _error(source, path, "not cannot be combined with other keys")
        return Not(leaf_parser(value[key], source, (*path, key)))
    if "then" not in value or set(value) != {"if", "then"}:
        raise _error(source, path, "an if condition must contain only 'if' and 'then'")
    return Implies(
        parse_condition(value["if"], source=source, path=(*path, "if")),
        leaf_parser(value["then"], source, (*path, "then")),
    )


def _parse_children(
    value: Any, source: str | None, path: tuple[str | int, ...]
) -> tuple[Condition, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        raise _error(source, path, "logical operator needs at least two children")
    return tuple(
        parse_condition(item, source=source, path=(*path, index))
        for index, item in enumerate(value)
    )


def _parse_range(
    value: Any, source: str | None, path: tuple[str | int, ...]
) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(source, path, "bit range must be 'MSB-LSB'")
    parts = value.split("-", 1)
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise _error(source, path, "bit range must be 'MSB-LSB'")
    return int(parts[0]), int(parts[1])


def all_of(*conditions: ConditionLike) -> Condition:
    children: list[Condition] = []
    for raw in conditions:
        condition = parse_condition(raw)
        flattened = condition.children if isinstance(condition, AllOf) else (condition,)
        for child in flattened:
            if child == FALSE:
                return FALSE
            if child != TRUE:
                children.append(child)
    unique = tuple(dict.fromkeys(children))
    if not unique:
        return TRUE
    if any(negate(child) in unique for child in unique):
        return FALSE
    return unique[0] if len(unique) == 1 else AllOf(unique)


def any_of(*conditions: ConditionLike) -> Condition:
    children: list[Condition] = []
    for raw in conditions:
        condition = parse_condition(raw)
        flattened = condition.children if isinstance(condition, AnyOf) else (condition,)
        for child in flattened:
            if child == TRUE:
                return TRUE
            if child != FALSE:
                children.append(child)
    unique = tuple(dict.fromkeys(children))
    if not unique:
        return FALSE
    if any(negate(child) in unique for child in unique):
        return TRUE
    return unique[0] if len(unique) == 1 else AnyOf(unique)


def exactly_one(*conditions: ConditionLike) -> Condition:
    children = tuple(parse_condition(condition) for condition in conditions)
    if not children:
        return FALSE
    return children[0] if len(children) == 1 else ExactlyOne(children)


def none_of(*conditions: ConditionLike) -> Condition:
    children = tuple(parse_condition(condition) for condition in conditions)
    if not children:
        return TRUE
    return negate(children[0]) if len(children) == 1 else NoneOf(children)


def negate(condition: ConditionLike) -> Condition:
    parsed = parse_condition(condition)
    if parsed == TRUE:
        return FALSE
    if parsed == FALSE:
        return TRUE
    if isinstance(parsed, Not):
        return parsed.child
    return Not(parsed)


not_ = negate


def normalize(condition: ConditionLike) -> Condition:
    """Return a deterministic, idempotent simplification of *condition*."""

    parsed = parse_condition(condition)
    if isinstance(parsed, AllOf):
        return all_of(*(normalize(child) for child in parsed.children))
    if isinstance(parsed, AnyOf):
        return any_of(*(normalize(child) for child in parsed.children))
    if isinstance(parsed, ExactlyOne):
        children = tuple(normalize(child) for child in parsed.children)
        return exactly_one(*children)
    if isinstance(parsed, NoneOf):
        children = tuple(normalize(child) for child in parsed.children)
        return none_of(*children)
    if isinstance(parsed, Implies):
        return implies(normalize(parsed.antecedent), normalize(parsed.consequent))
    if isinstance(parsed, Not):
        child = normalize(parsed.child)
        if isinstance(child, AllOf):
            return any_of(*(normalize(negate(item)) for item in child.children))
        if isinstance(child, AnyOf):
            return all_of(*(normalize(negate(item)) for item in child.children))
        if isinstance(child, NoneOf):
            return any_of(*(normalize(item) for item in child.children))
        if isinstance(child, Implies):
            return all_of(normalize(child.antecedent), normalize(negate(child.consequent)))
        return negate(child)
    return parsed


def implies(antecedent: ConditionLike, consequent: ConditionLike) -> Condition:
    left = parse_condition(antecedent)
    right = parse_condition(consequent)
    if left == FALSE or right == TRUE:
        return TRUE
    if left == TRUE:
        return right
    if right == FALSE:
        return negate(left)
    return Implies(left, right)


def partial_evaluate(condition: ConditionLike, context: EvaluationContext) -> Condition:
    """Replace concretely known subexpressions and retain unknown terms."""

    parsed = parse_condition(condition)
    value = parsed.evaluate(context)
    if value is TruthValue.TRUE:
        return TRUE
    if value is TruthValue.FALSE:
        return FALSE
    if isinstance(parsed, AllOf):
        return all_of(*(partial_evaluate(child, context) for child in parsed.children))
    if isinstance(parsed, AnyOf):
        return any_of(*(partial_evaluate(child, context) for child in parsed.children))
    if isinstance(parsed, ExactlyOne):
        return exactly_one(*(partial_evaluate(child, context) for child in parsed.children))
    if isinstance(parsed, NoneOf):
        return none_of(*(partial_evaluate(child, context) for child in parsed.children))
    if isinstance(parsed, Not):
        return negate(partial_evaluate(parsed.child, context))
    if isinstance(parsed, Implies):
        return implies(
            partial_evaluate(parsed.antecedent, context),
            partial_evaluate(parsed.consequent, context),
        )
    return parsed


def _contains_unresolved(condition: Condition) -> bool:
    if isinstance(condition, UnresolvedIdlCondition):
        return True
    if isinstance(condition, (AllOf, AnyOf, ExactlyOne, NoneOf)):
        return any(_contains_unresolved(child) for child in condition.children)
    if isinstance(condition, Not):
        return _contains_unresolved(condition.child)
    if isinstance(condition, Implies):
        return _contains_unresolved(condition.antecedent) or _contains_unresolved(
            condition.consequent
        )
    return False


def _freeze_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    return value


def _mutable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _mutable_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable_value(item) for item in value]
    return value


def _json_equal(left: Any, right: Any) -> bool:
    return _json_identity(left) == _json_identity(right)


def _json_identity(value: Any) -> tuple[Any, ...]:
    """Return a hashable identity with JSON value-type distinctions."""

    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, (list, tuple)):
        return ("array", tuple(_json_identity(item) for item in value))
    if isinstance(value, Mapping):
        return (
            "object",
            frozenset((_json_identity(key), _json_identity(item)) for key, item in value.items()),
        )
    return ("other", type(value), value)


def _ordered_values(left: Any, right: Any, operator: str) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False
    return {
        "<": left < right,
        ">": left > right,
        "<=": left <= right,
        ">=": left >= right,
    }[operator]


def _error(source: str | None, path: Sequence[str | int], message: str) -> ConditionError:
    location = "/".join(str(part) for part in path)
    prefix = f"{source}:" if source else ""
    if location:
        prefix += f"/{location}: "
    elif prefix:
        prefix += " "
    return ConditionError(prefix + message)


__all__ = [
    "FALSE",
    "TRUE",
    "AllOf",
    "AnyOf",
    "Condition",
    "ConditionError",
    "EvaluationContext",
    "ExactlyOne",
    "ExtensionTerm",
    "FreeTerm",
    "Implies",
    "NoneOf",
    "Not",
    "ParameterOperator",
    "ParameterTerm",
    "TruthValue",
    "UnresolvedConditionError",
    "UnresolvedIdlCondition",
    "XlenTerm",
    "all_of",
    "any_of",
    "exactly_one",
    "implies",
    "negate",
    "none_of",
    "normalize",
    "not_",
    "parse_condition",
    "partial_evaluate",
]
