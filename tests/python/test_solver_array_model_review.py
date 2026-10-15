# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest

from udb.conditions import EvaluationContext, TruthValue, parse_condition
from udb.domains import ParameterDomain
from udb.solver import ConditionSolver, SolverContext, SolverStatus


@pytest.mark.parametrize(("maximum", "member"), [(10**6, 5000), (2**60, 2**59)])
def test_model_can_materialize_sparse_unique_members_without_clamping_sat(maximum, member):
    domain = ParameterDomain.from_schema(
        {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": maximum},
            "uniqueItems": True,
            "maxItems": maximum + 1,
        }
    )
    conditions = [
        parse_condition({"param": {"name": "A", "index": 0, "equal": 0}}),
        parse_condition({"param": {"name": "A", "includes": member}}),
    ]
    solver = ConditionSolver(SolverContext(parameter_domains={"A": domain}))
    for index, condition in enumerate(conditions):
        solver.add(condition, f"condition {index}")
    assert domain.accepts([0, member])
    assert solver.check() is SolverStatus.SAT
    model = solver.model().parameters["A"]
    assert len(model) <= 4096
    assert domain.accepts(model)
    assert all(
        condition.evaluate(EvaluationContext(parameters={"A": model})) is TruthValue.TRUE
        for condition in conditions
    )
    # Finding a materializable model must not cap the original satisfiability problem.
    larger = parse_condition({"param": {"name": "A", "size": True, "greaterThan": 4096}})
    assert solver.check([larger]) is SolverStatus.SAT
    assert solver.check() is SolverStatus.SAT
