---
phase: 02-deterministic-measurement-spine
verified: 2026-08-01T23:49:03Z
status: gaps_found
next_action: "Close the three custody/H1 gaps, preserve frozen evidence, then re-run verification."
next_command: "/gsd:plan-phase 02 --gaps"
score: "32/35 must-haves verified"
behavior_unverified: 0
overrides_applied: 3
re_verification:
  previous_status: gaps_found
  previous_score: "31/35"
  gaps_closed:
    - "The direct adapter raw-leaf, preflight fixture-source, and H1-local packet/Markdown/decision/schema inspect-then-read paths now use read_authoritative_file()."
    - "CR-01 formal-attempt lineage is rooted in a replay-validated formal/completed attempt."
    - "CR-02 preserves verified source identity and source/gold conflict provenance in an invalid zero-record batch."
  gaps_remaining:
    - "The current v2 H1 packet has no decision that validates against it."
    - "H1's delegated formal/adversarial validation still directly reopens canonical files and schemas by pathname."
    - "Adapter rules, authority, and registry control artifacts are still read by pathname after validation."
  regressions: []
overrides:
  - must_have: "No Phase 1 custody module, accepted bundle byte, registry byte, source-authority byte, core UDB schema, generated data, model, external API, publication state, or remote repository is modified."
    reason: "Accepted only for commit 9d641ec8 in experiments/specchoice-v1.3.2/src/specchoice_evidence/filesystem.py: its descriptor-bound read_authoritative_file() single-descriptor leaf-read TOCTOU hardening. No other Phase 1 file, custody weakening, semantic rewrite, evidence mutation, authority expansion, remote/publication action, modification, or exception is accepted."
    accepted_by: "developer"
    accepted_at: "2026-08-01T07:25:55.903Z"
  - must_have: "The focused four-module pre-H1 suite passes without modifying or weakening any Phase 1 custody module, accepted byte, source-authority record, or live-boundary assertion."
    reason: "Accepted only for commit 9d641ec8 in experiments/specchoice-v1.3.2/src/specchoice_evidence/filesystem.py: its descriptor-bound read_authoritative_file() single-descriptor leaf-read TOCTOU hardening. No other Phase 1 file, custody weakening, semantic rewrite, evidence mutation, authority expansion, remote/publication action, modification, or exception is accepted."
    accepted_by: "developer"
    accepted_at: "2026-08-01T07:25:55.903Z"
  - must_have: "The final five-module focused Phase 2 suite passes without modifying or weakening any Phase 1 custody module, accepted byte, source-authority record, or live-boundary assertion."
    reason: "Accepted only for commit 9d641ec8 in experiments/specchoice-v1.3.2/src/specchoice_evidence/filesystem.py: its descriptor-bound read_authoritative_file() single-descriptor leaf-read TOCTOU hardening. No other Phase 1 file, custody weakening, semantic rewrite, evidence mutation, authority expansion, remote/publication action, modification, or exception is accepted."
    accepted_by: "developer"
    accepted_at: "2026-08-01T07:25:55.903Z"
gaps:
  - truth: "The current H1 human decision is hash-bound to the active H1 v2 packet and can represent the independently reviewed local-only disposition."
    status: failed
    reason: "The only approved decision binds packet_sha256 a897029b..., while the active validated packet is 4482bfe4.... The public validator rejects v2 plus that decision with H1_DECISION_BINDINGS_INVALID; v1 itself rejects with H1_BINDINGS_INVALID."
    artifacts:
      - path: "experiments/specchoice-v1.3.2/reviews/h1-source-gold-decision-v1.json"
        issue: "Historical v1 bindings do not match the current v2 packet/adversarial evidence."
      - path: "experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v2/h1-source-gold-review-v2.json"
        issue: "Current packet validates, but no validating human decision is present."
    missing:
      - "Preserve the v1 decision as historical evidence; after machine custody gaps are fixed, obtain an independently human-authored, explicitly versioned v2 decision bound to the v2 packet and its bindings."
  - truth: "Every H1 evidence and canonical control leaf is consumed only through the descriptor-bound no-follow reader before parsing or hashing."
    status: failed
    reason: "H1 delegates to cli.validate_adversarial_report() and attempts.validate_measurement_attempt(); these paths retain direct Path.read_bytes() calls for the adversarial report/oracle/golden input and schema. The local 02-08 seam test cannot exercise those real delegated reads."
    artifacts:
      - path: "experiments/specchoice-v1.3.2/src/specchoice_measurement/cli.py"
        issue: "_canonical_object() line 147 and _adversarial_bindings() line 162 reopen report/oracle/golden/schema paths."
      - path: "experiments/specchoice-v1.3.2/src/specchoice_measurement/attempts.py"
        issue: "_bindings() line 92 directly reopens schema_path."
    missing:
      - "Use a descriptor-bound canonical reader for the delegated report, oracle, golden, and schema leaves, then add public v2 H1 symlink/FIFO regressions that replace those actual leaves."
  - truth: "The accepted-v2 adapter consumes authority, rules, and registry control artifacts from descriptor-bound bytes after their validation."
    status: failed
    reason: "adapter._load_canonical_json() line 35 uses Path.read_bytes() for rules, source authority, and registry. Authority is first validated in a subprocess and subsequently reopened by pathname, leaving a check/use gap before score-bearing raw leaf processing."
    artifacts:
      - path: "experiments/specchoice-v1.3.2/src/specchoice_measurement/adapter.py"
        issue: "_load_canonical_json() is called for rules, authority, and bundle registry without read_authoritative_file()."
    missing:
      - "Read rules, authority, and registry from explicit checked roots and relative paths; add public symlink/FIFO regressions for each real control artifact and require an invalid zero-record batch."
