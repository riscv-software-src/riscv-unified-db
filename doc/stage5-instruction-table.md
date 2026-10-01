<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5 instruction-table contract

## Legacy oracle

The owning sources are
`tools/ruby-gems/udb-gen/lib/udb-gen/generators/inst_table/{generator,table_builder}.rb`,
`common_opts.rb`, and `udb/lib/udb/obj/instruction.rb`. The unit fixture uses three
mock instructions, deliberately preserving supplied opcode and variable order;
the integration fixture uses the complete `_` architecture and `test_table.txt`.
Both original `expected.txt` files are frozen without rewriting semantic rows.
Native Ruby captures supplement them for stdout, named RV32/RV64 configurations,
and a fully configured configuration path.

`inst-table` accepts `-c/--cfg` (default `_`, name or YAML path) and
`-o/--out` (default stdout). File output truncates the chosen file, does not
create its parent directory, and mentions only the basename in the command
prelude. Neither configuration selection nor an absolute directory is recorded
in that prelude. Unknown arguments are errors. The Python integration spelling
is `udb generate instruction-table --config CFG [-o FILE]`; the artifact
retains the legacy prelude intentionally, so comparisons need no normalization.

## Exact rows

Each row is `NAME BASE FIXED_BITS [VARIABLE_LIST]`, followed by a newline.
`NAME` is the database instruction name, not `long_name` or assembly text.
Assembly is retained separately in the public descriptor for downstream users.
The fixed fields are contiguous runs of `0`/`1` in the instruction match,
scanned from MSB to LSB, formatted as `bits<lsb`, and joined with `|`.
Adjacent fixed groups coalesce regardless of their opcode label. Instruction
length is independent of XLEN: compressed and wider instruction matches remain
their declared length.

Variables retain source declaration order, original location spelling (integer
locations become decimal strings), sign extension `~`, excluded values
`!value!value` in source order, then nonzero left shift `<count`, and finally
`=location`. Thus actual modifier order is `~`, `!`, `<`, despite the legacy
header's illustrative ordering. Scattered bits retain extraction order; they
must not be numerically sorted. Aliases are metadata, not extra table columns.

An instruction's structural definition determines RV32/RV64 support independently
of the selected machine width. The legacy table enumerates **all** database
instructions, not implemented or possible instructions: native captures for `_`,
`rv32`, `rv64`, and a fully configured YAML path are byte-identical.
Configuration selection chooses the database/overlay context, not row filtering
or the base label of a common instruction. Equal RV32/RV64 columns produce `common`;
different columns produce `common,32` then `common,64`; structurally single-base
instructions produce `32` or `64`. Output sorts complete row strings
lexicographically, retaining separate rows next to one another.

The header, legacy URL, command line, explanatory comments, spaces, and final
newline are part of the artifact. Stdout has no `-o`; file mode includes its
basename. Only command/path provenance is eligible for explicitly declared
expected-side normalization if a future integration changes the command.
Actual semantic rows must never be normalized.

## Python boundary

The native generator consumes immutable `Instruction` records from a
`Database`/`ResolvedDatabase` or a `ConfiguredArchitecture`. Configuration
selection retains the all-instruction legacy behavior. Structural XLEN analysis
uses public unconfigured presence queries and fails on deferred queries rather
than omitting unknown instructions. It must not inspect
private configured solver state or pin both encodings to machine MXLEN.
Typed public descriptors expose opcode ranges, ordered decode variables,
widths, exclusions, sign extension, left shifts, names, assembly, and origins.
Source-aware input errors reject unsupported encoding fields and malformed
locations rather than silently skipping them.

Generation is data-only and works from the installed bundled database without
a checkout, Ruby, an external compiler/toolchain, subprocesses, or network access. Installed
wheel/sdist command integration and acceptance belong to the parent lane.
This lane owns only descriptor/table modules, focused tests and raw fixtures,
this contract, and integration suggestions under `gen/handoff`.

## Native API

```python
from udb import Database
from udb.instruction_fields import InstructionFieldBuilder, instruction_fields
from udb.instruction_table import render_instruction_table, generate_instruction_table

database = Database.bundled()
fields = instruction_fields(database, "beq")
immediate = fields.encoding(32).variables[0]
print(immediate.bits, immediate.encoded_width, immediate.width)
text = render_instruction_table(database)  # pure, no stdout side effect
generate_instruction_table(database, output="instructions.txt")
```

