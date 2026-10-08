# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Immutable phase-start baseline and five-way boundary classification."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .filesystem import FilesystemPolicyError, inspect_authoritative_path


class BaselineError(ValueError):
    """Stable baseline validation or capture diagnostic."""


CLASSIFICATIONS = {
    "allowed_phase_change",
    "preexisting_unrelated",
    "new_out_of_boundary",
    "modified_out_of_boundary",
    "deleted_out_of_boundary",
}

DS_STORE_DIAGNOSTIC = "DS_STORE_IGNORED_OS_METADATA"


@dataclass(frozen=True)
class CommittedPathChange:
    path: str
    change_kind: str
    old_mode: str
    new_mode: str
    old_object: str
    new_object: str
    commit: str = ""


@dataclass(frozen=True)
class BoundaryResult:
    baseline_sha256: str
    classifications: list[dict[str, object]]
    blocking_violations: int
    history_start_commit: str | None = None
    reviewed_revision: str | None = None
    unique_changed_path_count: int = 0


def _is_ds_store(path: str) -> bool:
    return path.rsplit("/", 1)[-1] == ".DS_Store"


def _relative(path: str) -> str:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise BaselineError("PATH_ESCAPE_DETECTED")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise BaselineError("PATH_ESCAPE_DETECTED")
    return path


def path_is_allowed(path: str, allowlist: dict[str, object]) -> bool:
    """Use exact paths or a slash-terminated root; never prefix matching."""
    candidate = _relative(path)
    roots = allowlist.get("roots", [])
    exact_files = allowlist.get("exact_files", [])
    if not isinstance(roots, list) or not isinstance(exact_files, list):
        raise BaselineError("INVALID_ALLOWLIST")
    return candidate in exact_files or any(
        isinstance(root, str) and root.endswith("/") and candidate.startswith(root) for root in roots
    )


def load_baseline(path: Path) -> tuple[dict[str, Any], str]:
    """Load and validate immutable canonical baseline bytes and field invariants."""
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BaselineError("INVALID_BASELINE_JSON") from error
    if canonical_json_bytes(payload) != raw:
        raise BaselineError("BASELINE_NOT_CANONICAL")
    if payload.get("schema_version") not in {"1", "3"}:
        raise BaselineError("UNSUPPORTED_BASELINE_SCHEMA")
    worktree = payload.get("worktree")
    if not isinstance(worktree, dict):
        raise BaselineError("INVALID_BASELINE")
    for section in ("tracked_changes", "untracked_files"):
        entries = worktree.get(section)
        if not isinstance(entries, list):
            raise BaselineError("INVALID_BASELINE")
        paths: list[str] = []
        for item in entries:
            if not isinstance(item, dict):
                raise BaselineError("INVALID_BASELINE")
            paths.append(_relative(str(item.get("path", ""))))
            if item.get("file_kind") == "regular_file":
                require_byte_length(item.get("byte_length"))
                require_sha256(item.get("sha256"))
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise BaselineError("BASELINE_PATHS_NOT_SORTED")
    allowlist = payload.get("allowlist")
    if not isinstance(allowlist, dict):
        raise BaselineError("INVALID_ALLOWLIST")
    return payload, sha256_bytes(raw)


