# frozen_string_literal: true

# finds all reachable functions from a give sequence of statements

module Idl
  class AstNode
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node
    def reachable_functions(symtab)
      children.reduce([]) do |list, e|
        list.concat e.reachable_functions(symtab)
      end.uniq(&:name)
    end
  end

  class FunctionCallExpressionAst
    def reachable_functions(symtab)
      func_def_type = func_type(symtab)

      tvals = template_values(symtab)

      body_symtab = func_def_type.apply_template_values(tvals, self)

      # have we seen this exact same call already??
      key = nil
      begin
        key = [
          name,
          tvals,
          func_def_type.argument_values(body_symtab, arg_nodes, symtab, self)
        ].hash
        fns = func_def_type.func_def_ast.reachable_functions_cache[key]
        return fns unless fns.nil?
      rescue ValueError
        # fall through, we need to evaluate
      end

      fns = []
      if template?
        template_arg_nodes.each do |t|
          fns.concat(t.reachable_functions(symtab))
        end
      end

      arg_nodes.each do |a|
        fns.concat(a.reachable_functions(symtab))
      end

      func_def_type.apply_arguments(body_symtab, arg_nodes, symtab, self)

      unless func_def_type.builtin?
        prune_symtab = body_symtab #.deep_clone
        fns.concat(func_def_type.body.prune(prune_symtab, args_already_applied: true).reachable_functions(body_symtab))
      end

      fns = fns.push(func_def_type.func_def_ast).uniq(&:name)
      func_def_type.func_def_ast.reachable_functions_cache[key] = fns unless key.nil?
      fns
    end
  end

  class StatementAst
    def reachable_functions(symtab)
      fns = action.reachable_functions(symtab)
      action.add_symbol(symtab) if action.is_a?(Declaration)
      begin
        action.execute(symtab) if action.is_a?(Executable)
      rescue ValueError
        # ok
      end
      fns
    end
  end

  class ConditionalReturnStatementAst
    def reachable_functions(symtab)
      fns = condition.reachable_functions(symtab)
      if condition.value(symtab)
        fns.concat return_expression.reachable_functions(symtab)
        begin
          return_expression.execute(symtab)
        rescue ValueError
          # ok
        end
        fns
      else
        []
      end
    end
  end

  class ConditionalStatementAst
    def reachable_functions(symtab)
      fns = condition.reachable_functions(symtab)
      if condition.value(symtab)
        fns.concat action.reachable_functions(symtab)
        action.add_symbol(symtab) if action.is_a?(Declaration)
        begin
          action.execute(symtab) if action.is_a?(Executable)
        rescue ValueError
          # ok
        end
        fns
      else
        []
      end
    rescue ValueError
      # condition not known
      fns = action.reachable_functions(symtab)
      action.add_symbol(symtab) if action.is_a?(Declaration)
      begin
        action.execute(symtab) if action.is_a?(Executable)
      rescue ValueError
        # ok
      end
      fns
    end
  end

  class ForLoopAst
    def reachable_functions(symtab)
      # puts path
      # puts to_idl
      symtab.push
      symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))
      fns = init.reachable_functions(symtab)
      fns.concat(condition.reachable_functions(symtab))
      fns.concat(update.reachable_functions(symtab))
      stmts.each do |stmt|
        fns.concat(stmt.reachable_functions(symtab))
      end
      symtab.pop
      fns.uniq
    end
  end
end
