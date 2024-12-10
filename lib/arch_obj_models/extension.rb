# frozen_string_literal: true

require_relative "obj"
require_relative "schema"

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class ExtensionParameter
  # @return [ArchDef] The defining Arch def
  attr_reader :archdef

  # @return [String] Parameter name
  attr_reader :name

  # @return [String] Asciidoc description
  attr_reader :desc

  # @return [Schema] JSON Schema for this param
  attr_reader :schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validatino
  attr_reader :extra_validation

  # @return [Array<Extension>] The extension(s) that define this parameter
  #
  # Some parameters are defined by multiple extensions (e.g., CACHE_BLOCK_SIZE by Zicbom and Zicboz).
  # When defined in multiple places, the parameter *must* mean the extact same thing.
  attr_reader :exts

  # @returns [Idl::Type] Type of the parameter
  attr_reader :idl_type

  # Pretty convert extension schema to a string.
  def schema_type
    @schema.to_pretty_s
  end

  def initialize(ext, name, data)
    @archdef = ext.arch_def
    @data = data
    @name = name
    @desc = data["description"]
    @schema = Schema.new(data["schema"])
    @extra_validation = data["extra_validation"]
    also_defined_in = []
    unless data["also_defined_in"].nil?
      if data["also_defined_in"].is_a?(String)
        other_ext = @archdef.extension(data["also_defined_in"])
        raise "Definition error in #{ext.name}.#{name}: #{data['also_defined_in']} is not a known extension" if other_ext.nil?
        also_defined_in << other_ext
      else
        unless data["also_defined_in"].is_a?(Array) && data["also_defined_in"].all? { |e| e.is_a?(String) }
          raise "schema error: also_defined_in should be a string or array of strings"
        end

        data["also_defined_in"].each do |other_ext_name|
          other_ext = @archdef.extension(other_ext_name)
          raise "Definition error in #{ext.name}.#{name}: #{data['also_defined_in']} is not a known extension" if other_ext.nil?
          also_defined_in << other_ext
        end
      end
    end
    @exts = [ext] + also_defined_in
    @idl_type = @schema.to_idl_type.make_const.freeze
  end

  def defined_in_extension_version?(version)
    return true if @data.dig("when", "version").nil?

    Gem::Requirement.new(@data["when"]["version"]).satisfied_by?(Gem::Version.new(version))
  end

  # @return [String]
  def name_potentially_with_link(exts)
    raise ArgumentError, "Expecting Array" unless exts.is_a?(Array)
    raise ArgumentError, "Expecting Array[Extension]" unless exts[0].is_a?(Extension)

    if exts.size == 1
      "<<ext-#{exts[0].name}-param-#{name}-def,#{name}>>"
    else
      "#{name}"
    end
  end

  # sorts by name
  def <=>(other)
    raise ArgumentError, "ExtensionParameters are only comparable to other extension parameters" unless other.is_a?(ExtensionParameter)

    @name <=> other.name
  end
end

class ExtensionParameterWithValue
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

