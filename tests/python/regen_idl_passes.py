# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Regenerate the frozen Ruby oracle corpus for slice-17 IDL passes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from idl_pass_adoc_cases import adoc_cases

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_pass_oracle.rb")
DATA_FILE = Path(__file__).parent / "data" / "idl" / "passes.json"
SCRATCH = REPOSITORY_ROOT / "gen" / "s17-pass-oracle"
CONFIGS = ["_", "rv32", "rv64", "qc_iu"]


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


def _mock_csrs() -> list[dict[str, Any]]:
    return [
        {
            "name": "mockcsr",
            "address": 0x300,
            "length": 32,
            "fields": [
                {"name": "ONE", "width": 16, "value": 1, "lsb": 0},
                {"name": "UNKNOWN", "width": 16, "lsb": 16},
            ],
        },
        {
            "name": "mockcsr2",
            "address": 0x301,
            "length": 32,
            "value": 1,
            "fields": [{"name": "ONE", "width": 32, "value": 1}],
        },
        {
            "name": "testcsr",
            "address": 0x302,
            "length": 32,
            "fields": [
                {"name": "FIELD1", "width": 8, "value": 1, "lsb": 0},
                {"name": "FIELD2", "width": 8, "value": 2, "lsb": 8},
                {"name": "FIELD3", "width": 16, "lsb": 16},
            ],
        },
    ]


