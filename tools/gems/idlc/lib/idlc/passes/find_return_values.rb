# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# pass to find all the possible return values from a function body

module Idl

  class AstNode
    def pass_find_return_values(values, current_conditions)
      children.each do |c|
        c.pass_find_return_values(values, current_conditions)
      end
    end
  end

  class ReturnStatementAst < AstNode
    def pass_find_return_values(values, current_conditions, symtab)
      # if the action is a ternary operator, there is another condition to consider
      if first.is_a?(TernaryOperatorExpressionAst)
        current_conditions.push first.condition
        values << [first.true_expression, current_conditions.clone]
        current_conditions.pop
        current_conditions.push first.condition.invert(symtab)
        values << [first.false_expression, current_conditions.clone]
        current_conditions.pop
      else
        values << [self, current_conditions.clone]
      end
    end
  end

  class IfAst < AstNode
    def pass_find_return_values(values, current_conditions, symtab)
      current_conditions.push if_cond
      if_body.elements.each do |e|
        e.e.pass_find_return_values(values, current_conditions, symtab)
      end
      current_conditions.pop

      unless elseifs.empty?
        elseifs.elements.each do |eif|
          current_conditions.push eif.expression

          eif.body.elements.each do |e|
            e.e.pass_find_return_values(values, current_conditions, symtab)
          end

          current_conditions.pop
        end
      end

      unless final_else.empty?
        current_conditions.push if_cond.invert(symtab)

        final_else.body.elements.each do |e|
          e.e.pass_find_return_values(values, current_conditions, symtab)
        end
        current_conditions.pop
      end
    end
  end

  class FunctionBodyAst < AstNode
    # @return [Array<Ast, Array<Ast>>] List of possible return values, along with the condition it occurs under
    def pass_find_return_values(symtab)
      values = []
      current_conditions = []
      statements.each do |s|
        s.pass_find_return_values(values, current_conditions, symtab)
      end
      values
    end
  end
end
