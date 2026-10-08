# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Command boundary for deterministic measurement artifacts."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from specchoice_evidence.bundle import _sync_directory, _write_exact
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file

from .adapter import AdapterError, build_pr2164_adapter_batch
from .attempts import (
    AttemptError,
    load_measurement_attempt_manifest,
    run_adversarial_suite_v6,
    run_formal_measurement_v5,
    run_measurement_attempt,
    validate_adversarial_result_v6,
    validate_formal_measurement_v5,
    validate_measurement_attempt,
    validate_successor_adapter_batch_v6,
    write_successor_adapter_batch_v6,
)
from .final_reports import (
    FINAL_SUCCESSOR_TARGETS,
    FinalReportError,
    verify_final_successor_reports,
    write_final_successor_reports,
)
from .h1 import (
    H1Error,
    build_h1_packet,
    build_h1_semantic_packet_v6,
    validate_h1_decision_v2,
    validate_h1_ontology_decision_v1,
    validate_h1_ontology_options_v1,
    validate_h1_packet,
    validate_h1_readiness_v3,
    validate_h1_route_supersession_v1,
    validate_h1_semantic_packet_v6,
    validate_h1_semantic_readiness_v6,
    validate_h1_semantic_review_decision,
    write_h1_readiness_v3,
    write_h1_semantic_readiness_v6,
)
from .preflight import _source_bytes_by_fixture, preflight_prediction_batch
from .scoring import score_prediction_batch


def _read_bound_bytes(path: Path, code: str) -> bytes:
    try:
        _, raw = read_authoritative_file(path.parent, path.name)
        return raw
    except (OSError, FilesystemPolicyError) as error:
        raise AttemptError(code) from error


def _source_batch(args: argparse.Namespace) -> object:
    """Build the one explicit legacy-v2, pending-v3, or active-v3 source mode."""
    batch = build_pr2164_adapter_batch(
        authority_path=args.authority,
        bundle_root=args.bundle,
        rules_path=args.rules,
        pending_authority_path=getattr(args, "pending_authority", None),
        transition_path=getattr(args, "transition", None),
        revocation_path=getattr(args, "revocation", None),
    )
    if not batch.valid:
        raise AdapterError("ADAPTER_BATCH_NOT_SCORE_ELIGIBLE")
    return batch


def command_adapt_pr2164(args: argparse.Namespace) -> int:
    try:
        parent = os.lstat(args.output.parent)
        target = os.lstat(args.output)
    except FileNotFoundError:
        target = None
    except OSError as error:
        raise AdapterError("ADAPTER_OUTPUT_PATH_INVALID") from error
    if not args.output.parent.is_dir() or args.output.parent.is_symlink() or target is not None:
        raise AdapterError("ADAPTER_OUTPUT_ALREADY_EXISTS")
    batch = build_pr2164_adapter_batch(
        authority_path=args.authority,
        bundle_root=args.bundle,
        rules_path=args.rules,
        pending_authority_path=args.pending_authority,
        transition_path=args.transition,
        revocation_path=getattr(args, "revocation", None),
    )
    if not batch.valid:
        raise AdapterError("ADAPTER_BATCH_NOT_SCORE_ELIGIBLE")
    try:
        _write_exact(args.output, canonical_json_bytes(batch.as_dict()))
        _sync_directory(args.output.parent)
    except FileExistsError as error:
        raise AdapterError("ADAPTER_OUTPUT_ALREADY_EXISTS") from error
    sys.stdout.buffer.write(canonical_json_bytes({"adapter_batch_sha256": batch.adapter_batch_sha256, "status": "written"}))
    return 0


def command_run_formal_measurement(args: argparse.Namespace) -> int:
    """Run one formal attempt against the explicit selected source mode."""
    raw_predictions = _read_bound_bytes(args.predictions, "FORMAL_PREDICTIONS_UNREADABLE")
    schema_raw = _read_bound_bytes(args.schema, "ATTEMPT_SCHEMA_UNREADABLE")
    batch = _source_batch(args)
    preflight = preflight_prediction_batch(raw=raw_predictions, adapter_batch=batch, ingress="current-v1")
    score = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")
    result = run_measurement_attempt(
        mode="formal",
        attempt_id=args.attempt_id,
        attempt_root=args.attempt_root,
        inputs={
            "adapter_batch": batch,
            "ingress": "current-v1",
            "preflight": preflight,
            "raw_predictions": raw_predictions,
            "score_result": score,
            "schema_raw": schema_raw,
        },
    )
    if result["status"] != "completed":
        raise AttemptError("FORMAL_MEASUREMENT_NOT_CLEAN")
    validated = validate_measurement_attempt(
        attempt_root=args.attempt_root / args.attempt_id,
        adapter_batch=batch,
        schema_raw=schema_raw,
    )
    if validated != result:
        raise AttemptError("FORMAL_ATTEMPT_VALIDATION_MISMATCH")
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return 0


def command_validate_attempt(args: argparse.Namespace) -> int:
    schema_raw = _read_bound_bytes(args.schema, "ATTEMPT_SCHEMA_UNREADABLE")
    batch = _source_batch(args)
    sys.stdout.buffer.write(canonical_json_bytes(validate_measurement_attempt(
        attempt_root=args.attempt, adapter_batch=batch, schema_raw=schema_raw,
    )))
    return 0


def _fixture_span(batch: object, fixture_id: str) -> dict[str, object]:
    values = _source_bytes_by_fixture(batch).get(fixture_id, {})
    for digest, raw in values.items():
        for end in range(1, min(len(raw), 4) + 1):
            try:
                text = raw[:end].decode("utf-8")
            except UnicodeDecodeError:
                continue
            return {"source_sha256": digest, "start_byte": 0, "end_byte": end, "text": text}
    raise AttemptError("ADVERSARIAL_INPUT_INVALID")


