# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from udb import Configuration, Database, ResolvedDatabase
from udb.cli import main
from udb.generators.config_headers import ConfigHeaderError, generate_config_header
from udb.serialization import dumps_json

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "cfgs/mc100-32-full-example.yaml"
GOLDEN = ROOT / "tests/golden/mc100-32-full-example.golden"
FIXTURES = Path(__file__).with_name("fixtures") / "config_headers"


def configured(params=None, *, versions=None, name="Header -- demo"):
    values = {"MXLEN": 32, **(params or {})}
    extensions = versions if versions is not None else [["Xdemo", "1.0"]]

    def schema(value):
        kinds = {bool: "boolean", int: "integer", str: "string"}
        if isinstance(value, list):
            return {
                "type": "array",
                "items": {"type": kinds[type(value[0])] if value else "boolean"},
                "minItems": len(value),
                "maxItems": len(value),
            }
        return {"type": kinds[type(value)]}

    documents = {
        "ext/Xdemo.yaml": {
            "kind": "extension",
            "name": "Xdemo",
            "versions": [{"version": "1.0.0", "state": "ratified"}],
        },
        **{
            f"param/{key}.yaml": {
                "kind": "parameter",
                "name": key,
                "definedBy": True,
                "schema": schema(value),
            }
            for key, value in values.items()
        },
    }
    return ResolvedDatabase(documents).configure(
        Configuration(
            {
                "$schema": "config_schema.json#",
                "kind": "architecture configuration",
                "type": "fully configured",
                "name": name,
                "description": "A focused header fixture",
                "implemented_extensions": extensions,
                "params": values,
            }
        )
    )


@pytest.fixture(scope="module")
def full_architecture():
    return (
        Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas")
        .resolve()
        .configure(Configuration.from_file(CONFIG))
    )


@pytest.mark.parametrize("language,extension", [("c", "h"), ("svh", "svh")])
def test_full_configuration_matches_unchanged_golden(full_architecture, language, extension):
    actual = generate_config_header(full_architecture, language)
    assert actual.encode() == Path(f"{GOLDEN}.{extension}").read_bytes()


@pytest.mark.parametrize("language,directive", [("c", "#define"), ("svh", "`define")])
def test_parameter_macros(language, directive):
    architecture = configured(
        {
            "TRUE": True,
            "FALSE": False,
            "ZERO": 0,
            "STR": " __ Mixed---case / value __ ",
            "EMPTY_STR": "___",
            "DIGIT_STR": "32-bit",
            "BOOLS": [False, True, False, True],
            "INTS": [10, 2, 10, 0],
            "STRINGS": ["z!", "a b", "A--B", "z"],
            "EMPTY": [],
            "UNEVALUATED": "<%= MXLEN %>",
        }
    )
    output = generate_config_header(architecture, language)
    section = output.split("Configuration parameters")[1]
    macros = [line for line in section.splitlines() if line.startswith(directive + " ")]
    zero = "0" if language == "c" else "32'h0"
    width = "32" if language == "c" else "32'h20"
    assert macros == [
        f"{directive} UDB_BOOLS_1",
        f"{directive} UDB_BOOLS_3",
        f"{directive} UDB_DIGIT_STR_32_BIT",
        f"{directive} UDB_EMPTY_STR_",
        f"{directive} UDB_INTS_0",
        f"{directive} UDB_INTS_2",
        f"{directive} UDB_INTS_10",
        f"{directive} UDB_MXLEN {width}",
        f"{directive} UDB_MXLEN_32",
        f"{directive} UDB_STR_MIXED_CASE_VALUE",
        f"{directive} UDB_STRINGS_A_B",
        f"{directive} UDB_STRINGS_Z",
        f"{directive} UDB_TRUE",
        f"{directive} UDB_UNEVALUATED_MXLEN",
        f"{directive} UDB_ZERO {zero}",
        f"{directive} UDB_ZERO_0",
    ]


