# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Closed family registry and deterministic strict/auxiliary split primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from specchoice_evidence.canonical import canonical_json_bytes, require_sha256, sha256_bytes
from specchoice_measurement.diagnostics import Diagnostic, ordered_diagnostics


class SplitValidationError(ValueError):
    """Stable failure for Phase 3 family or split authority."""


@dataclass(frozen=True)
class SplitAudit:
    qualifying_pair_ids: tuple[str, ...]
    reused_pair_ids: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]


def _diag(code: str, field: str, *, item_id: str | None = None) -> Diagnostic:
    return Diagnostic(code, "blocker", fixture_id=item_id, field=field)


def _nonempty_strings(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item.strip() for item in value)
        and value == sorted(set(value))
    )


def validate_family_registry_v1(
    registry: object, *, candidate_inventory_sha256: str, pair_review_decision_sha256: str,
) -> dict[str, object]:
    """Validate definition-first family authority and exact primary assignments."""
    if not isinstance(registry, dict) or set(registry) != {
        "assignments", "bindings", "families", "registry_sha256", "registry_version", "schema_version"
    }:
        raise SplitValidationError("FAMILY_REGISTRY_INVALID")
    if registry.get("schema_version") != "family-registry-v1" or not isinstance(registry.get("registry_version"), str) or not registry["registry_version"]:
        raise SplitValidationError("FAMILY_REGISTRY_INVALID")
    families = registry.get("families")
    if not isinstance(families, list) or not families:
        raise SplitValidationError("FAMILY_REGISTRY_INVALID")
    family_ids: list[str] = []
    approved: set[str] = set()
    for family in families:
        if not isinstance(family, Mapping) or set(family) != {
            "definition", "exclusion_criteria", "family_id", "inclusion_criteria", "review_state"
        }:
            raise SplitValidationError("FAMILY_REGISTRY_INVALID")
        family_id = family.get("family_id")
        if (
            not isinstance(family_id, str) or not family_id or family_id == "ambiguous"
            or not isinstance(family.get("definition"), str) or not family["definition"].strip()
            or not _nonempty_strings(family.get("inclusion_criteria"))
            or not _nonempty_strings(family.get("exclusion_criteria"))
            or family.get("review_state") not in {"approved", "disputed", "excluded"}
        ):
            raise SplitValidationError("FAMILY_REGISTRY_INVALID")
        family_ids.append(family_id)
        if family["review_state"] == "approved":
            approved.add(family_id)
    if family_ids != sorted(set(family_ids)):
        raise SplitValidationError("FAMILY_REGISTRY_INVALID")

    assignments = registry.get("assignments")
    if not isinstance(assignments, list):
        raise SplitValidationError("PRIMARY_FAMILY_INVALID")
    item_ids: list[str] = []
    for assignment in assignments:
        if not isinstance(assignment, Mapping) or set(assignment) != {
            "item_id", "item_version", "primary_family", "secondary_tags"
        }:
            raise SplitValidationError("PRIMARY_FAMILY_INVALID")
        item_id = assignment.get("item_id")
        primary = assignment.get("primary_family")
        if (
            not isinstance(item_id, str) or not item_id
            or not isinstance(assignment.get("item_version"), str) or not assignment["item_version"]
            or not isinstance(primary, str) or not primary or primary == "ambiguous" or primary not in approved
            or not _nonempty_strings(assignment.get("secondary_tags"), allow_empty=True)
        ):
            raise SplitValidationError("PRIMARY_FAMILY_INVALID")
        item_ids.append(item_id)
    if item_ids != sorted(set(item_ids)):
        raise SplitValidationError("PRIMARY_FAMILY_INVALID")

    bindings = registry.get("bindings")
    try:
        if (
            not isinstance(bindings, Mapping)
            or set(bindings) != {"candidate_inventory_sha256", "pair_review_decision_sha256"}
            or require_sha256(candidate_inventory_sha256) != bindings["candidate_inventory_sha256"]
            or require_sha256(pair_review_decision_sha256) != bindings["pair_review_decision_sha256"]
        ):
            raise SplitValidationError("FAMILY_REGISTRY_BINDING_INVALID")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, SplitValidationError):
            raise
        raise SplitValidationError("FAMILY_REGISTRY_BINDING_INVALID") from error
    payload = {key: registry[key] for key in registry if key != "registry_sha256"}
    if registry.get("registry_sha256") != sha256_bytes(canonical_json_bytes(payload)):
        raise SplitValidationError("FAMILY_REGISTRY_HASH_INVALID")
    return registry


