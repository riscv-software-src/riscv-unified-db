# frozen_string_literal: true

# finds all reachable functions from a give sequence of statements

module Idl
  class AstNode
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node
    def reachable_functions(symtab, cache = {})
      children.reduce([]) do |list, e|
        fns = e.reachable_functions(symtab, cache)
        list.concat fns
      end.uniq(&:name)
    end
  end

  class FunctionCallExpressionAst
    def reachable_functions(symtab, cache = {})
      func_def_type = func_type(symtab)

      tvals = template_values(symtab)

      body_symtab = func_def_type.apply_template_values(tvals, self)

      fns = []

      begin
        if template?
          template_arg_nodes.each do |t|
            fns.concat(t.reachable_functions(symtab, cache))
          end
        end

        arg_nodes.each do |a|
          fns.concat(a.reachable_functions(symtab, cache))
        end

        unless func_def_type.builtin? || func_def_type.generated?
          avals = func_def_type.apply_arguments(body_symtab, arg_nodes, symtab, self)

          idx = [name, tvals, avals].hash

          unless cache.key?(idx)
            fns.concat(func_def_type.body.reachable_functions(body_symtab, cache))
            cache[idx] = true
          end
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
    def reachable_functions(symtab, cache = {})
      fns = action.reachable_functions(symtab, cache)

      action.add_symbol(symtab) if action.is_a?(Declaration)
      value_try do
        action.execute(symtab) if action.is_a?(Executable)
      end
        # ok

      fns
    end
  end


  class IfAst
    def reachable_functions(symtab, cache = {})
      fns = []
      value_try do
        fns.concat if_cond.reachable_functions(symtab, cache)
        value_result = value_try do
          if (if_cond.value(symtab))
            fns.concat if_body.reachable_functions(symtab, cache)
            return fns # no need to continue
          else
            if (if_cond.text_value == "pending_and_enabled_interrupts != 0")
              warn symtab.get("pending_and_enabled_interrupts")
              raise "???"
            end
            elseifs.each do |eif|
              fns.concat eif.cond.reachable_functions(symtab, cache)
              value_result = value_try do
                if (eif.cond.value(symtab))
                  fns.concat eif.body.reachable_functions(symtab, cache)
                  return fns # no need to keep going
                end
              end
              value_else(value_result) do
                # condition isn't known; body is potentially reachable
                fns.concat eif.body.reachable_functions(symtab, cache)
              end
            end
            fns.concat final_else_body.reachable_functions(symtab, cache)
          end
        end
        value_else(value_result) do
          fns.concat if_body.reachable_functions(symtab, cache)

          elseifs.each do |eif|
            fns.concat eif.cond.reachable_functions(symtab, cache)
            value_result = value_try do
              if (eif.cond.value(symtab))
                fns.concat eif.body.reachable_functions(symtab, cache)
                return fns # no need to keep going
              end
            end
            value_else(value_result) do
              # condition isn't known; body is potentially reachable
              fns.concat eif.body.reachable_functions(symtab, cache)
            end
          end
          fns.concat final_else_body.reachable_functions(symtab, cache)
        end
      end
      return fns
    end
  end

  class ConditionalReturnStatementAst
    def reachable_functions(symtab, cache)
      fns = condition.is_a?(FunctionCallExpressionAst) ? condition.reachable_functions(symtab, cache) : []
      value_result = value_try do
        cv = condition.value(symtab)
        if cv
          fns.concat return_expression.reachable_functions(symtab, cache)
        end
      end
      value_else(value_result) do
        fns.concat return_expression.reachable_functions(symtab, cache)
      end

      fns
    end
  end

  class ConditionalStatementAst
    def reachable_functions(symtab, cache = {})

      fns = condition.is_a?(FunctionCallExpressionAst) ? condition.reachable_functions(symtab, cache) : []

      value_result = value_try do
        if condition.value(symtab)
          fns.concat action.reachable_functions(symtab, cache)
          # no need to execute action (return)
        end
      end
      value_else(value_result) do
        # condition not known
        fns = fns.concat action.reachable_functions(symtab, cache)
      end

      fns
    end
  end

  class ForLoopAst
    def reachable_functions(symtab, cache = {})
      symtab.push(self)
      begin
        symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))
        fns = init.is_a?(FunctionCallExpressionAst) ? init.reachable_functions(symtab, cache) : []
        fns.concat(condition.reachable_functions(symtab, cache))
        fns.concat(update.reachable_functions(symtab, cache))
        stmts.each do |stmt|
          fns.concat(stmt.reachable_functions(symtab, cache))
        end
      ensure
        symtab.pop
      end
      fns
    end
  end
end
