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

The package also installs a small command-line interface for inspecting raw records:

```shell
udb list extension
udb show extension Zvkg
udb --path spec/std/isa list extension
udb --resolved show profile RVI20U64
udb --resolved --validate show profile RVI20U64
udb --resolved --overlay my-isa-overlay show profile RVI20U64
udb --path my-isa --schemas my-schemas --resolved --validate show extension Xdemo
```

The same commands are available through `python -m udb`.

The wheel contains the standard ISA YAML, IDL, and referenced AsciiDoc sources and their JSON
schemas. Code that needs direct access to those resources can use `importlib.resources` without a
repository checkout:

```python
from importlib.resources import files

isa_data = files("udb") / "_data" / "isa"
schemas = files("udb") / "_data" / "schemas"
```

The Python source code is licensed under BSD-3-Clause-Clear. The bundled database snapshot contains
material under BSD-3-Clause-Clear and CC-BY-4.0. The license texts, attribution notice, and REUSE
metadata are included in the distribution.
