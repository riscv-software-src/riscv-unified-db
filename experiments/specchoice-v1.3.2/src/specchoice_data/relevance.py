# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Pre-ranking relevance and non-counting metamorphic preregistration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, require_sha256, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file

from .schema import DataSchemaError, require_canonical_utc


class RelevanceValidationError(ValueError):
    """Stable failure for Phase 3 relevance or metamorphic authority."""


REQUIRED_METAMORPHIC_DIRECTIONS = (
    "choice_space_origin",
    "hardware_software_authority",
    "normative_note_example",
    "warl_fixed_legal_set",
)
SOURCE_KINDS = ("authoritative", "human_synthetic")
_FORBIDDEN_RANK_FIELDS = {"rank", "score", "similarity", "top_k"}
_FRAME_AXES = {"authority", "choice_object", "choice_space_origin"}
_FINAL_STATUSES = {"accept", "classify_out"}
_EXPECTED_DIRECTION_AXIS = {
    "choice_space_origin": "choice_space_origin",
    "hardware_software_authority": "authority",
    "normative_note_example": "final_status",
    "warl_fixed_legal_set": "choice_space_origin",
}


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sorted_strings(value: object, *, empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (empty or bool(value))
        and all(_text(item) for item in value)
        and value == sorted(set(value))
    )


def _self_hash_valid(value: Mapping[str, object], field: str) -> bool:
    payload = {key: value[key] for key in value if key != field}
    return value.get(field) == sha256_bytes(canonical_json_bytes(payload))


def _contains_forbidden_rank_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(_FORBIDDEN_RANK_FIELDS & set(value)) or any(
            _contains_forbidden_rank_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_rank_field(item) for item in value)
    return False


def _require_bindings(observed: object, expected: Mapping[str, object], code: str) -> None:
    if not isinstance(observed, Mapping) or dict(observed) != dict(expected):
        raise RelevanceValidationError(code)
    try:
        for key, value in observed.items():
            if key.endswith("_sha256"):
                require_sha256(value)
    except (TypeError, ValueError) as error:
        raise RelevanceValidationError(code) from error


def _validate_relevance_rows(
    rows: object,
    *,
    expected_ids: Sequence[str],
    case_targets: Mapping[str, Mapping[str, object]],
    approved_pairs: Mapping[str, Mapping[str, object]],
) -> list[str]:
    if not isinstance(rows, list):
        raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
    observed_ids = [row.get("case_id") if isinstance(row, Mapping) else None for row in rows]
    if observed_ids != sorted(expected_ids) or len(observed_ids) != len(set(observed_ids)):
        raise RelevanceValidationError("RELEVANCE_STRICT_COVERAGE_INVALID")
    pairhit: list[str] = []
    common_keys = {"case_id", "choice_object", "decisive_axes", "key_structure", "rationale"}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
        keys = set(row)
        relevant = keys == common_keys | {"relevant_pair_ids"}
        no_relevant = keys == common_keys | {"no_relevant_pair"}
        if not relevant and not no_relevant:
            raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
        case_id = row.get("case_id")
        target = case_targets.get(str(case_id))
        if (
            not isinstance(target, Mapping)
            or row.get("choice_object") != target.get("choice_object")
            or row.get("decisive_axes") != target.get("decisive_axes")
            or row.get("key_structure") != target.get("key_structure")
            or not _text(row.get("choice_object"))
            or not _sorted_strings(row.get("decisive_axes"))
            or not _sorted_strings(row.get("key_structure"))
            or not _text(row.get("rationale"))
        ):
            raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
        if no_relevant:
            if row.get("no_relevant_pair") is not True:
                raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
            continue
        pair_ids = row.get("relevant_pair_ids")
        if not _sorted_strings(pair_ids):
            raise RelevanceValidationError("RELEVANCE_ROW_INVALID")
        target_structure = set(row["key_structure"])
        target_axes = set(row["decisive_axes"])
        for pair_id in pair_ids:
            pair = approved_pairs.get(pair_id)
            if (
                not isinstance(pair, Mapping)
                or not target_structure.intersection(pair.get("shared_structure", []))
                or not target_axes.intersection(pair.get("discriminating_axes", []))
            ):
                raise RelevanceValidationError("RELEVANCE_PAIR_MISMATCH")
        pairhit.append(str(case_id))
    return sorted(pairhit)


