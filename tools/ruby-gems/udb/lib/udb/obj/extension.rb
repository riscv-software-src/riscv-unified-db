# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require_relative "database_obj"
require_relative "certifiable_obj"
require_relative "parameter"
require_relative "../schema"
require_relative "../condition"
require_relative "../presence"
require_relative "../version_spec"

module Udb

# Extension definition
  class Extension < TopLevelDatabaseObject
    # Add all methods in this module to this type of database object.
    include CertifiableObject
    include Comparable

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
        ExtensionVersion.new(name, v["version"], cfg_arch)
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
      cfg_arch.params.each do |param|
        if param.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
          @params << param
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

    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        @data.key?("requirements") \
          ? Condition.new(@data.fetch("requirements"), @cfg_arch, input_file: Pathname.new(__source), input_line: source_line(["requirements"]))
          : AlwaysTrueCondition.new
    end

    # @return [Array<Instruction>] the list of instructions implemented by *any version* of this extension (may be empty)
    def instructions
      @instructions ||=
        cfg_arch.instructions.select do |i|
          i.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
        end
    end

    # @return [Array<Csr>] the list of CSRs implemented by *any version* of this extension (may be empty)
    def csrs
      @csrs ||= \
        cfg_arch.csrs.select do |csr|
          csr.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
        end
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

      csrs.each do |csr|
        funcs += csr.reachable_functions
      end

      @reachable_functions = funcs.uniq
    end

    sig { override.params(other_ext: Object).returns(T.nilable(Integer)).checked(:never) }
    def <=>(other_ext)
      return nil unless other_ext.is_a?(Extension)
      other_ext.name <=> name
    end

    # returns list of exception codes that are defined by any version of this extension
    sig { returns(T::Array[ExceptionCode]) }
    def exception_codes
      @cfg_arch.exception_codes.select do |ecode|
        ecode.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
      end
    end

    # returns list of interrupt codes that are defined by any version of this extension
    sig { returns(T::Array[InterruptCode]) }
    def interrupt_codes
      @cfg_arch.interrupt_codes.select do |icode|
        icode.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
      end
    end

    # returns an ext req that will be satisfied by any known version of this extension
    sig { returns(ExtensionRequirement) }
    def to_ext_req
      ExtensionRequirement.new(name, ">= 0", arch: @cfg_arch)
    end
  end

