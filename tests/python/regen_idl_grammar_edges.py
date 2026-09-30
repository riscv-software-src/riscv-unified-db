# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Regenerate the frozen expectations in ``tests/python/data/idl/grammar_edges.json``.

This script is the *only* place that talks to the Ruby oracle
(``tests/python/ruby_idl_oracle.rb``) to produce test expectations. The corpus file itself
holds hand-curated ``{"id", "root", "text"}`` cases; this script fills in (or refreshes) the
``"expect"`` field for every case by asking the Ruby reference parser what it does with that
text, and writes the result back out.

Usage::

    cd <repo-root>
    mise exec -- bundle install               # once, to vendor the idlc gem's dependencies
    uv run python tests/python/regen_idl_grammar_edges.py

Requires ``mise`` and a working Ruby/Bundler toolchain (see ``bin/setup``). Never hand-edit the
``"expect"`` field of a case; edit ``"id"``/``"root"``/``"text"`` and rerun this script instead.
The pytest suite (``tests/python/test_idl_grammar_edges.py``) never calls Ruby: it only reads the
frozen JSON this script writes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUBY_ORACLE = Path(__file__).with_name("ruby_idl_oracle.rb")
DATA_FILE = Path(__file__).parent / "data" / "idl" / "grammar_edges.json"

# Batch size for a single Ruby invocation. Keeps process-startup overhead low without building
# one enormous JSON blob (the machine running this script may be memory constrained).
BATCH_SIZE = 40


def run_oracle(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run a batch of ``{"id", "root", "text"}`` cases through the Ruby oracle.

    Returns one result dict per case, in the same order, as produced by
    ``tests/python/ruby_idl_oracle.rb`` (see that file's header for the schema).
    """
    mise = shutil.which("mise")
    if mise is None:
        raise RuntimeError("mise is required to run the Ruby IDL oracle; see bin/setup")

    results: list[dict[str, Any]] = []
    for start in range(0, len(cases), BATCH_SIZE):
        batch = cases[start : start + BATCH_SIZE]
        payload = json.dumps(
            {"cases": [{"id": c["id"], "root": c["root"], "text": c["text"]} for c in batch]}
        )
        proc = subprocess.run(
            [mise, "exec", "--", "bundle", "exec", "ruby", str(RUBY_ORACLE)],
            cwd=REPOSITORY_ROOT,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Ruby IDL oracle failed on batch starting at {start}:\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        results.extend(json.loads(proc.stdout))
    return results


def regenerate(data_file: Path = DATA_FILE) -> None:
    doc = json.loads(data_file.read_text())
    cases = doc["cases"]

    ids = [c["id"] for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids in {data_file}: {sorted(duplicates)}")

    expectations = run_oracle(cases)
    if len(expectations) != len(cases):
        raise RuntimeError(f"oracle returned {len(expectations)} results for {len(cases)} cases")

    for case, expect in zip(cases, expectations, strict=True):
        case["expect"] = expect

    data_file.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    print(f"Regenerated {len(cases)} expectations in {data_file}")


if __name__ == "__main__":
    sys.exit(regenerate() or 0)
