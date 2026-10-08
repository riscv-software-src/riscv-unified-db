# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Phase-aware oracle: retain the legacy red cohort and require successor green."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import phase1_expected_red_oracle as legacy


SUCCESSOR_IDS = {
    "tests.test_fixture_closure.FixtureClosureTests.test_v5_executable_closure_and_candidate_entrypoints",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_builder_is_sorted_and_rejects_any_one_byte_drift",
    "tests.test_fixture_closure.FixtureClosureTests.test_v5_construction_decision_rejects_every_transitive_one_byte_drift_before_write",
    "tests.test_fixture_closure.FixtureClosureTests.test_v12_acceptance_and_cutover_entrypoints",
    "tests.test_fixture_closure.FixtureClosureTests.test_v5_registry_manifest_and_every_repair_payload_are_pre_freeze_committed_inputs",
    "tests.test_fixture_closure.FixtureClosureTests.test_v6_preflight_reconstructs_target_inventory_before_any_write",
    "tests.test_fixture_closure.FixtureClosureTests.test_v6_registry_is_a_complete_twenty_nine_file_inventory",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_exact_eleven_case_metric_population_contract",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_v5_outcome_contract_rejects_candidate_identity_leakage",
    "tests.test_measurement_scoring.MeasurementScoringTests.test_v5_span_population_is_frozen",
    "tests.test_measurement_h1.H1PublicContractTests.test_v5_h1_question_contract_is_exactly_seven_questions",
    "tests.test_measurement_h1.H1PacketTests.test_seven_question_h1_and_four_report_pipeline",
    "tests.test_measurement_h1.H1PacketTests.test_report_generation_rejects_one_byte_planning_or_predecessor_report_drift_before_write",
    "tests.test_source_contract.SourceContractTests.test_v4_authorization_is_append_only_classified_non_executable",
    "tests.test_fixture_closure.FixtureClosureTests.test_v5_rejection_is_exact_and_v5_mutators_fail_closed",
    "tests.test_fixture_closure.FixtureClosureTests.test_v6_future_target_inventory_is_typed_complete_and_occupancy_checked",
    "tests.test_fixture_closure.FixtureClosureTests.test_v6_registry_and_accepted_v3_transitive_inventories_are_reconstructed",
    "tests.test_fixture_closure.FixtureClosureTests.test_v6_v13_command_surface_is_real",
    "tests.test_fixture_closure.FixtureClosureTests.test_v13_human_decision_is_closed_self_hashed_and_request_bound",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v2_binds_clean_tool_env_exact_argv_and_real_git_blob_oid",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v2_rejects_tool_version_argv_environment_and_blob_oid_drift",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v2_is_exact_non_authorizing_history",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v3_freezes_authority_and_accepts_exact_historical_bytes",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v3_authority_binding_comes_from_freeze_tree",
    "tests.test_fixture_closure.FixtureClosureTests.test_public_v6_builder_rejects_semantically_invalid_authority_pre_state",
    "tests.test_fixture_closure.FixtureClosureTests.test_rooted_v6_proposal_rejects_copies_tamper_and_late_publish_collision_atomically",
    "tests.test_fixture_closure.FixtureClosureTests.test_v13_evidence_seam_rejects_invalid_or_reject_decisions_before_any_target_open",
    "tests.test_fixture_closure.FixtureClosureTests.test_v13_full_preflight_accepts_absent_or_exact_resume_and_rejects_divergent_occupancy",
    "tests.test_fixture_closure.FixtureClosureTests.test_v13_accepted_directory_and_pending_batch_are_byte_exact_resumable",
    "tests.test_fixture_closure.FixtureClosureTests.test_v13_activation_preflights_every_receipt_before_authority_replacement",
    "tests.test_measurement_h1.H1PacketTests.test_successor_public_cli_e2e_rejects_forged_adapter_formal_adversarial_and_packet",
    "tests.test_measurement_h1.H1PacketTests.test_successor_governance_validators_fail_closed_on_empty_inputs",
    "tests.test_measurement_h1.H1PacketTests.test_direct_decision_and_final_reports_reject_zero_upstream_bindings",
}

