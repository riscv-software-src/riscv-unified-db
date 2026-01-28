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
class TestValues < Minitest::Test
  include TestMixin

  def test_unimplemented_csr_field
    $mock_csr_field_class = Class.new do
      include Idl::CsrField
      def initialize(name, val, loc, impl)
        @name = name
        @val = val
        @loc = loc
        @impl = impl
      end
      attr_reader :name
      def type(_) = @val.nil? ? "RW" : "RO"
      def exists? = @impl
    end
    mock_csr_class = Class.new do
      include Idl::Csr
      def name = "mockcsr"
      def max_length = 32
      def length(_) = 32
      def dynamic_length? = false
      def value = nil
      def fields = [
        $mock_csr_field_class.new("ONE", 1, 0..15, false)
      ]
    end

    symtab = Idl::SymbolTable.new(
      csrs: [mock_csr_class.new],
      possible_xlens_cb: proc { [32, 64] }
    )

    idl = "CSR[mockcsr].ONE"
    @compiler.parser.set_input_file("", 0)
    m = @compiler.parser.parse(idl, root: :csr_field_access_expression)
    refute_nil m
    ast = m.to_ast
    refute_nil ast
    ast.freeze_tree(symtab)
    assert_equal 0, ast.value(symtab)
  end
end
