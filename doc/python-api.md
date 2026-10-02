<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# UDB Python API

`udb` is the alpha Python interface to the RISC-V Unified Database. From a checkout, install it with:

```shell
python -m pip install .
```

The distribution name is `udb`, so a future published release can be installed with
`python -m pip install udb`. This project has not yet established that the name is published or
available from the Python Package Index.

The package supports querying the bundled, raw standard ISA records and schemas. The raw data
is the unconfigured source database: it has not been resolved for an XLEN, extension set, or named
configuration. To analyze full architecture semantics or evaluation rules, pass a resolved database
and configuration to `database.resolve().configure(configuration)`. Full compilation and proof of
IDL logic are still being ported in Stage 4.

```python
from udb import Database

db = Database.bundled()
zvkg = db.extension("Zvkg")
print(zvkg.name)
print(zvkg["long_name"])

for instruction in db.instructions:
    print(instruction.name)
```

Use `Database.from_path(path, schemas_path=...)` to query another raw UDB tree. `objects(kind)`
returns all records, and `get(kind, name)` returns a single record. The convenience properties
`extensions`, `instructions`, `csrs`, and `profiles` and their singular lookup methods provide typed
views of the common record kinds. Records are immutable mappings; their source path is available as
`record.path`, and `record.to_dict()` returns a mutable copy.

Resolve YAML inheritance and apply custom overlays with `Database.resolve()`:

```python
resolved = db.resolve()
print(resolved.profile("RVI20U64")["extensions"]["I"]["presence"])

# Overlay directories use the same relative paths as the standard ISA tree.
custom = db.resolve(overlays=["my-isa-overlay"])
```

The result is an immutable `ResolvedDatabase` with the same query methods. Overlay files may be
partial records. Overlays apply in the supplied order using JSON Merge Patch: maps merge, arrays
and scalars replace, and null removes a key. Inheritance then expands `$inherits`, merges parents
in order followed by child overrides, and applies `$remove`. Null in an inheritance override
remains null. The source database and files are unchanged.

RISC-V versions and requirements are available as immutable values:

```python
from udb import Database, Version, VersionRequirement, parse_version_requirements

version = Version.parse("1.2")
assert version.canonical == "1.2.0"
assert version.to_rvi() == "1p2"

requirement = VersionRequirement.parse(">= 1.1")
assert requirement.matches(version)
assert parse_version_requirements([">= 1", "< 2"]) == (
    VersionRequirement.parse(">= 1"),
    VersionRequirement.parse("< 2"),
)

sm = Database.bundled().extension("Sm")
assert sm.version("1.12").canonical == "1.12.0"
assert requirement.matches(sm.version("1.12").version)
```

`VersionRequirement` supports `=`, `!=`, `<`, `<=`, `>`, `>=`, and `~>`. A bare version is exact
equality. The compatible operator uses an extension's ordered version metadata rather than SemVer:
versions remain compatible upward until the next release marked `breaking: true`. Pass
`versions=extension.version_set` to `matches()` for `~>`, or call
`extension.compatible_versions(version)` directly. Missing or empty requirement lists normalize to
`>= 0.0.0`. Extension version metadata, changes, and returned collections are immutable.

`resolved.documents` exposes the resolved mappings keyed by relative source path. `$child_of`
and `$parent_of` record inheritance relationships. Data `$ref` links remain references; they are
not expanded. Resolution does not apply schema defaults, choose extension versions, evaluate
configurations or conditions, or compile IDL. Use `resolved.configure(configuration)` to create a
configured architecture with solver-backed condition and presence queries.

Raw records and resolved databases also expose immutable source metadata. `record.source_at(...)`
and `resolved.source_at(document, ...)` return a `SourceSpan` for the exact field that defined the
value, including its logical source, overlay layer, one-based line and column range, scalar style,
and associated YAML comments. Inherited fields point to the parent definition and overlay values
point to the overlay definition; missing exact metadata returns `None` rather than guessing an
enclosing span. This keeps source details out of `to_dict()` and serialized semantic data.

Resolution also captures original source text. `resolved.source_text(path, layer=...)`
retrieves the defining YAML text, while `resolved.idl_sources` holds effective IDL files
and `resolved.idl_source_layers` retains their original overlay versions.
`resolved.resolve_idl_include(owner, filename)` resolves only captured sources using the
owner's layer and original location; it never reopens input directories or substitutes
bundled files. These snapshots remain usable after custom input files are removed.

