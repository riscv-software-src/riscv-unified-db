# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Checked-in corpus tests for :mod:`udb.idl`.

Two independent corpora are exercised here without an external implementation:

* ``tests/python/data/idl/syntax/*.yaml`` -- a small, representative corpus
  (~50 cases spanning almost every AST node kind) whose expected ``to_h()``
  output is frozen so this test can run offline.
* ``tests/python/data/idl/{expressions.json,constraints.yaml}`` -- reviewed
  frozen expression, literal, and constraint inputs retained from the migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from udb import idl
from udb.idl import IdlSyntaxError, parse

SYNTAX_CORPUS_DIR = Path(__file__).with_name("data") / "idl" / "syntax"
IDL_DATA_DIR = Path(__file__).with_name("data") / "idl"

_yaml = YAML(typ="safe")


def _dump(node: idl.Node) -> dict[str, Any]:
    """Mirror the frozen capture serializer's special-casing:
    ``IncludeStatementAst#to_h`` did not support includes, so the capture uses
    ``{"kind": "include", "filename": ...}``, and ``IsaAst`` is dumped via its own
    ``source_yaml``-derived source rather than ``to_h()``'s default."""
    if isinstance(node, idl.IncludeStatement):
        return {"kind": "include", "filename": node.filename}
    if isinstance(node, idl.Isa):
        return {
            "kind": "isa",
            "children": [_dump(child) for child in node.children],
            "source": node.source.source_dict(node.start, node.end),
        }
    return node.to_h()


def _load_syntax_corpus_cases() -> list[tuple[str, dict[str, Any]]]:
    paths = sorted(SYNTAX_CORPUS_DIR.glob("*.yaml"))
    assert paths, f"no corpus files found under {SYNTAX_CORPUS_DIR}"
    return [(path.stem, _yaml.load(path.read_text(encoding="utf-8"))) for path in paths]


@pytest.mark.parametrize(
    "case_id,doc", _load_syntax_corpus_cases(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_checked_in_syntax_corpus(case_id: str, doc: dict[str, Any]) -> None:
    text = doc["input"]
    root = doc["root"]
    label = doc.get("label", case_id)
    if doc.get("rejected"):
        with pytest.raises(IdlSyntaxError):
            parse(text, root, label=label)
        return
    node = parse(text, root, label=label)
    assert _dump(node) == doc["expected"]


def _expression_inputs(prefix: str) -> list[str]:
    data = json.loads((IDL_DATA_DIR / "expressions.json").read_text(encoding="utf-8"))
    return [case["text"] for case in data["cases"] if case["id"].startswith(f"{prefix}:")]


def _constraint_inputs(key: str) -> list[str]:
    data = _yaml.load((IDL_DATA_DIR / "constraints.yaml").read_text(encoding="utf-8"))
    return [test["c"] for test in data[key]]


@pytest.mark.parametrize("expression", _expression_inputs("literals"))
def test_frozen_literals_parse(expression: str) -> None:
    parse(expression, "expression")


@pytest.mark.parametrize("expression", _expression_inputs("expressions"))
def test_frozen_expressions_parse(expression: str) -> None:
    parse(expression, "expression")


@pytest.mark.parametrize("constraint", _constraint_inputs("tests"))
def test_frozen_constraints_parse(constraint: str) -> None:
    parse(constraint, "constraint_body")


@pytest.mark.parametrize("constraint", _constraint_inputs("error_tests"))
def test_frozen_constraint_errors_parse(constraint: str) -> None:
    # These are syntactically valid implication statements that fail *type
    # checking* (a later migration slice) -- they must still parse cleanly.
    parse(constraint, "constraint_body")
