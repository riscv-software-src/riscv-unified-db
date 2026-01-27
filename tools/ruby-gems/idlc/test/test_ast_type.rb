# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "idlc"
require "idlc/ast"
require_relative "helpers"
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "helpers"

# test IDL variables
class TestVariables < Minitest::Test
  include TestMixin

  def test_enum_ref
    def_idl = "enum MyEnum { Member 0b0 }"
    symtab = Idl::SymbolTable.new(
      possible_xlens_cb: proc { [32, 64] }
    )
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(def_idl, root: :enum_definition)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(symtab)
    ast.add_symbol(symtab)

    idl = "MyEnum::Member"
    m = @compiler.parser.parse(idl, root: :enum_ref)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    assert_equal Idl::Type.new(:enum_ref, enum_class: symtab.get("MyEnum")), ast.type(symtab)
    ast.freeze_tree(symtab)
    assert_equal Idl::Type.new(:enum_ref, enum_class: symtab.get("MyEnum")), ast.type(symtab)

    idl = "NotAnEnum::Member"
    m = @compiler.parser.parse(idl, root: :enum_ref)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    assert_raises Idl::AstNode::TypeError do
      ast.type(symtab)
    end
    assert_raises Idl::AstNode::TypeError do
      ast.freeze_tree(symtab)
    end

  end

  def test_bits_cast
    symtab = Idl::SymbolTable.new(
      possible_xlens_cb: proc { [32, 64] }
    )
    idl = "$bits(1'b0)"
    m = @compiler.parser.parse(idl, root: :bits_cast)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    assert_equal Idl::Type.new(:bits, width: 1), ast.type(symtab)
  end

  def test_csr_field_assignment
    $mock_csr_field_class = Class.new do
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
      def dynamic_location? = false
      def width(_) = @loc.size
      def type(_) = @val.nil? ? "RW" : "RO"
      def exists? = true
      def reset_value = @val.nil? ? "UNDEFINED_LEGAL" : @val
    end
    mock_csr_class = Class.new do
      include Idl::Csr
      def name = "mockcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      def fields = [
        $mock_csr_field_class.new("ONE", 1, 0..15),
        $mock_csr_field_class.new("UNKNOWN", nil, 16..31)
      ]
    end

    symtab = Idl::SymbolTable.new(
      csrs: [mock_csr_class.new],
      possible_xlens_cb: proc { [32, 64] }
    )

    idl = "CSR[mockcsr].UNKNOWN = 1"
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: :assignment)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(symtab)

    assert_instance_of Idl::CsrFieldAssignmentAst, ast

    assert_equal Idl::Type.new(:bits, width: 16), ast.csr_field.type(symtab)
    assert_equal Idl::Type.new(:bits, width: 16), ast.type(symtab)

    idl = "CSR[notacsr].FIELD = 1"
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: :assignment)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    assert_raises Idl::AstNode::TypeError do
      ast.freeze_tree(symtab)
    end

  end
end
