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
    if "prune" in case["passes"]
]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_prune_matches_ruby_oracle(case):
    assert_case_matches(case)


def test_every_ruby_prune_case_is_ported():
    # test_prune.rb has 31 methods; looped operators and multi-part CSR coverage
    # expand those methods to 40 independent black-box corpus entries.
    assert len(CASES) == 40
    assert all(case["expect"]["passes"]["prune"]["ok"] for case in CASES)
