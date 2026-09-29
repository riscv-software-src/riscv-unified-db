# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import shutil
import subprocess
from itertools import product
from pathlib import Path

import pytest

from udb.conditions import (
    FALSE,
    TRUE,
    AllOf,
    AnyOf,
    ConditionError,
    EvaluationContext,
    ExtensionTerm,
    FreeTerm,
    ParameterOperator,
    ParameterTerm,
    TruthValue,
    UnresolvedIdlCondition,
    XlenTerm,
    all_of,
    any_of,
    implies,
    negate,
    normalize,
    not_,
    parse_condition,
    partial_evaluate,
)
from udb.database import Database
from udb.domains import ParameterDomain
from udb.schema import SchemaStore
from udb.versions import ExtensionVersionSet, parse_version_requirements

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_condition_oracle.rb")
RUBY_DEFECTS = Path(__file__).with_name("ruby_condition_defects.rb")


def _condition_documents(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"definedBy", "requirements"} and (
                isinstance(child, bool)
                or (
                    isinstance(child, dict)
                    and any(
                        operator in child
                        for operator in (
                            "allOf",
                            "anyOf",
                            "oneOf",
                            "noneOf",
                            "not",
                            "if",
                            "extension",
                            "param",
                            "xlen",
                            "idl()",
                        )
                    )
                )
            ):
                yield child
            yield from _condition_documents(child)
    elif isinstance(value, list):
        for child in value:
            yield from _condition_documents(child)


def test_condition_round_trip_canonicalizes_version_requirements() -> None:
    source = {
        "allOf": [
            {"xlen": 64},
            {"extension": {"name": "A", "version": ">= 1.0"}},
            {
                "if": {"param": {"name": "MXLEN", "equal": 64}},
                "then": {"not": {"extension": {"name": "E"}}},
            },
        ]
    }

    condition = parse_condition(source)

    assert condition.to_data() == {
        "allOf": [
            {"xlen": 64},
            {"extension": {"name": "A", "version": ">= 1.0.0"}},
            {
                "if": {"param": {"name": "MXLEN", "equal": 64}},
                "then": {"not": {"extension": {"name": "E", "version": ">= 0.0.0"}}},
            },
        ]
    }


@pytest.mark.parametrize("constant", [False, True])
def test_condition_schema_accepts_serialized_boolean_constants(constant: bool) -> None:
    parameter = next(
        item for item in Database.bundled().objects("parameter") if item.name == "MXLEN"
    ).to_dict()
    parameter["definedBy"] = constant

    SchemaStore(REPOSITORY_ROOT / "spec/schemas").validate(parameter)


def test_every_schema_backed_condition_in_the_bundled_corpus_parses() -> None:
    count = 0
    for record in Database.bundled().objects():
        for data in _condition_documents(record.to_dict()):
            condition = parse_condition(data, source=record.path.as_posix())
            assert parse_condition(condition.to_data()) == condition
            count += 1

    assert count >= 2_800


def test_boolean_builders_use_mathematical_identities_and_flatten() -> None:
    xlen = XlenTerm(64)

    assert all_of() == TRUE
    assert any_of() == FALSE
    assert all_of(TRUE, xlen, AllOf((xlen, TRUE))) == xlen
    assert any_of(FALSE, xlen, xlen) == xlen
    assert negate(negate(xlen)) == xlen
    assert implies(FALSE, xlen) == TRUE


def test_normalization_is_idempotent_and_applies_de_morgan() -> None:
    a = FreeTerm("a")
    b = FreeTerm("b")
    expression = negate(AllOf((a, AllOf((TRUE, b, a)))))
    normalized = normalize(expression)

    assert normalized == any_of(negate(a), negate(b))
    assert normalize(normalized) == normalized
    assert parse_condition(normalized.to_data()) == normalized

    for left, right in product((False, True), repeat=2):
        context = EvaluationContext(free_terms={"a": left, "b": right})
        assert expression.evaluate(context) is normalized.evaluate(context)


def test_de_morgan_laws_hold_for_every_boolean_assignment() -> None:
    a = FreeTerm("a")
    b = FreeTerm("b")
    conjunction = AllOf((a, b))
    disjunction = parse_condition({"anyOf": [a.to_data(), b.to_data()]})

    for left, right in product((False, True), repeat=2):
        context = EvaluationContext(free_terms={"a": left, "b": right})
        assert negate(conjunction).evaluate(context) is any_of(negate(a), negate(b)).evaluate(
            context
        )
        assert negate(disjunction).evaluate(context) is all_of(negate(a), negate(b)).evaluate(
            context
        )


