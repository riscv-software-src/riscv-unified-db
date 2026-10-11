# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "test_helper"
require "udb"
require_relative "../../../backends/cpp_hart_gen/lib/gen_cpp"

class TestGenC < Minitest::Test
  def setup
    @symtab = Idl::SymbolTable.new
  end

  def parse(idl)
    compiler = Idl::Compiler.new
    m = compiler.parser.parse(idl, root: :single_declaration)
    refute_nil m

    ast = m.to_ast
    refute_nil ast
    assert_instance_of Idl::VariableDeclarationAst, ast

    ast
  end

  def test_array_decl_gen_c
    ast = parse("U32 foo [ 32 ]")

    # Regression test for array declarations in the C backend.
    c_code = ast.gen_c(@symtab)
    assert_equal "uint32_t foo[32]", c_code
  end

  def test_array_decl_gen_c_with_expression
    ast = parse("U32 bar [ VLEN ]")

    # Regression test for array declarations in the C backend.
    c_code = ast.gen_c(@symtab)
    assert_equal "uint32_t bar[VLEN]", c_code
  end
end