def prune_cases() -> list[dict[str, Any]]:
    cases = [
        _case("prune_forced_type", "expression", "true ? 4'b0 : 5'b1", ["prune"]),
        _case(
            "prune_forced_type_nested",
            "expression",
            "true ? 4'b0 : (5'b1 * 1)",
            ["prune"],
        ),
    ]
    for name, operator in (
        ("multiply", "*"),
        ("divide", "/"),
        ("add", "+"),
        ("subtract", "-"),
        ("and", "&"),
        ("or", "|"),
    ):
        cases.append(
            _case(
                f"prune_forced_type_nested_{name}",
                "expression",
                f"false ? 5'b0 : 4'b1 {operator} 1",
                ["prune"],
            )
        )
    cases += [
        _case(
            "prune_forced_type_negative_value",
            "expression",
            "false ? 4'sb0 : -(8'sd1)",
            ["prune"],
        ),
        _case(
            "prune_function_body_negative_return_value",
            "function_body",
            "if (false) { return 1; } return -(64'sd1);",
            ["prune"],
            return_type="signed Bits<64>",
            setup={"possible_xlens": [32, 64]},
        ),
        _case(
            "prune_ternary",
            "expression",
            "(true) ? {1'b1, {31{1'b0}}} : {1'b1, {63{1'b0}}}",
            ["prune"],
        ),
        _case(
            "prune_ternary_unknown_bits",
            "expression",
            "(true) ? {1'b1, {31{1'bx}}} : {1'b1, {63{1'b0}}}",
            ["prune"],
        ),
        _case(
            "prune_nested_ternary_type_coercion",
            "expression",
            "true ? (false ? 8'b0 : 16'b1) : 32'd2",
            ["prune"],
        ),
        _case(
            "prune_complex_concatenation",
            "expression",
            "true ? {1'b1, {7{1'b0}}} : {1'b0, {15{1'b1}}}",
            ["prune"],
        ),
        _case(
            "prune_arithmetic_known_values",
            "expression",
            "true ? (5 `+ 3) : (10 - 2)",
            ["prune"],
        ),
        _case(
            "prune_logical_operations",
            "expression",
            "true ? (true && false) : (true || false)",
            ["prune"],
        ),
        _case(
            "prune_bitwise_operations",
            "expression",
            "true ? (8'hFF & 8'h0F) : (8'hAA | 8'h55)",
            ["prune"],
        ),
        _case(
            "prune_shift_operations",
            "expression",
            "true ? (8'h01 << 3) : (8'h80 >> 3)",
            ["prune"],
        ),
        _case(
            "prune_comparison_operations",
            "expression",
            "true ? (5 > 3) : (2 < 1)",
            ["prune"],
        ),
        _case(
            "prune_nested_if_statements",
            "function_body",
            "if (true) { if (false) { return 1; } else { return 2; } }",
            ["prune"],
            return_type="Bits<32>",
        ),
        _case(
            "prune_unknown_condition_preserved",
            "expression",
            "unknown_var ? 1 : 2",
            ["prune"],
            setup={"vars": [{"name": "unknown_var", "type": "Bits<unknown>"}]},
        ),
    ]
    csr_setup = {"possible_xlens": [32, 64], "csrs": _mock_csrs()}
    cases += [
        _case(
            "prune_csr_known_field",
            "function_body",
            "if (CSR[mockcsr].ONE == 1) { return 1; }",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_csr_unknown_field",
            "function_body",
            "if (CSR[mockcsr].UNKNOWN == 1) { return 1; }",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_csr_field_assignment",
            "function_body",
            "CSR[mockcsr].UNKNOWN = CSR[mockcsr].ONE;",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_unknown_csr_bits_cast",
            "function_body",
            "Bits<32> tmp = $bits(CSR[mockcsr]);",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_known_csr_bits_cast",
            "function_body",
            "Bits<32> tmp = $bits(CSR[mockcsr2]);",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_multiple_known_csr_fields",
            "function_body",
            ("if (CSR[testcsr].FIELD1 == 1 && CSR[testcsr].FIELD2 == 2) { return 1; }"),
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_preserves_unknown_csr_field",
            "function_body",
            "if (CSR[testcsr].FIELD3 == 1) { return 1; }",
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        ),
        _case(
            "prune_type_width_mismatch",
            "expression",
            "true ? 4'b1111 : 8'b00000000",
            ["prune"],
        ),
        _case(
            "prune_complex_expression_tree",
            "expression",
            "true ? (false ? 1 : (true ? 2 : 3)) : 4",
            ["prune"],
        ),
    ]
    leak_programs = {
        "if_body_does_not_leak_assignments": (
            "Bits<32> a = 10; "
            "if (CSR[mockcsr].UNKNOWN == 1) { a = 0xdeadbeef; } "
            "Bits<32> result = a;"
        ),
        "conditional_statement_does_not_leak_assignment": (
            "Bits<32> a = 10; a = 0xdeadbeef if (CSR[mockcsr].UNKNOWN == 1); Bits<32> result = a;"
        ),
        "for_loop_does_not_leak_assignments": (
            "Bits<32> a = 10; for (Bits<8> i = 0; i < 4; i++) { a = i; } Bits<32> result = a;"
        ),
        "ary_range_assignment_does_not_leak": (
            "Bits<32> vec = 0; "
            "if (CSR[mockcsr].UNKNOWN == 1) { vec[7:0] = 0xff; } "
            "Bits<32> result = vec;"
        ),
        "ary_range_assignment_execute_updates_value": (
            "Bits<32> vec = 0x12340000; "
            "if (CSR[mockcsr].ONE == 1) { vec[7:0] = 0xab; } "
            "Bits<32> result = vec + 0;"
        ),
        "post_increment_does_not_leak": (
            "Bits<32> result = 0; "
            "for (Bits<8> i = 0; i < 4; i++) { result = i; } "
            "Bits<32> final = result;"
        ),
        "post_decrement_does_not_leak": (
            "Bits<32> result = 0; "
            "for (Bits<8> i = 3; i > 0; i--) { result = i; } "
            "Bits<32> final = result;"
        ),
        "multiple_assignments_unknown_branch_do_not_leak": (
            "Bits<32> a = 1; Bits<32> b = 2; "
            "if (CSR[mockcsr].UNKNOWN == 1) { a = 10; b = 20; } "
            "Bits<32> result_a = a; Bits<32> result_b = b;"
        ),
        "multiple_conditional_modifiers_do_not_leak": (
            "Bits<32> result = 0; "
            "result = 0x1111 if (CSR[mockcsr].UNKNOWN == 1); "
            "result = 0x2222 if (CSR[mockcsr].UNKNOWN == 2); "
            "Bits<32> final = result;"
        ),
        "for_loop_nested_unknown_if_does_not_leak": (
            "Bits<32> result = 0; "
            "if (CSR[mockcsr].UNKNOWN == 1) { "
            "for (Bits<8> i = 0; i < 4; i++) { result = 1; } } "
            "Bits<32> final = result;"
        ),
    }
    cases.extend(
        _case(
            f"prune_{name}",
            "function_body",
            text,
            ["prune"],
            return_type="Bits<32>",
            setup=csr_setup,
        )
        for name, text in leak_programs.items()
    )
    return cases


