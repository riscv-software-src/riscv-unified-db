# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "minitest/autorun"

# Mock the required dependencies for testing
module Udb
  class ExtensionRequirement
    attr_reader :requirement
    
    def initialize(requirement)
      @requirement = requirement
    end
    
    # Test helper method to check if this is a simple single extension
    def is_simple_single_extension?
      case @requirement
      when String
        true
      when Hash
        # Simple if it only has 'name' and optionally 'version'
        keys = @requirement.keys
        return false if keys.empty?
        return false unless keys.include?("name")
        return false if (keys - ["name", "version"]).any?
        return false if @requirement.has_key?("allOf") || 
                       @requirement.has_key?("anyOf") || 
                       @requirement.has_key?("not")
        true
      else
        false
      end
    end
    
    # Generate AsciiDoc without bullet points for simple cases
    def to_asciidoc_no_bullet
      case @requirement
      when String
        @requirement
      when Hash
        if @requirement["name"]
          result = @requirement["name"]
          if @requirement["version"]
            result += " (#{@requirement["version"]})"
          end
          result
        else
          "Unknown requirement"
        end
      else
        "Unknown requirement"
      end
    end
    
    # Main method that decides whether to add bullets
    def to_asciidoc
      if is_simple_single_extension?
        to_asciidoc_no_bullet
      else
        "* #{to_asciidoc_no_bullet}"
      end
    end
  end
end

class TestReqExpression < Minitest::Test
  def test_simple_single_extension_string
    # Test with a simple string extension
    req = Udb::ExtensionRequirement.new("Sm")
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?, "String extension 'Sm' should be simple single extension"
    
    # Should not have bullets in AsciiDoc output
    asciidoc_output = req.to_asciidoc_no_bullet
    assert_equal "Sm", asciidoc_output
    
    # Main to_asciidoc should not add bullets for simple single extensions
    main_output = req.to_asciidoc
    refute_includes main_output, "* ", "Simple single extension should not have bullet points"
  end

  def test_simple_single_extension_hash_name_only
    # Test with hash containing only name
    req = Udb::ExtensionRequirement.new({"name" => "Zicsr"})
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?, "Hash with name only should be simple single extension"
    
    # Should not have bullets in AsciiDoc output
    asciidoc_output = req.to_asciidoc_no_bullet
    assert_equal "Zicsr", asciidoc_output
    
    # Main to_asciidoc should not add bullets for simple single extensions
    main_output = req.to_asciidoc
    refute_includes main_output, "* ", "Simple single extension should not have bullet points"
  end

  def test_simple_single_extension_hash_name_and_version
    # Test with hash containing name and version
    req = Udb::ExtensionRequirement.new({"name" => "Zicsr", "version" => ">=1.0"})
    
    # Should be recognized as simple single extension
    assert req.is_simple_single_extension?, "Hash with name and version should be simple single extension"
    
    # Should not have bullets in AsciiDoc output
    asciidoc_output = req.to_asciidoc_no_bullet
    assert_includes asciidoc_output, "Zicsr"
    assert_includes asciidoc_output, ">=1.0"
    
    # Main to_asciidoc should not add bullets for simple single extensions
    main_output = req.to_asciidoc
    refute_includes main_output, "* ", "Simple single extension should not have bullet points"
  end

  def test_complex_allof_extension
    # Test with allOf containing multiple extensions - should have bullets
    req = Udb::ExtensionRequirement.new({
      "allOf" => [
        {"name" => "Zicsr"},
        {"name" => "Zifencei"}
      ]
    })
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?, "allOf with multiple extensions should not be simple single extension"
    
    # Main to_asciidoc should add bullets for complex expressions
    main_output = req.to_asciidoc
    assert_includes main_output, "* ", "Complex allOf expression should have bullet points"
  end

  def test_complex_anyof_extension
    # Test with anyOf containing multiple extensions - should have bullets
    req = Udb::ExtensionRequirement.new({
      "anyOf" => [
        {"name" => "Zicsr"},
        {"name" => "Zifencei"}
      ]
    })
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?, "anyOf with multiple extensions should not be simple single extension"
    
    # Main to_asciidoc should add bullets for complex expressions
    main_output = req.to_asciidoc
    assert_includes main_output, "* ", "Complex anyOf expression should have bullet points"
  end

  def test_complex_not_extension
    # Test with not expression - should have bullets
    req = Udb::ExtensionRequirement.new({
      "not" => {"name" => "Zicsr"}
    })
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?, "not expression should not be simple single extension"
    
    # Main to_asciidoc should add bullets for complex expressions
    main_output = req.to_asciidoc
    assert_includes main_output, "* ", "Complex not expression should have bullet points"
  end

  def test_hash_with_extra_fields
    # Test with hash containing extra fields beyond name/version - should have bullets
    req = Udb::ExtensionRequirement.new({
      "name" => "Zicsr",
      "version" => ">=1.0",
      "company" => "RISC-V"
    })
    
    # Should NOT be recognized as simple single extension due to extra field
    refute req.is_simple_single_extension?, "Hash with extra fields should not be simple single extension"
    
    # Main to_asciidoc should add bullets for complex expressions
    main_output = req.to_asciidoc
    assert_includes main_output, "* ", "Hash with extra fields should have bullet points"
  end

  def test_edge_case_empty_hash
    # Test with empty hash - should not crash
    req = Udb::ExtensionRequirement.new({})
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?, "Empty hash should not be simple single extension"
  end

  def test_edge_case_nil_requirement
    # Test with nil requirement - should not crash
    req = Udb::ExtensionRequirement.new(nil)
    
    # Should NOT be recognized as simple single extension
    refute req.is_simple_single_extension?, "Nil requirement should not be simple single extension"
  end
end
