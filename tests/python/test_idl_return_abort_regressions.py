# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Scope and state guards for conservative unknown-abort handling."""

import pytest

from udb.idl.errors import IdlValueUnknown
from udb.idl.parser import parse_function_body
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import Qualifier, Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)


def body_context(text):
    table = SymbolTable()
    table.add("u", Var("u", BITS8))
    table.push(None)
    table.add("__expected_return_type", BITS8)
    table.add("untouched", Var("untouched", BITS8, 7))
    table.add("hardware", Var("hardware", BITS8.qualify(Qualifier.GLOBAL), 11))
    node = parse_function_body(text)
    node.type_check(table)
    return node, table


@pytest.mark.parametrize(
    "text",
    [
        (
            "Bits<8> x = 0; for (Bits<8> i = 0; i < 2; i++) { "
            "x = 1; Bits<8> z = u; x = 4; } return x;"
        ),
        ("Bits<8> x = 0; for (Bits<8> i = 0; i < 2; i++) { Bits<8> z = u; x = 4; } return x;"),
    ],
)
def test_loop_body_abort_invalidates_writes_before_and_after_unknown(text):
    node, table = body_context(text)
    with pytest.raises(
        IdlValueUnknown, match="value of right-hand side of variable initialization is unknown"
    ):
        node.return_value(table)
    assert table.get("x").value is None
    with pytest.raises(IdlValueUnknown):
        node.return_values(table)
    assert table.get("x").value is None
    assert table.get("untouched").value == 7
    assert table.levels == 2


def test_known_false_loop_preserves_unexecuted_writes():
    node, table = body_context(
        "Bits<8> x = 0; for (Bits<8> i = 0; false; i++) { Bits<8> z = u; x = 4; } return x;"
    )
    assert node.return_value(table) == 0
    assert node.return_values(table) == [0]
    assert table.get("x").value == 0


def test_unknown_loop_without_writes_preserves_known_state_and_candidates():
    node, table = body_context(
        "Bits<8> x = 0; for (Bits<8> i = 0; i < u; i++) { return 1 if (false); } return x;"
    )
    with pytest.raises(IdlValueUnknown, match="Value of 'u' not known"):
        node.return_value(table)
    assert table.get("x").value == 0
    assert node.return_values(table) == [0]


def test_unknown_loop_preserves_literal_return_candidates():
    node, table = body_context(
        "Bits<8> x = 0; for (Bits<8> i = 0; i < u; i++) { x = 4; } return 6;"
    )
    with pytest.raises(IdlValueUnknown):
        node.return_value(table)
    assert node.return_values(table) == [6]
    assert table.get("x").value is None


def test_taken_body_abort_respects_trailing_local_shadow_and_hardware():
    node, table = body_context(
        "Bits<8> x = 0; if (true) { Bits<8> z = u; Bits<8> x = 5; "
        "x = x + 1; hardware = 5; } return x;"
    )
    with pytest.raises(IdlValueUnknown):
        node.return_value(table)
    assert table.get("x").value == 0
    assert table.get("hardware").value == 11
    assert table.get("untouched").value == 7
    assert table.get("z") is None
    assert node.return_values(table) == [0]


def test_loop_abort_respects_body_shadow_and_hardware():
    node, table = body_context(
        "Bits<8> x = 0; for (Bits<8> i = 0; i < u; i++) { "
        "Bits<8> x = 5; x = x + 1; hardware = 5; } return x;"
    )
    with pytest.raises(IdlValueUnknown):
        node.return_value(table)
    assert table.get("x").value == 0
    assert table.get("hardware").value == 11
    assert table.get("untouched").value == 7
    assert node.return_values(table) == [0]


def test_function_abort_invalidates_only_trailing_destinations():
    node, table = body_context("Bits<8> x = 0; Bits<8> z = u; x = 5; hardware = 5; return x;")
    with pytest.raises(
        IdlValueUnknown, match="value of right-hand side of variable initialization is unknown"
    ):
        node.return_value(table)
    assert table.get("x").value is None
    assert table.get("hardware").value == 11
    assert table.get("untouched").value == 7
    with pytest.raises(IdlValueUnknown):
        node.return_values(table)
    assert table.get("x").value is None


@pytest.mark.parametrize(
    ("loop", "reason"),
    [
        (
            "for (Bits<8> i = u; i < 2; i++) { x = 4; }",
            "value of right-hand side of variable initialization is unknown",
        ),
        ("for (Bits<8> i = 0; i < 1; i = i + u) { x = 4; }", ""),
    ],
)
def test_loop_initialization_and_update_abort_preserve_original_reason(loop, reason):
    node, table = body_context(f"Bits<8> x = 0; {loop} return x;")
    with pytest.raises(IdlValueUnknown) as unknown:
        node.return_value(table)
    assert unknown.value.reason == reason
    assert table.get("x").value is None
    with pytest.raises(IdlValueUnknown):
        node.return_values(table)
    assert table.get("x").value is None
    assert table.get("untouched").value == 7


def test_taken_body_abort_does_not_invalidate_unreachable_else_writes():
    node, table = body_context(
        "Bits<8> x = 0; if (true) { Bits<8> z = u; x = 5; } else { untouched = 4; } return x;"
    )
    with pytest.raises(IdlValueUnknown):
        node.return_value(table)
    assert table.get("x").value is None
    assert table.get("untouched").value == 7
    assert table.get("hardware").value == 11
    with pytest.raises(IdlValueUnknown):
        node.return_values(table)
    assert table.get("x").value is None
