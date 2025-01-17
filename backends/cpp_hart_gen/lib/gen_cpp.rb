
require_relative "constexpr_pass"

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
        expression = "bit_insert<#{msb.gen_cpp(symtab)}, #{lsb.gen_cpp(symtab)}>(#{variable.gen_cpp(symtab)}, #{write_value.gen_cpp(symtab)})"
      end
      value_else(value_result) do
        expression = "bit_insert(#{variable.gen_cpp(symtab)}, #{msb.gen_cpp(symtab)}, #{lsb.gen_cpp(symtab)}, #{write_value.gen_cpp(symtab)})"
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
      type = symtab.get(text_value)
      if type.kind == :struct
        "#{' ' * indent}__UDB_STRUCT(#{text_value})"
      else
        "#{' ' * indent}#{text_value}"
      end
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
      if csr.idx.is_a?(AstNode)
        if symtab.cfg_arch.csr(csr.idx.text_value).nil?
          "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr.idx.gen_cpp(symtab, 0, indent_spaces:)}).#{function_name}(__UDB_XLEN)"
        else
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.idx.text_value})._#{function_name}()"
        end
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.idx})._#{function_name}()"
      end
    end
  end

  class FunctionDefAst
    def gen_return_type(symtab)
      if templated?
        template_names.each_with_index do |tname, idx|
          symtab.add!(tname, Var.new(tname, template_types(symtab)[idx]))
        end
      end

      cpp =
        if @return_type_nodes.empty?
          "void"
        elsif @return_type_nodes.size == 1
          @return_type_nodes[0].gen_cpp(symtab, 0)
        else
          rts = @return_type_nodes.map { |rt| rt.gen_cpp(symtab, 0) }
          "std::tuple<#{rts.join(', ')}>"
        end

      if templated?
        template_names.each do |tname|
          symtab.del(tname)
        end
      end

      cpp
    end

    def gen_cpp_argument_list(symtab)
      if templated?
        template_names.each_with_index do |tname, idx|
          symtab.add!(tname, Var.new(tname, template_types(symtab)[idx]))
        end
      end

      list = @argument_nodes.map { |arg| arg.gen_cpp(symtab, 0) }.join(", ")

      if templated?
        template_names.each do |tname|
          symtab.del(tname)
        end
      end

      list
    end

    def gen_cpp_template(symtab)
      if !templated?
        ""
      else
        list = []
        ttypes = template_types(symtab)
        ttypes.each_index { |i|
          list << "#{ttypes[i].to_cxx_no_qualifiers} #{template_names[i]}"
        }
        "template <#{list.join(', ')}>"
      end
    end

    def gen_cpp_prototype(symtab, indent, indent_spaces: 2, include_semi: true)
      <<~PROTOTYPE
        #{' ' * indent}#{gen_cpp_template(symtab)}
        #{' ' * indent}#{name == 'raise' ? '[[noreturn]] ' : ''}#{constexpr?(symtab) ? 'constexpr static ' : ''}#{gen_return_type(symtab)} #{name.gsub('?', '_Q_')}(#{gen_cpp_argument_list(symtab)})#{include_semi ? ';' : ''}
      PROTOTYPE
    end
  end

  class CsrSoftwareWriteAst
    def gen_cpp(symtab, indent, indent_spaces: 2)
      # csr isn't known at runtime for sw_write...
      "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr.idx.gen_cpp(symtab, 0, indent_spaces:)}).sw_write(#{expression.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
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
      t = expression.type(symtab)
      width =
        if t.kind == :enum_ref
          t.enum_class.width
        else
          t.width
        end

      if width == :unknown
        "#{' '*indent}Bits<BitsInfinitePrecision>(#{expression.gen_cpp(symtab, 0, indent_spaces: )})"
      else
        raise "nil" if width.nil?
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

      field  = csr_field.field_def(symtab)
      if symtab.cfg_arch.multi_xlen? && field.dynamic_location?
        if csr_field.idx.is_a?(AstNode)
          "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr_field.idx.gen_cpp(symtab, 0)}).#{field.name}().hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
        else
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_field.csr_name(symtab)}).#{field.name}()._hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
        end
      else
        if csr_field.idx.is_a?(AstNode)
          "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr_field.idx.gen_cpp(symtab, 0)}).#{field.name}().hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)})"
        else
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_field.csr_name(symtab)}).#{field.name}()._hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)})"
        end
      end
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
        "#{' ' * indent}#{value(symtab)}_b"
      else
        if v.bit_length <= 127
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
        if constexpr?(symtab)
          "#{' ' * indent}__UDB_STATIC_PARAM(#{text_value}) /* #{var.value} */"
        else
          "#{' ' * indent}__UDB_RUNTIME_PARAM(#{text_value})"
        end
      elsif !var.nil? && var.type.global?
        if var.type.const?
          "#{' ' * indent}__UDB_CONST_GLOBAL(#{text_value})"
        else
          "#{' ' * indent}__UDB_MUTABLE_GLOBAL(#{text_value})"
        end
      elsif !var.nil? && var.decode_var?
        "#{' ' * indent}#{text_value}()"
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
      "#{' ' * indent}(#{condition.gen_cpp(symtab, 0, indent_spaces:)}) ? static_cast<#{type(symtab).to_cxx}>(#{true_expression.gen_cpp(symtab, 0, indent_spaces:)}) : static_cast<#{type(symtab).to_cxx}>(#{false_expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class BuiltinTypeNameAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if @type_name == "Bits"
        result = ""
        value_result = value_try do
          bits_expression.value(symtab)
          result = "#{' '*indent}Bits<#{bits_expression.gen_cpp(symtab, 0, indent_spaces:)}>"
        end
        value_else(value_result) do
          # see if this is a param with a bound
          if bits_expression.is_a?(IdAst)
            sym = symtab.get(bits_expression.text_value)
            if !sym.nil? && sym.param?
              param = symtab.cfg_arch.param(bits_expression.text_value)
              result = "#{' '*indent}Bits<#{param.schema.max_val}>" if param.schema.max_val_known?
            end
          end
          result = "#{' '*indent}Bits<BitsInfinitePrecision>" if result == ""
        end
        result
      elsif @type_name == "XReg"
        "#{' '*indent}Bits<#{symtab.cfg_arch.possible_xlens.max}>"
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
      symtab.get(init.lhs.text_value).value = nil

      stmts.each do |s|
        lines << s.gen_cpp(symtab, indent_spaces, indent_spaces:)
      end
      cpp = <<~LOOP
        for (#{init.gen_cpp(symtab, 0, indent_spaces:)}; #{condition.gen_cpp(symtab, 0, indent_spaces:)}; #{update.gen_cpp(symtab, 0, indent_spaces:)}) {
          #{lines.join("\n  ")}
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
      if var.type(symtab).integral?
        if index.constexpr?(symtab)
          "#{' '*indent}extract<#{index.gen_cpp(symtab, 0)}, 1, #{var.type(symtab).width}>(#{var.gen_cpp(symtab, 0, indent_spaces:)})"
        else
          "#{' '*indent}extract( #{var.gen_cpp(symtab, 0, indent_spaces:)}, #{index.gen_cpp(symtab, 0)}, 1)"
        end
      else
        if var.text_value.start_with?("X")
          #"#{' '*indent}#{var.gen_cpp(symtab, 0, indent_spaces:)}[#{index.gen_cpp(symtab, 0, indent_spaces:)}]"
          "#{' '*indent} __UDB_HART->_xreg(#{index.gen_cpp(symtab, 0, indent_spaces:)})"
        else
          "#{' '*indent}#{var.gen_cpp(symtab, 0, indent_spaces:)}[#{index.gen_cpp(symtab, 0, indent_spaces:)}]"
        end
      end
    end
  end

  class BinaryExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if op == ">>>"
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.sra(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
      else
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)} #{op} #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
      end
    end
  end

  class VariableAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class PcAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}__UDB_SET_PC(#{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class AryElementAssignmentAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if lhs.text_value.start_with?("X")
        #"#{' '*indent}  #{lhs.gen_cpp(symtab, 0, indent_spaces:)}[#{idx.gen_cpp(symtab, 0, indent_spaces:)}] = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
        "#{' '*indent}__UDB_HART->_set_xreg( #{idx.gen_cpp(symtab, 0, indent_spaces:)}, #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
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
          "#{' ' * indent}return #{return_value_nodes[0].gen_cpp(symtab, 0, indent_spaces:)};"
        else
          return_types = return_value_nodes.map { |rv| rv.type(symtab).to_cxx }
          return_values = return_value_nodes.map { |rv| rv.gen_cpp(symtab, 0, indent_spaces:) }
          "#{' ' * indent}return std::tuple<#{return_types.join(', ')}>{#{return_values.join(', ')}};"
        end
      "#{' ' * indent}#{expression}"
    end
  end

  class ReplicationExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      result = ""
      value_result = value_try do
        result = "#{' '*indent}replicate<#{n.value(symtab)}>(#{v.gen_cpp(symtab, 0, indent_spaces:)})"
      end
      value_else(value_result) do
        result = "#{' '*indent}replicate(#{v.gen_cpp(symtab, 0, indent_spaces:)}, #{n.gen_cpp(symtab, 0, indent_spaces:)})"
      end
      result
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

  class ArrayLiteralAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "{#{element_nodes.map { |e| e.gen_cpp(symtab, 0) }.join(', ')}}"
    end
  end

  class FunctionCallExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if name == "ary_includes?"
        # special case
        args_cpp = arg_nodes.map { |a| a.gen_cpp(symtab, 0, indent_spaces:) }
        "(std::find(#{args_cpp[0]}.begin(), #{args_cpp[0]}.end(), #{args_cpp[1]}) != #{args_cpp[0]}.end())"
      else
        targs_cpp = template_arg_nodes.map { |t| t.gen_cpp(symtab, 0, indent_spaces:) }
        args_cpp = arg_nodes.map { |a| a.gen_cpp(symtab, 0, indent_spaces:) }
        ftype = func_type(symtab)
        if ftype.func_def_ast.constexpr?(symtab)
          if targs_cpp.empty?
            "__UDB_CONSTEXPR_FUNC_CALL #{name.gsub("?", "_Q_")}(#{args_cpp.join(', ')})"
          else
            "__UDB_CONSTEXPR_FUNC_CALL #{name.gsub("?", "_Q_")}<#{targs_cpp.join(', ')}>(#{args_cpp.join(', ')})"
          end
        else
          if targs_cpp.empty?
            "__UDB_FUNC_CALL #{name.gsub("?", "_Q_")}(#{args_cpp.join(', ')})"
          else
            "__UDB_FUNC_CALL #{name.gsub("?", "_Q_")}<#{targs_cpp.join(', ')}>(#{args_cpp.join(', ')})"
          end
        end
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
        "#{' '*indent}__UDB_CSR_BY_ADDR(#{@idx.gen_cpp(symtab, 0, indent_spaces:)}).#{@field_name}().hw_read()"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{@idx}).#{@field_name}()._hw_read()"
      end
    end
  end

  class CsrReadExpressionAst
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      csr = csr_def(symtab)
      if csr.nil?
        # csr isn't known at runtime...
        "#{' '*indent}__UDB_CSR_BY_ADDR(#{idx.gen_cpp(symtab, 0, indent_spaces:)}).hw_read()"
      else
        if symtab.cfg_arch.multi_xlen? && csr.format_changes_with_xlen?
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.name})._hw_read(__UDB_XLEN)"
        else
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.name})._hw_read()"
        end
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
