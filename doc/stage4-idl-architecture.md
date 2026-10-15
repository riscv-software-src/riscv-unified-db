<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Architecture-bound IDL contract

Slice 16 binds the compiler to a resolved database without a Ruby process or repository
paths. Its public adapter constructs isolated symbol tables and accurate CSR/register
descriptors. A second, translation-only bootstrap supports slice 18:

```python
from udb.idl_environment import condition_symbol_table, symbol_table

bootstrap = condition_symbol_table(resolved_database)
runtime = symbol_table(configured_architecture)
```

The bootstrap uses database parameter types, builtin enums and builtin function
signatures. Parameters and implemented predicates stay symbolic; no configured
architecture queries or solver are called. It need not materialize register files,
evaluate CSR behavior, or specialize configuration-dependent globals. This prevents
condition compilation from recursing into a partly initialized architecture.

`condition_symbol_table` currently provides the database-derived `ExtensionName`,
`ExceptionCode` and `InterruptCode` enums and normal `FunctionType` signatures for
`implemented?`, `implemented_version?` and `implemented_csr?`. Its bindings are fresh
per call. These signatures are metadata, not a second AST evaluator; applying a
predicate remains symbolic. Builtin expression nodes such as `$array_includes?`
continue to use the compiler's existing semantics.

The bootstrap also registers `xlen() -> Bits<8>` as native signature-only metadata,
matching the real globals declaration while leaving its stateful body unused.
Without an execution-scope effective XLEN its value is explicitly unknown.

The genuine configuration-independent `INSTR_ENC_SIZE` declaration is registered
through ordinary declaration semantics from captured `isa/globals.isa`; its value is
not hardcoded. Other configuration-dependent globals are not visited by this bootstrap.
A synthetic database without that source does not acquire a fabricated constant.

Ordinary call semantics and resolved-source snapshots are integrated. Runtime and
register-width bootstrap construction delegate genuine global registration to the
compiler; the temporary bounds predicate evaluator has been removed. Compiler/data
failures are explicit, not hidden through exclusions or bundled-source substitution.

The runtime table loads the `.isa` entry point and included `.idl` sources, registers
types, signatures and globals in dependency order exactly once, and retains source
origins. Loading uses packaged resources or an explicitly supplied source provider.
Custom source trees and overlays must retain their IDL sources through YAML resolution;
using bundled globals silently in place of custom globals is not permitted. Synthetic
resolved databases may supply explicit IDL sources.

`ResolvedDatabase.idl_sources` selects effective entry files. The immutable
`idl_source_layers[(layer, path)]` also retains superseded originals, and
`idl_source_roots[layer]` preserves captured root provenance. The loader calls
`resolve_idl_include(owner: SourceText, filename: str) -> SourceText` to resolve
relative includes against the owner's original location, matching the Ruby compiler.
Cross-root targets must be explicitly captured; absolute includes and uncaptured
escapes are rejected. Paths are compared lexically, never reopened, so deleted
input trees remain supported. Include deduplication and cycles use `(layer, path)`
identities, not effective paths alone. Explicit synthetic providers may supply
`idl_source_layers` and `idl_source_roots` to represent the same topology; without
root provenance, relative lookup is confined to captured logical paths.
Crossing from a rooted owner to a rootless target requires explicitly supplied
target provenance; logical-path coincidence is not a physical-origin fallback.
For nonempty YAML IDL, plain and literal scalar styles are supported. Empty IDL
accepts every scalar style at its original header mark, including quoted Zcmop
no-operations. Literal offsets retain explicit indentation and decoded leading spaces.

## Adapter fidelity

CSR descriptors returned by `idl_environment`, normal `symbol_table` construction
and compiled-context clones all implement the native `CsrLike`/`CsrFieldLike`
protocol. Field existence, base predicates and `reset_value` are properties;
access semantics use `field.type(effective_xlen)`. They are not callable metadata
methods, so native reads cannot mistake false predicates or reset integers for
truthy bound methods. CSR addresses are integer properties.
Compile-time field reads query access types only at structurally applicable
possible widths. A symbolic architecture must not evaluate an RV64-only field's
`type()` at RV32; absent fields still read zero, non-RO fields remain unknown, and
a present field with no applicable width reports explicit semantic uncertainty.

The `csr_value` bitfield for an explicitly requested field sw-write body includes
all source-defined fields applicable to its structural execution XLEN, including
fields absent from the configured implementation. This matches Ruby's
`Csr#bitfield_type`/`HasFields#fields_for`, not its presence-filtered
`possible_fields_for`. Aggregate visitation still respects actual field presence;
explicit compilation does not fabricate fields or silently omit their source.

