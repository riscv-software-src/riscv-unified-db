# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "idlc"
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath


require_relative "helpers"

# Test IDL expressions
class TestExpressions < Minitest::Test
  include TestMixin

  def test_that_operators_are_left_recusrive
    idl = <<~IDL.strip
      4 - 3 - 1
    IDL

    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 0, ast.value(@symtab)
    assert_equal "((4 - 3) - 1)", ast.to_idl
  end

  def test_that_values_are_tuncated
    idl = <<~IDL.strip
      a + b
    IDL
    @symtab.add("a", Idl::Var.new("a", Idl::Type.new(:bits, width:4), 0xf))
    @symtab.add("b", Idl::Var.new("b", Idl::Type.new(:bits, width:4), 0x1))

    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 0, ast.value(@symtab)

    idl = <<~IDL.strip
      4'hf + 5'h1
    IDL

    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 16, ast.value(@symtab)
  end

  def test_that_const_values_are_not_tuncated
    idl = <<~IDL.strip
      4'hf + 4'h1
    IDL

    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 0x10, ast.value(@symtab)

    idl = <<~IDL.strip
      4'hf + 5'h1
    IDL

    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 16, ast.value(@symtab)
  end

  def test_that_multplication_is_higher_precedence_than_addition
    idl = <<~IDL.strip
      4 + 5'd3 * 2
    IDL

    ast = @compiler.compile_expression(idl, @symtab)
    warn ast.value(@symtab)
    refute_equal 14, ast.value(@symtab)
    assert_equal 10, ast.value(@symtab)
  end

  def test_that_integer_literals_give_correct_values
    idl = "8'd13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    idl = "16'hd"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    idl = "12'o15"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    idl = "4'b1101"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    idl = "-8'sd13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal(-13, ast.value(@symtab))

    idl = "-16'shd"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal(-13, ast.value(@symtab))

    idl = "-12'so15"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal(-13, ast.value(@symtab))

    idl = "-4'sb1101"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

    idl = "4'sb1101"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

    idl = "32'h80000000"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 0x80000000, ast.value(@symtab)

    idl = "32'h8000_0000"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 0x80000000, ast.value(@symtab)

    idl = "8'13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    # 13 decimal, unsigned XLEN-bit wide
    idl = "'13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    # 13 decimal, signed XLEN-bit wide
    idl = "'s13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 13, ast.value(@symtab)

    # compilation error: 300 does not fit in 8 bits
    idl = "8'h1_0000_0000"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

    # 3 decimal: the literal is 13, unsigned, in 4-bits. when negated, the sign bit is lost
    idl = "-4'd13"
    ast = @compiler.compile_expression(idl, @symtab)
    assert_equal 3, ast.value(@symtab)

    # compilation error: 300 does not fit in 8 bits
    idl = "8'sd300"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

    # compilation error: bit width must be positive
    idl = "0'15"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

    # compilation error: value does not fit in four bita
    idl = "4'hff"
    assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }
  end
end
