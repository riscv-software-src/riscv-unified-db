# Roadmap: SpecChoice v1.3.2

## Overview

SpecChoice v1.3.2 proceeds through seven strict, dependency-ordered increments: isolate and pin the public evidence, prove the measurement contract, preregister human-owned data, build and freeze the controlled treatments, execute only the authorized branch, evaluate partitions and ablations without pooling, and publish a reproducible bounded conclusion. Green and Yellow authorize controlled A/B/C model execution; Red is a valid fail-closed feasibility path that prohibits real model calls and succeeds only through independently auditable measurement, construction, blocker, and reproducibility evidence. Optional discovery and upstream contribution remain v2 and are not roadmap phases.

## Path Contract

- `[ALL]` requirements apply to Green, Yellow, and Red.
- `[G/Y]` requirements apply only after H3 selects Green or Yellow and H4 authorizes the exact external model configuration.
- A Red selection does not fail the roadmap: Phases 5–7 run in no-model mode and produce the Red feasibility package.
- `[G/Y]` requirements become `Not Applicable — Red` only after Phase 7 verifies every Red success condition; Red never counts as extraction-experiment success.
- Production held-out retrieval and real model calls are prohibited until the human-reviewed registries, prompts, configuration, branch, `N_strict`, repeats, and freeze root are approved.

## Phases

- [x] **Phase 1: Isolated Evidence Boundary and Source Integrity** - Establish a dependency-light experiment boundary and independently verifiable public inputs. (completed 2026-07-31)
- [x] **Phase 2: Deterministic Measurement Spine** - Prove the frozen adjudication and diagnostic contract on all 11 fixtures before innovation. (completed 2026-08-03)
- [x] **Phase 3: Human-Reviewed Data Preregistration** - Produce leakage-safe, provenance-rich data whose semantic decisions are explicitly human-approved. (completed 2026-08-04)
- [ ] **Phase 4: Offline Treatments, Retrieval, and Branch Freeze** - Make the controlled treatments inspectable offline, freeze them, and select exactly one fail-closed branch.
- [ ] **Phase 5: Authorized Execution and Immutable Evidence** - Execute the approved Green/Yellow call matrix or preserve a verifiable Red no-call record.
- [ ] **Phase 6: Partition-Aware Ablation and Metamorphic Evaluation** - Score the authorized branch without pooling partitions or collapsing distinct failure modes.
- [ ] **Phase 7: Reproducible Feasibility Conclusion** - Deliver a byte-stable, claim-bounded positive, negative, or Red conclusion for human acceptance.

## Phase Details

### Phase 1: Isolated Evidence Boundary and Source Integrity

**Goal:** The operator and reviewer can work from a self-contained experiment boundary whose public source identity is independently verifiable.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** TS-01, TS-02
**Vertical increment:** A usable local evidence workspace and verified source-manifest report, without any core UDB schema or generated-data modification.
**Human checkpoint:** Reviewer accepts the experiment boundary, source identities, and any documented 90-minute standalone fallback before measurement implementation proceeds.
**Success Criteria** (what must be TRUE):

  1. The operator can create, test, and inspect all prototype artifacts under `experiments/specchoice-v1.3.2/` without changing core UDB schemas, generated architecture data, or root dependency state.
  2. The reviewer can verify every named PR snapshot against its frozen commit and reproduce the stable hash of every consumed source file.
  3. The operator can reproduce the recorded environment decision and, if full setup exceeded the frozen limit, use the documented dependency-light fallback without weakening source verification.

**Plans:** 7/7 plans complete

Plans:

- [x] 01-01-PLAN.md
- [x] 01-02-PLAN.md
- [x] 01-03-PLAN.md
- [x] 01-04-PLAN.md
- [x] 01-05-PLAN.md
- [x] 01-06-PLAN.md
- [x] 01-07-PLAN.md

**Wave 1**

- [x] 01-01: Capture the immutable phase-start baseline and enforce the exact filesystem boundary.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02: Record standalone-first environment identity and the cumulative dependency-incident policy.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03: Prove pinned PR identities, preserve the #2192 rejection, and stage immutable raw/derived bundle content.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04: Verify the bundle offline and gate boundary/source integrity through canonical receipts and reviewer approval.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-05: Preserve the v2 incident, create the D-15 gap-restart lineage, and make committed post-baseline changes fail closed.

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-06: Freeze the exact 11-fixture/28-raw-file registry and construct a verifier-rooted but ineligible candidate.

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 01-07: Complete the separately authorized local-only acceptance transition and bind the exact Phase 2 source authority.