def invalidate_registry_dependents_v1(
    *, registry: Mapping[str, object], dependents: Sequence[Mapping[str, object]],
) -> tuple[Diagnostic, ...]:
    """Report every stale dependent without rewriting any artifact."""
    diagnostics = [
        _diag("FAMILY_REGISTRY_DEPENDENT_STALE", str(item.get("artifact_id", "dependent")))
        for item in dependents
        if item.get("registry_version") != registry.get("registry_version")
        or item.get("registry_sha256") != registry.get("registry_sha256")
    ]
    return ordered_diagnostics(diagnostics)


def _pair_identities(pair: Mapping[str, object]) -> tuple[set[str], set[tuple[str, int, int]]]:
    examples: set[str] = set()
    spans: set[tuple[str, int, int]] = set()
    sides = pair.get("sides")
    if not isinstance(sides, list) or len(sides) != 2:
        raise SplitValidationError("PROTOTYPE_PAIR_INVALID")
    for side in sides:
        if not isinstance(side, Mapping) or not isinstance(side.get("example_id"), str) or not isinstance(side.get("source_sha256"), str):
            raise SplitValidationError("PROTOTYPE_PAIR_INVALID")
        examples.add(str(side["example_id"]))
        side_spans = side.get("spans")
        if not isinstance(side_spans, list) or not side_spans:
            raise SplitValidationError("PROTOTYPE_PAIR_INVALID")
        for span in side_spans:
            if not isinstance(span, Mapping) or isinstance(span.get("start_byte"), bool) or not isinstance(span.get("start_byte"), int) or isinstance(span.get("end_byte"), bool) or not isinstance(span.get("end_byte"), int):
                raise SplitValidationError("PROTOTYPE_PAIR_INVALID")
            spans.add((str(side["source_sha256"]), int(span["start_byte"]), int(span["end_byte"])))
    return examples, spans


