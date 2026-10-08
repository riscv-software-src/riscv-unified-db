# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Phase 3 inventory freeze, Phase 2 gate, and descriptor-bound pair admission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from specchoice_evidence.canonical import (
    canonical_json_bytes,
    require_byte_length,
    require_sha256,
    sha256_bytes,
)
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    enumerate_authoritative_files,
    read_authoritative_file,
    require_relative_posix_path,
)
from specchoice_measurement.diagnostics import Diagnostic, ordered_diagnostics
from specchoice_measurement.strict_json import decode_strict_json

from .schema import DataSchemaError, load_phase3_schema_v1


class DataAdmissionError(ValueError):
    """Stable failure before a Phase 3 artifact may become authoritative."""


@dataclass(frozen=True)
class AdmissionResult:
    candidate_id: str | None
    candidate: Mapping[str, object] | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return self.candidate is not None and not any(item.severity == "blocker" for item in self.diagnostics)


def _inventory_payload(
    *, entries: list[dict[str, object]], phase2_authority_sha256: str,
    h1_decision_sha256: str, schema_sha256: str,
) -> dict[str, object]:
    return {
        "bindings": {
            "h1_decision_sha256": h1_decision_sha256,
            "phase2_authority_sha256": phase2_authority_sha256,
            "schema_sha256": schema_sha256,
        },
        "entries": entries,
        "schema_version": "candidate-inventory-v1",
    }


