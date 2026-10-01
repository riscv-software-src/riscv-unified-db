# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from . import container
from .common import ROOT, entrypoint

CLEAN_PATHS = (
    "gen",
    ".stamps",
    "tests/isa/build",
    "tests/isa/build32",
    "tests/isa/build64",
)
CLOBBER_PATHS = (".venv", "node_modules", ".home", ".cache")


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def clean(root: Path = ROOT) -> None:
    for relative in CLEAN_PATHS:
        _remove(root / relative)


def clobber(root: Path = ROOT, *, remove_container: bool = False) -> int:
    clean(root)
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
        clean()
        return 0
    return clobber(remove_container=args.container)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
