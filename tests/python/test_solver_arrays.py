# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest
import z3
from ruamel.yaml import YAML

import udb.solver_arrays as array_encoding
from udb import ArchitectureCheckStatus, Configuration, Database, QueryPresence
from udb.conditions import EvaluationContext, TruthValue, all_of, negate, parse_condition
from udb.domains import ArrayDomain, ParameterDomain
from udb.solver import (
    ConditionSolver,
    SolverContext,
    SolverError,
    SolverStatus,
    SolverUnknownError,
    finite_check,
)


def term(**comparison):
    return parse_condition({"param": {"name": "A", **comparison}})


def make_solver(items=None, **schema):
    domain = ParameterDomain.from_schema(
        {
            "type": "array",
            "items": {"type": "integer", "enum": [0, 1]} if items is None else items,
            "maxItems": 5000,
            **schema,
        }
    )
    return ConditionSolver(SolverContext(parameter_domains={"A": domain})), domain


def assert_model(solver, domain, *conditions):
    assert solver.check() is SolverStatus.SAT
    model = solver.model()
    concrete = model.parameters["A"]
    assert domain.accepts(concrete)
    context = EvaluationContext(parameters={"A": concrete})
    assert all(condition.evaluate(context) is TruthValue.TRUE for condition in conditions)
    return concrete


def test_parent_contradictory_membership_across_add_calls():
    solver, _ = make_solver()
    solver.add(term(size=True, equal=65))
    solver.add(term(includes=0), "includes zero")
    solver.add(term(includes=0), "again includes zero")
    solver.add(negate(term(includes=0)), "not includes zero")
    assert solver.check() is SolverStatus.UNSAT
    assert "not includes zero" in solver.unsat_core()


def test_parent_model_has_the_requested_65_items():
    solver, domain = make_solver()
    size = term(size=True, equal=65)
    solver.add(size)
    assert len(assert_model(solver, domain, size)) == 65


@pytest.mark.parametrize("index", [64, 65, 500, 4999])
def test_tail_index_and_negative_membership_share_storage(index):
    solver, _ = make_solver()
    solver.add(term(index=index, equal=0))
    solver.add(negate(term(includes=0)))
    assert solver.check() is SolverStatus.UNSAT


def test_repeated_negative_membership_and_extra_checks_are_consistent():
    solver, domain = make_solver()
    constraints = [term(size=True, equal=65), negate(term(includes=0))]
    for constraint in constraints:
        solver.add(constraint)
    assert assert_model(solver, domain, *constraints) == (1,) * 65
    for _ in range(2):
        assert solver.check([term(includes=0)]) is SolverStatus.UNSAT
        assert assert_model(solver, domain, *constraints) == (1,) * 65
    solver.add(negate(term(includes=0)))
    solver.add(term(index=64, equal=0))
    assert solver.check() is SolverStatus.UNSAT


def test_tail_membership_cannot_escape_domain():
    solver, _ = make_solver()
    solver.add(term(size=True, equal=65))
    solver.add(term(includes=2))
    assert solver.check() is SolverStatus.UNSAT


def test_tail_membership_can_be_the_only_matching_item():
    solver, domain = make_solver()
    values = [1] * 64 + [0]
    constraints = [term(equal=values), term(includes=0), term(index=64, equal=0)]
    for constraint in constraints:
        solver.add(constraint)
    assert assert_model(solver, domain, *constraints) == tuple(values)
    solver.add(negate(term(includes=0)))
    assert solver.check() is SolverStatus.UNSAT


@pytest.mark.parametrize("length", [4096, 4097, 2**64])
def test_exact_materialization_threshold_and_no_length_clamping(length):
    solver, domain = make_solver(maxItems=2**64)
    size = term(size=True, equal=length)
    solver.add(size)
    assert solver.check() is SolverStatus.SAT
    if length == 4096:
        assert len(assert_model(solver, domain, size)) == 4096
    else:
        with pytest.raises(SolverError, match=rf"{length}.*4096"):
            solver.model()


def test_large_minimum_is_a_symbolic_constraint_not_an_allocation():
    solver, _ = make_solver(minItems=4097, maxItems=2**64)
    solver.add(term(size=True, equal=4097))
    assert solver.check() is SolverStatus.SAT
    with pytest.raises(SolverError, match=r"4097.*4096"):
        solver.model()
    assert solver.check([term(size=True, equal=4096)]) is SolverStatus.UNSAT


