# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def test_range_operator_is_checked_in_strict_mode():
    loose = run_semantic_case(
        {
            "root": "expression",
            "text": "a[9:0]",
            "setup": {"vars": [{"name": "a", "type": "Bits<8>", "value": 0}]},
        }
    )
    assert loose["ok"] is True

    strict = run_semantic_case(
        {
            "root": "expression",
            "text": "a[9:0]",
            "strict": True,
            "setup": {"vars": [{"name": "a", "type": "Bits<8>", "value": 0}]},
        }
    )
    assert strict["error"] == "type"


def test_unknown_variable_value_raises_unknown_not_type_error():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "a + 1",
            "setup": {"vars": [{"name": "a", "type": "Bits<8>"}]},
            "observe": {"value": True},
        }
    )
    assert result["ok"] is True
    assert result["value"]["known"] is False


def test_unknown_condition_reports_all_known_branch_returns():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "if (flag) { return 1; } else { return 2; }",
            "return_type": "Bits<8>",
            "setup": {"vars": [{"name": "flag", "type": "Boolean"}]},
            "observe": {"return": True},
        }
    )
    assert result["return_value"]["known"] is False
    assert result["return_values"] == {"known": True, "value": ["1", "2"]}
