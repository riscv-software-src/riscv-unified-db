# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Side-effect-free, complete-batch prediction preflight."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specchoice_evidence.canonical import sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file, require_relative_posix_path

from .diagnostics import Diagnostic, ordered_diagnostics
from .strict_json import DuplicateKeyError, decode_strict_json, validate_current_payload


@dataclass(frozen=True)
class PreflightResult:
    status: str
    raw_prediction_sha256: str
    parsed_predictions: tuple[object, ...]
    diagnostics: tuple[Diagnostic, ...]

    def as_dict(self) -> dict[str, object]:
        blockers = [item.code for item in self.diagnostics if item.severity == "blocker"]
        value: dict[str, object] = {
            "blocking_diagnostics": blockers,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "raw_prediction_sha256": self.raw_prediction_sha256,
            "status": self.status,
        }
        if not blockers:
            value["parsed_predictions"] = list(self.parsed_predictions)
        return value


def _source_bytes_by_fixture(adapter_batch: object) -> dict[str, dict[str, bytes]]:
    """Read only adapter-declared fixture source files through bounded relative paths."""
    source_identity = getattr(adapter_batch, "source_identity", {})
    generation = source_identity.get("generation") if isinstance(source_identity, dict) else None
    if not isinstance(generation, str) or not generation or "/" in generation or "\\" in generation:
        return {}
    root = Path(__file__).parents[2] / "bundles" / "accepted" / generation
    values: dict[str, dict[str, bytes]] = {}
    for record in getattr(adapter_batch, "records", ()):
        for raw_file in record.raw_files:
            if raw_file.role != "fixture_source":
                continue
            try:
                relative = require_relative_posix_path(raw_file.path)
                evidence, raw = read_authoritative_file(root, relative.as_posix())
                if evidence.file_kind != "regular_file" or evidence.sha256 != raw_file.sha256:
                    continue
            except (FilesystemPolicyError, OSError, ValueError):
                continue
            if sha256_bytes(raw) == raw_file.sha256:
                values.setdefault(record.fixture_id, {})[raw_file.sha256] = raw
    return values


def _source_bytes_by_sha256(adapter_batch: object) -> dict[str, bytes]:
    """Compatibility view for scoring; preflight keeps fixture ownership separately."""
    return {
        digest: raw
        for values in _source_bytes_by_fixture(adapter_batch).values()
        for digest, raw in values.items()
    }


def preflight_prediction_batch(*, raw: bytes, adapter_batch: object, ingress: str) -> PreflightResult:
    """Collect all available blockers and make the one terminal score-eligibility decision."""
    raw_sha256 = sha256_bytes(raw)
    try:
        payload = decode_strict_json(raw)
    except UnicodeDecodeError:
        diagnostics = ordered_diagnostics([Diagnostic("JSON_NOT_UTF8", "blocker", field="payload")])
        return PreflightResult("invalid_preflight", raw_sha256, (), diagnostics)
    except DuplicateKeyError as error:
        diagnostics = ordered_diagnostics([Diagnostic("JSON_DUPLICATE_KEY", "blocker", field=str(error))])
        return PreflightResult("invalid_preflight", raw_sha256, (), diagnostics)
    except ValueError as error:
        code = "JSON_NONFINITE_CONSTANT" if str(error) in {"NaN", "Infinity", "-Infinity"} else "JSON_INVALID"
        diagnostics = ordered_diagnostics([Diagnostic(code, "blocker", field="payload")])
        return PreflightResult("invalid_preflight", raw_sha256, (), diagnostics)

    # Attach immutable byte views only for this pure validation call; no artifact is written.
    source_bytes_by_fixture = _source_bytes_by_fixture(adapter_batch)
    source_bytes = {
        digest: value
        for values in source_bytes_by_fixture.values()
        for digest, value in values.items()
    }
    source_paths_by_fixture = {
        record.fixture_id: {
            raw_file.path: raw_file.sha256
            for raw_file in record.raw_files
            if raw_file.role == "fixture_source"
            and raw_file.sha256 in source_bytes_by_fixture.get(record.fixture_id, {})
        }
        for record in getattr(adapter_batch, "records", ())
    }
    object.__setattr__(adapter_batch, "source_bytes_by_sha256", source_bytes) if False else None
    # Keep the adapter immutable: a narrow proxy supplies the verified source-byte index.
    class _BatchView:
        def __init__(self) -> None:
            self.adapter_batch_sha256 = getattr(adapter_batch, "adapter_batch_sha256", None)
            self.valid = getattr(adapter_batch, "valid", False)
            self.records = getattr(adapter_batch, "records", ())
            self.score_bearing_span_count = getattr(adapter_batch, "score_bearing_span_count", None)
            self.source_bytes_by_sha256 = source_bytes
            self.source_bytes_by_fixture = source_bytes_by_fixture
            self.source_paths_by_fixture = source_paths_by_fixture

    parsed = validate_current_payload(payload, adapter_batch=_BatchView(), ingress=ingress)
    diagnostics = ordered_diagnostics(parsed.diagnostics)
    blockers = any(item.severity == "blocker" for item in diagnostics)
    if blockers:
        return PreflightResult("invalid_preflight", raw_sha256, (), diagnostics)
    status = "completed_with_warnings" if diagnostics else "valid_preflight"
    return PreflightResult(status, raw_sha256, parsed.predictions, diagnostics)
