<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 4 IDL compiler design

This is the design contract for the Python IDL front end and semantic model in `udb.idl`. The
Ruby `idlc` gem stays in place as the behavioral oracle until each Stage 4 gate passes.

## Parser

The parser is a hand-written, pure-Python packrat parser in the `udb.idl.parser` package. Its
rules are split by grammar area into mixin classes that combine into one parser class. It implements the parsing expression grammar in
`tools/ruby-gems/idlc/lib/idlc/idl.treetop` rule for rule. Each Treetop rule becomes a method with
the same name, and each keeps the same ordered alternatives, repetition, and `&`/`!` lookahead.
Results are memoized by rule and input position. A provably equivalent fast path is allowed only
when differential tests over the full corpus cover it.

The design follows from these constraints and alternatives:

- Treetop is a PEG, and IDL relies on PEG semantics. Examples include ordered choice (`rval` must
  come last), negative lookahead in integer literals and `&`/`|`, and the `template_safe_*`
  expression variants that exclude `>` inside `Bits<...>`. A PEG implementation keeps the language
  unchanged.
- A context-free generator such as Lark LALR cannot express ordered choice or lookahead without
  rewriting the grammar. Lark Earley is ambiguous here and slow.
- pyparsing, TatSu, Parsimonious, and Arpeggio add runtime dependencies and still require
  grammar translation. A generated parser checked in from pegen or TatSu would add a generator to
  the contributor workflow and, for TatSu, a runtime library.
- Tree-sitter parses quickly and supports editors well, but each grammar compiles to C. UDB would
  have to publish its own platform wheels, while the primary wheel is meant to stay pure Python.
  Tree-sitter's LR conflict resolution also differs from PEG ordered choice and lookahead, which
  risks parity drift across the database. It still produces only a concrete tree, so Python
  lowering to the Ruby-compatible AST would still be needed. The open tree-sitter grammar in
  riscv/riscv-unified-db#1987 is not assumed to land.

The hand-written parser needs no runtime dependencies, installs from a pure wheel or sdist with no
tools, and keeps a one-to-one audit trail back to the grammar. The module docstring is the
authoritative grammar reference; it lists precedence levels, literal forms, comments, and reserved
words.

Editor support and syntax highlighting are separate from compilation. A tree-sitter or TextMate
grammar may serve that purpose later. It would be checked against the same corpus and would not
become a runtime dependency of the compiler. If parse throughput becomes a bottleneck, a measured
optimization or a separately packaged accelerator can be considered then.

Supported entry points match the Treetop roots used by UDB: `isa`, `function_body`,
`instruction_operation`, `expression`, `constraint_body`, and `for_loop`. On failure, the parser
raises `IdlSyntaxError` with the furthest failure offset, line and column, and the expected
terminals there. The message text need not match Treetop's.

## Syntax tree

`udb.idl.ast` defines one Python class for each Ruby `*Ast` class used by the language. Classes
keep the Ruby names without the `Ast` suffix only where the result is unambiguous; each class
declares the Ruby `to_h` `kind` string. Parsing constructs AST nodes directly and applies the same
lowering as Ruby `to_ast`: folding left-associative binary chains, specializing `$` builtins, and
producing `ParseTimeDetectedTypeError` nodes. The AST never holds a concrete syntax tree.

Each node stores its children as a tuple, its parent, and a half-open `(start, end)` interval
into an `IdlSource`. `IdlSource` owns the text, logical origin, first line, and optional mapping to
a YAML document and scalar span. Construction sets parent links, and `parse` relinks the final
tree because packrat memoization shares children with discarded speculative parents. The tree is
then frozen: public attributes cannot be reassigned. Semantic memoization uses private per-node caches owned by
the tree, and each configured architecture owns its own trees. The Ruby process-wide parse cache is
not reproduced. A compiler may keep a bounded cache of source text to AST, which must build a fresh
tree for each consumer that memoizes semantic state.

`to_h()` and `from_h()` produce and accept the Ruby serialization, including `kind`, field names,
and `source` offsets. That makes the Ruby `to_h` output the differential oracle for parsing and
lowering. `to_idl()` produces valid IDL that reparses to an equivalent tree.

## Module layout

Modules stay under about 1,000 lines. The parser is split by grammar area, and `udb.idl.ast`
becomes a package split by node family once slice 14 lands. Later slices add their semantics and
passes in separate modules, which also lets slices proceed in parallel. Package `__init__` modules
re-export the public API, so imports do not depend on the layout.

