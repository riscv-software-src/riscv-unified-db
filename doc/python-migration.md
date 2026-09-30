# Python migration plan

## Status

| Work | Status |
| --- | --- |
| Migration planning and repository inventory | Complete |
| Stage 1: packaged source database and raw API | Complete locally; CI pending |
| Stage 2a: YAML inheritance and overlays | Complete locally; CI pending |
| Stage 2b: schema validation | Complete locally; CI pending |
| Stage 2c: layout authoring, serialization, and remaining resolution work | Complete locally; CI pending |
| Stage 3: versions, configurations, conditions, and solving | Complete locally; CI pending |
| Stage 4: IDL compiler and semantic passes | In progress: syntax (branch 13) complete locally |
| Stage 5: generators, templates, and document rendering | Pending |
| Stage 6: CLI, build, release, and Ruby removal | Pending |

The standard database is bundled in the `udb` Python distribution. Every
current generator and supported workflow remains in scope. Generators may use
documented extras such as `udb[docs]` or `udb[sim]` so that the default install
does not carry every rendering and code-generation dependency. If a particular
generator proves impractical to preserve, that is a scope decision for
maintainers rather than an implicit consequence of the migration.

## Target state

The finished project has one supported Python package and command-line entry
point installable with `pip install udb`. The default installation can load the
bundled standard database, apply a caller-supplied custom ISA overlay, resolve
a configuration, and compile and analyze IDL. Documented extras provide every
supported generator. It does not need a repository checkout, Ruby, Bundler,
Rake, ERB, a network connection at runtime, or system-level installation of
native libraries and executables used by UDB itself.

The migration preserves externally observable semantics and artifacts where
they are intentional. It does not preserve Ruby class layouts, method names,
mutable object behavior, exception hierarchies, or incidental output ordering.
Python interfaces should be designed as maintainable Python APIs with type
annotations, explicit inputs, immutable values where practical, useful errors,
and no process-wide mutable state.

Confirmed Ruby defects corrected during the port are recorded in the running
[bug-fix log](python-migration-bugfixes.md), with regression tests. The migration
does not preserve a bug merely to obtain an exact match with Ruby.

## Review stack

Each branch contains one logical capability and builds on the preceding branch.
These are local branches until publication of the PR stack.

| Branch | Base | Capability |
| --- | --- | --- |
| `migration/python-01-package` | `main` | Installable standard database and raw API |
| `migration/python-02-resolution` | `migration/python-01-package` | Inheritance, overlays, and profile-report cutover |
| `migration/python-03-schema` | `migration/python-02-resolution` | Offline schema validation |
| `migration/python-04-serialization` | `migration/python-03-schema` | Deterministic resolved data and schema publication |
| `migration/python-05-layout` | `migration/python-04-serialization` | Python layout authoring and publication fixes |
| `migration/python-06-source-maps` | `migration/python-05-layout` | Source provenance, lazy references, and combined installed-package gate |
| `migration/python-07-versions` | `migration/python-06-source-maps` | Immutable RISC-V versions and release requirements |
| `migration/python-08-configurations` | `migration/python-07-versions` | Immutable configurations and bundled generic configurations |
| `migration/python-09-domains` | `migration/python-08-configurations` | Offline JSON Schema parameter domains and combined foundation gates |
| `migration/python-10-conditions` | `migration/python-09-domains` | Condition parsing, normalization, concrete evaluation, and Z3 condition solving |
| `migration/python-11-configured-queries` | `migration/python-10-conditions` | Data-only configured architecture queries, overlap checks, and solver integration |
| `migration/python-12-stage3-gates` | `migration/python-11-configured-queries` | Stage 3 integration and installed offline package acceptance gates |
| `migration/python-13-idl-syntax` | `migration/python-12-stage3-gates` | Pure-Python IDL parser and syntax tree with full-database Ruby parity |

The migration is organized by capabilities that can be integrated and tested,
not by the current gem boundaries. The Ruby code remains the behavioral oracle
during the transition. Each completed capability is switched to Python once it
passes its acceptance gate; a long-lived Python facade that calls Ruby is not a
completion state.

## Current migration surface

The following inventory counts tracked first-party files and physical lines at
the time this plan was written. It excludes `ext/`, `gen/`, dependency trees,
and coverage output. The counts describe migration size, not estimated effort.

| Source | Files | Physical lines | Migration relevance |
| --- | ---: | ---: | --- |
| Ruby (`.rb`) | 163 | 75,409 | Database, object model, logic, IDL, generators, tests, and support code |
| Rake | 16 | 3,241 | Resolution, generation, testing, packaging, and documentation orchestration |
| ERB | 63 | 6,668 | C/C++/SystemVerilog, HTML, AsciiDoc, YAML, and document templates |
| Treetop grammar | 1 | 652 | Current IDL parser grammar |
| Layout sources | 31 | 2,990 | Source-data expansion driven by Ruby/ERB conventions |
| Python | 16 | 4,761 | Existing generators and repository scripts; not yet a complete library |
| JavaScript | 8 | 7,633 | Explorer/indexing and editor/documentation support |
| Shell and `bin/` scripts | 56 | 4,628 | Developer and CI entry points |

The Ruby-controlled migration surface is therefore 274 files and 88,960
physical lines when Ruby, Rake, ERB, Treetop, and layouts are counted together.
The largest implementation areas are `idlc` (about 30,000 production and 4,600
test lines), `udb` (about 25,400 production and 8,300 test lines), and the
repository backends (about 13,700 production lines).

