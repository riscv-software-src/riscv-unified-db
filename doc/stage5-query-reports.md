<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Retained UDB queries, reports and fixed-bit matching

`udb.query_reports` replaces the **real** legacy report commands:
`bin/udb show extension|parameter`, `bin/udb list extensions|parameters|csrs`,
and `bin/udb disasm ENCODING`. It does not retire or wrap these Ruby callers.
Permanent installed CLI naming remains a separate integration decision.
The scoped module CLI below is available now for testing.

The implementation uses the accepted database, configuration, architecture,
condition binding and instruction-field descriptor APIs. It needs no Ruby,
Git, native UDB helper executable, network, checkout discovery or generated
architecture cache. Z3 is the accepted Python architecture dependency, not a
new solver or external command.

## Public Python interface

```python
from udb import Configuration, Database
from udb.query_reports import (
    InstructionMatcher,
    ReportBuilder,
    catalog_names,
    render_names,
)

raw = Database.bundled()
catalog_names(raw, "extension")  # raw, path-ordered names; does not resolve
resolved = raw.resolve()  # explicitly preserves the raw/resolved distinction
architecture = resolved.configure(Configuration.builtin("rv32"))
reports = ReportBuilder(architecture)

reports.extension("I").render()
reports.parameter("MXLEN").render()
render_names(reports.extensions())
reports.parameters(["Sm"]).render("json")
render_names(reports.csrs())

matcher = InstructionMatcher(architecture)
result = matcher.match("fff10093", width=32)
result.render()  # instruction names only
match = result.results[0].matches[0]
[(variable.name, variable.value) for variable in match.variables]
# [('imm', -1), ('xs1', 2), ('xd', 1)]
```

`ReportBuilder` requires an explicit `ConfiguredArchitecture`, rather than
silently converting raw inspection into configured queries. `catalog_names`
accepts raw or resolved databases without loading configurations.
`InstructionMatcher` accepts a raw/resolved `Database` or configured view;
raw input is resolved through the existing descriptor builder without mutating
it. Only a configured view can request configured selection.

Report outputs (`ExtensionReport`, `ParameterReport`, `ParameterRow`,
`ParameterListReport`) and matcher outputs (`DisassemblyReport`, `XlenMatches`,
`InstructionMatch`, `DecodedVariable`) are frozen dataclasses with tuple
collections. `ParameterListReport.to_data()` returns a fresh, mutable JSON-shaped
copy containing exactly `name`, `exts`, `description`; it deliberately does not
expose configuration values.

### Selection and ordering

- Extension detail lookup is catalog lookup, even for an unavailable extension.
  Versions preserve their declared strings and order. The instruction count
  contains direct instructions guaranteed by selecting any version, excluding
  instructions guaranteed by just the extension's requirements.
- Parameter detail lookup is also catalog lookup. The historical `Value:`
  section describes its **declared schema**, not its configured value.
  Structured detail exposes `has_configured_value` and `configured_value`
  separately. Missing extension/parameter detail returns `None`; render helpers
  preserve the native missing-name message.
  IDL-defined parameter conditions use the accepted `IdlConditionBinding`
  translator; no new evaluator or compiler is implemented here.
- Extension lists contain possible extensions, including implied extensions.
  Full configurations preserve implemented-extension declaration order;
  other configurations preserve native catalog path order.
- Unfiltered parameter lists put known values in configuration mapping order,
  then applicable unknown-value parameters in catalog order.
  Extension-filtered lists select named **possible** extensions, take direct,
  guaranteed parameters (not implied or conditionally applicable parameters),
  deduplicate and sort by parameter name. Unknown filter names produce no rows.
- Legacy CSR lists and instruction matching use the **whole catalog**, even
  for full configurations. They are not silently changed to possible objects.
  `csrs(selection="possible"|"mandatory")` and matcher `selection=...` are
  explicit alternatives. Instruction membership is evaluated for the requested
  effective XLEN; mandatory means necessary whenever that XLEN is executing.

### Matching is not operand disassembly

The default policy implements the legacy fixed-bit mask comparison, returning
**all** matches in native catalog path order, not choosing an alias or
pseudoinstruction. Ambiguity is observable through `XlenMatches.ambiguous`;
an empty match tuple is `illegal`. These flags describe fixed-bit matches,
not the complete dynamic legality of an instruction.

The default mask-only policy ignores high bits beyond each descriptor, as Ruby
does. An explicit `width=16` or `width=32` filters descriptor lengths and rejects
overflow; it does **not** infer a different width from the hexadecimal spelling
or the instruction's low bits. A 32-bit width request does not accidentally
return a compressed instruction.

Hexadecimal strings accept optional `0x`/`0X`, with at least one hexadecimal
digit. Whitespace, signs, underscores, and malformed prefixes are errors.
The programmatic API additionally accepts a nonnegative integer (not Boolean).

Effective-mode XLENs retain the native distinction from `MXLEN`: an unknown
machine width gives RV32 and RV64; `MXLEN=32` gives RV32; a 64-bit system can
still give both when lower-mode width support is unknown or variable.
The shipped `rv64` **partial** configuration consequently reports both.
An explicit incompatible `xlen` is rejected, not silently ignored.

