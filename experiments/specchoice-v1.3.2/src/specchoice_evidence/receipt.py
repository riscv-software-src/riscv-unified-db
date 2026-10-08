# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Canonical integrity receipts and their JSON-only reviewer projection."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, require_sha256, sha256_bytes
from .filesystem import FilesystemPolicyError, read_authoritative_file, write_new_descriptor_file


class ReceiptError(ValueError):
    """Stable receipt construction or validation failure."""


_V3_VERIFIER_PATHS = (
    "verifier/specchoice_evidence/__init__.py",
    "verifier/specchoice_evidence/canonical.py",
    "verifier/specchoice_evidence/filesystem.py",
    "verifier/specchoice_evidence/verify.py",
    "verify_bundle.py",
)


def _canonical_descriptor_payload(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    """Read one canonical receipt through its held parent descriptor."""
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ReceiptError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise ReceiptError(code)
    return value, raw


def _require_exact_keys(value: dict[str, Any], keys: set[str], code: str) -> None:
    if set(value) != keys:
        raise ReceiptError(code)


def _v3_identity(value: object, code: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ReceiptError(code)
    expected = {"core_sha256", "generation", "root_sha256", "snapshot_manifest_sha256"}
    if set(value) != expected or not isinstance(value.get("generation"), str):
        raise ReceiptError(code)
    for key in expected - {"generation"}:
        _require_digest(value.get(key), code)
    return {key: str(value[key]) for key in expected}


def _validate_v3_verifier_artifacts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) != len(_V3_VERIFIER_PATHS):
        raise ReceiptError("V3_VERIFIER_ARTIFACTS_INVALID")
    if [entry.get("path") if isinstance(entry, dict) else None for entry in value] != list(_V3_VERIFIER_PATHS):
        raise ReceiptError("V3_VERIFIER_ARTIFACTS_INVALID")
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"byte_length", "path", "sha256"}:
            raise ReceiptError("V3_VERIFIER_ARTIFACTS_INVALID")
        if isinstance(entry["byte_length"], bool) or not isinstance(entry["byte_length"], int) or entry["byte_length"] < 0:
            raise ReceiptError("V3_VERIFIER_ARTIFACTS_INVALID")
        _require_digest(entry["sha256"], "V3_VERIFIER_ARTIFACTS_INVALID")
    return value


def _hashed_v3(receipt: dict[str, Any]) -> dict[str, Any]:
    if "receipt_sha256" in receipt:
        raise ReceiptError("V3_RECEIPT_HASH_INVALID")
    return {**receipt, "receipt_sha256": sha256_bytes(canonical_json_bytes(receipt))}


def render_v3_receipt_markdown(receipt: dict[str, Any], title: str) -> str:
    """Render a pure, JSON-derived Markdown projection for an immutable v3 receipt."""
    if not isinstance(title, str) or not title:
        raise ReceiptError("V3_RECEIPT_MARKDOWN_INVALID")
    if receipt.get("receipt_sha256") != sha256_bytes(canonical_json_bytes({key: value for key, value in receipt.items() if key != "receipt_sha256"})):
        raise ReceiptError("V3_RECEIPT_HASH_INVALID")
    return f"# {title}\n\n```json\n{canonical_json_bytes(receipt).decode('utf-8')}```\n"


def _write_new_descriptor_file(root: Path, name: str, content: bytes) -> None:
    """Create exactly one immutable receipt leaf through a held root descriptor."""
    try:
        write_new_descriptor_file(root, name, content)
    except FilesystemPolicyError as error:
        if str(error) == "AUTHORITATIVE_DESTINATION_EXISTS":
            raise ReceiptError("V3_RECEIPT_DESTINATION_EXISTS") from error
        raise ReceiptError("V3_RECEIPT_WRITE_INVALID") from error
    except OSError as error:
        raise ReceiptError("V3_RECEIPT_DESTINATION_EXISTS") from error


