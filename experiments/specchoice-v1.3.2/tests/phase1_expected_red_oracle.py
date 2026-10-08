# SPDX-License-Identifier: BSD-3-Clause-Clear
"""Exact, non-discovered semantic gate for the Phase 1 expected-red partition."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import unittest

from specchoice_evidence.canonical import canonical_json_bytes


RED_IDS = {
    "tests.test_fixture_closure.FixtureClosureCandidateTests.test_fixture_accept_publish_rejects_racing_empty_target_without_overwrite",
    "tests.test_fixture_closure.FixtureClosureCandidateTests.test_fixture_publish_fails_closed_when_no_replace_primitive_is_unavailable",
    "tests.test_fixture_closure.FixtureClosureCandidateTests.test_public_fixture_acceptance_rejects_missing_mismatched_and_stale_authority",
    "tests.test_fixture_closure.FixtureClosureCandidateTests.test_public_fixture_acceptance_resolves_its_own_current_v7_basis",
    "tests.test_receipts.IntegrityReceiptTests.test_active_defaults_are_v7_from_experiment_and_repository_roots",
}

FOCUSED_MODULES = (
    "tests.test_measurement_adapter",
    "tests.test_measurement_parsing",
    "tests.test_measurement_scoring",
    "tests.test_measurement_attempts",
    "tests.test_measurement_h1",
    "tests.test_filesystem_boundary",
)

_BOUNDARY_BLOCKER = "FIXTURE_CLOSURE_ACCEPTANCE_BOUNDARY_BLOCKING"
_EXPECTED_OUTCOMES = (
    (
        "failure",
        "tests.test_fixture_closure.FixtureClosureCandidateTests.test_fixture_accept_publish_rejects_racing_empty_target_without_overwrite",
        None,
        "LOCAL_ACCEPTED_TARGET_EXISTS",
        _BOUNDARY_BLOCKER,
    ),
    (
        "failure",
        "tests.test_fixture_closure.FixtureClosureCandidateTests.test_fixture_publish_fails_closed_when_no_replace_primitive_is_unavailable",
        None,
        "ATOMIC_NO_REPLACE_UNAVAILABLE",
        _BOUNDARY_BLOCKER,
    ),
    (
        "failure",
        "tests.test_fixture_closure.FixtureClosureCandidateTests.test_public_fixture_acceptance_rejects_missing_mismatched_and_stale_authority",
        "FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_MISMATCH",
        "FIXTURE_CLOSURE_ACCEPTANCE_REGISTRY_MISMATCH",
        _BOUNDARY_BLOCKER,
    ),
    (
        "failure",
        "tests.test_fixture_closure.FixtureClosureCandidateTests.test_public_fixture_acceptance_rejects_missing_mismatched_and_stale_authority",
        "FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH",
        "FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH",
        _BOUNDARY_BLOCKER,
    ),
    (
        "error",
        "tests.test_fixture_closure.FixtureClosureCandidateTests.test_public_fixture_acceptance_resolves_its_own_current_v7_basis",
        None,
        "specchoice_evidence.bundle.BundleError",
        _BOUNDARY_BLOCKER,
    ),
    (
        "failure",
        "tests.test_receipts.IntegrityReceiptTests.test_active_defaults_are_v7_from_experiment_and_repository_roots",
        None,
        "AssertionError: 1 != 0",
        "AssertionError: 1 != 0",
    ),
)


class _Capture:
    def __init__(self) -> None:
        self.binary = tempfile.TemporaryFile(mode="w+b")
        self.text = io.TextIOWrapper(self.binary, encoding="utf-8", newline="\n")

    def close(self) -> str:
        self.text.flush()
        self.binary.seek(0)
        value = self.binary.read().decode("utf-8", "replace")
        self.text.detach()
        self.binary.close()
        return value


def _flatten(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    tests: list[unittest.TestCase] = []
    for item in suite:
        tests.extend(_flatten(item) if isinstance(item, unittest.TestSuite) else [item])
    return tests


def _run(tests: list[unittest.TestCase]) -> tuple[dict[str, object], str]:
    runner = """
import io
import json
import sys
import tempfile
import unittest

