# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""An unknown conditional write cannot leave a fabricated known destination."""

import pytest

from udb.idl.errors import IdlValueUnknown
from udb.idl.parser import parse_function_body
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import BOOL_TYPE, Type, TypeKind


def test_unknown_conditional_assignment_invalidates_written_binding():
    symtab = SymbolTable()
    symtab.push(None)
    symtab.add("a", Var("a", BOOL_TYPE))
    symtab.add("x", Var("x", Type(TypeKind.BITS, width=8), 1))
    node = parse_function_body("x = 2 if (a);")
    node.type_check(symtab)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(symtab)
    assert symtab.get("x").value is None
