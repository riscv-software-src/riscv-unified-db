# frozen_string_literal: true

module XceJson
  class Error < StandardError; end
  class ConfigurationError < Error; end
  class ExtensionNotFoundError < Error; end
  class InstructionNotFoundError < Error; end
  class InvalidEncodingError < Error; end
  class OutputError < Error; end
  class TestError < Error; end

  class NoInstructionsGeneratedError < Error
    attr_reader :skipped

    def initialize(message = "No XCE JSON instructions were generated", skipped: [])
      @skipped = skipped.freeze
      super(message)
    end
  end

  class UnsupportedInstructionError < Error
    attr_reader :instruction, :reason

    def initialize(instruction, reason)
      @instruction = instruction
      @reason = reason
      super("Instruction '#{instruction}' is unsupported: #{reason}")
    end
  end
end
