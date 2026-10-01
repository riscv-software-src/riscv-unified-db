# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Regression tests for the independently located review findings."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from test_schema_docs import DIALECT, ROOT, load_docs, write_schema

from udb.schema_docs import SchemaDocsError, SchemaDocsProjectionWarning, SchemaDocumentation
from udb.schema_docs.__main__ import main


def test_native_fixture_bytes_are_protected_from_formatting_hooks():
    directory = "tests/python/fixtures/schema_docs"
    config = YAML(typ="safe").load(ROOT / ".pre-commit-config.yaml")
    fixers = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] in {"end-of-file-fixer", "trailing-whitespace", "mixed-line-ending"}
    }
    assert len(fixers) == 3
    for hook in fixers.values():
        for path in (ROOT / directory).rglob("*"):
            if path.is_file():
                assert re.search(hook["exclude"], path.relative_to(ROOT).as_posix())
        assert not re.search(hook["exclude"], "src/udb/schema_docs/_render.py")
    assert directory in (ROOT / ".prettierignore").read_text().splitlines()


def test_all_suppressed_constraint_contexts_have_notices(tmp_path):
    store = write_schema(
        tmp_path / "schemas",
        properties={
            "null": {"type": "null"},
            "typed": {"type": "integer", "enum": [1, 1.5]},
            "a/b~c": {"type": "string", "title": "omitted", "pattern": "omitted"},
            "nested": {"type": "object", "$schema": DIALECT},
            "conjunctive": {
                "type": "string",
                "oneOf": [{"type": "integer", "description": "omitted"}],
            },
        },
        required=["null"],
    )
    docs = load_docs(tmp_path / "schemas")
    assert docs.schema_names == ("sample.json",)
    messages = {notice.pointer: notice.message for notice in docs.notices}
    for pointer in (
        "/properties/typed/type",
        "/properties/a~1b~0c/title",
        "/properties/a~1b~0c/pattern",
        "/properties/nested/$schema",
        "/properties/conjunctive/oneOf",
        "/properties/conjunctive/oneOf/0/type",
        "/properties/conjunctive/oneOf/0/description",
    ):
        assert pointer in messages
    assert "partially rendered" in messages["/required"]
    assert "partially rendered" in messages["/properties"]
    # Keep the caller's public store reusable, not mutated by notice collection.
    assert any(
        path.name == "sample.json"
        for path in store.resolved_schemas(base_url="https://schemas.udb.invalid")
    )


def test_typeless_root_does_not_silently_drop_its_properties(tmp_path):
    write_schema(tmp_path / "schemas", properties={"omitted": {"type": "string"}})
    schema = tmp_path / "schemas/sample.json"
    value = json.loads(schema.read_text())
    del value["type"]
    schema.write_text(json.dumps(value))
    docs = load_docs(tmp_path / "schemas")
    assert any(notice.pointer == "/properties" for notice in docs.notices)
    assert "omitted" not in docs.render("sample.json")


@pytest.mark.parametrize("path", ["reference/v0.1/page.mdx", "reference/v9.0/config_schema.mdx"])
def test_overrides_cannot_hide_inside_a_version_directory(tmp_path, path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    with pytest.raises(SchemaDocsError, match="canonical page"):
        docs.plan(tmp_path / "out", schema="sample.json", output_file=path)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("error", [BrokenPipeError("broken stdout"), OSError("short stdout")])
def test_cli_output_failures_are_explicit_without_secondary_traceback(
    tmp_path, monkeypatch, capsys, error
):
    monkeypatch.setattr(
        "udb.schema_docs.__main__._write_stdout",
        lambda text: (_ for _ in ()).throw(error),
    )
    with pytest.warns(SchemaDocsProjectionWarning):
        assert main(["--out", str(tmp_path / "out"), "--diagnostics"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "cannot write diagnostics to stdout" in output.err
    assert str(error) in output.err
    assert "Traceback" not in output.err


def test_stdout_writer_detects_short_binary_writes(monkeypatch):
    from udb.schema_docs.__main__ import _write_stdout

    class ShortWriter:
        buffer = None

        def write(self, payload):
            assert payload == "é\n".encode()
            return len(payload) - 1

    stream = ShortWriter()
    stream.buffer = stream
    monkeypatch.setattr("sys.stdout", stream)
    with pytest.raises(OSError, match="short write"):
        _write_stdout("é\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["--schema", "missing.json", "--diagnostics"],
        ["--schema", "config_schema.json"],
    ],
)
def test_actual_closed_stdout_pipe_returns_two_without_shutdown_retry(tmp_path, arguments):
    read, write = os.pipe()
    os.close(read)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "udb.schema_docs", "--out", str(tmp_path / "out"), *arguments],
            stdout=write,
            stderr=subprocess.PIPE,
            cwd=tmp_path,
            env={**os.environ, "PATH": "", "PYTHONPATH": str(ROOT / "src")},
            check=False,
        )
    finally:
        os.close(write)
    assert result.returncode == 2, result.stderr
    assert b"Broken pipe" in result.stderr
    assert b"Exception ignored" not in result.stderr
    assert b"Traceback" not in result.stderr


def test_distribution_notice_retains_all_derivation_licenses():
    notice = Path(__file__).resolve().parents[2] / "src/udb/schema_docs/NOTICE"
    text = notice.read_text()
    for attribution in ("Yukihiro Matsumoto", "Aaron Patterson", "Kirill Simonov", "Ingy"):
        assert attribution in text
    assert "BSD-2-Clause" in text
    assert "Permission is hereby granted" in text
    assert "THIS SOFTWARE IS PROVIDED" in text
