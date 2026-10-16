# SPDX-License-Identifier: BSD-3-Clause-Clear
"""No-replace rendering for successor reports from frozen canonical inputs."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from specchoice_evidence.bundle import _sync_directory, _write_exact
from specchoice_evidence.canonical import canonical_json_bytes, require_sha256, sha256_bytes
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    read_authoritative_file,
    require_relative_posix_path,
    write_new_descriptor_file,
)
from specchoice_evidence.publication import (
    PublicationContractError,
    resolve_historical_path,
)


class FinalReportError(ValueError):
    """Stable failure for a stale report input or incomplete evidence set."""


_LEGACY_PLANNING = "." + "planning/"


def _read_historical_input(root: Path, relative: str):
    try:
        return read_authoritative_file(
            root, resolve_historical_path(root, relative)
        )
    except PublicationContractError as error:
        raise FilesystemPolicyError("HISTORICAL_INPUT_INVALID") from error


FINAL_SUCCESSOR_TARGETS_02_22 = (
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION-02-22.md",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW-02-22.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION-02-22.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW-02-22.md",
)
FINAL_SUCCESSOR_SUMMARY_02_22 = (
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-22-SUMMARY.md"
)
_FINAL_02_22_ROLES = (
    "phase1_verification",
    "phase1_review",
    "phase2_verification",
    "phase2_review",
)
_FINAL_02_22_INPUT_PATHS = {
    "requirements": _LEGACY_PLANNING + "REQUIREMENTS.md",
    "roadmap": _LEGACY_PLANNING + "ROADMAP.md",
    "phase1_predecessor_review": _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW.md",
    "phase1_predecessor_verification": _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION.md",
    "phase2_predecessor_review": _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW.md",
    "phase2_predecessor_verification": _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION.md",
}


def validate_v4_terminal_report_inputs(*, decision: object, packet: object, readiness: object, runtime_closure: object, authority_path: Path) -> dict[str, object]:
    """A terminal report is eligible only for a complete approved v6 decision."""
    from .h1 import validate_approved_h1_terminal_v6

    return validate_approved_h1_terminal_v6(
        decision=decision, packet=packet, readiness=readiness,
        runtime_closure=runtime_closure, authority_path=authority_path,
    )


def _validate_final_02_22_input_bindings(
    root: Path, bindings: object
) -> dict[str, dict[str, object]]:
    """Re-read the fixed planning/predecessor inventory and match every record."""
    if not isinstance(bindings, Mapping) or set(bindings) != set(_FINAL_02_22_INPUT_PATHS):
        raise FinalReportError("FINAL_02_22_BINDING_INVENTORY_INVALID")
    normalized: dict[str, dict[str, object]] = {}
    for role in sorted(_FINAL_02_22_INPUT_PATHS):
        record = bindings.get(role)
        if not isinstance(record, Mapping) or set(record) != {"byte_length", "path", "sha256"}:
            raise FinalReportError("FINAL_02_22_BINDING_INVALID")
        expected_path = _FINAL_02_22_INPUT_PATHS[role]
        length = record.get("byte_length")
        try:
            digest = require_sha256(record.get("sha256"))
            evidence, raw = _read_historical_input(root, expected_path)
        except (FilesystemPolicyError, OSError, ValueError) as error:
            raise FinalReportError("FINAL_02_22_BINDING_INVALID") from error
        actual = {"byte_length": len(raw), "path": expected_path, "sha256": sha256_bytes(raw)}
        if (
            evidence.file_kind != "regular_file"
            or isinstance(length, bool)
            or not isinstance(length, int)
            or digest == "0" * 64
            or dict(record) != actual
        ):
            raise FinalReportError("FINAL_02_22_INPUT_DRIFT")
        normalized[role] = actual
    return normalized


def build_final_02_22_input_bindings(root: Path) -> dict[str, dict[str, object]]:
    """Capture the current fixed planning inputs for writer/validator preflight."""
    result: dict[str, dict[str, object]] = {}
    for role in sorted(_FINAL_02_22_INPUT_PATHS):
        path = _FINAL_02_22_INPUT_PATHS[role]
        try:
            evidence, raw = _read_historical_input(root, path)
        except (FilesystemPolicyError, OSError) as error:
            raise FinalReportError("FINAL_02_22_BINDING_INVALID") from error
        if evidence.file_kind != "regular_file":
            raise FinalReportError("FINAL_02_22_BINDING_INVALID")
        result[role] = {"byte_length": len(raw), "path": path, "sha256": sha256_bytes(raw)}
    return result


def validate_final_report_inputs(root: Path, bindings: object, receipts: object, *, human_disposition: str) -> None:
    """Reject report creation unless all hash-bound inputs and human evidence are complete."""
    if human_disposition != "approved" or not isinstance(bindings, Mapping) or not isinstance(receipts, Mapping):
        raise FinalReportError("FINAL_REPORT_NOT_APPROVED")
    if not bindings or not receipts or any(value is not True for value in receipts.values()):
        raise FinalReportError("FINAL_REPORT_RECEIPTS_INCOMPLETE")
    for path, digest in bindings.items():
        if not isinstance(path, str):
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
        try:
            expected = require_sha256(digest)
            current = (root / path).read_bytes()
        except (OSError, ValueError) as error:
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID") from error
        if sha256_bytes(current) != expected:
            raise FinalReportError("FINAL_REPORT_INPUT_DRIFT")


def write_successor_reports(
    root: Path, bindings: object, receipts: object, *, human_disposition: str, reports: Mapping[str, Mapping[str, object]],
) -> dict[str, str]:
    """Write a finite, deterministic report batch only after all inputs have validated."""
    validate_final_report_inputs(root, bindings, receipts, human_disposition=human_disposition)
    if len(reports) != 4 or list(reports) != sorted(reports):
        raise FinalReportError("FINAL_REPORT_SET_INVALID")
    payloads: dict[str, bytes] = {}
    for path, report in reports.items():
        if not isinstance(path, str) or not isinstance(report, Mapping):
            raise FinalReportError("FINAL_REPORT_SET_INVALID")
        payloads[path] = canonical_json_bytes(dict(report))
    for path in payloads:
        target = root / path
        write_new_descriptor_file(target.parent, target.name, payloads[path])
    return {path: sha256_bytes(payloads[path]) for path in sorted(payloads)}


FINAL_SUCCESSOR_TARGETS = (
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION-02-19.md",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW-02-19.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION-02-19.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW-02-19.md",
)
_FINAL_REPORT_ROLES = (
    "phase1_verification",
    "phase1_review",
    "phase2_verification",
    "phase2_review",
)
_FINAL_BINDING_ROLES = (
    "roadmap",
    "requirements",
    "phase1_predecessor_verification",
    "phase1_predecessor_review",
    "phase2_predecessor_verification",
    "phase2_predecessor_review",
    "executable_closure",
    "source_authority",
    "integrity_receipt",
    "golden_predictions",
    "formal_attempt",
    "formal_case_outcomes",
    "formal_metrics",
    "adversarial_report",
    "h1_questions",
    "h1_schema",
    "h1_packet",
    "h1_readiness",
    "h1_decision",
)
_CANONICAL_JSON_BINDINGS = frozenset(
    {
        "executable_closure",
        "source_authority",
        "integrity_receipt",
        "golden_predictions",
        "formal_attempt",
        "formal_case_outcomes",
        "formal_metrics",
        "adversarial_report",
        "h1_questions",
        "h1_schema",
        "h1_packet",
        "h1_readiness",
        "h1_decision",
    }
)
_COMMIT_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _canonical_successor_h1_inputs(root: Path) -> dict[str, Path]:
    """Return the one fixed successor chain that may authorize final reports."""
    experiment = root / "experiments/specchoice-v1.3.2"
    formal = experiment / "runs/measurement-attempts/formal-golden-pr2164-v5"
    review = experiment / "reports/h1/h1-source-gold-review-v6"
    return {
        "adapter_batch": experiment / "reports/h1/adapter-batch-pr2164-v5.json",
        "adversarial_report": experiment / "reports/h1/adversarial-oracle-results-v6.json",
        "adversarial_contract": experiment
        / "fixtures/measurement/adversarial/required-diagnostics-v4.json",
        "adjudication_schema": experiment
        / "config/measurement/canonical-adjudication-schema-v3.json",
        "executable_closure": experiment
        / "receipts/runtime-executable-closure-v3.json",
        "fixture_registry": experiment / "config/fixture-registry-pr2164-v6.json",
        "formal_attempt": formal,
        "golden_predictions": experiment
        / "fixtures/measurement/golden-predictions-v4.json",
        "ontology_decision": experiment
        / "reviews/h1-source-gold-ontology-decision-v1.json",
        "ontology_options": experiment
        / "config/measurement/h1-ontology-policy-options-v1.json",
        "ontology_supersession": experiment
        / "receipts/h1-review-route-supersession-v1.json",
        "questions": experiment
        / "config/measurement/h1-semantic-review-questions-v2.json",
        "rules": experiment / "config/measurement/pr2164-adapter-rules-v3.json",
        "semantic_contract": experiment
        / "config/measurement/pr2164-semantic-gold-contract-v2.json",
        "schema": experiment / "config/measurement/h1-review-schema-v4.json",
        "source_authority": experiment / "phase2/source-authority.json",
        "bundle_root": experiment
        / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3",
        "packet": review / "h1-source-gold-review-v6.json",
        "markdown": review / "h1-source-gold-review-v6.md",
        "readiness": experiment / "receipts/h1-review-readiness-v6.json",
        "decision": experiment / "reviews/h1-source-gold-decision-v5.json",
    }


def _canonical_final_binding_paths(root: Path) -> dict[str, Path]:
    inputs = _canonical_successor_h1_inputs(root)
    formal = inputs["formal_attempt"]
    return {
        "roadmap": root / (_LEGACY_PLANNING + "ROADMAP.md"),
        "requirements": root / (_LEGACY_PLANNING + "REQUIREMENTS.md"),
        "phase1_predecessor_verification": root
        / (_LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION.md"),
        "phase1_predecessor_review": root
        / (_LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW.md"),
        "phase2_predecessor_verification": root
        / (_LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION.md"),
        "phase2_predecessor_review": root
        / (_LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW.md"),
        "executable_closure": inputs["executable_closure"],
        "source_authority": inputs["source_authority"],
        "integrity_receipt": root
        / "experiments/specchoice-v1.3.2/receipts/integrity-receipt-v14.json",
        "golden_predictions": inputs["golden_predictions"],
        "formal_attempt": formal / "attempt.json",
        "formal_case_outcomes": formal / "case-outcomes.json",
        "formal_metrics": formal / "metrics.json",
        "adversarial_report": inputs["adversarial_report"],
        "h1_questions": inputs["questions"],
        "h1_schema": inputs["schema"],
        "h1_packet": inputs["packet"],
        "h1_readiness": inputs["readiness"],
        "h1_decision": inputs["decision"],
    }


def _canonical_input(root: Path, path: str, code: str) -> tuple[object, bytes]:
    try:
        relative = require_relative_posix_path(path).as_posix()
        evidence, raw = _read_historical_input(root, relative)
        if evidence.file_kind != "regular_file":
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        value = json.loads(raw.decode("utf-8"))
    except (
        FilesystemPolicyError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise FinalReportError(code) from error
    if canonical_json_bytes(value) != raw:
        raise FinalReportError(code)
    return value, raw


def _bound_input_bytes(root: Path, record: Mapping[str, object]) -> bytes:
    if set(record) != {"byte_length", "path", "role", "sha256"}:
        raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
    role, path = record.get("role"), record.get("path")
    if not isinstance(role, str) or not isinstance(path, str):
        raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
    try:
        expected_sha = require_sha256(record.get("sha256"))
        expected_length = record.get("byte_length")
        if isinstance(expected_length, bool) or not isinstance(expected_length, int) or expected_length < 0:
            raise ValueError("invalid byte length")
        relative = require_relative_posix_path(path).as_posix()
        evidence, raw = _read_historical_input(root, relative)
    except (FilesystemPolicyError, OSError, ValueError) as error:
        raise FinalReportError("FINAL_REPORT_BINDING_INVALID") from error
    if (
        evidence.file_kind != "regular_file"
        or len(raw) != expected_length
        or sha256_bytes(raw) != expected_sha
    ):
        raise FinalReportError("FINAL_REPORT_INPUT_DRIFT")
    if role in _CANONICAL_JSON_BINDINGS:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FinalReportError("FINAL_REPORT_CANONICAL_INPUT_INVALID") from error
        if canonical_json_bytes(value) != raw:
            raise FinalReportError("FINAL_REPORT_CANONICAL_INPUT_INVALID")
    return raw


def _validate_final_binding_set(
    root: Path, bindings: object
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    if not isinstance(bindings, list):
        raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
    records: list[dict[str, object]] = []
    values: dict[str, bytes] = {}
    for item in bindings:
        if not isinstance(item, Mapping):
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
        record = dict(item)
        role = record.get("role")
        if not isinstance(role, str) or role in values:
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
        values[role] = _bound_input_bytes(root, record)
        records.append(record)
    if tuple(record["role"] for record in records) != _FINAL_BINDING_ROLES:
        raise FinalReportError("FINAL_REPORT_BINDING_INVENTORY_INVALID")
    return records, values


def _formal_semantics(values: Mapping[str, bytes]) -> dict[str, object]:
    try:
        manifest = json.loads(values["formal_attempt"])
        case_outcomes = json.loads(values["formal_case_outcomes"])
        metrics = json.loads(values["formal_metrics"])
        golden = json.loads(values["golden_predictions"])
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise FinalReportError("FINAL_REPORT_FORMAL_INVALID") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("role") != "formal"
        or manifest.get("status") != "completed"
        or manifest.get("attempt_sha256")
        != sha256_bytes(
            canonical_json_bytes(
                {key: item for key, item in manifest.items() if key != "attempt_sha256"}
            )
        )
        or not isinstance(manifest.get("artifacts"), dict)
        or not isinstance(case_outcomes, list)
        or len(case_outcomes) != 11
        or not isinstance(metrics, dict)
        or not isinstance(golden, dict)
    ):
        raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
    for artifact_name, role in (
        ("case-outcomes.json", "formal_case_outcomes"),
        ("metrics.json", "formal_metrics"),
    ):
        identity = manifest["artifacts"].get(artifact_name)
        raw = values[role]
        if identity != {"byte_length": len(raw), "sha256": sha256_bytes(raw)}:
            raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
    required_metrics = {
        "surfacing": {"denominator": 8, "numerator": 8},
        "disposition": {"denominator": 8, "numerator": 8},
        "identity": {"denominator": 6, "numerator": 6},
    }
    if any(metrics.get(name) != expected for name, expected in required_metrics.items()):
        raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
    span_count = golden.get("score_bearing_span_count")
    evidence = metrics.get("evidence_integrity")
    if (
        isinstance(span_count, bool)
        or not isinstance(span_count, int)
        or span_count <= 0
        or evidence != {"denominator": span_count, "numerator": span_count}
    ):
        raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
    negative_ids = {
        "NEG_FIXED_ENCODING",
        "NEG_SHALL_NO_DELEGATION",
        "NEG_SOFTWARE_ADVICE",
    }
    negative_passes = 0
    for outcome in case_outcomes:
        if not isinstance(outcome, dict):
            raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
        if outcome.get("fixture_id") in negative_ids and outcome.get("actual_surfaced") is False:
            negative_passes += 1
    if negative_passes != 3:
        raise FinalReportError("FINAL_REPORT_FORMAL_INVALID")
    return {
        "case_count": 11,
        "evidence_span_population": span_count,
        "metrics": metrics,
        "negative_no_surface": {"denominator": 3, "numerator": 3},
    }


def _adversarial_semantics(values: Mapping[str, bytes]) -> dict[str, object]:
    try:
        report = json.loads(values["adversarial_report"])
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise FinalReportError("FINAL_REPORT_ADVERSARIAL_INVALID") from error
    cases = report.get("cases") if isinstance(report, dict) else None
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != "adversarial-oracle-results-v6"
        or report.get("status") != "diagnostic_only"
        or not isinstance(cases, list)
        or not cases
        or any(
            not isinstance(case, dict)
            or case.get("matched") is not True
            or case.get("metric_output_allowed") is not False
            for case in cases
        )
    ):
        raise FinalReportError("FINAL_REPORT_ADVERSARIAL_INVALID")
    return {"case_count": len(cases), "matched": len(cases), "status": "diagnostic_only"}


def _decision_semantics(root: Path, records: list[dict[str, object]], values: Mapping[str, bytes]) -> dict[str, object]:
    by_role = {str(item["role"]): str(item["path"]) for item in records}
    expected_paths = _canonical_final_binding_paths(root)
    try:
        supplied_paths = {
            role: root / require_relative_posix_path(by_role[role])
            for role in expected_paths
        }
    except (FilesystemPolicyError, KeyError, ValueError) as error:
        raise FinalReportError("FINAL_REPORT_BINDING_INVENTORY_INVALID") from error
    if any(
        supplied_paths[role].absolute() != expected.absolute()
        for role, expected in expected_paths.items()
    ):
        raise FinalReportError("FINAL_REPORT_BINDING_INVENTORY_INVALID")
    try:
        from .h1 import validate_h1_semantic_review_decision

        receipt = validate_h1_semantic_review_decision(
            **_canonical_successor_h1_inputs(root)
        )
        decision = json.loads(values["h1_decision"])
    except (
        FilesystemPolicyError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as error:
        raise FinalReportError("FINAL_REPORT_H1_DECISION_INVALID") from error
    responses = decision.get("responses")
    if not isinstance(responses, list):
        raise FinalReportError("FINAL_REPORT_H1_DECISION_INVALID")
    open_ids = [
        response.get("question_id")
        for response in responses
        if isinstance(response, dict) and response.get("disposition") != "approved"
    ]
    if any(not isinstance(identifier, str) for identifier in open_ids):
        raise FinalReportError("FINAL_REPORT_H1_DECISION_INVALID")
    return {
        "aggregate_disposition": receipt["aggregate_disposition"],
        "open_semantic_ids": open_ids,
        "question_count": receipt["questions"],
    }


def _final_evidence(
    root: Path, bindings: object, *, audited_commit: str
) -> dict[str, object]:
    if _COMMIT_RE.fullmatch(audited_commit) is None:
        raise FinalReportError("FINAL_REPORT_AUDITED_COMMIT_INVALID")
    records, values = _validate_final_binding_set(root, bindings)
    decision = _decision_semantics(root, records, values)
    formal = _formal_semantics(values)
    adversarial = _adversarial_semantics(values)
    return {
        "adversarial": adversarial,
        "audited_commit": audited_commit,
        "bindings": records,
        "decision": decision,
        "external_publication_authorized": False,
        "formal": formal,
        "schema_version": "final-successor-evidence-v1",
    }


def _report_status(role: str, evidence: Mapping[str, object]) -> str:
    if role.startswith("phase1_"):
        return "verified"
    decision = evidence.get("decision")
    return (
        "verified"
        if isinstance(decision, Mapping)
        and decision.get("aggregate_disposition") == "approved"
        else "gaps_found"
    )


def _render_final_report(role: str, evidence: Mapping[str, object]) -> bytes:
    if role not in _FINAL_REPORT_ROLES:
        raise FinalReportError("FINAL_REPORT_SET_INVALID")
    titles = {
        "phase1_verification": "Phase 1 Verification Successor 02-19",
        "phase1_review": "Phase 1 Review Successor 02-19",
        "phase2_verification": "Phase 2 Verification Successor 02-19",
        "phase2_review": "Phase 2 Review Successor 02-19",
    }
    status = _report_status(role, evidence)
    binding_sha = sha256_bytes(canonical_json_bytes(evidence["bindings"]))
    header = {
        "audited_commit": evidence["audited_commit"],
        "binding_set_sha256": binding_sha,
        "external_publication_authorized": False,
        "report_role": role,
        "schema_version": "final-successor-report-v1",
        "status": status,
    }
    lines = ["---"]
    lines.extend(
        f"{key}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for key, value in sorted(header.items())
    )
    lines.extend(
        [
            "---",
            "",
            f"# {titles[role]}",
            "",
            f"Status: `{status}`.",
            "",
            "This report is a deterministic projection of the canonical evidence below; prose is not authority.",
            "",
            "## Canonical evidence",
            "",
            "```json",
            canonical_json_bytes(dict(evidence)).decode("utf-8").rstrip("\n"),
            "```",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _validate_target_inventory(root: Path, targets: object) -> tuple[Path, ...]:
    if not isinstance(targets, (list, tuple)) or tuple(targets) != FINAL_SUCCESSOR_TARGETS:
        raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID")
    resolved: list[Path] = []
    for relative in targets:
        if not isinstance(relative, str):
            raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID")
        try:
            normalized = require_relative_posix_path(relative).as_posix()
        except (FilesystemPolicyError, ValueError) as error:
            raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID") from error
        target = root / normalized
        if (
            not target.parent.is_dir()
            or target.parent.is_symlink()
            or target.exists()
            or target.is_symlink()
        ):
            raise FinalReportError("FINAL_REPORT_TARGET_COLLISION")
        resolved.append(target)
    return tuple(resolved)


def _link_no_replace(source: Path, target: Path) -> None:
    os.link(source, target, follow_symlinks=False)


def write_final_successor_reports(
    root: Path,
    *,
    audited_commit: str,
    bindings: object,
    targets: object = FINAL_SUCCESSOR_TARGETS,
    preflight: bool = False,
) -> dict[str, object]:
    """Validate every input/collision, then link four staged files with cleanup on races."""
    evidence = _final_evidence(root, bindings, audited_commit=audited_commit)
    target_paths = _validate_target_inventory(root, targets)
    payloads = {
        relative: _render_final_report(role, evidence)
        for relative, role in zip(FINAL_SUCCESSOR_TARGETS, _FINAL_REPORT_ROLES, strict=True)
    }
    result = {
        "audited_commit": audited_commit,
        "report_sha256": {
            relative: sha256_bytes(payloads[relative]) for relative in FINAL_SUCCESSOR_TARGETS
        },
        "status": "preflight_valid" if preflight else "written",
    }
    if preflight:
        return result
    staging = Path(tempfile.mkdtemp(prefix=".final-successor-reports-", dir=root))
    created: list[tuple[Path, tuple[int, int]]] = []
    try:
        staged: list[Path] = []
        for index, relative in enumerate(FINAL_SUCCESSOR_TARGETS):
            path = staging / f"{index:02d}.md"
            _write_exact(path, payloads[relative])
            staged.append(path)
        _sync_directory(staging)
        for source, target in zip(staged, target_paths, strict=True):
            identity = os.stat(source, follow_symlinks=False)
            _link_no_replace(source, target)
            created.append((target, (identity.st_dev, identity.st_ino)))
        for parent in sorted({target.parent for target in target_paths}, key=str):
            _sync_directory(parent)
    except Exception as error:
        for target, identity in reversed(created):
            try:
                observed = os.stat(target, follow_symlinks=False)
                if (observed.st_dev, observed.st_ino) == identity:
                    target.unlink()
            except FileNotFoundError:
                pass
        for parent in sorted({target.parent for target, _ in created}, key=str):
            try:
                _sync_directory(parent)
            except OSError:
                pass
        raise FinalReportError("FINAL_REPORT_ATOMIC_PUBLISH_FAILED") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return result


def _parse_final_report(raw: bytes) -> tuple[dict[str, object], dict[str, object]]:
    try:
        text = raw.decode("utf-8")
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            raise ValueError("missing frontmatter")
        end = lines.index("---", 1)
        header: dict[str, object] = {}
        for line in lines[1:end]:
            key, separator, encoded = line.partition(": ")
            if not separator or key in header:
                raise ValueError("invalid frontmatter")
            header[key] = json.loads(encoded)
        marker = lines.index("```json", end + 1)
        closing = lines.index("```", marker + 1)
        if closing != marker + 2:
            raise ValueError("invalid evidence block")
        evidence_raw = (lines[marker + 1] + "\n").encode("utf-8")
        evidence = json.loads(evidence_raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise FinalReportError("FINAL_REPORT_INVALID") from error
    if not isinstance(evidence, dict) or canonical_json_bytes(evidence) != evidence_raw:
        raise FinalReportError("FINAL_REPORT_INVALID")
    return header, evidence


def verify_final_successor_reports(root: Path, *, targets: object) -> dict[str, object]:
    """Recompute all four projections and every embedded current-byte binding."""
    if not isinstance(targets, (list, tuple)) or tuple(targets) != FINAL_SUCCESSOR_TARGETS:
        raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID")
    parsed: list[tuple[bytes, dict[str, object], dict[str, object]]] = []
    for relative in FINAL_SUCCESSOR_TARGETS:
        try:
            evidence, raw = _read_historical_input(root, relative)
        except (FilesystemPolicyError, OSError) as error:
            raise FinalReportError("FINAL_REPORT_INVALID") from error
        if evidence.file_kind != "regular_file":
            raise FinalReportError("FINAL_REPORT_INVALID")
        header, projection = _parse_final_report(raw)
        parsed.append((raw, header, projection))
    canonical_evidence = parsed[0][2]
    if any(item[2] != canonical_evidence for item in parsed[1:]):
        raise FinalReportError("FINAL_REPORT_EVIDENCE_MISMATCH")
    audited_commit = canonical_evidence.get("audited_commit")
    bindings = canonical_evidence.get("bindings")
    if not isinstance(audited_commit, str):
        raise FinalReportError("FINAL_REPORT_AUDITED_COMMIT_INVALID")
    expected_evidence = _final_evidence(root, bindings, audited_commit=audited_commit)
    if canonical_evidence != expected_evidence:
        raise FinalReportError("FINAL_REPORT_EVIDENCE_MISMATCH")
    hashes: dict[str, str] = {}
    for relative, role, (raw, header, _) in zip(
        FINAL_SUCCESSOR_TARGETS, _FINAL_REPORT_ROLES, parsed, strict=True
    ):
        expected = _render_final_report(role, expected_evidence)
        if raw != expected or header.get("report_role") != role:
            raise FinalReportError("FINAL_REPORT_INVALID")
        hashes[relative] = sha256_bytes(raw)
    return {
        "audited_commit": audited_commit,
        "report_sha256": hashes,
        "status": "verified",
    }


def _final_02_22_evidence(
    root: Path,
    *,
    decision: object,
    packet: object,
    readiness: object,
    runtime_closure: object,
    authority_path: Path,
    input_bindings: object,
) -> dict[str, object]:
    validated_decision = validate_v4_terminal_report_inputs(
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    planning = _validate_final_02_22_input_bindings(root, input_bindings)
    if not isinstance(packet, Mapping) or not isinstance(readiness, Mapping):
        raise FinalReportError("FINAL_02_22_H1_INVALID")
    source_identity = packet.get("source_identity")
    if not isinstance(source_identity, Mapping) or readiness.get("source_identity") != source_identity:
        raise FinalReportError("FINAL_02_22_H1_INVALID")
    return {
        "decision_sha256": validated_decision["decision_sha256"],
        "external_publication_authorized": False,
        "input_bindings": planning,
        "packet_sha256": packet.get("packet_sha256"),
        "readiness_sha256": readiness.get("readiness_sha256"),
        "schema_version": "final-successor-evidence-02-22-v1",
        "source_identity": dict(source_identity),
    }


def _render_final_02_22_report(role: str, evidence: Mapping[str, object]) -> bytes:
    if role not in _FINAL_02_22_ROLES:
        raise FinalReportError("FINAL_02_22_TARGET_INVENTORY_INVALID")
    title = {
        "phase1_verification": "Phase 1 Verification Successor 02-22",
        "phase1_review": "Phase 1 Review Successor 02-22",
        "phase2_verification": "Phase 2 Verification Successor 02-22",
        "phase2_review": "Phase 2 Review Successor 02-22",
    }[role]
    lines = [
        "---",
        f"report_role: {json.dumps(role)}",
        'schema_version: "final-successor-report-02-22-v1"',
        'status: "approved"',
        "---",
        "",
        f"# {title}",
        "",
        "Status: `approved`.",
        "",
        "This report is a deterministic projection of the approved canonical evidence.",
        "",
        "```json",
        canonical_json_bytes(dict(evidence)).decode("utf-8").rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _read_optional_exact(root: Path, relative: str) -> bytes | None:
    try:
        _, raw = read_authoritative_file(root, relative)
        return raw
    except FilesystemPolicyError as error:
        if str(error) == "AUTHORITATIVE_FILE_MISSING":
            return None
        raise FinalReportError("FINAL_02_22_TARGET_INVALID") from error
    except OSError as error:
        raise FinalReportError("FINAL_02_22_TARGET_INVALID") from error


def _write_final_02_22_exact_resume(
    root: Path,
    relative: str,
    raw: bytes,
    *,
    preflight_status: str,
) -> str:
    """Enter only the no-replace primitive after the caller's final gate."""
    if preflight_status not in {"written", "resumed"}:
        raise FinalReportError("FINAL_02_22_TARGET_INVALID")
    if preflight_status == "resumed":
        return "resumed"
    try:
        write_new_descriptor_file(root, relative, raw)
        return "written"
    except FilesystemPolicyError as error:
        if str(error) != "AUTHORITATIVE_DESTINATION_EXISTS":
            raise FinalReportError("FINAL_02_22_TARGET_INVALID") from error
    existing = _read_optional_exact(root, relative)
    if existing != raw:
        raise FinalReportError("FINAL_02_22_TARGET_DIVERGED")
    return "resumed"


