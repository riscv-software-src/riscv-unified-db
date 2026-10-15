# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import pytest
from idl_semantics_helpers import run_semantic_case

KEYWORDS = [
    "if",
    "else",
    "for",
    "return",
    "returns",
    "arguments",
    "description",
    "body",
    "function",
    "builtin",
    "generated",
    "enum",
    "bitfield",
]
BUILTIN_TYPES = ["XReg", "Boolean", "String", "U64", "U32", "Bits"]


@pytest.mark.parametrize("word", KEYWORDS + BUILTIN_TYPES)
def test_reserved_words_rejected_as_function_names(word):
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                f"%version: 1.0\nfunction {word} {{ description {{ bad }} body {{ return; }} }}\n"
            ),
        }
    )
    assert result["ok"] is False
    if result["error"] == "type":
        assert f"reserved word '{word}'" in result["message"]


@pytest.mark.parametrize("word", KEYWORDS)
def test_reserved_words_rejected_as_variable_names(word):
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\nfunction ok { description { ok } "
                f"body {{ Bits<8> {word}; }} }}\n"
            ),
        }
    )
    assert result["error"] == "type"
    assert f"reserved word '{word}'" in result["message"]


def test_keyword_substrings_remain_valid():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\nfunction iffy { description { ok } "
                "body { Bits<8> returning = 1; } }\n"
            ),
        }
    )
    assert result["ok"] is True


def test_question_mark_function_name_is_valid():
    result = run_semantic_case(
        {
            "root": "isa",
            "text": (
                "%version: 1.0\nfunction isValid? { returns Boolean "
                "description { ok } body { return true; } }\n"
            ),
        }
    )
    assert result["ok"] is True


@pytest.mark.parametrize(
    "definition",
    [
        "struct S { Bits<8> if; }",
        "function f { arguments Bits<8> if description { f } body { } }",
        "Bits<8> if;",
        "function f { description { f } body { for (U32 if = 0; if < 2; if++) { return; } } }",
        "enum E { CSR }",
        "bitfield (8) B { if 7-0 }",
    ],
)
def test_reserved_words_rejected_at_other_declaration_sites(definition):
    result = run_semantic_case({"root": "isa", "text": f"%version: 1.0\n{definition}\n"})
    assert result["error"] == "type"
    assert "reserved word" in result["message"]
