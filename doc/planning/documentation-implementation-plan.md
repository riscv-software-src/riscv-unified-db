<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->
# UDB Documentation Site — Implementation Plan

This file tracks the detailed implementation plan for the new UDB Docusaurus documentation site.
Status is tracked inline so we can resume work across sessions.

**Status legend:**
- `[ ]` Not started
- `[~]` In progress
- `[x]` Done
- `[-]` Blocked / deferred

---

## Phase 0 — Foundation

Set up the Docusaurus project, CI/CD, and scaffolding before writing any content.

### 0.1 — Bootstrap Docusaurus project

- [x] **0.1.1** Use `doc/` as the Docusaurus root, keeping documentation source and site infrastructure together. The structure will be:
  ```
  doc/
    docs/          ← Markdown content (readable on GitHub as-is)
    src/           ← React components, custom pages, CSS
    static/        ← Assets served at site root (images, favicon)
    planning/      ← Planning docs (this file); excluded from Docusaurus content
    docusaurus.config.ts
    sidebars.ts
    package.json
  ```
- [x] **0.1.2** Initialize Docusaurus in the existing `doc/` directory. Because `doc/` already contains files, run `npx create-docusaurus@latest` into a temporary directory and then copy the scaffold files into `doc/`, skipping any files that already exist (e.g., `README.md`). Alternatively: `cd doc && npx create-docusaurus@latest . classic --typescript` — Docusaurus will warn about the non-empty directory but will proceed. Review and reconcile any conflicts before committing.
- [x] **0.1.3** Add `doc/node_modules/` to `.gitignore`. Also added `doc/.docusaurus` and `doc/build`. The root `node_modules` entry covers `doc/node_modules/` since Docusaurus is managed from the root package-lock with aube (see D3 in `decisions.md`).
- [x] **0.1.4** Commit the bare scaffold with a `docs/placeholder.md` so the site builds.
- [x] **0.1.5** Verify `./bin/aubr -C doc build` succeeds.

### 0.2 — Configure Docusaurus

- [x] **0.2.1** Set `doc/docusaurus.config.ts`:
  - `title`: "UDB — RISC-V Unified Database"
  - `tagline`: "The single source of truth for the RISC-V specification"
  - `url`: `https://riscv.github.io`
  - `baseUrl`: `/riscv-unified-db/`
  - `organizationName`: `riscv`, `projectName`: `riscv-unified-db`
  - `favicon`: `/img/udb-block.svg`
  - Note: `onBrokenLinks` is set to `warn` during scaffolding; change to `throw` once content pages exist (Phase 13+).
- [x] **0.2.2** Configure navbar: `[UDB logo] [Docs] [API Reference] [Browse Spec ↗] [GitHub ↗]`. Note: the `title: 'UDB'` text next to the logo was later removed (the logo alone links home) — see D8.
- [x] **0.2.3** Configure footer with license info and GitHub link.
- [x] **0.2.4** Configure `plugin-content-docs` with `sidebarPath` pointing to `doc/sidebars.ts`. Added `planning/**` to the `exclude` list so Docusaurus does not treat `doc/planning/` as content.
- [x] **0.2.5** Set `editUrl` to `https://github.com/riscv/riscv-unified-db/tree/main/doc/` so every page has an "Edit this page" link. Note: auto-generated schema doc pages suppress this link via `custom_edit_url: null` and instead show an inline `:::note Auto-generated` admonition — see D7.

### 0.3 — Search

- [ ] **0.3.1** Evaluate Algolia DocSearch vs. `@docusaurus/plugin-search-local`.
  - Prefer Algolia if the project qualifies for the free open-source tier; otherwise use local search.
  - **Decision rule**: Apply for Algolia at the same time as Phase 0.1. If not approved within 2 weeks of the site going live, use `@docusaurus/plugin-search-local` as the fallback. Do not block Phase 0.2 on this decision — configure local search first and swap to Algolia later if approved.
- [ ] **0.3.2** Integrate chosen search plugin and verify it indexes content.

### 0.4 — CI/CD integration

- [x] **0.4.1** Add a CI check that builds the Docusaurus site on every PR and push to `main`. The `build-docs-site` job is defined in `tools/test/regress-tests.yaml` (auto-generates `.github/workflows/regress.yml`) and runs `./bin/aube ci` + `./bin/aubr -C doc build`. No deployment — this is build-only for now (see D4 in `decisions.md`).
- [ ] **0.4.2** Decide whether the new Docusaurus site replaces or coexists with the existing `pages.yml` workflow.
  - **Recommended**: Keep `pages.yml` for generated artifacts; have the Docusaurus site link out to them. Merge the two deployments into a single Pages root once the Docusaurus site is ready to go live.
  - **This decision (Q4) must be made before 0.4.3 is executed.** See Open Questions.
- [ ] **0.4.3** Integrate the Docusaurus build output into the assembled `_site/` directory. The current `pages.yml` places generated artifacts at `_site/resolved_spec`, `_site/htmls/udb_api_doc`, etc., and generates `_site/index.html` from `tools/scripts/pages.html.template` using `tools/scripts/gen_pages_index.py`. The Docusaurus build output must go at the `_site/` root, which means the generated `index.html` must be removed or redirected. **Concrete plan**: place the Docusaurus build at `_site/` root; move the generated-artifacts landing page to `_site/artifacts/` and update the Docusaurus site to link there. Coordinate with Phase 15 cutover.

### 0.5 — Asset structure

Establish the canonical location for all site assets and move existing files there. This must happen before any Docusaurus component or config references them.

**Target structure:**
```
doc/static/
  img/
    udb.svg              ← UDB logo (wide horizontal lockup) — used in navbar and hero
    udb-alt.svg          ← UDB alternate lockup with tagline — available for use in landing page hero or marketing contexts; no specific task assigned yet
    udb-block.svg        ← UDB compact mark (square) — used as favicon source and in compact contexts
    idl-app-icon.svg     ← IDL square mark
    idl-circle.svg       ← IDL circle variant
    idl-favicon.svg      ← IDL favicon (16×16)
    idl-navbar-logo.svg  ← IDL wide lockup with wordmark
  favicon.ico            ← generated from idl-favicon.svg (or udb-block.svg)
```

Docusaurus serves `static/` at the site root, so `doc/static/img/udb.svg` → `/img/udb.svg`.
Inline content assets (diagrams, screenshots) live under `doc/docs/<section>/assets/` alongside the pages that reference them.

