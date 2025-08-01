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

    @bin = data["bin"]
    raise ArgumentError, "Missing bin for coverage point #{@name} of kind #{db_obj.kind}" if @bin.nil?

    @description = data["description"]
    raise ArgumentError, "Missing coverage point description for #{@name} of kind #{db_obj.kind}" if @description.nil?
  end
end
end
