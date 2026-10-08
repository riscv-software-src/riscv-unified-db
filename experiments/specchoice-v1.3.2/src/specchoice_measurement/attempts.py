# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Immutable terminal custody for deterministic Phase 2 measurement attempts."""

from __future__ import annotations

import base64
import json
import shutil
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from specchoice_evidence.bundle import BundleError, _publish_directory_no_replace, _sync_directory, _write_exact
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file
from specchoice_evidence.runtime_closure import RuntimeClosureError, load_runtime_closure_v4

from .adapter import (
    build_pr2164_accepted_v6_adapter_batch_v4,
    build_pr2164_adapter_batch,
    build_pr2164_v6_adapter_batch,
    validate_pr2164_accepted_v6_adapter_batch_v4,
)
from .preflight import preflight_prediction_batch
from .scoring import score_prediction_batch


class AttemptError(ValueError):
    """Stable custody or validation diagnostic for a terminal attempt."""


def require_v4_downstream_gate(*, runtime_closure: object, authority_path: Path) -> None:
    """Shared pre-write gate for every fresh v4 evidence writer."""
    try:
        canonical = authority_path.resolve(strict=True)
        repository = canonical.parents[3]
        expected = repository / "experiments/specchoice-v1.3.2/phase2/source-authority.json"
        if canonical != expected:
            raise AttemptError("ACTIVE_AUTHORITY_MISMATCH")
        load_runtime_closure_v4(repository, runtime_closure)
        evidence, authority_raw = read_authoritative_file(canonical.parent, canonical.name)
    except (FilesystemPolicyError, OSError, RuntimeClosureError) as error:
        raise AttemptError("RUNTIME_CLOSURE_V4_REQUIRED") from error
    if (
        evidence.file_kind != "regular_file"
        or evidence.sha256
        != "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae"
        or sha256_bytes(authority_raw)
        != "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae"
    ):
        raise AttemptError("ACTIVE_AUTHORITY_MISMATCH")


