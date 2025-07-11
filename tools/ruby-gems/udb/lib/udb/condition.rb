#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require "idlc/symbol_table"
require "udb/obj/extension"

module Udb

  class Constraint
    extend T::Sig

    sig { params(idl: String, input_file: String, input_line: Integer, cfg_arch: ConfiguredArchitecture).void }
    def initialize(idl, input_file:, input_line:, cfg_arch:)
      @ast = cfg_arch.idl_compiler.compile_func_body(idl, symtab: cfg_arch.symtab, input_file:, input_line:)
    end

    sig { params(symtab: Idl::SymbolTable).returns(T::Boolean) }
    def eval(symtab)
      @ast.satisfied?(symtab)
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

  class LogicNodeType < T::Enum
    enums do
      True = new
      False = new
      Term = new
      Not = new
      And = new
      Or = new
      None = new
      If = new
    end
  end

  # Abstract syntax tree of the condition logic
  class LogicNode
    extend T::Sig

    sig { returns(LogicNodeType) }
    attr_accessor :type

    TermType = T.type_alias { T.any(ExtensionRequirement, Constraint) }
    sig { params(type: LogicNodeType, children: T::Array[T.any(LogicNode, TermType)]).void }
    def initialize(type, children)
      raise ArgumentError, "Children must be singular" if [LogicNodeType::Term, LogicNodeType::Not].include?(type) && children.size != 1
      raise ArgumentError, "Children must have at least two elements" if [LogicNodeType::And, LogicNodeType::Or, LogicNodeType::None, LogicNodeType::If].include?(type) && children.size < 2

      @children = children
      if [LogicNodeType::True, LogicNodeType::False].include?(type)
        raise ArgumentError, "Children must be empty" unless children.empty?
      elsif type == LogicNodeType::Term
        # ensure the children are TermType
        raise "Children must be either ExtensionRequirements or Constraints" unless children.all? { |c| c.is_a?(ExtensionRequirement) || c.is_a?(Constraint) }
      else
        raise ArgumentError, "All Children must be LogicNodes" unless children.all? { |child| child.is_a?(LogicNode) }
        if type == LogicNodeType::Not
          @children = children
        else
          if children.size == 2
            @children = children
          else
            @children = [children.fetch(0), LogicNode.new(type, T.must(children[1..]))]
          end
        end
      end

      @type = type
    end

    # @return The terms (leafs) of this tree
    sig { returns(T::Array[T.any(ExtensionRequirement, Constraint)]) }
    def terms
      @terms ||=
        if @type == LogicNodeType::Term
          [@children.fetch(0)]
        else
          @children.map { |child| T.cast(child, LogicNode).terms }.flatten.uniq
        end
    end

    EvalCallbackType = T.type_alias { T.proc.params(arg0: T.any(ExtensionRequirement, Constraint)).returns(T::Boolean) }
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def make_eval_cb(&blk)
      blk
    end
    private :make_eval_cb

    # evaluate the logic tree using +symtab+ to evaluate any constraints and +ext_vers+ to evaluate any extension requirements
    sig { params(symtab: Idl::SymbolTable, ext_vers: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def eval(symtab, ext_vers)
      cb = make_eval_cb do |term|
        if term.is_a?(ExtensionRequirement)
          ext_vers.any? do |term_value|
            next unless term_value.is_a?(ExtensionVersion)

            ext_ver = T.cast(term_value, ExtensionVersion)
            term.satisfied_by?(ext_ver)
          end
        elsif term.is_a?(Constraint)
          term.eval(symtab)
        else
          T.absurd(term)
        end
      end
      eval_cb(cb)
    end

    sig { params(callback: EvalCallbackType).returns(T::Boolean) }
    def eval_cb(callback)
      if @type == LogicNodeType::True
        true
      elsif @type == LogicNodeType::False
        false
      elsif @type == LogicNodeType::Term
        ext_req = T.cast(@children[0], ExtensionRequirement)
        callback.call(ext_req)
      elsif @type == LogicNodeType::If
        cond_ext_ret = T.cast(@children[0], LogicNode)
        if cond_ext_ret.eval_cb(callback)
          T.cast(@children[1], LogicNode).eval_cb(callback)
        else
          true
        end
      elsif @type == LogicNodeType::Not
        !T.cast(@children[0], LogicNode).eval_cb(callback)
      elsif @type == LogicNodeType::And
        @children.all? { |child| T.cast(child, LogicNode).eval_cb(callback) }
      elsif @type == LogicNodeType::Or
        @children.any? { |child| T.cast(child, LogicNode).eval_cb(callback) }
      elsif @type == LogicNodeType::None
        @children.none? { |child| T.cast(child, LogicNode).eval_cb(callback) }
      else
        T.absurd(@type)
      end
    end

    sig { returns(String) }
    def to_s
      if @type == LogicNodeType::True
        "true"
      elsif @type == LogicNodeType::False
        "false"
      elsif @type == LogicNodeType::Term
        "(#{@children[0]})"
      elsif @type == LogicNodeType::Not
        "!#{@children[0]}"
      elsif @type == LogicNodeType::And
        "(#{@children[0]} ^ #{@children[1]})"
      elsif @type == LogicNodeType::Or
        "(#{@children[0]} v #{@children[1]})"
      elsif @type == LogicNodeType::None
        "!(#{@children[0]} v #{@children[1]})"
      elsif @type == LogicNodeType::If
        "(#{@children[0]} -> #{@children[1]})"
      else
        T.absurd(@type)
      end
    end
  end

  module AbstractCondition
    extend T::Sig
    extend T::Helpers
    interface!

    sig { abstract.returns(T::Boolean) }
    def empty?; end

    sig { abstract.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true); end

    sig { abstract.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other); end

    sig { abstract.returns(T.any(String, T::Hash[String, T.untyped])) }
    def to_h; end

    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch); end

    sig { abstract.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def satisfied_by_ext_ver_list?(_ext_ver_list); end

    sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch); end

    sig { abstract.returns(T::Boolean) }
    def has_constraint?; end

    sig { abstract.returns(T::Boolean) }
    def has_extension_requirement?; end
  end

  # represents a condition in the UDB data, which could include conditions involving
  # extensions and/or parameters
  class Condition
    extend T::Sig
    extend T::Helpers
    include AbstractCondition

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

    sig { params(yaml: T::Hash[String, T.untyped], cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      @yaml = yaml
      @cfg_arch = cfg_arch
    end

    sig { override.returns(T::Hash[String, T.untyped]) }
    def to_h = @yaml

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
      elsif yaml.key?("not")
        LogicNode.new(LogicNodeType::Not, [to_logic_tree_helper(yaml["not"], expand:)])
      elsif yaml.key?("extension")
        ExtensionCondition.new(yaml["extension"], @cfg_arch).to_logic_tree
      elsif yaml.key?("param")
        ConstraintCondition.new(yaml["param"], @cfg_arch).to_logic_tree
      else
        raise "Unexpected"
      end
    end
    private :to_logic_tree_helper

    sig { override.returns(T::Boolean) }
    def has_constraint?
      to_logic_tree.terms.any? { |t| t.is_a?(Constraint) }
    end

    sig { override.returns(T::Boolean) }
    def has_extension_requirement?
      to_logic_tree.terms.any? { |t| t.is_a?(ExtensionRequirement) }
    end

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(cfg_arch)
      r = satisfied_by_cfg_arch?(cfg_arch)
      r == SatisfiedResult::Yes || r == SatisfiedResult::Maybe
    end

    EvalCallbackType = T.type_alias { T.proc.params(term: T.any(ExtensionRequirement, Constraint)).returns(T::Boolean) }
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def make_cb_proc(&blk)
      blk
    end
    private :make_cb_proc

    sig { override.params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(cfg_arch)
      if cfg_arch.fully_configured?
        if to_logic_tree.eval(cfg_arch.symtab, cfg_arch.transitive_implemented_extension_versions)
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      elsif cfg_arch.partially_configured?
        mandatory_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionRequirement)
            cond_ext_req = T.cast(term, ExtensionRequirement)
            cfg_arch.mandatory_extension_reqs.any? { |cfg_ext_req| cond_ext_req.satisfied_by?(cfg_ext_req) }
          elsif term.is_a?(Constraint)
            constraint = T.cast(term, Constraint)
            constraint.eval(cfg_arch.symtab)
          else
            T.absurd(term)
          end
        end
        possible_ext_cb = make_cb_proc do |term|
          if term.is_a?(ExtensionRequirement)
            cond_ext_req = T.cast(term, ExtensionRequirement)
            cfg_arch.possible_extension_versions.any? { |cfg_ext_ver| cond_ext_req.satisfied_by?(cfg_ext_ver) }
          elsif term.is_a?(Constraint)
            constraint = T.cast(term, Constraint)
            constraint.eval(cfg_arch.symtab)
          else
            T.absurd(term)
          end
        end
        if to_logic_tree.eval_cb(mandatory_ext_cb)
          SatisfiedResult::Yes
        elsif to_logic_tree.eval_cb(possible_ext_cb)
          SatisfiedResult::Maybe
        else
          SatisfiedResult::No
        end
      else
        # unconfig. Can't really say anthing
        SatisfiedResult::Maybe
      end
    end

    sig { override.params(ext_ver_list: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def satisfied_by_ext_ver_list?(ext_ver_list)
      to_logic_tree.eval(@cfg_arch.symtab, ext_ver_list)
    end

    sig { override.params(other: AbstractCondition).returns(T::Boolean) }
    def compatible?(other)
      tree1 = to_logic_tree
      tree2 = other.to_logic_tree

      extensions = (tree1.terms + tree2.terms).map(&:extension).uniq

      extension_versions = extensions.map(&:versions)

      combos = combos_for(extension_versions)
      combos.each do |combo|
        return true if tree1.eval(combo) && tree2.eval(combo)
      end

      # there is no combination in which both self and other can be true
      false
    end

  end

  class AlwaysTrueCondition
    extend T::Sig
    include AbstractCondition

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= LogicNode.new(LogicNodeType::True, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = true

    sig { override.returns(T.any(String, T::Hash[String, T.untyped])) }
    def to_h = {}

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::Yes

    sig { override.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def satisfied_by_ext_ver_list?(_ext_ver_list) = true

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch) = true

    sig { override.returns(T::Boolean) }
    def has_constraint? = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false
  end

  class AlwaysFalseCondition
    extend T::Sig
    include AbstractCondition

    sig { override.returns(T::Boolean) }
    def empty? = true

    sig { override.params(expand: T::Boolean).returns(LogicNode) }
    def to_logic_tree(expand: true)
      @logic_tree ||= LogicNode.new(LogicNodeType::False, [])
    end

    sig { override.params(_other: T.untyped).returns(T::Boolean) }
    def compatible?(_other) = false

    sig { override.returns(T.any(String, T::Hash[String, T.untyped])) }
    def to_h = {}

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::No

    sig { override.params(_ext_ver_list: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def satisfied_by_ext_ver_list?(_ext_ver_list) = true

    sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
    def could_be_true?(_cfg_arch) = false

    sig { override.returns(T::Boolean) }
    def has_constraint? = false

    sig { override.returns(T::Boolean) }
    def has_extension_requirement? = false
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
      n = LogicNode.new(LogicNodeType::Term, [ext_req])

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

  class ConstraintCondition
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
  # This is because:
  #
  #
  # zero or more of which
  # may be conditional (via an ExtensionRequirementExpression)
  class Requirements < Condition
    extend T::Sig

    class ConditionalExtensionVersion < T::Struct
      prop :ext_ver, ExtensionVersion
      prop :cond, AbstractCondition
    end

    class ParseState < T::Enum
      enums do
        Condition = new
        ExtensionCondition = new
      end
    end

    sig { params(yaml: T.nilable(T::Hash[String, T.untyped]), cfg_arch: ConfiguredArchitecture).void }
    def initialize(yaml, cfg_arch)
      super(yaml || {}, cfg_arch)
    end

    sig {
      params(
        yaml: T::Hash[String, T.untyped],
        state: ParseState,
        cond_thus_far: T.nilable(T.all(AbstractCondition, Object)),
        result_ary: T::Array[ConditionalExtensionVersion]
      ).returns(T::Array[ConditionalExtensionVersion])
    }
    def implied_extension_versions_helper(yaml, state, cond_thus_far, result_ary)
      case (state)
      when ParseState::Condition
        if yaml.key?("extension")
          implied_extension_versions_helper(yaml.fetch("extension"), ParseState::ExtensionCondition, cond_thus_far, result_ary)
        elsif yaml.key?("allOf")
          yaml.fetch("allOf").each do |cond_yaml|
            implied_extension_versions_helper(yaml.fetch("allOf"), ParseState::Condition, cond_thus_far, result_ary)
          end
        elsif yaml.key?("anyOf") || yaml.key?("oneOf") || yaml.key?("noneOf")
          # nothing is certain below here, so just return results thus far
          return result_ary
        else
          raise "unexpected key(s): #{yaml.keys}"
        end

      when ParseState::ExtensionCondition
        if yaml.key?("name")
          req_spec =
            if yaml.key?("version")
              RequirementSpec.new(yaml.fetch("version"))
            else
              RequirementSpec.new(">= 0")
            end
          if req_spec.op == "="
            cond = cond_thus_far.nil? ? AlwaysTrueCondition.new : T.must(cond_thus_far)
            ext_ver = ExtensionVersion.new(yaml.fetch("name"), req_spec.version_spec.to_s, @cfg_arch)
            result_ary << ConditionalExtensionVersion.new(cond:, ext_ver:)
          end

        elsif yaml.key?("allOf")
          yaml.fetch("allOf").each do |ext_cond_yaml|
            implied_extension_versions_helper(ext_cond_yaml, ParseState::ExtensionCondition, cond_thus_far, result_ary)
          end

        elsif yaml.key?("if")
          if_cond = Condition.new(yaml.fetch("if"), @cfg_arch)
          cond = cond_thus_far.nil? ? if_cond : Condition.join(@cfg_arch, [cond_thus_far, if_cond])
          implied_extension_versions_helper(yaml.fetch("then"), ParseState::ExtensionCondition, cond, result_ary)

        elsif yaml.key?("anyOf") || yaml.key("oneOf") || yaml.key("noneOf")
          # there are not going to be specific requirements down an anyOf/oneOf/noneOf path
          # be required
          return result_ary
        else
          raise "Unexpected key(s): #{yaml.keys}"
        end

      else
        T.absurd(state)
      end

      result_ary
    end
    private :implied_extension_versions_helper

    sig { returns(T::Array[ConditionalExtensionVersion]) }
    def implied_extension_versions
      if empty?
        []
      else
        implied_extension_versions_helper(T.must(@yaml), ParseState::Condition, nil, [])
      end
    end
  end
end
