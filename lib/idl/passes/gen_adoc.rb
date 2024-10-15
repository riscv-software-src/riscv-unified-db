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
      "#{' '*indent}#{variable.gen_adoc(indent, indent_spaces: )}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}] = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class ConditionalReturnStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{return_expression.gen_adoc(indent, indent_spaces: )} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end
  class ReturnExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}return #{return_value_nodes.map{ |r| r.gen_adoc(0, indent_spaces: )}.join(', ')}"
    end
  end
  class IfBodyAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      adoc = []
      children.each do |e|
        adoc << e.gen_adoc(indent, indent_spaces:)
      end
      adoc.join("\n")
    end
  end

  class PostIncrementExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{rval.gen_adoc(indent, indent_spaces: )}++"
    end
  end
  class PostDecrementExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{rval.gen_adoc(indent, indent_spaces: )}--"
    end
  end
  class StringLiteralAst
    def gen_adoc(indent, indent_spaces: 2)
      # text_value will include leading and trailing quotes
      "#{' '*indent}#{text_value}"
    end
  end
  class DontCareReturnAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}-"
    end
  end
  class UserTypeNameAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{text_value}"
    end
  end
  class MultiVariableAssignmentAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}(#{variables.map { |v| v.gen_adoc(0, indent_spaces: )}.join(', ')} = #{function_call.gen_adoc(0, indent_spaces:)})"
    end
  end
  class CsrFunctionCallAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{csr.gen_adoc(indent, indent_spaces:)}.#{function_name}()"
    end
  end
  class CsrSoftwareWriteAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{csr.gen_adoc(indent, indent_spaces:)}.sw_write(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class FieldAccessExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{obj.gen_adoc(indent, indent_spaces: )}.#{@field_name}"
    end
  end
  class FieldAssignmentAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{field_access.gen_adoc(0, indent_spaces:)} = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class ConcatenationExpressionAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}{#{expressions.map { |e| e.gen_adoc(0, indent_spaces: )}.join(', ')}}"
    end
  end
  class BitsCastAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}$bits(#{expression.gen_adoc(0, indent_spaces: )})"
    end
  end
  class EnumCastAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}$enum(#{enum_name.gen_adoc(0, indent_spaces:)}, #{expression.gen_adoc(0, indent_spaces: )})"
    end
  end
  class CsrFieldAssignmentAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{csr_field.gen_adoc(indent, indent_spaces:)} = #{write_value.gen_adoc(0, indent_spaces:)}"
    end
  end
  class EnumRefAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}#{class_name}::#{member_name}"
    end
  end
  class EnumSizeAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}$enum_size(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class EnumElementSizeAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}$enum_element_size(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class EnumArrayCastAst
    def gen_adoc(indent, indent_spaces: 2)
      "#{' '*indent}$enum_to_a(#{enum_class.gen_adoc(0, indent_spaces:)})"
    end
  end
  class ParenExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_adoc(indent, indent_spaces:)})"
    end
  end
  class IntLiteralAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      raise "?" if text_value.empty?
      "#{' '*indent}#{text_value}"
    end
  end
  class IdAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{text_value}"
    end
  end
  class SignCastAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}$signed+++(+++#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end
  class AryRangeAccessAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{var.gen_adoc(indent, indent_spaces:)}[#{msb.gen_adoc(0, indent_spaces:)}:#{lsb.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class VariableDeclarationAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{id.gen_adoc(0, indent_spaces:)}"
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
        "#{' '*indent}Bits<#{bits_expression.gen_adoc(0, indent_spaces:)}>"
      else
        to_idl
      end
    end
  end

  class ForLoopAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["#{' '*indent}for pass:[(]#{init.gen_adoc(0, indent_spaces:)}; #{condition.gen_adoc(0, indent_spaces:)}; #{update.gen_adoc(0, indent_spaces:)}) {"]
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
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)}"
      else
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)}[#{ary_size.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)}"
      end
    end
  end

  class AryElementAccessAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{var.gen_adoc(indent, indent_spaces:)}[#{index.gen_adoc(0, indent_spaces:)}]"
    end
  end

  class BinaryExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_adoc(0, indent_spaces:)} #{op.sub("+", "pass:[+]")} #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class VariableAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class PcAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}$pc = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class AryElementAssignmentAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_adoc(0, indent_spaces:)}[#{idx.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)}"
    end
  end

  class StatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_adoc(0, indent_spaces:)};"
    end
  end

  class UnaryOperatorExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{op}#{exp.gen_adoc(0, indent_spaces:)}"
    end
  end

  class ReturnStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' ' * indent}return #{return_value_nodes.map { |v| v.gen_adoc(0, indent_spaces:) }.join(', ')};"
    end
  end

  class ReplicationExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}{#{n.gen_adoc(0, indent_spaces:)}{#{v.gen_adoc(indent, indent_spaces:)}}}"
    end
  end

  class ConditionalStatementAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}#{action.gen_adoc(0, indent_spaces:)} if (#{condition.gen_adoc(0, indent_spaces:)});"
    end
  end

  class FunctionCallExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      after_name = []
      after_name << "<#{template_arg_nodes.map { |t| t.gen_adoc(0, indent_spaces:)}.join(', ')}>" unless template_arg_nodes.empty?
      after_name << "pass:[(]#{arg_nodes.map { |a| a.gen_adoc(0, indent_spaces: ) }.join(', ')})"
      "#{' '*indent}%%LINK%func;#{name};#{name}%%#{after_name.join ''}"
    end
  end

  class ArraySizeAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "#{' '*indent}$array_size(#{expression.gen_adoc(0, indent_spaces:)})"
    end
  end

  class FunctionBodyAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      statements.map{ |s| "#{' ' * indent}#{s.gen_adoc(0, indent_spaces:)}" }.join("\n")
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
        "#{' '*indent}#{csr_text}"
      else
        "#{' '*indent}%%LINK%csr_field;#{idx_text}.#{@field_name};#{csr_text}%%"
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
        "#{' '*indent}#{csr_text}"
      else
        "#{' '*indent}%%LINK%csr;#{idx_text};#{csr_text}%%"
      end
    end
  end

  class IfAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      lines = ["#{' '*indent}if pass:[(]#{if_cond.gen_adoc(0, indent_spaces:)}) {"]
      if_body.stmts.each do |s|
        lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
      end
      elseifs.each do |eif|
        lines << "#{' '*indent}} else if pass:[(]#{eif.cond.gen_adoc(0, indent_spaces:)}) {"
        eif.body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      unless final_else_body.stmts.empty?
        lines << "#{' '*indent}} else {"
        final_else_body.stmts.each do |s|
          lines << s.gen_adoc(indent + indent_spaces, indent_spaces:)
        end
      end
      lines << "#{' '*indent}}"

      lines.join("\n")
    end
  end
end
