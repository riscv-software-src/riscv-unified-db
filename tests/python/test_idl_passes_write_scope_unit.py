# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Lexical invalidation, index dependencies and explicit typo diagnostics."""

import pytest
from test_idl_passes_scope_review_unit import BITS8, _runtime

from udb.idl import parse
from udb.idl.errors import IdlTypeError
from udb.idl.passes import prune, reachable_functions
from udb.idl.types import Type, TypeKind

ARRAY = Type(TypeKind.ARRAY, width=3, sub_type=BITS8)
INDEX_ARRAY = Type(TypeKind.ARRAY, width=1, sub_type=BITS8)


@pytest.mark.parametrize("index", ["b[0]", "k"])
def test_carried_array_index_and_local_alias_keep_runtime_semantics(index):
    text = (
        "Bits<8> x=0; for(Bits<8> i=0;i<3;i++){"
        f"Bits<8> k=b[0]; a[{index}]=9; b[0]=b[0]+1; x=a[1];"
        "} return x;"
    )
    original = parse(text, "function_body")
    caller = _runtime(a=(ARRAY, [1, 2, 3]), b=(INDEX_ARRAY, [0]))
    before = original.to_h()
    result = prune(original, caller)
    values = {"a": (ARRAY, [1, 2, 3]), "b": (INDEX_ARRAY, [0])}
    assert original.return_value(_runtime(**values)) == 9
    assert result.return_value(_runtime(**values)) == 9
    assert original.to_h() == before
    assert caller.get("a").value == [1, 2, 3]
    assert caller.get("b").value == [0]


def test_constant_local_index_preserves_unwritten_array_element_precision():
    original = parse(
        "Bits<8> x=0; for(Bits<8> i=0;i<3;i++){Bits<8> k=0; a[k]=9; x=a[1];}return x;",
        "function_body",
    )
    result = prune(original, _runtime(a=(ARRAY, [1, 2, 3])))
    assert "x = 8'2;" in result.to_idl()
    assert result.return_value(_runtime(a=(ARRAY, [1, 2, 3]))) == 2


def test_shadowed_index_and_array_writes_do_not_invalidate_outer_bindings():
    original = parse(
        "for(Bits<8> i=0;i<3;i++){Bits<8> k=i; Bits<8> a[3]=[0,0,0]; a[k]=9;}return a[k];",
        "function_body",
    )
    caller = _runtime(a=(ARRAY, [1, 2, 3]), k=(BITS8, 1))
    result = prune(original, caller)
    assert result.children[-1].to_idl() == "return 8'2;"
    assert caller.get("a").value == [1, 2, 3]
    assert caller.get("k").value == 1


@pytest.mark.parametrize("analyze", [prune, reachable_functions])
@pytest.mark.parametrize(
    "body",
    [
        "for(Bits<8> i=0;i<3;i++){a[typo]=9;}",
        "for(Bits<8> i=0;i<3;i++){missing[i]=9;}",
        "for(Bits<8> i=0;i<3;i++){Bits<8> k=typo; a[k]=9;}",
    ],
)
def test_missing_symbols_are_not_converted_to_unknown(analyze, body):
    with pytest.raises(IdlTypeError, match=r"typo|missing"):
        analyze(parse(body, "function_body"), _runtime(a=(ARRAY, [1, 2, 3])))
