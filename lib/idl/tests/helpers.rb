# frozen_string_literal: true

require "ostruct"

# Extension mock that returns an extension name
class MockExtension
  attr_reader :name
  def initialize(name)
    @name = name
  end
end

MockExtensionParameter = Struct.new(:name, :desc, :schema, :extra_validation, :exts, :type)

# ArchDef mock that knows about XLEN and extensions
class MockArchDef
  def param_values = { "XLEN" => 32 }
  def params = []
  def extensions = [MockExtension.new("I")]
  def mxlen = 64
  def exception_codes = [OpenStruct.new(var: "ACode", num: 0), OpenStruct.new(var: "BCode", num: 1)]
  def interrupt_codes = [OpenStruct.new(var: "CoolInterrupt", num: 1)]
end

module TestMixin
  def setup
    @archdef = MockArchDef.new
    @symtab = Idl::SymbolTable.new(@archdef, 32)
    @compiler = Idl::Compiler.new(@archdef)
  end
end