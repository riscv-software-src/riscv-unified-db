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


def merge_names(symtab: SymbolTable, alternatives: list[SymbolTable]) -> set[str]:
    """Names whose bindings may differ between ``symtab`` and its clones.

    Untouched globals still share the frozen base in every clone, so merging
    them would only reassign equal values.
    """
    names = {name for scope in symtab.keys_pretty()[1:] for name in scope}
    for alternative in alternatives:
        names.update(alternative.touched_global_names())
    return names
