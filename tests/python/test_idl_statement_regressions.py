# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Focused statement integration and safe unknown-write regressions."""

import pytest
from idl_semantics_helpers import make_symtab, run_semantic_case

from udb.idl import parse_constraint_body
from udb.idl.ast import ConditionalStatement, Node, UnknownLiteral
from udb.idl.errors import IdlInternalError, IdlTypeError, IdlValueUnknown
from udb.idl.parser import parse_expression, parse_function_body, parse_isa
from udb.idl.symbols import EnumDef, IdlEnvironment, SymbolTable, Var
from udb.idl.types import BOOL_TYPE, VOID_TYPE, StructType, Type, TypeKind

ISA_PROGRAM = (
    "%version: 1.0\n"
    "enum E { ONE }\n"
    "bitfield (8) B { LO 3-0 }\n"
    "struct S { Bits<8> field; }\n"
    "Bits<8> Constant = seven();\n"
    "function seven { returns Bits<8> description { seven } body { return 7; } }\n"
    "function echo { returns S arguments S value description { echo } body { return value; } }\n"
)


def test_isa_registers_types_signatures_and_globals_once(monkeypatch):
    table = SymbolTable()
    node = parse_isa(ISA_PROGRAM)
    registrations = []
    add = SymbolTable.add
    add_unique = SymbolTable.add_unique

    def record_add(self, name, value):
        if self is table:
            registrations.append(name)
        add(self, name, value)

    def record_add_unique(self, name, value):
        if self is table:
            registrations.append(name)
        add_unique(self, name, value)

    monkeypatch.setattr(SymbolTable, "add", record_add)
    monkeypatch.setattr(SymbolTable, "add_unique", record_add_unique)
    node.add_global_symbols(table)
    node.type_check(table)
    assert registrations == ["E", "B", "S", "seven", "echo", "Constant"]
    assert table.get("Constant").value == 7
    assert parse_expression("seven()").value(table) == 7


def test_isa_valid_program_signatures_and_global_initializer():
    result = run_semantic_case(
        {
            "id": "valid_isa_registration",
            "root": "isa",
            "text": ISA_PROGRAM,
            "observe": {"symbols": ["Constant"], "functions": True},
        }
    )
    assert result["ok"] is True
    assert result["symbols"]["Constant"]["value"] == {"known": True, "value": "7"}
    assert [function["name"] for function in result["functions"]] == ["seven", "echo"]
    assert result["functions"][1]["arguments"][0][0]["text"] == "struct S"
    assert result["functions"][1]["return_type"]["text"] == "struct S"


@pytest.mark.parametrize("clone", ["original", "global", "deep", "deep_without_values"])
def test_environment_builtin_enums_validate_generated_declarations(clone):
    original = SymbolTable(IdlEnvironment(builtin_enums=(EnumDef("InterruptCode", (1,), ("X",)),)))
    if clone == "global":
        table = original.global_clone()
    elif clone.startswith("deep"):
        table = original.deep_clone(clone_values=clone == "deep")
    else:
        table = original
    enum_type = table.get("InterruptCode")
    assert enum_type.is_builtin is True
    assert enum_type.element_names == ("X",)
    assert enum_type.element_values == (1,)
    node = parse_isa("%version: 1.0\ngenerated enum InterruptCode;\n")
    node.add_global_symbols(table)
    node.type_check(table)
    assert table.get("InterruptCode") is enum_type


def test_generated_enum_rejects_ordinary_user_enum():
    table = SymbolTable()
    parse_isa("%version: 1.0\nenum InterruptCode { X }\n").type_check(table)
    assert table.get("InterruptCode").is_builtin is False
    with pytest.raises(IdlTypeError, match="InterruptCode is not a builtin enum"):
        parse_isa("%version: 1.0\ngenerated enum InterruptCode;\n").type_check(table)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "text",
    [
        "-> P == true;",
        "-> 4 == true;",
        "(P == true) -> true;",
        "false -> 4 == true;",
    ],
)
def test_implication_recursively_rejects_incompatible_comparisons(text, strict):
    table = SymbolTable()
    table.add("P", Var("P", Type(TypeKind.BITS, width=8), 4))
    with pytest.raises(IdlTypeError):
        parse_constraint_body(text).type_check(table, strict=strict)


def test_implication_recursively_validates_function_argument_enum_members():
    table = SymbolTable(IdlEnvironment(builtin_enums=(EnumDef("ExtensionName", (0,), ("I",)),)))
    parse_isa(
        "%version: 1.0\n"
        "generated enum ExtensionName;\n"
        "function has_extension { returns Boolean arguments ExtensionName ext "
        "description { predicate } body { return true; } }\n"
    ).type_check(table)
    valid = parse_constraint_body("-> has_extension(ExtensionName::I);")
    valid.type_check(table)
    assert valid.satisfied(table) is True
    with pytest.raises(IdlTypeError, match="MISSING"):
        parse_constraint_body("-> has_extension(ExtensionName::MISSING);").type_check(table)


