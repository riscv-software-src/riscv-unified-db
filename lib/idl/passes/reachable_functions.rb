# frozen_string_literal: true

# finds all reachable functions from a give sequence of statements

module Idl
  class AstNode
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node
    def reachable_functions(symtab)
      children.reduce([]) do |list, e|
        fns = e.reachable_functions(symtab)
        list.concat fns
      end.uniq(&:name)
    end
  end

  class FunctionCallExpressionAst
    def reachable_functions(symtab)
      func_def_type = func_type(symtab)

      tvals = template_values(symtab)

      body_symtab = func_def_type.apply_template_values(tvals, self)

      fns = []

      begin
        if template?
          template_arg_nodes.each do |t|
            fns.concat(t.reachable_functions(symtab)) if t.is_a?(FunctionCallExpressionAst)
          end
        end

        arg_nodes.each do |a|
          fns.concat(a.reachable_functions(symtab)) if a.is_a?(FunctionCallExpressionAst)
        end

        func_def_type.apply_arguments(body_symtab, arg_nodes, symtab, self)

        unless func_def_type.builtin?
          fns.concat(func_def_type.body.reachable_functions(body_symtab))
        end

        fns = fns.push(func_def_type.func_def_ast).uniq(&:name)
      ensure
        body_symtab.pop
        body_symtab.release
      end

      fns
    end
  end

  class StatementAst
    def reachable_functions(symtab)
      fns = action.reachable_functions(symtab)

      action.add_symbol(symtab) if action.is_a?(Declaration)
      value_try do
        action.execute(symtab) if action.is_a?(Executable)
      end
        # ok

      fns
    end
  end

  class ConditionalReturnStatementAst
    def reachable_functions(symtab)
      fns = condition.is_a?(FunctionCallExpressionAst) ? condition.reachable_functions(symtab) : []
      value_result = value_try do
        cv = condition.value(symtab)
        if cv
          fns.concat return_expression.reachable_functions(symtab) if return_expression.is_a?(FunctionCallExpressionAst)
        end
      end
      value_else(value_result) do
        fns.concat return_expression.reachable_functions(symtab) if return_expression.is_a?(FunctionCallExpressionAst)
      end

      fns
    end
  end

  class ConditionalStatementAst
    def reachable_functions(symtab)

      fns = condition.is_a?(FunctionCallExpressionAst) ? condition.reachable_functions(symtab) : []

      value_result = value_try do
        if condition.value(symtab)
          fns.concat action.reachable_functions(symtab) if action.is_a?(FunctionCallExpressionAst)
          # no need to execute action (return)
        end
      end
      value_else(value_result) do
        # condition not known
        fns = fns.concat action.reachable_functions(symtab) if action.is_a?(FunctionCallExpressionAst)
      end
      
      fns
    end
  end

  class ForLoopAst
    def reachable_functions(symtab)
      symtab.push(self)
      begin
        symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))
        fns = init.is_a?(FunctionCallExpressionAst) ? init.reachable_functions(symtab) : []
        fns.concat(condition.reachable_functions(symtab)) if condition.is_a?(FunctionCallExpressionAst)
        fns.concat(update.reachable_functions(symtab)) if update.is_a?(FunctionCallExpressionAst)
        stmts.each do |stmt|
          fns.concat(stmt.reachable_functions(symtab))
        end
      ensure
        symtab.pop
      end
      fns
    end
  end
end
