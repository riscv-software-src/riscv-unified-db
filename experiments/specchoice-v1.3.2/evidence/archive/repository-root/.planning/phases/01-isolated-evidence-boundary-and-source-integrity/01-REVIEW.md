---
phase: 01-isolated-evidence-boundary-and-source-integrity
reviewed: 2026-07-31T12:23:15Z
depth: deep
files_reviewed: 2
files_reviewed_list:
  - experiments/specchoice-v1.3.2/src/specchoice_evidence/bundle.py
  - experiments/specchoice-v1.3.2/tests/test_fixture_closure.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-31T12:23:15Z
**Depth:** deep
**Files Reviewed:** 2
**Status:** clean

## Summary

The prior v6 authorization review was clean. The subsequent plans 01-06/01-07 gap-closure
defects and their fixes are documented below; final re-review found no remaining issues.

## Narrative Findings (AI reviewer)

Historic gap-closure findings and their resolution are recorded below so prior evidence
remains distinguishable from the final clean verdict.

## Verified Controls

- Old v6 authority is blocked before writes in both `write-local-mvp-receipt` and `accept-local-mvp`; a canonicalized v6 receipt also cannot reach finalization through an external output path, and the finalizer's shared delta check rejects the old v6 decision.
- The gate compares uncollapsed committed events from the full reviewed-revision-to-HEAD history plus staged, worktree, and untracked state. Disposable Git tests confirmed that add/delete histories for source, test, bundle, and receipt paths still block; staged/worktree/untracked changes also block.
- Exact issuance artifacts and the baseline's `future_control_exact_files` can be committed after the reviewed revision and replayed successfully. A path escape, symlink to an external path, absolute external path, and a control-file path supplied as a receipt all fail closed.
- The new current-reviewed temporary decision round trip writes and finalizes successfully with only its exact three issuance artifacts. This is test-only evidence; no v7 decision or receipt has been generated.
- Canonical restart-lineage mapping remains portable for default, absolute, and relative inputs; writer and finalizer use the same four experiment-relative paths. The three v6 evidence files are unchanged since `2ae36b46`, and raw v6 remains non-finalizable with `RESTART_LINEAGE_PROJECTION_MISMATCH`.
- Revision-pinned basis validation, historical schema-2/schema-3 rejection, per-commit A/M/D/T preservation, proposal-only behavior, and current boundary checks remain intact. The accepted generation's identity hashes remain unchanged and external publication authorization remains false.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v` — 76 tests passed.
- Disposable-Git history/live/absolute-path probe — passed.
- Escape, symlink, and control-path probe — passed.
- Issuance-artifact plus future-control committed replay probe — passed.
- `check-boundary --reviewed-revision 2d0c0436805fb7913540aa5322711a33c2426ab6` — zero blocking violations.
- v6 immutability, active restart validation, accepted-bundle verification, and `git diff --check b39bbc9b^..2d0c0436` — passed.

## Authorization Checkpoint

The implementation is clean and may enter the new v7 exact-basis human-authorization checkpoint. This is not finalization: compute the proposal at the intended full reviewed revision, obtain an immutable human schema-3 decision binding that basis, then generate and finalize the v7 receipt. No v7 decision or receipt exists yet.

---

_Reviewed: 2026-07-31T08:42:12Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_

---

## Gap-Closure Review (plans 01-06 and 01-07)

**Reviewed:** 2026-07-31T09:18:00Z
**Depth:** deep
**Scope:** commits `7a985abe`, `7fd22d46`, `6515e74f`, and `da9d8fb2`, including the
v3 candidate/accepted trees, embedded verifier, registry, v7 lineage controls, receipts,
and Phase 2 source authority.

### Verdict

**BLOCKED.** The normal fixture-complete bytes verify and the resolved CPython 3.14.5
offline replay succeeds, but two lifecycle/custody controls can be bypassed. The
`/usr/bin/python3` 3.9 replay fails on `zip(..., strict=True)`; this is **not** a finding
because the canonical environment decision pins CPython 3.14.5 and the declared replay
contract uses that resolved interpreter rather than broad Python-version compatibility.

### BLOCKER BL-01: Accepted lifecycle has no authorization gate

**Files:** `experiments/specchoice-v1.3.2/src/specchoice_evidence/bundle.py:665`,
`experiments/specchoice-v1.3.2/src/specchoice_evidence/cli.py:582`

**Issue:** `accept_fixture_closure_candidate()` accepts only a candidate directory and an
output directory. It does not take, load, or validate a local-acceptance decision; it does
not bind an authorization to the candidate's generation/root/snapshot hash, the v7 basis,
or the registry hash; and it does not run the boundary gate. The CLI exposes this directly
as `accept-fixture-closure-local`. Consequently any local caller able to read the candidate
can create an `accepted` / `downstream_eligible:true` generation without the separate
authorization promised by the lifecycle and without the `local-acceptance-v8.json` artifact
being used at all.

