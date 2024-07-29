require "rouge"

module Rouge
  module Lexers
    class Idl < RegexLexer
      tag "idl"
      filenames "idl", "isa"
      
      title "IDL"
      desc "ISA Description Language"

      ws = /[ \n]+/
      id = /[a-zA-Z_][a-zA-Z0-9_]*/

      def self.keywords
        @keywords ||= Set.new %w[
          if else for return returns arguments description body function builtin enum bitfield
        ]
      end

      def self.keywords_type
        @keywords_type ||= Set.new %w[
          Bits XReg U32 U64 String Boolean
        ]
      end

      # start { push :bol }

      state :bol do
        rule(//) { pop! }
      end

      state :root do
        rule ws, Text::Whitespace
        rule %r{#.*}, Comment::Single
        rule %r{"[^"]*"}, Str::Double
        rule %r{[A-Z][a-zA-Z0-9]*}, Name::Constant
        rule %r{(?:(?:[0-9]+)|(?:XLEN))?'s?[bodh]?[0-9_a-fA-F]+}, Num
        rule %r/0x[0-9a-f]+[lu]*/i, Num::Hex
        rule %r/0[0-7]+[lu]*/i, Num::Oct
        rule %r{\d+}, Num::Integer
        rule %r{(?:true|false|\$encoding|\$pc)}, Name::Builtin
        rule %r{[.,;:\[\]\(\)\}\{]}, Punctuation
        rule %r([~!%^&*+=\|?:<>/-]), Operator
        rule id do |m|
          name = m[0]

          if self.class.keywords.include? name
            token Keyword
          elsif self.class.keywords_type.include? name
            token Keyword::Type
          else
            token Name
          end
        end
      end
    end
  end
end
