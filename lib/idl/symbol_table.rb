# frozen_string_literal: true

require_relative "type"

module Idl
  # Objects to represent variables in the ISA def
  class Var
    attr_reader :name, :type, :value

    def initialize(name, type, value = nil, decode_var: false, template_index: nil, function_name: nil)
      @name = name
      raise ArgumentError, "Expecting a Type, got #{type.class.name}" unless type.is_a?(Type)

      @type = type
      @type.freeze
      @value = value
      raise 'unexpected' unless decode_var.is_a?(TrueClass) || decode_var.is_a?(FalseClass)

      @decode_var = decode_var
      @template_index = template_index
      @function_name = function_name
    end

    def hash
      [@name, @type, @value, @decode_var, @template_index, @function_name].hash
    end

    def to_s
      "VAR: #{type} #{name} #{value.nil? ? 'NO VALUE' : value}"
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

    # @return [Integer] 32 or 64, the XLEN in M-mode
    attr_reader :mxlen

    class DuplicateSymError < StandardError
    end

    def hash
      return @frozen_hash unless @frozen_hash.nil?

      [@scopes.hash, @archdef.hash].hash
    end

    def initialize(arch_def, effective_xlen = nil)
      @archdef = arch_def
      if arch_def.fully_configured?
        raise "effective_xlen should not be set when symbol table is given a fully-configured ArchDef" unless effective_xlen.nil?
      else
        raise "effective_xlen should be set when symbol table is given an ArchDef" if effective_xlen.nil?
      end
      @mxlen = effective_xlen.nil? ? arch_def.mxlen : effective_xlen
      @scopes = [{
        "X" => Var.new(
          "X",
          Type.new(:array, sub_type: XregType.new(@mxlen), width: 32, qualifiers: [:global])
        ),
        "XReg" => XregType.new(@mxlen),
        "Boolean" => Type.new(:boolean),
        "true" => Var.new(
          "true",
          Type.new(:boolean),
          true
        ),
        "false" => Var.new(
          "false",
          Type.new(:boolean),
          false
        )

      }]
      arch_def.params_with_value.each do |param_with_value|
        type = Type.from_json_schema(param_with_value.schema).make_const
        if type.kind == :array && type.width == :unknown
          type = Type.new(:array, width: param_with_value.value.length, sub_type: type.sub_type)
        end

        # could already be present...
        existing_sym = get(param_with_value.name)
        if existing_sym.nil?
          add!(param_with_value.name, Var.new(param_with_value.name, type, param_with_value.value))
        else
          unless existing_sym.type.equal_to?(type) && existing_sym.value == param_with_value.value
            raise DuplicateSymError, "Definition error: Param #{param.name} is defined by multiple extensions and is not the same definition in each"
          end
        end
      end
      # now add all parameters, even those not implemented
      arch_def.params_without_value.each do |param|
        if param.exts.size == 1
          if param.name == "XLEN"
            # special case: we actually do know XLEN
            add!(param.name, Var.new(param.name, param.type.clone.make_const, @mxlen))
          else
            add!(param.name, Var.new(param.name, param.type.clone.make_const))
          end
        else
          # could already be present...
          existing_sym = get(param.name)
          if existing_sym.nil?
            add!(param.name, Var.new(param.name, param.type.clone.make_const))
          else
            unless existing_sym.type.equal_to?(param.type)
              raise "Definition error: Param #{param.name} is defined by multiple extensions and is not the same definition in each"
            end
          end
        end
      end

      # add the builtin extensions
      add!(
        "ExtensionName",
        EnumerationType.new(
          "ExtensionName",
          arch_def.extensions.map(&:name),
          Array.new(arch_def.extensions.size) { |i| i + 1 }
        )
      )
      add!(
        "ExceptionCode",
        EnumerationType.new(
          "ExceptionCode",
          arch_def.exception_codes.map(&:var),
          arch_def.exception_codes.map(&:num)
        )
      )
      add!(
        "InterruptCode",
        EnumerationType.new(
          "InterruptCode",
          arch_def.interrupt_codes.map(&:var),
          arch_def.interrupt_codes.map(&:num)
        )
      )
    end

    # do a deep freeze to protect the sym table and all its entries from modification
    def deep_freeze
      @scopes.each do |k, v|
        k.freeze
        v.freeze
      end
      @scopes.freeze

      # set frozen_hash so that we can quickly compare symtabs
      @frozen_hash = [@scopes.hash, @archdef.hash].hash

      freeze
      self
    end

    # pushes a new scope
    # @return [SymbolTable] self
    def push
      # puts "push #{caller[0]}"
      # @scope_caller ||= []
      # @scope_caller.push caller[0]
      @scopes << {}
      self
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
    def deep_clone(clone_values: false, freeze_global: true)
      raise "don't do this" unless freeze_global

      # globals are frozen, so we can just return a shallow clone
      # if we are in global scope
      if levels == 1
        copy = dup
        copy.instance_variable_set(:@scopes, copy.instance_variable_get(:@scopes).dup)
        return copy
      end

      copy = dup
      # back up the table to global scope
      copy.instance_variable_set(:@scopes, [])
      c_scopes = copy.instance_variable_get(:@scopes)
      c_scopes.push(@scopes[0])

      @scopes[1..].each do |scope|
        c_scopes << {}
        scope.each do |k, v|
          if clone_values
            c_scopes.last[k] = v.dup
          else
            c_scopes.last[k] = v
          end
        end
      end
      copy
    end
  end
end
