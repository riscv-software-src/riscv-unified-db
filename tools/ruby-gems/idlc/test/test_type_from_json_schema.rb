# Copyright (c) 2026 titoatwork
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"

require "idlc"
require_relative "helpers"

# Tests for Idl::Type.from_json_schema resolving $refs into schema_defs.json.
class TestTypeFromJsonSchema < Minitest::Test
  def ref(name)
    Idl::Type.from_json_schema({ "$ref" => "schema_defs.json#/$defs/#{name}" })
  end

  def test_uint_refs_resolve
    assert_equal "Bits<32>", ref("uint32").to_idl
    assert_equal "Bits<64>", ref("uint64").to_idl
  end

  def test_unsigned_pow2_refs_resolve
    assert_equal "Bits<32>", ref("32bit_unsigned_pow2").to_idl
    assert_equal "Bits<64>", ref("64bit_unsigned_pow2").to_idl
  end

  def test_unknown_ref_raises
    assert_raises(RuntimeError) { ref("not_a_real_def") }
  end
end
