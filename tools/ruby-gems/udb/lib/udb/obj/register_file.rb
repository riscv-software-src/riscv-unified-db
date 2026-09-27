# Copyright (c) Animesh Agarwal
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require_relative "database_obj"
require_relative "../condition"

module Udb

class RegisterFile < TopLevelDatabaseObject
  extend T::Sig

  class RegisterEntry
    extend T::Sig

    class Role < T::Enum
      enums do
        Zero = new("zero")
        ReturnAddress = new("return_address")
        AlternateLinkRegister = new("alternate_link_register")
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

    sig { returns(T.nilable(String)) }
    def reset_value = @data["reset_value"]

    sig { returns(RegisterFile) }
    def register_file = @file

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
    def arch_read
      @data["arch_read()"] || @data["sw_read()"]
    end

    sig { returns(T.nilable(String)) }
    def arch_write
      @data["arch_write(value)"] || @data["sw_write(value)"]
    end

    sig { returns(T.nilable(String)) }
    def sw_read = arch_read

    sig { returns(T.nilable(String)) }
    def sw_write = arch_write

    sig { returns(T.nilable(AbstractCondition)) }
    def defined_by_condition
      return nil unless @data.key?("definedBy")

      @defined_by_condition ||= Condition.new(@data.fetch("definedBy"), @file.arch)
    end

    sig { returns(T.nilable(Condition)) }
    def when_condition
      return nil unless @data.key?("when")

      @when_condition ||= Condition.new(@data.fetch("when"), @file.arch)
    end
  end

  # Returns the IDL function body string for the register_length() field.
  # e.g. "return MXLEN;" or "return implemented?(ExtensionName::D) ? 64 : 32;"
  sig { returns(String) }
  def register_length = @data.fetch("register_length()")

  # Returns the stripped IDL expression (no 'return' keyword or trailing semicolon).
  sig { returns(String) }
  def register_length_expr
    register_length.strip.sub(/\Areturn\s+/, "").sub(/;\z/, "").strip
  end

  # Evaluate the register_length() IDL body against the given cfg_arch parameter context.
  # Returns an Integer if the width is statically determined, or a String param name
  # if the width depends on a runtime parameter (e.g. "VLEN").
  sig { params(cfg_arch: ConfiguredArchitecture).returns(T.any(Integer, String)) }
  def eval_register_length(cfg_arch)
    expr = register_length_expr

    # Literal integer
    return Integer(expr) if expr =~ /\A\d+\z/

    # Simple MXLEN reference
    if expr == "MXLEN"
      mxlen = cfg_arch.mxlen
      return mxlen || "MXLEN"  # Return String "MXLEN" for dynamic-XLEN configs
    end

    # Check for a fixed parameter
    fixed = cfg_arch.params_with_value.find { |p| p.name == expr }
    return T.cast(fixed.value, Integer).to_i if fixed

    # Check if it's a free parameter name
    free = cfg_arch.params_without_value.find { |p| p.name == expr }
    return expr if free

    # Complex expression — fall back to the architectural maximum.
    max_register_length
  end

  # Maximum value register_length() can return across all valid configurations.
  # Derived by compiling the register_length() expression against the full symtab
  # and calling max_value — unknown conditions (e.g. implemented?) cause the ternary
  # to return the max of both branches.
  sig { returns(Integer) }
  def max_register_length
    @max_register_length ||= _compute_max_register_length
  end

  private def _compute_max_register_length
    node = cfg_arch.idl_compiler.compile_expression(
      register_length_expr, cfg_arch.symtab, pass_error: true
    )
    max = node.max_value(cfg_arch.symtab)
    raise "Cannot determine max_register_length for register file '#{name}' " \
          "(register_length() expression: '#{register_length_expr}')" if max == :unknown
    Integer(max)
  end

  sig { returns(T.nilable(String)) }
  def summary = @data["summary"]

  sig { returns(T.nilable(String)) }
  def register_class = @data["register_class"]

  sig { returns(T::Array[RegisterEntry]) }
  def registers
    @registers ||= @data.fetch("registers", []).map.with_index { |reg, idx| RegisterEntry.new(self, reg, idx) }
  end

  sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Array[RegisterEntry]) }
  def registers_for(cfg_arch)
    registers.select do |register|
      condition = register.when_condition
      condition.nil? || condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
    end
  end

  sig { returns(T::Array[T::Hash[String, T.untyped]]) }
  def templates = @data.fetch("templates", [])
 end

end
