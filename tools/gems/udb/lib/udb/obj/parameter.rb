# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: strict

require "idlc/interfaces"

require_relative "database_obj"
require_relative "../schema"
require_relative "../version"

module Udb

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class Parameter
  extend T::Sig
  include Idl::RuntimeParam

  raise "Huh" unless ::Idl::Type.new(:bits, width: 5).integral?

  # @return [Architecture] The defining architecture
  sig { returns(ConfiguredArchitecture) }
  attr_reader :cfg_arch

  # @return [String] Parameter name
  sig { override.returns(String) }
  def name = @name

  # @return [String] Asciidoc description
  sig { override.returns(String) }
  attr_reader :desc

  # @return [Schema] JSON Schema for this param
  sig { override.returns(Schema) }
  attr_reader :schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validation
  sig { returns(T.nilable(String)) }
  attr_reader :extra_validation

  # Some parameters are defined by multiple extensions (e.g., CACHE_BLOCK_SIZE by Zicbom and Zicboz).
  # When defined in multiple places, the parameter *must* mean the exact same thing.
  #
  # @return [Array<Extension>] The extension(s) that define this parameter
  sig { returns(T::Array[Extension]) }
  attr_reader :exts

  # @returns [Idl::Type] Type of the parameter
  sig { override.returns(Idl::Type) }
  attr_reader :idl_type

  # Pretty convert extension schema to a string.
  sig { returns(String) }
  def schema_type
    @schema.to_pretty_s
  end

  # @returns [Object] default value, or nil if none
  sig { returns(T.nilable(Object)) }
  def default
    if T.cast(@data["schema"], T::Hash[String, Object]).key?("default")
      T.cast(@data["schema"], T::Hash[String, Object])["default"]
    end
  end

  sig { params(ext: Extension, name: String, data: T::Hash[String, T.untyped]).void }
  def initialize(ext, name, data)

    @cfg_arch = T.let(ext.cfg_arch, ConfiguredArchitecture)
    @data = T.let(data, T::Hash[String, T.untyped])
    @name = T.let(name, String)
    @desc = T.let(T.cast(data["description"], String), String)
    @schema = T.let(Schema.new(data["schema"]), Schema)
    @extra_validation = T.let(data.key?("extra_validation") ? T.let(T.cast(data["extra_validation"], String), String) : nil, T.nilable(String))
    also_defined_in_array = []
    also_defined_in_data = data["also_defined_in"]
    unless also_defined_in_data.nil?
      other_ext = T.let(nil, T.nilable(Extension))
      if also_defined_in_data.is_a?(String)
        other_ext_name = also_defined_in_data
        other_ext = @cfg_arch.extension(other_ext_name)
        raise "Definition error in #{ext.name}.#{name}: #{other_ext_name} is not a known extension" if other_ext.nil?

        also_defined_in_array << other_ext
      else
        unless also_defined_in_data.is_a?(Array) && also_defined_in_data.all? { |e| e.is_a?(String) }
          raise "schema error: also_defined_in should be a string or array of strings"
        end

        also_defined_in_data.each do |other_ext_name|
          other_ext = @cfg_arch.extension(other_ext_name)
          raise "Definition error in #{ext.name}.#{name}: #{also_defined_in_data} is not a known extension" if other_ext.nil?

          also_defined_in_array << other_ext
        end
      end
    end
    @exts = T.let([ext] + also_defined_in_array, T::Array[Extension])
    @idl_type = T.let(@schema.to_idl_type.make_const.freeze, ::Idl::Type)
    @when = T.let(nil, T.nilable(ExtensionRequirementExpression))
  end

  # @return [ExtensionRequirementExpression] Condition when the parameter exists
  sig { returns(ExtensionRequirementExpression) }
  def when
    @when ||=
      if @data["when"].nil?
        # the parent extension is implictly required
        cond =
          if @exts.size > 1
            { "anyOf" => @exts.map { |ext| { "name" => ext.name, "version" => ">= #{ext.min_version.version_str}" } }}
          else
            { "name" => @exts.fetch(0).name, "version" => ">= #{@exts.fetch(0).min_version.version_str}"}
          end
        ExtensionRequirementExpression.new(cond, @cfg_arch)
      else
        # the parent extension is implictly required
        cond =
          if @exts.size > 1
            { "allOf" => [{"anyOf" => @exts.map { |ext| { "name" => ext.name, "version" => ">= #{ext.min_version.version_str}" } } }, @data["when"]] }
          else
            { "allOf" => [ { "name" => @exts.fetch(0).name, "version" => ">= #{@exts.fetch(0).min_version.version_str}"}, @data["when"]] }
          end
        ExtensionRequirementExpression.new(cond, @cfg_arch)
      end
  end

  # @param cfg_arch [ConfiguredArchitecture]
  # @return [Boolean] if this parameter is defined in +cfg_arch+
  sig { params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def defined_in_cfg?(cfg_arch)
    if @exts.none? { |ext| cfg_arch.possible_extensions.any? { |e| e.name == ext.name } }
      return SatisfiedResult::No
    end

    if @when.nil?
      return SatisfiedResult::Yes
    end

    @when.satisfied_by_cfg_arch?(cfg_arch)
  end

  # @param exts [Array<Extension>] List of all in-scope extensions that define this parameter.
  # @return [String] Text to create a link to the parameter definition with the link text the parameter name.
  #                  if only one extension defines the parameter, otherwise just the parameter name.
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
  def value = raise "Parameter value not known"
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

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validatino
  sig { returns(T.nilable(String)) }
  def extra_validation = @param.extra_validation

  sig { returns(T::Array[Extension]) }
  def exts = @param.exts

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
