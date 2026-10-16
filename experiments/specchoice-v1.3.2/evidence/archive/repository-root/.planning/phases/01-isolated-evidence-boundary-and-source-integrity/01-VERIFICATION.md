---
phase: 01-isolated-evidence-boundary-and-source-integrity
verified: 2026-07-31T12:31:45Z
status: passed
score: 12/12 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 9/10
  gaps_closed:
    - "The downstream source bundle contains the complete, exact PR #2164 fixture input: 11 fixture directories and 28 authoritative raw files."
    - "The accepted bundle independently enforces bidirectional registry/core/raw closure and cannot be accepted without the current v7 boundary gate."
  gaps_remaining: []
  regressions: []
---

# Phase 1: Isolated Evidence Boundary and Source Integrity Verification Report

**Phase Goal:** The operator and reviewer can work from a self-contained experiment boundary whose public source identity is independently verifiable.

**Verified:** 2026-07-31T12:31:45Z
**Status:** passed
**Re-verification:** Yes — after complete PR #2164 fixture-closure and acceptance-gate repair.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Prototype work remains isolated to `experiments/specchoice-v1.3.2/` plus the narrow Phase 1 control files. | ✓ VERIFIED | `git diff --name-only 54cda4f5..07210440` outside the experiment and `.planning/` controls returned zero paths. `git diff --check` is clean. |
| 2 | The frozen PR #2164 identity is locally provable. | ✓ VERIFIED | Local commit `22e84458c87a7ccf4c07034de1eb6d0bf9764144`, tree `af003b427c66bd8ac9803a91b3bf363a1b1304d9`, and `refs/specchoice/pr-2164-head` were present and equal/reachable; the registry test also verifies Git blob identity. |
| 3 | The exact downstream fixture source is the finite 11-directory/28-raw-file PR #2164 universe. | ✓ VERIFIED | `fixture-registry-pr2164-v1.json` declares 11 sorted IDs and 28 files. Independent replay compared every accepted-v2 raw file to its pinned Git blob, length, and SHA-256: `checked_raw_files:28`, `all_git_bytes_match_accepted:true`. |
| 4 | Missing, extra, malformed, path-escaping, special, or re-canonicalized subset fixtures fail closed. | ✓ VERIFIED | The embedded verifier's `_verify_fixture_closure` enforces the fixed fixture names/classes/roles and bidirectional registry/core tuple equality; the 92-test suite includes empty/missing/extra/duplicate/role/path/hash tests and `test_recanonicalized_subset_fails_embedded_fixture_closure`. |
| 5 | Candidate and accepted states are distinct; only the active accepted v2 generation is downstream eligible. | ✓ VERIFIED | Candidate v2 verifies as `status:candidate`; accepted `source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2` verifies as `status:accepted`, `downstream_eligible:true`, `external_publication_authorized:false`. Historical v1 is preserved but explicitly revoked from downstream authority by `fixture-closure-revocation-v1.json`. |
| 6 | Local acceptance cannot bypass canonical authority or the live v7 zero-blocker boundary. | ✓ VERIFIED | `accept_fixture_closure_candidate()` internally resolves and validates v7 lineage, calls `check_current_boundary()`, validates the canonical decision against candidate identity/registry/basis, then stages and verifies before publication. Negative tests cover missing, mismatched, stale, and boundary-violating authority. Current v7 gate returned `blocking_violations:0`. |
| 7 | Generation publication never overwrites an existing target, including a race-created target. | ✓ VERIFIED | `_publish_directory_no_replace()` has only native no-replace operations (`renameatx_np(RENAME_EXCL)`, `renameat2(RENAME_NOREPLACE)`, or non-replacing `MoveFileExW`); unavailable primitives fail closed. The fixture-closure suite tests empty/nonempty target races and target preservation. |
| 8 | Accepted-bundle verification is standalone and needs no Git, network, repository module, or `PYTHONPATH`. | ✓ VERIFIED | A copied v2 accepted bundle, outside the repository, ran `verify_bundle.py` using only `/opt/homebrew/bin/python3` with `env -i PATH=/nonexistent`; it returned `bundle verified` / exit 0. |
| 9 | Existing generations and prior receipts remain immutable. | ✓ VERIFIED | The historical PR #2192 accepted manifest still hashes to `be220c0a858ac6d018dd48015a39e5ea1b68f75af21ad91ca13335eab3e6bebd`. `git diff --exit-code da9d8fb2..07210440` found no changes to v1 candidate/accepted trees or v8 receipts. |
| 10 | The current Phase 2 source authority is an exact, local-only pin. | ✓ VERIFIED | `phase2/source-authority.json` validates against accepted v2 and binds generation, root `6a682538…`, manifest `73b25a28…`, registry `ddda6f6c…`, commit/tree, and 11/28 counts; its `local_only:true` and `external_publication_authorized:false` fields are enforced. |
| 11 | The standalone-first environment and 90-minute fallback policy remain reproducible without probing the UDB toolchain. | ✓ VERIFIED | Canonical environment decision/receipt controls are exercised by nine environment tests; the final v9 integrity receipt records `environment:standalone_first` and no external publication authority. |
| 12 | The current boundary remains auditable without attributing or blocking pre-existing OS metadata. | ✓ VERIFIED | v7 boundary result has 0 blockers. All twelve `.DS_Store` paths remain visible as `new_out_of_boundary`, `attributed_to_phase:false`, `blocking:false`, with `DS_STORE_IGNORED_OS_METADATA`; ordinary out-of-boundary paths remain blocking in tests. |