def write_final_successor_reports_02_22(
    root: Path,
    *,
    decision: object,
    packet: object,
    readiness: object,
    runtime_closure: object,
    authority_path: Path,
    input_bindings: object,
    targets: object = FINAL_SUCCESSOR_TARGETS_02_22,
    preflight: bool = False,
) -> dict[str, object]:
    """Write the fixed four approved reports with no-replace exact resume."""
    if not isinstance(targets, (list, tuple)) or tuple(targets) != FINAL_SUCCESSOR_TARGETS_02_22:
        raise FinalReportError("FINAL_02_22_TARGET_INVENTORY_INVALID")
    evidence = _final_02_22_evidence(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    )
    payloads = {
        relative: _render_final_02_22_report(role, evidence)
        for relative, role in zip(FINAL_SUCCESSOR_TARGETS_02_22, _FINAL_02_22_ROLES, strict=True)
    }
    preflight_statuses: dict[str, str] = {}
    for relative, raw in payloads.items():
        existing = _read_optional_exact(root, relative)
        if existing is not None and existing != raw:
            raise FinalReportError("FINAL_02_22_TARGET_DIVERGED")
        preflight_statuses[relative] = (
            "resumed" if existing is not None else "written"
        )
    if preflight:
        return {
            "report_sha256": {path: sha256_bytes(raw) for path, raw in payloads.items()},
            "status": "preflight_valid",
        }
    # Revalidate the approval and all source bytes immediately before first write.
    if _final_02_22_evidence(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    ) != evidence:
        raise FinalReportError("FINAL_02_22_PREWRITE_DRIFT")
    statuses = {
        relative: _write_final_02_22_exact_resume(
            root,
            relative,
            payloads[relative],
            preflight_status=preflight_statuses[relative],
        )
        for relative in FINAL_SUCCESSOR_TARGETS_02_22
    }
    postflight = verify_final_successor_reports_02_22(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    )
    if postflight["report_sha256"] != {
        path: sha256_bytes(raw) for path, raw in payloads.items()
    }:
        raise FinalReportError("FINAL_02_22_POSTWRITE_DRIFT")
    return {
        "report_sha256": {path: sha256_bytes(raw) for path, raw in payloads.items()},
        "status": "resumed" if all(value == "resumed" for value in statuses.values()) else "written",
    }


