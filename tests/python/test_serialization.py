# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb import (
    Database,
    ResolvedDatabase,
    SchemaStore,
    SerializationError,
    dumps_json,
    dumps_yaml,
    write_config,
    write_resolved_schemas,
)
from udb.cli import main

REPOSITORY_ROOT = Path(__file__).parents[2]
RUBY_SCHEMA_ORACLE = Path(__file__).with_name("ruby_schema_serialization_oracle.rb")


def _write_schema(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "demo_schema.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "v1.2",
                "type": "object",
                "properties": {"name": {"type": "string"}},
            }
        ),
        encoding="utf-8",
    )
    (root / "json-schema-draft-07.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "http://json-schema.org/draft-07/schema#",
                "type": ["object", "boolean"],
            }
        ),
        encoding="utf-8",
    )


def _write_source(root: Path) -> None:
    path = root / "ext" / "Demo.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "$schema: demo_schema.json#\nkind: extension\nname: Demo\nvalues: [3, 1]\n",
        encoding="utf-8",
    )


def test_json_and_yaml_are_canonical_across_mapping_order() -> None:
    left = {"z": 1, "a": {"y": 2, "x": 3}, "items": [{"b": 4, "a": 5}]}
    right = {"items": [{"a": 5, "b": 4}], "a": {"x": 3, "y": 2}, "z": 1}

    assert dumps_json(left) == dumps_json(right)
    assert dumps_yaml(left) == dumps_yaml(right)
    assert dumps_json(left).endswith("\n")
    assert dumps_yaml(left).endswith("\n")


def test_yaml_quotes_strings_ambiguous_to_yaml_1_1_consumers() -> None:
    values = ["on", "OFF", "yes", "No", "1:20", "012", "2026-09-29", "null"]
    text = dumps_yaml({"values": values})
    yaml_1_1 = YAML(typ="safe")
    yaml_1_1.version = (1, 1)

    assert yaml_1_1.load(text) == {"values": values}


def test_yaml_preserves_numeric_mapping_keys_and_json_rejects_collisions() -> None:
    value = {2: "two", 1: "one", "nested": {3: "three"}}

    assert YAML(typ="safe").load(dumps_yaml(value)) == value
    with pytest.raises(SerializationError, match="collides after JSON normalization"):
        dumps_json({1: "integer", "1": "string"})
    with pytest.raises(SerializationError, match="collides after JSON normalization"):
        dumps_json({True: "boolean", "true": "string"})
    with pytest.raises(SerializationError, match="collides after JSON normalization"):
        dumps_json({None: "null", "null": "string"})


def test_serialization_errors_include_document_and_pointer() -> None:
    with pytest.raises(SerializationError, match=r"demo.yaml#/nested/value.*not serializable"):
        dumps_yaml({"nested": {"value": object()}}, source="demo.yaml")
    with pytest.raises(SerializationError, match=r"cfg.yaml#/\$source.*not portable"):
        dumps_yaml({"$source": "/checkout/cfg.yaml"}, source="cfg.yaml")
    with pytest.raises(SerializationError, match=r"cfg.yaml#/\$source.*not portable"):
        dumps_yaml({"$source": r"C:\checkout\cfg.yaml"}, source="cfg.yaml")
    with pytest.raises(SerializationError, match=r"cfg.yaml#/\$source.*not portable"):
        dumps_yaml({"$source": r"C:cfg.yaml"}, source="cfg.yaml")
    with pytest.raises(SerializationError, match=r"cfg.yaml#/tool_path.*not portable"):
        dumps_yaml({"tool_path": Path("/checkout/tool")}, source="cfg.yaml")


def test_config_serialization_is_stable_and_has_no_implicit_source(tmp_path: Path) -> None:
    config = {"params": {"MXLEN": 64}, "name": "demo"}
    first = write_config(config, tmp_path / "cfg.yaml")
    initial = first.read_bytes()
    write_config(dict(reversed(config.items())), first)

    assert first.read_bytes() == initial
    assert "$source" not in first.read_text(encoding="utf-8")
    assert YAML(typ="safe").load(initial) == config

    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")
    with pytest.raises(SerializationError, match="Cannot write"):
        write_config(config, blocker / "cfg.yaml")


def test_resolved_database_writes_versioned_portable_stable_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    schemas = tmp_path / "schemas"
    output = tmp_path / "out"
    _write_source(source)
    _write_schema(schemas)
    resolved = Database.from_path(source, schemas_path=schemas).resolve()

    written = resolved.write(output)
    first = {path.relative_to(output): path.read_bytes() for path in written}
    resolved.write(output)
    second = {path.relative_to(output): path.read_bytes() for path in written}

    document = YAML(typ="safe").load(output / "ext" / "Demo.yaml")
    assert first == second
    assert document["$schema"] == "v1.2/demo_schema.json#"
    assert resolved.extension("Demo")["$schema"] == "demo_schema.json#"
    assert "$source" not in document
    assert json.loads((output / "index.json").read_text(encoding="utf-8")) == ["ext/Demo.yaml"]


