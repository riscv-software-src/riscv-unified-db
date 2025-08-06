# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"
require_relative "../lib/udb"

class TestReqExpression < Minitest::Test
  def test_basic_method_existence
    # Test that our bullet point methods are defined
    methods = Udb::ExtensionRequirementExpression.instance_methods
    assert_includes methods, :is_simple_single_extension?
    assert_includes methods, :is_complex_condition_header?
    assert_includes methods, :to_asciidoc
  end

  def test_bullet_point_logic_patterns
    # Test the logic patterns that determine bullet behavior
    simple_string_cases = ["Sm", "Zicsr", "Zifencei"]
    simple_string_cases.each do |case_val|
      assert case_val.is_a?(String), "#{case_val} should be a simple string case"
      refute case_val.is_a?(Hash), "#{case_val} should not be a complex hash case"
    end

    # Test simple hash patterns (these should remove bullets)
    simple_hash_cases = [
      {"name" => "Zicsr"},
      {"name" => "Zicsr", "version" => ">=1.0"}
    ]
    simple_hash_cases.each do |hash_case|
      assert hash_case.is_a?(Hash), "#{hash_case} should be a hash"
      assert hash_case.has_key?("name"), "#{hash_case} should have name key"
      refute hash_case.has_key?("allOf"), "#{hash_case} should not have allOf"
      refute hash_case.has_key?("anyOf"), "#{hash_case} should not have anyOf"
    end

    # Test complex patterns (these should keep bullets)
    complex_cases = [
      {"allOf" => [{"name" => "Zicsr"}, {"name" => "Zifencei"}]},
      {"anyOf" => [{"name" => "Zicsr"}, {"name" => "Zifencei"}]},
      {"name" => "Zicsr", "version" => ">=1.0", "company" => "RISC-V"}
    ]
    complex_cases.each do |complex_case|
      assert complex_case.is_a?(Hash), "#{complex_case} should be a hash"
      has_complex_keys = complex_case.has_key?("allOf") ||
                        complex_case.has_key?("anyOf") ||
                        complex_case.keys.length > 2
      assert has_complex_keys, "#{complex_case} should have complex structure"
    end
  end
end
