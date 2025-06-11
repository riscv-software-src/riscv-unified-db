# frozen_string_literal: true

module Idl
  class AstNode
    def written?(symtab, varname, in_assignment: false)
      add_symbol(symtab) if is_a?(Declaration)

      if children.empty?
        false
      else
        children.any? { |child| child.written?(symtab, varname, in_assignment:) }
      end
    end
  end
  class IdAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      in_assignment && (text_value == varname)
    end
  end
  class VariableAssignmentAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      lhs.written?(symtab, varname, in_assignment: true) || \
        rhs.written?(symtab, varname, in_assignment:)
    end
  end
  class AryElementAssignmentAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      lhs.written?(symtab, varname, in_assignment: true) || \
        idx.written?(symtab, varname, in_assignment:) || \
        rhs.written?(symtab, varname, in_assignment:)
    end
  end
  class AryRangeAssignmentAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      variable.written?(symtab, varname, in_assignment: true) || \
        msb.written?(symtab, varname, in_assignment:) || \
        lsb.written?(symtab, varname, in_assignment:) || \
        write_value.written?(symtab, varname, in_assignment:)
    end
  end
  class FieldAssignmentAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      id.written?(symtab, varname, in_assignment: true) || \
        rhs.written?(symtab, varname, in_assignment:)
    end
  end
  class MultiVariableAssignmentAst < AstNode
    def written?(symtab, varname, in_assignment: false)
      variables.any? { |variable| variable.written?(symtab, varname, in_assignment: true) } || \
        function_call.written?(symtab, varname, in_assignment:)
    end
  end
end
