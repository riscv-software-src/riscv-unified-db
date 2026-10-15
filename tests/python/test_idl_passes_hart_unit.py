# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path

import pytest

from udb import Configuration, Database
from udb.idl import parse
from udb.idl.passes import constexpr, control_flow, written
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind
from udb.idl_architecture import ArchitectureCompiler

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def database():
    return Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()


@pytest.mark.parametrize(
    ("configuration", "name", "value", "known"),
    [
        ("rv32-riscv-tests", "MXLEN", 32, True),
        ("rv32-riscv-tests", "MUTABLE_MISA_C", False, True),
        ("rv32-riscv-tests", "IMP_ID_VALUE", 0, True),
        ("_", "MXLEN", None, False),
    ],
)
def test_constexpr_uses_actual_architectural_parameter_properties(
    database, configuration, name, value, known
):
    architecture = database.configure(
        Configuration.from_file(ROOT / "cfgs" / f"{configuration}.yaml")
    )
    symtab = ArchitectureCompiler(architecture).global_symbol_table
    parameter = symtab.param(name)
    assert parameter is not None
    assert parameter.value_known is known
    binding = symtab.get(name)
    assert isinstance(binding, Var) and binding.param
    assert binding.value == value
    assert constexpr(parse(name, "expression"), symtab) is known


def test_constexpr_distinguishes_local_known_global_and_runtime_bindings():
    symtab = SymbolTable()
    bits = Type(TypeKind.BITS, width=8)
    symtab.add("local", Var("local", bits, 1))
    symtab.add("runtime", Var("runtime", bits))
    symtab.add("global", Var("global", bits.make_global(), 1))
    assert constexpr(parse("local + 1", "expression"), symtab)
    assert not constexpr(parse("runtime + 1", "expression"), symtab)
    assert not constexpr(parse("global + 1", "expression"), symtab)
    assert not constexpr(parse("CSR[mstatus]", "expression"), symtab)
    assert not constexpr(parse("helper()", "expression"), symtab)
    assert constexpr(parse("CSR[mstatus].address()", "expression"), symtab)


def test_control_flow_recursion_and_exception_raises():
    tree = parse(
        "%version: 1.0\n"
        "function a { description { a } body { b(); } }"
        "function b { description { b } body { a(); $pc = 4; } }",
        "isa",
    )
    symtab = SymbolTable()
    tree.add_global_symbols(symtab)
    assert control_flow(parse("a()", "expression"), symtab)
    assert not control_flow(parse("raise(2)", "expression"), symtab)


@pytest.mark.parametrize(
    ("text", "written_names"),
    [
        ("a = b;", {"a"}),
        ("values[idx] = a;", {"values"}),
        ("values[idx][7:0] = a;", {"values"}),
        ("field.part = b;", {"field"}),
        ("(a, -, b) = helper();", {"a", "b"}),
        (
            (
                "for (Bits<8> a = 0; a < 4; a++) { helper(); } "
                "for (Bits<8> b = 4; b > 0; b--) { helper(); }"
            ),
            {"a", "b"},
        ),
        ("$pc = a;", {"$pc"}),
    ],
)
def test_written_locations_do_not_include_indices_or_rhs(text, written_names):
    node = parse(text, "function_body")
    symtab = SymbolTable()
    names = {"a", "b", "values", "idx", "field", "$pc"}
    assert {name for name in names if written(node, symtab, name)} == written_names


def test_direct_lvalue_analysis_keeps_index_as_a_read():
    node = parse("values[idx][7:0]", "expression")
    symtab = SymbolTable()
    assert written(node, symtab, "values", in_assignment=True)
    assert not written(node, symtab, "idx", in_assignment=True)
