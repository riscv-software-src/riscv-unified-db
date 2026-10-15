# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case


def _isa(definitions: str) -> str:
    return f"%version: 1.0\n{definitions}\n"


def test_function_definition_and_call():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": _isa(
                "function add { returns Bits<8> arguments Bits<8> a, Bits<8> b "
                "description { add } body { return a + b; } }\n"
                "function caller { returns Bits<8> description { caller } "
                "body { return add(2, 3); } }"
            ),
            "observe": {"functions": True},
        }
    )
    assert result["ok"] is True
    assert [function["name"] for function in result["functions"]] == ["add", "caller"]


def test_wrong_arity_is_rejected():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": _isa(
                "function f { arguments Bits<8> a description { f } body { } }\n"
                "function caller { description { caller } body { f(); } }"
            ),
        }
    )
    assert result["error"] == "type"
    assert "Wrong number of arguments" in result["message"]


def test_multiple_return_destructuring():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": _isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } "
                "body { return 1, 2; } }\n"
                "function caller { returns Bits<8> description { caller } "
                "body { Bits<8> a, b; (a, b) = pair(); return a + b; } }"
            ),
        }
    )
    assert result["ok"] is True


def test_multiple_return_arity_mismatch_is_rejected():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": _isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } "
                "body { return 1, 2; } }\n"
                "function caller { description { caller } "
                "body { Bits<8> a; (a, -, -) = pair(); } }"
            ),
        }
    )
    assert result["error"] == "type"


def test_builtin_and_generated_functions_are_registered():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": _isa(
                "builtin function b { returns Bits<8> description { builtin } }\n"
                "generated function g { returns Bits<8> description { generated } }"
            ),
            "observe": {"functions": True},
        }
    )
    assert [(f["name"], f["builtin"], f["generated"]) for f in result["functions"]] == [
        ("b", True, False),
        ("g", False, True),
    ]
