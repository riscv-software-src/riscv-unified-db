# frozen_string_literal: true

require "pathname"

class Config
  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has been configured with a value. May be empty.
  attr_reader :param_values

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

class Unconfig < Config
  attr_reader :param_values

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = {}.freeze
  end

  def mxlen = nil

  def implemented_extensions = raise "implemented_extensions is only availabe for a FullConfig"
  def mandatory_extensions = raise "mandatory_extensions is only availabe for a PartialConfig"
end

class PartialConfig < Config
  attr_reader :param_values, :mxlen

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = @data.key?("params") ? @data["params"] : [].freeze

    @mxlen = @data.dig("params", "XLEN")
    raise "Must set XLEN for a configured config" if @mxlen.nil?

    @mxlen.freeze
  end

  def implemented_extensions = raise "implemented_extensions is only availabe for a FullConfig"

  # @return [Array<ExtensionRequirement>] List of all extensions that must be implemented, as specified in the config file
  #                                       Implied/required extensions are *not* transitively included (though they are from ConfiguredArchitecture#mandatory_extensions)
  def mandatory_extensions(cfg_arch)
    @mandatory_extensions ||=
      if @data.key?("mandatory_extensions")
        @data["mandatory_extensions"].map do |e|
          ext = cfg_arch.extension(e["name"])
          raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

          req_spec = e["version"].is_a?(Array) ? e["version"] : [e["version"]]
          ExtensionRequirement.new(e["name"], *req_spec, presence: "mandatory", cfg_arch:)
        end
      else
        []
      end
  end

  # @return [Array<ExtensionRequirement>] List of all extensions that are prohibited.
  #                                       This only includes extensions explicitly prohibited by the config file.
  def prohibited_extensions(cfg_arch)
    return @prohibited_extensions unless @prohibited_extensions.nil?

    @prohibited_extensions = []
    if @data.key?("prohibited_extensions")
      @data["prohibited_extensions"].each do |e|
        @prohibited_extensions <<
          if e.is_a?(String)
            ExtensionRequirement.new(e, nil, cfg_arch:)
          else
            ExtensionRequirement.new(e["name"], e["version"], presence: "prohibited", cfg_arch:)
          end
      end
    end
    @prohibited_extensions
  end

  def prohibited_ext?(ext_name, cfg_arch) = prohibited_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }

  def ext?(ext_name, cfg_arch) = mandatory_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }
end


class FullConfig < Config
  attr_reader :param_values, :mxlen

  def initialize(cfg_file_path, data)
    super(cfg_file_path, data)

    @param_values = @data["params"]

    @mxlen = @data.dig("params", "XLEN").freeze
    raise "Must set XLEN for a configured config" if @mxlen.nil?
  end

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this architecture
  def implemented_extensions(cfg_arch)
    return @implemented_extensions unless @implemented_extensions.nil?

    @implemented_extensions = []
    if @data.key?("implemented_extensions")
      @data["implemented_extensions"].each do |e|
        if e.is_a?(Array)
          @implemented_extensions << ExtensionVersion.new(e[0], e[1], cfg_arch)
        else
          @implemented_extensions << ExtensionVersion.new(e["name"], e["version"], cfg_arch)
        end
      end
    end
    @implemented_extensions
  end

  def mandatory_extensions = raise "mandatory_extensions is only availabe for a PartialConfig"

  # def prohibited_ext?(ext_name, cfg_arch) = !ext?(ext_name, cfg_arch)
  # def ext?(ext_name, cfg_arch) = implemented_extensions(cfg_arch).any? { |e| e.name == ext_name.to_s }
end
