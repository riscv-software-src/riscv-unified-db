# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Non-Ruby checked-in corpus tests for :mod:`udb.idl`.

Two independent corpora are exercised here, neither of which requires the
live Ruby oracle at test time (unlike ``test_idl_parity.py``):

* ``tests/python/data/idl/syntax/*.yaml`` -- a small, representative corpus
  (~50 cases spanning almost every AST node kind) whose expected ``to_h()``
  output was *generated* from the live Ruby oracle (see
  ``generate_corpus.py`` mentioned in the migration report) but is checked
  in so this test can run offline.
* ``tools/ruby-gems/idlc/test/idl/{literals,expressions,constraints,
  constraint_errors}.yaml`` -- the idlc gem's own hand-written test data.
  Their ``=``/``r`` fields describe *semantic* results (evaluated
  ``to_idl()`` normal forms, constraint satisfiability) that are out of
  scope for this syntax-only slice, so only parse *acceptance* is checked:
  every ``e``/``c`` input must parse successfully as the appropriate root
  (``constraint_errors.yaml``'s inputs are syntactically valid implication
  statements that fail *type checking*, a later slice, so they must parse
  too).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from udb import idl
from udb.idl import IdlSyntaxError, parse

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SYNTAX_CORPUS_DIR = Path(__file__).with_name("data") / "idl" / "syntax"
IDLC_TEST_DATA_DIR = REPOSITORY_ROOT / "tools/ruby-gems/idlc/test/idl"

_yaml = YAML(typ="safe")


def _dump(node: idl.Node) -> dict[str, Any]:
    """Mirror ``ruby_idl_oracle.rb``'s ``dump`` special-casing (see
    ``test_idl_parity.py``'s identical helper): ``IncludeStatementAst#to_h``
    raises in Ruby, so the oracle special-cases it to ``{"kind": "include",
    "filename": ...}``, and ``IsaAst`` is dumped via its own
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


def _idlc_expression_inputs(filename: str) -> list[str]:
    data = _yaml.load((IDLC_TEST_DATA_DIR / filename).read_text(encoding="utf-8"))
    return [test["e"] for test in data["tests"]]


def _idlc_constraint_inputs(filename: str) -> list[str]:
    data = _yaml.load((IDLC_TEST_DATA_DIR / filename).read_text(encoding="utf-8"))
    return [test["c"] for test in data["tests"]]


@pytest.mark.parametrize("expression", _idlc_expression_inputs("literals.yaml"))
def test_idlc_literals_data_file_parses(expression: str) -> None:
    parse(expression, "expression")


@pytest.mark.parametrize("expression", _idlc_expression_inputs("expressions.yaml"))
def test_idlc_expressions_data_file_parses(expression: str) -> None:
    parse(expression, "expression")


@pytest.mark.parametrize("constraint", _idlc_constraint_inputs("constraints.yaml"))
def test_idlc_constraints_data_file_parses(constraint: str) -> None:
    parse(constraint, "constraint_body")


@pytest.mark.parametrize("constraint", _idlc_constraint_inputs("constraint_errors.yaml"))
def test_idlc_constraint_errors_data_file_parses(constraint: str) -> None:
    # These are syntactically valid implication statements that fail *type
    # checking* (a later migration slice) -- they must still parse cleanly.
    parse(constraint, "constraint_body")
