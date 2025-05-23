require_relative '../../test/test_helper'
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

require_relative "#{$root}/backends/ext_pdf_doc/idl_lexer"

# test IDL variables
class TestVariables < Minitest::Test
  # include TestMixin

  def test_false
    lexer = Rouge::Lexers::Idl.new
    (lexer.lex "false").each do |token, chunk|
      puts token
      puts chunk
    end
  end

  def test_function
    lexer = Rouge::Lexers::Idl.new
    tokens = lexer.lex <<~FUNC
      if (implemented?(ExtensionName::B) && (CSR[misa].B == 1'b0)) {
        raise(ExceptionCode::IllegalInstruction, $encoding);
      }
      XReg index = shamt & (xlen() - 1);
    FUNC

    tokens.each do |token, chunk|
      puts token
      puts chunk
    end

  end
end