def reachability_cases() -> list[dict[str, Any]]:
    def isa(case_id: str, definitions: str, target: str, pass_name: str):
        return _case(
            case_id,
            "isa",
            f"%version: 1.0\n{definitions}",
            [pass_name],
            target=target,
            setup={"possible_xlens": [32, 64]},
        )

    cases = [
        isa(
            "reachable_direct_call",
            """
function b { description { b } body { } }
function a { description { a } body { b(); } }
""",
            "a",
            "reachable_functions",
        ),
        isa(
            "reachable_transitive_closure",
            """
function d { description { d } body { } }
function c { description { c } body { d(); } }
function b { description { b } body { c(); } }
function a { description { a } body { b(); } }
""",
            "a",
            "reachable_functions",
        ),
        isa(
            "reachable_diamond_unique",
            """
function d { description { d } body { } }
function b { description { b } body { d(); } }
function c { description { c } body { d(); } }
function a { description { a } body { b(); c(); } }
""",
            "a",
            "reachable_functions",
        ),
        isa(
            "reachable_excludes_uncalled_function",
            """
function b { description { b } body { } }
function c { description { c } body { } }
function a { description { a } body { b(); } }
""",
            "a",
            "reachable_functions",
        ),
        isa(
            "reachable_empty_body",
            "function empty_fn { description { empty } body { } }",
            "empty_fn",
            "reachable_functions",
        ),
        isa(
            "reachable_known_argument_path",
            """
enum Branch { Left 0 Right 1 }
function go_left { description { left } body { } }
function go_right { description { right } body { } }
function dispatcher {
  arguments Branch branch
  description { dispatch }
  body {
    if (branch == Branch::Left) { go_left(); } else { go_right(); }
  }
}
function entry {
  description { entry }
  body { dispatcher(Branch::Left); }
}
""",
            "entry",
            "reachable_functions",
        ),
        isa(
            "reachable_unknown_path_includes_both",
            """
Bits<64> unknown_val;
function go_left { description { left } body { } }
function go_right { description { right } body { } }
function dispatcher {
  description { dispatch }
  body {
    if (unknown_val == 1) { go_left(); } else { go_right(); }
  }
}
""",
            "dispatcher",
            "reachable_functions",
        ),
        isa(
            "reachable_builtin_included",
            """
builtin function my_builtin { description { builtin } }
function caller { description { caller } body { my_builtin(); } }
""",
            "caller",
            "reachable_functions",
        ),
        _case(
            "reachable_shared_cache_transitive",
            "isa",
            """
%version: 1.0
function leaf { description { leaf } body { } }
function middle { description { middle } body { leaf(); } }
function caller1 { description { caller1 } body { middle(); } }
function caller2 { description { caller2 } body { middle(); } }
""",
            ["reachable_functions_shared"],
            shared_targets=["caller1", "caller2"],
            setup={"possible_xlens": [32, 64]},
        ),
    ]
    exception_prelude = """
enum Choice { A 0 B 1 }
enum ExceptionCode { ACode 0 BCode 1 CCode 4 }
builtin function raise {
  arguments ExceptionCode code
  description { raise }
}
builtin function raise_precise {
  arguments ExceptionCode code
  description { raise precise }
}
"""
    cases += [
        isa(
            "exceptions_transitive_known_argument",
            exception_prelude
            + """
function nested_choose {
  arguments Choice choice
  description { nested }
  body {
    if (choice == Choice::A) {
      raise(ExceptionCode::ACode);
    } else {
      raise(ExceptionCode::BCode);
    }
  }
}
function choose {
  arguments Choice choice
  description { choose }
  body { nested_choose(choice); }
}
function test { description { test } body { choose(Choice::B); } }
""",
            "test",
            "reachable_exceptions",
        ),
        isa(
            "exceptions_known_path_under_unknown_path",
            exception_prelude
            + """
Bits<64> unknown;
function choose {
  arguments Choice choice
  description { choose }
  body {
    if (unknown == 1) {
      if (choice == Choice::A) {
        raise(ExceptionCode::ACode);
      } else {
        raise(ExceptionCode::BCode);
      }
    }
  }
}
function test { description { test } body { choose(Choice::B); } }
""",
            "test",
            "reachable_exceptions",
        ),
        isa(
            "exceptions_unknown_branch_union",
            exception_prelude
            + """
Bits<64> unknown;
function test {
  description { test }
  body {
    if (unknown == 0) {
      raise(ExceptionCode::ACode);
    } else {
      raise_precise(ExceptionCode::CCode);
    }
  }
}
""",
            "test",
            "reachable_exceptions",
        ),
        isa(
            "exceptions_empty_body",
            exception_prelude + "function test { description { test } body { } }",
            "test",
            "reachable_exceptions",
        ),
    ]
    return cases


