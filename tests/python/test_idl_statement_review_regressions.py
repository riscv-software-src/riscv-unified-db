# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Compiler-owned corrections found during statement integration review."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from idl_semantics_helpers import run_semantic_case

from udb.idl.errors import IdlTypeError, IdlValueUnknown
from udb.idl.parser import parse_expression, parse_function_body, parse_isa
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import BOOL_TYPE, BitfieldType, Qualifier, Type, TypeKind

BITS8 = Type(TypeKind.BITS, width=8)


@pytest.mark.parametrize(
    ("text", "dtype", "value"),
    [
        ("a[u] = 7;", Type(TypeKind.ARRAY, width=2, sub_type=BITS8), [5, 6]),
        (
            "a[u][0] = 7;",
            Type(
                TypeKind.ARRAY,
                width=2,
                sub_type=Type(TypeKind.ARRAY, width=2, sub_type=BITS8),
            ),
            [[5, 6], [7, 8]],
        ),
        (
            "a[0][u] = 7;",
            Type(
                TypeKind.ARRAY,
                width=2,
                sub_type=Type(TypeKind.ARRAY, width=2, sub_type=BITS8),
            ),
            [[5, 6], [7, 8]],
        ),
    ],
)
def test_unknown_array_write_index_invalidates_root(text, dtype, value):
    table = SymbolTable()
    table.push(None)
    table.add("a", Var("a", dtype, value))
    table.add("u", Var("u", BITS8))
    node = parse_function_body(text)
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.execute(table)
    assert table.get("a").value is None


def test_unknown_bitfield_rhs_invalidates_root():
    table = SymbolTable()
    table.push(None)
    table.add("flags", Var("flags", BitfieldType("Flags", 8, ("LOW",), (range(8),)), 5))
    table.add("u", Var("u", BITS8))
    node = parse_function_body("flags.LOW = u;")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.execute(table)
    assert table.get("flags").value is None


def test_assignment_resolves_recreated_variable_binding():
    table = SymbolTable()
    table.push(None)
    table.add("x", Var("x", BITS8, 1))
    node = parse_function_body("x = x + 1;")
    node.type_check(table)
    node.children[0].execute(table)
    assert table.get("x").value == 2
    replacement = Var("x", BITS8, 3)
    table.add("x", replacement)
    node.children[0].execute(table)
    assert replacement.value == 4


def test_loop_body_redeclarations_and_repeated_evaluations_use_current_bindings():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": (
                "Bits<8> s = 0; for (Bits<8> i = 0; i < 3; i++) { "
                "Bits<8> x = 5; x = x + 1; s = s + x; } return s;"
            ),
            "return_type": "Bits<8>",
            "observe": {"return": True},
        }
    )
    assert result["ok"] is True
    assert result["return_value"] == {"known": True, "value": "18"}
    assert result["return_values"] == {"known": True, "value": ["18"]}


@pytest.mark.parametrize("width", [32, 64])
@pytest.mark.parametrize("value", [None, 0, 1])
def test_csr_bits_cast_uses_metadata_width_and_propagates_unknown(width, value):
    csr = SimpleNamespace(name="mockcsr", max_length=width, value=value)
    table = SymbolTable(IdlEnvironment(csrs=(csr,)))
    expression = parse_expression("$bits(CSR[mockcsr])")
    expression.type_check(table)
    assert expression.type(table).kind == TypeKind.BITS
    assert expression.type(table).width == width
    assert expression.const_eval(table) is (value is not None)
    if value is None:
        with pytest.raises(IdlValueUnknown):
            expression.value(table)
    else:
        assert expression.value(table) == value
    table.push(None)
    declaration = parse_function_body(f"Bits<{width}> tmp = $bits(CSR[mockcsr]);")
    declaration.type_check(table)
    if value is None:
        with pytest.raises(IdlValueUnknown):
            declaration.children[0].execute(table)
    else:
        declaration.children[0].execute(table)
    assert table.get("tmp").value == value


@pytest.mark.parametrize(
    "text",
    [
        "if (b) { s = 5; }",
        "if (false) { s = 3; } else if (b) { s = 5; }",
        "if (b) { if (true) { s = 5; } }",
        "if (b) { for (Bits<8> i = 0; i < 2; i++) { s = s + 1; } }",
    ],
)
def test_unknown_block_branches_invalidate_written_scalars(text):
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.push(None)
    table.add("s", Var("s", BITS8, 0))
    node = parse_function_body(text)
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("s").value is None


