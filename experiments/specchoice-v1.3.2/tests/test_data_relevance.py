# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from specchoice_data.relevance import (
    REQUIRED_METAMORPHIC_DIRECTIONS,
    RelevanceValidationError,
    build_relevance_metamorphic_packet_v1,
    build_relevance_metamorphic_readiness_v1,
    validate_metamorphic_registry_v1,
    validate_pair_relevance_registry_v1,
    validate_relevance_metamorphic_decision_v1,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes


class DataRelevanceTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.bindings = {
            "candidate_inventory_sha256": "a" * 64,
            "family_registry_sha256": "b" * 64,
            "family_registry_version": "family-registry-v1.0.0",
            "family_split_decision_sha256": "c" * 64,
            "pair_review_decision_sha256": "d" * 64,
            "split_manifest_sha256": "e" * 64,
        }
        self.pairs = {
            "PAIR_1": {
                "discriminating_axes": ["authority", "choice_space_origin"],
                "shared_structure": ["WARL", "legal_set"],
            }
        }
        self.targets = {
            "AUX_1": {
                "choice_object": "legal_set",
                "decisive_axes": ["choice_space_origin"],
                "key_structure": ["WARL"],
            },
            "STRICT_1": {
                "choice_object": "legal_set",
                "decisive_axes": ["authority"],
                "key_structure": ["WARL"],
            },
        }
        self.split = {
            "auxiliary_case_ids": ["AUX_1"],
            "strict_case_ids": ["STRICT_1"],
        }

    @staticmethod
    def _hash(value: dict[str, object], field: str) -> dict[str, object]:
        payload = {key: item for key, item in value.items() if key != field}
        return {**payload, field: sha256_bytes(canonical_json_bytes(payload))}

    def _row(self, case_id: str, *, no_relevant: bool = False) -> dict[str, object]:
        target = self.targets[case_id]
        common = {
            "case_id": case_id,
            "choice_object": target["choice_object"],
            "decisive_axes": target["decisive_axes"],
            "key_structure": target["key_structure"],
            "rationale": "Human preregistration rationale.",
        }
        if no_relevant:
            return {**common, "no_relevant_pair": True}
        return {**common, "relevant_pair_ids": ["PAIR_1"]}

    def _relevance(self, *, strict_rows=None, auxiliary_rows=None) -> dict[str, object]:
        strict = [self._row("STRICT_1")] if strict_rows is None else strict_rows
        auxiliary = [self._row("AUX_1")] if auxiliary_rows is None else auxiliary_rows
        value = {
            "auxiliary_rows": auxiliary,
            "bindings": self.bindings,
            "registry_version": "pair-relevance-registry-v1.0.0",
            "schema_version": "pair-relevance-registry-v1",
            "strict_pairhit_eligible_case_ids": [
                item["case_id"] for item in strict if "relevant_pair_ids" in item
            ],
            "strict_rows": strict,
        }
        return self._hash(value, "registry_sha256")

    def _unavailable_metamorphic(self, relevance_sha256: str) -> dict[str, object]:
        bindings = {**self.bindings, "relevance_registry_sha256": relevance_sha256}
        value = {
            "bindings": bindings,
            "count_eligible": False,
            "directions": [
                {
                    "availability": "unavailable",
                    "count_eligible": False,
                    "direction_id": direction,
                    "rationale": "No frozen metamorphic candidate exists in candidate inventory v1.",
                    "version": "metamorphic-direction-v1.0.0",
                }
                for direction in REQUIRED_METAMORPHIC_DIRECTIONS
            ],
            "registry_version": "metamorphic-registry-v1.0.0",
            "schema_version": "metamorphic-registry-v1",
        }
        return self._hash(value, "registry_sha256")

    def _available_direction(self, root: Path, direction: str) -> dict[str, object]:
        source = root / "source.txt"
        source.write_text("authoritative source text\n", encoding="utf-8")
        raw = source.read_bytes()
        axis = {
            "choice_space_origin": "choice_space_origin",
            "warl_fixed_legal_set": "choice_space_origin",
            "hardware_software_authority": "authority",
            "normative_note_example": "final_status",
        }[direction]
        delta = {
            "axis": axis,
            "from": "implementation_selected",
            "to": "ISA_fixed",
            "final_status": {"from": "accept", "to": "classify_out"},
        }
        authoritative = {
            "claim_to_span": [{"axis": "authority", "span_ids": ["source-span"]}],
            "final_status": "accept",
            "frame": {
                "authority": "implementation",
                "choice_object": "legal_set",
                "choice_space_origin": "implementation_selected",
            },
            "source_kind": "authoritative",
            "source_path": "source.txt",
            "source_sha256": sha256_bytes(raw),
            "spans": [
                {
                    "end_byte": len(raw),
                    "span_id": "source-span",
                    "start_byte": 0,
                    "text": raw.decode("utf-8"),
                }
            ],
        }
        synthetic = {
            "authored_by": "human-reviewer",
            "based_on_authoritative_span_id": "source-span",
            "claim_to_span": [{"axis": "authority", "span_ids": ["synthetic-replacement"]}],
            "count_eligible": False,
            "edit_rationale": "One controlled textual replacement for testing only.",
            "expected_delta": delta,
            "final_status": "classify_out",
            "frame": {
                "authority": "ISA",
                "choice_object": "legal_set",
                "choice_space_origin": "ISA_fixed",
            },
            "human_approval_ref": "review/test-only",
            "model_generated": False,
            "original_text": raw.decode("utf-8"),
            "replacement_text": "controlled replacement text\n",
            "source_kind": "human_synthetic",
        }
        return {
            "availability": "available",
            "candidate_id": f"META_{direction.upper()}",
            "count_eligible": False,
            "direction_id": direction,
            "expected_delta": delta,
            "source_a": authoritative,
            "source_b": synthetic,
            "version": "metamorphic-direction-v1.0.0",
        }

    def _metamorphic_with_available(self, root: Path) -> dict[str, object]:
        relevance = self._relevance()
        bindings = {**self.bindings, "relevance_registry_sha256": relevance["registry_sha256"]}
        value = {
            "bindings": bindings,
            "count_eligible": False,
            "directions": [self._available_direction(root, item) for item in REQUIRED_METAMORPHIC_DIRECTIONS],
            "registry_version": "metamorphic-registry-v1.0.0",
            "schema_version": "metamorphic-registry-v1",
        }
        return self._hash(value, "registry_sha256")

    def _validate_relevance(self, value: dict[str, object]) -> dict[str, object]:
        return validate_pair_relevance_registry_v1(
            value,
            split_manifest=self.split,
            approved_pairs=self.pairs,
            expected_bindings=self.bindings,
            case_targets=self.targets,
        )

    def test_relevance_covers_every_strict_case_exactly_once(self) -> None:
        self.assertEqual(self._validate_relevance(self._relevance())["strict_pairhit_eligible_case_ids"], ["STRICT_1"])
        missing = self._relevance(strict_rows=[])
        missing["strict_pairhit_eligible_case_ids"] = []
        missing = self._hash(missing, "registry_sha256")
        with self.assertRaisesRegex(RelevanceValidationError, "RELEVANCE_STRICT_COVERAGE_INVALID"):
            self._validate_relevance(missing)

    def test_no_relevant_pair_requires_rationale_and_is_not_pairhit_eligible(self) -> None:
        row = self._row("STRICT_1", no_relevant=True)
        value = self._relevance(strict_rows=[row])
        self.assertEqual(self._validate_relevance(value)["strict_pairhit_eligible_case_ids"], [])
        row["rationale"] = ""
        value = self._relevance(strict_rows=[row])
        with self.assertRaisesRegex(RelevanceValidationError, "RELEVANCE_ROW_INVALID"):
            self._validate_relevance(value)

    def test_relevance_requires_shared_structure_and_decisive_axis(self) -> None:
        bad_pairs = deepcopy(self.pairs)
        bad_pairs["PAIR_1"]["shared_structure"] = ["unrelated"]
        with self.assertRaisesRegex(RelevanceValidationError, "RELEVANCE_PAIR_MISMATCH"):
            validate_pair_relevance_registry_v1(
                self._relevance(), split_manifest=self.split, approved_pairs=bad_pairs,
                expected_bindings=self.bindings, case_targets=self.targets,
            )

    def test_relevance_has_no_rank_field(self) -> None:
        value = self._relevance()
        value["strict_rows"][0]["rank"] = 1
        value = self._hash(value, "registry_sha256")
        with self.assertRaisesRegex(RelevanceValidationError, "RELEVANCE_RANK_FIELD_FORBIDDEN"):
            self._validate_relevance(value)

    def test_auxiliary_relevance_is_separate(self) -> None:
        value = self._validate_relevance(self._relevance())
        self.assertEqual([row["case_id"] for row in value["auxiliary_rows"]], ["AUX_1"])
        self.assertEqual(value["strict_pairhit_eligible_case_ids"], ["STRICT_1"])

    def test_empty_strict_core_has_empty_complete_registry(self) -> None:
        self.split = {"auxiliary_case_ids": [], "strict_case_ids": []}
        self.targets = {}
        value = self._relevance(strict_rows=[], auxiliary_rows=[])
        self.assertEqual(self._validate_relevance(value)["strict_rows"], [])

    def test_exactly_four_required_metamorphic_directions(self) -> None:
        relevance = self._relevance()
        value = self._unavailable_metamorphic(relevance["registry_sha256"])
        self.assertEqual(
            [item["direction_id"] for item in validate_metamorphic_registry_v1(
                value, expected_bindings=value["bindings"], accepted_root=None,
                frozen_metamorphic_candidate_ids=set(), dataset_member_ids=set(),
            )["directions"]],
            list(REQUIRED_METAMORPHIC_DIRECTIONS),
        )
        value["directions"].pop()
        value = self._hash(value, "registry_sha256")
        with self.assertRaisesRegex(RelevanceValidationError, "METAMORPHIC_DIRECTION_SET_INVALID"):
            validate_metamorphic_registry_v1(
                value, expected_bindings=value["bindings"], accepted_root=None,
                frozen_metamorphic_candidate_ids=set(), dataset_member_ids=set(),
            )

    def test_authoritative_sides_reuse_descriptor_bound_span_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = self._metamorphic_with_available(root)
            ids = {item["candidate_id"] for item in value["directions"]}
            validate_metamorphic_registry_v1(
                value, expected_bindings=value["bindings"], accepted_root=root,
                frozen_metamorphic_candidate_ids=ids, dataset_member_ids=set(),
            )
            (root / "source.txt").write_text("mutated\n", encoding="utf-8")
            with self.assertRaisesRegex(RelevanceValidationError, "METAMORPHIC_SOURCE_INVALID"):
                validate_metamorphic_registry_v1(
                    value, expected_bindings=value["bindings"], accepted_root=root,
                    frozen_metamorphic_candidate_ids=ids, dataset_member_ids=set(),
                )

    def test_human_synthetic_side_requires_exact_edit_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = self._metamorphic_with_available(root)
            value["directions"][0]["source_b"]["human_approval_ref"] = ""
            value = self._hash(value, "registry_sha256")
            ids = {item["candidate_id"] for item in value["directions"]}
            with self.assertRaisesRegex(RelevanceValidationError, "METAMORPHIC_SYNTHETIC_INVALID"):
                validate_metamorphic_registry_v1(
                    value, expected_bindings=value["bindings"], accepted_root=root,
                    frozen_metamorphic_candidate_ids=ids, dataset_member_ids=set(),
                )

    def test_synthetic_or_model_generated_text_cannot_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = self._metamorphic_with_available(root)
            value["directions"][0]["source_b"]["model_generated"] = True
            value["directions"][0]["source_b"]["count_eligible"] = True
            value = self._hash(value, "registry_sha256")
            ids = {item["candidate_id"] for item in value["directions"]}
            with self.assertRaisesRegex(RelevanceValidationError, "METAMORPHIC_SYNTHETIC_INVALID"):
                validate_metamorphic_registry_v1(
                    value, expected_bindings=value["bindings"], accepted_root=root,
                    frozen_metamorphic_candidate_ids=ids, dataset_member_ids=set(),
                )

    def test_expected_delta_is_directed_and_version_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = self._metamorphic_with_available(root)
            value["directions"][0]["source_a"], value["directions"][0]["source_b"] = (
                value["directions"][0]["source_b"], value["directions"][0]["source_a"]
            )
            value = self._hash(value, "registry_sha256")
            ids = {item["candidate_id"] for item in value["directions"]}
            with self.assertRaisesRegex(RelevanceValidationError, "METAMORPHIC_DIRECTION_INVALID"):
                validate_metamorphic_registry_v1(
                    value, expected_bindings=value["bindings"], accepted_root=root,
                    frozen_metamorphic_candidate_ids=ids, dataset_member_ids=set(),
                )

    def test_packet_readiness_and_complete_human_decision(self) -> None:
        relevance = self._validate_relevance(self._relevance())
        metamorphic = self._unavailable_metamorphic(relevance["registry_sha256"])
        metamorphic = validate_metamorphic_registry_v1(
            metamorphic, expected_bindings=metamorphic["bindings"], accepted_root=None,
            frozen_metamorphic_candidate_ids=set(), dataset_member_ids={"PAIR_1"},
        )
        packet = build_relevance_metamorphic_packet_v1(relevance=relevance, metamorphic=metamorphic)
        readiness = build_relevance_metamorphic_readiness_v1(packet=packet)
        payload = {
            "aggregate_disposition": "approved",
            "aggregate_rationale": "The empty held-out registry and four unavailable directions accurately reflect the frozen inventory.",
            "attestation": "I reviewed every preregistered relevance row and required metamorphic direction without retrieval or model output.",
            "direction_reviews": [
                {"direction_id": item, "disposition": "excluded", "rationale": "No frozen candidate exists."}
                for item in REQUIRED_METAMORPHIC_DIRECTIONS
            ],
            "packet_sha256": packet["packet_sha256"],
            "readiness_sha256": readiness["readiness_sha256"],
            "relevance_reviews": [
                {"case_id": item["case_id"], "disposition": "approved", "rationale": "Judgment is correct."}
                for item in [*relevance["strict_rows"], *relevance["auxiliary_rows"]]
            ],
            "reviewer_id": "human-reviewer",
            "schema_version": "relevance-metamorphic-review-decision-v1",
            "signature": "Human Reviewer",
            "timestamp_utc": "2026-08-03T23:30:00Z",
        }
        decision = self._hash(payload, "decision_sha256")
        self.assertEqual(
            validate_relevance_metamorphic_decision_v1(
                decision=decision, packet=packet, readiness=readiness,
            ),
            decision,
        )


if __name__ == "__main__":
    unittest.main()
