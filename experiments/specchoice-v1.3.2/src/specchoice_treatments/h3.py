# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Decision-free H3 Red readiness for the closed offline treatment boundary."""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
from collections.abc import Mapping
from pathlib import Path

from specchoice_data.h2 import (
    H2ValidationError,
    audit_phase3_counts_v1,
    derive_data_eligibility_v1,
    validate_phase3_chain_v1,
    validate_phase3_data_authority_v1,
)
from specchoice_data.schema import DataSchemaError, require_canonical_utc
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import (
    FilesystemPolicyError,
    enumerate_authoritative_files,
    read_authoritative_file,
    write_exact_descriptor_files,
)
from specchoice_measurement.strict_json import decode_strict_json


class H3ValidationError(ValueError):
    """Stable failure for the H3 decision-free Red readiness boundary."""


_ACKNOWLEDGMENTS = (
    "phase3_red_authority",
    "offline_treatment_bundle",
    "test_only_retrieval_contract",
    "red_counts",
    "no_model_reachability",
    "h4_not_applicable",
    "change_control",
)
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "http",
        "urllib",
        "socket",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "google",
        "boto3",
        "keyring",
        "dotenv",
    }
)
_MACHINE_ONLY_FIELDS = frozenset(
    {
        "aggregate_disposition",
        "reviewer_id",
        "attestation",
        "signature",
        "rationale",
        "timestamp_utc",
    }
)
_PHASE3_ROOTS = (
    "phase3/data-authority-v1.json",
    "reports/h2/data-eligibility-v1.json",
    "reports/h2/h2-data-review-v1/review-packet.json",
    "receipts/h2-data-review-readiness-v1.json",
    "reviews/h2-data-decision-v1.json",
)
_TREATMENT_CONFIGS = (
    "config/treatments/delegation-frame-contract-v1.json",
    "config/treatments/frame-advisory-patterns-v1.json",
    "config/treatments/lexical-retrieval-contract-v1.json",
    "config/treatments/prompt-contract-v1.json",
)
_TREATMENT_FIXTURES = (
    "fixtures/treatments/contract-response-a-v1.json",
    "fixtures/treatments/contract-response-b-v1.json",
    "fixtures/treatments/contract-response-c-v1.json",
    "fixtures/treatments/frame-response-adversarial-v1.json",
    "fixtures/treatments/frame-response-b-valid-v1.json",
    "fixtures/treatments/frame-source-v1.txt",
    "fixtures/treatments/synthetic-complete-pairs-v1.json",
    "fixtures/treatments/synthetic-retrieval-receipt-v1.json",
    "fixtures/treatments/synthetic-target-v1.json",
)
_TREATMENT_PROMPTS = (
    "prompts/treatments/prompt-bundle-manifest-v1.json",
    "prompts/treatments/system-a-v1.txt",
    "prompts/treatments/system-b-v1.txt",
    "prompts/treatments/system-c-v1.txt",
)
_TREATMENT_SOURCES = (
    "src/specchoice_treatments/__init__.py",
    "src/specchoice_treatments/cli.py",
    "src/specchoice_treatments/h3.py",
    "src/specchoice_treatments/prompts.py",
    "src/specchoice_treatments/retrieval.py",
    "src/specchoice_treatments/schema.py",
)
_TREATMENT_TESTS = (
    "tests/test_treatments_frame.py",
    "tests/test_treatments_h3.py",
    "tests/test_treatments_prompts.py",
    "tests/test_treatments_retrieval.py",
)
_FROZEN_PATHS = tuple(
    sorted(
        {
            *_PHASE3_ROOTS,
            *_TREATMENT_CONFIGS,
            *_TREATMENT_FIXTURES,
            *_TREATMENT_PROMPTS,
            *_TREATMENT_SOURCES,
            *_TREATMENT_TESTS,
            "phase4/h3-v4-lifecycle-contract.md",
            "reports/h3/test-only-retrieval-contract-v1.json",
        }
    )
)


def _self_hash_valid(value: object, field: str) -> bool:
    return isinstance(value, Mapping) and value.get(field) == sha256_bytes(
        canonical_json_bytes({key: item for key, item in value.items() if key != field})
    )


def _load_canonical(root: Path, relative: str) -> tuple[dict[str, object], bytes]:
    try:
        _, raw = read_authoritative_file(root, relative)
        value = decode_strict_json(raw)
    except (FilesystemPolicyError, OSError, UnicodeDecodeError, ValueError) as error:
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    return value, raw


def _inventory(root: Path) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    try:
        observations = {path: read_authoritative_file(root, path) for path in _FROZEN_PATHS}
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID") from error
    records: list[dict[str, object]] = []
    raw_by_path: dict[str, bytes] = {}
    for path in _FROZEN_PATHS:
        evidence, raw = observations[path]
        if (
            evidence.file_kind != "regular_file"
            or evidence.hardlink_count != 1
            or evidence.sha256 is None
        ):
            raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
        records.append(
            {
                "byte_length": evidence.byte_length,
                "kind": evidence.file_kind,
                "path": evidence.path,
                "sha256": evidence.sha256,
            }
        )
        raw_by_path[path] = raw
    if [record["path"] for record in records] != sorted(record["path"] for record in records):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    return records, raw_by_path


def _require_phase3_red(
    *,
    chain: Mapping[str, object],
    authority: Mapping[str, object],
    eligibility: Mapping[str, object],
    decision: Mapping[str, object],
    raw_by_path: Mapping[str, bytes],
) -> dict[str, object]:
    try:
        audit = audit_phase3_counts_v1(chain)
        derived = derive_data_eligibility_v1(audit)
        if eligibility != derived:
            raise H3ValidationError("H3_PHASE3_RED_REQUIRED")
        validate_phase3_data_authority_v1(
            authority=authority,
            chain=chain,
            decision=decision,
            eligibility=eligibility,
        )
    except (H2ValidationError, KeyError, TypeError) as error:
        raise H3ValidationError("H3_PHASE3_RED_REQUIRED") from error
    required_false = (
        "retrieval_authorized",
        "model_execution_authorized",
        "external_publication_authorized",
    )
    if (
        eligibility.get("eligibility_status") != "red_required"
        or eligibility.get("qualifying_pair_count") != 1
        or eligibility.get("strict_case_count") != 0
        or eligibility.get("qualifying_pair_ids") != ["WARL_IMPLEMENTATION_SELECTED_VS_ISA_FIXED"]
        or eligibility.get("strict_case_ids") != []
        or any(
            eligibility.get(field) is not False
            for field in (
                "retrieval_authorized",
                "model_experiment_authorized",
                "external_publication_authorized",
            )
        )
        or authority.get("eligibility_status") != "red_required"
        or any(authority.get(field) is not False for field in required_false)
        or authority.get("phase4_decision_required") is not True
    ):
        raise H3ValidationError("H3_PHASE3_RED_REQUIRED")
    if not all(raw_by_path[path] for path in _PHASE3_ROOTS):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    return {
        "h2_decision_sha256": str(authority["h2_decision_sha256"]),
        "h2_packet_sha256": str(decision["packet_sha256"]),
        "h2_readiness_sha256": str(decision["readiness_sha256"]),
        "phase3_authority_sha256": str(authority["authority_sha256"]),
        "phase3_chain_sha256": str(chain["bindings"]["phase3_chain_sha256"]),
        "phase3_eligibility_report_sha256": str(eligibility["report_sha256"]),
    }


def load_phase4_freeze_inputs_v1(*, experiment_root: Path | None = None) -> dict[str, object]:
    """Reopen the full predecessor Red chain and every frozen treatment input."""
    root = experiment_root or Path(__file__).resolve().parents[2]
    inventory, raw_by_path = _inventory(root)
    try:
        chain = validate_phase3_chain_v1(experiment_root=root)
        authority, _ = _load_canonical(root, "phase3/data-authority-v1.json")
        eligibility, _ = _load_canonical(root, "reports/h2/data-eligibility-v1.json")
        _, decision_raw = _load_canonical(root, "reviews/h2-data-decision-v1.json")
        decision = decode_strict_json(decision_raw)
        if not isinstance(decision, dict):
            raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
        phase3_bindings = _require_phase3_red(
            chain=chain,
            authority=authority,
            eligibility=eligibility,
            decision=decision,
            raw_by_path=raw_by_path,
        )
    except H3ValidationError:
        raise
    except (H2ValidationError, KeyError, TypeError, ValueError) as error:
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID") from error
    inventory_hash = sha256_bytes(canonical_json_bytes(inventory))
    return {
        "phase3_bindings": phase3_bindings,
        "phase3_chain": chain,
        "phase3_authority": authority,
        "phase3_eligibility": eligibility,
        "phase4_freeze_inventory": inventory,
        "freeze_inventory_sha256": inventory_hash,
        "_experiment_root": root,
        "raw_by_path": raw_by_path,
    }


def _forbidden_imports(raw: bytes, path: str) -> None:
    try:
        tree = ast.parse(raw.decode("utf-8"), filename=path)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise H3ValidationError("H3_FORBIDDEN_IMPORT") from error
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names = [node.module]
        for name in names:
            if name.split(".", 1)[0] in _FORBIDDEN_IMPORT_ROOTS:
                raise H3ValidationError("H3_FORBIDDEN_IMPORT")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"__import__", "eval", "exec"}:
                raise H3ValidationError("H3_FORBIDDEN_IMPORT")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "import_module",
                "reload",
            }:
                raise H3ValidationError("H3_FORBIDDEN_IMPORT")


