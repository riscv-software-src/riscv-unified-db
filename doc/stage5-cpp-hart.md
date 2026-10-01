<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Retained C++ hart source generation

`udb.cpp_hart.CppHartGenerator` renders the retained C++ hart/ISS source tree.
Generation is an offline Python operation: it does not run Ruby, native UDB
commands, Git, a compiler, a dependency installer, or a network client.
Compiling or linking the generated tree is a separate acceptance boundary.

## Python API

```python
from pathlib import Path
from udb import Configuration, Database
from udb.cpp_hart import CppHartGenerator, RuntimeResources

database = Database.bundled().resolve()
architectures = [
    database.configure(Configuration.builtin("rv32")),
    database.configure(Configuration.builtin("rv64")),
]
generator = CppHartGenerator(architectures, build_name="both")
plan = generator.plan()
plan.apply(Path("output"))
```

Use `plan.apply(Path("output"))`, or `generator.generate("output")`, to write
files; `generator.generate("output", check=True)` reports drift without writes.
The plan has deterministic paths, bytes, modes, an exclusive owner, and a
content-addressed logical input dependency. Its manifest enumerates every
individual input hash rather than hiding the database behind that dependency.

For caller-owned data, use `Database.from_path(..., schemas_path=...).resolve(
overlays=(...))` and already validated `Configuration` inputs. Runtime assets
come from the installed package by default. Alternatively,
`RuntimeResources.from_path(path)` declares a root containing
`backends/cpp_hart_gen`, the toolchain support files, native test data and license
texts. The generator does not search upward for a repository or implicitly
follow configuration overlay pointers.

## Testing entry point

Pending integration into the unified CLI:

```sh
python -m udb.cpp_hart \
  --source spec/std/isa --schemas spec/schemas \
  --runtime-root . --config cfgs/rv32-riscv-tests.yaml \
  --out gen/cpp-hart-source

python -m udb.cpp_hart \
  --config rv32,rv64 --build-name both --out generated
```

Repeat `--config` or use comma-separated selectors. Builtin `_`, `rv32` and
`rv64` inputs are packaged resources; other selectors are explicit YAML paths
or names in `--configs-directory`. `--config all` selects that declared
directory, or the three builtin inputs when no directory is supplied. Multiple
configurations require `--build-name`; duplicate names and C++ name collisions
are errors. Build types are `Debug`, `RelWithDebInfo`, `Release` and `Asan`;
legacy uppercase spellings and `FAST_DEBUG` are accepted. The build name does
not rename configuration namespaces.

## Retained files and resources

The seven shared products are `hart_factory.hxx`, `db_data.hxx`, `db_data.cxx`,
`enum.hxx`, `enum.cxx`, `bitfield.hxx` and `libhart.h`. Each configuration has
the eleven native instruction, parameter, hart, CSR/container, structure and
function declaration/implementation headers under `include/udb/cfgs/<name>`.
The otherwise unscheduled native Renode declarations are emitted as
`libhart_renode.h` as well.

Static production headers, native sources/tests, GDB/Renode assets and toolchain
support are copied verbatim from declared resources, not maintained as another
source copy. `asset_manifest.py` is a dependency-free mapping usable by isolated
wheel/sdist builders. The generated CMake file defaults `UDB_ROOT` to the
standalone output root when its toolchain support is present, while retaining
the repository fallback and honoring an explicit `UDB_ROOT`.
Its default build type follows the selected generator build type; an explicitly
configured `CMAKE_BUILD_TYPE` remains authoritative.

The manifest records configuration selections, source text when available,
resolved record snapshots, global IDL sources, implementation sources, schemas,
static assets, output hashes/modes and unavailable instruction execution
contexts. Hashes of resolved records describe the actual public API inputs;
they are not misrepresented as hashes of original YAML bytes.
Unavailable contexts include their configuration name, source record, effective
XLEN and reason, so combined trees do not conflate configuration coverage.

## Semantic boundaries

The renderer uses `ArchitectureCompiler`, ordinary typed ASTs, pruning,
reachability/register/control-flow analyses, CSR descriptors,
`InstructionFieldBuilder` and the accepted decoder pass. It supplies globally
resolved function bindings to the control-flow analysis, matching the native
analysis's contract. It does not implement another IDL evaluator.

Present empty operations remain no-ops. Missing `operation()` bodies are
recorded and retain the native explicit execution failure, rather than becoming
invented successful implementations. Shared declarations are validated across
configurations; conflicting parameter/bitfield layouts or enum ordinals require
separate output trees instead of silently choosing the first overlay.

