# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Accepted-v2-only bounded PR #2164 fixture adapter."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from specchoice_evidence.bundle import _sync_directory, _write_exact
from specchoice_evidence.canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file, require_relative_posix_path
from specchoice_evidence.runtime_closure import RuntimeClosureError, load_runtime_closure_v4
from specchoice_evidence.verify import verify_accepted_bundle

from .domain import AdapterBatch, CanonicalFixtureRecord, Diagnostic, RawFileIdentity


class AdapterError(ValueError):
    """Stable error for bounded score-bearing fixture syntax."""

    def __init__(self, code: str, *, diagnostic: Diagnostic | None = None) -> None:
        super().__init__(code)
        self.diagnostic = diagnostic


def validate_v5_outcome_contract(contract: object, golden: object) -> None:
    """Validate the closed v5 11-case population before scoring may begin."""
    if not isinstance(contract, dict) or not isinstance(golden, dict):
        raise AdapterError("V5_OUTCOME_CONTRACT_INVALID")
    outcomes = golden.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != 11:
        raise AdapterError("V5_OUTCOME_CONTRACT_INVALID")
    indexed = {item.get("fixture_id"): item for item in outcomes if isinstance(item, dict)}
    surfaced = {key for key, item in indexed.items() if item.get("surfaced") is True}
    negatives = {key for key, item in indexed.items() if item.get("surfaced") is False}
    accepted = [item.get("proposed_name") for item in outcomes if item.get("parameter_status") == "accept"]
    candidates = set(contract.get("candidate_ids", []))
    if (
        len(indexed) != 11
        or surfaced != set(contract.get("surfaced_ids", []))
        or negatives != set(contract.get("negative_ids", []))
        or accepted != contract.get("identity_names")
        or any(indexed.get(candidate, {}).get("parameter_status") != "classify_out" or indexed[candidate].get("proposed_name") is not None for candidate in candidates)
    ):
        raise AdapterError("V5_OUTCOME_CONTRACT_INVALID")

EXPECTED_FIELDS = {
    "candidate_or_negative": ["expect_extract", "expect_params", "id"],
    "positive": ["class", "expect_extract", "expect_status", "gold_name", "id", "must_have_excerpt"],
}

_EXPERIMENT_ROOT = Path(__file__).parents[2]


