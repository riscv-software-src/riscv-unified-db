# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import pytest
import z3

import udb.architecture as architecture_api
import udb.solver_arrays as array_encoding
from udb import ArchitectureCheckStatus, Configuration, ResolvedDatabase
from udb.conditions import EvaluationContext, TruthValue, all_of, parse_condition
from udb.domains import ParameterDomain
from udb.solver import ConditionSolver, SolverContext, SolverError, SolverStatus, SolverUnknownError


def sparse_solver():
    domain = ParameterDomain.from_schema(
        {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": 10**6},
            "uniqueItems": True,
            "maxItems": 10**6 + 1,
        }
    )
    solver = ConditionSolver(SolverContext(parameter_domains={"A": domain}))
    first = parse_condition({"param": {"name": "A", "index": 0, "equal": 0}})
    member = parse_condition({"param": {"name": "A", "includes": 5000}})
    solver.add(first, "first is zero")
    return solver, domain, first, member


def test_model_retry_preserves_labels_extras_and_original_capacity():
    solver, domain, first, member = sparse_solver()
    extra = all_of(member, {"free": "chosen"})
    assert solver.check([extra]) is SolverStatus.SAT
    model = solver.model()
    assert len(model.parameters["A"]) <= 4096
    assert domain.accepts(model.parameters["A"])
    context = EvaluationContext(parameters=model.parameters, free_terms=model.free_terms)
    assert first.evaluate(context) is TruthValue.TRUE
    assert extra.evaluate(context) is TruthValue.TRUE
    larger = parse_condition({"param": {"name": "A", "size": True, "greaterThan": 4096}})
    assert solver.check([larger]) is SolverStatus.SAT
    with pytest.raises(SolverError, match="4096 concrete items"):
        solver.model()
    assert solver.check([extra]) is SolverStatus.SAT
    assert len(solver.model().parameters["A"]) <= 4096


def test_model_retry_preserves_definite_three_valued_constraints():
    solver, _, _, member = sparse_solver()
    choice = parse_condition({"anyOf": [{"free": "chosen"}, {"idl()": "pending();"}]})
    solver.add(choice, "definite choice")
    assert solver.check([member]) is SolverStatus.SAT
    assert solver.model().free_terms["chosen"] is True


def test_model_retry_unknown_keeps_original_sat_and_never_claims_oversize(monkeypatch):
    solver, _, _, member = sparse_solver()
    assert solver.check([member]) is SolverStatus.SAT
    monkeypatch.setattr(z3.Solver, "check", lambda self: z3.unknown)
    with pytest.raises(SolverUnknownError, match="materializable model"):
        solver.model()
    assert solver._last_status is SolverStatus.SAT


def test_resource_budgets_are_deterministic_and_witness_is_cheap(monkeypatch):
    configurations = []
    original_set = z3.Solver.set

    def record_set(self, *args, **kwargs):
        configurations.append(kwargs)
        return original_set(self, *args, **kwargs)

    monkeypatch.setattr(z3.Solver, "set", record_set)
    solver, _, _, member = sparse_solver()
    assert solver.check([member]) is SolverStatus.SAT
    assert len(solver.model().parameters["A"]) <= 4096
    assert all("timeout" not in configuration for configuration in configurations)
    assert {"rlimit": array_encoding.MAX_INDEXED_SOLVER_RESOURCES} in configurations
    assert {"rlimit": array_encoding.MAX_ARRAY_WITNESS_RESOURCES} in configurations
    assert (
        0
        < array_encoding.MAX_ARRAY_WITNESS_RESOURCES
        < (array_encoding.MAX_INDEXED_SOLVER_RESOURCES // 10)
    )


def architecture():
    database = ResolvedDatabase({})
    configuration = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "name": "empty",
            "type": "partially configured",
            "mandatory_extensions": [],
            "description": "Minimal solver model guard regression",
        }
    )
    return database.configure(configuration)


@pytest.mark.parametrize("status", [SolverStatus.UNKNOWN, SolverStatus.UNSAT])
def test_architecture_final_check_is_guarded_before_model(status, monkeypatch):
    configured = architecture()
    solver = configured._require_solver()
    monkeypatch.setattr(solver, "check", lambda *args, **kwargs: status)
    monkeypatch.setattr(solver, "minimal_conflict", lambda: ())
    monkeypatch.setattr(solver, "model", lambda: pytest.fail("must not request a non-SAT model"))
    result = configured.check()
    assert result.status is (
        ArchitectureCheckStatus.DEFERRED
        if status is SolverStatus.UNKNOWN
        else ArchitectureCheckStatus.UNSAT
    )
    assert result.diagnostics[0].code == (
        "solver-unknown" if status is SolverStatus.UNKNOWN else "unsatisfiable"
    )
    assert result.model is None


@pytest.mark.parametrize(
    "statuses",
    [
        [SolverStatus.UNKNOWN],
        [SolverStatus.SAT, SolverStatus.UNKNOWN],
        [SolverStatus.SAT, SolverStatus.UNSAT],
    ],
)
def test_compatibility_check_is_guarded_before_model(statuses, monkeypatch):
    configured = architecture()
    outcomes = iter(statuses)

    class ControlledSolver:
        def __init__(self, *args, **kwargs):
            pass

        def add(self, *args, **kwargs):
            pass

        def check(self, *args, **kwargs):
            return next(outcomes)

        def minimal_conflict(self):
            return ()

        def model(self):
            pytest.fail("must not request a non-SAT model")

    monkeypatch.setattr(architecture_api, "ConditionSolver", ControlledSolver)
    result = configured.compatible_with(configured)
    final = statuses[-1]
    assert result.status is (
        ArchitectureCheckStatus.DEFERRED
        if final is SolverStatus.UNKNOWN
        else ArchitectureCheckStatus.UNSAT
    )
    assert result.diagnostics[0].code == (
        "solver-unknown" if final is SolverStatus.UNKNOWN else "incompatible"
    )
    assert result.model is None


def test_architecture_model_retry_unknown_is_a_diagnostic(monkeypatch):
    configured = architecture()
    solver = configured._require_solver()

    def unresolved_model():
        raise SolverUnknownError("the solver could not decide a materializable model")

    monkeypatch.setattr(solver, "model", unresolved_model)
    result = configured.check()
    assert result.status is ArchitectureCheckStatus.DEFERRED
    assert result.diagnostics[0].code == "solver-unknown"
    assert "materializable model" in result.diagnostics[0].message
