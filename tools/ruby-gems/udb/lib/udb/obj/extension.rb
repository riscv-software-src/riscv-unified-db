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

    # @return Long name of the extension
    sig { returns(String) }
    def long_name = @data.fetch("long_name")

    # @return Either unprivileged or privileged
    sig { returns(String) }
    def priv_type = @data.fetch("type")

    # @return Either unpriv or priv
    sig { returns(String) }
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

    # @return Company that developed the extension
    # @return if the company isn't known
    sig { returns(T.nilable(Company)) }
    def company
      if @data.key?("company")
        @company ||= Company.new(@data["company"])
      end
    end

    # @return { "name" => String, "url" => String} The name and URL of a document license the doc falls under
    # @return [nil] if the license isn't known
    sig { returns(T.nilable(T::Hash[String, String])) }
    def doc_license
      @data["doc_license"]
    end

    # @return versions hash from config, sorted by version number
    sig { returns(T::Array[ExtensionVersion]) }
    def versions
      return @versions unless @versions.nil?

      @versions = @data["versions"].map do |v|
        cfg_arch.extension_version(name, v["version"])
      end
      @versions.sort!
      @versions
    end

    # @return Ratified versions hash from config
    sig { returns(T::Array[ExtensionVersion]) }
    def ratified_versions
      versions.select { |v| v.state == "ratified" }
    end

    # @return Any version ratified?
    sig { returns(T::Boolean) }
    def ratified = ratified_versions.any?

    # @return Mimumum defined version of this extension
    sig { returns(ExtensionVersion) }
    def min_version
      T.must(versions.min { |a, b| T.must(a.version_spec <=> b.version_spec) })
    end

    # @return Maximum defined version of this extension
    sig { returns(ExtensionVersion) }
    def max_version
      T.must(versions.max { |a, b| T.must(a.version_spec <=> b.version_spec) })
    end

    # @return Mimumum defined ratified version of this extension, or nil if there is none
    sig { returns(T.nilable(ExtensionVersion)) }
    def min_ratified_version
      return nil if ratified_versions.empty?

      ratified_versions.min { |a, b| T.must(a.version_spec <=> b.version_spec) }
    end

    # @return List of parameters that must be defined if some version of this extension is defined,
    #          excluding those required because of a requirement of extension
    sig { returns(T::Array[Parameter]) }
    def params
      @params ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding params for #{name} [:bar] :current/:total",
              total: cfg_arch.params.size,
              clear: true
            )
          cfg_arch.params.select do |p|
            pb.advance
            if p.defined_by_condition.mentions?(self)
              param_defined = p.defined_by_condition
              ext_implemented = to_condition
              preconditions_met = requirements_condition

              # inst is defined transitively by self if:
              (
                (-param_defined & ext_implemented) # it must be defined when preconditions are met, and
              ).unsatisfiable? && \
              (
                (-param_defined & preconditions_met) # it may not be defined when only self's requirements are met
              ).satisfiable?
            end
          end
        end
    end

    class ConditionallyApplicableParameter < T::Struct
      prop :cond, AbstractCondition
      prop :param, Parameter
    end

    sig { returns(T::Array[ConditionallyApplicableParameter]) }
    def conditional_params
      @cond_params ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding conditional params for #{name} [:bar] :current/:total",
              total: cfg_arch.params.size,
              clear: true
            )
          cfg_arch.params.filter_map do |p|
            pb.advance
            next if params.include?(p)
            next unless p.defined_by_condition.mentions?(self)
            next unless (p.defined_by_condition & self.to_condition).satisfiable?

            cond = p.defined_by_condition.partial_eval(ext_reqs: [self.to_ext_req]).minimize(expand: false)
            ConditionallyApplicableParameter.new(cond:, param: p)
          end
        end
    end

    # @return List of parameters that must be defined if this extension is defined due to one of the extension's requirements
    #          excluding those required because of a requirement of extension    def implied_params
    sig { returns(T::Array[Parameter]) }
    def implied_params
      @implied_params ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied params for #{name} [:bar] :current/:total",
              total: cfg_arch.params.size,
              clear: true
            )
          cfg_arch.params.select do |p|
            pb.advance
            param_defined = p.defined_by_condition
            preconditions_met = requirements_condition

            (-param_defined & preconditions_met).unsatisfiable?
          end
        end
    end

    # @return List of parameters that must be defined if some version of this extension is defined
    sig { returns(T::Array[Parameter]) }
    def all_params_that_must_be_implemented
      @all_params_that_must_be_implemented = params + implied_params
    end

    # returns a condition representing *any* version of this extension being implemented
    sig { returns(Condition) }
    def to_condition
      @condition ||= Condition.new({ "extension" => { "name" => name } }, @cfg_arch)
    end

    # @return a condition representing the requirements that apply to all versions of this extension
    sig { returns(AbstractCondition) }
    def general_extension_requirements_condition
      @general_extension_requirements_condition ||=
        @data.key?("requirements") \
          ? Condition.new(@data.fetch("requirements"), @cfg_arch, input_file: Pathname.new(__source), input_line: source_line(["requirements"]))
          : AlwaysTrueCondition.new(@cfg_arch)
    end

    # @return a condition representing the requirements that apply to all versions of this extension (not just the generic requirements)
    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||= to_ext_req.requirements_condition
    end

    # @return list of extensions that conflict with self
    def conflicting_extensions
      @cfg_arch.extensions.select do |ext|
        (to_condition & ext.to_condition).unsatisfiable?
      end
    end

    # @return the list of instructions implemented *directly* by *any version* of this extension (may be empty)
    #  Direct means that the instruction must be defined when the extension is implemented and may not be
    #  implemented when just the extension's requirements are met
    #
    #  In other words, direct is the set of instructions that are defined without transitivity
    sig { returns(T::Array[Instruction]) }
    def instructions
      @instructions ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding instructions for #{name} [:bar] :current/:total",
              total: cfg_arch.instructions.size,
              clear: true
            )
          cfg_arch.instructions.select do |i|
            pb.advance
            inst_defined = i.defined_by_condition
            next unless inst_defined.mentions?(self)
            requirement_met = to_condition
            preconditions_met = requirements_condition

            # inst is defined exclusively by self if:
            (
              (-inst_defined & requirement_met) # it must be defined when self is met, and
            ).unsatisfiable? &
            (
              (-inst_defined & preconditions_met)  # it may not be defined when only self's requirements are met
            ).satisfiable?
          end
        end
    end

    # @api private
    sig { returns(T::Set[Instruction]) }
    def instructions_set
      @instructions_set ||= Set.new(instructions)
    end

    # @return the list of instructions implemented *indirectly* by *any version* of this extension because
    # a requirement of the extension directly defines the instruction
    #
    # For example, the "C" extension implies c.addi because c.addi is directly defined by Zca and C
    # requires Zca to be implemented
    #
    # This list may be empty
    sig { returns(T::Array[Instruction]) }
    def implied_instructions
      @instructions ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied instructions for #{name} [:bar] :current/:total",
              total: cfg_arch.instructions.size,
              clear: true
            )
          cfg_arch.instructions.select do |i|
            pb.advance
            if i.defined_by_condition.mentions?(to_ext_req)
              inst_defined = i.defined_by_condition
              preconditions_met = requirements_condition

              # inst is defined transitively by self if:
              (
                (-inst_defined & preconditions_met) # it must be defined when preconditions are met, and
              ).unsatisfiable?
            end
          end
        end
    end

    # @api private
    sig { returns(T::Set[Instruction]) }
    def implied_instructions_set
      @implied_instructions_set ||= Set.new(implied_instructions)
    end

    # @return the list of CSRs implemented by *any version* of this extension (may be empty),
    # not including those defined by requirements of this extension
    sig { returns(T::Array[Csr]) }
    def csrs
      @csrs ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding csrs for #{name} [:bar] :current/:total",
              total: cfg_arch.csrs.size,
              clear: true
            )
          cfg_arch.csrs.select do |csr|
            pb.advance
            csr_defined = csr.defined_by_condition
            next unless csr_defined.mentions?(self)
            requirement_met = to_condition
            preconditions_met = requirements_condition

            # csr is defined exclusively by self if:
            (
              (csr_defined & -requirement_met) # it must be defined when self is met, and
            ).unsatisfiable? &
            (
              (-csr_defined & preconditions_met)  # it may not be defined when only self's requirements are met
            ).satisfiable?
          end
        end
    end

    # @return the list of csrs implemented *indirectly* by *any version* of this extension because
    # a requirement of the extension directly defines the csr
    #
    # This list may be empty
    sig { returns(T::Array[Csr]) }
    def implied_csrs
      @implied_csrs ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied csrs for #{name} [:bar] :current/:total",
              total: cfg_arch.csrs.size,
              clear: true
            )
          cfg_arch.csrs.select do |csr|
            pb.advance
            csr_defined = csr.defined_by_condition
            preconditions_met = requirements_condition

            # csr is defined transitively by self if:
            (
              (-csr_defined & preconditions_met) # it must be defined when preconditions are met, and
            ).unsatisfiable?
          end
        end
    end

    # @return the list of csrs that must be defined when any version of this extension is defined
    #         includes both those defined directly by self and those implied by self's requirements
    sig { returns(T::Array[Csr]) }
    def csrs_that_must_be_implemented
      @csrs_that_must_be_implemented ||= csrs + implied_csrs
    end

    # return the set of reachable functions from any of this extensions's CSRs or instructions in the given evaluation context
    #
    # @return Array of IDL functions reachable from any instruction or CSR in the extension
    sig { returns(T::Array[Idl::FunctionDefAst]) }
    def reachable_functions
      return @reachable_functions unless @reachable_functions.nil?

      funcs = T.let([], T::Array[Idl::FunctionDefAst])

      Udb.logger.info "Finding all reachable functions from extension #{name}"

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
      @exception_codes ||=
        @cfg_arch.exception_codes.select do |ecode|
          if ecode.defined_by_condition.mentions?(self)
            ecode.defined_by_condition.satisfied_by_ext_req?(to_ext_req, include_requirements: false) ||
              ecode.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
          else
            false
          end
        end
    end

    # returns list of interrupt codes that are defined by any version of this extension
    sig { returns(T::Array[InterruptCode]) }
    def interrupt_codes
      @interrupt_codes ||=
        @cfg_arch.interrupt_codes.select do |icode|
          if icode.defined_by_condition.mentions?(self)
            icode.defined_by_condition.satisfied_by_ext_req?(to_ext_req, include_requirements: false) ||
              icode.defined_by_condition.satisfiability_depends_on_ext_req?(to_ext_req)
          else
            false
          end
        end
    end

    # returns an ext req that will be satisfied by any known version of this extension
    sig { returns(ExtensionRequirement) }
    def to_ext_req
      @ext_req ||= @cfg_arch.extension_requirement(name, ">= 0")
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
        cfg_arch.extension_version(yaml.fetch("name"), RequirementSpec.new(requirements).version_spec)
      rescue
        raise "not an extension version"
      end
    end

    # @api private
    class MemomizedState < T::Struct
      prop :unconditional_expanded_ext_reqs, T.nilable(T::Array[ExtensionRequirement])
      prop :unconditional_unexpanded_ext_reqs, T.nilable(T::Array[ExtensionRequirement])
      prop :unconditional_expanded_ext_conflicts, T.nilable(T::Array[ExtensionRequirement])
      prop :unconditional_unexpanded_ext_conflicts, T.nilable(T::Array[ExtensionRequirement])
      prop :conditional_expanded_extension_requirements, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :conditional_unexpanded_extension_requirements, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :expanded_ext_requirements, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :unexpanded_ext_requirements, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :expanded_ext_conflicts, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :unexpanded_ext_conflicts, T.nilable(T::Array[ConditionalExtensionRequirement])
      prop :term, T.nilable(ExtensionTerm)
      prop :condition, T.nilable(AbstractCondition)
      prop :compatible_versions, T.nilable(T::Array[ExtensionVersion])
      prop :key, T.nilable(Integer)
    end

    # @param name [#to_s] The extension name
    # @param version [String] The version specifier
    # @param arch [Architecture] The architecture definition
    sig { params(name: String, version_spec: VersionSpec, arch: ConfiguredArchitecture, fail_if_version_does_not_exist: T::Boolean).void }
    def initialize(name, version_spec, arch, fail_if_version_does_not_exist: false)
      @name = name.freeze
      @version_spec = version_spec.freeze
      @version_str = @version_spec.canonical.freeze

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

      @memo = MemomizedState.new
    end
    private_class_method :new

    # @return true if this ExtensionVersion is defined in the database
    sig { returns(T::Boolean) }
    def valid? = !@ext.nil?

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

      ext_vers.fetch(0).arch.extension_requirement(ext_vers.fetch(0).name, "~> #{T.must(sorted.min).version_str}")
    end

    # @api private
    sig { returns(ExtensionTerm) }
    def to_term
      @memo.term ||= ExtensionTerm.new(@name, "=", @version_str)
    end

    sig { returns(AbstractCondition) }
    def to_condition
      @memo.condition ||=
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
      return @memo.compatible_versions unless @memo.compatible_versions.nil?

      @memo.compatible_versions = []
      @ext.versions.each do |v|
        @memo.compatible_versions << v if v.version_spec >= @version_spec
        break if @memo.compatible_versions.size.positive? && v.breaking?
      end
      raise "Didn't even find self?" if compatible_versions.empty?

      @memo.compatible_versions
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
      @memo.key ||= [@name, @version_spec].hash
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

    # @return The list of parameters for this extension version
    sig { returns(T::Array[T.any(Parameter, ParameterWithValue)]) }
    def params
      @params ||=
        ext.params.select do |param|
          (param.defined_by_condition & to_condition).satisfiable?
        end
    end

    # @return the list of instructions that must be implemented when self is implemented,
    # excluding instructions required by a dependence
    sig { returns(T::Array[Instruction]) }
    def directly_defined_instructions
      @instructions ||=
        ext.instructions.select do |inst|
          (inst.defined_by_condition & to_condition).satisfiable?
        end
    end

    # @api private
    sig { returns(T::Set[Instruction]) }
    def directly_defined_instructions_set
      @instructions_set ||= Set.new(directly_defined_instructions)
    end

    sig { returns(T::Array[Instruction]) }
    def implied_instructions
      @implied_instructions ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied instructions for #{self} [:bar] :current/:total",
              total: @arch.instructions.size,
              clear: true
            )
          @arch.instructions.select do |i|
            pb.advance

            next if directly_defined_instructions_set.include?(i)

            (-i.defined_by_condition & to_condition).unsatisfiable?
          end
        end
    end

    # list of all instructions that must be defined if this extension version is implemented
    # includes both those instructions directly defined by the extension plus any instruction
    # that must exist because of a dependence
    sig { returns(T::Array[Instruction]) }
    def all_instructions_that_must_be_implemented
      @all_instructions_that_must_be_implemented ||=
        directly_defined_instructions + implied_instructions
    end

    sig { returns(T::Set[Instruction]) }
    def implied_instructions_set
      @implied_instructions_set ||= Set.new(implied_instructions)
    end

    sig { returns(T::Array[Csr]) }
    def csrs
      @csrs ||=
        ext.csrs.select do |csr|
          (csr.defined_by_condition && to_condition).satisfiable?
        end
    end

    sig { returns(T::Array[Csr]) }
    def implied_csrs
      @implied_csrs ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied csrs for #{self} [:bar] :current/:total",
              total: @arch.csrs.size,
              clear: true
            )
          @arch.csrs.select do |csr|
            pb.advance
            if csr.defined_by_condition.mentions?(self, expand: true)
              (-csr.defined_by_condition & requirements_condition).unsatisfiable?
            end
          end
        end
    end

    sig { returns(T::Array[Csr]) }
    def all_csrs_that_must_be_implemented
      @all_csrs_that_must_be_implemented ||= csrs + implied_csrs
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
    def version_specific_requirements_condition
      @requirements_condition ||=
        @data.key?("requirements") \
          ? Condition.new(
              @data.fetch("requirements"),
              @arch,
              input_file: Pathname.new(ext.__source),
              input_line: ext.source_line(["versions", ext.data.fetch("versions").index { |v| VersionSpec.new(v["version"]) == version_spec }])
            )
          : AlwaysTrueCondition.new(@arch)
    end

    # the combination of this extension version requirement along with the overall extension requirements
    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        if @data.key?("requirements") && ext.data.key?("requirements")
          Condition.new(
            {
              "allOf" => [
                @data.fetch("requirements"),
                ext.data.fetch("requirements")
              ]
            },
            @arch
          )
        elsif !@data.key?("requirements")
          ext.general_extension_requirements_condition
        else
          version_specific_requirements_condition
        end
    end

    sig { returns(T::Array[ConditionalExtensionRequirement]) }
    def defining_extension_requirements
      []
      # combined_requirements_condition.implied_extension_requirements
    end

    # return all ExtensionRequirements that this ExtensionVersion unconditionally depends on
    # When expand is false, just return the list of ExtensionRequirements directly mentioned by the extension
    # When expand is true, also include ExtensionRequirements that are required by those directly mentioned by the extension
    #                      (i.e., collect the list from the transitive closure of requirements)
    sig { params(expand: T::Boolean).returns(T::Array[ExtensionRequirement]) }
    def unconditional_extension_requirements(expand:)
      if expand && !@memo.unconditional_expanded_ext_reqs.nil?
        @memo.unconditional_expanded_ext_reqs
      elsif !expand && !@memo.unconditional_unexpanded_ext_reqs.nil?
        @memo.unconditional_unexpanded_ext_reqs
      else
        list =
          begin
            requirements_condition.ext_req_terms(expand:).select do |ext_req|
              # is requirements_condition satisfiable when ext_req is not met?
              (requirements_condition & -ext_req.to_condition).unsatisfiable?
            end


            # req = requirements_condition.to_logic_tree(expand:)
            # expand_req = requirements_condition.to_logic_tree(expand: true)

            # # find all unconditional reqs -- that is,
            # # reqs that must always be satisfied for requirements to be met
            # unconditional_terms =
            #   req.terms.select do |term|
            #     next if term.is_a?(ParameterTerm) || term.is_a?(XlenTerm)
            #     raise "?" if term.is_a?(FreeTerm)

            #     next if term.name == name

            #     # see if req is satisfiable when term is absent
            #     cb = LogicNode.make_replace_cb do |node|
            #       if node.type == LogicNodeType::Term && node.node_children.fetch(0).is_a?(ExtensionTerm)
            #         node_term = T.cast(node.node_children.fetch(0), ExtensionTerm)
            #         if node_term.name == name
            #           LogicNode::True
            #         elsif node_term.name == term.name
            #           LogicNode::False
            #         else
            #           node
            #         end
            #       else
            #         node
            #       end
            #     end
            #     !expand_req.replace_terms(cb).satisfiable?
            #   end
            # T.cast(unconditional_terms, T::Array[ExtensionTerm]).map { |t| t.to_ext_req(@arch) }
          end
        if expand
          @memo.unconditional_expanded_ext_reqs = list
          @memo.unconditional_expanded_ext_reqs.freeze
        else
          @memo.unconditional_unexpanded_ext_reqs = list
          @memo.unconditional_unexpanded_ext_reqs.freeze
        end
      end
    end

    # return the exhaustive, transitive list of all known extension versions that unconditionally
    # conflict with self
    sig { returns(T::Array[ExtensionVersion]) }
    def unconditional_extension_version_conflicts
      @unconditional_extension_version_conflicts ||=
        @arch.extension_versions.select do |ext_ver|
          next if ext_ver.name == name

          (to_condition & ext_ver.to_condition).unsatisfiable?
          # !Condition.conjunction([to_condition, ext_ver.to_condition], @arch).satisfiable?
        end
    end

    # return all ExtensionRequirements that this ExtensionVersion unconditionally conflicts with
    # When expand is false, just return the list of ExtensionRequirements directly mentioned by the extension
    # When expand is true, also include ExtensionRequirements that are required by those directly mentioned by the extension
    #                      (i.e., collect the list from the transitive closure of requirements)
    sig { params(expand: T::Boolean).returns(T::Array[ExtensionRequirement]) }
    def unconditional_extension_conflicts(expand:)
      if expand && !@memo.unconditional_expanded_ext_conflicts.nil?
        @memo.unconditional_expanded_ext_conflicts
      elsif !expand && !@memo.unconditional_unexpanded_ext_conflicts.nil?
        @memo.unconditional_unexpanded_ext_conflicts
      else
        list =
          begin
            requirements_condition.ext_req_terms(expand:).select do |ext_req|
              (requirements_condition & ext_req.to_condition).unsatisfiable?
            end


            # req = requirements_condition.to_logic_tree(expand:)
            # expand_req = requirements_condition.to_logic_tree(expand: true)

            # # find all unconditional reqs -- that is,
            # # reqs that must always be satisfied for requirements to be met
            # unconditional_terms =
            #   req.terms.select do |term|
            #     next if term.is_a?(ParameterTerm) || term.is_a?(XlenTerm)
            #     raise "?" if term.is_a?(FreeTerm)

            #     next if term.name == name

            #     # see if req is unsatisfiable when term is present
            #     cb = LogicNode.make_replace_cb do |node|
            #       if node.type == LogicNodeType::Term && node.node_children.fetch(0).is_a?(ExtensionTerm)
            #         node_term = T.cast(node.node_children.fetch(0), ExtensionTerm)
            #         if node_term.name == name
            #           LogicNode::True
            #         elsif node_term.name == term.name
            #           LogicNode::True
            #         else
            #           node
            #         end
            #       else
            #         node
            #       end
            #     end
            #     !expand_req.replace_terms(cb).satisfiable?
            #   end

            # T.cast(unconditional_terms, T::Array[ExtensionTerm]).map { |t| t.to_ext_req(@arch) }
          end
        if expand
          @memo.unconditional_expanded_ext_conflicts = list
          @memo.unconditional_expanded_ext_conflicts.freeze
        else
          @memo.unconditional_unexpanded_ext_conflicts = list
          @memo.unconditional_unexpanded_ext_conflicts.freeze
        end
      end
    end

    sig { params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def conditional_extension_requirements(expand:)
      if expand && !@memo.conditional_expanded_extension_requirements.nil?
        @memo.conditional_expanded_extension_requirements
      elsif !expand && !@memo.conditional_unexpanded_extension_requirements.nil?
        @memo.conditional_unexpanded_extension_requirements
      else
        req = requirements_condition.to_logic_tree(expand:)

        cb = LogicNode.make_replace_cb do |node|
          next node unless node.type == LogicNodeType::Term

          rterm = node.children.fetch(0)

          next node unless rterm.is_a?(ExtensionTerm)

            # remove self
          next LogicNode::True if rterm.to_ext_req(@arch).satisfied_by?(self)

            # remove terms unconditionally true or false
          next LogicNode::True if unconditional_extension_requirements(expand: true).any? { |ext_req| ext_req.satisfied_by?(rterm.to_ext_req(@arch)) }
          next LogicNode::False if unconditional_extension_conflicts(expand: true).any? { |ext_req| ext_req.satisfied_by?(rterm.to_ext_req(@arch)) }

          node
        end

        remaining =
          req.replace_terms(cb).minimize(LogicNode::CanonicalizationType::ProductOfSums)

        list = T.let([], T::Array[ConditionalExtensionRequirement])

        # for the remaining terms, find out which ones
        remaining.terms.each do |term|
          next unless term.is_a?(ExtensionTerm)

          # find unconditional reqs of self && term
          c = Condition.conjunction([term.to_condition(@arch), to_condition], @arch)
          ctree = c.to_logic_tree(expand: true)
          unconditional_terms = remaining.terms.select do |cterm|
            next if cterm.is_a?(ParameterTerm) || cterm.is_a?(XlenTerm)
            raise "?" if cterm.is_a?(FreeTerm)

            next if cterm.name == name
            next if cterm.name == term.name

            cb = LogicNode.make_replace_cb do |node|
              if node.type == LogicNodeType::Term && node.node_children.fetch(0).is_a?(ExtensionTerm)
                node_term = T.cast(node.node_children.fetch(0), ExtensionTerm)
                if node_term.name == name
                  LogicNode::True
                elsif node_term.name == cterm.name
                  LogicNode::False
                else
                  node
                end
              else
                node
              end
            end
            !ctree.replace_terms(cb).satisfiable?
          end

          next if unconditional_terms.empty?

          if unconditional_terms.size == 1
            cond = T.cast(unconditional_terms.fetch(0), ExtensionTerm).to_ext_req(@arch).to_condition
            contradiction =
              Condition.conjunction(
                [
                  cond,
                  Condition.not(term.to_condition(@arch), @arch),
                  to_condition
                ],
                @arch
              )
            is_needed = !contradiction.satisfiable?
            if is_needed
              if Condition.conjunction([cond, Condition.not(term.to_condition(@arch), @arch)], @arch).satisfiable? # skip reqs that are implied
                list << ConditionalExtensionRequirement.new(
                  ext_req: term.to_ext_req(@arch),
                  cond:
                )
              end
            end
          else
            conj = Condition.conjunction(unconditional_terms.map { |t| T.cast(t, ExtensionTerm).to_condition(@arch) }, @arch)
            conj_tree = conj.to_logic_tree(expand: false)
            formula = LogicNode.new(
              LogicNodeType::And,
              conj_tree.node_children.map do |node|
                covered = conj_tree.node_children.any? do |other_node|
                  next false if node.equal?(other_node)

                  if Condition.conjunction([to_condition, Condition.new(other_node.to_h, @arch)], @arch).always_implies?(Condition.new(node.to_h, @arch))
                    true
                  else
                    false
                  end
                end

                if covered
                  LogicNode::True
                else
                  node
                end
              end
            )
            # is this needed? if self can still be satisfied when condition is false but term is true,
            # this term isn't actually a requirement (it's most likely related to a conflict)
            contradiction =
              Condition.conjunction(
                [
                  conj,
                  Condition.not(term.to_condition(@arch), @arch),
                  to_condition
                ],
                @arch
              )
            is_needed = !contradiction.satisfiable?
            cond = Condition.new(formula.reduce.to_h, @arch)
            if is_needed # && Condition.conjunction([cond, term.to_condition(@arch), to_condition], @arch).satisfiable? # make sure it's a requirement
              if Condition.conjunction([cond, Condition.not(term.to_condition(@arch), @arch)], @arch).satisfiable?
                list << ConditionalExtensionRequirement.new(
                  ext_req: term.to_ext_req(@arch),
                  cond:
                )
              end
            end
          end
        end

        if expand
          list.each do |cond_ext_req|
            ext_ver = T.must(cond_ext_req.ext_req.satisfying_versions.max)
            ext_ver.ext_requirements(expand:).each do |nested_cond_ext_req|
              already_in_cond_list =
                list.any? { |c| c.ext_req.satisfied_by?(nested_cond_ext_req.ext_req) } \
                  || list.any? { |c| c.cond.to_logic_tree(expand: false).terms.any? { |t| T.cast(t, ExtensionTerm).to_ext_req(@arch).satisfied_by?(nested_cond_ext_req.ext_req) } }
              already_in_uncond_list =
                unconditional_extension_requirements(expand:).any? { |ext_req| nested_cond_ext_req.ext_req.satisfied_by?(ext_req) }
              next if already_in_uncond_list

              if already_in_cond_list
                # keep the one with the more expansive condition

              else
                if nested_cond_ext_req.cond.empty?
                  list << ConditionalExtensionRequirement.new(
                    ext_req: nested_cond_ext_req.ext_req,
                    cond: cond_ext_req.cond
                  )
                else
                  list << ConditionalExtensionRequirement.new(
                    ext_req: nested_cond_ext_req.ext_req,
                    cond: Condition.conjunction([cond_ext_req.cond, nested_cond_ext_req.cond], @arch)
                  )
                end
              end
            end
          end
        end

        if expand
          @memo.conditional_expanded_extension_requirements = list
          @memo.conditional_expanded_extension_requirements.freeze
        else
          @memo.conditional_unexpanded_extension_requirements = list
          @memo.conditional_unexpanded_extension_requirements.freeze
        end
      end
    end

    # list of requirements that must be met to implement this ExtensionVersion
    # If conditional, the requirement only applies when the condition is true
    sig { params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def ext_requirements(expand:)
      # make a condition for the version, expand it, and then report what comes out, minus self
      if expand
        @memo.expanded_ext_requirements ||=
          unconditional_extension_requirements(expand:).map { |ext_req| ConditionalExtensionRequirement.new(ext_req:, cond: AlwaysTrueCondition.new(@arch)) } \
            + conditional_extension_requirements(expand:)
      else
        @memo.unexpanded_ext_requirements ||=
          unconditional_extension_requirements(expand:).map { |ext_req| ConditionalExtensionRequirement.new(ext_req:, cond: AlwaysTrueCondition.new(@arch)) } \
            + conditional_extension_requirements(expand:)
      end
    end

    sig { params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def ext_conflicts(expand:)
      # make a condition for the version, expand it, and then report what comes out, minus self
      if expand
        @memo.expanded_ext_conflicts ||=
          unconditional_extension_conflicts(expand:).map { |ext_req| ConditionalExtensionRequirement.new(ext_req:, cond: AlwaysTrueCondition.new(@arch)) }
      else
        @memo.unexpanded_ext_conflicts ||=
          unconditional_extension_conflicts(expand:).map { |ext_req| ConditionalExtensionRequirement.new(ext_req:, cond: AlwaysTrueCondition.new(@arch)) }
      end
    end

    # sorts extension by name, then by version
    sig { override.params(other: T.untyped).returns(T.nilable(Integer)).checked(:never) }
    def <=>(other)
      return nil unless other.is_a?(ExtensionVersion)

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
        @arch.exception_codes.select do |ecode|
          # define every extension version except this one (and compatible),
          # and test if the condition can be satisfied
          ecode.defined_by_condition.satisfied_by_ext_req?(@arch.extension_requirement(@name, "~> #{@version_spec}"), include_requirements: false) ||
            ecode.defined_by_condition.satisfiability_depends_on_ext_req?(@arch.extension_requirement(@name, "~> #{@version_spec}"))
        end
    end

    # the list of interrupt codes that require this extension version (or a compatible version)
    # in order to be defined
    sig { returns(T::Array[InterruptCode]) }
    def interrupt_codes
      @interrupt_codes ||=
        @arch.interrupt_codes.select do |icode|
          icode.defined_by_condition.satisfied_by_ext_req?(@arch.extension_requirement(@name, "~> #{@version_spec}"), include_requirements: false) ||
            icode.defined_by_condition.satisfiability_depends_on_ext_req?(@arch.extension_requirement(@name, "~> #{@version_spec}"))
        end
    end

    sig { params(xlens: T::Array[Integer]).returns(T::Array[Csr]) }
    def in_scope_csrs(xlens)
      csrs.select do |csr|
        csr.base.nil? || xlens.include?(csr.base)
      end
    end

    sig { params(xlens: T::Array[Integer]).returns(T::Array[Csr]) }
    def in_scope_instructions(xlens)
      directly_defined_instructions.select do |inst|
        inst.base.nil? || xlens.include?(inst.base)
      end
    end

    sig { returns(ExtensionRequirement) }
    def to_ext_req
      @ext_req ||= @arch.extension_requirement(name, "= #{version_str}")
    end

    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      @h ||=
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

    sig { returns(ExtensionTerm) }
    def to_term
      if @requirements.size == 1
        ExtensionTerm.new(name, @requirements.fetch(0).op, @requirements.fetch(0).version_spec)
      else
        raise "TODO #{self} #{@requirements.size}"
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
    sig { returns(Extension) }
    def extension
      @extension ||= T.must(@arch.extension(@name))
    end

    # create an ExtensionRequirement from YAML
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture
      ).returns(ExtensionRequirement)
    }
    def self.create_from_yaml(yaml, cfg_arch)
      requirements =
        if yaml["version"]
          yaml.fetch("version")
        else
          ">= 0"
        end
      cfg_arch.extension_requirement(yaml.fetch("name"), requirements)
    end

    # given a list of extension versions, return a single extension requirement that covers them
    # if the list is all known versions of an extension, will return the open-ended match ">= 0"
    sig {
      params(
        ext_vers: T::Array[ExtensionVersion]
      ).returns(ExtensionRequirement)
    }
    def self.create_from_ext_vers(ext_vers)
      raise "Must supply at least one extension version" if ext_vers.empty?
      raise "All ext_vers must be from the same extension" unless ext_vers.map(&:name).uniq.size == 1

      # first, get rid of any duplicates
      uniq_ext_vers = ext_vers.uniq
      ext = uniq_ext_vers.fetch(0).ext

      if uniq_ext_vers.size == ext.versions.size
        uniq_ext_vers.fetch(0).arch.extension_requirement(ext.name, ">= 0")
      elsif uniq_ext_vers.size == 1
        uniq_ext_vers.fetch(0).arch.extension_requirement(ext.name, "= #{uniq_ext_vers.fetch(0).version_str}")
      else
        min_ver = T.must(uniq_ext_vers.min)
        lower_bound = uniq_ext_vers.fetch(0).arch.extension_requirement(ext.name, ">= #{min_ver.version_str}")
        if lower_bound.satisfying_versions.size == uniq_ext_vers.size && uniq_ext_vers.all? { |ext_ver| lower_bound.satisfied_by?(ext_ver) }
          lower_bound
        else
          max_ver = T.must(uniq_ext_vers.max)
          upper_bound = uniq_ext_vers.fetch(0).arch.extension_requirement(ext.name, "<= #{max_ver.version_str}")
          if upper_bound.satisfying_versions.size == uniq_ext_vers.size && uniq_ext_vers.all? { |ext_ver| upper_bound.satisfied_by?(ext_ver) }
            upper_bound
          else
            range = uniq_ext_vers.fetch(0).arch.extension_requirement(ext.name, [">= #{min_ver.version_str}", "<= #{max_ver.version_str}"])
            if range.satisfying_versions.size == uniq_ext_vers.size && uniq_ext_vers.all? { |ext_ver| range.satisfied_by?(ext_ver) }
              range
            else
              # TODO: this is a complicated one
              raise "TODO: complicated extension requirement creation"
            end
          end
        end
      end
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

      @arch.extension_version(name, @requirements.fetch(0).version_spec.to_s)
    end

    sig {
      params(
        name: String,
        requirements: T.any(String, T::Array[String], RequirementSpec, T::Array[RequirementSpec]),
        arch: ConfiguredArchitecture
      ).void
    }
    def initialize(name, requirements, arch:)
      @name = name.to_s.freeze
      @arch = arch
      @ext = @arch.extension(@name)
      Udb.logger.warn "Could not find extension named '#{@name}'" if @ext.nil?

      @requirements =
        if @ext.nil?
          []
        else
          case requirements
          when Array
            if requirements.empty?
              [RequirementSpec.new(">= 0")]
            else
              if requirements.fetch(0).is_a?(String)
                requirements.map { |r| RequirementSpec.new(r) }
              else
                requirements
              end
            end
          when String
            [RequirementSpec.new(requirements)]
          when RequirementSpec
            [requirements]
          else
            T.absurd(requirements)
          end
        end.freeze
    end
    private_class_method :new

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

    # if self is met, then the requirements of the implemented (and satisfying) version
    # must be must
    #
    # thus, the requirements condition for self overall is exactly one of the version requirements
    sig { returns(AbstractCondition) }
    def requirements_condition
      @requirements_condition ||=
        begin
          version_reqs = satisfying_versions.map do |ext_ver|
            unless ext_ver.requirements_condition.empty?
              [ext_ver, ext_ver.requirements_condition]
            end
          end.compact.to_h
          if version_reqs.empty?
            AlwaysTrueCondition.new(@arch)
          elsif version_reqs.size == 1
            version_reqs.values.fetch(0)
          else
            # exaclty one of the requirements must be met
            # also add an implication for each version so they don't mix/match
            Condition.disjunction(version_reqs.values, @arch) & Condition.conjunction(version_reqs.map { |ext_ver, req| ext_ver.to_condition.implies(req) }, @arch)
          end
        end
    end

    # return a Condition representing this ExtensionRequirement
    sig { returns(Condition) }
    def to_condition
      @condition ||=
        Condition.new(condition_hash, @arch)
    end

    # return the UDB YAML representation of a Condition representing this ExtensionRequirement
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

    # return the list of parameters that are defined when ExtensionRequirement is met (and nothing else)
    sig { returns(T::Array[T.any(Parameter, ParameterWithValue)]) }
    def params
      @params ||=
        extension.params.select do |param|
          (param.defined_by_condition & to_condition).satisfiable?
        end
    end

    # return the list of parameters that are defined when preconditions of the ExtensionRequirement are met (and nothing else)
    def implied_params
      @params ||= extension.params.select do |p|
        param_defined = p.defined_by_condition
        requirement_met = requirements_condition

        (-param_defined & requirement_met).unsatisfiable?
      end
    end

    # list of instructions directly implemented by *any* satisfying version
    sig { returns(T::Array[Instruction]) }
    def instructions
      @instructions ||=
        extension.instructions.select do |inst|
          (inst.defined_by_condition & to_condition).satisfiable?
        end
    end

    # @api private
    sig { returns(T::Set[Instruction]) }
    def instructions_set
      @instructions_set ||= Set.new(instructions)
    end

    # @return the list of instructions implemented *indirectly* by *any satisfying version* of this requirement because
    # a requirement of this requirement directly defines the instruction
    #
    # For example, the "C" extension implies c.addi because c.addi is directly defined by Zca and C
    # requires Zca to be implemented
    #
    # This list may be empty
    sig { returns(T::Array[Instruction]) }
    def implied_instructions
      @implied_instructions ||=
        begin
          pb =
            Udb.create_progressbar(
              "Finding implied instructions for #{self} [:bar] :current/:total",
              total: @arch.instructions.size,
              clear: true
            )
          @arch.instructions.select do |i|
            pb.advance

            next if instructions_set.include?(i)

            (-i.defined_by_condition & to_condition).unsatisfiable?
          end
        end
    end

    # @api private
    sig { returns(T::Set[Instruction]) }
    def implied_instructions_set
      @implied_instructions_set ||= Set.new(implied_instructions)
    end

    # return all instructions that must be implemented when self is satisfied. This includes
    # instructions implied through a requirement of self (transitively)
    sig { returns(T::Array[Instruction]) }
    def all_instructions_that_must_be_implemented
      @all_instructions_that_must_be_implemented ||= instructions + implied_instructions
    end

    # @return [Array<Csr>] List of CSRs defined by any extension satisfying this requirement
    sig { returns(T::Array[Csr]) }
    def csrs
      @csrs ||=
        extension.csrs.select do |csr|
          (csr.defined_by_condition & to_condition).satisfiable?
        end
    end

    sig { returns(T::Array[Idl::FunctionDefAst]) }
    def reachable_functions
      return @reachable_functions unless @reachable_functions.nil?

      funcs = T.let([], T::Array[Idl::FunctionDefAst])

      bar = Udb.create_progressbar("Finding reachable functions for #{name} [:bar] :current/:total", total: instructions.size + csrs.size)

      instructions.each do |inst|
        bar.advance
        funcs += inst.reachable_functions(32) if inst.defined_in_base?(32)
        funcs += inst.reachable_functions(64) if inst.defined_in_base?(64)
      end

      csrs.each do |csr|
        bar.advance
        funcs += csr.reachable_functions
      end

      @reachable_functions = funcs.uniq
    end

    # @return [ExtensionVersion] The minimum extension version that satifies this extension requirement.
    #                            If none, raises an error.
    sig { returns(ExtensionVersion) }
    def min_satisfying_ext_ver
      if satisfying_versions.empty?
        Udb.logger.error "Extension requirement '#{self}' cannot be met by any available extension version. Available versions:"
        if @ext.versions.empty?
          Udb.logger.error "  none"
        else
          @ext.versions.each do |ext_ver|
            Udb.logger.error "  #{ext_ver}"
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
        Udb.logger.error "Extension requirement '#{self}' cannot be met by any available extension version. Available versions:"
        if @ext.versions.empty?
          Udb.logger.error "  none"
        else
          @ext.versions.each do |ext_ver|
            Udb.logger.error "  #{ext_ver}"
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
