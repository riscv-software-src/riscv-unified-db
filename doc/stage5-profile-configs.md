<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Profile configuration generation

Layer 22 replaces `Portfolio#to_config`, `Portfolio#to_strict_config`, and the
profile-file generation consumer. It does not replace profile documents or
portfolio groups. Input is a resolved database and a named profile; no repository
or Ruby lookup is allowed.

`udb.profile_configs.profile_configuration(database, name, strict=True)` returns
an immutable `Configuration`. It carries the profile's declared mandatory and
optional extension requirements, optional subcategories treated as optional,
and its additional requirements. Extensions are sorted by name. Missing
descriptions become empty strings, matching accepted Ruby correction 14.
Profile `base` is not a fabricated MXLEN assignment: the profile's own
requirements describe the relevant execution mode and width. Parameters remain
empty, matching the current profile conversion rather than portfolio-group
parameter synthesis.

Strict conversion checks the genuine configured architecture, then expands
extensions proven mandatory by that complete condition system. Each newly
required extension receives the legacy compatible requirement anchored at its
lowest satisfiable declared version. Existing declared requirements and optional
entries remain intact, including an optional extension independently proved
mandatory. Every presence/version query must be decided; unknown results,
unsatisfiable input, unknown extensions, malformed declarations and missing
possible versions are explicit errors. No solver assumptions are weakened.

`profile_configuration_plan(database, names=None)` returns the existing
`AuthoringPlan`, containing `<profile>.yaml` outputs beneath a caller-selected
output root. All outputs are computed before any write. Unsafe output names are
rejected; writes reuse the existing atomic, symlink-safe authoring boundary and
read-only generated-file permissions. `--check` is non-mutating and reports drift.
Explicit selection does not delete other profiles or caller-owned files.

Existing outputs must carry the known generated profile header; both write and
check mode reject an unowned file, including a source profile selected as its
own output. The shared `GeneratedFile.overwrite_prefixes` opt-in performs this
check before writes, without changing other authoring callers. Names must be
portable filenames and unique under case folding. Generated YAML is reloaded
and compared to the intended configuration before the plan is returned; IDL
whose characters cannot round-trip is rejected rather than written lossily.

The native optional subcategories `expansion`, `localized`, `development` and
`transitory` all map to optional. Prohibited or unknown presences are explicit
errors, rather than Ruby's non-mandatory-to-optional fallback. Malformed empty
requirements are rejected by configuration validation; false requirements remain
false and make strict generation fail, rather than being omitted.

The artifact oracle contains unmodified Ruby `to_config` and `to_strict_config`
results for all ten bundled profiles, captured under the shared Ruby lock from
the accepted Stage 4 implementation. All ten strict results were independently
compared equal to the tracked `cfgs/profile/*.yaml` documents before porting.
Comparison canonicalizes only version-requirement spelling;
extension membership, requirement operators, values, scalar/list
shape and all other fields remain asserted. YAML uses the existing deterministic
Python serializer rather than Ruby quoting/indentation. The generated banner
names the new command; these presentation changes are not semantic corrections.
Embedded IDL must remain a literal scalar and survive writing/reloading.

The expanded configuration is checked again before return: independently
choosing minimum compatible versions must not silently emit an inconsistent
combination. A generated inconsistent combination is reported, not weakened or
replaced with guessed version bounds.

Acceptance includes all-ten-profile frozen parity, live Ruby freshness under its
explicit opt-in, synthetic transitive/optional/version/invalid cases, repeatable
read-only output and drift checks, and standalone wheel/sdist API and CLI
generation. No Ruby code may run in installed-package checks. Existing tracked
profile files remain an independent semantic oracle during cutover.
