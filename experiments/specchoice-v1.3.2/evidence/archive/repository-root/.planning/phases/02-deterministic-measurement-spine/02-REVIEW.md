---
phase: 02-deterministic-measurement-spine
reviewed: 2026-08-01T23:42:05Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - experiments/specchoice-v1.3.2/config/measurement/canonical-adjudication-schema-v1.json
  - experiments/specchoice-v1.3.2/config/measurement/h1-review-schema-v1.json
  - experiments/specchoice-v1.3.2/config/measurement/pr2164-adapter-rules-v1.json
  - experiments/specchoice-v1.3.2/fixtures/measurement/adversarial/required-diagnostics-v1.json
  - experiments/specchoice-v1.3.2/fixtures/measurement/golden-predictions-v1.json
  - experiments/specchoice-v1.3.2/reports/h1/adversarial-oracle-results-v1.json
  - experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v1.json
  - experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v1.md
  - experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v2/h1-source-gold-review-v2.json
  - experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v2/h1-source-gold-review-v2.md
  - experiments/specchoice-v1.3.2/reviews/h1-source-gold-decision-v1.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/attempt.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/case-outcomes.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/diagnostics.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/metrics.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/parsed-predictions.json
  - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v1/report.json
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/__init__.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/adapter.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/attempts.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/cli.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/diagnostics.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/domain.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/h1.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/preflight.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/scoring.py
  - experiments/specchoice-v1.3.2/src/specchoice_measurement/strict_json.py
  - experiments/specchoice-v1.3.2/tests/test_measurement_adapter.py
  - experiments/specchoice-v1.3.2/tests/test_measurement_attempts.py
  - experiments/specchoice-v1.3.2/tests/test_measurement_h1.py
  - experiments/specchoice-v1.3.2/tests/test_measurement_parsing.py
  - experiments/specchoice-v1.3.2/tests/test_measurement_scoring.py
findings:
  critical: 3
  warning: 1
  info: 0
  total: 4
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-01T23:42:05Z
**Depth:** standard
**Files Reviewed:** 32
**Status:** issues_found

## Summary

The submitted measurement files preserve the expected formal score and the focused unit suite passes, but the H1 trust chain is not shippable. The signed decision is detached from the current packet, and several transitive, score-bearing readers still bypass the descriptor-bound no-follow reader. Consequently, a symlink/FIFO substitution can still cause external-byte consumption or blocking in paths presented as fail-closed.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: The submitted approved H1 decision cannot validate against the current packet

**Classification:** BLOCKER

**File:** `experiments/specchoice-v1.3.2/reviews/h1-source-gold-decision-v1.json:1`

**Issue:** The decision binds packet SHA-256 `a897...`, which is the v1 packet, while the current valid v2 packet is `4482...`. `validate-h1-packet` succeeds for `reports/h1/h1-source-gold-review-v2/h1-source-gold-review-v2.json`, but validating that packet with this decision returns `H1_DECISION_BINDINGS_INVALID`. Conversely, the v1 packet returns `H1_BINDINGS_INVALID` because the validator recomputes v2 adversarial bindings. The repository therefore contains an artifact marked `aggregate_disposition: approved` whose signature chain cannot be validated by the current public validator.

**Fix:** Preserve the v1 decision as historical evidence; do not copy or reinterpret its signatures. After an independent human review of the v2 packet, create a new, explicitly versioned decision whose `packet_sha256` and `packet_bindings` exactly match the v2 packet. Until then, mark the current review disposition as incomplete/non-authoritative and add a regression that expects the new decision to reach `H1_MANUAL_AUTHORIZATION_REQUIRED` rather than a binding error.

### CR-02: H1 validation reaches canonical evidence and the schema through unsafe direct pathname reads

**Classification:** BLOCKER

**File:** `experiments/specchoice-v1.3.2/src/specchoice_measurement/cli.py:147`