This physical-line count includes generated parser code derived from the
Treetop grammar. That code measures the current maintenance and test surface,
but it will be regenerated or replaced by the Python parser rather than ported
line by line.

The packaged-data design must account for 2,306 tracked YAML files under
`spec/std/isa`, 31 layout files, schemas, and any other standard source files
needed to interpret them. All currently generated standard YAML files are
tracked, so Stage 1 can package and read the source database without executing
layouts at package build time. Layout execution is still required later for
repository authoring and regeneration.

The inventory should be regenerated when large chunks land. A useful counting
rule is `git ls-files` grouped by extension, excluding `ext/`, `gen/`, coverage
directories, and dependency trees. Generated output and third-party submodules
must not be credited as migrated first-party code.

## Cross-cutting design rules

### Package and data boundaries

Use a conventional `src/udb/` package with importable resources. Access bundled
data through `importlib.resources`, not paths relative to the source checkout.
Keep these concepts separate in the public API:

- a source database containing raw, immutable YAML records;
- a resolved database after inheritance, defaults, schema handling, layouts,
  and overlays, with typed relationships for data `$ref` links;
- a configured architecture after version, requirement, parameter, and
  presence constraints are applied;
- compiled IDL and generator-facing semantic models.

That separation prevents a raw record containing `$inherits` from being
mistaken for a resolved architecture object. It also lets callers use the
packaged database without paying the cost of schema resolution, solving, or IDL
compilation.

The API should accept explicit resource providers or filesystem roots for
tests and custom data. The default standard-data provider comes from the wheel.
At the resolved layer, a custom ISA path is an overlay input and must not
silently replace schemas or the standard database. The Stage 1 raw API may open
a custom tree by itself, but does not call that operation an overlay.

### Compatibility contract

Before porting a capability, identify its semantic contract from fixtures,
schemas, current tests, and representative generated artifacts. Add differential
tests that run Ruby and Python on the same inputs while Ruby is still present.
Compare structured results after canonicalization where ordering, whitespace,
timestamps, absolute paths, or generator banners are incidental. Keep exact
golden comparisons where bytes are part of a downstream interface.

Compatibility means, as applicable:

- the same records, inheritance results, defaults, overlays, and provenance;
- the same accepted and rejected version requirements and configurations;
- equivalent satisfiability, implication, and parameter-domain results;
- the same IDL parse, typing, constant-evaluation, and reachability behavior;
- semantically equivalent generated source and documents;
- diagnostics that identify the source file, field or IDL span, and reason.

Document intentional semantic corrections as explicit migration decisions with
focused tests. Do not reproduce a Ruby bug merely to make an unreviewed golden
file pass.

### Dependencies and offline installation

The default package must not download tools or libraries at install or runtime.
Python dependencies must be available as wheels for the supported platform
matrix. The primary `udb` wheel should remain pure Python unless a demonstrated
constraint requires otherwise.

Z3, Espresso, `eqntott`, and `must` need an explicit disposition before their
callers are cut over. Prefer a maintained wheel dependency or a Python
implementation with the required semantics. If a native helper must remain,
publish and test a platform wheel or a narrowly scoped companion distribution;
do not require users to install a compiler, `make`, a shared library, or an OS
package. Do not reproduce the current install-time and first-use downloads.

Compilers and linters used only to validate generated C++, Go, C, or
SystemVerilog in project CI are not runtime dependencies of `udb`. Emitting
those sources from an installed generator must not require such a compiler;
downstream users may use their own toolchain to compile the result.

Every release candidate must be tested from built artifacts in a clean
environment:

1. Build the wheel and sdist.
2. Construct an offline wheelhouse containing `udb` and all dependencies.
3. Install the wheel with indexes and network access disabled.
4. Install the sdist with build isolation from the same offline wheelhouse.
5. Run import, bundled-data, resolution, solver, IDL, CLI, and representative
   generator smoke tests outside the repository checkout.
6. Repeat for every supported OS, CPU, and Python version.

An sdist test may consume dependency wheels from the offline wheelhouse. It may
not succeed only because the host already has Ruby, build tools, native
libraries, UDB caches, or repository data installed.

### Implementation and adversarial review

Deliver each stage in small vertical chunks. A chunk includes implementation,
focused tests, differential or golden evidence, public documentation, and the
CI change that makes the capability continuously enforced.

For each nontrivial chunk, use this review loop:

1. A lower-cost implementation agent receives the capability contract, files
   in scope, and exact acceptance tests.
2. The primary implementer integrates the result and runs the focused suite.
3. A fresh lower-cost adversarial-review agent receives the resulting diff and
   contract, but not the implementation rationale. It looks for omitted edge
   cases, accidental repository dependencies, mutability leaks, platform
   assumptions, semantic drift, and tests that only mirror implementation.
4. The primary implementer reproduces every material finding, fixes confirmed
   defects, and records rejected findings with evidence.
5. The stage gate runs from a clean environment. A chunk is complete only when
   its new Python path is the path exercised by CI.

Agents may accelerate implementation and review, but maintainers own API and
scope decisions. In particular, an agent cannot retire a generator or weaken a
semantic contract to close a chunk.

## Stage 1: packaged source database and raw API

### Capability

Build a useful, pure-Python `udb` package that exposes the bundled standard
source database without claiming to resolve it. This is the first independently
usable slice and establishes package layout, resource access, records, errors,
typing, CLI conventions, and release tests.

Implement:

