# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Git-free verification for a complete accepted source bundle.

This module is deliberately copied, with its two small stdlib-only dependencies, into
each accepted generation.  It never discovers a repository or executes a process.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .filesystem import (
    FilesystemPolicyError,
    FileEvidence,
    read_closed_authoritative_tree,
    read_authoritative_file,
    require_relative_posix_path,
)


class BundleVerificationError(ValueError):
    """Stable failure emitted before accepted contents are exposed."""


# This is intentionally duplicated into the standalone verifier rather than imported
# from the construction package.  A copied accepted bundle must prove the finite PR
# fixture universe without repository modules, Git objects, or network access.
_FIXTURE_BASE = "tools/python/param-extraction-eval/cases"
_FIXTURE_COMMIT = "22e84458c87a7ccf4c07034de1eb6d0bf9764144"
_FIXTURE_TREE = "af003b427c66bd8ac9803a91b3bf363a1b1304d9"
_FIXTURE_SET = {
    "CAND_WARL_FIXED_LEGAL_SET": ("candidate", "candidates", ("expected.yaml", "source.txt")),
    "NEG_EXT_GATED_PBMTE": ("negative", "negatives", ("expected.yaml", "source.txt")),
    "NEG_FIXED_ENCODING": ("negative", "negatives", ("expected.yaml", "source.txt")),
    "NEG_SHALL_NO_DELEGATION": ("negative", "negatives", ("expected.yaml", "source.txt")),
    "NEG_SOFTWARE_ADVICE": ("negative", "negatives", ("expected.yaml", "source.txt")),
    "POS_CSR_RW_MTVEC_ACCESS": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
    "POS_DIRECT_CACHE_BLOCK": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
    "POS_DIRECT_NUM_PMP": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
    "POS_RECALL_COUNT_GEILEN": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
    "POS_WARL_ASID_WIDTH": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
    "POS_WARL_MTVEC_MODES": ("positive", "positives", ("expected.yaml", "gold.yaml", "source.txt")),
}
_FIXTURE_ROLES = {
    "expected.yaml": "fixture_expected",
    "gold.yaml": "fixture_gold",
    "source.txt": "fixture_source",
}


BundleMaterial = Mapping[str, tuple[FileEvidence, bytes]]


