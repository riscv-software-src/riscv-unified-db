# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import subprocess

from . import fixtures
from .common import ROOT, entrypoint, udb_command


def leaf_command(name: str, *, check: bool) -> list[str]:
    suffix = ["--check"] if check else []
    if name == "profile-configs":
        return udb_command("generate", "profile-configs", "-o", str(ROOT / "cfgs/profile"), *suffix)
    if name == "schema-docs":
        command = udb_command("generate", "schema-docs", "-o", str(ROOT / "doc/docs/schemas"))
        command.extend(suffix if check else ["--replace-current"])
        return command
    if name == "schemas":
        return udb_command("generate", "schema-bundle", "-o", str(ROOT / "gen/schemas"), *suffix)
    if name == "idl-grammar":
        return [
            "node",
            str(ROOT / "tools/node/idl-grammar-gen/index.js"),
            *(["--check"] if check else []),
        ]
    raise ValueError(name)


def run_leaf(name: str, *, check: bool) -> int:
    return subprocess.run(leaf_command(name, check=check), cwd=ROOT, check=False).returncode


def run_group(name: str, *, check: bool) -> int:
    leaves = ["idl-grammar"]
    if name == "all":
        leaves[1:1] = ["schemas", "profile-configs", "schema-docs"]
    for leaf in leaves:
        status = run_leaf(leaf, check=check)
        if status:
            return status
    if name == "all":
        return fixtures.refresh(list(fixtures.REGISTRY), check=check)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "name",
        choices=("all", "quick", "schemas", "profile-configs", "schema-docs", "idl-grammar"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    check = args.check or os.environ.get("usage_check") == "true"
    if args.name in {"all", "quick"}:
        return run_group(args.name, check=check)
    return run_leaf(args.name, check=check)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
