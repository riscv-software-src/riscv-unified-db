# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Validation for reviewer-pending versioned source-contract proposals.

The proposal is deliberately not a source-publication decision.  It captures
the exact evidence a reviewer must approve before any accepted bundle can be
constructed, while keeping the frozen contract and its rejected receipt intact.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from collections.abc import Mapping
from pathlib import Path
from .canonical import canonical_json_bytes, require_byte_length, require_sha256, sha256_bytes
from .filesystem import (
    FilesystemPolicyError,
    read_authoritative_file,
    require_relative_posix_path,
)
from .git_proof import GitProofError


class SourceContractProposalError(ValueError):
    """A stable diagnostic for incomplete or unverifiable correction proposals."""


class FixtureRegistryError(ValueError):
    """Stable diagnostic for PR #2164 finite-set fixture custody failures."""


class _BoundedSubprocessError(OSError):
    """A child exceeded its closed input or output resource envelope."""


def _run_bounded_subprocess(
    command: list[str], *, input_bytes: bytes, max_stdout_bytes: int,
    max_stderr_bytes: int, timeout: float, max_stdin_bytes: int = 1024 * 1024,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one child while actively bounding all three byte streams."""
    if (
        not command or any(not isinstance(part, str) or not part for part in command)
        or not isinstance(input_bytes, bytes) or len(input_bytes) > max_stdin_bytes
        or min(max_stdin_bytes, max_stdout_bytes, max_stderr_bytes) < 0 or timeout <= 0
    ):
        raise _BoundedSubprocessError("SUBPROCESS_ENVELOPE_INVALID")
    with tempfile.TemporaryFile() as input_stream:
        input_stream.write(input_bytes)
        input_stream.seek(0)
        process = subprocess.Popen(
            command, stdin=input_stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        selector: selectors.BaseSelector | None = None
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        try:
            if process.stdout is None or process.stderr is None:
                raise _BoundedSubprocessError("SUBPROCESS_PIPE_UNAVAILABLE")
            selector = selectors.DefaultSelector()
            limits = {"stdout": max_stdout_bytes, "stderr": max_stderr_bytes}
            totals = {"stdout": 0, "stderr": 0}
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            deadline = time.monotonic() + timeout
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                events = selector.select(remaining)
                if not events:
                    raise subprocess.TimeoutExpired(command, timeout)
                for key, _ in events:
                    stream_name = key.data
                    chunk = os.read(key.fileobj.fileno(), min(64 * 1024, limits[stream_name] - totals[stream_name] + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    chunks[stream_name].append(chunk)
                    totals[stream_name] += len(chunk)
                    if totals[stream_name] > limits[stream_name]:
                        raise _BoundedSubprocessError(f"SUBPROCESS_{stream_name.upper()}_LIMIT")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            returncode = process.wait(timeout=remaining)
        except BaseException:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    process.kill()
                process.wait()
            raise
        finally:
            if selector is not None:
                try:
                    selector.close()
                except BaseException:
                    pass
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException:
                        pass
        return subprocess.CompletedProcess(
            command, returncode, stdout=b"".join(chunks["stdout"]), stderr=b"".join(chunks["stderr"]),
        )


_FIXTURE_BASE = "tools/python/param-extraction-eval/cases"
_EXPECTED_FIXTURES = {
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
_FIXTURE_COMMIT = "22e84458c87a7ccf4c07034de1eb6d0bf9764144"
_FIXTURE_TREE = "af003b427c66bd8ac9803a91b3bf363a1b1304d9"
_PORTABLE_FIXTURE_BUNDLE = (
    "experiments/specchoice-v1.3.2/bundles/accepted/"
    "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
)


def read_portable_fixture_blob(
    repository: Path, pinned_commit: str, local_bundle_path: str
) -> bytes:
    """Read one pinned fixture from the self-contained accepted byte archive."""
    from .publication import has_publication_manifest

    if pinned_commit != _FIXTURE_COMMIT or not has_publication_manifest(repository):
        raise FixtureRegistryError("FIXTURE_PIN_INVALID")
    try:
        evidence, raw = read_authoritative_file(
            repository, f"{_PORTABLE_FIXTURE_BUNDLE}/{local_bundle_path}"
        )
    except (FilesystemPolicyError, OSError) as error:
        raise FixtureRegistryError("FIXTURE_ARCHIVE_UNAVAILABLE") from error
    if evidence.file_kind != "regular_file":
        raise FixtureRegistryError("FIXTURE_NON_REGULAR_FILE")
    return raw
_FIXTURE_CONSTRUCTION_GENERATION = "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
_FIXTURE_CONSTRUCTION_SOURCE_COMMIT = "bf91185887590799e76a3077ca03fd7f319e88e2"
_FIXTURE_CONSTRUCTION_REGISTRY_SHA256 = "ddda6f6c96b4007d8d57aed64210fc08701b89bfd27feac5f0732c828c388f36"
_FIXTURE_CONSTRUCTION_VERIFIER_PATHS = (
    "verifier/specchoice_evidence/__init__.py",
    "verifier/specchoice_evidence/canonical.py",
    "verifier/specchoice_evidence/filesystem.py",
    "verifier/specchoice_evidence/verify.py",
    "verify_bundle.py",
)
_FIXTURE_CONSTRUCTION_CONTROL_PATHS = (
    "config/measurement/canonical-adjudication-schema-v1.json",
    "config/measurement/pr2164-adapter-rules-v1.json",
    "fixtures/measurement/golden-predictions-v1.json",
    "reports/h1/adversarial-oracle-results-v2.json",
)

_V4_SEMANTIC_REPAIRS = {
    "raw/evaluation_fixtures/CAND_WARL_FIXED_LEGAL_SET/expected.yaml",
    "raw/evaluation_fixtures/POS_DIRECT_NUM_PMP/gold.yaml",
    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/expected.yaml",
    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/gold.yaml",
    "raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/expected.yaml",
    "raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/gold.yaml",
}
_V4_CACHE_REPAIRS = {
    "unified_cache_block_identity": {
        "raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml",
    },
    "scoped_cache_block_identities": {
        "raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml",
    },
}
_V4_V3_REPAIR_TARGETS = {
    "raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml",
    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/expected.yaml",
}
_V4_PBMTE_EFFECTS = {
    "excluded_from_discovery": {"fixture_class": "absent", "gold": False, "classify_out": False, "surfaced": False},
    "surfaced_classified_out": {"fixture_class": "candidate", "gold": True, "classify_out": True, "surfaced": True},
    "included_capability_parameter": {"fixture_class": "positive", "gold": True, "classify_out": False, "surfaced": True},
}
_V4_CODE_PATHS = (
    "experiments/specchoice-v1.3.2/src/specchoice_evidence/canonical.py",
    "experiments/specchoice-v1.3.2/src/specchoice_evidence/cli.py",
    "experiments/specchoice-v1.3.2/src/specchoice_evidence/filesystem.py",
    "experiments/specchoice-v1.3.2/src/specchoice_evidence/source_contract.py",
    "experiments/specchoice-v1.3.2/src/specchoice_evidence/verify.py",
    "experiments/specchoice-v1.3.2/src/specchoice_measurement/h1.py",
)
_V4_REPAIR_REASONS = {
    "raw/evaluation_fixtures/CAND_WARL_FIXED_LEGAL_SET/expected.yaml": "freeze fixed legal-set classify-out disposition",
    "raw/evaluation_fixtures/NEG_EXT_GATED_PBMTE/expected.yaml": "apply the human surfaced/classified-out policy",
    "raw/evaluation_fixtures/NEG_EXT_GATED_PBMTE/gold.yaml": "record the surfaced PBMTE review candidate",
    "raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml": "retain only cache-local implementation evidence and a power-of-two domain",
    "raw/evaluation_fixtures/POS_DIRECT_NUM_PMP/gold.yaml": "restrict PMP entries to the architectural finite legal set",
    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/expected.yaml": "record GEILEN canonical naming through the existing UDB alias",
    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/gold.yaml": "permit zero GEILEN and describe direct guest-external targets",
    "raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/expected.yaml": "record ASIDLEN through the existing ASID_WIDTH alias",
    "raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/gold.yaml": "use ASIDLEN as the canonical ontology identity",
}


def validate_fixture_construction_proposal_v4(
    *, proposal: object, repair_manifest: object, registry: object, ontology: Mapping[str, object],
    predecessor_identity: Mapping[str, str], predecessor_manifest_sha256: str,
    predecessor_registry_sha256: str, predecessor_files: Mapping[str, Mapping[str, object]],
    predecessor_classes: Mapping[str, str], authority_sha256: str, revocation_sha256: str,
    repair_payloads: Mapping[str, bytes], supersession: object, supersession_sha256: str,
    legacy_proposal_sha256: str, legacy_manifest_sha256: str, legacy_registry_sha256: str,
    previous_supersession: object, previous_supersession_sha256: str,
    previous_legacy_proposal_sha256: str, previous_legacy_manifest_sha256: str, previous_legacy_registry_sha256: str,
    prior_supersession: object, prior_supersession_sha256: str,
    prior_legacy_proposal_sha256: str, prior_legacy_manifest_sha256: str, prior_legacy_registry_sha256: str,
    repository_root: Path,
) -> dict[str, object]:
    """Validate the decision-bound, append-only semantic-gold construction request."""
    if not isinstance(proposal, Mapping) or set(proposal) != {
        "active_authority", "external_publication_authorized", "fixed_code_artifacts", "fixed_code_commit", "generation", "local_only",
        "ontology_decision", "predecessor", "registry", "repair_manifest", "replacements", "revocation",
        "schema_version", "selected_policy", "status", "successor_inventory",
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_PROPOSAL_INVALID")
    if proposal.get("schema_version") != "fixture-construction-proposal-v4" or proposal.get("generation") != (
        "source-contract-v4-pr2164-semantic-gold-closure-verifier-rooted-v4"
    ) or proposal.get("status") != "awaiting_human_construction_authorization" or proposal.get("local_only") is not True or (
        proposal.get("external_publication_authorized") is not False
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_PROPOSAL_INVALID")
    _require_v4_git_commit(proposal.get("fixed_code_commit"), proposal.get("fixed_code_artifacts"), repository_root)
    artifact_sha256 = ontology.get("artifact_sha256")
    selected_policy = ontology.get("selected_policy")
    if not isinstance(artifact_sha256, str) or not isinstance(selected_policy, Mapping):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_POLICY_INVALID")
    pbmte = selected_policy.get("pbmte")
    cache = selected_policy.get("cache")
    if pbmte != "surfaced_classified_out" or cache != "unified_cache_block_identity":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_POLICY_INVALID")
    _require_v4_binding(proposal.get("ontology_decision"), "reviews/h1-source-gold-ontology-decision-v1.json", artifact_sha256)
    _require_v4_binding(proposal.get("active_authority"), "phase2/source-authority.json", authority_sha256)
    _require_v4_binding(proposal.get("revocation"), "receipts/fixture-closure-revocation-v2.json", revocation_sha256)
    allowed_repairs = _v4_allowed_repairs(str(cache), str(pbmte))
    _validate_v4_repair_manifest(
        repair_manifest, artifact_sha256, allowed_repairs, predecessor_files, repair_payloads, str(cache), str(pbmte),
    )
    inventory = _v4_inventory(predecessor_files, predecessor_classes, str(pbmte), repair_manifest)
    _validate_v4_registry(
        registry, repair_manifest, artifact_sha256, predecessor_registry_sha256, predecessor_files,
        predecessor_classes, str(pbmte), inventory,
    )
    predecessor = _require_mapping(proposal.get("predecessor"), "FIXTURE_CONSTRUCTION_V4_PREDECESSOR_INVALID")
    expected_predecessor = {
        "generation": predecessor_identity.get("generation"),
        "manifest_sha256": predecessor_manifest_sha256,
        "path": "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3",
        "registry_sha256": predecessor_registry_sha256,
        "root_sha256": predecessor_identity.get("root_sha256"),
    }
    if predecessor != expected_predecessor:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_PREDECESSOR_INVALID")
    manifest_sha256 = sha256_bytes(canonical_json_bytes(repair_manifest))
    registry_sha256 = sha256_bytes(canonical_json_bytes(registry))
    _require_v4_binding(proposal.get("repair_manifest"), "config/fixture-repairs/pr2164-semantic-gold-v3/repair-manifest.json", manifest_sha256)
    _require_v4_binding(proposal.get("registry"), "config/fixture-registry-pr2164-v4.json", registry_sha256)
    _validate_v4_supersession(
        supersession, supersession_sha256, legacy_proposal_sha256, legacy_manifest_sha256,
        legacy_registry_sha256, previous_supersession, previous_supersession_sha256,
        previous_legacy_proposal_sha256, previous_legacy_manifest_sha256, previous_legacy_registry_sha256,
        prior_supersession, prior_supersession_sha256,
        prior_legacy_proposal_sha256, prior_legacy_manifest_sha256, prior_legacy_registry_sha256,
        sha256_bytes(canonical_json_bytes(proposal)), manifest_sha256, registry_sha256,
    )
    if proposal.get("replacements") != repair_manifest["repairs"]:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_CLOSURE_INVALID")
    if proposal.get("selected_policy") != {"cache": cache, "pbmte": pbmte}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_POLICY_INVALID")
    if proposal.get("successor_inventory") != inventory:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_INVENTORY_INVALID")
    return dict(proposal)


def _require_v4_binding(value: object, path: str, digest: str) -> None:
    binding = _require_mapping(value, "FIXTURE_CONSTRUCTION_V4_BINDING_INVALID")
    if binding != {"path": path, "sha256": digest}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_BINDING_INVALID")


def _require_v4_artifact_set(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"proposal", "repair_manifest", "registry"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")
    return value


def validate_fixture_construction_decision_v4(
    decision: object, *, proposal: Mapping[str, object], proposal_sha256: str, supersession_sha256: str,
    ontology_sha256: str, authority_sha256: str,
) -> dict[str, object]:
    """Validate a closed human disposition only after the v4 proposal gate passed."""
    required = {
        "active_authority_sha256", "attestation", "decision", "decision_sha256", "decision_timestamp",
        "external_publication_authorized", "fixed_code_commit", "local_only", "ontology_decision_sha256",
        "proposal_sha256", "rationale", "reviewer", "schema_version", "supersession_sha256",
    }
    if not isinstance(decision, Mapping) or set(decision) != required or decision.get("schema_version") != "fixture-construction-decision-v4-v4" or decision.get("decision") not in {"authorize", "reject"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID")
    if decision.get("local_only") is not True or decision.get("external_publication_authorized") is not False or decision.get("fixed_code_commit") != proposal.get("fixed_code_commit") or (
        decision.get("proposal_sha256") != proposal_sha256 or decision.get("supersession_sha256") != supersession_sha256 or
        decision.get("ontology_decision_sha256") != ontology_sha256 or decision.get("active_authority_sha256") != authority_sha256
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_BINDING_INVALID")
    if not all(isinstance(decision.get(field), str) and decision[field].strip() for field in ("rationale", "reviewer", "attestation")):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID")
    timestamp = decision.get("decision_timestamp")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID") from error
    if parsed.tzinfo is None or parsed.isoformat().replace("+00:00", "Z") != timestamp:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID")
    supplied = decision.get("decision_sha256")
    projected = dict(decision)
    projected.pop("decision_sha256")
    if not isinstance(supplied, str) or supplied != sha256_bytes(canonical_json_bytes(projected)):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_DECISION_INVALID")
    return dict(decision)


_V4_NON_EXECUTABLE_ENTRYPOINTS = (
    "build-fixture-construction-candidate-v5",
    "validate-fixture-candidate-v5",
)


def _canonical_json_object(raw: bytes, diagnostic: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceContractProposalError(diagnostic) from error
    if not isinstance(value, Mapping) or canonical_json_bytes(value) != raw:
        raise SourceContractProposalError(diagnostic)
    return value


def render_v4_non_executable_supersession(
    *, proposal_raw: bytes, supersession_raw: bytes, decision_raw: bytes, ontology_raw: bytes,
) -> dict[str, object]:
    """Classify the preserved v4 authorization without changing its meaning."""
    proposal = _canonical_json_object(proposal_raw, "V4_NON_EXECUTABLE_INPUT_INVALID")
    supersession = _canonical_json_object(supersession_raw, "V4_NON_EXECUTABLE_INPUT_INVALID")
    decision = _canonical_json_object(decision_raw, "V4_NON_EXECUTABLE_INPUT_INVALID")
    ontology = _canonical_json_object(ontology_raw, "V4_NON_EXECUTABLE_INPUT_INVALID")
    artifacts = proposal.get("fixed_code_artifacts")
    if (
        proposal.get("schema_version") != "fixture-construction-proposal-v4"
        or supersession.get("schema_version") != "source-contract-construction-proposal-supersession-v3"
        or decision.get("schema_version") != "fixture-construction-decision-v4-v4"
        or decision.get("decision") != "authorize"
        or not isinstance(artifacts, list)
        or {artifact.get("path") for artifact in artifacts if isinstance(artifact, Mapping)} != set(_V4_CODE_PATHS)
    ):
        raise SourceContractProposalError("V4_NON_EXECUTABLE_INPUT_INVALID")
    return {
        "construction_authorized": False,
        "external_publication_authorized": False,
        "historical_v4": {
            "decision_sha256": sha256_bytes(decision_raw),
            "proposal_sha256": sha256_bytes(proposal_raw),
            "supersession_sha256": sha256_bytes(supersession_raw),
        },
        "local_only": True,
        "missing_entrypoints": list(_V4_NON_EXECUTABLE_ENTRYPOINTS),
        "missing_live_runtime_closure": True,
        "observed_fixed_code_artifacts": artifacts,
        "ontology_decision_sha256": sha256_bytes(ontology_raw),
        "schema_version": "v4-construction-authorization-non-executable-supersession-v1",
        "status": "authorized_but_non_executable",
        "successor_generation": "source-contract-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5",
    }


def validate_v4_non_executable_supersession(
    receipt: object, *, proposal_raw: bytes, supersession_raw: bytes, decision_raw: bytes, ontology_raw: bytes,
) -> dict[str, object]:
    """Fail closed unless an append-only receipt is the exact rendered classification."""
    expected = render_v4_non_executable_supersession(
        proposal_raw=proposal_raw,
        supersession_raw=supersession_raw,
        decision_raw=decision_raw,
        ontology_raw=ontology_raw,
    )
    if not isinstance(receipt, Mapping) or dict(receipt) != expected:
        raise SourceContractProposalError("V4_NON_EXECUTABLE_RECEIPT_INVALID")
    return dict(receipt)


_V5_CONSTRUCTION_GENERATION = "source-contract-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5"


def _v5_bound_inputs(bound_inputs: Mapping[str, bytes]) -> list[dict[str, object]]:
    if not isinstance(bound_inputs, Mapping) or not bound_inputs:
        raise SourceContractProposalError("V5_PROPOSAL_INPUT_INVALID")
    result: list[dict[str, object]] = []
    for path, raw in sorted(bound_inputs.items()):
        try:
            normalized = str(require_relative_posix_path(path))
        except ValueError as error:
            raise SourceContractProposalError("V5_PROPOSAL_INPUT_INVALID") from error
        if not isinstance(raw, bytes):
            raise SourceContractProposalError("V5_PROPOSAL_INPUT_INVALID")
        result.append({"byte_length": len(raw), "path": normalized, "sha256": sha256_bytes(raw)})
    if len({entry["path"] for entry in result}) != len(result):
        raise SourceContractProposalError("V5_PROPOSAL_INPUT_INVALID")
    return result


def build_source_contract_proposal_v5(
    *, runtime_closure_raw: bytes, authority_pre_state_raw: bytes, bound_inputs: Mapping[str, bytes], targets: list[str],
) -> dict[str, object]:
    """Build the decision-free v5 proposal from already-frozen bytes only."""
    if not isinstance(runtime_closure_raw, bytes) or not isinstance(authority_pre_state_raw, bytes):
        raise SourceContractProposalError("V5_PROPOSAL_INPUT_INVALID")
    try:
        target_paths = [str(require_relative_posix_path(target)) for target in targets]
    except (TypeError, ValueError) as error:
        raise SourceContractProposalError("V5_PROPOSAL_TARGET_INVALID") from error
    if not target_paths or target_paths != sorted(target_paths) or len(set(target_paths)) != len(target_paths):
        raise SourceContractProposalError("V5_PROPOSAL_TARGET_INVALID")
    return {
        "authority_pre_state": {"byte_length": len(authority_pre_state_raw), "path": "phase2/source-authority.json", "sha256": sha256_bytes(authority_pre_state_raw)},
        "bound_inputs": _v5_bound_inputs(bound_inputs),
        "external_publication_authorized": False,
        "generation": _V5_CONSTRUCTION_GENERATION,
        "local_only": True,
        "runtime_closure_sha256": sha256_bytes(runtime_closure_raw),
        "schema_version": "fixture-construction-proposal-v5",
        "status": "awaiting_human_construction_authorization",
        "targets": target_paths,
    }


def validate_source_contract_proposal_v5(
    proposal: object, *, runtime_closure_raw: bytes, authority_pre_state_raw: bytes, bound_inputs: Mapping[str, bytes],
) -> dict[str, object]:
    """Revalidate every transitive frozen byte before a v5 write boundary."""
    expected = build_source_contract_proposal_v5(
        runtime_closure_raw=runtime_closure_raw,
        authority_pre_state_raw=authority_pre_state_raw,
        bound_inputs=bound_inputs,
        targets=list(proposal.get("targets", [])) if isinstance(proposal, Mapping) else [],
    )
    if not isinstance(proposal, Mapping) or dict(proposal) != expected:
        raise SourceContractProposalError("V5_PROPOSAL_BINDING_MISMATCH")
    return dict(proposal)


def render_v5_rejected_pre_authorization_receipt() -> dict[str, object]:
    """Render, but never write, the v5 non-executable rejection receipt.

    The receipt is historical classification only.  In particular it does not
    supersede a human authorization because no v5 construction decision or
    candidate was ever present.
    """
    return {
        "authorization_present": False,
        "candidate_present": False,
        "construction_authorized": False,
        "external_publication_authorized": False,
        "human_decision_present": False,
        "known_defects": [
            "candidate and acceptance command handlers were success-shaped no-write stubs",
            "runtime closure omitted the 34 accepted-v3 referenced bundle files",
            "runtime closure omitted resolved Python git Ruby and Psych executable and library identities",
            "runtime closure did not reconstruct the registry-v6 29-raw-input universe",
            "target inventory contained only the two proposal leaves and trusted its own declaration",
            "required successor tests were renamed out of unittest discovery",
            "CACHE gold claimed powers two through sixty-three while omitting exponents fifty-one through fifty-four",
            "successor adapter remained on the accepted-v3 twenty-eight-file six-four-one contract",
            "EvidenceSpanIntegrity counted surfaced cases instead of score-bearing span occurrences",
            "golden predictions omitted complete semantic evidence spans and rationales",
            "the seven-question artifact exposed identifiers without complete hash-bound semantics",
        ],
        "local_only": True,
        "proposal_commit": "e1d52d8b",
        "schema_version": "source-contract-construction-proposal-v5-non-executable-supersession-v1",
        "status": "rejected_pre_authorization_non_executable",
        "v5_proposal_sha256": "18443f3ef7a305500386ea40186cf7e789d697f9b8ea0cf10e8141f401812405",
        "v5_supersession_sha256": "3bfaf6015f92bcfa2fdff7c11da1fea50f170b6ed8318f0f69466936948c4a2d",
        "v5_runtime_closure_sha256": "671fe4e36cfe23ea9f1490279c75ae615e46db60769f54a2edb801fd7c2524fe",
    }


def validate_v5_rejected_pre_authorization_receipt(
    receipt: object, *, runtime_closure_raw: bytes, proposal_raw: bytes,
    supersession_raw: bytes, repository_root: Path,
) -> dict[str, object]:
    """Validate the exact v5 rejected-history classification from live facts."""
    if (
        sha256_bytes(runtime_closure_raw) != "671fe4e36cfe23ea9f1490279c75ae615e46db60769f54a2edb801fd7c2524fe"
        or sha256_bytes(proposal_raw) != "18443f3ef7a305500386ea40186cf7e789d697f9b8ea0cf10e8141f401812405"
        or sha256_bytes(supersession_raw) != "3bfaf6015f92bcfa2fdff7c11da1fea50f170b6ed8318f0f69466936948c4a2d"
    ):
        raise SourceContractProposalError("V5_REJECTED_HISTORY_INPUT_MISMATCH")
    expected = render_v5_rejected_pre_authorization_receipt()
    if not isinstance(receipt, Mapping) or dict(receipt) != expected:
        raise SourceContractProposalError("V5_REJECTED_HISTORY_RECEIPT_INVALID")
    experiment = repository_root / "experiments/specchoice-v1.3.2"
    forbidden = (
        experiment / "receipts/source-contract-construction-decision-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5.json",
        experiment / "bundles/candidates/source-contract-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5",
    )
    if any(path.exists() or path.is_symlink() for path in forbidden):
        raise SourceContractProposalError("V5_REJECTED_HISTORY_STATE_MISMATCH")
    try:
        resolved = _run_bounded_subprocess(
            ["git", "-C", str(repository_root), "rev-parse", "e1d52d8b^{commit}"],
            input_bytes=b"", max_stdin_bytes=0, max_stdout_bytes=64,
            max_stderr_bytes=_V4_SUBPROCESS_MAX_STDERR_BYTES, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SourceContractProposalError("V5_REJECTED_HISTORY_COMMIT_INVALID") from error
    if resolved.returncode != 0:
        from .publication import (
            PublicationContractError,
            has_publication_manifest,
            publication_manifest_path,
            validate_publication_manifest,
        )

        if not has_publication_manifest(repository_root):
            raise SourceContractProposalError("V5_REJECTED_HISTORY_COMMIT_INVALID")
        try:
            publication = validate_publication_manifest(
                repository_root, publication_manifest_path(repository_root)
            )
        except PublicationContractError as error:
            raise SourceContractProposalError("V5_REJECTED_HISTORY_COMMIT_INVALID") from error
        provenance = publication.get("historical_provenance")
        if not isinstance(provenance, list) or not any(
            isinstance(item, Mapping)
            and item.get("commit_sha") == "e1d52d8b8ca638d142e5ecf054cb7a236c5f5a3c"
            for item in provenance
        ):
            raise SourceContractProposalError("V5_REJECTED_HISTORY_COMMIT_INVALID")
    elif not resolved.stdout.decode("ascii", "strict").strip().startswith("e1d52d8b"):
        raise SourceContractProposalError("V5_REJECTED_HISTORY_COMMIT_INVALID")
    return dict(receipt)


def _validate_v4_supersession(
    receipt: object, receipt_sha256: str, legacy_proposal_sha256: str, legacy_manifest_sha256: str,
    legacy_registry_sha256: str, previous_supersession: object, previous_supersession_sha256: str,
    previous_legacy_proposal_sha256: str, previous_legacy_manifest_sha256: str, previous_legacy_registry_sha256: str,
    prior_supersession: object, prior_supersession_sha256: str,
    prior_legacy_proposal_sha256: str, prior_legacy_manifest_sha256: str, prior_legacy_registry_sha256: str,
    proposal_sha256: str, manifest_sha256: str, registry_sha256: str,
) -> None:
    if not isinstance(receipt, Mapping) or set(receipt) != {
        "construction_authorized", "legacy", "previous_supersession", "replacement_reason", "schema_version", "status", "successor",
    } or receipt.get("schema_version") != "source-contract-construction-proposal-supersession-v3" or (
        receipt.get("status") != "semantic_proposal_v3_superseded"
    ) or receipt.get("construction_authorized") is not False or not isinstance(receipt.get("replacement_reason"), str) or (
        not receipt["replacement_reason"].strip()
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")
    legacy = _require_v4_artifact_set(receipt.get("legacy"))
    successor = _require_v4_artifact_set(receipt.get("successor"))
    _require_v4_binding(receipt.get("previous_supersession"), "receipts/source-contract-construction-proposal-v4-supersession-v2.json", previous_supersession_sha256)
    _validate_v4_supersession_v2(
        previous_supersession, previous_supersession_sha256,
        previous_legacy_proposal_sha256, previous_legacy_manifest_sha256, previous_legacy_registry_sha256,
        legacy_proposal_sha256,
        prior_supersession, prior_supersession_sha256,
        prior_legacy_proposal_sha256, prior_legacy_manifest_sha256, prior_legacy_registry_sha256,
    )
    _require_v4_binding(
        legacy.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v3.json", legacy_proposal_sha256,
    )
    _require_v4_binding(
        legacy.get("repair_manifest"),
        "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json", legacy_manifest_sha256,
    )
    _require_v4_binding(
        legacy.get("registry"),
        "config/fixture-registry-pr2164-v3.json", legacy_registry_sha256,
    )
    _require_v4_binding(
        successor.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json", proposal_sha256,
    )
    _require_v4_binding(
        successor.get("repair_manifest"),
        "config/fixture-repairs/pr2164-semantic-gold-v3/repair-manifest.json", manifest_sha256,
    )
    _require_v4_binding(
        successor.get("registry"),
        "config/fixture-registry-pr2164-v4.json", registry_sha256,
    )
    if receipt_sha256 != sha256_bytes(canonical_json_bytes(receipt)):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")


def _validate_v4_supersession_v2(
    receipt: object, receipt_sha256: str,
    legacy_proposal_sha256: str, legacy_manifest_sha256: str, legacy_registry_sha256: str,
    successor_proposal_sha256: str,
    previous_supersession: object, previous_supersession_sha256: str,
    previous_legacy_proposal_sha256: str, previous_legacy_manifest_sha256: str, previous_legacy_registry_sha256: str,
) -> None:
    """Prove the immutable v2 receipt bridges v2 to v3 through the v1 receipt."""
    if not isinstance(receipt, Mapping) or set(receipt) != {
        "construction_authorized", "legacy", "previous_supersession", "replacement_reason", "schema_version", "status", "successor",
    } or receipt.get("schema_version") != "source-contract-construction-proposal-supersession-v2" or (
        receipt.get("status") != "semantic_proposal_v2_superseded"
    ) or receipt.get("construction_authorized") is not False or not isinstance(receipt.get("replacement_reason"), str) or (
        not receipt["replacement_reason"].strip()
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")
    _require_v4_binding(
        receipt.get("previous_supersession"),
        "receipts/source-contract-construction-proposal-v4-supersession-v1.json",
        previous_supersession_sha256,
    )
    _validate_v4_previous_supersession(
        previous_supersession, legacy_proposal_sha256, legacy_manifest_sha256, legacy_registry_sha256,
        previous_legacy_proposal_sha256, previous_legacy_manifest_sha256, previous_legacy_registry_sha256,
    )
    legacy = _require_v4_artifact_set(receipt.get("legacy"))
    successor = _require_v4_artifact_set(receipt.get("successor"))
    _require_v4_binding(
        legacy.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v2.json",
        legacy_proposal_sha256,
    )
    _require_v4_binding(
        legacy.get("repair_manifest"),
        "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json",
        legacy_manifest_sha256,
    )
    _require_v4_binding(legacy.get("registry"), "config/fixture-registry-pr2164-v3.json", legacy_registry_sha256)
    _require_v4_binding(
        successor.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v3.json",
        successor_proposal_sha256,
    )
    _require_v4_binding(
        successor.get("repair_manifest"),
        "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json",
        legacy_manifest_sha256,
    )
    _require_v4_binding(successor.get("registry"), "config/fixture-registry-pr2164-v3.json", legacy_registry_sha256)
    if receipt_sha256 != sha256_bytes(canonical_json_bytes(receipt)):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")


def _validate_v4_previous_supersession(
    receipt: object, legacy_proposal_sha256: str, legacy_manifest_sha256: str, legacy_registry_sha256: str,
    previous_legacy_proposal_sha256: str, previous_legacy_manifest_sha256: str, previous_legacy_registry_sha256: str,
) -> None:
    """Prove the immutable v1 receipt itself bridges to this v2 legacy set."""
    if not isinstance(receipt, Mapping) or set(receipt) != {
        "construction_authorized", "legacy", "replacement_reason", "schema_version", "status", "successor",
    } or receipt.get("schema_version") != "source-contract-construction-proposal-supersession-v1" or (
        receipt.get("status") != "legacy_semantic_proposal_superseded"
    ) or receipt.get("construction_authorized") is not False or not isinstance(receipt.get("replacement_reason"), str) or (
        not receipt["replacement_reason"].strip()
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID")
    legacy = _require_v4_artifact_set(receipt.get("legacy"))
    successor = _require_v4_artifact_set(receipt.get("successor"))
    _require_v4_binding(
        legacy.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v1.json", previous_legacy_proposal_sha256,
    )
    _require_v4_binding(
        legacy.get("repair_manifest"), "config/fixture-repairs/pr2164-semantic-gold-v1/repair-manifest.json", previous_legacy_manifest_sha256,
    )
    _require_v4_binding(legacy.get("registry"), "config/fixture-registry-pr2164-v2.json", previous_legacy_registry_sha256)
    _require_v4_binding(
        successor.get("proposal"),
        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v2.json", legacy_proposal_sha256,
    )
    _require_v4_binding(
        successor.get("repair_manifest"), "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json", legacy_manifest_sha256,
    )
    _require_v4_binding(successor.get("registry"), "config/fixture-registry-pr2164-v3.json", legacy_registry_sha256)


_V4_GIT_MAX_ARTIFACT_BYTES = 1024 * 1024
_V4_SUBPROCESS_MAX_STDERR_BYTES = 4096


def _require_v4_git_commit(value: object, artifacts: object, repository_root: Path) -> None:
    if not isinstance(value, str) or len(value) != 40:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")
    if not isinstance(artifacts, list) or len(artifacts) != len(_V4_CODE_PATHS) or [item.get("path") if isinstance(item, Mapping) else None for item in artifacts] != list(_V4_CODE_PATHS):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {"byte_length", "path", "sha256"}:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")
        try:
            length = require_byte_length(artifact.get("byte_length"))
            require_sha256(artifact.get("sha256"))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID") from error
        if length > _V4_GIT_MAX_ARTIFACT_BYTES:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")
    try:
        int(value, 16)
        object_check = _run_bounded_subprocess(
            ["git", "-C", str(repository_root), "cat-file", "-e", f"{value}^{{commit}}"],
            input_bytes=b"", max_stdin_bytes=0, max_stdout_bytes=0,
            max_stderr_bytes=_V4_SUBPROCESS_MAX_STDERR_BYTES, timeout=30,
        )
        ancestry_check = _run_bounded_subprocess(
            ["git", "-C", str(repository_root), "merge-base", "--is-ancestor", value, "HEAD"],
            input_bytes=b"", max_stdin_bytes=0, max_stdout_bytes=0,
            max_stderr_bytes=_V4_SUBPROCESS_MAX_STDERR_BYTES, timeout=30,
        )
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID") from error
    if object_check.returncode != 0 or ancestry_check.returncode != 0:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")
    for artifact in artifacts:
        length = int(artifact["byte_length"])
        try:
            shown = _run_bounded_subprocess(
                ["git", "-C", str(repository_root), "show", f"{value}:{artifact['path']}"],
                input_bytes=b"", max_stdin_bytes=0, max_stdout_bytes=length,
                max_stderr_bytes=_V4_SUBPROCESS_MAX_STDERR_BYTES, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID") from error
        if shown.returncode != 0 or length != len(shown.stdout) or artifact.get("sha256") != sha256_bytes(shown.stdout):
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID")


def _v4_allowed_repairs(cache: str, pbmte: str) -> set[str]:
    effect = _V4_PBMTE_EFFECTS[pbmte]
    result = set(_V4_SEMANTIC_REPAIRS) | set(_V4_CACHE_REPAIRS[cache])
    if effect["surfaced"]:
        result.add("raw/evaluation_fixtures/NEG_EXT_GATED_PBMTE/expected.yaml")
    if effect["gold"]:
        result.add("raw/evaluation_fixtures/NEG_EXT_GATED_PBMTE/gold.yaml")
    return result


def _validate_v4_repair_manifest(
    manifest: object, ontology_decision_sha256: str, allowed_repairs: set[str],
    predecessor_files: Mapping[str, Mapping[str, object]], repair_payloads: Mapping[str, bytes], cache: str, pbmte: str,
) -> None:
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "ontology_decision_sha256", "predecessor_generation", "repairs", "schema_version",
    } or manifest.get("schema_version") != "pr2164-semantic-gold-repair-manifest-v3" or (
        manifest.get("predecessor_generation") != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
    ) or manifest.get("ontology_decision_sha256") != ontology_decision_sha256:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
    repairs = manifest.get("repairs")
    if not isinstance(repairs, list) or len(repairs) != _V4_YAML_PAYLOAD_COUNT or len(allowed_repairs) != _V4_YAML_PAYLOAD_COUNT:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
    seen: set[str] = set()
    for repair in repairs:
        if not isinstance(repair, Mapping) or set(repair) != {
            "control", "kind", "new_byte_length", "new_sha256", "old_byte_length", "old_sha256", "payload_path", "reason", "target_path",
        } or repair.get("kind") not in {"add", "replace"} or repair.get("control") not in {
            "cache_policy", "pbmte_policy", "semantic_correction",
        }:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
        target = _normalized_path(repair.get("target_path"), "fixture_construction_v4_target_path")
        payload = _normalized_path(repair.get("payload_path"), "fixture_construction_v4_payload_path")
        repair_version = "v3" if target in _V4_V3_REPAIR_TARGETS else "v2"
        expected_payload = f"config/fixture-repairs/pr2164-semantic-gold-{repair_version}/" + "/".join(target.split("/")[2:])
        if target in seen or target not in allowed_repairs or payload != expected_payload:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
        seen.add(target)
        try:
            new_sha = require_sha256(repair.get("new_sha256"))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID") from error
        expected_control = "cache_policy" if target in _V4_CACHE_REPAIRS[cache] else (
            "pbmte_policy" if "NEG_EXT_GATED_PBMTE" in target else "semantic_correction"
        )
        if repair.get("control") != expected_control or repair.get("reason") != _V4_REPAIR_REASONS.get(target):
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
        old = predecessor_files.get(target)
        if repair.get("kind") == "add":
            if old is not None or repair.get("old_sha256") is not None or repair.get("old_byte_length") is not None:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
        else:
            try:
                old_sha = require_sha256(repair.get("old_sha256")); old_length = require_byte_length(repair.get("old_byte_length"))
            except ValueError as error:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID") from error
            if old is None or (old_sha, old_length) != (old["sha256"], old["byte_length"]):
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_PREDECESSOR_INVALID")
        raw = repair_payloads.get(payload)
        try:
            new_length = require_byte_length(repair.get("new_byte_length"))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID") from error
        if raw is None or sha256_bytes(raw) != new_sha or len(raw) != new_length:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_PAYLOAD_INVALID")
    expected_payload_paths = {item.get("payload_path") for item in repairs}
    if (
        seen != allowed_repairs
        or [item.get("target_path") for item in repairs] != sorted(seen)
        or len(repair_payloads) != _V4_YAML_PAYLOAD_COUNT
        or set(repair_payloads) != expected_payload_paths
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID")
    _validate_v4_repair_yaml_batch(repair_payloads)
    try:
        text = {target: repair_payloads[repair["payload_path"]].decode("utf-8") for repair in repairs for target in [repair["target_path"]]}
    except UnicodeDecodeError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID") from error
    cache_text = text["raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml"]
    pmp_text = text["raw/evaluation_fixtures/POS_DIRECT_NUM_PMP/gold.yaml"]
    geilen_text = text["raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/gold.yaml"]
    geilen_expected = text["raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/expected.yaml"]
    asid_text = text["raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/gold.yaml"]
    asid_expected = text["raw/evaluation_fixtures/POS_WARL_ASID_WIDTH/expected.yaml"]
    pbmte_text = text.get("raw/evaluation_fixtures/NEG_EXT_GATED_PBMTE/expected.yaml")
    cand_text = text["raw/evaluation_fixtures/CAND_WARL_FIXED_LEGAL_SET/expected.yaml"]
    cache_domain = _v4_yaml_integer_domain(cache_text, "enum:", "definedBy:")
    pmp_domain = _v4_yaml_integer_domain(pmp_text, "enum:", "definedBy:")
    asid_top_level = {
        line.split(":", 1)[0] for line in asid_text.splitlines()
        if line and not line.startswith((" ", "#")) and ":" in line
    }
    cache_projection_invalid = (
        cache == "unified_cache_block_identity" and "name: CACHE_BLOCK_SIZE" not in cache_text
    ) or (
        cache == "scoped_cache_block_identities" and (
            "name: CACHE_BLOCK_SIZE.management_prefetch" not in cache_text or
            "CACHE_BLOCK_SIZE.zero_block" not in cache_text
        )
    )
    pbmte_projection_invalid = (
        _V4_PBMTE_EFFECTS[pbmte]["surfaced"] and (
            not isinstance(pbmte_text, str) or f"fixture_class: {_V4_PBMTE_EFFECTS[pbmte]['fixture_class']}" not in pbmte_text or (
                _V4_PBMTE_EFFECTS[pbmte]["classify_out"] and (
                    "final_disposition: classify_out" not in pbmte_text or
                    "classify_out_reason: surfaced_classified_out" not in pbmte_text
                )
            ) or (not _V4_PBMTE_EFFECTS[pbmte]["classify_out"] and "final_disposition: classify_out" in pbmte_text)
        )
    ) or (not _V4_PBMTE_EFFECTS[pbmte]["surfaced"] and pbmte_text is not None)
    if cache_projection_invalid or "uniform throughout" in cache_text or "implementation-specific" not in cache_text or cache_domain != {1 << shift for shift in range(64)} or (
        _v4_cache_semantics_invalid(cache_text) or
        pmp_domain != {0, 16, 64} or "minimum: 0" not in geilen_text or
        "direct targets" not in geilen_text or "gold_name: GEILEN" not in geilen_expected or
        "NUM_EXTERNAL_GUEST_INTERRUPTS" not in geilen_expected or "existing_alias" not in geilen_expected or "ASIDLEN" not in asid_text or "ASID_WIDTH" not in asid_expected or
        "existing_alias" not in asid_expected or "versioned_aliases" in asid_text or asid_top_level != {
            "$schema", "kind", "name", "description", "long_name", "schema", "definedBy", "requirements",
        } or pbmte_projection_invalid or "classify_out_reason: isa_fixed_singleton_legal_set" not in cand_text
    ):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SEMANTICS_INVALID")


_V4_YAML_VALIDATOR = r'''
begin
  batch = STDIN.read
  request = JSON.parse(batch)
  raise "request" unless request.is_a?(Array) && request.length == 9
  request.each do |entry|
    raise "entry" unless entry.is_a?(Hash) && entry.keys.sort == ["content_b64", "path"]
    raw = Base64.strict_decode64(entry.fetch("content_b64"))
    stream = Psych.parse_stream(raw)
    raise "documents" unless stream.children.length == 1
    root = stream.children.fetch(0).root
    raise "root" unless root.is_a?(Psych::Nodes::Mapping)
    stack = [root]
    until stack.empty?
      node = stack.pop
      raise "alias" if node.alias?
      raise "anchor" if node.respond_to?(:anchor) && node.anchor
      if node.is_a?(Psych::Nodes::Mapping)
        raise "mapping" unless node.children.length.even?
        seen = {}
        node.children.each_slice(2) do |key, value|
          raise "key" unless key.is_a?(Psych::Nodes::Scalar)
          raise "merge" if key.value == "<<" || key.tag == "tag:yaml.org,2002:merge"
          raise "duplicate" if seen.key?(key.value)
          seen[key.value] = true
          stack << value << key
        end
      elsif node.is_a?(Psych::Nodes::Sequence)
        node.children.each { |child| stack << child }
      elsif !node.is_a?(Psych::Nodes::Scalar)
        raise "node"
      end
    end
  end
  STDOUT.write(JSON.generate({"batch_sha256" => Digest::SHA256.hexdigest(batch), "valid" => true}) + "\n")
rescue StandardError
  exit 2
end
'''
_V4_YAML_PAYLOAD_COUNT = 9
_V4_YAML_MAX_PAYLOAD_BYTES = 64 * 1024
_V4_YAML_MAX_BATCH_BYTES = 256 * 1024
_V4_YAML_MAX_PATH_BYTES = 512
_V4_YAML_MAX_REQUEST_BYTES = 320 * 1024


def _validate_v4_repair_yaml_batch(repair_payloads: Mapping[str, bytes]) -> None:
    """Parse all already-read repair bytes in one fail-closed Psych subprocess."""
    if not isinstance(repair_payloads, Mapping) or len(repair_payloads) != _V4_YAML_PAYLOAD_COUNT or any(
        not isinstance(path, str) or len(path.encode("utf-8")) > _V4_YAML_MAX_PATH_BYTES
        or not isinstance(raw, bytes) or len(raw) > _V4_YAML_MAX_PAYLOAD_BYTES
        for path, raw in repair_payloads.items()
    ) or sum(len(raw) for raw in repair_payloads.values()) > _V4_YAML_MAX_BATCH_BYTES:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID")
    try:
        if any(require_relative_posix_path(path).as_posix() != path for path in repair_payloads):
            raise FilesystemPolicyError("PATH_ESCAPE_DETECTED")
    except FilesystemPolicyError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID") from error
    request = [
        {"content_b64": base64.b64encode(repair_payloads[path]).decode("ascii"), "path": path}
        for path in sorted(repair_payloads)
    ]
    request_raw = canonical_json_bytes(request)
    if len(request_raw) > _V4_YAML_MAX_REQUEST_BYTES:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID")
    ruby = shutil.which("ruby")
    if ruby is None or not Path(ruby).is_absolute():
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID")
    expected = canonical_json_bytes({"batch_sha256": sha256_bytes(request_raw), "valid": True})
    try:
        result = _run_bounded_subprocess(
            [ruby, "--disable-gems", "-rjson", "-rbase64", "-rpsych", "-rdigest", "-e", _V4_YAML_VALIDATOR],
            input_bytes=request_raw, max_stdin_bytes=_V4_YAML_MAX_REQUEST_BYTES,
            max_stdout_bytes=len(expected), max_stderr_bytes=_V4_SUBPROCESS_MAX_STDERR_BYTES, timeout=10,
            env={key: value for key, value in os.environ.items() if key not in {"RUBYOPT", "RUBYLIB"}},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID") from error
    if result.returncode != 0 or result.stdout != expected or result.stderr != b"":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID")


def _v4_cache_semantics_invalid(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return not all(
        phrase in normalized
        for phrase in (
            "finite evaluation domain 2^0 through 2^63",
            "versioned evaluation/udb modeling choice",
            "not an upper bound asserted by the challenge source",
        )
    )


def _validate_v4_cache_semantics(text: str) -> None:
    """Expose the versioned finite-domain assertion for focused regression tests."""
    if _v4_cache_semantics_invalid(text):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SEMANTICS_INVALID")


def _v4_yaml_integer_domain(text: str, start: str, end: str) -> set[int]:
    try:
        section = text.split(start, 1)[1]
    except IndexError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SEMANTICS_INVALID") from error
    if end in section:
        section = section.split(end, 1)[0]
    values = re.findall(r"0x[0-9A-Fa-f]+|(?<![A-Za-z0-9_])-?[0-9]+", section)
    try:
        return {int(value, 0) for value in values}
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_SEMANTICS_INVALID") from error


def _v4_inventory(
    predecessor_files: Mapping[str, Mapping[str, object]], predecessor_classes: Mapping[str, str], pbmte: str, manifest: Mapping[str, object],
) -> dict[str, object]:
    classes = dict(predecessor_classes)
    if _V4_PBMTE_EFFECTS[pbmte]["fixture_class"] == "absent":
        classes.pop("NEG_EXT_GATED_PBMTE")
    else:
        classes["NEG_EXT_GATED_PBMTE"] = str(_V4_PBMTE_EFFECTS[pbmte]["fixture_class"])
    partition = {kind: list(classes.values()).count(kind) for kind in ("candidate", "negative", "positive")}
    repairs = manifest["repairs"]
    assert isinstance(repairs, list)
    raw_count = sum(1 for item in predecessor_files.values() if item["fixture_id"] in classes) + sum(
        1 for item in repairs if item["kind"] == "add"
    )
    return {"fixture_count": len(classes), "partition": partition, "raw_file_count": raw_count}


def _validate_v4_registry(
    registry: object, manifest: Mapping[str, object], ontology_decision_sha256: str, predecessor_registry_sha256: str,
    predecessor_files: Mapping[str, Mapping[str, object]], predecessor_classes: Mapping[str, str], pbmte: str, inventory: Mapping[str, object],
) -> None:
    if not isinstance(registry, Mapping) or set(registry) != {
        "fixture_count", "fixtures", "ontology_decision_sha256", "predecessor_registry_sha256", "raw_file_count", "schema_version",
    } or registry.get("schema_version") != "4" or registry.get("ontology_decision_sha256") != ontology_decision_sha256 or (
        registry.get("predecessor_registry_sha256") != predecessor_registry_sha256
    ) or registry.get("fixture_count") != inventory["fixture_count"] or registry.get("raw_file_count") != inventory["raw_file_count"]:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
    try:
        require_sha256(registry.get("predecessor_registry_sha256"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID") from error
    classes = dict(predecessor_classes)
    if _V4_PBMTE_EFFECTS[pbmte]["fixture_class"] == "absent":
        classes.pop("NEG_EXT_GATED_PBMTE")
    else:
        classes["NEG_EXT_GATED_PBMTE"] = str(_V4_PBMTE_EFFECTS[pbmte]["fixture_class"])
    fixtures = registry.get("fixtures")
    if not isinstance(fixtures, list) or [item.get("fixture_id") if isinstance(item, Mapping) else None for item in fixtures] != sorted(classes):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
    repairs = {item["target_path"]: item for item in manifest["repairs"] if isinstance(item, Mapping)}
    expected_paths = {
        path for path, predecessor in predecessor_files.items() if predecessor["fixture_id"] in classes
    } | {path for path, item in repairs.items() if item["kind"] == "add"}
    actual_paths: set[str] = set()
    registry_repairs: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, Mapping) or set(fixture) != {"files", "fixture_class", "fixture_id"}:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
        fixture_id = fixture.get("fixture_id")
        expected_class = classes.get(str(fixture_id))
        if fixture.get("fixture_class") != expected_class:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
        files = fixture.get("files")
        if not isinstance(files, list) or [item.get("path") if isinstance(item, Mapping) else None for item in files] != sorted(
            item.get("path") for item in files if isinstance(item, Mapping)
        ):
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
        for file in files:
            if not isinstance(file, Mapping) or set(file) != {"byte_length", "origin", "path", "role", "sha256"}:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
            path = _normalized_path(file.get("path"), "fixture_construction_v4_registry_path")
            path_parts = path.split("/")
            if len(path_parts) != 4 or path_parts[:2] != ["raw", "evaluation_fixtures"] or path_parts[2] != fixture_id:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
            try:
                require_byte_length(file.get("byte_length")); require_sha256(file.get("sha256"))
            except ValueError as error:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID") from error
            if path in actual_paths:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
            actual_paths.add(path)
            if file.get("origin") == "repair":
                repair = repairs.get(path)
                if repair is None or (repair.get("new_sha256"), repair.get("new_byte_length"), file.get("role")) != (
                    file.get("sha256"), file.get("byte_length"), _v4_expected_role(path),
                ):
                    raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_CLOSURE_INVALID")
                registry_repairs.add(path)
            elif file.get("origin") == "predecessor":
                predecessor = predecessor_files.get(path)
                if predecessor is None or (file.get("role"), file.get("byte_length"), file.get("sha256")) != (
                    predecessor["role"], predecessor["byte_length"], predecessor["sha256"],
                ) or predecessor["fixture_id"] != fixture_id or path in repairs:
                    raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_PREDECESSOR_INVALID")
            else:
                raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REGISTRY_INVALID")
    if actual_paths != expected_paths or registry_repairs != set(repairs):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_V4_REPAIR_CLOSURE_INVALID")


def _v4_expected_role(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return _FIXTURE_ROLES[name]


def _fixture_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise FixtureRegistryError("FIXTURE_PATH_INVALID")
    try:
        return require_relative_posix_path(value).as_posix()
    except FilesystemPolicyError as error:
        raise FixtureRegistryError(str(error)) from error


def validate_fixture_registry(registry: object) -> dict[str, object]:
    """Validate the finite named PR #2164 set before it can reach construction."""
    if not isinstance(registry, Mapping) or set(registry) != {
        "fixture_count", "fixtures", "pinned_commit_sha", "pinned_tree_sha", "pull_request",
        "raw_file_count", "repository", "schema_version", "snapshot_id",
    }:
        raise FixtureRegistryError("FIXTURE_REGISTRY_INVALID")
    if registry.get("schema_version") != "1" or registry.get("repository") != "riscv/riscv-unified-db":
        raise FixtureRegistryError("FIXTURE_REGISTRY_INVALID")
    if registry.get("snapshot_id") != "evaluation_fixtures" or registry.get("pull_request") != 2164:
        raise FixtureRegistryError("FIXTURE_REGISTRY_IDENTITY_MISMATCH")
    if registry.get("pinned_commit_sha") != _FIXTURE_COMMIT or registry.get("pinned_tree_sha") != _FIXTURE_TREE:
        raise FixtureRegistryError("FIXTURE_REGISTRY_PIN_MISMATCH")
    fixtures = registry.get("fixtures")
    if not isinstance(fixtures, list):
        raise FixtureRegistryError("FIXTURE_REGISTRY_INVALID")
    if not fixtures:
        raise FixtureRegistryError("FIXTURE_REGISTRY_EMPTY")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    total = 0
    for fixture in fixtures:
        if not isinstance(fixture, Mapping) or set(fixture) != {"fixture_class", "fixture_id", "files"}:
            raise FixtureRegistryError("FIXTURE_ENTRY_INVALID")
        fixture_id = fixture.get("fixture_id")
        fixture_class = fixture.get("fixture_class")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise FixtureRegistryError("FIXTURE_ID_INVALID")
        if fixture_id in seen_ids:
            raise FixtureRegistryError("FIXTURE_DUPLICATE")
        seen_ids.add(fixture_id)
        expected = _EXPECTED_FIXTURES.get(fixture_id)
        if expected is None:
            raise FixtureRegistryError("FIXTURE_SET_MISMATCH")
        expected_class, directory, expected_names = expected
        if fixture_class != expected_class:
            raise FixtureRegistryError("FIXTURE_CLASS_MISMATCH")
        files = fixture.get("files")
        if not isinstance(files, list) or not files:
            raise FixtureRegistryError("FIXTURE_FILE_SET_MISMATCH")
        seen_names: set[str] = set()
        normalized_files: list[dict[str, object]] = []
        for file in files:
            if not isinstance(file, Mapping) or set(file) != {
                "filename", "local_bundle_path", "raw_byte_length", "raw_sha256", "role", "upstream_path",
            }:
                raise FixtureRegistryError("FIXTURE_FILE_INVALID")
            filename = file.get("filename")
            if not isinstance(filename, str) or filename in seen_names:
                raise FixtureRegistryError("FIXTURE_FILE_DUPLICATE")
            seen_names.add(filename)
            if filename not in expected_names:
                raise FixtureRegistryError("FIXTURE_FILE_SET_MISMATCH")
            if file.get("role") != _FIXTURE_ROLES[filename]:
                raise FixtureRegistryError("FIXTURE_ROLE_MISMATCH")
            upstream = _fixture_path(file.get("upstream_path"))
            local = _fixture_path(file.get("local_bundle_path"))
            if upstream != f"{_FIXTURE_BASE}/{directory}/{fixture_id}/{filename}" or local != f"raw/evaluation_fixtures/{fixture_id}/{filename}":
                raise FixtureRegistryError("FIXTURE_PATH_MISMATCH")
            try:
                length = require_byte_length(file.get("raw_byte_length"))
                digest = require_sha256(file.get("raw_sha256"))
            except ValueError as error:
                raise FixtureRegistryError("FIXTURE_DIGEST_OR_LENGTH_INVALID") from error
            normalized_files.append({
                "filename": filename, "local_bundle_path": local, "raw_byte_length": length,
                "raw_sha256": digest, "role": _FIXTURE_ROLES[filename], "upstream_path": upstream,
            })
        if set(seen_names) != set(expected_names):
            raise FixtureRegistryError("FIXTURE_FILE_SET_MISMATCH")
        if [item["filename"] for item in normalized_files] != sorted(expected_names):
            raise FixtureRegistryError("FIXTURE_FILE_ORDER_NONDETERMINISTIC")
        normalized.append({"fixture_class": expected_class, "fixture_id": fixture_id, "files": normalized_files})
        total += len(normalized_files)
    if seen_ids != set(_EXPECTED_FIXTURES):
        raise FixtureRegistryError("FIXTURE_SET_MISMATCH")
    if [item["fixture_id"] for item in normalized] != sorted(_EXPECTED_FIXTURES):
        raise FixtureRegistryError("FIXTURE_ORDER_NONDETERMINISTIC")
    if registry.get("fixture_count") != len(_EXPECTED_FIXTURES) or registry.get("raw_file_count") != total or total != 28:
        raise FixtureRegistryError("FIXTURE_COUNT_MISMATCH")
    return {"fixture_count": len(_EXPECTED_FIXTURES), "fixtures": normalized, "raw_file_count": total}


def verify_fixture_registry_git(registry: object, repository: Path) -> None:
    """Prove the exact registry against pinned Git or its published byte archive."""
    normalized = validate_fixture_registry(registry)
    def git_stdout(*arguments: str) -> bytes:
        result = _run_git(repository, *arguments)
        if result.returncode != 0:
            raise FixtureRegistryError("FIXTURE_GIT_OBJECT_UNAVAILABLE")
        return result.stdout
    from .publication import (
        PublicationContractError,
        has_publication_manifest,
        publication_manifest_path,
        validate_publication_manifest,
    )

    portable = has_publication_manifest(repository)
    if portable:
        try:
            publication = validate_publication_manifest(
                repository, publication_manifest_path(repository)
            )
        except PublicationContractError as error:
            raise FixtureRegistryError("FIXTURE_PUBLICATION_INVALID") from error
        provenance = publication.get("historical_provenance")
        if not isinstance(provenance, list) or not any(
            isinstance(item, Mapping) and item.get("commit_sha") == _FIXTURE_COMMIT
            for item in provenance
        ):
            raise FixtureRegistryError("FIXTURE_PUBLICATION_INVALID")
    else:
        legacy_ref = "refs/" + "specchoice/pr-2164-head"
        head = git_stdout("rev-parse", legacy_ref).decode("ascii", "strict").strip()
        if head != _FIXTURE_COMMIT:
            raise FixtureRegistryError("FIXTURE_PR_HEAD_MISMATCH")
        ancestry = _run_git(repository, "merge-base", "--is-ancestor", _FIXTURE_COMMIT, head)
        if ancestry.returncode != 0:
            raise FixtureRegistryError("FIXTURE_PIN_NOT_REACHABLE")
    pinned_available = _run_git(
        repository, "cat-file", "-e", f"{_FIXTURE_COMMIT}^{{commit}}"
    ).returncode == 0
    if pinned_available:
        tree = git_stdout("rev-parse", f"{_FIXTURE_COMMIT}^{{tree}}").decode("ascii", "strict").strip()
        if tree != _FIXTURE_TREE:
            raise FixtureRegistryError("FIXTURE_TREE_MISMATCH")
    for fixture in normalized["fixtures"]:
        assert isinstance(fixture, dict)
        for file in fixture["files"]:
            assert isinstance(file, dict)
            if pinned_available:
                object_ref = f"{_FIXTURE_COMMIT}:{file['upstream_path']}"
                if git_stdout("cat-file", "-t", object_ref).decode("ascii", "strict").strip() != "blob":
                    raise FixtureRegistryError("FIXTURE_NON_REGULAR_FILE")
                raw = git_stdout("show", object_ref)
            else:
                raw = read_portable_fixture_blob(
                    repository, _FIXTURE_COMMIT, str(file["local_bundle_path"])
                )
            if len(raw) != file["raw_byte_length"]:
                raise FixtureRegistryError("FIXTURE_RAW_BYTE_LENGTH_MISMATCH")
            if hashlib.sha256(raw).hexdigest() != file["raw_sha256"]:
                raise FixtureRegistryError("FIXTURE_RAW_SHA256_MISMATCH")


def validate_fixture_closure_proposal(proposal: object) -> dict[str, object]:
    """Validate the compact v3 proposal that binds the full registry by digest."""
    if not isinstance(proposal, Mapping) or set(proposal) != {
        "base_source_snapshots", "fixture_registry", "generation", "pinned_commit_sha",
        "pinned_tree_sha", "schema_version", "status",
    }:
        raise SourceContractProposalError("FIXTURE_CLOSURE_PROPOSAL_INVALID")
    if proposal.get("schema_version") != "1" or proposal.get("status") != "pending_reviewer_approval":
        raise SourceContractProposalError("FIXTURE_CLOSURE_PROPOSAL_INVALID")
    if proposal.get("generation") != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2":
        raise SourceContractProposalError("FIXTURE_CLOSURE_GENERATION_INVALID")
    if proposal.get("pinned_commit_sha") != _FIXTURE_COMMIT or proposal.get("pinned_tree_sha") != _FIXTURE_TREE:
        raise SourceContractProposalError("FIXTURE_CLOSURE_PIN_INVALID")
    normalized: dict[str, object] = {}
    for field, expected_path in (
        ("base_source_snapshots", "config/source_snapshots.json"),
        ("fixture_registry", "config/fixture-registry-pr2164-v1.json"),
    ):
        binding = proposal.get(field)
        if not isinstance(binding, Mapping) or set(binding) != {"path", "sha256"}:
            raise SourceContractProposalError("FIXTURE_CLOSURE_BINDING_INVALID")
        if _normalized_path(binding.get("path"), f"{field}_path") != expected_path:
            raise SourceContractProposalError("FIXTURE_CLOSURE_BINDING_INVALID")
        try:
            normalized[field] = {"path": expected_path, "sha256": require_sha256(binding.get("sha256"))}
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CLOSURE_BINDING_INVALID") from error
    return normalized


def validate_fixture_closure_decision(
    decision: object, proposal: object, *, proposal_path: str, proposal_sha256: str
) -> dict[str, object]:
    """Allow local candidate construction only; never authorise acceptance or publication."""
    validate_fixture_closure_proposal(proposal)
    if not isinstance(decision, Mapping) or set(decision) != {
        "approval_scope", "authorization", "proposal", "reviewer", "schema_version", "state",
    }:
        raise SourceContractProposalError("FIXTURE_CLOSURE_DECISION_INVALID")
    if decision.get("schema_version") != "1" or decision.get("approval_scope") != "local_candidate_construction_only" or decision.get("state") != "candidate_construction_authorized":
        raise SourceContractProposalError("FIXTURE_CLOSURE_DECISION_INVALID")
    if decision.get("authorization") != {
        "candidate_construction_authorized": True,
        "downstream_eligible": False,
        "external_publication_authorized": False,
    }:
        raise SourceContractProposalError("FIXTURE_CLOSURE_AUTHORIZATION_INVALID")
    if decision.get("reviewer") != {"approval_token": "authorize-v7-local-receipt-basis-only"}:
        raise SourceContractProposalError("FIXTURE_CLOSURE_REVIEWER_INVALID")
    binding = decision.get("proposal")
    if not isinstance(binding, Mapping) or set(binding) != {"path", "sha256"}:
        raise SourceContractProposalError("FIXTURE_CLOSURE_DECISION_INVALID")
    if _normalized_path(binding.get("path"), "fixture_closure_proposal_path") != proposal_path:
        raise SourceContractProposalError("FIXTURE_CLOSURE_PROPOSAL_MISMATCH")
    try:
        digest = require_sha256(binding.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CLOSURE_PROPOSAL_MISMATCH") from error
    if digest != proposal_sha256:
        raise SourceContractProposalError("FIXTURE_CLOSURE_PROPOSAL_MISMATCH")
    return dict(decision)


def validate_fixture_construction_proposal(proposal: object) -> dict[str, object]:
    """Validate the closed, non-authoritative verifier-rooted-v3 proposal."""
    if not isinstance(proposal, Mapping) or set(proposal) != {
        "candidate_identity_contract", "fixture_inventory", "fixed_source", "generation",
        "phase_gate_receipt", "predecessor_candidate", "protected_path_baseline",
        "schema_version", "source_controls", "status", "verifier_artifacts",
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PROPOSAL_FIELDS_INVALID")
    if proposal.get("schema_version") != "1" or proposal.get("status") != "pending_human_construction_decision":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PROPOSAL_INVALID")
    if proposal.get("generation") != _FIXTURE_CONSTRUCTION_GENERATION:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_GENERATION_INVALID")
    identity_contract = _require_mapping(
        proposal.get("candidate_identity_contract"), "FIXTURE_CONSTRUCTION_IDENTITY_CONTRACT_INVALID"
    )
    if identity_contract != {
        "core_field": "core_sha256",
        "root_field": "root_sha256",
        "snapshot_field": "snapshot_manifest_sha256",
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_IDENTITY_CONTRACT_INVALID")
    fixed_source = _require_mapping(proposal.get("fixed_source"), "FIXTURE_CONSTRUCTION_SOURCE_INVALID")
    if fixed_source.get("commit") != _FIXTURE_CONSTRUCTION_SOURCE_COMMIT or set(fixed_source) != {
        "commit", "implementation_diff"
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_SOURCE_INVALID")
    implementation_diff = _require_mapping(
        fixed_source.get("implementation_diff"), "FIXTURE_CONSTRUCTION_IMPLEMENTATION_DIFF_INVALID"
    )
    if set(implementation_diff) != {"changed_verifier_artifacts", "predecessor_generation"} or implementation_diff.get(
        "predecessor_generation"
    ) != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_IMPLEMENTATION_DIFF_INVALID")
    changed = implementation_diff.get("changed_verifier_artifacts")
    if not isinstance(changed, list) or changed != sorted(changed) or set(changed) != {
        "verifier/specchoice_evidence/filesystem.py", "verifier/specchoice_evidence/verify.py"
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_IMPLEMENTATION_DIFF_INVALID")
    inventory = _require_mapping(proposal.get("fixture_inventory"), "FIXTURE_CONSTRUCTION_INVENTORY_INVALID")
    if set(inventory) != {"fixture_count", "partition", "raw_file_count", "registry"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_INVENTORY_INVALID")
    if inventory.get("fixture_count") != 11 or inventory.get("raw_file_count") != 28 or inventory.get("partition") != {
        "candidate": 1, "negative": 4, "positive": 6
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_INVENTORY_INVALID")
    registry = _require_mapping(inventory.get("registry"), "FIXTURE_CONSTRUCTION_REGISTRY_INVALID")
    if registry.get("path") != "config/fixture-registry-pr2164-v1.json" or set(registry) != {"path", "sha256"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_REGISTRY_INVALID")
    if registry.get("sha256") != _FIXTURE_CONSTRUCTION_REGISTRY_SHA256:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_REGISTRY_INVALID")
    predecessor = _require_mapping(proposal.get("predecessor_candidate"), "FIXTURE_CONSTRUCTION_PREDECESSOR_INVALID")
    if set(predecessor) != {
        "candidate_relative_path", "core_sha256", "generation", "root_sha256", "snapshot_manifest_sha256"
    } or predecessor.get("generation") != "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PREDECESSOR_INVALID")
    _normalized_path(predecessor.get("candidate_relative_path"), "fixture_construction_predecessor_path")
    for field in ("core_sha256", "root_sha256", "snapshot_manifest_sha256"):
        try:
            require_sha256(predecessor.get(field))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PREDECESSOR_INVALID") from error
    controls = proposal.get("source_controls")
    if not isinstance(controls, list) or len(controls) != len(_FIXTURE_CONSTRUCTION_CONTROL_PATHS):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_CONTROLS_INVALID")
    normalized_controls: list[dict[str, str]] = []
    for control in controls:
        if not isinstance(control, Mapping) or set(control) != {"path", "sha256"}:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_CONTROLS_INVALID")
        path = _normalized_path(control.get("path"), "fixture_construction_control_path")
        try:
            digest = require_sha256(control.get("sha256"))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_CONTROLS_INVALID") from error
        normalized_controls.append({"path": path, "sha256": digest})
    if [item["path"] for item in normalized_controls] != list(_FIXTURE_CONSTRUCTION_CONTROL_PATHS):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_CONTROLS_INVALID")
    receipt = _require_mapping(proposal.get("phase_gate_receipt"), "FIXTURE_CONSTRUCTION_GATE_RECEIPT_INVALID")
    if set(receipt) != {"path", "sha256"} or receipt.get("path") != "phase2/source-authority.json":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_GATE_RECEIPT_INVALID")
    try:
        require_sha256(receipt.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_GATE_RECEIPT_INVALID") from error
    baseline = _require_mapping(proposal.get("protected_path_baseline"), "FIXTURE_CONSTRUCTION_BASELINE_INVALID")
    if baseline != {"commit": _FIXTURE_CONSTRUCTION_SOURCE_COMMIT, "result": "clean"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_BASELINE_INVALID")
    artifacts = proposal.get("verifier_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(_FIXTURE_CONSTRUCTION_VERIFIER_PATHS):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_VERIFIER_INVALID")
    normalized_artifacts: list[dict[str, object]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {"byte_length", "path", "sha256"}:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_VERIFIER_INVALID")
        path = _normalized_path(artifact.get("path"), "fixture_construction_verifier_path")
        try:
            normalized_artifacts.append({
                "byte_length": require_byte_length(artifact.get("byte_length")),
                "path": path,
                "sha256": require_sha256(artifact.get("sha256")),
            })
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CONSTRUCTION_VERIFIER_INVALID") from error
    if [item["path"] for item in normalized_artifacts] != list(_FIXTURE_CONSTRUCTION_VERIFIER_PATHS):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_VERIFIER_INVALID")
    return dict(proposal)


def validate_fixture_construction_decision(
    decision: object, proposal: object, *, proposal_path: str, proposal_sha256: str
) -> dict[str, object]:
    """Validate a human-owned authorize/reject construction disposition only."""
    validate_fixture_construction_proposal(proposal)
    if not isinstance(decision, Mapping) or set(decision) != {
        "decision", "decision_timestamp", "fixed_source_commit", "proposal", "rationale",
        "reviewer_identity", "schema_version",
    }:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_DECISION_FIELDS_INVALID")
    if decision.get("schema_version") != "1" or decision.get("decision") not in {"authorize", "reject"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_DECISION_INVALID")
    for field in ("decision_timestamp", "rationale", "reviewer_identity"):
        _require_string(decision, field)
    fixed_source = _require_mapping(proposal.get("fixed_source"), "FIXTURE_CONSTRUCTION_SOURCE_INVALID")
    if decision.get("fixed_source_commit") != fixed_source.get("commit"):
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_SOURCE_MISMATCH")
    binding = _require_mapping(decision.get("proposal"), "FIXTURE_CONSTRUCTION_DECISION_PROPOSAL_INVALID")
    if set(binding) != {"generation", "path", "sha256"}:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_DECISION_PROPOSAL_INVALID")
    if binding.get("generation") != proposal.get("generation") or _normalized_path(
        binding.get("path"), "fixture_construction_proposal_path"
    ) != proposal_path:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PROPOSAL_MISMATCH")
    try:
        digest = require_sha256(binding.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PROPOSAL_MISMATCH") from error
    if digest != proposal_sha256:
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_PROPOSAL_MISMATCH")
    return dict(decision)


def require_fixture_construction_authorization(decision: Mapping[str, object]) -> None:
    """Permit construction only for the human-authored authorize disposition."""
    if decision.get("decision") != "authorize":
        raise SourceContractProposalError("FIXTURE_CONSTRUCTION_NOT_AUTHORIZED")


def _require_string(mapping: Mapping[str, object], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise SourceContractProposalError(f"PROPOSAL_{field.upper()}_MISSING")
    return value


def _require_mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SourceContractProposalError(code)
    return value


def _normalized_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceContractProposalError(f"PROPOSAL_{field.upper()}_MISSING")
    try:
        return require_relative_posix_path(value).as_posix()
    except FilesystemPolicyError as error:
        raise SourceContractProposalError(str(error)) from error


def _require_git_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 40:
        raise SourceContractProposalError(f"PROPOSAL_{field.upper()}_INVALID")
    try:
        int(value, 16)
    except ValueError as error:
        raise SourceContractProposalError(f"PROPOSAL_{field.upper()}_INVALID") from error
    return value


def _validate_transforms(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise SourceContractProposalError("PROPOSAL_DECLARED_TRANSFORMS_MISSING")
    normalized: list[dict[str, object]] = []
    for transform in value:
        mapping = _require_mapping(transform, "PROPOSAL_TRANSFORM_INVALID")
        parameters = mapping.get("parameters")
        if not isinstance(parameters, Mapping):
            raise SourceContractProposalError("PROPOSAL_TRANSFORM_PARAMETERS_MISSING")
        normalized.append(
            {
                "name": _require_string(mapping, "name"),
                "parameters": dict(parameters),
                "proposed_derived_path": _normalized_path(
                    mapping.get("proposed_derived_path"), "proposed_derived_path"
                ),
                "version": _require_string(mapping, "version"),
            }
        )
    return normalized


def validate_source_contract_proposal(proposal: object) -> dict[str, object]:
    """Validate complete reviewer-pending source custody fields without publishing."""
    payload = _require_mapping(proposal, "INVALID_SOURCE_CONTRACT_PROPOSAL")
    if payload.get("schema_version") != "1":
        raise SourceContractProposalError("UNSUPPORTED_SOURCE_CONTRACT_PROPOSAL_SCHEMA")
    if payload.get("status") != "pending_reviewer_approval":
        raise SourceContractProposalError("SOURCE_CONTRACT_PROPOSAL_NOT_PENDING")
    if payload.get("proposed_contract_version") not in {"2", "3"}:
        raise SourceContractProposalError("INVALID_PROPOSED_CONTRACT_VERSION")
    _require_string(payload, "requested_generation_label")
    base_contract = _require_mapping(payload.get("base_frozen_contract"), "BASE_CONTRACT_MISSING")
    _normalized_path(base_contract.get("path"), "base_contract_path")
    try:
        require_sha256(base_contract.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("BASE_CONTRACT_SHA256_INVALID") from error
    rejected = _require_mapping(payload.get("historical_rejected_receipt"), "REJECTED_RECEIPT_MISSING")
    _normalized_path(rejected.get("path"), "historical_rejected_receipt_path")
    try:
        require_sha256(rejected.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("REJECTED_RECEIPT_SHA256_INVALID") from error

    raw_snapshots = payload.get("snapshots")
    if not isinstance(raw_snapshots, list) or not raw_snapshots:
        raise SourceContractProposalError("PROPOSAL_SNAPSHOTS_EMPTY")
    snapshots: dict[str, dict[str, object]] = {}
    for raw_snapshot in raw_snapshots:
        snapshot = _require_mapping(raw_snapshot, "PROPOSAL_SNAPSHOT_INVALID")
        snapshot_id = _require_string(snapshot, "snapshot_id")
        if snapshot_id in snapshots:
            raise SourceContractProposalError("PROPOSAL_SNAPSHOT_DUPLICATE")
        pull_request = snapshot.get("pull_request")
        if isinstance(pull_request, bool) or not isinstance(pull_request, int) or pull_request < 1:
            raise SourceContractProposalError("PROPOSAL_PULL_REQUEST_INVALID")
        for field in ("pinned_commit_sha", "pinned_tree_sha", "canonical_pr_head_sha"):
            _require_git_sha(snapshot.get(field), field)
        reachability = snapshot.get("reachability")
        if reachability not in {"equal_head", "reachable_ancestor"}:
            raise SourceContractProposalError("PROPOSAL_REACHABILITY_INVALID")
        change_control = snapshot.get("change_control")
        if change_control not in {"unchanged", "versioned_correction"}:
            raise SourceContractProposalError("PROPOSAL_CHANGE_CONTROL_INVALID")
        snapshots[snapshot_id] = dict(snapshot)
    if list(snapshots) != sorted(snapshots):
        raise SourceContractProposalError("PROPOSAL_SNAPSHOT_ORDER_NONDETERMINISTIC")

    raw_files = payload.get("consumed_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise SourceContractProposalError("PROPOSAL_CONSUMED_FILES_EMPTY")
    normalized_files: list[dict[str, object]] = []
    identities: set[tuple[str, str]] = set()
    local_paths: set[str] = set()
    for raw_file in raw_files:
        file = _require_mapping(raw_file, "PROPOSAL_CONSUMED_FILE_INVALID")
        snapshot_id = _require_string(file, "snapshot_id")
        if snapshot_id not in snapshots:
            raise SourceContractProposalError("PROPOSAL_FILE_SNAPSHOT_UNKNOWN")
        upstream_path = _normalized_path(file.get("upstream_path"), "upstream_path")
        local_bundle_path = _normalized_path(file.get("local_bundle_path"), "local_bundle_path")
        identity = (snapshot_id, upstream_path)
        if identity in identities or local_bundle_path in local_paths:
            raise SourceContractProposalError("PROPOSAL_CONSUMED_FILE_DUPLICATE")
        identities.add(identity)
        local_paths.add(local_bundle_path)
        try:
            raw_byte_length = require_byte_length(file.get("raw_byte_length"))
            raw_sha256 = require_sha256(file.get("raw_sha256"))
        except ValueError as error:
            raise SourceContractProposalError("PROPOSAL_RAW_DIGEST_OR_LENGTH_INVALID") from error
        if file.get("raw_authoritative") is not True:
            raise SourceContractProposalError("PROPOSAL_RAW_AUTHORITY_MISSING")
        normalized_files.append(
            {
                "declared_transforms": _validate_transforms(file.get("declared_transforms")),
                "experimental_role": _require_string(file, "experimental_role"),
                "local_bundle_path": local_bundle_path,
                "raw_authoritative": True,
                "raw_byte_length": raw_byte_length,
                "raw_sha256": raw_sha256,
                "snapshot_id": snapshot_id,
                "upstream_path": upstream_path,
                "why_consumed": _require_string(file, "why_consumed"),
            }
        )
    if normalized_files != sorted(
        normalized_files,
        key=lambda item: (str(item["snapshot_id"]), str(item["upstream_path"]), str(item["local_bundle_path"])),
    ):
        raise SourceContractProposalError("PROPOSAL_CONSUMED_FILE_ORDER_NONDETERMINISTIC")
    return {"consumed_files": normalized_files, "snapshots": snapshots}


def _approved_contract(proposal: Mapping[str, object]) -> dict[str, object]:
    """Return the exact proposal projection a proposal-only decision may bind."""
    return {
        "base_frozen_contract": proposal["base_frozen_contract"],
        "consumed_files": proposal["consumed_files"],
        "historical_rejected_receipt": proposal["historical_rejected_receipt"],
        "proposed_contract_version": proposal["proposed_contract_version"],
        "requested_generation_label": proposal["requested_generation_label"],
        "snapshots": proposal["snapshots"],
    }


def validate_source_publication_decision(
    decision: object,
    proposal: object,
    *,
    proposal_path: str,
    proposal_sha256: str,
) -> dict[str, object]:
    """Validate a hash-bound approval with explicit, non-escalating authority."""
    validate_source_contract_proposal(proposal)
    proposal_payload = _require_mapping(proposal, "INVALID_SOURCE_CONTRACT_PROPOSAL")
    payload = _require_mapping(decision, "INVALID_SOURCE_PUBLICATION_DECISION")
    expected_fields = {
        "approval_scope",
        "approved_contract",
        "authorization",
        "proposal",
        "reviewer",
        "schema_version",
        "state",
    }
    if set(payload) != expected_fields:
        raise SourceContractProposalError("SOURCE_DECISION_FIELDS_INVALID")
    if payload.get("schema_version") != "1":
        raise SourceContractProposalError("UNSUPPORTED_SOURCE_DECISION_SCHEMA")
    approval_scope = payload.get("approval_scope")
    state = payload.get("state")
    if approval_scope not in {"proposal_only", "candidate_construction_only"}:
        raise SourceContractProposalError("SOURCE_DECISION_SCOPE_INVALID")
    expected_state = {
        "proposal_only": "contract_approved",
        "candidate_construction_only": "candidate_construction_authorized",
    }[approval_scope]
    if state != expected_state:
        raise SourceContractProposalError("SOURCE_DECISION_STATE_INVALID")

    proposal_binding = _require_mapping(payload.get("proposal"), "SOURCE_DECISION_PROPOSAL_MISSING")
    if set(proposal_binding) != {"path", "sha256"}:
        raise SourceContractProposalError("SOURCE_DECISION_PROPOSAL_BINDING_INVALID")
    if _normalized_path(proposal_binding.get("path"), "decision_proposal_path") != proposal_path:
        raise SourceContractProposalError("SOURCE_DECISION_PROPOSAL_PATH_MISMATCH")
    try:
        proposal_digest = require_sha256(proposal_binding.get("sha256"))
    except ValueError as error:
        raise SourceContractProposalError("SOURCE_DECISION_PROPOSAL_SHA256_INVALID") from error
    if proposal_digest != proposal_sha256:
        raise SourceContractProposalError("SOURCE_DECISION_PROPOSAL_SHA256_MISMATCH")

    approved_contract = _require_mapping(
        payload.get("approved_contract"), "SOURCE_DECISION_CONTRACT_MISSING"
    )
    if dict(approved_contract) != _approved_contract(proposal_payload):
        raise SourceContractProposalError("SOURCE_DECISION_CONTRACT_MISMATCH")
    reviewer = _require_mapping(payload.get("reviewer"), "SOURCE_DECISION_REVIEWER_MISSING")
    expected_reviewer = {
        "proposal_only": {"approval_token": "approve-proposal-only"},
        "candidate_construction_only": {
            "approval_token": "authorize-candidate-construction-only"
        },
    }[approval_scope]
    if reviewer != expected_reviewer:
        raise SourceContractProposalError("SOURCE_DECISION_REVIEWER_APPROVAL_INVALID")
    authorization = _require_mapping(
        payload.get("authorization"), "SOURCE_DECISION_AUTHORIZATION_MISSING"
    )
    expected_authorization = {
        "proposal_only": {
            "accepted_publication_authorized": False,
            "candidate_construction_authorized": False,
            "source_extraction_authorized": False,
        },
        "candidate_construction_only": {
            "accepted_publication_authorized": False,
            "candidate_construction_authorized": True,
            "source_extraction_authorized": True,
        },
    }[approval_scope]
    if dict(authorization) != expected_authorization:
        raise SourceContractProposalError("SOURCE_DECISION_AUTHORIZATION_INVALID")
    return dict(payload)


def require_source_extraction_authorization(decision: Mapping[str, object]) -> None:
    """Fail closed unless a later, separately authorized decision permits extraction."""
    authorization = _require_mapping(
        decision.get("authorization"), "SOURCE_DECISION_AUTHORIZATION_MISSING"
    )
    if authorization.get("source_extraction_authorized") is not True:
        raise SourceContractProposalError("SOURCE_EXTRACTION_NOT_AUTHORIZED")


def require_candidate_construction_authorization(decision: Mapping[str, object]) -> None:
    """Fail closed unless a later decision expressly permits candidate construction."""
    authorization = _require_mapping(
        decision.get("authorization"), "SOURCE_DECISION_AUTHORIZATION_MISSING"
    )
    if authorization.get("candidate_construction_authorized") is not True:
        raise SourceContractProposalError("CANDIDATE_CONSTRUCTION_NOT_AUTHORIZED")


def require_accepted_publication_authorization(decision: Mapping[str, object]) -> None:
    """Fail closed unless a later decision expressly permits accepted publication."""
    authorization = _require_mapping(
        decision.get("authorization"), "SOURCE_DECISION_AUTHORIZATION_MISSING"
    )
    if "external_publication_authorized" in authorization:
        if authorization.get("external_publication_authorized") is not True:
            raise SourceContractProposalError("EXTERNAL_PUBLICATION_NOT_AUTHORIZED")
        return
    if authorization.get("accepted_publication_authorized") is not True:
        raise SourceContractProposalError("ACCEPTED_PUBLICATION_NOT_AUTHORIZED")


def validate_local_accepted_generation_decision(
    decision: object, *, allow_historical: bool = False
) -> dict[str, object]:
    """Validate the local-only reviewer disposition without granting publication authority."""
    payload = _require_mapping(decision, "INVALID_LOCAL_ACCEPTANCE_DECISION")
    expected_fields = {
        "approval_scope",
        "approved_generation",
        "authorization",
        "reviewed_receipt_basis_sha256",
        "reviewer",
        "schema_version",
        "state",
    }
    schema_version = payload.get("schema_version")
    if schema_version == "3":
        expected_fields |= {
            "committed_boundary_projection_sha256",
            "phase_start_baseline_sha256",
            "reviewed_revision",
        }
    if set(payload) != expected_fields:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_FIELDS_INVALID")
    if schema_version not in {"2", "3"}:
        raise SourceContractProposalError("UNSUPPORTED_LOCAL_ACCEPTANCE_DECISION_SCHEMA")
    if schema_version == "2" and not allow_historical:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_HISTORICAL_DECISION_REQUIRES_EXPLICIT_PATH")
    if payload.get("approval_scope") != "local_accepted_generation_only":
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_SCOPE_INVALID")
    if payload.get("state") != "local_accepted_generation_authorized":
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_STATE_INVALID")
    reviewer = _require_mapping(payload.get("reviewer"), "LOCAL_ACCEPTANCE_REVIEWER_MISSING")
    if dict(reviewer) != {"disposition": "approved_local_only"}:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REVIEWER_INVALID")
    authorization = _require_mapping(payload.get("authorization"), "LOCAL_ACCEPTANCE_AUTHORIZATION_MISSING")
    if dict(authorization) != {
        "external_publication_authorized": False,
        "local_accepted_generation_authorized": True,
    }:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_AUTHORIZATION_INVALID")
    binding = _require_mapping(payload.get("approved_generation"), "LOCAL_ACCEPTANCE_BINDING_MISSING")
    if set(binding) != {
        "candidate_relative_path",
        "core_sha256",
        "generation",
        "root_sha256",
        "snapshot_manifest_sha256",
    }:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_BINDING_INVALID")
    _normalized_path(binding.get("candidate_relative_path"), "candidate_relative_path")
    _require_string(binding, "generation")
    for field in ("core_sha256", "root_sha256", "snapshot_manifest_sha256"):
        try:
            require_sha256(binding.get(field))
        except ValueError as error:
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_BINDING_INVALID") from error
    try:
        require_sha256(payload.get("reviewed_receipt_basis_sha256"))
    except ValueError as error:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_RECEIPT_BASIS_INVALID") from error
    if schema_version == "3":
        revision = payload.get("reviewed_revision")
        if not isinstance(revision, str) or len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_REVIEWED_REVISION_INVALID")
        for field in ("phase_start_baseline_sha256", "committed_boundary_projection_sha256"):
            try:
                require_sha256(payload.get(field))
            except ValueError as error:
                raise SourceContractProposalError("LOCAL_ACCEPTANCE_PROJECTION_BINDING_INVALID") from error
    return dict(payload)


def require_local_accepted_generation_authorization(
    decision: Mapping[str, object], identity: Mapping[str, object], snapshot_manifest_sha256: str,
    *, allow_historical: bool = False,
) -> None:
    """Require exact local-only authority for one already-verified candidate identity."""
    validated = validate_local_accepted_generation_decision(decision, allow_historical=allow_historical)
    binding = _require_mapping(validated["approved_generation"], "LOCAL_ACCEPTANCE_BINDING_MISSING")
    for field in ("generation", "root_sha256", "manifest_sha256"):
        expected_field = "core_sha256" if field == "manifest_sha256" else field
        if binding.get(expected_field) != identity.get(field):
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_IDENTITY_MISMATCH")
    if binding.get("snapshot_manifest_sha256") != snapshot_manifest_sha256:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_SNAPSHOT_MISMATCH")


def validate_fixture_closure_local_acceptance_decision(decision: object) -> dict[str, object]:
    """Validate the v3 fixture-only local acceptance authority.

    This deliberately has a separate schema from the historical generic local
    acceptance decision.  It binds the registry and immutable v7 restart lineage,
    which are material to downstream fixture completeness.
    """
    payload = _require_mapping(decision, "FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID")
    if set(payload) != {
        "approval_scope", "approved_generation", "authorization", "fixture_registry_sha256",
        "reviewer", "schema_version", "state", "v7_basis",
    }:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_DECISION_FIELDS_INVALID")
    if payload.get("schema_version") != "1" or payload.get("approval_scope") != "fixture_closure_local_acceptance_only" or payload.get("state") != "fixture_closure_local_acceptance_authorized":
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID")
    if _require_mapping(payload.get("reviewer"), "FIXTURE_CLOSURE_ACCEPTANCE_REVIEWER_INVALID") != {"disposition": "approved_local_only"}:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_REVIEWER_INVALID")
    if _require_mapping(payload.get("authorization"), "FIXTURE_CLOSURE_ACCEPTANCE_AUTHORIZATION_INVALID") != {
        "external_publication_authorized": False,
        "fixture_closure_local_acceptance_authorized": True,
    }:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_AUTHORIZATION_INVALID")
    binding = _require_mapping(payload.get("approved_generation"), "FIXTURE_CLOSURE_ACCEPTANCE_BINDING_INVALID")
    if set(binding) != {"candidate_relative_path", "core_sha256", "generation", "root_sha256", "snapshot_manifest_sha256"}:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BINDING_INVALID")
    _normalized_path(binding.get("candidate_relative_path"), "fixture_closure_candidate_relative_path")
    _require_string(binding, "generation")
    for field in ("core_sha256", "root_sha256", "snapshot_manifest_sha256"):
        try:
            require_sha256(binding.get(field))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BINDING_INVALID") from error
    try:
        require_sha256(payload.get("fixture_registry_sha256"))
    except ValueError as error:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_INVALID") from error
    basis = _require_mapping(payload.get("v7_basis"), "FIXTURE_CLOSURE_ACCEPTANCE_BASIS_INVALID")
    if set(basis) != {"allowlist_sha256", "baseline_sha256", "restart_receipt_sha256", "reviewed_revision"}:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BASIS_INVALID")
    revision = basis.get("reviewed_revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BASIS_INVALID")
    for field in ("allowlist_sha256", "baseline_sha256", "restart_receipt_sha256"):
        try:
            require_sha256(basis.get(field))
        except ValueError as error:
            raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BASIS_INVALID") from error
    return dict(payload)


def require_fixture_closure_local_acceptance_authorization(
    decision: object, identity: Mapping[str, object], snapshot_manifest_sha256: str,
    registry_sha256: str, v7_basis: Mapping[str, object],
) -> None:
    """Require exact authority for a current, complete fixture candidate."""
    payload = validate_fixture_closure_local_acceptance_decision(decision)
    binding = _require_mapping(payload["approved_generation"], "FIXTURE_CLOSURE_ACCEPTANCE_BINDING_INVALID")
    for actual, bound in (("generation", "generation"), ("manifest_sha256", "core_sha256"), ("root_sha256", "root_sha256")):
        if binding.get(bound) != identity.get(actual):
            raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_IDENTITY_MISMATCH")
    if binding.get("snapshot_manifest_sha256") != snapshot_manifest_sha256:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_SNAPSHOT_MISMATCH")
    if payload.get("fixture_registry_sha256") != registry_sha256:
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_MISMATCH")
    if payload.get("v7_basis") != dict(v7_basis):
        raise SourceContractProposalError("FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH")


def _v10_identity(value: object, code: str) -> dict[str, object]:
    payload = _require_mapping(value, code)
    if set(payload) != {"core_sha256", "generation", "root_sha256", "snapshot_manifest_sha256"}:
        raise SourceContractProposalError(code)
    _require_string(payload, "generation")
    for field in ("core_sha256", "root_sha256", "snapshot_manifest_sha256"):
        try:
            require_sha256(payload.get(field))
        except ValueError as error:
            raise SourceContractProposalError(code) from error
    return dict(payload)


def _v10_verifiers(value: object, code: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) != 5:
        raise SourceContractProposalError(code)
    paths: list[str] = []
    normalized: list[dict[str, object]] = []
    for entry in value:
        payload = _require_mapping(entry, code)
        if set(payload) != {"byte_length", "path", "sha256"}:
            raise SourceContractProposalError(code)
        try:
            length = require_byte_length(payload.get("byte_length"))
            digest = require_sha256(payload.get("sha256"))
            path = require_relative_posix_path(payload.get("path")).as_posix()
        except (FilesystemPolicyError, ValueError) as error:
            raise SourceContractProposalError(code) from error
        paths.append(path)
        normalized.append({"byte_length": length, "path": path, "sha256": digest})
    if paths != sorted(paths) or len(set(paths)) != 5:
        raise SourceContractProposalError(code)
    return normalized


def validate_local_acceptance_request_v10(request: object) -> dict[str, object]:
    """Validate the machine-only v10 acceptance request without granting authority."""
    payload = _require_mapping(request, "LOCAL_ACCEPTANCE_REQUEST_V10_INVALID")
    required = {
        "authorization", "candidate", "construction", "fixed_source_commit", "fixture_inventory",
        "phase_gate_receipt", "projected_accepted", "protected_path_baseline", "requested_targets",
        "schema_version", "source_controls", "status", "verifier_artifacts",
    }
    if set(payload) != required or payload.get("schema_version") != "10" or payload.get("status") != "pending_independent_local_acceptance":
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_INVALID")
    if _require_mapping(payload.get("authorization"), "LOCAL_ACCEPTANCE_REQUEST_V10_INVALID") != {
        "external_publication_authorized": False,
        "local_acceptance_decision_authorized": False,
    }:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_INVALID")
    candidate = _v10_identity(payload.get("candidate"), "LOCAL_ACCEPTANCE_REQUEST_V10_IDENTITY_INVALID")
    projected = _v10_identity(payload.get("projected_accepted"), "LOCAL_ACCEPTANCE_REQUEST_V10_IDENTITY_INVALID")
    if candidate["generation"] != _FIXTURE_CONSTRUCTION_GENERATION or projected["generation"] != candidate["generation"]:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_IDENTITY_INVALID")
    construction = _require_mapping(payload.get("construction"), "LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID")
    if set(construction) != {"audit", "decision", "proposal"}:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID")
    for name in ("audit", "decision", "proposal"):
        entry = _require_mapping(construction.get(name), "LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID")
        if set(entry) != {"path", "sha256"}:
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID")
        try:
            require_relative_posix_path(entry.get("path"))
            require_sha256(entry.get("sha256"))
        except (FilesystemPolicyError, ValueError) as error:
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_CONSTRUCTION_INVALID") from error
    inventory = _require_mapping(payload.get("fixture_inventory"), "LOCAL_ACCEPTANCE_REQUEST_V10_INVENTORY_INVALID")
    if inventory.get("fixture_count") != 11 or inventory.get("raw_file_count") != 28 or inventory.get("partition") != {"candidate": 1, "negative": 4, "positive": 6}:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_INVENTORY_INVALID")
    verifier_artifacts = _v10_verifiers(payload.get("verifier_artifacts"), "LOCAL_ACCEPTANCE_REQUEST_V10_VERIFIERS_INVALID")
    controls = payload.get("source_controls")
    if not isinstance(controls, list) or len(controls) != 4:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_CONTROLS_INVALID")
    for field in ("phase_gate_receipt", "protected_path_baseline"):
        entry = _require_mapping(payload.get(field), "LOCAL_ACCEPTANCE_REQUEST_V10_PROJECTION_INVALID")
        if entry.get("result") != "clean":
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_PROJECTION_INVALID")
    targets = _require_mapping(payload.get("requested_targets"), "LOCAL_ACCEPTANCE_REQUEST_V10_TARGETS_INVALID")
    if set(targets) != {"accepted_bundle", "historical_authority", "pending_authority", "transition"}:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_TARGETS_INVALID")
    for target in targets.values():
        try:
            require_relative_posix_path(target)
        except FilesystemPolicyError as error:
            raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_TARGETS_INVALID") from error
    if payload.get("fixed_source_commit") != _FIXTURE_CONSTRUCTION_SOURCE_COMMIT:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_REQUEST_V10_SOURCE_INVALID")
    return {**dict(payload), "candidate": candidate, "projected_accepted": projected, "verifier_artifacts": verifier_artifacts}


def validate_local_acceptance_decision_v10(
    decision: object, request: object, request_sha256: str,
) -> dict[str, object]:
    """Validate an independently authored accept/reject decision bound to one request."""
    normalized_request = validate_local_acceptance_request_v10(request)
    payload = _require_mapping(decision, "LOCAL_ACCEPTANCE_DECISION_V10_INVALID")
    required = {
        "candidate", "decision", "external_publication_authorized", "projected_accepted", "rationale",
        "request_sha256", "reviewer_identity", "reviewed_at", "schema_version", "verifier_artifacts",
    }
    if set(payload) != required or payload.get("schema_version") != "10" or payload.get("decision") not in {"accept", "reject"}:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_INVALID")
    if payload.get("external_publication_authorized") is not False:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_PUBLICATION_INVALID")
    if not all(isinstance(payload.get(field), str) and payload[field] for field in ("rationale", "reviewer_identity", "reviewed_at")):
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_REVIEWER_INVALID")
    try:
        request_digest = require_sha256(payload.get("request_sha256"))
    except ValueError as error:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_REQUEST_INVALID") from error
    if request_digest != request_sha256:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_REQUEST_MISMATCH")
    if _v10_identity(payload.get("candidate"), "LOCAL_ACCEPTANCE_DECISION_V10_IDENTITY_INVALID") != normalized_request["candidate"] or _v10_identity(payload.get("projected_accepted"), "LOCAL_ACCEPTANCE_DECISION_V10_IDENTITY_INVALID") != normalized_request["projected_accepted"]:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_IDENTITY_MISMATCH")
    if _v10_verifiers(payload.get("verifier_artifacts"), "LOCAL_ACCEPTANCE_DECISION_V10_VERIFIERS_INVALID") != normalized_request["verifier_artifacts"]:
        raise SourceContractProposalError("LOCAL_ACCEPTANCE_DECISION_V10_VERIFIERS_MISMATCH")
    return dict(payload)


def _run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ("git", "-C", os.fspath(repository), *arguments), check=False, capture_output=True
        )
    except FileNotFoundError as error:
        raise GitProofError("GIT_CAPABILITY_UNAVAILABLE") from error
    except OSError as error:
        raise GitProofError("GIT_SUBPROCESS_FAILED") from error


def _git_stdout(repository: Path, *arguments: str) -> bytes:
    result = _run_git(repository, *arguments)
    if result.returncode != 0:
        raise SourceContractProposalError("PROPOSAL_GIT_OBJECT_UNAVAILABLE")
    return result.stdout


def verify_source_contract_proposal_git(proposal: object, repository: Path) -> None:
    """Prove every proposed pin, tree, reachability, and raw Git blob locally."""
    normalized = validate_source_contract_proposal(proposal)
    snapshots = normalized["snapshots"]
    assert isinstance(snapshots, dict)
    for snapshot in snapshots.values():
        assert isinstance(snapshot, dict)
        pull_request = snapshot["pull_request"]
        pinned = snapshot["pinned_commit_sha"]
        expected_head = snapshot["canonical_pr_head_sha"]
        expected_tree = snapshot["pinned_tree_sha"]
        assert isinstance(pull_request, int)
        assert isinstance(pinned, str)
        assert isinstance(expected_head, str)
        assert isinstance(expected_tree, str)
        head = _git_stdout(repository, "rev-parse", f"refs/specchoice/pr/{pull_request}").decode(
            "ascii", "strict"
        ).strip()
        if head != expected_head:
            raise SourceContractProposalError("PROPOSAL_CANONICAL_PR_HEAD_MISMATCH")
        _git_stdout(repository, "cat-file", "-e", f"{pinned}^{{commit}}")
        actual_tree = _git_stdout(repository, "rev-parse", f"{pinned}^{{tree}}").decode(
            "ascii", "strict"
        ).strip()
        if actual_tree != expected_tree:
            raise SourceContractProposalError("PROPOSAL_PINNED_TREE_MISMATCH")
        ancestry = _run_git(repository, "merge-base", "--is-ancestor", pinned, head)
        if ancestry.returncode == 1:
            raise SourceContractProposalError("PROPOSAL_PIN_NOT_REACHABLE")
        if ancestry.returncode != 0:
            raise SourceContractProposalError("PROPOSAL_GIT_ANCESTRY_FAILED")

    files = normalized["consumed_files"]
    assert isinstance(files, list)
    for file in files:
        assert isinstance(file, dict)
        snapshot = snapshots[file["snapshot_id"]]
        assert isinstance(snapshot, dict)
        pinned = snapshot["pinned_commit_sha"]
        assert isinstance(pinned, str)
        object_ref = f"{pinned}:{file['upstream_path']}"
        object_type = _git_stdout(repository, "cat-file", "-t", object_ref).decode("ascii", "strict").strip()
        if object_type != "blob":
            raise SourceContractProposalError("PROPOSAL_CONSUMED_PATH_NOT_REGULAR_FILE")
        raw = _git_stdout(repository, "show", object_ref)
        if len(raw) != file["raw_byte_length"]:
            raise SourceContractProposalError("PROPOSAL_RAW_BYTE_LENGTH_MISMATCH")
        if hashlib.sha256(raw).hexdigest() != file["raw_sha256"]:
            raise SourceContractProposalError("PROPOSAL_RAW_SHA256_MISMATCH")
