# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "minisat"
require "sorbet-runtime"

require "idlc/symbol_table"
require "udb/logic"

require "udb/idl/condition_to_udb"

module Udb

  class DatabaseObject; end
  class TopLevelDatabaseObject < DatabaseObject; end
  class Extension < TopLevelDatabaseObject; end
  class ExtensionVersion; end
  class ExtensionRequirement; end
  class AbstractCondition; end

  # an ExtensionRequirement that only applies when cond is true
  class ConditionalExtensionRequirement < T::Struct
    prop :ext_req, ExtensionRequirement
    prop :cond, AbstractCondition
  end

  # an ExtensionVersion that only applies when cond is true
  class ConditionalExtensionVersion < T::Struct
    prop :ext_ver, ExtensionVersion
    prop :cond, AbstractCondition
  end

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
    sig { returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      symtab = @cfg_arch.symtab.global_clone
      h = @ast.to_udb_h(symtab)
      symtab.release

      h
    end

    # convert into a pure UDB condition
    sig { returns(String) }
    def to_yaml
      YAML.dump(to_h)
    end

    sig { params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      Condition.new(to_h, @cfg_arch).to_logic_tree(expand:)
    end
  end

  # return type for satisfied_by functions
  class SatisfiedResult < T::Enum
    enums do
      Yes = new
      No = new
      Maybe = new
    end
  end.freeze
  SatisfiedResult::Yes.freeze
  SatisfiedResult::No.freeze
  SatisfiedResult::Maybe.freeze

  # a condition
  class AbstractCondition
    extend T::Sig
    extend T::Helpers
    abstract!

    # returns true if this condition is always true or always false
    # (does not depend on extensions or parameters)
    sig { abstract.returns(T::Boolean) }
    def empty?; end

    # convert to the underlying LogicNode-based tree
    sig { abstract.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true); end

    # is this condition satisfiable?
    sig { returns(T::Boolean) }
    def satisfiable?
      to_logic_tree(expand: true).satisfiable?
    end

    # is is possible for this condition and other to be simultaneously true?
    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def compatible?(other)
      LogicNode.new(LogicNodeType::And, [to_logic_tree(expand: true), other.to_logic_tree(expand: true)]).satisfiable?
    end

    # @return if the condition is, possibly is, or is definately not satisfied by cfg_arch
    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch); end

    # If ext_req is *not* satisfied, is condition satisfiable?
    sig { abstract.params(_ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(_ext_req); end

    # for the given config arch, is condition satisfiable?
    sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_satisfied_by_cfg_arch?(cfg_arch)
      satisfied_by_cfg_arch?(cfg_arch) != SatisfiedResult::No
    end

    # is this condition logically equivalent to other?
    # this is true logical equivalence, not just syntatic equivalence, e.g.:
    #  (a || a) is equivalent to (a)
    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def equivalent?(other)
      to_logic_tree(expand: true).equivalent?(other.to_logic_tree(expand: true))
    end

    # true if the condition references a parameter at some point
    sig { abstract.returns(T::Boolean) }
    def has_param?; end

    # true if the condition references an extension requirements at some point
    sig { abstract.returns(T::Boolean) }
    def has_extension_requirement?; end

    # convert condition into UDB-compatible hash
    sig { abstract.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h; end

    # convert condition into UDB-compatible YAML string
    sig { overridable.returns(String) }
    def to_yaml
      YAML.dump(to_h)
    end

    # convert condition into valid IDL
    sig { abstract.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch); end

    # condition in prose
    sig { abstract.returns(String) }
    def to_s_pretty; end

    # assuming that the condition represents an extension dependency,
    # return the specified extensions along with the condition under
    # which they apply
    #
    # specifically, this returns the complete list of positive terms (terms that are not negated
    # in solution) of requirements,
    # along with a conditionthat must hold for condition to be satisfied when the positive term is met
    #
    # @example
    #   given the equation (representing implications of the "C" extension):
    #      Zca@1.0.0 AND (!F OR Zcf@1.0.0) AND (!D OR Zcd@1.0.0)
    #
    #   return:
    #     [
    #        { ext_req: Zca@1.0.0, cond: True },
    #        { ext_req: Zcf@1.0.0, cond: !F },
    #        { ext_req: Zcd@1.0.0, cond: !D }
    #     ]
    #
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
    sig { abstract.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extensions; end
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
        Condition.new({ "allOf" => conds.map(&:to_h) }, cfg_arch)
      end
    end

    sig {
      params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
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
    def empty? = @yaml == true || @yaml == false || @yaml.empty?

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      if expand
        @logic_tree_expanded ||= to_logic_tree_helper(@yaml, expand: true)
      else
        @logic_tree ||= to_logic_tree_helper(@yaml, expand: false)
      end
    end

    sig {
      overridable
      .params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
        expand: T::Boolean
      ).returns(LogicNode)
    }
    def to_logic_tree_helper(yaml, expand: true)
      if yaml.is_a?(TrueClass)
        LogicNode.new(LogicNodeType::True, [])
      elsif yaml.is_a?(FalseClass)
        LogicNode.new(LogicNodeType::False, [])
      elsif yaml.key?("allOf")
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
        antecedent = to_logic_tree_helper(yaml.fetch("if"), expand:)
        consequent = to_logic_tree_helper(yaml.fetch("then"), expand:)
        LogicNode.new(LogicNodeType::If, [antecedent, consequent])
      elsif yaml.key?("extension")
        ExtensionCondition.new(yaml["extension"], @cfg_arch).to_logic_tree(expand:)
      elsif yaml.key?("param")
        ParamCondition.new(yaml["param"], @cfg_arch).to_logic_tree(expand:)
      elsif yaml.key?("idl()")
        IdlCondition.new(yaml, @cfg_arch, input_file: nil, input_line: nil).to_logic_tree(expand:)
      else
        raise "Unexpected: #{yaml.keys}"
      end
    end
    private :to_logic_tree_helper

    sig { override.returns(T::Boolean) }
    def has_param?
      to_logic_tree(expand: true).terms.any? { |t| t.is_a?(ParameterTerm) }
    end

    sig { override.returns(T::Boolean) }
    def has_extension_requirement?
      to_logic_tree(expand: true).terms.any? { |t| t.is_a?(ExtensionVersion) }
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
        implemented_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionTerm)
            satisfied = cfg_arch.transitive_implemented_extension_versions.any? do |ext_ver|
              term.to_ext_req(cfg_arch).satisfied_by?(ext_ver)
            end
            satisfied ? SatisfiedResult::Yes : SatisfiedResult::No
          else
            term.eval(cfg_arch.symtab)
          end
        end
        if to_logic_tree(expand: true).eval_cb(implemented_ext_cb) == SatisfiedResult::Yes
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
        possible_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionTerm)
            if cfg_arch.possible_extension_versions.any? { |cfg_ext_ver| term.to_ext_req(cfg_arch).satisfied_by?(cfg_ext_ver) }
              SatisfiedResult::Yes
            else
              SatisfiedResult::No
            end
          else
            term.eval(cfg_arch.symtab)
          end
        end

        if to_logic_tree(expand: true).eval_cb(mandatory_ext_cb) == SatisfiedResult::Yes
          SatisfiedResult::Yes
        elsif to_logic_tree(expand: true).eval_cb(possible_ext_cb) == SatisfiedResult::Yes
          SatisfiedResult::Maybe
        else
          SatisfiedResult::No
        end
      else
        # unconfig. Can't really say anthing
        SatisfiedResult::Maybe
      end
    end

    sig { override.params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req)
      to_logic_tree(expand: true).satisfiability_depends_on_ext_req?(ext_req)
    end

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      T.cast(to_logic_tree(expand: false).to_h, T::Hash[String, T.untyped])
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch)
      idl = to_logic_tree(expand: false).to_idl(cfg_arch)
      if to_logic_tree(expand: false).type == LogicNodeType::If
        idl
      else
        "-> #{idl};"
      end
    end

    # return the condition in a nice, human-readable form
    sig { override.returns(String) }
    def to_s_pretty
      to_logic_tree(expand: false).to_s_pretty
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extensions
      # strategy:
      #   1. convert to product-of-sums.
      #   2. for each product, find the positive terms. These are the implications
      #   3. for each product, find the negative terms. These are the "conditions" when the positive terms apply

      @implications ||= begin
        reqs = []
        pos = to_logic_tree(exapnd: true).minimize(LogicNode::CanonicalizationType::ProductOfSums)
        pos.children.each do |child|
          child = T.cast(child, LogicNode)
          if child.type == LogicNodeType::Term
            reqs << \
              ExtensionRequirementList::ConditionalExtensionVersion.new(
                ext_ver: T.cast(child.children.fetch(0), ExtensionTerm).to_ext_ver(@cfg_arch),
                cond: AlwaysTrueCondition.new
              )
          elsif child.children.all? { |child| T.cast(child, LogicNode).type == LogicNodeType::Not }
            # there is no positive term, so do nothing
          else
            raise "?" unless child.type == LogicNodeType::And

            positive_terms = child.children.select { |and_child| T.cast(and_child, LogicNode).type == LogicNodeType::Term }
            negative_terms =
              child.children.select { |and_child| T.cast(and_child, LogicNode).type == LogicNodeType::Not }
                .map { |neg_term| T.cast(neg_term, LogicNode).children.fetch(0) }
            positive_terms.each do |pterm|
              reqs << \
                ExtensionRequirementList::ConditionalExtensionVersion.new(
                  ext_ver: T.cast(T.cast(pterm, LogicNode).children.fetch(0), ExtensionTerm).to_ext_ver(@cfg_arch),
                  cond: LogicCondition.new(
                    T.cast(negative_terms.size == 1 ? negative_terms.fetch(0) : LogicNode.new(LogicNodeType::Or, negative_terms), LogicNode),
                    @cfg_arch
                  )
                )
            end
            reqs
          end
        end
        reqs
      end
    end
  end

  class LogicCondition < Condition

    sig { params(logic_node: LogicNode, cfg_arch: ConfiguredArchitecture).void }
    def initialize(logic_node, cfg_arch)
      @logic_node = logic_node
      @cfg_arch = cfg_arch
    end

    sig { override.returns(T::Boolean) }
    def empty? = @logic_node.type == LogicNodeType::True || @logic_node.type == LogicNodeType::False

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true) = @logic_node
  end

  class AlwaysTrueCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= {}
      @logic_tree[expand] ||= LogicNode.new(LogicNodeType::True, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = true

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      true
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::Yes

    sig { override.params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> true;"

    sig { override.returns(String) }
    def to_s_pretty
      "always"
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extensions = []
  end

  class AlwaysFalseCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= {}
      @logic_tree[expand] ||= LogicNode.new(LogicNodeType::False, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = false

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      false
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::No

    sig { override.params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> false;"

    sig { override.returns(String) }
    def to_s_pretty
      "never"
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extensions = []
  end

  class ParamCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig { params(yaml: T::Hash[String, T.untyped], expand: T::Boolean).returns(LogicNode) }
    def to_param_logic_tree_helper(yaml, expand:)
      if yaml.key?("name")
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new(yaml)])
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y, expand:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml.fetch("anyOf").map { |y| to_param_logic_tree_helper(y, expand:) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml.fetch("oneOf").map { |y| to_param_logic_tree_helper(y, expand:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::Not,
          [
            LogicNode.new(LogicNodeType::Or, yaml.fetch("noneOf").map { |y| to_param_logic_tree_helper(y, expand:) })
          ]
        )
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_param_logic_tree_helper(yaml.fetch("not"), expand:)])
      elsif yaml.key?("if")
        LogicNode.new(LogicNodeType::If,
          [
            Condition.new(yaml.fetch("if"), @cfg_arch).to_logic_tree(expand:),
            to_param_logic_tree_helper(yaml.fetch("then"), expand:)
          ]
        )

      else
        raise "unexpected key #{yaml.keys}"
      end
    end

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= {}
      @logic_tree[expand] ||= to_param_logic_tree_helper(@yaml, expand:)
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
      @logic_tree ||= {}
      @logic_tree[expand] ||= to_logic_tree_helper(@yaml, expand:)
    end

    # convert an ExtensionRequirement into a logic tree
    # if expand is true, also add requirements of the extension and all satisfing versions to the tree
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture,
        expand: T::Boolean
      ).returns(LogicNode)
    }
    def ext_req_to_logic_node(yaml, cfg_arch, expand: true)
      ext_req = ExtensionRequirement.create(yaml, cfg_arch)

      if !expand
        LogicNode.new(LogicNodeType::Term, [ext_req.to_term])
      else
        # to expand, we have to split the req into versions and apply version-specific requirements
        nodes = ext_req.satisfying_versions.map do |ext_ver|
          n = LogicNode.new(LogicNodeType::Term, [ext_ver.to_term])
          if !ext_ver.ext.requirements_condition.empty? && !ext_ver.requirements_condition.empty?
            n = LogicNode.new(
              LogicNodeType::And,
              [
                n,
                ext_ver.ext.requirements_condition.to_logic_tree(expand:),  # requirements of the extension
                ext_ver.requirements_condition.to_logic_tree(expand:)       # requirements of the extension version
              ]
            )
          elsif !ext_ver.ext.requirements_condition.empty?
            n = LogicNode.new(
              LogicNodeType::And,
              [
                n,
                ext_ver.ext.requirements_condition.to_logic_tree(expand:)  # requirements of the extension
              ]
            )
          elsif !ext_ver.requirements_condition.empty?
            n = LogicNode.new(
              LogicNodeType::And,
              [
                n,
                ext_ver.requirements_condition.to_logic_tree(expand:)       # requirements of the extension version
              ]
            )
          end
          n
        end
        if nodes.size == 0
          LogicNode.new(LogicNodeType::False, [])
        elsif nodes.size == 1
          nodes.fetch(0)
        else
          LogicNode.new(LogicNodeType::Or, nodes)
        end
      end
    end
    private :ext_req_to_logic_node

    sig { override.params(yaml: T.any(T::Hash[String, T.untyped], T::Boolean), expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree_helper(yaml, expand: true)
      if !yaml.is_a?(Hash)
        if yaml == true
          LogicNode.new(LogicNodeType::True, [])
        elsif yaml == false
          LogicNode.new(LogicNodeType::False, [])
        else
          T.absurd(yaml)
        end
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::Or, yaml["noneOf"].map { |node| to_logic_tree_helper(node, expand:) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node, expand:) })
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
      @logic_tree ||= {}
      @logic_tree[expand] ||= constraint.to_logic_tree(expand:)
    end

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h = constraint.to_h

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = @yaml.fetch("idl()")

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
        if (ext_req.requirement_specs.size == 1) && (ext_req.requirement_specs.fetch(0).op == "=")
          ext_ver = ext_req.satisfying_versions.fetch(0)
          @implied_extension_versions << ConditionalExtensionVersion.new(ext_ver:, cond: cond_ext_req.cond)
        end
      end
      @implied_extension_versions
    end
  end
end
