---
name: extract-parameters-from-subsection
description: Extract implementation-defined architectural parameters from a named subsection of a RISC-V AsciiDoc spec file and write UnifiedDB parameter-candidate YAML to /tmp/<subsection-title>.yaml.
argument-hint: <subsection-title> <adoc-file>
allowed-tools: Read, Bash, Write
---

Copyright (c) 2026 Udit Jain
SPDX-License-Identifier: BSD-3-Clause-Clear

Extract every implementation-defined architectural parameter described in the specified subsection of the given AsciiDoc file, then write the candidates to `/tmp/<subsection-title>.yaml`, where `<subsection-title>` is argument 1 lowercased with spaces replaced by hyphens (e.g., `"Supervisor Address Translation and Protection"` → `/tmp/supervisor-address-translation-and-protection.yaml`).

This is the parameter analogue of the `extract-instructions-from-subsection` skill. Where that skill finds a fixed lexical class (uppercase instruction mnemonics), a parameter is a **semantic** concept: a value the RISC-V ISA leaves to the implementation. There is no single token to match — parameters are found by the phrases the spec uses to _hand a decision to the implementation_, so the rules below are keyword-and-context patterns, and every candidate must be justified by a verbatim excerpt.

## Arguments

$ARGUMENTS

- **Argument 1**: The subsection title to search for (e.g., `"Supervisor Address Translation and Protection"` or `"Memory and Caches"`).
- **Argument 2**: Path to the AsciiDoc file (e.g., `ext/riscv-isa-manual/src/priv/supervisor.adoc`).

If either argument is missing, ask the user to provide it.

## Steps

### 1. Read the AsciiDoc file

Read the full content of the AsciiDoc file given as argument 2.

### 2. Locate the subsection

Find the subsection whose title matches argument 1. AsciiDoc section headings use `=` prefixes:

- `== Title` — level 1 (chapter)
- `=== Title` — level 2
- `==== Title` — level 3
- `===== Title` — level 4

Match the subsection title case-insensitively. The subsection's content starts on the line after the heading and ends just before the next heading of equal or higher level (i.e., same or fewer `=` characters).

### 3. Identify non-normative blocks to skip

Parameters are normative. Before scanning, mark and exclude non-normative text so it cannot seed a candidate:

- **NOTE delimited block**: `[NOTE]` followed by `====` on the next line, ending at the closing `====`.
- **Inline note**: a single line beginning with `NOTE:`.
- **Example / listing blocks**: delimited by `----` or `....`, and `[source]` blocks.

A candidate parameter must be supported by prose **outside** these blocks. A NOTE may be used as _supporting_ context for a candidate already found in normative text, but never as the sole source.

### 4. Scan for implementation-defined signals

Scan the normative text of the subsection for sentences that hand a value or behavior to the implementation. These keyword patterns are the signals (ordered roughly by strength; counts are their approximate frequency across the current ISA manual, to show they are real, load-bearing phrases and not invented ones):

**Strong signals — almost always name a parameter:**

- `UNSPECIFIED` / `is UNSPECIFIED` — the spec explicitly declines to fix a value (e.g., "The number of ASID bits is UNSPECIFIED").
- `implementation-defined` / `IMPLEMENTATION-DEFINED` / `implementation-specific` — an implementation chooses (e.g., "the size of a cache block ... implementation-specific").
- `WARL` (Write-Any-Read-Legal) / `WLRL` (Write-Legal-Read-Legal) — a field declared WARL or WLRL **is** a parameter; the parameter is its **set of legal values**. Do not require the excerpt to prove that the set is implementation-chosen before accepting the candidate. A set that the ISA happens to fix completely is a degenerate case of the legal-value classification, not a reason to reject the field. Emit the legal-value set as one of the classifications used by the UnifiedDB schema, and fall back to the schema's escape hatch when a field does not fit one.
- `platform-specific` / `vendor-defined` / `custom` — decision delegated below the ISA.

**WARL behaviour without the label.** Searching for the `WARL`/`WLRL` tokens under-reports: a field can have WARL behaviour without being declared as such. The clearest case is a read/write field that is fixed to zero under some circumstances — the set of values it will accept depends on the implementation or on configuration, which is exactly what a WARL legal-value set describes. Treat "this field reads as zero when …", "is read-only zero if …" and similar conditional-writability phrasing as a legal-value parameter even though no WARL token appears.

**Contextual signals — a parameter only when paired with a quantity or a named field:**

- `the number of <X> is` / `the number of implemented <X>` — a count parameter (e.g., "the number of implemented ASID bits, termed _ASIDLEN_").
- `the size of <X>` / `the width of <X>` — a size/width parameter.
- `reserved` — a parameter only when the reservation is _for implementation use_; plain "reserved, must be zero" encodings are **not** parameters and must be excluded.
- `may be` / `may support` / `optionally` guarding a concrete value or range.

