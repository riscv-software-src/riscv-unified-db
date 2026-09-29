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

The package supports querying the bundled, raw standard ISA records and schemas. The data
is the unconfigured source database: it has not been resolved for an XLEN, extension set, or named
configuration. Configuration resolution and the full behavior of the existing Ruby implementation
are still being ported.

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

`resolved.documents` exposes the resolved mappings keyed by relative source path. `$child_of`
and `$parent_of` record inheritance relationships. Data `$ref` links remain references; they are
not expanded. Resolution does not apply schema defaults, choose extension versions, evaluate
configurations or conditions, or compile IDL. It does not yet provide a configured architecture.

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
