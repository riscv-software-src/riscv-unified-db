# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from udb.idl import parse
from udb.idl.passes import reachable_exceptions, reachable_functions
from udb.idl.symbols import SymbolTable


def _environment(text):
    tree = parse("%version: 1.0\n" + text, "isa")
    symtab = SymbolTable()
    tree.add_global_symbols(symtab)
    return symtab


def test_recursive_shared_cache_contains_complete_closures_for_every_vertex():
    symtab = _environment(
        "function leaf { description { leaf } body {} }"
        "function a { description { a } body { b(); } }"
        "function b { description { b } body { a(); leaf(); } }"
    )
    cache = {}
    assert {
        fn.name for fn in reachable_functions(parse("a()", "expression"), symtab, cache=cache)
    } == {
        "a",
        "b",
        "leaf",
    }
    assert {
        fn.name for fn in reachable_functions(parse("b()", "expression"), symtab, cache=cache)
    } == {
        "a",
        "b",
        "leaf",
    }
    assert sorted(sorted(fn.name for fn in closure) for closure in cache.values()) == [
        ["a", "b", "leaf"],
        ["a", "b", "leaf"],
        ["leaf"],
    ]


def test_recursive_exception_closures_do_not_cache_partial_sentinels():
    symtab = _environment(
        "function a { description { a } body { b(); raise(1); } }"
        "function b { description { b } body { a(); raise_precise(4); } }"
    )
    cache = {}
    assert reachable_exceptions(parse("a()", "expression"), symtab, cache=cache) == 18
    assert reachable_exceptions(parse("b()", "expression"), symtab, cache=cache) == 18
    assert list(cache.values()) == [18, 18]


def test_exception_call_nested_in_expression_and_false_branch_are_analyzed():
    symtab = SymbolTable()
    tree = parse("if (false) { raise(0); } else { return 1 + raise(4); }", "function_body")
    assert reachable_exceptions(tree, symtab) == 16


def test_long_transitive_chains_do_not_depend_on_python_recursion_depth():
    count = 300
    symtab = _environment(
        "\n".join(
            f"function f{index} {{ description {{ f{index} }} body {{ "
            + (f"f{index + 1}();" if index < count - 1 else "")
            + " } }"
            for index in range(count)
        )
    )
    cache = {}
    functions = reachable_functions(parse("f0()", "expression"), symtab, cache=cache)
    assert {function.name for function in functions} == {f"f{index}" for index in range(count)}
    assert len(cache) == count


def test_loop_initializer_preserves_outer_known_argument():
    symtab = _environment(
        """
        function entry {
          arguments Bits<8> i
          description { entry }
          body {
            for (Bits<8> i = 0; i < 4; i++) { i = i + 1; }
            if (i == 9) { yes(); } else { no(); }
          }
        }
        function yes { description { yes } body {} }
        function no { description { no } body {} }
        """
    )
    assert {
        function.name for function in reachable_functions(parse("entry(9)", "expression"), symtab)
    } == {"entry", "yes"}