def test_normalization_and_serialization_properties_cover_boolean_algebra() -> None:
    a = FreeTerm("a")
    b = FreeTerm("b")
    expressions = (
        TRUE,
        FALSE,
        a,
        negate(a),
        AllOf((a, b)),
        parse_condition({"anyOf": [a.to_data(), b.to_data()]}),
        parse_condition({"oneOf": [a.to_data(), b.to_data()]}),
        parse_condition({"noneOf": [a.to_data(), b.to_data()]}),
        implies(a, b),
        negate(implies(a, b)),
    )

    for expression in expressions:
        normalized = normalize(expression)
        assert normalize(normalized) == normalized
        assert parse_condition(normalized.to_data()) == normalized
        for left, right in product((False, True), repeat=2):
            context = EvaluationContext(free_terms={"a": left, "b": right})
            assert expression.evaluate(context) is normalized.evaluate(context)


@pytest.mark.parametrize(
    "data",
    [
        {"extension": {"allOf": [{"name": "A"}, {"name": "B"}]}},
        {"extension": {"anyOf": [{"name": "A"}, {"name": "B"}]}},
        {"extension": {"oneOf": [{"name": "A"}, {"name": "B"}]}},
        {"extension": {"noneOf": [{"name": "A"}, {"name": "B"}]}},
        {"extension": {"not": {"name": "A"}}},
        {
            "extension": {
                "if": {"param": {"name": "P", "equal": 1}},
                "then": {"name": "A"},
            }
        },
        {
            "param": {
                "allOf": [
                    {"name": "P", "greaterThan": 0},
                    {"name": "P", "lessThan": 3},
                ]
            }
        },
    ],
)
def test_nested_and_conditional_condition_grammar_round_trips(data: dict) -> None:
    condition = parse_condition(data)
    assert parse_condition(condition.to_data()) == condition


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ({"allOf": [{"xlen": 64}, {"extension": {"name": "A"}}]}, TruthValue.UNKNOWN),
        ({"anyOf": [{"xlen": 32}, {"extension": {"name": "A"}}]}, TruthValue.UNKNOWN),
        ({"oneOf": [{"xlen": 64}, {"extension": {"name": "A"}}]}, TruthValue.UNKNOWN),
        ({"noneOf": [{"xlen": 32}, {"extension": {"name": "A"}}]}, TruthValue.UNKNOWN),
        (
            {"if": {"extension": {"name": "A"}}, "then": {"xlen": 32}},
            TruthValue.UNKNOWN,
        ),
    ],
)
def test_partial_evaluation_uses_three_valued_logic(condition: dict, expected: TruthValue) -> None:
    context = EvaluationContext(xlen=64)
    assert parse_condition(condition).evaluate(context) is expected


def test_exactly_one_rejects_two_known_true_children_even_with_unknown() -> None:
    condition = parse_condition(
        {
            "oneOf": [
                {"xlen": 64},
                {"param": {"name": "MXLEN", "equal": 64}},
                {"extension": {"name": "A"}},
            ]
        }
    )
    context = EvaluationContext(xlen=64, parameters={"MXLEN": 64})
    assert condition.evaluate(context) is TruthValue.FALSE


def test_extension_evaluation_distinguishes_partial_and_full_worlds() -> None:
    term = ExtensionTerm("A", parse_version_requirements(">= 1.0"))

    assert term.evaluate(EvaluationContext()) is TruthValue.UNKNOWN
    assert term.evaluate(EvaluationContext(closed_world_extensions=True)) is TruthValue.FALSE
    assert term.evaluate(EvaluationContext(extensions={"A": "1.1"})) is TruthValue.TRUE