---

# Phase 2: Deterministic Measurement Spine Verification Report

**Phase Goal:** As a human RISC-V reviewer, I want to trust the experiment's adjudication semantics and diagnostics, so that I can review the measurement spine before any frame, retrieval, or model result is considered.

**Verified:** 2026-08-01T23:49:03Z
**Status:** gaps_found  
**Re-verification:** Yes — after Plan 02-08

## Escalation Gate

The phase does not achieve its trust goal. Plans 02-07 and 02-08 correctly fixed the prior direct raw-leaf paths and strengthened formal-lineage/conflict provenance. However, the active review chain still has three observable defects: the sole approved decision is detached from the current v2 packet, H1 reaches unprotected delegated readers, and the adapter reopens its authority/rules/registry controls by pathname.

These are blockers, not uncertainty: the public v2 decision command exits 2 with `H1_DECISION_BINDINGS_INVALID`; the v1 packet exits 2 with `H1_BINDINGS_INVALID`; and the remaining direct readers are present in the active call paths. Passing normal-path tests and frozen-artifact validators do not prove a symlink/FIFO-safe custody boundary.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| --- | --- | --- | --- |
| Inspect the frozen source/gold semantics | One accepted-v2 11-fixture/28-raw authority is active. | Source-authority validator returned `valid`, 11 fixtures, and 28 raw files. | ✓ VERIFIED |
| Score the golden input | Six positives accept, four negatives remain unsurfaced, and the candidate is surfaced then `classify_out`. | Focused 64-test suite passed; formal attempt is `formal/completed`. | ✓ VERIFIED |
| Reject noncanonical input | Unknown/invalid/duplicate/conflicting predictions and noncanonical no-findings fail without repair. | Parsing and scoring suites pass under the closed schema/preflight path. | ✓ VERIFIED |
| Trace diagnostics and source evidence | Diagnostics and evidence are stable and originate only from accepted, descriptor-bound bytes. | Raw fixture and preflight paths are protected, but adapter controls and H1's delegated inputs can be reopened by pathname. | ✗ FAILED — BLOCKER |
| Review the current packet | The human can approve/dispute the active packet without model output or publication authority. | v2 packet validates and remains local-only, but the approved v1 decision fails against it. | ✗ FAILED — BLOCKER |
| Outcome | A reviewer can trust the measurement spine before later work. | Current H1/custody gaps leave the trust chain incomplete. | ✗ FAILED — BLOCKER |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | TS-03 scores the exact accepted-v2 all-11 golden set, including candidate surfaced-then-`classify_out`. | ✓ VERIFIED | 64 focused tests pass; formal attempt and authority validate. |
| 2 | TS-04 strictly rejects unknown, invalid, duplicate, and noncanonical no-finding inputs without repair. | ✓ VERIFIED | `strict_json.py`/`preflight.py` are substantive and the parsing suite passes. |
| 3 | TS-05 emits stable structured diagnostics and preserves `ACCEPTED_PARAMETER_NAME_MISSING` as warning-only. | ✓ VERIFIED | Scoring/adversarial validators pass and use a diagnostic-only report. |
| 4 | Formal/adversarial lineage requires a verified `formal/completed` attempt and conflict batches retain provenance with zero records. | ✓ VERIFIED | The named Plan 02-07 regressions are in the 64-test focused suite; stored v2 report validates with `--formal-attempt`. |
| 5 | Raw fixture leaves and preflight fixture sources use descriptor-returned bytes. | ✓ VERIFIED | `adapter._raw_identity()` and `preflight._source_bytes_by_fixture()` call `read_authoritative_file()`; their public regressions pass. |
| 6 | H1's entire evidence path, including delegated readers, is descriptor-bound. | ✗ FAILED — BLOCKER | `cli.py:147,162` and `attempts.py:92` retain active `Path.read_bytes()` readers reached by `_expected_bindings()`. |
| 7 | Adapter authority/rules/registry controls are descriptor-bound after validation. | ✗ FAILED — BLOCKER | `adapter.py:35` reopens each control artifact through `_load_canonical_json()`. |
| 8 | The active H1 packet has a validating local-only human decision. | ✗ FAILED — BLOCKER | v2 plus approved v1 decision returns `H1_DECISION_BINDINGS_INVALID`; v1 no longer validates either. |
| 9 | Frozen authority and stored formal/adversarial/H1 artifacts remain valid without regeneration. | ✓ VERIFIED | Authority, formal attempt, v2 adversarial report, and v2 packet/Markdown validators all exit 0. |
| 10 | No protected evidence/core-UDB boundary was changed by 02-08, except the accepted prior `filesystem.py` override. | ✓ PASSED (override) | `git diff --name-only bdc6e0a3..HEAD` is empty for accepted bundle, authority, formal/adversarial/H1/decision evidence, baselines, allowlist, Phase 1, `spec`, and `gen`. |
| 11 | The 64-test focused partition and 135-method phase-aware discovery partition remain present. | ✓ VERIFIED | Focused suite exits 0; discovery enumerates 135 methods. The full discovery run preserves the planned five expected-red failures plus one error. |
| 12 | The Phase 2 MVP goal is a valid user story and does not alter its success-criteria contract. | ✓ VERIFIED | `user-story.validate` returned `true`; `roadmap.get-phase 2` exposes the unchanged four criteria. |

