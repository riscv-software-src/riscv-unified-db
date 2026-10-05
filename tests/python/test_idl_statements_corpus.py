# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from idl_semantics_helpers import (
    RUBY_BUG_CORRECTIONS,
    assert_case_matches,
    compile_func_body,
    compile_isa,
    make_symtab,
)

DATA_FILE = Path(__file__).parent / "data" / "idl" / "statements.json"
DOCUMENT = json.loads(DATA_FILE.read_text())
CASES = DOCUMENT["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_statement_semantics_match_frozen_ruby_oracle(case):
    assert_case_matches(case)


def test_post_decrement_assignment_rhs_is_rejected():
    correction = RUBY_BUG_CORRECTIONS["post_decrement_assignment_rhs"]
    with pytest.raises(correction["error"], match=correction["message"]):
        compile_func_body(correction["text"], make_symtab())


def test_wrong_function_argument_type_has_diagnostic():
    correction = RUBY_BUG_CORRECTIONS["wrong_function_argument_type"]
    with pytest.raises(correction["error"], match=correction["message_contains"]):
        compile_isa(correction["text"], make_symtab())


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to verify the frozen Ruby statement oracle",
)
def test_frozen_statement_corpus_matches_ruby_oracle():
    from regen_idl_statements import build_cases, run_oracle

    rebuilt = build_cases()
    frozen_inputs = copy.deepcopy(CASES)
    for case in frozen_inputs:
        case.pop("expect")
    assert rebuilt == frozen_inputs, (
        "statements.json inputs are stale; rerun regen_idl_statements.py"
    )

    fresh = run_oracle(rebuilt)
    for case, expected in zip(CASES, fresh, strict=True):
        assert expected == case["expect"], (
            f"case {case['id']!r} is stale; rerun regen_idl_statements.py"
        )
