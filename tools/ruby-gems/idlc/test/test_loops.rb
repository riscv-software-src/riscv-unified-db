# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "idlc"
require_relative "helpers"
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "helpers"

# test IDL variables
class TestVariables < Minitest::Test
  include TestMixin

  def test_const_iter
    idl = <<~IDL
      for (U32 I = 0; I < 5; I++) {
        I = I + 1;
      }
    IDL

    # should not raise
    ast = @compiler.compile_for_loop(idl, @symtab, pass_error: true)
    assert_instance_of(Idl::ForLoopAst, ast)
  end

  def test_mutable_iter
    idl = <<~IDL
      for (U32 I = 0; I < 5; I = I + mutable_var) {
        I = I + 1;
      }
    IDL

    @symtab.add("mutable_var", Idl::Var.new("mutable_var", Idl::Type.new(:bits, width: 5)))

    # should raise
    assert_raises(Idl::AstNode::TypeError) {
      @compiler.compile_for_loop(idl, @symtab, pass_error: true)
    }

    idl = <<~IDL
      for (U32 I = 0; I < 5; I++) {
        I = I + mutable_var;
      }
    IDL

    # should raise
    assert_raises(Idl::AstNode::TypeError) {
      @compiler.compile_for_loop(idl, @symtab, pass_error: true)
    }

    idl = <<~IDL
      for (U32 i = 0; i < 5; i = i + mutable_var) {
        i = i + 1;
      }
    IDL

    # should not raise
    ast = @compiler.compile_for_loop(idl, @symtab, pass_error: true)
    assert_instance_of(Idl::ForLoopAst, ast)
  end
end
