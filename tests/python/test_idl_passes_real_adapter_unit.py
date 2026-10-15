# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Canonical real observations without changing standalone pass results."""

import test_idl_passes_real as real_contract
from idl_passes_helpers import _instruction_xlens, _observations, _register_records

from udb.idl.parser import parse
from udb.idl.passes import RegisterRef
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind

configured_architecture = real_contract.configured_architecture


def test_actual_instruction_xlen_entries_match_all_frozen_configuration_shapes(
    configured_architecture,
):
    config, architecture = configured_architecture
    expected = {item["id"]: item for item in real_contract.DOCUMENT["real"][config]}
    for sample in real_contract.SAMPLES:
        if sample["kind"] == "instruction":
            record = architecture.database.instruction(sample["name"])
            assert _instruction_xlens(architecture, record) == tuple(
                item["value"]["xlen"] for item in expected[sample["id"]]["value"]
            )


def test_decode_getters_are_an_adapter_only_canonicalization():
    symtab = SymbolTable()
    dtype = Type(TypeKind.BITS, width=5).make_const()
    symtab.add("xs1", Var("xs1", dtype, decode_var=True))
    symtab.add("ordinary", Var("ordinary", dtype))
    refs = (RegisterRef("X", "xs1"), RegisterRef("X", "ordinary"), RegisterRef("X", 1))
    assert _register_records(refs, symtab, decode_getters=True) == [
        {"file": "X", "index": 1},
        {"file": "X", "index": "ordinary"},
        {"file": "X", "index": "xs1()"},
    ]
    assert _register_records(refs, symtab) == [
        {"file": "X", "index": 1},
        {"file": "X", "index": "ordinary"},
        {"file": "X", "index": "xs1"},
    ]
    assert refs[0].index == "xs1"


def test_shared_observations_preserve_corrected_return_paths_and_caller_context():
    symtab = SymbolTable()
    symtab.add("unknown", Var("unknown", Type(TypeKind.BOOLEAN)))
    node = parse("if (unknown) { return 1; } else { return 2; }", "function_body")
    original = node.to_h()
    result = _observations(
        node,
        symtab,
        {"passes": ("return_values", "prune", "reachable_exceptions")},
        decode_getters=True,
    )
    assert result["return_values"] == {
        "ok": True,
        "value": [
            {"expression": "1", "conditions": ["unknown"]},
            {"expression": "2", "conditions": ["!unknown"]},
        ],
    }
    assert result["reachable_exceptions"] == {"ok": True, "value": {"mask": 0, "codes": []}}
    assert node.to_h() == original
    assert symtab.get("unknown").value is None
    assert symtab.levels == 1
