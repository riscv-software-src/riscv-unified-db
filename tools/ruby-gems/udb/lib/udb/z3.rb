# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "forwardable"
require "sorbet-runtime"
require "udb/version_spec"
require "z3"

module Udb
  class Z3Sovler; end

  # Arrays in Z3 are unbounded, but we need to occasionally represent the length of an array
  # therefore, we use this class to model a finite-sized array as a size plus constiuent scalars
  class Z3FiniteArray
    extend T::Sig

    sig { params(solver: Z3Solver, name: String, sort: T.any(T.class_of(Z3::IntSort), T.class_of(Z3::BoolSort), T.class_of(Z3::BitvecSort)), max_n: Integer, bitvec_width: T.nilable(Integer)).void }
    def initialize(solver, name, sort, max_n, bitvec_width: nil)
      @subtype_sort = sort
      @solver = solver
      @items = T.let([], T::Array[T.nilable(T.any(Z3::BitvecExpr, Z3::IntExpr, Z3::BoolExpr))])
      @size = Z3.Int("#{@name}_size")
      @max_size = max_n
      @bitvec_width = bitvec_width
    end

    sig { params(idx: Integer).returns(T.any(Z3::BitvecExpr, Z3::IntExpr, Z3::BoolExpr)) }
    def [](idx)
      T.must(
        @items[idx] ||=
          begin
            @solver.assert @size >= idx
            if @subtype_sort == Z3::BitvecSort
              @subtype_sort.new(T.must(@bitvec_width)).var("#{@name}_i#{idx}")
            else
              @subtype_sort.new.var("#{@name}_i#{idx}")
            end
          end
      )
    end

    def size_term = @size

    def max_size = @max_size
  end

  # represent a parameter in Z3
  # There will only ever be one parameter term per parameter
  # When a parameter term is constructed, it adds all relevant assertions to the solver
  class Z3ParameterTerm
    extend T::Sig

    # assert all constraints for an integer parameter
    sig { params(solver: Z3Solver, term: Z3::BitvecExpr, schema_hsh: T::Hash[String, T.untyped]).void }
    def self.constrain_int(solver, term, schema_hsh)
      if schema_hsh.key?("const")
        solver.assert(term == schema_hsh.fetch("const"))
      end

      if schema_hsh.key?("enum")
        expr = (term == schema_hsh.fetch("enum")[0])
        schema_hsh.fetch("enum")[1..].each do |v|
          expr = expr | (term == v)
        end
        solver.assert expr
      end

      if schema_hsh.key?("minimum")
        solver.assert term.unsigned_ge(schema_hsh.fetch("minimum"))
      end

      if schema_hsh.key?("maximum")
        solver.assert term.unsigned_le(schema_hsh.fetch("maximum"))
      end

      if schema_hsh.key?("allOf")
        constrain_int(solver, term, schema_hsh.fetch("allOf"))
      end

      if schema_hsh.key?("anyOf")
        raise "TODO"
      end

      if schema_hsh.key?("oneOf")
        raise "TODO"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO"
      end

      if schema_hsh.key?("if")
        raise "TODO"
      end

      if schema_hsh.key?("$ref")
        if schema_hsh.fetch("$ref").split("/").last == "uint32"
          solver.assert((term == 0) | (0 == (term & (term - 1))))
          solver.assert((term.unsigned_gt(0)) & (term.unsigned_le(2**32 - 1)))
        elsif schema_hsh.fetch("$ref").split("/").last == "uint64"
          solver.assert((term == 0) | (0 == (term & (term - 1))))
          solver.assert((term.unsigned_gt(0)) & (term.unsigned_le(2**64 - 1)))
        else
          raise "Unhandled schema $ref: #{schema_hsh.fetch("$ref")}"
        end
      end
    end

    # assert all constraints for a boolean parameter
    sig { params(solver: Z3Solver, term: Z3::BoolExpr, schema_hsh: T::Hash[String, T.untyped]).void }
    def self.constrain_bool(solver, term, schema_hsh)
      if schema_hsh.key?("const")
        solver.assert(term == schema_hsh.fetch("const"))
      end

      if schema_hsh.key?("allOf")
        constrain_bool(solver, term, schema_hsh.fetch("allOf"))
      end

      if schema_hsh.key?("anyOf")
        raise "TODO"
      end

      if schema_hsh.key?("oneOf")
        raise "TODO"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO"
      end

      if schema_hsh.key?("if")
        raise "TODO"
      end
    end

    def self.constrain_string(solver, term, schema_hsh)
      if schema_hsh.key?("const")
        solver.assert(term == schema_hsh.fetch("const").hash)
      end

      if schema_hsh.key?("enum")
        expr = (term == schema_hsh.fetch("enum")[0].hash)
        schema_hsh.fetch("enum")[1..].each do |v|
          expr = expr | (term == v.hash)
        end
        solver.assert expr
      end

      if schema_hsh.key?("anyOf")
        raise "TODO"
      end

      if schema_hsh.key?("oneOf")
        raise "TODO"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO"
      end

      if schema_hsh.key?("if")
        raise "TODO"
      end
    end

    # assert all constraints for an array parameter
    sig {
      params(
        solver: Z3Solver,
        term: Z3FiniteArray,
        schema_hsh: T::Hash[String, T.untyped],
        subtype_constrain: Method
      ).void
    }
    def self.constrain_array(solver, term, schema_hsh, subtype_constrain)
      if schema_hsh.key?("items")
        if schema_hsh.fetch("items").is_a?(Array)
          schema_hsh.fetch("items").each_with_index do |item_schema, idx|
            t = term[idx]
            subtype_constrain.call(solver, t, item_schema)
          end
        elsif schema_hsh.fetch("items").is_a?(Hash)
          max = schema_hsh.fetch("maxItems")
          (0..max).each do |idx|
            subtype_constrain.call(solver, term[idx], schema_hsh.fetch("items"))
          end
        else
          raise "unexpected"
        end
      end

      if schema_hsh.key?("additionalItems") && schema_hsh.fetch("additionalItems") != false
        min = 0
        max = nil
        if schema_hsh.key?("items")
          min = schema_hsh.fetch("items").size
        end
        if schema_hsh.key?("minItems")
          min = schema_hsh.fetch("minItems")
        end
        if schema_hsh.key?("maxItems")
          max = schema_hsh.fetch("maxItems")
        end
        raise "No max" if max.nil?

        ((min - 1)...max).each do |idx|
          subtype_constrain.call(solver, term[idx], schema_hsh.fetch("additionalItems"))
        end
      end

      if schema_hsh.key?("contains")
        max = schema_hsh.fetch("maxItems")
        subtype_constrain.call(solver, term[0], schema_hsh.fetch("contains"))
        (1..max).each do |i|
          subtype_constrain.call(solver, term[i], schema_hsh.fetch("contains"))
        end
      end

      if schema_hsh.key?("unique")
        max = schema_hsh.fetch("maxItems")
        Z3.Distinct(max.times.map { |i| term[i] })
      end

      if schema_hsh.key?("anyOf")
        raise "TODO"
      end

      if schema_hsh.key?("oneOf")
        raise "TODO"
      end

      if schema_hsh.key?("noneOf")
        raise "TODO"
      end

      if schema_hsh.key?("if")
        raise "TODO"
      end
    end

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
      elsif schema_hsh.key?("const")
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
      elsif schema_hsh.key?("$ref")
        if schema_hsh.fetch("$ref") == "schema_defs.json#/$defs/uint32"
          :int
        elsif schema_hsh.fetch("$ref") == "schema_defs.json#/$defs/uint64"
          :int
        else
          raise "unhandled ref: #{schema_hsh.fetch("$ref")}"
        end
      elsif schema_hsh.key?("not")
        detect_type(schema_hsh.fetch("not"))
      else
        raise "unhandled scalar schema:\n#{schema_hsh}"
      end
    end

    sig { params(schema_hsh: T::Hash[String, T.untyped]).returns(Symbol) }
    def self.detect_array_subtype(schema_hsh)
      if schema_hsh.key?("items") && schema_hsh.fetch("items").is_a?(Array)
        detect_type(schema_hsh.fetch("items")[0])
      elsif schema_hsh.key?("items")
        detect_type(schema_hsh.fetch("items"))
      else
        raise "Can't detect array subtype"
      end
    end

    sig { params(name: String, solver: Z3Solver, schema_hsh: T::Hash[String, T.untyped]).void }
    def initialize(name, solver, schema_hsh)
      @name = name
      @solver = solver

      case Z3ParameterTerm.detect_type(schema_hsh)
      when :int
        @term = Z3.Bitvec(name, 64)   # width doesn't matter here, so just make it large
        Z3ParameterTerm.constrain_int(@solver, @term, schema_hsh)
      when :boolean
        @term = Z3.Bool(name)
        Z3ParameterTerm.constrain_bool(@solver, @term, schema_hsh)
      when :string
        @term = Z3.Int(name)
        Z3ParameterTerm.constrain_string(@solver, @term, schema_hsh)
      when :array
        case Z3ParameterTerm.detect_array_subtype(schema_hsh)
        when :int
          @term = Z3FiniteArray.new(@solver, name, Z3::BitvecSort, schema_hsh.fetch("maxItems"), bitvec_width: 64)
          Z3ParameterTerm.constrain_array(@solver, @term, schema_hsh, Z3ParameterTerm.method(:constrain_int))
        when :boolean
          @term = Z3FiniteArray.new(@solver, name, Z3::BoolSort, schema_hsh.fetch("maxItems"))
          Z3ParameterTerm.constrain_array(@solver, @term, schema_hsh, Z3ParameterTerm.method(:constrain_bool))
        when :string
          @term = Z3FiniteArray.new(@solver, name, Z3::IntSort, schema_hsh.fetch("maxItems"))
          Z3ParameterTerm.constrain_array(@solver, @term, schema_hsh, Z3ParameterTerm.method(:constrain_string))
        else
          raise "TODO"
        end
        @idx_term = Z3.Int("#{name}_idx")
        @max_items = schema_hsh.fetch("maxItems")
        solver.assert @idx_term >= 0
        solver.assert @idx_term < @max_items
      end
    end

    sig { returns(Integer) }
    def max_items = @max_items

    sig { returns(Z3::IntExpr) }
    def idx_term
      @idx_term
    end

    sig { returns(Z3::IntExpr) }
    def size_term
      @term.size_term
    end

    sig { params(msb: Integer, lsb: Integer).returns(Z3::BitvecExpr) }
    def extract(msb, lsb)
      @term.extract(msb, lsb)
    end

    sig { params(idx: Integer).returns(T.any(Z3::BoolExpr, Z3::IntExpr, Z3::BitvecExpr)) }
    def [](idx)
      @term[idx]
    end

    sig { params(val: T.any(Integer, String, T::Boolean)).returns(Z3::BoolExpr) }
    def ==(val)
      if val.is_a?(String)
        @term == val.hash
      else
        @term == val
      end
    end

    sig { params(val: T.any(Integer, String, T::Boolean)).returns(Z3::BoolExpr) }
    def !=(val)
      if val.is_a?(String)
        @term != val.hash
      else
        @term != val
      end
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def <=(val)
      @term.unsigned_le(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def <(val)
      @term.unsigned_lt(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def >=(val)
      @term.unsigned_ge(val)
    end

    sig { params(val: Integer).returns(Z3::BoolExpr) }
    def >(val)
      @term.unsigned_gt(val)
    end

  end

  class Z3ExtensionRequirement
    extend T::Sig

    sig { params(name: String, req: T.any(RequirementSpec, T::Array[RequirementSpec]), solver: Z3Solver, cfg_arch: ConfiguredArchitecture).void }
    def initialize(name, req, solver, cfg_arch)
      @name = name
      @reqs = req
      @solver = solver

      @ext_req = cfg_arch.extension_requirement(name, @reqs)
      vers = @ext_req.satisfying_versions
      @term = Z3.Bool("#{name} #{@reqs.is_a?(Array) ? @reqs.map { |r| r.to_s }.join(", ") : @reqs.to_s}")
      if vers.empty?
        @solver.assert @term.implies(Z3.False)
      else
        if vers.size == 1
          @solver.assert @term.implies(@solver.ext_ver(name, vers.fetch(0).version_spec, cfg_arch).term)
        elsif vers.size == 2
          @solver.assert @term.implies(T.unsafe(Z3).Xor(*vers.map { |v| @solver.ext_ver(name, v.version_spec, cfg_arch).term }))
        else
          uneven_number_is_true = T.unsafe(Z3).Xor(*vers.map { |v| @solver.ext_ver(name, v.version_spec, cfg_arch).term })
          max_one_is_true =
            T.unsafe(Z3).And(
              *vers.combination(2).map do |pair|
                !(@solver.ext_ver(name, pair.fetch(0).version_spec, cfg_arch).term & @solver.ext_ver(name, pair.fetch(1).version_spec, cfg_arch).term)
              end
            )
          @solver.assert @term.implies(uneven_number_is_true & max_one_is_true)
        end
      end
      vers.each do |v|
        @solver.assert @solver.ext_ver(name, v.version_spec, cfg_arch).term.implies(@term)
      end
    end

    sig { returns(Z3::BoolExpr).checked(:never) }
    def term = @term
  end

  class Z3ExtensionVersion
    extend T::Sig

    sig { returns(Z3::BoolExpr) }
    attr_reader :term

    sig { params(name: String, version: VersionSpec, solver: Z3Solver, cfg_arch: ConfiguredArchitecture).void }
    def initialize(name, version, solver, cfg_arch)
      @name = name
      @solver = solver
      @term = Z3::Bool("#{name}@#{version}")
      @major_term = solver.ext_major(name)
      @minor_term = solver.ext_minor(name)
      @patch_term = solver.ext_patch(name)
      @pre_term = solver.ext_pre(name)

      @solver.assert @term.implies(
        Z3.And(
          @major_term == version.major,
          @minor_term == version.minor,
          @patch_term == version.patch,
          @pre_term == version.pre,
        )
      )
    end

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

    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def >(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      e =
        Z3.Or(
          (@major_term > ver_spec.major),
          ((@major_term == ver_spec.major) & (@minor_term > ver_spec.minor)),
          Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term > ver_spec.patch))
        )
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

    sig { params(ver: T.any(String, VersionSpec)).returns(Z3::BoolExpr) }
    def <(ver)
      ver_spec = ver.is_a?(VersionSpec) ? ver : VersionSpec.new(ver)

      e =
        Z3.Or(
          (@major_term < ver_spec.major),
          ((@major_term == ver_spec.major) & (@minor_term < ver_spec.minor)),
          Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term < ver_spec.patch))
        )
      if ver_spec.pre
        e
      else
        e & Z3.And((@major_term == ver_spec.major), (@minor_term == ver_spec.minor), (@patch_term == ver_spec.patch), (@pre_term))
      end
    end
  end

  class Z3Solver
    extend T::Sig
    extend Forwardable

    def_delegators :@solver,
      :assert,
      :prove!, :assertions,
      :check, :satisfiable?, :unsatisfiable?,
      :model,
      :push

    def initialize
      @solver = Z3::Solver.new
      @ext_vers = T.let({}, T::Hash[String, Z3ExtensionVersion])
      @ext_reqs = T.let({}, T::Hash[String, Z3ExtensionRequirement])
      @param_terms = T.let({}, T::Hash[String, Z3ParameterTerm])

      @ext_majors = T.let({}, T::Hash[String, Z3::IntExpr])
      @ext_minors = T.let({}, T::Hash[String, Z3::IntExpr])
      @ext_patches = T.let({}, T::Hash[String, Z3::IntExpr])
      @ext_pres = T.let({}, T::Hash[String, Z3::IntExpr])
    end

    def pop
      @ext_vers.clear
      @ext_reqs.clear
      @ext_majors.clear
      @ext_minors.clear
      @ext_patches.clear
      @ext_pres.clear
      @solver.pop
    end

    sig { returns(Z3::IntExpr) }
    def xlen
      unless @xlen
        @xlen = Z3.Int("xlen")
        @solver.assert((@xlen == 32) | (@xlen == 64))
      end
      @xlen
    end

    sig { params(name: String, version: T.any(String, VersionSpec), cfg_arch: ConfiguredArchitecture).returns(Z3ExtensionVersion) }
    def ext_ver(name, version, cfg_arch)
      version_spec = version.is_a?(VersionSpec) ? version : VersionSpec.new(version)
      key = [name, version_spec].hash
      if @ext_vers.key?(key)
        @ext_vers.fetch(key)
      else
        @ext_vers[key] = Z3ExtensionVersion.new(name, version_spec, self, cfg_arch)
      end
    end

    sig { params(name: String, req: T.any(RequirementSpec, T::Array[RequirementSpec]), cfg_arch: ConfiguredArchitecture).returns(Z3ExtensionRequirement) }
    def ext_req(name, req, cfg_arch)
      key = [name, req].hash
      @ext_reqs[key] ||= Z3ExtensionRequirement.new(name, req, self, cfg_arch)
    end

    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_major(name)
      @ext_majors[name] ||= Z3.Int("#{name}_major")
    end

    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_minor(name)
      @ext_minors[name] ||= Z3.Int("#{name}_minor")
    end

    sig { params(name: String).returns(Z3::IntExpr) }
    def ext_patch(name)
      @ext_patches[name] ||= Z3.Int("#{name}_patch")
    end

    sig { params(name: String).returns(Z3::BoolExpr) }
    def ext_pre(name)
      @ext_pres[name] ||= Z3.Bool("#{name}_pre")
    end


    sig { params(name: String, schema_hsh: T::Hash[String, T.untyped]).returns(Z3ParameterTerm) }
    def param(name, schema_hsh)
      if @param_terms.key?(name)
        @param_terms.fetch(name)
      else
        @param_terms[name] = Z3ParameterTerm.new(name, self, schema_hsh)
      end
    end
  end
end
