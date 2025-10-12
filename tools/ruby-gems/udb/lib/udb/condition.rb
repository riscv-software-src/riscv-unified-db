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

    # @api private
    sig {
      params(
        expand: T::Boolean,
        expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]
      )
      .returns(LogicNode)
    }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      Condition.new(to_h, @cfg_arch).to_logic_tree_internal(expand:, expanded_ext_vers:)
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
    def to_logic_tree(expand:); end

    # @api private
    sig { abstract.params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]).returns(LogicNode) }
    def to_logic_tree_internal(expand:, expanded_ext_vers:); end

    # is this condition satisfiable?
    sig { returns(T::Boolean) }
    def satisfiable?
      to_logic_tree(expand: true).satisfiable?
    end

    # is is possible for this condition and other to be simultaneously true?
    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def compatible?(other)
      LogicNode.new(
        LogicNodeType::And,
        [
          to_logic_tree(expand: true),
          other.to_logic_tree(expand: true)
        ]
      ).satisfiable?
    end

    # @return if the condition is, possibly is, or is definately not satisfied by cfg_arch
    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch); end

    # partially evaluate by replacing any known parameter terms with true/false, and returning
    # a new condition
    sig { abstract.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(AbstractCondition) }
    def partially_evaluate_for_params(cfg_arch, expand:); end

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

    # condition as an equation
    sig { abstract.returns(String) }
    def to_s; end

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
    def implied_extension_requirements; end
  end

  module ConvertibleToLogicNode
    extend T::Sig

    sig { params(tree: LogicNode, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]).void }
    def expand_ext_vers_in_logic_tree(tree, expanded_ext_vers:)
      terms_to_check = tree.terms
      expansion_size_pre = expanded_ext_vers.size

      Kernel.loop do
        next_terms_to_check = []
        terms_to_check.each do |term|
          next unless term.is_a?(ExtensionTerm)
          ext_req = term.to_ext_req(@cfg_arch)

          ext_req.satisfying_versions.each do |ext_ver|
            next if expanded_ext_vers.include?(ext_ver)
            expanded_ext_vers[ext_ver] = :in_progress

            ext_ver_requirements = ext_ver.requirements_condition.to_logic_tree_internal(expand: true, expanded_ext_vers:)
            ext_requirements = ext_ver.ext.requirements_condition.to_logic_tree_internal(expand: true, expanded_ext_vers:)

            expansion =
              LogicNode.new(LogicNodeType::And, [ext_requirements, ext_ver_requirements])
            expanded_ext_vers[ext_ver] = expansion
            next_terms_to_check.concat expansion.terms
          end
        end

        break if next_terms_to_check.empty? || expanded_ext_vers.size == expansion_size_pre
        terms_to_check = next_terms_to_check.uniq
      end
    end
  end

  # represents a condition in the UDB data, which could include conditions involving
  # extensions and/or parameters
  class Condition < AbstractCondition
    extend T::Sig
    extend T::Helpers
    include ConvertibleToLogicNode

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
    def to_logic_tree(expand:)
      if expand
        @logic_tree_expanded ||=
          begin
            expanded_ext_vers = T.let({}, T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)])
            tree = to_logic_tree_internal(expand:, expanded_ext_vers:)

            if expanded_ext_vers.empty?
              tree
            else
              implications = expanded_ext_vers.map { |ext_ver, logic_req| LogicNode.new(LogicNodeType::If, [ext_ver.to_condition.to_logic_tree(expand: false), T.cast(logic_req, LogicNode)]) }
              LogicNode.new(LogicNodeType::And, [tree] + implications)
            end
          end
      else
        @logic_tree_unexpanded ||= to_logic_tree_helper(@yaml, expand:, expanded_ext_vers: {})
      end
    end

    # @api private
    sig {
      override
      .params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)])
      .returns(LogicNode).checked(:never)
    }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      to_logic_tree_helper(@yaml, expand:, expanded_ext_vers:)
    end

    sig {
      overridable
      .params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
        expand: T::Boolean,
        expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]
      ).returns(LogicNode)
    }
    def to_logic_tree_helper(yaml, expand:, expanded_ext_vers:)
      if yaml.is_a?(TrueClass)
        LogicNode::True
      elsif yaml.is_a?(FalseClass)
        LogicNode::False
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::None, yaml["noneOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"), expand:, expanded_ext_vers:)])
      elsif yaml.key?("if")
        antecedent = to_logic_tree_helper(yaml.fetch("if"), expand:, expanded_ext_vers:)
        consequent = to_logic_tree_helper(yaml.fetch("then"), expand:, expanded_ext_vers:)
        LogicNode.new(LogicNodeType::If, [antecedent, consequent])
      elsif yaml.key?("extension")
        ExtensionCondition.new(yaml["extension"], @cfg_arch).to_logic_tree_internal(expand:, expanded_ext_vers:)
      elsif yaml.key?("param")
        ParamCondition.new(yaml["param"], @cfg_arch).to_logic_tree_internal(expand:, expanded_ext_vers:)
      elsif yaml.key?("idl()")
        IdlCondition.new(yaml, @cfg_arch, input_file: nil, input_line: nil).to_logic_tree_internal(expand:, expanded_ext_vers:)
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

    EvalCallbackType = T.type_alias { T.proc.params(term: TermType).returns(SatisfiedResult) }
    # @api private
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def make_cb_proc(&blk)
      blk
    end

    # return a new condition where any parameter term with a known outcome is replaced with a true/false
    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(Condition) }
    def partially_evaluate_for_params(cfg_arch, expand:)
      cb = make_cb_proc do |term|
        if term.is_a?(ExtensionTerm)
          SatisfiedResult::Maybe
        elsif term.is_a?(ParameterTerm)
          term.partial_eval(cfg_arch.config.param_values)
        elsif term.is_a?(FreeTerm)
          raise "unreachable"
        else
          T.absurd(term)
        end
      end

      Condition.new(
        to_logic_tree(expand:).partial_evaluate(cb).to_h,
        cfg_arch
      )
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(cfg_arch)
      if cfg_arch.fully_configured?
        implemented_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionTerm)
            ext_ver = cfg_arch.implemented_extension_version(term.name)
            next SatisfiedResult::No if ext_ver.nil?
            term.to_ext_req(cfg_arch).satisfied_by?(ext_ver) \
              ? SatisfiedResult::Yes
              : SatisfiedResult::No
          elsif term.is_a?(ParameterTerm)
            term.eval(cfg_arch)
          elsif term.is_a?(FreeTerm)
            raise "unreachable"
          else
            T.absurd(term)
          end
        end
        if to_logic_tree(expand: true).eval_cb(implemented_ext_cb) == SatisfiedResult::Yes
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      elsif cfg_arch.partially_configured?
        cb = make_cb_proc do |term|
          if term.is_a?(ExtensionTerm)
            if cfg_arch.mandatory_extension_reqs.any? { |cfg_ext_req| cfg_ext_req.satisfied_by?(term.to_ext_req(cfg_arch)) }
              SatisfiedResult::Yes
            elsif cfg_arch.possible_extension_versions.any? { |cfg_ext_ver| term.to_ext_req(cfg_arch).satisfied_by?(cfg_ext_ver) }
              SatisfiedResult::Maybe
            else
              SatisfiedResult::No
            end
          elsif term.is_a?(ParameterTerm)
            term.eval(cfg_arch)
          elsif term.is_a?(FreeTerm)
            raise "unreachable"
          else
            T.absurd(term)
          end
        end

        to_logic_tree(expand: true).eval_cb(cb)
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

    sig { override.returns(String) }
    def to_s
      to_logic_tree(expand: false).to_s(format: LogicNode::LogicSymbolFormat::C)
    end

    # return the condition in a nice, human-readable form
    sig { override.returns(String) }
    def to_s_pretty
      to_logic_tree(expand: false).to_s_pretty
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements
      # strategy:
      #   1. convert to product-of-sums.
      #   2. for each product, find the positive terms. These are the implications
      #   3. for each product, find the negative terms. These are the "conditions" when the positive terms apply

      @implications ||= begin
        reqs = []
        pos = to_logic_tree(expand: true).minimize(LogicNode::CanonicalizationType::ProductOfSums)
        if pos.type == LogicNodeType::Term
          reqs << pos
        elsif pos.type == LogicNodeType::Not
          # there are no positive terms, do nothing
        elsif pos.type == LogicNodeType::And
          pos.children.each do |child|
            child = T.cast(child, LogicNode)
            if child.type == LogicNodeType::Term
              term = child.children.fetch(0)
              if term.is_a?(ExtensionTerm)
                reqs << \
                  ConditionalExtensionRequirement.new(
                    ext_req: term.to_ext_req(@cfg_arch),
                    cond: AlwaysTrueCondition.new
                  )
              end
            elsif child.children.all? { |child| T.cast(child, LogicNode).type == LogicNodeType::Not }
              # there is no positive term, so do nothing
            else
              raise "? #{child.type}" unless child.type == LogicNodeType::Or

              positive_terms =
                child.node_children.select { |and_child| and_child.type == LogicNodeType::Term }
              negative_terms =
                child.node_children.select { |and_child| and_child.type == LogicNodeType::Not }
                .map { |neg_term| neg_term.node_children.fetch(0) }
              positive_terms.each do |pterm|
                cond_node =
                  negative_terms.size == 1 \
                    ? negative_terms.fetch(0)
                    : LogicNode.new(LogicNodeType::Or, negative_terms)

                reqs << \
                  ConditionalExtensionRequirement.new(
                    ext_req: T.cast(pterm.children.fetch(0), ExtensionTerm).to_ext_req(@cfg_arch),
                    cond: Condition.new(cond_node.to_h, @cfg_arch)
                  )
              end
              reqs
            end
          end
        end
        reqs
      end
    end

    ###################################################################
    #
    # The following functions can be used to programatically build conditions from
    # other conditions, e.g.,:
    #
    # Condition.not(
    #   Condition.conjunction([cond1, cond1], cfg_arch),
    #   cfg_arch
    # )
    ###################################################################

    # return a new Condition that the logical AND of conditions
    sig {
      params(
        conditions: T::Array[AbstractCondition],
        cfg_arch: ConfiguredArchitecture,
      )
      .returns(AbstractCondition)
    }
    def self.conjunction(conditions, cfg_arch)
      if conditions.empty?
        AlwaysFalseCondition.new
      elsif conditions.size == 1
        conditions.fetch(0)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::And,
            conditions.map { |c| c.to_logic_tree_internal(expand: false, expanded_ext_vers: {}) }
          ).to_h,
          cfg_arch
        )
      end
    end

    # return a new Condition that the logical OR of conditions
    sig {
      params(
        conditions: T::Array[AbstractCondition],
        cfg_arch: ConfiguredArchitecture,
      )
      .returns(AbstractCondition)
    }
    def self.disjunction(conditions, cfg_arch)
      if conditions.empty?
        AlwaysFalseCondition.new
      elsif conditions.size == 1
        conditions.fetch(0)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::Or,
            conditions.map { |c| c.to_logic_tree_internal(expand: false, expanded_ext_vers: {}) }
          ).to_h,
          cfg_arch
        )
      end
    end

    sig {
      params(
        condition: AbstractCondition,
        cfg_arch: ConfiguredArchitecture
      )
      .returns(AbstractCondition)
    }
    def self.not(condition, cfg_arch)
      if condition.is_a?(AlwaysFalseCondition)
        AlwaysTrueCondition.new
      elsif condition.is_a?(AlwaysTrueCondition)
        AlwaysFalseCondition.new
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::Not,
            [condition.to_logic_tree_internal(expand: false, expanded_ext_vers: {})]
          ).to_h,
          cfg_arch
        )
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

    sig { override.params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]).returns(LogicNode) }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      if expand
        @expanded_logic_node ||=
        expand_ext_vers_in_logic_tree(@logic_node, expanded_ext_vers:)
      end

      @logic_node
    end
  end

  class AlwaysTrueCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand:)
      LogicNode::True
    end

    # @api private
    sig {
      override
      .params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)])
      .returns(LogicNode)
    }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      LogicNode::True
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = true

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      true
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::Yes

    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(AbstractCondition) }
    def partially_evaluate_for_params(cfg_arch, expand:) = self

    sig { override.params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> true;"

    sig { override.returns(String) }
    def to_s = "true"

    sig { override.returns(String) }
    def to_s_pretty
      "always"
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements = []
  end

  class AlwaysFalseCondition < AbstractCondition
    extend T::Sig

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand:)
      LogicNode::False
    end

    sig {
      override
      .params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)])
      .returns(LogicNode)
    }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      LogicNode::False
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = false

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h
      false
    end

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::No

    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(AbstractCondition) }
    def partially_evaluate_for_params(cfg_arch, expand:) = self

    sig { override.params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> false;"

    sig { override.returns(String) }
    def to_s = "false"

    sig { override.returns(String) }
    def to_s_pretty
      "never"
    end

    sig { override.returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements = []
  end

  class Condition
    True = AlwaysTrueCondition.new.freeze
    False = AlwaysFalseCondition.new.freeze
  end

  class ParamCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig {
      params(
        yaml: T.any(TrueClass, FalseClass, T::Hash[String, T.untyped]),
        expand: T::Boolean,
        expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]
      )
      .returns(LogicNode)
    }
    def to_param_logic_tree_helper(yaml, expand:, expanded_ext_vers:)
      if yaml == true
        LogicNode::True
      elsif yaml == false
        LogicNode::False
      elsif yaml.key?("name")
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new(yaml)])
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y, expand:, expanded_ext_vers:) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml.fetch("anyOf").map { |y| to_param_logic_tree_helper(y, expand:, expanded_ext_vers:) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml.fetch("oneOf").map { |y| to_param_logic_tree_helper(y, expand:, expanded_ext_vers:) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::Not,
          [
            LogicNode.new(LogicNodeType::Or, yaml.fetch("noneOf").map { |y| to_param_logic_tree_helper(y, expand:, expanded_ext_vers:) })
          ]
        )
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_param_logic_tree_helper(yaml.fetch("not"), expand:, expanded_ext_vers:)])
      elsif yaml.key?("if")
        LogicNode.new(LogicNodeType::If,
          [
            Condition.new(yaml.fetch("if"), @cfg_arch).to_logic_tree_internal(expand:, expanded_ext_vers:),
            to_param_logic_tree_helper(yaml.fetch("then"), expand:, expanded_ext_vers:)
          ]
        )

      else
        raise "unexpected key #{yaml.keys}"
      end
    end

    sig {
      override
      .params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)])
      .returns(LogicNode)
    }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      if expand
        # can't memoize expansion, otherwise we'll miss the expansions!
        to_param_logic_tree_helper(@yaml, expand:, expanded_ext_vers:)
      else
        @logic_tree ||= to_param_logic_tree_helper(@yaml, expand:, expanded_ext_vers:)
      end
    end
  end

  class ExtensionCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig { override.params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]).returns(LogicNode) }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      if expand
        # can't memoize expansion, otherwise we'll miss the expansions!
        to_logic_tree_helper(@yaml, expand:, expanded_ext_vers:)
      else
        @unexpanded_logic_tree ||= to_logic_tree_helper(@yaml, expand:, expanded_ext_vers:)
      end
    end

    # convert an ExtensionRequirement into a logic tree
    # if expand is true, also add requirements of the extension and all satisfing versions to the tree
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture,
        expand: T::Boolean,
        expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]
      ).returns(LogicNode)
    }
    def ext_req_to_logic_node(yaml, cfg_arch, expand:, expanded_ext_vers:)
      ext_req = ExtensionRequirement.create(yaml, cfg_arch)

      if !expand
        LogicNode.new(LogicNodeType::Term, [ext_req.to_term])
      else
        # to expand, we have to split the req into versions and apply version-specific requirements
        # to avoid an infinite loop when an extension appears more than once, we also need to track
        # which expansions have already occurred.
        #
        #  (C)
        #
        #  C   -> Zca && (!D || Zcd) && (!F || Zcf)
        #  Zca -> (((!D || Zcd) && (!F || Zcf)) -> C)

        # any of the satisfying versions will do
        ext_req_cond =
          if ext_req.satisfying_versions.empty?
            LogicNode::False
          elsif ext_req.satisfying_versions.size == 1
            # we've just expanded...don't need to again!
            ext_req.satisfying_versions.fetch(0).to_condition.to_logic_tree_internal(expand: false, expanded_ext_vers:)
          else
            LogicNode.new(
              LogicNodeType::Or,
              ext_req.satisfying_versions.map do |ext_ver|
                # we've just expanded...don't need to again!
                ext_ver.to_condition.to_logic_tree_internal(expand: false, expanded_ext_vers:)
              end
            )
          end

        expand_ext_vers_in_logic_tree(ext_req_cond, expanded_ext_vers:)

        ext_req_cond
      end
    end
    private :ext_req_to_logic_node

    sig {
      override
      .params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
        expand: T::Boolean,
        expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]
      )
      .returns(LogicNode)
    }
    def to_logic_tree_helper(yaml, expand:, expanded_ext_vers:)
      if !yaml.is_a?(Hash)
        if yaml == true
          LogicNode::True
        elsif yaml == false
          LogicNode::False
        else
          T.absurd(yaml)
        end
      else
        if yaml.key?("allOf")
          LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
        elsif yaml.key?("anyOf")
          LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
        elsif yaml.key?("noneOf")
          LogicNode.new(LogicNodeType::Or, yaml["noneOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
        elsif yaml.key?("oneOf")
          LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node, expand:, expanded_ext_vers:) })
        elsif yaml.key?("not")
          LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"), expand:, expanded_ext_vers:)])
        elsif yaml.key?("if")
          LogicNode.new(
            LogicNodeType::If,
            [
              Condition.new(yaml.fetch("if"), @cfg_arch, input_file: @input_file, input_line: @input_line)
                .to_logic_tree_internal(expand:, expanded_ext_vers:),
              to_logic_tree_helper(yaml.fetch("then"), expand:, expanded_ext_vers:)
            ]
          )
        elsif yaml.key?("name")
          ext_req_to_logic_node(yaml, @cfg_arch, expand:, expanded_ext_vers:)
        else
          raise "unexpected key #{yaml.keys}"
        end
      end
    end
    private :to_logic_tree_helper
  end

  class IdlCondition < Condition

    sig { returns(String) }
    def reason = T.cast(@yaml, T::Hash[String, T.untyped]).fetch("reason")

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

      raise "missing required key" unless T.cast(@yaml, T::Hash[String, T.untyped]).key?("idl()")
    end

    sig { returns(Constraint) }
    def constraint
      @constraint ||= Constraint.new(
          T.cast(@yaml, T::Hash[String, T.untyped]).fetch("idl()"),
          input_file: @input_file,
          input_line: @input_line,
          cfg_arch: @cfg_arch
        )
    end

    sig { override.params(expand: T::Boolean, expanded_ext_vers: T::Hash[ExtensionVersion, T.any(Symbol, LogicNode)]).returns(LogicNode) }
    def to_logic_tree_internal(expand:, expanded_ext_vers:)
      if expand
        constraint.to_logic_tree_internal(expand:, expanded_ext_vers:)
      else
        @logic_tree = constraint.to_logic_tree_internal(expand:, expanded_ext_vers:)
      end
    end

    sig { override.returns(T.any(T::Hash[String, T.untyped], T::Boolean)) }
    def to_h = constraint.to_h

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = T.cast(@yaml, T::Hash[String, T.untyped]).fetch("idl()")

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
