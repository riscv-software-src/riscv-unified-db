# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module Udb
  # Checks that the operand names used in an instruction's description actually
  # exist in that instruction's encoding.
  #
  # A description that refers to `rd` when the encoding declares `xd`, or to
  # `rs1` when it declares `fs1`, is describing an operand the instruction does
  # not have. The name is usually borrowed from a sibling instruction, so the
  # prose reads plausibly and the error survives review.
  #
  # Descriptions legitimately mention *encoding fields* that are not decode
  # variables. A fixed field is part of the match string rather than an operand,
  # so it never appears in the variable list, but naming it is correct and
  # common: "`fround.d` is encoded like `fcvt.d.s`, but with `xs2` set to 4".
  # Those references are recognised by the phrasing around them and are not
  # reported.
  module OperandNameCheck
    extend T::Sig

    # Register-operand names used across the database. Restricting the check to
    # this set keeps it away from the many other backticked tokens that appear
    # in prose (CSR names, extension names, IDL fragments, and so on).
    OPERAND_NAMES = T.let(
      %w[rd rs1 rs2 rs3 xd xs1 xs2 fd fs1 fs2 fs3 vd vs1 vs2 vs3].freeze,
      T::Array[String]
    )

    class << self
      extend T::Sig

      # Return a list of human-readable problems for +inst+. Empty means the
      # description only names operands the encoding actually declares.
      sig { params(inst: Instruction).returns(T::Array[String]) }
      def problems(inst)
        description = T.let(inst.description, String)
        return [] if description.empty?

        declared = declared_variable_names(inst)
        # An instruction with no decode variables has nothing to check against;
        # every operand name in its prose would be reported, which is noise.
        return [] if declared.empty?

        mentioned(description).filter_map do |token|
          next if declared.include?(token)
          next if field_reference?(description, token)

          "#{inst.name}: description names `#{token}`, which is not in the " \
            "encoding (declares #{declared.sort.map { |n| "`#{n}`" }.join(", ")})"
        end
      end

      # Every decode-variable name the instruction declares, across both bases.
      # An instruction with separate RV32 and RV64 encodings can declare a
      # different set in each, and a name valid in either is valid in the prose.
      sig { params(inst: Instruction).returns(T::Set[String]) }
      def declared_variable_names(inst)
        names = T.let(Set.new, T::Set[String])
        [32, 64].each do |base|
          next unless inst.defined_in_base?(base)

          inst.decode_variables(base).each { |var| names << T.let(var.name, String) }
        end
        names
      end

      # The distinct operand-like tokens named in +description+.
      #
      # Only backticked occurrences count. Several operand names are also
      # ordinary words in running prose, and the database consistently marks up
      # the ones it means as code.
      sig { params(description: String).returns(T::Array[String]) }
      def mentioned(description)
        OPERAND_NAMES.select { |name| description.include?("`#{name}`") }
      end

      # True when +token+ is being named as an encoding field rather than used
      # as an operand: "the `xs2` field", "`rs2`=4", "`xs2` set to 4".
      sig { params(description: String, token: String).returns(T::Boolean) }
      def field_reference?(description, token)
        quoted = Regexp.escape(token)
        as_field = /`#{quoted}`\s*(?:field\b|=|(?:is\s+)?set\s+to\b)/i
        named_field = /\b(?:field|bits?)\s+`#{quoted}`/i

        as_field.match?(description) || named_field.match?(description)
      end
    end
  end
end
