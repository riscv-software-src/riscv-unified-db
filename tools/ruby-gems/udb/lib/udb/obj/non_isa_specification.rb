#!/usr/bin/env ruby
# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require 'yaml'
require 'pathname'
require 'sorbet-runtime'
require 'ostruct'
require_relative 'database_obj'

# Custom error classes for non-ISA specification processing
class NonIsaSpecificationError < StandardError; end
class NonIsaSpecificationLoadError < NonIsaSpecificationError; end
class NonIsaSpecificationValidationError < NonIsaSpecificationError; end

module Udb

##
# Clean non-ISA specification object that handles YAML-based specifications
class NonIsaSpecification
  include Kernel
  extend T::Sig

  sig { returns(String) }
  attr_reader :name

  sig { returns(T::Hash[String, T.untyped]) }
  attr_reader :data

  sig { returns(T.nilable(Pathname)) }
  attr_reader :spec_path

  sig { returns(T.nilable(T::Hash[String, T.untyped])) }
  attr_reader :spec_data

  sig { params(name: String, data: T::Hash[String, T.untyped]).void }
  def initialize(name, data)
    @name = name
    @data = data.dup
    @spec_data = nil
    @spec_path = nil
    load_spec_data
  end

  # Core spec data loading and validation
  sig { void }
  def load_spec_data
    base_path = Pathname.new(__dir__).parent.parent.parent.parent.parent.parent / "spec/custom/non_isa"
    @spec_path = base_path / "#{name}.yaml"
    return unless @spec_path.exist?

    begin
      @spec_data = YAML.safe_load_file(@spec_path, permitted_classes: [])
    rescue Psych::SyntaxError => e
      raise NonIsaSpecificationLoadError, "YAML syntax error in #{@spec_path}: #{e.message}"
    rescue => e
      raise NonIsaSpecificationLoadError, "Failed to load #{@spec_path}: #{e.message}"
    end
  end

  sig { returns(T::Boolean) }
  # Returns true if the spec is valid and has required fields.
  def valid?
    !@spec_data.nil? &&
      @spec_data['kind'] == 'non-isa specification' &&
      !@spec_data['name'].nil? &&
      !@spec_data['description'].nil?
  end

  sig { returns(String) }
  # Get the long name for display
  def long_name
    return @data['long_name'] if @data['long_name']
    return @spec_data['long_name'] if @spec_data&.dig('long_name')
    return @spec_data['name'] if @spec_data&.dig('name')
    name.split('_').map(&:capitalize).join(' ')
  end

  sig { returns(T.nilable(String)) }
  # Get the version if available
  def version
    @spec_data&.dig('version')
  end

  sig { returns(T.untyped) }
  # Get the main description prose array or string.
  def spec_description
    @spec_data&.dig('description')
  end

  sig { returns(T::Array[T::Hash[T.any(String, Symbol), T.untyped]]) }
  # Get the array of section hashes.
  def sections
    @spec_data&.dig('sections') || []
  end

  sig { returns(T::Array[T::Hash[T.any(String, Symbol), T.untyped]]) }
  # Get the array of reference hashes.
  def references
    @spec_data&.dig('references') || []
  end

  # Configuration methods
  sig { params(cfg_arch: T.untyped).returns(T::Boolean) }
  # Check if this non-ISA spec should be included in the given configuration
  def exists_in_cfg?(cfg_arch)
    return false unless valid?

    # Check configuration conditions if present
    when_condition = @data['when()'] || @spec_data&.dig('when()')
    return true if when_condition.nil?

    # Evaluate condition against cfg_arch
    # For now, simple string matching - could be enhanced with expression evaluation
    case when_condition
    when String
      # Basic string matching for now
      cfg_arch.param_values.any? { |k, v| when_condition.include?(k.to_s) }
    else
      true
    end
  end

  sig { params(cfg_arch: T.untyped).returns(T::Boolean) }
  # Check if this spec is optional in the given configuration
  def optional_in_cfg?(cfg_arch)
    # Non-ISA specs are generally optional unless marked as mandatory
    !(@data['mandatory'] == true || @spec_data&.dig('mandatory') == true)
  end

  sig { returns(T.untyped) }
  # Return configuration conditions that enable this spec
  def defined_by_condition
    when_condition = @data['when()'] || @spec_data&.dig('when()')
    return OpenStruct.new(to_asciidoc: "Always included") if when_condition.nil?

    # Convert condition to human-readable description
    OpenStruct.new(
      to_asciidoc: "When #{when_condition}"
    )
  end

  # Validation methods
  sig { returns(T::Array[String]) }
  # Validate all prose statement IDs and conventions for this spec.
  def validate_prose_ids
    return [] unless valid?

    issues = []
    statements = extract_prose_statements
    statements.each do |stmt|
      next unless stmt['id']
      id = stmt['id']
      source = stmt[:source] || 'unknown'

      # Check ID format according to prose-schema conventions
      unless valid_id_format?(id)
        issues << "Invalid ID format '#{id}' in #{source}: must be lowercase with underscores/hyphens only"
      end

      # Check for non-ISA specification naming convention
      unless valid_id_naming?(id)
        issues << "ID '#{id}' in #{source} should start with '#{name.downcase}-' for non-ISA specifications"
      end
    end

    # Check for duplicate IDs
    issues.concat(find_duplicate_ids(statements))
    issues
  end

  sig { params(include_sections: T::Boolean).returns(T::Array[T::Hash[T.any(String, Symbol), T.untyped]]) }
  # Extract all prose statements from description and sections, tagging their source.
  def extract_prose_statements(include_sections: true)
    statements = []
    # Extract from description
    if spec_description.is_a?(Array)
      spec_description.each_with_index { |stmt, i| statements << stmt.merge(source: "description[#{i}]") if stmt.is_a?(Hash) }
    end
    # Extract from sections
    if include_sections
      sections.each_with_index do |section, section_idx|
        next unless section['content'].is_a?(Array)
        section['content'].each_with_index do |stmt, stmt_idx|
          statements << stmt.merge(source: "sections[#{section_idx}].content[#{stmt_idx}]") if stmt.is_a?(Hash)
        end
      end
    end
    statements
  end

  # Rendering methods
  sig do
    params(
      cfg_arch: T.untyped,
      base_level: Integer,
      normative: T::Boolean,
      non_normative: T::Boolean
    ).returns(String)
  end
  # Configuration-aware rendering
  def render_for_cfg(cfg_arch, base_level: 3, normative: true, non_normative: true)
    return "" unless exists_in_cfg?(cfg_arch)

    to_asciidoc(
      base_level: base_level,
      normative: normative,
      non_normative: non_normative,
      when_callback: create_when_callback(cfg_arch)
    )
  end

  sig do
    params(
      base_level: Integer,
      normative: T::Boolean,
      non_normative: T::Boolean,
      when_callback: T.nilable(T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean))
    ).returns(String)
  end
  # Render the full specification as AsciiDoc, including description, sections, and references.
  def to_asciidoc(base_level: 3, normative: true, non_normative: true, when_callback: nil)
    return create_fallback_content(base_level) unless valid?

    content = []

    # Add main description prose
    desc_content = render_structured_prose(spec_description, normative: normative, non_normative: non_normative, when_callback: when_callback)
    content << desc_content if desc_content && !desc_content.empty?
    content << ""

    # Process all sections
    content.concat(render_sections(base_level, normative, non_normative, when_callback))

    # Add references section if present
    content.concat(render_references(base_level)) unless references.empty?

    content.join("\n")
  end

  private

  # Validation helper methods
  sig { params(id: String).returns(T::Boolean) }
  # IDs must be lowercase, start with a letter, and use only underscores/hyphens.
  def valid_id_format?(id)
    id.match?(/^[a-z][a-z0-9_-]*$/)
  end

  sig { params(id: String).returns(T::Boolean) }
  # IDs should start with spec name or allowed prefixes for non-ISA specs.
  def valid_id_naming?(id)
    id.start_with?(name.downcase) || id.match?(/^(ext|inst|csr)-/)
  end

  sig { params(statements: T::Array[T::Hash[T.any(String, Symbol), T.untyped]]).returns(T::Array[String]) }
  # Find duplicate IDs in the statements array.
  def find_duplicate_ids(statements)
    issues = []
    id_counts = Hash.new(0)
    statements.each { |stmt| id_counts[stmt['id']] += 1 if stmt['id'] }
    id_counts.each do |id, count|
      next if count == 1
      issues << "Duplicate ID '#{id}' appears #{count} times"
    end
    issues
  end

  # Rendering helper methods
  sig do
    params(
      base_level: Integer,
      normative: T::Boolean,
      non_normative: T::Boolean,
      when_callback: T.nilable(T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean))
    ).returns(T::Array[String])
  end
  # Render all sections, adjusting heading levels and filtering by callback.
  def render_sections(base_level, normative, non_normative, when_callback)
    content = []
    sections.each do |section|
      next unless should_include_section?(section, when_callback)
      level = section['level'] || (base_level + 1)
      content << "#{'=' * level} #{section['title']}"
      content << ""
      section_content = render_structured_prose(section['content'], normative: normative, non_normative: non_normative, when_callback: when_callback)
      content << section_content if section_content && !section_content.empty?
      content << ""
    end
    content
  end

  sig { params(base_level: Integer).returns(T::Array[String]) }
  # Render the references section as AsciiDoc, if any references exist.
  def render_references(base_level)
    content = []
    content << "#{'=' * (base_level + 1)} References"
    content << ""
    references.each do |ref|
      line = "* link:#{ref['url']}[#{ref['title']}]"
      line += " - #{ref['description']}" if ref['description']
      content << line
    end
    content << ""
    content
  end

  sig do
    params(
      prose_content: T.untyped,
      normative: T::Boolean,
      non_normative: T::Boolean,
      when_callback: T.nilable(T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean))
    ).returns(T.nilable(String))
  end
  # Render an array of prose statements as AsciiDoc, filtering by normative and conditional status.
  def render_structured_prose(prose_content, normative: true, non_normative: true, when_callback: nil)
    return nil if prose_content.nil?
    return "" unless prose_content.is_a?(Array)

    rendered_statements = []
    prose_content.each do |statement|
      next unless statement.is_a?(Hash) && statement['id'] && statement['text']

      # Filter by normative status
      stmt_normative = statement['normative']
      next if stmt_normative == true && !normative
      next if stmt_normative == false && !non_normative

      # Filter by when condition
      next if when_callback && !when_callback.call(statement['when()'], statement)

      rendered_statements << statement['text']
    end
    rendered_statements.join("\n\n")
  end

  sig do
    params(
      section: T::Hash[T.any(String, Symbol), T.untyped],
      when_callback: T.nilable(T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean))
    ).returns(T::Boolean)
  end
  # Determine if a section should be included based on its 'when()' condition and callback.
  def should_include_section?(section, when_callback = nil)
    when_condition = section['when()']
    return true if when_condition.nil?

    if when_callback
      when_callback.call(when_condition, section)
    else
      true
    end
  end

  sig { params(cfg_arch: T.untyped).returns(T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean)) }
  def create_when_callback(cfg_arch)
    T.let(
      lambda do |condition, _statement|
        # Simple implementation - could be enhanced with proper IDL evaluation
        if condition.nil?
          T.let(true, T::Boolean)
        else
          # For now, always include
          T.let(true, T::Boolean)
        end
      end,
      T.proc.params(arg0: T.untyped, arg1: T.untyped).returns(T::Boolean)
    )
  end

  sig { params(base_level: Integer).returns(String) }
  def create_fallback_content(base_level)
    "// Non-ISA specification '#{name}' not found or invalid\n" +
    "// This is a placeholder for missing content"
  end
end

end
