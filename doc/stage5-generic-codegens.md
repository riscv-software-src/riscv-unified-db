<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5 generic C, SystemVerilog and Go generators

## Public offline APIs

```python
from udb import Configuration, Database
from udb.generators.c_encoding import generate_c_encoding
from udb.generators.sv_decode import generate_sv_decode
from udb.generators.go import generate_go

architecture = Database.bundled().resolve().configure(Configuration.builtin("rv32"))
c_header = generate_c_encoding(architecture)
sv_package = generate_sv_decode(architecture, package_name="riscv_decode_package")
go_source = generate_go(architecture)
```

C/SV's automatic exception-name path requires the shared `udb.prose` service.
The explicit typed renderer seam is also available for callers that already
have rendered rows; this is not an alternative ERB engine or a fixture-based
production resolver:

```python
from udb.generators.encoding_inputs import ExceptionRecord

rows = (ExceptionRecord(2, "Illegal instruction", "IllegalInstruction", "I"),)
c_header = generate_c_encoding(architecture, exception_records=rows)
```

An explicitly empty tuple means no cause definitions. A missing argument means
the all-code prose service, never silently no causes. `ExceptionRecord` retains
`num`, rendered `name`, original `var`, and wrapper-extension `ext`. The original
wrapper's `var` is `code.name`, so a controlled name-template mutation retains
the original template in this unused provenance field; it is never emitted into
C/SV identifiers. `name` must already be rendered. No API invokes Ruby, Git,
network operations, native formatters, or checkout discovery. Callers may supply
a raw/resolved `Database` or `ConfiguredArchitecture`; only automatic C/SV
exception rendering requires a configured source.

The generators are available through the unified installed command:

```sh
udb generate c-encoding --config rv32 -o gen/c_header/encoding.out.h
udb generate sv-decode --config rv64 -o gen/sverilog/riscv_decode_package.svh
udb generate go-encoding --config _ -o gen/go/inst.go
```

Global `--database`, `--schema-dir`, and repeatable `--overlay` select explicit resources.
Non-generic `--config` values are explicit YAML paths. If that configuration
declares `arch_overlay`, supply its resources with `--overlay`; no custom
database is discovered implicitly. Existing database resolution implements the
merge, without a second resolver.
`--exception-records` supplies a strict JSON array of the four rendered-row
fields. `--package-name` overrides the SV output basename. Without `-o`, output
is UTF-8/LF stdout; named outputs create parents. Rendering/validation completes
before replacement. The accepted header/table writer handles file errors,
UTF-8 errors, short stdout writes, and broken pipes.

## Preserved selection and compiler interfaces

- C/SV default to **include all, BOTH**, exactly like the original Rake tasks.
  Supplying `--extensions` selects the original script filter unless overridden
  by `--include-all`. Space- and comma-separated extension names work.
- Go retains **RV64** and
  `A,D,F,I,M,Q,Zba,Zbb,Zbs,S,System,V,Zicsr,Sm,H,U,Zicntr,Zihpm`.
  An explicitly empty extension list disables filtering, as in its script.
- `--arch RV32|RV64|BOTH` exposes the original loader selection for all three
  outputs. The original C script only exposed BOTH, so new C RV32/RV64 checks
  compare complete opcode/mask/address semantics with that real loader.
- Generic encodings are not restricted by configured MXLEN or interpreted
  `definedBy.xlen`; only raw `base` and declared RV32/RV64 encoding branches
  restrict the old loader. BOTH keeps RV64's unsuffixed name, adds `_rv32` for a
  different RV32 match, and collapses identical matches. Instruction descriptors
  reuse `InstructionFieldBuilder`, including inherited format extraction.
  C's literal `.rv32` suffix normalization occurs before sorting, as in the
  original script; a separate real native CLI artifact covers that ordering.
- The legacy extension filter is a name-only compatibility filter, not
  configured architectural presence. Its permissive treatment of unknown
  condition shapes, version omission, `excludedBy` instruction handling, and
  strict missing instruction versus permissive missing CSR `definedBy` policy
  remain observable. The migration does not silently substitute a solver query.