def _mutate_adversarial_payload(payload: dict[str, object], oracle_id: str, *, negative_span: dict[str, object] | None = None) -> None:
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise AttemptError("ADVERSARIAL_INPUT_INVALID")
    by_fixture = {item.get("fixture_id"): item for item in predictions if isinstance(item, dict)}
    try:
        positive = by_fixture["POS_CSR_RW_MTVEC_ACCESS"]
        candidate = by_fixture["CAND_WARL_FIXED_LEGAL_SET"]
        negative = by_fixture["NEG_EXT_GATED_PBMTE"]
        positive_adjudication = positive["adjudication"]
        candidate_adjudication = candidate["adjudication"]
        negative_adjudication = negative["adjudication"]
        span = positive_adjudication["evidence_spans"][0]
    except (KeyError, IndexError, TypeError) as error:
        raise AttemptError("ADVERSARIAL_INPUT_INVALID") from error
    if not all(isinstance(item, dict) for item in (positive_adjudication, candidate_adjudication, negative_adjudication, span)):
        raise AttemptError("ADVERSARIAL_INPUT_INVALID")
    mutations = {
        "accepted-parameter-name-missing": lambda: positive_adjudication.update(proposed_name=None),
        "candidate-not-surfaced": lambda: candidate_adjudication.update(surfaced=False, parameter_status=None, evidence_spans=[]),
        "candidate-accepted": lambda: candidate_adjudication.update(parameter_status="accept"),
        "candidate-review": lambda: candidate_adjudication.update(parameter_status="review"),
        "positive-not-surfaced": lambda: positive_adjudication.update(
            surfaced=False, parameter_status=None, proposed_name=None, evidence_spans=[]
        ),
        "positive-classified-out": lambda: positive_adjudication.update(parameter_status="classify_out"),
        "negative-accepted": lambda: negative_adjudication.update(
            surfaced=True, parameter_status="accept", proposed_name="PBMTE", evidence_spans=[deepcopy(negative_span)]
        ),
        "negative-review": lambda: negative_adjudication.update(
            surfaced=True, parameter_status="review", proposed_name=None, evidence_spans=[deepcopy(negative_span)]
        ),
        "evidence-empty": lambda: positive_adjudication.update(evidence_spans=[]),
        "evidence-source-changed": lambda: span.update(source_sha256="0" * 64),
        "evidence-empty-range": lambda: span.update(end_byte=0),
        "evidence-text-mismatch": lambda: span.update(text="changed"),
    }
    try:
        mutations[oracle_id]()
    except KeyError as error:
        raise AttemptError("ADVERSARIAL_ORACLE_UNKNOWN") from error


def _canonical_object(path: Path, code: str) -> tuple[dict[str, object], bytes]:
    try:
        raw = _read_bound_bytes(path, code)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttemptError(code) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise AttemptError(code)
    return payload, raw


def _adversarial_bindings(*, batch: object, schema_raw: bytes, golden_raw: bytes, formal_attempt_sha256: str) -> dict[str, object]:
    return {
        "adapter_batch_sha256": getattr(batch, "adapter_batch_sha256", None),
        "formal_attempt_sha256": formal_attempt_sha256,
        "golden_predictions_sha256": sha256_bytes(golden_raw),
        "rule_sha256": getattr(batch, "rule_sha256", None),
        "schema_sha256": sha256_bytes(schema_raw),
        "source_identity": getattr(batch, "source_identity", None),
    }


def _require_adversarial_oracle_identity(
    oracle: dict[str, object], *, golden_path: Path, golden_raw: bytes, code: str
) -> list[dict[str, object]]:
    """Require every closed oracle entry to name the held prediction bytes exactly."""
    entries = oracle.get("oracles")
    if set(oracle) != {"oracles", "schema_version"} or oracle.get("schema_version") != "required-diagnostics-v1" or not isinstance(entries, list) or not entries:
        raise AttemptError(code)
    expected_identity = {
        "base_fixture": golden_path.name,
        "base_sha256": sha256_bytes(golden_raw),
    }
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"expected_diagnostics", "id", "raw_input_identity"} or not isinstance(entry.get("id"), str) or not isinstance(entry.get("expected_diagnostics"), list):
            raise AttemptError(code)
        identity = entry.get("raw_input_identity")
        if not isinstance(identity, dict) or set(identity) != {"base_fixture", "base_sha256", "mutation"} or not isinstance(identity.get("mutation"), str) or {
            "base_fixture": identity.get("base_fixture"), "base_sha256": identity.get("base_sha256"),
        } != expected_identity:
            raise AttemptError(code)
    return entries


