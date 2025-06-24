
# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "constexpr_pass"
require_relative "control_flow_pass"
require_relative "written_pass"
require_relative "type"

class TrueClass
  extend T::Sig
  sig { returns(String) }
  def to_cxx = "true"
end

class FalseClass
  extend T::Sig

  sig { returns(String) }
  def to_cxx = "false"
end

class Integer
  extend T::Sig

  sig { returns(String) }
  def to_cxx
    if negative?
      "-#{-self}_sb"
    else
      "#{self}_b"
    end
  end
end

class String
  extend T::Sig

  sig { returns(String) }
  def to_cxx
    "\"#{self}\"sv";
  end
end


module Idl
  class AstNode
    sig { abstract.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2); end
  end

  class NoopAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2) = ";"
  end

  class AryRangeAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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

  class ConditionalReturnStatementAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = <<~CPP
        if (#{condition.gen_cpp(symtab, 0, indent_spaces:)}) {
        #{return_expression.gen_cpp(symtab, indent_spaces, indent_spaces:)};
        }
      CPP
      "#{' ' * indent}#{cpp.gsub("\n", "\n#{' ' * indent}")}"
    end
  end

  class ReturnExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      return_expressions = return_value_nodes.map { |ast| ast.gen_cpp(symtab) }
      if return_expressions.size == 1
        "#{' ' * indent}return #{return_expressions[0]}"
      elsif return_expressions.size > 1
        "#{' ' * indent}return std::make_tuple<#{return_types(symtab).map(&:to_cxx_no_qualifiers).join(', ')}>(#{return_expressions.join(', ')})"
      else
        "#{' ' * indent}return"
      end
    end
  end

  class IfBodyAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = []
      children.each do |child|
        cpp << child.gen_cpp(symtab, indent = 2, indent_spaces:)
      end
      cpp.join("\n")
    end
  end

  class PostIncrementExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_cpp(symtab, indent = 2, indent_spaces:)}++"
    end
  end

  class PostDecrementExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{rval.gen_cpp(symtab, indent = 2, indent_spaces:)}--"
    end
  end

  class StringLiteralAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      # text_value will include leading and trailing quotes
      "#{' ' * indent}#{text_value}sv"
    end
  end

  class DontCareReturnAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}{}"
    end
  end

  class UserTypeNameAst < AstNode
    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c(symtab)
      type = symtab.get(text_value)
      if type.kind == :struct
        "struct #{text_value}"
      else
        text_value
      end
    end
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      type = symtab.get(text_value)
      if type.kind == :struct
        "#{' ' * indent}__UDB_STRUCT(#{text_value})"
      else
        "#{' ' * indent}#{text_value}"
      end
    end
  end

  class MultiVariableAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      lhs = "std::tie(#{variables.map { |v| v.gen_cpp(symtab, 0, indent_spaces: )}.join(', ')})"
      rhs = function_call.gen_cpp(symtab, 0, indent_spaces:)
      "#{' ' * indent}#{lhs} = #{rhs}"
    end
  end

  class CsrFunctionCallAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      args_cpp = args.map { |a| a.gen_cpp(symtab, 0, indent_spaces:) }

      csr_obj = csr.csr_def(symtab)
      if csr_obj.nil?
        if function_name == "sw_read"
          "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr.idx_expr.gen_cpp(symtab, 0, indent_spaces:)}).#{function_name}(__UDB_XLEN)"
        else
          "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr.idx_expr.gen_cpp(symtab, 0, indent_spaces:)}).#{function_name.gsub('?', '_Q_')}(#{args_cpp.join(', ')})"
        end
      else
        if function_name == "sw_read"
          if symtab.multi_xlen? && csr_def(symtab).format_changes_with_xlen?
            "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_obj.name})._#{function_name}(__UDB_XLEN)"
          else
            "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_obj.name})._#{function_name}()"
          end
        else
          "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_obj.name}).#{function_name.gsub('?', '_Q_')}(#{args_cpp.join(', ')})"
        end
      end
    end
  end

  class FunctionDefAst < AstNode
    sig { params(symtab: SymbolTable).returns(String) }
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

    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c_return_type(symtab)
      if @return_type_nodes.empty?
        "void"
      elsif @return_type_nodes.size == 1
        @return_type_nodes[0].gen_c(symtab)
      else
        raise "Can't have multiple return types for C #{name}"
      end
    end

    sig { params(symtab: SymbolTable).returns(String) }
    def gen_cpp_argument_list(symtab)
      symtab.push(self)
      apply_template_and_arg_syms(symtab)

      list = @argument_nodes.map do |arg|
        written = (builtin? || generated?) || body.written?(symtab, arg.name)
        "#{written ? '' : 'const'} #{T.cast(arg, VariableDeclarationAst).gen_cpp_maybe_ref(symtab, 0, ref: !written)}"
      end.join(", ")

      symtab.pop

      list
    end

    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c_argument_list(symtab)
      symtab.push(self)
      apply_template_and_arg_syms(symtab)

      list = @argument_nodes.map do |arg|
        arg.gen_c(symtab)
      end.join(", ")

      symtab.pop

      list
    end

    sig { params(symtab: SymbolTable).returns(String) }
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

    sig {
      params(
        symtab: SymbolTable,
        indent: Integer,
        indent_spaces: Integer,
        qualifiers: String,
        include_semi: T::Boolean,
        cpp_class: T.nilable(String)
      ).returns(String)
    }
    def gen_cpp_prototype(symtab, indent = 2, indent_spaces: 2, qualifiers: "", include_semi: true, cpp_class: nil)
      scope = cpp_class.nil? ? "" : "#{cpp_class}::"
      <<~PROTOTYPE
        #{' ' * indent}#{gen_cpp_template(symtab)}
        #{' ' * indent}#{name =~ /^raise.*/ ? '[[noreturn]] ' : ''} #{qualifiers} #{gen_return_type(symtab)} #{scope}#{name.gsub('?', '_Q_')}(#{gen_cpp_argument_list(symtab)})#{include_semi ? ';' : ''}
      PROTOTYPE
    end
  end

  class CsrSoftwareWriteAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      # csr isn't known at runtime for sw_write...
      csr_obj = csr.csr_def(symtab)
      if csr_obj.nil?
        "#{' '*indent}__UDB_CSR_BY_ADDR(#{csr.idx_expr.gen_cpp(symtab, 0, indent_spaces:)}).sw_write(#{expression.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_obj.name}).sw_write(#{expression.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
      end
    end
  end

  class FieldAccessExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}#{obj.gen_cpp(symtab, 0, indent_spaces: )}.#{@field_name}"
    end
  end

  class FieldAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{id.gen_cpp(symtab, 0, indent_spaces:)}.#{@field_name} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class ConcatenationExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}concat(#{expressions.map { |e| e.gen_cpp(symtab, 0, indent_spaces: )}.join(', ')})"
    end
  end

  class BitsCastAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      t = expr.type(symtab)
      width =
        if t.kind == :enum_ref
          t.enum_class.width
        else
          t.width
        end

      if width == :unknown
        # is the value also unknown?
        if t.known?
          "#{' '*indent}RuntimeBits<BitsInfinitePrecision>(#{expr.gen_cpp(symtab, 0, indent_spaces: )})"
        else
          "#{' '*indent}PossiblyUnknownRuntimeBits<BitsInfinitePrecision>(#{expr.gen_cpp(symtab, 0, indent_spaces: )})"
        end
      else
        raise "nil" if width.nil?
        # do we know if this value has anything unknown??
        if t.known?
          "#{' '*indent}Bits<#{width}>(#{expr.gen_cpp(symtab, 0, indent_spaces: )})"
        else
          "#{' '*indent}PossiblyUnknownBits<#{width}>(#{expr.gen_cpp(symtab, 0, indent_spaces: )})"
        end
      end
    end
  end

  class EnumCastAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}#{enum_name.gen_cpp(symtab, 0, indent_spaces:)}{#{expression.gen_cpp(symtab, 0, indent_spaces: )}}"
    end
  end

  class CsrFieldAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)

      field  = csr_field.field_def(symtab)
      if symtab.multi_xlen? && field.dynamic_location?
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_field.csr_name}).#{field.name}()._hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)}, __UDB_XLEN)"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_field.csr_name}).#{field.name}()._hw_write(#{write_value.gen_cpp(symtab, 0, indent_spaces:)})"
      end
    end
  end

  class EnumRefAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}#{class_name}::#{member_name}"
    end
  end

  class EnumSizeAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}#{value(symtab)}"
    end
  end

  class EnumElementSizeAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}#{value(symtab)}"
    end
  end

  class EnumArrayCastAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 2, indent_spaces: 2)
      "#{' '*indent}std::array<Bits<#{enum_class.type(symtab).width}>, #{enum_class.type(symtab).element_names.size}> {#{enum_class.type(symtab).element_values.map(&:to_s).join(', ')}}"
    end
  end

  class ParenExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class IntLiteralAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      v = value(symtab)
      w = width(symtab)
      t = type(symtab)

      if w == :unknown
        if t.known?
          "#{' ' * indent}_RuntimeBits<#{symtab.cfg_arch.possible_xlens.max}, #{t.signed?}>{#{v}_b, __UDB_XLEN}"
        else
          "#{' ' * indent}_PossiblyUnknownRuntimeBits<#{symtab.cfg_arch.possible_xlens.max}, #{t.signed?}>{\"#{v}\"_xb, __UDB_XLEN}"
        end
      else
        if t.known?
          if t.signed?
            "#{' ' * indent}#{v}_sb"
          else
            "#{' ' * indent}#{v}_b"
          end
        else
          if t.signed?
            "#{' ' * indent}\"#{v}\"_xsb"
          else
            "#{' ' * indent}\"#{v}\"_xb"
          end
        end
      end
    end
  end

  class IdAst < AstNode
    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c(symtab)
      text_value
    end
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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

  class SignCastAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)}).make_signed()"
    end
  end

  class AryRangeAccessAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      value_result = value_try do
        return "#{' '*indent}extract<#{lsb.value(symtab)}, #{msb.value(symtab) - lsb.value(symtab) + 1}>(#{var.gen_cpp(symtab, 0, indent_spaces:)})"
      end
      value_else(value_result) do
        # we don't know the value of something (probably a param), so we need the slow extract
        return "#{' '*indent}extract(#{var.gen_cpp(symtab, 0, indent_spaces:)}, #{lsb.gen_cpp(symtab, 0, indent_spaces:)}, #{msb.gen_cpp(symtab, 0, indent_spaces:)} - #{lsb.gen_cpp(symtab, 0, indent_spaces:)} + 1_b)"
      end
    end
  end

  class VariableDeclarationAst < AstNode
    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c(symtab)
      add_symbol(symtab)
      if ary_size.nil?
        "#{type_name.gen_c(symtab)} #{id.gen_c(symtab)}"
      else
        raise "TODO"
        cpp = nil
        value_result = value_try do
          cpp = "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab)},#{ary_size.value(symtab)}>#{ref ? '&' : ''} #{id.gen_cpp(symtab)}"
        end
        value_else(value_result) do
          cpp = "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab)}, #{ary_size.gen_cpp(symtab)}>#{ref ? '&' : ''} #{id.gen_cpp(symtab)}"
        end
        cpp
      end
    end

    sig { params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer, ref: T::Boolean).returns(String) }
    def gen_cpp_maybe_ref(symtab, indent = 0, indent_spaces: 2, ref: false)
      add_symbol(symtab)
      if ary_size.nil?
        "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)}#{ref ? '&' : ''} #{id.gen_cpp(symtab, 0, indent_spaces:)}"
      else
        cpp = nil
        value_result = value_try do
          cpp = "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab)},#{ary_size.value(symtab)}>#{ref ? '&' : ''} #{id.gen_cpp(symtab)}"
        end
        value_else(value_result) do
          cpp = "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab)}, #{ary_size.gen_cpp(symtab)}>#{ref ? '&' : ''} #{id.gen_cpp(symtab)}"
        end
        cpp
      end
    end

    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      gen_cpp_maybe_ref(symtab, indent, indent_spaces:, ref: false)
    end
  end

  class MultiVariableDeclarationAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      add_symbol(symtab)
      "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{var_name_nodes.map { |var| var.gen_cpp(symtab, 0, indent_spaces:) }.join(', ')}"
    end
  end

  class TernaryOperatorExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}(#{condition.gen_cpp(symtab, 0, indent_spaces:)}) ? static_cast<#{type(symtab).to_cxx}>(#{true_expression.gen_cpp(symtab, 0, indent_spaces:)}) : static_cast<#{type(symtab).to_cxx}>(#{false_expression.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class BuiltinTypeNameAst < AstNode
    sig { params(symtab: SymbolTable).returns(String) }
    def gen_c(symtab)
      if @type_name == "Bits"
        result = ""
        value_result = value_try do
          val = bits_expression.value(symtab)
          result = val <= 64 ? "uint64_t" : "unsigned __int128"
        end
        value_else(value_result) do
          # do we know the max?
          max_val = bits_expression.max_value(symtab)
          if max_val.nil?
            result = "unsigned __int128"
          elsif max_val <= 64
            result = "uint64_t"
          else
            result = "unsigned __int128"
          end
        end
        result
      elsif @type_name == "XReg"
        "uint64_t"
      elsif @type_name == "Boolean"
        "uint8_t"
      elsif @type_name == "U32"
        "uint32_t"
      elsif @type_name == "U64"
        "uint64_t"
      elsif @type_name == "String"
        "const char*"
      else
        raise "TODO: #{@type_name}"
      end
    end

    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if @type_name == "Bits"
        result = ""
        value_result = value_try do
          v = bits_expression.value(symtab)
          # know the value, so this is safely a Bits type
          result = "#{' '*indent}Bits<#{v}>"
        end
        value_else(value_result) do
          if bits_expression.constexpr?(symtab)
            result = "#{' '*indent}PossiblyUnknownBits<#{bits_expression.gen_cpp(symtab)}.get()>"
          elsif bits_expression.max_value(symtab).nil?
            result = "#{' '*indent}PossiblyUnknownBits<BitsInfinitePrecision>"
          else
            max = bits_expression.max_value(symtab)
            max = "BitsInfinitePrecision" if max == :unknown
            result = "#{' '*indent}_PossiblyUnknownRuntimeBits<#{max}, false>"
          end
        end
        result
      elsif @type_name == "XReg"
        "#{' '*indent}PossiblyUnknownBits<#{symtab.possible_xlens.max}>"
      elsif @type_name == "Boolean"
        "#{' '*indent}bool"
      elsif @type_name == "U32"
        "#{' '*indent}PossiblyUnknownBits<32>"
      elsif @type_name == "U64"
        "#{' '*indent}PossiblyUnknownBits<64>"
      elsif @type_name == "String"
        "#{' '*indent}std::string"
      else
        raise "TODO: #{@type_name}"
      end
    end
  end

  class ForLoopAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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

  class BuiltinVariableAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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

  class VariableDeclarationWithInitializationAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      add_symbol(symtab)
      if ary_size.nil?
        t = lhs_type(symtab)
        if t.kind == :bits && t.width == :unknown
          "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{lhs.gen_cpp(symtab, 0, indent_spaces:)}(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}, #{type_name.bits_expression.gen_cpp(symtab)})"
        else
          "#{' ' * indent}#{type_name.gen_cpp(symtab, 0, indent_spaces:)} #{lhs.gen_cpp(symtab, 0, indent_spaces:)}(#{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
        end
      else
        "#{' ' * indent}std::array<#{type_name.gen_cpp(symtab, 0, indent_spaces:)}, #{ary_size.gen_cpp(symtab, 0, indent_spaces:)}> #{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      end
    end
  end

  class AryElementAccessAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if var.type(symtab).integral?
        if index.constexpr?(symtab) && var.type(symtab).width != :unknown
          "#{' '*indent}extract<(#{index.gen_cpp(symtab, 0)}).get(), 1, #{var.type(symtab).width}>(#{var.gen_cpp(symtab, 0, indent_spaces:)})"
        else
          "#{' '*indent}extract( #{var.gen_cpp(symtab, 0, indent_spaces:)}, #{index.gen_cpp(symtab, 0)}, 1_b)"
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

  class BinaryExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if op == ">>>"
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.sra(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
      elsif op == "`<<"
        if rhs.constexpr?(symtab)
          # use template form of shift
          "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.template sll<#{rhs.value(symtab)}>())"
        else
          # use widening shift
          "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.widening_sll(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
        end
      elsif op == "`+"
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.widening_add(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
      elsif op == "`-"
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.widening_sub(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
      elsif op == "`*"
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.widening_mul(#{rhs.gen_cpp(symtab, 0, indent_spaces:)}))"
      else
        "#{' '*indent}(#{lhs.gen_cpp(symtab, 0, indent_spaces:)} #{op} #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
      end
    end
  end

  class VariableAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)} = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
    end
  end

  class PcAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}__UDB_SET_PC(#{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class AryElementAssignmentAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if lhs.text_value.start_with?("X")
        #"#{' '*indent}  #{lhs.gen_cpp(symtab, 0, indent_spaces:)}[#{idx.gen_cpp(symtab, 0, indent_spaces:)}] = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
        "#{' '*indent}__UDB_HART->_set_xreg( #{idx.gen_cpp(symtab, 0, indent_spaces:)}, #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
      elsif lhs.type(symtab).kind == :bits
        "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)}.setBit(#{idx.gen_cpp(symtab, 0, indent_spaces:)}, #{rhs.gen_cpp(symtab, 0, indent_spaces:)})"
      else
        # actually an array
        "#{' '*indent}#{lhs.gen_cpp(symtab, 0, indent_spaces:)}[#{idx.gen_cpp(symtab, 0, indent_spaces:)}] = #{rhs.gen_cpp(symtab, 0, indent_spaces:)}"
      end
    end
  end

  class StatementAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' ' * indent}#{action.gen_cpp(symtab, 0, indent_spaces:)};"
    end
  end

  class UnaryOperatorExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}#{op}(#{exp.gen_cpp(symtab, 0, indent_spaces:)})"
    end
  end

  class ReturnStatementAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      expression =
        if return_value_nodes.empty?
          "return;"
        elsif return_value_nodes.size == 1
          "#{' ' * indent}return #{return_value_nodes[0].gen_cpp(symtab, 0, indent_spaces:)};"
        else
          func_def = find_ancestor(FunctionDefAst)
          internal_error "Can't find function of return" if func_def.nil?
          return_values = return_value_nodes.map { |rv| rv.gen_cpp(symtab, 0, indent_spaces:) }
          "#{' ' * indent}return std::tuple<#{func_def.return_type_nodes.map { |rt| rt.gen_cpp(symtab)}.join(', ')}>{#{return_values.join(', ')}};"
        end
      "#{' ' * indent}#{expression}"
    end
  end

  class ReplicationExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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

  class ConditionalStatementAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      cpp = <<~IF
        if (#{condition.gen_cpp(symtab, 0, indent_spaces:)}) {
        #{action.gen_cpp(symtab, indent_spaces, indent_spaces:)};
        }
      IF
      cpp.lines.map { |l| "#{' ' * indent}#{l}" }.join("")
    end
  end

  class ArrayLiteralAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "{#{element_nodes.map { |e| e.gen_cpp(symtab, 0) }.join(', ')}}"
    end
  end

  class FunctionCallExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      if name == "ary_includes?"
        # special case
        if arg_nodes[0].type(symtab).width == :unknown
          # vector
          "__UDB_FUNC_CALL ary_includes_Q_(#{arg_nodes[0].gen_cpp(symtab, 0)}, #{arg_nodes[1].gen_cpp(symtab, 0)})"
        else
          # array
          "__UDB_CONSTEXPR_FUNC_CALL template ary_includes_Q_<#{arg_nodes[0].type(symtab).width}>(#{arg_nodes[0].gen_cpp(symtab, 0)}, #{arg_nodes[1].gen_cpp(symtab, 0)})"
        end
      elsif name == "implemented?"
        "__UDB_FUNC_CALL template _implemented_Q_<#{arg_nodes[0].gen_cpp(symtab, 0)}>()"
      elsif name == "implemented_version?"
        "__UDB_FUNC_CALL template _implemented_version_Q_<#{arg_nodes[0].gen_cpp(symtab, 0)}, #{arg_nodes[1].text_value}>()"
      else
        targs_cpp = template_arg_nodes.map { |t| t.gen_cpp(symtab, 0, indent_spaces:) }
        args_cpp = arg_nodes.map { |a| a.gen_cpp(symtab, 0, indent_spaces:) }
        ftype = func_type(symtab)
        if ftype.func_def_ast.constexpr?(symtab)
          if targs_cpp.empty?
            "__UDB_CONSTEXPR_FUNC_CALL #{name.gsub("?", "_Q_")}(#{args_cpp.join(', ')})"
          else
            "__UDB_CONSTEXPR_FUNC_CALL template #{name.gsub("?", "_Q_")}<#{targs_cpp.join(', ')}>(#{args_cpp.join(', ')})"
          end
        else
          if targs_cpp.empty?
            "__UDB_FUNC_CALL #{name.gsub("?", "_Q_")}(#{args_cpp.join(', ')})"
          else
            "__UDB_FUNC_CALL template #{name.gsub("?", "_Q_")}<#{targs_cpp.join(', ')}>(#{args_cpp.join(', ')})"
          end
        end
      end
    end
  end

  class ArraySizeAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}(#{expression.gen_cpp(symtab, 0, indent_spaces:)}).size()"
    end
  end

  class FunctionBodyAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      statements.map{ |s| "#{' ' * indent}#{s.gen_cpp(symtab, 0, indent_spaces:)}" }.join("\n")
    end
  end

  class CsrFieldReadExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      "#{' '*indent}__UDB_CSR_BY_NAME(#{csr_def(symtab).name}).#{@field_name}()._hw_read()"
    end
  end

  class CsrReadExpressionAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
    def gen_cpp(symtab, indent = 0, indent_spaces: 2)
      csr = csr_def(symtab)
      if symtab.multi_xlen? && csr.format_changes_with_xlen?
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.name})._hw_read(__UDB_XLEN)"
      else
        "#{' '*indent}__UDB_CSR_BY_NAME(#{csr.name})._hw_read()"
      end
    end
  end

  class IfAst < AstNode
    sig { override.params(symtab: SymbolTable, indent: Integer, indent_spaces: Integer).returns(String) }
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