### Phase 2: Deterministic Measurement Spine

**Goal:** As a human RISC-V reviewer, I want to trust the experiment's adjudication semantics and diagnostics, so that I can review the measurement spine before any frame, retrieval, or model result is considered.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** TS-03, TS-04, TS-05
**Vertical increment:** A runnable evaluator that produces correct, inspectable outcomes for all frozen fixtures, even if later innovation is never authorized.
**Human checkpoint:** H1 — Source/gold review approves the adapter's fixture interpretation and candidate semantics; failure blocks innovation but preserves the measurement increment.
**Success Criteria** (what must be TRUE):

  1. The operator can score golden predictions for all 11 pinned PR #2164 fixtures, including surfacing and then classifying out the candidate case.
  2. The operator sees strict rejection of unknown keys, invalid enums, duplicate/conflicting predictions, and every noncanonical no-finding state, with no silent repair.
  3. The reviewer can trace every failed or warning outcome to a stable diagnostic code and structured fields; a missing accepted name remains an identity warning and never rewrites disposition.
  4. The human reviewer can approve or dispute the frozen gold interpretation from the adapter audit without any model output being used to compensate for disputed semantics.

**Plans:** 22/22 plans resolved (19 executed, 3 superseded; 02-20 and 02-21 intentionally omit summaries by plan contract)

Plans:

- [x] 02-01-PLAN.md
- [x] 02-02-PLAN.md
- [x] 02-03-PLAN.md
- [x] 02-04-PLAN.md
- [x] 02-05-PLAN.md
- [x] 02-06-PLAN.md
- [x] 02-07-PLAN.md
- [x] 02-08-PLAN.md
- [x] 02-09-PLAN.md
- [x] 02-10-PLAN.md
- [x] 02-11-PLAN.md
- [x] 02-12-PLAN.md
- [x] 02-13-PLAN.md
- [x] 02-14-PLAN.md
- [x] 02-15-PLAN.md
- [x] 02-16-PLAN.md
- [x] 02-17-PLAN.md — superseded by the successor chain
- [x] 02-18-PLAN.md — partially executed, then superseded by 02-19 and the downstream-only successor
- [x] 02-19-PLAN.md — superseded downstream by 02-20 through 02-22
- [x] 02-20-PLAN.md
- [x] 02-21-PLAN.md
- [x] 02-22-PLAN.md

**Wave 1**

- [x] 02-01: Implement the versioned PR #2164 adapter and canonical adjudication domain model.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02: Implement strict schema parsing, no-finding invariants, and stable diagnostics.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03: Implement golden fixture scoring, candidate behavior, identity-warning separation, and evidence checks.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-04: Persist immutable formal and adversarial attempts with deterministic measurement artifacts.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-05: Produce the hash-bound H1 source/gold review packet and validate the human decision gate.

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 02-06: Record the narrow custody-hardening governance override and restore the Phase 2 MVP goal contract.

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 02-07: Bind adversarial lineage to a validated formal attempt and retain adapter conflict provenance.

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 02-08: Route adapter, preflight, and H1 leaves through descriptor-bound reads and preserve the exact phase-aware regression partition.

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 02-09: Build descriptor-rooted source-custody primitives with stable reads, exact tree snapshots, and parent-held publication.

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 02-10: Create a byte-bound v3 construction proposal, require human construction authorization, and publish only an ineligible candidate.

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 02-11: Require separate human local acceptance, materialize accepted v3 from held bytes, and create a non-effective pending transition.

**Wave 12** *(blocked on Wave 11 completion)*

- [x] 02-12: Generate accepted-v3 receipts and prove copied offline replay without repository or network authority.

**Wave 13** *(blocked on Wave 12 completion)*

- [x] 02-13: Rehearse adapter and preflight against pending v3 while the active authority remains unchanged.

**Wave 14** *(blocked on Wave 13 completion)*

- [x] 02-14: Rehearse the formal and adversarial held-read graph against pending v3 with independently validated lineage.

**Wave 15** *(blocked on Wave 14 completion)*

- [x] 02-15: Freeze the versioned H1 schema, explicit-schema packet bindings, readiness oracle, and seven-response decision contract.

