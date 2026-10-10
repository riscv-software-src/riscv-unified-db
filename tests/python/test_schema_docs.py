# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Whole-artifact oracles and bounded standalone schema documentation behavior."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from udb.errors import AuthoringError
from udb.schema import SchemaError, SchemaStore
from udb.schema_docs import (
    SchemaDocsError,
    SchemaDocsProjectionWarning,
    SchemaDocumentation,
    generate_schema_docs,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures/schema_docs"
DIALECT = "http://json-schema.org/draft-07/schema#"


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_docs(root: Path) -> SchemaDocumentation:
    with pytest.warns(SchemaDocsProjectionWarning):
        return SchemaDocumentation(SchemaStore(root))


def write_schema(root: Path, name: str = "sample.json", **fields) -> SchemaStore:
    root.mkdir(exist_ok=True, parents=True)
    (root / name).write_text(
        json.dumps(
            {
                "$schema": DIALECT,
                "$id": "v0.1",
                "type": "object",
                "properties": {},
                **fields,
            }
        ),
        encoding="utf-8",
    )
    return SchemaStore(root)


@pytest.mark.parametrize(
    ("schema_root", "oracle_name"),
    [
        (ROOT / "spec/schemas", "ruby-current"),
        (FIXTURES / "custom-schemas", "ruby-custom"),
        (FIXTURES / "psych-schemas", "ruby-psych-docs"),
    ],
)
def test_all_artifact_bytes_and_set_match_real_ruby(schema_root, oracle_name, tmp_path):
    oracle = FIXTURES / oracle_name
    manifest = json.loads((oracle / "manifest.json").read_text())
    assert {
        path.name: sha(path.read_bytes()) for path in sorted(schema_root.glob("*.json"))
    } == manifest["schemas"], (
        "schema changes require a new genuine Ruby oracle, not weaker comparison"
    )
    gem = ROOT / "tools/internal-gems/schema_doc_gen"
    for relative, expected in manifest["ruby_sources"].items():
        assert sha((gem / relative).read_bytes()) == expected
    docs = load_docs(schema_root)
    plan = docs.plan(tmp_path)
    assert {str(output.path) for output in plan.outputs} == set(manifest["artifacts"])
    for output in plan.outputs:
        expected = (oracle / "all" / output.path).read_bytes()
        assert sha(expected) == manifest["artifacts"][str(output.path)]
        assert output.content == expected, str(output.path)
    assert docs.render("config_schema.json").encode() == (oracle / "single.mdx").read_bytes()
    assert len(plan.apply(tmp_path)) == len(plan.outputs)
    assert plan.apply(tmp_path, check=True) == ()
    assert docs.plan(tmp_path).apply(tmp_path) == ()


def test_default_bundled_generation_is_offline_and_repository_independent(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("runtime tried network, subprocess or checkout cwd")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    with pytest.warns(SchemaDocsProjectionWarning):
        docs = SchemaDocumentation()
    assert len(docs.schema_names) == 23
    plan = docs.plan(tmp_path)
    assert len(plan.outputs) == 28
    for generated in plan.outputs:
        assert generated.content == (FIXTURES / "ruby-current/all" / generated.path).read_bytes(), (
            str(generated.path)
        )
    plan.apply(tmp_path)
    assert plan.apply(tmp_path, check=True) == ()


def test_api_uses_instance_snapshot_without_mutating_store(tmp_path):
    root = tmp_path / "schemas"
    store = write_schema(root, title="One")
    first = SchemaDocumentation(store)
    second = SchemaDocumentation(write_schema(root, title="Two"))
    assert "sidebar_label: One" in first.render("sample.json")
    assert "sidebar_label: Two" in second.render("sample.json")
    assert store.versioned_uri("sample.json#") == "v0.1/sample.json#"
    assert (
        store.resolved_schemas(base_url="https://example.org")[
            PurePosixPath("sample.json/v0.1/sample.json")
        ]["title"]
        == "One"
    )


def test_history_index_category_and_old_pages_are_preserved(tmp_path):
    docs = load_docs(ROOT / "spec/schemas")
    output = tmp_path / "history"
    shutil.copytree(ROOT / "doc/docs/schemas", output)
    current_pages = {output.path for output in docs.plan().outputs}
    old_bytes = {
        path.relative_to(output): path.read_bytes()
        for path in output.glob("*/*.mdx")
        if PurePosixPath(path.relative_to(output)) not in current_pages
    }
    plan = docs.plan(output)
    drift = plan.apply(output, check=True)
    assert set(map(str, drift)) == {
        "index.mdx",
        "v0.1/_category_.json",
        "v0.2/_category_.json",
        "v0.3/_category_.json",
        "v0.2/ext_schema.mdx",
        "v0.4/schema_defs.mdx",
        "v0.4/_category_.json",
    }
    plan.apply(output)
    assert (output / "index.mdx").read_bytes() == (
        FIXTURES / "ruby-current/history-index.mdx"
    ).read_bytes()
    for relative, expected in old_bytes.items():
        assert (output / relative).read_bytes() == expected
    history_manifest = json.loads((FIXTURES / "ruby-current/history-manifest.json").read_text())
    assert {
        path.relative_to(output).as_posix(): sha(path.read_bytes())
        for path in output.rglob("*")
        if path.is_file()
    } == history_manifest["artifacts"]
    assert json.loads((output / "v0.4/_category_.json").read_text())["position"] == 1
    assert docs.plan(output).apply(output, check=True) == ()


def test_missing_and_different_checks_and_immutable_preflight(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    plan = docs.plan(output)
    assert len(plan.apply(output, check=True)) == 3
    assert not output.exists()
    plan.apply(output)
    page = output / "v0.1/sample.mdx"
    page.write_text("released bytes", encoding="utf-8")
    index = output / "index.mdx"
    index.write_text("previous index", encoding="utf-8")
    assert plan.apply(output, check=True) == (
        PurePosixPath("v0.1/sample.mdx"),
        PurePosixPath("index.mdx"),
    )
    with pytest.raises(SchemaDocsError, match="immutable"):
        plan.apply(output)
    assert page.read_text() == "released bytes"
    assert index.read_text() == "previous index"
    plan.apply(output, replace_current=True)
    assert plan.apply(output, check=True) == ()


def test_single_file_override_no_categories_or_index(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    plan = docs.plan(tmp_path / "out", schema="sample.json", output_file="reference/schema.md")
    assert [str(output.path) for output in plan.outputs] == ["reference/schema.md"]
    assert plan.outputs[0].content.decode() == docs.render("sample.json")
    with pytest.raises(SchemaDocsError, match="requires a single"):
        docs.plan(output_file="reference.md")
    with pytest.raises(SchemaDocsError, match="historical"):
        docs.plan(schema="sample.json", output_file="v0.0/sample.mdx")
    with pytest.raises(SchemaDocsError, match=r"\.md"):
        docs.plan(schema="sample.json", output_file="sample.json")
    with pytest.raises(SchemaDocsError, match="schema index"):
        docs.plan(schema="sample.json", output_file="index.mdx")
    with pytest.raises(AuthoringError, match="unsafe"):
        docs.plan(schema="sample.json", output_file="../sample.mdx")
    with pytest.raises(SchemaDocsError, match="unknown"):
        docs.render("missing.json")
    plan.apply(tmp_path / "out")
    page = tmp_path / "out/reference/schema.md"
    page.write_text("published reference")
    with pytest.raises(SchemaDocsError, match="immutable"):
        plan.apply(tmp_path / "out", replace_current=True)
    assert page.read_text() == "published reference"


def test_stale_history_snapshot_is_rejected_before_writes(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    plan = docs.plan(output)
    older = output / "v0.0"
    older.mkdir(parents=True)
    (older / "sample.mdx").write_text("immutable old page")
    with pytest.raises(SchemaDocsError, match="history changed"):
        plan.apply(output)
    assert not (output / "v0.1/sample.mdx").exists()
    docs.plan(output).apply(output)
    assert 'href="./v0.0/sample"' in (output / "index.mdx").read_text()
    assert (older / "sample.mdx").read_text() == "immutable old page"


def test_canonical_override_cannot_impersonate_another_schema(tmp_path):
    docs = load_docs(ROOT / "spec/schemas")
    for path in ("v0.1/ext_schema.mdx", "v0.1/another.mdx", "v0.1/nested/config_schema.mdx"):
        with pytest.raises(SchemaDocsError, match="canonical page"):
            docs.plan(tmp_path, schema="config_schema.json", output_file=path)
    plan = docs.plan(
        tmp_path,
        schema="config_schema.json",
        output_file="v0.1/config_schema.mdx",
    )
    assert plan.outputs[0].path == PurePosixPath("v0.1/config_schema.mdx")


def test_inspection_only_plan_and_hidden_history_names(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    (output / "v0.0").mkdir(parents=True)
    (output / "v0.0/older.mdx").write_text("old")
    (output / "v0.0/.bak.mdx").write_text("ignored dotfile")
    assert docs.plan().history_pages is None
    assert docs.plan(output).apply(output)
    assert "older" in (output / "index.mdx").read_text()
    assert ".bak" not in (output / "index.mdx").read_text()


def test_no_index_option_and_unrelated_outputs_are_not_deleted(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep")
    (output / "index.mdx").write_text("keep index")
    docs.plan(output, generate_index=False).apply(output)
    assert (output / "index.mdx").read_text() == "keep index"
    assert (output / "unrelated.txt").read_text() == "keep"


def test_meta_schema_only_store_has_no_pages_and_an_empty_index(tmp_path):
    root = tmp_path / "schemas"
    root.mkdir()
    shutil.copyfile(
        ROOT / "spec/schemas/json-schema-draft-07.json",
        root / "json-schema-draft-07.json",
    )
    docs = SchemaDocumentation(SchemaStore(root))
    assert docs.schema_names == ()
    plan = docs.plan(tmp_path / "out")
    assert [str(output.path) for output in plan.outputs] == ["index.mdx"]
    assert "No schema documentation found." in plan.outputs[0].content.decode()
    plan.apply(tmp_path / "out")


@pytest.mark.parametrize("kind", ["version", "page", "root", "dangling_root"])
def test_symlinks_are_rejected_before_writing(tmp_path, kind):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    other = tmp_path / "other"
    other.mkdir()
    output.mkdir()
    if kind == "version":
        (output / "v0.1").symlink_to(other, target_is_directory=True)
    elif kind == "page":
        (output / "v0.1").mkdir()
        (other / "page.mdx").write_text("keep")
        (output / "v0.1/sample.mdx").symlink_to(other / "page.mdx")
    elif kind == "root":
        output.rmdir()
        output.symlink_to(other, target_is_directory=True)
    else:
        output.rmdir()
        output.symlink_to(other / "missing", target_is_directory=True)
    with pytest.raises((SchemaDocsError, AuthoringError), match=r"symlink|unsafe"):
        docs.plan(output).apply(output)
    assert not (other / "index.mdx").exists()


def test_output_directory_collision_is_rejected_before_any_writes(tmp_path):
    docs = SchemaDocumentation(write_schema(tmp_path / "schemas"))
    output = tmp_path / "out"
    (output / "v0.1/_category_.json").mkdir(parents=True)
    with pytest.raises(AuthoringError, match="not a regular file"):
        docs.plan(output).apply(output, replace_current=True)
    assert not (output / "v0.1/sample.mdx").exists()


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"dependentSchemas": {}}, "unsupported keyword"),
        ({"definitions": {"old": {"type": "string"}}}, "unsupported keyword"),
        ({"properties": {"tuple": {"type": "array", "items": [{"type": "string"}]}}}, "tuple"),
        ({"properties": {"union": {"type": ["string", "null"]}}}, "type unions"),
        ({"properties": {"ref": {"$ref": "missing.json#"}}}, "unknown local"),
        ({"properties": {"ref": {"$ref": "#/$defs/missing"}}}, "unresolved JSON pointer"),
        ({"properties": {"ref": {"$ref": "file:///etc/passwd"}}}, "unsupported reference"),
        ({"properties": {"ref": {"$ref": "//example.org/x.json"}}}, "unsupported reference"),
        ({"properties": {"ref": {"$ref": "#named-anchor"}}}, "named reference"),
        ({"$defs": {"bad": {"type": "imaginary"}}}, "invalid definition"),
        ({"$defs": {"bad": False}}, "boolean definitions"),
        ({"$defs": {"bad": {"$id": "v1.0"}}}, "nested schema"),
        ({"$defs": {"bad": {"$defs": {}}}}, "nested definitions"),
        ({"properties": {"constant": {"const": {"value": 1}}}}, "structured constants"),
        ({"properties": {"enum": {"enum": [[1, 2]]}}}, "structured enum"),
        ({"oneOf": [True]}, "boolean composition"),
        ({"type": "string"}, "non-object root"),
        ({"$ref": "#"}, "root references"),
        ({"enum": ["value"]}, "root literals"),
        (
            {"oneOf": [{"type": "string"}], "properties": {"ref": {"$ref": "#/oneOf/-1"}}},
            "unresolved JSON pointer",
        ),
        (
            {"oneOf": [{"type": "string"}], "properties": {"ref": {"$ref": "#/oneOf/00"}}},
            "unresolved JSON pointer",
        ),
        ({"unevaluatedProperties": False}, "unsupported keyword"),
        ({"$refs": "#/$defs/x"}, "unsupported keyword"),
    ],
)
def test_unsupported_features_fail_explicitly_without_output(tmp_path, fields, match):
    store = write_schema(tmp_path / "schemas", **fields)
    output = tmp_path / "out"
    with pytest.raises(SchemaDocsError, match=match):
        generate_schema_docs(output, schemas=store)
    assert not output.exists()


@pytest.mark.parametrize(
    "fields",
    [
        {"$id": "https://example.org/schema"},
        {"$schema": "https://json-schema.org/draft/2020-12/schema"},
    ],
)
def test_schema_store_dialect_and_version_errors_are_preserved(tmp_path, fields):
    with pytest.raises(SchemaError):
        SchemaDocumentation(write_schema(tmp_path / "schemas", **fields))


def test_cyclic_expandable_refs_fail_before_any_writes(tmp_path):
    root = tmp_path / "schemas"
    store = write_schema(root, properties={"item": {"$ref": "schema_defs.json#/$defs/a"}})
    write_schema(
        root,
        "schema_defs.json",
        **{
            "$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}},
        },
    )
    output = tmp_path / "out"
    with pytest.warns(SchemaDocsProjectionWarning), pytest.raises(SchemaDocsError, match="cyclic"):
        generate_schema_docs(output, schemas=store)
    assert not output.exists()


def test_legacy_projection_is_disclosed_with_exact_locations():
    docs = load_docs(ROOT / "spec/schemas")
    legacy = [notice for notice in docs.notices if "non-Draft-7" in notice.message]
    assert [(notice.schema, notice.keyword) for notice in legacy] == [
        ("inst_schema.json", "type"),
        ("inst_schema.json", "$refs"),
        ("inst_var_type_schema.json", "unevaluatedProperties"),
    ]
    assert all(notice.pointer.startswith("/") for notice in docs.notices)
    assert any(
        notice.schema == "csr_schema.json" and "suppresses" in notice.message
        for notice in docs.notices
    )


@pytest.mark.parametrize(
    ("schema", "pointer", "keyword"),
    [
        ("schema_defs.json", "/$defs/date/examples", "examples"),
        (
            "ext_schema.json",
            "/properties/versions/items/properties/release_date/oneOf/0/description",
            "description",
        ),
        (
            "ext_schema.json",
            "/properties/versions/items/properties/ratification_date/oneOf/0/examples",
            "examples",
        ),
        (
            "csr_schema.json",
            "/$defs/csr_field/properties/reset_value/oneOf/0/description",
            "description",
        ),
        (
            "inst_schema.json",
            "/$defs/old_encoding/properties/match/oneOf/2/description",
            "description",
        ),
    ],
)
def test_real_omitted_annotations_are_disclosed(schema, pointer, keyword):
    docs = load_docs(ROOT / "spec/schemas")
    assert any(
        (notice.schema, notice.pointer, notice.keyword) == (schema, pointer, keyword)
        for notice in docs.notices
    )


def test_usage_reports_omitted_and_partial_but_not_rendered_content(tmp_path):
    store = write_schema(
        tmp_path / "schemas",
        title="Rendered root title",
        description="Rendered root description",
        properties={
            "field": {
                "type": "string",
                "title": "Omitted property title",
                "description": "First paragraph.\n\nOmitted second paragraph.",
                "examples": ["first", "second"],
            },
        },
        **{
            "$defs": {
                "constant": {"type": "string", "const": "omitted", "title": "Omitted title"},
                "described": {"type": "string", "description": "Rendered definition description"},
                "values": {"enum": ["rendered", "values"]},
            }
        },
    )
    with pytest.warns(SchemaDocsProjectionWarning):
        docs = SchemaDocumentation(store)
    notices = {notice.pointer: notice.message for notice in docs.notices}
    for pointer in ("/properties/field/title", "/$defs/constant/title", "/$defs/constant/const"):
        assert "not rendered" in notices[pointer]
    for pointer in ("/properties/field/description", "/properties/field/examples"):
        assert "partially rendered" in notices[pointer]
    for pointer in ("/title", "/description", "/$defs/described/description", "/$defs/values/enum"):
        assert pointer not in notices
    assert "Omitted second paragraph" not in docs.render("sample.json")


def test_cli_diagnostics_are_one_json_document_and_include_io_errors(tmp_path, monkeypatch, capsys):
    from udb.schema_docs.__main__ import main

    output = tmp_path / "out"
    with pytest.warns(SchemaDocsProjectionWarning):
        assert main(["--out", str(output), "--diagnostics"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["status"] == "generated"
    assert len(generated["paths"]) == 28
    assert generated["notices"] and generated["notices"][0]["pointer"].startswith("/")
    (output / "v0.1/config_schema.mdx").write_text("drift")
    with pytest.warns(SchemaDocsProjectionWarning):
        assert main(["--out", str(output), "--diagnostics", "--check"]) == 1
    assert json.loads(capsys.readouterr().out)["paths"] == ["v0.1/config_schema.mdx"]
    monkeypatch.setattr(
        "udb.schema_docs.SchemaDocumentationPlan.apply",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("located test I/O error")),
    )
    with pytest.warns(SchemaDocsProjectionWarning):
        assert main(["--out", str(output), "--diagnostics"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "error": "located test I/O error"}
    assert "schema-docs: located test I/O error" in captured.err


def test_unbound_index_plan_requires_destination_when_history_exists(tmp_path):
    docs = load_docs(ROOT / "spec/schemas")
    old = tmp_path / "v0.0"
    old.mkdir()
    (old / "sample.mdx").write_text("historical")
    plan = docs.plan()
    assert plan.history_pages is None
    with pytest.raises(SchemaDocsError, match="without an output root"):
        plan.apply(tmp_path)
    assert not (tmp_path / "index.mdx").exists()
    docs.plan(tmp_path).apply(tmp_path)
    assert "./v0.0/sample" in (tmp_path / "index.mdx").read_text()


def test_standalone_cli_outside_checkout_with_empty_path(tmp_path):
    output = tmp_path / "out"
    command = [sys.executable, "-m", "udb.schema_docs", "--out", str(output)]
    environment = {**os.environ, "PATH": "", "PYTHONPATH": str(ROOT / "src")}
    generated = subprocess.run(
        command, cwd=tmp_path, env=environment, capture_output=True, text=True, check=False
    )
    assert generated.returncode == 0, generated.stderr
    checked = subprocess.run(
        [*command, "--check"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
    page = output / "v0.1/config_schema.mdx"
    page.write_text("deliberate drift", encoding="utf-8")
    drift = subprocess.run(
        [*command, "--check"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift.returncode == 1
    assert "drift: v0.1/config_schema.mdx" in drift.stdout
    immutable = subprocess.run(
        command, cwd=tmp_path, env=environment, capture_output=True, text=True, check=False
    )
    assert immutable.returncode == 2
    assert "immutable" in immutable.stderr
    assert page.read_text() == "deliberate drift"
