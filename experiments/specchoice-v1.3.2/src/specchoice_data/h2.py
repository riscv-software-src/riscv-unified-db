# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Whole-chain H2 audit and approved-only Phase 3 data authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    read_authoritative_file,
    write_exact_descriptor_files,
)
from specchoice_measurement.strict_json import decode_strict_json

from .admission import admit_pair_candidate_v1, validate_candidate_inventory_v1
from .cli import require_phase2_local_closure
from .relevance import (
    build_relevance_metamorphic_packet_v1,
    build_relevance_metamorphic_readiness_v1,
    render_relevance_metamorphic_markdown_v1,
    validate_metamorphic_registry_v1,
    validate_pair_relevance_registry_v1,
    validate_relevance_metamorphic_decision_v1,
)
from .review import (
    build_pair_review_packet_v1,
    build_pair_review_readiness_v1,
    render_pair_review_markdown_v1,
    validate_pair_review_decision_v1,
)
from .schema import DataSchemaError, require_canonical_utc
from .split_review import (
    build_family_split_review_packet_v1,
    build_family_split_review_readiness_v1,
    render_family_split_review_markdown_v1,
    validate_family_split_review_decision_v1,
)
from .splits import validate_family_registry_v1, validate_split_manifest_v1


class H2ValidationError(ValueError):
    """Stable failure for the H2 data authority boundary."""


