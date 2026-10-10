# frozen_string_literal: true

require "set"

require_relative "operand_constraints"
require_relative "encoding_converter"

module XceJson
  module InstructionConverter
    def self.convert(instruction, xlen)
      constraints = OperandConstraints.derive(instruction, xlen)
      attributes = derive_attributes(instruction, xlen)

      result = {
        "asm" => convert_asm(instruction, xlen),
        "encoding" => EncodingConverter.convert(instruction, xlen, constraints),
        "size" => instruction.encoding_width,
        "type" => attributes[:type]
      }
      result["arch"] = attributes[:arch] if attributes[:arch]
      result
    end

    def self.convert_asm(instruction, base)
      assembly = instruction.assembly
      return instruction.name if assembly.nil? || assembly.empty?

      variable_names = instruction.decode_variables(base).map(&:name).to_set
      operands = assembly.gsub(/\b(\w+)\b/) do |word|
        variable_names.include?(word) ? "$#{word}" : word
      end
      "#{instruction.name} #{operands}"
    end

    def self.derive_attributes(instruction, base)
      variable_names = instruction.decode_variables(base).map(&:name)
      type = if variable_names.any? { |name| name == "vm" || name.start_with?("v") }
               "vector"
             elsif variable_names.any? { |name| name.start_with?("f") }
               "float"
             else
               "integer"
             end

      attributes = { type: }
      attributes[:arch] = "rv#{instruction.base}" if instruction.base
      attributes
    end

    private_class_method :convert_asm, :derive_attributes
  end
end