Use `resolved.reference_at(document, ...)` to inspect a mapping containing `$ref`.
`DataReference.target` follows a data link lazily and returns a source-aware `ResolvedNode`, so
cyclic relationships are safe to navigate one edge at a time. `SchemaReference` identifies JSON
Schema links and is not followed through the architecture database. `resolved.references()`
enumerates both kinds without recursively expanding them.

Schema validation is explicit and uses only local or bundled Draft 7 schemas:

```python
validated = db.resolve(validate=True)
validated.validate()  # also available on an existing resolved database

custom_source = Database.from_path("my-isa", schemas_path="my-schemas")
custom_source.resolve(validate=True)
```

Validation checks every resolved document and reports its source path and failing field. Missing
schemas and schema-version mismatches are errors. It does not insert `default` values or change
records. Ambiguous YAML keys that would collapse to the same JSON key are rejected.

For lower-level validation, use `SchemaStore(db.schemas_root).validate(record, source="name.yaml")`.
`SchemaStore` is exported from `udb`; its `versioned_uri("ext_schema.json#")` method returns the
schema URI with the bundled version prefix. This is an explicit operation for consumers that
serialize records; querying and validation leave the record's original `$schema` unchanged.

Resolved data can be written as a deterministic YAML tree:

```python
resolved = Database.bundled().resolve(validate=True)
resolved.write("build/resolved-isa")
```

The output keeps source-relative document paths, writes sorted `index.yaml` and `index.json`
manifests, removes documents made stale by its previous manifest, and records versioned schema URIs
when the database has an associated schema store, without changing the in-memory database.
Repeated writes of the same semantic data are byte-identical. The serializer rejects absolute
`$source` values because checkout-specific paths would make the artifact non-portable.
Serialization errors identify the logical document and JSON Pointer containing the unsupported
value. A private ownership manifest records hashes so a later write cannot silently delete a stale
file that a user changed.

`write_config(mapping, path)` provides the same canonical YAML or JSON encoding for configuration
mappings. It does not add a `$source` field. `write_resolved_schemas(SchemaStore(...), output)`
publishes schemas beneath `<schema-name>/<version>/<schema-name>` and replaces each `$id` with its
canonical publication URL. Published schema JSON preserves source member order so existing
same-version artifacts remain byte-identical to Ruby output. `dumps_yaml()` and `dumps_json()`
expose the canonical encoders for callers that own their output stream; generic JSON sorts mapping
keys, while YAML preserves scalar key types and quotes strings that YAML 1.1 would misinterpret.

The package also installs a small command-line interface for inspecting records and validating
configurations:

```shell
udb list extension
udb show extension Zvkg
udb --database spec/std/isa --schema-dir spec/schemas list extension
udb show profile RVI20U64
udb validate data
udb --overlay my-isa-overlay show profile RVI20U64
udb --database my-isa --schema-dir my-schemas validate data
udb --database my-isa --schema-dir my-schemas resolve -o build/resolved-isa
udb --schema-dir my-schemas generate schema-bundle -o build/schemas
udb validate cfg -c rv64
udb validate cfg -c my-configuration.yaml
udb --overlay my-isa-overlay validate cfg -c my-configuration.yaml
udb --database my-isa --schema-dir my-schemas validate cfg -c my-configuration.yaml
udb --database spec/std/isa --schema-dir spec/schemas --overlay spec/custom/isa/qc_iu validate cfg -c cfgs/qc_iu.yaml
```

The same commands are available through `python -m udb`.

Generate the complete instruction table from bundled or explicitly supplied data:

```shell
udb generate instruction-table
udb generate instruction-table --config rv32 --output instructions.txt
udb --database my-isa --schema-dir my-schemas --overlay my-overlay generate instruction-table
```

`--config` accepts the bundled `_`, `rv32`, and `rv64` configurations or an
explicit YAML path. As in the legacy generator, configuration does not filter
instructions or pin their structural RV32/RV64 encodings. File output overwrites
an existing file but does not create missing parent directories. Stdout and files
use UTF-8/LF bytes; stdout contains only the artifact. Input/output errors exit 2.
The legacy command prelude is preserved verbatim, including the file basename.
See [the instruction-table contract](stage5-instruction-table.md).

