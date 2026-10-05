<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->
# UDB Documentation Site Plan

> [!NOTE]
> This planning snapshot predates the unified `udb` command and mise developer
> tasks. Command names below are historical design inputs, not current usage.

This site will document the entire riscv-unified-db monorepo. It will include at least the following (not necessarily in this order):

- What is UDB?
- Getting started for users
- Getting started for developers
- Getting started for specification writers
- Concepts (configurations, data pipeline, conditions)
- Description of the database (under spec/)
- IDL language (starting from doc/idl.adoc)
- Documentation for each tool and backend
- Links to the latest generated artifacts from UDB (like the current pages site does)

The sources of the documentation may live with their component in the monorepo, but there should be a Docusaurus `plugin-content-docs` path (or symlink under `doc/`) pointing to it so that all documentation is reachable from the site.

As much as possible, documentation should be pulled from source files to avoid documentation becoming stale. For example, the schema documentation should be generated from the schema files (with perhaps a high-level overview written in the markdown docs). API/CLI documentation should also be generated.

The site should use Docusaurus. It should be visually appealing and uncluttered. It should include good search features and SEO. As part of this process, all existing AsciiDoc documentation should be converted to Markdown.

This documentation will eventually replace the existing GitHub Pages site.

---

## What is UDB?

At its core, UDB is a database containing the RISC-V specification. Around that, we also provide tools to work with the data, generate artifacts like documentation and collateral for downstream projects, and validate the data itself.

### Current state

Still in development, though it is usable for many use cases [say which ones].

---

## Getting started for users

Ways to interact with UDB:

- udb gem
    - CLI
    - JSON RPC
- udb-gen gem
- idlc gem
    - CLI
    - Using the AST representation
- Using raw data (briefly describe that resolved data is what users want).

The udb gem is used to query database data and validate configuration files.

The udb-gen gem is used to create artifacts (like documentation) using udb data.

Explain the `bin/` wrapper scripts: `bin/udb`, `bin/udb-gen`, `bin/generate`, `bin/regress`, `bin/chore`.

Explain the difference between "raw" and "resolved" data, with a concrete example.

---

## Getting started for developers

### Setup

Include some setup information that currently exists in the top-level README.

### FAQ / How-Do-I

Incorporate doc/HOW-DO-I.adoc as a nice FAQ page.

### Contributing

Info from CONTRIBUTING.adoc.

### Writing a new generator

Explain how to add a new generator subcommand to `udb-gen` and expose it via `bin/generate`: how to get a `ConfiguredArchitecture` object, how ERB templates work, and how to use `udb_helpers`.

---

## Getting started for specification writers

Provide examples of how to add extensions, instructions, CSRs, etc.
Working on GUI tools to help with this task.
Show how to validate the data.
Show how to produce a spec.

Incorporate doc/data-templates.adoc.

---

## Concepts

### Configurations

RISC-V is a highly configurable specification. It consists of a small base specification upon which you can add hundreds of extensions, each of which may have its own implementation options.

Thus, most of the tools work with a _configuration_ to understand which parts of the spec are relevant to a task. UDB has three types of configurations:

- **Full configurations** exhaustively specify all options for a design, including extensions and implementation options (called parameters).
- **Partial configurations** specify some requirements but leave many choices unmade. Partial configurations can be used, for example, to describe RISC-V profiles.
- **The "unconfig"** (`_`). This special config just means that nothing is selected — you can think of it as an alias for the entire RISC-V specification.

UDB includes tools to validate configuration files, ensuring that the listed extensions do not conflict with each other and/or that all required parameters have values in the allowed range. You can also verify that a full configuration is _compatible_ with a partial configuration — e.g., that a full configuration is compatible with the RVA23 profile.

Document the configuration file format (cfgs/), including:
- Full configs (with `implemented_extensions` and all params)
- Partial configs (with `mandatory_extensions`)
- Overlays (`cfgs/NAME/arch_overlay/`)
- Reference the example configs: `cfgs/example_rv64_with_overlay.yaml`, `cfgs/mc100-32-full-example.yaml`

### The data pipeline

Describe the flow from `spec/` → overlay merge (JSON Merge Patch) → `$inherits`/`$remove` resolution → `gen/` → `ConfiguredArchitecture`. Reuse the diagram from `spec/std/isa/README.adoc`.

### Conditions

Special documentation of the conditions system is warranted. Incorporate doc/schema/conditions.adoc.

---

## Description of the database (under spec/)

The contents of `spec/std/isa` form a relational database. First-level directories are "tables" and YAML files under those directories are "rows". Columns are the data in the YAML files. Subdirectories under the first-level directory are not relevant — they are only to organize things for humans. In terms of the database, all the files are flat.

All tables should be explicitly enumerated. The full list is:

