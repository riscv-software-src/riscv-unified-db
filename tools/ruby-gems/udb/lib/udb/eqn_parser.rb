# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

# parses an equation from the `eqntott`/`espresso` tools

require "sorbet-runtime"
require "treetop"

module Udb

  class LogicNode; end

  # parses the equation format from `eqntott` / `espresso` and converts it to a LogicNode
  class Eqn

    EQN_GRAMMAR = <<~GRAMMAR
      grammar Eqn
        rule eqn
          expression space* ';' space* <Udb::Eqn::EqnTop>
        end

        rule name
          [a-zA-Z_] [a-zA-Z0-9.]* <Udb::Eqn::EqnName>
        end

        rule zero
          'ZERO' / '0' <Udb::Eqn::EqnZero>
        end

        rule one
          'ONE' / '1' <Udb::Eqn::EqnOne>
        end

        rule paren
          '(' space* ')' <Udb::Eqn::EmptyEqnParen>
          /
          '(' space* conjunction space* ')' <Udb::Eqn::EqnParen>
        end

        rule not
          '!' space* name <Udb::Eqn::EqnNot>
        end

        rule unary_expression
          paren / not / zero / one / name
        end

        rule conjunction
          first:unary_expression r:(space* '&' space* unary_expression)+ <Udb::Eqn::EqnAnd>
          /
          unary_expression
        end

        rule disjunction
          first:conjunction r:(space* '|' space* conjunction)+ <Udb::Eqn::EqnOr>
          /
          conjunction
        end

        rule expression
          (space* disjunction space*)
          {
            def to_logic_tree(term_map)
              disjunction.to_logic_tree(term_map)
            end
          }
        end

        rule space
          [ \n]
        end
      end
    GRAMMAR

    class EqnTop < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        send(:expression).to_logic_tree(term_map)
      end
    end

    class EqnName < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        term = term_map.fetch(text_value)
        LogicNode.new(
          LogicNodeType::Term,
          [term]
        )
      end
    end

    class EqnOne < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        LogicNode.new(LogicNodeType::True, [])
      end
    end

    class EqnZero < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        LogicNode.new(LogicNodeType::False, [])
      end
    end

    class EmptyEqnParen < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        LogicNode::True
      end
    end

    class EqnParen < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        send(:conjunction).to_logic_tree(term_map)
      end
    end

    class EqnNot < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        LogicNode.new(LogicNodeType::Not, [send(:name).to_logic_tree(term_map)])
      end
    end

    class EqnAnd < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        children = T.let([], T::Array[LogicNode])
        children << send(:first).to_logic_tree(term_map)
        send(:r).elements.each do |e|
          children << e.unary_expression.to_logic_tree(term_map)
        end
        LogicNode.new(LogicNodeType::And, children)
      end
    end

    class EqnOr < Treetop::Runtime::SyntaxNode
      extend T::Sig
      sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
      def to_logic_tree(term_map)
        children = T.let([], T::Array[LogicNode])
        children << send(:first).to_logic_tree(term_map)
        send(:r).elements.each do |e|
          children << e.conjunction.to_logic_tree(term_map)
        end
        LogicNode.new(LogicNodeType::Or, children)
      end
    end

    EqnParser = Treetop.load_from_string(EQN_GRAMMAR)

    extend T::Sig
    sig { params(eqn: String).void }
    def initialize(eqn)
      @eqn = eqn
      @parser = EqnParser.new
    end

    sig { params(term_map: T::Hash[String, TermType]).returns(LogicNode) }
    def to_logic_tree(term_map)
      m = @parser.parse(@eqn)
      if m.nil?
        puts "start"
        pp @eqn
        puts "end"
        raise "Error parsing eqn: #{@parser.failure_reason}"
      end

      raise "unexpected" unless m.is_a?(EqnTop)

      m.to_logic_tree(term_map)
    end
  end
end