**Wave 16** *(blocked on Wave 15 completion)*

- [x] 02-16: Perform the forward-only authority cutover, then generate all post-active measurement and H1 evidence.

**Wave 17** *(historical route superseded by Waves 18 and 19; resolved without terminal authority)*

- [x] 02-17: Validate fresh readiness, collect the human H1 disposition, and require four same-commit clean final reports. *(superseded)*

**Wave 18** *(Tasks 1-4 preserved; unfinished Tasks 5-13 superseded by Wave 19)*

- [x] 02-18: Execute the single versioned Phase 1/2 semantic-integrity successor across seven fresh-context segments, preserving v3 history and retaining four genuine human gates. *(partially executed, then superseded)*

**Wave 19** *(depends on completed 02-18 Tasks 1-4 and supersedes only unfinished Tasks 5-13)*

- [x] 02-19: Freeze the complete executable, tool, semantic-input, and authority-prestate closure before renewed construction authorization, then finish dual-gated v5 acceptance, deterministic measurement, seven-question H1 review, and four fresh reports. *(superseded downstream)*

**Waves 20-22** *(single downstream-only successor; supersedes further execution of 02-17 through 02-19 without rewriting their history)*

- [x] 02-20: Implement the authority-bound closure-v4, adapter, measurement, H1, and report code contracts, then freeze only committed code/tests/contracts. *(summary intentionally omitted by plan contract)*
- [x] 02-21: Bootstrap closure-v4 from that code-only commit and materialize fresh decision-free adapter, formal, adversarial, packet, and readiness evidence. *(summary intentionally omitted by plan contract)*
- [x] 02-22: Obtain the genuine three-state H1 decision and create four fresh reports plus the terminal summary only for an approved result.

### Phase 3: Human-Reviewed Data Preregistration

**Goal:** The reviewer can approve a defensible prototype and evaluation corpus before retrieval ranks or model outputs can influence semantic decisions.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** TS-08, TS-09, H2-01
**Vertical increment:** An audited data package that independently determines whether Green, Yellow, or Red remains feasible.
**Human checkpoint:** H2 — Data review approves labels, membership, primary families, pair axes, relevance judgments, and metamorphic directions; machines report inconsistencies but never rewrite them.
**Success Criteria** (what must be TRUE):

  1. The reviewer can inspect and approve complete contrastive pairs with positive and contrast passages, shared structure, frames, final statuses, discriminating axes, evidence, provenance, and manual-verification records.
  2. Automated validation proves item provenance, registered and version-compatible primary families, zero prototype/held-out example overlap, zero prototype/strict-core primary-family overlap, and no held-out passage in demonstrations.
  3. The human reviewer can explicitly approve or dispute every label, membership decision, family, pair axis, relevance judgment, and metamorphic expectation without automated relabeling or quota-filling pairs.
  4. The reviewer receives audited counts showing either a possible Green/Yellow data threshold or the exact defensible evidence requiring Red.

**Plans:** 4/4 plans complete

Plans:

- [x] 03-01-PLAN.md
- [x] 03-02-PLAN.md
- [x] 03-03-PLAN.md
- [x] 03-04-PLAN.md

**Wave 1**

- [x] 03-01: Curate provenance-rich prototype pairs and held-out gold without fabricated quota filling.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02: Define the versioned family registry and strict/auxiliary split manifest.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03: Preregister pair relevance and the four human-reviewed metamorphic directions.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-04: Run leakage/provenance validation and assemble the H2 approval and branch-eligibility packet.

### Phase 4: Offline Treatments, Retrieval, and Branch Freeze

**Goal:** The reviewer can inspect the exact treatments offline and authorize one immutable Green, Yellow, or Red execution contract.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** TS-10, H1-01, H2-02
**Vertical increment:** A replayable offline A/B/C prompt-and-retrieval bundle plus a verified freeze root that either enables one controlled path or fails closed.
**Human checkpoint:** H3 approves the manifest, branch, `N_strict`, and repeats. On Green/Yellow only, H4 separately approves the provider, immutable model snapshot, sampling/output settings, cost, credentials boundary, and external calls.
**Success Criteria** (what must be TRUE):

  1. The reviewer can inspect B and C outputs containing exactly `authority`, `choice_object`, and `choice_space_origin`, frozen enums with `unknown`, and a verbatim evidence span for every axis.
  2. The operator can retrieve exactly two complete pairs per controlled target using frozen TF-IDF/cosine settings, target-dependent rankings, and deterministic `pair_id` tie-breaking, with no embedding or learned retrieval component.
  3. The reviewer can compare rendered A/B/C prompt bytes and verify equal demonstration counts, shared target/rules/decision space/evidence requirements, intended treatment-only differences, and measured natural token differences without padding.
  4. The gate records exactly one approved branch plus `N_strict` and repeats; Red makes production retrieval and the real-model adapter unreachable, while Green/Yellow cannot call a model before the separate H4 approval verifies.

