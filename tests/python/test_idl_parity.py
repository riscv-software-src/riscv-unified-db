# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Differential test: Python IDL parser vs. the live Ruby ``idlc`` parser.

Extracts every IDL string embedded in the standard and custom architecture
databases (``spec/std/isa`` and ``spec/custom/isa``) plus every top-level
``isa``-root file under ``spec/std/isa/isa/`` (and, for extra coverage, any
equivalent files under ``spec/custom/isa``), runs them all through the Ruby
oracle (``ruby_idl_oracle.rb``) once, and asserts the Python parser produces
byte-identical ``to_h()`` output for every case.

Gated behind ``UDB_TEST_RUBY=1`` (see ``test_conditions.py`` for the same
pattern) since it shells out to ``mise exec -- bundle exec ruby``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from udb import idl
from udb.source import parse_yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_oracle.rb")

# Maps a YAML key suffix to the grammar root it must be parsed as. Every other
# ``xxx()``-suffixed string key (``sw_write(csr_value)``, ``when()``,
# ``register_length()``, plain ``xxx()``, ...) is a ``function_body``.
_KEY_ROOTS = {
    "operation()": "instruction_operation",
    "idl()": "constraint_body",
}


def _walk_idl_strings(
    value: Any, path: tuple[object, ...], record_id: str, out: list[dict[str, str]]
) -> None:
    """Recursively collect every ``xxx()``-suffixed string leaf in a raw YAML document.

    Mirrors the reference extraction approach used to precompute this
    project's oracle fixtures: any mapping key that ends in ``)`` and
    contains ``(``, whose value is a string, is an embedded IDL snippet.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.endswith(")") and "(" in key and isinstance(child, str):
                case_path = "/".join(str(part) for part in (*path, key))
                out.append(
                    {
                        "id": f"{record_id}#{case_path}",
                        "root": _KEY_ROOTS.get(key, "function_body"),
                        "text": child,
                    }
                )
            else:
                _walk_idl_strings(child, (*path, key), record_id, out)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_idl_strings(child, (*path, index), record_id, out)


def _extract_embedded_idl_cases(root_dir: Path) -> list[dict[str, str]]:
    """Extract every embedded IDL string from every YAML file under ``root_dir``.

    Uses a schema-independent raw YAML walk (``udb.source.parse_yaml``)
    rather than :class:`udb.database.Database`, since ``spec/custom/isa``
    contains partial JSON-merge-patch overlay documents (missing required
    fields such as ``name``) that ``Database.from_path`` rejects outright.
    """
    cases: list[dict[str, str]] = []
    for path in sorted(root_dir.rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        parsed = parse_yaml(text, source=str(path))
        _walk_idl_strings(parsed.value, (), str(path.relative_to(root_dir.parent)), cases)
    return cases


def _extract_isa_root_cases(isa_dir: Path) -> list[dict[str, str]]:
    """Every file directly inside an ``isa/`` directory is a whole ``isa``-root document."""
    cases = []
    for path in sorted(p for p in isa_dir.iterdir() if p.is_file()):
        cases.append(
            {
                "id": str(path.relative_to(isa_dir.parent.parent)),
                "root": "isa",
                "text": path.read_text(encoding="utf-8"),
            }
        )
    return cases


def _all_database_cases() -> list[dict[str, str]]:
    cases = _extract_embedded_idl_cases(REPOSITORY_ROOT / "spec/std/isa")
    cases += _extract_embedded_idl_cases(REPOSITORY_ROOT / "spec/custom/isa")
    cases += _extract_isa_root_cases(REPOSITORY_ROOT / "spec/std/isa/isa")
    for isa_dir in sorted((REPOSITORY_ROOT / "spec/custom/isa").glob("**/isa")):
        if isa_dir.is_dir():
            cases += _extract_isa_root_cases(isa_dir)
    return cases


# A few deliberately-invalid inputs (one per root) that neither implementation
# should accept, used to cross-check syntax-error reporting.
_INVALID_CASES = [
    {
        "id": "<invalid function_body: missing semicolon>",
        "root": "function_body",
        "text": "X[rd] = X[rs1] + X[rs2]",
    },
    {"id": "<invalid expression: dangling operator>", "root": "expression", "text": "1 + "},
    {"id": "<invalid expression: unbalanced paren>", "root": "expression", "text": "(1 + 2"},
    {
        "id": "<invalid function_body: unclosed string>",
        "root": "function_body",
        "text": 'String s = "unterminated;',
    },
    {
        "id": "<invalid function_body: bits template ambiguity>",
        "root": "function_body",
        "text": "Bits<1 == (2 > 1)> x = 5;",
    },
    {"id": "<invalid constraint_body: empty>", "root": "constraint_body", "text": ""},
    {
        "id": "<invalid for_loop: missing condition>",
        "root": "for_loop",
        "text": "for (U32 i = 0; ; i++) {}",
    },
    {"id": "<invalid isa: garbage>", "root": "isa", "text": "%version: 1.0\n@@@ not idl @@@"},
]


def _dump(node: idl.Node) -> dict[str, Any]:
    """Mirror ``ruby_idl_oracle.rb``'s ``dump``: special-case the two node kinds
    whose Ruby ``to_h`` cannot be called directly (``IncludeStatementAst``
    raises, and ``IsaAst`` needs its own ``source_yaml``-based source)."""
    if isinstance(node, idl.IncludeStatement):
        return {"kind": "include", "filename": node.filename}
    if isinstance(node, idl.Isa):
        return {
            "kind": "isa",
            "children": [_dump(child) for child in node.children],
            "source": node.source.source_dict(node.start, node.end),
        }
    return node.to_h()


def _run_ruby_oracle(cases: list[dict[str, str]]) -> list[dict[str, Any]]:
    mise = shutil.which("mise")
    if mise is None:
        pytest.fail("UDB_TEST_RUBY=1 requires mise and the repository Ruby toolchain")
    result = subprocess.run(
        [mise, "exec", "--no-deps", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
        cwd=REPOSITORY_ROOT,
        input=json.dumps({"cases": cases}),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Ruby IDL oracle failed:\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def database_cases() -> list[dict[str, str]]:
    return _all_database_cases()


@pytest.fixture(scope="module")
def database_oracle_results(database_cases: list[dict[str, str]]) -> list[dict[str, Any]]:
    return _run_ruby_oracle(database_cases)


pytestmark = pytest.mark.skipif(
    os.environ.get("UDB_TEST_RUBY") != "1",
    reason="set UDB_TEST_RUBY=1 to compare IDL parsing with the Ruby implementation",
)


def test_idl_syntax_matches_ruby_oracle_for_the_full_database(
    database_cases: list[dict[str, str]], database_oracle_results: list[dict[str, Any]]
) -> None:
    assert len(database_cases) >= 3900, "sanity check: extraction should cover the whole corpus"
    mismatches: list[tuple[str, str, Any, Any]] = []
    errors: list[tuple[str, str, str]] = []

    for case, oracle in zip(database_cases, database_oracle_results, strict=True):
        case_id, root, text = case["id"], case["root"], case["text"]
        try:
            node = idl.parse(text, root, label=case_id)
        except idl.IdlSyntaxError as error:
            if oracle.get("ok"):
                errors.append((case_id, root, f"python rejected, ruby accepted: {error}"))
            continue
        if not oracle.get("ok"):
            errors.append((case_id, root, "python accepted, ruby rejected"))
            continue
        python_h = _dump(node)
        ruby_h = oracle["ast"]
        if python_h != ruby_h:
            mismatches.append((case_id, root, python_h, ruby_h))

    if errors or mismatches:
        lines = [f"{len(errors)} acceptance disagreements, {len(mismatches)} to_h() mismatches"]
        for case_id, root, message in errors[:5]:
            lines.append(f"  ERROR {root} {case_id}: {message}")
        for case_id, root, python_h, ruby_h in mismatches[:5]:
            lines.append(
                f"  MISMATCH {root} {case_id}\n    python={python_h!r}\n    ruby  ={ruby_h!r}"
            )
        pytest.fail("\n".join(lines))


def test_invalid_idl_inputs_are_rejected_by_both_implementations() -> None:
    oracle_results = _run_ruby_oracle(_INVALID_CASES)
    for case, oracle in zip(_INVALID_CASES, oracle_results, strict=True):
        assert not oracle.get("ok"), f"expected ruby to reject {case['id']!r} but it was accepted"
        with pytest.raises(idl.IdlSyntaxError) as excinfo:
            idl.parse(case["text"], case["root"], label=case["id"])
        # Treetop's failure_line is 1-based and directly comparable to ours;
        # failure_index/column are Treetop-internal and not guaranteed to be
        # identical bookkeeping (e.g. Treetop reports the position after
        # skipped trailing whitespace in some alternatives), so we only
        # assert the (always load-bearing) line number matches.
        assert excinfo.value.line == oracle["line"], (
            f"{case['id']}: python failed at line {excinfo.value.line}, ruby at line {oracle['line']}"
        )
