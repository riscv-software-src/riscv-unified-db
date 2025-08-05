# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb
class NormativeRule
  # @return [String] Unique name of the normative rule
  #
  # Must adhere to the following naming convention.
  # The <id> is a unique suffix that describes the normative rule.
  # The convention is similar to the doc_link naming convention but more compact and tailored to UDB object types.
  #
  #   Object        Naming Convention                               Associated ISA features
  #   ============  =============================================== =========================================
  #   Extension     E:<ext-name>:<id>                               Single extension
  #                 EL:<ext-name>[_<ext-name>]:<id>                 List of extensions
  #                 EG:<group-name>:<id>                            Named group of extensions
  #   Instruction   I:<inst-name>:<id>                              Single instruction
  #                 IL:<inst-name>[_<inst-name>]+:<id>              List of instructions
  #                 IG:<group-name>:<id>                            Named group of insts (e.g., branch, load)
  #   CSR           C:<csr-name>:<id>                               Single CSR
  #                 CL:<csr-name>[_<csr-name>]+:<id>                List of CSRs
  #                 CG:<group-name>:<id>                            Named group of CSRs
  #   CSR Field     F:<csr-name>:<field-name>:<id>                  Single CSR field
  #                 FL:<csr-name>:<field-name>[_<field-name>]+:<id> List of fields in the same CSR
  #                 FG:<csr-name>:<group-name>:<id>                 Named group of CSR fields in the same CSR
  #                 CFG:csr-name>[_<csr-name>]+:<field-name>:<id>   Same field in the listed CSRs
  #   Parameter     P:<param-name>:<id>                             Single parameter
  #                 PL:<param-name>[_<param-name>]+:<id>            List of parameters
  #                 PG:<group-name>:<id>                            Named group of parameters
  attr_reader :name

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
