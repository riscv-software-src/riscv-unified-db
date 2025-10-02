# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "../ast"

class Idl::AstNode
  def gen_adoc(indent = 0, indent_spaces: 2)
    internal_error "must implement gen_adoc for #{self.class.name}"
  end
end

module Idl
  class NoopAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2) = ""
  end
  class AryRangeAssignmentAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{variable.gen_adoc(indent, indent_spaces:)}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}] = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class ConditionalReturnStatementAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{return_expression.gen_adoc(indent, indent_spaces:)} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end
  class ReturnExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}return #{return_value_nodes.map { |r| r.gen_adoc(0, indent_spaces:) }.join(', ')}"
    end
  end
  class IfBodyAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      adoc = []
      children.each do |e|
        adoc << e.gen_adoc(indent, indent_spaces:)
      end
      adoc.join("\n")
    end
  end

  class PostIncrementExpressionAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_adoc(indent, indent_spaces:)}++"
    end
  end
  class PostDecrementExpressionAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_adoc(indent, indent_spaces:)}--"
    end
  end
  class StringLiteralAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      # text_value will include leading and trailing quotes
      "#{' ' * indent}#{text_value}"
    end
  end
  class DontCareReturnAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}-"
    end
  end
  class UserTypeNameAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{text_value}"
    end
  end
  class MultiVariableAssignmentAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}(#{variables.map { |v| v.gen_adoc(0, indent_spaces:) }.join(', ')} = #{function_call.gen_adoc(0, indent_spaces:)})"
    end
  end
  class CsrFunctionCallAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      args_adoc = args.map { |arg| arg.gen_adoc(0) }
      "#{' ' * indent}#{csr.gen_adoc(indent, indent_spaces:)}.#{function_name}(#{args_adoc.join(', ')})"
    end
  end
  class CsrSoftwareWriteAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{csr.gen_adoc(indent, indent_spaces:)}.sw_write(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class FieldAccessExpressionAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{obj.gen_adoc(indent, indent_spaces:)}.#{@field_name}"
    end
  end
  class FieldAssignmentAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{id.gen_adoc(0, indent_spaces:)}.#{@field_name} = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end
  class ConcatenationExpressionAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}{#{expressions.map { |e| e.gen_adoc(0, indent_spaces:) }.join(', ')}}"
    end
  end
  class BitsCastAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}$bits(#{expr.gen_adoc(0, indent_spaces:)})"
    end
  end
  class EnumCastAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}$enum(#{enum_name.gen_adoc(0, indent_spaces:)}, #{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class CsrFieldAssignmentAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{csr_field.gen_adoc(indent, indent_spaces:)} = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class EnumRefAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}#{class_name}::#{member_name}"
    end
  end
  class EnumSizeAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}$enum_size(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class EnumElementSizeAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}$enum_element_size(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class EnumArrayCastAst < AstNode
    def gen_adoc(indent, indent_spaces: 2)
      "#{' ' * indent}$enum_to_a(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class ParenExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}(#{expression.gen_adoc(indent, indent_spaces:)})"
    end
  end
  class IntLiteralAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      raise "?" if text_value.empty?
      "#{' ' * indent}#{text_value}"
    end
  end
  class TrueExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}true"
    end
  end
  class FalseExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}false"
    end
  end
  class IdAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{text_value}"
    end
  end
  class SignCastAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}$signed+++(+++#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class AryRangeAccessAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{var.gen_adoc(indent, indent_spaces:)}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class VariableDeclarationAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{id.gen_adoc(0, indent_spaces:)}"
    end
  end

  class MultiVariableDeclarationAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{var_name_nodes.map { |var| var.gen_adoc(0, indent_spaces:) }.join(', ')}"
    end
  end

  class TernaryOperatorExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{condition.gen_adoc(0, indent_spaces:)} ? #{true_expression.gen_adoc(0, indent_spaces:)} : #{false_expression.gen_adoc(0, indent_spaces:)}"
    end
  end

  class BuiltinTypeNameAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      if @type_name == "Bits"
        "#{' ' * indent}Bits<#{bits_expression.gen_adoc(0, indent_spaces:)}>"
      else
        to_idl
      end
    end
  end

  class ForLoopAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["#{' ' * indent}for pass:[(]#{init.gen_adoc(0, indent_spaces:)}; #{condition.gen_adoc(0, indent_spaces:)}; #{update.gen_adoc(0, indent_spaces:)}) {"]
      stmts.each do |s|
        lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
      end
      lines << "#{' ' * indent}}"
      lines.join("\n")
    end
  end

  class BuiltinVariableAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      name
    end
  end

  class VariableDeclarationWithInitializationAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      if ary_size.nil?
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)}"
      else
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)}[#{ary_size.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)}"
      end
    end
  end

  class AryElementAccessAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{var.gen_adoc(indent, indent_spaces:)}[#{index.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class BinaryExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{lhs.gen_adoc(0, indent_spaces:)} #{op.sub("+", "pass:[+]").sub("`", "pass:[`]")} #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class VariableAssignmentAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class PcAssignmentAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}$pc = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class AryElementAssignmentAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{lhs.gen_adoc(0, indent_spaces:)}[#{idx.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class StatementAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_adoc(0, indent_spaces:)};"
    end
  end

  class UnaryOperatorExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{op}#{exp.gen_adoc(0, indent_spaces:)}"
    end
  end

  class ReturnStatementAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}return #{return_value_nodes.map { |v| v.gen_adoc(0, indent_spaces:) }.join(', ')};"
    end
  end

  class ReplicationExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}{#{n.gen_adoc(0, indent_spaces:)}{#{v.gen_adoc(indent, indent_spaces:)}}}"
    end
  end

  class ConditionalStatementAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_adoc(0, indent_spaces:)} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end

  class FunctionCallExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      after_name = []
      after_name << "<#{template_arg_nodes.map { |t| t.gen_adoc(0, indent_spaces:) }.join(', ')}>" unless template_arg_nodes.empty?
      after_name << "pass:[(]#{arg_nodes.map { |a| a.gen_adoc(0, indent_spaces:) }.join(', ')})"
      "#{' ' * indent}" + link_to_udb_doc_idl_func("#{name}") + "#{after_name.join ''}"
    end
  end

  class ArraySizeAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}$array_size(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end

  class FunctionBodyAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      statements.map { |s| "#{' ' * indent}#{s.gen_adoc(0, indent_spaces:)}" }.join("\n")
    end
  end

  class CsrFieldReadExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}" + link_to_udb_doc_csr_field("#{@csr_obj.name}", "#{@field_name}")
    end
  end

  class CsrReadExpressionAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}" + link_to_udb_doc_csr("#{csr_name}")
    end
  end

  class IfAst < AstNode
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["#{' ' * indent}if pass:[(]#{if_cond.gen_adoc(0, indent_spaces:)}) {"]
      if_body.stmts.each do |s|
        lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
      end
      elseifs.each do |eif|
        lines << "#{' ' * indent}} else if pass:[(]#{eif.cond.gen_adoc(0, indent_spaces:)}) {"
        eif.body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      unless final_else_body.stmts.empty?
        lines << "#{' ' * indent}} else {"
        final_else_body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      lines << "#{' ' * indent}}"

      lines.join("\n")
    end
  end
end