- [x] **0.5.1** Create `doc/static/img/` directory.
- [x] **0.5.2** Copy UDB logos from `doc/` to `doc/static/img/` (copies, not moves — originals kept for AsciiDoc pipeline per 0.5.4 decision):
  - `doc/udb.svg` → `doc/static/img/udb.svg`
  - `doc/udb-alt.svg` → `doc/static/img/udb-alt.svg`
  - `doc/udb-block.svg` → `doc/static/img/udb-block.svg`
- [x] **0.5.3** Copy IDL logos from `doc/` to `doc/static/img/`:
  - `doc/idl-app-icon.svg` → `doc/static/img/idl-app-icon.svg`
  - `doc/idl-circle.svg` → `doc/static/img/idl-circle.svg`
  - `doc/idl-favicon.svg` → `doc/static/img/idl-favicon.svg`
  - `doc/idl-navbar-logo.svg` → `doc/static/img/idl-navbar-logo.svg`
- [ ] **0.5.4** Update references to the old `doc/*.svg` paths:
  - `README.adoc` line 1: `image::doc/udb.svg[UDB banner]` — **Decision**: keep `doc/udb.svg` in place (do not move it) until the AsciiDoc pipeline is retired in Phase 15. Copy the file to `doc/static/img/udb.svg` rather than moving it. The copy can be removed once `README.adoc` is updated.
  - `tools/scripts/pages.html.template`: `<img src="udb-block.svg" ...>` — **Decision**: leave this reference unchanged until Phase 15 cutover. The `pages.yml` workflow copies `doc/udb-block.svg` to `_site/`; keep that copy step in place until the generated landing page is retired.
- [ ] **0.5.5** Generate `doc/static/favicon.ico` from `idl-favicon.svg`. **Tool decision**: use `imagemagick` (`convert` command), which is available in the CI container. Add a one-time generation step to the build setup notes; do not add it to the automated pre-build pipeline (the `.ico` file will be committed to the repo).

### 0.6 — Theming and branding

- [x] **0.6.1** Add the UDB logo (`/img/udb.svg`) to the Docusaurus navbar config.
- [x] **0.6.2** Choose a primary color palette (suggest RISC-V brand colors: `#2E3192` blue / `#ED1C24` red).
- [x] **0.6.3** Create `doc/src/css/custom.css` with color overrides. Define CSS custom properties for logo colors:
  ```css
  :root {
    --udb-logo-primary: #283272;
    --udb-logo-accent:  #F5B21B;
  }
  [data-theme='dark'] {
    --udb-logo-primary: #FFFFFF;   /* White for readability on dark */
    --udb-logo-accent:  #FFB800;   /* Vibrant gold */
  }
  ```
- [x] **0.6.4** Retrofit the three UDB SVGs to replace hardcoded hex fills with CSS variables. Color → variable mapping:
  - `#283272` and `#2c356d` (logo body fill, dark blue) → `var(--udb-logo-primary)`
  - `#F5B21B` and `#e6ac2c` (accent/highlight, gold) → `var(--udb-logo-accent)`
  - Any stroke colors that match the above hex values should also be replaced.
  - Colors appear in both embedded `<style>` blocks and inline `style=` attributes; replace both.
- [x] **0.6.5** Import UDB SVGs as React components via SVGR (Docusaurus supports this out of the box) so CSS variables apply correctly. Created `doc/src/theme/Logo/index.tsx` to inline the navbar logo. Also created `doc/static/img/udb-navbar.svg` (cropped version without tagline for better navbar fit).
- [x] **0.6.6** Verify light and dark mode both look good.

---

## Phase 0.7 — IDL Logo

All four IDL SVGs have been created in `doc/` and will be moved to `doc/static/img/` as part of Phase 0.5. The files are:

| File | Description |
|---|---|
| `doc/idl-app-icon.svg` | 100×100 rounded-rect, the reference/canonical design |
| `doc/idl-circle.svg` | 100×100 circle variant (mark scaled to fit inside circle) |
| `doc/idl-favicon.svg` | 16×16 favicon |
| `doc/idl-navbar-logo.svg` | 420×60 horizontal lockup: mark + "ISA Description Language" text |

All four use CSS custom properties (`var(--idl-logo-bg)`, `var(--idl-logo-fg)`) with hardcoded fallbacks (`#161b22` bg, `#33f1ff` fg). The `idl-high-contrast-hero.svg` was removed as not needed.

- [x] **0.7.1** IDL logo SVGs created in `doc/` with CSS custom properties (will be moved to `doc/static/img/` in Phase 0.5).
- [x] **0.7.2** Add IDL logo CSS variables to `doc/src/css/custom.css` (colors TBD — choose values that harmonize with the UDB palette and work in both light and dark mode):
  ```css
  :root {
    --idl-logo-bg: transparent;   /* light mode bg */
    --idl-logo-fg: #2E3192;       /* light mode fg — RISC-V blue */
  }
  [data-theme='dark'] {
    --idl-logo-bg: #161b22;
    --idl-logo-fg: #33f1ff;
  }
  ```
- [x] **0.7.3** Create `doc/src/components/IDLPageHeader/index.tsx` — a React component that renders the IDL logo alongside a subtitle. Use `idl-app-icon.svg` (compact) on reference pages and `idl-navbar-logo.svg` (wide) on the overview page. Import SVGs via SVGR.
- [ ] **0.7.4** Add `IDLPageHeader` to `docs/idl/overview.mdx` (rename from `.md`) with the wide navbar variant. **Note**: Deferred until IDL documentation pages are created in content phases.
- [ ] **0.7.5** Add `IDLPageHeader` (compact variant) to each remaining IDL reference page (rename `.md` → `.mdx` as needed). **Note**: Deferred until IDL documentation pages are created in content phases.

---

## Phase 0.8 — Documentation site README and planning docs

- [x] **0.8.1** The three planning docs have been moved to `doc/planning/`:
  - `doc/planning/documentation-plan.md` — content plan
  - `doc/planning/documentation-site-design.md` — design and navigation structure
  - `doc/planning/documentation-implementation-plan.md` — this file
- [x] **0.8.2** Write `doc/planning/README.md` explaining what these files are and that the implementation plan is the active working document.
- [x] **0.8.3** Write `doc/README.md` covering:
  - One-line description of what this directory is
  - How to install dependencies (`./bin/aube ci` from the repo root)
  - How to run the local dev server (`./bin/aubr -C doc start`)
  - Where the full contributor guide lives once the site is running (`/docs/contributing/docs-site`)
  - Where the architecture notes live (`/docs/contributing/docs-architecture`)
  - Where the planning docs live (`doc/planning/`)
- [x] **0.8.4** Create `doc/planning/decisions.md` — decision log recording significant decisions, rationale, affected files, and reversal steps. When an Open Question is resolved, add an entry here before marking it `[x]`.

