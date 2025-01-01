# frozen_string_literal: true

# Just adds the concept of base ISA (RV32I or RV64I) to the Architecture class.

require_relative "architecture"

class BaseArchitecture < Architecture
  # @return [String] Name of base ISA (rv32 or rv64)
  attr_reader :name

  # @return [Integer] 32 or 64
  attr_reader :base

  # Initialize a new base architecture definition
  #
  # @param name [#to_s] The name associated with this base architecture
  # @param base [Integer] RISC-V ISA MXLEN parameter value (can be nil if not static)
  # @param arch_dir [String,Pathname] Path to a directory with the associated architecture definition
  def initialize(name, base, arch_dir)
    super(arch_dir)
    @name = name.to_s.freeze
    @base = base
    @base.freeze
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "BaseArchitecture##{name}"
end