def verify_final_successor_reports_02_22(
    root: Path,
    *,
    decision: object,
    packet: object,
    readiness: object,
    runtime_closure: object,
    authority_path: Path,
    input_bindings: object,
    targets: object = FINAL_SUCCESSOR_TARGETS_02_22,
) -> dict[str, object]:
    """Re-render and byte-verify exactly the four fixed 02-22 reports."""
    if not isinstance(targets, (list, tuple)) or tuple(targets) != FINAL_SUCCESSOR_TARGETS_02_22:
        raise FinalReportError("FINAL_02_22_TARGET_INVENTORY_INVALID")
    evidence = _final_02_22_evidence(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    )
    hashes: dict[str, str] = {}
    for relative, role in zip(FINAL_SUCCESSOR_TARGETS_02_22, _FINAL_02_22_ROLES, strict=True):
        expected = _render_final_02_22_report(role, evidence)
        observed = _read_optional_exact(root, relative)
        if observed != expected:
            raise FinalReportError("FINAL_02_22_REPORT_INVALID")
        hashes[relative] = sha256_bytes(expected)
    return {"report_sha256": hashes, "status": "verified"}


def _render_final_02_22_summary(
    *, decision_sha256: str, report_sha256: Mapping[str, str]
) -> bytes:
    payload = {
        "decision_sha256": decision_sha256,
        "external_publication_authorized": False,
        "reports": [
            {"path": path, "sha256": report_sha256[path]}
            for path in FINAL_SUCCESSOR_TARGETS_02_22
        ],
        "schema_version": "final-successor-summary-02-22-v1",
        "status": "approved",
    }
    return (
        "# Phase 2 Successor Summary 02-22\n\n"
        "```json\n"
        + canonical_json_bytes(payload).decode("utf-8").rstrip("\n")
        + "\n```\n"
    ).encode("utf-8")


