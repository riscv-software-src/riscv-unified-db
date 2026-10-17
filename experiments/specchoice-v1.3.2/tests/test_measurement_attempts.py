# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Immutable, role-separated custody contracts for Phase 2 attempts."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from specchoice_evidence import filesystem
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError
from specchoice_measurement.adapter import (
    AdapterError,
    build_pr2164_adapter_batch,
    write_pr2164_accepted_v6_adapter_batch_v4,
)
from specchoice_measurement.attempts import (
    AttemptError,
    _apply_successor_mutations,
    _canonical_file,
    _evaluate_successor_payload,
    run_measurement_attempt,
    validate_measurement_attempt,
    validate_required_diagnostics_v4,
    validate_fresh_v4_target,
    run_fresh_adversarial_suite_v7,
    run_fresh_formal_measurement_v6,
    validate_fresh_adversarial_result_v7,
    validate_fresh_formal_measurement_v6,
)
from specchoice_measurement.cli import (
    command_validate_attempt,
    command_run_adversarial_oracles,
    command_run_formal_measurement,
    validate_adversarial_report,
)
from specchoice_measurement.preflight import preflight_prediction_batch
from specchoice_measurement.scoring import score_prediction_batch


class MeasurementAttemptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiment_root = Path(__file__).parents[1]
        self.bundle = self.experiment_root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        self.pending_bundle = self.experiment_root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        self._legacy_root = tempfile.TemporaryDirectory()
        self.addCleanup(self._legacy_root.cleanup)
        source_root = Path(self._legacy_root.name)
        (source_root / "phase2").mkdir()
        (source_root / "receipts/pending").mkdir(parents=True)
        shutil.copy2(self.experiment_root / "phase2/source-authority-v9-historical.json", source_root / "phase2/source-authority.json")
        shutil.copy2(self.experiment_root / "phase2/source-authority-v10-pending.json", source_root / "phase2/source-authority-v10-pending.json")
        shutil.copy2(self.experiment_root / "receipts/pending/fixture-closure-transition-v2-to-v3.json", source_root / "receipts/pending/fixture-closure-transition-v2-to-v3.json")
        shutil.copy2(self.experiment_root / "receipts/fixture-closure-acceptance-audit-v3.json", source_root / "receipts/fixture-closure-acceptance-audit-v3.json")
        self.authority = source_root / "phase2/source-authority.json"
        self.active_authority = self.experiment_root / "phase2/source-authority-v13-historical.json"
        self.revocation = self.experiment_root / "receipts/fixture-closure-revocation-v2.json"
        self.pending_authority = source_root / "phase2/source-authority-v10-pending.json"
        self.transition = source_root / "receipts/pending/fixture-closure-transition-v2-to-v3.json"
        self.batch = build_pr2164_adapter_batch(
            authority_path=self.authority,
            bundle_root=self.bundle,
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
        )
        self.raw = (self.experiment_root / "fixtures/measurement/golden-predictions-v1.json").read_bytes()
        self.active_v3_predictions = self.experiment_root / "fixtures/measurement/golden-predictions-v2.json"
        self.active_v3_oracle = self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v2.json"

    def _pending_formal_args(self, root: Path) -> SimpleNamespace:
        root.parent.mkdir(parents=True, exist_ok=True)
        batch = build_pr2164_adapter_batch(
            authority_path=self.authority,
            bundle_root=self.pending_bundle,
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            pending_authority_path=self.pending_authority,
            transition_path=self.transition,
        )
        self.assertTrue(batch.valid)
        payload = json.loads(self.raw.decode("utf-8"))
        payload["adapter_batch_sha256"] = batch.adapter_batch_sha256
        predictions = root.parent / "pending-v3-golden-predictions.json"
        predictions.write_bytes(canonical_json_bytes(payload))
        oracle_payload = json.loads((self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v1.json").read_text(encoding="utf-8"))
        for entry in oracle_payload["oracles"]:
            entry["raw_input_identity"]["base_fixture"] = predictions.name
            entry["raw_input_identity"]["base_sha256"] = sha256_bytes(predictions.read_bytes())
        oracle = root.parent / "pending-v3-required-diagnostics.json"
        oracle.write_bytes(canonical_json_bytes(oracle_payload))
        return SimpleNamespace(
            authority=self.authority,
            bundle=self.pending_bundle,
            rules=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            schema=self.experiment_root / "config/measurement/canonical-adjudication-schema-v1.json",
            predictions=predictions,
            pending_authority=self.pending_authority,
            transition=self.transition,
            attempt_root=root,
            attempt_id="formal-golden",
            adapter_batch=batch,
            oracle=oracle,
        )

    def _copy_fresh_repository(self, repository: Path) -> tuple[Path, dict[str, object]]:
        experiment = repository / "experiments/specchoice-v1.3.2"
        for relative in (
            "phase2/source-authority.json",
            "config/fixture-registry-pr2164-v6.json",
            "config/measurement/pr2164-semantic-gold-contract-v2.json",
            "config/measurement/pr2164-adapter-rules-v3.json",
            "config/measurement/pr2164-adapter-rules-v4.json",
            "config/measurement/canonical-adjudication-schema-v3.json",
            "fixtures/measurement/golden-predictions-v4.json",
            "fixtures/measurement/adversarial/required-diagnostics-v4.json",
        ):
            target = experiment / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.experiment_root / relative, target)
        shutil.copytree(
            self.experiment_root / (
                "bundles/accepted/"
                "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
            ),
            experiment / (
                "bundles/accepted/"
                "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
            ),
        )
        (experiment / "reports/h1").mkdir(parents=True)
        (experiment / "runs/measurement-attempts").mkdir(parents=True)
        closure: dict[str, object] = {
            "freeze_commit": "f" * 40,
            "future_targets": [{
                "kind": "file",
                "path": "experiments/specchoice-v1.3.2/reports/h1/adapter-batch-pr2164-v6.json",
            }],
            "schema_version": "runtime-executable-closure-v4",
        }
        receipt = experiment / "receipts/runtime-executable-closure-v4.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_bytes(canonical_json_bytes(closure))
        return experiment, closure

    def _active_formal_args(self, root: Path) -> SimpleNamespace:
        root.parent.mkdir(parents=True, exist_ok=True)
        batch = build_pr2164_adapter_batch(
            authority_path=self.active_authority,
            bundle_root=self.pending_bundle,
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            revocation_path=self.revocation,
        )
        self.assertTrue(batch.valid)
        return SimpleNamespace(
            authority=self.active_authority,
            bundle=self.pending_bundle,
            rules=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            schema=self.experiment_root / "config/measurement/canonical-adjudication-schema-v1.json",
            predictions=self.active_v3_predictions,
            pending_authority=None,
            transition=None,
            revocation=self.revocation,
            attempt_root=root,
            attempt_id="formal-golden",
            adapter_batch=batch,
        )

    def _inputs(self, *, raw: bytes | None = None, mode: str = "formal") -> dict[str, object]:
        prediction_bytes = self.raw if raw is None else raw
        preflight = preflight_prediction_batch(raw=prediction_bytes, adapter_batch=self.batch, ingress="current-v1")
        score = score_prediction_batch(adapter_batch=self.batch, preflight=preflight, mode=mode)
        return {
            "adapter_batch": self.batch,
            "ingress": "current-v1",
            "preflight": preflight,
            "raw_predictions": prediction_bytes,
            "score_result": score,
            "schema_path": self.experiment_root / "config/measurement/canonical-adjudication-schema-v1.json",
        }

    def test_complete_formal_attempt_preserves_raw_bytes_and_binds_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = run_measurement_attempt(
                mode="formal", attempt_id="complete", attempt_root=Path(directory), inputs=self._inputs()
            )
            target = Path(directory) / "complete"
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))

            self.assertEqual(attempt["status"], "completed")
            self.assertEqual(manifest["role"], "formal")
            decoded = base64.b64decode(manifest["raw_predictions_base64"], validate=True)
            self.assertEqual(decoded, self.raw)
            self.assertEqual(manifest["raw_predictions_sha256"], sha256_bytes(self.raw))
            self.assertEqual(manifest["attempt_sha256"], sha256_bytes(canonical_json_bytes({
                key: value for key, value in manifest.items() if key != "attempt_sha256"
            })))
            self.assertEqual(set(manifest["artifacts"]), {
                "case-outcomes.json", "diagnostics.json", "metrics.json", "parsed-predictions.json", "report.json"
            })
            self.assertEqual(
                validate_measurement_attempt(
                    attempt_root=target,
                    adapter_batch=self.batch,
                    schema_raw=(self.experiment_root / "config/measurement/canonical-adjudication-schema-v1.json").read_bytes(),
                )["status"],
                "completed",
            )

    def test_blocking_preflight_is_immutable_but_has_no_score_artifacts(self) -> None:
        invalid = json.loads(self.raw.decode("utf-8"))
        invalid["predictions"] = invalid["predictions"][:-1]
        raw = json.dumps(invalid, separators=(",", ":")).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            result = run_measurement_attempt(
                mode="formal", attempt_id="invalid", attempt_root=Path(directory), inputs=self._inputs(raw=raw)
            )
            target = Path(directory) / "invalid"
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))

            self.assertEqual((result["status"], manifest["role"]), ("invalid_preflight", "invalid_preflight"))
            self.assertTrue((target / "parsed-predictions.json").is_file())
            self.assertTrue((target / "diagnostics.json").is_file())
            self.assertFalse((target / "case-outcomes.json").exists())
            self.assertFalse((target / "metrics.json").exists())
            self.assertFalse((target / "report.json").exists())

    def test_diagnostic_only_is_not_promotable_and_targets_are_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diagnostic = run_measurement_attempt(
                mode="diagnostic_only", attempt_id="diagnostic", attempt_root=root, inputs=self._inputs(mode="diagnostic_only")
            )
            self.assertEqual((diagnostic["role"], diagnostic["status"]), ("diagnostic_only", "diagnostic_only"))
            self.assertFalse((root / "diagnostic" / "metrics.json").exists())

            target = root / "collision"
            target.mkdir()
            (target / "sentinel").write_bytes(b"original")
            with self.assertRaisesRegex(AttemptError, "ATTEMPT_TARGET_EXISTS"):
                run_measurement_attempt(mode="formal", attempt_id="collision", attempt_root=root, inputs=self._inputs())
            self.assertEqual((target / "sentinel").read_bytes(), b"original")

    def test_race_and_tampering_are_rejected_without_mutating_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from specchoice_measurement import attempts

            original = attempts._publish_directory_no_replace

            def race(source: Path, target: Path, collision_code: str) -> None:
                target.mkdir()
                (target / "sentinel").write_bytes(b"racer")
                original(source, target, collision_code)

            with patch("specchoice_measurement.attempts._publish_directory_no_replace", side_effect=race):
                with self.assertRaisesRegex(AttemptError, "ATTEMPT_TARGET_EXISTS"):
                    run_measurement_attempt(mode="formal", attempt_id="race", attempt_root=root, inputs=self._inputs())
            self.assertEqual((root / "race" / "sentinel").read_bytes(), b"racer")

            run_measurement_attempt(mode="formal", attempt_id="tamper", attempt_root=root, inputs=self._inputs())
            (root / "tamper" / "metrics.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(AttemptError, "ATTEMPT_ARTIFACT_HASH_MISMATCH"):
                validate_measurement_attempt(attempt_root=root / "tamper")

    def test_self_consistent_forged_derived_artifacts_fail_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_measurement_attempt(mode="formal", attempt_id="forged", attempt_root=root, inputs=self._inputs())
            target = root / "forged"
            forged = {"disposition": {"denominator": 7, "numerator": 0}}
            forged_raw = canonical_json_bytes(forged)
            (target / "metrics.json").write_bytes(forged_raw)
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))
            manifest["artifacts"]["metrics.json"] = {
                "byte_length": len(forged_raw), "sha256": sha256_bytes(forged_raw)
            }
            manifest["attempt_sha256"] = sha256_bytes(canonical_json_bytes({
                key: value for key, value in manifest.items() if key != "attempt_sha256"
            }))
            (target / "attempt.json").write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(AttemptError, "ATTEMPT_REPLAY_ARTIFACT_MISMATCH"):
                validate_measurement_attempt(
                    attempt_root=target,
                    adapter_batch=self.batch,
                    schema_raw=(self.experiment_root / "config/measurement/canonical-adjudication-schema-v1.json").read_bytes(),
                )

    def test_attempt_validation_rejects_symlinked_manifest_and_all_retained_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_measurement_attempt(mode="formal", attempt_id="linked", attempt_root=root, inputs=self._inputs())
            target = root / "linked"
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))
            outside = root / "outside"
            outside.mkdir()

            for name in ("attempt.json", *manifest["artifacts"]):
                owned = target / name
                external = outside / name
                shutil.copy2(owned, external)
                owned.unlink()
                owned.symlink_to(external)
                code = "ATTEMPT_MANIFEST_INVALID" if name == "attempt.json" else "ATTEMPT_ARTIFACT_INVALID"
                with self.assertRaisesRegex(AttemptError, code):
                    validate_measurement_attempt(attempt_root=target)
                owned.unlink()
                shutil.copy2(external, owned)

    def test_attempt_validation_rejects_leaf_swaps_before_no_follow_open(self) -> None:
        """A leaf changed after lstat cannot redirect the descriptor-backed read."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_measurement_attempt(mode="formal", attempt_id="swapped", attempt_root=root, inputs=self._inputs())
            target = root / "swapped"
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))
            outside = root / "outside"
            outside.mkdir()

            for name in ("attempt.json", "diagnostics.json"):
                owned = target / name
                external = outside / name
                shutil.copy2(owned, external)
                original_open = filesystem.os.open

                def swap_before_open(path: Path | str, flags: int, *args: object, **kwargs: object) -> int:
                    if path == owned.name and "dir_fd" in kwargs:
                        owned.unlink()
                        owned.symlink_to(external)
                    return original_open(path, flags, *args, **kwargs)

                code = "ATTEMPT_MANIFEST_INVALID" if name == "attempt.json" else "ATTEMPT_ARTIFACT_INVALID"
                with patch("specchoice_evidence.filesystem.os.open", side_effect=swap_before_open):
                    with self.assertRaisesRegex(AttemptError, code):
                        validate_measurement_attempt(attempt_root=target)
                self.assertTrue(owned.is_symlink())
                owned.unlink()
                shutil.copy2(external, owned)

    def test_public_formal_cli_rejects_prediction_schema_manifest_and_retained_artifact_leaf_races(self) -> None:
        """Every formal reader must use the descriptor-held value it validated."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._pending_formal_args(root / "attempts")
            original_read = filesystem.read_authoritative_file

            for path, code in (
                (args.predictions, "FORMAL_PREDICTIONS_UNREADABLE"),
                (args.schema, "ATTEMPT_SCHEMA_UNREADABLE"),
            ):
                with self.subTest(role=path.name):
                    def swapped_read(parent: Path, relative: str, *, target: Path = path):
                        if parent == target.parent and relative == target.name:
                            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
                        return original_read(parent, relative)

                    with patch("specchoice_measurement.cli.read_authoritative_file", side_effect=swapped_read, create=True):
                        with self.assertRaisesRegex(AttemptError, code):
                            command_run_formal_measurement(args)
                    self.assertFalse(args.attempt_root.exists())

    def test_public_adversarial_validator_rejects_report_oracle_golden_schema_and_attempt_leaf_races(self) -> None:
        """The report validator derives its identity from held public inputs, never report claims."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            formal_args = self._pending_formal_args(root / "attempts")
            formal_args.attempt_id = "formal"
            command_run_formal_measurement(formal_args)
            report = root / "adversarial.json"
            args = SimpleNamespace(
                authority=formal_args.authority,
                bundle=formal_args.bundle,
                rules=formal_args.rules,
                schema=formal_args.schema,
                predictions=formal_args.predictions,
                oracle=formal_args.oracle,
                pending_authority=self.pending_authority,
                transition=self.transition,
                formal_attempt=root / "attempts/formal",
                report=report,
            )
            command_run_adversarial_oracles(args)
            original_read = filesystem.read_authoritative_file
            for path in (args.report, args.oracle, args.predictions, args.schema):
                with self.subTest(role=path.name):
                    def swapped_read(parent: Path, relative: str, *, target: Path = path):
                        if parent == target.parent and relative == target.name:
                            raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
                        return original_read(parent, relative)

                    with patch("specchoice_measurement.cli.read_authoritative_file", side_effect=swapped_read, create=True):
                        with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
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
                            )

    def test_formal_cli_writes_one_clean_all_eleven_attempt_and_refuses_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._pending_formal_args(root)
            self.assertEqual(command_run_formal_measurement(args), 0)
            target = root / "formal-golden"
            manifest = json.loads((target / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual((manifest["role"], manifest["status"]), ("formal", "completed"))
            self.assertEqual(json.loads((target / "diagnostics.json").read_text(encoding="utf-8")), [])
            self.assertEqual(len(json.loads((target / "case-outcomes.json").read_text(encoding="utf-8"))), 11)
            self.assertEqual(
                json.loads((target / "metrics.json").read_text(encoding="utf-8")),
                {"disposition": {"denominator": 7, "numerator": 7}, "evidence_integrity": {"denominator": 7, "numerator": 7}, "identity": {"denominator": 6, "numerator": 6}, "surfacing": {"denominator": 7, "numerator": 7}},
            )
            for name in manifest["artifacts"]:
                content = (target / name).read_bytes()
                self.assertEqual(manifest["artifacts"][name], {"byte_length": len(content), "sha256": sha256_bytes(content)})
            original = (target / "attempt.json").read_bytes()
            with self.assertRaisesRegex(AttemptError, "ATTEMPT_TARGET_EXISTS"):
                command_run_formal_measurement(args)
            self.assertEqual((target / "attempt.json").read_bytes(), original)

            active_args = self._active_formal_args(root / "active-attempts")
            self.assertEqual(command_run_formal_measurement(active_args), 0)
            self.assertEqual(
                validate_measurement_attempt(
                    attempt_root=active_args.attempt_root / active_args.attempt_id,
                    adapter_batch=active_args.adapter_batch,
                    schema_raw=active_args.schema.read_bytes(),
                )["status"],
                "completed",
            )
            self.assertEqual(
                command_validate_attempt(SimpleNamespace(
                    attempt=active_args.attempt_root / active_args.attempt_id,
                    authority=active_args.authority,
                    bundle=active_args.bundle,
                    rules=active_args.rules,
                    schema=active_args.schema,
                    pending_authority=None,
                    transition=None,
                    revocation=active_args.revocation,
                )),
                0,
            )
            with self.assertRaisesRegex(AttemptError, "ATTEMPT_BINDINGS_INVALID"):
                command_validate_attempt(SimpleNamespace(
                    attempt=self.experiment_root / "runs/measurement-attempts/formal-golden-pr2164-v1",
                    authority=active_args.authority,
                    bundle=active_args.bundle,
                    rules=active_args.rules,
                    schema=active_args.schema,
                    pending_authority=None,
                    transition=None,
                    revocation=active_args.revocation,
                ))
            with self.assertRaisesRegex(AdapterError, "ADAPTER_BATCH_NOT_SCORE_ELIGIBLE"):
                command_validate_attempt(SimpleNamespace(
                    attempt=active_args.attempt_root / active_args.attempt_id,
                    authority=active_args.authority,
                    bundle=active_args.bundle,
                    rules=active_args.rules,
                    schema=active_args.schema,
                    pending_authority=self.pending_authority,
                    transition=None,
                    revocation=active_args.revocation,
                ))

    def test_adversarial_cli_is_diagnostic_only_and_matches_every_frozen_oracle(self) -> None:
        v4_golden = self.experiment_root / "fixtures/measurement/golden-predictions-v4.json"
        v4_contract = self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v4.json"
        contract_result = validate_required_diagnostics_v4(
            contract=v4_contract, golden_predictions=v4_golden
        )
        self.assertEqual(contract_result["case_count"], 17)
        contract_value, _ = _canonical_file(v4_contract, "invalid")
        golden_value, _ = _canonical_file(v4_golden, "invalid")
        self.assertEqual(
            [case["id"] for case in contract_value["cases"]],
            [
                "unknown-top-level-field", "missing-outcome", "duplicate-outcome",
                "candidate-not-surfaced", "candidate-accepted", "candidate-review-status",
                "candidate-evidence-empty", "positive-not-surfaced", "positive-classified-out",
                "accepted-name-missing", "evidence-source-changed", "evidence-empty-range",
                "evidence-text-mismatch", "negative-null-evidence", "negative-surfaced",
                "unknown-outcome-field", "complete-multi-diagnostic-order",
            ],
        )
        for case in contract_value["cases"]:
            mutated = _apply_successor_mutations(golden_value, case["mutations"])
            self.assertEqual(
                _evaluate_successor_payload(mutated, golden_value),
                case["expected_diagnostics"],
                case["id"],
            )
            self.assertFalse(case["metric_output_allowed"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            formal_args = self._pending_formal_args(root / "attempts")
            formal_args.attempt_id = "formal"
            self.assertEqual(command_run_formal_measurement(formal_args), 0)
            report = root / "adversarial.json"
            args = SimpleNamespace(
                authority=formal_args.authority,
                bundle=formal_args.bundle,
                rules=formal_args.rules,
                schema=formal_args.schema,
                predictions=formal_args.predictions,
                oracle=formal_args.oracle,
                pending_authority=self.pending_authority,
                transition=self.transition,
                formal_attempt=root / "attempts/formal",
                report=report,
            )
            self.assertEqual(command_run_adversarial_oracles(args), 0)
            payload = validate_adversarial_report(
                report_path=report,
                formal_attempt=args.formal_attempt,
                authority=args.authority,
                bundle=args.bundle,
                rules=args.rules,
                schema=args.schema,
                predictions=args.predictions,
                oracle=args.oracle,
                pending_authority=args.pending_authority,
                transition=args.transition,
            )
            self.assertEqual(payload["status"], "diagnostic_only")
            self.assertEqual(len(payload["cases"]), 12)
            self.assertTrue(all(case["role"] == "diagnostic_only" and case["matched"] for case in payload["cases"]))
            attempt_root = root / "adversarial-attempts"
            self.assertTrue(all((attempt_root / case["attempt_id"] / "attempt.json").is_file() for case in payload["cases"]))
            self.assertNotIn("metrics", payload)
            original_payload = deepcopy(payload)

            def assert_invalid_attempt_id(attempt_id: str) -> None:
                tampered = deepcopy(original_payload)
                tampered["cases"][0]["attempt_id"] = attempt_id
                report.write_bytes(canonical_json_bytes(tampered))
                with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
                    validate_adversarial_report(report_path=report, formal_attempt=args.formal_attempt)

            assert_invalid_attempt_id(str((attempt_root / "oracle-01").resolve()))

            outside = root / "outside"
            outside.mkdir()
            shutil.copytree(attempt_root / "oracle-01", outside / "oracle-01")
            assert_invalid_attempt_id("../outside/oracle-01")

            for name in ("attempt.json", "diagnostics.json", "parsed-predictions.json"):
                owned = attempt_root / "oracle-01" / name
                external = outside / name
                shutil.copy2(owned, external)
                owned.unlink()
                owned.symlink_to(external)
                report.write_bytes(canonical_json_bytes(original_payload))
                with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
                    validate_adversarial_report(report_path=report, formal_attempt=args.formal_attempt)
                owned.unlink()
                shutil.copy2(external, owned)

            shutil.rmtree(attempt_root / "oracle-01")
            (attempt_root / "oracle-01").symlink_to(outside / "oracle-01", target_is_directory=True)
            report.write_bytes(canonical_json_bytes(original_payload))
            with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
                validate_adversarial_report(report_path=report, formal_attempt=args.formal_attempt)

            with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
                report.write_bytes(canonical_json_bytes({"status": "formal"}))
                validate_adversarial_report(report_path=report, formal_attempt=args.formal_attempt)

            active_formal = self._active_formal_args(root / "active-attempts")
            active_formal.attempt_id = "formal"
            self.assertEqual(command_run_formal_measurement(active_formal), 0)
            active_report = root / "active-adversarial.json"
            active_args = SimpleNamespace(
                authority=active_formal.authority,
                bundle=active_formal.bundle,
                rules=active_formal.rules,
                schema=active_formal.schema,
                predictions=active_formal.predictions,
                oracle=self.active_v3_oracle,
                pending_authority=None,
                transition=None,
                revocation=self.revocation,
                formal_attempt=active_formal.attempt_root / "formal",
                report=active_report,
            )
            self.assertEqual(command_run_adversarial_oracles(active_args), 0)
            self.assertEqual(
                validate_adversarial_report(
                    report_path=active_report,
                    formal_attempt=active_args.formal_attempt,
                    authority=active_args.authority,
                    bundle=active_args.bundle,
                    rules=active_args.rules,
                    schema=active_args.schema,
                    predictions=active_args.predictions,
                    oracle=active_args.oracle,
                    revocation=active_args.revocation,
                )["status"],
                "diagnostic_only",
            )

            legacy_golden = json.loads(self.raw.decode("utf-8"))
            successor_golden = json.loads(self.active_v3_predictions.read_text(encoding="utf-8"))
            projected_golden = deepcopy(successor_golden)
            projected_golden["adapter_batch_sha256"] = legacy_golden["adapter_batch_sha256"]
            self.assertEqual(projected_golden, legacy_golden)

            legacy_oracle = json.loads((self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v1.json").read_text(encoding="utf-8"))
            successor_oracle = json.loads(self.active_v3_oracle.read_text(encoding="utf-8"))
            projected_oracle = deepcopy(successor_oracle)
            self.assertEqual(len(projected_oracle["oracles"]), len(legacy_oracle["oracles"]))
            for legacy_entry, successor_entry in zip(legacy_oracle["oracles"], projected_oracle["oracles"], strict=True):
                successor_entry["raw_input_identity"]["base_fixture"] = legacy_entry["raw_input_identity"]["base_fixture"]
                successor_entry["raw_input_identity"]["base_sha256"] = legacy_entry["raw_input_identity"]["base_sha256"]
            self.assertEqual(projected_oracle, legacy_oracle)

            for label, predictions, oracle in (
                ("v2-golden-v1-oracle", self.active_v3_predictions, self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v1.json"),
                ("v1-golden-v2-oracle", self.experiment_root / "fixtures/measurement/golden-predictions-v1.json", self.active_v3_oracle),
            ):
                with self.subTest(pair=label):
                    blocked_report = root / f"{label}.json"
                    blocked_args = SimpleNamespace(**{
                        **vars(active_args), "predictions": predictions, "oracle": oracle, "report": blocked_report,
                    })
                    with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_ORACLE_INVALID"):
                        command_run_adversarial_oracles(blocked_args)
                    self.assertFalse(blocked_report.exists())
                    self.assertFalse((root / f"{blocked_report.stem}-attempts").exists())

            for label, mutate in (
                ("missing", lambda identity: identity.pop("base_sha256")),
                ("extra", lambda identity: identity.update(unexpected="value")),
                ("type-invalid", lambda identity: identity.update(base_fixture=1)),
                ("wrong-digest", lambda identity: identity.update(base_sha256="0" * 64)),
            ):
                with self.subTest(identity=label):
                    tampered = deepcopy(successor_oracle)
                    mutate(tampered["oracles"][0]["raw_input_identity"])
                    tampered_oracle = root / f"tampered-{label}.json"
                    tampered_oracle.write_bytes(canonical_json_bytes(tampered))
                    blocked_report = root / f"tampered-{label}-report.json"
                    blocked_args = SimpleNamespace(**{
                        **vars(active_args), "oracle": tampered_oracle, "report": blocked_report,
                    })
                    with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_ORACLE_INVALID"):
                        command_run_adversarial_oracles(blocked_args)
                    self.assertFalse(blocked_report.exists())
                    self.assertFalse((root / f"{blocked_report.stem}-attempts").exists())

    def test_adversarial_report_rejects_forged_formal_attempt_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "adversarial-oracle-results-v2.json"
            source = self.experiment_root / "reports/h1/adversarial-oracle-results-v2.json"
            shutil.copy2(source, report)
            shutil.copytree(
                source.parent / "adversarial-oracle-results-v2-attempts",
                root / "adversarial-oracle-results-v2-attempts",
            )
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["bindings"]["formal_attempt_sha256"] = "0" * 64
            report.write_bytes(canonical_json_bytes(payload))

            with self.assertRaisesRegex(AttemptError, "ADVERSARIAL_REPORT_INVALID"):
                validate_adversarial_report(
                    report_path=report,
                    formal_attempt=self.experiment_root / "runs/measurement-attempts/formal-golden-pr2164-v1",
                )


    def test_fresh_v4_chain_is_deterministic_exact_resume_and_has_expected_metrics(self) -> None:
        closure = {"schema_version": "runtime-executable-closure-v4", "freeze_commit": "f" * 40}
        authority = self.experiment_root / "phase2/source-authority.json"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "attempt.json"
            with patch("specchoice_measurement.attempts.load_runtime_closure_v4", return_value=closure):
                self.assertFalse(validate_fresh_v4_target(target=target, runtime_closure=closure, authority_path=authority))
                target.write_bytes(b"fixed")
                self.assertTrue(validate_fresh_v4_target(target=target, runtime_closure=closure, authority_path=authority, expected=b"fixed"))
                with self.assertRaisesRegex(AttemptError, "V4_TARGET_DIVERGED"):
                    validate_fresh_v4_target(target=target, runtime_closure=closure, authority_path=authority, expected=b"other")

    def test_fresh_formal_v6_fixed_target_exact_resume_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment, closure = self._copy_fresh_repository(repository)
            authority = experiment / "phase2/source-authority.json"
            with (
                patch("specchoice_measurement.adapter.load_runtime_closure_v4", return_value=closure),
                patch("specchoice_measurement.attempts.load_runtime_closure_v4", return_value=closure),
            ):
                write_pr2164_accepted_v6_adapter_batch_v4(
                    repository=repository, runtime_closure=closure, authority_path=authority,
                )
                result = run_fresh_formal_measurement_v6(
                    repository=repository, runtime_closure=closure, authority_path=authority,
                )
                self.assertEqual(result["write_status"], "written")
                self.assertEqual(result["case_count"], 11)
                self.assertEqual(result["metrics"], {
                    "disposition": {"denominator": 8, "numerator": 8},
                    "evidence_integrity": {"denominator": 10, "numerator": 10},
                    "identity": {"denominator": 6, "numerator": 6},
                    "negative_controls": {"denominator": 3, "numerator": 3},
                    "surfacing": {"denominator": 8, "numerator": 8},
                })
                resumed = run_fresh_formal_measurement_v6(
                    repository=repository, runtime_closure=closure, authority_path=authority,
                )
                self.assertEqual(resumed["write_status"], "resumed")
                self.assertTrue(validate_fresh_formal_measurement_v6(
                    repository=repository, runtime_closure=closure, authority_path=authority,
                )["valid"])
            self.assertEqual(
                {path.name for path in (experiment / "runs/measurement-attempts/formal-golden-pr2164-v6").iterdir()},
                {"attempt.json", "case-outcomes.json", "diagnostics.json", "metrics.json", "parsed-predictions.json", "report.json"},
            )

    def test_fresh_formal_v6_rejects_partial_symlink_divergence_race_and_task16_adapter(self) -> None:
        for failure in (
            "partial", "symlink", "divergent", "race", "task16", "golden-drift",
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                experiment, closure = self._copy_fresh_repository(repository)
                authority = experiment / "phase2/source-authority.json"
                target = experiment / "runs/measurement-attempts/formal-golden-pr2164-v6"
                with (
                    patch("specchoice_measurement.adapter.load_runtime_closure_v4", return_value=closure),
                    patch("specchoice_measurement.attempts.load_runtime_closure_v4", return_value=closure),
                ):
                    write_pr2164_accepted_v6_adapter_batch_v4(
                        repository=repository, runtime_closure=closure, authority_path=authority,
                    )
                    if failure == "partial":
                        target.mkdir()
                        (target / "attempt.json").write_bytes(b"{}\n")
                        with self.assertRaisesRegex(AttemptError, "FRESH_V6_FORMAL_TARGET_DIVERGED"):
                            run_fresh_formal_measurement_v6(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                    elif failure == "symlink":
                        outside = repository / "outside"
                        outside.mkdir()
                        target.symlink_to(outside, target_is_directory=True)
                        with self.assertRaisesRegex(AttemptError, "FRESH_V6_FORMAL_TARGET_KIND_INVALID"):
                            run_fresh_formal_measurement_v6(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                    elif failure == "divergent":
                        run_fresh_formal_measurement_v6(
                            repository=repository, runtime_closure=closure, authority_path=authority,
                        )
                        (target / "metrics.json").write_bytes(b"{}\n")
                        with self.assertRaisesRegex(AttemptError, "FRESH_V6_FORMAL_TARGET_DIVERGED"):
                            run_fresh_formal_measurement_v6(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                    elif failure == "race":
                        from specchoice_measurement import attempts
                        original = attempts._publish_directory_no_replace

                        def race(source: Path, destination: Path, collision_code: str) -> None:
                            destination.mkdir()
                            (destination / "sentinel").write_bytes(b"racer")
                            original(source, destination, collision_code)

                        with patch("specchoice_measurement.attempts._publish_directory_no_replace", side_effect=race):
                            with self.assertRaisesRegex(AttemptError, "FRESH_V6_FORMAL_TARGET_RACE"):
                                run_fresh_formal_measurement_v6(
                                    repository=repository, runtime_closure=closure, authority_path=authority,
                                )
                        self.assertEqual((target / "sentinel").read_bytes(), b"racer")
                    elif failure == "task16":
                        adapter_target = experiment / "reports/h1/adapter-batch-pr2164-v6.json"
                        shutil.copy2(
                            self.experiment_root / "reports/h1/adapter-batch-pr2164-v5.json",
                            adapter_target,
                        )
                        with self.assertRaisesRegex(AdapterError, "ADAPTER_V4_OUTPUT_DIVERGED"):
                            run_fresh_formal_measurement_v6(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                        self.assertFalse(target.exists())
                    else:
                        golden = experiment / "fixtures/measurement/golden-predictions-v4.json"
                        original_canonical_file = _canonical_file

                        def drift_after_adapter(path: Path, code: str):
                            payload, raw = original_canonical_file(path, code)
                            if path.resolve() == golden.resolve():
                                payload = deepcopy(payload)
                                payload["outcomes"][0]["rationale"] += " drift"
                                raw = canonical_json_bytes(payload)
                            return payload, raw

                        with (
                            patch(
                                "specchoice_measurement.attempts._canonical_file",
                                side_effect=drift_after_adapter,
                            ),
                            self.assertRaisesRegex(AttemptError, "FRESH_V6_GOLDEN_INVALID"),
                        ):
                            run_fresh_formal_measurement_v6(
                                repository=repository,
                                runtime_closure=closure,
                                authority_path=authority,
                            )
                        self.assertFalse(target.exists())

    def test_fresh_adversarial_v7_fixed_target_resume_divergence_and_race(self) -> None:
        for failure in ("resume", "divergent", "symlink", "race"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                experiment, closure = self._copy_fresh_repository(repository)
                authority = experiment / "phase2/source-authority.json"
                target = experiment / "reports/h1/adversarial-oracle-results-v7.json"
                with (
                    patch("specchoice_measurement.adapter.load_runtime_closure_v4", return_value=closure),
                    patch("specchoice_measurement.attempts.load_runtime_closure_v4", return_value=closure),
                ):
                    write_pr2164_accepted_v6_adapter_batch_v4(
                        repository=repository, runtime_closure=closure, authority_path=authority,
                    )
                    run_fresh_formal_measurement_v6(
                        repository=repository, runtime_closure=closure, authority_path=authority,
                    )
                    if failure == "symlink":
                        outside = repository / "outside-report"
                        outside.write_bytes(b"outside")
                        target.symlink_to(outside)
                        with self.assertRaisesRegex(AttemptError, "FRESH_V7_ADVERSARIAL_TARGET_KIND_INVALID"):
                            run_fresh_adversarial_suite_v7(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                    elif failure == "race":
                        def race(path: Path, content: bytes) -> None:
                            target.write_bytes(b"racer")
                            raise FileExistsError(path)

                        with patch("specchoice_measurement.attempts._write_exact", side_effect=race):
                            with self.assertRaisesRegex(AttemptError, "FRESH_V7_ADVERSARIAL_TARGET_RACE"):
                                run_fresh_adversarial_suite_v7(
                                    repository=repository, runtime_closure=closure, authority_path=authority,
                                )
                        self.assertEqual(target.read_bytes(), b"racer")
                    else:
                        written = run_fresh_adversarial_suite_v7(
                            repository=repository, runtime_closure=closure, authority_path=authority,
                        )
                        self.assertEqual(written["case_count"], 17)
                        payload = json.loads(target.read_text(encoding="utf-8"))
                        self.assertEqual(payload["schema_version"], "adversarial-oracle-results-v7")
                        self.assertEqual(payload["bindings"]["closure_freeze_commit"], "f" * 40)
                        if failure == "resume":
                            resumed = run_fresh_adversarial_suite_v7(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )
                            self.assertEqual(resumed["write_status"], "resumed")
                            self.assertTrue(validate_fresh_adversarial_result_v7(
                                repository=repository, runtime_closure=closure, authority_path=authority,
                            )["valid"])
                        else:
                            target.write_bytes(b"{}\n")
                            with self.assertRaisesRegex(AttemptError, "FRESH_V7_ADVERSARIAL_REPORT_DIVERGED"):
                                run_fresh_adversarial_suite_v7(
                                    repository=repository, runtime_closure=closure, authority_path=authority,
                                )


if __name__ == "__main__":
    unittest.main()
