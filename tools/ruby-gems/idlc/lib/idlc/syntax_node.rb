
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

# adds a few functions to Treetop's syntax node
module Treetop
  module Runtime
    class SyntaxNode
      extend T::Sig
      # remember where the code comes from
      #
      # @param filename [String] Filename
      # @param starting_line [Integer] Starting line in the file
      sig { params(filename: T.nilable(String), starting_line: Integer).void }
      def set_input_file(filename, starting_line = 0)
        @input_file = filename
        @starting_line = starting_line
        elements&.each do |child|
          child.set_input_file(filename, starting_line)
        end
        raise "?" if @starting_line.nil?
      end

      sig { returns(T::Boolean) }
      def space? = false

      # Sets the input file for this syntax node unless it has already been set.
      #
      # If the input file has not been set, it will be set with the given filename and starting line number.
      #
      # @param [String] filename The name of the input file.
      # @param [Integer] starting_line The starting line number in the input file.
      sig { params(filename: T.nilable(String), starting_line: Integer).void }
      def set_input_file_unless_already_set(filename, starting_line = 0)
        if @input_file.nil?
          set_input_file(filename, starting_line)
        end
      end
    end
  end
end

module Idl
  class SyntaxNode < Treetop::Runtime::SyntaxNode
    extend T::Sig
    extend T::Helpers

    sig { overridable.returns(Idl::AstNode) }
    def to_ast = raise "Must override to_ast for #{self.class.name}"
  end
end
