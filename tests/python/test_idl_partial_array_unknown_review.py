# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest

from udb.idl import parse
from udb.idl.errors import IdlValueUnknown
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind


def table():
    bits = Type(TypeKind.BITS, width=8)
    result = SymbolTable()
    result.add("a", Var("a", Type(TypeKind.ARRAY, width=2, sub_type=bits), [5, 6]))
    result.add("b", Var("b", Type(TypeKind.ARRAY, width=2, sub_type=bits), [None, 1]))
    result.push(None)
    return result


@pytest.mark.parametrize("text", ["b[0]", "a[b[0]]"])
def test_partially_unknown_array_reads_raise_standard_value_unknown(text):
    context = table()
    node = parse(text, "expression")
    node.type_check(context)
    with pytest.raises(IdlValueUnknown):
        node.value(context)
    assert parse("b[1]", "expression").value(context) == 1


def test_partially_unknown_array_element_index_write_invalidates_root():
    context = table()
    node = parse("a[b[0]]=9;", "function_body")
    node.type_check(context)
    with pytest.raises(IdlValueUnknown):
        node.execute(context)
    assert context.get("a").value is None
    assert context.get("b").value == [None, 1]


def test_immutable_configuration_array_elements_are_read_normally():
    context = table()
    context.get("b").value = (7, 1)
    node = parse("b[0]", "expression")
    node.type_check(context)
    assert node.value(context) == 7
    assert context.get("b").value == (7, 1)