def discovery_cases() -> list[dict[str, Any]]:
    register_setup = {
        "mxlen": 64,
        "possible_xlens": [64],
        "register_files": [
            {"name": "X", "width": "MXLEN", "count": 32},
            {"name": "F", "width": 64, "count": 32},
        ],
        "vars": [
            {"name": "rs1", "type": "Bits<5>", "value": 3},
            {"name": "rs2", "type": "Bits<5>", "value": 4},
            {"name": "rd", "type": "Bits<5>", "value": 7},
            {"name": "unknown_idx", "type": "Bits<5>"},
            {"name": "v", "type": "Bits<64>"},
        ],
    }
    cases = [
        _case(
            "source_register_f_known_index",
            "expression",
            "F[rs1]",
            ["source_registers"],
            setup=register_setup,
        ),
        _case(
            "destination_register_f_known_index",
            "function_body",
            "F[rd] = v;",
            ["destination_registers"],
            return_type="void",
            setup=register_setup,
        ),
        _case(
            "source_register_x_known_index",
            "expression",
            "X[rs2]",
            ["source_registers"],
            setup=register_setup,
        ),
        _case(
            "register_reads_are_unique",
            "function_body",
            "Bits<64> a = F[rs1]; Bits<64> b = F[rs1]; Bits<64> c = X[rs2];",
            ["source_registers"],
            return_type="void",
            setup=register_setup,
        ),
        _case(
            "destination_register_nested_bit_write",
            "function_body",
            "F[rd][3] = 1;",
            ["destination_registers"],
            return_type="void",
            setup=register_setup,
        ),
        _case(
            "destination_register_nested_range_write",
            "function_body",
            "F[rd][7:0] = 8'hff;",
            ["destination_registers"],
            return_type="void",
            setup=register_setup,
        ),
        _case(
            "source_register_unknown_index",
            "expression",
            "F[unknown_idx]",
            ["source_registers"],
            setup=register_setup,
        ),
        _case(
            "destination_register_unknown_index",
            "function_body",
            "F[unknown_idx] = v;",
            ["destination_registers"],
            return_type="void",
            setup=register_setup,
        ),
        _case(
            "local_array_is_not_register_file",
            "function_body",
            "Bits<64> values[4]; Bits<64> a = values[1]; values[2] = a;",
            ["source_registers", "destination_registers"],
            return_type="void",
            setup=register_setup,
        ),
    ]
    csr_setup = {
        "possible_xlens": [32, 64],
        "csrs": _mock_csrs(),
        "vars": [{"name": "value", "type": "Bits<32>"}],
    }
    cases += [
        _case(
            "referenced_csr_read",
            "expression",
            "CSR[mockcsr]",
            ["referenced_csrs"],
            setup=csr_setup,
        ),
        _case(
            "referenced_csr_field_read",
            "expression",
            "CSR[mockcsr].ONE",
            ["referenced_csrs"],
            setup=csr_setup,
        ),
        _case(
            "referenced_csr_field_write",
            "function_body",
            "CSR[mockcsr].UNKNOWN = value;",
            ["referenced_csrs"],
            return_type="void",
            setup=csr_setup,
        ),
        _case(
            "referenced_csr_software_write",
            "function_body",
            "CSR[mockcsr].sw_write(value);",
            ["referenced_csrs"],
            return_type="void",
            setup=csr_setup,
        ),
        _case(
            "referenced_csrs_unique_sorted",
            "function_body",
            (
                "Bits<32> a = $bits(CSR[testcsr]); "
                "Bits<32> b = $bits(CSR[mockcsr]); "
                "Bits<32> c = $bits(CSR[testcsr]);"
            ),
            ["referenced_csrs"],
            return_type="void",
            setup=csr_setup,
        ),
        _case(
            "no_referenced_csrs",
            "function_body",
            "Bits<32> a = value + 1;",
            ["referenced_csrs"],
            return_type="void",
            setup=csr_setup,
        ),
    ]
    return cases


