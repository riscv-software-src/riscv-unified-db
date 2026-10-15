# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_passes_helpers import assert_case_matches

DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
ALL_CASES = json.loads(DATA_FILE.read_text(encoding="utf-8"))["cases"]
REGISTER_CASES = [
    case
    for case in ALL_CASES
    if {"source_registers", "destination_registers"} & set(case["passes"])
]
CSR_CASES = [case for case in ALL_CASES if "referenced_csrs" in case["passes"]]


@pytest.mark.parametrize("case", REGISTER_CASES, ids=[case["id"] for case in REGISTER_CASES])
def test_register_discovery_matches_ruby_oracle(case):
    assert_case_matches(case)


@pytest.mark.parametrize("case", CSR_CASES, ids=[case["id"] for case in CSR_CASES])
def test_referenced_csrs_match_ruby_oracle(case):
    assert_case_matches(case)


def test_register_and_csr_discovery_matrix_is_complete():
    assert len(REGISTER_CASES) == 9
    assert len(CSR_CASES) == 6
    complex_cases = {
        case["id"]
        for case in REGISTER_CASES
        if not next(iter(case["expect"]["passes"].values()))["ok"]
    }
    assert complex_cases == {
        "source_register_unknown_index",
        "destination_register_unknown_index",
    }