@pytest.mark.parametrize(
    "value,literal",
    [
        (0, "32'h0"),
        (1, "32'h1"),
        (2**31, "32'h80000000"),
        (2**32 - 1, "32'hFFFFFFFF"),
        (2**32, "64'h100000000"),
        (2**64 - 1, "64'hFFFFFFFFFFFFFFFF"),
        (2**64, "96'h10000000000000000"),
        (2**96, "128'h1000000000000000000000000"),
    ],
)
def test_svh_width_is_unsigned_and_rounded_to_32(value, literal):
    output = generate_config_header(configured({"VALUE": value}), "svh")
    assert f"`define UDB_VALUE {literal}\n" in output
    assert f"`define UDB_VALUE_{value}\n" in output
    assert f"#define UDB_VALUE {value}\n" in generate_config_header(
        configured({"VALUE": value}), "c"
    )


@pytest.mark.parametrize("version,macro", [("1", "1"), ("1.0", "1P0"), ("1.0.0", "1P0P0")])
def test_version_precision_is_the_input_not_catalog_or_canonical_requirement(version, macro):
    output = generate_config_header(configured(versions=[["Xdemo", version]]), "c")
    assert f"#define XDEMO{macro}_SUPPORTED\n" in output
    assert output.count("XDEMO_SUPPORTED\n") == 1


@pytest.mark.parametrize("language", ["c", "svh"])
def test_prerelease_version_macro_is_explicitly_unsupported(language):
    architecture = configured()
    documents = {key: dict(value) for key, value in architecture.database.documents.items()}
    documents["ext/Xdemo.yaml"]["versions"] = [{"version": "1.0.0-pre", "state": "development"}]
    data = architecture.configuration.to_dict()
    data["implemented_extensions"] = [["Xdemo", "1.0.0-pre"]]
    architecture = ResolvedDatabase(documents).configure(Configuration(data))
    assert architecture.check().valid
    with pytest.raises(ConfigHeaderError, match="XDEMO1P0P0-PRE_SUPPORTED"):
        generate_config_header(architecture, language)


@pytest.mark.parametrize("language", ["c", "svh"])
@pytest.mark.parametrize("name", ["Header\nname", "Header\rname", "Header*/name"])
def test_unsafe_config_name_cannot_escape_the_header_comment(language, name):
    with pytest.raises(ConfigHeaderError, match="name cannot be represented in a header comment"):
        generate_config_header(configured(name=name), language)


def test_extensions_are_explicit_case_insensitive_sorted_and_exact():
    architecture = configured()
    documents = {key: dict(value) for key, value in architecture.database.documents.items()}
    documents["ext/Xalpha.yaml"] = {
        "kind": "extension",
        "name": "Xalpha",
        "versions": [{"version": "2.0"}],
    }
    data = architecture.configuration.to_dict()
    data["implemented_extensions"] = [["Xdemo", "1.0.0"], ["Xalpha", "= 2.0"]]
    output = generate_config_header(ResolvedDatabase(documents).configure(Configuration(data)), "c")
    lines = output.split("/* Implemented extensions */\n")[1].split("\n\n")[0].splitlines()
    assert lines == [
        "#define XALPHA_SUPPORTED",
        "#define XALPHA2P0_SUPPORTED",
        "#define XDEMO_SUPPORTED",
        "#define XDEMO1P0P0_SUPPORTED",
    ]
    data["implemented_extensions"] = [["Xdemo", "99.0"]]
    with pytest.raises(ConfigHeaderError, match="no version matching"):
        generate_config_header(ResolvedDatabase(documents).configure(Configuration(data)), "c")


def test_guards_do_not_use_string_sanitization():
    output = generate_config_header(configured(), "c")
    assert "#ifndef UDB_CFG_HEADER____DEMO_H\n" in output
    assert output.endswith("#endif /* UDB_CFG_HEADER____DEMO_H */\n")


@pytest.mark.parametrize("name", ["_", "rv32", "rv64"])
def test_partial_and_unconfigured_are_explicitly_unsupported(name):
    architecture = ResolvedDatabase({}).configure(Configuration.builtin(name))
    with pytest.raises(ConfigHeaderError, match="Only fully configured configs are supported"):
        generate_config_header(architecture, "c")


