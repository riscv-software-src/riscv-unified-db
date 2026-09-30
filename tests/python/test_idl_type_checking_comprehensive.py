# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import pytest
from idl_semantics_helpers import run_semantic_case


@pytest.mark.parametrize(
    ("text", "symbol", "expected"),
    [
        ("Bits<32> x = 0;", "x", "Bits<32>"),
        ("U64 x = 0;", "x", "Bits<64>"),
        ("Boolean flag = true;", "flag", "Boolean"),
        ("Bits<32> arr[10];", "arr", "array of Bits<32>"),
    ],
)
def test_declaration_types(text, symbol, expected):
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": text,
            "observe": {"execute": True, "symbols": [symbol]},
        }
    )
    assert result["ok"] is True
    assert result["symbols"][symbol]["type"]["text"] == expected


def test_struct_member_assignment_and_access():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\n"
                "struct S { Bits<32> field1; Boolean field2; }\n"
                "function f { returns Bits<32> description { f } "
                "body { S s; s.field1 = 7; return s.field1; } }\n"
            ),
        }
    )
    assert result["ok"] is True


def test_bitfield_member_assignment_and_access():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\n"
                "bitfield (32) B { HI 31-16 LO 15-0 }\n"
                "function f { returns Bits<32> description { f } "
                "body { B b; b.LO = 7; return $bits(b); } }\n"
            ),
        }
    )
    assert result["ok"] is True


def test_arithmetic_truncation_warns():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "4'hf + 4'h1",
            "observe": {"value": True},
        }
    )
    assert result["ok"] is True
    assert "truncat" in result["warnings"].lower()


def test_incompatible_assignment_is_rejected():
    result = run_semantic_case({"root": "function_body", "text": "Bits<8> x = true;"})
    assert result["error"] == "type"
    assert "Incompatible type" in result["message"]
