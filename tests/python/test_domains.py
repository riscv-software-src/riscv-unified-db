# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from udb.database import Database
from udb.domains import (
    ArrayDomain,
    BooleanDomain,
    Bound,
    DomainError,
    DomainKind,
    EmptyDomain,
    EnumerationLimitError,
    InfiniteDomainError,
    IntegerDomain,
    NotSingletonError,
    ParameterDomain,
    StringDomain,
    UnsupportedDomainError,
)
from udb.schema import SchemaStore

REPOSITORY_ROOT = Path(__file__).parents[2]
ISA_ROOT = REPOSITORY_ROOT / "spec" / "std" / "isa"
SCHEMA_ROOT = REPOSITORY_ROOT / "spec" / "schemas"


def domain(schema: dict, *, source: str = "test schema") -> ParameterDomain:
    return ParameterDomain.from_schema(schema, source=source)


def test_boolean_domain_is_immutable_typed_and_singleton() -> None:
    schema = {"allOf": [{"type": "boolean"}, {"const": True}]}
    result = domain(schema)
    schema["allOf"][1]["const"] = False

    assert isinstance(result, BooleanDomain)
    assert result.kind is DomainKind.BOOLEAN
    assert result.allowed_values == (True,)
    assert result.accepts(True)
    assert not result.accepts(1)
    assert result.is_singleton
    assert result.single_value is True
    with pytest.raises(TypeError):
        result.schema["new"] = "value"  # type: ignore[index]


def test_integer_bounds_exclusions_and_complete_enumeration() -> None:
    result = domain(
        {
            "type": "integer",
            "minimum": 0,
            "exclusiveMinimum": 1,
            "maximum": 6,
            "exclusiveMaximum": 5,
            "not": {"const": 3},
        }
    )

    assert isinstance(result, IntegerDomain)
    assert result.minimum == Bound(1, inclusive=False)
    assert result.maximum == Bound(5, inclusive=False)
    assert result.cardinality == 2
    assert result.enumerate_values(limit=2) == (2, 4)
    assert all((value in result) == (value in {2, 4}) for value in range(7))
    with pytest.raises(EnumerationLimitError, match="more than 1"):
        result.enumerate_values(limit=1)


def test_enum_const_and_intersection_filter_values_without_mutation() -> None:
    left = domain({"type": "integer", "enum": [1, 2, 3, 4]}, source="left")
    right = domain({"type": "integer", "minimum": 2, "maximum": 3}, source="right")

    result = left & right

    assert isinstance(result, IntegerDomain)
    assert result.allowed_values == (2, 3)
    assert result.enumerate_values(limit=2) == (2, 3)
    assert left.enumerate_values(limit=4) == (1, 2, 3, 4)


def test_contradictory_and_cross_type_intersections_are_empty() -> None:
    backwards = domain({"type": "integer", "minimum": 2, "maximum": 1})
    cross_type = domain({"type": "integer"}) & domain({"type": "string"})
    mismatched_const = domain({"type": "integer", "const": "not an integer"})
    boolean_conflict = domain({"type": "boolean", "const": True}) & domain(
        {"type": "boolean", "const": False}
    )

    assert isinstance(backwards, EmptyDomain)
    assert isinstance(cross_type, EmptyDomain)
    assert isinstance(mismatched_const, EmptyDomain)
    assert isinstance(boolean_conflict, EmptyDomain)
    assert backwards.is_empty
    assert backwards.cardinality == 0
    assert backwards.enumerate_values(limit=0) == ()
    with pytest.raises(NotSingletonError):
        _ = backwards.single_value


def test_string_domains_distinguish_finite_and_infinite() -> None:
    finite = domain({"type": "string", "enum": ["direct", "vectored"]})
    infinite = domain({"type": "string", "not": {"const": "reserved"}})

    assert isinstance(finite, StringDomain)
    assert finite.enumerate_values(limit=2) == ("direct", "vectored")
    assert infinite.accepts("custom")
    assert not infinite.accepts("reserved")
    assert not infinite.is_finite
    with pytest.raises(InfiniteDomainError):
        infinite.enumerate_values(limit=100)