@pytest.mark.parametrize(
    "params,message",
    [
        ({"BAD-NAME": 1}, "Unsupported parameter"),
        ({"NEGATIVE": -1}, "Unsupported macro"),
        ({"NEGATIVES": [-1]}, "Unsupported macro"),
        ({"MIXED": [True, 1]}, "outside its declared domain"),
        ({"VALUE": 1, "VALUE_1": True}, "macro collision"),
    ],
)
def test_unsupported_values_do_not_produce_invalid_source(params, message):
    with pytest.raises(ConfigHeaderError, match=message):
        generate_config_header(configured(params), "c")


def test_invalid_and_incomplete_configuration_are_errors(full_architecture):
    data = full_architecture.configuration.to_dict()
    del data["params"]["MTVAL_WIDTH"]
    with pytest.raises(ConfigHeaderError, match="omits defined parameter"):
        generate_config_header(full_architecture.database.configure(Configuration(data)), "c")
    data = full_architecture.configuration.to_dict()
    data["params"]["MTVAL_WIDTH"] = -1
    with pytest.raises(ConfigHeaderError, match="outside its declared domain"):
        generate_config_header(full_architecture.database.configure(Configuration(data)), "c")
    data = full_architecture.configuration.to_dict()
    data["implemented_extensions"].append({"name": "Xunknown", "version": "1.0"})
    with pytest.raises(ConfigHeaderError, match="unknown extension"):
        generate_config_header(full_architecture.database.configure(Configuration(data)), "c")
    documents = {key: dict(value) for key, value in configured().database.documents.items()}
    documents["ext/Xdemo.yaml"]["requirements"] = False
    with pytest.raises(ConfigHeaderError, match="unsat"):
        generate_config_header(
            ResolvedDatabase(documents).configure(configured().configuration), "c"
        )


def test_cli_stdout_and_file_are_identical(tmp_path, capsys):
    assert main(["generate", "config-c-header", "--config", str(CONFIG)]) == 0
    assert capsys.readouterr().out.encode() == Path(f"{GOLDEN}.h").read_bytes()
    output = tmp_path / "nested/config.svh"
    assert main(["generate", "config-sv-header", "--config", str(CONFIG), "-o", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert output.read_bytes() == Path(f"{GOLDEN}.svh").read_bytes()


@pytest.fixture
def encoding_cli_inputs(tmp_path):
    architecture = configured(name="MC100-Ünï")
    source = tmp_path / "isa"
    for name, document in architecture.database.documents.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dumps_json(document).encode("utf-8"))
    config = tmp_path / "unicode.yaml"
    config.write_bytes(dumps_json(architecture.configuration.to_dict()).encode("utf-8"))
    return architecture, source, config


@pytest.mark.parametrize("language", ["c", "svh"])
def test_cli_utf8_lf_bytes_ignore_ascii_stdout_and_text_newlines(
    encoding_cli_inputs, language, monkeypatch, tmp_path
):
    architecture, source, config = encoding_cli_inputs
    expected = generate_config_header(architecture, language).encode("utf-8")
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="ascii", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", stdout)
    generator = "config-c-header" if language == "c" else "config-sv-header"
    args = ["--database", str(source), "generate", generator, "--config", str(config)]
    assert main(args) == 0
    assert buffer.getvalue() == expected
    output = tmp_path / "nested" / f"unicode.{language}"
    assert main([*args, "-o", str(output)]) == 0
    assert output.read_bytes() == expected
    assert b"\r\n" not in expected


@pytest.mark.parametrize("language", ["c", "svh"])
def test_cli_utf8_subprocess_succeeds_with_pythonioencoding_ascii(
    encoding_cli_inputs, language, tmp_path
):
    architecture, source, config = encoding_cli_inputs
    expected = generate_config_header(architecture, language).encode("utf-8")
    args = [
        sys.executable,
        "-m",
        "udb",
        "--database",
        str(source),
        "generate",
        "config-c-header" if language == "c" else "config-sv-header",
        "--config",
        str(config),
    ]
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    stdout = subprocess.run(args, env=env, cwd=ROOT, capture_output=True, check=False)
    assert stdout.returncode == 0, stdout.stderr
    assert stdout.stdout == expected and stdout.stderr == b""
    output = tmp_path / f"unicode.{language}"
    written = subprocess.run(
        [*args, "--output", str(output)], env=env, cwd=ROOT, capture_output=True, check=False
    )
    assert written.returncode == 0, written.stderr
    assert written.stdout == written.stderr == b""
    assert output.read_bytes() == expected


@pytest.mark.parametrize("failure", [BrokenPipeError, OSError])
def test_cli_stdout_io_error_has_explicit_exit_two(
    encoding_cli_inputs, failure, monkeypatch, capsys
):
    _, source, config = encoding_cli_inputs

    class FailedStream:
        def write(self, data):
            raise failure("intentional stdout failure")

    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=FailedStream()))
    assert main(["--database", str(source), "generate", "config-c-header", "-c", str(config)]) == 2
    assert "stdout: cannot write header: intentional stdout failure" in capsys.readouterr().err