- bundled `spec/std/isa` source data and the metadata needed to enumerate it;
- lazy, safe YAML 1.2 loading with no arbitrary object construction;
- generic immutable records that retain kind, name, source path, and raw data;
- deterministic per-kind enumeration and lookup;
- an explicit path for opening a standalone custom raw ISA tree;
- actionable duplicate, malformed-document, and missing-record errors;
- an `argparse`-based `udb list` and `udb show` CLI;
- wheel and sdist metadata, typed-package marker, and resource inclusion tests.

Do not create premature Python classes for every schema kind. Generic records
are enough until downstream behavior proves a stable typed abstraction. Do not
interpret `$inherits`, apply schema defaults, resolve references, execute
layouts, choose extension versions, solve conditions, compile IDL, or present a
raw database as a configured architecture.

### Acceptance criteria

- `pip install udb` from an offline wheelhouse succeeds in a clean environment
  with no Ruby or repository checkout.
- The installed wheel and installed sdist can enumerate and load all bundled
  standard YAML records through `importlib.resources`.
- YAML scalar behavior follows YAML 1.2 for values that differ from YAML 1.1,
  and unsafe tags are rejected.
- Records and nested values cannot be mutated through the public API.
- Lookups are deterministic, lazy loading is demonstrated by a test, and errors
  report the packaged or custom source location.
- Standalone custom-path behavior is covered for enumeration, duplicate names,
  malformed YAML, and missing directories. It is not described as overlay
  composition, which starts in Stage 2.
- `udb list` and `udb show` work from outside the checkout and have stable exit
  codes suitable for scripts.
- Documentation says plainly that unresolved inheritance and other raw fields
  remain in the returned data and that the API cannot replace a resolved or
  configured architecture.

## Stage 2: YAML, schema, overlay, and layout resolution

### Capability

Turn source records into a deterministic resolved database and provide a clean
authoring pipeline. This stage replaces the current YAML resolver, schema
default handling, merge behavior, provenance mapping, and Ruby/ERB layout
generation. It does not yet decide whether a configuration is satisfiable.

Implement in independently testable layers:

- source parsing with comments/source spans needed for diagnostics;
- `$inherits` evaluation with explicit cycle and missing-target errors;
- merge semantics for mappings, sequences, deletions, and overrides;
- JSON Schema loading, `$ref` resolution, validation, and default application;
- standard plus custom overlay composition with provenance retained through
  merges;
- typed, lazily navigable relationships for data `$ref` links, including cyclic
  object graphs, rather than wholesale recursive expansion;
- a resolved-database object with indexes and typed views introduced only where
  consumers need stable behavior;
- deterministic serialization for resolved configs, schemas, and architecture
  data;
- a Python-native layout mechanism and authoring command that regenerates all
  currently tracked layout-derived files without Ruby or ERB;
- a generator-authoring interface for templates, output ownership, dependency
  tracking, and atomic writes that later stages can reuse.

Choose a deliberately limited template language for data layouts. Layouts are
repository source transformation, so unrestricted evaluation of Python in
templates would replace one maintenance and security problem with another.
Generated headers must identify their source and the check mode must fail on
drift without rewriting files.

### Acceptance criteria

- A representative corpus and then the full standard database resolve to the
  same semantic values as Ruby, including nested inheritance, defaults, and
  custom overlays.
- Cycles, bad references, invalid schemas, incompatible merge shapes, and
  duplicate identities have focused negative tests with source-aware errors.
- Schema validation succeeds across all architecture files and configurations
  expected to validate today.
- Resolved output is byte-stable across repeated runs after documented
  canonicalization and does not contain checkout-specific absolute paths.
- Every one of the 31 layouts regenerates its tracked YAML output identically or
  with a reviewed, intentional normalization; a clean-tree check enforces this.
- The installed package can resolve bundled data without writing into its
  installation directory. Caches and requested output directories are explicit.
- No Stage 2 Python path shells out to Ruby, Bundler, Rake, or ERB.

## Stage 3: versions, configurations, conditions, and solving

### Capability

Build the low-level version, configuration, condition, and solving model used by
validation, IDL, and generators. These semantics belong together because
extension versions, implication rules, parameters, presence, and
satisfiability form one contract even though they are currently spread across
many Ruby classes. Queries that depend on compiled IDL complete only at the
Stage 4 integration gate.

Implement:

- RISC-V version parsing, canonicalization, ordering, compatible-version rules,
  and requirement operators;
- configuration parsing for mandatory, optional, prohibited, and
  parameterized extensions;
- the condition algebra for XLEN, extension versions, parameters, arrays, free
  terms, conjunction, disjunction, negation, and conditional requirements;
- deterministic evaluation, partial evaluation, normalization, implication,
  equivalence, satisfiability, and useful unsatisfiable explanations;
- parameter domains derived from JSON Schema, including bounds, enums, arrays,
  and referenced/all-of schemas;
- data-only configured queries for instructions, CSRs, fields, profiles,
  portfolios, manuals, and other current architecture objects, with explicit
  placeholders for queries that require compiled IDL;
- encoding and CSR conflict checks and profile/config consistency checks;
- bounded caches owned by architecture/solver instances rather than globals.

Treat the existing Ruby results and tests as the semantics oracle, but expose a
Pythonic model. Prefer small immutable expression nodes and explicit solver
contexts. Keep a simple evaluator for concrete and small finite cases so that
not every query initializes Z3. Solver-backed and finite implementations must
agree on overlapping domains.

Before completion, replace or package the current Espresso, `eqntott`, `must`,
and Z3 uses according to the dependency rules above. Optional diagnostics or
minimization features may use an extra only if the default installed package
still fulfills all normal resolution and generation workflows and the scope
change is explicitly approved.

