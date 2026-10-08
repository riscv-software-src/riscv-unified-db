# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Deterministic, local-only byte custody for executable closure receipts."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .filesystem import FilesystemPolicyError, read_authoritative_file, require_relative_posix_path
from .publication import (
    PublicationContractError,
    has_publication_manifest,
    publication_manifest_path,
    resolve_historical_path,
    validate_publication_manifest,
)


class RuntimeClosureError(ValueError):
    """Stable failure for an executable closure mismatch."""


_EXPERIMENT_PREFIX = "experiments/specchoice-v1.3.2"
_LEGACY_PLANNING = "." + "planning/"
_HISTORICAL_BLOB_CATALOG = (
    f"{_EXPERIMENT_PREFIX}/evidence/archive/historical-blob-catalog-v1.json.gz"
)
_ACCEPTED_V3 = (
    f"{_EXPERIMENT_PREFIX}/bundles/accepted/"
    "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
)
_REGISTRY_V6 = f"{_EXPERIMENT_PREFIX}/config/fixture-registry-pr2164-v6.json"
_REPAIR_MANIFEST_V5 = (
    f"{_EXPERIMENT_PREFIX}/config/fixture-repairs/"
    "pr2164-semantic-gold-v5/repair-manifest.json"
)
_AUTHORITY_PRE_STATE = f"{_EXPERIMENT_PREFIX}/phase2/source-authority.json"
_CLOSURE_V2_RECEIPT = f"{_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v2.json"
_CLOSURE_V2_BYTE_LENGTH = 89025
_CLOSURE_V2_SHA256 = "a09246c22165383613f6ffd7f4a0f925d631eee48c50e452ff4592532ae8b2eb"
_CLOSURE_V2_SUPERSESSION = (
    f"{_EXPERIMENT_PREFIX}/receipts/"
    "runtime-executable-closure-v2-non-authorizing-supersession-v1.json"
)
_CLOSURE_V3_RECEIPT = f"{_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v3.json"
_CLOSURE_V3_FREEZE = "dc87436a1a6e26ae6bd412d1800e39352ac2f811"
_CLOSURE_V3_BYTE_LENGTH = 90708
_CLOSURE_V3_SHA256 = "dbc86e53c044910536d9dbd494aa7df286604f3fbf6e4fdf8c4f3c11c943f774"

