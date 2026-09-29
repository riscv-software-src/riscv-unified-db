# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module Idl

  class AstNode; end
  class EnumDefinitionAst < AstNode; end
  class Type; end
  class EnumerationType < Type; end
  module Csr
    include Kernel
  end

  # Data types
  class Type
    extend T::Sig

    KINDS = [
      :void,     # empty
      :boolean,  # true or false, not compatible with bits/int/xreg
      :bits,     # integer with compile-time-known bit width
      :enum,     # enumeration class
      :enum_ref, # reference to an enumeration element, convertible to int and/or Bits<bit_width(MAX_ENUM_VALUE)>
      :bitfield, # bitfield, convertible to int and/or Bits<width>
      :struct,   # structure class
      :array,    # array of other types
      :tuple,    # tuple of other dissimilar types
      :function, # function
      :csr,      # a CSR register type
      :dontcare, # matches everything
      :string    # fixed-length character string
    ].freeze
    QUALIFIERS = [
      :const,
      :signed,
      :global,
      :known
    ].freeze

    # true for any type that can generally be treated as a scalar integer
    sig { returns(T::Boolean) }
    def integral?
      @kind == :bits
    end

    def ==(other)
      return false unless other.is_a?(Type)

      case other.kind
      when :bits
        @kind == :bits && @width == other.width
      when :enum_ref
        @kind == :enum_ref && T.must(@enum_class).name == other.name
      else
        raise "TODO: Type == for #{other.kind}"
      end
    end

    def runtime?
      if @kind == :array
        T.must(@sub_type).runtime?
      else
        @kind == :bits && !@width.is_a?(Integer)
      end
    end

    def default
      case @kind
      when :bits, :bitfield
        0
      when :boolean
        false
      when :array
        if @width == :unknown
          Array.new
        else
          Array.new(T.cast(@width, Integer), sub_type.default)
        end
      when :string
        ""
      when :enum_ref
        T.must(@enum_class).element_values.min
      when :enum
        raise "?"
      else
        raise "No default for #{@kind}"
      end
    end

    sig { returns(Symbol) }
    attr_reader :kind

    sig { returns(T::Array[Symbol]) }
    attr_reader :qualifiers

    sig { returns(T.any(Integer, Symbol)) }
    def width = T.must(@width)

    sig { returns(T.nilable(AstNode)) }
    attr_reader :width_ast

    sig { returns(T.nilable(Integer)) }
    attr_reader :max_width

    sig { returns(Type) }
    def sub_type = T.must(@sub_type)

    sig { returns(T::Array[Type]) }
    def tuple_types = T.must(@tuple_types)

    sig { returns(EnumerationType) }
    def enum_class = T.must(@enum_class)

    def qualify(qualifier)
      @qualifiers << qualifier
      @qualifiers.uniq!
      self
    end

    def self.from_typename(type_name, cfg_arch)
      case type_name
      when "XReg"
        return Type.new(:bits, width: cfg_arch.param_values.key?("MXLEN") ? cfg_arch.param_values.fetch("MXLEN") : :unknown, max_width: 64)
      when /Bits<((?:0x)?[0-9a-fA-F]+)>/
        Type.new(:bits, width: $1.to_i)
      end
    end

    sig {
      params(
        kind: Symbol,
        qualifiers: T::Array[Symbol],
        width: T.nilable(T.any(Integer, Symbol)),
        width_ast: T.nilable(AstNode),
        max_width: T.nilable(Integer),
        sub_type: T.nilable(Type),
        name: T.nilable(String),
        tuple_types: T.nilable(T::Array[Type]),
        return_type: T.nilable(Type),
        enum_class: T.nilable(EnumerationType),
        csr: T.nilable(Csr)
      )
      .void
    }
    def initialize(kind, qualifiers: [], width: nil, width_ast: nil, max_width: nil, sub_type: nil, name: nil, tuple_types: nil, return_type: nil, enum_class: nil, csr: nil)
      raise "Invalid kind '#{kind}'" unless KINDS.include?(kind)

      @kind = kind
      raise "Invalid qualifier" unless qualifiers.intersection(QUALIFIERS) == qualifiers

      @qualifiers = qualifiers
      # raise "#{width.class.name}" if (kind == :bits && !width.is_a?(Integer))

      raise "Should be a FunctionType" if kind == :function && !self.is_a?(FunctionType)

      @width = width
      @width_ast = width_ast
      @max_width = max_width
      @sub_type = sub_type
      raise "Tuples need a type list" if kind == :tuple && tuple_types.nil?
      @tuple_types = tuple_types
      @enum_class = enum_class
      @name = name
      if kind == :bits
        raise "Bits type must have width" unless @width
        raise "Bits type must have positive width (has #{@width})" unless @width == :unknown || T.cast(@width, Integer).positive?
      end
      if kind == :enum
        raise "Enum type must have width" unless @width
      end
      if kind == :array && width != 0
        raise "Array must have a subtype" unless @sub_type
      end
      if kind == :csr
        raise "CSR type must have a csr argument" if csr.nil?

        @csr = csr
        raise "CSR types must have a width" if width.nil?

        @width = width
      end
    end
    TYPE_FROM_KIND = [:boolean, :void, :dontcare].map { |k| [k, Type.new(k)] }.to_h.freeze

    def clone
      Type.new(
        @kind,
        qualifiers: @qualifiers.map(&:clone),
        width: @width,
        sub_type: @sub_type&.clone,
        name: @name.dup,
        tuple_types: @tuple_types&.map(&:clone),
        enum_class: @enum_class&.clone,
        csr: @csr
      )
    end

    # returns true if 'type' can be compared (e.g., >=, <, etc) to self
    # 'type' can be a Type object or a kind (as a Symbol)
    def comparable_to?(type)
      if type.is_a?(Symbol)
        raise "#{type} is not a kind" unless KINDS.include?(type)

        type = Type.new(type)
      end

      case @kind
      when :boolean
        return type.kind == :boolean
      when :enum_ref
        return \
          (type.kind == :enum_ref && type.enum_class.name == T.must(@enum_class).name) \
          || (type.kind == :enum && type.name == T.must(@enum_class).name)
      when :bits
        return type.convertable_to?(self) && (signed? == type.signed?)
      when :enum
        return type.convertable_to?(:bits)
      when :function
        # functions are not comparable to anything
        return false
      when :csr
        return ((type.kind == :csr) && (type.csr.name == @csr.name)) ||
              type.convertable_to?(Type.new(:bits, width: type.csr.width))
      when :string
        return type.kind == :string
      else
        raise "unimplemented #{@kind}"
      end
    end

    # returns true if identical to type, excluding qualifiers
    def equal_to?(type)
      if type.is_a?(Symbol)
        raise "#{type} is not a kind" unless KINDS.include?(type)

        type = TYPE_FROM_KIND[type]
      end

      case @kind
      when :boolean
        type.kind == :boolean
      when :enum_ref
        type.kind == :enum_ref && type.name == T.must(@enum_class).name
      when :dontcare
        true
      when :bits
        type.kind == :bits && type.width == @width
      when :string
        type.kind == :string && type.width == @width
      when :array
        type.kind == :array && type.sub_type.equal_to?(@sub_type)
      when :struct
        type.kind == :struct && (T.cast(type, StructType).type_name == T.cast(self, StructType).type_name)
      else
        raise "unimplemented type '#{@kind}'"
      end
    end

    # given an N-dimensional array type, return the primitive type
    def ary_type(ary)
      if ary.sub_type == :array
        ary_type(ary.sub_type)
      else
        ary.sub_type
      end
    end

    # returns true if self can be converted to 'type'
    # 'type' can be a Type object or a kind (as a Symbol)
    def convertable_to?(type)
      if type.is_a?(Symbol)
        raise "#{type} is not a kind" unless KINDS.include?(type)

        type = TYPE_FROM_KIND[type]
      end

      case @kind
      when :boolean
        return type.kind == :boolean
      when :enum_ref
        return \
          (type.kind == :enum && type.name == T.must(@enum_class).name) || \
          (type.kind == :enum_ref && type.enum_class.name == T.must(@enum_class).name)
      when :dontcare
        return true
      when :bits
        if type.kind == :enum_ref
          warn "You seem to be missing an $enum cast"
          return false
        end
        return type.kind == :bits || type.kind == :bitfield
      when :enum
        if type.kind == :bits
          return false
          # return (type.width == :unknown) || (width <= type.width)
        elsif type.kind == :enum
          return type.enum_class == enum_class
        else
          return false
        end
      when :tuple
        is_tuple_of_same_size = (type.kind == :tuple) && (T.must(@tuple_types).size == type.tuple_types.size)
        if is_tuple_of_same_size
          T.must(@tuple_types).each_index do |i|
            unless T.must(@tuple_types).fetch(i).convertable_to?(type.tuple_types.fetch(i))
              return false
            end
          end
          return true
        else
          return false
        end
      when :csr
        return (type.kind == :csr && type.csr.name == @csr.name) || type.convertable_to?(Type.new(:bits, width:))
      when :bitfield
        if (type.kind == :bitfield && name == type.name)
          return true
        elsif (type.kind == :bits && type.width == @width)
          return true
        else
          # be strict with bitfields -- only accept integrals that are exact width Bit types
          return false
        end
      when :array
        return type.kind == :array && type.sub_type.convertable_to?(sub_type) && type.width == @width
      when :string
        return type.kind == :string
      when :void
        return type.kind == :void
      when :struct
        return type.kind == :struct && (T.cast(type, StructType).name == T.cast(self, StructType).type_name)
      else
        raise "unimplemented type '#{@kind}'"
      end
    end

    # return IDL representation of the type
    sig { returns(String) }
    def to_idl
      case @kind
      when :bits
        if @width == :unknown
          raise "Cannot generate an IDL type with an unknown width"
        end
        if signed?
          raise "Cannot directly represent a signed bits"
        else
          "Bits<#{@width}>"
        end
      when :string
        "String"
      when :boolean
        "Boolean"
      else
        raise "TODO"
      end
    end

    def to_s
      ((@qualifiers.empty?) ? "" : "#{@qualifiers.map(&:to_s).join(' ')} ") + \
        if @kind == :bits
          "Bits<#{@width}>"
        elsif @kind == :enum
          "enum definition #{@name}"
        elsif @kind == :boolean
          "Boolean"
        elsif @kind == :enum_ref
          "enum #{T.must(@enum_class).name}"
        elsif @kind == :tuple
          "(#{T.must(@tuple_types).map { |t| t.to_s }.join(',')})"
        elsif @kind == :bitfield
          "bitfield #{@name}"
        elsif @kind == :array
          "array of #{@sub_type}"
        elsif @kind == :csr
          "CSR[#{@csr.name}]"
        elsif @kind == :void
          "void"
        elsif @kind == :string
          "string"
        elsif @kind == :struct
          "struct #{T.cast(self, StructType).type_name}"
        elsif @kind == :function
          "function #{name}"
        else
          raise @kind.to_s
        end
    end
    alias fully_qualified_name to_s

    def name
      if @kind == :bits
        "Bits<#{@width}>"
      elsif @kind == :enum
        @name
      elsif @kind == :bitfield
        @name
      elsif @kind == :function
        @name
      elsif @kind == :csr
        @csr.name
      elsif @kind == :enum_ref
        T.must(@enum_class).name
      else
        raise @kind.to_s
      end
    end

    def ary?
      @kind == :array
    end

    def const?
      @qualifiers.include?(:const)
    end

    def mutable?
      !const?
    end

    def signed?
      @qualifiers.include?(:signed)
    end

    def global?
      @qualifiers.include?(:global)
    end

    def known?
      @qualifiers.include?(:known)
    end

    def make_signed
      @qualifiers.append(:signed).uniq!
      self
    end

    # make this Type constant, and return self
    sig { returns(Type) }
    def make_const!
      @qualifiers.append(:const).uniq!
      self
    end

    # make a clone of this Type, add a constant qualifier, and return the new type
    sig { returns(Type) }
    def make_const
      new_t = clone
      new_t.make_const!
    end

    def make_global
      @qualifiers.append(:global).uniq!
      self
    end

    def make_known
      @qualifiers.append(:known).uniq!
      self
    end

    sig { params(value: Integer).returns(Integer) }
    def self.unsigned_bits_needed(value)
      raise "unsigned JSON schema integer cannot be negative" if value.negative?

      value.zero? ? 1 : value.bit_length
    end
    private_class_method :unsigned_bits_needed

    # @return [Idl::Type] Type of a scalar
    # @param schema [Hash] JSON Schema description of a scalar
    sig { params(schema: T::Hash[String, T.untyped]).returns(T.nilable(Type)) }
    def self.from_json_schema_scalar_type(schema)
      if schema.key?("type")
        case schema["type"]
        when "boolean"
          Type.new(:boolean)
        when "integer"
          if schema.key?("enum")
            Type.new(:bits, width: schema["enum"].map { |e| unsigned_bits_needed(e) }.max)
          elsif schema.key?("maximum")
            Type.new(:bits, width: unsigned_bits_needed(schema["maximum"]))
          else
            Type.new(:bits, width: 128)
          end
        when "string"
          if schema.key?("enum")
            Type.new(:string, width: schema["enum"].map(&:length).max)
          else
            Type.new(:string, width: 4096)
          end
        else
          raise "Unhandled JSON schema type"
        end
      elsif schema.key?("const")
        case schema["const"]
        when TrueClass, FalseClass
          Type.new(:boolean)
        when Integer
          Type.new(:bits, width: unsigned_bits_needed(schema["const"]))
        when String
          Type.new(:string, width: schema["const"].length)
        else
          raise "Unhandled const type"
        end
      elsif schema.key?("enum")
        raise "Mixed types in enum" unless schema["enum"].all? { |e| e.class == schema["enum"].fetch(0).class }

        case schema["enum"].fetch(0)
        when TrueClass, FalseClass
          Type.new(:boolean)
        when Integer
          Type.new(:bits, width: schema["enum"].map { |e| unsigned_bits_needed(e) }.max)
        when String
          Type.new(:string, width: schema["enum"].map { |e| e.length }.max)
        else
          raise "unhandled enum type"
        end
      elsif schema.key?("allOf")
        subschema_types = schema.fetch("allOf").map { |subschema| from_json_schema_scalar_type(subschema) }.compact
        raise "No subschema has a defined type" if subschema_types.empty?

        if subschema_types.fetch(0).kind == :string
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t.kind == :string }

          subschema_types.fetch(0)
        elsif subschema_types.fetch(0).kind == :boolean
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t.kind == :boolean }

          subschema_types.fetch(0)
        elsif subschema_types.fetch(0).kind == :bits
          raise "Subschema types do not agree" unless subschema_types[1..].all? { |t| t.kind == :bits }

          unknown_width_type = subschema_types.find { |t| t.width == :unknown }
          return unknown_width_type unless unknown_width_type.nil?

          subschema_types.max { |t1, t2| t1.width <=> t2.width }
        else
          raise "unhandled subschema type"
        end
      elsif schema.key?("$ref")
        if schema.fetch("$ref") == "schema_defs.json#/$defs/uint32"
          Type.new(:bits, width: 32)
        elsif schema.fetch("$ref") == "schema_defs.json#/$defs/uint64"
          Type.new(:bits, width: 64)
        else
          raise "unhandled ref: #{schema.fetch("$ref")}"
        end
      elsif schema.key?("not")
        nil
      else
        raise "unhandled scalar schema:\n#{schema}"
      end
    end
    private_class_method :from_json_schema_scalar_type

    sig { params(types: T::Array[Type]).returns(Type) }
    def self.merge_json_schema_scalar_types(types)
      raise "No scalar types" if types.empty?

      first = types.fetch(0)
      kind = first.kind
      raise "Schema error: Array elements must be the same type" unless types.all? { |t| t.kind == kind }

      if kind == :bits
        unknown_width_type = types.find { |t| t.width == :unknown }
        return unknown_width_type unless unknown_width_type.nil?

        Type.new(:bits, width: T.must(types.map(&:width).max))
      else
        raise "Schema error: Array elements must be the same type" unless types.all? { |t| first.equal_to?(t) }

        first
      end
    end
    private_class_method :merge_json_schema_scalar_types

    # @return [Idl::Type] Type of array
    # @param schema [Hash] JSON Schema description of an array
    sig { params(schema: T::Hash[String, T.untyped]).returns(Type) }
    def self.from_json_schema_array_type(schema)
      width = schema["minItems"]
      if !schema.key?("minItems") || !schema.key?("maxItems") || (schema["minItems"] != schema["maxItems"])
        width = :unknown
      end

      if schema["items"].is_a?(Hash)
        Type.new(:array, width:, sub_type: from_json_schema(schema["items"]))
      else
        raise "unexpected #{schema}" unless schema["items"].is_a?(Array)

        # this ia an array with each element specified
        item_types = schema["items"].map { |item_schema| from_json_schema_scalar_type(item_schema) }
        item_types << from_json_schema_scalar_type(schema["additionalItems"]) if schema.key?("additionalItems")
        sub_type = merge_json_schema_scalar_types(item_types.compact)
        Type.new(:array, width:, sub_type:)
      end
    end
    private_class_method :from_json_schema_array_type

    # @returns [Idl::Type] Type described by JSON +schema+
    sig { params(schema: T::Hash[String, T.untyped]).returns(T.nilable(Type)) }
    def self.from_json_schema(schema)
      hsh = schema.to_h
      if hsh.key?("type")
        case hsh["type"]
        when "boolean", "integer", "string"
          from_json_schema_scalar_type(hsh)
        when "array"
          from_json_schema_array_type(hsh)
        else
          raise "unexpected"
        end
      else
        from_json_schema_scalar_type(hsh)
      end
    end
  end

  class StructType < Type
    sig { returns(String) }
    attr_reader :type_name

    sig { params(type_name: String, member_types: T::Array[Type], member_names: T::Array[String]).void }
    def initialize(type_name, member_types, member_names)
      super(:struct)
      @type_name = type_name
      @member_types = member_types
      @member_names = member_names
    end

    sig { returns(String) }
    def name = @type_name

    def clone
      StructType.new(@type_name, @member_types, @member_names)
    end

    def default
      hsh = {}
      @member_types.size.times do |i|
        hsh[@member_names.fetch(i)] = @member_types.fetch(i).default
      end
      hsh
    end

    def member?(name) = @member_names.include?(name)

    def member_type(member_name)
      idx = @member_names.index(member_name)
      raise "No member named '#{member_name}'" if idx.nil?

      @member_types[idx]
    end

    # does this struct have any members whose type depends on a runtime parameter?
    def runtime?
      @member_types.any?(&:runtime?)
    end
  end

  class EnumerationType < Type
    extend T::Sig

    # @return [Integer] The bit width of the enumeration elements
    sig { returns(Integer) }
    def width = T.cast(@width, Integer)

    # @return [Array<String>] The names of the enumeration elements, in the same order as element_values
    sig { returns(T::Array[String]) }
    attr_reader :element_names

    # @return [Array<Integer>] The values of the enumeration elements, in the same order as element_names
    sig { returns(T::Array[Integer]) }
    attr_reader :element_values

    # @return [Type] The type of an reference to this Enumeration class
    sig { returns(Type) }
    attr_reader :ref_type

    # @param type_name [String] The name of the enum class
    # @param element_names [Array<String>] The names of the elements, in the same order as +element_values+
    # @param element_values [Array<Integer>] The values of the elements, in the same order as +element_names+
    sig {
      params(
        type_name: String,
        element_names: T::Array[String],
        element_values: T::Array[Integer],
        builtin: T::Boolean
      ).void
    }
    def initialize(type_name, element_names, element_values, builtin: false)
      width = T.must(element_values.max).bit_length
      width = 1 if width.zero? # can happen if only enum member has value 0
      super(:enum, width:)

      @name = type_name.freeze
      @element_names = element_names.freeze
      @element_values = element_values.freeze
      raise "names and values aren't the same size" unless element_names.size == element_values.size

      @ref_type = Type.new(:enum_ref, enum_class: self).freeze
      @builtin = builtin.freeze
    end

    sig { returns(T::Boolean) }
    def builtin? = @builtin

    sig { returns(EnumerationType) }
    def clone
      EnumerationType.new(T.must(@name), @element_names, @element_values)
    end

    sig { params(element_name: String).returns(T.nilable(Integer)) }
    def value(element_name)
      i = @element_names.index(element_name)
      return nil if i.nil?

      @element_values[i]
    end

    sig { params(element_value: Integer).returns(T.nilable(String)) }
    def element_name(element_value)
      i = @element_values.index(element_value)
      raise "? #{element_value}" if i.nil?
      return nil if i.nil?

      @element_names[i]
    end
  end

  class BitfieldType < Type
    def width = @field_ranges.map(&:size).reduce(&:+)
    def initialize(type_name, width, field_names, field_ranges)
      super(:bitfield, name: type_name, width:)

      @field_names = field_names
      @field_ranges = field_ranges
      raise "unexpected" unless field_names.is_a?(Array)
      raise "unexpected" unless field_ranges.is_a?(Array) && field_names.length == field_ranges.length
    end

    def range(field_name)
      i = @field_names.index(field_name)
      raise "Could not find #{field_name} in #{@name}" if i.nil?

      @field_ranges[i]
    end

    def field_names
      @field_names
    end

    def clone
      BitfieldType.new(
        name,
        width,
        field_names,
        @field_ranges
      )
    end

  end

  # represents a CSR register
  class CsrType < Type
    extend T::Sig

    sig { returns(Csr) }
    attr_reader :csr

    sig { params(csr: Csr, qualifiers: T::Array[Symbol]).void }
    def initialize(csr, qualifiers: [])
      super(:csr, name: csr.name, csr: csr, width: csr.max_length, qualifiers: qualifiers)
    end

    sig { returns(T::Array[CsrField]) }
    def fields
      raise "fields are unknown" if @csr == :unknown

      @csr.fields
    end
  end

  class FunctionType < Type
    attr_reader :func_def_ast

    sig {
      params(
        func_name: String,
        func_def_ast: FunctionDefAst,
        symtab: SymbolTable
      )
      .void
    }
    def initialize(func_name, func_def_ast, symtab)
      super(:function, name: func_name)
      @func_def_ast = func_def_ast
      @symtab = symtab

      raise "symtab should be at level 1" unless symtab.levels == 1
    end

    def argument_nodes = @func_def_ast.argument_nodes

    sig {
      returns(FunctionType)
    }
    def clone
      FunctionType.new(name, @func_def_ast, @symtab)
    end

    sig { returns(T::Boolean) }
    def builtin? = @func_def_ast.builtin?

    sig { returns(T::Boolean) }
    def generated? = @func_def_ast.generated?

    sig { returns(T::Boolean) }
    def external? = @func_def_ast.external?

    sig { returns(Integer) }
    def num_args = @func_def_ast.num_args

    # apply the arguments as Vars.
    # then add the value to the Var
    sig {
      params(
        symtab: SymbolTable,  # global symbol table
        argument_nodes: T::Array[Rvalue], # arguments
        call_site_symtab: SymbolTable,  # symbol table at the function call site
        func_call_ast: FunctionCallExpressionAst
      ).returns(T::Array[T.any(Integer, Symbol)])
    }
    def apply_arguments(symtab, argument_nodes, call_site_symtab, func_call_ast)
      idx = 0
      values = []
      @func_def_ast.arguments(symtab).each do |atype, aname|
        func_call_ast.type_error "Missing argument #{idx}" if idx >= argument_nodes.size
        value_result = Idl::AstNode.value_try do
          value = argument_nodes.fetch(idx).value(call_site_symtab)
          symtab.add(aname, Var.new(aname, atype, value))
          values << value
        end
        Idl::AstNode.value_else(value_result) do
          symtab.add(aname, Var.new(aname, atype))
          values << :unknown
        end
        idx += 1
      end
      values
    end

    # @return [Array<Integer,Boolean>] Array of argument values, if known
    # @return [nil] if at least one argument value is not known
    sig {
      params(
        symtab: SymbolTable,  # global symbol table
        argument_nodes: T::Array[Rvalue], # arguments
        call_site_symtab: SymbolTable,  # symbol table at the function call site
        func_call_ast: FunctionCallExpressionAst
      ).returns(T.nilable(T::Array[T.any(Integer, T::Boolean, Symbol)]))
    }
    def argument_values(symtab, argument_nodes, call_site_symtab, func_call_ast)
      idx = 0
      values = []
      @func_def_ast.arguments(symtab).each do |atype, aname|
        func_call_ast.type_error "Missing argument #{idx}" if idx >= argument_nodes.size
        value_result = Idl::AstNode.value_try do
          values << argument_nodes.fetch(idx).value(call_site_symtab)
        end
        Idl::AstNode.value_else(value_result) do
          return nil
        end
        idx += 1
      end
      values
    end

    # @param func_call_ast [FunctionCallExpressionAst] The function call interested in the return type
    # return [Type] type of the call return
    sig {
      params(
        argument_nodes: T::Array[Rvalue],
        func_call_ast: FunctionCallExpressionAst
      ).returns(Type)
    }
    def return_type(argument_nodes, func_call_ast)
      rtype =
        begin
          symtab = @symtab.global_clone
          symtab.push(func_call_ast)
          @func_def_ast.return_type(symtab)
        ensure
          symtab.pop
          symtab.release
        end

      T.must(rtype)
    end

    sig {
      params(
        argument_nodes: T::Array[Rvalue], # arguments
        call_site_symtab: SymbolTable,  # symbol table at the function call site
        func_call_ast: FunctionCallExpressionAst
      ).returns(T.nilable(T.any(Integer, T::Boolean, Symbol, T::Hash[String, T.untyped])))
    }
    def return_value(argument_nodes, call_site_symtab, func_call_ast)
      symtab = @symtab.global_clone
      symtab.push(func_call_ast)
      apply_arguments(symtab, argument_nodes, call_site_symtab, func_call_ast)

      begin
        value = @func_def_ast.body.return_value(symtab)
      ensure
        symtab.pop
        symtab.release
      end
      raise "?" if value.is_a?(SymbolTable)
      value
    end

    sig {
      params(
        index: Integer,
        argument_nodes: T::Array[Rvalue], # arguments
        call_site_symtab: SymbolTable,  # symbol table at the function call site
        func_call_ast: FunctionCallExpressionAst
      ).returns(T.nilable(Type))
    }
    def argument_type(index, argument_nodes, call_site_symtab, func_call_ast)
      return nil if index >= @func_def_ast.num_args

      symtab = @symtab.global_clone
      symtab.push(func_call_ast)

      begin
        arguments = @func_def_ast.arguments(symtab)
      ensure
        symtab.pop
        symtab.release
      end
      arguments[index][0]
    end

    sig {
      params(
        index: Integer,
        func_call_ast: FunctionCallExpressionAst
      ).returns(T.nilable(String))
    }
    def argument_name(index, func_call_ast)
      return nil if index >= @func_def_ast.num_args

      symtab = @symtab.global_clone
      symtab.push(func_call_ast)

      begin
        arguments = @func_def_ast.arguments(symtab)
      ensure
        symtab.pop
        symtab.release
      end
      arguments[index][1]
    end

    sig {
      returns(FunctionBodyAst)
    }
    def body = @func_def_ast.body
  end

  # General-purpose register file element type.
  # Represents the type of one element in a named register file (e.g. F, V, X).
  class RegFileElementType < Type
    attr_reader :name

    def initialize(name, width, max_width: nil)
      super(:bits, width:, max_width: max_width || width)
      @name = name
    end

    def to_s = "#{name}Reg"
    def to_cxx = "#{name}Reg"
  end

  # XReg is really a Bits<> type -- keep as a named alias for backwards compatibility
  class XregType < RegFileElementType
    def initialize(xlen)
      super("X", xlen, max_width: 64)
    end
  end

  # pre-define some common types
  Bits1Type = Type.new(:bits, width: 1).freeze
  Bits32Type = Type.new(:bits, width: 32).freeze
  Bits64Type = Type.new(:bits, width: 64).freeze
  BitsUnknownType = Type.new(:bits, width: :unknown).freeze
  ConstBitsUnknownType = Type.new(:bits, width: :unknown, qualifiers: [:const]).freeze
  ConstBoolType = Type.new(:boolean, qualifiers: [:const]).freeze
  BoolType = Type.new(:boolean).freeze
  VoidType = Type.new(:void).freeze
  StringType = Type.new(:string).freeze
end
