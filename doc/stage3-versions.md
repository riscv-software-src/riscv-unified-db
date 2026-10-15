<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 3 version slice

This slice supplies the version primitives used by later configuration, condition, and solver
work. It does not resolve configurations or initialize a solver.

## Public contract

- `Version` is immutable, hashable, and totally ordered. `Version.parse()` accepts
  `MAJOR[.MINOR[.PATCH[-pre]]]`, omitted components are zero, `canonical` and `str()` return three
  numeric components, and `to_rvi()` preserves the source precision used by RISC-V identifiers.
- A prerelease sorts immediately before the release with the same numeric components.
  `next_patch()` and `previous_patch()` return new values; the latter retains the existing UDB
  boundary convention of borrowing through `9999`.
- `VersionRequirement` is immutable and supports `=`, `!=`, `<`, `<=`, `>`, `>=`, and `~>`. Bare
  versions mean equality. `parse_version_requirements()` returns an immutable tuple of conjunctive
  requirements and maps a missing or empty value to `>= 0.0.0`.
- `ExtensionVersion` retains immutable release metadata. `ExtensionVersionSet` sorts releases,
  rejects canonical duplicates, and applies `breaking: true` compatibility boundaries. The
  extension database record exposes `version_set`, `versions`, exact lookup, compatible releases,
  ratified releases, and minimum/maximum helpers.
- `~>` is RISC-V compatibility, not the similarly named RubyGems pessimistic constraint. If the
  requested version is not released, the next greater known release is the anchor. A later
  breaking release is excluded and starts a new range; a breaking anchor is compatible with later
  releases until another breaking release.

The extension schema adds the documented `breaking` boolean and advances `ext_schema.json` from
`v0.1` to `v0.2`. The shared requirement schema now accepts `!=`, accepts only the RISC-V `-pre`
suffix, and describes RISC-V compatibility rather than RubyGems pessimistic constraints;
the version work originally advanced `schema_defs.json` from `v0.2` to `v0.3`; the condition slice
subsequently advances it to `v0.4` to admit Boolean condition identities.

## Test mapping

`tests/python/test_versions.py` maps the complete behavior of Ruby `VersionSpec` and
`RequirementSpec`: accepted and rejected spellings, canonical and RVI forms, equality and hashing,
ordering, increment/decrement boundaries, all comparison operators, compatible requirements, and
extension release metadata. Every version string in the bundled extension corpus is parsed by both
implementations. Small exhaustive version grids check every ordering relation, and table-driven
boundary cases exercise every operator below, at, and above its target.

The same file covers the extension APIs from `obj/extension.rb`: numeric sorting, exact lookup,
minimum/maximum and ratified releases, compatibility ranges, non-exact compatibility anchors,
duplicate detection, immutability, and schema validation of `breaking`. The installed-package gate
loads bundled extension metadata and evaluates ordinary and compatible requirements outside the
checkout.

Set `UDB_TEST_RUBY=1` to run `tests/python/ruby_versions_oracle.rb`. The oracle is test-only and
uses the repository Ruby implementation; production and installed-package code never invokes Ruby.

## Confirmed Ruby corrections

The live oracle reproduced these behaviors on 2026-09-29:

- `VersionSpec.new("1.0.0-pre") <=> VersionSpec.new("1.0.0")` returns `1`. Python follows the
  release ordering already described by the Ruby Z3 implementation and sorts prerelease first.
- Incrementing `1.2.3` produces an object whose `to_s` is still `1.2.3`, whose canonical value is
  `1.2.4`, and which is `eql?` to the original. Decrementing has the same stale string/hash defect.
  Python returns self-consistent new values.
- With releases `1.0`, breaking `2.0`, and `3.0`, Ruby reports compatible releases `[1.0, 2.0]`
  from `1.0` and only `[2.0]` from `2.0`. This includes the breaking boundary in the old range and
  prevents the new range from extending upward. Ruby also treats an explicit `breaking: false` as
  breaking because it checks only whether the key has a non-null value. Python returns `[1.0]` and
  `[2.0, 3.0]`, and a false marker does not start a boundary.
- The raw-mapping branch of Ruby `RequirementSpec#satisfied_by?` ignores the requested `~>` base.
  Bases `1.0`, `2.0`, `3.0`, and `99.0` all accepted candidates `1.0`, `2.0`, and `3.0` in the
  reproduction. Python evaluates the requested base against the version set.

The prerelease, patch-value, and raw `~>` corrections are asserted as narrow expected divergences in
the live differential test. Extension compatibility ranges were separately reproduced by invoking
the real Ruby `ExtensionVersion#compatible_versions` method with allocated release metadata. No
Python-only defect is recorded as a Ruby correction.