def validate_pair_relevance_registry_v1(
    registry: object,
    *,
    split_manifest: Mapping[str, object],
    approved_pairs: Mapping[str, Mapping[str, object]],
    expected_bindings: Mapping[str, object],
    case_targets: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Validate complete strict relevance and separately held auxiliary judgments."""
    required = {
        "auxiliary_rows",
        "bindings",
        "registry_sha256",
        "registry_version",
        "schema_version",
        "strict_pairhit_eligible_case_ids",
        "strict_rows",
    }
    if not isinstance(registry, dict) or set(registry) != required:
        raise RelevanceValidationError("RELEVANCE_REGISTRY_INVALID")
    if registry.get("schema_version") != "pair-relevance-registry-v1" or not _text(registry.get("registry_version")):
        raise RelevanceValidationError("RELEVANCE_REGISTRY_INVALID")
    if _contains_forbidden_rank_field(registry):
        raise RelevanceValidationError("RELEVANCE_RANK_FIELD_FORBIDDEN")
    _require_bindings(registry.get("bindings"), expected_bindings, "RELEVANCE_BINDING_INVALID")
    strict_ids = split_manifest.get("strict_case_ids")
    auxiliary_ids = split_manifest.get("auxiliary_case_ids")
    if not _sorted_strings(strict_ids, empty=True) or not _sorted_strings(auxiliary_ids, empty=True):
        raise RelevanceValidationError("RELEVANCE_SPLIT_INVALID")
    strict_pairhit = _validate_relevance_rows(
        registry.get("strict_rows"),
        expected_ids=strict_ids,
        case_targets=case_targets,
        approved_pairs=approved_pairs,
    )
    try:
        _validate_relevance_rows(
            registry.get("auxiliary_rows"),
            expected_ids=auxiliary_ids,
            case_targets=case_targets,
            approved_pairs=approved_pairs,
        )
    except RelevanceValidationError as error:
        if str(error) == "RELEVANCE_STRICT_COVERAGE_INVALID":
            raise RelevanceValidationError("RELEVANCE_AUXILIARY_COVERAGE_INVALID") from error
        raise
    if registry.get("strict_pairhit_eligible_case_ids") != strict_pairhit:
        raise RelevanceValidationError("RELEVANCE_PAIRHIT_DENOMINATOR_INVALID")
    if not _self_hash_valid(registry, "registry_sha256"):
        raise RelevanceValidationError("RELEVANCE_REGISTRY_HASH_INVALID")
    return registry


def _validate_frame(frame: object) -> None:
    if (
        not isinstance(frame, Mapping)
        or set(frame) != _FRAME_AXES
        or any(not _text(frame[axis]) for axis in _FRAME_AXES)
    ):
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")


def _validate_claim_to_span(claims: object, valid_span_ids: Set[str]) -> None:
    if not isinstance(claims, list) or not claims:
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
    observed_axes: list[str] = []
    for claim in claims:
        if not isinstance(claim, Mapping) or set(claim) != {"axis", "span_ids"}:
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
        axis = claim.get("axis")
        span_ids = claim.get("span_ids")
        if (
            axis not in _FRAME_AXES
            or not _sorted_strings(span_ids)
            or any(span_id not in valid_span_ids for span_id in span_ids)
        ):
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
        observed_axes.append(str(axis))
    if observed_axes != sorted(set(observed_axes)):
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")


def _validate_authoritative_source(source: object, accepted_root: Path | None) -> dict[str, str]:
    keys = {"claim_to_span", "final_status", "frame", "source_kind", "source_path", "source_sha256", "spans"}
    if not isinstance(source, Mapping) or set(source) != keys or source.get("source_kind") != "authoritative" or accepted_root is None:
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
    source_path = source.get("source_path")
    if not isinstance(source_path, str):
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
    try:
        _, raw = read_authoritative_file(accepted_root, source_path)
    except (FilesystemPolicyError, OSError, ValueError) as error:
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID") from error
    if source.get("source_sha256") != sha256_bytes(raw) or source.get("final_status") not in _FINAL_STATUSES:
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
    _validate_frame(source.get("frame"))
    spans = source.get("spans")
    if not isinstance(spans, list) or not spans:
        raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
    observed: dict[str, str] = {}
    for span in spans:
        if not isinstance(span, Mapping) or set(span) != {"end_byte", "span_id", "start_byte", "text"}:
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
        span_id, start, end, text = span.get("span_id"), span.get("start_byte"), span.get("end_byte"), span.get("text")
        if (
            not _text(span_id)
            or span_id in observed
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(raw)
            or not isinstance(text, str)
        ):
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
        try:
            extracted = raw[start:end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID") from error
        if extracted != text:
            raise RelevanceValidationError("METAMORPHIC_SOURCE_INVALID")
        observed[str(span_id)] = text
    _validate_claim_to_span(source.get("claim_to_span"), set(observed))
    return observed


def _validate_expected_delta(delta: object, direction_id: str) -> None:
    if not isinstance(delta, Mapping) or set(delta) != {"axis", "final_status", "from", "to"}:
        raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")
    final_status = delta.get("final_status")
    if (
        delta.get("axis") != _EXPECTED_DIRECTION_AXIS[direction_id]
        or not _text(delta.get("from"))
        or not _text(delta.get("to"))
        or delta.get("from") == delta.get("to")
        or not isinstance(final_status, Mapping)
        or set(final_status) != {"from", "to"}
        or final_status.get("from") not in _FINAL_STATUSES
        or final_status.get("to") not in _FINAL_STATUSES
        or final_status.get("from") == final_status.get("to")
    ):
        raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")


def _validate_synthetic_source(
    source: object,
    *,
    authoritative_spans: Mapping[str, str],
    expected_delta: Mapping[str, object],
) -> None:
    keys = {
        "authored_by", "based_on_authoritative_span_id", "claim_to_span", "count_eligible",
        "edit_rationale", "expected_delta", "final_status", "frame", "human_approval_ref",
        "model_generated", "original_text", "replacement_text", "source_kind",
    }
    if not isinstance(source, Mapping) or set(source) != keys or source.get("source_kind") != "human_synthetic":
        raise RelevanceValidationError("METAMORPHIC_SYNTHETIC_INVALID")
    base_id = source.get("based_on_authoritative_span_id")
    if (
        source.get("count_eligible") is not False
        or source.get("model_generated") is not False
        or not _text(source.get("authored_by"))
        or not _text(source.get("human_approval_ref"))
        or not _text(source.get("edit_rationale"))
        or not _text(source.get("replacement_text"))
        or source.get("original_text") == source.get("replacement_text")
        or base_id not in authoritative_spans
        or source.get("original_text") != authoritative_spans.get(str(base_id))
        or source.get("expected_delta") != expected_delta
        or source.get("final_status") not in _FINAL_STATUSES
    ):
        raise RelevanceValidationError("METAMORPHIC_SYNTHETIC_INVALID")
    try:
        _validate_frame(source.get("frame"))
        _validate_claim_to_span(source.get("claim_to_span"), {"synthetic-replacement"})
    except RelevanceValidationError as error:
        raise RelevanceValidationError("METAMORPHIC_SYNTHETIC_INVALID") from error


def validate_metamorphic_registry_v1(
    registry: object,
    *,
    expected_bindings: Mapping[str, object],
    accepted_root: Path | None,
    frozen_metamorphic_candidate_ids: Set[str],
    dataset_member_ids: Set[str],
) -> dict[str, object]:
    """Validate four exact directions or explicit frozen-inventory unavailability."""
    required = {"bindings", "count_eligible", "directions", "registry_sha256", "registry_version", "schema_version"}
    if not isinstance(registry, dict) or set(registry) != required:
        raise RelevanceValidationError("METAMORPHIC_REGISTRY_INVALID")
    if (
        registry.get("schema_version") != "metamorphic-registry-v1"
        or not _text(registry.get("registry_version"))
        or registry.get("count_eligible") is not False
    ):
        raise RelevanceValidationError("METAMORPHIC_REGISTRY_INVALID")
    _require_bindings(registry.get("bindings"), expected_bindings, "METAMORPHIC_BINDING_INVALID")
    directions = registry.get("directions")
    if not isinstance(directions, list) or [item.get("direction_id") if isinstance(item, Mapping) else None for item in directions] != list(REQUIRED_METAMORPHIC_DIRECTIONS):
        raise RelevanceValidationError("METAMORPHIC_DIRECTION_SET_INVALID")
    for row in directions:
        assert isinstance(row, Mapping)
        direction_id = str(row["direction_id"])
        if row.get("availability") == "unavailable":
            if set(row) != {"availability", "count_eligible", "direction_id", "rationale", "version"} or row.get("count_eligible") is not False or not _text(row.get("rationale")) or not _text(row.get("version")):
                raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")
            continue
        keys = {"availability", "candidate_id", "count_eligible", "direction_id", "expected_delta", "source_a", "source_b", "version"}
        candidate_id = row.get("candidate_id")
        if (
            set(row) != keys
            or row.get("availability") != "available"
            or row.get("count_eligible") is not False
            or not _text(row.get("version"))
            or candidate_id not in frozen_metamorphic_candidate_ids
            or candidate_id in dataset_member_ids
        ):
            raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")
        _validate_expected_delta(row.get("expected_delta"), direction_id)
        if not isinstance(row.get("source_a"), Mapping) or row["source_a"].get("source_kind") != "authoritative":
            raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")
        authoritative_spans = _validate_authoritative_source(row.get("source_a"), accepted_root)
        source_b = row.get("source_b")
        if isinstance(source_b, Mapping) and source_b.get("source_kind") == "authoritative":
            _validate_authoritative_source(source_b, accepted_root)
        else:
            _validate_synthetic_source(
                source_b,
                authoritative_spans=authoritative_spans,
                expected_delta=row["expected_delta"],
            )
        source_a = row["source_a"]
        final_delta = row["expected_delta"]["final_status"]
        if source_a.get("final_status") != final_delta.get("from") or source_b.get("final_status") != final_delta.get("to"):
            raise RelevanceValidationError("METAMORPHIC_DIRECTION_INVALID")
    if not _self_hash_valid(registry, "registry_sha256"):
        raise RelevanceValidationError("METAMORPHIC_REGISTRY_HASH_INVALID")
    return registry


def build_relevance_metamorphic_packet_v1(
    *, relevance: Mapping[str, object], metamorphic: Mapping[str, object],
) -> dict[str, object]:
    """Build a decision-free packet with no retrieval or model-result inputs."""
    if (
        relevance.get("schema_version") != "pair-relevance-registry-v1"
        or not _self_hash_valid(relevance, "registry_sha256")
        or metamorphic.get("schema_version") != "metamorphic-registry-v1"
        or not _self_hash_valid(metamorphic, "registry_sha256")
        or not isinstance(metamorphic.get("bindings"), Mapping)
        or metamorphic["bindings"].get("relevance_registry_sha256") != relevance.get("registry_sha256")
    ):
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_PACKET_INPUT_INVALID")
    directions = metamorphic["directions"]
    payload = {
        "auxiliary_relevance_rows": relevance["auxiliary_rows"],
        "bindings": metamorphic["bindings"],
        "counts": {
            "auxiliary_relevance": len(relevance["auxiliary_rows"]),
            "metamorphic_available": sum(item["availability"] == "available" for item in directions),
            "metamorphic_unavailable": sum(item["availability"] == "unavailable" for item in directions),
            "strict_pairhit_eligible": len(relevance["strict_pairhit_eligible_case_ids"]),
            "strict_relevance": len(relevance["strict_rows"]),
        },
        "metamorphic_directions": directions,
        "metamorphic_registry_sha256": metamorphic["registry_sha256"],
        "no_model_or_retrieval_inputs": True,
        "relevance_registry_sha256": relevance["registry_sha256"],
        "schema_version": "relevance-metamorphic-review-packet-v1",
        "strict_pairhit_eligible_case_ids": relevance["strict_pairhit_eligible_case_ids"],
        "strict_relevance_rows": relevance["strict_rows"],
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_relevance_metamorphic_markdown_v1(packet: Mapping[str, object]) -> bytes:
    """Render a deterministic non-authoritative reviewer projection."""
    return (
        "# Phase 3 Relevance and Metamorphic Review\n\n"
        f"Relevance registry: `{packet.get('relevance_registry_sha256')}`\n\n"
        f"Metamorphic registry: `{packet.get('metamorphic_registry_sha256')}`\n\n"
        "## Canonical packet\n\n```json\n"
    ).encode("utf-8") + canonical_json_bytes(packet) + b"```\n"


def build_relevance_metamorphic_readiness_v1(*, packet: Mapping[str, object], markdown: bytes | None = None) -> dict[str, object]:
    """Bind the decision-free packet and optional Markdown view."""
    if not _self_hash_valid(packet, "packet_sha256") or packet.get("no_model_or_retrieval_inputs") is not True:
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_READINESS_INPUT_INVALID")
    payload = {
        "metamorphic_registry_sha256": packet["metamorphic_registry_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "relevance_registry_sha256": packet["relevance_registry_sha256"],
        "schema_version": "relevance-metamorphic-review-readiness-v1",
        "status": "ready_for_human",
    }
    if markdown is not None:
        payload["markdown_sha256"] = sha256_bytes(markdown)
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_relevance_metamorphic_decision_v1(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object],
) -> dict[str, object]:
    """Require an explicit response for every relevance row and direction."""
    required = {
        "aggregate_disposition", "aggregate_rationale", "attestation", "decision_sha256",
        "direction_reviews", "packet_sha256", "readiness_sha256", "relevance_reviews",
        "reviewer_id", "schema_version", "signature", "timestamp_utc",
    }
    if not isinstance(decision, dict) or set(decision) != required or decision.get("schema_version") != "relevance-metamorphic-review-decision-v1":
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get("readiness_sha256") != readiness.get("readiness_sha256"):
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_BINDING_INVALID")
    if not _self_hash_valid(decision, "decision_sha256"):
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not _text(decision.get(field)):
            raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise RelevanceValidationError(str(error)) from error
    dispositions = {"approved", "disputed", "excluded"}
    if decision.get("aggregate_disposition") not in dispositions:
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    expected_cases = [
        item["case_id"]
        for item in [*packet["strict_relevance_rows"], *packet["auxiliary_relevance_rows"]]
    ]
    relevance_reviews = decision.get("relevance_reviews")
    if not isinstance(relevance_reviews, list) or [item.get("case_id") if isinstance(item, Mapping) else None for item in relevance_reviews] != expected_cases:
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    expected_directions = [item["direction_id"] for item in packet["metamorphic_directions"]]
    direction_reviews = decision.get("direction_reviews")
    if not isinstance(direction_reviews, list) or [item.get("direction_id") if isinstance(item, Mapping) else None for item in direction_reviews] != expected_directions:
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    for review in [*relevance_reviews, *direction_reviews]:
        if not isinstance(review, Mapping) or set(review) not in (
            {"case_id", "disposition", "rationale"},
            {"direction_id", "disposition", "rationale"},
        ) or review.get("disposition") not in dispositions or not _text(review.get("rationale")):
            raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCOMPLETE")
    availability = {item["direction_id"]: item["availability"] for item in packet["metamorphic_directions"]}
    if any(availability[item["direction_id"]] == "unavailable" and item["disposition"] != "excluded" for item in direction_reviews):
        raise RelevanceValidationError("RELEVANCE_METAMORPHIC_DECISION_INCONSISTENT")
    return decision


def write_relevance_metamorphic_readiness_v1(*, packet: Mapping[str, object], markdown: bytes | None = None) -> dict[str, object]:
    """Compatibility name for the immutable readiness constructor."""
    return build_relevance_metamorphic_readiness_v1(packet=packet, markdown=markdown)
