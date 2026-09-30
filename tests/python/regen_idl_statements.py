# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Build and regenerate the frozen slice-15 IDL statement-semantics corpus.

The case list is rebuilt from Ruby's data-driven semantic fixtures plus
black-box adversarial programs below. Ruby supplies every frozen expectation;
pytest reads only ``statements.json`` unless ``UDB_TEST_RUBY=1`` is set.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_statement_oracle.rb")
DATA_FILE = Path(__file__).parent / "data" / "idl" / "statements.json"
RUBY_DATA = REPOSITORY_ROOT / "tools" / "ruby-gems" / "idlc" / "test" / "data"
BATCH_SIZE = 32


def _case(case_id: str, root: str, text: str, **kwargs: Any) -> dict[str, Any]:
    return {"id": case_id, "root": root, "text": text, **kwargs}


def _yaml_cases() -> list[dict[str, Any]]:
    yaml = YAML(typ="safe")
    cases: list[dict[str, Any]] = []

    type_data = yaml.load((RUBY_DATA / "type_checking_tests.yaml").read_text())
    for category, entries in type_data.items():
        for entry in entries:
            case_id = f"ruby_type__{category}__{entry['name']}"
            source = {
                "fixture": "type_checking_tests.yaml",
                "category": category,
                "name": entry["name"],
                "should_pass": entry["should_pass"],
                "expected_error": entry.get("expected_error"),
                "expected_type": entry.get("expected_type"),
            }
            if entry["test_type"] == "expression":
                cases.append(
                    _case(
                        case_id,
                        "expression",
                        entry["idl"],
                        source=source,
                        setup={"possible_xlens": [32, 64]},
                        observe={"type": True},
                    )
                )
            else:
                name_match = re.search(r"\b([A-Za-z_]\w*)\s*=", entry["idl"])
                symbol = name_match.group(1) if name_match else "x"
                cases.append(
                    _case(
                        case_id,
                        "function_body",
                        f"{entry['idl']};",
                        source=source,
                        setup={"possible_xlens": [32, 64]},
                        observe={"symbols": [symbol]},
                    )
                )

    flow_data = yaml.load((RUBY_DATA / "control_flow_tests.yaml").read_text())
    for category, entries in flow_data.items():
        for entry in entries:
            case_id = f"ruby_flow__{category}__{entry['name']}"
            source = {
                "fixture": "control_flow_tests.yaml",
                "category": category,
                "name": entry["name"],
                "should_pass": entry["should_pass"],
                "expected_error": entry.get("expected_error"),
                "context": entry["context"],
            }
            if entry["context"] == "root":
                text = f"%version: 1.0\n\n{entry['idl']}"
            else:
                text = (
                    "%version: 1.0\n\n"
                    "function test_function {\n"
                    "  returns Bits<32>\n"
                    "  description { semantic fixture }\n"
                    "  body {\n"
                    f"{entry['idl']}\n"
                    "    return 32'd0;\n"
                    "  }\n"
                    "}\n"
                )
            cases.append(
                _case(
                    case_id,
                    "isa",
                    text,
                    source=source,
                    setup={"possible_xlens": [32, 64]},
                    observe={"functions": True},
                )
            )
    return cases


