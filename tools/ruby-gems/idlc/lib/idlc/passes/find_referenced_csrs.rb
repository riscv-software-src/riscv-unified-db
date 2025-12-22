# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module Idl
  class AstNode
    extend T::Sig
    sig { overridable.returns(T::Array[String]) }
    def find_referenced_csrs
      csrs = T.let([], T::Array[String])
      @children.each do |child|
        csrs += child.find_referenced_csrs
      end
      csrs.uniq
    end
  end

  class CsrReadExpressionAst < AstNode
    sig { override.returns(T::Array[String]) }
    def find_referenced_csrs
      [csr_name]
    end
  end

  class CsrWriteAst < AstNode
    sig { override.returns(T::Array[String]) }
    def find_referenced_csrs
      if idx.is_a?(IntLiteralAst)
        []
      else
        [idx.text_value]
      end
    end
  end
end
