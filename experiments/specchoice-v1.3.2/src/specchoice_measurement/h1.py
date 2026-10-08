# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Hash-bound H1 review material and validation of existing human decisions."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from specchoice_evidence.bundle import BundleError, _publish_directory_no_replace, _sync_directory, _write_exact
from specchoice_evidence.canonical import canonical_json_bytes, require_sha256, sha256_bytes
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    inspect_authoritative_path,
    read_authoritative_file,
    read_authoritative_files,
    write_new_descriptor_file,
)
from specchoice_evidence.runtime_closure import (
    RuntimeClosureError,
    verify_runtime_closure_v3,
    load_runtime_closure_v4,
)
from specchoice_evidence.publication import resolve_historical_path
from specchoice_evidence.successor import (
    SuccessorProtocolError,
    validate_accepted_v6_active_authority,
)

from .adapter import (
    AdapterError,
    build_pr2164_adapter_batch,
    validate_pr2164_accepted_v6_adapter_batch_v4,
)
from .attempts import (
    AttemptError,
    _successor_adapter_v6,
    validate_adversarial_result_v6,
    validate_fresh_adversarial_result_v7,
    validate_fresh_formal_measurement_v6,
    validate_formal_measurement_v5,
    validate_measurement_attempt,
)


class H1Error(ValueError):
    """Stable H1 packet or decision validation diagnostic."""


_V7_H1_QUESTION_IDS = (
    "ts03_adjacency", "ts03_empty_null_single_element", "ts03_equal_element_stable_order",
    "ts04_unclassified_manual_review", "ts05_adjacency", "ts05_empty_null_single_element",
    "ts05_equal_element_stable_order",
)
_V7_FIXTURE_IDS = (
    "CAND_WARL_FIXED_LEGAL_SET", "NEG_EXT_GATED_PBMTE", "NEG_FIXED_ENCODING",
    "NEG_SHALL_NO_DELEGATION", "NEG_SOFTWARE_ADVICE", "POS_CSR_RW_MTVEC_ACCESS",
    "POS_DIRECT_CACHE_BLOCK", "POS_DIRECT_NUM_PMP", "POS_RECALL_COUNT_GEILEN",
    "POS_WARL_ASID_WIDTH", "POS_WARL_MTVEC_MODES",
)
_H1_DISPOSITIONS = frozenset({"approved", "disputed", "incomplete"})
_V7_EXPERIMENT_PREFIX = "experiments/specchoice-v1.3.2"
_V7_SOURCE_IDENTITY_PATHS = {
    "adapter": f"{_V7_EXPERIMENT_PREFIX}/reports/h1/adapter-batch-pr2164-v6.json",
    "adapter_config": f"{_V7_EXPERIMENT_PREFIX}/config/measurement/pr2164-adapter-rules-v4.json",
    "adversarial": f"{_V7_EXPERIMENT_PREFIX}/reports/h1/adversarial-oracle-results-v7.json",
    "authority": f"{_V7_EXPERIMENT_PREFIX}/phase2/source-authority.json",
    "closure": f"{_V7_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v4.json",
    "formal_attempt": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/attempt.json",
    "formal_case_outcomes": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/case-outcomes.json",
    "formal_diagnostics": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/diagnostics.json",
    "formal_metrics": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/metrics.json",
    "formal_parsed_predictions": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/parsed-predictions.json",
    "formal_report": f"{_V7_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/report.json",
    "h1_schema": f"{_V7_EXPERIMENT_PREFIX}/config/measurement/h1-review-schema-v5.json",
    "question_contract": f"{_V7_EXPERIMENT_PREFIX}/config/measurement/h1-semantic-review-questions-v2.json",
}
_V7_SOURCE_IDENTITY_KEYS = frozenset(_V7_SOURCE_IDENTITY_PATHS)
_V7_PACKET_PATH = f"{_V7_EXPERIMENT_PREFIX}/reports/h1/h1-source-gold-review-v7/review-packet.json"
_V7_MARKDOWN_PATH = f"{_V7_EXPERIMENT_PREFIX}/reports/h1/h1-source-gold-review-v7/review-packet.md"
_V7_READINESS_PATH = f"{_V7_EXPERIMENT_PREFIX}/receipts/h1-review-readiness-v7.json"
_V7_DECISION_PATH = f"{_V7_EXPERIMENT_PREFIX}/reviews/h1-source-gold-decision-v6.json"
_CANONICAL_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_V7_EXPECTED_METRICS = {
    "disposition": {"denominator": 8, "numerator": 8},
    "evidence_integrity": {"denominator": 10, "numerator": 10},
    "identity": {"denominator": 6, "numerator": 6},
    "negative_controls": {"denominator": 3, "numerator": 3},
    "surfacing": {"denominator": 8, "numerator": 8},
}
_V7_FORMAL_ARTIFACT_ROLES = {
    "formal_case_outcomes": "case-outcomes.json",
    "formal_diagnostics": "diagnostics.json",
    "formal_metrics": "metrics.json",
    "formal_parsed_predictions": "parsed-predictions.json",
    "formal_report": "report.json",
}


def _v7_gate(runtime_closure: object, authority_path: Path) -> dict[str, object]:
    """Require the one published closure and descriptor-read active authority."""
    repository = _REPOSITORY.absolute()
    expected_authority = repository / _V7_SOURCE_IDENTITY_PATHS["authority"]
    if Path(os.path.abspath(authority_path)) != expected_authority:
        raise H1Error("ACTIVE_AUTHORITY_MISMATCH")
    try:
        closure = load_runtime_closure_v4(repository, runtime_closure)
        _, raw = read_authoritative_file(repository, _V7_SOURCE_IDENTITY_PATHS["authority"])
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, RuntimeClosureError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H1Error("RUNTIME_CLOSURE_V4_REQUIRED") from error
    if (
        canonical_json_bytes(value) != raw
        or sha256_bytes(raw) != "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae"
        or value.get("status") != "accepted_cutover_v13"
    ):
        raise H1Error("ACTIVE_AUTHORITY_MISMATCH")
    return {"authority": value, "closure": closure}


