# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest

from udb import Database, SchemaError, SchemaStore
from udb.cli import main


def write_extension(root: Path, body: str) -> None:
    path = root / "ext" / "Demo.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def write_extension_schema(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "v0.1",
        "type": "object",
        "required": ["$schema", "kind", "name", "count"],
        "properties": {
            "$schema": {"const": "demo_schema.json#"},
            "kind": {"const": "extension"},
            "name": {"const": "Demo"},
            "count": {"type": "integer", "minimum": 1},
            "enabled": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    }
    (root / "demo_schema.json").write_text(json.dumps(schema), encoding="utf-8")


def valid_extension() -> str:
    return """\
$schema: demo_schema.json#
kind: extension
name: Demo
count: 1
"""


def test_bundled_database_resolves_and_validates_every_document() -> None:
    source = Database.bundled()
    source_paths = {record.path.as_posix() for record in source.objects()}
    resolved = source.resolve(validate=True)

    assert resolved.is_resolved is True
    assert source_paths
    assert set(resolved.documents) == source_paths


def test_validation_is_opt_in_and_requires_schemas_and_declarations(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_extension(source, "kind: extension\nname: Demo\n")

    resolved = Database.from_path(source).resolve()

    assert resolved.extension("Demo").name == "Demo"
    with pytest.raises(SchemaError, match="no schema directory"):
        resolved.validate()

    schemas = tmp_path / "schemas"
    write_extension_schema(schemas)
    resolved_with_schemas = Database.from_path(source, schemas_path=schemas).resolve()
    with pytest.raises(SchemaError, match=r"ext/Demo\.yaml.*missing.*\$schema"):
        resolved_with_schemas.validate()


def test_validation_preserves_documents_and_does_not_apply_defaults(tmp_path: Path) -> None:
    source = tmp_path / "source"
    schemas = tmp_path / "schemas"
    write_extension(source, valid_extension())
    write_extension_schema(schemas)
    resolved = Database.from_path(source, schemas_path=schemas).resolve()
    original = resolved.extension("Demo").to_dict()

    assert resolved.resolve(validate=True) is resolved

    document = resolved.extension("Demo").to_dict()
    assert document == original
    assert document["$schema"] == "demo_schema.json#"
    assert "enabled" not in document
    assert SchemaStore(schemas).versioned_uri(document["$schema"]) == "v0.1/demo_schema.json#"


def test_invalid_overlay_reports_the_resolved_source_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    schemas = tmp_path / "schemas"
    overlay = tmp_path / "overlay"
    write_extension(source, valid_extension())
    write_extension_schema(schemas)
    write_extension(overlay, "count: 0\n")

    database = Database.from_path(source, schemas_path=schemas)
    with pytest.raises(SchemaError, match=r"ext/Demo\.yaml.*\$\.count"):
        database.resolve(overlays=(overlay,), validate=True)

    assert database.extension("Demo")["count"] == 1


def test_cli_validation_contract_and_custom_schema_root(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    schemas = tmp_path / "schemas"
    write_extension(source, valid_extension())
    write_extension_schema(schemas)

    assert (
        main(
            [
                "--database",
                str(source),
                "--schema-dir",
                str(schemas),
                "validate",
                "data",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--database",
                str(source),
                "--schema-dir",
                str(schemas),
                "show",
                "extension",
                "Demo",
            ]
        )
        == 0
    )
    assert '"name": "Demo"' in capsys.readouterr().out


def test_cli_custom_validation_without_schemas_is_a_clear_error(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    write_extension(source, valid_extension())

    assert main(["--database", str(source), "validate", "data"]) == 2
    stderr = capsys.readouterr().err
    assert "no schema directory" in stderr
    assert "Traceback" not in stderr