def write_final_successor_summary_02_22(
    root: Path,
    *,
    decision: object,
    packet: object,
    readiness: object,
    runtime_closure: object,
    authority_path: Path,
    input_bindings: object,
    output: str = FINAL_SUCCESSOR_SUMMARY_02_22,
    preflight: bool = False,
) -> dict[str, object]:
    """Write the summary only after exact verification of all four reports."""
    if output != FINAL_SUCCESSOR_SUMMARY_02_22:
        raise FinalReportError("FINAL_02_22_SUMMARY_PATH_INVALID")
    verified = verify_final_successor_reports_02_22(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    )
    if not isinstance(decision, Mapping) or not isinstance(decision.get("decision_sha256"), str):
        raise FinalReportError("FINAL_02_22_H1_INVALID")
    raw = _render_final_02_22_summary(
        decision_sha256=decision["decision_sha256"],
        report_sha256=verified["report_sha256"],
    )
    existing = _read_optional_exact(root, output)
    if existing is not None and existing != raw:
        raise FinalReportError("FINAL_02_22_TARGET_DIVERGED")
    preflight_status = "resumed" if existing is not None else "written"
    if preflight:
        status = "preflight_valid"
    else:
        # Re-run the complete approved-report gate immediately before the
        # no-replace summary write; the first pass is only used to render bytes.
        repeated = verify_final_successor_reports_02_22(
            root,
            decision=decision,
            packet=packet,
            readiness=readiness,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
            input_bindings=input_bindings,
        )
        if repeated != verified:
            raise FinalReportError("FINAL_02_22_PREWRITE_DRIFT")
        status = _write_final_02_22_exact_resume(
            root, output, raw, preflight_status=preflight_status
        )
        postflight = validate_final_successor_summary_02_22(
            root,
            decision=decision,
            packet=packet,
            readiness=readiness,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
            input_bindings=input_bindings,
            summary=output,
        )
        if postflight.get("sha256") != sha256_bytes(raw):
            raise FinalReportError("FINAL_02_22_POSTWRITE_DRIFT")
    return {"sha256": sha256_bytes(raw), "status": status}


