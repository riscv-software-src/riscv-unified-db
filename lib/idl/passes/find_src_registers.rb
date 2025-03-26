module Idl
  class ComplexRegDetermination < RuntimeError
  end

  class AstNode
    def find_src_registers(symtab)
      # if is_a?(Executable)
      #   value_result = value_try do
      #     execute(symtab)
      #   end
      #   value_else(value_result) do
      #     execute_unknown(symtab)
      #   end
      # end
      add_symbol(symtab) if is_a?(Declaration)

      srcs = []
      @children.each do |child|
        srcs.concat(child.find_src_registers(symtab))
      end
      srcs.uniq
    end

    def find_dst_registers(symtab)
      # if is_a?(Executable)
      #   value_result = value_try do
      #     execute(symtab)
      #   end
      #   value_else(value_result) do
      #     execute_unknown(symtab)
      #   end
      # end
      add_symbol(symtab) if is_a?(Declaration)

      srcs = []
      @children.each do |child|
        srcs.concat(child.find_dst_registers(symtab))
      end
      srcs.uniq
    end
  end

  class ForLoopAst
    # we don't unroll, but we don't add the index variable to the symtab, either
    # that will cause any register accesses dependent on the index variable to raise Complex
    def find_src_registers(symtab)
      srcs = init.find_src_registers(symtab)
      # don't add init to the symtab, since we don't want to use it...
      srcs += condition.find_src_registers(symtab)

      stmts.each do |stmt|
        srcs += stmt.find_src_registers(symtab)
      end
      srcs += update.find_src_registers(symtab)

      srcs
    end

    # we don't unroll, but we don't add the index variable to the symtab, either
    # that will cause any register accesses dependent on the index variable to raise Complex
    def find_dst_registers(symtab)
      dsts = init.find_dst_registers(symtab)
      # don't add init to the symtab, since we don't want to use it...
      dsts += condition.find_dst_registers(symtab)

      stmts.each do |stmt|
        dsts += stmt.find_dst_registers(symtab)
      end
      dsts += update.find_dst_registers(symtab)

      dsts
    end
  end

  class AryElementAccessAst
    def find_src_registers(symtab)
      value_result = value_try do
        if var.text_value == "X"
          return [index.value(symtab)]
        else
          return []
        end
      end
      value_else(value_result) do
        if var.text_value == "X"
          if index.type(symtab).const?
            return [index.gen_cpp(symtab, 0)]
          else
            raise ComplexRegDetermination
          end
        else
          return []
        end
      end
    end
  end

  class AryElementAssignmentAst
    def find_dst_registers(symtab)
      value_result = value_try do
        if lhs.text_value == "X"
          return [idx.value(symtab)]
        else
          return []
        end
      end
      value_else(value_result) do
        if lhs.text_value == "X"
          if idx.type(symtab).const?
            return [idx.gen_cpp(symtab, 0)]
          else
            raise ComplexRegDetermination
          end
        else
          return []
        end
      end
    end
  end
end
