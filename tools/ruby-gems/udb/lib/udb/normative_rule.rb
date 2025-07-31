# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb
class NormativeRule
  # @return [String] Description of normative rule (could be multiple lines)
  attr_reader :description

  # @return [String] Unique ID of the normative rule
  #
  # Must adhere to the following naming convention:
  #   Database Object   Naming Convention                   Notes
  #   ===============   =================================   ===========================
  #   Base              B:<base-name>:<suffix>              Where <base-name> is rv32i, rv32e, or rv64i
  #   Instruction       I:<inst-name>:<suffix>
  #   Extension         E:<extension-name>:<suffix>
  #   CSR               C:<CSR-name>:<suffix>
  #   CSR Field         F:<CSR-name>:<field-name>:<suffix>
  #
  attr_reader :id

  # @return [Array<DocLink>] List of certification point documentation links. Could be empty.
  attr_reader :doc_links

  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines normative rule (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @id = data["id"]
    raise ArgumentError, "Missing normative rule ID for object of kind #{db_obj.kind}" if @id.nil?

    @description = data["description"]
    raise ArgumentError, "Missing normative rule description for ID #{db_obj.id} of kind #{db_obj.kind}" if @description.nil?

    @doc_links = []
    data["doc_links"]&.each do |link_name|
      @doc_links << DocLink.new(link_name)
    end
  end
end
end
