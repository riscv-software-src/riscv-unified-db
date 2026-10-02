# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
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
def test_statement_semantics_match_frozen_expectation(case):
    assert_case_matches(case)


def test_post_decrement_assignment_rhs_is_rejected():
    correction = RUBY_BUG_CORRECTIONS["post_decrement_assignment_rhs"]
    with pytest.raises(correction["error"], match=correction["message"]):
        compile_func_body(correction["text"], make_symtab())


def test_wrong_function_argument_type_has_diagnostic():
    correction = RUBY_BUG_CORRECTIONS["wrong_function_argument_type"]
    with pytest.raises(correction["error"], match=correction["message_contains"]):
        compile_isa(correction["text"], make_symtab())
