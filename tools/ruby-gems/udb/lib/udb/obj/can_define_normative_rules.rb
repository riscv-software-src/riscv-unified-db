# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Contains Ruby methods included in Ruby class definition for any database object that can have
# normative rules defined in the database object's YAML definition.

require_relative "../normative_rule"

module Udb
module CanDefineNormativeRules
  # @return [Array<NormativeRule>] All normative rules defined by this database object
  def normative_rules
    return @normative_rules unless @normative_rules.nil?

    @normative_rules = []
    @data["normative_rules"]&.each do |cert_data|
      nr = NormativeRule.new(cert_data, self)
      arch.add_normative_rule(nr)
      @normative_rules << nr
    end
    @normative_rules
  end

  # @return [Hash<String, NormativeRule>] Hash with name as key of all normative rules defined by database object
  def normative_rules_hash
    return @normative_rules_hash unless @normative_rules_hash.nil?

    @normative_rules_hash = {}
    normative_rules.each do |nr|
      @normative_rules_hash[nr.name] = nr
    end
    @normative_rules_hash
  end

  # @param nr_name [String] Unique name for the normative rule
  # @return [NormativeRule]
  # @return [nil] if there is no normative rule with name of +nr_name+
  def normative_rule(nr_name) = normative_rules_hash[nr_name]
end # module
end
