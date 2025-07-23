# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "idlc/interfaces"

require_relative "database_obj"
require_relative "../schema"
require_relative "../version"

module Udb

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class Parameter < TopLevelDatabaseObject
  extend T::Sig
  include Idl::RuntimeParam

  # @return The defining architecture
  sig { returns(ConfiguredArchitecture) }
  attr_reader :cfg_arch

  # @return Parameter name
  sig { override.returns(String) }
  def name = @name

  # @return Asciidoc description
  sig { override.returns(String) }
  attr_reader :desc

  # @return JSON Schema for this param
  sig { override.returns(Schema) }
  attr_reader :schema

  # @returns Type of the parameter
  sig { override.returns(Idl::Type) }
  attr_reader :idl_type

  # Pretty convert extension schema to a string.
  sig { returns(String) }
  def schema_type
    @schema.to_pretty_s
  end

  sig { returns(T::Array[Constraint]) }
  def restrictions
    @restrictions ||=
      begin
        if @data["restrictions"].nil?
          []
        else
          @data["restictoins"].map do |restriction|
            Constraint.new(
              restriction["constraint()"],
              input_file: nil,
              input_line: nil,
              cfg_arch: @cfg_arch,
              reason: restriction["reason"]
            )
          end
        end
      end
  end

  # @returns default value, or nil if none
  sig { returns(T.nilable(Object)) }
  def default
    if T.cast(@data["schema"], T::Hash[String, Object]).key?("default")
      T.cast(@data["schema"], T::Hash[String, Object])["default"]
    end
  end

  sig {
    params(
      yaml: T::Hash[String, T.untyped],
      data_path: T.any(String, Pathname),
      cfg_arch: ConfiguredArchitecture
    ).void
  }
  def initialize(yaml, data_path, cfg_arch)
    super(yaml, data_path, cfg_arch)

    @schema = T.let(Schema.new(data["schema"]), Schema)
    @idl_type = T.let(@schema.to_idl_type.make_const.freeze, ::Idl::Type)
  end

  # @return if this parameter is defined in +cfg_arch+
  sig { params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def defined_in_cfg?(cfg_arch)
    defined_by_condition.satisfied_by_cfg_arch?(cfg_arch)
  end

  # @param exts List of all in-scope extensions that define this parameter.
  # @return Text to create a link to the parameter definition with the link text the parameter name.
  #         if only one extension defines the parameter, otherwise just the parameter name.
  sig { params(in_scope_exts: T::Array[Extension]).returns(String) }
  def name_potentially_with_link(in_scope_exts)

    helper = Class.new do include Udb::Helpers::TemplateHelpers end
    if in_scope_exts.size == 1
      helper.new.link_to_udb_doc_ext_param(in_scope_exts.fetch(0).name, name, name)
    else
      name
    end
  end

  # sorts by name
  sig { params(other: Parameter).returns(T.nilable(Integer)) }
  def <=>(other) = @name <=> other.name

  sig { returns(String) }
  def to_idl = "#{idl_type.to_idl} #{name}"

  sig { override.returns(T::Boolean) }
  def value_known? = false

  sig { override.returns(Idl::RuntimeParam::ValueType) }
  def value = raise "Parameter value not known for #{name}"
end

class ParameterWithValue
  extend T::Sig
  include Idl::RuntimeParam

  # @return [Object] The parameter value
  sig { override.returns(Idl::RuntimeParam::ValueType) }
  attr_reader :value

  # @return [String] Parameter name
  sig { override.returns(String) }
  def name = @param.name

  # @return [String] Asciidoc description
  sig { override.returns(String) }
  def desc = @param.desc

  # @return [Hash] JSON Schema for the parameter value
  sig { override.returns(Schema) }
  def schema = @param.schema

  # @returns [Idl::Type] Type of the parameter
  sig { override.returns(Idl::Type) }
  def idl_type = @param.idl_type

  sig { params(param: Parameter, value: Idl::RuntimeParam::ValueType).void }
  def initialize(param, value)
    @param = param
    @value = value
  end

  sig { override.returns(T::Boolean) }
  def value_known? = true
end

end
