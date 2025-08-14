# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require_relative "database_obj"
require_relative "can_define_normative_rules"
require_relative "can_define_coverage_points"
require_relative "can_define_cert_test_procedures"
require_relative "parameter"
require_relative "../schema"
require_relative "../req_expression"
require_relative "../presence"
require_relative "../version_spec"

module Udb

# Extension definition
class Extension < TopLevelDatabaseObject
  # Add all methods in these modules to this type of database object.
  include CanDefineNormativeRules
  include CanDefineCoveragePoints
  include CanDefineCertTestProcedures

  # @return [String] Long name of the extension
  sig { returns(String) }
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
  sig { returns(ExtensionVersion) }
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
  # @return [Array<ExtensionVersion>] Array of extensions implied by the largest version of this extension meeting version_requirement
  def implies(version_requirement = nil)
    if version_requirement.nil?
      max_version.implications
    else
      mv = ExtensionRequirement.new(@name, version_requirement, arch: @cfg_arch).max_satisfying_ext_ver
      mv.implications
    end
  end

  # @return [ExtensionRequirementExpression] Logic expression for conflicts
  sig { returns(AbstractRequirement) }
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
  sig { returns(T::Array[Idl::FunctionBodyAst]) }
  def reachable_functions
    return @reachable_functions unless @reachable_functions.nil?

    funcs = T.let([], T::Array[Idl::FunctionBodyAst])

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

  sig { returns(T::Array[ExceptionCode]) }
  def exception_codes
    @exception_codes ||=
      if @data.key?("exception_codes")
        ecodes = []

        d = T.cast(@data["exception_codes"], T::Array[T::Hash[String, T.any(Integer, String)]])
        d.each do |edata|
          raise "Duplicate exception code" if ecodes.any? { |e| e.num == edata["num"] || e.name == edata["name"] || e.var == edata["var"] }

          ecodes << ExceptionCode.new(
            T.cast(edata.fetch("name"), String),
            T.cast(edata.fetch("var"), String),
            T.cast(edata.fetch("num"), Integer),
            self
          )
        end

        ecodes
      else
        []
      end
  end

  sig { returns(T::Array[InterruptCode]) }
  def interrupt_codes
    @exception_codes ||=
      if @data.key?("interrupt_codes")
        ecodes = []

        d = T.cast(@data["interrupt_codes"], T::Array[T::Hash[String, T.any(Integer, String)]])
        d.each do |edata|
          raise "Duplicate interrup code" if ecodes.any? { |e| e.num == edata["num"] || e.name == edata["name"] || e.var == edata["var"] }

          ecodes << InterruptCode.new(
            T.cast(edata.fetch("name"), String),
            T.cast(edata.fetch("var"), String),
            T.cast(edata.fetch("num"), Integer),
            self
          )
        end

        ecodes
      else
        []
      end
  end
end

