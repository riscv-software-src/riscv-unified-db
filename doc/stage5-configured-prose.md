<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5 configured prose: contract and oracle

## Boundary (specified before implementation)

The frozen migration oracle retains a **restricted ERB-to-native adapter**; it is
not a Ruby interpreter and is not used by production consumers. Live standard
YAML/layout sources use the existing bounded layout engine's
`{{ expression }}`, `{% if/elif/else/endif %}`, and `{% for/endfor %}` syntax.
Configuration inputs are captured, typed data; neither native rendering nor
the adapter evaluates Python/Ruby source or reopens a source directory.
The semantic service supports retained extension AsciiDoc/PDF and C/SV/Go/C++
consumers. It does not implement standalone manual/config/appendix/profile/PRM
or Explorer products, or the retired shared document framework. Retiring those
products does not remove configuration-sensitive instruction/CSR content needed
by retained extension documentation or exception-name inputs needed by generators.
Python conversion is feasible for the complete captured source grammar and
structured-name boundary; no Ruby fallback or semantic-support retirement is
required. Unsupported inputs fail explicitly rather than leaking template syntax
or silently omitting configured content. The original ERB sources and Ruby
outcomes remain immutable in the reviewed test corpus.

The accepted `d6b06ca3` snapshot actually contains **128**, not 135,
ERB-bearing standard YAML records: **111 CSR and 17 instruction** records,
with **255 scalar values** (254 descriptions and one `access_detail`),
**1,746 tags**, and **49 byte-distinct tag bodies**. There are no additional
custom YAML records with ERB in this snapshot. The earlier inventory's 135
is not a test denominator: missing seven records cannot be invented or
counted as supported. The frozen corpus records every path, scalar path,
template, and source digest; tests require exact inventory equality.

### Deliberately supported legacy grammar

- Literal text, `<%= expression %>`, `<% if/elsif/else/end %>`,
  `<% unless/end %>`; optional leading/trailing `-` follows Tilt's `trim: "-"`.
  Whitespace and newlines are observable output, not normalized.
  Tilt selects Erubi: its truthy `trim: "-"` removes a standalone statement's
  indentation and following `[ \t]*\r?\n`, with or without hyphens. Statement
  hyphens have no extra effect off standalone lines. Expression indentation
  remains; an expression's trailing `-` removes its following whitespace/newline.
  Ruby parses CRLF inside Erubi's generated string literals as LF. The adapter
  implements these rules before native parsing, not with native trim flags.
  Evidence includes 347 untouched real Tilt outcomes beyond the original
  inventory, including the review's 18 cases.
- `ext?(:NAME)` and `ext?(:S, "> 1.9.1")`, unary `!`, comparisons,
  integer subtraction, parentheses, constants, and bounded ternary selection
  (`ext?(...) ? 2 : 1` and the virtual-address selector below). Python-only
  literals/keywords, conditional-expression spelling and chained comparisons
  are rejected by the legacy adapter; native syntax remains a distinct API.
- `possible_xlens.include?(32)`, including the exact
  `possible_xlens.include?(32) ? 32 : 64` width selector independently captured
  by the generic-generator name-mutation oracle.
- `(CACHE_BLOCK_SIZE.bit_length - 1)` and
  `[PMP_GRANULARITY, PMA_GRANULARITY].min`, compared with `<=` or `>`.
- Local `va_size = ext?(:Sv57) ? 57 : (ext?(:Sv48) ? 48 : 39)`,
  `va_size`, `va_size-1`; local assignment is retained, not discarded.
- `implemented_exception_codes.sort_by { |code| code.num }.each do |code|`
  and the corresponding interrupt loop (including observed spacing variants);
  `code.num` and `code.name` interpolation.
  These loops and `va_size` assignment are top-level only; loop bodies allow
  only literal text and the two code-field interpolations. This matches every
  occurrence in the frozen source inventory.

All other directives, calls, attributes, delimiters, or expressions are
rejected, including in inactive branches. Errors retain the captured scalar,
its field path, defining YAML span when available, the exact offending tag,
and observed configuration facts. There is no arbitrary evaluation fallback.

### Configuration semantics

Ruby `CfgArchitecture#erb_env` binds supplied recognized parameters as
constants (even when synthetically supplied outside their availability scope),
available unsupplied parameters to `:unknown`, and does not bind unavailable
unsupplied parameters. Unknown comparison with an integer
is false; unknown arithmetic/bit length fails; an unavailable constant raises
`NameError`. These are distinct states, not a default value or solver guess.
Malformed values preserve the corresponding captured Ruby error in the recorded
matrix, while the Python error provides structured provenance. Unobserved
operand types produce explicit Python diagnostics, without an invented Ruby
message or exception-class parity claim. Upstream `CapturedFailure` inputs retain
the supplied exact class and message.

Ruby `ext?` is false in `_`; in partial configurations it tests explicit
mandatory requirements (all satisfying versions meet the requested version);
in full configurations it tests implemented versions. This is **not**
Python's general possible-presence query. Reuse existing version/condition
APIs; do not introduce a second solver.

