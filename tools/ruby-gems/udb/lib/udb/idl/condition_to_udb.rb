# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require "idlc/ast"

module Idl
  class AstNode
    extend T::Sig

    UdbHashType = T.type_alias do T.any(T::Hash[String, T.untyped], T::Boolean) end

    sig { overridable.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      raise "Need to implement #{self.class.name}::to_udb_h in #{__FILE__}"
    end
  end

  class ImplicationExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      if antecedent.is_a?(TrueExpressionAst)
        consequent.to_udb_h(symtab)
      else
        {
          "if" => antecedent.to_udb_h(symtab),
          "then" => consequent.to_udb_h(symtab)
        }
      end
    end
  end

  class ParenExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      expression.to_udb_h(symtab)
    end
  end

  class ImplicationStatementAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      expression.to_udb_h(symtab)
    end
  end

  class ConstraintBodyAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      if @children.size == 1
        @children.fetch(0).to_udb_h(symtab)
      else
        {
          "allOf" => @children.map { |child| child.to_udb_h(symtab) }
        }
      end
    end
  end

  class TrueExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab) = true
  end

  class FalseExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab) = false
  end

  class IdAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      {
        "param" => {
          "name" => name,
          "equal" => true
        }
      }
    end
  end

  class ForLoopAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      res = { "allOf" => [] }

      symtab.push(self)
      init.execute(symtab)
      while condition.value(symtab)
        stmts.each do |stmt|
          if stmt.is_a?(ImplicationStatementAst)
            res["allOf"] << stmt.to_udb_h(symtab)
          elsif stmt.is_a?(ReturnStatementAst)
            raise "Returns are not allowed in constraints"
          else
            stmt.execute(symtab)
          end
        end
        update.execute(symtab)
      end
      symtab.pop

      res
    end
  end

  class AryElementAccessAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      {
        "param" => {
          "name" => var.name,
          "index" => index.value(symtab),
          "equal" => true
        }
      }
    end
  end

  class UnaryOperatorExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      case @op
      when "!"
        {
          "not" => exp.to_udb_h(symtab)
        }
      when "-", "~"
        raise "No conversion for -/~"
      else
        raise "Unexpected"
      end
    end
  end

  class FunctionCallExpressionAst < AstNode
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      case name
      when "implemented?"
        type_error "Bad argument to implemented?" unless args.fetch(0).text_value =~ /^ExtensionName::[A-Z][a-z0-9]*$/
        {
          "extension" => {
            "name" => args.fetch(0).text_value.gsub("ExtensionName::", "")
          }
        }
      when "implemented_version?"
        type_error "Bad first argument to implemented_version?" unless args.fetch(0).text_value =~ /^ExtensionName::[A-Z][a-z0-9]*$/
        type_error "Bad second argument to implemented_version?" unless args.fetch(1).text_value =~ /((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))\s*([0-9]+)(?:\.([0-9]+)(?:\.([0-9]+)(?:-(pre))?)?)?/
        {
          "extension" => {
            "name" => args.fetch(0).text_value.gsub("ExtensionName::", ""),
            "version" => args.fetch(1).text_value.gsub('"', "")
          }
        }
      when "$array_includes?"
        {
          "param" => {
            "name" => args.fetch(0).text_value,
            "includes" => args.fetch(1).value(symtab)
          }
        }
      else
        type_error "unsupported function in an IDL condition: #{name}"
      end
    end
  end

  class BinaryExpressionAst < AstNode
    OP_TO_KEY = {
      "==" => "equal",
      "!=" => "not_equal",
      ">" => "greater_than",
      "<" => "less_than",
      ">=" => "greater_than_or_equal",
      "<=" => "less_than_or_equal"
    }
    sig { override.params(symtab: Idl::SymbolTable).returns(UdbHashType) }
    def to_udb_h(symtab)
      case @op
      when "&&"
        {
          "allOf" => [
            lhs.to_udb_h(symtab),
            rhs.to_udb_h(symtab)
          ]
        }
      when "||"
        {
          "anyOf" => [
            lhs.to_udb_h(symtab),
            rhs.to_udb_h(symtab)
          ]
        }
      when "==", "!=", "<", ">", "<=", ">="
        if lhs.is_a?(IdAst)
          value_result = value_try do
            return {
              "param" => {
                "name" => lhs.name,
                OP_TO_KEY.fetch(@op) => rhs.value(symtab)
              }
            }
          end
          value_else(value_result) do
            raise "Comparison value (#{lhs.text_value}) must be compile-time evaluatable in #{text_value}"
          end
        elsif lhs.is_a?(AryElementAccessAst)
          raise "#{lhs.var.text_value} is not a parameter" unless lhs.var.is_a?(IdAst)

          index_value = T.let(nil, T.nilable(Integer))
          value_result = value_try do
            index_value = lhs.index.value(symtab)
          end
          value_else(value_result) do
            raise "Array index value (#{lhs.index.text_value}) must be known at compile time in #{text_value}"
          end

          value_result = value_try do
            return {
              "param" => {
                "name" => lhs.name,
                OP_TO_KEY.fetch(@op) => rhs.value(symtab),
                "index" => T.must(index_value)
              }
            }
          end
          value_else(value_result) do
            raise "Comparison value (#{rhs.text_value}) must be compile-time evaluatable in #{text_value}"
          end
        elsif rhs.is_a?(IdAst)
          value_result = value_try do
            return {
              "param" => {
                "name"  => rhs.name,
                OP_TO_KEY.fetch(@op) => lhs.value(symtab)
              }
            }
          end
          value_else(value_result) do
            raise "Comparison value (#{lhs.text_value}) must be compile-time evaluatable in #{text_value}"
          end
        elsif rhs.is_a?(AryElementAccessAst)
          raise "#{rhs.var.text_value} is not a parameter" unless rhs.var.is_a?(IdAst)

          index_value = T.let(nil, T.nilable(Integer))
          value_result = value_try do
            index_value = rhs.index.value(symtab)
          end
          value_else(value_result) do
            raise "Array index value (#{rhs.index.text_value}) must be known at compile time in #{text_value}"
          end

          value_result = value_try do
            return {
              "param" => {
                "name" => rhs.name,
                OP_TO_KEY.fetch(@op) => lhs.value(symtab),
                "index" => T.must(index_value)
              }
            }
          end
          value_else(value_result) do
            raise "Comparison value (#{lhs.text_value}) must be compile-time evaluatable in #{text_value}"
          end
        else
          raise "'#{text_value}' can not be converted to UDB YAML"
        end
      else
        raise "'#{text_value}` uses an operator (#{@op}) that cannot be converted to UDB YAML"
      end
    end
  end
end
