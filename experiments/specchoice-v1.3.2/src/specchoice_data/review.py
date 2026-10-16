# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Decision-free pair review packets and explicit human decision validation."""

from __future__ import annotations

from collections.abc import Mapping

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes

from .admission import AdmissionResult
from .schema import DataSchemaError, require_canonical_utc


class DataReviewError(ValueError):
    """Stable failure for a pair review packet, readiness, or decision."""


def build_pair_review_packet_v1(*, admission: AdmissionResult, inventory: Mapping[str, object]) -> dict[str, object]:
    """Build canonical machine authority without adding a human disposition."""
    if admission.candidate_id is None or admission.candidate is None:
        raise DataReviewError("PAIR_REVIEW_PACKET_INPUT_INVALID")
    payload = {
        "candidate": dict(admission.candidate),
        "candidate_id": admission.candidate_id,
        "diagnostics": [item.as_dict() for item in admission.diagnostics],
        "inventory_sha256": inventory.get("inventory_sha256"),
        "machine_state": "valid" if admission.valid else "invalid",
        "schema_version": "pair-review-packet-v1",
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_pair_review_markdown_v1(packet: Mapping[str, object]) -> bytes:
    """Render a one-way reviewer view whose source remains canonical JSON."""
    return (
        "# Phase 3 Pair Review\n\n"
        f"Candidate: `{packet.get('candidate_id')}`\n\n"
        f"Machine state: `{packet.get('machine_state')}`\n\n"
        "## Canonical packet\n\n```json\n"
        + canonical_json_bytes(dict(packet)).decode("utf-8").rstrip("\n")
        + "\n```\n"
    ).encode("utf-8")


def _packet_valid(packet: object) -> bool:
    if not isinstance(packet, Mapping) or set(packet) != {
        "candidate", "candidate_id", "diagnostics", "inventory_sha256", "machine_state", "packet_sha256", "schema_version"
    }:
        return False
    payload = {key: packet[key] for key in packet if key != "packet_sha256"}
    return packet.get("schema_version") == "pair-review-packet-v1" and packet.get("packet_sha256") == sha256_bytes(canonical_json_bytes(payload))


def build_pair_review_readiness_v1(*, packet: Mapping[str, object], markdown: bytes) -> dict[str, object]:
    """Build readiness with hashes and machine state only, never human fields."""
    if not _packet_valid(packet) or render_pair_review_markdown_v1(packet) != markdown:
        raise DataReviewError("PAIR_REVIEW_READINESS_INVALID")
    payload = {
        "candidate_id": packet["candidate_id"],
        "machine_state": packet["machine_state"],
        "markdown_sha256": sha256_bytes(markdown),
        "packet_sha256": packet["packet_sha256"],
        "schema_version": "pair-review-readiness-v1",
        "status": "ready_for_human" if packet["machine_state"] == "valid" else "structurally_invalid",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def _readiness_valid(readiness: object, packet: Mapping[str, object]) -> bool:
    if not isinstance(readiness, Mapping) or set(readiness) != {
        "candidate_id", "machine_state", "markdown_sha256", "packet_sha256", "readiness_sha256", "schema_version", "status"
    }:
        return False
    payload = {key: readiness[key] for key in readiness if key != "readiness_sha256"}
    return (
        readiness.get("schema_version") == "pair-review-readiness-v1"
        and readiness.get("packet_sha256") == packet.get("packet_sha256")
        and readiness.get("candidate_id") == packet.get("candidate_id")
        and readiness.get("machine_state") == packet.get("machine_state")
        and readiness.get("readiness_sha256") == sha256_bytes(canonical_json_bytes(payload))
    )


def validate_pair_review_decision_v1(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object],
) -> dict[str, object]:
    """Require every human field explicitly and reject structurally invalid approval."""
    if not _packet_valid(packet) or not _readiness_valid(readiness, packet):
        raise DataReviewError("PAIR_REVIEW_DECISION_BINDING_INVALID")
    required = {
        "aggregate_disposition", "aggregate_rationale", "attestation", "decision_sha256",
        "packet_sha256", "readiness_sha256", "relationship_review", "reviewer_id",
        "schema_version", "side_reviews", "signature", "timestamp_utc",
    }
    if not isinstance(decision, Mapping) or set(decision) != required or decision.get("schema_version") != "pair-review-decision-v1":
        raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get("readiness_sha256") != readiness.get("readiness_sha256"):
        raise DataReviewError("PAIR_REVIEW_DECISION_BINDING_INVALID")
    payload = {key: decision[key] for key in decision if key != "decision_sha256"}
    if decision.get("decision_sha256") != sha256_bytes(canonical_json_bytes(payload)):
        raise DataReviewError("PAIR_REVIEW_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "PAIR_REVIEW_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise DataReviewError(str(error)) from error
    dispositions = {"approved", "disputed", "excluded"}
    side_reviews = decision.get("side_reviews")
    if not isinstance(side_reviews, list) or len(side_reviews) != 2:
        raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
    if [item.get("role") if isinstance(item, Mapping) else None for item in side_reviews] != ["positive", "contrast"]:
        raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
    all_dispositions: list[str] = []
    for item in side_reviews:
        if (
            not isinstance(item, Mapping) or set(item) != {"disposition", "rationale", "role"}
            or item.get("disposition") not in dispositions
            or not isinstance(item.get("rationale"), str) or not item["rationale"].strip()
        ):
            raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
        all_dispositions.append(str(item["disposition"]))
    relationship = decision.get("relationship_review")
    if (
        not isinstance(relationship, Mapping) or set(relationship) != {"disposition", "rationale"}
        or relationship.get("disposition") not in dispositions
        or not isinstance(relationship.get("rationale"), str) or not relationship["rationale"].strip()
    ):
        raise DataReviewError("PAIR_REVIEW_DECISION_INCOMPLETE")
    all_dispositions.append(str(relationship["disposition"]))
    expected_aggregate = "disputed" if "disputed" in all_dispositions else "excluded" if "excluded" in all_dispositions else "approved"
    if decision.get("aggregate_disposition") != expected_aggregate:
        raise DataReviewError("PAIR_REVIEW_AGGREGATE_CONFLICT")
    if packet.get("machine_state") != "valid" and expected_aggregate == "approved":
        raise DataReviewError("PAIR_REVIEW_STRUCTURAL_APPROVAL_FORBIDDEN")
    return dict(decision)