# Extension definition
class Extension < ArchDefObject
  # @return [ArchDef] The architecture defintion
  attr_reader :arch_def

  # @return [String] Long name of the extension
  def long_name = @data["long_name"]

  # @return [String] Company that developed the extension
  # @return [nil] if the company isn't known
  def company
    @data["company"]
  end

  # @return [{ name: String, url: String}] The name and URL of a document license the doc falls under
  # @return [nil] if the license isn't known
  def doc_license
    @data["doc_license"]
  end

  # @return [Array<Hash>] versions hash from config
  def versions
    return @versions unless @versions.nil?

    @versions = @data["versions"].map do |v|
      ExtensionVersion.new(name, v["version"], arch_def)
    end
  end

  # @return [Array<ExtensionVersion>] Ratified versions hash from config
  def ratified_versions
    versions.select { |v| v.state == "ratified" }
  end

  # @return [ExtensionVersion] Mimumum defined version of this extension
  def min_version
    versions.min { |a, b| a.version <=> b.version }
  end

  # @return [ExtensionVersion] Maximum defined version of this extension
  def max_version
    versions.max { |a, b| a.version <=> b.version }
  end

  # @return [ExtensionVersion] Mimumum defined ratified version of this extension
  # @return [nil] if there is no ratified version
  def min_ratified_version
    return nil if ratified_versions.empty?

    ratified_versions.min { |a, b| a.version <=> b.version }
  end

  # @return [Array<ExtensionParameter>] List of parameters added by this extension
  def params
    return @params unless @params.nil?

    @params = []
    if @data.key?("params")
      @data["params"].each do |param_name, param_data|
        @params << ExtensionParameter.new(self, param_name, param_data)
      end
    end
    @params
  end

  # @param ext_data [Hash<String, Object>] The extension data from the architecture spec
  # @param arch_def [ArchDef] The architecture definition
  def initialize(ext_data, arch_def)
    super(ext_data)
    @arch_def = arch_def
  end

  # @param version_requirement [String] Version requirement
  # @return [Array<ExtensionVersion>] Array of extensions implied by any version of this extension meeting version_requirement
  def implies(version_requirement = ">= 0")
    return [] unless Gem::Requirement.new(version_requirement).satisfied_by?(max_version.version)

    max_version.implications
  end

  def conflicts
    return [] if @data["conflicts"].nil?

    to_extension_requirement_list(@data["conflicts"])
  end

  # @return [Array<Instruction>] the list of instructions implemented by *any version* of this extension (may be empty)
  def instructions
    return @instructions unless @instructions.nil?

    @instructions = arch_def.instructions.select { |i| versions.any? { |v| i.defined_by?(v) }}
  end

  # @return [Array<Csr>] the list of CSRs implemented by *any version* of this extension (may be empty)
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = arch_def.csrs.select { |csr| versions.any? { |v| csr.defined_by?(v) } }
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension (may be empty)
  def implemented_csrs(archdef)
    raise "should only be called with a fully configured arch def" unless archdef.fully_configured?

    return @implemented_csrs unless @implemented_csrs.nil?

    @implemented_csrs = archdef.implemented_csrs.select do |csr|
      versions.any? { |ver| csr.defined_by?(ExtensionVersion.new(name, ver["version"], @arch_def)) }
    end
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension (may be empty)
  def implemented_instructions(archdef)
    raise "should only be called with a fully configured arch def" unless archdef.fully_configured?

    return @implemented_instructions unless @implemented_instructions.nil?

    @implemented_instructions = archdef.implemented_instructions.select do |inst|
      versions.any? { |ver| inst.defined_by?(ExtensionVersion.new(name, ver["version"], @arch_def)) }
    end
  end

  # return the set of reachable functions from any of this extensions's CSRs or instructions in the given evaluation context
  #
  # @param symtab [Idl::SymbolTable] The evaluation context
  # @return [Array<Idl::FunctionDefAst>] Array of IDL functions reachable from any instruction or CSR in the extension
  def reachable_functions(symtab)
    @reachable_functions ||= {}

    return @reachable_functions[symtab] unless @reachable_functions[symtab].nil?

    funcs = []

    puts "Finding all reachable functions from extension #{name}"

    instructions.each do |inst|
      funcs += inst.reachable_functions(symtab, 32) if inst.defined_in_base?(32)
      funcs += inst.reachable_functions(symtab, 64) if inst.defined_in_base?(64)
    end

    csrs.each do |csr|
      funcs += csr.reachable_functions(arch_def)
    end

    @reachable_functions[symtab] = funcs.uniq
  end

  # @return [Array<Idl::FunctionDefAst>] Array of IDL functions reachable from any instruction or CSR in the extension, irrespective of a specific evaluation context
  def reachable_functions_unevaluated
    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    funcs = []
    instructions.each do |inst|
      funcs += inst.operation_ast(arch_def.symtab).reachable_functions(arch_def.symtab)
    end

    csrs.each do |csr|
      funcs += csr.reachable_functions(arch_def)
    end

    @reachable_functions_unevaluated = funcs.uniq(&:name)
  end
end

