# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "../ast"

module Idl
  class AstNode
    # Generates asciidoc to document an implementation option.
    #
    # The result is *not* IDL code, but pretty-ified Asciidoc for document layout
    #
    # @return [String] Asciidoc source
    def gen_option_adoc
      internal_error "must implement gen_option_adoc for #{self.class.name}"
    end
  end

  class FunctionBodyAst
    def gen_option_adoc
      statements.map(&:gen_option_adoc).join("\n")
    end
  end

  class FunctionCallExpressionAst
    def gen_option_adoc
      gen_adoc(0)
    end
  end

  class IfAst
    def gen_option_adoc
      adoc =
        <<~ADOC
          [when,"#{if_cond.to_idl}"]
          #{if_body.gen_option_adoc}
        ADOC
      elseifs.each do |eif|
        adoc << <<~ADOC
          [when,"#{eif.cond.to_idl}"]
          #{eif.body.gen_option_adoc}
        ADOC
      end
      unless final_else_body.nil?
        if elseifs.empty?
          if if_cond.is_a?(BinaryExpressionAst) || if_cond.is_a?(UnaryOperatorExpressionAst)
            adoc << <<~ADOC
              [when,"#{if_cond.invert(nil).to_idl}"]
              #{final_else_body.gen_option_adoc}
            ADOC
          else
            adoc << <<~ADOC
              [when,"!(#{if_cond.to_idl})"]
              #{final_else_body.gen_option_adoc}
            ADOC
          end
        else
          adoc << <<~ADOC
            [when,"else"]
            #{final_else_body.gen_option_adoc}
          ADOC
        end
      end
      adoc
    end
  end

  class IfBodyAst
    def gen_option_adoc
      stmts.map(&:gen_option_adoc).join("\n")
    end
  end

  class ReturnStatementAst
    def gen_option_adoc
      return_expression.gen_option_adoc
    end
  end

  class StatementAst
    def gen_option_adoc
      action.gen_option_adoc
    end
  end

  class IdAst
    def gen_option_adoc
      text_value
    end
  end

  class IntLiteralAst
    def gen_option_adoc
      if value(nil) == 1 << 65
        "UNDEFINED_LEGAL"
      elsif value(nil) == 1 << 66
        "UNDEFINED_LEGAL_DETERMINISTIC"
      else
        text_value
      end
    end
  end

  class ReturnExpressionAst
    def gen_option_adoc
      raise "unexpected" if return_value_nodes.size != 1

      return_value_nodes[0].gen_option_adoc
    end
  end

  class TernaryOperatorExpressionAst
    def gen_option_adoc
      cond = condition.is_a?(ParenExpressionAst) ? condition.expression : condition
      if cond.is_a?(BinaryExpressionAst) || cond.is_a?(UnaryOperatorExpressionAst)
        <<~ADOC
          [when,"#{cond.gen_adoc.gsub('"', "&quot;")}"]
          #{true_expression.gen_option_adoc}

          [when,"#{cond.invert(nil).gen_adoc.gsub('"', "&quot;")}"]
          #{false_expression.gen_option_adoc}

        ADOC
      else
        <<~ADOC
          [when,"#{cond.gen_adoc.gsub('"', "&quot;")}"]
          #{true_expression.gen_option_adoc}

          [when,"!(#{cond.gen_adoc.gsub('"', "&quot;")})"]
          #{false_expression.gen_option_adoc}

        ADOC
      end
    end
  end

  class EnumRefAst
    def gen_option_adoc
      if class_name == "CsrFieldType"
        case member_name
        when "RW", "RO"
          member_name
        when "ROH"
          "RO-H"
        when "RWR"
          "RW-R"
        when "RWH"
          "RW-H"
        when "RWRH"
          "RW-RH"
        else
          raise "unexpected"
        end
      else
        raise "Unexpected"
      end
    end
  end
end
