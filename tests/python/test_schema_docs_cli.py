# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_schema_docs import ROOT, native_expected

from udb import cli

FIXTURES = ROOT / "tests/python/fixtures/schema_docs"


def test_schema_cli_uses_custom_schemas_without_loading_isa(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_isa(*args, **kwargs):
        pytest.fail("schema documentation must not load an ISA database")

    monkeypatch.setattr("udb.database.Database.bundled", no_isa)
    args = [
        "--schema-dir",
        str(FIXTURES / "custom-schemas"),
        "generate",
        "schema-docs",
        "--output",
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
    assert (tmp_path / "reference/config.mdx").read_bytes() == native_expected(
        (FIXTURES / "ruby-custom/single.mdx").read_bytes()
    )
    assert cli.main([*args, "--check"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unchanged"
    assert not (tmp_path / "index.mdx").exists()


def test_schema_cli_forwards_current_replacement_and_nonwriting_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "generate",
        "schema-docs",
        "--output",
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
    "global_args",
    [["--database", "missing"], ["--view", "raw"], ["--overlay", "missing"]],
)
def test_schema_cli_rejects_isa_options_before_writing(
    tmp_path: Path, global_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "output"
    assert cli.main([*global_args, "generate", "schema-docs", "--output", str(output)]) == 2
    assert "does not accept ISA database options" in capsys.readouterr().err
    assert not output.exists()


def test_schema_cli_io_failure_is_machine_readable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "not-directory"
    output.write_text("keep")
    assert cli.main(["generate", "schema-docs", "--output", str(output), "--diagnostics"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert output.read_text() == "keep"
