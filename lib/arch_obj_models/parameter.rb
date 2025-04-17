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
    raise ArgumentError, "Expecting Extension but got #{ext.class}" unless ext.is_a?(Extension)
    raise ArgumentError, "Expecting String but got #{name.class}" unless name.is_a?(String)
    raise ArgumentError, "Expecting Hash but got #{data.class}" unless data.is_a?(Hash)

    @arch = ext.arch
    @data = data
    @name = name
    @desc = data["description"]
    @schema = Schema.new(data["schema"])
    @extra_validation = data["extra_validation"]
    also_defined_in_array = []
    also_defined_in_data = data["also_defined_in"]
    unless also_defined_in_data.nil?
      if also_defined_in_data.is_a?(String)
        other_ext_name = also_defined_in_data
        other_ext = @arch.extension(other_ext_name)
        raise "Definition error in #{ext.name}.#{name}: #{other_ext_name} is not a known extension" if other_ext.nil?

        also_defined_in_array << other_ext
      else
        unless also_defined_in_data.is_a?(Array) && also_defined_in_data.all? { |e| e.is_a?(String) }
          raise "schema error: also_defined_in should be a string or array of strings"
        end

        also_defined_in_data.each do |other_ext_name|
          other_ext = @arch.extension(other_ext_name)
          raise "Definition error in #{ext.name}.#{name}: #{also_defined_in_data} is not a known extension" if other_ext.nil?

          also_defined_in_array << other_ext
        end
      end
    end
    @exts = [ext] + also_defined_in_array
    @idl_type = @schema.to_idl_type.make_const.freeze
  end

  # @param version [ExtensionVersion]
  # @return [Boolean] if this parameter is defined in +version+
  def defined_in_extension_version?(version)
    return false if @exts.none? { |ext| ext.name == version.ext.name }
    return true if @data.dig("when", "version").nil?

    @exts.any? do |ext|
      ExtensionRequirement.new(ext.name, @data["when"]["version"], arch: ext.arch).satisfied_by?(version)
    end
  end

  # @param exts [Array<Extension>] List of all in-scope extensions that define this parameter.
  # @return [String] Text to create a link to the parameter definition with the link text the parameter name.
  #                  if only one extension defines the parameter, otherwise just the parameter name.
  def name_potentially_with_link(in_scope_exts)
    raise ArgumentError, "Expecting Array but got #{in_scope_exts.class}" unless in_scope_exts.is_a?(Array)
    raise ArgumentError, "Expecting Array[Extension]" unless in_scope_exts[0].is_a?(Extension)

    if in_scope_exts.size == 1
      link_to_udb_doc_ext_param(in_scope_exts[0].name, name, name)
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
