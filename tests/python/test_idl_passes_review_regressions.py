# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Independent semantic oracles for the slice 17 cross-family review."""

import pytest
from test_idl_passes_discovery_unit import _register_symtab

from udb.idl import parse
from udb.idl.errors import IdlValueUnknown
from udb.idl.passes import destination_registers, prune, reachable_functions, source_registers
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)


def scoped_table(**variables):
    table = SymbolTable()
    for name, (dtype, value) in variables.items():
        table.add(name, Var(name, dtype, value))
    table.push(None)
    return table


def functions(text):
    tree = parse("%version: 1.0\n" + text, "isa")
    table = SymbolTable()
    tree.add_global_symbols(table)
    return tree, table


def test_pruned_loop_preserves_changing_array_index_semantics():
    text = "Bits<8> j=0; Bits<8> x=0;for(Bits<8> i=0;i<3;i++){a[j]=9; j=j+1; x=a[1];} return x;"
    dtype = Type(TypeKind.ARRAY, width=3, sub_type=BITS8)
    original = parse(text, "function_body")
    result = prune(original, scoped_table(a=(dtype, [1, 2, 3])))
    assert original.return_value(scoped_table(a=(dtype, [1, 2, 3]))) == 9
    assert result.return_value(scoped_table(a=(dtype, [1, 2, 3]))) == 9


def test_linear_unknown_index_write_does_not_fold_old_array_element():
    original = parse("Bits<8> a[2]=[1,2]; a[u]=5; return a[0];", "function_body")
    result = prune(original, scoped_table(u=(BITS8, None)))
    assert result.children[-1].to_idl() == "return a[0];"


@pytest.mark.parametrize(
    "body",
    [
        "Bits<8> x=0; for(Bits<8> i=0;i<2;i++){if(x==1){c();} x=1;}",
        "Bits<8> a[2]=[0,0]; a[u]=1; if(a[0]==1){c();}",
    ],
)
def test_reachability_includes_calls_after_possible_loop_or_array_writes(body):
    _, table = functions(
        "function c {description {c} body {}}"
        "function g {arguments Bits<8> u description {g} body {" + body + "}}"
    )
    definition = table.get("g").func_def_ast
    before = definition.to_h()
    assert {callee.name for callee in reachable_functions(definition.body, table)} == {"c"}
    assert definition.to_h() == before


def test_known_branch_pruning_preserves_lexical_scope_on_reparse():
    text = "if(true){Bits<8> t=1; x=t;} Bits<8> t=u; return t;"
    table = scoped_table(u=(BITS8, None), x=(BITS8, None))
    result = prune(parse(text, "function_body"), table)
    reparsed = parse(result.to_idl(), "function_body")
    runtime = scoped_table(u=(BITS8, 7), x=(BITS8, None))
    runtime.add("__expected_return_type", BITS8)
    reparsed.type_check(runtime)
    assert reparsed.return_value(runtime) == 7


@pytest.mark.parametrize("discover", [source_registers, destination_registers])
@pytest.mark.parametrize(
    "text",
    [
        "Bits<5> r=rs1; X[r]=X[r];",
        "for(Bits<5> i=0;i<4;i++){X[i]=X[i+1];}",
    ],
)
def test_local_register_indices_are_complex_not_missing_symbols(discover, text):
    table = _register_symtab()
    table.get("rs1").value = None
    with pytest.raises(IdlValueUnknown):
        discover(parse(text, "function_body"), table)
    assert table.get("r") is None
    assert table.get("i") is None
    assert table.get("rs1").value is None


@pytest.mark.parametrize("identity", ["x & 8'h0F", "x | 8'h00"])
def test_bitwise_identity_pruning_preserves_width_and_runtime_value(identity):
    table = scoped_table(x=(Type(TypeKind.BITS, width=4), None))
    original = parse(f"({identity}) << 4", "expression")
    result = prune(original, table)
    assert original.type(table).width == 8
    assert result.type(table).width == 8
    runtime = scoped_table(x=(Type(TypeKind.BITS, width=4), 5))
    assert original.value(runtime) == 80
    assert result.value(runtime) == 80


def test_reachability_accepts_function_definition_root_with_argument_bindings():
    _, table = functions(
        "function c {description {c} body {}}"
        "function g {arguments Bits<8> u description {g} body {if(u==1){c();}}}"
    )
    definition = table.get("g").func_def_ast
    assert {callee.name for callee in reachable_functions(definition, table)} == {"c"}
    assert table.get("u") is None
