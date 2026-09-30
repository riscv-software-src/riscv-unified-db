# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Additional translation boundaries and requirement-owner regression tests."""

from __future__ import annotations

import pytest

from udb import ArchitectureCheckStatus, Configuration, QueryPresence, ResolvedDatabase
from udb.conditions import AllOf, EvaluationContext, TruthValue, normalize, parse_condition
from udb.idl import IdlSource, parse_isa
from udb.idl.errors import IdlError
from udb.idl.symbols import (
    BuiltinFunctionCallbacks,
    EnumDef,
    IdlEnvironment,
    SymbolTable,
    Var,
)
from udb.idl.types import BOOL_TYPE, Qualifier, Type, TypeKind
from udb.idl_conditions import compile_idl_condition, resolve_idl_conditions
from udb.idl_environment import symbol_table
from udb.idl_yaml_source import idl_field_source
from udb.source import parse_yaml


@pytest.fixture
def symtab():
    bits = Type(TypeKind.BITS, width=64, qualifiers=(Qualifier.CONST,))
    table = SymbolTable(
        IdlEnvironment(
            builtin_global_vars=(
                Var("P", bits, 64, param=True),
                Var("Q", BOOL_TYPE.qualify(Qualifier.CONST), True, param=True),
                Var(
                    "A",
                    Type(
                        TypeKind.ARRAY,
                        width=4,
                        sub_type=bits,
                        qualifiers=(Qualifier.CONST,),
                    ),
                    [1, 2, 3, 4],
                    param=True,
                ),
            ),
            builtin_enums=(EnumDef("ExtensionName", (0, 1), ("Xbase", "Xowner")),),
            builtin_funcs=BuiltinFunctionCallbacks(
                lambda name: False,
                lambda name, requirement: False,
                lambda address: False,
            ),
        )
    )
    signatures = parse_isa(
        "%version: 1.0\n"
        "generated function xlen { returns Bits<8> description { Effective XLEN predicate } }\n"
        "generated function implemented? { returns Boolean arguments ExtensionName extension "
        "description { Extension predicate } }\n"
        "generated function implemented_version? { returns Boolean "
        "arguments ExtensionName extension, String version_requirement "
        "description { Extension version predicate } }\n"
    ).definitions
    for signature in signatures:
        signature.add_symbol(table)
    return table


@pytest.mark.parametrize(
    ("text", "data"),
    [
        ("-> 3 != P;", {"param": {"name": "P", "notEqual": 3}}),
        ("-> 3 <= A[0];", {"param": {"name": "A", "index": 0, "greaterThanOrEqual": 3}}),
        ("-> 3 > A[0];", {"param": {"name": "A", "index": 0, "lessThan": 3}}),
        ("-> 3 < P[3:0];", {"param": {"name": "P", "range": "3-0", "greaterThan": 3}}),
        ("-> 3 < $array_size(A);", {"param": {"name": "A", "size": True, "greaterThan": 3}}),
        ("-> (P) == (3);", {"param": {"name": "P", "equal": 3}}),
        ("-> 1 < 3;", True),
        ("-> 1 > 3;", False),
        ("-> implemented?(ExtensionName::Xowner);", {"extension": {"name": "Xowner"}}),
        (
            '-> implemented_version?(ExtensionName::Xowner, ">= 2.0");',
            {"extension": {"name": "Xowner", "version": ">= 2.0"}},
        ),
        ("-> xlen() == 32;", {"xlen": 32}),
        ("-> 64 != xlen();", {"not": {"xlen": 64}}),
    ],
)
def test_additional_translation_boundaries(symtab, text, data):
    assert normalize(compile_idl_condition(text, symtab)) == normalize(parse_condition(data))