def test_unknown_branch_invalidates_all_possible_bodies_not_unreachable_else():
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.push(None)
    table.add("s", Var("s", BITS8, 1))
    table.add("x", Var("x", BITS8, 2))
    node = parse_function_body("if (b) { s = 5; } else if (true) { s = 6; } else { x = 9; }")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("s").value is None
    assert table.get("x").value == 2


def test_unknown_branch_invalidation_respects_local_shadowing():
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.push(None)
    outer = Var("s", BITS8, 7)
    table.add("s", outer)
    node = parse_function_body("if (b) { Bits<8> s = 3; s = 5; }")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("s") is outer
    assert outer.value == 7
    assert table.levels == 2


def test_unknown_branch_invalidates_nested_array_without_evaluating_index():
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.push(None)
    table.add("u", Var("u", BITS8))
    table.add(
        "a",
        Var(
            "a",
            Type(
                TypeKind.ARRAY,
                width=2,
                sub_type=Type(TypeKind.ARRAY, width=2, sub_type=BITS8),
            ),
            [[1, 2], [3, 4]],
        ),
    )
    node = parse_function_body("if (b) { a[u][0] = 5; }")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("a").value is None


@pytest.mark.parametrize("condition", ["true", "false"])
def test_known_block_branch_executes_only_taken_body(condition):
    table = SymbolTable()
    table.push(None)
    table.add("s", Var("s", BITS8, 0))
    node = parse_function_body(f"if ({condition}) {{ s = 5; }} else {{ s = 7; }}")
    node.type_check(table)
    node.children[0].execute(table)
    assert table.get("s").value == (5 if condition == "true" else 7)


def test_unknown_block_return_analysis_never_fabricates_definite_branch_write():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "Bits<8> s = 0; if (b) { s = 5; } return s;",
            "setup": {"vars": [{"name": "b", "type": "Boolean"}]},
            "return_type": "Bits<8>",
            "observe": {"return": True, "symbols": ["s"]},
        }
    )
    assert result["ok"] is True
    assert result["return_value"]["known"] is False
    assert result["return_values"]["known"] is False
    assert result["symbols"]["s"]["value"]["known"] is False


def test_unknown_block_literal_return_alternatives_are_preserved():
    result = run_semantic_case(
        {
            "root": "function_body",
            "text": "if (b) { return 1; } else { return 2; }",
            "setup": {"vars": [{"name": "b", "type": "Boolean"}]},
            "return_type": "Bits<8>",
            "observe": {"return": True},
        }
    )
    assert result["ok"] is True
    assert result["return_values"] == {"known": True, "value": ["1", "2"]}


@pytest.mark.parametrize("condition", ["true", "b", "false"])
@pytest.mark.parametrize("builtin", [True, False])
def test_conditional_runtime_calls_raise_unknown_not_internal(condition, builtin):
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    declaration = (
        "builtin function action { arguments Bits<8> c description { runtime } }"
        if builtin
        else "function action { arguments Bits<8> c description { runtime } body { } }"
    )
    parse_isa("%version: 1.0\n" + declaration).type_check(table)
    table.push(None)
    table.add("__expected_return_type", BITS8)
    node = parse_function_body(f"action(1) if ({condition}); return 4;")
    node.type_check(table)
    if condition == "false":
        assert node.return_value(table) == 4
    else:
        with pytest.raises(IdlValueUnknown):
            node.return_value(table)


@pytest.mark.parametrize("condition", ["true", "b", "false"])
def test_conditional_calls_invalidate_aggregate_arguments_and_written_globals(condition):
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.add("counter", Var("counter", BITS8, 5))
    table.add("unrelated", Var("unrelated", BITS8, 9))
    parse_isa(
        "%version: 1.0\n"
        "function action { arguments Bits<8> values[2] description { mutation } "
        "body { values[0] = 7; counter = 8; } }"
    ).type_check(table)
    table.push(None)
    table.add("__expected_return_type", BITS8)
    table.add("values", Var("values", Type(TypeKind.ARRAY, width=2, sub_type=BITS8), [1, 2]))
    local_counter = Var("counter", BITS8, 42)
    table.add("counter", local_counter)
    node = parse_function_body(f"action(values) if ({condition}); return 4;")
    node.type_check(table)
    if condition == "false":
        assert node.return_value(table) == 4
        assert table.get("values").value == [1, 2]
        assert table.get_global("counter").value == 5
    else:
        with pytest.raises(IdlValueUnknown):
            node.return_value(table)
        assert table.get("values").value is None
        assert table.get_global("counter").value is None
    assert local_counter.value == 42
    assert table.get_global("unrelated").value == 9


