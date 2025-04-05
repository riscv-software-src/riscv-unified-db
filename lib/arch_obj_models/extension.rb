# frozen_string_literal: true

require_relative "database_obj"
require_relative "parameter"
require_relative "schema"
require_relative "../presence"
require_relative "../version"

# A parameter (AKA option, AKA implementation-defined value) supported by an extension
class ExtensionParameter
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

  # @return [Array<Extension>] The extension(s) that define this parameter
  #
  # Some parameters are defined by multiple extensions (e.g., CACHE_BLOCK_SIZE by Zicbom and Zicboz).
  # When defined in multiple places, the parameter *must* mean the exact same thing.
  attr_reader :exts

  # @returns [Idl::Type] Type of the parameter
  attr_reader :idl_type

  # Pretty convert extension schema to a string.
  def schema_type
    @schema.to_pretty_s
  end

  def default
    if @data["schema"].key?("default")
      @data["schema"]["default"]
    end
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
      ExtensionRequirement.new(ext.name, @data["when"]["version"], arch: ext.arch).satisfied_by?(version)
    end
  end

  # @return [String]
  def name_potentially_with_link(exts)
    raise ArgumentError, "Expecting Array" unless exts.is_a?(Array)
    raise ArgumentError, "Expecting Array[Extension]" unless exts[0].is_a?(Extension)

    if exts.size == 1
      "<<ext-#{exts[0].name}-param-#{name}-def,#{name}>>"
    else
      name
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

  def idl_type = @param.idl_type

  def initialize(param, value)
    @param = param
    @value = value
  end
end

# Extension definition
class Extension < DatabaseObject
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

  # @return [Array<ExtensionVersion>] versions hash from config, sorted by version number
  def versions
    return @versions unless @versions.nil?

    @versions = @data["versions"].map do |v|
      ExtensionVersion.new(name, v["version"], arch)
    end
    @versions.sort!
    @versions
  end

  # @return [Array<ExtensionVersion>] Ratified versions hash from config
  def ratified_versions
    versions.select { |v| v.state == "ratified" }
  end

  # @return [ExtensionVersion] Mimumum defined version of this extension
  def min_version
    versions.min { |a, b| a.version_spec <=> b.version_spec }
  end

  # @return [ExtensionVersion] Maximum defined version of this extension
  def max_version
    versions.max { |a, b| a.version_spec <=> b.version_spec }
  end

  # @return [ExtensionVersion] Mimumum defined ratified version of this extension
  # @return [nil] if there is no ratified version
  def min_ratified_version
    return nil if ratified_versions.empty?

    ratified_versions.min { |a, b| a.version_spec <=> b.version_spec }
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

  # @param version_requirement [String] Version requirement
  # @return [Array<ExtensionVersion>] Array of extensions implied by the largest version of this extension meeting version_requirement
  def implies(version_requirement = nil)
    if version_requirement.nil?
      max_version.implications
    else
      mv = ExtensionRequirement.new(@name, version_requirement, cfg_arch: @cfg_arch).max_version
      mv.implications
    end
  end

  # @return [ExtensionRequirementExpression] Logic expression for conflicts
  def conflicts_condition
    @conflicts_condition ||=
      if @data["conflicts"].nil?
        AlwaysFalseExtensionRequirementExpression.new
      else
        ExtensionRequirementExpression.new(@data["conflicts"], @cfg_arch)
      end
  end

  # @return [Array<Instruction>] the list of instructions implemented by *any version* of this extension (may be empty)
  def instructions
    @instructions ||= cfg_arch.instructions.select { |i| versions.any? { |v| i.defined_by_condition.possibly_satisfied_by?(v) }}
  end

  # @return [Array<Csr>] the list of CSRs implemented by *any version* of this extension (may be empty)
  def csrs
    @csrs ||= cfg_arch.csrs.select { |csr| versions.any? { |v| csr.defined_by_condition.possibly_satisfied_by?(v) } }
  end

  # return the set of reachable functions from any of this extensions's CSRs or instructions in the given evaluation context
  #
  # @return [Array<Idl::FunctionDefAst>] Array of IDL functions reachable from any instruction or CSR in the extension
  def reachable_functions
    return @reachable_functions unless @reachable_functions.nil?

    funcs = []

    puts "Finding all reachable functions from extension #{name}"

    instructions.each do |inst|
      funcs += inst.reachable_functions(32) if inst.defined_in_base?(32)
      funcs += inst.reachable_functions(64) if inst.defined_in_base?(64)
    end

    # The one place in this file that needs a ConfiguredArchitecture object instead of just Architecture.
    raise "In #{name}, need to provide ConfiguredArchitecture" if cfg_arch.nil?
    csrs.each do |csr|
      funcs += csr.reachable_functions
    end

    @reachable_functions = funcs.uniq
  end

  def <=>(other_ext)
    raise ArgumentError, "Can only compare two Extensions" unless other_ext.is_a?(Extension)
    other_ext.name <=> name
  end
