# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import pytest
from idl_semantics_helpers import run_semantic_case


def _program(argument: str, declarations: str = "") -> str:
    return (
        "%version: 1.0\n"
        "function consume { arguments Bits<32> ConstArg description { consume } body { } }\n"
        "function caller { description { caller } body { "
        f"{declarations} consume({argument});"
        " } }\n"
    )


@pytest.mark.parametrize(
    ("name", "argument", "declarations"),
    [
        ("literal", "42", ""),
        ("constant", "Const", "Bits<32> Const = 42;"),
        ("constant_expression", "Const1 + Const2", "Bits<32> Const1 = 42; Bits<32> Const2 = 10;"),
    ],
)
def test_const_argument_accepts_const_expression(name, argument, declarations):
    result = run_semantic_case(
        {"root": "isa", "text": _program(argument, declarations), "case_name": name}
    )
    assert result["ok"] is True


@pytest.mark.parametrize(
    ("argument", "declarations"),
    [
        ("mutable_var", "Bits<32> mutable_var = 42;"),
        ("Const + mutable_var", "Bits<32> Const = 42; Bits<32> mutable_var = 10;"),
    ],
)
def test_const_argument_rejects_mutable_expression(argument, declarations):
    result = run_semantic_case({"root": "isa", "text": _program(argument, declarations)})
    assert result["error"] == "type"
    assert "mutable expression" in result["message"]


def test_mutable_argument_accepts_both_const_and_mutable_values():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\n"
                "function consume { arguments Bits<32> value description { consume } body { } }\n"
                "function caller { description { caller } body { "
                "Bits<32> Const = 42; Bits<32> mutable_var = 10; "
                "consume(Const); consume(mutable_var); } }\n"
            ),
        }
    )
    assert result["ok"] is True