def _adversarial_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    # Declarations, initialization, assignment, width conversion and execution.
    for width in range(1, 25):
        mask = (1 << min(width, 12)) - 1
        cases.append(
            _case(
                f"adv_decl_bits_{width}",
                "function_body",
                f"Bits<{width}> x = {mask}; return x;",
                return_type=f"Bits<{width}>",
                observe={"return": True, "symbols": ["x"], "const_eval": True},
            )
        )
    for width in range(2, 18):
        cases.append(
            _case(
                f"adv_reassign_bits_{width}",
                "function_body",
                f"Bits<{width}> x = 0; x = {width}; return x;",
                return_type=f"Bits<{width}>",
                observe={"return": True, "symbols": ["x"]},
            )
        )
    cases += [
        _case(
            "adv_const_reassignment",
            "function_body",
            "Bits<8> Constant = 1; Constant = 2;",
        ),
        _case(
            "adv_uninitialized_then_assign",
            "function_body",
            "Bits<8> x; x = 3; return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case("adv_assign_bool_to_bits", "function_body", "Bits<8> x = 0; x = true;"),
        _case("adv_assign_bits_to_bool", "function_body", "Boolean x = false; x = 1;"),
        _case(
            "adv_shadow_inner_scope",
            "function_body",
            "Bits<8> x = 1; if (true) { Bits<8> x = 2; } return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case("adv_duplicate_same_scope", "function_body", "Bits<8> x = 1; Bits<8> x = 2;"),
        _case(
            "adv_conditional_assignment_true",
            "function_body",
            "Bits<8> x = 1; x = 7 if true; return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case(
            "adv_conditional_assignment_false",
            "function_body",
            "Bits<8> x = 1; x = 7 if false; return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case(
            "adv_range_write",
            "function_body",
            "Bits<16> x = 0; x[7:4] = 15; return x;",
            return_type="Bits<16>",
            observe={"return": True},
        ),
        _case(
            "adv_bit_write",
            "function_body",
            "Bits<8> x = 0; x[3] = 1; return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case("adv_range_write_bad_order", "function_body", "Bits<8> x = 0; x[2:5] = 0;"),
        _case("adv_bit_write_bad_index", "function_body", "Bits<8> x = 0; x[8] = 1;"),
    ]
    for operator, expression in [
        ("add", "4'hf + 4'h1"),
        ("subtract", "4'h0 - 4'h1"),
        ("multiply", "4'hf * 4'hf"),
        ("left_shift", "4'hf << 2"),
        ("unary", "-4'sd8"),
    ]:
        cases.append(
            _case(
                f"adv_truncation_warning_{operator}",
                "expression",
                expression,
                observe={"type": True, "value": True},
            )
        )

    # Arrays and nested aggregate execution.
    for index in range(12):
        cases.append(
            _case(
                f"adv_array_write_{index}",
                "function_body",
                f"Bits<8> ary[12]; ary[{index}] = {index}; return ary[{index}];",
                return_type="Bits<8>",
                observe={"return": True, "symbols": ["ary"]},
            )
        )
    cases += [
        _case("adv_array_bad_index", "function_body", "Bits<8> ary[4]; ary[4] = 1;"),
        _case("adv_array_bad_index_type", "function_body", "Bits<8> ary[4]; ary[true] = 1;"),
        _case("adv_array_bad_value_type", "function_body", "Bits<8> ary[4]; ary[0] = true;"),
        _case(
            "adv_nested_array_bit_write",
            "function_body",
            "Bits<8> ary[2]; ary[1][3] = 1; return ary[1];",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case(
            "adv_nested_array_range_write",
            "function_body",
            "Bits<16> ary[2]; ary[1][7:4] = 10; return ary[1];",
            return_type="Bits<16>",
            observe={"return": True},
        ),
        _case(
            "adv_multi_declaration",
            "function_body",
            "Bits<8> a, b, c; a = 1; b = 2; c = 3; return a + b + c;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
    ]

    # If/else, conditional returns and all-path return behavior.
    for value in range(10):
        cases.append(
            _case(
                f"adv_if_known_{value}",
                "function_body",
                f"if ({str(value % 2 == 0).lower()}) {{ return {value}; }} else {{ return {value + 1}; }}",
                return_type="Bits<8>",
                observe={"return": True},
            )
        )
        cases.append(
            _case(
                f"adv_conditional_return_{value}",
                "function_body",
                f"return {value} if true; return {value + 1};",
                return_type="Bits<8>",
                observe={"return": True},
            )
        )
    cases += [
        _case(
            "adv_if_non_boolean_bits",
            "function_body",
            "if (1) { return 1; }",
            return_type="Bits<8>",
        ),
        _case(
            "adv_if_else_type_mismatch",
            "function_body",
            "if (true) { return 1; } else { return false; }",
            return_type="Bits<8>",
        ),
        _case(
            "adv_unknown_conditional_returns",
            "function_body",
            "if (flag) { return 1; } else { return 2; }",
            return_type="Bits<8>",
            setup={"vars": [{"name": "flag", "type": "Boolean"}]},
            observe={"return": True},
        ),
        _case(
            "adv_missing_return_path",
            "function_body",
            "if (flag) { return 1; }",
            return_type="Bits<8>",
            setup={"vars": [{"name": "flag", "type": "Boolean"}]},
            observe={"return": True},
        ),
        _case(
            "adv_else_if_chain",
            "function_body",
            "if (false) { return 1; } else if (true) { return 2; } else { return 3; }",
            return_type="Bits<8>",
            observe={"return": True},
        ),
        _case(
            "adv_nested_if_shadow",
            "function_body",
            "Bits<8> x = 1; if (true) { Bits<8> y = 2; if (true) { Bits<8> x = y; } } return x;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
    ]

    # Constant loops, mutable bounds, update forms and loop-local scope.
    for limit in range(1, 13):
        cases.append(
            _case(
                f"adv_loop_sum_{limit}",
                "function_body",
                f"Bits<16> sum = 0; for (U32 i = 0; i < {limit}; i++) {{ sum = sum + 1; }} return sum;",
                return_type="Bits<16>",
                observe={"return": True},
            )
        )
    cases += [
        _case(
            "adv_loop_assignment_update",
            "for_loop",
            "for (U32 i = 0; i < 4; i = i + 1) { Bits<8> x = i; }",
            observe={"const_eval": True},
        ),
        _case(
            "adv_loop_decrement",
            "for_loop",
            "for (U32 i = 4; i > 0; i--) { Bits<8> x = i; }",
            observe={"const_eval": True},
        ),
        _case(
            "adv_loop_non_boolean_condition",
            "for_loop",
            "for (U32 i = 0; 4; i++) { Bits<8> x = i; }",
        ),
        _case(
            "adv_loop_mutable_update_upper",
            "for_loop",
            "for (U32 I = 0; I < 4; I = I + step) { I = I + 1; }",
            setup={"vars": [{"name": "step", "type": "Bits<4>"}]},
        ),
        _case(
            "adv_loop_mutable_body_upper",
            "for_loop",
            "for (U32 I = 0; I < 4; I++) { I = I + step; }",
            setup={"vars": [{"name": "step", "type": "Bits<4>"}]},
        ),
        _case(
            "adv_loop_mutable_update_lower",
            "for_loop",
            "for (U32 i = 0; i < 4; i = i + step) { i = i + 1; }",
            setup={"vars": [{"name": "step", "type": "Bits<4>"}]},
        ),
        _case(
            "adv_loop_scope_does_not_escape",
            "function_body",
            "for (U32 i = 0; i < 2; i++) { Bits<8> x = i; } return i;",
            return_type="Bits<8>",
        ),
        _case(
            "adv_nested_loops",
            "function_body",
            "Bits<8> n = 0; for (U32 i = 0; i < 2; i++) { for (U32 j = 0; j < 3; j++) { n = n + 1; } } return n;",
            return_type="Bits<8>",
            observe={"return": True},
        ),
    ]

    # Functions, calls, const arguments, multiple returns and destructuring.
    def isa(body: str) -> str:
        return f"%version: 1.0\n\n{body}\n"

    for argc in range(7):
        arguments = ", ".join(f"Bits<8> a{i}" for i in range(argc))
        args_clause = f"arguments {arguments}" if arguments else ""
        expression = " + ".join(f"a{i}" for i in range(argc)) if argc else "0"
        call_args = ", ".join(str(i) for i in range(argc))
        cases.append(
            _case(
                f"adv_function_arity_valid_{argc}",
                "isa",
                isa(
                    f"function f {{ returns Bits<8> {args_clause} description {{ f }} body {{ return {expression}; }} }}\n"
                    f"function caller {{ returns Bits<8> description {{ caller }} body {{ return f({call_args}); }} }}"
                ),
                observe={"functions": True},
            )
        )
    cases += [
        _case(
            "adv_function_missing_arg",
            "isa",
            isa(
                "function f { arguments Bits<8> a description { f } body { } }\nfunction c { description { c } body { f(); } }"
            ),
        ),
        _case(
            "adv_function_extra_arg",
            "isa",
            isa(
                "function f { description { f } body { } }\nfunction c { description { c } body { f(1); } }"
            ),
        ),
        _case(
            "adv_function_unknown_name",
            "isa",
            isa("function c { description { c } body { missing(); } }"),
        ),
        _case(
            "adv_builtin_definition",
            "isa",
            isa("builtin function ext { returns Bits<8> arguments Bits<8> a description { ext } }"),
            observe={"functions": True},
        ),
        _case(
            "adv_generated_definition",
            "isa",
            isa(
                "generated function ext { returns Bits<8> arguments Bits<8> a description { ext } }"
            ),
            observe={"functions": True},
        ),
        _case(
            "adv_const_arg_literal",
            "isa",
            isa(
                "function f { arguments Bits<8> Const description { f } body { } }\nfunction c { description { c } body { f(3); } }"
            ),
        ),
        _case(
            "adv_const_arg_const_var",
            "isa",
            isa(
                "function f { arguments Bits<8> Const description { f } body { } }\nfunction c { description { c } body { Bits<8> Value = 3; f(Value); } }"
            ),
        ),
        _case(
            "adv_const_arg_mutable_var",
            "isa",
            isa(
                "function f { arguments Bits<8> Const description { f } body { } }\nfunction c { description { c } body { Bits<8> value = 3; f(value); } }"
            ),
        ),
        _case(
            "adv_const_arg_mutable_expression",
            "isa",
            isa(
                "function f { arguments Bits<8> Const description { f } body { } }\nfunction c { description { c } body { Bits<8> value = 3; f(value + 1); } }"
            ),
        ),
        _case(
            "adv_multiple_return_direct",
            "isa",
            isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } body { return 1, 2; } }"
            ),
            observe={"functions": True},
        ),
        _case(
            "adv_multiple_return_destructure",
            "isa",
            isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } body { return 1, 2; } }\nfunction c { returns Bits<8> description { c } body { Bits<8> a, b; (a, b) = pair(); return a + b; } }"
            ),
        ),
        _case(
            "adv_multiple_return_dontcare",
            "isa",
            isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } body { return 1, 2; } }\nfunction c { description { c } body { Bits<8> a; (a, -) = pair(); } }"
            ),
        ),
        _case(
            "adv_multiple_return_arity_mismatch",
            "isa",
            isa(
                "function pair { returns Bits<8>, Bits<8> description { pair } body { return 1, 2; } }\nfunction c { description { c } body { Bits<8> a; (a, -, -) = pair(); } }"
            ),
        ),
        _case(
            "adv_return_too_many",
            "isa",
            isa("function f { returns Bits<8> description { f } body { return 1, 2; } }"),
        ),
        _case(
            "adv_return_too_few",
            "isa",
            isa("function f { returns Bits<8>, Bits<8> description { f } body { return 1; } }"),
        ),
        _case(
            "adv_template_width_function",
            "isa",
            isa(
                "function identity { returns Bits<N> arguments Bits<N> value "
                "description { identity } body { return value; } }\n"
                "function caller { returns Bits<4> description { caller } "
                "body { return identity(3); } }"
            ),
            setup={"vars": [{"name": "N", "type": "const Bits<8>", "value": 4}]},
        ),
    ]

    # Structs and bitfields, including successful and rejected field writes.
    cases += [
        _case(
            "adv_struct_write",
            "isa",
            isa(
                "struct Pair { Bits<8> left; Bits<8> right; }\nfunction f { returns Bits<8> description { f } body { Pair p; p.left = 3; p.right = 4; return p.left + p.right; } }"
            ),
        ),
        _case(
            "adv_struct_bad_field",
            "isa",
            isa(
                "struct Pair { Bits<8> left; }\nfunction f { description { f } body { Pair p; p.right = 3; } }"
            ),
        ),
        _case(
            "adv_struct_bad_field_type",
            "isa",
            isa(
                "struct Pair { Boolean flag; }\nfunction f { description { f } body { Pair p; p.flag = 1; } }"
            ),
        ),
        _case(
            "adv_bitfield_write",
            "isa",
            isa(
                "bitfield (16) Fields { HI 15-8 LO 7-0 }\nfunction f { returns Bits<16> description { f } body { Fields x; x.HI = 18; x.LO = 52; return $bits(x); } }"
            ),
        ),
        _case(
            "adv_bitfield_bad_field",
            "isa",
            isa(
                "bitfield (8) Fields { LO 7-0 }\nfunction f { description { f } body { Fields x; x.NOPE = 1; } }"
            ),
        ),
        _case(
            "adv_bitfield_const_write",
            "isa",
            isa(
                "bitfield (8) Fields { LO 7-0 }\nfunction f { description { f } body { Fields Value; Value.LO = 1; } }"
            ),
        ),
    ]
    for split in range(1, 13):
        cases.append(
            _case(
                f"adv_bitfield_width_split_{split}",
                "isa",
                isa(
                    f"bitfield (16) B{split} {{ A 15-{split} B {split - 1}-0 }}\n"
                    f"function f{split} {{ description {{ f }} body {{ B{split} x; x.A = 0; x.B = 0; }} }}"
                ),
            )
        )

    # General register files and X register operations.
    rf_setup = {
        "mxlen": 64,
        "register_files": [
            {"name": "X", "width": 64, "count": 32},
            {"name": "F", "width": 64, "count": 32},
        ],
        "vars": [
            {"name": "rs1", "type": "Bits<5>", "value": 3},
            {"name": "rd", "type": "Bits<5>", "value": 7},
            {"name": "value", "type": "Bits<64>"},
        ],
    }
    cases += [
        _case(
            "adv_x_read",
            "function_body",
            "XReg v = X[rs1]; return v;",
            return_type="Bits<64>",
            setup=rf_setup,
        ),
        _case("adv_x_write", "function_body", "X[rd] = value;", setup=rf_setup),
        _case("adv_x_range_write", "function_body", "X[rd][7:0] = 8'hff;", setup=rf_setup),
        _case(
            "adv_f_read",
            "function_body",
            "FReg v = F[rs1]; return v;",
            return_type="Bits<64>",
            setup=rf_setup,
        ),
        _case("adv_f_write", "function_body", "F[rd] = value;", setup=rf_setup),
        _case("adv_regfile_bad_index_type", "function_body", "X[true] = value;", setup=rf_setup),
        _case("adv_regfile_bad_value_type", "function_body", "X[rd] = true;", setup=rf_setup),
        _case(
            "adv_regfile_read_not_const",
            "expression",
            "X[0]",
            setup=rf_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
    ]

    # CSR reads, fields, software accessors and writes.
    csr_setup = {
        "mxlen": 64,
        "possible_xlens": [32, 64],
        "csrs": [
            {
                "name": "mockcsr",
                "address": 0x300,
                "length": 64,
                "fields": [
                    {"name": "RO", "width": 8, "value": 5, "type": "RO"},
                    {"name": "RW", "width": 8, "type": "RW"},
                ],
            }
        ],
    }
    cases += [
        _case(
            "adv_csr_read",
            "expression",
            "CSR[mockcsr]",
            setup=csr_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
        _case(
            "adv_csr_field_ro",
            "expression",
            "CSR[mockcsr].RO",
            setup=csr_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
        _case(
            "adv_csr_field_rw",
            "expression",
            "CSR[mockcsr].RW",
            setup=csr_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
        _case(
            "adv_csr_address",
            "expression",
            "CSR[mockcsr].address()",
            setup=csr_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
        _case(
            "adv_csr_sw_read",
            "expression",
            "CSR[mockcsr].sw_read()",
            setup=csr_setup,
            observe={"type": True, "const_eval": True, "value": True},
        ),
        _case("adv_csr_bad_function", "expression", "CSR[mockcsr].nope()", setup=csr_setup),
        _case("adv_csr_function_args", "expression", "CSR[mockcsr].address(1)", setup=csr_setup),
        _case("adv_csr_unknown_name", "expression", "CSR[missing].address()", setup=csr_setup),
        _case("adv_csr_field_write", "function_body", "CSR[mockcsr].RW = 3;", setup=csr_setup),
        _case(
            "adv_csr_sw_write", "function_body", "CSR[mockcsr].sw_write(64'd3);", setup=csr_setup
        ),
    ]

    # Reserved identifiers at each semantic declaration site.
    reserved = [
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
    for word in reserved:
        cases.append(
            _case(
                f"adv_reserved_variable_{word}",
                "isa",
                isa(f"function ok {{ description {{ ok }} body {{ Bits<8> {word}; }} }}"),
            )
        )
        cases.append(
            _case(
                f"adv_reserved_function_{word}",
                "isa",
                isa(f"function {word} {{ description {{ bad }} body {{ return; }} }}"),
            )
        )
    for typename in ["XReg", "Boolean", "String", "U64", "U32", "Bits"]:
        cases.append(
            _case(
                f"adv_reserved_function_type_{typename}",
                "isa",
                isa(f"function {typename} {{ description {{ bad }} body {{ return; }} }}"),
            )
        )
    cases += [
        _case(
            "adv_valid_keyword_substring",
            "isa",
            isa("function iffy { description { ok } body { Bits<8> returning = 1; } }"),
        ),
        _case(
            "adv_question_function_name",
            "isa",
            isa("function isValid? { returns Boolean description { ok } body { return true; } }"),
            observe={"functions": True},
        ),
        _case("adv_reserved_struct_member", "isa", isa("struct S { Bits<8> if; }")),
        _case(
            "adv_reserved_function_argument",
            "isa",
            isa("function f { arguments Bits<8> if description { f } body { } }"),
        ),
        _case("adv_reserved_global", "isa", isa("Bits<8> if;")),
        _case(
            "adv_reserved_loop_variable",
            "isa",
            isa(
                "function f { description { f } "
                "body { for (U32 if = 0; if < 2; if++) { return; } } }"
            ),
        ),
        _case("adv_reserved_enum_member", "isa", isa("enum E { CSR }")),
        _case("adv_reserved_bitfield_field", "isa", isa("bitfield (8) B { if 7-0 }")),
        _case("adv_include_statement", "isa", '%version: 1.0\ninclude "other.idl"\n'),
    ]

    return cases


def build_cases() -> list[dict[str, Any]]:
    cases = _yaml_cases() + _adversarial_cases()
    ids = [case["id"] for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate statement case ids: {duplicates}")
    return cases


def run_oracle(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mise = shutil.which("mise")
    if mise is None:
        raise RuntimeError("mise is required to run the Ruby IDL statement oracle")

    results: list[dict[str, Any]] = []
    for start in range(0, len(cases), BATCH_SIZE):
        batch = cases[start : start + BATCH_SIZE]
        payload = json.dumps({"cases": batch})
        proc = subprocess.run(
            [mise, "exec", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
            cwd=REPOSITORY_ROOT,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Ruby statement oracle failed at case {start}:\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        results.extend(json.loads(proc.stdout))
    return results


def regenerate(data_file: Path = DATA_FILE) -> None:
    cases = build_cases()
    expectations = run_oracle(cases)
    if len(expectations) != len(cases):
        raise RuntimeError(f"oracle returned {len(expectations)} results for {len(cases)} cases")

    ruby_crashes = [
        (case["id"], expect)
        for case, expect in zip(cases, expectations, strict=True)
        if expect.get("error") == "other"
    ]
    if ruby_crashes:
        details = "\n".join(
            f"{case_id}: {expect['message']} ({expect.get('backtrace')})"
            for case_id, expect in ruby_crashes
        )
        raise RuntimeError(
            "non-diagnostic Ruby exceptions must be investigated and removed from "
            f"the Ruby-must-match corpus:\n{details}"
        )

    for case, expect in zip(cases, expectations, strict=True):
        case["expect"] = expect

    document = {
        "schema_version": 1,
        "description": "Ruby-generated black-box expectations for IDL statement semantics",
        "counts": {
            "ruby_type_checking_yaml": 158,
            "ruby_control_flow_yaml": 18,
            "adversarial": len(cases) - 176,
            "total": len(cases),
        },
        "cases": cases,
    }
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(document, indent=2) + "\n")
    print(f"Regenerated {len(cases)} statement cases in {data_file}")


if __name__ == "__main__":
    sys.exit(regenerate() or 0)
