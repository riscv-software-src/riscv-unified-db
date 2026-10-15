# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Configured values must not become loop bounds or increments."""

import pytest
from test_idl_condition_integration import symtab

from udb.idl.errors import IdlError
from udb.idl_conditions import compile_idl_condition

__all__ = ["symtab"]


@pytest.mark.parametrize(
    "text",
    [
        "for (U32 i = A[3]; i < 6; i++) { -> P > i; }",
        "for (U32 i = P; i < 66; i++) { -> P > i; }",
        "for (U32 i = P + 1; i < 67; i++) { -> P > i; }",
        "for (U32 i = 0; i < 3; i = i + P) { -> P > i; }",
        "for (U32 i = 0; i < 3; i = i + A[0]) { -> P > i; }",
    ],
)
def test_configured_parameter_loop_control_is_explicitly_rejected(symtab, text):
    original_array = symtab.get("A")
    original_values = list(original_array.value)
    with pytest.raises(IdlError, match=r"evaluatable|symbolic|parameter") as caught:
        compile_idl_condition(text, symtab, source="symbolic-loop.yaml")
    assert "symbolic-loop.yaml" in str(caught.value)
    assert symtab.get("P").value == 64
    assert symtab.get("A") is original_array
    assert original_array.value == original_values
    assert symtab.get("i") is None
    assert symtab.levels == 1
