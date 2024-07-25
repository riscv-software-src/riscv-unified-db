require_relative "../ast"

class Idl::AstNode
  def gen_adoc(indent = 0, indent_spaces: 2)
    internal_error "must implement gen_adoc for #{self.class.name}"
  end
end

module Idl
  class NoopAst
    def gen_adoc(indent = 0, indent_spaces: 2) = ""
  end
  class AryRangeAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{variable.gen_adoc(indent, indent_spaces: )}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}] = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class ConditionalReturnStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{return_expression.gen_adoc(indent, indent_spaces: )} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end
  class ReturnExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "return #{return_value_nodes.map{ |r| r.gen_adoc(0, indent_spaces: )}.join(', ')}"
    end
  end
  class IfBodyAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      adoc = []
      children.each do |e|
        adoc << e.gen_adoc(indent, indent_spaces:)
      end
      adoc.map{ |a| "#{' '*indent}#{a}" }.join("")
    end
  end

  class PostIncrementExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{rval.gen_adoc(indent, indent_spaces: )}++"
    end
  end
  class PostDecrementExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{rval.gen_adoc(indent, indent_spaces: )}--"
    end
  end
  class StringLiteralAst
    def gen_adoc(indent, indent_spaces: 2)
      "\"#{text_value}\""
    end
  end
  class DontCareReturnAst
    def gen_adoc(indent, indent_spaces: 2)
      "-"
    end
  end
  class UserTypeNameAst
    def gen_adoc(indent, indent_spaces: 2)
      text_value
    end
  end
  class MultiVariableAssignmentAst
    def gen_adoc(indent, indent_spaces: 2)
      "(#{variables.map { |v| v.gen_adoc(0, indent_spaces: )}.join(', ')} = #{function_call.gen_adoc(0, indent_spaces:)})"
    end
  end
  class CsrSoftwareReadAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{csr.gen_adoc(indent, indent_spaces:)}.sw_read()"
    end
  end
  class CsrSoftwareWriteAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{csr.gen_adoc(indent, indent_spaces:)}.sw_write(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class BitfieldAccessExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{bitfield.gen_adoc(indent, indent_spaces: )}.#{@field_name}"
    end
  end
  class ConcatenationExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "{#{expressions.map { |e| e.gen_adoc(0, indent_spaces: )}.join(', ')}}"
    end
  end
  class BitsCastAst
    def gen_adoc(indent, indent_spaces: 2)
      "$bits(#{expression.gen_adoc(0, indent_spaces: )})"
    end
  end
  class CsrFieldAssignmentAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{csr_field.gen_adoc(indent, indent_spaces:)} = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class EnumRefAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{class_name}::#{member_name}"
    end
  end
  class ParenExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "(#{expression.gen_adoc(indent, indent_spaces:)})"
    end
  end
  class IntLiteralAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      raise "?" if text_value.empty?
      text_value
    end
  end
  class IdAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      text_value
    end
  end
  class SignCastAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "$signed(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class AryRangeAccessAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{var.gen_adoc(indent, indent_spaces:)}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class VariableDeclarationAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{id.gen_adoc(0, indent_spaces:)};"
    end
  end

  class TernaryOperatorExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{condition.gen_adoc(0, indent_spaces:)} ? #{true_expression.gen_adoc(0, indent_spaces:)} : #{false_expression.gen_adoc(0, indent_spaces:)}"
    end
  end

  class BuiltinTypeNameAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      if @type_name == "Bits"
        "Bits<#{bits_expression.gen_adoc(0, indent_spaces:)}>"
      else
        to_idl
      end
    end
  end

  class ForLoopAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["#{' '*indent}for (#{init.gen_adoc(0, indent_spaces:)}; #{condition.gen_adoc(0, indent_spaces:)}; #{update.gen_adoc(0, indent_spaces:)}) {"]
      stmts.each do |s|
        lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
      end
      lines << "#{' '*indent}}"
      lines.join("\n")
    end
  end

  class BuiltinVariableAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      name
    end
  end

  class VariableDeclarationWithInitializationAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      if ary_size.nil?
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)};"
      else
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)}[#{ary_size.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)};"
      end
    end
  end

  class AryElementAccessAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{var.gen_adoc(indent, indent_spaces:)}[#{index.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class BinaryExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{lhs.gen_adoc(0, indent_spaces:)} #{op} #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class VariableAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class AryElementAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{lhs.gen_adoc(0, indent_spaces:)}[#{idx.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class StatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_adoc(0, indent_spaces:)};"
    end
  end

  class UnaryOperatorExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{op}#{exp.gen_adoc(0, indent_spaces:)}"
    end
  end

  class ReturnStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}return #{return_value_nodes.map { |v| v.gen_adoc(0, indent_spaces:) }.join(', ')};"
    end
  end

  class ReplicationExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "{#{n.gen_adoc(indent, indent_spaces:)}{#{v.gen_adoc(indent, indent_spaces:)}}}"
    end
  end

  class ConditionalStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{action.gen_adoc(indent, indent_spaces:)} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end

  class FunctionCallExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      after_name = []
      after_name << "<#{template_arg_nodes.map { |t| t.gen_adoc(0, indent_spaces:)}.join(', ')}>" unless template_arg_nodes.empty?
      after_name << "(#{arg_nodes.map { |a| a.gen_adoc(0, indent_spaces: ) }.join(', ')})"
      "%%LINK%func;#{name};#{name}%%#{after_name.join ''}"
    end
  end

  class FunctionBodyAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      statements.map{ |s| "#{' ' * indent}#{s.gen_adoc(indent, indent_spaces:)}" }.join("\n")
    end
  end

  class CsrFieldReadExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      idx_text =
        if @idx.is_a?(AstNode)
          @idx.text_value
        else
          @idx
        end
      csr_text = "CSR[#{idx_text}].#{@field_name}"
      if idx_text =~ /[0-9]+/
        csr_text
      else
        "%%LINK%csr_field;#{idx_text}.#{@field_name};#{csr_text}%%"
      end
    end
  end

  class CsrReadExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      idx_text =
        if @idx.is_a?(AstNode)
          @idx.text_value
        else
          @idx
        end

      csr_text = "CSR[#{idx_text}]"
      if idx_text =~ /[0-9]+/
        # we don't have the symtab to map this to a csr name
        csr_text
      else
        "%%LINK%csr;#{idx_text};#{csr_text}%%"
      end
    end
  end

  class IfAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["if (#{if_cond.gen_adoc(0, indent_spaces:)}) {"]
      if_body.stmts.each do |s|
        lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
      end
      elseifs.each do |eif|
        lines << "} else if (#{eif.cond.gen_adoc(0, indent_spaces:)}) {"
        eif.body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      unless final_else_body.stmts.empty?
        lines << "} else {"
        final_else_body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      lines << "}"

      lines.map { |l| "#{' ' * indent}#{l}"}.join("\n")
    end
  end
end
