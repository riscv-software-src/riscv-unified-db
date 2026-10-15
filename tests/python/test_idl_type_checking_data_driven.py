# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_semantics_helpers import assert_case_matches
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/ruby-gems/idlc/test/data/type_checking_tests.yaml"
CORPUS = json.loads((Path(__file__).parent / "data/idl/statements.json").read_text())["cases"]
BY_ID = {case["id"]: case for case in CORPUS}
TYPE_DATA = YAML(typ="safe").load(FIXTURE.read_text())
TYPE_ENTRIES = [(category, entry) for category, entries in TYPE_DATA.items() for entry in entries]


@pytest.mark.parametrize(
    ("category", "entry"),
    TYPE_ENTRIES,
    ids=[f"{category}__{entry['name']}" for category, entry in TYPE_ENTRIES],
)
def test_ruby_type_checking_fixture(category, entry):
    case = BY_ID[f"ruby_type__{category}__{entry['name']}"]
    assert case["source"]["should_pass"] == entry["should_pass"]
    assert case["source"]["expected_type"] == entry.get("expected_type")
    assert_case_matches(case)
