# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Black-box grammar/AST differential tests for the Python IDL parser (``udb.idl.parser``).

Every expectation in ``tests/python/data/idl/grammar_edges.json`` is a reviewed, frozen capture
from the retired implementation. Nothing here talks to Ruby at test time, and the capture has no
refresh command.

This module goes through exactly two adapters so it can be pointed at the real parser API with a
one-line change once that API is final:

* ``_parse(root, text)`` -- returns a parsed node exposing ``.to_h()``, or raises the parser's
  syntax error exception.
* ``_error_position(exc)`` -- extracts ``(line, column)`` from that exception.

If ``udb.idl.parser`` cannot be imported at all, the whole module is skipped (the parser is being
developed concurrently by another agent).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip(
    "udb.idl.parser",
    reason="udb.idl.parser is not implemented yet (Stage 4 IDL parser slice)",
)

DATA_FILE = Path(__file__).parent / "data" / "idl" / "grammar_edges.json"


def _parse(root: str, text: str):
    """Adapter: return an object with .to_h(), or raise the parser's syntax error.

    Update this single function once the parser's public entry point is final.
    """
    from udb.idl import parser

    return parser.parse(text, root=root)  # PLACEHOLDER


def _error_position(exc: BaseException) -> tuple[int, int]:
    """Adapter: return (line, column) from the parser's syntax error exception.

    Update this single function once the exception shape is final.
    """
    return exc.line, exc.column  # type: ignore[attr-defined]  # PLACEHOLDER


def _load_cases() -> list[dict[str, Any]]:
    doc = json.loads(DATA_FILE.read_text())
    cases = doc["cases"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids in grammar_edges.json"
    return cases


CASES = _load_cases()
ACCEPTED_CASES = [c for c in CASES if c["expect"]["ok"]]
REJECTED_CASES = [c for c in CASES if not c["expect"]["ok"]]

# Top-level AST fields where Python intentionally differs from a confirmed Ruby bug
# (see doc/python-migration-bugfixes.md).
RUBY_BUG_CORRECTIONS: dict[str, dict[str, Any]] = {
    "lit_dec_signed": {"width": "7"},  # entry 18
}
ROUND_TRIP_CASES = [c for c in ACCEPTED_CASES if c["expect"].get("round_trip")]


# The Ruby oracle stamps every node's source "file" with the case id (it calls
# parser.set_input_file(case_id, ...)). The adapter signature above is (root, text) only -- it
# has no way to plumb a filename through -- so "file" is not a meaningful thing to compare: it is
# an arbitrary label chosen by whoever drives the parser, not something the grammar determines.
# Normalize it away on both sides before comparing, everything else (kind, fields, begin/end
# offsets) is compared exactly.
def _normalize_source_file(node: Any) -> Any:
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "source" and isinstance(value, dict) and "file" in value:
                out[key] = {**value, "file": "<normalized>"}
            else:
                out[key] = _normalize_source_file(value)
        return out
    if isinstance(node, list):
        return [_normalize_source_file(v) for v in node]
    return node


def _strip_source(node: Any) -> Any:
    """Remove all "source" keys recursively, for round-trip comparisons modulo spans."""
    if isinstance(node, dict):
        return {k: _strip_source(v) for k, v in node.items() if k != "source"}
    if isinstance(node, list):
        return [_strip_source(v) for v in node]
    return node


@pytest.mark.parametrize("case", ACCEPTED_CASES, ids=[c["id"] for c in ACCEPTED_CASES])
def test_accepted_case_matches_ruby_ast(case: dict[str, Any]) -> None:
    node = _parse(case["root"], case["text"])
    actual = _normalize_source_file(node.to_h())
    expected = _normalize_source_file(case["expect"]["ast"])
    for key, value in RUBY_BUG_CORRECTIONS.get(case["id"], {}).items():
        expected[key] = value
    assert actual == expected


@pytest.mark.parametrize("case", REJECTED_CASES, ids=[c["id"] for c in REJECTED_CASES])
def test_rejected_case_matches_ruby_failure_position(case: dict[str, Any]) -> None:
    with pytest.raises(Exception) as exc_info:  # exact exception type is not final yet
        _parse(case["root"], case["text"])
    line, column = _error_position(exc_info.value)
    assert (line, column) == (case["expect"]["line"], case["expect"]["column"])


@pytest.mark.parametrize("case", ROUND_TRIP_CASES, ids=[c["id"] for c in ROUND_TRIP_CASES])
def test_round_trip_via_to_idl(case: dict[str, Any]) -> None:
    """For cases where Ruby's to_idl() reparses to a structurally identical tree (modulo source
    spans), Python's to_idl() must do the same: reparsing it must reproduce the original to_h(),
    ignoring "source"."""
    node = _parse(case["root"], case["text"])
    original = _strip_source(node.to_h())

    reparsed = _parse(case["root"], node.to_idl())
    round_tripped = _strip_source(reparsed.to_h())

    assert round_tripped == original