# This is intentionally code authority, not proposal authority.  A proposal can
# repeat this inventory but cannot add, remove, reorder, or relabel one target.
_FUTURE_TARGETS_V6: tuple[tuple[str, str], ...] = (
    ("construction_decision", f"{_EXPERIMENT_PREFIX}/receipts/source-contract-construction-decision-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6.json"),
    ("candidate", f"{_EXPERIMENT_PREFIX}/bundles/candidates/source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"),
    ("candidate_audit", f"{_EXPERIMENT_PREFIX}/receipts/source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6/candidate-audit-v6.json"),
    ("acceptance_request", f"{_EXPERIMENT_PREFIX}/receipts/local-acceptance-request-v13.json"),
    ("acceptance_decision", f"{_EXPERIMENT_PREFIX}/receipts/local-acceptance-decision-v13.json"),
    ("accepted_bundle", f"{_EXPERIMENT_PREFIX}/bundles/accepted/source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"),
    ("historical_authority", f"{_EXPERIMENT_PREFIX}/phase2/source-authority-v13-historical.json"),
    ("pending_authority", f"{_EXPERIMENT_PREFIX}/phase2/source-authority-v13-pending.json"),
    ("transition", f"{_EXPERIMENT_PREFIX}/receipts/pending/fixture-closure-transition-v3-to-v6.json"),
    ("readiness", f"{_EXPERIMENT_PREFIX}/receipts/pending/source-cutover-readiness-v13.json"),
    ("revocation", f"{_EXPERIMENT_PREFIX}/receipts/fixture-closure-revocation-v3-to-v6.json"),
    ("acceptance_audit", f"{_EXPERIMENT_PREFIX}/receipts/fixture-closure-acceptance-audit-v6.json"),
    ("offline_replay", f"{_EXPERIMENT_PREFIX}/receipts/fixture-closure-offline-replay-v6.json"),
    ("integrity", f"{_EXPERIMENT_PREFIX}/receipts/integrity-receipt-v14.json"),
    ("adapter_batch", f"{_EXPERIMENT_PREFIX}/reports/h1/adapter-batch-pr2164-v5.json"),
    ("formal_attempt", f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v5"),
    ("adversarial", f"{_EXPERIMENT_PREFIX}/reports/h1/adversarial-oracle-results-v6.json"),
    ("h1_packet", f"{_EXPERIMENT_PREFIX}/reports/h1/h1-source-gold-review-v6"),
    ("h1_readiness", f"{_EXPERIMENT_PREFIX}/receipts/h1-review-readiness-v6.json"),
    ("h1_decision", f"{_EXPERIMENT_PREFIX}/reviews/h1-source-gold-decision-v5.json"),
    ("phase1_verification", _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION-02-19.md"),
    ("phase1_review", _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW-02-19.md"),
    ("phase2_verification", _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION-02-19.md"),
    ("phase2_review", _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW-02-19.md"),
    ("summary", _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-19-SUMMARY.md"),
)

_KNOWN_RUNTIME_PATHS_V2 = (
    # Evidence and measurement implementation.
    *(
        f"{_EXPERIMENT_PREFIX}/src/{package}/{name}.py"
        for package, names in (
            ("specchoice_evidence", ("__init__", "authority", "baseline", "bundle", "canonical", "cli", "environment", "filesystem", "git_proof", "receipt", "runtime_closure", "source_contract", "successor", "verify")),
            ("specchoice_measurement", ("__init__", "adapter", "attempts", "cli", "diagnostics", "domain", "final_reports", "h1", "preflight", "scoring", "strict_json")),
        )
        for name in names
    ),
    # Every focused test and both the historical and successor exact oracle.
    *(
        f"{_EXPERIMENT_PREFIX}/tests/{name}"
        for name in (
            "test_source_contract.py", "test_fixture_closure.py", "test_filesystem_boundary.py",
            "test_measurement_adapter.py", "test_measurement_scoring.py", "test_measurement_parsing.py",
            "test_measurement_attempts.py", "test_measurement_h1.py",
            "phase1_expected_red_oracle.py", "phase1_expected_red_oracle_v2.py",
        )
    ),
    _REGISTRY_V6,
    _REPAIR_MANIFEST_V5,
    f"{_EXPERIMENT_PREFIX}/reviews/h1-source-gold-ontology-decision-v1.json",
    f"{_EXPERIMENT_PREFIX}/config/measurement/pr2164-semantic-gold-contract-v2.json",
    f"{_EXPERIMENT_PREFIX}/config/measurement/pr2164-adapter-rules-v3.json",
    f"{_EXPERIMENT_PREFIX}/config/measurement/canonical-adjudication-schema-v3.json",
    f"{_EXPERIMENT_PREFIX}/config/measurement/h1-semantic-review-questions-v2.json",
    f"{_EXPERIMENT_PREFIX}/config/measurement/h1-review-schema-v4.json",
    f"{_EXPERIMENT_PREFIX}/fixtures/measurement/golden-predictions-v4.json",
    f"{_EXPERIMENT_PREFIX}/fixtures/measurement/adversarial/required-diagnostics-v4.json",
    f"{_EXPERIMENT_PREFIX}/receipts/source-contract-construction-authorization-v4-non-executable-supersession-v1.json",
    f"{_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v1.json",
    f"{_EXPERIMENT_PREFIX}/receipts/source-contract-proposal-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5.json",
    f"{_EXPERIMENT_PREFIX}/receipts/source-contract-construction-proposal-v5-supersession-v4.json",
    f"{_EXPERIMENT_PREFIX}/receipts/source-contract-construction-proposal-v5-non-executable-supersession-v1.json",
    f"{_ACCEPTED_V3}/snapshot-manifest.json",
    _LEGACY_PLANNING + "ROADMAP.md",
    _LEGACY_PLANNING + "REQUIREMENTS.md",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION.md",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-19-PLAN.md",
)

_KNOWN_RUNTIME_PATHS_V3 = (
    *_KNOWN_RUNTIME_PATHS_V2,
    _CLOSURE_V2_RECEIPT,
    _CLOSURE_V2_SUPERSESSION,
)

_DYNAMIC_IMPORTS = (
    "specchoice_evidence.authority", "specchoice_evidence.bundle", "specchoice_evidence.cli", "specchoice_evidence.runtime_closure",
    "specchoice_evidence.source_contract", "specchoice_evidence.successor",
    "specchoice_measurement.adapter", "specchoice_measurement.attempts", "specchoice_measurement.cli",
    "specchoice_measurement.final_reports", "specchoice_measurement.h1", "specchoice_measurement.scoring",
)

_FORBIDDEN_AMBIENT_TOOL_ENV = ("GIT_OPTIONAL_LOCKS", "RUBYOPT", "RUBYLIB")


def _require_clean_tool_environment() -> dict[str, str]:
    """Reject ambient Git/Ruby injection before constructing or checking custody."""
    projection = {name: os.environ.get(name, "") for name in _FORBIDDEN_AMBIENT_TOOL_ENV}
    if any(projection.values()):
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_ENVIRONMENT_DIRTY")
    return projection


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }


def _ruby_environment() -> dict[str, str]:
    return {
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "RUBYLIB": "",
        "RUBYOPT": "",
    }


def future_target_inventory_v6() -> list[dict[str, str]]:
    """Return the typed, canonical future target inventory reconstructed from code."""
    return [
        {"kind": kind, "path": path}
        for kind, path in sorted(_FUTURE_TARGETS_V6, key=lambda item: item[1])
    ]


def closure_entry(root: Path, relative_path: str) -> dict[str, object]:
    """Capture one existing ordinary file using an experiment-relative path."""
    try:
        normalized = str(require_relative_posix_path(relative_path))
        resolved = resolve_historical_path(root, normalized)
        candidate = (root / resolved).resolve(strict=True)
        root_real = root.resolve(strict=True)
    except (OSError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_PATH_INVALID") from error
    if candidate == root_real or root_real not in candidate.parents or not candidate.is_file():
        raise RuntimeClosureError("RUNTIME_CLOSURE_PATH_INVALID")
    raw = candidate.read_bytes()
    return {"byte_length": len(raw), "path": normalized, "sha256": sha256_bytes(raw)}


def build_runtime_closure(root: Path, relative_paths: list[str]) -> dict[str, object]:
    """Freeze an exact, sorted finite file inventory for later no-write preflight."""
    if not isinstance(relative_paths, list) or not relative_paths:
        raise RuntimeClosureError("RUNTIME_CLOSURE_INPUT_INVALID")
    try:
        normalized = sorted(str(require_relative_posix_path(path)) for path in relative_paths)
    except (TypeError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_INPUT_INVALID") from error
    if len(set(normalized)) != len(normalized):
        raise RuntimeClosureError("RUNTIME_CLOSURE_INPUT_INVALID")
    return {
        "entries": [closure_entry(root, path) for path in normalized],
        "schema_version": "runtime-executable-closure-v1",
    }


def verify_runtime_closure(closure: object, root: Path) -> dict[str, object]:
    """Prove every bound entry still has exactly the frozen bytes before mutation."""
    if not isinstance(closure, Mapping) or closure.get("schema_version") != "runtime-executable-closure-v1":
        raise RuntimeClosureError("RUNTIME_CLOSURE_INVALID")
    entries = closure.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RuntimeClosureError("RUNTIME_CLOSURE_INVALID")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"byte_length", "path", "sha256"}:
            raise RuntimeClosureError("RUNTIME_CLOSURE_ENTRY_INVALID")
        try:
            path = str(require_relative_posix_path(entry["path"]))
            length = require_byte_length(entry["byte_length"])
            digest = require_sha256(entry["sha256"])
        except (KeyError, ValueError) as error:
            raise RuntimeClosureError("RUNTIME_CLOSURE_ENTRY_INVALID") from error
        if path in seen:
            raise RuntimeClosureError("RUNTIME_CLOSURE_ENTRY_INVALID")
        seen.add(path)
        current = closure_entry(root, path)
        if current["byte_length"] != length or current["sha256"] != digest:
            raise RuntimeClosureError("RUNTIME_CLOSURE_ENTRY_MISMATCH")
    return dict(closure)


def validate_v6_preflight_inventory(
    *, root: Path, input_paths: list[str], target_paths: list[str],
) -> dict[str, object]:
    """Read every frozen input and prove every future target is absent.

    This is deliberately independent of a proposal's self-declared ``targets``
    field: callers supply the inventory reconstructed from frozen config/code.
    It is used by every v6/v13 preflight before a writer is allowed to open a
    candidate, receipt, authority, or report target.
    """
    if not isinstance(input_paths, list) or not input_paths or not isinstance(target_paths, list) or not target_paths:
        raise RuntimeClosureError("RUNTIME_CLOSURE_INVENTORY_INVALID")
    try:
        inputs = sorted(str(require_relative_posix_path(path)) for path in input_paths)
        targets = sorted(str(require_relative_posix_path(path)) for path in target_paths)
    except (TypeError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_INVENTORY_INVALID") from error
    if len(inputs) != len(set(inputs)) or len(targets) != len(set(targets)) or set(inputs) & set(targets):
        raise RuntimeClosureError("RUNTIME_CLOSURE_INVENTORY_INVALID")
    # ``closure_entry`` consumes and hashes the current bytes; callers retain
    # the returned evidence in their decision/proposal validator.
    evidence = [closure_entry(root, path) for path in inputs]
    root_real = root.resolve(strict=True)
    for path in targets:
        candidate = root_real / path
        if candidate.exists() or candidate.is_symlink():
            raise RuntimeClosureError("RUNTIME_CLOSURE_TARGET_OCCUPIED")
    return {"inputs": evidence, "targets": targets}


def no_user_site_environment() -> dict[str, str]:
    """Return the only environment projection accepted by closure preflights."""
    return {
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE", ""),
        "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }


def _canonical_object_with_raw(
    path: Path, diagnostic: str,
) -> tuple[dict[str, object], bytes]:
    try:
        evidence, raw = read_authoritative_file(path.parent, path.name)
        value = json.loads(raw.decode("utf-8"))
    except (
        FilesystemPolicyError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeClosureError(diagnostic) from error
    if (
        evidence.file_kind != "regular_file"
        or not isinstance(value, dict)
        or canonical_json_bytes(value) != raw
    ):
        raise RuntimeClosureError(diagnostic)
    return value, raw


def _canonical_object(path: Path, diagnostic: str) -> dict[str, object]:
    return _canonical_object_with_raw(path, diagnostic)[0]


def _repository_relative(repository: Path, path: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(repository.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_PATH_INVALID") from error


def _run(command: list[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> bytes:
    try:
        completed = subprocess.run(
            command, cwd=cwd, env=dict(env) if env is not None else None,
            check=False, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_UNAVAILABLE") from error
    if completed.returncode != 0 or len(completed.stdout) > 4 * 1024 * 1024 or len(completed.stderr) > 64 * 1024:
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_UNAVAILABLE")
    return completed.stdout


def _file_identity(path: Path) -> dict[str, object]:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OSError
        raw = resolved.read_bytes()
    except OSError as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_UNAVAILABLE") from error
    return {"byte_length": len(raw), "path": os.fspath(resolved), "sha256": sha256_bytes(raw)}


def _fresh_python_discovery(experiment: Path) -> dict[str, object]:
    script = (
        "import importlib,json,sys\n"
        f"names={list(_DYNAMIC_IMPORTS)!r}\n"
        "[importlib.import_module(name) for name in names]\n"
        "items=[]\n"
        "for name,module in sorted(sys.modules.items()):\n"
        " p=getattr(module,'__file__',None)\n"
        " if isinstance(p,str): items.append({'module':name,'origin':p})\n"
        "print(json.dumps(items,sort_keys=True,separators=(',',':')))\n"
    )
    environment = {
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.fspath((experiment / "src").resolve(strict=True)),
    }
    argv = [os.fspath(Path(sys.executable).resolve(strict=True)), "-B", "-c", script]
    raw = _run(argv, cwd=experiment, env=environment)
    try:
        discovered = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_PYTHON_DISCOVERY_INVALID") from error
    if not isinstance(discovered, list):
        raise RuntimeClosureError("RUNTIME_CLOSURE_PYTHON_DISCOVERY_INVALID")
    origins: list[dict[str, object]] = []
    for item in discovered:
        if not isinstance(item, dict) or set(item) != {"module", "origin"}:
            raise RuntimeClosureError("RUNTIME_CLOSURE_PYTHON_DISCOVERY_INVALID")
        origin = Path(str(item["origin"]))
        if not origin.exists() or not origin.is_file():
            continue
        identity = _file_identity(origin)
        origins.append({"module": item["module"], **identity})
    origins.sort(key=lambda item: (str(item["path"]), str(item["module"])))
    return {
        "discovery_argv": argv,
        "discovery_environment": environment,
        "module_origins": origins,
    }


def _tool_identities(repository: Path, experiment: Path) -> dict[str, object]:
    _require_clean_tool_environment()
    python = _file_identity(Path(sys.executable))
    python.update({
        "cache_tag": sys.implementation.cache_tag,
        "implementation": sys.implementation.name,
        "version": platform.python_version(),
        "version_info": list(sys.version_info[:5]),
        **_fresh_python_discovery(experiment),
    })

    git_name = shutil.which("git")
    ruby_name = shutil.which("ruby")
    if git_name is None or ruby_name is None:
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_UNAVAILABLE")
    git_path = Path(git_name).resolve(strict=True)
    git_argv = [os.fspath(git_path), "--version"]
    git = {
        **_file_identity(git_path),
        "argv": git_argv,
        "environment": _git_environment(),
        "version_output": _run(
            git_argv, cwd=repository, env=_git_environment()
        ).decode("utf-8", "strict").rstrip("\n"),
    }

    ruby_path = Path(ruby_name).resolve(strict=True)
    ruby_script = (
        "require 'json'; require 'psych'; "
        "puts JSON.generate({'ruby_version'=>RUBY_VERSION,'ruby_description'=>RUBY_DESCRIPTION,"
        "'psych_version'=>Psych::VERSION,'loaded_features'=>$LOADED_FEATURES.select{|p| File.file?(p)}.sort})"
    )
    ruby_argv = [os.fspath(ruby_path), "-e", ruby_script]
    try:
        ruby_projection = json.loads(
            _run(ruby_argv, cwd=repository, env=_ruby_environment()).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_RUBY_DISCOVERY_INVALID") from error
    if not isinstance(ruby_projection, dict) or not isinstance(ruby_projection.get("loaded_features"), list):
        raise RuntimeClosureError("RUNTIME_CLOSURE_RUBY_DISCOVERY_INVALID")
    libraries = [_file_identity(Path(path)) for path in ruby_projection["loaded_features"]]
    libraries.sort(key=lambda item: str(item["path"]))
    ruby = {
        **_file_identity(ruby_path),
        "argv": ruby_argv,
        "environment": _ruby_environment(),
        "loaded_libraries": libraries,
        "psych_version": ruby_projection.get("psych_version"),
        "ruby_description": ruby_projection.get("ruby_description"),
        "ruby_version": ruby_projection.get("ruby_version"),
    }
    return {"git": git, "python": python, "ruby_psych": ruby}


def _git(repository: Path, *arguments: str) -> bytes:
    git_name = shutil.which("git")
    if git_name is None:
        raise RuntimeClosureError("RUNTIME_CLOSURE_TOOL_UNAVAILABLE")
    return _run(
        [
            os.fspath(Path(git_name).resolve(strict=True)),
            "--no-replace-objects",
            "-C",
            os.fspath(repository),
            *arguments,
        ],
        cwd=repository,
        env=_git_environment(),
    )


def _referenced_runtime_paths_v2(repository: Path) -> dict[str, set[str]]:
    """Reconstruct every path from accepted-v3 and registry-v6 independently."""
    classes: dict[str, set[str]] = {}

    def add(path: str, kind: str) -> None:
        try:
            normalized = require_relative_posix_path(path).as_posix()
        except ValueError as error:
            raise RuntimeClosureError("RUNTIME_CLOSURE_PATH_INVALID") from error
        classes.setdefault(normalized, set()).add(kind)

    for path in _KNOWN_RUNTIME_PATHS_V2:
        add(path, "known_mandatory")

    accepted_root = repository / _ACCEPTED_V3
    snapshot = _canonical_object(accepted_root / "snapshot-manifest.json", "RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
    core = snapshot.get("content_manifest_core")
    if not isinstance(core, dict):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
    referenced: list[str] = []
    snapshots = core.get("snapshots")
    artifacts = core.get("bundle_artifacts")
    if not isinstance(snapshots, list) or not isinstance(artifacts, list):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
    for item in snapshots:
        if not isinstance(item, dict) or not isinstance(item.get("consumed_files"), list):
            raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
        for entry in item["consumed_files"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("local_bundle_path"), str):
                raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
            referenced.append(entry["local_bundle_path"])
    for entry in artifacts:
        if not isinstance(entry, dict) or not isinstance(entry.get("local_bundle_path"), str):
            raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVALID")
        referenced.append(entry["local_bundle_path"])
    if len(referenced) != 34 or len(set(referenced)) != 34:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ACCEPTED_V3_INVENTORY_INVALID")
    for relative in referenced:
        add(f"{_ACCEPTED_V3}/{require_relative_posix_path(relative).as_posix()}", "accepted_v3_referenced_file")

    registry = _canonical_object(repository / _REGISTRY_V6, "RUNTIME_CLOSURE_REGISTRY_V6_INVALID")
    entries = registry.get("file_entries")
    if registry.get("raw_file_count") != 29 or not isinstance(entries, list) or len(entries) != 29:
        raise RuntimeClosureError("RUNTIME_CLOSURE_REGISTRY_V6_INVALID")
    registry_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("origin") not in {"accepted-v3", "repair-v5"} or not isinstance(entry.get("path"), str):
            raise RuntimeClosureError("RUNTIME_CLOSURE_REGISTRY_V6_INVALID")
        source = (
            f"{_ACCEPTED_V3}/{entry['path']}"
            if entry["origin"] == "accepted-v3"
            else f"{_EXPERIMENT_PREFIX}/{entry['path']}"
        )
        add(source, "registry_v6_raw_input")
        registry_paths.add(source)
    if len(registry_paths) != 29:
        raise RuntimeClosureError("RUNTIME_CLOSURE_REGISTRY_V6_INVALID")

    repair = _canonical_object(repository / _REPAIR_MANIFEST_V5, "RUNTIME_CLOSURE_REPAIR_MANIFEST_INVALID")
    payloads = repair.get("payloads")
    if repair.get("payload_count") != 9 or not isinstance(payloads, list) or len(payloads) != 9:
        raise RuntimeClosureError("RUNTIME_CLOSURE_REPAIR_MANIFEST_INVALID")
    for item in payloads:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise RuntimeClosureError("RUNTIME_CLOSURE_REPAIR_MANIFEST_INVALID")
        add(f"{_EXPERIMENT_PREFIX}/{item['path']}", "repair_v5_payload")

    return classes


def _referenced_runtime_paths_v3(repository: Path) -> dict[str, set[str]]:
    """Extend the complete v2 input universe with its append-only history."""
    classes = _referenced_runtime_paths_v2(repository)
    for path in (_CLOSURE_V2_RECEIPT, _CLOSURE_V2_SUPERSESSION):
        classes.setdefault(path, set()).add("known_mandatory")
    return classes


def _git_blob_binding(repository: Path, freeze_commit: str, relative_path: str) -> dict[str, object]:
    """Bind bytes from the frozen Git tree without consulting mutable live state."""
    try:
        normalized = require_relative_posix_path(relative_path).as_posix()
        blob_oid = _git(repository, "rev-parse", f"{freeze_commit}:{normalized}").decode("ascii").strip()
        if len(blob_oid) not in {40, 64}:
            raise ValueError
        int(blob_oid, 16)
        committed = _git(repository, "cat-file", "blob", blob_oid)
    except RuntimeClosureError as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_UNCOMMITTED_INPUT") from error
    except (UnicodeDecodeError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_GIT_BLOB_OID_INVALID") from error
    return {
        "byte_length": len(committed),
        "git_blob_oid": blob_oid,
        "path": normalized,
        "sha256": sha256_bytes(committed),
    }


@lru_cache(maxsize=8)
def _load_historical_blob_catalog(
    path: str, modified_ns: int, byte_length: int
) -> dict[str, dict[str, object]]:
    """Load one immutable catalog revision once per process."""
    del modified_ns, byte_length
    try:
        with gzip.open(path, "rb") as stream:
            raw_catalog = stream.read()
        catalog = json.loads(raw_catalog)
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID") from error
    if (
        not isinstance(catalog, dict)
        or canonical_json_bytes(catalog) != raw_catalog
        or catalog.get("schema_version") != 1
        or not isinstance(catalog.get("blobs"), list)
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    values = catalog["blobs"]
    if any(not isinstance(item, dict) for item in values):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    result = {str(item.get("git_blob_oid")): item for item in values}
    if len(result) != len(values):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    return result


def _archived_blob_binding(
    repository: Path, recorded: Mapping[str, object]
) -> dict[str, object]:
    """Reconstruct one recorded Git blob from the package-local content archive."""
    oid = recorded.get("git_blob_oid")
    if not isinstance(oid, str):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    path = repository / _HISTORICAL_BLOB_CATALOG
    try:
        status = path.stat()
    except OSError as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID") from error
    item = _load_historical_blob_catalog(
        str(path), status.st_mtime_ns, status.st_size
    ).get(oid)
    if item is None:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    if set(item) != {"byte_length", "content_base64", "git_blob_oid", "sha256"}:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    try:
        raw = base64.b64decode(item["content_base64"], validate=True)
    except (TypeError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID") from error
    git_oid = hashlib.sha1(
        f"blob {len(raw)}\0".encode("ascii") + raw
    ).hexdigest()
    binding = {
        "byte_length": len(raw),
        "git_blob_oid": git_oid,
        "path": recorded.get("path"),
        "sha256": sha256_bytes(raw),
    }
    if (
        item.get("byte_length") != len(raw)
        or item.get("sha256") != binding["sha256"]
        or git_oid != oid
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_ARCHIVED_BLOB_INVALID")
    return binding


def _verify_recorded_historical_binding(
    repository: Path, commit: str, recorded: Mapping[str, object]
) -> None:
    """Verify against Git when available, otherwise against the archived Git blob."""
    path = recorded.get("path")
    if not isinstance(path, str):
        raise RuntimeClosureError("RUNTIME_CLOSURE_HISTORY_ENTRY_INVALID")
    if has_publication_manifest(repository):
        frozen = _archived_blob_binding(repository, recorded)
    else:
        frozen = _git_blob_binding(repository, commit, path)
    if any(
        recorded.get(key) != frozen.get(key)
        for key in ("path", "byte_length", "sha256", "git_blob_oid")
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_HISTORY_MISMATCH")


def _git_bound_entry(repository: Path, freeze_commit: str, relative_path: str, kinds: set[str]) -> dict[str, object]:
    frozen = _git_blob_binding(repository, freeze_commit, relative_path)
    current = closure_entry(repository, relative_path)
    if (
        current["byte_length"] != frozen["byte_length"]
        or current["sha256"] != frozen["sha256"]
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_UNCOMMITTED_INPUT")
    return {**current, "classes": sorted(kinds), "git_blob_oid": frozen["git_blob_oid"]}


def _build_versioned_runtime_closure(
    repository: Path,
    *,
    freeze_commit: str | None,
    classes: dict[str, set[str]],
    schema_version: str,
) -> dict[str, object]:
    """Build common runtime/tool custody for one schema version."""
    ambient_tool_environment = _require_clean_tool_environment()
    repository = repository.resolve(strict=True)
    experiment = repository / _EXPERIMENT_PREFIX
    if freeze_commit is None:
        freeze_commit = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    if not isinstance(freeze_commit, str) or len(freeze_commit) != 40:
        raise RuntimeClosureError("RUNTIME_CLOSURE_FREEZE_COMMIT_INVALID")
    try:
        int(freeze_commit, 16)
    except ValueError as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_FREEZE_COMMIT_INVALID") from error
    _git(repository, "cat-file", "-e", f"{freeze_commit}^{{commit}}")

    discovery = _fresh_python_discovery(experiment)
    for origin in discovery["module_origins"]:
        assert isinstance(origin, dict)
        try:
            relative = Path(str(origin["path"])).resolve(strict=True).relative_to(repository).as_posix()
        except ValueError:
            continue
        classes.setdefault(relative, set()).add("dynamic_python_module")
    return {
        "entries": [
            _git_bound_entry(repository, freeze_commit, path, kinds)
            for path, kinds in sorted(classes.items())
        ],
        "freeze_commit": freeze_commit,
        "future_targets": future_target_inventory_v6(),
        "roots": {
            "experiment": _repository_relative(repository, experiment),
            "repository": os.fspath(repository),
        },
        "ambient_tool_environment": ambient_tool_environment,
        "schema_version": schema_version,
        "tools": _tool_identities(repository, experiment),
    }


def build_runtime_closure_v2(repository: Path, *, freeze_commit: str | None = None) -> dict[str, object]:
    """Build the transitive, tool-bound successor closure from code authority."""
    repository = repository.resolve(strict=True)
    return _build_versioned_runtime_closure(
        repository,
        freeze_commit=freeze_commit,
        classes=_referenced_runtime_paths_v2(repository),
        schema_version="runtime-executable-closure-v2",
    )


def verify_runtime_closure_v2(closure: object, repository: Path) -> dict[str, object]:
    """Rebuild the complete closure and reject any file, tool, env, or target drift."""
    if not isinstance(closure, Mapping) or closure.get("schema_version") != "runtime-executable-closure-v2":
        raise RuntimeClosureError("RUNTIME_CLOSURE_V2_INVALID")
    freeze_commit = closure.get("freeze_commit")
    if not isinstance(freeze_commit, str):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V2_INVALID")
    rebuilt = build_runtime_closure_v2(repository, freeze_commit=freeze_commit)
    if dict(closure) != rebuilt:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V2_MISMATCH")
    return rebuilt


def validate_runtime_closure_v2_supersession(
    receipt: object, *, predecessor_raw: bytes,
) -> dict[str, object]:
    """Validate the exact non-authorizing reason v2 cannot seed a proposal."""
    if (
        len(predecessor_raw) != _CLOSURE_V2_BYTE_LENGTH
        or sha256_bytes(predecessor_raw) != _CLOSURE_V2_SHA256
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V2_HISTORY_INVALID")
    expected = {
        "authorization_recorded": False,
        "candidate_exists": False,
        "defects": [
            {
                "code": "AUTHORITY_PRE_STATE_NOT_FREEZE_BOUND",
                "detail": (
                    "The v2 receipt does not bind phase2/source-authority.json to "
                    "its freeze commit, so a later proposal could silently rebind drifted bytes."
                ),
            }
        ],
        "external_publication_authorized": False,
        "local_only": True,
        "predecessor": {
            "byte_length": _CLOSURE_V2_BYTE_LENGTH,
            "path": _CLOSURE_V2_RECEIPT,
            "sha256": _CLOSURE_V2_SHA256,
        },
        "replacement": {
            "path": f"{_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v3.json",
            "schema_version": "runtime-executable-closure-v3",
        },
        "schema_version": "runtime-executable-closure-v2-non-authorizing-supersession-v1",
        "status": "superseded_pre_authorization_authority_pre_state_unbound",
        "successor_proposal_exists": False,
    }
    if not isinstance(receipt, Mapping) or dict(receipt) != expected:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V2_SUPERSESSION_INVALID")
    return expected


def build_runtime_closure_v3(repository: Path, *, freeze_commit: str | None = None) -> dict[str, object]:
    """Build the successor closure with a freeze-tree authority pre-state anchor."""
    repository = repository.resolve(strict=True)
    common = _build_versioned_runtime_closure(
        repository,
        freeze_commit=freeze_commit,
        classes=_referenced_runtime_paths_v3(repository),
        schema_version="runtime-executable-closure-v3",
    )
    frozen = common["freeze_commit"]
    assert isinstance(frozen, str)
    return {
        **common,
        "authority_pre_state": _git_blob_binding(repository, frozen, _AUTHORITY_PRE_STATE),
        "predecessor_closure_v2": _git_blob_binding(
            repository, frozen, _CLOSURE_V2_RECEIPT
        ),
    }


def verify_runtime_closure_v3(
    closure: object, repository: Path, *, authority_pre_state_raw: bytes,
) -> dict[str, object]:
    """Rebuild v3 and require the supplied historical authority to match the freeze tree."""
    if (
        not isinstance(closure, Mapping)
        or closure.get("schema_version") != "runtime-executable-closure-v3"
        or not isinstance(authority_pre_state_raw, bytes)
        or not authority_pre_state_raw
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_INVALID")
    freeze_commit = closure.get("freeze_commit")
    if not isinstance(freeze_commit, str):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_INVALID")
    rebuilt = build_runtime_closure_v3(repository, freeze_commit=freeze_commit)
    if dict(closure) != rebuilt:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_MISMATCH")
    authority = rebuilt["authority_pre_state"]
    assert isinstance(authority, dict)
    if (
        authority.get("byte_length") != len(authority_pre_state_raw)
        or authority.get("sha256") != sha256_bytes(authority_pre_state_raw)
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_AUTHORITY_PRESTATE_INVALID")
    return rebuilt


def validate_future_target_occupancy_v6(
    repository: Path, *, allowed_existing: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    """Reject occupied, missing-from-code, or caller-invented future outputs."""
    expected = future_target_inventory_v6()
    expected_paths = {entry["path"] for entry in expected}
    if not isinstance(allowed_existing, (set, frozenset)) or not allowed_existing <= expected_paths:
        raise RuntimeClosureError("V6_TARGET_OCCUPANCY_ALLOWLIST_INVALID")
    for entry in expected:
        path = entry["path"]
        occupied = (repository / path).exists() or (repository / path).is_symlink()
        if occupied != (path in allowed_existing):
            raise RuntimeClosureError("V6_TARGET_OCCUPANCY_MISMATCH")
    return expected


# v4 is deliberately a downstream-only closure.  Its receipt is an output, not
# an input: bootstrap must be useful precisely while that receipt is absent.
_CLOSURE_V4_RECEIPT = f"{_EXPERIMENT_PREFIX}/receipts/runtime-executable-closure-v4.json"
_CLOSURE_V4_FREEZE = "47ffaa1c5be6c058a3316cf7f8c56260c1e6ebde"
_CLOSURE_V4_BYTE_LENGTH = 127457
_CLOSURE_V4_SHA256 = "ccaa237c248d374fad781f6645d603d8d64710e8e4c0a748254caccbb7f4a018"
_PHASE2_LIFECYCLE_RECEIPT = (
    f"{_EXPERIMENT_PREFIX}/receipts/phase2-lifecycle-successor-v1.json"
)
_PHASE2_LIFECYCLE_BYTE_LENGTH = 6546
_PHASE2_LIFECYCLE_SHA256 = "5299154e4671d8957b40d6c3b874dd96331100874f0ee92c9d1d221947b57afc"
_PHASE2_EVIDENCE_COMMIT = "dc3e5883a10cd3efe1393220caf1f711561867b9"
_PHASE2_TRACKING_COMMIT = "d419689d829214e0913013c3de0268ffb987f826"
_PHASE2_TRACKING_PATHS = (
    _LEGACY_PLANNING + "REQUIREMENTS.md",
    _LEGACY_PLANNING + "ROADMAP.md",
    _LEGACY_PLANNING + "STATE.md",
)
_PHASE2_SUCCESSOR_CODE_PATHS = (
    f"{_EXPERIMENT_PREFIX}/src/specchoice_data/cli.py",
    f"{_EXPERIMENT_PREFIX}/src/specchoice_evidence/runtime_closure.py",
)
_ACCEPTED_V6 = (
    f"{_EXPERIMENT_PREFIX}/bundles/accepted/"
    "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
)
_V4_AUTHORITY_SHA256 = "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae"
_V4_ACCEPTED_IDENTITY = {
    "core_sha256": "3a55a816904c787bd6e1ffc78c1cb90fd4503cbe30022477472e777612b6d547",
    "root_sha256": "bd75dbc97869630bbaa41dbe48c3eb1b743b7c1022bd950180b7675ecf4dd1e9",
    "snapshot_manifest_sha256": "a143334abbbc15bf455789c862ffb0ece13047348e1e91aad3f71a8a7c7cbdd0",
}
_POST_CLOSURE_TARGETS_V4: tuple[str, ...] = tuple(sorted((
    f"{_EXPERIMENT_PREFIX}/reports/h1/adapter-batch-pr2164-v6.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/attempt.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/case-outcomes.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/diagnostics.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/metrics.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/parsed-predictions.json",
    f"{_EXPERIMENT_PREFIX}/runs/measurement-attempts/formal-golden-pr2164-v6/report.json",
    f"{_EXPERIMENT_PREFIX}/reports/h1/adversarial-oracle-results-v7.json",
    f"{_EXPERIMENT_PREFIX}/reports/h1/h1-source-gold-review-v7/review-packet.json",
    f"{_EXPERIMENT_PREFIX}/reports/h1/h1-source-gold-review-v7/review-packet.md",
    f"{_EXPERIMENT_PREFIX}/receipts/h1-review-readiness-v7.json",
    f"{_EXPERIMENT_PREFIX}/reviews/h1-source-gold-decision-v6.json",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION-02-22.md",
    _LEGACY_PLANNING + "phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW-02-22.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-VERIFICATION-02-22.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-REVIEW-02-22.md",
    _LEGACY_PLANNING + "phases/02-deterministic-measurement-spine/02-22-SUMMARY.md",
)))


def _validate_current_publication(repository: Path) -> dict[str, object]:
    """Require the current package authority while tolerating unavailable history."""
    try:
        return validate_publication_manifest(
            repository, publication_manifest_path(repository)
        )
    except PublicationContractError as error:
        raise RuntimeClosureError("PUBLICATION_CONTRACT_INVALID") from error


def _historical_commit_is_available(repository: Path, commit: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        capture_output=True,
        env=_git_environment(),
    )
    return completed.returncode == 0


def _validate_historical_entry_shape(entry: object) -> str:
    if not isinstance(entry, Mapping) or set(entry) != {
        "byte_length", "classes", "git_blob_oid", "path", "sha256"
    }:
        raise RuntimeClosureError("RUNTIME_CLOSURE_HISTORY_ENTRY_INVALID")
    try:
        path = require_relative_posix_path(entry["path"]).as_posix()
        require_byte_length(entry["byte_length"])
        require_sha256(entry["sha256"])
        oid = entry["git_blob_oid"]
        if not isinstance(oid, str) or len(oid) not in {40, 64}:
            raise ValueError
        int(oid, 16)
        classes = entry["classes"]
        if not isinstance(classes, list) or not classes or classes != sorted(set(classes)):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_HISTORY_ENTRY_INVALID") from error
    return path


def future_target_inventory_v7() -> list[dict[str, str]]:
    """Return the closed, typed, path-sorted v4 successor target set."""
    return [{"kind": "file", "path": path} for path in _POST_CLOSURE_TARGETS_V4]


def _v4_target_state(repository: Path, relative: str) -> str:
    """Classify a target without following links or accepting partial objects."""
    import stat

    candidate = repository / relative
    try:
        status = candidate.lstat()
    except FileNotFoundError:
        return "absent"
    if stat.S_ISLNK(status.st_mode):
        return "symlink"
    if stat.S_ISREG(status.st_mode):
        return "file"
    if stat.S_ISDIR(status.st_mode):
        return "directory"
    return "special"


def validate_runtime_closure_v4_bootstrap_targets(repository: Path) -> list[dict[str, str]]:
    """Fail before publication unless every future target and receipt is absent."""
    repository = repository.resolve(strict=True)
    for entry in future_target_inventory_v7():
        if _v4_target_state(repository, entry["path"]) != "absent":
            raise RuntimeClosureError("RUNTIME_CLOSURE_V4_BOOTSTRAP_TARGET_OCCUPIED")
    # Do not open the receipt here.  lstat is intentionally the only interaction
    # with the output path before its future no-replace writer opens it.
    if _v4_target_state(repository, _CLOSURE_V4_RECEIPT) != "absent":
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_RECEIPT_OCCUPIED")
    return future_target_inventory_v7()


def _v4_authority_identity(repository: Path) -> dict[str, object]:
    # Do not treat the authority's self-reported identity as custody.  The
    # successor validator walks the accepted-v6 cutover chain and verifies the
    # receipts before the v4 closure is allowed to bind it.
    try:
        from .successor import SuccessorProtocolError, validate_accepted_v6_for_downstream_v4

        validated = validate_accepted_v6_for_downstream_v4(repository)
    except (ImportError, SuccessorProtocolError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_AUTHORITY_INVALID") from error
    authority_path = repository / _AUTHORITY_PRE_STATE
    authority, raw = _canonical_object_with_raw(
        authority_path, "RUNTIME_CLOSURE_V4_AUTHORITY_INVALID",
    )
    if sha256_bytes(raw) != _V4_AUTHORITY_SHA256:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_AUTHORITY_SHA256_MISMATCH")
    accepted = authority.get("accepted_identity")
    if not isinstance(accepted, Mapping) or {key: accepted.get(key) for key in _V4_ACCEPTED_IDENTITY} != _V4_ACCEPTED_IDENTITY:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_IDENTITY_MISMATCH")
    manifest = _canonical_object(repository / f"{_ACCEPTED_V6}/snapshot-manifest.json", "RUNTIME_CLOSURE_V4_ACCEPTED_MANIFEST_INVALID")
    if (
        manifest.get("manifest_sha256") != _V4_ACCEPTED_IDENTITY["core_sha256"]
        or manifest.get("root_sha256") != _V4_ACCEPTED_IDENTITY["root_sha256"]
        or manifest.get("snapshot_manifest_sha256") != _V4_ACCEPTED_IDENTITY["snapshot_manifest_sha256"]
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_MANIFEST_MISMATCH")
    if {key: validated.get(key) for key in _V4_ACCEPTED_IDENTITY} != _V4_ACCEPTED_IDENTITY:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_IDENTITY_MISMATCH")
    paths = validated.get("bound_paths")
    if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_AUTHORITY_INVALID")
    return {"authority_sha256": _V4_AUTHORITY_SHA256, **_V4_ACCEPTED_IDENTITY, "bound_paths": paths}


def verify_runtime_closure_v3_historical(closure: object, repository: Path) -> dict[str, object]:
    """Verify v3 from its recorded Git tree without consulting mutable v3 inputs."""
    if not isinstance(closure, Mapping) or closure.get("schema_version") != "runtime-executable-closure-v3":
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_INVALID")
    receipt_path = repository / _CLOSURE_V3_RECEIPT
    expected, raw = _canonical_object_with_raw(
        receipt_path, "RUNTIME_CLOSURE_V3_HISTORY_INVALID",
    )
    if len(raw) != _CLOSURE_V3_BYTE_LENGTH or sha256_bytes(raw) != _CLOSURE_V3_SHA256:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_RECEIPT_INVALID")
    if dict(closure) != expected:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_MISMATCH")
    freeze_commit = expected.get("freeze_commit")
    if freeze_commit != _CLOSURE_V3_FREEZE:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_FREEZE_INVALID")
    entries = expected.get("entries")
    if not isinstance(entries, list) or len(entries) != 103:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_INVALID")
    paths: list[str] = []
    for entry in entries:
        path = _validate_historical_entry_shape(entry)
        paths.append(path)
        assert isinstance(entry, Mapping)
        _verify_recorded_historical_binding(repository, freeze_commit, entry)
    if paths != sorted(paths) or len(set(paths)) != 103:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_INVALID")
    if has_publication_manifest(repository):
        publication = _validate_current_publication(repository)
        provenance = publication.get("historical_provenance")
        if not isinstance(provenance, list) or not any(
            isinstance(item, Mapping) and item.get("commit_sha") == freeze_commit
            for item in provenance
        ):
            raise RuntimeClosureError("RUNTIME_CLOSURE_V3_HISTORY_FREEZE_INVALID")
    return expected


def _v4_accepted_tree_paths(repository: Path) -> set[str]:
    """Return every ordinary accepted-v6 leaf, rejecting links and partial raw trees."""
    root = repository / _ACCEPTED_V6
    try:
        files = sorted(root.rglob("*"))
    except OSError as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_TREE_INVALID") from error
    paths: set[str] = set()
    raw_paths: set[str] = set()
    for item in files:
        try:
            status = item.lstat()
        except OSError as error:
            raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_TREE_INVALID") from error
        import stat
        if stat.S_ISLNK(status.st_mode):
            raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_TREE_INVALID")
        if stat.S_ISDIR(status.st_mode):
            continue
        if not stat.S_ISREG(status.st_mode):
            raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_TREE_INVALID")
        if stat.S_ISREG(status.st_mode):
            relative = _repository_relative(repository, item)
            paths.add(relative)
            marker = f"{_ACCEPTED_V6}/raw/evaluation_fixtures/"
            if relative.startswith(marker):
                raw_paths.add(relative)
    if len(raw_paths) != 29 or len(paths) < 30:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_TREE_INVALID")
    return paths


def _v4_classes(repository: Path) -> dict[str, set[str]]:
    """Bind code, all accepted-v6 bytes, and each fixed active-lineage input."""
    classes = _referenced_runtime_paths_v3(repository)
    for path in (
        f"{_EXPERIMENT_PREFIX}/config/measurement/pr2164-adapter-rules-v4.json",
        f"{_EXPERIMENT_PREFIX}/config/measurement/h1-review-schema-v5.json",
    ):
        classes.setdefault(path, set()).add("v4_control")
    for path in _v4_accepted_tree_paths(repository):
        classes.setdefault(path, set()).add("accepted_v6_materialized")
    try:
        from .successor import SuccessorProtocolError, accepted_v6_active_bound_paths

        lineage = accepted_v6_active_bound_paths(repository)
    except (ImportError, SuccessorProtocolError) as error:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_ACCEPTED_AUTHORITY_INVALID") from error
    for path in lineage:
        classes.setdefault(path, set()).add("accepted_v6_source_lineage")
    return classes


def _runtime_closure_v4_projection(repository: Path, *, freeze_commit: str | None) -> dict[str, object]:
    """Rebuild a v4 receipt without inspecting later downstream outputs."""
    common = _build_versioned_runtime_closure(
        repository,
        freeze_commit=freeze_commit,
        classes=_v4_classes(repository),
        schema_version="runtime-executable-closure-v4",
    )
    historical = _canonical_object(repository / _CLOSURE_V3_RECEIPT, "RUNTIME_CLOSURE_V3_HISTORY_INVALID")
    verify_runtime_closure_v3_historical(historical, repository)
    future_targets = future_target_inventory_v7()
    return {
        **common,
        "accepted_v6_identity": _v4_authority_identity(repository),
        "bootstrap_receipt_path": _CLOSURE_V4_RECEIPT,
        "bootstrap_target_prestate": [{"path": entry["path"], "state": "absent"} for entry in future_targets],
        "future_targets": future_targets,
        "historical_closure_v3": {
            "byte_length": _CLOSURE_V3_BYTE_LENGTH,
            "freeze_commit": historical["freeze_commit"],
            "path": _CLOSURE_V3_RECEIPT,
            "sha256": _CLOSURE_V3_SHA256,
        },
    }


def build_runtime_closure_v4(repository: Path, *, freeze_commit: str | None = None) -> dict[str, object]:
    """Build only the absent-receipt bootstrap projection for closure v4."""
    repository = repository.resolve(strict=True)
    targets = validate_runtime_closure_v4_bootstrap_targets(repository)
    closure = _runtime_closure_v4_projection(repository, freeze_commit=freeze_commit)
    if closure["future_targets"] != targets:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_TARGET_INVENTORY_INVALID")
    return closure


def verify_runtime_closure_v4(closure: object, repository: Path) -> dict[str, object]:
    """Require the entire closure receipt, not merely its schema marker."""
    if not isinstance(closure, Mapping) or closure.get("schema_version") != "runtime-executable-closure-v4":
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_INVALID")
    freeze_commit = closure.get("freeze_commit")
    if not isinstance(freeze_commit, str):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_INVALID")
    rebuilt = _runtime_closure_v4_projection(repository.resolve(strict=True), freeze_commit=freeze_commit)
    if dict(closure) != rebuilt:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_MISMATCH")
    return rebuilt


def load_runtime_closure_v4(repository: Path, supplied: object) -> dict[str, object]:
    """Load the one published v4 receipt and reject an unmaterialized mapping."""
    receipt_path = repository.resolve(strict=True) / _CLOSURE_V4_RECEIPT
    receipt = _canonical_object(receipt_path, "RUNTIME_CLOSURE_V4_RECEIPT_REQUIRED")
    verified = verify_runtime_closure_v4(receipt, repository)
    if not isinstance(supplied, Mapping) or dict(supplied) != verified:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_RECEIPT_MISMATCH")
    return verified


def verify_runtime_closure_v4_historical(closure: object, repository: Path) -> dict[str, object]:
    """Verify the published v4 receipt from its frozen Git tree after lifecycle close."""
    if not isinstance(closure, Mapping) or closure.get("schema_version") != "runtime-executable-closure-v4":
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_INVALID")
    expected, raw = _canonical_object_with_raw(
        repository.resolve(strict=True) / _CLOSURE_V4_RECEIPT,
        "RUNTIME_CLOSURE_V4_HISTORY_INVALID",
    )
    if (
        len(raw) != _CLOSURE_V4_BYTE_LENGTH
        or sha256_bytes(raw) != _CLOSURE_V4_SHA256
        or dict(closure) != expected
        or expected.get("freeze_commit") != _CLOSURE_V4_FREEZE
        or expected.get("future_targets") != future_target_inventory_v7()
    ):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_MISMATCH")
    entries = expected.get("entries")
    if not isinstance(entries, list) or len(entries) != 198:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_INVALID")
    paths: list[str] = []
    for entry in entries:
        path = _validate_historical_entry_shape(entry)
        paths.append(path)
        assert isinstance(entry, Mapping)
        _verify_recorded_historical_binding(
            repository, _CLOSURE_V4_FREEZE, entry
        )
    if paths != sorted(paths) or len(set(paths)) != 198:
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_INVALID")
    historical = expected.get("historical_closure_v3")
    if not isinstance(historical, Mapping):
        raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_INVALID")
    if has_publication_manifest(repository):
        publication = _validate_current_publication(repository)
        provenance = publication.get("historical_provenance")
        if not isinstance(provenance, list) or not any(
            isinstance(item, Mapping) and item.get("commit_sha") == _CLOSURE_V4_FREEZE
            for item in provenance
        ):
            raise RuntimeClosureError("RUNTIME_CLOSURE_V4_HISTORY_FREEZE_INVALID")
    verify_runtime_closure_v3_historical(
        _canonical_object(repository / _CLOSURE_V3_RECEIPT, "RUNTIME_CLOSURE_V3_HISTORY_INVALID"),
        repository,
    )
    return expected


def _require_commit_ancestor(repository: Path, ancestor: str, descendant: str) -> None:
    try:
        _git(repository, "merge-base", "--is-ancestor", ancestor, descendant)
    except RuntimeClosureError as error:
        raise RuntimeClosureError("PHASE2_LIFECYCLE_ANCESTRY_INVALID") from error


def _lifecycle_binding(
    repository: Path, commit: str, path: str, *, require_current: bool,
) -> dict[str, object]:
    frozen = _git_blob_binding(repository, commit, path)
    if require_current:
        current = closure_entry(repository, path)
        if any(current.get(key) != frozen.get(key) for key in ("path", "byte_length", "sha256")):
            raise RuntimeClosureError("PHASE2_LIFECYCLE_CURRENT_BYTES_CHANGED")
    return frozen


def _verify_published_lifecycle_bindings(
    repository: Path,
    values: object,
    commit: str,
    diagnostic: str,
) -> list[dict[str, object]]:
    if not isinstance(values, list) or not values:
        raise RuntimeClosureError(diagnostic)
    result: list[dict[str, object]] = []
    paths: list[str] = []
    for value in values:
        if not isinstance(value, Mapping) or set(value) != {
            "byte_length", "git_blob_oid", "path", "sha256"
        }:
            raise RuntimeClosureError(diagnostic)
        try:
            path = require_relative_posix_path(value["path"]).as_posix()
            require_byte_length(value["byte_length"])
            require_sha256(value["sha256"])
            oid = value["git_blob_oid"]
            if not isinstance(oid, str) or len(oid) not in {40, 64}:
                raise ValueError
            int(oid, 16)
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeClosureError(diagnostic) from error
        _verify_recorded_historical_binding(repository, commit, value)
        paths.append(path)
        result.append(dict(value))
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeClosureError(diagnostic)
    return result


def _verify_published_phase2_lifecycle_successor_v1(
    successor: Mapping[str, object], repository: Path
) -> dict[str, object]:
    """Verify the immutable lifecycle receipt without requiring old DAG ancestry."""
    expected, raw = _canonical_object_with_raw(
        repository.resolve(strict=True) / _PHASE2_LIFECYCLE_RECEIPT,
        "PHASE2_LIFECYCLE_SUCCESSOR_INVALID",
    )
    if (
        len(raw) != _PHASE2_LIFECYCLE_BYTE_LENGTH
        or sha256_bytes(raw) != _PHASE2_LIFECYCLE_SHA256
        or dict(successor) != expected
        or expected.get("code_freeze_commit") != "470065e0237418ec4198c1c75c63530d1d9b7c5c"
        or expected.get("evidence_commit") != _PHASE2_EVIDENCE_COMMIT
        or expected.get("tracking_commit") != _PHASE2_TRACKING_COMMIT
        or expected.get("external_publication_authorized") is not False
        or expected.get("local_only") is not True
    ):
        raise RuntimeClosureError("PHASE2_LIFECYCLE_SUCCESSOR_MISMATCH")
    payload = dict(expected)
    recorded_sha = payload.pop("successor_sha256", None)
    if recorded_sha != sha256_bytes(canonical_json_bytes(payload)):
        raise RuntimeClosureError("PHASE2_LIFECYCLE_SUCCESSOR_MISMATCH")
    _verify_published_lifecycle_bindings(
        repository,
        expected.get("code_bindings"),
        str(expected["code_freeze_commit"]),
        "PHASE2_LIFECYCLE_CODE_BINDINGS_INVALID",
    )
    _verify_published_lifecycle_bindings(
        repository,
        expected.get("evidence_bindings"),
        _PHASE2_EVIDENCE_COMMIT,
        "PHASE2_LIFECYCLE_EVIDENCE_BINDINGS_INVALID",
    )
    _verify_published_lifecycle_bindings(
        repository,
        expected.get("tracking_bindings"),
        _PHASE2_TRACKING_COMMIT,
        "PHASE2_LIFECYCLE_TRACKING_BINDINGS_INVALID",
    )
    predecessor = _canonical_object(
        repository.resolve(strict=True) / _CLOSURE_V4_RECEIPT,
        "RUNTIME_CLOSURE_V4_HISTORY_INVALID",
    )
    verify_runtime_closure_v4_historical(predecessor, repository)
    _validate_current_publication(repository.resolve(strict=True))
    return expected


def build_phase2_lifecycle_successor_v1(
    repository: Path, *, code_freeze_commit: str,
) -> dict[str, object]:
    """Bind the validated v4 freeze, terminal evidence, and tracking transition forward-only."""
    repository = repository.resolve(strict=True)
    head = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    for commit in (
        _PHASE2_EVIDENCE_COMMIT,
        _PHASE2_TRACKING_COMMIT,
        code_freeze_commit,
        head,
    ):
        if len(commit) != 40:
            raise RuntimeClosureError("PHASE2_LIFECYCLE_COMMIT_INVALID")
        try:
            int(commit, 16)
        except ValueError as error:
            raise RuntimeClosureError("PHASE2_LIFECYCLE_COMMIT_INVALID") from error
        _git(repository, "cat-file", "-e", f"{commit}^{{commit}}")
    _require_commit_ancestor(repository, _PHASE2_EVIDENCE_COMMIT, _PHASE2_TRACKING_COMMIT)
    _require_commit_ancestor(repository, _PHASE2_TRACKING_COMMIT, code_freeze_commit)
    _require_commit_ancestor(repository, code_freeze_commit, head)
    try:
        _git(repository, "cat-file", "-e", f"{code_freeze_commit}:{_PHASE2_LIFECYCLE_RECEIPT}")
    except RuntimeClosureError:
        pass
    else:
        raise RuntimeClosureError("PHASE2_LIFECYCLE_RECEIPT_PREEXISTED")

    predecessor = _canonical_object(
        repository / _CLOSURE_V4_RECEIPT,
        "RUNTIME_CLOSURE_V4_HISTORY_INVALID",
    )
    verify_runtime_closure_v4_historical(predecessor, repository)
    evidence_paths = sorted(
        {
            _AUTHORITY_PRE_STATE,
            _CLOSURE_V4_RECEIPT,
            *(entry["path"] for entry in future_target_inventory_v7()),
        }
    )
    evidence_bindings = [
        _lifecycle_binding(
            repository, _PHASE2_EVIDENCE_COMMIT, path, require_current=True,
        )
        for path in evidence_paths
    ]
    tracking_bindings = [
        _lifecycle_binding(
            repository, _PHASE2_TRACKING_COMMIT, path, require_current=False,
        )
        for path in sorted(_PHASE2_TRACKING_PATHS)
    ]
    code_bindings = [
        _lifecycle_binding(repository, code_freeze_commit, path, require_current=True)
        for path in sorted(_PHASE2_SUCCESSOR_CODE_PATHS)
    ]
    payload: dict[str, object] = {
        "code_bindings": code_bindings,
        "code_freeze_commit": code_freeze_commit,
        "evidence_bindings": evidence_bindings,
        "evidence_commit": _PHASE2_EVIDENCE_COMMIT,
        "external_publication_authorized": False,
        "local_only": True,
        "predecessor_runtime_closure": {
            "byte_length": _CLOSURE_V4_BYTE_LENGTH,
            "freeze_commit": _CLOSURE_V4_FREEZE,
            "path": _CLOSURE_V4_RECEIPT,
            "sha256": _CLOSURE_V4_SHA256,
        },
        "receipt_prestate": {
            "path": _PHASE2_LIFECYCLE_RECEIPT,
            "state_at_code_freeze": "absent",
        },
        "schema_version": "phase2-lifecycle-successor-v1",
        "tracking_bindings": tracking_bindings,
        "tracking_commit": _PHASE2_TRACKING_COMMIT,
    }
    return {
        **payload,
        "successor_sha256": sha256_bytes(canonical_json_bytes(payload)),
    }


def verify_phase2_lifecycle_successor_v1(
    successor: object, repository: Path,
) -> dict[str, object]:
    """Rebuild the lifecycle successor and reject alternate history or mutable authority."""
    if (
        not isinstance(successor, Mapping)
        or successor.get("schema_version") != "phase2-lifecycle-successor-v1"
        or not isinstance(successor.get("code_freeze_commit"), str)
    ):
        raise RuntimeClosureError("PHASE2_LIFECYCLE_SUCCESSOR_INVALID")
    if has_publication_manifest(repository):
        return _verify_published_phase2_lifecycle_successor_v1(
            successor, repository
        )
    rebuilt = build_phase2_lifecycle_successor_v1(
        repository,
        code_freeze_commit=str(successor["code_freeze_commit"]),
    )
    if dict(successor) != rebuilt:
        raise RuntimeClosureError("PHASE2_LIFECYCLE_SUCCESSOR_MISMATCH")
    return rebuilt


def load_phase2_lifecycle_successor_v1(
    repository: Path, supplied: object,
) -> dict[str, object]:
    """Load the one canonical local lifecycle successor receipt."""
    receipt = _canonical_object(
        repository.resolve(strict=True) / _PHASE2_LIFECYCLE_RECEIPT,
        "PHASE2_LIFECYCLE_SUCCESSOR_REQUIRED",
    )
    verified = verify_phase2_lifecycle_successor_v1(receipt, repository)
    if not isinstance(supplied, Mapping) or dict(supplied) != verified:
        raise RuntimeClosureError("PHASE2_LIFECYCLE_SUCCESSOR_MISMATCH")
    return verified