def freeze_candidate_inventory_v1(
    *, candidate_root: Path, declarations: Sequence[tuple[str, str]],
    phase2_authority_sha256: str, h1_decision_sha256: str, schema_raw: bytes,
) -> dict[str, object]:
    """Freeze the complete pre-review candidate tree without repairing any input."""
    schema = load_phase3_schema_v1(schema_raw)
    try:
        authority_hash = require_sha256(phase2_authority_sha256)
        decision_hash = require_sha256(h1_decision_sha256)
        schema_hash = sha256_bytes(schema_raw)
        kinds = set(schema["candidate_kinds"])
        normalized: list[tuple[str, str]] = []
        for path, kind in declarations:
            relative = require_relative_posix_path(path).as_posix()
            if kind not in kinds:
                raise DataAdmissionError("CANDIDATE_KIND_INVALID")
            normalized.append((relative, kind))
    except (FilesystemPolicyError, ValueError, TypeError) as error:
        if isinstance(error, DataAdmissionError):
            raise
        raise DataAdmissionError("CANDIDATE_INVENTORY_INVALID") from error
    if normalized != sorted(normalized) or len({path for path, _ in normalized}) != len(normalized):
        raise DataAdmissionError("CANDIDATE_INVENTORY_ORDER_INVALID")
    try:
        observed = enumerate_authoritative_files(candidate_root)
    except (FilesystemPolicyError, OSError) as error:
        raise DataAdmissionError("CANDIDATE_INVENTORY_PATH_REJECTED") from error
    declared_paths = {path for path, _ in normalized}
    if observed != declared_paths:
        raise DataAdmissionError("CANDIDATE_INVENTORY_INCOMPLETE")
    entries: list[dict[str, object]] = []
    for path, kind in normalized:
        try:
            evidence, raw = read_authoritative_file(candidate_root, path)
            value = decode_strict_json(raw)
        except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
            raise DataAdmissionError("CANDIDATE_INVENTORY_INPUT_INVALID") from error
        if (
            evidence.file_kind != "regular_file"
            or not isinstance(value, dict)
            or canonical_json_bytes(value) != raw
            or value.get("candidate_kind") != kind
        ):
            raise DataAdmissionError("CANDIDATE_INVENTORY_INPUT_INVALID")
        entries.append({"byte_length": len(raw), "kind": kind, "path": path, "sha256": sha256_bytes(raw)})
    payload = _inventory_payload(
        entries=entries,
        phase2_authority_sha256=authority_hash,
        h1_decision_sha256=decision_hash,
        schema_sha256=schema_hash,
    )
    return {**payload, "inventory_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_candidate_inventory_v1(
    *, candidate_root: Path, inventory: object, schema_raw: bytes,
) -> dict[str, object]:
    """Revalidate the complete frozen candidate tree before semantic review."""
    schema = load_phase3_schema_v1(schema_raw)
    if not isinstance(inventory, dict) or set(inventory) != {
        "bindings", "entries", "inventory_sha256", "schema_version"
    }:
        raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
    payload = {key: inventory[key] for key in ("bindings", "entries", "schema_version")}
    bindings = inventory.get("bindings")
    entries = inventory.get("entries")
    try:
        if (
            inventory.get("schema_version") != schema["supported_versions"]["candidate_inventory"]
            or inventory.get("inventory_sha256") != sha256_bytes(canonical_json_bytes(payload))
            or not isinstance(bindings, Mapping)
            or set(bindings) != {
                "h1_decision_sha256", "phase2_authority_sha256", "schema_sha256"
            }
            or require_sha256(bindings["h1_decision_sha256"]) != bindings["h1_decision_sha256"]
            or require_sha256(bindings["phase2_authority_sha256"]) != bindings["phase2_authority_sha256"]
            or bindings["schema_sha256"] != sha256_bytes(schema_raw)
            or not isinstance(entries, list)
        ):
            raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, DataAdmissionError):
            raise
        raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED") from error

    declared_paths: list[str] = []
    for entry in entries:
        try:
            if not isinstance(entry, Mapping) or set(entry) != {
                "byte_length", "kind", "path", "sha256"
            }:
                raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
            path = require_relative_posix_path(entry["path"]).as_posix()
            if (
                path == "candidate-inventory.json"
                or entry["kind"] not in schema["candidate_kinds"]
                or require_byte_length(entry["byte_length"]) != entry["byte_length"]
                or require_sha256(entry["sha256"]) != entry["sha256"]
            ):
                raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
        except (KeyError, FilesystemPolicyError, TypeError, ValueError) as error:
            if isinstance(error, DataAdmissionError):
                raise
            raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED") from error
        declared_paths.append(path)
    if declared_paths != sorted(declared_paths) or len(set(declared_paths)) != len(declared_paths):
        raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")

    try:
        observed = enumerate_authoritative_files(candidate_root)
        expected = set(declared_paths)
        if "candidate-inventory.json" in observed:
            expected.add("candidate-inventory.json")
            _, inventory_raw = read_authoritative_file(candidate_root, "candidate-inventory.json")
            if inventory_raw != canonical_json_bytes(inventory):
                raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
        if observed != expected:
            raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
        for entry in entries:
            _, raw = read_authoritative_file(candidate_root, str(entry["path"]))
            candidate = decode_strict_json(raw)
            if (
                len(raw) != entry["byte_length"]
                or sha256_bytes(raw) != entry["sha256"]
                or not isinstance(candidate, dict)
                or canonical_json_bytes(candidate) != raw
                or candidate.get("candidate_kind") != entry["kind"]
            ):
                raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED")
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        if isinstance(error, DataAdmissionError):
            raise
        raise DataAdmissionError("CANDIDATE_INVENTORY_CHANGED") from error
    return inventory


def _diag(code: str, candidate_id: str | None, field: str, *, expected: object = None, observed: object = None) -> Diagnostic:
    return Diagnostic(code, "blocker", fixture_id=candidate_id, field=field, expected=expected, observed=observed)


def _exact(value: object, keys: set[str], code: str, candidate_id: str | None, field: str, diagnostics: list[Diagnostic]) -> bool:
    if not isinstance(value, Mapping):
        diagnostics.append(_diag(code, candidate_id, field, expected="object", observed=type(value).__name__))
        return False
    if set(value) != keys:
        diagnostics.append(_diag(code, candidate_id, field, expected=sorted(keys), observed=sorted(value)))
        return False
    return True