@pytest.mark.parametrize(
    ("data", "parameters", "expected"),
    [
        ({"name": "P", "equal": 3}, {"P": 3}, TruthValue.TRUE),
        ({"name": "P", "notEqual": 3}, {"P": 3}, TruthValue.FALSE),
        ({"name": "P", "greaterThan": 2}, {"P": 3}, TruthValue.TRUE),
        ({"name": "P", "lessThanOrEqual": 2}, {"P": 3}, TruthValue.FALSE),
        ({"name": "P", "oneOf": [2, 3]}, {"P": 3}, TruthValue.TRUE),
        ({"name": "P", "includes": 3}, {"P": [2, 3]}, TruthValue.TRUE),
        ({"name": "P", "index": 1, "equal": 3}, {"P": [2, 3]}, TruthValue.TRUE),
        ({"name": "P", "size": True, "equal": 2}, {"P": [2, 3]}, TruthValue.TRUE),
        ({"name": "P", "range": "3-1", "equal": 0b101}, {"P": 0b1011}, TruthValue.TRUE),
    ],
)
def test_parameter_comparisons(data: dict, parameters: dict, expected: TruthValue) -> None:
    condition = parse_condition({"param": data})
    assert condition.evaluate(EvaluationContext(parameters=parameters)) is expected


def test_out_of_range_array_index_is_false_instead_of_raising() -> None:
    condition = parse_condition({"param": {"name": "P", "index": 2, "equal": 1}})
    assert condition.evaluate(EvaluationContext(parameters={"P": [1]})) is TruthValue.FALSE


def test_partial_evaluate_keeps_only_unknown_expression() -> None:
    condition = all_of(
        XlenTerm(64),
        ExtensionTerm("A"),
        ParameterTerm("P", ParameterOperator.EQUAL, 1),
    )
    result = partial_evaluate(condition, EvaluationContext(xlen=64, parameters={"P": 1}))
    assert result == ExtensionTerm("A")


def test_idl_condition_is_an_explicit_unknown_marker() -> None:
    condition = parse_condition(
        {"idl()": "MXLEN == 32 -> xlen() == 32;", "reason": "width rule"},
        source="param/MXLEN.yaml",
    )
    assert isinstance(condition, UnresolvedIdlCondition)
    assert condition.evaluate(EvaluationContext()) is TruthValue.UNKNOWN
    assert condition.to_data()["reason"] == "width rule"
    assert condition.has_unresolved
    assert not_(condition) == negate(condition)
    assert not XlenTerm(64).has_unresolved


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"xlen": 64, "extension": {"name": "A"}},
        {"allOf": [{"xlen": 32}]},
        {"if": {"xlen": 32}},
        {"param": {"name": "P", "equal": 1, "greaterThan": 0}},
        {"param": {"name": "P", "oneOf": []}},
        {"param": {"name": "P", "oneOf": [1]}},
        {"param": {"name": "P", "size": False, "equal": 1}},
        {"param": {"name": "P", "index": -1, "equal": 1}},
        {"param": {"name": "P", "equal": 1, "reason": 3}},
        {"extension": {"allOf": [{"name": "A"}, {"name": "B"}], "extra": True}},
        {"free": ""},
    ],
)
def test_malformed_conditions_are_rejected(data: dict) -> None:
    with pytest.raises(ConditionError):
        parse_condition(data, source="test.yaml")


def _solver_module():
    return pytest.importorskip("udb.solver")


def test_solver_checks_domains_implication_and_equivalence() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    context = solver_api.SolverContext(
        extension_versions={"A": ("1.0", "2.0")},
        parameter_domains={
            "P": ParameterDomain.from_schema({"type": "integer", "minimum": 0, "maximum": 5})
        },
    )
    a = parse_condition({"extension": {"name": "A", "version": ">= 2.0"}})
    p = parse_condition({"param": {"name": "P", "greaterThan": 4}})

    assert solver_api.is_satisfiable(all_of(a, p), context)
    assert solver_api.implies(p, {"param": {"name": "P", "greaterThan": 3}}, context)
    assert solver_api.equivalent(implies(a, p), any_of(negate(a), p), context)


def test_solver_returns_labeled_unsat_core_and_minimal_conflict() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    solver = solver_api.ConditionSolver(solver_api.SolverContext())
    solver.add(XlenTerm(32), label="requires RV32")
    solver.add(XlenTerm(64), label="requires RV64")

    assert solver.check() is solver_api.SolverStatus.UNSAT
    assert set(solver.unsat_core()) == {"requires RV32", "requires RV64"}
    assert set(solver.minimal_conflict()) == {"requires RV32", "requires RV64"}


def test_solver_marks_satisfiable_result_unknown_when_idl_is_reached() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    solver = solver_api.ConditionSolver()
    solver.add(UnresolvedIdlCondition("-> SOME_PARAMETER;"))
    assert solver.check() is solver_api.SolverStatus.UNKNOWN

    definitely_true = solver_api.ConditionSolver()
    definitely_true.add(parse_condition({"anyOf": [True, {"idl()": "-> UNKNOWN;"}]}))
    assert definitely_true.check() is solver_api.SolverStatus.SAT


