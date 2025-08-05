# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb
class NormativeRule
  # @return [String] Unique name of the normative rule
  #
  #
  # Where to put normative rules in UDB:
  #   - If a rule is only associated with one UDB database object (extension, instruction, CSR, or CSR field) put it in the
  #     YAML file for that database object.
  #   - If a rule spans multiple instructions or CSRS but only belongs to one extension, put it in that extension's YAML file.
  #     If the rule doesn't always apply when the extension is present (e.g., 64-bit instructions in I extension),
  #     add "when" statements with expressions to limit when the rule applies (e.g., XLEN == 64).
  #   - If a rule spans multiple extensions, put it in the I extension since it always is present and add
  #     appropriate "when" statements to express when the rule applies (e.g., "extension?(F) || extension?(D)")
  #     OR put it in a YAML file under the std/isa/normative_rule directory
  #     and add "when" statements to express when the rule applies (e.g., "extension?(F) || extension?(D)")
  attr_reader :name

  # @return [String] One of: "extension", "instruction", "CSR", "CSR field", or "parameter"
  attr_reader :type

  # @return [String] Description of normative rule (could be multiple lines)
  attr_reader :description

  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines normative rule (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @data = data

    @name = data["name"]
    raise ArgumentError, "Missing name for normative rule for #{db_obj.name} of kind #{db_obj.kind}" if @name.nil?

    @type = data["type"]
    raise ArgumentError, "Missing type for normative rule #{@name} for #{db_obj.name} of kind #{db_obj.kind}" if @type.nil?

    @description = data["description"]
    raise ArgumentError, "Missing normative rule description #{@name} for #{db_obj.name} of kind #{db_obj.kind}" if @description.nil?
  end

  # @return [Array<DocLink>] Sorted list of documentation links. Could be empty.
  def doc_links
    return @doc_links unless @doc_links.nil?

    @doc_links = []

    @data["doc_links"]&.each do |link_name|
      @doc_links << DocLink.new(link_name)
    end

    @doc_links.sort_by!(&:link_name)
  end

  # This can be called before all the coverage point objects have been created.
  # @return [Array<String>] Sorted list of coverage points names referenced by this normative rule
  def coverage_point_names
    return @coverage_point_names unless @coverage_point_names.nil?

    @coverage_point_names = []
    @data["coverage_points"]&.each do |cp_name|
      @coverage_point_names << cp_name
    end

    @coverage_point_names.sort!
  end

  # @param arch Architecture
  # @return [Array<CoveragePoints>] Sorted list of coverage points referenced by this normative rule
  def coverage_points(arch)
    raise ArgumentError, "Need Architecture but got class #{arch.class}" unless arch.is_a?(Architecture)

    return @coverage_points unless @coverage_points.nil?

    @coverage_points = []
    @data["coverage_points"]&.each do |cp_name|
      cp = arch.coverage_point(cp_name)
      raise ArgumentError, "Can't find coverage point '#{cp_name}' for normative rule '#{@name}'" if cp.nil?
      @coverage_points << cp
    end

    @coverage_points.sort_by!(&:name)
  end
end
end
