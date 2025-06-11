# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

require "pathname"
require "forwardable"
require "yaml"
require_relative "obj/portfolio"

module Udb

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
  sig { abstract.returns(T::Boolean) }
  def overlay?; end

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  sig { abstract.returns(T.nilable(String)) }
  def arch_overlay; end

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
  sig { abstract.returns(T.nilable(String)) }
  def arch_overlay_abs; end

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

  sig { params(name: String).void }
  def initialize(name)
    @name = name
  end

  sig { returns(String) }
  def name = @name

  sig { returns(T::Boolean) }
  def configured? = !unconfigured?
end

# This class represents a configuration as specified by YAML files in the /cfg directory.
# Is is coded as an abstract base class (must be inherited by a child).
class FileConfig < AbstractConfig
  abstract!
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  # use FileConfig#create instead
  private_class_method :new

  sig { params(cfg_file_path: Pathname, data: T::Hash[String, T.untyped]).void }
  def initialize(cfg_file_path, data)
    super(data["name"])
    @cfg_file_path = cfg_file_path
    @data = data
  end

  sig { returns(String) }
  def type = @data["type"]

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
  # on the contents of cfg_filename.
  #
  # @return [FileConfig] A new FileConfig object
  sig { params(cfg_file_path: Pathname).returns(FileConfig) }
  def self.create(cfg_file_path)
    raise ArgumentError, "Cannot find #{cfg_file_path}" unless cfg_file_path.exist?

    data = ::YAML.load_file(cfg_file_path)

    # now deep freeze the data
    freeze_data(data)

    case data["type"]
    when "fully configured"
      FullConfig.send(:new, cfg_file_path, data)
    when "partially configured"
      PartialConfig.send(:new, cfg_file_path, data)
    when "unconfigured"
      UnConfig.send(:new, cfg_file_path, data)
    else
      raise "Unexpected type (#{data['type']}) in config"
    end
  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  sig { override.returns(T::Boolean) }
  def overlay? = !(@data["arch_overlay"].nil? || @data["arch_overlay"].empty?)

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  sig { override.returns(T.nilable(String)) }
  def arch_overlay = @data["arch_overlay"]

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
  sig { override.returns(T.nilable(String)) }
  def arch_overlay_abs
    return nil unless @data.key?("arch_overlay")

    if File.directory?("#{$root}/arch_overlay/#{@data['arch_overlay']}")
      "#{$root}/arch_overlay/#{@data['arch_overlay']}"
    elsif File.directory?(@data['arch_overlay'])
      @data['arch_overlay']
    else
      raise "Cannot find arch_overlay '#{@data['arch_overlay']}'"
    end
  end
end

#################################################################
# This class represents a configuration that is "unconfigured". #
# It doesn't know anything about extensions or parameters.      #
#################################################################
class UnConfig < FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  sig { params(cfg_file_path: Pathname, data: T::Hash[String, T.untyped]).void }
  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

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
class PartialConfig < FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  sig { params(cfg_file_path: Pathname, data: T::Hash[String, T.untyped]).void }
  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

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
          { "name" => e["name"], "version" => e["version"].is_a?(String) ? [e["version"]] : e["version"]}
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
          { "name" => e["name"], "version" => e["version"].is_a?(String) ? [e["version"]] : e["version"]}
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
class FullConfig < FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  sig { params(cfg_file_path: Pathname, data: T::Hash[String, T.untyped]).void }
  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

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

########################
# PortfolioGroupConfig #
########################

# A PortfolioGroupConfig provides an implementation of the AbstractConfig API using a PortfolioGroup object.
# This object contains information from one or more portfolios.
# A certificate has just one portfolio and a profile release has one or more portfolios.
class PortfolioGroupConfig < AbstractConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  sig { params(portfolio_grp: ::Udb::PortfolioGroup).void }
  def initialize(portfolio_grp)
    super(portfolio_grp.name)

    @portfolio_grp = portfolio_grp

  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has
  #                                been configured with a value. May be empty.
  sig { override.returns(T::Hash[String, ParamValueType]) }
  def param_values = @portfolio_grp.param_values

  # @return [Boolean] Is an overlay present?
  sig { override.returns(FalseClass) }
  def overlay? = false

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  sig { override.returns(T.nilable(String)) }
  def arch_overlay = nil

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
  sig { override.returns(T.nilable(String)) }
  def arch_overlay_abs = nil

  # 32, 64, or nil if dynamic (not yet supported in portfolio)
  sig { override.returns(T.nilable(Integer)) }
  def mxlen = @portfolio_grp.max_base

  # Portfolios are always considered partially configured.
  sig { override.returns(T::Boolean) }
  def fully_configured? = false

  sig { override.returns(T::Boolean) }
  def partially_configured? = true

  sig { override.returns(T::Boolean) }
  def unconfigured? = false

  # @return [Array<Hash{String => String,Array<String}>]
  #    List of all extensions that must be implemented by the configuration
  #    The first entry in the nested array is an Extension name.
  #    The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   mandatory_extensions =>
  #     [{ "name" => "A", "version" => ["~> 2.0"] }, { "name" => "B", "version" => ["~> 1.0"] }, ...]
  sig { returns(T::Array[T::Hash[String, T.any(String, T::Array[String])]]) }
  def mandatory_extensions
    @portfolio_grp.mandatory_ext_reqs.map do |ext_req|
      {
        "name" => ext_req.name,
        "version" => ext_req.requirement_specs.map(&:to_s)
      }
    end
  end

  # @return [Array<Hash{String => String,Array<String}>]
  #   List of all extensions that are explicitly prohibited by the configuration.
  #   The first entry in the nested array is an Extension name.
  #   The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   partial_config.prohibited_extensions =>
  #     [{ "name" => "F", "version" => [">= 2.0"] }, { "name" => "Zfa", "version" => ["> = 1.0"] }, ...]
  sig { returns(T::Array[T::Hash[String, T.any(String, T::Array[String])]]) }
  def prohibited_extensions = []    # No prohibited_extensions in a portfolio group

  # Whether or not a compliant instance of this partial config can have more extensions than those listed
  # in mandatory_extensions/non_mandatory_extensions.
  sig { returns(TrueClass) }
  def additional_extensions_allowed? = true
end
end