def _load_canonical_material(material: BundleMaterial, relative_path: str, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        _, raw = material[relative_path]
        value = json.loads(raw.decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleVerificationError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise BundleVerificationError(code)
    return value, raw


def _load_canonical(root: Path, relative_path: str, code: str) -> tuple[dict[str, Any], bytes]:
    """Read one canonical descriptor-rooted file for legacy call sites."""
    try:
        _, raw = read_authoritative_file(root, relative_path)
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleVerificationError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise BundleVerificationError(code)
    return value, raw


def _material_file(material: BundleMaterial | Path, relative_path: str) -> tuple[FileEvidence, bytes]:
    if isinstance(material, Path):
        return read_authoritative_file(material, relative_path)
    return material[relative_path]


def _raw_artifacts(core: dict[str, Any], material: BundleMaterial | Path) -> list[dict[str, object]]:
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
                evidence, _ = _material_file(material, local)
            except (KeyError, FilesystemPolicyError, ValueError) as error:
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


def _bundle_artifacts(core: dict[str, Any], material: BundleMaterial | Path) -> list[dict[str, object]]:
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
            evidence, _ = _material_file(material, local)
        except (KeyError, FilesystemPolicyError, ValueError) as error:
            raise BundleVerificationError("VERIFIER_ARTIFACT_INVALID") from error
        kind = record.get("kind")
        relationship = record.get("relationship")
        if (kind, relationship) not in {
            ("verifier", "bundle_verifier"),
            ("fixture_registry", "fixture_registry"),
        }:
            raise BundleVerificationError("VERIFIER_ARTIFACT_INVALID")
        if evidence.file_kind != "regular_file" or evidence.byte_length != length or evidence.sha256 != digest:
            raise BundleVerificationError("VERIFIER_ARTIFACT_TAMPERED")
        artifacts.append(
            {
                "byte_length": length,
                "kind": kind,
                "local_bundle_path": local,
                "raw_sha256": digest,
                "relationship": relationship,
            }
        )
    return artifacts


def _fixture_tuple(entry: dict[str, Any], *, registry: bool) -> tuple[str, str, str, int, str]:
    """Normalize a raw tuple from either the registry or manifest inventory."""
    try:
        upstream = require_relative_posix_path(str(entry.get("upstream_path"))).as_posix()
        local = require_relative_posix_path(str(entry.get("local_bundle_path"))).as_posix()
        length = require_byte_length(entry.get("raw_byte_length"))
        digest = require_sha256(entry.get("raw_sha256"))
    except (FilesystemPolicyError, ValueError) as error:
        raise BundleVerificationError("FIXTURE_CLOSURE_TUPLE_INVALID") from error
    role_key = "role" if registry else "experimental_role"
    role = entry.get(role_key)
    if not isinstance(role, str):
        raise BundleVerificationError("FIXTURE_CLOSURE_TUPLE_INVALID")
    return (upstream, local, role, length, digest)


def _verify_fixture_closure(core: dict[str, Any], material: BundleMaterial) -> None:
    """Prove a v3 fixture bundle has exactly the frozen 11/28 raw universe."""
    closure = core.get("fixture_closure")
    if closure is None:
        return
    if not isinstance(closure, dict) or set(closure) != {
        "fixture_count", "raw_file_count", "registry_path", "registry_sha256"
    }:
        raise BundleVerificationError("FIXTURE_CLOSURE_INVALID")
    if closure.get("fixture_count") != 11 or closure.get("raw_file_count") != 28:
        raise BundleVerificationError("FIXTURE_CLOSURE_COUNT_MISMATCH")
    if closure.get("registry_path") != "fixture-registry-pr2164-v1.json":
        raise BundleVerificationError("FIXTURE_CLOSURE_REGISTRY_PATH_MISMATCH")
    try:
        registry_digest = require_sha256(closure.get("registry_sha256"))
    except ValueError as error:
        raise BundleVerificationError("FIXTURE_CLOSURE_REGISTRY_DIGEST_INVALID") from error
    registry, registry_raw = _load_canonical_material(material, "fixture-registry-pr2164-v1.json", "FIXTURE_REGISTRY_INVALID")
    if sha256_bytes(registry_raw) != registry_digest:
        raise BundleVerificationError("FIXTURE_CLOSURE_REGISTRY_DIGEST_MISMATCH")
    if (
        set(registry) != {"fixture_count", "fixtures", "pinned_commit_sha", "pinned_tree_sha", "pull_request", "raw_file_count", "repository", "schema_version", "snapshot_id"}
        or registry.get("schema_version") != "1"
        or registry.get("repository") != "riscv/riscv-unified-db"
        or registry.get("snapshot_id") != "evaluation_fixtures"
        or registry.get("pull_request") != 2164
        or registry.get("pinned_commit_sha") != _FIXTURE_COMMIT
        or registry.get("pinned_tree_sha") != _FIXTURE_TREE
        or registry.get("fixture_count") != 11
        or registry.get("raw_file_count") != 28
    ):
        raise BundleVerificationError("FIXTURE_REGISTRY_IDENTITY_MISMATCH")
    artifacts = [
        item for item in core.get("bundle_artifacts", [])
        if isinstance(item, dict) and item.get("kind") == "fixture_registry"
    ]
    if len(artifacts) != 1 or artifacts[0].get("local_bundle_path") != "fixture-registry-pr2164-v1.json" or artifacts[0].get("sha256") != registry_digest:
        raise BundleVerificationError("FIXTURE_CLOSURE_REGISTRY_ARTIFACT_MISMATCH")
    fixtures = registry.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 11:
        raise BundleVerificationError("FIXTURE_REGISTRY_SET_MISMATCH")
    registry_tuples: set[tuple[str, str, str, int, str]] = set()
    fixture_ids: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict) or set(fixture) != {"fixture_class", "fixture_id", "files"}:
            raise BundleVerificationError("FIXTURE_REGISTRY_ENTRY_INVALID")
        fixture_id = fixture.get("fixture_id")
        if not isinstance(fixture_id, str) or fixture_id in fixture_ids or fixture_id not in _FIXTURE_SET:
            raise BundleVerificationError("FIXTURE_REGISTRY_SET_MISMATCH")
        fixture_ids.add(fixture_id)
        expected_class, directory, names = _FIXTURE_SET[fixture_id]
        files = fixture.get("files")
        if fixture.get("fixture_class") != expected_class or not isinstance(files, list) or len(files) != len(names):
            raise BundleVerificationError("FIXTURE_REGISTRY_ENTRY_INVALID")
        seen_names: set[str] = set()
        for file in files:
            if not isinstance(file, dict) or set(file) != {"filename", "local_bundle_path", "raw_byte_length", "raw_sha256", "role", "upstream_path"}:
                raise BundleVerificationError("FIXTURE_REGISTRY_ENTRY_INVALID")
            filename = file.get("filename")
            if not isinstance(filename, str) or filename in seen_names or filename not in names:
                raise BundleVerificationError("FIXTURE_REGISTRY_ENTRY_INVALID")
            seen_names.add(filename)
            if file.get("role") != _FIXTURE_ROLES[filename]:
                raise BundleVerificationError("FIXTURE_REGISTRY_ROLE_MISMATCH")
            expected_upstream = f"{_FIXTURE_BASE}/{directory}/{fixture_id}/{filename}"
            expected_local = f"raw/evaluation_fixtures/{fixture_id}/{filename}"
            if file.get("upstream_path") != expected_upstream or file.get("local_bundle_path") != expected_local:
                raise BundleVerificationError("FIXTURE_REGISTRY_PATH_MISMATCH")
            record = _fixture_tuple(file, registry=True)
            if record in registry_tuples:
                raise BundleVerificationError("FIXTURE_REGISTRY_DUPLICATE")
            registry_tuples.add(record)
        if seen_names != set(names):
            raise BundleVerificationError("FIXTURE_REGISTRY_ENTRY_INVALID")
    if fixture_ids != set(_FIXTURE_SET) or len(registry_tuples) != 28:
        raise BundleVerificationError("FIXTURE_REGISTRY_SET_MISMATCH")
    snapshots = core.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 1 or not isinstance(snapshots[0], dict):
        raise BundleVerificationError("FIXTURE_CLOSURE_CORE_MISMATCH")
    snapshot = snapshots[0]
    if any(snapshot.get(key) != value for key, value in {
        "repository": "riscv/riscv-unified-db", "snapshot_id": "evaluation_fixtures",
        "pull_request": 2164, "pinned_commit_sha": _FIXTURE_COMMIT, "pinned_tree_sha": _FIXTURE_TREE,
    }.items()):
        raise BundleVerificationError("FIXTURE_CLOSURE_CORE_MISMATCH")
    files = snapshot.get("consumed_files")
    if not isinstance(files, list):
        raise BundleVerificationError("FIXTURE_CLOSURE_CORE_MISMATCH")
    core_tuples = {_fixture_tuple(entry, registry=False) for entry in files if isinstance(entry, dict)}
    if len(core_tuples) != len(files) or core_tuples != registry_tuples:
        raise BundleVerificationError("FIXTURE_CLOSURE_CORE_REGISTRY_MISMATCH")


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


def _verify_tree_closure(material: BundleMaterial, artifacts: list[dict[str, object]]) -> None:
    """Reject any unmanifested file or prohibited kind in a replayable bundle."""
    expected = {"content-manifest-core.json", "snapshot-manifest.json"}
    expected.update(str(item["local_bundle_path"]) for item in artifacts)
    actual = {
        relative for relative in material
        if "__pycache__" not in relative.split("/") and not relative.endswith(".pyc")
    }
    missing = expected - actual
    if missing:
        raise BundleVerificationError("BUNDLE_MISSING_FILE")
    if actual - expected:
        raise BundleVerificationError("BUNDLE_EXTRA_FILE")


def verify_bundle_material(material: BundleMaterial, expected_status: str | None = None) -> dict[str, str]:
    """Verify one held closed-tree snapshot without reopening any authority paths."""
    core, core_bytes = _load_canonical_material(material, "content-manifest-core.json", "CORE_INVALID")
    final, _ = _load_canonical_material(material, "snapshot-manifest.json", "SNAPSHOT_MANIFEST_INVALID")
    status = final.get("status")
    if status not in {"accepted", "candidate"}:
        raise BundleVerificationError("GENERATION_STATUS_INVALID")
    if expected_status is not None and status != expected_status:
        raise BundleVerificationError(
            "GENERATION_NOT_ACCEPTED" if expected_status == "accepted" else "GENERATION_NOT_CANDIDATE"
        )
    if status == "accepted":
        if (
            final.get("downstream_eligible") is not True
            or final.get("offline_replay_proven") is not True
            or final.get("external_publication_authorized", False) is not False
            or final.get("accepted_publication_authorized", False) is not False
        ):
            raise BundleVerificationError("GENERATION_NOT_ACCEPTED")
    elif (
        final.get("downstream_eligible") is not False
        or final.get("accepted_publication_authorized") is not False
        or final.get("external_publication_authorized", False) is not False
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
    _verify_fixture_closure(core, material)
    artifacts = _raw_artifacts(core, material) + _bundle_artifacts(core, material)
    _verify_tree_closure(material, artifacts)
    recomputed_root = _root_digest(manifest_sha256, artifacts)
    if recomputed_root != root_sha256:
        raise BundleVerificationError("ROOT_SHA256_MISMATCH")
    return {"generation": generation, "manifest_sha256": manifest_sha256, "root_sha256": root_sha256, "status": status}


def verify_bundle(bundle_root: Path, expected_status: str | None = None) -> dict[str, str]:
    """Read and verify a rooted candidate or accepted generation from one closed tree."""
    try:
        material = read_closed_authoritative_tree(bundle_root)
    except FilesystemPolicyError as error:
        raise BundleVerificationError(str(error)) from error
    return verify_bundle_material(material, expected_status)


def verify_accepted_bundle(bundle_root: Path) -> dict[str, str]:
    """Recompute an accepted generation entirely from bundle-relative regular files."""
    return verify_bundle(bundle_root, "accepted")


def verify_accepted_bundle_material(material: BundleMaterial) -> dict[str, str]:
    """Verify an accepted generation from an already-held closed-tree snapshot."""
    return verify_bundle_material(material, "accepted")


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
        "from pathlib import Path\nimport sys\nsys.dont_write_bytecode = True\n"
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
