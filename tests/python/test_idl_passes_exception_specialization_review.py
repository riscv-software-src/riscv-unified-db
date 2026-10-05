# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Exception closures must preserve implicit writes and argument specialization."""

import pytest

from udb.idl import parse
from udb.idl.passes import reachable_exceptions
from udb.idl.symbols import SymbolTable

SOURCE = """
%version: 1.0
function walk {
  arguments Bits<8> op
  description { Read or write an implicit page-table entry. }
  body { if (op == 0) { raise(5); } else { raise(7); } }
}
function read_with_implicit_write {
  description { A read may update a page-table entry. }
  body { walk(0); walk(1); }
}
function read_without_implicit_write {
  description { The write is statically excluded. }
  body { walk(0); if (false) { walk(1); } }
}
"""


@pytest.mark.parametrize("first", [0, 1])
def test_exception_cache_keeps_distinct_scalar_argument_contexts(first):
    table = SymbolTable()
    parse(SOURCE, "isa").add_global_symbols(table)
    cache = {}
    assert reachable_exceptions(parse(f"walk({first})", "expression"), table, cache=cache) == (
        1 << (5 if first == 0 else 7)
    )
    assert reachable_exceptions(
        parse("read_with_implicit_write()", "expression"), table, cache=cache
    ) == (1 << 5) | (1 << 7)
    assert (
        reachable_exceptions(
            parse("read_without_implicit_write()", "expression"), table, cache=cache
        )
        == 1 << 5
    )