---

## Phase 0.9 — Documentation Status Indicators

Make it clear to readers which documentation is complete vs. in-progress while the site is under active development.

**Goal**: Set proper expectations for visitors during the construction phase and make the site feel professional rather than incomplete.

- [x] **0.9.1** Create a `PageStatus` component (or use Docusaurus admonitions) to indicate completion status at the top of pages. Status values: "complete", "in-progress", "planned". Start with admonitions for MVP:
  ```markdown
  :::info[Status: Complete]
  This documentation is complete and reviewed.
  :::

  :::warning[Status: In Progress]
  This documentation is partially complete. Some sections may be missing or outdated.
  :::

  :::caution[Status: Planned]
  This documentation is planned but not yet written. Check back soon.
  :::
  ```
  Can be upgraded to a custom React component later for more polish.

- [ ] **0.9.2** Add status indicators to the sidebar using custom CSS or sidebar item customization. Consider emoji (✅/🚧/📋) or colored dots for quick scanning. This makes status visible during navigation without requiring users to open each page.

- [x] **0.9.3** Create a "Documentation Status" page at `docs/intro/doc-status.md` that lists all planned documentation sections with their current status, so readers can see at a glance what exists and what's coming. Structure it by the main categories from the site design (Getting Started, Concepts, Database, IDL, Tools, Generators). Use a table format:
  | Section | Status |
  |---------|--------|
  | Getting Started for Users | 🚧 In Progress |
  | Getting Started for Spec Writers | 📋 Planned |
  | ... | ... |

- [x] **0.9.4** Add a frontmatter field `status: complete|in-progress|planned` to all documentation pages. This can be consumed by the PageStatus component (if built) or by a build script that validates status consistency. Added to key pages as they are created.

- [x] **0.9.5** (Optional) Add a global banner at the top of the site (using Docusaurus announcement bar) that says "🚧 This documentation site is under active construction. See [Documentation Status](/intro/doc-status) for details." Remove this once the site reaches stable status. Configure in `docusaurus.config.ts`:
  ```typescript
  announcementBar: {
    id: 'under_construction',
    content: '🚧 This documentation site is under active construction. See <a href="/intro/doc-status">Documentation Status</a> for details.',
    backgroundColor: '#ffa500',
    textColor: '#000000',
    isCloseable: true,
  }
  ```

**Acceptance**: Readers can immediately see which pages are trustworthy vs. incomplete. Status is visible both at the page level and in navigation. The Documentation Status page provides a roadmap of what's coming.

---

## Phase 1 — Landing Page

Build the custom landing page (`src/pages/index.tsx`).

### 1.1 — Hero section

- [x] **1.1.1** Display UDB logo, tagline, and three CTA buttons:
  - "Browse the spec" (external, new tab → generated artifacts URL)
  - "Get started" (→ `/docs/getting-started/users`)
  - "GitHub" (external, new tab → `https://github.com/riscv/riscv-unified-db`)
- [x] **1.1.2** Style hero with a subtle background (gradient or light pattern).

### 1.2 — "What is UDB?" summary

- [x] **1.2.1** Write a 3–4 sentence summary paragraph.
- [x] **1.2.2** Add "Learn more →" link to the full "What is UDB?" doc page.

### 1.3 — Role-based "I want to..." cards

- [x] **1.3.1** Implement a 2×2 card grid (or 4-column row on wide screens) with:
  - 🔍 Browse the RISC-V spec → generated artifacts (external)
  - ⚙️ Generate artifacts for my design → `/docs/getting-started/users`
  - 📝 Contribute data → `/docs/getting-started/spec-writers`
  - 🛠️ Build tools / contribute code → `/docs/getting-started/developers`
- [x] **1.3.2** Each card: icon, headline, 1–2 sentence body, primary link button.

### 1.4 — "What can UDB generate?" showcase

- [x] **1.4.1** Create a visual grid (3–5 items) showing example outputs. Implemented as a compact generator grid rather than screenshot-based showcase.
- [x] **1.4.2** Each item links to the relevant generator docs page.
- [-] **1.4.3** Gather/create screenshots or code snippets for each item. Deferred — using text cards only.

### 1.5 — Quick links bar

- [x] **1.5.1** Add a compact row of links:
  - IDL Language Reference
  - Schema Reference
  - Configuration Format
  - FAQ / How-Do-I
  - GitHub Issues (external)

---

## Phase 2 — Content: Introduction

### 2.1 — "What is UDB?" page (`docs/intro/what-is-udb.md`)

- [x] **2.1.1** Write the full "What is UDB?" page covering:
  - The database at the core (spec/)
  - Tools built around it
  - What it can generate
  - Who uses it and why
- [x] **2.1.2** Include the block diagram SVG (`doc/udb-block.svg`). Note: Used file structure infographic instead of block diagram.
- [x] **2.1.3** Add a "Current state" section noting the project is under active development and which use cases are stable. Note: Removed this section; page is now high-level overview with sections on: Database, Configuration, Customization, Working with UDB Data, and Learn More.

---

## Phase 3 — Content: Getting Started

### 3.1 — Getting started for users (`docs/getting-started/users/`)

- [ ] **3.1.1** Write overview page: the three main entry points (udb gem, udb-gen gem, idlc gem).
- [ ] **3.1.2** Write `udb-gem.md`: CLI usage, JSON RPC, Ruby API overview, installation.
  - Source: `tools/ruby-gems/udb/README.adoc` (convert from AsciiDoc).
  - Include auto-generated CLI reference (see Phase 7).
- [ ] **3.1.3** Write `udb-gen-gem.md`: overview, CLI usage, installation.
  - Include auto-generated CLI reference (see Phase 7).
- [ ] **3.1.4** Write `idlc-gem.md`: overview, CLI usage, AST API, installation.
  - Include auto-generated CLI reference (see Phase 7).
- [ ] **3.1.5** Write `raw-vs-resolved.md`: explain the difference between raw and resolved data with a concrete YAML example.
- [ ] **3.1.6** Write `python-interface.md`: document the Python bindings in `tools/ruby-gems/udb/` (investigate what exists).
- [ ] **3.1.7** Write `bin-scripts.md`: document `bin/udb`, `bin/udb-gen`, `bin/generate` (language-agnostic generator wrapper), `bin/regress`, `bin/chore`. Explain that `bin/generate` exposes all generators regardless of implementation language.

### 3.2 — Getting started for specification writers (`docs/getting-started/spec-writers/`)