Ruby `possible_xlens` depends on MXLEN and the known/prohibited S/U/H modes
and their SXLEN/UXLEN/VSXLEN/VUXLEN sequence values. Unknown mode widths
remain possible in partial configurations.

`ProseInputs.from_database(database, configuration)` projects declarations
using existing version and condition evaluation; it does not solve global
requirements, infer implementation, or certify architectural validity.
`from_architecture` has the same projection policy. Restricted partial
configurations (prohibitions, closed extension lists, extra requirements) and
unresolved IDL scope conditions explicitly require caller-captured availability
instead of an approximate answer. General symbolic projection is **not
implemented** here; use the existing architecture machinery to supply facts.
Supplied parameters override availability, matching Ruby's constant binding.

Code loops retain integer ordering and the original code identifier (`name`,
not `display_name`). Structured exception-name consumers receive explicit
`num`, rendered `name`, `var`, and wrapper-extension provenance; no ERB or
unresolved structured name may escape into generator JSON.
`resolve_exception_records(records, inputs)` preserves caller selection and
order, emits one `{num, name, var, ext}` row per extension (`ext` is a string),
and does not deduplicate. It is a caller-owned selection API, not the database
selection policy. Retained C/SV/Go wrappers must use
`resolve_all_exception_records(database, inputs)`: it derives **all** code rows
from the database in extension-major order, including transitive requirements of
matching extension versions. XLEN relations are added after recursive expansion,
matching Ruby's phase order: their direct extension mentions count, but those
extensions' requirements are not expanded again. For example, H-defined guest-fault codes appear
in H, S, Sm and U rows. This matches all raw wrapper captures, including full
configurations with absent extensions; configuration facts only render names.
The downstream Python decoder still owns sorting/deduplication.
`resolved_exception_names(inputs)` means **config-available** codes in numeric
order, and is not a substitute for the all-code wrapper. Four additional real
wrapper captures exercise controlled, unrendered templated-name mutations in
database records; the live standard code names themselves currently contain no ERB.

## Frozen artifact oracles

Before production implementation, capture real Ruby Tilt rendering of every
scalar in the above inventory for `_`, `rv32`, `rv64`, `qc_iu` (including
its overlay), and explicit full/H/parameter variants. Include the source
configuration, available/unavailable parameter facts, selected extension
facts, code lists, complete output **or exact exception class/message**,
and a source SHA-256. Do not count a Ruby failure or adapter rejection as an
output parity pass. Native rendering tests use the same captured typed inputs.

The dedicated Ruby regenerator is a development-only test oracle; invoke
under the original shared Ruby lock and `mise exec --no-deps`, with all
scratch/generated files beneath this worktree. Production/install runtime
never imports it or starts Ruby. Frozen data is consumed without Ruby.
Independent Ruby defects are recorded explicitly, with exact expected-side
corrections and separate reproduction; uncorrected original outputs/errors
remain in the corpus.

The original corpus has **14 configurations × 255 scalars = 3,570 outcomes**:
**3,484 direct raw-Ruby text comparisons**, **42 corrected/substituted oracle
text comparisons**, and **44 explicit errors**. Neither those errors nor the
42 substitutions are raw-Ruby output parity. The matrix includes mixed-width
H/S, Sv57/Sv48/Sv39 and the observed extension branches, both cache-granularity
inequalities, unknown/unavailable constants, malformed cache types, and
unknown/malformed/unavailable minimum operands. Fourteen separate real Ruby
structured exception-record captures cover the generator-name boundary.
`tag_inventory` records all 49 exact bodies and their occurrence counts.

Only three `*cause.CODE` scalars differ from raw Ruby in each configuration:
33 original substitutions concern the interrupt-accessor/undeclared-extension
behaviors; **three** concern empty tables from the unsatisfiable synthetic
`h64-mixed-sv57` declaration; **six** replace real Ruby Z3 type errors in the two
malformed synthetic cache configurations. The last nine are not evidence of
either advertised Ruby defect. The substitutions use the existing concrete/possible
code predicate and actual interrupt collection on the oracle object only, and
are separately labelled semantic projections, not successful raw generation.

