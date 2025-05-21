# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "pathname"
require "forwardable"
require_relative "obj/portfolio"

# This class represents a configuration. Is is coded as an abstract base class (must be inherited by a child).
#
# There are child classes derived from AbstractConfig to handle:
#   - Configurations specified by YAML files in the /cfg directory
#   - Configurations specified by portfolio groups (certificates and profile releases)
class Udb::AbstractConfig
  ####################
  # ABSTRACT METHODS #
  ####################

  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has
  #                                been configured with a value. May be empty.
  def param_values = raise "Abstract Method: Must be provided in child class"

  # @return [Boolean] Is an overlay present?
  def overlay? = raise "Abstract Method: Must be provided in child class"

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  def arch_overlay = raise "Abstract Method: Must be provided in child class"

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
  def arch_overlay_abs = raise "Abstract Method: Must be provided in child class"

  def mxlen = raise "Abstract Method: Must be provided in child class"

  def fully_configured? = raise "Abstract Method: Must be provided in child class"
  def partially_configured? = raise "Abstract Method: Must be provided in child class"
  def unconfigured? = raise "Abstract Method: Must be provided in child class"

  # @return [Array<Hash<String, String>>] List of all extensions known to be implemented by the configuration.
  def implemented_extensions = raise "Abstract Method: Must be provided in child class"

  # @return [Array<Hash{String => String,Array<String}>]
  #    List of all extensions that must be implemented by the configuration
  #    The first entry in the nested array is an Extension name.
  #    The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   mandatory_extensions =>
  #     [{ "name" => "A", "version" => ["~> 2.0"] }, { "name" => "B", "version" => ["~> 1.0"] }, ...]
  def mandatory_extensions = raise "Abstract Method: Must be provided in child class"

  # @return [Array<Hash{String => String,Array<String}>]
  #   List of all extensions that are explicitly prohibited by the configuration.
  #   The first entry in the nested array is an Extension name.
  #   The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   partial_config.prohibited_extensions =>
  #     [{ "name" => "F", "version" => [">= 2.0"] }, { "name" => "Zfa", "version" => ["> = 1.0"] }, ...]
  def prohibited_extensions = raise "Abstract Method: Must be provided in child class"

  # Whether or not a compliant instance of this partial config can have more extensions than those listed
  # in mandatory_extensions/non_mandatory_extensions.
  def additional_extensions_allowed? = raise "Abstract Method: Must be provided in child class"

  ########################
  # NON-ABSTRACT METHODS #
  ########################

  def initialize(name)
    @name = name
  end

  def name = @name
  def configured? = !unconfigured
end

# This class represents a configuration as specified by YAML files in the /cfg directory.
# Is is coded as an abstract base class (must be inherited by a child).
class Udb::FileConfig < Udb::AbstractConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  # use FileConfig#create instead
  private_class_method :new

  def initialize(cfg_file_path, data)
    super(data["name"])
    @cfg_file_path = cfg_file_path
    @data = data
  end

  def type = @data["type"]

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
  def self.create(cfg_filename)
    cfg_file_path = Pathname.new(cfg_filename)
    raise ArgumentError, "Cannot find #{cfg_filename}" unless cfg_file_path.exist?

    data = YAML.load(cfg_file_path.read, permitted_classes: [Date])

    # now deep freeze the data
    freeze_data(data)

    case data["type"]
    when "fully configured"
      Udb::FullConfig.send(:new, cfg_file_path, data)
    when "partially configured"
      Udb::PartialConfig.send(:new, cfg_file_path, data)
    when "unconfigured"
      Udb::UnConfig.send(:new, cfg_file_path, data)
    else
      raise "Unexpected type in config"
    end
  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  def overlay? = !(@data["arch_overlay"].nil? || @data["arch_overlay"].empty?)

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  def arch_overlay = @data["arch_overlay"]

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
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
class Udb::UnConfig < Udb::FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = {}.freeze
  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  def param_values = @param_values
  def mxlen = nil

  def fully_configured? = false
  def partially_configured? = false
  def unconfigured? = true

  def implemented_extensions = raise "implemented_extensions is only available for a FullConfig"
  def mandatory_extensions = raise "mandatory_extensions is only available for a PartialConfig"
  def prohibited_extensions = raise "prohibited_extensions is only available for a PartialConfig"
  def additional_extensions_allowed? = raise "additional_extensions_allowed? is only available for a PartialConfig"