def validate_fresh_v4_target(*, target: Path, runtime_closure: object, authority_path: Path, expected: bytes | None = None) -> bool:
    """Require absent creation or byte-exact resume after revalidating authority."""
    require_v4_downstream_gate(runtime_closure=runtime_closure, authority_path=authority_path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise AttemptError("V4_TARGET_KIND_INVALID")
    if not target.exists():
        return False
    try:
        evidence, raw = read_authoritative_file(target.parent, target.name)
    except (FilesystemPolicyError, OSError) as error:
        raise AttemptError("V4_TARGET_DIVERGED") from error
    if evidence.file_kind != "regular_file" or expected is None or raw != expected:
        raise AttemptError("V4_TARGET_DIVERGED")
    return True


_ATTEMPT_KEYS = frozenset({
    "artifacts", "attempt_id", "attempt_sha256", "bindings", "raw_predictions_base64",
    "raw_predictions_sha256", "role", "schema_version", "status",
})
_SCORE_ARTIFACTS = ("case-outcomes.json", "metrics.json", "report.json")
_BASE_ARTIFACTS = ("diagnostics.json", "parsed-predictions.json")
_VALID_ROLES = frozenset({"formal", "diagnostic_only", "invalid_preflight", "completed_with_warnings"})
_ROOT = Path(__file__).parents[2]
_BUNDLE = _ROOT / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
_AUTHORITY = _ROOT / "phase2/source-authority.json"
_RULES = _ROOT / "config/measurement/pr2164-adapter-rules-v1.json"
_SCHEMA = _ROOT / "config/measurement/canonical-adjudication-schema-v1.json"


def _attempt_target(attempt_root: Path, attempt_id: str) -> Path:
    if not attempt_id or "/" in attempt_id or "\\" in attempt_id or attempt_id in {".", ".."}:
        raise AttemptError("ATTEMPT_ID_INVALID")
    target = attempt_root / attempt_id
    if target.exists() or target.is_symlink():
        raise AttemptError("ATTEMPT_TARGET_EXISTS")
    return target


def _as_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise AttemptError(code)
    return dict(value)


def _artifact_payloads(*, inputs: Mapping[str, object], role: str, status: str) -> dict[str, object]:
    preflight = inputs.get("preflight")
    score = inputs.get("score_result")
    if preflight is None or score is None:
        raise AttemptError("ATTEMPT_INPUTS_INCOMPLETE")
    parsed = {
        "parsed_predictions": list(getattr(preflight, "parsed_predictions", ())),
        "raw_prediction_sha256": getattr(preflight, "raw_prediction_sha256", None),
        "status": getattr(preflight, "status", None),
    }
    payloads: dict[str, object] = {
        "diagnostics.json": [item.as_dict() for item in getattr(score, "diagnostics", ())],
        "parsed-predictions.json": parsed,
    }
    if role in {"formal", "completed_with_warnings"}:
        payloads["case-outcomes.json"] = [item.as_dict() for item in getattr(score, "case_outcomes", ())]
        metrics = getattr(score, "metrics", None)
        if metrics is None:
            raise AttemptError("ATTEMPT_SCORE_ARTIFACTS_FORBIDDEN")
        payloads["metrics.json"] = metrics.as_dict()
        payloads["report.json"] = {
            "case_outcomes": payloads["case-outcomes.json"],
            "diagnostics": payloads["diagnostics.json"],
            "metrics": payloads["metrics.json"],
            "role": role,
            "status": status,
        }
    return payloads


def _schema_bytes(inputs: Mapping[str, object]) -> bytes:
    schema_raw = inputs.get("schema_raw")
    if isinstance(schema_raw, bytes):
        return schema_raw
    schema_path = inputs.get("schema_path")
    if not isinstance(schema_path, Path):
        raise AttemptError("ATTEMPT_INPUTS_INCOMPLETE")
    try:
        _, schema_raw = read_authoritative_file(schema_path.parent, schema_path.name)
        return schema_raw
    except (OSError, FilesystemPolicyError) as error:
        raise AttemptError("ATTEMPT_SCHEMA_UNREADABLE") from error


def _bindings(inputs: Mapping[str, object], raw_predictions: bytes) -> dict[str, object]:
    batch = inputs.get("adapter_batch")
    if batch is None:
        raise AttemptError("ATTEMPT_INPUTS_INCOMPLETE")
    schema_raw = _schema_bytes(inputs)
    source_identity = getattr(batch, "source_identity", None)
    if not isinstance(source_identity, dict):
        raise AttemptError("ATTEMPT_SOURCE_IDENTITY_INVALID")
    adapter_sha = getattr(batch, "adapter_batch_sha256", None)
    if not isinstance(adapter_sha, str):
        raise AttemptError("ATTEMPT_ADAPTER_IDENTITY_INVALID")
    return {
        "adapter_batch_sha256": adapter_sha,
        "adapter_version": getattr(batch, "adapter_version", None),
        "ingress": inputs.get("ingress"),
        "raw_predictions_byte_length": len(raw_predictions),
        "raw_predictions_sha256": sha256_bytes(raw_predictions),
        "rule_sha256": getattr(batch, "rule_sha256", None),
        "schema_sha256": sha256_bytes(schema_raw),
        "source_identity": source_identity,
    }


def _terminal_role(*, mode: str, score: object) -> tuple[str, str]:
    status = getattr(score, "status", None)
    if mode == "diagnostic_only":
        return "diagnostic_only", "diagnostic_only"
    if mode != "formal":
        raise AttemptError("ATTEMPT_MODE_INVALID")
    if status == "completed":
        return "formal", "completed"
    if status == "completed_with_warnings":
        return "completed_with_warnings", "completed_with_warnings"
    return "invalid_preflight", "invalid_preflight"


def _manifest(*, attempt_id: str, role: str, status: str, raw_predictions: bytes, bindings: dict[str, object], artifacts: dict[str, dict[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifacts": artifacts,
        "attempt_id": attempt_id,
        "bindings": bindings,
        "raw_predictions_base64": base64.b64encode(raw_predictions).decode("ascii"),
        "raw_predictions_sha256": sha256_bytes(raw_predictions),
        "role": role,
        "schema_version": "measurement-attempt-v1",
        "status": status,
    }
    payload["attempt_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def run_measurement_attempt(*, mode: str, attempt_id: str, attempt_root: Path, inputs: object) -> dict[str, object]:
    """Stage, self-validate, and publish exactly one closed terminal attempt."""
    values = _as_dict(inputs, "ATTEMPT_INPUTS_INVALID")
    if "runtime_closure" in values or "authority_path" in values:
        closure = values.get("runtime_closure")
        authority = values.get("authority_path")
        if not isinstance(authority, Path):
            raise AttemptError("RUNTIME_CLOSURE_V4_REQUIRED")
        require_v4_downstream_gate(runtime_closure=closure, authority_path=authority)
    raw_predictions = values.get("raw_predictions")
    if not isinstance(raw_predictions, bytes):
        raise AttemptError("ATTEMPT_RAW_PREDICTIONS_INVALID")
    target = _attempt_target(attempt_root, attempt_id)
    score = values.get("score_result")
    role, status = _terminal_role(mode=mode, score=score)
    bindings = _bindings(values, raw_predictions)
    attempt_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{attempt_id}.staging-", dir=attempt_root))
    try:
        artifacts: dict[str, dict[str, object]] = {}
        for name, payload in _artifact_payloads(inputs=values, role=role, status=status).items():
            content = canonical_json_bytes(payload)
            _write_exact(temporary / name, content)
            artifacts[name] = {"sha256": sha256_bytes(content), "byte_length": len(content)}
        manifest = _manifest(
            attempt_id=attempt_id, role=role, status=status, raw_predictions=raw_predictions,
            bindings=bindings, artifacts=artifacts,
        )
        _write_exact(temporary / "attempt.json", canonical_json_bytes(manifest))
        validate_measurement_attempt(
            attempt_root=temporary,
            adapter_batch=values.get("adapter_batch"),
            schema_raw=_schema_bytes(values),
        )
        _sync_directory(temporary)
        _sync_directory(attempt_root)
        try:
            _publish_directory_no_replace(temporary, target, "ATTEMPT_TARGET_EXISTS")
        except BundleError as error:
            raise AttemptError(str(error)) from error
        _sync_directory(attempt_root)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {"attempt_sha256": manifest["attempt_sha256"], "role": role, "status": status}


def _read_attempt_file(*, attempt_root: Path, name: str, code: str) -> bytes:
    """Read one report-owned attempt leaf from its checked no-follow descriptor."""
    try:
        evidence, content = read_authoritative_file(attempt_root, name)
        if evidence.file_kind != "regular_file":
            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
        return content
    except (OSError, FilesystemPolicyError) as error:
        raise AttemptError(code) from error


def load_measurement_attempt_manifest(*, attempt_root: Path) -> dict[str, object]:
    """Load a canonical attempt manifest only from its report-owned directory."""
    try:
        raw = _read_attempt_file(
            attempt_root=attempt_root, name="attempt.json", code="ATTEMPT_MANIFEST_INVALID"
        )
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttemptError("ATTEMPT_MANIFEST_INVALID") from error
    if not isinstance(manifest, dict) or canonical_json_bytes(manifest) != raw or set(manifest) != _ATTEMPT_KEYS:
        raise AttemptError("ATTEMPT_MANIFEST_INVALID")
    return manifest


def _verify_replay(
    *,
    manifest: dict[str, object],
    artifact_bytes: Mapping[str, bytes],
    raw: bytes,
    adapter_batch: object | None = None,
    schema_raw: bytes | None = None,
) -> None:
    """Derive every terminal artifact from the bound raw input and current custody roots."""
    batch = adapter_batch or build_pr2164_adapter_batch(
        authority_path=_AUTHORITY, bundle_root=_BUNDLE, rules_path=_RULES
    )
    if not batch.valid:
        raise AttemptError("ATTEMPT_REPLAY_ADAPTER_INVALID")
    bindings = manifest["bindings"]
    assert isinstance(bindings, dict)
    ingress = bindings.get("ingress")
    if not isinstance(ingress, str):
        raise AttemptError("ATTEMPT_BINDINGS_INVALID")
    expected_bindings = _bindings(
        {
            "adapter_batch": batch,
            "schema_path": _SCHEMA,
            "schema_raw": schema_raw,
            "ingress": ingress,
        },
        raw,
    )
    if bindings != expected_bindings:
        raise AttemptError("ATTEMPT_BINDINGS_INVALID")
    preflight = preflight_prediction_batch(raw=raw, adapter_batch=batch, ingress=ingress)
    score = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")
    mode = "diagnostic_only" if manifest["role"] == "diagnostic_only" else "formal"
    role, status = _terminal_role(mode=mode, score=score)
    if (role, status) != (manifest["role"], manifest["status"]):
        raise AttemptError("ATTEMPT_REPLAY_TERMINAL_MISMATCH")
    expected_payloads = _artifact_payloads(
        inputs={"preflight": preflight, "score_result": score}, role=role, status=status
    )
    for name, payload in expected_payloads.items():
        if artifact_bytes[name] != canonical_json_bytes(payload):
            raise AttemptError("ATTEMPT_REPLAY_ARTIFACT_MISMATCH")


def validate_measurement_attempt(
    *,
    attempt_root: Path,
    adapter_batch: object | None = None,
    schema_raw: bytes | None = None,
) -> dict[str, object]:
    """Validate raw-byte recovery, non-cyclic manifest digest, and every sibling binding."""
    manifest = load_measurement_attempt_manifest(attempt_root=attempt_root)
    role, status = manifest.get("role"), manifest.get("status")
    if role not in _VALID_ROLES or not isinstance(status, str):
        raise AttemptError("ATTEMPT_ROLE_INVALID")
    if (role == "formal") != (status == "completed") or (role == "completed_with_warnings") != (status == "completed_with_warnings"):
        raise AttemptError("ATTEMPT_ROLE_STATUS_INVALID")
    try:
        raw = base64.b64decode(manifest["raw_predictions_base64"], validate=True)
    except (KeyError, TypeError, ValueError) as error:
        raise AttemptError("ATTEMPT_RAW_PREDICTIONS_INVALID") from error
    if manifest.get("raw_predictions_sha256") != sha256_bytes(raw):
        raise AttemptError("ATTEMPT_RAW_PREDICTIONS_HASH_MISMATCH")
    projection = {key: value for key, value in manifest.items() if key != "attempt_sha256"}
    if manifest.get("attempt_sha256") != sha256_bytes(canonical_json_bytes(projection)):
        raise AttemptError("ATTEMPT_DIGEST_MISMATCH")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict) or bindings.get("raw_predictions_sha256") != manifest["raw_predictions_sha256"]:
        raise AttemptError("ATTEMPT_BINDINGS_INVALID")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise AttemptError("ATTEMPT_ARTIFACTS_INVALID")
    expected = set(_BASE_ARTIFACTS)
    if role in {"formal", "completed_with_warnings"}:
        expected.update(_SCORE_ARTIFACTS)
    if set(artifacts) != expected:
        raise AttemptError("ATTEMPT_ARTIFACT_SET_INVALID")
    artifact_bytes: dict[str, bytes] = {}
    for name, identity in artifacts.items():
        if not isinstance(identity, dict) or set(identity) != {"sha256", "byte_length"}:
            raise AttemptError("ATTEMPT_ARTIFACTS_INVALID")
        try:
            content = _read_attempt_file(
                attempt_root=attempt_root, name=name, code="ATTEMPT_ARTIFACT_INVALID"
            )
            parsed = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AttemptError("ATTEMPT_ARTIFACT_INVALID") from error
        if canonical_json_bytes(parsed) != content or identity.get("sha256") != sha256_bytes(content) or identity.get("byte_length") != len(content):
            raise AttemptError("ATTEMPT_ARTIFACT_HASH_MISMATCH")
        artifact_bytes[name] = content
    _verify_replay(
        manifest=manifest,
        artifact_bytes=artifact_bytes,
        raw=raw,
        adapter_batch=adapter_batch,
        schema_raw=schema_raw,
    )
    return {"attempt_sha256": manifest["attempt_sha256"], "role": role, "status": status}


_SUCCESSOR_PARTITION_V6 = {"candidate": 2, "negative": 3, "positive": 6}
_SUCCESSOR_METRICS_V5 = {
    "disposition": {"denominator": 8, "numerator": 8},
    "evidence_integrity": {"denominator": 10, "numerator": 10},
    "identity": {"denominator": 6, "numerator": 6},
    "negative_controls": {"denominator": 3, "numerator": 3},
    "surfacing": {"denominator": 8, "numerator": 8},
}


def _successor_adapter_v6(
    *,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    golden_predictions: Path,
    bundle_root: Path,
    adapter_batch: Path | None = None,
) -> tuple[object, bytes, dict[str, object], bytes]:
    """Rebuild the successor adapter and optionally match its exact published bytes."""
    golden, golden_raw = _canonical_file(
        golden_predictions, "SUCCESSOR_GOLDEN_INVALID"
    )
    batch = build_pr2164_v6_adapter_batch(
        registry_path=fixture_registry,
        rules_path=rules,
        contract_path=semantic_contract,
        golden_path=golden_predictions,
        bundle_root=bundle_root,
    )
    records = tuple(getattr(batch, "records", ()))
    partition = {
        category: sum(getattr(record, "category", None) == category for record in records)
        for category in _SUCCESSOR_PARTITION_V6
    }
    raw_count = sum(len(tuple(getattr(record, "raw_files", ()))) for record in records)
    source_identity = getattr(batch, "source_identity", None)
    if (
        getattr(batch, "valid", False) is not True
        or tuple(getattr(batch, "diagnostics", ()))
        or len(records) != 11
        or partition != _SUCCESSOR_PARTITION_V6
        or raw_count != 29
        or getattr(batch, "score_bearing_span_count", None) != 10
        or not isinstance(source_identity, dict)
        or source_identity.get("golden_predictions_sha256") != sha256_bytes(golden_raw)
    ):
        raise AttemptError("SUCCESSOR_ADAPTER_INVALID")
    canonical = canonical_json_bytes(getattr(batch, "as_dict")())
    if adapter_batch is not None:
        _, published = _canonical_file(
            adapter_batch, "SUCCESSOR_ADAPTER_ARTIFACT_INVALID"
        )
        if published != canonical:
            raise AttemptError("SUCCESSOR_ADAPTER_ARTIFACT_INVALID")
    return batch, canonical, golden, golden_raw


def write_successor_adapter_batch_v6(
    *,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    golden_predictions: Path,
    bundle_root: Path,
    output: Path,
    preflight: bool = False,
) -> dict[str, object]:
    batch, canonical, _, _ = _successor_adapter_v6(
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        bundle_root=bundle_root,
    )
    if (
        output.exists()
        or output.is_symlink()
        or not output.parent.is_dir()
        or output.parent.is_symlink()
    ):
        raise AttemptError("SUCCESSOR_ADAPTER_OUTPUT_EXISTS")
    if not preflight:
        try:
            _write_exact(output, canonical)
            _sync_directory(output.parent)
        except (FileExistsError, OSError) as error:
            raise AttemptError("SUCCESSOR_ADAPTER_OUTPUT_EXISTS") from error
    return {
        "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256"),
        "fixture_count": 11,
        "raw_file_count": 29,
        "status": "preflight_valid" if preflight else "written",
    }


def validate_successor_adapter_batch_v6(
    *,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    golden_predictions: Path,
    bundle_root: Path,
) -> dict[str, object]:
    batch, canonical, _, _ = _successor_adapter_v6(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        bundle_root=bundle_root,
    )
    return {
        "adapter_batch_file_sha256": sha256_bytes(canonical),
        "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256"),
        "fixture_count": 11,
        "partition": dict(_SUCCESSOR_PARTITION_V6),
        "raw_file_count": 29,
        "score_bearing_span_count": 10,
        "valid": True,
    }


def _successor_prediction_bytes_v5(
    *, golden: Mapping[str, object], adapter_batch: object
) -> bytes:
    outcomes = golden.get("outcomes")
    if (
        golden.get("schema_version") != "golden-predictions-v4"
        or not isinstance(outcomes, list)
        or len(outcomes) != 11
    ):
        raise AttemptError("SUCCESSOR_GOLDEN_INVALID")
    predictions: list[dict[str, object]] = []
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise AttemptError("SUCCESSOR_GOLDEN_INVALID")
        observed = outcome.get("observed")
        spans = outcome.get("evidence_spans")
        if (
            not isinstance(observed, dict)
            or not isinstance(spans, list)
            or not isinstance(outcome.get("fixture_id"), str)
            or not isinstance(outcome.get("rationale"), str)
        ):
            raise AttemptError("SUCCESSOR_GOLDEN_INVALID")
        fixture_id = str(outcome["fixture_id"])
        predictions.append(
            {
                "adjudication": {
                    "evidence_spans": deepcopy(spans),
                    "parameter_status": observed.get("status"),
                    "proposed_name": observed.get("name"),
                    "surfaced": observed.get("surfaced"),
                },
                "finding_id": f"{fixture_id}:1",
                "fixture_id": fixture_id,
                "rationale": outcome["rationale"],
            }
        )
    return canonical_json_bytes(
        {
            "adapter_batch_sha256": getattr(adapter_batch, "adapter_batch_sha256", None),
            "predictions": predictions,
            "schema_version": "canonical-adjudication-v3",
        }
    )


def _successor_formal_score_v5(
    *, batch: object, golden: Mapping[str, object]
) -> tuple[bytes, object, object]:
    raw_predictions = _successor_prediction_bytes_v5(
        golden=golden, adapter_batch=batch
    )
    preflight = preflight_prediction_batch(
        raw=raw_predictions, adapter_batch=batch, ingress="current-v3"
    )
    score = score_prediction_batch(
        adapter_batch=batch, preflight=preflight, mode="formal"
    )
    metrics = getattr(score, "metrics", None)
    if (
        getattr(preflight, "status", None) != "valid_preflight"
        or len(tuple(getattr(preflight, "parsed_predictions", ()))) != 11
        or getattr(score, "status", None) != "completed"
        or len(tuple(getattr(score, "case_outcomes", ()))) != 11
        or tuple(getattr(score, "diagnostics", ()))
        or metrics is None
        or getattr(metrics, "as_dict")() != _SUCCESSOR_METRICS_V5
    ):
        raise AttemptError("SUCCESSOR_FORMAL_SCORE_INVALID")
    return raw_predictions, preflight, score


def _read_successor_formal_artifacts_v5(attempt: Path) -> tuple[dict[str, object], list[object], dict[str, object]]:
    manifest = load_measurement_attempt_manifest(attempt_root=attempt)
    try:
        case_raw = _read_attempt_file(
            attempt_root=attempt,
            name="case-outcomes.json",
            code="SUCCESSOR_FORMAL_ARTIFACT_INVALID",
        )
        metrics_raw = _read_attempt_file(
            attempt_root=attempt,
            name="metrics.json",
            code="SUCCESSOR_FORMAL_ARTIFACT_INVALID",
        )
        cases = json.loads(case_raw.decode("utf-8"))
        metrics = json.loads(metrics_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttemptError("SUCCESSOR_FORMAL_ARTIFACT_INVALID") from error
    if (
        not isinstance(cases, list)
        or len(cases) != 11
        or not isinstance(metrics, dict)
        or metrics != _SUCCESSOR_METRICS_V5
        or canonical_json_bytes(cases) != case_raw
        or canonical_json_bytes(metrics) != metrics_raw
    ):
        raise AttemptError("SUCCESSOR_FORMAL_ARTIFACT_INVALID")
    return manifest, cases, metrics


def run_formal_measurement_v5(
    *,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    golden_predictions: Path,
    adjudication_schema: Path,
    bundle_root: Path,
    attempt_root: Path,
    attempt_id: str,
    preflight: bool = False,
) -> dict[str, object]:
    batch, _, golden, _ = _successor_adapter_v6(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        bundle_root=bundle_root,
    )
    _, schema_raw = _canonical_file(
        adjudication_schema, "SUCCESSOR_ADJUDICATION_SCHEMA_INVALID"
    )
    source_identity = getattr(batch, "source_identity", {})
    if source_identity.get("adjudication_schema_sha256") != sha256_bytes(schema_raw):
        raise AttemptError("SUCCESSOR_ADJUDICATION_SCHEMA_INVALID")
    raw_predictions, parsed, score = _successor_formal_score_v5(
        batch=batch, golden=golden
    )
    target = _attempt_target(attempt_root, attempt_id)
    if preflight:
        return {
            "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256"),
            "case_count": 11,
            "metrics": dict(_SUCCESSOR_METRICS_V5),
            "status": "preflight_valid",
        }
    result = run_measurement_attempt(
        mode="formal",
        attempt_id=attempt_id,
        attempt_root=attempt_root,
        inputs={
            "adapter_batch": batch,
            "ingress": "current-v3",
            "preflight": parsed,
            "raw_predictions": raw_predictions,
            "score_result": score,
            "schema_raw": schema_raw,
        },
    )
    validated = validate_formal_measurement_v5(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        adjudication_schema=adjudication_schema,
        bundle_root=bundle_root,
        attempt=target,
    )
    if result.get("attempt_sha256") != validated.get("attempt_sha256"):
        raise AttemptError("SUCCESSOR_FORMAL_VALIDATION_MISMATCH")
    return validated


def validate_formal_measurement_v5(
    *,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    golden_predictions: Path,
    adjudication_schema: Path,
    bundle_root: Path,
    attempt: Path,
) -> dict[str, object]:
    batch, _, golden, _ = _successor_adapter_v6(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        bundle_root=bundle_root,
    )
    _, schema_raw = _canonical_file(
        adjudication_schema, "SUCCESSOR_ADJUDICATION_SCHEMA_INVALID"
    )
    source_identity = getattr(batch, "source_identity", {})
    if source_identity.get("adjudication_schema_sha256") != sha256_bytes(schema_raw):
        raise AttemptError("SUCCESSOR_ADJUDICATION_SCHEMA_INVALID")
    expected_raw, _, _ = _successor_formal_score_v5(batch=batch, golden=golden)
    validated = validate_measurement_attempt(
        attempt_root=attempt, adapter_batch=batch, schema_raw=schema_raw
    )
    manifest, cases, metrics = _read_successor_formal_artifacts_v5(attempt)
    try:
        retained_raw = base64.b64decode(
            manifest["raw_predictions_base64"], validate=True
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AttemptError("SUCCESSOR_FORMAL_LINEAGE_INVALID") from error
    category_counts = {
        category: sum(
            isinstance(case, dict) and case.get("category") == category for case in cases
        )
        for category in _SUCCESSOR_PARTITION_V6
    }
    if (
        validated.get("role") != "formal"
        or validated.get("status") != "completed"
        or manifest.get("schema_version") != "measurement-attempt-v1"
        or manifest.get("raw_predictions_sha256") != sha256_bytes(expected_raw)
        or retained_raw != expected_raw
        or category_counts != _SUCCESSOR_PARTITION_V6
    ):
        raise AttemptError("SUCCESSOR_FORMAL_LINEAGE_INVALID")
    return {
        "attempt_sha256": validated["attempt_sha256"],
        "case_count": len(cases),
        "metrics": metrics,
        "role": "formal",
        "status": "completed",
    }


_V4_ADVERSARIAL_CASE_IDS = (
    "unknown-top-level-field",
    "missing-outcome",
    "duplicate-outcome",
    "candidate-not-surfaced",
    "candidate-accepted",
    "candidate-review-status",
    "candidate-evidence-empty",
    "positive-not-surfaced",
    "positive-classified-out",
    "accepted-name-missing",
    "evidence-source-changed",
    "evidence-empty-range",
    "evidence-text-mismatch",
    "negative-null-evidence",
    "negative-surfaced",
    "unknown-outcome-field",
    "complete-multi-diagnostic-order",
)
_V4_MUTATION_OPERATIONS = frozenset(
    {
        "add_outcome_field",
        "add_top_level",
        "delete_outcome",
        "duplicate_outcome",
        "remove",
        "set",
    }
)


def _canonical_file(path: Path, code: str) -> tuple[dict[str, object], bytes]:
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        value = json.loads(raw.decode("utf-8"))
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttemptError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise AttemptError(code)
    return value, raw


def _successor_diagnostic_sort_key(value: Mapping[str, object]) -> tuple[object, ...]:
    severity = {"blocker": 0, "warning": 1}.get(value.get("severity"), 2)
    return (
        severity,
        str(value.get("code", "")),
        str(value.get("fixture_id") or ""),
        str(value.get("field", "")),
        str(value.get("finding_id") or ""),
        value.get("occurrence") if isinstance(value.get("occurrence"), int) else -1,
        str(value.get("source_sha256") or ""),
        canonical_json_bytes(value.get("expected")).decode("utf-8"),
        canonical_json_bytes(value.get("observed")).decode("utf-8"),
    )


def _successor_diagnostic(
    code: str,
    severity: str,
    *,
    fixture_id: str | None = None,
    field: str,
    occurrence: int = 0,
    expected: object = None,
    observed: object = None,
    source_sha256: str | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "expected": expected,
        "field": field,
        "finding_id": None if fixture_id is None else f"{fixture_id}:1",
        "fixture_id": fixture_id,
        "observed": observed,
        "occurrence": occurrence,
        "severity": severity,
        "source_sha256": source_sha256,
    }


def validate_required_diagnostics_v4(
    *, contract: Path, golden_predictions: Path
) -> dict[str, object]:
    """Require a closed, typed 17-case mutation contract bound to golden-v4 bytes."""
    value, raw = _canonical_file(contract, "ADVERSARIAL_V4_CONTRACT_INVALID")
    golden, golden_raw = _canonical_file(
        golden_predictions, "ADVERSARIAL_V4_GOLDEN_INVALID"
    )
    if golden.get("schema_version") != "golden-predictions-v4":
        raise AttemptError("ADVERSARIAL_V4_GOLDEN_INVALID")
    if set(value) != {
        "base_input",
        "cases",
        "diagnostic_order",
        "schema_version",
    } or value.get("schema_version") != "required-diagnostics-v4":
        raise AttemptError("ADVERSARIAL_V4_CONTRACT_INVALID")
    if value.get("base_input") != {
        "path": "fixtures/measurement/golden-predictions-v4.json",
        "sha256": sha256_bytes(golden_raw),
    }:
        raise AttemptError("ADVERSARIAL_V4_CONTRACT_BINDING_INVALID")
    if value.get("diagnostic_order") != {
        "deduplication": "never",
        "equal_element_tie_break": "input_ordinal",
        "fields": [
            "severity",
            "code",
            "fixture_id",
            "field",
            "finding_id",
            "occurrence",
            "source_sha256",
            "expected",
            "observed",
            "input_ordinal",
        ],
    }:
        raise AttemptError("ADVERSARIAL_V4_CONTRACT_INVALID")
    cases = value.get("cases")
    if (
        not isinstance(cases, list)
        or [case.get("id") for case in cases if isinstance(case, dict)]
        != list(_V4_ADVERSARIAL_CASE_IDS)
    ):
        raise AttemptError("ADVERSARIAL_V4_CONTRACT_INVALID")
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "expected_diagnostics",
            "formal_effect",
            "fixture_id",
            "id",
            "metric_output_allowed",
            "mutations",
            "rationale",
        }:
            raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        if (
            not isinstance(case.get("fixture_id"), str)
            or not isinstance(case.get("rationale"), str)
            or not case["rationale"].strip()
            or case.get("metric_output_allowed") is not False
            or case.get("formal_effect")
            not in {"invalid_preflight", "invalid_score", "completed_with_warnings"}
        ):
            raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        mutations = case.get("mutations")
        if not isinstance(mutations, list) or not mutations:
            raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        for mutation in mutations:
            if (
                not isinstance(mutation, dict)
                or set(mutation) != {"field", "fixture_id", "operation", "value"}
                or mutation.get("operation") not in _V4_MUTATION_OPERATIONS
                or not isinstance(mutation.get("field"), str)
                or not isinstance(mutation.get("fixture_id"), str)
            ):
                raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        diagnostics = case.get("expected_diagnostics")
        if not isinstance(diagnostics, list) or not diagnostics:
            raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict) or set(diagnostic) != {
                "code",
                "expected",
                "field",
                "finding_id",
                "fixture_id",
                "observed",
                "occurrence",
                "severity",
                "source_sha256",
            } or diagnostic.get("severity") not in {"blocker", "warning"}:
                raise AttemptError("ADVERSARIAL_V4_CASE_INVALID")
        if diagnostics != sorted(diagnostics, key=_successor_diagnostic_sort_key):
            raise AttemptError("ADVERSARIAL_V4_DIAGNOSTIC_ORDER_INVALID")
    return {
        "case_count": len(cases),
        "contract_sha256": sha256_bytes(raw),
        "golden_predictions_sha256": sha256_bytes(golden_raw),
        "valid": True,
    }


