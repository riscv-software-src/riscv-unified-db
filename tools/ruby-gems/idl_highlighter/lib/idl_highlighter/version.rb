# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Rouge
  class Lexer; end
  class RegexLexer < Lexer; end
  module Lexers
    class Idl < RegexLexer
      def self.version = "0.1.0"
    end
  end
end