### Acceptance criteria

- The complete current version and condition test corpus has Python equivalents
  or documented stronger replacements.
- Property tests cover ordering, requirement boundaries, De Morgan laws,
  normalization idempotence, evaluation/solver agreement, and serialization
  round trips.
- Differential tests cover `_`, `rv32`, `rv64`, and representative custom and
  partially configured architectures, including known unsatisfiable cases.
- Data-only instruction/CSR presence, extension implication, parameter values,
  profile membership, and conflict-check results match the reviewed Ruby
  baseline. IDL-dependent cases are identified and gated for Stage 4.
- Unsatisfiable configurations identify a useful conflicting subset rather
  than returning only false or a raw solver exception.
- Parallel architecture instances with different configurations do not leak
  caches, symbols, or parameter values into one another.
- All native functionality works after offline artifact installation with no
  system packages and no runtime download.

## Stage 4: IDL compiler and semantic passes

The Stage 4 design contract, including the parser decision and the slice
plan, is in [stage4-idl.md](stage4-idl.md).

### Capability

Replace the Treetop parser and the coupled Ruby AST/type system with a Python
IDL front end and semantic model. Do not assume that an external tree-sitter
change exists or will land. Parser technology is an implementation choice that
must satisfy the repository grammar and packaging constraints on its own.

Split this stage into vertical language slices, each including parsing, AST,
typing, constant evaluation, diagnostics, serialization, and applicable
passes. A practical order is literals/types and expressions; declarations and
symbol tables; functions and calls; control flow and returns; arrays, tuples,
structs, enums, and bitfields; CSR/register-file operations; includes and
source mapping; then strictness, unknown values, and full-database integration.

Implement:

- a documented grammar with precedence, comments, reserved words, and all
  accepted numeric literal forms;
- an immutable or controlled-mutation AST with stable source spans;
- symbol tables and scope rules without global compiler state;
- the full type system, qualifiers, width inference, conversions, truncation,
  unknown values, and strict-mode behavior;
- compile-time evaluation and pruning/specialization;
- AST serialization/deserialization used by resolved architecture artifacts;
- reachability, referenced-CSR, source-register, return-value, exception, and
  option-analysis passes;
- AsciiDoc/pretty-print support needed by documents and generators;
- the generator-specific analyses currently under `cpp_hart_gen`, including
  constant-expression, control-flow, written-location, and decode-tree logic;
- a syntax-highlighting definition usable by the final documentation toolchain.

Keep parsing separate from UDB object lookup. Parse syntax first, then bind and
type-check against an explicit architecture environment. This makes parser
tests small and allows tools such as editors and formatters to parse incomplete
code without constructing a full configured database.

### Acceptance criteria

- Every current IDL unit-test category has a Python test mapping: arrays, AST
  types, constraints, control flow, expressions, functions, loops, register
  files, strictness/unknowns, values, variables, pruning, reserved words, and
  type round trips.
- A checked-in corpus records accepted inputs, canonical ASTs, type results,
  evaluated values where known, and rejected-input diagnostics. Ruby and Python
  agree on that corpus except for reviewed corrections.
- Full IDL type checking passes for the smoke configuration matrix and all
  other configurations currently covered by regression tests.
- IDL-backed configured architecture queries deferred by Stage 3 now match the
  reviewed Ruby baseline and expose no placeholder state.
- Source errors from IDL embedded in YAML point back to the original YAML file
  and line/column range.
- AST serialization round trips without loss of semantic or source information
  needed by downstream generators.
- Repeated and concurrent compiler use is deterministic and isolated.
- The parser and compiler install from offline wheel/sdist artifacts without a
  generated parser tool, compiler, Ruby, or system library on the target host.

## Stage 5: generators, templates, and document rendering

### Capability

Port generators by output family on top of the stable Python semantic model.
Replace ERB with a Python template engine or direct structured generation as
appropriate. Replace Rake task graphs with ordinary Python functions and a
small explicit orchestration layer. A generator is complete only when its
installed-package entry point works outside the checkout.

Templates should contain presentation logic, not database resolution or solver
queries. Move shared formatting, links, tables, instruction encodings, CSR
fields, IDL rendering, and provenance into tested Python helpers. Prefer direct
generation for machine-readable and source-code outputs when templates obscure
escaping or type rules.

### Generator decision list

Every item below is retained unless maintainers explicitly approve a change:

All generation commands are installed through one or more documented extras;
`udb[docs]` and `udb[sim]` below illustrate the major groups. The exact grouping
is fixed when dependency evaluation is complete, without moving core
resolution, configuration, or IDL behind an extra.

