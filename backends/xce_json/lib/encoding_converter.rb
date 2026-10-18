# frozen_string_literal: true

require_relative "errors"

module XceJson
  module EncodingConverter
    def self.convert(inst, base, constraints)
      entries = extract_fixed_bits(inst.encoding_format(base))

      inst.decode_variables(base).each do |var|
        entries << convert_variable(inst, var, constraints)
      end

      entries.sort_by { |entry| entry["offset"] }
    end

    def self.extract_fixed_bits(format_str)
      entries = []
      index = format_str.length - 1

      while index >= 0
        if %w[0 1].include?(format_str[index])
          offset = format_str.length - 1 - index
          bits = format_str[index]
          while index.positive? && %w[0 1].include?(format_str[index - 1])
            index -= 1
            bits = format_str[index] + bits
          end
          entries << {
            "offset" => offset,
            "size" => bits.length,
            "type" => "bits",
            "value" => "0x#{bits.to_i(2).to_s(16).upcase}"
          }
        end
        index -= 1
      end

      entries
    end

    def self.convert_variable(inst, var, constraints)
      offset, size = location(inst, var)
      entry = {
        "offset" => offset,
        "size" => size,
        "type" => operand_type(var),
        "value" => var.name
      }
      constraint = constraints[var.name]
      entry["constraint"] = constraint if constraint && !constraint.empty?
      entry
    end

    def self.location(inst, var)
      value = var.location.to_s
      if value.include?("|")
        raise UnsupportedInstructionError.new(inst.name, "split encoding field '#{var.name}'")
      end

      bit = /\A(\d+)\z/.match(value)
      return [bit[1].to_i, 1] if bit

      range = /\A(\d+)-(\d+)\z/.match(value)
      if range
        msb = range[1].to_i
        lsb = range[2].to_i
        if msb < lsb
          raise InvalidEncodingError, "Instruction '#{inst.name}' has invalid encoding location '#{value}'"
        end
        return [lsb, msb - lsb + 1]
      end

      raise InvalidEncodingError, "Instruction '#{inst.name}' has invalid encoding location '#{value}'"
    end

    def self.operand_type(var)
      name = var.name
      return "r" if name.start_with?("x")
      return "f" if name.start_with?("f")
      return "vm" if name == "vm"
      return "vr" if name.start_with?("v")
      return "imm" if var.respond_to?(:sext?) && var.sext?

      "bits"
    end

    private_class_method :extract_fixed_bits, :convert_variable, :location, :operand_type
  end
end