**Fix:** Require a canonical, revision-pinned local acceptance decision as a mandatory CLI
argument. Validate it before staging with the same identity fields used by the receipt
(generation, core/root/snapshot digest, registry digest, v7 baseline and reviewed basis),
require `external_publication_authorized:false`, and call the current boundary gate before
the exclusive create/rename. Add a negative test showing that no accepted directory is
created when the decision is missing, stale, mismatched, or grants publication.

### BLOCKER BL-02: Offline accepted verification does not prove the frozen 11/28 registry closure

**Files:** `experiments/specchoice-v1.3.2/src/specchoice_evidence/verify.py:151-219`,
`experiments/specchoice-v1.3.2/src/specchoice_evidence/bundle.py:687-702`,
`experiments/specchoice-v1.3.2/src/specchoice_evidence/cli.py:593-612`

**Issue:** The embedded verifier treats `fixture-registry-pr2164-v1.json` only as an opaque
hashed artifact. It neither validates its finite 11-fixture/28-file schema nor cross-checks
each registry tuple (path, role, length, SHA-256) against `content_manifest_core.snapshots`
and the raw files. The acceptance function checks only the two numeric counts. A temporary
accepted copy with the core reduced to one consumed raw file, all other raw files removed,
and all manifests/root/self-digests recomputed was accepted by `verify_accepted_bundle()`.
The Phase 2 authority validator likewise compares only the registry file digest and summary
counts, so it does not close this gap itself. This violates the standalone requirement that
the accepted bundle prove the exact named PR #2164 fixture set without Git objects.

**Fix:** Embed a stdlib-only registry validator in every v3 bundle and make both candidate
and accepted verification require: canonical registry bytes; the exact frozen fixture IDs,
classes, filenames and roles; exactly 11 fixtures/28 raw entries; one registry artifact;
and bidirectional equality between registry entries, core consumed-file records, and actual
raw bytes. Require the `fixture_closure.registry_path`/digest to match that artifact. Make
the acceptance transition invoke this stricter verifier before publication and add a
recanonicalized-subset regression test (not merely a byte-tamper test).

### Validation performed

- Focused stdlib suite: 44 tests passed under CPython 3.14.5.
- `verify-accepted` and `validate-phase2-source-authority` passed for the checked-in v3
  accepted generation.
- Copied bundle replay with `env -i PATH=/nonexistent /opt/homebrew/bin/python3` passed.
- Copied bundle replay with `/usr/bin/python3` 3.9 failed on `zip(..., strict=True)` as
  expected outside the pinned interpreter contract.
- Adversarial re-canonicalized one-file accepted bundle was incorrectly accepted by
  `verify_accepted_bundle()`, establishing BL-02.

---

## Gap-Closure Re-review (a072bd08, 969cb4e6, 00b2cff7)

**Reviewed:** 2026-07-31T09:32:00Z
**Depth:** deep
**Verdict at that revision:** **BLOCKED — one lifecycle blocker remained.**

### Resolved: BL-02 registry-to-raw closure

The v2 embedded verifier now parses the canonical registry, validates the fixed named
11-fixture/28-file universe, requires its artifact digest/path to match
`fixture_closure`, and requires bidirectional tuple equality with the core consumed-file
inventory. The same strict verifier is called by local candidate verification. A copied v2
candidate/accepted bundle reduced to one raw file with all core/final/root/self hashes
recomputed now fails with `FIXTURE_CLOSURE_CORE_REGISTRY_MISMATCH`.

### BLOCKER BL-01 (remaining): The acceptance API and CLI do not enforce the current boundary

**Files:** `experiments/specchoice-v1.3.2/src/specchoice_evidence/bundle.py:674-699`,
`experiments/specchoice-v1.3.2/src/specchoice_evidence/cli.py:605-619`

**Issue:** The new decision is correctly canonical and binds generation, registry, and v7
hashes. However the accepting library function accepts a caller-provided `v7_basis` and
only compares it to the decision; it never validates the baseline/restart lineage or a
current boundary itself. The CLI is its only boundary wrapper, but calls
`check_boundary(..., reviewed_revision=args.reviewed_revision)`, not the current-HEAD gate.
Committed changes after that supplied historical revision are excluded from the committed
projection (only live staged/worktree/untracked changes are observed). Therefore a caller
can invoke the public function directly, or reuse a stale decision/revision after a clean
but out-of-boundary commit, and still create an accepted generation in a new target. This
does not meet the required *current zero-blocker boundary* prerequisite for acceptance.

