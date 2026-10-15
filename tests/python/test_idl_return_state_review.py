# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Residual unknown-control-flow must not expose stale candidate return states."""

import pytest
from idl_semantics_helpers import run_semantic_case

CASES = [
    (
        "taken_if_trailing_writes",
        "Bits<8> y = 0; if (true) { Bits<8> z = u; y = 5; } y = y + 1; return y;",
        "y",
    ),
    (
        "function_trailing_writes",
        "Bits<8> y = 0; Bits<8> z = u; y = 5; return y;",
        "y",
    ),
    (
        "unknown_loop_condition",
        "Bits<8> x = 0; for (Bits<8> i = 0; i < u; i++) { x = 4; } return x;",
        "x",
    ),
]


@pytest.mark.parametrize(("case_id", "text", "written"), CASES)
def test_unknown_aborts_invalidate_potential_writes(case_id, text, written):
    result = run_semantic_case(
        {
            "id": case_id,
            "root": "function_body",
            "text": text,
            "setup": {"vars": [{"name": "u", "type": "Bits<8>"}]},
            "return_type": "Bits<8>",
            "observe": {"return": True, "symbols": [written]},
        }
    )
    assert result["ok"]
    assert result["return_value"]["known"] is False
    assert result["symbols"][written]["value"]["known"] is False
    assert result["return_values"]["known"] is False