def test_resolved_database_removes_only_stale_manifest_documents(tmp_path: Path) -> None:
    output = tmp_path / "out"
    first = ResolvedDatabase(
        {
            "ext/Keep.yaml": {"kind": "extension", "name": "Keep"},
            "ext/Stale.yaml": {"kind": "extension", "name": "Stale"},
        }
    )
    first.write(output)
    unrelated = output / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    ResolvedDatabase({"ext/Keep.yaml": {"kind": "extension", "name": "Keep"}}).write(output)

    assert (output / "ext" / "Keep.yaml").is_file()
    assert not (output / "ext" / "Stale.yaml").exists()
    assert unrelated.read_text(encoding="utf-8") == "keep me"


def test_resolved_database_refuses_to_remove_modified_stale_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    first = ResolvedDatabase(
        {
            "ext/Keep.yaml": {"kind": "extension", "name": "Keep"},
            "ext/Stale.yaml": {"kind": "extension", "name": "Stale"},
        }
    )
    first.write(output)
    stale = output / "ext" / "Stale.yaml"
    stale.write_text("user change\n", encoding="utf-8")

    with pytest.raises(SerializationError, match="modified stale output"):
        ResolvedDatabase({"ext/Keep.yaml": {"kind": "extension", "name": "Keep"}}).write(output)

    assert stale.read_text(encoding="utf-8") == "user change\n"


def test_resolved_database_preflights_every_document_before_writing(tmp_path: Path) -> None:
    output = tmp_path / "out"
    ResolvedDatabase({"a.yaml": {"value": "old"}}).write(output)
    old_document = (output / "a.yaml").read_bytes()
    old_index = (output / "index.json").read_bytes()

    replacement = ResolvedDatabase(
        {
            "a.yaml": {"value": "new"},
            "z.yaml": {"unsupported": object()},
        }
    )
    with pytest.raises(SerializationError, match=r"z.yaml#/unsupported"):
        replacement.write(output)

    assert (output / "a.yaml").read_bytes() == old_document
    assert (output / "index.json").read_bytes() == old_index


def test_schema_stamping_requires_a_store_and_reports_logical_source(tmp_path: Path) -> None:
    without_store = ResolvedDatabase({"ext/Demo.yaml": {"$schema": "demo_schema.json#"}})
    with pytest.raises(SerializationError, match=r"ext/Demo.yaml#/\$schema.*schema directory"):
        without_store.write(tmp_path / "missing-store")

    schemas = tmp_path / "schemas"
    _write_schema(schemas)
    missing_schema = ResolvedDatabase(
        {"ext/Demo.yaml": {"$schema": "missing.json#"}}, schemas_root=schemas
    )
    with pytest.raises(SerializationError, match=r"ext/Demo.yaml#/\$schema.*Unknown schema"):
        missing_schema.write(tmp_path / "missing-schema")


@pytest.mark.parametrize("path", [r"..\escape.yaml", "C:/escape.yaml", "dir/name:alt.yaml"])
def test_resolved_document_paths_are_canonical_posix_paths(tmp_path: Path, path: str) -> None:
    database = ResolvedDatabase({path: {"value": 1}})

    with pytest.raises(SerializationError, match="POSIX separators"):
        database.write(tmp_path / "out")


@pytest.mark.parametrize(
    "documents",
    [
        {"a.yaml": {"value": 1}, "a.yaml/child.yaml": {"value": 2}},
        {"a.yaml/child.yaml": {"value": 2}, "a.yaml": {"value": 1}},
        {"index.yaml/child.yaml": {"value": 1}},
    ],
)
def test_resolved_database_rejects_output_path_ancestry_collisions(
    tmp_path: Path, documents: dict[str, dict[str, int]]
) -> None:
    with pytest.raises(SerializationError, match="Output path collision"):
        ResolvedDatabase(documents).write(tmp_path)

    assert not (tmp_path / "index.json").exists()


def test_resolved_database_preflights_file_directory_transitions(tmp_path: Path) -> None:
    output = tmp_path / "out"
    ResolvedDatabase({"a.yaml": {"value": 1}}).write(output)
    original = (output / "a.yaml").read_bytes()

    with pytest.raises(SerializationError, match="existing file"):
        ResolvedDatabase({"a.yaml/child.yaml": {"value": 2}}).write(output)

    assert (output / "a.yaml").read_bytes() == original

    nested_output = tmp_path / "nested-out"
    ResolvedDatabase({"a.yaml/child.yaml": {"value": 2}}).write(nested_output)
    nested_original = (nested_output / "a.yaml" / "child.yaml").read_bytes()
    with pytest.raises(SerializationError, match="existing directory"):
        ResolvedDatabase({"a.yaml": {"value": 1}}).write(nested_output)

    assert (nested_output / "a.yaml" / "child.yaml").read_bytes() == nested_original


