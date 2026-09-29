# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: strict
# frozen_string_literal: true

# Z3 Solver Integration for RISC-V Unified Database
#
# This module provides integration with the Z3 SMT solver to validate and reason about
# RISC-V architecture configurations, parameters, and extension requirements.
#


require "forwardable"
require "sorbet-runtime"
require "udb/version_spec"

require_relative "global_opts"
require_relative "z3_loader"

# Ensure Z3 library is available before requiring the z3 gem
Udb::Z3Loader.ensure_z3_loaded

require "z3"

# Patch Z3::AST#ast_kind to use a constant hash instead of allocating a new one on every call
module Z3
  class AST
    extend T::Sig

    AST_KIND_LOOKUP = T.let({
      0 => :numeral,
      1 => :app,
      2 => :var,
      3 => :quantifier,
      4 => :sort,
      5 => :func_decl,
      1000 => :unknown,
    }.freeze, T::Hash[Integer, Symbol])

    sig { returns(Symbol).checked(:never) }
    def ast_kind
      kind_id = LowLevel.get_ast_kind(self)
      AST_KIND_LOOKUP[kind_id] or raise Z3::Exception, "Unknown AST kind #{kind_id}"
    end
  end
end

module Z3
  # Extension to the Z3::Solver class to add tracked assertions
  class Solver
    extend T::Sig

    # Assert an expression and track it with a name for unsat core analysis
    #
    # This method extends Z3::Solver to support named assertions, which is useful
    # for debugging when a set of constraints is unsatisfiable. The name appears
    # in the unsat core, helping identify which constraints conflict.
    #
    # @param ast [Z3::Expr] The boolean expression to assert
    # @param name [String] A descriptive name for this assertion (used in unsat cores)
    sig { params(ast: Z3::Expr, name: String).void }
    def assert_as(ast, name)
      reset_model!
      Z3::LowLevel.solver_assert_and_track(
        self,
        ast, Z3::Bool(name))
    end
  end
end

