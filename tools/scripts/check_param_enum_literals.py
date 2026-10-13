#!/usr/bin/env python3
# Copyright (c) 2026 titoatwork
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Fail if IDL/YAML compares a string-enum parameter to a literal not in its enum.

Parameter files declare legal string values with schema.enum. Call sites
(CSR type() IDL, globals.isa, instruction operation() blocks) sometimes compare
those parameters to a string literal. A typo such as "always_zero" where the
enum only lists "always zero" is silently wrong: the comparison is always true
or always false, and no schema check catches it.

See https://github.com/riscv/riscv-unified-db/issues/2285

Only comparisons written on a single line are tested, and only with the
parameter on the left. "literal" op PARAM is legal IDL but does not currently
appear anywhere under spec/.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

YAML_SAFE = YAML(typ="safe")

# Regular expression to match either:
# - PARAM [op] "literal"
# - PARAM [op] 'literal'
# ... where "op" can be either "==" or "!=".
COMPARE_RE = re.compile(r"""\b([A-Z][A-Z0-9_]*)\s*(==|!=)\s*(?:"([^"]*)"|'([^']*)')""")


def load_param_string_enums(param_dir: Path) -> dict[str, set[str]]:
    """Map parameter name -> set of schema.enum string values."""
    enums: dict[str, set[str]] = {}
    if not param_dir.is_dir():
        return enums

    for path in sorted(param_dir.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as handle:
                doc = YAML_SAFE.load(handle)
        except (OSError, YAMLError) as exc:
            print(f"ERROR: could not load {path}: {exc}", file=sys.stderr)
            continue

        if not isinstance(doc, dict) or doc.get("kind") != "parameter":
            continue

        schema = doc.get("schema")
        if not isinstance(schema, dict):
            continue

        # Only string members matter here. Parameters that set enum without
        # type are included, since several real ones do.
        values = {v for v in schema.get("enum", []) if isinstance(v, str)}
        if values:
            enums[doc["name"]] = values

    return enums


def iter_scan_files(spec_root: Path) -> list[Path]:
    """Every ordinary file under spec/ whose name has an extension.

    .layout templates are scanned too. They are the source the generated
    instruction YAML comes from, and they do carry comparisons, so a typo in
    one should be reported against the file you can actually edit rather than
    against the generated copy that says not to edit it.
    """
    return sorted(p for p in spec_root.rglob("?*.?*") if p.is_file())


def find_invalid_compares(
    enums: dict[str, set[str]], files: list[Path]
) -> list[tuple[Path, int, str, str, str, str]]:
    """Return (path, line_no, param, op, literal, line_text) for bad compares."""
    bad: list[tuple[Path, int, str, str, str, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # Skip unreadable / binary-ish files under spec/.
            print(f"WARNING: could not read {path}: {exc}", file=sys.stderr)
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in COMPARE_RE.finditer(line):
                param = match.group(1)
                if param not in enums:
                    continue
                op = match.group(2)
                # group(3) is the double-quoted literal, group(4) the
                # single-quoted one. Exactly one of them matches.
                literal = match.group(3) if match.group(3) is not None else match.group(4)
                if literal in enums[param]:
                    continue
                bad.append((path, line_no, param, op, literal, line.strip()))
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=".",
        help="Repository root (default: current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    spec_root = root / "spec"
    param_dir = spec_root / "std" / "isa" / "param"

    if not param_dir.is_dir():
        print(f"ERROR: param directory not found: {param_dir}", file=sys.stderr)
        return 2

    enums = load_param_string_enums(param_dir)
    files = iter_scan_files(spec_root)
    bad = find_invalid_compares(enums, files)

    print(
        f"Checked {len(enums)} string-enum parameters across {len(files)} files under "
        f"spec/; found {len(bad)} invalid literal comparison(s)."
    )

    if not bad:
        print("OK: every PARAM ==/!= string literal is a member of that parameter's schema.enum.")
        return 0

    print("ERROR: string literal is not in the parameter's schema.enum:", file=sys.stderr)
    for path, line_no, param, op, literal, line in bad:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        allowed = ", ".join(repr(v) for v in sorted(enums[param]))
        print(f"  {rel}:{line_no}: {param} {op} {literal!r}", file=sys.stderr)
        print(f"    allowed: [{allowed}]", file=sys.stderr)
        print(f"    line: {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