end

# A specific version of an extension
class ExtensionVersion
  # @return [String] Name of the extension
  attr_reader :name

  # @return [Extension] Extension
  attr_reader :ext

  # @return [VersionSpec]
  attr_reader :version_spec

  # @return [String]
  attr_reader :version_str

  attr_reader :arch

  # @param name [#to_s] The extension name
  # @param version [String] The version specifier
  # @param arch [Architecture] The architecture definition
  def initialize(name, version_str, arch, fail_if_version_does_not_exist: false)
    @name = name.to_s
    @version_str = version_str
    @version_spec = VersionSpec.new(version_str)

    raise ArgumentError, "Must supply arch" if arch.nil?
    @arch = arch

    @ext = @arch.extension(@name)
    raise "Extension #{name} not found in architecture" if @ext.nil?

    @data = @ext.data["versions"].find { |v| VersionSpec.new(v["version"]) == @version_spec }

    if fail_if_version_does_not_exist && @data.nil?
      raise ArgumentError, "Version #{version_str} of #{@name} extension is not defined"
    elsif @data.nil?
      warn "Version #{version_str} of #{@name} extension is not defined"
    end
  end

  # @return [Array<ExtensionVersions>] List of known ExtensionVersions that are compatible with this ExtensionVersion (i.e., have larger version number and are not breaking)
  def compatible_versions
    return @compatible_versions unless @compatible_versions.nil?

    @compatible_versions = []
    @ext.versions.each do |v|
      @compatible_versions << v if v.version_spec >= @version_spec
      break if @compatible_versions.size.positive? && v.breaking?
    end
    raise "Didn't even find self?" if compatible_versions.empty?

    @compatible_versions
  end

  # @param other [ExtensionVersion]
  # @return [Boolean] Whether or not +other+ is compatible with self
  def compatible?(other) = compatible_versions.include?(other)

  # @return [Boolean] Whether or not this is a breaking version (i.e., incompatible with all prior versions)
  def breaking?
    !@data["breaking"].nil?
  end

  # @return [String] Canonical version string
  def canonical_version = @version_spec.canonical

  # @param other [ExtensionVersion] An extension name and version
  # @return [Boolean] whether or not this ExtensionVersion has the exact same name and version as other
  def eql?(other)
    raise "ExtensionVersion is not comparable to #{other.class}" unless other.is_a?(ExtensionVersion)

    @ext.name == other.ext.name && @version_spec.eql?(other.version_spec)
  end

  # @param other [ExtensionVersion] An extension name and version
  # @return [Boolean] whether or not this ExtensionVersion has the exact same name and version as other
  def ==(other)
    eql?(other)
  end

  # @return [String] The state of the extension version ('ratified', 'developemnt', etc)
  def state = @data["state"]

  def ratification_date = @data["ratification_date"]

  def changes = @data["changes"].nil? ? [] : @data["changes"]

  def url = @data["url"]

  # @return [Array<Person>] List of contributors to this extension version
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
    @ext.params.select { |p| p.defined_in_extension_version?(self) }
  end

  # @return [String] formatted like the RVI manual
  #
  # @example
  #   ExtensionVersion.new("A", "2.2").to_rvi_s #=> "A2p2"
  def to_rvi_s
    "#{name}#{@version_spec.to_rvi_s}"
  end

  # @return [String] Ext@Version
  def to_s
    "#{name}@#{@version_spec.canonical}"
  end

  # @return [ExtensionRequirementExpression] Condition that must be met for this version to be allowed.
  def requirement_condition
    @requirement_condition ||=
      begin
        r = case @data["requires"]
            when nil
              AlwaysTrueExtensionRequirementExpression.new
            when Hash
              ExtensionRequirementExpression.new(@data["requires"], @arch)
            else
              ExtensionRequirementExpression.new({ "oneOf" => [@data["requires"]] }, @arch)
            end
        r
      end
  end

  # @return [Array<Extension>] List of extensions that conflict with this ExtensionVersion
  #                            The list is *not* transitive; if conflict C1 implies C2,
  #                            only C1 shows up in the list
  def conflicts_condition
    ext.conflicts_condition
  end

  # Returns array of ExtensionVersions implied by this ExtensionVersion, along with a condition
  # under which it is in the list (which may be an AlwaysTrueExtensionRequirementExpression)
  #
  # @example
  #   ext_ver.implications #=> { :ext_ver => ExtensionVersion.new(:A, "2.1.0"), :cond => ExtensionRequirementExpression.new(...) }
  #
  # @return [Array<Hash{Symbol => ExtensionVersion, ExtensionRequirementExpression}>]
  #      List of extension versions that this ExtensionVersion implies
  #      This list is *not* transitive; if an implication I1 implies another extension I2,
  #      only I1 shows up in the list
  def implications
    return [] if @data["implies"].nil?

    ConditionalExtensionVersionList.new(@data["implies"], @arch)
  end

  # @return [Array<ExtensionVersion>] List of extension versions that might imply this ExtensionVersion
  #
  # Note that the list returned could include extension versions that conditionally imply this extension version
  # For example, Zcd.implied_by will return C, even though C only implies Zcd if D is also implemented
  def implied_by
    return @implied_by unless @implied_by.nil?

    @implied_by = []
    @arch.extensions.each do |ext|
      next if ext.name == name

      ext.versions.each do |ext_ver|
        ext_ver.implications.each do |implication|
          @implied_by << ext_ver if implication[:ext_ver] == self
        end
      end
    end
    @implied_by
  end

  # @return [Array<Hash{Symbol => ExtensionVersion, ExtensionRequirementExpression>]
  #    List of extension versions that might imply this ExtensionVersion, along with the condition under which it applies
  #
  # @example
  #   zcd_ext_ver.implied_by_with_condition #=> [{ ext_ver: "C 1.0", cond: "D ~> 1.0"}]
  #
  # @example
  #   zba_ext_ver.implied_by_with_condition #=> [{ ext_ver: "B 1.0", cond: AlwaysTrueExtensionRequirementExpression}]
  def implied_by_with_condition
    return @implied_by_with_condition unless @implied_by_with_condition.nil?

    @implied_by_with_condition = []
    @arch.extensions.each do |ext|
      next if ext.name == name

      ext.versions.each do |ext_ver|
        raise "????" if ext_ver.arch.nil?
        ext_ver.implications.each do |implication|
          @implied_by_with_condition << { ext_ver: ext_ver, cond: implication[:cond] } if implication[:ext_ver] == self
        end
      end
    end
    @implied_by_with_condition
  end

  # sorts extension by name, then by version
  def <=>(other)
    unless other.is_a?(ExtensionVersion)
      raise ArgumentError, "ExtensionVersions are only comparable to other extension versions"
    end

    if other.name != @name
      @name <=> other.name
    else
      @version_spec <=> other.version_spec
    end
  end

  def eql?(other)
    unless other.is_a?(ExtensionVersion)
      raise ArgumentError, "ExtensionVersions are only comparable to other extension versions"
    end

    @name == other.name && @version_spec == other.version_spec
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension version (may be empty)
  def implemented_csrs
    return @implemented_csrs unless @implemented_csrs.nil?

    raise "implemented_csrs needs an cfg_arch" if @cfg_arch.nil?

    @implemented_csrs = @cfg_arch.csrs.select do |csr|
      csr.defined_by_condition.possibly_satisfied_by?(self)
    end
  end

  # @return [Array<Csr>] the list of insts implemented by this extension version (may be empty)
  def implemented_instructions
    return @implemented_instructions unless @implemented_instructions.nil?

    raise "implemented_instructions needs an cfg_arch" if @cfg_arch.nil?

    @implemented_instructions = @cfg_arch.instructions.select do |inst|
      inst.defined_by_condition.possibly_satisfied_by?(self)
    end
  end

  # @param design [Design] The design
  # @return [Array<Csr>] List of CSRs in-scope for this design for this extension version (may be empty).
  #                      Factors in effect of design's xlen in the appropriate mode for the CSR.
  def in_scope_csrs(design)
    raise ArgumentError, "Require an IDesign object but got a #{design.class} object" unless design.is_a?(IDesign)

    return @in_scope_csrs unless @in_scope_csrs.nil?

    @in_scope_csrs = @arch.csrs.select do |csr|
      csr.defined_by_condition.possibly_satisfied_by?(self) &&
      (csr.base.nil? || (design.possible_xlens.include?(csr.base)))
    end
  end

  # @param design [Design] The design
  # @return [Array<Instruction>] List of instructions in-scope for this design for this extension version (may be empty).
  #                              Factors in effect of design's xlen in the appropriate mode for the instruction.
  def in_scope_instructions(design)
    raise ArgumentError, "Require an IDesign object but got a #{design.class} object" unless design.is_a?(IDesign)

    return @in_scope_instructions unless @in_scope_instructions.nil?

    @in_scope_instructions = @arch.instructions.select do |inst|
      inst.defined_by_condition.possibly_satisfied_by?(self) &&
      (inst.base.nil? || (design.possible_xlens.include?(inst.base)))
    end
  end