def test_reference_and_allof_use_the_explicit_offline_schema_store() -> None:
    schema = {
        "allOf": [
            {"$ref": "schema_defs.json#/$defs/uint64"},
            {"not": {"const": 0}},
        ]
    }
    with pytest.raises(DomainError, match="requires an explicit SchemaStore"):
        domain(schema)

    result = ParameterDomain.from_schema(
        schema,
        schema_store=SchemaStore(SCHEMA_ROOT),
        source="ARCH_ID_VALUE",
    )

    assert isinstance(result, IntegerDomain)
    assert result.minimum == Bound(0)
    assert result.maximum == Bound(2**64 - 1)
    assert not result.accepts(0)
    assert result.accepts(1)
    assert result.accepts(2**64 - 1)
    assert not result.accepts(2**64)


def test_local_and_nested_external_references_preserve_resolution_context(
    tmp_path: Path,
) -> None:
    local = domain(
        {
            "$defs": {"n": {"type": "integer", "enum": [1, 2]}},
            "$ref": "#/$defs/n",
        }
    )
    (tmp_path / "defs.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "v0.1",
                "$defs": {
                    "n": {"type": "integer", "enum": [3, 4]},
                    "array": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/n"},
                        "minItems": 1,
                        "maxItems": 1,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    nested = ParameterDomain.from_schema(
        {"$ref": "defs.json#/$defs/array"},
        schema_store=SchemaStore(tmp_path),
    )

    assert local.enumerate_values(limit=2) == (1, 2)
    assert (local & domain({"type": "integer", "minimum": 2})).single_value == 2
    assert nested.enumerate_values(limit=2) == ((3,), (4,))


def test_cyclic_schema_reference_has_a_domain_error() -> None:
    schema: dict = {
        "$defs": {"n": {"$ref": "#/$defs/n"}},
        "$ref": "#/$defs/n",
    }

    with pytest.raises(DomainError, match="cyclic parameter schema reference"):
        domain(schema, source="recursive")


def test_cyclic_external_schema_reference_has_a_domain_error(tmp_path: Path) -> None:
    (tmp_path / "cycle.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "v0.1",
                "$defs": {
                    "a": {"$ref": "#/$defs/b"},
                    "b": {"$ref": "#/$defs/a"},
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DomainError, match="cyclic parameter schema reference"):
        ParameterDomain.from_schema(
            {"$ref": "cycle.json#/$defs/a"},
            schema_store=SchemaStore(tmp_path),
            source="external cycle",
        )


def test_array_length_items_contains_and_uniqueness() -> None:
    result = domain(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [0, 7, 16]},
            "contains": {"const": 0},
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.min_items == 1
    assert result.max_items == 3
    assert result.unique_items
    assert result.accepts([0])
    assert result.accepts((7, 0, 16))
    assert not result.accepts([])
    assert not result.accepts([7])
    assert not result.accepts([0, 0])
    assert not result.accepts([0, 8])
    assert result.enumerate_values(limit=11) == (
        (0,),
        (0, 7),
        (0, 16),
        (7, 0),
        (16, 0),
        (0, 7, 16),
        (0, 16, 7),
        (7, 0, 16),
        (7, 16, 0),
        (16, 0, 7),
        (16, 7, 0),
    )


def test_contains_can_be_satisfied_by_an_additional_tuple_item() -> None:
    result = domain(
        {
            "type": "array",
            "items": [{"const": 0}],
            "additionalItems": {"const": 1},
            "contains": {"const": 1},
        }
    )

    assert isinstance(result, ArrayDomain)
    assert not result.is_empty
    assert result.accepts([0, 1])


def test_tuple_items_and_additional_items() -> None:
    result = domain(
        {
            "type": "array",
            "items": [{"const": False}, {"const": True}],
            "additionalItems": {"type": "boolean"},
            "minItems": 2,
            "maxItems": 3,
        }
    )

    assert isinstance(result, ArrayDomain)
    assert len(result.prefix_items) == 2
    assert result.domain_for_index(0).single_value is False  # type: ignore[union-attr]
    assert result.domain_for_index(1).single_value is True  # type: ignore[union-attr]
    assert result.accepts([False, True])
    assert result.accepts([False, True, False])
    assert not result.accepts([True, True])
    assert result.enumerate_values(limit=3) == (
        (False, True),
        (False, True, False),
        (False, True, True),
    )


def test_tuple_additional_items_false_makes_an_implicitly_bounded_domain() -> None:
    result = domain(
        {
            "type": "array",
            "items": [{"const": 1}, {"const": 2}],
            "additionalItems": False,
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.max_items is None
    assert result.effective_max_items == 2
    assert result.is_finite
    assert result.enumerate_values(limit=3) == ((), (1,), (1, 2))


def test_array_intersection_normalizes_length_and_item_constraints() -> None:
    left = domain(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [1, 2, 3]},
            "minItems": 1,
            "maxItems": 3,
        }
    )
    right = domain(
        {
            "type": "array",
            "items": {"type": "integer", "minimum": 2},
            "maxItems": 2,
            "uniqueItems": True,
        }
    )

    result = left & right

    assert isinstance(result, ArrayDomain)
    assert result.min_items == 1
    assert result.max_items == 2
    assert result.unique_items
    assert isinstance(result.item_domain, IntegerDomain)
    assert result.item_domain.allowed_values == (2, 3)
    assert result.enumerate_values(limit=6) == ((2,), (3,), (2, 3), (3, 2))


def test_array_enumeration_filters_before_applying_result_limit() -> None:
    result = domain(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [0, 1, 2]},
            "minItems": 1,
            "maxItems": 1,
            "contains": {"const": 2},
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.cardinality == 1
    assert result.is_singleton
    assert result.single_value == (2,)
    assert result.enumerate_values(limit=1) == ((2,),)


def test_array_empty_detection_covers_required_items_and_uniqueness() -> None:
    impossible_contains = domain(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [1, 2]},
            "contains": {"const": 3},
            "maxItems": 2,
        }
    )
    impossible_unique = domain(
        {
            "type": "array",
            "items": {"const": 1},
            "minItems": 2,
            "maxItems": 2,
            "uniqueItems": True,
        }
    )

    assert isinstance(impossible_contains, EmptyDomain)
    assert isinstance(impossible_unique, EmptyDomain)


def test_array_empty_detection_handles_tuple_duplicates_and_multiple_contains() -> None:
    duplicate_tuple = domain(
        {
            "type": "array",
            "items": [{"const": 1}, {"const": 1}],
            "additionalItems": False,
            "minItems": 2,
            "maxItems": 2,
            "uniqueItems": True,
        }
    )
    incompatible_contains = domain(
        {
            "allOf": [
                {
                    "type": "array",
                    "items": {"type": "integer", "enum": [0, 1]},
                    "maxItems": 1,
                    "contains": {"const": 0},
                },
                {"contains": {"const": 1}},
            ]
        }
    )

    assert isinstance(duplicate_tuple, EmptyDomain)
    assert isinstance(incompatible_contains, EmptyDomain)
    assert duplicate_tuple.cardinality == 0
    assert incompatible_contains.enumerate_values(limit=0) == ()


def test_zero_length_array_is_finite_with_infinite_item_schema() -> None:
    result = domain(
        {
            "type": "array",
            "items": {"type": "integer"},
            "maxItems": 0,
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.is_finite
    assert result.cardinality == 1
    assert result.is_singleton
    assert result.single_value == ()


def test_unique_unbounded_array_with_finite_items_is_finite() -> None:
    result = domain(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [1, 2]},
            "uniqueItems": True,
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.effective_max_items == 2
    assert result.is_finite
    assert result.cardinality == 5
    assert result.enumerate_values(limit=5) == ((), (1,), (2,), (1, 2), (2, 1))


def test_empty_tuple_position_makes_later_infinite_items_unreachable() -> None:
    result = domain(
        {
            "type": "array",
            "items": [{"type": "integer", "minimum": 1, "maximum": 0}],
            "additionalItems": {"type": "integer"},
        }
    )

    assert isinstance(result, ArrayDomain)
    assert result.effective_max_items == 0
    assert result.is_finite
    assert result.enumerate_values(limit=1) == ((),)


def test_array_enumeration_bounds_rejected_candidate_work() -> None:
    result = domain(
        {
            "type": "array",
            "items": [{"const": 0} for _ in range(200)],
            "additionalItems": False,
            "maxItems": 200,
            "uniqueItems": True,
        }
    )

    assert isinstance(result, ArrayDomain)
    with pytest.raises(EnumerationLimitError, match="bounded work"):
        result.enumerate_values(limit=2)


def test_large_finite_array_domain_never_silently_truncates() -> None:
    result = domain(
        {
            "type": "array",
            "items": {"type": "boolean"},
            "minItems": 32,
            "maxItems": 32,
        }
    )

    assert result.is_finite
    assert not result.is_empty
    assert result.cardinality is None
    with pytest.raises(EnumerationLimitError, match=r"more than 100|exceeds limit 100"):
        result.enumerate_values(limit=100)


def test_unsupported_non_corpus_shapes_have_actionable_errors() -> None:
    with pytest.raises(UnsupportedDomainError, match="pattern"):
        domain({"type": "string", "pattern": "^[a-z]+$"}, source="named-mode")
    with pytest.raises(UnsupportedDomainError, match="unconstrained tuple additionalItems"):
        domain({"type": "array", "items": [{"type": "integer"}]})
    with pytest.raises(UnsupportedDomainError, match="cannot infer"):
        domain({}, source="empty schema")
    with pytest.raises(UnsupportedDomainError, match="cannot infer"):
        domain({"maximum": 3}, source="implicit numeric union")
    with pytest.raises(UnsupportedDomainError, match="cannot infer"):
        domain({"items": {"type": "integer"}}, source="implicit array union")


def test_json_schema_integer_membership_includes_integral_floats() -> None:
    enum_domain = domain({"type": "integer", "enum": [1.0, 2]})
    const_domain = domain({"type": "integer", "const": 1})
    excluded_domain = domain({"type": "integer", "not": {"const": 1.0}})

    assert enum_domain.enumerate_values(limit=2) == (1, 2)
    assert enum_domain.accepts(1.0)
    assert const_domain.accepts(1.0)
    assert not excluded_domain.accepts(1.0)
    assert not enum_domain.accepts(True)


def test_membership_matches_draft7_for_supported_scalar_matrix() -> None:
    schemas_and_values = [
        ({"type": "boolean"}, [False, True, 0, 1, "true"]),
        (
            {
                "type": "integer",
                "exclusiveMinimum": 0,
                "maximum": 3,
                "enum": [1.0, 2, 3],
            },
            [False, 0, 1, 1.0, 2.0, 3, 4, "1"],
        ),
        ({"type": "string", "enum": ["a", "b"]}, ["", "a", "b", "c", 1]),
    ]

    for schema, values in schemas_and_values:
        result = domain(schema)
        validator = Draft7Validator(schema)
        assert [result.accepts(value) for value in values] == [
            validator.is_valid(value) for value in values
        ]


def test_array_membership_matrix_matches_draft7() -> None:
    schema = {
        "type": "array",
        "items": {"type": "integer", "enum": [0, 1, 2]},
        "contains": {"const": 2},
        "minItems": 1,
        "maxItems": 3,
        "uniqueItems": True,
    }
    result = domain(schema)
    validator = Draft7Validator(schema)
    values: list[list[object]] = [[]]
    atoms: tuple[object, ...] = (False, 0, 1, 1.0, 2, 3, "2")
    for first in atoms:
        values.append([first])
        for second in atoms:
            values.append([first, second])

    assert [result.accepts(value) for value in values] == [
        validator.is_valid(value) for value in values
    ]


def test_direct_concrete_construction_freezes_mutable_fields() -> None:
    allowed = [True]
    result = BooleanDomain({}, allowed_values=allowed)  # type: ignore[arg-type]

    allowed.append(False)

    assert result.allowed_values == (True,)
    assert not result.accepts(False)


def test_all_standard_parameter_schemas_are_supported_and_nonempty() -> None:
    database = Database.from_path(ISA_ROOT, schemas_path=SCHEMA_ROOT)
    store = SchemaStore(database.schemas_root)
    domains = [
        ParameterDomain.from_schema(
            parameter["schema"], schema_store=store, source=str(parameter.path)
        )
        for parameter in database.objects("parameter")
    ]

    assert len(domains) == 271
    assert all(not result.is_empty for result in domains)
    assert all(result.is_finite for result in domains)
    for parameter, result in zip(database.objects("parameter"), domains, strict=True):
        schema = parameter["schema"]
        if "default" in schema:
            assert result.accepts(schema["default"]), parameter.name