def test_unknown_call_does_not_invalidate_value_copied_scalar_argument():
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.add("c", Var("c", BITS8, 3))
    parse_isa(
        "%version: 1.0\n"
        "function action { arguments Bits<8> c description { local } body { c = 9; } }"
    ).type_check(table)
    table.push(None)
    node = parse_function_body("action(c) if (b);")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("c").value == 3


@pytest.mark.parametrize("condition", ["true", "b"])
def test_conditional_call_never_mutates_runtime_global_argument(condition):
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    parse_isa(
        "%version: 1.0\n"
        "function action { arguments Bits<8> values[2] description { mutation } "
        "body { values[0] = 7; } }"
    ).type_check(table)
    table.push(None)
    contents = [1, 2]
    table.add(
        "registers",
        Var(
            "registers",
            Type(
                TypeKind.ARRAY,
                width=2,
                sub_type=BITS8,
                qualifiers=(Qualifier.GLOBAL,),
            ),
            contents,
        ),
    )
    node = parse_function_body(f"action(registers) if ({condition});")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("registers").value is contents
    assert contents == [1, 2]


def test_call_invalidation_follows_transitive_globals_without_recursive_execution():
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.add("counter", Var("counter", BITS8, 5))
    table.add("unrelated", Var("unrelated", BITS8, 9))
    parse_isa(
        "%version: 1.0\n"
        "function helper { description { mutation } body { counter = 8; } }\n"
        "function action { description { transit } body { helper(); } }\n"
    ).type_check(table)
    table.push(None)
    node = parse_function_body("action() if (b);")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get_global("counter").value is None
    assert table.get_global("unrelated").value == 9


@pytest.mark.parametrize(
    "name",
    [
        "softfloat_approxRecip_1k0s",
        "softfloat_approxRecip_1k1s",
        "softfloat_approxRecipSqrt_1k0s",
        "softfloat_approxRecipSqrt_1k1s",
    ],
)
def test_genuine_fp_lookup_table_global_registration_uses_declared_array_type(name):
    path = Path(__file__).resolve().parents[2] / "spec/std/isa/isa/fp.idl"
    source = path.read_text()
    start = source.index(f"Bits<16> {name}[16] = [")
    declaration = source[start : source.index("];", start) + 2]
    table = SymbolTable()
    node = parse_isa("%version: 1.0\n" + declaration)
    node.add_global_symbols(table)
    assert table.get(name).type.width == 16
    assert table.get(name).type.sub_type.width == 16
    if name.endswith("1k1s"):
        with pytest.raises(IdlTypeError, match="Array elements must be identical"):
            node.type_check(table)
    else:
        node.type_check(table)


def test_homogeneous_boolean_array_initializer_retains_existing_semantics():
    table = SymbolTable()
    table.push(None)
    node = parse_function_body("Boolean values[3] = [true, false, true];")
    node.type_check(table)
    action = node.children[0].action
    action.add_symbol(table)
    assert table.get("values").value == [True, False, True]


@pytest.mark.parametrize(
    "text",
    [
        "Bits<16> values[2] = [1, true];",
        "Boolean values[2] = [true, 1];",
        "Bits<16> values[2] = [1, 7, 255];",
    ],
)
def test_array_initializer_rejects_incompatible_types_and_lengths(text):
    table = SymbolTable()
    table.push(None)
    with pytest.raises(IdlTypeError):
        parse_function_body(text).type_check(table)


def test_standalone_array_literal_rejects_incompatible_kinds():
    with pytest.raises(IdlTypeError, match="Array elements must be identical"):
        parse_expression("[1, true]").type_check(SymbolTable())


@pytest.mark.parametrize(
    "text",
    ["Bits<16> values[3] = [1, 7, 255];", "Bits<16> values[3] = ([1, 7, 255]);"],
)
def test_global_registration_is_separate_from_array_rhs_typechecking(text):
    table = SymbolTable()
    node = parse_isa("%version: 1.0\n" + text)
    node.add_global_symbols(table)
    assert table.get("values").type.sub_type.width == 16
    with pytest.raises(IdlTypeError, match="Array elements must be identical"):
        node.type_check(table)