def test_extra_condition_domain_constraints_survive_solver_pop() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    context = solver_api.SolverContext(
        parameter_domains={
            "P": ParameterDomain.from_schema({"type": "integer", "minimum": 0, "maximum": 5})
        }
    )
    condition = ParameterTerm("P", ParameterOperator.GREATER_THAN, 10)
    solver = solver_api.ConditionSolver(context)

    assert solver.check([condition]) is solver_api.SolverStatus.UNSAT
    assert solver.check([condition]) is solver_api.SolverStatus.UNSAT


def test_solver_consumes_real_extension_version_metadata() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    versions = ExtensionVersionSet.from_metadata(
        "A",
        [
            {"version": "1.0"},
            {"version": "1.1"},
            {"version": "2.0", "breaking": True},
        ],
    )
    compatible = parse_condition({"extension": {"name": "A", "version": "~> 1.0"}})

    allowed = solver_api.ConditionSolver(
        solver_api.SolverContext(extension_versions={"A": versions}, fixed_extensions={"A": "1.1"})
    )
    allowed.add(compatible)
    assert allowed.check() is solver_api.SolverStatus.SAT

    breaking = solver_api.ConditionSolver(
        solver_api.SolverContext(extension_versions={"A": versions}, fixed_extensions={"A": "2.0"})
    )
    breaking.add(compatible)
    assert breaking.check() is solver_api.SolverStatus.UNSAT


def test_solver_consumes_real_scalar_and_array_domains() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    integer = ParameterDomain.from_schema(
        {"type": "integer", "minimum": 0, "maximum": 5, "not": {"const": 3}}
    )
    array = ParameterDomain.from_schema(
        {
            "type": "array",
            "items": [{"const": 1}, {"const": "two"}],
            "additionalItems": False,
            "minItems": 0,
            "maxItems": 2,
        }
    )
    context = solver_api.SolverContext(parameter_domains={"P": integer, "A": array})

    assert not solver_api.is_satisfiable(
        parse_condition({"param": {"name": "P", "equal": 3}}), context
    )
    assert solver_api.is_satisfiable(
        parse_condition({"param": {"name": "A", "equal": [1, "two"]}}), context
    )
    assert solver_api.is_satisfiable(
        parse_condition({"param": {"name": "A", "size": True, "equal": 0}}), context
    )
    assert not solver_api.is_satisfiable(
        parse_condition({"param": {"name": "A", "index": 1, "equal": "wrong"}}), context
    )


def test_solver_rejects_impractically_large_materialized_arrays() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    array = ParameterDomain.from_schema(
        {"type": "array", "items": {"type": "integer"}, "maxItems": 5000}
    )
    solver = solver_api.ConditionSolver(solver_api.SolverContext(parameter_domains={"A": array}))

    with pytest.raises(solver_api.SolverError, match="exceeds the solver limit"):
        solver.add(parse_condition({"param": {"name": "A", "size": True, "equal": 1}}))


def test_solver_links_xlen_to_mxlen() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    domain = ParameterDomain.from_schema({"type": "integer", "enum": [32, 64]})
    context = solver_api.SolverContext(
        parameter_domains={"MXLEN": domain}, fixed_parameters={"MXLEN": 32}
    )

    assert not solver_api.is_satisfiable(XlenTerm(64), context)
    assert solver_api.is_satisfiable(XlenTerm(32), context)


def test_solver_contexts_are_independent_and_models_are_concrete() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    domain = ParameterDomain.from_schema({"type": "integer", "minimum": 0, "maximum": 5})
    versions = {"A": ("1.0", "2.0")}
    first = solver_api.ConditionSolver(
        solver_api.SolverContext(
            extension_versions=versions,
            parameter_domains={"P": domain},
            fixed_extensions={"A": "1.0"},
            fixed_parameters={"P": 2},
            xlen=32,
        )
    )
    second = solver_api.ConditionSolver(
        solver_api.SolverContext(
            extension_versions=versions,
            parameter_domains={"P": domain},
            fixed_extensions={"A": "2.0"},
            fixed_parameters={"P": 4},
            xlen=64,
        )
    )
    first.add(parse_condition({"param": {"name": "P", "equal": 2}}))
    second.add(parse_condition({"param": {"name": "P", "equal": 4}}))

    assert first.check() is solver_api.SolverStatus.SAT
    assert second.check() is solver_api.SolverStatus.SAT
    assert first.model().xlen == 32
    assert first.model().extensions == {"A": "1.0.0"}
    assert first.model().parameters == {"P": 2}
    assert second.model().xlen == 64
    assert second.model().extensions == {"A": "2.0.0"}
    assert second.model().parameters == {"P": 4}


