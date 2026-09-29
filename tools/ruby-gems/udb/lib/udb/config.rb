# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "pathname"
require "forwardable"
require "yaml"
require_relative "obj/portfolio"

module Udb
  extend T::Sig

  class ConfigType < T::Enum
    enums do
      UnConfig = new("unconfigured")
      Full = new("fully configured")
      Partial = new("partially configured")
    end
  end

# This class represents a configuration. Is is coded as an abstract base class (must be inherited by a child).
#
# There are child classes derived from AbstractConfig to handle:
#   - Configurations specified by YAML files in the /cfg directory
#   - Configurations specified by portfolio groups (certificates and profile releases)
  class AbstractConfig
    extend T::Sig
    extend T::Helpers
    abstract!

    ParamValueType = T.type_alias { T.any(Integer, String, T::Boolean, T::Array[Integer], T::Array[String], T::Array[T::Boolean]) }

    ####################
    # ABSTRACT METHODS #
    ####################

    # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has
    #                                been configured with a value. May be empty.
    sig { abstract.returns(T::Hash[String, ParamValueType]) }
    def param_values; end

    # @return [Boolean] Is an overlay present?
    sig { returns(T::Boolean) }
    def overlay?  = !(@data["arch_overlay"].nil? || @data["arch_overlay"].empty?)

    # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
    # @return [nil] No arch_overlay for this config
    sig { returns(T.nilable(String)) }
    def arch_overlay = @data["arch_overlay"]

    # @return Absolute path to the arch_overlay
    # @return No arch_overlay for this config
    sig { returns(T.nilable(Pathname)) }
    def arch_overlay_abs
      @info.overlay_path
    end

    sig { returns(Resolver::ConfigInfo) }
    attr_reader :info

    sig { returns(String) }
    def description = @data["description"]

    sig { returns(T.nilable(T.any(String, T::Array[String]))) }
    def compatible = @data["compatible"]

    sig { abstract.returns(T.nilable(Integer)) }
    def mxlen; end

    sig { abstract.returns(T::Boolean) }
    def fully_configured?; end

    sig { abstract.returns(T::Boolean) }
    def partially_configured?; end

    sig { abstract.returns(T::Boolean) }
    def unconfigured?; end

    ########################
    # NON-ABSTRACT METHODS #
    ########################

    # use AbstractConfig#create instead
    private_class_method :new

    sig { params(data: T::Hash[String, T.untyped], info: Resolver::ConfigInfo).void }
    def initialize(data, info)
      @data = data
      @info = info
      @name = @data.fetch("name")
      @name.freeze
      @type = ConfigType.deserialize(T.cast(@data.fetch("type"), String))
      @type.freeze
    end

    sig { returns(ConfigType) }
    attr_reader :type

    sig { returns(String) }
    def name = @name

    sig { returns(T::Boolean) }
    def configured? = !unconfigured?

    sig { params(obj: T.untyped).returns(T.untyped) }
    def self.freeze_data(obj)
      return obj if obj.frozen?

      if obj.is_a?(Hash)
        obj.each do |k, v|
          obj[k] = freeze_data(v)
        end
      elsif obj.is_a?(Array)
        obj.each { |v| freeze_data(v) }
      end

      obj.freeze
    end
    private_class_method :freeze_data

    # Factory method to create a FullConfig, PartialConfig, or UnConfig based
    # on the contents of cfg_file_path_or_portfolio_grp
    #
    # @return [AbstractConfig] A new AbstractConfig object
    sig { params(cfg_file_path_or_portfolio_grp: T.any(Pathname, PortfolioGroup), info: Resolver::ConfigInfo).returns(AbstractConfig) }
    def self.create(cfg_file_path_or_portfolio_grp, info)
      if cfg_file_path_or_portfolio_grp.is_a?(Pathname)
        cfg_file_path = T.cast(cfg_file_path_or_portfolio_grp, Pathname)
        raise ArgumentError, "Cannot find #{cfg_file_path}" unless cfg_file_path.exist?

        data = ::YAML.load_file(cfg_file_path)

        # now deep freeze the data
        freeze_data(data)

        case data["type"]
        when "fully configured"
          FullConfig.send(:new, data, info)
        when "partially configured"
          PartialConfig.send(:new, data, info)
        when "unconfigured"
          UnConfig.send(:new, data, info)
        else
          raise "Unexpected type (#{data['type']}) in config"
        end
      elsif cfg_file_path_or_portfolio_grp.is_a?(PortfolioGroup)
        portfolio_grp = T.cast(cfg_file_path_or_portfolio_grp, PortfolioGroup)
        data = {
          "$schema" => "config_schema.json#",
          "kind" => "architecture configuration",
          "type" => "partially configured",
          "name" => portfolio_grp.name,
          "description" => "Partial config construction from Portfolio Group #{portfolio_grp.name}",
          "params" => portfolio_grp.param_values,
          "mandatory_extensions" => portfolio_grp.mandatory_ext_reqs.map do |ext_req|
            {
              "name" => ext_req.name,
              "version" => ext_req.requirement_specs.map(&:to_s)
            }
          end
        }
        freeze_data(data)
        PartialConfig.send(:new, data, info)
      else
        T.absurd(cfg_file_path_or_portfolio_grp)
      end
    end

    # Create an AbstractConfig directly from a config data hash, bypassing file I/O.
    # Used when the config is already in memory (e.g., portfolio-derived temp configs).
    sig { params(data: T::Hash[String, T.untyped], info: Resolver::ConfigInfo).returns(AbstractConfig) }
    def self.create_from_data(data, info)
      freeze_data(data)
      case data["type"]
      when "fully configured"
        FullConfig.send(:new, data, info)
      when "partially configured"
        PartialConfig.send(:new, data, info)
      when "unconfigured"
        UnConfig.send(:new, data, info)
      else
        raise "Unexpected type (#{data['type']}) in config"
      end
    end
  end

  #################################################################
  # This class represents a configuration that is "unconfigured". #
  # It doesn't know anything about extensions or parameters.      #
  #################################################################
  class UnConfig < AbstractConfig
    ########################
    # NON-ABSTRACT METHODS #
    ########################

    sig { params(data: T::Hash[String, T.untyped], info: Resolver::ConfigInfo).void }
    def initialize(data, info)
      super(data, info)

      @param_values = {}.freeze
    end

    ###############################
    # ABSTRACT METHODS OVERRIDDEN #
    ###############################

    sig { override.returns(T::Hash[String, ParamValueType]) }
    def param_values = @param_values

    sig { override.returns(NilClass) }
    def mxlen = nil

    sig { override.returns(T::Boolean) }
    def fully_configured? = false

    sig { override.returns(T::Boolean) }
    def partially_configured? = false

    sig { override.returns(T::Boolean) }
    def unconfigured? = true
  end

  class InvalidConfigError < StandardError
  end