def test_argument_dependent_return_and_argument_types_bind_parameters_in_order():
    table = SymbolTable()
    node = parse_isa(
        "%version: 1.0\n"
        "function zeros { returns Bits<N> arguments Bits<8> N description { zeros } "
        "body { return 0; } }\n"
        "function width { returns Bits<16> arguments Bits<8> N, Bits<N> x "
        "description { dependent } body { return $width(x); } }\n"
    )
    node.type_check(table)
    for size in (8, 16, 8):
        assert parse_expression(f"zeros({size})").type(table).width == size
        assert parse_expression(f"zeros({size})").value(table) == 0
        call = parse_expression(f"width({size}, 1)")
        call.type_check(table)
        assert call.value(table) == size


@pytest.mark.parametrize("text", ["Bits<8> x = true;", "Boolean x = 1;"])
def test_explicit_isa_check_rejects_registered_incompatible_global_rhs(text):
    table = SymbolTable()
    node = parse_isa("%version: 1.0\n" + text)
    node.add_global_symbols(table)
    assert isinstance(table.get("x"), Var)
    with pytest.raises(IdlTypeError, match="Incompatible type"):
        node.type_check(table)


def test_duplicate_source_global_constants_are_rejected():
    with pytest.raises(IdlTypeError, match="already declared in this scope"):
        parse_isa("%version: 1.0\nBits<8> K = 1;\nBits<8> K = 2;").add_global_symbols(SymbolTable())


@pytest.mark.parametrize("freeze", [False, True])
def test_unknown_calls_invalidate_transitive_and_opaque_global_writes(freeze):
    table = SymbolTable()
    table.add("b", Var("b", BOOL_TYPE))
    table.add("counter", Var("counter", BITS8, 5))
    table.add("other", Var("other", BITS8, 6))
    table.add("P", Var("P", BITS8, 7, param=True))
    table.add("C", Var("C", Type(TypeKind.BITS, width=8, qualifiers=(Qualifier.CONST,)), 8))
    parse_isa(
        "%version: 1.0\n"
        "builtin function opaque { description { runtime } }\n"
        "function inner { description { inner } body { counter = 1; } }\n"
        "function outer { description { outer } body { inner(); } }\n"
        "function hidden { description { hidden } body { opaque(); } }"
    ).type_check(table)
    if freeze:
        table.freeze_globals()
        table = table.global_clone()
    table.push(None)
    table.add("__expected_return_type", BITS8)

    for call, cleared in (("outer", {"counter"}), ("hidden", {"counter", "other"})):
        caller = table.deep_clone()
        caller.get_global("counter").value = 5
        node = parse_function_body(f"{call}() if (b); return 4;")
        node.type_check(caller)
        with pytest.raises(IdlValueUnknown):
            node.return_value(caller)
        for name, value in (("counter", 5), ("other", 6), ("P", 7), ("C", 8)):
            expected = None if name in cleared else value
            assert caller.get_global(name).value == expected
        assert table.get_global("counter").value == 5


@pytest.mark.parametrize("freeze", [False, True])
def test_function_return_values_are_reused_only_for_equal_globals_and_arguments(freeze):
    table = SymbolTable()
    table.add("g", Var("g", BITS8, 3))
    table.add("u", Var("u", BITS8))
    parse_isa(
        "%version: 1.0\n"
        "function scaled { returns Bits<8> arguments Bits<8> x description { scaled } "
        "body { return x + g; } }\n"
        "function guarded { returns Bits<8> description { guarded } body { "
        "if (u == 0) { return 1; } return 2; } }"
    ).type_check(table)
    if freeze:
        table.freeze_globals()
        table = table.global_clone()
    table.push(None)
    table.add("__expected_return_type", BITS8)
    definition = table.get("scaled").func_def_ast
    calls = []
    original = type(definition.body).return_value

    def counting(body, symtab):
        calls.append(body)
        return original(body, symtab)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(type(definition.body), "return_value", counting)
        assert parse_expression("scaled(1)").value(table) == 4
        assert parse_expression("scaled(1)").value(table.deep_clone()) == 4
        assert len(calls) == 1
        assert parse_expression("scaled(2)").value(table) == 5
        assert len(calls) == 2
        changed = table.deep_clone()
        changed.get_global("g").value = 10
        assert parse_expression("scaled(1)").value(changed) == 11
        assert len(calls) == 3
        unknown = table.deep_clone()
        unknown.get_global("g").value = None
        for _ in range(2):
            with pytest.raises(IdlValueUnknown):
                parse_expression("scaled(1)").value(unknown)
        assert len(calls) == 4
        for _ in range(2):
            with pytest.raises(IdlValueUnknown):
                parse_expression("guarded()").value(table)
        assert len(calls) == 5
        known = table.deep_clone()
        known.get_global("u").value = 0
        assert parse_expression("guarded()").value(known) == 1
