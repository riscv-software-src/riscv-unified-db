# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Synthetic normal and option AsciiDoc cases for the slice-17 oracle."""

from __future__ import annotations

from typing import Any


def _case(
    case_id: str,
    root: str,
    text: str,
    passes: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "root": root,
        "text": text,
        "passes": passes,
        **kwargs,
    }


def adoc_cases() -> list[dict[str, Any]]:
    cases = [
        _case("adoc_integer", "expression", "8'hff", ["adoc"]),
        _case("adoc_boolean", "expression", "true", ["adoc"]),
        _case("adoc_string", "expression", '"quoted"', ["adoc"]),
        _case("adoc_binary_escaping", "expression", "a + b `+ c", ["adoc"]),
        _case("adoc_unary", "expression", "!a", ["adoc"]),
        _case("adoc_parentheses", "expression", "(a + b)", ["adoc"]),
        _case("adoc_ternary", "expression", "a == 1 ? b : c", ["adoc"]),
        _case(
            "adoc_concatenation_replication",
            "expression",
            "{a, {3{b}}}",
            ["adoc"],
        ),
        _case("adoc_bits_cast", "expression", "$bits(a)", ["adoc"]),
        _case("adoc_signed_cast", "expression", "$signed(a)", ["adoc"]),
        _case(
            "adoc_array_builtins",
            "expression",
            "$array_includes?(values, $array_size(values))",
            ["adoc"],
        ),
        _case("adoc_enum_reference", "expression", "Mode::Machine", ["adoc"]),
        _case(
            "adoc_function_call_link",
            "expression",
            "helper(a, 2)",
            ["adoc"],
        ),
        _case(
            "adoc_csr_links",
            "function_body_syntax",
            (
                "Bits<32> a = $bits(CSR[mstatus]); "
                "Bits<1> b = CSR[mstatus].MIE; "
                "CSR[mstatus].MIE = b; "
                "CSR[mstatus].sw_write(a);"
            ),
            ["adoc"],
        ),
        _case(
            "adoc_declarations_assignments",
            "function_body_syntax",
            (
                "Bits<8> a; Bits<8> b = 1; Bits<8> values[4]; "
                "a = b; values[2] = a; values[1][3:0] = 4'hf; "
                "$pc = a;"
            ),
            ["adoc"],
        ),
        _case(
            "adoc_if_else",
            "function_body_syntax",
            ("if (a) { b = 1; } else if (c) { b = 2; } else { b = 3; }"),
            ["adoc"],
        ),
        _case(
            "adoc_conditional_statements",
            "function_body_syntax",
            "b = 1 if (a); return b if (c);",
            ["adoc"],
        ),
        _case(
            "adoc_for_loop",
            "function_body_syntax",
            "for (Bits<8> i = 0; i < 4; i++) { values[i] = i; }",
            ["adoc"],
        ),
        _case(
            "adoc_multi_return_and_assignment",
            "function_body_syntax",
            "(a, -, b) = helper(); return a, b;",
            ["adoc"],
            python_expect={
                "passes": {
                    "adoc": {
                        "ok": True,
                        "value": (
                            "(a, -, b) = "
                            "%%UDB_DOC_LINK%func;helper;helper%%pass:[()];\n"
                            "return a, b;"
                        ),
                    }
                }
            },
        ),
        _case("adoc_empty_body", "function_body_syntax", "", ["adoc"]),
    ]
    option_cases = [
        _case(
            "option_adoc_if_else",
            "function_body_syntax",
            "if (a == 1) { return 2; } else { return 3; }",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_else_if",
            "function_body_syntax",
            ("if (a) { return true; } else if (b) { return false; } else { return c; }"),
            ["option_adoc"],
        ),
        _case(
            "option_adoc_ternary_binary",
            "function_body_syntax",
            "return (a == 1) ? 2 : 3;",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_ternary_identifier",
            "function_body_syntax",
            "return a ? 2 : 3;",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_function_call",
            "function_body_syntax",
            "helper(a);",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_undefined_legal",
            "function_body_syntax",
            "return 36893488147419103232;",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_undefined_legal_deterministic",
            "function_body_syntax",
            "return 73786976294838206464;",
            ["option_adoc"],
        ),
        _case(
            "option_adoc_csr_field_types",
            "function_body_syntax",
            (
                "if (a) { return CsrFieldType::ROH; } "
                "else if (b) { return CsrFieldType::RWRH; } "
                "else { return CsrFieldType::RW; }"
            ),
            ["option_adoc"],
        ),
        _case(
            "option_adoc_array_element",
            "function_body_syntax",
            ("return ($array_size(MTVEC_MODES) == 1) ? MTVEC_MODES[0] : UNDEFINED_LEGAL;"),
            ["option_adoc"],
            python_expect={
                "passes": {
                    "option_adoc": {
                        "ok": True,
                        "value": (
                            '[when,"$array_size(MTVEC_MODES) == 1"]\n'
                            "MTVEC_MODES[0]\n\n"
                            '[when,"$array_size(MTVEC_MODES) != 1"]\n'
                            "UNDEFINED_LEGAL\n\n"
                        ),
                    }
                }
            },
        ),
    ]
    return cases + option_cases
