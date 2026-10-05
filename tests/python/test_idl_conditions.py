# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Black-box slice 18 contract, written before the Python translator."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from udb import Configuration, Database, QueryPresence
from udb.conditions import EvaluationContext, TruthValue, normalize, parse_condition
from udb.idl import IdlSource
from udb.idl.errors import IdlError
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import BOOL_TYPE, Qualifier, Type, TypeKind

ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((Path(__file__).with_name("data") / "idl" / "conditions.json").read_text())
CONFIGS = ("_", "rv32", "rv64", "qc_iu")


def _compile(text, symtab, **kwargs):
    from udb.idl_conditions import compile_idl_condition

    return compile_idl_condition(text, symtab, **kwargs)


def _symbol_table():
    bits = Type(TypeKind.BITS, width=64, qualifiers=(Qualifier.CONST,))
    boolean = BOOL_TYPE.qualify(Qualifier.CONST)
    array = Type(TypeKind.ARRAY, width=4, sub_type=bits, qualifiers=(Qualifier.CONST,))
    return SymbolTable(
        IdlEnvironment(
            builtin_global_vars=(
                Var("P", bits, param=True),
                Var("Q", boolean, param=True),
                Var("A", array, param=True),
            )
        )
    )


@pytest.mark.parametrize(
    ("text", "data"),
    [
        ("-> true;", True),
        ("-> false;", False),
        ("-> Q;", {"param": {"name": "Q", "equal": True}}),
        ("-> !Q;", {"not": {"param": {"name": "Q", "equal": True}}}),
        ("-> P == 3;", {"param": {"name": "P", "equal": 3}}),
        ("-> P != 3;", {"param": {"name": "P", "notEqual": 3}}),
        ("-> P < 3;", {"param": {"name": "P", "lessThan": 3}}),
        ("-> P <= 3;", {"param": {"name": "P", "lessThanOrEqual": 3}}),
        ("-> P > 3;", {"param": {"name": "P", "greaterThan": 3}}),
        ("-> P >= 3;", {"param": {"name": "P", "greaterThanOrEqual": 3}}),
        ("-> 3 < P;", {"param": {"name": "P", "greaterThan": 3}}),
        ("-> 3 <= P;", {"param": {"name": "P", "greaterThanOrEqual": 3}}),
        ("-> 3 > P;", {"param": {"name": "P", "lessThan": 3}}),
        ("-> 3 >= P;", {"param": {"name": "P", "lessThanOrEqual": 3}}),
        ("-> 3 == P;", {"param": {"name": "P", "equal": 3}}),
        ("-> 3 < A[0];", {"param": {"name": "A", "index": 0, "greaterThan": 3}}),
        ("-> A[1] == 4;", {"param": {"name": "A", "index": 1, "equal": 4}}),
        ("-> P[3:0] == 4;", {"param": {"name": "P", "range": "3-0", "equal": 4}}),
        ("-> $array_size(A) == 4;", {"param": {"name": "A", "size": True, "equal": 4}}),
        ("-> $array_includes?(A, 3);", {"param": {"name": "A", "includes": 3}}),
        (
            "Q -> P > 3;",
            {
                "if": {"param": {"name": "Q", "equal": True}},
                "then": {"param": {"name": "P", "greaterThan": 3}},
            },
        ),
        ("for (U32 i = 0; i < 0; i++) { -> P > i; }", True),
        (
            "for (U32 i = 0; i < 3; i++) { -> A[i] > i; }",
            {"allOf": [{"param": {"name": "A", "index": i, "greaterThan": i}} for i in range(3)]},
        ),
    ],
)
def test_synthetic_translation(text, data):
    symtab = _symbol_table()
    before = symtab.snapshot_values()
    result = _compile(text, symtab)
    assert normalize(result) == normalize(parse_condition(data))
    assert not result.has_unresolved
    assert symtab.levels == 1
    assert symtab.get("i") is None
    assert symtab.snapshot_values() == before