Native full-configuration SAT selection currently admits extensions not in the
implementation list: `ConfiguredArchitecture#to_condition` adds positive
extension requirements without closed-world exclusions, and
`implemented_instructions` uses satisfiability. The Python generator follows
the accepted closed-world architecture API. Genuine raw Ruby artifacts and
their hashes are preserved; structural fixtures explicitly enumerate the
extra native instruction classes rather than weakening comparisons.

The legacy native configuration validator's schema/reference issues remain
separate from generation. Schema bytes are preserved. The generated `Config`
constructor accepts both retained `[name, version]` pairs and the public
configuration API's `{name, version}` records without altering input/output
schema versions.

Several representation-level differences from the Ruby templates are explicit:

- instruction-body XLEN selection is a compile-time branch on the instantiated
  instruction XLEN; this assumes decoded instruction objects are not reused
  after an effective-XLEN mode change;
- multi-value returns use `std::make_tuple`, so element types are deduced before
  conversion to the declared tuple return type;
- integer literals use brace initialization and are masked to their declared
  width, while native masks only negative literals;
- integral element access uses the template `at<index>()` form whenever the
  index is constant, including when the surrounding width is not statically
  known;
- dynamic array sizes use the public `Bits` alias rather than the native
  `_Bits<..., false>` spelling;
- source/destination register lists are sorted by register file and index rather
  than preserving analysis traversal order, and unknown register determination
  falls back on `IdlValueUnknown` rather than the Ruby-only exception class;
- immutable global initializers use their accepted evaluated literal values
  instead of re-rendering the original expression.

Signed decode-variable access preserves native behavior: bare decode variables
emit their unsigned accessor, while an explicit `$signed(...)` operation emits
`make_signed()`.

## Development evidence

`tests/python/capture_cpp_hart.rb` is a development-only oracle with explicit
resolver/output roots. `capture_cpp_hart_metadata.py` verifies every captured
raw output hash before extracting class and decode-field observations; it
never rewrites the raw artifacts and redacts host-specific paths in committed
metadata. Native `types.hxx` is classified as uncapturable by the standalone
oracle because its template requires a task-local `symtab` binding; no
`types.hxx` comparison is claimed. Focused tests cover retained products,
provenance, declared resources, offline generation, safe/check-only writes and
genuine native interfaces. Native C++ probes are under
`tests/python/fixtures/cpp_hart`.

Use a project-local pytest base directory:

```sh
PYTHONPATH=src:tests/python python -m pytest \
  tests/python/test_cpp_hart_emitter.py tests/python/test_cpp_hart_generator.py \
  --basetemp=gen/cpp-hart-test-state
```

The owning-lane report tracks exact gate results and pending integration
dependencies. The compiler-owning lane corrected the `constexpr` protocol
mismatch: architectural parameter `value_known` is a Boolean property, not a
method. Current source gates use that ordinary pass correction. No compatibility
shim is shipped in this subsystem.

The small full-configuration tree has genuine structural-oracle coverage,
native metadata execution, complete generated hart-header parsing, and a
compiled concrete RV32 hart probe covering reset, decode, arithmetic, signed
immediates and CSR access. The fetched-instruction probe additionally covers
the run loop, taken branches, jump/link, word stores, signed/unsigned byte
loads and software CSR read/write/set/zero-mask behavior.
A real two-configuration source tree and compiled
factory-selection probe cover independent generated namespaces. Distinct full
RV32/RV64 configurations additionally verify per-hart register/CSR widths,
RV64 high-bit arithmetic and ADDIW sign extension. Fresh generic RV32 source
generation and complete native hart-header parsing pass; present-empty selector
CSR software-read bodies retain their missing-return warnings.
Actual standard
missing-operation coverage is 22 contexts for `_`, 11 for `rv32`, and 22 for
`rv64`; no operations are attempted for those absent bodies. This is
not acceptance of every generic/overlay/multiconfiguration tree, installed
package, or ISS execution path; those boundaries
must be checked separately before registry cutover.

The packaged runtime follows the native copy rule for C/C++ headers, sources and
`cpp/test/*.{cpp,hpp,cmake}`. The accepted native Bits layer replaced generated
random tests with its handwritten property/defect corpus; the C++ hart
generator copies that retained corpus and does not regenerate Bits tests.

Standalone generated CMake configures offline against explicitly declared
cached dependency sources, and its native `hart` library builds. The verbatim
native Renode bridge currently fails its `SocModel` constraint because it lacks
the QC delay/syscall/device/synchronization methods; this is not patched during
source generation. The retained native run loops also do not increment
`HartBase::m_num_inst_exec`. The compatibility probe explicitly checks the
observed zero counter, not a repaired counter or correct large-block instruction
limit. Consequently, `run_n` requests at least as large as the basic-block limit
can loop without a decreasing instruction budget until another stop reason
occurs. Both native boundaries remain separate from generation acceptance, and
the failing Renode target is excluded from the successful `hart` build claim.
