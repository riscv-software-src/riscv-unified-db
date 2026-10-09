# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Decision-free family/split review packet and explicit human decision validation."""

from __future__ import annotations

from collections.abc import Mapping

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes

from .schema import DataSchemaError, require_canonical_utc


class SplitReviewError(ValueError):
    """Stable family/split review failure."""


def _self_hash_valid(value: Mapping[str, object], field: str) -> bool:
    payload = {key: value[key] for key in value if key != field}
    return value.get(field) == sha256_bytes(canonical_json_bytes(payload))


def build_family_split_review_packet_v1(
    *, registry: Mapping[str, object], manifest: Mapping[str, object],
) -> dict[str, object]:
    """Build a decision-free packet with definition rows before assignments."""
    if (
        registry.get("schema_version") != "family-registry-v1"
        or not _self_hash_valid(registry, "registry_sha256")
        or manifest.get("schema_version") != "split-manifest-v1"
        or not _self_hash_valid(manifest, "manifest_sha256")
        or not isinstance(manifest.get("bindings"), Mapping)
        or manifest["bindings"].get("registry_sha256") != registry.get("registry_sha256")
        or manifest["bindings"].get("registry_version") != registry.get("registry_version")
    ):
        raise SplitReviewError("FAMILY_SPLIT_PACKET_INPUT_INVALID")
    payload = {
        "assignments": registry["assignments"],
        "counts": {
            "auxiliary": len(manifest["auxiliary_case_ids"]),
            "prototype_pairs": len(manifest["prototype_pair_ids"]),
            "quarantined": len(manifest["quarantined_items"]),
            "strict": len(manifest["strict_case_ids"]),
        },
        "diagnostics": manifest["diagnostics"],
        "family_definitions": registry["families"],
        "manifest_sha256": manifest["manifest_sha256"],
        "memberships": {
            "auxiliary_case_ids": manifest["auxiliary_case_ids"],
            "prototype_pair_ids": manifest["prototype_pair_ids"],
            "quarantined_items": manifest["quarantined_items"],
            "strict_case_ids": manifest["strict_case_ids"],
        },
        "registry_sha256": registry["registry_sha256"],
        "registry_version": registry["registry_version"],
        "schema_version": "family-split-review-packet-v1",
        "split_ready": manifest["ready"],
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_family_split_review_markdown_v1(packet: Mapping[str, object]) -> bytes:
    """Render one deterministic, non-authoritative human view."""
    return (
        "# Phase 3 Family and Split Review\n\n"
        f"Registry: `{packet.get('registry_sha256')}`\n\n"
        f"Manifest: `{packet.get('manifest_sha256')}`\n\n"
        "## Canonical packet\n\n```json\n"
    ).encode("utf-8") + canonical_json_bytes(packet) + b"```\n"


def build_family_split_review_readiness_v1(
    *, packet: Mapping[str, object], markdown: bytes,
) -> dict[str, object]:
    """Bind packet forms without supplying any human field."""
    payload = {
        "manifest_sha256": packet["manifest_sha256"],
        "markdown_sha256": sha256_bytes(markdown),
        "packet_sha256": packet["packet_sha256"],
        "registry_sha256": packet["registry_sha256"],
        "schema_version": "family-split-review-readiness-v1",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_family_split_review_decision_v1(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object],
) -> dict[str, object]:
    """Require every definition, assignment, split, and aggregate human field."""
    required = {
        "aggregate_disposition", "aggregate_rationale", "assignment_reviews", "attestation",
        "decision_sha256", "definition_reviews", "packet_sha256", "readiness_sha256",
        "reviewer_id", "schema_version", "signature", "split_review", "timestamp_utc",
    }
    if not isinstance(decision, Mapping) or set(decision) != required or decision.get("schema_version") != "family-split-review-decision-v1":
        raise SplitReviewError("FAMILY_SPLIT_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get("readiness_sha256") != readiness.get("readiness_sha256"):
        raise SplitReviewError("FAMILY_SPLIT_DECISION_BINDING_INVALID")
    payload = {key: decision[key] for key in decision if key != "decision_sha256"}
    if decision.get("decision_sha256") != sha256_bytes(canonical_json_bytes(payload)):
        raise SplitReviewError("FAMILY_SPLIT_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise SplitReviewError("FAMILY_SPLIT_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "FAMILY_SPLIT_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise SplitReviewError(str(error)) from error
    dispositions = {"approved", "disputed", "excluded"}
    expected_families = [item["family_id"] for item in packet["family_definitions"]]
    expected_items = [item["item_id"] for item in packet["assignments"]]
    definition_reviews = decision.get("definition_reviews")
    assignment_reviews = decision.get("assignment_reviews")
    if not isinstance(definition_reviews, list) or [item.get("family_id") if isinstance(item, Mapping) else None for item in definition_reviews] != expected_families:
        raise SplitReviewError("FAMILY_SPLIT_DECISION_INCOMPLETE")
    if not isinstance(assignment_reviews, list) or [item.get("item_id") if isinstance(item, Mapping) else None for item in assignment_reviews] != expected_items:
        raise SplitReviewError("FAMILY_SPLIT_DECISION_INCOMPLETE")
    reviews = [*definition_reviews, *assignment_reviews, decision.get("split_review")]
    observed: list[str] = []
    for review in reviews:
        if not isinstance(review, Mapping) or review.get("disposition") not in dispositions or not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
            raise SplitReviewError("FAMILY_SPLIT_DECISION_INCOMPLETE")
        observed.append(str(review["disposition"]))
    expected_aggregate = "disputed" if "disputed" in observed else "excluded" if "excluded" in observed else "approved"
    if decision.get("aggregate_disposition") != expected_aggregate:
        raise SplitReviewError("FAMILY_SPLIT_AGGREGATE_CONFLICT")
    return dict(decision)
