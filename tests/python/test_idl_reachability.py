# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_passes_helpers import assert_case_matches

DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
ALL_CASES = json.loads(DATA_FILE.read_text(encoding="utf-8"))["cases"]
FUNCTION_CASES = [
    case
    for case in ALL_CASES
    if any(name.startswith("reachable_functions") for name in case["passes"])
]
EXCEPTION_CASES = [case for case in ALL_CASES if "reachable_exceptions" in case["passes"]]


@pytest.mark.parametrize("case", FUNCTION_CASES, ids=[case["id"] for case in FUNCTION_CASES])
def test_reachable_functions_match_ruby_oracle(case):
    assert_case_matches(case)


@pytest.mark.parametrize("case", EXCEPTION_CASES, ids=[case["id"] for case in EXCEPTION_CASES])
def test_reachable_exceptions_match_ruby_oracle(case):
    assert_case_matches(case)


def test_ruby_function_pass_contract_is_fully_represented():
    # Nine entries cover every reachable-functions test in test_functions.rb,
    # including the shared-cache regression. Four exception entries include the
    # two Ruby tests plus direct union/empty behavior.
    assert len(FUNCTION_CASES) == 9
    assert len(EXCEPTION_CASES) == 4
    assert all(
        observation["ok"]
        for case in FUNCTION_CASES + EXCEPTION_CASES
        for observation in case["expect"]["passes"].values()
    )