- [ ] **3.2.1** Write overview page.
- [ ] **3.2.2** Write `adding-extensions.md`: step-by-step guide with example.
- [ ] **3.2.3** Write `adding-instructions.md`: step-by-step guide with example.
- [ ] **3.2.4** Write `adding-csrs.md`: step-by-step guide with example.
- [ ] **3.2.5** Write `validating-data.md`: how to run validation, what errors look like, how to fix them.
- [ ] **3.2.6** Write `producing-a-spec.md`: end-to-end walkthrough from data to generated output.
- [ ] **3.2.7** Convert `doc/data-templates.adoc` → Markdown and incorporate into this section.

### 3.3 — Getting started for developers (`docs/getting-started/developers/`)

- [ ] **3.3.1** Write `setup.md`: environment setup (container, Ruby, Node, dependencies). Pull from top-level README.
- [ ] **3.3.2** Write `new-generator.md`: how to add a new generator subcommand to `udb-gen` and expose it via `bin/generate`; getting a `ConfiguredArchitecture`, ERB templates, `udb_helpers`.
- [ ] **3.3.3** Convert `doc/HOW-DO-I.adoc` → `faq.md` (FAQ / How-Do-I page).
- [ ] **3.3.4** Link to `docs/contributing/index.md` from the developer getting-started section (do not duplicate the content — the canonical location is Phase 9.1).
- [ ] **3.3.5** Convert `doc/ci.adoc` → `ci.md` (CI infrastructure overview).
- [ ] **3.3.6** Convert `doc/regress-test-infrastructure.adoc` → `testing.md`.

---

## Phase 4 — Content: Concepts

### 4.1 — Configurations (`docs/concepts/configurations/`)

- [x] **4.1.1** Write `overview.md`: what configurations are, the three types, why they exist. *(Exists at `doc/docs/concepts/configurations/overview.md`; cross-linked to schema reference.)*
- [ ] **4.1.2** Write `full-configs.md`: format, required fields, example (`cfgs/mc100-32-full-example.yaml`).
- [ ] **4.1.3** Write `partial-configs.md`: format, `mandatory_extensions`, example.
- [ ] **4.1.4** Write `unconfig.md`: what `_` means and when to use it.
- [ ] **4.1.5** Write `config-file-format.md`: complete reference for the config YAML format, including overlays (`cfgs/NAME/arch_overlay/`). Reference `cfgs/example_rv64_with_overlay.yaml`.
- [ ] **4.1.6** Write `validating-configs.md`: how to validate a config, compatibility checking against profiles. Must cover two levels of validation: (1) **Schema validation** — structural correctness checked by `bin/validate`; (2) **Semantic validation** — data-dependency rules that the schema cannot express, including: extension versions must exist in the database, the required set of `params` depends on which extensions are implemented (and on other parameter values), extension `requirements` conditions must be satisfied, and version constraints in partial configs must be satisfiable. Explain that a file can be schema-valid but semantically invalid, and that `bin/validate` checks both.

### 4.2 — The data pipeline (`docs/concepts/data-pipeline/`)

- [ ] **4.2.1** Write `overview.md`: the full flow `spec/` → overlay merge → `$inherits`/`$remove` → `gen/` → `ConfiguredArchitecture`.
- [ ] **4.2.2** Embed or recreate the pipeline diagram from `spec/std/isa/README.adoc`.
- [ ] **4.2.3** Write `overlay-merge.md`: JSON Merge Patch semantics, how overlays are applied.
- [ ] **4.2.4** Write `inherits-remove.md`: the `$inherits` and `$remove` operators with examples.
- [ ] **4.2.5** Write `data-resolution.md`: IDL → YAML conversion, what happens during resolution.

### 4.3 — Conditions system (`docs/concepts/conditions.md`)

- [ ] **4.3.0** Extract condition types (`condition`, `yaml_condition`, `idl_condition`, `xlen_condition`, `extension_condition`, `param_condition`) from `schema_defs.json` into a dedicated `spec/schemas/condition_schema.json`. Update all `$ref` paths in other schemas. This enables the schema doc generator to produce a standalone conditions reference page that can be linked from the `requirements` field in `config_schema.json` and other schemas.
- [ ] **4.3.1** Convert `doc/schema/conditions.adoc` → Markdown.
- [ ] **4.3.2** Review and update for accuracy/completeness.

---

## Phase 5 — Content: The Database

### 5.1 — Overview (`docs/database/overview.md`)

- [ ] **5.1.1** Write the "relational database" framing: tables, rows, columns.
- [ ] **5.1.2** Include the full table listing from the plan doc. The complete list of tables in `spec/std/isa/` is: `csr`, `exception_code`, `ext`, `inst`, `inst_opcode`, `inst_subtype`, `inst_type`, `inst_var`, `inst_var_type`, `interrupt_code`, `isa`, `manual`, `manual_version`, `param`, `profile`, `profile_family`, `profile_release`, `prose`, `register_file`. Also note `spec/std/non_isa/` (currently contains only `Semihosting.yaml`).
- [ ] **5.1.3** Explain that subdirectories within a table directory are organizational only.

### 5.2 — Table reference pages (`docs/database/tables/`)

For each table, create a page with: description, schema summary (auto-generated where possible), and example YAML.

- [ ] **5.2.1** `csr.md` — Control and Status Registers
- [ ] **5.2.2** `exception_code.md` — Synchronous exception codes
- [ ] **5.2.3** `ext.md` — ISA extensions
- [ ] **5.2.4** `inst.md` — Instructions
- [ ] **5.2.5** `inst-encoding.md` — inst_opcode, inst_subtype, inst_type (group these)
- [ ] **5.2.6** `inst-decode.md` — inst_var, inst_var_type (group these)
- [ ] **5.2.7** `interrupt_code.md` — Asynchronous interrupt codes
- [ ] **5.2.8** `isa.md` — Global IDL source files
- [ ] **5.2.9** `manual.md` — manual, manual_version (group these)
- [ ] **5.2.10** `param.md` — Configuration parameters
- [ ] **5.2.11** `profile.md` — profile, profile_family, profile_release (group these)
- [ ] **5.2.12** `register_file.md` — Register file definitions
- [ ] **5.2.13** `non-isa.md` — `spec/std/non_isa/` (non-ISA data; currently contains the Semihosting specification)

### 5.3 — Custom overlays (`docs/database/custom-overlays.md`)

- [ ] **5.3.1** Explain the overlay mechanism for customization.
- [ ] **5.3.2** Walk through an example from `spec/custom/`.

### 5.4 — Schema reference (`docs/database/schema/`)

