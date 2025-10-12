# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "idlc/interfaces"

require_relative "../condition"
require_relative "database_obj"
require_relative "../schema"
require_relative "../version"


module Udb
  class Schema; end
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

    # Pretty convert extension schema to a string.
    sig { returns(String) }
    def schema_type
      @schema.to_pretty_s
    end

    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        begin
          if @data["requirements"].nil?
            Condition::True
          else
            Condition.new(
              @data.fetch("requirements"),
              @cfg_arch,
              input_file: Pathname.new(__source),
              input_line: source_line(["requirements"])
            )
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

    class ConditionalSchema < T::Struct
      const :cond, AbstractCondition
      const :schema, Schema
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

      @schemas = T.let([], T::Array[ConditionalSchema])
      if data.fetch("schema").key?("oneOf")
        data.fetch("schema").fetch("oneOf").each do |cond_schema|
          @schemas << ConditionalSchema.new(schema: Schema.new(cond_schema.fetch("schema")), cond: Condition.new(cond_schema.fetch("when"), @cfg_arch))
        end
      else
        @schemas << ConditionalSchema.new(schema: Schema.new(data["schema"]), cond: AlwaysTrueCondition.new)
      end
    end

    sig { override.params(resolver: Resolver).void }
    def validate(resolver)

    end

    # whether or not the schema is unambiguously known
    # since schemas can change based on parameter values and/or extension presence,
    # non-full configs may not be able to know which schema applies
    sig { override.returns(T::Boolean) }
    def schema_known?
      @schema_known ||= begin
        if @schemas.size == 1
          true
        else
          1 == @schemas.count { |cond_schema| cond_schema.cond.could_be_satisfied_by_cfg_arch?(@cfg_arch) }
        end
      end
    end

    # @return JSON Schema for this param
    # @raises RuntimeError if schema_known? is false
    sig { override.returns(Schema) }
    def schema
      unless schema_known?
        raise "Schema is not known for parameter #{name} because more than one is possible given what we know about the configuration"
      end

      @schema ||= T.must(@schemas.find { |cond_schema| cond_schema.cond.satisfied_by_cfg_arch?(@cfg_arch) == SatisfiedResult::Yes }).schema
    end

    sig { returns(T::Array[ConditionalSchema]) }
    attr_reader :schemas

    class NoMatchingSchemaError < RuntimeError; end

    # @return list of schemas that are possible for this config
    sig { override.returns(T::Array[Schema]) }
    def possible_schemas
      @possible_schemas ||=
        begin
          list = @schemas.select { |s| s.cond.could_be_satisfied_by_cfg_arch?(@cfg_arch) }.map(&:schema)
          if list.empty?
            raise NoMatchingSchemaError, "Parameter #{name} has no matching schema for #{@cfg_arch.name}"
          end
          list
        end
    end

    sig { override.returns(T::Array[Schema]) }
    def all_schemas
      @schemas.map(&:schema)
    end

    # @returns Type of the parameter
    # @raises RuntimeError if schema_known? if false
    sig { override.returns(Idl::Type) }
    def idl_type
      unless schema_known?
        raise "Schema is not known for parameter #{name} because more than one is possible given what we know about the configuration"
      end

      @idl_type ||= schema.to_idl_type.make_const.freeze
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
    sig { override.params(other: T.untyped).returns(T.nilable(Integer)) }
    def <=>(other)
      return nil unless other.is_a?(Idl::RuntimeParam)

      @name <=> other.name
    end

    sig { returns(String) }
    def to_idl = "#{idl_type.to_idl} #{name}"

    sig { override.returns(T::Boolean) }
    def value_known? = false

    sig { override.returns(Idl::RuntimeParam::ValueType) }
    def value = raise "Parameter value not known for #{name}"
  end

  class ParameterWithValue
    extend T::Sig
    extend Forwardable
    include Idl::RuntimeParam

    def_delegators :@param,
      :name, :desc, :schema_known?, :schema, :schemas, :possible_schemas, :all_schemas, :idl_type,
      :defined_by_condition, :requirements_condition

    # @return [Object] The parameter value
    sig { override.returns(Idl::RuntimeParam::ValueType) }
    attr_reader :value

    sig { params(param: Parameter, value: Idl::RuntimeParam::ValueType).void }
    def initialize(param, value)
      @param = param
      @value = value
    end

    sig { override.returns(T::Boolean) }
    def value_known? = true
  end

end
