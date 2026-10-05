# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Native wrapper/library fidelity and explicit generator input diagnostics."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from udb import Configuration, Database, ResolvedDatabase
from udb.generators.c_encoding import generate_c_encoding
from udb.generators.encoding_inputs import (
    EncodingGeneratorError,
    ExceptionRecord,
    build_encoding_inputs,
    causes,
)
from udb.generators.generic_cli import main
from udb.generators.go import generate_go
from udb.generators.sv_decode import generate_sv_decode

FIXTURES = Path(__file__).parent / "fixtures/generic_codegen"
MATRIX = json.loads((FIXTURES / "matrix.json").read_text())


@pytest.fixture(scope="module")
def database():
    return Database.from_path("spec/std/isa", schemas_path="spec/schemas").resolve()


def configured(database, label):
    config = (
        Configuration.from_file("cfgs/mc100-32-full-example.yaml")
        if label == "full"
        else Configuration.builtin("_" if label == "all" else label)
    )
    return database.configure(config)


def records(label="all", filename="exceptions.json"):
    return tuple(
        ExceptionRecord.from_mapping(row)
        for row in json.loads((FIXTURES / label / filename).read_text())
    )


def prose_provider():
    try:
        return importlib.import_module("udb.prose")
    except ModuleNotFoundError as error:
        pytest.fail(f"mandatory shared udb.prose provider is missing: {error}")


@pytest.fixture
def output_dir():
    path = Path("gen/test-generic-codegen") / str(uuid4())
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def instruction(name="sample", match="0000000----------000-----0110011", **fields):
    return {
        "kind": "instruction",
        "name": name,
        "encoding": {
            "match": match,
            "variables": [{"name": "x", "location": "24-15"}, {"name": "rd", "location": "11-7"}],
        },
        **fields,
    }


def small_database(*instructions, csrs=(), extensions=()):
    return ResolvedDatabase(
        {
            **{f"inst/{row['name']}.yaml": row for row in instructions},
            **{f"csr/{row['name']}.yaml": {"kind": "csr", **row} for row in csrs},
            **{
                f"ext/{name}.yaml": {
                    "kind": "extension",
                    "name": name,
                    "versions": [{"version": "1.0"}],
                }
                for name in extensions
            },
        }
    )


def test_frozen_matrix_artifact_integrity():
    assert len(MATRIX["cases"]) == 48
    for digest, text in MATRIX["artifacts"].items():
        assert hashlib.sha256(text.encode()).hexdigest() == digest
    failure = MATRIX["errors"]["sv_filtered_cli"]
    assert failure["returncode"] == 1
    assert "AttributeError: 'list' object has no attribute 'split'" in failure["stderr"]


@pytest.mark.parametrize("label", ["all", "rv32", "rv64", "full"])
def test_original_rake_wrapper_bytes(database, label):
    source = configured(database, label)
    rows = records(label)
    assert (
        generate_c_encoding(source, exception_records=rows)
        == (FIXTURES / label / "encoding.out.h").read_text()
    )
    assert (
        generate_sv_decode(source, exception_records=rows)
        == (FIXTURES / label / "riscv_decode_package.svh").read_text()
    )
    # The native header embeds interpreter arguments and absolute checkout
    # paths. Only that single incidental line is intentionally different.
    assert (
        generate_go(source).split("\n", 1)[1]
        == (FIXTURES / label / "inst.go").read_text().split("\n", 1)[1]
    )


@pytest.mark.parametrize(
    "case",
    MATRIX["cases"],
    ids=lambda case: f"{case['config']}-{case['arch']}-{case['mode']}",
)
def test_complete_native_loader_and_renderer_matrix(database, case):
    source = configured(database, case["config"])
    options = {key: case[key] for key in ("extensions", "include_all", "arch")}
    projection = build_encoding_inputs(source, **options)
    assert {row.name: row.match for row in projection.instructions} == case["instructions"]
    assert {str(addr): name for addr, name in projection.csrs} == case["csrs"]
    rows = records(case["config"])
    assert (
        generate_sv_decode(source, exception_records=rows, **options)
        == MATRIX["artifacts"][case["sv"]]
    )
    if "c" in case:
        assert (
            generate_c_encoding(source, exception_records=rows, **options)
            == MATRIX["artifacts"][case["c"]]
        )
    else:
        # There is no native C --arch. Check every generated opcode/mask and
        # CSR against the real native loader rather than invent a C byte oracle.
        header = generate_c_encoding(source, exception_records=rows, **options)
        for row in projection.instructions:
            name = row.name.upper().replace(".", "_")
            assert f"#define MATCH_{name} 0x{row.value:x}\n" in header
            assert f"#define MASK_{name} 0x{row.mask:x}\n" in header
        for addr, name in projection.csrs:
            assert f"#define CSR_{name.replace('.', '_')} 0x{addr:x}\n" in header
    if case["mode"] != "empty":
        assert (
            generate_go(source, **options).split("\n", 1)[1]
            == (MATRIX["artifacts"][case["go"]].split("\n", 1)[1])
        )


