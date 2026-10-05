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

from udb.resolver import YamlResolver

REPO_ROOT = Path(__file__).parents[2]
ISA_ROOT = REPO_ROOT / "spec" / "std" / "isa"
RUBY_ORACLE = Path(__file__).with_name("ruby_resolution_oracle.rb")

_KNOWN_RUBY_PROVENANCE_DEFECTS = {
    "inst_type/I.yaml/opcodes/$parent_of": (
        "inst_subtype/I/I-x-x.yaml#/data/opcodes",
        "<missing>",
    ),
    "inst_type/R.yaml/opcodes/$parent_of": (
        "inst_subtype/R/R-x.yaml#/data/opcodes",
        "<missing>",
    ),
    "inst_var/I-imm.yaml/data/$parent_of": (
        "inst_subtype/I/I-x-x.yaml#/data/variables/imm",
        "<missing>",
    ),
    "inst_var/xd.yaml/data/$parent_of": (
        [
            "inst_subtype/I/I-x-x.yaml#/data/variables/xd",
            "inst_subtype/R/R-x.yaml#/data/variables/xd",
        ],
        "<missing>",
    ),
    "inst_var/xs1.yaml/data/$parent_of": (
        [
            "inst_subtype/I/I-x-x.yaml#/data/variables/xs1",
            "inst_subtype/R/R-x.yaml#/data/variables/xs1",
        ],
        "<missing>",
    ),
    "inst_var/xs2.yaml/data/$parent_of": (
        "inst_subtype/R/R-x.yaml#/data/variables/xs2",
        "<missing>",
    ),
    "profile/RVA20U64.yaml/extensions/$parent_of": (
        [
            "profile/RVA20S64.yaml#/extensions",
            "profile/RVA22U64.yaml#/extensions",
        ],
        "profile/RVA22U64.yaml#/extensions",
    ),
    "profile/RVA22U64.yaml/extensions/$parent_of": (
        [
            "profile/RVA22S64.yaml#/extensions",
            "profile/RVB23U64.yaml#/extensions",
        ],
        "profile/RVB23U64.yaml#/extensions",
    ),
    "profile/RVA23U64.yaml/extensions/$parent_of": (
        "profile/RVA23S64.yaml#/extensions",
        "<missing>",
    ),
    "profile/RVB23S64.yaml/extensions/$parent_of": (
        "profile/RVA23S64.yaml#/extensions",
        "<missing>",
    ),
    "profile/RVB23U64.yaml/extensions/$parent_of": (
        [
            "profile/RVA23U64.yaml#/extensions",
            "profile/RVB23S64.yaml#/extensions",
        ],
        "<missing>",
    ),
    "profile/RVI20U64.yaml/extensions/$parent_of": (
        "profile/RVA20U64.yaml#/extensions",
        "<missing>",
    ),
}


def _load_documents(root: Path) -> dict[str, dict]:
    yaml = YAML(typ="safe")
    documents = {}
    for path in sorted(root.rglob("*.yaml")):
        relative = path.relative_to(root).as_posix()
        with path.open(encoding="utf-8") as stream:
            documents[relative] = yaml.load(stream)
    return documents


def _canonicalize(value):
    if isinstance(value, dict):
        canonical = {}
        for key, item in value.items():
            if key == "$source":
                continue
            if key == "$schema" and isinstance(item, str):
                schema_name = Path(item.split("#", 1)[0]).name
                canonical[key] = f"{schema_name}#"
            else:
                canonical[key] = _canonicalize(item)
        return canonical
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _differences(left, right, path=()):
    if type(left) is not type(right):
        return {"/".join(map(str, path)): (left, right)}
    if isinstance(left, dict):
        differences = {}
        for key in sorted(set(left) | set(right), key=str):
            child_path = (*path, key)
            if key not in left:
                differences["/".join(map(str, child_path))] = ("<missing>", right[key])
            elif key not in right:
                differences["/".join(map(str, child_path))] = (left[key], "<missing>")
            else:
                differences.update(_differences(left[key], right[key], child_path))
        return differences
    if isinstance(left, list):
        if len(left) != len(right):
            return {"/".join(map(str, (*path, "length"))): (len(left), len(right))}
        differences = {}
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            differences.update(_differences(left_item, right_item, (*path, index)))
        return differences
    return {} if left == right else {"/".join(map(str, path)): (left, right)}


@pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to run the transitional Ruby parity oracle",
)
def test_full_standard_database_matches_ruby_without_idl(tmp_path: Path) -> None:
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")

    ruby_output = tmp_path / "ruby"
    result = subprocess.run(
        [
            mise,
            "exec",
            "--",
            "bundle",
            "exec",
            "ruby",
            str(RUBY_ORACLE),
            str(ISA_ROOT),
            str(ruby_output),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby resolution oracle failed:\n{result.stdout}\n{result.stderr}")

    source_documents = _load_documents(ISA_ROOT)
    ruby_documents = json.loads((ruby_output / "oracle.json").read_text(encoding="utf-8"))
    python_documents = YamlResolver(source_documents).resolve()

    assert source_documents
    assert python_documents.keys() == ruby_documents.keys()
    differences = _differences(
        _canonicalize(python_documents),
        _canonicalize(ruby_documents),
    )
    assert differences == _KNOWN_RUBY_PROVENANCE_DEFECTS