- C retains the include guard, MATCH/MASK and CSR/cause defines, all 18 common
  `INSN_FIELD_` masks, and repeated-inclusion `DECLARE_INSN/CSR/CAUSE` interfaces.
  The old loader discarded variables before field extraction; adding
  instruction-specific field macros would change that interface.
- SV retains 32-bit instruction parameters (`?` wildcard bits and compressed
  upper-half padding), 12-bit CSR and 6-bit cause parameters, alignment, and
  numeric/address ordering. Package names remain explicit output-dependent
  input. Unsupported widths/identifiers fail rather than emitting invalid SV.
  In particular, `qc_iu` includes 48/64-bit encodings and now exits nonzero
  instead of logging an error and emitting truncated 32-bit declarations.
- Go retains `package riscv`, the actual `cmd/internal/obj` import, `inst`,
  `encode(obj.As)`, assembler `A<NAME>` cases, signed 12-bit CSR encoding fields,
  nil fallback, and the `map[uint16]string` CSR table. It remains an assembler
  fragment, not a standalone assembler. Only its generated first comment changes:
  native argv/absolute paths become a deterministic package module name.
  No gofmt rewrite changes the native body.

C/SV invoke `ProseInputs.from_architecture` and
`resolve_all_exception_records(architecture.database, inputs)`. The selection
is **all extension-major codes**, even for a full configuration lacking H.
Config-available `resolved_exception_names` is not interchangeable. The native
wrapper's 37 rows collapse to 22 causes by stable numeric sorting and first-code
deduplication. Lowercase space/slash/hyphen replacement remains unchanged.
Identifier collisions, malformed records, invalid encodings, unsupported
language widths, and output errors are explicit exceptions/CLI diagnostics.

## Real oracle and consumer gates

`ruby_generic_codegen_oracle.rb` invokes the original Rake wrappers for `_`,
rv32, rv64 and MC100-32-Full. The latter's real `valid?.valid` is true with no
reasons. The witness captures the original all-extension-major name/code/ext
records, not config-selected substitutes. A controlled code-name mutation runs
through the actual Ruby ERB environment and wrapper in all four configurations.
The native C/SV scripts consume those genuine JSON rows and produce eight full
interpolated artifact oracles. Four native Go CLI outputs capture empty-filter
behavior, including BOTH suffixes.

The matrix regenerator records **48 complete native loader cases**:
four configurations × three architectures × all, filtered, empty and Go-default
filters. It retains 14 byte-distinct full library/script artifacts, with original
source and artifact SHA-256 values. Identical artifact content is stored once,
not reconstructed by the implementation. All wrapper C/SV bytes and Go bodies
are compared. The original filtered SV CLI's `list.split` exception is retained
separately; its unmodified library renderer and loader supply the valid filtered
oracles. The new CLI intentionally repairs that argument handling.

Focused tests cover the entire captured instruction/CSR maps, outputs, defaults,
error cases, and real compiler interfaces. Opt-in `UDB_TEST_GENERIC_TOOLS=1`
compiles/runs all 1,394 C declarations, 413 CSRs and 22 causes; Verilator parses
the entire SV package with every parameter referenced. Go compiles and links
against the installed toolchain's **actual** `cmd/internal/obj` archive using
the compiler's importcfg interface, and executes every 1,236 default case and
165 CSR entries. Only the intentionally caller-owned opcode enumeration is
supplied. No imports are rewritten, no toolchain is copied, and no dependency
symlinks or shared GOROOT writes are used. Plain external `go test` correctly
rejects this internal assembler import; that real failure motivated the ABI
consumer harness rather than a fake obj implementation.

The eight prose-provider gates use the in-tree `udb.prose` package and fail if
it is unavailable; absent-provider skips are not exception-resolution parity.
Installed wheel/sdist, unified CLI, wrapper retirement, registry/workflow
regeneration, and publication are covered by this lane's integration gate. No
original Ruby source is removed by this lane.