def test_configured_parameter_stays_symbolic():
    symtab = _symbol_table()
    symtab.get("P").value = 64
    result = _compile("-> P == 64;", symtab)
    assert result.to_data() == {"param": {"name": "P", "equal": 64}}
    assert result.evaluate(EvaluationContext(parameters={"P": 32})) is TruthValue.FALSE


def test_nested_idl_resolution_preserves_plain_siblings_and_gating():
    from udb.idl_conditions import resolve_idl_conditions

    original = parse_condition(
        {
            "if": {"param": {"name": "Q", "equal": True}},
            "then": {
                "allOf": [
                    {"idl()": "-> P > 3;"},
                    {"param": {"name": "P", "lessThan": 8}},
                ]
            },
        }
    )
    result = resolve_idl_conditions(original, _symbol_table())
    assert original.has_unresolved
    assert not result.has_unresolved
    assert result.evaluate(EvaluationContext(parameters={"Q": False, "P": 0})) is TruthValue.TRUE
    assert result.evaluate(EvaluationContext(parameters={"Q": True, "P": 0})) is TruthValue.FALSE
    assert result.evaluate(EvaluationContext(parameters={"Q": True, "P": 5})) is TruthValue.TRUE
    assert result.evaluate(EvaluationContext(parameters={"Q": True, "P": 9})) is TruthValue.FALSE


@pytest.mark.parametrize(
    "text",
    [
        "-> DOES_NOT_EXIST;",
        "-> unknown_function();",
        "-> P == A[Q];",
        "for (U32 i = 0; i < 3; i--) { -> P > i; }",
        "for (U32 i = 0; true; i++) { -> P > i; }",
    ],
)
def test_invalid_or_unbounded_constraint_is_explicit_and_scope_safe(text):
    symtab = _symbol_table()
    source = IdlSource(text, label="overlay/constraint.yaml", starting_line=40)
    with pytest.raises(IdlError) as error:
        _compile(text, symtab, source=source)
    assert "overlay/constraint.yaml" in str(error.value)
    assert symtab.levels == 1
    assert symtab.get("i") is None


def test_compilation_is_deterministic_and_isolated():
    def compile_one(value):
        symtab = _symbol_table()
        symtab.get("P").value = value
        return _compile("for (U32 i = 0; i < 3; i++) { -> P > i; }", symtab).to_data()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compile_one, [0, 1, 64, None] * 2))
    assert all(result == results[0] for result in results)


@pytest.fixture(scope="module")
def database():
    return Database.bundled().resolve()


@pytest.fixture(scope="module", params=CONFIGS)
def architecture(request, database):
    config = Configuration.from_file(ROOT / "cfgs" / f"{request.param}.yaml")
    if request.param == "qc_iu":
        database = Database.from_path(
            ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas"
        ).resolve(overlays=(ROOT / "spec/custom/isa/qc_iu",))
    return database.configure(config)


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_live_database_translation_matches_frozen_expectation(case, architecture):
    from udb.idl_environment import symbol_table

    expected = next(
        result for result in CORPUS["results"][architecture.name] if result["id"] == case["id"]
    )
    assert "error" not in expected
    result = _compile(case["text"], symbol_table(architecture))
    assert normalize(result) == normalize(parse_condition(expected["to_h"]))
    assert not result.has_unresolved


def test_generic_configurations_have_no_idl_deferrals(database):
    for name in ("_", "rv32", "rv64"):
        arch = database.configure(Configuration.builtin(name))
        check = arch.check()
        assert check.status.name == "VALID"
        assert not any(item.code == "idl-deferred" for item in check.diagnostics)


def test_rv32_sxlen_invariant_closes_supervisor_presence_gap(database):
    arch = database.configure(Configuration.builtin("rv32"))
    for name in ("Sv39", "Sv48", "Sv57", "Svnapot", "Svpbmt", "Svrsw60t59b", "Svukte"):
        assert arch.extension_presence(name) is QueryPresence.ABSENT