def _run_embedded_v3_replay(accepted_bundle: Path) -> dict[str, object]:
    """Prove the embedded verifier rejects tamper, missing, and extra artifacts in copied isolation."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        environment = {"PATH": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
        for name, mutate in (
            ("clean", None),
            ("tampered", lambda copied: (copied / "verify_bundle.py").write_bytes(b"tampered\n")),
            ("missing", lambda copied: (copied / "verify_bundle.py").unlink()),
            ("extra", lambda copied: (copied / "unexpected.txt").write_text("extra\n", encoding="utf-8")),
        ):
            copied = root / name
            shutil.copytree(accepted_bundle, copied)
            if mutate is not None:
                mutate(copied)
            result = subprocess.run(
                [sys.executable, "verify_bundle.py"], cwd=copied, env=environment,
                check=False, capture_output=True, text=True,
            )
            if (name == "clean") != (result.returncode == 0):
                raise ReceiptError("V3_OFFLINE_REPLAY_INVALID")
    return {
        "git_available": False,
        "network_available": False,
        "original_bundle_available": False,
        "repository_modules_available": False,
        "result": "passed",
    }


def build_accepted_v3_receipts(
    request_path: Path,
    decision_path: Path,
    candidate_audit_path: Path,
    pending_authority_path: Path,
    transition_path: Path,
    active_authority_path: Path,
    historical_authority_path: Path,
    accepted_bundle: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build three cross-bound accepted-v3 receipts from canonical descriptor-held inputs."""
    request, request_raw = _canonical_descriptor_payload(request_path, "V3_ACCEPTANCE_REQUEST_INVALID")
    decision, decision_raw = _canonical_descriptor_payload(decision_path, "V3_ACCEPTANCE_DECISION_INVALID")
    audit, audit_raw = _canonical_descriptor_payload(candidate_audit_path, "V3_CANDIDATE_AUDIT_INVALID")
    pending, pending_raw = _canonical_descriptor_payload(pending_authority_path, "V3_PENDING_AUTHORITY_INVALID")
    transition, transition_raw = _canonical_descriptor_payload(transition_path, "V3_TRANSITION_INVALID")
    active, active_raw = _canonical_descriptor_payload(active_authority_path, "V3_ACTIVE_AUTHORITY_INVALID")
    historical, historical_raw = _canonical_descriptor_payload(historical_authority_path, "V3_HISTORICAL_AUTHORITY_INVALID")
    if active_raw != historical_raw or active.get("schema_version") != "1" or active.get("local_only") is not True or active.get("external_publication_authorized") is not False:
        raise ReceiptError("V3_ACTIVE_AUTHORITY_INVALID")
    from .source_contract import validate_local_acceptance_decision_v10
    from .verify import verify_accepted_bundle

    validate_local_acceptance_decision_v10(decision, request, sha256_bytes(request_raw))
    verified = verify_accepted_bundle(accepted_bundle)
    identity = _v3_identity(decision.get("projected_accepted"), "V3_ACCEPTED_IDENTITY_INVALID")
    if identity != _v3_identity(pending.get("accepted_identity"), "V3_PENDING_AUTHORITY_INVALID"):
        raise ReceiptError("V3_ACCEPTED_IDENTITY_MISMATCH")
    if identity["generation"] != verified.get("generation") or identity["core_sha256"] != verified.get("manifest_sha256") or identity["root_sha256"] != verified.get("root_sha256"):
        raise ReceiptError("V3_ACCEPTED_IDENTITY_MISMATCH")
    artifacts = _validate_v3_verifier_artifacts(decision.get("verifier_artifacts"))
    for value, key, raw in ((pending, "request_sha256", request_raw), (pending, "decision_sha256", decision_raw), (pending, "transition_sha256", transition_raw)):
        if value.get(key) != sha256_bytes(raw):
            raise ReceiptError("V3_PENDING_LINEAGE_MISMATCH")
    if pending.get("status") != "pending_cutover_v10" or pending.get("local_only") is not True or pending.get("external_publication_authorized") is not False:
        raise ReceiptError("V3_PENDING_AUTHORITY_INVALID")
    if transition.get("request_sha256") != sha256_bytes(request_raw) or transition.get("decision_sha256") != sha256_bytes(decision_raw) or transition.get("old_authority_sha256") != sha256_bytes(active_raw):
        raise ReceiptError("V3_TRANSITION_INVALID")
    construction = {key: audit.get(key) for key in ("proposal", "decision")}
    if not all(isinstance(value, dict) and set(value) >= {"path", "sha256"} for value in construction.values()):
        raise ReceiptError("V3_CANDIDATE_AUDIT_INVALID")
    common = {
        "accepted_identity": identity,
        "active_authority_sha256": sha256_bytes(active_raw),
        "candidate_audit_sha256": sha256_bytes(audit_raw),
        "construction": construction,
        "decision_sha256": sha256_bytes(decision_raw),
        "external_publication_authorized": False,
        "fixture_inventory": {"fixture_count": 11, "partition": {"candidate": 1, "negative": 4, "positive": 6}, "raw_file_count": 28, "registry_sha256": pending["registry_sha256"]},
        "historical_authority_sha256": sha256_bytes(historical_raw),
        "local_only": True,
        "pending_authority_sha256": sha256_bytes(pending_raw),
        "pending_transition_sha256": sha256_bytes(transition_raw),
        "request_sha256": sha256_bytes(request_raw),
        "verifier_artifacts": artifacts,
    }
    acceptance = _hashed_v3({**common, "kind": "fixture_closure_acceptance_audit_v3", "schema_version": "3", "status": "accepted_v3_local_only"})
    integrity = _hashed_v3({**common, "acceptance_audit_sha256": acceptance["receipt_sha256"], "kind": "integrity_receipt_v10", "schema_version": "10", "status": "accepted_v3_integrity_pass"})
    replay = _hashed_v3({**common, "acceptance_audit_sha256": acceptance["receipt_sha256"], "copied_isolation_replay": _run_embedded_v3_replay(accepted_bundle), "integrity_receipt_sha256": integrity["receipt_sha256"], "kind": "fixture_closure_offline_replay_v3", "schema_version": "3", "status": "accepted_v3_offline_replay_pass"})
    return acceptance, integrity, replay