- [ ] **5.4.1** Write `overview.md`: what schemas are, where they live (`spec/schemas/`), how they are enforced.
- [ ] **5.4.2** Convert `doc/schema/versioning.adoc` → `versioning.md`.
- [x] **5.4.3** Set up auto-generation of per-schema documentation from the JSON Schema files in `spec/schemas/`. Implemented as a custom Ruby gem (`tools/internal-gems/schema_doc_gen/`) invoked via `bin/chore gen schema-docs`. Generates MDX pages under `doc/docs/schemas/<version>/`. See D7 in `decisions.md`.
- [x] **5.4.4** Add a schema index page listing all documented schemas with links. *(Auto-generated at `doc/docs/schemas/index.mdx`.)*

**Schema content review status** (improving `description` fields and `examples` in each schema file):
- [x] `config_schema.json` — Fully reviewed and improved: top-level description with overview and semantic validation note, Quick Start examples, field descriptions for all properties, version format corrected (`MAJOR[.MINOR[.PATCH]]`), `additional_extensions` default documented, `requirements` description added, `arch_overlay` grammar fixed, `$source` hidden with tooling note, cross-link to concepts overview and validating-configs page.
- [~] `schema_defs.json` — Partially improved: `extension_name`, `requirement_string`, `version_requirements`, `extension_version` (corrected format), `condition` (placeholder description pending 4.3.0), `spec_state` (full description with all enum values) descriptions added.
- [ ] `exception_code_schema.json`
- [~] `ext_schema.json` — Generator improved: bare `enum` (without `type`) now renders as pipe-separated values instead of `any`; `type` + `enum` together also renders enum values. Schema content review in progress.
- [ ] `inst_schema.json`
- [ ] `inst_opcode_schema.json`
- [ ] `inst_subtype_schema.json`
- [ ] `inst_type_schema.json`
- [ ] `inst_var_schema.json`
- [ ] `inst_var_type_schema.json`
- [ ] `inst_variable_metadatas.json`
- [ ] `interrupt_code_schema.json`
- [ ] `manual_schema.json`
- [ ] `manual_version_schema.json`
- [ ] `mmr_schema.json`
- [ ] `non_isa_schema.json`
- [ ] `param_schema.json`
- [ ] `prm_schema.json`
- [ ] `proc_cert_class_schema.json`
- [ ] `proc_cert_model_schema.json`
- [ ] `profile_family_schema.json`
- [ ] `profile_release_schema.json`
- [ ] `profile_schema.json`
- [ ] `register_file_schema.json`

---

## Phase 6 — Content: IDL Language

All content sourced from `doc/idl.adoc` (41.6 KB — comprehensive). Convert to Markdown and split into sections.

- [x] **6.1** Convert `doc/idl.adoc` → Markdown. Used manual conversion rather than pandoc; content was substantially revised, expanded, and restructured rather than mechanically converted.
- [x] **6.2** Split into the following pages under `docs/idl/`:
  - [x] **6.2.1** `index.mdx` — IDL section landing page with logo, tagline, reader guide cards, and language reference card grid
  - [x] **6.2.2** `overview.mdx` — Overview and design goals; IDL for Verilog/C users entry points; use cases; worked BLTU example; basics (comments, case sensitivity, keywords)
  - [x] **6.2.3** `data-types.mdx` — Bits\<N\>, Boolean, strings, enumerations, bitfields, structs, arrays, tuples
  - [x] **6.2.4** `variables.mdx` — Assignment, mutable variables, constants, naming rules table, compile-time vs. runtime
  - [x] **6.2.5** `literals.mdx` — Verilog-style, C-style, binary, array, string literals; warning callouts for sign-bit truncation
  - [x] **6.2.6** `operators.mdx` — Full HTML precedence table with rowspan, widening operators section with summary table
  - [x] **6.2.7** `type-conversions.mdx` — Implicit widening table, $signed/$bits/$enum/$enum_to_a casts; warning callouts
  - [x] **6.2.8** `control-flow.mdx` — if/else, for loops, const loop variables
  - [x] **6.2.9** `functions.mdx` — Calling functions, return statement, declarations, rules with hardware rationale, builtin functions
  - [x] **6.2.10** `scope.mdx` — Global, function, instruction, CSR scopes; .idl file organization
  - [x] **6.2.11** `builtins.mdx` — $pc, $encoding (with type table), $array_size, $enum_size, $enum_element_size
  - [x] **6.2.12** `standard-library.mdx` — CSR access, extension checks, raise() with full ExceptionCode table, read_memory/write_memory
  - [x] **6.2.13** `in-instructions.mdx` — How operation() bodies work
  - [x] **6.2.14** `in-csrs.mdx` — sw_read(), sw_write(), field types and reset values
- [x] **6.3** Reader guide pages:
  - [x] `guide-for-c-users.mdx` — IDL for Programmers: C-family language lineage, what carries over, what differs
  - [x] `guide-for-verilog-users.mdx` — IDL for Verilog Users: bit-vector model familiar, behavioral vs. structural distinction
  - [x] `common-misunderstandings.mdx` — Eight common mistakes with examples and fixes
  - [x] `for-spec-writers.mdx` — Patterns for writing new instructions and CSR definitions
  - [x] `quick-reference.mdx` — Dense syntax cheat sheet covering all language constructs
- [x] **6.4** Write `docs/idl/idlc.md` — the `idlc` compiler: compilation pipeline, AST, symbol table, value tracking/snapshotting, analysis passes, Ruby API, error handling.
- [x] **6.5** IDL syntax highlighting in Docusaurus — see D5 in `decisions.md`.

---

## Phase 7 — Content: Tools

### 7.1 — Auto-generated CLI reference

For each gem with a CLI, auto-generate reference docs from `--help` output or introspection.

- [ ] **7.1.1** Write a script (`doc/scripts/gen-cli-docs.rb` or `.sh`) that:
  - Runs each CLI with `--help` (and subcommand `--help`)
  - Emits a Markdown page per CLI
  - Note: `udb-gen` subcommands use a custom `SubcommandWithCommonOptions` base class, **not Thor**. The script must invoke each subcommand's `--help` directly rather than relying on Thor introspection.
- [ ] **7.1.2** Integrate the script into the Docusaurus build (pre-build step in `package.json`).
- [ ] **7.1.3** Verify output for `bin/udb`, `bin/udb-gen`, `bin/idlc`, and `bin/generate` (including all generator subcommands).

### 7.2 — Tool pages (`docs/tools/`)

