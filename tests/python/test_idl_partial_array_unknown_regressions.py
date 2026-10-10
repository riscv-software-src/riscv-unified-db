# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Partially unknown aggregates retain explicit unknowns and owned input state."""

import pytest

from udb.idl.errors import IdlInternalError, IdlTypeError, IdlValueUnknown
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)
ARRAY2 = Type(TypeKind.ARRAY, width=2, sub_type=BITS8)


def context():
    original_a, original_b = [5, 6], [None, 1]
    table = SymbolTable(
        IdlEnvironment(
            builtin_global_vars=(Var("a", ARRAY2, original_a), Var("b", ARRAY2, original_b))
        )
    )
    table.push(None)
    return table, original_a, original_b


@pytest.mark.parametrize("text", ["b[0]", "a[b[0]]", "a[0] + b[0]"])
def test_unknown_element_and_dependent_operations_keep_standard_unknown(text):
    table, original_a, original_b = context()
    node = parse_expression(text)
    node.type_check(table)
    with pytest.raises(IdlValueUnknown, match="Value of 'b\\[0\\]' not known"):
        node.value(table)
    assert parse_expression("b[1]").value(table) == 1
    assert table.get("a").value == original_a == [5, 6]
    assert table.get("b").value == original_b == [None, 1]


def test_unknown_index_write_preserves_environment_inputs_and_source_siblings():
    table, original_a, original_b = context()
    node = parse_function_body("a[b[0]] = 9;")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.execute(table)
    assert table.get("a").value is None
    assert table.get("b").value == [None, 1]
    assert original_a == [5, 6]
    assert original_b == [None, 1]


def test_nested_partial_array_preserves_known_siblings_and_invalidates_root():
    table, _, _ = context()
    matrix = Type(TypeKind.ARRAY, width=2, sub_type=ARRAY2)
    table.add("m", Var("m", matrix, [[None, 1], [2, 3]]))
    unknown = parse_expression("m[0][0]")
    unknown.type_check(table)
    with pytest.raises(IdlValueUnknown):
        unknown.value(table)
    assert parse_expression("m[0][1]").value(table) == 1
    assert parse_expression("m[1][0]").value(table) == 2
    node = parse_function_body("m[m[0][0]][1] = 9;")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.execute(table)
    assert table.get("m").value is None


@pytest.mark.parametrize("text", ["a[2]", "a[true]"])
def test_known_invalid_indices_remain_type_errors(text):
    table, _, _ = context()
    with pytest.raises(IdlTypeError):
        parse_expression(text).type_check(table)


@pytest.mark.parametrize("values", [(None, 1), (7, 1)])
def test_readonly_configuration_tuples_keep_sibling_precision_and_ownership(values):
    table = SymbolTable(
        IdlEnvironment(builtin_global_vars=(Var("CFG", ARRAY2.make_const(), values, param=True),))
    )
    stored = table.get("CFG").value
    selected = parse_expression("CFG[0]")
    selected.type_check(table)
    if values[0] is None:
        with pytest.raises(IdlValueUnknown):
            selected.value(table)
    else:
        assert selected.value(table) == 7
    assert parse_expression("CFG[1]").value(table) == 1
    assert table.get("CFG").value is stored
    assert table.get("CFG").value == values
    assert isinstance(stored, tuple)


def test_readonly_configuration_tuple_writes_are_rejected():
    table = SymbolTable()
    table.add("CFG", Var("CFG", ARRAY2.make_const(), (7, 1), param=True))
    table.push(None)
    with pytest.raises(IdlTypeError, match="Assigning to a constant"):
        parse_function_body("CFG[0] = 9;").type_check(table)
    assert table.get("CFG").value == (7, 1)


@pytest.mark.parametrize("value", ["07", {0: 7}])
def test_nonarray_host_values_remain_explicit_internal_errors(value):
    table, _, _ = context()
    table.get("b").value = value
    node = parse_expression("b[0]")
    node.type_check(table)
    with pytest.raises(IdlInternalError, match="Not an array"):
        node.value(table)