| Generator or workflow | Planned Python disposition | Required comparison |
| --- | --- | --- |
| Raw/resolved architecture and resolved schemas | Core serializer and CLI commands | Canonical structured equality and schema-version behavior |
| Layout-derived architecture YAML | Stage 2 authoring command | Tracked-file equality/drift check |
| Configuration C header | Direct Python generator | Compile check plus reviewed golden output |
| Configuration SystemVerilog header | Direct Python generator | Syntax/lint check plus reviewed golden output |
| Generic C encoding header | Port existing Python generator onto public API | Header diff and consumer compile check |
| Generic SystemVerilog output | Port existing Python generator onto public API | Output diff and syntax/lint check |
| Go output | Port existing Python generator onto public API | Output diff and Go compile/test |
| Instruction table | Python structured table builder | Canonical table equality |
| ISA Explorer CSR, extension, and instruction browsers | Python data/table generation and non-ERB templates | DOM/data assertions and browser smoke tests |
| ISA Explorer XLSX workbook | Python workbook library | Sheet names, cell values/types, formulas, and links |
| Extension documentation and PDF | `udb[docs]`: Python AsciiDoc generation plus chosen renderer | Semantic AsciiDoc diff and rendered smoke/golden checks |
| ISA manual, including version/config variants | `udb[docs]`: Python generation and navigation templates | Link check, semantic content diff, and HTML smoke tests |
| Configuration HTML documentation | `udb[docs]`: consolidate with manual document pipeline | Page set, links, anchors, and content comparison |
| Processor Requirements Manual PDF | `udb[docs]`: Python document pipeline | Source-content and rendered PDF smoke/golden checks |
| Instruction appendix AsciiDoc/PDF | `udb[docs]`: Python document pipeline | Existing golden plus rendered artifact check |
| Profile documents and profile-config generation | `udb[docs]`: Python document/config pipeline | Current profile regression matrix |
| Portfolio appendices/documents | `udb[docs]`: Python document pipeline | Page/section and content comparison |
| C++ hart model and decode tree | `udb[sim]`: Python semantic passes and source templates | Generated C++ build/unit tests and RV32/RV64/vector suites |
| External documentation renderer and links | Python extension/preprocessing layer | Include/link/source mapping corpus |
| Schema documentation | Replace internal Ruby gem with Python generator | Versioned MDX equality and immutability checks |
| IDL language documentation/highlighting | Python-compatible highlighter and renderer path | HTML build and representative token classes |
| Indexer/Search ingestion | Keep JavaScript only where it is the deployed runtime; feed it Python-produced data | Index schema and query smoke tests |
| UDB API documentation | Python API documentation | Installed-package import and docs link checks |

The AsciiDoc renderer is a specific architectural decision, not a hidden Ruby
dependency. Evaluate a Python-native renderer, invoking a distributable Java
tool, or owning a limited renderer/preprocessor for the constructs UDB uses.
The selected solution must cover diagrams, PDF/HTML attributes, includes,
anchors, cross references, Rouge replacement/highlighting, themes, and current
extensions. It must satisfy offline installation and no-system-install rules.
Keeping `asciidoctor` as an undocumented Ruby subprocess does not complete this
stage.

### Acceptance criteria

- Every row in the decision list has an owner, command, fixture, comparison
  policy, and CI job; no generator disappears because its old task was deleted.
- Each generator consumes only documented Python APIs, not internal dictionaries
  or paths in a checkout.
- Machine-readable output is deterministic and source output passes the target
  language's parser, compiler, or linter where available.
- Document builds validate includes, anchors, cross references, assets, and
  navigation. PDF checks inspect metadata/content and render representative
  pages rather than relying only on file existence.
- The C++ hart generator passes its generated-code unit tests and architecture
  test suites for the configurations currently exercised in CI.
- All generator CLIs run from offline-installed wheels with their documented
  extras outside the checkout. Core resolution, configuration, and IDL work
  with the default install.
- No generator, template, documentation renderer, or highlighter invokes Ruby,
  Bundler, Rake, ERB, or a downloaded-at-runtime helper.

## Stage 6: CLI, build, release, and Ruby removal

### Capability

Make Python the only supported implementation and remove transitional
infrastructure. Consolidate commands behind a coherent `udb` CLI while keeping
small repository wrappers only where they add stable developer ergonomics.

Implement and cut over:

- command groups for inspect, validate, resolve, IDL, generate, and repository
  authoring operations, with documented exit codes and machine-readable output
  where automation needs it;
- Python task orchestration for current `./do`, `bin/generate`, `bin/udb-gen`,
  schema, documentation, test, and generation workflows;
- pytest-based unit/integration suites and regression definitions that invoke
  installed Python entry points;
- type checking, Ruff, packaging validation, license checks, and generated-file
  drift checks;
- wheel/sdist release preparation, versioning, provenance, supported-platform
  matrices, and an explicit package-index name/ownership decision before any
  publication;
- contributor setup and documentation that install no Ruby toolchain;
- removal of gem release workflows, Gemfiles/lockfiles, Sorbet/Tapioca/YARD,
  Ruby coverage jobs, Rakefiles, gem sources, Treetop, ERB templates, and layout
  runtime requirements after their consumers have passed earlier gates.

Delete compatibility shims after all in-repository consumers have migrated.
Before deletion, use repository-wide searches plus CI tracing to find dynamic
task names, shell wrappers, documentation commands, and release jobs that may
not appear as normal imports.

### Acceptance criteria

- A clean checkout can complete setup, smoke tests, schema validation, config
  resolution, IDL type checking, and representative generation using Python
  tooling only.
- The full regression suite passes with Ruby absent from `PATH` and with no
  Ruby/Bundler/Rake environment variables or caches.
- Offline wheel and sdist installation gates pass on every supported platform.
- `pip install udb` provides bundled standard data and all documented default
  commands; installed-package tests never fall back to checkout files.
- Repository searches find no first-party `.rb`, `.rake`, `.erb`, Treetop, gem
  metadata, or executable Ruby shebangs, except intentionally retained
  historical artifacts explicitly approved by maintainers.
- Generated source and documents contain no requirement for Ruby or ERB.
- CI and release workflows contain no gem publication, Ruby setup, Sorbet,
  Bundler, Rake, or Ruby Asciidoctor steps.
- User and contributor documentation describes only the Python architecture
  and current commands.

## Integration order and stage gates

