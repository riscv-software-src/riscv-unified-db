# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"

require "idlc"
require_relative "helpers"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "helpers"

# test IDL variables
class TestStd < Minitest::Test
  include TestMixin

  def check_yaml(expected, actual, path)
    single_level_expected = expected.reject { |k, v| k == "source" || v.is_a?(Hash) || v.is_a?(Array) }
    single_level_actual   = actual.reject { |k, v| k == "source" || v.is_a?(Hash) || v.is_a?(Array) }
    assert_equal single_level_expected, single_level_actual, \
      "Along path '#{path.join("/")}', expected #{single_level_expected}, got #{single_level_actual}"
    expected.keys.each do |k|
      next if k == "source"
      if expected.fetch(k).is_a?(Hash) && actual.key?(k)
        assert actual.fetch(k).is_a?(Hash)
        check_yaml(expected.fetch(k), actual.fetch(k), path + [k])
      elsif expected.fetch(k).is_a?(Array) && actual.key?(k)
        assert actual.fetch(k).is_a?(Array)
        assert_equal expected.fetch(k).size, actual.fetch(k).size
        expected.fetch(k).each_index do |i|
          check_yaml(expected.fetch(k)[i], actual.fetch(k)[i], path + [k, i.to_s])
        end
      end
    end
  end

  def test_std_globals
    compiler = Idl::Compiler.new
    top_level = Pathname.new(__dir__) / "idl" / "std" / "isa" / "isa" / "globals.isa"

    source_mapper = {}
    ast = compiler.compile_file(top_level, source_mapper)

    direct = ast.to_h
    indirect = Idl::AstNode.from_h(direct, source_mapper).to_h

    check_yaml(direct, indirect, ["$"])
  end

  def test_std_inst_operation
    compiler = Idl::Compiler.new

    insts = Dir.glob(Pathname.new(__dir__) / "idl" / "std" / "inst" / "**" / "*.yaml")
    insts.each do |inst|
      y = YAML.load_file(inst)
      if y.key?("operation()") && !y.fetch("operation()").empty?
        ast = compiler.compile_inst_scope(y.fetch("operation()"), symtab: nil, input_file: inst, input_line: 0)
        direct = ast.to_h
        indirect = Idl::AstNode.from_h(direct, { file => File.read(file) }).to_h
        check_yaml(direct, indirect, [y.fetch("name"), "operation()"])
      end
    end
  end
end