@pytest.mark.parametrize("unique", [False, True])
def test_mixed_tuple_tail_domains_contains_and_equality(unique):
    solver, domain = make_solver(
        items=[{"const": "prefix"}, {"const": True}],
        additionalItems={"type": "integer", "minimum": 0, "maximum": 10000},
        uniqueItems=unique,
        contains={"const": 9999},
    )
    values = ["prefix", True, *range(62), 9999]
    constraints = [term(equal=values), term(includes=9999), term(index=64, equal=9999)]
    for constraint in constraints:
        solver.add(constraint)
    assert assert_model(solver, domain, *constraints) == tuple(values)
    solver.add(negate(term(includes=9999)))
    assert solver.check() is SolverStatus.UNSAT


def test_contains_is_not_satisfied_by_an_unrelated_tail_witness():
    solver, _ = make_solver(contains={"const": 0})
    solver.add(term(size=True, equal=65))
    solver.add(negate(term(includes=0)))
    assert solver.check() is SolverStatus.UNSAT


def test_unique_items_covers_prefix_and_tail_and_two_tail_indices():
    for left, right in [(0, 64), (64, 65)]:
        solver, _ = make_solver(
            items=[{"const": 1}],
            additionalItems={"type": "integer", "minimum": 0, "maximum": 10000},
            uniqueItems=True,
        )
        solver.add(term(size=True, equal=66))
        solver.add(term(index=left, equal=1))
        solver.add(term(index=right, equal=1))
        assert solver.check() is SolverStatus.UNSAT


def test_array_comparisons_and_oneof_use_full_concrete_values():
    values = [0] * 64 + [1]
    solver, domain = make_solver()
    choices = term(oneOf=[values, [1] * 65])
    different = term(notEqual=[1] * 65)
    solver.add(choices)
    solver.add(different)
    assert assert_model(solver, domain, choices, different) == tuple(values)
    solver.add(term(notEqual=values))
    assert solver.check() is SolverStatus.UNSAT


@pytest.mark.parametrize(
    "schema",
    [
        {"items": {"type": "integer", "enum": [0, 1]}},
        {"items": {"type": "integer", "enum": [0, 1]}, "contains": {"const": 1}},
        {
            "items": [{"const": "p"}],
            "additionalItems": {"type": "integer", "enum": [0, 1]},
        },
        {
            "items": [{"const": "p"}],
            "additionalItems": {"type": "integer", "enum": [0, 1]},
            "uniqueItems": True,
            "contains": {"const": 1},
        },
    ],
)
@pytest.mark.parametrize("explicit_items", [0, 64])
def test_indexed_arrays_agree_with_small_finite_enumeration(schema, explicit_items, monkeypatch):
    monkeypatch.setattr(array_encoding, "MAX_EXPLICIT_ARRAY_ITEMS", explicit_items)
    small = ParameterDomain.from_schema({"type": "array", "maxItems": 3, **schema})
    large = ParameterDomain.from_schema({"type": "array", "maxItems": 5000, **schema})
    atoms = [
        term(includes=0),
        term(includes=1),
        term(index=0, equal=0),
        term(index=2, equal=1),
        term(equal=[]),
        term(equal=["p", 0, 1]),
    ]
    cases = [*atoms, *(negate(atom) for atom in atoms)]
    cases.extend(all_of(left, negate(right)) for left, right in product(atoms, repeat=2))
    finite_context = SolverContext(parameter_domains={"A": small})
    for case in cases:
        expression = all_of(term(size=True, lessThanOrEqual=3), case)
        expected = finite_check(expression, finite_context)
        enumerated = any(
            expression.evaluate(EvaluationContext(parameters={"A": value})) is TruthValue.TRUE
            for value in small.enumerate_values(limit=100)
        )
        assert expected is (SolverStatus.SAT if enumerated else SolverStatus.UNSAT)
        solver = ConditionSolver(SolverContext(parameter_domains={"A": large}))
        solver.add(expression)
        assert solver.check() is expected
        if expected is SolverStatus.SAT:
            assert_model(solver, large, expression)


@pytest.mark.parametrize("xlen", [None, 32, 64])
def test_shipped_hpm_events_queries_do_not_allocate_capacity(xlen):
    root = Path(__file__).resolve().parents[2]
    document = YAML(typ="safe").load((root / "spec/std/isa/param/HPM_EVENTS.yaml").read_text())
    domain = ParameterDomain.from_schema(document["schema"])
    solver = ConditionSolver(SolverContext(parameter_domains={"HPM_EVENTS": domain}, xlen=xlen))
    conditions = [
        {"param": {"name": "HPM_EVENTS", "size": True, "equal": 65}},
        {"param": {"name": "HPM_EVENTS", "index": 64, "equal": 7}},
        {"param": {"name": "HPM_EVENTS", "includes": 7}},
    ]
    for condition in conditions:
        solver.add(condition)
    assert solver.check() is SolverStatus.SAT
    concrete = solver.model().parameters["HPM_EVENTS"]
    assert len(concrete) == 65
    assert domain.accepts(concrete)
    assert concrete[64] == 7
    solver.add({"not": conditions[-1]})
    assert solver.check() is SolverStatus.UNSAT