Stages are ordered by dependency, but work inside adjacent stages can overlap
behind private modules. Public claims and removal follow the gates:

1. Stage 1 may be prepared as a raw-data release while Ruby continues to
   provide all resolved/configured behavior. Publication waits for an explicit
   package-index name and ownership decision.
2. Stage 2 becomes the source of resolved data only after full-database and
   layout differential tests pass.
3. Stage 3 becomes the low-level and data-only architecture API used by CI
   checks before IDL and generators are moved onto it.
4. Stage 4 must pass full configuration type checking before semantic
   generators, especially the C++ hart, switch to Python IDL nodes.
5. Stage 5 ports low-coupling structured generators first, then documents, then
   the C++ hart and other consumers of advanced IDL analysis. The decision list
   remains the completion checklist.
6. Stage 6 removes Ruby only after every earlier acceptance gate runs through
   installed Python artifacts.

At each gate, record the Python command replacing the old command, the tests
that establish parity, known intentional differences, and the remaining Ruby
callers. A temporary dual-run mode is useful for CI evidence, but the default
path should switch promptly after a gate so that the Python implementation gets
real use rather than drifting beside Ruby.

## Definition of complete

The migration is complete when a user can install `udb` and its documented
generator extras with pip in an offline, clean environment and use the bundled
standard data to perform every supported resolution, configuration, IDL,
validation, and generation workflow; a repository contributor can regenerate
and test all tracked sources; all generator decisions above are closed; and
neither workflow requires Ruby, gem artifacts, Rake, ERB, runtime downloads, or
system-installed native dependencies used by UDB itself.

## Progress log

### 2026-09-29: plan and Stage 1 review

- Completed the repository inventory and migration plan.
- Built the Stage 1 wheel and sdist successfully with
  `python -m build --no-isolation --wheel --sdist`.
- Passed 23 Stage 1 Python tests with `pytest -q tests/python`.
- The registered `./bin/regress -n regress-python-unit` job passed, and the
  migrated profile report passed its existing Ruby-orchestrated golden check.
- Passed Ruff on the Stage 1 package, tests, build hook, and migrated Python
  script, and passed `git diff --check`.
- Adversarial checks found and drove fixes for editable-install resource
  lookup, relative source paths after a working-directory change, defensive
  record immutability, recursive-alias diagnostics, invalid UTF-8 diagnostics,
  referenced prose and license attribution in artifacts, and the misleading
  raw `Architecture` alias.
- Clean offline installs of both the wheel and sdist passed in separate fresh
  environments using `uv pip install --offline`. The sdist used build isolation
  with cached build requirements; CI also builds an explicit offline wheelhouse.
  From `/tmp`, with `PATH` restricted to each virtual
  environment and Ruby and Git unavailable, both installations loaded all
  2,306 raw YAML records and ran the CLI. Only `udb` and its runtime YAML
  dependency were installed for the runtime check.
- The final Stage 1 CI jobs cover Python 3.12 and 3.14; Python 3.14.7 passed
  locally and remote CI remains pending. The full repository regression suite
  was not run locally because it includes the larger LLVM, C++, and document
  suites.
- YAML formatting and REUSE checks passed. The installed Prettier cannot
  infer a TOML parser; `pyproject.toml` was validated by the successful lock,
  build, and installation checks. REUSE ran without multiprocessing because
  the local sandbox does not permit its worker socket.
- Stage 1 is complete against its local acceptance gate. It is a raw
  source-data capability and does not replace Ruby resolution, configuration,
  IDL, or generation. The next implementation chunk is Stage 2a: inheritance,
  merge, and schema-default semantics with Ruby parity tests, before layout
  authoring is ported.

### 2026-09-29: Stage 2a resolution and first consumer cutover

- Added in-memory inheritance resolution, ordered overlays, immutable resolved
  records, and CLI inspection through `--resolved` and `--overlay`.
- Switched the default profile report to bundled Python resolution. Its Rake
  wrappers no longer generate a resolved architecture before running it, and
  the existing profile-output golden remains unchanged.
- Passed all 63 Python tests with `UDB_TEST_RUBY=1`, including the live Ruby
  comparison across every standard YAML record. The comparison asserts 12
  specific corrected backlinks; other semantic content matches.
- Recorded eight confirmed Ruby defects and their regression tests in
  [the running bug-fix log](python-migration-bugfixes.md).
- Wheel/source-archive tests exercise resolution from packaged resources;
  Python-only CI checks installed resolution and a separate transitional CI
  job enforces the Ruby differential comparison.
- Schema defaults are annotations, not values inserted by this resolver.
  Stage 2b adds explicit schema validation; layout generation, serialization,
  source spans, and the remaining Stage 2 authoring workflow are still pending.

### 2026-09-29: Stage 2b offline schema validation

- Added an instance-scoped Draft 7 schema store, explicit validation through
  `resolve(validate=True)` and `ResolvedDatabase.validate()`, and CLI options
  for validation and a custom schema directory.
- Validation resolves only registered local schemas, checks schema versions,
  preserves input records, and never inserts defaults. The in-memory record
  retains its original `$schema`; `SchemaStore.versioned_uri()` provides
  version stamping for the later serializer. Ruby's on-disk URI rewrite is
  therefore deferred with serialization rather than copied into the query API.
- Passed all 92 Python tests with the live Ruby differential enabled. All
  2,306 resolved standard documents pass schema validation. Ruff, formatting,
  and diff checks passed.