@dataclass(frozen=True)
class EligibilityAudit:
    """Separate contributing ID buckets and non-count invariant state."""

    ids: Mapping[str, tuple[str, ...]]
    invariants: Mapping[str, bool]
    terminal_buckets_disjoint: bool
    failure_analysis: tuple[Mapping[str, object], ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        return {key: len(value) for key, value in sorted(self.ids.items())}

    def as_dict(self) -> dict[str, object]:
        return {
            "counts": self.counts,
            "ids": {key: list(value) for key, value in sorted(self.ids.items())},
            "invariants": dict(sorted(self.invariants.items())),
            "pair_admission_failure_analysis": [dict(item) for item in self.failure_analysis],
            "terminal_buckets_disjoint": self.terminal_buckets_disjoint,
        }


_PATHS = (
    "data/preregistration/candidates-v1/candidate-inventory.json",
    "data/preregistration/candidates-v1/pairs/warl-implementation-selected-vs-isa-fixed.json",
    "reports/h2/pair-review-v1/review-packet.json",
    "receipts/pair-review-readiness-v1.json",
    "reviews/pair-review-decision-v1.json",
    "reviews/pair-authoring-rejections-v1.json",
    "data/preregistration/family-registry-v1.json",
    "data/preregistration/split-manifest-v1.json",
    "reports/h2/family-split-review-v1/review-packet.json",
    "receipts/family-split-review-readiness-v1.json",
    "reviews/family-split-review-decision-v1.json",
    "data/preregistration/pair-relevance-registry-v1.json",
    "data/preregistration/metamorphic-registry-v1.json",
    "reports/h2/relevance-metamorphic-review-v1/review-packet.json",
    "receipts/relevance-metamorphic-review-readiness-v1.json",
    "reviews/relevance-metamorphic-review-decision-v1.json",
)


def _self_hash_valid(value: Mapping[str, object], field: str) -> bool:
    payload = {key: value[key] for key in value if key != field}
    return value.get(field) == sha256_bytes(canonical_json_bytes(payload))


def _load_canonical(root: Path, relative: str) -> tuple[dict[str, object], bytes]:
    try:
        _, raw = read_authoritative_file(root, relative)
        value = decode_strict_json(raw)
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        raise H2ValidationError("H2_CHAIN_INPUT_INVALID") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
    return value, raw


def validate_phase3_chain_v1(
    *, experiment_root: Path, overrides: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Reopen and recompute every Phase 3 edge from the approved Phase 2 gate."""
    try:
        gate = require_phase2_local_closure()
        if not gate.get("approved"):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        schema_value, schema_raw = _load_canonical(experiment_root, "config/data/phase3-data-schema-v1.json")
        del schema_value
        artifacts: dict[str, dict[str, object]] = {}
        raw_by_path: dict[str, bytes] = {}
        for relative in _PATHS:
            value, raw = _load_canonical(experiment_root, relative)
            artifacts[relative] = value
            raw_by_path[relative] = raw
        if overrides:
            for relative, value in overrides.items():
                if relative not in artifacts or not isinstance(value, Mapping):
                    raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
                artifacts[relative] = dict(value)

        inventory_path = "data/preregistration/candidates-v1/candidate-inventory.json"
        candidate_path = "data/preregistration/candidates-v1/pairs/warl-implementation-selected-vs-isa-fixed.json"
        inventory = artifacts[inventory_path]
        if (
            inventory.get("bindings", {}).get("phase2_authority_sha256") != gate["authority_sha256"]
            or inventory.get("bindings", {}).get("h1_decision_sha256") != gate["decision_sha256"]
        ):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        candidate_root = experiment_root / "data/preregistration/candidates-v1"
        validate_candidate_inventory_v1(candidate_root=candidate_root, inventory=inventory, schema_raw=schema_raw)
        admission = admit_pair_candidate_v1(
            candidate_root=candidate_root,
            candidate_path="pairs/warl-implementation-selected-vs-isa-fixed.json",
            inventory=inventory,
            accepted_root=gate["accepted_root"],
            schema_raw=schema_raw,
        )
        if not admission.valid or admission.candidate != artifacts[candidate_path]:
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")

        pair_packet = artifacts["reports/h2/pair-review-v1/review-packet.json"]
        fresh_pair_packet = build_pair_review_packet_v1(admission=admission, inventory=inventory)
        if pair_packet != fresh_pair_packet:
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        pair_markdown = render_pair_review_markdown_v1(pair_packet)
        _, observed_pair_markdown = read_authoritative_file(experiment_root, "reports/h2/pair-review-v1/review-packet.md")
        if observed_pair_markdown != pair_markdown:
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        pair_readiness = artifacts["receipts/pair-review-readiness-v1.json"]
        if pair_readiness != build_pair_review_readiness_v1(packet=pair_packet, markdown=pair_markdown):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        pair_decision = artifacts["reviews/pair-review-decision-v1.json"]
        validate_pair_review_decision_v1(decision=pair_decision, packet=pair_packet, readiness=pair_readiness)
        rejection_audit = artifacts["reviews/pair-authoring-rejections-v1.json"]
        if (
            rejection_audit.get("schema_version") != "pair-authoring-rejections-v1"
            or rejection_audit.get("bindings") != {
                "candidate_inventory_sha256": inventory["inventory_sha256"],
                "h1_decision_sha256": gate["decision_sha256"],
                "pair_review_decision_sha256": pair_decision["decision_sha256"],
            }
            or not isinstance(rejection_audit.get("rejections"), list)
            or not isinstance(rejection_audit.get("no_replacement_attestation"), str)
            or not rejection_audit["no_replacement_attestation"].strip()
        ):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")

        family = artifacts["data/preregistration/family-registry-v1.json"]
        validate_family_registry_v1(
            family,
            candidate_inventory_sha256=str(inventory["inventory_sha256"]),
            pair_review_decision_sha256=str(pair_decision["decision_sha256"]),
        )
        manifest = artifacts["data/preregistration/split-manifest-v1.json"]
        validate_split_manifest_v1(
            manifest,
            registry=family,
            prototype_pairs=[admission.candidate],
            held_out_items=[],
            demonstrations=[],
        )
        family_packet = artifacts["reports/h2/family-split-review-v1/review-packet.json"]
        if family_packet != build_family_split_review_packet_v1(registry=family, manifest=manifest):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        family_markdown = render_family_split_review_markdown_v1(family_packet)
        _, observed_family_markdown = read_authoritative_file(experiment_root, "reports/h2/family-split-review-v1/review-packet.md")
        if observed_family_markdown != family_markdown:
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        family_readiness = artifacts["receipts/family-split-review-readiness-v1.json"]
        if family_readiness != build_family_split_review_readiness_v1(packet=family_packet, markdown=family_markdown):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        family_decision = artifacts["reviews/family-split-review-decision-v1.json"]
        validate_family_split_review_decision_v1(decision=family_decision, packet=family_packet, readiness=family_readiness)

        relevance = artifacts["data/preregistration/pair-relevance-registry-v1.json"]
        relevance_bindings = {
            "candidate_inventory_sha256": inventory["inventory_sha256"],
            "family_registry_sha256": family["registry_sha256"],
            "family_registry_version": family["registry_version"],
            "family_split_decision_sha256": family_decision["decision_sha256"],
            "pair_review_decision_sha256": pair_decision["decision_sha256"],
            "split_manifest_sha256": manifest["manifest_sha256"],
        }
        pair_relationship = admission.candidate["relationship"]
        validate_pair_relevance_registry_v1(
            relevance,
            split_manifest=manifest,
            approved_pairs={str(admission.candidate_id): pair_relationship},
            expected_bindings=relevance_bindings,
            case_targets={},
        )
        metamorphic = artifacts["data/preregistration/metamorphic-registry-v1.json"]
        metamorphic_bindings = {**relevance_bindings, "relevance_registry_sha256": relevance["registry_sha256"]}
        frozen_metamorphic_ids: set[str] = set()
        validate_metamorphic_registry_v1(
            metamorphic,
            expected_bindings=metamorphic_bindings,
            accepted_root=gate["accepted_root"],
            frozen_metamorphic_candidate_ids=frozen_metamorphic_ids,
            dataset_member_ids=set(
                [*manifest["prototype_pair_ids"], *manifest["strict_case_ids"], *manifest["auxiliary_case_ids"]]
            ),
        )
        relevance_packet = artifacts["reports/h2/relevance-metamorphic-review-v1/review-packet.json"]
        if relevance_packet != build_relevance_metamorphic_packet_v1(relevance=relevance, metamorphic=metamorphic):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        relevance_markdown = render_relevance_metamorphic_markdown_v1(relevance_packet)
        _, observed_relevance_markdown = read_authoritative_file(
            experiment_root, "reports/h2/relevance-metamorphic-review-v1/review-packet.md"
        )
        if observed_relevance_markdown != relevance_markdown:
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        relevance_readiness = artifacts["receipts/relevance-metamorphic-review-readiness-v1.json"]
        if relevance_readiness != build_relevance_metamorphic_readiness_v1(packet=relevance_packet, markdown=relevance_markdown):
            raise H2ValidationError("H2_CHAIN_INPUT_INVALID")
        relevance_decision = artifacts["reviews/relevance-metamorphic-review-decision-v1.json"]
        validate_relevance_metamorphic_decision_v1(
            decision=relevance_decision, packet=relevance_packet, readiness=relevance_readiness
        )

        bindings_payload = {
            "candidate_inventory_sha256": inventory["inventory_sha256"],
            "family_registry_sha256": family["registry_sha256"],
            "family_split_decision_sha256": family_decision["decision_sha256"],
            "h1_decision_sha256": gate["decision_sha256"],
            "metamorphic_registry_sha256": metamorphic["registry_sha256"],
            "pair_authoring_rejections_file_sha256": sha256_bytes(
                raw_by_path["reviews/pair-authoring-rejections-v1.json"]
            ),
            "pair_review_decision_sha256": pair_decision["decision_sha256"],
            "phase2_authority_sha256": gate["authority_sha256"],
            "phase3_schema_sha256": sha256_bytes(schema_raw),
            "relevance_metamorphic_decision_sha256": relevance_decision["decision_sha256"],
            "relevance_registry_sha256": relevance["registry_sha256"],
            "split_manifest_sha256": manifest["manifest_sha256"],
        }
        bindings = {
            **bindings_payload,
            "phase3_chain_sha256": sha256_bytes(canonical_json_bytes(bindings_payload)),
        }
        metamorphic_states = {
            item["direction_id"]: (
                "excluded_unavailable"
                if item["availability"] == "unavailable"
                else "approved_available"
            )
            for item in metamorphic["directions"]
        }
        invariants = {
            "demonstration_leakage_free": True,
            "example_isolation": True,
            "family_isolation": True,
            "frozen_inventory_unchanged": True,
            "provenance_valid": True,
            "reviews_complete": True,
        }
        audit_material = {
            "auxiliary_case_ids": manifest["auxiliary_case_ids"],
            "held_out_dispositions": {},
            "invariants": invariants,
            "metamorphic_directions": metamorphic_states,
            "pair_authoring_rejections": rejection_audit["rejections"],
            "pair_dispositions": {str(admission.candidate_id): "approved_qualifying"},
            "relevance_dispositions": {},
            "strict_case_ids": manifest["strict_case_ids"],
        }
        return {
            "artifacts": artifacts,
            "audit_material": audit_material,
            "bindings": bindings,
            "invariants": invariants,
        }
    except Exception as error:
        if isinstance(error, H2ValidationError) and not overrides:
            raise
        code = "FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION" if overrides else "H2_CHAIN_INVALID"
        raise H2ValidationError(code) from error


def _ids_for(dispositions: Mapping[str, str], state: str) -> tuple[str, ...]:
    return tuple(sorted(item_id for item_id, observed in dispositions.items() if observed == state))


def _disjoint(*values: tuple[str, ...]) -> bool:
    seen: set[str] = set()
    for value in values:
        current = set(value)
        if seen.intersection(current):
            return False
        seen.update(current)
    return True


def audit_phase3_counts_v1(chain: Mapping[str, object]) -> EligibilityAudit:
    """Compute stable separate terminal and contributing buckets."""
    material = chain.get("audit_material")
    if not isinstance(material, Mapping):
        raise H2ValidationError("H2_COUNT_INPUT_INVALID")
    pairs = material.get("pair_dispositions")
    held_out = material.get("held_out_dispositions")
    relevance = material.get("relevance_dispositions")
    metamorphic = material.get("metamorphic_directions")
    invariants = material.get("invariants")
    if not all(isinstance(item, Mapping) for item in (pairs, held_out, relevance, metamorphic, invariants)):
        raise H2ValidationError("H2_COUNT_INPUT_INVALID")
    assert isinstance(pairs, Mapping) and isinstance(held_out, Mapping)
    assert isinstance(relevance, Mapping) and isinstance(metamorphic, Mapping)
    assert isinstance(invariants, Mapping)
    pair_qualifying = _ids_for(pairs, "approved_qualifying")
    pair_invalid = _ids_for(pairs, "structurally_invalid")
    pair_disputed = _ids_for(pairs, "disputed")
    pair_excluded = _ids_for(pairs, "excluded")
    pair_reused = _ids_for(pairs, "reused_nonqualifying")
    held_invalid = _ids_for(held_out, "structurally_invalid")
    held_disputed = _ids_for(held_out, "disputed")
    held_excluded = _ids_for(held_out, "excluded")
    held_strict = _ids_for(held_out, "approved_strict")
    held_auxiliary = _ids_for(held_out, "approved_auxiliary")
    ids = {
        "auxiliary_approved": held_auxiliary,
        "held_out_candidates": tuple(sorted(held_out)),
        "held_out_auxiliary": held_auxiliary,
        "held_out_disputed": held_disputed,
        "held_out_excluded": held_excluded,
        "held_out_invalid": held_invalid,
        "metamorphic_available_approved": _ids_for(metamorphic, "approved_available"),
        "metamorphic_disputed": _ids_for(metamorphic, "disputed"),
        "metamorphic_excluded_unavailable": _ids_for(metamorphic, "excluded_unavailable"),
        "pair_approved": pair_qualifying,
        "pair_candidates": tuple(sorted(pairs)),
        "pair_disputed": pair_disputed,
        "pair_excluded": pair_excluded,
        "pair_reused_nonqualifying": pair_reused,
        "pair_structurally_invalid": pair_invalid,
        "qualifying_pairs": pair_qualifying,
        "relevance_covered": _ids_for(relevance, "relevant_pairs"),
        "relevance_disputed": _ids_for(relevance, "disputed"),
        "relevance_no_relevant": _ids_for(relevance, "no_relevant_pair"),
        "strict_approved": held_strict,
    }
    terminal_disjoint = (
        _disjoint(pair_qualifying, pair_invalid, pair_disputed, pair_excluded, pair_reused)
        and _disjoint(held_invalid, held_disputed, held_excluded, held_strict, held_auxiliary)
        and _disjoint(
            ids["metamorphic_available_approved"],
            ids["metamorphic_disputed"],
            ids["metamorphic_excluded_unavailable"],
        )
    )
    normalized_invariants = {
        str(key): value for key, value in invariants.items() if isinstance(value, bool)
    }
    if len(normalized_invariants) != len(invariants):
        raise H2ValidationError("H2_COUNT_INPUT_INVALID")
    failure_analysis = material.get("pair_authoring_rejections", [])
    if not isinstance(failure_analysis, list) or any(not isinstance(item, Mapping) for item in failure_analysis):
        raise H2ValidationError("H2_COUNT_INPUT_INVALID")
    return EligibilityAudit(
        ids=ids,
        invariants=normalized_invariants,
        terminal_buckets_disjoint=terminal_disjoint,
        failure_analysis=tuple(dict(item) for item in failure_analysis),
    )


def derive_data_eligibility_v1(audit: EligibilityAudit) -> dict[str, object]:
    """Derive exactly one Green, Yellow, or Red feasibility result."""
    if not audit.terminal_buckets_disjoint or not audit.invariants or not all(audit.invariants.values()):
        raise H2ValidationError("H2_NON_COUNT_INVARIANT_INVALID")
    pairs = len(audit.ids.get("qualifying_pairs", ()))
    strict = len(audit.ids.get("strict_approved", ()))
    if pairs >= 6 and strict >= 10:
        status = "green_eligible"
    elif pairs >= 4 and strict >= 6:
        status = "yellow_eligible"
    else:
        status = "red_required"
    metamorphic_available = len(audit.ids.get("metamorphic_available_approved", ()))
    metamorphic_unavailable = len(audit.ids.get("metamorphic_excluded_unavailable", ()))
    payload = {
        "audit": audit.as_dict(),
        "corpus_coverage_audit": {
            "green_pair_shortfall": max(0, 6 - pairs),
            "green_strict_shortfall": max(0, 10 - strict),
            "metamorphic_available": metamorphic_available,
            "metamorphic_unavailable": metamorphic_unavailable,
            "qualifying_natural_pairs": pairs,
            "strict_cases": strict,
            "yellow_pair_shortfall": max(0, 4 - pairs),
            "yellow_strict_shortfall": max(0, 6 - strict),
        },
        "eligibility_status": status,
        "external_publication_authorized": False,
        "model_experiment_authorized": False,
        "phase4_decision_required": True,
        "pair_admission_failure_analysis": [dict(item) for item in audit.failure_analysis],
        "qualifying_pair_count": pairs,
        "qualifying_pair_ids": list(audit.ids.get("qualifying_pairs", ())),
        "reason": (
            "insufficient H1-consistent, controlled natural contrastive pairs and strict held-out cases"
            if status == "red_required"
            else "approved counts satisfy the deterministic preregistered threshold"
        ),
        "retrieval_authorized": False,
        "schema_version": "data-eligibility-v1",
        "strict_case_count": strict,
        "strict_case_ids": list(audit.ids.get("strict_approved", ())),
        "thresholds": {
            "green": {"qualifying_pairs": 6, "strict_cases": 10},
            "yellow": {"qualifying_pairs": 4, "strict_cases": 6},
        },
    }
    return {**payload, "report_sha256": sha256_bytes(canonical_json_bytes(payload))}


_ACK_CATEGORIES = (
    "audited_counts",
    "human_decisions",
    "invariant_results",
    "proposed_eligibility",
    "quarantine_and_exclusions",
    "threshold_derivation",
    "upstream_identities",
)


def build_h2_review_packet_v1(
    *, chain: Mapping[str, object], audit: EligibilityAudit, eligibility: Mapping[str, object],
) -> dict[str, object]:
    """Build the final decision-free H2 data review packet."""
    bindings = chain.get("bindings")
    invariants = chain.get("invariants")
    if not isinstance(bindings, Mapping) or not isinstance(invariants, Mapping) or not _self_hash_valid(eligibility, "report_sha256"):
        raise H2ValidationError("H2_PACKET_INPUT_INVALID")
    payload = {
        "audit": audit.as_dict(),
        "bindings": dict(bindings),
        "eligibility": dict(eligibility),
        "invariants": dict(invariants),
        "no_model_or_retrieval_inputs": True,
        "not_final_phase4_execution_authority": True,
        "required_acknowledgment_categories": list(_ACK_CATEGORIES),
        "schema_version": "h2-data-review-packet-v1",
        "warning": "NOT FINAL PHASE 4 EXECUTION AUTHORITY",
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h2_review_markdown_v1(packet: Mapping[str, object]) -> bytes:
    """Render the complete canonical H2 packet without editable machine fields."""
    return (
        "# Phase 3 H2 Data Review\n\n"
        "**NOT FINAL PHASE 4 EXECUTION AUTHORITY**\n\n"
        f"Proposed eligibility: `{packet.get('eligibility', {}).get('eligibility_status')}`\n\n"
        "## Canonical packet\n\n```json\n"
    ).encode("utf-8") + canonical_json_bytes(packet) + b"```\n"


def build_h2_review_readiness_v1(*, packet: Mapping[str, object], markdown: bytes) -> dict[str, object]:
    """Bind both decision-free packet forms."""
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or render_h2_review_markdown_v1(packet) != markdown
        or packet.get("no_model_or_retrieval_inputs") is not True
        or packet.get("not_final_phase4_execution_authority") is not True
    ):
        raise H2ValidationError("H2_READINESS_INPUT_INVALID")
    payload = {
        "eligibility_status": packet["eligibility"]["eligibility_status"],
        "markdown_sha256": sha256_bytes(markdown),
        "packet_sha256": packet["packet_sha256"],
        "phase3_chain_sha256": packet["bindings"].get("phase3_chain_sha256"),
        "schema_version": "h2-data-review-readiness-v1",
        "status": "ready_for_human",
        "warning": "NOT FINAL PHASE 4 EXECUTION AUTHORITY",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h2_review_readiness_v1(*, packet: Mapping[str, object], markdown: bytes) -> dict[str, object]:
    """Compatibility name for the immutable readiness constructor."""
    return build_h2_review_readiness_v1(packet=packet, markdown=markdown)


def validate_h2_data_decision_v1(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object],
) -> dict[str, object]:
    """Validate a complete genuine H2 response without inferring approval."""
    required = {
        "acknowledgments", "aggregate_disposition", "aggregate_rationale", "attestation",
        "decision_sha256", "packet_sha256", "readiness_sha256", "reviewer_id",
        "schema_version", "signature", "timestamp_utc",
    }
    if not isinstance(decision, dict) or set(decision) != required or decision.get("schema_version") != "h2-data-decision-v1":
        raise H2ValidationError("H2_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get("readiness_sha256") != readiness.get("readiness_sha256"):
        raise H2ValidationError("H2_DECISION_BINDING_INVALID")
    if not _self_hash_valid(decision, "decision_sha256"):
        raise H2ValidationError("H2_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise H2ValidationError("H2_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "H2_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise H2ValidationError(str(error)) from error
    dispositions = {"approved", "disputed", "incomplete"}
    aggregate = decision.get("aggregate_disposition")
    if aggregate not in dispositions:
        raise H2ValidationError("H2_DECISION_INCOMPLETE")
    acknowledgments = decision.get("acknowledgments")
    expected = packet.get("required_acknowledgment_categories")
    if not isinstance(acknowledgments, list) or [item.get("category") if isinstance(item, Mapping) else None for item in acknowledgments] != expected:
        raise H2ValidationError("H2_DECISION_INCOMPLETE")
    for item in acknowledgments:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"category", "disposition", "rationale"}
            or item.get("disposition") not in dispositions
            or not isinstance(item.get("rationale"), str)
            or not item["rationale"].strip()
        ):
            raise H2ValidationError("H2_DECISION_INCOMPLETE")
    if aggregate == "approved" and any(item["disposition"] != "approved" for item in acknowledgments):
        raise H2ValidationError("H2_DECISION_INCONSISTENT")
    return decision


def _build_data_authority_v1(
    *, chain: Mapping[str, object], audit: EligibilityAudit, eligibility: Mapping[str, object], decision: Mapping[str, object],
) -> dict[str, object]:
    bindings = chain.get("bindings")
    if not isinstance(bindings, Mapping):
        raise H2ValidationError("DATA_AUTHORITY_INPUT_INVALID")
    payload = {
        "approved_qualifying_pair_ids": list(audit.ids.get("qualifying_pairs", ())),
        "approved_strict_case_ids": list(audit.ids.get("strict_approved", ())),
        "audit": audit.as_dict(),
        "auxiliary_case_ids": list(audit.ids.get("auxiliary_approved", ())),
        "bindings": dict(bindings),
        "eligibility_report_sha256": eligibility["report_sha256"],
        "eligibility_status": eligibility["eligibility_status"],
        "external_publication_authorized": False,
        "h2_decision_sha256": decision["decision_sha256"],
        "model_execution_authorized": False,
        "phase4_decision_required": True,
        "quarantined_ids": sorted(
            {
                *audit.ids.get("pair_disputed", ()), *audit.ids.get("pair_excluded", ()),
                *audit.ids.get("pair_structurally_invalid", ()), *audit.ids.get("pair_reused_nonqualifying", ()),
                *audit.ids.get("held_out_disputed", ()), *audit.ids.get("held_out_excluded", ()),
                *audit.ids.get("held_out_invalid", ()), *audit.ids.get("metamorphic_disputed", ()),
                *audit.ids.get("metamorphic_excluded_unavailable", ()),
            }
        ),
        "retrieval_authorized": False,
        "schema_version": "phase3-data-authority-v1",
    }
    return {**payload, "authority_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_data_eligibility_markdown_v1(report: Mapping[str, object]) -> bytes:
    """Render eligibility only from canonical JSON."""
    return (
        "# Phase 3 Data Eligibility\n\n"
        "**NOT FINAL PHASE 4 EXECUTION AUTHORITY**\n\n"
        f"Eligibility: `{report.get('eligibility_status')}`\n\n"
        f"Report SHA-256: `{report.get('report_sha256')}`\n\n"
        "## Canonical report\n\n```json\n"
    ).encode("utf-8") + canonical_json_bytes(report) + b"```\n"


def validate_phase3_data_authority_v1(
    *, authority: object, chain: Mapping[str, object], decision: Mapping[str, object], eligibility: Mapping[str, object],
) -> dict[str, object]:
    """Validate authority against the exact current chain, decision, and report."""
    if not isinstance(authority, dict) or authority.get("schema_version") != "phase3-data-authority-v1" or not _self_hash_valid(authority, "authority_sha256"):
        raise H2ValidationError("DATA_AUTHORITY_INVALID")
    if authority.get("bindings") != chain.get("bindings"):
        raise H2ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    if authority.get("h2_decision_sha256") != decision.get("decision_sha256") or authority.get("eligibility_report_sha256") != eligibility.get("report_sha256") or authority.get("eligibility_status") != eligibility.get("eligibility_status"):
        raise H2ValidationError("DATA_AUTHORITY_BINDING_INVALID")
    if authority.get("eligibility_status") not in {"green_eligible", "yellow_eligible", "red_required"}:
        raise H2ValidationError("DATA_AUTHORITY_INVALID")
    if any(authority.get(field) is not False for field in ("retrieval_authorized", "model_execution_authorized", "external_publication_authorized")) or authority.get("phase4_decision_required") is not True:
        raise H2ValidationError("DATA_AUTHORITY_SCOPE_INVALID")
    return authority


def write_phase3_data_authority_v1(
    *, output_root: Path, chain: Mapping[str, object], audit: EligibilityAudit,
    eligibility: Mapping[str, object], decision: Mapping[str, object],
    packet: Mapping[str, object], readiness: Mapping[str, object],
) -> dict[str, object]:
    """Publish or exactly resume authority and eligibility projections as one file set."""
    validate_h2_data_decision_v1(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved":
        raise H2ValidationError("H2_APPROVAL_REQUIRED")
    if not _self_hash_valid(eligibility, "report_sha256"):
        raise H2ValidationError("DATA_AUTHORITY_INPUT_INVALID")
    authority = _build_data_authority_v1(chain=chain, audit=audit, eligibility=eligibility, decision=decision)
    validate_phase3_data_authority_v1(
        authority=authority, chain=chain, decision=decision, eligibility=eligibility
    )
    markdown = render_data_eligibility_markdown_v1(eligibility)
    payloads = {
        "phase3/data-authority-v1.json": canonical_json_bytes(authority),
        "reports/h2/data-eligibility-v1.json": canonical_json_bytes(eligibility),
        "reports/h2/data-eligibility-v1.md": markdown,
    }
    try:
        write_exact_descriptor_files(output_root, payloads)
    except (FilesystemPolicyError, OSError) as error:
        raise H2ValidationError("DATA_AUTHORITY_WRITE_INVALID") from error
    return {"authority": authority, "eligibility": dict(eligibility), "markdown": markdown}