**Plans:** 4/4 plans executed

Plans:

- [x] 04-01-PLAN.md
- [x] 04-02-PLAN.md
- [x] 04-03-PLAN.md
- [x] 04-04-PLAN.md

**Wave 1**

- [x] 04-01: Freeze the three-axis frame schema, advisory patterns, and strict B/C output contract.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02: Assemble treatment-controlled A/B/C prompts, serializers, structural diffs, and budget accounting.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-03: Implement deterministic complete-pair retrieval and validate it offline with target-only inputs.

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 04-04: Hash every treatment-affecting artifact and implement H3/H4 branch authorization with Red fail-closed enforcement.

### Phase 5: Authorized Execution and Immutable Evidence

**Goal:** The authorized branch yields complete immutable evidence without unauthorized calls, hidden repair, asymmetric retries, or favorable-subset execution.
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** TS-07, TS-11, TS-12
**Vertical increment:** Green/Yellow yields a replayable complete call corpus; Red yields a machine-verifiable empty call ledger and preserved measurement/construction evidence.
**Human checkpoint:** Execution must match the H3 freeze root and, for Green/Yellow, the H4 model authorization exactly; any frozen-input drift stops the run, records a decision, increments the version, and requires symmetric reruns.
**Success Criteria** (what must be TRUE):

  1. The reviewer can inspect immutable raw outputs captured before parsing, parsed outputs, parser diagnostics, and verbatim evidence-span audits as separate artifacts.
  2. On Green/Yellow, the operator can execute every preregistered strict-core case under A, B, and C with the same frozen controls, exactly two pairs, and the approved repeat count, with no missing cell.
  3. On Green/Yellow, the reviewer can inspect each call's prompt hash, model snapshot, sampling and output settings, actual token use, raw response, parse result, refusal/truncation state, and retry/failure state.
  4. On Red, the reviewer can verify an empty real-model call ledger and preserved runner, construction, ambiguity, and trigger evidence; the G/Y requirements remain conditional until Phase 7 validates Red closure.

**Plans:** 3 plans

Plans:

- [ ] 05-01: Implement freeze-root verification, immutable envelopes, raw-first persistence, and the stable execution plan.
- [ ] 05-02: Execute the authorized strict A/B/C matrix or the Red no-call branch without crossing the gate.
- [ ] 05-03: Audit cell completeness, call metadata, evidence lineage, replayability, and drift-triggered stop behavior.

### Phase 6: Partition-Aware Ablation and Metamorphic Evaluation

**Goal:** The reviewer can evaluate the frozen branch at case level while preserving every metric, treatment, partition, and denominator boundary.
**Mode:** mvp
**Depends on:** Phase 5
**Requirements:** TS-06, TS-13, H1-02, H1-03, H1-04, H2-03, H2-04
**Vertical increment:** A complete evaluation package that supports a positive, negative, or Red conclusion without yet asking the reviewer to accept the narrative.
**Human checkpoint:** Reviewer inspects case-level joins, denominators, advisory-only warnings, metamorphic directions, and failure classifications before interpretation; disputes do not relabel same-version gold.
**Success Criteria** (what must be TRUE):

  1. The reviewer receives independently calculated surfacing, disposition, exact/incorrect/missing identity, classify-out, and evidence-integrity outcomes; Green/Yellow adds separate frame-axis and retrieval results.
  2. On Green/Yellow, the reviewer can compare paired B-minus-A and C-minus-B case outcomes under their frozen controls and see shortcut-family failures without post-hoc prompt, label, family, relevance, or threshold changes.
  3. On Green/Yellow, the operator can run all four frozen metamorphic minimal pairs and the reviewer can inspect axis changes, decision changes, evidence integrity, and the expected directional relation.
  4. PairHit@K is reported only for preregistered relevance judgments, with retrieved pair IDs per case; strict, auxiliary, metamorphic, and repeat-disagreement outputs retain separate IDs and denominators.
  5. On Red, the reviewer receives only the deterministic measurement and construction-feasibility evaluation, with no absent model outputs presented as experimental zeros or extraction evidence.