An independent **unpatched** Ruby witness validates the existing
`cfgs/mc100-32-full-example.yaml` (`valid? == true`, no reasons). It reports
`ext?(:Smdbltrp) == false`, the DoubleTrap concrete predicate false, but its
solver availability true and DoubleTrap in the raw exception table. The raw
interrupt accessor again returns that exception table. This is genuine
valid-processor evidence for the two defects; **MC100 does not reproduce VScall
inclusion** (H's prerequisites conflict with its selected Sm version).
The separate six-configuration supplement retains all 255 scalars per config:
five synthetic cache boundaries and this valid MC100 example. It adds 1,508
raw-equal texts, 18 defect projections and four errors. Thus the original and
supplement together have 5,100 outcomes: **4,992 raw equal + 60 substituted +
48 errors**. The five cache shapes are explicitly Ruby-invalid declarations,
not certified processors; they cover equality, ±1 and both minimum operands.
Seven executable bit-length/minimum mutations are killed by raw cache captures.

Original outputs/errors are retained unchanged; a frozen digest protects the
entire original raw archive. No YAML, Ruby library, schema or general solver
implementation is modified.
NameError messages retain Ruby's exact randomized anonymous-class address in
the archive; Python diagnostics use the stable unavailable constant name rather
than fabricating a Ruby object address. Other captured parameter-error messages
are compared exactly.

## Native source cutover

The source cutover replaces these 255 embedded scalar templates and their
originating layouts with native syntax, changing only template tags, not prose.
Production consumers use `render_native`; the legacy adapter and Ruby-specific
unknown/error compatibility policy remain only for the frozen differential/error
archive and its runnable regression coverage. CSR code tables use native loops over
prepared rows from typed code records, cache constraints use named typed derived
inputs, and `va_size` is an explicit selected-width input. The precise authoring
patch boundary is **31 handwritten YAML files and seven layouts**, regenerating
**97 layout-owned YAML files** rather than editing generated read-only files directly:

| Originating layout                | ERB-bearing generated records |
| --------------------------------- | ----------------------------: |
| `csr/Zihpm/mhpmcounterN.layout`   |                            29 |
| `csr/Zihpm/mhpmcounterNh.layout`  |                            29 |
| `csr/Zihpm/mhpmeventN.layout`     |                            29 |
| `csr/I/mcounteren.layout`         |                             1 |
| `csr/S/scounteren.layout`         |                             1 |
| `inst/Zalrsc/lr.SIZE.AQRL.layout` |                             4 |
| `inst/Zalrsc/sc.SIZE.AQRL.layout` |                             4 |

Paths in this table are relative to `spec/std/isa`. Every YAML path and scalar
path is listed in the frozen corpus; the handoff includes the exact
layout-to-record mapping.

Stage 2 authoring and Stage 5 configured prose share native delimiters but are
**different evaluation stages**. In a `.layout`, emit the Stage 5 tag through
the existing Stage 2 string interpolation, e.g.
`{{ "{%- if extensions.H -%}" }}` or `{{ "{{ params.MXLEN }}" }}`.
Stage 2 emits those strings literally; only `render_native` subsequently
interprets them. Do not place unquoted configured tags directly into authoring
layouts. A dedicated two-stage test verifies this boundary without adding a
raw-block language, second renderer, or source YAML edits.
Native loops consume bounded prepared scalar rows (the existing layout engine
does not iterate arbitrary objects). Typed code records remain at the API
boundary; row preparation reuses that engine. No second renderer is added.
The shared CLI, installed checker, CI inventory, and schemas remain parent-owned
integration surfaces. A repository gate rejects ERB in live architecture YAML and
layout sources, while the immutable migration fixtures retain the original ERB text.

## Standalone API

```python
from udb import Configuration, Database
from udb.prose import CapturedProse, ProseInputs, native_prose_values, render_native

database = Database.bundled().resolve()
inputs = ProseInputs.from_database(database, Configuration.builtin("rv64"))
scalar = CapturedProse.from_record(database, database.csr("stvec"), "fields", "BASE", "description")
text = render_native(scalar, native_prose_values(scalar, inputs))
```

`ProseError.diagnostic` retains the scalar and captured YAML text/span, field
path, exact tag, configuration text, observed input values and their defining
spans, plus a legacy error class when applicable. Neither API reads a path.
Production Python contains no Ruby command, import hook, or arbitrary eval.

## Integration and fixture maintenance

`gen/handoff/prose-installed.diff` is unapplied; it uses the all-code API, not
config-filtered rows. Parent must run installed/package gates after integration.
No extra CI job is needed: `regress-python-unit` already discovers these tests.
The redundant original proposal is archived as `prose-ci-original.diff`;
`prose-ci.diff` is deliberately empty and must not be applied. Raw stdout/stderr,
payloads, witness scripts and resolver scratch remain under `gen/handoff`.

Fixture JSON has per-file REUSE `.license` sidecars. Artifacts containing copied
standard specification prose carry both BSD-3-Clause-Clear and CC-BY-4.0 plus
UDB/Qualcomm/ISA-manual contributor attribution; synthetic whitespace/name/query
probes do not claim to contain specification prose. Prettier formatting must
leave parsed raw values unchanged.

`test_exact_source_inventory` gates the migration manifest's 255 scalar paths,
native fields, regenerated layout outputs, and the absence of ERB from live
architecture sources. The immutable ERB corpus, digest, legacy differential/error
tests, and synthetic probes remain frozen-archive regressions. Native source parity
assertions render every converted field across the original and supplemental
configuration matrices. The qc_iu authoring generator is a separate lane, not an
omitted configured-prose scalar or a reason to reduce this denominator.
