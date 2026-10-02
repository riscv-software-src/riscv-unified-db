# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
DOCUMENT = json.loads(DATA_FILE.read_text(encoding="utf-8"))


def test_frozen_pass_corpus_is_deterministic_and_complete():
    ids = [case["id"] for case in DOCUMENT["cases"]]
    assert ids == list(dict.fromkeys(ids))
    assert len(ids) == 105
    assert DOCUMENT["configs"] == ["_", "rv32", "rv64", "qc_iu"]
    assert len(DOCUMENT["real_samples"]) == 27
    assert set(DOCUMENT["real"]) in (set(), set(DOCUMENT["configs"]))

    encoded = json.dumps(DOCUMENT, indent=2, sort_keys=True) + "\n"
    assert DATA_FILE.read_text(encoding="utf-8") == encoded
    assert "<repo>" not in encoded or "/home/" not in encoded
