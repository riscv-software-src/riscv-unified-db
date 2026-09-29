# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"
require_relative "../lib/udb/z3"

class TestZ3ParameterConstraints < Minitest::Test
  def setup
    @solver = Udb::Z3Solver.new
  end

  # String constraint tests
  def test_constrain_string_with_const
    schema = { "type" => "string", "const" => "test_value" }
    param = Udb::Z3ParameterTerm.new("string_param", @solver, schema)

    assert @solver.satisfiable?
    # The parameter should be constrained to the hash of "test_value"
  end

  def test_constrain_string_with_enum
    schema = { "type" => "string", "enum" => ["option1", "option2", "option3"] }
    param = Udb::Z3ParameterTerm.new("string_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_string_const_satisfiability
    schema = { "const" => "specific_string" }
    param = Udb::Z3ParameterTerm.new("str_param", @solver, schema)

    # Should be satisfiable with the specific string
    assert @solver.satisfiable?
  end

  # Array constraint tests
  def test_constrain_array_with_items_schema
    schema = {
      "type" => "array",
      "items" => { "type" => "integer", "minimum" => 0, "maximum" => 100 },
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("array_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_with_tuple_items
    schema = {
      "type" => "array",
      "items" => [
        { "type" => "integer", "const" => 1 },
        { "type" => "integer", "const" => 2 },
        { "type" => "integer", "const" => 3 }
      ],
      "maxItems" => 3
    }
    param = Udb::Z3ParameterTerm.new("tuple_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_with_contains
    schema = {
      "type" => "array",
      "items" => { "type" => "integer" },
      "contains" => { "type" => "integer", "const" => 42 },
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("contains_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_with_unique_items
    schema = {
      "type" => "array",
      "items" => { "type" => "integer", "minimum" => 0, "maximum" => 10 },
      "uniqueItems" => true,
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("unique_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_with_min_max_items
    schema = {
      "type" => "array",
      "items" => { "type" => "integer" },
      "minItems" => 2,
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("sized_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_boolean_items
    schema = {
      "type" => "array",
      "items" => { "type" => "boolean" },
      "maxItems" => 3
    }
    param = Udb::Z3ParameterTerm.new("bool_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_array_string_items
    schema = {
      "type" => "array",
      "items" => { "type" => "string", "enum" => ["a", "b", "c"] },
      "maxItems" => 3
    }
    param = Udb::Z3ParameterTerm.new("string_array", @solver, schema)

    assert @solver.satisfiable?
  end

  # detect_array_subtype tests
  def test_detect_array_subtype_integer
    schema = { "items" => { "type" => "integer" } }
    subtype = Udb::Z3ParameterTerm.detect_array_subtype(schema)

    assert_equal :int, subtype
  end

  def test_detect_array_subtype_boolean
    schema = { "items" => { "type" => "boolean" } }
    subtype = Udb::Z3ParameterTerm.detect_array_subtype(schema)

    assert_equal :boolean, subtype
  end

  def test_detect_array_subtype_string
    schema = { "items" => { "type" => "string" } }
    subtype = Udb::Z3ParameterTerm.detect_array_subtype(schema)

    assert_equal :string, subtype
  end

  def test_detect_array_subtype_tuple_style
    schema = { "items" => [{ "type" => "integer" }, { "type" => "integer" }] }
    subtype = Udb::Z3ParameterTerm.detect_array_subtype(schema)

    assert_equal :int, subtype
  end

  # $ref handling tests
  def test_constrain_int_with_uint32_ref
    schema = { "$ref" => "schema_defs.json#/$defs/uint32" }
    param = Udb::Z3ParameterTerm.new("uint32_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_int_with_uint64_ref
    schema = { "$ref" => "schema_defs.json#/$defs/uint64" }
    param = Udb::Z3ParameterTerm.new("uint64_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_int_with_32bit_pow2_ref
    schema = { "$ref" => "schema_defs.json#/$defs/32bit_unsigned_pow2" }
    param = Udb::Z3ParameterTerm.new("pow2_32_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_int_with_64bit_pow2_ref
    schema = { "$ref" => "schema_defs.json#/$defs/64bit_unsigned_pow2" }
    param = Udb::Z3ParameterTerm.new("pow2_64_param", @solver, schema)

    assert @solver.satisfiable?
  end

  # allOf schema tests
  def test_constrain_int_with_allof
    schema = {
      "allOf" => [
        { "type" => "integer", "minimum" => 10 },
        { "type" => "integer", "maximum" => 20 }
      ]
    }
    param = Udb::Z3ParameterTerm.new("allof_param", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_bool_with_allof
    schema = {
      "allOf" => [
        { "type" => "boolean" },
        { "const" => true }
      ]
    }
    param = Udb::Z3ParameterTerm.new("allof_bool", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_constrain_int_with_anyof_const
    schema = {
      "anyOf" => [
        { "const" => 1 },
        { "const" => 2 }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_const_param", @solver, schema)

    assert @solver.satisfiable?

    # Only 1 or 2 should be allowed
    [1, 2].each do |value|
      @solver.push
      @solver.assert(param == value)
      assert @solver.satisfiable?
      @solver.pop
    end

    @solver.push
    @solver.assert(param == 3)
    refute @solver.satisfiable?
    @solver.pop
  end

  def test_constrain_int_with_anyof_ranges
    schema = {
      "anyOf" => [
        { "minimum" => 0, "maximum" => 10 },
        { "minimum" => 100, "maximum" => 110 }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_range_param", @solver, schema)

    assert @solver.satisfiable?

    # A value inside either range is allowed
    [5, 105].each do |value|
      @solver.push
      @solver.assert(param == value)
      assert @solver.satisfiable?
      @solver.pop
    end

    # A value in the gap between the two ranges is not
    @solver.push
    @solver.assert(param == 50)
    refute @solver.satisfiable?
    @solver.pop
  end

  def test_constrain_int_with_anyof_and_other_constraints
    # anyOf combined with a sibling minimum: the value must satisfy the
    # minimum *and* fall into one of the anyOf subschemas.
    schema = {
      "minimum" => 1,
      "anyOf" => [
        { "const" => 0 },
        { "const" => 5 }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_combined_param", @solver, schema)

    # const 0 satisfies anyOf but violates the sibling minimum, so only 5 remains
    @solver.push
    @solver.assert(param == 0)
    refute @solver.satisfiable?
    @solver.pop

    @solver.push
    @solver.assert(param == 5)
    assert @solver.satisfiable?
    @solver.pop
  end

  def test_constrain_int_with_anyof_nested_allof
    # A nested allOf must stay branch-local. If it leaked straight into the
    # solver, the 10..20 branch would become mandatory and 105 unsatisfiable.
    schema = {
      "anyOf" => [
        { "allOf" => [{ "minimum" => 10 }, { "maximum" => 20 }] },
        { "minimum" => 100, "maximum" => 110 }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_nested_allof_param", @solver, schema)

    [15, 105].each do |value|
      @solver.push
      @solver.assert(param == value)
      assert @solver.satisfiable?
      @solver.pop
    end

    @solver.push
    @solver.assert(param == 50)
    refute @solver.satisfiable?
    @solver.pop
  end

  def test_constrain_bool_with_anyof
    schema = {
      "type" => "boolean",
      "anyOf" => [
        { "allOf" => [{ "const" => true }] },
        { "const" => false }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_bool", @solver, schema)

    [true, false].each do |value|
      @solver.push
      @solver.assert(param == value)
      assert @solver.satisfiable?
      @solver.pop
    end
  end

  def test_constrain_string_with_anyof
    schema = {
      "type" => "string",
      "anyOf" => [
        { "const" => "alpha" },
        { "enum" => ["beta", "gamma"] }
      ]
    }
    param = Udb::Z3ParameterTerm.new("anyof_string", @solver, schema)

    ["alpha", "beta", "gamma"].each do |value|
      @solver.push
      @solver.assert(param == value)
      assert @solver.satisfiable?
      @solver.pop
    end

    @solver.push
    @solver.assert(param == "delta")
    refute @solver.satisfiable?
    @solver.pop
  end

  # Type detection tests
  def test_detect_type_from_allof_integer
    schema = {
      "allOf" => [
        { "type" => "integer" },
        { "minimum" => 0 }
      ]
    }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :int, type
  end

  def test_detect_type_from_allof_integer_2
    schema = {
      "allOf" => [
        { "type" => "integer" },
        { "maximum" => 0 }
      ]
    }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :int, type
  end

  def test_detect_type_from_allof_boolean
    schema = {
      "allOf" => [
        { "type" => "boolean" },
        { "const" => true }
      ]
    }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :boolean, type
  end

  def test_detect_type_from_allof_string
    schema = {
      "allOf" => [
        { "type" => "string" },
        { "enum" => ["a", "b"] }
      ]
    }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :string, type
  end

  def test_detect_type_from_anyof_integer
    schema = {
      "anyOf" => [
        { "const" => 1 },
        { "const" => 2 }
      ]
    }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :int, type
  end

  def test_detect_type_from_ref_uint32
    schema = { "$ref" => "schema_defs.json#/$defs/uint32" }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :int, type
  end

  def test_detect_type_from_ref_pow2
    schema = { "$ref" => "schema_defs.json#/$defs/32bit_unsigned_pow2" }
    type = Udb::Z3ParameterTerm.detect_type(schema)

    assert_equal :int, type
  end

  # Edge case tests
  def test_parameter_term_with_empty_enum
    # This should still be satisfiable, just constrained
    schema = { "type" => "integer", "enum" => [42] }
    param = Udb::Z3ParameterTerm.new("single_enum", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_parameter_term_with_conflicting_constraints
    schema = {
      "type" => "integer",
      "minimum" => 100,
      "maximum" => 50  # Conflicting: min > max
    }
    param = Udb::Z3ParameterTerm.new("conflict_param", @solver, schema)

    # Should be unsatisfiable
    refute @solver.satisfiable?
  end

  def test_array_with_additional_items
    schema = {
      "type" => "array",
      "items" => [
        { "type" => "integer", "const" => 1 }
      ],
      "additionalItems" => { "type" => "integer", "minimum" => 10 },
      "maxItems" => 3
    }
    param = Udb::Z3ParameterTerm.new("additional_items_array", @solver, schema)

    assert @solver.satisfiable?
  end

  def test_parameter_operations
    schema = { "type" => "integer", "minimum" => 10, "maximum" => 20 }
    param = Udb::Z3ParameterTerm.new("test_param", @solver, schema)

    # Test equality
    @solver.push
    @solver.assert(param == 15)
    assert @solver.satisfiable?
    @solver.pop

    # Test inequality
    @solver.push
    @solver.assert(param != 15)
    assert @solver.satisfiable?
    @solver.pop

    # Test less than or equal
    @solver.push
    @solver.assert(param <= 12)
    assert @solver.satisfiable?
    @solver.pop

    # Test greater than or equal
    @solver.push
    @solver.assert(param >= 18)
    assert @solver.satisfiable?
    @solver.pop
  end

  def test_array_parameter_operations
    schema = {
      "type" => "array",
      "items" => { "type" => "integer" },
      "maxItems" => 3
    }
    param = Udb::Z3ParameterTerm.new("array_param", @solver, schema)

    # Test array equality
    @solver.push
    @solver.assert(param == [1, 2, 3])
    assert @solver.satisfiable?
    @solver.pop

    # Test array inequality
    @solver.push
    @solver.assert(param != [1, 2, 3])
    assert @solver.satisfiable?
    @solver.pop

    # Test has_value
    @solver.push
    @solver.assert(param.has_value?(5))
    assert @solver.satisfiable?
    @solver.pop
  end

  def test_string_parameter_equality
    schema = { "type" => "string", "enum" => ["option1", "option2"] }
    param = Udb::Z3ParameterTerm.new("string_param", @solver, schema)

    # Test string equality (uses hash comparison)
    @solver.push
    @solver.assert(param == "option1")
    assert @solver.satisfiable?
    @solver.pop

    # Test string inequality
    @solver.push
    @solver.assert(param != "option1")
    assert @solver.satisfiable?
    @solver.pop
  end

  def test_bitvec_extract
    schema = { "type" => "integer", "minimum" => 0, "maximum" => 0xFFFFFFFF }
    param = Udb::Z3ParameterTerm.new("bv_param", @solver, schema)

    # Test extract operation
    upper_bits = param.extract(31, 16)
    assert_instance_of Z3::BitvecExpr, upper_bits
  end

  def test_array_size_term
    schema = {
      "type" => "array",
      "items" => { "type" => "integer" },
      "minItems" => 2,
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("sized_array", @solver, schema)

    size = param.size_term
    assert_instance_of Z3::IntExpr, size

    # Size should be between 2 and 5
    @solver.push
    @solver.assert(size >= 2)
    @solver.assert(size <= 5)
    assert @solver.satisfiable?
    @solver.pop
  end

  def test_array_indexing
    schema = {
      "type" => "array",
      "items" => { "type" => "integer", "minimum" => 0, "maximum" => 100 },
      "maxItems" => 5
    }
    param = Udb::Z3ParameterTerm.new("indexed_array", @solver, schema)

    # Test array indexing
    elem0 = param[0]
    elem1 = param[1]

    assert_instance_of Z3::BitvecExpr, elem0
    assert_instance_of Z3::BitvecExpr, elem1

    # Elements should be different variables
    refute_equal elem0.object_id, elem1.object_id
  end
end