# A specific version of an extension
class ExtensionVersion
  extend T::Sig

  # @return [String] Name of the extension
  sig { returns(String) }
  attr_reader :name

  # @return [Extension] Extension
  sig { returns(Extension) }
  attr_reader :ext

  # @return [VersionSpec]
  sig { returns(VersionSpec) }
  attr_reader :version_spec

  # @return [String]
  sig { returns(String) }
  attr_reader :version_str

  sig { returns(ConfiguredArchitecture) }
  attr_reader :arch

  # @param name [#to_s] The extension name
  # @param version [String] The version specifier
  # @param arch [Architecture] The architecture definition
  sig { params(name: String, version_str: String, arch: ConfiguredArchitecture, fail_if_version_does_not_exist: T::Boolean).void }
  def initialize(name, version_str, arch, fail_if_version_does_not_exist: false)
    @name = name
    @version_str = version_str
    @version_spec = VersionSpec.new(version_str)

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

  # given a set of extension versions from the *same* extension, return the minimal set of
  # extension requirements that would cover then all
  sig { params(ext_vers: T::Array[ExtensionVersion]).returns(ExtensionRequirement) }
  def self.to_ext_req(ext_vers)
    raise "ext_vers cannot be empty" if ext_vers.empty?
    raise "All ext_vers must be of the same extension" unless ext_vers.all? { |ev| ev.name == ext_vers.fetch(0).name }

    sorted = ext_vers.sort
    unless T.must(sorted.min).compatible?(sorted.max)
      raise "Impossible to combine because the set contains incompatible versions"
    end

    ExtensionRequirement.new(ext_vers.fetch(0).name, "~> #{T.must(sorted.min).version_str}", arch: ext_vers.fetch(0).arch)
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

  # @return [Array<Parameter>] The list of parameters for this extension version
  sig { returns(T::Array[Parameter]) }
  def params
    @ext.params.select do |p|
      p.when.satisfied_by? do |ext_req|
        if ext_req.name == name
          ext_req.satisfied_by?(self)
        else
          @arch.possible_extension_versions.any? { |poss_ext_ver| ext_req.satisfied_by?(poss_ext_ver) }
        end
      end
    end
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
  sig { returns(AbstractRequirement) }
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
  sig { returns(ConditionalExtensionVersionList) }
  def implications
    return ConditionalExtensionVersionList.new([], @arch) if @data["implies"].nil?

    ConditionalExtensionVersionList.new(@data["implies"], @arch)
  end

  # @return [Array<ExtensionVersion>] List of extension versions that might imply this ExtensionVersion
  #
  # Note that the list returned could include extension versions that conditionally imply this extension version
  # For example, Zcd.implied_by will return C, even though C only implies Zcd if D is also implemented
  sig { returns(T::Array[ExtensionVersion]) }
  def implied_by
    return @implied_by unless @implied_by.nil?

    @implied_by = []
    @arch.extensions.each do |ext|
      next if ext.name == name

      ext.versions.each do |ext_ver|
        ext_ver.implications.each do |implication|
          @implied_by << ext_ver if implication.ext_ver == self && implication.cond.could_be_true?(@arch)
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
          @implied_by_with_condition << { ext_ver: ext_ver, cond: implication.cond } if implication.ext_ver == self
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

  sig { returns(T::Array[ExceptionCode]) }
  def exception_codes
    @exception_codes ||=
      if @data.key?("exception_codes")
        ecodes = []

        d = T.cast(@data["exception_codes"], T::Array[T::Hash[String, T.any(Integer, String)]])
        d.each do |edata|
          if ecodes.any? { |e| e.num == edata["num"] || e.name == edata["name"] || e.var == edata["var"] }
            raise "Duplicate exception code"
          end

          cond = T.let(T.cast(edata["when"], T::Hash[String, String]), T.nilable(T::Hash[String, String]))
          unless cond.nil? || cond["version"].nil?
            # check version
            next unless ExtensionRequirement.new(name, T.must(cond["version"]), arch: @cfg_arch).satisfied_by?(self)
          end
          ecodes <<
            ExceptionCode.new(
              T.cast(edata["name"], String),
              T.cast(edata["var"], String),
              T.cast(edata["num"], Integer),
              ext
            )
        end

        ecodes
      else
        []
      end
  end

  sig { returns(T::Array[InterruptCode]) }
  def interrupt_codes
    @interrupt_codes ||=
      if @data.key?("interrupt_codes")
        ecodes = []

        d = T.cast(@data["interrupt_codes"], T::Array[T::Hash[String, T.any(Integer, String)]])
        d.each do |edata|
          if ecodes.any? { |e| e.num == edata["num"] || e.name == edata["name"] || e.var == edata["var"] }
            raise "Duplicate interrupt code"
          end

          cond = T.let(T.cast(edata["when"], T::Hash[String, String]), T.nilable(T::Hash[String, String]))
          unless cond.nil? || cond["version"].nil?
            # check version
            next unless ExtensionRequirement.new(name, T.must(cond["version"]), arch: @cfg_arch).satisfied_by?(self)
          end
          ecodes <<
            InterruptCode.new(
              T.cast(edata["name"], String),
              T.cast(edata["var"], String),
              T.cast(edata["num"], Integer),
              ext
            )
        end

        ecodes
      else
        []
      end
  end

  # @param design [Design] The design
  # @return [Array<Csr>] List of CSRs in-scope for this design for this extension version (may be empty).
  #                      Factors in effect of design's xlen in the appropriate mode for the CSR.
  def in_scope_csrs(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

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
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_instructions unless @in_scope_instructions.nil?

    @in_scope_instructions = @arch.instructions.select do |inst|
      inst.defined_by_condition.possibly_satisfied_by?(self) &&
      (inst.base.nil? || (design.possible_xlens.include?(inst.base)))
    end
  end

  sig { returns(ExtensionRequirement) }
  def to_ext_req
    ExtensionRequirement.new(name, "= #{version_str}", arch: @arch)
  end
end

# Represents an extension requirement, that is an extension name paired with version requirement(s)
class ExtensionRequirement
  extend T::Sig

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
    @extension ||= @arch.extension(@name)
  end

  # @param name [#to_s] Extension name
  # @param requirements [String] Single requirement
  # @param requirements [Array<String>] List of requirements, all of which must hold
  # @param arch [Architecture]
  # @param presence [String or Presence or nil]
  sig {
    params(
      name: String,
      requirements: T.any(String, T::Array[String]),
      arch: ConfiguredArchitecture,
      note: T.nilable(String),
      req_id: T.nilable(String),
      presence: T.nilable(Presence)
    ).void
  }
  def initialize(name, requirements, arch:, note: nil, req_id: nil, presence: nil)
    @name = name.to_s.freeze
    @arch = arch
    @ext = @arch.extension(@name)
    raise ArgumentError, "Could not find extension named '#{@name}'" if @ext.nil?

    requirements_ary =
      case requirements
      when Array
        if requirements.empty?
          ["~> #{@ext.min_version.version_str}"]
        else
          requirements
        end
      when String
        [requirements]
      else
        T.absurd(requirements)
      end
    @requirements = requirements_ary.map { |r| RequirementSpec.new(r) }

    @note = note.freeze
    @req_id = req_id.freeze
    @presence = presence.freeze
  end

  def invert!
    @requirements.each(&:invert!)
  end

  # @return [Array<ExtensionVersion>] The list of extension versions that satisfy this extension requirement
  def satisfying_versions
    return @satisfying_versions unless @satisfying_versions.nil?

    ext = @arch.extension(@name)

    @satisfying_versions = ext.nil? ? [] : ext.versions.select { |v| satisfied_by?(v) }
  end

  def params
    @params ||= satisfying_versions.map(&:params).flatten.uniq
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

  # @return [ExtensionVersion] The minimum extension version that satifies this extension requirement.
  #                            If none, raises an error.
  sig { returns(ExtensionVersion) }
  def max_satisfying_ext_ver
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

    satisfying_versions.max
  end

  # returns true if this extension requirement is a superset of other_ext_req
  sig { params(other_ext_req: ExtensionRequirement).returns(T::Boolean) }
  def superset?(other_ext_req)
    return false if other_ext_req.name != name

    other_ext_req.satisfying_versions.all? { |ext_ver| satisfied_by?(ext_ver) }
  end

  # returns true if this extension requirement is a subset of other_ext_req
  sig { params(other_ext_req: ExtensionRequirement).returns(T::Boolean) }
  def subset?(other_ext_req)
    return false if other_ext_req.name != name

    satisfying_versions.all? { |ext_ver| other_ext_req.satisfied_by?(ext_ver) }
  end

  # returns true if either this extension requirement is a superset of other_ext_req
  # or other_ext_req is a superset of this extension requirement
  sig { params(other_ext_req: ExtensionRequirement).returns(T::Boolean) }
  def compatible?(other_ext_req)
    superset?(other_ext_req) || subset?(other_ext_req)
  end

  # given a compatible other_ext_req, return a single extension requirement that
  # covers both this and other_ext_req
  sig { params(other_ext_req: ExtensionRequirement).returns(ExtensionRequirement) }
  def merge(other_ext_req)
    raise "Cannot merge incompatible ExtensionRequirements" unless compatible?(other_ext_req)

    if superset?(other_ext_req)
      self
    else
      other_ext_req
    end
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

end
