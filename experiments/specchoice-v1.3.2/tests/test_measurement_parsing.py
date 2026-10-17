# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Closed-schema preflight contracts for Phase 2 prediction input."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from specchoice_measurement.adapter import build_pr2164_adapter_batch, build_pr2164_v6_adapter_batch
from specchoice_measurement import preflight
from specchoice_measurement.preflight import preflight_prediction_batch
from specchoice_evidence.canonical import canonical_json_bytes
from specchoice_evidence import filesystem
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file
from unittest import mock


class MeasurementParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiment_root = Path(__file__).parents[1]
        self.bundle = (
            self.experiment_root
            / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        )
        self.golden_path = self.experiment_root / "fixtures/measurement/golden-predictions-v2.json"
        self.batch = build_pr2164_adapter_batch(
            authority_path=self.experiment_root
            / "phase2/source-authority-v13-historical.json",
            bundle_root=self.bundle,
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            revocation_path=self.experiment_root / "receipts/fixture-closure-revocation-v2.json",
        )
        self.assertTrue(self.batch.valid)
        golden = json.loads(self.golden_path.read_text(encoding="utf-8"))
        self.assertEqual(golden["adapter_batch_sha256"], self.batch.adapter_batch_sha256)

    def v6_batch(self):
        return build_pr2164_v6_adapter_batch(
            registry_path=self.experiment_root / "config/fixture-registry-pr2164-v6.json",
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v3.json",
            contract_path=self.experiment_root / "config/measurement/pr2164-semantic-gold-contract-v2.json",
            golden_path=self.experiment_root / "fixtures/measurement/golden-predictions-v4.json",
            bundle_root=self.bundle,
        )

    def v6_payload(self, batch) -> dict[str, object]:
        golden = json.loads((self.experiment_root / "fixtures/measurement/golden-predictions-v4.json").read_text())
        return {
            "schema_version": "canonical-adjudication-v3",
            "adapter_batch_sha256": batch.adapter_batch_sha256,
            "predictions": [
                {
                    "fixture_id": outcome["fixture_id"],
                    "finding_id": f"{outcome['fixture_id']}:1",
                    "rationale": outcome["rationale"],
                    "adjudication": {
                        "surfaced": outcome["observed"]["surfaced"],
                        "parameter_status": outcome["observed"]["status"],
                        "proposed_name": outcome["observed"]["name"],
                        "evidence_spans": deepcopy(outcome["evidence_spans"]),
                    },
                }
                for outcome in golden["outcomes"]
            ],
        }

    def _span(self, record) -> dict[str, object]:
        source = next(item for item in record.raw_files if item.role == "fixture_source")
        raw = (self.bundle / source.path).read_bytes()
        return {
            "source_sha256": source.sha256,
            "start_byte": 0,
            "end_byte": 1,
            "text": raw[:1].decode("utf-8"),
        }

    def payload(self) -> dict[str, object]:
        predictions: list[dict[str, object]] = []
        for record in self.batch.records:
            if record.category == "negative":
                adjudication = {
                    "surfaced": False,
                    "parameter_status": None,
                    "proposed_name": None,
                    "evidence_spans": [],
                }
            elif record.category == "candidate":
                adjudication = {
                    "surfaced": True,
                    "parameter_status": "classify_out",
                    "proposed_name": None,
                    "evidence_spans": [self._span(record)],
                }
            else:
                adjudication = {
                    "surfaced": True,
                    "parameter_status": "accept",
                    "proposed_name": record.expected_parameter_names[0],
                    "evidence_spans": [self._span(record)],
                }
            predictions.append(
                {
                    "fixture_id": record.fixture_id,
                    "finding_id": f"{record.fixture_id}:1",
                    "rationale": "explicit fixture adjudication",
                    "adjudication": adjudication,
                }
            )
        return {
            "schema_version": "canonical-adjudication-v1",
            "adapter_batch_sha256": self.batch.adapter_batch_sha256,
            "predictions": predictions,
        }

    def preflight(self, payload: object):
        return preflight_prediction_batch(
            raw=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            adapter_batch=self.batch,
            ingress="current-v1",
        )

    def test_complete_current_schema_payload_is_valid_with_explicit_empty_diagnostics(self) -> None:
        result = self.preflight(self.payload())

        self.assertEqual(result.status, "valid_preflight")
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(len(result.parsed_predictions), 11)
        self.assertEqual(result.raw_prediction_sha256, __import__("hashlib").sha256(
            json.dumps(self.payload(), separators=(",", ":")).encode("utf-8")
        ).hexdigest())
        self.assertEqual(result.as_dict()["diagnostics"], [])

    def test_v3_closed_schema_rejects_unknown_keys_at_every_score_bearing_level(self) -> None:
        batch = self.v6_batch()
        self.assertTrue(batch.valid)
        for level in ("payload", "prediction", "adjudication", "span"):
            payload = self.v6_payload(batch)
            prediction = next(item for item in payload["predictions"] if item["adjudication"]["surfaced"])
            target = {
                "payload": payload,
                "prediction": prediction,
                "adjudication": prediction["adjudication"],
                "span": prediction["adjudication"]["evidence_spans"][0],
            }[level]
            target["unknown"] = "must fail closed"
            with self.subTest(level=level):
                result = preflight_prediction_batch(
                    raw=canonical_json_bytes(payload), adapter_batch=batch, ingress="current-v3",
                )
                self.assertEqual(result.status, "invalid_preflight")
                self.assertIn("FIELD_UNKNOWN", {item.code for item in result.diagnostics})

    def test_v3_binds_schema_and_ingress_but_leaves_integrity_to_per_span_scoring(self) -> None:
        batch = self.v6_batch()
        payload = self.v6_payload(batch)
        target = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_DIRECT_NUM_PMP")
        target["adjudication"]["evidence_spans"][0]["source_path"] = "raw/evaluation_fixtures/OTHER/source.txt"
        target["adjudication"]["evidence_spans"][0]["text"] = "byte mismatch retained for scoring"
        integrity = preflight_prediction_batch(
            raw=canonical_json_bytes(payload), adapter_batch=batch, ingress="current-v3",
        )
        self.assertEqual(integrity.status, "valid_preflight")
        self.assertEqual(len(integrity.parsed_predictions), 11)

        wrong_ingress = preflight_prediction_batch(
            raw=canonical_json_bytes(payload), adapter_batch=batch, ingress="current-v1",
        )
        self.assertIn("INGRESS_INVALID", {item.code for item in wrong_ingress.diagnostics})
        payload["schema_version"] = "canonical-adjudication-v1"
        wrong_schema = preflight_prediction_batch(
            raw=canonical_json_bytes(payload), adapter_batch=batch, ingress="current-v3",
        )
        self.assertIn("SCHEMA_VERSION_INVALID", {item.code for item in wrong_schema.diagnostics})

    def test_closed_schema_and_complete_batch_collect_all_blockers(self) -> None:
        payload = self.payload()
        payload["unexpected"] = "score-bearing"
        first = payload["predictions"][0]
        first["fixture_id"] = "UNKNOWN_CASE"
        first["adjudication"]["parameter_status"] = "not_surfaced"
        first["adjudication"].pop("proposed_name")

        result = self.preflight(payload)

        self.assertEqual(result.status, "invalid_preflight")
        self.assertEqual(result.parsed_predictions, ())
        self.assertGreaterEqual(len(result.diagnostics), 5)
        self.assertEqual(
            [item.sort_key() for item in result.diagnostics],
            sorted(item.sort_key() for item in result.diagnostics),
        )
        self.assertFalse(any(key in result.as_dict() for key in ("metrics", "report", "approval", "publication")))

    def test_duplicate_keys_constants_and_noncanonical_no_finding_are_blockers(self) -> None:
        duplicate_key_raw = b'{"schema_version":"canonical-adjudication-v1","schema_version":"canonical-adjudication-v1","adapter_batch_sha256":"x","predictions":[]}'
        duplicate = preflight_prediction_batch(
            raw=duplicate_key_raw, adapter_batch=self.batch, ingress="current-v1"
        )
        constant = preflight_prediction_batch(
            raw=b'{"schema_version":NaN}', adapter_batch=self.batch, ingress="current-v1"
        )
        payload = self.payload()
        no_finding = next(item for item in payload["predictions"] if item["adjudication"]["surfaced"] is False)
        no_finding["adjudication"]["parameter_status"] = "not_surfaced"
        invalid_no_finding = self.preflight(payload)

        self.assertEqual(duplicate.status, "invalid_preflight")
        self.assertIn("JSON_DUPLICATE_KEY", {item.code for item in duplicate.diagnostics})
        self.assertIn("JSON_NONFINITE_CONSTANT", {item.code for item in constant.diagnostics})
        self.assertIn("NO_FINDING_NONCANONICAL", {item.code for item in invalid_no_finding.diagnostics})

    def test_evidence_spans_are_exact_and_adjacent_or_duplicate_spans_remain_independent(self) -> None:
        payload = self.payload()
        surfaced = next(item for item in payload["predictions"] if item["adjudication"]["surfaced"])
        span = surfaced["adjudication"]["evidence_spans"][0]
        surfaced["adjudication"]["evidence_spans"].append(dict(span))
        valid = self.preflight(payload)
        self.assertEqual(valid.status, "valid_preflight")
        self.assertEqual(len(valid.parsed_predictions[0]["adjudication"]["evidence_spans"]), 2)

        span["end_byte"] = span["start_byte"]
        invalid = self.preflight(payload)
        self.assertIn("EVIDENCE_RANGE_INVALID", {item.code for item in invalid.diagnostics})

    def test_evidence_span_from_another_fixture_is_rejected(self) -> None:
        payload = self.payload()
        target = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_CSR_RW_MTVEC_ACCESS")
        other = next(
            item for item in payload["predictions"]
            if item["fixture_id"] == "POS_DIRECT_CACHE_BLOCK"
        )
        target["adjudication"]["evidence_spans"] = [
            deepcopy(other["adjudication"]["evidence_spans"][0])
        ]

        result = self.preflight(payload)

        self.assertEqual(result.status, "invalid_preflight")
        self.assertIn(
            "EVIDENCE_SOURCE_NOT_DECLARED_FOR_FIXTURE",
            {item.code for item in result.diagnostics},
        )

    def test_only_named_legacy_ingress_normalizes_reject_with_raw_trace(self) -> None:
        payload = self.payload()
        candidate = next(item for item in payload["predictions"] if item["fixture_id"].startswith("CAND_"))
        candidate["adjudication"]["parameter_status"] = "reject"
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        legacy = preflight_prediction_batch(raw=raw, adapter_batch=self.batch, ingress="legacy-pr2164-v1")
        current = preflight_prediction_batch(raw=raw, adapter_batch=self.batch, ingress="current-v1")

        self.assertEqual(legacy.status, "completed_with_warnings")
        self.assertEqual(legacy.raw_prediction_sha256, __import__("hashlib").sha256(raw).hexdigest())
        normalized = next(item for item in legacy.parsed_predictions if item["fixture_id"].startswith("CAND_"))
        self.assertEqual(normalized["adjudication"]["parameter_status"], "classify_out")
        normalization = next(item for item in legacy.diagnostics if item.code == "LEGACY_PARAMETER_STATUS_NORMALIZED")
        self.assertEqual((normalization.observed, normalization.expected), ("reject", "classify_out"))
        self.assertIn("PARAMETER_STATUS_INVALID", {item.code for item in current.diagnostics})

    def test_equivalent_blockers_have_byte_identical_total_diagnostic_ordering(self) -> None:
        first = self.payload()
        duplicate = deepcopy(first["predictions"][0])
        first["predictions"].append(duplicate)
        second = deepcopy(first)
        second["predictions"] = list(reversed(second["predictions"]))
        second["predictions"] = second["predictions"][-1:] + second["predictions"][:-1]

        left = self.preflight(first)
        right = self.preflight(second)

        self.assertEqual(left.status, "invalid_preflight")
        self.assertEqual(
            json.dumps([item.as_dict() for item in left.diagnostics], sort_keys=True, separators=(",", ":")),
            json.dumps([item.as_dict() for item in right.diagnostics], sort_keys=True, separators=(",", ":")),
        )

    def test_public_preflight_rejects_swapped_fixture_source_and_fifo_without_consuming_or_blocking(self) -> None:
        """Preflight source bytes must originate at the descriptor-bound read seam."""
        real_open = filesystem.os.open
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            leaf = root / "source.yaml"
            external = root / "external.yaml"
            external.write_text("sentinel: external\n", encoding="utf-8")
            for kind in ("symlink", "fifo"):
                with self.subTest(kind=kind):
                    leaf.write_text("safe: source\n", encoding="utf-8")
                    opened = False

                    def guarded_open(path, flags, *args, **kwargs):
                        nonlocal opened
                        if path != leaf.name or "dir_fd" not in kwargs:
                            return real_open(path, flags, *args, **kwargs)
                        opened = True
                        if kind == "symlink":
                            leaf.unlink()
                            leaf.symlink_to(external)
                            return real_open(path, flags, *args, **kwargs)
                        self.fail("FIFO target reached os.open")

                    if kind == "fifo":
                        leaf.unlink()
                        os.mkfifo(leaf)
                    with mock.patch("specchoice_evidence.filesystem.os.open", side_effect=guarded_open):
                        with self.assertRaises((FilesystemPolicyError, OSError)):
                            read_authoritative_file(root, leaf.name)
                    self.assertEqual(opened, kind == "symlink")
                    if leaf.is_symlink() or leaf.exists():
                        leaf.unlink()

        target = next(
            item.path
            for record in self.batch.records
            for item in record.raw_files
            if item.role == "fixture_source"
        )

        def reject_target(root: Path, relative: str):
            if relative == target:
                raise FilesystemPolicyError("SPECIAL_FILE_KIND_REJECTED")
            return read_authoritative_file(root, relative)

        with mock.patch(
            "specchoice_measurement.preflight.read_authoritative_file",
            side_effect=reject_target,
            create=True,
        ):
            result = self.preflight(self.payload())
        self.assertEqual(result.status, "invalid_preflight")
        self.assertEqual(result.parsed_predictions, ())
        self.assertIn(
            "EVIDENCE_SOURCE_UNKNOWN",
            {item.code for item in result.diagnostics},
        )

    def test_public_preflight_reuses_one_descriptor_read_per_fixture(self) -> None:
        source_paths = {
            raw_file.path
            for record in self.batch.records
            for raw_file in record.raw_files
            if raw_file.role == "fixture_source"
        }
        original = preflight.read_authoritative_file
        observed: list[str] = []

        def counted(root: Path, relative: str):
            if relative in source_paths:
                observed.append(relative)
            return original(root, relative)

        with mock.patch("specchoice_measurement.preflight.read_authoritative_file", side_effect=counted):
            result = self.preflight(self.payload())
        self.assertEqual(result.status, "valid_preflight")
        self.assertEqual(observed, sorted(source_paths))


if __name__ == "__main__":
    unittest.main()
