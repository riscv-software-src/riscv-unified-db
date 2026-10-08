---
phase: 02-deterministic-measurement-spine
plan: 16
subsystem: measurement-custody
tags: [python, anti-rollback, active-v3, formal-measurement, adversarial, h1]
requires:
  - phase: 02-15
    provides: explicit active-v3 measurement and H1 validation contracts
provides:
  - Canonical anti-rollback revocation and exact reviewed active-v3 authority
  - Immutable formal-v2 and diagnostic-only adversarial-v3 evidence
  - Decision-free H1 packet-v3 bound to the active-v3 evidence graph
affects: [02-17, measurement-reporting, human-h1-review]
tech-stack:
  added: []
  patterns: [forward-only exact-byte cutover resume, explicit active-v3 controls, immutable successor evidence]
key-files:
  created:
    - experiments/specchoice-v1.3.2/receipts/fixture-closure-revocation-v2.json
    - experiments/specchoice-v1.3.2/runs/measurement-attempts/formal-golden-pr2164-v2/
    - experiments/specchoice-v1.3.2/reports/h1/adversarial-oracle-results-v3.json
    - experiments/specchoice-v1.3.2/reports/h1/adversarial-oracle-results-v3-attempts/
    - experiments/specchoice-v1.3.2/reports/h1/h1-source-gold-review-v3/
  modified:
    - experiments/specchoice-v1.3.2/phase2/source-authority.json
key-decisions:
  - "Public cutover owner resumed only as already_activated after exact authority and revocation comparisons."
  - "Successor evidence used explicit active-v3 authority, accepted-v3 bundle, canonical revocation, golden-v2, and oracle-v2 controls."
  - "H1 packet-v3 remains decision-free and external_publication_authorized=false; Plan 17 retains the human gate."
patterns-established:
  - "Do not regenerate a completed successor artifact: validate held bytes and continue only from its exact valid state."
requirements-completed: [TS-03, TS-04, TS-05]
coverage:
  - id: D1
    description: Canonical revocation and active-v3 authority match reviewed pending bytes and validate as active.
    requirement: TS-03
    verification:
      - kind: other
        ref: specchoice_evidence.cli validate-phase2-source-authority --authority-mode active
        status: pass
    human_judgment: false
  - id: D2
    description: Formal-v2 and diagnostic-only adversarial-v3 are bound to the active-v3 source and validate with golden-v2/oracle-v2.
    requirement: TS-04
    verification:
      - kind: integration
        ref: specchoice_measurement.cli validate-attempt and validate-adversarial-report
        status: pass
    human_judgment: false
  - id: D3
    description: Decision-free packet-v3 validates against held formal/adversarial evidence and explicit active-v3 controls.
    requirement: TS-05
    verification:
      - kind: integration
        ref: specchoice_measurement.cli validate-h1-packet
        status: pass
    human_judgment: false
duration: 11min
completed: 2026-08-02
status: complete
---

# Phase 02 Plan 16: Forward-Only Active-v3 Evidence Summary

**Exact active-v3 authority and anti-rollback revocation now bind immutable formal-v2, diagnostic-only adversarial-v3, and decision-free H1 packet-v3 evidence.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-02T14:34:22Z
- **Completed:** 2026-08-02T14:45:00Z
- **Tasks:** 1
- **Files modified:** 47 evidence and authority files

## Accomplishments

- Rechecked the public cutover owner; it returned `{"status":"already_activated"}` without changing the protected authority or revocation bytes.
- Validated the active authority against accepted verifier-rooted-v3, then generated and validated formal-v2 exactly once.
- Generated and validated the diagnostic-only adversarial-v3 report from the held formal-v2 attempt.
- Built and validated the decision-free H1 packet-v3 with explicit schema-v2, active-v3, golden-v2, and oracle-v2 controls.

## Task Commits

Plan implementation commits already present at the execution baseline include `c67d526b` through `8e7e69c6` (active-v3 custody, successor inputs, H1 validation context, readiness binding, and focused fixture migration). The final artifact commit records this summary and the exact evidence leaves.

