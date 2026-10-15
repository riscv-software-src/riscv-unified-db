# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Regenerate the frozen expectations in ``tests/python/data/idl/expressions.json``.

This script is the *only* place that talks to the Ruby oracle
(``tests/python/ruby_idl_expression_oracle.rb``) to produce test expectations. The corpus file
holds hand-curated ``{"id", "text", "params"}`` cases (seeded from
``tools/ruby-gems/idlc/test/idl/expressions.yaml``/``literals.yaml`` plus adversarial additions
by :func:`build_seed_cases`); this script fills in (or refreshes) the ``"expect"`` field for
every case by asking the Ruby reference implementation what it does with that text/params, and
writes the result back out.

Usage::

    cd <repo-root>
    mise exec -- bundle install               # once, to vendor the idlc gem's dependencies
    uv run python tests/python/regen_idl_expressions.py            # refresh from the yaml + adversarial seed
    uv run python tests/python/regen_idl_expressions.py --refresh-only  # keep existing cases, just re-run oracle

Never hand-edit the ``"expect"`` field of a case; edit ``build_seed_cases`` (or the corpus file's
``"id"``/``"text"``/``"params"``) and rerun this script instead. The pytest suite
(``tests/python/test_idl_expressions.py``) never calls Ruby: it only reads the frozen JSON this
script writes, except for the ``UDB_TEST_RUBY=1``-gated freshness check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_expression_oracle.rb")
DATA_FILE = Path(__file__).parent / "data" / "idl" / "expressions.json"
IDLC_TEST_DIR = REPOSITORY_ROOT / "tools/ruby-gems/idlc/test/idl"

# Batch size for a single Ruby invocation. Keeps process-startup overhead low without building
# one enormous JSON blob (the machine running this script may be memory constrained).
BATCH_SIZE = 40