end

##############################################################################################################
# This class represents a configuration that is "partially-configured" (e.g., portfolio or configurable IP). #
# It only lists mandatory & prohibited extensions and fully-constrained parameters (single value).
##############################################################################################################
class Udb::PartialConfig < Udb::FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

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

  def param_values = @param_values
  def mxlen = @mxlen

  def fully_configured? = false
  def partially_configured? = true
  def unconfigured? = false

  def implemented_extensions = raise "implemented_extensions is only available for a FullConfig"

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
  def additional_extensions_allowed? = @data.key?("additional_extensions") ? @data["additional_extensions"] : true
end

################################################################################################################
# This class represents a configuration that is "fully-configured" (e.g., SoC tapeout or fully-configured IP). #
# It has a complete list of extensions and parameters (all are a single value at this point).                  #
################################################################################################################
class Udb::FullConfig < Udb::FileConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = @data["params"]

    @mxlen = @data.dig("params", "MXLEN").freeze
    raise "Must set MXLEN for a configured config" if @mxlen.nil?
  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  def param_values = @param_values
  def mxlen = @mxlen

  def fully_configured? = true
  def partially_configured? = false
  def unconfigured? = false

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

  def mandatory_extensions = raise "mandatory_extensions is only available for a PartialConfig"
  def prohibited_extensions = raise "prohibited_extensions is only available for a PartialConfig"
  def additional_extensions_allowed? = raise "additional_extensions_allowed? is only available for a PartialConfig"
end

########################
# PortfolioGroupConfig #
########################

# A PortfolioGroupConfig provides an implementation of the AbstractConfig API using a PortfolioGroup object.
# This object contains information from one or more portfolios.
# A certificate has just one portfolio and a profile release has one or more portfolios.
class Udb::PortfolioGroupConfig < Udb::AbstractConfig
  ########################
  # NON-ABSTRACT METHODS #
  ########################

  def initialize(portfolio_grp)
    raise ArgumentError, "portfolio_grp is a class #{portfolio_grp.class} but must be a PortfolioGroup" unless portfolio_grp.is_a?(PortfolioGroup)

    super(portfolio_grp.name)

    @portfolio_grp = portfolio_grp

    portfolio_grp.portfolios.each do |portfolio|
      raise "Portfolio #{portfolio.name} shouldn't have a non-nil cfg_arch member" if portfolio.cfg_arch?
      raise "Portfolio #{portfolio.name} shouldn't have a an arch member of type ConfiguredArchitecture" if portfolio.arch.is_a?(ConfiguredArchitecture)
    end
  end

  ###############################
  # ABSTRACT METHODS OVERRIDDEN #
  ###############################

  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has
  #                                been configured with a value. May be empty.
  def param_values = @portfolio_grp.param_values

  # @return [Boolean] Is an overlay present?
  def overlay? = false

  # @return [String] Either a path to an overlay directory, or the name of a folder under arch_overlay/
  # @return [nil] No arch_overlay for this config
  def arch_overlay = nil

  # @return [String] Absolute path to the arch_overlay
  # @return [nil] No arch_overlay for this config
  def arch_overlay_abs = nil

  # 32, 64, or nil if dynamic (not yet supported in portfolio)
  def mxlen = @portfolio_grp.max_base

  # Portfolios are always considered partially configured.
  def fully_configured? = false
  def partially_configured? = true
  def unconfigured? = false

  # @return [Array<Hash<String, String>>] List of all extensions known to be implemented by the configuration.
  def implemented_extensions = raise "Attempt to invoke implemented_extensions in PorfolioGroup #{name}"

  # @return [Array<Hash{String => String,Array<String}>]
  #    List of all extensions that must be implemented by the configuration
  #    The first entry in the nested array is an Extension name.
  #    The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   mandatory_extensions =>
  #     [{ "name" => "A", "version" => ["~> 2.0"] }, { "name" => "B", "version" => ["~> 1.0"] }, ...]
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
  def prohibited_extensions = []    # No prohibited_extensions in a portfolio group

  # Whether or not a compliant instance of this partial config can have more extensions than those listed
  # in mandatory_extensions/non_mandatory_extensions.
  def additional_extensions_allowed? = true
end
