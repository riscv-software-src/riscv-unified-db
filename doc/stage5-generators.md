<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5/6 generator and consumer inventory (source-traced)

Status: **inventory/contracts only**; all proposed migration gates below are **pending**, not implemented. Baseline: accepted Stage 4 `f5a2099a`. This report inventories first-party generators and callers; `ext/` third-party trees and generated `gen/` output are not migration credit. Stage 1–4 Python foundations already exist (packaged data, resolution/schema/serialization/layout, configurations/conditions, IDL compiler/semantic passes). Stage 5 output owners and Stage 6 invocation cutovers remain pending, including scripts that currently wrap Ruby. Preserve every legacy output/consumer unless a maintainer explicitly approves a scope reduction. `.adoc` source must be generated offline by installed Python; **only already-installed official external Asciidoctor/asciidoctor-pdf rendering** may use Ruby.

## Approved retention scope (2026-09-30)

This section and the registry's `scope_decisions` override the historical
preserve-all inventory below. Approval to retire a product is not a claim that
its source and consumers have already been removed.

| Disposition | Families/capabilities |
| --- | --- |
| Retain | C/SV configuration headers, generic C/SV/Go outputs, C++ hart/decode source, extension AsciiDoc/PDF, instruction table, UDB query/report/instruction-matching CLI, raw/resolved architecture and schemas, Python layouts, strict profile configs, architecture-test scaffolding, schema MDX, Pages landing/schema indexes, IDL highlighting. |
| Retire | ISA manual source/HTML, configuration-document source/HTML, instruction appendix source/PDF, profile-release documents, PRM source/PDF, all three Explorer browsers and XLSX, profile-extension report, JSON-reference search index, floating-point stimulus generator, manual title metadata, CSR HTML-fragment API, portfolio appendices, PRM external-document preprocessing, Ruby type/gem metadata. |
| Replace | Ruby API docs with a Python API reference; IDLC CLI with an interface aligned to Python IDL; QC CSR-family authoring with Python `.layout` files; generated C++ Bits source tests with native C++ randomized/property tests. |
| Conditional Python conversion | Configuration-sensitive prose and exception-name expansion: implement in Python if feasible; otherwise retirement is authorized. Never retain Ruby as a fallback or silently emit unevaluated/wrong configuration text. |
| Retire framework, preserve required content | Remove the old shared document-template framework and obsolete MMR/manual/PRM/portfolio pieces; instruction and CSR content remains part of retained extension documents. |

The historical registry keeps all 46 families so deletion is auditable:
21 are retired, six have explicit replacement/conversion contracts, and 19
remain retained without that special disposition. Retired-family golden/installed
generation obligations below are superseded by coherent removal of their code,
CLI/build/CI/publication consumers, fixtures and documentation. Do not weaken
tests for retained capabilities. Native C++ property/randomized tests must
preserve the Bits coverage previously supplied by generated tests.

ISA-manual chapter packaging is no longer a decision or distribution dependency.
Extension PDF rendering still uses the official external Asciidoctor toolchain.
Schema/Python API documentation and publication indexes remain retained.
Query/report/disassembly capabilities remain, but final Python CLI spelling
and compatibility aliases have not been approved by this scope decision.

## Accepted native Bits replacement

Review ID34 is implemented as handwritten native properties, not a Python
test-source generator. The Ruby authoring script and six generated sources are
removed. Independent native review accepted all legacy coverage and added
signed/runtime/unknown boundaries; standalone CTest passed 95 cases. The retained
backend aggregate passed its 39 property/defect cases through actual Rake asset
rules and CMake. `regress-native-bits` runs independently of hart generation.
See [the native contract](stage5-native-bits.md) for exact coverage, narrow
production fixes, replay, toolchain linking and unchanged limitations.

## Inventory method and acceptance

### Accepted schema-documentation slice

Layer 24 provides `udb generate schema-docs`, a public `udb.schema_docs` API
and the Python-backed repository wrapper. Full native current/history/custom
artifact comparisons and expanded Psych examples preserve exact bytes while
exposing located presentation limits. Installed wheel/sdist reconstruction
retains resources, license metadata and third-party notices; the actual
installed CLI passes complete native-artifact and diagnostic checks.
Docusaurus compiled an isolated generated-schema site without rewriting
historical pages. The [schema contract](stage5-schema-docs.md) records deliberate
historical CI drift and retained legacy anchor/provenance limitations.

### Accepted instruction-table slice

Layer 25 provides `udb generate instruction-table` and public immutable encoding
descriptors. Complete stdout/file artifacts match the frozen genuine Ruby
outputs; selecting RV32/RV64 does not filter database instructions. The
[instruction-table contract](stage5-instruction-table.md) documents exact
formatting, source provenance, and UTF-8/LF output/error behavior.
Native API/CLI tests run alongside the existing Ruby integration oracle, and
the actual wheel rebuilt from sdist passes installed acceptance outside the
checkout. Repository wrapper consolidation remains a later CLI-cutover step.

### Historical inventory method

Each family below receives its legacy command, implementation/templates, input/config/version matrix, output paths and consumers, fixture and comparison policy, prospective Python API/CLI layer above Stage 4, and pending installed/CI gate. An apparent Python script is **not migrated** if it shells a Ruby script or requires repository paths. All installed generation gates use offline wheels/sdists outside the checkout, no repository, network, or UDB-owned native toolchain. Separate repository gates may compile generated C++/C/Go/SV and separately render documents with external Asciidoctor.

The machine-readable [generator registry](stage5-generators.json) records 46
families and eight workflow-consumer groups, including dormant templates and
repository-only authoring tools. Gates apply to retained capabilities and their
approved replacements, not retired products. Pending gates are not claims of
implemented tests. Capability contracts must add executable artifact oracles
and exact commands before cutover.

## Owning-layer sequence

Layer 20 owns this inventory and its acceptance contracts. Layer 21 owns the
C/SystemVerilog configuration-header capability, including shared macro
formatting, CLI wiring, artifact oracles and installed coverage.

