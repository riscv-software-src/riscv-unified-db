# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from idl_passes_helpers import assert_case_matches

DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
ALL_CASES = json.loads(DATA_FILE.read_text(encoding="utf-8"))["cases"]
ADOC_CASES = [case for case in ALL_CASES if "adoc" in case["passes"]]
OPTION_CASES = [case for case in ALL_CASES if "option_adoc" in case["passes"]]


@pytest.mark.parametrize("case", ADOC_CASES, ids=[case["id"] for case in ADOC_CASES])
def test_adoc_matches_ruby_or_corrected_oracle(case):
    assert_case_matches(case)


@pytest.mark.parametrize("case", OPTION_CASES, ids=[case["id"] for case in OPTION_CASES])
def test_option_adoc_matches_ruby_oracle(case):
    assert_case_matches(case)


def test_adoc_corpus_covers_documents_and_options():
    assert len(ADOC_CASES) == 20
    assert len(OPTION_CASES) == 9
    broken = [case for case in ADOC_CASES if not case["expect"]["passes"]["adoc"]["ok"]]
    assert [case["id"] for case in broken] == ["adoc_multi_return_and_assignment"]
    assert "python_expect" in broken[0]