- Fresh wheel and isolated-sdist installations passed offline after caching
  the declared dependencies. Both installed copies resolved and validated all
  standard records and exercised the CLI from outside the checkout with Ruby
  and Git absent from `PATH`.
- Added the ninth confirmed Ruby defect to the running log: the repository's
  pinned JSON library silently merges distinct YAML keys that stringify to
  the same JSON name. Python rejects those ambiguous inputs.
- Full repository regression and remote platform CI remain pending. The next
  Stage 2 chunk covers deterministic resolved output, provenance/source spans,
  and replacing Ruby layout generation; configurations and IDL remain later
  stages.

### 2026-09-29: Stage 2c deterministic serialization

- Added canonical YAML and JSON encoders plus atomic writers for generic
  configuration mappings, resolved architecture trees, and publishable schemas.
- Resolved trees retain relative document paths and inheritance provenance,
  version-stamp `$schema` in emitted copies, and omit implicit checkout paths.
  Absolute `$source` values are rejected with a logical document and JSON
  Pointer diagnostic.
- Schema publication preserves the Ruby path and public `$id` contract while
  producing byte-identical JSON for the current schema versions. The existing
  `./do gen:schemas` entry point and schema-version CI check now invoke the
  Python `udb schemas` command; `udb resolve` exposes resolved trees without
  Ruby or repository-relative execution.
- Fine-grained YAML source spans and provenance propagation through overlays and
  inheritance were the next integration step, completed in the Stage 2c follow-up
  below without changing resolved semantic values or embedding absolute paths.

### 2026-09-29: Stage 2c authoring and provenance

- Converted all 31 layouts to restricted Python expressions and explicit
  generation recipes. `udb generate-layouts --root . [--check]` replaces ERB
  expansion, and the existing `./do gen:arch` wrapper delegates to it. All 532
  tracked YAML outputs retain their exact bytes. `AuthoringPlan` exposes output
  ownership, dependencies, drift checking, and individual atomic replacements.
- Integrated immutable source maps, YAML comments and scalar styles, provenance
  through overlays and inheritance, source-aware schema errors, duplicate
  identity checks, and lazy data-reference navigation. Embedded parameter
  schema references remain distinct from data links; cycles in data links do
  not cause recursive expansion.
- Independent review reproduced and corrected Python defects in quoted layout
  delimiters, invalid template UTF-8 diagnostics, schema publication preflight,
  source entries surviving YAML overrides, malformed reference diagnostics, and
  the source spans of multiple inheritance backlinks. Output paths are checked
  again before replacement to catch concurrent symlink changes; authoring still
  assumes callers control the output tree, rather than promising transactions
  against hostile concurrent filesystem mutation.
- Rejected a suggested error for literal closing `}}` delimiters: the PMP layout
  contains valid IDL replication syntax such as `{PMP_GRANULARITY-3{1'b1}}`.
  A regression preserves that syntax, and all generated outputs remain equal.
- The installed-package CI gate now checks every resolved value's source span,
  all 59 data references and 3 schema references, deterministic architecture and
  schema serialization, and every bundled layout output. It runs for both wheel
  and isolated-sdist installations outside the checkout with Ruby and Git absent
  from `PATH`.
- Both artifact installations passed locally on Linux AArch64 / Python 3.14.7,
  including all 2,306 records and 73,010 source spans. Installation used an
  explicit dependency wheelhouse with network, indexes, and the package cache
  disabled; the source archive built in isolation. The runtime environments
  contained only UDB and its six runtime dependencies.
- The combined registered Python regression passed **167 tests** with
  `UDB_TEST_RUBY=1`, including the live Ruby comparison across every standard
  document and byte-for-byte comparison of all published schemas. Independent
  adversarial review has no remaining material findings. The nine confirmed
  Ruby corrections remain recorded in the bug-fix log.
- `./do gen:arch gen:schemas`, the registered layout drift and profile-report
  regressions, Ruff, formatting, and diff checks passed. The generated workflow
  was regenerated from `tools/test/regress-gh-template.yaml` and the regression
  definitions. Full repository `./bin/regress --all` and remote platform CI remain
  pending; the full suite includes later-stage C++, LLVM, and document workflows.

Remaining Ruby callers are the configured architecture/IDL resolver used by
`./do gen:resolved_arch`, Ruby object-model consumers, and later-stage generators
and document renderers. Profile reporting, schema publication, and layout
generation use Python by default. No generator has been removed. Schema defaults
remain annotations, matching the confirmed resolver policy; configuration
defaulting and satisfiability belong to Stage 3. The next capability is versions,
configurations, conditions, and solving, followed by IDL and generator cutovers.

### 2026-09-29: Stage 3 foundations

- Added immutable RISC-V versions, requirements, release metadata, and extension
  version queries. `ext_schema.json` advances to `v0.2` for documented breaking
  releases; `schema_defs.json` advances to `v0.3` for the supported requirement
  grammar and corrected compatibility documentation.
- Added immutable configuration parsing, including the three bundled generic
  configurations, mandatory/optional/prohibited selections, full exact versions,
  and necessary machine-width inference. The retained Ruby profile-config
  generator now emits valid string descriptions, and all ten profile outputs
  were regenerated. Live parsing comparisons cover all 23 repository configs.
- Added typed, immutable parameter domains for all 271 standard parameter
  schemas, with local references, intersections, arrays, bounds, membership,
  and explicitly bounded complete enumeration. Domain analysis limits are
  documented in [the domain contract](stage3-domains.md).
