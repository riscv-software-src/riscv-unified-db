"""Public H1 packet, readiness, and human-decision contracts."""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence import cli as cli_module
from specchoice_evidence.publication import resolve_historical_path
from specchoice_measurement import h1
from specchoice_measurement.h1 import H1Error


class H1PublicContractTests(unittest.TestCase):
    def test_v5_h1_question_contract_is_exactly_seven_questions(self) -> None:
        root = Path(__file__).parents[1]
        value = json.loads((root / "config/measurement/h1-semantic-review-questions-v1.json").read_text())
        h1.validate_v5_h1_question_contract(value)
        value["question_ids"] = value["question_ids"][:-1]
        with self.assertRaisesRegex(H1Error, "V5_H1_QUESTION_CONTRACT_INVALID"):
            h1.validate_v5_h1_question_contract(value)

        questions = root / "config/measurement/h1-semantic-review-questions-v2.json"
        schema = root / "config/measurement/h1-review-schema-v4.json"
        bundle = root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        result = h1.validate_h1_semantic_questions_v2(
            questions=questions, bundle_root=bundle
        )
        self.assertEqual(result["question_count"], 7)
        self.assertEqual(result["question_ids"], list(h1._SUCCESSOR_QUESTION_IDS))
        schema_result = h1.validate_h1_review_schema_v4(
            schema=schema, questions=questions, bundle_root=bundle
        )
        self.assertEqual(schema_result["questions_sha256"], result["questions_sha256"])
        complete = json.loads(questions.read_text(encoding="utf-8"))
        self.assertEqual(
            {fixture for question in complete["questions"] for fixture in question["fixture_ids"]},
            set(h1._SUCCESSOR_FIXTURE_IDS),
        )
        self.assertEqual(
            {policy for question in complete["questions"] for policy in question["policy_ids"]},
            {"CACHE", "PBMTE"},
        )
        self.assertTrue(all(len(question["evidence"]) == len(question["fixture_ids"]) for question in complete["questions"]))
        self.assertFalse(any(
            forbidden in question
            for question in complete["questions"]
            for forbidden in ("reviewer", "reviewer_identity", "signature", "timestamp", "choice")
        ))
        with tempfile.TemporaryDirectory(dir=root) as directory:
            temporary = Path(directory)
            unknown = deepcopy(complete)
            unknown["questions"][0]["unexpected"] = True
            unknown["canonical_semantic_content_sha256"] = sha256_bytes(canonical_json_bytes({
                key: item for key, item in unknown.items() if key != "canonical_semantic_content_sha256"
            }))
            unknown_path = temporary / "unknown.json"
            unknown_path.write_bytes(canonical_json_bytes(unknown))
            with self.assertRaisesRegex(H1Error, "H1_SEMANTIC_QUESTION_INVALID"):
                h1.validate_h1_semantic_questions_v2(questions=unknown_path)

            drifted = deepcopy(complete)
            drifted["questions"][0]["prompt"] += " drift"
            drifted_path = temporary / "drifted.json"
            drifted_path.write_bytes(canonical_json_bytes(drifted))
            with self.assertRaisesRegex(H1Error, "H1_SEMANTIC_QUESTIONS_HASH_INVALID"):
                h1.validate_h1_semantic_questions_v2(questions=drifted_path)

    def test_h1_v3_exposes_readiness_and_v2_decision_validation_without_human_writers(self) -> None:
        from specchoice_measurement.h1 import (  # noqa: PLC0415
            build_h1_packet,
            render_h1_markdown,
            validate_h1_decision_v2,
            validate_h1_ontology_decision_v1,
            validate_h1_ontology_options_v1,
            validate_h1_packet,
            validate_h1_readiness_v3,
            validate_h1_route_supersession_v1,
            write_h1_readiness_v3,
            write_h1_ontology_options_v1,
        )

        for value in (
            build_h1_packet,
            render_h1_markdown,
            validate_h1_packet,
            write_h1_readiness_v3,
            validate_h1_readiness_v3,
            validate_h1_decision_v2,
            validate_h1_ontology_decision_v1,
            validate_h1_route_supersession_v1,
            validate_h1_ontology_options_v1,
            write_h1_ontology_options_v1,
        ):
            self.assertTrue(callable(value))
        self.assertFalse(any(
            "decision" in name
            and "validate" not in name
            and name != "write_h1_source_gold_decision_v6"
            for name in dir(h1)
        ))
        from specchoice_measurement.cli import build_parser  # noqa: PLC0415

        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "build-h1-packet", "--formal-attempt", "formal", "--adversarial-report", "adversarial",
                "--schema", "schema", "--output", "packet", "--markdown", "markdown",
            ])
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "write-h1-readiness-v3", "--formal-attempt", "formal", "--adversarial-result", "adversarial",
                "--packet", "packet", "--markdown", "markdown", "--schema", "schema",
                "--source-authority", "authority", "--canonical-revocation", "revocation", "--bundle", "bundle",
                "--rules", "rules", "--predictions", "predictions", "--oracle", "oracle",
                "--offline-replay", "replay", "--plan-summary", "/summary", "--output", "readiness",
            ])
        command_args = {
            "validate-h1-route-supersession-v1": [
                "--supersession", "supersession", "--schema", "schema", "--packet", "packet",
                "--markdown", "markdown", "--readiness", "readiness",
            ],
            "validate-h1-ontology-options-v1": ["--options", "options"],
        }
        for command, arguments in command_args.items():
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command, *arguments]).command, command)
        root = Path(__file__).parents[1]
        options_path = root / "config/measurement/h1-ontology-policy-options-v1.json"
        supersession_path = root / "receipts/h1-review-route-supersession-v1.json"
        self.assertEqual(validate_h1_ontology_options_v1(options=options_path)["schema_version"], "h1-ontology-policy-options-v1")
        packet_path = root / "reports/h1/h1-source-gold-review-v3/h1-source-gold-review-v3.json"
        readiness_path = root / "receipts/h1-review-readiness-v3.json"
        with tempfile.TemporaryDirectory(dir=root) as directory:
            temporary = Path(directory)
            options_value = json.loads(options_path.read_text(encoding="utf-8"))
            supersession_value = json.loads(supersession_path.read_text(encoding="utf-8"))

            def with_self_hash(value: dict[str, object], field: str) -> dict[str, object]:
                value[field] = sha256_bytes(canonical_json_bytes({
                    key: item for key, item in value.items() if key != field
                }))
                return value

            def ontology_decision() -> dict[str, object]:
                value: dict[str, object] = {
                    "bindings": {
                        "options_sha256": options_value["options_sha256"],
                        "supersession_sha256": supersession_value["supersession_sha256"],
                    },
                    "cache_policy": {
                        "rationale": "Keep the cache identity unified.",
                        "selection": "unified_cache_block_identity",
                    },
                    "external_publication_authorized": False,
                    "pbmte_policy": {
                        "rationale": "PBMTE is absent from discovery.",
                        "selection": "excluded_from_discovery",
                    },
                    "reviewer": "independent-human-reviewer",
                    "schema_version": "h1-source-gold-ontology-decision-v1",
                    "signature": "signed:ontology-policy",
                    "timestamp": "2026-08-02T00:00:00Z",
                }
                return with_self_hash(value, "decision_sha256")

            def validate_ontology(
                decision: Path, *, options: Path = options_path, supersession: Path = supersession_path,
            ) -> dict[str, object]:
                with patch.object(
                    h1,
                    "validate_h1_route_supersession_v1",
                    side_effect=AssertionError("ontology validation must not replay historical H1"),
                ):
                    return validate_h1_ontology_decision_v1(
                        options=options, supersession=supersession, decision=decision,
                    )

            valid_decision = ontology_decision()
            valid_decision_path = temporary / "ontology-decision.json"
            valid_decision_path.write_bytes(canonical_json_bytes(valid_decision))
            self.assertEqual(
                validate_ontology(valid_decision_path),
                {
                    "artifact_sha256": sha256_bytes(valid_decision_path.read_bytes()),
                    "decision_sha256": valid_decision["decision_sha256"],
                    "selected_policy": {
                        "cache": "unified_cache_block_identity",
                        "pbmte": "excluded_from_discovery",
                    },
                    "valid": True,
                },
            )
            invalid_decision_path = temporary / "invalid-ontology-decision.json"
            for timestamp in (
                "", "   ", "not-a-timestamp", "2026-08-02T00:00:00",
                "2026-08-02T02:00:00+02:00", "2026-02-30T00:00:00Z", "2026-08-02T24:00:00Z",
            ):
                with self.subTest(ontology_timestamp=timestamp):
                    invalid = ontology_decision()
                    invalid["timestamp"] = timestamp
                    invalid_decision_path.write_bytes(canonical_json_bytes(with_self_hash(invalid, "decision_sha256")))
                    with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_DECISION_INVALID"):
                        validate_ontology(invalid_decision_path)
            for field in ("reviewer", "signature"):
                with self.subTest(ontology_human_field=field):
                    invalid = ontology_decision()
                    invalid[field] = " \t "
                    invalid_decision_path.write_bytes(canonical_json_bytes(with_self_hash(invalid, "decision_sha256")))
                    with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_DECISION_INVALID"):
                        validate_ontology(invalid_decision_path)
            for policy_name in ("pbmte_policy", "cache_policy"):
                with self.subTest(ontology_rationale=policy_name):
                    invalid = ontology_decision()
                    assert isinstance(invalid[policy_name], dict)
                    invalid[policy_name]["rationale"] = " \t "
                    invalid_decision_path.write_bytes(canonical_json_bytes(with_self_hash(invalid, "decision_sha256")))
                    with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_DECISION_INVALID"):
                        validate_ontology(invalid_decision_path)
            route_bindings = supersession_value["bindings"]
            self.assertIsInstance(route_bindings, dict)
            self.assertEqual(len(route_bindings), 8)
            for binding in sorted(route_bindings):
                with self.subTest(supersession_binding=binding):
                    invalid_supersession = deepcopy(supersession_value)
                    invalid_supersession["bindings"][binding] = "0" * 64
                    with_self_hash(invalid_supersession, "supersession_sha256")
                    invalid_supersession_path = temporary / f"supersession-{binding}.json"
                    invalid_supersession_path.write_bytes(canonical_json_bytes(invalid_supersession))
                    with self.assertRaisesRegex(H1Error, "H1_ROUTE_SUPERSESSION_INVALID"):
                        validate_ontology(valid_decision_path, supersession=invalid_supersession_path)

            unknown_id = deepcopy(options_value)
            unknown_id["pbmte_choices"][0]["id"] = "unknown_policy"
            changed_consequence = deepcopy(options_value)
            changed_consequence["cache_choices"][0]["consequences"]["scope"] = "changed"
            changed_order = deepcopy(options_value)
            changed_order["pbmte_choices"].reverse()
            forbidden_selection = deepcopy(options_value)
            forbidden_selection["selection"] = "excluded_from_discovery"
            forbidden_human_field = deepcopy(options_value)
            forbidden_human_field["reviewer"] = "test-only-reviewer"
            invalid_options_path = temporary / "invalid-options.json"
            for attack, invalid_options in (
                ("unknown_id", unknown_id),
                ("changed_consequence", changed_consequence),
                ("changed_order", changed_order),
                ("forbidden_selection", forbidden_selection),
                ("forbidden_human_field", forbidden_human_field),
            ):
                with self.subTest(options_attack=attack):
                    invalid_options_path.write_bytes(canonical_json_bytes(
                        with_self_hash(invalid_options, "options_sha256")
                    ))
                    with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_INVALID"):
                        validate_h1_ontology_options_v1(options=invalid_options_path)

            missing_options_path = temporary / "missing-options.json"
            noncanonical_options_path = temporary / "noncanonical-options.json"
            noncanonical_options_path.write_text(json.dumps(options_value, indent=2), encoding="utf-8")
            symlink_options_path = temporary / "symlink-options.json"
            symlink_options_path.symlink_to(options_path)
            fifo_options_path = temporary / "fifo-options.json"
            os.mkfifo(fifo_options_path)
            for attack, invalid_path in (
                ("missing", missing_options_path),
                ("noncanonical", noncanonical_options_path),
                ("symlink", symlink_options_path),
                ("fifo", fifo_options_path),
            ):
                with self.subTest(options_path_attack=attack):
                    with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_INVALID"):
                        validate_h1_ontology_options_v1(options=invalid_path)

            generated_options_path = temporary / "generated-options.json"
            self.assertEqual(write_h1_ontology_options_v1(output=generated_options_path), options_value)
            generated_options_raw = generated_options_path.read_bytes()
            with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID"):
                write_h1_ontology_options_v1(output=generated_options_path)
            self.assertEqual(generated_options_path.read_bytes(), generated_options_raw)

            preexisting_options_path = temporary / "preexisting-options.json"
            preexisting_options_path.write_bytes(b"preexisting options\n")
            with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID"):
                write_h1_ontology_options_v1(output=preexisting_options_path)
            self.assertEqual(preexisting_options_path.read_bytes(), b"preexisting options\n")

            writer_symlink_target = temporary / "writer-symlink-target.json"
            writer_symlink_target.write_bytes(b"symlink target\n")
            writer_symlink_path = temporary / "writer-symlink-options.json"
            writer_symlink_path.symlink_to(writer_symlink_target)
            with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID"):
                write_h1_ontology_options_v1(output=writer_symlink_path)
            self.assertTrue(writer_symlink_path.is_symlink())
            self.assertEqual(writer_symlink_target.read_bytes(), b"symlink target\n")

            writer_fifo_path = temporary / "writer-fifo-options.json"
            os.mkfifo(writer_fifo_path)
            with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_OPTIONS_OUTPUT_INVALID"):
                write_h1_ontology_options_v1(output=writer_fifo_path)
            self.assertTrue(stat.S_ISFIFO(os.lstat(writer_fifo_path).st_mode))

            legacy_decision = H1PacketTests._decision(
                json.loads(packet_path.read_text(encoding="utf-8")),
                json.loads(readiness_path.read_text(encoding="utf-8")),
            )
            legacy_decision_path = temporary / "legacy-decision.json"
            legacy_decision_path.write_bytes(canonical_json_bytes(legacy_decision))

            def validate_legacy_with_supersession(path: Path) -> dict[str, object]:
                with patch.object(h1, "_ROUTE_SUPERSESSION", path):
                    return validate_h1_decision_v2(
                        schema=root / "config/measurement/h1-review-schema-v2.json", packet=packet_path,
                        readiness=readiness_path, decision=legacy_decision_path,
                    )

            with self.assertRaisesRegex(H1Error, "H1_LEGACY_ROUTE_SUPERSEDED"):
                validate_legacy_with_supersession(supersession_path)

            missing_supersession_path = temporary / "missing-supersession.json"
            tampered_supersession = deepcopy(supersession_value)
            tampered_supersession["status"] = "reviewed"
            tampered_supersession_path = temporary / "tampered-supersession.json"
            tampered_supersession_path.write_bytes(canonical_json_bytes(
                with_self_hash(tampered_supersession, "supersession_sha256")
            ))
            symlink_supersession_path = temporary / "symlink-supersession.json"
            symlink_supersession_path.symlink_to(supersession_path)
            fifo_supersession_path = temporary / "fifo-supersession.json"
            os.mkfifo(fifo_supersession_path)
            for attack, invalid_path in (
                ("missing", missing_supersession_path),
                ("tampered", tampered_supersession_path),
                ("symlink", symlink_supersession_path),
                ("fifo", fifo_supersession_path),
            ):
                with self.subTest(legacy_supersession_attack=attack):
                    with self.assertRaisesRegex(H1Error, "H1_ROUTE_SUPERSESSION_INVALID"):
                        validate_legacy_with_supersession(invalid_path)


