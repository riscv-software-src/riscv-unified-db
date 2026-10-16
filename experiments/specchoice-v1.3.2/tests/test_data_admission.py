# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from specchoice_data.admission import (
    DataAdmissionError,
    admit_pair_candidate_v1,
    freeze_candidate_inventory_v1,
    validate_candidate_inventory_v1,
)
from specchoice_data.review import (
    DataReviewError,
    build_pair_review_packet_v1,
    build_pair_review_readiness_v1,
    render_pair_review_markdown_v1,
    validate_pair_review_decision_v1,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_data.cli import require_phase2_local_closure
from specchoice_evidence.runtime_closure import (
    RuntimeClosureError,
    verify_phase2_lifecycle_successor_v1,
    verify_runtime_closure_v4_historical,
)
from specchoice_measurement.strict_json import decode_strict_json
from specchoice_data.worksheet import build_candidate_authoring_worksheet_v1


class DataAdmissionTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        experiment = Path(__file__).parents[1]
        self.schema_raw = (experiment / "config/data/phase3-data-schema-v1.json").read_bytes()
        self.fixture_root = Path(__file__).parent / "fixtures/data_preregistration/tracer"

    def _workspace(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory)
        candidates = root / "candidates"
        accepted = root / "accepted"
        (candidates / "pairs").mkdir(parents=True)
        (accepted / "fixtures/POS").mkdir(parents=True)
        (accepted / "fixtures/NEG").mkdir(parents=True)
        (accepted / "fixtures/POS/source.txt").write_bytes((self.fixture_root / "positive.txt").read_bytes())
        (accepted / "fixtures/NEG/source.txt").write_bytes((self.fixture_root / "contrast.txt").read_bytes())
        return candidates, accepted

    def _candidate(self, accepted: Path) -> dict[str, object]:
        def side(role: str, example_id: str, source_path: str, status: str, origin: str) -> dict[str, object]:
            raw = (accepted / source_path).read_bytes()
            text = raw.decode("utf-8")
            span_id = f"{role}-span-1"
            claims = [
                ("authority", "architecture"),
                ("choice_object", "mtvec access"),
                ("choice_space_origin", origin),
                ("final_status", status),
                ("rationale", f"Human-authored rationale for {role}."),
            ]
            return {
                "claims": [
                    {
                        "axis": axis,
                        "claim_id": f"{role}.{axis}",
                        "span_ids": [span_id],
                        "value": value,
                    }
                    for axis, value in claims
                ],
                "example_id": example_id,
                "role": role,
                "source_kind": "authoritative",
                "source_path": source_path,
                "source_sha256": sha256_bytes(raw),
                "spans": [
                    {
                        "end_byte": len(raw),
                        "span_id": span_id,
                        "start_byte": 0,
                        "text": text,
                    }
                ],
            }

        return {
            "candidate_id": "PAIR_MTVEC_ACCESS_V1",
            "candidate_kind": "pair",
            "presentation_order": ["positive", "contrast"],
            "relationship": {
                "discriminating_axes": ["choice_space_origin"],
                "expected_delta": {
                    "frame_axes": ["choice_space_origin"],
                    "final_status": {"from": "accept", "to": "classify_out"},
                },
                "rationale": "The origin of the choice space is the only intended contrast.",
                "shared_structure": ["same CSR", "same normative context"],
            },
            "schema_version": "phase3-pair-candidate-v1",
            "sides": [
                side("positive", "POS_MTVEC_ACCESS", "fixtures/POS/source.txt", "accept", "implementation"),
                side("contrast", "NEG_MTVEC_ENCODING", "fixtures/NEG/source.txt", "classify_out", "architecture"),
            ],
        }

    def _freeze(self, candidates: Path, accepted: Path) -> dict[str, object]:
        return self._freeze_value(candidates, self._candidate(accepted))

    def _freeze_value(self, candidates: Path, candidate: dict[str, object]) -> dict[str, object]:
        (candidates / "pairs/pair-mtvec.json").write_bytes(canonical_json_bytes(candidate))
        return freeze_candidate_inventory_v1(
            candidate_root=candidates,
            declarations=(("pairs/pair-mtvec.json", "pair"),),
            phase2_authority_sha256="a" * 64,
            h1_decision_sha256="b" * 64,
            schema_raw=self.schema_raw,
        )

    def _admit(self, candidates: Path, accepted: Path, inventory: dict[str, object]):
        return admit_pair_candidate_v1(
            candidate_root=candidates,
            candidate_path="pairs/pair-mtvec.json",
            inventory=inventory,
            accepted_root=accepted,
            schema_raw=self.schema_raw,
        )

    def test_phase2_lifecycle_successor_closes_tracking_transition(self) -> None:
        gate = require_phase2_local_closure()

        self.assertTrue(gate["approved"])
        self.assertEqual(
            gate["authority_sha256"],
            "0ff1bb7c22a11003595e59b6c616400b21218121639835f7529837085f2c6bae",
        )
        self.assertEqual(
            gate["decision_file_sha256"],
            "cac3039340d778198e8bbb3f565d9adc9009183624e81aa9b4dcd31c7a504599",
        )

    def test_phase2_predecessor_is_historical_and_tamper_evident(self) -> None:
        experiment = Path(__file__).parents[1]
        repository = experiment.parents[1]
        receipt = decode_strict_json(
            (experiment / "receipts/runtime-executable-closure-v4.json").read_bytes()
        )

        validated = verify_runtime_closure_v4_historical(receipt, repository)
        self.assertEqual(
            validated["freeze_commit"],
            "47ffaa1c5be6c058a3316cf7f8c56260c1e6ebde",
        )

        mutated = deepcopy(receipt)
        mutated["entries"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeClosureError, "RUNTIME_CLOSURE_V4_HISTORY_MISMATCH"
        ):
            verify_runtime_closure_v4_historical(mutated, repository)

    def test_phase2_lifecycle_successor_rejects_alternate_evidence(self) -> None:
        experiment = Path(__file__).parents[1]
        repository = experiment.parents[1]
        successor = decode_strict_json(
            (experiment / "receipts/phase2-lifecycle-successor-v1.json").read_bytes()
        )

        verified = verify_phase2_lifecycle_successor_v1(successor, repository)
        self.assertEqual(verified, successor)

        mutated = deepcopy(successor)
        mutated["evidence_bindings"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            RuntimeClosureError, "PHASE2_LIFECYCLE_SUCCESSOR_MISMATCH"
        ):
            verify_phase2_lifecycle_successor_v1(mutated, repository)

    def test_candidate_authoring_worksheet_is_complete_and_decision_free(self) -> None:
        gate = require_phase2_local_closure()
        worksheet = build_candidate_authoring_worksheet_v1(
            accepted_root=gate["accepted_root"],
            registry_name="fixture-registry-pr2164-v6.json",
            schema_raw=self.schema_raw,
            phase2_authority_sha256=gate["authority_sha256"],
            h1_decision_sha256=gate["decision_sha256"],
        )

        self.assertEqual(len(worksheet["accepted_files"]), 29)
        self.assertEqual(
            len({item["fixture_id"] for item in worksheet["accepted_files"]}), 11
        )
        self.assertEqual(
            sum(item["role"] == "fixture_source" for item in worksheet["accepted_files"]),
            11,
        )
        self.assertTrue(
            {"reviewer_id", "signature", "aggregate_disposition"}.isdisjoint(worksheet)
        )
        self.assertEqual(
            worksheet["human_action"]["resume_signal"],
            "FREEZE CANDIDATE INVENTORY V1",
        )

    def test_tracer_freezes_admits_renders_and_validates_explicit_human_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates, accepted = self._workspace(directory)
            inventory = self._freeze(candidates, accepted)
            admission = self._admit(candidates, accepted, inventory)

            self.assertTrue(admission.valid)
            self.assertEqual(admission.diagnostics, ())
            self.assertEqual([entry["path"] for entry in inventory["entries"]], ["pairs/pair-mtvec.json"])

            packet = build_pair_review_packet_v1(admission=admission, inventory=inventory)
            markdown = render_pair_review_markdown_v1(packet)
            readiness = build_pair_review_readiness_v1(packet=packet, markdown=markdown)
            decision_payload = {
                "aggregate_disposition": "approved",
                "aggregate_rationale": "Both sides and their directed relationship are supported by the cited bytes.",
                "attestation": "I reviewed every side and relationship field without machine-generated semantic completion.",
                "packet_sha256": packet["packet_sha256"],
                "readiness_sha256": readiness["readiness_sha256"],
                "relationship_review": {
                    "disposition": "approved",
                    "rationale": "The relationship is a controlled minimal contrast.",
                },
                "reviewer_id": "human-reviewer-1",
                "schema_version": "pair-review-decision-v1",
                "side_reviews": [
                    {"disposition": "approved", "rationale": "Positive side is supported.", "role": "positive"},
                    {"disposition": "approved", "rationale": "Contrast side is supported.", "role": "contrast"},
                ],
                "signature": "Human Reviewer",
                "timestamp_utc": "2026-08-03T20:00:00Z",
            }
            decision = {
                **decision_payload,
                "decision_sha256": sha256_bytes(canonical_json_bytes(decision_payload)),
            }

            validated = validate_pair_review_decision_v1(
                decision=decision,
                packet=packet,
                readiness=readiness,
            )

        self.assertEqual(validated, decision)
        self.assertIn("PAIR_MTVEC_ACCESS_V1", markdown.decode("utf-8"))

    def test_tracer_rejects_unlisted_or_mutated_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates, accepted = self._workspace(directory)
            inventory = self._freeze(candidates, accepted)

            (accepted / "fixtures/POS/source.txt").write_bytes(b"mutated\n")
            mutated_source = self._admit(candidates, accepted, inventory)
            self.assertIn("SOURCE_BYTES_CHANGED", {item.code for item in mutated_source.diagnostics})

            (accepted / "fixtures/POS/source.txt").unlink()
            os.symlink(self.fixture_root / "positive.txt", accepted / "fixtures/POS/source.txt")
            symlinked_source = self._admit(candidates, accepted, inventory)
            self.assertIn("SOURCE_PATH_REJECTED", {item.code for item in symlinked_source.diagnostics})

            (candidates / "pairs/unlisted.json").write_bytes(canonical_json_bytes(self._candidate(accepted)))
            unlisted = admit_pair_candidate_v1(
                candidate_root=candidates,
                candidate_path="pairs/unlisted.json",
                inventory=inventory,
                accepted_root=accepted,
                schema_raw=self.schema_raw,
            )
            self.assertIn("CANDIDATE_INVENTORY_CHANGED", {item.code for item in unlisted.diagnostics})

            candidate_path = candidates / "pairs/pair-mtvec.json"
            candidate_path.write_bytes(candidate_path.read_bytes() + b" ")
            mutated_candidate = self._admit(candidates, accepted, inventory)
            self.assertIn("CANDIDATE_INVENTORY_CHANGED", {item.code for item in mutated_candidate.diagnostics})

            escaped = admit_pair_candidate_v1(
                candidate_root=candidates,
                candidate_path="../outside.json",
                inventory=inventory,
                accepted_root=accepted,
                schema_raw=self.schema_raw,
            )
            self.assertIn("CANDIDATE_PATH_REJECTED", {item.code for item in escaped.diagnostics})

        mutations = {
            "empty_span": lambda value: value["sides"][0]["spans"][0].update({"end_byte": 0}),
            "unmapped_claim": lambda value: value["sides"][0]["claims"][0].update({"span_ids": ["missing-span"]}),
            "same_example": lambda value: value["sides"][1].update({"example_id": value["sides"][0]["example_id"]}),
            "missing_axis": lambda value: value["sides"][0]["claims"].pop(),
            "unknown_key": lambda value: value.update({"machine_guess": "forbidden"}),
        }
        expected = {
            "empty_span": "SOURCE_SPAN_INVALID",
            "unmapped_claim": "CLAIM_MAPPING_INVALID",
            "same_example": "PAIR_EXAMPLE_IDS_NOT_DISTINCT",
            "missing_axis": "CLAIM_AXIS_MISSING",
            "unknown_key": "CANDIDATE_SCHEMA_INVALID",
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                candidates, accepted = self._workspace(directory)
                candidate = self._candidate(accepted)
                mutate(candidate)
                inventory = self._freeze_value(candidates, candidate)
                result = self._admit(candidates, accepted, inventory)
                self.assertIn(expected[name], {item.code for item in result.diagnostics})

        with tempfile.TemporaryDirectory() as directory:
            candidates, _ = self._workspace(directory)
            (candidates / "pairs/pair-mtvec.json").write_bytes(
                b'{"candidate_kind":"pair","candidate_kind":"pair"}\n'
            )
            with self.assertRaisesRegex(DataAdmissionError, "CANDIDATE_INVENTORY_INPUT_INVALID"):
                freeze_candidate_inventory_v1(
                    candidate_root=candidates,
                    declarations=(("pairs/pair-mtvec.json", "pair"),),
                    phase2_authority_sha256="a" * 64,
                    h1_decision_sha256="b" * 64,
                    schema_raw=self.schema_raw,
                )

    def test_tracer_never_infers_human_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates, accepted = self._workspace(directory)
            inventory = self._freeze(candidates, accepted)
            admission = self._admit(candidates, accepted, inventory)
            packet = build_pair_review_packet_v1(admission=admission, inventory=inventory)
            markdown = render_pair_review_markdown_v1(packet)
            readiness = build_pair_review_readiness_v1(packet=packet, markdown=markdown)

        forbidden = {
            "aggregate_disposition",
            "attestation",
            "relationship_review",
            "reviewer_id",
            "side_reviews",
            "signature",
            "timestamp_utc",
        }
        self.assertTrue(forbidden.isdisjoint(readiness))
        with self.assertRaisesRegex(DataReviewError, "PAIR_REVIEW_DECISION_INCOMPLETE"):
            validate_pair_review_decision_v1(
                decision={
                    "schema_version": "pair-review-decision-v1",
                    "packet_sha256": packet["packet_sha256"],
                    "readiness_sha256": readiness["readiness_sha256"],
                    "aggregate_disposition": "approved",
                },
                packet=packet,
                readiness=readiness,
            )

    def test_complete_inventory_is_frozen_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates, accepted = self._workspace(directory)
            inventory = self._freeze(candidates, accepted)

            self.assertEqual(
                validate_candidate_inventory_v1(
                    candidate_root=candidates,
                    inventory=inventory,
                    schema_raw=self.schema_raw,
                ),
                inventory,
            )

            (candidates / "pairs/unlisted.json").write_bytes(
                canonical_json_bytes(self._candidate(accepted))
            )
            with self.assertRaisesRegex(
                DataAdmissionError, "CANDIDATE_INVENTORY_CHANGED"
            ):
                validate_candidate_inventory_v1(
                    candidate_root=candidates,
                    inventory=inventory,
                    schema_raw=self.schema_raw,
                )

    def test_invalid_candidates_remain_auditable_and_cannot_be_backfilled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates, accepted = self._workspace(directory)
            invalid_candidate = self._candidate(accepted)
            invalid_candidate["sides"][0]["spans"][0]["end_byte"] = 0
            inventory = self._freeze_value(candidates, invalid_candidate)

            invalid = self._admit(candidates, accepted, inventory)
            self.assertFalse(invalid.valid)
            self.assertEqual(invalid.candidate_id, "PAIR_MTVEC_ACCESS_V1")
            self.assertIn(
                "SOURCE_SPAN_INVALID", {item.code for item in invalid.diagnostics}
            )

            (candidates / "pairs/replacement.json").write_bytes(
                canonical_json_bytes(self._candidate(accepted))
            )
            with self.assertRaisesRegex(
                DataAdmissionError, "CANDIDATE_INVENTORY_CHANGED"
            ):
                validate_candidate_inventory_v1(
                    candidate_root=candidates,
                    inventory=inventory,
                    schema_raw=self.schema_raw,
                )


if __name__ == "__main__":
    unittest.main()
