# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Compiler integration regressions with explicit captured custom sources."""

import pytest

from udb import Configuration, DataError, ResolvedDatabase
from udb.idl.errors import IdlInternalError, IdlTypeError
from udb.idl.types import Qualifier
from udb.idl_architecture import ArchitectureCompiler
from udb.idl_environment import condition_symbol_table, symbol_table
from udb.idl_global_environment import global_ast
from udb.source import SourceText, parse_yaml


def _architecture(*, sources=None, operation="Bits<16> enc = $encoding; g = imm;"):
    documents = {
        "ext/I.yaml": {
            "kind": "extension",
            "name": "I",
            "versions": [{"version": "1.0.0", "state": "ratified"}],
        },
        "param/MXLEN.yaml": {
            "kind": "parameter",
            "name": "MXLEN",
            "definedBy": True,
            "schema": {"type": "integer", "enum": [32, 64]},
        },
        "inst/inc.yaml": {
            "kind": "instruction",
            "name": "inc",
            "definedBy": {"extension": {"name": "I"}},
            "encoding": {
                "match": "----------------",
                "variables": [
                    {"name": "imm", "location": "7-0", "sign_extend": True},
                ],
            },
            "operation()": operation,
        },
        "csr/demo.yaml": {
            "kind": "csr",
            "name": "demo",
            "definedBy": {"extension": {"name": "I"}},
            "address": 0x100,
            "priv_mode": "M",
            "length": 32,
            "sw_read()": "return 12;",
            "fields": {
                "F": {
                    "location": "3-0",
                    "type()": "return CsrFieldType::RW;",
                    "reset_value()": "return add_one(6);",
                    "sw_write(csr_value)": "return csr_value.F;",
                }
            },
        },
    }
    sources = {
        "isa/globals.isa": SourceText(
            "isa/globals.isa",
            '%version: 1.0\ninclude "helpers.idl"\ninclude "helpers.idl"\n'
            "enum CsrFieldType { RO 0 ROH 1 RW 2 RWR 3 RWH 4 RWRH 5 }\n"
            "Bits<32> g;\nU32 INSTR_ENC_SIZE = 16;\n",
        ),
        "isa/helpers.idl": SourceText(
            "isa/helpers.idl",
            "%version: 1.0\nfunction add_one {\n"
            "  returns Bits<8>\n  arguments Bits<8> x\n"
            "  description { Increment. }\n  body { return x + 1; }\n}\n",
            "overlay[0]",
        ),
        **(sources or {}),
    }
    database = ResolvedDatabase(documents, idl_sources=sources)
    configuration = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "fully configured",
            "name": "custom",
            "description": "custom compiler fixture",
            "implemented_extensions": [{"name": "I", "version": "1.0.0"}],
            "params": {"MXLEN": 32},
        }
    )
    return database.configure(configuration)


def test_runtime_loads_captured_sources_once_and_preserves_include_origin():
    architecture = _architecture()
    table = symbol_table(architecture)
    assert table.get("INSTR_ENC_SIZE").value == 16
    assert table.get("add_one").func_def_ast.source.label == "overlay[0]:isa/helpers.idl"
    ast = global_ast(architecture.database)
    assert [item.name for item in ast.functions] == ["add_one"]


def test_condition_bootstrap_reads_inherited_encoding_constant_without_other_globals():
    architecture = _architecture(
        sources={
            "isa/globals.isa": SourceText(
                "isa/globals.isa", '%version: 1.0\ninclude "helpers.idl"\nBits<MXLEN> OTHER;\n'
            ),
            "isa/helpers.idl": SourceText(
                "isa/helpers.idl", "%version: 1.0\nU32 INSTR_ENC_SIZE = 24;\n", "overlay[0]"
            ),
        }
    )
    table = condition_symbol_table(architecture.database)
    assert table.get("INSTR_ENC_SIZE").value == 24
    assert table.get("OTHER") is None
    assert table.get("MXLEN").value is None


def test_instruction_context_has_real_encoding_width_and_signed_decode_variables():
    compiler = ArchitectureCompiler(_architecture())
    compiled = compiler.compile_instruction("inc", effective_xlen=32)
    assert compiled.effective_xlen == 32
    assert compiled.symtab.get("__instruction_encoding_size").value == 16
    assert compiled.symtab.get("__effective_xlen").value == 32
    assert compiled.symtab.get("imm").decode_var
    assert compiled.symtab.get("imm").type.width == 8
    assert Qualifier.SIGNED in compiled.symtab.get("imm").type.qualifiers
    compiled.symtab.get("g").value = 4
    assert compiler.global_symbol_table.get("g").value is None
    assert compiler.compile_instruction("inc", effective_xlen=32).symtab.get("g").value is None
    with pytest.raises(ValueError, match="explicit"):
        compiler.compile_instruction("inc", effective_xlen=None)


