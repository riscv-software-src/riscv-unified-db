# SPDX-License-Identifier: BSD-3-Clause-Clear
"""TDD contract for isolated Phase 2 scoring semantics."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes
from specchoice_measurement.adapter import build_pr2164_adapter_batch, build_pr2164_v6_adapter_batch
from specchoice_measurement.cli import _fixture_span
from specchoice_measurement.diagnostics import Diagnostic
from specchoice_measurement.preflight import preflight_prediction_batch
from specchoice_measurement.scoring import (
    score_prediction_batch,
    validate_v5_span_population,
    validate_v6_span_population,
)
from specchoice_measurement.strict_json import _validate_span


class MeasurementScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiment_root = Path(__file__).parents[1]
        self.bundle = self.experiment_root / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        self.batch = build_pr2164_adapter_batch(
            authority_path=self.experiment_root / "phase2/source-authority-v13-historical.json",
            bundle_root=self.bundle,
            rules_path=self.experiment_root / "config/measurement/pr2164-adapter-rules-v1.json",
            revocation_path=self.experiment_root / "receipts/fixture-closure-revocation-v2.json",
        )
        self.assertTrue(self.batch.valid)
        self.golden_path = self.experiment_root / "fixtures/measurement/golden-predictions-v2.json"

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

    def v6_preflight(self, batch, payload):
        return preflight_prediction_batch(
            raw=canonical_json_bytes(payload), adapter_batch=batch, ingress="current-v3",
        )

    def golden_payload(self) -> dict[str, object]:
        raw = self.golden_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(raw, canonical_json_bytes(payload))
        self.assertEqual(payload["adapter_batch_sha256"], self.batch.adapter_batch_sha256)
        return payload

    def test_v5_span_population_is_frozen(self) -> None:
        golden = json.loads((self.experiment_root / "fixtures/measurement/golden-predictions-v3.json").read_text())
        self.assertEqual(validate_v5_span_population(golden), 8)
        golden["score_bearing_span_count"] = 7
        with self.assertRaisesRegex(ValueError, "V5_SPAN_POPULATION_INVALID"):
            validate_v5_span_population(golden)

    def test_v6_metrics_are_eight_eight_six_s_and_three(self) -> None:
        batch = self.v6_batch()
        self.assertTrue(batch.valid)
        payload = self.v6_payload(batch)
        preflight = self.v6_preflight(batch, payload)
        result = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")

        self.assertEqual(preflight.status, "valid_preflight")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.metrics.as_dict(), {
            "disposition": {"denominator": 8, "numerator": 8},
            "evidence_integrity": {"denominator": 10, "numerator": 10},
            "identity": {"denominator": 6, "numerator": 6},
            "negative_controls": {"denominator": 3, "numerator": 3},
            "surfacing": {"denominator": 8, "numerator": 8},
        })

    def test_v6_one_invalid_span_decrements_only_the_evidence_numerator(self) -> None:
        batch = self.v6_batch()
        payload = self.v6_payload(batch)
        target = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_DIRECT_CACHE_BLOCK")
        target["adjudication"]["evidence_spans"][0]["text"] = "semantically plausible but byte-inexact"

        preflight = self.v6_preflight(batch, payload)
        result = score_prediction_batch(adapter_batch=batch, preflight=preflight, mode="formal")

        self.assertEqual(preflight.status, "valid_preflight")
        self.assertEqual(result.status, "completed_with_warnings")
        self.assertEqual(result.metrics.as_dict()["evidence_integrity"], {"numerator": 9, "denominator": 10})
        self.assertEqual(result.metrics.as_dict()["surfacing"], {"numerator": 8, "denominator": 8})
        self.assertEqual(result.metrics.as_dict()["disposition"], {"numerator": 8, "denominator": 8})
        self.assertEqual([item.code for item in result.diagnostics], ["EVIDENCE_SPAN_INTEGRITY_FAILED"])

    def test_v6_duplicate_adjacent_and_multi_spans_each_count_in_s(self) -> None:
        batch = self.v6_batch()
        payload = self.v6_payload(batch)
        target = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_CSR_RW_MTVEC_ACCESS")
        span = target["adjudication"]["evidence_spans"][0]
        source = next(
            raw_file
            for record in batch.records
            if record.fixture_id == target["fixture_id"]
            for raw_file in record.raw_files
            if raw_file.role == "fixture_source"
        )
        raw = (self.bundle / source.path).read_bytes()
        adjacent = {
            "dimension": "surface",
            "source_path": source.path,
            "source_sha256": source.sha256,
            "start_byte": span["end_byte"],
            "end_byte": span["end_byte"] + 1,
            "text": raw[span["end_byte"]:span["end_byte"] + 1].decode("utf-8"),
        }
        target["adjudication"]["evidence_spans"].extend([deepcopy(span), adjacent])
        alternate_golden = {
            "score_bearing_span_count": 12,
            "outcomes": [
                {"evidence_spans": item["adjudication"]["evidence_spans"]}
                for item in payload["predictions"]
            ],
        }
        self.assertEqual(validate_v6_span_population(alternate_golden), 12)
        alternate_batch = replace(batch, score_bearing_span_count=12)

        result = score_prediction_batch(
            adapter_batch=alternate_batch,
            preflight=self.v6_preflight(alternate_batch, payload),
            mode="formal",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.metrics.as_dict()["evidence_integrity"], {"numerator": 12, "denominator": 12})

    def test_v6_span_population_and_candidate_identity_are_tamper_checked(self) -> None:
        batch = self.v6_batch()
        payload = self.v6_payload(batch)
        candidate = next(item for item in payload["predictions"] if item["fixture_id"] == "NEG_EXT_GATED_PBMTE")
        candidate["adjudication"]["proposed_name"] = "PBMTE"
        leaked = score_prediction_batch(
            adapter_batch=batch,
            preflight=self.v6_preflight(batch, payload),
            mode="formal",
        )
        self.assertEqual(leaked.status, "invalid_score")
        self.assertIn("CANDIDATE_IDENTITY_LEAKAGE", {item.code for item in leaked.diagnostics})

        payload = self.v6_payload(batch)
        next(item for item in payload["predictions"] if item["fixture_id"] == "POS_DIRECT_NUM_PMP")["adjudication"]["evidence_spans"].clear()
        tampered = score_prediction_batch(
            adapter_batch=batch,
            preflight=self.v6_preflight(batch, payload),
            mode="formal",
        )
        self.assertEqual(tampered.metrics, None)
        self.assertIn("EVIDENCE_SPANS_REQUIRED", {item.code for item in tampered.diagnostics})

    def required_diagnostic_oracles(self) -> dict[str, object]:
        path = self.experiment_root / "fixtures/measurement/adversarial/required-diagnostics-v2.json"
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(raw, canonical_json_bytes(payload))
        return payload

    def preflight(self, payload: object):
        return preflight_prediction_batch(
            raw=canonical_json_bytes(payload), adapter_batch=self.batch, ingress="current-v1"
        )

    def mutate_for_oracle(self, payload: dict[str, object], oracle_id: str) -> None:
        by_fixture = {item["fixture_id"]: item for item in payload["predictions"]}
        positive = by_fixture["POS_CSR_RW_MTVEC_ACCESS"]
        candidate = by_fixture["CAND_WARL_FIXED_LEGAL_SET"]
        negative = by_fixture["NEG_EXT_GATED_PBMTE"]
        target_span = positive["adjudication"]["evidence_spans"][0]
        negative_span = _fixture_span(self.batch, "NEG_EXT_GATED_PBMTE")
        mutations = {
            "accepted-parameter-name-missing": lambda: positive["adjudication"].update(proposed_name=None),
            "candidate-not-surfaced": lambda: candidate["adjudication"].update(
                surfaced=False, parameter_status=None, evidence_spans=[]
            ),
            "candidate-accepted": lambda: candidate["adjudication"].update(parameter_status="accept"),
            "candidate-review": lambda: candidate["adjudication"].update(parameter_status="review"),
            "positive-not-surfaced": lambda: positive["adjudication"].update(
                surfaced=False, parameter_status=None, proposed_name=None, evidence_spans=[]
            ),
            "positive-classified-out": lambda: positive["adjudication"].update(parameter_status="classify_out"),
            "negative-accepted": lambda: negative["adjudication"].update(
                surfaced=True,
                parameter_status="accept",
                proposed_name="PBMTE",
                evidence_spans=[deepcopy(negative_span)],
            ),
            "negative-review": lambda: negative["adjudication"].update(
                surfaced=True,
                parameter_status="review",
                proposed_name=None,
                evidence_spans=[deepcopy(negative_span)],
            ),
            "evidence-empty": lambda: positive["adjudication"].update(evidence_spans=[]),
            "evidence-source-changed": lambda: target_span.update(source_sha256="0" * 64),
            "evidence-empty-range": lambda: target_span.update(end_byte=0),
            "evidence-text-mismatch": lambda: target_span.update(text="changed"),
        }
        mutations[oracle_id]()

    def test_exact_all_eleven_golden_outcomes_keep_dimensions_independent(self) -> None:
        preflight = self.preflight(self.golden_payload())
        result = score_prediction_batch(adapter_batch=self.batch, preflight=preflight, mode="formal")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(len(result.case_outcomes), 11)
        self.assertEqual(result.metrics.as_dict(), {
            "disposition": {"denominator": 7, "numerator": 7},
            "evidence_integrity": {"denominator": 7, "numerator": 7},
            "identity": {"denominator": 6, "numerator": 6},
            "surfacing": {"denominator": 7, "numerator": 7},
        })
        outcomes = {item.fixture_id: item for item in result.case_outcomes}
        self.assertTrue(all(outcomes[record.fixture_id].surfacing_correct for record in self.batch.records))
        self.assertTrue(all(outcomes[record.fixture_id].disposition_correct for record in self.batch.records))
        self.assertTrue(all(outcomes[record.fixture_id].evidence_integrity for record in self.batch.records))
        for record in self.batch.records:
            if record.category == "positive":
                self.assertEqual(outcomes[record.fixture_id].identity_outcome, "exact")
        candidate = outcomes["CAND_WARL_FIXED_LEGAL_SET"]
        self.assertEqual(candidate.actual_status, "classify_out")
        self.assertIsNone(candidate.proposed_name)
        self.assertTrue(candidate.disposition_correct)

    def test_candidate_must_surface_then_classify_out(self) -> None:
        variants = (
            (False, None, "CANDIDATE_NOT_SURFACED"),
            (True, "accept", "CANDIDATE_ACCEPTED_AS_PARAMETER"),
            (True, "review", "CANDIDATE_LEFT_UNRESOLVED"),
        )
        for surfaced, status, code in variants:
            payload = self.golden_payload()
            candidate = next(item for item in payload["predictions"] if item["fixture_id"] == "CAND_WARL_FIXED_LEGAL_SET")
            candidate["adjudication"]["surfaced"] = surfaced
            candidate["adjudication"]["parameter_status"] = status
            if not surfaced:
                candidate["adjudication"]["evidence_spans"] = []
            with self.subTest(code=code):
                result = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(payload), mode="formal")
                self.assertIn(code, {item.code for item in result.diagnostics})
                self.assertEqual(result.metrics, None)

    def test_invalid_or_diagnostic_only_preflight_never_emits_formal_metrics(self) -> None:
        payload = self.golden_payload()
        payload["predictions"] = payload["predictions"][:-1]
        invalid = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(payload), mode="formal")
        diagnostic = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(self.golden_payload()), mode="diagnostic_only")

        self.assertEqual((invalid.status, invalid.metrics), ("invalid_preflight", None))
        self.assertEqual((diagnostic.status, diagnostic.metrics), ("diagnostic_only", None))

    def test_name_warning_preserves_semantics_and_matches_structured_oracle(self) -> None:
        payload = self.golden_payload()
        positive = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_CSR_RW_MTVEC_ACCESS")
        positive["adjudication"]["proposed_name"] = None

        result = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(payload), mode="formal")
        oracle = next(
            item
            for item in self.required_diagnostic_oracles()["oracles"]
            if item["id"] == "accepted-parameter-name-missing"
        )

        self.assertEqual(result.status, "completed_with_warnings")
        self.assertEqual(result.metrics.as_dict()["identity"], {"numerator": 5, "denominator": 6})
        self.assertEqual(result.metrics.as_dict()["surfacing"], {"numerator": 7, "denominator": 7})
        self.assertEqual(result.metrics.as_dict()["disposition"], {"numerator": 7, "denominator": 7})
        self.assertEqual([item.as_dict() for item in result.diagnostics], oracle["expected_diagnostics"])

    def test_every_required_diagnostic_oracle_is_complete_and_exact(self) -> None:
        required_fields = {
            "code", "severity", "fixture_id", "finding_id", "field", "occurrence", "expected", "observed", "source_sha256"
        }
        for oracle in self.required_diagnostic_oracles()["oracles"]:
            with self.subTest(oracle=oracle["id"]):
                self.assertEqual(set(oracle["expected_diagnostics"][0]), required_fields)
                payload = self.golden_payload()
                self.mutate_for_oracle(payload, oracle["id"])
                result = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(payload), mode="formal")
                expected = oracle["expected_diagnostics"][0]
                observed = next(item.as_dict() for item in result.diagnostics if item.code == expected["code"])
                self.assertEqual(observed, expected)

    def test_exact_duplicate_and_adjacent_spans_remain_distinct(self) -> None:
        payload = self.golden_payload()
        positive = next(item for item in payload["predictions"] if item["fixture_id"] == "POS_CSR_RW_MTVEC_ACCESS")
        span = positive["adjudication"]["evidence_spans"][0]
        source = next(
            raw_file
            for record in self.batch.records
            if record.fixture_id == "POS_CSR_RW_MTVEC_ACCESS"
            for raw_file in record.raw_files
            if raw_file.role == "fixture_source" and raw_file.sha256 == span["source_sha256"]
        )
        raw = (self.bundle / source.path).read_bytes()
        adjacent = {
            "source_sha256": source.sha256,
            "start_byte": span["end_byte"],
            "end_byte": span["end_byte"] + 1,
            "text": raw[span["end_byte"] : span["end_byte"] + 1].decode("utf-8"),
        }
        positive["adjudication"]["evidence_spans"] = [deepcopy(span), deepcopy(span), adjacent]

        preflight = self.preflight(payload)
        result = score_prediction_batch(adapter_batch=self.batch, preflight=preflight, mode="formal")

        self.assertEqual(preflight.diagnostics, ())
        self.assertEqual(preflight.parsed_predictions[5]["adjudication"]["evidence_spans"], [span, span, adjacent])
        self.assertEqual(result.status, "completed")
        self.assertTrue(next(item for item in result.case_outcomes if item.fixture_id == "POS_CSR_RW_MTVEC_ACCESS").evidence_integrity)

    def test_invalid_utf8_boundary_is_rejected_without_repair(self) -> None:
        record = next(item for item in self.batch.records if item.fixture_id == "POS_DIRECT_CACHE_BLOCK")
        source = next(
            raw_file
            for raw_file in record.raw_files
            if any(byte >= 128 for byte in (self.bundle / raw_file.path).read_bytes())
        )
        raw = (self.bundle / source.path).read_bytes()
        boundary = next(index for index, byte in enumerate(raw) if byte >= 128)
        diagnostics: list[Diagnostic] = []
        parsed = _validate_span(
            {
            "source_sha256": source.sha256,
            "start_byte": boundary + 1,
            "end_byte": boundary + 3,
            "text": "--",
            },
            fixture_id=record.fixture_id,
            field="adjudication.evidence_spans[0]",
            source_by_sha256={source.sha256: raw},
            allowed_source_sha256=frozenset({source.sha256}),
            diagnostics=diagnostics,
        )

        self.assertIsNone(parsed)
        self.assertEqual([item.code for item in diagnostics], ["EVIDENCE_TEXT_NOT_UTF8"])

    def test_case_and_warning_diagnostic_order_are_input_order_independent(self) -> None:
        payload = self.golden_payload()
        for fixture_id in ("POS_CSR_RW_MTVEC_ACCESS", "POS_DIRECT_CACHE_BLOCK"):
            next(item for item in payload["predictions"] if item["fixture_id"] == fixture_id)["adjudication"]["proposed_name"] = None
        reversed_payload = deepcopy(payload)
        reversed_payload["predictions"].reverse()

        left = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(payload), mode="formal")
        right = score_prediction_batch(adapter_batch=self.batch, preflight=self.preflight(reversed_payload), mode="formal")

        self.assertEqual(left.as_dict(), right.as_dict())


if __name__ == "__main__":
    unittest.main()
