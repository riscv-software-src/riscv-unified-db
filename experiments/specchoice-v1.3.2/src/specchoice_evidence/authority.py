# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Reusable semantic validation for Phase 2 source-authority bytes."""

from __future__ import annotations

from pathlib import Path

from .bundle import verify_accepted_bundle
from .canonical import sha256_bytes
from .verify import _load_canonical


class AuthorityValidationError(ValueError):
    """Stable failure for a source-authority semantic mismatch."""


def v10_identity(
    verified: dict[str, object], manifest: dict[str, object],
) -> dict[str, object]:
    return {
        "core_sha256": verified["manifest_sha256"],
        "generation": verified["generation"],
        "root_sha256": verified["root_sha256"],
        "snapshot_manifest_sha256": manifest["snapshot_manifest_sha256"],
    }


def validate_v10_authority(
    authority: dict[str, object],
    raw: bytes,
    verified: dict[str, object],
    manifest: dict[str, object],
    registry_sha256: str,
    revocation_raw: bytes | None,
) -> None:
    required = {
        "accepted_identity", "decision_sha256", "external_publication_authorized",
        "fixture_count", "generation", "local_only", "manifest_sha256",
        "pinned_commit_sha", "pinned_tree_sha", "raw_file_count", "registry_sha256",
        "request_sha256", "root_sha256", "schema_version", "status",
        "transition_sha256",
    }
    if (
        set(authority) != required
        or authority.get("schema_version") != "10"
        or authority.get("status") != "pending_cutover_v10"
    ):
        raise AuthorityValidationError("SOURCE_CUTOVER_PENDING_INVALID")
    snapshot = manifest["content_manifest_core"]["snapshots"][0]
    expected = {
        "fixture_count": 11,
        "generation": verified["generation"],
        "manifest_sha256": manifest["snapshot_manifest_sha256"],
        "pinned_commit_sha": snapshot["pinned_commit_sha"],
        "pinned_tree_sha": snapshot["pinned_tree_sha"],
        "raw_file_count": 28,
        "registry_sha256": registry_sha256,
        "root_sha256": verified["root_sha256"],
    }
    if (
        authority.get("external_publication_authorized") is not False
        or authority.get("local_only") is not True
        or any(authority.get(key) != value for key, value in expected.items())
        or authority.get("accepted_identity") != v10_identity(verified, manifest)
    ):
        raise AuthorityValidationError("SOURCE_CUTOVER_PENDING_INVALID")
    if (
        revocation_raw is None
        or sha256_bytes(revocation_raw) != authority.get("transition_sha256")
    ):
        raise AuthorityValidationError("SOURCE_CUTOVER_REVOCATION_MISMATCH")


def validate_phase2_source_authority(
    authority: dict[str, object],
    raw: bytes,
    bundle: Path,
    revocation_raw: bytes | None,
    authority_mode: str | None,
) -> dict[str, object]:
    """Validate held authority bytes against the accepted bundle semantics."""
    verified = verify_accepted_bundle(bundle)
    manifest, _ = _load_canonical(
        bundle, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID"
    )
    _, registry_raw = _load_canonical(
        bundle, "fixture-registry-pr2164-v1.json", "FIXTURE_REGISTRY_INVALID"
    )
    registry_sha256 = sha256_bytes(registry_raw)
    snapshot = manifest["content_manifest_core"]["snapshots"][0]
    expected = {
        "fixture_count": 11,
        "generation": verified["generation"],
        "manifest_sha256": manifest["snapshot_manifest_sha256"],
        "pinned_commit_sha": snapshot["pinned_commit_sha"],
        "pinned_tree_sha": snapshot["pinned_tree_sha"],
        "raw_file_count": 28,
        "registry_sha256": registry_sha256,
        "root_sha256": verified["root_sha256"],
    }
    if authority_mode is None:
        if (
            authority.get("schema_version") != "1"
            or authority.get("external_publication_authorized") is not False
            or authority.get("local_only") is not True
            or any(authority.get(key) != value for key, value in expected.items())
        ):
            raise AuthorityValidationError("PHASE2_SOURCE_AUTHORITY_MISMATCH")
        return {"status": "valid", **expected}
    if authority.get("schema_version") == "1":
        if (
            authority.get("external_publication_authorized") is not False
            or authority.get("local_only") is not True
            or any(authority.get(key) != value for key, value in expected.items())
        ):
            raise AuthorityValidationError("PHASE2_SOURCE_AUTHORITY_MISMATCH")
        if authority_mode == "active" and revocation_raw is not None:
            raise AuthorityValidationError("SOURCE_AUTHORITY_V2_REVOKED")
        return (
            {"eligible": False, "status": "historical_valid", **expected}
            if authority_mode == "historical-inspection"
            else {"eligible": True, "status": "valid", **expected}
        )
    validate_v10_authority(
        authority, raw, verified, manifest, registry_sha256, revocation_raw
    )
    if authority_mode != "active":
        return {"eligible": False, "status": "historical_valid", **expected}
    return {"eligible": True, "status": "valid", **expected}
