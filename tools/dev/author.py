# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from .common import ROOT, DevError, entrypoint

VALID_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def create_rvtest(name: str, root: Path = ROOT) -> int:
    if not VALID_NAME.fullmatch(name):
        raise DevError("test name may contain only letters, numbers, '.', '-', and '_'", 2)
    destinations = {
        64: root / "tests/isa/rv64uv" / f"{name}.S",
        32: root / "tests/isa/rv32uv" / f"{name}.S",
    }
    existing = [str(path) for path in destinations.values() if path.exists()]
    if existing:
        raise DevError(f"refusing to overwrite existing test: {', '.join(existing)}", 1)
    sources = {
        xlen: root / "tools/scripts" / f"new-rvtest-{xlen}-template.S" for xlen in destinations
    }
    makefrags = {
        xlen: destination.parent / "Makefrag" for xlen, destination in destinations.items()
    }
    for source in sources.values():
        if not source.is_file():
            raise DevError(f"missing template: {source}", 2)
    for makefrag in makefrags.values():
        if not makefrag.is_file():
            raise DevError(f"missing Makefrag: {makefrag}", 2)
    for xlen, destination in destinations.items():
        source = sources[xlen]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            source.read_text(encoding="utf-8").replace("__INSTR__", name),
            encoding="utf-8",
        )
        makefrag = makefrags[xlen]
        marker = f"rv{xlen}uv_sc_tests ="
        text = makefrag.read_text(encoding="utf-8")
        if marker not in text:
            raise DevError(f"missing '{marker}' in {makefrag}", 2)
        makefrag.write_text(text.replace(marker, f"{marker} {name}", 1), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?")
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    name = args.name or os.environ.get("usage_name")
    if not name:
        parser.error("NAME is required")
    root = args.root or Path(os.environ.get("usage_root") or ROOT)
    return create_rvtest(name, root)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))