def test_schema_publication_matches_versioned_ruby_contract(tmp_path: Path) -> None:
    schemas = tmp_path / "schemas"
    output = tmp_path / "published"
    _write_schema(schemas)

    written = write_resolved_schemas(SchemaStore(schemas), output)

    assert written == (output / "demo_schema.json" / "v1.2" / "demo_schema.json",)
    published = json.loads(written[0].read_text(encoding="utf-8"))
    assert published["$id"] == (
        "https://riscv.github.io/riscv-unified-db/schemas/demo_schema.json/v1.2/demo_schema.json"
    )
    assert not (output / "json-schema-draft-07.json").exists()


def test_bundled_database_serializes_every_document(tmp_path: Path) -> None:
    resolved = Database.bundled().resolve()

    written = resolved.write(tmp_path)
    yaml = YAML(typ="safe")
    schemas = SchemaStore(resolved.schemas_root)

    assert len(written) == len(resolved.documents) + 2
    assert {path.relative_to(tmp_path).as_posix() for path in written} == {
        *resolved.documents,
        "index.json",
        "index.yaml",
    }
    for relative_path, document in resolved.documents.items():
        expected = json.loads(dumps_json(document))
        if "$schema" in expected:
            expected["$schema"] = schemas.versioned_uri(expected["$schema"])
        assert yaml.load(tmp_path / relative_path) == expected


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare schema bytes with Ruby",
)
def test_all_published_schemas_match_ruby_bytes(tmp_path: Path) -> None:
    bundle = shutil.which("bundle")
    if bundle is None:
        pytest.fail("UDB_TEST_RUBY=1 requires the repository Ruby toolchain")
    python_output = tmp_path / "python"
    ruby_output = tmp_path / "ruby"
    write_resolved_schemas(SchemaStore(REPOSITORY_ROOT / "spec" / "schemas"), python_output)
    result = subprocess.run(
        [
            bundle,
            "exec",
            "ruby",
            str(RUBY_SCHEMA_ORACLE),
            str(REPOSITORY_ROOT / "spec" / "schemas"),
            str(ruby_output),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby schema oracle failed:\n{result.stdout}\n{result.stderr}")

    python_files = sorted(
        path.relative_to(python_output) for path in python_output.rglob("*.json") if path.is_file()
    )
    ruby_files = sorted(
        path.relative_to(ruby_output) for path in ruby_output.rglob("*.json") if path.is_file()
    )
    assert python_files == ruby_files
    for relative_path in python_files:
        assert (python_output / relative_path).read_bytes() == (
            ruby_output / relative_path
        ).read_bytes()


def test_serialization_cli_commands(tmp_path: Path) -> None:
    source = tmp_path / "source"
    schemas = tmp_path / "schemas"
    _write_source(source)
    _write_schema(schemas)

    assert (
        main(["--path", str(source), "--schemas", str(schemas), "resolve", str(tmp_path / "db")])
        == 0
    )
    assert (tmp_path / "db" / "ext" / "Demo.yaml").is_file()
    assert main(["--schemas", str(schemas), "schemas", str(tmp_path / "published")]) == 0
    assert (tmp_path / "published" / "demo_schema.json" / "v1.2" / "demo_schema.json").is_file()


def test_schema_cli_reads_the_explicit_live_schema_root(tmp_path: Path) -> None:
    schemas = tmp_path / "schemas"
    _write_schema(schemas)
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert main(["--schemas", str(schemas), "schemas", str(first)]) == 0

    schema_path = schemas / "demo_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$id"] = "v1.3"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    assert main(["--schemas", str(schemas), "schemas", str(second)]) == 0

    assert (first / "demo_schema.json" / "v1.2" / "demo_schema.json").is_file()
    assert (second / "demo_schema.json" / "v1.3" / "demo_schema.json").is_file()


def test_only_resolved_databases_can_write_resolved_trees(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_source(source)
    database = Database.from_path(source)

    with pytest.raises(AttributeError):
        database.write(tmp_path / "out")  # type: ignore[attr-defined]

    direct = ResolvedDatabase({"bad.yaml": {"nested": {"value": object()}}})
    with pytest.raises(SerializationError, match=r"bad.yaml#/nested/value"):
        direct.write(tmp_path / "bad")
