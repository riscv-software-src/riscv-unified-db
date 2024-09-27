# frozen_string_literal: true

require_relative "obj"

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class ExtensionParameter
  # @return [String] Parameter name
  attr_reader :name

  # @return [String] Asciidoc description
  attr_reader :desc

  # @return [Hash] JSON Schema for the parameter value
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
  attr_reader :type

  def initialize(name, desc, schema, extra_validation, exts)
    @name = name
    @desc = desc
    @schema = schema
    @extra_validation = extra_validation
    @exts = exts
    begin
      @type = Idl::Type.from_json_schema(@schema).make_const.freeze
    rescue
      warn "While parsing scheme for ExtensionParameter #{ext.name}.#{name}"
      raise
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
    @data["versions"]
  end

  # @return [Array<Hash>] Ratified versions hash from config
  def ratified_versions
    @data["versions"].select { |v| v["state"] == "ratified" }
  end

  # @return [String] Mimumum defined version of this extension
  def min_version
    versions.map { |v| Gem::Version.new(v["version"]) }.min
  end

  # @return [String] Maximum defined version of this extension
  def max_version
    versions.map { |v| Gem::Version.new(v["version"]) }.max
  end

  # @return [String] Mimumum defined ratified version of this extension
  # @return [nil] if there is no ratified version
  def min_ratified_version
    return nil if ratified_versions.empty?

    ratified_versions.map { |v| Gem::Version.new(v["version"]) }.min
  end

  # @return [Array<ExtensionParameter>] List of parameters added by this extension
  def params
    return @params unless @params.nil?

    @params = []
    if @data.key?("params")
      @data["params"].each do |param_name, param_data|
        also_defined_in = []
        unless param_data["also_defined_in"].nil?
          if param_data["also_defined_in"].is_a?(String)
            other_ext = arch_def.extension(param_data["also_defined_in"])
            raise "Definition error in #{name}.#{param_name}: #{param_data['also_defined_in']} is not a known extension" if other_ext.nil?
            also_defined_in << other_ext
          else
            unless param_data["also_defined_in"].is_a?(Array) && param_data["also_defined_in"].all? { |e| e.is_a?(String) }
              raise "schema error: also_defined_in should be a string or array of strings"
            end

            param_data["also_defined_in"].each do |other_ext_name|
              other_ext = arch_def.extension(other_ext_name)
              raise "Definition error in #{name}.#{param_name}: #{param_data['also_defined_in']} is not a known extension" if other_ext.nil?
              also_defined_in << other_ext
            end
          end
        end
        @params << ExtensionParameter.new(
          param_name,
          param_data["description"],
          param_data["schema"],
          param_data["extra_validation"],
          [self] + also_defined_in
        )
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
    implications = []
    @data["versions"].each do |v|
      next unless Gem::Requirement.new(version_requirement).satisfied_by?(Gem::Version.new(v["version"]))

      case v["implies"]
      when nil
        next
      when Array
        if v["implies"][0].is_a?(Array)
          implications += v["implies"].map { |e| ExtensionVersion.new(e[0], e[1])}
        else
          implications << ExtensionVersion.new(v["implies"][0], v["implies"][1])
        end
      end
    end
    implications
  end

  # @return [Array<Instruction>] the list of instructions implemented by this extension (may be empty)
  def instructions
    return @instructions unless @instructions.nil?

    @instructions = arch_def.instructions.select { |i| i.definedBy == name || (i.definedBy.is_a?(Array) && i.definedBy.include?(name)) }
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension (may be empty)
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = arch_def.csrs.select { |csr| csr.defined_by?(ExtensionVersion.new(name, max_version)) }
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
      funcs += inst.operation_ast(arch_def.idl_compiler).reachable_functions_unevaluated(arch_def)
    end

    csrs.each do |csr|
      funcs += csr.reachable_functions_unevaluated(arch_def)
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


  # @param name [#to_s] The extension name
  # @param version [Integer,String] The version specifier
  # @param arch_def [ArchDef] The architecture definition
  def initialize(name, version)
    @name = name.to_s
    @version = Gem::Version.new(version)
  end

  # @return Extension the extension object
  def ext(arch_def)
    arch_def.extension(name)
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
end

# Represents an extension requirement, that is an extension name paired with version requirement(s)
class ExtensionRequirement
  # @return [String] Extension name
  attr_reader :name
  attr_reader :note     # Optional note. Can be nil.
  attr_reader :req_id   # Optional Requirement ID. Can be nil.
  attr_reader :status   # Optional status (e.g., Mandatory, Optional, etc.). Can be nil.

  # @return [Gem::Requirement] Version requirement
  def version_requirement
    @requirement
  end

  def to_s
    "#{name} #{@requirement}"
  end

  # @param name [#to_s] Extension name
  # @param requirements (see Gem::Requirement#new)
  def initialize(name, *requirements, note: nil, req_id: nil, status: nil)
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
    @status = status
  end

  # @overload
  #   @param extension_version [ExtensionVersion] A specific extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  # @overload
  #   @param extension_name [#to_s] An extension name
  #   @param extension_name [#to_s] An extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  def satisfied_by?(*args)
    if args.size == 1
      raise ArgumentError, "Single argument must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      args[0].name == @name &&
        @requirement.satisfied_by?(Gem::Version.new(args[0].version))
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "First parameter must be an extension version" unless args[1].respond_to?(:to_s)

      args[0] == @name &&
        @requirement.satisfied_by?(Gem::Version.new(args[1]))
    else
      raise ArgumentError, "Wrong number of args (expecting 1 or 2)"
    end
  end

  # sorts by name
  def <=>(other)
    raise ArgumentError, "ExtensionRequirements are only comparable to other extension requirements" unless other.is_a?(ExtensionRequirement)

    @name <=> other.name
  end
end