The pure source API is `udb.instruction_table.render_instruction_table(source=None,
file_name=None)`. `source` accepts a raw/resolved database or configured architecture,
and defaults to bundled data. `generate_instruction_table(source=None, output=None,
stdout=None)` writes and returns that text. `udb.instruction_fields.InstructionFieldBuilder`
provides validated immutable descriptors with ordered opcode/decode ranges,
sign extension, shifts, exclusions, and captured source locations.

Generate generic C encodings, a SystemVerilog decode package, or the Go assembler
fragment from bundled data:

```shell
udb generate c-encoding --config rv32 -o encoding.out.h
udb generate sv-decode --config rv64 -o riscv_decode_package.svh
udb generate go-encoding --config _ -o inst.go
```

The corresponding offline APIs are
`udb.generators.c_encoding.generate_c_encoding`,
`udb.generators.sv_decode.generate_sv_decode`, and
`udb.generators.go.generate_go`. Each accepts a configured architecture.
The C and SystemVerilog generators resolve exception names through `udb.prose`;
callers with pre-rendered rows may supply typed
`udb.generators.encoding_inputs.ExceptionRecord` values instead. Generic
selection retains the legacy name-only extension filter and `RV32`, `RV64`, or
`BOTH` encoding projection rather than configuration-presence filtering.

Generate retained extension documentation as standalone AsciiDoc:

```shell
udb generate extension-document -e Zba@latest -o build/Zba
udb generate extension-document --config rv64 -e Zicsr -o build/Zicsr --include-implied
udb render pdf build/Zba/Zba.adoc -o build/Zba/Zba.pdf
```

Source generation is offline and uses the configured architecture, installed
`udb.prose` service, packaged templates, and explicit revision/date metadata.
It never invokes Git, Ruby, or a renderer. PDF output is an explicit boundary
that invokes an installed official `asciidoctor-pdf`; themes, fonts, images,
timeouts, and output paths can be supplied explicitly. The public source API is
`udb.extension_docs.generate_extension_document()` with `DocumentOptions`;
`udb.extension_docs.pdf.render_extension_pdf()` owns the external renderer
boundary. See [the extension-document contract](stage5-extension-documents.md).

Fully configured C and SystemVerilog headers can be generated without Ruby or a
native toolchain:

```shell
udb generate config-c-header --config my-full-config.yaml
udb generate config-sv-header -c my-full-config.yaml -o build/config.svh
udb --database my-isa --schema-dir my-schemas --overlay my-overlay generate config-c-header -c my-full-config.yaml
```

Configurations are explicit paths or the bundled names `_`, `rv32`, and `rv64`;
there is no implicit checkout
lookup. The default `_`, partial configurations, incomplete full configurations,
and inconsistent or undecidable configurations fail with exit status 2.
Generation preserves the reviewed legacy guard, presence-macro, version-precision,
string/array, and integer-width behavior. Unsupported macro identifiers and
collisions also fail explicitly. File outputs create missing parent directories;
file and stdout artifacts are UTF-8 with LF newlines, independent of locale and
`PYTHONIOENCODING`. Stdout contains only the header; output I/O errors use exit
status 2. See [the configuration-header contract](stage5-config-headers.md)
for exact byte conventions and supported inputs.

The public source API returns a complete string without writing files:

```python
from udb import Configuration, Database
from udb.generators.config_headers import generate_config_header

architecture = (
    Database.bundled().resolve().configure(Configuration.from_file("my-full-config.yaml"))
)
c_header = generate_config_header(architecture, "c")
sv_header = generate_config_header(architecture, "svh")
```

`validate-cfg` accepts a YAML configuration path or a bundled name (`_`, `rv32`, or `rv64`).
It resolves the selected database and explicit overlays, then checks configuration consistency,
including IDL requirements. It prints `<name>: valid`, `unsat`, or `deferred`; diagnostics go to
standard error. Exit status is 0 only for `valid`, 1 for inconsistent configurations, and 2 for
configuration input errors or an undecided check. `--validate` additionally validates resolved ISA documents
against their schemas; it is not needed for configuration checking. This command does not
type-check every instruction or CSR body, and it does not implicitly follow a configuration's
`arch_overlay` declaration. Overlays with checkout-relative IDL includes, such as `qc_iu`, need
the checkout source database (`--path`) as shown above rather than the bundled snapshot.

Proved configuration conflicts are shown as separate entries with captured requirement reasons,
rules, and original source locations when available. Array assignments summarize repeated values
and list a bounded number of other indexed values; these are observed input facts, not individually
proved causes. A parameter's definition condition is distinct from its supplied value. Unknown
core labels have an explicit raw-label fallback. This presentation does not change solver decisions
or conflict membership; invalid IDL remains an error diagnostic.
Displayed values and captured rule/IDL snippets preserve literal whitespace, even when
their previews are truncated.

