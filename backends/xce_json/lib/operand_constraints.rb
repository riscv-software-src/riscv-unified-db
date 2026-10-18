# frozen_string_literal: true

require "set"
require "idlc/passes/find_src_registers"
require_relative "../../cpp_hart_gen/lib/gen_cpp"
require_relative "errors"

module XceJson
  module OperandConstraints
    def self.derive(instruction, base)
      return {} unless instruction.operation_ast

      pruned_ast = instruction.pruned_operation_ast(base)
      symtab = instruction.fill_symtab(base, pruned_ast)
      source_registers = pruned_ast.find_src_registers(symtab)
      destination_registers = pruned_ast.find_dst_registers(symtab)
      variable_names = instruction.decode_variables(base).map(&:name).to_set
      constraints = {}

      source_registers.each do |_register_file, index|
        name = explicit_operand(variable_names, index)
        constraints[name] ||= "" if name
      end

      destination_registers.each do |_register_file, index|
        name = explicit_operand(variable_names, index)
        next unless name

        constraints[name] = constraints[name] == "" ? "+" : "="
      end

      constraints
    rescue Idl::ComplexRegDetermination
      raise UnsupportedInstructionError.new(instruction.name, "operand register access cannot be determined")
    ensure
      symtab&.release
    end

    def self.explicit_operand(variable_names, index)
      name = index.to_s.delete_suffix("()")
      variable_names.include?(name) ? name : nil
    end

    private_class_method :explicit_operand
  end
end
