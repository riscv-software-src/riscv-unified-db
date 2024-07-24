# frozen_string_literal: true

require_relative "prune"

# finds all reachable functions from a give sequence of statements

module Idl
  class AstNode
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node
    def reachable_functions(symtab)
      children.reduce([]) { |list, e| list.concat e.prune(symtab).reachable_functions(symtab) }.uniq(&:name)
    end
  end

  class FunctionCallExpressionAst
    def reachable_functions(symtab)
      func_def_type = func_type(symtab)

      fns = []
      if template?
        template_arg_nodes.each do |t|
          fns.concat(t.prune(symtab).reachable_functions(symtab))
        end
      end

      arg_nodes.each do |a|
        fns.concat(a.prune(symtab).reachable_functions(symtab))
      end

      body_symtab = func_def_type.apply_template_values(template_values(symtab))
      func_def_type.apply_arguments(body_symtab, arg_nodes, symtab)

      unless func_def_type.builtin?
        fns.concat(func_def_type.body.prune(body_symtab, args_already_applied: true).reachable_functions(body_symtab))
      end

      fns.push(func_def_type.func_def_ast).uniq(&:name)
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

  class ConditionalStatementAst
    def reachable_functions(symtab)
      if condition.value(symtab)
        fns = action.reachable_functions(symtab)
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
      symtab.push
      symtab.add(@init.lhs.name, Var.new(@init.lhs.name, @init.lhs_type(symtab)))
      fns = @init.reachable_functions(symtab)
      fns.concat(@condition.reachable_functions(symtab))
      fns.concat(@update.reachable_functions(symtab))
      @stmts.each do |stmt|
        fns.concat(stmt.reachable_functions(symtab))
      end
      symtab.pop
      fns.uniq
    end
  end
end