def test_scope_and_array_values_are_independent_on_success_and_failure(symtab):
    symtab.push()
    local = Var("local", Type(TypeKind.BITS, width=32), 9)
    symtab.add("local", local)
    array = symtab.get("A")
    before = list(array.value)
    for text in ("-> P == 3;", "-> unknown_function();"):
        try:
            compile_idl_condition(text, symtab)
        except IdlError:
            assert "unknown_function" in text
        assert symtab.levels == 2
        assert symtab.get("local") is local
        assert local.value == 9
        assert symtab.get("P").value == 64
        assert symtab.get("A") is array
        assert array.value == before


def test_loop_update_executes_before_next_translation(symtab):
    result = compile_idl_condition("for (U32 i = 0; i < 3; i = i + 2) { -> P > i; }", symtab)
    assert result.to_data() == {
        "allOf": [
            {"param": {"name": "P", "greaterThan": 0}},
            {"param": {"name": "P", "greaterThan": 2}},
        ]
    }
    assert symtab.get("i") is None


def test_loop_ceiling_is_source_aware(symtab):
    text = "for (U32 i = 0; i < 3; i++) { -> P > i; }"
    with pytest.raises(IdlError, match="max_loop_iterations=2") as error:
        compile_idl_condition(
            text,
            symtab,
            source=IdlSource(text, label="loop-overlay.yaml", starting_line=20),
            max_loop_iterations=2,
        )
    assert "loop-overlay.yaml" in str(error.value)
    assert symtab.levels == 1
    assert symtab.get("i") is None


@pytest.mark.parametrize(
    "text",
    [
        "for (U32 i = 0; i < 3; i = i) { -> P > i; }",
        "for (U32 i = 0; i < P; i++) { -> A[0] > i; }",
        "-> P == A[Q];",
        "-> P == P;",
        "-> P == true;",
        "-> 4 == true;",
        "-> P == 64'bx;",
        "-> xlen() > 32;",
        "-> xlen() == 16;",
        "-> implemented?(P);",
        "-> implemented?(ExtensionName::Missing);",
        '-> implemented_version?(ExtensionName::Xowner, "nonsense");',
        "-> Q ? true : false;",
        "-> (P & 1) == 1;",
    ],
)
def test_no_unknown_or_unsupported_silent_defaults(symtab, text):
    with pytest.raises(IdlError) as error:
        compile_idl_condition(text, symtab, source="unsupported-overlay.yaml")
    assert "unsupported-overlay.yaml" in str(error.value)
    assert symtab.get("P").value == 64


def test_reason_and_all_logical_operators_survive_resolution(symtab):
    original = parse_condition(
        {
            "allOf": [
                {"idl()": "-> P > 3;", "reason": "minimum width"},
                {
                    "anyOf": [
                        {"oneOf": [{"idl()": "-> Q;"}, False]},
                        {"noneOf": [{"idl()": "-> !Q;"}, False]},
                    ]
                },
                {"not": {"idl()": "-> P < 8;"}},
                {"if": {"idl()": "-> Q;"}, "then": {"param": {"name": "P", "equal": 64}}},
            ]
        },
        source="metadata.yaml",
    )
    resolved = resolve_idl_conditions(original, symtab)
    assert isinstance(resolved, AllOf)
    assert resolved.children[0].reason == "minimum width"
    assert resolved.children[0].source == "metadata.yaml"
    assert not resolved.has_unresolved
    assert original.has_unresolved
    assert resolved.evaluate(EvaluationContext(parameters={"Q": True, "P": 64})) is TruthValue.TRUE
    assert resolved.evaluate(EvaluationContext(parameters={"Q": True, "P": 7})) is TruthValue.FALSE


