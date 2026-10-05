# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Shared whole-tree traversal helpers."""

from __future__ import annotations

from collections.abc import Iterator

from ..ast import Node


def walk(node: Node) -> Iterator[Node]:
    """Yield *node* and every descendant in source order."""

    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))
