# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require_relative "database_obj"
require_relative "../req_expression"

module Udb

class RegisterFile < TopLevelDatabaseObject
  extend T::Sig

  class RegisterEntry
    extend T::Sig

    sig { returns(T::Hash[String, T.untyped]) }
    attr_reader :raw

    sig { params(file: RegisterFile, data: T::Hash[String, T.untyped]).void }
    def initialize(file, data)
      @file = file
      @raw = data
    end

    sig { returns(String) }
    def name = @raw.fetch("name")

    sig { returns(T.nilable(String)) }
    def abi_mnemonic = @raw["abi_mnemonic"]

    sig { returns(T.any(Integer, String)) }
    def index = @raw.fetch("index")

    sig { returns(T.nilable(String)) }
    def description = @raw["description"]

    sig { returns(T::Array[String]) }
    def roles = @raw.fetch("roles", [])

    sig { returns(T.nilable(T.any(Integer, String))) }
    def length = @raw["length"]

    sig { returns(T.nilable(ExtensionRequirementExpression)) }
    def defined_by_condition
      return nil unless @raw.key?("definedBy")

      @defined_by_condition ||= ExtensionRequirementExpression.new(@raw.fetch("definedBy"), @file.arch)
    end

    sig { returns(T.nilable(ExtensionRequirementExpression)) }
    def when_condition
      return nil unless @raw.key?("when")

      @when_condition ||= ExtensionRequirementExpression.new(@raw.fetch("when"), @file.arch)
    end
  end

  sig { returns(T.any(Integer, String)) }
  def length = @data.fetch("length")

  sig { returns(T.nilable(String)) }
  def summary = @data["summary"]

  sig { returns(T.nilable(String)) }
  def register_class = @data["register_class"]

  sig { returns(T.nilable(T.any(Integer, T::Hash[String, T.untyped]))) }
  def count = @data["count"]

  sig { returns(T::Array[RegisterEntry]) }
  def registers
    @registers ||= @data.fetch("registers", []).map { |reg| RegisterEntry.new(self, reg) }
  end

  sig { returns(T::Array[T::Hash[String, T.untyped]]) }
  def templates = @data.fetch("templates", [])
 end

end
