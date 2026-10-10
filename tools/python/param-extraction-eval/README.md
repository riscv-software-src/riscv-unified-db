<!--
SPDX-FileCopyrightText: 2024-2025 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Parameter-extraction evaluation fixtures

A frozen set of specification excerpts paired with the outcome a
parameter-extraction procedure should reach on each. Eleven cases: six
positives, four negatives, and one candidate, which is text that should be
surfaced and then classified out rather than dropped in silence.

```bash
./bin/python -m pytest tools/python/param-extraction-eval -v
```

Deterministic, no API key, no network. It checks the fixtures, not a model.

## Why the negatives carry the weight

Positives are easy to agree on. The cases that separate a working rule from a
plausible one are the passages where a reasonable rule produces a parameter that
should not exist:

| Case | The mistake it catches |
|------|------------------------|
| `NEG_FIXED_ENCODING` | turning a fixed encoding convention into a parameter |
| `NEG_SHALL_NO_DELEGATION` | reading a bare `shall` as an implementation choice |
| `NEG_SOFTWARE_ADVICE` | reading `should`/`may` software advice as hardware configuration |
| `NEG_EXT_GATED_PBMTE` | reading extension gating as a parameter |

`NEG_EXT_GATED_PBMTE` is the subtlest. "If Svpbmt is not implemented, PBMTE is
read-only zero" describes writability that depends on configuration, which is the
shape a legal-value parameter has, but UnifiedDB expresses it with
`definedBy: {extension: {name: Svpbmt}}` and no parameter exists.

## Firing too rarely is the other half

A rule keyed on the `WARL` and `WLRL` tokens misses fields whose legal values
depend on the implementation without either token appearing in the prose. Cases
marked `recall_case` contain no such token, and the suite asserts they do not, so
a token-keyed rule cannot reach them. `POS_RECALL_COUNT_GEILEN` is one: the
writability of `hstatus.VGEIN` follows a count that UnifiedDB already models as
`NUM_EXTERNAL_GUEST_INTERRUPTS`.

Without cases of this shape the set measures precision only.

## The WARL distinction

`CAND_WARL_FIXED_LEGAL_SET` is the reason this set exists.

A CSR field can carry the word **WARL** while its set of legal values is fixed by
the ISA. Software may write anything, the implementation legalises the write, and
the only legal encoding is the same for every implementation. No parameter
follows, and no parameter under `spec/std/isa/param` admits exactly one value.

It is filed as a candidate rather than a negative. The outcome is the same, no
parameter, but the two differ in what the procedure should do on the way there:
a negative should never be raised, while this should be raised and then
classified out, so that the decision is visible to whoever reviews the output.

`POS_WARL_MTVEC_MODES` is deliberately paired with it. Without a WARL positive, a
rule that rejected every WARL field would pass the set while being useless. The
suite asserts both are present for that reason.

## What the tests check

- Each case is well formed and states its expectation.
- Every positive is anchored to a parameter that still exists under
  `spec/std/isa/param`, so an upstream rename fails here rather than silently
  invalidating the fixture.
- Every negative expects nothing extracted and records the risk it guards.
- Every candidate expects to be surfaced and to yield no parameter.
- The WARL candidate and its paired positive are both present.
- At least two cases exercise the recall direction, and none of them contains a
  `WARL` or `WLRL` token.

## Scope, and what this is not

These fixtures evaluate **rules**, applied by a human or by an agent, against
fixed text. They do not run a model and they do not measure recall on a corpus.
They are a regression floor: prose guidance cannot detect when a later edit
breaks it, and this can.

Relevant caveat when interpreting any corpus-level extraction figure: recall
measured on the full specification varies substantially between identical runs of
the same model at `temperature=0`, which is why this set is deliberately small,
fixed and deterministic rather than a sampled benchmark. See
[#2163](https://github.com/riscv/riscv-unified-db/issues/2163).

## Provenance

Built while reviewing [#2097](https://github.com/riscv/riscv-unified-db/pull/2097),
the `extract-parameters-from-subsection` skill. Its author suggested the set land
as its own contribution rather than as a subtree of that PR, so that is what this
is. Placement was raised separately as
[#2158](https://github.com/riscv/riscv-unified-db/issues/2158); if maintainers
would rather these sat beside a skill, under `tests/`, or elsewhere, moving them
is a rename.
