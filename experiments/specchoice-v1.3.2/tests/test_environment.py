# SPDX-License-Identifier: BSD-3-Clause-Clear
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from specchoice_evidence.canonical import canonical_json_bytes, sha256_bytes
from specchoice_evidence.environment import (
    CumulativeIncident,
    EnvironmentObservation,
    build_default_decision,
    build_environment_decision,
    write_environment_artifacts,
)


class EnvironmentDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = EnvironmentObservation(
            python_implementation="CPython",
            python_version="3.14.0",
            git_implementation="git",
            git_version="2.50.1",
        )

    def test_equivalent_stable_observations_have_identical_canonical_bytes(self) -> None:
        observation = self.observation
        first = canonical_json_bytes(build_environment_decision(observation))
        second = canonical_json_bytes(build_environment_decision(observation))
        self.assertEqual(first, second)
        self.assertEqual(sha256_bytes(first), sha256_bytes(second))
        self.assertNotIn(b"hostname", first)
        self.assertNotIn(b"working_directory", first)
        self.assertNotIn(b"command", first)

    def test_default_decision_selects_standalone_first_without_udb_probe(self) -> None:
        decision = build_default_decision(
            self.observation
        )
        self.assertEqual(decision["route"], "standalone_first")
        self.assertEqual(decision["outcome"], "success")
        self.assertFalse(decision["fallback_triggered"])
        self.assertEqual(decision["fallback_ceiling_status"], "not_started")
        self.assertEqual(decision["full_udb_setup"], {"attempted": False, "required": False})
        self.assertEqual(decision["incident"], {"error_codes": [], "outcome": "not_triggered", "triggered": False})
        self.assertEqual(
            decision["capabilities"]["construction"],
            ["git_cli_for_construction", "python_standard_library"],
        )
        self.assertEqual(
            decision["capabilities"]["downstream"],
            ["offline_bundle_access", "python_standard_library"],
        )

    def test_audit_receipt_has_one_way_canonical_digest_reference(self) -> None:
        observation = self.observation
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision_path = root / "environment-decision.json"
            audit_path = root / "environment-receipt.json"
            digest = write_environment_artifacts(
                decision_path,
                audit_path,
                observation,
                audit_metadata={
                    "command": "python3 /private/tmp/specchoice/record.py --token secret",
                    "hostname": "build-host",
                    "timestamp": "2026-07-30T14:30:00Z",
                    "working_directory": "/private/tmp/specchoice",
                },
            )
            decision_bytes = decision_path.read_bytes()
            receipt_bytes = audit_path.read_bytes()
            receipt = json.loads(receipt_bytes.decode("utf-8"))
        self.assertEqual(digest, sha256_bytes(decision_bytes))
        self.assertEqual(receipt["canonical_environment_decision_sha256"], digest)
        self.assertNotIn("audit", json.loads(decision_bytes.decode("utf-8")))
        self.assertNotIn(b"build-host", decision_bytes)
        self.assertNotIn(b"secret", receipt_bytes)
        self.assertNotIn(b"/private/tmp/specchoice", receipt_bytes)

    def test_audit_only_metadata_cannot_change_canonical_decision_bytes(self) -> None:
        observation = self.observation
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_decision = root / "first-decision.json"
            second_decision = root / "second-decision.json"
            first_digest = write_environment_artifacts(
                first_decision,
                root / "first-audit.json",
                observation,
                audit_metadata={"hostname": "first-host", "timestamp": "2026-07-30T00:00:00Z"},
            )
            second_digest = write_environment_artifacts(
                second_decision,
                root / "second-audit.json",
                observation,
                audit_metadata={"hostname": "second-host", "timestamp": "2026-07-31T00:00:00Z"},
            )
            self.assertEqual(first_decision.read_bytes(), second_decision.read_bytes())
        self.assertEqual(first_digest, second_digest)

    def test_no_incident_remains_not_triggered(self) -> None:
        incident = CumulativeIncident()
        self.assertEqual(incident.canonical_projection(), {"error_codes": [], "outcome": "not_triggered", "triggered": False})
        self.assertEqual(incident.exit_code, 0)

    def test_retries_alternatives_and_waits_keep_first_failure_clock(self) -> None:
        incident = CumulativeIncident()
        incident.record_failure("REQUIRED_CAPABILITY_UNAVAILABLE", 100.0, command="check capability")
        incident.record_event("retry", 160.0, command="retry check")
        incident.record_event("alternative_setup", 220.0, command="try workaround")
        snapshot = incident.record_event("unattended_wait", 400.0)
        self.assertEqual(snapshot.started_at, 100.0)
        self.assertEqual(snapshot.elapsed_seconds, 300.0)
        self.assertFalse(snapshot.expansion_stopped)
        self.assertEqual(snapshot.outcome, "active")
        self.assertEqual([event["kind"] for event in incident.audit_events()], ["failure", "retry", "alternative_setup", "unattended_wait"])

    def test_pre_ceiling_resolutions_are_stable_outcomes(self) -> None:
        restored = CumulativeIncident()
        restored.record_failure("REQUIRED_CAPABILITY_UNAVAILABLE", 0.0)
        restored_snapshot = restored.resolve("restored_standalone", 5399.0)
        resolved = CumulativeIncident()
        resolved.record_failure("DEPENDENCY_SETUP_FAILED", 0.0)
        resolved_snapshot = resolved.resolve("dependency_resolved", 60.0)
        self.assertEqual(restored_snapshot.outcome, "restored_standalone")
        self.assertEqual(resolved_snapshot.outcome, "dependency_resolved")
        self.assertEqual(restored.exit_code, 0)
        self.assertEqual(resolved.exit_code, 0)

    def test_ceiling_exceeded_stops_expansion_and_preserves_red_blocker(self) -> None:
        incident = CumulativeIncident()
        incident.record_failure("DEPENDENCY_SETUP_FAILED", 10.0)
        snapshot = incident.record_event("build", 5410.0, command="build dependency")
        self.assertEqual(snapshot.outcome, "ceiling_exceeded")
        self.assertTrue(snapshot.expansion_stopped)
        self.assertEqual(incident.exit_code, 1)
        self.assertEqual(snapshot.workaround, "red_blocker")
        with self.assertRaisesRegex(ValueError, "INCIDENT_EXPANSION_STOPPED"):
            incident.record_event("download", 5411.0)

    def test_audit_event_counts_and_times_do_not_change_canonical_incident_projection(self) -> None:
        first = CumulativeIncident()
        first.record_failure("DEPENDENCY_SETUP_FAILED", 0.0)
        first.record_event("retry", 10.0)
        first.resolve("dependency_resolved", 20.0)
        second = CumulativeIncident()
        second.record_failure("DEPENDENCY_SETUP_FAILED", 1000.0)
        second.record_event("retry", 1200.0)
        second.record_event("unattended_wait", 1400.0)
        second.resolve("dependency_resolved", 1500.0)
        first_decision = canonical_json_bytes(build_environment_decision(self.observation, first))
        second_decision = canonical_json_bytes(build_environment_decision(self.observation, second))
        self.assertEqual(first_decision, second_decision)


if __name__ == "__main__":
    unittest.main()