# A specific version of an extension
class ExtensionVersion
  # @return [String] Name of the extension
  attr_reader :name

  # @return [Gem::Version] Version of the extension
  attr_reader :version

  # @return [Extension] Extension
  attr_reader :ext

  # @param name [#to_s] The extension name
  # @param version [Integer,String] The version specifier
  # @param arch_def [ArchDef] The architecture definition
  def initialize(name, version, arch_def)
    @name = name.to_s
    @version = Gem::Version.new(version)
    @arch_def = arch_def
    unless arch_def.nil?
      @ext = arch_def.extension(@name)
      raise "Extension #{name} not found in arch def" if @ext.nil?

      @data = @ext.data["versions"].find { |v| v["version"] == version.to_s }
      raise "Extension #{name} version #{version} not found in arch def" if @data.nil?
    end
  end

  # @return [String] The state of the extension version ('ratified', 'developemnt', etc)
  def state = @data["state"]

  def ratification_date = @data["ratification_date"]

  def changes = @data["changes"].nil? ? [] : @data["changes"]

  def url = @data["url"]

  def contributors
    return @contributors unless @contributors.nil?

    @contributors = []
    @data["contributors"]&.each do |c|
      @contributors << Person.new(c)
    end
    @contributors
  end

  # @return [Array<ExtensionParameter>] The list of parameters for this extension version
  def params
    @ext.params.select { |p| p.defined_in_extension_version?(@version) }
  end

  def to_s
    "#{name}@#{version}"
  end

  # @overload ==(other)
  #   @param other [String] An extension name
  #   @return [Boolean] whether or not this ExtensionVersion is named 'other'
  # @overload ==(other)
  #   @param other [ExtensionVersion] An extension name and version
  #   @return [Boolean] whether or not this ExtensionVersion has the exact same name and version as other
  def ==(other)
    case other
    when String
      @name == other
    when ExtensionVersion
      @name == other.name && @version == other.version
    else
      raise "Unexpected comparison"
    end
  end

  # @param other [ExtensionVersion] Comparison
  # @return [Boolean] Whether or not +other+ is an ExtensionVersion with the same name and version
  def eql?(other)
    return false unless other.is_a?(ExtensionVersion)

    @name == other.name && @version == other.version
  end

  def requirements
    r = case @data["requires"]
        when nil
          AlwaysTrueSchemaCondition.new
        when Hash
          SchemaCondition.new(@data["requires"])
        else
          SchemaCondition.new({"oneOf" => [@data["requires"]]})
        end
    if @data.key?("implies")
      rs = [r] + implications.map { |e| e.requirements }
      rs = rs.reject { |r| r.empty? }
      unless rs.empty?
        r = SchemaCondition.all_of(*rs.map { |r| r.to_h })
      end
    end
    r
  end

  def implications
    return @implications unless @implications.nil?

    @implications = []
    case @data["implies"]
    when nil
      return @implications
    when Array
      if @data["implies"][0].is_a?(Array)
        @implications += @data["implies"].map { |e| ExtensionVersion.new(e[0], e[1], @arch_def) }
      else
        @implications << ExtensionVersion.new(@data["implies"][0], @data["implies"][1], @arch_def)
      end
    end
    @implications.uniq!
    @implications
  end

  # @param ext_name [String] Extension name
  # @param ext_version_requirements [Number,String,Array] Extension version requirements, taking the same inputs as Gem::Requirement
  # @see https://docs.ruby-lang.org/en/3.0/Gem/Requirement.html#method-c-new Gem::Requirement#new
  # @return [Boolean] whether or not this ExtensionVersion is named `ext_name` and satifies the version requirements
  def satisfies?(ext_name, *ext_version_requirements)
    @name == ext_name && Gem::Requirement.new(ext_version_requirements).satisfied_by?(@version)
  end

  # sorts extension by name, then by version
  def <=>(other)
    raise ArgumentError, "ExtensionVersions are only comparable to other extension versions" unless other.is_a?(ExtensionVersion)

    if other.name != @name
      @name <=> other.name
    else
      @version <=> other.version
    end
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension version (may be empty)
  def implemented_csrs(archdef)
    raise "should only be called with a fully configured arch def" unless archdef.fully_configured?

    return @implemented_csrs unless @implemented_csrs.nil?

    @implemented_csrs = archdef.implemented_csrs.select do |csr|
      csr.defined_by?(self)
    end
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension version (may be empty)
  def implemented_instructions(archdef)
    raise "should only be called with a fully configured arch def" unless archdef.fully_configured?

    return @implemented_instructions unless @implemented_instructions.nil?

    @implemented_instructions = archdef.implemented_instructions.select do |inst|
      inst.defined_by?(self)
    end
  end
end

