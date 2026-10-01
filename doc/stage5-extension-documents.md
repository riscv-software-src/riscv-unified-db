<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Retained extension documents

This lane owns extension AsciiDoc and the explicit official external PDF
boundary, independently of the retired document/publication framework.
Instruction and CSR content is retained; manual, configuration publication,
portfolio/PRM, appendix, Explorer and CSR HTML API are not recreated.

## Contract

Input is an already resolved `ConfiguredArchitecture`, an ordered nonempty list
of `EXT[@VERSION|latest|REQUIREMENT]` selectors, and explicit document options.
Extension lookup, version matching, configured availability, implied
requirements, IDL compilation and IDL AsciiDoc rendering reuse the accepted
database, version, configuration, solver and compiler services.

The default basename is the first selector (matching legacy behavior); an
explicit basename overrides it. Basenames must be single safe filename
components, not paths. Generation emits UTF-8/LF source and assets under the
requested output directory. Git/date provenance is explicit caller metadata,
never a runtime process or checkout lookup.

Required content: revision/licensing/contributors/version history; extension
descriptions and requirements; instruction summaries, version/RV32/RV64
availability and implied-instruction tables; instruction encodings, decode
variables, configured prose, operations and defining-extension requirements;
global parameter descriptions, definition conditions, complete JSON schemas,
configured values and constraints; CSR summaries, attributes, formats, field locations/types/reset values and
descriptions, custom read/write behavior; reachable IDL function descriptions,
signature tables and bodies. Source-visible function calls are closed over the
accepted declarations as well as typed/pruned reachability, so constant folding
does not leave undocumented function targets. Native absence of an instruction operation remains
absence, not an invented body or placeholder.

Extension content selection uses the accepted unconfigured architecture's
invariants, matching the native `unsatisfiable_by_arch?` boundary. The requested
configuration still controls prose, IDL pruning, optional-field coloring and
fixed XLEN diagrams. Native full-config instruction-link queries are open-world:
the generator projects mandatory versions and parameter facts into the accepted
partial model for these queries only. CSR/extension links remain closed for full
configurations; partial configurations retain their declared restrictions.

Configured prose is an injected semantic dependency owned by prose23:
`render_prose(text, *, record, field_path, architecture) -> str`. The default
adapter imports the installed `udb.prose` provider and supplies `CapturedProse`
with `text`, `source`, `path=field_path`, and the record's scalar `span`, plus
`ProseInputs.from_architecture(architecture)`. Restricted partial configurations
may require caller-captured prose facts under that provider's public contract.
Unsupported configured templates fail explicitly. No Ruby fallback, second
solver, template evaluation, source reopening or custom checkout discovery is
permitted.

## Fidelity evidence

Before Python emission implementation, capture genuine current native source
artifacts through `GenExtPdfOptions#gen_adoc`. Keep raw artifacts and SHA-256,
selectors, configuration and source provenance in the fixture manifest.
Execute the original Xqci script unchanged, intercepting only its subprocess
boundary to emit source rather than start a renderer. Preserve the original
checked-in Xqci golden separately. A native error is an error observation, not
an output parity pass.

Compare complete artifacts, not selected snippets. Only explicitly named
dynamic metadata or documented formatter presentation changes may be normalized.
Any source-content correction or missing native content must be separately
classified rather than hidden by a broad text normalizer.

`test_extension_fidelity.py` compares all five successful complete captures:
Zba/unconfigured, Zicsr/unconfigured, Zicsr/MC100 full, Xqcicsr/QC and the original
Xqci script/QC. `reviewed-deltas.json` freezes each added/corrected line with its
native location, surrounding context, classification and complete hashes.
It distinguishes normative parameter/requirement additions, corrected implied
conditions, complete source-visible function declarations, malformed native
tuple assignments and the native fixed-RV32 `jvt`/`ssp` defects. These are explicit
source-content differences, **not** formatter normalization or raw parity.
The original Xqci golden remains separate; its only difference from the current
native script capture is the captured commit-provenance line.

The development capture helpers regenerate evidence only on explicit
request. They are not a test update mechanism. Raw native fixtures are never
rewritten by ordinary source generation or tests.

## Entry points and parent integration

```python
from udb.extension_docs import DocumentOptions, generate_extension_document
from udb.extension_docs.pdf import render_extension_pdf

source = generate_extension_document(
    architecture,
    ["Zba@latest"],
    "out",
    options=DocumentOptions(revision="explicit provenance"),
)
render_extension_pdf(source, source.with_suffix(".pdf"))
```

The parent-owned CLI patch adds `udb generate ext-doc` (source-only by default,
`--format pdf` explicitly renders) and `udb render pdf INPUT.adoc --out FILE`.
The repository adapter explicitly receives its input root and preserves
`./bin/generate ext-doc`'s PDF default. The new Xqci wrapper preserves the original
exact selectors, literal output directory and basename; custom QC data must be
explicit input, not installed package data. `--no-csr-field-desc` now genuinely
suppresses descriptions, correcting the native template's ignored flag.

Unapplied `gen/handoff/extension-*.patch` files cover shared CLI, wrappers,
packaging/licensing, installed checks, registry and regression definitions.
Installed wheel/sdist acceptance, lockfile updates, workflow generation,
configured-prose source cutover and Ruby retirement remain parent-owned.

## Rendering boundary and resources

Source generation is standalone/offline and never executes Ruby, Git, native
helpers, a renderer or network tools. Resource files are regular packaged files,
not runtime checkout symlinks. `assets/manifest.json` lists the declared official
theme/font/image closure and upstream paths/hashes; unrelated fonts, images,
the QC database, and the old framework are not bundled.

PDF rendering is explicitly requested and may invoke externally installed
official `asciidoctor-pdf` only. No UDB-owned Ruby lexer, helper, diagram wrapper
or require is permitted. Python prepares IDL highlighting and register diagrams.
Explicit caller theme/fonts/images remain supported. Missing tools/resources,
renderer failures/timeouts and invalid outputs are typed errors; failed renders
must not replace an existing PDF or leave scratch files.
Timeout/cancellation terminates the private renderer process group, including
an explicitly supplied serialization wrapper; resources live in an
output-adjacent directory and are removed after success or failure.

Caller source assets are explicit byte mappings. Includes are bounded, UTF-8,
relative to the included file and closed over declared/package assets; cycles,
traversal, remote images, output conflicts and escaping parent symlinks are errors.
The mapped standard floating-point CSR include is emitted with its complete
register labels and geometry.

Live rendering acceptance must inspect actual page text, document metadata and
representative rasterized pages, independently of source parity and installed
offline source checks. Serialize every Ruby invocation on the original Ruby
lock; never hold it with the heavy Python test lock.
The complete Zba comparison renders frozen native source and Python source
through the same official-renderer preparation boundary. QC rendering uses
the explicitly reviewed native additions and also exercises the QC theme,
embedded fonts, CSR field content and mapped floating-point diagram.
This is real official PDF acceptance, not a claim of legacy Ruby-renderer
binary-PDF identity.
