# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def test_declaration_assignment_and_execution():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<8> x; x = 9; return x;",
            "return_type": "Bits<8>",
            "observe": {"return": True, "symbols": ["x"]},
        }
    )
    assert result["return_value"] == {"known": True, "value": "9"}
    assert result["symbols"]["x"]["type"]["text"] == "Bits<8>"


def test_constants_are_read_only():
    result = run_semantic_case(
        {"root": "function_body", "text": "Bits<8> Constant = 1; Constant = 2;"}
    )
    assert result["error"] == "type"
    assert "Cannot assign to a const" in result["message"]


def test_inner_scope_may_shadow_outer_variable():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<8> x = 1; if (true) { Bits<8> x = 2; } return x;",
            "return_type": "Bits<8>",
            "observe": {"return": True},
        }
    )
    assert result["return_value"] == {"known": True, "value": "1"}


def test_same_scope_duplicate_is_rejected():
    result = run_semantic_case({"root": "function_body", "text": "Bits<8> x = 1; Bits<8> x = 2;"})
    assert result["ok"] is False
