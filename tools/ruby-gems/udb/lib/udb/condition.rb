# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "minisat"
require "sorbet-runtime"

require "idlc/symbol_table"
require "udb/logic"
require "udb/obj/extension"

require "udb/idl/condition_to_udb"

module Udb

  class ExtensionVersion; end

  # wrapper around an IDL function containing constraints
  class Constraint
    extend T::Sig

    sig { returns(T.nilable(String)) }
    attr_reader :reason

    sig {
      params(
        idl: String,
        input_file: T.nilable(Pathname),
        input_line: T.nilable(Integer),
        cfg_arch: ConfiguredArchitecture,
        reason: T.nilable(String)
      ).void
    }
    def initialize(idl, input_file:, input_line:, cfg_arch:, reason: nil)
      @cfg_arch = cfg_arch
      symtab = cfg_arch.symtab.global_clone
      @ast = @cfg_arch.idl_compiler.compile_constraint(idl, symtab)
      symtab.release
      @reason = reason
    end

    sig { params(symtab: Idl::SymbolTable).returns(T::Boolean) }
    def eval(symtab)
      @ast.satisfied?(symtab)
    end

    # convert into a pure UDB condition
    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      symtab = @cfg_arch.symtab.global_clone
      yaml = @ast.to_udb_h(symtab)
      symtab.release

      yaml
    end

    # convert into a pure UDB condition
    sig { returns(String) }
    def to_yaml
      YAML.dump(to_h)
    end

    sig { returns(LogicNode) }
    def to_logic_tree
      Condition.new(to_h, @cfg_arch).to_logic_tree
    end
  end

  # return type for satisfied_by functions
  class SatisfiedResult < T::Enum
    enums do
      Yes = new
      No = new
      Maybe = new
    end
  end

  class AbstractCondition
    extend T::Sig
    extend T::Helpers
    abstract!

    sig { abstract.returns(T::Boolean) }
    def empty?; end

    sig { abstract.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true); end

    sig { returns(T::Boolean) }
    def satisfiable?
      to_logic_tree.satisfiable?
    end

    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def compatible?(other)
      LogicNode.new(LogicNodeType::And, [to_logic_tree, other.to_logic_tree]).satisfiable?
    end

    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch); end

    sig { abstract.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(SatisfiedResult) }
    def satisfied_by_ext_ver_list?(_ext_ver_list); end

    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch); end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_satisfied_by_cfg_arch?(cfg_arch) = could_be_true?(cfg_arch)

    sig { params(ext_ver_list: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def could_be_satisfied_by_ext_ver_list?(ext_ver_list)
      [SatisfiedResult::Yes, SatisfiedResult::Maybe].include?(satisfied_by_ext_ver_list?(ext_ver_list))
    end

    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def equivalent?(other)
      to_logic_tree.equivalent?(other.to_logic_tree)
    end

    sig { abstract.returns(T::Boolean) }
    def has_param?; end

    sig { abstract.returns(T::Boolean) }
    def has_extension_requirement?; end

    sig { abstract.returns(T::Hash[String, T.untyped]) }
    def to_h; end

    sig { overridable.returns(String) }
    def to_yaml
      YAML.dump(to_h)
    end

    sig { abstract.returns(String) }
    def to_idl; end
  end

  # represents a condition in the UDB data, which could include conditions involving
  # extensions and/or parameters
  class Condition < AbstractCondition
    extend T::Sig
    extend T::Helpers

    sig {
      params(
        cfg_arch: ConfiguredArchitecture,
        conds: T::Array[T.all(AbstractCondition, Object)]
      )
      .returns(AbstractCondition)
    }
    def self.join(cfg_arch, conds)
      if conds.size == 0
        AlwaysTrueCondition.new
      elsif conds.size == 1
        conds.fetch(0)
      else
        Condition.new({ "allOf": conds.map(&:to_h) }, cfg_arch)
      end
    end

    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture,
        input_file: T.nilable(Pathname),
        input_line: T.nilable(Integer)
      )
      .void
    }
    def initialize(yaml, cfg_arch, input_file: nil, input_line: nil)
      @yaml = yaml
      @cfg_arch = cfg_arch
      @input_file = input_file
      @input_line = input_line
    end

    sig { override.returns(T::Boolean) }
    def empty? = @yaml.empty?

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= to_logic_tree_helper(@yaml, expand:)
    end

    sig {
      overridable
      .params(
        yaml: T::Hash[String, T.untyped],
        expand: T::Boolean
      ).returns(LogicNode)
    }
    def to_logic_tree_helper(yaml, expand: true)
      if yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::None, yaml["noneOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"), expand:)])
      elsif yaml.key?("if")
        LogicNode.new(LogicNodeType::If, [to_logic_tree_helper(yaml.fetch("if"), expand:), to_logic_tree_helper(yaml.fetch("then"), expand:)])
      elsif yaml.key?("extension")
        ExtensionCondition.new(yaml["extension"], @cfg_arch).to_logic_tree
      elsif yaml.key?("param")
        ParamCondition.new(yaml["param"], @cfg_arch).to_logic_tree
      elsif yaml.key?("idl()")
        IdlCondition.new(yaml, @cfg_arch, input_file: nil, input_line: nil).to_logic_tree
      else
        raise "Unexpected: #{yaml.keys}"
      end
    end
    private :to_logic_tree_helper

    sig { override.returns(T::Boolean) }
    def has_param?
      to_logic_tree.terms.any? { |t| t.is_a?(ParameterTerm) }
    end

    sig { override.returns(T::Boolean) }
    def has_extension_requirement?
      to_logic_tree.terms.any? { |t| t.is_a?(ExtensionVersion) }
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(cfg_arch)
      r = satisfied_by_cfg_arch?(cfg_arch)
      r == SatisfiedResult::Yes || r == SatisfiedResult::Maybe
    end

    EvalCallbackType = T.type_alias { T.proc.params(term: T.any(ExtensionTerm, ParameterTerm)).returns(SatisfiedResult) }
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def make_cb_proc(&blk)
      blk
    end
    private :make_cb_proc

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(cfg_arch)
      if cfg_arch.fully_configured?
        if to_logic_tree.eval(cfg_arch, cfg_arch.symtab, cfg_arch.transitive_implemented_extension_versions) == SatisfiedResult::Yes
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      elsif cfg_arch.partially_configured?
        mandatory_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionTerm)
            if cfg_arch.mandatory_extension_reqs.any? { |cfg_ext_req| cfg_ext_req.satisfied_by?(term.to_ext_ver(cfg_arch)) }
              SatisfiedResult::Yes
            else
              SatisfiedResult::No
            end
          else
            term.eval(cfg_arch.symtab)
          end
        end

        if to_logic_tree.eval_cb(mandatory_ext_cb) == SatisfiedResult::Yes
          SatisfiedResult::Yes
        elsif to_logic_tree.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions) == SatisfiedResult::Yes
          SatisfiedResult::Maybe
        else
          SatisfiedResult::No
        end
      else
        # unconfig. Can't really say anthing
        SatisfiedResult::Maybe
      end
    end

    sig { override.params(ext_ver_list: T::Array[ExtensionVersion]).returns(SatisfiedResult) }
    def satisfied_by_ext_ver_list?(ext_ver_list)
      to_logic_tree.eval(@cfg_arch, @cfg_arch.symtab, ext_ver_list)
    end

    sig { override.returns(T::Hash[String, T.untyped]) }
    def to_h
      T.cast(to_logic_tree.to_h, T::Hash[String, T.untyped])
    end

    sig { override.returns(String) }
    def to_idl
      to_logic_tree.to_idl
    end

  end

  class AlwaysTrueCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= LogicNode.new(LogicNodeType::True, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = true

    sig { override.returns(T::Hash[String, T.untyped]) }
    def to_h
      {
        "constraint" => {
          "if" => true,
          "then" => true
        }
      }
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::Yes

    sig { override.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(SatisfiedResult) }
    def satisfied_by_ext_ver_list?(_ext_ver_list) = SatisfiedResult::Yes

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch) = true

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.returns(String) }
    def to_idl = "true"
  end

  class AlwaysFalseCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= LogicNode.new(LogicNodeType::False, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = false

    sig { override.returns(T::Hash[String, T.untyped]) }
    def to_h
      {
        "constraint" => {
          "if" => true,
          "then" => false
        }
      }
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::No

    sig { override.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(SatisfiedResult) }
    def satisfied_by_ext_ver_list?(_ext_ver_list) = SatisfiedResult::No

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.returns(String) }
    def to_idl = "false"
  end

  class ParamCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig { params(yaml: T::Hash[String, T.untyped]).returns(LogicNode) }
    def to_param_logic_tree_helper(yaml)
      if yaml.key?("name")
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new(yaml)])
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::Not,
          [
            LogicNode.new(LogicNodeType::Or, yaml.fetch("noneOf").map { |y| to_param_logic_tree_helper(y) })
          ]
        )
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_param_logic_tree_helper(yaml.fetch("not"))])
      elsif yaml.key?("if")
        LogicNode.new(LogicNodeType::If,
          [
            Condition.new(yaml.fetch("if"), @cfg_arch).to_logic_tree,
            to_param_logic_tree_helper(yaml.fetch("then"))
          ]
        )

      else
        raise "unexpected key #{yaml.keys}"
      end
    end

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= to_param_logic_tree_helper(@yaml)
    end
  end

  class ExtensionCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= to_logic_tree_helper(@yaml, expand:)
    end

    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture,
        expand: T::Boolean
      ).returns(LogicNode)
    }
    def ext_req_to_logic_node(yaml, cfg_arch, expand: true)
      ext_req = ExtensionRequirement.create(yaml, cfg_arch)

      n =
        if ext_req.satisfying_versions.size == 1
          LogicNode.new(LogicNodeType::Term, [ext_req.satisfying_versions.fetch(0).to_term])
        else
          LogicNode.new(LogicNodeType::Or, ext_req.satisfying_versions.map { |v| LogicNode.new(LogicNodeType::Term, [v.to_term]) })
        end

      if expand
        c = ext_req.extension.conflicts_condition
        unless c.empty?
          c = LogicNode.new(LogicNodeType::Not, [Condition.new(ext_req.extension.data["conflicts"], @cfg_arch).to_logic_tree])
          n = LogicNode.new(LogicNodeType::And, [c, n])
        end

        ext_req.satisfying_versions.each do |ext_ver|
          ext_ver.implications.each do |implication|
            implied_ext_ver = implication.ext_ver
            implied_cond = implication.cond
            implied_ext_req = { "name" => implied_ext_ver.name, "version" => "= #{implied_ext_ver.version_str}" }
            if implied_cond.empty?
              # convert to an ext_req
              n = LogicNode.new(LogicNodeType::And, [n, ext_req_to_logic_node(implied_ext_req, cfg_arch, expand:)])
            else
              # conditional
              # convert to an ext_req
              cond_node = implied_cond.to_logic_tree(expand:)
              cond = LogicNode.new(LogicNodeType::If, [cond_node, ext_req_to_logic_node(implied_ext_req, cfg_arch, expand:)])
              n = LogicNode.new(LogicNodeType::And, [n, cond])
            end
          end
        end
      end

      n
    end
    private :ext_req_to_logic_node

    sig { override.params(yaml: T::Hash[String, T.untyped], expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree_helper(yaml, expand: true)
      if yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::Or, yaml["noneOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"), expand:)])
      elsif yaml.key?("name")
        ext_req_to_logic_node(yaml, @cfg_arch, expand:)
      else
        raise "unexpected key #{yaml.keys}"
      end
    end
    private :to_logic_tree_helper
  end

  class IdlCondition < Condition

    sig { returns(String) }
    def reason = @yaml.fetch("reason")

    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture,
        input_file: T.nilable(Pathname),
        input_line: T.nilable(Integer)
      )
      .void
    }
    def initialize(yaml, cfg_arch, input_file:, input_line:)
      super(yaml, cfg_arch, input_file:, input_line:)

      raise "missing required key" unless @yaml.key?("idl()")
    end

    sig { returns(Constraint) }
    def constraint
      @constraint ||= Constraint.new(
          @yaml.fetch("idl()"),
          input_file: @input_file,
          input_line: @input_line,
          cfg_arch: @cfg_arch
        )
    end

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= constraint.to_logic_tree
    end

    sig { override.returns(T::Hash[String, T.untyped]) }
    def to_h = constraint.to_h

    sig { override.returns(String) }
    def to_idl = @yaml.fetch("idl()")

  end

  # represents a `requires:` entry for an extension version
  # something is implied if it points to a single extension version, e.g.:
  #
  #  requires:
  #    extension:
  #      name: A
  #      version: = 1.0.0   # <- this is an implication
  #
  # The list of implied extensions can be conditional, for example:
  #
  # requires:
  #   extension:
  #     allOf:
  #       - name: Zca
  #         version: "1.0.0"
  #       - if:
  #           extension:
  #             name: F
  #             version: ~> 2.2
  #         then:
  #           name: Zcf
  #           version: "1.0.0"
  #       - if:
  #           extension:
  #             name: D
  #             version: ~> 2.2
  #         then:
  #           name: Zcd
  #           version: "1.0.0"
  #


  # a conditional list of extension requirements
  class ExtensionRequirementList
    extend T::Sig

    class ConditionalExtensionVersion < T::Struct
      prop :ext_ver, ExtensionVersion
      prop :cond, AbstractCondition
    end

    class ConditionalExtensionRequirement < T::Struct
      prop :ext_req, ExtensionRequirement
      prop :cond, AbstractCondition
    end

    class ParseState < T::Enum
      enums do
        Condition = new
        ExtensionCondition = new
      end
    end

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      @yaml = yaml
      @cfg_arch = cfg_arch
      @list = T.let(nil, T.nilable(T::Array[ConditionalExtensionRequirement]))
      @implied_extension_versions = T.let(nil, T.nilable(T::Array[ConditionalExtensionVersion]))
    end

    sig { params(yaml: T::Hash[String, T.untyped]).returns(ConditionalExtensionRequirement) }
    def make_cond_ext_req(yaml)
      ext_req = ExtensionRequirement.create(yaml, @cfg_arch)
      cond =
        if yaml.key?("when")
          Condition.new(yaml.fetch("when"), @cfg_arch)
        else
          AlwaysTrueCondition.new
        end
      ConditionalExtensionRequirement.new(ext_req:, cond:)
    end

    sig { params(yaml: T::Hash[String, T.untyped], l: T::Array[ConditionalExtensionRequirement]).void }
    def do_list(yaml, l)
      if yaml.key?("name")
        l << make_cond_ext_req(yaml)
      elsif yaml.key?("allOf")
        yaml.fetch("allOf").each { |item| do_list(item, l) }
      else
        raise "unexpected key #{yaml.keys}"
      end
    end

    sig { returns(T::Array[ConditionalExtensionRequirement]) }
    def list
      return @list unless @list.nil?

      @list = []
      do_list(@yaml, @list)
      @list
    end

    sig { returns(T::Array[ConditionalExtensionVersion]) }
    def implied_extension_versions
      return @implied_extension_versions unless @implied_extension_versions.nil?

      @implied_extension_versions = []
      list.each do |cond_ext_req|
        ext_req = cond_ext_req.ext_req
        puts ext_req.requirement_specs.fetch(0).op
        puts ext_req.requirement_specs.size
        if (ext_req.requirement_specs.size == 1) && (ext_req.requirement_specs.fetch(0).op == "=")
          ext_ver = ext_req.satisfying_versions.fetch(0)
          @implied_extension_versions << ConditionalExtensionVersion.new(ext_ver:, cond: cond_ext_req.cond)
        end
      end
      @implied_extension_versions
    end
  end
end
