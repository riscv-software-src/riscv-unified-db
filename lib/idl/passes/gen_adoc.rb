require_relative "../ast"

class Treetop::Runtime::SyntaxNode
  def gen_adoc(indent = 0, indent_spaces: 2)
    if terminal?
      text_value
    else
      adoc = ''
      next_pos = interval.begin
      elements.each do |e|
        if e.interval.size > 0 &&  e.interval.begin != next_pos
          adoc << input[next_pos..(e.interval.begin - 1)]
        end
        adoc << e.gen_adoc(indent+2, indent_spaces: 2)
        next_pos = e.interval.exclude_end? ? e.interval.end : (e.interval.end + 1)
      end
      if next_pos != (interval.exclude_end? ? interval.end : (interval.end + 1))
        end_pos = interval.exclude_end? ? interval.end - 1 : interval.end
        adoc << input[next_pos..end_pos]
      end
      if adoc != text_value && !text_value.index('xref').nil?
        raise
      end
      adoc
    end
  end
end

module Idl
  class AryRangeAccessAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      adoc = ''
      unless var.is_a?(AryRangeAccessAst) || var.is_a?(AryElementAccessAst)
        adoc << input[interval.begin...var.interval.begin]
        adoc << var.gen_adoc(indent + indent_spaces, indent_spaces: indent_spaces)
      end
      adoc << input[var.interval.end...msb.interval.begin]
      adoc << msb.gen_adoc(indent + indent_spaces, indent_spaces: indent_spaces)
      adoc << input[msb.interval.end...lsb.interval.begin]
      adoc << lsb.gen_adoc(indent + indent_spaces, indent_spaces: indent_spaces)
      adoc << input[lsb.interval.end...interval.end]
      adoc
    end
  end

  class FunctionCallExpressionAst
    def gen_adoc(indent = 0, indent_spaces: 2)
      "xref:funcs:funcs.adoc##{name}-func-def[#{name}]" << t.gen_adoc << "(#{function_arg_list.gen_adoc})"
    end
  end
end
