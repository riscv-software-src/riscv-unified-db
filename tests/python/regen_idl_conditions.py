# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Regenerate ``data/idl/conditions.json`` from the Ruby ``idl()`` condition oracle.

Collects every ``idl()`` condition in ``spec/std/isa`` and ``spec/custom/isa``
and records, per bundled configuration, Ruby's translation into a UDB
condition and its evaluation. Run with the Ruby toolchain available::

    mise exec --no-deps -- uv run python tests/python/regen_idl_conditions.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
ORACLE = Path(__file__).with_name("ruby_idl_condition_oracle.rb")
OUTPUT = Path(__file__).with_name("data") / "idl" / "conditions.json"
CONFIGS = ("_", "rv32", "rv64", "qc_iu")


def _find_idl_conditions(node: object, path: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "idl()" and isinstance(value, str):
                found.append(("/".join(path), value))
            else:
                found.extend(_find_idl_conditions(value, (*path, str(key))))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_find_idl_conditions(value, (*path, str(index))))
    return found


def collect_cases() -> list[dict[str, str]]:
    yaml = YAML(typ="safe")
    cases = []
    for spec in ("spec/std/isa", "spec/custom/isa"):
        for file in sorted((ROOT / spec).rglob("*.yaml")):
            document = yaml.load(file.read_text())
            relative = file.relative_to(ROOT).as_posix()
            for path, text in _find_idl_conditions(document):
                cases.append({"id": f"{relative}#{path}", "file": relative, "text": text})
    return cases


def main() -> int:
    cases = collect_cases()
    by_config = {}
    for config in CONFIGS:
        print(f"running Ruby oracle for {config} ({len(cases)} cases)", file=sys.stderr)
        completed = subprocess.run(
            [
                "mise",
                "exec",
                "--no-deps",
                "--",
                "bundle",
                "exec",
                "ruby",
                str(ORACLE),
                str(ROOT),
                config,
            ],
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        )
        by_config[config] = json.loads(completed.stdout)["results"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"cases": cases, "results": by_config}, indent=1, sort_keys=True) + "\n"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