Repository authors can regenerate every layout-derived architecture file without Ruby, Rake, or
ERB:

```shell
udb author layouts --root .
udb author layouts --root . --check
udb author layouts --root . --collection qc-iu --check
udb author layouts --root generated --collection standard --collection qc-iu
```

The layout renderer is intentionally limited to interpolation, conditionals, and bounded loops.
Generation owns the 532 tracked YAML outputs associated with the 31 layout sources, adds a stable
source warning, writes replacements atomically, and marks generated files read-only. `--check`
reports drift and exits with status 1 without modifying files.

Standard layouts remain the default. `--collection qc-iu` selects the five QC
CSR layouts and all 56 generated files; repeating `--collection` selects multiple
collections (standard plus QC owns 588 files). Input errors use exit status 2.
QC authoring has replaced the removed `gen_mcliciX.rb`; there is no separate QC
authoring command. See [the QC layout contract](stage5-qc-layouts.md).

`--source-root DIR` reads templates from an explicit independent source tree,
without falling back to packaged resources. Without it, a complete local source
set takes precedence over bundled templates; partial source sets are errors.
When no source templates exist at the output root, installed generation uses
bundled layouts offline. The public API also supports immutable caller-defined
collections whose source/output roots need not be under the standard ISA:

```python
from pathlib import Path, PurePosixPath
from udb import LayoutCollection, LayoutJob, generate_layouts, get_layout_collection

generate_layouts(
    Path("generated"),
    collections=(get_layout_collection("qc_iu"),),
    source_root=Path("explicit-source-tree"),
)
vendor = LayoutCollection(
    name="vendor",
    source_root=PurePosixPath("templates"),
    output_root=PurePosixPath("custom/csrs"),
    jobs=(
        LayoutJob(
            PurePosixPath("example.layout"),
            PurePosixPath("example.yaml"),
            {"number": 1},
        ),
    ),
)
generate_layouts(Path("generated"), collections=(vendor,), source_root=Path("vendor-data"))
```

Collection job paths are relative to the collection's logical source/output
roots. `source_root=` chooses the physical input tree and the first positional
root chooses the physical output tree. An optional collection `resource_root`
is relative to packaged `udb/_data`; it is never a checkout lookup. Job inputs
are recursively immutable snapshots. Plans record template and recipe-code
dependencies, reject duplicate ownership/source aliases, and write only their
owned outputs.

For other generators, `udb.authoring.GeneratedFile` describes output bytes, ownership,
dependencies, and permissions. `AuthoringPlan(outputs).apply(root, check=True)` reports drift;
omitting `check=True` writes the outputs. Replacements are atomic per file. The caller controls
the output tree while generation runs; applying a plan is not a transaction across the tree.
An optional `GeneratedFile.overwrite_prefixes` tuple restricts replacement to files starting
with one of the nonempty byte prefixes. When supplied, unowned existing files are rejected
before writes, including in check mode. Omitting it preserves ordinary authoring behavior.

Layout directives use `{{ value }}` and `{% ... %}`. Layouts that emit native configured-prose
tags quote the complete tag as a Stage 2 expression, so the authoring renderer writes it literally
for the later configuration-sensitive rendering stage.

Configuration-sensitive instruction and CSR prose can be rendered offline from captured database
and configuration data:

```python
from udb import Configuration, Database
from udb.prose import CapturedProse, ProseInputs, native_prose_values, render_native

resolved = Database.bundled().resolve()
inputs = ProseInputs.from_database(resolved, Configuration.builtin("rv64"))
scalar = CapturedProse.from_record(resolved, resolved.csr("stvec"), "fields", "BASE", "description")
text = render_native(scalar, native_prose_values(scalar, inputs))
```

`render_native` uses the bounded layout expression engine and rejects ERB. `native_prose_values`
projects the typed extension, parameter, selected-width, cache-granularity, and code-row inputs used
by the captured scalar. Structured generator consumers should use
`resolve_all_exception_records`; `resolved_exception_names` instead selects only
configuration-available codes. These APIs do not reopen checkout files or invoke Ruby, Git, or a
solver. There is intentionally no configured-prose CLI. The former restricted ERB adapter remains
only for the immutable migration oracle; live architecture sources and production consumers use
native syntax. See the [configured-prose contract](stage5-configured-prose.md).

