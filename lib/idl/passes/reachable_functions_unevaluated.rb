# frozen_string_literal: true

# finds all reachable functions from a give sequence of statements

module Idl
  class AstNode
    # @param design [Design] The design
    # @return [Array<FunctionBodyAst>] List of all functions that can be reached (via function calls) from this node, without considering value evaluation
    def reachable_functions_unevaluated(design)
      children.reduce([]) do |list, e|
        list.concat e.reachable_functions_unevaluated(design)
      end.uniq(&:name)
    end
  end

  class FunctionCallExpressionAst
    def reachable_functions_unevaluated(design)
      fns = []
      if template?
        template_arg_nodes.each do |t|
          fns.concat(t.reachable_functions_unevaluated(design))
        end
      end

      arg_nodes.each do |a|
        fns.concat(a.reachable_functions_unevaluated(design))
      end

      func_def_ast = design.function(name)
      raise "No function '#{name}' found in Architecture def" if func_def_ast.nil?

      fns += func_def_ast.reachable_functions_unevaluated(design)
      fns.uniq(&:name)
    end
  end

  class FunctionDefAst
    def reachable_functions_unevaluated(design)
      fns = [self]

      unless builtin?
        body.stmts.each do |stmt|
          fns += stmt.reachable_functions_unevaluated(design)
        end
      end

      fns.uniq
    end
  end
end