def command_run_adversarial_oracles(args: argparse.Namespace) -> int:
    """Prove frozen diagnostics for the explicit selected source mode only."""
    schema_raw = _read_bound_bytes(args.schema, "ADVERSARIAL_REPORT_INVALID")
    batch = _source_batch(args)
    formal = validate_measurement_attempt(
        attempt_root=args.formal_attempt, adapter_batch=batch, schema_raw=schema_raw
    )
    if (formal["role"], formal["status"]) != ("formal", "completed"):
        raise AttemptError("FORMAL_ATTEMPT_NOT_CLEAN")
    oracle, oracle_raw = _canonical_object(args.oracle, "ADVERSARIAL_ORACLE_INVALID")
    golden, golden_raw = _canonical_object(args.predictions, "ADVERSARIAL_INPUT_INVALID")
    entries = _require_adversarial_oracle_identity(
        oracle, golden_path=args.predictions, golden_raw=golden_raw, code="ADVERSARIAL_ORACLE_INVALID"
    )
    negative_span = _fixture_span(batch, "NEG_EXT_GATED_PBMTE")
    attempt_root = args.report.parent / f"{args.report.stem}-attempts"
    if args.report.exists() or args.report.is_symlink() or attempt_root.exists() or attempt_root.is_symlink():
        raise AttemptError("ADVERSARIAL_REPORT_EXISTS")
    cases: list[dict[str, object]] = []
    for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not isinstance(entry.get("expected_diagnostics"), list):
                raise AttemptError("ADVERSARIAL_ORACLE_INVALID")
            payload = deepcopy(golden)
            _mutate_adversarial_payload(payload, entry["id"], negative_span=negative_span)
            raw_predictions = canonical_json_bytes(payload)
            preflight = preflight_prediction_batch(raw=raw_predictions, adapter_batch=batch, ingress="current-v1")
            score = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")
            observed = [item.as_dict() for item in (preflight.diagnostics if preflight.status == "invalid_preflight" else score.diagnostics)]
            expected = entry["expected_diagnostics"]
            if observed != expected:
                raise AttemptError("ADVERSARIAL_ORACLE_MISMATCH")
            attempt = run_measurement_attempt(
                mode="diagnostic_only",
                attempt_id=f"oracle-{index:02d}",
                attempt_root=attempt_root,
                inputs={
                    "adapter_batch": batch,
                    "ingress": "current-v1",
                    "preflight": preflight,
                    "raw_predictions": raw_predictions,
                    "score_result": score,
                    "schema_raw": schema_raw,
                },
            )
            if validate_measurement_attempt(
                attempt_root=attempt_root / f"oracle-{index:02d}",
                adapter_batch=batch,
                schema_raw=schema_raw,
            ) != attempt:
                raise AttemptError("ADVERSARIAL_ATTEMPT_VALIDATION_MISMATCH")
            cases.append({
                "attempt_id": f"oracle-{index:02d}",
                "attempt_sha256": attempt["attempt_sha256"],
                "expected_diagnostics": expected,
                "id": entry["id"],
                "matched": True,
                "observed_diagnostics": observed,
                "raw_predictions_sha256": sha256_bytes(raw_predictions),
                "role": attempt["role"],
                "status": attempt["status"],
            })
    report = {
        "bindings": _adversarial_bindings(
            batch=batch, schema_raw=schema_raw, golden_raw=golden_raw,
            formal_attempt_sha256=str(formal["attempt_sha256"]),
        ),
        "cases": cases,
        "oracle_sha256": sha256_bytes(oracle_raw),
        "schema_version": "adversarial-oracle-results-v2",
        "status": "diagnostic_only",
    }
    if args.report.exists() or args.report.is_symlink():
        raise AttemptError("ADVERSARIAL_REPORT_EXISTS")
    try:
        _write_exact(args.report, canonical_json_bytes(report))
        _sync_directory(args.report.parent)
    except FileExistsError as error:
        raise AttemptError("ADVERSARIAL_REPORT_EXISTS") from error
    validate_adversarial_report(
        report_path=args.report,
        formal_attempt=args.formal_attempt,
        authority=args.authority,
        bundle=args.bundle,
        rules=args.rules,
        schema=args.schema,
        predictions=args.predictions,
        oracle=args.oracle,
        pending_authority=args.pending_authority,
        transition=args.transition,
        revocation=getattr(args, "revocation", None),
    )
    sys.stdout.buffer.write(canonical_json_bytes({"oracle_sha256": report["oracle_sha256"], "status": report["status"]}))
    return 0


def validate_adversarial_report(
    *,
    report_path: Path,
    formal_attempt: Path,
    authority: Path | None = None,
    bundle: Path | None = None,
    rules: Path | None = None,
    schema: Path | None = None,
    predictions: Path | None = None,
    oracle: Path | None = None,
    pending_authority: Path | None = None,
    transition: Path | None = None,
    revocation: Path | None = None,
) -> dict[str, object]:
    """Validate the closed, canonical diagnostic-only report against the frozen oracle."""
    explicit = (authority, bundle, rules, schema, predictions, oracle)
    if all(value is None for value in explicit):
        experiment_root = Path(__file__).parents[2]
        authority = experiment_root / "phase2/source-authority-v9-historical.json"
        bundle = experiment_root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        rules = experiment_root / "config/measurement/pr2164-adapter-rules-v1.json"
        schema = experiment_root / "config/measurement/canonical-adjudication-schema-v1.json"
        predictions = experiment_root / "fixtures/measurement/golden-predictions-v1.json"
        oracle = experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v1.json"
        batch = build_pr2164_adapter_batch(authority_path=authority, bundle_root=bundle, rules_path=rules)
    elif any(value is None for value in explicit):
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    else:
        args = argparse.Namespace(
            authority=authority, bundle=bundle, rules=rules,
            pending_authority=pending_authority, transition=transition, revocation=revocation,
        )
        batch = _source_batch(args)
    assert schema is not None and predictions is not None and oracle is not None
    try:
        schema_raw = _read_bound_bytes(schema, "ADVERSARIAL_REPORT_INVALID")
        formal = validate_measurement_attempt(
            attempt_root=formal_attempt, adapter_batch=batch, schema_raw=schema_raw
        )
        report, _ = _canonical_object(report_path, "ADVERSARIAL_REPORT_INVALID")
        oracle, oracle_raw = _canonical_object(oracle, "ADVERSARIAL_REPORT_INVALID")
        golden, golden_raw = _canonical_object(predictions, "ADVERSARIAL_REPORT_INVALID")
        expected_entries = _require_adversarial_oracle_identity(
            oracle, golden_path=predictions, golden_raw=golden_raw, code="ADVERSARIAL_REPORT_INVALID"
        )
    except (AttemptError, OSError, ValueError) as error:
        raise AttemptError("ADVERSARIAL_REPORT_INVALID") from error
    if (formal.get("role"), formal.get("status")) != ("formal", "completed"):
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    expected_keys = {"bindings", "cases", "oracle_sha256", "schema_version", "status"}
    if set(report) != expected_keys or report.get("schema_version") != "adversarial-oracle-results-v2" or report.get("status") != "diagnostic_only":
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    bindings = report.get("bindings")
    if not batch.valid or not isinstance(bindings, dict) or bindings != _adversarial_bindings(
        batch=batch, schema_raw=schema_raw, golden_raw=golden_raw,
        formal_attempt_sha256=str(formal["attempt_sha256"]),
    ):
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    cases = report.get("cases")
    if report.get("oracle_sha256") != sha256_bytes(oracle_raw) or not isinstance(expected_entries, list) or not isinstance(cases, list) or len(cases) != len(expected_entries):
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    attempt_root = report_path.parent / f"{report_path.stem}-attempts"
    if not attempt_root.is_dir() or attempt_root.is_symlink():
        raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    for index, (entry, case) in enumerate(zip(expected_entries, cases, strict=True), start=1):
        if not isinstance(entry, dict) or not isinstance(case, dict) or set(case) != {
            "attempt_id", "attempt_sha256", "expected_diagnostics", "id", "matched", "observed_diagnostics", "raw_predictions_sha256", "role", "status"
        } or case.get("id") != entry.get("id") or case.get("expected_diagnostics") != entry.get("expected_diagnostics") or case.get("observed_diagnostics") != entry.get("expected_diagnostics") or case.get("matched") is not True or (case.get("role"), case.get("status")) != ("diagnostic_only", "diagnostic_only") or not isinstance(case.get("attempt_id"), str) or not isinstance(case.get("attempt_sha256"), str) or len(case["attempt_sha256"]) != 64 or not isinstance(case.get("raw_predictions_sha256"), str) or len(case["raw_predictions_sha256"]) != 64:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
        expected_attempt_id = f"oracle-{index:02d}"
        if case["attempt_id"] != expected_attempt_id:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
        attempt_path = attempt_root / expected_attempt_id
        if not attempt_path.is_dir() or attempt_path.is_symlink():
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
        try:
            validated = validate_measurement_attempt(
                attempt_root=attempt_path, adapter_batch=batch, schema_raw=schema_raw
            )
            manifest = load_measurement_attempt_manifest(attempt_root=attempt_path)
        except AttemptError as error:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID") from error
        if validated != {"attempt_sha256": case["attempt_sha256"], "role": "diagnostic_only", "status": "diagnostic_only"}:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
        try:
            raw = base64.b64decode(manifest["raw_predictions_base64"], validate=True)
        except (KeyError, TypeError, ValueError) as error:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID") from error
        payload = deepcopy(golden)
        _mutate_adversarial_payload(payload, str(case["id"]), negative_span=_fixture_span(batch, "NEG_EXT_GATED_PBMTE"))
        if raw != canonical_json_bytes(payload) or sha256_bytes(raw) != case["raw_predictions_sha256"]:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
        preflight = preflight_prediction_batch(raw=raw, adapter_batch=batch, ingress="current-v1")
        score = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")
        observed = [item.as_dict() for item in (preflight.diagnostics if preflight.status == "invalid_preflight" else score.diagnostics)]
        if observed != entry["expected_diagnostics"]:
            raise AttemptError("ADVERSARIAL_REPORT_INVALID")
    return report


