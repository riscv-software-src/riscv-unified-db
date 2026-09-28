# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "ostruct"
require "concurrent"
require "sorbet-runtime"
require "udb/obj/register_file"
require "udb/cfg_arch"

# Tests for RegisterFile Ruby object model changes needed for register file consolidation.
#
# These tests drive Step 4 of the implementation:
#   - register_length() IDL function body field (replaces static register_length field)
#   - RegisterFile#eval_register_length(cfg_arch) -> Integer or String param name
#   - RegisterFile#max_register_length -> Integer architectural maximum
#   - RegisterEntry#reset_value -> IDL literal string or nil
#   - RegisterEntry#register_file -> parent RegisterFile back-reference
class TestRegisterFileObj < Minitest::Test
  include Udb

  # Build a mock ConfiguredArchitecture that is-a real ConfiguredArchitecture (Sorbet passes),
  # but with minimal state. Uses allocate to bypass the complex constructor.
  def make_cfg_arch(mxlen: 64, free_params: [])
    arch = Udb::ConfiguredArchitecture.allocate
    arch.instance_variable_set(:@mxlen, mxlen)
    arch.instance_variable_set(:@objects, Concurrent::Hash.new)
    arch.instance_variable_set(:@object_hashes, Concurrent::Hash.new)

    # Inject test-only methods to answer what eval_register_length needs
    mxlen_val = mxlen
    free_params_names = free_params
    arch.define_singleton_method(:mxlen) { mxlen_val }
    arch.define_singleton_method(:param_values) { mxlen_val ? { "MXLEN" => mxlen_val } : {} }
    arch.define_singleton_method(:params_with_value) do
      mxlen_val ? [OpenStruct.new(name: "MXLEN", value: mxlen_val)] : []
    end
    arch.define_singleton_method(:params_without_value) do
      free_params_names.map { |n| OpenStruct.new(name: n) }
    end
    arch
  end

  # Build a minimal RegisterFile from a data hash using a real ConfiguredArchitecture
  # instance (bypasses Sorbet type check by using a genuine subtype).
  def make_rf(data_overrides = {})
    base = {
      "name" => "X",
      "kind" => "register_file",
      "long_name" => "General Purpose Registers",
      "register_length()" => "return MXLEN;",
      "registers" => [
        {
          "name" => "x0",
          "reset_value" => "0",
          "arch_read()" => "return 0;",
          "arch_write(value)" => "return 0;"
        },
        {
          "name" => "x1"
        }
      ]
    }.merge(data_overrides)
    arch = make_cfg_arch(mxlen: 64)
    RegisterFile.new(base, Pathname.new("/mock/register_file/X.yaml"), arch)
  end

  # register_length() IDL body should be returned as a string
  def test_register_length_idl_string
    rf = make_rf
    assert_equal "return MXLEN;", rf.register_length,
      "Expected register_length to return the IDL body string"
  end

  # eval_register_length with MXLEN=64 cfg_arch should return Integer 64
  def test_eval_register_length_integer
    rf = make_rf
    cfg_arch = make_cfg_arch(mxlen: 64)
    result = rf.eval_register_length(cfg_arch)
    assert_equal 64, result,
      "Expected eval_register_length to return 64 for MXLEN=64 cfg_arch"
  end

  # eval_register_length for V with free VLEN should return String "VLEN"
  def test_eval_register_length_param_string
    rf = make_rf(
      "name" => "V",
      "long_name" => "Vector Registers",
      "register_length()" => "return VLEN;",
      "registers" => Array.new(32) { |i| { "name" => "v#{i}" } }
    )
    cfg_arch = make_cfg_arch(mxlen: nil, free_params: ["VLEN"])
    result = rf.eval_register_length(cfg_arch)
    assert_equal "VLEN", result,
      "Expected eval_register_length to return param name string when VLEN is free"
  end

  # reset_value present in YAML (x0 entry) should be returned as a string
  def test_reset_value_present
    rf = make_rf
    assert_equal "0", rf.registers[0].reset_value,
      "Expected x0 reset_value to be '0'"
  end

  # reset_value absent from YAML (x1 entry) should return nil
  def test_reset_value_absent
    rf = make_rf
    assert_nil rf.registers[1].reset_value,
      "Expected x1 reset_value to be nil when not specified"
  end

  # registers[0].register_file should be the parent RegisterFile object
  def test_register_file_back_ref
    rf = make_rf
    entry = rf.registers[0]
    assert_same rf, entry.register_file,
      "Expected register_file to return the parent RegisterFile"
  end

  def test_registers_for_excludes_entries_with_unsatisfied_conditions
    rf = make_rf
    condition = Object.new
    condition.define_singleton_method(:could_be_satisfied_by_cfg_arch?) { |_| false }
    rf.registers[1].define_singleton_method(:when_condition) { condition }

    assert_equal [rf.registers[0]], rf.registers_for(make_cfg_arch)
  end
end
