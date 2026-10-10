# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Additional owned regressions for the independent adapter review."""

from pathlib import Path

import pytest
from test_idl_architecture_adapter import _architecture

from udb import Configuration, Database, DataError, ResolvedDatabase
from udb.idl.errors import IdlTypeError, IdlValueUnknown
from udb.idl.parser import parse_function_body
from udb.idl.symbols import SymbolTable
from udb.idl_architecture import ArchitectureCompiler
from udb.idl_environment import possible_xlens
from udb.idl_yaml_source import idl_field_source
from udb.source import SourceText, parse_yaml


@pytest.mark.parametrize("header", ["|2", "|2-", "|+2"])
@pytest.mark.parametrize("blank_first", [False, True])
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_literal_offsets_keep_blank_lines_chomping_nested_indent_and_crlf(
    header, blank_first, nested, newline
):
    indent = "  " if nested else ""
    lines = ["outer:"] if nested else []
    lines.append(f"{indent}operation(): {header}")
    if blank_first:
        lines.append(f"{indent}    ")
    lines.extend((f"{indent}    missing = 1;", f"{indent}  return;", f"{indent}  "))
    text = newline.join(lines) + newline
    parsed = parse_yaml(text, source="columns.yaml")
    path = ("outer", "operation()") if nested else ("operation()",)
    value = parsed.value["outer"]["operation()"] if nested else parsed.value["operation()"]
    source = idl_field_source(text, parsed.sources[path], value, label="columns.yaml")
    ast = parse_function_body(source.text, source=source)
    table = SymbolTable()
    table.push(ast)
    with pytest.raises(IdlTypeError) as caught:
        ast.type_check(table)
    raw_position = text.index("missing")
    expected_line = text[:raw_position].count("\n") + 1
    expected_column = raw_position - text.rfind("\n", 0, raw_position)
    assert (caught.value.node.lineno, caught.value.node.column) == (
        expected_line,
        expected_column,
    )
    assert source._pos_to_file_offset(caught.value.node.start) == raw_position
    assert source.starting_line == parsed.sources[path].start_line
    assert source.label == "columns.yaml"


@pytest.mark.parametrize("scalar", ['""', "''", ">", "|"])
def test_empty_scalar_keeps_original_header_mark(scalar):
    text = f"operation(): {scalar}\n"
    parsed = parse_yaml(text, source="empty.yaml")
    span = parsed.sources[("operation()",)]
    source = idl_field_source(text, span, "", label="empty.yaml")
    assert source.starting_offset == span.start_column - 1
    assert source.lineno(0) == span.start_line
    assert source.column(0) == span.start_column


def _conditional_architecture(*, csr_base=None, field_base=None, mxlen=None, reset=None):
    original = _architecture()
    globals_source = original.database.idl_sources["isa/globals.isa"]
    original = _architecture(
        sources={
            globals_source.source: SourceText(
                globals_source.source,
                globals_source.text + "\nBits<MXLEN> UNDEFINED_LEGAL;\n"
                "Bits<MXLEN> UNDEFINED_LEGAL_DETERMINISTIC;\n",
            )
        }
    )
    documents = {path: dict(data) for path, data in original.database.documents.items()}
    csr = documents["csr/demo.yaml"]
    if csr_base is not None:
        csr["definedBy"] = {"allOf": [{"extension": {"name": "I"}}, {"xlen": csr_base}]}
    fields = dict(csr["fields"])
    fields["F"] = dict(fields["F"])
    if field_base is not None:
        fields["F"]["definedBy"] = {"xlen": field_base}
    if reset is not None:
        fields["F"]["reset_value()"] = reset
    csr["fields"] = fields
    configuration = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "conditional",
            "description": "Explicit structural and machine reset contexts.",
            "mandatory_extensions": [{"name": "I", "version": "1.0.0"}],
            "params": {} if mxlen is None else {"MXLEN": mxlen},
        }
    )
    return ResolvedDatabase(documents, idl_sources=original.database.idl_sources).configure(
        configuration
    )


@pytest.mark.parametrize("base", [32, 64])
@pytest.mark.parametrize("field_only", [False, True])
def test_structural_csr_and_field_bases_are_symmetric_in_public_compilation(base, field_only):
    compiler = ArchitectureCompiler(
        _conditional_architecture(
            csr_base=None if field_only else base, field_base=base if field_only else None
        )
    )
    opposite = 64 if base == 32 else 32
    if field_only:
        assert compiler.compile_csr("demo", effective_xlen=opposite).effective_xlen == opposite
    else:
        with pytest.raises(DataError, match=f"RV{opposite}"):
            compiler.compile_csr("demo", effective_xlen=opposite)
    for behavior in ("type()", "sw_write(csr_value)"):
        with pytest.raises(DataError, match=f"RV{opposite}"):
            compiler.compile_field("demo", "F", behavior, effective_xlen=opposite)
        assert (
            compiler.compile_field("demo", "F", behavior, effective_xlen=base).effective_xlen
            == base
        )
    result = compiler.type_check()
    assert result.ok
    assert f"CSR demo.F.type()/RV{base}" in result.checked
    assert f"CSR demo.F.type()/RV{opposite}" not in result.checked


