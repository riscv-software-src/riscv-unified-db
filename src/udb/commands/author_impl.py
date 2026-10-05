# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Implement installed layout authoring."""

from __future__ import annotations

from pathlib import Path

from ..progress import ProgressCallback


def run_author(
    root: Path,
    *,
    source_root: Path | None,
    collections: list[str],
    check: bool,
    progress: ProgressCallback | None = None,
) -> int:
    from ..layout_collections import get_layout_collection
    from ..layouts import generate_layouts

    names = collections or ["standard"]
    selected = tuple(get_layout_collection("qc_iu" if name == "qc-iu" else name) for name in names)
    drift = generate_layouts(
        root,
        source_root=source_root,
        collections=selected,
        check=check,
        progress=progress,
    )
    if check:
        for path in drift:
            print(path)
    return 1 if check and drift else 0
