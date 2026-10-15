# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from udb.idl import parse
from udb.idl.passes import return_values
from udb.idl.symbols import SymbolTable


def test_all_prior_negations_and_nested_ternary_preserve_order_and_input():
    body = parse(
        "if (a) { return 0; } else if (b) { return 1; } "
        "else if (c) { return d ? 2 : 3; } else { return 4; }",
        "function_body",
    )
    parents = [(child, child.parent) for child in body.children]
    values = return_values(body, SymbolTable())
    assert [(v.expression.to_idl(), [c.to_idl() for c in v.conditions]) for v in values] == [
        ("0", ["a"]),
        ("1", ["!a", "b"]),
        ("2", ["!a", "!b", "c", "d"]),
        ("3", ["!a", "!b", "c", "!d"]),
        ("4", ["!a", "!b", "!c"]),
    ]
    assert all(child.parent is parent for child, parent in parents)


def test_parenthesized_ternaries_expand_without_dropping_outer_conditions():
    body = parse("if (outer) { return (a ? 1 : (b ? 2 : 3)); }", "function_body")
    values = return_values(body, SymbolTable())
    assert [(v.expression.to_idl(), [c.to_idl() for c in v.conditions]) for v in values] == [
        ("1", ["outer", "a"]),
        ("2", ["outer", "!a", "b"]),
        ("3", ["outer", "!a", "!b"]),
    ]
