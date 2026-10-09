# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Fail-closed validation tests for pending source-contract corrections."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from specchoice_evidence.source_contract import (
    SourceContractProposalError,
    render_v4_non_executable_supersession,
    validate_v4_non_executable_supersession,
    require_accepted_publication_authorization,
    require_candidate_construction_authorization,
    require_fixture_construction_authorization,
    require_source_extraction_authorization,
    validate_fixture_construction_decision,
    validate_fixture_construction_proposal,
    validate_source_contract_proposal,
    validate_source_publication_decision,
    verify_source_contract_proposal_git,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes


def git(*arguments: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def proposal_for(raw: bytes, commit: str, tree: str) -> dict[str, object]:
    return {
        "schema_version": "1",
        "status": "pending_reviewer_approval",
        "proposed_contract_version": "2",
        "requested_generation_label": "candidate-v2",
        "base_frozen_contract": {"path": "config/source_snapshots.json", "sha256": "a" * 64},
        "historical_rejected_receipt": {"path": "bundles/rejected/receipt.json", "sha256": "b" * 64},
        "snapshots": [
            {
                "snapshot_id": "fixture",
                "repository": "example/repository",
                "pull_request": 7,
                "pinned_commit_sha": commit,
                "pinned_tree_sha": tree,
                "canonical_pr_head_sha": commit,
                "reachability": "equal_head",
                "change_control": "versioned_correction",
            }
        ],
        "consumed_files": [
            {
                "snapshot_id": "fixture",
                "upstream_path": "fixture.txt",
                "local_bundle_path": "raw/fixture.txt",
                "experimental_role": "test fixture",
                "why_consumed": "Proves exact byte custody.",
                "raw_authoritative": True,
                "raw_byte_length": len(raw),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "declared_transforms": [],
            }
        ],
    }


def proposal_only_decision_for(proposal: dict[str, object]) -> dict[str, object]:
    approved_contract = {
        "base_frozen_contract": proposal["base_frozen_contract"],
        "consumed_files": proposal["consumed_files"],
        "historical_rejected_receipt": proposal["historical_rejected_receipt"],
        "proposed_contract_version": proposal["proposed_contract_version"],
        "requested_generation_label": proposal["requested_generation_label"],
        "snapshots": proposal["snapshots"],
    }
    return {
        "approval_scope": "proposal_only",
        "approved_contract": approved_contract,
        "authorization": {
            "accepted_publication_authorized": False,
            "candidate_construction_authorized": False,
            "source_extraction_authorized": False,
        },
        "proposal": {
            "path": "receipts/source-contract-correction-proposal-v2.json",
            "sha256": sha256_bytes(canonical_json_bytes(proposal)),
        },
        "reviewer": {"approval_token": "approve-proposal-only"},
        "schema_version": "1",
        "state": "contract_approved",
    }


class SourceContractProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.audit = self.root / "audit.git"
        git("init", "-q", self.source.as_posix())
        git("config", "user.email", "test@example.invalid", cwd=self.source)
        git("config", "user.name", "SpecChoice test", cwd=self.source)
        self.raw = b"fixture\r\n"
        (self.source / "fixture.txt").write_bytes(self.raw)
        git("add", "fixture.txt", cwd=self.source)
        git("commit", "-qm", "fixture", cwd=self.source)
        self.commit = git("rev-parse", "HEAD", cwd=self.source)
        self.tree = git("rev-parse", "HEAD^{tree}", cwd=self.source)
        git("clone", "--bare", "-q", self.source.as_posix(), self.audit.as_posix())
        git("--git-dir", self.audit.as_posix(), "update-ref", "refs/specchoice/pr/7", self.commit)
        self.proposal = proposal_for(self.raw, self.commit, self.tree)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_pending_proposal_has_local_git_proof(self) -> None:
        validate_source_contract_proposal(self.proposal)
        verify_source_contract_proposal_git(self.proposal, self.audit)

    def test_missing_required_file_fields_fail_closed(self) -> None:
        for field in (
            "upstream_path",
            "local_bundle_path",
            "experimental_role",
            "raw_sha256",
            "raw_byte_length",
            "declared_transforms",
        ):
            invalid = copy.deepcopy(self.proposal)
            del invalid["consumed_files"][0][field]
            with self.subTest(field=field), self.assertRaises(SourceContractProposalError):
                validate_source_contract_proposal(invalid)

    def test_missing_role_or_transform_details_fail_closed(self) -> None:
        invalid = copy.deepcopy(self.proposal)
        invalid["consumed_files"][0]["declared_transforms"] = [{"name": "normalize"}]
        with self.assertRaisesRegex(SourceContractProposalError, "TRANSFORM_PARAMETERS_MISSING"):
            validate_source_contract_proposal(invalid)

    def test_git_proof_rejects_tampered_raw_hash_or_non_blob_path(self) -> None:
        tampered_hash = copy.deepcopy(self.proposal)
        tampered_hash["consumed_files"][0]["raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(SourceContractProposalError, "RAW_SHA256_MISMATCH"):
            verify_source_contract_proposal_git(tampered_hash, self.audit)

        directory_path = copy.deepcopy(self.proposal)
        directory_path["consumed_files"][0]["upstream_path"] = "."
        with self.assertRaises(SourceContractProposalError):
            verify_source_contract_proposal_git(directory_path, self.audit)

    def test_proposal_only_decision_cannot_authorize_extraction_or_publication(self) -> None:
        decision = proposal_only_decision_for(self.proposal)
        validated = validate_source_publication_decision(
            decision,
            self.proposal,
            proposal_path="receipts/source-contract-correction-proposal-v2.json",
            proposal_sha256=sha256_bytes(canonical_json_bytes(self.proposal)),
        )

        with self.assertRaisesRegex(SourceContractProposalError, "SOURCE_EXTRACTION_NOT_AUTHORIZED"):
            require_source_extraction_authorization(validated)
        with self.assertRaisesRegex(
            SourceContractProposalError, "CANDIDATE_CONSTRUCTION_NOT_AUTHORIZED"
        ):
            require_candidate_construction_authorization(validated)
        with self.assertRaisesRegex(SourceContractProposalError, "ACCEPTED_PUBLICATION_NOT_AUTHORIZED"):
            require_accepted_publication_authorization(validated)

    def test_proposal_only_decision_rejects_scope_escalation_and_contract_drift(self) -> None:
        decision = proposal_only_decision_for(self.proposal)
        decision["authorization"]["source_extraction_authorized"] = True
        with self.assertRaisesRegex(SourceContractProposalError, "AUTHORIZATION_INVALID"):
            validate_source_publication_decision(
                decision,
                self.proposal,
                proposal_path="receipts/source-contract-correction-proposal-v2.json",
                proposal_sha256=sha256_bytes(canonical_json_bytes(self.proposal)),
            )

        decision = proposal_only_decision_for(self.proposal)
        decision["approved_contract"]["snapshots"] = []
        with self.assertRaisesRegex(SourceContractProposalError, "CONTRACT_MISMATCH"):
            validate_source_publication_decision(
                decision,
                self.proposal,
                proposal_path="receipts/source-contract-correction-proposal-v2.json",
                proposal_sha256=sha256_bytes(canonical_json_bytes(self.proposal)),
            )

    def test_v3_fixture_construction_decision_binds_exact_proposal_and_source(self) -> None:
        experiment_root = Path(__file__).parents[1]
        proposal_path = (
            experiment_root
            / "receipts/source-contract-proposal-v3-pr2164-fixture-closure-verifier-rooted-v3.json"
        )
        proposal_raw = proposal_path.read_bytes()
        proposal = json.loads(proposal_raw.decode("utf-8"))
        fixed_source = proposal["fixed_source"]
        self.assertIsInstance(fixed_source, dict)
        decision = {
            "decision": "authorize",
            "decision_timestamp": "2026-08-02T12:00:00Z",
            "fixed_source_commit": fixed_source["commit"],
            "proposal": {
                "generation": proposal["generation"],
                "path": proposal_path.relative_to(experiment_root).as_posix(),
                "sha256": sha256_bytes(proposal_raw),
            },
            "rationale": "The exact immutable candidate construction proposal was reviewed.",
            "reviewer_identity": "human-riscv-reviewer",
            "schema_version": "1",
        }

        validate_fixture_construction_proposal(proposal)
        validated = validate_fixture_construction_decision(
            decision,
            proposal,
            proposal_path=proposal_path.relative_to(experiment_root).as_posix(),
            proposal_sha256=sha256_bytes(proposal_raw),
        )

        self.assertEqual(validated["decision"], "authorize")
        self.assertEqual(validated["fixed_source_commit"], fixed_source["commit"])
        self.assertEqual(validated["proposal"]["generation"], proposal["generation"])
        require_fixture_construction_authorization(validated)

        rejected = {**decision, "decision": "reject"}
        validated_rejection = validate_fixture_construction_decision(
            rejected,
            proposal,
            proposal_path=proposal_path.relative_to(experiment_root).as_posix(),
            proposal_sha256=sha256_bytes(proposal_raw),
        )
        with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_NOT_AUTHORIZED"):
            require_fixture_construction_authorization(validated_rejection)

        wrong_source = {**decision, "fixed_source_commit": "0" * 40}
        with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_SOURCE_MISMATCH"):
            validate_fixture_construction_decision(
                wrong_source,
                proposal,
                proposal_path=proposal_path.relative_to(experiment_root).as_posix(),
                proposal_sha256=sha256_bytes(proposal_raw),
            )


class SourceContractTests(unittest.TestCase):
    def test_v4_authorization_is_append_only_classified_non_executable(self) -> None:
        experiment_root = Path(__file__).parents[1]
        paths = {
            "proposal": experiment_root / "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
            "supersession": experiment_root / "receipts/source-contract-construction-proposal-v4-supersession-v3.json",
            "decision": experiment_root / "receipts/source-contract-construction-decision-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
            "ontology": experiment_root / "reviews/h1-source-gold-ontology-decision-v1.json",
        }
        original = {name: path.read_bytes() for name, path in paths.items()}

        rendered = render_v4_non_executable_supersession(
            proposal_raw=original["proposal"],
            supersession_raw=original["supersession"],
            decision_raw=original["decision"],
            ontology_raw=original["ontology"],
        )

        self.assertEqual(rendered["status"], "authorized_but_non_executable")
        self.assertFalse(rendered["construction_authorized"])
        self.assertEqual(rendered["missing_entrypoints"], [
            "build-fixture-construction-candidate-v5",
            "validate-fixture-candidate-v5",
        ])
        validate_v4_non_executable_supersession(
            rendered,
            proposal_raw=original["proposal"],
            supersession_raw=original["supersession"],
            decision_raw=original["decision"],
            ontology_raw=original["ontology"],
        )
        self.assertEqual({name: path.read_bytes() for name, path in paths.items()}, original)


if __name__ == "__main__":
    unittest.main()
