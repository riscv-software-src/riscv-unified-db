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
        return @keywords unless @keywords.nil?

        @keywords = Set.new %w[
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
        rule(/#.*/, Comment::Single)
        rule(/"[^"]*"/, Str::Double)
        rule(/[A-Z][a-zA-Z0-9]*/, Name::Constant)
        rule(/(?:(?:[0-9]+)|(?:XLEN))?'s?[bodh]?[0-9_a-fA-F]+/, Num)
        rule(/0x[0-9a-f]+[lu]*/i, Num::Hex)
        rule(/0[0-7]+[lu]*/i, Num::Oct)
        rule(/\d+/, Num::Integer)
        rule(/(?:true|false|\$encoding|\$pc|\$signed|\$bits)/, Name::Builtin)
        rule(/[.,;:\[\]()}{]/, Punctuation)
        rule %r{[~!%^&*+=|?:<>/-]}, Operator
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