@pytest.mark.parametrize("mxlen", [None, 32, 64])
def test_reset_uses_machine_context_preserves_parameter_metadata_and_visits_once(mxlen):
    compiler = ArchitectureCompiler(_conditional_architecture(mxlen=mxlen))
    machine = compiler.global_symbol_table.get("MXLEN")
    for requested in (32, 64):
        if requested not in possible_xlens(compiler.architecture):
            with pytest.raises(DataError, match=f"RV{requested}"):
                compiler.compile_field("demo", "F", "reset_value()", effective_xlen=requested)
            continue
        reset = compiler.compile_field("demo", "F", "reset_value()", effective_xlen=requested)
        assert reset.effective_xlen == mxlen
        assert reset.symtab.get("MXLEN").type is machine.type
        assert reset.symtab.get("MXLEN").value == machine.value
        effective = reset.symtab.get("__effective_xlen")
        assert (effective is None) if mxlen is None else (effective.value == mxlen)
        assert reset.return_value() == 7
    result = compiler.type_check()
    suffix = "MXLEN" if mxlen is None else f"RV{mxlen}"
    assert [name for name in result.checked if ".reset_value()" in name] == [
        f"CSR demo.F.reset_value()/{suffix}"
    ]


def test_actual_dual_width_reset_request_retains_machine_mxlen_context():
    architecture = _conditional_architecture(mxlen=64)
    documents = dict(architecture.database.documents)
    documents["ext/S.yaml"] = {
        "kind": "extension",
        "name": "S",
        "versions": [{"version": "1.0.0", "state": "ratified"}],
    }
    documents["param/SXLEN.yaml"] = {
        "kind": "parameter",
        "name": "SXLEN",
        "definedBy": {"extension": {"name": "S"}},
        "schema": {"type": "array", "items": {"type": "integer", "enum": [32, 64]}},
    }
    configuration = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "actual-dual",
            "description": "RV64 machine with both supervisor execution widths.",
            "mandatory_extensions": [
                {"name": "I", "version": "1.0.0"},
                {"name": "S", "version": "1.0.0"},
            ],
            "params": {"MXLEN": 64, "SXLEN": [32, 64]},
        }
    )
    architecture = ResolvedDatabase(
        documents, idl_sources=architecture.database.idl_sources
    ).configure(configuration)
    assert possible_xlens(architecture) == (32, 64)
    compiler = ArchitectureCompiler(architecture)
    machine = compiler.global_symbol_table.get("MXLEN")
    for requested in (32, 64):
        reset = compiler.compile_field("demo", "F", "reset_value()", effective_xlen=requested)
        assert reset.effective_xlen == 64
        assert reset.symtab.get("MXLEN").type is machine.type
        assert reset.symtab.get("MXLEN").value == 64
        assert reset.symtab.get("__effective_xlen").value == 64
        assert reset.return_value() == 7


@pytest.mark.parametrize(
    "reset",
    [
        "return MXLEN;",
        "if (MXLEN == 32) { return UNDEFINED_LEGAL; } return 3;",
    ],
)
def test_unknown_reset_results_and_conditions_are_not_undefined_sentinels(reset):
    compiler = ArchitectureCompiler(_conditional_architecture(reset=reset))
    field = compiler.global_symbol_table.csr_hash["demo"].fields[0]
    with pytest.raises(IdlValueUnknown):
        _ = field.reset_value


def test_rooted_include_requires_actual_rootless_target_provenance():
    owner = SourceText("isa/globals.isa", '%version: 1.0\ninclude "helpers.idl"\n', "overlay[0]")
    target = SourceText("isa/helpers.idl", "%version: 1.0\n")
    database = ResolvedDatabase(
        {},
        idl_sources={owner.source: owner, target.source: target},
        idl_source_roots={"overlay[0]": "/captured/custom"},
    )
    with pytest.raises(DataError, match=r"physical origin.*idl_source_roots.*helpers.idl"):
        database.resolve_idl_include(owner, "helpers.idl")


@pytest.fixture(scope="module")
def genuine_compiler():
    root = Path(__file__).resolve().parents[2]
    database = Database.from_path(
        root / "spec/std/isa", schemas_path=root / "spec/schemas"
    ).resolve()
    return ArchitectureCompiler(database.configure(Configuration.from_file(root / "cfgs/_.yaml")))


@pytest.mark.parametrize("number", range(1, 16, 2))
def test_actual_zcmop_empty_operations_compile(genuine_compiler, number):
    result = genuine_compiler.compile_instruction(f"c.mop.{number}", effective_xlen=32)
    assert result.ast.stmts == ()
    assert result.effective_xlen == 32
    assert result.source.text == ""
    assert result.source.label == f"inst/Zcmop/c.mop.{number}.yaml"
