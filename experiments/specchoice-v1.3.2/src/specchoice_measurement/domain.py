# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Frozen Phase 2 adapter records and terminal result contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    fixture_id: str = ""
    field: str = ""
    occurrence: int = 0
    expected: object | None = None
    observed: object | None = None
    source_sha256: str | None = None
    source_hashes: dict[str, str] | None = None

    def sort_key(self) -> tuple[int, str, str, str, int]:
        return ({"blocker": 0, "warning": 1}[self.severity], self.code, self.fixture_id, self.field, self.occurrence)

    def as_dict(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value not in (None, "", 0)}


@dataclass(frozen=True)
class RawFileIdentity:
    path: str
    role: str
    byte_length: int
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalFixtureRecord:
    fixture_id: str
    category: str
    adapter_version: str
    rule_sha256: str
    source_identity: dict[str, str]
    raw_files: tuple[RawFileIdentity, ...]
    original_score_bearing: dict[str, object]
    expect_extract: bool
    expected_parameter_count: int
    expected_parameter_names: tuple[str, ...]
    evidence_required: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "adapter_version": self.adapter_version,
            "category": self.category,
            "evidence_required": self.evidence_required,
            "expect_extract": self.expect_extract,
            "expected_parameter_count": self.expected_parameter_count,
            "expected_parameter_names": list(self.expected_parameter_names),
            "fixture_id": self.fixture_id,
            "original_score_bearing": self.original_score_bearing,
            "raw_files": [item.as_dict() for item in self.raw_files],
            "rule_sha256": self.rule_sha256,
            "source_identity": self.source_identity,
        }


@dataclass(frozen=True)
class AdapterBatch:
    adapter_version: str
    rule_sha256: str
    source_identity: dict[str, str]
    records: tuple[CanonicalFixtureRecord, ...]
    diagnostics: tuple[Diagnostic, ...]
    adapter_batch_sha256: str
    # Successor adapters freeze the evidence population from their bound golden
    # artifact.  It is runtime validation state, not part of the legacy batch
    # projection (and therefore does not rewrite historical batch identities).
    score_bearing_span_count: int | None = None

    @property
    def valid(self) -> bool:
        return not any(item.severity == "blocker" for item in self.diagnostics)

    def canonical_projection(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "records": [item.as_dict() for item in self.records],
            "rule_sha256": self.rule_sha256,
            "source_identity": self.source_identity,
            "valid": self.valid,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"adapter_batch_sha256": self.adapter_batch_sha256, **self.canonical_projection()}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @classmethod
    def from_parts(
        cls,
        *,
        adapter_version: str,
        rule_sha256: str,
        source_identity: dict[str, str],
        records: tuple[CanonicalFixtureRecord, ...],
        diagnostics: tuple[Diagnostic, ...],
    ) -> "AdapterBatch":
        ordered_diagnostics = tuple(sorted(diagnostics, key=Diagnostic.sort_key))
        ordered_records = tuple(sorted(records, key=lambda item: item.fixture_id))
        projection = {
            "adapter_version": adapter_version,
            "diagnostics": [item.as_dict() for item in ordered_diagnostics],
            "records": [item.as_dict() for item in ordered_records],
            "rule_sha256": rule_sha256,
            "source_identity": source_identity,
            "valid": not any(item.severity == "blocker" for item in ordered_diagnostics),
        }
        return cls(
            adapter_version=adapter_version,
            rule_sha256=rule_sha256,
            source_identity=source_identity,
            records=ordered_records,
            diagnostics=ordered_diagnostics,
            adapter_batch_sha256=sha256_bytes(canonical_json_bytes(projection)),
        )
