# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Progress events shared by library APIs and user interfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """One state update for a potentially long-running operation."""

    task: str
    description: str
    completed: int | None = None
    total: int | None = None
    finished: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


def report_progress(
    callback: ProgressCallback | None,
    task: str,
    description: str,
    *,
    completed: int | None = None,
    total: int | None = None,
    finished: bool = False,
) -> None:
    """Report progress when a caller supplied a callback."""

    if callback is not None:
        callback(
            ProgressEvent(
                task,
                description,
                completed=completed,
                total=total,
                finished=finished,
            )
        )