def test_native_all_code_rows_not_configured_selection():
    baseline = json.loads((FIXTURES / "all/exceptions.json").read_text())
    assert len(baseline) == 37
    assert len(causes(records())) == 22
    assert [row["ext"] for row in baseline] == sorted(row["ext"] for row in baseline)
    assert [row["ext"] for row in baseline if row["num"] == 20] == ["H", "S", "Sm", "U"]
    for label in ("rv32", "rv64", "full"):
        assert json.loads((FIXTURES / label / "exceptions.json").read_text()) == baseline


@pytest.mark.parametrize("label", ["all", "rv32", "rv64", "full"])
def test_genuine_ruby_interpolated_names_reach_identifiers(database, label):
    rows = records(label, "interpolated-exceptions.json")
    native_names = {num: name for num, name in causes(rows)}
    expected = native_names[20]
    assert expected.startswith("host_")
    assert "<%" not in expected
    source = configured(database, label)
    header = generate_c_encoding(source, exception_records=rows)
    sv = generate_sv_decode(source, exception_records=rows)
    assert f"#define CAUSE_{expected.upper()} 0x14\n" in header
    assert f"CAUSE_{expected.upper()}" in sv
    assert header == (FIXTURES / label / "interpolated-encoding.out.h").read_text()
    assert sv == (FIXTURES / label / "interpolated-decode.svh").read_text()
    assert (
        generate_go(source, extensions="", arch="BOTH").split("\n", 1)[1]
        == (FIXTURES / label / "empty-extension-inst.go").read_text().split("\n", 1)[1]
    )


@pytest.mark.parametrize("label", ["all", "rv32", "rv64", "full"])
def test_shared_prose_provider_genuine_original_wrapper_rows(database, label):
    # Mandatory integration gate. Missing provider is an explicitly reported
    # prerequisite, not evidence of exception-name resolution parity.
    prose = prose_provider()
    source = configured(database, label)
    rows = prose.resolve_all_exception_records(
        database, prose.ProseInputs.from_architecture(source)
    )
    assert list(rows) == json.loads((FIXTURES / label / "exceptions.json").read_text())
    assert generate_c_encoding(source) == (FIXTURES / label / "encoding.out.h").read_text()
    assert generate_sv_decode(source) == (FIXTURES / label / "riscv_decode_package.svh").read_text()


@pytest.mark.parametrize("label", ["all", "rv32", "rv64", "full"])
def test_shared_prose_provider_genuine_interpolation_capture(database, label):
    prose = prose_provider()
    mutation = json.loads((FIXTURES / label / "interpolation.json").read_text())
    native_template = (
        "{% if extensions.H %}Guest{% else %}Host{% endif %}/"
        "{% if derived.has_xlen_32 %}32{% else %}64{% endif %}-fault"
    )
    selected = prose.all_exception_records(database)
    changed = []
    for record in selected:
        if record.name == mutation["original_name"]:
            assert record.name_source is not None
            record = replace(
                record,
                name=native_template,
                var=mutation["template"],
                name_source=replace(record.name_source, text=native_template),
            )
        changed.append(record)
    assert any(record.name == native_template for record in changed)
    source = configured(database, label)
    # The native capture changes code.name in memory, not its YAML filename
    # or the already-selected extension-major rows.
    rows = prose.resolve_exception_records(changed, prose.ProseInputs.from_architecture(source))
    assert list(rows) == json.loads((FIXTURES / label / "interpolated-exceptions.json").read_text())
    typed = tuple(ExceptionRecord.from_mapping(row) for row in rows)
    assert (
        generate_c_encoding(source, exception_records=typed)
        == (FIXTURES / label / "interpolated-encoding.out.h").read_text()
    )
    assert (
        generate_sv_decode(source, exception_records=typed)
        == (FIXTURES / label / "interpolated-decode.svh").read_text()
    )


