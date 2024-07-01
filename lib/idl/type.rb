# frozen_string_literal: true

module Idl
  # Data types
  class Type
    KINDS = [
      :void,     # empty
      :boolean,  # true or false, not compatible with bits/int/xreg
      :bits,     # integer with compile-time-known bit width
      :enum,     # enumeration class
      :enum_ref, # reference to an enumeration element, convertable to int and/or Bits<bit_width(MAX_ENUM_VALUE)>
      :bitfield, # bitfield, convertable to int and/or Bits<width>
      :array,    # array of other types
      :tuple,    # tuple of other disimilar types
      :function, # function
      :template_function, # template function, where the template arguments are known but template values need to be applied to become a full function
      :csr,      # a CSR register type
      :dontcare  # matches everything
    ].freeze
    QUALIFIERS = [
      :const,
      :constexpr, # i.e., known at instruction decode time
      :signed
    ].freeze

    # true for any type that can generally be treated as a scalar integer
    def integral?
      @kind == :bits
    end

    attr_reader :kind, :qualifiers, :width, :sub_type, :tuple_types, :return_type, :arguments, :enum_class

    def qualify(qualifier)
      @qualifiers << qualifier
      @qualifiers.uniq!
      self
    end

    def self.from_typename(type_name, arch_def)
      case type_name
      when 'XReg'
        return Type.new(:bits, width: arch_def.config_params['XLEN'])
      when 'FReg'
        return Type.new(:freg, width: 32)
      when 'DReg'
        return Type.new(:dreg, width: 64)
      when /Bits<((?:0x)?[0-9a-fA-F]+)>/
        Type.new(:bits, width: $1.to_i)
      end
    end

    def initialize(kind, qualifiers: [], width: nil, sub_type: nil, name: nil, tuple_types: nil, return_type: nil, arguments: nil, enum_class: nil, csr: nil)
      raise "Invalid kind '#{kind}'" unless KINDS.include?(kind)

      @kind = kind
      qualifiers.each do |q|
        raise 'Invalid qualifier' unless QUALIFIERS.include?(q)
      end
      @qualifiers = qualifiers
      # raise "#{width.class.name}" if (kind == :bits && !width.is_a?(Integer))

      raise "Width must be an Integer, is a #{width.class}" unless width.nil? || width.is_a?(Integer)
      @width = width
      @sub_type = sub_type
      raise "Tuples need a type list" if kind == :tuple && tuple_types.nil?
      @tuple_types = tuple_types
      @return_type = return_type
      @arguments = arguments
      @enum_class = enum_class
      @name = name
      if kind == :bits
        raise "Bits type must have width" unless @width
        raise "Bits type must have positive width" unless @width.positive?
      end
      if kind == :enum
        raise "Enum type must have width" unless @width
      end
      if kind == :array
        raise "Array must have a subtype" unless @sub_type
      end
      if kind == :csr
        raise 'CSR type must have a csr argument' if csr.nil?

        @csr = csr

        raise 'CSR types get width from csr argument; width should not be specified' unless width.nil? || width == csr.length

        @width = csr.length
      end
    end

    def clone
      Type.new(
        @kind,
        qualifiers: @qualifiers&.map(&:clone),
        width: @width,
        sub_type: @sub_type&.clone,
        name: @name.dup,
        tuple_types: @tuple_types&.map(&:clone),
        return_type: @return_type&.clone,
        arguments: @arguments&.map(&:clone),
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
          (type.kind == :enum_ref && type.enum_class.name == @enum_class.name) \
          || (type.kind == :enum && type.name == @enum_class.name)
      when :bits
        return type.convertable_to?(self)
      when :enum
        return type.convertable_to?(:bits)
      when :function
        # functions are not comparable to anything
        return false
      when :csr
        return ((type.kind == :csr) && (type.csr.name == @csr.name)) ||
              type.convertable_to?(Type.new(:bits, width: type.csr.width))
      else
        raise "unimplemented #{@kind}"
      end
    end

    # returns true if identical to type, excluding qualifiers
    def equal_to?(type)
      if type.is_a?(Symbol)
        raise "#{type} is not a kind" unless KINDS.include?(type)

        type = Type.new(type)
      end

      case @kind
      when :boolean
        return type.kind == :boolean
      when :enum_ref
        return type.kind == :enum_ref && type.name == @enum_class.name
      when :dontcare
        return true
      when :bits
        return type.kind == :bits && type.width == @width
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

        type = Type.new(type)
      end

      case @kind
      when :boolean
        return type.kind == :boolean
      when :enum_ref
        return \
          (type.kind == :enum && type.name == @enum_class.name) || \
          (type.kind == :enum_ref && type.enum_class.name == @enum_class.name)
      when :dontcare
        return true
      when :bits
        return type.kind != :boolean
      when :function
        return @return_type.convertable_to?(type)
      when :enum
        if type.kind == :bits
          return width <= type.width
        elsif type.kind == :enum
          return type.enum_class == enum_class
        else
          return false
        end
      when :tuple
        is_tuple_of_same_size = (type.kind == :tuple) && (@tuple_types.size == type.tuple_types.size)
        if is_tuple_of_same_size
          @tuple_types.each_index do |i|
            unless @tuple_types[i].convertable_to?(type.tuple_types[i])
              return false
            end
          end
          return true
        else
          return false
        end
      when :csr
        return (type.kind == :csr && type.csr.name == @csr.name) || type.convertable_to?(Type.new(:bits, width: @csr.length))
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
      else
        raise "unimplemented type '#{@kind}'"
      end
    end

    def to_s
      ((@qualifiers.nil? || @qualifiers.empty?) ? '' : "#{@qualifiers.map(&:to_s).join(' ')} ") + \
        if @kind == :bits
          "Bits<#{@width}>"
        elsif @kind == :enum
          "enum definition #{@name}"
        elsif @kind == :boolean
          "Boolean"
        elsif @kind == :function
          @return_type.to_s
        elsif @kind == :enum_ref
          "enum #{@enum_class.name}"
        elsif @kind == :tuple
          "(#{@tuple_types.map{ |t| t.to_s }.join(',')})"
        elsif @kind == :bitfield
          "bitfield #{@name}"
        elsif @kind == :array
          "array of #{@sub_type}"
        elsif @kind == :csr
          "CSR[#{@csr.name}]"
        elsif @kind == :void
          "void"
        else
          raise @kind.to_s
        end
    end
    alias fully_qualified_name to_s

    def to_cxx_no_qualifiers
        if @kind == :bits
          raise "@width is a #{@width.class}" unless @width.is_a?(Integer)
          if signed?
            "SignedBits<#{@width.is_a?(Integer) ? @width : @width.to_cxx}>"
          else
            "Bits<#{@width.is_a?(Integer) ? @width : @width.to_cxx}>"
          end
        elsif @kind == :enum
          "#{@name}"
        elsif @kind == :boolean
          "bool"
        elsif @kind == :function
          "std::function<#{@return_type.to_cxx}(...)>"
        elsif @kind == :enum_ref
          "#{@enum_class.name}"
        elsif @kind == :tuple
          "std::tuple<#{@tuple_types.map{ |t| t.to_cxx }.join(',')}>"
        elsif @kind == :bitfield
          "#{@name}"
        elsif @kind == :array
          "#{@sub_type}[]"
        elsif @kind == :csr
          "#{@csr.downcase.capitalize}Csr"
        else
          raise @kind.to_s
        end
    end

    def to_cxx
      ((@qualifiers.nil? || @qualifiers.empty?) ? '' : "#{@qualifiers.include?(:const) ? 'const' : ''} ") + \
      to_cxx_no_qualifiers
    end

    def name
      if @kind == :bits
        "Bits<#{@width}>"
      elsif @kind == :enum
        @name
      elsif @kind == :bitfield
        @name
      elsif @kind == :function || @kind == :template_function
        @name
      elsif @kind == :csr
        @csr.name
      elsif @kind == :enum_ref
        @enum_class.name
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

    def constexpr?
      @qualifiers.include?(:constexpr)
    end

    def mutable?
      return !const? && !constexpr?
    end

    def make_constexpr
      @qualifiers.append(:constexpr).uniq!
      self
    end

    def remove_constexpr
      @qualifiers.delete_if { |q| q == :constexpr }
      self
    end

    def signed?
      @qualifiers.include?(:signed)
    end

    def make_signed
      @qualifiers.append(:signed).uniq!
      self
    end
  end


  class EnumerationType < Type
    attr_reader :element_names, :element_values, :width

    def initialize(type_name, element_names, element_values)
      width = element_values.max.bit_length
      width = 1 if width.zero? # can happen if only enum member has value 0
      super(:enum, width: width)

      @name = type_name
      @element_names = element_names
      @element_values = element_values
      raise "unexpected" unless element_names.is_a?(Array)

      # now add the constant values at the same scope
      # ...or, enum values are only usable in specific contexts?
  #    element_names.each_index do |idx|
  #      syms.add!(element_names[idx], Var.new(element_names[idx], self, element_values[idx]))
  #    end
    end

    def value(element_name)
      i = @element_names.index(element_name)
      raise "Could not find #{element_name} in enumeration #{@name}" if i.nil?

      return @element_values[i]
    end
  end

  class BitfieldType < Type
    def initialize(type_name, width, field_names, field_ranges)
      super(:bitfield, name: type_name, width: width)

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
    attr_reader :csr

    def initialize(csr, qualifiers: [])
      super(:csr, name: csr.name, csr: csr, qualifiers: qualifiers)
    end

    def fields
      @csr.fields
    end
  end

  class FunctionType < Type
    def initialize(func_name, func_def_ast, symtab, archdef)
      super(:function, name: func_name)
      @func_def_ast = func_def_ast
      @symtab = symtab.deep_clone
      @archdef = archdef

      raise "symtab should be at level 1" unless symtab.levels == 1
    end

    def num_args = @func_def_ast.num_args

    def type_check_call(template_values = [])
      return unless templated?

      symtab = apply_template_values(template_values)

      @func_def_ast.type_check_template_instance(symtab, @archdef)
    end

    def template_names = @func_def_ast.template_names

    def template_types = @func_def_ast.template_types

    def templated? = @func_def_ast.templated?

    def apply_template_values(template_values = [])
      raise "Missing template values" if templated? && template_values.empty?

      raise "wrong number of template values" unless template_names.size == template_values.size

      symtab = @symtab.deep_clone

      symtab.push

      template_values.each_with_index do |value, idx|
        symtab.add!(template_names[idx], Var.new(template_names[idx], template_types[idx], value))
      end
      symtab
    end

    def return_type(template_values = [])
      symtab = apply_template_values(template_values)

      @func_def_ast.return_type(symtab, @archdef)
    end

    # @param template_values [Array<Integer>] Template values to apply, required if {#templated?}
    # @return [Array<Type>] return types
    def return_types(template_values = [])
      symtab = apply_template_values(template_values)

      @func_def_ast.return_types(symtab, @archdef)
    end

    def argument_type(index, template_values = [])
      return nil if index >= @func_def_ast.num_args

      symtab = apply_template_values(template_values)

      arguments = @func_def_ast.arguments(symtab, @archdef)
      arguments[index][0]
    end

    def argument_name(index, template_values = [])
      return nil if index >= @func_def_ast.num_args

      symtab = apply_template_values(template_values)

      arguments = @func_def_ast.arguments(symtab, @archdef)
      arguments[index][1]
    end

    def constexpr?(template_values = [])
      symtab = apply_template_values(template_values)

      @func_def_ast.constexpr?(symtab, @archdef)
    end

    def body = @func_def_ast.body_block.function_body
  end

  # a function that is templated, and hasn't been fully typed checked yet
  # because it needs to have template arguments resolved
  class TemplateFunctionType < Type
    attr_reader :template_types, :ast

    def initialize(func_name, template_types, ast)
      super(:template_function, name: func_name, arguments: arguments)
      @template_types = template_types
      @ast = ast
    end
  end

  # XReg is really a Bits<> type, so we override it just to get
  # prettier prints
  class XregType < Type
    def initialize(xlen)
      super(:bits, width: xlen)
    end

    def to_s
      'XReg'
    end

    def to_cxx
      'XReg'
    end
  end
end
