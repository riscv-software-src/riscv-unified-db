# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Repeated exception analysis must assign the current context's local binding."""

import pytest

from udb.idl import parse
from udb.idl.passes import reachable_exceptions
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Type, TypeKind


@pytest.mark.parametrize("gate", [None, True, False])
def test_repeated_unknown_guard_analysis_uses_current_owned_binding(gate):
    table = SymbolTable()
    table.add("gate", Var("gate", Type(TypeKind.BOOLEAN), gate))
    node = parse(
        "raise(5); Boolean adue; adue=gate; if(adue){raise(7);}",
        "function_body",
    )
    before = node.to_idl()
    expected = (1 << 5) | (0 if gate is False else 1 << 7)
    cache = {}
    for _ in range(2):
        context = table.deep_clone()
        assert reachable_exceptions(node, context, cache=cache) == expected
        assert context.get("adue") is None
        assert context.get("gate").value is gate
    assert table.get("adue") is None
    assert node.to_idl() == before
