# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_schema_docs import ROOT

from udb import cli

FIXTURES = ROOT / "tests/python/fixtures/schema_docs"


def test_schema_cli_uses_custom_schemas_without_loading_isa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_isa(*args, **kwargs):
        pytest.fail("schema documentation must not load an ISA database")

    monkeypatch.setattr(cli.Database, "bundled", no_isa)
    args = [
        "generate",
        "schema-docs",
        "--schemas",
        str(FIXTURES / "custom-schemas"),
        "--out",
        str(tmp_path),
        "--schema",
        "config_schema.json",
        "--no-index",
        "--output-file",
        "reference/config.mdx",
        "--diagnostics",
    ]
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "generated"
    assert result["paths"] == ["reference/config.mdx"]
    assert (tmp_path / "reference/config.mdx").read_bytes() == (
        FIXTURES / "ruby-custom/single.mdx"
    ).read_bytes()
    assert cli.main([*args, "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unchanged"
    assert not (tmp_path / "index.mdx").exists()


def test_schema_cli_forwards_current_replacement_and_nonwriting_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "generate",
        "schema-docs",
        "--out",
        str(tmp_path),
        "--schema",
        "config_schema.json",
        "--no-index",
        "--diagnostics",
    ]
    assert cli.main(args) == 0
    capsys.readouterr()
    page = tmp_path / "v0.1/config_schema.mdx"
    native = page.read_bytes()
    page.chmod(0o644)
    page.write_bytes(b"drift\n")
    assert cli.main([*args, "--check"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "drift"
    assert page.read_bytes() == b"drift\n"
    assert cli.main(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    assert page.read_bytes() == b"drift\n"
    assert cli.main([*args, "--replace-current"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "generated"
    assert page.read_bytes() == native


@pytest.mark.parametrize(
    "global_args", [["--path", "missing"], ["--resolved"], ["--overlay", "missing"], ["--validate"]]
)
def test_schema_cli_rejects_isa_options_before_writing(
    tmp_path: Path, global_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "output"
    with pytest.raises(SystemExit) as error:
        cli.main([*global_args, "generate", "schema-docs", "--out", str(output)])
    assert error.value.code == 2
    assert "not ISA options" in capsys.readouterr().err
    assert not output.exists()


def test_schema_cli_io_failure_is_machine_readable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "not-directory"
    output.write_text("keep")
    assert cli.main(["generate", "schema-docs", "--out", str(output), "--diagnostics"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert output.read_text() == "keep"


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize("state", ["clean", "drift", "invalid"])
def test_repository_chore_preserves_generator_exit_and_check_behavior(
    tmp_path: Path, check: bool, state: str
) -> None:
    (tmp_path / "bin").mkdir()
    shutil.copyfile(ROOT / "bin/chore", tmp_path / "bin/chore")
    python = tmp_path / "bin/python"
    python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
    python.chmod(0o755)
    shutil.copytree(FIXTURES / "custom-schemas", tmp_path / "spec/schemas")
    output = tmp_path / "doc/docs/schemas"
    shutil.copytree(FIXTURES / "ruby-custom/all", output)
    page = output / "v0.2/config_schema.mdx"
    native = page.read_bytes()
    if state == "drift":
        page.write_bytes(b"drift\n")
    elif state == "invalid":
        (tmp_path / "spec/schemas/config_schema.json").write_text("{invalid")
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    command = ["bash", str(tmp_path / "bin/chore"), "gen"]
    if check:
        command.append("-f")
    command.append("schema-docs")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        command, cwd=tmp_path, env=environment, capture_output=True, text=True, check=False
    )
    expected = 2 if state == "invalid" else 1 if check and state == "drift" else 0
    assert result.returncode == expected, result.stdout + result.stderr
    if check or state == "invalid":
        assert {
            path.relative_to(output): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        } == before
    else:
        assert page.read_bytes() == native