The wheel contains the standard ISA YAML, IDL, referenced AsciiDoc sources, authoring layouts, and
their JSON schemas. The bundled layouts let the authoring command populate an explicit output root
without reading templates from a repository checkout. Code that needs direct access to those
resources can use `importlib.resources`:

```python
from importlib.resources import files

isa_data = files("udb") / "_data" / "isa"
schemas = files("udb") / "_data" / "schemas"
layouts = files("udb") / "_data" / "layouts"
qc_layouts = files("udb") / "_data" / "custom_layouts" / "qc_iu"
```

The Python source code is licensed under BSD-3-Clause-Clear. The bundled database snapshot contains
material under BSD-3-Clause-Clear and CC-BY-4.0. The license texts, attribution notice, and REUSE
metadata are included in the distribution.

Configuration declarations are immutable values, separate from architecture solving:

```python
from udb import Configuration

rv64 = Configuration.builtin("rv64")
assert rv64.mxlen == 64
custom = Configuration.from_file("my-config.yaml")
for selection in custom.extensions:
    print(selection.name, selection.presence, selection.requirements)
```

`Configuration(mapping)` and `Configuration.from_yaml(text, source=...)` accept explicit inputs.
The generic `_`, `rv32`, and `rv64` configurations are bundled. Parsing validates schemas and
version syntax, accepts legacy full-configuration extension pairs, and preserves parameter
values and requirements. `non_mandatory_extensions` becomes optional presence in the Python API.
`to_dict()` returns a mutable serializable copy. Overlay and compatible-configuration declarations
are retained as metadata; parsing never follows repository paths implicitly.
Configurations parsed from text, files, or bundled resources retain their original YAML
in `source_text` for exact IDL diagnostics. Mapping-only inputs have no original text;
this metadata is neither compared nor emitted by `to_dict()`.

`ParameterDomain` interprets parameter schemas without initializing a solver:

```python
from udb import Database, ParameterDomain, SchemaStore

db = Database.bundled().resolve()
record = db.get("parameter", "MXLEN")
domain = ParameterDomain.from_schema(record["schema"], schema_store=SchemaStore(db.schemas_root))
assert domain.enumerate_values(limit=2) == (32, 64)
assert domain.accepts(64)
```

Domains support bounds, enums, arrays, local references, and `allOf` intersections. Membership,
emptiness, singleton values, and complete bounded enumeration use JSON Schema semantics.
Defaults remain annotations. Enumeration raises when the complete result exceeds the supplied
limit; unsupported schema shapes or analyses fail explicitly. See
[the domain contract](stage3-domains.md) for the supported subset and analysis limits.

Conditions parse into immutable expressions that support three-valued evaluation and Z3 solving:

```python
from udb import EvaluationContext, TruthValue, parse_condition

condition = parse_condition(
    {
        "allOf": [
            {"extension": {"name": "Zicsr"}},
            {"param": {"name": "MXLEN", "equal": 64}},
        ]
    }
)
assert condition.evaluate(EvaluationContext(xlen=64)) is TruthValue.UNKNOWN
known = EvaluationContext(extensions={"Zicsr": "2.0.0"}, parameters={"MXLEN": 64})
assert condition.evaluate(known) is TruthValue.TRUE
closed = EvaluationContext(xlen=64, closed_world_extensions=True, closed_world_parameters=True)
assert condition.evaluate(closed) is TruthValue.FALSE
```

Condition expressions represent extension requirements, parameter comparisons, XLEN constraints,
free terms, conjunction, disjunction, negation, implication, exact-one (`oneOf`), none-of (`noneOf`),
and unresolved `idl()` blocks. `parse_condition(data)` parses raw YAML condition structures,
`condition.to_data()` converts back to deterministic data, `condition.evaluate(context)` performs
three-valued concrete evaluation (`TRUE`, `FALSE`, `UNKNOWN`), `condition.partial_evaluate(context)`
simplifies known subexpressions, and `normalize(condition)` applies Boolean identities.
Plainly parsed conditions containing `idl()` return `has_unresolved == True` and evaluate to
`UNKNOWN` when their truth depends on IDL logic. The IDL condition compiler resolves those leaves
into the ordinary condition algebra; configured architectures do this before solver encoding.

`ResolvedDatabase.configure(configuration)` creates an immutable `ConfiguredArchitecture`:

