# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CSR and register-file reference discovery."""

from __future__ import annotations

from dataclasses import dataclass

from ..ast import (
    AryElementAccess,
    AryElementAssignment,
    AryRangeAssignment,
    CsrReadExpression,
    CsrWrite,
    Id,
    IntLiteral,
    Node,
)
from ..errors import IdlError, IdlValueUnknown
from ..symbols import SymbolTable
from ..types import RegFileElementType, Type, TypeKind
from ._register_walk import register_nodes
from ._walk import walk


@dataclass(frozen=True, slots=True)
class RegisterRef:
    """One statically identifiable register-file element."""

    file: str
    index: int | str


def referenced_csrs(node: Node) -> frozenset[str]:
    """Return names of statically referenced CSRs."""

    result: set[str] = set()
    for current in walk(node):
        if isinstance(current, CsrReadExpression):
            result.add(current.csr_name)
        elif isinstance(current, CsrWrite) and not isinstance(current.idx, IntLiteral):
            result.add(current.idx.to_idl())
    return frozenset(result)


def _register_file_name(node: Node, symtab: SymbolTable) -> str | None:
    try:
        node_type = node.type(symtab)
    except IdlError:
        return None
    if (
        isinstance(node_type, Type)
        and node_type.kind == TypeKind.ARRAY
        and isinstance(node_type.sub_type, RegFileElementType)
        and node_type.is_global
    ):
        return node_type.sub_type.name
    return None


def _register_index(node: Node, symtab: SymbolTable) -> int | str:
    try:
        value = node.value(symtab)
    except IdlValueUnknown:
        index_type = node.type(symtab)
        if index_type.is_const:
            return node.to_idl()
        raise
    if not isinstance(value, int):
        node.value_error("Register-file index is not an integer")
    return value


def _source_ref(node: AryElementAccess, symtab: SymbolTable) -> RegisterRef | None:
    file_name = _register_file_name(node.var, symtab)
    if file_name is None:
        return None
    return RegisterRef(file_name, _register_index(node.index, symtab))


def source_registers(node: Node, symtab: SymbolTable) -> frozenset[RegisterRef]:
    """Return register-file elements read by *node*."""

    result: set[RegisterRef] = set()
    for current, local in register_nodes(node, symtab):
        if isinstance(current, AryElementAccess):
            ref = _source_ref(current, local)
            if ref is not None:
                result.add(ref)
    return frozenset(result)


def _element_destination(node: AryElementAssignment, symtab: SymbolTable) -> RegisterRef | None:
    if isinstance(node.lhs, Id):
        base = node.lhs
        index = node.index
    elif isinstance(node.lhs, AryElementAccess) and isinstance(node.lhs.var, Id):
        base = node.lhs.var
        index = node.lhs.index
    else:
        return None

    file_name = _register_file_name(base, symtab)
    if file_name is None:
        return None
    return RegisterRef(file_name, _register_index(index, symtab))


def _range_destination(node: AryRangeAssignment, symtab: SymbolTable) -> RegisterRef | None:
    if not isinstance(node.variable, AryElementAccess):
        return None
    file_name = _register_file_name(node.variable.var, symtab)
    if file_name is None:
        return None
    return RegisterRef(file_name, _register_index(node.variable.index, symtab))


def destination_registers(node: Node, symtab: SymbolTable) -> frozenset[RegisterRef]:
    """Return register-file elements written by *node*."""

    result: set[RegisterRef] = set()
    for current, local in register_nodes(node, symtab):
        ref: RegisterRef | None = None
        if isinstance(current, AryElementAssignment):
            ref = _element_destination(current, local)
        elif isinstance(current, AryRangeAssignment):
            ref = _range_destination(current, local)
        if ref is not None:
            result.add(ref)
    return frozenset(result)
