# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

require "sorbet-runtime"

class Udb::CertTestProcedure
  extend T::Sig

  # @return [String] Unique ID of the test procedure
  sig { returns(String) }
  attr_reader :id

  # Description of test procedure (could be multiple lines).
  sig { returns(String) }
  attr_reader :description

  # What kind of database object is this?
  sig { returns(String) }
  attr_reader :kind

  # Name of test file that implements this test procedure. Could be nil.
  sig { returns(T.nilable(String)) }
  attr_reader :test_file_name

  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines test procedure (Extension, Instruction, CSR, or CSR field)
  sig {params(data: T::Hash[String, T.untyped], db_obj: T.any(Extension, Instruction, Csr, CsrField)).void }
  def initialize(data, db_obj)
    @data = data
    @db_obj = db_obj

    @id = T.must_because(data["id"]) { pp data }
    @description = T.must_because(data["description"]) { pp data }
    @kind = T.must_because(db_obj.kind) { pp db_obj }
    @test_file_name = data["test_file_name"]

    if test_file_name.nil?
      warn "Warning: Missing test_file_name for certification test procedure description for ID #{id} of kind #{kind}"
    end
  end

  # @return [Array<CertNormativeRule>]
  def cert_normative_rules
    return @cert_normative_rules unless @cert_normative_rules.nil?

    @cert_normative_rules = []
    @data["normative_rules"]&.each do |id|
      cp = @db_obj.cert_coverage_point(id)
      raise ArgumentError, "Can't find certification test procedure with ID '#{id}' for '#{@db_obj.name}' of kind #{@db_obj.kind}" if cp.nil?
      @cert_normative_rules << cp
    end
    @cert_normative_rules
  end

  # @return [String] String (likely multiline) of certification test procedure steps using Asciidoc lists
  def cert_steps = @data["steps"]
end
