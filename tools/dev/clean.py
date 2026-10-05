# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from . import container
from .common import ROOT, DevError, entrypoint

CLEAN_PATHS = ("gen", ".stamps")
CLOBBER_PATHS = (".venv", "node_modules", ".home", ".cache")


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def isa_clean_commands(root: Path = ROOT) -> tuple[tuple[str, ...], ...]:
    tests = str(root / "tests/isa")
    return (
        ("make", "-C", tests, "clean"),
        ("make", "-C", tests, "XLEN=32", "clean"),
    )


def clean(root: Path = ROOT) -> int:
    for relative in CLEAN_PATHS:
        _remove(root / relative)
    for command in isa_clean_commands(root):
        try:
            result = subprocess.run(command, cwd=root, check=False)
        except OSError as error:
            raise DevError(f"failed to run {' '.join(command)}: {error}") from error
        if result.returncode:
            return result.returncode
    return 0


def clobber(root: Path = ROOT, *, remove_container: bool = False) -> int:
    status = clean(root)
    if status:
        return status
    for relative in CLOBBER_PATHS:
        _remove(root / relative)
    if remove_container:
        return container.execute("remove", root=root)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("clean", "clobber"))
    parser.add_argument("--container", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "clean":
        return clean()
    return clobber(remove_container=args.container)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
