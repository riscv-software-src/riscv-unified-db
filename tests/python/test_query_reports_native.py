# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Entire real native artifacts, captured before production Python implementation."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb import Configuration, Database
from udb.query_reports import (
    InstructionMatcher,
    ReportBuilder,
    render_extension,
    render_names,
    render_parameter,
)
from udb.query_reports.cli import main
from udb.query_reports.formatting import condition_text

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parent / "fixtures/query_reports"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


@pytest.fixture(scope="module")
def database():
    return Database.bundled().resolve()


@pytest.fixture(scope="module")
def builders(database):
    return {
        name: ReportBuilder(
            database.configure(
                Configuration.from_file(ROOT / "cfgs/mc100-32-full-example.yaml")
                if name == "full"
                else Configuration.builtin(name)
            )
        )
        for name in ("_", "rv32", "rv64", "full")
    }


@pytest.fixture(scope="module")
def matchers(builders):
    return {name: InstructionMatcher(builder.architecture) for name, builder in builders.items()}


def native(name):
    return (FIXTURES / f"{name}.stdout.txt").read_bytes()


def test_native_capture_hashes_and_native_sources_are_frozen():
    assert MANIFEST["base"] == "a67618c2"
    assert "unmodified" in MANIFEST["transport"]
    layout_oracle = json.loads((ROOT / "tests/data/qc_layouts/oracle.json").read_text())
    migrated_layouts = {output["path"]: output for output in layout_oracle["outputs"].values()}
    for name, observation in MANIFEST["cases"].items():
        assert observation["command"][1] == "tools/ruby-gems/udb/bin/udb"
        for stream in ("stdout", "stderr"):
            assert (
                hashlib.sha256((FIXTURES / f"{name}.{stream}.txt").read_bytes()).hexdigest()
                == observation[f"{stream}_sha256"]
            )
    for name, expected in MANIFEST["sources"].items():
        source = ROOT / name
        if source.is_file():
            content = source.read_bytes()
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected:
                migrated = migrated_layouts[name]
                assert migrated["native_sha256"] == expected
                first, rest = content.split(b"\n", 1)
                assert rest.startswith(b"\n# WARNING: This file is auto-generated from ")
                warning_end = rest.index(b"\n\n", 1) + 2
                original = first + b"\n" + rest[warning_end:]
                assert hashlib.sha256(original).hexdigest() == migrated["accepted_sha256"]
            continue
        assert name == "spec/custom/isa/qc_iu/csr/Xqci/gen_mcliciX.rb"
        assert layout_oracle["generator"] == name
        assert layout_oracle["generator_sha256"] == expected
        assert hashlib.sha256(layout_oracle["generator_source"].encode()).hexdigest() == expected
    auxiliary = json.loads((FIXTURES / "native-auxiliary-manifest.json").read_text())
    for name, expected in auxiliary["outputs"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected


def test_entire_native_model_condition_reports():
    observations = json.loads((FIXTURES / "native-condition-observations.json").read_text())
    assert len(observations) == 13
    for observation in observations:
        assert condition_text(observation["raw"]) == observation["text"]
        assert condition_text(observation["raw"], pretty=True) == observation["pretty"]


@pytest.mark.parametrize("name", ["I", "Zicsr", "C", "missing"])
def test_entire_extension_human_report(builders, name):
    lookup = "NoSuchExtension" if name == "missing" else name
    assert render_extension(builders["_"].extension(lookup), lookup).encode() == native(
        f"show-extension-{name}"
    )


@pytest.mark.parametrize("name", ["MXLEN", "SXLEN", "ARCH_ID_VALUE", "NUM_PMP_ENTRIES", "missing"])
def test_entire_parameter_human_report(builders, name):
    lookup = "NO_SUCH_PARAMETER" if name == "missing" else name
    assert render_parameter(builders["_"].parameter(lookup), lookup).encode() == native(
        f"show-parameter-{name}"
    )


def test_parameter_value_heading_is_schema_not_configured_value(builders):
    report = builders["full"].parameter("MXLEN")
    assert report.has_configured_value and report.configured_value == 32
    assert report.render().encode() == native("show-parameter-full-MXLEN")


@pytest.mark.parametrize(
    ("config", "fixture"),
    [
        ("_", "list-extensions-all"),
        ("rv32", "list-extensions-rv32"),
        ("full", "list-extensions-full"),
    ],
)
def test_entire_extension_list_order(builders, config, fixture):
    assert render_names(builders[config].extensions()).encode() == native(fixture)


@pytest.mark.parametrize("config", ["_", "full"])
def test_csr_listing_is_catalog_even_when_configured(builders, config):
    assert render_names(builders[config].csrs()).encode() == native(
        "list-csrs-all" if config == "_" else "list-csrs-full"
    )


@pytest.mark.parametrize(
    ("extensions", "label"), [(("I",), "I"), (("Sm",), "Sm"), (("NoSuchExtension",), "empty")]
)
def test_entire_parameter_ascii_table(builders, extensions, label):
    assert builders["_"].parameters(extensions).render().encode() == native(
        f"list-parameters-{label}-ascii"
    )


@pytest.mark.parametrize("extension", ["I", "Sm"])
@pytest.mark.parametrize("output_format", ["yaml", "json"])
def test_all_parameter_fields_and_order_in_both_serializations(builders, extension, output_format):
    report = builders["_"].parameters([extension])
    loader = json.loads if output_format == "json" else YAML(typ="safe").load
    expected = loader(native(f"list-parameters-{extension}-{output_format}"))
    assert report.to_data() == expected
    assert loader(report.render(output_format)) == expected
    assert all(list(row) == ["name", "exts", "description"] for row in report.to_data())


@pytest.mark.parametrize(("config", "label"), [("_", "all"), ("full", "full")])
def test_entire_unfiltered_parameter_rows_and_known_value_order(builders, config, label):
    expected = json.loads(native(f"list-parameters-{label}-json"))
    observations = json.loads((FIXTURES / "native-description-observations.json").read_text())
    corrected = []
    for row in expected:
        if row["name"] in observations:
            observation = observations[row["name"]]
            assert row["description"] == observation["psych_native_resolved_description"]
            row["description"] = observation["psych_source_description"]
            corrected.append(row["name"])
    assert len(corrected) == (9 if config == "_" else 2)
    assert builders[config].parameters().to_data() == expected


def test_native_source_parser_proves_all_nine_description_corrections(database):
    observations = json.loads((FIXTURES / "native-description-observations.json").read_text())
    assert len(observations) == 9
    for name, observation in observations.items():
        path = ROOT / f"spec/std/isa/param/{name}.yaml"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == observation["source_sha256"]
        assert (
            observation["psych_source_description"]
            == database.get("parameter", name)["description"]
        )
        assert (
            observation["psych_native_resolved_description"]
            != observation["psych_source_description"]
        )


def test_show_parameter_preserves_all_nine_source_description_newlines(builders):
    observations = json.loads((FIXTURES / "native-description-observations.json").read_text())
    assert len(observations) == 9
    for name, observation in observations.items():
        report = builders["_"].parameter(name)
        assert report.description == observation["psych_source_description"]
        source_render = render_parameter(report, name)
        native_render = replace(
            report, description=observation["psych_native_resolved_description"]
        ).render()
        assert source_render == native_render.replace(" \n\n  Value:", "\n    \n\n  Value:", 1)
        assert len(source_render.encode()) == len(native_render.encode()) + 4


@pytest.mark.parametrize(
    ("name", "encoding", "config"),
    [
        ("addi", "fff10093", "_"),
        ("compressed", "0001", "_"),
        ("xlen-dependent", "2081", "_"),
        ("rv64-only", "00003003", "_"),
        ("illegal", "ffffffff", "_"),
        ("zero", "0", "_"),
        ("overwide", "100000013", "_"),
        ("rv32", "00003003", "rv32"),
        ("rv64", "00003003", "rv64"),
        ("full-catalog", "00003003", "full"),
    ],
)
def test_entire_fixed_bit_disassembly_corpus(matchers, name, encoding, config):
    assert matchers[config].match(encoding).render().encode() == native(f"disasm-{name}")


def test_custom_overlay_ambiguity_and_rv32_structural_filter():
    database = Database.bundled().resolve(overlays=[FIXTURES / "overlay"])
    for label, configuration in [
        ("ambiguous", Configuration.builtin("_")),
        ("rv32", Configuration.builtin("rv32")),
    ]:
        report = InstructionMatcher(database.configure(configuration)).match("13")
        assert report.render().encode() == native(f"disasm-custom-{label}")
    assert report.results[0].matches[0].name == "addi"


def test_real_module_cli_config_declared_overlay_native_output(capsys):
    assert (
        main(
            [
                "disasm",
                "13",
                "--config",
                str(FIXTURES / "custom.yaml"),
                "--arch-overlay",
                str(FIXTURES),
            ]
        )
        == 0
    )
    streams = capsys.readouterr()
    assert streams.out.encode() == native("disasm-custom-ambiguous")
    assert streams.err == ""


def test_real_addi_variable_extraction_and_compressed_descriptor_width(matchers):
    match = matchers["_"].match("fff10093", width=32).results[0].matches[0]
    assert match.name == "addi"
    assert [
        (field.name, field.encoded_value, field.value, field.width) for field in match.variables
    ] == [
        ("imm", 4095, -1, 12),
        ("xs1", 2, 2, 5),
        ("xd", 1, 1, 5),
    ]
    report = matchers["_"].match("0001", width=16)
    assert report.results[0].ambiguous
    assert [(match.name, match.length) for match in report.results[0].matches] == [
        ("c.addi", 16),
        ("c.nop", 16),
    ]
    assert matchers["_"].match("0001", width=32).results[0].illegal


def test_possible_filter_changes_catalog_selection_without_changing_legacy_default(matchers):
    assert [item.name for item in matchers["full"].match("00003003").results[0].matches] == ["ld"]
    # The full RV32 fixture omits Zilsd; ld is still in the legacy catalog
    # but cannot be selected as an instruction of that configured processor.
    assert matchers["full"].match("00003003", selection="possible").results[0].illegal
    assert [
        item.name for item in matchers["full"].match("13", selection="mandatory").results[0].matches
    ] == ["addi"]


def test_all_271_parameter_detail_shapes_are_supported(builders):
    builder = builders["_"]
    for parameter in builder.database.objects("parameter"):
        report = builder.parameter(parameter.name)
        assert report.name == parameter.name
        assert isinstance(report.description, str)
        assert isinstance(report.schema_description, str)
        assert report.render().startswith(parameter.name + "\n\n")