def return_value_cases() -> list[dict[str, Any]]:
    setup = {
        "vars": [
            {"name": "a", "type": "Boolean"},
            {"name": "b", "type": "Boolean"},
            {"name": "c", "type": "Boolean"},
        ]
    }

    def result(expression: str, conditions: list[str]) -> dict[str, Any]:
        return {"expression": expression, "conditions": conditions}

    def case(case_id: str, text: str, values: list[dict[str, Any]]):
        return _case(
            case_id,
            "function_body",
            text,
            ["return_values"],
            return_type="Bits<8>",
            setup=setup,
            python_expect={
                "passes": {
                    "return_values": {
                        "ok": True,
                        "value": values,
                    }
                }
            },
        )

    return [
        case("return_values_empty", "", []),
        case("return_values_direct", "return 1;", [result("1", [])]),
        case(
            "return_values_if_without_else",
            "if (a) { return 1; }",
            [result("1", ["a"])],
        ),
        case(
            "return_values_if_else",
            "if (a) { return 1; } else { return 2; }",
            [result("1", ["a"]), result("2", ["!a"])],
        ),
        case(
            "return_values_else_if",
            ("if (a) { return 1; } else if (b) { return 2; } else { return 3; }"),
            [
                result("1", ["a"]),
                result("2", ["!a", "b"]),
                result("3", ["!a", "!b"]),
            ],
        ),
        case(
            "return_values_nested_conditions",
            ("if (a) { if (b) { return 1; } else { return 2; } } else { return 3; }"),
            [
                result("1", ["a", "b"]),
                result("2", ["a", "!b"]),
                result("3", ["!a"]),
            ],
        ),
        case(
            "return_values_ternary",
            "return a ? 1 : 2;",
            [result("1", ["a"]), result("2", ["!a"])],
        ),
        case(
            "return_values_sequential",
            "return 1; return 2 if (c);",
            [result("1", []), result("2", ["c"])],
        ),
    ]


def build_cases() -> list[dict[str, Any]]:
    cases = (
        prune_cases()
        + reachability_cases()
        + discovery_cases()
        + return_value_cases()
        + adoc_cases()
    )
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate pass corpus case id")
    return cases


