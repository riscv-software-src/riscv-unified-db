# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import unittest

from specchoice_data.splits import (
    SplitValidationError,
    audit_held_out_demonstration_leakage_v1,
    audit_prototype_reuse_v1,
    derive_split_manifest_v1,
    invalidate_registry_dependents_v1,
    validate_family_registry_v1,
    validate_split_manifest_v1,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes


class DataSplitTests(unittest.TestCase):
    def _registry(self) -> dict[str, object]:
        payload = {
            "assignments": [
                {"item_id": "HELD_A", "item_version": "v1", "primary_family": "other_family", "secondary_tags": []},
                {"item_id": "HELD_B", "item_version": "v1", "primary_family": "warl_legal_set", "secondary_tags": ["boundary"]},
                {"item_id": "PAIR_A", "item_version": "phase3-pair-candidate-v1", "primary_family": "warl_legal_set", "secondary_tags": []},
            ],
            "bindings": {"candidate_inventory_sha256": "a" * 64, "pair_review_decision_sha256": "b" * 64},
            "families": [
                {
                    "definition": "A disjoint held-out family used only by tests.",
                    "exclusion_criteria": ["WARL legal-set cases."],
                    "family_id": "other_family",
                    "inclusion_criteria": ["The item is not a WARL legal-set case."],
                    "review_state": "approved",
                },
                {
                    "definition": "Implementation-selected versus fixed legal-value sets.",
                    "exclusion_criteria": ["Constraints that do not define a legal-value set."],
                    "family_id": "warl_legal_set",
                    "inclusion_criteria": ["The choice object is a legal-value set."],
                    "review_state": "approved",
                },
            ],
            "registry_version": "v1",
            "schema_version": "family-registry-v1",
        }
        return {**payload, "registry_sha256": sha256_bytes(canonical_json_bytes(payload))}

    def _pair(self, pair_id: str = "PAIR_A", positive: str = "POS_A", contrast: str = "NEG_A") -> dict[str, object]:
        def side(example_id: str, start: int) -> dict[str, object]:
            return {
                "example_id": example_id,
                "source_sha256": str(start + 1) * 64,
                "spans": [{"start_byte": start, "end_byte": start + 10}],
            }

        return {"candidate_id": pair_id, "sides": [side(positive, 0), side(contrast, 20)]}

    def _held_out(self) -> list[dict[str, object]]:
        return [
            {"example_id": "HELD_EX_A", "item_id": "HELD_A", "item_version": "v1", "review_state": "approved", "source_sha256": "c" * 64, "spans": [{"start_byte": 0, "end_byte": 10}]},
            {"example_id": "HELD_EX_B", "item_id": "HELD_B", "item_version": "v1", "review_state": "approved", "source_sha256": "d" * 64, "spans": [{"start_byte": 0, "end_byte": 10}]},
        ]

    def test_registry_requires_closed_definitions_before_assignments(self) -> None:
        registry = self._registry()
        del registry["families"][0]["inclusion_criteria"]
        with self.assertRaisesRegex(SplitValidationError, "FAMILY_REGISTRY_INVALID"):
            validate_family_registry_v1(registry, candidate_inventory_sha256="a" * 64, pair_review_decision_sha256="b" * 64)

    def test_primary_family_is_exactly_one_registered_id(self) -> None:
        for invalid in (None, "", "ambiguous", ["warl_legal_set"], "missing"):
            with self.subTest(invalid=invalid):
                registry = self._registry()
                registry["assignments"][0]["primary_family"] = invalid
                with self.assertRaisesRegex(SplitValidationError, "PRIMARY_FAMILY_INVALID"):
                    validate_family_registry_v1(registry, candidate_inventory_sha256="a" * 64, pair_review_decision_sha256="b" * 64)

    def test_registry_change_invalidates_all_dependents(self) -> None:
        registry = validate_family_registry_v1(self._registry(), candidate_inventory_sha256="a" * 64, pair_review_decision_sha256="b" * 64)
        dependents = [{"artifact_id": "packet", "registry_version": "old", "registry_sha256": registry["registry_sha256"]}, {"artifact_id": "split", "registry_version": "v1", "registry_sha256": "0" * 64}]
        diagnostics = invalidate_registry_dependents_v1(registry=registry, dependents=dependents)
        self.assertEqual([item.code for item in diagnostics], ["FAMILY_REGISTRY_DEPENDENT_STALE"] * 2)

    def test_count_eligible_pairs_cannot_reuse_example_or_span_identity(self) -> None:
        first = self._pair()
        reused = self._pair("PAIR_B", positive="POS_A", contrast="NEG_B")
        reused["sides"][1]["source_sha256"] = first["sides"][1]["source_sha256"]
        reused["sides"][1]["spans"] = first["sides"][1]["spans"]
        audit = audit_prototype_reuse_v1([first, reused])
        self.assertEqual(audit.qualifying_pair_ids, ("PAIR_A",))
        self.assertEqual(audit.reused_pair_ids, ("PAIR_B",))
        self.assertEqual({item.code for item in audit.diagnostics}, {"PROTOTYPE_EXAMPLE_ID_REUSED", "PROTOTYPE_SOURCE_SPAN_REUSED"})

    def test_split_is_pure_function_of_approved_examples_and_primary_families(self) -> None:
        registry = self._registry()
        first = derive_split_manifest_v1(registry=registry, prototype_pairs=[self._pair()], held_out_items=self._held_out(), demonstrations=[])
        second = derive_split_manifest_v1(registry=registry, prototype_pairs=[self._pair()], held_out_items=list(reversed(self._held_out())), demonstrations=[])
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(validate_split_manifest_v1(first, registry=registry, prototype_pairs=[self._pair()], held_out_items=self._held_out(), demonstrations=[]), first)

    def test_example_overlap_and_strict_family_overlap_fail_closed(self) -> None:
        held = self._held_out()
        held[0]["example_id"] = "POS_A"
        manifest = derive_split_manifest_v1(registry=self._registry(), prototype_pairs=[self._pair()], held_out_items=held, demonstrations=[])
        self.assertIn("HELD_OUT_EXAMPLE_OVERLAP", {item["code"] for item in manifest["diagnostics"]})
        self.assertFalse(manifest["ready"])

    def test_family_overlap_routes_only_to_auxiliary(self) -> None:
        manifest = derive_split_manifest_v1(registry=self._registry(), prototype_pairs=[self._pair()], held_out_items=self._held_out(), demonstrations=[])
        self.assertEqual(manifest["strict_case_ids"], ["HELD_A"])
        self.assertEqual(manifest["auxiliary_case_ids"], ["HELD_B"])

    def test_no_held_out_passage_identity_in_demonstrations(self) -> None:
        held = self._held_out()
        demonstrations = [{"source_sha256": "c" * 64, "start_byte": 0, "end_byte": 10}]
        diagnostics = audit_held_out_demonstration_leakage_v1(held_out_items=held, demonstrations=demonstrations)
        self.assertEqual([item.code for item in diagnostics], ["HELD_OUT_PASSAGE_IN_DEMONSTRATION"])

    def test_empty_strict_core_is_valid_red_evidence(self) -> None:
        registry = self._registry()
        registry["assignments"] = [registry["assignments"][2]]
        payload = {key: registry[key] for key in registry if key != "registry_sha256"}
        registry["registry_sha256"] = sha256_bytes(canonical_json_bytes(payload))
        manifest = derive_split_manifest_v1(registry=registry, prototype_pairs=[self._pair()], held_out_items=[], demonstrations=[])
        self.assertTrue(manifest["ready"])
        self.assertEqual(manifest["strict_case_ids"], [])
        self.assertEqual(manifest["auxiliary_case_ids"], [])


if __name__ == "__main__":
    unittest.main()