## Semantics

Semantic methods live on the node classes and take an explicit `SymbolTable`. They mirror Ruby:
`type_check(symtab, strict=...)`, `type(symtab)`, `value(symtab)`, `values(symtab)`,
`execute(symtab)`, `return_type`, `return_value(s)`, `const_eval(symtab)`, `prune(symtab)`, and
the documentation generators. Mirroring the Ruby method structure keeps a large, subtle port
auditable node by node. Passes that span the whole tree, such as reachability or register
discovery, are separate functions in `udb.idl.passes`.

The implementation must not use global compiler state:

- An unknown compile-time value raises `IdlValueUnknown`, which carries the reason and node. It
  replaces Ruby's `throw(:value_error)` and the class-level `value_error_reason`.
- Type errors raise `IdlTypeError` with the node span, and compiler defects raise
  `IdlInternalError`. Both format the Ruby-style source excerpt but never print or exit.
- Truncation warnings go through `warnings.warn` or an injected diagnostics sink.
- `Type` values are immutable. Ruby's in-place qualifier mutations such as `make_const!` become
  methods that return a new type. Every call site is reviewed for aliasing that relied on mutation.
- `SymbolTable` holds a scope stack of mutable `Var` bindings for compile-time execution.
  `deep_clone()` and `global_clone()` return independent tables, and the Ruby clone pool and
  semaphore are not reproduced.
- The architecture environment reaches the compiler through an explicit protocol: parameters,
  CSRs, register files, builtin enums, `implemented?` callbacks, MXLEN, and possible XLENs.
  `udb.idl` does not import `udb.architecture`. Stage 4 integration provides the adapter.

## Source mapping

Diagnostics for IDL embedded in YAML identify the original file, line, and column. Stage 2c source
maps provide the scalar span and style. An `IdlSource` built from a YAML scalar maps an IDL offset
back through the scalar's line offsets. This replaces Ruby's `line_file_offsets`. IDL files map
directly.

## Testing and corpus

- **Whole-database differential:** with `UDB_TEST_RUBY=1`,
  `tests/python/ruby_idl_oracle.rb` parses every IDL field in the standard and custom database, plus
  every `.idl` and `.isa` file. Python must produce identical `to_h()` output. Later slices extend
  the oracle with types, values, and diagnostics.
- **Checked-in corpus:** `tests/python/data/idl/` holds small reviewed inputs with canonical ASTs,
  types, known values, and rejected-input diagnostics. The corpus is regenerated from the oracle
  and reviewed like a golden file. The existing `tools/ruby-gems/idlc/test/idl/*.yaml` data files
  are consumed directly.
- **Unit-test mapping:** each `tools/ruby-gems/idlc/test/test_*.rb` category maps to a
  `tests/python/test_idl_*.py` module. The mapping is recorded in this file as slices land.
- **Corrections:** a confirmed Ruby defect goes in `doc/python-migration-bugfixes.md` with a
  regression test and a reviewed corpus exception. Python defects go in the migration progress
  log.

## Slices

| Branch | Capability |
| --- | --- |
| `migration/python-13-idl-syntax` | Parser, AST classes, lowering, `to_h`/`from_h`/`to_idl`, syntax diagnostics, and a whole-database parse differential |
| `migration/python-14-idl-expressions` | Types, literals, values, and expression typing and evaluation |
| `migration/python-15-idl-statements` | Symbol tables, declarations, functions and calls, control flow, aggregates, CSR and register-file operations, and includes |
| `migration/python-16-idl-architecture` | Architecture environment, YAML source mapping, and full type checking for `_`, `rv32`, `rv64`, and `qc_iu` |
| `migration/python-17-idl-passes` | Pruning, reachability, register and CSR discovery, return values, AsciiDoc and option generation, and `cpp_hart_gen` analyses |
| `migration/python-18-idl-conditions` | `idl()` conditions and closure of the Stage 3 deferred results |

Each slice updates CI and the installed-package gate for its public capability.

The Stage 3 deferrals closed by slice 18 are the 52 `idl()` conditions in the standard database:
4 extension requirements and 48 parameter requirements. Every bundled configuration, including
`_`, reports `DEFERRED` because of them. Their Ruby translation, `udb/idl/condition_to_udb.rb`,
relies on constant evaluation and for-loop execution, so it cannot start before slice 14.
