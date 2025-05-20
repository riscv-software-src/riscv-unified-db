# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "concurrent"

require_relative "type"

module Udb
  class Architecture; end
  class ConfiguredArchitecture < Architecture; end
end

module Idl
  # Objects to represent variables in the ISA def
  class Var
    attr_reader :name, :type, :value

    def initialize(name, type, value = nil, decode_var: false, template_index: nil, function_name: nil, param: false)
      @name = name
      raise ArgumentError, "Expecting a Type, got #{type.class.name}" unless type.is_a?(Type)

      @type = type
      @type.qualify(:template_var)
      @type.freeze
      @value = value
      raise "unexpected" unless decode_var.is_a?(TrueClass) || decode_var.is_a?(FalseClass)

      @decode_var = decode_var
      @template_index = template_index
      @function_name = function_name
      @param = param
    end

    def hash
      [@name, @type, @value, @decode_var, @template_index, @function_name, @param].hash
    end

    def to_s
      "VAR: #{type} #{name} #{value.nil? ? 'NO VALUE' : value}"
    end

    def clone
      Var.new(
        name,
        type.clone,
        value&.clone,
        decode_var: @decode_var,
        template_index: @template_index,
        function_name: @function_name,
        param: @param
      )
    end

    def const?
      @type.const?
    end

    def decode_var?
      @decode_var
    end

    def param?
      @param
    end

    # @param function_name [#to_s] A function name
    # @return [Boolean] whether or not this variable is a function template argument from a call site for the function 'function_name'
    def template_value_for?(function_name)
      !@template_index.nil? && (function_name.to_s == @function_name)
    end

    def template_value? = !@template_index.nil?

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
    extend T::Sig

    def cfg_arch = @cfg_arch

    # @return [Integer] 32 or 64, the XLEN in M-mode
    attr_reader :mxlen

    class DuplicateSymError < StandardError
    end

    def hash
      return @frozen_hash unless @frozen_hash.nil?

      [@scopes.hash, @cfg_arch.hash].hash
    end

    sig { params(cfg_arch: T.nilable(Udb::ConfiguredArchitecture)).void }
    def initialize(cfg_arch)
      @mutex = Thread::Mutex.new
      @cfg_arch = cfg_arch
      @mxlen = (cfg_arch.nil? || cfg_arch.unconfigured?) ? nil : cfg_arch.mxlen
      @callstack = [nil]
      @scopes = [{
        "X" => Var.new(
          "X",
          Type.new(:array, sub_type: XregType.new(@mxlen.nil? ? 64 : @mxlen), width: 32, qualifiers: [:global])
        ),
        "XReg" => XregType.new(@mxlen.nil? ? 64 : @mxlen),
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
      cfg_arch && cfg_arch.params_with_value.each do |param_with_value|
        type = Type.from_json_schema(param_with_value.schema).make_const
        if type.kind == :array && type.width == :unknown
          type = Type.new(:array, width: param_with_value.value.length, sub_type: type.sub_type, qualifiers: [:const])
        end

        # could already be present...
        existing_sym = get(param_with_value.name)
        if existing_sym.nil?
          add!(param_with_value.name, Var.new(param_with_value.name, type, param_with_value.value, param: true))
        else
          unless existing_sym.type.equal_to?(type) && existing_sym.value == param_with_value.value
            raise DuplicateSymError, "Definition error: Param #{param.name} is defined by multiple extensions and is not the same definition in each"
          end
        end
      end

      # now add all parameters, even those not implemented
      cfg_arch && cfg_arch.params_without_value.each do |param|
        if param.exts.size == 1
          add!(param.name, Var.new(param.name, param.idl_type.clone.make_const, param: true))
        else
          # could already be present...
          existing_sym = get(param.name)
          if existing_sym.nil?
            add!(param.name, Var.new(param.name, param.idl_type.clone.make_const, param: true))
          else
            unless existing_sym.type.equal_to?(param.idl_type)
              raise "Definition error: Param #{param.name} is defined by multiple extensions and is not the same definition in each"
            end
          end
        end
      end
    end

    # do a deep freeze to protect the sym table and all its entries from modification
    def deep_freeze
      @scopes.each do |k, v|
        k.freeze
        v.freeze
      end
      @scopes.freeze

      # set frozen_hash so that we can quickly compare symtabs
      @frozen_hash = [@scopes.hash, @cfg_arch.hash].hash

      # set up the global clone that be used as a mutable table
      @global_clone_pool = Concurrent::Array.new

      5.times do
        copy = SymbolTable.allocate
        copy.instance_variable_set(:@scopes, [@scopes[0]])
        copy.instance_variable_set(:@callstack, [@callstack[0]])
        copy.instance_variable_set(:@cfg_arch, @cfg_arch)
        copy.instance_variable_set(:@mxlen, @mxlen)
        copy.instance_variable_set(:@mutex, @mutex)
        copy.instance_variable_set(:@global_clone_pool, @global_clone_pool)
        copy.instance_variable_set(:@in_use, Concurrent::Semaphore.new(1))
        @global_clone_pool << copy
      end

      freeze
      self
    end

    # @return [String] inspection string
    def inspect
      "SymbolTable[#{@cfg_arch&.name}]#{frozen? ? ' (frozen)' : ''}"
    end

    # pushes a new scope
    # @return [SymbolTable] self
    def push(ast)
      # puts "push #{caller[0]}"
      # @scope_caller ||= []
      # @scope_caller.push caller[0]
      raise "#{@scopes.size} #{@callstack.size}" unless @scopes.size == @callstack.size
      @scopes << {}
      @callstack << ast
      @frozen_hash = nil
      self
    end

    # pops the top of the scope stack
    def pop
      # puts "pop #{caller[0]}"
      # puts "    from #{@scope_caller.pop}"
      raise "Error: popping the symbol table would remove global scope" if @scopes.size == 1

      raise "?" unless @scopes.size == @callstack.size
      @scopes.pop
      @callstack.pop
    end

    def callstack
      @callstack.reverse.map { |ast| ast.nil? ? "" : "#{ast.input_file}:#{ast.lineno}" }.join("\n")
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
        result = s.fetch(name, nil)
        return result unless result.nil?
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

    # delete a new symbol at the outermost scopea
    #
    # @param name [#to_s] Symbol name
    # @param var [Object] Symbol object (usually a Var or a Type)
    def del(name)
      raise "No symbol #{name} at outer scope" unless @scopes.last.key?(name)

      @scopes.last.delete(name)
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

    # @return [Boolean] true if the symbol table is at the global scope
    def at_global_scope?
      @scopes.size == 1
    end

    # @return [SymbolTable] a mutable clone of the global scope of this SymbolTable
    def global_clone
      # raise "symtab isn't frozen" if @global_clone.nil?
      # raise "global clone isn't at global scope" unless @global_clone.at_global_scope?

      @global_clone_pool.each do |symtab|
        return symtab if symtab.instance_variable_get(:@in_use).try_acquire
      end

      # need more!
      $logger.info "Allocating more SymbolTables"
      5.times do
        copy = SymbolTable.allocate
        copy.instance_variable_set(:@scopes, [@scopes[0]])
        copy.instance_variable_set(:@callstack, [@callstack[0]])
        copy.instance_variable_set(:@cfg_arch, @cfg_arch)
        copy.instance_variable_set(:@mxlen, @mxlen)
        copy.instance_variable_set(:@mutex, @mutex)
        copy.instance_variable_set(:@global_clone_pool, @global_clone_pool)
        copy.instance_variable_set(:@in_use, Concurrent::Semaphore.new(1))
        @global_clone_pool << copy
      end

      global_clone
    end

    def release
      @mutex.synchronize do
        pop while levels > 1
        raise "Clone isn't back in global scope" unless at_global_scope?
        raise "You are calling release on the frozen SymbolTable" if frozen?
        raise "Double release detected" unless in_use?

        @in_use.release
      end
    end

    def in_use? = @in_use.available_permits.zero?

    # @return [SymbolTable] a deep clone of this SymbolTable
    def deep_clone(clone_values: false, freeze_global: true)
      raise "don't do this" unless freeze_global

      # globals are frozen, so we can just return a shallow clone
      # if we are in global scope
      if levels == 1
        copy = dup
        copy.instance_variable_set(:@scopes, copy.instance_variable_get(:@scopes).dup)
        copy.instance_variable_set(:@callstack, copy.instance_variable_get(:@callstack).dup)
        return copy
      end

      copy = dup
      # back up the table to global scope
      copy.instance_variable_set(:@callstack, @callstack.dup)
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
