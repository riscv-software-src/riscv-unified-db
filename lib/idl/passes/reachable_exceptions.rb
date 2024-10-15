# frozen_string_literal: true

require_relative "prune"

# finds all reachable exceptions from a give sequence of statements

module Idl
  class AstNode
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node
    def reachable_exceptions(symtab)
      return 0 if @children.empty?

      mask = 0
      @children.size.times do |i|
        mask |= @children[i].reachable_exceptions(symtab)
      end
      mask
    end
  end

  class FunctionCallExpressionAst
    def reachable_exceptions(symtab)
      if name == "raise"
        # first argument is the exception
        code_ast = arg_nodes[0]
        value_result = value_try do
          code = code_ast.value(symtab)
          internal_error "Code should be an integer" unless code.is_a?(Integer)
          return 1 << code
        end
        value_else(value_result) do
          value_error "Cannot determine value of exception code"
        end
      end

      # return @reachable_exceptions_func_call_cache[symtab] unless @reachable_exceptions_func_call_cache[symtab].nil?

      func_def_type = func_type(symtab)

      mask = 0
      if template?
        template_arg_nodes.each do |t|
          mask |= t.reachable_exceptions(symtab) if t.is_a?(FunctionCallExpressionAst)
        end
      end

      arg_nodes.each do |a|
        mask |= a.reachable_exceptions(symtab) if a.is_a?(FunctionCallExpressionAst)
      end

      unless func_def_type.builtin?
        body_symtab = func_def_type.apply_template_values(template_values(symtab), self)
        func_def_type.apply_arguments(body_symtab, arg_nodes, symtab, self)

        begin
          mask |= func_def_type.body.reachable_exceptions(body_symtab)
        ensure
          body_symtab.pop
          body_symtab.release
        end
      end

      # @reachable_exceptions_func_call_cache[symtab] = mask
      mask
    end
  end

  class StatementAst
    def reachable_exceptions(symtab)
      mask =
        # if action.is_a?(FunctionCallExpressionAst)
          action.reachable_exceptions(symtab)
        # else
          # 0
        # end
      action.add_symbol(symtab) if action.is_a?(Declaration)
      if action.is_a?(Executable)
        value_try do
          action.execute(symtab)
        end
      end
        # ok
      mask
    end
  end

  class IfAst
    def reachable_exceptions(symtab)
      mask = 0
      value_try do
        mask = if_cond.reachable_exceptions(symtab) if if_cond.is_a?(FunctionCallExpressionAst)
        value_result = value_try do
          if (if_cond.value(symtab))
            mask |= if_body.reachable_exceptions(symtab)
            return mask # no need to continue
          else
            elseifs.each do |eif|
              mask |= eif.cond.reachable_exceptions(symtab) if eif.cond.is_a?(FunctionCallExpressionAst)
              value_result = value_try do
                if (eif.cond.value(symtab))
                  mask |= eif.body.reachable_exceptions(symtab)
                  return mask # no need to keep going
                end
              end
              value_else(value_result) do
                # condition isn't known; body is potentially reachable
                mask |= eif.body.reachable_exceptions(symtab)
              end
            end
            mask |= final_else_body.reachable_exceptions(symtab)
          end
        end
        value_else(value_result) do
          mask |= if_body.reachable_exceptions(symtab)

          elseifs.each do |eif|
            mask |= eif.cond.reachable_exceptions(symtab) if eif.cond.is_a?(FunctionCallExpressionAst)
            value_result = value_try do
              if (eif.cond.value(symtab))
                mask |= eif.body.reachable_exceptions(symtab)
                return mask # no need to keep going
              end
            end
            value_else(value_result) do
              # condition isn't known; body is potentially reachable
              mask |= eif.body.reachable_exceptions(symtab)
            end
          end
          mask |= final_else_body.reachable_exceptions(symtab)
        end
      end
      return mask
    end
  end

  class ConditionalReturnStatementAst
    def reachable_exceptions(symtab)
      mask = condition.is_a?(FunctionCallExpressionAst) ? condition.reachable_exceptions(symtab) : 0
      value_result = value_try do
        if condition.value(symtab)
          mask |= return_expression.is_a?(FunctionCallExpressionAst) ? return_expression.reachable_exceptions(symtab) : 0
            # ok
        end
      end
      value_else(value_result) do
        mask |= return_expression.is_a?(FunctionCallExpressionAst) ? return_expression.reachable_exceptions(symtab) : 0
      end
      mask
    end
  end

  class ConditionalStatementAst
    def reachable_exceptions(symtab)
      mask = 0
      value_result = value_try do
        mask |= condition.reachable_exceptions(symtab)
        if condition.value(symtab)
          mask |= action.reachable_exceptions(symtab)
          action.add_symbol(symtab) if action.is_a?(Declaration)
          if action.is_a?(Executable)
            value_result = value_try do
              action.execute(symtab)
            end
          end
        end
      end
      value_else(value_result) do
        mask = 0
        # condition not known
        mask |= condition.reachable_exceptions(symtab)
        mask |= action.reachable_exceptions(symtab)
        action.add_symbol(symtab) if action.is_a?(Declaration)
        if action.is_a?(Executable)
          value_result = value_try do
            action.execute(symtab)
          end
        end
      end
      mask
    end
  end

  class ForLoopAst
    def reachable_exceptions(symtab)
      symtab.push(self)
      begin
        symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))
        mask = init.is_a?(FunctionCallExpressionAst) ? init.reachable_exceptions(symtab) : 0
        mask |= condition.reachable_exceptions(symtab) if condition.is_a?(FunctionCallExpressionAst)
        mask |= update.reachable_exceptions(symtab) if update.is_a?(FunctionCallExpressionAst)
        stmts.each do |stmt|
          mask |= stmt.reachable_exceptions(symtab)
        end
      ensure
        symtab.pop
      end
      mask
    end
  end
end
