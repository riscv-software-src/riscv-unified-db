# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Native public body probes for defects exposed by actual architecture acceptance."""

import pytest
from test_idl_architecture_adapter import _architecture

from udb import ResolvedDatabase
from udb.idl.errors import IdlTypeError, IdlValueUnknown
from udb.idl.parser import parse_expression
from udb.idl.symbols import SymbolTable
from udb.idl.types import CsrFieldLike, CsrLike, FunctionType
from udb.idl_architecture import ArchitectureCompiler
from udb.idl_environment import idl_environment, symbol_table
from udb.source import SourceText


def _field_architecture(*, condition=True, access="RO", reset=7):
    architecture = _architecture()
    documents = {path: dict(data) for path, data in architecture.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    fields = dict(csr["fields"])
    fields["F"] = {
        "definedBy": condition,
        "location_rv32": "3-0",
        "location_rv64": "7-0",
        "type": access,
        "reset_value": reset,
    }
    csr["fields"] = fields
    return ResolvedDatabase(documents, idl_sources=architecture.database.idl_sources).configure(
        architecture.configuration
    )


def test_public_symbol_table_has_actual_native_descriptor_protocol_and_ro_value():
    architecture = _field_architecture()
    table = symbol_table(architecture)
    csr = table.csr_hash["demo"]
    field = csr.fields[0]
    assert isinstance(csr, CsrLike)
    assert isinstance(field, CsrFieldLike)
    assert csr.address == 0x100
    assert field.defined_in_all_bases is True
    assert field.defined_in_base32 is True
    assert field.defined_in_base64 is True
    assert field.exists is True
    assert field.reset_value == 7
    assert field.type(32) == "RO"
    expression = parse_expression("CSR[demo].F")
    expression.type_check(table)
    assert expression.value(table) == 7
    direct = SymbolTable(idl_environment(architecture))
    assert direct.csr_hash["demo"].fields[0].type(32) == "RO"
    assert direct.csr_hash["demo"].fields[0].reset_value == 7
    assert parse_expression("CSR[demo].F").value(direct) == 7


def test_native_field_properties_do_not_treat_bound_predicates_as_true():
    table = symbol_table(_field_architecture(condition={"xlen": 32}))
    field = table.csr_hash["demo"].fields[0]
    assert field.defined_in_all_bases is False
    assert field.base32_only is True
    assert field.base64_only is False
    assert parse_expression("CSR[demo].F").type(table).width == 4


def test_native_absent_field_read_is_zero_not_a_truthy_bound_method():
    table = symbol_table(_field_architecture(condition={"xlen": 64}))
    assert table.csr_hash["demo"].fields[0].exists is False
    assert parse_expression("CSR[demo].F").value(table) == 0


def test_native_non_ro_and_undefined_reset_stay_explicitly_unknown():
    for architecture in (
        _field_architecture(access="RW"),
        _field_architecture(reset="UNDEFINED_LEGAL"),
    ):
        with pytest.raises(IdlValueUnknown):
            parse_expression("CSR[demo].F").value(symbol_table(architecture))


def test_explicit_sw_write_uses_source_defined_bitfield_even_for_absent_fields():
    architecture = _field_architecture(condition=False)
    documents = {path: dict(data) for path, data in architecture.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    field = dict(csr["fields"]["F"])
    field["sw_write(csr_value)"] = "return csr_value.F;"
    csr["fields"] = {"F": field}
    architecture = ResolvedDatabase(
        documents, idl_sources=architecture.database.idl_sources
    ).configure(architecture.configuration)
    compiler = ArchitectureCompiler(architecture)
    assert compiler.global_symbol_table.csr_hash["demo"].fields[0].exists is False
    result = compiler.compile_field("demo", "F", "sw_write(csr_value)", effective_xlen=32)
    result.symtab.get("csr_value").value = 9
    assert result.return_value() == 9
    assert not any(".F.sw_write" in name for name in compiler.type_check().checked)


@pytest.mark.parametrize("argument", ["mode", "tinst_value"])
def test_public_function_argument_can_shadow_registered_global_function(argument):
    architecture = _architecture()
    source = architecture.database.idl_sources["isa/globals.isa"]
    architecture = _architecture(
        sources={
            source.source: SourceText(
                source.source,
                source.text + f"\nfunction {argument} {{ returns Bits<8> "
                "description { Global function. } body { return 1; } }\n"
                f"function local_arg {{ returns Bits<8> arguments Bits<8> {argument} "
                f"description {{ Local argument. }} body {{ return {argument}; }} }}\n",
            )
        }
    )
    compiler = ArchitectureCompiler(architecture)
    result = compiler.compile_function("local_arg")
    result.symtab.get(argument).value = 5
    assert result.return_value() == 5
    assert isinstance(compiler.global_symbol_table.get(argument), FunctionType)


def test_public_function_still_rejects_duplicate_arguments_in_its_own_scope():
    architecture = _architecture()
    source = architecture.database.idl_sources["isa/globals.isa"]
    architecture = _architecture(
        sources={
            source.source: SourceText(
                source.source,
                source.text + "\nfunction duplicate { returns Bits<8> "
                "arguments Bits<8> mode, Bits<8> mode "
                "description { Duplicate arguments. } body { return mode; } }\n",
            )
        }
    )
    with pytest.raises(IdlTypeError, match="already bound in this scope"):
        ArchitectureCompiler(architecture).compile_function("duplicate")
