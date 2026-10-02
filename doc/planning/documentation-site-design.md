<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->
# UDB Documentation Site Design

> [!NOTE]
> This planning snapshot predates the unified `udb` command and mise developer
> tasks. Command names below are historical design inputs, not current usage.

This file captures the design decisions for the UDB Docusaurus documentation site,
including the landing page layout, navigation structure, and audience targeting.

---

## Target Audiences

Five distinct visitor types, each with different immediate needs:

| Audience | What they want immediately |
|---|---|
| **Curious newcomers** | "What is this project? Should I care about it?" |
| **RISC-V spec consumers** | "I want to look up an instruction / CSR / extension." |
| **Tool users** | "I want to generate a PDF spec / C header / ISS for my chip." |
| **Specification writers** | "I want to add an extension or fix data." |
| **Developers / contributors** | "I want to build a new backend or contribute code." |

The landing page must route each of these people to the right place within ~3 seconds of arriving.

---

## Landing Page Layout

### 1. Hero Section

- Project logo (`doc/udb.svg`)
- Tagline: *"The single source of truth for the RISC-V specification"*
- Three prominent CTAs:
  - **Browse the spec** → links to the generated artifacts (external, opens in new tab)
  - **Get started** → links to the getting-started section
  - **GitHub** → links to https://github.com/riscv/riscv-unified-db (external)

### 2. "What is UDB?" Summary

One short paragraph pulled from the "What is UDB?" section. Keep it to 3–4 sentences.
Link to the full "What is UDB?" page for those who want more.

### 3. Role-Based "I want to..." Cards

Four cards, each with an icon, a short description, and a primary link.
This is the most important navigation element on the page.

| Icon | Headline | Body | Link |
|---|---|---|---|
| 🔍 | **Browse the RISC-V spec** | Explore instructions, CSRs, extensions, and profiles in the latest UDB-generated specifications. | → Generated artifacts (external) |
| ⚙️ | **Generate artifacts for my design** | Use UDB tools to produce PDFs, C headers, SystemVerilog packages, and more from a processor configuration. | → Getting started for users |
| 📝 | **Contribute data** | Add extensions, instructions, or CSRs to the database. Learn the data format and validation tools. | → Getting started for spec writers |
| 🛠️ | **Build tools / contribute code** | Develop new backends, contribute to the Ruby gems, or improve the toolchain. | → Getting started for developers |

### 4. "What can UDB generate?" Showcase

A visual grid showing example outputs from the major backends. Each item has a
screenshot or code snippet and links to the relevant backend documentation page.

Suggested items:
- Programmer's Reference Manual PDF (prm_pdf)
- C encoding header snippet (generators/c_header)
- SystemVerilog decode package snippet (generators/sverilog)
- Profile documentation (profile)

### 5. Quick Links Bar

A compact row of links to the most-referenced reference pages:

- IDL Language Reference
- Schema Reference
- Configuration Format
- FAQ / How-Do-I
- GitHub Issues (external)

---

## Top-Level Navigation (Navbar)

Minimal — 5–7 items max. The sidebar handles deeper navigation.

```
[Home]  [Docs ▾]  [API Reference]  [Browse Spec ↗]  [GitHub ↗]
```

- **Home** — landing page
- **Docs** — dropdown or direct link to the docs sidebar
- **API Reference** — YARD-generated Ruby API docs (auto-generated)
- **Browse Spec ↗** — external link to the latest generated GitHub Pages artifacts
- **GitHub ↗** — external link to the repository

---

## Sidebar / Docs Structure

```
Introduction
  What is UDB?
  Current state

Getting Started
  For users
    udb gem (CLI + JSON RPC)
    udb-gen gem
    idlc gem
    Using raw / resolved data
    Python interface
    bin/ wrapper scripts
  For specification writers
    Adding extensions
    Adding instructions
    Adding CSRs
    Validating data
    Producing a spec
  For developers / contributors
    Setup
    Writing a new generator
    Contributing code
    FAQ / How-Do-I

Concepts
  Configurations
    Full configurations
    Partial configurations
    The unconfig (_)
    Configuration file format
    Validating configurations
  The data pipeline
    Overview and flow diagram
    Overlay merge (JSON Merge Patch)
    $inherits and $remove operators
    Data resolution
  Conditions system

The Database (spec/)
  Overview
  Tables reference
    csr
    exception_code
    ext
    inst
    inst_opcode / inst_subtype / inst_type
    inst_var / inst_var_type
    interrupt_code
    isa
    manual / manual_version
    param

    profile / profile_family / profile_release

    register_file
  Custom overlays (spec/custom/)
  Schema reference (auto-generated)
    Versioning
    Conditions

IDL Language
  Overview and design goals
  Data types
  Literals
  Operators
  Variables and constants
  Type conversions and casting
  Builtins
  Control flow
  Functions
  Scope rules
  IDL in instruction definitions
  IDL in CSR definitions
  idlc compiler

Tools
  udb gem
    Overview
    CLI reference (auto-generated)
    Ruby API (link to YARD docs)
    Installation
  udb-gen gem
    Overview
    CLI reference (auto-generated)
    Installation
  idlc gem
    Overview
    CLI reference (auto-generated)
    AST API
    Installation
  udb_helpers gem
  idl_highlighter gem
  bin/generate
  bin/regress
  bin/chore

Generators
  Overview
  PRM PDF (prm_pdf)
  C++ ISS (cpp_hart_gen)
  C Header (c_header)
  Go (go)
  SystemVerilog (sverilog)
  Profile Docs (profile)
  Instructions Appendix
  Search Indexer

Contributing
  Code contributions
  Data contributions
  Commit message conventions
  Code review process
  License
  Contributing to the docs site
  Docs site architecture
```

---

## Design Principles

- **Task-oriented Getting Started pages**: Procedural ("do this, then this"), not conceptual.
- **Concept pages are reference-oriented**: Explain how things work, not how to do tasks.
- **Configurations under Concepts, not top-level**: It's a concept to understand, not a task to perform.
- **Generated artifacts link is prominent**: It's likely the most-visited destination. Put it in the navbar and in the hero CTA.
- **FAQ / How-Do-I lives under developer Getting Started**: The content from `doc/HOW-DO-I.adoc` is developer-focused.
- **API docs are auto-generated**: YARD for Ruby gems. Link from the navbar, not buried in the sidebar.
- **AsciiDoc → Markdown**: All existing `.adoc` files should be converted to Markdown for Docusaurus compatibility.

---

## Technical Notes

- **Framework**: Docusaurus v3
- **Search**: Docusaurus built-in search or Algolia DocSearch
- **API docs**: YARD-generated, published as a separate static site or Docusaurus page
- **Schema docs**: Auto-generated from JSON Schema files in `spec/schemas/`
- **CLI docs**: Auto-generated from `--help` output or Thor introspection
- **AsciiDoc conversion**: Convert all `doc/*.adoc` files to Markdown as part of site setup
- **Source co-location**: Use Docusaurus `plugin-content-docs` `path` option to point at source locations (e.g., backend READMEs) rather than symlinks, which can be fragile
- **Versioning**: Display the current git tag/commit prominently; consider Docusaurus versioning once the API stabilizes
- **Deployment**: GitHub Actions → GitHub Pages (replacing the existing generated-spec Pages site)