def test_nested_leaf_uses_exact_captured_yaml_scalar_source(symtab):
    text = (
        "kind: extension\n"
        "name: Xowner\n"
        "versions:\n"
        "  - version: '1.0'\n"
        "requirements:\n"
        "  allOf:\n"
        "    - idl(): |\n"
        "        -> unknown_function();\n"
        "    - true\n"
    )
    parsed = parse_yaml(text, source="captured.yaml", layer="overlay[0]")
    condition = parse_condition(
        parsed.value["requirements"], source="captured.yaml", path=("requirements",)
    )
    leaf = condition.children[0]
    assert leaf.source_path == ("requirements", "allOf", 0, "idl()")
    span = parsed.sources.at(*leaf.source_path)
    with pytest.raises(IdlError) as error:
        resolve_idl_conditions(
            condition,
            symtab,
            source_for=lambda current: idl_field_source(
                text, span, current.text, label="overlay[0]:captured.yaml"
            ),
        )
    assert "overlay[0]:captured.yaml" in str(error.value)
    assert error.value.node.lineno == 8
    assert error.value.node.column == 12


def _extension(name, *, requirements=None, versions=None):
    return {
        "kind": "extension",
        "name": name,
        "versions": versions or [{"version": "1.0", "state": "ratified"}],
        **({"requirements": requirements} if requirements is not None else {}),
    }


def _configuration(**changes):
    return Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "condition-integration",
            "description": "condition integration",
            "mandatory_extensions": [{"name": "Xbase", "version": ">= 1"}],
            **changes,
        }
    )


def _database(*, owner_requirement=None, parameter_requirement=None, versions=None):
    return ResolvedDatabase(
        {
            "ext/Xbase.yaml": _extension("Xbase"),
            "ext/Xowner.yaml": _extension(
                "Xowner", requirements=owner_requirement, versions=versions
            ),
            "param/P.yaml": {
                "kind": "parameter",
                "name": "P",
                "definedBy": {"extension": {"name": "Xowner"}},
                "schema": {"type": "integer", "minimum": 1, "maximum": 4},
                **(
                    {"requirements": parameter_requirement}
                    if parameter_requirement is not None
                    else {}
                ),
            },
            "inst/owned.yaml": {
                "kind": "instruction",
                "name": "owned",
                "definedBy": {"idl()": "-> implemented?(ExtensionName::Xowner);"},
            },
        }
    )


@pytest.mark.parametrize("kind", ["extension", "parameter"])
def test_absent_owner_gates_false_idl_requirements(kind):
    kwargs = {
        "owner_requirement" if kind == "extension" else "parameter_requirement": {
            "idl()": "-> false;"
        }
    }
    database = _database(**kwargs)
    absent = database.configure(
        _configuration(prohibited_extensions=[{"name": "Xowner", "version": ">= 0"}])
    )
    assert absent.check().status is ArchitectureCheckStatus.VALID
    assert absent.object_presence(database.instruction("owned")) is QueryPresence.ABSENT
    present = database.configure(
        _configuration(mandatory_extensions=[{"name": "Xowner", "version": ">= 1"}])
    )
    assert present.check().status is ArchitectureCheckStatus.UNSAT


def test_version_requirement_is_gated_by_its_exact_version():
    database = _database(
        versions=[
            {"version": "1.0", "state": "ratified"},
            {"version": "2.0", "state": "ratified", "requirements": {"idl()": "-> false;"}},
        ]
    )
    architecture = database.configure(
        _configuration(mandatory_extensions=[{"name": "Xowner", "version": "= 1.0"}])
    )
    assert architecture.check().status is ArchitectureCheckStatus.VALID
    assert architecture.extension_presence("Xowner", "= 2.0") is QueryPresence.ABSENT
    assert architecture.object_presence(database.instruction("owned")) is QueryPresence.MANDATORY


def test_mixed_configuration_tree_keeps_plain_constraints():
    database = _database()
    requirements = {
        "allOf": [
            {"idl()": "-> P > 1;"},
            {"param": {"name": "P", "lessThan": 3}},
        ]
    }
    valid = database.configure(_configuration(params={"P": 2}, requirements=requirements))
    assert valid.check().status is ArchitectureCheckStatus.VALID
    invalid = database.configure(_configuration(params={"P": 3}, requirements=requirements))
    assert invalid.check().status is ArchitectureCheckStatus.UNSAT