CSR and field presence include parent and own conditions. Partial configurations use
possible existence; full configurations expose definite absence. Structural RV32/RV64
base restrictions are inferred from an unpinned solver context, not merely from the
current machine width. Common-location fields accept either base; fields with separate
RV32/RV64 layouts require a valid explicit base for `location`. Width estimation follows
its separate documented unknown-base convention.
Public CSR/field compilation rejects an explicitly inapplicable structural base.
Aggregate visitation checks both parent CSR and independent field restrictions.
All compiler entry paths also validate a supplied execution XLEN against
`possible_xlens(architecture)`, not merely against the set `{32, 64}`. Symbolic
widths and actual dual-width architectures remain supported; a reset request's
supplied execution width is validated before using its machine-MXLEN reset context.

CSR maximum length follows Ruby's MXLEN/XLEN and mode-dependent rules. Dynamic field
type/reset/write/read bodies use the compiler rather than guessed strings or reset
defaults. An unsupported or unknown compile-time result is explicit.
Reset evaluation normalizes both `UNDEFINED_LEGAL` and
`UNDEFINED_LEGAL_DETERMINISTIC` identifiers to the public `"UNDEFINED_LEGAL"` result.
Unknown conditions and unrelated unknown values are not converted to reset sentinels.

The implemented-CSR callback tests the disjunction of all definitions sharing an
address, independently of document order. A missing descriptor is false, not unknown.
Extension callbacks query the requested extension/version condition: prohibiting one
version must not prohibit other permitted optional versions. Bootstrap callbacks keep
their distinct construction semantics.

Each environment/table construction owns its mutable bindings. Compiler/evaluator
clones must not mutate caller globals; shared frozen types and source metadata are safe.
No installed API depends on backend monkey patches.

## Compilation and acceptance

`udb.idl_architecture.ArchitectureCompiler(configured_architecture)` exposes:

- `compile_instruction(name, *, effective_xlen, type_check=True)`
- `compile_function(name, *, effective_xlen=None, type_check=True)`
- `compile_csr(name, behavior="sw_read()", *, effective_xlen=None, type_check=True)`
- `compile_field(csr_name, field_name, behavior, *, effective_xlen=None, type_check=True)`
- `type_check()`

Each compilation returns `CompiledIdl` with `ast`, an owned scoped `symtab`, `source`,
`effective_xlen` and `expected_return_type`. Normal function results expose their body;
generated/builtin functions expose their signature node. `return_value()` evaluates a
fresh clone through normal body semantics. `global_symbol_table` returns a fresh
global clone. Field `type()`, `reset_value()` and `sw_write(csr_value)` use their
appropriate enum, reset-width and sentinel-capable return contexts.

Field `reset_value()` is an explicit exception to execution-width specialization:
it runs at machine MXLEN, as in Ruby's reset context, not the caller's instruction
XLEN. A supplied `effective_xlen` still validates structural applicability, but
the returned reset context reports machine MXLEN (or `None` when symbolic).
Its original MXLEN parameter metadata is preserved. Aggregate checks visit each
reset once, labeled `/RV32` or `/RV64` for a pinned machine and `/MXLEN` otherwise.
Non-reset CSR and field behaviors continue to use their execution contexts.

`type_check()` visits non-absent instruction/CSR/field bodies and global functions.
It returns `ArchitectureTypeCheckResult(checked, diagnostics, unavailable=())`.
`checked` records attempted contexts, `.ok` requires no diagnostics, and
`.raise_errors()` reports type-checking failures, not coverage gaps.
`.complete` requires both `.ok` and no unavailable contexts; consumers requiring
complete semantics must check this property rather than treating `.ok` as coverage.
The existing two-positional-argument result constructor remains supported.

An applicable instruction whose optional `operation()` key is absent is explicitly
unavailable, not successfully compiled or a type error. Each immutable
`IdlUnavailable` record contains `context`, `source`, `behavior` and `reason`.
Its source names the actual record path and missing behavior (for example,
`inst/example.yaml#/operation()`), without fabricated scalar offsets. No body was
attempted, so that context is not in `checked`. Direct `compile_instruction` still
raises `DataError` for a missing operation. A present empty body is checked; a
present malformed or incorrectly typed body remains a diagnostic. Unavailability
depends on source-key absence, never on a hardcoded instruction list or unsupported
body exclusion. Constructor/global-registration failures remain explicit and must
be reported separately from later body checking.

The architecture compiler must expose typed instruction operations for an explicit
effective XLEN, CSR/field behavior bodies with their argument and expected-return
types, and global function definitions. It must expose enough compiled context for
slice 17's real-sample analysis; a bare AST without its binding environment is not enough.
Full architecture type checking visits the applicable instructions, CSR bodies and
functions for `_`, `rv32`, `rv64`, and `qc_iu`, matching the current regression matrix.

Instruction scope includes decode variables and `$encoding` at the actual encoding
width, `$pc`, XReg aliases and the effective XLEN. CSR scope includes the correct
XLEN and `csr_value` where declared. Includes preserve each file's independent source
span. YAML diagnostics restore original file lines and columns, including inherited
and overlay fields.

The public API's final spelling is documented in `doc/python-api.md` when integrated.
CI and the existing offline wheel/sdist gate import and execute the architecture,
source-mapping and value-bounds capabilities. A module-level public API still needs
installed coverage even when it is not re-exported from `udb.__init__`.
