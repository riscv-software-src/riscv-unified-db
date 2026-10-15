<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 3 configured architecture queries

`ResolvedDatabase.configure(configuration)` creates an immutable
`ConfiguredArchitecture`. The caller must supply a `Configuration`; the API never
looks up configuration names, overlays, compatible configurations, or repository
paths implicitly.

The configured view combines extension-version metadata, YAML conditions,
parameter domains, and the configuration declaration in an instance-owned solver.
It enforces at most one version per extension, extension and version requirements,
parameter `definedBy` and requirements, exact full configurations, partial
mandatory/optional/prohibited selections, fixed parameter values, and
`additional_extensions: false`.

```python
from udb import Configuration, Database, QueryPresence

database = Database.bundled().resolve()
architecture = database.configure(Configuration.builtin("rv64"))

assert architecture.extension_presence("I") is QueryPresence.MANDATORY
print(architecture.check().status)
print([instruction.name for instruction in architecture.possible_instructions])
```

`check()` returns `VALID`, `UNSAT`, or `DEFERRED` with structured diagnostics and
a deletion-minimal labeled conflict for unsatisfiable data constraints. Unknown
extension names or versions, unknown parameters, out-of-domain values, and missing
values in fully configured architectures are diagnostics rather than path lookups
or process-global failures. `compatible_with()` accepts another configured
architecture or an explicit `Configuration` and checks both declarations in a
fresh solver context.

Presence queries return `MANDATORY`, `POSSIBLE`, `ABSENT`, or `DEFERRED`.
They cover extension versions, generic records, instructions, CSRs, CSR fields,
exception codes, interrupt codes, parameters, profiles, and manual-version
extension membership. A CSR field always includes its parent CSR condition; a
field without `definedBy` inherits the parent condition. Direct extension queries
inspect the declared `definedBy`, while implied queries use solver implication and
therefore include transitive extension requirements.

Instruction overlap checks normalize both legacy `encoding.match` declarations
and resolved `format` declarations. They account for RV32/RV64 variants, split
field locations, exact variable `not` exclusions, referenced opcode values, and
hint references. A shared code point is a conflict only when both defining
conditions can hold; mutually exclusive definitions are reported as aliases.
CSR overlap checks use direct addresses, virtual addresses, and the indirect key
`(priv_mode, indirect_address, indirect_slot)`, with XLEN and defining conditions.

The focused tests map to the existing Ruby `test_cfg.rb` and `test_cfg_arch.rb`
coverage for unconfigured, partial, full, mandatory/optional/prohibited,
extension closure, parameter scope, instruction/CSR presence, and compatibility.
An opt-in live differential (`UDB_TEST_RUBY=1`) compares the generic and custom
mock configurations through the real Ruby `ConfiguredArchitecture`. Encoding
tests cover the behavior of Ruby `Instruction#encoding` and
`Encoding#indistinguishable?`, including exclusions and hints.

Stage 4 remains responsible for compiling and proving IDL. In Stage 3, an active
extension or parameter requirement expressed as `idl()` makes architecture
validity `DEFERRED`. Instruction operations, reachable functions and exceptions,
CSR read/write/type/reset behavior, dynamic register-length expressions, and any
other query that evaluates IDL return or require an explicit deferred result.
Data-only presence and conflict queries continue to work when unrelated records
contain IDL.
