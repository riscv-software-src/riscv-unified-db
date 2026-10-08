# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Lossless raw-JSON decoding and closed canonical-adjudication validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from specchoice_evidence.canonical import canonical_json_bytes

from .diagnostics import Diagnostic


SCHEMA_VERSION = "canonical-adjudication-v1"
SCHEMA_VERSION_V3 = "canonical-adjudication-v3"
CURRENT_INGRESS = "current-v1"
CURRENT_INGRESS_V3 = "current-v3"
LEGACY_INGRESS = "legacy-pr2164-v1"
_PAYLOAD_KEYS = frozenset({"schema_version", "adapter_batch_sha256", "predictions"})
_PREDICTION_KEYS = frozenset({"fixture_id", "finding_id", "rationale", "adjudication"})
_ADJUDICATION_KEYS = frozenset({"surfaced", "parameter_status", "proposed_name", "evidence_spans"})
_SPAN_KEYS = frozenset({"source_sha256", "start_byte", "end_byte", "text"})
_SPAN_KEYS_V3 = frozenset({
    "dimension", "source_path", "source_sha256", "start_byte", "end_byte",
    "text",
})
_SURFACED_STATUSES = frozenset({"accept", "classify_out", "review"})
_SURFACED_STATUSES_V3 = frozenset({"accept", "classify_out"})