def test_stable_first_code_deduplication_and_native_sanitization():
    rows = (
        ExceptionRecord(3, "First / named-cause", "A", "Z"),
        ExceptionRecord(1, "One", "B", "A"),
        ExceptionRecord(3, "Second", "C", "A"),
    )
    assert causes(rows) == ((1, "one"), (3, "first___named_cause"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("num", True),
        ("num", -1),
        ("name", ""),
        ("name", "<%= MXLEN %>"),
        ("ext", ""),
    ],
)
def test_exception_rows_fail_explicitly(field, value):
    row = {"num": 1, "name": "Valid", "var": "Valid", "ext": "I", field: value}
    with pytest.raises(EncodingGeneratorError):
        ExceptionRecord.from_mapping(row)


def test_missing_exception_name_context_is_not_silently_empty():
    with pytest.raises(EncodingGeneratorError, match="ConfiguredArchitecture"):
        generate_c_encoding(small_database(instruction()))
    with pytest.raises(EncodingGeneratorError, match="ExceptionRecord"):
        generate_sv_decode(small_database(instruction()), exception_records=[{"num": 0}])


def test_legacy_filter_is_not_architecture_presence_solver():
    source = small_database(instruction())
    # Current {"extension": ...} shape was permissively included by the native
    # filter. No second interpretation of architecture conditions is added.
    conditioned = small_database(
        instruction(definedBy={"extension": {"name": "Absent"}}),
        extensions=("Absent",),
    )
    assert build_encoding_inputs(conditioned, extensions=["I"], include_all=False).instructions
    assert generate_go(source, extensions="") == generate_go(source, include_all=True)
    assert not build_encoding_inputs(source, include_all=False).instructions


@pytest.mark.parametrize("arch", ["RV32", "RV64", "BOTH"])
def test_raw_base_constraint_remains_a_loader_constraint(arch):
    source = small_database(instruction(base=64))
    rows = build_encoding_inputs(source, arch=arch).instructions
    assert bool(rows) == (arch != "RV32")


@pytest.mark.parametrize("value", ["rv32", "RV128", None, 64])
def test_invalid_target_arch_is_explicit(value):
    with pytest.raises(EncodingGeneratorError, match="target architecture"):
        build_encoding_inputs(small_database(), arch=value)


def test_native_c_common_masks_and_sv_compressed_wildcards():
    source = small_database(
        instruction(
            "c.test",
            "000------------1",
            encoding={
                "match": "000------------1",
                "variables": [{"name": "x", "location": "12-1"}],
            },
        )
    )
    header = generate_c_encoding(source, exception_records=())
    assert "#define INSN_FIELD_IMM_S 0xfe000000  /* 31-25 */\n" in header
    assert "INSN_FIELD_X" not in header
    sv = generate_sv_decode(source, exception_records=())
    assert "32'b????????????????000????????????1" in sv


def test_signed_go_csr_field_and_nil_fallback():
    source = small_database(instruction("negative", "1111111----------000-----1110011"))
    text = generate_go(source, include_all=True)
    assert "return &inst{ 0x73, 0x0, 0x0, 0x0, -32, 0x7f }" in text
    assert "\treturn nil\n" in text


def test_identifier_collisions_and_invalid_sv_package_are_diagnostics():
    source = small_database(instruction("a.b"), instruction("ab"))
    with pytest.raises(EncodingGeneratorError, match="collision"):
        generate_go(source, include_all=True)
    with pytest.raises(EncodingGeneratorError, match="package identifier"):
        generate_sv_decode(source, package_name="bad-package", exception_records=())


def test_unsupported_address_and_exception_widths_are_explicit():
    source = small_database(instruction(), csrs=({"name": "wide", "address": 0x1000},))
    with pytest.raises(EncodingGeneratorError, match="12 bits"):
        generate_sv_decode(source, exception_records=())
    assert "#define CSR_WIDE 0x1000" in generate_c_encoding(source, exception_records=())
    too_wide = small_database(instruction(), csrs=({"name": "wide", "address": 0x10000},))
    with pytest.raises(EncodingGeneratorError, match="uint16"):
        generate_go(too_wide, include_all=True)
    rows = (ExceptionRecord(64, "Wide", "Wide", "I"),)
    with pytest.raises(EncodingGeneratorError, match="6 bits"):
        generate_sv_decode(small_database(), exception_records=rows)
    assert "#define CAUSE_WIDE 0x40" in generate_c_encoding(
        small_database(), exception_records=rows
    )