def write_accepted_v3_receipts(receipt_directory: Path, receipts: tuple[dict[str, Any], dict[str, Any], dict[str, Any]]) -> list[str]:
    """Persist the exact immutable v3 receipt set without replacement."""
    acceptance, integrity, replay = receipts
    outputs = (
        ("fixture-closure-acceptance-audit-v3.json", canonical_json_bytes(acceptance)),
        ("fixture-closure-acceptance-audit-v3.md", render_v3_receipt_markdown(acceptance, "Fixture Closure Acceptance Audit v3").encode("utf-8")),
        ("fixture-closure-offline-replay-v3.json", canonical_json_bytes(replay)),
        ("integrity-receipt-v10.json", canonical_json_bytes(integrity)),
        ("integrity-receipt-v10.md", render_v3_receipt_markdown(integrity, "Integrity Receipt v10").encode("utf-8")),
    )
    for name, content in outputs:
        _write_new_descriptor_file(receipt_directory, name, content)
    return [name for name, _ in outputs]


def _receipt_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    projected = dict(receipt)
    projected.pop("receipt_sha256", None)
    return projected


def _hashed(receipt: dict[str, Any]) -> dict[str, Any]:
    projected = _receipt_projection(receipt)
    projected["receipt_sha256"] = sha256_bytes(canonical_json_bytes(projected))
    return projected


def _require_digest(value: object, code: str) -> str:
    try:
        return require_sha256(value)
    except ValueError as error:
        raise ReceiptError(code) from error


