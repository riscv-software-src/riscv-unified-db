# frozen_string_literal: true

require_relative "../ast"

def create_int_literal(value)
  str = value <= 512 ? value.to_s : "0x#{value.to_s(16)}"
  Idl::IntLiteralAst.new(str, 0...str.size)
end

def create_bool_literal(value)
  if value
    Idl::IdAst.new("true", 0..4)
  else
    Idl::IdAst.new("false", 0..5)
  end
end

def create_literal(value)
  if value.is_a?(Integer)
    create_int_literal(value)
  elsif value.is_a?(TrueClass) || value.is_a?(FalseClass)
    create_bool_literal(value)
  else
    raise "TODO: #{value.class.name}"
  end
end

module Idl
  # set up a default
  class AstNode
    def prune(symtab)
      new_children = children.map { |child| child.prune(symtab) }

      new_node = dup
      new_node.instance_variable_set(:@children, new_children)

      if is_a?(Executable)
        value_result = value_try do
          execute(symtab)
        end
        value_else(value_result) do
          execute_unknown(symtab)
        end
      end
      add_symbol(symtab) if is_a?(Declaration)

      new_node
    end
  end
  class FunctionCallExpressionAst
    def prune(symtab)
      value_result = value_try do
        v = value(symtab)
        return create_literal(v)
      end
      value_else(value_result) do
        FunctionCallExpressionAst.new(input, interval, name, targs.map { |t| t.prune(symtab) }, args.map { |a| a.prune(symtab)} )
      end
    end
  end
  class VariableDeclarationWithInitializationAst
    def prune(symtab)
      VariableDeclarationWithInitializationAst.new(
        input, interval,
        type_name.dup,
        lhs.dup,
        ary_size&.prune(symtab),
        rhs.prune(symtab)
      )
    end
  end
  class ForLoopAst
    def prune(symtab)
      symtab.push(self)
      symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))
      begin
        new_loop =
          ForLoopAst.new(
            input, interval,
            init.prune(symtab),
            condition.prune(symtab),
            update.prune(symtab),
            stmts.map { |s| s.prune(symtab) }
          )
      ensure
        symtab.pop
      end
      new_loop
    end
  end
  class FunctionBodyAst
    def prune(symtab, args_already_applied: false)
      symtab.push(self)

      begin
        func_def = find_ancestor(FunctionDefAst)
        unless args_already_applied || func_def.nil?
          if func_def.templated? # can't prune a template because we don't have all types
            return dup
          end

          # push template values
          func_def.template_names.each_with_index do |tname, idx|
            symtab.add(tname, Var.new(tname, func_def.template_types(symtab)[idx]))
          end

          # push args
          func_def.arguments(symtab).each do |arg_type, arg_name|
            symtab.add(arg_name, Var.new(arg_name, arg_type))
          end
        end

        pruned_body = nil

        value_result = value_try do
          # go through the statements, and stop if we find one that retuns or raises an exception
          statements.each_with_index do |s, idx|
            if s.is_a?(ReturnStatementAst)
              pruned_body = FunctionBodyAst.new(input, interval, statements[0..idx].map { |s| s.prune(symtab) })
              return pruned_body
            elsif s.is_a?(ConditionalReturnStatementAst)
              value_try do
                v = s.return_value(symtab)

                # conditional return, condition not taken if v.nil?
                unless v.nil?
                  pruned_body = FunctionBodyAst.new(input, interval, statements[0..idx].map { |s| s.prune(symtab) })
                  return pruned_body
                end
              end
              # || conditional return, condition not known; keep going
            elsif s.is_a?(StatementAst) && s.action.is_a?(FunctionCallExpressionAst) && s.action.name == "raise"
              pruned_body = FunctionBodyAst.new(input, interval, statements[0..idx].map { |s| s.prune(symtab) })
              return pruned_body
            else
              s.execute(symtab)
            end
          end

          pruned_body = FunctionBodyAst.new(input, interval, statements.map { |s| s.prune(symtab) })
        end
        value_else(value_result) do
          pruned_body = FunctionBodyAst.new(input, interval, statements.map { |s| s.prune(symtab) })
        end
      ensure
        symtab.pop
      end

      pruned_body
    end
  end
  class StatementAst
    def prune(symtab)
      pruned_action = action.prune(symtab)
      pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
      value_try do
        pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
      end
      # || ok

      StatementAst.new(input, interval, pruned_action)
    end
  end
  class BinaryExpressionAst
    # @!macro prune
    def prune(symtab)
      value_try do
        val = value(symtab)
        return create_literal(val)
      end
      # fall through

      lhs_value = nil
      rhs_value = nil

      value_try do
        lhs_value = lhs.value(symtab)
      end

      value_try do
        rhs_value = rhs.value(symtab)
      end

      if op == "&&"
        if lhs_value == false
          rhs.prune(symtab)
        else
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      elsif op == "||"
        if lhs_value == true
          rhs.prune(symtab)
        else
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      elsif op == "&"
        if lhs_value == 0
          # 0 & anything == 0
          create_literal(0)
        elsif (rhs.type(symtab).width != :unknown) && lhs_value == ((1 << rhs.type(symtab).width) - 1)
          # rhs idenntity
          rhs.prune(symtab)
        elsif rhs_value == 0
          # anything & 0 == 0
          create_literal(0)
        elsif (lhs.type(symtab).width != :unknown) && rhs_value == (1 << lhs.type(symtab).width - 1)
          # lhs identity
          lhs.prune(symtab)
        else
          # neither lhs nor rhs were prunable
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      elsif op == "|"
        if lhs_value == 0
          # rhs idenntity
          rhs.prune(symtab)
        elsif lhs_value == ((1 << rhs.type(symtab).width) - 1)
          # ~0 | anything == ~0
          create_literal(lhs_value)
        elsif rhs_value == 0
          # lhs identity
          lhs.prune(symtab)
        elsif rhs_value == (1 << lhs.type(symtab).width - 1)
          # anything | ~0 == ~0
          create_literal(rhs_value)
        else
          # neither lhs nor rhs were prunable
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      else
        BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
      end
    end
  end

  class IfBodyAst
    def prune(symtab)
      pruned_stmts = []
      stmts.each do |s|
        pruned_stmts << s.prune(symtab)

        break if pruned_stmts.last.is_a?(StatementAst) && pruned_stmts.last.action.is_a?(FunctionCallExpressionAst) && pruned_stmts.last.action.name == "raise"
      end
      IfBodyAst.new(input, interval, pruned_stmts)
    end
  end

  class ElseIfAst
    def prune(symtab)
      ElseIfAst.new(
        input, interval,
        body.interval,
        cond.prune(symtab),
        body.prune(symtab).stmts
      )
    end
  end

  class IfAst
    # @!macro prune
    def prune(symtab)
      value_result = value_try do
        if if_cond.value(symtab)
          return if_body.prune(symtab)
        elsif !elseifs.empty?
          # we know that the if condition is false, so now we treat the else if
          # as the starting point and try again
          return IfAst.new(
            input, interval,
            elseifs[0].cond.dup,
            elseifs[0].body.dup,
            elseifs[1..].map(&:dup),
            final_else_body.dup).prune(symtab)
        elsif !final_else_body.stmts.empty?
          # the if is false, and there are no else ifs, so the result of the prune is just the pruned else body
          return final_else_body.prune(symtab)
        else
          # the if is false, and there are no else ifs or elses. This is just a no-op
          return NoopAst.new
        end
      end
      value_else(value_result) do
        # we don't know the value of the if condition
        # we still might know the value of an else if
        unknown_elsifs = []
        elseifs.each do |eif|
          value_result = value_try do
            if eif.cond.value(symtab)
              # this elseif is true, so turn it into an else and then we are done
              return IfAst.new(
                input, interval,
                if_cond.dup,
                if_body.dup,
                unknown_elsifs.map(&:dup),
                eif.body.dup
              ).prune(symtab)
            else
              # this elseif is false, so we can remove it
              next :ok
            end
          end
          value_else(value_result) do
            unknown_elsifs << eif
          end
        end
        # we get here, then we don't know the value of anything. just return this if with everything pruned
        IfAst.new(
          input, interval,
          if_cond.prune(symtab),
          if_body.prune(symtab),
          unknown_elsifs.map { |eif| eif.prune(symtab) },
          final_else_body.prune(symtab)
        )
      end
    end
  end

  class ConditionalReturnStatementAst
    def prune(symtab)
      value_result = value_try do
        if condition.value(symtab)
          return return_expression.prune(symtab)
        else
          return NoopAst.new
        end
      end
      value_else(value_result) do
        ConditionalReturnStatementAst.new(input, interval, return_expression.prune(symtab), condition.prune(symtab))
      end
    end
  end

  class ConditionalStatementAst
    def prune(symtab)
      value_result = value_try do
        if condition.value(symtab)
          pruned_action = action.prune(symtab)
          pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
          value_result = value_try do
            pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
          end

          return StatementAst.new(input, interval, pruned_action)
        else
          return NoopAst.new
        end
      end
      value_else(value_result) do
        # condition not known
        pruned_action = action.prune(symtab)
        pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
        value_result = value_try do
          pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
        end
          # ok
        ConditionalStatementAst.new(input, interval, pruned_action, condition.prune(symtab))
      end
    end
  end

  class TernaryOperatorExpressionAst
    def prune(symtab)
      value_result = value_try do
        if condition.value(symtab)
          return true_expression.prune(symtab)
        else
          return false_expression.prune(symtab)
        end
      end
      value_else(value_result) do
        TernaryOperatorExpressionAst.new(
          input, interval,
          condition.prune(symtab),
          true_expression.prune(symtab),
          false_expression.prune(symtab)
        )
      end
    end
  end
end