**Plans:** 4 plans

Plans:

- [ ] 06-01: Join immutable predictions to frozen gold and compute partition-specific outcome metrics.
- [ ] 06-02: Produce paired B-A/C-B analyses, frame diagnostics, and the frozen failure taxonomy.
- [ ] 06-03: Evaluate metamorphic directions, preregistered PairHit@K, retrieved IDs, and repeat stability.
- [ ] 06-04: Assemble branch-aware Green/Yellow or Red evaluation artifacts with denominator and partition audits.

### Phase 7: Reproducible Feasibility Conclusion

**Goal:** The human reviewer can reproduce and accept a bounded positive, negative, or Red feasibility conclusion from immutable evidence.
**Mode:** mvp
**Depends on:** Phase 6
**Requirements:** TS-14, TS-15
**Vertical increment:** The complete v1.3.2 handoff: canonical reports, exact rerun commands, limitations, decision record, and an approved interpretation.
**Human checkpoint:** H5 accepts or disputes the failure taxonomy, limitations, and claim bounds. H6 remains a separate downstream prerequisite for any optional public communication and is not a v1 phase.
**Success Criteria** (what must be TRUE):

  1. The reviewer can trace branch and split counts, case-level results, failure taxonomy, and limitations to immutable evidence and read a bounded positive, negative, or Red conclusion with none of the prohibited claims.
  2. Equivalent captured inputs produce byte-identical canonical JSON with UTF-8/LF, NFC normalization, stable array ordering, sorted keys, no absolute paths or timestamps, content hashes, and exact reproduction commands.
  3. The H5 record captures interpretation approval or disputes without same-version relabeling, and no public action occurs without a later H6 approval.
  4. On Red, the reviewer can reproduce the passing runner, scoring-gap assessment, attempted construction audit, explicit blocker, no-call proof, ambiguity report, and revised feasibility conclusion before G/Y requirements close as `Not Applicable — Red`.

**Plans:** 3 plans

Plans:

- [ ] 07-01: Generate canonical JSON/Markdown results, hashes, reproducibility instructions, and decision-log linkage.
- [ ] 07-02: Draft the branch-bounded feasibility narrative, limitations, and H5 interpretation packet.
- [ ] 07-03: Verify final path closure, requirement status, prohibited-claim checks, and the no-public-action boundary.

## Coverage

| Requirement | Phase |
|-------------|-------|
| TS-01 | Phase 1 |
| TS-02 | Phase 1 |
| TS-03 | Phase 2 |
| TS-04 | Phase 2 |
| TS-05 | Phase 2 |
| TS-06 | Phase 6 |
| TS-07 | Phase 5 |
| TS-08 | Phase 3 |
| TS-09 | Phase 3 |
| TS-10 | Phase 4 |
| TS-11 | Phase 5 |
| TS-12 | Phase 5 |
| TS-13 | Phase 6 |
| TS-14 | Phase 7 |
| TS-15 | Phase 7 |
| H1-01 | Phase 4 |
| H1-02 | Phase 6 |
| H1-03 | Phase 6 |
| H1-04 | Phase 6 |
| H2-01 | Phase 3 |
| H2-02 | Phase 4 |
| H2-03 | Phase 6 |
| H2-04 | Phase 6 |

**Coverage:** 23/23 v1 requirements mapped exactly once; no v2 discovery, packaging, communication, or upstream requirement is scheduled.

## Progress

**Execution Order:** Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Isolated Evidence Boundary and Source Integrity | 7/7 | Complete    | 2026-07-31 |
| 2. Deterministic Measurement Spine | 22/22 | Complete | 2026-08-03 |
| 3. Human-Reviewed Data Preregistration | 4/4 | Complete   | 2026-08-04 |
| 4. Offline Treatments, Retrieval, and Branch Freeze | 4/4 | In Progress|  |
| 5. Authorized Execution and Immutable Evidence | 0/3 | Not started | - |
| 6. Partition-Aware Ablation and Metamorphic Evaluation | 0/4 | Not started | - |
| 7. Reproducible Feasibility Conclusion | 0/3 | Not started | - |
