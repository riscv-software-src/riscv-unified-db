# Copyright (c) Animesh Agarwal
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

    class Role < T::Enum
      enums do
        Zero = new("zero")
        ReturnAddress = new("return_address")
        StackPointer = new("stack_pointer")
        GlobalPointer = new("global_pointer")
        ThreadPointer = new("thread_pointer")
        FramePointer = new("frame_pointer")
        ReturnValue = new("return_value")
        Argument = new("argument")
        Temporary = new("temporary")
      end
    end

  sig { returns(T::Hash[String, T.untyped]) }
  attr_reader :data

    sig { returns(Integer) }
    attr_reader :index

    sig { params(file: RegisterFile, data: T::Hash[String, T.untyped], index: Integer).void }
    def initialize(file, data, index)
      @file = file
      @data = data
      @index = index
    end

    sig { returns(String) }
    def name = @data.fetch("name")

    sig { returns(T::Array[String]) }
    def abi_mnemonics = @data.fetch("abi_mnemonics", [])

    sig { returns(T.any(Integer, String)) }
    def index = @index

    sig { returns(T.nilable(String)) }
    def description = @data["description"]

    sig { returns(T::Array[Role]) }
    def roles
      @roles ||= @data.fetch("roles", []).map { |role| Role.deserialize(role) }
    end

    sig { returns(T.nilable(T::Boolean)) }
    def caller_saved = @data["caller_saved"]

    sig { returns(T.nilable(T::Boolean)) }
    def callee_saved = @data["callee_saved"]

    sig { returns(T.nilable(String)) }
    def sw_read = @data["sw_read()"]

    sig { returns(T.nilable(String)) }
    def sw_write = @data["sw_write(value)"]

    sig { returns(T.nilable(ExtensionRequirementExpression)) }
    def defined_by_condition
      return nil unless @data.key?("definedBy")

      @defined_by_condition ||= ExtensionRequirementExpression.new(@data.fetch("definedBy"), @file.arch)
    end

    sig { returns(T.nilable(ExtensionRequirementExpression)) }
    def when_condition
      return nil unless @data.key?("when")

      @when_condition ||= ExtensionRequirementExpression.new(@data.fetch("when"), @file.arch)
    end
  end

  sig { returns(T.any(Integer, String)) }
  def register_length = @data.fetch("register_length")

  sig { returns(T.nilable(String)) }
  def summary = @data["summary"]

  sig { returns(T.nilable(String)) }
  def register_class = @data["register_class"]

  sig { returns(T::Array[RegisterEntry]) }
  def registers
    @registers ||= @data.fetch("registers", []).map.with_index { |reg, idx| RegisterEntry.new(self, reg, idx) }
  end

  sig { returns(T::Array[T::Hash[String, T.untyped]]) }
  def templates = @data.fetch("templates", [])
 end

end
