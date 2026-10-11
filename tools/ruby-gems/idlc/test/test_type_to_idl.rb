# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"

require "idlc"
require_relative "helpers"

# Tests for Idl::Type#to_idl rendering.
class TestTypeToIdl < Minitest::Test
  def test_bits_to_idl_has_closing_angle_bracket
    assert_equal "Bits<32>", Idl::Type.new(:bits, width: 32).to_idl
  end

  def test_string_to_idl_returns_string_name
    assert_equal "String", Idl::Type.new(:string, width: 8).to_idl
  end

  def test_json_schema_zero_integer_const_needs_one_bit
    type = Idl::Type.from_json_schema({ "const" => 0 })

    assert_equal Idl::Type.new(:bits, width: 1), type
  end

  def test_json_schema_tuple_array_widens_integer_item_types
    type = Idl::Type.from_json_schema(
      {
        "type" => "array",
        "items" => [
          { "const" => 0 }
        ],
        "additionalItems" => {
          "type" => "integer",
          "enum" => [7, 16]
        },
        "minItems" => 1,
        "maxItems" => 3,
        "uniqueItems" => true
      }
    )

    assert_equal :array, type.kind
    assert_equal :unknown, type.width
    assert_equal Idl::Type.new(:bits, width: 5), type.sub_type
  end
end