def _outcome_by_id(payload: dict[str, object], fixture_id: str) -> dict[str, object]:
    outcomes = payload.get("outcomes")
    if not isinstance(outcomes, list):
        raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
    for outcome in outcomes:
        if isinstance(outcome, dict) and outcome.get("fixture_id") == fixture_id:
            return outcome
    raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")


def _nested_parent(value: object, field: str) -> tuple[object, str]:
    tokens = field.split(".")
    if not tokens or any(not token for token in tokens):
        raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
    current = value
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            try:
                current = current[int(token)]
            except IndexError as error:
                raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID") from error
        else:
            raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
    return current, tokens[-1]


def _apply_successor_mutations(
    base: dict[str, object], mutations: list[dict[str, object]]
) -> dict[str, object]:
    value = deepcopy(base)
    for mutation in mutations:
        operation = mutation["operation"]
        fixture_id = str(mutation["fixture_id"])
        field = str(mutation["field"])
        replacement = deepcopy(mutation.get("value"))
        if operation == "add_top_level":
            value[field] = replacement
            continue
        outcomes = value.get("outcomes")
        if not isinstance(outcomes, list):
            raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
        if operation in {"delete_outcome", "duplicate_outcome"}:
            positions = [
                index
                for index, outcome in enumerate(outcomes)
                if isinstance(outcome, dict) and outcome.get("fixture_id") == fixture_id
            ]
            if len(positions) != 1:
                raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
            if operation == "delete_outcome":
                del outcomes[positions[0]]
            else:
                outcomes.insert(positions[0] + 1, deepcopy(outcomes[positions[0]]))
            continue
        outcome = _outcome_by_id(value, fixture_id)
        if operation == "add_outcome_field":
            outcome[field] = replacement
            continue
        parent, leaf = _nested_parent(outcome, field)
        if isinstance(parent, dict):
            if operation == "remove":
                if leaf not in parent:
                    raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
                del parent[leaf]
            elif operation == "set":
                if leaf not in parent:
                    raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
                parent[leaf] = replacement
            else:
                raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
        elif isinstance(parent, list) and leaf.isdigit():
            index = int(leaf)
            try:
                if operation == "remove":
                    del parent[index]
                elif operation == "set":
                    parent[index] = replacement
                else:
                    raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
            except IndexError as error:
                raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID") from error
        else:
            raise AttemptError("ADVERSARIAL_V4_MUTATION_INVALID")
    return value


