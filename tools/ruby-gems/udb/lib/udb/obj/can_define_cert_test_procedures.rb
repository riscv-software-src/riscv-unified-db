# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Contains Ruby methods included in Ruby class definition for any database object that can have certification
# test procedures defined in the database object's YAML definition.

require_relative "../cert_test_procedure"

module Udb
module CertTestProcedure
  # @return [Array<CertTestProcedure>]
  def cert_test_procedures
    return @cert_test_procedures unless @cert_test_procedures.nil?

    @cert_test_procedures = []
    @data["cert_test_procedures"]&.each do |tp_data|
      @cert_test_procedures << CertTestProcedure.new(tp_data, self)
    end
    @cert_test_procedures
  end

  # @return [Hash<String, CertTestProcedure>] Hash of all certification test procedures defined by database object
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
