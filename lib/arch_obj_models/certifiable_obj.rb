# frozen_string_literal: true

require_relative "cert_normative_rule"
require_relative "cert_test_procedure"

module CertifiableObject
  # @return [Array<CertNormativeRule>]
  def cert_normative_rules
    return @cert_normative_rules unless @cert_normative_rules.nil?

    @cert_normative_rules = []
    @data["cert_normative_rules"]&.each do |cert_data|
      @cert_normative_rules << CertNormativeRule.new(cert_data, self)
    end
    @cert_normative_rules
  end

  # @return [Hash<String, CertNormativeRule>] Hash with ID as key of all normative rules defined by database object
  def cert_coverage_point_hash
    return @cert_coverage_point_hash unless @cert_coverage_point_hash.nil?

    @cert_coverage_point_hash = {}
    cert_normative_rules.each do |cp|
      @cert_coverage_point_hash[cp.id] = cp
    end
    @cert_coverage_point_hash
  end

  # @param id [String] Unique ID for the normative rule
  # @return [CertNormativeRule]
  # @return [nil] if there is no certification normative ruleed with ID of +id+
  def cert_coverage_point(id)
    cert_coverage_point_hash[id]
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