def _load_canonical_json(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        payload = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterError(code) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise AdapterError(code)
    return payload, raw


def _validate_phase2_authority(authority_path: Path, bundle_root: Path) -> dict[str, str]:
    """Validate the inspection-only active-v2 mode at the public boundary."""
    authority_before, authority_before_raw = _load_canonical_json(authority_path, "PHASE2_SOURCE_AUTHORITY_INVALID")
    revocation_path = authority_path.parent.parent / "receipts/fixture-closure-revocation-v2.json"
    try:
        read_authoritative_file(revocation_path.parent, revocation_path.name)
    except FilesystemPolicyError as error:
        if str(error) != "AUTHORITATIVE_FILE_MISSING":
            raise AdapterError("SOURCE_AUTHORITY_REVOCATION_INVALID") from error
    except OSError as error:
        raise AdapterError("SOURCE_AUTHORITY_REVOCATION_INVALID") from error
    else:
        raise AdapterError("SOURCE_AUTHORITY_V2_REVOKED")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "specchoice_evidence.cli",
            "validate-phase2-source-authority",
            "--authority",
            authority_path.as_posix(),
            "--bundle",
            bundle_root.as_posix(),
            "--revocation",
            revocation_path.as_posix(),
            "--authority-mode",
            "active",
        ],
        check=False,
        capture_output=True,
        cwd=_EXPERIMENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(_EXPERIMENT_ROOT / "src")},
        text=True,
    )
    try:
        read_authoritative_file(revocation_path.parent, revocation_path.name)
    except FilesystemPolicyError as error:
        if str(error) != "AUTHORITATIVE_FILE_MISSING":
            raise AdapterError("SOURCE_AUTHORITY_REVOCATION_INVALID") from error
    except OSError as error:
        raise AdapterError("SOURCE_AUTHORITY_REVOCATION_INVALID") from error
    else:
        raise AdapterError("SOURCE_AUTHORITY_V2_REVOKED")
    authority, authority_raw = _load_canonical_json(authority_path, "PHASE2_SOURCE_AUTHORITY_INVALID")
    if authority_raw != authority_before_raw:
        raise AdapterError("PHASE2_SOURCE_AUTHORITY_CHANGED_DURING_VALIDATION")
    receipt = _closed_validator_stdout(completed, "PHASE2_SOURCE_AUTHORITY_INVALID")
    verified = verify_accepted_bundle(bundle_root)
    manifest, _ = _load_canonical_json(bundle_root / "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    registry, registry_raw = _load_canonical_json(bundle_root / "fixture-registry-pr2164-v1.json", "FIXTURE_REGISTRY_INVALID")
    snapshot = manifest.get("content_manifest_core", {}).get("snapshots", []) if isinstance(manifest.get("content_manifest_core"), dict) else []
    if not isinstance(snapshot, list) or len(snapshot) != 1:
        raise AdapterError("PHASE2_SOURCE_AUTHORITY_INVALID")
    expected_receipt = {
        "eligible": True,
        "fixture_count": 11,
        "generation": verified["generation"],
        "manifest_sha256": manifest.get("snapshot_manifest_sha256"),
        "pinned_commit_sha": snapshot[0].get("pinned_commit_sha"),
        "pinned_tree_sha": snapshot[0].get("pinned_tree_sha"),
        "raw_file_count": 28,
        "registry_sha256": sha256_bytes(registry_raw),
        "root_sha256": verified["root_sha256"],
        "status": "valid",
    }
    if receipt != expected_receipt or authority != authority_before:
        raise AdapterError("PHASE2_SOURCE_AUTHORITY_INVALID")
    return _source_identity(authority, verified)


def _closed_validator_stdout(completed: subprocess.CompletedProcess[str], code: str = "PENDING_SOURCE_CUTOVER_INVALID") -> dict[str, object]:
    """Accept precisely one canonical stdout receipt from the public validator."""
    if completed.returncode != 0 or completed.stderr:
        raise AdapterError(code)
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AdapterError(f"{code}_STDOUT_INVALID") from error
    if not isinstance(receipt, dict) or completed.stdout.encode("utf-8") != canonical_json_bytes(receipt):
        raise AdapterError(f"{code}_STDOUT_INVALID")
    return receipt


def _held_verified_provenance(verified: dict[str, str]) -> dict[str, str]:
    """Retain only verifier-proven identity when a later custody check fails."""
    return {
        "generation": verified["generation"],
        "manifest_sha256": verified["manifest_sha256"],
        "root_sha256": verified["root_sha256"],
    }


def _validate_pending_source_cutover(
    *,
    authority_path: Path,
    bundle_root: Path,
    pending_authority_path: Path,
    transition_path: Path,
) -> dict[str, str]:
    """Bind an explicit pending-v3 rehearsal without making it active authority."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "specchoice_evidence.cli",
            "validate-pending-source-cutover-v10",
            "--pending-authority",
            pending_authority_path.as_posix(),
            "--transition",
            transition_path.as_posix(),
            "--active-authority",
            authority_path.as_posix(),
            "--accepted-bundle",
            bundle_root.as_posix(),
        ],
        check=False,
        capture_output=True,
        cwd=_EXPERIMENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(_EXPERIMENT_ROOT / "src")},
        text=True,
    )
    receipt = _closed_validator_stdout(completed)
    pending, pending_raw = _load_canonical_json(pending_authority_path, "PENDING_SOURCE_AUTHORITY_INVALID")
    transition, transition_raw = _load_canonical_json(transition_path, "PENDING_SOURCE_TRANSITION_INVALID")
    active, active_raw = _load_canonical_json(authority_path, "PHASE2_SOURCE_AUTHORITY_INVALID")
    verified = verify_accepted_bundle(bundle_root)
    manifest, _ = _load_canonical_json(bundle_root / "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    registry, registry_raw = _load_canonical_json(bundle_root / "fixture-registry-pr2164-v1.json", "FIXTURE_REGISTRY_INVALID")
    expected_receipt = {
        "active_authority_sha256": sha256_bytes(active_raw),
        "eligible": False,
        "pending_authority_sha256": sha256_bytes(pending_raw),
        "status": "pending_cutover_valid_non_effective",
        "transition_sha256": sha256_bytes(transition_raw),
    }
    if receipt != expected_receipt:
        raise AdapterError("PENDING_SOURCE_CUTOVER_RECEIPT_MISMATCH")
    snapshot = manifest.get("content_manifest_core", {}).get("snapshots", []) if isinstance(manifest.get("content_manifest_core"), dict) else []
    fixtures = registry.get("fixtures") if isinstance(registry, dict) else None
    partition = {
        category: sum(isinstance(item, dict) and item.get("fixture_class") == category for item in fixtures or ())
        for category in ("positive", "negative", "candidate")
    }
    accepted_identity = {
        "core_sha256": verified["manifest_sha256"],
        "generation": verified["generation"],
        "root_sha256": verified["root_sha256"],
        "snapshot_manifest_sha256": manifest.get("snapshot_manifest_sha256"),
    }
    if (
        pending.get("schema_version") != "10"
        or pending.get("status") != "pending_cutover_v10"
        or pending.get("local_only") is not True
        or pending.get("external_publication_authorized") is not False
        or pending.get("accepted_identity") != accepted_identity
        or pending.get("generation") != verified["generation"]
        or pending.get("manifest_sha256") != manifest.get("snapshot_manifest_sha256")
        or pending.get("root_sha256") != verified["root_sha256"]
        or pending.get("registry_sha256") != sha256_bytes(registry_raw)
        or pending.get("fixture_count") != 11
        or pending.get("raw_file_count") != 28
        or not isinstance(snapshot, list)
        or len(snapshot) != 1
        or pending.get("pinned_commit_sha") != snapshot[0].get("pinned_commit_sha")
        or pending.get("pinned_tree_sha") != snapshot[0].get("pinned_tree_sha")
        or partition != {"positive": 6, "negative": 4, "candidate": 1}
        or transition.get("old_authority_sha256") != sha256_bytes(active_raw)
        or transition.get("accepted_identity") != accepted_identity
        or active.get("schema_version") != "1"
        or active.get("local_only") is not True
        or active.get("external_publication_authorized") is not False
    ):
        raise AdapterError("PENDING_SOURCE_CUTOVER_RECEIPT_MISMATCH")
    audit_path = authority_path.parent.parent / "receipts/fixture-closure-acceptance-audit-v3.json"
    audit, audit_raw = _load_canonical_json(audit_path, "PENDING_SOURCE_AUDIT_INVALID")
    inventory = audit.get("fixture_inventory")
    if (
        audit.get("kind") != "fixture_closure_acceptance_audit_v3"
        or audit.get("status") != "accepted_v3_local_only"
        or audit.get("local_only") is not True
        or audit.get("external_publication_authorized") is not False
        or audit.get("accepted_identity") != accepted_identity
        or audit.get("active_authority_sha256") != sha256_bytes(active_raw)
        or audit.get("historical_authority_sha256") != sha256_bytes(active_raw)
        or audit.get("pending_authority_sha256") != sha256_bytes(pending_raw)
        or audit.get("pending_transition_sha256") != sha256_bytes(transition_raw)
        or audit.get("decision_sha256") != pending.get("decision_sha256")
        or audit.get("request_sha256") != pending.get("request_sha256")
        or inventory != {
            "fixture_count": 11,
            "partition": {"candidate": 1, "negative": 4, "positive": 6},
            "raw_file_count": 28,
            "registry_sha256": sha256_bytes(registry_raw),
        }
        or not isinstance(audit.get("verifier_artifacts"), list)
        or len(audit["verifier_artifacts"]) != 5
        or sha256_bytes(canonical_json_bytes({key: value for key, value in audit.items() if key != "receipt_sha256"}))
        != audit.get("receipt_sha256")
    ):
        raise AdapterError("PENDING_SOURCE_AUDIT_MISMATCH")
    return _source_identity(pending, verified)


def _validate_active_source_cutover(
    *, authority_path: Path, bundle_root: Path, revocation_path: Path
) -> dict[str, str]:
    """Bind active-v3 only to one descriptor-rechecked public validator receipt."""
    authority_before, authority_before_raw = _load_canonical_json(authority_path, "PHASE2_SOURCE_AUTHORITY_INVALID")
    revocation_before, revocation_before_raw = _load_canonical_json(revocation_path, "SOURCE_AUTHORITY_REVOCATION_INVALID")
    manifest_path = bundle_root / "snapshot-manifest.json"
    registry_path = bundle_root / "fixture-registry-pr2164-v1.json"
    manifest_before, manifest_before_raw = _load_canonical_json(manifest_path, "SNAPSHOT_MANIFEST_INVALID")
    registry_before, registry_before_raw = _load_canonical_json(registry_path, "FIXTURE_REGISTRY_INVALID")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "specchoice_evidence.cli",
            "validate-phase2-source-authority",
            "--authority",
            authority_path.as_posix(),
            "--bundle",
            bundle_root.as_posix(),
            "--revocation",
            revocation_path.as_posix(),
            "--authority-mode",
            "active",
        ],
        check=False,
        capture_output=True,
        cwd=_EXPERIMENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(_EXPERIMENT_ROOT / "src")},
        text=True,
    )
    authority, authority_raw = _load_canonical_json(authority_path, "PHASE2_SOURCE_AUTHORITY_INVALID")
    revocation, revocation_raw = _load_canonical_json(revocation_path, "SOURCE_AUTHORITY_REVOCATION_INVALID")
    manifest, manifest_raw = _load_canonical_json(manifest_path, "SNAPSHOT_MANIFEST_INVALID")
    registry, registry_raw = _load_canonical_json(registry_path, "FIXTURE_REGISTRY_INVALID")
    if (
        authority_raw != authority_before_raw
        or revocation_raw != revocation_before_raw
        or manifest_raw != manifest_before_raw
        or registry_raw != registry_before_raw
    ):
        raise AdapterError("ACTIVE_SOURCE_CUTOVER_DESCRIPTOR_CHANGED_DURING_VALIDATION")
    receipt = _closed_validator_stdout(completed, "ACTIVE_SOURCE_CUTOVER_INVALID")
    verified = verify_accepted_bundle(bundle_root)
    fixtures = registry.get("fixtures") if isinstance(registry, dict) else None
    partition = {
        category: sum(isinstance(item, dict) and item.get("fixture_class") == category for item in fixtures or ())
        for category in ("positive", "negative", "candidate")
    }
    expected_receipt = {
        "eligible": True,
        "fixture_count": 11,
        "generation": verified["generation"],
        "manifest_sha256": manifest.get("snapshot_manifest_sha256"),
        "pinned_commit_sha": authority.get("pinned_commit_sha"),
        "pinned_tree_sha": authority.get("pinned_tree_sha"),
        "raw_file_count": 28,
        "registry_sha256": sha256_bytes(registry_raw),
        "root_sha256": verified["root_sha256"],
        "status": "valid",
    }
    accepted_identity = {
        "core_sha256": verified["manifest_sha256"],
        "generation": verified["generation"],
        "root_sha256": verified["root_sha256"],
        "snapshot_manifest_sha256": manifest.get("snapshot_manifest_sha256"),
    }
    if (
        receipt != expected_receipt
        or authority != authority_before
        or revocation != revocation_before
        or manifest != manifest_before
        or registry != registry_before
        or set(manifest) != {
            "accepted_publication_authorized", "content_manifest_core", "downstream_eligible",
            "external_publication_authorized", "generation", "manifest_sha256", "offline_replay_proven",
            "root_sha256", "schema_version", "snapshot_manifest_sha256", "snapshots", "status",
        }
        or manifest.get("schema_version") != "1"
        or manifest.get("status") != "accepted"
        or manifest.get("downstream_eligible") is not True
        or manifest.get("offline_replay_proven") is not True
        or manifest.get("accepted_publication_authorized") is not False
        or manifest.get("external_publication_authorized") is not False
        or manifest.get("generation") != verified["generation"]
        or manifest.get("manifest_sha256") != verified["manifest_sha256"]
        or manifest.get("root_sha256") != verified["root_sha256"]
        or set(registry) != {
            "fixture_count", "fixtures", "pinned_commit_sha", "pinned_tree_sha", "pull_request",
            "raw_file_count", "repository", "schema_version", "snapshot_id",
        }
        or registry.get("schema_version") != "1"
        or registry.get("repository") != "riscv/riscv-unified-db"
        or registry.get("snapshot_id") != "evaluation_fixtures"
        or registry.get("pull_request") != 2164
        or registry.get("pinned_commit_sha") != authority.get("pinned_commit_sha")
        or registry.get("pinned_tree_sha") != authority.get("pinned_tree_sha")
        or authority.get("schema_version") != "10"
        or authority.get("status") != "pending_cutover_v10"
        or authority.get("accepted_identity") != accepted_identity
        or authority.get("generation") != verified["generation"]
        or authority.get("manifest_sha256") != manifest.get("snapshot_manifest_sha256")
        or authority.get("root_sha256") != verified["root_sha256"]
        or authority.get("registry_sha256") != sha256_bytes(registry_raw)
        or authority.get("transition_sha256") != sha256_bytes(revocation_raw)
        or authority.get("fixture_count") != 11
        or authority.get("raw_file_count") != 28
        or not authority_raw
        or not revocation_raw
        or not isinstance(fixtures, list)
        or len(fixtures) != 11
        or partition != {"positive": 6, "negative": 4, "candidate": 1}
    ):
        raise AdapterError("ACTIVE_SOURCE_CUTOVER_RECEIPT_MISMATCH")
    return _source_identity(authority, verified)


def _bounded_yaml_fields(raw: bytes, *, source: str) -> dict[str, object]:
    """Read only known top-level scalar YAML forms; never become a general YAML parser."""
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise AdapterError("FIXTURE_TEXT_NOT_UTF8") from error
    fields: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            raise AdapterError(f"UNSUPPORTED_YAML_SYNTAX:{source}")
        key, value = line.split(":", 1)
        if not key or (key != "$schema" and not key.replace("_", "").isalnum()) or key in fields:
            raise AdapterError(f"UNSUPPORTED_YAML_SYNTAX:{source}")
        value = value.strip()
        if value in {">", "|"}:
            block: list[str] = []
            while index < len(lines) and (not lines[index] or lines[index].startswith((" ", "\t"))):
                block.append(lines[index])
                index += 1
            fields[key] = "\n".join(block).strip()
        elif value == "true":
            fields[key] = True
        elif value == "false":
            fields[key] = False
        elif value.isdecimal():
            fields[key] = int(value)
        elif value == "":
            # Nested YAML is provenance-only in this adapter.  Its indented body is
            # deliberately not interpreted, while score-bearing top-level fields stay bounded.
            fields[key] = None
        elif value.startswith("[") and value.endswith("]"):
            items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
            fields[key] = [int(item) if item.isdecimal() else item for item in items]
        elif value and not value.startswith(("{", "-")):
            fields[key] = value
        else:
            raise AdapterError(f"UNSUPPORTED_YAML_SYNTAX:{source}")
    return fields


def _source_identity(authority: dict[str, Any], verified: dict[str, str]) -> dict[str, str]:
    fields = (
        "generation", "manifest_sha256", "pinned_commit_sha", "pinned_tree_sha",
        "registry_sha256", "root_sha256",
    )
    identity = {field: str(authority[field]) for field in fields}
    if identity["generation"] != verified["generation"] or identity["root_sha256"] != verified["root_sha256"]:
        raise AdapterError("PHASE2_SOURCE_IDENTITY_MISMATCH")
    return identity


def _raw_identity(bundle_root: Path, declared: dict[str, Any]) -> tuple[RawFileIdentity, bytes]:
    path = declared.get("local_bundle_path")
    try:
        require_relative_posix_path(path)
        evidence, raw = read_authoritative_file(bundle_root, path)
        expected_length = require_byte_length(declared.get("raw_byte_length"))
        expected_hash = require_sha256(declared.get("raw_sha256"))
    except (FilesystemPolicyError, OSError, ValueError, TypeError) as error:
        raise AdapterError("RAW_PATH_OR_IDENTITY_INVALID") from error
    if evidence.file_kind != "regular_file" or evidence.byte_length != expected_length or evidence.sha256 != expected_hash:
        raise AdapterError("RAW_IDENTITY_MISMATCH")
    if len(raw) != expected_length or sha256_bytes(raw) != expected_hash:
        raise AdapterError("RAW_IDENTITY_CHANGED_DURING_READ")
    return RawFileIdentity(path=path, role=str(declared["role"]), byte_length=expected_length, sha256=expected_hash), raw


def _record_from_fixture(
    fixture: dict[str, Any], *, bundle_root: Path, source_identity: dict[str, str], adapter_version: str, rule_sha256: str, rules: dict[str, Any]
) -> CanonicalFixtureRecord:
    fixture_id = fixture.get("fixture_id")
    category = fixture.get("fixture_class")
    if not isinstance(fixture_id, str) or category not in {"positive", "negative", "candidate"} or rules["category_derivation"].get(category) != category:
        raise AdapterError("FIXTURE_DECLARATION_INVALID")
    raw_files: list[RawFileIdentity] = []
    contents: dict[str, bytes] = {}
    for declared in fixture.get("files", []):
        if not isinstance(declared, dict):
            raise AdapterError("FIXTURE_FILE_DECLARATION_INVALID")
        item, raw = _raw_identity(bundle_root, declared)
        if item.role in contents:
            raise AdapterError("RAW_ROLE_DUPLICATE")
        raw_files.append(item)
        contents[item.role] = raw
    expected_raw = contents.get("fixture_expected")
    if expected_raw is None:
        raise AdapterError("EXPECTED_FILE_MISSING")
    expected = _bounded_yaml_fields(expected_raw, source=f"{fixture_id}:expected")
    required_fields = rules["expected_fields"]["positive" if category == "positive" else "candidate_or_negative"]
    if any(field not in expected for field in required_fields):
        raise AdapterError("EXPECTED_SCORE_FIELDS_INVALID")
    if expected.get("id") != fixture_id or not isinstance(expected.get("expect_extract"), bool):
        raise AdapterError("EXPECTED_SCORE_FIELDS_INVALID")
    expect_extract = expected["expect_extract"]
    expected_count = 1 if category == "positive" else expected.get("expect_params")
    if not isinstance(expected_count, int):
        raise AdapterError("EXPECTED_SCORE_FIELDS_INVALID")
    if expected_count < 0:
        raise AdapterError("EXPECTED_PARAMETER_COUNT_INVALID")
    evidence_required = expected.get("must_have_excerpt")
    if category == "positive" and not isinstance(evidence_required, bool):
        raise AdapterError("EVIDENCE_REQUIREMENT_INVALID")
    if category != "positive":
        evidence_required = False
    names: tuple[str, ...] = ()
    score_fields: dict[str, object] = {
        "id": expected["id"], "expect_extract": expect_extract, "expect_params": expected_count,
    }
    if category == "positive":
        gold_raw = contents.get("fixture_gold")
        if gold_raw is None or not isinstance(expected.get("gold_name"), str) or expected_count != 1 or not expect_extract:
            raise AdapterError("POSITIVE_SCORE_FIELDS_INVALID")
        gold = _bounded_yaml_fields(gold_raw, source=f"{fixture_id}:gold")
        if gold.get("name") != expected["gold_name"]:
            raise AdapterError(
                "GOLD_NAME_MISMATCH",
                diagnostic=Diagnostic(
                    code="GOLD_NAME_MISMATCH",
                    severity="blocker",
                    fixture_id=fixture_id,
                    field="gold_name",
                    expected=expected["gold_name"],
                    observed=gold.get("name"),
                    source_hashes={
                        "fixture_expected": next(item.sha256 for item in raw_files if item.role == "fixture_expected"),
                        "fixture_gold": next(item.sha256 for item in raw_files if item.role == "fixture_gold"),
                    },
                ),
            )
        names = (str(gold["name"]),)
        score_fields.update({"gold_name": expected["gold_name"], "gold_name_verified": gold["name"], "must_have_excerpt": evidence_required})
    elif "fixture_gold" in contents or expected_count != 0:
        raise AdapterError("NONPOSITIVE_GOLD_OR_COUNT_INVALID")
    if category == "candidate" and not expect_extract:
        raise AdapterError("CANDIDATE_EXPECT_EXTRACT_INVALID")
    if category == "negative" and expect_extract:
        raise AdapterError("NEGATIVE_EXPECT_EXTRACT_INVALID")
    return CanonicalFixtureRecord(
        fixture_id=fixture_id,
        category=category,
        adapter_version=adapter_version,
        rule_sha256=rule_sha256,
        source_identity=source_identity,
        raw_files=tuple(sorted(raw_files, key=lambda item: (item.path, item.role))),
        original_score_bearing=score_fields,
        expect_extract=expect_extract,
        expected_parameter_count=expected_count,
        expected_parameter_names=names,
        evidence_required=evidence_required,
    )


def validate_complete_adapter_batch(
    *,
    records: tuple[CanonicalFixtureRecord, ...],
    expected_fixture_ids: tuple[str, ...],
    expected_raw_file_count: int,
    adapter_version: str,
    rule_sha256: str,
    source_identity: dict[str, str],
) -> AdapterBatch:
    """Make score eligibility an explicit finite-set and identity gate.

    The function deliberately does not repair, sort, or retain an invalid record set:
    diagnostics are audit material only, while records remain unavailable to a scorer.
    """
    diagnostics: list[Diagnostic] = []
    actual_ids = tuple(record.fixture_id for record in records)
    if actual_ids != tuple(sorted(actual_ids)):
        diagnostics.append(Diagnostic(code="ADAPTER_ORDER_NONCANONICAL", severity="blocker"))
    if set(actual_ids) != set(expected_fixture_ids) or len(actual_ids) != len(expected_fixture_ids):
        diagnostics.append(
            Diagnostic(
                code="ADAPTER_FIXTURE_SET_MISMATCH",
                severity="blocker",
                expected=list(expected_fixture_ids),
                observed=list(actual_ids),
            )
        )
    for occurrence, fixture_id in enumerate(actual_ids):
        if actual_ids.count(fixture_id) > 1:
            diagnostics.append(
                Diagnostic(
                    code="ADAPTER_FIXTURE_DUPLICATE",
                    severity="blocker",
                    fixture_id=fixture_id,
                    occurrence=occurrence + 1,
                )
            )
    raw_file_count = sum(len(record.raw_files) for record in records)
    if raw_file_count != expected_raw_file_count:
        diagnostics.append(
            Diagnostic(
                code="ADAPTER_RAW_FILE_COUNT_MISMATCH",
                severity="blocker",
                expected=expected_raw_file_count,
                observed=raw_file_count,
            )
        )
    for occurrence, record in enumerate(records, start=1):
        if record.adapter_version != adapter_version:
            diagnostics.append(
                Diagnostic(
                    code="ADAPTER_VERSION_MIXED",
                    severity="blocker",
                    fixture_id=record.fixture_id,
                    field="adapter_version",
                    occurrence=occurrence,
                    expected=adapter_version,
                    observed=record.adapter_version,
                )
            )
        if record.rule_sha256 != rule_sha256:
            diagnostics.append(
                Diagnostic(
                    code="ADAPTER_RULE_HASH_MIXED",
                    severity="blocker",
                    fixture_id=record.fixture_id,
                    field="rule_sha256",
                    occurrence=occurrence,
                    expected=rule_sha256,
                    observed=record.rule_sha256,
                )
            )
        if record.source_identity != source_identity:
            diagnostics.append(
                Diagnostic(
                    code="ADAPTER_SOURCE_IDENTITY_MIXED",
                    severity="blocker",
                    fixture_id=record.fixture_id,
                    occurrence=occurrence,
                )
            )
    invalid = any(item.severity == "blocker" for item in diagnostics)
    return AdapterBatch.from_parts(
        adapter_version=adapter_version,
        rule_sha256=rule_sha256,
        source_identity=source_identity,
        records=() if invalid else records,
        diagnostics=tuple(diagnostics),
    )


def _invalid_batch(
    *, adapter_version: str, rule_sha256: str, source_identity: dict[str, str], code: str, diagnostic: Diagnostic | None = None
) -> AdapterBatch:
    return AdapterBatch.from_parts(
        adapter_version=adapter_version,
        rule_sha256=rule_sha256,
        source_identity=source_identity,
        records=(),
        diagnostics=(diagnostic or Diagnostic(code=code, severity="blocker"),),
    )


def build_pr2164_adapter_batch(
    *,
    authority_path: Path,
    bundle_root: Path,
    rules_path: Path,
    pending_authority_path: Path | None = None,
    transition_path: Path | None = None,
    revocation_path: Path | None = None,
) -> AdapterBatch:
    """Build exactly one legacy-v2, pending-v3, or active-v3 source-mode batch."""
    rules, rules_raw = _load_canonical_json(rules_path, "ADAPTER_RULES_NOT_CANONICAL")
    required_rule_keys = {"adapter_version", "category_derivation", "expected_fields", "fixture_count", "fixture_id_sort", "gold_fields", "raw_file_count", "schema_version", "score_bearing_allowlist"}
    if set(rules) != required_rule_keys or rules.get("schema_version") != "1" or not isinstance(rules.get("adapter_version"), str) or not re.fullmatch(r"pr2164-adapter-v[1-9][0-9]*", rules["adapter_version"]):
        raise AdapterError("ADAPTER_RULES_INVALID")
    if rules.get("fixture_count") != 11 or rules.get("raw_file_count") != 28 or rules.get("fixture_id_sort") != "ascending_unicode" or rules.get("score_bearing_allowlist") != ["fixture_id", "category", "expect_extract", "expected_parameter_count", "expected_parameter_names", "evidence_required"] or rules.get("category_derivation") != {"candidate": "candidate", "negative": "negative", "positive": "positive"} or rules.get("gold_fields") != {"positive": ["name"]} or rules.get("expected_fields") != EXPECTED_FIELDS:
        raise AdapterError("ADAPTER_RULES_INVALID")
    adapter_version = rules["adapter_version"]
    rule_sha256 = sha256_bytes(rules_raw)
    source_identity: dict[str, str] = {}
    try:
        if pending_authority_path is None and transition_path is None and revocation_path is None:
            source_identity = _validate_phase2_authority(authority_path, bundle_root)
        elif pending_authority_path is not None and transition_path is not None and revocation_path is None:
            verified = verify_accepted_bundle(bundle_root)
            source_identity = _held_verified_provenance(verified)
            source_identity = _validate_pending_source_cutover(
                authority_path=authority_path,
                bundle_root=bundle_root,
                pending_authority_path=pending_authority_path,
                transition_path=transition_path,
            )
        elif pending_authority_path is None and transition_path is None and revocation_path is not None:
            verified = verify_accepted_bundle(bundle_root)
            source_identity = _held_verified_provenance(verified)
            source_identity = _validate_active_source_cutover(
                authority_path=authority_path,
                bundle_root=bundle_root,
                revocation_path=revocation_path,
            )
        else:
            raise AdapterError("SOURCE_CUTOVER_MODE_INVALID")
        registry_path = bundle_root / "fixture-registry-pr2164-v1.json"
        registry, registry_raw = _load_canonical_json(registry_path, "FIXTURE_REGISTRY_NOT_CANONICAL")
        if sha256_bytes(registry_raw) != source_identity["registry_sha256"]:
            raise AdapterError("FIXTURE_REGISTRY_SHA256_MISMATCH")
        fixtures = registry.get("fixtures")
        if not isinstance(fixtures, list) or registry.get("fixture_count") != 11 or registry.get("raw_file_count") != 28:
            raise AdapterError("FIXTURE_REGISTRY_COUNTS_INVALID")
        records = tuple(
            _record_from_fixture(
                fixture, bundle_root=bundle_root, source_identity=source_identity,
                adapter_version=adapter_version, rule_sha256=rule_sha256, rules=rules,
            )
            for fixture in fixtures
            if isinstance(fixture, dict)
        )
    except (AdapterError, OSError, ValueError) as error:
        return _invalid_batch(
            adapter_version=adapter_version,
            rule_sha256=rule_sha256,
            source_identity=source_identity,
            code=str(error).split(":", 1)[0],
            diagnostic=error.diagnostic if isinstance(error, AdapterError) else None,
        )
    return validate_complete_adapter_batch(
        records=records,
        expected_fixture_ids=tuple(str(fixture["fixture_id"]) for fixture in fixtures if isinstance(fixture, dict)),
        expected_raw_file_count=28,
        adapter_version=adapter_version,
        rule_sha256=rule_sha256,
        source_identity=source_identity,
    )


_V6_RULE_KEYS = {
    "adapter_version", "allowed_origins", "bindings", "closed",
    "expected_partition", "file_entry_fields", "fixture_contract_fields",
    "fixture_count", "raw_file_count", "schema_version",
    "score_bearing_allowlist",
}
_V6_BINDING_KEYS = {
    "adjudication_schema", "fixture_registry", "golden_predictions",
    "repair_manifest", "semantic_contract",
}
_V6_REGISTRY_KEYS = {
    "file_entries", "fixture_count", "fixture_ids",
    "ontology_decision_sha256", "partition", "raw_file_count",
    "repair_manifest", "repair_manifest_byte_length",
    "repair_manifest_sha256", "schema_version",
}
_V6_FILE_ENTRY_KEYS = {
    "byte_length", "fixture_id", "origin", "path", "role", "sha256",
}
_V6_CONTRACT_KEYS = {
    "candidate_ids", "fixture_contracts", "identity_names", "negative_ids",
    "partition", "schema_version", "surfaced_ids",
}
_V6_FIXTURE_CONTRACT_KEYS = {
    "expected_disposition", "expected_parameter_count",
    "expected_parameter_names", "expected_surfaced", "fixture_class",
    "fixture_id", "source_gold_name",
}
_V6_GOLDEN_KEYS = {
    "bindings", "outcomes", "schema_version", "score_bearing_span_count",
}
_V6_OUTCOME_KEYS = {
    "evidence_spans", "expected", "fixture_class", "fixture_id", "observed",
    "rationale",
}
_V6_EXPECTED_KEYS = {"disposition", "names", "parameter_count", "surface"}
_V6_OBSERVED_KEYS = {"name", "status", "surfaced"}
_V6_SPAN_KEYS = {
    "dimension", "end_byte", "source_path", "source_sha256", "start_byte",
    "text",
}
_V6_SCHEMA_KEYS = {
    "adjudication_fields", "evidence_span_dimensions",
    "evidence_span_fields", "no_finding", "payload_fields",
    "prediction_fields", "schema_version", "statuses", "unknown_keys",
}


def _v6_exact_keys(value: object, expected: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise AdapterError(code)
    return value


def _v6_binding(value: object, code: str) -> dict[str, object]:
    binding = _v6_exact_keys(value, {"byte_length", "path", "sha256"}, code)
    try:
        relative = require_relative_posix_path(binding["path"])
        byte_length = require_byte_length(binding["byte_length"])
        digest = require_sha256(binding["sha256"])
    except (FilesystemPolicyError, TypeError, ValueError) as error:
        raise AdapterError(code) from error
    return {
        "byte_length": byte_length,
        "path": relative.as_posix(),
        "sha256": digest,
    }


def _v6_bound_raw(
    experiment_root: Path, value: object, code: str,
) -> tuple[dict[str, object], bytes]:
    binding = _v6_binding(value, code)
    try:
        evidence, raw = read_authoritative_file(experiment_root, str(binding["path"]))
    except (FilesystemPolicyError, OSError) as error:
        raise AdapterError(code) from error
    if (
        evidence.file_kind != "regular_file"
        or evidence.byte_length != binding["byte_length"]
        or evidence.sha256 != binding["sha256"]
        or len(raw) != binding["byte_length"]
        or sha256_bytes(raw) != binding["sha256"]
    ):
        raise AdapterError(code)
    return binding, raw


def _v6_canonical_payload(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterError(code) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise AdapterError(code)
    return payload


def _v6_read_entry(
    *, experiment_root: Path, bundle_root: Path, entry: dict[str, Any], materialized_only: bool = False,
) -> tuple[RawFileIdentity, bytes]:
    if set(entry) != _V6_FILE_ENTRY_KEYS:
        raise AdapterError("V6_REGISTRY_ENTRY_SCHEMA_INVALID")
    fixture_id = entry.get("fixture_id")
    origin = entry.get("origin")
    role = entry.get("role")
    if (
        not isinstance(fixture_id, str)
        or origin not in {"accepted-v3", "repair-v5"}
        or role not in {"fixture_expected", "fixture_gold", "fixture_source"}
    ):
        raise AdapterError("V6_REGISTRY_ENTRY_INVALID")
    try:
        relative = require_relative_posix_path(entry.get("path"))
        expected_length = require_byte_length(entry.get("byte_length"))
        expected_hash = require_sha256(entry.get("sha256"))
    except (FilesystemPolicyError, TypeError, ValueError) as error:
        raise AdapterError("V6_REGISTRY_ENTRY_INVALID") from error
    path = relative.as_posix()
    if materialized_only:
        filename = {
            "fixture_source": "source.txt",
            "fixture_expected": "expected.yaml",
            "fixture_gold": "gold.yaml",
        }[str(role)]
        path = f"raw/evaluation_fixtures/{fixture_id}/{filename}"
        root = bundle_root
    elif origin == "accepted-v3":
        if not path.startswith(f"raw/evaluation_fixtures/{fixture_id}/"):
            raise AdapterError("V6_REGISTRY_ORIGIN_PATH_INVALID")
        root = bundle_root
    else:
        prefix = f"config/fixture-repairs/pr2164-semantic-gold-v5/{fixture_id}/"
        if not path.startswith(prefix):
            raise AdapterError("V6_REGISTRY_ORIGIN_PATH_INVALID")
        root = experiment_root
    try:
        evidence, raw = read_authoritative_file(root, path)
    except (FilesystemPolicyError, OSError) as error:
        raise AdapterError("V6_RAW_IDENTITY_INVALID") from error
    if (
        evidence.file_kind != "regular_file"
        or evidence.byte_length != expected_length
        or evidence.sha256 != expected_hash
        or len(raw) != expected_length
        or sha256_bytes(raw) != expected_hash
    ):
        raise AdapterError("V6_RAW_IDENTITY_MISMATCH")
    return RawFileIdentity(path, str(role), expected_length, expected_hash), raw


def _v6_parse_source_gold_name(raw: bytes, fixture_id: str) -> str:
    fields = _bounded_yaml_fields(raw, source=f"{fixture_id}:gold")
    name = fields.get("name")
    if not isinstance(name, str) or not name:
        raise AdapterError("V6_SOURCE_GOLD_NAME_INVALID")
    return name


def _v6_validate_semantic_payloads(contents: dict[str, dict[str, bytes]]) -> None:
    cache = contents["POS_DIRECT_CACHE_BLOCK"]["fixture_gold"].decode("utf-8")
    match = re.search(r"(?m)^\s+enum: \[([^\]]+)\]$", cache)
    if match is None:
        raise AdapterError("V6_CACHE_DOMAIN_INVALID")
    try:
        cache_values = [int(item.strip(), 16) for item in match.group(1).split(",")]
    except ValueError as error:
        raise AdapterError("V6_CACHE_DOMAIN_INVALID") from error
    if cache_values != [1 << exponent for exponent in range(64)]:
        raise AdapterError("V6_CACHE_DOMAIN_INVALID")

    pmp = contents["POS_DIRECT_NUM_PMP"]["fixture_gold"].decode("utf-8")
    pmp_match = re.search(r"(?m)^\s+enum: \[([^\]]+)\]$", pmp)
    if pmp_match is None:
        raise AdapterError("V6_PMP_DOMAIN_INVALID")
    try:
        pmp_values = [int(item.strip()) for item in pmp_match.group(1).split(",")]
    except ValueError as error:
        raise AdapterError("V6_PMP_DOMAIN_INVALID") from error
    if pmp_values != [0, 16, 64]:
        raise AdapterError("V6_PMP_DOMAIN_INVALID")

    geilen = contents["POS_RECALL_COUNT_GEILEN"]["fixture_gold"].decode("utf-8")
    minimum = re.search(r"(?m)^\s+minimum: ([0-9]+)$", geilen)
    maximum = re.search(r"(?m)^\s+maximum: ([0-9]+)$", geilen)
    if minimum is None or maximum is None or (int(minimum.group(1)), int(maximum.group(1))) != (0, 63):
        raise AdapterError("V6_GEILEN_DOMAIN_INVALID")


def validate_v6_outcome_contract(
    contract: object,
    golden: object,
    *,
    source_files: dict[str, dict[str, tuple[str, bytes]]] | None = None,
) -> int:
    """Validate all 11 successor outcomes and return the frozen span population S."""
    contract_value = _v6_exact_keys(contract, _V6_CONTRACT_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
    golden_value = _v6_exact_keys(golden, _V6_GOLDEN_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
    if (
        contract_value.get("schema_version") != "pr2164-semantic-gold-contract-v2"
        or golden_value.get("schema_version") != "golden-predictions-v4"
    ):
        raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
    fixture_contracts = contract_value.get("fixture_contracts")
    outcomes = golden_value.get("outcomes")
    if not isinstance(fixture_contracts, list) or not isinstance(outcomes, list) or len(fixture_contracts) != 11 or len(outcomes) != 11:
        raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
    mapped: dict[str, dict[str, Any]] = {}
    for item in fixture_contracts:
        mapping = _v6_exact_keys(item, _V6_FIXTURE_CONTRACT_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
        fixture_id = mapping.get("fixture_id")
        if not isinstance(fixture_id, str) or fixture_id in mapped:
            raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
        mapped[fixture_id] = mapping
    if list(mapped) != sorted(mapped):
        raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")

    seen: set[str] = set()
    span_count = 0
    for value in outcomes:
        outcome = _v6_exact_keys(value, _V6_OUTCOME_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
        fixture_id = outcome.get("fixture_id")
        if not isinstance(fixture_id, str) or fixture_id in seen or fixture_id not in mapped:
            raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
        seen.add(fixture_id)
        mapping = mapped[fixture_id]
        expected = _v6_exact_keys(outcome.get("expected"), _V6_EXPECTED_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
        observed = _v6_exact_keys(outcome.get("observed"), _V6_OBSERVED_KEYS, "V6_OUTCOME_CONTRACT_INVALID")
        expected_value = {
            "disposition": mapping["expected_disposition"],
            "names": mapping["expected_parameter_names"],
            "parameter_count": mapping["expected_parameter_count"],
            "surface": mapping["expected_surfaced"],
        }
        observed_value = {
            "name": mapping["expected_parameter_names"][0] if mapping["fixture_class"] == "positive" else None,
            "status": (
                "accept" if mapping["fixture_class"] == "positive"
                else "classify_out" if mapping["fixture_class"] == "candidate"
                else None
            ),
            "surfaced": mapping["expected_surfaced"],
        }
        if (
            outcome.get("fixture_class") != mapping["fixture_class"]
            or expected != expected_value
            or observed != observed_value
            or not isinstance(outcome.get("rationale"), str)
            or len(str(outcome.get("rationale"))) < 24
        ):
            raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
        spans = outcome.get("evidence_spans")
        if not isinstance(spans, list):
            raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
        expected_dimensions = (
            {"surface", "disposition"} if mapping["fixture_class"] == "candidate"
            else {"surface"} if mapping["fixture_class"] == "positive"
            else set()
        )
        dimensions: list[str] = []
        for span_value in spans:
            span = _v6_exact_keys(span_value, _V6_SPAN_KEYS, "V6_EVIDENCE_SPAN_INVALID")
            dimension = span.get("dimension")
            path = span.get("source_path")
            digest = span.get("source_sha256")
            start = span.get("start_byte")
            end = span.get("end_byte")
            text = span.get("text")
            if start == 0 and end == 1:
                raise AdapterError("V6_EVIDENCE_PLACEHOLDER_REJECTED")
            if (
                dimension not in {"surface", "disposition"}
                or not isinstance(path, str)
                or not isinstance(digest, str)
                or not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or not isinstance(text, str)
                or end <= start
                or end - start <= 1
                or len(text.strip()) < 8
            ):
                raise AdapterError("V6_EVIDENCE_SPAN_INVALID")
            if source_files is not None:
                declared = source_files.get(fixture_id, {}).get(path)
                if declared is None or declared[0] != digest:
                    raise AdapterError("V6_EVIDENCE_SOURCE_INVALID")
                raw = declared[1]
                if end > len(raw):
                    raise AdapterError("V6_EVIDENCE_RANGE_INVALID")
                try:
                    exact = raw[start:end].decode("utf-8")
                except UnicodeDecodeError as error:
                    raise AdapterError("V6_EVIDENCE_TEXT_INVALID") from error
                if exact != text:
                    raise AdapterError("V6_EVIDENCE_TEXT_INVALID")
            dimensions.append(str(dimension))
            span_count += 1
        if set(dimensions) != expected_dimensions or len(dimensions) != len(expected_dimensions):
            raise AdapterError("V6_EVIDENCE_DIMENSIONS_INVALID")
    if seen != set(mapped) or list(seen) == []:
        raise AdapterError("V6_OUTCOME_CONTRACT_INVALID")
    if golden_value.get("score_bearing_span_count") != span_count:
        raise AdapterError("V6_SPAN_POPULATION_INVALID")
    return span_count


def build_pr2164_v6_adapter_batch(
    *,
    registry_path: Path,
    rules_path: Path,
    contract_path: Path,
    golden_path: Path,
    bundle_root: Path,
    materialized_only: bool = False,
) -> AdapterBatch:
    """Build the real 29-file, 6/3/2 successor adapter without rewriting v3."""
    adapter_version = "pr2164-adapter-v3"
    rule_sha256 = ""
    source_identity: dict[str, str] = {}
    experiment_root = rules_path.parents[2]
    try:
        rules, rules_raw = _load_canonical_json(rules_path, "V6_ADAPTER_RULES_INVALID")
        rule_sha256 = sha256_bytes(rules_raw)
        if set(rules) != _V6_RULE_KEYS or rules.get("schema_version") != "3" or rules.get("closed") is not True:
            raise AdapterError("V6_ADAPTER_RULES_INVALID")
        adapter_version = rules.get("adapter_version")
        if adapter_version != "pr2164-adapter-v3":
            raise AdapterError("V6_ADAPTER_RULES_INVALID")
        if (
            rules.get("fixture_count") != 11
            or rules.get("raw_file_count") != 29
            or rules.get("expected_partition") != {"candidate": 2, "negative": 3, "positive": 6}
            or rules.get("allowed_origins") != ["accepted-v3", "repair-v5"]
            or rules.get("file_entry_fields") != sorted(_V6_FILE_ENTRY_KEYS)
            or rules.get("fixture_contract_fields") != sorted(_V6_FIXTURE_CONTRACT_KEYS)
            or rules.get("score_bearing_allowlist") != [
                "fixture_id", "category", "expect_extract",
                "expected_parameter_count", "expected_parameter_names",
                "evidence_required",
            ]
        ):
            raise AdapterError("V6_ADAPTER_RULES_INVALID")
        bindings = _v6_exact_keys(rules.get("bindings"), _V6_BINDING_KEYS, "V6_ADAPTER_BINDINGS_INVALID")
        payloads: dict[str, dict[str, Any]] = {}
        raws: dict[str, bytes] = {}
        for name in sorted(_V6_BINDING_KEYS):
            # The accepted-v6 adapter consumes the materialized bundle, not the
            # mutable repair-workspace copies.  The repair manifest remains
            # provenance in the registry, but is deliberately not opened in
            # materialized-only mode.
            if materialized_only and name == "repair_manifest":
                _v6_binding(bindings[name], "V6_ADAPTER_BINDING_MISMATCH")
                continue
            binding, raw = _v6_bound_raw(experiment_root, bindings[name], "V6_ADAPTER_BINDING_MISMATCH")
            payloads[name] = _v6_canonical_payload(raw, "V6_ADAPTER_BINDING_MISMATCH")
            raws[name] = raw
            expected_argument = {
                "fixture_registry": registry_path,
                "semantic_contract": contract_path,
                "golden_predictions": golden_path,
            }.get(name)
            if expected_argument is not None and expected_argument.absolute() != (experiment_root / str(binding["path"])).absolute():
                raise AdapterError("V6_ADAPTER_BOUND_PATH_MISMATCH")

        registry = payloads["fixture_registry"]
        contract = payloads["semantic_contract"]
        golden = payloads["golden_predictions"]
        manifest = payloads.get("repair_manifest")
        schema = payloads["adjudication_schema"]
        if (
            set(schema) != _V6_SCHEMA_KEYS
            or schema.get("schema_version") != "canonical-adjudication-v3"
            or schema.get("unknown_keys") != "reject"
            or schema.get("payload_fields") != ["adapter_batch_sha256", "predictions", "schema_version"]
            or schema.get("prediction_fields") != ["adjudication", "finding_id", "fixture_id", "rationale"]
            or schema.get("adjudication_fields") != ["evidence_spans", "parameter_status", "proposed_name", "surfaced"]
            or schema.get("evidence_span_fields") != ["dimension", "end_byte", "source_path", "source_sha256", "start_byte", "text"]
            or schema.get("evidence_span_dimensions") != ["disposition", "surface"]
            or schema.get("statuses") != ["accept", "classify_out", None]
            or schema.get("no_finding") != {"evidence_spans": [], "parameter_status": None, "proposed_name": None, "surfaced": False}
        ):
            raise AdapterError("V6_ADJUDICATION_SCHEMA_INVALID")
        if set(registry) != _V6_REGISTRY_KEYS or registry.get("schema_version") != "6":
            raise AdapterError("V6_REGISTRY_SCHEMA_INVALID")
        if (
            registry.get("fixture_count") != 11
            or registry.get("raw_file_count") != 29
            or registry.get("partition") != rules["expected_partition"]
            or registry.get("repair_manifest") != bindings["repair_manifest"]["path"]
            or registry.get("repair_manifest_byte_length") != bindings["repair_manifest"]["byte_length"]
            or registry.get("repair_manifest_sha256") != bindings["repair_manifest"]["sha256"]
        ):
            raise AdapterError("V6_REGISTRY_SCHEMA_INVALID")
        fixture_ids = registry.get("fixture_ids")
        entries = registry.get("file_entries")
        if (
            not isinstance(fixture_ids, list)
            or len(fixture_ids) != 11
            or fixture_ids != sorted(fixture_ids)
            or len(set(fixture_ids)) != 11
            or not isinstance(entries, list)
            or len(entries) != 29
        ):
            raise AdapterError("V6_REGISTRY_INVENTORY_INVALID")
        if any(not isinstance(entry, dict) or set(entry) != _V6_FILE_ENTRY_KEYS for entry in entries):
            raise AdapterError("V6_REGISTRY_ENTRY_SCHEMA_INVALID")
        if entries != sorted(
            entries,
            key=lambda item: (
                str(item["fixture_id"]), str(item["role"]), str(item["path"]),
            ),
        ):
            raise AdapterError("V6_REGISTRY_ORDER_INVALID")
        if {entry["fixture_id"] for entry in entries} != set(fixture_ids):
            raise AdapterError("V6_REGISTRY_INVENTORY_INVALID")

        repair_entries = {str(entry["path"]) for entry in entries if entry["origin"] == "repair-v5"}
        if materialized_only:
            if len(repair_entries) != 9:
                raise AdapterError("V6_REPAIR_MANIFEST_REGISTRY_MISMATCH")
        else:
            manifest_value = _v6_exact_keys(
                manifest,
                {"ontology_decision", "payload_count", "payloads", "predecessor_generation", "schema_version"},
                "V6_REPAIR_MANIFEST_INVALID",
            )
            if (
                manifest_value.get("schema_version") != "pr2164-semantic-gold-repair-manifest-v5"
                or manifest_value.get("payload_count") != 9
            ):
                raise AdapterError("V6_REPAIR_MANIFEST_INVALID")
            ontology_binding, _ = _v6_bound_raw(experiment_root, manifest_value.get("ontology_decision"), "V6_ONTOLOGY_BINDING_INVALID")
            if ontology_binding["sha256"] != registry.get("ontology_decision_sha256"):
                raise AdapterError("V6_ONTOLOGY_BINDING_INVALID")
            manifest_payloads = manifest_value.get("payloads")
            if not isinstance(manifest_payloads, list) or len(manifest_payloads) != 9:
                raise AdapterError("V6_REPAIR_MANIFEST_INVALID")
            manifest_paths: set[str] = set()
            for value in manifest_payloads:
                binding, _ = _v6_bound_raw(experiment_root, value, "V6_REPAIR_PAYLOAD_BINDING_INVALID")
                path = str(binding["path"])
                if path in manifest_paths:
                    raise AdapterError("V6_REPAIR_PAYLOAD_DUPLICATE")
                manifest_paths.add(path)
            if repair_entries != manifest_paths:
                raise AdapterError("V6_REPAIR_MANIFEST_REGISTRY_MISMATCH")

        if set(contract) != _V6_CONTRACT_KEYS or contract.get("schema_version") != "pr2164-semantic-gold-contract-v2":
            raise AdapterError("V6_SEMANTIC_CONTRACT_INVALID")
        mappings = contract.get("fixture_contracts")
        if not isinstance(mappings, list) or len(mappings) != 11:
            raise AdapterError("V6_SEMANTIC_CONTRACT_INVALID")
        if any(not isinstance(mapping, dict) or set(mapping) != _V6_FIXTURE_CONTRACT_KEYS for mapping in mappings):
            raise AdapterError("V6_SEMANTIC_MAPPING_INVALID")
        if [mapping["fixture_id"] for mapping in mappings] != fixture_ids:
            raise AdapterError("V6_SEMANTIC_MAPPING_SET_INVALID")
        mapping_by_id = {str(mapping["fixture_id"]): mapping for mapping in mappings}
        if len(mapping_by_id) != 11:
            raise AdapterError("V6_SEMANTIC_MAPPING_SET_INVALID")
        partition = {
            category: sum(mapping["fixture_class"] == category for mapping in mappings)
            for category in ("candidate", "negative", "positive")
        }
        if partition != rules["expected_partition"] or contract.get("partition") != partition:
            raise AdapterError("V6_SEMANTIC_PARTITION_INVALID")
        surfaced_ids = [mapping["fixture_id"] for mapping in mappings if mapping["expected_surfaced"] is True]
        negative_ids = [mapping["fixture_id"] for mapping in mappings if mapping["fixture_class"] == "negative"]
        candidate_ids = [mapping["fixture_id"] for mapping in mappings if mapping["fixture_class"] == "candidate"]
        identity_names = [mapping["expected_parameter_names"][0] for mapping in mappings if mapping["fixture_class"] == "positive"]
        if (
            contract.get("surfaced_ids") != surfaced_ids
            or contract.get("negative_ids") != negative_ids
            or contract.get("candidate_ids") != candidate_ids
            or contract.get("identity_names") != identity_names
        ):
            raise AdapterError("V6_SEMANTIC_CONTRACT_INVALID")

        golden_bindings = _v6_exact_keys(
            golden.get("bindings") if isinstance(golden, dict) else None,
            {"adjudication_schema", "fixture_registry", "semantic_contract"},
            "V6_GOLDEN_BINDINGS_INVALID",
        )
        for golden_name, rule_name in {
            "adjudication_schema": "adjudication_schema",
            "fixture_registry": "fixture_registry",
            "semantic_contract": "semantic_contract",
        }.items():
            if _v6_binding(golden_bindings[golden_name], "V6_GOLDEN_BINDINGS_INVALID") != _v6_binding(bindings[rule_name], "V6_GOLDEN_BINDINGS_INVALID"):
                raise AdapterError("V6_GOLDEN_BINDINGS_INVALID")

        identities: dict[str, list[RawFileIdentity]] = {fixture_id: [] for fixture_id in fixture_ids}
        contents: dict[str, dict[str, bytes]] = {fixture_id: {} for fixture_id in fixture_ids}
        paths_by_fixture: dict[str, set[str]] = {fixture_id: set() for fixture_id in fixture_ids}
        for entry in entries:
            item, raw = _v6_read_entry(
                experiment_root=experiment_root, bundle_root=bundle_root, entry=entry,
                materialized_only=materialized_only,
            )
            fixture_id = str(entry["fixture_id"])
            if item.path in paths_by_fixture[fixture_id] or item.role in contents[fixture_id]:
                raise AdapterError("V6_REGISTRY_DUPLICATE_FILE_OR_ROLE")
            paths_by_fixture[fixture_id].add(item.path)
            identities[fixture_id].append(item)
            contents[fixture_id][item.role] = raw
        _v6_validate_semantic_payloads(contents)

        records: list[CanonicalFixtureRecord] = []
        source_identity = {
            "adjudication_schema_sha256": sha256_bytes(raws["adjudication_schema"]),
            "generation": bundle_root.name,
            "golden_predictions_sha256": sha256_bytes(raws["golden_predictions"]),
            "registry_sha256": sha256_bytes(raws["fixture_registry"]),
            "repair_manifest_sha256": (
                str(bindings["repair_manifest"]["sha256"])
                if materialized_only else sha256_bytes(raws["repair_manifest"])
            ),
            "rule_sha256": rule_sha256,
            "semantic_contract_sha256": sha256_bytes(raws["semantic_contract"]),
        }
        source_files: dict[str, dict[str, tuple[str, bytes]]] = {}
        for fixture_id in fixture_ids:
            mapping = mapping_by_id[fixture_id]
            category = mapping["fixture_class"]
            expected_raw = contents[fixture_id].get("fixture_expected")
            source_raw = contents[fixture_id].get("fixture_source")
            gold_raw = contents[fixture_id].get("fixture_gold")
            if expected_raw is None or source_raw is None or category not in {"positive", "negative", "candidate"}:
                raise AdapterError("V6_FIXTURE_PAYLOAD_SET_INVALID")
            expected = _bounded_yaml_fields(expected_raw, source=f"{fixture_id}:expected")
            if expected.get("id") != fixture_id or expected.get("expect_extract") is not mapping["expected_surfaced"]:
                raise AdapterError("V6_EXPECTED_CONTRACT_MISMATCH")
            expected_names = mapping["expected_parameter_names"]
            expected_count = mapping["expected_parameter_count"]
            if (
                not isinstance(expected_names, list)
                or not isinstance(expected_count, int)
                or isinstance(expected_count, bool)
                or expected_count != len(expected_names)
            ):
                raise AdapterError("V6_SEMANTIC_MAPPING_INVALID")
            source_gold_name = mapping["source_gold_name"]
            if category == "positive":
                if gold_raw is None or mapping["expected_disposition"] != "accept" or expected_count != 1:
                    raise AdapterError("V6_POSITIVE_CONTRACT_INVALID")
                actual_gold_name = _v6_parse_source_gold_name(gold_raw, fixture_id)
                aliases = expected.get("versioned_aliases", [])
                if (
                    actual_gold_name != source_gold_name
                    or expected.get("gold_name") != source_gold_name
                    or (expected_names[0] != source_gold_name and expected_names[0] not in aliases)
                ):
                    raise AdapterError("V6_POSITIVE_IDENTITY_INVALID")
            elif category == "candidate":
                if mapping["expected_disposition"] != "classify_out" or expected_count != 0 or expected_names:
                    raise AdapterError("V6_CANDIDATE_CONTRACT_INVALID")
                if expected.get("expect_params") != 0 or expected.get("final_disposition") != "classify_out":
                    raise AdapterError("V6_CANDIDATE_CONTRACT_INVALID")
                if fixture_id == "NEG_EXT_GATED_PBMTE":
                    if gold_raw is None or _v6_parse_source_gold_name(gold_raw, fixture_id) != "PBMTE" or source_gold_name != "PBMTE":
                        raise AdapterError("V6_PBMTE_PROVENANCE_INVALID")
                elif gold_raw is not None or source_gold_name is not None:
                    raise AdapterError("V6_CANDIDATE_GOLD_INVALID")
            else:
                if gold_raw is not None or mapping["expected_disposition"] != "not_surfaced" or expected_count != 0 or expected_names or source_gold_name is not None:
                    raise AdapterError("V6_NEGATIVE_CONTRACT_INVALID")
                if expected.get("expect_params") != 0:
                    raise AdapterError("V6_NEGATIVE_CONTRACT_INVALID")
            source_item = next(item for item in identities[fixture_id] if item.role == "fixture_source")
            source_files[fixture_id] = {source_item.path: (source_item.sha256, source_raw)}
            records.append(CanonicalFixtureRecord(
                fixture_id=fixture_id,
                category=str(category),
                adapter_version=adapter_version,
                rule_sha256=rule_sha256,
                source_identity=source_identity,
                raw_files=tuple(sorted(identities[fixture_id], key=lambda item: (item.path, item.role))),
                original_score_bearing={
                    "expected_disposition": mapping["expected_disposition"],
                    "expected_surfaced": mapping["expected_surfaced"],
                    "source_gold_name": source_gold_name,
                },
                expect_extract=bool(mapping["expected_surfaced"]),
                expected_parameter_count=expected_count,
                expected_parameter_names=tuple(str(name) for name in expected_names),
                evidence_required=bool(mapping["expected_surfaced"]),
            ))

        span_count = validate_v6_outcome_contract(contract, golden, source_files=source_files)
        batch = validate_complete_adapter_batch(
            records=tuple(records),
            expected_fixture_ids=tuple(fixture_ids),
            expected_raw_file_count=29,
            adapter_version=adapter_version,
            rule_sha256=rule_sha256,
            source_identity=source_identity,
        )
        return replace(batch, score_bearing_span_count=span_count)
    except (AdapterError, OSError, TypeError, ValueError) as error:
        return _invalid_batch(
            adapter_version=adapter_version,
            rule_sha256=rule_sha256,
            source_identity=source_identity,
            code=str(error).split(":", 1)[0],
            diagnostic=error.diagnostic if isinstance(error, AdapterError) else None,
        )


_V4_EXPERIMENT = Path("experiments/specchoice-v1.3.2")
_V4_GENERATION = "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
_V4_AUTHORITY_SHA256 = "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae"
_V4_ACCEPTED_IDENTITY = {
    "core_sha256": "3a55a816904c787bd6e1ffc78c1cb90fd4503cbe30022477472e777612b6d547",
    "root_sha256": "bd75dbc97869630bbaa41dbe48c3eb1b743b7c1022bd950180b7675ecf4dd1e9",
    "snapshot_manifest_sha256": "a143334abbbc15bf455789c862ffb0ece13047348e1e91aad3f71a8a7c7cbdd0",
}
_V4_RULE_KEYS = {
    "accepted_generation", "adapter_version", "bindings", "closed",
    "fixture_count", "materialized_leaf_by_role", "output_path",
    "raw_file_count", "schema_version",
}
_V4_BINDING_KEYS = {
    "adjudication_schema", "fixture_registry", "golden_predictions",
    "legacy_rules", "semantic_contract",
}
_V4_LEAVES = {
    "fixture_expected": "expected.yaml",
    "fixture_gold": "gold.yaml",
    "fixture_source": "source.txt",
}


def _v4_paths(repository: Path) -> dict[str, Path]:
    experiment = repository / _V4_EXPERIMENT
    return {
        "authority": experiment / "phase2/source-authority.json",
        "bundle": experiment / f"bundles/accepted/{_V4_GENERATION}",
        "closure": experiment / "receipts/runtime-executable-closure-v4.json",
        "output": experiment / "reports/h1/adapter-batch-pr2164-v6.json",
        "rules": experiment / "config/measurement/pr2164-adapter-rules-v4.json",
    }


def _v4_canonical_binding(
    *, experiment_root: Path, binding: object, code: str,
) -> tuple[dict[str, object], dict[str, Any], bytes]:
    normalized, raw = _v6_bound_raw(experiment_root, binding, code)
    return normalized, _v6_canonical_payload(raw, code), raw


def _v4_gate(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
    bundle_root: Path, rules_path: Path,
) -> tuple[
    dict[str, object], bytes, dict[str, Any], bytes,
    dict[str, tuple[dict[str, object], dict[str, Any], bytes]], bytes,
]:
    """Hold the published closure, authority, and every v4 control by exact bytes."""
    paths = _v4_paths(repository)
    try:
        verified_closure = load_runtime_closure_v4(repository, runtime_closure)
    except RuntimeClosureError as error:
        raise AdapterError("RUNTIME_CLOSURE_V4_REQUIRED") from error
    try:
        if (
            authority_path.resolve(strict=True) != paths["authority"]
            or bundle_root.resolve(strict=True) != paths["bundle"]
            or rules_path.resolve(strict=True) != paths["rules"]
        ):
            raise AdapterError("FORGED_UNBOUND_GENERATION")
    except OSError as error:
        raise AdapterError("FORGED_UNBOUND_GENERATION") from error

    closure, closure_raw = _load_canonical_json(paths["closure"], "RUNTIME_CLOSURE_V4_REQUIRED")
    if closure != verified_closure or canonical_json_bytes(verified_closure) != closure_raw:
        raise AdapterError("RUNTIME_CLOSURE_V4_REQUIRED")
    future_targets = verified_closure.get("future_targets")
    if not isinstance(future_targets, list) or {
        item.get("path") for item in future_targets if isinstance(item, dict)
    }.isdisjoint({_V4_EXPERIMENT.joinpath("reports/h1/adapter-batch-pr2164-v6.json").as_posix()}):
        raise AdapterError("RUNTIME_CLOSURE_V4_TARGET_INVENTORY_INVALID")

    authority, authority_raw = _load_canonical_json(paths["authority"], "ACTIVE_AUTHORITY_MISMATCH")
    accepted = authority.get("accepted_identity")
    if (
        sha256_bytes(authority_raw) != _V4_AUTHORITY_SHA256
        or authority.get("schema_version") != "13"
        or authority.get("status") != "accepted_cutover_v13"
        or authority.get("generation") != _V4_GENERATION
        or authority.get("fixture_count") != 11
        or authority.get("raw_file_count") != 29
        or authority.get("local_only") is not True
        or authority.get("external_publication_authorized") is not False
        or not isinstance(accepted, dict)
        or accepted.get("generation") != _V4_GENERATION
        or {key: accepted.get(key) for key in _V4_ACCEPTED_IDENTITY} != _V4_ACCEPTED_IDENTITY
    ):
        raise AdapterError("ACTIVE_AUTHORITY_MISMATCH")

    rules, rules_raw = _load_canonical_json(paths["rules"], "ADAPTER_V4_RULES_INVALID")
    if (
        set(rules) != _V4_RULE_KEYS
        or rules.get("schema_version") != "4"
        or rules.get("adapter_version") != "pr2164-adapter-v4"
        or rules.get("accepted_generation") != _V4_GENERATION
        or rules.get("closed") is not True
        or rules.get("fixture_count") != 11
        or rules.get("raw_file_count") != 29
        or rules.get("output_path") != "reports/h1/adapter-batch-pr2164-v6.json"
        or rules.get("materialized_leaf_by_role") != _V4_LEAVES
    ):
        raise AdapterError("ADAPTER_V4_RULES_INVALID")
    bindings = _v6_exact_keys(rules.get("bindings"), _V4_BINDING_KEYS, "ADAPTER_V4_RULES_INVALID")
    experiment_root = repository / _V4_EXPERIMENT
    controls = {
        name: _v4_canonical_binding(
            experiment_root=experiment_root,
            binding=bindings[name],
            code="ADAPTER_V4_BINDING_INVALID",
        )
        for name in sorted(_V4_BINDING_KEYS)
    }
    _, bundle_registry_raw = _load_canonical_json(
        paths["bundle"] / "fixture-registry-pr2164-v6.json",
        "ACCEPTED_V6_BUNDLE_REGISTRY_INVALID",
    )
    if bundle_registry_raw != controls["fixture_registry"][2]:
        raise AdapterError("ACCEPTED_V6_BUNDLE_REGISTRY_INVALID")
    return verified_closure, closure_raw, authority, authority_raw, controls, rules_raw


def build_pr2164_accepted_v6_adapter_batch_v4(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
    bundle_root: Path, rules_path: Path,
) -> AdapterBatch:
    """Build the v4 batch only from the active canonical accepted-v6 bundle."""
    source_identity: dict[str, str] = {}
    try:
        repository = repository.resolve(strict=True)
        paths = _v4_paths(repository)
        verified_closure, closure_raw, _, authority_raw, controls, rules_raw = _v4_gate(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
            bundle_root=bundle_root,
            rules_path=rules_path,
        )
        batch = build_pr2164_v6_adapter_batch(
            registry_path=repository / _V4_EXPERIMENT / str(controls["fixture_registry"][0]["path"]),
            rules_path=repository / _V4_EXPERIMENT / str(controls["legacy_rules"][0]["path"]),
            contract_path=repository / _V4_EXPERIMENT / str(controls["semantic_contract"][0]["path"]),
            golden_path=repository / _V4_EXPERIMENT / str(controls["golden_predictions"][0]["path"]),
            bundle_root=paths["bundle"],
            materialized_only=True,
        )
        if not batch.valid or batch.diagnostics:
            raise AdapterError(
                batch.diagnostics[0].code if batch.diagnostics
                else "ACCEPTED_V6_MATERIALIZED_RAW_TREE_INVALID"
            )
        if (
            len(batch.records) != 11
            or sum(len(record.raw_files) for record in batch.records) != 29
            or batch.score_bearing_span_count != 10
            or any(
                raw.path != f"raw/evaluation_fixtures/{record.fixture_id}/{_V4_LEAVES[raw.role]}"
                for record in batch.records for raw in record.raw_files
            )
        ):
            raise AdapterError("ACCEPTED_V6_MATERIALIZED_RAW_TREE_INVALID")
        source_identity = {
            "accepted_bundle_path": f"bundles/accepted/{_V4_GENERATION}",
            "adapter_v4_rules_path": "config/measurement/pr2164-adapter-rules-v4.json",
            "adapter_v4_rules_sha256": sha256_bytes(rules_raw),
            "adjudication_schema_path": str(controls["adjudication_schema"][0]["path"]),
            "adjudication_schema_sha256": sha256_bytes(controls["adjudication_schema"][2]),
            "authority_path": "phase2/source-authority.json",
            "authority_sha256": sha256_bytes(authority_raw),
            "closure_byte_length": str(len(closure_raw)),
            "closure_freeze_commit": str(verified_closure["freeze_commit"]),
            "closure_path": "receipts/runtime-executable-closure-v4.json",
            "closure_sha256": sha256_bytes(closure_raw),
            "core_sha256": _V4_ACCEPTED_IDENTITY["core_sha256"],
            "generation": _V4_GENERATION,
            "golden_predictions_path": str(controls["golden_predictions"][0]["path"]),
            "golden_predictions_sha256": sha256_bytes(controls["golden_predictions"][2]),
            "legacy_rules_path": str(controls["legacy_rules"][0]["path"]),
            "legacy_rules_sha256": sha256_bytes(controls["legacy_rules"][2]),
            "registry_path": str(controls["fixture_registry"][0]["path"]),
            "registry_sha256": sha256_bytes(controls["fixture_registry"][2]),
            "root_sha256": _V4_ACCEPTED_IDENTITY["root_sha256"],
            "semantic_contract_path": str(controls["semantic_contract"][0]["path"]),
            "semantic_contract_sha256": sha256_bytes(controls["semantic_contract"][2]),
            "snapshot_manifest_sha256": _V4_ACCEPTED_IDENTITY["snapshot_manifest_sha256"],
        }
        rule_sha256 = sha256_bytes(rules_raw)
        records = tuple(
            replace(
                record,
                adapter_version="pr2164-adapter-v4",
                rule_sha256=rule_sha256,
                source_identity=source_identity,
            )
            for record in batch.records
        )
        rebuilt = AdapterBatch.from_parts(
            adapter_version="pr2164-adapter-v4",
            rule_sha256=rule_sha256,
            source_identity=source_identity,
            records=records,
            diagnostics=(),
        )
        return replace(rebuilt, score_bearing_span_count=10)
    except (AdapterError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return _invalid_batch(
            adapter_version="pr2164-adapter-v4", rule_sha256="", source_identity=source_identity,
            code=str(error).split(":", 1)[0], diagnostic=error.diagnostic if isinstance(error, AdapterError) else None,
        )


def _expected_pr2164_accepted_v6_adapter_v4(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> tuple[AdapterBatch, bytes]:
    paths = _v4_paths(repository)
    batch = build_pr2164_accepted_v6_adapter_batch_v4(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        bundle_root=paths["bundle"],
        rules_path=paths["rules"],
    )
    if not batch.valid or batch.diagnostics:
        code = batch.diagnostics[0].code if batch.diagnostics else "ADAPTER_V4_INVALID"
        raise AdapterError(code)
    return batch, batch.canonical_bytes()


def write_pr2164_accepted_v6_adapter_batch_v4(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Publish or byte-exactly resume the one fixed fresh adapter artifact."""
    repository = repository.resolve(strict=True)
    paths = _v4_paths(repository)
    batch, expected = _expected_pr2164_accepted_v6_adapter_v4(
        repository=repository, runtime_closure=runtime_closure, authority_path=authority_path,
    )
    target = paths["output"]
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise AdapterError("ADAPTER_V4_OUTPUT_KIND_INVALID")
    if target.exists():
        try:
            evidence, raw = read_authoritative_file(target.parent, target.name)
        except (FilesystemPolicyError, OSError) as error:
            raise AdapterError("ADAPTER_V4_OUTPUT_INVALID") from error
        if evidence.file_kind != "regular_file" or raw != expected:
            raise AdapterError("ADAPTER_V4_OUTPUT_DIVERGED")
        validated = validate_pr2164_accepted_v6_adapter_batch_v4(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        if validated.get("adapter_batch_sha256") != batch.adapter_batch_sha256:
            raise AdapterError("ADAPTER_V4_OUTPUT_DIVERGED")
        return {"adapter_batch_sha256": batch.adapter_batch_sha256, "status": "resumed", "valid": True}
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise AdapterError("ADAPTER_V4_OUTPUT_PARENT_INVALID")

    # Repeat the complete published-closure and authority gate immediately next
    # to the first no-replace write.  A target race is rejected by O_EXCL.
    fresh_batch, fresh = _expected_pr2164_accepted_v6_adapter_v4(
        repository=repository, runtime_closure=runtime_closure, authority_path=authority_path,
    )
    if fresh != expected:
        raise AdapterError("ADAPTER_V4_PREWRITE_DRIFT")
    try:
        _write_exact(target, fresh)
        _sync_directory(target.parent)
    except (FileExistsError, OSError) as error:
        raise AdapterError("ADAPTER_V4_OUTPUT_RACE") from error
    validate_pr2164_accepted_v6_adapter_batch_v4(
        repository=repository, runtime_closure=runtime_closure, authority_path=authority_path,
    )
    return {"adapter_batch_sha256": fresh_batch.adapter_batch_sha256, "status": "written", "valid": True}


def validate_pr2164_accepted_v6_adapter_batch_v4(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Rebuild the fixed adapter from custody roots and compare published bytes."""
    repository = repository.resolve(strict=True)
    paths = _v4_paths(repository)
    batch, expected = _expected_pr2164_accepted_v6_adapter_v4(
        repository=repository, runtime_closure=runtime_closure, authority_path=authority_path,
    )
    try:
        evidence, raw = read_authoritative_file(paths["output"].parent, paths["output"].name)
    except (FilesystemPolicyError, OSError) as error:
        raise AdapterError("ADAPTER_V4_OUTPUT_INVALID") from error
    if evidence.file_kind != "regular_file" or raw != expected:
        raise AdapterError("ADAPTER_V4_OUTPUT_DIVERGED")
    return {
        "adapter_batch_file_sha256": sha256_bytes(raw),
        "adapter_batch_sha256": batch.adapter_batch_sha256,
        "fixture_count": 11,
        "raw_file_count": 29,
        "score_bearing_span_count": 10,
        "valid": True,
    }
