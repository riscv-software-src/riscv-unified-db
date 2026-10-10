# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exercise frozen translation independently of runtime-global execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from udb import Database
from udb.conditions import normalize, parse_condition
from udb.idl import IdlSource
from udb.idl_conditions import compile_idl_condition
from udb.idl_environment import condition_symbol_table

CORPUS = json.loads((Path(__file__).with_name("data") / "idl" / "conditions.json").read_text())


@pytest.fixture(scope="module")
def condition_symbols():
    return condition_symbol_table(Database.bundled().resolve())


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_real_bootstrap_matches_all_four_frozen_translations(case, condition_symbols):
    before = condition_symbols.snapshot_values()
    condition = compile_idl_condition(
        case["text"], condition_symbols, source=IdlSource(case["text"], label=case["id"])
    )
    for results in CORPUS["results"].values():
        expected = next(result for result in results if result["id"] == case["id"])
        assert "error" not in expected
        assert normalize(condition) == normalize(parse_condition(expected["to_h"]))
    assert not condition.has_unresolved
    assert condition_symbols.levels == 1
    assert condition_symbols.snapshot_values() == before
