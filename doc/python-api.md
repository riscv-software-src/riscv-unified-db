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
udb --path spec/std/isa list extension
udb --resolved show profile RVI20U64
udb --resolved --validate show profile RVI20U64
udb --resolved --overlay my-isa-overlay show profile RVI20U64
udb --path my-isa --schemas my-schemas --resolved --validate show extension Xdemo
udb --path my-isa --schemas my-schemas --validate resolve build/resolved-isa
udb --schemas my-schemas schemas build/schemas
udb validate-cfg rv64
udb validate-cfg my-configuration.yaml
udb --overlay my-isa-overlay validate-cfg my-configuration.yaml
udb --path my-isa --schemas my-schemas validate-cfg my-configuration.yaml
udb --path spec/std/isa --schemas spec/schemas --overlay spec/custom/isa/qc_iu validate-cfg cfgs/qc_iu.yaml
```

The same commands are available through `python -m udb`.

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
udb generate-layouts --root .
udb generate-layouts --root . --check
```

The layout renderer is intentionally limited to interpolation, conditionals, and bounded loops.
Generation owns the 532 tracked YAML outputs associated with the 31 layout sources, adds a stable
source warning, writes replacements atomically, and marks generated files read-only. `--check`
reports drift and exits with status 1 without modifying files.

For other generators, `udb.authoring.GeneratedFile` describes output bytes, ownership,
dependencies, and permissions. `AuthoringPlan(outputs).apply(root, check=True)` reports drift;
omitting `check=True` writes the outputs. Replacements are atomic per file. The caller controls
the output tree while generation runs; applying a plan is not a transaction across the tree.

Layout directives use `{{ value }}` and `{% ... %}`. Any literal `<% ... %>` text in a layout is
content preserved for a later configured-document rendering stage; it is not executed by the
layout renderer.

The wheel contains the standard ISA YAML, IDL, referenced AsciiDoc sources, authoring layouts, and
their JSON schemas. The bundled layouts let the authoring command populate an explicit output root
without reading templates from a repository checkout. Code that needs direct access to those
resources can use `importlib.resources`:

```python
from importlib.resources import files

isa_data = files("udb") / "_data" / "isa"
schemas = files("udb") / "_data" / "schemas"
layouts = files("udb") / "_data" / "layouts"
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
