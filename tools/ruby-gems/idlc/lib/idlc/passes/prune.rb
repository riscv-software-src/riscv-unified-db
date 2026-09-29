# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

# This file contains AST functions that prune out unreachable paths given
# some known values in a symbol table
# It adds a `prune` function to every AstNode that returns a new,
# pruned subtree.

require "sorbet-runtime"

require_relative "../ast"

module Idl
  module PruneHelpers
    extend T::Sig
    def self.create_int_literal(value, forced_type: nil)
      width = forced_type ? forced_type.width : value.bit_length
      raise "pruning error: attempting to prune an integer with unknown width" unless width.is_a?(Integer)
      width = 1 if width == 0

      # negative values must keep an explicit sign marker and their native decimal
      # text; the literal grammar already parses signed negative decimals correctly,
      # while re-encoding as an unsigned magnitude (with no sign marker) silently
      # drops the sign once rendered to C++ (see IntLiteralAst#gen_cpp)
      str =
        if value.is_a?(Integer) && value.negative?
          "#{width}'sd#{value}"
        else
          v = value <= 512 ? value.to_s : "h#{value.to_s(16)}"
          "#{width}'#{v}"
        end
      Idl::IntLiteralAst.new(str, 0...str.size, str)
    end

    def self.create_bool_literal(value)
      if value
        Idl::TrueExpressionAst.new("true", 0..4)
      else
        Idl::FalseExpressionAst.new("false", 0..5)
      end
    end

    # returns nil if array holds bools
    # otherwise (it holds bits), returns max bitwidth of all elements
    sig { params(symtab: Idl::SymbolTable, node: Idl::AstNode, max: T.nilable(Integer)).returns(T.nilable(Integer)) }
    def self.find_max_element_width(symtab, node, max = nil)
      if node.is_a?(Idl::ArrayLiteralAst)
        node.entries.map do |e|
          e_max = find_max_element_width(symtab, e)
          max.nil? ? e_max : [max, e_max].max
        end.max
      else
        if node.is_a?(Idl::TrueExpressionAst) || node.is_a?(Idl::FalseExpressionAst)
          nil
        else
          node_width = node.type(symtab).width
          max.nil? ? node_width : [max, node_width].max
        end
      end
    end

    def self.coerce_ary_element_widths(symtab, elements, max_element_width)
      if elements.is_a?(Array) && elements.empty?
        Idl::ArrayLiteralAst.new("pruned_literal_ary", 0..18, [])
      elsif elements.fetch(0).is_a?(Idl::ArrayLiteralAst)
        # Recursively coerce nested arrays - pass e.entries, not e
        Idl::ArrayLiteralAst.new("pruned_literal_ary", 0..18,
          elements.map { |e| coerce_ary_element_widths(symtab, e.entries, max_element_width) })
      else
        # Base case: elements is an array of leaf nodes, coerce each to max_element_width
        coerced = elements.map { |node| create_int_literal(node.value(symtab), forced_type: Idl::Type.new(:bits, width: max_element_width)) }
        Idl::ArrayLiteralAst.new("pruned_literal_ary", 0..18, coerced)
      end
    end

    def self.create_literal(symtab, value, type, forced_type: nil)
      case type.kind
      when :enum_ref
        member_name = type.enum_class.element_names[type.enum_class.element_values.index(value)]
        str = "#{type.enum_class.name}::#{member_name}"
        Idl::EnumRefAst.new(str, 0...str.size, type.enum_class.name, member_name)
      when :bits
        create_int_literal(value, forced_type:)
      when :boolean
        create_bool_literal(value)
      when :array
        elements = value.map { |e| create_literal(symtab, e, type.sub_type) }
        # array elements MUST have the same type, so we need to coerce them
        # find the leaf level, and get the bit widths if needed
        ary = Idl::ArrayLiteralAst.new("pruned_literal_ary", 0..18, elements)
        max_element_width = find_max_element_width(symtab, ary)
        if max_element_width.nil?
          ary
        else
          coerce_ary_element_widths(symtab, elements, max_element_width)
        end
      else
        raise "TODO: #{type}"
      end
    end
  end
end

