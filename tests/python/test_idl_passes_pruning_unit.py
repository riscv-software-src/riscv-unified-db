# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest

from udb.idl import parse
from udb.idl.passes import prune
from udb.idl.passes._tree import isolated_symtab
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("true ? 4'b0 : 5'b1", "5'd0"),
        ("false ? 4'sb0 : -(8'sd1)", "8'sd-1"),
        ("true ? (false ? 1 : (true ? 2 : 3)) : 4", "3'd2"),
        ("true ? {1'b1, {31{1'bx}}} : {1'b1, {63{1'b0}}}", "{32'0,1'b1,{31{1'bx}}}"),
    ],
)
def test_expression_specialization_preserves_width(text, expected):
    original = parse(text, "expression")
    serialized = original.to_h()
    parents = [(child, child.parent) for child in original.children]
    assert prune(original, SymbolTable()).to_idl() == expected
    assert original.to_h() == serialized
    assert all(child.parent is parent for child, parent in parents)


def test_pruning_leaves_caller_symbols_unchanged_and_return_removes_dead_statements():
    symtab = SymbolTable()
    symtab.add("a", Var("a", Type(TypeKind.BITS, width=8), 5))
    body = parse("return a; return 2;", "function_body")
    assert prune(body, symtab).to_idl() == "return 8'5;"
    assert symtab.get("a").value == 5
    assert symtab.levels == 1


@pytest.mark.parametrize("text", ["false && a", "a && false", "true || a", "a || true"])
def test_logical_short_circuits_preserve_unknown_runtime_values(text):
    symtab = SymbolTable()
    symtab.add("a", Var("a", Type(TypeKind.BOOLEAN)))
    result = prune(parse(text, "expression"), symtab).to_idl()
    assert result == ("false" if "&&" in text else "true")


def test_pass_local_symbol_clone_owns_global_arrays_and_keeps_binding_metadata():
    symtab = SymbolTable()
    variable = Var(
        "array", Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8)), [1, 2]
    )
    variable.const_incompatible()
    symtab.add("array", variable)
    local = isolated_symtab(symtab)
    local.get("array").value[0] = 3
    assert variable.value == [1, 2]
    assert not local.get("array").const_eval
    local.add("new", Var("new", Type(TypeKind.BOOLEAN)))
    assert symtab.get("new") is None


def test_unknown_array_write_invalidates_only_selected_elements_not_index_variables():
    from udb.idl.passes.pruning import _nullify

    symtab = SymbolTable()
    bits = Type(TypeKind.BITS, width=8)
    symtab.add("array", Var("array", Type(TypeKind.ARRAY, width=3, sub_type=bits), [1, 2, 3]))
    symtab.add("idx", Var("idx", bits, 1))
    _nullify(parse("array[idx] = 5;", "function_body"), symtab)
    assert symtab.get("array").value == [1, None, 3]
    assert symtab.get("idx").value == 1
    symtab.get("idx").value = None
    _nullify(parse("array[idx] = 5;", "function_body"), symtab)
    assert symtab.get("array").value == [None, None, None]


def test_nested_arrays_coerce_all_leaf_widths_and_partial_arrays_are_not_folded():
    symtab = SymbolTable()
    assert prune(parse("[[1],[300]]", "expression"), symtab).to_idl() == "[[9'1],[9'300]]"
    symtab.add(
        "array",
        Var(
            "array",
            Type(TypeKind.ARRAY, width=3, sub_type=Type(TypeKind.BITS, width=8)),
            [1, None, 3],
        ),
    )
    assert prune(parse("array", "expression"), symtab).to_idl() == "array"


def test_loop_initializer_shadows_without_invalidating_outer_binding():
    node = parse(
        "Bits<8> i = 9; for (Bits<8> i = 0; i < 4; i++) { i = i + 1; } return i;",
        "function_body",
    )
    assert prune(node, SymbolTable()).to_idl().endswith("return 8'9;")
