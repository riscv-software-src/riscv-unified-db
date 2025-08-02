# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "minitest/autorun"
require_relative "../lib/udb/req_expression"

# Mock architecture for testing  
class MockArch
  def extension(name)
    MockExtension.new
  end
end

class MockExtension
  def min_version
    "1.0"
  end
end

class TestReqExpression < Minitest::Test
  def setup
    @arch = MockArch.new
  end

  def test_simple_single_extension_string
    # Test with a simple string extension
    req = Udb::ExtensionRequirement.new("Sm", @arch)
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?("Sm"), "String extension 'Sm' should be simple single extension"
    
    # Should not have bullets in AsciiDoc output when called without indent
    asciidoc_output = req.to_asciidoc("Sm", 0)
    refute_includes asciidoc_output, "* ", "Simple single extension should not have bullet points at root level"
    assert_includes asciidoc_output, "Sm", "Should contain extension name"
  end

  def test_simple_single_extension_hash_name_only
    # Test with hash containing only name
    cond = {"name" => "Zicsr"}
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?(cond), "Hash with name only should be simple single extension"
    
    # Should not have bullets in AsciiDoc output at root level
    asciidoc_output = req.to_asciidoc(cond, 0)
    refute_includes asciidoc_output, "* ", "Simple single extension should not have bullet points at root level"
    assert_includes asciidoc_output, "Zicsr", "Should contain extension name"
  end

  def test_simple_single_extension_hash_name_and_version
    # Test with hash containing name and version
    cond = {"name" => "Zicsr", "version" => ">=1.0"}
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?(cond), "Hash with name and version should be simple single extension"
    
    # Should not have bullets in AsciiDoc output at root level
    asciidoc_output = req.to_asciidoc(cond, 0)
    refute_includes asciidoc_output, "* ", "Simple single extension should not have bullet points at root level"
    assert_includes asciidoc_output, "Zicsr", "Should contain extension name"
    assert_includes asciidoc_output, ">=1.0", "Should contain version"
  end

  def test_complex_allof_extension
    # Test with allOf containing multiple extensions - should have bullets
    cond = {
      "allOf" => [
        {"name" => "Zicsr"},
        {"name" => "Zifencei"}
      ]
    }
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?(cond), "allOf with multiple extensions should not be simple single extension"
    
    # Should have bullets for complex expressions
    asciidoc_output = req.to_asciidoc(cond, 0)
    assert_includes asciidoc_output, "*", "Complex allOf expression should have bullet points"
  end

  def test_complex_anyof_extension
    # Test with anyOf containing multiple extensions - should have bullets
    cond = {
      "anyOf" => [
        {"name" => "Zicsr"},
        {"name" => "Zifencei"}
      ]
    }
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?(cond), "anyOf with multiple extensions should not be simple single extension"
    
    # Should have bullets for complex expressions
    asciidoc_output = req.to_asciidoc(cond, 0)
    assert_includes asciidoc_output, "*", "Complex anyOf expression should have bullet points"
  end

  def test_hash_with_extra_fields
    # Test with hash containing extra fields beyond name/version - should have bullets
    cond = {
      "name" => "Zicsr",
      "version" => ">=1.0",
      "company" => "RISC-V"
    }
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should NOT be recognized as simple single extension due to extra field (size > 2)
    refute req.is_simple_single_extension?(cond), "Hash with extra fields should not be simple single extension"
  end

  def test_edge_case_empty_hash
    # Test with empty hash - should not crash
    cond = {}
    req = Udb::ExtensionRequirement.new(cond, @arch)
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?(cond), "Empty hash should not be simple single extension"
  end
end
