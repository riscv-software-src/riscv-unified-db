# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Fail-closed construction and offline verification for candidate bundles.

Candidate construction is deliberately distinct from publication: this module only
materializes ``bundles/candidates/<generation>`` and never creates or writes an
``accepted`` namespace.  Plan 04 must supply the offline replay proof before a
separate accepted-state transition can exist.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .baseline import (
    BaselineError,
    check_current_boundary,
    check_publication_boundary,
    validate_boundary_restart,
)
from .filesystem import (
    FilesystemPolicyError,
    enumerate_authoritative_files,
    inspect_authoritative_path,
    read_authoritative_file,
    require_relative_posix_path,
)
from .git_proof import GitProofError, read_pinned_blob
from .source_contract import (
    FixtureRegistryError,
    SourceContractProposalError,
    require_accepted_publication_authorization,
    require_candidate_construction_authorization,
    require_fixture_closure_local_acceptance_authorization,
    validate_local_acceptance_decision_v10,
    validate_local_acceptance_request_v10,
    require_fixture_construction_authorization,
    require_local_accepted_generation_authorization,
    require_source_extraction_authorization,
    read_portable_fixture_blob,
    validate_source_publication_decision,
    validate_fixture_registry,
    validate_fixture_closure_decision,
    validate_fixture_closure_proposal,
    validate_fixture_construction_decision,
    validate_fixture_construction_proposal,
    verify_fixture_registry_git,
)
from .verify import (
    BundleVerificationError,
    _bundle_artifacts,
    _raw_artifacts,
    embed_verifier_artifacts,
    verify_accepted_bundle,
    verify_candidate_bundle,
)


class BundleError(ValueError):
    """Stable construction or offline-verification diagnostic."""


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BundleError(code)
    return value


