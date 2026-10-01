# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest

from udb.cpp_hart.emitter import Emitter
from udb.cpp_hart.types import cpp_type, names
from udb.idl.parser import parse_expression, parse_function_body
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import VOID_TYPE, WIDTH_UNKNOWN, EnumerationType, Qualifier, Type, TypeKind


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8'hff", "_Bits<8, false>{255_b}"),
        ("8'shff", "_Bits<8, true>{255_b}"),
        ("true", "true"),
        ("$signed(8'h80)", "(_Bits<8, false>{128_b}).make_signed()"),
        ("$signed(8'shff)", "(_Bits<8, true>{255_b}).make_signed()"),
        ("8'hf `+ 8'h1", "(_Bits<8, false>{15_b}.widening_add(_Bits<8, false>{1_b}))"),
        ("8'hf[3:1]", "_Bits<8, false>{15_b}.template extract<3, 1>()"),
    ],
)
def test_expression_lowering(text, expected):
    table = SymbolTable()
    node = parse_expression(text)
    node.type_check(table)
    assert Emitter(table).expression(node) == expected


def test_emission_owns_scopes_and_preserves_native_decode_access():
    table = SymbolTable()
    table.add(
        "imm",
        Var("imm", Type(TypeKind.BITS, width=12, qualifiers=(Qualifier.SIGNED,)), decode_var=True),
    )
    assert Emitter(table).expression(parse_expression("imm")) == "imm()"
    assert Emitter(table).expression(parse_expression("$signed(imm)")) == "(imm()).make_signed()"
    body = parse_function_body("Bits<8> x = 1; if (x == 1) { x = 2; }")
    table.push(body)
    table.add("__expected_return_type", VOID_TYPE)
    body.type_check(table)
    text = Emitter(table).statement(body)
    assert "PossiblyUnknownBits<8> x" in text
    assert "if (" in text and "x =" in text
    assert table.levels == 2


def test_native_type_families():
    assert cpp_type(Type(TypeKind.BITS, width=32)) == "_PossiblyUnknownBits<32, false>"
    assert (
        cpp_type(Type(TypeKind.BITS, width=WIDTH_UNKNOWN, max_width=128).make_signed())
        == "_PossiblyUnknownRuntimeBits<128, true>"
    )
    assert names("rv32-test", "hart") == "Rv32Test_Hart"
    assert names("rv32", "csr_field", "mstatus", "MIE") == "Rv32_Mstatus_Mie_Field"


def test_unbounded_runtime_width_uses_native_infinite_precision_constant():
    emitter = Emitter(SymbolTable())
    dtype = Type(TypeKind.BITS, width=WIDTH_UNKNOWN)
    assert emitter.runtime_width(dtype) == "BitsInfinitePrecision"
    assert emitter.runtime_width(dtype, raw=True) == "BitsInfinitePrecision"


def test_tuple_dontcare_return_has_concrete_native_type():
    table = SymbolTable()
    body = parse_function_body("return 1, -;")
    table.push(body)
    table.add(
        "__expected_return_type",
        Type(TypeKind.TUPLE, tuple_types=(Type(TypeKind.BITS, width=8), Type(TypeKind.BOOLEAN))),
    )
    body.type_check(table)
    assert Emitter(table).statement(body) == "return std::make_tuple(_Bits<1, false>{1_b}, bool{});"


def test_enum_cast_uses_the_accepted_type_name_not_ast_repr():
    table = SymbolTable()
    table.add("Mode", EnumerationType("Mode", ("Zero", "One"), (0, 1)))
    node = parse_expression("$enum(Mode, 8'h1)")
    node.type_check(table)
    assert Emitter(table).expression(node) == "Mode{_Bits<8, false>{1_b}}"


def test_enum_array_cast_uses_the_accepted_type_node():
    table = SymbolTable()
    table.add("Mode", EnumerationType("Mode", ("Zero", "Four"), (0, 4)))
    node = parse_expression("$enum_to_a(Mode)")
    node.type_check(table)
    assert Emitter(table).expression(node) == "std::array<Bits<3>, 2>{0_b, 4_b}"
