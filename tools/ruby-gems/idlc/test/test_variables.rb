# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require 'idlc'
require_relative 'test_helper'
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "helpers"

# test IDL variables
class TestVariables < Minitest::Test
  include TestMixin

  def test_that_constants_are_read_only
    idl = <<~IDL.strip
      XReg MyConstant = 15;
      MyContant = 0;
    IDL

    assert_raises(Idl::AstNode::TypeError) do
      @compiler.compile_func_body(idl, symtab: @symtab, no_rescue: true)
    end
  end
end