def audit_no_model_reachability_v1(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Prove the treatment package has only its singleton offline verifier surface."""
    inventory = freeze_inputs.get("phase4_freeze_inventory")
    raw_by_path = freeze_inputs.get("raw_by_path")
    root = freeze_inputs.get("_experiment_root")
    if (
        not isinstance(inventory, list)
        or not isinstance(raw_by_path, Mapping)
        or not isinstance(root, Path)
    ):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    paths = [entry.get("path") for entry in inventory if isinstance(entry, Mapping)]
    if paths != sorted(_FROZEN_PATHS) or set(paths) != set(_FROZEN_PATHS):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    for path in _TREATMENT_SOURCES:
        raw = raw_by_path.get(path)
        if not isinstance(raw, bytes):
            raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
        _forbidden_imports(raw, path)
    from . import cli

    parser = cli.build_parser()
    commands = sorted(
        action.dest
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
        for _ in action.choices
    )
    command_names = sorted(
        name
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
        for name in action.choices
    )
    if commands != ["command"] or command_names != ["verify-retrieval-contract"]:
        raise H3ValidationError("H3_CLI_SURFACE_INVALID")
    parser.parse_args(
        [
            "verify-retrieval-contract",
            "--target",
            "fixtures/treatments/synthetic-target-v1.json",
            "--corpus",
            "fixtures/treatments/synthetic-complete-pairs-v1.json",
            "--config",
            "config/treatments/lexical-retrieval-contract-v1.json",
            "--prompt-manifest",
            "prompts/treatments/prompt-bundle-manifest-v1.json",
        ]
    )
    with contextlib.redirect_stderr(io.StringIO()):
        if cli.main(["model-run"]) != 2:
            raise H3ValidationError("H3_NETWORK_REACHABILITY_INVALID")
    try:
        all_paths = enumerate_authoritative_files(root)
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID") from error
    if any("h4" in path.lower() for path in all_paths):
        raise H3ValidationError("H3_H4_ARTIFACT_FORBIDDEN")
    treatment_paths = [
        path
        for path in all_paths
        if path.startswith(
            (
                "config/treatments/",
                "fixtures/treatments/",
                "prompts/treatments/",
                "src/specchoice_treatments/",
            )
        )
    ]
    if any(
        any(
            token in path.lower() for token in ("credential", "secret", "provider", "model", ".env")
        )
        for path in treatment_paths
    ):
        raise H3ValidationError("H3_CREDENTIAL_PATH_FORBIDDEN")
    payload = {
        "checks": {
            "cli_singleton": True,
            "forbidden_imports_absent": True,
            "h4_artifacts_absent": True,
            "runtime_success_parser_no_network": True,
            "runtime_unknown_command_no_network": True,
            "unsafe_config_and_credential_paths_absent": True,
        },
        "cli_commands": command_names,
        "forbidden_import_roots": sorted(_FORBIDDEN_IMPORT_ROOTS),
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v1/review-packet.json",
            "reports/h3/h3-red-review-v1/review-packet.md",
            "receipts/h3-branch-readiness-v1.json",
        ],
        "schema_version": "h3-no-model-reachability-v1",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v1(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Build the canonical decision-free H3 Red review packet."""
    bindings = freeze_inputs.get("phase3_bindings")
    inventory = freeze_inputs.get("phase4_freeze_inventory")
    inventory_hash = freeze_inputs.get("freeze_inventory_sha256")
    raw_by_path = freeze_inputs.get("raw_by_path")
    if (
        not isinstance(bindings, Mapping)
        or not isinstance(inventory, list)
        or not isinstance(inventory_hash, str)
        or not isinstance(raw_by_path, Mapping)
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    no_model = audit_no_model_reachability_v1(freeze_inputs)
    prompt_raw = raw_by_path.get("prompts/treatments/prompt-bundle-manifest-v1.json")
    retrieval_raw = raw_by_path.get("reports/h3/test-only-retrieval-contract-v1.json")
    if not isinstance(prompt_raw, bytes) or not isinstance(retrieval_raw, bytes):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": inventory_hash,
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        "phase3_bindings": dict(bindings),
        "phase4_freeze_inventory": inventory,
        "production_retrieval_authorized": False,
        "prompt_bundle_manifest_sha256": sha256_bytes(prompt_raw),
        "provider_config_present": False,
        "repeat_count": 0,
        "required_acknowledgment_categories": list(_ACKNOWLEDGMENTS),
        "retrieval_contract_report_sha256": sha256_bytes(retrieval_raw),
        "recovery_contract": {
            "disputed": "corrected upstream input requires a versioned regenerated successor chain",
            "incomplete": "a new immutable decision may bind unchanged readiness",
            "missing": "machine readiness is not branch authority",
        },
        "schema_version": "h3-red-review-packet-v1",
        "warning": "MACHINE READINESS ONLY; NOT BRANCH AUTHORITY",
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v1(packet: Mapping[str, object]) -> bytes:
    """Render Markdown exclusively from canonical packet JSON."""
    if not _self_hash_valid(packet, "packet_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        (
            b"# Phase 4 H3 Red Review\n\n"
            b"**MACHINE READINESS ONLY; NOT BRANCH AUTHORITY**\n\n"
            b"## Canonical packet\n\n```json\n"
        )
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v1(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    """Bind only decision-free H3 machine products and their exact roots."""
    rendered = render_h3_red_review_markdown_v1(packet)
    if markdown is None:
        markdown = rendered
    required = {
        "N_strict",
        "branch",
        "credentials_boundary",
        "external_calls_authorized",
        "freeze_inventory_sha256",
        "h4_reason",
        "h4_required",
        "markdown_sha256",
        "model_execution_authorized",
        "model_snapshot",
        "no_model_reachability_sha256",
        "packet_sha256",
        "phase3_authority_sha256",
        "production_retrieval_authorized",
        "provider_config_present",
        "readiness_sha256",
        "repeat_count",
        "schema_version",
        "status",
    }
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or markdown != rendered
        or any(field in packet for field in _MACHINE_ONLY_FIELDS)
        or packet.get("branch") != "red"
        or packet.get("N_strict") != 0
        or isinstance(packet.get("N_strict"), bool)
        or packet.get("repeat_count") != 0
        or isinstance(packet.get("repeat_count"), bool)
        or packet.get("h4_required") is not False
        or packet.get("h4_reason") != "not_applicable_red"
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or packet.get("model_snapshot") != "not_applicable_red"
        or packet.get("credentials_boundary") != "not_applicable_red"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    bindings = packet.get("phase3_bindings")
    if not isinstance(bindings, Mapping):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": bindings["phase3_authority_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v1",
        "status": "ready_for_human",
    }
    if set({**payload, "readiness_sha256": ""}) != required:
        raise H3ValidationError("H3_READINESS_INVALID")
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h3_red_readiness_v1(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    """Publish only exact-resume machine outputs; human decision and authority stay absent."""
    expected = build_h3_red_readiness_v1(packet, markdown)
    if dict(readiness) != expected or not _self_hash_valid(readiness, "readiness_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v1.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v1/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v1/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error


_V2_MACHINE_ONLY_FIELDS = _MACHINE_ONLY_FIELDS | frozenset({"acknowledgments"})


def _load_h3_v1_predecessor(*, root: Path) -> dict[str, object]:
    """Bind the immutable v1 decision as history, never as v2 authority."""
    packet, _ = _load_canonical(root, "reports/h3/h3-red-review-v1/review-packet.json")
    readiness, _ = _load_canonical(root, "receipts/h3-branch-readiness-v1.json")
    decision, _ = _load_canonical(root, "reviews/h3-branch-decision-v1.json")
    if (
        packet.get("schema_version") != "h3-red-review-packet-v1"
        or readiness.get("schema_version") != "h3-branch-readiness-v1"
        or decision.get("schema_version") != "h3-branch-decision-v1"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or not _self_hash_valid(decision, "decision_sha256")
        or decision.get("packet_sha256") != packet.get("packet_sha256")
        or decision.get("readiness_sha256") != readiness.get("readiness_sha256")
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    return {
        "decision_sha256": decision["decision_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "readiness_sha256": readiness["readiness_sha256"],
        "status": "historical_predecessor_not_authority",
    }


def load_phase4_freeze_inputs_v2(*, experiment_root: Path | None = None) -> dict[str, object]:
    """Recompute the successor freeze from completed authority code and tests."""
    inputs = load_phase4_freeze_inputs_v1(experiment_root=experiment_root)
    root = inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    return {**inputs, "predecessor_v1": _load_h3_v1_predecessor(root=root)}


def audit_no_model_reachability_v2(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Version the closed no-model audit with the successor output inventory."""
    audit = audit_no_model_reachability_v1(freeze_inputs)
    payload = {
        **{key: value for key, value in audit.items() if key != "no_model_reachability_sha256"},
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v2/review-packet.json",
            "reports/h3/h3-red-review-v2/review-packet.md",
            "receipts/h3-branch-readiness-v2.json",
        ],
        "schema_version": "h3-no-model-reachability-v2",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v2(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Build a decision-free v2 packet that explains why v1 cannot authorize it."""
    predecessor = freeze_inputs.get("predecessor_v1")
    if (
        not isinstance(predecessor, Mapping)
        or predecessor.get("status") != "historical_predecessor_not_authority"
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    v1_packet = build_h3_red_review_packet_v1(freeze_inputs)
    no_model = audit_no_model_reachability_v2(freeze_inputs)
    payload = {
        **{
            key: value
            for key, value in v1_packet.items()
            if key
            not in {
                "no_model_reachability",
                "no_model_reachability_sha256",
                "packet_sha256",
                "schema_version",
            }
        },
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        "predecessor_v1": dict(predecessor),
        "schema_version": "h3-red-review-packet-v2",
        "successor_rationale": (
            "v2 successor rationale: ordering conflict discovered because v1 readiness froze h3.py and "
            "tests before authority implementation and adversarial tests existed; v1 remains valid historical "
            "decision but cannot generate authority, while v2 freezes the completed implementation and tests "
            "before a new human decision."
        ),
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v2(packet: Mapping[str, object]) -> bytes:
    """Render the successor review projection only from its canonical packet."""
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or packet.get("schema_version") != "h3-red-review-packet-v2"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        (
            b"# Phase 4 H3 Red Successor Review v2\n\n"
            b"**MACHINE READINESS ONLY; NOT BRANCH AUTHORITY**\n\n"
            b"## Canonical packet\n\n```json\n"
        )
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v2(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    """Bind a machine-only v2 readiness root without reviewer-owned fields."""
    rendered = render_h3_red_review_markdown_v2(packet)
    if markdown is None:
        markdown = rendered
    if (
        markdown != rendered
        or any(field in packet for field in _V2_MACHINE_ONLY_FIELDS)
        or packet.get("branch") != "red"
        or isinstance(packet.get("N_strict"), bool)
        or packet.get("N_strict") != 0
        or isinstance(packet.get("repeat_count"), bool)
        or packet.get("repeat_count") != 0
        or packet.get("h4_required") is not False
        or packet.get("h4_reason") != "not_applicable_red"
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or packet.get("model_snapshot") != "not_applicable_red"
        or packet.get("credentials_boundary") != "not_applicable_red"
        or not isinstance(packet.get("phase3_bindings"), Mapping)
        or not isinstance(packet.get("predecessor_v1"), Mapping)
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": packet["phase3_bindings"]["phase3_authority_sha256"],
        "predecessor_v1_decision_sha256": packet["predecessor_v1"]["decision_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v2",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h3_red_readiness_v2(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    """Publish only the exact-resume, decision-free v2 machine review products."""
    expected = build_h3_red_readiness_v2(packet, markdown)
    if dict(readiness) != expected or not _self_hash_valid(readiness, "readiness_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v2.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v2/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v2/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error


def validate_h3_red_decision_v2(
    *,
    decision: object,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, object]:
    """Validate a future v2 human decision without treating v1 as interchangeable."""
    required = {
        "acknowledgments",
        "aggregate_disposition",
        "aggregate_rationale",
        "attestation",
        "decision_sha256",
        "packet_sha256",
        "readiness_sha256",
        "reviewer_id",
        "schema_version",
        "signature",
        "timestamp_utc",
    }
    if (
        not isinstance(decision, dict)
        or set(decision) != required
        or decision.get("schema_version") != "h3-branch-decision-v2"
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get(
        "readiness_sha256"
    ) != readiness.get("readiness_sha256"):
        raise H3ValidationError("H3_DECISION_BINDING_INVALID")
    if not _self_hash_valid(decision, "decision_sha256"):
        raise H3ValidationError("H3_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "H3_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise H3ValidationError(str(error)) from error
    aggregate = decision.get("aggregate_disposition")
    if aggregate not in {"approved_red", "disputed", "incomplete"}:
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    acknowledgments = decision.get("acknowledgments")
    expected = packet.get("required_acknowledgment_categories")
    if (
        not isinstance(acknowledgments, list)
        or [item.get("category") if isinstance(item, Mapping) else None for item in acknowledgments]
        != expected
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    for item in acknowledgments:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"category", "disposition", "rationale"}
            or item.get("disposition") not in {"approved", "disputed", "incomplete"}
            or not isinstance(item.get("rationale"), str)
            or not item["rationale"].strip()
        ):
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if aggregate == "approved_red" and any(
        item["disposition"] != "approved" for item in acknowledgments
    ):
        raise H3ValidationError("H3_DECISION_INCONSISTENT")
    return decision


def _require_current_v2_inputs(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    current = load_phase4_freeze_inputs_v2(experiment_root=root)
    for field in (
        "phase3_bindings",
        "phase4_freeze_inventory",
        "freeze_inventory_sha256",
        "predecessor_v1",
        "raw_by_path",
    ):
        if freeze_inputs.get(field) != current.get(field):
            raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    return current


def _freeze_root_v2(
    *, packet: Mapping[str, object], readiness: Mapping[str, object], decision: Mapping[str, object]
) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "decision_sha256": decision["decision_sha256"],
                "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
                "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
                "packet_sha256": packet["packet_sha256"],
                "phase3_authority_sha256": readiness["phase3_authority_sha256"],
                "readiness_sha256": readiness["readiness_sha256"],
            }
        )
    )


def build_h3_red_authority_v2(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Construct, but do not publish, authority from one exact fresh v2 approval."""
    current = _require_current_v2_inputs(freeze_inputs)
    expected_packet = build_h3_red_review_packet_v2(current)
    expected_readiness = build_h3_red_readiness_v2(expected_packet)
    if dict(packet) != expected_packet or dict(readiness) != expected_readiness:
        raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    validated_decision = validate_h3_red_decision_v2(
        decision=decision, packet=packet, readiness=readiness
    )
    if validated_decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "decision_sha256": validated_decision["decision_sha256"],
        "external_calls_authorized": False,
        "freeze_root_sha256": _freeze_root_v2(
            packet=packet, readiness=readiness, decision=validated_decision
        ),
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": readiness["phase3_authority_sha256"],
        "predecessor_v1_decision_sha256": readiness["predecessor_v1_decision_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "readiness_sha256": readiness["readiness_sha256"],
        "repeat_count": 0,
        "schema_version": "phase4-branch-authority-v2",
    }
    return {**payload, "authority_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_h3_red_authority_v2(
    *,
    authority: object,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: Mapping[str, object],
) -> dict[str, object]:
    """Validate a constructed v2 authority against the exact v2 decision chain."""
    required = {
        "N_strict",
        "authority_sha256",
        "branch",
        "credentials_boundary",
        "decision_sha256",
        "external_calls_authorized",
        "freeze_root_sha256",
        "h4_reason",
        "h4_required",
        "model_execution_authorized",
        "model_snapshot",
        "packet_sha256",
        "phase3_authority_sha256",
        "predecessor_v1_decision_sha256",
        "production_retrieval_authorized",
        "provider_config_present",
        "readiness_sha256",
        "repeat_count",
        "schema_version",
    }
    if (
        not isinstance(authority, dict)
        or set(authority) != required
        or authority.get("schema_version") != "phase4-branch-authority-v2"
        or not _self_hash_valid(authority, "authority_sha256")
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    if (
        authority.get("branch") != "red"
        or isinstance(authority.get("N_strict"), bool)
        or authority.get("N_strict") != 0
        or isinstance(authority.get("repeat_count"), bool)
        or authority.get("repeat_count") != 0
        or authority.get("h4_required") is not False
        or authority.get("h4_reason") != "not_applicable_red"
        or any(
            authority.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or authority.get("model_snapshot") != "not_applicable_red"
        or authority.get("credentials_boundary") != "not_applicable_red"
        or authority.get("packet_sha256") != packet.get("packet_sha256")
        or authority.get("readiness_sha256") != readiness.get("readiness_sha256")
        or authority.get("decision_sha256") != decision.get("decision_sha256")
        or authority.get("phase3_authority_sha256") != readiness.get("phase3_authority_sha256")
        or authority.get("predecessor_v1_decision_sha256")
        != readiness.get("predecessor_v1_decision_sha256")
        or authority.get("freeze_root_sha256")
        != _freeze_root_v2(packet=packet, readiness=readiness, decision=decision)
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return authority


def write_h3_red_authority_v2(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Publish v2 authority only after exact fresh approved_red validation."""
    authority = build_h3_red_authority_v2(
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision=decision,
    )
    validate_h3_red_authority_v2(
        authority=authority, packet=packet, readiness=readiness, decision=decision
    )
    try:
        write_exact_descriptor_files(
            output_root,
            {
                "phase4/branch-authority-v2.json": canonical_json_bytes(authority),
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID") from error
    return authority


def _historical_identity(
    *, path: str, raw: bytes, value: Mapping[str, object], self_hash_field: str
) -> dict[str, object]:
    """Describe one validated immutable predecessor without making it current authority."""
    self_hash = value.get(self_hash_field)
    if not isinstance(self_hash, str) or not _self_hash_valid(value, self_hash_field):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    return {
        "path": path,
        "raw_sha256": sha256_bytes(raw),
        "schema_version": value.get("schema_version"),
        "self_sha256": self_hash,
    }


def _load_h3_v1_historical_predecessor(*, root: Path) -> dict[str, object]:
    """Revalidate the v1 decision as immutable history for the v3 successor."""
    decision, decision_raw = _load_canonical(root, "reviews/h3-branch-decision-v1.json")
    if decision.get("schema_version") != "h3-branch-decision-v1":
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    return {
        "decision": _historical_identity(
            path="reviews/h3-branch-decision-v1.json",
            raw=decision_raw,
            value=decision,
            self_hash_field="decision_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def _load_h3_v2_historical_predecessor(*, root: Path) -> dict[str, object]:
    """Revalidate v2's complete historical chain without reopening it as current authority."""
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v2/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v2.json")
    decision, decision_raw = _load_canonical(root, "reviews/h3-branch-decision-v2.json")
    authority, authority_raw = _load_canonical(root, "phase4/branch-authority-v2.json")
    if (
        packet.get("schema_version") != "h3-red-review-packet-v2"
        or readiness.get("schema_version") != "h3-branch-readiness-v2"
        or decision.get("schema_version") != "h3-branch-decision-v2"
        or authority.get("schema_version") != "phase4-branch-authority-v2"
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    validate_h3_red_decision_v2(decision=decision, packet=packet, readiness=readiness)
    validate_h3_red_authority_v2(
        authority=authority, packet=packet, readiness=readiness, decision=decision
    )
    return {
        "authority": _historical_identity(
            path="phase4/branch-authority-v2.json",
            raw=authority_raw,
            value=authority,
            self_hash_field="authority_sha256",
        ),
        "decision": _historical_identity(
            path="reviews/h3-branch-decision-v2.json",
            raw=decision_raw,
            value=decision,
            self_hash_field="decision_sha256",
        ),
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v2/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v2.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def load_phase4_freeze_inputs_v3(*, experiment_root: Path | None = None) -> dict[str, object]:
    """Freeze the completed lifecycle fix while retaining v1/v2 only as history."""
    inputs = load_phase4_freeze_inputs_v1(experiment_root=experiment_root)
    root = inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    return {
        **inputs,
        "predecessor_v1": _load_h3_v1_historical_predecessor(root=root),
        "predecessor_v2": _load_h3_v2_historical_predecessor(root=root),
    }


def audit_no_model_reachability_v3(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Version the no-model audit for the v3 machine-only successor products."""
    audit = audit_no_model_reachability_v1(freeze_inputs)
    payload = {
        **{key: value for key, value in audit.items() if key != "no_model_reachability_sha256"},
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v3/review-packet.json",
            "reports/h3/h3-red-review-v3/review-packet.md",
            "receipts/h3-branch-readiness-v3.json",
        ],
        "schema_version": "h3-no-model-reachability-v3",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v3(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Build a v3 machine packet that binds v1/v2 history but grants no authority."""
    predecessor_v1 = freeze_inputs.get("predecessor_v1")
    predecessor_v2 = freeze_inputs.get("predecessor_v2")
    if (
        not isinstance(predecessor_v1, Mapping)
        or not isinstance(predecessor_v2, Mapping)
        or predecessor_v1.get("status") != "historical_predecessor_not_current_authority"
        or predecessor_v2.get("status") != "historical_predecessor_not_current_authority"
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    v1_packet = build_h3_red_review_packet_v1(freeze_inputs)
    no_model = audit_no_model_reachability_v3(freeze_inputs)
    payload = {
        **{
            key: value
            for key, value in v1_packet.items()
            if key
            not in {
                "no_model_reachability",
                "no_model_reachability_sha256",
                "packet_sha256",
                "schema_version",
            }
        },
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        "predecessor_v1": dict(predecessor_v1),
        "predecessor_v2": dict(predecessor_v2),
        "schema_version": "h3-red-review-packet-v3",
        "successor_rationale": (
            "v3 successor rationale: v2 decision and authority remain historically valid under their bound evidence, "
            "but the frozen tests rejected the legitimate authority-present lifecycle state and Ruff reported F401, "
            "so v2 cannot serve as complete Phase 4 closure. v3 fixes only lifecycle tests and static checking; "
            "it does not change Red semantics, counts, or permission boundaries."
        ),
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v3(packet: Mapping[str, object]) -> bytes:
    """Render the v3 review projection exclusively from the canonical packet."""
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or packet.get("schema_version") != "h3-red-review-packet-v3"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        (
            b"# Phase 4 H3 Red Successor Review v3\n\n"
            b"**MACHINE READINESS ONLY; V3 HUMAN DECISION REQUIRED BEFORE ANY AUTHORITY**\n\n"
            b"## Canonical packet\n\n```json\n"
        )
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v3(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    """Bind only v3 machine products and immutable predecessor identities."""
    rendered = render_h3_red_review_markdown_v3(packet)
    if markdown is None:
        markdown = rendered
    predecessor_v1 = packet.get("predecessor_v1")
    predecessor_v2 = packet.get("predecessor_v2")
    if (
        markdown != rendered
        or any(field in packet for field in _V2_MACHINE_ONLY_FIELDS)
        or packet.get("branch") != "red"
        or isinstance(packet.get("N_strict"), bool)
        or packet.get("N_strict") != 0
        or isinstance(packet.get("repeat_count"), bool)
        or packet.get("repeat_count") != 0
        or packet.get("h4_required") is not False
        or packet.get("h4_reason") != "not_applicable_red"
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or packet.get("model_snapshot") != "not_applicable_red"
        or packet.get("credentials_boundary") != "not_applicable_red"
        or not isinstance(packet.get("phase3_bindings"), Mapping)
        or not isinstance(predecessor_v1, Mapping)
        or not isinstance(predecessor_v2, Mapping)
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "historical_predecessors": {"v1": dict(predecessor_v1), "v2": dict(predecessor_v2)},
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": packet["phase3_bindings"]["phase3_authority_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v3",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h3_red_readiness_v3(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    """Publish exact v3 machine evidence and deliberately no decision or authority leaf."""
    expected = build_h3_red_readiness_v3(packet, markdown)
    if dict(readiness) != expected or not _self_hash_valid(readiness, "readiness_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v3.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v3/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v3/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error


_V4_DECISION_FIELDS = frozenset(
    {
        "acknowledgments",
        "aggregate_disposition",
        "aggregate_rationale",
        "attestation",
        "decision_sha256",
        "packet_sha256",
        "readiness_sha256",
        "reviewer_id",
        "schema_version",
        "signature",
        "timestamp_utc",
    }
)
_V4_AUTHORITY_FIELDS = frozenset(
    {
        "N_strict",
        "authority_sha256",
        "branch",
        "credentials_boundary",
        "decision_sha256",
        "external_calls_authorized",
        "freeze_root_sha256",
        "h4_reason",
        "h4_required",
        "model_execution_authorized",
        "model_snapshot",
        "packet_sha256",
        "phase3_authority_sha256",
        "predecessor_v1_decision_sha256",
        "predecessor_v2_authority_sha256",
        "predecessor_v2_decision_sha256",
        "predecessor_v3_packet_sha256",
        "predecessor_v3_readiness_sha256",
        "production_retrieval_authorized",
        "provider_config_present",
        "readiness_sha256",
        "repeat_count",
        "schema_version",
    }
)
_V4_DECISION_PATH = "reviews/h3-branch-decision-v4.json"
_V4_AUTHORITY_PATH = "phase4/branch-authority-v4.json"
_V3_APPROVAL_EVIDENCE_PATH = "fixtures/h3/h3-v3-human-approval-source.txt"


def _load_h3_v1_historical_chain(*, root: Path) -> dict[str, object]:
    """Bind v1's valid decision as immutable history and never as current authority."""
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v1/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v1.json")
    decision, decision_raw = _load_canonical(root, "reviews/h3-branch-decision-v1.json")
    if (
        packet.get("schema_version") != "h3-red-review-packet-v1"
        or readiness.get("schema_version") != "h3-branch-readiness-v1"
        or decision.get("schema_version") != "h3-branch-decision-v1"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or not _self_hash_valid(decision, "decision_sha256")
        or decision.get("packet_sha256") != packet.get("packet_sha256")
        or decision.get("readiness_sha256") != readiness.get("readiness_sha256")
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    return {
        "decision": _historical_identity(
            path="reviews/h3-branch-decision-v1.json",
            raw=decision_raw,
            value=decision,
            self_hash_field="decision_sha256",
        ),
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v1/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v1.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def _load_h3_v3_historical_predecessor(*, root: Path, approval_source: Path) -> dict[str, object]:
    """Bind v3 machine evidence and its external human-source identity without inventing a leaf."""
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v3/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v3.json")
    try:
        approval_raw = approval_source.read_bytes()
    except OSError as error:
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID") from error
    if (
        packet.get("schema_version") != "h3-red-review-packet-v3"
        or readiness.get("schema_version") != "h3-branch-readiness-v3"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or readiness.get("packet_sha256") != packet.get("packet_sha256")
        or (root / "reviews/h3-branch-decision-v3.json").exists()
        or (root / "phase4/branch-authority-v3.json").exists()
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    return {
        "decision_status": "no_persisted_v3_decision_artifact",
        "human_approval_source": {
            "byte_length": len(approval_raw),
            "kind": "historical_user_approval_source",
            "raw_sha256": sha256_bytes(approval_raw),
            "source_locator": "codex-attachment:b0c0b467-0d6c-405a-8c3b-2b9afe4b678a/pasted-text.txt",
        },
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v3/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v3.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def load_phase4_freeze_inputs_v4(
    *,
    experiment_root: Path | None = None,
    approval_source: Path | None = None,
) -> dict[str, object]:
    """Reopen the complete v4 predecessor chain before any v4 machine product is built."""
    inputs = load_phase4_freeze_inputs_v1(experiment_root=experiment_root)
    root = inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    source = approval_source or root / _V3_APPROVAL_EVIDENCE_PATH
    return {
        **inputs,
        "predecessor_v1": _load_h3_v1_historical_chain(root=root),
        "predecessor_v2": _load_h3_v2_historical_predecessor(root=root),
        "predecessor_v3": _load_h3_v3_historical_predecessor(root=root, approval_source=source),
    }


def audit_no_model_reachability_v4(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Version the no-model audit for v4's machine-only output paths."""
    audit = audit_no_model_reachability_v1(freeze_inputs)
    payload = {
        **{key: value for key, value in audit.items() if key != "no_model_reachability_sha256"},
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v4/review-packet.json",
            "reports/h3/h3-red-review-v4/review-packet.md",
            "receipts/h3-branch-readiness-v4.json",
        ],
        "schema_version": "h3-no-model-reachability-v4",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v4(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Build the v4 machine packet after all lifecycle code and tests are frozen."""
    predecessors = tuple(freeze_inputs.get(f"predecessor_v{version}") for version in (1, 2, 3))
    if any(
        not isinstance(item, Mapping)
        or item.get("status") != "historical_predecessor_not_current_authority"
        for item in predecessors
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    v1_packet = build_h3_red_review_packet_v1(freeze_inputs)
    no_model = audit_no_model_reachability_v4(freeze_inputs)
    payload = {
        **{
            key: value
            for key, value in v1_packet.items()
            if key
            not in {
                "no_model_reachability",
                "no_model_reachability_sha256",
                "packet_sha256",
                "schema_version",
            }
        },
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        "predecessor_v1": dict(predecessors[0]),
        "predecessor_v2": dict(predecessors[1]),
        "predecessor_v3": dict(predecessors[2]),
        "schema_version": "h3-red-review-packet-v4",
        "successor_rationale": (
            "v4 successor rationale: v3 roots and the attached human approval remain valid historical evidence, "
            "but v3 inventory did not include the final decision/authority publication lifecycle and therefore "
            "cannot safely close that lifecycle. v4 freezes the complete lifecycle before its new decision only; "
            "it does not change Red semantics, N_strict=0, repeat_count=0, or permission boundaries."
        ),
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v4(packet: Mapping[str, object]) -> bytes:
    """Render v4 Markdown only from its canonical machine packet."""
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or packet.get("schema_version") != "h3-red-review-packet-v4"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        (
            b"# Phase 4 H3 Red Successor Review v4\n\n"
            b"**MACHINE READINESS ONLY; V4 HUMAN DECISION REQUIRED BEFORE ANY AUTHORITY**\n\n"
            b"## Canonical packet\n\n```json\n"
        )
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v4(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    """Bind v4's decision-free packet, lifecycle inventory, and predecessor identities."""
    rendered = render_h3_red_review_markdown_v4(packet)
    if markdown is None:
        markdown = rendered
    predecessors = tuple(packet.get(f"predecessor_v{version}") for version in (1, 2, 3))
    if (
        markdown != rendered
        or any(field in packet for field in _V2_MACHINE_ONLY_FIELDS)
        or packet.get("branch") != "red"
        or isinstance(packet.get("N_strict"), bool)
        or packet.get("N_strict") != 0
        or isinstance(packet.get("repeat_count"), bool)
        or packet.get("repeat_count") != 0
        or packet.get("h4_required") is not False
        or packet.get("h4_reason") != "not_applicable_red"
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or packet.get("model_snapshot") != "not_applicable_red"
        or packet.get("credentials_boundary") != "not_applicable_red"
        or not isinstance(packet.get("phase3_bindings"), Mapping)
        or any(not isinstance(item, Mapping) for item in predecessors)
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "historical_predecessors": {
            str(version): dict(predecessors[version - 1]) for version in (1, 2, 3)
        },
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": packet["phase3_bindings"]["phase3_authority_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v4",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h3_red_readiness_v4(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    """Publish only exact v4 machine products; decision and authority remain excluded outputs."""
    expected = build_h3_red_readiness_v4(packet, markdown)
    if dict(readiness) != expected or not _self_hash_valid(readiness, "readiness_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v4.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v4/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v4/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error


def validate_h3_red_decision_v4(
    *,
    decision: object,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, object]:
    """Validate the closed v4 human-decision schema without inferring an approval."""
    if (
        not isinstance(decision, dict)
        or set(decision) != _V4_DECISION_FIELDS
        or decision.get("schema_version") != "h3-branch-decision-v4"
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if decision.get("packet_sha256") != packet.get("packet_sha256") or decision.get(
        "readiness_sha256"
    ) != readiness.get("readiness_sha256"):
        raise H3ValidationError("H3_DECISION_BINDING_INVALID")
    if not _self_hash_valid(decision, "decision_sha256"):
        raise H3ValidationError("H3_DECISION_HASH_INVALID")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "H3_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise H3ValidationError(str(error)) from error
    aggregate = decision.get("aggregate_disposition")
    if aggregate not in {"approved_red", "disputed", "incomplete"}:
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    acknowledgments = decision.get("acknowledgments")
    expected = packet.get("required_acknowledgment_categories")
    if (
        not isinstance(acknowledgments, list)
        or [item.get("category") if isinstance(item, Mapping) else None for item in acknowledgments]
        != expected
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    for item in acknowledgments:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"category", "disposition", "rationale"}
            or item.get("disposition") not in {"approved", "disputed", "incomplete"}
            or not isinstance(item.get("rationale"), str)
            or not item["rationale"].strip()
        ):
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if aggregate == "approved_red" and any(
        item["disposition"] != "approved" for item in acknowledgments
    ):
        raise H3ValidationError("H3_DECISION_INCONSISTENT")
    return decision


def build_h3_red_decision_v4(
    *,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    acknowledgments: list[dict[str, str]],
    aggregate_disposition: str,
    aggregate_rationale: str,
    reviewer_id: str,
    attestation: str,
    signature: str,
    timestamp_utc: str,
) -> dict[str, object]:
    """Construct one human-owned v4 decision value; this function never writes a file."""
    payload = {
        "acknowledgments": acknowledgments,
        "aggregate_disposition": aggregate_disposition,
        "aggregate_rationale": aggregate_rationale,
        "attestation": attestation,
        "packet_sha256": packet.get("packet_sha256"),
        "readiness_sha256": readiness.get("readiness_sha256"),
        "reviewer_id": reviewer_id,
        "schema_version": "h3-branch-decision-v4",
        "signature": signature,
        "timestamp_utc": timestamp_utc,
    }
    decision = {**payload, "decision_sha256": sha256_bytes(canonical_json_bytes(payload))}
    return validate_h3_red_decision_v4(decision=decision, packet=packet, readiness=readiness)


def write_h3_red_decision_v4(
    *,
    output_root: Path,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Publish or exact-resume the single v4 decision leaf without authority side effects."""
    validated = validate_h3_red_decision_v4(decision=decision, packet=packet, readiness=readiness)
    try:
        write_exact_descriptor_files(
            output_root, {_V4_DECISION_PATH: canonical_json_bytes(validated)}
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_DECISION_WRITE_INVALID") from error
    return validated


def _require_current_v4_inputs(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    current = load_phase4_freeze_inputs_v4(experiment_root=root)
    for field in (
        "phase3_bindings",
        "phase4_freeze_inventory",
        "freeze_inventory_sha256",
        "predecessor_v1",
        "predecessor_v2",
        "predecessor_v3",
        "raw_by_path",
    ):
        if freeze_inputs.get(field) != current.get(field):
            raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    return current


def _freeze_root_v4(
    *, packet: Mapping[str, object], readiness: Mapping[str, object], decision: Mapping[str, object]
) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "decision_sha256": decision["decision_sha256"],
                "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
                "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
                "packet_sha256": packet["packet_sha256"],
                "phase3_authority_sha256": readiness["phase3_authority_sha256"],
                "predecessor_v1_decision_sha256": packet["predecessor_v1"]["decision"][
                    "self_sha256"
                ],
                "predecessor_v2_authority_sha256": packet["predecessor_v2"]["authority"][
                    "self_sha256"
                ],
                "predecessor_v2_decision_sha256": packet["predecessor_v2"]["decision"][
                    "self_sha256"
                ],
                "predecessor_v3_packet_sha256": packet["predecessor_v3"]["packet"]["self_sha256"],
                "predecessor_v3_readiness_sha256": packet["predecessor_v3"]["readiness"][
                    "self_sha256"
                ],
                "readiness_sha256": readiness["readiness_sha256"],
            }
        )
    )


def build_h3_red_authority_v4(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Construct, but do not publish, a v4 authority from one exact current approval."""
    current = _require_current_v4_inputs(freeze_inputs)
    expected_packet = build_h3_red_review_packet_v4(current)
    expected_readiness = build_h3_red_readiness_v4(expected_packet)
    if dict(packet) != expected_packet or dict(readiness) != expected_readiness:
        raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    if not isinstance(decision, Mapping):
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    validated_decision = validate_h3_red_decision_v4(
        decision=decision, packet=packet, readiness=readiness
    )
    if validated_decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "decision_sha256": validated_decision["decision_sha256"],
        "external_calls_authorized": False,
        "freeze_root_sha256": _freeze_root_v4(
            packet=packet, readiness=readiness, decision=validated_decision
        ),
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": readiness["phase3_authority_sha256"],
        "predecessor_v1_decision_sha256": packet["predecessor_v1"]["decision"]["self_sha256"],
        "predecessor_v2_authority_sha256": packet["predecessor_v2"]["authority"]["self_sha256"],
        "predecessor_v2_decision_sha256": packet["predecessor_v2"]["decision"]["self_sha256"],
        "predecessor_v3_packet_sha256": packet["predecessor_v3"]["packet"]["self_sha256"],
        "predecessor_v3_readiness_sha256": packet["predecessor_v3"]["readiness"]["self_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "readiness_sha256": readiness["readiness_sha256"],
        "repeat_count": 0,
        "schema_version": "phase4-branch-authority-v4",
    }
    return {**payload, "authority_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_h3_red_authority_v4(
    *,
    authority: object,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: Mapping[str, object],
) -> dict[str, object]:
    """Validate v4 authority against the exact machine and human roots."""
    if (
        not isinstance(authority, dict)
        or set(authority) != _V4_AUTHORITY_FIELDS
        or authority.get("schema_version") != "phase4-branch-authority-v4"
        or not _self_hash_valid(authority, "authority_sha256")
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    expected_values = {
        "branch": "red",
        "N_strict": 0,
        "repeat_count": 0,
        "h4_required": False,
        "h4_reason": "not_applicable_red",
        "provider_config_present": False,
        "external_calls_authorized": False,
        "production_retrieval_authorized": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "credentials_boundary": "not_applicable_red",
        "packet_sha256": packet.get("packet_sha256"),
        "readiness_sha256": readiness.get("readiness_sha256"),
        "decision_sha256": decision.get("decision_sha256"),
        "phase3_authority_sha256": readiness.get("phase3_authority_sha256"),
        "predecessor_v1_decision_sha256": packet.get("predecessor_v1", {})
        .get("decision", {})
        .get("self_sha256"),
        "predecessor_v2_authority_sha256": packet.get("predecessor_v2", {})
        .get("authority", {})
        .get("self_sha256"),
        "predecessor_v2_decision_sha256": packet.get("predecessor_v2", {})
        .get("decision", {})
        .get("self_sha256"),
        "predecessor_v3_packet_sha256": packet.get("predecessor_v3", {})
        .get("packet", {})
        .get("self_sha256"),
        "predecessor_v3_readiness_sha256": packet.get("predecessor_v3", {})
        .get("readiness", {})
        .get("self_sha256"),
        "freeze_root_sha256": _freeze_root_v4(
            packet=packet, readiness=readiness, decision=decision
        ),
    }
    if (
        isinstance(authority.get("N_strict"), bool)
        or isinstance(authority.get("repeat_count"), bool)
        or any(authority.get(field) != expected for field, expected in expected_values.items())
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return authority


def write_h3_red_authority_v4(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Publish or exact-resume only the single fully validated v4 authority leaf."""
    authority = build_h3_red_authority_v4(
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision=decision,
    )
    validate_h3_red_authority_v4(
        authority=authority, packet=packet, readiness=readiness, decision=decision
    )
    try:
        write_exact_descriptor_files(
            output_root, {_V4_AUTHORITY_PATH: canonical_json_bytes(authority)}
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID") from error
    return authority


def validate_h3_v4_pre_publication_lifecycle(
    *,
    experiment_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Require that frozen v4 machine roots precede both post-decision output leaves."""
    current = _require_current_v4_inputs(freeze_inputs)
    if (
        dict(packet) != build_h3_red_review_packet_v4(current)
        or dict(readiness) != build_h3_red_readiness_v4(packet)
        or (experiment_root / _V4_DECISION_PATH).exists()
        or (experiment_root / _V4_AUTHORITY_PATH).exists()
    ):
        raise H3ValidationError("H3_PRE_PUBLICATION_LIFECYCLE_INVALID")
    return {"state": "pre_publication"}


def validate_h3_v4_decision_published_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Validate the approved-decision/no-authority lifecycle state without assuming machine roots are absent."""
    try:
        decision, _ = _load_canonical(output_root, _V4_DECISION_PATH)
    except H3ValidationError as error:
        raise H3ValidationError("H3_DECISION_PUBLICATION_LIFECYCLE_INVALID") from error
    current = _require_current_v4_inputs(freeze_inputs)
    if (
        dict(packet) != build_h3_red_review_packet_v4(current)
        or dict(readiness) != build_h3_red_readiness_v4(packet)
        or (output_root / _V4_AUTHORITY_PATH).exists()
    ):
        raise H3ValidationError("H3_DECISION_PUBLICATION_LIFECYCLE_INVALID")
    validate_h3_red_decision_v4(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    return {"state": "decision_published_authority_absent"}


def validate_h3_v4_post_publication_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Require exact canonical decision and authority leaves after publication without path-absence assumptions."""
    try:
        decision, _ = _load_canonical(output_root, _V4_DECISION_PATH)
        authority, _ = _load_canonical(output_root, _V4_AUTHORITY_PATH)
    except H3ValidationError as error:
        raise H3ValidationError("H3_POST_PUBLICATION_LIFECYCLE_INVALID") from error
    current = _require_current_v4_inputs(freeze_inputs)
    if dict(packet) != build_h3_red_review_packet_v4(current) or dict(
        readiness
    ) != build_h3_red_readiness_v4(packet):
        raise H3ValidationError("H3_POST_PUBLICATION_LIFECYCLE_INVALID")
    validate_h3_red_decision_v4(decision=decision, packet=packet, readiness=readiness)
    validate_h3_red_authority_v4(
        authority=authority, packet=packet, readiness=readiness, decision=decision
    )
    return {"state": "post_publication"}


# V5 deliberately does not modify the v1--v4 records above.  It freezes a new
# lifecycle whose only mutable names are the two declared v5 publication leaves.
_V5_DECISION_FIELDS = _V4_DECISION_FIELDS
_V5_AUTHORITY_FIELDS = _V4_AUTHORITY_FIELDS | frozenset(
    {
        "decision_raw_sha256",
        "predecessor_v4_authority_sha256",
        "predecessor_v4_decision_sha256",
    }
)
_V5_DECISION_PATH = "reviews/h3-branch-decision-v5.json"
_V5_AUTHORITY_PATH = "phase4/branch-authority-v5.json"
_V3_APPROVAL_SOURCE_LOCATOR = (
    "codex-attachment:b0c0b467-0d6c-405a-8c3b-2b9afe4b678a/pasted-text.txt"
)
_V3_APPROVAL_SOURCE_SHA256 = "d98fc8967cdba51283924b457c6b24a3f3dde540cd997867eea748b787e606cc"
_V3_APPROVAL_SOURCE_LENGTH = 6227
_FROZEN_PATHS_V5 = tuple(
    sorted(
        {
            *_FROZEN_PATHS,
            _V3_APPROVAL_EVIDENCE_PATH,
            "phase4/h3-v5-lifecycle-contract.md",
        }
    )
)


def _inventory_v5(root: Path) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    """Freeze v5-only inputs without recalculating any historical inventory."""
    try:
        observations = {path: read_authoritative_file(root, path) for path in _FROZEN_PATHS_V5}
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID") from error
    records: list[dict[str, object]] = []
    raw_by_path: dict[str, bytes] = {}
    for path in _FROZEN_PATHS_V5:
        evidence, raw = observations[path]
        if (
            evidence.file_kind != "regular_file"
            or evidence.hardlink_count != 1
            or evidence.sha256 is None
        ):
            raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
        records.append(
            {
                "byte_length": evidence.byte_length,
                "kind": evidence.file_kind,
                "path": evidence.path,
                "sha256": evidence.sha256,
            }
        )
        raw_by_path[path] = raw
    return records, raw_by_path


def _require_absent_authoritative_leaf(root: Path, relative: str, code: str) -> None:
    """Only a descriptor-proven ENOENT represents an unoccupied protected leaf."""
    try:
        read_authoritative_file(root, relative)
    except FilesystemPolicyError as error:
        if str(error) == "AUTHORITATIVE_FILE_MISSING":
            return
        raise H3ValidationError(code) from error
    raise H3ValidationError(code)


def _read_v5_leaf_or_absent(root: Path, relative: str) -> bytes | None:
    """Return an exact regular leaf or distinguish every occupied unsafe path."""
    try:
        _, raw = read_authoritative_file(root, relative)
        return raw
    except FilesystemPolicyError as error:
        if str(error) == "AUTHORITATIVE_FILE_MISSING":
            return None
        raise H3ValidationError("H3_PUBLICATION_PATH_INVALID") from error


def _decode_v5_canonical(raw: bytes, *, code: str) -> dict[str, object]:
    try:
        value = decode_strict_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise H3ValidationError(code) from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise H3ValidationError(code)
    return value


def _load_h3_v3_local_historical_predecessor(*, root: Path) -> dict[str, object]:
    """Bind the original v3 approval bytes stored locally without inventing a v3 leaf."""
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v3/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v3.json")
    try:
        _, approval_raw = read_authoritative_file(root, _V3_APPROVAL_EVIDENCE_PATH)
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID") from error
    _require_absent_authoritative_leaf(
        root, "reviews/h3-branch-decision-v3.json", "H3_PREDECESSOR_CHAIN_INVALID"
    )
    _require_absent_authoritative_leaf(
        root, "phase4/branch-authority-v3.json", "H3_PREDECESSOR_CHAIN_INVALID"
    )
    if (
        packet.get("schema_version") != "h3-red-review-packet-v3"
        or readiness.get("schema_version") != "h3-branch-readiness-v3"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or readiness.get("packet_sha256") != packet.get("packet_sha256")
        or len(approval_raw) != _V3_APPROVAL_SOURCE_LENGTH
        or sha256_bytes(approval_raw) != _V3_APPROVAL_SOURCE_SHA256
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    return {
        "decision_status": "no_persisted_v3_decision_artifact",
        "human_approval_source": {
            "byte_length": len(approval_raw),
            "kind": "repository_local_historical_user_approval_source",
            "path": _V3_APPROVAL_EVIDENCE_PATH,
            "raw_sha256": sha256_bytes(approval_raw),
            "source_locator": _V3_APPROVAL_SOURCE_LOCATOR,
        },
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v3/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v3.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def _load_h3_v4_historical_predecessor(*, root: Path) -> dict[str, object]:
    """Validate the published v4 chain strictly as historical predecessor evidence."""
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v4/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v4.json")
    decision, decision_raw = _load_canonical(root, _V4_DECISION_PATH)
    authority, authority_raw = _load_canonical(root, _V4_AUTHORITY_PATH)
    if (
        packet.get("schema_version") != "h3-red-review-packet-v4"
        or readiness.get("schema_version") != "h3-branch-readiness-v4"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or readiness.get("packet_sha256") != packet.get("packet_sha256")
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    validate_h3_red_decision_v4(decision=decision, packet=packet, readiness=readiness)
    validate_h3_red_authority_v4(
        authority=authority, packet=packet, readiness=readiness, decision=decision
    )
    return {
        "authority": _historical_identity(
            path=_V4_AUTHORITY_PATH,
            raw=authority_raw,
            value=authority,
            self_hash_field="authority_sha256",
        ),
        "decision": _historical_identity(
            path=_V4_DECISION_PATH,
            raw=decision_raw,
            value=decision,
            self_hash_field="decision_sha256",
        ),
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v4/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v4.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_predecessor_not_current_authority",
    }


def load_phase4_freeze_inputs_v5(*, experiment_root: Path | None = None) -> dict[str, object]:
    """Open the portable v5 freeze without depending on an ambient attachment path."""
    root = experiment_root or Path(__file__).resolve().parents[2]
    base = load_phase4_freeze_inputs_v1(experiment_root=root)
    inventory, raw_by_path = _inventory_v5(root)
    return {
        **base,
        "phase4_freeze_inventory": inventory,
        "freeze_inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "raw_by_path": raw_by_path,
        "predecessor_v1": _load_h3_v1_historical_chain(root=root),
        "predecessor_v2": _load_h3_v2_historical_predecessor(root=root),
        "predecessor_v3": _load_h3_v3_local_historical_predecessor(root=root),
        "predecessor_v4": _load_h3_v4_historical_predecessor(root=root),
    }


def audit_no_model_reachability_v5(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Audit only the v5 machine outputs; the post-decision leaves stay excluded."""
    inventory = freeze_inputs.get("phase4_freeze_inventory")
    raw_by_path = freeze_inputs.get("raw_by_path")
    root = freeze_inputs.get("_experiment_root")
    if (
        not isinstance(inventory, list)
        or not isinstance(raw_by_path, Mapping)
        or not isinstance(root, Path)
    ):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    paths = [entry.get("path") for entry in inventory if isinstance(entry, Mapping)]
    if paths != sorted(_FROZEN_PATHS_V5) or set(paths) != set(_FROZEN_PATHS_V5):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    for path in _TREATMENT_SOURCES:
        raw = raw_by_path.get(path)
        if not isinstance(raw, bytes):
            raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
        _forbidden_imports(raw, path)
    from . import cli

    parser = cli.build_parser()
    commands = sorted(
        action.dest
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
        for _ in action.choices
    )
    command_names = sorted(
        name
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
        for name in action.choices
    )
    if commands != ["command"] or command_names != ["verify-retrieval-contract"]:
        raise H3ValidationError("H3_CLI_SURFACE_INVALID")
    parser.parse_args(
        [
            "verify-retrieval-contract",
            "--target",
            "fixtures/treatments/synthetic-target-v1.json",
            "--corpus",
            "fixtures/treatments/synthetic-complete-pairs-v1.json",
            "--config",
            "config/treatments/lexical-retrieval-contract-v1.json",
            "--prompt-manifest",
            "prompts/treatments/prompt-bundle-manifest-v1.json",
        ]
    )
    with contextlib.redirect_stderr(io.StringIO()):
        if cli.main(["model-run"]) != 2:
            raise H3ValidationError("H3_NETWORK_REACHABILITY_INVALID")
    try:
        all_paths = enumerate_authoritative_files(root)
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID") from error
    if any("h4" in path.lower() for path in all_paths):
        raise H3ValidationError("H3_H4_ARTIFACT_FORBIDDEN")
    treatment_paths = [
        path
        for path in all_paths
        if path.startswith(
            (
                "config/treatments/",
                "fixtures/treatments/",
                "prompts/treatments/",
                "src/specchoice_treatments/",
            )
        )
    ]
    if any(
        any(
            token in path.lower() for token in ("credential", "secret", "provider", "model", ".env")
        )
        for path in treatment_paths
    ):
        raise H3ValidationError("H3_CREDENTIAL_PATH_FORBIDDEN")
    payload = {
        "checks": {
            "cli_singleton": True,
            "forbidden_imports_absent": True,
            "h4_artifacts_absent": True,
            "runtime_success_parser_no_network": True,
            "runtime_unknown_command_no_network": True,
            "unsafe_config_and_credential_paths_absent": True,
        },
        "cli_commands": command_names,
        "forbidden_import_roots": sorted(_FORBIDDEN_IMPORT_ROOTS),
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v5/review-packet.json",
            "reports/h3/h3-red-review-v5/review-packet.md",
            "receipts/h3-branch-readiness-v5.json",
        ],
        "schema_version": "h3-no-model-reachability-v5",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v5(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    """Build the v5 machine-only packet after the full lifecycle is frozen."""
    predecessors = tuple(freeze_inputs.get(f"predecessor_v{version}") for version in (1, 2, 3, 4))
    if any(
        not isinstance(item, Mapping)
        or item.get("status") != "historical_predecessor_not_current_authority"
        for item in predecessors
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    bindings = freeze_inputs.get("phase3_bindings")
    inventory = freeze_inputs.get("phase4_freeze_inventory")
    inventory_hash = freeze_inputs.get("freeze_inventory_sha256")
    raw_by_path = freeze_inputs.get("raw_by_path")
    if (
        not isinstance(bindings, Mapping)
        or not isinstance(inventory, list)
        or not isinstance(inventory_hash, str)
        or not isinstance(raw_by_path, Mapping)
    ):
        raise H3ValidationError("H3_CHAIN_INPUT_INVALID")
    prompt_raw = raw_by_path.get("prompts/treatments/prompt-bundle-manifest-v1.json")
    retrieval_raw = raw_by_path.get("reports/h3/test-only-retrieval-contract-v1.json")
    if not isinstance(prompt_raw, bytes) or not isinstance(retrieval_raw, bytes):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    no_model = audit_no_model_reachability_v5(freeze_inputs)
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": inventory_hash,
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "phase3_bindings": dict(bindings),
        "phase4_freeze_inventory": inventory,
        "production_retrieval_authorized": False,
        "prompt_bundle_manifest_sha256": sha256_bytes(prompt_raw),
        "provider_config_present": False,
        "repeat_count": 0,
        "required_acknowledgment_categories": list(_ACKNOWLEDGMENTS),
        "retrieval_contract_report_sha256": sha256_bytes(retrieval_raw),
        "recovery_contract": {
            "disputed": "corrected upstream input requires a versioned regenerated successor chain",
            "incomplete": "a new immutable decision may bind unchanged readiness",
            "missing": "machine readiness is not branch authority",
        },
        "warning": "MACHINE READINESS ONLY; NOT BRANCH AUTHORITY",
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        "predecessor_v1": dict(predecessors[0]),
        "predecessor_v2": dict(predecessors[1]),
        "predecessor_v3": dict(predecessors[2]),
        "predecessor_v4": dict(predecessors[3]),
        "schema_version": "h3-red-review-packet-v5",
        "successor_rationale": (
            "v5 successor rationale: v4 roots, decision, and authority remain historically valid under their bound evidence, "
            "but v4's frozen pre-publication test incorrectly depended on authority absence in the real checkout and its "
            "publication writer did not force one persisted decision/authority state-machine binding, so v4 cannot provide "
            "complete Phase 4 closure. v5 fixes only test-state isolation, decision/authority publication consistency, symlink "
            "protection, and historical-attachment portability; it does not change Red semantics, N_strict=0, repeat_count=0, "
            "or any permission boundary."
        ),
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v5(packet: Mapping[str, object]) -> bytes:
    """Render v5 Markdown only from its canonical packet."""
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or packet.get("schema_version") != "h3-red-review-packet-v5"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        (
            b"# Phase 4 H3 Red Successor Review v5\n\n"
            b"**MACHINE READINESS ONLY; V5 HUMAN DECISION REQUIRED BEFORE ANY AUTHORITY**\n\n"
            b"## Canonical packet\n\n```json\n"
        )
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v5(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    """Bind the v5 machine-only roots before any v5 decision leaf exists."""
    rendered = render_h3_red_review_markdown_v5(packet)
    if markdown is None:
        markdown = rendered
    if (
        markdown != rendered
        or any(field in packet for field in _V2_MACHINE_ONLY_FIELDS)
        or packet.get("branch") != "red"
        or packet.get("N_strict") != 0
        or isinstance(packet.get("N_strict"), bool)
        or packet.get("repeat_count") != 0
        or isinstance(packet.get("repeat_count"), bool)
        or packet.get("h4_required") is not False
        or packet.get("h4_reason") != "not_applicable_red"
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
        or packet.get("model_snapshot") != "not_applicable_red"
        or packet.get("credentials_boundary") != "not_applicable_red"
        or not isinstance(packet.get("phase3_bindings"), Mapping)
        or any(
            not isinstance(packet.get(f"predecessor_v{version}"), Mapping)
            for version in (1, 2, 3, 4)
        )
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "historical_predecessors": {
            str(version): dict(packet[f"predecessor_v{version}"]) for version in (1, 2, 3, 4)
        },
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": packet["phase3_bindings"]["phase3_authority_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v5",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def write_h3_red_readiness_v5(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    """Publish only the declared machine-only v5 packet, Markdown, and readiness."""
    expected = build_h3_red_readiness_v5(packet, markdown)
    if dict(readiness) != expected or not _self_hash_valid(readiness, "readiness_sha256"):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v5.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v5/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v5/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error


def validate_h3_red_decision_v5(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object]
) -> dict[str, object]:
    """Validate the exact closed v5 decision schema without granting authority."""
    if (
        not isinstance(decision, dict)
        or set(decision) != _V5_DECISION_FIELDS
        or decision.get("schema_version") != "h3-branch-decision-v5"
        or decision.get("packet_sha256") != packet.get("packet_sha256")
        or decision.get("readiness_sha256") != readiness.get("readiness_sha256")
        or not _self_hash_valid(decision, "decision_sha256")
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "H3_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise H3ValidationError(str(error)) from error
    aggregate = decision.get("aggregate_disposition")
    if aggregate not in {"approved_red", "disputed", "incomplete"}:
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    acknowledgments = decision.get("acknowledgments")
    expected = packet.get("required_acknowledgment_categories")
    if (
        not isinstance(acknowledgments, list)
        or [item.get("category") if isinstance(item, Mapping) else None for item in acknowledgments]
        != expected
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    for item in acknowledgments:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"category", "disposition", "rationale"}
            or item.get("disposition") not in {"approved", "disputed", "incomplete"}
            or not isinstance(item.get("rationale"), str)
            or not item["rationale"].strip()
        ):
            raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if aggregate == "approved_red" and any(
        item["disposition"] != "approved" for item in acknowledgments
    ):
        raise H3ValidationError("H3_DECISION_INCONSISTENT")
    return decision


def build_h3_red_decision_v5(
    *,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    acknowledgments: list[dict[str, str]],
    aggregate_disposition: str,
    aggregate_rationale: str,
    reviewer_id: str,
    attestation: str,
    signature: str,
    timestamp_utc: str,
) -> dict[str, object]:
    """Construct a v5 human decision value; publication remains a separate state transition."""
    payload = {
        "acknowledgments": acknowledgments,
        "aggregate_disposition": aggregate_disposition,
        "aggregate_rationale": aggregate_rationale,
        "attestation": attestation,
        "packet_sha256": packet.get("packet_sha256"),
        "readiness_sha256": readiness.get("readiness_sha256"),
        "reviewer_id": reviewer_id,
        "schema_version": "h3-branch-decision-v5",
        "signature": signature,
        "timestamp_utc": timestamp_utc,
    }
    decision = {**payload, "decision_sha256": sha256_bytes(canonical_json_bytes(payload))}
    return validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)


def _require_current_v5_inputs(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    current = load_phase4_freeze_inputs_v5(experiment_root=root)
    for field in (
        "phase3_bindings",
        "phase4_freeze_inventory",
        "freeze_inventory_sha256",
        "predecessor_v1",
        "predecessor_v2",
        "predecessor_v3",
        "predecessor_v4",
        "raw_by_path",
    ):
        if freeze_inputs.get(field) != current.get(field):
            raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    return current


def _validate_v5_machine_roots(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, object]:
    current = _require_current_v5_inputs(freeze_inputs)
    expected_packet = build_h3_red_review_packet_v5(current)
    expected_readiness = build_h3_red_readiness_v5(expected_packet)
    if dict(packet) != expected_packet or dict(readiness) != expected_readiness:
        raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    return current


def _freeze_root_v5(
    *,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: Mapping[str, object],
    decision_raw: bytes,
) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "decision_raw_sha256": sha256_bytes(decision_raw),
                "decision_sha256": decision["decision_sha256"],
                "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
                "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
                "packet_sha256": packet["packet_sha256"],
                "phase3_authority_sha256": readiness["phase3_authority_sha256"],
                "predecessor_v1_decision_sha256": packet["predecessor_v1"]["decision"][
                    "self_sha256"
                ],
                "predecessor_v2_authority_sha256": packet["predecessor_v2"]["authority"][
                    "self_sha256"
                ],
                "predecessor_v2_decision_sha256": packet["predecessor_v2"]["decision"][
                    "self_sha256"
                ],
                "predecessor_v3_packet_sha256": packet["predecessor_v3"]["packet"]["self_sha256"],
                "predecessor_v3_readiness_sha256": packet["predecessor_v3"]["readiness"][
                    "self_sha256"
                ],
                "predecessor_v4_authority_sha256": packet["predecessor_v4"]["authority"][
                    "self_sha256"
                ],
                "predecessor_v4_decision_sha256": packet["predecessor_v4"]["decision"][
                    "self_sha256"
                ],
                "readiness_sha256": readiness["readiness_sha256"],
            }
        )
    )


def _build_h3_red_authority_v5_from_persisted_decision(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision_raw: bytes,
) -> dict[str, object]:
    """Construct authority only from descriptor-re-read decision bytes."""
    _validate_v5_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    decision = _decode_v5_canonical(decision_raw, code="H3_DECISION_PUBLICATION_LIFECYCLE_INVALID")
    validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "decision_raw_sha256": sha256_bytes(decision_raw),
        "decision_sha256": decision["decision_sha256"],
        "external_calls_authorized": False,
        "freeze_root_sha256": _freeze_root_v5(
            packet=packet, readiness=readiness, decision=decision, decision_raw=decision_raw
        ),
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": readiness["phase3_authority_sha256"],
        "predecessor_v1_decision_sha256": packet["predecessor_v1"]["decision"]["self_sha256"],
        "predecessor_v2_authority_sha256": packet["predecessor_v2"]["authority"]["self_sha256"],
        "predecessor_v2_decision_sha256": packet["predecessor_v2"]["decision"]["self_sha256"],
        "predecessor_v3_packet_sha256": packet["predecessor_v3"]["packet"]["self_sha256"],
        "predecessor_v3_readiness_sha256": packet["predecessor_v3"]["readiness"]["self_sha256"],
        "predecessor_v4_authority_sha256": packet["predecessor_v4"]["authority"]["self_sha256"],
        "predecessor_v4_decision_sha256": packet["predecessor_v4"]["decision"]["self_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "readiness_sha256": readiness["readiness_sha256"],
        "repeat_count": 0,
        "schema_version": "phase4-branch-authority-v5",
    }
    return {**payload, "authority_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_h3_red_authority_v5(
    *,
    authority: object,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: Mapping[str, object],
    decision_raw: bytes,
) -> dict[str, object]:
    """Validate that authority binds both raw and self identities of its decision."""
    if (
        not isinstance(authority, dict)
        or set(authority) != _V5_AUTHORITY_FIELDS
        or authority.get("schema_version") != "phase4-branch-authority-v5"
        or not _self_hash_valid(authority, "authority_sha256")
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    expected = _build_h3_red_authority_v5_from_persisted_decision(
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision_raw=decision_raw,
    )
    if (
        decision != _decode_v5_canonical(decision_raw, code="H3_AUTHORITY_INVALID")
        or dict(authority) != expected
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return authority


def write_h3_red_decision_v5(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Publish only an approved, exact v5 decision when authority is still absent."""
    _validate_v5_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    validated = validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)
    if validated.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    expected_raw = canonical_json_bytes(validated)
    current_decision = _read_v5_leaf_or_absent(output_root, _V5_DECISION_PATH)
    current_authority = _read_v5_leaf_or_absent(output_root, _V5_AUTHORITY_PATH)
    if current_authority is not None or (
        current_decision is not None and current_decision != expected_raw
    ):
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if current_decision is None:
        try:
            write_exact_descriptor_files(output_root, {_V5_DECISION_PATH: expected_raw})
        except (FilesystemPolicyError, OSError) as error:
            raise H3ValidationError("H3_DECISION_WRITE_INVALID") from error
        current_decision = _read_v5_leaf_or_absent(output_root, _V5_DECISION_PATH)
    if current_decision != expected_raw:
        raise H3ValidationError("H3_DECISION_WRITE_INVALID")
    return validated


def publish_h3_red_authority_v5(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    """Advance exactly one v5 publication state, deriving authority from the persisted decision only."""
    _validate_v5_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    requested = validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)
    if requested.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    expected_decision_raw = canonical_json_bytes(requested)
    current_decision = _read_v5_leaf_or_absent(output_root, _V5_DECISION_PATH)
    current_authority = _read_v5_leaf_or_absent(output_root, _V5_AUTHORITY_PATH)
    if current_authority is not None and current_decision is None:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if current_decision is not None and current_decision != expected_decision_raw:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if current_authority is not None:
        persisted = _decode_v5_canonical(current_decision, code="H3_PUBLICATION_STATE_INVALID")
        authority = _decode_v5_canonical(current_authority, code="H3_PUBLICATION_STATE_INVALID")
        validate_h3_red_authority_v5(
            authority=authority,
            freeze_inputs=freeze_inputs,
            packet=packet,
            readiness=readiness,
            decision=persisted,
            decision_raw=current_decision,
        )
        return authority
    if current_decision is None:
        write_h3_red_decision_v5(
            output_root=output_root,
            freeze_inputs=freeze_inputs,
            packet=packet,
            readiness=readiness,
            decision=requested,
        )
        current_decision = _read_v5_leaf_or_absent(output_root, _V5_DECISION_PATH)
    if current_decision != expected_decision_raw:
        raise H3ValidationError("H3_DECISION_WRITE_INVALID")
    authority = _build_h3_red_authority_v5_from_persisted_decision(
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision_raw=current_decision,
    )
    authority_raw = canonical_json_bytes(authority)
    try:
        write_exact_descriptor_files(output_root, {_V5_AUTHORITY_PATH: authority_raw})
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID") from error
    retained = _read_v5_leaf_or_absent(output_root, _V5_AUTHORITY_PATH)
    if retained != authority_raw:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID")
    return authority


def validate_h3_v5_publication_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Classify only the three allowed v5 publication states via no-follow reads."""
    _validate_v5_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    decision_raw = _read_v5_leaf_or_absent(output_root, _V5_DECISION_PATH)
    authority_raw = _read_v5_leaf_or_absent(output_root, _V5_AUTHORITY_PATH)
    if decision_raw is None and authority_raw is None:
        return {"state": "absent"}
    if decision_raw is None:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    decision = _decode_v5_canonical(decision_raw, code="H3_PUBLICATION_STATE_INVALID")
    validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    if authority_raw is None:
        return {"state": "decision_only_exact"}
    authority = _decode_v5_canonical(authority_raw, code="H3_PUBLICATION_STATE_INVALID")
    validate_h3_red_authority_v5(
        authority=authority,
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision=decision,
        decision_raw=decision_raw,
    )
    return {"state": "decision_and_authority_exact"}


def validate_h3_v5_pre_publication_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Require the explicit empty state in an isolated output root."""
    state = validate_h3_v5_publication_lifecycle(
        output_root=output_root,
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
    )
    if state != {"state": "absent"}:
        raise H3ValidationError("H3_PRE_PUBLICATION_LIFECYCLE_INVALID")
    return state


def validate_h3_v5_post_publication_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    """Require the fully exact state after the declared v5 publication."""
    state = validate_h3_v5_publication_lifecycle(
        output_root=output_root,
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
    )
    if state != {"state": "decision_and_authority_exact"}:
        raise H3ValidationError("H3_POST_PUBLICATION_LIFECYCLE_INVALID")
    return state


# v6 keeps its schema in one declaration.  Constructor, self-hash, validator,
# round trip, and publication all consume this exact closed key set.
V6_AUTHORITY_KEYS = frozenset(
    {
        "N_strict",
        "authority_sha256",
        "branch",
        "credentials_boundary",
        "decision_raw_sha256",
        "decision_sha256",
        "external_calls_authorized",
        "freeze_root_sha256",
        "h4_reason",
        "h4_required",
        "model_execution_authorized",
        "model_snapshot",
        "packet_sha256",
        "phase3_authority_sha256",
        "predecessor_v1_decision_sha256",
        "predecessor_v2_authority_sha256",
        "predecessor_v2_decision_sha256",
        "predecessor_v3_packet_sha256",
        "predecessor_v3_readiness_sha256",
        "predecessor_v4_authority_sha256",
        "predecessor_v4_decision_sha256",
        "predecessor_v5_authority_sha256",
        "predecessor_v5_decision_sha256",
        "production_retrieval_authorized",
        "provider_config_present",
        "readiness_sha256",
        "repeat_count",
        "schema_version",
    }
)
_V6_DECISION_PATH = "reviews/h3-branch-decision-v6.json"
_V6_AUTHORITY_PATH = "phase4/branch-authority-v6.json"
_V6_CONTRACT_PATH = "phase4/h3-v6-lifecycle-contract.md"
_V6_RUFF_RECEIPT_PATH = "receipts/h3-v6-ruff-0.16.json"
_FROZEN_PATHS_V6 = tuple(sorted({*_FROZEN_PATHS_V5, _V6_CONTRACT_PATH, _V6_RUFF_RECEIPT_PATH}))


def _inventory_v6(root: Path) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    try:
        observations = {path: read_authoritative_file(root, path) for path in _FROZEN_PATHS_V6}
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID") from error
    records, raw_by_path = [], {}
    for path in _FROZEN_PATHS_V6:
        evidence, raw = observations[path]
        if (
            evidence.file_kind != "regular_file"
            or evidence.hardlink_count != 1
            or evidence.sha256 is None
        ):
            raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
        records.append(
            {
                "byte_length": evidence.byte_length,
                "kind": evidence.file_kind,
                "path": evidence.path,
                "sha256": evidence.sha256,
            }
        )
        raw_by_path[path] = raw
    return records, raw_by_path


def _load_h3_v5_failed_publication(*, root: Path) -> dict[str, object]:
    packet, packet_raw = _load_canonical(root, "reports/h3/h3-red-review-v5/review-packet.json")
    readiness, readiness_raw = _load_canonical(root, "receipts/h3-branch-readiness-v5.json")
    decision, decision_raw = _load_canonical(root, _V5_DECISION_PATH)
    authority, authority_raw = _load_canonical(root, _V5_AUTHORITY_PATH)
    if (
        packet.get("schema_version") != "h3-red-review-packet-v5"
        or readiness.get("schema_version") != "h3-branch-readiness-v5"
        or not _self_hash_valid(packet, "packet_sha256")
        or not _self_hash_valid(readiness, "readiness_sha256")
        or readiness.get("packet_sha256") != packet.get("packet_sha256")
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    validate_h3_red_decision_v5(decision=decision, packet=packet, readiness=readiness)
    if authority.get("schema_version") != "phase4-branch-authority-v5" or not _self_hash_valid(
        authority, "authority_sha256"
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    return {
        "authority": _historical_identity(
            path=_V5_AUTHORITY_PATH,
            raw=authority_raw,
            value=authority,
            self_hash_field="authority_sha256",
        ),
        "decision": _historical_identity(
            path=_V5_DECISION_PATH,
            raw=decision_raw,
            value=decision,
            self_hash_field="decision_sha256",
        ),
        "failure_code": "H3_AUTHORITY_INVALID",
        "packet": _historical_identity(
            path="reports/h3/h3-red-review-v5/review-packet.json",
            raw=packet_raw,
            value=packet,
            self_hash_field="packet_sha256",
        ),
        "readiness": _historical_identity(
            path="receipts/h3-branch-readiness-v5.json",
            raw=readiness_raw,
            value=readiness,
            self_hash_field="readiness_sha256",
        ),
        "status": "historical_failed_publication_not_current_authority",
    }


def load_phase4_freeze_inputs_v6(*, experiment_root: Path | None = None) -> dict[str, object]:
    root = experiment_root or Path(__file__).resolve().parents[2]
    base = load_phase4_freeze_inputs_v5(experiment_root=root)
    inventory, raw_by_path = _inventory_v6(root)
    return {
        **base,
        "phase4_freeze_inventory": inventory,
        "freeze_inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "raw_by_path": raw_by_path,
        "predecessor_v5": _load_h3_v5_failed_publication(root=root),
    }


def _validate_v6_machine_roots(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> None:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    current = load_phase4_freeze_inputs_v6(experiment_root=root)
    for field in (
        "phase3_bindings",
        "phase4_freeze_inventory",
        "freeze_inventory_sha256",
        "predecessor_v1",
        "predecessor_v2",
        "predecessor_v3",
        "predecessor_v4",
        "predecessor_v5",
        "raw_by_path",
    ):
        if freeze_inputs.get(field) != current.get(field):
            raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")
    if dict(packet) != build_h3_red_review_packet_v6(current) or dict(
        readiness
    ) != build_h3_red_readiness_v6(packet):
        raise H3ValidationError("FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION")


def _v6_authority_hash(authority: Mapping[str, object]) -> str:
    if set(authority) != V6_AUTHORITY_KEYS:
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return sha256_bytes(
        canonical_json_bytes(
            {key: value for key, value in authority.items() if key != "authority_sha256"}
        )
    )


def _build_h3_red_authority_v6_from_persisted_decision(
    *,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision_raw: bytes,
) -> dict[str, object]:
    _validate_v6_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    decision = _decode_v5_canonical(decision_raw, code="H3_DECISION_PUBLICATION_LIFECYCLE_INVALID")
    validate_h3_red_decision_v6(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    predecessors = {version: packet[f"predecessor_v{version}"] for version in (1, 2, 3, 4, 5)}
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "decision_raw_sha256": sha256_bytes(decision_raw),
        "decision_sha256": decision["decision_sha256"],
        "external_calls_authorized": False,
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": readiness["phase3_authority_sha256"],
        "predecessor_v1_decision_sha256": predecessors[1]["decision"]["self_sha256"],
        "predecessor_v2_authority_sha256": predecessors[2]["authority"]["self_sha256"],
        "predecessor_v2_decision_sha256": predecessors[2]["decision"]["self_sha256"],
        "predecessor_v3_packet_sha256": predecessors[3]["packet"]["self_sha256"],
        "predecessor_v3_readiness_sha256": predecessors[3]["readiness"]["self_sha256"],
        "predecessor_v4_authority_sha256": predecessors[4]["authority"]["self_sha256"],
        "predecessor_v4_decision_sha256": predecessors[4]["decision"]["self_sha256"],
        "predecessor_v5_authority_sha256": predecessors[5]["authority"]["self_sha256"],
        "predecessor_v5_decision_sha256": predecessors[5]["decision"]["self_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "readiness_sha256": readiness["readiness_sha256"],
        "repeat_count": 0,
        "schema_version": "phase4-branch-authority-v6",
    }
    payload["freeze_root_sha256"] = sha256_bytes(
        canonical_json_bytes(
            {key: value for key, value in payload.items() if key != "freeze_root_sha256"}
        )
    )
    authority = {**payload, "authority_sha256": ""}
    if set(authority) != V6_AUTHORITY_KEYS:
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return {**payload, "authority_sha256": _v6_authority_hash(authority)}


def audit_no_model_reachability_v6(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path):
        raise H3ValidationError("H3_FREEZE_INVENTORY_INVALID")
    v5_inventory, v5_raw = _inventory_v5(root)
    audit = audit_no_model_reachability_v5(
        {
            **freeze_inputs,
            "phase4_freeze_inventory": v5_inventory,
            "freeze_inventory_sha256": sha256_bytes(canonical_json_bytes(v5_inventory)),
            "raw_by_path": v5_raw,
        }
    )
    payload = {
        **{
            key: value
            for key, value in audit.items()
            if key
            not in {"no_model_reachability_sha256", "inspected_output_paths", "schema_version"}
        },
        "inspected_output_paths": [
            "reports/h3/h3-red-review-v6/review-packet.json",
            "reports/h3/h3-red-review-v6/review-packet.md",
            "receipts/h3-branch-readiness-v6.json",
        ],
        "schema_version": "h3-no-model-reachability-v6",
    }
    return {**payload, "no_model_reachability_sha256": sha256_bytes(canonical_json_bytes(payload))}


def build_h3_red_review_packet_v6(freeze_inputs: Mapping[str, object]) -> dict[str, object]:
    root = freeze_inputs.get("_experiment_root")
    if not isinstance(root, Path) or any(
        not isinstance(freeze_inputs.get(f"predecessor_v{version}"), Mapping)
        for version in (1, 2, 3, 4, 5)
    ):
        raise H3ValidationError("H3_PREDECESSOR_CHAIN_INVALID")
    base = load_phase4_freeze_inputs_v5(experiment_root=root)
    v5_packet = build_h3_red_review_packet_v5(base)
    no_model = audit_no_model_reachability_v6(freeze_inputs)
    payload = {
        **{
            key: value
            for key, value in v5_packet.items()
            if key
            not in {
                "freeze_inventory_sha256",
                "no_model_reachability",
                "no_model_reachability_sha256",
                "packet_sha256",
                "phase4_freeze_inventory",
                "predecessor_v1",
                "predecessor_v2",
                "predecessor_v3",
                "predecessor_v4",
                "schema_version",
                "successor_rationale",
            }
        },
        "freeze_inventory_sha256": freeze_inputs["freeze_inventory_sha256"],
        "phase4_freeze_inventory": freeze_inputs["phase4_freeze_inventory"],
        "no_model_reachability": no_model,
        "no_model_reachability_sha256": no_model["no_model_reachability_sha256"],
        **{
            f"predecessor_v{version}": dict(freeze_inputs[f"predecessor_v{version}"])
            for version in (1, 2, 3, 4, 5)
        },
        "schema_version": "h3-red-review-packet-v6",
        "successor_rationale": "v6 successor rationale: v5 roots and human decision remain immutable historical evidence, and the two v5 publication leaves remain preserved as failed publication artifacts. However, the frozen v5 authority constructor emitted predecessor-v4 identity fields that the frozen closed-field validator did not admit, so every legitimately generated v5 authority necessarily failed post-publication validation. v6 repairs only this constructor-validator schema drift and completes validation under the repository-pinned Ruff 0.16 environment; it does not change Red semantics, N_strict=0, repeat_count=0, retrieval authority, model boundaries, or any permission boundary.",
    }
    return {**payload, "packet_sha256": sha256_bytes(canonical_json_bytes(payload))}


def render_h3_red_review_markdown_v6(packet: Mapping[str, object]) -> bytes:
    if (
        not _self_hash_valid(packet, "packet_sha256")
        or packet.get("schema_version") != "h3-red-review-packet-v6"
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    return (
        b"# Phase 4 H3 Red Successor Review v6\n\n**MACHINE READINESS ONLY; V6 HUMAN DECISION REQUIRED BEFORE ANY AUTHORITY**\n\n## Canonical packet\n\n```json\n"
        + canonical_json_bytes(dict(packet))
        + b"```\n"
    )


def build_h3_red_readiness_v6(
    packet: Mapping[str, object], markdown: bytes | None = None
) -> dict[str, object]:
    rendered = render_h3_red_review_markdown_v6(packet)
    if markdown is None:
        markdown = rendered
    if (
        markdown != rendered
        or packet.get("branch") != "red"
        or packet.get("N_strict") != 0
        or packet.get("repeat_count") != 0
        or packet.get("h4_required") is not False
        or any(
            packet.get(field) is not False
            for field in (
                "provider_config_present",
                "external_calls_authorized",
                "production_retrieval_authorized",
                "model_execution_authorized",
            )
        )
    ):
        raise H3ValidationError("H3_READINESS_INVALID")
    payload = {
        "N_strict": 0,
        "branch": "red",
        "credentials_boundary": "not_applicable_red",
        "external_calls_authorized": False,
        "freeze_inventory_sha256": packet["freeze_inventory_sha256"],
        "h4_reason": "not_applicable_red",
        "h4_required": False,
        "historical_predecessors": {
            str(version): dict(packet[f"predecessor_v{version}"]) for version in (1, 2, 3, 4, 5)
        },
        "markdown_sha256": sha256_bytes(markdown),
        "model_execution_authorized": False,
        "model_snapshot": "not_applicable_red",
        "no_model_reachability_sha256": packet["no_model_reachability_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "phase3_authority_sha256": packet["phase3_bindings"]["phase3_authority_sha256"],
        "production_retrieval_authorized": False,
        "provider_config_present": False,
        "repeat_count": 0,
        "schema_version": "h3-branch-readiness-v6",
        "status": "ready_for_human",
    }
    return {**payload, "readiness_sha256": sha256_bytes(canonical_json_bytes(payload))}


def validate_h3_red_decision_v6(
    *, decision: object, packet: Mapping[str, object], readiness: Mapping[str, object]
) -> dict[str, object]:
    if (
        not isinstance(decision, dict)
        or set(decision) != _V5_DECISION_FIELDS
        or decision.get("schema_version") != "h3-branch-decision-v6"
        or decision.get("packet_sha256") != packet.get("packet_sha256")
        or decision.get("readiness_sha256") != readiness.get("readiness_sha256")
        or not _self_hash_valid(decision, "decision_sha256")
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if decision.get("aggregate_disposition") not in {
        "approved_red",
        "disputed",
        "incomplete",
    } or not all(
        isinstance(decision.get(field), str) and decision[field].strip()
        for field in ("aggregate_rationale", "attestation", "reviewer_id", "signature")
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    try:
        require_canonical_utc(decision.get("timestamp_utc"), "H3_DECISION_INCOMPLETE")
    except DataSchemaError as error:
        raise H3ValidationError(str(error)) from error
    acknowledgments, expected = (
        decision.get("acknowledgments"),
        packet.get("required_acknowledgment_categories"),
    )
    if (
        not isinstance(acknowledgments, list)
        or [item.get("category") if isinstance(item, Mapping) else None for item in acknowledgments]
        != expected
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if any(
        not isinstance(item, Mapping)
        or set(item) != {"category", "disposition", "rationale"}
        or item.get("disposition") not in {"approved", "disputed", "incomplete"}
        or not isinstance(item.get("rationale"), str)
        or not item["rationale"].strip()
        for item in acknowledgments
    ):
        raise H3ValidationError("H3_DECISION_INCOMPLETE")
    if decision["aggregate_disposition"] == "approved_red" and any(
        item["disposition"] != "approved" for item in acknowledgments
    ):
        raise H3ValidationError("H3_DECISION_INCONSISTENT")
    return decision


def build_h3_red_decision_v6(
    *,
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    acknowledgments: list[dict[str, str]],
    aggregate_disposition: str,
    aggregate_rationale: str,
    reviewer_id: str,
    attestation: str,
    signature: str,
    timestamp_utc: str,
) -> dict[str, object]:
    payload = {
        "acknowledgments": acknowledgments,
        "aggregate_disposition": aggregate_disposition,
        "aggregate_rationale": aggregate_rationale,
        "attestation": attestation,
        "packet_sha256": packet.get("packet_sha256"),
        "readiness_sha256": readiness.get("readiness_sha256"),
        "reviewer_id": reviewer_id,
        "schema_version": "h3-branch-decision-v6",
        "signature": signature,
        "timestamp_utc": timestamp_utc,
    }
    return validate_h3_red_decision_v6(
        decision={**payload, "decision_sha256": sha256_bytes(canonical_json_bytes(payload))},
        packet=packet,
        readiness=readiness,
    )


def validate_h3_red_authority_v6(
    *,
    authority: object,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision_raw: bytes,
) -> dict[str, object]:
    if (
        not isinstance(authority, dict)
        or set(authority) != V6_AUTHORITY_KEYS
        or authority.get("schema_version") != "phase4-branch-authority-v6"
        or authority.get("authority_sha256") != _v6_authority_hash(authority)
    ):
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    expected = _build_h3_red_authority_v6_from_persisted_decision(
        freeze_inputs=freeze_inputs, packet=packet, readiness=readiness, decision_raw=decision_raw
    )
    if dict(authority) != expected:
        raise H3ValidationError("H3_AUTHORITY_INVALID")
    return authority


def _write_v6_decision(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> bytes:
    _validate_v6_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    validated = validate_h3_red_decision_v6(decision=decision, packet=packet, readiness=readiness)
    if validated.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    expected = canonical_json_bytes(validated)
    current, authority = (
        _read_v5_leaf_or_absent(output_root, _V6_DECISION_PATH),
        _read_v5_leaf_or_absent(output_root, _V6_AUTHORITY_PATH),
    )
    if authority is not None or (current is not None and current != expected):
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if current is None:
        try:
            write_exact_descriptor_files(output_root, {_V6_DECISION_PATH: expected})
        except (FilesystemPolicyError, OSError) as error:
            raise H3ValidationError("H3_DECISION_WRITE_INVALID") from error
        current = _read_v5_leaf_or_absent(output_root, _V6_DECISION_PATH)
    if current != expected:
        raise H3ValidationError("H3_DECISION_WRITE_INVALID")
    return current


def publish_h3_red_authority_v6(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
    decision: object,
) -> dict[str, object]:
    _validate_v6_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    requested = validate_h3_red_decision_v6(decision=decision, packet=packet, readiness=readiness)
    if requested.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    expected = canonical_json_bytes(requested)
    decision_raw, authority_raw = (
        _read_v5_leaf_or_absent(output_root, _V6_DECISION_PATH),
        _read_v5_leaf_or_absent(output_root, _V6_AUTHORITY_PATH),
    )
    if authority_raw is not None and decision_raw is None:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if decision_raw is not None and decision_raw != expected:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    if authority_raw is not None:
        authority = _decode_v5_canonical(authority_raw, code="H3_PUBLICATION_STATE_INVALID")
        validate_h3_red_authority_v6(
            authority=authority,
            freeze_inputs=freeze_inputs,
            packet=packet,
            readiness=readiness,
            decision_raw=decision_raw,
        )
        return authority
    if decision_raw is None:
        decision_raw = _write_v6_decision(
            output_root=output_root,
            freeze_inputs=freeze_inputs,
            packet=packet,
            readiness=readiness,
            decision=requested,
        )
    authority = _build_h3_red_authority_v6_from_persisted_decision(
        freeze_inputs=freeze_inputs, packet=packet, readiness=readiness, decision_raw=decision_raw
    )
    raw = canonical_json_bytes(authority)
    try:
        write_exact_descriptor_files(output_root, {_V6_AUTHORITY_PATH: raw})
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID") from error
    if _read_v5_leaf_or_absent(output_root, _V6_AUTHORITY_PATH) != raw:
        raise H3ValidationError("H3_AUTHORITY_WRITE_INVALID")
    return authority


def validate_h3_v6_publication_lifecycle(
    *,
    output_root: Path,
    freeze_inputs: Mapping[str, object],
    packet: Mapping[str, object],
    readiness: Mapping[str, object],
) -> dict[str, str]:
    _validate_v6_machine_roots(freeze_inputs=freeze_inputs, packet=packet, readiness=readiness)
    decision_raw, authority_raw = (
        _read_v5_leaf_or_absent(output_root, _V6_DECISION_PATH),
        _read_v5_leaf_or_absent(output_root, _V6_AUTHORITY_PATH),
    )
    if decision_raw is None and authority_raw is None:
        return {"state": "absent"}
    if decision_raw is None:
        raise H3ValidationError("H3_PUBLICATION_STATE_INVALID")
    decision = _decode_v5_canonical(decision_raw, code="H3_PUBLICATION_STATE_INVALID")
    validate_h3_red_decision_v6(decision=decision, packet=packet, readiness=readiness)
    if decision.get("aggregate_disposition") != "approved_red":
        raise H3ValidationError("H3_APPROVED_RED_REQUIRED")
    if authority_raw is None:
        return {"state": "decision_only_exact"}
    validate_h3_red_authority_v6(
        authority=_decode_v5_canonical(authority_raw, code="H3_PUBLICATION_STATE_INVALID"),
        freeze_inputs=freeze_inputs,
        packet=packet,
        readiness=readiness,
        decision_raw=decision_raw,
    )
    return {"state": "decision_and_authority_exact"}


def write_h3_red_readiness_v6(
    *,
    experiment_root: Path,
    packet: Mapping[str, object],
    markdown: bytes,
    readiness: Mapping[str, object],
) -> None:
    if dict(readiness) != build_h3_red_readiness_v6(packet, markdown):
        raise H3ValidationError("H3_READINESS_INVALID")
    try:
        write_exact_descriptor_files(
            experiment_root,
            {
                "receipts/h3-branch-readiness-v6.json": canonical_json_bytes(readiness),
                "reports/h3/h3-red-review-v6/review-packet.json": canonical_json_bytes(packet),
                "reports/h3/h3-red-review-v6/review-packet.md": markdown,
            },
        )
    except (FilesystemPolicyError, OSError) as error:
        raise H3ValidationError("H3_READINESS_INVALID") from error