**Score:** 32/35 de-duplicated plan must-haves verified. The three existing developer-accepted Phase 1 `filesystem.py` exceptions are counted as `PASSED (override)`.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `phase2/source-authority.json` and accepted-v2 bundle | Exact local 11/28 authority | ✓ VERIFIED | Validator returns the pinned generation, identity, and counts. |
| `strict_json.py`, `diagnostics.py`, `preflight.py`, `scoring.py` | Closed canonical input and deterministic outcomes | ✓ VERIFIED | Substantive, wired, and covered by focused tests. |
| `adapter.py` | Accepted-only adapter with descriptor-bound authority and raw inputs | ✗ PARTIAL — BLOCKER | Raw leaves are protected, but rules/authority/registry controls are not. |
| `attempts.py`, `cli.py`, v2 adversarial report | Immutable formal and diagnostic-only evidence | ✗ PARTIAL — BLOCKER | Normal validators pass; delegated canonical/schema reads are pathname-based. |
| `h1.py`, v2 packet/Markdown, v1 decision | Hash-bound local-only review material | ✗ PARTIAL — BLOCKER | Packet/Markdown validate; no current decision validates. |
| Plan 02-08 tests | Public custody regressions | ⚠️ INCOMPLETE COVERAGE | Tests cover local seams but do not substitute the transitive H1 or adapter-control leaves. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Source authority/rules/registry | Adapter batch | Authority validation plus canonical control reads | ✗ PARTIAL — BLOCKER | Subsequent `_load_canonical_json()` opens by pathname. |
| Accepted raw leaves | Adapter/preflight | `read_authoritative_file()` bytes | ✓ WIRED | Raw and fixture-source consumers use the descriptor-bound reader. |
| Formal attempt | Adversarial report | Explicit replay-validated `--formal-attempt` | ✓ WIRED | Stored v2 report validates. |
| Formal/adversarial evidence | H1 packet | `_expected_bindings()` | ✗ PARTIAL — BLOCKER | Delegated validation reaches direct canonical/schema reads. |
| Active H1 packet | Human decision | `validate_h1_decision()` recomputes bindings | ✗ NOT WIRED — BLOCKER | The only decision is bound to the invalid/superseded v1 packet. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| Adapter batch | 11 records / 28 raw identities | Active accepted-v2 bundle | Yes | ⚠️ UNSAFE CONTROL FLOW |
| Preflight evidence map | Fixture source bytes | Descriptor-bound accepted-bundle leaves | Yes | ✓ FLOWING |
| Formal/adversarial chain | Formal attempt and diagnostic oracle | Stored canonical artifacts | Yes on normal input | ⚠️ UNSAFE TRANSITIVE READ |
| H1 review | Packet, Markdown, decision, bindings | Current v2 packet plus historical v1 decision | Packet flows; human-decision chain does not | ✗ DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Focused measurement/filesystem suite | `python3 -m unittest tests.test_measurement_adapter ... tests.test_filesystem_boundary -q` | 64 tests passed | ✓ PASS |
| Active source authority | `specchoice_evidence.cli validate-phase2-source-authority ...` | `status: valid`, 11 fixtures, 28 raw files | ✓ PASS |
| Formal attempt | `specchoice_measurement.cli validate-attempt ...` | `formal/completed`, digest `c81649...` | ✓ PASS |
| Explicit formal adversarial report | `validate-adversarial-report --formal-attempt ...` | v2 diagnostic-only report valid | ✓ PASS |
| H1 v2 packet/Markdown | `validate-h1-packet ...v2...` | exit 0 | ✓ PASS |
| Current H1 decision | `validate-h1-decision --packet ...v2... --decision ...v1...` | `H1_DECISION_BINDINGS_INVALID`, exit 2 | ✗ FAIL |
| Historical H1 v1 packet | `validate-h1-packet ...v1...` | `H1_BINDINGS_INVALID`, exit 2 | ✗ FAIL |
| Discovery partition | `unittest.defaultTestLoader.discover("tests")` | 135 methods enumerated; full discovery retains the expected five failures and one error | ✓ PASS |

