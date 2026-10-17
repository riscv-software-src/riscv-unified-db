# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Git-free verification for a complete accepted source bundle.

This module is deliberately copied, with its two small stdlib-only dependencies, into
each accepted generation.  It never discovers a repository or executes a process.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .filesystem import FilesystemPolicyError, inspect_authoritative_path, require_relative_posix_path


class BundleVerificationError(ValueError):
    """Stable failure emitted before accepted contents are exposed."""


def _load_canonical(root: Path, relative_path: str, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        evidence = inspect_authoritative_path(root, relative_path)
        if evidence.file_kind != "regular_file":
            raise BundleVerificationError(code)
        raw = (root / relative_path).read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleVerificationError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise BundleVerificationError(code)
    return value, raw


def _raw_artifacts(core: dict[str, Any], root: Path) -> list[dict[str, object]]:
    snapshots = core.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise BundleVerificationError("SNAPSHOT_INVENTORY_EMPTY")
    artifacts: list[dict[str, object]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            raise BundleVerificationError("SNAPSHOT_MANIFEST_INVALID")
        for field in ("repository", "snapshot_id", "pinned_commit_sha", "pinned_tree_sha"):
            if not isinstance(snapshot.get(field), str) or not snapshot[field]:
                raise BundleVerificationError("SNAPSHOT_IDENTITY_INVALID")
        if isinstance(snapshot.get("pull_request"), bool) or not isinstance(snapshot.get("pull_request"), int):
            raise BundleVerificationError("SNAPSHOT_IDENTITY_INVALID")
        files = snapshot.get("consumed_files")
        if not isinstance(files, list) or not files:
            raise BundleVerificationError("CONSUMED_FILE_INVENTORY_INVALID")
        for entry in files:
            if not isinstance(entry, dict):
                raise BundleVerificationError("CONSUMED_FILE_INVENTORY_INVALID")
            try:
                local = require_relative_posix_path(str(entry.get("local_bundle_path"))).as_posix()
                length = require_byte_length(entry.get("raw_byte_length"))
                digest = require_sha256(entry.get("raw_sha256"))
                evidence = inspect_authoritative_path(root, local)
            except (FilesystemPolicyError, ValueError) as error:
                raise BundleVerificationError("RAW_INVENTORY_INVALID") from error
            if evidence.file_kind != "regular_file" or evidence.byte_length != length or evidence.sha256 != digest:
                raise BundleVerificationError("STAGED_RAW_CUSTODY_MISMATCH")
            artifacts.append(
                {
                    "byte_length": length,
                    "kind": "raw",
                    "local_bundle_path": local,
                    "raw_sha256": digest,
                    "relationship": "authoritative_raw",
                }
            )
    return artifacts


def _bundle_artifacts(core: dict[str, Any], root: Path) -> list[dict[str, object]]:
    records = core.get("bundle_artifacts")
    if not isinstance(records, list) or not records:
        raise BundleVerificationError("VERIFIER_ARTIFACTS_MISSING")
    artifacts: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise BundleVerificationError("VERIFIER_ARTIFACT_INVALID")
        try:
            local = require_relative_posix_path(str(record.get("local_bundle_path"))).as_posix()
            length = require_byte_length(record.get("byte_length"))
            digest = require_sha256(record.get("sha256"))
            evidence = inspect_authoritative_path(root, local)
        except (FilesystemPolicyError, ValueError) as error:
            raise BundleVerificationError("VERIFIER_ARTIFACT_INVALID") from error
        if record.get("kind") != "verifier" or record.get("relationship") != "bundle_verifier":
            raise BundleVerificationError("VERIFIER_ARTIFACT_INVALID")
        if evidence.file_kind != "regular_file" or evidence.byte_length != length or evidence.sha256 != digest:
            raise BundleVerificationError("VERIFIER_ARTIFACT_TAMPERED")
        artifacts.append(
            {
                "byte_length": length,
                "kind": "verifier",
                "local_bundle_path": local,
                "raw_sha256": digest,
                "relationship": "bundle_verifier",
            }
        )
    return artifacts


def _root_digest(manifest_sha256: str, artifacts: list[dict[str, object]]) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "artifacts": sorted(artifacts, key=lambda item: str(item["local_bundle_path"])),
                "manifest_sha256": manifest_sha256,
                "root_schema_version": "1",
            }
        )
    )


