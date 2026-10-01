# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Load captured architecture IDL sources without reopening repository paths."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from .errors import DataError
from .idl.ast import (
    BitfieldDefinition,
    BuiltinEnumDefinition,
    EnumDefinition,
    IncludeStatement,
    Isa,
    Node,
    StructDefinition,
    UserTypeName,
)
from .idl.parser import parse_isa
from .idl.source import IdlSource

if TYPE_CHECKING:
    from .database import ResolvedDatabase
    from .source import SourceText


@cache
def global_ast(database: ResolvedDatabase, *, entrypoint: str = "isa/globals.isa") -> Isa | None:
    """Flatten includes once in source order, retaining each declaration's own span."""
    if not database.idl_sources:
        return None
    loaded: set[tuple[str, str]] = set()
    active: list[tuple[str, str]] = []
    definitions: list[Node] = []
    entry: Isa | None = None

    def visit(captured: SourceText) -> None:
        nonlocal entry
        identity = (captured.layer, captured.source)
        if identity in active:
            labels = [database.idl_source_layers[key].label for key in (*active, identity)]
            raise DataError(f"Cyclic IDL include: {' -> '.join(labels)}")
        if identity in loaded:
            return
        source = IdlSource(text=captured.text, label=captured.label)
        isa = parse_isa(source.text, source=source)
        if entry is None:
            entry = isa
        active.append(identity)
        for definition in isa.definitions:
            if isinstance(definition, IncludeStatement):
                visit(database.resolve_idl_include(captured, definition.filename))
            else:
                definitions.append(definition)
        active.pop()
        loaded.add(identity)

    try:
        captured_entry = database.idl_sources[entrypoint]
    except KeyError:
        raise DataError(
            f"Missing captured IDL source {entrypoint!r}, required by IDL entry point"
        ) from None
    visit(captured_entry)
    assert entry is not None
    types = [
        node
        for node in definitions
        if isinstance(
            node, (EnumDefinition, BuiltinEnumDefinition, BitfieldDefinition, StructDefinition)
        )
    ]
    type_names = {node.name for node in types}

    def dependencies(node: Node) -> set[str]:
        found = {node.name} if isinstance(node, UserTypeName) else set()
        for child in node.children:
            found.update(dependencies(child))
        return found

    ordered: list[Node] = []
    known: set[str] = set()
    while types:
        ready = [
            node for node in types if not ((dependencies(node) & type_names) - {node.name} - known)
        ]
        if not ready:
            raise DataError(
                f"Cyclic IDL type dependencies: {', '.join(node.name for node in types)}"
            )
        for node in ready:
            types.remove(node)
            known.add(node.name)
            ordered.append(node)
    type_ids = {id(node) for node in ordered}
    ordered.extend(node for node in definitions if id(node) not in type_ids)
    return Isa(source=entry.source, start=entry.start, end=entry.end, children=tuple(ordered))
