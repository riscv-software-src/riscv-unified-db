# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Complete raw-oracle comparisons with frozen, explicitly classified changes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest
from extension_documents_helpers import (
    configured_prose_provider,
    formatter_lines,
    repaired_anchor_expectation,
)

from udb import Configuration, Database, SchemaStore
from udb.extension_docs import DocumentOptions, render_extension_document

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parent / "fixtures/extension_docs"
CASES = ("zba-all", "zicsr-all", "zicsr-full", "qcicsr", "xqci-original-script")
CLASSIFICATIONS = {
    "normative-global-parameters",
    "normative-version-requirements",
    "complete-implied-condition",
    "native-tuple-assignment-correction",
    "native-fixed-rv32-csr-correction",
    "source-visible-function-declarations",
}


def selectors_for(case):
    return case.get("selectors") or case["argv"][case["argv"].index("--no-csr-field-desc") + 1 :]


def digest(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def corrected_native(case_id: str, *, preserve_format: bool = False) -> str:
    """Apply exact, reviewed expected-side edits; never normalize source content."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    case = next(case for case in manifest["outcomes"] if case["id"] == case_id)
    raw_bytes = (FIXTURES / case["artifact"]).read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == case["sha256"]
    names = [selector.partition("@")[0] for selector in selectors_for(case)]
    repaired = repaired_anchor_expectation(raw_bytes.decode(), names)
    original = formatter_lines(repaired)
    reviewed = json.loads((FIXTURES / "reviewed-deltas.json").read_text())[case_id]
    assert digest(original) == reviewed["native_with_anchor_repairs_sha256"]
    lines = original[:]
    offset = 0
    for edit in reviewed["edits"]:
        assert edit["classification"] in CLASSIFICATIONS
        index = edit["native_line"] - 1
        before = edit["before"]
        assert original[index : index + len(before)] == before
        assert original[max(0, index - 3) : index] == edit["context_before"]
        end = index + len(before)
        assert original[end : end + 3] == edit["context_after"]
        assert lines[index + offset : index + offset + len(before)] == before
        lines[index + offset : index + offset + len(before)] = edit["after"]
        offset += len(edit["after"]) - len(before)
    assert digest(lines) == reviewed["reviewed_complete_sha256"]
    if preserve_format:
        raw_lines = repaired.splitlines()
        indices, literal = [], None
        for index, line in enumerate(raw_lines):
            if line in {"----", "...."}:
                literal = None if literal == line else line
                indices.append(index)
            elif literal is not None or line.strip():
                indices.append(index)
        assert len(indices) == len(original)
        for edit in reversed(reviewed["edits"]):
            start = edit["native_line"] - 1
            count = len(edit["before"])
            end = indices[start + count - 1] + 1 if count else indices[start]
            raw_lines[indices[start] : end] = edit["after"]
        return "\n".join(raw_lines) + "\n"
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("case_id", CASES)
def test_complete_native_artifact_and_every_classified_addition(case_id, tmp_path):
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    case = next(case for case in manifest["outcomes"] if case["id"] == case_id)
    schemas = SchemaStore(ROOT / "spec/schemas")
    configuration = (
        Configuration.builtin(case["cfg"])
        if case["cfg"] in {"_", "rv32", "rv64"}
        else Configuration.from_file(
            ROOT / "cfgs" / ("qc_iu.yaml" if case["cfg"] == "qc_iu" else Path(case["cfg"]).name),
            schema_store=schemas,
        )
    )
    overlays = (ROOT / "spec/custom/isa" / configuration.overlay,) if configuration.overlay else ()
    architecture = (
        Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas")
        .resolve(overlays=overlays)
        .configure(configuration)
    )
    actual = render_extension_document(
        architecture,
        selectors_for(case),
        options=DocumentOptions(
            revision=manifest["head"],
            today=date(2026, 10, 1),
            include_implied="-i" in case["argv"],
            include_csr_field_descriptions=True,
            prose=configured_prose_provider(architecture),
        ),
    )
    (tmp_path / (case_id + ".adoc")).write_text(actual, encoding="utf-8")
    declared = set(re.findall(r"(?m)^\[#udb-function-([^\]]+)\]", actual))
    referenced = set(re.findall(r"xref:#udb-function-([^\[]+)\[", actual))
    assert referenced <= declared
    assert formatter_lines(actual) == formatter_lines(corrected_native(case_id))


def test_recorded_native_latest_error_is_not_an_artifact_parity_pass():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    case = next(case for case in manifest["outcomes"] if case["id"] == "zba-latest")
    assert not case["ok"]
    assert case["error"]["class"] == "NoMethodError"
    assert "undefined method 'each' for nil" in case["error"]["message"]
    assert case["id"] not in CASES
