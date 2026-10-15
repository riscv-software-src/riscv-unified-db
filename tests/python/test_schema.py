# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from udb.schema import SchemaError, SchemaStore

REPOSITORY_ROOT = Path(__file__).parents[2]
SCHEMA_ROOT = REPOSITORY_ROOT / "spec" / "schemas"


def write_schema(root: Path, name: str, schema: object) -> None:
    (root / name).write_text(json.dumps(schema), encoding="utf-8")


def local_store(tmp_path: Path, *, versioned_ref: bool = False) -> SchemaStore:
    write_schema(
        tmp_path,
        "defs.json",
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "v0.2",
            "$defs": {"positive": {"type": "integer", "minimum": 1}},
        },
    )
    write_schema(
        tmp_path,
        "item_schema.json",
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "v0.1",
            "$defs": {
                "named": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                }
            },
            "type": "object",
            "required": ["$schema", "count"],
            "properties": {
                "$schema": {"const": "item_schema.json#"},
                "count": {
                    "$ref": (
                        "v0.2/defs.json#/$defs/positive"
                        if versioned_ref
                        else "defs.json#/$defs/positive"
                    )
                },
                "enabled": {"type": "boolean", "default": True},
                "disabled": {"type": "boolean", "default": False},
                "retries": {"type": "integer", "default": 0},
            },
        },
    )
    return SchemaStore(tmp_path)


def test_versions_bare_and_versioned_schema_uris(tmp_path: Path) -> None:
    store = local_store(tmp_path)

    assert store.versioned_uri("item_schema.json#") == "v0.1/item_schema.json#"
    assert (
        store.versioned_uri("v0.1/item_schema.json#/$defs/named")
        == "v0.1/item_schema.json#/$defs/named"
    )
    with pytest.raises(SchemaError, match="version mismatch"):
        store.versioned_uri("v9.9/item_schema.json#")


def test_validation_resolves_local_refs_normalizes_keys_and_does_not_add_defaults(
    tmp_path: Path,
) -> None:
    store = local_store(tmp_path)
    document = {"$schema": "v0.1/item_schema.json#", "count": 2, 7: "numeric key"}

    store.validate(document, source="item.yaml")

    assert "enabled" not in document
    assert "disabled" not in document
    assert "retries" not in document
    assert 7 in document


@pytest.mark.parametrize(
    "nested",
    [
        {1: "integer", "1": "string"},
        {"1": "string", 1: "integer"},
        {"outer": {1: "integer", "1": "string"}},
        {"outer": {"1": "string", 1: "integer"}},
    ],
)
def test_json_key_normalization_rejects_collisions(
    tmp_path: Path, nested: dict[object, object]
) -> None:
    store = local_store(tmp_path)
    document = {"$schema": "item_schema.json#", "count": 1, "nested": nested}

    with pytest.raises(SchemaError, match=r"collision.yaml.*both normalize.*'1'"):
        store.validate(document, source="collision.yaml")


def test_validation_resolves_versioned_cross_schema_refs(tmp_path: Path) -> None:
    store = local_store(tmp_path, versioned_ref=True)
    store.validate({"$schema": "item_schema.json#", "count": 2})


def test_validation_supports_schema_fragments(tmp_path: Path) -> None:
    store = local_store(tmp_path)
    store.validate(
        {"$schema": "v0.1/item_schema.json#/$defs/named", "name": "valid"},
        source="fragment.yaml",
    )


def test_validation_errors_include_source_and_location(tmp_path: Path) -> None:
    store = local_store(tmp_path)

    with pytest.raises(SchemaError, match=r"bad.yaml.*\$\.count"):
        store.validate({"$schema": "item_schema.json#", "count": 0}, source="bad.yaml")
    with pytest.raises(SchemaError, match="missing non-empty string"):
        store.validate({"count": 1}, source="missing.yaml")
    with pytest.raises(SchemaError, match="not representable as JSON"):
        store.validate({"$schema": "item_schema.json#", "count": float("nan")}, source="nan.yaml")


