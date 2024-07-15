# frozen_string_literal: true

require_relative "type"

module Idl
  # Objects to represent variables in the ISA def
  class Var
    attr_reader :name, :type, :value

    def initialize(name, type, value = nil, decode_var: false, template_index: nil, function_name: nil)
      @name = name
      raise 'unexpected' unless type.is_a?(Type)

      @type = type
      @value = value
      raise 'unexpected' unless decode_var.is_a?(TrueClass) || decode_var.is_a?(FalseClass)

      @decode_var = decode_var
      @template_index = template_index
      @function_name = function_name
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

    # @param function_name [#to_s] A function name
    # @return [Boolean] whether or not this variable is a function template argument from a call site for the function 'function_name'
    def template_value_for?(function_name)
      !@template_index.nil? && (function_name.to_s == @function_name)
    end

    # @return [Integer] the template value position
    # @raise if Var is not a template value
    def template_index
      raise "Not a template value" if @template_index.nil?

      @template_index
    end

    def template_val?
      !@template_index.nil?
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

    # pushes a new scope
    def push
      # puts "push #{caller[0]}"
      # @scope_caller ||= []
      # @scope_caller.push caller[0]
      @scopes << {}
    end

    # pops the top of the scope stack
    def pop
      # puts "pop #{caller[0]}"
      # puts "    from #{@scope_caller.pop}"
      raise "Error: popping the symbol table would remove global scope" if @scopes.size == 1

      @scopes.pop
    end

    # @return [Boolean] whether or not any symbol 'name' is defined at any level in the symbol table
    def key?(name)
      @scopes.each { |s| return true if s.key?(name) }
    end

    def keys_pretty
      @scopes.map { |s| s.map { |k, v| v.is_a?(Var) && v.template_val? ? "#{k} (template)" : k }}
    end

    # searches the symbol table scope-by-scope to find 'name'
    #
    # @return [Object] A symbol named 'name', or nil if not found
    def get(name)
      @scopes.reverse_each do |s|
        return s[name] if s.key?(name)
      end
      nil
    end

    def get_from(name, level)
      raise ArgumentError, "level must be positive" unless level.positive?

      raise "There is no level #{level}" unless level < levels

      @scopes[0..level - 1].reverse_each do |s|
        return s[name] if s.key?(name)
      end
      nil
    end

    # @return [Object] the symbol named 'name' from global scope, or nil if not found
    def get_global(name)
      get_from(name, 1)
    end

    # searches the symbol table scope-by-scope to find all entries for which the block returns true
    #
    # @param single_scope [Boolean] If true, stop searching more scope as soon as there are matches
    # @yieldparam obj [Object] A object stored in the symbol table
    # @yieldreturn [Boolean] Whether or not the object is the one you are looking for
    # @return [Array<Object>] All matches
    def find_all(single_scope: false, &block)
      raise ArgumentError, "Block needed" unless block_given?

      raise ArgumentError, "Find block takes one argument" unless block.arity == 1

      matches = []

      @scopes.reverse_each do |s|
        s.each_value do |v|
          matches << v if yield v
        end
        break if single_scope && !matches.empty?
      end
      matches
    end

    # add a new symbol at the outermost scope
    #
    # @param name [#to_s] Symbol name
    # @param var [Object] Symbol object (usually a Var or a Type)
    def add(name, var)
      @scopes.last[name] = var
    end

    # add a new symbol at the outermost scope, unless that symbol is already defined
    #
    # @param name [#to_s] Symbol name
    # @param var [Object] Symbol object (usually a Var or a Type)
    # @raise [DuplicationSymError] if 'name' is already in the symbol table
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

    # @return [Integer] Number of scopes on the symbol table (global at 1)
    def levels
      @scopes.size
    end

    # pretty-print the symbol table contents
    def print
      @scopes.each do |s|
        s.each do |name, obj|
          puts "#{name} #{obj}"
        end
      end
    end

    # @return [SymbolTable] a deep clone of this SymbolTable
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