```python
from udb import Configuration, Database, QueryPresence

db = Database.bundled().resolve()
arch = db.configure(Configuration.builtin("rv64"))

assert arch.extension_presence("I") is QueryPresence.MANDATORY
check = arch.check()
assert check.status.name == "VALID"
print([inst.name for inst in arch.possible_instructions])
```

`ConfiguredArchitecture` combines extension-version catalogs, parameter domains, YAML and compiled
IDL conditions, and configuration declarations. Queries return `QueryPresence` (`MANDATORY`, `POSSIBLE`, `ABSENT`,
`DEFERRED`). Supported queries include extension presence, version presence, instructions, CSRs, CSR
fields, exception codes, interrupt codes, parameters, profiles, encoding overlaps, CSR address
overlaps, and compatibility checking via `arch.compatible_with(other)`. Queries that depend on
undecidable solver queries return `DEFERRED` or `UNKNOWN`; supported IDL requirements no longer
cause deferral. `arch.check()` returns an `ArchitectureCheck` with status `VALID`, `UNSAT`, or
`DEFERRED`. Unsatisfiable configurations report labeled diagnostic conflicts. Invalid custom
IDL requirements produce source-aware `invalid-idl-condition` diagnostics.

`udb.configuration_diagnostics.explain_conflict(arch, check)` returns immutable explanation entries
in exactly `check.conflict` order. Each retains its complete original `label`, including when a long
display is truncated, plus any captured source spans and details. `format_check_diagnostics(arch,
check)` returns the corresponding stderr lines without rereading sources or performing solver
queries. The underlying `ArchitectureCheck` and its diagnostics are unchanged.

## Profile configuration generation

`udb.profile_configs.profile_configuration(resolved, name)` converts a profile
into an immutable partial `Configuration`. Declared mandatory/optional
requirements and profile requirements are retained; strict conversion adds
solver-proven mandatory extensions at their minimum possible compatible
versions. Invalid or undecidable inputs are errors. `strict=False` requests only
the declared configuration, without solving or claiming its consistency.

`profile_configuration_plan(resolved, names=None)` returns an `AuthoringPlan` of
deterministic read-only `<profile>.yaml` files. It computes every selected
configuration before writing and reuses atomic output and symlink checks.
Explicit selections leave other files untouched. The installed CLI resolves
bundled or explicitly selected source data and supports explicit overlays:

```shell
udb generate profile-configs -o generated-profiles
udb generate profile-configs --profile RVI20U32 -o generated-profiles
udb generate profile-configs --profile RVI20U32 -o generated-profiles --check
udb --database my-isa --schema-dir my-schemas --overlay my-overlay generate profile-configs -o generated-profiles
```

Generation exits 0 on success. `--check` prints differing relative paths and
exits 1 without writing; invalid input or output errors exit 2. No repository,
Ruby or network access is needed. YAML quoting and version spelling use the
Python serializer; extension and constraint semantics match the retained native
profile artifacts. Profile execution-width requirements do not implicitly
assign machine MXLEN.

Existing selected outputs must have the generated-profile header, so accidentally
choosing a source-profile directory cannot overwrite its records. Portable names
must not collide under case folding; unrepresentable IDL/YAML output is rejected
before writing.

## IDL parsing and semantics

`udb.idl` parses expressions, function bodies, instruction operations, constraints,
loops, and ISA files into source-aware syntax trees. Nodes provide `to_idl()` and
`to_h()`; `idl.from_h()` restores serialized trees. Parse failures raise
`IdlSyntaxError`; semantic failures raise `IdlTypeError` or `IdlSemanticError`.
Evaluation that cannot determine a value raises `IdlValueUnknown`.

Type checking and execution use an explicit `SymbolTable` and `IdlEnvironment`
from `udb.idl.symbols`. ISA checking registers types, function signatures and
globals before checking bodies. A standalone function body requires a local
scope and its expected return type:

```python
from udb import idl
from udb.idl.symbols import IdlEnvironment, SymbolTable
from udb.idl.types import Type, TypeKind

symbols = SymbolTable(IdlEnvironment(mxlen=64))
definitions = idl.parse_isa(
    "%version: 1.0\n"
    "function increment { returns Bits<8> arguments Bits<8> value "
    "description { Increment a value. } body { return value + 1; } }\n"
)
definitions.type_check(symbols)
symbols.push(None)
symbols.add("__expected_return_type", Type(TypeKind.BITS, width=8))
body = idl.parse_function_body(
    "Bits<8> values[2]; "
    "for (Bits<8> i = 0; i < 2; i++) { values[i] = increment(i); } "
    "return values[1];"
)
body.type_check(symbols)
assert body.return_value(symbols) == 2
symbols.pop()
```

