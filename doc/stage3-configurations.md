<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 3 configuration inputs

`Configuration(mapping)`, `Configuration.from_yaml(text)`, and
`Configuration.from_file(path)` parse immutable configuration declarations.
`Configuration.builtin("_")`, `Configuration.builtin("rv32")`, and
`Configuration.builtin("rv64")` use generic configurations bundled in the wheel.
These constructors validate structure and version syntax; architecture membership,
parameter domains, and satisfiability are checked by the configured architecture.

`ConfigurationKind` distinguishes unconfigured, partial, and full declarations.
`extensions` contains `ExtensionSelection` values with a `Presence` of mandatory,
optional, or prohibited and a tuple of conjunctive `VersionRequirement` values.
The existing `non_mandatory_extensions` YAML spelling maps to optional presence.
Full configurations accept exact versions, including the legacy `[name, version]`
pair form, and require `MXLEN`. Partial configurations retain unknown parameters.
`mxlen` includes the existing necessary inference from subordinate mode widths.

Configuration inputs never implicitly follow `arch_overlay` or `compatible`
paths. Callers supply overlays to database resolution and compatible configurations
to consistency checks explicitly, so installed code has no repository lookup.
`params` and `requirements` are recursively immutable; `to_dict()` returns a
mutable, serializable copy. Parse errors include source locations when available.

The tests map the Ruby configuration parser's three variants, full exact versions,
legacy pairs, mandatory/optional/prohibited selections, extra-extension policy,
width inference, and immutable parameter values. Live differential checks compare
every repository configuration, including generated profiles, without compiling
IDL or constructing a configured architecture. Tests for architecture validity and
extension closure belong to the configured-query slice.

The existing profile configuration generator emitted null descriptions when the
profile had no description, violating its own configuration schema. Its Ruby
emitter now uses an empty string in that case, and its generated configurations
are regenerated. Five example/test configurations' obsolete external schema URLs
are updated to the current local schema reference. Neither change retires a generator or changes
architectural requirements.
