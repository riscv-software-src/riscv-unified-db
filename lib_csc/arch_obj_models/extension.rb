# frozen_string_literal: true

require_relative "database_obj"
require_relative "parameter"
require_relative "schema"
require_relative "../presence"
require_relative "../version"

# Extension definition
class Extension < DatabaseObject
  # @return [String] Long name of the extension
  def long_name = @data["long_name"]

  # @return [String] Either unprivileged or privileged
  def priv_type = @data["type"]

  # @return [String] Either unpriv or priv
  def compact_priv_type
    case priv_type
    when "unprivileged"
      "unpriv"
    when "privileged"
      "priv"
    else
      if priv_type.nil? || priv_type.empty?
        raise ArgumentError, "Extension #{name} missing its type in database (must be privileged or unprivileged)"
      else
        raise ArgumentError, "Extension #{name} has illegal privileged/unprivileged type of #{priv_type}"
      end
    end
  end

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

  # @return [Boolean] Any version ratified?
  def ratified = ratified_versions.any?

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

  # @return [Array<Parameter>] List of parameters added by this extension
  def params
    return @params unless @params.nil?

    @params = []
    if @data.key?("params")
      @data["params"].each do |param_name, param_data|
        @params << Parameter.new(self, param_name, param_data)
      end
    end
    @params
  end

  # @param version_requirement [String] Version requirement
  # @return [Array<ExtensionVersion>] Array of extensions implied by any version of this extension meeting version_requirement
  def implies(version_requirement = nil)
    if version_requirement.nil?
      return [] unless ExtensionRequirement.new(@new, @arch).satisfied_by?(max_version.version)
    else
      return [] unless ExtensionRequirement.new(@new, version_requirement, @arch).satisfied_by?(max_version.version)
    end

    max_version.implications
  end

  # @return [Array<ExtensionRequirement>] List of conflicting extension requirements
  def conflicts
    return [] if @data["conflicts"].nil?

    if @data["conflicts"].is_a?(String)
      [ExtensionRequirement.new(@data["conflicts"], @arch)]
    elsif @data["conflicts"].is_a?(Hash)
      [ExtensionRequirement.new(@data["conflicts"]["name"], @data["conflicts"]["version"], @arch)]
    elsif @data["conflicts"].is_a?(Array)
      @data["conflicts"].map do |conflict|
        if conflict.is_a?(String)
          ExtensionRequirement.new(conflict, @arch)
        elsif conflict.is_a?(Array)
          ExtensionRequirement.new(conflict["name"], conflict["version"], @arch)
        else
          raise "Invalid conflicts data: #{conflict.inspect}"
        end
      end
    else
      raise "Invalid conflicts data: #{@data["conflicts"].inspect}"
    end
  end

  # @return [Array<Instruction>] the list of instructions implemented by *any version* of this extension (may be empty)
  def instructions
    return @instructions unless @instructions.nil?

    @instructions = arch.instructions.select { |i| versions.any? { |v| i.defined_by?(v) }}
  end

  # @return [Array<Csr>] the list of CSRs implemented by *any version* of this extension (may be empty)
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = arch.csrs.select { |csr| versions.any? { |v| csr.defined_by?(v) } }
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
      funcs += csr.reachable_functions(design)
    end

    @reachable_functions[symtab] = funcs.uniq
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

  # @return [String] The state of the extension version ('ratified', 'development', etc)
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

  # @return [Array<Parameter>] The list of parameters for this extension version
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

  # @return [SchemaCondition] Condition that must be met for this version to be allowed.
  #                           Transitively includes any requirements from an implied extension.
  def requirement_condition
    @requirement_condition ||=
      begin
        r = case @data["requires"]
            when nil
              AlwaysTrueSchemaCondition.new
            when Hash
              SchemaCondition.new(@data["requires"], @arch)
            else
              SchemaCondition.new({ "oneOf" => [@data["requires"]] }, @arch)
            end
        if @data.key?("implies")
          rs = [r] + implications.map(&:requirement_condition)
          rs = rs.reject(&:empty?)
          r = SchemaCondition.all_of(*rs.map(&:to_h), arch: @arch) unless rs.empty?
        end
        r
      end
  end

  # @return [Array<ExtensionVersion>] List of extensions that conflict with this ExtensionVersion
  #                                   The list is *not* transitive; if conflict C1 implies C2,
  #                                   only C1 shows up in the list
  def conflicts
    @conflicts ||= @ext.conflicts.map(&:satisfying_versions).flatten.uniq.sort
  end

  # @return [Array<ExtensionVersion>] List of extensions that conflict with this ExtensionVersion
  #                                   The list *is* transitive; if conflict C1 implies C2,
  #                                   both C1 and C2 show up in the list
  def transitive_conflicts
    return @transitive_conflicts unless @transive_conflicts.nil?

    @transitive_conflicts = []
    conflicts.each do |c|
      @transitive_conflicts << c
      @transitive_conflicts.concat(c.transitive_implications)
    end
    @transitive_conflicts.uniq!
    @transitive_conflicts.sort!
    @transitive_conflicts
  end

  # @return [Array<ExtensionVersion>] List of extension versions that are implied by with this ExtensionVersion
  #                                   This list is *not* transitive; if an implication I1 implies another extension I2,
  #                                   only I1 shows up in the list
  def implications
    return @implications unless @implications.nil?

    @implications = []
    case @data["implies"]
    when nil
      return @implications
    when Array
      if @data["implies"][0].is_a?(Array)
        @implications.concat(@data["implies"].map { |e| ExtensionVersion.new(e[0], e[1], @arch) })
      else
        @implications << ExtensionVersion.new(@data["implies"][0], @data["implies"][1], @arch)
      end
    end
    @implications.sort!
    @implications
  end

  # @return [Array<ExtensionVersion>] List of extension versions that are implied by with this ExtensionVersion.
  #                                   This list is transitive; if an implication I1 implies another extension I2,
  #                                   both I1 and I2 are in the returned list
  def transitive_implications
    return @transitive_implications unless @transitive_implications.nil?

    @transitive_implications = []
    case @data["implies"]
    when nil
      return @transitive_implications
    when Array
      if @data["implies"][0].is_a?(Array)
        impls = @data["implies"].map { |e| ExtensionVersion.new(e[0], e[1], @arch) }
        @transitive_implications.concat(impls)
        impls.each do |i|
          transitive_impls = i.implications
          @transitive_implications.concat(transitive_impls) unless transitive_impls.empty?
        end
      else
        impl = ExtensionVersion.new(@data["implies"][0], @data["implies"][1], @arch)
        @transitive_implications << impl
        transitive_impls = impl.implications
        @transitive_implications.concat(transitive_impls) unless transitive_impls.empty?
      end
    end
    @transitive_implications.uniq!
    @transitive_implications.sort!
    @transitive_implications
  end

  # @param ext_name [String] Extension name
  # @param ext_version_requirements [String,Array<String>] Extension version requirements
  # @return [Boolean] whether or not this ExtensionVersion is named `ext_name` and satisfies the version requirements
  def satisfies?(ext_name, *ext_version_requirements)
    ExtensionRequirement.new(ext_name, ext_version_requirements, arch).satisfied_by?(self)
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

  # @return [Array<Csr>] List of CSRs implemented by this extension version (may be empty)
  def implemented_csrs
    return @implemented_csrs unless @implemented_csrs.nil?

    @implemented_csrs = @arch.csrs.select do |csr|
      csr.defined_by?(self)
    end
  end

  # @return [Array<Instruction>] List of insts implemented by this extension version (may be empty)
  def implemented_instructions
    return @implemented_instructions unless @implemented_instructions.nil?

    @implemented_instructions = @arch.instructions.select do |inst|
      inst.defined_by?(self)
    end
  end

  # @param design [Design] The design
  # @return [Array<Csr>] List of CSRs in-scope for this design for this extension version (may be empty).
  #                      Factors in effect of design's xlen in the appropriate mode for the CSR.
  def in_scope_csrs(design)
    raise ArgumentError, "Require an IDesign object but got a #{design.class} object" unless design.is_a?(IDesign)

    return @in_scope_csrs unless @in_scope_csrs.nil?

    @in_scope_csrs = @arch.csrs.select do |csr|
      csr.defined_by?(self) &&
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
      inst.defined_by?(self) &&
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

  # @return [Extension] The extension corresponding to this requirement
  def extension = @ext

  # @param name [#to_s] Extension name
  # @param requirements [String] Single requirement
  # @param requirements [Array<String>] List of requirements, all of which must hold
  # @param arch [Architecture] The architecture database
  def initialize(name, *requirements, arch, note: nil, req_id: nil, presence: nil)
    raise ArgumentError, "For #{name}, arch not allowed to be nil" if arch.nil?
    raise ArgumentError, "For #{name}, Architecture is required" unless arch.is_a?(Architecture)

    @name = name.to_s.freeze
    @arch = arch
    @ext = @arch.extension(@name)
    if @ext.nil?
      raise ArgumentError, "Could not find extension named '#{@name}'"
    end

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

  # @return [Array<ExtensionVersion>] The list of extension versions that satisfy this extension requirement.
  #                                   If none, returns an empty array.
  def satisfying_versions
    return @satisfying_versions unless @satisfying_versions.nil?

    @satisfying_versions = @ext.versions.select { |v| satisfied_by?(v) }
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