def test_implication_forwards_strict_to_both_operands(monkeypatch):
    node = parse_constraint_body("true -> false;")
    implication = node.children[0].children[0]
    table = SymbolTable()
    checked = []

    def check_operand(self, symtab, *, strict=False):
        checked.append((self, symtab, strict))

    monkeypatch.setattr(type(implication.antecedent), "type_check", check_operand)
    monkeypatch.setattr(type(implication.consequent), "type_check", check_operand)
    node.type_check(table, strict=True)
    assert checked == [
        (implication.antecedent, table, True),
        (implication.consequent, table, True),
    ]


@pytest.mark.parametrize("text", ["-> P == 4;", "(P == 4) -> P != 0;"])
def test_implication_recursive_check_preserves_valid_comparisons(text):
    table = SymbolTable()
    table.add("P", Var("P", Type(TypeKind.BITS, width=8), 4))
    node = parse_constraint_body(text)
    node.type_check(table, strict=True)
    assert node.satisfied(table) is True


@pytest.mark.parametrize("text", ["Bits<8> x; Bits<8> x;", "Bits<8> x, x;"])
def test_duplicate_declaration_policy_is_same_scope_only(text):
    table = SymbolTable()
    table.push(None)
    with pytest.raises(IdlTypeError, match=r"(already declared|Duplicate variable)"):
        parse_function_body(text).type_check(table)


def test_assignment_memoization_does_not_leak_between_equal_named_tables():
    node = parse_function_body("x = 7;")
    first = SymbolTable()
    second = SymbolTable()
    for table in (first, second):
        table.push(None)
        table.add("x", Var("x", Type(TypeKind.BITS, width=8), 0))
        node.type_check(table)
    node.children[0].execute(first)
    assert first.get("x").value == 7
    assert second.get("x").value == 0
    node.children[0].execute(second)
    assert second.get("x").value == 7


@pytest.mark.parametrize(
    ("statement", "target_type", "initial"),
    [
        (
            "x[1] = 3 if (a);",
            Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8)),
            [1, 2],
        ),
        (
            "x[1][3:0] = 3 if (a);",
            Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8)),
            [1, 2],
        ),
        ("x[3:0] = 3 if (a);", Type(TypeKind.BITS, width=8), 1),
        (
            "x.field = 3 if (a);",
            StructType("S", [Type(TypeKind.BITS, width=8)], ["field"]),
            {"field": 1},
        ),
        ("x++ if (a);", Type(TypeKind.BITS, width=8), 1),
        ("x-- if (a);", Type(TypeKind.BITS, width=8), 1),
    ],
)
def test_unknown_conditional_aggregate_and_increment_writes(statement, target_type, initial):
    table = SymbolTable()
    table.push(None)
    table.add("a", Var("a", BOOL_TYPE))
    table.add("x", Var("x", target_type, initial))
    if statement.startswith(("x++", "x--")):
        action = parse_expression(statement[:3])
        conditional = ConditionalStatement(
            source=action.source,
            start=action.start,
            end=action.end,
            children=(action, parse_expression("a")),
        )
    else:
        conditional = parse_function_body(statement).children[0]
    conditional.type_check(table)
    with pytest.raises(IdlValueUnknown):
        conditional.execute(table)
    assert table.get("x").value is None


def test_unknown_conditional_destructuring_invalidates_every_destination():
    table = make_symtab()
    parse_isa(
        "%version: 1.0\n"
        "function pair { returns Bits<8>, Bits<8> description { pair } body { return 1, 2; } }"
    ).type_check(table)
    table.push(None)
    table.add("a", Var("a", BOOL_TYPE))
    table.add("x", Var("x", Type(TypeKind.BITS, width=8), 1))
    table.add("y", Var("y", Type(TypeKind.BITS, width=8), 2))
    node = parse_function_body("(x, y) = pair() if (a);")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("x").value is None
    assert table.get("y").value is None


def test_unknown_conditional_register_write_does_not_mutate_runtime_binding():
    table = make_symtab({"mxlen": 64, "register_files": [{"name": "F", "width": 32, "count": 4}]})
    registers = table.get("F").value
    table.push(None)
    table.add("a", Var("a", BOOL_TYPE))
    node = parse_function_body("F[1] = 3 if (a);")
    node.type_check(table)
    with pytest.raises(IdlValueUnknown):
        node.children[0].execute(table)
    assert table.get("F").value is registers


def test_unsupported_invalidation_is_not_a_silent_success():
    node = parse_expression("1")
    with pytest.raises(IdlInternalError, match="nullify_assignments"):
        node.nullify_assignments(SymbolTable())