Subsequent layers follow dependency order, with one separately reviewable
capability per layer; names/numbers are assigned when created, not speculative
branches. Shared configured-prose rendering and encoding descriptors precede
generic C/SV/Go output and instruction tables. Profile configuration conversion
remains independent of retired profile documents. Extension-document-owned
components/assets precede extension AsciiDoc/PDF. Schema/Python API documentation
and retained publication indexes have separate owners. C++ source emission and
static resources build on accepted IDL passes, with generated-code acceptance
and native C++ Bits randomized/property coverage before cutover. Authoring tools
and the retained portions of all eight workflow groups remain in scope.

Stage 6 CLI/task orchestration, setup/quality and release consolidation have
separate owners above the accepted capabilities. Ruby deletion is a final layer,
blocked until every retained consumer is covered. Package-index publication
requires the separate name/ownership decision; fork branch publication is not
authorization to publish a distribution.

## Historical generator contracts

The source traces below describe the original inventory. Apply the approved
retention scope above before treating any proposed API, output or gate as work.

### Retained surfaces identified by independent contract review

The custom ISA includes a separate Ruby/ERB authoring generator,
`spec/custom/isa/qc_iu/csr/Xqci/gen_mcliciX.rb`, that emits the indexed
`qc.mclic{ip,ie,lvl,mwpstartaddr,mwpendaddr}*.yaml` CSR families. It is not a
`.layout` file and is not covered by standard layout generation. Its Python
authoring replacement must preserve the complete generated path set and exact
CSR bytes, with an installed generator and custom-source drift gate.
The **135-file count below is only YAML configured prose**, not all embedded
ERB: this Ruby source additionally contains ERB heredocs.

`bin/udb` and `bin/idlc` are retained CLI consumers, not aliases of the already
ported Python inspection commands. Their Thor implementations are
`tools/ruby-gems/{udb,idlc}/lib/{udb,idlc}/cli.rb`. Preserve UDB
`validate spec|cfg`, `extension`, `parameter`, `extensions`, `parameters`,
`csrs`, and `disasm ENCODING`; preserve IDLC `compile --format yaml --root`,
`eval`, and `tc inst`, including their supported filters/formats, output
semantics and errors. The compiler API alone does not close these CLI contracts.

Two model methods currently cross the rendering boundary in-process:
`manual.rb` uses `Asciidoctor.load(...).doctitle`, and `csr.rb` implements
`Csr#description_html` with `Asciidoctor.convert`. Neither may remain a hidden
installed Ruby dependency. Manual chapter titles become captured resource
metadata (or explicit caller-supplied metadata), verified against the official
external renderer during resource preparation. Retain HTML description
fragments as an explicit optional external-rendering capability; source
generation remains Python-only and missing renderers are reported explicitly.
Do not replace either with a homegrown general AsciiDoc renderer.

**Appendix oracle exception:** the legacy golden contains
`:wavedrom: {docdir}/../../bin/wavedrom`. All appendix byte-equality statements
in this inventory apply after removing exactly this known tool-location
attribute from the expected artifact. Installed output must not emit a dead
checkout-relative path. Supply WaveDrom and bytefield executables at the external
render step, preserving all diagram blocks and testing rendered results.
`bin/asciidoctor`, `bin/wavedrom`, `bin/bytefield-svg` and `bin/aub*` belong
to the explicit rendering/toolchain consumer inventory; they are not runtime
dependencies of installed source generation.

Repository validation and fixture authoring remain first-class workflows:
`./do test:csrs`, `test:inst_encodings`, `test:schema`, `test:idl`,
`test:llvm`, `chore:update_golden_appendix`, and
`chore:udb_gen:update_fixtures`, plus `bin/chore`'s Xqci and fixture commands.
Their replacements must preserve the CSR pre-commit hook, encoding/IDL CI
coverage, `tools/python/auto-inst` tests, and exact intended fixture file sets.
This is separate from running pytest against previously captured fixtures.

Additional consumers include `tools/mcp_gen_server/server.py` and its README
(resolved tree paths); `.github/workflows/autofix.yaml`,
`autofix-comment.yml`, and `copilot-setup-steps.yml`; Ruby launch/recommendation
settings in `.vscode/{launch,extensions}.json`; `.rubocop.yml`,
`.solargraph.yml`, `CLAUDE.md`, and `codecov.yml`.
The gem-install-time native downloader
`tools/ruby-gems/udb/ext/udb_download/extconf.rb` and Ruby-owned
`tools/ruby-gems/udb/python/yaml_resolver.py` require explicit retirement after
their consumers are replaced. A Python filename is not proof of cutover.

### Implemented foundations versus pending structured generators