def command_validate_adversarial_report(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(
        canonical_json_bytes(
            validate_adversarial_report(
                report_path=args.report,
                formal_attempt=args.formal_attempt,
                authority=args.authority,
                bundle=args.bundle,
                rules=args.rules,
                schema=args.schema,
                predictions=args.predictions,
                oracle=args.oracle,
                pending_authority=args.pending_authority,
                transition=args.transition,
                revocation=getattr(args, "revocation", None),
            )
        )
    )
    return 0


def command_build_h1_packet(args: argparse.Namespace) -> int:
    packet = build_h1_packet(
        formal_attempt=args.formal_attempt,
        adversarial_report=args.adversarial_report,
        output_json=args.output,
        output_markdown=args.markdown,
        schema=args.schema,
        authority=args.authority,
        bundle=args.bundle,
        rules=args.rules,
        predictions=args.predictions,
        oracle=args.oracle,
        pending_authority=args.pending_authority,
        transition=args.transition,
        revocation=args.revocation,
    )
    sys.stdout.buffer.write(canonical_json_bytes({"packet_sha256": packet["packet_sha256"], "status": "written"}))
    return 0


def command_validate_h1_packet(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_packet(
        packet=args.packet, markdown=args.markdown, schema=args.schema,
        formal_attempt=args.formal_attempt, adversarial_report=args.adversarial_report,
        authority=args.authority, bundle=args.bundle, rules=args.rules, predictions=args.predictions, oracle=args.oracle,
        pending_authority=args.pending_authority, transition=args.transition, revocation=args.revocation,
    )))
    return 0


def command_write_h1_readiness_v3(args: argparse.Namespace) -> int:
    if not args.phase_gate_stdin:
        raise H1Error("H1_PHASE_GATE_STDIN_REQUIRED")
    sys.stdout.buffer.write(canonical_json_bytes(write_h1_readiness_v3(
        output=args.output, formal_attempt=args.formal_attempt, adversarial_result=args.adversarial_result,
        packet=args.packet, markdown=args.markdown, schema=args.schema, source_authority=args.source_authority,
        canonical_revocation=args.canonical_revocation, bundle=args.bundle, rules=args.rules,
        predictions=args.predictions, oracle=args.oracle, offline_replay=args.offline_replay,
        phase_gate=sys.stdin.buffer.read(), plan_summary=args.plan_summary,
    )))
    return 0


def command_validate_h1_readiness_v3(args: argparse.Namespace) -> int:
    if not args.phase_gate_stdin:
        raise H1Error("H1_PHASE_GATE_STDIN_REQUIRED")
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_readiness_v3(
        readiness=args.readiness, formal_attempt=args.formal_attempt, adversarial_result=args.adversarial_result,
        packet=args.packet, markdown=args.markdown, schema=args.schema, source_authority=args.source_authority,
        canonical_revocation=args.canonical_revocation, bundle=args.bundle, rules=args.rules,
        predictions=args.predictions, oracle=args.oracle, offline_replay=args.offline_replay,
        phase_gate=sys.stdin.buffer.read(), plan_summary=args.plan_summary,
    )))
    return 0


