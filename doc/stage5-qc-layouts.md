<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# QC CSR layout authoring contract

This implements approved review entry 32: replace
`spec/custom/isa/qc_iu/csr/Xqci/gen_mcliciX.rb` with the existing restricted
Python `.layout` mechanism. The inherited registry's proposed `author qc-mclic`
command is superseded. There is no QC-specific CLI, second renderer, Ruby
fallback, network download, or native UDB runtime dependency.

## Ownership and semantics

The original generator writes next to itself, irrespective of its working
directory. Its five heredocs own **56 files**, not all `qc.*` CSRs:

| Family | Indices | Address | Fields |
| --- | --- | --- | --- |
| `qc.mclicipN.yaml` | 0–7 | `0x7f0 + N` | IRQ `32*N`–`32*N+31`, one-bit pending |
| `qc.mclicieN.yaml` | 0–7 | `0x7f8 + N` | IRQ `32*N`–`32*N+31`, one-bit enabled |
| `qc.mclicilvlNN.yaml` | 00–31 | `0xbc0 + N` | IRQ `8*N`–`8*N+7`, four-bit level |
| `qc.mwpstartaddrN.yaml` | 0–3 | `0x7d0 + N` | `ADDR`, bits 31–0 |
| `qc.mwpendaddrN.yaml` | 0–3 | `0x7d4 + N` | `ADDR`, bits 31–0 |

All are 32-bit, machine-mode, writable CSRs, defined for XLEN 32 and
`Xqciint`. Level and watchpoint CSRs additionally require version `>=0.4`.
All fields are RW and reset to zero. Preserve every field name, location,
description, comment, schema reference, and any existing IDL literally.
Extension history documents the enable-address correction and addition of
the level/watchpoint families. The pending CSRs are directly referenced by
`qc.{setinti,clrinti,c.setint,c.clrint}` instruction IDL; resolution, extension
documents and simulator generation also consume the custom overlay.

No schema, model, instruction, configured-prose, or CSR-behavior changes belong
to this conversion. Other QC CSRs remain handwritten and unowned.

## Preimplementation oracle

Before implementing Python generation, copy the original Ruby generator into
an isolated project-local scratch directory, then execute **only that copy**
under the original shared Ruby lock with `mise exec --no-deps -- ruby`.
Never run native generation against the current source directory.

Freeze all original native output bytes, tracked output bytes, source bytes,
SHA-256 hashes, complete output paths, parsed YAML semantics, Ruby version and
capture command in `tests/data/qc_layouts/oracle.json`. Compare the entire
56-file set. Classify any original-versus-tracked differences before deciding
the expected Python bytes; intentional Stage 4/schema corrections take
precedence over stale Ruby generation. Preserve raw native evidence.

The only permitted new output normalization is the existing layout ownership
warning, identifying the corresponding `.layout` source. Removing exactly that
warning must recover the frozen accepted source bytes; do not normalize YAML
formatting, comments, descriptions, locations, or semantics.

Capture completed before Python implementation at baseline
`d6b06ca35dacd03da77be638fc7b81f1b1297b64`, using Ruby
`3.4.10 (2026-06-30 revision 2b0b7728dc) +YJIT +PRISM [aarch64-linux]`.
The original generator SHA-256 is
`1759ceaf80aa55473f7434ed2e2c44c959fca9d206330ea6b3a71c25517b556a`.
All **56 files / 96,366 bytes** are exactly identical between native generation
and tracked source, including parsed semantics. There are **zero corrections
or exceptions** to reproduce in this owned set and no embedded IDL bodies.
This does not authorize changes to corrected neighboring QC data or schemas.
The fixture retains both raw captures and parsed meanings, not a Python-produced
expected result.

## Public API and resource contract

Extend generic layout source selection, not the rendering grammar. Standard
selection remains the default and must retain its **532 outputs / 31 sources**
exactly. QC selection owns 56 outputs / five sources. Selecting both owns 588
outputs without overlapping ownership.

A public immutable layout collection describes relative template and output
roots, recipes, and an optional package-resource prefix. Custom collections
must not be forced under `spec/std/isa`. Callers can provide an explicit,
separate source tree while writing to a chosen output root. Explicit source
inputs must never silently fall back to installed resources. Partial source
sets, unknown collections, unsafe paths, missing resources, invalid UTF-8,
and duplicate ownership are explicit errors.

Reuse `udb.layouts` and `udb.authoring.AuthoringPlan`: deterministic
dependencies and source warnings, atomic replacements, read-only outputs,
and nonwriting drift checks. Recipe mappings and nested inputs are immutable
snapshots. Generation does not modify templates or other unowned files.

Installed authoring must use bundled QC layouts or caller-provided source
data offline, outside a checkout, without reading source through repository
fallbacks. Resource packaging and shared CLI integration are supplied as
unapplied patches for the parent. The existing generic `generate-layouts`
command gains optional collection/source selection; its current default
behavior and exit codes remain unchanged.

Use `udb.layout_collections.get_layout_collection("qc_iu")` with
`udb.layouts.layout_plan` or `generate_layouts`, passing
`collections=(collection,)`. `LayoutCollection` captures a `name`, relative
`source_root` and `output_root`, relative `LayoutJob` recipes, optional
`resource_root`, and recipe-code `dependencies`. A caller-defined collection
does not require registration. `source_root=` on the planning/generation
function chooses a separate physical source tree, not a different output tree.
`layout_collection_names()` exposes the two registered CLI selectors:
`standard` and `qc_iu`. After parent integration:

```shell
udb generate-layouts --root . --collection qc_iu --check
udb generate-layouts --root generated --collection qc_iu --source-root source-data
udb generate-layouts --root generated --collection standard --collection qc_iu
```

QC resources reside at `udb/_data/custom_layouts/qc_iu/csr/Xqci/*.layout`;
the 56 regenerated records at `udb/_data/custom_isa/qc_iu/csr/Xqci/*.yaml`
provide an installed drift oracle, not a full bundled QC database. In particular,
this does not bundle QC's checkout-relative globals include or change overlay
resolution. No configured-prose source is converted here.

## Acceptance

Targeted tests must establish exact native/tracked/converted byte comparisons,
all 56 parsed CSR semantics and index boundaries, complete owned-file set,
all 532 unchanged standard outputs, independent template/output roots,
immutable recipes, explicit source/resource failures, safe ownership,
nonwriting drift checks, read-only regeneration, and standalone resource use.

The parent must apply packaging/invocation patches, build wheel and sdist,
rebuild the wheel from sdist, and run the supplied actual installed acceptance
helper with no checkout/network/native helper available. This lane does not
claim package acceptance before that gate runs. Ruby consumer deletion and
Rake/bin/CI wiring remain parent-owned and are blocked on accepted integration.
