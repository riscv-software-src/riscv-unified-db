# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Precision and ownership complements to the parent's semantic review oracles."""

import pytest
from test_idl_passes_discovery_unit import _register_symtab

from udb.idl import parse
from udb.idl.passes import RegisterRef, destination_registers, prune, source_registers
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)


def _runtime(**values):
    table = SymbolTable()
    for name, (dtype, value) in values.items():
        table.add(name, Var(name, dtype, value))
    table.push()
    table.add("__expected_return_type", BITS8)
    return table.deep_clone()


def test_loop_stable_index_keeps_unwritten_element_precision_and_caller_array():
    dtype = Type(TypeKind.ARRAY, width=3, sub_type=BITS8)
    table = _runtime(a=(dtype, [1, 2, 3]))
    node = parse(
        "Bits<8> j=0; Bits<8> x=0; for(Bits<8> i=0;i<3;i++){a[j]=9; x=a[1];} return x;",
        "function_body",
    )
    result = prune(node, table)
    assert "x = 8'2;" in result.to_idl()
    assert node.return_value(_runtime(a=(dtype, [1, 2, 3]))) == 2
    assert result.return_value(_runtime(a=(dtype, [1, 2, 3]))) == 2
    assert table.get("a").value == [1, 2, 3]


def test_loop_changing_index_before_write_preserves_runtime_value():
    dtype = Type(TypeKind.ARRAY, width=4, sub_type=BITS8)
    node = parse(
        "Bits<8> j=0; Bits<8> x=0; for(Bits<8> i=0;i<3;i++){j=j+1; a[j]=9; x=a[1];} return x;",
        "function_body",
    )
    result = prune(node, _runtime(a=(dtype, [1, 2, 3, 4])))
    assert node.return_value(_runtime(a=(dtype, [1, 2, 3, 4]))) == 9
    assert result.return_value(_runtime(a=(dtype, [1, 2, 3, 4]))) == 9


@pytest.mark.parametrize("condition", ["true", "false"])
def test_selected_declaring_branches_keep_scope_and_dead_statement_elimination(condition):
    node = parse(
        f"if({condition}){{Bits<8> t=1; return t;}}else{{Bits<8> t=2; return t;}} return 99;",
        "function_body",
    )
    result = prune(node, _runtime())
    assert "99" not in result.to_idl()
    reparsed = parse(result.to_idl(), "function_body")
    reparsed.type_check(_runtime())
    assert reparsed.return_value(_runtime()) == (1 if condition == "true" else 2)


@pytest.mark.parametrize("discover", [source_registers, destination_registers])
def test_local_register_values_follow_assignments_without_caller_or_ast_mutation(discover):
    table = _register_symtab()
    node = parse("Bits<5> r=rs1; X[r]=X[r]; r=5; X[r]=X[r];", "function_body")
    original = node.to_h()
    assert discover(node, table) == frozenset({RegisterRef("X", 3), RegisterRef("X", 5)})
    assert table.get("r") is None
    assert table.get("rs1").value == 3
    assert node.to_h() == original


@pytest.mark.parametrize("discover", [source_registers, destination_registers])
def test_loop_local_index_and_shadowing_remain_precise(discover):
    table = _register_symtab()
    node = parse(
        "Bits<5> r=7; for(Bits<5> i=0;i<4;i++){Bits<5> r=3; X[r]=X[r];} X[r]=X[r];",
        "function_body",
    )
    assert discover(node, table) == frozenset({RegisterRef("X", 3), RegisterRef("X", 7)})
    assert table.get("r") is None


def test_bitwise_same_width_identities_still_specialize():
    table = _runtime(x=(BITS8, None))
    for text in ("x & 8'hff", "x | 8'h00"):
        result = prune(parse(text, "expression"), table)
        assert result.to_idl() == "x"
        assert result.type(table).width == 8
