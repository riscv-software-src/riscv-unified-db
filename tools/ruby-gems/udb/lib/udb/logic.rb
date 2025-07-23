# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "treetop"

require "idlc/symbol_table"
require "udb/eqn_parser"
require "udb/obj/extension"
require "udb/version_spec"

# Implements the LogicNode class, which is used to test for satisfiability/equality/etc of logic
#
# LogicNode isn't meant to used by the "public" API. It is used by the Condition classes, which
# correspond to concepts in the UDB data
#
# @see Condition

module Udb
  class LogicNodeType < T::Enum
    enums do
      True = new
      False = new
      Term = new
      Not = new
      And = new
      Or = new
      Xor = new
      None = new
      If = new
    end
  end

  # a terminal for an Extension with a specific version (a-la an ExtensionVersion)
  # we don't use ExtensionVersion for terminals just to keep LogicNode independent of the rest of UDB
  class ExtensionTerm
    extend T::Sig
    include Comparable

    sig { returns(String) }
    attr_reader :name

    sig { returns(String) }
    attr_reader :version

    sig { params(name: String, ver: String).void }
    def initialize(name, ver)
      @name = name
      @version = ver
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(ExtensionVersion) }
    def to_ext_ver(cfg_arch)
      ExtensionVersion.new(@name, @version, cfg_arch)
    end

    sig { override.returns(String) }
    def to_s
      "#{@name}@#{@version}"
    end

    sig { returns(T::Hash[String, String]) }
    def to_h
      {
        "name" => @name,
        "version" => "= #{@version}"
      }
    end

    sig { returns(String) }
    def to_idl
      "implemented_version?(ExtensionName::#{@name}, \"= #{@version}\")"
    end

    sig { override.params(other: BasicObject).returns(T.nilable(Integer)) }
    def <=>(other)
      return nil unless T.cast(other, Object).is_a?(ExtensionTerm)

      other_ext = T.cast(other, ExtensionTerm)
      if @name == other_ext.name
        T.must(VersionSpec.new(@version) <=> VersionSpec.new(other_ext.version))
      else
        T.must(@name <=> other_ext.name)
      end
    end

    # hash and eql? must be implemented to use ExtensionTerm as a Hash key
    sig { override.returns(Integer) }
    def hash = to_s.hash

    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      return false unless T.cast(other, Object).is_a?(ExtensionTerm)

      (self <=> T.cast(other, ExtensionTerm)) == 0
    end

  end

  # a terminal for a Parameter test (e.g., MXLEN == 32)
  class ParameterTerm
    extend T::Sig
    include Comparable

    class ParameterComparisonType < T::Enum
      enums do
        Equal = new("equal")
        NotEqual = new("not_equal")
        LessThan = new("less_than")
        GreaterThan = new("greater_than")
        LessThanOrEqual = new("less_than_or_equal")
        GreaterThanOrEqual = new("greater_than_or_equal")
        Includes = new("includes")
      end
    end

    sig { params(yaml: T::Hash[String, T.untyped]).void }
    def initialize(yaml)
      @yaml = yaml
    end

    sig { returns(String) }
    def name = @yaml.fetch("name")

    sig { returns(String) }
    def reason = @yaml.fetch("reason")

    sig { returns(T.nilable(Integer)) }
    def index = @yaml["index"]

    sig { returns(T.any(Integer, String, T::Boolean)) }
    def comparison_value
      @yaml.fetch(comparison_type.serialize)
    end

    sig { returns(ParameterComparisonType) }
    def comparison_type
      if @yaml.key?("equal")
        ParameterComparisonType::Equal
      elsif @yaml.key?("not_equal")
        ParameterComparisonType::NotEqual
      elsif @yaml.key?("less_than")
        ParameterComparisonType::LessThan
      elsif @yaml.key?("greater_than")
        ParameterComparisonType::GreaterThan
      elsif @yaml.key?("less_than_or_equal")
        ParameterComparisonType::LessThanOrEqual
      elsif @yaml.key?("greater_than_or_equal")
        ParameterComparisonType::GreaterThanOrEqual
      elsif @yaml.key?("includes")
        ParameterComparisonType::Includes
      else
        raise "No comparison found in [#{@yaml.keys}]"
      end
    end

    sig { params(value: T.untyped).returns(SatisfiedResult) }
    def eval_value(value)
      t = comparison_type
      case t
      when ParameterComparisonType::Equal
        (value == @yaml["equal"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::NotEqual
        (value != @yaml["not_equal"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::LessThan
        (value < @yaml["less_than"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::GreaterThan
        (value > @yaml["greater_than"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::LessThanOrEqual
        (value <= @yaml["less_than_or_equal"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::GreaterThanOrEqual
        (value >= @yaml["greater_than_or_equal"]) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::Includes
        (value.includes?(@yaml["includes"])) ? SatisfiedResult::Yes : SatisfiedResult::No
      else
        T.absurd(t)
      end
    end

    sig { params(symtab: Idl::SymbolTable).returns(SatisfiedResult) }
    def eval(symtab)
      var = symtab.get(name)
      raise "Could not find symbol #{name}" if var.nil?

      raise "Expecting a var" unless var.is_a?(Idl::Var)

      return SatisfiedResult::Maybe if var.value.nil?

      if var.type.kind == :array
        raise "Missing index or includes" unless @yaml.key?("index") || @yaml.key("includes")

        if @yaml.key?("index")
          raise "Index out of range" if T.cast(@yaml.fetch("index"), Integer) >= T.cast(var.value, Array).size

          value = var.value.fetch(@yaml.fetch("index"))
          eval_value(value)
        elsif @yaml.key?("includes")
          eval_value(var.value)
        else
          raise "unreachable"
        end
      else
        eval_value(var.value)
      end
    end

    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      @yaml
    end

    sig { returns(String) }
    def to_idl
      to_s # same for now
    end

    sig { returns(String) }
    def param_to_s
      if index.nil?
        name
      else
        "#{name}[#{index}]"
      end
    end

    sig { override.returns(String) }
    def to_s
      t = comparison_type
      case t
      when ParameterComparisonType::Equal
        "(#{param_to_s}=#{comparison_value})"
      when ParameterComparisonType::NotEqual
        "(#{param_to_s}!=#{comparison_value})"
      when ParameterComparisonType::LessThan
        "(#{param_to_s}<#{comparison_value})"
      when ParameterComparisonType::GreaterThan
        "(#{param_to_s}>#{comparison_value})"
      when ParameterComparisonType::LessThanOrEqual
        "(#{param_to_s}<=#{comparison_value})"
      when ParameterComparisonType::GreaterThanOrEqual
        "(#{param_to_s}>=#{comparison_value})"
      when ParameterComparisonType::Includes
        "$ary_includes?(#{param_to_s}, #{comparison_value})"
      else
        T.absurd(t)
      end
    end

    sig { override.params(other: BasicObject).returns(T.nilable(Integer)) }
    def <=>(other)
      return nil unless T.cast(other, Object).is_a?(ParameterTerm)

      other_param = T.cast(other, ParameterTerm)
      if name != other_param.name
        name <=> other_param.name
      elsif !index.nil? && !other_param.index.nil? && index != other_param.index
        T.must(index) <=> T.must(other_param.index)
      elsif comparison_type != other_param.comparison_type
        comparison_type <=> other_param.comparison_type
      elsif comparison_value != other_param.comparison_value
        if comparison_value.is_a?(String)
          T.cast(comparison_value, String) <=> T.cast(other_param.comparison_value, String)
        else
          T.cast(comparison_value, Integer) <=> T.cast(other_param.comparison_value, Integer)
        end
      else
        # these are the same (ignoring reason)
        return 0
      end
    end

    # hash and eql? must be implemented to use ExtensionTerm as a Hash key
    sig { override.returns(Integer) }
    def hash = @yaml.hash

    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      return false unless T.cast(other, Object).is_a?(ParameterTerm)

      (self <=> T.cast(other, ParameterTerm)) == 0
    end
  end

  # Abstract syntax tree of the condition logic
  class LogicNode
    extend T::Sig

    TermType = T.type_alias { T.any(ExtensionTerm, ParameterTerm) }
    ChildType = T.type_alias { T.any(LogicNode, TermType) }

    sig { returns(LogicNodeType) }
    attr_reader :type

    sig { returns(T::Array[ChildType]) }
    attr_reader :children

    sig { params(type: LogicNodeType, children: T::Array[ChildType]).void }
    def initialize(type, children)
      if [LogicNodeType::Term, LogicNodeType::Not].include?(type) && children.size != 1
        raise ArgumentError, "Children must be singular"
      end
      if [LogicNodeType::And, LogicNodeType::Or, LogicNodeType::Xor, LogicNodeType::None, LogicNodeType::If].include?(type) && children.size < 2
        raise ArgumentError, "Children must have at least two elements"
      end

      @children = children
      if [LogicNodeType::True, LogicNodeType::False].include?(type) && !children.empty?
        raise ArgumentError, "Children must be empty"
      elsif type == LogicNodeType::Term
        # ensure the children are TermType
        children.each { |child| T.assert_type!(T.cast(child, TermType), TermType) }
      else
        raise ArgumentError, "All Children must be LogicNodes" unless children.all? { |child| child.is_a?(LogicNode) }
      end

      @type = type
    end

    # @return The unique terms (leafs) of this tree
    sig { returns(T::Array[TermType]) }
    def terms
      @terms ||=
        if @type == LogicNodeType::Term
          [@children.fetch(0)]
        else
          @children.map { |child| T.cast(child, LogicNode).terms }.flatten.uniq
        end
    end

    # @return The unique terms (leafs) of this tree, exculding antecendents of an IF
    sig { returns(T::Array[TermType]) }
    def terms_no_antecendents
      if @type == LogicNodeType::If
        T.cast(@children.fetch(1), LogicNode).terms_no_antecendents
      elsif @type == LogicNodeType::Term
        [T.cast(@children.fetch(0), TermType)]
      else
        @children.map { |child| T.cast(child, LogicNode).terms_no_antecendents }.flatten.uniq
      end
    end

    EvalCallbackType = T.type_alias { T.proc.params(arg0: TermType).returns(SatisfiedResult) }
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def make_eval_cb(&blk)
      blk
    end
    private :make_eval_cb

    # evaluate the logic tree using +symtab+ to evaluate any constraints and +ext_vers+ to evaluate any extension requirements
    sig { params(cfg_arch: ConfiguredArchitecture, symtab: Idl::SymbolTable, ext_vers: T::Array[ExtensionVersion]).returns(SatisfiedResult) }
    def eval(cfg_arch, symtab, ext_vers)
      cb = make_eval_cb do |term|
        case term
        when ExtensionTerm
          ext_vers.any? { |ext_ver| ext_ver == term.to_ext_ver(cfg_arch) } ? SatisfiedResult::Yes : SatisfiedResult::No
        when ParameterTerm
          term.eval(symtab)
        else
          T.absurd(term)
        end
      end
      eval_cb(cb)
    end

    sig { params(callback: EvalCallbackType).returns(SatisfiedResult) }
    def eval_cb(callback)
      if @type == LogicNodeType::True
        SatisfiedResult::Yes
      elsif @type == LogicNodeType::False
        SatisfiedResult::No
      elsif @type == LogicNodeType::Term
        child = T.cast(@children.fetch(0), TermType)
        callback.call(child)
      elsif @type == LogicNodeType::If
        cond_ext_ret = T.cast(@children[0], LogicNode)
        res = cond_ext_ret.eval_cb(callback)
        case res
        when SatisfiedResult::Yes
          T.cast(@children[1], LogicNode).eval_cb(callback)
        when SatisfiedResult::Maybe
          SatisfiedResult::Maybe
        when SatisfiedResult::No
          SatisfiedResult::Yes
        else
          T.absurd(res)
        end
      elsif @type == LogicNodeType::Not
        res = T.cast(@children[0], LogicNode).eval_cb(callback)
        case res
        when SatisfiedResult::Yes
          SatisfiedResult::No
        when SatisfiedResult::No
          SatisfiedResult::Yes
        when SatisfiedResult::Maybe
          SatisfiedResult::Maybe
        else
          T.absurd(res)
        end
      elsif @type == LogicNodeType::And
        if @children.all? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::Yes }
          SatisfiedResult::Yes
        elsif @children.any? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::No }
          SatisfiedResult::No
        else
          SatisfiedResult::Maybe
        end
      elsif @type == LogicNodeType::Or
        if @children.any? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::Yes }
          SatisfiedResult::Yes
        elsif @children.all? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::No }
          SatisfiedResult::No
        else
          SatisfiedResult::Maybe
        end
      elsif @type == LogicNodeType::None
        if @children.all? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::No }
          SatisfiedResult::Yes
        elsif @children.any? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::Yes }
          SatisfiedResult::No
        else
          SatisfiedResult::Maybe
        end
      elsif @type == LogicNodeType::Xor
        if @children.any? { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::Maybe }
          SatisfiedResult::Maybe
        elsif @children.count { |child| T.cast(child, LogicNode).eval_cb(callback) == SatisfiedResult::Yes } == 1
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      else
        T.absurd(@type)
      end
    end

    class LogicSymbolFormat < T::Enum
      enums do
        C = new
        Eqn = new
        English = new
        Predicate = new
      end
    end

    LOGIC_SYMBOLS = {
      LogicSymbolFormat::C => {
        TRUE: "1",
        FALSE: "0",
        NOT: "!",
        AND: "&&",
        OR: "||",
        XOR: "^",
        IMPLIES: "DOES NOT EXIST"
      },
      LogicSymbolFormat::Eqn => {
        TRUE: "ONE",
        FALSE: "ZERO",
        NOT: "!",
        AND: "&",
        OR: "|",
        XOR: "DOES NOT EXIST",
        IMPLIES: "DOES NOT EXIST"
      },
      LogicSymbolFormat::English => {
        TRUE: "true",
        FALSE: "false",
        NOT: "NOT ",
        AND: "AND",
        OR: "OR",
        XOR: "XOR",
        IMPLIES: "IMPLIES"
      },
      LogicSymbolFormat::Predicate => {
        TRUE: "true",
        FALSE: "false",
        NOT: "\u00ac",
        AND: "\u2227",
        OR: "\u2228",
        XOR: "\u2295",
        IMPLIES: "\u2192"
      }
    }

    sig { params(format: LogicSymbolFormat).returns(String) }
    def to_s(format: LogicSymbolFormat::Predicate)
      if @type == LogicNodeType::True
        LOGIC_SYMBOLS[format][:TRUE]
      elsif @type == LogicNodeType::False
        LOGIC_SYMBOLS[format][:FALSE]
      elsif @type == LogicNodeType::Term
        @children[0].to_s
      elsif @type == LogicNodeType::Not
        "#{LOGIC_SYMBOLS[format][:NOT]}#{@children[0]}"
      elsif @type == LogicNodeType::And
        "(#{@children.map { |c| T.cast(c, LogicNode).to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:AND]} ")})"
      elsif @type == LogicNodeType::Or
        "(#{@children.map { |c| T.cast(c, LogicNode).to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::Xor
        "(#{@children.map { |c| T.cast(c, LogicNode).to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:XOR]} ")})"
      elsif @type == LogicNodeType::None
        "#{LOGIC_SYMBOLS[format][:NOT]}(#{@children.map { |c| T.cast(c, LogicNode).to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::If
        "(#{T.cast(@children.fetch(0), LogicNode).to_s(format:)} #{LOGIC_SYMBOLS[format][:IMPLIES]} #{T.cast(@children.fetch(1), LogicNode).to_s(format:)})"
      else
        T.absurd(@type)
      end
    end

    sig { returns(String) }
    def to_idl
      case @type
      when LogicNodeType::True
        "true"
      when LogicNodeType::False
        "false"
      when LogicNodeType::Term
        T.cast(@children.fetch(0), TermType).to_idl
      when LogicNodeType::Not
        "!#{@children.fetch(0).to_idl}"
      when LogicNodeType::And
        "(#{@children.map(&:to_idl).join(" && ")})"
      when LogicNodeType::Or
        "(#{@children.map(&:to_idl).join(" || ")})"
      when LogicNodeType::Xor, LogicNodeType::None
        nnf.to_idl
      when LogicNodeType::If
        "(#{@children.fetch(0).to_idl}) -> (#{@children.fetch(1).to_idl})"
      else
        T.absurd(@type)
      end
    end

    # convert to a UDB schema
    sig { params(term_determined: T::Boolean).returns(T.any(T::Boolean, T::Hash[String, T.untyped])) }
    def to_h(term_determined = false)
      if @type == LogicNodeType::True
        true
      elsif @type == LogicNodeType::False
        false
      elsif @type == LogicNodeType::Term
        if term_determined
          @children.fetch(0).to_h
        else
          child = T.cast(@children.fetch(0), TermType)
          case child
          when ExtensionTerm
            { "extension" => @children.fetch(0).to_h }
          when ParameterTerm
            { "param" => @children.fetch(0).to_h }
          else
            T.absurd(child)
          end
        end
      elsif @type == LogicNodeType::Not
        child = T.cast(@children.fetch(0), LogicNode)
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "not" => child.to_h(true) } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "not" => child.to_h(true) } }
        else
          { "not" => child.to_h(term_determined) }
        end
      elsif @type == LogicNodeType::And
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "allOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "allOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        else
          { "allOf" => @children.map { |child| T.cast(child, LogicNode).to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::Or
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "anyOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "anyOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        else
          { "anyOf" => @children.map { |child| T.cast(child, LogicNode).to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::Xor
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "oneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "oneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        else
          { "oneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::None
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "noneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "noneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(true) } } }
        else
          { "noneOf" => @children.map { |child| T.cast(child, LogicNode).to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::If
        {
          "if" => T.cast(@children.fetch(0), LogicNode).to_h(false),
          "then" => T.cast(@children.fetch(1), LogicNode).to_h(term_determined)
        }
      else
        T.absurd(@type)
      end
    end

    sig { params(node: LogicNode).returns(LogicNode) }
    def do_nnf_for_not(node)
      child = do_nnf(T.cast(node.children.fetch(0), LogicNode))
      child_type = child.type
      case child_type
      when LogicNodeType::Term
        # identity
        LogicNode.new(LogicNodeType::Not, [child])
      when LogicNodeType::True
        # invert to false
        LogicNode.new(LogicNodeType::False, [])
      when LogicNodeType::False
        # invert to true
        LogicNode.new(LogicNodeType::True, [])
      when LogicNodeType::And
        # distribute
        # !(a && b) == (!a || !b)
        LogicNode.new(
          LogicNodeType::Or,
          child.children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [T.cast(child2, LogicNode)])) }
        )
      when LogicNodeType::Or
        # distribute
        # !(a || b) == (!a && !b)
        LogicNode.new(
          LogicNodeType::And,
          child.children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [T.cast(child2, LogicNode)])) }
        )
      when LogicNodeType::Not
        # !!A = A
        grandchild = T.cast(child.children.fetch(0), LogicNode)
        do_nnf(grandchild)
      when LogicNodeType::If, LogicNodeType::None, LogicNodeType::Xor
        raise "impossible; xor/none are expanded"
      else
        T.absurd(child_type)
      end
    end
    private :do_nnf_for_not

    # rewrite to Negation Normal Form
    sig { params(node: LogicNode).returns(LogicNode) }
    def do_nnf(node)
      node_type = node.type
      case node_type
      when LogicNodeType::Not
        do_nnf_for_not(node)
      when LogicNodeType::And
        LogicNode.new(LogicNodeType::And, node.children.map { |child2| do_nnf(T.cast(child2, LogicNode)) })
      when LogicNodeType::Or
        LogicNode.new(LogicNodeType::Or, node.children.map { |child2| do_nnf(T.cast(child2, LogicNode)) })
      when LogicNodeType::None
        # NOR(A, b) = !A && !B
        LogicNode.new(
          LogicNodeType::And,
          node.children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [T.cast(child2, LogicNode)])) }
        )
      when LogicNodeType::Xor
        # XOR(A, b) = (A && !B) || (!A && B)
        new_kids = []
        node.children.size.times do |i|
          group = []
          node.children.size.times do |j|
            if i == j
              group << node.children.fetch(j)
            else
              group << do_nnf(LogicNode.new(LogicNodeType::Not, [node.children.fetch(j)]))
            end
          end
          new_kids << LogicNode.new(LogicNodeType::And, group)
        end
        LogicNode.new(
          LogicNodeType::Or,
          new_kids
        )
      when LogicNodeType::If
        # A -> B == !A or B
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [T.cast(node.children.fetch(0), LogicNode)]
            ),
            do_nnf(T.cast(node.children.fetch(1), LogicNode))
          ]
        )
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        node
      else
        T.absurd(node_type)
      end
    end
    private :do_nnf

    # @return self, converted to Negation Normal Form
    sig { returns(LogicNode) }
    def nnf
      n = do_nnf(self)
      raise "not NNF: #{n}" unless n.is_nnf?
      n
    end

    # @return true iff self is in Negation Normal Form
    def is_nnf?
      if @type == LogicNodeType::Not
        T.cast(@children.fetch(0), LogicNode).type == LogicNodeType::Term
      elsif @type == LogicNodeType::Term
        true
      else
        @children.all? { |child| T.cast(child, LogicNode).is_nnf? }
      end
    end

    sig { params(node: LogicNode).returns(LogicNode) }
    def do_parenthesize(node)
      if node.type == LogicNodeType::And
        if node.children.size == 2
          node
        else
          root = LogicNode.new(LogicNodeType::And, [do_parenthesize(T.cast(node.children.fetch(0), LogicNode)), do_parenthesize(T.cast(node.children.fetch(1), LogicNode))])
          (2...node.children.size).each do |i|
            root = LogicNode.new(LogicNodeType::And, [root, do_parenthesize(T.cast(node.children.fetch(i), LogicNode))])
          end
          root
        end
      elsif node.type == LogicNodeType::Or
        if node.children.size == 2
          node
        else
          root = LogicNode.new(LogicNodeType::Or, [do_parenthesize(T.cast(node.children.fetch(0), LogicNode)), do_parenthesize(T.cast(node.children.fetch(1), LogicNode))])
          (2...node.children.size).each do |i|
            root = LogicNode.new(LogicNodeType::Or, [root, do_parenthesize(T.cast(node.children.fetch(i), LogicNode))])
          end
          root
        end
      elsif node.type == LogicNodeType::Xor
        # XOR is not distributive, so we need to conver this to AND/OR and then parenthesize
        do_parenthesize(do_nnf(node))
      elsif node.type == LogicNodeType::None
        if node.children.size == 2
          LogicNode.new(
            LogicNodeType::Not,
            [
              LogicNode.new(
                LogicNodeType::Or,
                [
                  do_parenthesize(T.cast(node.children.fetch(0), LogicNode)),
                  do_parenthesize(T.cast(node.children.fetch(1), LogicNode))
                ]
              )
            ]
          )
        else
          tree =
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(
                  LogicNodeType::Or,
                  [
                    do_parenthesize(T.cast(node.children.fetch(0), LogicNode)),
                    do_parenthesize(T.cast(node.children.fetch(1), LogicNode))
                  ]
                )
              ]
            )
          (2...node.children.size).each do |i|
            tree = LogicNode.new(LogicNodeType::Or, [tree, do_parenthesize(T.cast(node.children.fetch(i), LogicNode))])
          end
          tree
        end
      else
        node
      end
    end
    private :do_parenthesize

    # @return rewrites the tree so that no node has more than 2 children
    sig { returns(LogicNode) }
    def parenthesize
      do_parenthesize(self)
    end

    # distribute OR over AND
    # A || (B && C) => (A || B) && (A || C)
    # (A && B) || C => (A || C) && (B || C)
    sig { params(left: LogicNode, right: LogicNode).returns(LogicNode) }
    def distribute_or(left, right)
      if left.type == LogicNodeType::And
        lhs =
          distribute_or(
            T.cast(left.children.fetch(0), LogicNode),
            right,
          )
        rhs =
          distribute_or(
            T.cast(left.children.fetch(1), LogicNode),
            right,
          )
        LogicNode.new(LogicNodeType::And, [lhs, rhs])
      elsif right.type == LogicNodeType::And
        lhs =
          distribute_or(
            left,
            T.cast(right.children.fetch(0), LogicNode)
          )
        rhs =
          distribute_or(
            left,
            T.cast(right.children.fetch(1), LogicNode)
          )
        LogicNode.new(LogicNodeType::And, [lhs, rhs])
      else
        LogicNode.new(LogicNodeType::Or, [left, right])
      end
    end
    private :distribute_or

    # rewrite to Conjunctive Normal Form
    sig { params(node: LogicNode).returns(LogicNode) }
    def do_cnf(node)
      if node.type == LogicNodeType::And
        left = do_cnf(T.cast(node.children.fetch(0), LogicNode))
        right = do_cnf(T.cast(node.children.fetch(1), LogicNode))
        LogicNode.new(LogicNodeType::And, [left, right])
      elsif node.type == LogicNodeType::Or
        left = do_cnf(T.cast(node.children.fetch(0), LogicNode))
        right = do_cnf(T.cast(node.children.fetch(1), LogicNode))
        distribute_or(left, right)
      else
        node
      end
    end
    private :do_cnf

    sig { params(node: LogicNode).returns(LogicNode) }
    def flatten_cnf(node)
      if node.type == LogicNodeType::And
        flat_lhs = flatten_cnf(T.cast(node.children.fetch(0), LogicNode))
        flat_rhs = flatten_cnf(T.cast(node.children.fetch(1), LogicNode))
        if flat_lhs.type == LogicNodeType::And && flat_rhs.type == LogicNodeType::And
          LogicNode.new(LogicNodeType::And, flat_lhs.children + flat_rhs.children)
        elsif flat_lhs.type == LogicNodeType::And
          LogicNode.new(LogicNodeType::And, flat_lhs.children + [flat_rhs])
        elsif flat_rhs.type == LogicNodeType::And
          LogicNode.new(LogicNodeType::And, [flat_lhs] + flat_rhs.children)
        else
          LogicNode.new(LogicNodeType::And, [flat_lhs, flat_rhs])
        end
      elsif node.type == LogicNodeType::Or
        flat_lhs = flatten_cnf(T.cast(node.children.fetch(0), LogicNode))
        flat_rhs = flatten_cnf(T.cast(node.children.fetch(1), LogicNode))
        if flat_lhs.type == LogicNodeType::Or && flat_rhs.type == LogicNodeType::Or
          LogicNode.new(LogicNodeType::Or, flat_lhs.children + flat_rhs.children)
        elsif flat_lhs.type == LogicNodeType::Or
          LogicNode.new(LogicNodeType::Or, flat_lhs.children + [flat_rhs])
        elsif flat_rhs.type == LogicNodeType::Or
          LogicNode.new(LogicNodeType::Or, [flat_lhs] + flat_rhs.children)
        else
          LogicNode.new(LogicNodeType::Or, [flat_lhs, flat_rhs])
        end
      else
        node
      end
    end
    private :flatten_cnf

    # @return convert to Conjunctive Normal Form
    sig { returns(LogicNode) }
    def cnf
      n = nnf
      raise "not NNF: #{n}" unless n.is_nnf?
      flatten_cnf(do_cnf(parenthesize.nnf))
    end

    def is_cnf?
      if @type == LogicNodeType::Term
        true
      elsif @type == LogicNodeType::Not
        T.cast(@children.fetch(0), LogicNode).type == LogicNodeType::Term
      elsif @type == LogicNodeType::Or
        @children.all? do |child|
          T.cast(child, LogicNode).type == LogicNodeType::Term || \
            ((T.cast(child, LogicNode).type == LogicNodeType::Not) && \
              T.cast(T.cast(child, LogicNode).children.fetch(0), LogicNode).type == LogicNodeType::Term)
        end
      elsif @type == LogicNodeType::And
        @children.all? do |child|
          T.cast(child, LogicNode).type == LogicNodeType::Term || \
            ((T.cast(child, LogicNode).type == LogicNodeType::Not) && \
              T.cast(T.cast(child, LogicNode).children.fetch(0), LogicNode).type == LogicNodeType::Term) || \
            (T.cast(child, LogicNode).type == LogicNodeType::Or && \
             T.cast(child, LogicNode).is_cnf?)
        end
      else
        false
      end
    end

    sig { params(solver: MiniSat::Solver, node: LogicNode, term_map: T::Hash[TermType, MiniSat::Variable], cur_or: T::nilable(T::Array[T.untyped])).void }
    def to_solver(solver, node, term_map, cur_or)
      if node.type == LogicNodeType::Term
        v = term_map[T.cast(T.cast(node, LogicNode).children.fetch(0), TermType)]
        if cur_or.nil?
          solver << v
        else
          cur_or << v
        end
      elsif node.type == LogicNodeType::Not
        child = T.cast(node.children.fetch(0), LogicNode)
        term = T.cast(child.children.fetch(0), TermType)
        v = -term_map[term]
        if cur_or.nil?
          solver << v
        else
          cur_or << v
        end
      elsif node.type == LogicNodeType::Or
        T.cast(node, LogicNode).children.each do |child|
          to_solver(solver, T.cast(child, LogicNode), term_map, cur_or)
        end
      elsif node.type == LogicNodeType::And
        node.children.each do |child|
          new_or = []
          to_solver(solver, T.cast(child, LogicNode), term_map, new_or)
          solver << new_or
        end
      else
        raise "not in cnf"
      end
    end
    private :to_solver

    # @return true iff self is satisfiable (possible to be true for some combination of term values)
    sig { returns(T::Boolean) }
    def satisfiable?
      c = cnf
      raise "cnf error" unless c.is_cnf?

      t = c.terms

      solver = MiniSat::Solver.new

      term_map = T.let({}, T::Hash[TermType, MiniSat::Variable])
      t.each do |term|
        unless term_map.key?(term)
          term_map[term] = solver.new_var
        end
      end
      raise "term mapping failed" unless t.uniq == term_map.keys

      to_solver(solver, c, term_map, nil)

      solver.solve
      solver.satisfied?
    end

    # @return true iff self and other are logically equivalent (identical truth tables)
    sig { params(other: LogicNode).returns(T::Boolean) }
    def equivalent?(other)
      # equivalent (A <=> B) if the biconditional is true:
      #   (A -> B) && (B -> A)
      #   (!A || B) && (!B || A)

      # equivalence is a tautology iff ~(A <=> B) is a contradiction,
      # i.e., !(A <=> B) is UNSATISFIABLE

      !LogicNode.new(
        LogicNodeType::Not,
        [
          LogicNode.new(
            LogicNodeType::And,
            [
              LogicNode.new(LogicNodeType::Or, [LogicNode.new(LogicNodeType::Not, [self]), other]),
              LogicNode.new(LogicNodeType::Or, [LogicNode.new(LogicNodeType::Not, [other]), self])
            ]
          )
        ]
      )
      .satisfiable?
    end

    sig { params(tree: LogicNode, term_map: T::Hash[TermType, String]).returns(String) }
    def do_to_eqntott(tree, term_map)
      t = tree.type
      case t
      when LogicNodeType::True
        "1"
      when LogicNodeType::False
        "0"
      when LogicNodeType::And
        "(#{tree.children.map { |child| do_to_eqntott(T.cast(child, LogicNode), term_map) }.join(" & ")})"
      when LogicNodeType::Or
        "(#{tree.children.map { |child| do_to_eqntott(T.cast(child, LogicNode), term_map) }.join(" | ")})"
      when LogicNodeType::Xor
        do_to_eqntott(tree.nnf, term_map)
      when LogicNodeType::None
        do_to_eqntott(LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Or, tree.children)]), term_map)
      when LogicNodeType::Term
        term_map.fetch(T.cast(tree.children.fetch(0), TermType))
      when LogicNodeType::Not
        "!(#{do_to_eqntott(T.cast(tree.children.fetch(0), LogicNode), term_map)})"
      when LogicNodeType::If
        do_to_eqntott(tree.nnf, term_map)
      else
        T.absurd(t)
      end
    end

    class EqntottResult < T::Struct
      const :eqn, String
      const :term_map, T::Hash[String, TermType]
    end

    # return equation suitable for `eqntott` input
    sig { returns(EqntottResult) }
    def to_eqntott
      next_term_name = "a"
      term_map = T.let({}, T::Hash[TermType, String])
      t = terms
      t.each do |term|
        unless term_map.key?(term)
          term_map[term] = next_term_name
          next_term_name = next_term_name.next
        end
      end

      EqntottResult.new(eqn: "out = #{do_to_eqntott(self, term_map)}", term_map: term_map.invert)
    end


    sig { returns(LogicNode) }
    def minimize
      eqn_result = to_eqntott
      tt = T.let(nil, T.nilable(String))
      Tempfile.open do |f|
        f.write <<~FILE
          NAME=f;
          #{eqn_result.eqn};
        FILE
        f.flush

        tt = `eqntott -l #{f.path}`
      end

      Tempfile.open do |f|
        f.write T.must(tt)
        f.flush

        result = `espresso -Dso -Dsignature -oeqntott #{f.path}`
        result.lines.each do |line|
          next if line[0] == "."

          if line =~ /out = (.*;)/
            eqn = $1
            return Eqn.new(eqn).to_logic_tree(eqn_result.term_map)
          end
        end

        raise "Could not find equation"
      end

    end

    sig { override.returns(Integer) }
    def hash = to_h.hash

    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      return false unless T.cast(other, Object).is_a?(LogicNode)

      other_node = T.cast(other, LogicNode)
      to_h.eql?(other_node.to_h)
    end
  end
end