ids = json.loads(sys.stdin.read())
capture_binary = tempfile.TemporaryFile(mode=\"w+b\")
capture_text = io.TextIOWrapper(capture_binary, encoding=\"utf-8\", newline=\"\\n\")
result = unittest.TextTestRunner(stream=capture_text, verbosity=0).run(
    unittest.defaultTestLoader.loadTestsFromNames(ids)
)
capture_text.flush()
capture_binary.seek(0)
payload = {
    \"errors\": [[test.id(), text] for test, text in result.errors],
    \"expected_failures\": [[test.id(), text] for test, text in result.expectedFailures],
    \"failures\": [[test.id(), text] for test, text in result.failures],
    \"output\": capture_binary.read().decode(\"utf-8\", \"replace\"),
    \"skipped\": [[test.id(), reason] for test, reason in result.skipped],
    \"tests_run\": result.testsRun,
    \"unexpected_successes\": [test.id() for test in result.unexpectedSuccesses],
}
capture_text.detach()
capture_binary.close()
sys.stdout.write(\"\\n__PHASE1_ORACLE_RESULT__\" + json.dumps(payload, sort_keys=True, separators=(\",\", \":\")))
"""
    completed = subprocess.run(
        [sys.executable, "-c", runner],
        input=json.dumps([test.id() for test in tests]),
        text=True,
        capture_output=True,
        check=False,
        start_new_session=True,
    )
    marker = "__PHASE1_ORACLE_RESULT__"
    prefix, found, encoded = completed.stdout.rpartition(marker)
    if completed.returncode or not found:
        raise SystemExit("ORACLE_RUNNER_INVALID")
    try:
        result = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise SystemExit("ORACLE_RUNNER_INVALID") from error
    diagnostics = prefix + completed.stderr + str(result.get("output", ""))
    return result, diagnostics


def _normalized_outcomes(result: dict[str, object]) -> list[dict[str, str]] | None:
    observed = [("failure", test_id, text) for test_id, text in result["failures"]]
    observed.extend(("error", test_id, text) for test_id, text in result["errors"])
    normalized: list[dict[str, str]] = []
    for kind, parent_id, subtest_code, expected, actual in _EXPECTED_OUTCOMES:
        matches = [
            (observed_kind, test_id, text)
            for observed_kind, test_id, text in observed
            if observed_kind == kind
            and test_id.startswith(parent_id)
            and (subtest_code is None or f"code='{subtest_code}'" in test_id)
            and expected in text
            and actual in text
        ]
        if len(matches) != 1:
            return None
        observed.remove(matches[0])
        normalized.append({
            "expected": expected,
            "id": parent_id if subtest_code is None else f"{parent_id} (code='{subtest_code}')",
            "kind": kind,
            "observed": actual,
        })
    return normalized if not observed else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-focused", required=True, type=int)
    parser.add_argument("--expected-discovered", required=True, type=int)
    parser.add_argument("--expected-green", required=True, type=int)
    args = parser.parse_args()
    loader = unittest.defaultTestLoader
    discovered = _flatten(loader.discover("tests", top_level_dir="."))
    focused = _flatten(unittest.TestSuite(loader.loadTestsFromName(name) for name in FOCUSED_MODULES))
    ids = {test.id() for test in discovered}
    if len(focused) != args.expected_focused or len(discovered) != args.expected_discovered or RED_IDS - ids or len(RED_IDS) != 5:
        raise SystemExit("ORACLE_DISCOVERY_PARTITION_INVALID")
    green = [test for test in discovered if test.id() not in RED_IDS]
    green_result, green_output = _run(green)
    if green_result["tests_run"] != args.expected_green or green_result["failures"] or green_result["errors"] or green_result["skipped"] or green_result["expected_failures"] or green_result["unexpected_successes"]:
        print(green_output, file=sys.stderr, end="")
        raise SystemExit("ORACLE_GREEN_PARTITION_INVALID")
    red = [test for test in discovered if test.id() in RED_IDS]
    red_result, red_output = _run(red)
    outcomes = _normalized_outcomes(red_result)
    if red_result["tests_run"] != 5 or len(red_result["failures"]) != 5 or len(red_result["errors"]) != 1 or red_result["skipped"] or red_result["expected_failures"] or red_result["unexpected_successes"] or outcomes is None:
        print(red_output, file=sys.stderr, end="")
        raise SystemExit("ORACLE_RED_OUTCOMES_INVALID")
    sys.stdout.buffer.write(canonical_json_bytes({
        "discovered": len(discovered), "focused": len(focused), "green": len(green),
        "red_ids": sorted(RED_IDS), "red_outcomes": outcomes,
        "status": "phase1_expected_red_oracle_passed",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