`InstructionFieldBuilder(source).describe(name_or_instruction)` reuses structural
analysis for batches. An `Instruction` argument must be the actual record from
the supplied source database or the builder's effective resolved database.
Equal-looking records from another database are rejected, including records
with the same name and data but different source provenance. A string argument
explicitly looks up that name in the builder's database. When a raw database is
resolved by the builder, its own raw records are accepted, but the returned
`InstructionFields.instruction` is the effective resolved record, not the raw
argument. This preserves inherited extraction semantics and their defining spans.
`InstructionFields` retains that immutable record and assembly string.
`EncodingFields` exposes `xlen`, the exact
match, length, ordered `OpcodeField` values, and ordered `DecodeField` values.
`BitRange` has inclusive `high` and `low` endpoints. Opcode offsets are the
low endpoint; extraction positions in `DecodeField.bits` are MSB-first in
the declared concatenation order, not sorted instruction positions.
`encoded_width` excludes implicit left-shift zeros; `width` includes them.

`instruction_table_rows(descriptors)` produces immutable `InstructionTableRow`
values. `render_instruction_table_rows(rows, file_name=...)` is a pure formatter
and preserves explicitly supplied field order, including the original mocked
unit fixture. The frozen dataclass constructors themselves do **not** validate
arbitrary caller-supplied ranges, widths, modifier values, tuple types, names,
or nested immutability. Hand-built descriptors and rows are trusted formatter
inputs; only builder-produced descriptors have the validation guarantees
described here. This distinction also allows the genuine legacy mocked unit
fixture's intentionally supplied opcode order and offsets to be reproduced.
`render_instruction_table(source=None, file_name=None)` loads
bundled data by default. `generate_instruction_table(source=None, output=None,
stdout=None)` validates the complete table before writing, then returns the
same text it wrote; stdout is the default and is injectable.

Legacy match encodings and per-XLEN **match** branches are supported and covered
by genuine Ruby artifact parity. None of the currently bundled instructions
uses `format`. For the schema-shaped single `format` path, public data references
provide type lengths, subtype variables, and opcode values; fixed bit runs
coalesce after placement. Variable-type references are checked for existence
and mapping shape, but are not exposed as `DecodeField` metadata and do not
supply sign-extension/shift/exclusion semantics. The current resolved variable
schema does not permit those modifiers, so schema-valid format variables lack
them, as in Ruby. Format-local variable annotations must agree with the
subtype's extraction semantics. Scattered opcode locations are rejected
explicitly, as legacy Ruby requires contiguous opcodes.

The implementation also handles per-XLEN `format` branches and explicit
subtype-variable modifiers in synthetic inputs. These are **hypothetical,
non-schema extensions**, not claims of current schema-valid legacy parity:
the current resolved format schema has no RV32/RV64 split, and Ruby reads
opcodes from top-level `format.opcodes`. Their targeted synthetic tests prove
the native behavior only; they are not genuine Ruby format artifact oracles.

For builder-produced descriptors, malformed matches, locations, names, widths,
modifier types, missing references,
overlapping/unaccounted bits, and unrecognized encoding keys are explicit errors.
Errors include the logical document/pointer and exact captured source span when
available. Inheritance metadata (`$child_of`, `$parent_of`) and opcode display
names are recognized provenance/presentation fields rather than extraction
semantics. Instruction names must remain unambiguous single row tokens: whitespace,
nonprinting/control characters, comment markers, and table syntax characters
`#=|~!<>` are rejected with the original name's source span. Valid names are not
rewritten or limited to a new ASCII identifier regex.
Negative, out-of-width, or duplicate excluded values remain unchanged, as in Ruby;
they are not truncated, deduplicated, sorted, or silently dropped. No extraction
bits or exclusions are inferred from the private overlap/solver machinery.
This exclusion policy deliberately differs from `udb.encoding`'s overlap parser,
which rejects negative/out-of-width exclusions and omits exclusions with
nonzero implicit low bits in left-shifted variables.
The table is a faithful textual representation, not an overlap-analysis result;
the two APIs can therefore differ on such records. Their parsers have not been
unified or otherwise changed by this generator port.

Custom source databases needing parameter schema references require their
explicit schema directory, just like other configured architecture queries:
`Database.from_path("my-isa", schemas_path="my-schemas").resolve()`.
