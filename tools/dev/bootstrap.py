# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from . import container
from .common import ROOT


def choose_toolchain(requested: str, root: Path = ROOT) -> str:
    if requested != "auto":
        return requested
    local = root / ".toolchain-local"
    if local.exists():
        text = local.read_text(encoding="utf-8")
        if "UDB_TOOLCHAIN_NONE=1" in text:
            return "none"
        if "UDB_TOOLCHAIN_CONTAINER=1" in text:
            return "container"
        return "native"
    if container.find_runtime():
        return "container"
    if shutil.which("g++") or shutil.which("clang++"):
        return "native"
    return "none"


def setup_commands(
    *, root: Path = ROOT, toolchain: str = "auto", hooks: bool = True
) -> tuple[str, list[list[str]]]:
    selected = choose_toolchain(toolchain, root)
    commands: list[list[str]] = []
    if hooks:
        commands.append(["prek", "install", "--prepare-hooks"])
    if selected == "container":
        command = container.command_for("pull", root=root)
        if command is not None:
            commands.append(command)
    return selected, commands


def write_toolchain_preference(selected: str, root: Path = ROOT) -> None:
    value = {
        "container": "UDB_TOOLCHAIN_CONTAINER=1\n",
        "native": "UDB_TOOLCHAIN_CONTAINER=0\n",
        "none": "UDB_TOOLCHAIN_NONE=1\n",
    }[selected]
    (root / ".toolchain-local").write_text(value, encoding="utf-8")


def setup(*, toolchain: str, hooks: bool, root: Path = ROOT) -> int:
    selected, commands = setup_commands(root=root, toolchain=toolchain, hooks=hooks)
    for command in commands:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    write_toolchain_preference(selected, root)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--toolchain", choices=("auto", "container", "native", "none"), default="auto"
    )
    parser.add_argument("--no-hooks", action="store_true")
    args = parser.parse_args(argv)
    return setup(toolchain=args.toolchain, hooks=not args.no_hooks)


if __name__ == "__main__":
    raise SystemExit(main())
