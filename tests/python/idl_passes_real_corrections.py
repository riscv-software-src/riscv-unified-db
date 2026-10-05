# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exact real-source expectations for confirmed Ruby defects and canonical layout."""

from copy import deepcopy
from typing import Any

MTVEC_PRINTER_CASES = frozenset(
    {
        ("_", "csr_mtvec_mode_sw_write_rv32"),
        ("_", "csr_mtvec_mode_sw_write_rv64"),
        ("rv32", "csr_mtvec_mode_sw_write_rv32"),
        ("rv64", "csr_mtvec_mode_sw_write_rv32"),
        ("rv64", "csr_mtvec_mode_sw_write_rv64"),
        ("qc_iu", "csr_mtvec_mode_sw_write_rv32"),
    }
)
STANDARD_EXCEPTION_XLENS = {"_": (32, 64), "rv32": (32,), "rv64": (32, 64)}
STALE_BINDING_EXCEPTION_CASES = frozenset(
    (config, sample)
    for config in STANDARD_EXCEPTION_XLENS
    for sample in ("inst_lw", "function_read_memory")
)
QC_TAIL = (
    "physical_address = virtual_address;"
    "access_check(physical_address,LEN,virtual_address,MemoryOperation::Read,"
    "ExceptionCode::LoadAccessFault,PrivilegeMode::M);"
    "raise(ExceptionCode::LoadAddressMisaligned,PrivilegeMode::M,virtual_address);"
)
QC_CANONICAL_TAIL = QC_TAIL.replace(";access_check", ";\naccess_check").replace(
    ";raise", ";\nraise"
)


def corrected_real_expectation(config: str, sample: str, frozen: Any) -> Any:
    expected = deepcopy(frozen)
    key = (config, sample)
    if key in MTVEC_PRINTER_CASES:
        text = expected["prune"]["value"]["to_idl"]
        array = "[1'0,1'1]" if config == "qc_iu" else "MTVEC_MODES"
        invalid = f"$array_size({array}, csr_value.MODE)"
        assert text.count(invalid) == 1, key
        expected["prune"]["value"]["to_idl"] = text.replace(
            invalid, f"$array_includes?({array}, csr_value.MODE)"
        )
    elif key == ("qc_iu", "function_read_memory"):
        text = expected["prune"]["value"]["to_idl"]
        assert text.endswith(QC_TAIL), key
        expected["prune"]["value"]["to_idl"] = text[: -len(QC_TAIL)] + QC_CANONICAL_TAIL
    elif key in STALE_BINDING_EXCEPTION_CASES:
        if sample == "inst_lw":
            assert (
                tuple(entry["value"]["xlen"] for entry in expected)
                == (STANDARD_EXCEPTION_XLENS[config])
            ), key
            assert all(entry["ok"] is True for entry in expected), key
            observations = [entry["value"]["passes"] for entry in expected]
        else:
            observations = [expected]
        for passes in observations:
            assert passes["reachable_exceptions"] == {
                "ok": True,
                "value": {"mask": 8240, "codes": [4, 5, 13]},
            }, key
            passes["reachable_exceptions"] = {
                "ok": True,
                "value": {"mask": 8368, "codes": [4, 5, 7, 13]},
            }
    return expected
