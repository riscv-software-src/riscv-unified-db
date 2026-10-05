# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path

from .common import ROOT, entrypoint, python_command, udb_command


def selected_files(files: list[str], all_files: bool) -> list[str]:
    if files:
        return files
    command = ["git", "ls-files"] if all_files else ["git", "diff", "--name-only", "HEAD"]
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def lint_commands(files: list[str], all_files: bool) -> list[list[str]]:
    chosen = selected_files(files, all_files)
    python_files = [path for path in chosen if path.endswith(".py")]
    shell_files = [path for path in chosen if path.endswith(".sh") or path.startswith("bin/")]
    commands: list[list[str]] = []
    if python_files:
        commands.append(python_command("-m", "ruff", "check", *python_files))
    if shell_files:
        commands.append(["shellcheck", *shell_files])
    commands.extend(
        [
            ["reuse", "lint"],
            udb_command("validate", "data"),
            udb_command("validate", "idl", "-c", "_"),
        ]
    )
    return commands


def format_commands(files: list[str], all_files: bool, *, check: bool) -> list[list[str]]:
    chosen = selected_files(files, all_files)
    python_files = [path for path in chosen if path.endswith(".py")]
    prettier_files = [
        path for path in chosen if Path(path).suffix in {".json", ".toml", ".yaml", ".yml"}
    ]
    shell_files = [path for path in chosen if path.endswith(".sh") or path.startswith("bin/")]
    native_files = [
        path for path in chosen if Path(path).suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}
    ]
    commands: list[list[str]] = []
    if python_files:
        command = python_command("-m", "ruff", "format")
        if check:
            command.append("--check")
        commands.append([*command, *python_files])
    if prettier_files:
        commands.append(["npx", "prettier", "--check" if check else "--write", *prettier_files])
    if shell_files:
        commands.append(["shfmt", "-d" if check else "-w", *shell_files])
    if native_files:
        option = ["--dry-run", "--Werror"] if check else ["-i"]
        commands.append(["clang-format", *option, *native_files])
    return commands


def execute(commands: list[list[str]]) -> int:
    for command in commands:
        status = subprocess.run(command, cwd=ROOT, check=False).returncode
        if status:
            return status
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("lint", "format"))
    parser.add_argument("files", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = args.files or shlex.split(os.environ.get("usage_files", ""))
    all_files = args.all or os.environ.get("usage_all") == "true"
    check = args.check or os.environ.get("usage_check") == "true"
    if files and all_files:
        parser.error("choose FILES or --all")
    commands = (
        lint_commands(files, all_files)
        if args.action == "lint"
        else format_commands(files, all_files, check=check)
    )
    return execute(commands)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
