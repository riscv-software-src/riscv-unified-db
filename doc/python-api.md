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

The package also installs a small command-line interface for inspecting raw records:

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
```

The same commands are available through `python -m udb`.

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
Conditions containing `idl()` return `has_unresolved == True` and evaluate to `UNKNOWN` when their
truth depends on IDL logic. Full compilation and proof of IDL logic are deferred to Stage 4.

`ResolvedDatabase.configure(configuration)` creates an immutable `ConfiguredArchitecture`:

```python
from udb import Configuration, Database, QueryPresence

db = Database.bundled().resolve()
arch = db.configure(Configuration.builtin("rv64"))

assert arch.extension_presence("I") is QueryPresence.MANDATORY
check = arch.check()
# rv64 includes idl()-gated extensions and parameters, so it is DEFERRED until Stage 4.
assert check.status.name == "DEFERRED"
print([inst.name for inst in arch.possible_instructions])
```

`ConfiguredArchitecture` combines extension-version catalogs, parameter domains, YAML conditions,
and configuration declarations. Queries return `QueryPresence` (`MANDATORY`, `POSSIBLE`, `ABSENT`,
`DEFERRED`). Supported queries include extension presence, version presence, instructions, CSRs, CSR
fields, exception codes, interrupt codes, parameters, profiles, encoding overlaps, CSR address
overlaps, and compatibility checking via `arch.compatible_with(other)`. Queries that depend on
unresolved IDL logic return `DEFERRED` or `UNKNOWN` without failing unrelated data queries.
`arch.check()` returns an `ArchitectureCheckResult` with status `VALID`, `UNSAT`, or `DEFERRED`.
Unsatisfiable configurations report labeled diagnostic conflicts.