def test_invalid_custom_idl_is_an_actionable_diagnostic():
    database = _database(owner_requirement={"idl()": "-> unknown_function();"})
    architecture = database.configure(_configuration())
    check = architecture.check()
    assert check.status is ArchitectureCheckStatus.UNSAT
    diagnostic = next(item for item in check.diagnostics if item.code == "invalid-idl-condition")
    assert diagnostic.source == "ext/Xowner.yaml"
    assert "unknown_function" in diagnostic.message
    assert "ext/Xowner.yaml" in diagnostic.message
    assert not any(item.code == "idl-deferred" for item in check.diagnostics)


def test_architecture_uses_captured_overlay_source_for_nested_requirements():
    text = (
        "kind: extension\n"
        "name: Xowner\n"
        "versions:\n"
        "  - version: '1.0'\n"
        "requirements:\n"
        "  allOf:\n"
        "    - idl(): |\n"
        "        -> unknown_function();\n"
        "    - true\n"
    )
    parsed = parse_yaml(text, source="ext/Xowner.yaml", layer="overlay[0]")
    documents = dict(_database().documents)
    documents["ext/Xowner.yaml"] = parsed.value
    database = ResolvedDatabase(
        documents,
        sources={"ext/Xowner.yaml": parsed.sources},
        source_texts={("overlay[0]", "ext/Xowner.yaml"): text},
    )
    check = database.configure(_configuration()).check()
    assert check.status is ArchitectureCheckStatus.UNSAT
    diagnostic = next(item for item in check.diagnostics if item.code == "invalid-idl-condition")
    assert "overlay[0]:ext/Xowner.yaml" in diagnostic.message
    assert "On line 8" in diagnostic.message


def test_architecture_uses_captured_configuration_source_offsets(monkeypatch):
    text = (
        "$schema: config_schema.json#\n"
        "kind: architecture configuration\n"
        "name: captured-config\n"
        "description: Captured config source\n"
        "type: partially configured\n"
        "mandatory_extensions:\n"
        "  - name: Xbase\n"
        "    version: '>= 1'\n"
        "requirements:\n"
        "  idl(): |\n"
        "    -> unknown_function();\n"
    )
    configuration = Configuration.from_yaml(text, source="removed/config.yaml")
    database = _database()

    def no_database_source(*args, **kwargs):
        pytest.fail("configuration IDL must use its own captured YAML text")

    monkeypatch.setattr(ResolvedDatabase, "source_text", no_database_source)
    architecture = database.configure(configuration)
    check = architecture.check()
    assert check.status is ArchitectureCheckStatus.UNSAT
    diagnostic = next(item for item in check.diagnostics if item.code == "invalid-idl-condition")
    assert "removed/config.yaml" in diagnostic.message
    assert "On line 11" in diagnostic.message
    with pytest.raises(IdlError) as error:
        architecture._resolve_condition(
            parse_condition(configuration.requirements, path=("requirements",)),
            sources=configuration.sources,
            source_text=configuration.source_text,
        )
    assert error.value.node.lineno == 11
    assert error.value.node.column == 8


def test_configured_array_runtime_translation_remains_symbolic():
    documents = dict(_database().documents)
    documents["param/EN.yaml"] = {
        "kind": "parameter",
        "name": "EN",
        "definedBy": {"extension": {"name": "Xbase"}},
        "schema": {
            "type": "array",
            "items": {"type": "boolean"},
            "minItems": 2,
            "maxItems": 2,
        },
    }
    architecture = ResolvedDatabase(documents).configure(
        _configuration(params={"EN": [False, True]})
    )
    table = symbol_table(architecture)
    before = table.snapshot_values()
    condition = compile_idl_condition("-> EN[0] || EN[1];", table)
    expected = parse_condition(
        {
            "anyOf": [
                {"param": {"name": "EN", "index": 0, "equal": True}},
                {"param": {"name": "EN", "index": 1, "equal": True}},
            ]
        }
    )
    assert normalize(condition) == normalize(expected)
    assert table.snapshot_values() == before
