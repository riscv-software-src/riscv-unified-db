<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# UDB Documentation

This directory is the root of the UDB documentation site, built with [Docusaurus](https://docusaurus.io/).

## Local development

Dependencies are managed from the **repo root** via aube. Run all commands from the
repo root, not from inside `doc/`.

```bash
# Start the local dev server with live reload
./bin/aubr -C doc start

# Build the static site
./bin/aubr -C doc build
```

The dev server runs at `http://localhost:3000` by default.

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