`global_clone()` copies global bindings; `deep_clone()` copies every scope.
Both isolate mutable bindings, nested values and memoization while retaining
immutable types and sources. The legacy `clone_values=False` argument does not
permit mutation to leak into the original table. Tables constructed from the
same environment also own their mutable bindings independently.

Python rejects duplicate declarations in the same scope but permits outer-scope
shadowing. Unknown conditional writes invalidate their destination rather than
retaining a previously known value.

## Architecture-bound IDL

`udb.idl_architecture.ArchitectureCompiler(architecture)` loads captured global and
include sources and returns owned `CompiledIdl` contexts:

```python
from udb.idl_architecture import ArchitectureCompiler

compiler = ArchitectureCompiler(arch)
operation = compiler.compile_instruction("addi", effective_xlen=64)
operation.ast.type_check(operation.symtab)
print(operation.source.label, operation.effective_xlen)
```

`compile_function`, `compile_csr` and `compile_field` expose the corresponding
bodies, binding environments and expected return types. Explicit execution widths
must be possible for the architecture and structurally applicable to the object.
Field reset evaluation uses machine MXLEN, not instruction XLEN; a requested
execution width is still validated. `return_value()` evaluates a fresh clone
without mutating the compiled context.

`arch.instruction_operation("addi", effective_xlen=64)` and
`arch.csr_behavior("misa", effective_xlen=64)` expose these genuine compiled contexts
directly. Instruction XLEN is required explicitly; CSR behavior retains its compiler-owned
return context and source mapping.

`compiler.type_check()` returns `ArchitectureTypeCheckResult`. Its `checked` tuple
records attempted contexts and `diagnostics` records failures. Applicable
instructions without an optional `operation()` produce immutable `unavailable`
records with context, actual record/behavior source, behavior and reason. They are
not checked successes. `.ok` means no type diagnostics; `.complete` additionally
requires no unavailable contexts. `.raise_errors()` reports diagnostics only;
direct compilation of a missing body raises `DataError`. Present empty bodies
are checked and malformed bodies remain errors.

Native CSR descriptors expose integer addresses and field existence/base/reset
properties; dynamic access types use `field.type(effective_xlen)`. Field sw-write
bitfields retain all structurally applicable source fields, even when an explicit
field is absent from the configured implementation.

`udb.idl.value_bounds.min_value(node, symtab)` and `max_value(node, symtab)` expose
conservative value bounds. Source spans retain original file coordinates for
captured includes and YAML bodies.

## IDL analysis and source generation

`udb.idl.passes` provides standalone passes over ordinary compiled contexts:

```python
from udb.idl.passes import prune, source_registers, to_adoc

optimized = prune(operation.ast, operation.symtab)
print(source_registers(optimized, operation.symtab))
adoc_source = to_adoc(optimized)
```

Pruning owns its output tree and cloned binding values. `reachable_functions` and
`reachable_exceptions` compute transitive closures; optional caches are caller-owned
and specialize function argument contexts. `referenced_csrs`, `source_registers`
and `destination_registers` discover dependencies, with immutable `RegisterRef`
records retaining the register file and known or generated index. `return_values`
returns conditional expression alternatives without inventing a definite value.

`constexpr`, `control_flow` and `written` expose hart analyses without AST monkey
patches. `DecodeEncoding`, `DecodeVariable`, `build_decode_tree` and
`DecodeGenerator` expose decoder analysis and C++ source generation, including
implementation guards, hint ordering and variable exclusions.

`to_adoc` and `to_option_adoc` generate source entirely in Python. Rendering is a
separate consumer step using official external Asciidoctor/asciidoctor-pdf;
no renderer or Ruby-backed IDL pass is bundled.

The existing canonical syntax-highlighting definition is `doc/src/prism/idl.js`,
registered with the documentation site's Prism renderer. Its generated TextMate
counterpart supports the VS Code extension. These definitions are separate from
the Python compiler and add no parser or highlighting dependency to the default
installed package.

## IDL conditions