def run_oracle(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run a batch of ``{"id", "text", "params"}`` cases through the Ruby oracle.

    Returns one result dict per case, in the same order, as produced by
    ``tests/python/ruby_idl_expression_oracle.rb`` (see that file's header for the schema).
    """
    mise = shutil.which("mise")
    if mise is None:
        raise RuntimeError("mise is required to run the Ruby IDL expression oracle; see bin/setup")

    results: list[dict[str, Any]] = []
    for start in range(0, len(cases), BATCH_SIZE):
        batch = cases[start : start + BATCH_SIZE]
        payload = json.dumps(
            {
                "cases": [
                    {
                        "id": c["id"],
                        "text": c["text"],
                        "params": c["params"],
                        "enums": c.get("enums", []),
                    }
                    for c in batch
                ]
            }
        )
        proc = subprocess.run(
            [mise, "exec", "--no-deps", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
            cwd=REPOSITORY_ROOT,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ruby oracle failed:\n{proc.stderr}")
        results.extend(json.loads(proc.stdout))
    return results


def _yaml_cases(yaml_path: Path, prefix: str) -> list[dict[str, Any]]:
    """Build ``{"id", "text", "params"}`` cases from an idlc ``test/idl/*.yaml`` file.

    Mirrors how ``tools/ruby-gems/idlc/test/test_expressions.rb`` consumes this format: each
    entry's ``"e"`` field is one case, and (when present) its ``"="`` field is a second case (the
    comparison expression). ``"p"`` is bound the same way as ``ExpressionTestFactory``: integers
    become ``Bits<bit_length>`` (width 1 for zero), strings become ``String``, booleans become
    ``Boolean``.
    """
    doc = YAML(typ="safe").load(yaml_path.read_text())
    cases: list[dict[str, Any]] = []
    for i, entry in enumerate(doc["tests"]):
        params = entry.get("p", {})
        cases.append({"id": f"{prefix}:{i}", "text": entry["e"], "params": params})
        if "=" in entry:
            cases.append({"id": f"{prefix}:{i}:=", "text": entry["="], "params": params})
    return cases


def _adversarial_cases() -> list[dict[str, Any]]:
    """Hand-written cases exercising width/sign edge cases not in the idlc yaml corpus.

    Each covers a specific rule from ``doc/stage4-idl.md``'s slice-14 scope: overflow/truncation,
    wide shifts, signed comparison, unknown ``value_known=false`` results, x-bits, and every
    builtin/operator at least once.
    """
    cases: list[dict[str, Any]] = [
        # --- integer literal edge cases ---
        {"id": "adv:lit_zero_width_verilog", "text": "0'd0", "params": {}},
        {"id": "adv:lit_max_hex", "text": "0xffffffffffffffff", "params": {}},
        {"id": "adv:lit_signed_cpp", "text": "0xffs", "params": {}},
        {"id": "adv:lit_signed_decimal", "text": "63s", "params": {}},
        {"id": "adv:lit_signed_decimal_neg", "text": "-1s", "params": {}},
        {"id": "adv:lit_unknown_bits_b", "text": "4'b10x1", "params": {}},
        {"id": "adv:lit_unknown_bits_h", "text": "8'hxf", "params": {}},
        {"id": "adv:lit_unknown_bits_o", "text": "6'o1x", "params": {}},
        {"id": "adv:lit_unknown_bits_upper_x", "text": "4'bX011", "params": {}},
        {"id": "adv:lit_mxlen_no_symtab_mxlen", "text": "MXLEN'5", "params": {}},
        {"id": "adv:lit_underscore_hex", "text": "0xFF_FF", "params": {}},
        {"id": "adv:lit_octal_cpp", "text": "017", "params": {}},
        {"id": "adv:lit_binary_cpp", "text": "0b1010", "params": {}},
        {"id": "adv:lit_verilog_signed_overflow", "text": "8'sd200", "params": {}},
        # --- unary ---
        {"id": "adv:unary_neg_bits", "text": "-(4'd5)", "params": {}},
        {"id": "adv:unary_not_bool", "text": "!true", "params": {}},
        {"id": "adv:unary_bitwise_not", "text": "~(4'hf)", "params": {}},
        {"id": "adv:unary_neg_signed", "text": "-(4'shf)", "params": {}},
        # --- binary arithmetic and width propagation ---
        {"id": "adv:add_widening", "text": "8'hff + 8'h01", "params": {}},
        {"id": "adv:add_widen_op", "text": "8'hff `+ 8'h01", "params": {}},
        {"id": "adv:sub_widen_op", "text": "4'h0 `- 4'h1", "params": {}},
        {"id": "adv:mul_widen_op", "text": "8'hff `* 8'h02", "params": {}},
        {"id": "adv:shl_widen_op", "text": "4'hf `<< 2", "params": {}},
        {"id": "adv:mul_overflow_trunc", "text": "8'hff * 8'h02", "params": {}},
        {"id": "adv:shift_left_large", "text": "1 << 100", "params": {}},
        {"id": "adv:shift_right_large", "text": "0xff >> 100", "params": {}},
        {"id": "adv:shift_by_large_unknown", "text": "a << b", "params": {"a": 4, "b": 100}},
        {"id": "adv:div_by_zero_known", "text": "4 / 0", "params": {}},
        {"id": "adv:mod_by_zero_known", "text": "4 % 0", "params": {}},
        {"id": "adv:div_unknown", "text": "a / b", "params": {"a": 10, "b": 3}},
        # --- comparisons, signed vs unsigned ---
        {"id": "adv:signed_lt_negative", "text": "(-1s) < 1", "params": {}},
        {"id": "adv:unsigned_lt_wraps", "text": "0xffffffffffffffffs < 0", "params": {}},
        {"id": "adv:eq_diff_width", "text": "8'hff == 0xff", "params": {}},
        {"id": "adv:neq_bool", "text": "true != false", "params": {}},
        {"id": "adv:ge_le", "text": "(4 >= 4) && (4 <= 4)", "params": {}},
        # --- logical / bitwise ---
        {"id": "adv:logical_and_shortcircuit_false", "text": "false && (1 / 0 == 0)", "params": {}},
        {"id": "adv:logical_or_shortcircuit_true", "text": "true || (1 / 0 == 0)", "params": {}},
        {"id": "adv:bitwise_and", "text": "0xf0 & 0x0f", "params": {}},
        {"id": "adv:bitwise_or", "text": "0xf0 | 0x0f", "params": {}},
        {"id": "adv:bitwise_xor", "text": "0xff ^ 0x0f", "params": {}},
        # --- ternary ---
        {"id": "adv:ternary_known_cond", "text": "true ? 1 : 2", "params": {}},
        {"id": "adv:ternary_unknown_cond", "text": "a ? 1 : 2", "params": {"a": True}},
        {"id": "adv:ternary_width_promote", "text": "true ? 8'h1 : 16'h1", "params": {}},
        # --- concatenation / replication ---
        {"id": "adv:concat_two", "text": "{4'hf, 4'h0}", "params": {}},
        {"id": "adv:concat_three", "text": "{1'b1, 2'b01, 1'b0}", "params": {}},
        {"id": "adv:replication_basic", "text": "{4{1'b1}}", "params": {}},
        {"id": "adv:replication_zero", "text": "{0{1'b1}}", "params": {}},
        # --- array literal ---
        {"id": "adv:array_literal_basic", "text": "[1'd1, 1'd0, 1'd1]", "params": {}},
        {"id": "adv:array_literal_single", "text": "[42]", "params": {}},
        {"id": "adv:array_literal_mismatch", "text": "[1, 2, 3]", "params": {}},
        # --- element / range access ---
        {"id": "adv:element_access_lsb", "text": "(8'hff)[0]", "params": {}},
        {"id": "adv:element_access_msb", "text": "(8'hff)[7]", "params": {}},
        {"id": "adv:element_access_oob", "text": "(8'hff)[8]", "params": {}},
        {"id": "adv:range_access_basic", "text": "(8'hff)[7:4]", "params": {}},
        {"id": "adv:range_access_single", "text": "(8'hff)[3:3]", "params": {}},
        {"id": "adv:range_access_reversed", "text": "(8'hff)[3:7]", "params": {}},
        {"id": "adv:array_element_access", "text": "([1'd1, 1'd0, 1'd1])[1]", "params": {}},
        {"id": "adv:array_element_oob", "text": "([1'd1, 1'd0, 1'd1])[5]", "params": {}},
        # --- casts and width builtins ---
        {"id": "adv:bits_cast_bool", "text": "$bits(true)", "params": {}},
        {"id": "adv:bits_cast_bool_false", "text": "$bits(false)", "params": {}},
        {"id": "adv:signed_cast", "text": "$signed(8'hff)", "params": {}},
        {"id": "adv:signed_cast_zero", "text": "$signed(8'h00)", "params": {}},
        {"id": "adv:width_reveal", "text": "$width(8'hff)", "params": {}},
        {"id": "adv:width_reveal_param", "text": "$width(a)", "params": {"a": 5}},
        # --- string literal ---
        {"id": "adv:string_basic", "text": '"hello"', "params": {}},
        {"id": "adv:string_empty", "text": '""', "params": {}},
        # --- paren nesting ---
        {"id": "adv:paren_nested", "text": "((((1))))", "params": {}},
        # --- identifiers / params ---
        {"id": "adv:id_bool_param", "text": "flag", "params": {"flag": True}},
        {"id": "adv:id_string_param", "text": "s", "params": {"s": "abc"}},
        {"id": "adv:id_bits_param_add", "text": "n + 1", "params": {"n": 5}},
        {"id": "adv:id_not_found", "text": "totally_unknown_symbol_xyz", "params": {}},
        # --- error cases (type errors) ---
        {"id": "adv:err_bool_plus_int", "text": "true + 1", "params": {}},
        {"id": "adv:err_string_minus_int", "text": '"x" - 1', "params": {}},
        {"id": "adv:err_bad_builtin", "text": "$notreal(1)", "params": {}},
        {"id": "adv:err_range_backwards_bad", "text": "(4'hf)[10:0]", "params": {}},
        {"id": "adv:err_concat_bool", "text": "{true, 1'b0}", "params": {}},
        {"id": "adv:err_ternary_mismatched", "text": '(true ? 1 : "x")', "params": {}},
        # --- concatenation const-qualifier (Ruby bug entry 26, see doc/python-migration-bugfixes.md) ---
        {"id": "adv:concat_const_var", "text": "{a, 1'b1}", "params": {"a": 5}},
        {"id": "adv:concat_all_literal_const", "text": "{1'b1, 1'b0}", "params": {}},
        # --- enums ---
        {
            "id": "adv:enum_ref",
            "text": "PrivilegeMode::M",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_ref_bad_member",
            "text": "PrivilegeMode::NotAMode",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_size",
            "text": "$enum_size(PrivilegeMode)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_element_size",
            "text": "$enum_element_size(PrivilegeMode)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_to_a",
            "text": "$enum_to_a(PrivilegeMode)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_cast_valid",
            "text": "$enum(PrivilegeMode, 3'd3)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_cast_bad_value",
            "text": "$enum(PrivilegeMode, 3'd2)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:enum_cast_not_bits",
            "text": "$enum(PrivilegeMode, true)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:array_includes_enum",
            "text": "$array_includes?($enum_to_a(PrivilegeMode), 1)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:array_includes_missing",
            "text": "$array_includes?($enum_to_a(PrivilegeMode), 7)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        {
            "id": "adv:bits_cast_enum_ref",
            "text": "$bits(PrivilegeMode::M)",
            "params": {},
            "enums": [_PRIVILEGE_MODE_ENUM],
        },
        # --- bitfield / struct field access ---
        {
            "id": "adv:bitfield_field_lo",
            "text": "a.lo",
            "params": {"a": _bitfield_param("Foo", 8, {"lo": [0, 3], "hi": [4, 7]}, 0b10110101)},
        },
        {
            "id": "adv:bitfield_field_hi",
            "text": "a.hi",
            "params": {"a": _bitfield_param("Foo", 8, {"lo": [0, 3], "hi": [4, 7]}, 0b10110101)},
        },
        {
            "id": "adv:bitfield_field_bad",
            "text": "a.nope",
            "params": {"a": _bitfield_param("Foo", 8, {"lo": [0, 3], "hi": [4, 7]}, 0b10110101)},
        },
        {
            "id": "adv:bits_cast_bitfield",
            "text": "$bits(a)",
            "params": {"a": _bitfield_param("Foo", 8, {"lo": [0, 3], "hi": [4, 7]}, 0b10110101)},
        },
        {
            "id": "adv:struct_field_ok",
            "text": "s.x",
            "params": {"s": _struct_param("Point", {"x": 8, "y": 8}, {"x": 3, "y": 4})},
        },
        {
            "id": "adv:struct_field_bad",
            "text": "s.z",
            "params": {"s": _struct_param("Point", {"x": 8, "y": 8}, {"x": 3, "y": 4})},
        },
        # --- builtin variables ---
        {"id": "adv:builtin_pc", "text": "$pc", "params": {}},
        {"id": "adv:builtin_bad", "text": "$bogus_builtin_var", "params": {}},
    ]
    return cases


_PRIVILEGE_MODE_ENUM = {"name": "PrivilegeMode", "elements": {"M": 3, "S": 1, "U": 0}}


def _bitfield_param(
    name: str, width: int, fields: dict[str, list[int]], value: int
) -> dict[str, Any]:
    """A ``{"bitfield": {...}, "value": int}`` param spec understood by the oracle's ``bind``."""
    return {"bitfield": {"name": name, "width": width, "fields": fields}, "value": value}


def _struct_param(name: str, members: dict[str, int], value: dict[str, int]) -> dict[str, Any]:
    """A ``{"struct": {...}, "value": {...}}`` param spec understood by the oracle's ``bind``."""
    return {"struct": {"name": name, "members": members}, "value": value}


def build_seed_cases() -> list[dict[str, Any]]:
    """The full corpus of ``{"id", "text", "params"}`` cases, before ``"expect"`` is filled in."""
    cases: list[dict[str, Any]] = []
    cases.extend(_yaml_cases(IDLC_TEST_DIR / "expressions.yaml", "expressions"))
    cases.extend(_yaml_cases(IDLC_TEST_DIR / "literals.yaml", "literals"))
    cases.append({"id": "bad:1", "text": "true + 1", "params": {}})
    cases.append({"id": "bad:2", "text": "$bogus(1)", "params": {}})
    cases.append({"id": "u:1", "text": "X + 1", "params": {}})
    cases.extend(_adversarial_cases())
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Keep the existing corpus file's cases (ids/text/params); only re-run the oracle.",
    )
    args = parser.parse_args()

    if args.refresh_only:
        doc = json.loads(DATA_FILE.read_text())
        cases = [
            {
                "id": c["id"],
                "text": c["text"],
                "params": c["params"],
                "enums": c.get("enums", []),
            }
            for c in doc["cases"]
        ]
    else:
        cases = build_seed_cases()

    ids = [c["id"] for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids: {sorted(duplicates)}")

    expectations = run_oracle(cases)
    out_cases = [
        {
            "id": c["id"],
            "text": c["text"],
            "params": c["params"],
            **({"enums": c["enums"]} if c.get("enums") else {}),
            "expect": e,
        }
        for c, e in zip(cases, expectations, strict=True)
    ]
    DATA_FILE.write_text(json.dumps({"cases": out_cases}, indent=2) + "\n")
    print(f"wrote {len(out_cases)} cases to {DATA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
