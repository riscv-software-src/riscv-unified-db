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
  class Architecture; end
  class ConfiguredArchitecture < Architecture; end
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
      returns(LogicNode)
    }
    def to_logic_tree_internal
      Condition.new(to_h, @cfg_arch).to_logic_tree_internal
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
    sig { abstract.returns(LogicNode) }
    def to_logic_tree_internal; end

    # is this condition satisfiable?
    sig { returns(T::Boolean) }
    def satisfiable?
      to_logic_tree(expand: true).satisfiable?
    end

    # is this condition unsatisfiable?
    sig { returns(T::Boolean) }
    def unsatisfiable?
      to_logic_tree(expand: true).unsatisfiable?
    end

    # is this condition in any way affected by term?
    sig { params(term: T.any(Extension, ExtensionVersion, ExtensionRequirement, Parameter, ParameterWithValue), expand: T::Boolean).returns(T::Boolean) }
    def mentions?(term, expand: true)
      to_logic_tree(expand:).terms.any? do |t|
        case t
        when ExtensionTerm
          (term.is_a?(Extension) || term.is_a?(ExtensionVersion) || term.is_a?(ExtensionRequirement)) && (term.name == t.name)
        when ParameterTerm
          (term.is_a?(Parameter) || term.is_a?(ParameterWithValue)) && (term.name == t.name)
        else
          false
        end
      end
    end

    # return list of all extension requirements in the condition
    #
    # if expand is true, expand the condition to include transitive requirements
    sig { params(expand: T::Boolean).returns(T::Array[ExtensionRequirement]) }
    def ext_req_terms(expand:)
      if expand
        @expanded_ext_req_terms ||=
          to_logic_tree(expand:).terms.grep(ExtensionTerm).map { |term| term.to_ext_req(@cfg_arch) }
      else
        @unexpanded_ext_req_terms ||=
          to_logic_tree(expand:).terms.grep(ExtensionTerm).map { |term| term.to_ext_req(@cfg_arch) }
      end
    end

    # return list of all parameters in the condition
    #
    # if expand is true, expand the condition to include transitive requirements
    sig { params(expand: T::Boolean).returns(T::Array[Parameter]) }
    def param_terms(expand:)
      if expand
        @expanded_param_terms ||=
          to_logic_tree(expand:).terms.grep(ParameterTerm).map { |term| @cfg_arch.param(term.name) }
      else
        @unexpanded_param_terms ||=
          to_logic_tree(expand:).terms.grep(ParameterTerm).map { |term| @cfg_arch.param(term.name) }
      end
    end

    # is is possible for this condition and other to be simultaneously true?
    sig { params(other: AbstractCondition).returns(T::Boolean) }
    def compatible?(other)
      (self & other).satisfiable?
    end

    # @return if the condition is, possibly is, or is definately not satisfied by cfg_arch
    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch); end

    sig { abstract.params(ext_reqs: T::Array[ExtensionRequirement], expand: T::Boolean).returns(AbstractCondition) }
    def partial_eval(ext_reqs: [], expand: true); end

    # partially evaluate by replacing any known parameter terms with true/false, and returning
    # a new condition
    sig { abstract.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(AbstractCondition) }
    def partially_evaluate_for_params(cfg_arch, expand:); end

    # is condition satisfied if +ext_req+ is the only thing defined?
    #
    # When include_requirements is true, expand the condition before evaluating
    sig { abstract.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfied_by_ext_req?(ext_req, include_requirements: false); end

    # If ext_req is *not* satisfied, is condition satisfiable?
    # When +include_requirements+ is true, also assume that the ext_req's requirements are not met
    sig { abstract.params(_ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(_ext_req, include_requirements: false); end

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

    sig { params(other_condition: AbstractCondition).returns(T::Boolean) }
    def covered_by?(other_condition)
      # cover means other_condition always implies self
      # can test that by seeing if the contradiction is satisfiable, i.e.:
      # if other_condition -> self , contradition would be other_condition & not self
      contradiction = LogicNode.new(
        LogicNodeType::And,
        [
          other_condition.to_logic_tree(expand: true),
          LogicNode.new(LogicNodeType::Not, [to_logic_tree(expand: true)])
        ]
      )
      !contradiction.satisfiable?
    end

    sig { params(other_condition: AbstractCondition).returns(T::Boolean) }
    def always_implies?(other_condition)
      other_condition.covered_by?(self)
    end

    # true if the condition references a parameter at some point
    sig { abstract.returns(T::Boolean) }
    def has_param?; end

    # true if the condition references an extension requirements at some point
    sig { abstract.returns(T::Boolean) }
    def has_extension_requirement?; end

    sig { abstract.params(expand: T::Boolean).returns(AbstractCondition) }
    def minimize(expand: true); end

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
    sig { abstract.params(expand: T::Boolean).returns(String) }
    def to_s(expand: false); end

    # condition in prose
    sig { abstract.returns(String) }
    def to_s_pretty; end

    # print, with actualy values of terms
    sig { abstract.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(String) }
    def to_s_with_value(cfg_arch, expand:); end

    # condition in Asciidoc
    sig { abstract.returns(String) }
    def to_asciidoc; end

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
    sig { abstract.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements(expand: true); end

    # inversion of implied_extension_requirements
    sig { abstract.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_conflicts(expand: true); end

    sig { abstract.params(other: AbstractCondition).returns(AbstractCondition) }
    def &(other); end

    sig { abstract.params(other: AbstractCondition).returns(AbstractCondition) }
    def |(other); end

    # we use - instead of ! for negation to avoid ambiguous situations like:
    #
    #  !condition.satisfiable?
    #     (is this "negate condition is satisfiable" or "condition is unsatisfiable")
    sig { abstract.returns(AbstractCondition) }
    def -@; end

    sig { params(other: AbstractCondition).returns(AbstractCondition) }
    def implies(other)
      -self | other
    end

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
        (AlwaysTrueCondition.new(cfg_arch))
      elsif conds.size == 1
        conds.fetch(0)
      else
        Condition.new({ "allOf" => conds.map(&:to_h) }, cfg_arch)
      end
    end

    class MemoizedState < T::Struct
      prop :satisfied_by_cfg_arch, T::Hash[ConfiguredArchitecture, SatisfiedResult]
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
      @memo = MemoizedState.new(satisfied_by_cfg_arch: {})
    end

    sig { override.returns(T::Boolean) }
    def empty? = @yaml == true || @yaml == false || @yaml.empty?

    sig { params(term: ExtensionTerm, expansion_clauses: T::Array[LogicNode], touched_terms: T::Set[TermType]).void }
    def expand_extension_term_requirements(term, expansion_clauses, touched_terms)
      ext_req = term.to_ext_req(@cfg_arch)

      unless touched_terms.include?(term)
        touched_terms.add(term)

        unless ext_req.requirements_condition.empty?
          clause = ext_req.to_condition.implies(ext_req.requirements_condition).to_logic_tree(expand: false)
          expansion_clauses << clause
          expand_term_requirements(clause, expansion_clauses, touched_terms)
        end
      end
    end
    private :expand_extension_term_requirements

    sig { params(tree: LogicNode, expansion_clauses: T::Array[LogicNode]).void }
    def expand_extension_version_ranges(tree, expansion_clauses)
      # wherever we have an extension range (ExtensionRequirement), add a clause to say exactly one
      # satisfing version can be met
      mentioned_ext_terms = (tree.terms.grep(ExtensionTerm) + expansion_clauses.map { |c| c.terms.grep(ExtensionTerm) }.flatten).uniq

      covered_ext_reqs = T.let(Set.new, T::Set[ExtensionRequirement])
      mentioned_ext_terms.each do |ext_term|
        unless ext_term.comparison == ExtensionTerm::ComparisonOp::Equal
          ext_req = ext_term.to_ext_req(@cfg_arch)
          unless covered_ext_reqs.include?(ext_req)
            ext_vers = ext_req.satisfying_versions
            if ext_vers.size == 1
              # add ext_req -> ext_ver
              expansion_clauses <<
                LogicNode.new(
                  LogicNodeType::If,
                  [
                    LogicNode.new(LogicNodeType::Term, [ext_req.to_term]),
                    LogicNode.new(LogicNodeType::Term, [ext_vers.fetch(0).to_term])
                  ]
                )
              # add ext_ver -> ext_req
              expansion_clauses <<
                LogicNode.new(
                  LogicNodeType::If,
                  [
                    LogicNode.new(LogicNodeType::Term, [ext_vers.fetch(0).to_term]),
                    LogicNode.new(LogicNodeType::Term, [ext_req.to_term])
                  ]
                )
            elsif ext_vers.empty?
              # add ext_req -> false
              expansion_clauses <<
                LogicNode.new(
                  LogicNodeType::If,
                  [
                    LogicNode.new(LogicNodeType::Term, [ext_req.to_term]),
                    LogicNode::False
                  ]
                )
            else
              # add ext_req -> XOR(ext_ver)
              expansion_clauses <<
                LogicNode.new(
                  LogicNodeType::If,
                  [
                    LogicNode.new(LogicNodeType::Term, [ext_req.to_term]),
                    LogicNode.new(
                      LogicNodeType::Xor,
                      ext_vers.map { |v| LogicNode.new(LogicNodeType::Term, [v.to_term]) }
                    )
                  ]
                )
              ext_vers.each do |ext_ver|
                # add ext_ver -> ext_req
                expansion_clauses <<
                  LogicNode.new(
                    LogicNodeType::If,
                    [
                      LogicNode.new(LogicNodeType::Term, [ext_ver.to_term]),
                      LogicNode.new(LogicNodeType::Term, [ext_req.to_term]),
                    ]
                  )
              end

            end
          end
        end
      end
    end
    private :expand_extension_version_ranges

    sig { params(tree: LogicNode, expansion_clauses: T::Array[LogicNode]).void }
    def expand_to_enforce_single_ext_ver(tree, expansion_clauses)
      # for every mentioned extension, enforce that either zero or one version is ever implemented
      mentioned_ext_terms = (tree.terms.grep(ExtensionTerm) + expansion_clauses.map { |c| c.terms.grep(ExtensionTerm) }.flatten).uniq

      grouped_ext_terms = mentioned_ext_terms.group_by(&:name)

      grouped_ext_terms.each do |ext_name, ext_terms|
        # assuming this comes after expand_extension_version_ranges, so we can ignore ranges
        mentioned_versions = ext_terms.select { |e| e.comparison == ExtensionTerm::ComparisonOp::Equal }
        if mentioned_versions.size > 1
          # add NONE(ext_terms) || XOR(ext_terms)
          expansion_clauses <<
            LogicNode.new(
              LogicNodeType::Or,
              [
                LogicNode.new(
                  LogicNodeType::None,
                  mentioned_versions.map { |t| LogicNode.new(LogicNodeType::Term, [t]) }
                ),
                LogicNode.new(
                  LogicNodeType::Xor,
                  mentioned_versions.map { |t| LogicNode.new(LogicNodeType::Term, [t]) }
                )
              ]
            )
        end
      end
    end

    sig { params(term: ParameterTerm, expansion_clauses: T::Array[LogicNode], touched_terms: T::Set[TermType]).void }
    def expand_parameter_term_requirements(term, expansion_clauses, touched_terms)
      unless touched_terms.include?(term)
        touched_terms.add(term)

        # param expansion only depends on the parameter, not the comparison
        return if touched_terms.any? { |t| t.is_a?(ParameterTerm) && t.name == term.name }

        param = T.must(@cfg_arch.param(term.name))
        unless param.requirements_condition.empty?
          clause =
            LogicNode.new(
              LogicNodeType::If,
              [
                LogicNode.new(LogicNodeType::Term, [term]),
                param.requirements_condition.to_logic_tree(expand: false)
              ]
            )

          expansion_clauses << clause
          expand_term_requirements(clause, expansion_clauses, touched_terms)
        end
      end
    end
    private :expand_parameter_term_requirements

    sig { params(tree: LogicNode, expansion_clauses: T::Array[LogicNode]).void }
    def expand_to_enforce_param_relations(tree, expansion_clauses)
      mentioned_param_terms =
        (
          tree.terms.grep(ParameterTerm) \
          + expansion_clauses.map { |clause| clause.terms.grep(ParameterTerm) }.flatten
        ).uniq
      grouped_param_terms = mentioned_param_terms.group_by { |t| t.name }
      grouped_param_terms.each do |param_name, param_terms|
        if param_terms.size > 1
          param_terms.each do |t1|
            param_terms.each do |t2|
              next if t1.equal?(t2)

              relation = t1.relation_to(t2)
              unless relation.nil?
                expansion_clauses << relation
              end
            end
          end
        end
      end
    end
    private :expand_to_enforce_param_relations


    sig { params(tree: LogicNode, expansion_clauses: T::Array[LogicNode]).void }
    def expand_xlen(tree, expansion_clauses)
      if tree.terms.any? { |t| t.is_a?(XlenTerm) } || expansion_clauses.any? { |clause| clause.terms.any? { |t| t.is_a?(XlenTerm) } }
        expansion_clauses << LogicNode.new(LogicNodeType::Xor, [LogicNode::Xlen32, LogicNode::Xlen64])
      end
    end
    private :expand_xlen

    sig { params(tree: LogicNode, expansion_clauses: T::Array[LogicNode], touched_terms: T::Set[TermType]).returns(T::Array[LogicNode]) }
    def expand_term_requirements(tree, expansion_clauses = [], touched_terms = T.let(Set.new, T::Set[TermType]))
      terms = tree.terms

      terms.each do |term|
        case term
        when ExtensionTerm
          expand_extension_term_requirements(term, expansion_clauses, touched_terms)
        when ParameterTerm
          expand_parameter_term_requirements(term, expansion_clauses, touched_terms)
        else
          #pass
        end
      end

      expansion_clauses
    end

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand:)
      if expand
        @logic_tree_expanded ||=
          begin
            # we do several things in expansion:
            #
            #  1. expand any requirements of extensions/parameters
            #  2. ensure XLEN is exclusive (can be 32 or 64, but not both)
            #  3. ensure zero or one version of an extension can be implemented
            starting_tree = to_logic_tree_internal

            expansion_clauses = expand_term_requirements(starting_tree)

            expand_extension_version_ranges(starting_tree, expansion_clauses)

            # enforce_single_ext_ver must come after expand_extension_version_ranges
            expand_to_enforce_single_ext_ver(starting_tree, expansion_clauses)

            expand_to_enforce_param_relations(starting_tree, expansion_clauses)

            expand_xlen(starting_tree, expansion_clauses)

            expanded_tree =
              if expansion_clauses.empty?
                starting_tree
              else
                LogicNode.new(LogicNodeType::And, [starting_tree] + expansion_clauses)
              end
            # puts starting_tree
            # puts
            # puts expanded_tree
            # puts "_________________________________________________________________"
            expanded_tree
          end
      else
        @logic_tree_unexpanded ||= to_logic_tree_helper(@yaml)
      end
    end

    sig { override.params(expand: T::Boolean).returns(AbstractCondition) }
    def minimize(expand: true)
      Condition.new(to_logic_tree(expand:).minimize(LogicNode::CanonicalizationType::ProductOfSums).to_h, @cfg_arch)
    end

    # @api private
    sig {
      override
      .returns(LogicNode).checked(:never)
    }
    def to_logic_tree_internal
      to_logic_tree_helper(@yaml)
    end

    sig {
      overridable
      .params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
      ).returns(LogicNode)
    }
    def to_logic_tree_helper(yaml)
      if yaml.is_a?(TrueClass)
        LogicNode::True
      elsif yaml.is_a?(FalseClass)
        LogicNode::False
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node) })
      elsif yaml.key?("noneOf")
        LogicNode.new(LogicNodeType::None, yaml["noneOf"].map { |node| to_logic_tree_helper(node) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node) })
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"))])
      elsif yaml.key?("if")
        antecedent = to_logic_tree_helper(yaml.fetch("if"))
        consequent = to_logic_tree_helper(yaml.fetch("then"))
        LogicNode.new(LogicNodeType::If, [antecedent, consequent])
      elsif yaml.key?("extension")
        ExtensionCondition.new(yaml["extension"], @cfg_arch).to_logic_tree_internal
      elsif yaml.key?("param")
        ParamCondition.new(yaml["param"], @cfg_arch).to_logic_tree_internal
      elsif yaml.key?("xlen")
        case yaml.fetch("xlen")
        when 32
          LogicNode::Xlen32
        when 64
          LogicNode::Xlen64
        else
          raise "unexpected"
        end
      elsif yaml.key?("idl()")
        IdlCondition.new(yaml, @cfg_arch, input_file: nil, input_line: nil).to_logic_tree_internal
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
        elsif term.is_a?(XlenTerm)
          # can't use cfg_arch.possible_xlens because of an initialization circular dependency in figuring out
          # is S/U is implemented
          if term.xlen == 32
            if cfg_arch.mxlen.nil?
              SatisfiedResult::Maybe
            elsif cfg_arch.mxlen == 32
              SatisfiedResult::Yes
            else
              # mxlen == 64. can some other mode be 32?
              if !cfg_arch.config.param_values.key?("SXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("SXLEN"), T::Array[Integer]).include?(32)
                SatisfiedResult::Yes
              elsif !cfg_arch.config.param_values.key?("UXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("UXLEN"), T::Array[Integer]).include?(32)
                SatisfiedResult::Yes
              elsif !cfg_arch.config.param_values.key?("VSXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("VSXLEN"), T::Array[Integer]).include?(32)
                SatisfiedResult::Yes
              elsif !cfg_arch.config.param_values.key?("VUXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("VUXLEN"), T::Array[Integer]).include?(32)
                SatisfiedResult::Yes
              else
                SatisfiedResult::No
              end
            end
          elsif term.xlen == 64
            if cfg_arch.mxlen.nil?
              SatisfiedResult::Maybe
            elsif cfg_arch.mxlen == 32
              SatisfiedResult::No
            else
              # mxlen == 64. can some other mode be 32?
              if !cfg_arch.config.param_values.key?("SXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("SXLEN"), T::Array[Integer]) == [32]
                SatisfiedResult::Maybe
              elsif !cfg_arch.config.param_values.key?("UXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("UXLEN"), T::Array[Integer]) == [32]
                SatisfiedResult::Maybe
              elsif !cfg_arch.config.param_values.key?("VSXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("VSXLEN"), T::Array[Integer]) == [32]
                SatisfiedResult::Maybe
              elsif !cfg_arch.config.param_values.key?("VUXLEN")
                SatisfiedResult::Maybe
              elsif T.cast(cfg_arch.config.param_values.fetch("VUXLEN"), T::Array[Integer]) == [32]
                SatisfiedResult::Maybe
              else
                SatisfiedResult::Yes
              end
            end
          else
            raise "term.xlen is not 32 or 64"
          end
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
      @memo.satisfied_by_cfg_arch[cfg_arch] ||=
        if cfg_arch.fully_configured?
          implemented_ext_cb = make_cb_proc do |term|
            if term.is_a?(ExtensionTerm)
              ext_ver = cfg_arch.implemented_extension_version(term.name)
              next SatisfiedResult::No if ext_ver.nil?
              term.to_ext_req(cfg_arch).satisfied_by?(ext_ver) \
                ? SatisfiedResult::Yes
                : SatisfiedResult::No
            elsif term.is_a?(ParameterTerm)
              if cfg_arch.param_values.key?(term.name)
                term.eval(cfg_arch)
              else
                SatisfiedResult::No
              end
            elsif term.is_a?(FreeTerm)
              raise "unreachable"
            elsif term.is_a?(XlenTerm)
              if cfg_arch.possible_xlens.include?(term.xlen)
                if cfg_arch.possible_xlens.size == 1
                  SatisfiedResult::Yes
                else
                  SatisfiedResult::Maybe
                end
              else
                SatisfiedResult::No
              end
            else
              T.absurd(term)
            end
          end
          if to_logic_tree(expand: false).eval_cb(implemented_ext_cb) == SatisfiedResult::Yes
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
            elsif term.is_a?(XlenTerm)
              if cfg_arch.possible_xlens.include?(term.xlen)
                if cfg_arch.possible_xlens.size == 1
                  SatisfiedResult::Yes
                else
                  SatisfiedResult::Maybe
                end
              else
                SatisfiedResult::No
              end
            else
              T.absurd(term)
            end
          end

          to_logic_tree(expand: false).eval_cb(cb)
        else
          # unconfig. Can't really say anthing
          SatisfiedResult::Maybe
        end
    end

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfied_by_ext_req?(ext_req, include_requirements: false)
      cb = make_cb_proc do |term|
        if term.is_a?(ExtensionTerm)
          if term.to_ext_req(@cfg_arch).satisfied_by?(ext_req)
            SatisfiedResult::Yes
          else
            SatisfiedResult::No
          end
        else
          SatisfiedResult::No
        end
      end
      ext_req.to_condition.to_logic_tree(expand: include_requirements).eval_cb(cb) == SatisfiedResult::Yes
    end

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req, include_requirements: false)
      if include_requirements
        (self & -ext_req.to_condition & -ext_req.requirements_condition).satisfiable? == false
      else
        (self & -ext_req.to_condition).satisfiable? == false
      end
    end

    sig { override.params(ext_reqs: T::Array[ExtensionRequirement], expand: T::Boolean).returns(AbstractCondition) }
    def partial_eval(ext_reqs: [], expand: true)
      cb = LogicNode.make_replace_cb do |node|
        if node.type == LogicNodeType::Term
          term = node.children.fetch(0)
          if term.is_a?(ExtensionTerm)
            if ext_reqs.any? { |ext_req| term.to_ext_req(@cfg_arch).satisfied_by?(ext_req) }
              next LogicNode::True
            end
          end
        end
        node
      end
      LogicCondition.new(to_logic_tree(expand:).replace_terms(cb), @cfg_arch)
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

    sig { override.params(expand: T::Boolean).returns(String) }
    def to_s(expand: false)
      to_logic_tree(expand:).to_s(format: LogicNode::LogicSymbolFormat::C)
    end

    # return the condition in a nice, human-readable form
    sig { override.returns(String) }
    def to_s_pretty
      to_logic_tree(expand: false).to_s_pretty
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(String) }
    def to_s_with_value(cfg_arch, expand: false)
      cb = LogicNode.make_eval_cb do |term|
        case term
        when ExtensionTerm
          if cfg_arch.fully_configured?
            ext_ver = cfg_arch.implemented_extension_version(term.name)
            if ext_ver.nil? || !term.to_ext_req(cfg_arch).satisfied_by?(ext_ver)
              SatisfiedResult::No
            else
              SatisfiedResult::Yes
            end
          elsif cfg_arch.partially_configured?
            if cfg_arch.mandatory_extension_reqs.any? { |cfg_ext_req| cfg_ext_req.satisfied_by?(term.to_ext_req(cfg_arch)) }
              SatisfiedResult::Yes
            elsif cfg_arch.possible_extension_versions.any? { |cfg_ext_ver| term.to_ext_req(cfg_arch).satisfied_by?(cfg_ext_ver) }
              SatisfiedResult::Maybe
            else
              SatisfiedResult::No
            end
          else
            SatisfiedResult::Maybe
          end
        when ParameterTerm
          if cfg_arch.fully_configured?
            if cfg_arch.param_values.key?(term.name)
              term.eval(cfg_arch)
            else
              SatisfiedResult::No
            end
          elsif cfg_arch.partially_configured?
            term.eval(cfg_arch)
          else
            SatisfiedResult::Maybe
          end
        when XlenTerm
          if cfg_arch.possible_xlens.include?(term.xlen)
            if cfg_arch.possible_xlens.size == 1
              SatisfiedResult::Yes
            else
              SatisfiedResult::Maybe
            end
          else
            SatisfiedResult::No
          end
        else
          raise "unexpected term type #{term.class.name}"
        end
      end
      to_logic_tree(expand:).to_s_with_value(cb, format: LogicNode::LogicSymbolFormat::C)
    end

    sig { override.returns(String) }
    def to_asciidoc
      to_logic_tree(expand: false).to_asciidoc(include_versions: false)
    end

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements(expand: true)
      # strategy:
      #   1. convert to sum-of-products.
      #   2. for each product, find the positive terms. These are the implications
      #   3. for each product, find the negative terms. These are the "conditions" when the positive terms apply

      @implications ||= begin
        reqs = T.let([], T::Array[ConditionalExtensionRequirement])
        pos = to_logic_tree(expand:).minimize(LogicNode::CanonicalizationType::ProductOfSums)

        if pos.type == LogicNodeType::Term
          single_term = pos.children.fetch(0)
          if single_term.is_a?(ExtensionTerm)
            reqs << ConditionalExtensionRequirement.new(ext_req: single_term.to_ext_req(@cfg_arch), cond: AlwaysTrueCondition.new(@cfg_arch))
          else
            # this is a single parameter, do nothing
          end
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
                    cond: AlwaysTrueCondition.new(@cfg_arch)
                  )
              end
            elsif child.type == LogicNodeType::Not
              # not a positive term; do nothing
            elsif child.children.all? { |child| T.cast(child, LogicNode).type == LogicNodeType::Not }
              # there is no positive term, so do nothing
            else
              raise "? #{child.type}" unless child.type == LogicNodeType::Or

              positive_terms =
                child.node_children.select do |and_child|
                  and_child.type == LogicNodeType::Term && and_child.children.fetch(0).is_a?(ExtensionTerm)
                end
              cond_terms =
                child.node_children.select { |and_child| and_child.type == LogicNodeType::Not }
                .map { |neg_term| neg_term.node_children.fetch(0) }
              cond_terms +=
                child.node_children.select do |and_child|
                  and_child.type == LogicNodeType::Term && and_child.children.fetch(0).is_a?(ParameterTerm)
                end.map { |c| LogicNode.new(LogicNodeType::Not, [c]) }
              positive_terms.each do |pterm|
                cond_node =
                  if cond_terms.empty?
                    LogicNode::True
                  else
                    cond_terms.size == 1 \
                        ? cond_terms.fetch(0)
                        : LogicNode.new(LogicNodeType::And, cond_terms)
                  end

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

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_conflicts(expand: true)
      # strategy:
      #   1. invert extension requiremnts (to get conflicts)
      #   1. convert to product-of-sums.
      #   2. for each product, find the positive terms. These are the conflicts
      #   3. for each product, find the negative terms. These are the "conditions" when the positive terms apply

      @conflicts ||= begin
        conflicts = T.let([], T::Array[ConditionalExtensionRequirement])
        pos = LogicNode.new(LogicNodeType::Not, [to_logic_tree(expand:)]).minimize(LogicNode::CanonicalizationType::ProductOfSums)
        if pos.type == LogicNodeType::Term
          # there are no negative terms, do nothing
        elsif pos.type == LogicNodeType::Not
          single_term = pos.node_children.fetch(0).children.fetch(0)
          if single_term.is_a?(ExtensionTerm)
            conflicts << \
              ConditionalExtensionRequirement.new(
                ext_req: single_term.to_ext_req(@cfg_arch),
                cond: AlwaysTrueCondition.new(@cfg_arch)
              )
          else
            # parameter, do nothing
          end
        elsif pos.type == LogicNodeType::And
          pos.children.each do |child|
            child = T.cast(child, LogicNode)
            if child.type == LogicNodeType::Term
              # not a negative term; do nothing
            elsif child.type == LogicNodeType::Not
              term = child.node_children.fetch(0).children.fetch(0)
              if term.is_a?(ExtensionTerm)
                conflicts << \
                  ConditionalExtensionRequirement.new(
                    ext_req: term.to_ext_req(@cfg_arch),
                    cond: (AlwaysTrueCondition.new(@cfg_arch))
                  )
              else
                puts "Not a term: #{term} #{term.class.name}"
              end
            elsif child.children.all? { |child| T.cast(child, LogicNode).type == LogicNodeType::Term }
              # there is no negative term, so do nothing
            else
              raise "? #{child.type}" unless child.type == LogicNodeType::Or

              negative_terms =
                child.node_children.select do |and_child|
                  and_child.type == LogicNodeType::Not && and_child.node_children.fetch(0).children.fetch(0).is_a?(ExtensionTerm)
                end.map { |n| n.node_children.fetch(0) }
              cond_terms =
                child.node_children.select { |and_child| and_child.type == LogicNodeType::Term }
              negative_terms.each do |nterm|
                cond_node =
                  if cond_terms.empty?
                    LogicNode::True
                  else
                    cond_terms.size == 1 \
                        ? cond_terms.fetch(0)
                        : LogicNode.new(LogicNodeType::Or, cond_terms)
                  end

                conflicts << \
                  ConditionalExtensionRequirement.new(
                    ext_req: T.cast(nterm.children.fetch(0), ExtensionTerm).to_ext_req(@cfg_arch),
                    cond: Condition.new(cond_node.to_h, @cfg_arch)
                  )
              end
              conflicts
            end
          end
        end
        conflicts
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
        AlwaysFalseCondition.new(cfg_arch)
      elsif conditions.size == 1
        conditions.fetch(0)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::And,
            conditions.map { |c| c.to_logic_tree_internal }
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
        AlwaysFalseCondition.new(cfg_arch)
      elsif conditions.size == 1
        conditions.fetch(0)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::Or,
            conditions.map { |c| c.to_logic_tree_internal }
          ).to_h,
          cfg_arch
        )
      end
    end

    # return a new Condition that the logical XOR of conditions
    sig {
      params(
        conditions: T::Array[AbstractCondition],
        cfg_arch: ConfiguredArchitecture,
      )
      .returns(AbstractCondition)
    }
    def self.one_of(conditions, cfg_arch)
      if conditions.empty?
        AlwaysFalseCondition.new(cfg_arch)
      elsif conditions.size == 1
        conditions.fetch(0)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::Xor,
            conditions.map { |c| c.to_logic_tree_internal }
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
        AlwaysTrueCondition.new(cfg_arch)
      elsif condition.is_a?(AlwaysTrueCondition)
        AlwaysFalseCondition.new(cfg_arch)
      else
        Condition.new(
          LogicNode.new(
            LogicNodeType::Not,
            [condition.to_logic_tree_internal]
          ).to_h,
          cfg_arch
        )
      end
    end


    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def &(other)
      Condition.conjunction([self, other], @cfg_arch)
    end

    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def |(other)
      Condition.disjunction([self, other], @cfg_arch)
    end

    sig { override.returns(AbstractCondition) }
    def -@
      Condition.not(self, @cfg_arch)
    end
  end

  class LogicCondition < Condition

    sig { params(logic_node: LogicNode, cfg_arch: ConfiguredArchitecture).void }
    def initialize(logic_node, cfg_arch)
      @logic_node = logic_node
      @cfg_arch = cfg_arch
      @yaml = logic_node.to_h
    end

    sig { override.returns(T::Boolean) }
    def empty? = @logic_node.type == LogicNodeType::True || @logic_node.type == LogicNodeType::False

    sig { override.returns(LogicNode) }
    def to_logic_tree_internal
      @logic_node
    end
  end

  class AlwaysTrueCondition < AbstractCondition
    extend T::Sig

    sig { params(cfg_arch: ConfiguredArchitecture).void }
    def initialize(cfg_arch)
      @cfg_arch = cfg_arch
    end

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: false)
      LogicNode::True
    end

    # @api private
    sig {
      override
      .returns(LogicNode)
    }
    def to_logic_tree_internal
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
    def partially_evaluate_for_params(cfg_arch, expand: false) = self

    sig { override.params(ext_reqs: T::Array[ExtensionRequirement], expand: T::Boolean).returns(AbstractCondition) }
    def partial_eval(ext_reqs: [], expand: true) = self

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfied_by_ext_req?(ext_req, include_requirements: false) = false

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req, include_requirements: false) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.params(expand: T::Boolean).returns(AbstractCondition) }
    def minimize(expand: true) = self

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> true;"

    sig { override.params(expand: T::Boolean).returns(String) }
    def to_s(expand: false) = "true"

    sig { override.returns(String) }
    def to_s_pretty
      "always"
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(String) }
    def to_s_with_value(cfg_arch, expand: false) = "true"

    sig { override.returns(String) }
    def to_asciidoc = "true"

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements(expand: true) = []

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_conflicts(expand: true) = []

    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def &(other)
      Condition.conjunction([self, other], @cfg_arch)
    end

    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def |(other)
      self
    end

    sig { override.returns(AbstractCondition) }
    def -@
      AlwaysFalseCondition.new(@cfg_arch)
    end
  end

  class AlwaysFalseCondition < AbstractCondition
    extend T::Sig

    sig { params(cfg_arch: ConfiguredArchitecture).void }
    def initialize(cfg_arch)
      @cfg_arch = cfg_arch
    end

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand:)
      LogicNode::False
    end

    sig {
      override
      .returns(LogicNode)
    }
    def to_logic_tree_internal
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

    sig { override.params(ext_reqs: T::Array[ExtensionRequirement], expand: T::Boolean).returns(AbstractCondition) }
    def partial_eval(ext_reqs: [], expand: true) = self

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfied_by_ext_req?(ext_req, include_requirements: false) = false

    sig { override.params(ext_req: ExtensionRequirement, include_requirements: T::Boolean).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req, include_requirements: false) = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false

    sig { override.params(expand: T::Boolean).returns(AbstractCondition) }
    def minimize(expand: true) = self

    sig { override.returns(T::Boolean) }
    def has_param? = false

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch) = "-> false;"

    sig { override.params(expand: T::Boolean).returns(String) }
    def to_s(expand: false) = "false"

    sig { override.returns(String) }
    def to_s_pretty
      "never"
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture, expand: T::Boolean).returns(String) }
    def to_s_with_value(cfg_arch, expand: false) = "false"

    sig { override.returns(String) }
    def to_asciidoc = "false"

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_requirements(expand: true) = []

    sig { override.params(expand: T::Boolean).returns(T::Array[ConditionalExtensionRequirement]) }
    def implied_extension_conflicts(expand: true) = []


    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def &(other)
      self
    end

    sig { override.params(other: AbstractCondition).returns(AbstractCondition) }
    def |(other)
      Condition.disjunction([self, other], @cfg_arch)
    end

    sig { override.returns(AbstractCondition) }
    def -@
      AlwaysTrueCondition.new(@cfg_arch)
    end
  end

  class ParamCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig {
      params(
        yaml: T.any(TrueClass, FalseClass, T::Hash[String, T.untyped])
      )
      .returns(LogicNode)
    }
    def to_param_logic_tree_helper(yaml)
      if yaml == true
        LogicNode::True
      elsif yaml == false
        LogicNode::False
      elsif yaml.key?("name")
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new(yaml)])
      elsif yaml.key?("allOf")
        LogicNode.new(LogicNodeType::And, yaml.fetch("allOf").map { |y| to_param_logic_tree_helper(y) })
      elsif yaml.key?("anyOf")
        LogicNode.new(LogicNodeType::Or, yaml.fetch("anyOf").map { |y| to_param_logic_tree_helper(y) })
      elsif yaml.key?("oneOf")
        LogicNode.new(LogicNodeType::Xor, yaml.fetch("oneOf").map { |y| to_param_logic_tree_helper(y) })
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
            Condition.new(yaml.fetch("if"), @cfg_arch).to_logic_tree_internal,
            to_param_logic_tree_helper(yaml.fetch("then"))
          ]
        )

      else
        raise "unexpected key #{yaml.keys}"
      end
    end

    sig {
      override
      .returns(LogicNode)
    }
    def to_logic_tree_internal
      @logic_tree ||= to_param_logic_tree_helper(@yaml)
    end
  end

  class ExtensionCondition < Condition
    extend T::Sig

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml, cfg_arch)
    end

    sig { override.returns(LogicNode) }
    def to_logic_tree_internal
      @logic_tree ||= to_logic_tree_helper(@yaml)
    end

    # convert an ExtensionRequirement into a logic tree
    # if expand is true, also add requirements of the extension and all satisfing versions to the tree
    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        cfg_arch: ConfiguredArchitecture
      ).returns(LogicNode)
    }
    def ext_req_to_logic_node(yaml, cfg_arch)
      ext_req = ExtensionRequirement.create_from_yaml(yaml, cfg_arch)

      LogicNode.new(LogicNodeType::Term, [ext_req.to_term])
    end
    private :ext_req_to_logic_node

    sig {
      override
      .params(
        yaml: T.any(T::Hash[String, T.untyped], T::Boolean),
      )
      .returns(LogicNode)
    }
    def to_logic_tree_helper(yaml)
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
          LogicNode.new(LogicNodeType::And, yaml["allOf"].map { |node| to_logic_tree_helper(node) })
        elsif yaml.key?("anyOf")
          LogicNode.new(LogicNodeType::Or, yaml["anyOf"].map { |node| to_logic_tree_helper(node) })
        elsif yaml.key?("noneOf")
          LogicNode.new(LogicNodeType::Or, yaml["noneOf"].map { |node| to_logic_tree_helper(node) })
        elsif yaml.key?("oneOf")
          LogicNode.new(LogicNodeType::Xor, yaml["oneOf"].map { |node| to_logic_tree_helper(node) })
        elsif yaml.key?("not")
          LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml.fetch("not"))])
        elsif yaml.key?("if")
          LogicNode.new(
            LogicNodeType::If,
            [
              Condition.new(yaml.fetch("if"), @cfg_arch, input_file: @input_file, input_line: @input_line)
                .to_logic_tree_internal,
              to_logic_tree_helper(yaml.fetch("then"))
            ]
          )
        elsif yaml.key?("name")
          ext_req_to_logic_node(yaml, @cfg_arch)
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

    sig { override.returns(LogicNode) }
    def to_logic_tree_internal
      @logic_tree = constraint.to_logic_tree_internal
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
      ext_req = ExtensionRequirement.create_from_yaml(yaml, @cfg_arch)
      cond =
        if yaml.key?("when")
          Condition.new(yaml.fetch("when"), @cfg_arch)
        else
          AlwaysTrueCondition.new(@cfg_arch)
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
