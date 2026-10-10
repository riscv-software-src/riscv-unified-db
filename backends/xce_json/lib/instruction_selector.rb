# frozen_string_literal: true

require "set"
require_relative "errors"

module XceJson
  SkippedInstruction = Data.define(:instruction, :reason)
  SelectionResult = Data.define(:groups, :skipped)

  module InstructionSelector
    # @param cfg_arch [Udb::ConfiguredArchitecture]
    # @param extension_filter [Array<String>, nil]
    # @param instruction_filter [Array<String>, nil]
    # @return [SelectionResult]
    def self.select(cfg_arch, xlen:, extension_filter: nil, instruction_filter: nil)
      candidates = cfg_arch.possible_instructions.select do |instruction|
        instruction.defined_in_base?(xlen)
      end
      validate_extensions!(candidates, extension_filter) if extension_filter

      result = Hash.new { |hash, key| hash[key] = [] }
      skipped = []
      seen = Set.new
      requested = instruction_filter&.to_set

      candidates.each do |instruction|
        next if requested && !requested.include?(instruction.name)

        names = extension_names(instruction).uniq.sort
        next if extension_filter && (names & extension_filter).empty?

        begin
          owner_extension = determine_owner(instruction, names)
        rescue UnsupportedInstructionError => e
          raise if requested&.include?(instruction.name)

          skipped << SkippedInstruction.new(e.instruction, e.reason)
          next
        end

        next if owner_extension.nil?
        next if seen.include?(instruction.name)

        seen.add(instruction.name)
        result[owner_extension] << instruction
      end

      missing = requested&.difference(seen)
      unless missing.nil? || missing.empty?
        raise InstructionNotFoundError,
              "Instruction(s) not found for the selected config/extensions: #{missing.to_a.sort.join(', ')}"
      end

      SelectionResult.new(result, skipped)
    end

    def self.validate_extensions!(candidates, extension_filter)
      available = candidates.flat_map { |instruction| extension_names(instruction) }.to_set
      extension_filter.each do |extension_name|
        unless available.include?(extension_name)
          raise ExtensionNotFoundError, "Extension '#{extension_name}' is not available in the selected config"
        end
      end
    end

    def self.determine_owner(instruction, names)
      return nil if names.empty?
      if names.size > 1
        raise UnsupportedInstructionError.new(
          instruction.name,
          "extension ownership cannot be determined from: #{names.join(', ')}"
        )
      end

      names.first
    end

    def self.extension_names(instruction)
      instruction.defined_by_condition
                 .ext_req_terms(expand: false)
                 .map { |term| term.extension.name }
    end

    private_class_method :validate_extensions!, :determine_owner, :extension_names
  end
end
