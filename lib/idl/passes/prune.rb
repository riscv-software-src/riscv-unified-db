# frozen_string_literal: true

require_relative "../ast"

module Treetop
  module Runtime
    class SyntaxNode
      # @!macro [new] prune
      #   @param symtab [Idl::SymbolTable] Context of the compilation
      #   @return [AstNode] A new abstract syntax tree with all dead/unreachable code removed
      def prune(symtab)
        new_elements = elements.nil? ? [] : elements.map { |e| e.prune(symtab) }
        new_node = clone # self.class.new(input, interval, new_elements)
        new_node.elements.clear
        new_node.elements.concat(new_elements)

        # extension_modules.each do |m|
          # new_node.extend m
        # end

        if is_a?(Idl::AstNode)
          begin
            if new_node.is_a?(Idl::Declaration)
              new_node.add_symbol(symtab)
            end
            if new_node.is_a?(Idl::Executable)
              new_node.execute(symtab) # to update values
            end
          rescue Idl::AstNode::ValueError
            # new_node.type_check(symtab)
          end
        end

        new_node
      end
    end
  end
end

module Idl
  # set up a default
  class AstNode
    def prune(_symtab)
      clone
    end
  end
  class FunctionCallExpressionAst
    def prune(symtab)
      FunctionCallExpressionAst.new(input, interval, name, @targs.map { |t| t.prune(symtab) }, @args.map { |a| a.prune(symtab)} )
    end
  end
  class FunctionBodyAst
    def prune(symtab)
      symtab.push
      raise "?" if symtab.get("current_mode").nil?
      func_def = find_ancestor(FunctionDefAst)
      unless func_def.nil?
        return FunctionBodyAst.new(input, interval, statements) if func_def.templated? # can't prune a template because we don't have all types

        # push template values
        func_def.template_names.each_with_index do |tname, idx|
          symtab.add(tname, Var.new(tname, func_def.template_types(symtab)[idx]))
        end

        # push args
        func_def.arguments(symtab).each do |arg_type, arg_name|
          symtab.add(arg_name, Var.new(arg_name, arg_type))
        end
      end
      begin
        # go through the statements, and stop if we find one that retuns
        statements.each_with_index do |s, idx|
          if s.is_a?(Returns)
            v = s.return_value(symtab)
            return FunctionBodyAst.new(input, interval, statements[0..idx].map { |s| s.prune(symtab) }) unless v.nil?
          else
            s.execute(symtab)
          end
        end

        FunctionBodyAst.new(input, interval, statements.map { |s| s.prune(symtab) })
      rescue ValueError
        FunctionBodyAst.new(input, interval, statements.map { |s| s.prune(symtab) })
      ensure
        symtab.pop
      end
    end
  end
  class StatementAst
    def prune(symtab)
      pruned_action = action.prune(symtab)
      if pruned_action.is_a?(Declaration)
        pruned_action.add_symbol(symtab)
      end
      if pruned_action.is_a?(Executable)
        begin
          pruned_action.execute(symtab)
        rescue ValueError
          # ok
        end
      end
      StatementAst.new(pruned_action)
    end
  end
  class AryElementAccessAst
    def prune(symtab)
      AryElementAccessAst.new(input, interval, @var.prune(symtab), @index.prune(symtab))
    end
  end
  class AryRangeAccessAst
    def prune(symtab)
      AryRangeAccessAst.new(input, interval, @var.prune(symtab), @msb.prune(symtab), @lsb.prune(symtab))
    end
  end
  class BinaryExpressionAst
    # @!macro prune
    def prune(symtab)
      if op == "&&"
        begin
          if @lhs.value(symtab) == false
            @rhs.prune(symtab)
          else
            BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
          end
        rescue ValueError
          BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
        end
      elsif op == "||"
        begin
          if @lhs.value(symtab) == true
            @rhs.prune(symtab)
          else
            BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
          end
        rescue ValueError
          BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
        end
      else
        BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
      end
    end
  end

  class IfBodyAst
    def prune(symtab)
      pruned_stmts = []
      stmts.each do |s|
        pruned_stmts << s.prune(symtab)
      end
      IfBodyAst.new(pruned_stmts)
    end
  end

  class ElseIfAst
    def prune(symtab)
      ElseIfAst.new(cond.prune(symtab), body.prune(symtab).stmts)
    end
  end

  class IfAst
    # @!macro prune
    def prune(symtab)
      if if_cond.value(symtab)
        if_body.prune(symtab)
      elsif !elseifs.empty?
        # we know that the if condition is false, so now we treat the else if
        # as the starting point and try again
        IfAst.new(
          elseifs[0].cond.prune(symtab),
          elseifs[0].body.prune(symtab),
          elseifs[1..].map { |e| e.prune(symtab) },
          final_else_body.prune(symtab))
      elsif !final_else_body.stmts.empty?
        # the if is false, and there are no else ifs, so the result of the prune is just the pruned else body
        final_else_body.prune(symtab)
      else
        # the if is false, and there are no else ifs or elses. This is just a no-op
        NoopAst.new
      end
    rescue ValueError
      # we don't know the value of the if condition
      # we still might know the value of an else if
      unknown_elsifs = []
      elseifs.each do |eif|
        begin
          if eif.cond.value(symtab)
            # this elseif is true, so turn it into an else and then we are done
            return IfAst.new(if_cond.prune(symtab), if_body.prune(symtab), unknown_elsifs.map { |u| u.prune(symtab)}, eif.body.prune(symtab))
          else
            # this elseif is false, so we can remove it
            next
          end
        rescue ValueError
          unknown_elsifs << eif
        end
      end
      # we get here, then we don't know the value of anything. just return this if with everything pruned
      IfAst.new(if_cond.prune(symtab), if_body.prune(symtab), elseifs.map { |eif| eif.prune(symtab)}, final_else_body.prune(symtab))
    end
  end

  class ConditionalStatementAst
    def prune(symtab)
      if condition.value(symtab)
        StatementAst.new(action.prune(symtab))
      else
        NoopAst.new()
      end
    rescue ValueError
      # condition not known
      ConditionalStatementAst.new(action.prune(symtab), condition.prune(symtab))
    end
  end

  # class TernaryOperatorExpressionAst
  #   def prune(symtab)
  #     begin
  #     rescue ValueError
  #       TernaryOperatorExpressionAst.new()
  #     end
  #   end
  # end
end
