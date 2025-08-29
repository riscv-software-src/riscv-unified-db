# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb
class CoveragePoint
  # @return [String] Unique name for coverage point
  attr_reader :name

  # @return [String] Number of bins (can be expression so is a String, not an Integer)
  attr_reader :bins

  # @return [String] Description of coverage point (could be multiple lines)
  attr_reader :description

  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines coverage point (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @name = data["name"]
    raise ArgumentError, "Missing name for coverage point for #{db_obj.name} of kind #{db_obj.kind}" if @name.nil?

    @bins = data["bins"]
    raise ArgumentError, "Missing bins for coverage point #{@name} of kind #{db_obj.kind}" if @bins.nil?

    @description = data["description"]
    raise ArgumentError, "Missing coverage point description for #{@name} of kind #{db_obj.kind}" if @description.nil?
  end

  # @param arch [Architecture]
  # @return [Array<NormativeRules>] Sorted list of normative rules referenced by this coverage point.
  def normative_rules(arch)
    raise ArgumentError, "Need Architecture but got class #{arch.class}" unless arch.is_a?(Architecture)

    @normative_rules = []

    arch.normative_rules.each do |nr|
      nr.coverage_point_names.each do |cp_name|
        @normative_rules << nr if cp_name == @name
      end
    end

    @normative_rules.sort_by!(&:name)
  end
end
end
