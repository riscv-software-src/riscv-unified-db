# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Independent source/compiler acceptance cases from the slice 16 review."""

import pytest
from test_idl_architecture_adapter import _architecture

from udb import Configuration, DataError, ResolvedDatabase
from udb.idl.errors import IdlTypeError
from udb.idl.parser import parse_function_body
from udb.idl.symbols import SymbolTable
from udb.idl_architecture import ArchitectureCompiler
from udb.idl_yaml_source import idl_field_source
from udb.source import SourceText, parse_yaml


@pytest.mark.parametrize("scalar", ['""', "''", ">", "|"])
def test_empty_idl_scalars_accept_every_yaml_style(scalar):
    text = f"operation(): {scalar}\n"
    parsed = parse_yaml(text, source="empty.yaml")
    source = idl_field_source(
        text, parsed.sources[("operation()",)], parsed.value["operation()"], label="empty.yaml"
    )
    assert source.text == ""
    assert parse_function_body(source.text, source=source).stmts == ()


def _restricted_compiler(*, field_only=False):
    original = _architecture()
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    restriction = {"allOf": [{"extension": {"name": "I"}}, {"xlen": 32}]}
    csr = documents["csr/demo.yaml"]
    if not field_only:
        csr["definedBy"] = restriction
    fields = dict(csr["fields"])
    fields["F"] = {**fields["F"], "definedBy": {"xlen": 32}}
    csr["fields"] = fields
    configuration = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "unpinned",
            "description": "Both machine widths are possible.",
            "mandatory_extensions": [{"name": "I", "version": "1.0.0"}],
            "params": {},
        }
    )
    database = ResolvedDatabase(documents, idl_sources=original.database.idl_sources)
    return ArchitectureCompiler(database.configure(configuration))


def test_rv32_only_csr_never_compiles_or_is_visited_under_rv64():
    compiler = _restricted_compiler()
    with pytest.raises(DataError, match="RV64"):
        compiler.compile_csr("demo", effective_xlen=64)
    result = compiler.type_check()
    assert not any(
        context.startswith("CSR demo.") and context.endswith("/RV64") for context in result.checked
    )
    assert "CSR demo.sw_read()/RV32" in result.checked


def test_rv32_only_field_rejects_rv64_compilation():
    compiler = _restricted_compiler(field_only=True)
    with pytest.raises(DataError, match="RV64"):
        compiler.compile_field("demo", "F", "type()", effective_xlen=64)


def test_typecheck_filters_csr_and_independent_field_base_restrictions():
    result = _restricted_compiler().type_check()
    assert "CSR demo.sw_read()/RV32" in result.checked
    assert "CSR demo.sw_read()/RV64" not in result.checked
    result = _restricted_compiler(field_only=True).type_check()
    assert "CSR demo.sw_read()/RV64" in result.checked
    assert "CSR demo.F.type()/RV32" in result.checked
    assert "CSR demo.F.type()/RV64" not in result.checked


@pytest.mark.parametrize("sentinel", ["UNDEFINED_LEGAL", "UNDEFINED_LEGAL_DETERMINISTIC"])
def test_real_undefined_reset_declarations_normalize_both_sentinels(sentinel):
    original = _architecture()
    globals_source = original.database.idl_sources["isa/globals.isa"]
    architecture = _architecture(
        sources={
            globals_source.source: SourceText(
                globals_source.source,
                globals_source.text + f"Bits<MXLEN> {sentinel};\n",
            )
        }
    )
    documents = {path: dict(data) for path, data in architecture.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    fields = dict(csr["fields"])
    fields["F"] = {**fields["F"], "reset_value()": f"return {sentinel};"}
    csr["fields"] = fields
    database = ResolvedDatabase(documents, idl_sources=architecture.database.idl_sources)
    compiler = ArchitectureCompiler(database.configure(architecture.configuration))
    field = compiler.global_symbol_table.csr_hash["demo"].fields[0]
    assert field.reset_value == "UNDEFINED_LEGAL"


@pytest.mark.parametrize("header", ["|2", "|2-", "|+2"])
def test_explicit_literal_indent_maps_overindented_first_line_exactly(header):
    text = f"operation(): {header}\n    missing = 1;\n  return;\n"
    parsed = parse_yaml(text, source="indent.yaml")
    source = idl_field_source(
        text, parsed.sources[("operation()",)], parsed.value["operation()"], label="indent.yaml"
    )
    ast = parse_function_body(source.text, source=source)
    table = SymbolTable()
    table.push(ast)
    with pytest.raises(IdlTypeError) as caught:
        ast.type_check(table)
    assert (caught.value.node.lineno, caught.value.node.column) == (2, 5)