| Table | Description |
|---|---|
| `csr` | Control and Status Registers |
| `exception_code` | Synchronous exception codes |
| `ext` | ISA extensions |
| `inst` | Instructions |
| `inst_opcode` | Instruction opcode definitions |
| `inst_subtype` | Instruction encoding subtypes |
| `inst_type` | Instruction encoding types |
| `inst_var` | Instruction decode variables |
| `inst_var_type` | Instruction decode variable types |
| `interrupt_code` | Asynchronous interrupt codes |
| `isa` | Global IDL source files |
| `manual` | External manual references |
| `manual_version` | External manual version references |
| `param` | Configuration parameters |

| `profile` | RISC-V profiles |
| `profile_family` | Profile families |
| `profile_release` | Profile releases |

| `register_file` | Register file definitions |

Consider generating each table's documentation from a README in the table's directory.

YAML files follow a schema enforced by JSON Schema. The schemas should be documented on this site, and the documentation should be generated automatically from the schema files themselves. We need to improve the schema files to add examples and better descriptions for this purpose.

### Custom overlays

Like the RISC-V spec itself, UDB is structured to enable customization of the database. Data files can be overlaid to change behavior and/or add new features (like instructions). Examples exist in `spec/custom/`.

### Data resolution

Describe what occurs during the data resolution step, including:
- The `$inherits` operator
- The `$remove` operator
- IDL → YAML conversion

### Schema

Put the schema documentation here. There should be a short overview and the rest should be generated from the schema files. Incorporate doc/schema/versioning.adoc.

---

## IDL Language

Starting from `doc/idl.adoc` (already comprehensive). Sections:

- Overview and design goals
- Data types (Bits<N>, Boolean, enumerations, bitfields, structs, arrays)
- Literals (integer, array, string)
- Operators (full precedence table)
- Variables and constants
- Type conversions and casting
- Builtins
- Control flow
- Functions (including generated and builtin functions)
- Scope rules
- Sources (how IDL appears in .isa files, instruction operations, CSR definitions)

Also document:
- The `idlc` gem as the IDL compiler
- The `idl_highlighter` gem for syntax highlighting

---

## Documentation for each tool

Should include overview, usage details, installation details (if relevant), and details for developers/contributors.

Tools to document:

**Published Ruby Gems** (located in `tools/ruby-gems/`):

| Tool | Location | Description |
|---|---|---|
| `udb` gem | `tools/ruby-gems/udb/` | Main database interface library; CLI and Ruby API |
| `udb-gen` gem | `tools/ruby-gems/udb-gen/` | Artifact generation tool; each generator is a subcommand |
| `idlc` gem | `tools/ruby-gems/idlc/` | IDL compiler; CLI and AST API |
| `udb_helpers` gem | `tools/ruby-gems/udb_helpers/` | Template helpers used by generators |
| `idl_highlighter` gem | `tools/ruby-gems/idl_highlighter/` | Syntax highlighting for IDL |

**Internal Build Tools** (located in `tools/internal-gems/`):

| Tool | Location | Description |
|---|---|---|
| `schema_doc_gen` gem | `tools/internal-gems/schema_doc_gen/` | Generates schema documentation (not published to RubyGems) |

**Command-line Tools**:

| Tool | Location | Description |
|---|---|---|
| `bin/generate` | `bin/generate` | Language-agnostic wrapper exposing all generators (Ruby via `udb-gen`, Python tools, etc.) |
| `bin/regress` | `bin/regress` | Regression test runner |
| `bin/chore` | `bin/chore` | Repository maintenance tool |

---

## Generators

Generators produce artifacts from UDB data. They are invoked via `bin/generate` (the language-agnostic wrapper) or directly via `udb-gen` (the Ruby interface). Explain all the generators that exist, show examples of what they produce, and how to invoke them.

| Generator | `bin/generate` subcommand | What it produces |
|---|---|---|
| `cpp_hart_gen` | `bin/generate cpp-hart-gen` | C++ ISS (Instruction Set Simulator) hart implementation |
| `c_header` | `bin/generate c-header` | C encoding header (used by Spike, ACTs, Sail) |
| `go` | `bin/generate go` | Go instruction/CSR definitions |
| `sverilog` | `bin/generate sverilog` | SystemVerilog decode package |
| `indexer` | `bin/generate indexer` | Search index for the UDB documentation website |
| `instructions_appendix` | `bin/generate instructions-appendix` | AsciiDoc instruction appendix |
| `prm_pdf` | `bin/generate prm-pdf` | Programmer's Reference Manual PDF |
| `profile` | `bin/generate profile` | Profile documentation |

Note: The subcommand names above are illustrative — use the actual `bin/generate --help` output as the authoritative reference.

---

## Links to generated artifacts

Prominent link (external, opens in new tab) to the latest generated RISC-V specifications produced by UDB. This replaces the role of the current GitHub Pages site.