def verify_bundle(bundle_root: Path, expected_status: str | None = None) -> dict[str, str]:
    """Recompute a rooted candidate or accepted generation from bundle-relative files."""
    core, core_bytes = _load_canonical(bundle_root, "content-manifest-core.json", "CORE_INVALID")
    final, _ = _load_canonical(bundle_root, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    status = final.get("status")
    if status not in {"accepted", "candidate"}:
        raise BundleVerificationError("GENERATION_STATUS_INVALID")
    if expected_status is not None and status != expected_status:
        raise BundleVerificationError(
            "GENERATION_NOT_ACCEPTED" if expected_status == "accepted" else "GENERATION_NOT_CANDIDATE"
        )
    if status == "accepted":
        if final.get("downstream_eligible") is not True or final.get("offline_replay_proven") is not True:
            raise BundleVerificationError("GENERATION_NOT_ACCEPTED")
    elif (
        final.get("downstream_eligible") is not False
        or final.get("accepted_publication_authorized") is not False
        or not isinstance(final.get("offline_replay_proven"), bool)
    ):
        raise BundleVerificationError("CANDIDATE_ACCEPTED_STATE_FORBIDDEN")
    generation = final.get("generation")
    root_sha256 = final.get("root_sha256")
    manifest_sha256 = final.get("manifest_sha256")
    if not isinstance(generation, str) or not generation:
        raise BundleVerificationError("SNAPSHOT_BINDING_MISSING")
    try:
        require_sha256(root_sha256)
        require_sha256(manifest_sha256)
    except ValueError as error:
        raise BundleVerificationError("SNAPSHOT_BINDING_MISSING") from error
    if sha256_bytes(core_bytes) != manifest_sha256:
        raise BundleVerificationError("MANIFEST_SHA256_MISMATCH")
    if final.get("content_manifest_core") != core:
        raise BundleVerificationError("SNAPSHOT_CORE_PROJECTION_MISMATCH")
    final_snapshots = final.get("snapshots")
    core_snapshots = core.get("snapshots")
    if not isinstance(final_snapshots, list) or not isinstance(core_snapshots, list):
        raise BundleVerificationError("SNAPSHOT_MANIFEST_INVALID")
    if len(final_snapshots) != len(core_snapshots):
        raise BundleVerificationError("SNAPSHOT_MANIFEST_INVALID")
    for core_snapshot, final_snapshot in zip(core_snapshots, final_snapshots, strict=True):
        if not isinstance(core_snapshot, dict) or not isinstance(final_snapshot, dict):
            raise BundleVerificationError("SNAPSHOT_MANIFEST_INVALID")
        if any(final_snapshot.get(key) != value for key, value in {
            "generation": generation, "root_sha256": root_sha256, "manifest_sha256": manifest_sha256
        }.items()):
            raise BundleVerificationError("SNAPSHOT_BINDING_MISMATCH")
        projected = {key: value for key, value in final_snapshot.items() if key not in {
            "generation", "root_sha256", "manifest_sha256"
        }}
        if projected != core_snapshot:
            raise BundleVerificationError("SNAPSHOT_CORE_PROJECTION_MISMATCH")
    supplied_self = final.get("snapshot_manifest_sha256")
    projected_final = dict(final)
    projected_final.pop("snapshot_manifest_sha256", None)
    if supplied_self != sha256_bytes(canonical_json_bytes(projected_final)):
        raise BundleVerificationError("SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH")
    recomputed_root = _root_digest(manifest_sha256, _raw_artifacts(core, bundle_root) + _bundle_artifacts(core, bundle_root))
    if recomputed_root != root_sha256:
        raise BundleVerificationError("ROOT_SHA256_MISMATCH")
    return {"generation": generation, "manifest_sha256": manifest_sha256, "root_sha256": root_sha256, "status": status}


def verify_accepted_bundle(bundle_root: Path) -> dict[str, str]:
    """Recompute an accepted generation entirely from bundle-relative regular files."""
    return verify_bundle(bundle_root, "accepted")


def verify_candidate_bundle(bundle_root: Path) -> dict[str, str]:
    """Recompute a non-accepted rooted candidate without granting eligibility."""
    return verify_bundle(bundle_root, "candidate")


def embed_verifier_artifacts(destination: Path) -> list[dict[str, object]]:
    """Copy the minimal stdlib verifier into a staged generation and return its records."""
    package = destination / "verifier/specchoice_evidence"
    package.mkdir(parents=True, exist_ok=True)
    source_package = Path(__file__).parent
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in ("canonical.py", "filesystem.py", "verify.py"):
        shutil.copy2(source_package / name, package / name)
    entry = destination / "verify_bundle.py"
    entry.write_text(
        "from pathlib import Path\nimport sys\n"
        "sys.path.insert(0, str(Path(__file__).parent / 'verifier'))\n"
        "from specchoice_evidence.verify import BundleVerificationError, verify_bundle\n"
        "try:\n    verify_bundle(Path(__file__).parent)\n"
        "except BundleVerificationError as error:\n    print(str(error), file=sys.stderr)\n    raise SystemExit(2)\n"
        "print('bundle verified')\n",
        encoding="utf-8",
    )
    records: list[dict[str, object]] = []
    paths = [entry, *(package / name for name in ("__init__.py", "canonical.py", "filesystem.py", "verify.py"))]
    for path in sorted(paths):
        relative = path.relative_to(destination).as_posix()
        raw = path.read_bytes()
        records.append({
            "byte_length": len(raw),
            "kind": "verifier",
            "local_bundle_path": relative,
            "relationship": "bundle_verifier",
            "sha256": sha256_bytes(raw),
        })
    return records


def create_synthetic_accepted_bundle(candidate: Path, destination: Path, generation: str) -> dict[str, str]:
    """Create a disposable accepted fixture; production publication is intentionally absent."""
    if destination.exists() or destination.is_symlink():
        raise BundleVerificationError("ACCEPTED_TARGET_EXISTS")
    shutil.copytree(candidate, destination)
    core, _ = _load_canonical(destination, "content-manifest-core.json", "CORE_INVALID")
    core["bundle_artifacts"] = embed_verifier_artifacts(destination)
    core_bytes = canonical_json_bytes(core)
    (destination / "content-manifest-core.json").write_bytes(core_bytes)
    manifest_sha256 = sha256_bytes(core_bytes)
    artifacts = _raw_artifacts(core, destination) + _bundle_artifacts(core, destination)
    root_sha256 = _root_digest(manifest_sha256, artifacts)
    snapshots = []
    for snapshot in core["snapshots"]:
        assert isinstance(snapshot, dict)
        snapshots.append({**snapshot, "generation": generation, "manifest_sha256": manifest_sha256, "root_sha256": root_sha256})
    final: dict[str, Any] = {
        "content_manifest_core": core,
        "downstream_eligible": True,
        "generation": generation,
        "manifest_sha256": manifest_sha256,
        "offline_replay_proven": True,
        "root_sha256": root_sha256,
        "schema_version": "1",
        "snapshots": snapshots,
        "status": "accepted",
    }
    final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(final))
    (destination / "snapshot-manifest.json").write_bytes(canonical_json_bytes(final))
    return verify_accepted_bundle(destination)