module Udb
  class Z3Sovler; end

  # Encapsulates a type constraint callback for validating array items
  #
  # This struct holds a method reference and its associated JSON schema, allowing
  # lazy evaluation of type constraints on array elements. The method is called
  # with the solver, a Z3 term, and the schema to generate constraint assertions.
  class TypeConstraint < T::Struct
    const :mthd, Method
    const :schema, T::Hash[String, T.untyped]
  end

  # Aggregates all JSON schema constraints for an array parameter
  #
  # This struct collects various array validation rules from JSON schemas:
  # - Position-specific item schemas (tuple validation)
  # - General item schema for remaining positions
  # - "contains" requirement (at least one matching item)
  # - Uniqueness constraint
  # - Size bounds (min/max)
  class ArrayConstraints < T::Struct
    # Schema applied to specific array positions (for tuple-style arrays)
    prop :item_by_idx, T::Hash[Integer, TypeConstraint], default: {}

    # Schema applied to all positions not covered by item_by_idx
    prop :item_rest, T.nilable(TypeConstraint)

    # When present, array must contain at least one item matching this schema
    prop :contains, T.nilable(TypeConstraint)

    # Whether array items must be unique (JSON schema "uniqueItems")
    prop :unique, T::Boolean, default: false

    # Maximum number of elements allowed
    prop :max_size, T.nilable(Integer)

    # Minimum number of elements required
    prop :min_size, T.nilable(Integer)
  end

  # Models a finite-sized array in Z3 using explicit scalar variables
  #
  # Z3 arrays are normally unbounded, but we need finite arrays with explicit size
  # for parameter validation. This class models an array as:
  # - A size variable (Z3::IntExpr)
  # - Individual scalar variables for each potential element
  #
  # Limitations:
  # - Cannot truly represent unbounded arrays (would require ForAll/Exists quantifiers
  #   not available in the Z3 Ruby bindings)
  # - Maximum practical size is 64 elements (hardcoded limit)
  # - Arrays larger than 64 are capped at 64 with an error if more are needed
  #
  class Z3FiniteArray
    extend T::Sig

    sig {
      params(
        solver: Z3Solver,
        name: String,
        sort: T.any(T.class_of(Z3::IntSort), T.class_of(Z3::BoolSort), T.class_of(Z3::BitvecSort)),
        constraints: ArrayConstraints,
        bitvec_width: T.nilable(Integer))
      .void
    }
    def initialize(solver, name, sort, constraints, bitvec_width: nil)
      @name = name
      @solver = solver
      @subtype_sort =
        T.let(
          if sort == Z3::BitvecSort
            sort.new(T.must(bitvec_width))
          else
            sort.new
          end,
          Z3::Sort
        )
      @constraints = constraints
      # Determine array size: use max_size if specified, otherwise cap at 64
      # The 64-element limit is a practical constraint to keep the solver tractable
      @num_items =
        T.let(
          if @constraints.max_size.nil?
            64
          else
            if T.must(@constraints.max_size) > 64
              64
            else
              T.must(@constraints.max_size)
            end
          end,
          Integer
        )
      # Create Z3 variables for each array element and apply constraints
      @items = T.let(
        Array.new(@num_items) { |index|
          v = @subtype_sort.var("#{@name}_idx#{index}")
          constrain_element(index, v)
        },
        T::Array[T.any(Z3::BitvecExpr, Z3::IntExpr, Z3::BoolExpr)]
      )
      # Create a size variable to track the logical array length
      @size = T.let(Z3.Int("#{@name}_size"), Z3::IntExpr)
      unless @constraints.min_size.nil?
        solver.assert_as @size >= @constraints.min_size, "#{@name}_size_lower_bound"
      end
      unless @constraints.max_size.nil?
        solver.assert_as @size <= @constraints.max_size, "#{@name}_size_upper_bound"
      end
      # Handle "contains" constraint: at least one element must match the schema
      unless @constraints.contains.nil?
        target_value = @subtype_sort.var("#{@name}_contain_value")
        T.must(@constraints.contains).mthd.call(@solver, target_value, T.must(@constraints.contains).schema, assert: true)
        exprs = @items.map do |item|
          item == target_value
        end
        solver.assert T.unsafe(Z3).Or(*exprs)
      end
      # Handle uniqueness constraint: all elements must be distinct
      if @constraints.unique
        solver.assert T.unsafe(Z3).Distinct(*@items)
      end
    end

    sig { params(idx: Integer).returns(T.any(Z3::BitvecExpr, Z3::IntExpr, Z3::BoolExpr)) }
    def [](idx)
      if idx >= @num_items
        raise "array index (#{idx}) is out of bounds (#{@num_items}). May need to increase the upper limit of Z3FiniteArray from 64"
      end
      @items.fetch(idx)
    end

    # Apply type constraints to array element at a specific index
    #
    # This method applies JSON schema constraints to an array element based on:
    # 1. Position-specific schemas (item_by_idx) - for tuple-style arrays
    # 2. General schema (item_rest) - for remaining positions
    #
    # @param i [Integer] The array index
    # @param v [Z3::Expr] The Z3 variable representing the element
    # @return [Z3::Expr] The same variable (for chaining)
    sig { params(i: Integer, v: Z3::Expr).returns(Z3::Expr) }
    def constrain_element(i, v)
      if !@constraints.item_by_idx.empty?
        already_constrained = T.let(false, T::Boolean)
        @constraints.item_by_idx.each do |idx, typ_constr|
          if idx == i
            already_constrained = true
            assertions =
              typ_constr.mthd.call(@solver, v, typ_constr.schema, assert: false)
            assertions.each { |a| @solver.assert a }
          end
        end
        # Apply general schema if no position-specific schema was found
        if !already_constrained && !@constraints.item_rest.nil?
          assertions =
            T.must(@constraints.item_rest).mthd.call(@solver, v, T.must(@constraints.item_rest).schema, assert: false)
          assertions.each { |a| @solver.assert a }
        end
      elsif !@constraints.item_rest.nil?
        T.must(@constraints.item_rest).mthd.call(@solver, v, T.must(@constraints.item_rest).schema)
      end
      v
    end

    # Check if the array contains a specific value
    #
    # Returns a Z3 expression that is true if at least one element within the
    # logical array size equals the given value. For strings, we use hash values
    # since Z3 doesn't natively support string types.
    #
    # @param val [Integer, Boolean, String, Z3::Expr] The value to search for
    # @return [Z3::BoolExpr] Expression that is true if value is present
    sig { params(val: T.any(Integer, T::Boolean, String, Z3::Expr)).returns(Z3::BoolExpr) }
    def has_value?(val)
      exprs = @items.each_with_index.map do |i, idx|
        # Use hash for strings since Z3 doesn't have native string support
        (i == (val.is_a?(String) ? val.hash : val)) & (@size > idx)
      end
      T.unsafe(Z3).Or(*exprs)
    end

    # Check array equality (same elements in same positions)
    #
    # Equality is defined as:
    # - Same logical size
    # - Same values at each position up to the size
    #
    # Special cases:
    # - Empty arrays: size == 0
    # - Arrays larger than our model: raise error or return false
    # - Arrays smaller than min_size: return false
    #
    # @param ary [Array] The Ruby array to compare against
    # @return [Z3::BoolExpr] Expression that is true if arrays are equal
    sig { params(ary: T::Array[T.any(Integer, String, T::Boolean)]).returns(Z3::BoolExpr) }
    def ==(ary)
      if ary.empty?
        @size == 0
      elsif ary.size > @num_items
        # Check if this is a real constraint violation or just our 64-element limit
        if @constraints.max_size.nil?
          # This is an artificial limit from our 64-element cap
          raise "Comparison of array larger than proof model can handle. May need to increase the 64-entry limit"
        elsif T.must(@constraints.max_size) > @num_items
          raise "Comparison of array larger than proof model can handle. May need to increase the 64-entry limit"
        else
          # Array can't be equal because it exceeds the schema's max_size
          return Z3.False
        end
      elsif !@constraints.min_size.nil? && (ary.size < T.must(@constraints.min_size))
        # Array is too small to satisfy min_size constraint
        return Z3.False
      else
        # Build equality expression: size matches and all elements match
        exprs = ary.each_index.map do |i|
          # Use hash for strings since Z3 doesn't have native string support
          @items.fetch(i) == (ary[i].is_a?(String) ? ary[i].hash : ary[i])
        end
        T.unsafe(Z3).And(@size == ary.size, *exprs)
      end
    end

    sig { params(ary: T::Array[T.any(Integer, String, T::Boolean)]).returns(Z3::BoolExpr) }
    def !=(ary)
      ~(self == ary)
    end

    sig { returns(Z3::IntExpr) }
    def size_term = @size

    sig { returns(T.nilable(Integer)) }
    def max_size = @constraints.max_size
  end

  # Represents a RISC-V parameter as a Z3 term with JSON schema constraints
  #
  # This class bridges JSON schemas and Z3 solver terms. When constructed, it:
  # 1. Detects the parameter type from the JSON schema
  # 2. Creates an appropriate Z3 variable (Bool, Int, Bitvec, or FiniteArray)
  # 3. Applies all schema constraints as Z3 assertions
  #
  # There is only one Z3ParameterTerm per parameter name in a solver context.
  # The term is created lazily and cached by the Z3Solver.
  #
  # Supported JSON schema features:
  # - Type constraints (boolean, integer, string, array)
  # - Value constraints (const, enum, minimum, maximum)
  # - Composition (allOf; anyOf for boolean, integer, and string)
  # - References ($ref to uint32/uint64)
  # - Array constraints (items, minItems, maxItems, contains, uniqueItems)
  #
  # Not yet supported (TODO):
  # - anyOf for array
  # - oneOf, noneOf
  # - if/then/else (conditional schemas)
  class Z3ParameterTerm
    extend T::Sig

    sig { returns(String) }
    attr_reader :name

    sig { returns(T.any(Z3::BoolExpr, Z3::IntExpr, Z3::BitvecExpr, Z3FiniteArray)) }
    attr_reader :term

    # Construct Z3 constraints for an integer parameter from JSON schema
    #
    # Handles JSON schema keywords:
    # - const: exact value
    # - enum: one of several values
    # - minimum/maximum: range bounds (unsigned comparison)
    # - allOf: conjunction of subschemas
    # - anyOf: inclusive disjunction of subschemas (at least one must hold)
    # - $ref: references to uint32/uint64 types
    #
    # @param solver [Z3Solver] The solver to add assertions to
    # @param term [Z3::BitvecExpr] The Z3 bitvector term to constrain
    # @param schema_hsh [Hash] The JSON schema
    # @param name [String, nil] Optional name for debugging
    # @param assert [Boolean] Whether to assert constraints immediately
    # @return [Array<Z3::BoolExpr>] The generated constraint expressions
    sig {
      params(
        solver: Z3Solver,
        term: Z3::BitvecExpr,
        schema_hsh: T::Hash[String, T.untyped],
        name: T.nilable(String),
        assert: T::Boolean
      )
      .returns(T::Array[Z3::BoolExpr])
    }
    def self.constrain_int(solver, term, schema_hsh, name: nil, assert: true)
      assertions = T.let([], T::Array[Z3::BoolExpr])
      if schema_hsh.key?("const")
        assertions << (term == schema_hsh.fetch("const"))
      end

      if schema_hsh.key?("enum")
        # Build disjunction: term equals one of the enum values
        expr = (term == schema_hsh.fetch("enum")[0])
        schema_hsh.fetch("enum")[1..].each do |v|
          expr = expr | (term == v)
        end
        assertions << expr
      end

      if schema_hsh.key?("minimum")
        # Use unsigned comparison for RISC-V parameter values
        assertions << term.unsigned_ge(schema_hsh.fetch("minimum"))
      end

      if schema_hsh.key?("maximum")
        assertions << term.unsigned_le(schema_hsh.fetch("maximum"))
      end

      if schema_hsh.key?("allOf")
        schema_hsh.fetch("allOf").each do |h|
          assertions += constrain_int(solver, term, h, assert: false)
        end
      end

      if schema_hsh.key?("anyOf")
        branches = schema_hsh.fetch("anyOf").map do |h|
          constrain_int(solver, term, h, assert: false)
        end
        assertions << any_of_constraint(branches)
      end

      if schema_hsh.key?("oneOf")
        raise "TODO: oneOf not yet implemented for integer constraints"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO: noneOf not yet implemented for integer constraints"
      end

      if schema_hsh.key?("if")
        raise "TODO: if/then/else not yet implemented for integer constraints"
      end

      if schema_hsh.key?("$ref")
        # Handle references to shorthand type definitions
        if schema_hsh.fetch("$ref").split("/").last == "uint32"
          assertions << ((term.unsigned_ge(0)) & (term.unsigned_le(2**32 - 1)))
        elsif schema_hsh.fetch("$ref").split("/").last == "uint64"
          assertions << ((term.unsigned_ge(0)) & (term.unsigned_le(2**64 - 1)))
        elsif schema_hsh.fetch("$ref").split("/").last == "32bit_unsigned_pow2"
          assertions << ((term == 0) | (0 == (term & (term - 1))))
          assertions << ((term.unsigned_gt(0)) & (term.unsigned_le(2**32 - 1)))
        elsif schema_hsh.fetch("$ref").split("/").last == "64bit_unsigned_pow2"
          assertions << ((term == 0) | (0 == (term & (term - 1))))
          assertions << ((term.unsigned_gt(0)) & (term.unsigned_le(2**64 - 1)))
        else
          raise "Unhandled schema $ref: #{schema_hsh.fetch("$ref")}"
        end
      end

      if assert
        assertions.each { |a| solver.assert a }
      end
      assertions
    end

    # Construct Z3 constraints for a boolean parameter from JSON schema
    #
    # Handles JSON schema keywords:
    # - const: exact boolean value
    # - allOf: conjunction of subschemas
    # - anyOf: inclusive disjunction of subschemas (at least one must hold)
    #
    # @param solver [Z3Solver] The solver to add assertions to
    # @param term [Z3::BoolExpr] The Z3 boolean term to constrain
    # @param schema_hsh [Hash] The JSON schema
    # @param name [String, nil] Optional name for debugging
    # @param assert [Boolean] Whether to assert constraints immediately
    # @return [Array<Z3::BoolExpr>] The generated constraint expressions
    sig {
      params(
        solver: Z3Solver,
        term: Z3::BoolExpr,
        schema_hsh: T::Hash[String, T.untyped],
        name: T.nilable(String),
        assert: T::Boolean
      )
      .returns(T::Array[Z3::BoolExpr])
    }
    def self.constrain_bool(solver, term, schema_hsh, name: nil, assert: true)
      assertions = T.let([], T::Array[Z3::BoolExpr])
      if schema_hsh.key?("const")
        assertions << (term == schema_hsh.fetch("const"))
      end

      if schema_hsh.key?("allOf")
        schema_hsh.fetch("allOf").each do |h|
          assertions += constrain_bool(solver, term, h, assert: false)
        end
      end

      if schema_hsh.key?("anyOf")
        branches = schema_hsh.fetch("anyOf").map do |h|
          constrain_bool(solver, term, h, assert: false)
        end
        assertions << any_of_constraint(branches)
      end

      if schema_hsh.key?("oneOf")
        raise "TODO: oneOf not yet implemented for boolean constraints"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO: noneOf not yet implemented for boolean constraints"
      end

      if schema_hsh.key?("if")
        raise "TODO: if/then/else not yet implemented for boolean constraints"
      end

      if assert
        assertions.each { |a| solver.assert a }
      end
      assertions
    end

    # Construct Z3 constraints for a string parameter from JSON schema
    #
    # Since Z3 doesn't natively support strings, we use integer hashes of strings.
    # This means we can check equality but not string operations like length or regex.
    #
    # Handles JSON schema keywords:
    # - const: exact string value (compared via hash)
    # - enum: one of several string values (compared via hash)
    # - anyOf: inclusive disjunction of subschemas (at least one must hold)
    #
    # @param solver [Z3Solver] The solver to add assertions to
    # @param term [Z3::IntExpr] The Z3 integer term representing the string hash
    # @param schema_hsh [Hash] The JSON schema
    # @param name [String, nil] Optional name for debugging
    # @param assert [Boolean] Whether to assert constraints immediately
    # @return [Array<Z3::BoolExpr>] The generated constraint expressions
    sig {
      params(
        solver: Z3Solver,
        term: Z3::IntExpr,
        schema_hsh: T::Hash[String, T.untyped],
        name: T.nilable(String),
        assert: T::Boolean
      )
      .returns(T::Array[Z3::BoolExpr])
    }
    def self.constrain_string(solver, term, schema_hsh, name: nil, assert: true)
      assertions = T.let([], T::Array[Z3::BoolExpr])
      if schema_hsh.key?("const")
        # Compare string hashes since Z3 doesn't have native string support
        assertions << (term == schema_hsh.fetch("const").hash)
      end

      if schema_hsh.key?("enum")
        # Build disjunction of string hash comparisons
        expr = (term == schema_hsh.fetch("enum")[0].hash)
        schema_hsh.fetch("enum")[1..].each do |v|
          expr = expr | (term == v.hash)
        end
        assertions << expr
      end

      if schema_hsh.key?("anyOf")
        branches = schema_hsh.fetch("anyOf").map do |h|
          constrain_string(solver, term, h, assert: false)
        end
        assertions << any_of_constraint(branches)
      end

      if schema_hsh.key?("oneOf")
        raise "TODO: oneOf not yet implemented for string constraints"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO: noneOf not yet implemented for string constraints"
      end

      if schema_hsh.key?("if")
        raise "TODO: if/then/else not yet implemented for string constraints"
      end

      if assert
        assertions.each { |a| solver.assert a }
      end
      assertions
    end

    sig { params(branches: T::Array[T::Array[Z3::BoolExpr]]).returns(Z3::BoolExpr) }
    def self.any_of_constraint(branches)
      expressions = branches.map do |branch|
        branch.reduce(Z3.True) { |expression, assertion| expression & assertion }
      end
      expressions.reduce(Z3.False) { |expression, branch| expression | branch }
    end
    private_class_method :any_of_constraint

    # Extract array constraints from JSON schema
    #
    # Processes JSON schema array keywords and returns an ArrayConstraints object
    # that will be used to construct a Z3FiniteArray. Handles:
    # - items: schema for array elements (tuple or uniform)
    # - additionalItems: schema for elements beyond tuple positions
    # - contains: at least one element must match this schema
    # - uniqueItems: all elements must be distinct
    # - minItems/maxItems: size bounds
    #
    # @param solver [Z3Solver] The solver (for context)
    # @param schema_hsh [Hash] The JSON schema
    # @param subtype_constrain [Method] Method to constrain array element types
    # @return [ArrayConstraints] The extracted constraints
    sig {
      params(
        solver: Z3Solver,
        schema_hsh: T::Hash[String, T.untyped],
        subtype_constrain: Method,
      )
      .returns(ArrayConstraints)
    }
    def self.constrain_array(solver, schema_hsh, subtype_constrain)
      constraints = ArrayConstraints.new
      if schema_hsh.key?("items")
        if schema_hsh.fetch("items").is_a?(Array)
          # Tuple-style array: different schema for each position
          schema_hsh.fetch("items").each_with_index do |item_schema, idx|
            constraints.item_by_idx[idx] = TypeConstraint.new(mthd: subtype_constrain, schema: item_schema)
          end
        elsif schema_hsh.fetch("items").is_a?(Hash)
          # Uniform array: same schema for all positions
          # Store for lazy constraint application
          constraints.item_rest = TypeConstraint.new(mthd: subtype_constrain, schema: schema_hsh.fetch("items"))
        else
          raise "unexpected"
        end
      end

      if schema_hsh.key?("additionalItems") && schema_hsh.fetch("additionalItems") != false
        # Schema for positions beyond those specified in tuple-style items
        constraints.item_rest = TypeConstraint.new(mthd: subtype_constrain, schema: schema_hsh.fetch("additionalItems"))
      end

      if schema_hsh.key?("contains")
        # At least one element must match this schema
        constraints.contains = TypeConstraint.new(mthd: subtype_constrain, schema: schema_hsh.fetch("contains"))
      end

      if schema_hsh.key?("unique")
        constraints.unique = true
      end

      if schema_hsh.key?("maxItems")
        constraints.max_size = schema_hsh.fetch("maxItems")
      end

      if schema_hsh.key?("minItems")
        constraints.min_size = schema_hsh.fetch("minItems")
      end

      if schema_hsh.key?("anyOf")
        raise "TODO: anyOf not yet implemented for array constraints"
      end

      if schema_hsh.key?("oneOf")
        raise "TODO: oneOf not yet implemented for array constraints"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO: noneOf not yet implemented for array constraints"
      end

      if schema_hsh.key?("if")
        raise "TODO: if/then/else not yet implemented for array constraints"
      end
      constraints
    end

    # Infer the parameter type from a JSON schema
    #
    # Examines the schema to determine if it represents a boolean, integer,
    # string, or array type. Uses multiple heuristics:
    # - Explicit "type" field
    # - Type of "const" value
    # - Type of "enum" values (must be homogeneous)
    # - Type inference from "allOf"/"anyOf" subschemas
    # - Known "$ref" patterns (uint32, uint64)
    #
    # @param schema_hsh [Hash] The JSON schema
    # @return [Symbol] One of :boolean, :int, :string, :array
    sig { params(schema_hsh: T::Hash[String, T.untyped]).returns(Symbol) }
    def self.detect_type(schema_hsh)
      if schema_hsh.key?("type")
        case schema_hsh["type"]
        when "boolean"
          :boolean
        when "integer"
          :int
        when "string"
          :string
        when "array"
          :array
        else
          raise "Unhandled JSON schema type"
        end
      elsif schema_hsh.key?("minimum") || schema_hsh.key?("maximum")
        :int
      elsif schema_hsh.key?("const")
        # Infer type from const value
        case schema_hsh["const"]
        when TrueClass, FalseClass
          :boolean
        when Integer
          :int
        when String
          :string
        else
          raise "Unhandled const type"
        end
      elsif schema_hsh.key?("enum")
        # Infer type from enum values (must be homogeneous)
        raise "Mixed types in enum" unless schema_hsh["enum"].all? { |e| e.class == schema_hsh["enum"].fetch(0).class }

        case schema_hsh["enum"].fetch(0)
        when TrueClass, FalseClass
          :boolean
        when Integer
          :int
        when String
          :string
        else
          raise "unhandled enum type"
        end
      elsif schema_hsh.key?("allOf")
        # Infer type from subschemas (must agree)
        subschema_types = schema_hsh.fetch("allOf").map { |subschema| detect_type(subschema) }

        if subschema_types.fetch(0) == :string
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :string }

          :string
        elsif subschema_types.fetch(0) == :boolean
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :boolean }

          :boolean
        elsif subschema_types.fetch(0) == :int
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :int }

          :int
        else
          raise "unhandled subschema type"
        end
      elsif schema_hsh.key?("anyOf")
        # Infer type from anyOf subschemas (must agree on type even if values differ)
        subschema_types = schema_hsh.fetch("anyOf").map { |subschema| detect_type(subschema) }

        if subschema_types.fetch(0) == :string
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :string }

          :string
        elsif subschema_types.fetch(0) == :boolean
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :boolean }

          :boolean
        elsif subschema_types.fetch(0) == :int
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t == :int }

          :int
        else
          raise "unhandled subschema type"
        end
      elsif schema_hsh.key?("$ref")
        case schema_hsh.fetch("$ref").split("/").last
        when "uint32", "uint64", "32bit_unsigned_pow2", "64bit_unsigned_pow2"
          :int
        else
          raise "unhandled ref: #{schema_hsh.fetch("$ref")}"
        end
      elsif schema_hsh.key?("not")
        # Type is same as negated schema
        detect_type(schema_hsh.fetch("not"))
      else
        raise "unhandled scalar schema:\n#{schema_hsh}"
      end
    end

    # Detect the element type of an array schema
    #
    # Examines the "items" field to determine what type of elements the array contains.
    # Handles both tuple-style (array of schemas) and uniform (single schema) arrays.
    #
    # @param schema_hsh [Hash] The JSON schema for an array
    # @return [Symbol] The element type (:boolean, :int, :string)
    sig { params(schema_hsh: T::Hash[String, T.untyped]).returns(Symbol) }
    def self.detect_array_subtype(schema_hsh)
      if schema_hsh.key?("items") && schema_hsh.fetch("items").is_a?(Array)
        # Tuple-style: use first element's type
        detect_type(schema_hsh.fetch("items")[0])
      elsif schema_hsh.key?("items")
        # Uniform: use the single schema's type
        detect_type(schema_hsh.fetch("items"))
      else
        raise "Can't detect array subtype"
      end
    end

    # Create a new parameter term with constraints from JSON schema
    #
    # This constructor:
    # 1. Detects the parameter type from the schema
    # 2. Creates an appropriate Z3 variable
    # 3. Applies all schema constraints as assertions
    #
    # @param name [String] The parameter name
    # @param solver [Z3Solver] The solver to add constraints to
    # @param schema_hsh [Hash] The JSON schema defining the parameter
    sig { params(name: String, solver: Z3Solver, schema_hsh: T::Hash[String, T.untyped]).void }
    def initialize(name, solver, schema_hsh)
      @name = name
      @solver = solver
      @type = T.let(Z3ParameterTerm.detect_type(schema_hsh), Symbol)

      @term = T.let(
        case @type
        when :int
          # Use 64-bit bitvector (width doesn't affect constraint solving, just makes it large enough)
          t = Z3.Bitvec(name, 64)
          Z3ParameterTerm.constrain_int(@solver, t, schema_hsh, name:)
          t
        when :boolean
          t = Z3.Bool(name)
          Z3ParameterTerm.constrain_bool(@solver, t, schema_hsh, name:)
          t
        when :string
          # Represent strings as integer hashes
          t = Z3.Int(name)
          Z3ParameterTerm.constrain_string(@solver, t, schema_hsh, name:)
          t
        when :array
          # Detect element type and create finite array
          subtype = Z3ParameterTerm.detect_array_subtype(schema_hsh)

          case subtype
          when :int
            constraints = Z3ParameterTerm.constrain_array(@solver, schema_hsh, Z3ParameterTerm.method(:constrain_int))
            Z3FiniteArray.new(@solver, name, Z3::BitvecSort, constraints, bitvec_width: 64)
          when :boolean
            constraints = Z3ParameterTerm.constrain_array(@solver, schema_hsh, Z3ParameterTerm.method(:constrain_bool))
            Z3FiniteArray.new(@solver, name, Z3::BoolSort, constraints)
          when :string
            constraints = Z3ParameterTerm.constrain_array(@solver, schema_hsh, Z3ParameterTerm.method(:constrain_string))
            Z3FiniteArray.new(@solver, name, Z3::IntSort, constraints)
          else
            raise "TODO: Unsupported array element type"
          end
        end,
        T.any(Z3::BoolExpr, Z3::IntExpr, Z3::BitvecExpr, Z3FiniteArray)
      )
    end

    sig { returns(Z3::IntExpr) }
    def size_term
      raise "Not an array parameter" unless @term.is_a?(Z3FiniteArray)
      @term.size_term
    end

    sig { params(msb: Integer, lsb: Integer).returns(Z3::BitvecExpr) }
    def extract(msb, lsb)
      T.cast(@term, Z3::BitvecExpr).extract(msb, lsb)
    end

    sig { params(idx: Integer).returns(T.any(Z3::BoolExpr, Z3::IntExpr, Z3::BitvecExpr)) }
    def [](idx)
      unless @term.is_a?(Z3FiniteArray)
        raise "#{@name} is not an array parameter"
      end
      @term[idx]
    end

    sig { params(val: T.any(Integer, T::Boolean, String, Z3::Expr)).returns(Z3::Expr) }
    def has_value?(val)
      unless @term.is_a?(Z3FiniteArray)
        raise "#{@name} is not an array parameter"
      end
      @term.has_value?(val)
    end

    sig { params(val: T.any(Integer, String, T::Boolean, T::Array[Integer], T::Array[String], T::Array[T::Boolean])).returns(Z3::BoolExpr) }
    def ==(val)
      case val
      when String
        # Compare string hashes
        T.cast(@term, Z3::IntExpr) == val.hash
      when Array
        T.cast(@term, Z3FiniteArray) == val
      else
        T.cast(@term, Z3::Expr) == val
      end
    end

    sig { params(val: T.any(Integer, String, T::Boolean, T::Array[Integer], T::Array[String], T::Array[T::Boolean])).returns(Z3::BoolExpr) }
    def !=(val)
      case val
      when String
        T.cast(@term, Z3::IntExpr) != val.hash
      when Array
        T.cast(@term, Z3FiniteArray) != val
      else
        T.cast(@term, Z3::Expr) != val
      end
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def <=(val)
      T.cast(@term, Z3::BitvecExpr).unsigned_le(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def <(val)
      T.cast(@term, Z3::BitvecExpr).unsigned_lt(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def >=(val)
      T.cast(@term, Z3::BitvecExpr).unsigned_ge(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def >(val)
      T.cast(@term, Z3::BitvecExpr).unsigned_gt(val)
    end

  end

  # Models a RISC-V extension requirement in Z3
  #
  # An extension requirement specifies that an extension must satisfy certain
  # version constraints (e.g., ">=1.0.0", "~>2.0"). This class:
  # 1. Finds all extension versions that satisfy the requirement
  # 2. Creates a Z3 boolean term representing the requirement
  # 3. Asserts that the requirement implies exactly one satisfying version is present
  #
  # The constraint logic ensures:
  # - If no versions satisfy the requirement, the requirement term implies false
  # - If versions exist, exactly one must be true (using XOR for mutual exclusivity)
  # - If a version is true, the requirement must be true (bidirectional implication)
  class Z3ExtensionRequirement
    extend T::Sig

    sig { params(name: String, req: T.any(RequirementSpec, T::Array[RequirementSpec]), solver: Z3Solver, cfg_arch: ConfiguredArchitecture).void }
    def initialize(name, req, solver, cfg_arch)
      @name = name
      @reqs = req
      @solver = solver

      @ext_req = T.let(cfg_arch.extension_requirement(name, @reqs), ExtensionRequirement)
      vers = @ext_req.satisfying_versions
      @term = T.let(
        Z3.Bool("#{name} #{@reqs.is_a?(Array) ? @reqs.map { |r| r.to_s }.join(", ") : @reqs.to_s}"),
        Z3::BoolExpr
      )
      if vers.empty?
        # No versions satisfy this requirement, so it can never be true
        @solver.assert @term.implies(Z3.False)
      else
        if vers.size == 1
          # Exactly one version satisfies: requirement iff that version
          @solver.assert @term.implies(@solver.ext_ver(name, vers.fetch(0).version_spec, cfg_arch).term)
        elsif vers.size == 2
          # Two versions: use XOR for mutual exclusivity
          @solver.assert @term.implies(T.unsafe(Z3).Xor(*vers.map { |v| @solver.ext_ver(name, v.version_spec, cfg_arch).term }))
        else
          # Multiple versions: ensure exactly one is true
          # XOR of all versions ensures an odd number are true
          uneven_number_is_true = T.unsafe(Z3).Xor(*vers.map { |v| @solver.ext_ver(name, v.version_spec, cfg_arch).term })
          # Pairwise exclusion ensures at most one is true
          max_one_is_true =
            T.unsafe(Z3).And(
              *vers.combination(2).map do |pair|
                # No two versions can both be true
                !(@solver.ext_ver(name, pair.fetch(0).version_spec, cfg_arch).term & @solver.ext_ver(name, pair.fetch(1).version_spec, cfg_arch).term)
              end
            )
          # Together: exactly one version is true
          @solver.assert @term.implies(uneven_number_is_true & max_one_is_true)
        end
      end
      # Bidirectional: if a version is present, the requirement is satisfied
      vers.each do |v|
        @solver.assert @solver.ext_ver(name, v.version_spec, cfg_arch).term.implies(@term)
      end
    end

    sig { returns(Z3::BoolExpr).checked(:never) }
    def term = @term
  end

  # Models a specific RISC-V extension version in Z3
  #
  # Represents a concrete extension version (e.g., "Zicsr@2.0.0") as:
  # - A boolean term indicating if this version is present
  # - Integer terms for major, minor, patch version components
  # - A boolean term for pre-release status
  #
  # The version term implies constraints on the component terms, allowing
  # version comparison operations (==, !=, <, <=, >, >=) to work correctly.
  class Z3ExtensionVersion
    extend T::Sig

    sig { returns(Z3::BoolExpr) }
    attr_reader :term

    sig { params(name: String, version: VersionSpec, solver: Z3Solver, cfg_arch: ConfiguredArchitecture).void }
    def initialize(name, version, solver, cfg_arch)
      @name = name
      @solver = T.let(solver, Z3Solver)
      @term = T.let(Z3::Bool("#{name}@#{version}"), Z3::BoolExpr)
      @major_term = T.let(solver.ext_major(name), Z3::IntExpr)
      @minor_term = T.let(solver.ext_minor(name), Z3::IntExpr)
      @patch_term = T.let(solver.ext_patch(name), Z3::IntExpr)
      @pre_term = T.let(solver.ext_pre(name), Z3::BoolExpr)

      # If this version is present, constrain the component terms
      @solver.assert @term.implies(
        Z3.And(
          @major_term == version.major,
          @minor_term == version.minor,
          @patch_term == version.patch,
          @pre_term == version.pre,
        )
      )
    end

    # Check version equality
    #
    # Compares all version components: major, minor, patch, and pre-release status
    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def ==(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term == ver_spec.patch), (@pre_term == ver_spec.pre))
    end

    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def !=(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      Z3.Or((@major_term != ver_spec.major), (@minor_term != ver_spec.minor), (@patch_term != ver_spec.patch), (@pre_term != ver_spec.pre))
    end

    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def >=(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      (self == ver) | (self > ver)
    end

    # Check if this version is greater than another
    #
    # Version comparison follows semantic versioning rules:
    # - Compare major, then minor, then patch
    # - Pre-release versions are less than release versions with same major.minor.patch
    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def >(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      e =
        Z3.Or(
          (@major_term > ver_spec.major),
          ((@major_term == ver_spec.major) & (@minor_term > ver_spec.minor)),
          Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term > ver_spec.patch))
        )
      # Handle pre-release comparison: if comparing to a pre-release, a release version is greater
      if ver_spec.pre
        e & Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term == ver_spec.patch), (!@pre_term))
      else
        e
      end
    end

    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def <=(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      (self == ver) | (self < ver)
    end

    # Check if this version is less than another
    #
    # Inverse of > with special handling for pre-release versions
    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def <(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      e =
        Z3.Or(
          (@major_term < ver_spec.major),
          ((@major_term == ver_spec.major) & (@minor_term < ver_spec.minor)),
          Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term < ver_spec.patch))
        )
      # Handle pre-release comparison: if comparing to a release, a pre-release version is less
      if ver_spec.pre
        e
      else
        e | Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term == ver_spec.patch), (@pre_term))
      end
    end
  end

  # Main Z3 solver wrapper for RISC-V architecture validation
  #
  # This class provides a high-level interface to Z3 for validating RISC-V
  # configurations. It manages:
  # - Parameter terms with JSON schema constraints
  # - Extension version terms
  # - Extension requirement terms
  # - Stack-based solver contexts (push/pop)
  #
  # The solver maintains caches of terms organized in stacks, allowing
  # incremental solving with backtracking via push/pop operations.
  class Z3Solver
    extend T::Sig
    extend Forwardable

    # Delegate common solver operations to the underlying Z3::Solver
    def_delegators :@solver,
      :assert, :assert_as,
      :prove!, :assertions,
      :check, :satisfiable?, :unsatisfiable?,
      :model

    sig { returns(Z3::Solver) }
    attr_reader :solver

    @parallel_enabled = T.let(nil, T.nilable(T::Boolean))

    class << self
      extend T::Sig

      sig { returns(T.nilable(T::Boolean)) }
      def parallel_enabled
        @parallel_enabled
      end

      sig { params(value: T.nilable(T::Boolean)).void }
      def parallel_enabled=(value)
        @parallel_enabled = value
      end

      sig { params(desired: T::Boolean).void }
      def configure_parallelization(desired)
        previous = parallel_enabled

        if !previous.nil? && previous != desired
          if desired
            Udb.logger.warn "Z3 parallelization was previously disabled, but is now being enabled"
          else
            Udb.logger.warn "Z3 parallelization was previously enabled, but is now being disabled"
          end
        end

        Z3.set_param("parallel.enable", desired ? "true" : "false")
        self.parallel_enabled = desired
      end
    end

    sig { void }
    def initialize
      if Udb.global_options.parallel_z3
        Z3Solver.configure_parallelization(true)
      else
        Z3Solver.configure_parallelization(false)
      end

      @solver = T.let(Z3::Solver.new, Z3::Solver)

      # Stacks for incremental solving with push/pop
      @ext_vers = T.let([{}], T::Array[T::Hash[Integer, Z3ExtensionVersion]])
      @ext_reqs = T.let([{}], T::Array[T::Hash[Integer, Z3ExtensionRequirement]])
      @param_terms = T.let([{}], T::Array[T::Hash[String, Z3ParameterTerm]])

      # Extension version component terms (shared across versions of same extension)
      @ext_majors = T.let([{}], T::Array[T::Hash[String, Z3::IntExpr]])
      @ext_minors = T.let([{}], T::Array[T::Hash[String, Z3::IntExpr]])
      @ext_patches = T.let([{}], T::Array[T::Hash[String, Z3::IntExpr]])
      @ext_pres = T.let([{}], T::Array[T::Hash[String, Z3::BoolExpr]])

      @xlen = T.let(nil, T.nilable(Z3::IntExpr))
    end

    # Pop a solver context level
    #
    # Removes the most recent push level, discarding all terms and assertions
    # added since that push. Raises an error if already at the base level.
    sig { void }
    def pop
      if @ext_vers.size == 1
        Udb.logger.error "Popping solver at base level"
        raise
      end
      @ext_vers.pop
      @ext_reqs.pop
      @param_terms.pop
      @ext_majors.pop
      @ext_minors.pop
      @ext_patches.pop
      @ext_pres.pop
      @solver.pop
    end

    # Push a new solver context level
    #
    # Creates a new scope for terms and assertions. All changes can be
    # undone with a corresponding pop operation.
    sig { void }
    def push
      @ext_vers.push({})
      @ext_reqs.push({})
      @param_terms.push({})
      @ext_majors.push({})
      @ext_minors.push({})
      @ext_patches.push({})
      @ext_pres.push({})
      @solver.push
    end

    # Get or create the XLEN term
    #
    # XLEN represents the base integer register width (32 or 64 bits).
    # This term is constrained to be either 32 or 64.
    sig { returns(Z3::IntExpr) }
    def xlen
      unless @xlen
        @xlen = Z3.Int("xlen")
        @solver.assert_as((@xlen == 32) | (@xlen == 64), "_pxlen")
      end
      @xlen
    end

    # Get or create an extension version term
    #
    # Returns a cached term if it exists, otherwise creates a new one.
    # The term is stored in the current context level.
    sig { params(name: String, version: T.any(String, VersionSpec), cfg_arch: ConfiguredArchitecture).returns(Z3ExtensionVersion) }
    def ext_ver(name, version, cfg_arch)
      version_spec = version.is_a?(VersionSpec) ? version : VersionSpec.new(version)
      key = [name, version_spec].hash
      # Search from most recent context backwards
      @ext_vers.reverse_each do |h|
        if h.key?(key)
          return h.fetch(key)
        end
      end
      # Create new term in current context
      ev = Z3ExtensionVersion.new(name, version_spec, self, cfg_arch)
      T.must(@ext_vers.last)[key] = ev
      ev
    end

    # Get or create an extension requirement term
    #
    # Returns a cached term if it exists, otherwise creates a new one.
    sig { params(name: String, req: T.any(RequirementSpec, T::Array[RequirementSpec]), cfg_arch: ConfiguredArchitecture).returns(Z3ExtensionRequirement) }
    def ext_req(name, req, cfg_arch)
      key = [name, req].hash
      @ext_reqs.reverse_each do |h|
        if h.key?(key)
          return h.fetch(key)
        end
      end
      T.must(@ext_reqs.last)[key] ||= Z3ExtensionRequirement.new(name, req, self, cfg_arch)
    end

    # Get or create the major version term for an extension
    #
    # All versions of the same extension share these component terms.
    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_major(name)
      @ext_majors.reverse_each do |h|
        if h.key?(name)
          return h.fetch(name)
        end
      end
      T.must(@ext_majors.last)[name] ||= Z3.Int("#{name}_major")
    end

    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_minor(name)
      @ext_minors.reverse_each do |h|
        if h.key?(name)
          return h.fetch(name)
        end
      end
      T.must(@ext_minors.last)[name] ||= Z3.Int("#{name}_minor")
    end

    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_patch(name)
      @ext_patches.reverse_each do |h|
        if h.key?(name)
          return h.fetch(name)
        end
      end
      T.must(@ext_patches.last)[name] ||= Z3.Int("#{name}_patch")
    end

    sig { params(name: String).returns(Z3::BoolExpr) }
    def ext_pre(name)
      @ext_pres.reverse_each do |h|
        if h.key?(name)
          return h.fetch(name)
        end
      end
      T.must(@ext_pres.last)[name] ||= Z3.Bool("#{name}_pre")
    end


    # Get or create a parameter term with JSON schema constraints
    #
    # Returns a cached term if it exists, otherwise creates a new one
    # with all schema constraints applied.
    sig { params(name: String, schema_hsh: T::Hash[String, T.untyped]).returns(Z3ParameterTerm) }
    def param(name, schema_hsh)
      @param_terms.reverse_each do |h|
        if h.key?(name)
          return h.fetch(name)
        end
      end
      T.must(@param_terms.last)[name] = Z3ParameterTerm.new(name, self, schema_hsh)
    end
  end
end
