# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb
class NormativeRule
  # @return [String] Unique name of the normative rule
  #
  # Must adhere to the following naming convention:
  #   Database Object   Naming Convention                   Notes
  #   ===============   =================================   ===========================
  #   Base              B:<base-name>:<suffix>              Where <base-name> is rv32i, rv32e, or rv64i
  #   Instruction       I:<inst-name>:<suffix>
  #   Instruction       IL:<inst-name>[:<inst-name>]:<suffix> Multiple instructions
  #   Instruction       IG:<inst-group>:<suffix>            Named group of instructions
  #   Extension         E:<extension-name>:<suffix>
  #   CSR               C:<CSR-name>:<suffix>
  #   CSR Field         F:<CSR-name>:<field-name>:<suffix>
  #
  attr_reader :name

  # @return [String] Description of normative rule (could be multiple lines)
  attr_reader :description

  # @return [Array<DocLink>] List of documentation links. Could be empty.
  attr_reader :doc_links

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

    @doc_links = []
    data["doc_links"]&.each do |link_name|
      @doc_links << DocLink.new(link_name)
    end
  end

  # @return [Array<CoveragePoints>] List of coverage points referenced by this normative rule
  def coverage_points
    return @coverage_points unless @coverage_points.nil?

    @coverage_points = []
    @data["coverage_points"]&.each do |cp_name|
      cp = @db_obj.coverage_point(cp_name)
      raise ArgumentError, "Can't find coverage point '#{cp_name}' for normative rule '#{@name}'" if cp.nil?
      @coverage_points << nr
    end
    @coverage_points
  end
end
end