### Probe Execution

No declared or conventional `scripts/*/tests/probe-*.sh` probe exists. **SKIPPED (no phase probe entry points).**

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| TS-03 | 02-01, 02-03 through 02-08 | Versioned accepted-v2 adapter and deterministic all-11 golden runner | ✗ BLOCKED | Normal scoring is correct, but score-bearing adapter control artifacts can escape the required no-follow custody boundary. |
| TS-04 | 02-02, 02-04 through 02-08 | Closed canonical adjudication schema and no silent repair | ✓ SATISFIED | Closed-schema/preflight tests pass; no control gap changes the parser's rejection semantics. |
| TS-05 | 02-02 through 02-08 | Stable structured diagnostics and warning-only accepted-name absence | ✗ BLOCKED | H1/adversarial diagnostic evidence can be reached through unprotected delegated reads; current H1 decision is not bound. |

All requirement IDs declared by Plans 02-01 through 02-08 are TS-03, TS-04, or TS-05, and all three map to Phase 2 in `REQUIREMENTS.md`; no orphaned Phase 2 requirement was found. No later roadmap phase specifically schedules these custody/H1 repairs, so they are not deferred.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `src/specchoice_measurement/adapter.py` | 35 | `Path.read_bytes()` for authority/rules/registry controls | 🛑 BLOCKER | Check/use gap permits symlink/FIFO substitution before score-bearing processing. |
| `src/specchoice_measurement/cli.py` | 147, 162 | Direct canonical/schema pathname reads | 🛑 BLOCKER | H1 reaches these via adversarial validation. |
| `src/specchoice_measurement/attempts.py` | 92 | Direct schema pathname read | 🛑 BLOCKER | H1 reaches this through formal-attempt replay. |
| `tests/test_measurement_h1.py` | 150 | Local seam mock plus unrelated leaf race test | ⚠️ WARNING | Passes without exercising actual delegated H1 readers. |

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, placeholder, or empty production implementation was found. The excluded untracked review-copy file and ambient `.DS_Store` files were not read, used, or modified.

### Gaps Summary

One goal-blocking concern remains in three connected forms:

1. **Current H1 authority is incomplete.** Preserve the historical v1 decision and obtain a new independent v2 decision only after its custody chain is repaired.
2. **H1's descriptor boundary is incomplete.** Extend descriptor-bound reads beyond the local H1 functions into the delegated formal/adversarial validation paths.
3. **Adapter control artifacts bypass custody.** Bind rules, authority, and registry reads to one checked descriptor, then test real swaps/special files at the public builder.

The normal 64-test suite and frozen validators demonstrate baseline functionality; they do not disprove these defects because the relevant public leaf substitutions are absent from the tests.

---

_Verified: 2026-08-01T23:49:03Z_
_Verifier: the agent (gsd-verifier)_
