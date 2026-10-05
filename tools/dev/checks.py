# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import fixtures, quality
from .common import ROOT, entrypoint, python_command, udb_command


def command_for(name: str, *, config: str = "_") -> list[str]:
    commands = {
        "data": udb_command("validate", "data"),
        "encodings": udb_command("validate", "encodings"),
        "csrs": udb_command("validate", "csrs"),
        "idl": udb_command("validate", "idl", "-c", config),
        "layouts": udb_command("author", "layouts", "--root", str(ROOT), "--check"),
        "schema-versions": python_command(str(ROOT / "tools/scripts/check_schema_versions.py")),
    }
    return commands[name]


def run_one(name: str, *, config: str = "_") -> int:
    if name == "fixtures":
        return fixtures.refresh(list(fixtures.REGISTRY), check=True)
    if name == "quality":
        commands = quality.lint_commands([], True)
        commands.extend(quality.format_commands([], True, check=True))
        return quality.execute(commands)
    return subprocess.run(command_for(name, config=config), cwd=ROOT, check=False).returncode


def run_all(jobs: int) -> int:
    names = [
        "quality",
        "data",
        "encodings",
        "csrs",
        "idl",
        "layouts",
        "fixtures",
    ]
    with ThreadPoolExecutor(max_workers=min(jobs, len(names))) as executor:
        statuses = list(executor.map(run_one, names))
    return next((status for status in statuses if status), 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "name",
        choices=("all", "data", "encodings", "csrs", "idl", "layouts", "schema-versions"),
    )
    parser.add_argument("-c", "--config", default=os.environ.get("usage_config", "_"))
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=int(os.environ.get("usage_jobs") or (os.cpu_count() or 1)),
    )
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.name == "all":
        return run_all(args.jobs)
    return run_one(args.name, config=args.config)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
