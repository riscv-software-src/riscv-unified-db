# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "udb/operand_name_check"

# Tests for the description/encoding operand-name agreement check.
#
# These exercise the string-level rules directly rather than building a
# ConfiguredArchitecture, so they stay fast and describe the intent of each
# rule rather than the state of the database on the day they were written.
class TestOperandNameCheck < Minitest::Test
  Check = Udb::OperandNameCheck

  def mentioned(description)
    Check.mentioned(description)
  end

  def field_reference?(description, token)
    Check.field_reference?(description, token)
  end

  # --- which tokens are considered at all ---------------------------------- #

  def test_operand_names_in_backticks_are_collected
    assert_equal ["xd"], mentioned("writes the result to `xd`.")
  end

  def test_tokens_outside_backticks_are_ignored
    assert_empty mentioned("writes the result to xd, which is an operand.")
  end

  def test_non_operand_tokens_are_ignored
    # `rm`, `imm` and CSR names are backticked all over the database and are
    # not register operands.
    assert_empty mentioned("rounds using `rm` and adds `imm` before writing `mepc`.")
  end

  def test_each_token_is_reported_once
    assert_equal ["rd"], mentioned("`rd` is written, then `rd` is read, then `rd` again.")
  end

  def test_collects_several_distinct_operands
    assert_equal %w[fs1 fs2 xd], mentioned("compares `fs1` with `fs2` into `xd`.").sort
  end

  def test_a_name_that_is_a_substring_of_another_is_not_confused
    # `rs1` must not be reported merely because `xs1` is present, and the
    # backtick delimiters are what keep the two apart.
    assert_equal ["xs1"], mentioned("the immediate is encoded in `xs1`.")
  end

  # --- distinguishing an encoding field from an operand -------------------- #

  def test_the_x_field_phrasing_is_a_field_reference
    # fcvt.d.s: "The `xs2` field encodes the datatype of the source"
    assert field_reference?("The `xs2` field encodes the datatype of the source.", "xs2")
  end

  def test_equals_phrasing_is_a_field_reference
    # fround.q: "is encoded like `fcvt.q.s`, but with `rs2`=4"
    assert field_reference?("encoded like `fcvt.q.s`, but with `rs2`=4.", "rs2")
  end

  def test_set_to_phrasing_is_a_field_reference
    # fround.d: "is encoded like `fcvt.d.s`, but with `xs2` set to 4"
    assert field_reference?("encoded like `fcvt.d.s`, but with `xs2` set to 4.", "xs2")
  end

  def test_is_set_to_phrasing_is_a_field_reference
    assert field_reference?("but with `xs2` is set to 4.", "xs2")
  end

  def test_field_before_the_token_is_a_field_reference
    # csrrci: "encoded in the `xs1` field"
    assert field_reference?("a 5-bit immediate encoded in the field `xs1`.", "xs1")
  end

  def test_plain_operand_use_is_not_a_field_reference
    refute field_reference?("writes to integer register `xd` if the condition holds.", "xd")
  end

  def test_field_reference_is_specific_to_the_token
    description = "The `xs2` field encodes the datatype; the result goes to `rd`."

    assert field_reference?(description, "xs2")
    refute field_reference?(description, "rd"),
           "a field reference to one token must not excuse a different token"
  end

  # --- regression cases from the database ---------------------------------- #
  #
  # Each of these is a real description that the check must classify the way
  # it does, so a future change to the rules has to confront them.

  def test_fclass_q_style_prose_is_reported
    description = <<~TEXT
      The `fclass.q` instruction examines the value in floating-point register `rs1` and writes to integer
      register `rd` a 10-bit mask that indicates the class of the floating-point number.
    TEXT

    assert_equal %w[rd rs1], mentioned(description).sort
    refute field_reference?(description, "rd")
    refute field_reference?(description, "rs1")
  end

  def test_fcvt_d_s_style_prose_is_not_reported
    description = <<~TEXT
      The single-precision to double-precision conversion instruction, `fcvt.d.s` is encoded in the OP-FP
      major opcode space and both the source and destination are floating-point registers. The `xs2` field
      encodes the datatype of the source, and the `fmt` field encodes the datatype of the destination.
    TEXT

    assert_includes mentioned(description), "xs2"
    assert field_reference?(description, "xs2"),
           "naming a fixed encoding field is legitimate and must not be reported"
  end

  def test_csrrci_style_prose_is_not_reported
    description = <<~TEXT
      ... zero-extending a 5-bit unsigned immediate (imm[4:0]) field encoded in the `xs1` field instead of a
      value from an integer register.
    TEXT

    assert field_reference?(description, "xs1")
  end
end