module Idl
  # set up a default
  class AstNode
    def always_terminates? = false

    # forced_type, when not nil, is the type that the pruned result must be
    # if is used when pruning expressions to ensure that the prune doesn't change
    # bit width just because a value is known and would fit in something smaller
    def prune(symtab, forced_type: nil)
      new_children = children.map { |child| child.prune(symtab, forced_type:) }

      if executable?
        value_try do
          execute(symtab)
        end
        # value_else: execute raised ValueError; symtab state is already correct
      end
      add_symbol(symtab) if declaration?

      # avoid allocation when nothing changed
      return self if !frozen? && new_children.each_with_index.all? { |c, i| c.equal?(children[i]) }

      new_node = dup
      new_node.instance_variable_set(:@children, new_children)
      new_node
    end

    def nullify_assignments(symtab)
      children.each { |child| child.nullify_assignments(symtab) }
    end
  end
  class VariableAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = VariableAssignmentAst.new(input, interval, lhs.dup, rhs.prune(symtab))
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
    def nullify_assignments(symtab)
      sym = symtab.get(lhs.text_value)
      unless sym.nil?
        sym.value = nil
      end
    end
  end
  class AryElementAssignmentAst < AstNode
    def nullify_assignments(symtab)
      case lhs.type(symtab).kind
      when :array
        value_result = value_try do
          lhs_value = lhs.value(symtab)
          value_result2 = value_try do
            lhs_value[idx.value(symtab)] = nil
          end
          value_else(value_result2) do
            # index unknown: nullify entire array
            lhs_value.map! { |_v| nil }
          end
        end
        value_else(value_result) do
          # array var itself is unknown; nothing more to do
        end
      when :bits
        root = lhs
        root = root.var while root.is_a?(AryElementAccessAst) || root.is_a?(AryRangeAccessAst)
        var = symtab.get(root.name)
        var.value = nil unless var.nil?
      end
    end
  end
  class AryRangeAssignmentAst < AstNode
    def nullify_assignments(symtab)
      return if variable.type(symtab).global?
      root = variable
      root = root.var while root.is_a?(AryElementAccessAst) || root.is_a?(AryRangeAccessAst)
      var = symtab.get(root.name)
      var.value = nil unless var.nil?
    end
  end
  class FieldAssignmentAst < AstNode
    def nullify_assignments(symtab)
      var = symtab.get(id.name)
      var.value = nil unless var.nil?
    end
  end
  class MultiVariableAssignmentAst < AstNode
    def nullify_assignments(symtab)
      variables.each do |v|
        sym = symtab.get(v.text_value)
        sym.value = nil unless sym.nil?
      end
    end
  end
  class PostIncrementExpressionAst < AstNode
    def nullify_assignments(symtab)
      var = symtab.get(rval.text_value)
      var.value = nil unless var.nil?
    end
  end
  class PostDecrementExpressionAst < AstNode
    def nullify_assignments(symtab)
      var = symtab.get(rval.text_value)
      var.value = nil unless var.nil?
    end
  end
  class FunctionCallExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).kind == :bits
          # can only prune if the bit width of the integer is known
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        elsif type(symtab).kind == :struct
          value_error <<~MSG
            Literal struct values can't be pruned since a struct can't be initialized with a single expression.
            This would require syntax like { .a = FOO, .b = BAR }
          MSG
        end
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        FunctionCallExpressionAst.new(input, interval, name, @children.map { |a| a.prune(symtab) })
      end
    end
  end
  class VariableDeclarationWithInitializationAst < AstNode
    def prune(symtab, forced_type: nil)
      add_symbol(symtab)

      # do we want to remove a constant? If so, need to add a prune for IdAst that
      # spits out a literal
      #
      # if lhs.const?
      #   value_try do
      #     rhs.value(symtab)
      #     # rhs value is known, and variable is const. it can be removed
      #     return NoopAst.new
      #   end
      # end

      VariableDeclarationWithInitializationAst.new(
        input, interval,
        type_name.dup,
        lhs.dup,
        ary_size&.prune(symtab),
        rhs.prune(symtab),
        @for_iter_var
      )
    end
  end
  class ForLoopAst < AstNode
    def prune(symtab, forced_type: nil)
      symtab.push(self)
      symtab.add(init.lhs.name, Var.new(init.lhs.name, init.lhs_type(symtab)))

      # Nullify any outer-scope variable assigned in the loop body, since we
      # don't know how many iterations ran (or if any ran at all)
      stmts.each { |stmt| stmt.nullify_assignments(symtab) }

      # Snapshot after nullification so restore brings back nil values, not pre-loop values
      snapshot = symtab.snapshot_values

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
        symtab.restore_values(snapshot)
        symtab.pop
      end
      # Nullify any outer-scope variable assigned in the loop body, since we
      # don't know how many iterations ran (or if any ran at all)
      stmts.each { |stmt| stmt.nullify_assignments(symtab) }
      new_loop
    end
  end
  class FunctionDefAst < AstNode
    def prune(symtab, forced_type: nil)
      pruned_body =
        unless builtin? || generated?
          apply_arg_syms(symtab)
          @body.prune(symtab, args_already_applied: true)
        end

      FunctionDefAst.new(
        input, interval,
        name,
        @return_type_nodes.map(&:dup),
        @argument_nodes.map(&:dup),
        @desc,
        @type,
        pruned_body
      )
    end
  end
  class ParenExpressionAst
    def prune(symtab, forced_type: nil)
      e = expression.prune(symtab, forced_type:)
      if e.is_a?(ParenExpressionAst)
        e
      elsif e.is_a?(IntLiteralAst) || e.is_a?(TrueExpressionAst) || e.is_a?(FalseExpressionAst) || e.is_a?(IdAst)
        e
      else
        ParenExpressionAst.new(input, interval, e)
      end
    end
  end
  class FunctionBodyAst < AstNode
    def prune(symtab, forced_type: nil, args_already_applied: false)
      symtab.push(self)

      begin
        func_def = find_ancestor(FunctionDefAst)
        unless args_already_applied || func_def.nil?

          # push args
          func_def.arguments(symtab).each do |arg_type, arg_name|
            symtab.add(arg_name, Var.new(arg_name, arg_type))
          end
        end

        pruned_body = nil
        prune_stmts = -> {
          [].tap do |out|
            statements.each do |s|
              out << s.prune(symtab)
              break if out.last.always_terminates?
            end
          end
        }

        value_result = value_try do
          # go through the statements, and stop if we find one that returns or raises an exception
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

          pruned_body = FunctionBodyAst.new(input, interval, prune_stmts.())
        end
        value_else(value_result) do
          pruned_body = FunctionBodyAst.new(input, interval, prune_stmts.())
        end
      ensure
        symtab.pop
      end

      pruned_body
    end
  end
  class StatementAst < AstNode
    def always_terminates?
      action.is_a?(FunctionCallExpressionAst) && action.name == "raise"
    end

    def prune(symtab, forced_type: nil)
      pruned_action = action.prune(symtab)

      new_stmt = StatementAst.new(input, interval, pruned_action)
      # pruned_action.freeze_tree(symtab) unless pruned_action.frozen?

      pruned_action.add_symbol(symtab) if pruned_action.declaration?
      # action#prune already handles symtab update (execute)

      new_stmt
    end
  end
  class BinaryExpressionAst < AstNode
    # @!macro prune
    def prune(symtab, forced_type: nil)
      value_try do
        val = value(symtab)
        if val.is_a?(Integer)
          # can only prune if the bit width of the integer is known
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        end
        return PruneHelpers.create_literal(symtab, val, type(symtab), forced_type: forced_type || type(symtab))
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
        raise "pruning error" unless forced_type.nil? || forced_type.kind == :boolean
        if !lhs_value.nil? && !rhs_value.nil?
          PruneHelpers.create_bool_literal(lhs_value && rhs_value)
        elsif lhs_value == true
          rhs.prune(symtab)
        elsif rhs_value == true
          lhs.prune(symtab)
        elsif lhs_value == false || rhs_value == false
          PruneHelpers.create_bool_literal(false)
        else
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      elsif op == "||"
        raise "pruning error" unless forced_type.nil? || forced_type.kind == :boolean
        if !lhs_value.nil? && !rhs_value.nil?
          PruneHelpers.create_bool_literal(lhs_value || rhs_value)
        elsif lhs_value == true || rhs_value == true
          PruneHelpers.create_bool_literal(true)
        elsif lhs_value == false
          rhs.prune(symtab)
        elsif rhs_value == false
          lhs.prune(symtab)
        else
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      elsif op == "&"
        if lhs_value == 0 && type(symtab).width != :unknown
          PruneHelpers.create_literal(symtab, 0, forced_type: forced_type || type(symtab))
        elsif (rhs.type(symtab).width != :unknown) && lhs_value == ((1 << rhs.type(symtab).width) - 1) && type(symtab).width != :unknown
          # rhs idenntity
          rhs.prune(symtab, forced_type:)
        elsif rhs_value == 0 && type(symtab).width != :unknown
          # anything & 0 == 0
          PruneHelpers.create_literal(symtab, 0, forced_type: forced_type || type(symtab))
        elsif (lhs.type(symtab).width != :unknown) && rhs_value == ((1 << lhs.type(symtab).width) - 1) && type(symtab).width != :unknown
          # lhs identity
          lhs.prune(symtab, forced_type:)
        else
          # neither lhs nor rhs were prunable
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab, forced_type:), @op, rhs.prune(symtab, forced_type:))
        end
      elsif op == "|"
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)

        if lhs_value == 0
          # rhs idenntity
          rhs.prune(symtab, forced_type:)
        elsif rhs_type.width != :unknown && lhs_value == ((1 << rhs.type(symtab).width) - 1) && type(symtab).width != :unknown
          # ~0 | anything == ~0
          PruneHelpers.create_literal(symtab, lhs_value, forced_type: forced_type || type(symtab))
        elsif rhs_value == 0 && type(symtab).width != :unknown
          # lhs identity
          lhs.prune(symtab, forced_type:)
        elsif lhs_type.width != :unknown && rhs_value == ((1 << lhs.type(symtab).width) - 1) && type(symtab).width != :unknown
          # anything | ~0 == ~0
          PruneHelpers.create_literal(symtab, rhs_value, forced_type: forced_type || type(symtab))
        else
          # neither lhs nor rhs were prunable
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab, forced_type:), @op, rhs.prune(symtab, forced_type:))
        end
      elsif op == "=="
        if !lhs_value.nil? && !rhs_value.nil?
          PruneHelpers.create_bool_literal(lhs_value == rhs_value)
        else
          BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
        end
      else
        BinaryExpressionAst.new(input, interval, lhs.prune(symtab), @op, rhs.prune(symtab))
      end
    end
  end

  class IfBodyAst < AstNode
    def always_terminates?
      !stmts.empty? && stmts.last.always_terminates?
    end

    def prune(symtab, restore: true, forced_type: nil)
      pruned_stmts = []
      symtab.push(nil)
      snapshot = symtab.snapshot_values if restore
      stmts.each do |s|
        pruned_stmts << s.prune(symtab)

        break if pruned_stmts.last.always_terminates?
      end
      if restore
        symtab.restore_values(snapshot)
      end
      symtab.pop
      IfBodyAst.new(input, interval, pruned_stmts)
    end
  end

  class ElseIfAst < AstNode
    def prune(symtab, forced_type: nil)
      ElseIfAst.new(
        input, interval,
        body.interval,
        cond.prune(symtab),
        body.prune(symtab).stmts
      )
    end
  end

  class IfAst < AstNode
    # @!macro prune
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        if if_cond.value(symtab)
          return if_body.prune(symtab, restore: false)
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
          return final_else_body.prune(symtab, restore: false)
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
        # After pruning, some elseif conditions may resolve to a literal (e.g., `false && <runtime_csr_read>`
        # fails value() due to the CSR read but prune() short-circuits the && to false). Filter those out.
        pruned_elsifs = unknown_elsifs.filter_map do |eif|
          pruned = eif.prune(symtab)
          next nil if pruned.cond.is_a?(FalseExpressionAst)
          pruned
        end
        result = IfAst.new(
          input, interval,
          if_cond.prune(symtab),
          if_body.prune(symtab),
          pruned_elsifs,
          final_else_body.prune(symtab)
        )
        # Nullify any variable assigned in any branch, since we don't know which ran
        if_body.nullify_assignments(symtab)
        pruned_elsifs.each { |eif| eif.body.nullify_assignments(symtab) }
        final_else_body.nullify_assignments(symtab)
        result
      end
    end
  end

  class ConditionalReturnStatementAst < AstNode
    def prune(symtab, forced_type: nil)
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

  class ConditionalStatementAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        if condition.value(symtab)
          pruned_action = action.prune(symtab)
          pruned_action.add_symbol(symtab) if pruned_action.declaration?
          value_result = value_try do
            pruned_action.execute(symtab) if pruned_action.executable?
          end

          return StatementAst.new(input, interval, pruned_action)
        else
          return NoopAst.new
        end
      end
      value_else(value_result) do
        # condition not known
        pruned_action = action.prune(symtab)
        pruned_action.add_symbol(symtab) if pruned_action.declaration?
        value_result = value_try do
          pruned_action.execute(symtab) if pruned_action.executable?
        end
        # Condition is unknown, so the assignment may not have run; nullify to prevent leakage
        pruned_action.nullify_assignments(symtab)
        ConditionalStatementAst.new(input, interval, pruned_action, condition.prune(symtab))
      end
    end
  end

  class ConcatenationExpressionAst
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        return PruneHelpers.create_int_literal(v, forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        c = ConcatenationExpressionAst.new(
          input, interval, @children.map { |c| c.prune(symtab) }
        )
        if forced_type
          if forced_type.width < type(symtab).width
            c = AryRangeAccessAst.new(
              input, interval, c, PruneHelpers.create_int_literal(forced_type.width - 1), create_int_literal(0)
            )
          elsif forced_type.width > type(symtab).width
            extra = forced_type.width - type(symtab).width
            mock_type = Struct.new(:width)
            c = ConcatenationExpressionAst.new(
              input, interval, [PruneHelpers.create_int_literal(0, forced_type: mock_type.new(extra))] + @children.map { |c| c.prune(symtab) }
            )
          end
        end
        c
      end
    end
  end

  class ReplicationExpressionAst
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        return PruneHelpers.create_int_literal(v, forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        c = ReplicationExpressionAst.new(input, interval, n.prune(symtab), v.prune(symtab))
        if forced_type
          if forced_type.width < type(symtab).width
            c = AryRangeAccessAst.new(
              input, interval, c, PruneHelpers.create_int_literal(forced_type.width - 1), create_int_literal(0)
            )
          elsif forced_type.width > type(symtab).width
            extra = forced_type.width - type(symtab).width
            mock_type = Struct.new(:width)
            c = ConcatenationExpressionAst.new(
              input, interval, [PruneHelpers.create_int_literal(0, forced_type: mock_type.new(extra))] + @children.map { |c| c.prune(symtab) }
            )
          end
        end
        c
      end
    end
  end

  class IntLiteralAst
    def prune(symtab, forced_type: nil)
      if forced_type
        raise "pruning error: attempt to force bitwidth when width is unknown" if forced_type.width.nil? || forced_type.width == :unknown
        v = value(symtab)
        # negative values need an explicit sign marker; without it, the literal
        # re-parses as unsigned and loses its sign once rendered to C++
        s = v.negative? ? "#{forced_type.width}'sd#{v}" : "#{forced_type.width}'d#{v}"
        IntLiteralAst.new(s, 0...s.size, s)
      else
        dup
      end
    end
  end

  class TernaryOperatorExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        if condition.value(symtab)
          return true_expression.prune(symtab, forced_type: forced_type || type(symtab))
        else
          return false_expression.prune(symtab, forced_type: forced_type || type(symtab))
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

  class CsrFieldAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      CsrFieldAssignmentAst.new(input, interval, csr_field.dup, write_value.prune(symtab))
    end
  end

  class CsrFieldReadExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).width == :unknown
          value_error "unknown width"
        end
        return PruneHelpers.create_int_literal(v, forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        CsrFieldReadExpressionAst.new(input, interval, @csr.dup, @field_name)
      end
    end
  end

  class CsrReadExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).width == :unknown
          value_error "unknown width"
        end
        return PruneHelpers.create_int_literal(v, forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        CsrReadExpressionAst.new(input, interval, @csr_name)
      end
    end
  end

  class BitsCastAst < AstNode
    def prune(symtab, forced_type: nil)
      p = expr.prune(symtab, forced_type:)
      if p.type(symtab).kind == :bits
        return p
      else
        return BitsCastAst.new(input, interval, p)
      end
    end
  end

  class IdAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        value_error "Not pruning struct types" if type(symtab).kind == :struct
        v = value(symtab)
        if type(symtab).kind == :bits
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        end
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        dup
      end
    end
  end

  class UnaryOperatorExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).kind == :bits
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        end
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        UnaryOperatorExpressionAst.new(input, interval, @op, exp.prune(symtab, forced_type:))
      end
    end
  end

  class AryElementAccessAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).kind == :bits
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        end
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        AryElementAccessAst.new(input, interval, var.prune(symtab), index.prune(symtab))
      end
    end
  end

  class AryRangeAccessAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).width == :unknown
          value_error "Unknown width"
        end
        return PruneHelpers.create_int_literal(v, forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        AryRangeAccessAst.new(input, interval, var.prune(symtab), msb.prune(symtab), lsb.prune(symtab))
      end
    end
  end

  class FieldAccessExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        if type(symtab).kind == :bits
          if type(symtab).width == :unknown
            value_error "Unknown width"
          end
        end
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        FieldAccessExpressionAst.new(input, interval, obj.prune(symtab), @field_name)
      end
    end
  end

  class EnumRefAst < AstNode
    def prune(symtab, forced_type: nil)
      value_result = value_try do
        v = value(symtab)
        return PruneHelpers.create_literal(symtab, v, type(symtab), forced_type: forced_type || type(symtab))
      end
      value_else(value_result) do
        dup
      end
    end
  end

  class ReturnStatementAst < AstNode
    def always_terminates? = true

    def prune(symtab, forced_type: nil)
      ReturnStatementAst.new(input, interval, return_expression.prune(symtab))
    end
  end

  class ReturnExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      ReturnExpressionAst.new(input, interval, return_value_nodes.map { |n| n.prune(symtab) })
    end
  end

  class MultiVariableAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = MultiVariableAssignmentAst.new(
        input, interval,
        variables.map(&:dup),
        function_call.prune(symtab)
      )
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class AryElementAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = AryElementAssignmentAst.new(
        input, interval,
        lhs.dup,
        idx.prune(symtab),
        rhs.prune(symtab)
      )
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class AryRangeAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = AryRangeAssignmentAst.new(
        input, interval,
        variable.dup,
        msb.prune(symtab),
        lsb.prune(symtab),
        write_value.prune(symtab)
      )
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class FieldAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = FieldAssignmentAst.new(
        input, interval,
        id.dup,
        @field_name,
        rhs.prune(symtab)
      )
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class VariableDeclarationAst < AstNode
    def prune(symtab, forced_type: nil)
      add_symbol(symtab)
      dup
    end
  end

  class MultiVariableDeclarationAst < AstNode
    def prune(symtab, forced_type: nil)
      add_symbol(symtab)
      dup
    end
  end

  class PostIncrementExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = PostIncrementExpressionAst.new(input, interval, rval.dup)
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class PostDecrementExpressionAst < AstNode
    def prune(symtab, forced_type: nil)
      new_ast = PostDecrementExpressionAst.new(input, interval, rval.dup)
      value_try do
        new_ast.execute(symtab)
      end
      # value_else: execute already sets nil on failure, nothing more to do
      new_ast
    end
  end

  class PcAssignmentAst < AstNode
    def prune(symtab, forced_type: nil)
      PcAssignmentAst.new(input, interval, rhs.prune(symtab))
    end
  end

  class CsrSoftwareWriteAst < AstNode
    def prune(symtab, forced_type: nil)
      CsrSoftwareWriteAst.new(input, interval, csr.dup, expression.prune(symtab))
    end
  end
end
