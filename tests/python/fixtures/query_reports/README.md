<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Native UDB query/report evidence

These artifacts are genuine output from the unmodified Ruby Thor entrypoint
`tools/ruby-gems/udb/bin/udb` on base `a67618c2`, not generated Python expectations.
The initial report and opcode corpus was captured before production Python code
was written. `manifest.json` freezes every exact command, status, raw stdout/stderr
SHA-256, ISA/custom/config input and native model source SHA-256.

The capture transport is `Open3.capture3`: `RUBYLIB` explicitly selects the owning
worktree's native UDB/IDL libraries while Bundler supplies the already-installed
dependencies. Every successful case retains stderr, including genuine native
logging and resolved-cache messages. No color/whitespace/error normalization is
applied. Custom cases have independent cache directories; `--arch-overlay` is
the container and the configuration's `arch_overlay` selects its overlay.

The initial `native-first.*` pair records the first successful normal entrypoint
probe; the manifest's `disasm-*` pairs are the parity oracles. All raw bytes,
including JSON-looking `.stdout.txt` files, must be excluded from whitespace and
formatting hooks. Attribution is supplied by `.license` sidecars, never inserted
into the captured output.

## One independently demonstrated native correction

The native YAML resolver loses a physical blank line when serializing nine
double-quoted parameter descriptions. Both Psych reading the original source and
the accepted Python source parser produce a final newline; Psych reading the
native resolver's output instead produces a final space.
`native-description-observations.json` freezes **both genuine Ruby observations**
and the original source hash. Whole-list tests apply only these nine exact
description substitutions (two occur in the full-config list). Every other field,
row, condition spelling and ordering is compared unchanged. The original raw
reports remain untouched.

`native-full-config.yaml` is an exact byte copy of
`cfgs/mc100-32-full-example.yaml`, verified against its manifest source hash, so
installed acceptance never needs a checkout.

## Reproduction

Run from the owning worktree with the original Ruby lock, existing dependency
environment, `UV_NO_SYNC=1`, and `mise exec --no-deps`:

```bash
bundle exec --gemfile /explicit/original/Gemfile ruby tests/python/capture_query_reports.rb
bundle exec --gemfile /explicit/original/Gemfile ruby tests/python/capture_query_report_descriptions.rb
```

The first utility also accepts explicit case names for bounded recapture. The
second utility captures original-vs-resolved scalar observations and copies the
full configuration from the first utility's resolved cache (or the initial
aggregate cache when present). The condition utility is
`capture_query_report_conditions.rb`; it invokes the native model caller used
by show/list and freezes 13 complete text/pretty condition shapes, including
indexed array parameters. `native-auxiliary-manifest.json` freezes hashes and
exact reproduction transports for these additional artifacts.
No utility is imported or executed by production Python.
