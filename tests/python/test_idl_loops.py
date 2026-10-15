# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def test_constant_loop_executes():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": (
                "Bits<8> count = 0; "
                "for (U32 i = 0; i < 5; i++) { count = count + 1; } "
                "return count;"
            ),
            "return_type": "Bits<8>",
            "observe": {"return": True},
        }
    )
    assert result["return_value"] == {"known": True, "value": "5"}


def test_uppercase_iteration_variable_rejects_mutable_update():
    result = run_semantic_case(
        {
            "root": "for_loop",
            "text": "for (U32 I = 0; I < 5; I = I + step) { I = I + 1; }",
            "setup": {"vars": [{"name": "step", "type": "Bits<5>"}]},
        }
    )
    assert result["error"] == "type"


def test_lowercase_iteration_variable_allows_mutable_update():
    result = run_semantic_case(
        {
            "root": "for_loop",
            "text": "for (U32 i = 0; i < 5; i = i + step) { i = i + 1; }",
            "setup": {"vars": [{"name": "step", "type": "Bits<5>"}]},
        }
    )
    assert result["ok"] is True


def test_iteration_variable_does_not_escape_loop_scope():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "for (U32 i = 0; i < 2; i++) { Bits<8> x = i; } return i;",
            "return_type": "Bits<8>",
        }
    )
    assert result["error"] == "type"