# A specific version of an extension
  class ExtensionVersion
    extend T::Sig
    include Comparable

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

    # create an ExtensionVersion from YAML
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture
      ).returns(ExtensionVersion)
    }
    def self.create(yaml, cfg_arch)
      requirements =
        if yaml.key?("version")
          yaml.fetch("version")
        else
          raise "not an extension version"
        end
      if requirements.is_a?(Array)
        if requirements.size != 1
          raise "not an extension version: #{requirements} (#{requirements.size})"
        end
        requirements = requirements.fetch(0)
      end
      begin
        ExtensionVersion.new(yaml.fetch("name"), RequirementSpec.new(requirements).version_spec.canonical, cfg_arch)
      rescue
        raise "not an extension version"
      end
    end

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
      if fail_if_version_does_not_exist && @ext.nil?
        raise "Extension #{name} not found in architecture"
      elsif @ext.nil?
        Udb.logger.warn "Extension #{name} not found in architecture"
        return # can't go futher
      end

      @data = @ext.data["versions"].find { |v| VersionSpec.new(v["version"]) == @version_spec }

      if fail_if_version_does_not_exist && @data.nil?
        raise ArgumentError, "Version #{version_str} of #{@name} extension is not defined"
      elsif @data.nil?
        Udb.logger.warn "Version #{version_str} of #{@name} extension is not defined"
      end
    end

    # @api private
    def inspect
      to_s
    end

    # true if the extension {name, version} is defined in the database, regardless of config
    # false otherwise
    sig { returns(T::Boolean) }
    def valid? = !@data.nil?

    # given a set of extension versions from the *same* extension, return the minimal set of
    # extension requirements that would cover then all
    sig { params(ext_vers: T::Array[ExtensionVersion]).returns(ExtensionRequirement) }
    def self.to_ext_req(ext_vers)
      raise "ext_vers cannot be empty" if ext_vers.empty?
      raise "All ext_vers must be of the same extension" unless ext_vers.all? { |ev| ev.name == ext_vers.fetch(0).name }

      sorted = ext_vers.sort
      unless T.must(sorted.min).compatible?(T.must(sorted.max))
        raise "Impossible to combine because the set contains incompatible versions"
      end

      ExtensionRequirement.new(ext_vers.fetch(0).name, "~> #{T.must(sorted.min).version_str}", arch: ext_vers.fetch(0).arch)
    end

    # @api private
    sig { returns(ExtensionTerm) }
    def to_term
      @term ||= ExtensionTerm.new(@name, "=", @version_str)
    end

    sig { returns(AbstractCondition) }
    def to_condition
      @condition ||=
        Condition.new(condition_hash, @arch)
    end

    sig { returns(T.any(T::Hash[String, T.untyped], FalseClass)) }
    def condition_hash
      {
        "extension" => {
          "name" => name,
          "version" => "= #{version_str}"
        }
      }
    end

    # @return List of known ExtensionVersions that are compatible with this ExtensionVersion (i.e., have larger version number and are not breaking)
    # the list is inclsive (this version is present)
    sig { returns(T::Array[ExtensionVersion]) }
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
    sig { params(other: ExtensionVersion).returns(T::Boolean) }
    def compatible?(other) = compatible_versions.include?(other)

    # @return [Boolean] Whether or not this is a breaking version (i.e., incompatible with all prior versions)
    sig { returns(T::Boolean) }
    def breaking?
      !@data["breaking"].nil?
    end

    # @return [String] Canonical version string
    sig { returns(String) }
    def canonical_version = @version_spec.canonical

    # @param other [ExtensionVersion] An extension name and version
    # @return [Boolean] whether or not this ExtensionVersion has the exact same name and version as other
    sig { params(other: ExtensionVersion).returns(T::Boolean) }
    def <=>(other)
      if other.is_a?(ExtensionVersion)
        if @ext.name == other.ext.name
          @version_spec <=> other.version_spec
        else
          @ext.name <=> other.ext.name
        end
      else
        nil
      end
    end

    sig { override.params(other: T.untyped).returns(T::Boolean) }
    def eql?(other)
      if other.is_a?(ExtensionVersion)
        self.==(other)
      else
        false
      end
    end

    sig { override.returns(Integer) }
    def hash
      [@name, @version_spec].hash
    end

    # @return [String] The state of the extension version ('ratified', 'developemnt', etc)
    sig { returns(String) }
    def state = T.cast(@data.fetch("state"), String)

    sig { returns(T.nilable(String)) }
    def ratification_date = @data["ratification_date"]

    sig { returns(T.nilable(T::Array[String])) }
    def changes = @data["changes"].nil? ? [] : T.cast(@data.fetch("changes"), T::Array[String])

    sig { returns(T.nilable(String)) }
    def url = @data["url"]

    # @return [Array<Person>] List of contributors to this extension version
    sig { returns(T::Array[Person]) }
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
        p.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
      end
    end

    # @return [String] formatted like the RVI manual
    #
    # @example
    #   ExtensionVersion.new("A", "2.2").to_rvi_s #=> "A2p2"
    sig { returns(String) }
    def to_rvi_s
      "#{name}#{@version_spec.to_rvi_s}"
    end

    # @return [String] Ext@Version
    sig { returns(String) }
    def to_s
      "#{name}@#{@version_spec.canonical}"
    end

    # @return Condition that must be met for this version to be allowed.
    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        @data.key?("requirements") \
          ? Condition.new(
              @data.fetch("requirements"),
              @arch,
              input_file: Pathname.new(ext.__source),
              input_line: ext.source_line(["versions", ext.data.fetch("versions").index { |v| VersionSpec.new(v["version"]) == version_spec }])
            )
          : AlwaysTrueCondition.new
    end

    # the combination of this extension version requirement along with the overall extension requirements
    sig { returns(AbstractCondition) }
    def combined_requirements_condition
      if @data.key?("requirements") && !ext.requirements_condition.empty?
        Condition.new(
          {
            "allOf" => [
              @data.fetch("requirements"),
              ext.data.fetch("requirements")
            ]
          },
          @arch
        )
      elsif requirements_condition.empty?
        ext.requirements_condition
      else
        requirements_condition
      end
    end

    # Returns array of ExtensionVersions implied by this ExtensionVersion, along with a condition
    # under which it is in the list (which may be an AlwaysTrueCondition)
    #
    # specifically, this returns the complete list of positive terms (terms that are not negated
    # in solution) of requirements,
    # along with a condition under which the positive term applies
    #
    # @example
    #   given the equation (reqpresenting implications of the "C" extension):
    #      Zca AND (!F OR Zcf) AND (!D OR Zcd)
    #
    #   return:
    #     [
    #        { ext_ver: Zca, cond: True },
    #        { ext_ver: Zcf, cond: !F },
    #        { ext_ver: Zcd, cond: !D }
    #     ]
    # @example
    #   given the equation
    #     Zc AND ((Zc1 AND Zc2) OR (!Zcond))
    #
    #   return
    #     [
    #       { ext_ver: Zc,  cond True},
    #       { ext_ver: Zc1, cond: !Zcond},
    #       { ext_ver: Zc2, cond: !Zcond}
    #     ]
    #
    # This list is *not* transitive; if an implication I1 implies another extension I2,
    # only I1 shows up in the list
    sig { returns(T::Array[ConditionalExtensionVersion]) }
    def implications
      @implications ||= requirements_condition.implied_extension_requirements.map do |cond_ext_req|
        if cond_ext_req.ext_req.is_ext_ver?
          satisfied = cond_ext_req.cond.satisfied_by_cfg_arch?(@arch)
          if satisfied == SatisfiedResult::Yes
            ConditionalExtensionVersion.new(
              ext_ver: cond_ext_req.ext_req.to_ext_ver,
              cond: AlwaysTrueCondition.new
            )
          elsif satisfied == SatisfiedResult::Maybe
            ConditionalExtensionVersion.new(
              ext_ver: cond_ext_req.ext_req.to_ext_ver,
              cond: cond_ext_req.cond
            )
          else
            nil
          end
        else
          nil
        end
      end.compact
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
            @implied_by << ext_ver if implication.ext_ver == self && implication.cond.could_be_satisfied_by_cfg_arch?(@arch)
          end
        end
      end
      @implied_by
    end

    # @return
    #    List of extension versions that might imply this ExtensionVersion, along with the condition under which it applies
    #
    # @example
    #   zcd_ext_ver.implied_by_with_condition #=> [{ ext_ver: "C 1.0", cond: "D ~> 1.0"}]
    #
    # @example
    #   zba_ext_ver.implied_by_with_condition #=> [{ ext_ver: "B 1.0", cond: AlwaysTrueCondition}]
    sig { returns(T::Array[ConditionalExtensionVersion]) }
    def implied_by_with_condition
      return @implied_by_with_condition unless @implied_by_with_condition.nil?

      @implied_by_with_condition = []
      @arch.extensions.each do |ext|
        next if ext.name == name

        ext.versions.each do |ext_ver|
          raise "????" if ext_ver.arch.nil?
          ext_ver.implications.each do |implication|
            if implication.ext_ver == self
              @implied_by_with_condition << ConditionalExtensionVersion.new(ext_ver: ext_ver, cond: implication.cond)
            end
          end
        end
      end
      @implied_by_with_condition
    end

    # sorts extension by name, then by version
    sig { override.params(other: T.untyped).returns(T.nilable(Integer)).checked(:never) }
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

    # the list of exception codes that require this extension version (or a compatible version)
    # in order to be defined
    sig { returns(T::Array[ExceptionCode]) }
    def exception_codes
      @exception_codes ||=
        @cfg_arch.exception_codes.select do |ecode|
          # define every extension version except this one (and compatible),
          # and test if the condition can be satisfied
          ecode.defined_by_condition.satisfiability_depends_on_ext_req?(ExtensionRequirement.new(@name, "~> #{@version_spec}", arch: @cfg_arch))
        end
    end

    # the list of interrupt codes that require this extension version (or a compatible version)
    # in order to be defined
    sig { returns(T::Array[InterruptCode]) }
    def interrupt_codes
      @interrupt_codes ||=
        @cfg_arch.interrupt_codes.select do |ecode|
          ecode.defined_by_condition.satisfiability_depends_on_ext_req?(ExtensionRequirement.new(@name, "~> #{@version_spec}", arch: @cfg_arch))
        end
    end

    # @param design [Design] The design
    # @return [Array<Csr>] List of CSRs in-scope for this design for this extension version (may be empty).
    #                      Factors in effect of design's xlen in the appropriate mode for the CSR.
    def in_scope_csrs(design)
      raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

      return @in_scope_csrs unless @in_scope_csrs.nil?

      @in_scope_csrs = @arch.csrs.select do |csr|
        csr.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req) &&
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
        inst.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req) &&
        (inst.base.nil? || (design.possible_xlens.include?(inst.base)))
      end
    end

    sig { returns(ExtensionRequirement) }
    def to_ext_req
      ExtensionRequirement.new(name, "= #{version_str}", arch: @arch)
    end

    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      {
        "name" => @name,
        "version" => "= #{version_str}"
      }
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

    sig { returns(ExtensionTerm) }
    def to_term
      if @requirements.size == 1
        ExtensionTerm.new(name, @requirements.fetch(0).op, @requirements.fetch(0).version_spec)
      else
        raise "TODO"
      end
    end

    sig { returns(ConfiguredArchitecture) }
    def cfg_arch = @arch

    # returns true when the version requirement is ">= 0"
    sig { returns(T::Boolean) }
    def satified_by_any_version?
      @requirements.size == 1 && \
        @requirements.fetch(0).op == ">=" && \
        @requirements.fetch(0).version_spec == "0"
    end

    # @return Set of requirement specifications
    sig { returns(T::Array[RequirementSpec]) }
    def requirement_specs = @requirements

    # pretty display of requirements, with special case that ">= 0" is "any"
    def requirement_specs_to_s_pretty
      if satified_by_any_version?
        "any"
      else
        "#{@requirements.map(&:to_s).join(" and ")}"
      end
    end

    sig { override.returns(String) }
    def to_s
      "#{name} " + requirement_specs_to_s_pretty
    end

    # like to_s, but omits the requirement if the requirement is ">= 0"
    sig { returns(String) }
    def to_s_pretty
      if satified_by_any_version?
        name
      else
        to_s
      end
    end

    # @return [Extension] The extension that this requirement is for
    def extension
      @extension ||= @arch.extension(@name)
    end

    # create an ExtensionRequirement from YAML
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture
      ).returns(ExtensionRequirement)
    }
    def self.create(yaml, cfg_arch)
      requirements =
        if yaml.key?("version")
          yaml.fetch("version")
        else
          ">= 0"
        end
      ExtensionRequirement.new(yaml.fetch("name"), requirements, arch: cfg_arch)
    end

    sig { returns(T::Boolean) }
    def is_ext_ver?
      @requirements.size == 1 && @requirements.fetch(0).op == "="
    end

    sig { returns(ExtensionVersion) }
    def to_ext_ver
      unless is_ext_ver?
        raise "ExtensionRequirement can only be converted to and ExtensionVersion when there is a single equality version requirement"
      end

      ExtensionVersion.new(name, @requirements.fetch(0).version_spec.to_s, @arch)
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
      Udb.logger.warn "Could not find extension named '#{@name}'" if @ext.nil?

      requirements_ary =
        if @ext.nil?
          []
        else
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
        end
      @requirements = requirements_ary.map { |r| RequirementSpec.new(r) }

      @note = note.freeze
      @req_id = req_id.freeze
      @presence = presence.freeze
    end

    def invert!
      @requirements.each(&:invert!)
    end

    # true if there is at least one matching extension version defined in the database
    # false otherwise (meaning there is no definition)
    sig { returns(T::Boolean) }
    def valid? = !satisfying_versions.empty?

    # @return [Array<ExtensionVersion>] The list of extension versions that satisfy this extension requirement
    sig { returns(T::Array[ExtensionVersion]) }
    def satisfying_versions
      return @satisfying_versions unless @satisfying_versions.nil?

      ext = @arch.extension(@name)

      @satisfying_versions = ext.nil? ? [] : ext.versions.select { |v| satisfied_by?(v) }
    end

    # @return the disjunction of the requirements condition of all satisfying versions
    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        Condition.disjunction(
          satisfying_versions.map { |ext_ver| ext_ver.combined_requirements_condition },
          @arch
        )
    end

    sig { returns(AbstractCondition) }
    def to_condition
      @condition ||=
        Condition.new(condition_hash, @arch)
    end

    sig { returns(T.any(T::Hash[String, T.untyped], FalseClass)) }
    def condition_hash
      if @requirements.size == 1
        {
          "extension" => {
            "name" => name,
            "version" => @requirements.fetch(0).to_s
          }
        }
      else
        # conditions don't handle multi-reqs, so return the list of satisfying versions instead
        if satisfying_versions.size == 0
          false
        elsif satisfying_versions.size == 1
          {
            "extension" => {
              "name" => name,
              "version" => "= #{satisfying_versions.fetch(0).version_str}"
            }
          }
        else
          {
            "anyOf" => satisfying_versions.map do |ext_ver|
              {
                "extension" => {
                  "name" => name,
                  "version" => "= #{ext_ver.version_str}"
                }
              }
            end
          }
        end
      end
    end

    def params
      @params ||= satisfying_versions.map(&:params).flatten.uniq
    end

    # @return [ExtensionVersion] The minimum extension version that satifies this extension requirement.
    #                            If none, raises an error.
    sig { returns(ExtensionVersion) }
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

      T.must(satisfying_versions.min)
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

      T.must(satisfying_versions.max)
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
    sig { returns(T::Array[Csr]) }
    def csrs
      @csrs ||= @arch.csrs.select do |csr|
        csr.defined_by_condition.satisfiability_depends_on_ext_req?(self)
      end
    end

    sig { params(other: Object).returns(T::Boolean) }
    def ==(other)
      return false unless other.is_a?(ExtensionRequirement)

      (satisfying_versions.size == other.satisfying_versions.size) && \
        satisfying_versions.all? { |version| other.satisfying_versions.include?(version) }
    end

    # sorts by name
    sig { override.params(other: T.untyped).returns(T.nilable(Integer)).checked(:never) }
    def <=>(other)
      return nil unless other.is_a?(ExtensionRequirement)

      @name <=> other.name
    end

    # hash equality
    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      return false unless T.cast(other, Object).is_a?(ExtensionRequirement)

      satisfying_versions == T.cast(other, ExtensionRequirement).satisfying_versions
    end

    sig { override.returns(Integer) }
    def hash
      satisfying_versions.hash
    end

    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      {
        "name" => @name,
        "version" => @requirements.empty? ? ">= 0" : @requirements.map(&:to_s)
      }
    end
  end

end