`udb.idl_conditions.compile_idl_condition(text, symtab, source=...)` parses and type-checks
a constraint body, returning a symbolic `udb.conditions.Condition`. Parameters and extension
predicates stay symbolic even when the supplied table contains configured values. The caller's
bindings and scope are unchanged. `resolve_idl_conditions(condition, symtab)` recursively replaces
IDL leaves while retaining logical siblings, owner/version antecedents and reason metadata.

Translation supports Boolean logic and implication, the six comparisons, parameter element,
range and size selectors, array membership, extension/version predicates, XLEN equality and
statically bounded loops. Loop controls and comparison operands must be compile-time evaluatable
and parameter-independent. Unknown operands, unsupported constructs and unbounded loops raise
source-aware IDL errors; there are no free-proposition or guessed-value fallbacks.

Architecture requirements use a separate lazy, translation-only symbol table, avoiding a circular
dependency on runtime presence queries. Captured YAML and configuration source coordinates are
retained. Generic configurations are valid with compiled requirements, and the rv32 SXLEN invariant
proves the seven 64-bit supervisor extensions absent. Runtime version callbacks also prove
catalog-impossible versions absent, rather than retaining Ruby's weaker unknown answer.

## Schema documentation

Schema MDX generation is included in the default install and works offline:

```python
from udb.schema import SchemaStore
from udb.schema_docs import SchemaDocumentation, generate_schema_docs

docs = SchemaDocumentation()  # bundled schemas; no ISA database or checkout needed
page = docs.render("config_schema.json")
plan = docs.plan("schema-docs")
changed = plan.apply("schema-docs")
assert not plan.apply("schema-docs", check=True)
limits = docs.notices  # located, explicitly warned legacy presentation constraints

custom = SchemaDocumentation(SchemaStore("my-schemas"))
custom.plan("custom-docs").apply("custom-docs")
drift = generate_schema_docs("schema-docs", check=True)
```

The CLI is `udb [--schema-dir DIR] generate schema-docs -o DIR [--check]`.
`--diagnostics` emits one JSON document containing status, paths, and all
located notices; input/output failures return exit 2 with an error document.
`--schema NAME.json --output-file reference/schema.mdx` selects one page.
All-page generation includes versioned category metadata and an index that
retains historical pages. Check mode returns missing/different owned paths
without writing (exit 1 on drift, 2 on invalid input). Differing existing MDX
is immutable by default; `--replace-current` permits only canonical pages of
the selected current schemas, never arbitrary/historical output overrides.
Re-plan if historical page names change. Unknown keywords and unsupported
schemas fail explicitly; no refs are fetched and no renderer is invoked.
See [the precise artifact contract](stage5-schema-docs.md), including exact
Ruby oracles and deliberately retained historical drift.

## Retained configured reports and instruction matching

See [Stage 5 query/report API](stage5-query-reports.md) for `udb.query_reports`,
immutable outputs, native catalog/configuration selection, encoding-field decoding,
and the testing module CLI. Permanent installed command naming remains separate.

## C++ hart source generation

Retained C++ hart/ISS source trees are generated offline from configured
architectures:

```python
from pathlib import Path
from udb import Configuration, Database
from udb.cpp_hart import CppHartGenerator

resolved = Database.bundled().resolve()
architecture = resolved.configure(Configuration.builtin("rv32"))
generator = CppHartGenerator([architecture])
generator.generate(Path("generated-hart"))
```

`CppHartGenerator.plan()` exposes deterministic output bytes, modes, ownership,
input hashes and unavailable instruction-operation contexts before writing.
Multiple configurations share one output tree when `build_name` is supplied.
`RuntimeResources.from_path(ROOT)` selects an explicit checkout/resource root;
the default reads the installed package's declared C/C++/GDB/Renode assets.
Generation itself does not invoke Ruby, Git, CMake, a compiler, a formatter,
dependency installation or the network.

The CLI is:

```sh
udb generate cpp-hart -c rv32 -o generated-hart
udb generate cpp-hart -c rv32 -c rv64 --build-name both -o generated-both
```

Use global `--database`, `--schema-dir`, and repeatable `--overlay` options for
explicit caller-owned inputs. Configuration overlays are never discovered implicitly.
`--config-dir` resolves named YAML selectors used with `--all-configs`.
`--build-type` accepts `Debug`, `RelWithDebInfo`, `Release` or `Asan`; `--check`
reports drift without writing. See [the precise C++ source contract](stage5-cpp-hart.md)
for retained files, native comparison evidence and separate compilation limits.