def _strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _inventory_entry(inventory: object, path: str, schema_raw: bytes) -> Mapping[str, object] | None:
    if not isinstance(inventory, Mapping) or set(inventory) != {"bindings", "entries", "inventory_sha256", "schema_version"}:
        return None
    payload = {key: inventory[key] for key in ("bindings", "entries", "schema_version")}
    if (
        inventory.get("schema_version") != "candidate-inventory-v1"
        or inventory.get("inventory_sha256") != sha256_bytes(canonical_json_bytes(payload))
        or not isinstance(inventory.get("bindings"), Mapping)
        or inventory["bindings"].get("schema_sha256") != sha256_bytes(schema_raw)
        or not isinstance(inventory.get("entries"), list)
    ):
        return None
    return next((entry for entry in inventory["entries"] if isinstance(entry, Mapping) and entry.get("path") == path), None)


def admit_pair_candidate_v1(
    *, candidate_root: Path, candidate_path: str, inventory: object,
    accepted_root: Path, schema_raw: bytes,
) -> AdmissionResult:
    """Collect deterministic blockers for one frozen directed pair candidate."""
    diagnostics: list[Diagnostic] = []
    try:
        schema = load_phase3_schema_v1(schema_raw)
        normalized = require_relative_posix_path(candidate_path).as_posix()
    except (DataSchemaError, FilesystemPolicyError, ValueError):
        diagnostics.append(_diag("CANDIDATE_PATH_REJECTED", None, "candidate_path", observed=candidate_path))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    try:
        validate_candidate_inventory_v1(
            candidate_root=candidate_root,
            inventory=inventory,
            schema_raw=schema_raw,
        )
    except DataAdmissionError:
        diagnostics.append(_diag("CANDIDATE_INVENTORY_CHANGED", None, "candidate_root"))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    entry = _inventory_entry(inventory, normalized, schema_raw)
    if entry is None:
        diagnostics.append(_diag("CANDIDATE_NOT_IN_INVENTORY", None, "candidate_path", observed=normalized))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    try:
        _, raw = read_authoritative_file(candidate_root, normalized)
    except (FilesystemPolicyError, OSError):
        diagnostics.append(_diag("CANDIDATE_PATH_REJECTED", None, "candidate_path", observed=normalized))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    if entry.get("byte_length") != len(raw) or entry.get("sha256") != sha256_bytes(raw) or entry.get("kind") != "pair":
        diagnostics.append(_diag("CANDIDATE_INVENTORY_CHANGED", None, "candidate", expected=dict(entry), observed={"byte_length": len(raw), "sha256": sha256_bytes(raw)}))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    try:
        value = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError):
        diagnostics.append(_diag("CANDIDATE_JSON_INVALID", None, "candidate"))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    if not isinstance(value, Mapping):
        diagnostics.append(_diag("CANDIDATE_SCHEMA_INVALID", None, "candidate"))
        return AdmissionResult(None, None, ordered_diagnostics(diagnostics))
    candidate_id = value.get("candidate_id") if isinstance(value.get("candidate_id"), str) else None
    if canonical_json_bytes(value) != raw:
        diagnostics.append(_diag("CANDIDATE_NOT_CANONICAL", candidate_id, "candidate"))
    top_keys = {"candidate_id", "candidate_kind", "presentation_order", "relationship", "schema_version", "sides"}
    _exact(value, top_keys, "CANDIDATE_SCHEMA_INVALID", candidate_id, "candidate", diagnostics)
    if value.get("schema_version") != schema["supported_versions"]["pair_candidate"] or value.get("candidate_kind") != "pair" or candidate_id is None:
        diagnostics.append(_diag("CANDIDATE_SCHEMA_INVALID", candidate_id, "candidate.schema_version"))
    sides = value.get("sides")
    parsed_roles: list[str] = []
    example_ids: list[str] = []
    claims_by_role: dict[str, dict[str, str]] = {}
    if not isinstance(sides, list) or len(sides) != 2:
        diagnostics.append(_diag("PAIR_SIDES_INVALID", candidate_id, "candidate.sides", expected=2, observed=sides))
        sides = []
    for index, side in enumerate(sides):
        field = f"candidate.sides[{index}]"
        side_keys = {"claims", "example_id", "role", "source_kind", "source_path", "source_sha256", "spans"}
        if not _exact(side, side_keys, "PAIR_SIDE_SCHEMA_INVALID", candidate_id, field, diagnostics):
            continue
        assert isinstance(side, Mapping)
        role = side.get("role")
        example_id = side.get("example_id")
        source_path = side.get("source_path")
        if role not in {"positive", "contrast"} or not isinstance(example_id, str) or not example_id or side.get("source_kind") != "authoritative" or not isinstance(source_path, str):
            diagnostics.append(_diag("PAIR_SIDE_SCHEMA_INVALID", candidate_id, field))
            continue
        parsed_roles.append(role)
        example_ids.append(example_id)
        try:
            _, source_raw = read_authoritative_file(accepted_root, source_path)
        except (FilesystemPolicyError, OSError, ValueError):
            diagnostics.append(_diag("SOURCE_PATH_REJECTED", candidate_id, f"{field}.source_path", observed=source_path))
            continue
        if side.get("source_sha256") != sha256_bytes(source_raw):
            diagnostics.append(_diag("SOURCE_BYTES_CHANGED", candidate_id, f"{field}.source_sha256", expected=side.get("source_sha256"), observed=sha256_bytes(source_raw)))
        spans = side.get("spans")
        span_ids: set[str] = set()
        if not isinstance(spans, list) or not spans:
            diagnostics.append(_diag("SOURCE_SPANS_REQUIRED", candidate_id, f"{field}.spans"))
            spans = []
        for span_index, span in enumerate(spans):
            span_field = f"{field}.spans[{span_index}]"
            if not _exact(span, {"end_byte", "span_id", "start_byte", "text"}, "SOURCE_SPAN_INVALID", candidate_id, span_field, diagnostics):
                continue
            assert isinstance(span, Mapping)
            span_id = span.get("span_id")
            start, end, text = span.get("start_byte"), span.get("end_byte"), span.get("text")
            if (
                not isinstance(span_id, str) or not span_id or span_id in span_ids
                or isinstance(start, bool) or not isinstance(start, int)
                or isinstance(end, bool) or not isinstance(end, int)
                or start < 0 or end <= start or end > len(source_raw) or not isinstance(text, str)
            ):
                diagnostics.append(_diag("SOURCE_SPAN_INVALID", candidate_id, span_field))
                continue
            span_ids.add(span_id)
            try:
                observed_text = source_raw[start:end].decode("utf-8")
            except UnicodeDecodeError:
                observed_text = None
            if observed_text != text:
                diagnostics.append(_diag("SOURCE_SPAN_TEXT_MISMATCH", candidate_id, f"{span_field}.text", expected=observed_text, observed=text))
        claims = side.get("claims")
        axes: list[str] = []
        claim_values: dict[str, str] = {}
        claim_ids: set[str] = set()
        if not isinstance(claims, list) or not claims:
            diagnostics.append(_diag("CLAIM_MAPPING_REQUIRED", candidate_id, f"{field}.claims"))
            claims = []
        for claim_index, claim in enumerate(claims):
            claim_field = f"{field}.claims[{claim_index}]"
            if not _exact(claim, {"axis", "claim_id", "span_ids", "value"}, "CLAIM_MAPPING_INVALID", candidate_id, claim_field, diagnostics):
                continue
            assert isinstance(claim, Mapping)
            axis, claim_id, supporting = claim.get("axis"), claim.get("claim_id"), claim.get("span_ids")
            if (
                axis not in schema["claim_axes"] or not isinstance(claim_id, str) or not claim_id
                or claim_id in claim_ids or not isinstance(claim.get("value"), str) or not claim["value"].strip()
                or not isinstance(supporting, list) or not supporting
                or any(not isinstance(item, str) or item not in span_ids for item in supporting)
            ):
                diagnostics.append(_diag("CLAIM_MAPPING_INVALID", candidate_id, claim_field))
                continue
            claim_ids.add(claim_id)
            axes.append(axis)
            claim_values[str(axis)] = str(claim["value"])
        if set(axes) != set(schema["claim_axes"]) or len(axes) != len(schema["claim_axes"]):
            diagnostics.append(_diag("CLAIM_AXIS_MISSING", candidate_id, f"{field}.claims", expected=schema["claim_axes"], observed=axes))
        elif claim_values["final_status"] not in schema["final_statuses"]:
            diagnostics.append(_diag("FINAL_STATUS_INVALID", candidate_id, f"{field}.claims", observed=claim_values["final_status"]))
        claims_by_role[role] = claim_values
    if parsed_roles != ["positive", "contrast"] or value.get("presentation_order") != ["positive", "contrast"]:
        diagnostics.append(_diag("PAIR_PRESENTATION_ORDER_INVALID", candidate_id, "candidate.presentation_order"))
    if len(example_ids) == 2 and example_ids[0] == example_ids[1]:
        diagnostics.append(_diag("PAIR_EXAMPLE_IDS_NOT_DISTINCT", candidate_id, "candidate.sides"))
    relationship = value.get("relationship")
    relationship_keys = {"discriminating_axes", "expected_delta", "rationale", "shared_structure"}
    if _exact(relationship, relationship_keys, "PAIR_RELATIONSHIP_INVALID", candidate_id, "candidate.relationship", diagnostics):
        assert isinstance(relationship, Mapping)
        expected_delta = relationship.get("expected_delta")
        valid_delta = _exact(expected_delta, {"final_status", "frame_axes"}, "PAIR_EXPECTED_DELTA_INVALID", candidate_id, "candidate.relationship.expected_delta", diagnostics)
        if valid_delta:
            assert isinstance(expected_delta, Mapping)
            final_status = expected_delta.get("final_status")
            if (
                not _strings(expected_delta.get("frame_axes"))
                or any(axis not in schema["frame_axes"] for axis in expected_delta["frame_axes"])
                or not isinstance(final_status, Mapping)
                or set(final_status) != {"from", "to"}
                or final_status.get("from") not in schema["final_statuses"]
                or final_status.get("to") not in schema["final_statuses"]
            ):
                diagnostics.append(_diag("PAIR_EXPECTED_DELTA_INVALID", candidate_id, "candidate.relationship.expected_delta"))
        if (
            not _strings(relationship.get("shared_structure"))
            or not _strings(relationship.get("discriminating_axes"))
            or any(axis not in schema["frame_axes"] for axis in relationship.get("discriminating_axes", []))
            or not isinstance(relationship.get("rationale"), str) or not relationship["rationale"].strip()
        ):
            diagnostics.append(_diag("PAIR_RELATIONSHIP_INVALID", candidate_id, "candidate.relationship"))
        if valid_delta and all(role in claims_by_role for role in ("positive", "contrast")):
            assert isinstance(expected_delta, Mapping)
            final_status = expected_delta.get("final_status")
            discriminating = relationship.get("discriminating_axes")
            if (
                not isinstance(final_status, Mapping)
                or final_status.get("from") != claims_by_role["positive"].get("final_status")
                or final_status.get("to") != claims_by_role["contrast"].get("final_status")
                or expected_delta.get("frame_axes") != discriminating
            ):
                diagnostics.append(_diag("PAIR_EXPECTED_DELTA_MISMATCH", candidate_id, "candidate.relationship.expected_delta"))
            if isinstance(discriminating, list):
                uncontrolled = [
                    axis for axis in schema["frame_axes"]
                    if (claims_by_role["positive"].get(axis) != claims_by_role["contrast"].get(axis)) != (axis in discriminating)
                ]
                if uncontrolled:
                    diagnostics.append(_diag("PAIR_UNCONTROLLED_CONTRAST", candidate_id, "candidate.relationship.discriminating_axes", observed=uncontrolled))
    ordered = ordered_diagnostics(diagnostics)
    return AdmissionResult(candidate_id, value, ordered)