- [ ] **7.2.1** `udb-gem.md` — Overview, installation, link to CLI reference, link to YARD API docs.
- [ ] **7.2.2** `udb-gen-gem.md` — Overview, installation, link to CLI reference. Note that `udb-gen` subcommands correspond 1:1 with generators; link to the Generators section.
- [ ] **7.2.3** `idlc-gem.md` — Overview, installation, CLI reference, AST API overview.
- [ ] **7.2.4** `udb-helpers.md` — Overview of template helpers, key helper methods.
- [ ] **7.2.5** `idl-highlighter.md` — Brief overview and editor usage; link to the canonical page at `docs/idl/idl-highlighter.md` for full details.
- [ ] **7.2.6** `bin-generate.md` — `bin/generate`: the language-agnostic generator wrapper; how it maps to `udb-gen` subcommands and Python tools; use this when you don't care which language implements the generator.
- [ ] **7.2.7** `bin-regress.md` — `bin/regress` runner.
- [ ] **7.2.8** `bin-chore.md` — `bin/chore` maintenance tool.

### 7.3 — YARD API documentation

- [ ] **7.3.1** Ensure all five gems have adequate YARD doc comments (audit and fill gaps).
- [ ] **7.3.2** Extend the existing `yard doc` CI step (currently in `regress.yml` via `./do gen:udb:api_doc`, which generates `udb` gem docs only) to cover all five gems. The output currently lands at `_site/htmls/udb_api_doc`; consolidate under `/api/` in the new site.
- [ ] **7.3.3** Publish YARD output as a separate static directory under the Pages site (e.g., `/api/`).
- [ ] **7.3.4** Link from the navbar "API Reference" item to the YARD output.

---

## Phase 8 — Content: Generators

### 8.1 — Overview page (`docs/generators/overview.md`)

- [ ] **8.1.1** Write an overview explaining what generators are, how they work (`ConfiguredArchitecture`, ERB templates, `udb_helpers`), and how to invoke them via `bin/generate` or `udb-gen`.
- [ ] **8.1.2** Include the full generators table. **Note on current state**: `bin/generate` currently dispatches only three subcommands (`ext-doc`, `isa-explorer`, `manual`) — all via `udb-gen`. Other generators (prm-pdf, cfg-html-doc, cpp-hart-gen, etc.) are invoked via Rake tasks, not `bin/generate`. Document the actual invocation method for each generator; update once Q8 (generator migration) is resolved.
- [ ] **8.1.3** Explain the relationship between `bin/generate` (language-agnostic wrapper), `udb-gen` (Ruby interface), and Rake-based generators.

### 8.2 — Per-generator pages (`docs/generators/`)

For each generator: description, what it produces, how to invoke it, example output, developer notes.

**Generators currently accessible via `bin/generate` (and `udb-gen`):**

- [ ] **8.2.1** `ext-doc.md` — Extension documentation generator.
- [ ] **8.2.2** `isa-explorer.md` — ISA explorer tables.
- [ ] **8.2.3** `manual.md` — ISA manual generator.

**Generators currently invoked via Rake (update invocation docs once Q8 is resolved):**

- [ ] **8.2.4** `prm-pdf.md` — PRM PDF.
- [ ] **8.2.5** `cfg-html-doc.md` — HTML config documentation.
- [ ] **8.2.6** `cpp-hart-gen.md` — C++ ISS hart.
- [ ] **8.2.7** `c-header.md` — C encoding header.
- [ ] **8.2.8** `go.md` — Go definitions.
- [ ] **8.2.9** `sverilog.md` — SystemVerilog decode package.
- [ ] **8.2.10** `profile.md` — Profile documentation.
- [ ] **8.2.11** `instructions-appendix.md` — Instruction appendix.
- [ ] **8.2.12** `indexer.md` — Search indexer.

---

## Phase 9 — Content: Contributing

- [ ] **9.1** Convert `CONTRIBUTING.adoc` → `docs/contributing/index.md`.
- [ ] **9.2** Write `docs/contributing/code.md` — code contribution workflow (branches, PRs, review).
- [ ] **9.3** Write `docs/contributing/data.md` — data contribution workflow (adding spec data).
- [ ] **9.4** Write `docs/contributing/commit-messages.md` — Conventional Commits guide.
- [ ] **9.5** Write `docs/contributing/code-review.md` — review process, code owners.
- [ ] **9.6** Write `docs/contributing/license.md` — BSD-3-Clear, what is and isn't accepted.
- [ ] **9.7** Write `docs/contributing/docs-site.md` — contributor guide for the documentation site itself:
  - Prerequisites and local dev setup (`./bin/aube ci`, `./bin/aubr -C doc start`)
  - How to add a new page (file location, front matter, sidebar registration)
  - How to add a page to the sidebar (`sidebars.js`)
  - Markdown conventions used on this site (admonitions, code blocks, MDX components)
  - How to add an inline diagram or image (where assets go, how to reference them)
  - How to use the `IDLPageHeader` component
  - How to write a `DOCS.md` pointer for a new component
  - How to preview auto-generated content (schema docs, CLI docs) locally
  - Link to `docs/contributing/docs-architecture.md` for pipeline internals
- [ ] **9.8** Write `docs/contributing/docs-architecture.md` — architecture notes for documentation site maintainers:
  - Directory structure of `doc/` and what each part does
  - How the Docusaurus build pipeline works end-to-end
  - How auto-generation works: schema docs (Phase 10.1), CLI docs (Phase 10.2), YARD (Phase 10.3)
  - How to add a new auto-generation script and wire it into the pre-build step
  - How deployment works (GitHub Actions → GitHub Pages)
  - How the asset pipeline works (`static/img/`, SVGR, CSS custom properties)
  - Known gotchas and maintenance notes (Docusaurus upgrade considerations, SVGR config, etc.)
  - **Consolidate** the three planning docs in `doc/planning/` into this page as a historical/rationale section, then archive or remove the planning docs.

---

## Phase 10 — Auto-generation Infrastructure

This phase sets up the tooling to keep docs in sync with source automatically.

### 10.1 — Schema documentation generation

- [x] **10.1.1** Evaluated `@adobe/jsonschema2md` — not suitable (poor MDX output, limited control over formatting). Chose custom Ruby implementation instead.
- [-] **10.1.2** N/A — `@adobe/jsonschema2md` not used.
- [x] **10.1.3** Wrote custom Ruby gem `tools/internal-gems/schema_doc_gen/` that reads each JSON Schema file and emits structured MDX. Invoked via `bin/chore gen schema-docs`. See D7 in `decisions.md` for design decisions.
- [x] **10.1.4** Generation step added: `bin/chore gen schema-docs` (run manually; not yet wired into the Docusaurus pre-build step — see note below).
- [~] **10.1.5** Improving schema files with better `description` fields and `examples`: `config_schema.json` fully done; `schema_defs.json` partially done (`extension_name`, `requirement_string`, `version_requirements`, `extension_version`, `condition` updated); remaining schemas not yet reviewed. See schema content review status in Phase 5.4.

  **Note**: Schema docs are currently regenerated manually via `bin/chore gen schema-docs` and committed. Wiring into the Docusaurus pre-build step requires the Docker container to be available during `./bin/aubr -C doc build`, which is not the case in the current CI setup (see D4). Options: (a) keep committing generated files, (b) add a CI step that runs `bin/chore gen schema-docs` before the Docusaurus build, (c) move generation to a Node.js script that runs without Docker.