def test_cli_stdout_short_binary_writes_preserve_complete_utf8(encoding_cli_inputs, monkeypatch):
    architecture, source, config = encoding_cli_inputs

    class ShortStream(io.BytesIO):
        def write(self, data):
            return super().write(data[:7])

    stream = ShortStream()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stream))
    assert main(["--database", str(source), "generate", "config-c-header", "-c", str(config)]) == 0
    assert stream.getvalue() == generate_config_header(architecture, "c").encode("utf-8")


def test_cli_stdout_incomplete_binary_write_is_an_explicit_error(
    encoding_cli_inputs, monkeypatch, capsys
):
    _, source, config = encoding_cli_inputs
    stream = SimpleNamespace(write=lambda data: 0)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stream))
    assert main(["--database", str(source), "generate", "config-c-header", "-c", str(config)]) == 2
    assert "stdout did not accept the complete header" in capsys.readouterr().err


def test_cli_closed_pipe_does_not_retry_at_shutdown(encoding_cli_inputs):
    _, source, config = encoding_cli_inputs
    reader, writer = os.pipe()
    os.close(reader)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "udb",
                "--database",
                str(source),
                "generate",
                "config-c-header",
                "-c",
                str(config),
            ],
            cwd=ROOT,
            stdout=writer,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        os.close(writer)
    assert result.returncode == 2
    assert b"stdout: cannot write header" in result.stderr
    assert b"Traceback" not in result.stderr
    assert b"Exception ignored" not in result.stderr


def test_cli_failure_does_not_write_or_implicitly_lookup_repository(tmp_path, capsys):
    output = tmp_path / "nested/config.h"
    assert main(["generate", "config-c-header", "-o", str(output)]) == 2
    assert "not fully configured" in capsys.readouterr().err
    assert not output.parent.exists()
    assert main(["generate", "config-c-header", "-c", "mc100-32-full-example"]) == 2
    assert "cannot read configuration" in capsys.readouterr().err
    assert main(["generate", "config-c-header", "-c", "cfgs/nonexistent.yaml"]) == 2
    assert capsys.readouterr().out == ""


def test_explicit_custom_database_has_no_bundled_fallback(tmp_path, capsys):
    architecture = configured({"VALUE": 7})
    source = tmp_path / "isa"
    for name, document in architecture.database.documents.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_json(document))
    config = tmp_path / "custom.yaml"
    config.write_text(json.dumps(architecture.configuration.to_dict()))
    expected = generate_config_header(architecture, "c")
    assert main(["--database", str(source), "generate", "config-c-header", "-c", str(config)]) == 0
    assert capsys.readouterr().out == expected
    assert main(["generate", "config-c-header", "-c", str(config)]) == 2
    assert "unknown extension" in capsys.readouterr().err
    assert (
        main(
            [
                "--database",
                str(tmp_path / "missing"),
                "generate",
                "config-c-header",
                "-c",
                str(config),
            ]
        )
        == 2
    )
    assert "Error:" in capsys.readouterr().err