##############################################################################################################
# This class represents a configuration that is "partially-configured" (e.g., portfolio or configurable IP). #
# It only lists mandatory & prohibited extensions and fully-constrained parameters (single value).
##############################################################################################################
  class PartialConfig < AbstractConfig
    ########################
    # NON-ABSTRACT METHODS #
    ########################

    sig { params(data: T::Hash[String, T.untyped], info: Resolver::ConfigInfo).void }
    def initialize(data, info)
      super(data, info)

      @param_values = @data.key?("params") ? @data["params"] : {}.freeze

      @mxlen = @data.dig("params", "MXLEN")

      if @mxlen.nil?
        # Infer MXLEN from subordinate mode XLENs: if any of UXLEN/SXLEN/VSXLEN/VUXLEN
        # can be 64, then MXLEN must be 64 (lower modes cannot exceed machine-mode width).
        MODE_XLEN_PARAMS.each do |param|
          val = @data.dig("params", param)
          if val == 64 || (val.is_a?(Array) && val.include?(64))
            @mxlen = 64
            break
          end
        end

        if @mxlen.nil?
          param_req = @data.dig("requirements", "param")
          @mxlen = 64 if !param_req.nil? && param_req_implies_64?(param_req)
        end
      end

      @mxlen.freeze unless @mxlen.nil?
    end

    ###############################
    # ABSTRACT METHODS OVERRIDDEN #
    ###############################

    sig { override.returns(T::Hash[String, ParamValueType]) }
    def param_values = @param_values

    sig { override.returns(T.nilable(Integer)) }
    def mxlen = @mxlen

    sig { override.returns(T::Boolean) }
    def fully_configured? = false

    sig { override.returns(T::Boolean) }
    def partially_configured? = true

    sig { override.returns(T::Boolean) }
    def unconfigured? = false

    sig { returns(T::Array[T::Hash[String, T.any(String, T::Array[String])]]) }
    def mandatory_extensions
      @mandatory_extensions ||=
        if @data["mandatory_extensions"].nil?
          []
        else
          @data["mandatory_extensions"].map do |e|
            # convert the requirement to always be an array
            { "name" => e["name"], "version" => e["version"].is_a?(String) ? [e["version"]] : e["version"] }
          end
        end
    end

    sig { returns(T::Array[T::Hash[String, T.any(String, T::Array[String])]]) }
    def non_mandatory_extensions
      @non_mandatory_extensions ||=
        if @data["non_mandatory_extensions"].nil?
          []
        else
          @data["non_mandatory_extensions"].map do |e|
            # convert the requirement to always be an array
            { "name" => e["name"], "version" => e["version"].is_a?(String) ? [e["version"]] : e["version"] }
          end
        end
    end

    sig { returns(T::Array[T::Hash[String, T::Array[String]]]) }
    def prohibited_extensions
      @prohibited_extensions ||=
        if @data["prohibited_extensions"].nil?
          []
        else
          @data["prohibited_extensions"].map do |e|
            # convert the requirement to always be an array
            {
              "name" => e["name"],
              "version" =>
                if e.key?("version")
                  e["version"].is_a?(String) ? [e["version"]] : e["version"]
                else
                  ">=0"
                end
            }
          end
        end
    end

    # Whether or not a compliant instance of this partial config can have more extensions than those listed
    # in mandatory_extensions/non_mandatory_extensions.
    sig { returns(T::Boolean) }
    def additional_extensions_allowed? = @data.key?("additional_extensions") ? @data["additional_extensions"] : true

    sig { returns(T.nilable(T::Hash[String, T.untyped])) }
    def requirements = @data["requirements"]

    private

    MODE_XLEN_PARAMS = %w[UXLEN SXLEN VSXLEN VUXLEN].freeze

    # Returns true if the param requirements condition guarantees that at least one
    # subordinate-mode XLEN param must be 64, which implies MXLEN = 64.
    #
    # Entailment rules:
    #   allOf: any child entailing 64 is sufficient (all must hold)
    #   anyOf: all children must entail 64 (only one needs to hold, so we can't
    #          conclude 64 unless every branch requires it)
    #   noneOf/not/if/oneOf: too complex to reason about without a solver → false
    #   leaf with a MODE_XLEN_PARAMS name and equal/includes 64 → true
    #   anything else (extension, xlen, idl, other params) → false
    sig { params(yaml: T.untyped).returns(T::Boolean) }
    def param_req_implies_64?(yaml)
      return false unless yaml.is_a?(Hash)

      if yaml.key?("allOf")
        yaml["allOf"].any? { |child| param_req_implies_64?(child) }
      elsif yaml.key?("anyOf")
        yaml["anyOf"].all? { |child| param_req_implies_64?(child) }
      elsif yaml.key?("param")
        param_req_implies_64?(yaml["param"])
      elsif yaml.key?("name") && MODE_XLEN_PARAMS.include?(yaml["name"])
        yaml["equal"] == 64 || yaml["includes"] == 64
      else
        false
      end
    end
  end

  ################################################################################################################
  # This class represents a configuration that is "fully-configured" (e.g., SoC tapeout or fully-configured IP). #
  # It has a complete list of extensions and parameters (all are a single value at this point).                  #
  ################################################################################################################
  class FullConfig < AbstractConfig
    ########################
    # NON-ABSTRACT METHODS #
    ########################

    sig { params(data: T::Hash[String, T.untyped], info: Resolver::ConfigInfo).void }
    def initialize(data, info)
      super(data, info)

      @param_values = @data["params"]

      @mxlen = @data.dig("params", "MXLEN").freeze
      if @mxlen.nil?
        Udb.logger.error "Must set MXLEN for a full config"
        raise InvalidConfigError
      end
    end

    ###############################
    # ABSTRACT METHODS OVERRIDDEN #
    ###############################

    sig { override.returns(T::Hash[String, ParamValueType]) }
    def param_values = @param_values

    sig { override.returns(Integer) }
    def mxlen = @mxlen

    sig { override.returns(T::Boolean) }
    def fully_configured? = true

    sig { override.returns(T::Boolean) }
    def partially_configured? = false

    sig { override.returns(T::Boolean) }
    def unconfigured? = false

    sig { returns(T::Array[T::Hash[String, String]]) }
    def implemented_extensions
      @implemented_extensions ||=
        if @data["implemented_extensions"].nil?
          []
        else
          @data["implemented_extensions"].map do |e|
            if e.is_a?(Array)
              { "name" => e[0], "version" => implemented_extension_version(e[1]) }
            elsif e.is_a?(Hash)
              { "name" => e.fetch("name"), "version" => implemented_extension_version(e.fetch("version")) }
            end
          end
        end
    end

    private

    sig { params(version: String).returns(String) }
    def implemented_extension_version(version)
      version_str = version.strip
      if version_str.start_with?("=")
        RequirementSpec.new(version_str).version_spec.to_s
      else
        VersionSpec.new(version_str).to_s
      end
    end

  end
end