def test_free_terms_have_concrete_and_solver_context_values() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    term = FreeTerm("generated-clause")

    assert term.evaluate(EvaluationContext()) is TruthValue.UNKNOWN
    assert term.evaluate(EvaluationContext(free_terms={term.name: True})) is TruthValue.TRUE
    solver = solver_api.ConditionSolver(
        solver_api.SolverContext(fixed_free_terms={term.name: False})
    )
    solver.add(term)
    assert solver.check() is solver_api.SolverStatus.UNSAT


def test_finite_evaluator_agrees_with_z3_on_small_domains() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    context = solver_api.SolverContext(
        extension_versions={"A": ("1.0", "2.0")},
        parameter_domains={
            "P": ParameterDomain.from_schema({"type": "integer", "enum": [0, 1, 2]})
        },
    )
    a = parse_condition({"extension": {"name": "A", "version": ">= 2.0"}})
    p = parse_condition({"param": {"name": "P", "greaterThan": 0}})
    free = FreeTerm("choice")
    expressions = (
        all_of(a, p, free),
        any_of(negate(a), p),
        implies(all_of(a, free), p),
        parse_condition({"oneOf": [a.to_data(), p.to_data(), free.to_data()]}),
        parse_condition({"noneOf": [a.to_data(), p.to_data(), free.to_data()]}),
    )

    for expression in expressions:
        finite = solver_api.finite_check(expression, context)
        solver = solver_api.ConditionSolver(context)
        solver.add(expression)
        assert finite is solver.check()


def test_integer_parameter_comparisons_use_json_numeric_equality() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    domain = ParameterDomain.from_schema({"type": "integer", "const": 1})
    context = solver_api.SolverContext(parameter_domains={"P": domain})
    numeric = parse_condition({"param": {"name": "P", "equal": 1.0}})
    boolean = parse_condition({"param": {"name": "P", "equal": True}})

    assert numeric.evaluate(EvaluationContext(parameters={"P": 1})) is TruthValue.TRUE
    assert boolean.evaluate(EvaluationContext(parameters={"P": 1})) is TruthValue.FALSE
    assert solver_api.finite_check(numeric, context) is solver_api.SolverStatus.SAT
    assert solver_api.finite_check(boolean, context) is solver_api.SolverStatus.UNSAT
    assert solver_api.is_satisfiable(numeric, context)
    assert not solver_api.is_satisfiable(boolean, context)


def test_parameter_term_identity_preserves_json_types_recursively() -> None:
    boolean = parse_condition({"param": {"name": "P", "equal": True}})
    integer = parse_condition({"param": {"name": "P", "equal": 1}})

    expression = any_of(boolean, integer)

    assert boolean != integer
    assert len({boolean, integer}) == 2
    assert isinstance(expression, AnyOf)
    assert expression.children == (boolean, integer)
    assert expression.evaluate(EvaluationContext(parameters={"P": 1})) is TruthValue.TRUE

    nested_boolean = parse_condition({"param": {"name": "P", "equal": [True]}})
    nested_integer = parse_condition({"param": {"name": "P", "equal": [1]}})
    nested_expression = any_of(nested_boolean, nested_integer)
    assert isinstance(nested_expression, AnyOf)
    assert nested_expression.evaluate(EvaluationContext(parameters={"P": [1]})) is TruthValue.TRUE


def test_unconstrained_homogeneous_parameter_one_of_uses_a_scalar_symbol() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    condition = parse_condition({"param": {"name": "P", "oneOf": [1, 2]}})

    assert solver_api.finite_check(condition) is None
    solver = solver_api.ConditionSolver()
    solver.add(condition)
    assert solver.check() is solver_api.SolverStatus.SAT
    assert solver.model().parameters["P"] in (1, 2)

    domain_context = solver_api.SolverContext(
        parameter_domains={"P": ParameterDomain.from_schema({"type": "integer", "enum": [1, 2]})}
    )
    assert solver_api.finite_check(condition, domain_context) is solver_api.SolverStatus.SAT
    constrained = solver_api.ConditionSolver(domain_context)
    constrained.add(condition)
    assert constrained.check() is solver_api.SolverStatus.SAT


