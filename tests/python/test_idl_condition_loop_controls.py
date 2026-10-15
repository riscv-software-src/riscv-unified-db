# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Static loop controls preserve parameter dependencies and lexical bindings."""

import pytest
from test_idl_condition_integration import symtab

from udb.conditions import normalize, parse_condition
from udb.idl import IdlSource, parse_isa
from udb.idl.errors import IdlError
from udb.idl.symbols import Var
from udb.idl_conditions import compile_idl_condition

__all__ = ["symtab"]


def _functions(table, text):
    for function in parse_isa("%version: 1.0\n" + text).functions:
        function.add_symbol(table)


@pytest.mark.parametrize(
    "text",
    [
        "for (U32 i = 0; i < P; i++) { -> P > i; }",
        "for (U32 i = 0; i < A[0]; i++) { -> P > i; }",
        "for (U32 i = 0; i < 2; i++) { for (U32 j = A[i]; j < 8; j++) { -> P > j; } }",
        "for (U32 i = 0; i < 0; i = i + P) { -> P > i; }",
    ],
)
def test_symbolic_controls_are_rejected_before_unrolling(symtab, text):
    before = symtab.snapshot_values()
    source = IdlSource(text, label="loop-control.yaml", starting_line=30)
    with pytest.raises(IdlError, match="symbolic") as caught:
        compile_idl_condition(text, symtab, source=source)
    assert "loop-control.yaml" in str(caught.value)
    assert caught.value.node.lineno == 31
    assert symtab.snapshot_values() == before
    assert symtab.levels == 1
    assert symtab.get("i") is None
    assert symtab.get("j") is None


@pytest.mark.parametrize(
    "text",
    [
        "for (U32 i = parameter_start(); i < 66; i++) { -> P > i; }",
        "for (U32 i = alias_start(); i < 66; i++) { -> P > i; }",
        "for (U32 i = 0; i < 3; i = i + alias_start()) { -> P > i; }",
        "for (U32 i = 0; i < alias_start(); i++) { -> P > i; }",
    ],
)
def test_parameter_reads_through_function_aliases_are_symbolic(symtab, text):
    _functions(
        symtab,
        """
function parameter_start {
  returns U32
  description { Parameter-dependent control. }
  body { U32 alias = P; return alias; }
}
function alias_start {
  returns U32
  description { Indirect parameter-dependent control. }
  body { return parameter_start(); }
}
""",
    )
    before = symtab.snapshot_values()
    with pytest.raises(IdlError, match="symbolic") as caught:
        compile_idl_condition(text, symtab, source="alias-loop.yaml")
    assert "alias-loop.yaml" in str(caught.value)
    assert symtab.snapshot_values() == before
    assert symtab.levels == 1


@pytest.mark.parametrize(
    "text",
    [
        "for (U32 i = 0; i < 2; i++) { for (U32 j = i; j < i + 1; j++) { -> A[j] > j; } }",
        "for (U32 P = 0; P < 2; P++) { -> A[P] > P; }",
        "for (U32 i = start(0); i < 2; i = i + start(1)) { -> A[i] > i; }",
        "for (U32 i = 0; i < 2; i = i + local_start()) { -> A[i] > i; }",
    ],
)
def test_constant_local_and_shadowed_controls_remain_valid(symtab, text):
    _functions(
        symtab,
        """
function start {
  returns U32
  arguments U32 P
  description { The argument shadows the global parameter. }
  body { U32 value = P; return value; }
}
function local_start {
  returns U32
  description { The local constant shadows the global parameter. }
  body { U32 P = 1; return P; }
}
""",
    )
    before = symtab.snapshot_values()
    condition = compile_idl_condition(text, symtab)
    expected = parse_condition(
        {
            "allOf": [
                {"param": {"name": "A", "index": 0, "greaterThan": 0}},
                {"param": {"name": "A", "index": 1, "greaterThan": 1}},
            ]
        }
    )
    assert normalize(condition) == normalize(expected)
    assert symtab.snapshot_values() == before
    assert symtab.get("P").value == 64
    assert symtab.get("i") is None
    assert symtab.get("j") is None


def test_function_globals_are_not_hidden_by_caller_local_bindings(symtab):
    _functions(
        symtab,
        """
function parameter_start {
  returns U32
  description { Always reads the global parameter. }
  body { return P; }
}
""",
    )
    original = symtab.get("P")
    symtab.push()
    local = Var("P", original.type, 0)
    symtab.add("P", local)
    before = symtab.snapshot_values()
    try:
        with pytest.raises(IdlError, match="symbolic"):
            compile_idl_condition(
                "for (U32 i = parameter_start(); i < 66; i++) { -> A[0] > i; }",
                symtab,
                source="caller-shadow.yaml",
            )
        assert symtab.levels == 2
        assert symtab.get("P") is local
        assert original.value == 64
        assert symtab.snapshot_values() == before
        assert symtab.get("i") is None
    finally:
        symtab.pop()
