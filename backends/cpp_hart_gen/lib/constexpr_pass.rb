# frozen_string_literal: true

module Idl
  class AstNode
    def constexpr?(symtab)
      if children.empty?
        true
      else
        children.all? { |child| child.constexpr?(symtab) }
      end
    end
  end
  class IdAst
    def constexpr?(symtab)
      sym = symtab.get(name)
      return true if sym.nil?
      return true if sym.is_a?(Type)
      return false if sym.value.nil? # assuming undefined syms are local (be sure to type check first!!)

      if sym.param?
        symtab.cfg_arch.params_with_value.any? { |p| p.name == text_value }
      elsif sym.template_value?
        true
      else
        !sym.type.global?
      end
    end
  end
  class PcAssignmentAst
    def constexpr?(symtab) = false
  end
  class FunctionCallExpressionAst
    def constexpr?(symtab) = false # conservative, can do better...
  end
  class CsrFieldReadExpressionAst
    def constexpr?(symtab) = false
  end
  class CsrReadExpressionAst
    def constexpr?(symtab) = false
  end
  class CsrSoftwareWriteAst
    def constexpr?(symtab) = false
  end
  class CsrFunctionCallAst
    def constexpr?(symtab) = function_name == "address"
  end
  class CsrWriteAst
    def constexpr?(symtab) = false
  end
  class FunctionDefAst
    # @return [Boolean] If the function is possibly C++ constexpr (does not access CSRs or registers)
    def constexpr?(symtab)
      return false if builtin?
      return false if generated? # might actually know this in some cases...

      body.constexpr?(symtab)
    end
  end
end
