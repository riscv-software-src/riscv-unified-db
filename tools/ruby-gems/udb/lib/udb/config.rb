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

    ParamValueType = T.type_alias { T.any(Integer, String, T::Boolean) }

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
        data.fetch("params")["MXLEN"] = portfolio_grp.max_base
        freeze_data(data)
        PartialConfig.send(:new, data, info)
      else
        T.absurd(cfg_file_path_or_portfolio_grp)
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

      @param_values = @data.key?("params") ? @data["params"] : [].freeze

      @mxlen = @data.dig("params", "MXLEN")
      if @mxlen.nil?
        raise "Must set MXLEN for a configured config"
      end

      @mxlen.freeze
    end

    ###############################
    # ABSTRACT METHODS OVERRIDDEN #
    ###############################

    sig { override.returns(T::Hash[String, ParamValueType]) }
    def param_values = @param_values

    sig { override.returns(Integer) }
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
    def prohibited_extensions
      @prohibited_extensions ||=
        if @data["prohibited_extensions"].nil?
          []
        else
          @data["prohibited_extensions"].map do |e|
            # convert the requirement to always be an array
            { "name" => e["name"], "version" => e["version"].is_a?(String) ? [e["version"]] : e["version"] }
          end
        end
    end

    # Whether or not a compliant instance of this partial config can have more extensions than those listed
    # in mandatory_extensions/non_mandatory_extensions.
    sig { returns(T::Boolean) }
    def additional_extensions_allowed? = @data.key?("additional_extensions") ? @data["additional_extensions"] : true
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
      raise "Must set MXLEN for a configured config" if @mxlen.nil?
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
              { "name" => e[0], "version" => e[1] }
            else
              e
            end
          end
        end
    end
  end
end
