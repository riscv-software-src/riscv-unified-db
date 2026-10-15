# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import pytest
from test_idl_passes_review_regressions import BITS8, functions, scoped_table

from udb.idl import parse
from udb.idl.passes import prune, reachable_functions
from udb.idl.symbols import Var
from udb.idl.types import Type, TypeKind

ARRAY = Type(TypeKind.ARRAY, width=3, sub_type=BITS8)
LOOPS = [
    "for(Bits<8> i=0;i<3;i++){Bits<8> k=i; a[k]=9;}",
    "for(Bits<8> i=0;i<2;i++){for(Bits<8> k=0;k<3;k++){a[k]=9;}}",
]


@pytest.mark.parametrize("loop", LOOPS)
def test_local_and_nested_loop_indices_preserve_pruned_execution(loop):
    original = parse(loop + "return a[0];", "function_body")
    caller = scoped_table(a=(ARRAY, [1, 2, 3]))
    result = prune(original, caller)
    assert caller.get("a").value == [1, 2, 3]
    assert original.return_value(scoped_table(a=(ARRAY, [1, 2, 3]))) == 9
    assert result.return_value(scoped_table(a=(ARRAY, [1, 2, 3]))) == 9


@pytest.mark.parametrize("loop", LOOPS)
def test_local_and_nested_loop_indices_do_not_break_reachability(loop):
    _, table = functions(
        "function c {description {c} body {}}"
        "function g {description {g} body {" + loop + "if(a[0]==9){c();}}}"
    )
    table.add("a", Var("a", ARRAY, [1, 2, 3]))
    assert {callee.name for callee in reachable_functions(table.get("g").func_def_ast, table)} == {
        "c"
    }
    assert table.get("a").value == [1, 2, 3]


@pytest.mark.parametrize("action", ["a[b[0]]=9;", "Bits<8> x=a[b[0]];"])
def test_unknown_element_used_as_index_remains_symbolic_in_pruning(action):
    array = Type(TypeKind.ARRAY, width=1, sub_type=BITS8)
    caller = scoped_table(a=(ARRAY, [1, 2, 3]), b=(array, [0]), u=(BITS8, None))
    original = parse("if(u==1){b[0]=1;}" + action + "return a[0];", "function_body")
    result = prune(original, caller)
    for flag in (0, 1):
        values = {"a": (ARRAY, [1, 2, 3]), "b": (array, [0]), "u": (BITS8, flag)}
        assert result.return_value(scoped_table(**values)) == original.return_value(
            scoped_table(**values)
        )
    assert caller.get("a").value == [1, 2, 3]
    assert caller.get("b").value == [0]
