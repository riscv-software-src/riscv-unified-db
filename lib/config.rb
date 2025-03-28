# frozen_string_literal: true

require "pathname"

# This class represents a configuration file (e.g., cfgs/*/cfg.yaml), independent of the Architecture.
# Can either be in the /cfg directory or created at runtime in memory by the certificate tasks.rake file.
class Config
  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has
  #                                been configured with a value. May be empty.
  attr_reader :param_values

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

  # use Config#create instead
  private_class_method :new

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

  # factory method to create a FullConfig, PartialConfig, or Unconfig based on the contents of cfg_filename
  #
  # @return [Config] A new Config
  def self.create(cfg_filename)
    cfg_file_path = Pathname.new(cfg_filename)
    raise ArgumentError, "Cannot find #{cfg_filename}" unless cfg_file_path.exist?

    data = YAML.load(cfg_file_path.read, permitted_classes: [Date])

    # now deep freeze the data
    freeze_data(data)

    case data["type"]
    when "fully configured"
      FullConfig.send(:new, cfg_file_path, data)
    when "partially configured"
      PartialConfig.send(:new, cfg_file_path, data)
    when "unconfigured"
      Unconfig.send(:new, cfg_file_path, data)
    else
      raise "Unexpected type in config"
    end
  end

  def initialize(cfg_file_path, data)
    @cfg_file_path = cfg_file_path
    @data = data
  end

  def name = @data["name"]

  def fully_configured? = @data["type"] == "fully configured"
  def partially_configured? = @data["type"] == "partially configured"
  def unconfigured? = @data["type"] == "unconfigured"
  def configured? = @data["type"] != "unconfigured"
  def type = @data["type"]
end

#################################################################
# This class represents a configuration that is "unconfigured". #
# It doesn't know anything about extensions or parameters.      #
#################################################################
class Unconfig < Config
  attr_reader :param_values

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = {}.freeze
  end

  def mxlen = nil

  def implemented_extensions = raise "implemented_extensions is only available for a FullConfig"
  def mandatory_extensions = raise "mandatory_extensions is only available for a PartialConfig"
  def prohibited_extensions = raise "prohibited_extensions is only available for a PartialConfig"
end

##############################################################################################################
# This class represents a configuration that is "partially-configured" (e.g., portfolio or configurable IP). #
# It only lists mandatory & prohibited extensions and fully-constrained parameters (single value).
##############################################################################################################
class PartialConfig < Config
  attr_reader :param_values, :mxlen

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = @data.key?("params") ? @data["params"] : [].freeze

    @mxlen = @data.dig("params", "MXLEN")
    raise "Must set MXLEN for a configured config" if @mxlen.nil?

    @mxlen.freeze
  end

  def additional_extensions_allowed? = @data.key?("additional_extensions") ? @data["additional_extensions"] : true

  def implemented_extensions = raise "implemented_extensions is only availabe for a FullConfig"

  # @return [Array<Hash{String => String,Array<String}>]
  #    List of all extensions that must be implemented, as specified in the config file
  #    The first entry in the nested array is an Extension name.
  #    The second entry in the nested array is an Extension version requirement
  #
  # @example
  #   partial_config.mandatory_extensions =>
  #     [{ "name" => "A", "version" => ["~> 2.0"] }, { "name" => "B", "version" => ["~> 1.0"] }, ...]
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

  # @return [Array<Hash{String => String,Array<String}>]
  #   List of all extensions that are explicitly prohibited.
  #   The first entry in the nested array is an Extension name.
  #   The second entry in the nested array is an Extension version requirement.
  #
  # @example
  #   partial_config.prohibited_extensions =>
  #     [{ "name" => "F", "version" => [">= 2.0"] }, { "name" => "Zfa", "version" => ["> = 1.0"] }, ...]
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

  # def prohibited_ext?(ext_name, cfg_arch) = prohibited_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }

  # def ext?(ext_name, cfg_arch) = mandatory_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }
end

################################################################################################################
# This class represents a configuration that is "fully-configured" (e.g., SoC tapeout or fully-configured IP). #
# It has a complete list of extensions and parameters (all are a single value at this point).                  #
################################################################################################################
class FullConfig < Config
  attr_reader :param_values, :mxlen

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = @data["params"]

    @mxlen = @data.dig("params", "MXLEN").freeze
    raise "Must set MXLEN for a configured config" if @mxlen.nil?
  end

  # @return [Array<Hash<String, String>>] List of all extensions known to be implemented in this architecture
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

  # def prohibited_ext?(ext_name, cfg_arch) = !ext?(ext_name, cfg_arch)
  # def ext?(ext_name, cfg_arch) = implemented_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }
end
