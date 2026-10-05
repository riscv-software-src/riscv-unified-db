# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_passes_helpers import assert_case_matches

DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
CASES = [
    case
    for case in json.loads(DATA_FILE.read_text(encoding="utf-8"))["cases"]
    if "return_values" in case["passes"]
]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_return_values_follow_corrected_contract(case):
    # The checked-in Ruby observation remains available under ``expect``.
    # ``python_expect`` specifies the correction because Ruby's pass uses stale
    # AST accessors and crashes for every non-empty body.
    assert_case_matches(case)


def test_ruby_return_value_crashes_are_frozen_separately():
    assert len(CASES) == 8
    assert CASES[0]["expect"]["passes"]["return_values"] == {
        "ok": True,
        "value": [],
    }
    assert all(not case["expect"]["passes"]["return_values"]["ok"] for case in CASES[1:])
    assert all("python_expect" in case for case in CASES)