def test_qc_iu_sv_rejects_wide_encodings_instead_of_truncating():
    database = Database.from_path("spec/std/isa", schemas_path="spec/schemas").resolve(
        overlays=("spec/custom/isa/qc_iu",)
    )
    source = database.configure(Configuration.from_file("cfgs/qc_iu.yaml"))
    with pytest.raises(
        EncodingGeneratorError,
        match=r"qc\.e\.addai: SystemVerilog decode needs a 16- or 32-bit encoding",
    ):
        generate_sv_decode(source)


def test_malformed_filter_and_identifier_collisions_fail_explicitly():
    source = small_database(instruction(definedBy={"allOf": 1}))
    with pytest.raises(EncodingGeneratorError, match="alternatives"):
        build_encoding_inputs(source, include_all=False)
    with pytest.raises(EncodingGeneratorError, match="collision"):
        generate_c_encoding(
            small_database(instruction("sample"), instruction("SAMPLE")), exception_records=()
        )
    with pytest.raises(EncodingGeneratorError, match="collision"):
        causes(
            (ExceptionRecord(1, "Same-name", "A", "I"), ExceptionRecord(2, "Same name", "B", "I"))
        )


def test_split_branch_aliasing_preserves_native_naming():
    row = instruction("shift")
    branch = row["encoding"]
    row["definedBy"] = {"xlen": 32}
    row["encoding"] = {"RV32": branch}
    source = small_database(row)
    assert [item.name for item in build_encoding_inputs(source).instructions] == ["shift_rv32"]
    assert [item.name for item in build_encoding_inputs(source, arch="RV32").instructions] == [
        "shift"
    ]
    assert not build_encoding_inputs(source, arch="RV64").instructions


def test_c_suffix_normalization_precedes_native_sorting():
    source = small_database(instruction("a.rv32"), instruction("a0"))
    text = generate_c_encoding(source, exception_records=())
    assert text == (FIXTURES / "native-c-suffix-order.h").read_text()
    assert text.index("#define MATCH_A0 ") < text.index("#define MATCH_A_RV32 ")


def test_cli_config_overlay_uses_only_explicit_caller_resources(output_dir, capsys):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "one.yaml").write_text(
        "kind: instruction\nname: one\nencoding:\n  match: '00000000000000000000000000000001'\n"
    )
    overlay = output_dir / "custom/my-overlay/inst"
    overlay.mkdir(parents=True)
    (overlay / "one.yaml").write_text("encoding:\n  match: '00000000000000000000000000000011'\n")
    config = Configuration.builtin("_").to_dict()
    config["arch_overlay"] = "my-overlay"
    config_path = output_dir / "config.yaml"
    config_path.write_text(json.dumps(config))
    output = output_dir / "go.go"
    args = [
        "--path",
        str(isa.parent),
        "--config",
        str(config_path),
        "--include-all",
        "--output",
        str(output),
    ]
    assert main("go", args) == 1
    assert "--overlay" in capsys.readouterr().err
    assert not output.exists()
    assert main("go", [*args, "--overlay-root", str(overlay.parent.parent)]) == 0
    assert "return &inst{ 0x3," in output.read_text()


def test_cli_creates_parents_and_uses_requested_sv_package(output_dir):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "one.yaml").write_text(
        "kind: instruction\nname: one\nencoding:\n  match: '00000000000000000000000000000001'\n"
    )
    codes = output_dir / "codes.json"
    codes.write_text("[]")
    output = output_dir / "nested/custom.svh"
    assert (
        main(
            "sv-decode",
            [
                "--path",
                str(isa.parent),
                "--exception-records",
                str(codes),
                "--output",
                str(output),
            ],
        )
        == 0
    )
    assert output.read_bytes().startswith(
        b"/* Automatically generated by UDB */\npackage custom;\n"
    )


def test_cli_failure_does_not_replace_existing_output(output_dir, capsys):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "bad.yaml").write_text("kind: instruction\nname: bad\nencoding:\n  match: invalid\n")
    output = output_dir / "existing.h"
    output.write_bytes(b"keep")
    assert main("c-encoding", ["--path", str(isa.parent), "--output", str(output)]) == 1
    assert output.read_bytes() == b"keep"
    assert "match must be" in capsys.readouterr().err


def test_cli_write_failure_is_explicit(output_dir, capsys):
    isa = output_dir / "isa/inst"
    isa.mkdir(parents=True)
    (isa / "one.yaml").write_text(
        "kind: instruction\nname: one\nencoding:\n  match: '00000000000000000000000000000001'\n"
    )
    assert (
        main("go", ["--path", str(isa.parent), "--include-all", "--output", str(output_dir)]) == 1
    )
    assert "cannot write go" in capsys.readouterr().err
