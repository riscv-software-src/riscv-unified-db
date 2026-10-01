<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Stage 5: approved generator retirements

The approved scope in `stage5-generators.json` supersedes the historical
preserve-all inventory. Removing a product also removes its commands, dedicated
templates, golden fixtures, regression jobs, publication downloads and landing
page links. It does not remove architecture records, schemas, or retained
instruction/CSR content merely because those records also fed retired documents.

## Independent retirements

The retirement layer removes ISA manuals, instruction appendices, profile-release
documents and portfolio appendices, PRM documents and external-document
preprocessing, all ISA Explorer formats, the profile-extension report, the
JSON-reference indexer and the floating-point stimulus authoring script.
The retired manual chapter-title and CSR HTML-fragment methods are removed
without removing their containing architecture models.

Retained extension documents still use the existing shared instruction/CSR
templates until the Python document pipeline replaces them. C/SV/Go and C++
generators, the instruction table, configuration headers, strict profile
configurations, schema publication and schema documentation remain.
Existing native floating-point tests and their external-data reader remain;
retiring stimulus authoring does not authorize deleting floating-point tests.

## Dependency-ordered completion

Configuration-document publication, its backend, and its regression jobs are
retired. Function lookup and search are available through the Python database
and IDL interfaces without generated configuration-document artifacts.

Ruby typing/gem maintenance and the remainder of the old shared documentation
framework are removed at final cutover, after their retained runtime and
extension-document consumers have replacements. Python API reference generation
is a replacement contract, not permission to drop API documentation.

## Acceptance

Check that retired public commands and CI/publication references are absent,
that the workflow regenerates from its source registry, and that retained
generator discovery, Rake loading and focused native generator tests still work.
Keep retired-product fixture removal distinct from weakening retained-feature
tests. No schema version or data correction is reverted to make these gates pass.