**Fix:** Move v7 lineage validation and a `check_current_boundary(repository, active_v7_baseline)`
gate into the acceptance implementation (or make the lower-level function private and pass
only a validated gate capability created by the CLI). Require the decision's reviewed
revision to be an exact, allowed current issuance state as well. Add a disposable-Git test
that commits an out-of-allowlist file after the decision revision, leaves the worktree
clean, and proves both the CLI and callable acceptance path fail before creating a target.

### Re-review validation

- Full stdlib suite: **85 tests passed** under the pinned CPython 3.14.5.
- v2 candidate and accepted verifiers passed; active `phase2/source-authority.json` validates
  against v2 with `external_publication_authorized:false`.
- Recanonicalized one-file v2 candidate/accepted replay failed closed as required.
- `git diff --exit-code da9d8fb2..HEAD` confirmed legacy v1 candidate/accepted trees and
  v8 receipts unchanged; the old v2 (PR #2192) accepted manifest remains
  `be220c0a858ac6d018dd48015a39e5ea1b68f75af21ad91ca13335eab3e6bebd`.

---

## Final Re-review (1c374cab, ea5ec95e)

**Reviewed:** 2026-07-31T09:48:00Z
**Depth:** deep
**Verdict:** **CLEAN.**

### Resolved: BL-01 current-boundary acceptance bypass

`accept_fixture_closure_candidate()` now accepts only a canonical decision path, resolves
the v7 baseline/allowlist/restart files from the implementation, validates that lineage,
and calls `check_current_boundary()` itself. The CLI exposes no caller-controlled basis or
reviewed-revision argument. A fake canonical decision basis fails with
`FIXTURE_CLOSURE_ACCEPTANCE_BASIS_MISMATCH`; a disposable clone with a later committed
out-of-boundary file fails with `FIXTURE_CLOSURE_ACCEPTANCE_BOUNDARY_BLOCKING`; and separate
staged, worktree, and untracked violations all fail with that same code before an accepted
target is created.

### Final validation

- Full stdlib suite: **88 tests passed** under the pinned CPython 3.14.5.
- Recanonicalized v2 subset attack remains rejected by both local and embedded verifiers.
- Copied v2 accepted bundle replay passed with an empty environment and no Git executable.
- `verify-accepted` and active Phase 2 source-authority validation pass for the v2 accepted
generation, with external publication authorization false.
- `git diff --exit-code da9d8fb2..HEAD` confirmed legacy v1 candidate/accepted bytes and v8
receipts unchanged; the historical v2 accepted manifest hash remains unchanged.

---

## Final Re-review (07210440)

**Reviewed:** 2026-07-31T12:23:15Z
**Depth:** deep
**Verdict:** **CLEAN.**

### Atomic no-replace generation publication

All four generation-producing lifecycle paths now publish their completed staging
directory only through `_publish_directory_no_replace()`: generic and verifier-rooted
candidate construction, ordinary local acceptance, and fixture-closure local acceptance.
The only remaining `os.replace()` updates a manifest entirely within a private staging
tree, before that tree is published; it cannot replace a generation target. There is no
check-then-replace fallback.

The native operations are single-call no-replace operations: Darwin uses
`renameatx_np(..., RENAME_EXCL)`, Linux uses `renameat2(..., RENAME_NOREPLACE)`, and
Windows uses `MoveFileExW` without `MOVEFILE_REPLACE_EXISTING`. Existing-target errno and
Win32 mappings become the lifecycle-specific collision codes; unavailable primitives and
all other failures become stable fail-closed diagnostics. Cleanup acts only on the still
unpublished staging path after a failed native rename, never on the target path.

### Final validation

- The focused fixture-closure suite passed **15 tests**, including deterministic candidate
  and accepted publication races against empty targets, a nonempty target-preservation
  race, and unavailable-primitive rejection.
- The complete stdlib suite passed **92 tests** under the pinned CPython 3.14.5, exercising
  ordinary candidate construction and acceptance as well as the new race controls.
- The checked-in v2 accepted fixture bundle replayed with an empty environment and no Git
  executable: `env -i PATH=/nonexistent /opt/homebrew/bin/python3 verify_bundle.py`.
- `git diff --exit-code 07210440^ 07210440 -- bundles receipts` found no bundle or receipt
  changes. The historical PR #2192 accepted manifest remains
  `be220c0a858ac6d018dd48015a39e5ea1b68f75af21ad91ca13335eab3e6bebd`; the current v2
  accepted fixture manifest remains
  `ecb37d0a75a0d7f68e1ec166168440d6c799bc04d1fc475e013dfadadf09d972`.

---

_Reviewed: 2026-07-31T12:23:15Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
