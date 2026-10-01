# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest
from extension_documents_helpers import (
    configured_prose_provider,
    formatter_lines,
    repaired_anchor_expectation,
)

from udb import Configuration, Database
from udb.extension_docs import (
    DocumentOptions,
    ExtensionDocumentError,
    generate_extension_document,
    render_extension_document,
    select_extensions,
)
from udb.extension_docs.documents import template
from udb.extension_docs.model import basename_for

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parent / "fixtures/extension_docs"


@pytest.fixture(scope="module")
def database():
    return Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()


@pytest.fixture(scope="module")
def architecture(database):
    return database.configure(Configuration.builtin("_"))


def test_native_capture_integrity():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for outcome in manifest["outcomes"]:
        if outcome["ok"]:
            data = (FIXTURES / outcome["artifact"]).read_bytes()
            assert len(data) == outcome["bytes"]
            assert hashlib.sha256(data).hexdigest() == outcome["sha256"]
        else:
            assert outcome["error"]["class"] and outcome["error"]["message"]


def test_complete_zba_artifact_matches_native_after_explicit_link_repair(architecture):
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    outcome = next(item for item in manifest["outcomes"] if item["id"] == "zba-all")
    raw = (FIXTURES / outcome["artifact"]).read_text()
    actual = render_extension_document(
        architecture,
        ["Zba"],
        options=DocumentOptions(revision=manifest["head"], today=date(2026, 10, 1)),
    )
    assert formatter_lines(actual) == formatter_lines(repaired_anchor_expectation(raw, ["Zba"]))


@pytest.mark.parametrize("selector", ["Zba", "Zba@latest", "Zba@1", "Zba@>=1", "Zba@~>1"])
def test_all_supported_selectors_use_existing_version_matching(architecture, selector):
    (selection,) = select_extensions(architecture, [selector])
    assert selection.name == "Zba"
    assert [v.canonical for v in selection.versions] == ["1.0.0"]


@pytest.mark.parametrize("selector", ["Zba@", "Zba@2", "Zba@bogus", "../Zba", "Zba@>=2"])
def test_bad_selectors_are_explicit_errors(architecture, selector):
    with pytest.raises(ExtensionDocumentError):
        select_extensions(architecture, [selector])


@pytest.mark.parametrize("name", ["", ".", "..", "../out", "a/b", "a\\b", "a\nb"])
def test_output_basename_cannot_escape_directory(architecture, name):
    selections = select_extensions(architecture, ["Zba"])
    with pytest.raises(ExtensionDocumentError):
        basename_for(selections, DocumentOptions(basename=name))


def test_default_basename_preserves_exact_original_selector(architecture):
    selections = select_extensions(architecture, ["Zba@latest"])
    assert basename_for(selections, DocumentOptions()) == "Zba@latest"
    assert basename_for(selections, DocumentOptions(basename="custom")) == "custom"


def test_source_output_symlink_never_overwrites_caller_input(architecture, tmp_path):
    original = tmp_path / "original.adoc"
    original.write_text("Caller input\n")
    output = tmp_path / "out"
    output.mkdir()
    (output / "Zba.adoc").symlink_to(original)
    with pytest.raises(ExtensionDocumentError, match="must not follow a symlink"):
        generate_extension_document(architecture, ["Zba"], output)
    assert original.read_text() == "Caller input\n"


def test_partial_rv64_latest_generates_complete_source_with_configured_idl(database):
    architecture = database.configure(Configuration.builtin("rv64"))
    text = render_extension_document(
        architecture, ["Zba@latest"], options=DocumentOptions(revision="explicit")
    )
    assert "[#udb-extension-Zba]" in text
    assert "Operation::" in text and "== IDL Functions" in text
    assert ":revnumber: 1.0.0" in text
    assert "<%=" not in text and "%%UDB_DOC_LINK%" not in text


def test_unknown_template_is_not_an_input_path():
    with pytest.raises(ExtensionDocumentError):
        template("../../anything")


def test_source_generation_never_starts_a_process_or_reopens_sources(
    architecture, monkeypatch, tmp_path
):
    def forbidden(*args, **kwargs):
        raise AssertionError("source generation attempted external runtime/source access")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Database, "from_path", forbidden)
    target = generate_extension_document(
        architecture,
        ["Zba"],
        tmp_path / "outputs",
        options=DocumentOptions(basename="result"),
    )
    assert target.name == "result.adoc"
    assert target.read_bytes().endswith(b"\n")
    assert b"\r" not in target.read_bytes()
    assert "Operation::" in target.read_text()


