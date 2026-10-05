# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CSR pruning against the compiler's structural environment interface."""

from __future__ import annotations

import pytest
from idl_passes_helpers import _Csr

from udb.idl.parser import parse
from udb.idl.passes import prune
from udb.idl.symbols import IdlEnvironment, SymbolTable
from udb.idl.types import Type, TypeKind


def _symtab(value):
    csr = _Csr({"name": "demo", "address": 0x300, "length": 32, "value": value})
    return SymbolTable(IdlEnvironment(mxlen=64, csrs=(csr,)))


@pytest.mark.parametrize(
    ("forced_type", "expected"),
    [(None, "32'33"), (Type(TypeKind.BITS, width=64), "64'33")],
)
def test_known_csr_prunes_to_width_preserving_bits(forced_type, expected):
    node = parse("CSR[demo]", "expression")
    assert prune(node, _symtab(33), forced_type=forced_type).to_idl() == expected
    assert node.to_idl() == "CSR[demo]"


def test_unknown_csr_remains_symbolic():
    assert prune(parse("CSR[demo]", "expression"), _symtab(None)).to_idl() == "CSR[demo]"
