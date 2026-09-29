# Copyright (c) 2026 titoatwork
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "json"
require "pathname"

# Regression: 32bit_unsigned_pow2 / 64bit_unsigned_pow2 enum lists must contain
# only true powers of two. A historical 4095 (0xfff) entry leaked into parameter
# enums (e.g. MTVEC base-alignment) and into these shared schema defs.
class TestSchemaDefsPow2 < Minitest::Test
  SCHEMA_DEFS = (Pathname.new(__dir__) / ".." / ".." / ".." / ".." / "spec" / "schemas" / "schema_defs.json").expand_path

  def setup
    @defs = JSON.parse(SCHEMA_DEFS.read)["$defs"]
  end

  def power_of_two?(n)
    n.is_a?(Integer) && n.positive? && (n & (n - 1)).zero?
  end

  def assert_pow2_enum(name)
    schema = @defs.fetch(name)
    assert_equal "integer", schema["type"], "#{name} type"
    enum = schema.fetch("enum")
    assert !enum.empty?, "#{name} enum must not be empty"

    bad = enum.reject { |v| power_of_two?(v) }
    assert_empty bad, "#{name} enum contains non-powers-of-two: #{bad.inspect}"
  end

  def test_32bit_unsigned_pow2_enum_is_powers_of_two
    assert_pow2_enum("32bit_unsigned_pow2")
  end

  def test_64bit_unsigned_pow2_enum_is_powers_of_two
    assert_pow2_enum("64bit_unsigned_pow2")
  end

  def test_schema_defs_file_present
    assert SCHEMA_DEFS.file?, "expected schema_defs.json at #{SCHEMA_DEFS}"
  end
end