def _validate_classifications(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ReceiptError("BOUNDARY_CLASSIFICATIONS_INVALID")
    records: list[dict[str, object]] = []
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ReceiptError("BOUNDARY_CLASSIFICATIONS_INVALID")
        if not isinstance(record.get("status"), str):
            raise ReceiptError("BOUNDARY_CLASSIFICATIONS_INVALID")
        if not isinstance(record.get("attributed_to_phase"), bool) or not isinstance(record.get("blocking"), bool):
            raise ReceiptError("BOUNDARY_CLASSIFICATIONS_INVALID")
        records.append(record)
    return sorted(records, key=lambda record: str(record["path"]))


def _local_source_identity(approved_generation: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_relative_path": approved_generation.get("candidate_relative_path"),
        "core_sha256": approved_generation.get("core_sha256"),
        "external_publication_authorized": False,
        "generation": approved_generation.get("generation"),
        "kind": "local_accepted_generation",
        "local_accepted_generation_authorized": True,
        "root_sha256": approved_generation.get("root_sha256"),
        "snapshot_manifest_sha256": approved_generation.get("snapshot_manifest_sha256"),
    }


def local_receipt_basis_sha256(
    baseline_sha256: str,
    environment_sha256: str,
    local_identity: dict[str, object],
    boundary_classifications: list[dict[str, object]],
    *,
    reviewed_revision: str | None = None,
    committed_boundary_projection_sha256: str | None = None,
) -> str:
    """Hash the reviewer-visible local facts without creating a receipt/decision cycle."""
    if (reviewed_revision is None) != (committed_boundary_projection_sha256 is None):
        raise ReceiptError("LOCAL_RECEIPT_PROJECTION_BINDING_INVALID")
    basis: dict[str, object] = {
        "boundary_classifications": _validate_classifications(boundary_classifications),
        "environment_decision_sha256": _require_digest(environment_sha256, "RECEIPT_DIGEST_INVALID"),
        "phase_start_baseline_sha256": _require_digest(baseline_sha256, "RECEIPT_DIGEST_INVALID"),
        "source_identity": _local_source_identity(local_identity),
    }
    if reviewed_revision is not None:
        if len(reviewed_revision) != 40 or any(char not in "0123456789abcdef" for char in reviewed_revision):
            raise ReceiptError("LOCAL_REVIEWED_REVISION_INVALID")
        basis["committed_boundary_projection_sha256"] = _require_digest(
            committed_boundary_projection_sha256, "LOCAL_RECEIPT_PROJECTION_INVALID"
        )
        basis["reviewed_revision"] = reviewed_revision
    return sha256_bytes(canonical_json_bytes(basis))


def validate_receipt(source: dict[str, Any] | Path) -> dict[str, Any]:
    """Validate canonical receipt bytes and the non-cyclic receipt digest."""
    if isinstance(source, Path):
        try:
            raw = source.read_bytes()
            receipt = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReceiptError("RECEIPT_INVALID") from error
        if not isinstance(receipt, dict) or canonical_json_bytes(receipt) != raw:
            raise ReceiptError("RECEIPT_NOT_CANONICAL")
    else:
        receipt = source
    if not isinstance(receipt, dict) or receipt.get("schema_version") not in {"1", "2", "3", "4", "5"}:
        raise ReceiptError("RECEIPT_SCHEMA_INVALID")
    if receipt.get("generator_version") not in {"1", "2", "3", "4", "5"}:
        raise ReceiptError("RECEIPT_GENERATOR_INVALID")
    if (receipt.get("schema_version") == "5") != (
        receipt.get("generator_version") == "5"
    ):
        raise ReceiptError("RECEIPT_GENERATOR_INVALID")
    for key in ("phase_start_baseline_sha256", "environment_decision_sha256", "receipt_sha256"):
        _require_digest(receipt.get(key), "RECEIPT_DIGEST_INVALID")
    source_identity = receipt.get("source_identity")
    if not isinstance(source_identity, dict):
        raise ReceiptError("SOURCE_IDENTITY_INVALID")
    kind = source_identity.get("kind")
    if kind == "accepted_generation":
        for key in ("generation", "root_sha256", "manifest_sha256"):
            value = source_identity.get(key)
            if key == "generation":
                if not isinstance(value, str) or not value:
                    raise ReceiptError("SOURCE_IDENTITY_INVALID")
            else:
                _require_digest(value, "SOURCE_IDENTITY_INVALID")
        if "rejected_attempt_sha256" in source_identity:
            raise ReceiptError("SOURCE_IDENTITY_AMBIGUOUS")
    elif kind == "rejected_attempt":
        _require_digest(source_identity.get("rejected_attempt_sha256"), "SOURCE_IDENTITY_INVALID")
        if any(key in source_identity for key in ("generation", "root_sha256", "manifest_sha256")):
            raise ReceiptError("SOURCE_IDENTITY_AMBIGUOUS")
    elif kind == "local_accepted_generation":
        expected_fields = {
            "candidate_relative_path",
            "core_sha256",
            "external_publication_authorized",
            "generation",
            "kind",
            "local_accepted_generation_authorized",
            "root_sha256",
            "snapshot_manifest_sha256",
        }
        if set(source_identity) != expected_fields:
            raise ReceiptError("SOURCE_IDENTITY_INVALID")
        if (
            not isinstance(source_identity.get("candidate_relative_path"), str)
            or not source_identity["candidate_relative_path"]
            or not isinstance(source_identity.get("generation"), str)
            or not source_identity["generation"]
            or source_identity.get("external_publication_authorized") is not False
            or source_identity.get("local_accepted_generation_authorized") is not True
        ):
            raise ReceiptError("SOURCE_IDENTITY_INVALID")
        for key in ("core_sha256", "root_sha256", "snapshot_manifest_sha256"):
            _require_digest(source_identity.get(key), "SOURCE_IDENTITY_INVALID")
        for key in ("reviewer_decision_sha256", "receipt_basis_sha256"):
            _require_digest(receipt.get(key), "RECEIPT_DIGEST_INVALID")
    else:
        raise ReceiptError("SOURCE_IDENTITY_INVALID")
    _validate_classifications(receipt.get("boundary_classifications"))
    for key in ("blocking_diagnostics", "nonblocking_diagnostics"):
        if not isinstance(receipt.get(key), list) or not all(isinstance(item, str) for item in receipt[key]):
            raise ReceiptError("RECEIPT_DIAGNOSTICS_INVALID")
    if not isinstance(receipt.get("reviewer_package_complete"), bool) or receipt.get("outcome") not in {"pass", "fail"}:
        raise ReceiptError("RECEIPT_OUTCOME_INVALID")
    if receipt.get("receipt_sha256") != sha256_bytes(canonical_json_bytes(_receipt_projection(receipt))):
        raise ReceiptError("RECEIPT_SELF_HASH_MISMATCH")
    if kind == "rejected_attempt" and receipt.get("outcome") != "fail":
        raise ReceiptError("REJECTED_SOURCE_CANNOT_PASS")
    if kind == "local_accepted_generation" and (
        receipt.get("outcome") != "pass" or receipt.get("blocking_diagnostics") != []
    ):
        raise ReceiptError("LOCAL_SOURCE_CANNOT_BE_BLOCKED_PASS")
    if receipt.get("schema_version") in {"3", "4"}:
        lineage = receipt.get("restart_lineage")
        if not isinstance(lineage, dict) or set(lineage) != {"allowlist", "baseline", "incident_receipt", "previous_baseline", "reason_code", "reviewed_revision", "scope"}:
            raise ReceiptError("RESTART_LINEAGE_INVALID")
        if lineage.get("reason_code") != "D15_RESTART_COMMITTED_HISTORY_BLIND_SPOT" or lineage.get("scope") != "gap_closure_only" or not isinstance(lineage.get("reviewed_revision"), str):
            raise ReceiptError("RESTART_LINEAGE_INVALID")
        for name in ("allowlist", "baseline", "incident_receipt", "previous_baseline"):
            if not isinstance(lineage[name], dict) or not isinstance(lineage[name].get("path"), str):
                raise ReceiptError("RESTART_LINEAGE_INVALID")
            _require_digest(lineage[name].get("sha256"), "RESTART_LINEAGE_INVALID")
        if lineage["baseline"]["sha256"] != receipt["phase_start_baseline_sha256"]:
            raise ReceiptError("RESTART_LINEAGE_BASELINE_MISMATCH")
    if receipt.get("schema_version") == "5":
        authority = receipt.get("publication_authority")
        if not isinstance(authority, dict) or set(authority) != {
            "manifest_path", "manifest_sha256", "reviewed_revision", "upstream_base_commit"
        }:
            raise ReceiptError("PUBLICATION_AUTHORITY_INVALID")
        if authority.get("manifest_path") != "evidence/publication-manifest-v1.json":
            raise ReceiptError("PUBLICATION_AUTHORITY_INVALID")
        _require_digest(authority.get("manifest_sha256"), "PUBLICATION_AUTHORITY_INVALID")
        for key in ("reviewed_revision", "upstream_base_commit"):
            value = authority.get(key)
            if not isinstance(value, str) or len(value) != 40 or any(
                char not in "0123456789abcdef" for char in value
            ):
                raise ReceiptError("PUBLICATION_AUTHORITY_INVALID")
        if (
            authority["manifest_sha256"] != receipt["phase_start_baseline_sha256"]
            or authority["reviewed_revision"] != receipt.get("reviewed_revision")
            or "restart_lineage" in receipt
        ):
            raise ReceiptError("PUBLICATION_AUTHORITY_INVALID")
    if receipt.get("schema_version") in {"4", "5"}:
        revision = receipt.get("reviewed_revision")
        if not isinstance(revision, str) or len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
            raise ReceiptError("LOCAL_REVIEWED_REVISION_INVALID")
        _require_digest(receipt.get("committed_boundary_projection_sha256"), "LOCAL_RECEIPT_PROJECTION_INVALID")
    return receipt


def build_blocked_receipt(
    baseline_sha256: str,
    environment_sha256: str,
    rejected_attempt_sha256: str,
    boundary_classifications: list[dict[str, object]],
) -> dict[str, Any]:
    """Build the current fail-closed receipt without an accepted source identity."""
    records = _validate_classifications(boundary_classifications)
    blocking = ["SOURCE_GENERATION_NOT_ACCEPTED"]
    blocking.extend(sorted({str(record.get("status")) for record in records if record["blocking"]}))
    receipt: dict[str, Any] = {
        "boundary_classifications": records,
        "blocking_diagnostics": blocking,
        "environment_decision_sha256": _require_digest(environment_sha256, "RECEIPT_DIGEST_INVALID"),
        "generator_version": "1",
        "nonblocking_diagnostics": sorted(
            {str(record.get("diagnostic")) for record in records if record.get("diagnostic")}
        ),
        "outcome": "fail",
        "phase_start_baseline_sha256": _require_digest(baseline_sha256, "RECEIPT_DIGEST_INVALID"),
        "reviewer_package_complete": False,
        "schema_version": "1",
        "source_identity": {
            "kind": "rejected_attempt",
            "rejected_attempt_sha256": _require_digest(rejected_attempt_sha256, "SOURCE_IDENTITY_INVALID"),
        },
    }
    return validate_receipt(_hashed(receipt))


def build_local_mvp_receipt(
    baseline_sha256: str,
    environment_sha256: str,
    approved_generation: dict[str, object],
    boundary_classifications: list[dict[str, object]],
    reviewer_decision_sha256: str,
    reviewed_receipt_basis_sha256: str,
    restart_lineage: dict[str, object] | None = None,
    *,
    reviewed_revision: str | None = None,
    committed_boundary_projection_sha256: str | None = None,
    publication_authority: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Build a pass receipt for a local-only accepted identity after all machine gates pass."""
    if publication_authority is not None and restart_lineage is not None:
        raise ReceiptError("BOUNDARY_AUTHORITY_AMBIGUOUS")
    if reviewed_revision is not None and restart_lineage is None and publication_authority is None:
        raise ReceiptError("BOUNDARY_AUTHORITY_REQUIRED")
    source_identity = _local_source_identity(approved_generation)
    records = _validate_classifications(boundary_classifications)
    if any(record["blocking"] for record in records):
        raise ReceiptError("LOCAL_MVP_BOUNDARY_BLOCKING")
    basis = local_receipt_basis_sha256(
        baseline_sha256,
        environment_sha256,
        source_identity,
        records,
        reviewed_revision=reviewed_revision,
        committed_boundary_projection_sha256=committed_boundary_projection_sha256,
    )
    if reviewed_receipt_basis_sha256 != basis:
        raise ReceiptError("LOCAL_RECEIPT_BASIS_MISMATCH")
    receipt: dict[str, Any] = {
        "blocking_diagnostics": [],
        "boundary_classifications": records,
        "environment_decision_sha256": _require_digest(environment_sha256, "RECEIPT_DIGEST_INVALID"),
        "generator_version": "5" if publication_authority is not None else ("4" if reviewed_revision is not None else ("3" if restart_lineage is not None else "2")),
        "nonblocking_diagnostics": ["LOCAL_MVP_ONLY_EXTERNAL_PUBLICATION_PROHIBITED"],
        "outcome": "pass",
        "phase_start_baseline_sha256": _require_digest(baseline_sha256, "RECEIPT_DIGEST_INVALID"),
        "receipt_basis_sha256": _require_digest(basis, "RECEIPT_DIGEST_INVALID"),
        "reviewer_decision_sha256": _require_digest(reviewer_decision_sha256, "RECEIPT_DIGEST_INVALID"),
        "reviewer_package_complete": False,
        "schema_version": "5" if publication_authority is not None else ("4" if reviewed_revision is not None else ("3" if restart_lineage is not None else "2")),
        "source_identity": source_identity,
    }
    if restart_lineage is not None:
        receipt["restart_lineage"] = restart_lineage
    if publication_authority is not None:
        receipt["publication_authority"] = publication_authority
    if reviewed_revision is not None:
        receipt["reviewed_revision"] = reviewed_revision
        receipt["committed_boundary_projection_sha256"] = committed_boundary_projection_sha256
    return validate_receipt(_hashed(receipt))


def render_markdown(receipt: dict[str, Any]) -> str:
    """Render only validated JSON values; no file, Git, boundary, or hash lookups occur here."""
    value = validate_receipt(receipt)
    source = value["source_identity"]
    lines = [
        "# Phase 1 Integrity Receipt",
        "",
        f"- Authoritative SHA-256: `{value['receipt_sha256']}`",
        f"- Generator version: `{value['generator_version']}`",
        f"- Outcome: `{value['outcome']}`",
        f"- Reviewer package complete: `{str(value['reviewer_package_complete']).lower()}`",
        f"- Phase-start baseline SHA-256: `{value['phase_start_baseline_sha256']}`",
        f"- Environment decision SHA-256: `{value['environment_decision_sha256']}`",
        f"- Source identity: `{source['kind']}`",
        "",
        "## Boundary classifications",
        "",
    ]
    if source["kind"] == "local_accepted_generation":
        lines.extend(
            [
                f"- Local accepted generation: `{source['generation']}`",
                f"- Core SHA-256: `{source['core_sha256']}`",
                f"- Logical root SHA-256: `{source['root_sha256']}`",
                f"- Snapshot manifest SHA-256: `{source['snapshot_manifest_sha256']}`",
                "- External publication authorized: `false`",
            ]
        )
    for record in value["boundary_classifications"]:
        lines.append(
            f"- `{record['path']}` — `{record['status']}`, blocking={str(record['blocking']).lower()}, "
            f"attributed_to_phase={str(record['attributed_to_phase']).lower()}"
        )
    lines.extend(["", "## Diagnostics", ""])
    for diagnostic in value["blocking_diagnostics"] + value["nonblocking_diagnostics"]:
        lines.append(f"- `{diagnostic}`")
    return "\n".join(lines) + "\n"


def write_receipt_package(receipt: dict[str, Any], json_path: Path, markdown_path: Path) -> dict[str, Any]:
    """Persist canonical JSON first; Markdown failure leaves it valid but incomplete."""
    value = validate_receipt(receipt)
    value = _hashed({**_receipt_projection(value), "reviewer_package_complete": False})
    json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        markdown_path.write_text(render_markdown(_hashed({**_receipt_projection(value), "reviewer_package_complete": True})), encoding="utf-8")
    except OSError:
        json_path.write_bytes(canonical_json_bytes(value))
        return validate_receipt(value)
    value = _hashed({**_receipt_projection(value), "reviewer_package_complete": True})
    json_path.write_bytes(canonical_json_bytes(value))
    return validate_receipt(value)
