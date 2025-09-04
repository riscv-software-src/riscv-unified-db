# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Contains Ruby methods included in Ruby class definition for any database object that can have
# normative rules listed in the database object's YAML definition.

require_relative "../normative_rule_req"

module Udb
module CanHaveNormativeRuleReqs
  # @return [Array<NormativeRuleReq>] All normative rule requirements defined by this database object sorted by name
  def normative_rule_reqs
    return @normative_rule_reqs unless @normative_rule_reqs.nil?

    @normative_rule_reqs = []
    @data["normative_rules"]&.each do |nrr_data|
      @normative_rule_reqs << NormativeRuleReq.new(nrr_data, self)
    end
    @normative_rule_reqs
  end

  # @return [Hash<String, NormativeRuleReq>] Hash with name as key of all normative rule reqs created by database object
  def normative_rule_reqs_hash
    return @normative_rule_reqs_hash unless @normative_rule_reqs_hash.nil?

    @normative_rule_reqs_hash = {}
    normative_rule_reqs.each do |nrr|
      @normative_rule_reqs_hash[nrr.name] = nrr
    end
    @normative_rule_reqs_hash
  end

  # @param name [String] Name of the normative rule
  # @return [NormativeRuleReq]
  # @return [nil] if there is no normative rule req with name of +name+
  def normative_rule_req(name) = normative_rule_reqs_hash[name]
end # module
end
