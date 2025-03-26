# frozen_string_literal: true

# pass to see if node sets the PC
# does _NOT_ count exceptions

module Idl
  class AstNode
    def control_flow?(symtab)
      if children.empty?
        false
      else
        children.any? { |child| child.control_flow?(symtab) }
      end
    end
  end

  class PcAssignmentAst
    def control_flow?(symtab) = true
  end

  class FunctionCallExpressionAst
    def control_flow?(symtab)
      return true if children.any? { |child| child.control_flow?(symtab) }

      return false if name =~ /^raise.*$/ # we don't count exceptions

      func_def_type = func_type(symtab)

      return false if func_def_type.builtin? || func_def_type.generated?

      func_def_type.body.control_flow?(symtab)
    end
  end
end
