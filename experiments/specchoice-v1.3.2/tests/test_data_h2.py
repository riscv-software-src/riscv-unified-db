# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from specchoice_data.h2 import (
    EligibilityAudit,
    H2ValidationError,
    audit_phase3_counts_v1,
    build_h2_review_packet_v1,
    build_h2_review_readiness_v1,
    derive_data_eligibility_v1,
    render_data_eligibility_markdown_v1,
    render_h2_review_markdown_v1,
    validate_h2_data_decision_v1,
    validate_phase3_chain_v1,
    validate_phase3_data_authority_v1,
    write_phase3_data_authority_v1,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes


class DataH2Tests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.experiment = Path(__file__).parents[1]

    @staticmethod
    def _hash(value: dict[str, object], field: str) -> dict[str, object]:
        payload = {key: item for key, item in value.items() if key != field}
        return {**payload, field: sha256_bytes(canonical_json_bytes(payload))}

    def _audit_material(self) -> dict[str, object]:
        return {
            "auxiliary_case_ids": [],
            "held_out_dispositions": {},
            "invariants": {
                "demonstration_leakage_free": True,
                "example_isolation": True,
                "family_isolation": True,
                "frozen_inventory_unchanged": True,
                "provenance_valid": True,
                "reviews_complete": True,
            },
            "metamorphic_directions": {
                "choice_space_origin": "excluded_unavailable",
                "hardware_software_authority": "excluded_unavailable",
                "normative_note_example": "excluded_unavailable",
                "warl_fixed_legal_set": "excluded_unavailable",
            },
            "pair_dispositions": {"PAIR_1": "approved_qualifying"},
            "relevance_dispositions": {},
            "strict_case_ids": [],
        }

    def _packet(self) -> tuple[dict[str, object], dict[str, object], EligibilityAudit, dict[str, object]]:
        chain = {
            "audit_material": self._audit_material(),
            "bindings": {"candidate_inventory_sha256": "a" * 64, "phase3_chain_sha256": "b" * 64},
            "invariants": self._audit_material()["invariants"],
        }
        audit = audit_phase3_counts_v1(chain)
        eligibility = derive_data_eligibility_v1(audit)
        packet = build_h2_review_packet_v1(chain=chain, audit=audit, eligibility=eligibility)
        markdown = render_h2_review_markdown_v1(packet)
        readiness = build_h2_review_readiness_v1(packet=packet, markdown=markdown)
        return packet, readiness, audit, eligibility

    def _decision(self, packet: dict[str, object], readiness: dict[str, object], *, aggregate: str = "approved") -> dict[str, object]:
        disposition = "approved" if aggregate == "approved" else aggregate
        payload = {
            "acknowledgments": [
                {"category": category, "disposition": disposition, "rationale": "Reviewed against the exact packet."}
                for category in packet["required_acknowledgment_categories"]
            ],
            "aggregate_disposition": aggregate,
            "aggregate_rationale": "The recomputed counts and deterministic Red result are trustworthy.",
            "attestation": "This approval covers data feasibility only and grants no retrieval, model, publication, or Phase 4 execution authority.",
            "packet_sha256": packet["packet_sha256"],
            "readiness_sha256": readiness["readiness_sha256"],
            "reviewer_id": "human-reviewer",
            "schema_version": "h2-data-decision-v1",
            "signature": "Human Reviewer",
            "timestamp_utc": "2026-08-04T08:00:00Z",
        }
        return self._hash(payload, "decision_sha256")

    def test_h2_readiness_recomputes_every_upstream_identity(self) -> None:
        chain = validate_phase3_chain_v1(experiment_root=self.experiment)
        audit = audit_phase3_counts_v1(chain)
        eligibility = derive_data_eligibility_v1(audit)
        packet = build_h2_review_packet_v1(chain=chain, audit=audit, eligibility=eligibility)
        readiness = build_h2_review_readiness_v1(packet=packet, markdown=render_h2_review_markdown_v1(packet))
        self.assertEqual(eligibility["eligibility_status"], "red_required")
        self.assertEqual(readiness["status"], "ready_for_human")

    def test_counts_keep_invalid_disputed_excluded_and_auxiliary_separate(self) -> None:
        chain = {"audit_material": self._audit_material()}
        material = chain["audit_material"]
        material["pair_dispositions"] = {
            "PAIR_APPROVED": "approved_qualifying",
            "PAIR_DISPUTED": "disputed",
            "PAIR_EXCLUDED": "excluded",
            "PAIR_INVALID": "structurally_invalid",
            "PAIR_REUSED": "reused_nonqualifying",
        }
        material["held_out_dispositions"] = {
            "AUX": "approved_auxiliary",
            "H_DISPUTED": "disputed",
            "H_EXCLUDED": "excluded",
            "H_INVALID": "structurally_invalid",
            "STRICT": "approved_strict",
        }
        material["strict_case_ids"] = ["STRICT"]
        material["auxiliary_case_ids"] = ["AUX"]
        audit = audit_phase3_counts_v1(chain)
        self.assertEqual(audit.ids["qualifying_pairs"], ("PAIR_APPROVED",))
        self.assertEqual(audit.ids["pair_disputed"], ("PAIR_DISPUTED",))
        self.assertEqual(audit.ids["held_out_auxiliary"], ("AUX",))
        self.assertTrue(audit.terminal_buckets_disjoint)

    def test_thresholds_use_only_approved_unique_qualifying_pairs_and_strict_cases(self) -> None:
        green = EligibilityAudit(
            ids={"qualifying_pairs": tuple(f"P{i}" for i in range(6)), "strict_approved": tuple(f"S{i}" for i in range(10))},
            invariants={"all_non_count_invariants": True}, terminal_buckets_disjoint=True,
        )
        yellow = EligibilityAudit(
            ids={"qualifying_pairs": tuple(f"P{i}" for i in range(4)), "strict_approved": tuple(f"S{i}" for i in range(6))},
            invariants={"all_non_count_invariants": True}, terminal_buckets_disjoint=True,
        )
        self.assertEqual(derive_data_eligibility_v1(green)["eligibility_status"], "green_eligible")
        self.assertEqual(derive_data_eligibility_v1(yellow)["eligibility_status"], "yellow_eligible")

    def test_insufficient_complete_data_is_red_not_invalid(self) -> None:
        audit = audit_phase3_counts_v1({"audit_material": self._audit_material()})
        report = derive_data_eligibility_v1(audit)
        self.assertEqual(report["eligibility_status"], "red_required")
        self.assertEqual(report["qualifying_pair_count"], 1)
        self.assertEqual(report["strict_case_count"], 0)
        self.assertFalse(report["model_experiment_authorized"])

    def test_any_frozen_input_change_invalidates_h2(self) -> None:
        family_path = "data/preregistration/family-registry-v1.json"
        mutated = deepcopy(validate_phase3_chain_v1(experiment_root=self.experiment)["artifacts"][family_path])
        mutated["registry_sha256"] = "0" * 64
        with self.assertRaisesRegex(H2ValidationError, "FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION"):
            validate_phase3_chain_v1(experiment_root=self.experiment, overrides={family_path: mutated})

    def test_missing_payload_differs_from_complete_incomplete_h2(self) -> None:
        packet, readiness, _, _ = self._packet()
        with self.assertRaisesRegex(H2ValidationError, "H2_DECISION_INCOMPLETE"):
            validate_h2_data_decision_v1(decision={"aggregate_disposition": "incomplete"}, packet=packet, readiness=readiness)
        decision = self._decision(packet, readiness, aggregate="incomplete")
        self.assertEqual(validate_h2_data_decision_v1(decision=decision, packet=packet, readiness=readiness), decision)

    def test_disputed_or_incomplete_h2_cannot_authorize_data_root(self) -> None:
        packet, readiness, audit, eligibility = self._packet()
        for aggregate in ("disputed", "incomplete"):
            with self.subTest(aggregate=aggregate), tempfile.TemporaryDirectory() as directory:
                decision = self._decision(packet, readiness, aggregate=aggregate)
                with self.assertRaisesRegex(H2ValidationError, "H2_APPROVAL_REQUIRED"):
                    write_phase3_data_authority_v1(
                        output_root=Path(directory), chain={"bindings": packet["bindings"]}, audit=audit,
                        eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
                    )

    def test_h2_decision_binds_exact_packet_and_readiness(self) -> None:
        packet, readiness, _, _ = self._packet()
        decision = self._decision(packet, readiness)
        decision["packet_sha256"] = "0" * 64
        decision = self._hash(decision, "decision_sha256")
        with self.assertRaisesRegex(H2ValidationError, "H2_DECISION_BINDING_INVALID"):
            validate_h2_data_decision_v1(decision=decision, packet=packet, readiness=readiness)

    def test_data_authority_requires_current_approved_h2(self) -> None:
        packet, readiness, audit, eligibility = self._packet()
        decision = self._decision(packet, readiness)
        with tempfile.TemporaryDirectory() as directory:
            result = write_phase3_data_authority_v1(
                output_root=Path(directory), chain={"bindings": packet["bindings"]}, audit=audit,
                eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
            )
            authority = result["authority"]
            self.assertEqual(validate_phase3_data_authority_v1(
                authority=authority, chain={"bindings": packet["bindings"]}, decision=decision,
                eligibility=eligibility,
            ), authority)

    def test_data_authority_contains_exactly_one_eligibility_status(self) -> None:
        packet, readiness, audit, eligibility = self._packet()
        decision = self._decision(packet, readiness)
        with tempfile.TemporaryDirectory() as directory:
            authority = write_phase3_data_authority_v1(
                output_root=Path(directory), chain={"bindings": packet["bindings"]}, audit=audit,
                eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
            )["authority"]
        self.assertEqual(authority["eligibility_status"], "red_required")
        self.assertTrue({"green_eligible", "yellow_eligible"}.isdisjoint(authority))

    def test_eligibility_is_not_phase4_execution_authority(self) -> None:
        _, _, _, eligibility = self._packet()
        self.assertFalse(eligibility["retrieval_authorized"])
        self.assertFalse(eligibility["model_experiment_authorized"])
        self.assertFalse(eligibility["external_publication_authorized"])
        self.assertTrue(eligibility["phase4_decision_required"])

    def test_exact_resume_accepts_identical_and_rejects_divergent(self) -> None:
        packet, readiness, audit, eligibility = self._packet()
        decision = self._decision(packet, readiness)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_phase3_data_authority_v1(
                output_root=root, chain={"bindings": packet["bindings"]}, audit=audit,
                eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
            )
            second = write_phase3_data_authority_v1(
                output_root=root, chain={"bindings": packet["bindings"]}, audit=audit,
                eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
            )
            self.assertEqual(first["authority"], second["authority"])
            report_path = root / "reports/h2/data-eligibility-v1.json"
            report_path.write_bytes(b"divergent\n")
            with self.assertRaisesRegex(H2ValidationError, "DATA_AUTHORITY_WRITE_INVALID"):
                write_phase3_data_authority_v1(
                    output_root=root, chain={"bindings": packet["bindings"]}, audit=audit,
                    eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
                )

    def test_version_change_requires_stop_log_increment_and_symmetric_rerun(self) -> None:
        packet, readiness, audit, eligibility = self._packet()
        decision = self._decision(packet, readiness)
        with tempfile.TemporaryDirectory() as directory:
            result = write_phase3_data_authority_v1(
                output_root=Path(directory), chain={"bindings": packet["bindings"]}, audit=audit,
                eligibility=eligibility, decision=decision, packet=packet, readiness=readiness,
            )
            changed = deepcopy(result["authority"])
            changed["bindings"] = {**changed["bindings"], "candidate_inventory_sha256": "f" * 64}
            changed = self._hash(changed, "authority_sha256")
            with self.assertRaisesRegex(H2ValidationError, "FROZEN_INPUT_CHANGE_REQUIRES_NEW_EXPERIMENT_VERSION"):
                validate_phase3_data_authority_v1(
                    authority=changed, chain={"bindings": packet["bindings"]}, decision=decision,
                    eligibility=eligibility,
                )

    def test_eligibility_markdown_is_projection_of_canonical_json(self) -> None:
        _, _, _, eligibility = self._packet()
        markdown = render_data_eligibility_markdown_v1(eligibility)
        self.assertIn(eligibility["report_sha256"].encode(), markdown)
        self.assertIn(b"NOT FINAL PHASE 4 EXECUTION AUTHORITY", markdown)


if __name__ == "__main__":
    unittest.main()
