# frozen_string_literal: true

# Extension mock that returns an extension name
class MockExtension
  attr_reader :name
  def initialize(name)
    @name = name
  end
end

# ArchDef mock that knows about XLEN and extensions
class MockArchDef
  def config_params = { "XLEN" => 32 }
  def extensions = [MockExtension.new("I")]
end

module TestMixin
  def setup
    @archdef = MockArchDef.new
    @symtab = Idl::SymbolTable.new(@archdef)
    @compiler = Idl::Compiler.new(@archdef)
  end
end