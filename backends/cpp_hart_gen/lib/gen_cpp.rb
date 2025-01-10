
module Idl
  class AstNode
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      internal_error "Need to implemente #gen_cpp for #{self.class.name}"
    end
  end

  class NoopAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2) = ";"
  end

  class AryRangeAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      expression = nil
      value_result = value_try do
        # see if msb, lsb is compile-time-known
        _ = msb.value(symtab)
        _ = lsb.value(symtab)
        expression = "bit_insert(#{variable.gen_cpp(symtab)}, #{msb.gen_cpp(symtab)}, #{lsb.gen_cpp(symtab)}, #{write_value.gen_cpp(symtab)})"
      end
      value_else(value_result) do
        expression = "bit_insert<#{msb.gen_cpp(symtab)}, #{lsb.gen_cpp(symtab)}>(#{variable.gen_cpp(symtab)}, #{write_value.gen_cpp(symtab)})"
      end

      "#{' ' * indent}#{expression}"
    end
  end

  class ConditionalReturnStatementAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = <<~CPP
        if (#{condition.gen_cpp(symtab, 0, indent_spaces:)}) {
        #{return_expression.gen_cpp(symtab, indent_spaces, indent_spaces:)};
        }
      CPP
      "#{' ' * indent}#{cpp.gsub("\n", "\n#{' ' * indent}")}"
    end
  end

  class ReturnExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{return_expression.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class IfBodyAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = []
      children.each do |child|
        cpp << child.gen_cpp(symtab, indent, indent_spaces:)
      end
      cpp.join("\n")
    end
  end

  class PostIncrementExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_cpp(symtab, indent, indent_spaces:)}++"
    end
  end

  class PostDecrementExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_cpp(symtab, indent, indent_spaces:)}--"
    end
  end

  class StringLiteralAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      # text_value will include leading and trailing quotes
      "#{' ' * indent}#{text_value}"
    end
  end

  class DontCareReturnAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}std::ignore"
    end
  end

  class UserTypeNameAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{text_value}"
    end
  end

  class MultiVariableAssignmentAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      lhs = "std::tie(#{variables.map { |v| v.gen_cpp(symtab, 0, indent_spaces: )}.join(', ')})"
      rhs = function_call.gen_cpp(symtab, 0, indent_spaces:)
      "#{' ' * indent}#{lhs} = #{rhs}"
    end
  end

  class CsrFunctionCallAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      csr_ref = csr.gen_cpp(symtab, 0, indent_spaces:)
      "#{' ' * indent}#{csr_ref}.#{function_name}()"
    end
  end

  class CsrSoftwareWriteAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      csr_ref = csr.gen_cpp(symtab, 0, indent_spaces:)
      "#{' ' * indent}#{csr_ref}.sw_write(#{expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class FieldAccessExpressionAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{obj.gen_cpp(symtab, 0, indent_spaces: )}.#{@field_name}"
    end
  end

  class FieldAssignmentAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{field_access.gen_cpp(symtab, 0, indent_spaces:)} = #{write_value.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class ConcatenationExpressionAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}concat(#{expressions.map { |e| e.gen_cpp(symtab, 0, indent_spaces: )}.join(', ')})"
    end
  end

  class BitsCastAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      width = expression.type(symtab).width
      if (width == :unknown)
        "#{' '*indent}Bits<BitsInfinitePrecision>(#{expression.gen_cpp(symtab, 0, indent_spaces: )})"
      else
        "#{' '*indent}Bits<#{width}>(#{expression.gen_cpp(symtab, 0, indent_spaces: )})"
      end
    end
  end

  class EnumCastAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{enum_name.gen_cpp(symtab, 0, indent_spaces:)}{#{expression.gen_cpp(symtab, 0, indent_spaces: )}})"
    end
  end

  class CsrFieldAssignmentAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{csr_field.gen_cpp(symtab, 0, indent_spaces:)}.write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class EnumRefAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{class_name}::#{member_name}"
    end
  end

  class EnumSizeAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{value(symtab)}"
    end
  end

  class EnumElementSizeAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}#{value(symtab)}"
    end
  end

  class EnumArrayCastAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      "#{' '*indent}std::array<Bits<#{enum_class.type(symtab).width}>, #{enum_class.type(symtab).element_names.size}> {#{enum_class.type(symtab).element_values.map(&:to_s).join(', ')}}"
    end
  end

  class ParenExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class IntLiteralAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      v = value(symtab)
      if v >= 0
        if v.bit_length <= 64
          "#{' ' * indent}#{value(symtab)}ULL"
        else
          "#{' ' * indent}#{value(symtab)}_b"
        end
      else
        if v.bit_length <= 63
          "#{' ' * indent}#{value(symtab)}LL"
        else
          "#{' ' * indent}#{value(symtab)}_b"
        end
      end
    end
  end

  class IdAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      var = symtab.get(text_value)

      if !var.nil? && var.param?
        if var.value.nil?
          "#{' ' * indent}__UDB_RUNTIME_PARAM(#{text_value})"
        else
          "#{' ' * indent}__UDB_STATIC_PARAM(#{text_value})"
        end
      else
        "#{' ' * indent}#{text_value}"
      end
    end
  end

  class SignCastAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)}).make_signed()"
    end
  end

  class AryRangeAccessAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      value_result = value_try do
        return "#{' '*indent}extract<#{lsb.value(symtab)}, #{msb.value(symtab) - lsb.value(symtab) + 1}>(#{var.gen_cpp(symtab, 0, indent_spaces:)})"
      end
      value_else(value_result) do
        # we don't know the value of something (probably a param), so we need the slow extract
        return "#{' '*indent}extract(#{var.gen_cpp(symtab, 0, indent_spaces:)}, #{lsb.gen_cpp(symtab, 0, indent_spaces:)}, #{msb.gen_cpp(symtab, 0, indent_spaces:)} - #{lsb.gen_cpp(symtab, 0, indent_spaces:)} + 1)"
      end
    end
  end

  class VariableDeclarationAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      add_symbol(symtab)
      "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{id.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class MultiVariableDeclarationAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      add_symbol(symtab)
      "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{var_name_nodes.map { |var| var.gen_cpp(symtab, 0, indent_spaces:) }.join(', ')}"
    end
  end

  class TernaryOperatorExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}(#{condition.gen_cpp(symtab, 0, indent_spaces:)}) ? (#{true_expression.gen_cpp(symtab, 0, indent_spaces:)}) : (#{false_expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class BuiltinTypeNameAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if @type_name == "Bits"
        "#{' '*indent}Bits<#{bits_expression.gen_cpp(symtab, 0, indent_spaces:)}>"
      elsif @type_name == "XReg"
        "#{' '*indent}Bits<#{symtab.cfg_arch.possible_xlens.max()}>"
      elsif @type_name == "Boolean"
        "#{' '*indent}bool"
      elsif @type_name == "U32"
        "#{' '*indent}Bits<32>"
      elsif @type_name == "U64"
        "#{' '*indent}Bits<64>"
      elsif @type_name == "String"
        "#{' '*indent}std::string"
      else
        raise "TODO: #{@type_name}"
      end
    end
  end

  class ForLoopAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      # lines = ["#{' '*indent}for pass:[(]#{init.gen_cpp(0, indent_spaces:)}; #{condition.gen_cpp(0, indent_spaces:)}; #{update.gen_cpp(0, indent_spaces:)}) {"]
      lines = []
      symtab.push(nil)
      init.add_symbol(symtab)
      stmts.each do |s|
        lines << s.gen_cpp(symtab, indent_spaces, indent_spaces:)
      end
      cpp = <<~LOOP
        for (#{init.gen_cpp(symtab, 0, indent_spaces:)}; #{condition.gen_cpp(symtab, 0, indent_spaces:)}; #{update.gen_cpp(symtab, 0, indent_spaces:)}) {
        #{lines.join("\n")}
        }
      LOOP
      symtab.pop()
      cpp.lines.map { |l| "#{' ' * indent}#{l}" }.join('')
    end
  end

  class BuiltinVariableAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      case name
      when "$encoding"
        "#{' ' * indent}__UDB_ENCODING"
      when "$pc"
        "#{' ' * indent}__UDB_PC"
      else
        raise "TODO: #{name}"
      end
    end
  end

  class VariableDeclarationWithInitializationAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      add_symbol(symtab)
      if ary_size.nil?
        "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      else
        "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab, 0, indent_spaces:)}, #{ary_size.gen_cpp(symtab, 0, indent_spaces:)}> #{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      end
    end
  end

  class AryElementAccessAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if var.text_value.start_with?("X")
        #"#{' '*indent}#{var.gen_cpp(symtab, 0, indent_spaces:)}[#{index.gen_cpp(symtab, 0, indent_spaces:)}]"
        "#{' '*indent} __UDB__FUNC__OBJ  xregRef(#{index.gen_cpp(symtab, 0, indent_spaces:)})"
      else
        "#{' '*indent}#{var.gen_cpp(symtab, 0, indent_spaces:)}[#{index.gen_cpp(symtab, 0, indent_spaces:)}]"
      end
    end
  end

  class BinaryExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)} #{op} #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class VariableAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class PcAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}__USB_SET_PC(#{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class AryElementAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if lhs.text_value.start_with?("X")
        #"#{' '*indent}  #{lhs.gen_cpp(symtab, 0, indent_spaces:)}[#{idx.gen_cpp(symtab, 0, indent_spaces:)}] = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
        "#{' '*indent} __UDB__FUNC__OBJ xregRef ( #{idx.gen_cpp(symtab, 0, indent_spaces:)} ) = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      else
        "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)}[#{idx.gen_cpp(symtab, 0, indent_spaces:)}] = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      end
    end
  end

  class StatementAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_cpp(symtab, 0, indent_spaces:)};"
    end
  end

  class UnaryOperatorExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}#{op}(#{exp.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class ReturnStatementAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      expression =
        if return_value_nodes.size == 1
          "return #{return_value_nodes[0].gen_cpp(symtab, 0, indent_spaces:)};"
        else
          return_types = return_value_nodes.map { |rv| rv.type(symtab).to_cxx }
          return_values = return_value_nodes.map { |rv| rv.gen_cpp(symtab, 0, indent_spaces:) }
          "return std::tuple<#{return_types.join(', ')}>{#{return_values.join(', ')}};"
        end
      "#{' ' * indent}#{expression}"
    end
  end

  class ReplicationExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}replicate<#{n.gen_cpp(symtab, 0, indent_spaces:)}>(#{v.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class ConditionalStatementAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = <<~IF
        if (#{condition.gen_cpp(symtab, 0, indent_spaces:)}) {
        #{action.gen_cpp(symtab, indent_spaces, indent_spaces:)}
        }
      IF
      cpp.lines.map { |l| "#{' ' * indent}#{l}" }.join("")
    end
  end

  class FunctionCallExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      after_name = []
      targs_cpp = template_arg_nodes.map { |t| t.gen_cpp(symtab, 0, indent_spaces:) }
      args_cpp = arg_nodes.map { |a| a.gen_cpp(symtab, 0, indent_spaces:) }
      if targs_cpp.empty?
        "__UDB__FUNC__OBJ #{name.gsub("?", "_Q_")}(#{args_cpp.join(', ')})"
      else
        "__UDB__FUNC__OBJ #{name.gsub("?", "_Q_")}<#{targs_cpp.join(', ')}>(#{args_cpp.join(', ')})"
      end
    end
  end

  class ArraySizeAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)}).size()"
    end
  end

  class FunctionBodyAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      statements.map{ |s| "#{' ' * indent}#{s.gen_cpp(symtab, 0, indent_spaces:)}" }.join("\n")
    end
  end

  class CsrFieldReadExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if @idx.is_a?(AstNode)
        "#{' '*indent}__UDB_CSR_BY_ADDR(#{@idx.gen_cpp(symtab, 0, indent_spaces:)}).#{@field_name}"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{@idx}).#{@field_name}"
      end
    end
  end

  class CsrReadExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if @idx.is_a?(AstNode)
        "#{' '*indent}__UDB_CSR_BY_ADDR(#{@idx.gen_cpp(symtab, 0, indent_spaces:)}).hw_read()"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{@idx}).hw_read()"
      end
    end
  end

  class IfAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = []
      cpp << "if (#{if_cond.gen_cpp(symtab, 0, indent_spaces:)}) {"
      if_body.stmts.each do |stmt|
        cpp << stmt.gen_cpp(symtab, indent_spaces, indent_spaces:)
      end
      elseifs.each do |eif|
        cpp << "} else if (#{eif.cond.gen_cpp(symtab, 0, indent_spaces:)}) {"
        eif.body.stmts.each do |s|
          cpp << s.gen_cpp(symtab, indent_spaces, indent_spaces:)
        end
      end
      unless final_else_body.stmts.empty?
        cpp << "} else {"
        final_else_body.stmts.each do |s|
          cpp << s.gen_cpp(symtab, indent_spaces, indent_spaces:)
        end
      end
      cpp << "}"
      cpp.map { |l| "#{' ' * indent}#{l}" }.join("\n")
    end
  end
end
