# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import json
import re
from io import StringIO
from pathlib import Path

import pytest
from schema_docs_psych_cases import (
    block_scalar_cases,
    boundary_cases,
    cases,
    edge_cases,
    scanner_cases,
)

from udb.schema_docs._examples import example_text, full_examples, quick_start
from udb.schema_docs._psych import dump
from udb.schema_docs._psych_emitter import PsychEmitter
from udb.schema_docs._psych_scalars import ruby_string
from udb.serialization import dumps_yaml

ROOT = Path(__file__).resolve().parents[2]
ORACLE = Path(__file__).parent / "fixtures/schema_docs/ruby-current/all"


def test_current_top_level_example_yaml_matches_genuine_ruby():
    for name, version in (("config_schema", "v0.1"), ("ext_schema", "v0.2")):
        schema = json.loads((ROOT / f"spec/schemas/{name}.json").read_text())
        expected = re.findall(
            r"```yaml\n(.*?)\n```",
            (ORACLE / version / f"{name}.mdx").read_text(),
            re.DOTALL,
        )
        rendered = [example_text(example) for example in schema["examples"]]
        for block in rendered:
            assert block in expected


def test_example_yaml_does_not_mutate_core_serializer():
    value = {"mapping": None, "sequence": [None, "2.1", True]}
    before = dumps_yaml(value)
    example_text(value)
    assert dumps_yaml(value) == before


@pytest.mark.parametrize(
    ("filename", "count", "inputs"),
    [
        ("ruby-psych.json", 1092, cases),
        ("ruby-psych-edge.json", 483, edge_cases),
        ("ruby-psych-boundaries.json", 513, boundary_cases),
        ("ruby-psych-scanner.json", 312, scanner_cases),
        ("ruby-psych-block-chains.json", 176, block_scalar_cases),
    ],
)
def test_expanded_scalar_collection_corpus_matches_raw_psych(filename, count, inputs):
    oracle = json.loads((ORACLE.parent.parent / filename).read_text())
    assert (oracle["ruby_version"], oracle["psych_version"], oracle["libyaml_version"]) == (
        "3.4.10",
        "5.3.1",
        [0, 2, 5],
    )
    assert len(oracle["inputs"]) == count
    assert oracle["inputs"] == inputs()
    payload = json.dumps(oracle["inputs"], ensure_ascii=False, allow_nan=False).encode()
    assert hashlib.sha256(payload).hexdigest() == oracle["input_sha256"]
    for index, (value, expected) in enumerate(zip(oracle["inputs"], oracle["yaml"], strict=True)):
        assert dump(value) == expected, (index, value)
    for value, expected in zip(oracle["inputs"], oracle["scalar_text"], strict=True):
        if expected is not None:
            assert ruby_string(value["value"]) == expected


def test_metadata_uses_ruby_truth_and_null_false_caption_fallback():
    for value in (0, "", [], {}):
        example = {"_quick_start": value, "_title": None, "field": "line1\n"}
        assert "**Example:**" in quick_start([example])
        assert full_examples([example]) == ""
    for value in (None, False):
        example = {"_quick_start": value, "_title": value, "field": 1e20}
        assert quick_start([example]) == ""
        assert ">Example 1</summary>" in full_examples([example])
        assert "field: 1.0e+20\n" in full_examples([example])
    assert ">Example 1</summary>" in full_examples([[1], 2])


def test_plain_root_scalar_retains_open_ended_state():
    emitter = PsychEmitter(StringIO())
    emitter.root_context = True
    emitter.write_plain("root scalar")
    assert emitter.open_ended is True
    assert emitter._keep_document_end is False