def command_validate_h1_decision_v2(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_decision_v2(
        schema=args.schema, packet=args.packet, readiness=args.readiness, decision=args.decision,
    )))
    return 0


def command_validate_h1_route_supersession_v1(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_route_supersession_v1(
        supersession=args.supersession, schema=args.schema, packet=args.packet, markdown=args.markdown,
        readiness=args.readiness,
    )))
    return 0


def command_validate_h1_ontology_options_v1(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_ontology_options_v1(options=args.options)))
    return 0


def command_validate_h1_ontology_decision_v1(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_ontology_decision_v1(
        options=args.options, supersession=args.supersession, decision=args.decision,
    )))
    return 0


def _successor_measurement_inputs(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "fixture_registry": args.fixture_registry,
        "rules": args.rules,
        "semantic_contract": args.semantic_contract,
        "golden_predictions": args.golden_predictions,
        "bundle_root": args.bundle_root,
    }


def command_adapt_pr2164_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(write_successor_adapter_batch_v6(
        output=args.output,
        preflight=args.preflight,
        **_successor_measurement_inputs(args),
    )))
    return 0


def command_validate_adapter_batch_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_successor_adapter_batch_v6(
        adapter_batch=args.adapter_batch,
        **_successor_measurement_inputs(args),
    )))
    return 0


def command_run_formal_measurement_v5(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(run_formal_measurement_v5(
        adapter_batch=args.adapter_batch,
        adjudication_schema=args.adjudication_schema,
        attempt_root=args.attempt_root,
        attempt_id=args.attempt_id,
        preflight=args.preflight,
        **_successor_measurement_inputs(args),
    )))
    return 0


def command_validate_formal_measurement_v5(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_formal_measurement_v5(
        adapter_batch=args.adapter_batch,
        adjudication_schema=args.adjudication_schema,
        attempt=args.attempt,
        **_successor_measurement_inputs(args),
    )))
    return 0


def command_run_adversarial_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(run_adversarial_suite_v6(
        contract=args.contract,
        golden_predictions=args.golden_predictions,
        formal_attempt=args.formal_attempt,
        adapter_batch=args.adapter_batch,
        fixture_registry=args.fixture_registry,
        rules=args.rules,
        semantic_contract=args.semantic_contract,
        schema=args.schema,
        bundle_root=args.bundle_root,
        output=args.output,
        preflight=args.preflight,
    )))
    return 0


def command_validate_adversarial_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_adversarial_result_v6(
        report=args.report,
        contract=args.contract,
        golden_predictions=args.golden_predictions,
        formal_attempt=args.formal_attempt,
        adapter_batch=args.adapter_batch,
        fixture_registry=args.fixture_registry,
        rules=args.rules,
        semantic_contract=args.semantic_contract,
        schema=args.schema,
        bundle_root=args.bundle_root,
    )))
    return 0


def _successor_h1_inputs(args: argparse.Namespace) -> dict[str, object]:
    return {
        "adapter_batch": args.adapter_batch,
        "adversarial_report": args.adversarial_report,
        "adversarial_contract": args.adversarial_contract,
        "adjudication_schema": args.adjudication_schema,
        "executable_closure": args.executable_closure,
        "formal_attempt": args.formal_attempt,
        "golden_predictions": args.golden_predictions,
        "fixture_registry": args.fixture_registry,
        "ontology_decision": args.ontology_decision,
        "ontology_options": args.ontology_options,
        "ontology_supersession": args.ontology_supersession,
        "questions": args.questions,
        "rules": args.rules,
        "semantic_contract": args.semantic_contract,
        "schema": args.schema,
        "source_authority": args.source_authority,
        "bundle_root": args.bundle_root,
    }


def command_build_h1_semantic_packet_v6(args: argparse.Namespace) -> int:
    value = build_h1_semantic_packet_v6(
        output_json=args.output,
        output_markdown=args.markdown,
        preflight=args.preflight,
        **_successor_h1_inputs(args),
    )
    sys.stdout.buffer.write(canonical_json_bytes({
        "packet_sha256": value["packet_sha256"],
        "status": "preflight_valid" if args.preflight else "written",
    }))
    return 0


def command_validate_h1_semantic_packet_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_semantic_packet_v6(
        packet=args.packet,
        markdown=args.markdown,
        **_successor_h1_inputs(args),
    )))
    return 0


def command_write_h1_semantic_readiness_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(write_h1_semantic_readiness_v6(
        output=args.output,
        packet=args.packet,
        markdown=args.markdown,
        preflight=args.preflight,
        **_successor_h1_inputs(args),
    )))
    return 0


def command_validate_h1_semantic_readiness_v6(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_semantic_readiness_v6(
        readiness=args.readiness,
        packet=args.packet,
        markdown=args.markdown,
        **_successor_h1_inputs(args),
    )))
    return 0


def command_validate_h1_semantic_review_decision(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(validate_h1_semantic_review_decision(
        packet=args.packet,
        markdown=args.markdown,
        readiness=args.readiness,
        decision=args.decision,
        **_successor_h1_inputs(args),
    )))
    return 0


def _repository_root(args: argparse.Namespace) -> Path:
    return args.repository_root.absolute()


def _final_targets(args: argparse.Namespace) -> tuple[str, ...]:
    root = _repository_root(args)
    supplied = (
        args.phase1_verification,
        args.phase1_review,
        args.phase2_verification,
        args.phase2_review,
    )
    values: list[str] = []
    for path in supplied:
        absolute = path.absolute()
        try:
            values.append(absolute.relative_to(root).as_posix())
        except ValueError as error:
            raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID") from error
    if tuple(values) != FINAL_SUCCESSOR_TARGETS:
        raise FinalReportError("FINAL_REPORT_TARGET_INVENTORY_INVALID")
    return tuple(values)


