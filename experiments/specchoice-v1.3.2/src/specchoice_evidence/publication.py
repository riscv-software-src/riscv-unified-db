# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Publication-authority seam for the forward-only SpecChoice successor."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .canonical import CanonicalValueError, canonical_json_bytes, require_sha256, sha256_bytes
from .filesystem import (
    FilesystemPolicyError,
    read_authoritative_file,
    require_relative_posix_path,
)


class PublicationContractError(ValueError):
    """Stable failure for a publication-manifest contract violation."""


EXPERIMENT_ROOT = "experiments/specchoice-v1.3.2"
PUBLICATION_MANIFEST = f"{EXPERIMENT_ROOT}/evidence/publication-manifest-v1.json"
_LEGACY_PLANNING_PREFIX = "." + "planning/"
_ARCHIVE_PREFIX = f"{EXPERIMENT_ROOT}/evidence/archive/repository-root/"


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise PublicationContractError("PUBLICATION_GIT_UNAVAILABLE") from error


def _read_declared(repository: Path, path: str) -> bytes:
    try:
        return read_authoritative_file(repository, path)[1]
    except FilesystemPolicyError as error:
        if str(error) == "AUTHORITATIVE_FILE_MISSING":
            raise PublicationContractError("PUBLICATION_FILE_MISSING") from error
        raise PublicationContractError("PUBLICATION_FILE_INVALID") from error


def publication_manifest_path(repository: Path) -> Path:
    """Return the sole active publication authority path."""
    return repository / PUBLICATION_MANIFEST


def has_publication_manifest(repository: Path) -> bool:
    """Report whether this checkout uses the forward-only publication seam."""
    return publication_manifest_path(repository).is_file()


def _load_manifest(repository: Path) -> tuple[dict[str, object], bytes]:
    path = publication_manifest_path(repository)
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicationContractError("PUBLICATION_MANIFEST_INVALID") from error
    if not isinstance(manifest, dict) or canonical_json_bytes(manifest) != raw:
        raise PublicationContractError("PUBLICATION_MANIFEST_INVALID")
    return manifest, raw


def resolve_historical_path(repository: Path, legacy_path: str) -> str:
    """Resolve a legacy root path through its byte-identical archive mapping."""
    try:
        legacy = require_relative_posix_path(legacy_path).as_posix()
    except FilesystemPolicyError as error:
        raise PublicationContractError("HISTORICAL_MAPPING_INVALID") from error
    if not legacy.startswith(_LEGACY_PLANNING_PREFIX):
        return legacy
    if not has_publication_manifest(repository) and (repository / legacy).is_file():
        return legacy
    manifest, _ = _load_manifest(repository)
    historical = manifest.get("historical_evidence")
    if not isinstance(historical, dict) or not isinstance(historical.get("mappings"), list):
        raise PublicationContractError("HISTORICAL_EVIDENCE_INVALID")
    matches = [
        value
        for value in historical["mappings"]
        if isinstance(value, dict) and value.get("legacy_path") == legacy
    ]
    if len(matches) != 1:
        raise PublicationContractError("HISTORICAL_MAPPING_INVALID")
    mapping = matches[0]
    archive = mapping.get("archive_path")
    expected = _require_sha(mapping.get("sha256"), "HISTORICAL_MAPPING_INVALID")
    if not isinstance(archive, str) or not archive.startswith(_ARCHIVE_PREFIX):
        raise PublicationContractError("HISTORICAL_MAPPING_INVALID")
    raw = _read_declared(repository, archive)
    if sha256_bytes(raw) != expected:
        raise PublicationContractError("HISTORICAL_ARCHIVE_HASH_MISMATCH")
    return archive


