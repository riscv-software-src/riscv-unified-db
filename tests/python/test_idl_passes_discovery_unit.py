# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from dataclasses import dataclass

import pytest

from udb.idl.errors import IdlValueUnknown
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.passes import (
    RegisterRef,
    destination_registers,
    referenced_csrs,
    source_registers,
)
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import Type, TypeKind


@dataclass
class _RegisterFile:
    name: str
    register_length: str
    registers: tuple[object, ...]


def _register_symtab() -> SymbolTable:
    env = IdlEnvironment(
        mxlen=64,
        register_files=(
            _RegisterFile("X", "return MXLEN;", tuple(range(32))),
            _RegisterFile("F", "return 64;", tuple(range(32))),
        ),
    )
    symtab = SymbolTable(env)
    bits5 = Type(TypeKind.BITS, width=5)
    bits64 = Type(TypeKind.BITS, width=64)
    symtab.add("rs1", Var("rs1", bits5, 3))
    symtab.add("rd", Var("rd", bits5, 7))
    symtab.add("unknown_idx", Var("unknown_idx", bits5))
    symtab.add(
        "CONST_IDX",
        Var("CONST_IDX", bits5.make_const()),
    )
    symtab.add("v", Var("v", bits64))
    return symtab


def test_referenced_csrs_walks_reads_fields_and_software_writes() -> None:
    body = parse_function_body("Bits<32> a = $bits(CSR[testcsr]); CSR[mockcsr].sw_write(a);")
    assert referenced_csrs(body) == frozenset({"mockcsr", "testcsr"})


def test_register_discovery_known_and_nested_destinations() -> None:
    symtab = _register_symtab()
    assert source_registers(parse_expression("F[rs1]"), symtab) == frozenset({RegisterRef("F", 3)})
    assert destination_registers(parse_function_body("F[rd][3] = 1;"), symtab) == frozenset(
        {RegisterRef("F", 7)}
    )
    assert destination_registers(parse_function_body("F[rd][7:0] = 8'hff;"), symtab) == frozenset(
        {RegisterRef("F", 7)}
    )


def test_register_discovery_uses_standalone_idl_for_symbolic_const_index() -> None:
    symtab = _register_symtab()
    assert source_registers(parse_expression("F[CONST_IDX]"), symtab) == frozenset(
        {RegisterRef("F", "CONST_IDX")}
    )


def test_register_discovery_rejects_runtime_only_index() -> None:
    symtab = _register_symtab()
    with pytest.raises(IdlValueUnknown):
        source_registers(parse_expression("F[unknown_idx]"), symtab)
    with pytest.raises(IdlValueUnknown):
        destination_registers(
            parse_function_body("F[unknown_idx] = v;"),
            symtab,
        )


def test_local_array_is_not_a_register_file() -> None:
    symtab = _register_symtab()
    local_array = Type(
        TypeKind.ARRAY,
        sub_type=Type(TypeKind.BITS, width=64),
        width=4,
    )
    symtab.add("values", Var("values", local_array))
    assert source_registers(parse_expression("values[1]"), symtab) == frozenset()