# These ten tests were introduced by the two semantic recovery commits.  Keep
# their exact discovery IDs explicit so they cannot silently leak back into the
# historical 72/150/145 oracle population.
RECOVERY_SEMANTIC_IDS = {
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_v6_golden_contract_contains_all_eleven_evidence_bound_outcomes",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_v6_adapter_closes_the_full_twenty_nine_file_semantic_population",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_v6_golden_spans_are_exact_semantic_bytes_and_candidates_bind_both_dimensions",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_v6_closed_controls_reject_unknown_keys_missing_mapping_and_twenty_ninth_raw_drift",
    "tests.test_measurement_parsing.MeasurementParsingTests.test_v3_closed_schema_rejects_unknown_keys_at_every_score_bearing_level",
    "tests.test_measurement_parsing.MeasurementParsingTests.test_v3_binds_schema_and_ingress_but_leaves_integrity_to_per_span_scoring",
    "tests.test_measurement_scoring.MeasurementScoringTests.test_v6_metrics_are_eight_eight_six_s_and_three",
    "tests.test_measurement_scoring.MeasurementScoringTests.test_v6_one_invalid_span_decrements_only_the_evidence_numerator",
    "tests.test_measurement_scoring.MeasurementScoringTests.test_v6_duplicate_adjacent_and_multi_spans_each_count_in_s",
    "tests.test_measurement_scoring.MeasurementScoringTests.test_v6_span_population_and_candidate_identity_are_tamper_checked",
}
SUCCESSOR_IDS |= RECOVERY_SEMANTIC_IDS
PHASE_02_20_IDS = {
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v4_bootstrap_has_no_self_dependency",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v4_binds_all_seventeen_post_closure_targets",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_pr2164_adapter_v4_binds_canonical_authority_and_materialized_raw_tree",
    "tests.test_measurement_attempts.MeasurementAttemptTests.test_fresh_v4_chain_is_deterministic_exact_resume_and_has_expected_metrics",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_binds_complete_seven_question_semantics_and_v4_identity",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_packet_and_readiness_contain_no_human_values",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_real_fresh_chain_rejects_each_canonical_forgery",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_fixed_packet_and_readiness_writers_are_decision_free_exact_resume",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_writers_repeat_full_gate_before_write_primitive",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v7_packet_writer_rejects_divergent_link_special_partial_and_race",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v6_decision_writer_is_fixed_path_and_preflight_rejects_hostile_target",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v6_decision_writer_revalidates_closure_and_authority_before_write",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v6_decision_distinguishes_missing_payload_from_complete_incomplete_judgment",
    "tests.test_measurement_h1.H1PacketTests.test_h1_v6_terminal_outputs_require_approved_decision",
    "tests.test_measurement_h1.H1PacketTests.test_validate_h1_review_readiness_v7_cli_is_registered_read_only_and_fail_closed",
    "tests.test_measurement_h1.H1PacketTests.test_render_h1_review_checkpoint_v7_cli_requires_no_write_and_persists_no_human_fields",
    "tests.test_measurement_h1.H1PacketTests.test_validate_h1_source_gold_decision_v6_cli_is_registered_read_only_and_fail_closed",
    "tests.test_measurement_h1.H1PacketTests.test_validate_approved_h1_terminal_v6_cli_is_registered_read_only_and_fail_closed",
    "tests.test_measurement_h1.H1PacketTests.test_v4_02_22_reports_are_approved_only_exact_resume_and_summary_is_downstream",
}
PHASE_02_20_HARDENING_IDS = {
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v4_rejects_schema_only_and_hostile_bootstrap_targets",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v4_writer_repeats_preflight_before_first_write",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v4_post_validation_does_not_reapply_bootstrap_absence",
    "tests.test_fixture_closure.FixtureClosureTests.test_accepted_v6_active_validator_rejects_lineage_and_materialized_raw_drift",
    "tests.test_fixture_closure.FixtureClosureTests.test_runtime_closure_v3_historical_rejects_truncated_or_mutated_receipt",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_pr2164_adapter_v4_rejects_unpublished_schema_only_closure_and_raw_drift",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_pr2164_adapter_v4_writer_exact_resume_divergence_and_fixed_path",
    "tests.test_measurement_adapter.MeasurementAdapterTests.test_pr2164_adapter_v4_writer_rejects_target_race_without_replacement",
    "tests.test_measurement_attempts.MeasurementAttemptTests.test_fresh_formal_v6_fixed_target_exact_resume_and_metrics",
    "tests.test_measurement_attempts.MeasurementAttemptTests.test_fresh_formal_v6_rejects_partial_symlink_divergence_race_and_task16_adapter",
    "tests.test_measurement_attempts.MeasurementAttemptTests.test_fresh_adversarial_v7_fixed_target_resume_divergence_and_race",
}
PHASE_02_20_IDS |= PHASE_02_20_HARDENING_IDS
SUCCESSOR_IDS |= PHASE_02_20_IDS

