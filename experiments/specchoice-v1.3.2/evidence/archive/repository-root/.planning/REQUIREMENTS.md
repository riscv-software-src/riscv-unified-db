# Requirements: SpecChoice v1.3.2

**Defined:** 2026-07-30  
**Core Value:** Produce a reproducible, leakage-safe, falsifiable A/B/C result—positive, negative, or Red-path infeasible—without weakening gold semantics, deterministic measurement, or human control of RISC-V judgments.

## Path Contract

- **ALL** requirements apply to every defensible Green, Yellow, or Red outcome.
- **G/Y** requirements apply only when the human-approved gate authorizes a Green or Yellow controlled model experiment.
- If the gate selects Red, G/Y requirements are closed as `Not Applicable — Red` only after the independent Red feasibility-assessment requirements pass. Red never counts as extraction-experiment success.
- Optional discovery and upstream work are v2 scope and cannot be used to satisfy v1.

## User Stories

- As a human RISC-V reviewer, I can inspect and approve source semantics, labels, split membership, primary families, contrastive axes, retrieval relevance, metamorphic directions, and the Green/Yellow/Red branch before any real model call.
- As an experiment operator, I can reproduce the measurement runner, freeze an exact run contract, execute only an authorized branch, and preserve every raw response and diagnostic without silent repair.
- As an ML evaluation reviewer, I can trace each aggregate result to case-level A/B/C outcomes, exact prompt and prediction hashes, separate denominators, and auditable evidence spans.
- As a UnifiedDB maintainer, I can evaluate a small isolated prototype and bounded feasibility conclusion without accepting a repository-wide schema, emitter, service, or unsupported novelty claim.
- As a researcher, I receive a useful result when either hypothesis is supported, unsupported, or cannot be tested safely because the project correctly selects Red.

## v1 Requirements

Requirements for the frozen SpecChoice v1.3.2 execution baseline. Each maps to exactly one roadmap phase.

### Experimental Foundation and Controls

- [x] **TS-01** `[ALL]`: The operator can work entirely within a dependency-light `experiments/specchoice-v1.3.2/` boundary containing the prototype's code, configuration, data, prompts, tests, runs, reports, and notes, without modifying core UDB schemas or generated data.
- [x] **TS-02** `[ALL]`: The operator can verify a source manifest that pins every named public PR snapshot to its frozen commit and records stable hashes for every consumed source file.
- [x] **TS-03** `[ALL]`: The operator can run a versioned PR #2164 adapter and deterministic measurement runner that scores golden predictions for all 11 pinned fixtures, including surfacing and then classifying out the candidate fixture.
- [x] **TS-04** `[ALL]`: The operator receives strict validation of the canonical adjudication schema, including the unique nullable `surfaced=false` representation, rejection of `parameter_status:not_surfaced`, unknown-key rejection, enum enforcement, and no silent repair.
- [x] **TS-05** `[ALL]`: Tests and reports expose every required stable diagnostic code with structured fields, while `ACCEPTED_PARAMETER_NAME_MISSING` remains an identity warning that cannot change disposition correctness.
- [ ] **TS-06** `[ALL]`: The reviewer receives independently calculated surfacing, disposition, exact/incorrect/missing identity, classify-out, and evidence-integrity outcomes; Green/Yellow additionally reports each frame axis and retrieval quality separately.
- [ ] **TS-07** `[ALL]`: The reviewer can audit at least one non-empty verbatim evidence span for every surfaced finding and can inspect immutable raw outputs, parsed outputs, and parser diagnostics as separate artifacts.
- [x] **TS-08** `[ALL]`: Automated validation proves provenance for every data item, zero prototype/held-out example overlap, zero prototype/strict-core primary-family overlap, registered primary families, compatible registry versions, and no held-out passage in prompt demonstrations.
- [x] **TS-09** `[ALL]`: The human reviewer controls labels, dataset membership, primary families, contrastive pairs and axes, relevance judgments, metamorphic expectations, fallback state, and public communication; any frozen-input change stops the run, enters the decision log, increments the experiment version, and triggers symmetric reruns.
- [ ] **TS-10** `[ALL]`: A machine-evaluated and human-approved gate records exactly one Green, Yellow, or Red state plus `N_strict` and repeat count, blocks model execution on every Red trigger, and prevents model output from compensating for unreliable gold.
- [ ] **TS-11** `[G/Y]`: The operator can execute every preregistered strict-core case under A, B, and C with the same model snapshot, sampling, target context, shared guidance, decision space, evidence rules, exactly two demonstration pairs, and repeat count; only the intended treatment differs.
- [ ] **TS-12** `[G/Y]`: The reviewer can inspect every call's prompt hash, actual input/output tokens, output limit, model snapshot, sampling settings, raw response, parse result, refusal/truncation state, and retry/failure state, with no missing strict-core A/B/C cell.
- [ ] **TS-13** `[G/Y]`: The operator can run four frozen, human-reviewed metamorphic minimal pairs covering choice-space origin, true WARL versus fixed legal set, hardware versus software authority, and normative versus NOTE/example language, and report the expected directional relation.
- [ ] **TS-14** `[ALL]`: The reviewer receives case-level results, branch and split counts, failure taxonomy, limitations, and a bounded positive, negative, or Red feasibility conclusion that makes none of the prohibited statistical, full-corpus, private-pipeline, confirmed-parameter, or merge-readiness claims.
- [ ] **TS-15** `[ALL]`: Equivalent captured inputs produce byte-identical canonical JSON using UTF-8/LF, NFC normalization, stable array ordering, sorted keys, no absolute paths or timestamps in core reports, content hashes, and exact reproducibility commands.

