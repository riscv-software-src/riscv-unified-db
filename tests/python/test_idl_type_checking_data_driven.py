# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_semantics_helpers import assert_case_matches

CORPUS = json.loads((Path(__file__).parent / "data/idl/statements.json").read_text())["cases"]
TYPE_CASES = [case for case in CORPUS if case["id"].startswith("ruby_type__")]


@pytest.mark.parametrize(
    "case",
    TYPE_CASES,
    ids=[case["id"].removeprefix("ruby_type__") for case in TYPE_CASES],
)
def test_frozen_type_checking_case(case):
    assert "should_pass" in case["source"]
    assert_case_matches(case)