# Is the extension mandatory, optional, various kinds of optional, etc.
# Accepts two kinds of YAML schemas:
#   String
#     Example => presence: mandatory
#   Hash
#     Must have the key "optional" with a String value
#     Example => presence:
#                  optional: development
class ExtensionPresence
  attr_reader :presence
  attr_reader :optional_type

  # @param data [Hash, String] The presence data from the architecture spec
  def initialize(data)
    if data.is_a?(String)
      raise "Unknown extension presence of #{data}" unless ["mandatory","optional"].include?(data)

      @presence = data
      @optional_type = nil
    elsif data.is_a?(Hash)
      data.each do |key, value|
        if key == "optional"
          raise ArgumentError, "Extension presence hash #{data} missing type of optional" if value.nil?
          raise ArgumentError, "Unknown extension presence optional #{value} for type of optional" unless
            ["localized", "development", "expansion", "transitory"].include?(value)

          @presence = key
          @optional_type = value
        else
          raise ArgumentError, "Extension presence hash #{data} has unsupported key of #{key}"
        end
      end
    else
      raise ArgumentError, "Extension presence is a #{data.class} but only String or Hash are supported"
    end
  end

  def mandatory? = (@presence == mandatory)
  def optional? = (@presence == optional)

  # Class methods
  def self.mandatory = "mandatory"
  def self.optional = "optional"
  def self.optional_type_localized = "localized"
  def self.optional_type_development = "development"
  def self.optional_type_expansion = "expansion"
  def self.optional_type_transitory = "transitory"

  def self.presence_types = [mandatory, optional]
  def self.optional_types = [
        optional_type_localized,
        optional_type_development,
        optional_type_expansion,
        optional_type_transitory]

  def self.presence_types_obj
    return @presence_types_obj unless @presence_types_obj.nil?

    @presence_types_obj = []

    presence_types.each do |presence_type|
      @presence_types_obj << ExtensionPresence.new(presence_type)
    end

    @presence_types_obj
  end

  def self.optional_types_obj
    return @optional_types_obj unless @optional_types_obj.nil?

    @optional_types_obj = []

    optional_types.each do |optional_type|
      @optional_types_obj << ExtensionPresence.new({ self.optional => optional_type })
    end

    @optional_types_obj
  end

  def to_s
    @optional_type.nil? ? "#{presence}" : "#{presence} (#{optional_type})"
  end

  # @overload ==(other)
  #   @param other [String] A presence string
  #   @return [Boolean] whether or not this ExtensionPresence has the same presence (ignores optional_type)
  # @overload ==(other)
  #   @param other [ExtensionPresence] An extension presence object
  #   @return [Boolean] whether or not this ExtensionPresence has the exact same presence and optional_type as other
  def ==(other)
    case other
    when String
      @presence == other
    when ExtensionPresence
      @presence == other.presence && @optional_type == other.optional_type
    else
      raise "Unexpected comparison"
    end
  end

  # Sorts by presence, then by optional_type
  def <=>(other)
    raise ArgumentError, "ExtensionPresence is only comparable to other ExtensionPresence classes" unless other.is_a?(ExtensionPresence)

    if @presence != other.presence
      @presence <=> other.presence
    else
      @optional_type <=> other.optional_type
    end
  end
end

# Represents an extension requirement, that is an extension name paired with version requirement(s)
class ExtensionRequirement
  # @return [String] Extension name
  attr_reader :name
  attr_reader :note     # Optional note. Can be nil.
  attr_reader :req_id   # Optional Requirement ID. Can be nil.
  attr_reader :presence # Optional presence (e.g., mandatory, optional, etc.). Can be nil.

  # @return [Gem::Requirement] Version requirement
  def version_requirement
    @requirement
  end

  def to_s
    "#{name} #{@requirement}"
  end

  # @param name [#to_s] Extension name
  # @param requirements (see Gem::Requirement#new)
  def initialize(name, *requirements, note: nil, req_id: nil, presence: nil)
    @name = name.to_s
    requirements =
      if requirements.empty?
        [">= 0"]
      else
        requirements
      end
    @requirement = Gem::Requirement.new(requirements)
    @note = note
    @req_id = req_id
    @presence = presence
  end

  # @return [Array<ExtensionVersion>] The list of extension versions that satisfy this requirement
  def satisfying_versions(archdef)
    ext = archdef.extension(@name)
    return [] if ext.nil?

    ext.versions.select { |v| @requirement.satisfied_by?(v.version) }
  end

  # @overload
  #   @param extension_version [ExtensionVersion] A specific extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  # @overload
  #   @param extension_requirement [ExtensionRequirement] A range of extension versions
  #   @return [Boolean] whether or not extension_requirement is satisfied by this requirement
  # @overload
  #   @param extension_name [#to_s] An extension name
  #   @param extension_name [#to_s] An extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  def satisfied_by?(*args)
    if args.size == 1
      if args[0].is_a?(ExtensionVersion)
        args[0].name == @name &&
          @requirement.satisfied_by?(Gem::Version.new(args[0].version))
      elsif args[0].is_a?(ExtensionRequirement)
        satisfying_versions.all? do |ext_ver|
          satified_by?(ext_ver)
        end
      else
        raise ArgumentError, "Single argument must be an ExtensionVersion or ExtensionRquirement"
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "First parameter must be an extension version" unless args[1].respond_to?(:to_s)

      args[0] == @name &&
        @requirement.satisfied_by?(Gem::Version.new(args[1]))
    else
      raise ArgumentError, "Wrong number of args (expecting 1 or 2)"
    end
  end

  # @return [Array<Csr>] List of CSRs defined by any extension satisfying this requirement
  def csrs(arch_def)
    return @csrs unless @csrs.nil?

    @csrs = arch_def.csrs.select do |csr|
      satisfying_versions(arch_def).any? do |ext_ver|
        csr.defined_by?(ext_ver)
      end
    end
  end

  # sorts by name
  def <=>(other)
    raise ArgumentError, "ExtensionRequirements are only comparable to other extension requirements" unless other.is_a?(ExtensionRequirement)

    @name <=> other.name
  end
end
