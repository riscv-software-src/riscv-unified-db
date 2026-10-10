# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "idlc"
require "idlc/passes/prune"
require_relative "helpers"
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

# test IDL variables
class TestVariables < Minitest::Test
  include TestMixin

  def test_prune_forced_type
    orig_idl = "true ? 4'b0 : 5'b1"

    expected_idl = "5'd0"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    assert_instance_of Idl::TernaryOperatorExpressionAst, ast

    pruned = ast.prune(symtab)
    assert_instance_of Idl::IntLiteralAst, pruned

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_forced_type_nested
    orig_idl = "true ? 4'b0 : (5'b1 * 1)"

    expected_idl = "5'd0"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    assert_instance_of Idl::TernaryOperatorExpressionAst, ast

    pruned = ast.prune(symtab)
    assert_instance_of Idl::IntLiteralAst, pruned

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_forced_type_nested_2
    ops = ["*", "/", "+", "-", "&", "|"]
    ops.each do |op|
      orig_idl = "false ? 5'b0 : 4'b1 #{op} 1"

      expected_idl = "5'#{eval "1 #{op} 1"}"

      symtab = Idl::SymbolTable.new
      m = @compiler.parser.parse(orig_idl, root: :expression)
      refute_nil m

      ast = m.to_ast
      assert_instance_of Idl::TernaryOperatorExpressionAst, ast

      pruned = ast.prune(symtab)
      assert_instance_of Idl::IntLiteralAst, pruned

      assert_equal expected_idl, pruned.to_idl
    end
  end

  def test_prune_forced_type_negative_value
    # regression test: a negative value pruned into a forced (signed) type must
    # keep its sign marker ('sd, not just 'd), or the literal re-parses as
    # unsigned and its sign is lost when later rendered to C++
    orig_idl = "false ? 4'sb0 : -(8'sd1)"

    expected_idl = "8'sd-1"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    assert_instance_of Idl::TernaryOperatorExpressionAst, ast

    pruned = ast.prune(symtab)
    assert_instance_of Idl::IntLiteralAst, pruned

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_function_body_negative_return_value
    # regression test for the highest_set_bit() bug: a function whose declared
    # return type is signed, that falls through to a bare negative literal
    # return (e.g. "return -'sd1;"), must prune to a literal that keeps its
    # sign marker so the value survives C++ codegen (see gen_cpp.rb IntLiteralAst#gen_cpp)
    orig_idl = <<~IDL
      if (false) {
        return 1;
      }
      return -(64'sd1);
    IDL

    symtab = Idl::SymbolTable.new(possible_xlens_cb: proc { [32, 64] })
    ast =
      @compiler.compile_func_body(
        orig_idl,
        return_type: Idl::Type.new(:bits, width: 64, qualifiers: [:signed]),
        symtab:,
        input_file: "temp"
      )
    refute_nil(ast)

    pruned = ast.prune(symtab)
    return_stmt = pruned.statements.last
    assert_instance_of Idl::ReturnStatementAst, return_stmt

    literal = return_stmt.return_expression.return_value_nodes.first
    assert_instance_of Idl::IntLiteralAst, literal
    assert_equal "64'sd-1", literal.to_idl
    assert literal.type(symtab).signed?
    assert_equal(-1, literal.value(symtab))
  end

  def test_ternary_prune
    orig_idl = "(true) ? {1'b1, {31{1'b0}}} : {1'b1, {63{1'b0}}}"
    expected_idl = "64'h80000000"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    assert_instance_of Idl::TernaryOperatorExpressionAst, ast

    pruned = ast.prune(symtab)
    assert_instance_of Idl::IntLiteralAst, pruned

    assert_equal expected_idl, pruned.to_idl
  end

  def test_ternary_prune_2
    orig_idl = "(true) ? {1'b1, {31{1'bx}}} : {1'b1, {63{1'b0}}}"
    expected_idl = "{32'0,1'b1,{31{1'bx}}}"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    assert_instance_of Idl::TernaryOperatorExpressionAst, ast

    pruned = ast.prune(symtab)
    assert_instance_of Idl::ConcatenationExpressionAst, pruned

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_nested_ternary_with_type_coercion
    orig_idl = "true ? (false ? 8'b0 : 16'b1) : 32'd2"
    expected_idl = "32'd1"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m, proc { @compiler.parser.failure_reason }

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_complex_concatenation
    orig_idl = "true ? {1'b1, {7{1'b0}}} : {1'b0, {15{1'b1}}}"
    expected_idl = "16'128"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_arithmetic_with_known_values
    orig_idl = "true ? (5 `+ 3) : (10 - 2)"
    expected_idl = "4'8"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_logical_operations
    orig_idl = "true ? (true && false) : (true || false)"
    expected_idl = "false"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_bitwise_operations
    orig_idl = "true ? (8'hFF & 8'h0F) : (8'hAA | 8'h55)"
    expected_idl = "8'15"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_shift_operations
    orig_idl = "true ? (8'h01 << 3) : (8'h80 >> 3)"
    expected_idl = "8'8"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_comparison_operations
    orig_idl = "true ? (5 > 3) : (2 < 1)"
    expected_idl = "true"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_nested_if_statements
    orig_idl = <<~IDL
      if (true) {
        if (false) {
          return 1;
        } else {
          return 2;
        }
      }
    IDL
    expected_idl = <<~IDL
      return 2;
    IDL

    symtab = Idl::SymbolTable.new
    ast = @compiler.compile_func_body(
      orig_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil ast

    pruned = ast.prune(symtab)
    assert_equal expected_idl.strip, pruned.to_idl.strip
  end

  def test_prune_unknown_condition_preserved
    orig_idl = "unknown_var ? 1 : 2"

    symtab = Idl::SymbolTable.new
    symtab.add("unknown_var", Idl::Var.new("unknown_var", Idl::Type.new(:bits, width: :unknown)))
    # Don't define unknown_var, so it remains unknown
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    # Should preserve the ternary since condition is unknown
    assert_instance_of Idl::TernaryOperatorExpressionAst, pruned
  end

  def test_prune_csr_value
    orig_idl = <<~IDL
      if (CSR[mockcsr].ONE == 1) {
        return 1;
      }
    IDL
    expected_idl = <<~IDL
      return 1;
    IDL

    mock_csr_class = Class.new do
      include Idl::Csr
      def name = "mockcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      def fields = [
        MockCsrFieldClass.new("ONE", 1, 0..15),
        MockCsrFieldClass.new("UNKNOWN", nil, 16..31)
      ]
    end
    mock_csr_class2 = Class.new do
      include Idl::Csr
      def name = "mockcsr2"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = 1
      def fields = [
        MockCsrFieldClass.new("ONE", 1, 0..31)
      ]
    end
    symtab = Idl::SymbolTable.new(
      csrs: [mock_csr_class.new, mock_csr_class2.new],
      possible_xlens_cb: proc { [32, 64] }
    )
    ast =
      @compiler.compile_func_body(
        orig_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(ast)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl

    orig_idl = <<~IDL
      if (CSR[mockcsr].UNKNOWN == 1) {
        return 1;
      }
    IDL
    expected_idl = <<~IDL
      if (CSR[mockcsr].UNKNOWN == 1) {
        return 1;
      }
    IDL
    ast =
          @compiler.compile_func_body(
            orig_idl,
            return_type: Idl::Type.new(:bits, width: 32),
            symtab:,
            input_file: "temp"
          )
    refute_nil(ast)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl

    orig_idl = <<~IDL
      CSR[mockcsr].UNKNOWN = CSR[mockcsr].ONE;
    IDL
    expected_idl = <<~IDL
      CSR[mockcsr].UNKNOWN = 32'1;
    IDL
    ast =
          @compiler.compile_func_body(
            orig_idl,
            return_type: Idl::Type.new(:bits, width: 32),
            symtab:,
            input_file: "temp"
          )
    refute_nil(ast)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl

    orig_idl = <<~IDL
      Bits<32> tmp = $bits(CSR[mockcsr]);
    IDL
    expected_idl = <<~IDL
      Bits<32> tmp = $bits(CSR[mockcsr]);
    IDL
    ast =
          @compiler.compile_func_body(
            orig_idl,
            return_type: Idl::Type.new(:bits, width: 32),
            symtab:,
            input_file: "temp"
          )
    refute_nil(ast)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl

    orig_idl = <<~IDL
      Bits<32> tmp = $bits(CSR[mockcsr2]);
    IDL
    expected_idl = <<~IDL
      Bits<32> tmp = 32'1;
    IDL
    ast =
          @compiler.compile_func_body(
            orig_idl,
            return_type: Idl::Type.new(:bits, width: 32),
            symtab:,
            input_file: "temp"
          )
    refute_nil(ast)
    ast.freeze_tree(symtab)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_prune_csr_field_with_multiple_fields
    mock_csr_class = Class.new do
      include Idl::Csr
      def name = "testcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      def fields = [
        MockCsrFieldClass.new("FIELD1", 1, 0..7),
        MockCsrFieldClass.new("FIELD2", 2, 8..15),
        MockCsrFieldClass.new("FIELD3", nil, 16..31)
      ]
    end

    symtab = Idl::SymbolTable.new(
      csrs: [mock_csr_class.new],
      possible_xlens_cb: proc { [32, 64] }
    )

    orig_idl = <<~IDL
      if (CSR[testcsr].FIELD1 == 1 && CSR[testcsr].FIELD2 == 2) {
        return 1;
      }
    IDL
    expected_idl = <<~IDL
      return 1;
    IDL

    ast = @compiler.compile_func_body(
      orig_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil ast

    pruned = ast.prune(symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )

    assert_equal expected_ast.to_idl, pruned.to_idl
  end

  def test_prune_preserves_unknown_csr_field
    mock_csr_class = Class.new do
      include Idl::Csr
      def name = "testcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      def fields = [
        MockCsrFieldClass.new("UNKNOWN", nil, 0..31)
      ]
    end

    symtab = Idl::SymbolTable.new(
      csrs: [mock_csr_class.new],
      possible_xlens_cb: proc { [32, 64] }
    )

    orig_idl = <<~IDL
      if (CSR[testcsr].UNKNOWN == 1) {
        return 1;
      }
    IDL

    ast = @compiler.compile_func_body(
      orig_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil ast

    pruned = ast.prune(symtab)

    # Should preserve the if statement since field value is unknown
    assert_instance_of Idl::FunctionBodyAst, pruned
    assert_includes pruned.to_idl, "if"
  end

  def test_prune_with_type_width_mismatch
    orig_idl = "true ? 4'b1111 : 8'b00000000"
    expected_idl = "8'd15"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_prune_complex_expression_tree
    orig_idl = "true ? (false ? 1 : (true ? 2 : 3)) : 4"
    expected_idl = "3'd2"

    symtab = Idl::SymbolTable.new
    m = @compiler.parser.parse(orig_idl, root: :expression)
    refute_nil m

    ast = m.to_ast
    pruned = ast.prune(symtab)

    assert_equal expected_idl, pruned.to_idl
  end

  def test_if_body_does_not_leak_assignments
    # 'a' is assigned inside an if with unknown condition.
    # After the if, 'a' should be unknown, so 'result = a' must NOT be folded to a constant.
    orig_idl = <<~IDL
      Bits<32> a = 10;
      if (CSR[mockcsr].UNKNOWN == 1) {
        a = 0xdeadbeef;
      }
      Bits<32> result = a;
    IDL
    expected_idl = <<~IDL
      Bits<32> a = 10;
      if (CSR[mockcsr].UNKNOWN == 1) {
        a = 0xdeadbeef;
      }
      Bits<32> result = a;
    IDL

    mock_csr_field_class2 = Class.new do
      include Idl::CsrField
      def initialize(name, val, loc)
        @name = name
        @val = val
        @loc = loc
      end
      attr_reader :name
      def defined_in_all_bases? = true
      def defined_in_base32? = true
      def defined_in_base64? = true
      def base64_only? = false
      def base32_only? = false
      def location(_) = @loc
      def width(_) = 32
      def type(_) = @val.nil? ? "RW" : "RO"
      def exists? = true
      def reset_value = @val.nil? ? "UNDEFINED_LEGAL" : @val
    end
    leak_csr_class = Class.new do
      include Idl::Csr
      def name = "mockcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      define_method(:fields) { [mock_csr_field_class2.new("UNKNOWN", nil, 0..31)] }
    end
    symtab = Idl::SymbolTable.new(
      csrs: [leak_csr_class.new],
      possible_xlens_cb: proc { [32, 64] }
    )
    ast =
      @compiler.compile_func_body(
        orig_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(ast)
    pruned_ast = ast.prune(symtab)
    expected_ast =
      @compiler.compile_func_body(
        expected_idl,
        return_type: Idl::Type.new(:bits, width: 32),
        symtab:,
        input_file: "temp"
      )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  # Helper to build a symtab with mockcsr having ONE (known=1) and UNKNOWN (unknown) fields
  def build_mock_symtab
    mock_field_class = Class.new do
      include Idl::CsrField
      def initialize(name, val, loc)
        @name = name
        @val = val
        @loc = loc
      end
      attr_reader :name
      def defined_in_all_bases? = true
      def defined_in_base32? = true
      def defined_in_base64? = true
      def base64_only? = false
      def base32_only? = false
      def location(_) = @loc
      def width(_) = 32
      def type(_) = @val.nil? ? "RW" : "RO"
      def exists? = true
      def reset_value = @val.nil? ? "UNDEFINED_LEGAL" : @val
    end
    mock_csr = Class.new do
      include Idl::Csr
      def name = "mockcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      define_method(:fields) do
        [
          mock_field_class.new("ONE", 1, 0..15),
          mock_field_class.new("UNKNOWN", nil, 16..31)
        ]
      end
    end
    Idl::SymbolTable.new(
      csrs: [mock_csr.new],
      possible_xlens_cb: proc { [32, 64] }
    )
  end

  def compile_and_prune(idl, symtab)
    ast = @compiler.compile_func_body(
      idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(ast)
    ast.prune(symtab)
  end

  def test_conditional_statement_does_not_leak_assignment
    # a = 0xdeadbeef if (CSR[mockcsr].UNKNOWN == 1);
    # After pruning, 'a' should be unknown (nil), not 0xdeadbeef
    orig_idl = <<~IDL
      Bits<32> a = 10;
      a = 0xdeadbeef if (CSR[mockcsr].UNKNOWN == 1);
      Bits<32> result = a;
    IDL
    expected_idl = <<~IDL
      Bits<32> a = 10;
      a = 0xdeadbeef if (CSR[mockcsr].UNKNOWN == 1);
      Bits<32> result = a;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_for_loop_does_not_leak_assignments
    # 'a' is assigned inside a for loop body.
    # After the loop, 'a' should be unknown (nil).
    orig_idl = <<~IDL
      Bits<32> a = 10;
      for (Bits<8> i = 0; i < 4; i++) {
        a = i;
      }
      Bits<32> result = a;
    IDL
    expected_idl = <<~IDL
      Bits<32> a = 10;
      for (Bits<8> i = 0; i < 4; i++) {
        a = i;
      }
      Bits<32> result = a;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_ary_range_assignment_does_not_leak
    # vec[7:0] = 0xff inside unknown if; after if, vec should be unknown
    orig_idl = <<~IDL
      Bits<32> vec = 0;
      if (CSR[mockcsr].UNKNOWN == 1) {
        vec[7:0] = 0xff;
      }
      Bits<32> result = vec;
    IDL
    expected_idl = <<~IDL
      Bits<32> vec = 0;
      if (CSR[mockcsr].UNKNOWN == 1) {
        vec[7:0] = 0xff;
      }
      Bits<32> result = vec;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_ary_range_assignment_execute_updates_value
    # vec[7:0] = 0xab with known condition (ONE == 1); result should fold to the updated value.
    # Uses vec + 0 to force folding of the variable reference.
    orig_idl = <<~IDL
      Bits<32> vec = 0x12340000;
      if (CSR[mockcsr].ONE == 1) {
        vec[7:0] = 0xab;
      }
      Bits<32> result = vec + 0;
    IDL
    expected_idl = <<~IDL
      Bits<32> vec = 0x12340000;
      vec[7:0] = 0xab;
      Bits<32> result = 32'h123400ab;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_post_increment_does_not_leak
    # i++ is the update expression in a for loop; after the loop, a variable
    # assigned using i should remain unknown
    orig_idl = <<~IDL
      Bits<32> result = 0;
      for (Bits<8> i = 0; i < 4; i++) {
        result = i;
      }
      Bits<32> final = result;
    IDL
    expected_idl = <<~IDL
      Bits<32> result = 0;
      for (Bits<8> i = 0; i < 4; i++) {
        result = i;
      }
      Bits<32> final = result;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_post_decrement_does_not_leak
    # i-- as a for-loop update expression; after the loop, a variable
    # assigned using i should remain unknown
    orig_idl = <<~IDL
      Bits<32> result = 0;
      for (Bits<8> i = 3; i > 0; i--) {
        result = i;
      }
      Bits<32> final = result;
    IDL
    expected_idl = <<~IDL
      Bits<32> result = 0;
      for (Bits<8> i = 3; i > 0; i--) {
        result = i;
      }
      Bits<32> final = result;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_multiple_assignments_in_unknown_branch_do_not_leak
    # Multiple variables assigned in same unknown branch; all should be unknown after
    orig_idl = <<~IDL
      Bits<32> a = 1;
      Bits<32> b = 2;
      if (CSR[mockcsr].UNKNOWN == 1) {
        a = 10;
        b = 20;
      }
      Bits<32> result_a = a;
      Bits<32> result_b = b;
    IDL
    expected_idl = <<~IDL
      Bits<32> a = 1;
      Bits<32> b = 2;
      if (CSR[mockcsr].UNKNOWN == 1) {
        a = 10;
        b = 20;
      }
      Bits<32> result_a = a;
      Bits<32> result_b = b;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end

  def test_multiple_conditional_modifiers_do_not_leak
    # Two consecutive conditional modifiers with unknown conditions; final value should be unknown.
    # After first modifier (unknown cond), result is nullified.
    # After second modifier (unknown cond), result stays unknown.
    # final = result must NOT fold to 0x2222.
    orig_idl = <<~IDL
      Bits<32> result = 0;
      result = 0x1111 if (CSR[mockcsr].UNKNOWN == 1);
      result = 0x2222 if (CSR[mockcsr].UNKNOWN == 2);
      Bits<32> final = result;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    pruned_idl = pruned_ast.to_idl
    # The key assertion: 'final' must not be folded to a literal constant
    refute_match(/final = \d+'\h/, pruned_idl, "value leaked through conditional modifiers: #{pruned_idl}")
  end

  def test_for_loop_nested_in_unknown_if_does_not_leak
    # For loop nested inside unknown if branch; variables assigned in loop should be unknown
    orig_idl = <<~IDL
      Bits<32> result = 0;
      if (CSR[mockcsr].UNKNOWN == 1) {
        for (Bits<8> i = 0; i < 4; i++) {
          result = 1;
        }
      }
      Bits<32> final = result;
    IDL
    expected_idl = <<~IDL
      Bits<32> result = 0;
      if (CSR[mockcsr].UNKNOWN == 1) {
        for (Bits<8> i = 0; i < 4; i++) {
          result = 1;
        }
      }
      Bits<32> final = result;
    IDL
    symtab = build_mock_symtab
    pruned_ast = compile_and_prune(orig_idl, symtab)
    expected_ast = @compiler.compile_func_body(
      expected_idl,
      return_type: Idl::Type.new(:bits, width: 32),
      symtab:,
      input_file: "temp"
    )
    refute_nil(expected_ast)
    assert_equal expected_ast.to_idl, pruned_ast.to_idl
  end
end