def _canonical_load(path: Path, code: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError(code) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise BundleError(code)
    return payload


def _canonical_load_from_root(root: Path, relative_path: str, code: str) -> tuple[dict[str, Any], bytes]:
    """Parse one canonical control leaf from the descriptor-bound read result."""
    try:
        _, raw = read_authoritative_file(root, relative_path)
        payload = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError(code) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise BundleError(code)
    return payload, raw


def _relative(path: object, code: str) -> str:
    if not isinstance(path, str):
        raise BundleError(code)
    try:
        return require_relative_posix_path(path).as_posix()
    except FilesystemPolicyError as error:
        raise BundleError(str(error)) from error


def _file_key(entry: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(entry["snapshot_id"]),
        str(entry["upstream_path"]),
        str(entry["local_bundle_path"]),
    )


def _has_path_collision(paths: list[str]) -> bool:
    parsed = sorted(PurePosixPath(path) for path in paths)
    for index, path in enumerate(parsed):
        for other in parsed[index + 1 :]:
            if path == other or path in other.parents or other in path.parents:
                return True
    return False


def _approved_inventory(
    decision: object, proposal: object
) -> tuple[dict[str, object], dict[str, dict[str, object]], list[dict[str, object]]]:
    try:
        decision_mapping = _mapping(decision, "INVALID_SOURCE_DECISION")
        proposal_binding = _mapping(decision_mapping.get("proposal"), "SOURCE_DECISION_PROPOSAL_MISSING")
        proposal_path = _relative(proposal_binding.get("path"), "SOURCE_DECISION_PROPOSAL_BINDING_INVALID")
        validated = validate_source_publication_decision(
            decision,
            proposal,
            proposal_path=proposal_path,
            proposal_sha256=sha256_bytes(canonical_json_bytes(proposal)),
        )
        require_source_extraction_authorization(validated)
        require_candidate_construction_authorization(validated)
    except SourceContractProposalError as error:
        raise BundleError(str(error)) from error
    contract = _mapping(validated.get("approved_contract"), "CANDIDATE_CONTRACT_MISSING")
    raw_snapshots = contract.get("snapshots")
    raw_files = contract.get("consumed_files")
    if not isinstance(raw_snapshots, list) or not raw_snapshots:
        raise BundleError("SNAPSHOT_INVENTORY_EMPTY")
    if not isinstance(raw_files, list) or not raw_files:
        raise BundleError("CONSUMED_FILE_INVENTORY_EMPTY")
    snapshots: dict[str, dict[str, object]] = {}
    for raw in raw_snapshots:
        snapshot = dict(_mapping(raw, "SNAPSHOT_INVENTORY_INVALID"))
        identifier = snapshot.get("snapshot_id")
        if not isinstance(identifier, str) or not identifier or identifier in snapshots:
            raise BundleError("SNAPSHOT_INVENTORY_DUPLICATE")
        snapshots[identifier] = snapshot
    files: list[dict[str, object]] = []
    identities: set[tuple[str, str]] = set()
    local_paths: list[str] = []
    for raw in raw_files:
        entry = dict(_mapping(raw, "CONSUMED_FILE_INVENTORY_INVALID"))
        snapshot_id = entry.get("snapshot_id")
        if not isinstance(snapshot_id, str) or snapshot_id not in snapshots:
            raise BundleError("CONSUMED_FILE_SNAPSHOT_UNKNOWN")
        upstream = _relative(entry.get("upstream_path"), "UPSTREAM_PATH_INVALID")
        local = _relative(entry.get("local_bundle_path"), "LOCAL_PATH_INVALID")
        role = entry.get("experimental_role")
        if not isinstance(role, str) or not role:
            raise BundleError("CONSUMED_FILE_ROLE_MISSING")
        try:
            entry["raw_byte_length"] = require_byte_length(entry.get("raw_byte_length"))
            entry["raw_sha256"] = require_sha256(entry.get("raw_sha256"))
        except ValueError as error:
            raise BundleError("RAW_DIGEST_OR_LENGTH_INVALID") from error
        if entry.get("raw_authoritative") is not True or not isinstance(entry.get("declared_transforms"), list):
            raise BundleError("RAW_AUTHORITY_OR_TRANSFORM_INVALID")
        identity = (snapshot_id, upstream)
        if identity in identities:
            raise BundleError("CONSUMED_FILE_DUPLICATE")
        identities.add(identity)
        entry["upstream_path"] = upstream
        entry["local_bundle_path"] = local
        local_paths.append(local)
        files.append(entry)
    if _has_path_collision(local_paths):
        raise BundleError("LOCAL_PATH_COLLISION")
    return validated, snapshots, sorted(files, key=_file_key)


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exact(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _core_and_artifacts(
    snapshots: Mapping[str, Mapping[str, object]], files: list[dict[str, object]], root: Path, git_repository: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    artifacts: list[dict[str, object]] = []
    grouped: dict[str, list[dict[str, object]]] = {identifier: [] for identifier in snapshots}
    for entry in files:
        snapshot = snapshots[entry["snapshot_id"]]
        pinned = snapshot.get("pinned_commit_sha")
        if not isinstance(pinned, str):
            raise BundleError("PINNED_COMMIT_INVALID")
        try:
            raw = read_pinned_blob(git_repository, pinned, entry["upstream_path"])
        except GitProofError as error:
            try:
                raw = read_portable_fixture_blob(
                    git_repository, pinned, str(entry["local_bundle_path"])
                )
            except FixtureRegistryError:
                raise BundleError(str(error)) from error
        if len(raw) != entry["raw_byte_length"]:
            raise BundleError("RAW_BYTE_LENGTH_MISMATCH")
        if sha256_bytes(raw) != entry["raw_sha256"]:
            raise BundleError("RAW_SHA256_MISMATCH")
        local = str(entry["local_bundle_path"])
        _write_exact(root / local, raw)
        evidence = inspect_authoritative_path(root, local)
        if evidence.file_kind != "regular_file" or evidence.byte_length != len(raw) or evidence.sha256 != entry["raw_sha256"]:
            raise BundleError("STAGED_RAW_CUSTODY_MISMATCH")
        consumed = {
            "declared_transforms": entry["declared_transforms"],
            "derived_artifacts": [],
            "experimental_role": entry["experimental_role"],
            "local_bundle_path": local,
            "raw_authoritative": True,
            "raw_byte_length": len(raw),
            "raw_sha256": entry["raw_sha256"],
            "upstream_path": entry["upstream_path"],
        }
        grouped[str(entry["snapshot_id"])].append(consumed)
        artifacts.append({
            "byte_length": len(raw), "kind": "raw", "local_bundle_path": local,
            "raw_sha256": entry["raw_sha256"], "relationship": "authoritative_raw",
        })
    core_snapshots = []
    for snapshot_id in sorted(snapshots):
        snapshot = snapshots[snapshot_id]
        core_snapshots.append({
            "consumed_files": sorted(grouped[snapshot_id], key=lambda item: (item["upstream_path"], item["local_bundle_path"])),
            "pinned_commit_sha": snapshot["pinned_commit_sha"],
            "pinned_tree_sha": snapshot["pinned_tree_sha"],
            "pull_request": snapshot["pull_request"], "repository": snapshot["repository"],
            "snapshot_id": snapshot_id,
        })
    return {"schema_version": "1", "snapshots": core_snapshots}, sorted(artifacts, key=lambda item: item["local_bundle_path"])


def _root_digest(manifest_sha256: str, artifacts: list[dict[str, object]]) -> str:
    return sha256_bytes(canonical_json_bytes({
        "artifacts": sorted(artifacts, key=lambda item: str(item["local_bundle_path"])),
        "manifest_sha256": manifest_sha256,
        "root_schema_version": "1",
    }))


def _snapshot_manifest(core: dict[str, object], generation: str, manifest_sha256: str, root_sha256: str) -> dict[str, object]:
    snapshots: list[dict[str, object]] = []
    for snapshot in core["snapshots"]:
        assert isinstance(snapshot, dict)
        snapshots.append({
            **snapshot,
            "generation": generation,
            "manifest_sha256": manifest_sha256,
            "root_sha256": root_sha256,
        })
    manifest = {
        "content_manifest_core": core, "generation": generation,
        "manifest_sha256": manifest_sha256, "root_sha256": root_sha256,
        "schema_version": "1", "snapshots": snapshots, "status": "candidate",
        "downstream_eligible": False, "accepted_publication_authorized": False,
        "external_publication_authorized": False,
        "offline_replay_proven": False,
    }
    manifest["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    return manifest


def construct_candidate(
    decision: object,
    proposal: object,
    git_repository: Path,
    candidates_root: Path,
    *,
    fixture_registry_path: Path | None = None,
) -> dict[str, object]:
    """Extract exact approved blobs into a deterministic, explicitly non-accepted candidate."""
    validated, snapshots, files = _approved_inventory(decision, proposal)
    del validated
    registry_bytes: bytes | None = None
    if fixture_registry_path is not None:
        try:
            _, registry_bytes = read_authoritative_file(fixture_registry_path.parent, fixture_registry_path.name)
            registry = json.loads(registry_bytes.decode("utf-8"))
        except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BundleError("FIXTURE_REGISTRY_INVALID") from error
        if canonical_json_bytes(registry) != registry_bytes:
            raise BundleError("FIXTURE_REGISTRY_NOT_CANONICAL")
        try:
            normalized = validate_fixture_registry(registry)
            verify_fixture_registry_git(registry, git_repository)
        except FixtureRegistryError as error:
            raise BundleError(str(error)) from error
        registry_files = {
            (file["upstream_path"], file["local_bundle_path"], file["raw_byte_length"], file["raw_sha256"], file["role"])
            for fixture in normalized["fixtures"]
            for file in fixture["files"]
            if isinstance(fixture, dict) and isinstance(file, dict)
        }
        proposal_files = {
            (entry["upstream_path"], entry["local_bundle_path"], entry["raw_byte_length"], entry["raw_sha256"], entry["experimental_role"])
            for entry in files
        }
        if registry_files != proposal_files:
            raise BundleError("FIXTURE_REGISTRY_PROPOSAL_MISMATCH")
    contract = _mapping(_mapping(decision, "INVALID_SOURCE_DECISION").get("approved_contract"), "CANDIDATE_CONTRACT_MISSING")
    generation = contract.get("requested_generation_label")
    if not isinstance(generation, str) or not generation or "/" in generation or "\\" in generation:
        raise BundleError("CANDIDATE_GENERATION_INVALID")
    target = candidates_root / generation
    if target.exists() or target.is_symlink():
        raise BundleError("CANDIDATE_TARGET_EXISTS")
    candidates_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{generation}.staging-", dir=candidates_root))
    try:
        core, artifacts = _core_and_artifacts(snapshots, files, temporary, git_repository)
        if registry_bytes is not None:
            _write_exact(temporary / "fixture-registry-pr2164-v1.json", registry_bytes)
            core["fixture_closure"] = {
                "fixture_count": 11,
                "raw_file_count": 28,
                "registry_path": "fixture-registry-pr2164-v1.json",
                "registry_sha256": sha256_bytes(registry_bytes),
            }
            fixture_registry_artifact = {
                "byte_length": len(registry_bytes),
                "kind": "fixture_registry",
                "local_bundle_path": "fixture-registry-pr2164-v1.json",
                "relationship": "fixture_registry",
                "sha256": sha256_bytes(registry_bytes),
            }
        else:
            fixture_registry_artifact = None
        core["bundle_artifacts"] = embed_verifier_artifacts(temporary)
        if fixture_registry_artifact is not None:
            core["bundle_artifacts"].append(fixture_registry_artifact)
        artifacts.extend(_bundle_artifacts(core, temporary))
        core_bytes = canonical_json_bytes(core)
        manifest_sha256 = sha256_bytes(core_bytes)
        root_sha256 = _root_digest(manifest_sha256, artifacts)
        _write_exact(temporary / "content-manifest-core.json", core_bytes)
        final = _snapshot_manifest(core, generation, manifest_sha256, root_sha256)
        _write_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        verify_candidate(temporary)
        _sync_directory(temporary)
        _sync_directory(candidates_root)
        _publish_directory_no_replace(temporary, target, "CANDIDATE_TARGET_EXISTS")
        _sync_directory(candidates_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {"generation": generation, "manifest_sha256": manifest_sha256, "root_sha256": root_sha256, "status": "candidate"}


def construct_fixture_closure_candidate(
    decision: object,
    proposal: object,
    fixture_registry_path: Path,
    git_repository: Path,
    candidates_root: Path,
) -> dict[str, object]:
    """Build the v3 finite-set candidate from a compact digest-bound proposal."""
    try:
        proposal_raw = canonical_json_bytes(proposal)
        validate_fixture_closure_decision(
            decision,
            proposal,
            proposal_path="receipts/source-contract-proposal-v3-pr2164-fixture-closure-v2.json",
            proposal_sha256=sha256_bytes(proposal_raw),
        )
        bindings = validate_fixture_closure_proposal(proposal)
        _, registry_raw = read_authoritative_file(fixture_registry_path.parent, fixture_registry_path.name)
        registry = json.loads(registry_raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError, SourceContractProposalError) as error:
        raise BundleError("FIXTURE_CLOSURE_PROPOSAL_INVALID") from error
    if canonical_json_bytes(registry) != registry_raw:
        raise BundleError("FIXTURE_REGISTRY_NOT_CANONICAL")
    registry_binding = bindings["fixture_registry"]
    source_binding = bindings["base_source_snapshots"]
    assert isinstance(registry_binding, dict) and isinstance(source_binding, dict)
    if sha256_bytes(registry_raw) != registry_binding["sha256"]:
        raise BundleError("FIXTURE_REGISTRY_BINDING_MISMATCH")
    source_snapshots = fixture_registry_path.with_name("source_snapshots.json")
    try:
        _, source_raw = read_authoritative_file(source_snapshots.parent, source_snapshots.name)
        source_payload = json.loads(source_raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError("SOURCE_SNAPSHOTS_BINDING_MISMATCH") from error
    if canonical_json_bytes(source_payload) != source_raw or sha256_bytes(source_raw) != source_binding["sha256"]:
        raise BundleError("SOURCE_SNAPSHOTS_BINDING_MISMATCH")
    try:
        normalized = validate_fixture_registry(registry)
        verify_fixture_registry_git(registry, git_repository)
    except FixtureRegistryError as error:
        raise BundleError(str(error)) from error
    consumed_files = []
    for fixture in normalized["fixtures"]:
        assert isinstance(fixture, dict)
        for file in fixture["files"]:
            assert isinstance(file, dict)
            consumed_files.append({
                "declared_transforms": [],
                "experimental_role": file["role"],
                "local_bundle_path": file["local_bundle_path"],
                "raw_authoritative": True,
                "raw_byte_length": file["raw_byte_length"],
                "raw_sha256": file["raw_sha256"],
                "snapshot_id": "evaluation_fixtures",
                "upstream_path": file["upstream_path"],
                "why_consumed": "Frozen PR #2164 finite-set fixture custody input.",
            })
    generic_proposal = {
        "base_frozen_contract": {"path": "config/source_snapshots.json", "sha256": source_binding["sha256"]},
        "consumed_files": sorted(consumed_files, key=lambda item: (item["snapshot_id"], item["upstream_path"], item["local_bundle_path"])),
        "historical_rejected_receipt": {"path": "bundles/rejected/pr-2192-current-head/attempt-receipt.json", "sha256": "0" * 64},
        "proposed_contract_version": "3",
        "requested_generation_label": proposal["generation"],
        "schema_version": "1",
        "snapshots": [{
            "canonical_pr_head_sha": "22e84458c87a7ccf4c07034de1eb6d0bf9764144",
            "change_control": "versioned_correction",
            "pinned_commit_sha": "22e84458c87a7ccf4c07034de1eb6d0bf9764144",
            "pinned_tree_sha": "af003b427c66bd8ac9803a91b3bf363a1b1304d9",
            "pull_request": 2164,
            "reachability": "equal_head",
            "repository": "riscv/riscv-unified-db",
            "snapshot_id": "evaluation_fixtures",
        }],
        "status": "pending_reviewer_approval",
    }
    generic_decision = {
        "approval_scope": "candidate_construction_only",
        "approved_contract": {
            key: generic_proposal[key]
            for key in ("base_frozen_contract", "consumed_files", "historical_rejected_receipt", "proposed_contract_version", "requested_generation_label", "snapshots")
        },
        "authorization": {
            "accepted_publication_authorized": False,
            "candidate_construction_authorized": True,
            "source_extraction_authorized": True,
        },
        "proposal": {
            "path": "receipts/source-contract-proposal-v3-pr2164-fixture-closure-v2.json",
            "sha256": sha256_bytes(canonical_json_bytes(generic_proposal)),
        },
        "reviewer": {"approval_token": "authorize-candidate-construction-only"},
        "schema_version": "1",
        "state": "candidate_construction_authorized",
    }
    return construct_candidate(
        generic_decision,
        generic_proposal,
        git_repository,
        candidates_root,
        fixture_registry_path=fixture_registry_path,
    )


def _replace_exact(path: Path, content: bytes) -> None:
    """Replace a generated manifest atomically after recomputing all bound fields."""
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _native_publish_no_replace(source: Path, target: Path) -> None:
    """Atomically rename a staged directory only when its target does not exist.

    This intentionally has no `os.replace` fallback: replacing an attacker-created
    directory would undermine the immutable-generation namespace.
    """
    import ctypes
    import sys

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameatx_np", None)
        if rename is None:
            raise NotImplementedError
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-2, os.fsencode(source), -2, os.fsencode(target), 0x00000004)  # RENAME_EXCL
        if result == 0:
            return
        number = ctypes.get_errno()
        if number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FileExistsError(number, os.strerror(number), os.fspath(target))
        raise OSError(number, os.strerror(number), os.fspath(target))
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise NotImplementedError
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
        if result == 0:
            return
        number = ctypes.get_errno()
        if number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FileExistsError(number, os.strerror(number), os.fspath(target))
        if number in {errno.ENOSYS, errno.EINVAL}:
            raise NotImplementedError
        raise OSError(number, os.strerror(number), os.fspath(target))
    if os.name == "nt":
        move = ctypes.windll.kernel32.MoveFileExW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move.restype = ctypes.c_int
        if move(os.fspath(source), os.fspath(target), 0):
            return
        number = ctypes.get_last_error()
        if number in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
            raise FileExistsError(number, "target exists", os.fspath(target))
        raise OSError(number, "MoveFileExW failed", os.fspath(target))
    raise NotImplementedError


def _publish_directory_no_replace(source: Path, target: Path, collision_code: str) -> None:
    """Publish a completed generation without a check-then-replace race."""
    try:
        _native_publish_no_replace(source, target)
    except FileExistsError as error:
        raise BundleError(collision_code) from error
    except NotImplementedError as error:
        raise BundleError("ATOMIC_NO_REPLACE_UNAVAILABLE") from error
    except OSError as error:
        raise BundleError("ATOMIC_NO_REPLACE_FAILED") from error


def _run_embedded_verifier(bundle: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "verify_bundle.py"], cwd=bundle, check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise BundleError("EMBEDDED_VERIFIER_FAILED")


def construct_verifier_rooted_candidate(
    source_candidate: Path, candidates_root: Path, generation: str
) -> dict[str, object]:
    """Derive a fresh non-accepted identity with the verifier bytes in its logical root.

    The historical source candidate is recomputed before copying.  This keeps its exact
    seven approved raw blobs intact and never creates, renames, or writes an accepted path.
    """
    if not generation or "/" in generation or "\\" in generation:
        raise BundleError("CANDIDATE_GENERATION_INVALID")
    source_identity = verify_candidate(source_candidate)
    if source_identity.get("status") != "candidate":
        raise BundleError("SOURCE_CANDIDATE_NOT_ELIGIBLE")
    target = candidates_root / generation
    if target.exists() or target.is_symlink():
        raise BundleError("CANDIDATE_TARGET_EXISTS")
    candidates_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{generation}.staging-", dir=candidates_root))
    try:
        shutil.rmtree(temporary)
        shutil.copytree(source_candidate, temporary)
        (temporary / "content-manifest-core.json").unlink()
        (temporary / "snapshot-manifest.json").unlink()
        core = _canonical_load(source_candidate / "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
        if "bundle_artifacts" in core:
            raise BundleError("SOURCE_CANDIDATE_ALREADY_ROOTED")
        core["bundle_artifacts"] = embed_verifier_artifacts(temporary)
        core_bytes = canonical_json_bytes(core)
        manifest_sha256 = sha256_bytes(core_bytes)
        artifacts = _raw_artifacts(core, temporary) + _bundle_artifacts(core, temporary)
        root_sha256 = _root_digest(manifest_sha256, artifacts)
        _write_exact(temporary / "content-manifest-core.json", core_bytes)
        final = _snapshot_manifest(core, generation, manifest_sha256, root_sha256)
        _write_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        verify_candidate_bundle(temporary)
        _run_embedded_verifier(temporary)
        final["offline_replay_proven"] = True
        final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in final.items() if key != "snapshot_manifest_sha256"
        }))
        _replace_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        verify_candidate_bundle(temporary)
        _run_embedded_verifier(temporary)
        _sync_directory(temporary)
        _sync_directory(candidates_root)
        _publish_directory_no_replace(temporary, target, "CANDIDATE_TARGET_EXISTS")
        _sync_directory(candidates_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {
        "generation": generation,
        "manifest_sha256": manifest_sha256,
        "root_sha256": root_sha256,
        "status": "candidate",
    }


def construct_fixture_construction_candidate_v3(
    decision: object,
    proposal: object,
    proposal_path: str,
    predecessor: Path,
    candidates_root: Path,
) -> dict[str, object]:
    """Construct only the human-authorized verifier-rooted-v3 candidate.

    The accepted predecessor is read and copied as immutable source material.  The
    new tree is always a candidate: it receives fresh verifier-derived identities
    and never writes an accepted or authority namespace.
    """
    proposal_raw = canonical_json_bytes(proposal)
    try:
        bindings = validate_fixture_construction_proposal(proposal)
        authorized = validate_fixture_construction_decision(
            decision,
            proposal,
            proposal_path=proposal_path,
            proposal_sha256=sha256_bytes(proposal_raw),
        )
        require_fixture_construction_authorization(authorized)
        predecessor_identity = verify_accepted_bundle(predecessor)
        predecessor_binding = _mapping(
            bindings.get("predecessor_candidate"), "FIXTURE_CONSTRUCTION_PREDECESSOR_INVALID"
        )
    except (BundleVerificationError, SourceContractProposalError) as error:
        raise BundleError(str(error)) from error
    expected_relative = predecessor_binding.get("candidate_relative_path")
    try:
        experiment = Path(__file__).resolve().parents[2]
        if predecessor.resolve() != (experiment / str(expected_relative)).resolve():
            raise BundleError("FIXTURE_CONSTRUCTION_PREDECESSOR_MISMATCH")
        for control in bindings["source_controls"]:
            _, raw = read_authoritative_file(experiment, str(control["path"]))
            if sha256_bytes(raw) != control["sha256"]:
                raise BundleError("FIXTURE_CONSTRUCTION_CONTROL_MISMATCH")
        receipt = _mapping(bindings["phase_gate_receipt"], "FIXTURE_CONSTRUCTION_GATE_RECEIPT_INVALID")
        _, receipt_raw = read_authoritative_file(experiment, str(receipt["path"]))
        if sha256_bytes(receipt_raw) != receipt["sha256"]:
            raise BundleError("FIXTURE_CONSTRUCTION_GATE_RECEIPT_MISMATCH")
    except OSError as error:
        raise BundleError("FIXTURE_CONSTRUCTION_PREDECESSOR_MISMATCH") from error
    if (
        predecessor_identity.get("generation") != predecessor_binding.get("generation")
        or predecessor_identity.get("manifest_sha256") != predecessor_binding.get("core_sha256")
        or predecessor_identity.get("root_sha256") != predecessor_binding.get("root_sha256")
    ):
        raise BundleError("FIXTURE_CONSTRUCTION_PREDECESSOR_MISMATCH")
    predecessor_final = _canonical_load(predecessor / "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    if predecessor_final.get("snapshot_manifest_sha256") != predecessor_binding.get("snapshot_manifest_sha256"):
        raise BundleError("FIXTURE_CONSTRUCTION_PREDECESSOR_MISMATCH")
    target_generation = bindings["generation"]
    assert isinstance(target_generation, str)
    target = candidates_root / target_generation
    if target.exists() or target.is_symlink():
        raise BundleError("CANDIDATE_TARGET_EXISTS")
    candidates_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target_generation}.staging-", dir=candidates_root))
    try:
        shutil.rmtree(temporary)
        shutil.copytree(predecessor, temporary)
        (temporary / "content-manifest-core.json").unlink()
        (temporary / "snapshot-manifest.json").unlink()
        core, _ = _canonical_load_from_root(predecessor, "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
        registry_artifacts = [
            artifact for artifact in core.get("bundle_artifacts", [])
            if isinstance(artifact, dict) and artifact.get("kind") == "fixture_registry"
        ]
        if len(registry_artifacts) != 1:
            raise BundleError("FIXTURE_CLOSURE_REGISTRY_ARTIFACT_MISSING")
        core["bundle_artifacts"] = embed_verifier_artifacts(temporary) + registry_artifacts
        core_bytes = canonical_json_bytes(core)
        core_sha256 = sha256_bytes(core_bytes)
        artifacts = _raw_artifacts(core, temporary) + _bundle_artifacts(core, temporary)
        root_sha256 = _root_digest(core_sha256, artifacts)
        _write_exact(temporary / "content-manifest-core.json", core_bytes)
        final = _snapshot_manifest(core, target_generation, core_sha256, root_sha256)
        _write_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        verify_candidate(temporary)
        _run_embedded_verifier(temporary)
        with tempfile.TemporaryDirectory(prefix="fixture-v3-isolation-") as isolated:
            replay = Path(isolated) / "bundle"
            shutil.copytree(temporary, replay)
            result = subprocess.run(
                [sys.executable, "verify_bundle.py"],
                cwd=replay,
                env={"PATH": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or result.stdout != "bundle verified\n":
                raise BundleError("COPIED_ISOLATION_REPLAY_FAILED")
        final["offline_replay_proven"] = True
        final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes({
            key: value for key, value in final.items() if key != "snapshot_manifest_sha256"
        }))
        _replace_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        identity = verify_candidate(temporary)
        _run_embedded_verifier(temporary)
        _sync_directory(temporary)
        _sync_directory(candidates_root)
        _publish_directory_no_replace(temporary, target, "CANDIDATE_TARGET_EXISTS")
        _sync_directory(candidates_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {
        **identity,
        "copied_isolation_replay": "passed",
        "snapshot_manifest_sha256": final["snapshot_manifest_sha256"],
    }


def fixture_construction_candidate_audit(
    decision: object, proposal: object, proposal_path: str, decision_path: str, candidate: Path
) -> dict[str, object]:
    """Return the closed audit projection for the non-authoritative v3 candidate."""
    proposal_raw = canonical_json_bytes(proposal)
    decision_raw = canonical_json_bytes(decision)
    try:
        bindings = validate_fixture_construction_proposal(proposal)
        authorized = validate_fixture_construction_decision(
            decision, proposal, proposal_path=proposal_path, proposal_sha256=sha256_bytes(proposal_raw)
        )
        require_fixture_construction_authorization(authorized)
        identity = verify_candidate(candidate)
        final, _ = _canonical_load_from_root(candidate, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
        core, _ = _canonical_load_from_root(candidate, "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
    except (SourceContractProposalError, OSError) as error:
        raise BundleError(str(error)) from error
    if identity.get("generation") != bindings.get("generation"):
        raise BundleError("FIXTURE_CONSTRUCTION_GENERATION_INVALID")
    raw_artifacts = [
        {"path": item["local_bundle_path"], "sha256": item["raw_sha256"]}
        for item in _raw_artifacts(core, candidate)
    ]
    verifier_artifacts = [
        {"byte_length": item["byte_length"], "path": item["local_bundle_path"], "sha256": item["sha256"]}
        for item in core.get("bundle_artifacts", [])
        if isinstance(item, dict) and item.get("kind") == "verifier"
    ]
    if verifier_artifacts != bindings["verifier_artifacts"]:
        raise BundleError("FIXTURE_CONSTRUCTION_VERIFIER_BINDING_MISMATCH")
    return {
        "candidate": {
            "core_sha256": identity["manifest_sha256"],
            "downstream_eligible": False,
            "external_publication_authorized": False,
            "generation": identity["generation"],
            "root_sha256": identity["root_sha256"],
            "snapshot_manifest_sha256": final["snapshot_manifest_sha256"],
            "status": "candidate",
        },
        "copied_isolation_replay": {
            "original_bundle_available": False,
            "repository_modules_available": False,
            "result": "passed",
        },
        "decision": {"path": decision_path, "sha256": sha256_bytes(decision_raw)},
        "fixed_source_commit": bindings["fixed_source"]["commit"],
        "fixture_inventory": bindings["fixture_inventory"],
        "pinned_commit_sha": core["snapshots"][0]["pinned_commit_sha"],
        "pinned_tree_sha": core["snapshots"][0]["pinned_tree_sha"],
        "proposal": {"generation": bindings["generation"], "path": proposal_path, "sha256": sha256_bytes(proposal_raw)},
        "raw_artifacts": raw_artifacts,
        "schema_version": "1",
        "source_controls": bindings["source_controls"],
        "status": "candidate",
        "verifier_artifacts": verifier_artifacts,
    }


def verify_candidate(candidate: Path) -> dict[str, object]:
    """Offline recomputation of raw custody, core/root, and final non-cyclic binding."""
    core, core_raw = _canonical_load_from_root(candidate, "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
    final, _ = _canonical_load_from_root(candidate, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    if final.get("status") != "candidate" or final.get("downstream_eligible") is not False or final.get("accepted_publication_authorized") is not False or final.get("external_publication_authorized", False) is not False or not isinstance(final.get("offline_replay_proven"), bool):
        raise BundleError("CANDIDATE_ACCEPTED_STATE_FORBIDDEN")
    actual_manifest = sha256_bytes(core_raw)
    if final.get("manifest_sha256") != actual_manifest:
        raise BundleError("MANIFEST_SHA256_MISMATCH")
    without_self = dict(final)
    supplied_self = without_self.pop("snapshot_manifest_sha256", None)
    if supplied_self != sha256_bytes(canonical_json_bytes(without_self)):
        raise BundleError("SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH")
    if final.get("content_manifest_core") != core:
        raise BundleError("SNAPSHOT_CORE_PROJECTION_MISMATCH")
    generation, root_sha256 = final.get("generation"), final.get("root_sha256")
    if not isinstance(generation, str) or not isinstance(root_sha256, str):
        raise BundleError("SNAPSHOT_BINDING_MISSING")
    artifacts: list[dict[str, object]] = []
    snapshots = core.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise BundleError("SNAPSHOT_INVENTORY_EMPTY")
    for core_snapshot, final_snapshot in zip(snapshots, final.get("snapshots", []), strict=True):
        if not isinstance(core_snapshot, dict) or not isinstance(final_snapshot, dict):
            raise BundleError("SNAPSHOT_MANIFEST_INVALID")
        if final_snapshot.get("generation") != generation or final_snapshot.get("root_sha256") != root_sha256 or final_snapshot.get("manifest_sha256") != actual_manifest:
            raise BundleError("SNAPSHOT_BINDING_MISMATCH")
        if {key: value for key, value in final_snapshot.items() if key not in {"generation", "root_sha256", "manifest_sha256"}} != core_snapshot:
            raise BundleError("SNAPSHOT_CORE_PROJECTION_MISMATCH")
        for file in core_snapshot.get("consumed_files", []):
            if not isinstance(file, dict):
                raise BundleError("CONSUMED_FILE_INVENTORY_INVALID")
            local = _relative(file.get("local_bundle_path"), "LOCAL_PATH_INVALID")
            try:
                evidence, raw = read_authoritative_file(candidate, local)
            except FilesystemPolicyError as error:
                if str(error) == "AUTHORITATIVE_FILE_MISSING":
                    raise BundleError("STAGED_RAW_CUSTODY_MISMATCH") from error
                raise BundleError(str(error)) from error
            except OSError as error:
                raise BundleError("STAGED_RAW_CUSTODY_MISMATCH") from error
            if evidence.file_kind != "regular_file" or evidence.byte_length != file.get("raw_byte_length") or evidence.sha256 != file.get("raw_sha256"):
                raise BundleError("STAGED_RAW_CUSTODY_MISMATCH")
            artifacts.append({"byte_length": evidence.byte_length, "kind": "raw", "local_bundle_path": local, "raw_sha256": evidence.sha256, "relationship": "authoritative_raw"})
    if "bundle_artifacts" in core:
        try:
            artifacts.extend(_bundle_artifacts(core, candidate))
        except Exception as error:
            raise BundleError(str(error)) from error
    expected = {"content-manifest-core.json", "snapshot-manifest.json"}
    expected.update(str(item["local_bundle_path"]) for item in artifacts)
    try:
        actual = {
            relative for relative in enumerate_authoritative_files(candidate)
            if "__pycache__" not in relative.split("/") and not relative.endswith(".pyc")
        }
    except FilesystemPolicyError as error:
        raise BundleError(str(error)) from error
    if expected - actual:
        raise BundleError("BUNDLE_MISSING_FILE")
    if actual - expected:
        raise BundleError("BUNDLE_EXTRA_FILE")
    recomputed = _root_digest(actual_manifest, sorted(artifacts, key=lambda item: item["local_bundle_path"]))
    if recomputed != root_sha256:
        raise BundleError("ROOT_SHA256_MISMATCH")
    # Keep fixture-closure candidates and embedded accepted verification on the
    # same finite-set rule. Generic historical candidates need no bundled verifier.
    if "fixture_closure" in core:
        try:
            verify_candidate_bundle(candidate)
        except BundleVerificationError as error:
            raise BundleError(str(error)) from error
    return {"generation": generation, "manifest_sha256": actual_manifest, "root_sha256": root_sha256, "status": "candidate"}


def publish_accepted(decision: object) -> None:
    """Deliberately closed publication boundary until Plan 04 proves offline replay."""
    try:
        require_accepted_publication_authorization(_mapping(decision, "INVALID_SOURCE_DECISION"))
    except SourceContractProposalError as error:
        raise BundleError(str(error)) from error
    raise BundleError("OFFLINE_REPLAY_PROOF_REQUIRED")


def accept_local_candidate(
    decision: object, candidate: Path, accepted_root: Path, *, allow_historical: bool = False
) -> dict[str, object]:
    """Atomically pin one already-rooted candidate for local MVP use only.

    The copied directory retains the candidate's bytes and its non-external manifest state.
    Local acceptability is therefore represented only by the separately hash-bound decision;
    no external publication state is synthesized or implied.
    """
    identity = verify_candidate(candidate)
    final = _canonical_load(candidate / "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    snapshot_sha256 = final.get("snapshot_manifest_sha256")
    if not isinstance(snapshot_sha256, str):
        raise BundleError("SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH")
    try:
        require_local_accepted_generation_authorization(
            _mapping(decision, "INVALID_LOCAL_ACCEPTANCE_DECISION"),
            identity,
            snapshot_sha256,
            allow_historical=allow_historical,
        )
    except SourceContractProposalError as error:
        raise BundleError(str(error)) from error
    generation = identity["generation"]
    assert isinstance(generation, str)
    target = accepted_root / generation
    if target.exists() or target.is_symlink():
        raise BundleError("LOCAL_ACCEPTED_TARGET_EXISTS")
    accepted_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{generation}.staging-", dir=accepted_root))
    try:
        shutil.rmtree(temporary)
        shutil.copytree(candidate, temporary)
        if (temporary / "content-manifest-core.json").read_bytes() != (
            candidate / "content-manifest-core.json"
        ).read_bytes() or (temporary / "snapshot-manifest.json").read_bytes() != (
            candidate / "snapshot-manifest.json"
        ).read_bytes():
            raise BundleError("LOCAL_ACCEPTED_COPY_IDENTITY_MISMATCH")
        if verify_candidate(temporary) != identity:
            raise BundleError("LOCAL_ACCEPTED_COPY_IDENTITY_MISMATCH")
        _run_embedded_verifier(temporary)
        _sync_directory(temporary)
        _sync_directory(accepted_root)
        _publish_directory_no_replace(temporary, target, "LOCAL_ACCEPTED_TARGET_EXISTS")
        _sync_directory(accepted_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return identity


def _fixture_closure_current_v7_basis() -> dict[str, object]:
    """Resolve the only valid lineage and live boundary from this implementation."""
    experiment = Path(__file__).resolve().parents[2]
    repository = experiment.parents[1]
    baseline = experiment / "baselines/phase-start-v7-fixture-closure.json"
    allowlist = experiment / "config/boundary_allowlist-v7-fixture-closure.json"
    restart = experiment / "receipts/boundary-restart-v7-fixture-closure.json"
    previous = experiment / "baselines/phase-start-v6-fixture-closure.json"
    try:
        projection = validate_boundary_restart(baseline, previous, allowlist, restart)
        from .publication import has_publication_manifest

        publication_mode = has_publication_manifest(repository)
        boundary = (
            check_publication_boundary(repository)
            if publication_mode
            else check_current_boundary(repository, baseline)
        )
    except (BaselineError, OSError) as error:
        raise BundleError(str(error)) from error
    if boundary.blocking_violations:
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_BOUNDARY_BLOCKING")
    if not boundary.reviewed_revision:
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_REVIEWED_REVISION_INVALID")
    return {
        "allowlist_sha256": projection["allowlist"]["sha256"],
        "baseline_sha256": (
            projection["baseline"]["sha256"]
            if publication_mode
            else boundary.baseline_sha256
        ),
        "restart_receipt_sha256": projection["incident_receipt"]["sha256"],
        "reviewed_revision": boundary.reviewed_revision,
    }


def accept_fixture_closure_candidate(
    candidate: Path, accepted_root: Path, decision_path: Path
) -> dict[str, object]:
    """Promote only the complete v3 candidate into a fresh local accepted tree.

    This is a local lifecycle transition, not an external publication operation.  The
    candidate is verified before copying and never changed.  The accepted tree gets a
    freshly rooted core/manifest because its embedded verifier and lifecycle state are
    part of its own content address.
    """
    if not isinstance(decision_path, Path):
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID")
    try:
        _, decision_raw = read_authoritative_file(decision_path.parent, decision_path.name)
        decision = json.loads(decision_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID") from error
    if not isinstance(decision, dict) or canonical_json_bytes(decision) != decision_raw:
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_DECISION_NOT_CANONICAL")
    v7_basis = _fixture_closure_current_v7_basis()
    identity = verify_candidate(candidate)
    generation = identity.get("generation")
    if generation != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2":
        raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_GENERATION_INVALID")
    final_candidate, _ = _canonical_load_from_root(candidate, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    snapshot_sha256 = final_candidate.get("snapshot_manifest_sha256")
    if not isinstance(snapshot_sha256, str):
        raise BundleError("SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH")
    try:
        _, registry_raw = read_authoritative_file(candidate, "fixture-registry-pr2164-v1.json")
        registry_sha256 = sha256_bytes(registry_raw)
        require_fixture_closure_local_acceptance_authorization(
            decision, identity, snapshot_sha256, registry_sha256, v7_basis
        )
    except (OSError, SourceContractProposalError) as error:
        raise BundleError(str(error)) from error
    target = accepted_root / generation
    if target.exists() or target.is_symlink():
        raise BundleError("LOCAL_ACCEPTED_TARGET_EXISTS")
    accepted_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{generation}.staging-", dir=accepted_root))
    try:
        shutil.rmtree(temporary)
        shutil.copytree(candidate, temporary)
        (temporary / "content-manifest-core.json").unlink()
        (temporary / "snapshot-manifest.json").unlink()
        core, _ = _canonical_load_from_root(candidate, "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
        closure = core.get("fixture_closure")
        if not isinstance(closure, dict) or closure.get("fixture_count") != 11 or closure.get("raw_file_count") != 28:
            raise BundleError("FIXTURE_CLOSURE_ACCEPTANCE_INCOMPLETE")
        registry_artifacts = [
            artifact for artifact in core.get("bundle_artifacts", [])
            if isinstance(artifact, dict) and artifact.get("kind") == "fixture_registry"
        ]
        if len(registry_artifacts) != 1:
            raise BundleError("FIXTURE_CLOSURE_REGISTRY_ARTIFACT_MISSING")
        core["bundle_artifacts"] = embed_verifier_artifacts(temporary) + registry_artifacts
        core_bytes = canonical_json_bytes(core)
        manifest_sha256 = sha256_bytes(core_bytes)
        _write_exact(temporary / "content-manifest-core.json", core_bytes)
        artifacts = _raw_artifacts(core, temporary) + _bundle_artifacts(core, temporary)
        root_sha256 = _root_digest(manifest_sha256, artifacts)
        snapshots = [
            {**snapshot, "generation": generation, "manifest_sha256": manifest_sha256, "root_sha256": root_sha256}
            for snapshot in core["snapshots"]
        ]
        final: dict[str, object] = {
            "accepted_publication_authorized": False,
            "content_manifest_core": core,
            "downstream_eligible": True,
            "external_publication_authorized": False,
            "generation": generation,
            "manifest_sha256": manifest_sha256,
            "offline_replay_proven": True,
            "root_sha256": root_sha256,
            "schema_version": "1",
            "snapshots": snapshots,
            "status": "accepted",
        }
        final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(final))
        _write_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        # The embedded verifier re-parses the frozen registry and proves its
        # bidirectional equality with the raw manifest inventory before acceptance.
        verified = verify_accepted_bundle(temporary)
        _run_embedded_verifier(temporary)
        _sync_directory(temporary)
        _sync_directory(accepted_root)
        _publish_directory_no_replace(temporary, target, "LOCAL_ACCEPTED_TARGET_EXISTS")
        _sync_directory(accepted_root)
        return verified
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _accepted_v3_projection(candidate: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Compute the exact accepted-v3 identity without publishing any state."""
    identity = verify_candidate(candidate)
    if identity.get("generation") != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3":
        raise BundleError("LOCAL_ACCEPTANCE_V10_GENERATION_INVALID")
    core, _ = _canonical_load_from_root(candidate, "content-manifest-core.json", "CONTENT_MANIFEST_CORE_INVALID")
    final_candidate, _ = _canonical_load_from_root(candidate, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    if not isinstance(final_candidate.get("snapshot_manifest_sha256"), str):
        raise BundleError("SNAPSHOT_MANIFEST_SELF_DIGEST_MISMATCH")
    accepted_final = {
        "accepted_publication_authorized": False, "content_manifest_core": core,
        "downstream_eligible": True, "external_publication_authorized": False,
        "generation": identity["generation"], "manifest_sha256": identity["manifest_sha256"],
        "offline_replay_proven": True, "root_sha256": identity["root_sha256"], "schema_version": "1",
        "snapshots": [
            {**snapshot, "generation": identity["generation"], "manifest_sha256": identity["manifest_sha256"], "root_sha256": identity["root_sha256"]}
            for snapshot in core["snapshots"]
        ], "status": "accepted",
    }
    projection = {
        "core_sha256": identity["manifest_sha256"], "generation": identity["generation"],
        "root_sha256": identity["root_sha256"], "snapshot_manifest_sha256": sha256_bytes(canonical_json_bytes(accepted_final)),
    }
    return projection, core, final_candidate


def build_local_acceptance_request_v10(
    candidate: Path, audit_path: Path, construction_decision_path: Path, proposal_path: Path, active_authority_path: Path,
) -> dict[str, object]:
    """Build a closed machine request; it cannot grant local acceptance or publication."""
    projected, _, _ = _accepted_v3_projection(candidate)
    audit = _canonical_load(audit_path, "LOCAL_ACCEPTANCE_REQUEST_V10_AUDIT_INVALID")
    construction = _canonical_load(construction_decision_path, "LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID")
    proposal = _canonical_load(proposal_path, "LOCAL_ACCEPTANCE_REQUEST_V10_PROPOSAL_INVALID")
    active_raw = active_authority_path.read_bytes()
    active = _canonical_load(active_authority_path, "LOCAL_ACCEPTANCE_REQUEST_V10_AUTHORITY_INVALID")
    candidate_identity = audit.get("candidate")
    if not isinstance(candidate_identity, dict) or candidate_identity.get("status") != "candidate":
        raise BundleError("LOCAL_ACCEPTANCE_REQUEST_V10_AUDIT_INVALID")
    candidate_binding = {
        key: candidate_identity.get(key)
        for key in ("core_sha256", "generation", "root_sha256", "snapshot_manifest_sha256")
    }
    candidate_final, _ = _canonical_load_from_root(candidate, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    if candidate_binding != {
        "core_sha256": projected["core_sha256"], "generation": projected["generation"],
        "root_sha256": projected["root_sha256"], "snapshot_manifest_sha256": candidate_final["snapshot_manifest_sha256"],
    }:
        raise BundleError("LOCAL_ACCEPTANCE_REQUEST_V10_CANDIDATE_MISMATCH")
    verifiers = audit.get("verifier_artifacts")
    if not isinstance(verifiers, list):
        raise BundleError("LOCAL_ACCEPTANCE_REQUEST_V10_AUDIT_INVALID")
    request = {
        "authorization": {"external_publication_authorized": False, "local_acceptance_decision_authorized": False},
        "candidate": candidate_binding,
        "construction": {
            "audit": {"path": "receipts/fixture-closure-candidate-audit-v3.json", "sha256": sha256_bytes(audit_path.read_bytes())},
            "decision": {"path": "receipts/source-contract-decision-v3-pr2164-fixture-closure-verifier-rooted-v3.json", "sha256": sha256_bytes(construction_decision_path.read_bytes())},
            "proposal": {"path": "receipts/source-contract-proposal-v3-pr2164-fixture-closure-verifier-rooted-v3.json", "sha256": sha256_bytes(proposal_path.read_bytes())},
        },
        "fixed_source_commit": audit.get("fixed_source_commit"),
        "fixture_inventory": audit.get("fixture_inventory"),
        "phase_gate_receipt": {"result": "clean", "sha256": sha256_bytes(active_raw)},
        "projected_accepted": projected,
        "protected_path_baseline": {"commit": proposal.get("protected_path_baseline", {}).get("commit"), "result": "clean"},
        "requested_targets": {
            "accepted_bundle": f"bundles/accepted/{projected['generation']}",
            "historical_authority": "phase2/source-authority-v9-historical.json",
            "pending_authority": "phase2/source-authority-v10-pending.json",
            "transition": "receipts/pending/fixture-closure-transition-v2-to-v3.json",
        },
        "schema_version": "10", "source_controls": audit.get("source_controls"),
        "status": "pending_independent_local_acceptance", "verifier_artifacts": verifiers,
    }
    validate_local_acceptance_request_v10(request)
    if active.get("schema_version") != "1":
        raise BundleError("LOCAL_ACCEPTANCE_REQUEST_V10_AUTHORITY_INVALID")
    return request


def _stage_held_candidate_inventory(candidate: Path, destination: Path) -> None:
    """Copy a complete candidate only from descriptor-read bytes held in memory."""
    try:
        inventory = {
            relative: read_authoritative_file(candidate, relative)[1]
            for relative in sorted(enumerate_authoritative_files(candidate))
        }
    except (FilesystemPolicyError, OSError) as error:
        raise BundleError(str(error)) from error
    for relative, raw in inventory.items():
        _write_exact(destination / relative, raw)


def accept_fixture_closure_candidate_v10(
    request_path: Path, decision_path: Path, candidate: Path, accepted_root: Path,
) -> dict[str, object]:
    """Materialize a reviewed v3 successor only in the caller-selected namespace."""
    request_raw = request_path.read_bytes()
    decision_raw = decision_path.read_bytes()
    request = _canonical_load(request_path, "LOCAL_ACCEPTANCE_REQUEST_V10_INVALID")
    decision = _canonical_load(decision_path, "LOCAL_ACCEPTANCE_DECISION_V10_INVALID")
    validated_decision = validate_local_acceptance_decision_v10(decision, request, sha256_bytes(request_raw))
    if validated_decision["decision"] != "accept":
        raise BundleError("LOCAL_ACCEPTANCE_V10_REJECTED")
    expected_projection = validate_local_acceptance_request_v10(request)["projected_accepted"]
    target = accepted_root / str(expected_projection["generation"])
    if target.exists() or target.is_symlink():
        raise BundleError("LOCAL_ACCEPTED_TARGET_EXISTS")
    accepted_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{expected_projection['generation']}.staging-", dir=accepted_root))
    try:
        shutil.rmtree(temporary)
        _stage_held_candidate_inventory(candidate, temporary)
        projected, core, _ = _accepted_v3_projection(temporary)
        if projected != expected_projection:
            raise BundleError("LOCAL_ACCEPTANCE_V10_PROJECTION_MISMATCH")
        (temporary / "snapshot-manifest.json").unlink()
        final = {
            "accepted_publication_authorized": False, "content_manifest_core": core,
            "downstream_eligible": True, "external_publication_authorized": False,
            "generation": projected["generation"], "manifest_sha256": projected["core_sha256"],
            "offline_replay_proven": True, "root_sha256": projected["root_sha256"], "schema_version": "1",
            "snapshots": [
                {**snapshot, "generation": projected["generation"], "manifest_sha256": projected["core_sha256"], "root_sha256": projected["root_sha256"]}
                for snapshot in core["snapshots"]
            ], "status": "accepted",
        }
        final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(final))
        if final["snapshot_manifest_sha256"] != projected["snapshot_manifest_sha256"]:
            raise BundleError("LOCAL_ACCEPTANCE_V10_PROJECTION_MISMATCH")
        _write_exact(temporary / "snapshot-manifest.json", canonical_json_bytes(final))
        verified = verify_accepted_bundle(temporary)
        _run_embedded_verifier(temporary)
        _sync_directory(temporary)
        _sync_directory(accepted_root)
        _publish_directory_no_replace(temporary, target, "LOCAL_ACCEPTED_TARGET_EXISTS")
        _sync_directory(accepted_root)
        return verified
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
