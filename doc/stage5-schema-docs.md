<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5: standalone schema documentation

## Scope and artifact contract

This lane replaces both `schema-doc-gen` and `schema-docs-all` in
`tools/internal-gems/schema_doc_gen`, including its index generator. Python
produces **MDX source**, not rendered HTML. Docusaurus and its existing
`AnchorOpenDetails` component remain the renderer. Generation uses a bundled
or caller-supplied `SchemaStore`, never a checkout, Ruby, or the network.
The default install already supplies the JSON Schema and YAML dependencies;
no new extra or dependency is required.

The oracle is the **current Ruby implementation run against current schemas
into a new, isolated output tree**. Tracked `doc/docs/schemas` pages are a
separate historical baseline, not the oracle for deliberately changed
schemas. Existing same-version drift must be reported, not "repaired" by
changing schemas, incrementing versions, or rewriting historical artifacts.
Ruby oracle capture must precede Python implementation.

The supported input dialect and identifiers are those of `SchemaStore`:
Draft 7 and `$id: v<major>.<minor>`. Versions are independent per schema.
Meta-schema files are not documentation pages. The single-page API returns
the exact MDX string; all-page generation plans
`<id>/<filename-without-json>.mdx`, `<id>/_category_.json`, and `index.mdx`.
An explicit single-file output takes precedence over the versioned tree.

Preserve Ruby's frontmatter (including legacy regeneration instructions and
generator provenance URL), badge, overview, Quick Start, full examples,
composition/Variants, Definitions, Properties and Schema Information.
Required properties sort first using the captured Ruby 3.4 numeric-key
ordering, **including its unstable tie behavior** in unsorted tables with
more than sixteen fields. Stable Python sorting would reorder three current
pages (`csr_schema`, `inst_schema`, `profile_schema`) and is therefore not
used. Already grouped inputs retain insertion order.
Property descriptions use their first paragraph, fold newlines to spaces,
and escape angle brackets. Full definition descriptions retain their separate
body and first-line summary.
`type: null` placeholders and `$source` tooling fields follow the legacy
presentation, including the tooling note. Definition anchors lowercase and
replace underscores; variant anchors use lowercase alphanumeric slugging.
Keep the exact `<details>`/summary styles, anchor component import, table
escaping, whitespace and terminal-newline behavior.

`schema_defs.json` references inline the same descriptions/types as Ruby.
Other registered schema references retain independently versioned relative
links; Draft 7 meta-schema references link to its absolute `$id`. Absolute
HTTP(S) references are hyperlinks only, never fetched. Local refs must resolve
in the supplied store; missing refs and unsafe references are errors.
The legacy external-fragment transformation (replace `/` with `-`, including
the leading `/$defs/` prefix) is retained literally. This can produce a
Markdown anchor that does not match a definition anchor; it is an existing
Ruby artifact defect, not evidence of unresolved JSON references. Link
corrections must be independently reviewed, not hidden in oracle comparison.
Preserve internal object-variant expansion and remaining shared definitions,
array-of-object mini-tables, enums, boolean sub-schemas, examples and example
metadata removal. YAML examples preserve Ruby Psych serialization, not merely
equivalent YAML data.

The example serializer implements Psych 5.3.1 scalar scanning and libyaml
0.2.5 emission over isolated ruamel event machinery. Ordinary strings are
not restricted to the original fixtures: indicator/date/numeric-looking strings,
folding at 80 columns, long UTF-8 keys, trailing newlines, control characters,
non-BMP Unicode, nested collections, nulls and Ruby float spelling are covered
by genuine native differential captures. Ruby truthiness and collection
inspection also apply to example metadata. Ruby-derived sorting is permanently
pinned to Ruby 3.4.10 `enum.c` uniform intro-sort tie ordering.
The adjacent packaged `schema_docs/NOTICE` retains the BSD-2-Clause and MIT
attribution/license texts for these adaptations.

## Bounded presentation and explicit diagnostics

This is a legacy-compatible **documentation projection**, not a second JSON
Schema validator. `SchemaStore` validates schema structure. Rendering accepts
only an enumerated vocabulary and known schema-node shapes; unknown keywords,
unhandled tuple schemas, unsupported type unions and invalid/cyclic expandable
references fail explicitly before writing. Validation-only constraints that
Ruby does not describe in its tables are disclosed with location-qualified
projection notices, rather than silently claimed as rendered. The two
existing non-Draft-7 keywords (`$refs`, `unevaluatedProperties`) and the
`inst_schema` definition's reference-shaped `type` string require explicit,
exact-path legacy diagnostics, not reinterpretation as `$ref` or a different dialect.
No schema source is edited to accommodate these diagnostics.

Rendering records consumption of individual schema-node annotations and
constraints, independently of the artifact bytes. Thus omitted definition/
variant examples, titles, descriptions, constants, type constraints suppressed
by enum presentation, nested dialect declarations and conjunctive compositions
receive notices. Truncated property descriptions and first-only property
examples are marked partial; required fields suppressed from tables are also
partial. Notice pointers use JSON Pointer escaping, including property names
containing `/` or `~`. A feature rendered completely elsewhere in the same
projection is not mislabeled as omitted.

The vocabulary comprises `$schema`, top-level `$id`/`$defs`, `$ref`, `title`,
`description`, `examples`, scalar `type`, `required`, `properties`, `const`,
`enum`, `items`, `oneOf`/`anyOf`/`allOf`, and the located validation-only
keywords `additionalProperties`, `patternProperties`, `not`, `if`/`then`/`else`,
`propertyNames`, `contains`, `pattern`, `format`, numeric bounds, `multipleOf`,
array/string/object bounds, `uniqueItems`, `default`, `readOnly`/`writeOnly`
and `$comment`. Nested definitions/identifiers, legacy `definitions`,
structured enum/const values, non-object roots, boolean definition blocks,
root reference/literal presentation, named reference anchors and
unregistered/unsafe/invalid-JSON-pointer local refs are explicit
errors. Boolean property/array-item schemas are supported. Only the three
exact existing legacy paths/values are tolerated with dedicated notices;
the same invalid spellings elsewhere are errors.

