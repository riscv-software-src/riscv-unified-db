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

This first release supports querying the bundled, raw standard ISA records and schemas. The data
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

The alpha API does not yet provide a resolved architecture model or evaluate `$inherits`, overlays,
configurations, `$ref`, conditions, IDL, or Z3 semantics.

The package also installs a small command-line interface for inspecting raw records:

```shell
udb list extension
udb show extension Zvkg
udb --path spec/std/isa list extension
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