def test_unconstrained_mixed_parameter_one_of_is_explicitly_unsupported() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    condition = parse_condition({"param": {"name": "P", "oneOf": [1, "one"]}})

    with pytest.raises(solver_api.SolverError, match="homogeneous scalar"):
        solver_api.ConditionSolver().add(condition)


def test_finite_evaluator_honors_unmentioned_fixed_context_constraints() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    domain = ParameterDomain.from_schema({"type": "integer", "enum": [1, 2]})
    context = solver_api.SolverContext(parameter_domains={"P": domain}, fixed_parameters={"P": 3})

    assert solver_api.finite_check(TRUE, context) is solver_api.SolverStatus.UNSAT
    solver = solver_api.ConditionSolver(context)
    solver.add(TRUE)
    assert solver.check() is solver_api.SolverStatus.UNSAT


def test_unknown_fixed_extension_versions_are_rejected_before_solving() -> None:
    solver_api = _solver_module()

    with pytest.raises(solver_api.SolverError, match="unknown version"):
        solver_api.SolverContext(extension_versions={"A": ("1.0",)}, fixed_extensions={"A": "2.0"})
    with pytest.raises(solver_api.SolverError, match="no version catalog"):
        solver_api.SolverContext(fixed_extensions={"Missing": "1.0"})


def test_solver_conflict_is_minimized_relative_to_unlabeled_background() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    solver = solver_api.ConditionSolver()
    solver.add(XlenTerm(32))
    solver.add(XlenTerm(64), label="requires RV64")

    assert solver.check() is solver_api.SolverStatus.UNSAT
    assert solver.minimal_conflict() == ("requires RV64",)


def test_boolean_solver_helpers_do_not_collapse_unknown_results() -> None:
    pytest.importorskip("z3")
    solver_api = _solver_module()
    unresolved = UnresolvedIdlCondition("-> SOME_PARAMETER;")

    with pytest.raises(solver_api.SolverUnknownError):
        solver_api.is_satisfiable(unresolved)
    with pytest.raises(solver_api.SolverUnknownError):
        solver_api.implies(TRUE, unresolved)
    with pytest.raises(solver_api.SolverUnknownError):
        solver_api.equivalent(TRUE, unresolved)
    assert solver_api.implies(unresolved, unresolved)


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare conditions with the Ruby implementation",
)
def test_condition_evaluation_and_sat_match_ruby_oracle() -> None:
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")
    data = [
        {"xlen": 32},
        {"xlen": 64},
        {"param": {"name": "LITTLE_IS_BETTER", "equal": True}},
        {"param": {"name": "LITTLE_IS_BETTER", "equal": False}},
    ]
    result = subprocess.run(
        [mise, "exec", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
        cwd=REPOSITORY_ROOT,
        input=json.dumps({"config": "little_is_better", "conditions": data}),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby condition oracle failed:\n{result.stdout}\n{result.stderr}")
    expected = json.loads(result.stdout)
    context = EvaluationContext(
        xlen=32,
        parameters={"LITTLE_IS_BETTER": True},
        closed_world_extensions=True,
        closed_world_parameters=True,
    )
    evaluation_names = {
        TruthValue.TRUE: "yes",
        TruthValue.FALSE: "no",
        TruthValue.UNKNOWN: "maybe",
    }
    solver_api = _solver_module()

    for raw, oracle in zip(data, expected, strict=True):
        condition = parse_condition(raw)
        assert condition.to_data() == oracle["data"]
        assert evaluation_names[condition.evaluate(context)] == oracle["evaluation"]
        assert solver_api.is_satisfiable(condition) is oracle["satisfiable"]


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to reproduce corrected Ruby condition behavior",
)
def test_legacy_ruby_condition_defects_are_reproducible() -> None:
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")
    result = subprocess.run(
        [mise, "exec", "--", "bundle", "exec", "ruby", str(RUBY_DEFECTS)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby condition defect reproduction failed:\n{result.stdout}\n{result.stderr}")
    assert json.loads(result.stdout) == {
        "empty_conjunction": False,
        "one_way_equivalence": True,
        "bit_range_three": "no",
    }