## Writes, checks and history

Plan before writing, using `AuthoringPlan` for safe deterministic atomic
publication. Existing versioned MDX bytes are immutable: conflicting writes
fail by default; check mode returns exact missing/different owned paths
without changing files. Index and current-version category metadata are
regenerable. Unrelated and older-version pages/category files remain untouched.
Index generation includes historical `vN[.N...]` directories already present
in the chosen output tree, with Ruby's numeric version discovery and
alphabetical schema/version card ordering. Category positions use Ruby's
descending **lexical** current-version ordering, not numeric ordering.
Explicit opt-in replacement is for isolated oracle output or deliberate
current-version regeneration only; never an excuse to rewrite old versions.
Single-file overrides must be `.md`/`.mdx`, cannot replace the index or name
an older version. Within any version directory they must exactly equal the
selected schema's canonical path; they cannot impersonate another schema.
They cannot use `replace_current` to overwrite an arbitrary
published page. Plans detect changes to the historical page-name set before
publication; re-plan instead of losing new history. Unsafe/symlink/directory
output collisions fail before any writes.

Dotfile historical pages are ignored, matching Ruby's glob. Other historical
page names must use the same safe identifier alphabet as schema files; unsafe
names are explicit errors. Plans created without an output root are valid for
inspection or fresh trees; an index plan must be rebuilt with its destination
to retain already existing history.

The proposed manual `bin/chore gen schema-docs` wrapper intentionally requests
`--replace-current`; its fail-on-change path and CI use non-writing `--check`.
Historical pages remain protected in both modes. The byte-locked legacy
provenance URL still points to the Ruby source: replacing it after Ruby
retirement is a separately reviewed Stage 6 artifact transition, not a parity
fix or a reason to rewrite historical MDX now.

The eventual unified command is
`udb generate schema-docs [--schemas DIR] --out DIR [--check]`, with bundled
schemas by default. The standalone module entry point and API remain usable
while the parent integrates shared CLI, installed checks and CI. This lane
does not modify those shared files or release/versioning policy.

## Public API and standalone invocation

```python
from udb.schema import SchemaStore
from udb.schema_docs import SchemaDocumentation, generate_schema_docs

docs = SchemaDocumentation()  # bundled schemas
mdx = docs.render("config_schema.json")
plan = docs.plan("generated-schema-docs")
changed = plan.apply("generated-schema-docs")
assert plan.apply("generated-schema-docs", check=True) == ()
limits = plan.notices

custom = SchemaDocumentation(SchemaStore("my-schemas"))
custom.plan("custom-docs").apply("custom-docs")
drift = generate_schema_docs("generated-schema-docs", check=True)
```

Until unified CLI integration:

```sh
python -m udb.schema_docs --out generated-schema-docs
python -m udb.schema_docs --schemas my-schemas --out custom-docs --check
python -m udb.schema_docs --out pages --schema config_schema.json --output-file config.md
```

Exit codes are 0 for successful generation or clean checks, 1 for check
drift, and 2 for input/output errors. `--no-index` retains an existing index.
`--replace-current` is an explicit current-canonical-page replacement;
`--diagnostics` emits exactly one JSON document with `status`, `check`, `paths`
and complete located `notices`, or an error document on input/output failures.
Human progress lines never share that stdout. Located warnings/errors remain
on stderr; unavailable/broken/short stdout writes are explicit exit-2 I/O
errors (an unwritable stream cannot carry its own JSON error). The permanent
CLI patch delegates to this same implementation and exposes `--diagnostics`.
The API warns
once per instance with `SchemaDocsProjectionWarning`, and exposes immutable
notices on the instance and plan. Generation requires no installed renderer.

## Evidence and acceptance

The checked-in capture utility invokes the real Ruby all/single entry points
under the shared Ruby lock and `mise exec --no-deps`. A capture manifest records
schema/source and generated-artifact SHA-256 hashes. Python tests compare
the complete output set and exact bytes, not a selected substring or an
updated tracked-doc baseline. Historical differences are recorded separately.
Focused supplied-store tests cover references, examples, category/index,
history, immutability, unsupported inputs, checks and offline operation.
Installed-wheel and Docusaurus compilation checks are parent-owned gates,
not implied by a source-tree oracle pass.

The original 28 current, 36 history-seeded and 7 caller-supplied artifacts and
60 sort cases remain unchanged. Additional full-page Psych fixture captures
exercise examples and numeric enum/const/reference rendering, while the scalar/
collection corpora compare every byte against raw native `YAML.dump` output
and metadata against Ruby `to_s`; no goldens are generated by Python.

## Observed historical baseline (not repaired)

The isolated history-seeded **Ruby** capture contains 36 artifacts. Compared
with tracked `doc/docs/schemas`, it adds `v0.2/ext_schema.mdx`,
`v0.4/schema_defs.mdx`, and `v0.4/_category_.json`, and changes `index.mdx`
and the category positions in `v0.1`, `v0.2` and `v0.3`. Existing current and
old-version MDX bytes do not change. This is the deliberate-schema/legacy-CI
drift, distinct from Python parity. No schema versions or tracked schema
documentation were modified in this lane. Fresh Python output equals all
28 current Ruby artifacts exactly; the custom supplied-store oracle and
history-seeded oracle likewise use complete exact-byte comparisons, with
**no incidental-difference allowance, normalization or ignored files**.