def _require_mapping(value: object, keys: set[str], diagnostic: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise PublicationContractError(diagnostic)
    return value


def _require_sha(value: object, diagnostic: str) -> str:
    try:
        return require_sha256(value)
    except CanonicalValueError as error:
        raise PublicationContractError(diagnostic) from error


def _require_git_sha(value: object, diagnostic: str) -> str:
    if not isinstance(value, str) or len(value) != 40:
        raise PublicationContractError(diagnostic)
    try:
        int(value, 16)
    except ValueError as error:
        raise PublicationContractError(diagnostic) from error
    return value


def _publication_entries(
    repository: Path,
    publication: dict[str, object],
    experiment_root: str,
) -> tuple[dict[str, dict[str, object]], dict[str, bytes]]:
    values = publication.get("paths")
    if not isinstance(values, list) or not values:
        raise PublicationContractError("PUBLICATION_PATHS_INVALID")
    entries: dict[str, dict[str, object]] = {}
    payloads: dict[str, bytes] = {}
    prefix = f"{experiment_root}/"
    for value in values:
        entry = _require_mapping(
            value,
            {"consumers", "path", "role", "sha256"},
            "PUBLICATION_PATH_ENTRY_INVALID",
        )
        path_value = entry.get("path")
        role = entry.get("role")
        consumers = entry.get("consumers")
        if not isinstance(path_value, str) or not path_value.startswith(prefix):
            raise PublicationContractError("PUBLICATION_PATH_ENTRY_INVALID")
        try:
            path = require_relative_posix_path(path_value).as_posix()
        except FilesystemPolicyError as error:
            raise PublicationContractError("PUBLICATION_PATH_ENTRY_INVALID") from error
        if path in entries:
            raise PublicationContractError("PUBLICATION_PATH_ENTRY_INVALID")
        if not isinstance(role, str) or not role:
            raise PublicationContractError("PUBLICATION_PATH_ENTRY_INVALID")
        if (
            not isinstance(consumers, list)
            or not consumers
            or any(not isinstance(consumer, str) or not consumer for consumer in consumers)
        ):
            raise PublicationContractError("PUBLICATION_CONSUMER_REQUIRED")
        expected = _require_sha(entry.get("sha256"), "PUBLICATION_PATH_ENTRY_INVALID")
        raw = _read_declared(repository, path)
        if sha256_bytes(raw) != expected:
            raise PublicationContractError("PUBLICATION_FILE_HASH_MISMATCH")
        entries[path] = entry
        payloads[path] = raw
    return entries, payloads


def _validate_policy_dependencies(
    policy: dict[str, object],
    entries: dict[str, dict[str, object]],
    payloads: dict[str, bytes],
) -> None:
    prohibited = policy.get("prohibited_repository_root_dependencies")
    if not isinstance(prohibited, list) or any(
        not isinstance(item, str) or not item for item in prohibited
    ):
        raise PublicationContractError("PUBLICATION_POLICY_INVALID")
    for path, entry in entries.items():
        if entry.get("role") != "runtime":
            continue
        raw = payloads[path]
        if any(
            (
                (b'"' + item.encode("utf-8") in raw or b"'" + item.encode("utf-8") in raw)
                if item == _LEGACY_PLANNING_PREFIX
                else item.encode("utf-8") in raw
            )
            for item in prohibited
        ):
            raise PublicationContractError("PROHIBITED_REPOSITORY_ROOT_DEPENDENCY")
        ambient_ref = b"refs/" + b"specchoice/pr-"
        if policy.get("ambient_custom_refs_prohibited") is True and ambient_ref in raw:
            raise PublicationContractError("AMBIENT_CUSTOM_REF_DEPENDENCY")


def _validate_tracked_inventory(
    repository: Path,
    manifest_path: Path,
    experiment_root: str,
    entries: dict[str, dict[str, object]],
) -> None:
    tracked = _git(repository, "ls-files", "-z", "--", experiment_root)
    if tracked.returncode != 0:
        raise PublicationContractError("PUBLICATION_GIT_UNAVAILABLE")
    manifest_relative = manifest_path.relative_to(repository).as_posix()
    actual = {
        path.decode("utf-8", "strict")
        for path in tracked.stdout.split(b"\0")
        if path and path.decode("utf-8", "strict") != manifest_relative
    }
    if actual != set(entries):
        raise PublicationContractError("PUBLICATION_INVENTORY_MISMATCH")


def _validate_upstream_base(repository: Path, value: object) -> str:
    base = _require_git_sha(value, "PUBLICATION_UPSTREAM_BASE_INVALID")
    ancestry = _git(repository, "merge-base", "--is-ancestor", base, "HEAD")
    if ancestry.returncode != 0:
        raise PublicationContractError("PUBLICATION_UPSTREAM_BASE_INVALID")
    return base


def _validate_historical_evidence(
    repository: Path,
    historical: dict[str, object],
    entries: dict[str, dict[str, object]],
) -> list[dict[str, str]]:
    mappings = historical.get("mappings")
    commits = historical.get("commits")
    if not isinstance(mappings, list) or not isinstance(commits, list):
        raise PublicationContractError("HISTORICAL_EVIDENCE_INVALID")
    for value in mappings:
        mapping = _require_mapping(
            value,
            {"archive_path", "legacy_path", "sha256"},
            "HISTORICAL_MAPPING_INVALID",
        )
        legacy = mapping.get("legacy_path")
        archive = mapping.get("archive_path")
        expected = _require_sha(mapping.get("sha256"), "HISTORICAL_MAPPING_INVALID")
        if not isinstance(legacy, str) or not legacy.startswith(_LEGACY_PLANNING_PREFIX):
            raise PublicationContractError("HISTORICAL_MAPPING_INVALID")
        if not isinstance(archive, str) or archive not in entries:
            raise PublicationContractError("HISTORICAL_MAPPING_INVALID")
        archive_entry = entries[archive]
        if archive_entry.get("role") != "historical_input" or archive_entry.get("sha256") != expected:
            raise PublicationContractError("HISTORICAL_ARCHIVE_HASH_MISMATCH")

    provenance: list[dict[str, str]] = []
    for value in commits:
        commit = _require_mapping(
            value,
            {"commit_sha", "role", "tree_sha"},
            "HISTORICAL_PROVENANCE_INVALID",
        )
        commit_sha = commit.get("commit_sha")
        tree_sha = commit.get("tree_sha")
        role = commit.get("role")
        if not isinstance(role, str) or not role:
            raise PublicationContractError("HISTORICAL_PROVENANCE_INVALID")
        commit_sha = _require_git_sha(commit_sha, "HISTORICAL_PROVENANCE_INVALID")
        tree_sha = _require_git_sha(tree_sha, "HISTORICAL_PROVENANCE_INVALID")
        available = _git(repository, "cat-file", "-e", f"{commit_sha}^{{commit}}")
        if available.returncode != 0:
            provenance.append({"commit_sha": commit_sha, "status": "not_available"})
            continue
        observed = _git(repository, "rev-parse", f"{commit_sha}^{{tree}}")
        if observed.returncode != 0 or observed.stdout.decode("ascii", "strict").strip() != tree_sha:
            raise PublicationContractError("HISTORICAL_PROVENANCE_CONTRADICTORY")
        provenance.append({"commit_sha": commit_sha, "status": "verified"})
    return provenance


def validate_publication_manifest(
    repository: Path, manifest_path: Path
) -> dict[str, object]:
    """Validate the single active publication authority."""
    try:
        if manifest_path.resolve(strict=False) != publication_manifest_path(repository).resolve(strict=False):
            raise PublicationContractError("PUBLICATION_MANIFEST_INVALID")
        manifest, raw = _load_manifest(repository)
    except OSError as error:
        raise PublicationContractError("PUBLICATION_MANIFEST_INVALID") from error
    if canonical_json_bytes(manifest) != raw:
        raise PublicationContractError("PUBLICATION_MANIFEST_INVALID")
    if manifest.get("schema_version") != 1:
        raise PublicationContractError("PUBLICATION_MANIFEST_SCHEMA_UNSUPPORTED")
    if set(manifest) != {"historical_evidence", "policy", "publication", "schema_version"}:
        raise PublicationContractError("PUBLICATION_MANIFEST_INVALID")
    policy = _require_mapping(
        manifest.get("policy"),
        {
            "ambient_custom_refs_prohibited",
            "experiment_root",
            "prohibited_repository_root_dependencies",
            "tracked_package_files_must_match_inventory",
        },
        "PUBLICATION_POLICY_INVALID",
    )
    experiment_root = policy.get("experiment_root")
    if (
        not isinstance(experiment_root, str)
        or experiment_root != EXPERIMENT_ROOT
        or policy.get("tracked_package_files_must_match_inventory") is not True
        or policy.get("ambient_custom_refs_prohibited") is not True
    ):
        raise PublicationContractError("PUBLICATION_POLICY_INVALID")
    publication = _require_mapping(
        manifest.get("publication"),
        {"paths", "upstream_base_commit"},
        "PUBLICATION_SECTION_INVALID",
    )
    historical = _require_mapping(
        manifest.get("historical_evidence"),
        {"commits", "mappings"},
        "HISTORICAL_EVIDENCE_INVALID",
    )
    upstream_base = _validate_upstream_base(
        repository, publication.get("upstream_base_commit")
    )
    entries, payloads = _publication_entries(repository, publication, experiment_root)
    _validate_policy_dependencies(policy, entries, payloads)
    _validate_tracked_inventory(repository, manifest_path, experiment_root, entries)
    historical_provenance = _validate_historical_evidence(
        repository, historical, entries
    )
    return {
        "historical_provenance": historical_provenance,
        "path_count": len(entries),
        "status": "valid",
        "upstream_base_commit": upstream_base,
    }


def validate_publication_baseline(repository: Path) -> dict[str, object]:
    """Validate the package and reject live changes outside its declared boundary."""
    result = validate_publication_manifest(
        repository, publication_manifest_path(repository)
    )
    status = _git(
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=all",
    )
    head = _git(repository, "rev-parse", "HEAD")
    if status.returncode != 0 or head.returncode != 0:
        raise PublicationContractError("PUBLICATION_GIT_UNAVAILABLE")
    blocking: list[str] = []
    changed: list[str] = []
    prefix = f"{EXPERIMENT_ROOT}/"
    try:
        for record in status.stdout.split(b"\0"):
            if not record:
                continue
            if len(record) < 4 or record[2:3] != b" ":
                raise UnicodeDecodeError("utf-8", record, 0, len(record), "invalid status")
            path = record[3:].decode("utf-8", "strict")
            changed.append(path)
            if not path.startswith(prefix):
                blocking.append(path)
    except UnicodeDecodeError as error:
        raise PublicationContractError("PUBLICATION_STATUS_INVALID") from error
    return {
        **result,
        "blocking_changes": sorted(blocking),
        "changed_paths": sorted(changed),
        "reviewed_revision": head.stdout.decode("ascii", "strict").strip(),
    }