def test_all_instruction_detail_links_have_anchors(architecture):
    text = render_extension_document(architecture, ["Zba"])
    instructions = set(re.findall(r"^\[#udb-insn-([^\]]+)\]$", text, re.MULTILINE))
    assert len(instructions) == 9
    for name in instructions:
        assert f"xref:#udb-insn-{name}[" in text


def test_configured_prose_dependency_has_no_silent_fallback(database, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "udb.prose", None)
    arch = database.configure(Configuration.builtin("_"))
    with pytest.raises(ExtensionDocumentError, match=r"[Cc]onfigured prose provider required"):
        render_extension_document(arch, ["Zicsr"])


def test_provider_binding_and_native_csr_content(database):
    arch = database.configure(Configuration.builtin("_"))
    provider = configured_prose_provider(arch)
    text = render_extension_document(arch, ["Zicsr"], options=DocumentOptions(prose=provider))
    assert "<%" not in text and "%%UDB_DOC_LINK" not in text
    assert "== Software read" in text
    assert "== Field Summary" in text and "Reset value::" in text
    assert "[wavedrom," in text and "=== mtval_for" in text


def test_field_summary_flag_never_evaluates_excluded_descriptions(architecture):
    from udb.extension_docs.compiler import DocumentCompiler
    from udb.extension_docs.csrs import CsrSections
    from udb.extension_docs.model import SelectionQueries

    def provider(text, *, field_path, **kwargs):
        assert not (field_path[0] == "fields" and field_path[-1] == "description")
        return text

    sections = CsrSections(
        architecture,
        DocumentCompiler(architecture),
        SelectionQueries(architecture),
        DocumentOptions(include_csr_field_descriptions=False, prose=provider),
    )
    text = sections.render(architecture.database.csr("fcsr"))
    assert "== Field Summary" in text and "UNDEFINED_LEGAL" in text
    assert "== Fields" not in text and "Description::" not in text
    assert "[[udb-csrfield-fcsr-FRM]]FRM" in text


def test_absent_native_operation_is_not_replaced_with_a_placeholder(architecture):
    from udb.extension_docs.compiler import DocumentCompiler
    from udb.extension_docs.instructions import InstructionSections
    from udb.extension_docs.model import SelectionQueries

    instruction = next(
        item for item in architecture.database.instructions if item.data.get("operation()") is None
    )
    sections = InstructionSections(
        architecture,
        DocumentCompiler(architecture),
        select_extensions(architecture, ["Zicsr"]),
        SelectionQueries(architecture),
        DocumentOptions(),
    )
    text = sections.render(instruction)
    assert "TODO" not in text and "not implemented" not in text
    assert "Operation::" not in text


def test_parameters_use_global_model_records_and_complete_schemas(architecture):
    from udb.extension_docs.model import SelectionQueries
    from udb.extension_docs.parameters import parameters_for, render_parameter

    queries = SelectionQueries(architecture)
    selection = select_extensions(architecture, ["Sm"])[0]
    records = parameters_for(selection, queries)
    mxlen = next(record for record in records if record.name == "MXLEN")
    text = render_parameter(mxlen, queries, DocumentOptions())
    assert "[#udb-param-MXLEN]" in text and "Requirements::" in text
    assert mxlen.data["requirements"]["idl()"].strip() in text
    schema_text = re.search(r"\[source,json\]\n----\n(.*?)\n----", text, re.DOTALL)[1]
    assert json.loads(schema_text) == {"type": "integer", "enum": [32, 64]}
    nested = next(record for record in records if record.data["schema"].get("items"))
    nested_text = render_parameter(nested, queries, DocumentOptions())
    schema = json.loads(re.search(r"\[source,json\]\n----\n(.*?)\n----", nested_text, re.DOTALL)[1])
    assert schema == json.loads(json.dumps(dict(nested.data["schema"]), default=dict))
    assert isinstance(schema["items"], (dict, list))


def test_original_xqci_golden_only_differs_by_captured_commit_provenance():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    golden = (FIXTURES / manifest["original_golden"]["path"]).read_bytes()
    assert hashlib.sha256(golden).hexdigest() == manifest["original_golden"]["sha256"]
    case = next(item for item in manifest["outcomes"] if item["id"] == "xqci-original-script")
    current = (FIXTURES / case["artifact"]).read_text()
    provenance = (
        "This document was created using the "
        "http://github.org/riscv/riscv-unified-db[RISC-V Unified Database] at commit "
        + manifest["head"]
        + ".\n"
    )
    assert current.count(provenance) == 1
    assert formatter_lines(current.replace(provenance, "")) == formatter_lines(golden.decode())