- `./do gen:resolved_arch CFG=_ [COMPILE_IDL=1]` (`Rakefile:79-99`): Python `ResolvedDatabase.write()` and installed `udb ... resolve OUT` already provide deterministic trees/manifests, and `write_resolved_schemas()` / `udb ... schemas OUT` already publish versioned `$id` (`doc/python-api.md:114-174`, `Rakefile:100-105`). Rake wrapper and optional globals.isa-to-YAML export remain Ruby. Proposed core `udb resolve`/`udb schemas` already exist; extend optional semantic IDL export if still consumed. Fixtures: existing schema publication snapshots and resolved tree; canonical structured equality, schema-version/immutability, config `{_,rv32,rv64}`, stale manifest and installed offline gate pending for full old invocation parity.
- `./do gen:arch`: `Rakefile:272-276` shells Python `udb generate-layouts --root .`; tracked `spec/std/isa/**/*.yaml` byte drift gate (`--check`) exists from Stage 2. Repo wrapper not migrated. Installed data loads bundled tracked YAML; no runtime layout execution.
- `./do gen:cfg` and `./bin/chore gen -f profile-cfgs`: `Rakefile:320-341`, `bin/chore:390-415`; enumerate all `_` architecture profiles to emit read-only `cfgs/profile/<profile>.yaml` via Ruby `profile.to_strict_config`. Proposed core `udb generate profile-configs --out DIR`, typed strict-config conversion + canonical writer, no checkout assumption for installed command; tracked-file byte drift and semantic version/presence fixtures for every profile pending. Python profile queries exist but strict-config transformation is not documented.
- `./bin/generate cfg-c-header|cfg-svh-header -c CFG [-o FILE]` (`bin/generate`, `bin/udb-gen`, `udb-gen/lib/udb-gen/{cfg_header_base,defines}.rb`, `generators/cfg_{c,svh}_header/generator.rb`): default stdout/config `_`, named or path config; emit `#define`/SV `` `define`` macros, guards and values. `./bin/chore gen -f cfg-headers` uses `mc100-32-full-example` golden `tests/golden/mc100-32-full-example.golden.{h,svh}` (`bin/chore:448-475`). Proposed core `udb generate cfg-c-header|cfg-svh-header --config CFG [-o FILE]` and shared typed define formatting. Reviewed golden bytes plus C preprocess and SV syntax, installed offline CLI gate **pending**.
- `./do gen:go|c_header|sverilog CONFIG=_ OUTPUT_DIR=...`: Ruby Rake resolves architecture paths then shells existing `backends/generators/{Go/go_generator.py,c_header/generate_encoding.py,sverilog/sverilog_generator.py}` (`backends/generators/tasks.rake`). Files `gen/go/inst.go` (package `riscv`, imports `cmd/internal/obj`), `gen/c_header/encoding.out.h` (Spike/ACTs/Sail per task description), `gen/sverilog/riscv_decode_package.svh`; Python scripts also accept extension filters, `RV32|RV64|BOTH` and `--include-all`. The C/SV path is especially **not migrated**: Rake `with_resolved_exception_codes` renders exception code names through Ruby ERB into a temporary JSON file before invoking Python; `backends/generators/generator.py` reads resolved directory YAML. Proposed `udb generate go|c-encoding|sv-decode --config CFG --output FILE` over configured encoding/CSR/code descriptors with native Python exception-name formatting; preserve architecture/extension/include-all filters. Byte comparison after normalizing generated command prelude, plus canonical opcode/mask/CSR equality; Go consumer compile, C compile, SV lint separately; installed wheel generation without toolchain/repository pending.
- `./bin/generate inst-table [-c CFG] [-o FILE]`: Ruby `udb-gen/generators/inst_table/{generator,table_builder}.rb`, stdout default; current `udb-gen/test/{unit,integration}/test_inst_table.rb`. Proposed `udb generate instruction-table` with typed table rows + deterministic formatter; canonical row equality, text golden and extension/version/encoding cases, installed offline pending.
- `./bin/udb-gen isa-explorer -t {ext-browser,inst-browser,csr-browser,xlsx} -o DIR [--skip N]` (also `bin/generate`): `udb-gen/generators/isa_explorer/{generator,table_builder,js_xlsx_writer}.rb`, `templates/isa_explorer/{ext,inst,csr}-browser.html.erb`, outputs `DIR/{ext,inst,csr}-explorer.html`, `DIR/isa_explorer.xlsx` with Extensions/Instructions/CSRs sheets (`generator.rb:85-214`). Shared typed table schema feeding non-ERB HTML/static JS or Python XLSX library; `udb generate isa-explorer --type ... --config CFG --out DIR`. Browser DOM/filter/link and spreadsheet sheet names/cell values/types/formulas/hyperlinks/ordering; **no XLSX ZIP byte oracle**. Existing four CI browser/workbook jobs `.github/workflows/regress.yml:971-1045`; offline installed and client/browser smoke gates pending.
- `./do gen:index`: `backends/indexer/tasks.rake` launches Node `index-unifieddb.js <repo-root>` and writes `gen/indexer/index-unified.json`; README incorrectly says `index-unifieddb.json`. JS recursively indexes checkout YAML/JSON as relative `$ref` paths, not installed resources. Proposed `udb generate index --scope ... --out FILE` explicitly defining ISA vs full-tree scope and reference schema; canonical JSON fixture + search client ingestion/query smoke, offline installed no checkout; retain deployed JS runtime only if a real consumer is found.

### AsciiDoc, documents, simulator, and supporting assets

- **Extension docs** `./bin/generate ext-doc -c CFG -o DIR [-b BASENAME] [-i] [--no-csr-field-desc] EXT[@VERSION] ...` (`udb-gen/generators/ext_doc/{generator,helpers}.rb`, `udb-gen/templates/ext_doc/*.erb`, `templates/common/{csr,inst,mmr}.adoc.erb`): emits `DIR/<basename>.adoc` and presently renders `DIR/<basename>.pdf` through `asciidoctor-pdf`. Versions accept default/latest/exact (usage suggests range syntax, validator may reject it; test explicitly) and implied extension lists. `tools/scripts/gen_xqci.rb` composes Xqci version + required extensions from `spec/custom/isa/qc_iu/ext/Xqci.yaml`, `qc_iu` config, QC PDF theme/assets; `tests/data/golden/Xqci@0.13.0.adoc`, `bin/chore:424-442`, `regress-gen-ext-pdf`. Proposed `udb[docs] generate ext-doc --config ... --extension EXT@REQ ... --out DIR` core AsciiDoc without renderer, `udb render pdf` optional **external installed** official renderer with explicit assets. Normalize generated commit/date line; semantic sections/encoding/CSR/link oracle, stable fixture review plus external PDF inspect/render gate pending. Rendering uses theme/fonts/images, diagrams and legacy `idl_highlighter`; Python must replace UDB-specific preprocessing/syntax definition, not external renderer.
- **ISA manual** `./bin/generate manual -c CFG -v {all,VERSION[,VERSION...]} -f html [-o DIR]` (`udb-gen/generators/manual/{generator.rb,tasks.rake}`, `udb-gen/templates/manual/{index,isa_nav,isa_version_index,ext,csr,func,instruction,param_list,playbook}*.erb` and `templates/common/csr.adoc.erb`). Rake dynamically reads `spec/std/isa/manual_version/**/*.yaml` and referenced `manual/isa.yaml`, chapters/version prose from `ext/riscv-isa-manual` git trees; writes `DIR/isa/<version>/antora/{antora.yml,nav.adoc,modules/{chapters,insts,csrs,exts,funcs,params,ROOT}/pages/*.adoc}`, top landing/playbook at `DIR/isa/top/<version|all|sha256(version-list)>/antora/...`, HTML at `DIR/isa/top/<hash>/html` (`tasks.rake:19-481`). Legacy command calls `git submodule update`, git archive, local git init/commit and `antora ... --fetch`: **not offline/installed**. Python `udb[docs] generate manual --config CFG --versions ... --out DIR --chapter-source PATH` must bundle/accept versioned chapter sources and assets; never fetch or discover checkout on installed generation. Compare page set, canonical versions, nav/anchors/cross-references, chapter content including prose and manifests; explicit separate external Antora/render HTML smoke and no-network wheel AsciiDoc gate pending. Distinguish Antora (Node site assembler) from allowed official Asciidoctor rendering; no UDB-owned Ruby plugin.
- **Config HTML/AsciiDoc** `./do gen:adoc[CFG]`, `./do gen:html[CFG1,CFG2,...]`, `./do serve:html[CFG,PORT]` (`backends/cfg_html_doc/{adoc_gen,html_gen,tasks}.rake`, `templates/{csr,inst,ext,func,landing,toc,config}.adoc.erb`): `gen/cfg_html_doc/<cfg>/adoc/{csrs,insts,exts,funcs}/{record}.adoc`, `all_<type>s.adoc`, `ROOT/landing.adoc`; `antora/modules/{ROOT,csrs,insts,exts,funcs}/pages/*`, nav, `antora.yml`, `playbook.yaml`, prose from `spec/std/isa/prose`, final `html/`. `html_gen.rake:238-250` uses Antora `--fetch` (network). Proposed `udb[docs] generate config-doc --config CFG --out DIR` consolidate page/format helpers with manual but retain both legacy page sets/anchors; bundle or accept prose/assets, external HTML assembly separate. Compare representative `example_rv64_with_overlay` page set/links/anchor/IDL and normal config; installed offline AsciiDoc, separate external HTML/link gate pending.
- **PRM** `./do prm:adoc[NAME]`, `./do prm:pdf[NAME]`, `./do prm:view[NAME]` and alias tasks `generate_prm_{adoc,pdf}[NAME]` (`backends/prm_pdf/{tasks,adoc_gen,pdf_gen}.rake`, `tools/ruby-gems/udb/lib/udb/prm_generator.rb`, `templates/{config,csr,ext,non_isa_spec,prm_main}.adoc.erb`, `backends/common_templates/adoc/*`). Input `spec/custom/non_isa/prm_example/<name>.yaml` (e.g. `prm_demo_rv32_with_external`), processor config and custom non-ISA specs/external docs; `gen/prm_pdf/<name>/adoc/{config,csrs,insts,exts,specs}/*.adoc`, `pdf/_prm_main.adoc`, `<name>-specification.pdf`; PRM PDF theme/logo/fonts (`backends/prm_pdf/pdf-theme`). Ruby `ContentSanitizer`, `ExternalDocumentationRenderer`, `FileIncluder` preprocess relative `.edn` includes and headings; they are UDB logic and must be Python, with caller-supplied offline local external docs and explicit missing-input errors rather than fetching. Proposed `udb[docs] generate prm --prm PATH --out DIR [--assets DIR]` writes full source tree including main `.adoc`; external `asciidoctor-pdf` only for PDF. Fixture custom PRM with ISA, non-ISA, missing/available external includes; semantic sections/paths/assets/links/source mapping and PDF smoke/golden pages pending. `PdfGenerator` currently invokes binary from Ruby; cannot credit entire path as migrated.
- **Instruction appendix** `./do gen:instruction_appendix_adoc` and `./do gen:instruction_appendix [ASSEMBLY=1]` (`backends/instructions_appendix/tasks.rake`, `templates/instructions.adoc.erb`) use `_` possible instructions to write `gen/instructions_appendix/all_instructions.adoc` and external-rendered `instructions_appendix.pdf` with `THEME`/fonts/images. Tracked **byte-exact** fixture `tests/golden/all_instructions.golden.adoc`, existing `./do test:instruction_appendix`; Python `udb[docs] generate instruction-appendix --assembly ... --out DIR`, same named source and optional separate external PDF. Golden diff including assembly variant, link/encoding/section checks and installed offline gate pending.
- **Profile releases / portfolio** `./do gen:profile_release_{pdf,html}[RELEASE]`, `./do portfolios`, shortcuts `./do RVI20|RVA20|RVA22|RVA23|RVB23|MockProfile{,Release}` (`backends/profile/tasks.rake`, `backends/profile/templates/profile.adoc.erb`, `backends/portfolio/{tasks.rake,templates/{beginning,ext_appendix,inst_appendix,csr_appendix,idl_func_appendix}}`). Rake dynamically enumerates every `spec/std/isa/profile_release/*.yaml`, profile family and referenced profiles; `PortfolioDesign` constructs a portfolio-specific configured architecture. Outputs `gen/profile/{adoc,pdf,html}/<release>ProfileRelease.{adoc,pdf,html}` and render scripts `adoc2{pdf,html}.sh` (scripts shell `bundle exec`, must disappear). `pf_get_latest_csc_isa_manual` clones/updates CSC and docs-resources repositories on demand: replace with explicit offline locally bundled/caller-supplied chapter and asset inputs. Proposed `udb[docs] generate profile-release --release NAME --out DIR`, Python portfolio requirements/view layer; same templates as portfolio appendices, external rendering optional. Test `RVI20` plus all listed releases, sections/presence/config synthesis, source/link semantics; external PDF/HTML golden smoke, installed offline source gate pending.
- **Portfolio appendices** shared `backends/portfolio/templates/{beginning,ext_appendix,inst_appendix,csr_appendix,idl_func_appendix}.adoc.erb`, `tools/ruby-gems/udb/lib/udb/{obj/portfolio,portfolio_design}.rb` and `udb_helpers/backend_helpers.rb`; not independent deployable today but **separate retained template family** used by profile docs and portfolio-derived outputs. Python typed portfolio/extension/CSR/IDL tables + AsciiDoc partials with cross-reference oracles and same installed docs gate pending.
- **C++ hart/decode** `./do gen:cpp_hart CONFIG=rv32|rv64|rv64-vector|CFG[,CFG...] [BUILD_NAME=...] [BUILD_TYPE=debug|fast_debug|asan|release]`, build/test targets `build:cpp_hart|iss|renode_hart|softfloat_tests`, `test:cpp_hart|riscv_tests|riscv_vector_tests` (`backends/cpp_hart_gen/tasks.rake`). Dynamic regex Rake rules render `templates/*.{h,hxx,cxx}.erb` (20 files) using `lib/{gen_cpp,template_helpers,csr_template_helpers,decode_tree,constexpr_pass,control_flow_pass,written_pass}.rb` plus `idlc` passes; emit `gen/cpp_hart_gen/<build_name>_<build_type>/{include/udb/{hart_factory,db_data,enum,bitfield,libhart,...},include/udb/cfgs/<config>/{inst,inst_impl,params,hart,hart_impl,csrs,csrs_impl,csr_container,structs,func_prototypes,idl_funcs_impl}.hxx,src/{db_data,enum}.cxx,CMakeLists.txt}`, plus shared C/C++ headers/source/test symlinks. Python Stage 4 already has `DecodeGenerator`, `build_decode_tree`, `prune`, `constexpr`, `control_flow`, `written` (`doc/python-api.md:411-444`): **semantic passes migrated, ERB templates/output orchestration not**. Proposed `udb[sim] generate cpp-hart --config CFG [--config ...] --build-name ... --out DIR`, package static C/C++ and templates as resources or copy to output; no symlink back to checkout. Preserve include file layout, formatter behavior, generated model semantics, CMake integration and renode C# consumer. Installed source generation must not require clang-format/CMake/compiler/native deps/network; format in Python or optional repo-only check. Separate repository gates compile C++23, Catch2 tests, rv32/rv64/vector architectural suites, Renode build; CMake currently fetches multiple dependencies over network (`backends/cpp_hart_gen/CMakeLists.txt`), never run inside installed-generation gate. Existing `cpp/test/gen_test_bits.rb` generates random directed bit tests and must be ported/preserved for repo test authoring; don't credit tests merely because C++ sources are present.

### Documentation, schema, highlighting, site/search family contracts

- **Versioned schema MDX** `./bin/chore gen [-f] schema-docs` -> `tools/internal-gems/schema_doc_gen/bin/{schema-docs-all,schema-doc-gen}` and `lib/schema_doc_gen{,/index_generator}.rb` (`bin/chore:303-322`); from `spec/schemas/*.json` except Draft meta-schema, `$id` independently names `doc/docs/schemas/<version>/<schema>.mdx`, `<version>/_category_.json`, and `doc/docs/schemas/index.mdx`. `$defs`, refs, polymorphic variants, example formatting, anchors, frontmatter, collapsible sections and existing historical MDX docs all matter. Python `udb[docs] generate schema-docs --schemas DIR --out DIR` with packaged schemas, verbatim **byte equality of preexisting same-version tracked MDX** and immutability gate (`tools/test/regress-tests.yaml:624-655`), links/MDX Docusaurus compile, installed offline generation pending. Do not overwrite released version content without schema `$id` bump.
- **IDL language docs and highlighting** `doc/idl.adoc`, `doc/docs/idl/*.mdx`, Docusaurus site `doc/package.json`, canonical Prism `doc/src/prism/idl.js` registered by `doc/src/theme/prism-include-languages.js`, `tools/node/idl-grammar-gen/index.js` -> `tools/vscode/idl/syntaxes/idl.tmLanguage.json` (`bin/chore gen vscode-idl`), VS Code scopes/injection definitions `tools/vscode/{idl,yamlidl,adocerb,cpperb}`. Legacy CI `./bin/bundle exec asciidoctor -r idl_highlighter -a toc=left -a source-highlighter=rouge -o idl.html doc/idl.adoc` uses **first-party Ruby Rouge lexer** `tools/ruby-gems/idl_highlighter/lib/idl_highlighter.rb`; a Ruby UDB highlighter/plugin is *not* permitted by only-official-external-renderer rule. Python owns IDL syntax/highlighter source (or static grammar recognized by official renderer), while Prism/JS + TextMate client grammars remain as deployed; external Asciidoctor handles rendering. Compare representative keywords, types, symbols/IDL blocks in Prism/TextMate/rendered HTML, full Docusaurus docs build and link/navigation checks; no native Ruby highlighter in installed source gate. Some legacy editor ERB injection packages have to be adapted/retired **only after** replacement workflow, not silently removed.
- **UDB API/tool docs** `./do gen:udb:api_doc` writes `gen/udb_api_doc` via YARD+Sorbet (`tools/ruby-gems/tasks.rake:116-132`), `./do gen:tool_doc` writes Ruby YARD doc with `cfg_arch.yardopts`, `idl.yardopts` (`Rakefile:69-77`). `udb[docs] generate api-doc` from installed Python package/docstrings incl `udb`/IDL, API import and link tests; do not preserve Ruby YARD-only class names. Existing `doc/python-api.md` is API usage contract but not generated reference replacement. CLI/offline import gate pending.
- **Pages publication indexes and schema assets**: existing Python `tools/scripts/gen_schema_index.py` merges schema versions without dropping historical releases, writes `_site/schemas/index.json`; `tools/scripts/download_schema_releases.py` retrieves released historical assets and `publish_schemas.py` writes GitHub releases; `tools/scripts/gen_pages_index.py` + `pages.html.template` generate `_site/index.html` using schema index, SHA/date/URL from env (`.github/workflows/{pages,schema-release}.yml`). These scripts are *already Python*, not Stage 5 Ruby port credit, but release/Pages use Ruby `./do gen:schemas` and checkouts/network. Keep historical released-schema retrieval solely in deployment tooling; installed generation must never download or require GitHub; test canonical schema index merging and link encoding, HTML token escaping, publication immutability separately. Docusaurus `doc/package.json`, `docs-preview.yml` already use JS/Node `bin/aubr`, not UDB Ruby generation.
- **Profile extension listing** `tools/python/profile_extensions.py` already reads Python bundled resolved data by default; `./do test:profile_extensions` / `./do chore:update_golden_profile_extensions` still execute via Ruby Rake (`tools/python/tasks.rake`) against `tests/golden/profile_extensions.golden`. Stage 6 cut over wrapper and retain exact text fixture/profile filter/explicit-resolved-path behavior; no false Ruby migration credit for Python script itself.



### Additional first-party authoring/test-data generators (do not drop as unreferenced)

- `tools/scripts/fpgen_generate.rb` is a standalone UDB Ruby/Z3 floating-point stimulus generator: `fpgen_generate.rb --output PATH [--samples-per-task N] [--seed N] [--all-types]` produces directed and optionally solver-generated deterministic **JSONL** f32 vectors; no active workflow caller was found by repository search. It is still a first-party generator, so either preserve as `udb author fp-stimuli --out FILE --seed 1234 ...` using packaged Python Z3 and semantics, with record-schema/seed reproducibility and SoftFloat consumer check, or obtain an explicit maintainer scope decision before retirement. Fixture: checked-in representative seeded JSONL needed; gate pending, not satisfied by Stage 4 IDL passes.
- `tools/scripts/new-rvtest` copies `new-rvtest-{32,64}-template.S` into `tests/isa/{rv32uv,rv64uv}/<name>.S` and updates each `Makefrag` after validating name; not Ruby itself, but creates new architecture-test sources consumed by `backends/cpp_hart_gen/tasks.rake`/ISA tests. Keep this repository-authoring workflow; template substitution and both Makefrag updates require fixture/drift validation and Python CLI or stable shell wrapper only if Stage 6 claims unified authoring commands. `tools/scripts/run-rvtest` is a test runner, not output generation; preserve with Python CLI/test orchestration.
- `./bin/chore gen ruby-type-def`, `gen gem-versions` and `update gem-versions` generate Ruby/Sorbet declarations and gem metadata today (`bin/chore:329-356,498-510`, `tools/scripts/gen_gem_versions.rb`), not installed-package outputs; replacing them means Python typing/stub checks and wheel/sdist version automation, **not** porting Sorbet/Tapioca output. Retire only after all Ruby consumers and gem release jobs are gone.

### Corrections and captured consumer edge cases

- `backends/indexer/README.adoc` advertises `index-unifieddb.json`, actual task writes `index-unified.json` (`tasks.rake:7`): preserve consumed path and update README on cutover, do not silently rename.
- Manual and cfg HTML generation each use Antora; separate AsciiDoc source generation from external HTML renderer and ensure installer never performs legacy `--fetch`, submodule updates, `git archive`, or temporary git commits (`manual/tasks.rake:356-481`, `cfg_html_doc/html_gen.rake:238-250`). Supplied local chapter/asset files are allowed; never fetch during offline wheel generation.
- PRM includes a separate custom *non-ISA* tree `spec/custom/non_isa/prm_example/`, not bundled in `pyproject.toml`; expose an explicit PRM path and local external docs, and include source references without reopening a deleted checkout.
- `isa_explorer/table_builder.rb:48-83` uses sorted profile releases, highest extension versions, transitive requirements, ratification dates, hardcoded manual `isa_20240411` URLs; `--skip` is a stride (`idx % N == 0`), not “drop first N”. Preserve/populate link destination from selected manual version rather than silently changing URLs. `js_xlsx_writer.rb` hand-interpolates JS strings, requiring Python escaping and DOM data parity.
- `udb-gen/inst_table/table_builder.rb:21-69` emits opcode field positions and decode-variable `~` sign extension, `!` exclusions, `<` left shift and bit locations per RV32/RV64, sorts lines and embeds an output-dependent command header. Existing tests own both `tools/ruby-gems/udb-gen/test/{unit,integration}/fixtures/inst_table/expected.txt`. Current Python `src/udb/encoding.py` match/mask/value is insufficient to reconstruct these rows; expose semantic field descriptors rather than parsing generated text.

### Shared and apparently uninvoked template subfamilies

- `tools/ruby-gems/udb-gen/templates/common/{csr,inst,mmr}.adoc.erb` supply shared CSR/instruction/MMR renderers; `backends/common_templates/adoc/{csr,inst}.adoc.erb` are symlinks to those same files. Preserve CSR and instruction outputs in extension, manual, PRM/profile consumers without relying on checkout symlinks in a wheel. No direct invocation of `common/mmr.adoc.erb` was found in first-party Ruby/ERB text searches; inventory as **unverified/deferred MMR contract**, not permission to delete. Likewise `backends/cpp_hart_gen/templates/{libhart_renode.h,types.hxx}.erb` and `udb-gen/templates/manual/{csr,index}.adoc.erb` are present but not directly named by currently enumerated Rake output rules; determine if dynamically included or intentionally dormant before removal. Target Python shared CSR/MMR/instruction rendering and C++ static/header coverage; fixtures for MMR/indirect paths pending.
- `tools/ruby-gems/udb/lib/udb/external_documentation_renderer.rb` (not only `prm_generator.rb`) implements duplicate chapter tracking, include recursion/cycle detection, heading adjustment, missing-file warnings, image path repair, and file/asset references; its process-wide class sets must become **per-call** Python state (`external_documentation_renderer.rb:19-115,208-340`). Oracle explicit duplicate/missing/cyclic/nested includes and image paths. `tools/ruby-gems/udb_helpers/lib/udb_helpers/backend_helpers.rb` and `udb-gen/lib/udb-gen/{template_helpers,adoc_helpers}.rb` own sanitization, xrefs/anchors, WaveDrom hex/entity formatting, provenance/revision; mirror in tested presentation layer, not Ruby renderer plugin.
- `tools/ruby-gems/udb-gen/assets/img/*` are symlinks to `riscv-docs-resources` and `backends/common_templates/adoc/*` are symlinks to Ruby gem templates. Existing docs assets/partials are **not** wheel resources under `pyproject.toml`; `udb[docs]` must package real licensed resource bytes or require explicit local path, never links back to checkout/submodule at installed runtime. Asciidoctor themes/fonts from `backends/prm_pdf/pdf-theme` and `ext/docs-resources` are separately supplied only for external rendering.


### Embedded configured-prose templates (135 YAML source files)

`rg '<%' spec/{std,custom}/isa -g '*.yaml' -g '*.layout'` finds **135 source YAML files** (116 CSR, 19 instruction) whose descriptions/fields retain Ruby `<% ... %>` conditional/interpolation source after Stage 2 layout expansion; `doc/python-api.md:190-206` explicitly says layout generation preserves it for *later* configured-document rendering. Representative `spec/std/isa/csr/{sip,mideleg,stvec}.yaml` and `inst/Zicbom/cbo.flush.yaml` use `ext?(:H)`, extension-version predicates, named parameters (`MXLEN`, cache block size), conditional/elsif/unless, and formatting/bit-length expressions. Ruby `tools/ruby-gems/udb/lib/udb/cfg_arch.rb:1640-1728` creates `erb_env` and `render_erb` via Tilt/tempfile; `tools/ruby-gems/udb-gen/templates/manual/csr.adoc.erb:11,130` invokes it for CSR/field descriptions; `backends/generators/tasks.rake:12-29` invokes it for exception code names. Not resolved Stage 2/4 merely because source data is Python-readable. Proposed typed restricted configured-prose expression/conditional renderer above `ConfiguredArchitecture` with explicit interpolation input and source-aware errors; **do not execute arbitrary Ruby or preserve ERB**. Fixture matrix `_`, full RV32/RV64, H/Smaia, parameter/XLEN branches, scalar field descriptions and exception names; compare semantic rendered text and separately record confirmed Ruby defects. This is a shared upstream requirement for manual/config/PRM/extension documentation and generic C/SV encodings, with installed offline fixture gate pending.

### HTML/browser runtime and UI asset matrix

`tools/ruby-gems/udb-gen/templates/isa_explorer/{ext,inst,csr}-browser.html.erb` inlines `templates/isa_explorer/load_table.js` and points to Tabulator 6.3.1 JS/CSS on `unpkg.com`; render-page generation itself is local, but browser smoke must use pinned local/mocked assets or a separately network-permitted deployed-runtime job. Manual playbook `udb-gen/templates/manual/playbook.yml.erb:27-50` and cfg HTML playbook `backends/cfg_html_doc/html_gen.rake:116-140` refer to remote Antora UI bundle and checkout `node_modules/@asciidoctor/tabs` CSS/JS and local `templates/manual/highlight.js` / `backends/cfg_html_doc/ui/highlight.js`. All these UI files are consumers/resources requiring explicitly packaged bytes or caller-supplied local assets at installed-generation time; **generation must never fetch `unpkg`, GitLab UI, or npm**. HTML assembly in separate external jobs may use already installed Antora/official Asciidoctor. Test HTML stylesheet/script references and IDL highlighting token classes, not only page count.

## Stage 6 consumers and workflow contracts

1. **Entry points**: `do` is `mise exec ... bundle exec ... ruby -r rake` (`do:1-22`); `bin/udb-gen` is Bundler wrapper, `bin/generate` dispatches its six Ruby subcommands, `bin/regress` wraps `tools/test/regress-cli.rb`, and `bin/chore` dispatches Ruby/Bundle generation, releases and test chores. Target `udb inspect|validate|resolve|idl|generate|author` installed commands and Python repo orchestration wrappers (`./do`, `bin/generate`, `bin/regress`, `bin/chore`) if stable aliases retained; preserve stable config names/path modes, stdout/error exit codes, machine-readable results, arg list/matrix and artifact paths. Existing `udb list|show|resolve|schemas|validate-cfg|generate-layouts` are genuine Python, but **none of the wrappers above are migrated**. Deprecated `./do gen:{ext_pdf,isa_explorer_*,html_manual}` already exit with guidance (`Rakefile:279-319`); migrate their documented messages only if retaining aliases, not resurrect retired output paths.
2. **Dynamic graph/workflow**: top `Rakefile:44-50` loads *all* `backends/*/tasks.rake` + `tools/*/tasks.rake`; regex file rules in C++ hart, manual, config docs and `backends/profile/tasks.rake:17-100` create targets by config/profile release, and `Rakefile:374-404` names portfolio shortcuts. `bin/chore gen all|smoke|regress|schema-docs|profile-cfgs|cfg-headers|udb-gen|xqci|instruction-appendix|vscode-idl` generates artifacts/fixtures/CI; preserve replacements as explicit Python function graph, not static task-name grep. `tools/test/gen_regress.py` creates `.github/workflows/regress.yml` from `regress-tests.yaml` + `regress-gh-template.yaml`: edit the **sources**, regenerate workflow, compare generated YAML canonical equality; avoid editing generated workflow alone. `tools/test/check_python_install*.py` existing installed gates owned by parent; expand generator installed matrices when capabilities land (contents not inspected).
3. **Tests/CI**: `tools/test/regress-tests.yaml` PR matrix invokes Ruby unit/integration (udb, idlc, udb-gen, helpers, scripts), Sorbet, cfg header/golden, schema-doc/golden, IDL conditions/parity (temporary Ruby oracle), C++ rv32/rv64/vector, Go/C/SV, ISA/manual/cfg/PRM/profile/appendix; merge-queue builds/upload HTML/PDF, browser/workbook, resolved spec, IDL docs, API docs (`.github/workflows/regress.yml` generated from YAML). Preserve artifact names/output paths consumed by `.github/workflows/pages.yml` downloads: manual, browser, spreadsheet, profiles, instruction appendix, IDL doc, schema index and docs site. Stage 6 should replace live Ruby parity with captured fixtures then retire it once equivalent Python gates cover behavior; CI no UDB Ruby on PATH for installed/PR gate, separate external renderer job with Asciidoctor available. Python schema/layout/IDL/config tests are present but do not prove generators.
4. **Packaging/build/release**: `pyproject.toml` currently packages bundled standard ISA/schema/config and `[project.scripts] udb`, **no `docs`/`sim` extras or backend templates/fonts/static C++/manual chapters/PRM custom sources** (`pyproject.toml:24-76`, `hatch_build.py`); these must be declared package resources or mandatory explicit local input for installed generators, with wheel **and sdist** outside-checkout import/resource/output tests across platforms. `tools/ruby-gems/tasks.rake` still stages four gems; `bin/chore build udb-gem`; `.github/workflows/{release_gems,gem_bump,release_udb_deps}.yml` and `.mise.toml`, `Gemfile*`, `.default-gems`, `bin/{setup,doctor}`, `.github/actions/mise-setup/action.yml` install/cache Ruby and UDB native eqntott/espresso/must/z3. Replace gem publication with reproducible Python wheel/sdist build/version/provenance and explicit PyPI ownership/name decision (name not confirmed), retain required pure Python Z3 dependency wheel and offline install gate. Schema release/page indexing still active, not gem release. C++ generated-code test suite may use separate native CMake/toolchain/network resources; Python wheel generation may not.
5. **Quality/docs/editor**: `.pre-commit-config.yaml`, `bin/pre-commit`/`prek`, Ruff, schema validation, `bin/doctor`, documentation user commands (`AGENTS.md`, `doc/python-api.md`, docs/README, backend READMEs), VS Code extension `tools/eclipse/udb-vscode`, `doc/package.json`, Pages/preview and highlighted `doc/idl.adoc` must point to Python-supported commands and entry points. Keep Docusaurus/JS deployed runtime, external Asciidoctor toolchain, C++ compiler/Go/SV lint solely in separate consumer checks. `tools/scripts/gen_xqci.rb`, `tools/scripts/gen_gem_versions.rb`, `tools/scripts/fpgen_generate.rb`, `backends/cpp_hart_gen/cpp/test/gen_test_bits.rb`, Ruby test fixtures/coverage, Sorbet/Tapioca/YARD and first-party `.erb/.rake/.rb` need migration/retirement only after outputs and callers pass gates; `tools/vscode/cpperb/test-erb.cpp.erb` is an editor fixture, not an active generator.



### Deployed artifact routing (do not break consumers)

`.github/workflows/regress.yml:925-1120` uploads and `.github/workflows/pages.yml:32-170` downloads the following named artifacts: `resolved-spec` (`gen/resolved_spec/_` -> `_site/resolved_spec`), `udb-api` (`gen/udb_api_doc` -> `_site/htmls/udb_api_doc`), `isa-explorer-{csr,ext,inst,spreadsheet}` (`gen/isa_explorer/{browser,spreadsheet}` -> `_site/isa_explorer`), `isa-html-manual` (`gen/manual/isa/top/all/html` -> `_site/manual/html`), `cfg-html-manual` (`gen/cfg_html_doc/example_rv64_with_overlay/html` -> `_site/example_cfg/html`), `inst-appendix` (`gen/instructions_appendix/instructions_appendix.pdf` -> `_site/pdfs`), `RVI20`, `RVA20`, `RVA22`, `RVA23`, `RVB23` profile PDFs (`gen/profile/pdf/<name>ProfileRelease.pdf` -> `_site/pdfs`), `idl-doc` (`idl.html`), `docs-site` (`doc/build` -> `_site/docs-preview`), and `reuse-manifest` (SPDX). `tools/scripts/pages.html.template` links to these deployed addresses; canonical report/output compatibility must test URLs as well as generation. The Pages workflow also publishes `_site/schemas/<schema>/<version>/<schema>` and `_site/schemas/index.json` from generated/current + downloaded historical releases. JS/Docusaurus build is an independent deployed consumer, not UDB Python generator credit.

## Prerequisites and first vertical slice

**Highest-risk missing semantic APIs**: (a) fully concrete/full-config version and parameter selection incl typed macro emit, profile strict-config derivation (Ruby `CfgHeaderBase#generate_header`, `Profile#to_strict_config`; current Python `ConfiguredArchitecture` is symbolic and exposes `configuration.params` and presence, not a documented `fully_configured?`/implemented concrete versions); (b) opcode field segmentation + decode-variable location/sign extension/shift/exclusions (Ruby instruction table, C++/generic backends; Python `InstructionEncoding` exposes match/mask but **not** the full table row representation); (c) manual-volume/chapter/version/revision + bundled prose/model source and content provenance (current package excludes external `riscv-isa-manual` chapters); (d) portfolio-specific config inference and non-ISA PRM entities/external-document preprocessing; (e) shared AsciiDoc links/anchors/monospace auto-link, encoding diagrams/wavedrom, CSR field tables, formatting/IDL, escaping and deterministic metadata; (f) browser table profile-release requirements, ratification and dynamic extension prerequisites; (g) hart generation template helper parity beyond existing Stage 4 decoder passes; (h) restricted configured prose interpolation across 135 ERB-bearing source YAML files, especially CSR/field descriptions and structured exception-code names. Derive typed public APIs from `src/udb/{architecture,encoding,configuration,idl/passes}`, not templates spelunking into raw internals.

**Start with C/SV full-configuration header as one low-coupling vertical slice**: inspect `udb-gen/lib/udb-gen/cfg_header_base.rb` and `generators/cfg_{c,svh}_header/generator.rb`, `common_opts.rb`, `bin/chore:448-475`, `tests/golden/mc100-32-full-example.golden.{h,svh}`, `src/udb/{architecture,configuration,versions}.py`, `cfgs/mc100-32-full-example.yaml`; add typed fully-configured selection/define helper, two installed `udb generate` commands and fixtures. Reject generic `_` config with explicit error (legacy requires fully configured); test boolean/int/string/list params, extension version macros, stdout/file guards, C/SV compiler/lint in separate repo gate. Keep source generation toolchain-free/offline in both wheel/sdist gates. **Instruction table second**: `inst_table/table_builder.rb` and existing unit/integration `fixtures/inst_table/expected.txt` expose a missing decode-variable API, so it is not the lowest-coupling first slice despite being plain text.

**Oracle rules**: pin accepted Ruby baseline `f5a2099a` and capture oracle artifacts/fixture SHA under repository-owned `tests/` only when implementing; never execute Ruby in installed gate. Compare tracked generated YAML/headers/appendix/unchanged schema MDX byte for byte; canonical structured equality for resolved data, headers/code compare post-normalization for intentional command timestamps/path differences, semantic AsciiDoc page/section/anchor/link checks with representative golden files, workbook decoded cell semantics rather than ZIP bytes, rendered PDF text/metadata/pages with normalized nondeterministic IDs/times, HTML DOM/nav/link checks and C++/Go/C/SV compile/lint. Record reviewed deviations in `doc/python-migration-bugfixes.md`; do not adopt Ruby bugs silently. Gate each family with Python unit/fixture and wheel/sdist offline generation; full docs/cross-compiler suites once in separate CI jobs; all planned gates above **pending**.