Variable extraction uses only the validated encoding descriptor:
declared ranges are concatenated in order, then `left_shift` and sign extension
are applied. The value is a mathematical signed integer when declared signed,
not a fabricated operand string. Raw `encoded_value`, width, alias and modifiers
are also retained. Encoding-field exclusions are diagnostic metadata and never
silently remove a legacy fixed-bit match. Assembly text is returned unexpanded;
register naming, pseudoinstruction selection, reserved operand interpretation,
and instruction execution are outside this capability.

## Testing CLI

```bash
python -m udb.query_reports show extension I
python -m udb.query_reports show parameter MXLEN --config rv32
python -m udb.query_reports list extensions --config rv64
python -m udb.query_reports list parameters -e Sm -f json
python -m udb.query_reports list csrs
python -m udb.query_reports disasm fff10093 --config rv32 --width 32
```

All leaves accept `--arch`/`--path`/`-a`, `--schemas`, `--config`/`-c`,
`--config-dir`/`--config_dir`, `--arch-overlay`/`--arch_overlay`,
repeatable explicit `--overlay`, and the compatibility-only `--gen`
(accepted without generating files). An explicit `--arch`/`--path` requires
an explicit `--schemas`; the Python API does not discover a repository schema
directory. Repository wrappers therefore supply both paths. Omitted ISA input
uses packaged data and its packaged schemas.
Configuration lookup tries an existing supplied filename, an explicitly
supplied configuration directory, then packaged `_`, `rv32`, `rv64` when no
directory was supplied. No checkout configuration directory is discovered.

`--arch-overlay` is the container for the configuration's `arch_overlay`
declaration; it alone does not apply an overlay to `_`. Alternatively, explicit
`--overlay` paths apply directly and in precedence order. A config declaring an
overlay without either explicit option fails instead of discovering a checkout.

Only extension/parameter lists expose `--output`/`-o` (`-` means stdout).
Parameter lists support `--output-format`/`--output_format`/`-f`
(`ascii`, `yaml`, `json`) and `--extensions`/`-e` as separate tokens:
`-e Sm S` is two names; `-e Sm,S` is one name. ASCII headings/separators,
multiline cells and row ordering match captured Terminal::Table artifacts.
YAML and JSON preserve the entire native structure and order; equivalent YAML
quoting/layout is not promised.

Successful missing-name reports and illegal/ambiguous mask matches exit 0,
as native UDB does. Runtime/input/output errors exit 1; argparse grammar errors
exit 2. Like the native list commands, a named output is opened/truncated before
configuration resolution; a later config error can leave an empty file.
Output is short-write-safe UTF-8/LF; missing output directories are errors.
Thor-specific prefix/help shortcuts and colorization are not part of this
module test interface.

## Frozen evidence and intentional correction

`tests/python/fixtures/query_reports/manifest.json` freezes 38 genuine native
entrypoint observations and hashes all native source/config/ISA inputs.
Raw artifacts are never regenerated from Python or whitespace-normalized.
Whole human reports, ASCII tables, name lists and disassembly artifacts are
compared byte-for-byte except for the exact nine parameter-description
corrections below; entire JSON/YAML row shapes and order are compared
semantically. Captures include missing names, malformed hex, zero/overwide
opcodes, compressed ambiguity, XLEN-dependent encodings, full/partial configs,
and a configuration-declared custom overlay.

One native resolver-serialization defect is intentionally not reproduced:
the descriptions of `MUTABLE_MISA_C`, `MUTABLE_MISA_D`, `MUTABLE_MISA_F`,
`MUTABLE_MISA_H`, `MUTABLE_MISA_M`, `MUTABLE_MISA_Q`, `MUTABLE_MISA_S`,
`MUTABLE_MISA_U`, and `VMID_WIDTH` lose a blank line during Ruby resolution.
This is not a Psych parser defect. Independent Psych reads of the original and
native-resolved YAML prove that each original description ends in newline while
the native resolved artifact ends in space. The accepted Python source parser
agrees with the **original Psych read**. Consequently, each corresponding
`show parameter` report contains one indented blank line before `Value:` and is
four bytes longer than the native report. Whole-list tests substitute only those
exact frozen source descriptions (nine unconfigured rows, two full-config rows).
Their native artifacts remain untouched. No schema/data is reverted and no
private schema parser is imported.
An additional native-model corpus freezes 13 complete condition text/pretty
shapes. Human pretty conditions otherwise preserve native conventions, including
the historical `Paremeter` spelling/missing name and English ordinal array
indices; machine-readable conditions retain correct names. Pretty array indices
at or above 10^21 are explicitly unsupported rather than assigned invented words.

The targeted tests are `test_query_matching.py`, `test_query_reports_unit.py`,
`test_query_reports_cli.py`, and `test_query_reports_native.py`.
`query_reports_installed_acceptance.py` is a plain-stdlib installed gate helper:
copy it and the explicit fixtures to the package gate's acceptance area, remove
`PYTHONPATH`, hide external executables/network, and run the installed interpreter:

```bash
python query_reports_installed_acceptance.py /explicit/frozen/query_reports
```

It requires `udb` to be imported beneath that interpreter's installation prefix,
uses packaged ISA/configurations plus explicit frozen overlay/full-config files,
and forbids external process execution, network connections, executable
discovery and source-tree Database fallback during runtime assertions.
It must be run on the actual wheel, sdist installation and rebuilt wheel by the
parent package gates; source-mode validation is not installed acceptance.
