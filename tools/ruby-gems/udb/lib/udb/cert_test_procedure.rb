# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

require "sorbet-runtime"

module Udb

class CertTestProcedure
  extend T::Sig

  # @return [String] Unique name of the test procedure
  sig { returns(String) }
  attr_reader :name

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
  sig {params(data: T::Hash[String, T.untyped], db_obj: T.any(::Udb::Extension, ::Udb::Instruction, ::Udb::Csr, ::Udb::CsrField)).void }
  def initialize(data, db_obj)
    @data = data
    @db_obj = db_obj

    @name = T.must_because(data["name"]) { pp data }
    @description = T.must_because(data["description"]) { pp data }
    @kind = T.must_because(db_obj.kind) { pp db_obj }
    @test_file_name = data["test_file_name"]

    if test_file_name.nil?
      warn "Warning: Missing test_file_name for certification test procedure description #{name} of kind #{kind}"
    end
  end

  # @return [Array<NormativeRule>] List of normative rules referenced by this test procedure
  def normative_rules
    return @normative_rules unless @normative_rules.nil?

    @normative_rules = []
    @data["normative_rules"]&.each do |nr_name|
      nr = @db_obj.arch.normative_rule(nr_name)
      raise ArgumentError, "Can't find normative rule '#{nr_name}' for certification test procedure '#{@name}'" if nr.nil?
      @normative_rules << nr
    end
    @normative_rules
  end

  # @return [String] String (likely multi-line) of certification test procedure steps using Asciidoc lists
  def cert_steps = @data["steps"]
end
end