def capture_baseline(destination: Path, payload: dict[str, Any]) -> str:
    """Create a new canonical generation; never overwrite an existing baseline."""
    if destination.exists() or destination.is_symlink():
        raise BaselineError("BASELINE_ALREADY_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(payload)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except FileExistsError as error:
        raise BaselineError("BASELINE_ALREADY_EXISTS") from error
    return sha256_bytes(encoded)


def create_restart_baseline(
    previous_path: Path,
    destination: Path,
    *,
    previous_reference: str,
    reason_code: str,
    remediation: dict[str, object],
) -> tuple[str, str]:
    """Create a D-15 successor without recapturing or reclassifying start state."""
    previous, previous_sha256 = load_baseline(previous_path)
    _relative(previous_reference)
    if not isinstance(reason_code, str) or not reason_code:
        raise BaselineError("INVALID_RESTART_REASON")
    if not isinstance(remediation, dict):
        raise BaselineError("INVALID_RESTART_REMEDIATION")
    payload = json.loads(canonical_json_bytes(previous).decode("utf-8"))
    payload["restart"] = {
        "previous_baseline": {"path": previous_reference, "sha256": previous_sha256},
        "reason_code": reason_code,
        "remediation": remediation,
        "schema_version": "1",
    }
    return capture_baseline(destination, payload), previous_sha256


def validate_restart_lineage(baseline_path: Path, previous_path: Path) -> tuple[str, str]:
    """Prove a successor retained its predecessor's attribution inventory exactly."""
    current, current_sha256 = load_baseline(baseline_path)
    previous, previous_sha256 = load_baseline(previous_path)
    restart = current.get("restart")
    if not isinstance(restart, dict):
        raise BaselineError("RESTART_LINEAGE_MISSING")
    predecessor = restart.get("previous_baseline")
    if not isinstance(predecessor, dict) or predecessor.get("sha256") != previous_sha256:
        raise BaselineError("RESTART_LINEAGE_MISMATCH")
    for key in ("allowlist", "file_kind_policy", "index", "repository", "worktree"):
        if current.get(key) != previous.get(key):
            raise BaselineError("RESTART_RECLASSIFICATION_DETECTED")
    return current_sha256, previous_sha256


def _git_paths(root: Path, *arguments: str) -> set[str]:
    output = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return {item.decode("utf-8", "surrogateescape") for item in output.split(b"\0") if item}


def _commit(root: Path, revision: str) -> str:
    try:
        value = subprocess.run(["git", "-C", os.fspath(root), "rev-parse", "--verify", f"{revision}^{{commit}}"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("ascii").strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise BaselineError("BOUNDARY_HISTORY_REVISION_INVALID") from error
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise BaselineError("BOUNDARY_HISTORY_REVISION_INVALID")
    return value


def require_full_commit(root: Path, revision: object) -> str:
    """Resolve an immutable, canonical commit spelling for frozen evidence."""
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise BaselineError("BOUNDARY_REVIEWED_REVISION_NOT_FULL")
    resolved = _commit(root, revision)
    if resolved != revision:
        raise BaselineError("BOUNDARY_REVIEWED_REVISION_MOVED")
    return resolved


def capture_committed_history(root: Path, start_commit: str, reviewed_revision: str) -> list[CommittedPathChange]:
    """Capture every A/M/D/T event between two commits without net-diff collapse.

    The traversal walks every commit reachable from ``reviewed`` but not ``start`` in
    reverse topological order.  For merge commits, the event is the deterministic
    first-parent-to-merge diff; this preserves the merge result while still retaining
    the events from each side branch's individual commits.
    """
    start, reviewed = _commit(root, start_commit), _commit(root, reviewed_revision)
    if subprocess.run(["git", "-C", os.fspath(root), "merge-base", "--is-ancestor", start, reviewed]).returncode:
        raise BaselineError("BOUNDARY_HISTORY_NOT_DESCENDANT")
    try:
        history = subprocess.run(
            ["git", "-C", os.fspath(root), "rev-list", "--reverse", "--topo-order", f"{start}..{reviewed}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode("ascii").splitlines()
    except subprocess.CalledProcessError as error:
        raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR") from error
    except UnicodeDecodeError as error:
        raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR") from error
    if any(len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit) for commit in history):
        raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR")
    records: list[CommittedPathChange] = []
    for commit in history:
        try:
            parents = subprocess.run(
                ["git", "-C", os.fspath(root), "rev-list", "--parents", "-n", "1", commit],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.decode("ascii").split()
            if len(parents) < 2 or parents[0] != commit:
                raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR")
            raw = subprocess.run(
                [
                    "git", "-C", os.fspath(root), "diff", "--raw", "-z", "--no-renames",
                    "--diff-filter=AMDT", parents[1], commit,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except subprocess.CalledProcessError as error:
            raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR") from error
        except UnicodeDecodeError as error:
            raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR") from error
        records.extend(_parse_committed_changes(raw, commit))
    return records


def _parse_committed_changes(raw: bytes, commit: str) -> list[CommittedPathChange]:
    """Parse one first-parent commit diff as uncollapsed path events."""
    raw_fields = raw[:-1].split(b"\0") if raw.endswith(b"\0") else []
    if raw and (not raw_fields or len(raw_fields) % 2):
        raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR")
    records: list[CommittedPathChange] = []
    for index in range(0, len(raw_fields), 2):
        header, raw_path = raw_fields[index:index + 2]
        if not header or not raw_path:
            raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR")
        try:
            fields = header.decode("ascii").split()
            path = _relative(raw_path.decode("utf-8", "surrogateescape"))
        except UnicodeDecodeError as error:
            raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR") from error
        if len(fields) != 5 or not fields[0].startswith(":") or fields[4] not in {"A", "M", "D", "T"}:
            raise BaselineError("BOUNDARY_HISTORY_PARSE_ERROR")
        old_mode, new_mode, old_object, new_object = fields[0][1:], fields[1], fields[2], fields[3]
        records.append(CommittedPathChange(path, {"A":"added","M":"modified","D":"deleted","T":"type_changed"}[fields[4]], old_mode, new_mode, old_object, new_object, commit))
    return records


def capture_live_state(root: Path) -> dict[str, list[dict[str, str]]]:
    layers = {"staged": _git_paths(root, "diff", "--cached", "--name-only", "-z"), "worktree": _git_paths(root, "diff", "--name-only", "-z"), "untracked": _git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")}
    layers["untracked"] |= {path for path in _git_paths(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z") if _is_ds_store(path)}
    return {path: [{"source": source} for source, paths in layers.items() if path in paths] for path in sorted(set().union(*layers.values()))}


def merge_boundary_changes(committed: list[CommittedPathChange], live: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for change in committed:
        event = {
            "commit": change.commit,
            "change_kind": change.change_kind,
            "old_mode": change.old_mode,
            "new_mode": change.new_mode,
            "old_object": change.old_object,
            "new_object": change.new_object,
        }
        record = merged.setdefault(
            change.path,
            {"path": change.path, "change_sources": ["committed_history"], "committed_changes": [], "live_changes": []},
        )
        committed_changes = record["committed_changes"]
        assert isinstance(committed_changes, list)
        committed_changes.append(event)
        # Retain the final event as the compatibility summary, but never discard history.
        record.update({"committed_change": event, "change_kind": change.change_kind, "old_mode": change.old_mode, "new_mode": change.new_mode})
    for path, changes in live.items():
        record = merged.setdefault(path, {"path": path, "change_sources": [], "live_changes": []})
        record["live_changes"] = changes; record["change_sources"] = sorted(set([*record["change_sources"], *(item["source"] for item in changes)]))
    return merged


def capture_current_paths(root: Path) -> set[str]:
    """Collect the current delta plus visible `.DS_Store` metadata paths."""
    return set(capture_live_state(root))


def committed_boundary_projection(
    root: Path, baseline_path: Path, *, reviewed_revision: object
) -> dict[str, object]:
    """Project only committed baseline-to-revision evidence, never the live filesystem.

    This is deliberately separate from ``check_boundary``.  A reviewer can freeze this
    projection before writing a decision or receipt; later index/worktree/untracked files
    cannot change its bytes.
    """
    baseline, baseline_sha256 = load_baseline(baseline_path)
    repository = baseline.get("repository")
    start = repository.get("head_commit") if isinstance(repository, dict) else None
    if not isinstance(start, str) or not start:
        raise BaselineError("BOUNDARY_HISTORY_START_MISSING")
    reviewed = require_full_commit(root, reviewed_revision)
    committed = capture_committed_history(root, start, reviewed)
    merged = merge_boundary_changes(committed, {})
    worktree = baseline["worktree"]
    prior_entries = [*worktree["tracked_changes"], *worktree["untracked_files"]]
    prior_paths = {str(item["path"]): item for item in prior_entries}
    classifications: list[dict[str, object]] = []
    for path in sorted(prior_paths):
        evidence = merged.get(path)
        if evidence is None:
            record = _classification(path, "preexisting_unrelated", allowed=False)
        else:
            change = evidence["committed_change"]
            assert isinstance(change, dict)
            status = "deleted_out_of_boundary" if change["change_kind"] == "deleted" else "modified_out_of_boundary"
            record = _classification(path, status, allowed=path_is_allowed(path, baseline["allowlist"]))
            record.update(evidence)
        classifications.append(record)
    for path in sorted(set(merged) - set(prior_paths)):
        record = _classification(path, "new_out_of_boundary", allowed=path_is_allowed(path, baseline["allowlist"]))
        record.update(merged[path])
        classifications.append(record)
    return {
        "boundary_classifications": classifications,
        "history_start_commit": _commit(root, start),
        "phase_start_baseline_sha256": baseline_sha256,
        "reviewed_revision": reviewed,
        "unique_changed_path_count": len(classifications),
    }


def committed_boundary_projection_sha256(projection: dict[str, object]) -> str:
    """Return the canonical digest of a committed-only boundary projection."""
    return sha256_bytes(canonical_json_bytes(projection))


def committed_publication_projection(
    root: Path, *, reviewed_revision: object
) -> dict[str, object]:
    """Project the current upstream-to-successor DAG under the manifest boundary."""
    from .publication import (
        EXPERIMENT_ROOT,
        PublicationContractError,
        publication_manifest_path,
        validate_publication_manifest,
    )

    try:
        publication = validate_publication_manifest(
            root, publication_manifest_path(root)
        )
        manifest_raw = publication_manifest_path(root).read_bytes()
    except (OSError, PublicationContractError) as error:
        raise BaselineError("PUBLICATION_BOUNDARY_INVALID") from error
    start = str(publication["upstream_base_commit"])
    reviewed = require_full_commit(root, reviewed_revision)
    committed = capture_committed_history(root, start, reviewed)
    merged = merge_boundary_changes(committed, {})
    prefix = f"{EXPERIMENT_ROOT}/"
    classifications: list[dict[str, object]] = []
    for path in sorted(merged):
        record = _classification(
            path, "new_out_of_boundary", allowed=path.startswith(prefix)
        )
        record.update(merged[path])
        classifications.append(record)
    if any(record["blocking"] for record in classifications):
        raise BaselineError("PUBLICATION_BOUNDARY_BLOCKING")
    return {
        "boundary_classifications": classifications,
        "history_start_commit": start,
        "phase_start_baseline_sha256": sha256_bytes(manifest_raw),
        "reviewed_revision": reviewed,
        "unique_changed_path_count": len(classifications),
    }


def check_live_boundary(root: Path, baseline_path: Path) -> BoundaryResult:
    """Fail closed on staged, worktree, and untracked changes without history reads."""
    baseline, baseline_sha256 = load_baseline(baseline_path)
    worktree = baseline["worktree"]
    prior_entries = [*worktree["tracked_changes"], *worktree["untracked_files"]]
    prior_paths = {str(item["path"]): item for item in prior_entries}
    live = capture_live_state(root)
    try:
        relative_baseline = baseline_path.relative_to(root).as_posix()
        live.pop(relative_baseline, None)
    except ValueError:
        pass
    classifications: list[dict[str, object]] = []
    for path in sorted(prior_paths):
        current = _current_fingerprint(root, path)
        evidence = live.get(path)
        if evidence is None and current is not None and _matches_baseline(prior_paths[path], current):
            record = _classification(path, "preexisting_unrelated", allowed=False)
        else:
            status = "deleted_out_of_boundary" if current is None else "modified_out_of_boundary"
            record = _classification(path, status, allowed=path_is_allowed(path, baseline["allowlist"]))
        if evidence is not None:
            record.update({"path": path, "change_sources": sorted(item["source"] for item in evidence), "live_changes": evidence})
        classifications.append(record)
    for path in sorted(set(live) - set(prior_paths)):
        record = _classification(path, "new_out_of_boundary", allowed=path_is_allowed(path, baseline["allowlist"]))
        record.update({"path": path, "change_sources": sorted(item["source"] for item in live[path]), "live_changes": live[path]})
        classifications.append(record)
    return BoundaryResult(baseline_sha256, classifications, sum(bool(item["blocking"]) for item in classifications), None, None, len(classifications))


def _current_fingerprint(root: Path, path: str) -> dict[str, object] | None:
    """Read a current path only after the filesystem policy accepts its components."""
    candidate = root.joinpath(*_relative(path).split("/"))
    try:
        details = candidate.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISDIR(details.st_mode):
        return {"file_kind": "directory"}
    try:
        evidence = inspect_authoritative_path(root, path)
    except FilesystemPolicyError as error:
        return {"diagnostic": str(error), "file_kind": "rejected"}
    return {
        "byte_length": evidence.byte_length,
        "file_kind": evidence.file_kind,
        "sha256": evidence.sha256,
    }


def _matches_baseline(entry: dict[str, object], current: dict[str, object]) -> bool:
    if entry.get("file_kind") != current.get("file_kind"):
        return False
    if entry.get("file_kind") != "regular_file":
        return True
    return (
        entry.get("byte_length") == current.get("byte_length")
        and entry.get("sha256") == current.get("sha256")
    )


def _classification(
    path: str,
    status: str,
    *,
    allowed: bool,
) -> dict[str, object]:
    """Return a visible classification without granting `.DS_Store` attribution."""
    if _is_ds_store(path):
        return {
            "path": path,
            "status": status,
            "attributed_to_phase": False,
            "blocking": False,
            "diagnostic": DS_STORE_DIAGNOSTIC,
        }
    if status == "preexisting_unrelated":
        return {"path": path, "status": status, "attributed_to_phase": False, "blocking": False}
    if allowed:
        return {"path": path, "status": "allowed_phase_change", "attributed_to_phase": True, "blocking": False}
    return {"path": path, "status": status, "attributed_to_phase": True, "blocking": True}


def check_boundary(root: Path, baseline_path: Path, *, reviewed_revision: str = "HEAD") -> BoundaryResult:
    """Classify delta against one fixed baseline without reinterpretation."""
    baseline, baseline_sha256 = load_baseline(baseline_path)
    worktree = baseline["worktree"]
    prior_entries = [*worktree["tracked_changes"], *worktree["untracked_files"]]
    prior_paths = {str(item["path"]): item for item in prior_entries}
    start = baseline.get("repository", {}).get("head_commit") if isinstance(baseline.get("repository"), dict) else None
    reviewed = _commit(root, reviewed_revision) if start else None
    if start:
        merged = merge_boundary_changes(
            capture_committed_history(root, str(start), str(reviewed)), capture_live_state(root)
        )
    else:
        # Unit fixtures without a repository retain the legacy patched live-path seam.
        merged = {
            path: {"path": path, "change_sources": ["live_fixture"], "live_changes": []}
            for path in capture_current_paths(root)
        }
    current_paths = set(merged)
    try: current_paths.discard(baseline_path.relative_to(root).as_posix()); merged.pop(baseline_path.relative_to(root).as_posix(), None)
    except ValueError: pass
    classifications: list[dict[str, object]] = []
    for path in sorted(prior_paths):
        current = _current_fingerprint(root, path)
        evidence = merged.get(path)
        if evidence is None and current is not None and _matches_baseline(prior_paths[path], current):
            record = _classification(path, "preexisting_unrelated", allowed=False)
        else:
            allowed = path_is_allowed(path, baseline["allowlist"])
            status = "deleted_out_of_boundary" if current is None else "modified_out_of_boundary"
            record = _classification(path, status, allowed=allowed)
        if evidence is not None:
            record.update(evidence)
        classifications.append(record)
    for path in sorted(current_paths - set(prior_paths)):
        allowed = path_is_allowed(path, baseline["allowlist"])
        record = _classification(path, "new_out_of_boundary", allowed=allowed); record.update(merged[path]); classifications.append(record)
    blocking = sum(bool(item["blocking"]) for item in classifications)
    return BoundaryResult(baseline_sha256, classifications, blocking, str(start) if start else None, reviewed, len(classifications))


def check_current_boundary(root: Path, baseline_path: Path) -> BoundaryResult:
    """Gate the entire current repository: committed history through current HEAD plus live state.

    Frozen receipt-basis construction must not use this function: it deliberately observes
    the moving current repository state.  Issuance and finalization use it after proving
    the frozen revision projection, so a clean worktree cannot hide a later bad commit.
    """
    current_head = _commit(root, "HEAD")
    return check_boundary(root, baseline_path, reviewed_revision=current_head)


def check_publication_boundary(root: Path) -> BoundaryResult:
    """Gate a successor against its exact manifest instead of a detached old DAG.

    Every declared package byte is hash-checked by the publication validator;
    every live path outside that package is blocking.  This is the forward-only
    counterpart to ``check_current_boundary`` for a branch based on new upstream.
    """
    from .publication import (
        PublicationContractError,
        publication_manifest_path,
        validate_publication_baseline,
    )

    try:
        result = validate_publication_baseline(root)
        manifest_raw = publication_manifest_path(root).read_bytes()
    except (OSError, PublicationContractError) as error:
        raise BaselineError("PUBLICATION_BOUNDARY_INVALID") from error
    blocking = set(result["blocking_changes"])
    classifications = [
        {
            "attributed_to_phase": path not in blocking,
            "blocking": path in blocking,
            "path": path,
            "status": (
                "new_out_of_boundary" if path in blocking else "allowed_phase_change"
            ),
        }
        for path in result["changed_paths"]
    ]
    return BoundaryResult(
        sha256_bytes(manifest_raw),
        classifications,
        len(blocking),
        str(result["upstream_base_commit"]),
        str(result["reviewed_revision"]),
        len(classifications),
    )


def validate_boundary_restart(baseline_path: Path, previous_baseline_path: Path, allowlist_path: Path, incident_receipt_path: Path) -> dict[str, object]:
    baseline, baseline_sha = load_baseline(baseline_path); _, previous_sha = load_baseline(previous_baseline_path)
    raw_allow, raw_incident = allowlist_path.read_bytes(), incident_receipt_path.read_bytes()
    try: allow, incident = json.loads(raw_allow), json.loads(raw_incident)
    except json.JSONDecodeError as error: raise BaselineError("BOUNDARY_RESTART_INVALID") from error
    if baseline.get("schema_version") != "3" or canonical_json_bytes(allow) != raw_allow or canonical_json_bytes(incident) != raw_incident: raise BaselineError("BOUNDARY_RESTART_NOT_CANONICAL")
    restart = baseline.get("restart")
    if not isinstance(restart, dict) or not isinstance(restart.get("reason_code"), str) or not isinstance(restart.get("scope"), str): raise BaselineError("BOUNDARY_RESTART_BINDING_MISMATCH")
    allowlist_binding = restart.get("v7_allowlist", restart.get("v5_allowlist"))
    if restart.get("previous_baseline", {}).get("sha256") != previous_sha or restart.get("incident_receipt", {}).get("sha256") != sha256_bytes(raw_incident) or not isinstance(allowlist_binding, dict) or allowlist_binding.get("sha256") != sha256_bytes(raw_allow): raise BaselineError("BOUNDARY_RESTART_BINDING_MISMATCH")
    if baseline.get("allowlist") != allow or baseline.get("future_control_exact_files") != allow.get("exact_files") or incident.get("receipt_sha256") != sha256_bytes(canonical_json_bytes({key:value for key,value in incident.items() if key != "receipt_sha256"})): raise BaselineError("BOUNDARY_RESTART_BINDING_MISMATCH")
    return {"baseline": {"path": baseline_path.as_posix(), "sha256": baseline_sha}, "allowlist": {"path": allowlist_path.as_posix(), "sha256": sha256_bytes(raw_allow)}, "incident_receipt": {"path": incident_receipt_path.as_posix(), "sha256": sha256_bytes(raw_incident)}, "previous_baseline": {"path": previous_baseline_path.as_posix(), "sha256": previous_sha}, "reviewed_revision": restart.get("reviewed_revision"), "reason_code": restart["reason_code"], "scope": restart["scope"]}
