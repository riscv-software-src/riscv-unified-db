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
bin/setup    # one-command setup: installs mise, all tool versions, all dependencies,
             # git hooks, and walks through C++ toolchain configuration
bin/doctor   # verify the environment is correctly set up (run after bin/setup)
```

## Common Commands

```bash
./bin/regress -h              # help on running regression tests
./bin/generate -h             # help on generating content
./bin/chore -h                # help on repository development chores

./bin/regress --list          # list all regression tests
./bin/regress --tag smoke     # run smoke tests (fast subset)
./bin/regress --tag unit      # run unit tests
./bin/regress --all           # run full regression suite
./bin/regress -n <test-name>  # run a single named test
./bin/regress -n regress-udb-unit-test --matrix=test=conditions  # run a single matrix variant

./do test:idlc:unit           # run IDL compiler unit tests
./do test:udb:unit            # run UDB library unit tests
./do test:sorbet              # run Sorbet type checks
./do test:idl CFG=_           # type-check IDL for a config (also: rv32, rv64, qc_iu)
./do test:inst_encodings      # check instruction encoding conflicts
./do test:schema              # validate all arch files against schemas

./do gen:arch                 # generate arch files from layout templates
./do gen:resolved_arch CFG=_  # resolve a configuration (default: "_" = unconfigured)
./do gen:schemas              # resolve schema files to gen/schemas/

./bin/generate manual -v all -f html          # generate HTML ISA manual
./bin/generate ext-doc -h                     # generate extension documentation
./bin/udb-gen isa-explorer -t ext-browser -o gen/isa_explorer  # ISA explorer

./bin/pre-commit              # run pre-commit checks manually
```

## Architecture

### Repository Structure

- `spec/std/isa/` — RISC-V standard data (extensions, instructions, CSRs, profiles, etc.)
- `spec/custom/isa/` — Non-standard/custom extensions
- `spec/schemas/` — JSON schemas for all data types
- `cfgs/` — Architecture configurations used by backends
- `backends/` — Artifact generators (documents, simulators, etc.)
- `tools/ruby-gems/` — Ruby gem libraries
- `tools/test/` — Test infrastructure
- `bin/` — Wrapper scripts; run natively with mise-managed tools (container is only used for the RISC-V cross-toolchain via `bin/chore container`)
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

Some files are auto-generated from `.layout` ERB templates (e.g., AMO variants, HPM counters, PMP registers). Run `./do gen:arch` to regenerate them. Auto-generated files are read-only (chmod 0444).

### Configurations (`cfgs/`)

A configuration YAML specifies which extensions are mandatory/optional and sets parameter values. The special `_` config is the fully unconfigured architecture. Backends use configs to customize output.

### Ruby Library (`tools/ruby-gems/`)

Four gems:
- **`udb`** — Core database API (`Udb::Architecture`, `Udb::Resolver`, and all object types in `lib/udb/obj/`)
- **`idlc`** — IDL compiler (parser, type checker, AST, passes)
- **`udb-gen`** — Generator backends
- **`udb_helpers`** — Shared utilities

The `Udb::Resolver` class is the entry point: `resolver.cfg_arch_for("rv64")` returns an `Architecture` object. The `Architecture` class provides methods like `extensions()`, `instructions()`, `csrs()`, `profiles()`, etc.

### ISA Description Language (IDL)

IDL is a domain-specific language with a C/Verilog-like syntax used to formally describe instruction behavior, CSR semantics, and other semantics difficult to express solely in YAML. The IDL language documentation is in `doc/docs/idl`. IDL code appears primarily in `operation():` fields of instruction YAML files and other fields with tags that end in "()".

IDL is compiled by the `idlc` gem. The compiler performs type checking and can generate AsciiDoc documentation, option analysis, and other passes. Key types: `Bits<N>`, `XReg` (alias for `Bits<MXLEN>`), `Boolean`, enums, bitfields, structs.

### Backends (`backends/`)

Each backend has a `tasks.rake` file that registers Rake tasks. Key backends:
- `cfg_html_doc` — HTML documentation for a specific config
- `cpp_hart_gen` — C++ ISS (Instruction Set Simulator) hart model
- `prm_pdf` — Processor Requirements Manual PDF
- `instructions_appendix` — Instruction appendix AsciiDoc/PDF

### CI / Pre-commit

Pre-commit hooks run automatically on `git commit`. They include YAML/JSON linting, schema validation, and prettier formatting. If a hook auto-fixes files, `git add` the changes and recommit.

CI is split into PR tests (`ci_stage: pr`) and merge-queue deployment tests (`ci_stage: merge_queue`). Test definitions are in `tools/test/regress-tests.yaml`.

## Contribution Notes

- Squash merge policy: PR title/description becomes the commit message
- Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0) style (not enforced)
- PRs require approval from a maintainer
- Link PRs to issues with `Fixes #<number>` or `Closes #<number>` in the PR description
- All PRs must pass `./bin/regress --all`

### Pull Request Message Style

Because PRs are squash-merged, write the PR title and description as the final commit message.

- Keep the title short and specific; use a conventional prefix when it helps.
- Keep the body to one to three concise paragraphs explaining what changed and why.
- Avoid AI-generated boilerplate: long summaries, exhaustive change lists, validation logs, large tables, and copied diffs.
- Mention validation only when it is non-obvious, special, or cannot be inferred from CI.
