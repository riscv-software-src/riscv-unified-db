# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Closed Phase 3 schema contract built on the existing strict JSON decoder."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re

from specchoice_evidence.canonical import canonical_json_bytes
from specchoice_measurement.strict_json import decode_strict_json


class DataSchemaError(ValueError):
    """Stable failure for the Phase 3 schema and closed-value contracts."""


_SCHEMA = {
    "candidate_kinds": ["held_out", "metamorphic", "pair"],
    "claim_axes": ["authority", "choice_object", "choice_space_origin", "final_status", "rationale"],
    "eligibility_statuses": ["green_eligible", "red_required", "yellow_eligible"],
    "final_statuses": ["accept", "classify_out"],
    "frame_axes": ["authority", "choice_object", "choice_space_origin"],
    "human_dispositions": ["approved", "disputed", "excluded"],
    "machine_states": ["invalid", "valid"],
    "metamorphic_directions": [
        "choice_space_origin",
        "hardware_software_authority",
        "normative_note_example",
        "warl_fixed_legal_set",
    ],
    "record_keys": {
        "claim": ["axis", "claim_id", "span_ids", "value"],
        "held_out": [
            "candidate_id", "candidate_kind", "claims", "example_id",
            "schema_version", "source_kind", "source_path", "source_sha256", "spans",
        ],
        "metamorphic": [
            "candidate_id", "candidate_kind", "direction_id", "presentation_order",
            "relationship", "schema_version", "sources",
        ],
        "pair": [
            "candidate_id", "candidate_kind", "presentation_order", "relationship",
            "schema_version", "sides",
        ],
        "relationship": ["discriminating_axes", "expected_delta", "rationale", "shared_structure"],
        "side": ["claims", "example_id", "role", "source_kind", "source_path", "source_sha256", "spans"],
        "span": ["end_byte", "span_id", "start_byte", "text"],
        "synthetic_edit": ["end_byte", "original_text", "replacement_text", "start_byte"],
    },
    "schema_version": "phase3-data-schema-v1",
    "source_kinds": ["authoritative", "human_synthetic"],
    "supported_versions": {
        "candidate_inventory": "candidate-inventory-v1",
        "held_out_candidate": "phase3-held-out-candidate-v1",
        "metamorphic_candidate": "phase3-metamorphic-candidate-v1",
        "pair_candidate": "phase3-pair-candidate-v1",
        "pair_review_decision": "pair-review-decision-v1",
        "pair_review_packet": "pair-review-packet-v1",
        "pair_review_readiness": "pair-review-readiness-v1",
    },
}
_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


def load_phase3_schema_v1(raw: bytes) -> dict[str, object]:
    """Require the one canonical, exact Phase 3 schema contract."""
    try:
        value = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise DataSchemaError("PHASE3_DATA_SCHEMA_INVALID") from error
    if not isinstance(value, dict) or value != _SCHEMA or canonical_json_bytes(value) != raw:
        raise DataSchemaError("PHASE3_DATA_SCHEMA_INVALID")
    return value


def require_exact_keys(value: object, expected: set[str], code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise DataSchemaError(code)
    return value


def require_nonempty_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataSchemaError(code)
    return value


def require_json_integer(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DataSchemaError(code)
    return value


def require_canonical_utc(value: object, code: str) -> str:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise DataSchemaError(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise DataSchemaError(code) from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise DataSchemaError(code)
    return value