## Evidence Identities

- Active authority and pending-v3 authority: `e1681a347a6d9cbdf6d0f19863b4d2856a36663949fcc0a6f4d2960c5dd8e6d1`.
- Canonical revocation and pending transition: `472bc06268c2e7c70d6975717f9d0f60b14e1a495cbca73342e9effe7bb33543`.
- Formal-v2 internal `attempt_sha256`: `5af7673e4b02cbafac57336805a28cb245466abe23450953d01452efc2bd655d`; canonical `attempt.json` bytes: `dbdcea065674051c22facbb2b18e384db23e7b855fb65978fd4ebe4d38140b3d`.
- Adversarial-v3 canonical report bytes: `326ddbf2de9e4a0888fd0cc6da5ef00c34330060f594ceb047be1b8ee5b36cd0`.
- H1 packet-v3 internal `packet_sha256`: `65b4a3a0f1d1df32112cd7e8f9080ae247a704368756295273b52a6d99111aad`; canonical JSON bytes: `6b421c758b47e5ce4796b2a95ca26ed00bc0977468f388542df48130948a495e`; Markdown bytes: `7e9a0af5421df995107d9747fe6cac75ea8a4df72e4429c30200c38e29adc0a6`.

## Verification

- `validate-phase2-source-authority --authority-mode active` — passed with `eligible: true`, 11 fixtures, 28 raw files, and accepted-v3 identity.
- `validate-attempt` for `formal-golden-pr2164-v2` — passed as completed.
- `validate-adversarial-report` for `adversarial-oracle-results-v3.json` — passed as diagnostic-only with all 12 oracle cases matched.
- `validate-h1-packet` for H1 packet-v3 — passed with `external_publication_authorized: false`.
- `phase1_expected_red_oracle.py --expected-focused 72 --expected-discovered 150 --expected-green 145` — passed before and after successor evidence creation.
- Exact `cmp` and SHA-256 checks confirmed the active authority equals pending-v3 and canonical revocation equals the pending transition both before and after evidence production.

## Decisions Made

- No public or private readiness receipt, human disposition, model run, deployment, or external publication was created.
- The forward-only invariant remains: if a future successor check fails, active-v3 and all already-valid evidence stay intact; v2 is never restored.

## Deviations from Plan

### Execution Recovery

**1. [Rule 3 - Blocking environment] Resolved unavailable `python3` command lookup without installing dependencies**
- **Found during:** Preflight.
- **Issue:** The login shell reported `python3` unavailable even though the repository's existing Homebrew Python 3.14.5 was present.
- **Fix:** Used `/opt/homebrew/bin/python3` for every public validator and evidence command.
- **Verification:** All required validators and the 72/150/145 oracle passed.

**2. [Controlled cleanup] Removed an agent-created empty packet target directory before the sole successful packet build**
- **Found during:** Packet-v3 build.
- **Issue:** An empty directory was mistakenly pre-created at the public builder's output target, which correctly rejected it with `H1_OUTPUT_EXISTS` before writing any packet file.
- **Fix:** Root independently verified it had no children and removed exactly that empty non-evidence directory with `rmdir`; no artifact was overwritten, regenerated, or deleted.
- **Verification:** The subsequent single public `build-h1-packet` invocation wrote and validated the packet-v3 JSON and Markdown.

**Total deviations:** 2; neither changed reviewed authority/revocation bytes or evidence semantics.

## Known Stubs

None.

## Next Phase Readiness

Plan 17 remains the required human gate. Phase 2 is not claimed complete here: H1 human review/decision and the four fresh reports remain intentionally out of scope.

## Self-Check: PASSED

- Confirmed all formal-v2 (6), adversarial-v3 attempt (36), and H1 packet-v3 (2) files exist.
- Confirmed the protected hashes and all three public evidence validators after the final oracle run.

---
*Phase: 02-deterministic-measurement-spine*
*Completed: 2026-08-02*
