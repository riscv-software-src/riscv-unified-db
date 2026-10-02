<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# AGENTS.md

This file provides guidance to Gen AI agents when working with code in this repository.

## Overview

The RISC-V Unified Database (UnifiedDB/UDB) is a repository that holds all information needed to describe RISC-V: extensions, instructions, CSRs, profiles, and documentation prose. Tools generate artifacts (spec documents, simulators, toolchain inputs) from this data.

**Important:** This project is under rapid development. Schemas and APIs change frequently. Data in `spec/` is a work in progress.

## Setup

```bash
mise run setup   # install configured dependencies, hooks, and select a C++ toolchain
mise run doctor  # verify the prepared development environment
```

## Common Commands

```bash
uv run udb --help             # help on the installed database tool
mise tasks                    # list repository development tasks
mise run test                 # run default Python tests
mise run check                # run retained validation and quality checks
mise run check:all            # run the full regression suite
mise run check:idl -- --config rv64  # type-check IDL for one configuration
mise run check:encodings       # check instruction encoding conflicts
mise run check:data            # validate database documents against schemas
mise run check:layouts         # check generated architecture layouts for drift
mise run gen:all               # regenerate retained developer artifacts
mise run check:pre-commit      # run all pre-commit checks manually

uv run udb generate extension-document --help
uv run udb generate instruction-table --help
uv run udb author layouts --root . --check
```

Use the installed `udb` command for user/database operations and `mise run
<task>` for repository development. In a checkout, invoke the installed command
as `uv run udb ...`; do not add `PYTHONPATH`, bypass synchronization, or call a
virtual-environment interpreter directly.

## Architecture

### Repository Structure

- `spec/std/isa/` — RISC-V standard data (extensions, instructions, CSRs, profiles, etc.)
- `spec/custom/isa/` — Non-standard/custom extensions
- `spec/schemas/` — JSON schemas for all data types
- `cfgs/` — Architecture configurations used by backends
- `src/udb/` — Python package, command-line interface, IDL compiler, and generators
- `tools/dev/` — Repository development task implementations
- `tests/` — Python, native, package, editor, and integration tests
- `gen/` — Generated output (gitignored)
- `ext/` — Git submodules (riscv-isa-manual, riscv-opcodes, riscv-tests, etc.)

### Data Model

All spec data is YAML with JSON schema validation. Every file starts with:

```yaml
$schema: "<schema-name>.json#"
kind: <object-type>
name: <unique-name>
```

Key data types and their locations:

- **Extensions**: `spec/std/isa/ext/<Name>.yaml`
- **Instructions**: `spec/std/isa/inst/<Extension>/<name>.yaml`
- **CSRs**: `spec/std/isa/csr/<Extension>/<name>.yaml`
- **Profiles**: `spec/std/isa/profile/`, `spec/std/isa/profile_release/`, `spec/std/isa/profile_family/`

Some files are auto-generated from Python-native `.layout` templates (e.g., AMO variants, HPM
counters, PMP registers). Run `uv run udb author layouts --root .` to regenerate them or
`uv run udb author layouts --root . --check` to check for drift. Auto-generated files are read-only
(chmod 0444).

### Configurations (`cfgs/`)

A configuration YAML specifies which extensions are mandatory/optional and sets parameter values. The special `_` config is the fully unconfigured architecture. Backends use configs to customize output.

### Python Package (`src/udb/`)

The `udb` package is the supported database API and command-line interface. It
contains database resolution, configurations and conditions, the IDL compiler,
query/report tools, authoring support, and retained artifact generators. The
`Database` class is the main source API; resolving and configuring it produces
the architecture view used by generators and validation.

### ISA Description Language (IDL)

IDL is a domain-specific language with a C/Verilog-like syntax used to formally describe instruction behavior, CSR semantics, and other semantics difficult to express solely in YAML. The IDL language documentation is in `doc/docs/idl`. IDL code appears primarily in `operation():` fields of instruction YAML files and other fields with tags that end in "()".

IDL is compiled by the Python implementation under `src/udb/idl/`. The compiler
performs parsing, type checking, evaluation, and semantic passes used by
validation and generators. Key types include `Bits<N>`, `XReg` (an alias for
`Bits<MXLEN>`), `Boolean`, enums, bitfields, and structs.

### Generators and native runtime

Retained generators are exposed through `udb generate ...`. Repository build and
acceptance workflows are exposed as mise tasks. Notable outputs include the C++
ISS/hart model, generic C/SystemVerilog/Go encodings, configuration headers,
schema documentation, instruction tables, and extension documents.

Generator implementations live with the Python package under `src/udb/`. The
C++ hart runtime sources and native tests live under `src/udb/cpp_hart/runtime/`.

See `doc/stage5-retirements.md` for the approved document and Explorer retirements.

### CI / Pre-commit

Pre-commit hooks run automatically on `git commit`. They include YAML/JSON linting, schema validation, and formatting. If a hook auto-fixes files, `git add` the changes and recommit.

CI is split into PR checks and merge-queue deployment checks. Regression commands are mise tasks declared in `tools/dev/tasks.toml`; CI orchestration is in `.github/workflows/regress.yml`.

## Contribution Notes

- Squash merge policy: PR title/description becomes the commit message
- Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0) style (not enforced)
- PRs require approval from a maintainer
- Link PRs to issues with `Fixes #<number>` or `Closes #<number>` in the PR description
- All PRs must pass `mise run check:all`

### Pull Request Message Style

Because PRs are squash-merged, write the PR title and description as the final commit message.

- Keep the title short and specific; use a conventional prefix when it helps.
- Keep the body to one to three concise paragraphs explaining what changed and why.
- Avoid AI-generated boilerplate: long summaries, exhaustive change lists, validation logs, large tables, and copied diffs.
- Mention validation only when it is non-obvious, special, or cannot be inferred from CI.
