# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_semantics_helpers import assert_case_matches, run_semantic_case

CORPUS = json.loads((Path(__file__).parent / "data/idl/statements.json").read_text())["cases"]
FLOW_CASES = [case for case in CORPUS if case["id"].startswith("ruby_flow__")]


@pytest.mark.parametrize(
    "case",
    FLOW_CASES,
    ids=[case["id"].removeprefix("ruby_flow__") for case in FLOW_CASES],
)
def test_frozen_control_flow_case(case):
    assert "should_pass" in case["source"]
    assert_case_matches(case)


def test_unknown_condition_collects_both_return_values():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "if (flag) { return 1; } else { return 2; }",
            "return_type": "Bits<8>",
            "setup": {"vars": [{"name": "flag", "type": "Boolean"}]},
            "observe": {"return": True},
        }
    )
    assert result["return_values"] == {"known": True, "value": ["1", "2"]}


def test_if_condition_requires_boolean():
    result = run_semantic_case({"root": "function_body", "text": "if (1) { return 1; }"})
    assert result["error"] == "type"
    assert "not boolean" in result["message"]
