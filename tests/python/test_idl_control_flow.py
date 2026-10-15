# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_semantics_helpers import assert_case_matches, run_semantic_case
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/ruby-gems/idlc/test/data/control_flow_tests.yaml"
CORPUS = json.loads((Path(__file__).parent / "data/idl/statements.json").read_text())["cases"]
BY_ID = {case["id"]: case for case in CORPUS}
FLOW_DATA = YAML(typ="safe").load(FIXTURE.read_text())
FLOW_ENTRIES = [(category, entry) for category, entries in FLOW_DATA.items() for entry in entries]


@pytest.mark.parametrize(
    ("category", "entry"),
    FLOW_ENTRIES,
    ids=[f"{category}__{entry['name']}" for category, entry in FLOW_ENTRIES],
)
def test_ruby_control_flow_fixture(category, entry):
    case = BY_ID[f"ruby_flow__{category}__{entry['name']}"]
    assert case["source"]["should_pass"] == entry["should_pass"]
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
