
# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module Udb
class CsrField
  TYPE_VALUE_TO_CPP_NAME = T.let(
    {
      0 => "RO",
      1 => "ROH",
      2 => "RW",
      3 => "RWR",
      4 => "RWH",
      5 => "RWRH"
    }.freeze,
    T::Hash[Integer, String]
  )

  # @return [String] C++ implementation of type() body
  sig { params(xlen: Integer).returns(String) }
  def type_to_cpp(xlen)
    raise "#{csr.name}.#{field.name} is not defined in RV#{xlen}" unless defined_in_base?(xlen)

    pruned_ast = pruned_type_ast(xlen)
    if pruned_ast.nil?
      # type is const
      udb_type = type(xlen)
      return "return CsrFieldType::#{udb_type.sub('-', '')};"
    end

    cpp = nil
    symtab = fill_symtab_for_type(xlen, pruned_ast)
    value_result = pruned_ast.value_try do
      type_value = pruned_ast.return_value(symtab)
      cpp = "return CsrFieldType::#{TYPE_VALUE_TO_CPP_NAME[type_value]};"
    end
    pruned_ast.value_else(value_result) do
      cpp = pruned_ast.gen_cpp(symtab)
    end
    symtab.release

    cpp
  end
end
end