- The initial combined foundation suite passed **250 tests** with live Ruby
  comparisons. Clean wheel and build-isolated sdist installations passed the
  expanded durable gate from outside the checkout, with indexes and the package
  cache disabled and Ruby/Git absent from `PATH` (Linux AArch64, Python 3.14.7).
  Both installations validated generic configurations and all parameter domains,
  alongside every earlier package gate. These results precede the independent
  domain review fixes and are not a Stage 3 completion claim.
- Fresh independent domain review reproduced seven additional Python defects
  beyond the initial corpus. Corrections and another review gate are in progress.
  Confirmed Ruby corrections are separately recorded as entries 10–17 in the
  running bug log; new Python defects are not counted there.
- Dedicated version, configuration, and domain differential regressions are
  generated from `tools/test/regress-tests.yaml`. The default Python unit and
  installed-package jobs exercise the new Python APIs.

### 2026-09-29: Stage 3 completion and integration gates

- Added condition AST parsing, canonical data serialization, three-valued concrete
  evaluation, partial evaluation, normalization, and Z3 condition solving in `udb.conditions`
  and `udb.solver`. Unresolved `idl()` blocks are explicitly preserved as `UnresolvedIdlCondition`
  and defer evaluation/solving proofs to Stage 4 without crashing data queries.
- Added data-only configured architecture queries in `ConfiguredArchitecture` via
  `ResolvedDatabase.configure(configuration)`. Supported queries cover extension version
  catalogs, mandatory/optional/prohibited presence, instruction/CSR/field presence, exception/interrupt
  codes, parameter values, profile membership, encoding overlaps, CSR address overlaps, and
  architecture compatibility checks. IDL-backed queries return explicit `DEFERRED` or `UNKNOWN`
  results without claiming complete IDL evaluation.
- Added dedicated CI regression definitions in `tools/test/regress-tests.yaml` for
  `regress-python-conditions-parity` and `regress-python-configured-parity`. Regenerated `.github/workflows/regress.yml`
  from `tools/test/regress-gh-template.yaml` using the generator script.
- Extended `tools/test/check_python_install.py` in the installed wheel/sdist offline gate
  to import and exercise representative condition solving and configured queries from outside
  the checkout with Ruby and Git absent from `PATH`. The bundled `rv64` configuration checks as
  `DEFERRED` because some of its extensions and parameters are gated by `idl()` conditions.
  `tests/python/test_distribution.py` now runs this same script against a wheel rebuilt from the
  sdist in a fresh virtual environment, so the CI gate cannot drift unexercised.
- Confirmed Ruby corrections remain recorded as entries 1–17 in `doc/python-migration-bugfixes.md`.
  Fresh reviews found and fixed Python-only defects: typed `ParameterTerm` equality, unconstrained
  `oneOf` sort inference, missing top-level `udb` exports for the condition and solver API,
  `solver.implies`/`solver.equivalent` returning `False` instead of raising `SolverUnknownError`
  when finite enumeration was unavailable, and incorrect assertions in the installed-package gate
  and API examples. Because these were Python implementation issues rather than Ruby divergences,
  they are explicitly not added to the Ruby bug log.
- Local validation: 340+ Python tests pass with `UDB_TEST_RUBY=1` Ruby-oracle differentials, both
  Stage 3 parity regress jobs pass, the installed wheel gate passes from `/tmp` with a restricted
  `PATH`, and `prek` hooks pass for the Stage 3 range.
- Every existing generator is preserved. Remaining Ruby callers are the configured architecture/IDL
  resolver used by `./do gen:resolved_arch`, Ruby object-model consumers, and later-stage generators
  and document renderers. Full repository `./bin/regress --all` and remote CI remain pending.
  Stage 3 is complete locally against its acceptance gate.

### 2026-09-29: Stage 4 IDL syntax

- Recorded the Stage 4 design contract in `doc/stage4-idl.md`. The compiler uses a
  hand-written pure-Python packrat PEG parser that mirrors `idl.treetop` rule for rule,
  keeping the wheel pure Python and offline. Tree-sitter remains an option for editor
  tooling only.
- Added `udb.idl` with `parse` and per-root entry points (`parse_isa`,
  `parse_function_body`, `parse_instruction_operation`, `parse_expression`,
  `parse_constraint_body`, `parse_for_loop`). It also has an immutable AST whose
  `to_h`/`from_h`/`to_idl` follow Ruby's canonical serialization, and `IdlSyntaxError`
  with line and column. The parser has no global state; the whole database parses in
  about two seconds.
- `tests/python/test_idl_parity.py` (gated by `UDB_TEST_RUBY=1`) compares every embedded
  IDL string and `isa/` file in `spec/std/isa` and `spec/custom/isa` against Ruby, with
  no differences. Offline coverage comes from:
  - a checked-in syntax corpus (`test_idl_corpus.py`);
  - parser unit tests;
  - an independently written black-box grammar suite (`test_idl_grammar_edges.py`,
    263 Ruby-generated cases covering acceptance, rejection line/column, and `to_idl`
    round trips).
- Added the `regress-python-idl-syntax-parity` CI job. The installed-package gate now
  parses every bundled `isa/` file from the installed wheel. That gate found a
  Python 3.12-only `dataclass(slots=True)` zero-argument `super()` failure, now fixed.
- Confirmed Ruby defects are recorded as bug-log entries 18–21: signed decimal literal
  width, two `to_idl` printing errors, and a post-increment assignment crash.
- Semantic analysis (types, symbol tables, values, type checking), passes, and closing
  the Stage 3 `idl()` deferrals remain for branches 14–18 as planned in
  `doc/stage4-idl.md`.
