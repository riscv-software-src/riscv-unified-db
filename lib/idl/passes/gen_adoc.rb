require_relative "../ast"

class Idl::AstNode
  def gen_adoc(indent = 0, indent_spaces: 2)
    adoc = []
    puts self.class.name if elements.nil?
    elements.each do |e|
      next unless e.is_a?(Idl::AstNode)

      adoc << e.gen_adoc(indent, indent_spaces:)
    end
    adoc.map{ |a| "#{' '*indent}#{a}" }.join('')
  end
  # def gen_adoc(indent = 0, indent_spaces: 2)
  #   if terminal?
  #     text_value
  #   else
  #     adoc = ''
  #     next_pos = interval.begin
  #     elements.each do |e|
  #       if e.interval.size > 0 &&  e.interval.begin != next_pos
  #         adoc << input[next_pos..(e.interval.begin - 1)]
  #       end
  #       adoc << e.gen_adoc(indent+2, indent_spaces: 2)
  #       next_pos = e.interval.exclude_end? ? e.interval.end : (e.interval.end + 1)
  #     end
  #     if next_pos != (interval.exclude_end? ? interval.end : (interval.end + 1))
  #       end_pos = interval.exclude_end? ? interval.end - 1 : interval.end
  #       adoc << input[next_pos..end_pos]
  #     end
  #     if adoc != text_value && !text_value.index('xref').nil?
  #       raise
  #     end
  #     adoc
  #   end
  # end
end

module Idl
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
      "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{var_write.gen_adoc(0, indent_spaces:)};"
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
        "Bits<#{@bits_expression.gen_adoc(0, indent_spaces:)}>"
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
      if @ary_size.nil?
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)} = #{rhs.gen_adoc(0, indent_spaces:)};"
      else
        "#{' ' * indent}#{type_name.gen_adoc(0, indent_spaces:)} #{lhs.gen_adoc(0, indent_spaces:)}[#{@ary_size.gen_adoc(0, indent_spaces:)}] = #{rhs.gen_adoc(0, indent_spaces:)};"
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
      "#{lhs.gen_adoc(0, indent_spaces:)}[#{@idx.gen_adoc(0, indent_spaces:)}] = #{@rhs.gen_adoc(0, indent_spaces:)}"
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
      values = [first.gen_adoc(0, indent_spaces:)] + rest.elements.each { |e| e.e.gen_adoc(0, indent_spaces: )}
      "#{' ' * indent}return #{values.join(', ')};"
    end
  end

  class ReplicationExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      puts v.class.name
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
      csr_text = "CSR[#{idx.text_value}].#{csr_field_name.text_value}"
      if idx.text_value =~ /[0-9]+/
        csr_text
      else
        "%%LINK%csr_field;#{idx.text_value}.#{csr_field_name.text_value};#{csr_text}%%"
      end
    end
  end

  class CsrReadExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      csr_text = "CSR[#{idx.text_value}]"
      if idx.text_value =~ /[0-9]+/
        csr_text
      else
        "%%LINK%csr;#{idx.text_value};#{csr_text}%%"
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