class H1PacketTests(unittest.TestCase):
    semantic_ids = (
        "ts03_adjacency",
        "ts03_empty_null_single_element",
        "ts03_equal_element_stable_order",
        "ts04_unclassified_manual_review",
        "ts05_adjacency",
        "ts05_empty_null_single_element",
        "ts05_equal_element_stable_order",
    )

    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.formal = self.root / "runs/measurement-attempts/formal-golden-pr2164-v1"
        self.adversarial = self.root / "reports/h1/adversarial-oracle-results-v2.json"
        self.active_formal = self.root / "runs/measurement-attempts/formal-golden-pr2164-v2"
        self.active_adversarial = self.root / "reports/h1/adversarial-oracle-results-v3.json"
        self.schema = self.root / "config/measurement/h1-review-schema-v2.json"
        self.bundle = self.root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        self.active_bundle = self.root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        self.rules = self.root / "config/measurement/pr2164-adapter-rules-v1.json"
        self.predictions = self.root / "fixtures/measurement/golden-predictions-v1.json"
        self.oracle = self.root / "fixtures/measurement/adversarial/required-diagnostics-v1.json"
        self.revocation = self.root / "receipts/fixture-closure-revocation-v1.json"
        self.replay = self.root / "receipts/fixture-closure-offline-replay-v3.json"
        self.cutover = self.root / "receipts/source-cutover-readiness-v10.json"

    def test_seven_question_h1_and_four_report_pipeline(self) -> None:
        value = json.loads((self.root / "config/measurement/h1-semantic-review-questions-v1.json").read_text())
        h1.validate_v5_h1_question_contract(value)
        self.assertEqual(value["question_ids"], list(self.semantic_ids))
        questions = self.root / "config/measurement/h1-semantic-review-questions-v2.json"
        schema = self.root / "config/measurement/h1-review-schema-v4.json"
        result = h1.validate_h1_semantic_questions_v2(
            questions=questions,
            bundle_root=self.active_bundle,
        )
        self.assertEqual(result["question_ids"], list(self.semantic_ids))
        self.assertEqual(
            h1.validate_h1_review_schema_v4(
                schema=schema, questions=questions, bundle_root=self.active_bundle
            )["question_count"],
            7,
        )
        from specchoice_measurement.cli import build_parser  # noqa: PLC0415

        parser = build_parser()
        for command in (
            "adapt-pr2164-v6",
            "validate-adapter-batch-v6",
            "run-formal-measurement-v5",
            "validate-formal-measurement-v5",
            "run-adversarial-semantic-suite-v6",
            "validate-adversarial-semantic-result-v6",
            "build-h1-semantic-packet-v6",
            "validate-h1-semantic-packet-v6",
            "write-h1-semantic-readiness-v6",
            "validate-h1-semantic-readiness",
            "validate-h1-semantic-review-decision",
            "write-final-successor-reports",
            "verify-final-successor-reports",
        ):
            self.assertIn(command, parser._subparsers._group_actions[0].choices)

    def test_successor_public_cli_e2e_rejects_forged_adapter_formal_adversarial_and_packet(self) -> None:
        self._run_successor_public_chain(check_direct_report_bypass=False)

    def test_direct_decision_and_final_reports_reject_zero_upstream_bindings(self) -> None:
        self._run_successor_public_chain(check_direct_report_bypass=True)

    def _run_successor_public_chain(
        self, *, check_direct_report_bypass: bool
    ) -> None:
        from specchoice_measurement.cli import build_parser  # noqa: PLC0415

        root = self.root.absolute()
        registry = root / "config/fixture-registry-pr2164-v6.json"
        rules = root / "config/measurement/pr2164-adapter-rules-v3.json"
        semantic_contract = root / "config/measurement/pr2164-semantic-gold-contract-v2.json"
        golden = root / "fixtures/measurement/golden-predictions-v4.json"
        adjudication_schema = root / "config/measurement/canonical-adjudication-schema-v3.json"
        adversarial_contract = root / "fixtures/measurement/adversarial/required-diagnostics-v4.json"
        questions = root / "config/measurement/h1-semantic-review-questions-v2.json"
        h1_schema = root / "config/measurement/h1-review-schema-v4.json"
        measurement_args = [
            "--fixture-registry", str(registry),
            "--rules", str(rules),
            "--semantic-contract", str(semantic_contract),
            "--golden-predictions", str(golden),
            "--bundle-root", str(self.active_bundle.absolute()),
        ]
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(root / "src"),
            }
        )

        def cli(arguments: list[str], *, expected: int = 0) -> dict[str, object] | None:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "specchoice_measurement.cli", *arguments],
                cwd=root,
                env=environment,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                expected,
                completed.stderr.decode("utf-8", "replace"),
            )
            if expected:
                self.assertFalse(completed.stdout)
                return None
            self.assertFalse(completed.stderr)
            return json.loads(completed.stdout)

        with tempfile.TemporaryDirectory(dir=root) as directory:
            temporary = Path(directory)
            legacy_adapter = temporary / "legacy-adapter-must-not-accept-v3.json"
            cli(
                [
                    "adapt-pr2164",
                    "--authority", str(root / "phase2/source-authority.json"),
                    "--bundle", str(self.active_bundle.absolute()),
                    "--rules", str(rules),
                    "--output", str(legacy_adapter),
                ],
                expected=2,
            )
            self.assertFalse(legacy_adapter.exists())
            legacy_attempt_root = temporary / "legacy-attempt-must-not-accept-v3"
            cli(
                [
                    "run-formal-measurement",
                    "--authority", str(root / "phase2/source-authority.json"),
                    "--bundle", str(self.active_bundle.absolute()),
                    "--rules", str(rules),
                    "--schema", str(adjudication_schema),
                    "--predictions", str(golden),
                    "--attempt-root", str(legacy_attempt_root),
                    "--attempt-id", "forbidden-v3",
                ],
                expected=2,
            )
            self.assertFalse(legacy_attempt_root.exists())

            adapter = temporary / "adapter-v6.json"
            adapted = cli(
                ["adapt-pr2164-v6", *measurement_args, "--output", str(adapter)]
            )
            self.assertEqual(
                (adapted["fixture_count"], adapted["raw_file_count"]), (11, 29)
            )
            validated_adapter = cli(
                [
                    "validate-adapter-batch-v6",
                    *measurement_args,
                    "--adapter-batch",
                    str(adapter),
                ]
            )
            self.assertEqual(
                validated_adapter["partition"],
                {"candidate": 2, "negative": 3, "positive": 6},
            )

            attempt_root = temporary / "attempts"
            formal = attempt_root / "formal-v5"
            formal_result = cli(
                [
                    "run-formal-measurement-v5",
                    *measurement_args,
                    "--adapter-batch",
                    str(adapter),
                    "--adjudication-schema",
                    str(adjudication_schema),
                    "--attempt-root",
                    str(attempt_root),
                    "--attempt-id",
                    "formal-v5",
                ]
            )
            expected_metrics = {
                "disposition": {"denominator": 8, "numerator": 8},
                "evidence_integrity": {"denominator": 10, "numerator": 10},
                "identity": {"denominator": 6, "numerator": 6},
                "negative_controls": {"denominator": 3, "numerator": 3},
                "surfacing": {"denominator": 8, "numerator": 8},
            }
            self.assertEqual(formal_result["metrics"], expected_metrics)
            self.assertEqual(
                cli(
                    [
                        "validate-formal-measurement-v5",
                        *measurement_args,
                        "--adapter-batch",
                        str(adapter),
                        "--adjudication-schema",
                        str(adjudication_schema),
                        "--attempt",
                        str(formal),
                    ]
                )["case_count"],
                11,
            )

            adversarial = temporary / "adversarial-v6.json"
            adversarial_args = [
                "--contract", str(adversarial_contract),
                "--golden-predictions", str(golden),
                "--formal-attempt", str(formal),
                "--adapter-batch", str(adapter),
                "--fixture-registry", str(registry),
                "--rules", str(rules),
                "--semantic-contract", str(semantic_contract),
                "--schema", str(adjudication_schema),
                "--bundle-root", str(self.active_bundle.absolute()),
            ]
            self.assertEqual(
                cli(
                    [
                        "run-adversarial-semantic-suite-v6",
                        *adversarial_args,
                        "--output",
                        str(adversarial),
                    ]
                )["case_count"],
                17,
            )
            self.assertTrue(
                cli(
                    [
                        "validate-adversarial-semantic-result-v6",
                        "--report",
                        str(adversarial),
                        *adversarial_args,
                    ]
                )["valid"]
            )

            def successor_h1_inputs(
                *,
                selected_adapter: Path = adapter,
                selected_formal: Path = formal,
                selected_adversarial: Path = adversarial,
                selected_closure: Path | None = None,
                selected_ontology: Path | None = None,
                selected_authority: Path | None = None,
            ) -> dict[str, Path]:
                return {
                    "adapter_batch": selected_adapter,
                    "adversarial_report": selected_adversarial,
                    "adversarial_contract": adversarial_contract,
                    "adjudication_schema": adjudication_schema,
                    "executable_closure": selected_closure or closure,
                    "fixture_registry": registry,
                    "formal_attempt": selected_formal,
                    "golden_predictions": golden,
                    "ontology_decision": selected_ontology
                    or root / "reviews/h1-source-gold-ontology-decision-v1.json",
                    "ontology_options": root
                    / "config/measurement/h1-ontology-policy-options-v1.json",
                    "ontology_supersession": root
                    / "receipts/h1-review-route-supersession-v1.json",
                    "questions": questions,
                    "rules": rules,
                    "semantic_contract": semantic_contract,
                    "schema": h1_schema,
                    "source_authority": selected_authority
                    or root / "phase2/source-authority.json",
                    "bundle_root": self.active_bundle.absolute(),
                }

            def successor_h1_args(**selections: Path) -> list[str]:
                values = successor_h1_inputs(**selections)
                arguments: list[str] = []
                for name, path in values.items():
                    arguments.extend((f"--{name.replace('_', '-')}", str(path)))
                return arguments

            closure = temporary / "runtime-executable-closure-v3.json"
            closure_value = {
                "freeze_commit": "0" * 40,
                "schema_version": "runtime-executable-closure-v3",
            }
            closure.write_bytes(canonical_json_bytes(closure_value))
            active_authority = root / "phase2/source-authority.json"

            def h1_cli(
                arguments: list[str], *, expected: int = 0
            ) -> dict[str, object] | None:
                parsed = build_parser().parse_args(arguments)
                output = tempfile.SpooledTemporaryFile()
                with (
                    patch.object(
                        h1,
                        "_SUCCESSOR_EXECUTABLE_CLOSURE",
                        closure,
                    ),
                    patch.object(
                        h1,
                        "_SUCCESSOR_ONTOLOGY_DECISION",
                        parsed.ontology_decision,
                    ),
                    patch.object(
                        h1,
                        "_ACTIVE_AUTHORITY",
                        parsed.source_authority,
                    ),
                    patch.object(
                        h1,
                        "_SUCCESSOR_HISTORICAL_AUTHORITY",
                        active_authority,
                    ),
                    patch.object(
                        h1,
                        "verify_runtime_closure_v3",
                        return_value=closure_value,
                    ) as closure_validator,
                    patch.object(
                        h1,
                        "validate_accepted_v6_active_authority",
                        return_value={
                            "authority_sha256": sha256_bytes(active_authority.read_bytes()),
                            "status": "accepted_v6_state_chain_verified",
                        },
                    ) as authority_validator,
                    patch.object(sys, "stdout", SimpleNamespace(buffer=output)),
                ):
                    if expected:
                        with self.assertRaises(H1Error):
                            parsed.handler(parsed)
                    else:
                        self.assertEqual(parsed.handler(parsed), 0)
                        closure_validator.assert_called_once_with(
                            closure_value,
                            root.parents[1],
                            authority_pre_state_raw=active_authority.read_bytes(),
                        )
                        authority_validator.assert_called_once_with(root.parents[1])
                if expected:
                    output.close()
                    return None
                output.seek(0)
                raw = output.read()
                output.close()
                return json.loads(raw)

            packet = temporary / "review-v6/review-packet.json"
            markdown = temporary / "review-v6/REVIEW.md"
            self.assertIn(
                "packet_sha256",
                h1_cli(
                    [
                        "build-h1-semantic-packet-v6",
                        *successor_h1_args(),
                        "--output", str(packet),
                        "--markdown", str(markdown),
                    ]
                ),
            )
            self.assertEqual(
                h1_cli(
                    [
                        "validate-h1-semantic-packet-v6",
                        *successor_h1_args(),
                        "--packet", str(packet),
                        "--markdown", str(markdown),
                    ]
                )["schema_version"],
                "h1-source-gold-review-v6",
            )
            readiness = temporary / "readiness-v6.json"
            self.assertEqual(
                h1_cli(
                    [
                        "write-h1-semantic-readiness-v6",
                        *successor_h1_args(),
                        "--packet", str(packet),
                        "--markdown", str(markdown),
                        "--output", str(readiness),
                    ]
                )["schema_version"],
                "h1-semantic-readiness-v6",
            )
            self.assertEqual(
                h1_cli(
                    [
                        "validate-h1-semantic-readiness",
                        *successor_h1_args(),
                        "--packet", str(packet),
                        "--markdown", str(markdown),
                        "--readiness", str(readiness),
                    ]
                )["readiness_sha256"],
                json.loads(readiness.read_bytes())["readiness_sha256"],
            )

            packet_value = json.loads(packet.read_bytes())
            readiness_value = json.loads(readiness.read_bytes())
            schema_result = h1.validate_h1_review_schema_v4(
                schema=h1_schema,
                questions=questions,
                bundle_root=self.active_bundle,
            )
            decision_value: dict[str, object] = {
                "aggregate_disposition": "approved",
                "bindings": {
                    "packet_sha256": packet_value["packet_sha256"],
                    "questions_sha256": schema_result["questions_sha256"],
                    "readiness_sha256": readiness_value["readiness_sha256"],
                    "schema_sha256": schema_result["schema_sha256"],
                },
                "external_publication_authorized": False,
                "fixture_reviews": [
                    {
                        "disposition": "approved",
                        "fixture_id": review["fixture_id"],
                        "rationale": "I reviewed the frozen fixture semantics.",
                        "reviewed_semantics_sha256": review[
                            "reviewed_semantics_sha256"
                        ],
                        "signature": f"human:{review['fixture_id']}",
                    }
                    for review in packet_value["fixture_reviews"]
                ],
                "rationale": "I reviewed every fixture and semantic question.",
                "responses": [
                    {
                        "disposition": "approved",
                        "fixture_signoffs": [
                            {
                                "disposition": "approved",
                                "fixture_id": fixture_id,
                                "signature": f"human:{question['id']}:{fixture_id}",
                            }
                            for fixture_id in question["fixture_ids"]
                        ],
                        "question_id": question["id"],
                        "rationale": "The expected semantics are correct.",
                        "response": "approve_expected_semantics",
                    }
                    for question in packet_value["semantic_questions"]
                ],
                "reviewer_identity": "independent-human-reviewer",
                "schema_version": "h1-source-gold-decision-v5",
                "signature": "human:all-successor-semantics",
                "timestamp": "2026-08-03T00:00:00Z",
            }
            decision_value["decision_sha256"] = sha256_bytes(
                canonical_json_bytes(decision_value)
            )
            decision = temporary / "decision-v5.json"
            decision.write_bytes(canonical_json_bytes(decision_value))
            self.assertTrue(
                h1_cli(
                    [
                        "validate-h1-semantic-review-decision",
                        *successor_h1_args(),
                        "--packet",
                        str(packet),
                        "--markdown",
                        str(markdown),
                        "--readiness",
                        str(readiness),
                        "--decision",
                        str(decision),
                    ]
                )["valid"]
            )

            if check_direct_report_bypass:
                from specchoice_measurement import final_reports  # noqa: PLC0415
                from specchoice_measurement.final_reports import (  # noqa: PLC0415
                    FinalReportError,
                )

                def validate_direct_decision(
                    *, selected_packet: Path = packet,
                    selected_markdown: Path = markdown,
                    selected_readiness: Path = readiness,
                    selected_decision: Path = decision,
                ) -> dict[str, object]:
                    with (
                        patch.object(
                            h1,
                            "_SUCCESSOR_EXECUTABLE_CLOSURE",
                            closure,
                        ),
                        patch.object(
                            h1,
                            "_SUCCESSOR_HISTORICAL_AUTHORITY",
                            active_authority,
                        ),
                        patch.object(
                            h1,
                            "verify_runtime_closure_v3",
                            return_value=closure_value,
                        ) as closure_validator,
                        patch.object(
                            h1,
                            "validate_accepted_v6_active_authority",
                            return_value={
                                "authority_sha256": sha256_bytes(
                                    active_authority.read_bytes()
                                ),
                                "status": "accepted_v6_state_chain_verified",
                            },
                        ) as authority_validator,
                    ):
                        result = h1.validate_h1_semantic_review_decision(
                            **successor_h1_inputs(),
                            packet=selected_packet,
                            markdown=selected_markdown,
                            readiness=selected_readiness,
                            decision=selected_decision,
                        )
                        closure_validator.assert_called_once_with(
                            closure_value,
                            root.parents[1],
                            authority_pre_state_raw=active_authority.read_bytes(),
                        )
                        authority_validator.assert_called_once_with(root.parents[1])
                        return result

                self.assertTrue(validate_direct_decision()["valid"])
                zero_packet_value = deepcopy(packet_value)
                retained_bindings = {
                    "golden_predictions_sha256",
                    "h1_review_schema_sha256",
                    "questions_semantic_content_sha256",
                    "questions_sha256",
                }
                for name in h1._SUCCESSOR_PACKET_BINDING_KEYS - retained_bindings:
                    zero_packet_value["bindings"][name] = "0" * 64
                self.assertEqual(
                    sum(
                        digest == "0" * 64
                        for digest in zero_packet_value["bindings"].values()
                    ),
                    13,
                )
                zero_packet_value["packet_sha256"] = sha256_bytes(
                    canonical_json_bytes(
                        {
                            key: item
                            for key, item in zero_packet_value.items()
                            if key != "packet_sha256"
                        }
                    )
                )
                zero_packet = temporary / "zero-upstream-packet.json"
                zero_packet.write_bytes(canonical_json_bytes(zero_packet_value))
                zero_markdown = temporary / "zero-upstream-review.md"
                zero_markdown.write_text(
                    h1.render_h1_semantic_markdown_v6(zero_packet_value),
                    encoding="utf-8",
                )
                zero_readiness_value = deepcopy(readiness_value)
                zero_readiness_value["bindings"] = {
                    **zero_packet_value["bindings"],
                    "packet_file_sha256": sha256_bytes(zero_packet.read_bytes()),
                }
                zero_readiness_value["readiness_sha256"] = sha256_bytes(
                    canonical_json_bytes(
                        {
                            key: item
                            for key, item in zero_readiness_value.items()
                            if key != "readiness_sha256"
                        }
                    )
                )
                zero_readiness = temporary / "zero-upstream-readiness.json"
                zero_readiness.write_bytes(canonical_json_bytes(zero_readiness_value))
                zero_decision_value = deepcopy(decision_value)
                zero_decision_value["bindings"]["packet_sha256"] = (
                    zero_packet_value["packet_sha256"]
                )
                zero_decision_value["bindings"]["readiness_sha256"] = (
                    zero_readiness_value["readiness_sha256"]
                )
                zero_decision_value["decision_sha256"] = sha256_bytes(
                    canonical_json_bytes(
                        {
                            key: item
                            for key, item in zero_decision_value.items()
                            if key != "decision_sha256"
                        }
                    )
                )
                zero_decision = temporary / "zero-upstream-decision.json"
                zero_decision.write_bytes(canonical_json_bytes(zero_decision_value))
                with self.assertRaisesRegex(
                    H1Error, "H1_SUCCESSOR_PACKET_BINDING_INVALID"
                ):
                    validate_direct_decision(
                        selected_packet=zero_packet,
                        selected_markdown=zero_markdown,
                        selected_readiness=zero_readiness,
                        selected_decision=zero_decision,
                    )

                integrity = temporary / "integrity-v14.json"
                integrity.write_bytes(canonical_json_bytes({}))
                report_inputs = {
                    **successor_h1_inputs(),
                    "packet": zero_packet,
                    "markdown": zero_markdown,
                    "readiness": zero_readiness,
                    "decision": zero_decision,
                }
                repository = root.parents[1]
                def historical(relative: str) -> Path:
                    return repository / resolve_historical_path(repository, relative)

                binding_paths = {
                    "roadmap": historical("." + "planning/ROADMAP.md"),
                    "requirements": historical("." + "planning/REQUIREMENTS.md"),
                    "phase1_predecessor_verification": historical("." + "planning/phases/01-isolated-evidence-boundary-and-source-integrity/01-VERIFICATION.md"),
                    "phase1_predecessor_review": historical("." + "planning/phases/01-isolated-evidence-boundary-and-source-integrity/01-REVIEW.md"),
                    "phase2_predecessor_verification": historical("." + "planning/phases/02-deterministic-measurement-spine/02-VERIFICATION.md"),
                    "phase2_predecessor_review": historical("." + "planning/phases/02-deterministic-measurement-spine/02-REVIEW.md"),
                    "executable_closure": closure,
                    "source_authority": active_authority,
                    "integrity_receipt": integrity,
                    "golden_predictions": golden,
                    "formal_attempt": formal / "attempt.json",
                    "formal_case_outcomes": formal / "case-outcomes.json",
                    "formal_metrics": formal / "metrics.json",
                    "adversarial_report": adversarial,
                    "h1_questions": questions,
                    "h1_schema": h1_schema,
                    "h1_packet": zero_packet,
                    "h1_readiness": zero_readiness,
                    "h1_decision": zero_decision,
                }
                report_bindings = []
                for role in final_reports._FINAL_BINDING_ROLES:
                    path = binding_paths[role]
                    raw = path.read_bytes()
                    report_bindings.append(
                        {
                            "byte_length": len(raw),
                            "path": path.relative_to(repository).as_posix(),
                            "role": role,
                            "sha256": sha256_bytes(raw),
                        }
                    )
                with (
                    patch.object(
                        final_reports,
                        "_canonical_successor_h1_inputs",
                        return_value=report_inputs,
                    ),
                    patch.object(
                        final_reports,
                        "_canonical_final_binding_paths",
                        return_value=binding_paths,
                    ),
                    patch.object(
                        final_reports,
                        "_validate_target_inventory",
                        side_effect=AssertionError("report target opened"),
                    ) as target_guard,
                    patch.object(
                        h1,
                        "_SUCCESSOR_EXECUTABLE_CLOSURE",
                        closure,
                    ),
                    patch.object(
                        h1,
                        "_SUCCESSOR_HISTORICAL_AUTHORITY",
                        active_authority,
                    ),
                    patch.object(
                        h1,
                        "verify_runtime_closure_v3",
                        return_value=closure_value,
                    ),
                    patch.object(
                        h1,
                        "validate_accepted_v6_active_authority",
                        return_value={
                            "authority_sha256": sha256_bytes(
                                active_authority.read_bytes()
                            ),
                            "status": "accepted_v6_state_chain_verified",
                        },
                    ),
                    self.assertRaisesRegex(
                        FinalReportError, "FINAL_REPORT_H1_DECISION_INVALID"
                    ),
                ):
                    final_reports.write_final_successor_reports(
                        repository,
                        audited_commit="a" * 40,
                        bindings=report_bindings,
                        preflight=True,
                    )
                target_guard.assert_not_called()

            forged_adapter = temporary / "forged-adapter.json"
            forged_adapter_value = json.loads(adapter.read_bytes())
            forged_adapter_value.update(diagnostics=[], records=[], valid=False)
            forged_adapter_value["adapter_batch_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_adapter_value.items()
                        if key != "adapter_batch_sha256"
                    }
                )
            )
            forged_adapter.write_bytes(canonical_json_bytes(forged_adapter_value))

            forged_formal = temporary / "forged-formal"
            shutil.copytree(formal, forged_formal)
            forged_manifest = json.loads((forged_formal / "attempt.json").read_bytes())
            forged_manifest["artifacts"] = {}
            forged_manifest["attempt_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_manifest.items()
                        if key != "attempt_sha256"
                    }
                )
            )
            (forged_formal / "attempt.json").write_bytes(
                canonical_json_bytes(forged_manifest)
            )

            forged_adversarial = temporary / "forged-adversarial.json"
            forged_adversarial_value = json.loads(adversarial.read_bytes())
            forged_adversarial_value["cases"] = []
            forged_adversarial_value["report_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_adversarial_value.items()
                        if key != "report_sha256"
                    }
                )
            )
            forged_adversarial.write_bytes(
                canonical_json_bytes(forged_adversarial_value)
            )

            for label, inputs in (
                (
                    "adapter",
                    successor_h1_args(selected_adapter=forged_adapter),
                ),
                (
                    "formal",
                    successor_h1_args(selected_formal=forged_formal),
                ),
                (
                    "adversarial",
                    successor_h1_args(selected_adversarial=forged_adversarial),
                ),
            ):
                with self.subTest(upstream_forgery=label):
                    forged_packet = temporary / f"blocked-{label}/packet.json"
                    h1_cli(
                        [
                            "build-h1-semantic-packet-v6",
                            *inputs,
                            "--output", str(forged_packet),
                            "--markdown", str(forged_packet.with_name("REVIEW.md")),
                            "--preflight",
                        ],
                        expected=2,
                    )
                    h1_cli(
                        [
                            "validate-h1-semantic-review-decision",
                            *inputs,
                            "--packet",
                            str(packet),
                            "--markdown",
                            str(markdown),
                            "--readiness",
                            str(readiness),
                            "--decision",
                            str(decision),
                        ],
                        expected=2,
                    )
                    self.assertFalse(forged_packet.parent.exists())

            empty = temporary / "canonical-empty.json"
            empty.write_bytes(canonical_json_bytes({}))
            closure_packet = temporary / "blocked-governance-closure/packet.json"
            closure_args = build_parser().parse_args(
                [
                    "build-h1-semantic-packet-v6",
                    *successor_h1_args(selected_closure=empty),
                    "--output",
                    str(closure_packet),
                    "--markdown",
                    str(closure_packet.with_name("REVIEW.md")),
                    "--preflight",
                ]
            )
            with (
                patch.object(
                    h1,
                    "validate_accepted_v6_active_authority",
                    return_value={
                        "authority_sha256": sha256_bytes(active_authority.read_bytes()),
                        "status": "accepted_v6_state_chain_verified",
                    },
                ),
                self.assertRaisesRegex(
                    H1Error, "H1_SUCCESSOR_GOVERNANCE_INVALID"
                ),
            ):
                closure_args.handler(closure_args)
            self.assertFalse(closure_packet.parent.exists())

            wrong_ontology = temporary / "wrong-ontology-selection.json"
            wrong_ontology_value = json.loads(
                (
                    root / "reviews/h1-source-gold-ontology-decision-v1.json"
                ).read_bytes()
            )
            wrong_ontology_value["pbmte_policy"]["selection"] = (
                "excluded_from_discovery"
            )
            wrong_ontology_value["decision_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in wrong_ontology_value.items()
                        if key != "decision_sha256"
                    }
                )
            )
            wrong_ontology.write_bytes(canonical_json_bytes(wrong_ontology_value))
            for label, inputs in (
                (
                    "ontology",
                    successor_h1_args(selected_ontology=empty),
                ),
                (
                    "ontology-selection",
                    successor_h1_args(selected_ontology=wrong_ontology),
                ),
                (
                    "source-authority",
                    successor_h1_args(selected_authority=empty),
                ),
            ):
                with self.subTest(governance_forgery=label):
                    forged_packet = temporary / f"blocked-governance-{label}/packet.json"
                    h1_cli(
                        [
                            "build-h1-semantic-packet-v6",
                            *inputs,
                            "--output",
                            str(forged_packet),
                            "--markdown",
                            str(forged_packet.with_name("REVIEW.md")),
                            "--preflight",
                        ],
                        expected=2,
                    )
                    self.assertFalse(forged_packet.parent.exists())

            for label, mutate in (
                ("prompt", lambda value: value["semantic_questions"][0].update(prompt="forged")),
                ("unknown", lambda value: value["semantic_questions"][0].update(unexpected=True)),
            ):
                with self.subTest(packet_forgery=label):
                    forged_packet_value = json.loads(packet.read_bytes())
                    mutate(forged_packet_value)
                    forged_packet_value["packet_sha256"] = sha256_bytes(
                        canonical_json_bytes(
                            {
                                key: item
                                for key, item in forged_packet_value.items()
                                if key != "packet_sha256"
                            }
                        )
                    )
                    forged_packet = temporary / f"packet-{label}.json"
                    forged_packet.write_bytes(canonical_json_bytes(forged_packet_value))
                    h1_cli(
                        [
                            "validate-h1-semantic-packet-v6",
                            *successor_h1_args(),
                            "--packet", str(forged_packet),
                            "--markdown", str(markdown),
                        ],
                        expected=2,
                    )

    def test_successor_governance_validators_fail_closed_on_empty_inputs(self) -> None:
        from specchoice_evidence.runtime_closure import (  # noqa: PLC0415
            RuntimeClosureError,
            verify_runtime_closure_v3,
        )
        from specchoice_evidence.successor import (  # noqa: PLC0415
            SuccessorProtocolError,
            validate_accepted_v6_active_authority,
        )

        repository = self.root.parents[1]
        with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_V3_INVALID"):
            verify_runtime_closure_v3({}, repository, authority_pre_state_raw=b"authority")
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            temporary = Path(directory)
            empty = temporary / "empty.json"
            empty.write_bytes(canonical_json_bytes({}))
            with self.assertRaisesRegex(H1Error, "H1_ONTOLOGY_DECISION_INVALID"):
                h1.validate_h1_ontology_decision_v1(
                    options=self.root
                    / "config/measurement/h1-ontology-policy-options-v1.json",
                    supersession=self.root
                    / "receipts/h1-review-route-supersession-v1.json",
                    decision=empty,
                )
            empty_repository = temporary / "empty-repository"
            empty_repository.mkdir()
            with self.assertRaisesRegex(
                SuccessorProtocolError,
                "ACCEPTED_V6_ACTIVE_AUTHORITY_INPUT_INVALID",
            ):
                validate_accepted_v6_active_authority(empty_repository)

    def test_report_generation_rejects_one_byte_planning_or_predecessor_report_drift_before_write(self) -> None:
        from specchoice_measurement import final_reports  # noqa: PLC0415
        from specchoice_measurement.final_reports import FinalReportError, validate_final_report_inputs  # noqa: PLC0415
        repository = self.root.parents[1]
        source = repository / resolve_historical_path(
            repository, "." + "planning/ROADMAP.md"
        )
        self.assertTrue(source.is_file())
        frozen = sha256_bytes(source.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.txt").write_bytes(b"frozen\n")
            validate_final_report_inputs(root, {"input.txt": sha256_bytes(b"frozen\n")}, {"all": True}, human_disposition="approved")
            (root / "input.txt").write_bytes(b"drifted\n")
            with self.assertRaisesRegex(FinalReportError, "FINAL_REPORT_INPUT_DRIFT"):
                validate_final_report_inputs(root, {"input.txt": sha256_bytes(b"frozen\n")}, {"all": True}, human_disposition="approved")
        self.assertNotEqual(frozen, sha256_bytes(source.read_bytes() + b"\n"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for role in final_reports._FINAL_BINDING_ROLES:
                path = f"inputs/{role}.json" if role in final_reports._CANONICAL_JSON_BINDINGS else f"inputs/{role}.md"
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = canonical_json_bytes({}) if role in final_reports._CANONICAL_JSON_BINDINGS else b"frozen\n"
                target.write_bytes(raw)
                records.append({
                    "byte_length": len(raw),
                    "path": path,
                    "role": role,
                    "sha256": sha256_bytes(raw),
                })
            validated, _ = final_reports._validate_final_binding_set(root, records)
            self.assertEqual(tuple(item["role"] for item in validated), final_reports._FINAL_BINDING_ROLES)
            roadmap = root / str(records[0]["path"])
            roadmap.write_bytes(b"drifted\n")
            with self.assertRaisesRegex(FinalReportError, "FINAL_REPORT_INPUT_DRIFT"):
                final_reports._validate_final_binding_set(root, records)
            roadmap.write_bytes(b"frozen\n")
            for malformed in (
                records[:-1],
                [records[1], records[0], *records[2:]],
                [*records, {**records[-1], "role": "extra"}],
            ):
                with self.assertRaisesRegex(FinalReportError, "FINAL_REPORT_BINDING"):
                    final_reports._validate_final_binding_set(root, malformed)

            for relative in final_reports.FINAL_SUCCESSOR_TARGETS:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
            evidence = {
                "adversarial": {"case_count": 17, "matched": 17, "status": "diagnostic_only"},
                "audited_commit": "a" * 40,
                "bindings": records,
                "decision": {"aggregate_disposition": "approved", "open_semantic_ids": [], "question_count": 7},
                "external_publication_authorized": False,
                "formal": {"case_count": 11, "evidence_span_population": 10, "metrics": {}, "negative_no_surface": {"denominator": 3, "numerator": 3}},
                "schema_version": "final-successor-evidence-v1",
            }
            with patch("specchoice_measurement.final_reports._final_evidence", return_value=evidence):
                for targets in (
                    final_reports.FINAL_SUCCESSOR_TARGETS[:-1],
                    (*final_reports.FINAL_SUCCESSOR_TARGETS, "extra.md"),
                    (
                        final_reports.FINAL_SUCCESSOR_TARGETS[1],
                        final_reports.FINAL_SUCCESSOR_TARGETS[0],
                        *final_reports.FINAL_SUCCESSOR_TARGETS[2:],
                    ),
                ):
                    with self.assertRaisesRegex(FinalReportError, "FINAL_REPORT_TARGET_INVENTORY_INVALID"):
                        final_reports.write_final_successor_reports(
                            root,
                            audited_commit="a" * 40,
                            bindings=records,
                            targets=targets,
                        )
                original_link = final_reports._link_no_replace
                last = root / final_reports.FINAL_SUCCESSOR_TARGETS[-1]

                def collide_on_last(staged: Path, target: Path) -> None:
                    if target == last:
                        target.write_bytes(b"racer\n")
                    original_link(staged, target)

                with patch("specchoice_measurement.final_reports._link_no_replace", side_effect=collide_on_last):
                    with self.assertRaisesRegex(FinalReportError, "FINAL_REPORT_ATOMIC_PUBLISH_FAILED"):
                        final_reports.write_final_successor_reports(
                            root,
                            audited_commit="a" * 40,
                            bindings=records,
                            targets=final_reports.FINAL_SUCCESSOR_TARGETS,
                        )
                self.assertTrue(all(
                    not (root / relative).exists()
                    for relative in final_reports.FINAL_SUCCESSOR_TARGETS[:-1]
                ))
                self.assertEqual(last.read_bytes(), b"racer\n")

    def _legacy_context(self, directory: Path) -> dict[str, Path | None]:
        source_root = directory / "pre-cutover"
        authority = source_root / "phase2/source-authority.json"
        authority.parent.mkdir(parents=True, exist_ok=True)
        if not authority.exists():
            shutil.copy2(self.root / "phase2/source-authority-v9-historical.json", authority)
        return {
            "authority": authority,
            "bundle": self.bundle,
            "rules": self.rules,
            "predictions": self.predictions,
            "oracle": self.oracle,
            "pending_authority": None,
            "transition": None,
            "revocation": None,
        }

    def _active_context(self) -> dict[str, Path | None]:
        return {
            # These v2/v3 fixtures are historical after the accepted-v6
            # cutover; replay them against the preserved pre-cutover authority.
            "authority": self.root / "phase2/source-authority-v13-historical.json",
            "bundle": self.active_bundle,
            "rules": self.rules,
            "predictions": self.root / "fixtures/measurement/golden-predictions-v2.json",
            "oracle": self.root / "fixtures/measurement/adversarial/required-diagnostics-v2.json",
            "pending_authority": None,
            "transition": None,
            "revocation": self.root / "receipts/fixture-closure-revocation-v2.json",
        }

    def _active_evidence(self, directory: Path) -> tuple[Path, Path]:
        from specchoice_measurement.cli import (  # noqa: PLC0415
            command_run_adversarial_oracles,
            command_run_formal_measurement,
        )

        formal = directory / "formal-golden-pr2164-v2"
        report = directory / "adversarial-oracle-results-v3.json"
        if not formal.exists():
            context = self._active_context()
            formal_args = SimpleNamespace(
                authority=context["authority"], bundle=context["bundle"], rules=context["rules"],
                schema=self.root / "config/measurement/canonical-adjudication-schema-v1.json",
                predictions=context["predictions"], pending_authority=None, transition=None,
                revocation=context["revocation"], attempt_root=directory, attempt_id=formal.name,
            )
            self.assertEqual(command_run_formal_measurement(formal_args), 0)
            self.assertEqual(command_run_adversarial_oracles(SimpleNamespace(
                authority=context["authority"], bundle=context["bundle"], rules=context["rules"],
                schema=formal_args.schema, predictions=context["predictions"], oracle=context["oracle"],
                pending_authority=None, transition=None, revocation=context["revocation"],
                formal_attempt=formal, report=report,
            )), 0)
        return formal, report

    def _build(self, directory: Path) -> tuple[Path, Path, dict[str, object]]:
        formal, adversarial = self._active_evidence(directory)
        packet_path = directory / "packet" / "packet.json"
        markdown_path = directory / "packet" / "packet.md"
        packet = h1.build_h1_packet(
            formal_attempt=formal,
            adversarial_report=adversarial,
            output_json=packet_path,
            output_markdown=markdown_path,
            schema=self.schema,
            **self._active_context(),
        )
        return packet_path, markdown_path, packet

    def _readiness(self, directory: Path, packet: Path, markdown: Path) -> Path:
        summary = directory / "02-16-SUMMARY-fixture.md"
        summary.write_text("# disposable normalized projection\n", encoding="utf-8")
        readiness = directory / "h1-review-readiness-v3.json"
        h1.write_h1_readiness_v3(
            output=readiness,
            formal_attempt=self._active_evidence(directory)[0],
            adversarial_result=self._active_evidence(directory)[1],
            packet=packet,
            markdown=markdown,
            schema=self.schema,
            source_authority=self._active_context()["authority"],
            canonical_revocation=self._active_context()["revocation"],
            bundle=self.active_bundle,
            rules=self.rules,
            predictions=self._active_context()["predictions"],
            oracle=self._active_context()["oracle"],
            offline_replay=self.replay,
            phase_gate=self.cutover.read_bytes(),
            plan_summary=summary,
        )
        return readiness

    @staticmethod
    def _decision(packet: dict[str, object], readiness: dict[str, object], *, disposition: str = "approved") -> dict[str, object]:
        reviews = []
        for review in packet["fixture_reviews"]:
            assert isinstance(review, dict)
            semantics = {key: value for key, value in review.items() if key != "signature_slot"}
            reviews.append({
                "disposition": "approved",
                "fixture_id": review["fixture_id"],
                "reviewed_semantics_sha256": sha256_bytes(canonical_json_bytes(semantics)),
                "reviewer": "independent-human-reviewer",
                "signature": f"signed:{review['fixture_id']}",
            })
        decision: dict[str, object] = {
            "aggregate_disposition": disposition,
            "bindings": {
                "packet_sha256": packet["packet_sha256"],
                "phase_gate_sha256": readiness["bindings"]["phase_gate_sha256"],
                "readiness_sha256": readiness["readiness_sha256"],
                "schema_sha256": readiness["bindings"]["schema_sha256"],
            },
            "external_publication_authorized": False,
            "fixture_reviews": reviews,
            "reviewer": "independent-human-reviewer",
            "rationale": "independent review completed",
            "semantic_responses": {
                identifier: {"disposition": "approved", "response": "reviewed"}
                for identifier in H1PacketTests.semantic_ids
            },
            "timestamp": "2026-08-02T00:00:00Z",
            "schema_version": "h1-source-gold-decision-v2",
        }
        decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
        return decision

    def test_packet_is_complete_clean_and_markdown_is_a_pure_projection(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            packet_path, markdown_path, packet = self._build(Path(directory))
            validated = h1.validate_h1_packet(
                packet=packet_path, markdown=markdown_path, schema=self.schema,
                formal_attempt=self._active_evidence(Path(directory))[0],
                adversarial_report=self._active_evidence(Path(directory))[1], **self._active_context(),
            )
            self.assertEqual(validated, packet)
            self.assertEqual(len(packet["fixture_reviews"]), 11)
            self.assertFalse(packet["external_publication_authorized"])
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), h1.render_h1_markdown(packet))

    def test_any_packet_binding_or_markdown_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet_path, markdown_path, packet = self._build(root)
            changed = deepcopy(packet)
            assert isinstance(changed["bindings"], dict)
            changed["bindings"]["golden_predictions_sha256"] = "0" * 64
            changed["packet_sha256"] = sha256_bytes(canonical_json_bytes({key: value for key, value in changed.items() if key != "packet_sha256"}))
            packet_path.write_bytes(canonical_json_bytes(changed))
            with self.assertRaisesRegex(H1Error, "H1_BINDINGS_INVALID"):
                h1.validate_h1_packet(
                    packet=packet_path, markdown=markdown_path, schema=self.schema,
                    formal_attempt=self._active_evidence(root)[0], adversarial_report=self._active_evidence(root)[1],
                    **self._active_context(),
                )
            packet_path.write_bytes(canonical_json_bytes(packet))
            markdown_path.write_text("not a projection\n", encoding="utf-8")
            with self.assertRaisesRegex(H1Error, "H1_MARKDOWN_INVALID"):
                h1.validate_h1_packet(
                    packet=packet_path, markdown=markdown_path, schema=self.schema,
                    formal_attempt=self._active_evidence(root)[0], adversarial_report=self._active_evidence(root)[1],
                    **self._active_context(),
                )

    def test_readiness_is_one_time_and_validator_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet, markdown, _ = self._build(root)
            readiness = self._readiness(root, packet, markdown)
            before = readiness.read_bytes()
            phase_gate = self.cutover.read_bytes()
            self.assertEqual(
                h1.validate_h1_readiness_v3(
                    readiness=readiness, formal_attempt=self._active_evidence(root)[0], adversarial_result=self._active_evidence(root)[1],
                    packet=packet, markdown=markdown, schema=self.schema, source_authority=self._active_context()["authority"],
                    canonical_revocation=self._active_context()["revocation"], offline_replay=self.replay, phase_gate=phase_gate,
                    plan_summary=root / "02-16-SUMMARY-fixture.md", bundle=self.active_bundle, rules=self.rules,
                    predictions=self._active_context()["predictions"], oracle=self._active_context()["oracle"],
                )["readiness_sha256"],
                json.loads(before)["readiness_sha256"],
            )
            self.assertEqual(readiness.read_bytes(), before)
            with self.assertRaisesRegex(H1Error, "H1_READINESS_EXISTS"):
                self._readiness(root, packet, markdown)

    def test_v2_decision_validator_checks_closed_human_contract_without_authoring(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet_path, markdown_path, packet = self._build(root)
            readiness_path = self._readiness(root, packet_path, markdown_path)
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            decision = self._decision(packet, readiness)
            decision_path = root / "decision.json"
            decision_path.write_bytes(canonical_json_bytes(decision))
            receipt = h1.validate_h1_decision_v2(
                schema=self.schema, packet=packet_path, readiness=readiness_path, decision=decision_path
            )
            self.assertEqual(receipt["fixture_count"], 11)
            self.assertEqual(receipt["aggregate_disposition"], "approved")
            self.assertFalse(receipt["external_publication_authorized"])

            for binding in ("packet_sha256", "schema_sha256"):
                with self.subTest(binding=binding):
                    detached_readiness = deepcopy(readiness)
                    assert isinstance(detached_readiness["bindings"], dict)
                    detached_readiness["bindings"][binding] = "0" * 64
                    detached_readiness["readiness_sha256"] = sha256_bytes(canonical_json_bytes({
                        key: value for key, value in detached_readiness.items() if key != "readiness_sha256"
                    }))
                    detached_decision = deepcopy(decision)
                    assert isinstance(detached_decision["bindings"], dict)
                    detached_decision["bindings"]["readiness_sha256"] = detached_readiness["readiness_sha256"]
                    detached_decision["decision_sha256"] = sha256_bytes(canonical_json_bytes({
                        key: value for key, value in detached_decision.items() if key != "decision_sha256"
                    }))
                    readiness_path.write_bytes(canonical_json_bytes(detached_readiness))
                    decision_path.write_bytes(canonical_json_bytes(detached_decision))
                    with self.assertRaisesRegex(H1Error, "H1_READINESS_BINDINGS_INVALID"):
                        h1.validate_h1_decision_v2(
                            schema=self.schema, packet=packet_path, readiness=readiness_path, decision=decision_path
                        )

            questions_path = self.root / "config/measurement/h1-semantic-review-questions-v2.json"
            schema_v4 = self.root / "config/measurement/h1-review-schema-v4.json"
            questions = json.loads(questions_path.read_text(encoding="utf-8"))
            golden = json.loads((self.root / "fixtures/measurement/golden-predictions-v4.json").read_text(encoding="utf-8"))
            schema_result = h1.validate_h1_review_schema_v4(
                schema=schema_v4, questions=questions_path
            )
            successor_bindings = {
                key: "0" * 64 for key in h1._SUCCESSOR_PACKET_BINDING_KEYS
            }
            successor_bindings.update(
                {
                    "h1_review_schema_sha256": schema_result["schema_sha256"],
                    "golden_predictions_sha256": sha256_bytes(
                        (self.root / "fixtures/measurement/golden-predictions-v4.json").read_bytes()
                    ),
                    "questions_semantic_content_sha256": schema_result[
                        "canonical_semantic_content_sha256"
                    ],
                    "questions_sha256": schema_result["questions_sha256"],
                }
            )
            successor_packet: dict[str, object] = {
                "bindings": successor_bindings,
                "external_publication_authorized": False,
                "fixture_reviews": h1._successor_fixture_reviews(golden),
                "schema_version": "h1-source-gold-review-v6",
                "semantic_questions": questions["questions"],
            }
            successor_packet["packet_sha256"] = sha256_bytes(canonical_json_bytes(successor_packet))
            successor_packet_path = root / "successor-packet.json"
            successor_packet_path.write_bytes(canonical_json_bytes(successor_packet))
            successor_readiness: dict[str, object] = {
                "bindings": {
                    **successor_bindings,
                    "packet_file_sha256": sha256_bytes(successor_packet_path.read_bytes()),
                },
                "external_publication_authorized": False,
                "schema_version": "h1-semantic-readiness-v6",
            }
            successor_readiness["readiness_sha256"] = sha256_bytes(canonical_json_bytes(successor_readiness))
            successor_readiness_path = root / "successor-readiness.json"
            successor_readiness_path.write_bytes(canonical_json_bytes(successor_readiness))
            successor_decision: dict[str, object] = {
                "aggregate_disposition": "approved",
                "bindings": {
                    "packet_sha256": successor_packet["packet_sha256"],
                    "questions_sha256": schema_result["questions_sha256"],
                    "readiness_sha256": successor_readiness["readiness_sha256"],
                    "schema_sha256": schema_result["schema_sha256"],
                },
                "external_publication_authorized": False,
                "fixture_reviews": [
                    {
                        "disposition": "approved",
                        "fixture_id": review["fixture_id"],
                        "rationale": "I reviewed this fixture's frozen semantics.",
                        "reviewed_semantics_sha256": review["reviewed_semantics_sha256"],
                        "signature": f"human:{review['fixture_id']}",
                    }
                    for review in successor_packet["fixture_reviews"]
                ],
                "rationale": "I reviewed all fixture and question semantics.",
                "responses": [
                    {
                        "disposition": "approved",
                        "fixture_signoffs": [
                            {"disposition": "approved", "fixture_id": fixture_id, "signature": f"human:{question['id']}:{fixture_id}"}
                            for fixture_id in question["fixture_ids"]
                        ],
                        "question_id": question["id"],
                        "rationale": "The expected semantics and machine assertions are correct.",
                        "response": "approve_expected_semantics",
                    }
                    for question in successor_packet["semantic_questions"]
                ],
                "reviewer_identity": "independent-human-reviewer",
                "schema_version": "h1-source-gold-decision-v5",
                "signature": "human:all-seven-questions",
                "timestamp": "2026-08-03T00:00:00Z",
            }
            successor_decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(successor_decision))
            successor_decision_path = root / "successor-decision.json"
            successor_decision_path.write_bytes(canonical_json_bytes(successor_decision))

            def validate_successor_decision(
                *, selected_schema: Path = schema_v4,
            ) -> dict[str, object]:
                validated_readiness = json.loads(successor_readiness_path.read_bytes())
                with patch.object(
                    h1,
                    "validate_h1_semantic_readiness_v6",
                    return_value=validated_readiness,
                ):
                    return h1.validate_h1_semantic_review_decision(
                        adapter_batch=root / "validated-adapter.json",
                        adversarial_report=root / "validated-adversarial.json",
                        adversarial_contract=root / "validated-adversarial-contract.json",
                        adjudication_schema=root / "validated-adjudication-schema.json",
                        executable_closure=root / "validated-closure.json",
                        fixture_registry=root / "validated-registry.json",
                        formal_attempt=root / "validated-formal",
                        golden_predictions=self.root
                        / "fixtures/measurement/golden-predictions-v4.json",
                        ontology_decision=root / "validated-ontology.json",
                        ontology_options=root / "validated-ontology-options.json",
                        ontology_supersession=root
                        / "validated-ontology-supersession.json",
                        questions=questions_path,
                        rules=root / "validated-rules.json",
                        semantic_contract=root / "validated-semantic-contract.json",
                        schema=selected_schema,
                        source_authority=root / "validated-authority.json",
                        bundle_root=root / "validated-bundle",
                        packet=successor_packet_path,
                        markdown=root / "validated-review.md",
                        readiness=successor_readiness_path,
                        decision=successor_decision_path,
                    )

            self.assertEqual(
                validate_successor_decision()["questions"],
                7,
            )
            for label, mutate in (
                (
                    "prompt",
                    lambda packet: packet["semantic_questions"][0].update(
                        prompt="Forged prompt with a recomputed packet digest."
                    ),
                ),
                (
                    "unknown-nested-key",
                    lambda packet: packet["semantic_questions"][0].update(
                        unexpected="forged"
                    ),
                ),
            ):
                with self.subTest(packet_forgery=label):
                    forged_packet = deepcopy(successor_packet)
                    mutate(forged_packet)
                    forged_packet["packet_sha256"] = sha256_bytes(
                        canonical_json_bytes(
                            {
                                key: item
                                for key, item in forged_packet.items()
                                if key != "packet_sha256"
                            }
                        )
                    )
                    successor_packet_path.write_bytes(
                        canonical_json_bytes(forged_packet)
                    )
                    forged_readiness = deepcopy(successor_readiness)
                    forged_readiness["bindings"]["packet_file_sha256"] = sha256_bytes(
                        successor_packet_path.read_bytes()
                    )
                    forged_readiness["readiness_sha256"] = sha256_bytes(
                        canonical_json_bytes(
                            {
                                key: item
                                for key, item in forged_readiness.items()
                                if key != "readiness_sha256"
                            }
                        )
                    )
                    successor_readiness_path.write_bytes(
                        canonical_json_bytes(forged_readiness)
                    )
                    forged_decision = deepcopy(successor_decision)
                    forged_decision["bindings"]["packet_sha256"] = forged_packet[
                        "packet_sha256"
                    ]
                    forged_decision["bindings"]["readiness_sha256"] = (
                        forged_readiness["readiness_sha256"]
                    )
                    forged_decision["decision_sha256"] = sha256_bytes(
                        canonical_json_bytes(
                            {
                                key: item
                                for key, item in forged_decision.items()
                                if key != "decision_sha256"
                            }
                        )
                    )
                    successor_decision_path.write_bytes(
                        canonical_json_bytes(forged_decision)
                    )
                    with self.assertRaisesRegex(
                        H1Error,
                        "H1_SUCCESSOR_PACKET_(QUESTIONS_)?INVALID",
                    ):
                        validate_successor_decision()
            forged_review_packet = deepcopy(successor_packet)
            forged_review = forged_review_packet["fixture_reviews"][0]
            forged_review["reviewed_semantics"]["rationale"] += " forged"
            forged_review["reviewed_semantics_sha256"] = sha256_bytes(
                canonical_json_bytes(forged_review["reviewed_semantics"])
            )
            forged_review_packet["packet_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_review_packet.items()
                        if key != "packet_sha256"
                    }
                )
            )
            successor_packet_path.write_bytes(canonical_json_bytes(forged_review_packet))
            forged_review_readiness = deepcopy(successor_readiness)
            forged_review_readiness["bindings"]["packet_file_sha256"] = sha256_bytes(
                successor_packet_path.read_bytes()
            )
            forged_review_readiness["readiness_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_review_readiness.items()
                        if key != "readiness_sha256"
                    }
                )
            )
            successor_readiness_path.write_bytes(
                canonical_json_bytes(forged_review_readiness)
            )
            forged_review_decision = deepcopy(successor_decision)
            forged_review_decision["fixture_reviews"][0][
                "reviewed_semantics_sha256"
            ] = forged_review["reviewed_semantics_sha256"]
            forged_review_decision["bindings"]["packet_sha256"] = (
                forged_review_packet["packet_sha256"]
            )
            forged_review_decision["bindings"]["readiness_sha256"] = (
                forged_review_readiness["readiness_sha256"]
            )
            forged_review_decision["decision_sha256"] = sha256_bytes(
                canonical_json_bytes(
                    {
                        key: item
                        for key, item in forged_review_decision.items()
                        if key != "decision_sha256"
                    }
                )
            )
            successor_decision_path.write_bytes(
                canonical_json_bytes(forged_review_decision)
            )
            with self.assertRaisesRegex(H1Error, "H1_SUCCESSOR_PACKET_INVALID"):
                validate_successor_decision()
            successor_packet_path.write_bytes(canonical_json_bytes(successor_packet))
            successor_readiness_path.write_bytes(
                canonical_json_bytes(successor_readiness)
            )
            placeholder = deepcopy(successor_decision)
            placeholder["responses"][0]["response"] = "reviewed"
            placeholder["decision_sha256"] = sha256_bytes(canonical_json_bytes({
                key: item for key, item in placeholder.items() if key != "decision_sha256"
            }))
            successor_decision_path.write_bytes(canonical_json_bytes(placeholder))
            with self.assertRaisesRegex(H1Error, "H1_SEMANTIC_RESPONSES_INVALID"):
                validate_successor_decision()
            inconsistent = deepcopy(successor_decision)
            inconsistent["responses"][0]["response"] = "reject_expected_semantics"
            inconsistent["responses"][0]["disposition"] = "disputed"
            for signoff in inconsistent["responses"][0]["fixture_signoffs"]:
                signoff["disposition"] = "disputed"
            inconsistent["decision_sha256"] = sha256_bytes(canonical_json_bytes({
                key: item for key, item in inconsistent.items() if key != "decision_sha256"
            }))
            successor_decision_path.write_bytes(canonical_json_bytes(inconsistent))
            with self.assertRaisesRegex(H1Error, "H1_DISPUTE_AGGREGATION_INVALID"):
                validate_successor_decision()
            with self.assertRaisesRegex(H1Error, "H1_REVIEW_SCHEMA_V4_INVALID"):
                validate_successor_decision(
                    selected_schema=self.root
                    / "config/measurement/h1-review-schema-v3.json"
                )

    def test_incomplete_or_disputed_leaf_must_match_aggregate(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet_path, markdown_path, packet = self._build(root)
            readiness_path = self._readiness(root, packet_path, markdown_path)
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            decision = self._decision(packet, readiness)
            assert isinstance(decision["fixture_reviews"], list)
            assert isinstance(decision["fixture_reviews"][0], dict)
            decision["fixture_reviews"][0]["disposition"] = "disputed"
            decision["decision_sha256"] = sha256_bytes(canonical_json_bytes({key: value for key, value in decision.items() if key != "decision_sha256"}))
            decision_path = root / "decision.json"
            decision_path.write_bytes(canonical_json_bytes(decision))
            with self.assertRaisesRegex(H1Error, "H1_DISPUTE_AGGREGATION_INVALID"):
                h1.validate_h1_decision_v2(schema=self.schema, packet=packet_path, readiness=readiness_path, decision=decision_path)

    def test_public_h1_validators_cover_packet_markdown_readiness_decision_schema_and_retained_roles(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet_path, markdown_path, packet = self._build(root)
            readiness_path = self._readiness(root, packet_path, markdown_path)
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            decision_path = root / "decision.json"
            decision_path.write_bytes(canonical_json_bytes(self._decision(packet, readiness)))
            self.assertEqual(
                h1.validate_h1_decision_v2(schema=self.schema, packet=packet_path, readiness=readiness_path, decision=decision_path)["valid"],
                True,
            )
            for path in (packet_path, markdown_path, readiness_path, decision_path, self.schema, self.formal / "attempt.json", self.adversarial):
                self.assertTrue(path.is_file(), path)

    def test_public_h1_reuses_validated_attempt_and_adversarial_objects_without_reopen(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            packet_path, markdown_path, packet = self._build(root)
            self.assertEqual(
                h1.validate_h1_packet(
                    packet=packet_path, markdown=markdown_path, schema=self.schema,
                    formal_attempt=self._active_evidence(root)[0], adversarial_report=self._active_evidence(root)[1],
                    **self._active_context(),
                )["bindings"],
                packet["bindings"],
            )
            legacy = h1.build_h1_packet(
                formal_attempt=self.formal,
                adversarial_report=self.adversarial,
                output_json=root / "legacy" / "packet.json",
                output_markdown=root / "legacy" / "packet.md",
                schema=self.schema,
                **self._legacy_context(root),
            )
            self.assertEqual(legacy["bindings"]["formal_attempt_sha256"], json.loads(
                (self.formal / "attempt.json").read_text(encoding="utf-8")
            )["attempt_sha256"])


    def _copy_fresh_v7_repository(
        self, repository: Path
    ) -> tuple[Path, dict[str, object]]:
        experiment = repository / "experiments/specchoice-v1.3.2"
        for relative in (
            "phase2/source-authority.json",
            "config/fixture-registry-pr2164-v6.json",
            "config/measurement/pr2164-semantic-gold-contract-v2.json",
            "config/measurement/pr2164-adapter-rules-v3.json",
            "config/measurement/pr2164-adapter-rules-v4.json",
            "config/measurement/canonical-adjudication-schema-v3.json",
            "config/measurement/h1-review-schema-v5.json",
            "config/measurement/h1-semantic-review-questions-v2.json",
            "fixtures/measurement/golden-predictions-v4.json",
            "fixtures/measurement/adversarial/required-diagnostics-v4.json",
        ):
            target = experiment / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / relative, target)
        shutil.copytree(
            self.root / (
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
            "future_targets": [
                {
                    "kind": "file",
                    "path": (
                        "experiments/specchoice-v1.3.2/reports/h1/"
                        "adapter-batch-pr2164-v6.json"
                    ),
                }
            ],
            "schema_version": "runtime-executable-closure-v4",
        }
        receipt = experiment / "receipts/runtime-executable-closure-v4.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_bytes(canonical_json_bytes(closure))
        return experiment, closure

    def test_h1_v7_real_fresh_chain_rejects_each_canonical_forgery(self) -> None:
        from specchoice_measurement.adapter import (  # noqa: PLC0415
            write_pr2164_accepted_v6_adapter_batch_v4,
        )
        from specchoice_measurement.attempts import (  # noqa: PLC0415
            run_fresh_adversarial_suite_v7,
            run_fresh_formal_measurement_v6,
        )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment, closure = self._copy_fresh_v7_repository(repository)
            authority = experiment / "phase2/source-authority.json"
            patches = (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(h1, "load_runtime_closure_v4", return_value=closure),
                mock.patch(
                    "specchoice_measurement.adapter.load_runtime_closure_v4",
                    return_value=closure,
                ),
                mock.patch(
                    "specchoice_measurement.attempts.load_runtime_closure_v4",
                    return_value=closure,
                ),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                write_pr2164_accepted_v6_adapter_batch_v4(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                run_fresh_formal_measurement_v6(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                run_fresh_adversarial_suite_v7(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                records, values, _ = h1._v7_source_snapshot(
                    runtime_closure=closure,
                    authority_path=authority,
                )
                packet = h1.build_h1_review_packet_v7(
                    questions=values["question_contract"]["questions"],
                    fixture_reviews=h1._expected_v7_fixture_reviews(
                        values["formal_case_outcomes"], records
                    ),
                    source_identity=records,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                self.assertEqual(len(packet["fixture_reviews"]), 11)
                self.assertEqual(len(packet["questions"]), 7)

                targets = {
                    "adapter": experiment / "reports/h1/adapter-batch-pr2164-v6.json",
                    "attempt": experiment
                    / "runs/measurement-attempts/formal-golden-pr2164-v6/attempt.json",
                    "metrics": experiment
                    / "runs/measurement-attempts/formal-golden-pr2164-v6/metrics.json",
                    "case_outcomes": experiment
                    / "runs/measurement-attempts/formal-golden-pr2164-v6/case-outcomes.json",
                    "adversarial": experiment
                    / "reports/h1/adversarial-oracle-results-v7.json",
                }
                for role, target in targets.items():
                    with self.subTest(role=role):
                        original = target.read_bytes()
                        forged = json.loads(original)
                        if isinstance(forged, dict):
                            forged["forged"] = True
                        else:
                            self.assertIsInstance(forged, list)
                            forged[0] = {**forged[0], "forged": True}
                        target.write_bytes(canonical_json_bytes(forged))
                        try:
                            with self.assertRaisesRegex(
                                H1Error, "H1_V7_FRESH_CHAIN_INVALID"
                            ):
                                h1._v7_source_snapshot(
                                    runtime_closure=closure,
                                    authority_path=authority,
                                )
                        finally:
                            target.write_bytes(original)

    def _v7_packet(self) -> tuple[dict[str, object], dict[str, object]]:
        """Build an isolated packet projection; real fresh-chain coverage is above."""
        root = Path(__file__).parents[1]
        closure = {"schema_version": "runtime-executable-closure-v4"}
        question_contract = json.loads(
            (root / "config/measurement/h1-semantic-review-questions-v2.json").read_text(encoding="utf-8")
        )
        cases = json.loads(
            (root / "runs/measurement-attempts/formal-golden-pr2164-v5/case-outcomes.json").read_text(encoding="utf-8")
        )
        raws = {
            key: canonical_json_bytes(
                question_contract if key == "question_contract"
                else cases if key == "formal_case_outcomes"
                else {"role": key}
            )
            for key in h1._V7_SOURCE_IDENTITY_KEYS
        }
        source_identity = {
            key: {
                "path": h1._V7_SOURCE_IDENTITY_PATHS[key],
                "byte_length": len(raws[key]),
                "sha256": sha256_bytes(raws[key]),
            }
            for key in h1._V7_SOURCE_IDENTITY_KEYS
        }
        values = {
            key: question_contract if key == "question_contract"
            else cases if key == "formal_case_outcomes"
            else {"role": key}
            for key in h1._V7_SOURCE_IDENTITY_KEYS
        }
        snapshot = (source_identity, values, raws)
        self._last_v7_snapshot = snapshot
        fixture_reviews = h1._expected_v7_fixture_reviews(cases, source_identity)
        with mock.patch.object(h1, "_v7_source_snapshot", return_value=snapshot):
            packet = h1.build_h1_review_packet_v7(
                questions=question_contract["questions"], fixture_reviews=fixture_reviews, source_identity=source_identity,
                runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
            )
        return packet, closure

    @staticmethod
    def _v7_human_decision(
        packet: dict[str, object], readiness: dict[str, object],
        *, disposition: str = "incomplete",
    ) -> dict[str, object]:
        decision: dict[str, object] = {
            "aggregate_disposition": disposition,
            "aggregate_rationale": f"human judgment {disposition}",
            "attestation": "personally reviewed",
            "fixture_reviews": [
                {
                    "fixture_id": item["fixture_id"],
                    "disposition": disposition,
                    "rationale": "human judgment",
                }
                for item in packet["fixture_reviews"]
            ],
            "packet_sha256": packet["packet_sha256"],
            "readiness_sha256": readiness["readiness_sha256"],
            "reviewer": "reviewer",
            "schema_version": "h1-source-gold-decision-v6",
            "semantic_responses": [
                {
                    "id": item,
                    "disposition": disposition,
                    "rationale": "human judgment",
                }
                for item in h1._V7_H1_QUESTION_IDS
            ],
            "signature": "signature",
            "timestamp_utc": "2026-08-03T00:00:00Z",
        }
        decision["decision_sha256"] = sha256_bytes(
            canonical_json_bytes(decision)
        )
        return decision

    def test_h1_v7_binds_complete_seven_question_semantics_and_v4_identity(self) -> None:
        packet, closure = self._v7_packet()
        self.assertEqual([item["id"] for item in packet["questions"]], list(h1._V7_H1_QUESTION_IDS))
        self.assertEqual(packet["schema_version"], "h1-review-packet-v7")
        self.assertEqual(len(packet["fixture_reviews"]), 11)
        self.assertTrue(all(question["evidence"] for question in packet["questions"]))
        self.assertTrue(all(
            {"source_path", "source_sha256", "start_byte", "end_byte", "text"} <= set(span)
            for question in packet["questions"] for span in question["evidence"]
        ))
        forged = deepcopy(packet["source_identity"])
        forged["adapter"]["sha256"] = "0" * 64
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            self.assertRaisesRegex(H1Error, "H1_V7_SOURCE_IDENTITY_INVALID"),
        ):
            h1.build_h1_review_packet_v7(
                questions=packet["questions"], fixture_reviews=packet["fixture_reviews"],
                source_identity=forged, runtime_closure=closure,
                authority_path=Path(__file__).parents[1] / "phase2/source-authority.json",
            )

    def test_h1_v7_packet_and_readiness_contain_no_human_values(self) -> None:
        packet, closure = self._v7_packet()
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(packet=packet, runtime_closure=closure, authority_path=Path(__file__).parents[1] / "phase2/source-authority.json")
        self.assertNotIn("responses", packet)
        self.assertNotIn("responses", readiness)
        self.assertEqual(readiness["source_identity"], packet["source_identity"])
        self.assertEqual(readiness["markdown"], packet["markdown"])
        tampered = deepcopy(packet)
        tampered["questions"][0]["prompt"] += " tampered"
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            self.assertRaises(H1Error),
        ):
            h1.build_h1_review_readiness_v7(
                packet=tampered, runtime_closure=closure,
                authority_path=Path(__file__).parents[1] / "phase2/source-authority.json",
            )

    def test_h1_v6_decision_distinguishes_missing_payload_from_complete_incomplete_judgment(self) -> None:
        packet, closure = self._v7_packet()
        root = Path(__file__).parents[1]
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(packet=packet, runtime_closure=closure, authority_path=root / "phase2/source-authority.json")
            with self.assertRaisesRegex(H1Error, "H1_V6_DECISION_INCOMPLETE"):
                h1.validate_h1_source_gold_decision_v6(decision={}, packet=packet, readiness=readiness, runtime_closure=closure, authority_path=root / "phase2/source-authority.json")
            decision = {
                "aggregate_disposition": "incomplete", "aggregate_rationale": "human judgment remains incomplete",
                "attestation": "personally reviewed", "fixture_reviews": [{"fixture_id": item["fixture_id"], "disposition": "incomplete", "rationale": "human judgment"} for item in packet["fixture_reviews"]],
                "packet_sha256": packet["packet_sha256"], "readiness_sha256": readiness["readiness_sha256"], "reviewer": "reviewer",
                "schema_version": "h1-source-gold-decision-v6", "semantic_responses": [{"id": item, "disposition": "incomplete", "rationale": "human judgment"} for item in h1._V7_H1_QUESTION_IDS],
                "signature": "signature", "timestamp_utc": "2026-08-03T00:00:00Z",
            }
            decision["decision_sha256"] = sha256_bytes(canonical_json_bytes({key: decision[key] for key in sorted(decision)}))
            self.assertEqual(h1.validate_h1_source_gold_decision_v6(decision=decision, packet=packet, readiness=readiness, runtime_closure=closure, authority_path=root / "phase2/source-authority.json"), decision)
            with tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                output = repository / h1._V7_DECISION_PATH
                output.parent.mkdir(parents=True)
                with mock.patch.object(h1, "_REPOSITORY", repository):
                    result = h1.write_h1_source_gold_decision_v6(
                        output=output, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
                    )
                    self.assertEqual(result["aggregate_disposition"], "incomplete")
                    self.assertEqual(output.read_bytes(), canonical_json_bytes(decision))
                    self.assertEqual(
                        h1.write_h1_source_gold_decision_v6(
                            output=output, decision=decision, packet=packet, readiness=readiness,
                            runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
                        )["status"],
                        "resumed",
                    )
                    invalid = deepcopy(decision)
                    invalid["timestamp_utc"] = "2026-08-03T02:00:00+02:00"
                    invalid["decision_sha256"] = sha256_bytes(canonical_json_bytes({
                        key: value for key, value in invalid.items() if key != "decision_sha256"
                    }))
                    output.unlink()
                    with self.assertRaisesRegex(H1Error, "H1_V6_DECISION_INCOMPLETE"):
                        h1.write_h1_source_gold_decision_v6(
                            output=output, decision=invalid, packet=packet, readiness=readiness,
                            runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
                        )
                    self.assertFalse(output.exists())

    def test_h1_v6_terminal_outputs_require_approved_decision(self) -> None:
        packet, closure = self._v7_packet()
        root = Path(__file__).parents[1]
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(packet=packet, runtime_closure=closure, authority_path=root / "phase2/source-authority.json")
            for disposition in ("approved", "disputed", "incomplete"):
                decision = {
                    "aggregate_disposition": disposition, "aggregate_rationale": f"human judgment {disposition}", "attestation": "personally reviewed",
                    "fixture_reviews": [{"fixture_id": item["fixture_id"], "disposition": disposition, "rationale": "human judgment"} for item in packet["fixture_reviews"]],
                    "packet_sha256": packet["packet_sha256"], "readiness_sha256": readiness["readiness_sha256"], "reviewer": "reviewer",
                    "schema_version": "h1-source-gold-decision-v6", "semantic_responses": [{"id": item, "disposition": disposition, "rationale": "human judgment"} for item in h1._V7_H1_QUESTION_IDS],
                    "signature": "signature", "timestamp_utc": "2026-08-03T00:00:00Z",
                }
                decision["decision_sha256"] = sha256_bytes(canonical_json_bytes({key: decision[key] for key in sorted(decision)}))
                self.assertEqual(
                    h1.validate_h1_source_gold_decision_v6(
                        decision=decision, packet=packet, readiness=readiness,
                        runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
                    )["aggregate_disposition"], disposition,
                )
                if disposition == "approved":
                    self.assertEqual(
                        h1.validate_approved_h1_terminal_v6(
                            decision=decision, packet=packet, readiness=readiness,
                            runtime_closure=closure, authority_path=root / "phase2/source-authority.json",
                        )["aggregate_disposition"], "approved",
                    )
                else:
                    with self.assertRaisesRegex(H1Error, "H1_V6_TERMINAL_APPROVAL_REQUIRED"):
                        h1.validate_approved_h1_terminal_v6(decision=decision, packet=packet, readiness=readiness, runtime_closure=closure, authority_path=root / "phase2/source-authority.json")

    def test_h1_v7_fixed_packet_and_readiness_writers_are_decision_free_exact_resume(self) -> None:
        from specchoice_measurement.adapter import (  # noqa: PLC0415
            write_pr2164_accepted_v6_adapter_batch_v4,
        )
        from specchoice_measurement.attempts import (  # noqa: PLC0415
            run_fresh_adversarial_suite_v7,
            run_fresh_formal_measurement_v6,
        )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment, closure = self._copy_fresh_v7_repository(repository)
            authority = experiment / "phase2/source-authority.json"
            with (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(h1, "load_runtime_closure_v4", return_value=closure),
                mock.patch(
                    "specchoice_measurement.adapter.load_runtime_closure_v4",
                    return_value=closure,
                ),
                mock.patch(
                    "specchoice_measurement.attempts.load_runtime_closure_v4",
                    return_value=closure,
                ),
            ):
                write_pr2164_accepted_v6_adapter_batch_v4(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                run_fresh_formal_measurement_v6(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                run_fresh_adversarial_suite_v7(
                    repository=repository,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                self.assertEqual(
                    h1.write_h1_review_packet_v7(
                        runtime_closure=closure, authority_path=authority
                    )["status"],
                    "written",
                )
                self.assertEqual(
                    h1.write_h1_review_packet_v7(
                        runtime_closure=closure, authority_path=authority
                    )["status"],
                    "resumed",
                )
                self.assertEqual(
                    h1.write_h1_review_readiness_v7(
                        runtime_closure=closure, authority_path=authority
                    )["status"],
                    "written",
                )
                self.assertEqual(
                    h1.write_h1_review_readiness_v7(
                        runtime_closure=closure, authority_path=authority
                    )["status"],
                    "resumed",
                )

                packet = json.loads((repository / h1._V7_PACKET_PATH).read_bytes())
                readiness = json.loads(
                    (repository / h1._V7_READINESS_PATH).read_bytes()
                )
                h1.validate_h1_review_readiness_v7(
                    readiness=readiness,
                    packet=packet,
                    runtime_closure=closure,
                    authority_path=authority,
                )
                for forbidden in (
                    "aggregate_disposition",
                    "attestation",
                    "reviewer",
                    "semantic_responses",
                    "signature",
                    "timestamp_utc",
                ):
                    self.assertNotIn(forbidden, packet)
                    self.assertNotIn(forbidden, readiness)
                self.assertFalse((repository / h1._V7_DECISION_PATH).exists())

    def test_h1_v7_writers_repeat_full_gate_before_write_primitive(self) -> None:
        packet, closure = self._v7_packet()
        packet_expected = (
            packet,
            canonical_json_bytes(packet),
            h1.render_h1_review_checkpoint_v7(packet),
        )
        root = Path(__file__).parents[1]
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(
                packet=packet,
                runtime_closure=closure,
                authority_path=root / "phase2/source-authority.json",
            )
        readiness_expected = (
            packet,
            readiness,
            canonical_json_bytes(readiness),
        )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            with (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(
                    h1,
                    "_expected_fixed_h1_review_packet_v7",
                    side_effect=[
                        packet_expected,
                        H1Error("ACTIVE_AUTHORITY_MISMATCH"),
                    ],
                ),
                mock.patch.object(h1, "_publish_directory_no_replace") as primitive,
                self.assertRaisesRegex(H1Error, "ACTIVE_AUTHORITY_MISMATCH"),
            ):
                h1.write_h1_review_packet_v7(
                    runtime_closure=closure,
                    authority_path=root / "phase2/source-authority.json",
                )
            primitive.assert_not_called()
            self.assertFalse((repository / h1._V7_PACKET_PATH).exists())
            self.assertFalse((repository / h1._V7_MARKDOWN_PATH).exists())

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            publish_parent = (
                repository / h1._V7_PACKET_PATH
            ).parent.parent
            publish_parent.mkdir(parents=True)
            with (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(
                    h1,
                    "_expected_fixed_h1_review_packet_v7",
                    side_effect=[
                        packet_expected,
                        packet_expected,
                        H1Error("ACTIVE_AUTHORITY_MISMATCH"),
                    ],
                ),
                mock.patch.object(h1, "_publish_directory_no_replace") as primitive,
                self.assertRaisesRegex(H1Error, "ACTIVE_AUTHORITY_MISMATCH"),
            ):
                h1.write_h1_review_packet_v7(
                    runtime_closure=closure,
                    authority_path=root / "phase2/source-authority.json",
                )
            primitive.assert_not_called()
            self.assertFalse((repository / h1._V7_PACKET_PATH).exists())
            self.assertFalse((repository / h1._V7_MARKDOWN_PATH).exists())
            self.assertEqual(list(publish_parent.iterdir()), [])

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / h1._V7_READINESS_PATH).parent.mkdir(parents=True)
            with (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(
                    h1,
                    "_expected_fixed_h1_review_readiness_v7",
                    side_effect=[
                        readiness_expected,
                        H1Error("RUNTIME_CLOSURE_V4_REQUIRED"),
                    ],
                ),
                mock.patch.object(h1, "_write_h1_exact_resume") as primitive,
                self.assertRaisesRegex(H1Error, "RUNTIME_CLOSURE_V4_REQUIRED"),
            ):
                h1.write_h1_review_readiness_v7(
                    runtime_closure=closure,
                    authority_path=root / "phase2/source-authority.json",
                )
            primitive.assert_not_called()
            self.assertFalse((repository / h1._V7_READINESS_PATH).exists())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "readiness.json"
            with (
                mock.patch.object(
                    h1,
                    "_preflight_h1_exact_resume",
                    side_effect=AssertionError("late target preflight"),
                ),
                mock.patch.object(h1, "write_new_descriptor_file") as primitive,
            ):
                self.assertEqual(
                    h1._write_h1_exact_resume(
                        output,
                        b"{}\n",
                        "H1_V7_READINESS_OUTPUT_INVALID",
                        preflight_status="written",
                    ),
                    "written",
                )
            primitive.assert_called_once_with(output.parent, output.name, b"{}\n")

    def test_h1_v7_packet_writer_rejects_divergent_link_special_partial_and_race(self) -> None:
        packet, closure = self._v7_packet()
        packet_raw = canonical_json_bytes(packet)
        markdown_raw = h1.render_h1_review_checkpoint_v7(packet)
        expected = (packet, packet_raw, markdown_raw)
        root = Path(__file__).parents[1]

        for kind in (
            "divergent", "symlink", "special", "partial", "empty_directory", "extra"
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                packet_path = repository / h1._V7_PACKET_PATH
                packet_path.parent.mkdir(parents=True)
                if kind == "divergent":
                    packet_path.write_bytes(b"divergent\n")
                elif kind == "symlink":
                    source = repository / "symlink-source"
                    source.write_bytes(packet_raw)
                    packet_path.symlink_to(source)
                elif kind == "special":
                    os.mkfifo(packet_path)
                elif kind == "partial":
                    packet_path.write_bytes(packet_raw)
                elif kind == "empty_directory":
                    pass
                else:
                    packet_path.write_bytes(packet_raw)
                    (repository / h1._V7_MARKDOWN_PATH).write_bytes(markdown_raw)
                    (packet_path.parent / "undeclared.json").write_bytes(b"{}\n")
                with (
                    mock.patch.object(h1, "_REPOSITORY", repository),
                    mock.patch.object(
                        h1,
                        "_expected_fixed_h1_review_packet_v7",
                        return_value=expected,
                    ),
                    mock.patch.object(h1, "_publish_directory_no_replace") as primitive,
                    self.assertRaisesRegex(H1Error, "H1_V7_PACKET_OUTPUT_INVALID"),
                ):
                    h1.write_h1_review_packet_v7(
                        runtime_closure=closure,
                        authority_path=root / "phase2/source-authority.json",
                    )
                primitive.assert_not_called()

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            racer = repository / h1._V7_PACKET_PATH
            racer.parent.parent.mkdir(parents=True)
            real_publish = h1._publish_directory_no_replace

            def race(source: Path, target: Path, code: str) -> None:
                racer.parent.mkdir(parents=True)
                racer.write_bytes(b"racer\n")
                real_publish(source, target, code)

            with (
                mock.patch.object(h1, "_REPOSITORY", repository),
                mock.patch.object(
                    h1,
                    "_expected_fixed_h1_review_packet_v7",
                    return_value=expected,
                ),
                mock.patch.object(
                    h1, "_publish_directory_no_replace", side_effect=race
                ),
                self.assertRaisesRegex(H1Error, "H1_V7_PACKET_OUTPUT_INVALID"),
            ):
                h1.write_h1_review_packet_v7(
                    runtime_closure=closure,
                    authority_path=root / "phase2/source-authority.json",
                )
            self.assertEqual(racer.read_bytes(), b"racer\n")
            self.assertFalse((repository / h1._V7_MARKDOWN_PATH).exists())

    def test_h1_v6_decision_writer_is_fixed_path_and_preflight_rejects_hostile_target(self) -> None:
        packet, closure = self._v7_packet()
        root = Path(__file__).parents[1]
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(
                packet=packet,
                runtime_closure=closure,
                authority_path=root / "phase2/source-authority.json",
            )
        decision = self._v7_human_decision(packet, readiness)

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            fixed_parent = (repository / h1._V7_DECISION_PATH).parent
            fixed_parent.mkdir(parents=True)
            alias_parent = repository / "review-alias"
            alias_parent.symlink_to(fixed_parent, target_is_directory=True)
            for alternate in (
                repository / "reviews/alternate.json",
                repository / "reviews/h1-source-gold-decision-v5.json",
                alias_parent / Path(h1._V7_DECISION_PATH).name,
            ):
                with (
                    self.subTest(path=alternate.name),
                    mock.patch.object(h1, "_REPOSITORY", repository),
                    mock.patch.object(h1, "_write_h1_exact_resume") as primitive,
                    self.assertRaisesRegex(H1Error, "H1_V6_DECISION_OUTPUT_INVALID"),
                ):
                    h1.write_h1_source_gold_decision_v6(
                        output=alternate,
                        decision=decision,
                        packet=packet,
                        readiness=readiness,
                        runtime_closure=closure,
                        authority_path=root / "phase2/source-authority.json",
                    )
                primitive.assert_not_called()
                self.assertFalse(alternate.exists())

        for kind in ("directory", "symlink", "divergent"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                output = repository / h1._V7_DECISION_PATH
                output.parent.mkdir(parents=True)
                if kind == "directory":
                    output.mkdir()
                elif kind == "symlink":
                    source = repository / "decision-source"
                    source.write_bytes(canonical_json_bytes(decision))
                    output.symlink_to(source)
                else:
                    output.write_bytes(b"divergent\n")
                with (
                    mock.patch.object(h1, "_REPOSITORY", repository),
                    mock.patch.object(h1, "_v7_source_snapshot", return_value=self._last_v7_snapshot),
                    mock.patch.object(h1, "_validate_published_v7_review_bytes"),
                    self.assertRaisesRegex(H1Error, "H1_V6_DECISION_OUTPUT_INVALID"),
                ):
                    h1.write_h1_source_gold_decision_v6(
                        output=output,
                        decision=decision,
                        packet=packet,
                        readiness=readiness,
                        runtime_closure=closure,
                        authority_path=root / "phase2/source-authority.json",
                        preflight=True,
                    )

    def test_h1_v6_decision_writer_revalidates_closure_and_authority_before_write(self) -> None:
        packet, closure = self._v7_packet()
        snapshot = self._last_v7_snapshot
        root = Path(__file__).parents[1]
        with (
            mock.patch.object(h1, "_v7_source_snapshot", return_value=snapshot),
            mock.patch.object(h1, "_validate_published_v7_review_bytes"),
        ):
            readiness = h1.build_h1_review_readiness_v7(
                packet=packet,
                runtime_closure=closure,
                authority_path=root / "phase2/source-authority.json",
            )
        decision = self._v7_human_decision(packet, readiness)

        for code in ("RUNTIME_CLOSURE_V4_REQUIRED", "ACTIVE_AUTHORITY_MISMATCH"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                output = repository / h1._V7_DECISION_PATH
                output.parent.mkdir(parents=True)
                with (
                    mock.patch.object(h1, "_REPOSITORY", repository),
                    mock.patch.object(
                        h1,
                        "_v7_source_snapshot",
                        side_effect=[snapshot, H1Error(code)],
                    ),
                    mock.patch.object(h1, "_validate_published_v7_review_bytes"),
                    mock.patch.object(h1, "_write_h1_exact_resume") as primitive,
                    self.assertRaisesRegex(H1Error, code),
                ):
                    h1.write_h1_source_gold_decision_v6(
                        output=output,
                        decision=decision,
                        packet=packet,
                        readiness=readiness,
                        runtime_closure=closure,
                        authority_path=root / "phase2/source-authority.json",
                    )
                primitive.assert_not_called()
                self.assertFalse(output.exists())

    def test_v4_02_22_reports_are_approved_only_exact_resume_and_summary_is_downstream(self) -> None:
        from specchoice_measurement import final_reports

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in final_reports._FINAL_02_22_INPUT_PATHS.values():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(f"frozen:{relative}\n".encode())
            for relative in (*final_reports.FINAL_SUCCESSOR_TARGETS_02_22, final_reports.FINAL_SUCCESSOR_SUMMARY_02_22):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
            bindings = final_reports.build_final_02_22_input_bindings(root)
            decision = {"decision_sha256": "d" * 64, "aggregate_disposition": "approved"}
            packet = {"packet_sha256": "p" * 64, "source_identity": {"closure": {"path": "fixed", "byte_length": 1, "sha256": "c" * 64}}}
            readiness = {"readiness_sha256": "r" * 64, "source_identity": packet["source_identity"]}
            with mock.patch.object(final_reports, "validate_v4_terminal_report_inputs", return_value=decision):
                real_write = final_reports._write_final_02_22_exact_resume
                write_count = 0

                def racing_write(
                    base: Path,
                    relative: str,
                    raw: bytes,
                    *,
                    preflight_status: str,
                ) -> str:
                    nonlocal write_count
                    write_count += 1
                    if write_count == 2:
                        (base / relative).write_bytes(b"concurrent-divergent\n")
                    return real_write(
                        base,
                        relative,
                        raw,
                        preflight_status=preflight_status,
                    )

                with (
                    mock.patch.object(
                        final_reports,
                        "_write_final_02_22_exact_resume",
                        side_effect=racing_write,
                    ),
                    self.assertRaisesRegex(
                        final_reports.FinalReportError,
                        "FINAL_02_22_TARGET_DIVERGED",
                    ),
                ):
                    final_reports.write_final_successor_reports_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )
                first, second, third, _ = final_reports.FINAL_SUCCESSOR_TARGETS_02_22
                self.assertTrue((root / first).is_file())
                self.assertEqual((root / second).read_bytes(), b"concurrent-divergent\n")
                self.assertFalse((root / third).exists())
                (root / second).unlink()
                with mock.patch.object(
                    final_reports,
                    "verify_final_successor_reports_02_22",
                    wraps=final_reports.verify_final_successor_reports_02_22,
                ) as postflight:
                    written = final_reports.write_final_successor_reports_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )
                self.assertEqual(postflight.call_count, 1)
                self.assertEqual(written["status"], "written")
                self.assertEqual(
                    final_reports.write_final_successor_reports_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )["status"], "resumed",
                )
                with mock.patch.object(
                    final_reports,
                    "verify_final_successor_reports_02_22",
                    wraps=final_reports.verify_final_successor_reports_02_22,
                ) as summary_gate:
                    final_reports.write_final_successor_summary_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )
                self.assertEqual(summary_gate.call_count, 3)
                self.assertEqual(
                    final_reports.validate_final_successor_summary_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )["status"], "verified",
                )
                summary_path = root / final_reports.FINAL_SUCCESSOR_SUMMARY_02_22
                summary_raw = summary_path.read_bytes()
                real_summary_gate = final_reports.verify_final_successor_reports_02_22
                summary_gate_count = 0

                def drift_summary_during_repeated_gate(*args: object, **kwargs: object) -> dict[str, object]:
                    nonlocal summary_gate_count
                    verified_reports = real_summary_gate(*args, **kwargs)
                    summary_gate_count += 1
                    if summary_gate_count == 2:
                        summary_path.write_bytes(b"concurrent-divergent\n")
                    return verified_reports

                with (
                    mock.patch.object(
                        final_reports,
                        "verify_final_successor_reports_02_22",
                        side_effect=drift_summary_during_repeated_gate,
                    ),
                    self.assertRaisesRegex(
                        final_reports.FinalReportError,
                        "FINAL_02_22_SUMMARY_INVALID",
                    ),
                ):
                    final_reports.write_final_successor_summary_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )
                self.assertEqual(summary_gate_count, 3)
                self.assertEqual(summary_path.read_bytes(), b"concurrent-divergent\n")
                summary_path.write_bytes(summary_raw)
                drifted = root / final_reports._FINAL_02_22_INPUT_PATHS["roadmap"]
                drifted.write_bytes(drifted.read_bytes() + b"drift")
                with self.assertRaisesRegex(final_reports.FinalReportError, "FINAL_02_22_INPUT_DRIFT"):
                    final_reports.verify_final_successor_reports_02_22(
                        root, decision=decision, packet=packet, readiness=readiness,
                        runtime_closure={}, authority_path=root / "authority.json",
                        input_bindings=bindings,
                    )

    @staticmethod
    def _run_evidence_cli(argv: list[str]) -> tuple[int, bytes, bytes]:
        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8", write_through=True)
        stderr = io.TextIOWrapper(stderr_bytes, encoding="utf-8", write_through=True)
        with (
            mock.patch.object(sys, "argv", ["specchoice-evidence", *argv]),
            mock.patch.object(sys, "stdout", stdout),
            mock.patch.object(sys, "stderr", stderr),
        ):
            try:
                status = cli_module.main()
            except SystemExit as error:
                status = int(error.code or 0)
        stdout.flush()
        stderr.flush()
        observed_stdout = stdout_bytes.getvalue()
        observed_stderr = stderr_bytes.getvalue()
        stdout.detach()
        stderr.detach()
        return status, observed_stdout, observed_stderr

    @staticmethod
    def _filesystem_snapshot(root: Path) -> tuple[tuple[object, ...], ...]:
        entries: list[tuple[object, ...]] = []
        for path in sorted(root.rglob("*")):
            status = path.lstat()
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                kind = "symlink"
                content: object = os.readlink(path)
            elif path.is_file():
                kind = "file"
                content = path.read_bytes()
            elif path.is_dir():
                kind = "directory"
                content = None
            else:
                kind = "special"
                content = None
            entries.append(
                (relative, kind, content, stat.S_IMODE(status.st_mode), status.st_mtime_ns)
            )
        return tuple(entries)

    def _assert_v7_parser_contract(
        self,
        repository: Path,
        command: str,
        pairs: list[tuple[str, Path]],
        *,
        flags: tuple[str, ...] = (),
    ) -> list[str]:
        argv = [command]
        for option, value in pairs:
            argv.extend((option, str(value)))
        argv.extend(flags)
        parsed = cli_module.build_parser().parse_args(argv)
        self.assertTrue(callable(parsed.handler))
        baseline = self._filesystem_snapshot(repository)

        for index, (option, _) in enumerate(pairs):
            start = 1 + (index * 2)
            candidate = argv[:start] + argv[start + 2 :]
            status, stdout, stderr = self._run_evidence_cli(candidate)
            self.assertEqual(status, 2, option)
            self.assertEqual(stdout, b"", option)
            self.assertTrue(stderr, option)
            self.assertEqual(self._filesystem_snapshot(repository), baseline, option)
        for option, value in pairs:
            status, stdout, stderr = self._run_evidence_cli(
                [*argv, option, str(value)]
            )
            self.assertEqual(status, 2, option)
            self.assertEqual(stdout, b"", option)
            self.assertTrue(stderr, option)
            self.assertEqual(self._filesystem_snapshot(repository), baseline, option)
        for flag in flags:
            without = [item for item in argv if item != flag]
            status, stdout, stderr = self._run_evidence_cli(without)
            self.assertEqual((status, stdout), (2, b""), flag)
            self.assertTrue(stderr, flag)
            self.assertEqual(self._filesystem_snapshot(repository), baseline, flag)
            status, stdout, stderr = self._run_evidence_cli([*argv, flag])
            self.assertEqual((status, stdout), (2, b""), flag)
            self.assertTrue(stderr, flag)
            self.assertEqual(self._filesystem_snapshot(repository), baseline, flag)

        abbreviated = list(argv)
        abbreviated[1] = pairs[0][0][:-2]
        for candidate in (
            abbreviated,
            [*argv, "--unknown-option", "value"],
            [*argv, "extra-positional"],
        ):
            status, stdout, stderr = self._run_evidence_cli(candidate)
            self.assertEqual(status, 2)
            self.assertEqual(stdout, b"")
            self.assertTrue(stderr)
            self.assertEqual(self._filesystem_snapshot(repository), baseline)
        return argv

    @staticmethod
    def _fixed_v7_paths(repository: Path) -> dict[str, Path]:
        return {
            role: repository / relative
            for role, relative in cli_module._H1_V7_FIXED_PATHS.items()
        }

    def _assert_wrong_cli_paths(
        self,
        repository: Path,
        argv: list[str],
        pairs: list[tuple[str, Path]],
    ) -> None:
        for index, (option, _) in enumerate(pairs):
            candidate = list(argv)
            candidate[2 + (index * 2)] = str(repository / f"alternate-{index}.json")
            before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
            ):
                status, stdout, stderr = self._run_evidence_cli(candidate)
            self.assertEqual(status, 2, option)
            self.assertEqual(stdout, b"", option)
            self.assertIn(b"H1_V7_CANONICAL_PATH_REQUIRED", stderr, option)
            self.assertEqual(self._filesystem_snapshot(repository), before, option)

    def test_validate_h1_review_readiness_v7_cli_is_registered_read_only_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "marker").write_bytes(b"unchanged\n")
            paths = self._fixed_v7_paths(repository)
            pairs = [
                ("--receipt", paths["readiness"]),
                ("--packet", paths["packet"]),
                ("--runtime-closure", paths["runtime_closure"]),
                ("--authority", paths["authority"]),
                ("--adapter-config", paths["adapter_config"]),
                ("--h1-schema", paths["h1_schema"]),
            ]
            argv = self._assert_v7_parser_contract(
                repository,
                "validate-h1-review-readiness-v7", pairs
            )
            before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"ready": True}, {"packet": True}, {"closure": True}, {"rules": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module, "validate_h1_review_readiness_v7", return_value={"ready": True}
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual(status, 0)
            self.assertEqual(
                stdout,
                canonical_json_bytes({"status": "h1_review_readiness_v7_valid"}),
            )
            self.assertEqual(stderr, b"")
            self.assertEqual(self._filesystem_snapshot(repository), before)
            self._assert_wrong_cli_paths(repository, argv, pairs)

            wrong_directory = repository / "wrong-directory"
            wrong_directory.mkdir()
            wrong_link = repository / "wrong-link"
            wrong_link.symlink_to(wrong_directory, target_is_directory=True)
            for wrong in (wrong_directory, wrong_link):
                candidate = list(argv)
                candidate[2] = str(wrong)
                with (
                    mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                    mock.patch.object(cli_module, "_repository_root", return_value=repository),
                ):
                    status, output, _ = self._run_evidence_cli(candidate)
                self.assertEqual((status, output), (2, b""))

            failure_before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"ready": True}, {"packet": True}, {"closure": True}, {"rules": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module,
                    "validate_h1_review_readiness_v7",
                    side_effect=H1Error("H1_V7_READINESS_MISMATCH"),
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual((status, stdout), (2, b""))
            self.assertIn(b"H1_V7_READINESS_MISMATCH", stderr)
            self.assertEqual(self._filesystem_snapshot(repository), failure_before)

        for kind in ("missing", "directory", "symlink", "duplicate", "noncanonical"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory)
                paths = self._fixed_v7_paths(repository)
                target = paths["readiness"]
                target.parent.mkdir(parents=True)
                if kind == "directory":
                    target.mkdir()
                elif kind == "symlink":
                    source = repository / "source.json"
                    source.write_bytes(b"{}\n")
                    target.symlink_to(source)
                elif kind == "duplicate":
                    target.write_bytes(b'{"status":1,"status":2}\n')
                elif kind == "noncanonical":
                    target.write_bytes(b'{\n  "status": 1\n}\n')
                pairs = [
                    ("--receipt", paths["readiness"]),
                    ("--packet", paths["packet"]),
                    ("--runtime-closure", paths["runtime_closure"]),
                    ("--authority", paths["authority"]),
                    ("--adapter-config", paths["adapter_config"]),
                    ("--h1-schema", paths["h1_schema"]),
                ]
                candidate = ["validate-h1-review-readiness-v7"]
                for option, value in pairs:
                    candidate.extend((option, str(value)))
                before = self._filesystem_snapshot(repository)
                with (
                    mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                    mock.patch.object(cli_module, "_repository_root", return_value=repository),
                ):
                    status, stdout, stderr = self._run_evidence_cli(candidate)
                self.assertEqual((status, stdout), (2, b""))
                self.assertTrue(stderr)
                self.assertEqual(self._filesystem_snapshot(repository), before)

    def test_render_h1_review_checkpoint_v7_cli_requires_no_write_and_persists_no_human_fields(self) -> None:
        packet, _ = self._v7_packet()
        rendered = h1.render_h1_review_checkpoint_v7(packet)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "marker").write_bytes(b"unchanged\n")
            paths = self._fixed_v7_paths(repository)
            pairs = [
                ("--packet", paths["packet"]),
                ("--readiness", paths["readiness"]),
                ("--runtime-closure", paths["runtime_closure"]),
                ("--authority", paths["authority"]),
                ("--h1-schema", paths["h1_schema"]),
            ]
            argv = self._assert_v7_parser_contract(
                repository,
                "render-h1-review-checkpoint-v7", pairs, flags=("--no-write",)
            )
            before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[packet, {"readiness": True}, {"closure": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module, "validate_h1_review_readiness_v7", return_value={"readiness": True}
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual((status, stdout, stderr), (0, rendered, b""))
            self.assertEqual(self._filesystem_snapshot(repository), before)
            for field in (b'"reviewer"', b'"signature"', b'"timestamp_utc"'):
                self.assertNotIn(field, stdout)
            self._assert_wrong_cli_paths(repository, argv, pairs)

            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[packet, {"readiness": True}, {"closure": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module,
                    "validate_h1_review_readiness_v7",
                    side_effect=H1Error("H1_V7_PUBLISHED_REVIEW_INVALID"),
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual((status, stdout), (2, b""))
            self.assertIn(b"H1_V7_PUBLISHED_REVIEW_INVALID", stderr)
            self.assertEqual(self._filesystem_snapshot(repository), before)

    def test_validate_h1_source_gold_decision_v6_cli_is_registered_read_only_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "marker").write_bytes(b"unchanged\n")
            paths = self._fixed_v7_paths(repository)
            pairs = [
                ("--decision", paths["decision"]),
                ("--packet", paths["packet"]),
                ("--readiness", paths["readiness"]),
                ("--runtime-closure", paths["runtime_closure"]),
                ("--authority", paths["authority"]),
                ("--h1-schema", paths["h1_schema"]),
            ]
            argv = self._assert_v7_parser_contract(
                repository,
                "validate-h1-source-gold-decision-v6", pairs
            )
            before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"decision": True}, {"packet": True}, {"ready": True}, {"closure": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module, "validate_h1_source_gold_decision_v6", return_value={"decision": True}
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual(status, 0)
            self.assertEqual(
                stdout,
                canonical_json_bytes({"status": "h1_source_gold_decision_v6_valid"}),
            )
            self.assertEqual(stderr, b"")
            self.assertEqual(self._filesystem_snapshot(repository), before)
            self._assert_wrong_cli_paths(repository, argv, pairs)

            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"decision": True}, {"packet": True}, {"ready": True}, {"closure": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module,
                    "validate_h1_source_gold_decision_v6",
                    side_effect=H1Error("H1_V6_AGGREGATE_CONFLICT"),
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual((status, stdout), (2, b""))
            self.assertIn(b"H1_V6_AGGREGATE_CONFLICT", stderr)
            self.assertEqual(self._filesystem_snapshot(repository), before)

    def test_validate_approved_h1_terminal_v6_cli_is_registered_read_only_and_fail_closed(self) -> None:
        from specchoice_measurement import final_reports

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "marker").write_bytes(b"unchanged\n")
            paths = self._fixed_v7_paths(repository)
            terminal_paths = [repository / path for path in final_reports.FINAL_SUCCESSOR_TARGETS_02_22]
            pairs = [
                ("--decision", paths["decision"]),
                ("--packet", paths["packet"]),
                ("--readiness", paths["readiness"]),
                ("--runtime-closure", paths["runtime_closure"]),
                ("--authority", paths["authority"]),
                ("--adapter-config", paths["adapter_config"]),
                ("--h1-schema", paths["h1_schema"]),
                ("--phase1-verification", terminal_paths[0]),
                ("--phase1-review", terminal_paths[1]),
                ("--phase2-verification", terminal_paths[2]),
                ("--phase2-review", terminal_paths[3]),
                ("--summary", repository / final_reports.FINAL_SUCCESSOR_SUMMARY_02_22),
            ]
            argv = self._assert_v7_parser_contract(
                repository,
                "validate-approved-h1-terminal-v6", pairs
            )
            before = self._filesystem_snapshot(repository)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"decision": True}, {"packet": True}, {"ready": True}, {"closure": True}, {"rules": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module, "validate_approved_h1_terminal_v6", return_value={"decision": True}
                ),
                mock.patch.object(cli_module, "build_final_02_22_input_bindings", return_value={}),
                mock.patch.object(cli_module, "validate_final_successor_summary_02_22", return_value={"status": "verified"}),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual(status, 0)
            self.assertEqual(
                stdout,
                canonical_json_bytes({"status": "approved_h1_terminal_v6_valid"}),
            )
            self.assertEqual(stderr, b"")
            self.assertEqual(self._filesystem_snapshot(repository), before)
            self._assert_wrong_cli_paths(repository, argv, pairs[:7])

            for index, (option, _) in enumerate(pairs[7:], start=7):
                candidate = list(argv)
                candidate[2 + (index * 2)] = str(repository / f"wrong-terminal-{index}.md")
                wrong_path_before = self._filesystem_snapshot(repository)
                with (
                    mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                    mock.patch.object(cli_module, "_repository_root", return_value=repository),
                ):
                    status, output, error = self._run_evidence_cli(candidate)
                self.assertEqual((status, output), (2, b""), option)
                self.assertIn(b"FINAL_02_22_CANONICAL_PATH_REQUIRED", error, option)
                self.assertEqual(
                    self._filesystem_snapshot(repository), wrong_path_before, option
                )

            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=repository / "experiments/specchoice-v1.3.2"),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "_v7_h1_value",
                    side_effect=[{"decision": True}, {"packet": True}, {"ready": True}, {"closure": True}, {"rules": True}],
                ),
                mock.patch.object(cli_module, "_validate_h1_v7_cli_schema"),
                mock.patch.object(
                    cli_module,
                    "validate_approved_h1_terminal_v6",
                    side_effect=H1Error("H1_V6_TERMINAL_APPROVAL_REQUIRED"),
                ),
            ):
                status, stdout, stderr = self._run_evidence_cli(argv)
            self.assertEqual((status, stdout), (2, b""))
            self.assertIn(b"H1_V6_TERMINAL_APPROVAL_REQUIRED", stderr)
            self.assertEqual(self._filesystem_snapshot(repository), before)


if __name__ == "__main__":
    unittest.main()