end

# Represents an extension requirement, that is an extension name paired with version requirement(s)
class ExtensionRequirement
  # @return [String] Extension name
  attr_reader :name

  # @return [String,nil] Optional note
  attr_reader :note

  # @return [String,nil] Optional Requirement ID.
  attr_reader :req_id

  # @return [String,nil], Optional presence (e.g., mandatory, optional, etc.)
  attr_reader :presence

  # @return [Array<RequirementSpec>] Set of requirement specifications
  def requirement_specs = @requirements

  def requirement_specs_to_s
    "#{@requirements.map(&:to_s).join(', ')}"
  end

  def to_s
    "#{name} " + requirement_specs_to_s
  end

  # @return [Extension] The extension that this requirement is for
  def extension
    return @extension unless @extension.nil?

    raise "Cannot get extension; arch was not initialized" if @arch.nil?

    @extension = @arch.extension(@name)
  end

  # @param name [#to_s] Extension name
  # @param requirements [String] Single requirement
  # @param requirements [Array<String>] List of requirements, all of which must hold
  # @param arch [Architecture]
  def initialize(name, *requirements, arch: nil, note: nil, req_id: nil, presence: nil)
    raise ArgumentError, "For #{name}, got class #{arch.class} but need Architecture" unless arch.is_a?(Architecture)

    @name = name.to_s.freeze
    @arch = arch
    @ext = @arch.extension(@name)
    raise ArgumentError, "Could not find extension named '#{@name}'" if @ext.nil?

    requirements =
      if requirements.empty?
        ["~> #{@ext.min_version.version_str}"]
      else
        requirements
      end
    @requirements = requirements.map { |r| RequirementSpec.new(r) }

    @note = note.freeze
    @req_id = req_id.freeze
    @presence = presence.freeze
  end

  def invert!
    @requirements.each(&:invert!)
  end

  # @return [Array<ExtensionVersion>] The list of extension versions that satisfy this extension requirement
  def satisfying_versions
    ext = @arch.extension(@name)
    return [] if ext.nil?

    ext.versions.select { |v| satisfied_by?(v) }
  end

  # @return [ExtensionVersion] The minimum extension version that satifies this extension requirement.
  #                            If none, raises an error.
  def min_satisfying_ext_ver
    if satisfying_versions.empty?
      warn "Extension requirement '#{self}' cannot be met by any available extension version. Available versions:"
      if @ext.versions.empty?
        warn "  none"
      else
        @ext.versions.each do |ext_ver|
          warn "  #{ext_ver}"
        end
      end

      raise "Cannot satisfy extension requirement '#{self}'"
    end

    satisfying_versions.min
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
        return false if args[0].name != @name

        @requirements.all? { |r| r.satisfied_by?(args[0].version_spec, @ext) }
      elsif args[0].is_a?(ExtensionRequirement)
        return false if args[0].name != @name

        @requirements.all? do |r|
          args[0].satisfying_versions.all? do |ext_ver|
            r.satisfied_by?(ext_ver.version_spec, @ext)
          end
        end
      else
        raise ArgumentError, "Single argument must be an ExtensionVersion or ExtensionRequirement"
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "First parameter must be an extension version" unless args[1].respond_to?(:to_s)

      return false if args[0] != @name

      @requirements.all? { |r| r.satisfied_by?(args[1], @ext) }
    else
      raise ArgumentError, "Wrong number of args (expecting 1 or 2)"
    end
  end

  # @return [Array<Csr>] List of CSRs defined by any extension satisfying this requirement
  def csrs
    @csrs ||= @arch.csrs.select do |csr|
      satisfying_versions.any? do |ext_ver|
        csr.defined_by_condition.possibly_satisfied_by?(ext_ver)
      end
    end
  end

  # sorts by name
  def <=>(other)
    raise ArgumentError, "ExtensionRequirements are only comparable to other extension requirements" unless other.is_a?(ExtensionRequirement)

    @name <=> other.name
  end
end
