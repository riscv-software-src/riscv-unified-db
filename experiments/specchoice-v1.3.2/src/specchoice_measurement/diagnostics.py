# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Stable Phase 2 diagnostic records and the one declared total ordering."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SEVERITY_RANK = {"blocker": 0, "warning": 1}


@dataclass(frozen=True)
class Diagnostic:
    """A serializable diagnostic whose ordering cannot depend on input traversal."""

    code: str
    severity: str
    fixture_id: str | None = None
    field: str = ""
    finding_id: str | None = None
    occurrence: int = 0
    expected: object | None = None
    observed: object | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_RANK:
            raise ValueError("DIAGNOSTIC_SEVERITY_INVALID")

    def sort_key(self) -> tuple[int, str, str, str, int]:
        return (
            SEVERITY_RANK[self.severity],
            self.code,
            self.fixture_id or "",
            self.field,
            self.occurrence,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def ordered_diagnostics(items: list[Diagnostic] | tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    """Return the sole deterministic collection order for diagnostic output."""
    return tuple(sorted(items, key=Diagnostic.sort_key))