**Negative controls — text that looks like a signal but is not a parameter.** Each of these has produced a plausible-looking false positive, so check a candidate against this list before keeping it:

- **Fixed encoding or address conventions** — a CSR number, an opcode, a field position. Fixed by the ISA for every implementation, so nothing is delegated.
- **Advice aimed at software** — `should` / `may` / `is recommended` addressed to compilers, assemblers or programmers describes how to _use_ the ISA, not a hardware choice.
- **A bare `shall` constraint** — a requirement every implementation must meet delegates nothing. A constraint becomes a parameter only when the spec also says the implementation picks the value.
- **`reserved, must be zero`** — a fixed encoding, not a reservation for implementation use.

A candidate that matches one of these must be dropped, not downgraded.

**Named-value anchors:** the spec often tags the exact normative sentence with an inline anchor — a block anchor `[[norm:<id>]]` on its own line, or an inline anchor `[#norm:<id>]#...#` wrapping the sentence. When present, capture the `<id>`; it is the authoritative provenance link for the parameter and pairs the candidate to its normative text.

### 5. For each candidate, extract the fields

For every signal that survives step 3, build a candidate with:

- **name** — an UPPER_SNAKE_CASE identifier in UnifiedDB style. Prefer the spec's own term when it names one (`ASIDLEN` → `ASID_WIDTH`, `PMLEN` → `PMLEN`); otherwise synthesize a descriptive name from the noun phrase (`CACHE_BLOCK_SIZE`).
- **excerpt** — the verbatim sentence(s) from the subsection that justify the parameter. This is mandatory: no excerpt, no candidate. This is the anti-hallucination guard — a reviewer must be able to confirm the parameter against the copied text without re-reading the spec.
- **source** — `file`, `subsection`, and the `norm:<id>` anchor if one exists.
- **definedBy** — the extension(s) that introduce the parameter, as a `condition` per `param_schema.json` (a single `extension: {name: ...}`, or `anyOf`/`allOf` of extension names). Infer from the subsection's owning extension **only when that extension is unambiguous**. The inference is unsafe in two common cases; in both, emit the best guess with `uncertain: true` and an `open_question` rather than asserting it:
  - the parameter is gated by several extensions, none of which owns the subsection — `CACHE_BLOCK_SIZE` lives in a CMO subsection but is defined by `anyOf` Zicbom/Zicbop/Zicboz;
  - applicability depends on another **parameter** rather than an extension — e.g. how many PMP entries are usable follows `NUM_PMP_ENTRIES`, which no `definedBy` condition expresses.
- **schema** — a JSON-Schema-draft-07 fragment for the legal values. Emit `type: integer` / `type: boolean` / `enum: [...]`. **Only** add `minimum`/`maximum`/`enum` bounds that the spec states explicitly (e.g., "ASIDMAX ... is 9 for Sv32 or 16 for Sv39/48/57" → `maximum: 16`). If the spec gives no bound, leave the type unbounded — never invent limits.
- **classification** (the two axes the parameter-extraction effort tracks):
  - `named`: `true` if the spec gives the value an explicit name (`ASIDLEN`, `PMLEN`), else `false`.
  - `config_dependent`: `true` if the legal values depend on another configuration choice (XLEN, paging mode, privilege mode), else `false` for a free-standing value.

### 6. Recall check against the existing UnifiedDB parameter list

For every candidate, check whether UnifiedDB already models it: list `spec/std/isa/param/*.yaml` (the manually curated parameter list) and compare by name and by meaning. Tag each candidate:

- `status: existing` — already in `spec/std/isa/param/` (report the matching filename). Useful as a precision/recall check on the extractor.
- `status: new` — not yet modeled; a genuine recall candidate for a human to review and add.
- `status: possible_duplicate` — a plausible match exists but the correspondence is not one-to-one: the existing file uses a different name for the same concept, the candidate covers only part of an existing parameter, or one candidate spans several existing files. Name the file(s) considered and state what is unresolved.

Matching by name alone is not sufficient — renames and conceptual duplicates will not match textually. When in doubt use `possible_duplicate` rather than guessing: a wrong `new` inflates the apparent recall gap, and a wrong `existing` hides a real one.

Do not overwrite or propose edits to existing files from this skill; it only surfaces candidates for review.

### 7. Write the review envelope

This skill produces **two artifacts, in order**, and stops after the first:

1. **The review envelope** — what is written here. It carries the evidence a reviewer needs: excerpt, anchor, classification, status, uncertainty and open questions.
2. **Mergeable UnifiedDB YAML** — one `param_schema.json`-valid file per parameter, written **only after a human has accepted the candidate**, with every review-only key stripped.

Keeping them separate matters because the envelope is deliberately **not** a valid UnifiedDB parameter file and must not be presented as one: it nests candidates under a `parameters:` wrapper that is outside the parameter object schema, and it omits the required `kind`, `long_name` and `description`. Emitting it is a review step, not a merge-ready result.

Derive the output filename from argument 1 (lowercased, spaces → hyphens). Write `/tmp/<derived-name>.yaml` in this shape:

