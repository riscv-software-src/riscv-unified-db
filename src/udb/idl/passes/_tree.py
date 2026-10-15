# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Copy syntax subtrees without following parent links or semantic caches."""

from dataclasses import replace

from ..ast import Node
from ..symbols import SymbolTable


def rebuild(node: Node, children: tuple[Node, ...]) -> Node:
    return replace(node, children=children, parent=None, _cache={})


def clone(node: Node) -> Node:
    return rebuild(node, tuple(clone(child) for child in node.children))


def isolated_symtab(symtab: SymbolTable) -> SymbolTable:
    """Use the compiler's public independent clone, preserving bound contexts."""

    return symtab.deep_clone(clone_values=True)