def _validate_v7_fresh_measurement_chain(
    *,
    runtime_closure: Mapping[str, object],
    authority_path: Path,
    records: Mapping[str, Mapping[str, object]],
    values: Mapping[str, object],
    raws: Mapping[str, bytes],
) -> None:
    """Replay all fresh measurement stages and bind their exact retained bytes."""
    repository = _REPOSITORY.absolute()
    try:
        adapter = validate_pr2164_accepted_v6_adapter_batch_v4(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        formal = validate_fresh_formal_measurement_v6(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        adversarial = validate_fresh_adversarial_result_v7(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
    except (AdapterError, AttemptError, FilesystemPolicyError, OSError, ValueError) as error:
        raise H1Error("H1_V7_FRESH_CHAIN_INVALID") from error

    adapter_value = values.get("adapter")
    formal_manifest = values.get("formal_attempt")
    formal_metrics = values.get("formal_metrics")
    adversarial_value = values.get("adversarial")
    if (
        adapter
        != {
            "adapter_batch_file_sha256": records["adapter"]["sha256"],
            "adapter_batch_sha256": (
                adapter_value.get("adapter_batch_sha256")
                if isinstance(adapter_value, Mapping)
                else None
            ),
            "fixture_count": 11,
            "raw_file_count": 29,
            "score_bearing_span_count": 10,
            "valid": True,
        }
        or not isinstance(formal_manifest, Mapping)
        or formal.get("attempt_sha256") != formal_manifest.get("attempt_sha256")
        or formal.get("case_count") != 11
        or formal.get("metrics") != _V7_EXPECTED_METRICS
        or formal_metrics != _V7_EXPECTED_METRICS
        or formal.get("role") != "formal"
        or formal.get("status") != "completed"
        or formal.get("valid") is not True
        or not isinstance(adversarial_value, Mapping)
        or adversarial.get("case_count") != 17
        or adversarial.get("report_sha256")
        != adversarial_value.get("report_sha256")
        or adversarial.get("status") != "diagnostic_only"
        or adversarial.get("valid") is not True
    ):
        raise H1Error("H1_V7_FRESH_CHAIN_INVALID")

    artifacts = formal_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise H1Error("H1_V7_FRESH_CHAIN_INVALID")
    for role, name in _V7_FORMAL_ARTIFACT_ROLES.items():
        if artifacts.get(name) != {
            "byte_length": records[role]["byte_length"],
            "sha256": records[role]["sha256"],
        }:
            raise H1Error("H1_V7_FRESH_CHAIN_INVALID")

    # Reject a pathname replacement during replay. The packet binds only the
    # first retained snapshot after every validator has proven the same bytes.
    try:
        current = read_authoritative_files(
            repository,
            [_V7_SOURCE_IDENTITY_PATHS[key] for key in sorted(_V7_SOURCE_IDENTITY_PATHS)],
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_V7_FRESH_CHAIN_INVALID") from error
    if any(
        current[_V7_SOURCE_IDENTITY_PATHS[role]][1] != raws[role]
        for role in sorted(_V7_SOURCE_IDENTITY_PATHS)
    ):
        raise H1Error("H1_V7_FRESH_CHAIN_INVALID")


def _v7_source_snapshot(
    *, runtime_closure: object, authority_path: Path
) -> tuple[dict[str, dict[str, object]], dict[str, object], dict[str, bytes]]:
    """Re-read every fixed source and return its actual path/length/hash record."""
    gated = _v7_gate(runtime_closure, authority_path)
    try:
        held = read_authoritative_files(
            _REPOSITORY.absolute(),
            [_V7_SOURCE_IDENTITY_PATHS[key] for key in sorted(_V7_SOURCE_IDENTITY_PATHS)],
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID") from error
    records: dict[str, dict[str, object]] = {}
    values: dict[str, object] = {}
    raws: dict[str, bytes] = {}
    for role in sorted(_V7_SOURCE_IDENTITY_PATHS):
        path = _V7_SOURCE_IDENTITY_PATHS[role]
        evidence, raw = held[path]
        if evidence.file_kind != "regular_file":
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID") from error
        if canonical_json_bytes(value) != raw:
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
        records[role] = {"path": path, "byte_length": len(raw), "sha256": sha256_bytes(raw)}
        values[role] = value
        raws[role] = raw
    if values["closure"] != gated["closure"] or values["authority"] != gated["authority"]:
        raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
    _validate_h1_review_schema_v5_value(values["h1_schema"])
    bundle = _REPOSITORY.absolute() / (
        f"{_V7_EXPERIMENT_PREFIX}/bundles/accepted/"
        "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
    )
    question_result = validate_h1_semantic_questions_v2(
        questions=_REPOSITORY.absolute() / _V7_SOURCE_IDENTITY_PATHS["question_contract"],
        bundle_root=bundle,
    )
    if question_result["question_ids"] != list(_V7_H1_QUESTION_IDS):
        raise H1Error("H1_V7_QUESTION_SET_INVALID")
    _validate_v7_fresh_measurement_chain(
        runtime_closure=gated["closure"],
        authority_path=authority_path,
        records=records,
        values=values,
        raws=raws,
    )
    return records, values, raws


def _require_v7_source_identity(
    supplied: object, actual: Mapping[str, Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    if not isinstance(supplied, Mapping) or set(supplied) != _V7_SOURCE_IDENTITY_KEYS:
        raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
    normalized: dict[str, dict[str, object]] = {}
    for role in sorted(_V7_SOURCE_IDENTITY_PATHS):
        value = supplied.get(role)
        if not isinstance(value, Mapping) or set(value) != {"path", "byte_length", "sha256"}:
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
        length = value.get("byte_length")
        try:
            digest = require_sha256(value.get("sha256"))
        except ValueError as error:
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID") from error
        record = {"path": value.get("path"), "byte_length": length, "sha256": digest}
        if (
            isinstance(length, bool)
            or not isinstance(length, int)
            or length < 0
            or digest == "0" * 64
            or record != actual[role]
        ):
            raise H1Error("H1_V7_SOURCE_IDENTITY_INVALID")
        normalized[role] = record
    return normalized


def _validate_h1_review_schema_v5_value(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "additional_properties", "aggregate_precedence", "decision", "markdown",
        "packet", "question_ids", "readiness", "schema_version", "source_identity",
    }:
        raise H1Error("H1_REVIEW_SCHEMA_V5_INVALID")
    source = value.get("source_identity")
    packet = value.get("packet")
    readiness = value.get("readiness")
    decision = value.get("decision")
    if (
        value.get("additional_properties") is not False
        or value.get("schema_version") != "h1-review-schema-v5"
        or value.get("aggregate_precedence") != ["incomplete", "disputed", "approved"]
        or value.get("question_ids") != list(_V7_H1_QUESTION_IDS)
        or source != {
            "additional_properties": False,
            "record_fields": ["byte_length", "path", "sha256"],
            "required_paths": _V7_SOURCE_IDENTITY_PATHS,
        }
        or not isinstance(packet, Mapping)
        or packet.get("schema_version") != "h1-review-packet-v7"
        or packet.get("required_fields") != [
            "fixture_reviews", "markdown", "packet_sha256", "questions", "schema_version", "source_identity"
        ]
        or packet.get("fixture_review_count") != 11
        or packet.get("question_count") != 7
        or packet.get("human_fields") is not False
        or not isinstance(readiness, Mapping)
        or readiness.get("schema_version") != "h1-review-readiness-v7"
        or readiness.get("required_fields") != [
            "markdown", "packet", "packet_sha256", "readiness_sha256", "schema_version", "source_identity", "status"
        ]
        or readiness.get("human_fields") is not False
        or not isinstance(decision, Mapping)
        or decision.get("schema_version") != "h1-source-gold-decision-v6"
        or decision.get("allowed_dispositions") != ["approved", "disputed", "incomplete"]
        or decision.get("fixture_review_count") != 11
        or decision.get("semantic_response_count") != 7
        or decision.get("timestamp_format") != "YYYY-MM-DDTHH:MM:SSZ"
    ):
        raise H1Error("H1_REVIEW_SCHEMA_V5_INVALID")


def validate_h1_review_schema_v5(*, schema: Path) -> dict[str, object]:
    """Validate the closed v5 schema without accepting an alternate path contract."""
    try:
        _, raw = read_authoritative_file(schema.parent, schema.name)
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H1Error("H1_REVIEW_SCHEMA_V5_INVALID") from error
    if canonical_json_bytes(value) != raw:
        raise H1Error("H1_REVIEW_SCHEMA_V5_INVALID")
    _validate_h1_review_schema_v5_value(value)
    return {"schema_sha256": sha256_bytes(raw), "valid": True}


def _expected_v7_fixture_reviews(
    cases: object, source_identity: Mapping[str, Mapping[str, object]]
) -> list[dict[str, object]]:
    if (
        not isinstance(cases, list)
        or [case.get("fixture_id") if isinstance(case, Mapping) else None for case in cases]
        != list(_V7_FIXTURE_IDS)
    ):
        raise H1Error("H1_V7_FIXTURE_REVIEW_SET_INVALID")
    binding = source_identity["formal_case_outcomes"]
    reviews: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping) or case.get("category") not in {"candidate", "negative", "positive"}:
            raise H1Error("H1_V7_FIXTURE_REVIEW_SET_INVALID")
        surfaced = case.get("actual_surfaced")
        if not isinstance(surfaced, bool):
            raise H1Error("H1_V7_FIXTURE_REVIEW_SET_INVALID")
        disposition = case.get("actual_status") if surfaced else "not_surfaced"
        if not isinstance(disposition, str) or not disposition:
            raise H1Error("H1_V7_FIXTURE_REVIEW_SET_INVALID")
        outcome = dict(case)
        reviews.append({
            "evidence_binding": {
                "byte_length": binding["byte_length"],
                "index": index,
                "path": binding["path"],
                "sha256": binding["sha256"],
            },
            "expected_disposition": disposition,
            "expected_surfaced": surfaced,
            "fixture_class": case["category"],
            "fixture_id": case["fixture_id"],
            "formal_outcome_sha256": sha256_bytes(canonical_json_bytes(outcome)),
        })
    return reviews


def _v7_review_core(
    *, questions: object, fixture_reviews: object, source_identity: object,
    runtime_closure: object, authority_path: Path,
) -> dict[str, object]:
    actual, values, _ = _v7_source_snapshot(
        runtime_closure=runtime_closure, authority_path=authority_path
    )
    normalized_identity = _require_v7_source_identity(source_identity, actual)
    contract = values["question_contract"]
    expected_questions = contract.get("questions") if isinstance(contract, Mapping) else None
    if questions != expected_questions:
        raise H1Error("H1_V7_QUESTION_SEMANTICS_INVALID")
    expected_reviews = _expected_v7_fixture_reviews(
        values["formal_case_outcomes"], normalized_identity
    )
    if fixture_reviews != expected_reviews:
        raise H1Error("H1_V7_FIXTURE_REVIEW_SET_INVALID")
    return {
        "fixture_reviews": expected_reviews,
        "questions": expected_questions,
        "schema_version": "h1-review-core-v7",
        "source_identity": normalized_identity,
    }


def _render_h1_review_core_v7(core: Mapping[str, object]) -> bytes:
    return (
        "# H1 Source-Gold Review Checkpoint v7\n\n"
        "This decision-free checkpoint is a deterministic projection of the canonical review core.\n\n"
        "```json\n"
        + canonical_json_bytes(dict(core)).decode("utf-8").rstrip("\n")
        + "\n```\n"
    ).encode("utf-8")


def build_h1_review_packet_v7(*, questions: object, fixture_reviews: object, source_identity: object, markdown_sha256: str | None = None, runtime_closure: object, authority_path: Path) -> dict[str, object]:
    """Build a decision-free packet with every semantic question fully bound."""
    core = _v7_review_core(
        questions=questions, fixture_reviews=fixture_reviews,
        source_identity=source_identity, runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    markdown = _render_h1_review_core_v7(core)
    actual_markdown_sha256 = sha256_bytes(markdown)
    if markdown_sha256 is not None and markdown_sha256 != actual_markdown_sha256:
        raise H1Error("H1_V7_MARKDOWN_BINDING_INVALID")
    payload = {
        "fixture_reviews": core["fixture_reviews"],
        "markdown": {
            "byte_length": len(markdown),
            "path": _V7_MARKDOWN_PATH,
            "sha256": actual_markdown_sha256,
        },
        "questions": core["questions"],
        "schema_version": "h1-review-packet-v7",
        "source_identity": core["source_identity"],
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h1_review_checkpoint_v7(packet: object) -> bytes:
    """Render the packet's decision-free core without introducing a hash cycle."""
    if not isinstance(packet, Mapping) or set(packet) != {
        "fixture_reviews", "markdown", "packet_sha256", "questions", "schema_version", "source_identity"
    }:
        raise H1Error("H1_V7_PACKET_INVALID")
    core = {
        "fixture_reviews": packet["fixture_reviews"],
        "questions": packet["questions"],
        "schema_version": "h1-review-core-v7",
        "source_identity": packet["source_identity"],
    }
    raw = _render_h1_review_core_v7(core)
    if packet.get("markdown") != {
        "byte_length": len(raw), "path": _V7_MARKDOWN_PATH, "sha256": sha256_bytes(raw)
    }:
        raise H1Error("H1_V7_MARKDOWN_BINDING_INVALID")
    return raw


def _expected_fixed_h1_review_packet_v7(
    *, runtime_closure: object, authority_path: Path
) -> tuple[dict[str, object], bytes, bytes]:
    """Rebuild the one fixed decision-free packet and both published bytes."""
    source_identity, values, _ = _v7_source_snapshot(
        runtime_closure=runtime_closure, authority_path=authority_path
    )
    question_contract = values["question_contract"]
    questions = (
        question_contract.get("questions")
        if isinstance(question_contract, Mapping)
        else None
    )
    packet = build_h1_review_packet_v7(
        questions=questions,
        fixture_reviews=_expected_v7_fixture_reviews(
            values["formal_case_outcomes"], source_identity
        ),
        source_identity=source_identity,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    packet_raw = canonical_json_bytes(packet)
    markdown_raw = render_h1_review_checkpoint_v7(packet)
    return packet, packet_raw, markdown_raw


def _preflight_v7_packet_targets(
    *, packet_raw: bytes, markdown_raw: bytes
) -> str:
    """Require both fixed packet leaves to be absent or byte-identical."""
    repository = _REPOSITORY.absolute()
    expected = {
        _V7_PACKET_PATH: packet_raw,
        _V7_MARKDOWN_PATH: markdown_raw,
    }
    states: list[str] = []
    for path, raw in expected.items():
        try:
            evidence, existing = read_authoritative_file(repository, path)
        except FilesystemPolicyError as error:
            if str(error) != "AUTHORITATIVE_FILE_MISSING":
                raise H1Error("H1_V7_PACKET_OUTPUT_INVALID") from error
            states.append("absent")
            continue
        except OSError as error:
            raise H1Error("H1_V7_PACKET_OUTPUT_INVALID") from error
        if evidence.file_kind != "regular_file" or existing != raw:
            raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
        states.append("identical")
    if states == ["absent", "absent"]:
        target_directory = (repository / _V7_PACKET_PATH).parent
        if target_directory.exists() or target_directory.is_symlink():
            raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
        return "written"
    if states == ["identical", "identical"]:
        _validate_v7_packet_directory_shape()
        return "resumed"
    raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")


def _validate_v7_packet_directory_shape() -> None:
    target = (_REPOSITORY.absolute() / _V7_PACKET_PATH).parent
    if target.is_symlink() or not target.is_dir():
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
    try:
        children = list(target.iterdir())
    except OSError as error:
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID") from error
    if {child.name for child in children} != {
        Path(_V7_PACKET_PATH).name,
        Path(_V7_MARKDOWN_PATH).name,
    } or len(children) != 2:
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")


def _validate_published_v7_packet_bytes(
    *, packet: Mapping[str, object], packet_raw: bytes, markdown_raw: bytes
) -> None:
    """Postflight the fixed packet pair through one held authority root."""
    if packet_raw != canonical_json_bytes(dict(packet)):
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
    _validate_v7_packet_directory_shape()
    try:
        held = read_authoritative_files(
            _REPOSITORY.absolute(), [_V7_PACKET_PATH, _V7_MARKDOWN_PATH]
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID") from error
    if (
        held[_V7_PACKET_PATH][1] != packet_raw
        or held[_V7_MARKDOWN_PATH][1] != markdown_raw
        or render_h1_review_checkpoint_v7(packet) != markdown_raw
    ):
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")


def write_h1_review_packet_v7(
    *, runtime_closure: object, authority_path: Path
) -> dict[str, object]:
    """Publish or exactly resume the fixed decision-free packet pair."""
    packet, packet_raw, markdown_raw = _expected_fixed_h1_review_packet_v7(
        runtime_closure=runtime_closure, authority_path=authority_path
    )
    status = _preflight_v7_packet_targets(
        packet_raw=packet_raw, markdown_raw=markdown_raw
    )

    # A first build is never a write token. Replay the complete closure,
    # authority, adapter, formal, and adversarial chain immediately before the
    # descriptor-rooted multi-file publication primitive is entered.
    fresh_packet, fresh_packet_raw, fresh_markdown_raw = (
        _expected_fixed_h1_review_packet_v7(
            runtime_closure=runtime_closure, authority_path=authority_path
        )
    )
    if (
        fresh_packet != packet
        or fresh_packet_raw != packet_raw
        or fresh_markdown_raw != markdown_raw
    ):
        raise H1Error("H1_V7_PACKET_PREWRITE_DRIFT")
    if status == "written":
        repository = _REPOSITORY.absolute()
        target = (repository / _V7_PACKET_PATH).parent
        parent = target.parent
        if not parent.is_dir() or parent.is_symlink():
            raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
        temporary = Path(
            tempfile.mkdtemp(prefix=".h1-source-gold-review-v7.staging-", dir=parent)
        )
        try:
            _write_exact(temporary / Path(_V7_PACKET_PATH).name, fresh_packet_raw)
            _write_exact(temporary / Path(_V7_MARKDOWN_PATH).name, fresh_markdown_raw)
            _sync_directory(temporary)

            # Staging may take long enough for the accepted authority or one of
            # the retained fresh-chain leaves to change.  Rebuild the complete
            # chain only after staging is durable and immediately before the
            # no-replace directory publication.
            publish_packet, publish_packet_raw, publish_markdown_raw = (
                _expected_fixed_h1_review_packet_v7(
                    runtime_closure=runtime_closure,
                    authority_path=authority_path,
                )
            )
            if (
                publish_packet != fresh_packet
                or publish_packet_raw != fresh_packet_raw
                or publish_markdown_raw != fresh_markdown_raw
            ):
                raise H1Error("H1_V7_PACKET_PREWRITE_DRIFT")
            _publish_directory_no_replace(
                temporary, target, "H1_V7_PACKET_OUTPUT_RACE"
            )
            _sync_directory(parent)
        except (BundleError, OSError) as error:
            raise H1Error("H1_V7_PACKET_OUTPUT_INVALID") from error
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    _validate_published_v7_packet_bytes(
        packet=fresh_packet,
        packet_raw=fresh_packet_raw,
        markdown_raw=fresh_markdown_raw,
    )
    postflight_packet, postflight_packet_raw, postflight_markdown_raw = (
        _expected_fixed_h1_review_packet_v7(
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
    )
    if (
        postflight_packet != fresh_packet
        or postflight_packet_raw != fresh_packet_raw
        or postflight_markdown_raw != fresh_markdown_raw
    ):
        raise H1Error("H1_V7_PACKET_OUTPUT_INVALID")
    return {
        "markdown_sha256": fresh_packet["markdown"]["sha256"],
        "packet_sha256": fresh_packet["packet_sha256"],
        "status": status,
        "valid": True,
    }


def build_h1_review_readiness_v7(*, packet: object, runtime_closure: object, authority_path: Path) -> dict[str, object]:
    """Produce decision-free readiness; human response fields are never accepted."""
    if not isinstance(packet, Mapping) or packet.get("schema_version") != "h1-review-packet-v7" or "responses" in packet:
        raise H1Error("H1_V7_PACKET_INVALID")
    expected_packet = build_h1_review_packet_v7(
        questions=packet.get("questions"), fixture_reviews=packet.get("fixture_reviews"),
        source_identity=packet.get("source_identity"), runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    if dict(packet) != expected_packet:
        raise H1Error("H1_V7_PACKET_INVALID")
    packet_raw = canonical_json_bytes(expected_packet)
    markdown_raw = render_h1_review_checkpoint_v7(expected_packet)
    payload = {
        "markdown": {"byte_length": len(markdown_raw), "path": _V7_MARKDOWN_PATH, "sha256": sha256_bytes(markdown_raw)},
        "packet": {"byte_length": len(packet_raw), "path": _V7_PACKET_PATH, "sha256": sha256_bytes(packet_raw)},
        "packet_sha256": expected_packet["packet_sha256"],
        "schema_version": "h1-review-readiness-v7",
        "source_identity": expected_packet["source_identity"],
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def _expected_fixed_h1_review_readiness_v7(
    *, runtime_closure: object, authority_path: Path
) -> tuple[dict[str, object], dict[str, object], bytes]:
    """Rebuild readiness only after the fixed packet pair is retained exactly."""
    packet, packet_raw, markdown_raw = _expected_fixed_h1_review_packet_v7(
        runtime_closure=runtime_closure, authority_path=authority_path
    )
    _validate_published_v7_packet_bytes(
        packet=packet, packet_raw=packet_raw, markdown_raw=markdown_raw
    )
    readiness = build_h1_review_readiness_v7(
        packet=packet,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    return packet, readiness, canonical_json_bytes(readiness)


def write_h1_review_readiness_v7(
    *, runtime_closure: object, authority_path: Path
) -> dict[str, object]:
    """Publish or exactly resume the one fixed decision-free readiness receipt."""
    packet, readiness, raw = _expected_fixed_h1_review_readiness_v7(
        runtime_closure=runtime_closure, authority_path=authority_path
    )
    output = _REPOSITORY.absolute() / _V7_READINESS_PATH
    preflight_status = _preflight_h1_exact_resume(
        output, raw, "H1_V7_READINESS_OUTPUT_INVALID"
    )

    # Rebuild the complete fixed chain after construction and immediately
    # after the target preflight, immediately before entering the no-replace
    # write primitive. No human value is an argument to this writer or
    # introduced into its canonical projection.
    fresh_packet, fresh_readiness, fresh_raw = (
        _expected_fixed_h1_review_readiness_v7(
            runtime_closure=runtime_closure, authority_path=authority_path
        )
    )
    if (
        fresh_packet != packet
        or fresh_readiness != readiness
        or fresh_raw != raw
    ):
        raise H1Error("H1_V7_READINESS_PREWRITE_DRIFT")
    status = _write_h1_exact_resume(
        output,
        fresh_raw,
        "H1_V7_READINESS_OUTPUT_INVALID",
        preflight_status=preflight_status,
    )
    postflight = validate_h1_review_readiness_v7(
        readiness=fresh_readiness,
        packet=fresh_packet,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    if canonical_json_bytes(postflight) != fresh_raw:
        raise H1Error("H1_V7_READINESS_OUTPUT_INVALID")
    return {
        "packet_sha256": fresh_packet["packet_sha256"],
        "readiness_sha256": fresh_readiness["readiness_sha256"],
        "status": status,
        "valid": True,
    }


def _validate_published_v7_review_bytes(
    *, packet: Mapping[str, object], readiness: Mapping[str, object]
) -> None:
    try:
        held = read_authoritative_files(
            _REPOSITORY.absolute(), [_V7_PACKET_PATH, _V7_MARKDOWN_PATH, _V7_READINESS_PATH]
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_V7_PUBLISHED_REVIEW_INVALID") from error
    expected = {
        _V7_PACKET_PATH: canonical_json_bytes(dict(packet)),
        _V7_MARKDOWN_PATH: render_h1_review_checkpoint_v7(packet),
        _V7_READINESS_PATH: canonical_json_bytes(dict(readiness)),
    }
    if any(held[path][1] != raw for path, raw in expected.items()):
        raise H1Error("H1_V7_PUBLISHED_REVIEW_INVALID")


def validate_h1_review_readiness_v7(
    *, readiness: object, packet: object, runtime_closure: object, authority_path: Path
) -> dict[str, object]:
    """Read-only validation of the three published packet/Markdown/readiness files."""
    if not isinstance(readiness, Mapping) or not isinstance(packet, Mapping):
        raise H1Error("H1_V7_READINESS_INVALID")
    expected = build_h1_review_readiness_v7(
        packet=packet, runtime_closure=runtime_closure, authority_path=authority_path
    )
    if dict(readiness) != expected:
        raise H1Error("H1_V7_READINESS_MISMATCH")
    _validate_published_v7_review_bytes(packet=packet, readiness=readiness)
    return dict(readiness)


def validate_h1_source_gold_decision_v6(*, decision: object, packet: object, readiness: object, runtime_closure: object, authority_path: Path) -> dict[str, object]:
    """Validate the closed three-state human judgment without writing anything."""
    if not isinstance(packet, Mapping) or not isinstance(readiness, Mapping) or not isinstance(decision, Mapping):
        raise H1Error("H1_V6_DECISION_INVALID")
    expected_readiness = build_h1_review_readiness_v7(
        packet=packet, runtime_closure=runtime_closure, authority_path=authority_path
    )
    if dict(readiness) != expected_readiness:
        raise H1Error("H1_V6_PACKET_READINESS_MISMATCH")
    _validate_published_v7_review_bytes(packet=packet, readiness=readiness)
    required = {
        "aggregate_disposition", "aggregate_rationale", "attestation", "decision_sha256", "fixture_reviews",
        "packet_sha256", "readiness_sha256", "reviewer", "schema_version", "semantic_responses", "signature", "timestamp_utc",
    }
    if set(decision) != required or decision.get("schema_version") != "h1-source-gold-decision-v6":
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get("readiness_sha256") != readiness.get("readiness_sha256"):
        raise H1Error("H1_V6_PACKET_READINESS_MISMATCH")
    decision_payload = {key: decision[key] for key in sorted(required - {"decision_sha256"})}
    if decision.get("decision_sha256") != sha256_bytes(canonical_json_bytes(decision_payload)):
        raise H1Error("H1_V6_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer", "signature", "timestamp_utc"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise H1Error("H1_V6_DECISION_INCOMPLETE")
    timestamp = decision["timestamp_utc"]
    try:
        if _CANONICAL_UTC_RE.fullmatch(timestamp) is None:
            raise ValueError("noncanonical UTC timestamp")
        parsed_timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise H1Error("H1_V6_DECISION_INCOMPLETE") from error
    if parsed_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") != timestamp:
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    items = decision.get("semantic_responses")
    aggregate = decision.get("aggregate_disposition")
    if not isinstance(items, list) or len(items) != 7 or aggregate not in _H1_DISPOSITIONS:
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    if [item.get("id") if isinstance(item, dict) else None for item in items] != list(_V7_H1_QUESTION_IDS):
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    if any(not isinstance(item, dict) or set(item) != {"id", "disposition", "rationale"} or item.get("disposition") not in _H1_DISPOSITIONS or not isinstance(item.get("rationale"), str) or not item["rationale"].strip() for item in items):
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    fixture_items = decision.get("fixture_reviews")
    packet_fixtures = packet.get("fixture_reviews")
    if not isinstance(fixture_items, list) or not isinstance(packet_fixtures, list) or len(fixture_items) != 11:
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    expected_ids = [item["fixture_id"] for item in packet_fixtures]
    if [item.get("fixture_id") if isinstance(item, dict) else None for item in fixture_items] != expected_ids:
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    if any(not isinstance(item, dict) or set(item) != {"fixture_id", "disposition", "rationale"} or item.get("disposition") not in _H1_DISPOSITIONS or not isinstance(item.get("rationale"), str) or not item["rationale"].strip() for item in fixture_items):
        raise H1Error("H1_V6_DECISION_INCOMPLETE")
    all_dispositions = [item["disposition"] for item in items + fixture_items]
    expected_aggregate = (
        "incomplete" if "incomplete" in all_dispositions
        else "disputed" if "disputed" in all_dispositions
        else "approved"
    )
    if aggregate != expected_aggregate:
        raise H1Error("H1_V6_AGGREGATE_CONFLICT")
    return dict(decision)


def _preflight_h1_exact_resume(output: Path, raw: bytes, code: str) -> str:
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise H1Error(code)
    try:
        _, existing = read_authoritative_file(output.parent, output.name)
    except FilesystemPolicyError as error:
        if str(error) != "AUTHORITATIVE_FILE_MISSING":
            raise H1Error(code) from error
        return "written"
    except OSError as error:
        raise H1Error(code) from error
    if existing != raw:
        raise H1Error(code)
    return "resumed"


def _write_h1_exact_resume(
    output: Path, raw: bytes, code: str, *, preflight_status: str
) -> str:
    """Enter only the no-replace primitive after the caller's final gate."""
    if preflight_status not in {"written", "resumed"}:
        raise H1Error(code)
    if preflight_status == "resumed":
        return preflight_status
    try:
        write_new_descriptor_file(output.parent, output.name, raw)
    except FilesystemPolicyError as error:
        raise H1Error(code) from error
    return "written"


def _validate_h1_exact_output(output: Path, raw: bytes, code: str) -> None:
    try:
        evidence, retained = read_authoritative_file(output.parent, output.name)
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error(code) from error
    if evidence.file_kind != "regular_file" or retained != raw:
        raise H1Error(code)


def write_h1_source_gold_decision_v6(
    *, output: Path, decision: object, packet: object, readiness: object,
    runtime_closure: object, authority_path: Path, preflight: bool = False,
) -> dict[str, object]:
    """Validate a complete human decision before an immutable exact-resume write."""
    fixed_output = (_REPOSITORY.absolute() / _V7_DECISION_PATH).absolute()
    if output.absolute() != fixed_output:
        raise H1Error("H1_V6_DECISION_OUTPUT_INVALID")
    validated = validate_h1_source_gold_decision_v6(
        decision=decision, packet=packet, readiness=readiness,
        runtime_closure=runtime_closure, authority_path=authority_path,
    )
    raw = canonical_json_bytes(validated)
    preflight_status = _preflight_h1_exact_resume(
        output, raw, "H1_V6_DECISION_OUTPUT_INVALID"
    )
    if preflight:
        status = "preflight_valid"
    else:
        # The first validation is not a durable authorization token. Repeat the
        # complete packet/readiness/fresh-chain gate at the write boundary so a
        # changed closure or active authority cannot reach the primitive.
        fresh = validate_h1_source_gold_decision_v6(
            decision=decision,
            packet=packet,
            readiness=readiness,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        fresh_raw = canonical_json_bytes(fresh)
        if fresh != validated or fresh_raw != raw:
            raise H1Error("H1_V6_DECISION_PREWRITE_DRIFT")
        status = _write_h1_exact_resume(
            output,
            fresh_raw,
            "H1_V6_DECISION_OUTPUT_INVALID",
            preflight_status=preflight_status,
        )
        _validate_h1_exact_output(
            output, fresh_raw, "H1_V6_DECISION_OUTPUT_INVALID"
        )
        postflight = validate_h1_source_gold_decision_v6(
            decision=decision,
            packet=packet,
            readiness=readiness,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        if canonical_json_bytes(postflight) != fresh_raw:
            raise H1Error("H1_V6_DECISION_OUTPUT_INVALID")
    return {
        "aggregate_disposition": validated["aggregate_disposition"],
        "decision_sha256": validated["decision_sha256"],
        "status": status,
    }


def validate_approved_h1_terminal_v6(*, decision: object, packet: object, readiness: object, runtime_closure: object, authority_path: Path) -> dict[str, object]:
    validated = validate_h1_source_gold_decision_v6(decision=decision, packet=packet, readiness=readiness, runtime_closure=runtime_closure, authority_path=authority_path)
    if validated.get("aggregate_disposition") != "approved":
        raise H1Error("H1_V6_TERMINAL_APPROVAL_REQUIRED")
    return validated


_V5_H1_QUESTION_IDS = (
    "ts03_adjacency", "ts03_empty_null_single_element", "ts03_equal_element_stable_order",
    "ts04_unclassified_manual_review", "ts05_adjacency", "ts05_empty_null_single_element",
    "ts05_equal_element_stable_order",
)


def validate_v5_h1_question_contract(value: object) -> None:
    """Require the fixed seven human-owned semantic questions before packet rendering."""
    if not isinstance(value, dict) or value.get("schema_version") != "h1-semantic-review-questions-v1" or value.get("question_ids") != list(_V5_H1_QUESTION_IDS):
        raise H1Error("V5_H1_QUESTION_CONTRACT_INVALID")


_ROOT = Path(__file__).parents[2]
_REPOSITORY = _ROOT.parents[1]
_SCHEMA = _ROOT / "config/measurement/canonical-adjudication-schema-v1.json"
_H1_V2_SCHEMA = _ROOT / "config/measurement/h1-review-schema-v2.json"
_H1_V3_PACKET = _ROOT / "reports/h1/h1-source-gold-review-v3/h1-source-gold-review-v3.json"
_H1_V3_MARKDOWN = _ROOT / "reports/h1/h1-source-gold-review-v3/h1-source-gold-review-v3.md"
_H1_V3_READINESS = _ROOT / "receipts/h1-review-readiness-v3.json"
_H1_V2_FORMAL = _ROOT / "runs/measurement-attempts/formal-golden-pr2164-v2/attempt.json"
_H1_V3_ADVERSARIAL = _ROOT / "reports/h1/adversarial-oracle-results-v3.json"
_ACTIVE_AUTHORITY = _ROOT / "phase2/source-authority.json"
_REVOCATION_V2 = _ROOT / "receipts/fixture-closure-revocation-v2.json"
_ROUTE_SUPERSESSION = _ROOT / "receipts/h1-review-route-supersession-v1.json"
_SUCCESSOR_ONTOLOGY_OPTIONS = _ROOT / "config/measurement/h1-ontology-policy-options-v1.json"
_SUCCESSOR_ONTOLOGY_DECISION = _ROOT / "reviews/h1-source-gold-ontology-decision-v1.json"
_SUCCESSOR_EXECUTABLE_CLOSURE = _ROOT / "receipts/runtime-executable-closure-v3.json"
_SUCCESSOR_HISTORICAL_AUTHORITY = _ROOT / "phase2/source-authority-v13-historical.json"
_H1_V3_BUNDLE = _ROOT / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
_H1_V1_RULES = _ROOT / "config/measurement/pr2164-adapter-rules-v1.json"
_H1_V2_PREDICTIONS = _ROOT / "fixtures/measurement/golden-predictions-v2.json"
_H1_V2_ORACLE = _ROOT / "fixtures/measurement/adversarial/required-diagnostics-v2.json"
_H1_V3_REPLAY = _ROOT / "receipts/fixture-closure-offline-replay-v3.json"
_H1_V2_SUMMARY = _REPOSITORY / resolve_historical_path(
    _REPOSITORY,
    "." + "planning/phases/02-deterministic-measurement-spine/02-16-SUMMARY.md",
)

_ROUTE_BINDING_PATHS = {
    # The route refusal is immutable history.  After accepted-v6 cutover its
    # authority input is the preserved v13 historical file, not the new head.
    "active_authority_sha256": _SUCCESSOR_HISTORICAL_AUTHORITY,
    "adversarial_v3_sha256": _H1_V3_ADVERSARIAL,
    "formal_v2_sha256": _H1_V2_FORMAL,
    "h1_review_schema_v2_sha256": _H1_V2_SCHEMA,
    "packet_v3_json_sha256": _H1_V3_PACKET,
    "packet_v3_markdown_sha256": _H1_V3_MARKDOWN,
    "readiness_v3_sha256": _H1_V3_READINESS,
    "revocation_v2_sha256": _REVOCATION_V2,
}

_ONTOLOGY_OPTIONS = {
    "cache_choices": [
        {
            "consequences": {
                "management_prefetch_identity": "CACHE_BLOCK_SIZE",
                "scope": "unified",
                "zero_block_identity": "CACHE_BLOCK_SIZE",
            },
            "id": "unified_cache_block_identity",
        },
        {
            "consequences": {
                "management_prefetch_identity": "CACHE_BLOCK_SIZE.management_prefetch",
                "scope": "scoped",
                "zero_block_identity": "CACHE_BLOCK_SIZE.zero_block",
            },
            "id": "scoped_cache_block_identities",
        },
    ],
    "external_publication_authorized": False,
    "local_only": True,
    "pbmte_choices": [
        {
            "consequences": {
                "discovery_surfaced": False,
                "exclusion_reason": "excluded_from_discovery",
                "final_included": False,
                "fixture_class": "absent",
                "parameter_identity": None,
            },
            "id": "excluded_from_discovery",
        },
        {
            "consequences": {
                "discovery_surfaced": True,
                "exclusion_reason": "surfaced_classified_out",
                "final_included": False,
                "fixture_class": "candidate",
                "parameter_identity": None,
            },
            "id": "surfaced_classified_out",
        },
        {
            "consequences": {
                "discovery_surfaced": True,
                "exclusion_reason": None,
                "final_included": True,
                "fixture_class": "positive",
                "parameter_identity": "PBMTE",
            },
            "id": "included_capability_parameter",
        },
    ],
    "schema_version": "h1-ontology-policy-options-v1",
}


def _relative(path: Path, code: str) -> str:
    try:
        return path.absolute().relative_to(_ROOT.absolute()).as_posix()
    except ValueError as error:
        raise H1Error(code) from error


def _read_canonical_value(path: Path, code: str) -> tuple[Any, bytes]:
    try:
        evidence, raw = read_authoritative_file(_ROOT, _relative(path, code))
        if evidence.file_kind != "regular_file":
            raise H1Error(code)
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H1Error(code) from error
    if canonical_json_bytes(value) != raw:
        raise H1Error(code)
    return value, raw


def _read_canonical(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    value, raw = _read_canonical_value(path, code)
    if not isinstance(value, dict):
        raise H1Error(code)
    return value, raw


def _require_digest(value: object, code: str) -> str:
    try:
        return require_sha256(value)
    except ValueError as error:
        raise H1Error(code) from error


def _is_canonical_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 20:
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def _packet_projection(packet: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in packet.items() if key != "packet_sha256"}


def _batch(
    *, authority: Path, bundle: Path, rules: Path, pending_authority: Path | None,
    transition: Path | None, revocation: Path | None,
) -> object:
    batch = build_pr2164_adapter_batch(
        authority_path=authority,
        bundle_root=bundle,
        rules_path=rules,
        pending_authority_path=pending_authority,
        transition_path=transition,
        revocation_path=revocation,
    )
    if not batch.valid:
        raise H1Error("H1_ADAPTER_NOT_ELIGIBLE")
    return batch


def _review_items(batch: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in getattr(batch, "records", ()):
        category = getattr(record, "category")
        items.append({
            "adapter_lineage": {
                "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256"),
                "adapter_version": getattr(record, "adapter_version"),
                "rule_sha256": getattr(record, "rule_sha256"),
            },
            "candidate_surfaced_then_classify_out": category == "candidate",
            "category": category,
            "evidence": [raw.as_dict() for raw in getattr(record, "raw_files", ())],
            "expect_extract": getattr(record, "expect_extract"),
            "expected_parameter_count": getattr(record, "expected_parameter_count"),
            "expected_parameter_names": list(getattr(record, "expected_parameter_names")),
            "fixture_id": getattr(record, "fixture_id"),
            "signature_slot": {"reviewer": None, "signature": None},
        })
    if len(items) != 11 or [item["fixture_id"] for item in items] != sorted(item["fixture_id"] for item in items):
        raise H1Error("H1_FIXTURE_SET_INVALID")
    return items


def _expected_bindings(
    *, formal_attempt: Path, adversarial_report: Path, h1_schema: Path, authority: Path, bundle: Path,
    rules: Path, predictions: Path, oracle: Path, pending_authority: Path | None, transition: Path | None,
    revocation: Path | None, batch: object,
) -> dict[str, Any]:
    from .cli import validate_adversarial_report

    try:
        _, schema_raw = _read_canonical(_SCHEMA, "H1_BINDINGS_INVALID")
        formal_summary = validate_measurement_attempt(
            attempt_root=formal_attempt, adapter_batch=batch, schema_raw=schema_raw
        )
        formal, _ = _read_canonical(formal_attempt / "attempt.json", "H1_FORMAL_ATTEMPT_INVALID")
        adversarial = validate_adversarial_report(
            report_path=adversarial_report,
            formal_attempt=formal_attempt,
            authority=authority,
            bundle=bundle,
            rules=rules,
            schema=_SCHEMA,
            predictions=predictions,
            oracle=oracle,
            pending_authority=pending_authority,
            transition=transition,
            revocation=revocation,
        )
    except (AttemptError, ValueError, OSError) as error:
        raise H1Error("H1_EVIDENCE_INVALID") from error
    if (formal_summary.get("role"), formal_summary.get("status")) != ("formal", "completed") or (
        formal.get("role"), formal.get("status")
    ) != ("formal", "completed"):
        raise H1Error("H1_FORMAL_ATTEMPT_NOT_CLEAN")
    bindings = formal.get("bindings")
    artifacts = formal.get("artifacts")
    if not isinstance(bindings, dict) or not isinstance(artifacts, dict):
        raise H1Error("H1_FORMAL_ATTEMPT_INVALID")
    diagnostics = formal_attempt / "diagnostics.json"
    diagnostics_value, diagnostics_raw = _read_canonical_value(diagnostics, "H1_FORMAL_DIAGNOSTICS_INVALID")
    if diagnostics_value != []:
        raise H1Error("H1_FORMAL_DIAGNOSTICS_NOT_CLEAN")
    diagnostic_entry = artifacts.get("diagnostics.json")
    if not isinstance(diagnostic_entry, dict) or diagnostic_entry != {
        "byte_length": len(diagnostics_raw), "sha256": sha256_bytes(diagnostics_raw)
    }:
        raise H1Error("H1_FORMAL_DIAGNOSTICS_INVALID")
    adversarial_bindings = adversarial.get("bindings")
    expected_source = getattr(batch, "source_identity")
    try:
        _, h1_schema_raw = read_authoritative_file(h1_schema.parent, h1_schema.name)
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_BINDINGS_INVALID") from error
    schema_sha256 = sha256_bytes(schema_raw)
    h1_schema_sha256 = sha256_bytes(h1_schema_raw)
    if (
        not isinstance(adversarial_bindings, dict)
        or bindings.get("adapter_batch_sha256") != getattr(batch, "adapter_batch_sha256")
        or bindings.get("adapter_version") != getattr(batch, "adapter_version")
        or bindings.get("rule_sha256") != getattr(batch, "rule_sha256")
        or bindings.get("schema_sha256") != schema_sha256
        or bindings.get("source_identity") != expected_source
        or adversarial_bindings.get("formal_attempt_sha256") != formal.get("attempt_sha256")
        or adversarial_bindings.get("adapter_batch_sha256") != getattr(batch, "adapter_batch_sha256")
        or adversarial_bindings.get("rule_sha256") != getattr(batch, "rule_sha256")
        or adversarial_bindings.get("schema_sha256") != schema_sha256
        or adversarial_bindings.get("golden_predictions_sha256") != bindings.get("raw_predictions_sha256")
        or adversarial_bindings.get("source_identity") != expected_source
    ):
        raise H1Error("H1_BINDINGS_INVALID")
    _, adversarial_raw = _read_canonical(adversarial_report, "H1_ADVERSARIAL_REPORT_INVALID")
    return {
        "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256"),
        "adapter_version": getattr(batch, "adapter_version"),
        "adversarial_report_sha256": sha256_bytes(adversarial_raw),
        "formal_attempt_sha256": formal.get("attempt_sha256"),
        "formal_diagnostics_sha256": sha256_bytes(diagnostics_raw),
        "golden_predictions_sha256": bindings.get("raw_predictions_sha256"),
        "h1_review_schema_sha256": h1_schema_sha256,
        "rule_sha256": getattr(batch, "rule_sha256"),
        "schema_sha256": schema_sha256,
        "source_identity": expected_source,
    }


def _validate_packet_value(packet: object, *, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(packet, dict) or set(packet) != {
        "bindings", "external_publication_authorized", "fixture_reviews", "packet_sha256", "schema_version"
    }:
        raise H1Error("H1_PACKET_INVALID")
    if packet.get("schema_version") != "h1-source-gold-review-v2" or packet.get("external_publication_authorized") is not False:
        raise H1Error("H1_PACKET_INVALID")
    if packet.get("packet_sha256") != sha256_bytes(canonical_json_bytes(_packet_projection(packet))):
        raise H1Error("H1_PACKET_HASH_INVALID")
    bindings = packet.get("bindings")
    if not isinstance(bindings, dict) or expected is not None and bindings != expected:
        raise H1Error("H1_BINDINGS_INVALID")
    reviews = packet.get("fixture_reviews")
    if not isinstance(reviews, list) or len(reviews) != 11:
        raise H1Error("H1_FIXTURE_SET_INVALID")
    identifiers = [item.get("fixture_id") for item in reviews if isinstance(item, dict)]
    if len(identifiers) != 11 or identifiers != sorted(identifiers) or len(set(identifiers)) != 11:
        raise H1Error("H1_FIXTURE_SET_INVALID")
    for item in reviews:
        if not isinstance(item, dict) or set(item) != {
            "adapter_lineage", "candidate_surfaced_then_classify_out", "category", "evidence", "expect_extract",
            "expected_parameter_count", "expected_parameter_names", "fixture_id", "signature_slot"
        } or item.get("signature_slot") != {"reviewer": None, "signature": None}:
            raise H1Error("H1_REVIEW_ITEM_INVALID")
    return packet


def render_h1_markdown(packet: object) -> str:
    """Project validated JSON only; this function neither reads evidence nor decides H1."""
    value = _validate_packet_value(packet)
    lines = [
        "# H1 Source/Gold Review Packet",
        "",
        f"- Packet SHA-256: `{value['packet_sha256']}`",
        "- External publication authorized: `false`",
        "- Aggregate disposition: human decision required (not present in this packet)",
        "",
        "## Immutable bindings",
        "",
    ]
    for key, binding in value["bindings"].items():
        lines.append(f"- `{key}`: `{canonical_json_bytes(binding).decode('utf-8').rstrip() if isinstance(binding, dict) else binding}`")
    lines.extend(["", "## Fixture review items", ""])
    for review in value["fixture_reviews"]:
        lines.extend([
            f"### {review['fixture_id']}",
            "",
            f"- Category: `{review['category']}`",
            f"- expect_extract: `{str(review['expect_extract']).lower()}`",
            f"- Expected parameter count: `{review['expected_parameter_count']}`",
            f"- Expected parameter names: `{', '.join(review['expected_parameter_names'])}`",
            f"- Candidate surfaced then classify_out: `{str(review['candidate_surfaced_then_classify_out']).lower()}`",
            f"- Adapter lineage: `{canonical_json_bytes(review['adapter_lineage']).decode('utf-8').rstrip()}`",
            "- Signature slot: reviewer/signature intentionally blank pending independent human review",
            "",
        ])
    return "\n".join(lines)


def _publish_packet_pair(*, output_json: Path, output_markdown: Path, json_bytes: bytes, markdown_bytes: bytes) -> None:
    if output_json == output_markdown or output_json.parent != output_markdown.parent:
        raise H1Error("H1_OUTPUT_PATH_INVALID")
    target = output_json.parent
    parent = target.parent
    try:
        evidence = inspect_authoritative_path(_ROOT, _relative(parent, "H1_OUTPUT_PATH_INVALID"))
    except FilesystemPolicyError as error:
        raise H1Error("H1_OUTPUT_PATH_INVALID") from error
    if evidence.file_kind != "directory" or target.exists() or target.is_symlink():
        raise H1Error("H1_OUTPUT_EXISTS")
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=parent))
    try:
        _write_exact(staging / output_json.name, json_bytes)
        _write_exact(staging / output_markdown.name, markdown_bytes)
        _sync_directory(staging)
        _publish_directory_no_replace(staging, target, "H1_OUTPUT_EXISTS")
        _sync_directory(parent)
    except (BundleError, FileExistsError, OSError) as error:
        if staging.exists():
            shutil.rmtree(staging)
        raise H1Error("H1_OUTPUT_EXISTS") from error


def _read_canonical_external(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H1Error(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise H1Error(code)
    return value, raw


def _validate_v2_schema(schema: Path) -> bytes:
    value, raw = _read_canonical_external(schema, "H1_SCHEMA_INVALID")
    required = {
        "schema_version": "h1-review-schema-v2",
        "packet": {
            "additional_properties": False,
            "external_publication_authorized": False,
            "fixture_reviews": 11,
            "schema_version": "h1-source-gold-review-v2",
        },
        "readiness": {"additional_properties": False, "external_publication_authorized": False},
        "decision": {
            "additional_properties": False,
            "aggregate_disposition": ["approved", "disputed", "incomplete"],
            "external_publication_authorized": False,
            "fixture_reviews": 11,
            "human_authored": True,
            "semantic_response_ids": [
                "ts03_adjacency",
                "ts03_empty_null_single_element",
                "ts03_equal_element_stable_order",
                "ts04_unclassified_manual_review",
                "ts05_adjacency",
                "ts05_empty_null_single_element",
                "ts05_equal_element_stable_order",
            ],
        },
    }
    if value != required:
        raise H1Error("H1_SCHEMA_INVALID")
    return raw


def _canonical_digest(path: Path, code: str) -> str:
    if path == _H1_V3_MARKDOWN:
        try:
            _, raw = read_authoritative_file(path.parent, path.name)
        except (FilesystemPolicyError, OSError) as error:
            raise H1Error(code) from error
        return sha256_bytes(raw)
    _, raw = _read_canonical_external(path, code)
    return sha256_bytes(raw)


def _route_bindings() -> dict[str, str]:
    return {
        name: _canonical_digest(path, "H1_ROUTE_SUPERSESSION_INPUT_INVALID")
        for name, path in _ROUTE_BINDING_PATHS.items()
    }


def _historical_phase_gate() -> bytes:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(_ROOT / "src")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "tests/phase1_expected_red_oracle.py",
                "--expected-focused", "72",
                "--expected-discovered", "150",
                "--expected-green", "145",
            ],
            cwd=_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID") from error
    if completed.returncode != 0:
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    return completed.stdout


def _validate_v3_route_inputs(*, schema: Path, packet: Path, markdown: Path, readiness: Path) -> dict[str, str]:
    expected_paths = {
        "schema": _H1_V2_SCHEMA,
        "packet": _H1_V3_PACKET,
        "markdown": _H1_V3_MARKDOWN,
        "readiness": _H1_V3_READINESS,
    }
    supplied_paths = {"schema": schema, "packet": packet, "markdown": markdown, "readiness": readiness}
    for name, expected in expected_paths.items():
        if supplied_paths[name].absolute() != expected.absolute():
            raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    schema_raw = _validate_v2_schema(schema)
    packet_value, packet_raw = _read_canonical_external(packet, "H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    _validate_packet_value(packet_value)
    try:
        _, markdown_raw = read_authoritative_file(markdown.parent, markdown.name)
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID") from error
    if markdown_raw != render_h1_markdown(packet_value).encode("utf-8"):
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    readiness_value, readiness_raw = _read_canonical_external(readiness, "H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    if (
        set(readiness_value) != {"bindings", "external_publication_authorized", "readiness_sha256", "schema_version"}
        or readiness_value.get("schema_version") != "h1-review-readiness-v3"
        or readiness_value.get("external_publication_authorized") is not False
        or readiness_value.get("readiness_sha256") != sha256_bytes(canonical_json_bytes({
            key: value for key, value in readiness_value.items() if key != "readiness_sha256"
        }))
    ):
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    bindings = readiness_value.get("bindings")
    if not isinstance(bindings, dict) or bindings.get("packet_sha256") != sha256_bytes(packet_raw) or (
        bindings.get("schema_sha256") != sha256_bytes(schema_raw)
    ):
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    validate_h1_readiness_v3(
        readiness=readiness,
        formal_attempt=_H1_V2_FORMAL.parent,
        adversarial_result=_H1_V3_ADVERSARIAL,
        packet=packet,
        markdown=markdown,
        schema=schema,
        source_authority=_SUCCESSOR_HISTORICAL_AUTHORITY,
        canonical_revocation=_REVOCATION_V2,
        bundle=_H1_V3_BUNDLE,
        rules=_H1_V1_RULES,
        predictions=_H1_V2_PREDICTIONS,
        oracle=_H1_V2_ORACLE,
        offline_replay=_H1_V3_REPLAY,
        phase_gate=_historical_phase_gate(),
        plan_summary=_H1_V2_SUMMARY,
    )
    return {
        "h1_review_schema_v2_sha256": sha256_bytes(schema_raw),
        "packet_v3_json_sha256": sha256_bytes(packet_raw),
        "packet_v3_markdown_sha256": sha256_bytes(markdown_raw),
        "readiness_v3_sha256": sha256_bytes(readiness_raw),
    }


def _route_supersession_value(bindings: dict[str, str]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bindings": bindings,
        "external_publication_authorized": False,
        "local_only": True,
        "schema_version": "h1-review-route-supersession-v1",
        "status": "insufficient_for_decision",
    }
    value["supersession_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def _validate_route_supersession_receipt(supersession: Path) -> dict[str, Any]:
    """Strictly validate the published refusal receipt without replaying history."""
    value, _ = _read_canonical_external(supersession, "H1_ROUTE_SUPERSESSION_INVALID")
    expected = _route_supersession_value(_route_bindings())
    if value != expected:
        raise H1Error("H1_ROUTE_SUPERSESSION_INVALID")
    return value


def write_h1_route_supersession_v1(
    *, output: Path, schema: Path, packet: Path, markdown: Path, readiness: Path,
) -> dict[str, Any]:
    """Write the one immutable refusal receipt for the historical H1 route."""
    direct = _validate_v3_route_inputs(schema=schema, packet=packet, markdown=markdown, readiness=readiness)
    bindings = _route_bindings()
    if any(bindings[name] != value for name, value in direct.items()):
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    value = _route_supersession_value(bindings)
    try:
        write_new_descriptor_file(_ROOT, _relative(output, "H1_ROUTE_SUPERSESSION_OUTPUT_INVALID"), canonical_json_bytes(value))
    except FilesystemPolicyError as error:
        raise H1Error("H1_ROUTE_SUPERSESSION_OUTPUT_INVALID") from error
    return value


def validate_h1_route_supersession_v1(
    *, supersession: Path, schema: Path, packet: Path, markdown: Path, readiness: Path,
) -> dict[str, Any]:
    """Validate that the fixed v3 route remains historical evidence only."""
    direct = _validate_v3_route_inputs(schema=schema, packet=packet, markdown=markdown, readiness=readiness)
    bindings = _route_bindings()
    if any(bindings[name] != value for name, value in direct.items()):
        raise H1Error("H1_ROUTE_SUPERSESSION_INPUT_INVALID")
    return _validate_route_supersession_receipt(supersession)


def _ontology_options_value() -> dict[str, Any]:
    value = dict(_ONTOLOGY_OPTIONS)
    value["options_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def write_h1_ontology_options_v1(*, output: Path) -> dict[str, Any]:
    """Write the closed, decision-free H1 ontology policy request once."""
    value = _ontology_options_value()
    try:
        write_new_descriptor_file(_ROOT, _relative(output, "H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID"), canonical_json_bytes(value))
    except FilesystemPolicyError as error:
        raise H1Error("H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID") from error
    return value


def validate_h1_ontology_options_v1(*, options: Path) -> dict[str, Any]:
    """Require the exact closed PBMTE and cache choice request."""
    value, _ = _read_canonical_external(options, "H1_ONTOLOGY_OPTIONS_INVALID")
    if value != _ontology_options_value():
        raise H1Error("H1_ONTOLOGY_OPTIONS_INVALID")
    return value


def validate_h1_ontology_decision_v1(*, options: Path, supersession: Path, decision: Path) -> dict[str, Any]:
    """Validate a human-authored closed selection without supplying any human field."""
    options_value = validate_h1_ontology_options_v1(options=options)
    supersession_value = _validate_route_supersession_receipt(supersession)
    value, raw = _read_canonical_external(decision, "H1_ONTOLOGY_DECISION_INVALID")
    required = {
        "bindings", "cache_policy", "decision_sha256", "external_publication_authorized", "pbmte_policy",
        "reviewer", "schema_version", "signature", "timestamp",
    }
    if set(value) != required or value.get("schema_version") != "h1-source-gold-ontology-decision-v1" or (
        value.get("external_publication_authorized") is not False
    ):
        raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
    if value.get("decision_sha256") != sha256_bytes(canonical_json_bytes({
        key: item for key, item in value.items() if key != "decision_sha256"
    })):
        raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
    if value.get("bindings") != {
        "options_sha256": options_value["options_sha256"],
        "supersession_sha256": supersession_value["supersession_sha256"],
    }:
        raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
    for key, choices in (("pbmte_policy", options_value["pbmte_choices"]), ("cache_policy", options_value["cache_choices"])):
        policy = value.get(key)
        if (
            not isinstance(policy, dict)
            or set(policy) != {"rationale", "selection"}
            or not isinstance(policy.get("rationale"), str)
            or not policy["rationale"].strip()
        ):
            raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
        if policy.get("selection") not in {choice["id"] for choice in choices}:
            raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
    if not all(
        isinstance(value.get(key), str) and value[key].strip() for key in ("reviewer", "signature")
    ) or not _is_canonical_utc_timestamp(value.get("timestamp")):
        raise H1Error("H1_ONTOLOGY_DECISION_INVALID")
    return {
        "artifact_sha256": sha256_bytes(raw),
        "decision_sha256": value["decision_sha256"],
        "selected_policy": {
            "cache": value["cache_policy"]["selection"],
            "pbmte": value["pbmte_policy"]["selection"],
        },
        "valid": True,
    }


def build_h1_packet(
    *, formal_attempt: Path, adversarial_report: Path, output_json: Path, output_markdown: Path, schema: Path,
    authority: Path, bundle: Path, rules: Path, predictions: Path, oracle: Path,
    pending_authority: Path | None = None, transition: Path | None = None, revocation: Path | None = None,
) -> dict[str, Any]:
    """Build an immutable packet from validated evidence; it never creates a decision."""
    _validate_v2_schema(schema)
    batch = _batch(
        authority=authority, bundle=bundle, rules=rules, pending_authority=pending_authority,
        transition=transition, revocation=revocation,
    )
    expected = _expected_bindings(
        formal_attempt=formal_attempt, adversarial_report=adversarial_report, h1_schema=schema,
        authority=authority, bundle=bundle, rules=rules, predictions=predictions, oracle=oracle,
        pending_authority=pending_authority, transition=transition, revocation=revocation, batch=batch,
    )
    packet: dict[str, Any] = {
        "bindings": expected,
        "external_publication_authorized": False,
        "fixture_reviews": _review_items(batch),
        "schema_version": "h1-source-gold-review-v2",
    }
    packet["packet_sha256"] = sha256_bytes(canonical_json_bytes(packet))
    _validate_packet_value(packet, expected=expected)
    _publish_packet_pair(
        output_json=output_json,
        output_markdown=output_markdown,
        json_bytes=canonical_json_bytes(packet),
        markdown_bytes=render_h1_markdown(packet).encode("utf-8"),
    )
    return packet


def validate_h1_packet(
    *, packet: Path, markdown: Path, schema: Path, formal_attempt: Path, adversarial_report: Path,
    authority: Path, bundle: Path, rules: Path, predictions: Path, oracle: Path,
    pending_authority: Path | None = None, transition: Path | None = None, revocation: Path | None = None,
) -> dict[str, Any]:
    """Recompute every current H1 binding and reject non-projection Markdown."""
    _validate_v2_schema(schema)
    value, _ = _read_canonical(packet, "H1_PACKET_INVALID")
    batch = _batch(
        authority=authority, bundle=bundle, rules=rules, pending_authority=pending_authority,
        transition=transition, revocation=revocation,
    )
    expected = _expected_bindings(
        formal_attempt=formal_attempt, adversarial_report=adversarial_report, h1_schema=schema,
        authority=authority, bundle=bundle, rules=rules, predictions=predictions, oracle=oracle,
        pending_authority=pending_authority, transition=transition, revocation=revocation, batch=batch,
    )
    value = _validate_packet_value(value, expected=expected)
    if value.get("fixture_reviews") != _review_items(batch):
        raise H1Error("H1_REVIEW_ITEM_INVALID")
    try:
        _, markdown_bytes = read_authoritative_file(_ROOT, _relative(markdown, "H1_MARKDOWN_INVALID"))
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_MARKDOWN_INVALID") from error
    if markdown_bytes != render_h1_markdown(value).encode("utf-8"):
        raise H1Error("H1_MARKDOWN_INVALID")
    return value


def _readiness_bindings(
    *, formal_attempt: Path, adversarial_result: Path, packet: Path, markdown: Path, schema: Path,
    source_authority: Path, canonical_revocation: Path, bundle: Path, rules: Path, predictions: Path, oracle: Path,
    offline_replay: Path, phase_gate: bytes,
    plan_summary: Path,
) -> dict[str, str]:
    if not plan_summary.is_absolute() or ".." in plan_summary.parts:
        raise H1Error("H1_PLAN_SUMMARY_PATH_INVALID")
    _validate_v2_schema(schema)
    validate_h1_packet(
        packet=packet, markdown=markdown, schema=schema, formal_attempt=formal_attempt,
        adversarial_report=adversarial_result, authority=source_authority, bundle=bundle, rules=rules,
        predictions=predictions, oracle=oracle, revocation=canonical_revocation,
    )
    _, formal_raw = _read_canonical_external(formal_attempt / "attempt.json", "H1_FORMAL_ATTEMPT_INVALID")
    _, adversarial_raw = _read_canonical_external(adversarial_result, "H1_ADVERSARIAL_REPORT_INVALID")
    _, packet_raw = _read_canonical_external(packet, "H1_PACKET_INVALID")
    try:
        _, markdown_raw = read_authoritative_file(markdown.parent, markdown.name)
        _, authority_raw = _read_canonical_external(source_authority, "H1_SOURCE_AUTHORITY_INVALID")
        _, revocation_raw = _read_canonical_external(canonical_revocation, "H1_REVOCATION_INVALID")
        _, replay_raw = _read_canonical_external(offline_replay, "H1_OFFLINE_REPLAY_INVALID")
        _, summary_raw = read_authoritative_file(plan_summary.parent, plan_summary.name)
        phase_gate_value = json.loads(phase_gate.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise H1Error("H1_READINESS_INPUT_INVALID") from error
    if canonical_json_bytes(phase_gate_value) != phase_gate:
        raise H1Error("H1_PHASE_GATE_INVALID")
    return {
        "adversarial_result_sha256": sha256_bytes(adversarial_raw),
        "canonical_revocation_sha256": sha256_bytes(revocation_raw),
        "formal_attempt_sha256": sha256_bytes(formal_raw),
        "markdown_sha256": sha256_bytes(markdown_raw),
        "offline_replay_sha256": sha256_bytes(replay_raw),
        "packet_sha256": sha256_bytes(packet_raw),
        "phase_gate_sha256": sha256_bytes(phase_gate),
        "plan_summary_sha256": sha256_bytes(summary_raw),
        "schema_sha256": sha256_bytes(_validate_v2_schema(schema)),
        "source_authority_sha256": sha256_bytes(authority_raw),
    }


def _readiness_value(bindings: dict[str, str]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bindings": bindings,
        "external_publication_authorized": False,
        "schema_version": "h1-review-readiness-v3",
    }
    value["readiness_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def write_h1_readiness_v3(
    *, output: Path, formal_attempt: Path, adversarial_result: Path, packet: Path, markdown: Path, schema: Path,
    source_authority: Path, canonical_revocation: Path, bundle: Path, rules: Path, predictions: Path, oracle: Path,
    offline_replay: Path, phase_gate: bytes, plan_summary: Path,
) -> dict[str, Any]:
    """Create one descriptor-checked readiness receipt; never creates a human decision."""
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise H1Error("H1_READINESS_EXISTS")
    value = _readiness_value(_readiness_bindings(
        formal_attempt=formal_attempt, adversarial_result=adversarial_result, packet=packet, markdown=markdown,
        schema=schema, source_authority=source_authority, canonical_revocation=canonical_revocation,
        bundle=bundle, rules=rules, predictions=predictions, oracle=oracle,
        offline_replay=offline_replay, phase_gate=phase_gate, plan_summary=plan_summary,
    ))
    try:
        _write_exact(output, canonical_json_bytes(value))
        _sync_directory(output.parent)
    except (FileExistsError, OSError) as error:
        raise H1Error("H1_READINESS_EXISTS") from error
    return value


def validate_h1_readiness_v3(
    *, readiness: Path, formal_attempt: Path, adversarial_result: Path, packet: Path, markdown: Path, schema: Path,
    source_authority: Path, canonical_revocation: Path, bundle: Path, rules: Path, predictions: Path, oracle: Path,
    offline_replay: Path, phase_gate: bytes, plan_summary: Path,
) -> dict[str, Any]:
    """Compare a pre-existing readiness receipt with fresh held inputs without rewriting it."""
    value, _ = _read_canonical_external(readiness, "H1_READINESS_INVALID")
    expected = _readiness_value(_readiness_bindings(
        formal_attempt=formal_attempt, adversarial_result=adversarial_result, packet=packet, markdown=markdown,
        schema=schema, source_authority=source_authority, canonical_revocation=canonical_revocation,
        bundle=bundle, rules=rules, predictions=predictions, oracle=oracle,
        offline_replay=offline_replay, phase_gate=phase_gate, plan_summary=plan_summary,
    ))
    if value != expected:
        raise H1Error("H1_READINESS_BINDINGS_INVALID")
    return value


_SEMANTIC_RESPONSE_IDS = (
    "ts03_adjacency", "ts03_empty_null_single_element", "ts03_equal_element_stable_order",
    "ts04_unclassified_manual_review", "ts05_adjacency", "ts05_empty_null_single_element",
    "ts05_equal_element_stable_order",
)


def validate_h1_decision_v2(*, schema: Path, packet: Path, readiness: Path, decision: Path) -> dict[str, Any]:
    """Validate a fully human-authored successor decision without authoring or inferring one."""
    schema_raw = _validate_v2_schema(schema)
    packet_value, packet_raw = _read_canonical_external(packet, "H1_PACKET_INVALID")
    packet_value = _validate_packet_value(packet_value)
    readiness_value, readiness_raw = _read_canonical_external(readiness, "H1_READINESS_INVALID")
    if (
        set(readiness_value) != {"bindings", "external_publication_authorized", "readiness_sha256", "schema_version"}
        or readiness_value.get("schema_version") != "h1-review-readiness-v3"
        or readiness_value.get("external_publication_authorized") is not False
    ):
        raise H1Error("H1_READINESS_INVALID")
    readiness_bindings = readiness_value.get("bindings")
    required_readiness_bindings = {
        "adversarial_result_sha256", "canonical_revocation_sha256", "formal_attempt_sha256", "markdown_sha256",
        "offline_replay_sha256", "packet_sha256", "phase_gate_sha256", "plan_summary_sha256", "schema_sha256",
        "source_authority_sha256",
    }
    if not isinstance(readiness_bindings, dict) or set(readiness_bindings) != required_readiness_bindings:
        raise H1Error("H1_READINESS_INVALID")
    for binding in readiness_bindings.values():
        _require_digest(binding, "H1_READINESS_INVALID")
    _require_digest(readiness_value.get("readiness_sha256"), "H1_READINESS_INVALID")
    if readiness_value.get("readiness_sha256") != sha256_bytes(canonical_json_bytes({
        key: value for key, value in readiness_value.items() if key != "readiness_sha256"
    })):
        raise H1Error("H1_READINESS_INVALID")
    if (
        readiness_bindings["packet_sha256"] != sha256_bytes(packet_raw)
        or readiness_bindings["schema_sha256"] != sha256_bytes(schema_raw)
    ):
        raise H1Error("H1_READINESS_BINDINGS_INVALID")
    value, _ = _read_canonical_external(decision, "H1_DECISION_INVALID")
    required = {
        "aggregate_disposition", "bindings", "decision_sha256", "external_publication_authorized", "fixture_reviews",
        "rationale", "reviewer", "schema_version", "semantic_responses", "timestamp",
    }
    if set(value) != required or value.get("schema_version") != "h1-source-gold-decision-v2" or value.get("external_publication_authorized") is not False:
        raise H1Error("H1_DECISION_INVALID")
    if value.get("decision_sha256") != sha256_bytes(canonical_json_bytes({key: item for key, item in value.items() if key != "decision_sha256"})):
        raise H1Error("H1_DECISION_HASH_INVALID")
    if not all(isinstance(value.get(key), str) and value[key] for key in ("reviewer", "timestamp", "rationale")):
        raise H1Error("H1_DECISION_INVALID")
    expected_bindings = {
        "packet_sha256": packet_value["packet_sha256"],
        "phase_gate_sha256": readiness_value.get("bindings", {}).get("phase_gate_sha256"),
        "readiness_sha256": readiness_value.get("readiness_sha256"),
        "schema_sha256": sha256_bytes(schema_raw),
    }
    if value.get("bindings") != expected_bindings:
        raise H1Error("H1_DECISION_BINDINGS_INVALID")
    reviews = value.get("fixture_reviews")
    packet_reviews = packet_value.get("fixture_reviews")
    if not isinstance(reviews, list) or not isinstance(packet_reviews, list) or len(reviews) != 11:
        raise H1Error("H1_DECISION_REVIEW_SET_INVALID")
    expected_by_id = {review["fixture_id"]: review for review in packet_reviews if isinstance(review, dict)}
    if len(expected_by_id) != 11 or {review.get("fixture_id") for review in reviews if isinstance(review, dict)} != set(expected_by_id):
        raise H1Error("H1_DECISION_REVIEW_SET_INVALID")
    dispositions: list[str] = []
    for review in reviews:
        if not isinstance(review, dict) or set(review) != {"disposition", "fixture_id", "reviewed_semantics_sha256", "reviewer", "signature"}:
            raise H1Error("H1_DECISION_REVIEW_INVALID")
        expected_review = expected_by_id.get(review.get("fixture_id"))
        if expected_review is None or review.get("reviewed_semantics_sha256") != sha256_bytes(canonical_json_bytes({
            key: item for key, item in expected_review.items() if key != "signature_slot"
        })) or not isinstance(review.get("reviewer"), str) or not review["reviewer"]:
            raise H1Error("H1_DECISION_REVIEW_INVALID")
        disposition = review.get("disposition")
        signature = review.get("signature")
        if disposition not in {"approved", "disputed", "incomplete"} or (disposition == "incomplete" and signature is not None) or (disposition != "incomplete" and (not isinstance(signature, str) or not signature)):
            raise H1Error("H1_DECISION_REVIEW_INVALID")
        dispositions.append(disposition)
    responses = value.get("semantic_responses")
    if not isinstance(responses, dict) or set(responses) != set(_SEMANTIC_RESPONSE_IDS):
        raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
    for identifier in _SEMANTIC_RESPONSE_IDS:
        response = responses[identifier]
        if not isinstance(response, dict) or set(response) != {"disposition", "response"}:
            raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        disposition = response.get("disposition")
        answer = response.get("response")
        if disposition not in {"approved", "disputed", "incomplete"} or (disposition == "incomplete" and answer is not None) or (disposition != "incomplete" and (not isinstance(answer, str) or not answer)):
            raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        dispositions.append(disposition)
    aggregate = value.get("aggregate_disposition")
    expected_aggregate = "incomplete" if "incomplete" in dispositions else "disputed" if "disputed" in dispositions else "approved"
    if aggregate != expected_aggregate:
        raise H1Error("H1_DISPUTE_AGGREGATION_INVALID")
    supersession = _validate_route_supersession_receipt(_ROUTE_SUPERSESSION)
    route_bindings = supersession["bindings"]
    if (
        sha256_bytes(packet_raw) == route_bindings["packet_v3_json_sha256"]
        and sha256_bytes(readiness_raw) == route_bindings["readiness_v3_sha256"]
    ):
        raise H1Error("H1_LEGACY_ROUTE_SUPERSEDED")
    return {
        "aggregate_disposition": aggregate,
        "decision_sha256": value["decision_sha256"],
        "external_publication_authorized": False,
        "fixture_count": 11,
        "semantic_response_ids": sorted(_SEMANTIC_RESPONSE_IDS),
        "valid": True,
    }


# Successor v6 route.  The historical v2/v3 contracts above remain readable and
# immutable; these functions deliberately use new schema names and never infer
# or emit a human-controlled field.
_SUCCESSOR_QUESTION_IDS = _SEMANTIC_RESPONSE_IDS
_SUCCESSOR_FIXTURE_IDS = (
    "CAND_WARL_FIXED_LEGAL_SET",
    "NEG_EXT_GATED_PBMTE",
    "NEG_FIXED_ENCODING",
    "NEG_SHALL_NO_DELEGATION",
    "NEG_SOFTWARE_ADVICE",
    "POS_CSR_RW_MTVEC_ACCESS",
    "POS_DIRECT_CACHE_BLOCK",
    "POS_DIRECT_NUM_PMP",
    "POS_RECALL_COUNT_GEILEN",
    "POS_WARL_ASID_WIDTH",
    "POS_WARL_MTVEC_MODES",
)
_HUMAN_DISPOSITIONS = ("approved", "disputed", "incomplete")
_HUMAN_RESPONSES = (
    "approve_expected_semantics",
    "reject_expected_semantics",
    "needs_revision",
)
_QUESTION_KEYS = {
    "allowed_dispositions",
    "allowed_responses",
    "evidence",
    "expected_semantics",
    "fixture_ids",
    "id",
    "machine_assertions",
    "metric",
    "metric_effect",
    "policy_ids",
    "prompt",
    "rationale",
    "requirement_id",
    "structural_rules",
    "subject_type",
}
_STRUCTURAL_RULE_KEYS = {
    "adjacency",
    "deduplication",
    "empty_null_single",
    "equal_element_order",
}
_SUCCESSOR_PACKET_BINDING_KEYS = {
    "adapter_batch_file_sha256",
    "adapter_batch_sha256",
    "adversarial_contract_sha256",
    "adversarial_report_sha256",
    "adjudication_schema_sha256",
    "executable_closure_sha256",
    "fixture_registry_sha256",
    "formal_attempt_manifest_sha256",
    "formal_attempt_sha256",
    "golden_predictions_sha256",
    "h1_review_schema_sha256",
    "ontology_decision_sha256",
    "questions_semantic_content_sha256",
    "questions_sha256",
    "rule_sha256",
    "semantic_contract_sha256",
    "source_authority_sha256",
}


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _successor_question_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key != "canonical_semantic_content_sha256"
    }


def validate_h1_semantic_questions_v2(
    *, questions: Path, bundle_root: Path | None = None
) -> dict[str, Any]:
    """Validate seven fully specified, source-bound questions with no human values."""
    value, raw = _read_canonical_external(questions, "H1_SEMANTIC_QUESTIONS_INVALID")
    if set(value) != {
        "canonical_semantic_content_sha256",
        "ontology_policies",
        "question_ids",
        "questions",
        "schema_version",
    } or value.get("schema_version") != "h1-semantic-review-questions-v2":
        raise H1Error("H1_SEMANTIC_QUESTIONS_INVALID")
    if value.get("question_ids") != list(_SUCCESSOR_QUESTION_IDS):
        raise H1Error("H1_SEMANTIC_QUESTIONS_INVALID")
    expected_semantic_sha = sha256_bytes(
        canonical_json_bytes(_successor_question_projection(value))
    )
    if value.get("canonical_semantic_content_sha256") != expected_semantic_sha:
        raise H1Error("H1_SEMANTIC_QUESTIONS_HASH_INVALID")
    policies = value.get("ontology_policies")
    if policies != [
        {
            "id": "CACHE",
            "rationale": "The current CMO specification requires one uniform cache-block size for the initial CMO extensions.",
            "selection": "unified_cache_block_identity",
        },
        {
            "id": "PBMTE",
            "rationale": "Svpbmt availability is surfaced as implementation-dependent evidence, while PBMTE remains a runtime enable field and is classified out as a final parameter.",
            "selection": "surfaced_classified_out",
        },
    ]:
        raise H1Error("H1_SEMANTIC_QUESTIONS_POLICY_INVALID")
    entries = value.get("questions")
    if not isinstance(entries, list) or len(entries) != 7:
        raise H1Error("H1_SEMANTIC_QUESTIONS_INVALID")
    if [entry.get("id") for entry in entries if isinstance(entry, dict)] != list(
        _SUCCESSOR_QUESTION_IDS
    ):
        raise H1Error("H1_SEMANTIC_QUESTIONS_INVALID")
    covered_fixtures: set[str] = set()
    covered_policies: set[str] = set()
    source_cache: dict[str, bytes] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _QUESTION_KEYS:
            raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        if (
            entry.get("requirement_id") not in {"TS-03", "TS-04", "TS-05"}
            or not _nonempty_text(entry.get("metric"))
            or not _nonempty_text(entry.get("subject_type"))
            or not _nonempty_text(entry.get("prompt"))
            or not _nonempty_text(entry.get("rationale"))
            or entry.get("allowed_dispositions") != list(_HUMAN_DISPOSITIONS)
            or entry.get("allowed_responses") != list(_HUMAN_RESPONSES)
        ):
            raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        fixture_ids = entry.get("fixture_ids")
        policy_ids = entry.get("policy_ids")
        if (
            not isinstance(fixture_ids, list)
            or not fixture_ids
            or fixture_ids != sorted(fixture_ids)
            or len(fixture_ids) != len(set(fixture_ids))
            or not set(fixture_ids) <= set(_SUCCESSOR_FIXTURE_IDS)
            or not isinstance(policy_ids, list)
            or policy_ids != sorted(policy_ids)
            or len(policy_ids) != len(set(policy_ids))
            or not set(policy_ids) <= {"CACHE", "PBMTE"}
        ):
            raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        covered_fixtures.update(fixture_ids)
        covered_policies.update(policy_ids)
        structural = entry.get("structural_rules")
        if (
            not isinstance(structural, dict)
            or set(structural) != _STRUCTURAL_RULE_KEYS
            or not all(_nonempty_text(item) for item in structural.values())
        ):
            raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        expected = entry.get("expected_semantics")
        metric_effect = entry.get("metric_effect")
        assertions = entry.get("machine_assertions")
        if (
            not isinstance(expected, dict)
            or set(expected) != {"accepted_behavior", "rejected_behavior", "summary"}
            or not all(_nonempty_text(item) for item in expected.values())
            or not isinstance(metric_effect, dict)
            or set(metric_effect) != {"denominator_effect", "failure_effect", "metric"}
            or not all(_nonempty_text(item) for item in metric_effect.values())
            or not isinstance(assertions, list)
            or not assertions
        ):
            raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        for assertion in assertions:
            if (
                not isinstance(assertion, dict)
                or set(assertion) != {"expected", "id", "operator", "path"}
                or not all(
                    _nonempty_text(assertion.get(key))
                    for key in ("id", "operator", "path")
                )
            ):
                raise H1Error("H1_SEMANTIC_QUESTION_INVALID")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID")
        evidence_fixtures: set[str] = set()
        for span in evidence:
            if not isinstance(span, dict) or set(span) != {
                "end_byte",
                "fixture_id",
                "source_path",
                "source_sha256",
                "start_byte",
                "text",
            }:
                raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID")
            fixture_id = span.get("fixture_id")
            source_path = span.get("source_path")
            source_sha256 = span.get("source_sha256")
            start = span.get("start_byte")
            end = span.get("end_byte")
            text = span.get("text")
            if (
                fixture_id not in fixture_ids
                or not isinstance(source_path, str)
                or not source_path.startswith(f"raw/evaluation_fixtures/{fixture_id}/")
                or not source_path.endswith("/source.txt")
                or not isinstance(source_sha256, str)
                or len(source_sha256) != 64
                or isinstance(start, bool)
                or not isinstance(start, int)
                or isinstance(end, bool)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or not _nonempty_text(text)
                or len(text.encode("utf-8")) != end - start
            ):
                raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID")
            evidence_fixtures.add(fixture_id)
            if bundle_root is not None:
                if source_path not in source_cache:
                    try:
                        _, source_cache[source_path] = read_authoritative_file(
                            bundle_root, source_path
                        )
                    except (FilesystemPolicyError, OSError) as error:
                        raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID") from error
                source = source_cache[source_path]
                if (
                    sha256_bytes(source) != source_sha256
                    or end > len(source)
                    or source[start:end] != text.encode("utf-8")
                ):
                    raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID")
        if evidence_fixtures != set(fixture_ids):
            raise H1Error("H1_SEMANTIC_QUESTION_EVIDENCE_INVALID")
    if covered_fixtures != set(_SUCCESSOR_FIXTURE_IDS) or covered_policies != {
        "CACHE",
        "PBMTE",
    }:
        raise H1Error("H1_SEMANTIC_QUESTION_COVERAGE_INVALID")
    return {
        "canonical_semantic_content_sha256": expected_semantic_sha,
        "question_count": 7,
        "question_ids": list(_SUCCESSOR_QUESTION_IDS),
        "questions_sha256": sha256_bytes(raw),
        "valid": True,
    }


def validate_h1_review_schema_v4(
    *, schema: Path, questions: Path, bundle_root: Path | None = None
) -> dict[str, Any]:
    """Require the closed v4 schema to bind the exact seven-question bytes."""
    if tuple(questions.parts[-3:]) != (
        "config",
        "measurement",
        "h1-semantic-review-questions-v2.json",
    ):
        raise H1Error("H1_REVIEW_SCHEMA_V4_INVALID")
    questions_result = validate_h1_semantic_questions_v2(
        questions=questions, bundle_root=bundle_root
    )
    value, raw = _read_canonical_external(schema, "H1_REVIEW_SCHEMA_V4_INVALID")
    expected = {
        "additional_properties": False,
        "decision": {
            "additional_properties": False,
            "allowed_dispositions": list(_HUMAN_DISPOSITIONS),
            "allowed_responses": list(_HUMAN_RESPONSES),
            "fixture_reviews": 11,
            "human_fields": [
                "reviewer_identity",
                "rationale",
                "signature",
                "timestamp",
            ],
            "schema_version": "h1-source-gold-decision-v5",
            "semantic_responses": 7,
        },
        "packet": {
            "additional_properties": False,
            "external_publication_authorized": False,
            "fixture_reviews": 11,
            "schema_version": "h1-source-gold-review-v6",
            "semantic_questions": 7,
        },
        "questions": {
            "canonical_semantic_content_sha256": questions_result[
                "canonical_semantic_content_sha256"
            ],
            "path": "config/measurement/h1-semantic-review-questions-v2.json",
            "question_ids": list(_SUCCESSOR_QUESTION_IDS),
            "sha256": questions_result["questions_sha256"],
        },
        "readiness": {
            "additional_properties": False,
            "external_publication_authorized": False,
            "schema_version": "h1-semantic-readiness-v6",
        },
        "schema_version": "h1-review-schema-v4",
    }
    if value != expected:
        raise H1Error("H1_REVIEW_SCHEMA_V4_INVALID")
    return {"schema_sha256": sha256_bytes(raw), "valid": True, **questions_result}


def _successor_fixture_reviews(golden: dict[str, Any]) -> list[dict[str, Any]]:
    outcomes = golden.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != 11:
        raise H1Error("H1_SUCCESSOR_GOLDEN_INVALID")
    reviews: list[dict[str, Any]] = []
    for outcome in outcomes:
        if not isinstance(outcome, dict) or not isinstance(outcome.get("fixture_id"), str):
            raise H1Error("H1_SUCCESSOR_GOLDEN_INVALID")
        projection = {
            key: item
            for key, item in outcome.items()
            if key != "reviewed_semantics_sha256"
        }
        review = {
            "fixture_id": outcome["fixture_id"],
            "reviewed_semantics": projection,
            "reviewed_semantics_sha256": sha256_bytes(canonical_json_bytes(projection)),
        }
        reviews.append(review)
    if [item["fixture_id"] for item in reviews] != list(_SUCCESSOR_FIXTURE_IDS):
        raise H1Error("H1_SUCCESSOR_GOLDEN_INVALID")
    return reviews


def _successor_packet_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "packet_sha256"}


def _read_successor_formal_manifest(formal_attempt: Path) -> tuple[dict[str, Any], bytes]:
    manifest = formal_attempt / "attempt.json" if formal_attempt.is_dir() else formal_attempt
    value, raw = _read_canonical_external(manifest, "H1_SUCCESSOR_FORMAL_INVALID")
    if value.get("role") != "formal" or value.get("status") != "completed":
        raise H1Error("H1_SUCCESSOR_FORMAL_INVALID")
    return value, raw


def _successor_bindings(
    *,
    adapter_batch: Path,
    adversarial_report: Path,
    adversarial_contract: Path,
    adjudication_schema: Path,
    executable_closure: Path,
    fixture_registry: Path,
    formal_attempt: Path,
    golden_predictions: Path,
    ontology_decision: Path,
    ontology_options: Path,
    ontology_supersession: Path,
    questions: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    source_authority: Path,
    bundle_root: Path | None = None,
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    if bundle_root is None:
        raise H1Error("H1_SUCCESSOR_BUNDLE_REQUIRED")
    schema_result = validate_h1_review_schema_v4(
        schema=schema, questions=questions, bundle_root=bundle_root
    )
    questions_value, questions_raw = _read_canonical_external(
        questions, "H1_SEMANTIC_QUESTIONS_INVALID"
    )
    golden, golden_raw = _read_canonical_external(
        golden_predictions, "H1_SUCCESSOR_GOLDEN_INVALID"
    )
    if golden.get("schema_version") != "golden-predictions-v4":
        raise H1Error("H1_SUCCESSOR_GOLDEN_INVALID")
    _successor_fixture_reviews(golden)
    closure, closure_raw = _read_canonical_external(
        executable_closure, "H1_SUCCESSOR_EXECUTABLE_CLOSURE_INVALID"
    )
    if (
        executable_closure.absolute() != _SUCCESSOR_EXECUTABLE_CLOSURE.absolute()
        or ontology_options.absolute() != _SUCCESSOR_ONTOLOGY_OPTIONS.absolute()
        or ontology_supersession.absolute() != _ROUTE_SUPERSESSION.absolute()
        or ontology_decision.absolute() != _SUCCESSOR_ONTOLOGY_DECISION.absolute()
        or source_authority.absolute() != _ACTIVE_AUTHORITY.absolute()
    ):
        raise H1Error("H1_SUCCESSOR_GOVERNANCE_INVALID")
    try:
        _, historical_authority_raw = _read_canonical_external(
            _SUCCESSOR_HISTORICAL_AUTHORITY,
            "H1_SUCCESSOR_GOVERNANCE_INVALID",
        )
        verify_runtime_closure_v3(
            closure,
            _REPOSITORY,
            authority_pre_state_raw=historical_authority_raw,
        )
        ontology_result = validate_h1_ontology_decision_v1(
            options=ontology_options,
            supersession=ontology_supersession,
            decision=ontology_decision,
        )
        authority_result = validate_accepted_v6_active_authority(_REPOSITORY)
    except (RuntimeClosureError, SuccessorProtocolError, OSError, ValueError) as error:
        raise H1Error("H1_SUCCESSOR_GOVERNANCE_INVALID") from error
    if ontology_result.get("selected_policy") != {
        "cache": "unified_cache_block_identity",
        "pbmte": "surfaced_classified_out",
    }:
        raise H1Error("H1_SUCCESSOR_ONTOLOGY_INVALID")
    _, ontology_raw = _read_canonical_external(
        ontology_decision, "H1_SUCCESSOR_ONTOLOGY_INVALID"
    )
    if ontology_result.get("artifact_sha256") != sha256_bytes(ontology_raw):
        raise H1Error("H1_SUCCESSOR_ONTOLOGY_INVALID")
    _, authority_raw = _read_canonical_external(
        source_authority, "H1_SUCCESSOR_SOURCE_AUTHORITY_INVALID"
    )
    if authority_result.get("authority_sha256") != sha256_bytes(authority_raw):
        raise H1Error("H1_SUCCESSOR_SOURCE_AUTHORITY_INVALID")
    try:
        batch, adapter_raw, _, rebuilt_golden_raw = _successor_adapter_v6(
            adapter_batch=adapter_batch,
            fixture_registry=fixture_registry,
            rules=rules,
            semantic_contract=semantic_contract,
            golden_predictions=golden_predictions,
            bundle_root=bundle_root,
        )
        if rebuilt_golden_raw != golden_raw:
            raise AttemptError("SUCCESSOR_GOLDEN_REOPEN_MISMATCH")
        formal_result = validate_formal_measurement_v5(
            adapter_batch=adapter_batch,
            fixture_registry=fixture_registry,
            rules=rules,
            semantic_contract=semantic_contract,
            golden_predictions=golden_predictions,
            adjudication_schema=adjudication_schema,
            bundle_root=bundle_root,
            attempt=formal_attempt,
        )
        adversarial_result = validate_adversarial_result_v6(
            report=adversarial_report,
            contract=adversarial_contract,
            golden_predictions=golden_predictions,
            formal_attempt=formal_attempt,
            adapter_batch=adapter_batch,
            fixture_registry=fixture_registry,
            rules=rules,
            semantic_contract=semantic_contract,
            schema=adjudication_schema,
            bundle_root=bundle_root,
        )
    except AttemptError as error:
        raise H1Error(f"H1_SUCCESSOR_UPSTREAM_INVALID:{error}") from error
    if (
        formal_result.get("case_count") != 11
        or formal_result.get("metrics")
        != {
            "disposition": {"denominator": 8, "numerator": 8},
            "evidence_integrity": {"denominator": 10, "numerator": 10},
            "identity": {"denominator": 6, "numerator": 6},
            "negative_controls": {"denominator": 3, "numerator": 3},
            "surfacing": {"denominator": 8, "numerator": 8},
        }
        or adversarial_result.get("case_count") != 17
        or adversarial_result.get("status") != "diagnostic_only"
        or adversarial_result.get("valid") is not True
    ):
        raise H1Error("H1_SUCCESSOR_UPSTREAM_INVALID")
    formal, formal_raw = _read_successor_formal_manifest(formal_attempt)
    adversarial, adversarial_raw = _read_canonical_external(
        adversarial_report, "H1_SUCCESSOR_ADVERSARIAL_INVALID"
    )
    if (
        formal.get("attempt_sha256") != formal_result.get("attempt_sha256")
        or adversarial.get("report_sha256") != adversarial_result.get("report_sha256")
    ):
        raise H1Error("H1_SUCCESSOR_UPSTREAM_INVALID")
    canonical_inputs = {
        "adversarial_contract_sha256": adversarial_contract,
        "adversarial_report_sha256": adversarial_report,
        "adjudication_schema_sha256": adjudication_schema,
        "fixture_registry_sha256": fixture_registry,
        "rule_sha256": rules,
        "semantic_contract_sha256": semantic_contract,
    }
    bindings: dict[str, str] = {
        "adapter_batch_file_sha256": sha256_bytes(adapter_raw),
        "adapter_batch_sha256": str(getattr(batch, "adapter_batch_sha256")),
        "formal_attempt_manifest_sha256": sha256_bytes(formal_raw),
        "formal_attempt_sha256": str(formal_result["attempt_sha256"]),
        "golden_predictions_sha256": sha256_bytes(golden_raw),
        "h1_review_schema_sha256": str(schema_result["schema_sha256"]),
        "executable_closure_sha256": sha256_bytes(closure_raw),
        "ontology_decision_sha256": sha256_bytes(ontology_raw),
        "questions_semantic_content_sha256": str(
            schema_result["canonical_semantic_content_sha256"]
        ),
        "questions_sha256": sha256_bytes(questions_raw),
        "source_authority_sha256": sha256_bytes(authority_raw),
    }
    for name, path in canonical_inputs.items():
        _, raw = _read_canonical_external(path, "H1_SUCCESSOR_BINDING_INVALID")
        bindings[name] = sha256_bytes(raw)
    if set(bindings) != _SUCCESSOR_PACKET_BINDING_KEYS:
        raise H1Error("H1_SUCCESSOR_BINDING_INVALID")
    return bindings, questions_value, golden


def _validate_successor_packet_value(
    value: object,
    *,
    expected_bindings: dict[str, str] | None = None,
    expected_questions: list[dict[str, Any]] | None = None,
    expected_reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "bindings",
        "external_publication_authorized",
        "fixture_reviews",
        "packet_sha256",
        "schema_version",
        "semantic_questions",
    }:
        raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    if (
        value.get("schema_version") != "h1-source-gold-review-v6"
        or value.get("external_publication_authorized") is not False
        or value.get("packet_sha256")
        != sha256_bytes(canonical_json_bytes(_successor_packet_projection(value)))
    ):
        raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    bindings = value.get("bindings")
    if (
        not isinstance(bindings, dict)
        or set(bindings) != _SUCCESSOR_PACKET_BINDING_KEYS
        or any(
            not isinstance(item, str) or len(item) != 64
            for item in bindings.values()
        )
        or (expected_bindings is not None and bindings != expected_bindings)
    ):
        raise H1Error("H1_SUCCESSOR_PACKET_BINDING_INVALID")
    reviews = value.get("fixture_reviews")
    questions = value.get("semantic_questions")
    if (
        not isinstance(reviews, list)
        or [item.get("fixture_id") for item in reviews if isinstance(item, dict)]
        != list(_SUCCESSOR_FIXTURE_IDS)
        or not isinstance(questions, list)
        or [item.get("id") for item in questions if isinstance(item, dict)]
        != list(_SUCCESSOR_QUESTION_IDS)
    ):
        raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    for review in reviews:
        if not isinstance(review, dict) or set(review) != {
            "fixture_id",
            "reviewed_semantics",
            "reviewed_semantics_sha256",
        }:
            raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
        semantics = review.get("reviewed_semantics")
        if (
            not isinstance(semantics, dict)
            or set(semantics)
            != {
                "evidence_spans",
                "expected",
                "fixture_class",
                "fixture_id",
                "observed",
                "rationale",
            }
            or semantics.get("fixture_id") != review.get("fixture_id")
            or review.get("reviewed_semantics_sha256")
            != sha256_bytes(canonical_json_bytes(semantics))
            or not isinstance(semantics.get("expected"), dict)
            or set(semantics["expected"])
            != {"disposition", "names", "parameter_count", "surface"}
            or not isinstance(semantics.get("observed"), dict)
            or set(semantics["observed"])
            != {"name", "status", "surfaced"}
            or not isinstance(semantics.get("evidence_spans"), list)
            or any(
                not isinstance(span, dict)
                or set(span)
                != {
                    "dimension",
                    "end_byte",
                    "source_path",
                    "source_sha256",
                    "start_byte",
                    "text",
                }
                for span in semantics["evidence_spans"]
            )
        ):
            raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    for question in questions:
        if (
            not isinstance(question, dict)
            or set(question) != _QUESTION_KEYS
            or not isinstance(question.get("expected_semantics"), dict)
            or set(question["expected_semantics"])
            != {"accepted_behavior", "rejected_behavior", "summary"}
            or not isinstance(question.get("metric_effect"), dict)
            or set(question["metric_effect"])
            != {"denominator_effect", "failure_effect", "metric"}
            or not isinstance(question.get("structural_rules"), dict)
            or set(question["structural_rules"]) != _STRUCTURAL_RULE_KEYS
            or not isinstance(question.get("machine_assertions"), list)
            or any(
                not isinstance(assertion, dict)
                or set(assertion) != {"expected", "id", "operator", "path"}
                for assertion in question["machine_assertions"]
            )
            or not isinstance(question.get("evidence"), list)
            or any(
                not isinstance(span, dict)
                or set(span)
                != {
                    "end_byte",
                    "fixture_id",
                    "source_path",
                    "source_sha256",
                    "start_byte",
                    "text",
                }
                for span in question["evidence"]
            )
        ):
            raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    if expected_questions is not None and questions != expected_questions:
        raise H1Error("H1_SUCCESSOR_PACKET_QUESTIONS_INVALID")
    if expected_reviews is not None and reviews != expected_reviews:
        raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    forbidden_human_keys = {
        "aggregate_disposition",
        "choice",
        "reviewer",
        "reviewer_identity",
        "signature",
        "timestamp",
    }

    def reject_prefill(item: object) -> None:
        if isinstance(item, dict):
            if forbidden_human_keys & set(item):
                raise H1Error("H1_HUMAN_PREFILL_FORBIDDEN")
            for nested in item.values():
                reject_prefill(nested)
        elif isinstance(item, list):
            for nested in item:
                reject_prefill(nested)

    reject_prefill({"fixture_reviews": reviews, "semantic_questions": questions})
    return value


def render_h1_semantic_markdown_v6(packet: object) -> str:
    value = _validate_successor_packet_value(packet)
    lines = [
        "# H1 Semantic Review Packet v6",
        "",
        f"- Packet SHA-256: `{value['packet_sha256']}`",
        "- External publication authorized: `false`",
        "- Human response fields: intentionally absent",
        "",
        "## Immutable bindings",
        "",
    ]
    for key in sorted(value["bindings"]):
        lines.append(f"- `{key}`: `{value['bindings'][key]}`")
    lines.extend(["", "## Seven semantic questions", ""])
    for question in value["semantic_questions"]:
        lines.extend(
            [
                f"### {question['id']}",
                "",
                question["prompt"],
                "",
                f"Expected semantics: {question['expected_semantics']['summary']}",
                f"Rationale: {question['rationale']}",
                f"Fixtures: {', '.join(question['fixture_ids'])}",
                f"Policies: {', '.join(question['policy_ids']) or 'none'}",
                "",
            ]
        )
    lines.extend(["## Fixture semantics", ""])
    for review in value["fixture_reviews"]:
        lines.extend(
            [
                f"### {review['fixture_id']}",
                "",
                f"- Reviewed-semantics SHA-256: `{review['reviewed_semantics_sha256']}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_h1_semantic_packet_v6(
    *,
    adapter_batch: Path,
    adversarial_report: Path,
    adversarial_contract: Path,
    adjudication_schema: Path,
    executable_closure: Path,
    fixture_registry: Path,
    formal_attempt: Path,
    golden_predictions: Path,
    ontology_decision: Path,
    ontology_options: Path,
    ontology_supersession: Path,
    output_json: Path,
    output_markdown: Path,
    questions: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    source_authority: Path,
    bundle_root: Path | None = None,
    preflight: bool = False,
) -> dict[str, Any]:
    """Build or dry-run the complete successor packet without human placeholders."""
    bindings, question_value, golden = _successor_bindings(
        adapter_batch=adapter_batch,
        adversarial_report=adversarial_report,
        adversarial_contract=adversarial_contract,
        adjudication_schema=adjudication_schema,
        executable_closure=executable_closure,
        fixture_registry=fixture_registry,
        formal_attempt=formal_attempt,
        golden_predictions=golden_predictions,
        ontology_decision=ontology_decision,
        ontology_options=ontology_options,
        ontology_supersession=ontology_supersession,
        questions=questions,
        rules=rules,
        semantic_contract=semantic_contract,
        schema=schema,
        source_authority=source_authority,
        bundle_root=bundle_root,
    )
    packet: dict[str, Any] = {
        "bindings": bindings,
        "external_publication_authorized": False,
        "fixture_reviews": _successor_fixture_reviews(golden),
        "schema_version": "h1-source-gold-review-v6",
        "semantic_questions": question_value["questions"],
    }
    packet["packet_sha256"] = sha256_bytes(canonical_json_bytes(packet))
    _validate_successor_packet_value(
        packet,
        expected_bindings=bindings,
        expected_questions=question_value["questions"],
        expected_reviews=_successor_fixture_reviews(golden),
    )
    markdown = render_h1_semantic_markdown_v6(packet).encode("utf-8")
    if preflight:
        if (
            output_json == output_markdown
            or output_json.parent != output_markdown.parent
            or output_json.exists()
            or output_json.is_symlink()
            or output_markdown.exists()
            or output_markdown.is_symlink()
        ):
            raise H1Error("H1_OUTPUT_EXISTS")
        return packet
    _publish_packet_pair(
        output_json=output_json,
        output_markdown=output_markdown,
        json_bytes=canonical_json_bytes(packet),
        markdown_bytes=markdown,
    )
    return packet


def validate_h1_semantic_packet_v6(
    *,
    packet: Path,
    markdown: Path,
    adapter_batch: Path,
    adversarial_report: Path,
    adversarial_contract: Path,
    adjudication_schema: Path,
    executable_closure: Path,
    fixture_registry: Path,
    formal_attempt: Path,
    golden_predictions: Path,
    ontology_decision: Path,
    ontology_options: Path,
    ontology_supersession: Path,
    questions: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    source_authority: Path,
    bundle_root: Path | None = None,
) -> dict[str, Any]:
    bindings, question_value, golden = _successor_bindings(
        adapter_batch=adapter_batch,
        adversarial_report=adversarial_report,
        adversarial_contract=adversarial_contract,
        adjudication_schema=adjudication_schema,
        executable_closure=executable_closure,
        fixture_registry=fixture_registry,
        formal_attempt=formal_attempt,
        golden_predictions=golden_predictions,
        ontology_decision=ontology_decision,
        ontology_options=ontology_options,
        ontology_supersession=ontology_supersession,
        questions=questions,
        rules=rules,
        semantic_contract=semantic_contract,
        schema=schema,
        source_authority=source_authority,
        bundle_root=bundle_root,
    )
    value, _ = _read_canonical_external(packet, "H1_SUCCESSOR_PACKET_INVALID")
    value = _validate_successor_packet_value(
        value,
        expected_bindings=bindings,
        expected_questions=question_value["questions"],
        expected_reviews=_successor_fixture_reviews(golden),
    )
    if value["semantic_questions"] != question_value["questions"] or value[
        "fixture_reviews"
    ] != _successor_fixture_reviews(golden):
        raise H1Error("H1_SUCCESSOR_PACKET_INVALID")
    try:
        _, markdown_raw = read_authoritative_file(markdown.parent, markdown.name)
    except (FilesystemPolicyError, OSError) as error:
        raise H1Error("H1_SUCCESSOR_MARKDOWN_INVALID") from error
    if markdown_raw != render_h1_semantic_markdown_v6(value).encode("utf-8"):
        raise H1Error("H1_SUCCESSOR_MARKDOWN_INVALID")
    return value


def _successor_readiness_value(bindings: dict[str, str]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bindings": bindings,
        "external_publication_authorized": False,
        "schema_version": "h1-semantic-readiness-v6",
    }
    value["readiness_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def write_h1_semantic_readiness_v6(
    *, output: Path, packet: Path, markdown: Path, preflight: bool = False, **inputs: Any
) -> dict[str, Any]:
    packet_value = validate_h1_semantic_packet_v6(
        packet=packet, markdown=markdown, **inputs
    )
    _, packet_raw = _read_canonical_external(packet, "H1_SUCCESSOR_PACKET_INVALID")
    bindings = dict(packet_value["bindings"])
    bindings["packet_file_sha256"] = sha256_bytes(packet_raw)
    value = _successor_readiness_value(bindings)
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise H1Error("H1_SUCCESSOR_READINESS_EXISTS")
    if not preflight:
        try:
            _write_exact(output, canonical_json_bytes(value))
            _sync_directory(output.parent)
        except (FileExistsError, OSError) as error:
            raise H1Error("H1_SUCCESSOR_READINESS_EXISTS") from error
    return value


def validate_h1_semantic_readiness_v6(
    *, readiness: Path, packet: Path, markdown: Path, **inputs: Any
) -> dict[str, Any]:
    packet_value = validate_h1_semantic_packet_v6(
        packet=packet, markdown=markdown, **inputs
    )
    _, packet_raw = _read_canonical_external(packet, "H1_SUCCESSOR_PACKET_INVALID")
    bindings = dict(packet_value["bindings"])
    bindings["packet_file_sha256"] = sha256_bytes(packet_raw)
    expected = _successor_readiness_value(bindings)
    value, _ = _read_canonical_external(readiness, "H1_SUCCESSOR_READINESS_INVALID")
    if value != expected:
        raise H1Error("H1_SUCCESSOR_READINESS_INVALID")
    return value


def _aggregate_disposition(values: list[str]) -> str:
    return "incomplete" if "incomplete" in values else "disputed" if "disputed" in values else "approved"


def validate_h1_semantic_review_decision(
    *, adapter_batch: Path, adversarial_report: Path, adversarial_contract: Path,
    adjudication_schema: Path, executable_closure: Path, fixture_registry: Path,
    formal_attempt: Path, golden_predictions: Path, ontology_decision: Path,
    ontology_options: Path, ontology_supersession: Path, questions: Path,
    rules: Path, semantic_contract: Path, schema: Path, source_authority: Path,
    bundle_root: Path, packet: Path, markdown: Path, readiness: Path,
    decision: Path,
) -> dict[str, Any]:
    """Validate human answers only after replaying the complete successor chain."""
    validated_readiness = validate_h1_semantic_readiness_v6(
        readiness=readiness,
        packet=packet,
        markdown=markdown,
        adapter_batch=adapter_batch,
        adversarial_report=adversarial_report,
        adversarial_contract=adversarial_contract,
        adjudication_schema=adjudication_schema,
        executable_closure=executable_closure,
        fixture_registry=fixture_registry,
        formal_attempt=formal_attempt,
        golden_predictions=golden_predictions,
        ontology_decision=ontology_decision,
        ontology_options=ontology_options,
        ontology_supersession=ontology_supersession,
        questions=questions,
        rules=rules,
        semantic_contract=semantic_contract,
        schema=schema,
        source_authority=source_authority,
        bundle_root=bundle_root,
    )
    schema_result = validate_h1_review_schema_v4(schema=schema, questions=questions)
    questions_value, _ = _read_canonical_external(
        questions, "H1_SEMANTIC_QUESTIONS_INVALID"
    )
    golden, golden_raw = _read_canonical_external(
        golden_predictions, "H1_SUCCESSOR_GOLDEN_INVALID"
    )
    if golden.get("schema_version") != "golden-predictions-v4":
        raise H1Error("H1_SUCCESSOR_GOLDEN_INVALID")
    expected_reviews = _successor_fixture_reviews(golden)
    packet_value, packet_raw = _read_canonical_external(
        packet, "H1_SUCCESSOR_PACKET_INVALID"
    )
    packet_value = _validate_successor_packet_value(
        packet_value,
        expected_questions=questions_value["questions"],
        expected_reviews=expected_reviews,
    )
    packet_bindings = packet_value["bindings"]
    validated_bindings = dict(validated_readiness["bindings"])
    validated_packet_file_sha256 = validated_bindings.pop(
        "packet_file_sha256", None
    )
    if (
        packet_bindings != validated_bindings
        or validated_packet_file_sha256 != sha256_bytes(packet_raw)
        or validated_readiness.get("schema_version")
        != "h1-semantic-readiness-v6"
        or packet_bindings.get("questions_sha256")
        != schema_result["questions_sha256"]
        or packet_bindings.get("questions_semantic_content_sha256")
        != schema_result["canonical_semantic_content_sha256"]
        or packet_bindings.get("h1_review_schema_sha256")
        != schema_result["schema_sha256"]
        or packet_bindings.get("golden_predictions_sha256")
        != sha256_bytes(golden_raw)
    ):
        raise H1Error("H1_SUCCESSOR_PACKET_BINDING_INVALID")
    readiness_value, readiness_raw = _read_canonical_external(
        readiness, "H1_SUCCESSOR_READINESS_INVALID"
    )
    expected_readiness_keys = {
        "bindings",
        "external_publication_authorized",
        "readiness_sha256",
        "schema_version",
    }
    expected_readiness_bindings = dict(packet_value["bindings"])
    expected_readiness_bindings["packet_file_sha256"] = sha256_bytes(packet_raw)
    if (
        readiness_value != validated_readiness
        or set(readiness_value) != expected_readiness_keys
        or readiness_value.get("schema_version") != "h1-semantic-readiness-v6"
        or readiness_value.get("external_publication_authorized") is not False
        or readiness_value.get("readiness_sha256")
        != sha256_bytes(
            canonical_json_bytes(
                {
                    key: item
                    for key, item in readiness_value.items()
                    if key != "readiness_sha256"
                }
            )
        )
        or readiness_value.get("bindings") != expected_readiness_bindings
    ):
        raise H1Error("H1_SUCCESSOR_READINESS_INVALID")
    value, _ = _read_canonical_external(decision, "H1_SEMANTIC_DECISION_INVALID")
    required = {
        "aggregate_disposition",
        "bindings",
        "decision_sha256",
        "external_publication_authorized",
        "fixture_reviews",
        "rationale",
        "responses",
        "reviewer_identity",
        "schema_version",
        "signature",
        "timestamp",
    }
    if (
        set(value) != required
        or value.get("schema_version") != "h1-source-gold-decision-v5"
        or value.get("external_publication_authorized") is not False
        or value.get("decision_sha256")
        != sha256_bytes(
            canonical_json_bytes(
                {
                    key: item
                    for key, item in value.items()
                    if key != "decision_sha256"
                }
            )
        )
        or not all(
            _nonempty_text(value.get(key))
            for key in ("reviewer_identity", "rationale", "signature")
        )
        or not _is_canonical_utc_timestamp(value.get("timestamp"))
    ):
        raise H1Error("H1_SEMANTIC_DECISION_INVALID")
    expected_bindings = {
        "packet_sha256": packet_value["packet_sha256"],
        "questions_sha256": schema_result["questions_sha256"],
        "readiness_sha256": readiness_value["readiness_sha256"],
        "schema_sha256": schema_result["schema_sha256"],
    }
    if value.get("bindings") != expected_bindings:
        raise H1Error("H1_SEMANTIC_DECISION_BINDING_INVALID")
    packet_reviews = {
        item["fixture_id"]: item
        for item in packet_value["fixture_reviews"]
        if isinstance(item, dict)
    }
    fixture_reviews = value.get("fixture_reviews")
    if (
        not isinstance(fixture_reviews, list)
        or [item.get("fixture_id") for item in fixture_reviews if isinstance(item, dict)]
        != list(_SUCCESSOR_FIXTURE_IDS)
    ):
        raise H1Error("H1_SEMANTIC_DECISION_FIXTURE_REVIEWS_INVALID")
    dispositions: list[str] = []
    for review in fixture_reviews:
        if not isinstance(review, dict) or set(review) != {
            "disposition",
            "fixture_id",
            "rationale",
            "reviewed_semantics_sha256",
            "signature",
        }:
            raise H1Error("H1_SEMANTIC_DECISION_FIXTURE_REVIEWS_INVALID")
        fixture_id = review.get("fixture_id")
        disposition = review.get("disposition")
        if (
            fixture_id not in packet_reviews
            or review.get("reviewed_semantics_sha256")
            != packet_reviews[fixture_id]["reviewed_semantics_sha256"]
            or disposition not in _HUMAN_DISPOSITIONS
            or not _nonempty_text(review.get("rationale"))
            or not _nonempty_text(review.get("signature"))
        ):
            raise H1Error("H1_SEMANTIC_DECISION_FIXTURE_REVIEWS_INVALID")
        dispositions.append(str(disposition))
    questions_by_id = {
        item["id"]: item
        for item in packet_value["semantic_questions"]
        if isinstance(item, dict)
    }
    responses = value.get("responses")
    if (
        not isinstance(responses, list)
        or [item.get("question_id") for item in responses if isinstance(item, dict)]
        != list(_SUCCESSOR_QUESTION_IDS)
    ):
        raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
    choice_disposition = {
        "approve_expected_semantics": "approved",
        "reject_expected_semantics": "disputed",
        "needs_revision": "incomplete",
    }
    for response in responses:
        if not isinstance(response, dict) or set(response) != {
            "disposition",
            "fixture_signoffs",
            "question_id",
            "rationale",
            "response",
        }:
            raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        question = questions_by_id.get(response.get("question_id"))
        disposition = response.get("disposition")
        choice = response.get("response")
        if (
            question is None
            or choice not in _HUMAN_RESPONSES
            or disposition != choice_disposition.get(choice)
            or not _nonempty_text(response.get("rationale"))
        ):
            raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        signoffs = response.get("fixture_signoffs")
        expected_fixture_ids = question["fixture_ids"]
        if (
            not isinstance(signoffs, list)
            or [item.get("fixture_id") for item in signoffs if isinstance(item, dict)]
            != expected_fixture_ids
        ):
            raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        for signoff in signoffs:
            if (
                not isinstance(signoff, dict)
                or set(signoff) != {"disposition", "fixture_id", "signature"}
                or signoff.get("disposition") != disposition
                or not _nonempty_text(signoff.get("signature"))
            ):
                raise H1Error("H1_SEMANTIC_RESPONSES_INVALID")
        dispositions.append(str(disposition))
    aggregate = _aggregate_disposition(dispositions)
    if value.get("aggregate_disposition") != aggregate:
        raise H1Error("H1_DISPUTE_AGGREGATION_INVALID")
    return {
        "aggregate_disposition": aggregate,
        "decision_sha256": value["decision_sha256"],
        "external_publication_authorized": False,
        "fixture_count": 11,
        "questions": 7,
        "readiness_file_sha256": sha256_bytes(readiness_raw),
        "valid": True,
    }
