# frozen_string_literal: true

require "ostruct"

# Extension mock that returns an extension name
class Xmockension
  attr_reader :name
  def initialize(name)
    @name = name
  end
end

XmockensionParameter = Struct.new(:name, :desc, :schema, :extra_validation, :exts, :type)
XmockensionParameterWithValue = Struct.new(:name, :desc, :schema, :extra_validation, :exts, :value)

# ConfiguredArchitecture mock that knows about XLEN and extensions
class MockConfiguredArchitecture
  def param_values = { "XLEN" => 32 }
  def params_with_value = [XmockensionParameterWithValue.new("XLEN", "mxlen", {"type" => "integer", "enum" => [32, 64]}, nil, nil, 32)]
  def params_without_value = []
  def params = []
  def extensions = [Xmockension.new("I")]
  def mxlen = 64
  def exception_codes = [OpenStruct.new(var: "ACode", num: 0), OpenStruct.new(var: "BCode", num: 1)]
  def interrupt_codes = [OpenStruct.new(var: "CoolInterrupt", num: 1)]

  def fully_configured? = false
  def partially_configured? = true
  def unconfigured? = false

  def name = "mock"

  attr_accessor :global_ast
end

module TestMixin
  def setup
    @cfg_arch = MockConfiguredArchitecture.new
    @symtab = Idl::SymbolTable.new(@cfg_arch)
    @compiler = Idl::Compiler.new
  end
end
