# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import io
import os
import subprocess
from pathlib import Path

import pytest
from test_query_matching import small_database

from udb import Configuration
from udb.cli import main as udb_main
from udb.query_reports import InstructionMatcher, ReportError
from udb.query_reports.cli import build_parser, load_architecture, main, write_report

FIXTURES = Path(__file__).parent / "fixtures/query_reports"
ROOT = Path(__file__).parents[2]


def test_main_parsing_dispatch_output_file_and_semantics(monkeypatch, capsys, tmp_path):
    arch = small_database().configure(Configuration.builtin("_"))
    monkeypatch.setattr("udb.query_reports.cli.load_architecture", lambda args: arch)
    assert main(["disasm", "1", "--width", "16"]) == 0
    assert capsys.readouterr().out == InstructionMatcher(arch).match(1, width=16).render()
    assert main(["show", "parameter", "missing"]) == 0
    assert capsys.readouterr().out == "Could not find parameter named missing\n"
    output = tmp_path / "names.txt"
    assert main(["list", "extensions", "-o", str(output)]) == 0
    assert output.read_bytes() == b"I\nX\n"
    assert main(["list", "parameters", "-e", "NoSuchExtension", "-f", "json"]) == 0
    assert capsys.readouterr().out == "[]\n"


def test_native_error_messages_and_output_truncation(capsys, tmp_path):
    output = tmp_path / "output.txt"
    output.write_text("previous")
    assert main(["list", "extensions", "--config", "missing", "-o", str(output)]) == 1
    assert capsys.readouterr().err == "Cannot find config: missing\n"
    assert output.read_bytes() == b""
    assert main(["disasm", " 13"]) == 1
    assert capsys.readouterr().err == (FIXTURES / "disasm-malformed.stderr.txt").read_text()
    assert main(["disasm", "0xz", "--arch", str(output)]) == 1
    assert capsys.readouterr().err == f"Arch directory does not exist: {output}\n"


def test_no_implicit_config_overlay_fallback(capsys):
    assert main(["disasm", "13", "--config", str(FIXTURES / "custom.yaml")]) == 1
    assert (
        capsys.readouterr().err
        == "config declares arch_overlay; supply --arch-overlay or explicit --overlay\n"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["list", "parameters", "--output-format", "csv"],
        ["show", "extension"],
        ["disasm", "13", "--width", "64"],
        ["disasm", "13", "--schemas", "ignored"],
    ],
)
def test_grammar_errors_exit_two(argv):
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2


def test_legacy_flags_and_array_grammar():
    args = build_parser().parse_args(
        [
            "list",
            "parameters",
            "--arch",
            "isa",
            "--arch_overlay",
            "custom",
            "--config_dir",
            "configs",
            "--gen",
            "unused",
            "--output_format",
            "json",
            "-e",
            "A",
            "B,C",
        ]
    )
    assert args.path == Path("isa")
    assert args.arch_overlay == Path("custom") and args.config_dir == Path("configs")
    assert args.extensions == ["A", "B,C"]


def test_config_dir_has_no_builtin_fallback(tmp_path):
    args = build_parser().parse_args(
        ["list", "extensions", "--config", "_", "--config-dir", str(tmp_path)]
    )
    with pytest.raises(ReportError, match="Cannot find config"):
        load_architecture(args)


def test_explicit_real_tree_requires_and_accepts_schemas(capsys):
    arch = ROOT / "spec/std/isa"
    assert main(["show", "parameter", "ARCH_ID_VALUE", "--arch", str(arch)]) == 1
    assert capsys.readouterr().err == "Explicit --path/--arch requires --schemas\n"

    assert (
        main(
            [
                "show",
                "parameter",
                "ARCH_ID_VALUE",
                "--path",
                str(arch),
                "--schemas",
                str(ROOT / "spec/schemas"),
            ]
        )
        == 0
    )
    assert (
        capsys.readouterr().out.encode()
        == (FIXTURES / "show-parameter-ARCH_ID_VALUE.stdout.txt").read_bytes()
    )


def test_installed_cli_candidate_routes_reports_and_disassembly(capsys):
    assert udb_main(["inspect", "extension", "I"]) == 0
    assert (
        capsys.readouterr().out.encode() == (FIXTURES / "show-extension-I.stdout.txt").read_bytes()
    )
    assert udb_main(["disasm", "fff10093", "--width", "32"]) == 0
    assert capsys.readouterr().out.encode() == (FIXTURES / "disasm-addi.stdout.txt").read_bytes()


def test_repository_wrapper_routes_queries_and_supplies_schemas():
    environment = os.environ.copy()
    environment["UV_NO_SYNC"] = "1"
    environment["RUBYOPT"] = "--query-reports-must-not-use-ruby"
    result = subprocess.run(
        [
            str(ROOT / "bin/udb"),
            "show",
            "parameter",
            "ARCH_ID_VALUE",
            "--arch",
            str(ROOT / "spec/std/isa"),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == (FIXTURES / "show-parameter-ARCH_ID_VALUE.stdout.txt").read_bytes()
    assert result.stderr == b""


def test_writer_short_writes_utf8_and_no_progress():
    class Short(io.BytesIO):
        def write(self, data):
            return super().write(data[:2])

    stream = Short()
    write_report("≠\n", stream)
    assert stream.getvalue() == "≠\n".encode()

    class NoProgress(io.BytesIO):
        def write(self, data):
            return 0

    with pytest.raises(OSError, match="complete report"):
        write_report("abc", NoProgress())


def test_output_errors_return_one_without_replacement(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "udb.query_reports.cli.load_architecture",
        lambda args: small_database().configure(Configuration.builtin("_")),
    )
    assert main(["list", "extensions", "-o", str(tmp_path / "missing/child")]) == 1
    assert "No such file" in capsys.readouterr().err


def test_broken_pipe_is_reported_as_output_error(monkeypatch, capsys):
    class Broken(io.BytesIO):
        def write(self, data):
            raise BrokenPipeError("closed report consumer")

    class Stdout:
        buffer = Broken()

    monkeypatch.setattr(
        "udb.query_reports.cli.load_architecture",
        lambda args: small_database().configure(Configuration.builtin("_")),
    )
    with monkeypatch.context() as context:
        context.setattr("udb.query_reports.cli.sys.stdout", Stdout())
        assert main(["list", "extensions"]) == 1
    assert capsys.readouterr().err == "closed report consumer\n"
