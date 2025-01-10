# frozen_string_literal: true

require "ostruct"
require_relative "../../idesign"

# Extension mock that returns an extension name
class Xmockension
  attr_reader :name
  def initialize(name)
    @name = name
  end
end

XmockensionParameter = Struct.new(:name, :desc, :schema, :extra_validation, :exts, :type)
XmockensionParameterWithValue = Struct.new(:name, :desc, :schema, :extra_validation, :exts, :value)

# Design class mock that knows about XLEN and extensions
class MockDesign < IDesign
  def initialize
    super("mock")
  end

  def mxlen = 64
  def param_values = { "XLEN" => 32 }
  def params_with_value = [XmockensionParameterWithValue.new("XLEN", "mxlen", {"type" => "integer", "enum" => [32, 64]}, nil, nil, 32)]
  def params_without_value = []
  def implemented_ext_vers = [Xmockension.new("I")]
  def implemented_exception_codes = [OpenStruct.new(var: "ACode", num: 0), OpenStruct.new(var: "BCode", num: 1)]
  def implemented_interrupt_codes = [OpenStruct.new(var: "CoolInterrupt", num: 1)]

  def fully_configured? = false
  def partially_configured? = true
  def unconfigured? = false

  attr_accessor :global_ast
end

module TestMixin
  def setup
    @design = MockDesign.new
    @symtab = Idl::SymbolTable.new(@design)
    @compiler = Idl::Compiler.new
  end
end