class DuplicateKeyError(ValueError):
    """Raised before JSON object construction can discard a duplicate key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(value)


def decode_strict_json(raw: bytes) -> object:
    """Decode only UTF-8 JSON, preserving duplicate-key and non-finite failures."""
    text = raw.decode("utf-8")
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)


@dataclass(frozen=True)
class ParsedPayload:
    schema_version: str
    ingress: str
    adapter_batch_sha256: str
    predictions: tuple[dict[str, object], ...]
    canonical_projection: bytes
    diagnostics: tuple[Diagnostic, ...]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _exact_keys(value: object, expected: frozenset[str], field: str, diagnostics: list[Diagnostic], fixture_id: str | None = None) -> bool:
    if not isinstance(value, dict):
        diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", fixture_id, field, expected="object", observed=type(value).__name__))
        return False
    actual = set(value)
    for key in sorted(expected - actual):
        diagnostics.append(Diagnostic("FIELD_MISSING", "blocker", fixture_id, f"{field}.{key}", expected="present"))
    for key in sorted(actual - expected):
        diagnostics.append(Diagnostic("FIELD_UNKNOWN", "blocker", fixture_id, f"{field}.{key}", observed=value[key]))
    return actual == set(expected)


def _required_string(value: dict[str, Any], key: str, field: str, diagnostics: list[Diagnostic]) -> str | None:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", field=field, expected="non-empty string", observed=item))
        return None
    return item


def _validate_span(
    value: object,
    *,
    fixture_id: str | None,
    field: str,
    source_by_sha256: dict[str, bytes],
    allowed_source_sha256: frozenset[str],
    diagnostics: list[Diagnostic],
    schema_version: str = SCHEMA_VERSION,
    allowed_source_paths: dict[str, str] | None = None,
) -> dict[str, object] | None:
    is_v3 = schema_version == SCHEMA_VERSION_V3
    valid = _exact_keys(value, _SPAN_KEYS_V3 if is_v3 else _SPAN_KEYS, field, diagnostics, fixture_id)
    if not isinstance(value, dict):
        return None
    dimension = value.get("dimension")
    source_path = value.get("source_path")
    source_sha256 = value.get("source_sha256")
    start = value.get("start_byte")
    end = value.get("end_byte")
    text = value.get("text")
    if is_v3:
        if dimension not in {"surface", "disposition"}:
            diagnostics.append(Diagnostic("EVIDENCE_DIMENSION_INVALID", "blocker", fixture_id, f"{field}.dimension", expected=["disposition", "surface"], observed=dimension))
            valid = False
        if not isinstance(source_path, str) or not source_path:
            diagnostics.append(Diagnostic("EVIDENCE_SOURCE_PATH_INVALID", "blocker", fixture_id, f"{field}.source_path", expected="non-empty relative path", observed=source_path))
            valid = False
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            diagnostics.append(Diagnostic("EVIDENCE_SOURCE_HASH_INVALID", "blocker", fixture_id, f"{field}.source_sha256", source_sha256=source_sha256 if isinstance(source_sha256, str) else None))
            valid = False
    elif not isinstance(source_sha256, str) or source_sha256 not in source_by_sha256:
        diagnostics.append(Diagnostic("EVIDENCE_SOURCE_UNKNOWN", "blocker", fixture_id, f"{field}.source_sha256", source_sha256=source_sha256 if isinstance(source_sha256, str) else None))
        valid = False
    elif not is_v3 and source_sha256 not in allowed_source_sha256:
        diagnostics.append(Diagnostic("EVIDENCE_SOURCE_NOT_DECLARED_FOR_FIXTURE", "blocker", fixture_id, f"{field}.source_sha256", source_sha256=source_sha256))
        valid = False
    if not _is_int(start) or not _is_int(end):
        diagnostics.append(Diagnostic("EVIDENCE_RANGE_TYPE_INVALID", "blocker", fixture_id, field, expected="integer byte offsets", observed=[start, end]))
        valid = False
    if not isinstance(text, str):
        diagnostics.append(Diagnostic("EVIDENCE_TEXT_TYPE_INVALID", "blocker", fixture_id, f"{field}.text", expected="string", observed=text))
        valid = False
    if not valid:
        return None
    assert isinstance(source_sha256, str) and isinstance(start, int) and isinstance(end, int) and isinstance(text, str)
    if is_v3:
        assert isinstance(dimension, str) and isinstance(source_path, str)
        # Integrity is a score-bearing dimension in v3.  Preserve every
        # structurally valid span, including an invalid hash/range/text, so one
        # bad span decrements only the numerator while S stays frozen.
        return {
            "dimension": dimension,
            "source_path": source_path,
            "source_sha256": source_sha256,
            "start_byte": start,
            "end_byte": end,
            "text": text,
        }
    raw = source_by_sha256[source_sha256]
    if start < 0 or end <= start or end > len(raw):
        diagnostics.append(Diagnostic("EVIDENCE_RANGE_INVALID", "blocker", fixture_id, field, expected=f"[0,{len(raw)}] non-empty", observed=[start, end], source_sha256=source_sha256))
        return None
    try:
        exact_text = raw[start:end].decode("utf-8")
    except UnicodeDecodeError:
        diagnostics.append(Diagnostic("EVIDENCE_TEXT_NOT_UTF8", "blocker", fixture_id, field, source_sha256=source_sha256))
        return None
    if exact_text != text:
        diagnostics.append(Diagnostic("EVIDENCE_TEXT_MISMATCH", "blocker", fixture_id, f"{field}.text", expected=exact_text, observed=text, source_sha256=source_sha256))
        return None
    return {"source_sha256": source_sha256, "start_byte": start, "end_byte": end, "text": text}


def validate_current_payload(
    payload: object,
    *,
    adapter_batch: object,
    ingress: str,
) -> ParsedPayload:
    """Validate all score-bearing levels while collecting every traversable blocker."""
    diagnostics: list[Diagnostic] = []
    successor = getattr(adapter_batch, "score_bearing_span_count", None) is not None
    expected_schema = SCHEMA_VERSION_V3 if successor else SCHEMA_VERSION
    allowed_ingress = {CURRENT_INGRESS_V3} if successor else {CURRENT_INGRESS, LEGACY_INGRESS}
    if ingress not in allowed_ingress:
        diagnostics.append(Diagnostic("INGRESS_INVALID", "blocker", field="ingress", expected=sorted(allowed_ingress), observed=ingress))
    _exact_keys(payload, _PAYLOAD_KEYS, "payload", diagnostics)
    if not isinstance(payload, dict):
        return ParsedPayload("", ingress, "", (), b"", tuple(diagnostics))
    schema_version = payload.get("schema_version")
    if schema_version != expected_schema:
        diagnostics.append(Diagnostic("SCHEMA_VERSION_INVALID", "blocker", field="payload.schema_version", expected=expected_schema, observed=schema_version))
    adapter_hash = payload.get("adapter_batch_sha256")
    batch_hash = getattr(adapter_batch, "adapter_batch_sha256", None)
    if not isinstance(adapter_hash, str) or adapter_hash != batch_hash:
        diagnostics.append(Diagnostic("ADAPTER_BATCH_SHA256_MISMATCH", "blocker", field="payload.adapter_batch_sha256", expected=batch_hash, observed=adapter_hash))
    if not getattr(adapter_batch, "valid", False):
        diagnostics.append(Diagnostic("ADAPTER_BATCH_INVALID", "blocker", field="adapter_batch"))
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", field="payload.predictions", expected="array", observed=type(predictions).__name__))
        return ParsedPayload(str(schema_version), ingress, str(adapter_hash), (), b"", tuple(diagnostics))

    records = tuple(getattr(adapter_batch, "records", ()))
    record_by_id = {record.fixture_id: record for record in records}
    source_by_sha256 = getattr(adapter_batch, "source_bytes_by_sha256", {})
    if not isinstance(source_by_sha256, dict):
        source_by_sha256 = {}
    source_by_fixture = getattr(adapter_batch, "source_bytes_by_fixture", {})
    if not isinstance(source_by_fixture, dict):
        source_by_fixture = {}
    source_paths_by_fixture = getattr(adapter_batch, "source_paths_by_fixture", {})
    if not isinstance(source_paths_by_fixture, dict):
        source_paths_by_fixture = {}

    seen_fixture_ids: dict[str, int] = {}
    seen_finding_ids: dict[str, int] = {}
    parsed: list[dict[str, object]] = []
    for index, prediction in enumerate(predictions, start=1):
        prediction_field = "prediction"
        _exact_keys(prediction, _PREDICTION_KEYS, prediction_field, diagnostics)
        if not isinstance(prediction, dict):
            continue
        fixture_id = _required_string(prediction, "fixture_id", f"{prediction_field}.fixture_id", diagnostics)
        finding_id = _required_string(prediction, "finding_id", f"{prediction_field}.finding_id", diagnostics)
        rationale = _required_string(prediction, "rationale", f"{prediction_field}.rationale", diagnostics)
        if fixture_id is not None:
            if fixture_id not in record_by_id:
                diagnostics.append(Diagnostic("FIXTURE_ID_UNKNOWN", "blocker", fixture_id, f"{prediction_field}.fixture_id", observed=fixture_id))
            if fixture_id in seen_fixture_ids:
                occurrence = seen_fixture_ids[fixture_id]
                diagnostics.append(Diagnostic("PREDICTION_FIXTURE_DUPLICATE", "blocker", fixture_id, f"{prediction_field}.fixture_id", occurrence=occurrence, expected="unique fixture_id", observed=fixture_id))
            seen_fixture_ids[fixture_id] = seen_fixture_ids.get(fixture_id, 0) + 1
        if finding_id is not None:
            if finding_id in seen_finding_ids:
                occurrence = seen_finding_ids[finding_id]
                diagnostics.append(Diagnostic("FINDING_ID_DUPLICATE", "blocker", fixture_id, f"{prediction_field}.finding_id", occurrence=occurrence, expected="unique finding_id", observed=finding_id))
            seen_finding_ids[finding_id] = seen_finding_ids.get(finding_id, 0) + 1
        adjudication = prediction.get("adjudication")
        _exact_keys(adjudication, _ADJUDICATION_KEYS, f"{prediction_field}.adjudication", diagnostics, fixture_id)
        if not isinstance(adjudication, dict):
            continue
        surfaced = adjudication.get("surfaced")
        status = adjudication.get("parameter_status")
        name = adjudication.get("proposed_name")
        spans = adjudication.get("evidence_spans")
        valid_prediction = fixture_id is not None and finding_id is not None and rationale is not None
        if not isinstance(surfaced, bool):
            diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", fixture_id, f"{prediction_field}.adjudication.surfaced", expected="boolean", observed=surfaced))
            valid_prediction = False
        if not isinstance(spans, list):
            diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", fixture_id, f"{prediction_field}.adjudication.evidence_spans", expected="array", observed=spans))
            valid_prediction = False
            spans = []
        normalized_status = status
        surfaced_statuses = _SURFACED_STATUSES_V3 if successor else _SURFACED_STATUSES
        if status == "reject":
            if ingress == LEGACY_INGRESS:
                normalized_status = "classify_out"
                diagnostics.append(Diagnostic("LEGACY_PARAMETER_STATUS_NORMALIZED", "warning", fixture_id, f"{prediction_field}.adjudication.parameter_status", expected="classify_out", observed="reject"))
            else:
                diagnostics.append(Diagnostic("PARAMETER_STATUS_INVALID", "blocker", fixture_id, f"{prediction_field}.adjudication.parameter_status", expected=sorted(surfaced_statuses), observed=status))
                valid_prediction = False
        if surfaced is False:
            if not (normalized_status is None and name is None and spans == []):
                diagnostics.append(Diagnostic("NO_FINDING_NONCANONICAL", "blocker", fixture_id, f"{prediction_field}.adjudication", expected={"surfaced": False, "parameter_status": None, "proposed_name": None, "evidence_spans": []}, observed=adjudication))
                valid_prediction = False
        elif surfaced is True:
            if normalized_status not in surfaced_statuses:
                diagnostics.append(Diagnostic("PARAMETER_STATUS_INVALID", "blocker", fixture_id, f"{prediction_field}.adjudication.parameter_status", expected=sorted(surfaced_statuses), observed=normalized_status))
                valid_prediction = False
            if name is not None and not isinstance(name, str):
                diagnostics.append(Diagnostic("FIELD_TYPE_INVALID", "blocker", fixture_id, f"{prediction_field}.adjudication.proposed_name", expected="string or null", observed=name))
                valid_prediction = False
            if not spans:
                diagnostics.append(Diagnostic("EVIDENCE_SPANS_REQUIRED", "blocker", fixture_id, f"{prediction_field}.adjudication.evidence_spans", expected="non-empty array", observed=spans))
                valid_prediction = False
        else:
            valid_prediction = False
        parsed_spans: list[dict[str, object]] = []
        for span_index, span in enumerate(spans):
            allowed = source_by_fixture.get(fixture_id, {}) if fixture_id is not None else {}
            allowed_paths = source_paths_by_fixture.get(fixture_id, {}) if fixture_id is not None else {}
            parsed_span = _validate_span(
                span,
                fixture_id=fixture_id,
                field=f"{prediction_field}.adjudication.evidence_spans[{span_index}]",
                source_by_sha256=source_by_sha256,
                allowed_source_sha256=frozenset(allowed) if isinstance(allowed, dict) else frozenset(),
                diagnostics=diagnostics,
                schema_version=expected_schema,
                allowed_source_paths=allowed_paths if isinstance(allowed_paths, dict) else {},
            )
            if parsed_span is None:
                valid_prediction = False
            else:
                parsed_spans.append(parsed_span)
        if valid_prediction:
            parsed.append({
                "schema_version": expected_schema,
                "ingress": ingress,
                "fixture_id": fixture_id,
                "finding_id": finding_id,
                "rationale": rationale,
                "adjudication": {"surfaced": surfaced, "parameter_status": normalized_status, "proposed_name": name, "evidence_spans": parsed_spans},
            })
    expected_ids = set(record_by_id)
    observed_ids = set(seen_fixture_ids)
    for fixture_id in sorted(expected_ids - observed_ids):
        diagnostics.append(Diagnostic("PREDICTION_FIXTURE_MISSING", "blocker", fixture_id, "payload.predictions", expected="one prediction"))
    projection = {"schema_version": expected_schema, "ingress": ingress, "adapter_batch_sha256": adapter_hash, "predictions": parsed}
    return ParsedPayload(expected_schema, ingress, adapter_hash if isinstance(adapter_hash, str) else "", tuple(parsed), canonical_json_bytes(projection), tuple(diagnostics))
