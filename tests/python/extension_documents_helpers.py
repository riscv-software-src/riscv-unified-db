# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Full-artifact comparison helpers."""

from __future__ import annotations

import re

from udb.extension_docs.links import anchor
from udb.extension_docs.prose import configured_prose_provider as _configured_prose_provider


def configured_prose_provider(architecture):
    """Bind tests to the installed production prose adapter."""
    return _configured_prose_provider(architecture)


def formatter_lines(text: str) -> list[str]:
    """Only blank template lines and trailing whitespace outside listings vary.

    Source blocks, literal examples and WaveDrom JSON keep every byte, including
    blank lines and indentation. No prose, row, section or content is discarded.
    """
    result = []
    literal = None
    for line in text.splitlines():
        if line in {"----", "...."}:
            literal = None if literal == line else line
            result.append(line)
        elif literal is not None:
            result.append(line)
        elif line.strip():
            result.append(line.rstrip())
    return result


def repaired_anchor_expectation(raw: str, extension_names: list[str]) -> str:
    """Guarded expected-side link-target additions; raw native artifacts stay raw."""
    aliases = []
    for match in re.finditer(r"^\[#udb:doc:(inst|csr|csr_field):([^\]]+)\]$", raw, re.MULTILINE):
        kind = match[1]
        target = match[2]
        # Legacy CSR-field anchors use csr-name-field-name separated by a dash.
        if kind == "csr_field":
            target = target.replace(":", "*")
        aliases.append((match[0], anchor(kind, target)))
    for original, alias in aliases:
        raw = raw.replace(original, alias + "\n" + original)
    marker = "== Extension description\n"
    assert raw.count(marker) == 1
    before, after = raw.split(marker, 1)
    chunks = after.split(":leveloffset: +2\n")
    assert len(chunks) >= len(extension_names) + 1
    for index, name in enumerate(extension_names):
        chunks[index] += anchor("ext", name) + "\n[#udb:doc:ext:" + name + "]\n"
    return before + marker + ":leveloffset: +2\n".join(chunks)
