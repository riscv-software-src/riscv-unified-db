<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5: configuration C and SystemVerilog headers

## Reviewed legacy contract

This slice ports `udb-gen/lib/udb-gen/cfg_header_base.rb`, `defines.rb`,
`common_opts.rb`, and `generators/cfg_{c,svh}_header/generator.rb`. The
`test/test_cfg_headers.rb` tests and tracked
`tests/golden/mc100-32-full-example.golden.{h,svh}` are byte-level oracles.
The input is `cfgs/mc100-32-full-example.yaml`, whose declared name is
`MC100-32-Full`, not its filename. No golden changes are authorized here.

Only **fully configured** configurations are supported: Ruby explicitly rejects
unconfigured `_` and partial configurations (including `rv32` and `rv64`).
Extension macros represent the explicitly implemented versions, not a transitive
closure or an arbitrary solver model. Versions must exist in the selected
database. The Python implementation additionally checks the public configured
architecture's validity, so incomplete, inconsistent, unknown, or undecidable
inputs fail explicitly; it never supplies defaults or guesses values.

Output conventions, shared by both languages:

- The comment prelude, including the historical `udb-gen` attribution, section
  order, blank lines, and final newline are preserved byte for byte.
- Guards are `UDB_CFG_<CONFIG>_H` / `_SVH`. Uppercase the declared configuration
  name and replace each non-ASCII alphanumeric character with `_`; unlike string
  values, do not collapse or trim guard underscores.
- Sort implemented extensions by uppercase name. Emit empty `NAME_SUPPORTED`
  and `NAME<version>_SUPPORTED` macros; version formatting uses the public RISC-V
  version representation, preserving explicitly written patch components.
- Sort parameter names lexically and prefix them with `UDB_`. True emits an empty
  macro; false emits nothing. Integer zero is an integer, not a false boolean.
  Integers emit a value macro and a presence macro suffixed with the decimal value.
- String values emit only a suffixed presence macro. Uppercase, replace
  non-ASCII alphanumerics with underscores, collapse consecutive underscores,
  and strip leading/trailing underscores. Do not interpret strings as templates.
- Boolean arrays emit each true element's zero-based index in input order.
  Integer arrays emit unique values sorted numerically. String arrays sanitize
  first, then deduplicate and sort lexically. Empty arrays emit nothing.
  Python rejects heterogeneous arrays instead of silently ignoring them.
- C uses decimal integer values, `#define`, block comments, and
  `#endif /* GUARD */`. SV uses backtick directives, line comments, and
  `` `endif // GUARD``. SV integer values are uppercase hexadecimal with
  unsigned width `ceil(max(32, bit_length(value))/32)*32`, including 32-bit zero.

Identifiers must be usable by their target preprocessors. Empty and digit-leading
string suffixes remain valid after the parameter prefix and are preserved.
Parameters with invalid names, negative integer suffixes, prerelease version
suffixes containing a hyphen, and macro collisions fail explicitly rather than
producing broken source. These unsupported-input errors are not changes to
valid legacy artifact bytes; negative SV values also have no valid Ruby sized
hex representation. Native tools are acceptance checks, not runtime dependencies.

## Public interface and data boundary

`udb.generators.config_headers.generate_config_header(architecture, language)`
returns a complete string, using an ordinary `ConfiguredArchitecture` built by
`Database.resolve().configure(Configuration(...))`. `language` is `"c"` or `"svh"`.
It reads immutable public configuration, database, and version APIs only.

`udb generate cfg-c-header|cfg-svh-header --config CONFIG [-o FILE]` defaults to
stdout and the bundled `_` configuration (therefore an explicit unsupported
configuration error without `--config`). `-c` and `--cfg` are compatibility aliases.
Only `_`, `rv32`, and `rv64` are bundled names; custom configurations require an
explicit YAML path. No implicit checkout lookup or `arch_overlay` loading occurs.
Global `--path`, `--schemas`, `--overlay`, and `--validate` select the same data
and resolution behavior as `validate-cfg`. Output directories are created only
after successful generation. File and stdout artifacts are UTF-8 bytes with LF
newlines, independent of the locale, platform text newline handling, and
`PYTHONIOENCODING`. Input or generation errors use exit status 2 without printing
macro bytes. Output encoding, filesystem, and stdout I/O errors also have explicit
diagnostics and exit status 2; I/O failures can occur after some bytes were written.

The installed wheel and sdist must generate representative C/SV source offline
from bundled ISA data and an explicit full configuration, without Ruby, ERB,
compilers, checkout files, runtime downloads, or fallback databases.

## Acceptance and cutover

Focused tests must cover both tracked goldens; macro type, ordering, width,
version precision, and identifier rules; full/partial errors; explicit custom
databases; CLI stdout/file behavior; and C compilation / SV syntax checking.
A narrowly scoped serialized live Ruby oracle must capture complete stdout and
compare it with both tracked golden files. Frozen oracles require provenance.
Confirmed Ruby bug corrections require independent reproduction and exact
regressions; changing an old golden just to fit Python is prohibited.

Acceptance commands:

```shell
UDB_TEST_HEADER_TOOLS=1 python -m pytest -n 8 \
  --basetemp=gen/config-headers/pytest tests/python/test_config_headers.py -k "not live_ruby"
UDB_TEST_RUBY=1 python -m pytest -n 0 \
  --basetemp=gen/config-headers/pytest-ruby tests/python/test_config_headers.py -k live_ruby
```

Use `mise exec --no-deps` and the coordinator's Ruby lock for local live oracle
commands. `values.{h,svh}` are genuine frozen Ruby outputs with source/file hashes
and capture commands in `tests/python/fixtures/config_headers/README.md`.
The live negative-input regression independently reproduces Ruby's invalid
`` `define UDB_NEGATIVE 32'h-1`` and `UDB_NEGATIVE_-1`, and Ruby's silent
omission of heterogeneous arrays; Python instead rejects these unsupported
inputs. No replacement negative literal or guessed missing macro is introduced.

The `regress-python-config-headers` CI consumer now generates both full-config
artifacts through the installed Python CLI and compares unchanged goldens before
C/SV acceptance. The existing package matrix invokes
`check_python_install.check_config_headers()` for both installed wheel and sdist;
it uses explicit fixture values and bundled ISA data, checks exact artifact
hashes, and exercises actual installed stdout/file CLI paths offline.

Repository shell wrappers remain legacy: `bin/generate` dispatches header
commands to `bin/udb-gen`; `bin/chore`'s `do_gen_cfg_headers_golden()` dispatches
through `bin/bundle exec udb-gen`. Their named-config lookup and bootstrapping
policy are not part of the installed Python API. No Ruby fallback is introduced
into Python. The precise CI consumer is cut over instead of silently changing
wrapper name resolution or introducing another installation bootstrap.
Exact commands and results are recorded in `gen/handoff/headers-report.md`.