def test_cli_overlay_and_output_errors_are_explicit(tmp_path, capsys):
    architecture = configured()
    source = tmp_path / "isa"
    for name, document in architecture.database.documents.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_json(document))
    overlay = tmp_path / "overlay"
    (overlay / "ext").mkdir(parents=True)
    (overlay / "ext/Xdemo.yaml").write_text(json.dumps({"requirements": False}))
    config = tmp_path / "custom.yaml"
    config.write_text(json.dumps(architecture.configuration.to_dict()))
    assert (
        main(
            [
                "--database",
                str(source),
                "--overlay",
                str(overlay),
                "generate",
                "config-c-header",
                "-c",
                str(config),
            ]
        )
        == 2
    )
    assert "unsat" in capsys.readouterr().err
    assert (
        main(
            [
                "--database",
                str(source),
                "generate",
                "config-c-header",
                "-c",
                str(config),
                "-o",
                str(source),
            ]
        )
        == 2
    )
    assert "cannot write header" in capsys.readouterr().err


def test_snapshot_generation_does_not_reopen_source(tmp_path):
    original = configured()
    source = tmp_path / "isa"
    for name, document in original.database.documents.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_json(document))
    architecture = Database.from_path(source).resolve().configure(original.configuration)
    expected = generate_config_header(architecture, "svh")
    shutil.rmtree(source)
    assert generate_config_header(architecture, "svh") == expected
    assert architecture.configuration.params == {"MXLEN": 32}