def command_write_final_successor_reports(args: argparse.Namespace) -> int:
    bindings: list[dict[str, object]] = []
    for encoded in args.binding:
        try:
            value = json.loads(encoded)
        except json.JSONDecodeError as error:
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID") from error
        if not isinstance(value, dict):
            raise FinalReportError("FINAL_REPORT_BINDING_INVALID")
        bindings.append(value)
    sys.stdout.buffer.write(canonical_json_bytes(write_final_successor_reports(
        _repository_root(args),
        audited_commit=args.audited_commit,
        bindings=bindings,
        targets=_final_targets(args),
        preflight=args.preflight,
    )))
    return 0


def command_verify_final_successor_reports(args: argparse.Namespace) -> int:
    sys.stdout.buffer.write(canonical_json_bytes(verify_final_successor_reports(
        _repository_root(args), targets=_final_targets(args)
    )))
    return 0


def _add_successor_h1_inputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("--adapter-batch", type=Path, required=True)
    command.add_argument("--adversarial-report", type=Path, required=True)
    command.add_argument("--adversarial-contract", type=Path, required=True)
    command.add_argument("--adjudication-schema", type=Path, required=True)
    command.add_argument("--executable-closure", type=Path, required=True)
    command.add_argument("--formal-attempt", type=Path, required=True)
    command.add_argument("--golden-predictions", type=Path, required=True)
    command.add_argument("--fixture-registry", type=Path, required=True)
    command.add_argument("--ontology-decision", type=Path, required=True)
    command.add_argument("--ontology-options", type=Path, required=True)
    command.add_argument("--ontology-supersession", type=Path, required=True)
    command.add_argument("--questions", type=Path, required=True)
    command.add_argument("--rules", type=Path, required=True)
    command.add_argument("--semantic-contract", type=Path, required=True)
    command.add_argument("--schema", type=Path, required=True)
    command.add_argument("--source-authority", type=Path, required=True)
    command.add_argument("--bundle-root", type=Path, required=True)


def _add_successor_measurement_inputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("--fixture-registry", type=Path, required=True)
    command.add_argument("--rules", type=Path, required=True)
    command.add_argument("--semantic-contract", type=Path, required=True)
    command.add_argument("--golden-predictions", type=Path, required=True)
    command.add_argument("--bundle-root", type=Path, required=True)