**Affected:** `experiments/specchoice-v1.3.2/src/specchoice_measurement/cli.py:162`, `experiments/specchoice-v1.3.2/src/specchoice_measurement/attempts.py:92`, `experiments/specchoice-v1.3.2/src/specchoice_measurement/h1.py:113`

**Issue:** `_expected_bindings()` calls `validate_adversarial_report()`, which uses `_canonical_object()` and therefore `Path.read_bytes()` for the adversarial report, frozen oracle, and golden predictions. The same H1 path calls `validate_measurement_attempt()`, whose replay calls `_bindings()` and directly reads `_SCHEMA`; `_adversarial_bindings()` also directly reads its schema path. These reads occur outside `read_authoritative_file`, so a final-leaf symlink swap can consume external bytes and a FIFO can block the validator. The 02-08 H1 test patches only `specchoice_measurement.h1.read_authoritative_file`; it does not exercise these delegated consumers.

**Fix:** Make one descriptor-bound canonical-reader helper the only path for canonical report/oracle/golden/schema bytes. Pass an explicit checked root plus relative leaf (or a checked parent plus basename for CLI-supplied artifacts) into that helper, and use its returned bytes for parsing and every digest. Replace the direct schema reads in `_bindings()` and `_adversarial_bindings()`. Add public H1 regressions that replace the actual transitive report, oracle, golden, and schema leaves with a pre-open symlink and FIFO and verify a bounded H1 error without opening the target.

### CR-03: Adapter control artifacts remain vulnerable to symlink/FIFO substitution after validation

**Classification:** BLOCKER

**File:** `experiments/specchoice-v1.3.2/src/specchoice_measurement/adapter.py:35`

**Affected:** `experiments/specchoice-v1.3.2/src/specchoice_measurement/adapter.py:337`, `experiments/specchoice-v1.3.2/src/specchoice_measurement/adapter.py:341`

**Issue:** `_load_canonical_json()` uses `Path.read_bytes()` for rules, the Phase 2 authority, and the accepted-bundle registry. In particular, the authority is validated in a subprocess and then reopened through an unchecked pathname, creating a check/use gap. The registry is similarly reopened after bundle verification. An attacker who swaps either final leaf to a symlink before the reopen can redirect the adapter to external bytes; a FIFO blocks the scoring/H1 path instead of being rejected before open. This leaves the public adapter and H1's `_batch()` outside the asserted descriptor-bound custody boundary.

**Fix:** Change `_load_canonical_json()` to accept a checked root and relative path and obtain both canonical bytes and identity from `read_authoritative_file`. Use that helper for `rules_path`, `authority_path`, and the bundle registry, reusing only descriptor-returned bytes after validation. Add public adapter tests that perform actual immediate-before-open symlink swaps and FIFO substitutions for each control artifact, assert an invalid zero-record batch, and assert no external target is opened.

## Warnings

### WR-01: The new H1 regression validates the helper, not the public validators, for real symlink/FIFO leaves

**Classification:** WARNING

**File:** `experiments/specchoice-v1.3.2/tests/test_measurement_h1.py:186`

**Issue:** The symlink/FIFO loop invokes `read_authoritative_file(root, leaf.name)` directly on an unrelated `race-leaf.json`. It never substitutes `packet_path`, `markdown_path`, `decision_path`, `_SCHEMA`, or `_H1_SCHEMA` and then invokes `validate_h1_packet()`/`validate_h1_decision()`. The earlier loop only mocks the H1 module seam, so it cannot detect the transitive bypasses in CR-02. The test's public-boundary claim is therefore a false assurance.

**Fix:** For each real authority leaf, arrange the swap at the filesystem boundary immediately before its open and call the corresponding public validator. Assert the expected enclosing H1 error, no external sentinel consumption, and no FIFO open. Cover both H1-local and delegated readers.

---

_Reviewed: 2026-08-01T23:42:05Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
