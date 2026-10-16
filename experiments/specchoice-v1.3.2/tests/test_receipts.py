# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import tempfile
import unittest
import json
import shutil
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from specchoice_evidence.baseline import BoundaryResult, CommittedPathChange
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.cli import (
    _committed_basis_material,
    _publication_authority,
    _require_current_boundary_clean,
    _require_post_review_delta_clean,
    _restart_lineage_for_local_mvp_receipt,
    _write_local_mvp_receipt,
    build_parser,
)
from specchoice_evidence.receipt import (
    ReceiptError,
    build_local_mvp_receipt,
    build_blocked_receipt,
    local_receipt_basis_sha256,
    render_markdown,
    validate_receipt,
    write_receipt_package,
)
from specchoice_evidence.source_contract import (
    SourceContractProposalError,
    validate_local_accepted_generation_decision,
)


class IntegrityReceiptTests(unittest.TestCase):
    @staticmethod
    def _identity() -> dict[str, object]:
        return {
            "candidate_relative_path": "bundles/candidates/fixture",
            "core_sha256": "c" * 64,
            "generation": "fixture",
            "root_sha256": "d" * 64,
            "snapshot_manifest_sha256": "e" * 64,
        }

    @staticmethod
    def _classifications() -> list[dict[str, object]]:
        return [{
            "path": ".DS_Store", "status": "preexisting_unrelated", "attributed_to_phase": False,
            "blocking": False, "diagnostic": "DS_STORE_IGNORED_OS_METADATA",
        }]

    @staticmethod
    def _restart_lineage(baseline_sha256: str) -> dict[str, object]:
        return {
            "allowlist": {"path": "config/allowlist.json", "sha256": "b" * 64},
            "baseline": {"path": "baselines/phase-start.json", "sha256": baseline_sha256},
            "incident_receipt": {"path": "receipts/restart.json", "sha256": "c" * 64},
            "previous_baseline": {"path": "baselines/phase-start-v1.json", "sha256": "d" * 64},
            "reason_code": "D15_RESTART_COMMITTED_HISTORY_BLIND_SPOT",
            "reviewed_revision": "a" * 40,
            "scope": "gap_closure_only",
        }

    def test_v5_integrity_receipt_binds_restart_and_preserves_accepted_bundle_identity(self) -> None:
        """The v5 receipt is local-only and derives its Markdown solely from canonical JSON."""
        root = Path(__file__).resolve().parents[1]
        receipt_path = root / "receipts/integrity-receipt-v5.json"
        receipt = validate_receipt(receipt_path)
        self.assertEqual(receipt["schema_version"], "3")
        self.assertEqual(receipt["source_identity"]["generation"], "source-contract-v2-pr2192-86a0021b-verifier-rooted-v1")
        self.assertEqual(receipt["source_identity"]["core_sha256"], "6ca1f176c84464d499d6c0e81d03ba3f23fdcdd1b5bd43bc28d9b2153a797495")
        self.assertEqual(receipt["source_identity"]["root_sha256"], "aacdda8218e3779747ae2dec45f9da81822f615ec4b257e55b0766baf8317d5a")
        self.assertEqual(receipt["source_identity"]["snapshot_manifest_sha256"], "1c81f84cf4894a7ecfde4b72e17d6e479a91cb0cfa408258611b00bdf5e2e397")
        self.assertFalse(receipt["source_identity"]["external_publication_authorized"])
        restart = receipt["restart_lineage"]
        self.assertEqual(restart["baseline"]["sha256"], "a0b9f9fdddb42f042bd6dfa8753b012c4514adbb4d8be4ea6faefdcafc402e40")
        self.assertEqual(restart["allowlist"]["sha256"], "8008c839c32f91b2f973f4799ebb27e58e010569057f3f7a4d96c9bcec6d9903")
        self.assertEqual(restart["incident_receipt"]["sha256"], "80b54ba1e45a00d391614cea7e2ffaf53b05ea966a52c1c26f8e0f8bb6ba42fd")
        self.assertEqual(render_markdown(receipt), (root / "receipts/integrity-receipt-v5.md").read_text(encoding="utf-8"))
        self.assertEqual(render_markdown(json.loads(receipt_path.read_text(encoding="utf-8"))), render_markdown(receipt))

    def test_rejected_source_receipt_is_canonical_and_markdown_is_json_only(self) -> None:
        receipt = build_blocked_receipt(
            baseline_sha256="a" * 64,
            environment_sha256="b" * 64,
            rejected_attempt_sha256="c" * 64,
            boundary_classifications=[
                {"path": ".DS_Store", "status": "preexisting_unrelated", "attributed_to_phase": False,
                 "blocking": False, "diagnostic": "DS_STORE_IGNORED_OS_METADATA"}
            ],
        )
        validated = validate_receipt(receipt)
        self.assertEqual(validated["outcome"], "fail")
        self.assertFalse(validated["reviewer_package_complete"])
        self.assertIn("SOURCE_GENERATION_NOT_ACCEPTED", validated["blocking_diagnostics"])
        markdown = render_markdown(validated)
        self.assertEqual(markdown, render_markdown(validated))
        self.assertIn(validated["receipt_sha256"], markdown)

    def test_receipt_hash_and_markdown_failure_do_not_invalidate_json_authority(self) -> None:
        receipt = build_blocked_receipt("a" * 64, "b" * 64, "c" * 64, [])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "integrity-receipt.json"
            markdown = Path(directory) / "missing" / "integrity-receipt.md"
            result = write_receipt_package(receipt, destination, markdown)
            self.assertEqual(result["receipt_sha256"], receipt["receipt_sha256"])
            self.assertFalse(result["reviewer_package_complete"])
            self.assertEqual(destination.read_bytes(), canonical_json_bytes(result))
            validate_receipt(destination)
        broken = dict(receipt)
        broken["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(ReceiptError, "RECEIPT_SELF_HASH_MISMATCH"):
            validate_receipt(broken)

    def test_local_mvp_receipt_is_pass_only_for_local_identity_with_external_publication_false(self) -> None:
        identity = self._identity()
        classifications = self._classifications()
        basis = local_receipt_basis_sha256("a" * 64, "b" * 64, identity, classifications)
        receipt = build_local_mvp_receipt(
            "a" * 64, "b" * 64, identity, classifications, "f" * 64, basis
        )
        self.assertEqual(receipt["outcome"], "pass")
        self.assertEqual(receipt["source_identity"]["kind"], "local_accepted_generation")
        self.assertFalse(receipt["source_identity"]["external_publication_authorized"])
        self.assertEqual(render_markdown(receipt), render_markdown(receipt))

    def test_revision_bound_receipt_and_decision_require_projection_binding(self) -> None:
        identity = self._identity()
        classifications = self._classifications()
        revision = "a" * 40
        projection = "b" * 64
        basis = local_receipt_basis_sha256(
            "a" * 64,
            "b" * 64,
            identity,
            classifications,
            reviewed_revision=revision,
            committed_boundary_projection_sha256=projection,
        )
        receipt = build_local_mvp_receipt(
            "a" * 64,
            "b" * 64,
            identity,
            classifications,
            "f" * 64,
            basis,
            restart_lineage=self._restart_lineage("a" * 64),
            reviewed_revision=revision,
            committed_boundary_projection_sha256=projection,
        )
        self.assertEqual(receipt["schema_version"], "4")
        self.assertEqual(receipt["reviewed_revision"], revision)
        self.assertEqual(receipt["committed_boundary_projection_sha256"], projection)
        decision = {
            "approval_scope": "local_accepted_generation_only",
            "approved_generation": identity,
            "authorization": {
                "external_publication_authorized": False,
                "local_accepted_generation_authorized": True,
            },
            "committed_boundary_projection_sha256": projection,
            "phase_start_baseline_sha256": "a" * 64,
            "reviewed_receipt_basis_sha256": basis,
            "reviewed_revision": revision,
            "reviewer": {"disposition": "approved_local_only"},
            "schema_version": "3",
            "state": "local_accepted_generation_authorized",
        }
        self.assertEqual(validate_local_accepted_generation_decision(decision)["schema_version"], "3")
        decision["reviewed_revision"] = "HEAD"
        with self.assertRaisesRegex(SourceContractProposalError, "LOCAL_ACCEPTANCE_REVIEWED_REVISION_INVALID"):
            validate_local_accepted_generation_decision(decision)

    def test_shared_issuance_and_finalization_gate_rejects_current_boundary_violation(self) -> None:
        result = BoundaryResult("a" * 64, [], 1)
        with patch("specchoice_evidence.cli.check_current_boundary", return_value=result):
            with self.assertRaisesRegex(ReceiptError, "LOCAL_MVP_CURRENT_BOUNDARY_BLOCKING"):
                _require_current_boundary_clean(Path("repository"), Path("baseline.json"))

    def test_compute_basis_cli_is_canonical_from_experiment_and_repository_cwds(self) -> None:
        experiment_root = Path(__file__).resolve().parents[1]
        repository_root = experiment_root.parents[1]
        revision = subprocess.run(
            ["git", "-C", os.fspath(repository_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        command = [
            sys.executable, "-m", "specchoice_evidence.cli", "compute-local-mvp-receipt-basis",
            "--environment-decision", os.fspath(experiment_root / "receipts/environment-decision.json"),
            "--accepted-directory", os.fspath(experiment_root / "bundles/accepted"),
            "--approved-generation", "source-contract-v2-pr2192-86a0021b-verifier-rooted-v1",
            "--candidate-relative-path", "bundles/candidates/source-contract-v2-pr2192-86a0021b-verifier-rooted-v1",
            "--reviewed-revision", revision,
        ]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": os.fspath(experiment_root / "src")}
        outputs = [
            subprocess.run(command, cwd=cwd, env=environment, check=True, capture_output=True).stdout
            for cwd in (experiment_root, repository_root)
        ]
        self.assertEqual(outputs[0], outputs[1])
        proposal = json.loads(outputs[0])
        self.assertTrue(proposal["proposal_only"])
        self.assertEqual(proposal["status"], "proposal_only")
        self.assertEqual(proposal["reviewed_revision"], revision)
        self.assertEqual(proposal["source_identity"]["candidate_relative_path"], "bundles/candidates/source-contract-v2-pr2192-86a0021b-verifier-rooted-v1")

    def test_publication_receipt_writer_and_finalizer_use_schema_five(self) -> None:
        experiment_root = Path(__file__).resolve().parents[1]
        repository = experiment_root.parents[1]
        baseline_sha256 = sha256_bytes(
            (experiment_root / "evidence/publication-manifest-v1.json").read_bytes()
        )
        reviewed_revision = subprocess.run(
            ["git", "-C", os.fspath(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        projection_sha256 = "1" * 64
        environment_sha256 = "2" * 64
        identity = self._identity()
        classifications = self._classifications()
        basis = local_receipt_basis_sha256(
            baseline_sha256,
            environment_sha256,
            identity,
            classifications,
            reviewed_revision=reviewed_revision,
            committed_boundary_projection_sha256=projection_sha256,
        )

        authority = _publication_authority(repository, reviewed_revision)
        material = {
            "committed_boundary_projection": {
                "boundary_classifications": classifications,
            },
            "committed_boundary_projection_sha256": projection_sha256,
            "environment_decision_sha256": environment_sha256,
            "phase_start_baseline_sha256": baseline_sha256,
            "receipt_basis_sha256": basis,
            "reviewed_revision": reviewed_revision,
        }
        template = json.loads(
            (experiment_root / "receipts/reviewer-boundary-decision-v6.json").read_text(
                encoding="utf-8"
            )
        )
        decision = dict(template)
        decision.update(
            {
                "approved_generation": identity,
                "committed_boundary_projection_sha256": projection_sha256,
                "phase_start_baseline_sha256": baseline_sha256,
                "reviewed_receipt_basis_sha256": basis,
                "reviewed_revision": reviewed_revision,
            }
        )
        decision_raw = canonical_json_bytes(decision)
        with tempfile.TemporaryDirectory(dir=experiment_root / "receipts") as directory:
            output_root = Path(directory)
            decision_path = output_root / "reviewer-decision.json"
            receipt_path = output_root / "integrity-receipt.json"
            markdown_path = output_root / "integrity-receipt.md"
            decision_path.write_bytes(decision_raw)
            write_args = build_parser().parse_args(
                [
                    "write-local-mvp-receipt",
                    "--decision", str(decision_path),
                    "--receipt", str(receipt_path),
                    "--markdown", str(markdown_path),
                ]
            )
            written = _write_local_mvp_receipt(
                write_args,
                decision,
                decision_raw,
                identity,
                self._restart_lineage("a" * 64),
                material,
            )

            self.assertEqual(written["schema_version"], "5")
            self.assertNotIn("restart_lineage", written)
            self.assertEqual(written["publication_authority"], authority)
            self.assertEqual(
                written["publication_authority"]["reviewed_revision"],
                written["reviewed_revision"],
            )

            finalize_args = build_parser().parse_args(
                [
                    "finalize-review",
                    "--decision", str(decision_path),
                    "--receipt", str(receipt_path),
                    "--markdown", str(markdown_path),
                ]
            )
            with patch("specchoice_evidence.cli._require_post_review_delta_clean"), patch(
                "specchoice_evidence.cli._require_current_boundary_clean"
            ), patch(
                "specchoice_evidence.cli._committed_basis_material",
                return_value=material,
            ):
                self.assertEqual(finalize_args.handler(finalize_args), 0)

    def test_schema_five_rejects_a_mismatched_generator_version(self) -> None:
        reviewed_revision = "f" * 40
        projection_sha256 = "1" * 64
        environment_sha256 = "2" * 64
        identity = self._identity()
        classifications = self._classifications()
        baseline_sha256 = "a" * 64
        basis = local_receipt_basis_sha256(
            baseline_sha256,
            environment_sha256,
            identity,
            classifications,
            reviewed_revision=reviewed_revision,
            committed_boundary_projection_sha256=projection_sha256,
        )
        receipt = build_local_mvp_receipt(
            baseline_sha256,
            environment_sha256,
            identity,
            classifications,
            "3" * 64,
            basis,
            reviewed_revision=reviewed_revision,
            committed_boundary_projection_sha256=projection_sha256,
            publication_authority={
                "manifest_path": "evidence/publication-manifest-v1.json",
                "manifest_sha256": baseline_sha256,
                "reviewed_revision": reviewed_revision,
                "upstream_base_commit": "e" * 40,
            },
        )
        receipt["generator_version"] = "4"
        projection = dict(receipt)
        projection.pop("receipt_sha256")
        receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(projection))

        with self.assertRaisesRegex(ReceiptError, "RECEIPT_GENERATOR_INVALID"):
            validate_receipt(receipt)

    def test_local_receipt_basis_mismatch_rejects_schema_two_and_three_construction(self) -> None:
        identity = self._identity()
        classifications = self._classifications()
        for restart_lineage in (None, self._restart_lineage("a" * 64)):
            with self.subTest(schema="3" if restart_lineage else "2"):
                with self.assertRaisesRegex(ReceiptError, "LOCAL_RECEIPT_BASIS_MISMATCH"):
                    build_local_mvp_receipt(
                        "a" * 64,
                        "b" * 64,
                        identity,
                        classifications,
                        "f" * 64,
                        "0" * 64,
                        restart_lineage=restart_lineage,
                    )

    def test_schema_three_lineage_baseline_mismatch_rejects_validation_and_finalization(self) -> None:
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / "receipts/integrity-receipt-v5.json").read_text(encoding="utf-8"))
        receipt["phase_start_baseline_sha256"] = "0" * 64
        projected = dict(receipt)
        projected.pop("receipt_sha256")
        receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(projected))
        with self.assertRaisesRegex(ReceiptError, "RESTART_LINEAGE_BASELINE_MISMATCH"):
            validate_receipt(receipt)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "integrity-receipt.json"
            markdown_path = Path(directory) / "integrity-receipt.md"
            receipt_path.write_bytes(canonical_json_bytes(receipt))
            markdown_path.write_text("not reached\n", encoding="utf-8")
            arguments = build_parser().parse_args(
                [
                    "finalize-review",
                    "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                    "--receipt", str(receipt_path),
                    "--markdown", str(markdown_path),
                ]
            )
            with self.assertRaisesRegex(ReceiptError, "RESTART_LINEAGE_BASELINE_MISMATCH"):
                arguments.handler(arguments)

    def test_finalization_requires_the_exact_restart_projection(self) -> None:
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / "receipts/integrity-receipt-v5.json").read_text(encoding="utf-8"))
        receipt["restart_lineage"]["reviewed_revision"] = "0" * 40
        projected = dict(receipt)
        projected.pop("receipt_sha256")
        receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(projected))
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory)
            for relative_path in (
                "baselines/phase-start-v5-gap-closure.json",
                "baselines/phase-start-v2.json",
                "config/boundary_allowlist-v5-gap-closure.json",
                "receipts/boundary-restart-v5.json",
            ):
                destination = fixture_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative_path, destination)
            receipt_path = fixture_root / "receipts/integrity-receipt.json"
            markdown_path = fixture_root / "receipts/integrity-receipt.md"
            receipt_path.write_bytes(canonical_json_bytes(receipt))
            markdown_path.write_text("not reached\n", encoding="utf-8")
            arguments = build_parser().parse_args(
                [
                    "finalize-review",
                    "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                    "--receipt", str(receipt_path),
                    "--markdown", str(markdown_path),
                ]
            )
            with self.assertRaisesRegex(ReceiptError, "HISTORICAL_RECEIPT_NOT_FINALIZABLE"):
                arguments.handler(arguments)

    def test_active_defaults_are_v7_from_experiment_and_repository_roots(self) -> None:
        experiment_root = Path(__file__).resolve().parents[1]
        repository_root = experiment_root.parents[1]
        expected_baseline = experiment_root / "baselines/phase-start-v7-fixture-closure.json"
        expected_restart = experiment_root / "receipts/boundary-restart-v7-fixture-closure.json"
        original_cwd = Path.cwd()
        try:
            for cwd in (experiment_root, repository_root):
                os.chdir(cwd)
                parser = build_parser()
                boundary = parser.parse_args(["check-boundary"])
                receipt = parser.parse_args(["write-local-mvp-receipt", "--decision", "decision.json"])
                self.assertEqual(boundary.baseline, expected_baseline)
                self.assertEqual(receipt.baseline, expected_baseline)
                self.assertEqual(receipt.restart_receipt, expected_restart)
                self.assertEqual(boundary.handler(boundary), 0)
        finally:
            os.chdir(original_cwd)

    def test_v8_receipt_is_bound_to_the_v7_baseline(self) -> None:
        root = Path(__file__).resolve().parents[1]
        receipt = validate_receipt(root / "receipts/integrity-receipt-v8.json")
        self.assertEqual(receipt["phase_start_baseline_sha256"], "b338372c74c605aa8b294ee30bcc39410422a6a5673e15061f86f28188debecb")
        self.assertFalse(receipt["source_identity"]["external_publication_authorized"])

    def test_restart_lineage_uses_canonical_paths_for_default_absolute_and_relative_inputs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected_paths = {
            "allowlist": "config/boundary_allowlist-v7-fixture-closure.json",
            "baseline": "baselines/phase-start-v7-fixture-closure.json",
            "incident_receipt": "receipts/boundary-restart-v7-fixture-closure.json",
            "previous_baseline": "baselines/phase-start-v6-fixture-closure.json",
        }
        command_prefix = [
            "write-local-mvp-receipt",
            "--decision", str(root / "receipts/reviewer-boundary-decision-v6.json"),
        ]
        invocations = [
            command_prefix,
            command_prefix + [
                "--baseline", str(root / "baselines/phase-start-v7-fixture-closure.json"),
                "--restart-receipt", str(root / "receipts/boundary-restart-v7-fixture-closure.json"),
            ],
            command_prefix + [
                "--baseline", "baselines/phase-start-v7-fixture-closure.json",
                "--restart-receipt", "receipts/boundary-restart-v7-fixture-closure.json",
            ],
        ]
        original_cwd = Path.cwd()
        try:
            os.chdir(root)
            for invocation in invocations:
                with self.subTest(invocation=invocation):
                    args = build_parser().parse_args(invocation)
                    lineage = _restart_lineage_for_local_mvp_receipt(args)
                    assert lineage is not None
                    self.assertEqual(
                        {name: lineage[name]["path"] for name in expected_paths}, expected_paths
                    )
        finally:
            os.chdir(original_cwd)

    def test_v6_decision_cannot_rebuild_a_receipt_after_post_review_code_changes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        decision_path = root / "receipts/reviewer-boundary-decision-v6.json"
        v6_receipt_path = root / "receipts/integrity-receipt-v6.json"
        original_decision, original_receipt = decision_path.read_bytes(), v6_receipt_path.read_bytes()
        with tempfile.TemporaryDirectory(dir=root / "receipts") as directory:
            output_root = Path(directory)
            arguments = build_parser().parse_args(
                [
                    "write-local-mvp-receipt",
                    "--decision", str(decision_path),
                    "--accepted-directory", str(root / "bundles/accepted"),
                    "--receipt", str(output_root / "replacement.json"),
                    "--markdown", str(output_root / "replacement.md"),
                ]
            )
            with patch("specchoice_evidence.cli.capture_live_state", return_value={}):
                with self.assertRaisesRegex((ReceiptError, Exception), "(?:LOCAL_RECEIPT_POST_REVIEW_DELTA_BLOCKING|BOUNDARY_HISTORY_NOT_DESCENDANT)"):
                    arguments.handler(arguments)
        self.assertEqual(decision_path.read_bytes(), original_decision)
        self.assertEqual(v6_receipt_path.read_bytes(), original_receipt)

    def test_post_review_gate_allows_exact_artifacts_and_future_controls_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        repository = root.parents[1]
        arguments = build_parser().parse_args(
            [
                "finalize-review",
                "--decision", str(root / "receipts/reviewer-boundary-decision-v6.json"),
                "--receipt", str(root / "receipts/integrity-receipt-v6.json"),
                "--markdown", str(root / "receipts/integrity-receipt-v6.md"),
            ]
        )
        decision = {"reviewed_revision": "a" * 40}
        allowed_live = {
            "experiments/specchoice-v1.3.2/receipts/reviewer-boundary-decision-v6.json": [{"source": "untracked"}],
            "experiments/specchoice-v1.3.2/receipts/integrity-receipt-v6.json": [{"source": "untracked"}],
            "experiments/specchoice-v1.3.2/receipts/integrity-receipt-v6.md": [{"source": "untracked"}],
            ".planning/STATE.md": [{"source": "worktree"}],
            ".DS_Store": [{"source": "untracked"}],
        }
        with patch("specchoice_evidence.cli.capture_committed_history", return_value=[]), patch(
            "specchoice_evidence.cli.capture_live_state", return_value=allowed_live
        ):
            _require_post_review_delta_clean(arguments, decision, repository)

    def test_post_review_gate_blocks_clean_final_tree_code_history(self) -> None:
        root = Path(__file__).resolve().parents[1]
        repository = root.parents[1]
        arguments = build_parser().parse_args(
            [
                "finalize-review",
                "--decision", str(root / "receipts/reviewer-boundary-decision-v6.json"),
                "--receipt", str(root / "receipts/integrity-receipt-v6.json"),
                "--markdown", str(root / "receipts/integrity-receipt-v6.md"),
            ]
        )
        transient_path = "experiments/specchoice-v1.3.2/src/specchoice_evidence/transient.py"
        history = [
            CommittedPathChange(transient_path, "added", "000000", "100644", "0" * 8, "1" * 8, "a" * 40),
            CommittedPathChange(transient_path, "deleted", "100644", "000000", "1" * 8, "0" * 8, "b" * 40),
        ]
        with patch("specchoice_evidence.cli.capture_committed_history", return_value=history), patch(
            "specchoice_evidence.cli.capture_live_state", return_value={}
        ):
            with self.assertRaisesRegex(ReceiptError, "LOCAL_RECEIPT_POST_REVIEW_DELTA_BLOCKING"):
                _require_post_review_delta_clean(arguments, {"reviewed_revision": "a" * 40}, repository)

    def test_post_review_gate_blocks_staged_worktree_and_untracked_code(self) -> None:
        root = Path(__file__).resolve().parents[1]
        repository = root.parents[1]
        arguments = build_parser().parse_args(
            [
                "finalize-review",
                "--decision", str(root / "receipts/reviewer-boundary-decision-v6.json"),
                "--receipt", str(root / "receipts/integrity-receipt-v6.json"),
                "--markdown", str(root / "receipts/integrity-receipt-v6.md"),
            ]
        )
        code_path = "experiments/specchoice-v1.3.2/src/specchoice_evidence/changed.py"
        for source in ("staged", "worktree", "untracked"):
            with self.subTest(source=source), patch(
                "specchoice_evidence.cli.capture_committed_history", return_value=[]
            ), patch("specchoice_evidence.cli.capture_live_state", return_value={code_path: [{"source": source}]}):
                with self.assertRaisesRegex(ReceiptError, "LOCAL_RECEIPT_POST_REVIEW_DELTA_BLOCKING"):
                    _require_post_review_delta_clean(arguments, {"reviewed_revision": "a" * 40}, repository)

    def test_historical_v5_decision_cannot_issue_under_the_current_v7_lineage(self) -> None:
        root = Path(__file__).resolve().parents[1]
        repository = root.parents[1]
        template = json.loads((root / "receipts/reviewer-boundary-decision-v6.json").read_text(encoding="utf-8"))
        revision = subprocess.run(
            ["git", "-C", os.fspath(repository), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        approved_generation = template["approved_generation"]
        assert isinstance(approved_generation, dict)
        material = _committed_basis_material(
            root=repository,
            baseline=root / "baselines/phase-start-v5-gap-closure.json",
            environment=root / "receipts/environment-decision.json",
            approved_generation=approved_generation,
            reviewed_revision=revision,
        )
        decision = dict(template)
        decision.update(
            {
                "committed_boundary_projection_sha256": material["committed_boundary_projection_sha256"],
                "phase_start_baseline_sha256": material["phase_start_baseline_sha256"],
                "reviewed_receipt_basis_sha256": material["receipt_basis_sha256"],
                "reviewed_revision": material["reviewed_revision"],
            }
        )
        with tempfile.TemporaryDirectory(dir=root / "receipts") as directory:
            output_root = Path(directory)
            decision_path = output_root / "reviewer-decision.json"
            receipt_path = output_root / "integrity-receipt.json"
            markdown_path = output_root / "integrity-receipt.md"
            decision_path.write_bytes(canonical_json_bytes(decision))
            write_args = build_parser().parse_args(
                [
                    "write-local-mvp-receipt",
                    "--decision", str(decision_path),
                    "--accepted-directory", str(root / "bundles/accepted"),
                    "--baseline", str(root / "baselines/phase-start-v5-gap-closure.json"),
                    "--restart-receipt", str(root / "receipts/boundary-restart-v5.json"),
                    "--receipt", str(receipt_path),
                    "--markdown", str(markdown_path),
                ]
            )
            with patch("specchoice_evidence.cli.capture_live_state", return_value={}), patch(
                "specchoice_evidence.cli._require_current_boundary_clean"
            ), self.assertRaisesRegex(ReceiptError, "LOCAL_MVP_BOUNDARY_BLOCKING"):
                write_args.handler(write_args)

    def test_v5_write_without_restart_fails_closed_before_receipt_issuance(self) -> None:
        root = Path(__file__).resolve().parents[1]
        arguments = build_parser().parse_args(
            [
                "write-local-mvp-receipt",
                "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                "--baseline", str(root / "baselines/phase-start-v5-gap-closure.json"),
            ]
        )
        arguments.restart_receipt = None
        with self.assertRaisesRegex(ReceiptError, "LOCAL_RECEIPT_BASIS_MISMATCH"):
            arguments.handler(arguments)

    def test_explicit_historical_baseline_uses_schema_two_compatibility_without_restart(self) -> None:
        root = Path(__file__).resolve().parents[1]
        arguments = build_parser().parse_args(
            [
                "write-local-mvp-receipt",
                "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                "--baseline", str(root / "baselines/phase-start-v2.json"),
            ]
        )
        self.assertIsNone(_restart_lineage_for_local_mvp_receipt(arguments))

    def test_write_command_rejects_recomputed_basis_that_differs_from_decision(self) -> None:
        root = Path(__file__).resolve().parents[1]
        arguments = build_parser().parse_args(
            [
                "write-local-mvp-receipt",
                "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                "--accepted-directory", str(root / "bundles/accepted"),
                "--baseline", str(root / "baselines/phase-start-v5-gap-closure.json"),
                "--environment-decision", str(root / "receipts/environment-decision.json"),
                "--receipt", str(root / "receipts/should-not-write.json"),
                "--markdown", str(root / "receipts/should-not-write.md"),
                "--restart-receipt", str(root / "receipts/boundary-restart-v5.json"),
            ]
        )
        with self.assertRaisesRegex(ReceiptError, "LOCAL_RECEIPT_BASIS_MISMATCH"):
            arguments.handler(arguments)

    def test_historical_schema_three_receipt_cannot_finalize(self) -> None:
        root = Path(__file__).resolve().parents[1]
        arguments = build_parser().parse_args(
            [
                "finalize-review",
                "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                "--receipt", str(root / "receipts/integrity-receipt-v5.json"),
                "--markdown", str(root / "receipts/integrity-receipt-v5.md"),
            ]
        )
        with self.assertRaisesRegex(ReceiptError, "HISTORICAL_RECEIPT_NOT_FINALIZABLE"):
            arguments.handler(arguments)

    def test_historical_schema_two_receipt_cannot_finalize(self) -> None:
        root = Path(__file__).resolve().parents[1]
        arguments = build_parser().parse_args(
            [
                "finalize-review",
                "--decision", str(root / "receipts/reviewer-boundary-decision.json"),
                "--receipt", str(root / "receipts/integrity-receipt.json"),
                "--markdown", str(root / "receipts/integrity-receipt.md"),
            ]
        )
        with self.assertRaisesRegex(ReceiptError, "HISTORICAL_RECEIPT_NOT_FINALIZABLE"):
            arguments.handler(arguments)


if __name__ == "__main__":
    unittest.main()
