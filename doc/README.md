<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# UDB Documentation

This directory is the root of the UDB documentation site, built with [Docusaurus](https://docusaurus.io/).

## Local development

Run documentation tasks from the repository root:

```bash
# Build and serve the local site
mise run docs:build site
mise run docs:serve site

# Build the static site
mise run docs:build site
```

The static server runs at `http://localhost:8000` by default. Pass a different
port with `mise run docs:serve site -- --port PORT`.

## Directory structure

```
doc/
  docs/          ← Markdown content pages (readable on GitHub as-is)
  src/           ← React components, custom pages, CSS
  static/        ← Assets served at the site root (images, favicon)
  planning/      ← Planning documents (excluded from Docusaurus content)
  docusaurus.config.ts
  sidebars.ts
  package.json   ← Docusaurus dependencies (workspace member of root package.json)
```

## Further reading

Once the site is running, the full contributor guide is at:

- `/docs/contributing/docs-site` — how to add pages, use components, write MDX
- `/docs/contributing/docs-architecture` — how the build pipeline and auto-generation work

Planning documents (content plan, design decisions, implementation plan) live in [`doc/planning/`](planning/README.md).