def audit_prototype_reuse_v1(pairs: Sequence[Mapping[str, object]]) -> SplitAudit:
    """Keep the first stable pair identity and quarantine every later reuse."""
    seen_examples: set[str] = set()
    seen_spans: set[tuple[str, int, int]] = set()
    qualifying: list[str] = []
    reused: list[str] = []
    diagnostics: list[Diagnostic] = []
    ordered_pairs = sorted(pairs, key=lambda item: str(item.get("candidate_id", "")))
    for pair in ordered_pairs:
        pair_id = pair.get("candidate_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise SplitValidationError("PROTOTYPE_PAIR_INVALID")
        examples, spans = _pair_identities(pair)
        duplicate_example = bool(examples & seen_examples)
        duplicate_span = bool(spans & seen_spans)
        if duplicate_example or duplicate_span:
            reused.append(pair_id)
            if duplicate_example:
                diagnostics.append(_diag("PROTOTYPE_EXAMPLE_ID_REUSED", "example_id", item_id=pair_id))
            if duplicate_span:
                diagnostics.append(_diag("PROTOTYPE_SOURCE_SPAN_REUSED", "source_span", item_id=pair_id))
            continue
        qualifying.append(pair_id)
        seen_examples.update(examples)
        seen_spans.update(spans)
    return SplitAudit(tuple(qualifying), tuple(reused), ordered_diagnostics(diagnostics))


def audit_held_out_demonstration_leakage_v1(
    *, held_out_items: Sequence[Mapping[str, object]], demonstrations: Sequence[Mapping[str, object]],
) -> tuple[Diagnostic, ...]:
    """Reject exact held-out passage identities present in any demonstration."""
    demo_ids = {
        (item.get("source_sha256"), item.get("start_byte"), item.get("end_byte"))
        for item in demonstrations
    }
    diagnostics: list[Diagnostic] = []
    for item in sorted(held_out_items, key=lambda value: str(value.get("item_id", ""))):
        for span in item.get("spans", []) if isinstance(item.get("spans"), list) else []:
            if isinstance(span, Mapping) and (item.get("source_sha256"), span.get("start_byte"), span.get("end_byte")) in demo_ids:
                diagnostics.append(_diag("HELD_OUT_PASSAGE_IN_DEMONSTRATION", "source_span", item_id=str(item.get("item_id"))))
    return ordered_diagnostics(diagnostics)


def derive_split_manifest_v1(
    *, registry: Mapping[str, object], prototype_pairs: Sequence[Mapping[str, object]],
    held_out_items: Sequence[Mapping[str, object]], demonstrations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Derive immutable memberships with no caller-provided split override."""
    bindings = registry.get("bindings")
    if not isinstance(bindings, Mapping):
        raise SplitValidationError("FAMILY_REGISTRY_BINDING_INVALID")
    validated = validate_family_registry_v1(
        registry,
        candidate_inventory_sha256=str(bindings.get("candidate_inventory_sha256")),
        pair_review_decision_sha256=str(bindings.get("pair_review_decision_sha256")),
    )
    assignments = {str(item["item_id"]): item for item in validated["assignments"]}
    reuse = audit_prototype_reuse_v1(prototype_pairs)
    pair_map = {str(pair["candidate_id"]): pair for pair in prototype_pairs}
    diagnostics = list(reuse.diagnostics)
    prototype_examples: set[str] = set()
    prototype_families: set[str] = set()
    accepted_pair_ids: list[str] = []
    for pair_id in reuse.qualifying_pair_ids:
        assignment = assignments.get(pair_id)
        if assignment is None:
            diagnostics.append(_diag("PRIMARY_FAMILY_INVALID", "prototype_assignment", item_id=pair_id))
            continue
        examples, _ = _pair_identities(pair_map[pair_id])
        prototype_examples.update(examples)
        prototype_families.add(str(assignment["primary_family"]))
        accepted_pair_ids.append(pair_id)

    strict: list[str] = []
    auxiliary: list[str] = []
    quarantined: list[dict[str, str]] = []
    strict_families: set[str] = set()
    for item in sorted(held_out_items, key=lambda value: str(value.get("item_id", ""))):
        item_id = item.get("item_id")
        assignment = assignments.get(str(item_id))
        if not isinstance(item_id, str) or assignment is None or item.get("item_version") != assignment.get("item_version"):
            diagnostics.append(_diag("PRIMARY_FAMILY_INVALID", "held_out_assignment", item_id=str(item_id)))
            continue
        if item.get("review_state") != "approved":
            quarantined.append({"item_id": item_id, "reason": f"review_{item.get('review_state', 'invalid')}"})
            continue
        example_id = item.get("example_id")
        if not isinstance(example_id, str) or example_id in prototype_examples:
            diagnostics.append(_diag("HELD_OUT_EXAMPLE_OVERLAP", "example_id", item_id=item_id))
            continue
        family = str(assignment["primary_family"])
        if family in prototype_families:
            auxiliary.append(item_id)
        else:
            strict.append(item_id)
            strict_families.add(family)
    diagnostics.extend(audit_held_out_demonstration_leakage_v1(held_out_items=held_out_items, demonstrations=demonstrations))
    ordered = ordered_diagnostics(diagnostics)
    payload = {
        "auxiliary_case_ids": sorted(auxiliary),
        "bindings": {
            "candidate_inventory_sha256": bindings["candidate_inventory_sha256"],
            "pair_review_decision_sha256": bindings["pair_review_decision_sha256"],
            "registry_sha256": validated["registry_sha256"],
            "registry_version": validated["registry_version"],
        },
        "diagnostics": [item.as_dict() for item in ordered],
        "prototype_example_ids": sorted(prototype_examples),
        "prototype_pair_ids": sorted(accepted_pair_ids),
        "prototype_primary_family_ids": sorted(prototype_families),
        "quarantined_items": quarantined,
        "ready": not ordered,
        "reused_prototype_pair_ids": list(reuse.reused_pair_ids),
        "schema_version": "split-manifest-v1",
        "strict_case_ids": sorted(strict),
        "strict_primary_family_ids": sorted(strict_families),
    }
    return {**payload, "manifest_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_split_manifest_v1(
    manifest: object, *, registry: Mapping[str, object], prototype_pairs: Sequence[Mapping[str, object]],
    held_out_items: Sequence[Mapping[str, object]], demonstrations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Require byte-independent semantic equality with a fresh pure derivation."""
    expected = derive_split_manifest_v1(
        registry=registry,
        prototype_pairs=prototype_pairs,
        held_out_items=held_out_items,
        demonstrations=demonstrations,
    )
    if manifest != expected:
        raise SplitValidationError("SPLIT_MANIFEST_INVALID")
    return expected
