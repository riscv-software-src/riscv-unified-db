# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Exact-set guards for the frozen PR #2164 fixture custody input."""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import specchoice_evidence.cli as cli_module
from specchoice_evidence.bundle import (
    BundleError,
    accept_fixture_closure_candidate,
    construct_fixture_closure_candidate,
    fixture_construction_candidate_audit,
    verify_candidate,
)
from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.filesystem import FilesystemPolicyError, read_authoritative_file
from specchoice_evidence.cli import _v4_predecessor_material
from specchoice_evidence.verify import _bundle_artifacts, _raw_artifacts, _root_digest, verify_accepted_bundle
from specchoice_evidence.source_contract import (
    _v4_inventory,
    _require_v4_git_commit,
    _validate_v4_previous_supersession,
    FixtureRegistryError,
    SourceContractProposalError,
    require_fixture_closure_local_acceptance_authorization,
    validate_fixture_construction_decision_v4,
    build_source_contract_proposal_v5,
    render_v5_rejected_pre_authorization_receipt,
    validate_v5_rejected_pre_authorization_receipt,
    validate_source_contract_proposal_v5,
    validate_fixture_registry,
    verify_fixture_registry_git,
)
from specchoice_evidence.runtime_closure import (
    RuntimeClosureError,
    _git_blob_binding,
    _git_bound_entry,
    _require_clean_tool_environment,
    _tool_identities,
    _referenced_runtime_paths_v2,
    build_runtime_closure,
    future_target_inventory_v6,
    validate_future_target_occupancy_v6,
    verify_runtime_closure,
    verify_runtime_closure_v2,
    verify_runtime_closure_v3,
    verify_runtime_closure_v4,
    validate_runtime_closure_v4_bootstrap_targets,
    validate_runtime_closure_v2_supersession,
    build_runtime_closure_v4,
    future_target_inventory_v7,
    verify_runtime_closure_v3_historical,
)
from specchoice_evidence.successor import (
    SuccessorProtocolError,
    _ACCEPTANCE_DECISION_RELATIVE,
    _AUDIT_RELATIVE,
    _CANDIDATE_RELATIVE,
    _DECISION_RELATIVE,
    _PACKET_RELATIVE,
    _REQUEST_RELATIVE,
    _accepted_projection_v6,
    _preflight_exact_file,
    _validate_recorded_proposal_inputs,
    _verify_exact_accepted_v6,
    _occupied_v13_targets,
    build_source_contract_proposal_v6,
    preflight_local_acceptance_request_v13,
    preflight_activate_pending_source_cutover_v13,
    preflight_prepare_pending_source_cutover_v13,
    validate_local_acceptance_decision_v13,
    accepted_v6_active_bound_paths,
    validate_accepted_v6_active_authority,
    validate_source_contract_proposal_v6,
    validate_v13_evidence_chain,
    write_source_contract_proposal_packet_v6,
)


class FixtureClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.experiment = Path(__file__).resolve().parents[1]
        self.registry = json.loads(
            (self.experiment / "config/fixture-registry-pr2164-v1.json").read_text(encoding="utf-8")
        )
        self.repository = self.experiment.parents[1]

    def test_frozen_registry_proves_exactly_eleven_fixtures_and_twenty_eight_blobs(self) -> None:
        normalized = validate_fixture_registry(self.registry)
        self.assertEqual(normalized["fixture_count"], 11)
        self.assertEqual(normalized["raw_file_count"], 28)
        self.assertEqual(
            [entry["fixture_id"] for entry in normalized["fixtures"]],
            sorted(entry["fixture_id"] for entry in normalized["fixtures"]),
        )
        verify_fixture_registry_git(self.registry, self.repository)

    def test_registry_fails_closed_for_empty_missing_extra_duplicate_and_bad_role(self) -> None:
        for mutation, code in (
            (lambda value: value.update({"fixtures": []}), "FIXTURE_REGISTRY_EMPTY"),
            (lambda value: value["fixtures"].pop(), "FIXTURE_SET_MISMATCH"),
            (lambda value: value["fixtures"].append(copy.deepcopy(value["fixtures"][0])), "FIXTURE_DUPLICATE"),
            (lambda value: value["fixtures"][0]["files"].pop(), "FIXTURE_FILE_SET_MISMATCH"),
            (lambda value: value["fixtures"][0]["files"][0].update({"role": "gold"}), "FIXTURE_ROLE_MISMATCH"),
        ):
            invalid = copy.deepcopy(self.registry)
            mutation(invalid)
            with self.subTest(code=code), self.assertRaisesRegex(FixtureRegistryError, code):
                validate_fixture_registry(invalid)

    def test_registry_fails_closed_for_escape_and_git_byte_drift(self) -> None:
        invalid = copy.deepcopy(self.registry)
        invalid["fixtures"][0]["files"][0]["upstream_path"] = "../escape.txt"
        with self.assertRaisesRegex(FixtureRegistryError, "PATH_ESCAPE_DETECTED"):
            validate_fixture_registry(invalid)

        invalid = copy.deepcopy(self.registry)
        invalid["fixtures"][0]["files"][0]["raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(FixtureRegistryError, "FIXTURE_RAW_SHA256_MISMATCH"):
            verify_fixture_registry_git(invalid, self.repository)

    def test_v5_executable_closure_and_candidate_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracked = root / "tracked.json"
            tracked.write_bytes(b"frozen\n")
            closure = {
                "entries": [{
                    "byte_length": len(tracked.read_bytes()),
                    "path": "tracked.json",
                    "sha256": sha256_bytes(tracked.read_bytes()),
                }],
                "schema_version": "runtime-executable-closure-v1",
            }
            self.assertEqual(verify_runtime_closure(closure, root)["schema_version"], closure["schema_version"])
            tracked.write_bytes(b"drifted\n")
            with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_ENTRY_MISMATCH"):
                verify_runtime_closure(closure, root)

        commands = cli_module.build_parser()._subparsers._group_actions[0].choices
        self.assertTrue({
            "write-source-contract-proposal-v5",
            "validate-source-contract-proposal-v5",
            "validate-fixture-construction-decision-v5",
            "build-fixture-construction-candidate-v5",
            "validate-fixture-candidate-v5",
            "validate-runtime-executable-closure",
        }.issubset(commands))

    def test_runtime_closure_builder_is_sorted_and_rejects_any_one_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_bytes(b"a\n")
            (root / "b.txt").write_bytes(b"b\n")
            closure = build_runtime_closure(root, ["b.txt", "a.txt"])
            self.assertEqual([item["path"] for item in closure["entries"]], ["a.txt", "b.txt"])
            verify_runtime_closure(closure, root)
            (root / "b.txt").write_bytes(b"B\n")
            with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_ENTRY_MISMATCH"):
                verify_runtime_closure(closure, root)

    def test_runtime_closure_v4_bootstrap_has_no_self_dependency(self) -> None:
        receipt = "experiments/specchoice-v1.3.2/receipts/runtime-executable-closure-v4.json"
        self.assertNotIn(receipt, {entry["path"] for entry in future_target_inventory_v7()})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                build_runtime_closure_v4.__name__, "build_runtime_closure_v4"
            )
            self.assertFalse((root / receipt).exists())

    def test_runtime_closure_v4_binds_all_seventeen_post_closure_targets(self) -> None:
        targets = future_target_inventory_v7()
        self.assertEqual(len(targets), 17)
        self.assertEqual(targets, sorted(targets, key=lambda entry: entry["path"]))
        self.assertEqual({entry["kind"] for entry in targets}, {"file"})

    def test_runtime_closure_v4_rejects_schema_only_and_hostile_bootstrap_targets(self) -> None:
        with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_V4_INVALID"):
            verify_runtime_closure_v4(
                {"schema_version": "runtime-executable-closure-v4"}, self.repository
            )

        target = future_target_inventory_v7()[0]["path"]
        for kind in ("file", "directory", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                occupied = root / target
                occupied.parent.mkdir(parents=True)
                if kind == "file":
                    occupied.write_bytes(b"occupied\n")
                elif kind == "directory":
                    occupied.mkdir()
                else:
                    occupied.symlink_to("missing")
                with self.assertRaisesRegex(
                    RuntimeClosureError,
                    "RUNTIME_CLOSURE_V4_BOOTSTRAP_TARGET_OCCUPIED",
                ):
                    validate_runtime_closure_v4_bootstrap_targets(root)

    def test_runtime_closure_v4_writer_repeats_preflight_before_first_write(self) -> None:
        closure = {
            "freeze_commit": "f" * 40,
            "schema_version": "runtime-executable-closure-v4",
        }
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment = repository / "experiments/specchoice-v1.3.2"
            receipt = experiment / "receipts/runtime-executable-closure-v4.json"
            receipt.parent.mkdir(parents=True)
            args = SimpleNamespace(receipt=receipt, freeze_commit="f" * 40)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=experiment),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module,
                    "build_runtime_closure_v4",
                    side_effect=[closure, RuntimeClosureError("late target race")],
                ) as builder,
                mock.patch.object(cli_module, "write_new_descriptor_file") as writer,
            ):
                with self.assertRaisesRegex(RuntimeClosureError, "late target race"):
                    cli_module.command_write_runtime_executable_closure_v4(args)
                self.assertEqual(builder.call_count, 2)
                writer.assert_not_called()

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment = repository / "experiments/specchoice-v1.3.2"
            receipt = experiment / "receipts/runtime-executable-closure-v4.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_bytes(canonical_json_bytes(closure))
            args = SimpleNamespace(receipt=receipt, freeze_commit="f" * 40)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=experiment),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(cli_module, "verify_runtime_closure_v4", return_value=closure),
                mock.patch.object(cli_module, "build_runtime_closure_v4") as builder,
            ):
                self.assertEqual(
                    cli_module.command_write_runtime_executable_closure_v4(args), 0
                )
                builder.assert_not_called()
            alias = receipt.with_name("closure-alias.json")
            alias.symlink_to(receipt.name)
            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=experiment),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                self.assertRaisesRegex(ValueError, "RUNTIME_CLOSURE_V4_PATH_INVALID"),
            ):
                cli_module.command_write_runtime_executable_closure_v4(
                    SimpleNamespace(receipt=alias, freeze_commit="f" * 40)
                )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            experiment = repository / "experiments/specchoice-v1.3.2"
            receipt = experiment / "receipts/runtime-executable-closure-v4.json"
            receipt.parent.mkdir(parents=True)
            args = SimpleNamespace(receipt=receipt, freeze_commit="f" * 40)

            def identical_racer(root: Path, relative: str, raw: bytes) -> None:
                (root / relative).write_bytes(raw)
                raise FilesystemPolicyError("AUTHORITATIVE_DESTINATION_EXISTS")

            with (
                mock.patch.object(cli_module, "_experiment_root", return_value=experiment),
                mock.patch.object(cli_module, "_repository_root", return_value=repository),
                mock.patch.object(
                    cli_module, "build_runtime_closure_v4", side_effect=[closure, closure]
                ),
                mock.patch.object(cli_module, "verify_runtime_closure_v4", return_value=closure),
                mock.patch.object(
                    cli_module, "write_new_descriptor_file", side_effect=identical_racer
                ),
            ):
                self.assertEqual(
                    cli_module.command_write_runtime_executable_closure_v4(args), 0
                )
            self.assertEqual(receipt.read_bytes(), canonical_json_bytes(closure))

    def test_runtime_closure_v4_post_validation_does_not_reapply_bootstrap_absence(self) -> None:
        closure = {
            "freeze_commit": "e" * 40,
            "schema_version": "runtime-executable-closure-v4",
        }
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            materialized = repository / future_target_inventory_v7()[0]["path"]
            materialized.parent.mkdir(parents=True)
            materialized.write_bytes(b"downstream exact-resume bytes\n")
            with mock.patch(
                "specchoice_evidence.runtime_closure._runtime_closure_v4_projection",
                return_value=closure,
            ):
                self.assertEqual(
                    verify_runtime_closure_v4(closure, repository), closure
                )

    def test_accepted_v6_active_validator_rejects_lineage_and_materialized_raw_drift(self) -> None:
        repository = self.repository
        accepted = (
            "experiments/specchoice-v1.3.2/bundles/accepted/"
            "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
        )
        candidate = (
            "experiments/specchoice-v1.3.2/bundles/candidates/"
            "source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
        )
        packet = (
            "experiments/specchoice-v1.3.2/receipts/"
            "source-contract-proposal-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6"
        )
        bound = accepted_v6_active_bound_paths(repository)
        expected_fixed = {
            "experiments/specchoice-v1.3.2/phase2/source-authority.json",
            "experiments/specchoice-v1.3.2/receipts/runtime-executable-closure-v3.json",
            "experiments/specchoice-v1.3.2/phase2/source-authority-v13-historical.json",
            "experiments/specchoice-v1.3.2/phase2/source-authority-v13-pending.json",
            "experiments/specchoice-v1.3.2/receipts/pending/source-cutover-readiness-v13.json",
            "experiments/specchoice-v1.3.2/receipts/pending/fixture-closure-transition-v3-to-v6.json",
            "experiments/specchoice-v1.3.2/receipts/fixture-closure-acceptance-audit-v6.json",
            "experiments/specchoice-v1.3.2/receipts/fixture-closure-revocation-v3-to-v6.json",
            "experiments/specchoice-v1.3.2/receipts/fixture-closure-offline-replay-v6.json",
            "experiments/specchoice-v1.3.2/receipts/integrity-receipt-v14.json",
            "experiments/specchoice-v1.3.2/receipts/local-acceptance-request-v13.json",
            "experiments/specchoice-v1.3.2/receipts/local-acceptance-decision-v13.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-decision-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6/candidate-audit-v6.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-proposal-v5-non-executable-supersession-v1.json",
        }
        proposal_value = json.loads((repository / packet / "proposal.json").read_text())
        proposal_inputs = {entry["path"] for entry in proposal_value["bound_inputs"]}
        v4_lineage = {
            "experiments/specchoice-v1.3.2/receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-proposal-v4-supersession-v3.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-decision-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
        }
        self.assertTrue(v4_lineage <= proposal_inputs)
        historical_closure = json.loads(
            (repository / "experiments/specchoice-v1.3.2/receipts/runtime-executable-closure-v3.json").read_text()
        )
        incomplete_proposal = deepcopy(proposal_value)
        incomplete_proposal["bound_inputs"] = [
            entry for entry in incomplete_proposal["bound_inputs"]
            if entry["path"]
            != "experiments/specchoice-v1.3.2/config/measurement/pr2164-semantic-gold-contract-v2.json"
        ]
        with self.assertRaisesRegex(
            SuccessorProtocolError, "ACCEPTED_V6_ACTIVE_AUTHORITY_MISMATCH",
        ):
            _validate_recorded_proposal_inputs(
                repository, incomplete_proposal, historical_closure,
            )
        expected_tree = {
            path.relative_to(repository).as_posix()
            for tree in (repository / candidate, repository / packet)
            for path in tree.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(set(bound), expected_fixed | v4_lineage | expected_tree)

        def copied_repository(destination: Path) -> None:
            for relative in bound:
                source = repository / relative
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            shutil.copytree(repository / accepted, destination / accepted)

        def validate_copy(root: Path) -> dict[str, object]:
            with mock.patch(
                "specchoice_evidence.successor.verify_runtime_closure_v3_historical",
                side_effect=lambda closure, _repository: dict(closure),
            ):
                return validate_accepted_v6_active_authority(root)

        tamper_paths = (
            f"{packet}/proposal.json",
            f"{packet}/supersession-v5.json",
            "experiments/specchoice-v1.3.2/phase2/source-authority-v13-pending.json",
            "experiments/specchoice-v1.3.2/receipts/local-acceptance-decision-v13.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-decision-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-proposal-v4-supersession-v3.json",
            "experiments/specchoice-v1.3.2/receipts/source-contract-construction-decision-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json",
            (
                f"{accepted}/raw/evaluation_fixtures/"
                "CAND_WARL_FIXED_LEGAL_SET/source.txt"
            ),
            f"{accepted}/snapshot-manifest.json",
            (
                f"{candidate}/raw/evaluation_fixtures/"
                "CAND_WARL_FIXED_LEGAL_SET/source.txt"
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            clean = Path(directory)
            copied_repository(clean)
            validate_copy(clean)
        for relative in tamper_paths:
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                copied_repository(root)
                path = root / relative
                path.write_bytes(path.read_bytes() + b"tamper")
                with self.assertRaisesRegex(
                    SuccessorProtocolError,
                    "ACCEPTED_V6_ACTIVE_AUTHORITY_(?:INPUT_INVALID|MISMATCH)",
                ):
                    validate_copy(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied_repository(root)
            with (
                mock.patch(
                    "specchoice_evidence.successor._verify_exact_accepted_v6",
                    side_effect=SuccessorProtocolError("LOCAL_ACCEPTED_V6_DIVERGENT"),
                ),
                self.assertRaisesRegex(
                    SuccessorProtocolError,
                    "ACCEPTED_V6_ACTIVE_AUTHORITY_INPUT_INVALID",
                ),
            ):
                validate_copy(root)

    def test_runtime_closure_v3_historical_rejects_truncated_or_mutated_receipt(self) -> None:
        repository = Path(__file__).parents[3]
        receipt = json.loads((repository / "experiments/specchoice-v1.3.2/receipts/runtime-executable-closure-v3.json").read_text())
        self.assertEqual(len(receipt["entries"]), 103)
        verify_runtime_closure_v3_historical(receipt, repository)
        truncated = deepcopy(receipt)
        truncated["entries"] = truncated["entries"][:1]
        with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_V3_HISTORY_MISMATCH"):
            verify_runtime_closure_v3_historical(truncated, repository)
        mutated = deepcopy(receipt)
        mutated["entries"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_V3_HISTORY_MISMATCH"):
            verify_runtime_closure_v3_historical(mutated, repository)

    def test_v5_construction_decision_rejects_every_transitive_one_byte_drift_before_write(self) -> None:
        closure_raw = b'{"closure":"frozen"}\n'
        authority_raw = b'{"accepted_identity":"accepted-v3"}\n'
        inputs = {"config/fixture-registry-pr2164-v5.json": b"registry\n"}
        proposal = build_source_contract_proposal_v5(
            runtime_closure_raw=closure_raw,
            authority_pre_state_raw=authority_raw,
            bound_inputs=inputs,
            targets=["bundles/candidates/source-contract-v5"],
        )
        validate_source_contract_proposal_v5(
            proposal,
            runtime_closure_raw=closure_raw,
            authority_pre_state_raw=authority_raw,
            bound_inputs=inputs,
        )
        for name, changed in (
            ("closure", b'{"closure":"drifted"}\n'),
            ("authority", b'{"accepted_identity":"drifted"}\n'),
            ("input", b"registry drift\n"),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(SourceContractProposalError, "V5_PROPOSAL_BINDING_MISMATCH"):
                validate_source_contract_proposal_v5(
                    proposal,
                    runtime_closure_raw=changed if name == "closure" else closure_raw,
                    authority_pre_state_raw=changed if name == "authority" else authority_raw,
                    bound_inputs={"config/fixture-registry-pr2164-v5.json": changed} if name == "input" else inputs,
                )

    def test_v12_acceptance_and_cutover_entrypoints(self) -> None:
        commands = cli_module.build_parser()._subparsers._group_actions[0].choices
        self.assertTrue({
            "write-local-acceptance-request-v12",
            "validate-local-acceptance-decision-v12",
            "accept-fixture-closure-local-v12",
            "prepare-pending-source-cutover-v12",
            "validate-pending-source-cutover-v12",
            "activate-pending-source-cutover-v12",
            "write-accepted-v5-receipts",
        }.issubset(commands))

    def test_v5_registry_manifest_and_every_repair_payload_are_pre_freeze_committed_inputs(self) -> None:
        registry = json.loads((self.experiment / "config/fixture-registry-pr2164-v5.json").read_text())
        manifest = json.loads((self.experiment / "config/fixture-repairs/pr2164-semantic-gold-v4/repair-manifest.json").read_text())
        self.assertEqual(registry["fixture_count"], 11)
        self.assertEqual(registry["raw_file_count"], 29)
        self.assertEqual(len(registry["fixture_ids"]), 11)
        self.assertEqual(len(manifest["payload_paths"]), 9)
        for path in manifest["payload_paths"]:
            self.assertTrue((self.experiment / path).is_file(), path)

    def test_v6_registry_is_a_complete_twenty_nine_file_inventory(self) -> None:
        registry = json.loads((self.experiment / "config/fixture-registry-pr2164-v6.json").read_text())
        entries = registry["file_entries"]
        self.assertEqual(registry["fixture_count"], 11)
        self.assertEqual(registry["raw_file_count"], 29)
        self.assertEqual(len(entries), 29)
        self.assertEqual({entry["fixture_id"] for entry in entries}, {
            "CAND_WARL_FIXED_LEGAL_SET", "NEG_EXT_GATED_PBMTE", "NEG_FIXED_ENCODING",
            "NEG_SHALL_NO_DELEGATION", "NEG_SOFTWARE_ADVICE", "POS_CSR_RW_MTVEC_ACCESS",
            "POS_DIRECT_CACHE_BLOCK", "POS_DIRECT_NUM_PMP", "POS_RECALL_COUNT_GEILEN",
            "POS_WARL_ASID_WIDTH", "POS_WARL_MTVEC_MODES",
        })
        self.assertEqual(registry["partition"], {"candidate": 2, "negative": 3, "positive": 6})
        self.assertTrue(all(set(entry) == {"fixture_id", "origin", "path", "role", "byte_length", "sha256"} for entry in entries))

    def test_v6_preflight_reconstructs_target_inventory_before_any_write(self) -> None:
        from specchoice_evidence.runtime_closure import validate_v6_preflight_inventory

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            inputs.mkdir()
            (inputs / "registry.json").write_bytes(b"registry\n")
            result = validate_v6_preflight_inventory(
                root=root,
                input_paths=["inputs/registry.json"],
                target_paths=["receipts/proposal.json", "bundles/candidate"],
            )
            self.assertEqual(result["targets"], ["bundles/candidate", "receipts/proposal.json"])
            (root / "receipts").mkdir()
            (root / "receipts/proposal.json").write_bytes(b"occupied\n")
            with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_TARGET_OCCUPIED"):
                validate_v6_preflight_inventory(
                    root=root,
                    input_paths=["inputs/registry.json"],
                    target_paths=["receipts/proposal.json", "bundles/candidate"],
                )

    def test_v5_rejection_is_exact_and_v5_mutators_fail_closed(self) -> None:
        receipt = render_v5_rejected_pre_authorization_receipt()
        validated = validate_v5_rejected_pre_authorization_receipt(
            receipt,
            runtime_closure_raw=(self.experiment / "receipts/runtime-executable-closure-v1.json").read_bytes(),
            proposal_raw=(self.experiment / "receipts/source-contract-proposal-v5-pr2164-semantic-gold-executable-closure-verifier-rooted-v5.json").read_bytes(),
            supersession_raw=(self.experiment / "receipts/source-contract-construction-proposal-v5-supersession-v4.json").read_bytes(),
            repository_root=self.repository,
        )
        self.assertEqual(validated["status"], "rejected_pre_authorization_non_executable")
        self.assertFalse(validated["human_decision_present"])
        self.assertFalse(validated["candidate_present"])
        for command in (
            "build-fixture-construction-candidate-v5",
            "accept-fixture-closure-local-v12",
            "activate-pending-source-cutover-v12",
        ):
            result = subprocess.run(
                [sys.executable, "-m", "specchoice_evidence.cli", command, "--preflight"],
                cwd=self.experiment, check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("V5_PACKET_REJECTED_PRE_AUTHORIZATION", result.stderr)

    def test_v6_future_target_inventory_is_typed_complete_and_occupancy_checked(self) -> None:
        inventory = future_target_inventory_v6()
        self.assertEqual(len(inventory), 25)
        self.assertEqual([item["path"] for item in inventory], sorted(item["path"] for item in inventory))
        self.assertEqual(len({item["kind"] for item in inventory}), 25)
        self.assertTrue(all("source-contract-v5" not in item["path"] for item in inventory))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(validate_future_target_occupancy_v6(root), inventory)
            occupied = next(item["path"] for item in inventory if item["kind"] == "construction_decision")
            target = root / occupied
            target.parent.mkdir(parents=True)
            target.write_bytes(b"occupied")
            with self.assertRaisesRegex(RuntimeClosureError, "V6_TARGET_OCCUPANCY_MISMATCH"):
                validate_future_target_occupancy_v6(root)
            self.assertEqual(target.read_bytes(), b"occupied")

    def test_v6_registry_and_accepted_v3_transitive_inventories_are_reconstructed(self) -> None:
        classes = _referenced_runtime_paths_v2(self.repository)
        accepted = {path for path, kinds in classes.items() if "accepted_v3_referenced_file" in kinds}
        registry = {path for path, kinds in classes.items() if "registry_v6_raw_input" in kinds}
        repairs = {path for path, kinds in classes.items() if "repair_v5_payload" in kinds}
        self.assertEqual(len(accepted), 34)
        self.assertEqual(len(registry), 29)
        self.assertEqual(len(repairs), 9)
        self.assertTrue(all((self.repository / path).is_file() for path in accepted | registry | repairs))

    def test_v6_v13_command_surface_is_real(self) -> None:
        commands = cli_module.build_parser()._subparsers._group_actions[0].choices
        expected = {
            "write-runtime-executable-closure-v3", "validate-runtime-executable-closure-v3",
            "write-source-contract-proposal-v6", "validate-source-contract-proposal-v6",
            "validate-fixture-construction-decision-v6", "build-fixture-construction-candidate-v6",
            "validate-fixture-candidate-v6", "write-fixture-candidate-audit-v6",
            "write-local-acceptance-request-v13", "validate-local-acceptance-decision-v13",
            "accept-fixture-closure-local-v13", "prepare-pending-source-cutover-v13",
            "validate-pending-source-cutover-v13", "activate-pending-source-cutover-v13",
            "write-accepted-v6-receipts", "verify-accepted-v6-receipts",
        }
        self.assertTrue(expected <= set(commands))

    def test_v13_human_decision_is_closed_self_hashed_and_request_bound(self) -> None:
        candidate = {
            "core_sha256": "a" * 64, "generation": "source-contract-v6",
            "root_sha256": "b" * 64, "snapshot_manifest_sha256": "c" * 64,
            "status": "candidate",
        }
        projected = {key: value for key, value in candidate.items() if key != "status"}
        request = {
            "candidate": candidate, "projected_accepted": projected,
            "schema_version": "local-acceptance-request-v13",
        }
        request_sha = sha256_bytes(canonical_json_bytes(request))
        decision = {
            "attestation": "I personally reviewed these exact candidate bytes.",
            "candidate": candidate, "decision": "accept",
            "decision_timestamp": "2026-08-03T12:34:56Z",
            "external_publication_authorized": False,
            "projected_accepted": projected, "rationale": "Exact local candidate accepted.",
            "request_sha256": request_sha, "reviewer": "human-reviewer",
            "schema_version": "local-acceptance-decision-v13",
        }
        decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
        self.assertEqual(
            validate_local_acceptance_decision_v13(decision, request, request_sha256=request_sha)["decision"],
            "accept",
        )
        for field in ("reviewer", "rationale", "attestation"):
            malformed = copy.deepcopy(decision)
            malformed[field] = ""
            malformed.pop("decision_sha256")
            malformed["decision_sha256"] = sha256_bytes(canonical_json_bytes(malformed))
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "LOCAL_ACCEPTANCE_DECISION_V13_INVALID"
            ):
                validate_local_acceptance_decision_v13(malformed, request, request_sha256=request_sha)
        stale = copy.deepcopy(decision)
        stale["rationale"] = "changed without refreshing self hash"
        with self.assertRaisesRegex(ValueError, "LOCAL_ACCEPTANCE_DECISION_V13_INVALID"):
            validate_local_acceptance_decision_v13(stale, request, request_sha256=request_sha)

    def test_runtime_closure_v2_binds_clean_tool_env_exact_argv_and_real_git_blob_oid(self) -> None:
        with mock.patch.dict(os.environ, {"GIT_OPTIONAL_LOCKS": "1"}, clear=False):
            with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_TOOL_ENVIRONMENT_DIRTY"):
                _require_clean_tool_environment()
        with mock.patch.dict(os.environ, {"RUBYOPT": "-rnot_allowed"}, clear=False):
            with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_TOOL_ENVIRONMENT_DIRTY"):
                _tool_identities(self.repository, self.experiment)

        tools = _tool_identities(self.repository, self.experiment)
        self.assertEqual(tools["git"]["environment"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(tools["git"]["environment"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertIn("require 'psych'", tools["ruby_psych"]["argv"][-1])
        self.assertIn("import importlib", tools["python"]["discovery_argv"][-1])
        self.assertFalse(tools["ruby_psych"]["argv"][-1].startswith("sha256:"))

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
            subprocess.run(["git", "config", "user.name", "Closure Test"], cwd=repository, check=True)
            (repository / "bound.txt").write_bytes(b"bound bytes\n")
            subprocess.run(["git", "add", "bound.txt"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "bound"], cwd=repository, check=True)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            blob = subprocess.run(
                ["git", "rev-parse", f"{commit}:bound.txt"], cwd=repository,
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            entry = _git_bound_entry(repository, commit, "bound.txt", {"test"})
            self.assertEqual(entry["git_blob_oid"], blob)
            self.assertNotIn("git_blob_sha256", entry)

    def test_runtime_closure_v2_rejects_tool_version_argv_environment_and_blob_oid_drift(self) -> None:
        frozen = {
            "ambient_tool_environment": {"GIT_OPTIONAL_LOCKS": "", "RUBYLIB": "", "RUBYOPT": ""},
            "entries": [{"git_blob_oid": "a" * 40, "path": "bound.txt"}],
            "freeze_commit": "b" * 40,
            "schema_version": "runtime-executable-closure-v2",
            "tools": {
                "git": {"argv": ["/git", "--version"], "environment": {"LC_ALL": "C"}, "version_output": "git version 1"},
                "ruby_psych": {"argv": ["/ruby", "-e", "script"], "ruby_version": "3.3.0"},
            },
        }
        with mock.patch("specchoice_evidence.runtime_closure.build_runtime_closure_v2", return_value=frozen):
            verify_runtime_closure_v2(frozen, self.repository)
            for mutation in (
                lambda value: value["tools"]["git"].update({"version_output": "git version forged"}),
                lambda value: value["tools"]["git"].update({"argv": ["git", "--version"]}),
                lambda value: value["tools"]["git"].update({"environment": {"LC_ALL": "en_US"}}),
                lambda value: value["entries"][0].update({"git_blob_oid": "c" * 40}),
            ):
                drifted = copy.deepcopy(frozen)
                mutation(drifted)
                with self.assertRaisesRegex(RuntimeClosureError, "RUNTIME_CLOSURE_V2_MISMATCH"):
                    verify_runtime_closure_v2(drifted, self.repository)

    def test_runtime_closure_v3_freezes_authority_and_accepts_exact_historical_bytes(self) -> None:
        authority_raw = b'{"schema_version":"10"}\n'
        frozen = {
            "authority_pre_state": {
                "byte_length": len(authority_raw),
                "git_blob_oid": "a" * 40,
                "path": "experiments/specchoice-v1.3.2/phase2/source-authority.json",
                "sha256": sha256_bytes(authority_raw),
            },
            "freeze_commit": "b" * 40,
            "schema_version": "runtime-executable-closure-v3",
        }
        with mock.patch(
            "specchoice_evidence.runtime_closure.build_runtime_closure_v3",
            return_value=frozen,
        ):
            self.assertEqual(
                verify_runtime_closure_v3(
                    frozen, self.repository, authority_pre_state_raw=authority_raw
                ),
                frozen,
            )
            with self.assertRaisesRegex(
                RuntimeClosureError, "RUNTIME_CLOSURE_V3_AUTHORITY_PRESTATE_INVALID"
            ):
                verify_runtime_closure_v3(
                    frozen,
                    self.repository,
                    authority_pre_state_raw=authority_raw.replace(b"10", b"11"),
                )

    def test_runtime_closure_v3_authority_binding_comes_from_freeze_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
            subprocess.run(["git", "config", "user.name", "Closure Test"], cwd=repository, check=True)
            authority = repository / "authority.json"
            original = b'{"authority":"frozen"}\n'
            authority.write_bytes(original)
            subprocess.run(["git", "add", "authority.json"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "authority"], cwd=repository, check=True)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            drifted = b'{"authority":"live-drift"}\n'
            authority.write_bytes(drifted)
            subprocess.run(["git", "add", "authority.json"], cwd=repository, check=True)
            subprocess.run(["git", "commit", "-qm", "replacement"], cwd=repository, check=True)
            replacement = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            subprocess.run(["git", "replace", commit, replacement], cwd=repository, check=True)
            replaced_blob = subprocess.run(
                ["git", "show", f"{commit}:authority.json"], cwd=repository, check=True,
                capture_output=True,
            ).stdout
            self.assertEqual(replaced_blob, drifted)
            binding = _git_blob_binding(repository, commit, "authority.json")
            self.assertEqual(binding["sha256"], sha256_bytes(original))
            self.assertNotEqual(binding["sha256"], sha256_bytes(drifted))

    def test_runtime_closure_v2_is_exact_non_authorizing_history(self) -> None:
        predecessor_raw = (self.experiment / "receipts/runtime-executable-closure-v2.json").read_bytes()
        receipt_path = self.experiment / (
            "receipts/runtime-executable-closure-v2-"
            "non-authorizing-supersession-v1.json"
        )
        receipt = json.loads(receipt_path.read_bytes())
        validated = validate_runtime_closure_v2_supersession(
            receipt, predecessor_raw=predecessor_raw
        )
        self.assertEqual(
            validated["status"],
            "superseded_pre_authorization_authority_pre_state_unbound",
        )
        self.assertFalse(validated["authorization_recorded"])
        self.assertFalse(validated["successor_proposal_exists"])
        with self.assertRaisesRegex(
            RuntimeClosureError, "RUNTIME_CLOSURE_V2_HISTORY_INVALID"
        ):
            validate_runtime_closure_v2_supersession(
                receipt, predecessor_raw=predecessor_raw[:-1] + b" "
            )
        with self.assertRaisesRegex(
            SourceContractProposalError, "RUNTIME_CLOSURE_V2_SUPERSEDED"
        ):
            cli_module.command_write_runtime_executable_closure_v2(
                mock.Mock()
            )

    def test_public_v6_builder_rejects_semantically_invalid_authority_pre_state(self) -> None:
        """Direct library callers cannot bypass accepted-v3 authority semantics."""
        accepted = self.experiment / (
            "bundles/accepted/"
            "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        )
        revocation = self.experiment / "receipts/fixture-closure-revocation-v2.json"
        authority_raw = canonical_json_bytes({})
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            experiment = repository / "experiments/specchoice-v1.3.2"
            shutil.copytree(
                accepted,
                experiment
                / "bundles/accepted/"
                "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3",
            )
            (experiment / "receipts").mkdir(parents=True)
            shutil.copy2(
                revocation,
                experiment / "receipts/fixture-closure-revocation-v2.json",
            )
            (experiment / "phase2").mkdir()
            (experiment / "phase2/source-authority.json").write_bytes(authority_raw)
            with (
                mock.patch(
                    "specchoice_evidence.successor._parse_closure_v3",
                    return_value={"freeze_commit": "a" * 40},
                ),
                mock.patch(
                    "specchoice_evidence.successor._validate_closure_v2_history"
                ),
                mock.patch("specchoice_evidence.successor._validate_v5_rejection"),
            ):
                with self.assertRaisesRegex(
                    SuccessorProtocolError, "V6_AUTHORITY_PRE_STATE_INVALID"
                ):
                    build_source_contract_proposal_v6(
                        repository,
                        closure_raw=b"closure",
                        authority_pre_state_raw=authority_raw,
                        v5_rejection_raw=b"rejection",
                    )

    def test_rooted_v6_proposal_rejects_copies_tamper_and_late_publish_collision_atomically(self) -> None:
        proposal = {"generation": "v6", "schema_version": "fixture-construction-proposal-v6"}
        supersession = {"schema_version": "source-contract-construction-proposal-v6-supersession-v5"}
        closure_raw, authority_raw, rejection_raw = b"closure", b"authority", b"rejection"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            packet = repository / _PACKET_RELATIVE
            packet.mkdir(parents=True)
            (packet / "proposal.json").write_bytes(canonical_json_bytes(proposal))
            (packet / "supersession-v5.json").write_bytes(canonical_json_bytes(supersession))
            copied = repository / "copied-packet"
            shutil.copytree(packet, copied)
            patches = (
                mock.patch("specchoice_evidence.successor._build_source_contract_proposal_v6", return_value=proposal),
                mock.patch("specchoice_evidence.successor._supersession_v5", return_value=supersession),
                mock.patch("specchoice_evidence.successor.validate_future_target_occupancy_v6", return_value=[]),
            )
            with patches[0], patches[1], patches[2]:
                validate_source_contract_proposal_v6(
                    repository, packet, closure_raw=closure_raw,
                    authority_pre_state_raw=authority_raw, v5_rejection_raw=rejection_raw,
                )
                with self.assertRaisesRegex(SuccessorProtocolError, "V6_PROPOSAL_PACKET_PATH_INVALID"):
                    validate_source_contract_proposal_v6(
                        repository, copied, closure_raw=closure_raw,
                        authority_pre_state_raw=authority_raw, v5_rejection_raw=rejection_raw,
                    )
                (packet / "proposal.json").write_bytes(canonical_json_bytes({"generation": "tampered"}))
                with self.assertRaisesRegex(SuccessorProtocolError, "V6_PROPOSAL_BINDING_MISMATCH"):
                    validate_source_contract_proposal_v6(
                        repository, packet, closure_raw=closure_raw,
                        authority_pre_state_raw=authority_raw, v5_rejection_raw=rejection_raw,
                    )

            shutil.rmtree(packet)
            with (
                mock.patch("specchoice_evidence.successor._build_source_contract_proposal_v6", return_value=proposal),
                mock.patch("specchoice_evidence.successor._supersession_v5", return_value=supersession),
                mock.patch("specchoice_evidence.successor.validate_future_target_occupancy_v6", return_value=[]),
                mock.patch(
                    "specchoice_evidence.successor._publish_directory_no_replace",
                    side_effect=BundleError("late collision"),
                ),
            ):
                with self.assertRaisesRegex(SuccessorProtocolError, "late collision"):
                    write_source_contract_proposal_packet_v6(
                        repository, packet, closure_raw=closure_raw,
                        authority_pre_state_raw=authority_raw, v5_rejection_raw=rejection_raw,
                    )
            self.assertFalse(packet.exists())
            self.assertEqual(list(packet.parent.glob(".proposal-v6.staging-*")), [])

    def test_v13_evidence_seam_rejects_invalid_or_reject_decisions_before_any_target_open(self) -> None:
        candidate_projection = {
            "core_sha256": "a" * 64, "generation": "v6", "root_sha256": "b" * 64,
            "snapshot_manifest_sha256": "c" * 64, "status": "candidate",
        }
        request = {
            "candidate": candidate_projection,
            "projected_accepted": {key: value for key, value in candidate_projection.items() if key != "status"},
            "schema_version": "local-acceptance-request-v13",
        }
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()

            def write(relative: str, value: dict[str, object]) -> bytes:
                raw = canonical_json_bytes(value)
                target = repository / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                return raw

            closure_raw = write(
                "experiments/specchoice-v1.3.2/receipts/runtime-executable-closure-v3.json",
                {"schema_version": "runtime-executable-closure-v3"},
            )
            construction_raw = write(_DECISION_RELATIVE, {"decision": "authorize"})
            audit_raw = write(_AUDIT_RELATIVE, {})
            request_raw = write(_REQUEST_RELATIVE, request)
            (repository / _CANDIDATE_RELATIVE).mkdir(parents=True)
            rejection = repository / "experiments/specchoice-v1.3.2/receipts/source-contract-construction-proposal-v5-non-executable-supersession-v1.json"
            rejection.parent.mkdir(parents=True, exist_ok=True)
            rejection.write_bytes(canonical_json_bytes({}))
            decision = {
                "attestation": "Personally reviewed.", "candidate": candidate_projection,
                "decision": "reject", "decision_timestamp": "2026-08-03T12:34:56Z",
                "external_publication_authorized": False,
                "projected_accepted": request["projected_accepted"],
                "rationale": "Reject exact candidate.",
                "request_sha256": sha256_bytes(request_raw), "reviewer": "human",
                "schema_version": "local-acceptance-decision-v13",
            }
            decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
            decision_raw = write(_ACCEPTANCE_DECISION_RELATIVE, decision)
            common_patches = (
                mock.patch("specchoice_evidence.successor._parse_closure_v3", return_value={}),
                mock.patch("specchoice_evidence.successor._validate_fixture_construction_decision_v6", return_value={"decision": "authorize"}),
                mock.patch("specchoice_evidence.successor._validate_registry_v6", return_value=({}, b"{}")),
                mock.patch("specchoice_evidence.successor.validate_fixture_candidate_v6", return_value={}),
                mock.patch("specchoice_evidence.successor.build_fixture_candidate_audit_v6", return_value={}),
                mock.patch("specchoice_evidence.successor._build_local_acceptance_request_v13", return_value=request),
            )
            with common_patches[0], common_patches[1], common_patches[2], common_patches[3], common_patches[4], common_patches[5]:
                with self.assertRaisesRegex(SuccessorProtocolError, "LOCAL_ACCEPTANCE_V13_REJECTED"):
                    validate_v13_evidence_chain(
                        repository, stage="accept", candidate=repository / _CANDIDATE_RELATIVE,
                        packet_directory=repository / _PACKET_RELATIVE, closure_raw=closure_raw,
                        authority_pre_state_raw=b"authority", audit_raw=audit_raw,
                        construction_decision_raw=construction_raw, request_raw=request_raw,
                        acceptance_decision_raw=decision_raw, require_accept=True,
                    )
            self.assertFalse((repository / "experiments/specchoice-v1.3.2/bundles/accepted/source-contract-v6-pr2164-semantic-gold-executable-closure-verifier-rooted-v6").exists())

            invalid = dict(decision)
            invalid["decision"] = "accept"
            invalid["decision_sha256"] = "0" * 64
            invalid_raw = write(_ACCEPTANCE_DECISION_RELATIVE, invalid)
            with common_patches[0], common_patches[1], common_patches[2], common_patches[3], common_patches[4], common_patches[5]:
                with self.assertRaisesRegex(SuccessorProtocolError, "LOCAL_ACCEPTANCE_DECISION_V13_INVALID"):
                    validate_v13_evidence_chain(
                        repository, stage="accept", candidate=repository / _CANDIDATE_RELATIVE,
                        packet_directory=repository / _PACKET_RELATIVE, closure_raw=closure_raw,
                        authority_pre_state_raw=b"authority", audit_raw=audit_raw,
                        construction_decision_raw=construction_raw, request_raw=request_raw,
                        acceptance_decision_raw=invalid_raw, require_accept=True,
                    )

    def test_v13_full_preflight_accepts_absent_or_exact_resume_and_rejects_divergent_occupancy(self) -> None:
        expected_request = {"schema_version": "local-acceptance-request-v13", "status": "pending"}
        expected_raw = canonical_json_bytes(expected_request)
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            request_path = repository / _REQUEST_RELATIVE
            with mock.patch(
                "specchoice_evidence.successor.validate_v13_evidence_chain",
                return_value={"request": expected_request},
            ):
                _, _, state = preflight_local_acceptance_request_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=b"authority", audit_raw=b"audit",
                    construction_decision_raw=b"construction",
                )
                self.assertEqual(state, "absent")
                request_path.parent.mkdir(parents=True, exist_ok=True)
                request_path.write_bytes(expected_raw)
                _, _, state = preflight_local_acceptance_request_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=b"authority", audit_raw=b"audit",
                    construction_decision_raw=b"construction",
                )
                self.assertEqual(state, "exact_resume")
                request_path.write_bytes(b"divergent")
                with self.assertRaisesRegex(SuccessorProtocolError, "LOCAL_ACCEPTANCE_REQUEST_V13_DIVERGENT"):
                    preflight_local_acceptance_request_v13(
                        repository, candidate=repository / _CANDIDATE_RELATIVE,
                        packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                        authority_pre_state_raw=b"authority", audit_raw=b"audit",
                        construction_decision_raw=b"construction",
                    )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            unexpected = repository / _ACCEPTANCE_DECISION_RELATIVE
            unexpected.parent.mkdir(parents=True)
            unexpected.write_bytes(b"occupied before request")
            with self.assertRaisesRegex(SuccessorProtocolError, "V13_PREFLIGHT_TARGET_OCCUPIED"):
                _occupied_v13_targets(repository, "request")

    def test_v13_accepted_directory_and_pending_batch_are_byte_exact_resumable(self) -> None:
        final = {"snapshot_manifest_sha256": "f" * 64, "status": "accepted"}
        final_raw = canonical_json_bytes(final)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, accepted = root / "candidate", root / "accepted"
            candidate.mkdir()
            accepted.mkdir()
            (candidate / "payload.txt").write_bytes(b"exact payload\n")
            (accepted / "payload.txt").write_bytes(b"exact payload\n")
            (candidate / "snapshot-manifest.json").write_bytes(canonical_json_bytes({"status": "candidate"}))
            (accepted / "snapshot-manifest.json").write_bytes(final_raw)
            with mock.patch(
                "specchoice_evidence.successor.verify_accepted_bundle",
                return_value={"generation": "v6", "manifest_sha256": "a" * 64, "root_sha256": "b" * 64},
            ):
                verified = _verify_exact_accepted_v6(candidate, accepted, final_raw)
                self.assertEqual(verified["snapshot_manifest_sha256"], "f" * 64)
                (accepted / "payload.txt").write_bytes(b"divergent payload\n")
                with self.assertRaisesRegex(SuccessorProtocolError, "LOCAL_ACCEPTED_V6_DIVERGENT"):
                    _verify_exact_accepted_v6(candidate, accepted, final_raw)

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            authority_raw = canonical_json_bytes({"generation": "v3"})
            authority = repository / "experiments/specchoice-v1.3.2/phase2/source-authority.json"
            authority.parent.mkdir(parents=True)
            authority.write_bytes(authority_raw)
            values = {
                "pending": {"status": "pending_cutover_v13"},
                "transition": {"status": "pending_non_effective"},
                "readiness": {"status": "ready_for_atomic_activation"},
            }
            with mock.patch(
                "specchoice_evidence.successor.build_pending_source_cutover_v13",
                return_value=values,
            ):
                _, payloads, dispositions = preflight_prepare_pending_source_cutover_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                    construction_decision_raw=b"construction", request_raw=b"request",
                    decision_raw=b"decision",
                )
                self.assertTrue(all(state == "absent" for state in dispositions.values()))
                exact_path = sorted(payloads)[0]
                exact = repository / exact_path
                exact.parent.mkdir(parents=True, exist_ok=True)
                exact.write_bytes(payloads[exact_path])
                _, _, resumed = preflight_prepare_pending_source_cutover_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                    construction_decision_raw=b"construction", request_raw=b"request",
                    decision_raw=b"decision",
                )
                self.assertEqual(resumed[exact_path], "exact_resume")
                divergent_path = sorted(payloads)[1]
                divergent = repository / divergent_path
                divergent.parent.mkdir(parents=True, exist_ok=True)
                divergent.write_bytes(b"divergent")
                with self.assertRaisesRegex(SuccessorProtocolError, "PENDING_CUTOVER_V13_DIVERGENT"):
                    preflight_prepare_pending_source_cutover_v13(
                        repository, candidate=repository / _CANDIDATE_RELATIVE,
                        packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                        authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                        construction_decision_raw=b"construction", request_raw=b"request",
                        decision_raw=b"decision",
                    )

    def test_v13_activation_preflights_every_receipt_before_authority_replacement(self) -> None:
        authority_raw = canonical_json_bytes({"generation": "v3"})
        identity = {
            "core_sha256": "a" * 64, "generation": "v6", "root_sha256": "b" * 64,
            "snapshot_manifest_sha256": "c" * 64,
        }
        values = {
            "pending": {"accepted_identity": identity},
            "transition": {"status": "pending_non_effective"},
            "readiness": {"status": "ready_for_atomic_activation"},
        }
        receipts = {
            "experiments/specchoice-v1.3.2/receipts/fixture-closure-acceptance-audit-v6.json": canonical_json_bytes({"status": "accepted"}),
            "experiments/specchoice-v1.3.2/receipts/integrity-receipt-v14.json": canonical_json_bytes({"status": "verified"}),
        }
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory).resolve()
            authority = repository / "experiments/specchoice-v1.3.2/phase2/source-authority.json"
            authority.parent.mkdir(parents=True)
            authority.write_bytes(authority_raw)
            patches = (
                mock.patch("specchoice_evidence.successor.validate_pending_source_cutover_v13", return_value=values),
                mock.patch("specchoice_evidence.successor._accepted_v6_receipts", return_value=receipts),
            )
            with patches[0], patches[1]:
                _, _, _, dispositions = preflight_activate_pending_source_cutover_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                    construction_decision_raw=b"construction", request_raw=b"request",
                    decision_raw=b"decision",
                )
                self.assertEqual(set(dispositions), set(receipts))
                self.assertTrue(all(state == "absent" for state in dispositions.values()))
                exact_path = sorted(receipts)[0]
                exact = repository / exact_path
                exact.parent.mkdir(parents=True, exist_ok=True)
                exact.write_bytes(receipts[exact_path])
                _, _, _, resumed = preflight_activate_pending_source_cutover_v13(
                    repository, candidate=repository / _CANDIDATE_RELATIVE,
                    packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                    authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                    construction_decision_raw=b"construction", request_raw=b"request",
                    decision_raw=b"decision",
                )
                self.assertEqual(resumed[exact_path], "exact_resume")
                divergent_path = sorted(receipts)[1]
                divergent = repository / divergent_path
                divergent.parent.mkdir(parents=True, exist_ok=True)
                divergent.write_bytes(b"divergent")
                with self.assertRaisesRegex(SuccessorProtocolError, "ACCEPTED_V6_RECEIPT_DIVERGENT"):
                    preflight_activate_pending_source_cutover_v13(
                        repository, candidate=repository / _CANDIDATE_RELATIVE,
                        packet_directory=repository / _PACKET_RELATIVE, closure_raw=b"closure",
                        authority_pre_state_raw=authority_raw, audit_raw=b"audit",
                        construction_decision_raw=b"construction", request_raw=b"request",
                        decision_raw=b"decision",
                    )
            self.assertEqual(authority.read_bytes(), authority_raw)


class FixtureClosureCandidateTests(unittest.TestCase):

    def _assert_canonical_revocation_absent(self, authority_root: Path) -> None:
        with self.assertRaisesRegex(FilesystemPolicyError, "AUTHORITATIVE_FILE_MISSING"):
            read_authoritative_file(authority_root / "receipts", "fixture-closure-revocation-v2.json")

    def _public_command(self, experiment: Path, *arguments: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, "-m", "specchoice_evidence.cli", *arguments],
            cwd=experiment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_v3_local_acceptance_prepares_pending_cutover_without_switching_v2(self) -> None:
        """The public v10 flow is disposable, forward-only, and leaves v2 alone until cutover."""
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        historical_v2 = experiment / "phase2/source-authority-v9-historical.json"
        audit = experiment / "receipts/fixture-closure-candidate-audit-v3.json"
        construction = experiment / "receipts/source-contract-decision-v3-pr2164-fixture-closure-verifier-rooted-v3.json"
        proposal = experiment / "receipts/source-contract-proposal-v3-pr2164-fixture-closure-verifier-rooted-v3.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority_root = root / "authority-root"
            active_v2 = authority_root / "phase2/source-authority.json"
            active_v2.parent.mkdir(parents=True)
            (authority_root / "receipts").mkdir()
            shutil.copyfile(historical_v2, active_v2)
            self._assert_canonical_revocation_absent(authority_root)
            request = root / "local-acceptance-request-v10.json"
            self._public_command(
                experiment,
                "write-local-acceptance-request-v10", "--candidate", str(candidate), "--audit", str(audit),
                "--construction-decision", str(construction), "--proposal", str(proposal),
                "--active-authority", str(active_v2), "--request", str(request),
            )
            request_payload = json.loads(request.read_text(encoding="utf-8"))
            self.assertNotIn("reviewer_identity", request_payload)
            decision = {
                "candidate": request_payload["candidate"], "decision": "accept",
                "external_publication_authorized": False,
                "projected_accepted": request_payload["projected_accepted"],
                "rationale": "disposable public test", "request_sha256": sha256_bytes(request.read_bytes()),
                "reviewer_identity": "test-reviewer", "reviewed_at": "2026-08-02T00:00:00Z",
                "schema_version": "10", "verifier_artifacts": request_payload["verifier_artifacts"],
            }
            decision_path = root / "decision.json"
            decision_path.write_bytes(canonical_json_bytes(decision))
            self.assertEqual(
                self._public_command(
                    experiment,
                    "validate-local-acceptance-decision-v10", "--request", str(request),
                    "--decision", str(decision_path),
                ),
                {
                    "decision": "accept",
                    "request_sha256": sha256_bytes(request.read_bytes()),
                    "status": "local_acceptance_decision_valid",
                },
            )
            accepted_root = root / "accepted"
            accepted = self._public_command(
                experiment,
                "accept-fixture-closure-local-v10", "--request", str(request), "--decision", str(decision_path),
                "--candidate", str(candidate), "--accepted-directory", str(accepted_root),
            )
            accepted_bundle = accepted_root / str(accepted["generation"])
            active = root / "source-authority.json"
            shutil.copyfile(active_v2, active)
            revocation = root / "fixture-closure-revocation-v2.json"
            readiness = experiment / "receipts/source-cutover-readiness-v10.json"
            self._public_command(
                experiment,
                "validate-phase2-source-authority", "--authority", str(active),
                "--bundle", str(experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"),
                "--revocation", str(revocation), "--authority-mode", "active",
            )
            historical = root / "source-authority-v9-historical.json"
            shutil.copyfile(active, historical)
            pending = root / "source-authority-v10-pending.json"
            transition = root / "fixture-closure-transition-v2-to-v3.json"
            self._public_command(
                experiment,
                "prepare-pending-source-cutover-v10", "--request", str(request), "--decision", str(decision_path),
                "--old-authority", str(active), "--accepted-bundle", str(accepted_bundle),
                "--pending-authority", str(pending), "--transition", str(transition), "--revocation", str(revocation),
            )
            self.assertEqual(
                self._public_command(
                    experiment,
                    "validate-pending-source-cutover-v10", "--pending-authority", str(pending),
                    "--transition", str(transition), "--active-authority", str(active),
                    "--accepted-bundle", str(accepted_bundle),
                )["status"],
                "pending_cutover_valid_non_effective",
            )
            revocation.write_bytes(transition.read_bytes())
            failed_v2 = subprocess.run(
                [
                    sys.executable, "-m", "specchoice_evidence.cli", "validate-phase2-source-authority",
                    "--authority", str(active),
                    "--bundle", str(experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"),
                    "--revocation", str(revocation), "--authority-mode", "active",
                ], cwd=experiment, check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(failed_v2.returncode, 0)
            revocation.unlink()
            self._public_command(
                experiment,
                "validate-phase2-source-authority", "--authority", str(historical),
                "--bundle", str(experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"),
                "--revocation", str(revocation), "--authority-mode", "historical-inspection",
            )
            self.assertFalse(self._public_command(
                experiment,
                "validate-phase2-source-authority", "--authority", str(historical),
                "--bundle", str(experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"),
                "--revocation", str(revocation), "--authority-mode", "historical-inspection",
            )["eligible"])
            self.assertEqual(active.read_bytes(), active_v2.read_bytes())
            self._assert_canonical_revocation_absent(authority_root)
            for bundle, expected in (
                (root / "missing-bundle", ""),
                (experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2", ""),
            ):
                with self.subTest(bundle=bundle):
                    result = subprocess.run(
                        [
                            sys.executable, "-m", "specchoice_evidence.cli", "activate-pending-source-cutover-v10",
                            "--pending-authority", str(pending), "--transition", str(transition),
                            "--readiness", str(readiness),
                            "--canonical-revocation", str(revocation), "--active-authority", str(active),
                            "--accepted-bundle", str(bundle),
                        ], cwd=experiment, check=False, capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0, expected)
                    self.assertFalse(revocation.exists())
                    self.assertEqual(active.read_bytes(), active_v2.read_bytes())
            # The public activator only accepts the single reviewed readiness
            # binding; its source inputs must therefore be the canonical pending
            # objects, even though the mutation targets remain disposable.
            pending = experiment / "phase2/source-authority-v10-pending.json"
            transition = experiment / "receipts/pending/fixture-closure-transition-v2-to-v3.json"
            accepted_bundle = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
            shutil.copyfile(active_v2, active)
            self._public_command(
                experiment,
                "activate-pending-source-cutover-v10", "--pending-authority", str(pending), "--transition", str(transition),
                "--readiness", str(readiness),
                "--canonical-revocation", str(revocation), "--active-authority", str(active), "--accepted-bundle", str(accepted_bundle),
            )
            self.assertNotEqual(active.read_bytes(), active_v2.read_bytes())
            self.assertTrue(revocation.exists())
            self._public_command(
                experiment,
                "validate-phase2-source-authority", "--authority", str(active), "--bundle", str(accepted_bundle),
                "--revocation", str(revocation), "--authority-mode", "active",
            )
            self.assertEqual(
                self._public_command(
                    experiment,
                    "activate-pending-source-cutover-v10", "--pending-authority", str(pending), "--transition", str(transition),
                    "--readiness", str(readiness),
                    "--canonical-revocation", str(revocation), "--active-authority", str(active), "--accepted-bundle", str(accepted_bundle),
                )["status"],
                "already_activated",
            )
            complete_revocation = revocation.read_bytes()
            complete_active = active.read_bytes()
            alternative_pending_payload = json.loads(pending.read_text(encoding="utf-8"))
            alternative_pending_payload["decision_sha256"] = "0" * 64
            alternative_transition_payload = json.loads(transition.read_text(encoding="utf-8"))
            alternative_transition_payload["decision_sha256"] = "0" * 64
            alternative_projection = dict(alternative_pending_payload)
            alternative_projection.pop("transition_sha256")
            alternative_transition_payload["new_authority_projection_sha256"] = sha256_bytes(
                canonical_json_bytes(alternative_projection)
            )
            alternative_transition = root / "self-consistent-transition.json"
            alternative_transition.write_bytes(canonical_json_bytes(alternative_transition_payload))
            alternative_pending_payload["transition_sha256"] = sha256_bytes(alternative_transition.read_bytes())
            alternative_pending = root / "self-consistent-pending.json"
            alternative_pending.write_bytes(canonical_json_bytes(alternative_pending_payload))
            malformed_readiness = root / "malformed-readiness.json"
            malformed_readiness.write_bytes(canonical_json_bytes({"schema_version": "10"}))
            malformed_transition = root / "malformed-complete-transition.json"
            malformed_transition.write_bytes(canonical_json_bytes({"schema_version": "2"}))
            for supplied_readiness, supplied_pending, supplied_transition in (
                (root / "missing-readiness.json", pending, transition),
                (malformed_readiness, pending, transition),
                (readiness, alternative_pending, alternative_transition),
                (readiness, pending, malformed_transition),
            ):
                with self.subTest(readiness=supplied_readiness.name, pending=supplied_pending.name):
                    result = subprocess.run(
                        [
                            sys.executable, "-m", "specchoice_evidence.cli", "activate-pending-source-cutover-v10",
                            "--pending-authority", str(supplied_pending), "--transition", str(supplied_transition),
                            "--readiness", str(supplied_readiness), "--canonical-revocation", str(revocation),
                            "--active-authority", str(active), "--accepted-bundle", str(accepted_bundle),
                        ], cwd=experiment, check=False, capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(revocation.read_bytes(), complete_revocation)
                    self.assertEqual(active.read_bytes(), complete_active)
            before = active.read_bytes()
            invalid_pending = root / "invalid-pending.json"
            invalid_pending.write_bytes(canonical_json_bytes({"schema_version": "10"}))
            with self.assertRaisesRegex(AssertionError, "SOURCE_CUTOVER"):
                self._public_command(
                    experiment,
                    "activate-pending-source-cutover-v10", "--pending-authority", str(invalid_pending),
                    "--readiness", str(readiness),
                    "--transition", str(transition), "--canonical-revocation", str(revocation),
                    "--active-authority", str(active), "--accepted-bundle", str(accepted_bundle),
                )
            self.assertEqual(active.read_bytes(), before)

            # Revocation may be durable while the authority replacement has not
            # happened; the public owner resumes only from exact held bytes.
            resume = root / "resume"
            resume.mkdir()
            resume_active = resume / "source-authority.json"
            resume_revocation = resume / "fixture-closure-revocation-v2.json"
            shutil.copyfile(active_v2, resume_active)
            resume_revocation.write_bytes(transition.read_bytes())
            self.assertEqual(
                self._public_command(
                    experiment,
                    "activate-pending-source-cutover-v10", "--pending-authority", str(pending),
                    "--readiness", str(readiness),
                    "--transition", str(transition), "--canonical-revocation", str(resume_revocation),
                    "--active-authority", str(resume_active), "--accepted-bundle", str(accepted_bundle),
                )["status"],
                "activated",
            )
            self.assertEqual(resume_active.read_bytes(), pending.read_bytes())

            for mutation in (
                lambda path: path.write_bytes(canonical_json_bytes({"schema_version": "2"})),
                lambda path: path.write_bytes(canonical_json_bytes({**json.loads(transition.read_text(encoding="utf-8")), "old_authority_sha256": "0" * 64})),
            ):
                with self.subTest(transition_mutation=mutation):
                    invalid_transition = root / "invalid-transition.json"
                    mutation(invalid_transition)
                    before_revocation = revocation.read_bytes()
                    before_active = active.read_bytes()
                    with self.assertRaisesRegex(AssertionError, "SOURCE_CUTOVER"):
                        self._public_command(
                            experiment, "activate-pending-source-cutover-v10", "--pending-authority", str(pending),
                            "--readiness", str(readiness),
                            "--transition", str(invalid_transition), "--canonical-revocation", str(revocation),
                            "--active-authority", str(active), "--accepted-bundle", str(accepted_bundle),
                        )
                    self.assertEqual(revocation.read_bytes(), before_revocation)
                    self.assertEqual(active.read_bytes(), before_active)

            with self.assertRaisesRegex(AssertionError, "SOURCE_CUTOVER"):
                self._public_command(
                    experiment, "activate-pending-source-cutover-v10", "--pending-authority", str(pending),
                    "--readiness", str(readiness),
                    "--transition", str(transition), "--canonical-revocation", str(revocation),
                    "--active-authority", str(active),
                    "--accepted-bundle", str(experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"),
                )

    def test_v3_copied_offline_replay_uses_embedded_hardened_verifier(self) -> None:
        """The v10 accepted successor verifies with only its embedded verifier."""
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "candidate"
            shutil.copytree(candidate, copied)
            result = subprocess.run(
                [sys.executable, "verify_bundle.py"], cwd=copied,
                env={"PATH": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_v3_acceptance_receipts_and_copied_replay_bind_same_identity(self) -> None:
        """Public receipt writers bind accepted v3 without activating the pending cutover."""
        experiment = Path(__file__).resolve().parents[1]
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        historical_v2 = experiment / "phase2/source-authority-v9-historical.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "authority-root/phase2/source-authority.json"
            active.parent.mkdir(parents=True)
            (root / "authority-root/receipts").mkdir()
            shutil.copyfile(historical_v2, active)
            self._assert_canonical_revocation_absent(root / "authority-root")
            before = active.read_bytes()
            result = self._public_command(
                experiment,
                "write-accepted-v3-receipts",
                "--request", str(experiment / "receipts/local-acceptance-request-v10.json"),
                "--decision", str(experiment / "receipts/local-acceptance-v10.json"),
                "--candidate-audit", str(experiment / "receipts/fixture-closure-candidate-audit-v3.json"),
                "--pending-authority", str(experiment / "phase2/source-authority-v10-pending.json"),
                "--transition", str(experiment / "receipts/pending/fixture-closure-transition-v2-to-v3.json"),
                "--active-authority", str(active),
                "--historical-authority", str(active),
                "--accepted-bundle", str(accepted),
                "--receipt-directory", str(root),
            )
            self.assertEqual(result["status"], "accepted_v3_receipts_written")
            self.assertEqual(result["written"], [
                "fixture-closure-acceptance-audit-v3.json",
                "fixture-closure-acceptance-audit-v3.md",
                "fixture-closure-offline-replay-v3.json",
                "integrity-receipt-v10.json",
                "integrity-receipt-v10.md",
            ])
            audit = json.loads((root / "fixture-closure-acceptance-audit-v3.json").read_text(encoding="utf-8"))
            integrity = json.loads((root / "integrity-receipt-v10.json").read_text(encoding="utf-8"))
            replay = json.loads((root / "fixture-closure-offline-replay-v3.json").read_text(encoding="utf-8"))
            for path in (
                root / "fixture-closure-acceptance-audit-v3.json",
                root / "integrity-receipt-v10.json",
                root / "fixture-closure-offline-replay-v3.json",
            ):
                self.assertEqual(path.read_bytes(), canonical_json_bytes(json.loads(path.read_text(encoding="utf-8"))))
            self.assertEqual(audit["accepted_identity"], integrity["accepted_identity"])
            self.assertEqual(audit["accepted_identity"], replay["accepted_identity"])
            self.assertEqual(audit["local_only"], True)
            self.assertEqual(audit["external_publication_authorized"], False)
            self.assertEqual(len(audit["verifier_artifacts"]), 5)
            self.assertEqual(replay["copied_isolation_replay"], {
                "git_available": False,
                "network_available": False,
                "original_bundle_available": False,
                "repository_modules_available": False,
                "result": "passed",
            })
            self.assertEqual(active.read_bytes(), before)
            self._assert_canonical_revocation_absent(root / "authority-root")

    def test_source_authority_and_bundle_consumers_reuse_descriptor_bound_canonical_bytes(self) -> None:
        """The public authority receipt is assembled from descriptor-read bundle leaves."""
        experiment = Path(__file__).resolve().parents[1]
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        command = [
            sys.executable, "-m", "specchoice_evidence.cli", "validate-phase2-source-authority",
            "--authority", "phase2/source-authority-v13-historical.json", "--bundle", str(accepted),
            "--revocation", "receipts/fixture-closure-revocation-v2.json", "--authority-mode", "active",
        ]
        result = subprocess.run(command, cwd=experiment, check=False, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stdout, canonical_json_bytes(json.loads(result.stdout.decode("utf-8"))))
        receipt = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(receipt["status"], "valid")
        self.assertEqual(set(receipt), {
            "eligible", "fixture_count", "generation", "manifest_sha256", "pinned_commit_sha",
            "pinned_tree_sha", "raw_file_count", "registry_sha256", "root_sha256", "status",
        })

    def test_public_candidate_and_acceptance_paths_reject_rebound_control_leaves(self) -> None:
        """Public consumers fail closed before a special control leaf can be consumed."""
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "candidate"
            shutil.copytree(candidate, copied)
            registry = copied / "fixture-registry-pr2164-v1.json"
            registry.unlink()
            os.mkfifo(registry)
            with self.assertRaisesRegex(BundleError, "VERIFIER_ARTIFACT_INVALID|SPECIAL_FILE_KIND_REJECTED|STAGED_RAW_CUSTODY_MISMATCH"):
                verify_candidate(copied)

    def test_fixture_candidate_publish_rejects_racing_empty_target_without_overwrite(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        original = __import__("specchoice_evidence.bundle", fromlist=["_native_publish_no_replace"])._native_publish_no_replace

        def attacker(source: Path, target: Path) -> None:
            target.mkdir()
            original(source, target)

        with tempfile.TemporaryDirectory() as directory:
            candidates = Path(directory) / "candidates"
            target = candidates / "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
            with mock.patch("specchoice_evidence.bundle._native_publish_no_replace", side_effect=attacker):
                with self.assertRaisesRegex(BundleError, "CANDIDATE_TARGET_EXISTS"):
                    construct_fixture_closure_candidate(
                        json.loads((experiment / "receipts/source-contract-decision-v3-pr2164-fixture-closure-v2.json").read_text()),
                        json.loads((experiment / "receipts/source-contract-proposal-v3-pr2164-fixture-closure-v2.json").read_text()),
                        experiment / "config/fixture-registry-pr2164-v1.json",
                        experiment.parents[1],
                        candidates,
                    )
            self.assertTrue(target.is_dir())
            self.assertEqual(list(target.iterdir()), [])

    def test_fixture_accept_publish_rejects_racing_empty_target_without_overwrite(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        original = __import__("specchoice_evidence.bundle", fromlist=["_native_publish_no_replace"])._native_publish_no_replace

        def attacker(source: Path, target: Path) -> None:
            target.mkdir()
            original(source, target)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = self._write_fixture_acceptance_decision(
                root / "decision.json", self._current_fixture_acceptance_decision(experiment)
            )
            target = root / "accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
            with mock.patch("specchoice_evidence.bundle._native_publish_no_replace", side_effect=attacker):
                with self.assertRaisesRegex(BundleError, "LOCAL_ACCEPTED_TARGET_EXISTS"):
                    accept_fixture_closure_candidate(candidate, root / "accepted", decision)
            self.assertTrue(target.is_dir())
            self.assertEqual(list(target.iterdir()), [])

    def test_fixture_candidate_publish_preserves_racing_nonempty_target(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        original = __import__("specchoice_evidence.bundle", fromlist=["_native_publish_no_replace"])._native_publish_no_replace

        def attacker(source: Path, target: Path) -> None:
            target.mkdir()
            (target / "attacker.txt").write_text("do not overwrite", encoding="utf-8")
            original(source, target)

        with tempfile.TemporaryDirectory() as directory:
            candidates = Path(directory) / "candidates"
            target = candidates / "source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
            with mock.patch("specchoice_evidence.bundle._native_publish_no_replace", side_effect=attacker):
                with self.assertRaisesRegex(BundleError, "CANDIDATE_TARGET_EXISTS"):
                    construct_fixture_closure_candidate(
                        json.loads((experiment / "receipts/source-contract-decision-v3-pr2164-fixture-closure-v2.json").read_text()),
                        json.loads((experiment / "receipts/source-contract-proposal-v3-pr2164-fixture-closure-v2.json").read_text()),
                        experiment / "config/fixture-registry-pr2164-v1.json",
                        experiment.parents[1],
                        candidates,
                    )
            self.assertEqual((target / "attacker.txt").read_text(encoding="utf-8"), "do not overwrite")

    def test_fixture_publish_fails_closed_when_no_replace_primitive_is_unavailable(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = self._write_fixture_acceptance_decision(
                root / "decision.json", self._current_fixture_acceptance_decision(experiment)
            )
            with mock.patch("specchoice_evidence.bundle._native_publish_no_replace", side_effect=NotImplementedError):
                with self.assertRaisesRegex(BundleError, "ATOMIC_NO_REPLACE_UNAVAILABLE"):
                    accept_fixture_closure_candidate(candidate, root / "accepted", decision)

    def _current_fixture_acceptance_decision(self, experiment: Path) -> dict[str, object]:
        decision = json.loads((experiment / "receipts/local-acceptance-v9.json").read_text(encoding="utf-8"))
        decision["v7_basis"]["reviewed_revision"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=experiment.parents[1], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        return decision

    def _write_fixture_acceptance_decision(self, path: Path, decision: dict[str, object]) -> Path:
        path.write_bytes(canonical_json_bytes(decision))
        return path

    def test_public_fixture_acceptance_resolves_its_own_current_v7_basis(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        decision = self._current_fixture_acceptance_decision(experiment)
        with tempfile.TemporaryDirectory() as directory:
            accepted_root = Path(directory) / "accepted"
            decision_path = self._write_fixture_acceptance_decision(Path(directory) / "decision.json", decision)
            result = accept_fixture_closure_candidate(candidate, accepted_root, decision_path)
            self.assertEqual(result["status"], "accepted")
            self.assertTrue((accepted_root / result["generation"]).is_dir())

    def test_public_fixture_acceptance_rejects_missing_mismatched_and_stale_authority(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        decision = self._current_fixture_acceptance_decision(experiment)
        variants = (
            (None, "FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID"),
            ({**decision, "fixture_registry_sha256": "0" * 64}, "FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_MISMATCH"),
            ({**decision, "v7_basis": {**decision["v7_basis"], "reviewed_revision": "0" * 40}}, "FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH"),
        )
        for authority, code in variants:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                accepted_root = Path(directory) / "accepted"
                decision_path = (
                    None if authority is None
                    else self._write_fixture_acceptance_decision(Path(directory) / "decision.json", authority)
                )
                with self.assertRaisesRegex(BundleError, code):
                    accept_fixture_closure_candidate(candidate, accepted_root, decision_path)
                self.assertFalse(accepted_root.exists())

    def test_public_fixture_acceptance_rejects_current_boundary_violation(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        repository = experiment.parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        violation = repository / "fixture-closure-boundary-violation.tmp"
        violation.write_text("must block acceptance", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as directory:
                decision_path = self._write_fixture_acceptance_decision(
                    Path(directory) / "decision.json", self._current_fixture_acceptance_decision(experiment)
                )
                with self.assertRaisesRegex(BundleError, "FIXTURE_CLOSURE_ACCEPTANCE_BOUNDARY_BLOCKING"):
                    accept_fixture_closure_candidate(
                        candidate, Path(directory) / "accepted", decision_path
                    )
        finally:
            violation.unlink()

    def test_local_acceptance_authority_is_bound_to_identity_registry_and_v7_basis(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v1"
        identity = verify_candidate(candidate)
        final = json.loads((candidate / "snapshot-manifest.json").read_text(encoding="utf-8"))
        registry_sha256 = sha256_bytes((candidate / "fixture-registry-pr2164-v1.json").read_bytes())
        v7_basis = {
            "allowlist_sha256": "a" * 64,
            "baseline_sha256": "b" * 64,
            "restart_receipt_sha256": "c" * 64,
            "reviewed_revision": "d" * 40,
        }
        decision = {
            "approval_scope": "fixture_closure_local_acceptance_only",
            "approved_generation": {
                "candidate_relative_path": "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v1",
                "core_sha256": identity["manifest_sha256"],
                "generation": identity["generation"],
                "root_sha256": identity["root_sha256"],
                "snapshot_manifest_sha256": final["snapshot_manifest_sha256"],
            },
            "authorization": {
                "external_publication_authorized": False,
                "fixture_closure_local_acceptance_authorized": True,
            },
            "fixture_registry_sha256": registry_sha256,
            "reviewer": {"disposition": "approved_local_only"},
            "schema_version": "1",
            "state": "fixture_closure_local_acceptance_authorized",
            "v7_basis": v7_basis,
        }
        require_fixture_closure_local_acceptance_authorization(
            decision, identity, final["snapshot_manifest_sha256"], registry_sha256, v7_basis
        )
        for changed, code in (
            (None, "FIXTURE_CLOSURE_ACCEPTANCE_DECISION_INVALID"),
            ({**decision, "fixture_registry_sha256": "0" * 64}, "FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_MISMATCH"),
            ({**decision, "v7_basis": {**v7_basis, "reviewed_revision": "e" * 40}}, "FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(SourceContractProposalError, code):
                require_fixture_closure_local_acceptance_authorization(
                    changed, identity, final["snapshot_manifest_sha256"], registry_sha256, v7_basis
                )

    def test_recanonicalized_subset_fails_embedded_fixture_closure(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "accepted"
            shutil.copytree(accepted, copied)
            core_path = copied / "content-manifest-core.json"
            core = json.loads(core_path.read_text(encoding="utf-8"))
            files = core["snapshots"][0]["consumed_files"]
            keep = files[:1]
            for entry in files[1:]:
                (copied / entry["local_bundle_path"]).unlink()
            core["snapshots"][0]["consumed_files"] = keep
            core_bytes = canonical_json_bytes(core)
            core_path.write_bytes(core_bytes)
            manifest_sha256 = sha256_bytes(core_bytes)
            artifacts = _raw_artifacts(core, copied) + _bundle_artifacts(core, copied)
            root_sha256 = _root_digest(manifest_sha256, artifacts)
            final_path = copied / "snapshot-manifest.json"
            final = json.loads(final_path.read_text(encoding="utf-8"))
            final["content_manifest_core"] = core
            final["manifest_sha256"] = manifest_sha256
            final["root_sha256"] = root_sha256
            final["snapshots"] = [
                {
                    **snapshot,
                    "generation": final["generation"],
                    "manifest_sha256": manifest_sha256,
                    "root_sha256": root_sha256,
                }
                for snapshot in core["snapshots"]
            ]
            final.pop("snapshot_manifest_sha256")
            final["snapshot_manifest_sha256"] = sha256_bytes(canonical_json_bytes(final))
            final_path.write_bytes(canonical_json_bytes(final))
            with self.assertRaisesRegex(Exception, "FIXTURE_CLOSURE_CORE_REGISTRY_MISMATCH"):
                verify_accepted_bundle(copied)

    def test_verifier_rooted_v3_candidate_has_fresh_root_and_unchanged_source_hashes(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / (
            "bundles/candidates/source-contract-v3-pr2164-fixture-closure-"
            "22e84458-verifier-rooted-v3"
        )
        identity = verify_candidate(candidate)
        self.assertEqual(identity["status"], "candidate")
        manifest = json.loads((candidate / "snapshot-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["downstream_eligible"])
        self.assertFalse(manifest["external_publication_authorized"])
        self.assertEqual(
            sum(len(snapshot["consumed_files"]) for snapshot in manifest["snapshots"]), 28
        )
        core = json.loads((candidate / "content-manifest-core.json").read_text(encoding="utf-8"))
        self.assertEqual(core["fixture_closure"]["fixture_count"], 11)
        self.assertEqual(core["fixture_closure"]["raw_file_count"], 28)
        self.assertEqual(len(core["bundle_artifacts"]), 6)
        self.assertEqual(
            [artifact["local_bundle_path"] for artifact in core["bundle_artifacts"] if artifact["kind"] == "verifier"],
            [
                "verifier/specchoice_evidence/__init__.py",
                "verifier/specchoice_evidence/canonical.py",
                "verifier/specchoice_evidence/filesystem.py",
                "verifier/specchoice_evidence/verify.py",
                "verify_bundle.py",
            ],
        )
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2"
        accepted_core = json.loads((accepted / "content-manifest-core.json").read_text(encoding="utf-8"))
        self.assertNotEqual(identity["manifest_sha256"], sha256_bytes((accepted / "content-manifest-core.json").read_bytes()))
        self.assertEqual(
            sorted(entry["raw_sha256"] for entry in core["snapshots"][0]["consumed_files"]),
            sorted(entry["raw_sha256"] for entry in accepted_core["snapshots"][0]["consumed_files"]),
        )
        proposal = json.loads((experiment / "receipts/source-contract-proposal-v3-pr2164-fixture-closure-verifier-rooted-v3.json").read_text())
        decision = json.loads((experiment / "receipts/source-contract-decision-v3-pr2164-fixture-closure-verifier-rooted-v3.json").read_text())
        audit = fixture_construction_candidate_audit(
            decision, proposal,
            "receipts/source-contract-proposal-v3-pr2164-fixture-closure-verifier-rooted-v3.json",
            "receipts/source-contract-decision-v3-pr2164-fixture-closure-verifier-rooted-v3.json",
            candidate,
        )
        self.assertEqual(audit["copied_isolation_replay"]["result"], "passed")

        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "candidate"
            shutil.copytree(candidate, copied)
            (copied / "raw/evaluation_fixtures/unexpected.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(BundleError, "BUNDLE_EXTRA_FILE"):
                verify_candidate(copied)
            (copied / "raw/evaluation_fixtures/unexpected.txt").unlink()
            (copied / "raw/evaluation_fixtures/POS_WARL_MTVEC_MODES/gold.yaml").unlink()
            with self.assertRaisesRegex(BundleError, "STAGED_RAW_CUSTODY_MISMATCH"):
                verify_candidate(copied)

        with self.subTest("semantic_gold_v4_proposal_is_closed_over_repairs_and_registry"):
            proposal_v2 = experiment / "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v2.json"
            historical_proposal_v3 = experiment / "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v3.json"
            repair_manifest_v2 = experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json"
            registry_v3 = experiment / "config/fixture-registry-pr2164-v3.json"
            supersession_v1 = experiment / "receipts/source-contract-construction-proposal-v4-supersession-v1.json"
            historical_supersession_v2 = experiment / "receipts/source-contract-construction-proposal-v4-supersession-v2.json"
            predecessor_v3 = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
            result = subprocess.run(
                [
                    sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-proposal-v4",
                    "--proposal", str(proposal_v2),
                    "--predecessor", str(predecessor_v3),
                    "--active-authority", str(experiment / "phase2/source-authority-v13-historical.json"),
                    "--historical-authority", str(experiment / "phase2/source-authority-v9-historical.json"),
                    "--revocation", str(experiment / "receipts/fixture-closure-revocation-v2.json"),
                    "--ontology-decision", str(experiment / "reviews/h1-source-gold-ontology-decision-v1.json"),
                    "--repair-manifest", str(repair_manifest_v2), "--registry", str(registry_v3),
                    "--supersession", str(supersession_v1),
                ],
                cwd=experiment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0, "legacy proposal-v2 must be decision-ineligible")
            proposal_payload = json.loads(proposal_v2.read_text(encoding="utf-8"))
            supersession_payload = json.loads(supersession_v1.read_text(encoding="utf-8"))
            self.assertEqual(proposal_payload["status"], "awaiting_human_construction_authorization")
            self.assertEqual(proposal_payload["selected_policy"]["pbmte"], "surfaced_classified_out")
            self.assertEqual(proposal_payload["selected_policy"]["cache"], "unified_cache_block_identity")

            cache_gold = (experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/POS_DIRECT_CACHE_BLOCK/gold.yaml").read_text(encoding="utf-8")
            pmp_gold = (experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/POS_DIRECT_NUM_PMP/gold.yaml").read_text(encoding="utf-8")
            geilen_expected = (experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/POS_RECALL_COUNT_GEILEN/expected.yaml").read_text(encoding="utf-8")
            asid_gold = (experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/POS_WARL_ASID_WIDTH/gold.yaml").read_text(encoding="utf-8")
            asid_expected = (experiment / "config/fixture-repairs/pr2164-semantic-gold-v2/POS_WARL_ASID_WIDTH/expected.yaml").read_text(encoding="utf-8")
            self.assertIn("enum:", cache_gold)
            self.assertIn("0x4", cache_gold)
            self.assertNotIn("uniform throughout", cache_gold)
            self.assertIn("maximum is omitted intentionally", cache_gold)
            self.assertIn("- 0", pmp_gold)
            self.assertIn("- 16", pmp_gold)
            self.assertIn("- 64", pmp_gold)
            self.assertIn("existing_alias", geilen_expected)
            self.assertIn("gold_name: GEILEN", geilen_expected)
            self.assertIn("NUM_EXTERNAL_GUEST_INTERRUPTS", geilen_expected)
            self.assertNotIn("versioned_aliases", asid_gold)
            self.assertIn("versioned_aliases", asid_expected)
            legacy_proposal = experiment / "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v1.json"
            legacy_manifest = experiment / "config/fixture-repairs/pr2164-semantic-gold-v1/repair-manifest.json"
            legacy_registry = experiment / "config/fixture-registry-pr2164-v2.json"
            self.assertEqual(supersession_payload["legacy"]["proposal"]["sha256"], sha256_bytes(legacy_proposal.read_bytes()))
            self.assertEqual(supersession_payload["legacy"]["repair_manifest"]["sha256"], sha256_bytes(legacy_manifest.read_bytes()))
            self.assertEqual(supersession_payload["legacy"]["registry"]["sha256"], sha256_bytes(legacy_registry.read_bytes()))
            self.assertNotEqual(legacy_manifest.read_bytes(), repair_manifest_v2.read_bytes())

            def run_v4(*, proposal_path: Path | None = None, manifest_path: Path | None = None, registry_path: Path | None = None, supersession_path: Path | None = None, decision_path: Path = experiment / "reviews/h1-source-gold-ontology-decision-v1.json") -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [
                        sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-proposal-v4",
                        "--proposal", str(proposal_path or proposal_v4), "--predecessor", str(predecessor_v3),
                        "--active-authority", str(experiment / "phase2/source-authority-v13-historical.json"),
                        "--historical-authority", str(experiment / "phase2/source-authority-v9-historical.json"),
                        "--revocation", str(experiment / "receipts/fixture-closure-revocation-v2.json"),
                        "--ontology-decision", str(decision_path), "--repair-manifest", str(manifest_path or repair_manifest),
                        "--registry", str(registry_path or registry_v4), "--supersession", str(supersession_path or rebind_supersession(proposal_path or proposal_v4, manifest_path or repair_manifest, registry_path or registry_v4)),
                        "--staging-root", str(staging_root),
                    ], cwd=experiment, check=False, capture_output=True, text=True,
                )

            with tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                historical_manifest = json.loads(repair_manifest_v2.read_text(encoding="utf-8"))
                historical_registry = json.loads(registry_v3.read_text(encoding="utf-8"))
                historical_proposal = json.loads(historical_proposal_v3.read_text(encoding="utf-8"))

                def write_payload(name: str, value: object) -> Path:
                    path = temporary / name
                    path.write_bytes(canonical_json_bytes(value))
                    return path

                staging_root = temporary / "staging"
                cache_target = staging_root / "config/fixture-repairs/pr2164-semantic-gold-v3/POS_DIRECT_CACHE_BLOCK/gold.yaml"
                cache_target.parent.mkdir(parents=True, exist_ok=True)
                fixed_cache = cache_gold.replace(
                    "Modeling note: maximum is omitted intentionally — the challenge snippet does\n"
                    "  not state an upper bound (contrast some UDB encodings that use 2**64-1 as a\n"
                    "  stand-in for \"unbounded\").",
                    "Modeling note: this ontology version deliberately represents the finite\n"
                    "  evaluation domain 2^0 through 2^63. That upper boundary is a versioned\n"
                    "  evaluation/UDB modeling choice, not an upper bound asserted by the challenge\n"
                    "  source.",
                ).encode("utf-8")
                cache_target.write_bytes(fixed_cache)
                geilen_target = staging_root / "config/fixture-repairs/pr2164-semantic-gold-v3/POS_RECALL_COUNT_GEILEN/expected.yaml"
                geilen_target.parent.mkdir(parents=True, exist_ok=True)
                fixed_geilen = geilen_expected.replace(
                    "versioned_aliases:\n  - NUM_EXTERNAL_GUEST_INTERRUPTS\nversioned_aliases:\n  - NUM_EXTERNAL_GUEST_INTERRUPTS\n",
                    "versioned_aliases:\n  - NUM_EXTERNAL_GUEST_INTERRUPTS\n",
                ).encode("utf-8")
                geilen_target.write_bytes(fixed_geilen)

                original_manifest = copy.deepcopy(historical_manifest)
                original_manifest["schema_version"] = "pr2164-semantic-gold-repair-manifest-v3"
                corrected = {
                    "raw/evaluation_fixtures/POS_DIRECT_CACHE_BLOCK/gold.yaml": cache_target,
                    "raw/evaluation_fixtures/POS_RECALL_COUNT_GEILEN/expected.yaml": geilen_target,
                }
                for repair in original_manifest["repairs"]:
                    replacement = corrected.get(repair["target_path"])
                    if replacement is not None:
                        repair["payload_path"] = replacement.relative_to(staging_root).as_posix()
                        raw = replacement.read_bytes()
                        repair["new_byte_length"] = len(raw)
                        repair["new_sha256"] = sha256_bytes(raw)
                repair_manifest = write_payload("repair-manifest-v3.json", original_manifest)

                original_registry = copy.deepcopy(historical_registry)
                original_registry["schema_version"] = "4"
                for fixture in original_registry["fixtures"]:
                    for file in fixture["files"]:
                        replacement = corrected.get(file["path"])
                        if replacement is not None:
                            raw = replacement.read_bytes()
                            file["byte_length"] = len(raw)
                            file["sha256"] = sha256_bytes(raw)
                registry_v4 = write_payload("registry-v4.json", original_registry)

                fixed_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=experiment, check=True, capture_output=True, text=True).stdout.strip()
                code_paths = (
                    "experiments/specchoice-v1.3.2/src/specchoice_evidence/canonical.py",
                    "experiments/specchoice-v1.3.2/src/specchoice_evidence/cli.py",
                    "experiments/specchoice-v1.3.2/src/specchoice_evidence/filesystem.py",
                    "experiments/specchoice-v1.3.2/src/specchoice_evidence/source_contract.py",
                    "experiments/specchoice-v1.3.2/src/specchoice_evidence/verify.py",
                    "experiments/specchoice-v1.3.2/src/specchoice_measurement/h1.py",
                )
                code_artifacts = []
                for path in code_paths:
                    raw = subprocess.run(["git", "show", f"{fixed_commit}:{path}"], cwd=experiment, check=True, capture_output=True).stdout
                    code_artifacts.append({"byte_length": len(raw), "path": path, "sha256": sha256_bytes(raw)})
                original_proposal = copy.deepcopy(historical_proposal)
                original_proposal["fixed_code_artifacts"] = code_artifacts
                original_proposal["fixed_code_commit"] = fixed_commit
                original_proposal["generation"] = "source-contract-v4-pr2164-semantic-gold-closure-verifier-rooted-v4"
                original_proposal["repair_manifest"] = {
                    "path": "config/fixture-repairs/pr2164-semantic-gold-v3/repair-manifest.json",
                    "sha256": sha256_bytes(repair_manifest.read_bytes()),
                }
                original_proposal["registry"] = {
                    "path": "config/fixture-registry-pr2164-v4.json",
                    "sha256": sha256_bytes(registry_v4.read_bytes()),
                }
                original_proposal["replacements"] = original_manifest["repairs"]
                proposal_v4 = write_payload("proposal-v4.json", original_proposal)
                supersession_v3_payload = {
                    "construction_authorized": False,
                    "legacy": {
                        "proposal": {"path": "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v3.json", "sha256": sha256_bytes(historical_proposal_v3.read_bytes())},
                        "repair_manifest": {"path": "config/fixture-repairs/pr2164-semantic-gold-v2/repair-manifest.json", "sha256": sha256_bytes(repair_manifest_v2.read_bytes())},
                        "registry": {"path": "config/fixture-registry-pr2164-v3.json", "sha256": sha256_bytes(registry_v3.read_bytes())},
                    },
                    "previous_supersession": {"path": "receipts/source-contract-construction-proposal-v4-supersession-v2.json", "sha256": sha256_bytes(historical_supersession_v2.read_bytes())},
                    "replacement_reason": "v4 replaces duplicate and contradictory semantic payloads without rewriting v3 history",
                    "schema_version": "source-contract-construction-proposal-supersession-v3",
                    "status": "semantic_proposal_v3_superseded",
                    "successor": {
                        "proposal": {"path": "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json", "sha256": sha256_bytes(proposal_v4.read_bytes())},
                        "repair_manifest": original_proposal["repair_manifest"], "registry": original_proposal["registry"],
                    },
                }
                supersession_v3 = write_payload("supersession-v3.json", supersession_v3_payload)

                def rebind_supersession(proposal_path: Path, manifest_path: Path, registry_path: Path) -> Path:
                    rebound = copy.deepcopy(supersession_v3_payload)
                    rebound["successor"]["proposal"]["sha256"] = sha256_bytes(proposal_path.read_bytes())
                    rebound["successor"]["repair_manifest"]["sha256"] = sha256_bytes(manifest_path.read_bytes())
                    rebound["successor"]["registry"]["sha256"] = sha256_bytes(registry_path.read_bytes())
                    return write_payload(f"rebound-{len(list(temporary.iterdir()))}.json", rebound)
                self.assertEqual(run_v4().returncode, 0)

                import specchoice_evidence.source_contract as source_contract_module

                historical_payloads = {
                    repair["payload_path"]: (experiment / repair["payload_path"]).read_bytes()
                    for repair in historical_manifest["repairs"]
                }
                repaired_payloads = {
                    repair["payload_path"]: (
                        (staging_root if "pr2164-semantic-gold-v3" in repair["payload_path"] else experiment)
                        / repair["payload_path"]
                    ).read_bytes()
                    for repair in original_manifest["repairs"]
                }
                self.assertFalse((staging_root / "config/fixture-repairs/pr2164-semantic-gold-v2").exists())
                with self.subTest("v4_repair_payloads_require_exact_two_staged_and_seven_reused_single_links"):
                    underspecified = copy.deepcopy(original_manifest)
                    underspecified["repairs"].pop()
                    with self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_MANIFEST_INVALID"
                    ):
                        cli_module._v4_repair_payloads(underspecified, staging_root)

                    linked_staging = temporary / "linked-staging"
                    staged_paths = [
                        repair["payload_path"] for repair in original_manifest["repairs"]
                        if "pr2164-semantic-gold-v3" in repair["payload_path"]
                    ]
                    for payload in staged_paths:
                        destination = linked_staging / payload
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes((staging_root / payload).read_bytes())
                    staged_link = linked_staging / staged_paths[0]
                    staged_source = linked_staging / "staged-hardlink-source"
                    staged_source.write_bytes(staged_link.read_bytes())
                    staged_link.unlink()
                    os.link(staged_source, staged_link)
                    with self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_PAYLOAD_INVALID"
                    ):
                        cli_module._v4_repair_payloads(original_manifest, linked_staging)

                    linked_experiment = temporary / "linked-experiment"
                    reused_paths = [
                        repair["payload_path"] for repair in original_manifest["repairs"]
                        if "pr2164-semantic-gold-v2" in repair["payload_path"]
                    ]
                    for payload in reused_paths:
                        destination = linked_experiment / payload
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes((experiment / payload).read_bytes())
                    reused_link = linked_experiment / reused_paths[0]
                    reused_source = linked_experiment / "reused-hardlink-source"
                    reused_source.write_bytes(reused_link.read_bytes())
                    reused_link.unlink()
                    os.link(reused_source, reused_link)
                    with mock.patch.object(cli_module, "_experiment_root", return_value=linked_experiment), self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_PAYLOAD_INVALID"
                    ):
                        cli_module._v4_repair_payloads(original_manifest, staging_root)

                    oversized_staging = temporary / "oversized-staging"
                    for payload in staged_paths:
                        destination = oversized_staging / payload
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes((staging_root / payload).read_bytes())
                    (oversized_staging / staged_paths[0]).write_bytes(b"x" * (64 * 1024 + 1))
                    with self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_PAYLOAD_INVALID"
                    ):
                        cli_module._v4_repair_payloads(original_manifest, oversized_staging)

                with self.subTest("v4_yaml_batch_rejects_historical_and_structural_ambiguity"):
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"):
                        source_contract_module._validate_v4_repair_yaml_batch(historical_payloads)
                    source_contract_module._validate_v4_repair_yaml_batch(repaired_payloads)
                    valid_key = next(iter(repaired_payloads))
                    sibling_payloads = dict(repaired_payloads)
                    sibling_payloads[valid_key] = b"items:\n  - name: first\n  - name: second\n"
                    source_contract_module._validate_v4_repair_yaml_batch(sibling_payloads)
                    oversized_payloads = dict(repaired_payloads)
                    oversized_payloads[valid_key] = b"x" * (64 * 1024 + 1)
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"):
                        source_contract_module._validate_v4_repair_yaml_batch(oversized_payloads)
                    eight_payloads = dict(list(repaired_payloads.items())[:-1])
                    ten_payloads = dict(repaired_payloads)
                    ten_payloads["config/fixture-repairs/pr2164-semantic-gold-v2/EXTRA/gold.yaml"] = b"name: extra\n"
                    for payload_count, payloads in ((8, eight_payloads), (10, ten_payloads)):
                        with self.subTest(payload_count=payload_count), self.assertRaisesRegex(
                            SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"
                        ):
                            source_contract_module._validate_v4_repair_yaml_batch(payloads)
                    oversized_path_payloads = dict(repaired_payloads)
                    oversized_path_payloads["x" * 513] = oversized_path_payloads.pop(valid_key)
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"):
                        source_contract_module._validate_v4_repair_yaml_batch(oversized_path_payloads)
                    oversized_envelope_payloads = {
                        path: b"key: " + (b"x" * (27 * 1024)) + b"\n"
                        for path in repaired_payloads
                    }
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"):
                        source_contract_module._validate_v4_repair_yaml_batch(oversized_envelope_payloads)
                    for name, raw in (
                        ("empty", b""),
                        ("non-mapping", b"- one\n- two\n"),
                        ("invalid-utf8", b"key: \xff\n"),
                        ("nested-duplicate", b"root:\n  nested: 1\n  nested: 2\n"),
                        ("malformed", b"root: [\n"),
                        ("multi-document", b"---\na: 1\n---\nb: 2\n"),
                        ("unused-anchor", b"a: &unused 1\n"),
                        ("anchor-alias", b"a: &shared 1\nb: *shared\n"),
                        ("merge", b"base: &base\n  a: 1\nvalue:\n  <<: *base\n"),
                        ("inline-merge", b"value: {<<: {a: 1}}\n"),
                        ("tagged-merge", b"value:\n  !!merge not-left: {a: 1}\n"),
                    ):
                        malformed_payloads = dict(repaired_payloads)
                        malformed_payloads[valid_key] = raw
                        with self.subTest(yaml_case=name), self.assertRaisesRegex(
                            SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"
                        ):
                            source_contract_module._validate_v4_repair_yaml_batch(malformed_payloads)

                with self.subTest("v4_yaml_batch_fails_closed_for_parser_boundary_failures"):
                    failures = (
                        OSError("ruby unavailable"),
                        subprocess.TimeoutExpired("ruby", 10),
                        subprocess.CompletedProcess([], 2, stdout=b"", stderr=b""),
                        subprocess.CompletedProcess([], 0, stdout=b'{"valid":true} \n', stderr=b""),
                        subprocess.CompletedProcess([], 0, stdout=b'{"valid":true}\n', stderr=b"warning"),
                    )
                    for failure in failures:
                        with mock.patch.object(source_contract_module, "_run_bounded_subprocess", side_effect=failure if isinstance(failure, BaseException) else None, return_value=None if isinstance(failure, BaseException) else failure), self.assertRaisesRegex(
                            SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_REPAIR_YAML_INVALID"
                        ):
                            source_contract_module._validate_v4_repair_yaml_batch(repaired_payloads)

                    for stream in ("stdout", "stderr"):
                        command = [
                            sys.executable,
                            "-c",
                            f"import sys; sys.{stream}.buffer.write(b'x' * 4097)",
                        ]
                        with self.subTest(oversized_stream=stream), self.assertRaises(OSError):
                            source_contract_module._run_bounded_subprocess(
                                command,
                                input_bytes=b"",
                                max_stdout_bytes=4096,
                                max_stderr_bytes=4096,
                                timeout=5,
                            )

                    def fake_process() -> mock.Mock:
                        process = mock.Mock()
                        process.stdout = io.BytesIO()
                        process.stderr = io.BytesIO()
                        process.poll.return_value = None
                        process.wait.return_value = -9
                        return process

                    selector_setup_cases = ("constructor", "second-register")
                    for setup_case in selector_setup_cases:
                        process = fake_process()
                        selector = mock.Mock()
                        selector.register.side_effect = [None, OSError("register failed")]
                        selector_patch = (
                            mock.patch.object(source_contract_module.selectors, "DefaultSelector", side_effect=OSError("selector failed"))
                            if setup_case == "constructor"
                            else mock.patch.object(source_contract_module.selectors, "DefaultSelector", return_value=selector)
                        )
                        with self.subTest(selector_setup=setup_case), mock.patch.object(
                            source_contract_module.subprocess, "Popen", return_value=process,
                        ), selector_patch, self.assertRaises(OSError):
                            source_contract_module._run_bounded_subprocess(
                                [sys.executable, "-c", "pass"], input_bytes=b"",
                                max_stdout_bytes=1, max_stderr_bytes=1, timeout=1,
                            )
                        process.kill.assert_called_once_with()
                        process.wait.assert_called()
                        self.assertTrue(process.stdout.closed)
                        self.assertTrue(process.stderr.closed)
                        if setup_case == "second-register":
                            selector.close.assert_called_once_with()

                    spawned: list[subprocess.Popen[bytes]] = []
                    original_popen = source_contract_module.subprocess.Popen

                    def capture_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
                        process = original_popen(*args, **kwargs)
                        spawned.append(process)
                        return process

                    with mock.patch.object(source_contract_module.subprocess, "Popen", side_effect=capture_popen), self.assertRaises(subprocess.TimeoutExpired):
                        source_contract_module._run_bounded_subprocess(
                            [sys.executable, "-c", "import time; time.sleep(10)"], input_bytes=b"",
                            max_stdout_bytes=1, max_stderr_bytes=1, timeout=0.05,
                        )
                    self.assertEqual(len(spawned), 1)
                    self.assertIsNotNone(spawned[0].poll())
                    self.assertTrue(spawned[0].stdout is not None and spawned[0].stdout.closed)
                    self.assertTrue(spawned[0].stderr is not None and spawned[0].stderr.closed)

                with self.subTest("v4_cache_domain_requires_honest_versioned_boundary"):
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_SEMANTICS_INVALID"):
                        source_contract_module._validate_v4_cache_semantics(cache_gold)
                    source_contract_module._validate_v4_cache_semantics(fixed_cache.decode("utf-8"))

                with self.subTest("v1_v2_v3_proposals_are_decision_ineligible"):
                    for legacy in (
                        experiment / "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v1.json",
                        proposal_v2,
                        historical_proposal_v3,
                    ):
                        with self.subTest(legacy=legacy.name):
                            self.assertNotEqual(run_v4(proposal_path=legacy).returncode, 0)

                with self.subTest("v4_predecessor_uses_one_closed_tree_snapshot"):
                    with mock.patch(
                        "specchoice_evidence.cli.read_closed_authoritative_tree",
                        wraps=cli_module.read_closed_authoritative_tree,
                    ) as read_closed, mock.patch(
                        "specchoice_evidence.cli.verify_accepted_bundle", side_effect=AssertionError("legacy path reopen")
                    ), mock.patch(
                        "specchoice_evidence.verify.read_authoritative_file", side_effect=AssertionError("material reopen")
                    ):
                        material = _v4_predecessor_material(predecessor_v3)
                    self.assertEqual(read_closed.call_count, 1)
                    self.assertEqual(material["identity"]["status"], "accepted")

                with self.subTest("v4_code_artifacts_are_exact_historical_commit_proofs"):
                    mutations = {
                        "wrong-path": lambda artifacts: artifacts[0].update({"path": "experiments/specchoice-v1.3.2/src/specchoice_evidence/not-cli.py"}),
                        "wrong-order": lambda artifacts: artifacts.reverse(),
                        "duplicate": lambda artifacts: artifacts.__setitem__(1, copy.deepcopy(artifacts[0])),
                        "wrong-length": lambda artifacts: artifacts[0].update({"byte_length": artifacts[0]["byte_length"] + 1}),
                        "wrong-hash": lambda artifacts: artifacts[0].update({"sha256": "0" * 64}),
                    }
                    for name, mutate in mutations.items():
                        forged = copy.deepcopy(original_proposal)
                        mutate(forged["fixed_code_artifacts"])
                        with self.subTest(name=name):
                            self.assertNotEqual(run_v4(proposal_path=write_payload(f"code-{name}.json", forged)).returncode, 0)
                    oversized_artifacts = copy.deepcopy(code_artifacts)
                    oversized_artifacts[0]["byte_length"] = source_contract_module._V4_GIT_MAX_ARTIFACT_BYTES + 1
                    with mock.patch("specchoice_evidence.source_contract._run_bounded_subprocess") as command, self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID"
                    ):
                        _require_v4_git_commit(fixed_commit, oversized_artifacts, experiment.parents[1])
                    command.assert_not_called()
                    with mock.patch("specchoice_evidence.source_contract._run_bounded_subprocess") as command:
                        command.side_effect = [
                            subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1),
                        ]
                        with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_CODE_COMMIT_INVALID"):
                            _require_v4_git_commit(fixed_commit, code_artifacts, experiment.parents[1])
                    forged = copy.deepcopy(original_proposal)
                    forged["fixed_code_commit"] = "0" * 40
                    self.assertNotEqual(run_v4(proposal_path=write_payload("code-nonexistent.json", forged)).returncode, 0)

                with self.subTest("v4_rejects_reason_and_previous_supersession_lineage_tampering"):
                    forged_manifest = copy.deepcopy(original_manifest)
                    forged_manifest["repairs"][0]["reason"] = "different rationale"
                    forged_manifest_path = write_payload("wrong-reason-manifest.json", forged_manifest)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_proposal["replacements"] = forged_manifest["repairs"]
                    self.assertNotEqual(run_v4(proposal_path=write_payload("wrong-reason-proposal.json", forged_proposal), manifest_path=forged_manifest_path).returncode, 0)
                    tampered_v1 = json.loads(supersession_v1.read_text(encoding="utf-8"))
                    tampered_v1["successor"]["proposal"]["sha256"] = "0" * 64
                    with self.assertRaisesRegex(SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_(SUPERSESSION|BINDING)_INVALID"):
                        _validate_v4_previous_supersession(
                            tampered_v1,
                            sha256_bytes(proposal_v2.read_bytes()), sha256_bytes(repair_manifest_v2.read_bytes()),
                            sha256_bytes(registry_v3.read_bytes()),
                            sha256_bytes(legacy_proposal.read_bytes()), sha256_bytes(legacy_manifest.read_bytes()),
                            sha256_bytes(legacy_registry.read_bytes()),
                        )
                    for side in ("legacy", "successor"):
                        tampered_v1 = json.loads(supersession_v1.read_text(encoding="utf-8"))
                        tampered_v1[side]["unknown"] = {"path": "extra", "sha256": "0" * 64}
                        with self.subTest(lineage="s1", side=side), self.assertRaisesRegex(
                            SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID"
                        ):
                            _validate_v4_previous_supersession(
                                tampered_v1,
                                sha256_bytes(proposal_v2.read_bytes()), sha256_bytes(repair_manifest_v2.read_bytes()),
                                sha256_bytes(registry_v3.read_bytes()),
                                sha256_bytes(legacy_proposal.read_bytes()), sha256_bytes(legacy_manifest.read_bytes()),
                                sha256_bytes(legacy_registry.read_bytes()),
                            )
                    supersession_v2_payload = json.loads(historical_supersession_v2.read_text(encoding="utf-8"))
                    for side in ("legacy", "successor"):
                        tampered_v2 = copy.deepcopy(supersession_v2_payload)
                        tampered_v2[side]["unknown"] = {"path": "extra", "sha256": "0" * 64}
                        with self.subTest(lineage="s2", side=side), self.assertRaisesRegex(
                            SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_SUPERSESSION_INVALID"
                        ):
                            source_contract_module._validate_v4_supersession_v2(
                                tampered_v2, sha256_bytes(canonical_json_bytes(tampered_v2)),
                                sha256_bytes(proposal_v2.read_bytes()), sha256_bytes(repair_manifest_v2.read_bytes()),
                                sha256_bytes(registry_v3.read_bytes()), sha256_bytes(historical_proposal_v3.read_bytes()),
                                json.loads(supersession_v1.read_text(encoding="utf-8")), sha256_bytes(supersession_v1.read_bytes()),
                                sha256_bytes(legacy_proposal.read_bytes()), sha256_bytes(legacy_manifest.read_bytes()),
                                sha256_bytes(legacy_registry.read_bytes()),
                            )
                    for side in ("legacy", "successor"):
                        tampered_v3 = copy.deepcopy(supersession_v3_payload)
                        tampered_v3[side]["unknown"] = {"path": "extra", "sha256": "0" * 64}
                        with self.subTest(lineage="s3", side=side):
                            self.assertNotEqual(
                                run_v4(supersession_path=write_payload(f"tampered-v3-{side}.json", tampered_v3)).returncode,
                                0,
                            )

                with self.subTest("v4_decision_requires_closed_self_hashed_human_fields"):
                    proposal_binding = {"fixed_code_commit": "a" * 40}
                    decision = {
                        "active_authority_sha256": "d" * 64, "attestation": "signed-by-reviewer",
                        "decision": "authorize", "decision_timestamp": "2026-08-03T12:34:56Z",
                        "external_publication_authorized": False, "fixed_code_commit": "a" * 40,
                        "local_only": True, "ontology_decision_sha256": "c" * 64,
                        "proposal_sha256": "b" * 64, "rationale": "human construction review complete",
                        "reviewer": "reviewer@example.invalid", "schema_version": "fixture-construction-decision-v4-v4",
                        "supersession_sha256": "e" * 64,
                    }
                    decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
                    for disposition in ("authorize", "reject"):
                        candidate = copy.deepcopy(decision)
                        candidate["decision"] = disposition
                        candidate.pop("decision_sha256")
                        candidate["decision_sha256"] = sha256_bytes(canonical_json_bytes(candidate))
                        self.assertEqual(validate_fixture_construction_decision_v4(candidate, proposal=proposal_binding, proposal_sha256="b" * 64, supersession_sha256="e" * 64, ontology_sha256="c" * 64, authority_sha256="d" * 64)["decision"], disposition)
                    malformed = copy.deepcopy(decision)
                    malformed["decision_timestamp"] = "2026-08-03T12:34:56+00:00"
                    self.assertRaises(SourceContractProposalError, validate_fixture_construction_decision_v4, malformed, proposal=proposal_binding, proposal_sha256="b" * 64, supersession_sha256="e" * 64, ontology_sha256="c" * 64, authority_sha256="d" * 64)

                with self.subTest("v4_decision_cli_and_writer_accept_only_the_valid_v4_baseline"):
                    def decision_payload(disposition: str) -> dict[str, object]:
                        value = {
                            "active_authority_sha256": sha256_bytes(
                                (experiment / "phase2/source-authority-v13-historical.json").read_bytes()
                            ), "attestation": "signed-by-reviewer",
                            "decision": disposition, "decision_timestamp": "2026-08-03T12:34:56Z", "external_publication_authorized": False,
                            "fixed_code_commit": fixed_commit, "local_only": True,
                            "ontology_decision_sha256": sha256_bytes((experiment / "reviews/h1-source-gold-ontology-decision-v1.json").read_bytes()),
                            "proposal_sha256": sha256_bytes(proposal_v4.read_bytes()), "rationale": "reviewed construction disposition",
                            "reviewer": "reviewer@example.invalid", "schema_version": "fixture-construction-decision-v4-v4",
                            "supersession_sha256": sha256_bytes(supersession_v3.read_bytes()),
                        }
                        value["decision_sha256"] = sha256_bytes(canonical_json_bytes(value))
                        return value

                    v4_args = ["--proposal", str(proposal_v4), "--predecessor", str(predecessor_v3), "--active-authority", str(experiment / "phase2/source-authority-v13-historical.json"), "--historical-authority", str(experiment / "phase2/source-authority-v9-historical.json"), "--revocation", str(experiment / "receipts/fixture-closure-revocation-v2.json"), "--ontology-decision", str(experiment / "reviews/h1-source-gold-ontology-decision-v1.json"), "--repair-manifest", str(repair_manifest), "--registry", str(registry_v4), "--supersession", str(supersession_v3), "--staging-root", str(staging_root)]
                    for disposition in ("authorize", "reject"):
                        decision_path = write_payload(f"decision-{disposition}.json", decision_payload(disposition))
                        result = subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-decision-v4", *v4_args, "--decision", str(decision_path)], cwd=experiment, check=False, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)

                    def rejects_decision(name: str, value: object) -> None:
                        self.assertNotEqual(
                            subprocess.run(
                                [sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-decision-v4", *v4_args,
                                 "--decision", str(write_payload(name, value))], cwd=experiment, check=False,
                            ).returncode,
                            0,
                        )

                    for name, mutation in (
                        ("decision-wrong-schema.json", lambda value: value.update({"schema_version": "fixture-construction-decision-v4-v3"})),
                        ("decision-unknown.json", lambda value: value.update({"unknown": True})),
                        ("decision-empty.json", lambda value: value.update({"rationale": ""})),
                        ("decision-utc.json", lambda value: value.update({"decision_timestamp": "2026-08-03T12:34:56+00:00"})),
                        ("decision-stale-binding.json", lambda value: value.update({"proposal_sha256": "0" * 64})),
                        ("decision-fixed-commit.json", lambda value: value.update({"fixed_code_commit": "0" * 40})),
                        ("decision-supersession.json", lambda value: value.update({"supersession_sha256": "0" * 64})),
                        ("decision-ontology.json", lambda value: value.update({"ontology_decision_sha256": "0" * 64})),
                        ("decision-authority.json", lambda value: value.update({"active_authority_sha256": "0" * 64})),
                        ("decision-not-local.json", lambda value: value.update({"local_only": False})),
                        ("decision-external.json", lambda value: value.update({"external_publication_authorized": True})),
                        ("decision-empty-reviewer.json", lambda value: value.update({"reviewer": ""})),
                        ("decision-empty-attestation.json", lambda value: value.update({"attestation": ""})),
                    ):
                        invalid = decision_payload("authorize")
                        mutation(invalid)
                        invalid.pop("decision_sha256")
                        invalid["decision_sha256"] = sha256_bytes(canonical_json_bytes(invalid))
                        rejects_decision(name, invalid)
                    stale_self = decision_payload("authorize")
                    stale_self["rationale"] = "changed without refreshing the self hash"
                    rejects_decision("decision-stale-self.json", stale_self)
                    noncanonical_decision = temporary / "decision-noncanonical.json"
                    noncanonical_decision.write_text(json.dumps(decision_payload("authorize"), indent=2), encoding="utf-8")
                    self.assertNotEqual(subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-decision-v4", *v4_args, "--decision", str(noncanonical_decision)], cwd=experiment, check=False).returncode, 0)
                    duplicate_decision = temporary / "decision-duplicate.json"
                    duplicate_decision.write_bytes(b'{"decision":"authorize","decision":"reject"}')
                    self.assertNotEqual(subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-decision-v4", *v4_args, "--decision", str(duplicate_decision)], cwd=experiment, check=False).returncode, 0)
                    linked_decision = temporary / "decision-link.json"
                    linked_decision.symlink_to(temporary / "decision-authorize.json")
                    self.assertNotEqual(subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "validate-fixture-construction-decision-v4", *v4_args, "--decision", str(linked_decision)], cwd=experiment, check=False).returncode, 0)
                    output = temporary / "output"
                    output.mkdir()
                    writer = subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "write-fixture-construction-proposal-v4", *v4_args, "--output-root", str(output)], cwd=experiment, check=False, capture_output=True, text=True)
                    self.assertEqual(writer.returncode, 0, writer.stderr)
                    targets = {
                        "config/fixture-repairs/pr2164-semantic-gold-v3/POS_DIRECT_CACHE_BLOCK/gold.yaml": fixed_cache,
                        "config/fixture-repairs/pr2164-semantic-gold-v3/POS_RECALL_COUNT_GEILEN/expected.yaml": fixed_geilen,
                        "config/fixture-repairs/pr2164-semantic-gold-v3/repair-manifest.json": repair_manifest.read_bytes(),
                        "config/fixture-registry-pr2164-v4.json": registry_v4.read_bytes(),
                        "receipts/source-contract-proposal-v4-pr2164-semantic-gold-closure-verifier-rooted-v4.json": proposal_v4.read_bytes(),
                        "receipts/source-contract-construction-proposal-v4-supersession-v3.json": supersession_v3.read_bytes(),
                    }
                    self.assertEqual({relative: (output / relative).read_bytes() for relative in targets}, targets)
                    self.assertEqual(subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "write-fixture-construction-proposal-v4", *v4_args, "--output-root", str(output)], cwd=experiment, check=False).returncode, 0)

                    resumed = temporary / "resumed"
                    resumed.mkdir()
                    for relative in list(targets)[:3]:
                        path = resumed / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(targets[relative])
                    resume = subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "write-fixture-construction-proposal-v4", *v4_args, "--output-root", str(resumed)], cwd=experiment, check=False, capture_output=True, text=True)
                    self.assertEqual(resume.returncode, 0, resume.stderr)
                    self.assertEqual({relative: (resumed / relative).read_bytes() for relative in targets}, targets)

                    for index, occupied in enumerate(targets):
                        collision_root = temporary / f"collision-{index}"
                        collision_root.mkdir()
                        occupied_path = collision_root / occupied
                        occupied_path.parent.mkdir(parents=True, exist_ok=True)
                        occupied_path.write_bytes(b"preexisting")
                        result = subprocess.run([sys.executable, "-m", "specchoice_evidence.cli", "write-fixture-construction-proposal-v4", *v4_args, "--output-root", str(collision_root)], cwd=experiment, check=False, capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(occupied_path.read_bytes(), b"preexisting")
                        for other in targets:
                            if other != occupied:
                                self.assertFalse((collision_root / other).exists())

                    hardlink_root = temporary / "hardlink-collision"
                    hardlink_root.mkdir()
                    hardlink_target = next(iter(targets))
                    hardlink_source = hardlink_root / "source"
                    hardlink_source.write_bytes(targets[hardlink_target])
                    linked = hardlink_root / hardlink_target
                    linked.parent.mkdir(parents=True)
                    os.link(hardlink_source, linked)
                    hardlink_result = subprocess.run(
                        [sys.executable, "-m", "specchoice_evidence.cli", "write-fixture-construction-proposal-v4", *v4_args, "--output-root", str(hardlink_root)],
                        cwd=experiment, check=False, capture_output=True, text=True,
                    )
                    self.assertNotEqual(hardlink_result.returncode, 0)
                    for other in targets:
                        if other != hardlink_target:
                            self.assertFalse((hardlink_root / other).exists())

                    postflight_root = temporary / "postflight-mismatch"
                    postflight_root.mkdir()
                    with mock.patch.object(
                        cli_module,
                        "write_exact_descriptor_files",
                        side_effect=FilesystemPolicyError("AUTHORITATIVE_POSTWRITE_MISMATCH"),
                    ), self.assertRaisesRegex(
                        SourceContractProposalError, "FIXTURE_CONSTRUCTION_V4_WRITE_INVALID"
                    ):
                        cli_module._write_v4_no_replace(postflight_root, {"receipts/proposal.json": b"expected"})
                    self.assertFalse((postflight_root / "receipts/proposal.json").exists())

                with self.subTest("v4_rejects_forged_old_hash_and_length"):
                    forged_manifest = copy.deepcopy(original_manifest)
                    forged_manifest["repairs"][0]["old_sha256"] = "0" * 64
                    forged_manifest["repairs"][0]["old_byte_length"] = 0
                    forged_manifest_path = write_payload("forged-manifest.json", forged_manifest)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_proposal["replacements"] = forged_manifest["repairs"]
                    self.assertNotEqual(run_v4(proposal_path=write_payload("forged-proposal.json", forged_proposal), manifest_path=forged_manifest_path).returncode, 0)

                with self.subTest("v4_rejects_mislabeled_replace_and_swapped_payload_control"):
                    forged_manifest = copy.deepcopy(original_manifest)
                    replacement = next(item for item in forged_manifest["repairs"] if item["kind"] == "replace")
                    replacement["kind"] = "add"
                    replacement["old_sha256"] = None
                    replacement["old_byte_length"] = None
                    forged_manifest_path = write_payload("mislabeled-manifest.json", forged_manifest)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_proposal["replacements"] = forged_manifest["repairs"]
                    self.assertNotEqual(run_v4(proposal_path=write_payload("mislabeled-proposal.json", forged_proposal), manifest_path=forged_manifest_path).returncode, 0)

                    forged_manifest = copy.deepcopy(original_manifest)
                    first, second = forged_manifest["repairs"][:2]
                    first["payload_path"], second["payload_path"] = second["payload_path"], first["payload_path"]
                    first["control"] = "semantic_correction"
                    forged_manifest_path = write_payload("swapped-manifest.json", forged_manifest)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_proposal["replacements"] = forged_manifest["repairs"]
                    self.assertNotEqual(run_v4(proposal_path=write_payload("swapped-proposal.json", forged_proposal), manifest_path=forged_manifest_path).returncode, 0)

                with self.subTest("v4_rejects_forged_registry_predecessor_and_reused_leaf"):
                    forged_registry = copy.deepcopy(original_registry)
                    forged_registry["predecessor_registry_sha256"] = "0" * 64
                    forged_registry["fixtures"][0]["files"][0]["role"] = "fixture_gold"
                    forged_registry_path = write_payload("forged-registry.json", forged_registry)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["registry"]["sha256"] = sha256_bytes(forged_registry_path.read_bytes())
                    self.assertNotEqual(run_v4(proposal_path=write_payload("registry-proposal.json", forged_proposal), registry_path=forged_registry_path).returncode, 0)

                with self.subTest("v4_rejects_registry_repair_claimed_as_predecessor"):
                    forged_registry = copy.deepcopy(original_registry)
                    repaired = next(
                        file for fixture in forged_registry["fixtures"] for file in fixture["files"]
                        if file["path"] == "raw/evaluation_fixtures/CAND_WARL_FIXED_LEGAL_SET/expected.yaml"
                    )
                    repaired["origin"] = "predecessor"
                    forged_registry_path = write_payload("origin-registry.json", forged_registry)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["registry"]["sha256"] = sha256_bytes(forged_registry_path.read_bytes())
                    self.assertNotEqual(run_v4(proposal_path=write_payload("origin-proposal.json", forged_proposal), registry_path=forged_registry_path).returncode, 0)

                with self.subTest("v4_rejects_opposite_valid_human_selection"):
                    opposite = json.loads((experiment / "reviews/h1-source-gold-ontology-decision-v1.json").read_text(encoding="utf-8"))
                    opposite["pbmte_policy"]["selection"] = "excluded_from_discovery"
                    opposite.pop("decision_sha256")
                    opposite["decision_sha256"] = sha256_bytes(canonical_json_bytes(opposite))
                    opposite_path = write_payload("opposite-decision.json", opposite)
                    self.assertNotEqual(run_v4(decision_path=opposite_path).returncode, 0)

                with self.subTest("v4_rejects_rebound_opposite_policy_with_only_seven_repairs"):
                    opposite = json.loads((experiment / "reviews/h1-source-gold-ontology-decision-v1.json").read_text(encoding="utf-8"))
                    opposite["pbmte_policy"]["selection"] = "excluded_from_discovery"
                    opposite.pop("decision_sha256")
                    opposite["decision_sha256"] = sha256_bytes(canonical_json_bytes(opposite))
                    opposite_path = write_payload("rebound-opposite-decision.json", opposite)
                    forged_manifest = copy.deepcopy(original_manifest)
                    forged_manifest["ontology_decision_sha256"] = sha256_bytes(opposite_path.read_bytes())
                    forged_manifest["repairs"] = [
                        repair for repair in forged_manifest["repairs"]
                        if "NEG_EXT_GATED_PBMTE" not in repair["target_path"]
                    ]
                    forged_manifest_path = write_payload("rebound-manifest.json", forged_manifest)
                    forged_registry = copy.deepcopy(original_registry)
                    forged_registry["ontology_decision_sha256"] = sha256_bytes(opposite_path.read_bytes())
                    forged_registry["fixtures"] = [
                        fixture for fixture in forged_registry["fixtures"]
                        if fixture["fixture_id"] != "NEG_EXT_GATED_PBMTE"
                    ]
                    forged_registry["fixture_count"] = 10
                    forged_registry["raw_file_count"] = 26
                    forged_registry_path = write_payload("rebound-registry.json", forged_registry)
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["ontology_decision"]["sha256"] = sha256_bytes(opposite_path.read_bytes())
                    forged_proposal["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_proposal["registry"]["sha256"] = sha256_bytes(forged_registry_path.read_bytes())
                    forged_proposal["replacements"] = forged_manifest["repairs"]
                    forged_proposal["selected_policy"]["pbmte"] = "excluded_from_discovery"
                    forged_proposal["successor_inventory"] = {
                        "fixture_count": 10,
                        "partition": {"candidate": 1, "negative": 3, "positive": 6},
                        "raw_file_count": 26,
                    }
                    forged_proposal_path = write_payload("rebound-proposal.json", forged_proposal)
                    forged_supersession = copy.deepcopy(supersession_v3_payload)
                    forged_supersession["successor"]["proposal"]["sha256"] = sha256_bytes(forged_proposal_path.read_bytes())
                    forged_supersession["successor"]["repair_manifest"]["sha256"] = sha256_bytes(forged_manifest_path.read_bytes())
                    forged_supersession["successor"]["registry"]["sha256"] = sha256_bytes(forged_registry_path.read_bytes())
                    forged_supersession_path = write_payload("rebound-supersession.json", forged_supersession)
                    predecessor_material = _v4_predecessor_material(predecessor_v3)
                    self.assertEqual(
                        _v4_inventory(
                            predecessor_material["files"], predecessor_material["classes"],
                            "excluded_from_discovery", forged_manifest,
                        ),
                        forged_proposal["successor_inventory"],
                    )
                    counterfactual = run_v4(
                        proposal_path=forged_proposal_path, manifest_path=forged_manifest_path,
                        registry_path=forged_registry_path, supersession_path=forged_supersession_path,
                        decision_path=opposite_path,
                    )
                    self.assertNotEqual(counterfactual.returncode, 0)
                    retained_registry = copy.deepcopy(original_registry)
                    retained_registry["ontology_decision_sha256"] = sha256_bytes(opposite_path.read_bytes())
                    retained_registry_path = write_payload("retained-pbmte-registry.json", retained_registry)
                    retained_proposal = copy.deepcopy(forged_proposal)
                    retained_proposal["registry"]["sha256"] = sha256_bytes(retained_registry_path.read_bytes())
                    retained_proposal_path = write_payload("retained-pbmte-proposal.json", retained_proposal)
                    retained_supersession = copy.deepcopy(forged_supersession)
                    retained_supersession["successor"]["proposal"]["sha256"] = sha256_bytes(retained_proposal_path.read_bytes())
                    retained_supersession["successor"]["registry"]["sha256"] = sha256_bytes(retained_registry_path.read_bytes())
                    retained_supersession_path = write_payload("retained-pbmte-supersession.json", retained_supersession)
                    self.assertNotEqual(
                        run_v4(
                            proposal_path=retained_proposal_path, manifest_path=forged_manifest_path,
                            registry_path=retained_registry_path, supersession_path=retained_supersession_path,
                            decision_path=opposite_path,
                        ).returncode,
                        0,
                    )

                with self.subTest("v4_rejects_nonexistent_code_commit"):
                    forged_proposal = copy.deepcopy(original_proposal)
                    forged_proposal["fixed_code_commit"] = "0" * 40
                    self.assertNotEqual(run_v4(proposal_path=write_payload("zero-commit.json", forged_proposal)).returncode, 0)

                with self.subTest("v4_rejects_noncanonical_duplicate_and_symlink_inputs"):
                    noncanonical = temporary / "noncanonical-proposal.json"
                    noncanonical.write_text(json.dumps(original_proposal, indent=2), encoding="utf-8")
                    self.assertNotEqual(run_v4(proposal_path=noncanonical).returncode, 0)
                    duplicate = temporary / "duplicate-proposal.json"
                    duplicate.write_bytes(b'{"schema_version":"fixture-construction-proposal-v4","schema_version":"fixture-construction-proposal-v4"}')
                    self.assertNotEqual(run_v4(proposal_path=duplicate).returncode, 0)
                    symlink = temporary / "proposal-link.json"
                    symlink.symlink_to(proposal_v4)
                    self.assertNotEqual(run_v4(proposal_path=symlink).returncode, 0)

    def test_accepted_v3_is_distinct_and_downstream_eligible(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        candidate = experiment / "bundles/candidates/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v1"
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v1"
        self.assertEqual(verify_candidate(candidate)["status"], "candidate")
        verified = verify_accepted_bundle(accepted)
        self.assertEqual(verified["status"], "accepted")
        manifest = json.loads((accepted / "snapshot-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["downstream_eligible"])
        self.assertTrue(manifest["offline_replay_proven"])
        self.assertFalse(manifest["external_publication_authorized"])

    def test_phase2_authority_requires_the_accepted_registry_digest(self) -> None:
        experiment = Path(__file__).resolve().parents[1]
        accepted = experiment / "bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3"
        command = [
            sys.executable, "-m", "specchoice_evidence.cli", "validate-phase2-source-authority",
            "--authority", "phase2/source-authority-v13-historical.json", "--bundle", str(accepted),
            "--revocation", "receipts/fixture-closure-revocation-v2.json", "--authority-mode", "active",
        ]
        result = subprocess.run(command, cwd=experiment, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        authority = json.loads(
            (experiment / "phase2/source-authority-v13-historical.json").read_text(encoding="utf-8")
        )
        authority["registry_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "source-authority.json"
            invalid.write_text(json.dumps(authority, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            command[command.index("phase2/source-authority-v13-historical.json")] = str(invalid)
            result = subprocess.run(command, cwd=experiment, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
