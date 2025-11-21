# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "numbers_and_words"
require "minisat"
require "tempfile"
require "treetop"

require "idlc/symbol_table"
require "udb/eqn_parser"
require "udb/version_spec"

# Implements the LogicNode class, which is used to test for satisfiability/equality/etc of logic
#
# LogicNode isn't meant to used by the "public" API. It is used by the Condition classes, which
# correspond to concepts in the UDB data
#
# @see Condition
module Udb
  # node types in a boolean logic tree
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

  class XlenTerm
    extend T::Sig
    include Comparable

    attr_reader :xlen

    sig { params(xlen: Integer).void }
    def initialize(xlen)
      @xlen = xlen
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(Condition) }
    def to_condition(cfg_arch)
      Condition.new({ "xlen" => @xlen }, cfg_arch)
    end

    sig { override.returns(String) }
    def to_s
      "xlen=#{@xlen}"
    end

    sig { returns(String) }
    def to_s_pretty = to_s

    sig { returns(String) }
    def to_asciidoc = "xlen+++()+++ == #{@xlen}"

    sig { returns(T::Hash[String, Integer]) }
    def to_h
      {
        "xlen" => @xlen
      }
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch)
      "(xlen() == #{@xlen})"
    end

    sig {
      override
      .params(other: T.untyped)
      .returns(T.nilable(Integer))
      .checked(:never)
    }
    def <=>(other)
      return nil unless other.is_a?(XlenTerm)

      @xlen <=> other.xlen
    end

    # hash and eql? must be implemented to use ExtensionTerm as a Hash key
    sig { override.returns(Integer) }
    def hash = to_s.hash

    sig {
      override
      .params(other: T.untyped)
      .returns(T::Boolean)
      .checked(:never)
    }
    def eql?(other)
      return false unless other.is_a?(XlenTerm)

      (self <=> other) == 0
    end
  end

  # a terminal for an Extension with a version specifier (a-la an ExtensionRequirement)
  # we don't use ExtensionRequirement for terminals just to keep LogicNode independent of the rest of UDB
  class ExtensionTerm
    extend T::Sig
    include Comparable

    class ComparisonOp < T::Enum
      enums do
        Equal = new("=")
        GreaterThanOrEqual = new(">=")
        GreaterThan = new(">")
        LessThanOrEqual = new("<=")
        LessThan = new("<")
        Compatible = new("~>")
      end
    end

    sig { returns(String) }
    attr_reader :name

    sig { returns(VersionSpec) }
    attr_reader :version

    sig { returns(ComparisonOp) }
    def comparison = @op

    sig { params(name: String, op: T.any(ComparisonOp, String), ver: T.any(String, VersionSpec)).void }
    def initialize(name, op, ver)
      @name = name
      @op = T.let(
        if op.is_a?(String)
          ComparisonOp.deserialize(op)
        else
          op
        end,

        ComparisonOp)
      @version = ver.is_a?(String) ? VersionSpec.new(ver) : ver
    end

    sig { returns(T::Boolean) }
    def matches_any_version?
      @op == ComparisonOp::Equal && @version == VersionSpec.new("0")
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(ExtensionRequirement) }
    def to_ext_req(cfg_arch)
      cfg_arch.extension_requirement(@name, "#{@op.serialize} #{@version}")
    end


    sig { params(cfg_arch: ConfiguredArchitecture).returns(ExtensionVersion) }
    def to_ext_ver(cfg_arch)
      raise "Not an extension version" unless @op == ComparisonOp::Equal

      cfg_arch.extension_version(@name, @version.to_s)
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(Condition) }
    def to_condition(cfg_arch)
      Condition.new({ "extension" => { "name" => name, "version" => "#{@op.serialize} #{@version}" } }, cfg_arch)
    end

    sig { override.returns(String) }
    def to_s
      "#{@name}#{@op.serialize}#{@version}"
    end

    sig { returns(String) }
    def to_s_pretty
      "Extension #{@name}, version #{@version}"
    end

    sig { returns(T::Hash[String, String]) }
    def to_h
      {
        "name" => @name,
        "version" => "#{@op.serialize} #{@version}"
      }
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch)
      if @op == ComparisonOp::GreaterThanOrEqual && @version.eql?("0")
        "implemented?(ExtensionName::#{@name})"
      else
        "implemented_version?(ExtensionName::#{@name}, \"#{@op.serialize} #{@version}\")"
      end
    end

    # return the minimum version possible that would satisfy this term
    def min_possible_version
      case @op
      when ComparisonOp::Equal, ComparisonOp::GreaterThanOrEqual, ComparisonOp::Compatible
        @version
      when ComparisonOp::GreaterThan
        @version.increment_patch
      when ComparisonOp::LessThanOrEqual, ComparisonOp::LessThan
        VersionSpec.new("0")
      else
        T.absurd(@op)
      end
    end

    # return the maximum version possible that would satisfy this term
    sig { returns(VersionSpec) }
    def max_possible_version
      case @op
      when ComparisonOp::Equal, ComparisonOp::LessThanOrEqual, ComparisonOp::Compatible
        @version
      when ComparisonOp::LessThan
        if @version.zero?
          nil
        else
          @version.decrement_patch
        end
      when ComparisonOp::GreaterThanOrEqual, ComparisonOp::GreaterThan
        VersionSpec.new("0")
      else
        T.absurd(@op)
      end
    end

    sig {
      override
      .params(other: T.untyped)
      .returns(T.nilable(Integer))
      .checked(:never)
    }
    def <=>(other)
      return nil unless other.is_a?(ExtensionTerm)

      other_ext = other
      if @op == ComparisonOp::Equal && other_ext.comparison == ComparisonOp::Equal
        if @name == other_ext.name
          T.must(@version <=> other_ext.version)
        else
          T.must(@name <=> other_ext.name)
        end
      else
        if @name == other_ext.name
          if min_possible_version == other_ext.min_possible_version
            max_possible_version <=> other_ext.max_possible_version
          else
            min_possible_version <=> other_ext.min_possible_version
          end
        else
          T.must(@name <=> other_ext.name)
        end
      end
    end

    # hash and eql? must be implemented to use ExtensionTerm as a Hash key
    sig { override.returns(Integer) }
    def hash = to_s.hash

    sig {
      override
      .params(other: T.untyped)
      .returns(T::Boolean)
      .checked(:never)
    }
    def eql?(other)
      return false unless other.is_a?(ExtensionTerm)

      (self <=> other) == 0
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
        OneOf = new("oneOf")
      end
    end

    ValueType = T.type_alias { T.any(Integer, String, T::Boolean, T::Array[T.any(Integer, String)]) }

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

    sig { returns(T.nilable(T::Boolean)) }
    def size = @yaml["size"]

    sig { returns(T::Boolean) }
    def array_comparison? = @yaml.key?("index") || @yaml.key?("size") || @yaml.key?("includes")

    sig { returns(ValueType) }
    def comparison_value
      @yaml.fetch(comparison_type.serialize)
    end

    # return a negated version of self, or nil if no simple negation exists
    sig { returns(T.nilable(ParameterTerm)) }
    def negate
      if @yaml.key?("equal")
        new_yaml = @yaml.dup
        new_yaml["not_equal"] = @yaml["equal"]
        new_yaml.delete("equal")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("not_equal")
        new_yaml = @yaml.dup
        new_yaml["equal"] = @yaml["not_equal"]
        new_yaml.delete("not_equal")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("less_than")
        new_yaml = @yaml.dup
        new_yaml["greater_than_or_equal"] = @yaml["less_than"]
        new_yaml.delete("less_than")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("greater_than")
        new_yaml = @yaml.dup
        new_yaml["less_than_or_equal"] = @yaml["greater_than"]
        new_yaml.delete("greater_than")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("less_than_or_equal")
        new_yaml = @yaml.dup
        new_yaml["greater_than"] = @yaml["less_than_or_equal"]
        new_yaml.delete("less_than_or_equal")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("greater_than_or_equal")
        new_yaml = @yaml.dup
        new_yaml["less_than"] = @yaml["greater_than_or_equal"]
        new_yaml.delete("greater_than_or_equal")
        ParameterTerm.new(new_yaml)
      elsif @yaml.key?("includes")
        nil
      elsif @yaml.key?("oneOf")
        nil
      else
        raise "No comparison found in [#{@yaml.keys}]"
      end
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
      elsif @yaml.key?("oneOf")
        ParameterComparisonType::OneOf
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
        (value.include?(@yaml["includes"])) ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterComparisonType::OneOf
        (@yaml["oneOf"].include?(value)) ? SatisfiedResult::Yes : SatisfiedResult::No
      else
        T.absurd(t)
      end
    end

    sig { params(param_values: T::Hash[String, T.untyped]).returns(SatisfiedResult) }
    def _eval(param_values)
      val = param_values[name]

      # don't have the value, so can't say either way
      return SatisfiedResult::Maybe if val.nil?

      if val.is_a?(Array)
        raise "Missing index, includes, or size key in #{@yaml}" unless array_comparison?

        if @yaml.key?("index")
          raise "Index out of range" if T.cast(@yaml.fetch("index"), Integer) >= T.cast(val, Array).size

          value = val.fetch(@yaml.fetch("index"))
          eval_value(value)
        elsif @yaml.key?("includes")
          eval_value(val)
        elsif @yaml.key?("size")
          value = val.size
          eval_value(value)
        else
          raise "unreachable"
        end
      elsif val.is_a?(Integer)
        if @yaml.key?("range")
          msb, lsb = @yaml.fetch("range").split("-").map(&:to_i)
          eval_value((val >> lsb) & (1 << (msb - lsb)))
        else
          eval_value(val)
        end
      else
        eval_value(val)
      end
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
    def eval(cfg_arch)
      p = cfg_arch.param(name)

      # we know nothing at all about this param. it might not even be valid
      return SatisfiedResult::No if p.nil?

      # since conditions are involved in ConfiguredArchitecture creation
      # (to, for example, determine the list of implemented extensions)
      # we use the parameter values directly from the config instead of the symtab
      # (which may not be constructed yet)
      _eval(cfg_arch.config.param_values)
    end

    sig { params(param_values: T::Hash[String, T.untyped]).returns(SatisfiedResult) }
    def partial_eval(param_values) = _eval(param_values)

    sig { returns(T::Hash[String, T.untyped]) }
    def to_h
      @yaml
    end

    sig { params(cfg_arch: T.nilable(ConfiguredArchitecture)).returns(String) }
    def to_idl(cfg_arch)
      t = comparison_type
      case t
      when ParameterComparisonType::Equal
        if comparison_value.is_a?(String)
          "(#{param_to_s}==\"#{comparison_value}\")"
        else
          "(#{param_to_s}==#{comparison_value})"
        end
      when ParameterComparisonType::NotEqual
        if comparison_value.is_a?(String)
          "(#{param_to_s}!=\"#{comparison_value}\")"
        else
          "(#{param_to_s}!=#{comparison_value})"
        end
      when ParameterComparisonType::LessThan
        "(#{param_to_s}<#{comparison_value})"
      when ParameterComparisonType::GreaterThan
        "(#{param_to_s}>#{comparison_value})"
      when ParameterComparisonType::LessThanOrEqual
        "(#{param_to_s}<=#{comparison_value})"
      when ParameterComparisonType::GreaterThanOrEqual
        "(#{param_to_s}>=#{comparison_value})"
      when ParameterComparisonType::Includes
        "$array_includes?(#{param_to_s}, #{comparison_value})"
      when ParameterComparisonType::OneOf
        "(#{T.cast(comparison_value, T::Array[T.any(Integer, String)]).map { |v| "#{param_to_s}==#{v}" }.join("||")})"
      else
        T.absurd(t)
      end
    end

    def to_asciidoc
      padoc =
        index.nil? \
          ? name
          : "#{name}[#{index}]"
      type = comparison_type
      case type
      when ParameterTerm::ParameterComparisonType::Equal
        "`#{padoc}` == #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::NotEqual
        "`#{padoc}` != #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::LessThan
        "`#{padoc}` < #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::GreaterThan
        "`#{padoc}` > #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::LessThanOrEqual
        "`#{padoc}` <= #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::GreaterThanOrEqual
        "`#{padoc}` >= #{comparison_value}"
      when ParameterTerm::ParameterComparisonType::Includes
        "#{comparison_value} in `#{padoc}`"
      when ParameterTerm::ParameterComparisonType::OneOf
        "`#{padoc}` in [#{@yaml["oneOf"].join(", ")}]"
      else
        T.absurd(type)
      end
    end

    sig { returns(String) }
    def param_to_s
      if !index.nil?
        "#{name}[#{index}]"
      elsif !size.nil?
        "$array_size(#{name})"
      else
        name
      end
    end

    sig { override.returns(String) }
    def to_s
      # just return IDL
      to_idl(nil)
    end

    sig { returns(String) }
    def to_s_pretty
      t = comparison_type
      i = index
      if i.nil?
        case t
        when ParameterComparisonType::Equal
          "Paremeter #{@name} equals #{comparison_value}"
        when ParameterComparisonType::NotEqual
          "Paremeter #{@name} does not equal #{comparison_value}"
        when ParameterComparisonType::LessThan
          "Paremeter #{@name} is less than #{comparison_value}"
        when ParameterComparisonType::GreaterThan
          "Paremeter #{@name} is greater than #{comparison_value}"
        when ParameterComparisonType::LessThanOrEqual
          "Paremeter #{@name} is less than or equal to #{comparison_value}"
        when ParameterComparisonType::GreaterThanOrEqual
          "Paremeter #{@name} is greater than or equal to #{comparison_value}"
        when ParameterComparisonType::Includes
          "Paremeter #{@name} (an array) includes the value #{comparison_value}"
        when ParameterComparisonType::OneOf
          "Paremeter #{@name} is one of the following values: #{comparison_value}"
        else
          T.absurd(t)
        end
      else
        case t
        when ParameterComparisonType::Equal
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} equals #{comparison_value}"
        when ParameterComparisonType::NotEqual
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} does not equal #{comparison_value}"
        when ParameterComparisonType::LessThan
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} is less than #{comparison_value}"
        when ParameterComparisonType::GreaterThan
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} is greater than #{comparison_value}"
        when ParameterComparisonType::LessThanOrEqual
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} is less than or equal to #{comparison_value}"
        when ParameterComparisonType::GreaterThanOrEqual
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} is greater than or equal to #{comparison_value}"
        when ParameterComparisonType::Includes
          raise "Cannot occur"
        when ParameterComparisonType::OneOf
          "The #{i.to_words(ordinal: true, remove_hyphen: true)} element of paremeter #{@name} equals on of the following values: #{comparison_value}"
        else
          T.absurd(t)
        end
      end
    end

    sig { returns(T::Boolean) }
    def param_is_array?
      @yaml.keys.any? { |k| ["index", "includes", "size"].include?(k) }
    end

    # if self and other_param had a well-defined logical relationship, return it
    # otherwise, return nil
    # *note*: this is only one half of the relationship. to get the whole picture, need to use
    # self.relation_to(other_param) && other_param.relation_to(self)
    sig { params(other_param: ParameterTerm).returns(T.nilable(LogicNode)) }
    def relation_to(other_param)
      return nil unless name == other_param.name

      self_implies_other =
        LogicNode.new(LogicNodeType::If, [LogicNode.new(LogicNodeType::Term, [self]), LogicNode.new(LogicNodeType::Term, [other_param])])

      self_implies_not_other =
        LogicNode.new(LogicNodeType::If, [LogicNode.new(LogicNodeType::Term, [self]), LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [other_param])])])

      if param_is_array?
        if @yaml.key?("includes")
          if other_param.to_h.key?("index") && other_param.to_h.key?("equals") && (other_param.to_h.fetch("equals") == @yaml.fetch("includes"))
            self_implies_other
          elsif other_param.to_h.key?("size") && other_param.to_h.key?("equals") && (other_param.to_h.fetch("equals") == 0)
            self_implies_not_other
          elsif other_param.to_h.key?("size") && other_param.to_h.key?("not_equal") && (other_param.to_h.fetch("not_equal") == 0)
            self_implies_other
          elsif other_param.to_h.key?("size") && other_param.to_h.key?("greater_than") && (other_param.to_h.fetch("greater_than") == 0)
            self_implies_other
          end
        elsif @yaml.key?("size")
          scalar_relation_to(other_param, self_implies_other, self_implies_not_other)
        elsif @yaml.key?("index") && other_param.to_h.key?("index") && @yaml.fetch("index") == other_param.to_h.fetch("index")
          scalar_relation_to(other_param, self_implies_other, self_implies_not_other)
        end
      else
        scalar_relation_to(other_param, self_implies_other, self_implies_not_other)
      end
    end

    # @api private
    sig { params(other_param: ParameterTerm, self_implies_other: LogicNode, self_implies_not_other: LogicNode).returns(T.nilable(LogicNode)) }
    def scalar_relation_to(other_param, self_implies_other, self_implies_not_other)
      op = comparison_type
      other_op = other_param.comparison_type

      case op
      when ParameterComparisonType::Equal
        case other_op
        when ParameterComparisonType::Equal
          if comparison_value != other_param.comparison_value
            self_implies_not_other
          else
            self_implies_other
          end
        when ParameterComparisonType::NotEqual
          if comparison_value != other_param.comparison_value
            if comparison_value.is_a?(TrueClass) || comparison_value.is_a?(FalseClass)
              self_implies_other
            end
          else
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_other
          else
            self_implies_not_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          else
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, Integer) > T.cast(other_param.comparison_value, Integer)
            self_implies_other
          else
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, Integer) >= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          else
            self_implies_not_other
          end
        when ParameterComparisonType::OneOf
          if T.cast(other_param.comparison_value, T::Array[T.any(String, Integer)]).include?(comparison_value)
            self_implies_other
          else
            self_implies_not_other
          end
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::NotEqual
        case other_op
        when ParameterComparisonType::Equal
          if comparison_value != other_param.comparison_value
            if comparison_value.is_a?(TrueClass) || comparison_value.is_a?(FalseClass)
              self_implies_other
            end
          else
            self_implies_other
          end
        when ParameterComparisonType::NotEqual
          if comparison_value != other_param.comparison_value # otherwise, this would be self-comparison
            if comparison_value.is_a?(TrueClass) || comparison_value.is_a?(FalseClass)
              self_implies_not_other
            end
          else
            self_implies_other
          end
        when ParameterComparisonType::LessThan,
              ParameterComparisonType::LessThanOrEqual,
              ParameterComparisonType::GreaterThan,
              ParameterComparisonType::GreaterThanOrEqual,
              ParameterComparisonType::OneOf
          # nothing to say here.
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::LessThan
        case other_op
        when ParameterComparisonType::Equal
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::NotEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::OneOf
          if T.cast(other_param.comparison_value, T::Array[Integer]).all? { |v| v >= T.cast(comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::LessThanOrEqual
        case other_op
        when ParameterComparisonType::Equal
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::NotEqual
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::OneOf
          if T.cast(other_param.comparison_value, T::Array[Integer]).all? { |v| v > T.cast(comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::GreaterThan
        case other_op
        when ParameterComparisonType::Equal
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::NotEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, Integer) >= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, Integer) > T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::OneOf
          if T.cast(other_param.comparison_value, T::Array[Integer]).all? { |v| v <= T.cast(comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::Includes
          # if self is a size operation and size is 0, we can know that other_param does not include
          # otherwise, we know nothing
          if @yaml.key?("size") && size == 0
            self_implies_not_other
          end
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::GreaterThanOrEqual
        case other_op
        when ParameterComparisonType::Equal
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::NotEqual
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, Integer) < T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, Integer) <= T.cast(other_param.comparison_value, Integer)
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, Integer) > T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, Integer) >= T.cast(other_param.comparison_value, Integer)
            self_implies_other
          end
        when ParameterComparisonType::OneOf
          if T.cast(other_param.comparison_value, T::Array[Integer]).all? { |v| v < T.cast(comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::OneOf
        case other_op
        when ParameterComparisonType::Equal
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v != T.cast(other_param.comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::NotEqual
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v != T.cast(other_param.comparison_value, Integer) }
            self_implies_other
          end
        when ParameterComparisonType::LessThan
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v >= T.cast(other_param.comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::LessThanOrEqual
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v > T.cast(other_param.comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThan
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v <= T.cast(other_param.comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::GreaterThanOrEqual
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| v < T.cast(other_param.comparison_value, Integer) }
            self_implies_not_other
          end
        when ParameterComparisonType::OneOf
          # self implies other if all in set set are also in other set
          if T.cast(comparison_value, T::Array[Integer]).all? { |v| T.cast(other_param.comparison_value, T::Array[Integer]).include?(v) }
            self_implies_other
          end
        when ParameterComparisonType::Includes
          raise "impossible"
        else
          T.absurd(other_op)
        end
      when ParameterComparisonType::Includes
        raise "impossible"
      else
        T.absurd(op)
      end
    end

    sig {
      override
      .params(other: T.untyped)
      .returns(T.nilable(Integer))
      .checked(:never)
    }
    def <=>(other)
      return nil unless other.is_a?(ParameterTerm)

      other_param = other
      if name != other_param.name
        name <=> other_param.name
      elsif !index.nil? && !other_param.index.nil? && index != other_param.index
        T.must(index) <=> T.must(other_param.index)
      elsif size != other.size
        # one is a size operator and one isn't.
        size.nil? ? 1 : -1
      elsif @yaml.key?("includes") || other_param.to_h.key?("includes")
        if @yaml.key?("includes") && other_param.to_h.key?("includes")
          @yaml.fetch("includes") <=> other_param.to_h.fetch("includes")
        elsif @yaml.key?("includes") && !other_param.to_h.key?("includes")
          1
        elsif !@yaml.key?("includes") && other_param.to_h.key?("includes")
          -1
        end
      elsif @yaml.key?("oneOf") || other_param.to_h.key?("oneOf")
        if @yaml.key?("oneOf") && other_param.to_h.key?("oneOf")
          @yaml.fetch("oneOf") <=> other_param.to_h.fetch("oneOf")
        elsif @yaml.key?("oneOf")
          1
        else
          -1
        end
      elsif comparison_type != other_param.comparison_type
        comparison_type <=> other_param.comparison_type
      elsif comparison_value != other_param.comparison_value
        cv = comparison_value
        if cv.is_a?(String)
          cv <=> T.cast(other_param.comparison_value, String)
        elsif cv.is_a?(Array)
          cv <=> T.cast(other_param.comparison_value, T::Array[T.any(String, T::Boolean, Integer)])
        else
          T.cast(comparison_value, Integer) <=> T.cast(other_param.comparison_value, Integer)
        end
      else
        # these are the same (ignoring reason)
        return 0
      end
    end

    # hash and eql? must be implemented to use ParameterTerm as a Hash key
    sig {
      override
      .returns(Integer)
      .checked(:never)
    }
    def hash = @yaml.hash

    sig {
      override
      .params(other: T.untyped)
      .returns(T::Boolean)
      .checked(:never)
    }
    def eql?(other)
      return false unless other.is_a?(ParameterTerm)

      (self <=> other) == 0
    end
  end

  # @api private
  # represents a "free" term, i.e., one that is not bound to the problem at hand
  # used by the Tseytin Transformation, which introduces new propositions to represent
  # subformula
  class FreeTerm
    extend T::Sig
    include Comparable

    @next_id = 1

    sig { returns(Integer) }
    attr_reader :id

    sig { void }
    def initialize
      @id = FreeTerm.instance_variable_get(:@next_id)
      FreeTerm.instance_variable_set(:@next_id, @id + 1)
    end

    sig {
      override
      .returns(String)
    }
    def to_s
      "t#{@id}"
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch)
      "FreeTerm"
    end

    def to_h = {}

    sig { returns(String) }
    def to_s_pretty = to_s

    sig {
      override
      .params(other: T.untyped)
      .returns(T.nilable(Integer))
      .checked(:never)
    }
    def <=>(other)
      return nil unless other.is_a?(FreeTerm)

      @id <=> other.id
    end

    # hash and eql? must be implemented to use ParameterTerm as a Hash key
    sig {
      override
      .returns(Integer)
      .checked(:never)
    }
    def hash = @id.hash

    sig {
      override
      .params(other: T.untyped)
      .returns(T::Boolean)
      .checked(:never)
    }
    def eql?(other)
      return false unless other.is_a?(FreeTerm)

      (self <=> other) == 0
    end
  end

  TermType = T.type_alias { T.any(ExtensionTerm, ParameterTerm, XlenTerm, FreeTerm) }

  # Abstract syntax tree of the condition logic
  class LogicNode
    extend T::Sig

    # statistics counters
    def self.reset_stats
      @num_brute_force_sat_solves = 0
      @time_brute_force_sat_solves = 0
      @num_minisat_sat_solves = 0
      @time_minisat_sat_solves = 0
      @num_minisat_cache_hits = 0
    end

    reset_stats

    def self.num_brute_force_sat_solves
      @num_brute_force_sat_solves
    end

    def self.inc_brute_force_sat_solves
      @num_brute_force_sat_solves += 1
    end

    def self.num_minisat_sat_solves
      @num_minisat_sat_solves
    end

    def self.inc_minisat_sat_solves
      @num_minisat_sat_solves += 1
    end

    def self.num_minisat_cache_hits
      @num_minisat_cache_hits
    end

    def self.inc_minisat_cache_hits
      @num_minisat_cache_hits += 1
    end


    ChildType = T.type_alias { T.any(LogicNode, TermType) }

    sig { returns(LogicNodeType) }
    attr_reader :type

    sig { returns(T::Array[ChildType]) }
    attr_reader :children

    # object to hold results of expensive calculations
    # LogicNode type and children are frozen at construction so
    # we can safely remember and return these values
    class MemoizedState < T::Struct
      # when true, the formula is known to be in CNF form
      # when false, the formula is known to not be in CNF form
      prop :is_cnf, T.nilable(T::Boolean)

      # when not nil, an equisatisfiable representation of self in CNF form
      prop :cnf_form, T.nilable(LogicNode)

      # when true, a flattened version of the formula would be CNF
      # when false, a flattened version of the formula would not be CNF
      prop :is_nested_cnf, T.nilable(T::Boolean)

      # when true, the formula would be unaltered by calling reduce
      # when false, the formula would be reduced further by calling reduce
      prop :is_reduced, T.nilable(T::Boolean)

      # list of terms in the formula
      prop :terms, T.nilable(T::Array[TermType])

      # list of literals in the formula
      prop :literals, T.nilable(T::Array[TermType])

      # when true, formula is known to be satisfiable
      # when false, formula is known to be unsatisfiable
      prop :is_satisfiable, T.nilable(T::Boolean)

      # result of #equisat_cnf
      prop :equisat_cnf, T.nilable(LogicNode)

      # result of #equisat_cnf
      prop :equiv_cnf, T.nilable(LogicNode)
    end

    attr_accessor :memo

    sig { params(type: LogicNodeType, children: T::Array[ChildType]).void }
    def initialize(type, children)
      if [LogicNodeType::Term, LogicNodeType::Not].include?(type) && children.size != 1
        raise ArgumentError, "Children must be singular"
      end
      if [LogicNodeType::And, LogicNodeType::Or, LogicNodeType::Xor, LogicNodeType::None, LogicNodeType::If].include?(type) && children.size < 2
        raise ArgumentError, "Children must have at least two elements"
      end

      @children = children
      @children.freeze
      @node_children = (@type == LogicNodeType::Term) ? nil : T.cast(@children, T::Array[LogicNode])


      if [LogicNodeType::True, LogicNodeType::False].include?(type) && !children.empty?
        raise ArgumentError, "Children must be empty"
      elsif type == LogicNodeType::Term
        # ensure the children are TermType
        children.each { |child| T.assert_type!(T.cast(child, TermType), TermType) }
      else
        # raise ArgumentError, "All Children must be LogicNodes" unless children.all? { |child| child.is_a?(LogicNode) }
      end

      @type = type
      @type.freeze

      # used for memoization in transformation routines
      @memo = MemoizedState.new(
        is_cnf: nil,
        is_nested_cnf: nil,
        is_reduced: nil,
        terms: nil,
        literals: nil,
        is_satisfiable: nil,
        equisat_cnf: nil,
        equiv_cnf: nil
      )
    end

    # @api private
    sig { returns(T::Array[LogicNode]) }
    def node_children
      @node_children
    end

    True = LogicNode.new(LogicNodeType::True, [])
    True.memo.is_cnf = true
    True.memo.is_nested_cnf = true
    True.memo.is_reduced = true
    True.memo.cnf_form = True
    True.memo.terms = [].freeze
    True.memo.literals = [].freeze
    True.freeze

    False = LogicNode.new(LogicNodeType::False, [])
    False.memo.is_cnf = true
    False.memo.is_nested_cnf = true
    False.memo.is_reduced = true
    False.memo.cnf_form = False
    False.memo.terms = [].freeze
    False.memo.literals = [].freeze
    False.freeze

    Xlen32 = LogicNode.new(LogicNodeType::Term, [XlenTerm.new(32).freeze]).freeze
    Xlen64 = LogicNode.new(LogicNodeType::Term, [XlenTerm.new(64).freeze]).freeze

    # If ext_req is false, can this logic tree be satisfied?
    sig { params(ext_req: ExtensionRequirement).returns(T::Boolean) }
    def satisfiability_depends_on_ext_req?(ext_req)
      # the tree needs something in ext_vers if it is always
      # unsatisfiable when the corresponding ExtensionTerms are false
      cb = LogicNode.make_eval_cb do |term|
        case term
        when ExtensionTerm
          ext_req.satisfied_by?(term.to_ext_req(ext_req.cfg_arch)) \
            ? SatisfiedResult::No
            : SatisfiedResult::Maybe
        when ParameterTerm
          SatisfiedResult::Maybe
        when FreeTerm
          SatisfiedResult::No
        when XlenTerm
          SatisfiedResult::Maybe
        else
          T.absurd(term)
        end
      end
      eval_cb(cb) == SatisfiedResult::No
    end

    # @return The unique terms (leafs) of this tree
    sig { returns(T::Array[TermType]) }
    def terms
      @memo.terms ||= literals.uniq
    end

    # @return The unique terms (leafs) of this tree, exculding antecendents of an IF
    sig { returns(T::Array[TermType]) }
    def terms_no_antecendents
      if @type == LogicNodeType::If
        node_children.fetch(1).terms_no_antecendents
      elsif @type == LogicNodeType::Term
        [T.cast(@children.fetch(0), TermType)]
      else
        node_children.map { |child| child.terms_no_antecendents }.flatten.uniq
      end
    end

    # @return all literals in the tree
    # unlike #terms, this list will include leaves that are equivalent
    sig { returns(T::Array[TermType]) }
    def literals
      @memo.literals ||=
        if @type == LogicNodeType::Term
          [@children.fetch(0)]
        else
          node_children.map { |child| child.literals }.flatten
        end
    end


    sig { params(mterms: T::Array[String], group_by: String).returns(T::Hash[Integer, T::Array[String]]) }
    def self.group_mterms(mterms, group_by)
      groups = T.let({}, T::Hash[Integer, T::Array[String]])
      mterms.each do |mterm|
        n = mterm.count(group_by)
        groups[n] ||= []
        groups.fetch(n) << mterm
      end
      groups
    end

    class PairMintermsResult < T::Struct
      const :new_group, T::Array[String]
      const :matched_mterms, T::Set[String]
    end

    sig { params(group1: T::Array[String], group2: T::Array[String]).returns(PairMintermsResult) }
    def self.pair_mterms(group1, group2)
      new_group = []
      matched = Set.new
      group1.each do |m1|
        group2.each do |m2|
          diff_count = 0
          diff_index = -1
          loop_index = 0
          m1.each_char do |bit|
            if bit != m2[loop_index]
              diff_count += 1
              diff_index = loop_index
            end
            loop_index += 1
          end
          if diff_count == 1
            new_mterm = m1.dup
            new_mterm[diff_index] = "-"
            new_group << new_mterm
            matched.add(m1)
            matched.add(m2)
          end
        end
      end
      PairMintermsResult.new(new_group: new_group.uniq, matched_mterms: matched)
    end


    def self.prime_implicant_covers_mterm?(implicant, minterm)
      implicant.chars.zip(minterm.chars).all? do |i_bit, m_bit|
        i_bit == "-" || i_bit == m_bit
      end
    end

    class PrimeImplicantsResult < T::Struct
      const :essential, T::Array[String]
      const :minimal, T::Array[String]
    end

    # given a list of minterms/maxterms, each represented by a string of "0" and "1",
    # return the prime implicants, represented by a string of "0", "1", and "-"
    sig { params(mterms: T::Array[String], group_by: String).returns(PrimeImplicantsResult) }
    def self.find_prime_implicants(mterms, group_by)
      groups = group_mterms(mterms, group_by)

      # Pair mterms until no further simplification is possible
      prime_implicants = T.let([], T::Array[String])
      matched = T.let(Set.new, T::Set[String])
      while groups.size > 1
        new_groups = Hash.new { |h, k| h[k] = [] }
        matched.clear
        groups.keys.sort.each_cons(2) do |k1, k2|
          res = pair_mterms(T.must(groups[T.must(k1)]), T.must(groups[T.must(k2)]))
          matched.merge(res.matched_mterms)
          new_group = res.new_group
          new_groups[k1] += new_group unless new_group.empty?
        end
        prime_implicants += groups.values.flatten.reject { |mterm| matched.include?(mterm) }
        groups = new_groups
      end
      prime_implicants += groups.values.flatten.reject { |mterm| matched.include?(mterm) }
      prime_implicants.uniq!

      coverage = Hash.new { |h, k| h[k] = [] }

      mterms.each do |minterm|
        prime_implicants.each_with_index do |implicant, idx|
          if prime_implicant_covers_mterm?(implicant, minterm)
            coverage[minterm] << idx
          end
        end
      end

      essential_indices = []
      uncovered = mterms.dup

      # Find essential prime implicants
      coverage.each do |mterm, implicant_indices|
        if implicant_indices.size == 1
          idx = implicant_indices.first
          unless essential_indices.include?(idx)
            essential_indices << idx
            # Remove all minterms covered by this implicant
            uncovered.reject! { |m| prime_implicant_covers_mterm?(prime_implicants.fetch(idx), m) }
          end
        end
      end

      minimal_indices = essential_indices.dup
      # Greedy selection for remaining minterms
      while uncovered.any?
        best_idx = T.cast(prime_implicants.each_with_index.max_by do |implicant, idx|
          uncovered.count { |m| prime_implicant_covers_mterm?(implicant, m) }
        end, T::Array[Integer]).last

        minimal_indices << best_idx
        uncovered.reject! { |m| prime_implicant_covers_mterm?(prime_implicants.fetch(T.must(best_idx)), m) }
      end

      PrimeImplicantsResult.new(
        essential: essential_indices.map { |i| prime_implicants.fetch(i) },
        minimal:  minimal_indices.map { |i| prime_implicants.fetch(i) }
      )
    end

    class CanonicalizationType < T::Enum
      enums do
        SumOfProducts = new
        ProductOfSums = new
      end
    end

    sig { params(result_type: CanonicalizationType).returns(LogicNode) }
    def quine_mccluskey(result_type)
      # map terms to indicies for later
      nterms = terms.size
      if nterms.zero?
        # trival case; this is either true or false
        assert_cb = LogicNode.make_eval_cb do |term|
          raise "unreachable"
        end
        return eval_cb(assert_cb) == SatisfiedResult::Yes ? LogicNode::True : LogicNode::False
      end
      term_idx = T.let({}, T::Hash[TermType, Integer])
      terms.each_with_index do |term, idx|
        term_idx[term] = idx
      end

      # mterms are either minterms (for sum-of-products) or maxterms (for product-of-sums)
      mterms =
        case result_type
        when CanonicalizationType::SumOfProducts
          minterms = T.let([], T::Array[String])
          (1 << nterms).times do |val|
            cb = LogicNode.make_eval_cb do |term|
              ((val >> term_idx.fetch(term)) & 1).zero? ? SatisfiedResult::No : SatisfiedResult::Yes
            end
            if eval_cb(cb) == SatisfiedResult::Yes
              minterms << val.to_s(2).rjust(nterms, "0")
            end
          end
          minterms
        when CanonicalizationType::ProductOfSums
          maxterms = T.let([], T::Array[String])
          (1 << nterms).times do |val|
            cb = LogicNode.make_eval_cb do |term|
              ((val >> term_idx.fetch(term)) & 1).zero? ? SatisfiedResult::No : SatisfiedResult::Yes
            end
            if eval_cb(cb) == SatisfiedResult::No
              # swap 0's and 1's since maxterms are inverted
              maxterms << val.to_s(2).gsub("0", "X").gsub("1", "0").gsub("X", "1").rjust(nterms, "1")
            end
          end
          maxterms
        else
          T.absurd(result_type)
        end

      if mterms.empty?
        if result_type == CanonicalizationType::SumOfProducts
          return False
        else
          return True
        end
      end

      primes = LogicNode.find_prime_implicants(mterms, result_type == CanonicalizationType::SumOfProducts ? "1" : "0")
      min_primes = primes.minimal

      if (result_type == CanonicalizationType::SumOfProducts)
        products = T.let([], T::Array[LogicNode])
        min_primes.each do |p|
          product = T.let([], T::Array[LogicNode])
          p = p.reverse
          p.size.times do |idx|
            if p[idx] == "1"
              product << LogicNode.new(LogicNodeType::Term, [terms.fetch(idx)])
            elsif p[idx] == "0"
              product << LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [terms.fetch(idx)])])
            end
          end
          if product.size == 0
            # trivially satisfiable
            products << True
          elsif product.size == 1
            products << product.fetch(0)
          else
            products << LogicNode.new(LogicNodeType::And, product)
          end
        end

        if products.size == 0
          # trivially satisfiable
          True
        elsif products.size == 1
          products.fetch(0)
        else
          LogicNode.new(LogicNodeType::Or, products)
        end
      elsif result_type == CanonicalizationType::ProductOfSums
        sums = T.let([], T::Array[LogicNode])
        min_primes.each do |p|
          sum = T.let([], T::Array[LogicNode])
          p = p.reverse
          p.size.times do |idx|
            if p[idx] == "1"
              sum << LogicNode.new(LogicNodeType::Term, [terms.fetch(idx)])
            elsif p[idx] == "0"
              sum << LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [terms.fetch(idx)])])
            end
          end
          if sum.size == 0
            # unsatisfiable
            sums << False
          elsif sum.size == 1
            sums << sum.fetch(0)
          else
            sums << LogicNode.new(LogicNodeType::Or, sum)
          end
        end

        if sums.size == 0
          False
        elsif sums.size == 1
          sums.fetch(0)
        else
          LogicNode.new(LogicNodeType::And, sums)
        end
      else
        T.absurd(result_type)
      end
    end
    private :quine_mccluskey

    # convert to either sum-of-products form or product-of-sums form and minimize the result
    sig { params(result_type: CanonicalizationType).returns(LogicNode) }
    def minimize(result_type)
      if terms.size <= 4
        quine_mccluskey(result_type)
      else
        # special-case check for when the formula is large but obviously already minimized
        # added this because espresso runtime for Shcounterenw requirements was painfully long
        if result_type == CanonicalizationType::ProductOfSums && terms.size > 32 && nnf.nested_cnf? && terms.size == literals.size
          equiv_cnf
        else
          espresso(result_type, true)
        end
      end
    end

    class ConditionalEndterm < T::Struct
      const :term, TermType
      const :cond, LogicNode
    end

    EvalCallbackType = T.type_alias { T.proc.params(arg0: TermType).returns(SatisfiedResult) }
    sig { params(blk: EvalCallbackType).returns(EvalCallbackType) }
    def self.make_eval_cb(&blk)
      blk
    end

    ReplaceCallbackType = T.type_alias { T.proc.params(arg0: LogicNode).returns(LogicNode) }
    sig { params(blk: ReplaceCallbackType).returns(ReplaceCallbackType) }
    def self.make_replace_cb(&blk)
      blk
    end

    sig { params(callback: ReplaceCallbackType).returns(LogicNode) }
    def replace_terms(callback)
      case @type
      when LogicNodeType::True, LogicNodeType::False
        self
      when LogicNodeType::Term
        callback.call(self)
      when LogicNodeType::If, LogicNodeType::Not, LogicNodeType::And,
           LogicNodeType::Or, LogicNodeType::None, LogicNodeType::Xor
        LogicNode.new(
          @type,
          node_children.map { |c| c.replace_terms(callback) }
        )
      else
        T.absurd(@type)
      end
    end

    sig { params(callback: EvalCallbackType).returns(SatisfiedResult) }
    def eval_cb(callback)
      case @type
      when LogicNodeType::True
        SatisfiedResult::Yes
      when LogicNodeType::False
        SatisfiedResult::No
      when LogicNodeType::Term
        child = T.cast(@children.fetch(0), TermType)
        callback.call(child)
      when LogicNodeType::If
        cond_ext_ret = node_children.fetch(0)
        res = cond_ext_ret.eval_cb(callback)
        if res == SatisfiedResult::Yes
          node_children.fetch(1).eval_cb(callback)
        elsif res == SatisfiedResult::Maybe
          ## if "then" is true, then res doesn't matter....
          node_children.fetch(1).eval_cb(callback) == SatisfiedResult::Yes \
            ? SatisfiedResult::Yes
            : SatisfiedResult::Maybe
        else
          # if antecedent is false, implication is true
          SatisfiedResult::Yes
        end
      when LogicNodeType::Not
        res = node_children.fetch(0).eval_cb(callback)
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
      when LogicNodeType::And
        yes_cnt = T.let(0, Integer)
        node_children.each do |child|
          res1 = child.eval_cb(callback)
          return SatisfiedResult::No if res1 == SatisfiedResult::No

          yes_cnt += 1 if res1 == SatisfiedResult::Yes
        end
        if yes_cnt == node_children.size
          SatisfiedResult::Yes
        else
          SatisfiedResult::Maybe
        end
      when LogicNodeType::Or
        no_cnt = 0
        node_children.each do |child|
          res1 = child.eval_cb(callback)
          return SatisfiedResult::Yes if res1 == SatisfiedResult::Yes

          no_cnt += 1 if res1 == SatisfiedResult::No
        end
        if no_cnt == node_children.size
          SatisfiedResult::No
        else
          SatisfiedResult::Maybe
        end
      when LogicNodeType::None
        no_cnt = 0
        node_children.each do |child|
          res1 = child.eval_cb(callback)
          return SatisfiedResult::No if res1 == SatisfiedResult::Yes

          no_cnt += 1 if res1 == SatisfiedResult::No
        end
        if no_cnt == node_children.size
          SatisfiedResult::Yes
        else
          SatisfiedResult::Maybe
        end
      when LogicNodeType::Xor
        yes_cnt = T.let(0, Integer)
        has_maybe = T.let(false, T::Boolean)
        node_children.each do |child|
          res1 = child.eval_cb(callback)

          has_maybe ||= (res1 == SatisfiedResult::Maybe)
          yes_cnt += 1 if res1 == SatisfiedResult::Yes
          return SatisfiedResult::No if yes_cnt > 1
        end
        if yes_cnt == 1 && !has_maybe
          SatisfiedResult::Yes
        elsif has_maybe
          SatisfiedResult::Maybe
        else
          SatisfiedResult::No
        end
      else
        T.absurd(@type)
      end
    end

    # partially evalute -- replace anything known with true/false, and otherwise leave it alone
    sig { params(cb: EvalCallbackType).returns(LogicNode) }
    def partial_evaluate(cb)
      case @type
      when LogicNodeType::Term
        res = cb.call(T.cast(@children.fetch(0), TermType))
        if res == SatisfiedResult::Yes
          True
        elsif res == SatisfiedResult::No
          False
        else
          self
        end
      else
        LogicNode.new(@type, node_children.map { |child| child.partial_evaluate(cb) })
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
        IMPLIES: "->" # making this up; there is no implication operator in C
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

    # return a nice, human-readable form that may gloss over details
    sig { returns(String) }
    def to_s_pretty
      if @type == LogicNodeType::True
        "true"
      elsif @type == LogicNodeType::False
        "false"
      elsif @type == LogicNodeType::Term
        @children.fetch(0).to_s_pretty
      elsif @type == LogicNodeType::Not
        "not #{@children.fetch(0).to_s_pretty}"
      elsif @type == LogicNodeType::And
        "(#{node_children.map { |c| c.to_s_pretty }.join(" and ")})"
      elsif @type == LogicNodeType::Or
        "(#{node_children.map { |c| c.to_s_pretty }.join(" or ")})"
      elsif @type == LogicNodeType::Xor
        "(#{node_children.map { |c| c.to_s_pretty }.join(" xor ")})"
      elsif @type == LogicNodeType::None
        "none of (#{node_children.map { |c| c.to_s_pretty }.join(", ")})"
      elsif @type == LogicNodeType::If
        "if #{node_children.fetch(0).to_s_pretty} then #{node_children.fetch(1).to_s_pretty})"
      else
        T.absurd(@type)
      end
    end

    sig { override.returns(Integer) }
    def hash
      if @type == LogicNodeType::True
        true.hash
      elsif @type == LogicNodeType::False
        false.hash
      elsif @type == LogicNodeType::Term
        @children[0].to_s.hash
      elsif @type == LogicNodeType::Not
        [:not, node_children.fetch(0).hash].hash
      elsif @type == LogicNodeType::And
        [:and, node_children.map(&:hash)].hash
      elsif @type == LogicNodeType::Or
        [:or, node_children.map(&:hash)].hash
      elsif @type == LogicNodeType::Xor
        [:xor, node_children.map(&:hash)].hash
      elsif @type == LogicNodeType::None
        [:none, node_children.map(&:hash)].hash
      elsif @type == LogicNodeType::If
        [:if, node_children.map(&:hash)].hash
      else
        T.absurd(@type)
      end
    end

    sig { params(format: LogicSymbolFormat).returns(String) }
    def to_s(format: LogicSymbolFormat::Predicate)
      if @type == LogicNodeType::True
        LOGIC_SYMBOLS[format][:TRUE]
      elsif @type == LogicNodeType::False
        LOGIC_SYMBOLS[format][:FALSE]
      elsif @type == LogicNodeType::Term
        @children[0].to_s
      elsif @type == LogicNodeType::Not
        "#{LOGIC_SYMBOLS[format][:NOT]}#{node_children.fetch(0).to_s(format:)}"
      elsif @type == LogicNodeType::And
        "(#{node_children.map { |c| c.to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:AND]} ")})"
      elsif @type == LogicNodeType::Or
        "(#{node_children.map { |c| c.to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::Xor
        "(#{node_children.map { |c| c.to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:XOR]} ")})"
      elsif @type == LogicNodeType::None
        "#{LOGIC_SYMBOLS[format][:NOT]}(#{node_children.map { |c| c.to_s(format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::If
        "(#{node_children.fetch(0).to_s(format:)} #{LOGIC_SYMBOLS[format][:IMPLIES]} #{node_children.fetch(1).to_s(format:)})"
      else
        T.absurd(@type)
      end
    end

    sig { params(callback: EvalCallbackType, format: LogicSymbolFormat).returns(String) }
    def to_s_with_value(callback, format: LogicSymbolFormat::Predicate)
      if @type == LogicNodeType::True
        LOGIC_SYMBOLS[format][:TRUE]
      elsif @type == LogicNodeType::False
        LOGIC_SYMBOLS[format][:FALSE]
      elsif @type == LogicNodeType::Term
        v = callback.call(T.cast(@children.fetch(0), TermType))
        str =
          case v
          when SatisfiedResult::Yes
            "{true}"
          when SatisfiedResult::No
            "{false}"
          when SatisfiedResult::Maybe
            "{unknown}"
          else
            T.absurd(v)
          end
        "`#{@children.fetch(0)}`#{str}"
      elsif @type == LogicNodeType::Not
        "#{LOGIC_SYMBOLS[format][:NOT]}#{node_children.fetch(0).to_s_with_value(callback, format:)}"
      elsif @type == LogicNodeType::And
        "(#{node_children.map { |c| c.to_s_with_value(callback, format:) }.join(" #{LOGIC_SYMBOLS[format][:AND]} ")})"
      elsif @type == LogicNodeType::Or
        "(#{node_children.map { |c| c.to_s_with_value(callback, format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::Xor
        "(#{node_children.map { |c| c.to_s_with_value(callback, format:) }.join(" #{LOGIC_SYMBOLS[format][:XOR]} ")})"
      elsif @type == LogicNodeType::None
        "#{LOGIC_SYMBOLS[format][:NOT]}(#{node_children.map { |c| c.to_s_with_value(callback, format:) }.join(" #{LOGIC_SYMBOLS[format][:OR]} ")})"
      elsif @type == LogicNodeType::If
        "(#{node_children.fetch(0).to_s_with_value(callback, format:)} #{LOGIC_SYMBOLS[format][:IMPLIES]} #{node_children.fetch(1).to_s_with_value(callback, format:)})"
      else
        T.absurd(@type)
      end
    end

    sig { params(include_versions: T::Boolean).returns(String) }
    def to_asciidoc(include_versions:)
      case @type
      when LogicNodeType::Term
        term = T.cast(children.fetch(0), TermType)
        if term.is_a?(ExtensionTerm)
          if include_versions
            "`#{term.name}`#{term.comparison}#{term.version.canonical}"
          else
            "`#{term.name}`"
          end
        elsif term.is_a?(ParameterTerm)
          term.to_asciidoc
        elsif term.is_a?(FreeTerm)
          raise "Should not occur"
        elsif term.is_a?(XlenTerm)
          term.to_asciidoc
        else
          T.absurd(term)
        end
      when LogicNodeType::False
        "false"
      when LogicNodeType::True
        "true"
      when LogicNodeType::Not
        if node_children.fetch(0).type == LogicNodeType::Term
          term = node_children.fetch(0).children.fetch(0)
          if term.is_a?(ParameterTerm)
            negation = term.negate
            unless negation.nil?
              return negation.to_asciidoc
            end
          end
        end
        "!#{node_children.fetch(0).to_asciidoc(include_versions:)}"
      when LogicNodeType::And
        "++(++#{node_children.map { |c| c.to_asciidoc(include_versions:) }.join(" && ")})"
      when LogicNodeType::Or
        "++(++#{node_children.map { |c| c.to_asciidoc(include_versions:) }.join(" pass:[||] ")})"
      when LogicNodeType::If
        "++(++#{node_children.fetch(0).to_asciidoc(include_versions:)} -> #{node_children.fetch(1).to_asciidoc(include_versions:)})"
      when LogicNodeType::Xor
        "++(++#{node_children.map { |c| c.to_asciidoc(include_versions:) }.join(" &#2295; ")})"
      when LogicNodeType::None
        "!++(++#{node_children.map { |c| c.to_asciidoc(include_versions:) }.join(" pass:[||] ")})"
      else
        T.absurd(@type)
      end
    end

    sig { params(cfg_arch: ConfiguredArchitecture).returns(String) }
    def to_idl(cfg_arch)
      case @type
      when LogicNodeType::True
        "true"
      when LogicNodeType::False
        "false"
      when LogicNodeType::Term
        T.cast(@children.fetch(0), TermType).to_idl(cfg_arch)
      when LogicNodeType::Not
        "!#{node_children.fetch(0).to_idl(cfg_arch)}"
      when LogicNodeType::And
        "(#{node_children.map { |c| c.to_idl(cfg_arch) }.join(" && ") })"
      when LogicNodeType::Or
        "(#{node_children.map { |c| c.to_idl(cfg_arch) }.join(" || ")})"
      when LogicNodeType::Xor, LogicNodeType::None
        nnf.to_idl(cfg_arch)
      when LogicNodeType::If
        "(!(#{node_children.fetch(0).to_idl(cfg_arch)}) || (#{node_children.fetch(1).to_idl(cfg_arch)}))"
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
          when FreeTerm
            { "free" => child.id } # only needed for #hash
          when XlenTerm
            @children.fetch(0).to_h
          else
            T.absurd(child)
          end
        end
      elsif @type == LogicNodeType::Not
        child = node_children.fetch(0)
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "not" => child.to_h(true) } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "not" => child.to_h(true) } }
        else
          { "not" => child.to_h(term_determined) }
        end
      elsif @type == LogicNodeType::And
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "allOf" => node_children.map { |child| child.to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "allOf" => node_children.map { |child| child.to_h(true) } } }
        else
          { "allOf" => node_children.map { |child| child.to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::Or
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "anyOf" => node_children.map { |child| child.to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "anyOf" => node_children.map { |child| child.to_h(true) } } }
        else
          { "anyOf" => node_children.map { |child| child.to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::Xor
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "oneOf" => node_children.map { |child| child.to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "oneOf" => node_children.map { |child| child.to_h(true) } } }
        else
          { "oneOf" => node_children.map { |child| child.to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::None
        if !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ExtensionTerm) }
          { "extension" => { "noneOf" => node_children.map { |child| child.to_h(true) } } }
        elsif !term_determined && terms_no_antecendents.all? { |term| term.is_a?(ParameterTerm) }
          { "param" => { "noneOf" => node_children.map { |child| child.to_h(true) } } }
        else
          { "noneOf" => node_children.map { |child| child.to_h(term_determined) } }
        end
      elsif @type == LogicNodeType::If
        {
          "if" => node_children.fetch(0).to_h(false),
          "then" => node_children.fetch(1).to_h(term_determined)
        }
      else
        T.absurd(@type)
      end
    end

    sig {
      params(node: LogicNode)
      .returns(LogicNode)
      .checked(:never)
    }
    def do_nnf_for_not(node)
      child = node.node_children.fetch(0)
      child_type = child.type
      case child_type
      when LogicNodeType::Term
        # identity
        node
      when LogicNodeType::True
        # invert to false
        False
      when LogicNodeType::False
        # invert to true
        True
      when LogicNodeType::And
        # distribute
        # !(a && b) == (!a || !b)
        LogicNode.new(
          LogicNodeType::Or,
          child.node_children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [child2])) }
        )
      when LogicNodeType::Or
        # distribute
        # !(a || b) == (!a && !b)
        LogicNode.new(
          LogicNodeType::And,
          child.node_children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [child2])) }
        )
      when LogicNodeType::Not
        # !!A = A
        grandchild = child.node_children.fetch(0)
        do_nnf(grandchild)
      when LogicNodeType::If, LogicNodeType::None, LogicNodeType::Xor
        do_nnf_for_not(LogicNode.new(LogicNodeType::Not, [do_nnf(child)]))
      else
        T.absurd(child_type)
      end
    end
    private :do_nnf_for_not

    # rewrite to Negation Normal Form
    sig { params(node: LogicNode).returns(LogicNode).checked(:never) }
    def do_nnf(node)
      node_type = node.type
      case node_type
      when LogicNodeType::Not
        do_nnf_for_not(node)
      when LogicNodeType::And, LogicNodeType::Or
        LogicNode.new(node_type, node.node_children.map { |child2| do_nnf(child2) })
      when LogicNodeType::None
        # NOR(A, b) = !A && !B
        LogicNode.new(
          LogicNodeType::And,
          node.node_children.map { |child2| do_nnf(LogicNode.new(LogicNodeType::Not, [child2])) }
        )
      when LogicNodeType::Xor
        # XOR(A, b) = (A && !B) || (!A && B)
        new_kids = []
        node.children.size.times do |i|
          group = []
          node.children.size.times do |j|
            if i == j
              group << do_nnf(node.node_children.fetch(j))
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
            do_nnf(LogicNode.new(
              LogicNodeType::Not,
              [node.node_children.fetch(0)]
            )),
            do_nnf(node.node_children.fetch(1))
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
      do_nnf(self)
    end

    # @return true iff self is in Negation Normal Form
    def nnf?
      if @type == LogicNodeType::Not
        node_children.fetch(0).type == LogicNodeType::Term
      elsif @type == LogicNodeType::Term
        true
      else
        node_children.all? { |child| child.nnf? }
      end
    end

    # rewrite so that each node has at most two children
    #
    # @example
    #   (A || B || C) => ((A || B) || C)
    sig { params(node: LogicNode).returns(LogicNode).checked(:never) }
    def do_group_by_2(node)
      t = node.type
      case t
      when LogicNodeType::And
        root =
          LogicNode.new(
            LogicNodeType::And,
            [
              do_group_by_2(node.node_children.fetch(0)),
              do_group_by_2(node.node_children.fetch(1))
            ]
          )
        (2...node.children.size).each do |i|
          root =
            LogicNode.new(
              LogicNodeType::And,
              [
                root,
                do_group_by_2(node.node_children.fetch(i))
              ]
            )
        end
        root
      when LogicNodeType::Or
        root =
          LogicNode.new(
            LogicNodeType::Or,
            [
              do_group_by_2(node.node_children.fetch(0)),
              do_group_by_2(node.node_children.fetch(1))
            ]
          )
        (2...node.children.size).each do |i|
          root =
            LogicNode.new(
              LogicNodeType::Or,
              [
                root,
                do_group_by_2(node.node_children.fetch(i))
              ]
            )
        end
        root
      when LogicNodeType::Xor
        # XOR is not distributive, so we need to conver this to AND/OR and then group_by_2
        do_group_by_2(do_nnf(node))
      when LogicNodeType::None
        if node.children.size == 2
          LogicNode.new(
            LogicNodeType::Not,
            [
              LogicNode.new(
                LogicNodeType::Or,
                [
                  do_group_by_2(node.node_children.fetch(0)),
                  do_group_by_2(node.node_children.fetch(1))
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
                    do_group_by_2(node.node_children.fetch(0)),
                    do_group_by_2(node.node_children.fetch(1))
                  ]
                )
              ]
            )
          (2...node.children.size).each do |i|
            tree =
              LogicNode.new(
                LogicNodeType::Or,
                [
                  tree,
                  do_group_by_2(node.node_children.fetch(i))
                ]
              )
          end
          tree
        end
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        node
      when LogicNodeType::Not
        LogicNode.new(LogicNodeType::Not, [do_group_by_2(node.node_children.fetch(0))])
      when LogicNodeType::If
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [do_group_by_2(node.node_children.fetch(0))]
            ),
            do_group_by_2(node.node_children.fetch(1))
          ]
        )
      else
        T.absurd(t)
      end
    end
    private :do_group_by_2

    # does each node have at most two children?
    sig { params(node: LogicNode).returns(T::Boolean) }
    def grouped_by_2?(node)
      t = node.type
      case t
      when LogicNodeType::And, LogicNodeType::Or
        node.children.size == 2 && \
          grouped_by_2?(node.node_children.fetch(0)) && \
          grouped_by_2?(node.node_children.fetch(1))
      when LogicNodeType::Not
        grouped_by_2?(node.node_children.fetch(0))
      when LogicNodeType::Term
        true
      when LogicNodeType::None, LogicNodeType::If, LogicNodeType::Xor
        raise "?"
      when LogicNodeType::True, LogicNodeType::False
        true
      else
        T.absurd(t)
      end
    end

    # @return rewrites the tree so that no node has more than 2 children
    #
    # @example
    #   (A || B || C) => ((A || B) || C)
    sig { returns(LogicNode) }
    def group_by_2
      do_group_by_2(self)
    end

    # distribute OR over AND
    #
    # @example
    #   A || (B && C) => (A || B) && (A || C)
    #
    # @example
    # (A && B) || C => (A || C) && (B || C)
    #
    # @example
    # (A && B) || (C && D) => ((A || C) && (A || D)) && ((B || C) && (B || D))
    sig { params(left: LogicNode, right: LogicNode, clause_count: T::Array[Integer], raise_on_explosion: T::Boolean).returns(LogicNode) }
    def distribute_or(left, right, clause_count = [0], raise_on_explosion:)
      if left.type == LogicNodeType::And && right.type == LogicNodeType::And
        # we want to do:
        #
        #   left   ||  right
        # (A && B) || (C && D) => ((A || C) && (A || D)) && ((B || C) && (B || D))

        a = do_equiv_cnf(left.node_children.fetch(0), clause_count, raise_on_explosion:)
        b = do_equiv_cnf(left.node_children.fetch(1), clause_count, raise_on_explosion:)
        c = do_equiv_cnf(right.node_children.fetch(0), clause_count, raise_on_explosion:)
        d = do_equiv_cnf(right.node_children.fetch(1), clause_count, raise_on_explosion:)

        # t1 is an AND of cnfs, so t1 will be cnf
        clause_count[0] = clause_count.fetch(0) + 2
        t1 =
          LogicNode.new(
            LogicNodeType::And,
            [
              do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [a, c]), clause_count, raise_on_explosion:),
              do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [a, d]), clause_count, raise_on_explosion:),
            ]
          )

        # t2 is an AND of cnfs, so t1 will be cnf
        clause_count[0] = clause_count.fetch(0) + 2
        t2 =
          LogicNode.new(
            LogicNodeType::And,
            [
              do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [b, c]), clause_count, raise_on_explosion:),
              do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [b, d]), clause_count, raise_on_explosion:),
            ]
          )
        # t3 is an AND of cnfs, so t3 will be cnf
        LogicNode.new(LogicNodeType::And, [t1, t2])
      elsif left.type == LogicNodeType::And
        # we want to do:
        #
        #   left   || right
        # (A && B) ||   C   => (A || C) && (B || C)

        a = do_equiv_cnf(left.node_children.fetch(0), clause_count, raise_on_explosion:)
        b = do_equiv_cnf(left.node_children.fetch(1), clause_count, raise_on_explosion:)
        c = do_equiv_cnf(right, clause_count, raise_on_explosion:)

        clause_count[0] = clause_count.fetch(0) + 1
        clause1 = do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [a, c]), clause_count, raise_on_explosion:)
        clause_count[0] = clause_count.fetch(0) + 1
        clause2 = do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [b, c]), clause_count, raise_on_explosion:)

        LogicNode.new(LogicNodeType::And, [clause1, clause2])
      elsif right.type == LogicNodeType::And
        # want to do:
        #
        # left ||  right
        #   A  || (B && C) => (A || B) && (A || C)

        a = do_equiv_cnf(left, clause_count, raise_on_explosion:)
        b = do_equiv_cnf(right.node_children.fetch(0), clause_count, raise_on_explosion:)
        c = do_equiv_cnf(right.node_children.fetch(1), clause_count, raise_on_explosion:)

        clause_count[0] = clause_count.fetch(0) + 2
        t1 = LogicNode.new(LogicNodeType::And,
          [
            do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [a, b]), clause_count, raise_on_explosion:),
            do_equiv_cnf(LogicNode.new(LogicNodeType::Or, [a, c]), clause_count, raise_on_explosion:)
          ]
        ).reduce
        raise "?" unless t1.nested_cnf?
        t1
      else
        # this is
        # (A || B), where either A and/or B is a disjunction
        a = do_equiv_cnf(left, clause_count, raise_on_explosion:)
        b = do_equiv_cnf(right, clause_count, raise_on_explosion:)

        clause_count[0] = clause_count.fetch(0) + 2
        t1 = LogicNode.new(LogicNodeType::Or, [a, b]).reduce
        t1 = t1.nested_cnf? ? t1 : do_equiv_cnf(t1, clause_count, raise_on_explosion:).reduce
        raise "?" unless t1.nested_cnf?
        t1
      end
    end
    private :distribute_or

    class SizeExplosion < RuntimeError; end

    # rewrite to Conjunctive Normal Form (i.e., product-of-sums) using Demorgan's laws
    sig {
      params(
        node: LogicNode,
        clause_count: T::Array[Integer],
        raise_on_explosion: T::Boolean
      )
      .returns(LogicNode)
      .checked(:never)
    }
    def do_equiv_cnf(node, clause_count = [0], raise_on_explosion:)
      return node if node.nested_cnf? == true

      if raise_on_explosion && clause_count.fetch(0) > 10
        raise SizeExplosion
      end

      cnf_node =
        if node.type == LogicNodeType::And
          raise "??" unless node.children.size == 2
          left = node.node_children.fetch(0)
          right = node.node_children.fetch(1)

          left = do_equiv_cnf(left, clause_count, raise_on_explosion:).reduce
          right = do_equiv_cnf(right, clause_count, raise_on_explosion:).reduce
          # left and right are in cnf form
          # If we and them together, the result is still cnf
          LogicNode.new(LogicNodeType::And, [left, right]).reduce
        elsif node.type == LogicNodeType::Or
          raise "??" unless node.children.size == 2
          # distributed or over and
          distribute_or(
            node.node_children.fetch(0),
            node.node_children.fetch(1),
            clause_count,
            raise_on_explosion:
          )
        else
          unless [
            node.type == LogicNodeType::Term,
            (node.type == LogicNodeType::Not && \
              node.node_children.fetch(0).type == LogicNodeType::Term),
            node.type == LogicNodeType::True,
            node.type == LogicNodeType::False
          ].any?
            raise "?? #{node.to_s(format: LogicSymbolFormat::C)}"
          end
          node.reduce
        end
      if cnf_node.frozen?
        raise "?" unless cnf_node.memo.is_nested_cnf
      else
        cnf_node.memo.is_nested_cnf = true
      end
      cnf_node
    end
    private :do_equiv_cnf

    # flattens a boolean expression using associativity rules.
    # It simplifies nested AND and OR operations by merging them into a single level.
    #
    # @example
    #    ((A || B) || C) => (A || B || C)
    sig { params(node: LogicNode).returns(LogicNode) }
    def flatten_cnf(node)
      if node.type == LogicNodeType::And
        flattened_kids = node.node_children.map { |child| flatten_cnf(child) }

        if flattened_kids.any? { |child| child.type == LogicNodeType::False }
          # whole conjunction can be reduced to false
          False
        else
          non_literal_kids = flattened_kids.reject { |child| child.type == LogicNodeType::True }
          flat_children = non_literal_kids.flat_map do |child|
            if child.type == LogicNodeType::And
              child.node_children
            else
              child
            end
          end

          if flat_children.empty?
            True
          elsif flat_children.size == 1
            flat_children.fetch(0)
          else
            LogicNode.new(LogicNodeType::And, flat_children)
          end
        end
      elsif node.type == LogicNodeType::Or
        flattened_kids = node.node_children.map { |child| flatten_cnf(child) }

        if flattened_kids.any? { |child| child.type == LogicNodeType::True }
          # whole disjunction can be reduced to true
          True
        else
          non_literal_kids = flattened_kids.reject { |child| child.type == LogicNodeType::False }
          flat_children = non_literal_kids.flat_map do |child|
            if child.type == LogicNodeType::Or
              child.node_children
            else
              child
            end
          end

          if flat_children.empty?
            False
          elsif flat_children.size == 1
            flat_children.fetch(0)
          else
            LogicNode.new(LogicNodeType::Or, flat_children)
          end
        end
      else
        node
      end
    end
    private :flatten_cnf

    # reduce the equation by removing easy identities:
    #
    # (A || B || .. || true)     => true
    # (A || B || .. || Z || !Z)  => true
    # (A && B && .. && false)    => false
    # (A && B && .. && Z && !Z)  => false
    # NONE(A, B, ..., true)      => false
    # false -> A                 => true
    # true  -> A                 => A
    sig { returns(LogicNode) }
    def reduce
      unless @memo.is_reduced.nil?
        raise "?" unless @memo.is_reduced == true
        return self
      end

      reduced =
        case @type
        when LogicNodeType::And
          reduced = LogicNode.new(LogicNodeType::And, node_children.map { |child| child.reduce })
          # see if there is a false term or a contradiction (a && !a)
          # if so, reduce to false
          must_be_false = reduced.node_children.any? do |child|

            # a false anywhere will make the conjunction false
            child.type == LogicNodeType::False ||

              # a contradiction (a && !a) will make the conjunction false
              (child.type == LogicNodeType::Term &&
                reduced.node_children.any? do |other_child|

                  other_child.type == LogicNodeType::Not && \
                  other_child.node_children.fetch(0).type == LogicNodeType::Term && \
                  child.children.fetch(0) == other_child.node_children.fetch(0).children.fetch(0)
                end)
          end
          if must_be_false
            False
          else

            # eliminate True
            true_reduced_children = reduced.node_children.reject { |c| c.type == LogicNodeType::True }
            if true_reduced_children.size != reduced.children.size
              reduced =
                if true_reduced_children.size == 0
                  True
                elsif true_reduced_children.size == 1
                  true_reduced_children.fetch(0)
                else
                  LogicNode.new(LogicNodeType::And, true_reduced_children)
                end
            end

            reduced
          end
        when LogicNodeType::Or
          reduced = LogicNode.new(LogicNodeType::Or, node_children.map { |child| child.reduce })
          # see if there is a true term or a tautology (a || !a)
          # if so, reduce to true
          must_be_true = reduced.node_children.any? do |child|

            # a true anywhere will make the disjunction true
            child.type == LogicNodeType::True ||

              # a tautology (a || !a) will make the disjunction true
              (child.type == LogicNodeType::Term &&
                reduced.node_children.any? do |other_child|

                  other_child.type == LogicNodeType::Not && \
                  other_child.node_children.fetch(0).type == LogicNodeType::Term && \
                  child.children.fetch(0) == other_child.node_children.fetch(0).children.fetch(0)
                end)
          end
          if must_be_true
            True
          else

            # eliminate False
            false_reduced_children = reduced.node_children.reject { |c| c.type == LogicNodeType::False }
            if false_reduced_children.size != reduced.children.size
              reduced =
                if false_reduced_children.size == 0
                  False
                elsif false_reduced_children.size == 1
                  false_reduced_children.fetch(0)
                else
                  LogicNode.new(LogicNodeType::Or, false_reduced_children)
                end
            end

            reduced
          end
        when LogicNodeType::Xor
          reduced = LogicNode.new(LogicNodeType::Xor, node_children.map { |child| child.reduce })
          xor_with_self = reduced.children.size == 2 &&
            reduced.node_children.fetch(0).type == LogicNodeType::Term &&
            reduced.node_children.fetch(1).type == LogicNodeType::Term &&
            reduced.node_children.fetch(0).children.fetch(0) == reduced.node_children.fetch(1).children.fetch(0)
          if xor_with_self
            # xor with self if always false
            False
          else
            reduced
          end
        when LogicNodeType::If
          reduced = LogicNode.new(LogicNodeType::If, node_children.map { |child| child.reduce })
          antecedent = reduced.node_children.fetch(0)
          consequent = reduced.node_children.fetch(1)
          if antecedent.type == LogicNodeType::True
            consequent
          elsif antecedent.type == LogicNodeType::False
            return True
          elsif consequent.type == LogicNodeType::True
            return True
          elsif consequent.type == LogicNodeType::False
            return LogicNode.new(LogicNodeType::Not, [antecedent])
          else
            reduced
          end
        when LogicNodeType::Not
          reduced = LogicNode.new(LogicNodeType::Not, node_children.map { |child| child.reduce })
          child = reduced.node_children.fetch(0)
          if child.type == LogicNodeType::Not
            # !!a = a
            reduced.node_children.fetch(0).node_children.fetch(0)
          elsif child.type == LogicNodeType::False
            # !false = true
            return True
          elsif child.type == LogicNodeType::True
            # !true = false
            return False
          else
            reduced
          end
        when LogicNodeType::None
          if node_children.any? { |c| c.type == LogicNodeType::True }
            True
          else
            self.dup
          end
        when LogicNodeType::True, LogicNodeType::False, LogicNodeType::Term
          self
        else
          T.absurd(@type)
        end

      if reduced.memo.is_reduced.nil?
        reduced.memo.is_reduced = true
      end
      reduced
    end

    # coverts self to an equivalent formula in Conjunctive Normal Form
    # and returns it as a new formula (self is unmodified)
    #
    # iteratively uses Demorgan's Laws. May explode since the worst case
    # is exponential in the number of clauses
    sig { params(raise_on_explosion: T::Boolean).returns(LogicNode) }
    def equiv_cnf(raise_on_explosion: true)
      @memo.equiv_cnf ||=
        begin
          r = reduce
          return r if r.type == LogicNodeType::True || r.type == LogicNodeType::False

          n = r.nnf

          candidate = n.reduce
          candidate = n.group_by_2
          unflattened = do_equiv_cnf(candidate, raise_on_explosion:)
          result = flatten_cnf(unflattened).reduce
          if result.frozen?
            raise "?" unless result.memo.is_cnf == true
          else
            result.memo.is_cnf = true
          end
          result
        end
    end

    # coverts self to an equisatisfiable formula in Conjunctive Normal Form
    # and returns it as a new formula (self is unmodified)
    sig { returns(LogicNode) }
    def equisat_cnf
      return @memo.equisat_cnf unless @memo.equisat_cnf.nil?
      return self if @type == LogicNodeType::True
      return self if @type == LogicNodeType::False

      # strategy: try conversion using Demorgan's laws first. If that appears to be getting too
      # large (exponential in the worst case), fall back on the tseytin transformation
      @memo.equisat_cnf =
        if @memo.equiv_cnf.nil?
          if terms.count > 4 || literals.count > 10
            tseytin
          else
            # try demorgan first, then fall back if it gets too big
            begin
              equiv_cnf
            rescue SizeExplosion
              tseytin
            end
          end
        else
          # we already calculated an equivalent cnf, which is also equisatisfiable
          @mem.equiv_cnf
        end
    end

    # returns true iff tree is in Conjunctive Normal Form
    sig { returns(T::Boolean) }
    def cnf?
      unless @memo.is_cnf.nil?
        return @memo.is_cnf
      end

      ret =
        case @type
        when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
          true
        when LogicNodeType::Not
          node_children.fetch(0).type == LogicNodeType::Term
        when LogicNodeType::Or
          node_children.all? do |child|
            [
              child.type == LogicNodeType::True,
              child.type == LogicNodeType::False,
              child.type == LogicNodeType::Term,
              child.type == LogicNodeType::Not && \
                child.node_children.fetch(0).type == LogicNodeType::Term
            ].any?
          end
        when LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
          false
        when LogicNodeType::And
          node_children.all? { |child| child.cnf_conjunction_term? }
        else
          T.absurd(@type)
        end

      @memo.is_cnf = ret
    end

    # returns true iff tree is in Disjunctive Normal Form
    sig { returns(T::Boolean) }
    def dnf?
      case @type
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        true
      when LogicNodeType::Not
        node_children.fetch(0).type == LogicNodeType::Term
      when LogicNodeType::Or
        node_children.all? { |child| child.dnf_disjunctive_term? }
      when LogicNodeType::And
        node_children.all? do |child|
          [
            child.type == LogicNodeType::True,
            child.type == LogicNodeType::False,
            child.type == LogicNodeType::Term,
            child.type == LogicNodeType::Not && \
              child.node_children.fetch(0).type == LogicNodeType::Term
          ].any?
        end
      when LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
        false
      else
        T.absurd(@type)
      end
    end

    # @api private
    # returns true iff tree is a valid term in a cnf conjunction
    sig { returns(T::Boolean) }
    def cnf_conjunction_term?
      case @type
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        true
      when LogicNodeType::Not
        node_children.fetch(0).type == LogicNodeType::Term
      when LogicNodeType::Or
        # or is only valid if only contains literals
        node_children.all? do |child|
          [
            child.type == LogicNodeType::True,
            child.type == LogicNodeType::False,
            child.type == LogicNodeType::Term,
            ((child.type == LogicNodeType::Not) && \
              child.node_children.fetch(0).type == LogicNodeType::Term)
          ].any?
        end
      when LogicNodeType::And, LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
        false
      else
        T.absurd(@type)
      end
    end

    # @api private
    # returns true iff tree is a valid term in a dnf disjunction
    sig { returns(T::Boolean) }
    def dnf_disjunctive_term?
      case @type
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        true
      when LogicNodeType::Not
        node_children.fetch(0).type == LogicNodeType::Term
      when LogicNodeType::And
        # and is only valid if only contains literals
        node_children.all? do |child|
          [
            child.type == LogicNodeType::True,
            child.type == LogicNodeType::False,
            child.type == LogicNodeType::Term,
            ((child.type == LogicNodeType::Not) && \
              child.node_children.fetch(0).type == LogicNodeType::Term)
          ]
        end
      when LogicNodeType::Or, LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
        false
      else
        T.absurd(@type)
      end
    end

    # @api private
    # returns true iff tree is a valid term in a nested cnf conjunction
    sig { params(ancestor_or: T::Boolean).returns(T::Boolean) }
    def nested_cnf_conjunction_term?(ancestor_or)
      case @type
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        true
      when LogicNodeType::Not
        node_children.fetch(0).type == LogicNodeType::Term
      when LogicNodeType::Or
        node_children.all? do |child|
          [
            child.type == LogicNodeType::True,
            child.type == LogicNodeType::False,
            child.type == LogicNodeType::Term,
            ((child.type == LogicNodeType::Not) && \
              child.node_children.fetch(0).type == LogicNodeType::Term),
            child.type == LogicNodeType::Or && child.nested_cnf_conjunction_term?(true)
          ].any?
        end
      when LogicNodeType::And
        return false if ancestor_or

        node_children.all? do |child|
          [
            child.type == LogicNodeType::True,
            child.type == LogicNodeType::False,
            child.type == LogicNodeType::Term,
            ((child.type == LogicNodeType::Not) && \
              child.node_children.fetch(0).type == LogicNodeType::Term),
            (child.type == LogicNodeType::Or && \
              child.nested_cnf_conjunction_term?(true)),
            (child.type == LogicNodeType::And && \
              child.nested_cnf_conjunction_term?(ancestor_or))
          ].any?
        end
      when LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
        false
      else
        T.absurd(@type)
      end
    end

    # returns true iff tree, if flattened, would be cnf
    # allows nested ANDs as long as there is no ancestor OR
    # allows nested ORs as long as there is no decendent AND
    sig { returns(T::Boolean) }
    def nested_cnf?
      unless @memo.is_nested_cnf.nil?
        return @memo.is_nested_cnf
      end

      ret =
        case @type
        when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
          true
        when LogicNodeType::Not
          node_children.fetch(0).type == LogicNodeType::Term
        when LogicNodeType::And
          node_children.all? do |child|
            child.nested_cnf_conjunction_term?(false)
          end
        when LogicNodeType::Or
          # or is only valid if only it recursively contains only literals or disjunctions
          node_children.all? do |child|
            [
              child.type == LogicNodeType::True,
              child.type == LogicNodeType::False,
              child.type == LogicNodeType::Term,
              ((child.type == LogicNodeType::Not) && \
                child.node_children.fetch(0).type == LogicNodeType::Term),
              child.type == LogicNodeType::Or && \
                child.node_children.all? { |grandchild| grandchild.nested_cnf_conjunction_term?(true) }
            ].any?
          end
        when LogicNodeType::Xor, LogicNodeType::If, LogicNodeType::None
          false
        else
          T.absurd(@type)
        end
      @memo.is_nested_cnf = ret
    end

    sig { params(solver: MiniSat::Solver, node: LogicNode, term_map: T::Hash[TermType, MiniSat::Variable], cur_or: T::nilable(T::Array[T.untyped])).void }
    def build_solver(solver, node, term_map, cur_or)
      if node.type == LogicNodeType::Term
        v = term_map.fetch(T.cast(node.children.fetch(0), TermType))
        if cur_or.nil?
          solver << v
        else
          cur_or << v
        end
      elsif node.type == LogicNodeType::Not
        child = node.node_children.fetch(0)
        term = T.cast(child.children.fetch(0), TermType)
        v = -term_map.fetch(term)
        if cur_or.nil?
          solver << v
        else
          cur_or << v
        end
      elsif node.type == LogicNodeType::Or
        node.node_children.each do |child|
          build_solver(solver, child, term_map, cur_or)
        end
      elsif node.type == LogicNodeType::And
        node.node_children.each do |child|
          new_or = []
          build_solver(solver, child, term_map, new_or)
          solver << new_or
        end
      else
        raise "not in cnf"
      end
    end
    private :build_solver

    sig { params(other: LogicNode).returns(T::Boolean) }
    def always_implies?(other)
      # can test that by seeing if the contradiction is satisfiable, i.e.:
      # if self -> other , contradition would be self & not other
      contradiction = LogicNode.new(
        LogicNodeType::And,
        [
          self,
          LogicNode.new(LogicNodeType::Not, [other])
        ]
      )
      !contradiction.satisfiable?
    end

    # @return true iff self is satisfiable (possible to be true for some combination of term values)
    sig { returns(T::Boolean) }
    def satisfiable?
      @memo.is_satisfiable ||=
        begin
          nterms = terms.size

          if nterms < 8 && literals.size <= 32
            # just brute force it
            LogicNode.inc_brute_force_sat_solves
            term_idx = T.let({}, T::Hash[TermType, Integer])
            terms.each_with_index do |term, idx|
              term_idx[term] = idx
            end
            # define the callback outside the loop to avoid allocating a new block on every iteration
            val_out_of_loop = 0
            cb = LogicNode.make_eval_cb do |term|
              ((val_out_of_loop >> term_idx.fetch(term)) & 1).zero? ? SatisfiedResult::No : SatisfiedResult::Yes
            end

            if nterms.zero?
              return eval_cb(cb) == SatisfiedResult::Yes
            else
              (2**nterms).to_i.times do |i|
                val_out_of_loop = i
                if eval_cb(cb) == SatisfiedResult::Yes
                  return true
                end
              end
            end
            return false

          else
            # use SAT solver
            LogicNode.inc_minisat_sat_solves

            @@cache ||= {}
            cache_key = hash
            if @@cache.key?(cache_key)
              LogicNode.inc_minisat_cache_hits
              return @@cache[cache_key]
            end

            c = self.cnf? ? self : equisat_cnf
            # raise "cnf error" unless c.cnf?

            if c.type == LogicNodeType::True
              return true
            elsif c.type == LogicNodeType::False
              return false
            end

            t = c.terms

            solver = MiniSat::Solver.new

            term_map = T.let({}, T::Hash[TermType, MiniSat::Variable])
            t.each do |term|
              unless term_map.key?(term)
                term_map[term] = solver.new_var
              end
            end
            raise "term mapping failed" unless t.uniq == term_map.keys

            build_solver(solver, flatten_cnf(c), term_map, nil)

            solver.solve
            @@cache[cache_key] = solver.satisfied?
          end
        end
    end

    # @return true iff self is unsatisfiable (not possible to be true for any combination of term values)
    sig { returns(T::Boolean) }
    def unsatisfiable? = !satisfiable?

    sig { params(other: LogicNode).returns(T::Boolean) }
    def equisatisfiable?(other)
      if satisfiable?
        other.satisfiable?
      else
        !other.satisfiable?
      end
    end

    # @return true iff self and other are logically equivalent (identical truth tables)
    sig { params(other: LogicNode).returns(T::Boolean) }
    def equivalent?(other)
      # equivalent (A <=> B) if the biconditional is true:
      #   (A -> B) && (B -> A)
      # or, expressed without implication:
      #   (!A || B) && (!B || A)

      # equivalence is a tautology iff ~(A <=> B) is a contradiction,
      # i.e., !(A <=> B) is UNSATISFIABLE
      #       !((!A || B) && (!B || A)) is UNSATISFIABLE

      r = self
      other = other
      contradiction = LogicNode.new(
        LogicNodeType::Not,
        [
          LogicNode.new(
            LogicNodeType::And,
            [
              LogicNode.new(
                LogicNodeType::Or,
                [
                  LogicNode.new(LogicNodeType::Not, [r]),
                  other
                ]
              ),
              LogicNode.new(
                LogicNodeType::Or,
                [
                  LogicNode.new(LogicNodeType::Not, [r]),
                  self
                ]
              )
            ]
          )
        ]
      )
      !contradiction.satisfiable?
    end

    sig {
      params(
        tree: LogicNode,
        term_map: T::Hash[TermType, String]
      )
      .returns(String)
      .checked(:never)
    }
    def do_to_eqntott(tree, term_map)
      t = tree.type
      case t
      when LogicNodeType::True
        "1"
      when LogicNodeType::False
        "0"
      when LogicNodeType::And
        "(#{tree.node_children.map { |child| do_to_eqntott(child, term_map) }.join(" & ")})"
      when LogicNodeType::Or
        "(#{tree.node_children.map { |child| do_to_eqntott(child, term_map) }.join(" | ")})"
      when LogicNodeType::Xor
        do_to_eqntott(tree.nnf, term_map)
      when LogicNodeType::None
        do_to_eqntott(LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Or, tree.children)]), term_map)
      when LogicNodeType::Term
        term_map.fetch(T.cast(tree.children.fetch(0), TermType))
      when LogicNodeType::Not
        "!(#{do_to_eqntott(tree.node_children.fetch(0), term_map)})"
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

    # @api private
    sig { params(node: LogicNode).returns(LogicNode) }
    def distribute_not_helper(node)
      child = node.node_children.fetch(0)
      child_type = child.type
      case child_type
      when LogicNodeType::And
        LogicNode.new(LogicNodeType::Or, child.children.map { |c| LogicNode.new(LogicNodeType::Not, [c]).distribute_not })
      when LogicNodeType::Or
        LogicNode.new(LogicNodeType::And, child.children.map { |c| LogicNode.new(LogicNodeType::Not, [c]).distribute_not })
      when LogicNodeType::Not
        if child.node_children.fetch(0).type == LogicNodeType::Term
          child.node_children.fetch(0)
        else
          distribute_not_helper(child)
        end
      when LogicNodeType::Term
        self
      when LogicNodeType::True
        LogicNode.new(LogicNodeType::False, [])
      when LogicNodeType::False
        LogicNode.new(LogicNodeType::True, [])
      when LogicNodeType::None, LogicNodeType::Xor, LogicNodeType::If
        raise "Expecting format to start in CNF or DNF"
      else
        T.absurd(child_type)
      end
    end
    private :distribute_not_helper

    # @api private
    sig { returns(LogicNode) }
    def distribute_not
      # recursively apply demorgan until we get to terms
      raise "Not a negation" unless @type == LogicNodeType::Not

      distribute_not_helper(self)
    end

    # @api private
    sig {
      params(subformulae: T::Array[LogicNode])
      .void
      .checked(:never)
    }
    def collect_tseytin(subformulae)
      case @type
      when LogicNodeType::And
        # (¬A ∨ ¬B ∨ p) ∧ (A ∨ ¬p) ∧ (B ∨ ¬p)
        a = node_children.fetch(0).tseytin_prop
        b = node_children.fetch(1).tseytin_prop
        subformulae <<
          LogicNode.new(
            LogicNodeType::And,
            [
              LogicNode.new(LogicNodeType::Or,
                [
                  LogicNode.new(LogicNodeType::Not, [a]),
                  LogicNode.new(LogicNodeType::Not, [b]),
                  tseytin_prop
                ]
              ),
              LogicNode.new(LogicNodeType::Or,
                [
                  a,
                  LogicNode.new(LogicNodeType::Not, [tseytin_prop])
                ]
              ),
              LogicNode.new(LogicNodeType::Or,
                [
                  b,
                  LogicNode.new(LogicNodeType::Not, [tseytin_prop])
                ]
              )
            ]
          )
        node_children.fetch(0).collect_tseytin(subformulae)
        node_children.fetch(1).collect_tseytin(subformulae)
      when LogicNodeType::Or
        # (A ∨ B ∨ ¬p) ∧ (¬A ∨ p) ∧ (¬B ∨ p)
        a = node_children.fetch(0).tseytin_prop
        b = node_children.fetch(1).tseytin_prop
        subformulae <<
          LogicNode.new(
            LogicNodeType::And,
            [
              LogicNode.new(LogicNodeType::Or, [a, b, LogicNode.new(LogicNodeType::Not, [tseytin_prop])]),
              LogicNode.new(LogicNodeType::Or, [LogicNode.new(LogicNodeType::Not, [a]), tseytin_prop]),
              LogicNode.new(LogicNodeType::Or, [LogicNode.new(LogicNodeType::Not, [b]), tseytin_prop])
            ]
          )
        node_children.fetch(0).collect_tseytin(subformulae)
        node_children.fetch(1).collect_tseytin(subformulae)
      when LogicNodeType::Not
        # (A ∨ p) ∧ (¬A ∨ ¬p)
        a = node_children.fetch(0).tseytin_prop
        subformulae <<
          LogicNode.new(
            LogicNodeType::And,
            [
              LogicNode.new(LogicNodeType::Or, [a, tseytin_prop]),
              LogicNode.new(LogicNodeType::Or, [
                LogicNode.new(LogicNodeType::Not, [a]),
                LogicNode.new(LogicNodeType::Not, [tseytin_prop]),
              ])
            ]
          )
        node_children.fetch(0).collect_tseytin(subformulae)
      when LogicNodeType::True, LogicNodeType::False
        # pass
      when LogicNodeType::Term
        # pass
      else
        raise "? #{@type}"
      end
    end

    # a free variable representing this formula
    sig { returns(LogicNode) }
    def tseytin_prop
      case @type
      when LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False
        self
      else
        @tseytin_prop ||=
          LogicNode.new(LogicNodeType::Term, [FreeTerm.new])
      end
    end

    # @api private
    sig { returns(LogicNode) }
    def tseytin
      subformulae = []
      r = reduce
      return r if [LogicNodeType::Term, LogicNodeType::True, LogicNodeType::False].any?(r.type)

      grouped = r.group_by_2
      grouped.collect_tseytin(subformulae)

      if subformulae.size == 0
        raise "? #{r}"
      elsif subformulae.size == 1
        subformulae.fetch(0)
      else
        equisatisfiable_formula = LogicNode.new(LogicNodeType::And, subformulae + [grouped.tseytin_prop])
        flatten_cnf(equisatisfiable_formula).reduce
      end
    end

    sig { returns(String) }
    def to_dimacs
      if @type == LogicNodeType::Term
        <<~DIMACS
          p cnf 1 1
          1 0
        DIMACS
      elsif @type == LogicNodeType::Not
        <<~DIMACS
          p cnf 1 1
          -1 0
        DIMACS
      elsif @type == LogicNodeType::True || @type == LogicNodeType::False
        raise "Cannot represent true/false in DIMACS"
      elsif @type == LogicNodeType::And
        lines = ["p cnf #{terms.size} #{@children.size}"]
        lines += node_children.map do |child|
          if child.type == LogicNodeType::Or
            term_line = child.node_children.map do |grandchild|
              if grandchild.type == LogicNodeType::Not
                (-(T.must(terms.index(grandchild.node_children.fetch(0).node_children.fetch(0))) + 1)).to_s
              elsif grandchild.type == LogicNodeType::Term
                (T.must(terms.index(grandchild.node_children.fetch(0))) + 1).to_s
              end
            end.join(" ")
            "#{term_line} 0"
          elsif child.type == LogicNodeType::Term
            "#{T.must(terms.index(child.children.fetch(0))) + 1} 0"
          elsif child.type == LogicNodeType::Not
            "-#{T.must(terms.index(child.node_children.fetch(0).children.fetch(0))) + 1} 0"
          else
            raise "Not CNF"
          end
        end

        lines.join("\n")
      else
        raise "Not CNF"
      end
    end

    sig { params(dimacs: String).returns(LogicNode) }
    def from_dimacs(dimacs)
      nodes = dimacs.each_line.map do |line|
        if line =~ /^(((-?\d+) )+)0/
          ts = T.let($1.strip.split(" "), T::Array[String])
          if ts.size == 1
            t = ts.fetch(0)
            if t[0] == "-"
              index = t[1..].to_i - 1
              LogicNode.new(
                LogicNodeType::Not,
                [LogicNode.new(LogicNodeType::Term, [terms.fetch(index)])]
              )
            else
              index = t.to_i - 1
              LogicNode.new(LogicNodeType::Term, [terms.fetch(index)])
            end
          else
            LogicNode.new(LogicNodeType::Or,
              ts.map do |t|
                if t[0] == "-"
                  i = t[1..].to_i - 1
                  LogicNode.new(
                    LogicNodeType::Not,
                    [LogicNode.new(LogicNodeType::Term, [terms.fetch(i)])]
                  )
                else
                  i = t.to_i - 1
                  LogicNode.new(LogicNodeType::Term, [terms.fetch(i)])
                end
              end
            )
          end
        else
          nil
        end
      end.compact

      if nodes.size == 1
        nodes.fetch(0)
      else
        LogicNode.new(LogicNodeType::And, nodes)
      end
    end

    # return minimally unsatisfiable subsets of the unstatisfiable formula
    sig { returns(T::Array[LogicNode]) }
    def minimal_unsat_subsets
      r = reduce
      c = r.equiv_cnf(raise_on_explosion: false)
      Tempfile.create(%w/formula .cnf/) do |f|
        f.write c.to_dimacs
        f.flush

        Tempfile.create do |rf|
          # run must, re-use the tempfile for the result
          `must -o #{rf.path} #{f.path}`
          unless $?.success?
            raise "could not find minimal subsets"
          end

          rf.rewind
          result = rf.read

          mus_dimacs = T.let([], T::Array[String])
          cur_dimacs = T.let(nil, T.nilable(String))
          result.each_line do |line|
            if line =~ /MUS #\d+/
              mus_dimacs << cur_dimacs unless cur_dimacs.nil?
              cur_dimacs = ""
            else
              cur_dimacs = T.must(cur_dimacs) + line
            end
          end
          mus_dimacs << T.must(cur_dimacs)

          return mus_dimacs.map { |d| c.from_dimacs(d) }
        end
      end
    end


    # minimize the function using espresso
    sig {
      params(
        result_type: CanonicalizationType,
        exact: T::Boolean
      )
      .returns(LogicNode)
    }
    def espresso(result_type, exact)
      nterms = terms.size

      pla =
        if nterms > 4 || literals.size >= 32

          eqn_result =
            if result_type == CanonicalizationType::SumOfProducts
              to_eqntott
            elsif result_type == CanonicalizationType::ProductOfSums
              LogicNode.new(LogicNodeType::Not, [self]).to_eqntott
            else
              T.absurd(result_type)
            end
          tt = T.let(nil, T.nilable(String))
          Tempfile.open do |f|
            f.write <<~FILE
              NAME=f;
              #{eqn_result.eqn};
            FILE
            f.flush

            tt = `eqntott -l #{f.path}`
            unless $?.success?
              raise "eqntott failure"
            end
          end

          if T.must(tt).lines.any? { |l| l =~ /^\.p 0/ }
            if result_type == CanonicalizationType::SumOfProducts
              # short circuit here, it's trivially false
              return LogicNode.new(LogicNodeType::False, [])
            else
              # short circuit here, it's trivially true
              return LogicNode.new(LogicNodeType::True, [])
            end
          end
          tt
        else

          term_idx = T.let({}, T::Hash[TermType, Integer])
          terms.each_with_index do |term, idx|
            term_idx[term] = idx
          end

          # define the callback outside the loop to avoid allocating a new block on every iteration
          val_out_of_loop = 0
          cb = LogicNode.make_eval_cb do |term|
            ((val_out_of_loop >> term_idx.fetch(term)) & 1).zero? ? SatisfiedResult::No : SatisfiedResult::Yes
          end

          tt = T.let([], T::Array[T::Array[String]])
          (1 << nterms).times do |val|
            val_out_of_loop = val
            if result_type == CanonicalizationType::SumOfProducts
              if eval_cb(cb) == SatisfiedResult::Yes
                tt << [val.to_s(2).rjust(nterms, "0").reverse, "1"]
              else
                tt << [val.to_s(2).rjust(nterms, "0").reverse, "0"]
              end
            elsif result_type == CanonicalizationType::ProductOfSums
              if eval_cb(cb) == SatisfiedResult::Yes
                tt << [val.to_s(2).rjust(nterms, "0").reverse, "0"]
              else
                tt << [val.to_s(2).rjust(nterms, "0").reverse, "1"]
              end
            end
          end

          <<~INFILE
            .i #{nterms}
            .o 1
            .na f
            .ob out
            .p #{tt.size}
            #{tt.map { |t| t.join(" ") }.join("\n")}
          INFILE
        end

      Tempfile.open do |f|
        f.write pla
        f.flush

        cmd =
          if exact
            "espresso -Dsignature #{f.path}"
          else
            "espresso -efast #{f.path}"
          end
        result = `#{cmd} 2>&1`
        unless $?.success?
          raise "espresso failure\n#{result}"
        end

        sop_terms = []
        always_true = T.let(false, T::Boolean)
        result.lines.each_with_index do |line, idx|
          next if line[0] == "."
          next if line[0] == "#"

          if line =~ /^([01\-]{#{terms.size}}) 1/
            term = $1
            conjunction_kids = []
            terms.size.times do |i|
              if term[i] == "1"
                conjunction_kids << LogicNode.new(LogicNodeType::Term, [terms.fetch(i)])
              elsif term[i] == "0"
                conjunction_kids << LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [terms.fetch(i)])])
              else
                raise "unexpected" unless term[i] == "-"
              end
            end
            if conjunction_kids.size == 1
              sop_terms << conjunction_kids.fetch(0)
            elsif conjunction_kids.size > 0
              sop_terms << LogicNode.new(LogicNodeType::And, conjunction_kids)
            else
              # always true
              always_true = true
            end
          end
        end

        sop =
          if sop_terms.size == 1
            sop_terms.fetch(0)
          elsif sop_terms.size > 0
            LogicNode.new(LogicNodeType::Or, sop_terms)
          else
            always_true ? LogicNode.new(LogicNodeType::True, []) : LogicNode.new(LogicNodeType::False, [])
          end

        if result_type == CanonicalizationType::SumOfProducts
          sop
        else
          # result is actually !result, so negate it and then distribute
          LogicNode.new(LogicNodeType::Not, [sop]).distribute_not
        end
      end

    end

    # @api private
    sig { override.returns(Integer) }
    def hash = to_h.hash

    sig { override.params(other: T.untyped).returns(T::Boolean) }
    def eql?(other)
      return false unless other.is_a?(LogicNode)

      to_h.eql?(other.to_h)
    end
  end
end
