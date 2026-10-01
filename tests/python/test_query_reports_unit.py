# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from dataclasses import FrozenInstanceError

import pytest

from udb import Configuration, ResolvedDatabase
from udb.query_reports import (
    ParameterListReport,
    ReportBuilder,
    ReportError,
    catalog_names,
)
from udb.query_reports.formatting import condition_text, schema_text


def configuration(**extra):
    return Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "test",
            "description": "report fixture",
            "mandatory_extensions": [],
            **extra,
        }
    )


@pytest.fixture
def database():
    return ResolvedDatabase(
        {
            "ext/A.yaml": {
                "kind": "extension",
                "name": "A",
                "versions": [{"version": "1.0"}],
                "requirements": {"extension": {"name": "B"}},
            },
            "ext/B.yaml": {"kind": "extension", "name": "B", "versions": [{"version": "1.0"}]},
            "param/P.yaml": {
                "kind": "parameter",
                "name": "P",
                "definedBy": {"extension": {"name": "A"}},
                "schema": {"type": "boolean"},
                "description": "P description",
            },
            "param/Q.yaml": {
                "kind": "parameter",
                "name": "Q",
                "definedBy": {"extension": {"name": "B"}},
                "schema": {"type": "integer", "minimum": 0},
                "description": "Q description",
            },
            "param/R.yaml": {
                "kind": "parameter",
                "name": "R",
                "definedBy": {
                    "allOf": [
                        {"extension": {"name": "A"}},
                        {"param": {"name": "P", "equal": True}},
                    ]
                },
                "schema": {"type": "string"},
                "description": "conditional",
            },
            "csr/Z/z.yaml": {"kind": "csr", "name": "z", "definedBy": {"extension": {"name": "A"}}},
            "csr/A/a.yaml": {"kind": "csr", "name": "a", "definedBy": {"extension": {"name": "B"}}},
        }
    )


def test_filtered_parameters_direct_not_implied_or_conditionally_applicable(database):
    report = ReportBuilder(database.configure(Configuration.builtin("_")))
    assert [row.name for row in report.parameters(["A"]).rows] == ["P"]
    assert [row.name for row in report.parameters(["A", "B", "A", "missing"]).rows] == ["P", "Q"]
    assert report.parameters([]) == ParameterListReport(())
    with pytest.raises(TypeError, match="not one string"):
        report.parameters("A")
    with pytest.raises(TypeError):
        report.parameters([1])
    with pytest.raises(FrozenInstanceError):
        report.parameters(["A"]).rows[0].name = "changed"


def test_configured_order_and_extension_filter_availability(database):
    arch = database.configure(
        configuration(
            prohibited_extensions=[{"name": "A"}],
            params={"Q": 1},
        )
    )
    builder = ReportBuilder(arch)
    assert builder.extensions() == ("B",)
    assert builder.parameters(["A"]).rows == ()
    assert [row.name for row in builder.parameters().rows] == ["Q"]
    assert builder.parameter("R").description == "conditional"
    assert builder.parameter("R").has_configured_value is False
    assert builder.parameter("missing") is None
    assert builder.extension("missing") is None
    assert builder.csrs() == ("a", "z")
    assert builder.csrs(selection="possible") == ("a",)
    with pytest.raises(ReportError):
        builder.csrs(selection="bad")
    ordered = ReportBuilder(database.configure(configuration(params={"Q": 1, "P": False})))
    assert [row.name for row in ordered.parameters().rows] == ["Q", "P"]


def test_raw_catalog_names_never_resolve_or_configure(database, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("catalog query must not resolve/configure")

    monkeypatch.setattr(ResolvedDatabase, "resolve", forbidden)
    monkeypatch.setattr(ResolvedDatabase, "configure", forbidden)
    assert catalog_names(database, "csr") == ("a", "z")
    with pytest.raises(TypeError, match="configure explicitly"):
        ReportBuilder(database)


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"const": 1024}, "0x400"),
        ({"enum": ["little", "big"]}, "[little, big]"),
        ({"$ref": "schema_defs.json#/definitions/uint32"}, "32-bit integer"),
        (
            {"allOf": [{"type": "integer", "minimum": 0, "maximum": 255}, {"not": {"const": 0}}]},
            "8-bit integer, ≠ 0",
        ),
        ({"not": {"anyOf": [{"const": 1}, {"const": 2048}]}}, "≠ 1 or 0x800"),
        ({"type": "integer", "minimum": 3, "maximum": 7}, "3 to 7"),
        ({"type": "integer", "minimum": 0}, "&#8805; 0"),
        ({"type": "integer", "maximum": 999}, "&#8804; 999"),
        ({"type": "string", "pattern": "xyz"}, "string matching xyz"),
        ({"type": "string", "format": "date"}, "date"),
        (
            {"type": "array", "minItems": 0, "items": {"type": "boolean"}},
            "at least 0-element array of boolean",
        ),
        ({"type": "array", "maxItems": 2}, "at most 2-element array"),
        (
            {"type": "array", "minItems": 1, "maxItems": 1, "contains": {"const": 32}},
            "1-element array Contains : [32]",
        ),
    ],
)
def test_schema_human_shapes(schema, expected):
    assert schema_text(schema) == expected


@pytest.mark.parametrize(
    "schema",
    [
        {},
        {"$ref": "unhandled.json#"},
        {"type": "object"},
        {"not": {"enum": [1]}},
        {"type": "array", "items": True},
    ],
)
def test_unsupported_schema_is_explicit(schema):
    with pytest.raises(ReportError):
        schema_text(schema)


def test_condition_precision_selectors_and_all_parameter_values():
    assert condition_text({"extension": {"name": "A", "version": "~> 1.0"}}) == "A~>1.0"
    assert condition_text({"param": {"name": "P", "index": 1, "equal": True}}) == "(P[1]==true)"
    assert (
        condition_text({"param": {"name": "P", "size": True, "equal": 2}}) == "($array_size(P)==2)"
    )
    assert condition_text({"param": {"name": "P", "range": "3-0", "equal": 5}}) == "(P[3:0]==5)"
    assert condition_text({"not": {"xlen": 32}}) == "!xlen=32"
    assert condition_text({"param": {"name": "P", "includes": 32}}) == "$array_includes?(P, 32)"


def test_parameter_list_does_not_expose_configuration_values(database):
    result = ReportBuilder(database.configure(configuration(params={"P": True}))).parameters()
    assert list(result.to_data()[0]) == ["name", "exts", "description"]
    with pytest.raises(ReportError, match="output format"):
        result.render("csv")
    data = result.to_data()
    data[0]["name"] = "mutation"
    assert result.rows[0].name == "P"


def test_idl_defined_parameter_uses_accepted_condition_binding(database):
    documents = {path: dict(data) for path, data in database.documents.items()}
    documents["param/IDL.yaml"] = {
        "kind": "parameter",
        "name": "IDL",
        "definedBy": {"idl()": "-> P;"},
        "schema": {"type": "boolean"},
        "description": "IDL-derived parameter availability",
    }
    source = ResolvedDatabase(documents)
    builder = ReportBuilder(source.configure(Configuration.builtin("_")))
    report = builder.parameter("IDL")
    assert report.defined_by == "(P==true)"
    assert report.defined_by_pretty == "Paremeter  equals true"
    assert next(row.exts for row in builder.parameters().rows if row.name == "IDL") == "(P==true)"