**Score:** 12/12 truths verified (0 present-but-behavior-unverified).

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `config/fixture-registry-pr2164-v1.json` | Exact PR #2164 source inventory | ✓ VERIFIED | Canonical 11-fixture/28-raw registry with pinned commit/tree and per-file path, role, length, and SHA-256. |
| `bundles/accepted/source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2/` | Self-sufficient downstream source generation | ✓ VERIFIED | 28 independently readable raw files, canonical manifests, registry, and rooted stdlib verifier. Root SHA-256: `6a682538c35d678b15852963e4f8f5316ee84d184f6a96a7996133be3de02f6d`. |
| `baselines/phase-start-v7-fixture-closure.json` | Immutable current boundary baseline | ✓ VERIFIED | SHA-256 `b338372c74c605aa8b294ee30bcc39410422a6a5673e15061f86f28188debecb`; validated with its exact allowlist/restart lineage. |
| `receipts/local-acceptance-v9.json` and `integrity-receipt-v9.json` | Local-only acceptance and authoritative closure receipt | ✓ VERIFIED | Decision binds candidate identity/registry/v7 basis; v9 JSON receipt is `outcome:pass`, self-hash `e5ec85a81b10ea0c8b466adaa88e44c6b3143b3aa5cb605c85c5ce8dd6364453`, publication false. |
| `phase2/source-authority.json` | Phase 2 input pin, not Phase 2 implementation | ✓ VERIFIED | Only source authority artifacts exist under `phase2/`; no evaluator, scoring, model, or Phase 2 planning work was started. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- |
| Registry | Accepted bundle raw tree | Embedded verifier | ✓ WIRED | Registry parses the exact finite set and must equal the manifest inventory; every tuple is rehashed from accepted bytes. |
| Acceptance decision | Candidate and current boundary | `accept_fixture_closure_candidate()` | ✓ WIRED | Canonical identity/basis/registry match and `check_current_boundary()` precede staging or target publication. |
| Accepted bundle | Phase 2 source authority | `validate-phase2-source-authority` | ✓ WIRED | Command passed with exact generation/root/manifest/registry/commit/tree/counts and local-only flags. |
| Candidate/accepted staging tree | Immutable generation path | `_publish_directory_no_replace()` | ✓ WIRED | Native exclusive rename is the only completed-generation publication path; collision and unavailable-primitive paths reject. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Full custody implementation | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v` | 92 tests passed | ✓ PASS |
| Current boundary | `check-boundary --baseline phase-start-v7-fixture-closure.json --reviewed-revision HEAD` | 0 blockers; `.DS_Store` visible/non-attributed/nonblocking | ✓ PASS |
| Active accepted generation | `verify-accepted --bundle …-v2` | Accepted identity/root verified | ✓ PASS |
| Phase 2 source pin | `validate-phase2-source-authority --authority phase2/source-authority.json --bundle …-v2` | Exact 11/28, commit/tree, manifest/root/registry binding valid | ✓ PASS |
| Offline copied replay | `env -i PATH=/nonexistent python3 verify_bundle.py` | `bundle verified`, exit 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| --- | --- | --- | --- |
| TS-01 | Isolated experiment boundary with provenance and integrity controls | ✓ SATISFIED | v7 baseline/allowlist, regular-file policy, standalone environment, immutable receipts, and zero-blocker current boundary. |
| TS-02 | Independently verifiable frozen public source inputs | ✓ SATISFIED | Pinned PR proof, per-byte 11/28 registry closure, immutable accepted v2 generation, and no-Git/no-network copied replay. |

### Anti-Patterns Found

None. The final changed implementation/test paths had no `TBD`, `FIXME`, `XXX`, placeholder, or unimplemented markers; `git diff --check` is clean.

### Probe Execution

No separate shell probe is declared for this phase. The custody CLI verification commands and the standalone copied-bundle verifier above are the runnable Phase 1 probes and were executed independently.

## Gaps Summary

No blocking gaps remain. The previous Phase 2 input-completeness blocker is closed by the immutable accepted v2 generation. Phase 2 may consume only the pinned `phase2/source-authority.json` generation; this verification does not authorize Phase 2 execution, external publication, push, PR creation, or model calls.

---

_Verified: 2026-07-31T12:31:45Z_
_Verifier: the agent (gsd-verifier)_