```yaml
parameters:
  - name: ASID_WIDTH
    status: existing # spec/std/isa/param/ASID_WIDTH.yaml
    definedBy:
      extension:
        name: S
    schema:
      type: integer
      minimum: 0
      maximum: 16
    classification:
      named: true # spec calls it ASIDLEN
      config_dependent: true # ASIDMAX depends on paging mode (Sv32 vs Sv39/48/57)
    signal: is UNSPECIFIED + the number of <X> bits
    uncertain: false
    open_questions: []
    excerpt: |
      The number of ASID bits is UNSPECIFIED and may be zero. The number of
      implemented ASID bits, termed ASIDLEN, ... The maximal value of ASIDLEN,
      termed ASIDMAX, is 9 for Sv32 or 16 for Sv39, Sv48, and Sv57.
    source:
      file: priv/supervisor.adoc
      subsection: Supervisor Address Translation and Protection (satp) Register
      anchor: norm:asidlen
```

Use the Write tool to create the file.

### 8. Self-check before reporting

Run these checks and fix or drop any candidate that fails. They are mechanical on purpose — each one catches a failure mode that is otherwise invisible in a plausible-looking result:

1. **Excerpt is real.** Search the subsection text for each `excerpt` and confirm it appears verbatim. A candidate whose excerpt cannot be found was hallucinated; drop it.
2. **Excerpt is normative.** Confirm the excerpt does not start inside a block skipped in step 3 (`[NOTE]`, `NOTE:`, `----`, `....`, `[source]`).
3. **Signal is named.** Every candidate must cite which signal from step 4 it matched. No signal, no candidate.
4. **Negative controls applied.** Re-read each candidate against the negative-control list in step 4. For a WARL/WLRL candidate, confirm a legal-value classification has been assigned (or the escape hatch used) rather than the candidate being dropped.
5. **Uncertainty is recorded, not resolved.** Any `definedBy` that was inferred across multiple extensions, and any name-vs-meaning match that was not exact, carries `uncertain: true` and an `open_question`.
6. **Names are well formed and unique** — UPPER_SNAKE_CASE, no duplicates within the file.

Report the counts from checks 1 and 2 in step 9; a non-zero drop count is a useful signal, not a failure.

### 9. Report

Print a summary:

- The subsection title found
- The number of candidates extracted, split by `new` / `existing` / `possible_duplicate`
- How many candidates were dropped by the self-check, and why
- How many candidates carry `uncertain: true`
- The path written, and a reminder that it is a review envelope, not a mergeable parameter file
- A one-line-per-candidate list: `name (status, named=?, config_dependent=?, uncertain=?)`

## Worked example (validated against the current database)

Two candidates below were extracted with these rules from real subsections and checked against the committed `spec/std/isa/param/` files — both round-trip to an existing parameter, which validates the extractor's precision.

**`ASID_WIDTH`** — file `priv/supervisor.adoc`, subsection _"Supervisor Address Translation and Protection (`satp`) Register"_, anchor `norm:asidlen`:

> "The number of ASID bits is UNSPECIFIED and may be zero. The number of implemented ASID bits, termed _ASIDLEN_ ... The maximal value of ASIDLEN, termed ASIDMAX, is 9 for Sv32 or 16 for Sv39, Sv48, and Sv57."

Signals: `is UNSPECIFIED` + `the number of ... bits`. Named (`ASIDLEN`), config-dependent (bound is 9 or 16 depending on paging mode), `type: integer, minimum: 0, maximum: 16`. Matches `spec/std/isa/param/ASID_WIDTH.yaml` (`minimum: 0, maximum: 16`, `definedBy: {extension: {name: S}}`).

**`CACHE_BLOCK_SIZE`** — file `unpriv/cmo.adoc`, subsection _"Memory and Caches"_, anchor `norm:cache_block_size`:

> "The capacity and organization of a cache and the size of a cache block are both _implementation-specific_ ..."

Signals: `implementation-specific` + `the size of a cache block`. Unnamed, not config-dependent, `type: integer`. Matches `spec/std/isa/param/CACHE_BLOCK_SIZE.yaml` (defined by `anyOf` of Zicbom/Zicbop/Zicboz).

Output for a run over the `satp` subsection:

```yaml
parameters:
  - name: ASID_WIDTH
    status: existing # spec/std/isa/param/ASID_WIDTH.yaml
    definedBy:
      extension:
        name: S
    schema:
      type: integer
      minimum: 0
      maximum: 16
    classification:
      named: true
      config_dependent: true
    excerpt: |
      The number of ASID bits is UNSPECIFIED ... The maximal value of ASIDLEN,
      termed ASIDMAX, is 9 for Sv32 or 16 for Sv39, Sv48, and Sv57.
    source:
      file: priv/supervisor.adoc
      subsection: Supervisor Address Translation and Protection (satp) Register
      anchor: norm:asidlen
```