def test_void_return_and_fetch_body_in_explicit_scope():
    table = SymbolTable()
    fetch = parse_isa("%version: 1.0\nfetch { return 0; }").fetch
    table.push(fetch)
    table.add("INSTR_ENC_WIDTH", Var("INSTR_ENC_WIDTH", Type(TypeKind.BITS, width=8), 16))
    table.add("__expected_return_type", fetch.return_type(table))
    fetch.type_check(table)
    assert fetch.body.return_value(table) == 0
    assert fetch.return_type(table).width == 16
    assert fetch.const_eval(table) is True

    table.add("__expected_return_type", VOID_TYPE)
    body = parse_function_body("return;")
    body.type_check(table)
    assert body.return_value(table) == "void"
    assert body.return_values(table) == ["void"]


@pytest.mark.parametrize("clone_method", ["deep_clone", "global_clone"])
def test_clones_isolate_global_bindings_and_nested_values(clone_method):
    table = SymbolTable()
    dtype = Type(
        TypeKind.ARRAY,
        width=2,
        sub_type=Type(TypeKind.ARRAY, width=2, sub_type=Type(TypeKind.BITS, width=8)),
    )
    global_var = Var("g", dtype, [[1, 2], [3, 4]], for_loop_iter=True)
    global_var.const_incompatible()
    table.add("g", global_var)
    clone = getattr(table, clone_method)()
    clone.get("g").value[0][0] = 9
    clone.add("new", Var("new", BOOL_TYPE, True))
    assert table.get("g").value == [[1, 2], [3, 4]]
    assert table.get("new") is None
    assert clone.get("g").type is dtype
    assert clone.get("g").for_loop_iter is True
    assert clone.get("g").const_eval is False


@pytest.mark.parametrize("clone_values", [True, False])
def test_deep_clone_always_isolates_local_and_global_struct_containers(clone_values):
    dtype = StructType("S", [Type(TypeKind.ARRAY, width=2, sub_type=BOOL_TYPE)], ["flags"])
    table = SymbolTable()
    table.add("global_state", Var("global_state", dtype, {"flags": [True, False]}))
    table.push(None)
    table.add("local_state", Var("local_state", dtype, {"flags": [True, False]}))
    clone = table.deep_clone(clone_values=clone_values)
    for name in ("global_state", "local_state"):
        clone.get(name).value["flags"][0] = False
        assert table.get(name).value["flags"] == [True, False]
        assert clone.get(name).type is dtype


def test_environment_builtins_are_independent_across_tables():
    builtin = Var("g", Type(TypeKind.ARRAY, width=1, sub_type=Type(TypeKind.BITS, width=8)), [[1]])
    hook = lambda: (32, 64)
    environment = IdlEnvironment(builtin_global_vars=(builtin,), possible_xlens_cb=hook)
    first = SymbolTable(environment)
    second = SymbolTable(environment)
    first.get("g").value[0][0] = 7
    assert builtin.value == [[1]]
    assert second.get("g").value == [[1]]
    assert first.deep_clone().possible_xlens == (32, 64)


def test_function_types_evaluate_against_cloned_global_bindings():
    table = SymbolTable()
    node = parse_isa(
        "%version: 1.0\nBits<8> Param = 7;\n"
        "function read_param { returns Bits<8> description { read } body { return Param; } }"
    )
    node.type_check(table)
    clone = table.deep_clone(clone_values=True)
    clone.get("Param").value = 9
    call = parse_expression("read_param()")
    assert call.value(table) == 7
    assert call.value(clone) == 9
    assert clone.get("read_param").func_def_ast is table.get("read_param").func_def_ast


def test_expression_with_huge_width_and_small_value_avoids_mask_allocation():
    table = SymbolTable()
    table.add("x", Var("x", Type(TypeKind.BITS, width=2**64), 7))
    expression = parse_expression("(x + 1) + 1")
    expression.type_check(table)
    assert expression.value(table) == 9
    assert Node.truncate(-9, 2**64, True) == -9
    assert Node.truncate(128, 8, True) == -128
    assert Node.truncate(-129, 8, True) == 127


@pytest.mark.parametrize("signed", [False, True])
def test_huge_width_truncation_preserves_partial_unknown_bits(signed):
    value = UnknownLiteral(known_value=3, unknown_mask=4)
    assert Node.truncate(value, 2**64, signed) is value
    known = UnknownLiteral(known_value=3, unknown_mask=0)
    assert Node.truncate(known, 2**64, signed) == 3


def test_isa_fetch_checks_in_isolated_body_scope():
    table = SymbolTable()
    table.add(
        "INSTR_ENC_WIDTH", Var("INSTR_ENC_WIDTH", Type(TypeKind.BITS, width=8).make_const(), 16)
    )
    node = parse_isa("%version: 1.0\nfetch { Bits<8> local = 1; return local; }")
    node.type_check(table)
    assert table.levels == 1
    assert table.get("local") is None
    assert node.fetch.const_eval(table) is True
    assert table.get("local") is None


def test_isa_rejects_multiple_fetch_blocks_before_body_checks():
    node = parse_isa("%version: 1.0\nfetch { return 0; }\nfetch { return 1; }")
    with pytest.raises(IdlTypeError, match="Multiple fetch blocks"):
        node.type_check(SymbolTable())
