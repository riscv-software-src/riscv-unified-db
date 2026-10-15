# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Paired carried-array execution starts from independently owned equal state."""

import pytest
from test_idl_passes_scope_review_unit import _runtime
from test_idl_passes_write_scope_unit import ARRAY, INDEX_ARRAY

from udb.idl import parse
from udb.idl.passes import prune


def test_runtime_context_helper_owns_supplied_mutable_arrays():
    values = {"a": (ARRAY, [1, 2, 3]), "b": (INDEX_ARRAY, [0])}
    first = _runtime(**values)
    second = _runtime(**values)
    assert first.get("a").value is not values["a"][1]
    assert first.get("b").value is not values["b"][1]
    assert first.get("a").value is not second.get("a").value
    first.get("a").value[0] = 9
    first.get("b").value[0] = 3
    assert second.get("a").value == values["a"][1] == [1, 2, 3]
    assert second.get("b").value == values["b"][1] == [0]


@pytest.mark.parametrize("index", ["b[0]", "k"])
def test_carried_array_pruning_preserves_execution_in_independent_contexts(index):
    original = parse(
        "Bits<8> x=0; for(Bits<8> i=0;i<3;i++){"
        f"Bits<8> k=b[0]; a[{index}]=9; b[0]=b[0]+1; x=a[1];"
        "} return x;",
        "function_body",
    )
    caller = _runtime(a=(ARRAY, [1, 2, 3]), b=(INDEX_ARRAY, [0]))
    before = original.to_h()
    result = prune(original, caller)
    original_context = caller.deep_clone()
    pruned_context = caller.deep_clone()
    assert original_context.get("a").value is not pruned_context.get("a").value
    assert original_context.get("b").value is not pruned_context.get("b").value
    assert original.return_value(original_context) == 9
    assert result.return_value(pruned_context) == 9
    assert parse(result.to_idl(), "function_body").return_value(caller.deep_clone()) == 9
    assert original_context.get("a").value == pruned_context.get("a").value == [9, 9, 9]
    assert original_context.get("b").value == pruned_context.get("b").value == [3]
    assert original.to_h() == before
    assert caller.get("a").value == [1, 2, 3]
    assert caller.get("b").value == [0]