def _add_final_report_targets(command: argparse.ArgumentParser) -> None:
    repository_root = Path(__file__).parents[4]
    command.add_argument("--repository-root", type=Path, default=repository_root)
    command.add_argument("--phase1-verification", type=Path, required=True)
    command.add_argument("--phase1-review", type=Path, required=True)
    command.add_argument("--phase2-verification", type=Path, required=True)
    command.add_argument("--phase2-review", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specchoice-measurement")
    commands = parser.add_subparsers(dest="command", required=True)
    adapter = commands.add_parser("adapt-pr2164")
    adapter.add_argument("--authority", type=Path, required=True)
    adapter.add_argument("--bundle", type=Path, required=True)
    adapter.add_argument("--rules", type=Path, required=True)
    adapter.add_argument("--pending-authority", type=Path)
    adapter.add_argument("--transition", type=Path)
    adapter.add_argument("--revocation", type=Path)
    adapter.add_argument("--output", type=Path, required=True)
    adapter.set_defaults(handler=command_adapt_pr2164)
    formal = commands.add_parser("run-formal-measurement")
    formal.add_argument("--authority", type=Path, required=True)
    formal.add_argument("--bundle", type=Path, required=True)
    formal.add_argument("--rules", type=Path, required=True)
    formal.add_argument("--schema", type=Path, required=True)
    formal.add_argument("--predictions", type=Path, required=True)
    formal.add_argument("--pending-authority", type=Path)
    formal.add_argument("--transition", type=Path)
    formal.add_argument("--revocation", type=Path)
    formal.add_argument("--attempt-root", type=Path, required=True)
    formal.add_argument("--attempt-id", required=True)
    formal.set_defaults(handler=command_run_formal_measurement)
    validate_attempt = commands.add_parser("validate-attempt")
    validate_attempt.add_argument("--attempt", type=Path, required=True)
    validate_attempt.add_argument("--authority", type=Path, required=True)
    validate_attempt.add_argument("--bundle", type=Path, required=True)
    validate_attempt.add_argument("--rules", type=Path, required=True)
    validate_attempt.add_argument("--schema", type=Path, required=True)
    validate_attempt.add_argument("--pending-authority", type=Path)
    validate_attempt.add_argument("--transition", type=Path)
    validate_attempt.add_argument("--revocation", type=Path)
    validate_attempt.set_defaults(handler=command_validate_attempt)
    adversarial = commands.add_parser("run-adversarial-oracles")
    adversarial.add_argument("--authority", type=Path, required=True)
    adversarial.add_argument("--bundle", type=Path, required=True)
    adversarial.add_argument("--rules", type=Path, required=True)
    adversarial.add_argument("--schema", type=Path, required=True)
    adversarial.add_argument("--predictions", type=Path, required=True)
    adversarial.add_argument("--oracle", type=Path, required=True)
    adversarial.add_argument("--pending-authority", type=Path)
    adversarial.add_argument("--transition", type=Path)
    adversarial.add_argument("--revocation", type=Path)
    adversarial.add_argument("--formal-attempt", type=Path, required=True)
    adversarial.add_argument("--report", type=Path, required=True)
    adversarial.set_defaults(handler=command_run_adversarial_oracles)
    validate_adversarial = commands.add_parser("validate-adversarial-report")
    validate_adversarial.add_argument("--report", type=Path, required=True)
    validate_adversarial.add_argument("--formal-attempt", type=Path, required=True)
    validate_adversarial.add_argument("--authority", type=Path, required=True)
    validate_adversarial.add_argument("--bundle", type=Path, required=True)
    validate_adversarial.add_argument("--rules", type=Path, required=True)
    validate_adversarial.add_argument("--schema", type=Path, required=True)
    validate_adversarial.add_argument("--predictions", type=Path, required=True)
    validate_adversarial.add_argument("--oracle", type=Path, required=True)
    validate_adversarial.add_argument("--pending-authority", type=Path)
    validate_adversarial.add_argument("--transition", type=Path)
    validate_adversarial.add_argument("--revocation", type=Path)
    validate_adversarial.set_defaults(handler=command_validate_adversarial_report)
    h1_build = commands.add_parser("build-h1-packet")
    h1_build.add_argument("--formal-attempt", type=Path, required=True)
    h1_build.add_argument("--adversarial-report", type=Path, required=True)
    h1_build.add_argument("--schema", type=Path, required=True)
    h1_build.add_argument("--authority", type=Path, required=True)
    h1_build.add_argument("--bundle", type=Path, required=True)
    h1_build.add_argument("--rules", type=Path, required=True)
    h1_build.add_argument("--predictions", type=Path, required=True)
    h1_build.add_argument("--oracle", type=Path, required=True)
    h1_build.add_argument("--pending-authority", type=Path)
    h1_build.add_argument("--transition", type=Path)
    h1_build.add_argument("--revocation", type=Path)
    h1_build.add_argument("--output", type=Path, required=True)
    h1_build.add_argument("--markdown", type=Path, required=True)
    h1_build.set_defaults(handler=command_build_h1_packet)
    h1_packet = commands.add_parser("validate-h1-packet")
    h1_packet.add_argument("--packet", type=Path, required=True)
    h1_packet.add_argument("--markdown", type=Path, required=True)
    h1_packet.add_argument("--schema", type=Path, required=True)
    h1_packet.add_argument("--formal-attempt", type=Path, required=True)
    h1_packet.add_argument("--adversarial-report", type=Path, required=True)
    h1_packet.add_argument("--authority", type=Path, required=True)
    h1_packet.add_argument("--bundle", type=Path, required=True)
    h1_packet.add_argument("--rules", type=Path, required=True)
    h1_packet.add_argument("--predictions", type=Path, required=True)
    h1_packet.add_argument("--oracle", type=Path, required=True)
    h1_packet.add_argument("--pending-authority", type=Path)
    h1_packet.add_argument("--transition", type=Path)
    h1_packet.add_argument("--revocation", type=Path)
    h1_packet.set_defaults(handler=command_validate_h1_packet)
    readiness_writer = commands.add_parser("write-h1-readiness-v3")
    readiness_validator = commands.add_parser("validate-h1-readiness-v3")
    for command in (readiness_writer, readiness_validator):
        command.add_argument("--formal-attempt", type=Path, required=True)
        command.add_argument("--adversarial-result", type=Path, required=True)
        command.add_argument("--packet", type=Path, required=True)
        command.add_argument("--markdown", type=Path, required=True)
        command.add_argument("--schema", type=Path, required=True)
        command.add_argument("--source-authority", type=Path, required=True)
        command.add_argument("--canonical-revocation", type=Path, required=True)
        command.add_argument("--bundle", type=Path, required=True)
        command.add_argument("--rules", type=Path, required=True)
        command.add_argument("--predictions", type=Path, required=True)
        command.add_argument("--oracle", type=Path, required=True)
        command.add_argument("--offline-replay", type=Path, required=True)
        command.add_argument("--plan-summary", type=Path, required=True)
        command.add_argument("--phase-gate-stdin", action="store_true", required=True)
    readiness_writer.add_argument("--output", type=Path, required=True)
    readiness_writer.set_defaults(handler=command_write_h1_readiness_v3)
    readiness_validator.add_argument("--readiness", type=Path, required=True)
    readiness_validator.set_defaults(handler=command_validate_h1_readiness_v3)
    h1_decision = commands.add_parser("validate-h1-decision-v2")
    h1_decision.add_argument("--schema", type=Path, required=True)
    h1_decision.add_argument("--packet", type=Path, required=True)
    h1_decision.add_argument("--readiness", type=Path, required=True)
    h1_decision.add_argument("--decision", type=Path, required=True)
    h1_decision.set_defaults(handler=command_validate_h1_decision_v2)
    h1_supersession = commands.add_parser("validate-h1-route-supersession-v1")
    h1_supersession.add_argument("--supersession", type=Path, required=True)
    h1_supersession.add_argument("--schema", type=Path, required=True)
    h1_supersession.add_argument("--packet", type=Path, required=True)
    h1_supersession.add_argument("--markdown", type=Path, required=True)
    h1_supersession.add_argument("--readiness", type=Path, required=True)
    h1_supersession.set_defaults(handler=command_validate_h1_route_supersession_v1)
    h1_options = commands.add_parser("validate-h1-ontology-options-v1")
    h1_options.add_argument("--options", type=Path, required=True)
    h1_options.set_defaults(handler=command_validate_h1_ontology_options_v1)
    h1_ontology_decision = commands.add_parser("validate-h1-ontology-decision-v1")
    h1_ontology_decision.add_argument("--options", type=Path, required=True)
    h1_ontology_decision.add_argument("--supersession", type=Path, required=True)
    h1_ontology_decision.add_argument("--decision", type=Path, required=True)
    h1_ontology_decision.set_defaults(handler=command_validate_h1_ontology_decision_v1)
    successor_adapter = commands.add_parser("adapt-pr2164-v6")
    _add_successor_measurement_inputs(successor_adapter)
    successor_adapter.add_argument("--output", type=Path, required=True)
    successor_adapter.add_argument("--preflight", action="store_true")
    successor_adapter.set_defaults(handler=command_adapt_pr2164_v6)
    successor_adapter_validator = commands.add_parser("validate-adapter-batch-v6")
    _add_successor_measurement_inputs(successor_adapter_validator)
    successor_adapter_validator.add_argument("--adapter-batch", type=Path, required=True)
    successor_adapter_validator.set_defaults(handler=command_validate_adapter_batch_v6)
    successor_formal = commands.add_parser("run-formal-measurement-v5")
    _add_successor_measurement_inputs(successor_formal)
    successor_formal.add_argument("--adapter-batch", type=Path, required=True)
    successor_formal.add_argument("--adjudication-schema", type=Path, required=True)
    successor_formal.add_argument("--attempt-root", type=Path, required=True)
    successor_formal.add_argument("--attempt-id", required=True)
    successor_formal.add_argument("--preflight", action="store_true")
    successor_formal.set_defaults(handler=command_run_formal_measurement_v5)
    successor_formal_validator = commands.add_parser("validate-formal-measurement-v5")
    _add_successor_measurement_inputs(successor_formal_validator)
    successor_formal_validator.add_argument("--adapter-batch", type=Path, required=True)
    successor_formal_validator.add_argument("--adjudication-schema", type=Path, required=True)
    successor_formal_validator.add_argument("--attempt", type=Path, required=True)
    successor_formal_validator.set_defaults(handler=command_validate_formal_measurement_v5)
    adversarial_v6 = commands.add_parser("run-adversarial-semantic-suite-v6")
    adversarial_v6.add_argument("--contract", type=Path, required=True)
    adversarial_v6.add_argument("--golden-predictions", type=Path, required=True)
    adversarial_v6.add_argument("--formal-attempt", type=Path, required=True)
    adversarial_v6.add_argument("--adapter-batch", type=Path, required=True)
    adversarial_v6.add_argument("--fixture-registry", type=Path, required=True)
    adversarial_v6.add_argument("--rules", type=Path, required=True)
    adversarial_v6.add_argument("--semantic-contract", type=Path, required=True)
    adversarial_v6.add_argument("--schema", type=Path, required=True)
    adversarial_v6.add_argument("--bundle-root", type=Path, required=True)
    adversarial_v6.add_argument("--output", type=Path, required=True)
    adversarial_v6.add_argument("--preflight", action="store_true")
    adversarial_v6.set_defaults(handler=command_run_adversarial_v6)
    adversarial_v6_validator = commands.add_parser("validate-adversarial-semantic-result-v6")
    adversarial_v6_validator.add_argument("--report", type=Path, required=True)
    adversarial_v6_validator.add_argument("--contract", type=Path, required=True)
    adversarial_v6_validator.add_argument("--golden-predictions", type=Path, required=True)
    adversarial_v6_validator.add_argument("--formal-attempt", type=Path, required=True)
    adversarial_v6_validator.add_argument("--adapter-batch", type=Path, required=True)
    adversarial_v6_validator.add_argument("--fixture-registry", type=Path, required=True)
    adversarial_v6_validator.add_argument("--rules", type=Path, required=True)
    adversarial_v6_validator.add_argument("--semantic-contract", type=Path, required=True)
    adversarial_v6_validator.add_argument("--schema", type=Path, required=True)
    adversarial_v6_validator.add_argument("--bundle-root", type=Path, required=True)
    adversarial_v6_validator.set_defaults(handler=command_validate_adversarial_v6)
    h1_semantic_build = commands.add_parser("build-h1-semantic-packet-v6")
    _add_successor_h1_inputs(h1_semantic_build)
    h1_semantic_build.add_argument("--output", type=Path, required=True)
    h1_semantic_build.add_argument("--markdown", type=Path, required=True)
    h1_semantic_build.add_argument("--preflight", action="store_true")
    h1_semantic_build.set_defaults(handler=command_build_h1_semantic_packet_v6)
    h1_semantic_validate = commands.add_parser("validate-h1-semantic-packet-v6")
    _add_successor_h1_inputs(h1_semantic_validate)
    h1_semantic_validate.add_argument("--packet", type=Path, required=True)
    h1_semantic_validate.add_argument("--markdown", type=Path, required=True)
    h1_semantic_validate.set_defaults(handler=command_validate_h1_semantic_packet_v6)
    h1_semantic_readiness_write = commands.add_parser("write-h1-semantic-readiness-v6")
    _add_successor_h1_inputs(h1_semantic_readiness_write)
    h1_semantic_readiness_write.add_argument("--packet", type=Path, required=True)
    h1_semantic_readiness_write.add_argument("--markdown", type=Path, required=True)
    h1_semantic_readiness_write.add_argument("--output", type=Path, required=True)
    h1_semantic_readiness_write.add_argument("--preflight", action="store_true")
    h1_semantic_readiness_write.set_defaults(handler=command_write_h1_semantic_readiness_v6)
    h1_semantic_readiness_validate = commands.add_parser("validate-h1-semantic-readiness")
    _add_successor_h1_inputs(h1_semantic_readiness_validate)
    h1_semantic_readiness_validate.add_argument("--packet", type=Path, required=True)
    h1_semantic_readiness_validate.add_argument("--markdown", type=Path, required=True)
    h1_semantic_readiness_validate.add_argument("--readiness", type=Path, required=True)
    h1_semantic_readiness_validate.set_defaults(handler=command_validate_h1_semantic_readiness_v6)
    h1_semantic_decision = commands.add_parser("validate-h1-semantic-review-decision")
    _add_successor_h1_inputs(h1_semantic_decision)
    h1_semantic_decision.add_argument("--packet", type=Path, required=True)
    h1_semantic_decision.add_argument("--markdown", type=Path, required=True)
    h1_semantic_decision.add_argument("--readiness", type=Path, required=True)
    h1_semantic_decision.add_argument("--decision", type=Path, required=True)
    h1_semantic_decision.set_defaults(handler=command_validate_h1_semantic_review_decision)
    final_write = commands.add_parser("write-final-successor-reports")
    _add_final_report_targets(final_write)
    final_write.add_argument("--audited-commit", required=True)
    final_write.add_argument("--binding", action="append", required=True)
    final_write.add_argument("--preflight", action="store_true")
    final_write.set_defaults(handler=command_write_final_successor_reports)
    final_verify = commands.add_parser("verify-final-successor-reports")
    _add_final_report_targets(final_verify)
    final_verify.set_defaults(handler=command_verify_final_successor_reports)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (AdapterError, AttemptError, FinalReportError, H1Error, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