CURRENT_CODE_MODULES = (
    "tests.test_fixture_closure",
    "tests.test_measurement_adapter",
    "tests.test_measurement_attempts",
    "tests.test_measurement_h1",
)
CURRENT_CODE_RED_IDS = {
    test_id for test_id in legacy.RED_IDS
    if test_id.startswith("tests.test_fixture_closure.")
}


def main() -> int:
    loader = unittest.defaultTestLoader
    all_discovered = list(legacy._flatten(loader.discover("tests", top_level_dir=".")))
    discovered_ids = {test.id() for test in all_discovered}
    if (
        len(RECOVERY_SEMANTIC_IDS) != 10
        or len(PHASE_02_20_HARDENING_IDS) != 11
        or len(PHASE_02_20_IDS) != 30
        or not SUCCESSOR_IDS <= discovered_ids
    ):
        raise SystemExit("ORACLE_SUCCESSOR_DISCOVERY_CHANGED")
    discovered = [test for test in all_discovered if test.id() not in SUCCESSOR_IDS]
    focused = [test for test in legacy._flatten(unittest.TestSuite(loader.loadTestsFromName(name) for name in legacy.FOCUSED_MODULES)) if test.id() not in SUCCESSOR_IDS]
    if len(discovered) != 150 or len(focused) != 72:
        raise SystemExit("ORACLE_LEGACY_COHORT_CHANGED")
    # The 145 predecessor-green cases are a frozen partition fact, not a live
    # authority assertion.  Accepted-v6 intentionally supersedes several
    # predecessor current-authority/schema assumptions; re-running those tests
    # against the new authority would conflate historical evidence with the
    # successor state.  The exact five-method/six-outcome red signature remains
    # live below, while the explicit 02-20 cohort is the current-green gate.
    historical_green = [test for test in discovered if test.id() not in legacy.RED_IDS]
    if len(historical_green) != 145:
        raise SystemExit("ORACLE_LEGACY_GREEN_PARTITION_CHANGED")
    red, _ = legacy._run([test for test in discovered if test.id() in legacy.RED_IDS])
    if (
        red["tests_run"] != 5
        or len(red["failures"]) != 5
        or len(red["errors"]) != 1
        or red["skipped"]
        or red["expected_failures"]
        or red["unexpected_successes"]
        or legacy._normalized_outcomes(red) is None
    ):
        raise SystemExit("ORACLE_LEGACY_RED_CHANGED")
    current = list(legacy._flatten(unittest.TestSuite(
        loader.loadTestsFromName(name) for name in CURRENT_CODE_MODULES
    )))
    current_ids = {test.id() for test in current}
    if (
        len(current) != 116
        or len(current_ids) != 116
        or (current_ids & legacy.RED_IDS) != CURRENT_CODE_RED_IDS
        or not PHASE_02_20_IDS <= current_ids
    ):
        raise SystemExit("ORACLE_CURRENT_CODE_COHORT_CHANGED")
    current_green = [test for test in current if test.id() not in legacy.RED_IDS]
    if len(current_green) != 112:
        raise SystemExit("ORACLE_CURRENT_CODE_GREEN_PARTITION_CHANGED")
    return 0 if unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(current_green)
    ).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