def test_unknown_missing_and_nonlocal_schemas_are_rejected(tmp_path: Path) -> None:
    store = local_store(tmp_path)

    with pytest.raises(SchemaError, match="Unknown schema"):
        store.versioned_uri("missing.json#")
    with pytest.raises(SchemaError, match=r"unknown.yaml.*Unknown schema"):
        store.validate({"$schema": "missing.json#"}, source="unknown.yaml")
    for uri in ("../item_schema.json#", "/item_schema.json#", "https://example.com/schema.json#"):
        with pytest.raises(SchemaError, match=r"schema URI|Schema URI"):
            store.versioned_uri(uri)


@pytest.mark.parametrize(
    "reference",
    [
        "missing.json#",
        "v9.9/defs.json#/$defs/positive",
        "https://example.invalid/never-fetch.json#",
    ],
)
def test_missing_versioned_or_network_reference_is_not_retrieved(
    tmp_path: Path, reference: str
) -> None:
    write_schema(
        tmp_path,
        "bad_ref.json",
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "v0.1",
            "$ref": reference,
        },
    )
    store = SchemaStore(tmp_path)

    with pytest.raises(SchemaError, match="cannot resolve schema reference"):
        store.validate({"$schema": "bad_ref.json#"}, source="offline.yaml")


@pytest.mark.parametrize(
    ("name", "contents", "message"),
    [
        ("broken.json", "{", "cannot load JSON schema"),
        ("array.json", "[]", "must contain an object"),
        (
            "unversioned.json",
            '{"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}',
            "must be a version",
        ),
        (
            "invalid.json",
            '{"$schema": "http://json-schema.org/draft-07/schema#", "$id": "v0.1", "type": 7}',
            "invalid Draft 7 schema",
        ),
        (
            "wrong_dialect.json",
            '{"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "v0.1"}',
            "unsupported JSON Schema dialect",
        ),
    ],
)
def test_invalid_schema_files_are_source_aware(
    tmp_path: Path, name: str, contents: str, message: str
) -> None:
    (tmp_path / name).write_text(contents, encoding="utf-8")

    with pytest.raises(SchemaError, match=message) as error:
        SchemaStore(tmp_path).versioned_uri(name)
    assert name in str(error.value)


def test_loaded_schemas_are_cached_per_store(tmp_path: Path) -> None:
    store = local_store(tmp_path)
    assert store.versioned_uri("item_schema.json#") == "v0.1/item_schema.json#"

    schema_path = tmp_path / "item_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$id"] = "v9.9"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    assert store.versioned_uri("item_schema.json#") == "v0.1/item_schema.json#"
    assert SchemaStore(tmp_path).versioned_uri("item_schema.json#") == "v9.9/item_schema.json#"


def test_relative_path_root_is_stable_after_working_directory_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    local_store(schemas)
    monkeypatch.chdir(tmp_path)
    store = SchemaStore(Path("schemas"))
    monkeypatch.chdir(tmp_path.parent)

    store.validate({"$schema": "item_schema.json#", "count": 1})


def test_string_schema_root_is_supported(tmp_path: Path) -> None:
    local_store(tmp_path)
    store = SchemaStore(str(tmp_path))

    assert store.versioned_uri("item_schema.json#") == "v0.1/item_schema.json#"


def test_missing_string_schema_root_is_descriptive(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(SchemaError, match="Schema directory does not exist"):
        SchemaStore(str(missing))


def test_all_repository_schemas_load_and_relevant_standard_records_validate() -> None:
    store = SchemaStore(SCHEMA_ROOT)
    schema_files = sorted(SCHEMA_ROOT.glob("*.json"))
    versioned = {
        schema_file.name: store.versioned_uri(f"{schema_file.name}#")
        for schema_file in schema_files
        if schema_file.name != "json-schema-draft-07.json"
    }

    assert versioned["csr_schema.json"] == "v0.3/csr_schema.json#"
    assert versioned["inst_schema.json"] == "v0.2/inst_schema.json#"
    assert len(versioned) == len(schema_files) - 1

    yaml = YAML(typ="safe")
    for relative_path in ("ext/Zvkg.yaml", "inst/I/add.yaml"):
        source = REPOSITORY_ROOT / "spec" / "std" / "isa" / relative_path
        document = yaml.load(source)
        store.validate(document, source=relative_path)
