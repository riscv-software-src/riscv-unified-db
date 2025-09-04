# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "obj/database_obj"

module Udb

# Contains one Normative Rule requirement
class NormativeRuleReq
  # @return [String] Normative rule name (mandatory)
  attr_reader :name

  # @return [String] When expression (optional)
  attr_reader :when

  # @param data [Hash<String, Object>] Data from YAML file for requirement
  # @param db_obj [DatabaseObject] Database object that has a normative rule requirement
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject for db_obj but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @name = data["name"]
    if @name.nil?
      raise ArgumentError, "Missing name for normative rule requirement in #{db_obj.name} of kind #{db_obj.kind}"
    end

    @when = data["when"]
  end
end
end
