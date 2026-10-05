# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from udb.cli import main

FIXTURES = Path(__file__).parent / "fixtures/instruction_table"


@pytest.fixture
def table_inputs(tmp_path):
    source = tmp_path / "isa"
    inst = source / "inst" / "demo.yaml"
    inst.parent.mkdir(parents=True)
    data = {
        "kind": "instruction",
        "name": "demo",
        "encoding": {"match": "1--0", "variables": [{"name": "x", "location": "2-1"}]},
    }
    inst.write_text(json.dumps(data), encoding="utf-8")
    args = ["--path", str(source), "generate", "instruction-table"]
    return inst, data, args


def test_cli_complete_rv32_table_matches_unfiltered_ruby(capsys, tmp_path):
    assert main(["generate", "instruction-table", "--cfg", "rv32"]) == 0
    captured = capsys.readouterr()
    assert captured.out.encode() == (FIXTURES / "native-rv32-stdout.txt").read_bytes()
    assert captured.err == ""
    output = tmp_path / "test_table.txt"
    assert main(["generate", "instruction-table", "--out", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert output.read_bytes() == (FIXTURES / "legacy-all-file.txt").read_bytes()


def test_cli_custom_database_and_overlay(table_inputs, tmp_path, capsys):
    _, _, args = table_inputs
    assert main(args) == 0
    assert capsys.readouterr().out.endswith("demo common 1<3|0<0 x=2-1\n")
    overlay = tmp_path / "overlay/inst"
    overlay.mkdir(parents=True)
    (overlay / "demo.yaml").write_text('encoding:\n  match: "0--1"\n', encoding="utf-8")
    assert main(["--overlay", str(overlay.parent), *args]) == 0
    assert capsys.readouterr().out.endswith("demo common 0<3|1<0 x=2-1\n")


def test_cli_validates_before_overwriting_output(table_inputs, tmp_path, capsys):
    inst, data, args = table_inputs
    output = tmp_path / "table.txt"
    output.write_bytes(b"existing output\n")
    data["encoding"]["variables"][0]["location"] = "9-1"
    inst.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main([*args, "-o", str(output)])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "inst/demo.yaml" in captured.err and "location" in captured.err
    assert output.read_bytes() == b"existing output\n"


@pytest.mark.parametrize("destination", ["missing/table.txt", "."])
def test_cli_output_errors_do_not_create_parent(table_inputs, tmp_path, capsys, destination):
    _, _, args = table_inputs
    with pytest.raises(SystemExit) as error:
        main([*args, "-o", str(tmp_path / destination)])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "cannot write instruction table" in captured.err
    assert not (tmp_path / "missing").exists()


def test_cli_configuration_errors_are_explicit(table_inputs, tmp_path, capsys):
    _, _, args = table_inputs
    with pytest.raises(SystemExit) as error:
        main([*args, "--config", str(tmp_path / "missing.yaml")])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "cannot read configuration" in captured.err


@pytest.mark.parametrize("result", [0, None, BrokenPipeError("closed"), OSError("full")])
def test_cli_stdout_failures_exit_two(table_inputs, result, monkeypatch, capsys):
    _, _, args = table_inputs

    def write(data):
        if isinstance(result, OSError):
            raise result
        return result

    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=SimpleNamespace(write=write)))
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert "stdout: cannot write instruction table" in capsys.readouterr().err


def test_cli_short_writes_keep_complete_output(table_inputs, monkeypatch, capsys):
    _, _, args = table_inputs
    assert main(args) == 0
    expected = capsys.readouterr().out.encode()

    class ShortStream(io.BytesIO):
        def write(self, data):
            return super().write(data[:7])

    stream = ShortStream()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stream))
    assert main(args) == 0
    assert stream.getvalue() == expected


def test_cli_utf8_lf_ignores_text_encoding(table_inputs, monkeypatch, tmp_path):
    inst, data, args = table_inputs
    data["name"] = "d\u00e9mo"
    inst.write_text(json.dumps(data), encoding="utf-8")
    inst.rename(inst.with_name("d\u00e9mo.yaml"))
    output = tmp_path / "table.txt"
    assert main([*args, "-o", str(output)]) == 0
    expected = output.read_bytes().replace(b" -o table.txt", b"")
    buffer = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buffer, encoding="ascii", newline="\r\n"))
    assert main(args) == 0
    assert buffer.getvalue() == expected
    assert "d\u00e9mo common".encode() in expected
    assert b"\r\n" not in expected


def test_cli_closed_pipe_does_not_retry_at_shutdown(table_inputs):
    _, _, args = table_inputs
    reader, writer = os.pipe()
    os.close(reader)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "udb", *args],
            stdout=writer,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        os.close(writer)
    assert result.returncode == 2
    assert b"stdout: cannot write instruction table" in result.stderr
    assert b"Traceback" not in result.stderr and b"Exception ignored" not in result.stderr