### H1 — DelegationFrame Effect

- [x] **H1-01** `[G/Y]`: For systems B and C, the reviewer receives exactly the three required DelegationFrame axes—`authority`, `choice_object`, and `choice_space_origin`—using frozen enums, permitting `unknown`, and carrying a verbatim evidence span for each axis.
- [ ] **H1-02** `[G/Y]`: The reviewer can compare paired B-minus-A case outcomes where A and B use the same two fixed complete contrastive pairs and all shared controls, with the DelegationFrame as the intended intervention.
- [ ] **H1-03** `[G/Y]`: The reviewer receives separate accuracy for all three frame axes and frozen `FRAME_COMBINATION_REQUIRES_REVIEW` warnings that remain non-blocking and cannot alter axis or disposition correctness.
- [ ] **H1-04** `[G/Y]`: The reviewer can determine whether the frame changes shortcut-family errors and required metamorphic directions without post-hoc prompt, label, family, or threshold changes.

### H2 — Axis-Contrastive Retrieval Effect

- [x] **H2-01** `[G/Y]`: The human reviewer can approve a bank of complete contrastive pairs in which each unit records positive and contrast passages, shared structure, frames, final statuses, discriminating axes, evidence spans, source provenance, and manual verification, without fabricated quota-filling pairs.
- [ ] **H2-02** `[G/Y]`: The operator can retrieve exactly two complete pairs per controlled target using frozen TF-IDF and cosine-similarity settings, deterministic `pair_id` tie-breaking, target-dependent rankings, and no embeddings, vector database, learned retriever, or learned reranker.
- [ ] **H2-03** `[G/Y]`: The reviewer can inspect a versioned and hashed relevance registry frozen before retrieval, per-case retrieved pair IDs, and `PairHit@K` calculated only for cases with preregistered human relevance judgments.
- [ ] **H2-04** `[G/Y]`: The reviewer can compare paired C-minus-B outcomes where B and C share the identical frame, adjudication, context, evidence, model, pair-count, and repeat controls, with complete-pair selection method as the only intended intervention.

## Acceptance Criteria

### Every Outcome Path

- All 11 pinned fixtures score successfully from golden predictions.
- Source, fixture, prompt, data, configuration, and report identities are pinned or content-hashed.
- Human-owned semantic decisions and approvals are explicit artifacts.
- No same-version frozen input is modified after execution begins.
- Every aggregate traces to case-level data and independently auditable evidence.
- The final conclusion is reproducible and stays within the frozen claim boundary.

### Green

- At least 6 verified contrastive pairs exist, the frozen strict core contains at least 10 adjudicated cases, families and relevance are frozen, and schemas are parseable.
- Full preregistered strict-core A/B/C execution and the four metamorphic evaluations complete.

### Yellow

- At least 4 verified contrastive pairs exist, the frozen strict core contains at least 6 adjudicated cases, and labels and family assignments are human-reviewed.
- Reduced preregistered strict-core A/B/C execution completes; auxiliary data remains separately reported and optional discovery is skipped by default.

### Red

- No real model experiment runs.
- The runner, public scoring-gap assessment, attempted data/split construction, explicit blocker or disputed semantic decision, ambiguity report, and revised feasibility conclusion are auditable and reproducible.

## Definition of Done

A v1 requirement is complete only when its implementation is committed, its automated verification passes where applicable, its required human review record exists, and its output can be reproduced from committed or content-addressed inputs. The milestone completes on exactly one approved branch:

- Green or Yellow completes all applicable `ALL` and `G/Y` requirements; or
- Red completes all `ALL` requirements and records every `G/Y` requirement as `Not Applicable — Red` with the approved Red trigger.

