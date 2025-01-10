# frozen_string_literal: true

# A synchroncous exception code
class ExceptionCode
  # @return [String] Long-form display name (can include special characters)
  attr_reader :name

  # @return [String] Field name for an IDL enum
  attr_reader :var

  # @return [Integer] Code, written into *mcause
  attr_reader :num

  # @return [Extension] Extension that defines this code
  attr_reader :ext

  def initialize(name, var, number, ext)
    @name = name
    @name.freeze
    @var = var
    @num = number
    @ext = ext
  end
end

# Define InterruptCode class (all the same members as ExceptionCode)
InterruptCode = Class.new(ExceptionCode)
