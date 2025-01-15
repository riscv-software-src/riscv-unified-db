# frozen_string_literal: true

require_relative "database_obj"
require_relative "schema"
require_relative "../version"

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class Parameter
  # @return [Architecture] The defining architecture
  attr_reader :arch

  # @return [String] Parameter name
  attr_reader :name

  # @return [String] Asciidoc description
  attr_reader :desc

  # @return [Schema] JSON Schema for this param
  attr_reader :schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validation
  attr_reader :extra_validation

  # Some parameters are defined by multiple extensions (e.g., CACHE_BLOCK_SIZE by Zicbom and Zicboz).
  # When defined in multiple places, the parameter *must* mean the exact same thing.
  #
  # @return [Array<Extension>] The extension(s) that define this parameter
  attr_reader :exts

  # @returns [Idl::Type] Type of the parameter
  attr_reader :idl_type

  # Pretty convert extension schema to a string.
  def schema_type
    @schema.to_pretty_s
  end

  # @param ext [Extension]
  # @param name [String]
  # @param data [Hash<String, Object]
  def initialize(ext, name, data)
    @arch = ext.arch
    @data = data
    @name = name
    @desc = data["description"]
    @schema = Schema.new(data["schema"])
    @extra_validation = data["extra_validation"]
    also_defined_in = []
    unless data["also_defined_in"].nil?
      if data["also_defined_in"].is_a?(String)
        other_ext = @arch.extension(data["also_defined_in"])
        raise "Definition error in #{ext.name}.#{name}: #{data['also_defined_in']} is not a known extension" if other_ext.nil?

        also_defined_in << other_ext
      else
        unless data["also_defined_in"].is_a?(Array) && data["also_defined_in"].all? { |e| e.is_a?(String) }
          raise "schema error: also_defined_in should be a string or array of strings"
        end

        data["also_defined_in"].each do |other_ext_name|
          other_ext = @arch.extension(other_ext_name)
          raise "Definition error in #{ext.name}.#{name}: #{data['also_defined_in']} is not a known extension" if other_ext.nil?

          also_defined_in << other_ext
        end
      end
    end
    @exts = [ext] + also_defined_in
    @idl_type = @schema.to_idl_type.make_const.freeze
  end

  # @param version [ExtensionVersion]
  # @return [Boolean] if this parameter is defined in +version+
  def defined_in_extension_version?(version)
    return false if @exts.none? { |ext| ext.name == version.ext.name }
    return true if @data.dig("when", "version").nil?

    @exts.any? do |ext|
      ExtensionRequirement.new(ext.name, @data["when"]["version"], ext.arch).satisfied_by?(version)
    end
  end

  # @param ext [Extension] Extension that defines this parameter.
  # @return [String] Text that includes the parameter name and a link to the parameter definition.
  #                  Should only be called if there is only one in-scope extension that defines the parameter.
  def name_with_link(ext)
    link_to_ext_param(ext.name, name)
  end

  # @param exts [Array<Extension>] List of all in-scope extensions that define this parameter.
  # @return [String] Text that includes the parameter name and a link to the parameter definition
  #                  if only one extension defines the parameter, otherwise just the parameter name.
  def name_potentially_with_link(in_scope_exts)
    raise ArgumentError, "Expecting Array" unless in_scope_exts.is_a?(Array)
    raise ArgumentError, "Expecting Array[Extension]" unless in_scope_exts[0].is_a?(Extension)

    if in_scope_exts.size == 1
      link_to_ext_param(in_scope_exts[0].name, name)
    else
      name
    end
  end

  # sorts by name
  def <=>(other)
    raise ArgumentError, "Parameters are only comparable to other extension parameters" unless other.is_a?(Parameter)

    @name <=> other.name
  end
end

class ParameterWithValue
  # @return [Object] The parameter value
  attr_reader :value

  # @return [String] Parameter name
  def name = @param.name

  # @return [String] Asciidoc description
  def desc = @param.desc

  # @return [Hash] JSON Schema for the parameter value
  def schema = @param.schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validatino
  def extra_validation = @param.extra_validation

  # @return [Extension] The extension that defines this parameter
  def exts = @param.exts

  def initialize(param, value)
    @param = param
    @value = value
  end
end
