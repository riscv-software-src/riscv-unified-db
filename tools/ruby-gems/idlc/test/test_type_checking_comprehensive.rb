# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "idlc"
require "idlc/ast"
require_relative "helpers"
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

# Comprehensive type checking tests based on doc/idl.adoc
# Tests are organized by documentation sections to ensure alignment
class TestTypeCheckingComprehensive < Minitest::Test
  include TestMixin

  def setup
    @symtab = Idl::SymbolTable.new(
      possible_xlens_cb: proc { [32, 64] }
    )
    @compiler = Idl::Compiler.new
  end

  # ============================================================================
  # Section: Data Types → Primitive Types → Bits<N>
  # ============================================================================

  def test_bits_type_with_literal_width
    idl = "Bits<32> x = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind
    assert_equal 32, ast.action.lhs.type(@symtab).width
  end

  def test_bits_type_with_config_param_width
    # MXLEN is a configuration parameter available in symtab
    @symtab.add("MXLEN", Idl::Var.new("MXLEN", Idl::Type.new(:bits, width: 7, qualifiers: [:const])))
    idl = "Bits<MXLEN> x = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind
    # Width should be :unknown since MXLEN is runtime-dependent
    assert_equal :unknown, ast.action.lhs.type(@symtab).width
  end

  def test_bits_type_with_expression_width
    idl = "Bits<{8, 1'b0}> x = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind
    assert_equal 16, ast.action.lhs.type(@symtab).width
  end

  def test_bits_type_aliases
    # Test XReg alias (Bits<MXLEN>)
    idl = "XReg x = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind

    # Test U64 alias (Bits<64>)
    idl = "U64 y = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind
    assert_equal 64, ast.action.lhs.type(@symtab).width

    # Test U32 alias (Bits<32>)
    idl = "U32 z = 0;"
    ast = compile_statement(idl)
    assert_equal :bits, ast.action.lhs.type(@symtab).kind
    assert_equal 32, ast.action.lhs.type(@symtab).width
  end

  # ============================================================================
  # Section: Data Types → Primitive Types → Boolean
  # ============================================================================

  def test_boolean_type_declaration
    idl = "Boolean flag = true;"
    ast = compile_statement(idl)
    assert_equal :boolean, ast.action.lhs.type(@symtab).kind
  end

  def test_boolean_cannot_mix_with_bits
    # Boolean and Bits<N> are incompatible
    idl = "Boolean flag = 1;"
    assert_raises(Idl::AstNode::TypeError) do
      compile_statement(idl)
    end
  end

  # ============================================================================
  # Section: Data Types → Composite Types → Enumerations
  # ============================================================================

  def test_enum_member_type
    enum_def = <<~IDL
      enum MyEnum {
        Member1 0
        Member2 1
        Member3 2
      }
    IDL
    compile_and_add_to_symtab(enum_def.strip, :enum_definition)

    idl = "MyEnum::Member1"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :enum_ref, type.kind
    assert_equal "MyEnum", type.enum_class.name
  end

  def test_enum_member_must_be_qualified
    enum_def = "enum MyEnum { Member 0 }"
    compile_and_add_to_symtab(enum_def, :enum_definition)

    # Unqualified reference should fail
    idl = "Member"
    assert_raises(Idl::AstNode::TypeError) do
      compile_expression(idl)
    end
  end

  def test_enum_reference_to_nonexistent_enum
    idl = "NotAnEnum::Member"
    assert_raises(Idl::AstNode::TypeError) do
      compile_expression(idl)
    end
  end

  # ============================================================================
  # Section: Data Types → Composite Types → Bitfields
  # ============================================================================

  def test_bitfield_member_access_type
    bitfield_def = <<~IDL
      bitfield (64) MyBitfield {
        Field1 63-32
        Field2 31-0
      }
    IDL
    compile_and_add_to_symtab(bitfield_def.strip, :bitfield_definition)

    # Declare a variable of bitfield type
    @symtab.add!("bf", Idl::Var.new("bf", @symtab.get("MyBitfield")))

    idl = "bf.Field1"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 32, type.width
  end

  # ============================================================================
  # Section: Data Types → Composite Types → Structs
  # ============================================================================

  def test_struct_member_access_type
    struct_def = <<~IDL
      struct MyStruct {
        Bits<32> field1;
        Boolean field2;
      }
    IDL
    compile_and_add_to_symtab(struct_def.strip, :struct_definition)

    @symtab.add!("s", Idl::Var.new("s", @symtab.get("MyStruct")))

    idl = "s.field1"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 32, type.width
  end

  # ============================================================================
  # Section: Data Types → Composite Types → Arrays
  # ============================================================================

  def test_array_element_type
    idl = "Bits<32> arr[10];"
    ast = compile_statement(idl)
    # Array variable itself has array type
    assert_equal :array, ast.action.type(@symtab).kind


    # Array element access should have element type
    elem_idl = "arr[5]"
    elem_ast = compile_expression(elem_idl)
    elem_type = elem_ast.type(@symtab)
    assert_equal :bits, elem_type.kind
    assert_equal 32, elem_type.width
  end

  # ============================================================================
  # Section: Type conversions
  # ============================================================================

  def test_implicit_width_conversion_unsigned
    # When operands have different widths, smaller is extended to larger
    idl = "4'b1111 + 8'b00000001"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width
    refute type.signed?
  end

  def test_implicit_width_conversion_signed
    # Signed values are sign-extended
    idl = "$signed(4'b1111) + 8'b00000001"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width
    refute type.signed?
  end

  def test_assignment_truncates_wider_value
    # When assigning wider value to narrower variable, upper bits are discarded
    @symtab.add!("narrow", Idl::Var.new("narrow", Idl::Type.new(:bits, width: 4), 0))

    idl = "narrow = 8'hFF;"
    ast = compile_statement(idl)
    # Assignment should succeed (truncation is implicit)
    refute_nil ast
  end

  # ============================================================================
  # Section: Casting → $signed
  # ============================================================================

  def test_signed_cast_changes_signedness
    idl = "$signed(4'b1111)"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 4, type.width
    assert type.signed?
  end

  def test_signed_cast_affects_comparison
    # Without $signed: unsigned comparison
    idl1 = "4'b1111 < 4'b0001"
    ast1 = compile_expression(idl1)
    assert_equal false, ast1.value(@symtab)

    # With $signed: signed comparison (-1 < 1)
    idl2 = "$signed(4'b1111) < $signed(4'b0001)"
    ast2 = compile_expression(idl2)
    assert_equal true, ast2.value(@symtab)
  end

  # ============================================================================
  # Section: Casting → $bits
  # ============================================================================

  def test_bits_cast_enum_to_bits
    enum_def = "enum MyEnum { A 0 B 1 C 7 }"
    compile_and_add_to_symtab(enum_def, :enum_definition)

    idl = "$bits(MyEnum::C)"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    # Should be wide enough to hold largest value (7 requires 3 bits)
    assert_equal 3, type.width
  end

  def test_bits_cast_bitfield_to_bits
    bitfield_def = "bitfield (32) MyBitfield { Field 31-0 }"
    compile_and_add_to_symtab(bitfield_def, :bitfield_definition)

    @symtab.add!("bf", Idl::Var.new("bf", @symtab.get("MyBitfield")))

    idl = "$bits(bf)"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 32, type.width
  end

  # ============================================================================
  # Section: Operators → Binary operators with different widths
  # ============================================================================

  def test_binary_operator_extends_to_larger_width
    # 4-bit + 8-bit should result in 8-bit
    idl = "4'hF + 8'h01"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal 8, type.width
  end

  def test_binary_operator_sign_propagation
    # Result is signed only if both operands are signed
    idl1 = "$signed(4'hF) + $signed(4'h1)"
    ast1 = compile_expression(idl1)
    assert ast1.type(@symtab).signed?

    idl2 = "$signed(4'hF) + 4'h1"
    ast2 = compile_expression(idl2)
    refute ast2.type(@symtab).signed?
  end

  # ============================================================================
  # Section: Operators → Widening operators
  # ============================================================================

  def test_widening_multiply_type
    idl = "4'hF `* 4'hF"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width  # 4 + 4
  end

  def test_widening_add_type
    idl = "4'hF `+ 4'h1"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 5, type.width  # max(4,4) + 1
  end

  def test_widening_left_shift_type
    idl = "4'hF `<< 2"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 6, type.width  # 4 + 2
  end

  # ============================================================================
  # Section: Operators → Comparison operators
  # ============================================================================

  def test_comparison_operators_return_boolean
    comparisons = ["4'h5 > 4'h3", "4'h5 < 4'h3", "4'h5 >= 4'h3", "4'h5 <= 4'h3"]

    comparisons.each do |idl|
      ast = compile_expression(idl)
      type = ast.type(@symtab)
      assert_equal :boolean, type.kind, "#{idl} should return Boolean"
    end
  end

  def test_equality_operators_return_boolean
    idl1 = "4'h5 == 4'h5"
    ast1 = compile_expression(idl1)
    assert_equal :boolean, ast1.type(@symtab).kind

    idl2 = "4'h5 != 4'h3"
    ast2 = compile_expression(idl2)
    assert_equal :boolean, ast2.type(@symtab).kind
  end

  # ============================================================================
  # Section: Operators → Logical operators
  # ============================================================================

  def test_logical_operators_require_boolean_operands
    idl = "true && false"
    ast = compile_expression(idl)
    assert_equal :boolean, ast.type(@symtab).kind

    # Bits<N> cannot be used with logical operators
    idl_invalid = "1 && 0"
    assert_raises(Idl::AstNode::TypeError) do
      compile_expression(idl_invalid)
    end
  end

  def test_logical_operators_return_boolean
    idl = "true || false"
    ast = compile_expression(idl)
    assert_equal :boolean, ast.type(@symtab).kind
  end

  # ============================================================================
  # Section: Operators → Ternary operator
  # ============================================================================

  def test_ternary_condition_must_be_boolean
    idl = "true ? 4'h5 : 4'h3"
    ast = compile_expression(idl)
    refute_nil ast

    # Condition must be boolean
    idl_invalid = "1 ? 4'h5 : 4'h3"
    assert_raises(Idl::AstNode::TypeError) do
      compile_expression(idl_invalid)
    end
  end

  def test_ternary_result_type_is_wider_branch
    # When branches have different widths, result is wider
    idl = "true ? 8'hFF : 4'hF"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width
  end

  # ============================================================================
  # Section: Operators → Bit extraction
  # ============================================================================

  def test_single_bit_extraction_type
    idl = "8'hFF[3]"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 1, type.width
    refute type.signed?  # Always unsigned
  end

  def test_range_extraction_type
    idl = "8'hFF[7:4]"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 4, type.width  # 7 - 4 + 1
    refute type.signed?  # Always unsigned
  end

  # ============================================================================
  # Section: Operators → Concatenation
  # ============================================================================

  def test_concatenation_type
    idl = "{4'hF, 4'h0}"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width  # 4 + 4
    refute type.signed?  # Always unsigned
  end

  def test_replication_type
    idl = "{4{2'b10}}"
    ast = compile_expression(idl)
    type = ast.type(@symtab)
    assert_equal :bits, type.kind
    assert_equal 8, type.width  # 4 * 2
    refute type.signed?  # Always unsigned
  end

  # ============================================================================
  # Section: Expressions -> Logical operators -> Short circuiting
  # ============================================================================

  # Regression test for https://github.com/riscv/riscv-unified-db/issues/1140
  #
  # '&&' and '||' short circuit, so a single operand with a known value decides the whole
  # expression. That is true of either operand, not just the left one. It matters for chains,
  # because 'a && b && c' is left associative and parses as '(a && b) && c': when only 'b' is
  # known, the inner expression can only be resolved by looking at its right-hand side.
  def add_short_circuit_syms
    @symtab.add!("UNKNOWN", Idl::Var.new("UNKNOWN", Idl::Type.new(:boolean)))
    @symtab.add!("FALSE", Idl::Var.new("FALSE", Idl::Type.new(:boolean), false))
    @symtab.add!("TRUE", Idl::Var.new("TRUE", Idl::Type.new(:boolean), true))
    # a non-boolean operand, so that failing to short circuit is a type error
    @symtab.add!("STR", Idl::Var.new("STR", Idl::Type.new(:string), "not a boolean"))
  end

  def test_and_short_circuits_on_either_operand
    add_short_circuit_syms

    assert_equal false, compile_expression("UNKNOWN && (FALSE && STR)").value(@symtab)
    assert_equal false, compile_expression("UNKNOWN && FALSE && STR").value(@symtab)
    assert_equal false, compile_expression("STR && FALSE && UNKNOWN").value(@symtab)
  end

  def test_or_short_circuits_on_either_operand
    add_short_circuit_syms

    assert_equal true, compile_expression("UNKNOWN || (TRUE || STR)").value(@symtab)
    assert_equal true, compile_expression("UNKNOWN || TRUE || STR").value(@symtab)
    assert_equal true, compile_expression("STR || TRUE || UNKNOWN").value(@symtab)
  end

  # ============================================================================
  # Negative test cases: Type errors
  # ============================================================================

  def test_type_error_boolean_arithmetic
    # Boolean cannot be used in arithmetic
    assert_raises(Idl::AstNode::TypeError) do
      compile_expression("true + false")
    end
  end

  def test_type_error_string_arithmetic
    # String cannot be used in arithmetic
    @symtab.add!("str", Idl::Var.new("str", Idl::Type.new(:string), "hello"))

    assert_raises(Idl::AstNode::TypeError) do
      compile_expression('"hello" + 5')
    end
  end

  def test_type_error_incompatible_assignment
    # Cannot assign Boolean to Bits<N>
    idl = "Bits<8> x = true;"
    assert_raises(Idl::AstNode::TypeError) do
      compile_statement(idl)
    end
  end

  # ============================================================================
  # Helper methods
  # ============================================================================

  private

  def compile_statement(idl)
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: :statement)
    refute_nil m, "Failed to parse: #{idl}: #{@compiler.parser.failure_reason}"
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(@symtab)
    ast.type_check(@symtab, strict: false)
    ast
  end

  def compile_expression(idl)
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: :expression)
    refute_nil m, "Failed to parse: #{idl}"
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(@symtab)
    ast.type_check(@symtab, strict: false)
    ast
  end

  def compile_and_add_to_symtab(idl, root)
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: root)
    refute_nil m, "Failed to parse: #{idl}: #{@compiler.parser.failure_reason}"
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(@symtab)
    ast.add_symbol(@symtab)
    ast
  end
end
