# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Construction-only Git object and PR-head proof for source snapshots.

This module intentionally has no role in offline bundle verification.  Its only
authority is the local object graph fetched from the canonical PR-head ref.
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, sha256_bytes
from .filesystem import FilesystemPolicyError, require_relative_posix_path


class GitProofError(ValueError):
    """A deterministic source-construction diagnostic."""


GitRunner = Callable[[tuple[str, ...]], subprocess.CompletedProcess[bytes]]


def run_git(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[bytes]:
    """Run Git without leaking platform output into canonical proof records."""
    return subprocess.run(arguments, check=False, capture_output=True)


def _execute(arguments: Sequence[str], runner: GitRunner) -> subprocess.CompletedProcess[bytes]:
    try:
        return runner(tuple(arguments))
    except FileNotFoundError as error:
        raise GitProofError("GIT_CAPABILITY_UNAVAILABLE") from error
    except OSError as error:
        raise GitProofError("GIT_SUBPROCESS_FAILED") from error


def _git_at(repository: Path, *arguments: str) -> tuple[str, ...]:
    return ("git", "-C", os.fspath(repository), *arguments)


def initialize_disposable_bare_repository(repository: Path, *, runner: GitRunner = run_git) -> None:
    """Create a never-reused bare scratch repository for construction evidence."""
    if repository.exists() or repository.is_symlink():
        raise GitProofError("GIT_SCRATCH_ALREADY_EXISTS")
    result = _execute(("git", "init", "--bare", os.fspath(repository)), runner)
    if result.returncode != 0:
        raise GitProofError("GIT_SCRATCH_INITIALIZATION_FAILED")


def _local_pr_ref(pull_request: int) -> str:
    if isinstance(pull_request, bool) or not isinstance(pull_request, int) or pull_request < 1:
        raise GitProofError("INVALID_PULL_REQUEST")
    return f"refs/specchoice/pr/{pull_request}"


def fetch_canonical_pr_head(
    repository: Path,
    canonical_remote: str,
    pull_request: int,
    *,
    runner: GitRunner = run_git,
) -> str:
    """Fetch exactly one canonical PR head ref into the disposable repository."""
    if not isinstance(canonical_remote, str) or not canonical_remote:
        raise GitProofError("INVALID_CANONICAL_REMOTE")
    local_ref = _local_pr_ref(pull_request)
    remote_ref = f"refs/pull/{pull_request}/head:{local_ref}"
    result = _execute(
        _git_at(repository, "fetch", "--no-tags", canonical_remote, remote_ref),
        runner,
    )
    if result.returncode != 0:
        raise GitProofError("PR_REF_UNAVAILABLE")
    resolved = _execute(_git_at(repository, "rev-parse", local_ref), runner)
    if resolved.returncode != 0:
        raise GitProofError("PR_REF_MISSING")
    return resolved.stdout.decode("ascii", "strict").strip()


def fetch_pinned_commit(
    repository: Path,
    canonical_remote: str,
    pinned_commit_sha: str,
    *,
    runner: GitRunner = run_git,
) -> None:
    """Fetch the exact frozen object without substituting a branch or PR head."""
    pinned = _require_hex_sha(pinned_commit_sha, "INVALID_PINNED_COMMIT_SHA")
    result = _execute(_git_at(repository, "fetch", "--no-tags", canonical_remote, pinned), runner)
    if result.returncode != 0:
        raise GitProofError("PIN_COMMIT_UNAVAILABLE")


def _require_hex_sha(value: object, code: str) -> str:
    if not isinstance(value, str) or len(value) != 40:
        raise GitProofError(code)
    try:
        int(value, 16)
    except ValueError as error:
        raise GitProofError(code) from error
    return value


def prove_pinned_snapshot(
    repository: Path,
    pull_request: int,
    pinned_commit_sha: str,
    *,
    runner: GitRunner = run_git,
) -> dict[str, str]:
    """Require commit/tree objects and equality-or-ancestry for one PR identity."""
    pinned = _require_hex_sha(pinned_commit_sha, "INVALID_PINNED_COMMIT_SHA")
    local_ref = _local_pr_ref(pull_request)
    head_result = _execute(_git_at(repository, "rev-parse", local_ref), runner)
    if head_result.returncode != 0:
        raise GitProofError("PR_REF_MISSING")
    resolved_head_sha = head_result.stdout.decode("ascii", "strict").strip()
    _require_hex_sha(resolved_head_sha, "INVALID_RESOLVED_HEAD_SHA")

    commit_result = _execute(_git_at(repository, "cat-file", "-e", f"{pinned}^{{commit}}"), runner)
    if commit_result.returncode != 0:
        raise GitProofError("PIN_COMMIT_MISSING")
    tree_result = _execute(_git_at(repository, "rev-parse", f"{pinned}^{{tree}}"), runner)
    if tree_result.returncode != 0:
        raise GitProofError("PIN_TREE_MISSING")
    pinned_tree_sha = tree_result.stdout.decode("ascii", "strict").strip()
    _require_hex_sha(pinned_tree_sha, "PIN_TREE_MISSING")

    ancestry = _execute(
        _git_at(repository, "merge-base", "--is-ancestor", pinned, resolved_head_sha),
        runner,
    )
    if ancestry.returncode == 1:
        raise GitProofError("PR_PIN_NOT_REACHABLE")
    if ancestry.returncode != 0:
        raise GitProofError("GIT_SUBPROCESS_FAILED")
    return {
        "pinned_commit_sha": pinned,
        "pinned_tree_sha": pinned_tree_sha,
        "pull_request": str(pull_request),
        "resolved_head_sha": resolved_head_sha,
        "verification_result": "passed",
    }


def read_pinned_path(
    repository: Path,
    pinned_commit_sha: str,
    upstream_path: str,
    *,
    runner: GitRunner = run_git,
) -> bytes:
    """Return exact Git-object bytes only after an independent proof has passed."""
    pinned = _require_hex_sha(pinned_commit_sha, "INVALID_PINNED_COMMIT_SHA")
    try:
        relative = require_relative_posix_path(upstream_path).as_posix()
    except FilesystemPolicyError as error:
        raise GitProofError(str(error)) from error
    result = _execute(_git_at(repository, "show", f"{pinned}:{relative}"), runner)
    if result.returncode != 0:
        raise GitProofError("REQUESTED_PATH_MISSING")
    return result.stdout


def read_pinned_blob(
    repository: Path,
    pinned_commit_sha: str,
    upstream_path: str,
    *,
    runner: GitRunner = run_git,
) -> bytes:
    """Return exact bytes only when ``pin:path`` is a verified Git blob."""
    pinned = _require_hex_sha(pinned_commit_sha, "INVALID_PINNED_COMMIT_SHA")
    try:
        relative = require_relative_posix_path(upstream_path).as_posix()
    except FilesystemPolicyError as error:
        raise GitProofError(str(error)) from error
    object_ref = f"{pinned}:{relative}"
    object_type = _execute(_git_at(repository, "cat-file", "-t", object_ref), runner)
    if object_type.returncode != 0:
        raise GitProofError("REQUESTED_PATH_MISSING")
    if object_type.stdout.decode("ascii", "strict").strip() != "blob":
        raise GitProofError("REQUESTED_PATH_NOT_REGULAR_FILE")
    result = _execute(_git_at(repository, "show", object_ref), runner)
    if result.returncode != 0:
        raise GitProofError("REQUESTED_PATH_MISSING")
    return result.stdout


def validate_consumed_file_request(request: object) -> list[dict[str, object]]:
    """Require an explicit reviewer-owned inventory; never infer a whole tree."""
    if not isinstance(request, dict) or request.get("schema_version") != "1":
        raise GitProofError("INVALID_CONSUMED_FILE_INVENTORY")
    entries = request.get("entries")
    if request.get("state") == "unresolved":
        raise GitProofError("CONSUMED_FILE_INVENTORY_UNRESOLVED")
    if not isinstance(entries, list):
        raise GitProofError("INVALID_CONSUMED_FILE_INVENTORY")
    if not entries:
        raise GitProofError("CONSUMED_FILE_INVENTORY_EMPTY")
    normalized: list[dict[str, object]] = []
    identities: set[tuple[str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise GitProofError("INVALID_CONSUMED_FILE_INVENTORY")
        snapshot_id = entry.get("snapshot_id")
        upstream_path = entry.get("upstream_path")
        local_path = entry.get("local_bundle_path")
        role = entry.get("experimental_role")
        required = (snapshot_id, upstream_path, local_path, role)
        if not all(isinstance(value, str) and value for value in required):
            raise GitProofError("INVALID_CONSUMED_FILE_INVENTORY")
        try:
            upstream = require_relative_posix_path(upstream_path).as_posix()
            local = require_relative_posix_path(local_path).as_posix()
        except FilesystemPolicyError as error:
            raise GitProofError(str(error)) from error
        identity = (snapshot_id, upstream, local)
        if identity in identities:
            raise GitProofError("DUPLICATE_CONSUMED_FILE_INVENTORY")
        identities.add(identity)
        normalized.append(
            {
                "declared_transforms": entry.get("declared_transforms", []),
                "experimental_role": role,
                "local_bundle_path": local,
                "snapshot_id": snapshot_id,
                "upstream_path": upstream,
            }
        )
    return sorted(
        normalized,
        key=lambda item: (str(item["snapshot_id"]), str(item["upstream_path"])),
    )


def rejected_attempt_receipt(
    *,
    snapshot: dict[str, object],
    error: GitProofError,
    resolved_head_sha: str | None,
    pinned_tree_sha: str | None,
) -> dict[str, object]:
    """Return canonical-receipt content for a failed construction attempt only."""
    pull_request = snapshot["pull_request"]
    pinned_commit_sha = snapshot["pinned_commit_sha"]
    return {
        "attempt_id": f"pr-{pull_request}-current-head",
        "diagnostic": str(error),
        "expected": {"pinned_commit_sha": pinned_commit_sha},
        "observed": {
            "pinned_tree_sha": pinned_tree_sha,
            "resolved_head_sha": resolved_head_sha,
        },
        "pull_request": pull_request,
        "repository": snapshot["repository"],
        "schema_version": "1",
        "status": "rejected",
        "tool_versions": {"git": _git_version(), "python": platform.python_version()},
        "verification": {"pr_ref": f"refs/pull/{pull_request}/head", "result": "rejected"},
    }


def _git_version() -> str:
    result = run_git(("git", "--version"))
    if result.returncode != 0:
        return "unavailable"
    return result.stdout.decode("ascii", "replace").strip()


def write_rejected_attempt(destination: Path, receipt: dict[str, object]) -> str:
    """Persist only canonical rejected evidence, refusing to overwrite an attempt."""
    if destination.exists() or destination.is_symlink():
        raise GitProofError("REJECTED_ATTEMPT_ALREADY_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(receipt)
    with destination.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256_bytes(encoded)


def audit_snapshots(
    config: dict[str, object], rejected_directory: Path
) -> tuple[list[dict[str, object]], int]:
    """Audit every frozen identity in configured order and persist rejected attempts."""
    snapshots = config.get("snapshots")
    remote = config.get("canonical_remote")
    if not isinstance(snapshots, list) or not isinstance(remote, str):
        raise GitProofError("INVALID_SOURCE_SNAPSHOTS_CONFIG")
    results: list[dict[str, object]] = []
    failures = 0
    with tempfile.TemporaryDirectory(prefix="specchoice-git-proof-") as temporary:
        repository = Path(temporary) / "proof.git"
        initialize_disposable_bare_repository(repository)
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                raise GitProofError("INVALID_SOURCE_SNAPSHOTS_CONFIG")
            pull_request = snapshot.get("pull_request")
            pinned = snapshot.get("pinned_commit_sha")
            if not isinstance(pull_request, int) or not isinstance(pinned, str):
                raise GitProofError("INVALID_SOURCE_SNAPSHOTS_CONFIG")
            resolved: str | None = None
            tree: str | None = None
            try:
                resolved = fetch_canonical_pr_head(repository, remote, pull_request)
                fetch_pinned_commit(repository, remote, pinned)
                proof = prove_pinned_snapshot(repository, pull_request, pinned)
                results.append({"snapshot_id": snapshot.get("snapshot_id"), **proof})
            except GitProofError as error:
                failures += 1
                tree_result = _execute(
                    _git_at(repository, "rev-parse", f"{pinned}^{{tree}}"), run_git
                )
                if tree_result.returncode == 0:
                    tree = tree_result.stdout.decode("ascii", "strict").strip()
                receipt = rejected_attempt_receipt(
                    snapshot=snapshot,
                    error=error,
                    resolved_head_sha=resolved,
                    pinned_tree_sha=tree,
                )
                destination = (
                    rejected_directory / f"pr-{pull_request}-current-head" / "attempt-receipt.json"
                )
                receipt_sha256 = write_rejected_attempt(destination, receipt)
                results.append(
                    {
                        "diagnostic": str(error),
                        "receipt_sha256": receipt_sha256,
                        "snapshot_id": snapshot.get("snapshot_id"),
                        "status": "rejected",
                    }
                )
    return results, failures
