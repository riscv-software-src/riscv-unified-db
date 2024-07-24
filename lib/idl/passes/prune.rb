# frozen_string_literal: true

require_relative "../ast"

module Idl
  # set up a default
  class AstNode
    def prune(symtab)
      new_children = children.map { |child| child.prune(symtab) }

      new_node = dup
      new_node.instance_variable_set(:@children, new_children)
      new_node
    end
  end
  class FunctionCallExpressionAst
    def prune(symtab)
      FunctionCallExpressionAst.new(input, interval, name, @targs.map { |t| t.prune(symtab) }, @args.map { |a| a.prune(symtab)} )
    end
  end
  class VariableDeclarationWithInitializationAst
    def prune(symtab)
      VariableDeclarationWithInitializationAst.new(
        input, interval,
        @type_name.dup,
        @lhs.dup,
        @ary_size&.prune(symtab),
        @rhs.prune(symtab)
      )
    end
  end
  class ForLoopAst
    def prune(symtab)
      symtab.push
      symtab.add(@init.lhs.name, Var.new(@init.lhs.name, @init.lhs_type(symtab)))
      new_loop =
        ForLoopAst.new(
          input, interval,
          @init.prune(symtab),
          @condition.prune(symtab),
          @update.prune(symtab),
          @stmts.map { |s| s.prune(symtab) }
        )
      symtab.pop
      new_loop
    end
  end
  class FunctionBodyAst
    def prune(symtab, args_already_applied: false)
      symtab.push

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
      pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
      begin
        pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
      rescue ValueError
        # ok
      end

      StatementAst.new(input, interval, pruned_action)
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
      begin
        val = value(symtab)
        if val
          if type(symtab).kind == :boolean
            if val == false
              IdAst.new(input, interval, "false")
            else
              IdAst.new(input, interval, "true")
            end
          else
            val_str = val.to_s
            IntLiteralAst.new(val_str, 0...val_str.length)
          end
        end
      rescue ValueError
        # fall through
      end

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
      elsif op == "&"
        begin
          lhs_value = @lhs.value(symtab)
          if lhs_value.zero?
            # 0 & anything == 0
            IntLiteralAst.new("0", 0..0)
          elsif lhs_value == ((1 << @rhs.type(symtab).width) - 1)
            # rhs idenntity
            @rhs.prune(symtab)
          else
            begin
              rhs_value = @rhs.value(symtab)
              if rhs_value.zero?
                # anything & 0 == 0
                IntLiteralAst.new("0", 0..0)
              elsif rhs_value == (1 << @lhs.type(symtab).width - 1)
                # lhs identity
                @lhs.prune(symtab)
              else
                # neither lhs nor rhs were prunable
                BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
              end
            rescue ValueError
              # lhs wasn't prunable and don't know rhs
              BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
            end
          end
        rescue ValueError
          # don't know lhs
          begin
            rhs_value = @rhs.value(symtab)
            if rhs_value == 0
              # anything & 0 == 0
              IntLiteralAst.new("0", 0..0)
            elsif rhs_value == (1 << @lhs.type(symtab).width - 1)
              # lhs identity
              @lhs.prune(symtab)
            else
              # don't know lhs and rhs wasn't prunable
              BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
            end
          rescue ValueError
            # don't know either lhs or rhs
            BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
          end
        end
      elsif op == "|"
        begin
          lhs_value = @lhs.value(symtab)
          if lhs_value.zero?
            # rhs idenntity
            @rhs.prune(symtab)
          elsif lhs_value == ((1 << @rhs.type(symtab).width) - 1)
            # ~0 | anything == ~0
            lhs_val_str = lhs_value.to_s
            IntLiteralAst.new(lhs_val_str, 0...lhs_val_str.size)
          else
            begin
              rhs_value = @rhs.value(symtab)
              if rhs_value.zero?
                # lhs identity
                @lhs.prune(symtab)
              elsif rhs_value == (1 << @lhs.type(symtab).width - 1)
                # anything | ~0 == ~0
                rhs_val_str = rhs_value.to_s
                IntLiteralAst.new(rhs_val_str, 0...rhs_val_str.size)
              else
                # neither lhs nor rhs were prunable
                BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
              end
            rescue ValueError
              # lhs wasn't prunable and don't know rhs
              BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
            end
          end
        rescue ValueError
          # don't know lhs
          begin
            rhs_value = @rhs.value(symtab)
            if rhs_value.zero?
              # lhs identity
              @lhs.prune(symtab)
            elsif rhs_value == (1 << @lhs.type(symtab).width - 1)
              # anything | ~0 == ~0
              rhs_val_str = rhs_value.to_s
              IntLiteralAst.new(rhs_val_str, 0...rhs_val_str.size)
            else
              # don't know lhs and rhs wasn't prunable
              BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
            end
          rescue ValueError
            # don't know either lhs or rhs
            BinaryExpressionAst.new(input, interval, @lhs.prune(symtab), @op, @rhs.prune(symtab))
          end
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
      if if_cond.value(symtab)
        if_body.prune(symtab)
      elsif !elseifs.empty?
        # we know that the if condition is false, so now we treat the else if
        # as the starting point and try again
        IfAst.new(
          input, interval,
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
            return IfAst.new(
              input, interval,
              if_cond.prune(symtab),
              if_body.prune(symtab),
              unknown_elsifs.map { |u| u.prune(symtab) },
              eif.body.prune(symtab)
            )
          else
            # this elseif is false, so we can remove it
            next
          end
        rescue ValueError
          unknown_elsifs << eif
        end
      end
      # we get here, then we don't know the value of anything. just return this if with everything pruned
      IfAst.new(
        input, interval,
        if_cond.prune(symtab),
        if_body.prune(symtab),
        elseifs.map { |eif| eif.prune(symtab) },
        final_else_body.prune(symtab)
      )
    end
  end

  class ConditionalStatementAst
    def prune(symtab)
      if condition.value(symtab)
        pruned_action = action.prune(symtab)
        pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
        begin
          pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
        rescue ValueError
          # ok
        end
        StatementAst.new(input, interval, pruned_action)
      else
        NoopAst.new()
      end
    rescue ValueError
      # condition not known
      pruned_action = action.prune(symtab)
      pruned_action.add_symbol(symtab) if pruned_action.is_a?(Declaration)
      begin
        pruned_action.execute(symtab) if pruned_action.is_a?(Executable)
      rescue ValueError
        # ok
      end
      ConditionalStatementAst.new(input, interval, pruned_action, condition.prune(symtab))
    end
  end

  class TernaryOperatorExpressionAst
    def prune(symtab)
      begin
        if condition.value(symtab)
          true_expression.prune(symtab)
        else
          false_expression.prune(symtab)
        end
      rescue ValueError
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
