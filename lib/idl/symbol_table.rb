# frozen_string_literal: true

require_relative "type"

module Idl
  # Objects to represent variables in the ISA def
  class Var
    attr_reader :name, :type, :value

    def initialize(name, type, value = nil, decode_var: false)
      @name = name
      raise 'unexpected' unless type.is_a?(Type)

      @type = type
      @value = value
      raise 'unexpected' unless decode_var.is_a?(TrueClass) || decode_var.is_a?(FalseClass)

      @decode_var = decode_var
    end

    def clone
      Var.new(
        name,
        type.clone,
        value&.clone,
        decode_var: @decode_var
      )
    end

    def const?
      @type.const?
    end

    def decode_var?
      @decode_var
    end

    def to_cxx
      @name
    end

    def value=(new_value)
      @value = new_value
    end
  end

  # scoped symbol table holding known symbols at a current point in parsing
  class SymbolTable
    attr_reader :archdef

    class DuplicateSymError < StandardError
    end

    def initialize(arch_def)
      @archdef = arch_def
      @scopes = [{
        'X' => Var.new(
          'X',
          Type.new(:array, sub_type: XregType.new(arch_def.config_params['XLEN']), width: 32)
        ),
        'XReg' => XregType.new(arch_def.config_params['XLEN']),
        'PC' => Var.new(
          'PC',
          XregType.new(arch_def.config_params['XLEN'])
        ),
        'Boolean' => Type.new(:boolean),
        'True' => Var.new(
          'True',
          Type.new(:boolean),
          true
        ),
        'true' => Var.new(
          'true',
          Type.new(:boolean),
          true
        ),
        'False' => Var.new(
          'False',
          Type.new(:boolean),
          false
        ),
        'false' => Var.new(
          'false',
          Type.new(:boolean),
          true
        )

      }]
      arch_def.config_params.each do |name, value|
        if value.is_a?(Integer)
          width = value.bit_length
          width = 1 if width.zero? # happens if value is 0
          add!(name, Var.new(name, Type.new(:bits, width:), value))
        elsif value.is_a?(TrueClass) || value.is_a?(FalseClass)
          add!(name, Var.new(name, Type.new(:boolean), value))
        elsif value.is_a?(String)
          # just make sure this isn't something we think we need
          expected_names = ["NAME", "M_MODE_ENDIANESS", "S_MODE_ENDIANESS", "U_MODE_ENDIANESS", "VS_MODE_ENDIANESS", "VU_MODE_ENDIANESS"]
          raise "Unexpected String type for '#{name}'" unless expected_names.include?(name)
        elsif value.is_a?(Array)
          unless value.all? { |v| v.is_a?(Integer) || v.is_a?(TrueClass) || v.is_a?(FalseClass) }
            raise "For param #{name}: Can only handle arrays of ints or bools"
          end

          ary = []
          element_type =
            if value[0].is_a?(Integer)
              max_bit_width = value.reduce(0) { |v, max| v > max ? v : max }
              Type.new(:bits, width: max_bit_width)
            else
              Type.new(:boolean)
            end
          ary_type = Type.new(:array, width: value.size, sub_type: element_type)
          value.each_with_index do |v, idx|
            ary << Var.new("#{name}[#{idx}]", element_type, v)
          end
          add!(name, Var.new(name, ary_type, ary))
        else
          raise "Unhandled config param type '#{value.class.name}' for '#{name}'"
        end
      end
      arch_def.extensions.each do |ext|

      end
      add!('ExtensionName', EnumerationType.new('ExtensionName', arch_def.extensions.map(&:name), Array.new(arch_def.extensions.size) { |i| i + 1 }))
    end

    def push
      # puts "push #{caller[0]}"
      # @scope_caller ||= []
      # @scope_caller.push caller[0]
      @scopes << {}
    end

    def pop
      # puts "pop #{caller[0]}"
      # puts "    from #{@scope_caller.pop}"
      raise 'Error: popping the symbol table would remove global scope' if @scopes.size == 1

      @scopes.pop
    end

    def key?(name)
      @scopes.each { |s| return true if s.key?(name) }
    end

    def get(name)
      @scopes.reverse_each do |s|
        return s[name] if s.key?(name)
      end
      nil
    end

    def add(name, var)
      @scopes.last[name] = var
    end

    # add, and make sure name is unique
    def add!(name, var)
      raise DuplicateSymError, "Symbol #{name} already defined as #{get(name)}" unless @scopes.select { |h| h.key? name }.empty?

      @scopes.last[name] = var
    end

    # add to the scope above the tail, and make sure name is unique at that scope
    def add_above!(name, var)
      raise "There is only one scope" if @scopes.size <= 1

      raise "Symbol #{name} already defined" unless @scopes[0..-2].select { |h| h.key? name }.empty?

      @scopes[-2][name] = var
    end

    # add to the scope at level, and make sure name is unique at that scope
    def add_at!(level, name, var)
      raise "Level #{level} is too large #{@scopes.size}" if  level >= @scopes.size

      raise "Symbol #{name} already defined" unless @scopes[0...level].select { |h| h.key? name }.empty?
  
      @scopes[level][name] = var
    end

    def levels
      @scopes.size
    end

    def print
      @scopes.each do |s|
        s.each do |name, obj|
          puts "#{name} #{obj}"
        end
      end
    end

    # return a deep clone of this SymbolTable
    def deep_clone(clone_values: false)
      copy = SymbolTable.new(@archdef)
      copy.instance_variable_set(:@scopes, [])
      c_scopes = copy.instance_variable_get(:@scopes)

      @scopes.each do |scope|
        c_scopes << {}
        scope.each do |k, v|
          if clone_values
            c_scopes.last[k] = v.clone
          else
            c_scopes.last[k] = v
          end
        end
      end
      copy
    end
  end
end
