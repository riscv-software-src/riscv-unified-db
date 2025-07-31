# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Contains Ruby methods included in Ruby class definition for any database object that can have normative rules and
# certification test procedures defined in the database object's YAML definition.

require_relative "../normative_rule"
require_relative "../cert_test_procedure"

module Udb
module CertifiableObject
  # @return [Array<NormativeRule>] All normative rules defined by this certifiable_object
  def normative_rules
    return @normative_rules unless @normative_rules.nil?

    @normative_rules = []
    @data["normative_rules"]&.each do |cert_data|
      @normative_rules << NormativeRule.new(cert_data, self)
    end
    @normative_rules
  end

  # @return [Hash<String, NormativeRule>] Hash with ID as key of all normative rules defined by database object
  def normative_rules_hash
    return @normative_rules_hash unless @normative_rules_hash.nil?

    @normative_rules_hash = {}
    normative_rules.each do |nr|
      @normative_rules_hash[nr.id] = nr
    end
    @normative_rules_hash
  end

  # @param id [String] Unique ID for the normative rule
  # @return [NormativeRule]
  # @return [nil] if there is no normative rule with ID of +id+
  def normative_rule(id)
    normative_rules_hash[id]
  end

  # @return [Array<CertTestProcedure>]
  def cert_test_procedures
    return @cert_test_procedures unless @cert_test_procedures.nil?

    @cert_test_procedures = []
    @data["cert_test_procedures"]&.each do |cert_data|
      @cert_test_procedures << CertTestProcedure.new(cert_data, self)
    end
    @cert_test_procedures
  end

  # @return [Hash<String, CertTestProcedure>] Hash of all normative rules defined by database object
  def cert_test_procedure_hash
    return @cert_test_procedure_hash unless @cert_test_procedure_hash.nil?

    @cert_test_procedure_hash = {}
    cert_test_procedures.each do |tp|
      @cert_test_procedure_hash[tp.id] = tp
    end
    @cert_test_procedure_hash
  end

  # @param id [String] Unique ID for test procedure
  # @return [CertTestProcedure]
  # @return [nil] if there is no certification test procedure with ID +id+
  def cert_test_procedure(id)
    cert_test_procedure_hash[id]
  end
end # module
end