def test_function_and_field_bodies_evaluate_using_normal_call_semantics():
    compiler = ArchitectureCompiler(_architecture())
    function = compiler.compile_function("add_one")
    assert function.source.label == "overlay[0]:isa/helpers.idl"
    function.symtab.get("x").value = 20
    assert function.return_value() == 21
    assert function.return_value() == 21
    assert compiler.compile_csr("demo", effective_xlen=32).return_value() == 12
    assert compiler.compile_field("demo", "F", "reset_value()").return_value() == 7
    field = compiler.global_symbol_table.csr_hash["demo"].fields[0]
    assert field.type(32) == "RW"
    assert field.reset_value == 7
    write = compiler.compile_field("demo", "F", "sw_write(csr_value)", effective_xlen=32)
    assert write.symtab.get("csr_value").type.field_names == ("F",)
    result = compiler.type_check()
    assert result.ok, [(item.context, str(item.error)) for item in result.diagnostics]
    assert "instruction inc/RV32" in result.checked
    assert "function add_one" in result.checked


def test_function_return_types_can_depend_on_bound_argument_symbols():
    architecture = _architecture()
    helper = architecture.database.idl_sources["isa/helpers.idl"]
    architecture = _architecture(
        sources={
            "isa/helpers.idl": SourceText(
                helper.source,
                helper.text + "\nfunction sized {\nreturns Bits<N>\n"
                "arguments Bits<8> x, U32 N\n"
                "description { Argument-dependent return width. }\nbody { return x; }\n}\n",
            ),
        }
    )
    result = ArchitectureCompiler(architecture).compile_function("sized", type_check=False)
    assert result.symtab.get("N").value is None
    assert result.expected_return_type.width == "unknown"


def test_architecture_typecheck_reports_bad_body_without_hiding_other_contexts():
    result = ArchitectureCompiler(_architecture(operation="g = unknown;")).type_check()
    assert not result.ok
    assert "instruction inc/RV32" in result.checked
    assert "CSR demo.F.reset_value()/RV32" in result.checked
    assert [(item.context, type(item.error)) for item in result.diagnostics] == [
        ("instruction inc/RV32", IdlTypeError)
    ]
    with pytest.raises(IdlInternalError, match="unknown"):
        result.raise_errors()


@pytest.mark.parametrize(
    "target", ["missing.idl", "globals.isa", "../globals.isa", "/absolute.idl"]
)
def test_include_missing_cycle_and_escape_are_explicit(target):
    architecture = _architecture(
        sources={
            "isa/helpers.idl": SourceText(
                "isa/helpers.idl", f'%version: 1.0\ninclude "{target}"\n'
            ),
        }
    )
    with pytest.raises(DataError):
        global_ast(architecture.database)


def test_missing_entrypoint_never_substitutes_bundled_globals():
    with pytest.raises(DataError, match=r"globals\.isa"):
        global_ast(
            ResolvedDatabase(
                {},
                idl_sources={
                    "isa/helpers.idl": SourceText("isa/helpers.idl", "%version: 1.0\n"),
                },
            )
        )


def test_yaml_diagnostics_use_captured_overlay_source_columns():
    architecture = _architecture(operation="g = unknown;")
    text = "kind: instruction\nname: inc\noperation(): |\n    g = unknown;\n"
    parsed = parse_yaml(text, source="inst/inc.yaml", layer="overlay[1]")
    original = architecture.database.documents
    database = ResolvedDatabase(
        original,
        sources={"inst/inc.yaml": parsed.sources},
        source_texts={("overlay[1]", "inst/inc.yaml"): text},
        idl_sources=architecture.database.idl_sources,
    )
    compiler = ArchitectureCompiler(database.configure(architecture.configuration))
    with pytest.raises(IdlTypeError) as caught:
        compiler.compile_instruction("inc", effective_xlen=32)
    assert caught.value.node.source.label == "overlay[1]:inst/inc.yaml"
    assert (caught.value.node.lineno, caught.value.node.column) == (4, 9)