### 10.2 — CLI documentation generation

- [ ] **10.2.1** Confirm the CLI framework used by each gem. `udb-gen` subcommands use a custom `SubcommandWithCommonOptions` base class (not Thor). The generation script must invoke `--help` directly for each subcommand rather than relying on framework introspection.
- [ ] **10.2.2** Write `doc/scripts/gen-cli-docs.rb` to generate CLI reference pages.
- [ ] **10.2.3** Add to pre-build pipeline.

### 10.3 — YARD generation

- [ ] **10.3.1** Add `.yardopts` files to each gem specifying output format and included files.
- [ ] **10.3.2** Add `yard doc` to CI.
- [ ] **10.3.3** Publish output to `/api/` under the Pages site.

### 10.4 — AsciiDoc → Markdown conversion

All existing `.adoc` files must be converted. This is a one-time migration.

| Source file | Target location | Status |
|---|---|---|
| `doc/idl.adoc` | `docs/idl/` (split into 14 pages + 5 reader guides) | `[x]` |
| `doc/HOW-DO-I.adoc` | `docs/getting-started/developers/faq.md` | `[ ]` |
| `doc/data-templates.adoc` | `docs/getting-started/spec-writers/data-templates.md` | `[ ]` |
| `doc/ci.adoc` | `docs/getting-started/developers/ci.md` | `[ ]` |
| `doc/regress-test-infrastructure.adoc` | `docs/getting-started/developers/testing.md` | `[ ]` |
| `doc/schemas.adoc` | `docs/database/schema/overview.md` | `[ ]` |
| `doc/schema/conditions.adoc` | `docs/concepts/conditions.md` | `[ ]` |
| `doc/schema/versioning.adoc` | `docs/database/schema/versioning.md` | `[ ]` |
| `CONTRIBUTING.adoc` | `docs/contributing/index.md` | `[ ]` |
| `tools/ruby-gems/udb/README.adoc` | `docs/tools/udb-gem.md` (primary source) | `[ ]` |
| `doc/ruby.adoc` | merge into `docs/tools/udb-gem.md` if content is non-trivial; drop if still a stub | `[ ]` |
| `doc/riscv-opcodes-migration.adoc` | `docs/getting-started/spec-writers/riscv-opcodes-migration.md` if non-trivial; drop if still a stub | `[ ]` |
| `doc/prose-schema.adoc` | `docs/database/prose-schema.md` (structured prose encoding; note this table is being removed — confirm disposition before converting) | `[ ]` |
| `spec/std/isa/README.adoc` | Embed diagram in `docs/concepts/data-pipeline/overview.md` | `[ ]` |

**Notes on stub files**: `doc/ruby.adoc` and `doc/riscv-opcodes-migration.adoc` are currently stubs (a few lines of TODO content). Before converting, check whether they have been filled in. If still stubs, drop them and remove from the sidebar. See Q6.

**Cleanup**: After each `.adoc` file is converted and its content is live in Docusaurus, delete the original `.adoc` file to prevent divergence. Exception: `doc/idl.adoc` — keep until the IDL HTML artifact in `pages.yml` is retired (see Phase 15 cleanup task).

**Conversion process for each file:**
1. Run `pandoc -f asciidoc -t gfm --wrap=none <input.adoc> -o <output.md>`
2. Manually review and fix: cross-references, admonitions (NOTE/WARNING/TIP → Docusaurus admonitions), code block language tags, image paths.
3. Update internal links to use Docusaurus-style relative paths.

---

## Phase 12 — DOCS.md Pointers

For each component that has documentation under `doc/`, create a `DOCS.md` file in the component's source directory pointing contributors to the right place in `doc/`. This keeps docs central while making them discoverable from the source tree. None of these files exist yet — they must be created.

**Format for each `DOCS.md`:**
```markdown
## Documentation

The documentation for this component lives in [`doc/<path>/`](relative/path/to/doc/<path>/).
Please edit files there rather than here.
```

Components that need a `DOCS.md`:

- [ ] **12.1** `tools/ruby-gems/udb/DOCS.md` → points to `doc/docs/tools/udb-gem.md`
- [ ] **12.2** `tools/ruby-gems/udb-gen/DOCS.md` → points to `doc/docs/tools/udb-gen-gem.md`
- [ ] **12.3** `tools/ruby-gems/idlc/DOCS.md` → points to `doc/docs/tools/idlc-gem.md`
- [ ] **12.4** `tools/ruby-gems/udb_helpers/DOCS.md` → points to `doc/docs/tools/udb-helpers.md`
- [ ] **12.5** `tools/ruby-gems/idl_highlighter/DOCS.md` → points to `doc/docs/idl/idl-highlighter.md`
- [ ] **12.6** Each generator directory (once migrated from `backends/`) → points to `doc/docs/generators/<name>.md`
- [ ] **12.7** `spec/std/isa/` → points to `doc/docs/database/` (top-level pointer for the whole database section)

---

## Phase 13 — Sidebar and Navigation

- [ ] **13.1** Write `doc/sidebars.js` with the full hierarchy from `documentation-site-design.md`.
- [ ] **13.2** Verify all sidebar entries have corresponding `.md` files.
- [ ] **13.3** Add `pagination_prev` / `pagination_next` front matter where the auto-generated order is wrong.
- [ ] **13.4** Add `sidebar_position` front matter to all pages to enforce ordering.

---

## Phase 14 — Quality and Polish

- [ ] **14.1** Run a broken-link check (`./bin/aubr -C doc build` catches most; also use `linkinator` or similar).
- [ ] **14.2** Add OpenGraph / SEO metadata to key pages.
- [ ] **14.3** Verify mobile responsiveness.
- [ ] **14.4** Verify dark mode.
- [ ] **14.5** Add a "last updated" timestamp to pages (Docusaurus `showLastUpdateTime: true`).
- [ ] **14.6** Verify "Edit this page" links work on all hand-authored pages. Auto-generated pages (schema docs) suppress the edit link via `custom_edit_url: null` and show an inline provenance note instead — this is intentional.
- [ ] **14.7** Write a redirect map for any URLs from the old Pages site that should continue to work.
- [ ] **14.8** Announce the new site in the project README and update the README's documentation links.

