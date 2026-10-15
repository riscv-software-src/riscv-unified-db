# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from idl_semantics_helpers import run_semantic_case

CSR_SETUP = {
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


def test_csr_address_is_constant():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "CSR[mockcsr].address()",
            "setup": CSR_SETUP,
            "observe": {"type": True, "const_eval": True, "value": True},
        }
    )
    assert result["const_eval"] is True
    assert result["value"] == {"known": True, "value": str(0x300)}


def test_read_only_csr_field_value_is_known():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "CSR[mockcsr].RO",
            "setup": CSR_SETUP,
            "observe": {"type": True, "value": True},
        }
    )
    assert result["type"]["text"] == "Bits<8>"
    assert result["value"] == {"known": True, "value": "5"}


def test_read_write_csr_field_value_is_unknown():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "CSR[mockcsr].RW",
            "setup": CSR_SETUP,
            "observe": {"value": True},
        }
    )
    assert result["value"]["known"] is False


def test_csr_field_write_typechecks_but_is_not_executable():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "CSR[mockcsr].RW = 3;",
            "setup": CSR_SETUP,
        }
    )
    assert result["ok"] is True


def test_csr_software_write_requires_xreg_width():
    good = run_semantic_case(
        {
            "root": "function_body",
            "text": "CSR[mockcsr].sw_write(64'd3);",
            "setup": CSR_SETUP,
        }
    )
    assert good["ok"] is True

    bad = run_semantic_case(
        {
            "root": "function_body",
            "text": "CSR[mockcsr].sw_write(8'd3);",
            "setup": CSR_SETUP,
        }
    )
    assert bad["error"] == "type"


def test_unknown_csr_name_is_rejected():
    result = run_semantic_case(
        {
            "root": "expression",
            "text": "CSR[missing].address()",
            "setup": CSR_SETUP,
        }
    )
    assert result["error"] == "type"
