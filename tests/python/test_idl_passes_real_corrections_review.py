# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Corrections are exact, immutable, case-specific and preserve all other observations."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from idl_passes_real_corrections import (
    MTVEC_PRINTER_CASES,
    QC_CANONICAL_TAIL,
    QC_TAIL,
    STALE_BINDING_EXCEPTION_CASES,
    STANDARD_EXCEPTION_XLENS,
    corrected_real_expectation,
)

from udb.idl.ast import ArrayIncludes
from udb.idl.errors import IdlTypeError
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.symbols import SymbolTable

DATA_FILE = Path(__file__).parent / "data/idl/passes.json"
DOCUMENT = json.loads(DATA_FILE.read_text())


@pytest.mark.parametrize("config,sample", sorted(MTVEC_PRINTER_CASES))
def test_confirmed_array_printer_bug_has_one_exact_corrected_observation(config, sample):
    frozen = next(item for item in DOCUMENT["real"][config] if item["id"] == sample)["value"]
    before = deepcopy(frozen)
    expected = corrected_real_expectation(config, sample, frozen)
    assert frozen == before
    old = frozen["prune"]["value"]["to_idl"]
    new = expected["prune"]["value"]["to_idl"]
    assert new.replace("$array_includes?(", "$array_size(") == old
    array = "[1'0,1'1]" if config == "qc_iu" else "MTVEC_MODES"
    invalid = parse_expression(f"$array_size({array}, csr_value.MODE)")
    with pytest.raises(IdlTypeError, match="expects 1 argument"):
        invalid.type_check(SymbolTable())
    assert isinstance(parse_expression(f"$array_includes?({array}, csr_value.MODE)"), ArrayIncludes)
    parse_function_body(new)
    expected["prune"]["value"]["to_idl"] = old
    assert expected == frozen


def test_qc_canonical_statement_separators_are_exact_not_general_whitespace_normalization():
    frozen = next(
        item for item in DOCUMENT["real"]["qc_iu"] if item["id"] == "function_read_memory"
    )["value"]
    before = deepcopy(frozen)
    expected = corrected_real_expectation("qc_iu", "function_read_memory", frozen)
    old = frozen["prune"]["value"]["to_idl"]
    new = expected["prune"]["value"]["to_idl"]
    assert frozen == before
    assert new == old[: -len(QC_TAIL)] + QC_CANONICAL_TAIL
    assert new.replace(";\naccess_check", ";access_check").replace(";\nraise", ";raise") == old
    assert [statement.kind for statement in parse_function_body(new).children] == [
        statement.kind for statement in parse_function_body(old).children
    ]
    expected["prune"]["value"]["to_idl"] = old
    assert expected == frozen


def test_all_other_frozen_real_fields_and_cases_are_unchanged():
    corrected = (
        MTVEC_PRINTER_CASES | STALE_BINDING_EXCEPTION_CASES | {("qc_iu", "function_read_memory")}
    )
    for config, entries in DOCUMENT["real"].items():
        for item in entries:
            if item["ok"] and (config, item["id"]) not in corrected:
                assert (
                    corrected_real_expectation(config, item["id"], item["value"]) == item["value"]
                )


@pytest.mark.parametrize("config,sample", sorted(STALE_BINDING_EXCEPTION_CASES))
def test_confirmed_stale_binding_omission_changes_only_exact_exception_observation(config, sample):
    frozen = next(item for item in DOCUMENT["real"][config] if item["id"] == sample)["value"]
    before = deepcopy(frozen)
    expected = corrected_real_expectation(config, sample, frozen)
    observations = (
        [entry["value"]["passes"] for entry in expected] if sample == "inst_lw" else [expected]
    )
    assert frozen == before
    for passes in observations:
        assert passes["reachable_exceptions"] == {
            "ok": True,
            "value": {"mask": 8368, "codes": [4, 5, 7, 13]},
        }
        passes["reachable_exceptions"] = {
            "ok": True,
            "value": {"mask": 8240, "codes": [4, 5, 13]},
        }
    assert expected == frozen


@pytest.mark.parametrize("config,sample", sorted(STALE_BINDING_EXCEPTION_CASES))
@pytest.mark.parametrize("field,value", [("mask", 8368), ("codes", [4, 5, 7, 13])])
def test_exception_correction_rejects_any_changed_frozen_observation(config, sample, field, value):
    original = next(item for item in DOCUMENT["real"][config] if item["id"] == sample)["value"]
    for index in range(len(original) if sample == "inst_lw" else 1):
        frozen = deepcopy(original)
        passes = frozen[index]["value"]["passes"] if sample == "inst_lw" else frozen
        passes["reachable_exceptions"]["value"][field] = value
        with pytest.raises(AssertionError):
            corrected_real_expectation(config, sample, frozen)


@pytest.mark.parametrize("config", sorted(STANDARD_EXCEPTION_XLENS))
@pytest.mark.parametrize("change", ["additional-context", "missing-context", "different-xlen"])
def test_instruction_exception_correction_rejects_changed_context_shape(config, change):
    frozen = deepcopy(
        next(item for item in DOCUMENT["real"][config] if item["id"] == "inst_lw")["value"]
    )
    if change == "additional-context":
        frozen.append(deepcopy(frozen[0]))
    elif change == "missing-context":
        frozen.pop()
    else:
        frozen[0]["value"]["xlen"] = 128
    with pytest.raises(AssertionError):
        corrected_real_expectation(config, "inst_lw", frozen)