@pytest.mark.parametrize("language,extension", [("c", "h"), ("svh", "svh")])
def test_frozen_ruby_parameter_artifact(language, extension):
    data = json.loads((FIXTURES / "values.json").read_text())
    architecture = configured(data["params"], name=data["name"], versions=[])
    assert (
        generate_config_header(architecture, language).encode()
        == (FIXTURES / f"values.{extension}").read_bytes()
    )


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
@pytest.mark.parametrize("language,extension", [("c", "h"), ("svh", "svh")])
def test_live_ruby_parameter_artifact(language, extension):
    result = subprocess.run(
        [
            "mise",
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            f"-I{ROOT / 'tools/ruby-gems/udb/lib'}",
            f"-I{ROOT / 'tools/ruby-gems/udb-gen/lib'}",
            str(Path(__file__).with_name("ruby_config_headers_oracle.rb")),
            str(ROOT),
            language,
            str(FIXTURES / "values.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    assert result.stdout == (FIXTURES / f"values.{extension}").read_bytes()


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
def test_live_ruby_invalid_macros_are_reproduced_and_explicitly_rejected(tmp_path):
    data = {"name": "Unsupported", "params": {"MXLEN": 32, "NEGATIVE": -1, "MIXED": [True, 1]}}
    path = tmp_path / "unsupported.json"
    path.write_text(json.dumps(data))
    result = subprocess.run(
        [
            "mise",
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            f"-I{ROOT / 'tools/ruby-gems/udb/lib'}",
            f"-I{ROOT / 'tools/ruby-gems/udb-gen/lib'}",
            str(Path(__file__).with_name("ruby_config_headers_oracle.rb")),
            str(ROOT),
            "svh",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    assert "`define UDB_NEGATIVE 32'h-1\n" in result.stdout
    assert "`define UDB_NEGATIVE_-1\n" in result.stdout
    assert "`define UDB_MIXED" not in result.stdout
    with pytest.raises(ConfigHeaderError, match="Unsupported macro"):
        generate_config_header(configured({"NEGATIVE": -1}), "svh")
    with pytest.raises(ConfigHeaderError, match="outside its declared domain"):
        generate_config_header(configured({"MIXED": [True, 1]}), "svh")


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
@pytest.mark.parametrize("configuration", ["_", "rv32", "rv64"])
def test_live_ruby_full_only_support_is_verified(configuration):
    result = subprocess.run(
        [
            "mise",
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            f"-I{ROOT / 'tools/ruby-gems/udb/lib'}",
            f"-I{ROOT / 'tools/ruby-gems/udb-gen/lib'}",
            str(Path(__file__).with_name("ruby_config_headers_oracle.rb")),
            str(ROOT),
            "c",
            configuration,
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert b"is not fully configured. Only fully configured configs are supported." in (
        result.stdout + result.stderr
    )
    assert b"#define " not in result.stdout


@pytest.mark.skipif(os.environ.get("UDB_TEST_RUBY") != "1", reason="live Ruby oracle is opt-in")
@pytest.mark.parametrize("language,extension", [("c", "h"), ("svh", "svh")])
def test_live_ruby_artifact_oracle(full_architecture, language, extension):
    result = subprocess.run(
        [
            "mise",
            "exec",
            "--no-deps",
            "--",
            "bundle",
            "exec",
            "ruby",
            f"-I{ROOT / 'tools/ruby-gems/udb/lib'}",
            f"-I{ROOT / 'tools/ruby-gems/udb-gen/lib'}",
            str(Path(__file__).with_name("ruby_config_headers_oracle.rb")),
            str(ROOT),
            language,
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    assert result.stdout == Path(f"{GOLDEN}.{extension}").read_bytes()
    assert result.stdout == generate_config_header(full_architecture, language).encode()


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_HEADER_TOOLS") != "1", reason="native source checks are opt-in"
)
def test_generated_sources_compile_and_lint(full_architecture, tmp_path):
    cc = shutil.which("gcc")
    verilator = shutil.which("verilator")
    assert cc is not None, "C header acceptance requires gcc"
    assert verilator is not None, "SV header acceptance requires verilator"
    (tmp_path / "config.h").write_text(generate_config_header(full_architecture, "c"))
    (tmp_path / "config.svh").write_text(generate_config_header(full_architecture, "svh"))
    c = tmp_path / "consumer.c"
    c.write_text(
        '#include "config.h"\n#include "config.h"\n'
        "#ifndef I2P1_SUPPORTED\n#error missing I version\n#endif\n"
        "#ifndef UDB_MTVEC_MODES_1\n#error missing array presence\n#endif\n"
        '_Static_assert(UDB_MXLEN == 32, "machine width");\n'
        "int main(void) { return UDB_ARCH_ID_VALUE != 1; }\n"
    )
    sv = tmp_path / "consumer.sv"
    sv.write_text(
        '`include "config.svh"\n`include "config.svh"\n'
        "module consumer;\n"
        "`ifndef I2P1_SUPPORTED\nmissing_extension_macro\n`endif\n"
        "localparam logic [31:0] XLEN = `UDB_MXLEN;\n"
        "initial begin\n"
        '  assert (XLEN == 32) else $fatal(1, "machine width");\n'
        "end\nendmodule\n"
    )
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-c",
            str(c),
            "-o",
            str(tmp_path / "consumer.o"),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [verilator, "--lint-only", "--top-module", "consumer", f"-I{tmp_path}", str(sv)],
        check=True,
        capture_output=True,
    )
    (tmp_path / "values.svh").write_bytes((FIXTURES / "values.svh").read_bytes())
    sv.write_text(
        '`include "values.svh"\n'
        "module consumer;\n"
        "localparam logic [127:0] LARGE = `UDB_U96_NEXT;\n"
        "initial begin\n"
        '  assert (LARGE == (128\'h1 << 96)) else $fatal(1, "wide value");\n'
        '  assert ($bits(`UDB_U32_MAX) == 32) else $fatal(1, "32-bit width");\n'
        '  assert ($bits(`UDB_U64_NEXT) == 96) else $fatal(1, "96-bit width");\n'
        "end\nendmodule\n"
    )
    subprocess.run(
        [verilator, "--lint-only", "--top-module", "consumer", f"-I{tmp_path}", str(sv)],
        check=True,
        capture_output=True,
    )