def _evaluate_successor_payload(
    value: dict[str, object], base: dict[str, object]
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    extra_top = sorted(set(value) - set(base))
    for field in extra_top:
        diagnostics.append(
            _successor_diagnostic(
                "UNKNOWN_FIELD",
                "blocker",
                field=f"payload.{field}",
                expected=None,
                observed=field,
            )
        )
    outcomes = value.get("outcomes")
    base_outcomes = base.get("outcomes")
    if not isinstance(outcomes, list) or not isinstance(base_outcomes, list):
        diagnostics.append(
            _successor_diagnostic(
                "FORMAL_COVERAGE_MISMATCH",
                "blocker",
                field="outcomes",
                expected=11,
                observed=None if not isinstance(outcomes, list) else len(outcomes),
            )
        )
        return sorted(diagnostics, key=_successor_diagnostic_sort_key)
    base_by_id = {
        item.get("fixture_id"): item for item in base_outcomes if isinstance(item, dict)
    }
    ids = [item.get("fixture_id") for item in outcomes if isinstance(item, dict)]
    for fixture_id in sorted(set(ids)):
        count = ids.count(fixture_id)
        if isinstance(fixture_id, str) and count > 1:
            diagnostics.append(
                _successor_diagnostic(
                    "PREDICTION_FIXTURE_DUPLICATE",
                    "blocker",
                    fixture_id=fixture_id,
                    field="outcomes",
                    expected=1,
                    observed=count,
                )
            )
    missing = sorted(set(base_by_id) - set(ids))
    if missing:
        diagnostics.append(
            _successor_diagnostic(
                "PREDICTION_FIXTURE_MISSING",
                "blocker",
                field="outcomes",
                expected=missing,
                observed=[],
            )
        )
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        fixture_id = outcome.get("fixture_id")
        baseline = base_by_id.get(fixture_id)
        if not isinstance(fixture_id, str) or not isinstance(baseline, dict):
            continue
        extras = sorted(set(outcome) - set(baseline))
        for field in extras:
            diagnostics.append(
                _successor_diagnostic(
                    "UNKNOWN_FIELD",
                    "blocker",
                    fixture_id=fixture_id,
                    field=f"outcomes.{field}",
                    expected=None,
                    observed=field,
                )
            )
        expected = outcome.get("expected")
        observed = outcome.get("observed")
        base_observed = baseline.get("observed")
        fixture_class = outcome.get("fixture_class")
        if not isinstance(expected, dict) or not isinstance(observed, dict) or not isinstance(base_observed, dict):
            continue
        actual_surfaced = observed.get("surfaced")
        expected_surfaced = expected.get("surface")
        status = observed.get("status")
        expected_status = expected.get("disposition")
        if actual_surfaced != expected_surfaced:
            code = (
                "CANDIDATE_NOT_SURFACED"
                if fixture_class == "candidate" and actual_surfaced is False
                else "MISSING_EXPECTED_PARAMETER"
                if fixture_class == "positive" and actual_surfaced is False
                else "NEGATIVE_UNNECESSARILY_SURFACED"
            )
            diagnostics.append(
                _successor_diagnostic(
                    code,
                    "blocker",
                    fixture_id=fixture_id,
                    field="observed.surfaced",
                    expected=expected_surfaced,
                    observed=actual_surfaced,
                )
            )
        if status not in {"accept", "classify_out", None}:
            diagnostics.append(
                _successor_diagnostic(
                    "PARAMETER_STATUS_INVALID",
                    "blocker",
                    fixture_id=fixture_id,
                    field="observed.status",
                    expected=expected_status,
                    observed=status,
                )
            )
        elif fixture_class == "candidate" and status == "accept":
            diagnostics.append(
                _successor_diagnostic(
                    "CANDIDATE_ACCEPTED_AS_PARAMETER",
                    "blocker",
                    fixture_id=fixture_id,
                    field="observed.status",
                    expected="classify_out",
                    observed="accept",
                )
            )
        elif fixture_class == "positive" and status == "classify_out":
            diagnostics.append(
                _successor_diagnostic(
                    "POSITIVE_CLASSIFIED_OUT",
                    "blocker",
                    fixture_id=fixture_id,
                    field="observed.status",
                    expected="accept",
                    observed="classify_out",
                )
            )
        if (
            fixture_class == "positive"
            and actual_surfaced is True
            and status == "accept"
            and observed.get("name") is None
        ):
            names = expected.get("names")
            diagnostics.append(
                _successor_diagnostic(
                    "ACCEPTED_PARAMETER_NAME_MISSING",
                    "warning",
                    fixture_id=fixture_id,
                    field="observed.name",
                    expected=names[0] if isinstance(names, list) and names else None,
                    observed=None,
                )
            )
        spans = outcome.get("evidence_spans")
        base_spans = baseline.get("evidence_spans")
        if actual_surfaced is False and spans is None:
            diagnostics.append(
                _successor_diagnostic(
                    "NO_FINDING_NONCANONICAL",
                    "blocker",
                    fixture_id=fixture_id,
                    field="evidence_spans",
                    expected=[],
                    observed=None,
                )
            )
        elif actual_surfaced is True and spans == []:
            diagnostics.append(
                _successor_diagnostic(
                    "EVIDENCE_SPAN_EMPTY",
                    "blocker",
                    fixture_id=fixture_id,
                    field="evidence_spans",
                    expected="non-empty array",
                    observed=[],
                )
            )
        elif isinstance(spans, list) and isinstance(base_spans, list):
            known_sources = {
                item.get("source_sha256")
                for item in base_spans
                if isinstance(item, dict)
            }
            for occurrence, span in enumerate(spans, start=1):
                if not isinstance(span, dict):
                    continue
                source_sha = span.get("source_sha256")
                start, end, text = span.get("start_byte"), span.get("end_byte"), span.get("text")
                if source_sha not in known_sources:
                    diagnostics.append(
                        _successor_diagnostic(
                            "EVIDENCE_SOURCE_UNKNOWN",
                            "blocker",
                            fixture_id=fixture_id,
                            field="evidence_spans",
                            occurrence=occurrence,
                            expected=sorted(item for item in known_sources if isinstance(item, str)),
                            observed=source_sha,
                            source_sha256=source_sha if isinstance(source_sha, str) else None,
                        )
                    )
                    continue
                if (
                    isinstance(start, bool)
                    or not isinstance(start, int)
                    or isinstance(end, bool)
                    or not isinstance(end, int)
                    or end <= start
                ):
                    diagnostics.append(
                        _successor_diagnostic(
                            "EVIDENCE_RANGE_EMPTY",
                            "blocker",
                            fixture_id=fixture_id,
                            field="evidence_spans",
                            occurrence=occurrence,
                            expected="start_byte < end_byte",
                            observed=[start, end],
                            source_sha256=source_sha if isinstance(source_sha, str) else None,
                        )
                    )
                    continue
                matching = [
                    item
                    for item in base_spans
                    if isinstance(item, dict)
                    and item.get("source_sha256") == source_sha
                    and item.get("start_byte") == start
                    and item.get("end_byte") == end
                ]
                if matching and all(item.get("text") != text for item in matching):
                    diagnostics.append(
                        _successor_diagnostic(
                            "EVIDENCE_TEXT_MISMATCH",
                            "blocker",
                            fixture_id=fixture_id,
                            field="evidence_spans",
                            occurrence=occurrence,
                            expected=matching[0].get("text"),
                            observed=text,
                            source_sha256=source_sha if isinstance(source_sha, str) else None,
                        )
                    )
    return sorted(diagnostics, key=_successor_diagnostic_sort_key)


def _build_adversarial_result_v6(
    *,
    contract: Path,
    golden_predictions: Path,
    formal_attempt: Path,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    bundle_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    contract_result = validate_required_diagnostics_v4(
        contract=contract, golden_predictions=golden_predictions
    )
    contract_value, contract_raw = _canonical_file(
        contract, "ADVERSARIAL_V4_CONTRACT_INVALID"
    )
    batch, adapter_raw, golden, golden_raw = _successor_adapter_v6(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        bundle_root=bundle_root,
    )
    formal = validate_formal_measurement_v5(
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        golden_predictions=golden_predictions,
        adjudication_schema=schema,
        bundle_root=bundle_root,
        attempt=formal_attempt,
    )
    adapter_identity = getattr(batch, "adapter_batch_sha256")
    _, rules_raw = _canonical_file(rules, "ADVERSARIAL_V6_RULES_INVALID")
    _, schema_raw = _canonical_file(schema, "ADVERSARIAL_V6_SCHEMA_INVALID")
    cases: list[dict[str, object]] = []
    for case in contract_value["cases"]:
        assert isinstance(case, dict)
        mutations = case["mutations"]
        assert isinstance(mutations, list)
        mutated = _apply_successor_mutations(golden, mutations)
        observed = _evaluate_successor_payload(mutated, golden)
        if observed != case["expected_diagnostics"]:
            raise AttemptError(f"ADVERSARIAL_V6_MISMATCH:{case['id']}")
        cases.append(
            {
                "expected_diagnostics": case["expected_diagnostics"],
                "formal_effect": case["formal_effect"],
                "id": case["id"],
                "matched": True,
                "metric_output_allowed": False,
                "mutated_input_sha256": sha256_bytes(canonical_json_bytes(mutated)),
                "observed_diagnostics": observed,
            }
        )
    report: dict[str, object] = {
        "bindings": {
            "adapter_batch_file_sha256": sha256_bytes(adapter_raw),
            "adapter_batch_sha256": adapter_identity,
            "formal_attempt_sha256": formal["attempt_sha256"],
            "golden_predictions_sha256": sha256_bytes(golden_raw),
            "required_diagnostics_sha256": sha256_bytes(contract_raw),
            "rule_sha256": sha256_bytes(rules_raw),
            "schema_sha256": sha256_bytes(schema_raw),
        },
        "cases": cases,
        "schema_version": "adversarial-oracle-results-v6",
        "status": "diagnostic_only",
    }
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report, contract_result


def run_adversarial_suite_v6(
    *,
    contract: Path,
    golden_predictions: Path,
    formal_attempt: Path,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    bundle_root: Path,
    output: Path,
    preflight: bool = False,
) -> dict[str, object]:
    """Execute every typed mutation and emit no formal metrics for diagnostic subsets."""
    report, contract_result = _build_adversarial_result_v6(
        contract=contract,
        golden_predictions=golden_predictions,
        formal_attempt=formal_attempt,
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        schema=schema,
        bundle_root=bundle_root,
    )
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise AttemptError("ADVERSARIAL_V6_OUTPUT_EXISTS")
    if not preflight:
        try:
            _write_exact(output, canonical_json_bytes(report))
            _sync_directory(output.parent)
        except (FileExistsError, OSError) as error:
            raise AttemptError("ADVERSARIAL_V6_OUTPUT_EXISTS") from error
    return {
        "case_count": contract_result["case_count"],
        "report_sha256": report["report_sha256"],
        "status": "preflight_valid" if preflight else "diagnostic_only",
    }


def validate_adversarial_result_v6(
    *,
    report: Path,
    contract: Path,
    golden_predictions: Path,
    formal_attempt: Path,
    adapter_batch: Path,
    fixture_registry: Path,
    rules: Path,
    semantic_contract: Path,
    schema: Path,
    bundle_root: Path,
) -> dict[str, object]:
    """Replay the full mutation contract and compare a pre-existing canonical report."""
    expected, _ = _build_adversarial_result_v6(
        contract=contract,
        golden_predictions=golden_predictions,
        formal_attempt=formal_attempt,
        adapter_batch=adapter_batch,
        fixture_registry=fixture_registry,
        rules=rules,
        semantic_contract=semantic_contract,
        schema=schema,
        bundle_root=bundle_root,
    )
    value, raw = _canonical_file(report, "ADVERSARIAL_V6_REPORT_INVALID")
    if raw != canonical_json_bytes(expected):
        raise AttemptError("ADVERSARIAL_V6_REPORT_INVALID")
    return {
        "case_count": len(value["cases"]),
        "report_sha256": value["report_sha256"],
        "status": value["status"],
        "valid": True,
    }


_FRESH_EXPERIMENT = Path("experiments/specchoice-v1.3.2")
_FRESH_ADAPTER = Path("reports/h1/adapter-batch-pr2164-v6.json")
_FRESH_FORMAL = Path("runs/measurement-attempts/formal-golden-pr2164-v6")
_FRESH_ADVERSARIAL = Path("reports/h1/adversarial-oracle-results-v7.json")
_FRESH_FORMAL_FILES = frozenset({
    "attempt.json", "case-outcomes.json", "diagnostics.json", "metrics.json",
    "parsed-predictions.json", "report.json",
})


def _fresh_paths(repository: Path) -> dict[str, Path]:
    experiment = repository / _FRESH_EXPERIMENT
    return {
        "adapter": experiment / _FRESH_ADAPTER,
        "adversarial": experiment / _FRESH_ADVERSARIAL,
        "authority": experiment / "phase2/source-authority.json",
        "bundle": experiment / (
            "bundles/accepted/"
            "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
        ),
        "contract": experiment / "fixtures/measurement/adversarial/required-diagnostics-v4.json",
        "formal": experiment / _FRESH_FORMAL,
        "golden": experiment / "fixtures/measurement/golden-predictions-v4.json",
        "registry": experiment / "config/fixture-registry-pr2164-v6.json",
        "rules": experiment / "config/measurement/pr2164-adapter-rules-v4.json",
        "schema": experiment / "config/measurement/canonical-adjudication-schema-v3.json",
        "semantic": experiment / "config/measurement/pr2164-semantic-gold-contract-v2.json",
    }


def _fresh_v6_context(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> tuple[object, dict[str, object], bytes]:
    """Rebuild the fresh adapter and require its fixed published artifact."""
    repository = repository.resolve(strict=True)
    paths = _fresh_paths(repository)
    require_v4_downstream_gate(
        runtime_closure=runtime_closure, authority_path=authority_path,
    )
    validate_pr2164_accepted_v6_adapter_batch_v4(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    batch = build_pr2164_accepted_v6_adapter_batch_v4(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
        bundle_root=paths["bundle"],
        rules_path=paths["rules"],
    )
    if not getattr(batch, "valid", False) or tuple(getattr(batch, "diagnostics", ())):
        raise AttemptError("FRESH_V6_ADAPTER_INVALID")
    _, adapter_raw = _canonical_file(paths["adapter"], "FRESH_V6_ADAPTER_INVALID")
    if adapter_raw != getattr(batch, "canonical_bytes")():
        raise AttemptError("FRESH_V6_ADAPTER_INVALID")
    golden, golden_raw = _canonical_file(paths["golden"], "FRESH_V6_GOLDEN_INVALID")
    source_identity = getattr(batch, "source_identity", None)
    if (
        not isinstance(source_identity, dict)
        or source_identity.get("golden_predictions_sha256") != sha256_bytes(golden_raw)
    ):
        raise AttemptError("FRESH_V6_GOLDEN_INVALID")
    return batch, golden, golden_raw


def _fresh_formal_expected_files(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> tuple[object, bytes, dict[str, bytes]]:
    batch, golden, _ = _fresh_v6_context(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    paths = _fresh_paths(repository)
    _, schema_raw = _canonical_file(paths["schema"], "FRESH_V6_SCHEMA_INVALID")
    source_identity = getattr(batch, "source_identity", None)
    if (
        not isinstance(source_identity, dict)
        or source_identity.get("adjudication_schema_sha256") != sha256_bytes(schema_raw)
    ):
        raise AttemptError("FRESH_V6_SCHEMA_INVALID")
    raw_predictions, parsed, score = _successor_formal_score_v5(
        batch=batch, golden=golden,
    )
    role, status = _terminal_role(mode="formal", score=score)
    if (role, status) != ("formal", "completed"):
        raise AttemptError("FRESH_V6_FORMAL_SCORE_INVALID")
    values: dict[str, object] = {
        "adapter_batch": batch,
        # canonical-adjudication-v3 remains the closed payload schema; v4 is
        # the custody/adapter generation, not a new JSON ingress dialect.
        "ingress": "current-v3",
        "preflight": parsed,
        "raw_predictions": raw_predictions,
        "score_result": score,
        "schema_raw": schema_raw,
    }
    artifacts: dict[str, dict[str, object]] = {}
    files: dict[str, bytes] = {}
    for name, payload in _artifact_payloads(
        inputs=values, role=role, status=status,
    ).items():
        content = canonical_json_bytes(payload)
        files[name] = content
        artifacts[name] = {"byte_length": len(content), "sha256": sha256_bytes(content)}
    manifest = _manifest(
        attempt_id="formal-golden-pr2164-v6",
        role=role,
        status=status,
        raw_predictions=raw_predictions,
        bindings=_bindings(values, raw_predictions),
        artifacts=artifacts,
    )
    files["attempt.json"] = canonical_json_bytes(manifest)
    if set(files) != _FRESH_FORMAL_FILES:
        raise AttemptError("FRESH_V6_FORMAL_ARTIFACT_SET_INVALID")
    return batch, schema_raw, files


def _read_exact_formal_directory(target: Path, expected: Mapping[str, bytes]) -> dict[str, bytes]:
    if target.is_symlink() or not target.is_dir():
        raise AttemptError("FRESH_V6_FORMAL_TARGET_KIND_INVALID")
    try:
        children = list(target.iterdir())
    except OSError as error:
        raise AttemptError("FRESH_V6_FORMAL_TARGET_INVALID") from error
    if {child.name for child in children} != set(expected) or len(children) != len(expected):
        raise AttemptError("FRESH_V6_FORMAL_TARGET_DIVERGED")
    retained: dict[str, bytes] = {}
    for name in sorted(expected):
        try:
            evidence, raw = read_authoritative_file(target, name)
        except (OSError, FilesystemPolicyError) as error:
            raise AttemptError("FRESH_V6_FORMAL_TARGET_INVALID") from error
        if evidence.file_kind != "regular_file" or raw != expected[name]:
            raise AttemptError("FRESH_V6_FORMAL_TARGET_DIVERGED")
        retained[name] = raw
    try:
        final_children = list(target.iterdir())
    except OSError as error:
        raise AttemptError("FRESH_V6_FORMAL_TARGET_INVALID") from error
    if (
        target.is_symlink()
        or not target.is_dir()
        or {child.name for child in final_children} != set(expected)
        or len(final_children) != len(expected)
    ):
        raise AttemptError("FRESH_V6_FORMAL_TARGET_DIVERGED")
    return retained


def validate_fresh_formal_measurement_v6(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Replay and byte-compare the fixed six-file formal-v6 directory."""
    repository = repository.resolve(strict=True)
    batch, schema_raw, expected = _fresh_formal_expected_files(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    target = _fresh_paths(repository)["formal"]
    _read_exact_formal_directory(target, expected)
    validated = validate_measurement_attempt(
        attempt_root=target, adapter_batch=batch, schema_raw=schema_raw,
    )
    metrics = json.loads(expected["metrics.json"].decode("utf-8"))
    if metrics != _SUCCESSOR_METRICS_V5:
        raise AttemptError("FRESH_V6_FORMAL_METRICS_INVALID")
    return {
        "attempt_sha256": validated["attempt_sha256"],
        "case_count": 11,
        "metrics": metrics,
        "role": "formal",
        "status": "completed",
        "valid": True,
    }


def run_fresh_formal_measurement_v6(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Publish or byte-exactly resume the fixed fresh formal-v6 directory."""
    repository = repository.resolve(strict=True)
    paths = _fresh_paths(repository)
    batch, schema_raw, expected = _fresh_formal_expected_files(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    target = paths["formal"]
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise AttemptError("FRESH_V6_FORMAL_TARGET_KIND_INVALID")
    if target.exists():
        _read_exact_formal_directory(target, expected)
        result = validate_fresh_formal_measurement_v6(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        return {**result, "write_status": "resumed"}
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink():
        raise AttemptError("FRESH_V6_FORMAL_PARENT_INVALID")
    temporary = Path(tempfile.mkdtemp(prefix=".formal-golden-pr2164-v6.staging-", dir=parent))
    try:
        for name in sorted(expected):
            _write_exact(temporary / name, expected[name])
        validate_measurement_attempt(
            attempt_root=temporary, adapter_batch=batch, schema_raw=schema_raw,
        )
        _sync_directory(temporary)
        _sync_directory(parent)

        # Re-run the non-optional published closure and active-authority gate
        # immediately before publishing the directory.
        fresh_batch, fresh_schema, fresh_expected = _fresh_formal_expected_files(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        if (
            fresh_expected != expected
            or getattr(fresh_batch, "adapter_batch_sha256", None)
            != getattr(batch, "adapter_batch_sha256", None)
            or fresh_schema != schema_raw
        ):
            raise AttemptError("FRESH_V6_FORMAL_PREWRITE_DRIFT")
        try:
            _publish_directory_no_replace(
                temporary, target, "FRESH_V6_FORMAL_TARGET_RACE",
            )
        except BundleError as error:
            raise AttemptError(str(error)) from error
        _sync_directory(parent)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    result = validate_fresh_formal_measurement_v6(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    return {**result, "write_status": "written"}


def _fresh_adversarial_expected(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> tuple[dict[str, object], bytes]:
    batch, golden, golden_raw = _fresh_v6_context(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    paths = _fresh_paths(repository)
    formal = validate_fresh_formal_measurement_v6(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    contract_result = validate_required_diagnostics_v4(
        contract=paths["contract"], golden_predictions=paths["golden"],
    )
    contract, contract_raw = _canonical_file(
        paths["contract"], "FRESH_V7_ADVERSARIAL_CONTRACT_INVALID",
    )
    _, adapter_raw = _canonical_file(paths["adapter"], "FRESH_V7_ADAPTER_INVALID")
    _, rules_raw = _canonical_file(paths["rules"], "FRESH_V7_RULES_INVALID")
    _, schema_raw = _canonical_file(paths["schema"], "FRESH_V7_SCHEMA_INVALID")
    cases: list[dict[str, object]] = []
    for case in contract["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("mutations"), list):
            raise AttemptError("FRESH_V7_ADVERSARIAL_CONTRACT_INVALID")
        mutated = _apply_successor_mutations(golden, case["mutations"])
        observed = _evaluate_successor_payload(mutated, golden)
        if observed != case.get("expected_diagnostics"):
            raise AttemptError(f"FRESH_V7_ADVERSARIAL_MISMATCH:{case.get('id')}")
        cases.append({
            "expected_diagnostics": case["expected_diagnostics"],
            "formal_effect": case["formal_effect"],
            "id": case["id"],
            "matched": True,
            "metric_output_allowed": False,
            "mutated_input_sha256": sha256_bytes(canonical_json_bytes(mutated)),
            "observed_diagnostics": observed,
        })
    if len(cases) != contract_result["case_count"] or len(cases) != 17:
        raise AttemptError("FRESH_V7_ADVERSARIAL_CONTRACT_INVALID")
    source_identity = getattr(batch, "source_identity", {})
    report: dict[str, object] = {
        "bindings": {
            "adapter_batch_file_sha256": sha256_bytes(adapter_raw),
            "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256", None),
            "authority_sha256": source_identity.get("authority_sha256"),
            "closure_freeze_commit": source_identity.get("closure_freeze_commit"),
            "closure_sha256": source_identity.get("closure_sha256"),
            "formal_attempt_sha256": formal["attempt_sha256"],
            "golden_predictions_sha256": sha256_bytes(golden_raw),
            "required_diagnostics_sha256": sha256_bytes(contract_raw),
            "rule_sha256": sha256_bytes(rules_raw),
            "schema_sha256": sha256_bytes(schema_raw),
        },
        "cases": cases,
        "schema_version": "adversarial-oracle-results-v7",
        "status": "diagnostic_only",
    }
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report, canonical_json_bytes(report)


def validate_fresh_adversarial_result_v7(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Replay and byte-compare the fixed fresh adversarial-v7 report."""
    repository = repository.resolve(strict=True)
    expected, expected_raw = _fresh_adversarial_expected(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    target = _fresh_paths(repository)["adversarial"]
    try:
        evidence, raw = read_authoritative_file(target.parent, target.name)
    except (OSError, FilesystemPolicyError) as error:
        raise AttemptError("FRESH_V7_ADVERSARIAL_REPORT_INVALID") from error
    if evidence.file_kind != "regular_file" or raw != expected_raw:
        raise AttemptError("FRESH_V7_ADVERSARIAL_REPORT_DIVERGED")
    return {
        "case_count": len(expected["cases"]),
        "report_sha256": expected["report_sha256"],
        "status": "diagnostic_only",
        "valid": True,
    }


def run_fresh_adversarial_suite_v7(
    *, repository: Path, runtime_closure: Mapping[str, object], authority_path: Path,
) -> dict[str, object]:
    """Publish or byte-exactly resume the fixed fresh adversarial-v7 report."""
    repository = repository.resolve(strict=True)
    target = _fresh_paths(repository)["adversarial"]
    expected, expected_raw = _fresh_adversarial_expected(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise AttemptError("FRESH_V7_ADVERSARIAL_TARGET_KIND_INVALID")
    if target.exists():
        result = validate_fresh_adversarial_result_v7(
            repository=repository,
            runtime_closure=runtime_closure,
            authority_path=authority_path,
        )
        return {**result, "write_status": "resumed"}
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise AttemptError("FRESH_V7_ADVERSARIAL_PARENT_INVALID")

    # The second build is the write-adjacent mandatory closure/authority gate.
    fresh, fresh_raw = _fresh_adversarial_expected(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    if fresh_raw != expected_raw or fresh.get("report_sha256") != expected.get("report_sha256"):
        raise AttemptError("FRESH_V7_ADVERSARIAL_PREWRITE_DRIFT")
    try:
        _write_exact(target, fresh_raw)
        _sync_directory(target.parent)
    except (FileExistsError, OSError) as error:
        raise AttemptError("FRESH_V7_ADVERSARIAL_TARGET_RACE") from error
    result = validate_fresh_adversarial_result_v7(
        repository=repository,
        runtime_closure=runtime_closure,
        authority_path=authority_path,
    )
    return {**result, "write_status": "written"}