def real_samples() -> list[dict[str, Any]]:
    samples = [
        {"id": f"inst_{name}", "kind": "instruction", "name": name}
        for name in ("add", "lw", "csrrw", "vadd.vv", "fence", "ecall")
    ]
    samples += [
        {"id": f"function_{name}", "kind": "function", "name": name}
        for name in ("xlen", "read_memory", "mstatus_sd_reset_value")
    ]
    for xlen in (32, 64):
        samples += [
            {
                "id": f"csr_misa_sw_read_rv{xlen}",
                "kind": "csr",
                "csr": "misa",
                "body": "sw_read",
                "xlen": xlen,
            },
            {
                "id": f"csr_misa_f_type_rv{xlen}",
                "kind": "csr",
                "csr": "misa",
                "field": "F",
                "body": "field_type",
                "xlen": xlen,
            },
            {
                "id": f"csr_misa_f_reset_rv{xlen}",
                "kind": "csr",
                "csr": "misa",
                "field": "F",
                "body": "field_reset",
                "xlen": xlen,
            },
            {
                "id": f"csr_misa_f_sw_write_rv{xlen}",
                "kind": "csr",
                "csr": "misa",
                "field": "F",
                "body": "field_sw_write",
                "xlen": xlen,
            },
            {
                "id": f"csr_mtvec_mode_type_rv{xlen}",
                "kind": "csr",
                "csr": "mtvec",
                "field": "MODE",
                "body": "field_type",
                "xlen": xlen,
            },
            {
                "id": f"csr_mtvec_mode_reset_rv{xlen}",
                "kind": "csr",
                "csr": "mtvec",
                "field": "MODE",
                "body": "field_reset",
                "xlen": xlen,
            },
            {
                "id": f"csr_mtvec_mode_sw_write_rv{xlen}",
                "kind": "csr",
                "csr": "mtvec",
                "field": "MODE",
                "body": "field_sw_write",
                "xlen": xlen,
            },
            {
                "id": f"csr_mstatus_sd_type_rv{xlen}",
                "kind": "csr",
                "csr": "mstatus",
                "field": "SD",
                "body": "field_type",
                "xlen": xlen,
            },
            {
                "id": f"csr_mstatus_sd_reset_rv{xlen}",
                "kind": "csr",
                "csr": "mstatus",
                "field": "SD",
                "body": "field_reset",
                "xlen": xlen,
            },
        ]
    return samples


def run_oracle(
    cases: list[dict[str, Any]],
    *,
    include_real: bool,
) -> dict[str, Any]:
    payload = {
        "cases": cases,
        "configs": CONFIGS if include_real else [],
        "real_samples": real_samples(),
        "scratch": str(SCRATCH),
    }
    command = ["bundle", "exec", "ruby", str(RUBY_ORACLE)]
    process = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        sys.stderr.write(process.stderr)
        raise SystemExit(process.returncode)
    return json.loads(process.stdout)


def build_document(*, include_real: bool = True) -> dict[str, Any]:
    cases = build_cases()
    oracle = run_oracle(cases, include_real=include_real)
    by_id = {result["id"]: result for result in oracle["synthetic"]}
    frozen = []
    for case in cases:
        item = dict(case)
        result = by_id[case["id"]]
        result.pop("id")
        item["expect"] = result
        frozen.append(item)
    return {
        "schema_version": 1,
        "ruby_oracle": RUBY_ORACLE.name,
        "configs": CONFIGS,
        "cases": frozen,
        "real_samples": real_samples(),
        "real": oracle["real"],
    }


def main() -> None:
    include_real = "--synthetic-only" not in sys.argv
    document = build_document(include_real=include_real)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(document['cases'])} synthetic cases and "
        f"{len(document['real'])} real configurations to {DATA_FILE}"
    )


if __name__ == "__main__":
    main()
