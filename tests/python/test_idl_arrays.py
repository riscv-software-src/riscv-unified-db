# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def test_array_element_assignment_executes():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<8> ary[4]; ary[2] = 7; return ary[2];",
            "return_type": "Bits<8>",
            "observe": {"return": True, "symbols": ["ary"]},
        }
    )
    assert result["return_value"] == {"known": True, "value": "7"}
    assert result["symbols"]["ary"]["value"]["value"] == ["0", "0", "7", "0"]


def test_nested_bits_element_assignment_executes():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<32> v[4]; v[1][0] = 1; return v[1];",
            "return_type": "Bits<32>",
            "observe": {"return": True},
        }
    )
    assert result["return_value"] == {"known": True, "value": "1"}


def test_nested_bits_range_assignment_executes():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<16> v[2]; v[1][7:4] = 10; return v[1];",
            "return_type": "Bits<16>",
            "observe": {"return": True},
        }
    )
    assert result["return_value"] == {"known": True, "value": "160"}


def test_array_index_is_bounds_checked():
    result = run_semantic_case({"root": "function_body", "text": "Bits<8> ary[4]; ary[4] = 1;"})
    assert result["error"] == "type"
    assert "out of range" in result["message"]
