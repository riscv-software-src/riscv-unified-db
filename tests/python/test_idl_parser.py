# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Unit tests for :mod:`udb.idl.parser` and :mod:`udb.idl.ast`.

These tests are independent of the Ruby oracle; see ``test_idl_parity.py``
for the differential comparison against the live Ruby implementation and
``data/idl/syntax/*.yaml`` for a small checked-in corpus generated from it.
"""

from __future__ import annotations

import dataclasses

import pytest

from udb.idl import (
    ArrayLiteral,
    ArraySize,
    BinaryExpression,
    ConcatenationExpression,
    FunctionCallExpression,
    Id,
    IdlSyntaxError,
    Isa,
    ParenExpression,
    ParseTimeDetectedTypeError,
    ReplicationExpression,
    TernaryOperatorExpression,
    UnaryOperatorExpression,
    UnknownLiteral,
    UserTypeName,
    from_h,
    parse,
    parse_constraint_body,
    parse_expression,
    parse_for_loop,
    parse_function_body,
    parse_instruction_operation,
    parse_isa,
)

# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "width", "value", "signed", "radix"),
    [
        ("0", 1, 0, False, 10),
        ("5", 3, 5, False, 10),
        # Ruby reports 3 here (python-migration-bugfixes.md entry 18).
        ("5s", 4, 5, True, 10),
        ("32's5", 32, 5, True, 10),
        ("0x1f", 5, 31, False, 16),
        ("0x1fs", 6, 31, True, 16),
        ("017", 4, 15, False, 10),
        ("017s", 5, 15, True, 10),
        ("0b101", 3, 5, False, 2),
        ("0b101s", 4, 5, True, 2),
        ("'0", "unknown", 0, False, 10),
        ("'d63", "unknown", 63, False, 10),
        ("'d6_3", "unknown", 63, False, 10),
        ("8'd5", 8, 5, False, 10),
        ("8'h1f", 8, 31, False, 16),
        ("8'b101", 8, 5, False, 2),
        ("8'o17", 8, 15, False, 8),
        ("8'sd5", 8, 5, True, 10),
        ("8'sh1f", 8, 31, True, 16),
        ("8'sb101", 8, 5, True, 2),
        ("8'so17", 8, 15, True, 8),
        ("MXLEN'd1", "unknown", 1, False, 10),
    ],
)
def test_int_literal_forms(text: str, width: object, value: int, signed: bool, radix: int) -> None:
    node = parse_expression(text)
    h = node.to_h()
    assert h["kind"] == "bits_literal"
    assert h["width"] == ("MXLEN" if width == "unknown" else str(width))
    assert h["value"] == value
    assert h["signed"] is signed
    assert h["radix"] == radix


def test_unknown_bits_literal_produces_known_and_unknown_masks() -> None:
    node = parse_expression("4'b1x0x")
    h = node.to_h()
    assert h["kind"] == "bits_literal"
    # 1x0x: known bits are 1 and 0 at positions 3 and 1 (0-based from MSB);
    # x positions are unknown. `to_h`'s "value" is the Ruby-`to_s`-matching
    # string form (`"<n>'b<bits>"`), matching what the Ruby oracle's
    # `JSON.generate` actually produces for a non-JSON-native `UnknownLiteral`
    # (Ruby's `json` stdlib falls back to `#to_s` via `Object#to_json`).
    assert h["value"] == str(UnknownLiteral(known_value=0b1000, unknown_mask=0b0101))
    assert h["value"] == "4'b1x0x"


def test_string_literal_has_no_escape_processing() -> None:
    node = parse_expression(r'"a\nb"')
    assert node.to_h() == {
        "kind": "string_literal",
        "text": r"a\nb",
        "source": {"file": "<idl>", "begin": 0, "end": 6},
    }


# ---------------------------------------------------------------------------
# Precedence / associativity
# ---------------------------------------------------------------------------


def test_arithmetic_precedence_binds_multiplication_tighter_than_addition() -> None:
    node = parse_expression("1 + 2 * 3")
    assert isinstance(node, BinaryExpression)
    assert node.op == "+"
    assert isinstance(node.rhs, BinaryExpression)
    assert node.rhs.op == "*"


def test_binary_operators_are_left_associative() -> None:
    node = parse_expression("1 - 2 - 3")
    assert isinstance(node, BinaryExpression)
    assert node.op == "-"
    assert isinstance(node.lhs, BinaryExpression)
    assert node.lhs.op == "-"
    assert node.lhs.lhs.to_idl() == "1"


@pytest.mark.parametrize(
    ("text", "top_op"),
    [
        ("1 || 2 && 3", "||"),
        ("1 && 2 | 3", "&&"),
        ("1 | 2 ^ 3", "|"),
        ("1 ^ 2 & 3", "^"),
        ("1 & 2 == 3", "&"),
        ("1 == 2 < 3", "=="),
        ("1 < 2 << 3", "<"),
        ("1 << 2 + 3", "<<"),
        ("1 + 2 * 3", "+"),
    ],
)
def test_precedence_ladder_p9_down_to_p0(text: str, top_op: str) -> None:
    node = parse_expression(text)
    assert isinstance(node, BinaryExpression)
    assert node.op == top_op


def test_ternary_expression() -> None:
    node = parse_expression("1 == 1 ? 2 : 3")
    assert isinstance(node, TernaryOperatorExpression)
    # `BinaryExpressionAst#to_idl` always parenthesizes (Ruby: `"(#{lhs} #{op} #{rhs})"`).
    assert node.condition.to_idl() == "(1 == 1)"
    assert node.true_expression.to_idl() == "2"
    assert node.false_expression.to_idl() == "3"


def test_implication_with_missing_antecedent_gets_synthetic_true() -> None:
    node = parse_constraint_body("-> true;")
    stmt = node.children[0]
    implication = stmt.children[0]
    assert implication.antecedent.to_idl() == "true"
    assert implication.antecedent.start == implication.antecedent.end


def test_implication_with_explicit_antecedent() -> None:
    node = parse_constraint_body("(a -> b);")
    implication = node.children[0].children[0]
    assert implication.antecedent.to_idl() == "a"
    assert implication.consequent.to_idl() == "b"


# ---------------------------------------------------------------------------
# Template-safe expressions
# ---------------------------------------------------------------------------


def test_template_safe_bits_width_with_parenthesized_comparison() -> None:
    # `p3_template_binary_operator` excludes bare `>`/`>=` inside `Bits<...>`
    # ("if you need it for an expression, enclose the expression in ()", per
    # the grammar comment); a parenthesized `>` comparison is fine since the
    # `>` is hidden inside a `paren_expr` primary.
    node = parse_function_body("Bits<(1 > 0)> x = 5;")
    decl = node.children[0].children[0]
    width_expr = decl.type_name.bits_expression
    assert isinstance(width_expr, ParenExpression)
    assert isinstance(width_expr.expression, BinaryExpression)
    assert width_expr.expression.op == ">"


def test_template_safe_right_operand_is_not_template_safe() -> None:
    # `template_safe_p4_binary_expression`'s right operand is the plain
    # (non-template-safe) `p3_binary_expression`, so once a `p4` operator
    # (e.g. `==`) is seen, the right operand can itself greedily continue
    # past a bare `>` -- even one that was meant to close the `Bits<...>`.
    # This is a real quirk in the upstream Treetop grammar (confirmed against
    # the Ruby oracle): `Bits<1 == (2 > 1)> x = 5;` is *not* parseable,
    # because the right operand of `==` greedily consumes `(2 > 1) > x` as
    # `((2 > 1) > x)`, leaving no `>` to close the `Bits<...>`.
    with pytest.raises(IdlSyntaxError) as excinfo:
        parse_function_body("Bits<1 == (2 > 1)> x = 5;")
    assert excinfo.value.offset == 21


# ---------------------------------------------------------------------------
# Comments and whitespace
# ---------------------------------------------------------------------------


def test_comment_is_pure_whitespace() -> None:
    node = parse_expression("1 + # a comment\n 2")
    assert isinstance(node, BinaryExpression)
    assert node.op == "+"


def test_unterminated_comment_is_not_whitespace() -> None:
    with pytest.raises(IdlSyntaxError):
        parse_expression("1 + # no newline before EOF")


# ---------------------------------------------------------------------------
# Reserved words (grammar itself does not reject them; type_check does, later)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word", ["if", "true", "false", "Bits", "XReg", "enum", "CSR"])
def test_reserved_words_are_not_rejected_by_the_grammar(word: str) -> None:
    # Reserved keywords used in *keyword* position still parse as that
    # keyword; here we just confirm the parser doesn't special-case them as
    # invalid `id`s in a spot the grammar doesn't otherwise constrain.
    node = parse_function_body(f"U32 {word}_var = 1;")
    assert node.children[0].children[0].lhs.name == f"{word}_var"


# ---------------------------------------------------------------------------
# `$`-builtins
# ---------------------------------------------------------------------------


def test_dollar_width() -> None:
    node = parse_expression("$width(x)")
    assert node.to_h()["kind"] == "bits_width_cast"


def test_dollar_signed() -> None:
    node = parse_expression("$signed(x)")
    assert node.to_h()["kind"] == "sign_cast"


def test_dollar_bits() -> None:
    node = parse_expression("$bits(x)")
    assert node.to_h()["kind"] == "bits_cast"


def test_dollar_array_size() -> None:
    node = parse_expression("$array_size(x)")
    assert isinstance(node, ArraySize)


def test_dollar_array_includes() -> None:
    node = parse_expression("$array_includes?(x, y)")
    assert node.to_h()["kind"] == "array_includes_funcall"


def test_dollar_enum_size_wraps_bare_id_as_user_type_name() -> None:
    node = parse_expression("$enum_size(MyEnum)")
    assert isinstance(node.enum_class_name, UserTypeName)
    assert node.enum_class_name.name == "MyEnum"


def test_dollar_enum_element_size() -> None:
    node = parse_expression("$enum_element_size(MyEnum)")
    assert isinstance(node.enum_class_name, UserTypeName)


def test_dollar_enum_to_a() -> None:
    node = parse_expression("$enum_to_a(MyEnum)")
    assert isinstance(node.enum_class_name, UserTypeName)


def test_dollar_enum_cast() -> None:
    node = parse_expression("$enum(MyEnum, x)")
    assert isinstance(node.enum_class_name, UserTypeName)
    assert node.expression.to_idl() == "x"


def test_dollar_unknown_builtin_is_a_parse_time_type_error() -> None:
    node = parse_expression("$nonexistent(x)")
    assert isinstance(node, ParseTimeDetectedTypeError)


def test_dollar_wrong_arg_count_is_a_parse_time_type_error() -> None:
    node = parse_expression("$width(x, y)")
    assert isinstance(node, ParseTimeDetectedTypeError)
    assert "expects 1 argument" in node.reason
    assert "2 given" in node.reason


def test_dollar_enum_size_wrong_arg_type_is_a_parse_time_type_error() -> None:
    node = parse_expression("$enum_size(1)")
    assert isinstance(node, ParseTimeDetectedTypeError)
    assert "expects argument 1" in node.reason


# ---------------------------------------------------------------------------
# Every root
# ---------------------------------------------------------------------------


def test_root_isa() -> None:
    node = parse_isa('%version: 1.0\ninclude "foo.idl"\n')
    assert isinstance(node, Isa)
    assert node.children[0].filename == "foo.idl"


def test_root_function_body() -> None:
    node = parse_function_body("X[rd] = 1; return;")
    assert node.to_h()["kind"] == "function_body"
    assert len(node.children) == 2


def test_root_instruction_operation() -> None:
    node = parse_instruction_operation("X[rd] = X[rs1] + X[rs2];")
    assert node.to_h()["kind"] == "function_body"


def test_root_expression() -> None:
    node = parse_expression("1 + 1")
    assert isinstance(node, BinaryExpression)


def test_root_constraint_body() -> None:
    node = parse_constraint_body("a -> b;")
    assert node.to_h()["kind"] == "constraint_body"


def test_root_for_loop() -> None:
    node = parse_for_loop("for (U32 i = 0; i < 4; i++) { X[i] = 0; }")
    assert node.to_h()["kind"] == "for_loop_stmt"


def test_unknown_root_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown IDL parse root"):
        parse("1", root="not_a_root")


# ---------------------------------------------------------------------------
# Syntax errors: offset / line / column
# ---------------------------------------------------------------------------


def test_syntax_error_reports_offset_line_column() -> None:
    with pytest.raises(IdlSyntaxError) as excinfo:
        parse_expression("1 + ")
    error = excinfo.value
    assert error.offset == 4
    assert error.line == 1
    assert error.column == 5


def test_syntax_error_line_column_after_newlines() -> None:
    with pytest.raises(IdlSyntaxError) as excinfo:
        parse_function_body("X[rd] = 1;\nX[rd] = ;")
    error = excinfo.value
    assert error.line == 2
    assert error.column == 9


def test_syntax_error_reports_expected_terminals() -> None:
    with pytest.raises(IdlSyntaxError) as excinfo:
        parse_expression("1 +")
    assert excinfo.value.expected


def test_trailing_garbage_after_a_complete_parse_is_a_syntax_error() -> None:
    with pytest.raises(IdlSyntaxError):
        parse_expression("1 + 1 garbage")


# ---------------------------------------------------------------------------
# `to_idl` reparse round trip
# ---------------------------------------------------------------------------


def _strip_source(value: object) -> object:
    """Recursively drop ``"source"`` entries from a ``to_h()`` dict.

    ``to_idl()`` output need not have the same text length/spacing as the
    original source (e.g. ``"{1, 2, 3}"`` re-renders as ``"{1,2,3}"``), so a
    "reparses to an equivalent tree" check must ignore ``source`` (character
    offsets) and compare only the structural/semantic content.
    """
    if isinstance(value, dict):
        return {k: _strip_source(v) for k, v in value.items() if k != "source"}
    if isinstance(value, list):
        return [_strip_source(v) for v in value]
    return value


# Cases whose `to_idl()` output re-parses to a *structurally identical* tree
# (ignoring source offsets, which naturally shift with `to_idl()`'s spacing).
# Ruby's `BinaryExpressionAst#to_idl` unconditionally parenthesizes
# (`"(#{lhs} #{op} #{rhs})"`), so any case containing a bare (unparenthesized
# in the source) `BinaryExpression` anywhere in the tree gains one extra
# `ParenExpression` wrapper at that spot once round-tripped through
# `to_idl()` -- semantically equivalent, but not structurally identical. Such
# cases are covered separately below by a syntactic-validity-only check.
@pytest.mark.parametrize(
    ("root", "text"),
    [
        ("expression", "a ? b : c"),
        ("expression", "{1, 2, 3}"),
        ("expression", "{4{1'b1}}"),
        ("expression", "[1, 2, 3]"),
        ("expression", "-x++"),
        ("expression", "$enum_size(MyEnum)"),
        ("expression", "$array_includes?(a, 1)"),
        ("function_body", "XReg v = CSR[mstatus].sw_read();\n"),
        ("constraint_body", "a -> b;"),
    ],
)
def test_to_idl_reparses_to_an_equivalent_tree(root: str, text: str) -> None:
    node = parse(text, root)
    reparsed = parse(node.to_idl(), root)
    assert _strip_source(node.to_h()) == _strip_source(reparsed.to_h())


@pytest.mark.parametrize(
    ("root", "text"),
    [
        ("expression", "1 + 2 * (3 - 4)"),
        ("function_body", "U32 x = 1;\nif (x == 1) {\n  return x;\n} else {\n  return 0;\n}"),
        ("for_loop", "for (U32 i = 0; i < 4; i++) { X[i] = 0; }"),
    ],
)
def test_to_idl_reparses_without_error_for_binary_expressions(root: str, text: str) -> None:
    # `to_idl()`'s extra parenthesization (see above) changes tree shape but
    # must still be valid, reparseable IDL.
    node = parse(text, root)
    parse(node.to_idl(), root)


# ---------------------------------------------------------------------------
# `from_h(to_h(x)) == x` round trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("root", "text"),
    [
        ("expression", "1 + 2 * 3"),
        ("expression", "a.b"),
        ("expression", "f(1, 2)"),
        ("expression", "CSR[mstatus]"),
        ("expression", "CSR[mstatus].MIE"),
        ("expression", "x[3]"),
        ("expression", "x[3:0]"),
        ("expression", "$enum(MyEnum, x)"),
        ("function_body", "U32 x = 1; return x;"),
        ("for_loop", "for (U32 i = 0; i < 4; i++) { X[i] = 0; }"),
        ("constraint_body", "a -> b;"),
        ("isa", "%version: 1.0\nenum Foo { A 0 B 1 }\n"),
    ],
)
def test_from_h_of_to_h_round_trips(root: str, text: str) -> None:
    node = parse(text, root, label="case")
    data = node.to_h()
    rebuilt = from_h(data, {"case": text})
    assert rebuilt.to_h() == data


# ---------------------------------------------------------------------------
# Frozen-tree enforcement
# ---------------------------------------------------------------------------


def test_nodes_are_frozen() -> None:
    node = parse_expression("1 + 1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.start = 99  # type: ignore[misc]


def test_children_have_a_parent_link() -> None:
    node = parse_expression("1 + 1")
    assert isinstance(node, BinaryExpression)
    assert node.lhs.parent is node
    assert node.rhs.parent is node


# ---------------------------------------------------------------------------
# Misc: array access, field access, function calls, concatenation, replication
# ---------------------------------------------------------------------------


def test_array_element_and_range_access() -> None:
    node = parse_expression("x[3:0]")
    assert node.to_h()["kind"] == "array_range_access"
    node2 = parse_expression("x[3]")
    assert node2.to_h()["kind"] == "array_access"


def test_function_call_with_arguments() -> None:
    node = parse_expression("f(1, 2, 3)")
    assert isinstance(node, FunctionCallExpression)
    assert len(node.args) == 3


def test_concatenation_and_replication() -> None:
    node = parse_expression("{1, 2}")
    assert isinstance(node, ConcatenationExpression)
    node2 = parse_expression("{4{1'b1}}")
    assert isinstance(node2, ReplicationExpression)


def test_array_literal() -> None:
    node = parse_expression("[1, 2, 3]")
    assert isinstance(node, ArrayLiteral)
    assert len(node.children) == 3


def test_unary_operators() -> None:
    node = parse_expression("!x")
    assert isinstance(node, UnaryOperatorExpression)
    assert node.op == "!"


def test_id_expression() -> None:
    node = parse_expression("some_var")
    assert isinstance(node, Id)
    assert node.name == "some_var"