def test_owned_context_isolated_from_callers_z3_context():
    caller_context = z3.Context()
    caller_solver = z3.Solver(ctx=caller_context)
    caller_value = z3.Int("caller_value", ctx=caller_context)
    caller_solver.add(caller_value == 17)
    solver, domain = make_solver()
    constraint = term(size=True, equal=65)
    solver.add(constraint)
    assert len(assert_model(solver, domain, constraint)) == 65
    assert caller_solver.check() == z3.sat
    assert caller_solver.model().eval(caller_value).as_long() == 17


def test_nested_arrays_are_explicitly_unsupported():
    nested = ParameterDomain.from_schema({"type": "array", "items": {"type": "integer"}})
    domain = ArrayDomain(
        schema={},
        item_domain=nested,
        additional_items=nested,
        max_items=5000,
    )
    solver = ConditionSolver(SolverContext(parameter_domains={"A": domain}))
    with pytest.raises(SolverError, match="unsupported nested item domains"):
        solver.add(term(size=True, equal=65))


def test_unknown_is_not_a_success_shaped_boolean_or_model(monkeypatch):
    solver, _ = make_solver()
    solver.add(term(size=True, equal=65))
    monkeypatch.setattr(solver._solver, "check", lambda: z3.unknown)
    assert solver.check() is SolverStatus.UNKNOWN
    with pytest.raises(SolverUnknownError, match="could not decide"):
        solver.satisfiable()
    with pytest.raises(SolverError, match="only after a satisfiable"):
        solver.model()


def test_unsuccessful_rotation_witness_does_not_prove_unsat(monkeypatch):
    solver, _ = make_solver(
        items={"type": "integer", "minimum": 0, "maximum": 10000},
        uniqueItems=True,
    )
    # Distinct 0,2 is a valid prefix, but no cyclic rotation starts that way.
    solver.add(term(size=True, equal=65), "size")
    solver.add(term(index=0, equal=0), "first")
    solver.add(term(index=1, equal=2), "second")
    monkeypatch.setattr(solver._solver, "check", lambda: z3.unknown)
    assert solver.check() is SolverStatus.UNKNOWN
    with pytest.raises(SolverUnknownError, match="could not decide"):
        solver.satisfiable()


def test_rotation_witness_honors_labels_and_contains():
    solver, domain = make_solver(
        items={"type": "integer", "minimum": 0, "maximum": 10000},
        uniqueItems=True,
        contains={"const": 9999},
    )
    constraints = [term(size=True, equal=65), term(index=64, equal=9999)]
    for index, constraint in enumerate(constraints):
        solver.add(constraint, f"constraint {index}")
    assert_model(solver, domain, *constraints)
    solver.add(negate(term(includes=9999)), "no required value")
    assert solver.check() is SolverStatus.UNSAT


@pytest.mark.parametrize(
    ("items", "value", "wrong"),
    [
        ({"type": "boolean"}, True, 1),
        ({"type": "string", "enum": ["a", "b"]}, "b", "c"),
    ],
)
def test_typed_tail_predicates_share_membership_and_domains(items, value, wrong):
    solver, domain = make_solver(items=items)
    constraints = [term(size=True, equal=65), term(index=64, equal=value)]
    for constraint in constraints:
        solver.add(constraint)
    assert_model(solver, domain, *constraints)
    assert solver.check([term(includes=wrong)]) is SolverStatus.UNSAT
    assert solver.check([negate(term(includes=value))]) is SolverStatus.UNSAT


def test_shipped_configuration_solver_construction_and_queries():
    root = Path(__file__).resolve().parents[2]
    raw = Database.from_path(root / "spec/std/isa", schemas_path=root / "spec/schemas")
    standard = raw.resolve()
    for name, expected in [
        ("_", QueryPresence.POSSIBLE),
        ("rv32", QueryPresence.MANDATORY),
        ("rv64", QueryPresence.MANDATORY),
        ("qc_iu", QueryPresence.MANDATORY),
    ]:
        config = Configuration.from_file(root / "cfgs" / f"{name}.yaml")
        database = (
            raw.resolve(overlays=[root / "spec/custom/isa" / config.overlay])
            if name == "qc_iu"
            else standard
        )
        architecture = database.configure(config)
        result = architecture.check()
        assert result.status is ArchitectureCheckStatus.DEFERRED
        assert {diagnostic.code for diagnostic in result.diagnostics} == {"idl-deferred"}
        assert architecture.object_presence(database.instruction("add")) is expected
        if name == "qc_iu":
            assert architecture.extension_presence("H") is QueryPresence.ABSENT