## v2 Requirements

Deferred capabilities may be considered only after every required Green/Yellow deliverable passes. They are not part of the current roadmap and are removed first under time pressure.

### Optional Discovery

- **DISC-01**: The reviewer can inspect one controlled qualitative discovery slice of approximately 30–80 paragraphs without treating it as benchmark gold or a recall estimate.
- **DISC-02**: The reviewer can inspect private top-10 dossiers containing rank, provenance, source passage, retrieved pair, frame, adjudication, possible existing parameter, and open question without claiming a confirmed new parameter.

### Packaging and Upstream Preparation

- **PACK-01**: The operator can package the completed prototype into a small external repository without changing the frozen experiment result or implying an accepted upstream location.
- **COMM-01**: The human reviewer can approve a private maintainer-comment draft describing the bounded result and asking whether the controlled data or ablation is useful.
- **UPST-01**: The human reviewer can authorize an Issue, comment, or PR-ready branch only after the deterministic runner, split checks, experiment, novelty check, maintainer invitation, and line-by-line explainability criteria pass.

## Out of Scope

Explicit exclusions prevent scope creep and preserve the controlled hypotheses.

| Feature | Reason |
|---------|--------|
| Generic RAG or vector-database infrastructure | Adds unrelated indexing and storage choices to a three-day pair-retrieval test. |
| Embeddings, embedding comparisons, learned retrieval, reranking, or query expansion | Introduces unregistered model and optimization confounds; the frozen retrieval treatment is TF-IDF plus cosine similarity. |
| Multi-agent extraction orchestration or knowledge graphs | Adds unmeasured reasoning and data-model interventions unrelated to `B-A` or `C-B`. |
| More required frame axes, mandatory `scope`, or a general ontology | Changes H1 and increases semantic annotation burden beyond the frozen three-axis frame. |
| Full-corpus extraction or a repository-wide benchmark | Available gold, family isolation, time, and review capacity cannot support full-corpus or significance claims. |
| UDB YAML emission, taxonomy redesign, complete `definedBy` inference, or fuzzy identity matching | Conflates adjudication with alignment and production emission. |
| Candidate discovery combined with demonstration retrieval | The two tasks have different objectives; hard-negative similarity must not suppress discovery. |
| Prompt optimization, adaptive pair tuning, post-hoc relabeling, or same-version threshold changes | Leaks held-out outcomes into the controlled experiment. |
| LLM-generated gold, pair labels, relevance judgments, or unreviewed metamorphic transformations | The evaluated model cannot define its own semantic target. |
| Silent output repair, tolerant schema coercion, hidden retries, or best-repeat selection | Conceals instruction-following and execution failures and can bias a small experiment. |
| Semantic-entailment claims based only on evidence-span presence | A verbatim span proves occurrence, not that the adjudication follows from it. |
| Neutral-text token padding or unequal demonstration counts | Padding and unequal examples are themselves treatment changes. |
| A single blended headline score or statistical-significance claim | Hides distinct failure modes and overstates evidence from a small strict core. |
| Production API, service, database, UI, authentication, or core UDB backend integration | Not required to answer the feasibility question and would consume the spike. |
| Automatic public Issues, comments, pull requests, or upstream writes | Public communication requires explicit human approval and satisfaction of frozen upstream criteria. |

## Traceability

Roadmap creation maps every v1 requirement to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TS-01 | Phase 1 | Complete |
| TS-02 | Phase 1 | Complete |
| TS-03 | Phase 2 | Complete |
| TS-04 | Phase 2 | Complete |
| TS-05 | Phase 2 | Complete |
| TS-06 | Phase 6 | Pending |
| TS-07 | Phase 5 | Pending |
| TS-08 | Phase 3 | Complete |
| TS-09 | Phase 3 | Complete |
| TS-10 | Phase 4 | Pending |
| TS-11 | Phase 5 | Pending |
| TS-12 | Phase 5 | Pending |
| TS-13 | Phase 6 | Pending |
| TS-14 | Phase 7 | Pending |
| TS-15 | Phase 7 | Pending |
| H1-01 | Phase 4 | Complete |
| H1-02 | Phase 6 | Pending |
| H1-03 | Phase 6 | Pending |
| H1-04 | Phase 6 | Pending |
| H2-01 | Phase 3 | Complete |
| H2-02 | Phase 4 | Pending |
| H2-03 | Phase 6 | Pending |
| H2-04 | Phase 6 | Pending |

**Coverage:**

- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-30*  
*Last updated: 2026-08-03 after approved Phase 2 terminal verification*
