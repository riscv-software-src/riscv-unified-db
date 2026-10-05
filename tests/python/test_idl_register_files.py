# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import make_symtab, run_semantic_case, type_to_str

REGISTER_SETUP = {
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


def test_register_file_globals_are_registered():
    symtab = make_symtab(REGISTER_SETUP)
    assert type_to_str(symtab.get("F").type) == "global array of FReg"
    assert type_to_str(symtab.get("FReg")) == "FReg"
    assert type_to_str(symtab.get("XReg")) == "XReg"


def test_register_file_element_read_typechecks():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "FReg v = F[rs1]; return v;",
            "return_type": "Bits<64>",
            "setup": REGISTER_SETUP,
        }
    )
    assert result["ok"] is True


def test_register_file_element_write_typechecks():
    result = run_semantic_case(
        {"root": "function_body", "text": "F[rd] = value;", "setup": REGISTER_SETUP}
    )
    assert result["ok"] is True


def test_register_read_is_not_compile_time_known():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "F[0]",
            "setup": REGISTER_SETUP,
            "observe": {"const_eval": True, "value": True},
        }
    )
    assert result["const_eval"] is False
    assert result["value"]["known"] is False


def test_register_file_write_checks_element_type():
    result = run_semantic_case(
        {"root": "function_body", "text": "F[rd] = true;", "setup": REGISTER_SETUP}
    )
    assert result["error"] == "type"