def validate_final_successor_summary_02_22(
    root: Path,
    *,
    decision: object,
    packet: object,
    readiness: object,
    runtime_closure: object,
    authority_path: Path,
    input_bindings: object,
    summary: str = FINAL_SUCCESSOR_SUMMARY_02_22,
) -> dict[str, object]:
    """Read-only post-generation verification of reports and terminal summary."""
    if summary != FINAL_SUCCESSOR_SUMMARY_02_22:
        raise FinalReportError("FINAL_02_22_SUMMARY_PATH_INVALID")
    verified = verify_final_successor_reports_02_22(
        root,
        decision=decision,
        packet=packet,
        readiness=readiness,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        input_bindings=input_bindings,
    )
    if not isinstance(decision, Mapping) or not isinstance(decision.get("decision_sha256"), str):
        raise FinalReportError("FINAL_02_22_H1_INVALID")
    expected = _render_final_02_22_summary(
        decision_sha256=decision["decision_sha256"],
        report_sha256=verified["report_sha256"],
    )
    if _read_optional_exact(root, summary) != expected:
        raise FinalReportError("FINAL_02_22_SUMMARY_INVALID")
    return {"sha256": sha256_bytes(expected), "status": "verified"}


# Explicit version aliases for callers that key interfaces by closure generation.
write_final_successor_reports_v4 = write_final_successor_reports_02_22
verify_final_successor_reports_v4 = verify_final_successor_reports_02_22
write_final_successor_summary_v4 = write_final_successor_summary_02_22
validate_final_successor_summary_v4 = validate_final_successor_summary_02_22