---

## Phase 15 — Cutover

- [ ] **15.1** Run the new site in parallel with the old Pages site for a review period.
- [ ] **15.2** Get sign-off from maintainers (Derek Hower, Paul Clarke).
- [ ] **15.3** Update `pages.yml` to deploy the Docusaurus site as the root of GitHub Pages.
- [ ] **15.4** Archive or redirect the generated landing page (`tools/scripts/pages.html.template` and `tools/scripts/gen_pages_index.py`).
- [ ] **15.5** Update any external links (RISC-V International, downstream projects) to point to the new site.
- [ ] **15.6** Update `README.adoc` to point to the new Docusaurus site URL and remove links to the old Pages site.
- [ ] **15.7** Remove the `asciidoctor` IDL HTML build step from CI (`regress.yml` / `pages.yml`) once Phase 6 IDL docs are live and Q9 is confirmed. Delete `doc/idl.html` artifact references.
- [ ] **15.8** Delete converted `.adoc` source files from `doc/` that have been fully migrated to Docusaurus Markdown (see Phase 10.4 cleanup note).

---

## Dependency Map

```
Phase 0.1 (Bootstrap)
  └─► Phase 0.2 (Configure)
  └─► Phase 13 (Sidebar — sidebars.js format depends on Docusaurus version)
Phase 0.5 (Assets) ──► Phase 0.6 (Theming)
Phase 0.6 (custom.css) ──► Phase 0.7.2 (IDL CSS variables)
Phase 0 (Foundation)
  └─► Phase 1 (Landing Page)
  └─► Phase 10.4 (AsciiDoc conversion) ──► Phases 2–9 (Content)
  └─► Phase 10.1 (Schema gen) ──► Phase 5.4 (Schema reference)
  └─► Phase 10.2 (CLI gen) ──► Phase 7.1 (CLI reference)
  └─► Phase 10.3 (YARD gen) ──► Phase 7.3 (API docs)
Phases 2–9 (Content) ──► Phase 12 (DOCS.md Pointers)
Phases 2–9 (Content) ──► Phase 13 (Sidebar)
Phase 13 ──► Phase 14 (Quality)
Phase 14 ──► Phase 15 (Cutover)
Q4 (coexistence decision) ──► Phase 0.4.3 (CI/CD merge)
```

---

## Open Questions

Resolved decisions are recorded in [`decisions.md`](decisions.md) with rationale, affected files, and reversal steps.

- [x] **Q1** ~~Should the Docusaurus site live at `doc/` or at the repo root?~~ **Resolved**: see D1 in `decisions.md`.
- [x] **Q2** ~~TypeScript or JavaScript?~~ **Resolved**: TypeScript. See D2 in `decisions.md`.
- [ ] **Q3** Algolia DocSearch or local search? (Algolia is better UX but requires applying for the free tier; local search works immediately.) **Decision rule**: start with local search; apply for Algolia in parallel; swap if approved. Do not block Phase 0.2 on this.
- [ ] **Q4** Should the new site fully replace the existing Pages site immediately, or coexist during a transition period? **Must be resolved before Phase 0.4.3.** (Recommendation: coexist until content is complete; Docusaurus site at root, generated artifacts at `/artifacts/`.)
- [ ] **Q5** Is there a Python interface to document? `tools/ruby-gems/udb/python/yaml_resolver.py` and `tools/python/udb.py` exist but appear to be scripts, not a published API. Determine whether a Python interface worthy of documentation exists; if not, drop `docs/getting-started/users/python-interface.md` and remove from the sidebar.
- [ ] **Q6** Should `doc/riscv-opcodes-migration.adoc` and `doc/ruby.adoc` (both stubs) be written or dropped? Check current content before converting; if still TODO stubs, drop them.
- [ ] **Q7** Versioning: should the Docusaurus site use Docusaurus versioning (multiple doc versions) or just track `main`? (Recommendation: track `main` only until the API stabilizes.)
- [ ] **Q8** What is the exact destination path for generators after the `backends/` migration? Currently only `ext-doc`, `isa-explorer`, and `manual` are accessible via `bin/generate`. Update Phase 8.2 generator pages with correct invocation once the migration is complete.
- [ ] **Q9** What is the disposition of `doc/idl.html` (the AsciiDoc-rendered IDL reference, built by `asciidoctor` in CI and published to the Pages site)? Once Phase 6 (IDL docs in Docusaurus) is complete, this artifact and its CI build step can be removed. Confirm before removing.
- [ ] **Q10** `doc/prose-schema.adoc` documents the structured prose encoding system. The `prose` table in `spec/std/isa/` is being removed. Confirm whether `prose-schema.adoc` should be converted, archived, or dropped.
- [ ] **Q11** Rename `arch_overlay` to `spec_overlay` globally in the repository (tools, configuration schema, and documentation). The current name is confusing; "spec overlay" more clearly indicates that this feature overlays the specification data, not the architecture itself. This is a breaking change for configuration files and requires coordination.

---

## Known Issues / Future Work

Items identified during PR reviews or implementation that should be addressed in future updates:

- **IDL examples using misa checks**: Several IDL code examples (e.g., in `overview.mdx` and `standard-library.mdx`) use `CSR[misa].C` checks to demonstrate dynamic extension enabling/disabling. However, the handling of mutable vs. immutable `misa` is still being finalized in the specification. These examples should be reviewed and potentially replaced with examples that don't depend on misa mutability semantics once the spec is settled. (Identified in PR 1723 review, comments 56-57)

- **ERB syntax in function descriptions**: Function descriptions in `.idl` files may be processed through ERB templates. If ERB delimiters (like `<%-`) appear in a description, they could be interpreted as ERB code. Consider documenting this as a known limitation or adding validation to warn about ERB syntax in descriptions. (Identified in PR 1723 review, comment 55)

---

## Suggested Work Order (First Sprint)

For someone picking this up fresh, the highest-value first steps are:

1. **Phase 0** — Get the Docusaurus scaffold up and building in CI. Nothing else can proceed without this.
2. **Phase 10.4** — Convert the AsciiDoc files to Markdown. This is mechanical work that unblocks most content phases.
3. **Phase 1** — Build the landing page. This is the most visible deliverable and validates the design.
4. **Phase 6** — IDL language docs. The `idl.adoc` source is already comprehensive; this is mostly conversion + splitting.
5. **Phase 4** — Concepts. These are foundational; users need them before they can understand anything else.
