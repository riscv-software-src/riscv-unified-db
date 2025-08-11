# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "type"
require_relative "symbol_table"
require_relative "syntax_node"

module Idl

  # type, from ruby's perspective, of any IDL value
  BasicValueRbType = T.type_alias {
    T.any(
      Integer,    # Bits
      T::Boolean, # Boolean
      String,     # String
      T::Array[Integer],  # array of Bits
      T::Array[T::Boolean],  # array of Bools
      T::Array[String]    # array of strings
    )
  }

  ValueRbType = T.type_alias {
    T.any(
      BasicValueRbType,
      T::Hash[String, BasicValueRbType] # structs
    )
  }

  EMPTY_ARRAY = [].freeze

  # base class for all nodes considered part of the Ast
  # @abstract
  class AstNode
    extend T::Sig
    extend T::Helpers
    abstract!

    Bits1Type = Type.new(:bits, width: 1, qualifiers: [:known].freeze).freeze
    PossiblyUnknownBits1Type = Type.new(:bits, width: 1).freeze
    Bits32Type = Type.new(:bits, width: 32, qualifiers: [:known].freeze).freeze
    PossiblyUnknownBits32Type = Type.new(:bits, width: 32).freeze
    Bits64Type = Type.new(:bits, width: 64, qualifiers: [:known].freeze).freeze
    PossiblyUnknownBits64Type = Type.new(:bits, width: 64).freeze
    ConstBoolType = Type.new(:boolean, qualifiers: [:const]).freeze
    BoolType = Type.new(:boolean).freeze
    VoidType = Type.new(:void).freeze
    StringType = Type.new(:string).freeze

    # @return [String] Source input file
    sig { returns(Pathname) }
    attr_reader :input_file

    # @return [Integer] Starting line in the source input file (i.e., position 0 of {#input} in the file)
    sig { returns(Integer) }
    attr_reader :starting_line

    # @return [String] Source string
    sig { returns(String) }
    attr_reader :input

    # @return [Range] Range within the input for this node
    sig { returns(Range) }
    attr_reader :interval

    # @return [String] The IDL source of this node
    sig { returns(String) }
    attr_reader :text_value

    # @return [AstNode] The parent node
    # @return [nil] if this is the root of the tree
    sig { returns(T.nilable(AstNode)) }
    attr_reader :parent

    # @return [Array<AstNode>] Children of this node
    sig { returns(T::Array[AstNode]) }
    attr_reader :children

    # error that is thrown when compilation reveals a type error
    class TypeError < StandardError
      extend T::Sig

      # @return [String] The error message
      sig { returns(String) }
      attr_reader :what

      # The backtrace starting from the 'type_error' call site
      #
      # Note, this will be different (truncated) from #backtrace
      #
      # @return [Array<String>] The compiler backtrace at the error point
      sig { returns(T::Array[String]) }
      attr_reader :bt

      # @param what [String] Error message
      sig { params(what: String).void }
      def initialize(what)
        super(what)

        @what = what
        @bt = Kernel.caller

        # shift twice to get to the call site of 'type_error'
        @bt.shift
        @bt.shift
      end
    end

    # error that is thrown when the compiler hits an unrecoverable error (that needs fixed!)
    class InternalError < StandardError
      extend T::Sig

      # @return [String] The error message
      sig { returns(String) }
      attr_reader :what

      # The backtrace starting from the 'internal_error' call site
      #
      # Note, this will be different (truncated) from #backtrace
      #
      # @return [Array<String>] The compiler backtrace at the error point
      sig { returns(T::Array[String]) }
      attr_reader :bt

      sig { params(what: String).void }
      def initialize(what)
        super(what)

        @what = what
        @bt = Kernel.caller

        # shift twice to get to the call site of 'internal_error'
        @bt.shift
        @bt.shift
      end
    end

    # exception type raised when the value of IDL code is requested (via node.value(...)) but
    # cannot be provided because some part the code isn't known at compile time
    class ValueError < StandardError
      extend T::Sig

      sig { returns(Integer) }
      attr_reader :lineno

      sig { returns(String) }
      attr_reader :file

      sig { returns(String) }
      attr_reader :reason

      sig { params(lineno: Integer, file: String, reason: String).void }
      def initialize(lineno, file, reason)
        super(reason)
        @lineno = lineno
        @file = file
        @reason = reason
      end

      sig { returns(String) }
      def what = message

      sig { returns(String) }
      def message
        <<~WHAT
          In file #{file}
          On line #{lineno}
            A value error occurred
            #{reason}
        WHAT
      end
    end

    sig { params(block: T.proc.params(arg0: Object).returns(T.untyped)).returns(T.untyped) }
    def self.value_try(&block)
      catch(:value_error, &block)
    end
    sig { params(block: T.proc.params(arg0: Object).returns(T.untyped)).returns(T.untyped) }
    def value_try(&block) = self.class.value_try(&block)

    sig { params(value_result: T.untyped, _block: T.proc.returns(T.untyped)).returns(T.untyped) }
    def self.value_else(value_result, &_block)
      return unless value_result == :unknown_value

      yield
    end
    sig { params(value_result: T.untyped, block: T.proc.returns(T.untyped)).returns(T.untyped) }
    def value_else(value_result, &block) = self.class.value_else(value_result, &block)

    # is this node const evaluatable?
    # all nodes with a compile-time-known value are const_eval
    # not all const_eval nodes have a compile-time-known value; they may rely on an unknown parameter
    sig { abstract.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab); end

    # @param input [String] The source being compiled
    # @param interval [Range] The range in the source corresponding to this AstNode
    # @param children [Array<AstNode>] Children of this node
    sig { params(input: String, interval: Range, children: T::Array[AstNode]).void }
    def initialize(input, interval, children)
      @input = input
      @input_file = nil
      @starting_line = 0
      @interval = interval
      @text_value = input[interval]
      @children = children
      @parent = nil # will be set later unless this is the root
      @children.each { |child| child.instance_variable_set(:@parent, self) }
    end

    # Sets the input file for this syntax node unless it has already been set.
    #
    # If the input file has not been set, it will be set with the given filename and starting line number.
    #
    # @param [String] filename The name of the input file.
    # @param [Integer] starting_line The starting line number in the input file.
    sig { params(filename: T.any(Pathname, String), starting_line: Integer).void }
    def set_input_file_unless_already_set(filename, starting_line = 0)
      return unless @input_file.nil?

      @input_file = Pathname.new(filename)
      @starting_line = starting_line
      children.each do |child|
        child.set_input_file_unless_already_set(filename, starting_line)
      end
      raise "?" if @starting_line.nil?
    end

    # remember where the code comes from
    #
    # @param filename [String] Filename
    # @param starting_line [Integer] Starting line in the file
    sig { params(filename: T.any(Pathname, String), starting_line: Integer).void }
    def set_input_file(filename, starting_line = 0)
      @input_file = Pathname.new(filename)
      @starting_line = starting_line
      children.each do |child|
        child.set_input_file(filename, starting_line)
      end
      raise "?" if @starting_line.nil?
    end

    # @return [Integer] the current line number
    sig { returns(Integer) }
    def lineno
      T.must(input[0..interval.first]).count("\n") + 1 + (@starting_line.nil? ? 0 : @starting_line)
    end

    # @return [AstNode] the first ancestor that is_a?(+klass+)
    # @return [nil] if no ancestor is found
    sig { params(klass: Class).returns(T.nilable(AstNode)) }
    def find_ancestor(klass)
      if @parent.nil?
        nil
      elsif @parent.is_a?(klass)
        @parent
      else
        @parent.find_ancestor(klass)
      end
    end

    class LinesDescriptor < T::Struct
      const :lines, String
      const :problem_interval, Range
      const :lines_interval, Range
    end

    # @return [String] returns +-2 lines around the current interval
    sig { returns(LinesDescriptor) }
    def lines_around
      cnt = 0
      interval_start = interval.min
      while cnt < 2
        cnt += 1 if input[interval_start] == "\n"
        break if interval_start.zero?

        interval_start -= 1
      end

      cnt = 0
      interval_end = interval.max
      while cnt < 3
        cnt += 1 if input[interval_end] == "\n"
        break if interval_end >= (input.size - 1)
        break if cnt == 3

        interval_end += 1
      end

      LinesDescriptor.new(
        lines: T.must(input[interval_start..interval_end]),
        problem_interval: (interval.min - interval_start..interval.max - interval_start),
        lines_interval: (interval_start + 1)..interval_end
      )
    end

    sig { params(reason: String).void }
    def truncation_warn(reason)
      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
          A value was truncated
          #{reason}.
          Perhaps you want to use a widening operator (`+, `-, `*, `<<)?
      WHAT
      warn msg
    end

    # raise a type error
    #
    # @param reason [String] Error message
    # @raise [AstNode::TypeError] always
    sig { params(reason: String).returns(T.noreturn) }
    def type_error(reason)
      lines_desc = lines_around
      lines = lines_desc.lines
      problem_interval = lines_desc.problem_interval
      lines_interval = lines_desc.lines_interval

      lines =
        if $stdout.isatty
          [
            lines[0...problem_interval.min],
            "\u001b[31m",
            lines[problem_interval],
            "\u001b[0m",
            lines[(problem_interval.max + 1)..]
          ].join("")
        else
          [
            lines[0...problem_interval.min],
            "**HERE** >> ",
            lines[problem_interval],
            " << **HERE**",
            lines[(problem_interval.max + 1)..]
          ].join("")
        end

      starting_lineno = T.must(input[0..lines_interval.min]).count("\n")
      lines = lines.lines.map do |line|
        starting_lineno += 1
        "#{@starting_line + starting_lineno - 1}: #{line}"
      end.join("")

      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
        In the code:

          #{lines.gsub("\n", "\n  ")}

        A type error occurred
          #{$stdout.isatty ? "\u001b[31m#{reason}\u001b[0m" : reason}
      WHAT
      raise AstNode::TypeError, msg
    end

    # raise an internal error
    #
    # @param reason [String] Error message
    # @raise [AstNode::TypeError] always
    sig { params(reason: String).returns(T.noreturn) }
    def internal_error(reason)
      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
          An internal error occurred
          #{reason}
      WHAT
      raise AstNode::InternalError, msg
    end

    @value_error_reason = nil
    @value_error_ast = nil
    class << self
      attr_accessor :value_error_reason, :value_error_ast
    end

    # raise a value error, indicating that the value is not known at compile time
    #
    # @param reason [String] Error message
    # @raise [AstNode::ValueError] always
    sig { params(reason: String, ast: T.nilable(AstNode)).returns(T.noreturn) }
    def self.value_error(reason, ast = nil)
      AstNode.value_error_reason = reason
      AstNode.value_error_ast = ast
      # warn reason
      # warn "At #{ast.input_file}:#{ast.lineno}" unless ast.nil?
      throw(:value_error, :unknown_value)
      #raise AstNode::ValueError.new(lineno, input_file, reason), reason, []
    end
    sig { params(reason: String).returns(T.noreturn) }
    def value_error(reason) = self.class.value_error(reason, self)

    # unindent a multiline string, getting rid of all common leading whitespace (like <<~ heredocs)
    #
    # borrowed from https://stackoverflow.com/questions/33527064/multiline-strings-with-no-indent
    #
    # @param s [String] A string (presumably with newlines)
    # @return [String] Unindented string
    sig { params(s: String).returns(String) }
    def unindent(s)
      s.gsub(%r{^#{s.scan(/^[ \t]+(?=\S)/).min}}, "")
    end

    # pretty print the AST rooted at this node
    #
    # @param indent [Integer] The starting indentation, in # of spaces
    # @param indent_size [Integer] The extra indentation applied to each level of the tree
    # @param io [IO] Where to write the output
    sig { params(indent: Integer, indent_size: Integer, io: IO).void }
    def print_ast(indent = 0, indent_size: 2, io: $stdout)
      io.puts "#{' ' * indent}#{self.class.name}:"
      children.each do |node|
        node.print_ast(indent + indent_size, indent_size:)
      end
    end

    # @!macro [new] freeze_tree
    #
    #   freeze the entire tree from further modification
    #   This is also an opportunity to pre-calculate anything that only needs global symbols
    #
    #   @param global_symtab [SymbolTable] Symbol table with global scope populated


    # @!macro freeze_tree
    sig { params(global_symtab: SymbolTable).returns(AstNode) }
    def freeze_tree(global_symtab)
      return self if frozen?

      @children.each { |child| child.freeze_tree(global_symtab) }
      freeze
    end

    # @return [String] A string representing the path to this node in the tree
    sig { returns(String) }
    def path
      if @parent.nil?
        "#{self.class.name}"
      else
        "#{@parent.path}.#{self.class.name}"
      end
    end

    # @!macro [new] type_check
    #   type check this node and all children
    #
    #   Calls to {#type} and/or {#value} may depend on type_check being called first
    #   with the same symtab. If not, those functions may raise an AstNode::InternalError
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @raise [AstNode::TypeError] if there is a type error
    #   @raise [AstNode::InternalError] if there is an internal compiler error during type check
    #   @return [void]

    # @!macro type_check
    # @abstract
    sig { abstract.params(symtab: SymbolTable).void }
    def type_check(symtab); end

    # @!macro [new] to_idl
    #   Return valid IDL representation of the node (and its subtree)
    #
    #   @return [String] IDL code for the node

    # @!macro to_idl
    # @abstract
    sig { abstract.returns(String) }
    def to_idl; end

    sig { overridable.returns(String) }
    def to_idl_verbose = to_idl

    sig { returns(String) }
    def inspect = self.class.name.to_s
  end

  # interface for nodes that can be executed, but don't have a value (e.g., statements)
  module Executable
    extend T::Sig
    extend T::Helpers
    interface!

    # @!macro [new] execute
    #   "execute" the statement by updating the variables in the symbol table
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if some part of the statement cannot be executed at compile time
    #   @return [void]

    # @!macro [new] execute_unknown
    #   "execute" the statement, forcing any variable assignments to an unknown state
    #   This is used down unknown conditional paths.
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if some part of the statement cannot be executed at compile time
    #   @return [void]

    # @!macro execute
    sig { abstract.params(symtab: SymbolTable).void }
    def execute(symtab); end

    # @!macro execute_unknown
    sig { abstract.params(symtab: SymbolTable).void }
    def execute_unknown(symtab); end
  end

  ExecutableAst = T.type_alias { T.all(Executable, AstNode) }

  # interface for nodes that *might* return a value in a function body
  module Returns
    extend T::Sig
    extend T::Helpers
    abstract!

    # @!macro [new] return_value
    #   Evaluate the compile-time return value of this node, or, if the node does not return
    #   (e.g., because it is an IfAst but there is no return on the taken path), execute the node
    #   and update the symtab
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if, during evaluation, a node without a compile-time value is found
    #   @return [Integer] The return value, if it is integral
    #   @return [Boolean] The return value, if it is boolean
    #   @return [nil]     if the return value is not compile-time-known

    # returns the return type, or nil if the type is void
    sig { abstract.params(symtab: SymbolTable).returns(Type) }
    def return_type(symtab); end

    # @!macro return_value
    # return value or nil if there is no return in a potentionally-returning node (like an if body)
    sig { abstract.params(symtab: SymbolTable).returns(T.nilable(ValueRbType)) }
    def return_value(symtab); end

    # @!macro [new] return_values
    #   Evaluate all possible compile-time return values of this node, or, if the node does not return
    #   (e.g., because it is an IfAst but there is no return on a possible path), execute the node
    #   and update the symtab
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if, during evaluation, a node without a compile-time value is found
    #   @return [Array<Integer>] The possible return values. Will be an empty array if there are no return values
    #   @return [Array<Boolean>] The possible return values. Will be an empty array if there are no return values

    # @!macro return_values
    sig { abstract.params(symtab: SymbolTable).returns(T::Array[ValueRbType]) }
    def return_values(symtab); end

    # @return [Type] The expected return type (as defined by the encolsing function)
    sig { params(symtab: SymbolTable).returns(Type) }
    def expected_return_type(symtab)
      T.bind(self, AstNode) # let Sorbet know this is always executed by an AstNode

      func_def = T.cast(find_ancestor(FunctionDefAst), T.nilable(FunctionDefAst))
      if func_def.nil?
        if symtab.get("__expected_return_type").nil?
          internal_error "Forgot to set __expected_return_type in the symbol table"
        end

        symtab.get("__expected_return_type")
      else
        global_symtab = symtab.global_clone
        global_symtab.push(nil)
        if func_def.templated?
          # add template vars
          ttypes = func_def.template_types(global_symtab)
          func_def.template_names.each_with_index do |tname, i|
            global_symtab.add!(tname, Var.new(tname, ttypes[i], template_index: i))
          end
        end
        rtype = func_def.return_type(global_symtab)
        global_symtab.release
        rtype
        # # need to find the type to get the right symbol table
        # func_type = @func_type_cache[symtab.name]
        # return func_type.return_type(EMPTY_ARRAY, self) unless func_type.nil?

        # func_type = symtab.get_global(func_def.name)
        # internal_error "Couldn't find function type for '#{func_def.name}'" if func_type.nil?

        # # to get the return type, we need to find the template values in case this is
        # # a templated function definition
        # #
        # # that information should be up the stack in the symbol table
        # if func_type.templated?
        #   template_values = symtab.find_all(single_scope: true) do |o|
        #     o.is_a?(Var) && o.template_value_for?(func_def.name)
        #   end
        #   unless template_values.size == func_type.template_names.size
        #     internal_error "Did not find correct number of template arguments (found #{template_values.size}, need #{func_type.template_names.size}) #{symtab.keys_pretty}"
        #   end
        #   func_type.return_type(template_values.sort { |a, b| a.template_index <=> b.template_index }.map(&:value), self)
        # else
        #   @func_type_cache[symtab.name]= func_type
        #   func_type.return_type(EMPTY_ARRAY, self)
        # end
      end
    end
  end

  # interface for R-values (e.g., expressions that have a value)
  module Rvalue
    extend T::Sig
    extend T::Helpers
    abstract!

    # @!macro [new] type
    #  Given a specific symbol table, return the type of this node.
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #  @param symtab [SymbolTable] Symbol table for lookup
    #  @return [Type] The type of the node
    #  @raise [AstNode::InternalError] if the type is dependent on symtab, and type_check was not called first

    # @!macro [new] type_no_args
    #  Return the type of this node
    #
    #  @param _symtab [SymbolTable] Not used
    #  @return [Type] The type of the node

    # @!macro type
    # @abstract
    sig { abstract.params(symtab: SymbolTable).returns(Type) }
    def type(symtab); end

    # @!macro [new] value
    #   Return the compile-time-known value of the node
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @return [Integer] if the compile-time-known value is integral
    #   @return [Boolean] if the compile-time-known value is a boolean
    #   @raise [AstNode::ValueError] if the value is not knowable at compile time
    #   @raise [AstNode::InternalError] if the value is dependent on symtab, and type_check was not called first

    # @!macro [new] value_no_args
    #   Return the compile-time-known value of the node
    #
    #   @param _symtab [SymbolTable] Not used
    #   @return [Integer] if the compile-time-known value is an integer
    #   @return [Boolean] if the compile-time-known value is a boolean
    #   @raise [AstNode::ValueError] if the value is not knowable at compile time

    # @!macro value
    # @abstract
    sig { abstract.params(symtab: SymbolTable).returns(ValueRbType) }
    def value(symtab); end

    sig { params(symtab: SymbolTable).returns(T.any(Integer, Symbol)) }
    def max_value(symtab)
      value_result = T.cast(self, AstNode).value_try do
        return T.cast(T.must(value(symtab)), T.any(Integer, Symbol))
      end
      T.cast(self, AstNode).value_else(value_result) do
        return :unknown
      end
    end

    sig { params(symtab: SymbolTable).returns(T.any(Integer, Symbol)) }
    def min_value(symtab)
      value_result = T.cast(self, AstNode).value_try do
        return T.cast(T.must(value(symtab)), T.any(Integer, Symbol))
      end
      T.cast(self, AstNode).value_else(value_result) do
        return :unknown
      end
    end

    # @!macro [new] values
    #  Return a complete list of possible compile-time-known values of the node, or raise a ValueError if
    #  the full list cannot be determined
    #
    #  For most AstNodes, this will just be a single-entry array
    #
    #  @param symtab [SymbolTable] The context for the evaluation
    #  @return [Array<Integer>] The complete list of compile-time-known values, when they are integral
    #  @return [Array<Boolean>] The complete list of compile-time-known values, when they are booleans
    #  @return [AstNode::ValueError] if the list of values is not knowable at compile time

    # @!macro values
    sig { params(symtab: SymbolTable).returns(T::Array[ValueRbType]) }
    def values(symtab) = [value(symtab)]

    sig { params(value: Integer, width: Integer, signed: T::Boolean).returns(Integer) }
    def truncate(value, width, signed)
      masked = value & ((1 << width) - 1)
      if signed
        # signed: need to mask and convert
        if masked[width - 1] == 1
          # twos compliment value is 2^width - value
          -((1 << width) - masked)
        else
          masked
        end
      else
        # unsigned: simple truncation
        masked
      end
    end
  end

  RvalueAst = T.type_alias { T.all(Rvalue, AstNode) }

  # interface for any AstNode that introduces a new symbol into scope
  module Declaration
    extend T::Sig
    extend T::Helpers
    interface!

    # @!macro [new] add_symbol
    #  Add symbol(s) at the outermost scope of the symbol table
    #
    #  @param symtab [SymbolTable] Symbol table at the scope that the symbol(s) will be inserted
    sig { abstract.params(symtab: SymbolTable).void }
    def add_symbol(symtab); end
  end

  class IncludeStatementSyntaxNode < SyntaxNode
    sig { override.returns(IncludeStatementAst) }
    def to_ast
      s = T.let(send(:string), StringLiteralSyntaxNode)
      IncludeStatementAst.new(input, interval, s.to_ast)
    end
  end

  class IncludeStatementAst < AstNode
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    # @return [String] filename to include
    sig { returns(String) }
    def filename = T.must(@children[0]).text_value[1..-2] || ""

    sig { params(input: String, interval: Range, filename: AstNode).void }
    def initialize(input, interval, filename)
      super(input, interval, [filename])
    end

    sig { override.returns(String) }
    def to_idl = "include \"#{filename}\""

    sig { override.params(symtab: SymbolTable).void }
    def type_check(symtab); end
  end

  class IdSyntaxNode < SyntaxNode
    def to_ast = IdAst.new(input, interval)
  end

  # an identifier
  #
  # Used for variables
  class IdAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = const? || symtab.get(name).const_eval?

    # @return [String] The ID name
    sig { returns(String) }
    def name = text_value

    sig { params(input: String, interval: T::Range[Integer]).void }
    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @const = T.let((text_value[0] == T.must(text_value[0]).upcase), T::Boolean)
    end

    # @!macro type_check
    def type_check(symtab)
      type_error "no symbol named '#{name}' on line #{lineno}" if symtab.get(name).nil?
    end

    # @!macro type
    sig { override.params(symtab: SymbolTable).returns(Type) }
    def type(symtab)
      return @type unless @type.nil?

      type_error "Symbol '#{name}' not found" if symtab.get(name).nil?

      sym = symtab.get(name)
      # @type =
      if sym.is_a?(Type)
        sym
      elsif sym.is_a?(Var)
        sym.type
      else
        internal_error "Unexpected object on the symbol table"
      end
    end

    # @return [Boolean] whether or not the Id represents a const
    sig { returns(T::Boolean) }
    def const? = @const

    # @!macro value
    def value(symtab)
      var = symtab.get(name)

      type_error "Variable '#{name}' was not found" if var.nil?

      value_error "Value of '#{name}' not known" if var.value.nil?

      v = var.value
      value_error "Value of #{name} is unknown" if v == :unknown
      v
    end

    sig { override.params(symtab: SymbolTable).returns(T.any(Integer, Symbol)) }
    def max_value(symtab)
      max = T.let(:unknown, T.any(Integer, Symbol))
      value_result = value_try do
        max = value(symtab)
      end
      value_else(value_result) do
        var = symtab.get(name)
        if !var.nil? && var.param?
          param = T.must(symtab.param(text_value))
          if param.schema.max_val_known?
            max = param.schema.max_val
          end
        end
      end
      max
    end

    sig { override.params(symtab: SymbolTable).returns(T.any(Integer, Symbol)) }
    def min_value(symtab)
      min = T.let(:unknown, T.any(Integer, Symbol))
      value_result = value_try do
        min = value(symtab)
      end
      value_else(value_result) do
        var = symtab.get(name)
        if !var.nil? && var.param?
          param = T.must(symtab.param(text_value))
          if param.schema.min_val_known?
            min = param.schema.min_val
          end
        end
      end
      min
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = name
  end

  class GlobalWithInitializationSyntaxNode < SyntaxNode
    def to_ast
      GlobalWithInitializationAst.new(input, interval, send(:single_declaration_with_initialization).to_ast)
    end
  end

  # global variable declared with an initializer,
  #
  # e.g.,
  #
  # Bits<65> UNDEFINED_LEGAL = 65'h10000000000000000;
  # Bits<FLEN> f[32] = [0, 0, 0, 0, 0, 0, 0, 0,
  #                     0, 0, 0, 0, 0, 0, 0, 0,
  #                     0, 0, 0, 0, 0, 0, 0, 0,
  #                     0, 0, 0, 0, 0, 0, 0, 0];
  class GlobalWithInitializationAst < AstNode
    include Executable
    include Declaration

    def id = var_decl_with_init.id
    def rhs = var_decl_with_init.rhs

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = var_decl_with_init.lhs.const? && var_decl_with_init.rhs.const_eval?(symtab)

    # @return [VariableDeclarationWithInitializationAst] The initializer
    def var_decl_with_init
      @children[0]
    end

    def initialize(input, interval, var_decl_with_init)
      super(input, interval, [var_decl_with_init])
      var_decl_with_init.make_global
    end

    # @1macro type_check
    def type_check(symtab)
      var_decl_with_init.type_check(symtab)
    end

    # @1macro type
    def type(symtab)
      var_decl_with_init.lhs_type(symtab)
    end

    # @1macro value
    def value(symtab)
      var_decl_with_init.value(symtab)
    end

    sig { override.params(symtab: SymbolTable).void }
    def execute(symtab) = var_decl_with_init.execute(symtab)

    sig { override.params(symtab: SymbolTable).void }
    def execute_unknown(symtab) = var_decl_with_init.execute_unknown(symtab)

    sig { override.params(symtab: SymbolTable).void }
    def add_symbol(symtab)
      raise "Symtab should be at global scope" unless symtab.levels == 1

      # globals never have a compile-time value
      var_decl_with_init.add_symbol(symtab)
    end

    # @1macro to_idl
    sig { override.returns(String) }
    def to_idl
      var_decl_with_init.to_idl
    end
  end

  class GlobalSyntaxNode < SyntaxNode
    def to_ast
      GlobalAst.new(input, interval, send(:declaration).to_ast)
    end
  end

  class GlobalAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = declaration.id.const? # default initialization gives a value

    def id
      declaration.id.text_value
    end

    # @return [VariableDeclarationAst] The decl
    def declaration
      @children[0]
    end

    def initialize(input, interval, declaration)
      super(input, interval, [declaration])
      declaration.make_global
    end

    def type_check(symtab)
      declaration.type_check(symtab)
    end

    def type(symtab)
      declaration.type(symtab)
    end

    def add_symbol(symtab)
      internal_error "Should be at global scope" unless symtab.levels == 1

      declaration.add_symbol(symtab)
    end

    sig { override.returns(String) }
    def to_idl = declaration.to_idl
  end

  # @api private
  class IsaSyntaxNode < SyntaxNode
    def to_ast
      IsaAst.new(
        input,
        interval,
        send(:definitions).elements.reject do |e|
          e.elements.all?(&:space?)
        end.map(&:to_ast)
      )
    end
  end

  # top-level AST node
  class IsaAst < AstNode
    def definitions = children

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    # @return [Array<AstNode>] List of all global variable definitions
    def globals = definitions.select { |d| d.is_a?(GlobalWithInitializationAst) || d.is_a?(GlobalAst) }

    # @return {Array<AstNode>] List of all enum definitions
    def enums = definitions.select { |e| e.is_a?(EnumDefinitionAst) || e.is_a?(BuiltinEnumDefinitionAst) }

    # @return {Array<AstNode>] List of all bitfield definitions
    def bitfields = definitions.grep(BitfieldDefinitionAst)

    # @return [Array<AstNode>] List of all struct definitions
    def structs = definitions.grep(StructDefinitionAst)

    # @return [Array<AstNode>] List of all function definitions
    def functions = definitions.grep(FunctionDefAst)

    # @return [FetchAst] Fetch body
    def fetch = definitions.grep(FetchAst)[0]

    # Add all the global symbols to symtab
    #
    # @param symtab [SymbolTable] symbol table
    def add_global_symbols(symtab)
      raise "Symtab is not at global scope" unless symtab.levels == 1

      enums.each { |g| g.add_symbol(symtab); }
      bitfields.each { |g| g.add_symbol(symtab) }
      globals.each { |g| g.add_symbol(symtab) }
      structs.each { |g| g.add_symbol(symtab) }
      functions.each { |g| g.add_symbol(symtab) }
    end

    # replaces an include statement with the ast in that file, making
    # it a direct child of this IsaAst
    #
    # @param include_ast [IncludeStatementAst] The include, which must be a child of this IsaAst
    # @Param isa_ast [IsaAst] The result of compiling the include
    def replace_include!(include_ast, isa_ast)
      # find the index of the child
      idx = children.index(include_ast)
      internal_error "Can't find include ast in children" if idx.nil?

      @children[idx] = isa_ast.children
      @children.flatten!
    end

    # @!macro type_check
    def type_check(symtab)
      definitions.each { |d| d.type_check(symtab) }

      fetch_blocks = definitions.grep(FetchAst)
      type_error "Multiple fetch blocks defined" if fetch_blocks.size > 1
      type_error "No fetch block defined" if fetch_blocks.size.zero?
    end

    sig { override.returns(String) }
    def to_idl
      <<~IDL
        %version 1.0

        #{globals.map(&:to_idl).join("\n")}
        #{enums.map(&:to_idl).join("\n")}
        #{bitfields.map(&:to_idl).join("\n")}
        #{structs.map(&:to_idl).join("\n")}
        #{functions.map(&:to_idl).join("\n")}
        #{fetch.to_idl}
      IDL
    end
  end

  class ArraySizeSyntaxNode < SyntaxNode
    def to_ast
      ArraySizeAst.new(input, interval, send(:expression).to_ast)
    end
  end

  class ArraySizeAst < AstNode
    # @return [AstNode] Array expression
    def expression = children[0]

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, expression)
      super(input, interval, [expression])
    end

    def type_check(symtab)
      expression.type_check(symtab)
      expression_type = expression.type(symtab)
      type_error "#{expression.text_value} is not an array" unless expression_type.kind == :array
      type_error "#{expression.text_value} must be a constant" unless expression_type.const?
    end

    def type(symtab)
      if expression.type(symtab).width == :unknown
        Type.new(:bits, width: :unknown, qualifiers: [:const, :known])
      else
        len = expression.type(symtab).width.bit_length
        len = len.zero? ? 1 : len
        Type.new(:bits, width: len, qualifiers: [:const, :known])
      end
    end

    def value(symtab)
      expression.type(symtab).width
    end

    sig { override.returns(String) }
    def to_idl = "$array_size(#{expression.to_idl})"
  end


  class EnumSizeSyntaxNode < SyntaxNode
    def to_ast
      EnumSizeAst.new(input, interval, send(:user_type_name).to_ast)
    end
  end

  # represents the builtin that returns the nymber of elements in an enum class
  #
  #  $enum_size(XRegWidth) #=> 2
  class EnumSizeAst < AstNode
    def enum_class = children[0]

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, enum_class_name)
      super(input, interval, [enum_class_name])
    end

    def type_check(symtab)
      enum_class.type_check(symtab)
    end

    def type(symtab)
      Type.new(
        :bits,
        width: enum_class.type(symtab).element_names.size.bit_length,
        qualifiers: [:const, :known]
      )
    end

    def value(symtab)
      enum_class.type(symtab).element_names.size
    end

    sig { override.returns(String) }
    def to_idl = "$enum_size(#{enum_class.to_idl})"
  end

  class EnumElementSizeSyntaxNode < SyntaxNode
    def to_ast
      EnumElementSizeAst.new(input, interval, send(:user_type_name).to_ast)
    end
  end

  # represents the builtin that returns the bitwidth of an element in an enum class
  #
  #  $enum_element_size(PrivilegeMode) #=> 3
  class EnumElementSizeAst < AstNode
    def enum_class = children[0]

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, enum_class_name)
      super(input, interval, [enum_class_name])
    end

    def type_check(symtab)
      enum_class.type_check(symtab)
    end

    def type(symtab)
      Type.new(:bits, width: enum_class.type(symtab).width, qualifiers: [:const, :known])
    end

    def value(symtab)
      enum_class.type(symtab).width
    end

    sig { override.returns(String) }
    def to_idl = "$enum_element_size(#{enum_class.to_idl})"
  end

  class EnumCastSyntaxNode < SyntaxNode
    def to_ast
      EnumCastAst.new(input, interval, send(:user_type_name).to_ast, send(:expression).to_ast)
    end
  end

  class EnumCastAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    # @return [UserTypeAst] Enum name
    def enum_name = @children[0]

    # @return [Rvalue] Value expression
    def expression = @children[1]

    def initialize(input, interval, user_type_name, expression)
      super(input, interval, [user_type_name, expression])
    end

    def type_check(symtab)
      enum_name.type_check(symtab)
      expression.type_check(symtab)

      if expression.type(symtab).kind != :bits
        type_error "Can only cast from Bits<N> to enum"
      end

      enum_def_type = symtab.get(enum_name.text_value)
      type_error "No enum named #{enum_name.text_value}" if enum_def_type.nil?

      value_try do
        unless enum_def_type.element_values.include?(expression.value(symtab))
          type_error "#{expression.value(symtab)} is not a value in enum #{enum_name.text_value}"
        end
      end
    end

    def type(symtab)
      enum_def_type = symtab.get(enum_name.text_value)
      Type.new(:enum_ref, enum_class: enum_def_type)
    end

    def value(symtab) = expression.value(symtab)

    sig { override.returns(String) }
    def to_idl = "$enum(#{enum_name.to_idl}, #{expression.to_idl})"
  end

  class EnumArrayCastSyntaxNode < SyntaxNode
    def to_ast
      EnumArrayCastAst.new(input, interval, send(:user_type_name).to_ast)
    end
  end

  # represents the builtin that returns an array with all elements of an Enum type
  #
  #  $enum_to_a(PrivilegeMode) #=> [3, 1, 1, 0, 5, 4]
  class EnumArrayCastAst < AstNode
    def enum_class = children[0]

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, enum_class_name)
      super(input, interval, [enum_class_name])
    end

    def type_check(symtab)
      enum_class.type_check(symtab)
    end

    def type(symtab)
      Type.new(
        :array,
        width: enum_class.type(symtab).element_values.size,
        sub_type: Type.new(:bits, width: enum_class.type(symtab).width, qualifiers: [:const, :known]),
        qualifiers: [:const]
      )
    end

    def value(symtab)
      enum_class.type(symtab).element_values
    end

    sig { override.returns(String) }
    def to_idl = "$enum_to_a(#{enum_class.to_idl})"
  end

  class EnumDefinitionSyntaxNode < SyntaxNode
    def to_ast
      values = []

      send(:e).elements.each do |e|
        if e.i.empty?
          values << nil
        else
          values << e.i.int.to_ast
        end
      end

      EnumDefinitionAst.new(
        input,
        interval,
        send(:user_type_name).to_ast,
        send(:e).elements.map { |entry| entry.user_type_name.to_ast },
        values
      )
    end
  end

  # Node representing an IDL enum definition
  #
  #  # this will result in an EnumDefinitionAst
  #  enum PrivilegeMode {
  #    M  0b011
  #    S  0b001
  #    HS 0b001 # alias for S when H extension is used
  #    U  0b000
  #    VS 0b101
  #    VU 0b100
  #  }
  class EnumDefinitionAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, user_type, element_names, element_values)
      super(input, interval, [user_type] + element_names + element_values.reject { |e| e.nil? })
      @user_type = user_type
      @element_name_asts = element_names
      @element_value_asts = element_values

      next_auto_value = 0
      @element_values = T.let([], T::Array[Integer])

      @element_value_asts.each do |e|
        if e.nil?
          @element_values << next_auto_value
          next_auto_value += 1
        else
          @element_values << e.value(nil)
          next_auto_value = T.must(@element_values.last) + 1
        end
      end

      @type = EnumerationType.new(name, self.element_names, self.element_values)
    end

    # @return [Array<String>] Array of all element names, in the same order as those from {#element_values}
    sig { returns(T::Array[String]) }
    def element_names
      return @element_names unless @element_names.nil?

      @element_names = @element_name_asts.map(&:text_value)
    end

    # @return [Array<Integer>]
    #    Array of all element values, in the same order as those from {#element_names}.
    #    All values will be assigned their final values, even those with auto-numbers
    sig { returns(T::Array[Integer]) }
    def element_values = @element_values

    # @!macro type_check
    def type_check(symtab)
      @element_value_asts.each do |e|
        unless e.nil?
          e.type_check(symtab)
        end
      end

      add_symbol(symtab)
      @user_type.type_check(symtab)
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      internal_error "All enums should be declared in global scope" unless symtab.levels == 1

      internal_error "Type is nil?" if type(symtab).nil?
      symtab.add!(name, type(symtab))
    end

    # @!macro type_no_args
    def type(symtab)
      @type
    end

    # @!macro value_no_args
    def value(_symtab) = raise InternalError, "Enum definitions have no value"

    # @return [String] enum name
    def name = @user_type.text_value

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      idl = "enum #{name} { "
      element_names.each_index do |idx|
        idl << "#{element_names[idx]} #{element_values[idx]} "
      end
      idl << "}"
      idl
    end
  end

  class BuiltinEnumDefinitionSyntaxNode < SyntaxNode
    def to_ast
      BuiltinEnumDefinitionAst.new(input, interval, send(:user_type_name).to_ast)
    end
  end

  # represents a builtin (auto-generated from config) enum definition
  #
  #   # this will result in a BuiltinEnumDefinitionAst
  #   generated enum ExtensionName
  #
  class BuiltinEnumDefinitionAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, user_type)
      super(input, interval, [user_type])
      @user_type = user_type
    end

    # @!macro type_check_no_args
    def type_check(symtab)
      sym = symtab.get(@user_type.text_value)
      type_error "Builtin enum #{@user_type.text_value} is not defined" if sym.nil?
      type_error "#{@user_type.text_value} is not an enum" unless sym.is_a?(EnumerationType)
      type_error "#{@user_type.text_value} is not a builtin enum" unless sym.builtin?
    end

    def element_names(symtab)
      type(symtab).element_names
    end

    def element_values(symtab)
      type(symtab).element_values
    end

    # @!macro type
    def type(symtab)
      symtab.get(@user_type.text_value)
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      # doesn't actually do anything since the type has already been added to the symbol table
    end

    # @return [String] name of the enum class
    def name = @user_type.text_value

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "generated enum #{@user_type.text_value}"
  end

  class BitfieldFieldDefinitionAst < AstNode
    # @return [String] The field name
    attr_reader :name

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, name, msb, lsb)
      if lsb.nil?
        super(input, interval, [msb])
      else
        super(input, interval, [msb, lsb])
      end

      @name = name
      @lsb = lsb
      @msb = msb
    end

    # @!macro type_check
    def type_check(symtab)
      @msb.type_check(symtab)

      value_result = value_try do
        @msb.value(symtab)
      end
      value_else(value_result) do
        @msb.type_error "Bitfield position must be compile-time-known"
      end

      return if @lsb.nil?

      @lsb.type_check(symtab)
      value_result = value_try do
        @lsb.value(symtab)
      end
      value_else(value_result) do
        @lsb.type_error "Bitfield position must be compile-time-known"
      end
    end

    # @return Range The field's location in the bitfield
    def range(symtab)
      if @lsb.nil?
        @msb.value(symtab)..@msb.value(symtab)
      else
        @lsb.value(symtab)..@msb.value(symtab)
      end
    end

    sig { override.returns(String) }
    def to_idl
      if @lsb.nil?
        "#{@name} #{@msb.to_idl}"
      else
        "#{@name} #{@msb.to_idl}-#{@lsb.to_idl}"
      end
    end
  end

  class BitfieldDefinitionSyntaxNode < SyntaxNode
    def to_ast
      fields = []
      send(:e).elements.each do |f|
        fields << BitfieldFieldDefinitionAst.new(f.input, f.interval, f.field_name.text_value, f.range.int.to_ast, f.range.lsb.empty? ? nil : f.range.lsb.int.to_ast)
      end
      BitfieldDefinitionAst.new(input, interval, send(:user_type_name).to_ast, send(:int).to_ast, fields)
    end
  end

  # represents a bitfield definition
  #
  #  # this will result in a BitfieldDefinitionAst
  #  bitfield (64) Sv39PageTableEntry {
  #    N 63
  #    PBMT 62-61
  #    Reserved 60-54
  #    PPN2 53-28
  #    PPN1 27-19
  #    PPN0 18-10
  #    PPN 53-10 # in addition to the components, we define the entire PPN
  #    RSW  9-8
  #    D 7
  #    A 6
  #    G 5
  #    U 4
  #    X 3
  #    W 2
  #    R 1
  #    V 0
  #  }
  class BitfieldDefinitionAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, name, size, fields)
      super(input, interval, [name, size] + fields)

      @name = name
      @size = size
      @fields = fields
    end

    # @!macro freeze_tree
    def freeze_tree(global_symtab)
      return if frozen?

      type(global_symtab)

      @children.each { |child| child.freeze_tree(global_symtab) }

      freeze
    end

    # @return [Integer] The number of bits in the Bitfield
    def size(symtab)
      @size.value(symtab)
    end

    # @return [Array<String>] Array of all element names, in the same order as those from {#element_ranges}
    def element_names
      return @element_names unless @element_names.nil?

      @element_names = @fields.map(&:name)
    end

    # @return [Array<Range>]
    #    Array of all element ranges, in the same order as those from {#element_names}.
    def element_ranges(symtab)
      return @element_ranges unless @element_ranges.nil?

      @element_ranges = @fields.map { |f| f.range(symtab) }
    end

    # @!macro type_check
    def type_check(symtab)
      @size.type_check(symtab)
      @fields.each do |f|
        f.type_check(symtab)
        r = f.range(symtab)
        type_error "Field position (#{r}) is larger than the bitfield width (#{@size.value(symtab)} #{@size.text_value})" if r.first >= @size.value(symtab)
      end

      add_symbol(symtab)
      @name.type_check(symtab)
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      internal_error "All Bitfields should be declared at global scope" unless symtab.levels == 1

      t = type(symtab)
      internal_error "Type is nil" if t.nil?

      symtab.add!(name, t)
    end

    # @!macro type_no_args
    def type(symtab)
      return @type unless @type.nil?

      @type = BitfieldType.new(
        name,
        @size.value(symtab),
        element_names,
        element_ranges(symtab)
      )
    end

    # @return [String] bitfield name
    def name = @name.text_value

    # @!macro value_no_args
    def value(_symtab) = raise AstNode::InternalError, "Bitfield definitions have no value"

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      idl = ["bitfield (#{@size.to_idl}) #{@name.to_idl} { "]
      @fields.each do |f|
        idl << f.to_idl
      end
      idl << "}"
      idl.join("\n")
    end
  end

  class StructDefinitionSyntaxNode < SyntaxNode
    def to_ast
      member_types = []
      member_names = []
      send(:member).elements.each do |m|
        member_types << m.type_name.to_ast
        member_names << m.id.text_value
      end
      StructDefinitionAst.new(input, interval, send(:user_type_name).text_value, member_types, member_names)
    end
  end

  # Structure declaration
  #
  # for example, this maps to a StructDefinitionAst:
  #
  # struct TranslationResult {
  #   Bits<PHYS_ADDR_SIZE> paddr;
  #   Pbmt pbmt;
  #   ...
  # }
  class StructDefinitionAst < AstNode
    include Declaration

    # @return [String] Struct name
    attr_reader :name

    # @return [Array<AstNode>] Types of each member
    attr_reader :member_types

    # @return [Array<String>] Member names
    attr_reader :member_names

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval, name, member_types, member_names)
      super(input, interval, member_types)

      @name = name
      @member_types = member_types
      @member_names = member_names
    end

    # @!macro type_check
    def type_check(symtab)
      @member_types.each do |t|
        t.type_check(symtab)
      end
      add_symbol(symtab)
    end

    # @!macro type
    def type(symtab)
      StructType.new(@name, @member_types.map do |t|
        member_type = t.type(symtab)
        type_error "Type #{t.text_value} is not known" if member_type.nil?

        member_type = Type.new(:enum_ref, enum_class: member_type) if member_type.kind == :enum
        member_type
      end, @member_names)
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      internal_error "Structs should be declared at global scope" unless symtab.levels == 1

      t = type(symtab)
      symtab.add!(name, t)
    end

    # @param name [String] Member name
    # @param symtab [SymbolTable] Context
    # @return [Type] Type of member +name+
    # @return [nil] if there is no member +name+
    def member_type(name, symtab)
      idx = member_names.index(name)
      return nil if idx.nil?
      member_types[idx].type(symtab)
    end

    # @return [Integer] Number of members
    def num_members = member_names.size

    sig { override.returns(String) }
    def to_idl
      member_decls = []
      num_members.times do |i|
        member_decls << "#{member_types[i].to_idl} #{member_names[i]}"
      end
      "struct #{name} { #{member_decls.join("; ")}; }"
    end
  end

  # class VariableAccessAst < Ast

  # end

  # class LValAst < VariableAccessAst
  # end

  # class MemoryLValAst < LValAst
  # end

  # class VariableLValAst < LValAst
  # end

  # class RValAst < VariableAccessAst
  # end

  # class MemoryRValAst < RValAst
  # end

  # class VariableRValAst < RValAst
  # end

  # this is not used as an AST node; we use it split chained array accesses
  #
  # For example, it helps us represent
  #   X[rs1][31:0]
  class AryAccessSyntaxNode < SyntaxNode
    # fix up left recursion
    #
    # @return [AstNode] New tree rooted at the array access
    def to_ast
      var = send(:a).to_ast
      send(:brackets).elements.each do |bracket|
        var =
          if bracket.msb.empty?
            AryElementAccessAst.new(input, interval, var, bracket.lsb.to_ast)
          else
            AryRangeAccessAst.new(input, interval, var,
                                  bracket.msb.expression.to_ast, bracket.lsb.to_ast)
          end
      end

      var
    end
  end

  class AryElementAccessAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      if var.name == "X"
        false
      else
        var.const_eval?(symtab) && index.const_eval?(symtab)
      end
    end

    def var = @children[0]
    def index = @children[1]

    def initialize(input, interval, var, index)
      super(input, interval, [var, index])
    end

    # @!macro type_check
    def type_check(symtab)
      var.type_check(symtab)
      index.type_check(symtab)

      type_error "Array index must be integral" unless index.type(symtab).integral?

      var_type = var.type(symtab)
      if var_type.kind == :array
        value_result = value_try do
          index_value = index.value(symtab)
          if var_type.width != :unknown
            type_error "Array index out of range" if index_value >= var_type.width
          end
        end # Ok, doesn't need to be known

      elsif var_type.integral?
        if var_type.kind == :bits
          value_result = value_try do
            index_value = index.value(symtab)
            if (var_type.width != :unknown) && (index_value >= var_type.width)
              type_error "Bits element index (#{index_value}) out of range (max #{var_type.width - 1}) in access '#{text_value}'"
            end
          end # OK, doesn need to be known
        end

      else
        type_error "Array element access can only be used with integral types and arrays"
      end
    end

    def type(symtab)
      var_type = var.type(symtab)
      if var_type.kind == :array
        var_type.sub_type
      elsif var_type.integral?
        if var_type.known?
          Bits1Type
        else
          PossiblyUnknownBits1Type
        end
      else
        internal_error "Bad ary element access"
      end
    end

    def value(symtab)
      if var.type(symtab).integral?
        (var.value(symtab) >> index.value(symtab)) & 1
      else
        value_error "X registers are not compile-time-known" if var.text_value == "X"

        ary = var.value(symtab)
        # internal_error "Not an array" unless ary.type.kind == :array

        internal_error "Not an array (is a #{ary.class.name})" unless ary.is_a?(Array)

        idx = index.value(symtab)
        internal_error "Index out of range; make sure type_check is called" if idx >= ary.size

        ary[idx]
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{var.to_idl}[#{index.to_idl}]"
  end

  class AryRangeAccessAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      if var.name == "X"
        false
      else
        var.const_eval?(symtab) && msb.const_eval?(symtab).const_eval? && lsb.const_eval?(symtab)
      end
    end

    def var = @children[0]
    def msb = @children[1]
    def lsb = @children[2]

    def initialize(input, interval, var, msb, lsb)
      super(input, interval, [var, msb, lsb])
    end

    # @!macro type_check
    def type_check(symtab)
      var.type_check(symtab)
      msb.type_check(symtab)
      lsb.type_check(symtab)

      type_error "Range operator only defined for integral types (found #{var.type(symtab)})" unless var.type(symtab).integral?

      type_error "Range MSB must be an integral type" unless msb.type(symtab).integral?
      type_error "Range LSB must be an integral type" unless lsb.type(symtab).integral?

      value_result = value_try do
        msb_value = msb.value(symtab)
        lsb_value = lsb.value(symtab)

        var_type = var.type(symtab)
        if var_type.kind == :bits && var_type.width != :unknown && msb_value >= var_type.width
          type_error "Range too large for bits (msb = #{msb_value}, range size = #{var_type.width})"
        end

        range_size = msb_value - lsb_value + 1
        type_error "zero/negative range (#{msb_value}:#{lsb_value})" if range_size <= 0
      end  # OK, don't have to know
    end

    # @!macro type
    def type(symtab)
      value_result = value_try do
        msb_value = msb.value(symtab)
        lsb_value = lsb.value(symtab)
        range_size = msb_value - lsb_value + 1
        if var.type(symtab).known?
          return Type.new(:bits, width: range_size, qualifiers: [:known])
        else
          return Type.new(:bits, width: range_size)
        end
      end
      # don't know the width at compile time....assume the worst
      value_else(value_result) { var.type(symtab) }
    end

    # @!macro value
    def value(symtab)
      mask = (1 << (msb.value(symtab) - lsb.value(symtab) + 1)) - 1
      (var.value(symtab) >> lsb.value(symtab)) & mask
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{var.to_idl}[#{msb.to_idl}:#{lsb.to_idl}]"

  end

  class PcAssignmentSyntaxNode < SyntaxNode
    def to_ast
      PcAssignmentAst.new(input, interval, send(:rval).to_ast)
    end
  end

  class PcAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    # @return [AstNode] Right-hand side expression
    sig { returns(RvalueAst) }
    def rhs = T.cast(children.fetch(0), RvalueAst)

    sig { params(input: String, interval: T::Range[Integer], rval: RvalueAst).void }
    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    # @macro execute
    sig { override.params(symtab: SymbolTable).void }
    def execute(symtab) = value_error "$pc is never statically known"

    # @macro execute_unknown
    sig { override.params(symtab: SymbolTable).void }
    def execute_unknown(symtab); end

    # @!macro type_check
    sig { override.params(symtab: SymbolTable).void }
    def type_check(symtab)
      rhs.type_check(symtab)
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "$pc = #{rhs.to_idl}"
  end

  class VariableAssignmentSyntaxNode < SyntaxNode
    def to_ast
      VariableAssignmentAst.new(input, interval, send(:var).to_ast, send(:rval).to_ast)
    end
  end

  # represents a scalar variable assignment statement
  #
  # for example, these will result in a VariableAssignmentAst
  #   # given: Bits<XLEN> zero;
  #   zero = XLEN'b0
  class VariableAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      return false if !lhs.const_eval?(symtab)

      if rhs.const_eval?(symtab)
        true
      else
        lhs_var = symtab.get(lhs.name)
        type_error "variable #{lhs.name} was not declared" if lhs_var.nil? || !lhs_var.is_a?(Var)

        lhs_var.const_incompatible!
        false
      end
    end

    sig { returns(IdAst) }
    def lhs = T.cast(@children.fetch(0), IdAst)

    sig { returns(RvalueAst) }
    def rhs = T.cast(@children.fetch(1), RvalueAst)

    def initialize(input, interval, lhs_ast, rhs_ast)
      super(input, interval, [lhs_ast, rhs_ast])
      @vars = {}
    end

    # @!macro type_check
    def type_check(symtab)
      lhs.type_check(symtab)
      lhs_var = symtab.get(lhs.name)
      type_error "Cannot assign to a const" if lhs_var.type.const? && !lhs_var.for_loop_iter?

      rhs.type_check(symtab)
      if lhs_var.type.const? && lhs_var.for_loop_iter?
        # also check that the rhs is const_eval
        type_error "Assignment would make iteration variable non-const" unless rhs.type(symtab).const?
      end
      unless rhs.type(symtab).convertable_to?(lhs.type(symtab))
        type_error "Incompatible type in assignment (#{lhs.type(symtab)}, #{rhs.type(symtab)})"
      end
    end

    def var(symtab)
      variable = @vars[symtab.name]
      if variable.nil?
        variable = symtab.get(lhs.text_value)
        @vars[symtab.name] = variable
      end
      variable
    end

    # @!macro execute
    def execute(symtab)
      if lhs.is_a?(CsrWriteAst)
        value_error "CSR writes are never compile-time-known"
      else
        variable = var(symtab)

        internal_error "No variable #{lhs.text_value}" if variable.nil?

        unless variable.type.global?
          value_result = value_try do
            variable.value = rhs.value(symtab)
          end
          value_else(value_result) do
            variable.value = nil
            value_error ""
          end
        end
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      if lhs.is_a?(CsrWriteAst)
        value_error "CSR writes are never compile-time-known"
      else
        variable = var(symtab)

        internal_error "No variable #{lhs.text_value}" if variable.nil?

        variable.value = nil
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{lhs.to_idl} = #{rhs.to_idl}"
  end

  class AryElementAssignmentSyntaxNode < SyntaxNode
    def to_ast
      AryElementAssignmentAst.new(input, interval, send(:var).to_ast, send(:idx).to_ast, send(:rval).to_ast)
    end
  end

  # represents an array element assignment
  #
  # for example:
  #   X[rs1] = XLEN'd0
  class AryElementAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      return false if !lhs.const_eval?(symtab)

      if idx.const_eval?(symtab) && rhs.const_eval?(symtab)
        true
      else
        lhs_var = symtab.get(lhs.name)
        type_error "array #{lhs.name} has not been declared" if lhs_var.nil?

        lhs_var.const_incompatible!
        false
      end
    end

    def lhs = @children[0]
    def idx = @children[1]
    def rhs = @children[2]

    def initialize(input, interval, lhs, idx, rhs)
      super(input, interval, [lhs, idx, rhs])
    end

    # @!macro type_check
    def type_check(symtab)
      lhs.type_check(symtab)
      unless [:array, :bits].include?(lhs.type(symtab).kind)
        type_error "#{lhs.text_value} must be an array or an integral type"
      end
      type_error "Assigning to a constant" if lhs.type(symtab).const?

      idx.type_check(symtab)

      type_error "Index must be integral" unless idx.type(symtab).integral?

      value_result = value_try do
        idx_value = idx.value(symtab)
        type_error "Array index (#{idx.text_value} = #{idx_value}) out of range (< #{lhs.type(symtab).width})" if idx_value >= lhs.type(symtab).width
      end
      # OK, doesn't need to be known

      rhs.type_check(symtab)

      case lhs.type(symtab).kind
      when :array
        unless rhs.type(symtab).convertable_to?(lhs.type(symtab).sub_type)
          type_error "Incompatible type in array assignment"
        end
      when :bits
        unless rhs.type(symtab).convertable_to?(Bits1Type)
          type_error "Incompatible type in integer slice assignment"
        end
      else
        internal_error "Unexpected type on array element assignment"
      end
    end

    # @!macro execute
    def execute(symtab)
      lhs_type = lhs.type(symtab)
      return if lhs_type.global?

      case lhs_type.kind
      when :array
        idx_value = idx.value(symtab)
        lhs_value = lhs.value(symtab)
        value_result = value_try do
          lhs_value[idx_value] = rhs.value(symtab)
        end
        value_else(value_result) do
          lhs_value[idx_value] = nil
          value_error "right-hand side of array element assignment is unknown"
        end
      when :bits
        var = symtab.get(lhs.text_value)
        value_result = value_try do
          v = rhs.value(symtab)
          var.value = (lhs.value(symtab) & ~0) | ((v & 1) << idx.value(symtab))
        end
        value_else(value_result) do
          var.value = nil
        end
      else
        internal_error "unexpected type for array element assignment"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      value_result = T.let(nil, T.nilable(Symbol))
      case lhs.type(symtab).kind
      when :array
        lhs_value = T.let(lhs.value(symtab), T::Array[T.nilable(ValueRbType)])
        value_result = value_try do
          idx_value = idx.value(symtab)
          value_result = value_try do
            lhs_value[idx_value] = rhs.value(symtab)
          end
          value_else(value_result) do
            lhs_value[idx_value] = nil
            value_error "right-hand side of array element assignment is unknown"
          end
        end
        value_else(value_result) do
          # the idx isn't known; the entire array must become unknown
          lhs_value.map! { |_v| nil }
        end
      when :bits
        var = symtab.get(lhs.text_value)
        value_result = value_try do
          v = rhs.value(symtab)
          var.value = (lhs.value & ~0) | ((v & 1) << idx.value(symtab))
        end
        value_else(value_result) do
          var.value = nil
        end
      else
        internal_error "unexpected type for array element assignment"
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{lhs.to_idl}[#{idx.to_idl}] = #{rhs.to_idl}"
  end

  class AryRangeAssignmentSyntaxNode < SyntaxNode
    def to_ast
      AryRangeAssignmentAst.new(input, interval, send(:var).to_ast, send(:msb).to_ast, send(:lsb).to_ast, send(:rval).to_ast)
    end
  end

  # represents an array range assignment
  #
  # for example:
  #   vec[8:0] = 8'd0
  class AryRangeAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      return false if !variable.const_eval?(symtab)

      if lsb.const_eval?(symtab) && msb.const_eval?(symtab) && write_value.const_eval?(symtab)
        true
      else
        lhs_var = symtab.get(variable.name)
        type_error "array #{variable.name} has not be declared" if lhs_var.nil?

        lhs_var.const_incompatible!
        false
      end
    end

    def variable = @children[0]
    def msb = @children[1]
    def lsb = @children[2]
    def write_value = @children[3]

    def initialize(input, interval, variable, msb, lsb, write_value)
      super(input, interval, [variable, msb, lsb, write_value])
    end

    # @!macro type_check
    def type_check(symtab)
      variable.type_check(symtab)
      type_error "#{variable.text_value} must be integral" unless variable.type(symtab).kind == :bits
      type_error "Assigning to a constant" if variable.type(symtab).const?

      msb.type_check(symtab)
      lsb.type_check(symtab)

      type_error "MSB must be integral" unless msb.type(symtab).integral?
      type_error "LSB must be integral" unless lsb.type(symtab).integral?

      value_result = value_try do
        msb_value = msb.value(symtab)
        lsb_value = lsb.value(symtab)

        type_error "MSB must be > LSB" unless msb_value > lsb_value
        type_error "MSB is out of range" if msb_value >= variable.type(symtab).width
      end
      # OK, don't have to know the value

      write_value.type_check(symtab)

      unless write_value.type(symtab).integral?
        type_error "Incompatible type in range assignment"
      end
    end

    def rhs
      write_value
    end

    # @!macro execute
    def execute(symtab)
      return if variable.type(symtab).global?

      value_result = value_try do
        var_val = variable.value(symtab)

        msb_val = msb.value(symtab)
        lsb_val = lsb.value(symtab)

        type_error "MSB (#{msb_val}) is <= LSB (#{lsb_val})" if msb_val <= lsb_val

        rval_val = write_value.value(symtab)

        mask = ((1 << msb_val) - 1) << lsb_val

        var_val &= ~mask

        var_val | ((rval_val << lsb_val) & mask)
        symtab.add(variable.name, Var.new(variable.name, variable.type(symtab), var_val))
        :ok
      end
      value_else(value_result) do
        symtab.add(variable.name, Var.new(variable.name, variable.type(symtab)))
        value_error "Either the range or right-hand side of an array range assignment is unknown"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.add(variable.name, Var.new(variable.name, variable.type(symtab)))
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{variable.to_idl}[#{msb.to_idl}:#{lsb.to_idl}] = #{write_value.to_idl}"
  end

  class FieldAssignmentSyntaxNode < SyntaxNode
    def to_ast
      FieldAssignmentAst.new(input, interval, send(:id).to_ast, send(:field_name).text_value, send(:rval).to_ast)
    end
  end

  # represents a bitfield or struct assignment
  #
  # for example:
  #   Sv39PageTableEntry entry;
  #   entry.PPN = 0
  #
  class FieldAssignmentAst < AstNode
    include Executable

    sig { returns(IdAst) }
    def id = T.cast(@children.fetch(0), IdAst)

    sig { returns(RvalueAst) }
    def rhs = T.cast(@children.fetch(1), RvalueAst)

    sig { returns(String) }
    def field_name = @field_name

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      var = symtab.get(id.name)
      type_error "#{id.name} is not declared!" if var.nil?

      return false if !var.const_eval?

      if rhs.const_eval?(symtab)
        true
      else
        var.const_incompatible!
        false
      end
    end

    sig { params(input: String, interval: T::Range[Integer], id: IdAst, field_name: String, rhs: RvalueAst).void }
    def initialize(input, interval, id, field_name, rhs)
      super(input, interval, [id, rhs])
      @field_name = field_name
    end

    # @!macro type
    def type(symtab)
      var = symtab.get(id.name)
      type_error "#{id.name} has not been declared" if var.nil?

      if var.type.kind == :bitfield
        Type.new(:bits, width: var.type.range(@field_name).size)
      elsif var.type.kind == :struct
        var.type.member_type(@field_name)
      else
        internal_error "huh? #{id.text_value} #{var.type.kind}"
      end
    end

    # @!macro type_check
    def type_check(symtab)
      id.type_check(symtab)
      var = symtab.get(id.name)
      type_error "#{id.name} has not been declared" if var.nil?

      if var.type.kind == :bitfield
        internal_error "#{id.name} Not a BitfieldType (is a #{var.type})" unless var.type.respond_to?(:field_names)
        unless var.type.field_names.include?(@field_name)
          type_error "#{@field_name} is not a member of #{var.type}"
        end
      elsif var.type.kind == :struct
        type_error "#{@field_name} is not a member of #{var.type}" unless var.type.member?(@field_name)
      else
        type_error "#{id.name} is not a bitfield  or struct (is #{var.type})"
      end

      type_error "Cannot write const variable" if var.type.const?

      rhs.type_check(symtab)
      return if rhs.type(symtab).convertable_to?(type(symtab))

      type_error "Incompatible type in assignment (#{type(symtab)}, #{rhs.type(symtab)})"
    end

    # @!macro execute
    def execute(symtab)
      var = symtab.get(id.name)
      type_error "#{id.name} has not been declared" if var.nil?

      if var.type.kind == :bitfield
        bitfield_val = id.value(symtab)
        range = var.type.range(@field_name)
        rhs_value = T.cast(rhs.value(symtab), Integer)
        rhs_value_trunc = rhs_value & ((1 << range.size) - 1)

        # zero out the field
        bitfield_val &= ~(((1 << range.size) - 1) << range.first)
        bitfield_val |= rhs_value_trunc << range.first
        var.value = bitfield_val
      elsif var.type.kind == :struct
        struct_val = id.value(symtab)
        struct_val[@field_name] = rhs.value(symtab)
      else
        value_error "TODO: Field assignment execution"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      var = symtab.get(id.name)
      var.value = nil
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{id.to_idl}.#{@field_name} = #{rhs.to_idl}"
  end

  class CsrFieldAssignmentSyntaxNode < SyntaxNode
    def to_ast
      CsrFieldAssignmentAst.new(input, interval, send(:csr_field_access_expression).to_ast, send(:rval).to_ast)
    end
  end

  class CsrFieldAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    def csr_field = @children[0]
    def write_value = @children[1]

    def initialize(input, interval, csr_field, write_value)
      super(input, interval, [csr_field, write_value])
    end

    def type(symtab)
      if field(symtab).defined_in_all_bases?
        if symtab.mxlen == 64 && symtab.multi_xlen?
          Type.new(:bits, width: [field(symtab).location(32).size, field(symtab).location(64).size].max)
        else
          Type.new(:bits, width: field(symtab).location(symtab.mxlen).size)
        end
      elsif field(symtab).base64_only?
        Type.new(:bits, width: field(symtab).location(64).size)
      elsif field(symtab).base32_only?
        Type.new(:bits, width: field(symtab).location(32).size)
      else
        internal_error "Unexpected base for field"
      end
    end

    def field(symtab)
      csr_field.field_def(symtab)
    end

    def type_check(symtab)
      csr_field.type_check(symtab)

      write_value.type_check(symtab)
      type_error "Incompatible type in assignment" unless write_value.type(symtab).convertable_to?(type(symtab))
    end

    # @!macro execute
    def execute(symtab)
      value_error "CSR field writes are never compile-time-executable"
    end

    # @!macro execute_unknown
    def execute_unknown(symtab); end

    sig { override.returns(String) }
    def to_idl = "#{csr_field.to_idl} = #{write_value.to_idl}"
  end

  class MultiVariableAssignmentSyntaxNode < SyntaxNode
    def to_ast
      MultiVariableAssignmentAst.new(input, interval, [send(:first).to_ast] + send(:rest).elements.map { |r| r.var.to_ast }, send(:function_call).to_ast)
    end
  end

  # represents assignment of multiple variable from a function call that returns multiple values
  #
  # for example:
  #   (match_result, cfg) = pmp_match<access_size>(paddr);
  class MultiVariableAssignmentAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      func_is_const_eval = function_call.const_eval?(symtab)
      everything_is_const_eval = func_is_const_eval

      variables.each do |variable|
        var = symtab.get(variable.name)
        type_error "#{var} was not declared" if var.nil?
        everything_is_const_eval = false unless var.const_eval?

        var.const_incompatible! unless func_is_const_eval
      end

      func_is_const_eval
    end

    def variables = @children[0..-2]
    def function_call = @children.last

    def initialize(input, interval, variables, function_call)
      super(input, interval, variables + [function_call])
    end

    # @return [Array<AstNode>] The variables being assigned, in order
    def vars
      variables
    end

    def rhs
      function_call
    end

    # @!macro type_check
    def type_check(symtab)
      function_call.type_check(symtab)
      variables.each { |var| var.type_check(symtab) }

      type_error "Assigning value to a constant" if variables.any? { |v| v.type(symtab).const? }

      type_error "Function '#{function_call.name}' has no return type" if function_call.type(symtab).nil?
      unless function_call.type(symtab).kind == :tuple
        type_error "Function '#{function_call.name}' only returns 1 variable"
      end

      if function_call.type(symtab).tuple_types.size != vars.size
        type_error "function '#{function_call.name}' returns #{function_call.type(symtab).tuple_types.size} arguments, but  #{variables.size} were specified"
      end

      function_call.type(symtab).tuple_types.each_index do |i|
        next if variables[i].is_a?(DontCareLvalueAst)
        raise "Implementation error" if variables[i].is_a?(DontCareReturnAst)

        var = symtab.get(variables[i].text_value)
        type_error "No symbol named '#{variables[i].text_value}'" if var.nil?

        internal_error "Cannot determine type of #{variables[i].text_value}" unless var.respond_to?(:type)

        unless var.type.convertable_to?(function_call.type(symtab).tuple_types[i])
          type_error "'#{function_call.name}' expecting a #{function_call.type(symtab).tuple_types[i]} in argument #{i}, but was given #{var.type(symtab)}"
        end
      end
    end

    # @!macro execute
    def execute(symtab)
      value_result = value_try do
        values = function_call.execute(symtab)

        i = 0
        variables.each do |v|
          next if v.type(symtab).global?

          var = symtab.get(v.text_value)
          internal_error "call type check" if var.nil?

          var.value = values[i]
          i += 1
        end
      end
      value_else(value_result) do
        variables.each do |v|
          symtab.get(v.text_value).value = nil
        end
        value_error "value of right-hand side of multi-variable assignment is unknown"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      variables.each do |v|
        symtab.get(v.text_value).value = nil
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "(#{variables.map(&:to_idl).join(', ')}) = #{function_call.to_idl}"
  end

  class MultiVariableDeclarationSyntaxNode < SyntaxNode
    def to_ast
      MultiVariableDeclarationAst.new(input, interval, send(:type_name).to_ast, [send(:first).to_ast] + send(:rest).elements.map { |r| r.id.to_ast })
    end
  end

  # represents the declaration of multiple variables
  #
  # for example:
  #   Bits<64> a, b;
  #   Bits<64> a, b, c, d;
  class MultiVariableDeclarationAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      add_symbol(symtab)
      true
    end

    # @return [AstNode] Declared type
    def type_name = @children[0]

    # @return [Array<AstNode>] Variable names
    def var_name_nodes = @children[1..]

    def initialize(input, interval, type_name, var_names)
      super(input, interval, [type_name] + var_names)

      @global = false
    end

    # mark this declaration as being in global scope
    def make_global
      @global = true
    end

    # @return [Array<String>] Variables being declared
    def var_names
      var_name_nodes.map(&:text_value)
    end

    # @!macro type_check
    def type_check(symtab)
      type_name.type_check(symtab)

      add_symbol(symtab)
    end

    # @!macro type
    def type(symtab)
      if @global
        type_name.type(symtab).clone.make_global
      else
        type_name.type(symtab)
      end
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      var_name_nodes.each do |vname|
        symtab.add(vname.text_value, Var.new(vname.text_value, type(symtab), type(symtab).default))
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{type_name.to_idl} #{var_name_nodes.map(&:to_idl).join(', ')}"
  end

  class VariableDeclarationSyntaxNode < SyntaxNode
    def to_ast
      VariableDeclarationAst.new(input, interval, send(:type_name).to_ast, send(:id).to_ast, send(:ary_size).empty? ? nil : send(:ary_size).ary_size_decl.expression.to_ast)
    end
  end

  # represents a single variable declaration (without assignment)
  #
  # for example:
  #   Bits<64> doubleword
  #   Boolean has_property
  class VariableDeclarationAst < AstNode
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      add_symbol(symtab)
      true
    end

    sig { returns(TypeNameAst) }
    def type_name = T.cast(children.fetch(0), TypeNameAst)

    sig { returns(IdAst) }
    def id = T.cast(children.fetch(1), IdAst)

    sig { returns(T.nilable(RvalueAst)) }
    def ary_size = children[2].nil? ? nil : T.cast(children.fetch(2), RvalueAst)

    sig { returns(String) }
    def name = id.text_value

    sig {
      params(
        input: String,
        interval: T::Range[Integer],
        type_name: TypeNameAst,
        id: IdAst,
        ary_size: T.nilable(RvalueAst)
      ).void
    }
    def initialize(input, interval, type_name, id, ary_size)
      if ary_size.nil?
        super(input, interval, [type_name, id])
      else
        super(input, interval, [type_name, id, ary_size])
      end

      @global = false
    end

    sig { void }
    def make_global
      @global = true
    end

    sig { params(symtab: SymbolTable).returns(T.nilable(Type)) }
    def decl_type(symtab)
      dtype = type_name.type(symtab)

      return nil if dtype.nil?

      qualifiers = []
      qualifiers << :const if T.must(id.text_value[0]).upcase == id.text_value[0]
      qualifiers << :global if @global

      dtype = Type.new(:enum_ref, enum_class: dtype, qualifiers:) if dtype.kind == :enum

      # dtype = dtype.clone.qualify(q.text_value.to_sym) unless q.empty?

      unless ary_size.nil?
        value_result = value_try do
          dtype = Type.new(:array, width: T.must(ary_size).value(symtab), sub_type: dtype, qualifiers:)
        end
        value_else(value_result) do
          dtype = Type.new(:array, width: :unknown, sub_type: dtype, qualifiers:)
        end
      end

      dtype
    end

    def type(symtab) = decl_type(symtab)

    # @!macro type_check
    def type_check(symtab, add_sym = true)
      type_name.type_check(symtab)
      dtype = type_name.type(symtab)

      type_error "No type '#{type_name.text_value}'" if dtype.nil?

      type_error "Constants must be initialized at declaration" if id.text_value[0] == T.must(id.text_value[0]).upcase

      unless ary_size.nil?
        T.must(ary_size).type_check(symtab)
        value_result = value_try do
          T.must(ary_size).value(symtab)
        end
        value_else(value_result) do
          # it's ok that we don't know the value yet, as long as the value is a const
          type_error "Array size (#{T.must(ary_size).text_value}) must be a constant" unless T.must(ary_size).type(symtab).const?
        end
      end

      add_symbol(symtab) if add_sym

      id.type_check(symtab)
    end

    # @!macro add_symbol
    sig { override.params(symtab: SymbolTable).void }
    def add_symbol(symtab)
      if @global
        # fill global with nil to prevent its use in compile-time evaluation
        symtab.add!(id.text_value, Var.new(id.text_value, decl_type(symtab), nil))
      else
        type_error "No Type '#{type_name.text_value}'" if decl_type(symtab).nil?
        symtab.add(id.text_value, Var.new(id.text_value, decl_type(symtab), T.must(decl_type(symtab)).default))
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      if ary_size.nil?
        "#{type_name.to_idl} #{id.to_idl}"
      else
        "#{type_name.to_idl} #{id.to_idl}[#{T.must(ary_size).to_idl}]"
      end
    end
  end

  class VariableDeclarationWithInitializationSyntaxNode < SyntaxNode
    def to_ast
      ary_size_ast = send(:ary_size).empty? ? nil : send(:ary_size).expression.to_ast
      VariableDeclarationWithInitializationAst.new(
        input, interval,
        send(:type_name).to_ast, send(:id).to_ast, ary_size_ast, send(:rval).to_ast,
        false
      )
    end
  end

  class ForLoopIterationVariableDeclarationSyntaxNode < SyntaxNode
    def to_ast
      ary_size_ast = send(:ary_size).empty? ? nil : send(:ary_size).expression.to_ast
      VariableDeclarationWithInitializationAst.new(
        input, interval,
        send(:type_name).to_ast, send(:id).to_ast, ary_size_ast, send(:rval).to_ast,
        true
      )
    end
  end

  # represents a single variable declaration with initialization
  #
  # for example:
  #   Bits<64> doubleword = 64'hdeadbeef
  #   Boolean has_property = true
  class VariableDeclarationWithInitializationAst < AstNode
    include Executable
    include Declaration

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      var = Var.new(lhs.text_value, lhs_type(symtab))
      symtab.add(lhs.text_value, var)
      if rhs.const_eval?(symtab)
        true
      else
        var.const_incompatible!
        false
      end
    end

    sig { returns(TypeNameAst) }
    def type_name = T.cast(@children[0], TypeNameAst)

    sig { returns(IdAst) }
    def lhs = T.cast(@children[1], IdAst)

    sig { returns(T.nilable(RvalueAst)) }
    def ary_size = @children[3].nil? ? nil : T.cast(@children[3], RvalueAst)

    sig { returns(RvalueAst) }
    def rhs = T.cast(@children[2], RvalueAst)

    sig { returns(String) }
    def id = lhs.text_value

    sig {
      params(
        input: String,
        interval: T::Range[Integer],
        type_name_ast: TypeNameAst,
        var_write_ast: IdAst,
        ary_size: T.nilable(RvalueAst),
        rval_ast: RvalueAst,
        is_for_loop_iteration_var: T::Boolean
      ).void
    }
    def initialize(input, interval, type_name_ast, var_write_ast, ary_size, rval_ast, is_for_loop_iteration_var)
      if ary_size.nil?
        super(input, interval, [type_name_ast, var_write_ast, rval_ast])
      else
        super(input, interval, [type_name_ast, var_write_ast, rval_ast, ary_size])
      end
      @global = false
      @for_iter_var = is_for_loop_iteration_var
    end

    def make_global
      @global = true
    end

    def lhs_type(symtab)
      decl_type = type_name.type(symtab).clone
      type_error "No type '#{type_name.text_value}' on line #{lineno}" if decl_type.nil?

      qualifiers = []
      qualifiers << :const if T.must(lhs.text_value[0]).upcase == lhs.text_value[0]
      qualifiers << :global if @global

      decl_type = Type.new(:enum_ref, enum_class: decl_type) if decl_type.kind == :enum

      qualifiers.each do |q|
        decl_type.qualify(q)
      end

      unless ary_size.nil?
        value_result = value_try do
          decl_type = Type.new(:array, sub_type: decl_type, width: T.must(ary_size).value(symtab), qualifiers:)
        end
        value_else(value_result) do
          type_error "Array size must be known at compile time"
        end
      end

      decl_type
    end

    # @!macro type_check
    def type_check(symtab)
      rhs.type_check(symtab)

      type_name.type_check(symtab)

      ary_size&.type_check(symtab)

      decl_type = lhs_type(symtab)

      if decl_type.const?
        # this is a constant; ensure we are assigning a constant value
        value_result = value_try do
          symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone, rhs.value(symtab), for_loop_iter: @for_iter_var))
        end
        value_else(value_result) do
          unless rhs.type(symtab).const?
            type_error "Declaring constant (#{lhs.name}) with a non-constant value (#{rhs.text_value})"
          end
          symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone, for_loop_iter: @for_iter_var))
        end
      else
        symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone, for_loop_iter: @for_iter_var))
      end

      lhs.type_check(symtab)

      # now check that the assignment is compatible
      return if rhs.type(symtab).convertable_to?(decl_type)

      type_error "Incompatible type (#{decl_type}, #{rhs.type(symtab)}) in assignment"
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      if @global
        if lhs.text_value[0] == T.must(lhs.text_value[0]).upcase
          # const, add the value if it's known
          value_result = value_try do
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs.value(symtab), for_loop_iter: @for_iter_var))
          end
          value_else(value_result) do
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), for_loop_iter: @for_iter_var))
          end
        else
          # mutable globals never have a compile-time value
          symtab.add!(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), for_loop_iter: @for_iter_var))
        end
      else
        value_result = value_try do
          if @for_iter_var
            # don't add the value, because it will change across iterations
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), for_loop_iter: @for_iter_var))
          else
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs.value(symtab), for_loop_iter: @for_iter_var))
          end
        end
        value_else(value_result) do
          symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), for_loop_iter: @for_iter_var))
        end
      end
    end

    # @!macro execute
    def execute(symtab)
      value_error "TODO: Array declaration" unless ary_size.nil?
      rhs_value = T.let(nil, T.nilable(ValueRbType))
      return if @global # never executed at compile time

      value_result = value_try do
        rhs_value = rhs.value(symtab)
      end
      value_else(value_result) do
        symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), nil, for_loop_iter: @for_iter_var))
        value_error "value of right-hand side of variable initialization is unknown"
      end
      symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs_value))
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), nil, for_loop_iter: @for_iter_var))
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      if ary_size.nil?
        "#{type_name.to_idl} #{lhs.to_idl} = #{rhs.to_idl}"
      else
        "#{type_name.to_idl} #{lhs.to_idl}[#{T.must(ary_size).to_idl}] = #{rhs.to_idl}"
      end
    end
  end

  class BinaryExpressionRightSyntaxNode < SyntaxNode

    # fix up left recursion
    # i.e., xlen() - 1 - i => (xlen() - 1) - i
    def to_ast
      first =
        BinaryExpressionAst.new(
          input, (interval.begin...send(:r).elements[0].r.interval.end),
          send(:l).to_ast, send(:r).elements[0].op.text_value, send(:r).elements[0].r.to_ast
        )

      if send(:r).elements.size == 1
        first
      else
        send(:r).elements[1..].inject(first) do |lhs, el|
          BinaryExpressionAst.new(input, (lhs.interval.begin...el.r.interval.end),
                                  lhs, el.op.text_value, el.r.to_ast)
        end
      end
    end

    def type_check(_symtab)
      raise "you must have forgotten the to_ast pass"
    end
  end

  class WidthRevealSyntaxNode < SyntaxNode
    def to_ast
      WidthRevealAst.new(input, interval, send(:expression).to_ast)
    end
  end

  class WidthRevealAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    sig { returns(RvalueAst) }
    def expression = T.cast(@children.fetch(0), RvalueAst)

    sig { params(input: String, interval: T::Range[Integer], e: AstNode).void }
    def initialize(input, interval, e)
      super(input, interval, [e])
    end

    sig { override.params(symtab: SymbolTable).void }
    def type_check(symtab)
      expression.type_check(symtab)

      e_type = expression.type(symtab)
      type_error "#{expression.text_value} is not a Bits<N> type" unless e_type.kind == :bits
    end

    sig { override.params(symtab: SymbolTable).returns(Type) }
    def type(symtab)
      if (expression.type(symtab).width == :unknown)
        BitsUnknownType
      else
        Type.new(:bits, width: T.cast(expression.type(symtab).width, Integer).bit_length)
      end
    end

    sig { override.params(symtab: SymbolTable).returns(Integer) }
    def value(symtab)
      v = expression.type(symtab).width
      value_error "Width is not known" if v == :unknown
      T.cast(v, Integer)
    end

    sig { override.returns(String) }
    def to_idl = "$width(#{expression.to_idl})"
  end

  class SignCastSyntaxNode < SyntaxNode
    def to_ast
      SignCastAst.new(input, interval, send(:expression).to_ast)
    end
  end

  class SignCastAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def expression = @children[0]

    def initialize(input, interval, exp) = super(input, interval, [exp])

    # @!macro type_check
    def type_check(symtab)
      expression.type_check(symtab)
    end

    # @!macro type
    def type(symtab) = expression.type(symtab).clone.make_signed

    # @!macro value
    def value(symtab)
      t = expression.type(symtab)
      internal_error "Expecting a bits type" unless t.kind == :bits
      v = expression.value(symtab)

      if ((v >> (t.width - 1)) & 1) == 1
        # twos compliment negate the value
        -(2**t.width - v)
      else
        v
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "$signed(#{expression.to_idl})"
  end

  class BitsCastSyntaxNode < SyntaxNode
    def to_ast
      BitsCastAst.new(input, interval, send(:expr).to_ast)
    end
  end

  # Node for a cast to a Bits<N> type
  #
  # This will result in a BitsCaseAst:
  #
  #   $bits(ExceptionCode::LoadAccessFault)
  class BitsCastAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      expr.const_eval?(symtab)
    end

    # @return [AstNode] The casted expression
    def expr = @children[0]

    def initialize(input, interval, exp) = super(input, interval, [exp])

    # @!macro type_check
    def type_check(symtab)
      expr.type_check(symtab)

      unless [:bits, :enum_ref, :csr].include?(expr.type(symtab).kind)
        type_error "#{expr.type(symtab)} Cannot be cast to bits"
      end
    end

    # @!macro type
    def type(symtab)
      etype = expr.type(symtab)

      case etype.kind
      when :bits
        etype
      when :enum_ref
        Type.new(:bits, width: etype.enum_class.width, qualifiers: [:known])
      when :csr
        if (etype.csr.is_a?(Symbol) && etype.csr == :unknown) || etype.csr.dynamic_length?
          Type.new(:bits, width: :unknown)
        else
          Type.new(:bits, width: etype.csr.length)
        end
      else
        type_error "$bits cast is only defined for CSRs and Enum references"
      end
    end

    # @!macro value
    def value(symtab)
      etype = expr.type(symtab)

      case etype.kind
      # when :bits
      #   expr.value(symtab)
      when :enum_ref
        if expr.is_a?(EnumRefAst)
          element_name = expr.text_value.split(":")[2]
          etype.enum_class.value(element_name)
        else
          # this is an expression with an EnumRef type
          expr.value(symtab)
        end
      when :csr
        expr.value(symtab)
      else
        type_error "TODO: Bits cast for #{etype.kind}"
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "$signed(#{expr.to_idl})"
  end

  class BinaryExpressionAst < AstNode
    include Rvalue

    LOGICAL_OPS = ["==", "!=", ">", "<", ">=", "<=", "&&", "||"].freeze
    BIT_OPS = ["&", "|", "^"].freeze
    ARITH_OPS = ["+", "-", "/", "*", "%", "<<", ">>", ">>>", "`+", "`-", "`*", "`<<"].freeze
    OPS = (LOGICAL_OPS + ARITH_OPS + BIT_OPS).freeze

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      # can't check for short-circuit here unless we also evaluate values during the const_eval pass
      # thus, conservative assume there is no short-circuiting
      lhs.const_eval?(symtab) && rhs.const_eval?(symtab)
    end

    def lhs = @children[0]
    def rhs = @children[1]

    # create a new, left-recursion-fixed, binary expression
    def initialize(input, interval, lhs, op, rhs)
      super(input, interval, [lhs, rhs])
      @op = op.to_s
      type_error "Bad op '#{@op}'" unless OPS.include?(@op)
    end

    # @return [BinaryExpressionAst] this expression, but with an inverted condition
    def invert(symtab)
      unless symtab.nil?
        type_error "Not a boolean operator" unless type(symtab).kind == :boolean
      end

      inverted_op_map = {
        "==" => "!=",
        "!=" => "==",
        ">" => "<=",
        "<" => ">=",
        "<=" => ">",
        ">=" => "<"
      }

      if inverted_op_map.key?(op)
        BinaryExpressionAst.new(input, interval, lhs.dup, inverted_op_map[op], rhs.dup)
      else
        UnaryOperatorExpressionAst.new(input, interval, "!", self.dup)
      end
      # else
      #   # harder case of && / ||
      #   if op == "&&"
      #     inverted_text = "!#{lhs.to_idl} || !#{rhs.to_idl}"
      #     BinaryExpressionAst.new(inverted_text, 0..(inverted_text.size - 1), UnaryOperatorExpressionAst.new())
      #   elsif op == "||"
      #     inverted_text = "!#{lhs.to_idl} && !#{rhs.to_idl}"
      #   end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      "(#{lhs.to_idl} #{op} #{rhs.to_idl})"
    end

    # @!macro type
    def type(symtab)
      lhs_type = lhs.type(symtab)
      short_circuit = T.let(false, T::Boolean)

      value_result = value_try do
        lhs_value = lhs.value(symtab)
        if (lhs_value == true && op == "||") || (lhs_value == false && op == "&&")
          short_circuit = true
        end
      end
      value_else(value_result) { short_circuit = false }

      rhs_type = rhs.type(symtab) unless short_circuit

      qualifiers = []
      qualifiers << :const if lhs_type.const? && (short_circuit || rhs_type.const?)

      if LOGICAL_OPS.include?(op)
        if qualifiers.include?(:const)
          ConstBoolType
        else
          BoolType
        end
      elsif ["<<", ">>", ">>>"].include?(op)
        # type of non-widening left/right shift is the type of the left hand side
        lhs_type
      elsif op == "`<<"
        qualifiers << :known if lhs_type.known? && rhs_type.known?
        value_result = value_try do
          # if shift amount is known, then the result width is increased by the shift
          # otherwise, the result is the width of the left hand side
          value_error "lhs width unknown" if lhs_type.width == :unknown
          return Type.new(:bits, width: lhs_type.width + rhs.value(symtab), qualifiers:)
        end
        value_else(value_result) do
          Type.new(:bits, width: lhs_type.width, qualifiers:)
        end
      elsif ["`+", "`-"].include?(op)
        qualifiers << :known # +/- raises exception if either lhs or rhs has undefined state
        # widening addition/subtraction: result is 1 more bit than the largest operand to
        # capture the carry
        value_result = value_try do
          value_error "lhs width is unknown" if lhs_type.width == :unknown
          value_error "rhs width is unknown" if rhs_type.width == :unknown
          return Type.new(:bits, width: [lhs_type.width, rhs_type.width].max + 1, qualifiers:)
        end
        value_else(value_result) do
          Type.new(:bits, width: :unknown, qualifiers:)
        end
      elsif op == "`*"
        qualifiers << :known if lhs_type.known? && rhs_type.known?
        # widening multiply: result is 2x the width of the largest operand
        value_result = value_try do
          value_error "lhs width is unknown" if lhs_type.width == :unknown
          value_error "rhs width is unknown" if rhs_type.width == :unknown
          return Type.new(:bits, width: [lhs_type.width, rhs_type.width].max * 2, qualifiers:)
        end
        value_else(value_result) do
          Type.new(:bits, width: :unknown, qualifiers:)
        end
      else
        qualifiers << :signed if lhs_type.signed? && rhs_type.signed?
        qualifiers << :known if lhs_type.known? && (short_circuit || rhs_type.known?)
        if [lhs_type.width, rhs_type.width].include?(:unknown)
          Type.new(:bits, width: :unknown, qualifiers:)
        else
          Type.new(:bits, width: [lhs_type.width, rhs_type.width].max, qualifiers:)
        end
      end
    end

    # @!macro type_check
    def type_check(symtab)
      internal_error "No type_check function #{lhs.inspect}" unless lhs.respond_to?(:type_check)

      lhs.type_check(symtab)
      short_circuit = T.let(false, T::Boolean)
      value_result = value_try do
        lhs_value = lhs.value(symtab)
        if (lhs_value == true && op == "||") || (lhs_value == false && op == "&&")
          short_circuit = true
        end
      end
      value_else(value_result) do
        short_circuit = false
      end
      rhs.type_check(symtab) unless short_circuit

      if ["<=", ">=", "<", ">", "!=", "=="].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        internal_error text_value if rhs_type.nil?
        unless rhs_type.comparable_to?(lhs_type)
          type_error "#{lhs.text_value} (type = #{lhs_type}) and #{rhs.text_value} (type = #{rhs_type}) are not comparable"
        end

      elsif ["&&", "||"].include?(op)
        lhs_type = lhs.type(symtab)
        unless lhs_type.convertable_to?(:boolean)
          type_error "left-hand side of #{op} needs to be boolean (is #{lhs_type}) (#{text_value})"
        end

        unless short_circuit
          rhs_type = rhs.type(symtab)
          unless rhs_type.convertable_to?(:boolean)
            type_error "right-hand side of #{op} needs to be boolean (is #{rhs_type}) (#{text_value})"
          end
        end

      elsif op == "<<"
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        type_error "Unsupported type for left shift: #{lhs_type}" unless lhs_type.kind == :bits
        type_error "Unsupported shift for left shift: #{rhs_type}" unless rhs_type.kind == :bits
      elsif op == "`<<"
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        type_error "Unsupported type for left shift: #{lhs_type}" unless lhs_type.kind == :bits
        type_error "Unsupported shift for left shift: #{rhs_type}" unless rhs_type.kind == :bits
        type_error "Widening shift amount must be constant (if it's not, the width of the result is unknowable)." unless rhs_type.const?
      elsif [">>", ">>>"].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        type_error "Unsupported type for right shift: #{lhs_type}" unless lhs_type.kind == :bits
        type_error "Unsupported shift for right shift: #{rhs_type}" unless rhs_type.kind == :bits
      elsif ["*", "`*", "/", "%"].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        unless lhs_type.integral? && rhs_type.integral?
          type_error "Multiplication/division is only defined for integral types. Maybe you forgot a $bits cast?"
        end
      elsif ["+", "-", "`+", "`-"].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        unless lhs_type.integral? && rhs_type.integral?
          type_error "Addition/subtraction is only defined for integral types. Maybe you forgot a $bits cast?"
        end
      elsif ["&", "|", "^"].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        unless lhs_type.integral? && rhs_type.integral?
          type_error "Bitwise operation is only defined for integral types. Maybe you forgot a $bits cast?"
        end
      else
        internal_error "Unhandled op '#{op}'"
      end
    end

    # @param value [Integer] the value
    # @param signed [Boolean] if true, return the number of bits needed if the value is a signed type
    # @return [Integer] the number of bits needed to represent value in two's complement
    def bits_needed(value, signed)
      if signed
        case value
        when 0
          1
        when 1
          2
        else
          if value > 0
            # need bit_legnth plus a sign bit
            bits = value.bit_length + 1
          else
            # need bit_length plus a sign bit, unless value is a power of 2
            if (value.abs & (value.abs - 1)) == 0
              value.bit_length
            else
              value.bit_length + 1
            end
          end
        end
      else
        internal_error "unsigned value is negative" if value < 0

        value == 0 ? 1 : value.bit_length
      end
    end

    def max_value(symtab)
      lhs_max_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        lhs_max_value = lhs.value(symtab)
      end
      value_else(value_result) do
        lhs_max_value = lhs.max_value(symtab)
      end

      lhs_min_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        lhs_min_value = lhs.value(symtab)
      end
      value_else(value_result) do
        lhs_min_value = lhs.min_value(symtab)
      end

      rhs_max_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        rhs_max_value = rhs.value(symtab)
      end
      value_else(value_result) do
        rhs_max_value = rhs.max_value(symtab)
      end
      rhs_min_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        rhs_min_value = rhs.value(symtab)
      end
      value_else(value_result) do
        rhs_min_value = rhs.min_value(symtab)
      end

      max_value =
        case @op
        when "+"
          return :unknown if [lhs_max_value, rhs_max_value].include?(:unknown)

          sum = T.cast(lhs_max_value, Integer) + T.cast(rhs_max_value, Integer)
          # convert to unsigned if needed
          sum = sum & ((1 << type(symtab).width) - 1) if sum < 0 && !type(symtab).signed?

          # check for truncation
          sum_bits_needed = bits_needed(sum, type(symtab).signed?)
          if type(symtab).width != :unknown
            return sum if sum_bits_needed <= type(symtab).width

            trunc_sum = truncate(sum, type(symtab).width, type(symtab).signed?)
            truncation_warn "result is truncated from #{sum} to #{trunc_sum}. Did you mean to use the widening additio
            n operator (`+)?"
            return trunc_sum
          else
            # sum width isn't known...we might still be able to know that it fits if the sum would fit
            # in lhs or rhs
            return sum if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= sum_bits_needed)
            return sum if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= sum_bits_needed)

            return :unknown # Cannot know if sum would be truncated
          end
        when "`+"
          return :unknown if [lhs_max_value, rhs_max_value].include?(:unknown)

          sum = T.cast(lhs_max_value, Integer) + T.cast(rhs_max_value, Integer)
          # convert to unsigned if needed
          sum = sum & ((1 << type(symtab).width) - 1) if sum < 0 && !type(symtab).signed?

          return sum
        when "-"
          return :unknown if [lhs_max_value, rhs_min_value].include?(:unknown)

          diff = T.cast(lhs_max_value, Integer) - T.cast(rhs_min_value, Integer)
          diff = diff & ((1 << type(symtab).width) - 1) if diff < 0 && !type(symtab).signed?
          diff_bits_needed = bits_needed(diff, type(symtab).signed?)

          if type(symtab).width != :unknown
            return diff if diff_bits_needed <= type(symtab).width

            trunc_diff = truncate(diff, type(symtab).width, type(symtab).signed?)
            truncation_warn "result is truncated from #{diff} to #{trunc_diff}. Did you mean to use the widening subtraction operator (`-)?"
            return trunc_diff
          else
            # diff width isn't known...we might still be able to know that it fits if the sum would fit
            # in lhs or rhs
            return diff if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= diff_bits_needed)
            return diff if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= diff_bits_needed)

            return :unknown # Cannot know if sum would be truncated
          end
        when "`-"
          return :unknown if [lhs_max_value, rhs_min_value].include?(:unknown)

          diff = T.cast(lhs_max_value, Integer) - T.cast(rhs_min_value, Integer)
          diff = diff & ((1 << type(symtab).width) - 1) if diff < 0 && !type(symtab).signed?

          return diff
        when "*"
          # max could be multiplying the mins if both are negative
          return :unknown if [lhs_max_value, rhs_max_value].include?(:unknown)

          if lhs.type(symtab).signed? && rhs.type(symtab).signed?
            return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)
          end

          prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer)
          if ![lhs_min_value, rhs_min_value].include?(:unknown) && ((T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)) > prod)
            prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)
          end
          prod = prod & ((1 << type(symtab).width) - 1) if prod < 0 && !type(symtab).signed?

          # check for truncation
          prod_bits_needed = bits_needed(prod, type(symtab).signed?)
          if (type(symtab).width != :unknown)
            return prod if prod_bits_needed <= type(symtab).width

            trunc_prod = truncate(prod, type(symtab).width, type(symtab).signed?)
            truncation_warn "result is truncated from #{prod} to #{trunc_prod}. Did you mean to use the widening multiplication operator (`*)?"
            return trunc_prod
          else
            # prod width isn't known...we might still be able to know that it fits if the sum would fit
            # in lhs or rhs
            return prod if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= prod_bits_needed)
            return prod if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= prod_bits_needed)

            return :unknown # Cannot know if sum would be truncated
          end
        when "`*"
          # max could be multiplying the mins if both are negative
          return :unknown if [lhs_max_value, rhs_max_value].include?(:unknown)

          if lhs.type(symtab).signed? && rhs.type(symtab).signed?
            return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)
          end

          prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer)
          if ![lhs_min_value, rhs_min_value].include?(:unknown) && ((T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)) > prod)
            prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)
          end

          prod
        end
      raise "TODO: #{op}" if max_value.nil?
      max_value
    end

    def min_value(symtab)
      lhs_max_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        lhs_max_value = lhs.value(symtab)
      end
      value_else(value_result) do
        lhs_max_value = lhs.max_value(symtab)
      end

      lhs_min_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        lhs_min_value = lhs.value(symtab)
      end
      value_else(value_result) do
        lhs_min_value = lhs.min_value(symtab)
      end

      rhs_max_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        rhs_max_value = rhs.value(symtab)
      end
      value_else(value_result) do
        rhs_max_value = rhs.max_value(symtab)
      end

      rhs_min_value = T.let(:unknown, T.any(Symbol, Integer))
      value_result = value_try do
        rhs_min_value = rhs.value(symtab)
      end
      value_else(value_result) do
        rhs_min_value = rhs.min_value(symtab)
      end

      case op
      when "+"
        return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)

        sum = T.cast(lhs_min_value, Integer) + T.cast(rhs_min_value, Integer)
        sum = sum & ((1 << type(symtab).width) - 1) if sum < 0 && !type(symtab).signed?

        # check for truncation
        sum_bits_needed = bits_needed(sum, type(symtab).signed?)
        if type(symtab).width != :unknown
          return sum if sum_bits_needed <= type(symtab).width

          trunc_sum = truncate(sum, type(symtab).width, type(symtab).signed?)
          truncation_warn "result is truncated from #{sum} to #{trunc_sum}. Did you mean to use the widening addition operator (`+)?"
          return trunc_sum
        else
          # sum width isn't known...we might still be able to know that it fits if the sum would fit
          # in lhs or rhs
          return sum if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= sum_bits_needed)
          return sum if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= sum_bits_needed)

          return :unknown # Cannot know if sum would be truncated
        end
      when "`+"
        return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)

        sum = T.cast(lhs_min_value, Integer) + T.cast(rhs_min_value, Integer)
        sum = sum & ((1 << type(symtab).width) - 1) if sum < 0 && !type(symtab).signed?

        return sum
      when "-"
        return :unknown if [lhs_min_value, rhs_max_value].include?(:unknown)

        diff = T.cast(lhs_min_value, Integer) - T.cast(rhs_max_value, Integer)
        diff = diff & ((1 << type(symtab).width) - 1) if diff < 0 && !type(symtab).signed?

        diff_bits_needed = bits_needed(diff, type(symtab).signed?)
        if type(symtab).width != :unknown
          return diff if diff_bits_needed <= type(symtab).width

          trunc_diff = truncate(diff, type(symtab).width, type(symtab).signed?)
          truncation_warn "result is truncated from #{diff} to #{trunc_diff}. Did you mean to use the widening subtraction operator (`-)?"
          return trunc_diff
        else
          # diff width isn't known...we might still be able to know that it fits if the sum would fit
          # in lhs or rhs
          return diff if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= diff_bits_needed)
          return diff if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= diff_bits_needed)

          return :unknown # Cannot know if sum would be truncated
        end
      when "`-"
        return :unknown if [lhs_min_value, rhs_max_value].include?(:unknown)

        diff = T.cast(lhs_min_value, Integer) - T.cast(rhs_max_value, Integer)
        diff = diff & ((1 << type(symtab).width) - 1) if diff < 0 && !type(symtab).signed?

        return diff
      when "*"
        # min could be any combination of mutliplying min/max if numbers are signed
        return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)

        if lhs.type(symtab).signed?
          return :unknown if rhs_max_value == :unknown
        end

        if rhs.type(symtab).signed?
          return :unknown if lhs_max_value == :unknown
        end

        prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)
        prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_max_value, Integer) if (rhs_max_value != :unknown) && ((T.cast(lhs_min_value, Integer) * T.cast(rhs_max_value, Integer)) < prod)
        prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_min_value, Integer) if (lhs_max_value != :unknown) && ((T.cast(lhs_max_value, Integer) * T.cast(rhs_min_value, Integer)) < prod)
        prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer) if (![lhs_max_value, rhs_min_value].include?(:unknown)) && ((T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer)) < prod)
        prod = prod & ((1 << type(symtab).width) - 1) if prod < 0 && !type(symtab).signed?

        # check for truncation
        prod_bits_needed = bits_needed(prod, type(symtab).signed?)
        if (type(symtab).width != :unknown)
          return prod if prod_bits_needed <= type(symtab).width

          trunc_prod = truncate(prod, type(symtab).width, type(symtab).signed?)
          truncation_warn "result is truncated from #{prod} to #{trunc_prod}. Did you mean to use the widening multiplication operator (`*)?"
          return trunc_prod
        else
          # sum width isn't known...we might still be able to know that it fits if the sum would fit
          # in lhs or rhs
          return prod if (lhs.type(symtab).width != :unknown) && (lhs.type(symtab).width >= prod_bits_needed)
          return prod if (rhs.type(symtab).width != :unknown) && (rhs.type(symtab).width >= prod_bits_needed)

          return :unknown # Cannot know if sum would be truncated
        end
      when "`*"
        # max could be multiplying the mins if both are negative
        return :unknown if [lhs_min_value, rhs_min_value].include?(:unknown)

        if lhs.type(symtab).signed?
          return :unknown if rhs_max_value == :unknown
        end

        if rhs.type(symtab).signed?
          return :unknown if lhs_max_value == :unknown
        end

        prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_min_value, Integer)
        prod = T.cast(lhs_min_value, Integer) * T.cast(rhs_max_value, Integer) if (rhs_max_value != :unknown) && ((T.cast(lhs_min_value, Integer) * T.cast(rhs_max_value, Integer)) < prod)
        prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_min_value, Integer) if (lhs_max_value != :unknown) && ((T.cast(lhs_max_value, Integer) * T.cast(rhs_min_value, Integer)) < prod)
        prod = T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer) if (![lhs_max_value, rhs_min_value].include?(:unknown)) && ((T.cast(lhs_max_value, Integer) * T.cast(rhs_max_value, Integer)) < prod)
        prod = prod & ((1 << type(symtab).width) - 1) if prod < 0 && !type(symtab).signed?

        return prod
      else
        raise "TODO: op '#{op}'"
      end
    end

    # @!macro value
    def value(symtab)
      # cached_value = @value_cache[symtab]
      # return cached_value unless cached_value.nil?

      value =
        if op == ">>>"
          lhs_value = lhs.value(symtab)
          if (lhs_value & (1 << (lhs.type(symtab).width - 1))).zero?
            shamt = rhs.value(symtab)
            shamt.zero? ? lhs_value : (lhs_value >> shamt)
          else
            # need to shift in ones
            shift_amount = rhs.value(symtab)
            if shift_amount.zero?
              lhs_value
            else
              shifted_value = lhs_value >> shift_amount
              mask_len = [lhs.type(symtab).width, shift_amount].min
              mask = ((1 << mask_len) - 1) << [(lhs.type(symtab).width - shift_amount), 0].max

              shifted_value | mask
            end
          end
        elsif ["&&", "||"].include?(op)
          # these can short circuit, so we might only need to check the lhs
          lhs_value = lhs.value(symtab)
          if (op == "&&") && lhs_value == false
            false
          elsif (op == "||") && lhs_value == true
            true
          else
            if op == "&&"
              lhs_value && rhs.value(symtab)
            else
              lhs_value || rhs.value(symtab)
            end
          end
        elsif op == "=="
          value_result = value_try do
            return lhs.value(symtab) == rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that == is false if the possible values of each do not overlap
            if lhs.values(symtab).intersection(rhs.values(symtab)).empty?
              false
            else

              value_error "There is overlap in the lhs/rhs return values"
            end
          end
        elsif op == "!="
          value_result = value_try do
            return lhs.value(symtab) != rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that != is true if the possible values of each do not overlap
            if lhs.values(symtab).intersection(rhs.values(symtab)).empty?
              true
            else
              value_error "There is overlap in the lhs/rhs return values"
            end
          end
        elsif op == "<="
          value_result = value_try do
            return lhs.value(symtab) <= rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that != is true if the possible values of lhs are all <= the possible values of rhs
            rhs_values = rhs.values(symtab)
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value <= rhs_value } }
              true
            else
              value_error "Some value of lhs is not <= some value of rhs"
            end
          end
        elsif op == ">="
          value_result = value_try do
            return lhs.value(symtab) >= rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that != is true if the possible values of lhs are all >= the possible values of rhs
            rhs_values = rhs.values(symtab)
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value >= rhs_value } }
              true
            else
              value_error "Some value of lhs is not >= some value of rhs"
            end
          end
        elsif op == "<"
          value_result = value_try do
            return lhs.value(symtab) < rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that != is true if the possible values of lhs are all < the possible values of rhs
            rhs_values = rhs.values(symtab)
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value < rhs_value } }
              true
            else
              value_error "Some value of lhs is not < some value of rhs"
            end
          end
        elsif op == ">"
          value_result = value_try do
            return lhs.value(symtab) > rhs.value(symtab)
          end
          value_else(value_result) do
            # even if we don't know the exact value of @lhs and @rhs, we can still
            # know that != is true if the possible values of lhs are all > the possible values of rhs
            rhs_values = rhs.values(symtab)
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value > rhs_value } }
              true
            else
              value_error "Some value of lhs is not > some value of rhs"
            end
          end
        elsif op == "&"
          # if one side is zero, we don't need to know the other side
          value_result = value_try do
            return 0 if lhs.value(symtab).zero?
          end
          # ok, try rhs

          return 0 if rhs.value(symtab).zero?

          lhs.value(symtab) & rhs.value(symtab)

        elsif op == "|"
          # if one side is all ones, we don't need to know the other side
          rhs_type = rhs.type(symtab)
          value_error("Unknown width") if rhs_type.width == :unknown
          lhs_type = lhs.type(symtab)
          value_error("unknown width") if lhs_type.width == :unknown

          value_result = value_try do
            rhs_mask = ((1 << rhs_type.width) - 1)
            return rhs_mask if (rhs.value(symtab) == rhs_mask) && (lhs_type.width <= rhs_type.width)
          end
          # ok, try rhs

          lhs_mask = ((1 << lhs_type.width) - 1)
          return lhs_mask if (lhs.value(symtab) == lhs_mask) && (rhs_type.width <= lhs_type.width)

          lhs.value(symtab) | rhs.value(symtab)

        else
          v =
            case op
            when "+", "`+"
              lhs.value(symtab) + rhs.value(symtab)
            when "-", "`-"
              lhs.value(symtab) - rhs.value(symtab)
            when "*", "`*"
              lhs.value(symtab) * rhs.value(symtab)
            when "/"
              lhs.value(symtab) / rhs.value(symtab)
            when "%"
              lhs.value(symtab) % rhs.value(symtab)
            when "^"
              lhs.value(symtab) ^ rhs.value(symtab)
            when "|"
              lhs.value(symtab) | rhs.value(symtab)
            when "&"
              lhs.value(symtab) & rhs.value(symtab)
            when ">>"
              lhs.value(symtab) >> rhs.value(symtab)
            when "<<", "`<<"
              lhs.value(symtab) << rhs.value(symtab)
            else
              internal_error "Unhandled binary op #{op}"
            end

          expr_type = type(symtab).width
          value_error "Cannot know value of Bits with unknown width" if expr_type == :unknown

          v_trunc =
            if op.include?("`")
              v
            else
              truncate(v, type(symtab).width, type(symtab).signed?)
            end

          truncation_warn "The value of '#{text_value}' is truncated from #{v} to #{v_trunc} because the result is only #{type(symtab).width} bits" if v != v_trunc
          v_trunc
        end
      # @value_cache[symtab] = value
      value
    end

    # returns the operator as a string
    attr_reader :op
  end

  class ParenExpressionSyntaxNode < SyntaxNode
    def to_ast
      ParenExpressionAst.new(input, interval, send(:e).to_ast)
    end
  end

  # represents a parenthesized expression
  #
  # for example:
  #  (a + b)
  class ParenExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = expression.const_eval?(symtab)

    def initialize(input, interval, exp) = super(input, interval, [exp])

    def expression = @children[0]

    def invert(symtab) = expression.invert(symtab)

    # @!macro type_check
    def type_check(symtab) = expression.type_check(symtab)

    # @!macro type
    def type(symtab) = expression.type(symtab)

    # @!macro value
    def value(symtab) = expression.value(symtab)

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "(#{expression.to_idl})"
  end

  class ArrayLiteralSyntaxNode < SyntaxNode
    def to_ast
      ArrayLiteralAst.new(input, interval, [send(:first).to_ast] + send(:rest).elements.map { |r| r.expression.to_ast })
    end
  end

  class ArrayLiteralAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = element_nodes.all? { |enode| enode.const_eval?(symtab) }

    def entries = @children

    def element_nodes
      entries
    end

    # @!macro type_check
    def type_check(symtab)
      entries.each do |node|
        node.type_check(symtab)
      end

      unless element_nodes.all? { |e| e.type(symtab).equal_to?(element_nodes[0].type(symtab)) }
        type_error "Array elements must be identical"
      end
    end

    def type(symtab)
      Type.new(:array, width: element_nodes.size, sub_type: element_nodes[0].type(symtab))
    end

    def value(symtab)
      element_nodes.map { |e| e.value(symtab) }
    end

    sig { override.returns(String) }
    def to_idl = "[#{element_nodes.map(&:to_idl).join(',')}]"
  end

  class ConcatenationExpressionSyntaxNode < SyntaxNode
    def to_ast
      ConcatenationExpressionAst.new(input, interval, [send(:first).to_ast] + send(:rest).elements.map { |e| e.expression.to_ast })
    end
  end

  # represents a concatenation expression
  #
  # for example:
  #   {1'b0, 5'd3}
  class ConcatenationExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = expressions.all? { |e| e.const_eval?(symtab) }

    def expressions = @children

    # @!macro type_check
    def type_check(symtab)
      type_error "Must concatenate at least two objects" if expressions.size < 2

      expressions.each do |exp|
        exp.type_check(symtab)
        e_type = exp.type(symtab)
        type_error "Concatenation only supports Bits<> types" unless e_type.kind == :bits

        internal_error "Negative width for element #{exp.text_value}" if (e_type.width != :unknown) && (e_type.width <= 0)
      end
    end

    # @!macro type
    def type(symtab)
      all_known_values = T.let(true, T::Boolean)
      width_known = T.let(true, T::Boolean)

      is_const = T.let(true, T::Boolean)
      total_width = expressions.reduce(0) do |sum, exp|
        e_type = exp.type(symtab)
        if e_type.width == :unknown
          width_known = false
        elsif width_known
          sum = sum + e_type.width
        end
        all_known_values &= e_type.known?
        sum
      end

      qualifiers = is_const ? [:const] : []

      if all_known_values
        qualifiers << :known
        if width_known
          Type.new(:bits, width: total_width, qualifiers:)
        else
          Type.new(:bits, width: :unknown, qualifiers:)
        end
      else
        if width_known
          Type.new(:bits, width: total_width, qualifiers:)
        else
          Type.new(:bits, width: :unknown, qualifiers:)
        end
      end
    end

    # @!macro value
    def value(symtab)
      result = 0
      total_width = 0
      expressions.reverse_each do |exp|
        result |= (exp.value(symtab) << total_width)
        total_width += exp.type(symtab).width
      end
      result
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "{#{expressions.map { |exp| exp.to_idl }.join(',')}}"
  end

  class ReplicationExpressionSyntaxNode < SyntaxNode
    def to_ast
      ReplicationExpressionAst.new(input, interval, send(:n).to_ast, send(:v).to_ast)
    end
  end

  # represents a replication expression
  #
  # for example:
  #   {5{5'd3}}
  class ReplicationExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = n.const_eval?(symtab) && v.const_eval?(symtab)


    def n = @children[0]
    def v = @children[1]

    def initialize(input, interval, n, v)
      super(input, interval, [n, v])
    end

    # @!macro type_check
    def type_check(symtab)
      n.type_check(symtab)
      v.type_check(symtab)

      type_error "value of replication must be a Bits type" unless v.type(symtab).kind == :bits
      value_try do
        type_error "replication amount must be positive (#{n.value(symtab)})" unless n.value(symtab).positive?
      end
      # type_error "replication amount must be known at compile time"
    end

    # @!macro value
    def value(symtab)
      result = 0
      n.value(symtab).times do |i|
        result |= v.value(symtab) << (i * v.type(symtab).width)
      end
      result
    end

    # @!macro type
    def type(symtab)
      value_result = value_try do
        width = (n.value(symtab) * v.type(symtab).width)
        return Type.new(:bits, width:, qualifiers: [:known])
      end
      value_else(value_result) do
        Type.new(:bits, width: :unknown)
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "{#{n.to_idl}{#{v.to_idl}}}"
  end

  class PostDecrementExpressionSyntaxNode < SyntaxNode
    def to_ast
      PostDecrementExpressionAst.new(input, interval, send(:rval).to_ast)
    end
  end

  # represents a post-decrement expression
  #
  # for example:
  #   i--
  class PostDecrementExpressionAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = rval.const_eval?(symtab)

    sig { returns(T.any(IntLiteralAst, BuiltinVariableAst, StringLiteralAst, IdAst)) }
    def rval = T.cast(@children.fetch(0), T.any(IntLiteralAst, BuiltinVariableAst, StringLiteralAst, IdAst))

    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    def type_check(symtab)
      rval.type_check(symtab)
      rval_immutable =
        rval.is_a?(IdAst) && (rval.type(symtab).const? && !symtab.get(T.cast(rval, IdAst).name).for_loop_iter?)
      type_error "Cannot decrement a const variable" if rval_immutable
      type_error "Post decement must be integral" unless rval.type(symtab).integral?
    end

    def type(symtab)
      rval.type(symtab)
    end

    # @!macro execute
    def execute(symtab)
      var = symtab.get(rval.text_value)
      value_result = value_try do
        internal_error "No symbol #{rval.text_value}" if var.nil?

        value_error "value of variable '#{rval.text_value}' not know" if var.value.nil?

        var.value = var.value - 1
      end
      value_else(value_result) do
        var.value = nil
        value_error "value of variable '#{rval.text_value}' not know"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.get(rval.text_value).value = nil
    end

    sig { override.returns(String) }
    def to_idl = "#{rval.to_idl}--"
  end

  class BuiltinVariableSyntaxNode < SyntaxNode
    def to_ast
      BuiltinVariableAst.new(input, interval)
    end
  end

  class BuiltinVariableAst < AstNode

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      case name
      when "$encoding"
        true
      when "$pc"
        false
      else
        raise "TODO"
      end
    end

    def name = text_value

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
    end

    def type_check(symtab)
      type_error "Not a builtin variable" unless ["$pc", "$encoding"].include?(name)
    end

    def type(symtab)
      case name
      when "$encoding"
        sz = symtab.get("__instruction_encoding_size")
        internal_error "Forgot to set __instruction_encoding_size" if sz.nil?
        Type.new(:bits, width: sz.value, qualifiers: [:const, :known])
      when "$pc"
        if symtab.mxlen == 32
          Bits32Type
        else
          Bits64Type
        end
      end
    end

    def value(symtab)
      value_error "Cannot know the value of pc or encoding"
    end

    sig { override.returns(String) }
    def to_idl = name
  end

  class PostIncrementExpressionSyntaxNode < SyntaxNode
    def to_ast
      PostIncrementExpressionAst.new(input, interval, send(:rval).to_ast)
    end
  end

  # represents a post-increment expression
  #
  # for example:
  #   i++
  class PostIncrementExpressionAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = rval.const_eval?(symtab)

    def rval = @children[0]

    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    # @!macro type_check
    def type_check(symtab)
      rval.type_check(symtab)
      var = symtab.get(rval.text_value)
      rval_immutable =
        rval.is_a?(IdAst) && (rval.type(symtab).const? && !var.for_loop_iter?)
      type_error "Cannot increment a const variable" if rval_immutable
      type_error "Post increment variable must be integral" unless var.type.integral?
    end

    # @!macro type
    def type(symtab)
      rval.type(symtab)
    end

    # @!macro execute
    def execute(symtab)
      var = symtab.get(rval.text_value)

      value_result = value_try do
        internal_error "No symbol named '#{rval.text_value}'" if var.nil?

        value_error "#{rval.text_value} is not compile-time-known" if var.value.nil?

        var.value = var.value + 1
      end
      value_else(value_result) do
        var.value = nil
        value_error "#{rval.text_value} is not compile-time-known" if var.value.nil?
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.get(rval.text_value).value = nil
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{rval.to_idl}++"
  end

  class FieldAccessExpressionSyntaxNode < SyntaxNode
    def to_ast
      FieldAccessExpressionAst.new(input, interval, send(:field_access_eligible_expression).to_ast, send(:field_name).text_value)
    end
  end

  # represents a bitfield or struct field access (rvalue)
  #
  # for example:
  #   entry.PPN
  class FieldAccessExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = obj.const_eval?(symtab)

    sig { returns(RvalueAst) }
    def obj = T.cast(@children.fetch(0), RvalueAst)

    def initialize(input, interval, bitfield, field_name)
      super(input, interval, [bitfield])

      @field_name = field_name
    end

    def kind(symtab)
      obj.type(symtab).kind
    end

    # @!macro type
    def type(symtab)
      obj_type = obj.type(symtab)

      if obj_type.kind == :bitfield
        Type.new(:bits, width: T.cast(obj_type, BitfieldType).range(@field_name).size)
      elsif obj_type.kind == :struct
        T.cast(obj_type, StructType).member_type(@field_name)
      else
        internal_error "huh? #{obj.text_value} #{obj_type.kind}"
      end
    end

    def type_check(symtab)
      obj.type_check(symtab)

      obj_type = obj.type(symtab)

      if obj_type.kind == :bitfield
        internal_error "#{obj.text_value} Not a BitfieldType (is a #{obj_type.class.name})" unless obj_type.respond_to?(:field_names)
        unless T.cast(obj_type, BitfieldType).field_names.include?(@field_name)
          type_error "#{@field_name} is not a member of #{obj_type}"
        end
      elsif obj_type.kind == :struct
        type_error "#{@field_name} is not a member of #{obj_type}" unless T.cast(obj_type, StructType).member?(@field_name)
      else
        type_error "#{obj.text_value} is not a bitfield (is #{obj.type(symtab)})"
      end
    end

    # @!macro value
    def value(symtab)
      if kind(symtab) == :bitfield
        range = T.cast(obj.type(symtab), BitfieldType).range(@field_name)
        (T.cast(obj.value(symtab), Integer) >> range.first) & ((1 << range.size) - 1)
      elsif kind(symtab) == :struct
        T.cast(obj.value(symtab), T::Hash[String, BasicValueRbType])[@field_name]
      else
        type_error "#{obj.text_value} is Not a bitfield."
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{obj.to_idl}.#{@field_name}"
  end

  class EnumRefSyntaxNode < SyntaxNode
    def to_ast
      EnumRefAst.new(input, interval, send(:enum_class).text_value, send(:member).text_value)
    end
  end

  # represents an enum reference
  #
  # for example:
  #  ExtensionName::C
  #  PrivilegeMode::M
  class EnumRefAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def class_name = @enum_class_name
    def member_name = @member_name

    def initialize(input, interval, class_name, member_name)
      super(input, interval, EMPTY_ARRAY)

      @enum_class_name = class_name
      @member_name = member_name
      @enum_def_type = nil
    end

    # @!macro freeze_tree
    def freeze_tree(global_symtab)
      return if frozen?

      @enum_def_type = global_symtab.get(@enum_class_name)

      unless @enum_def_type.kind == :enum
        type_error "#{@enum_class_name} is not a defined Enum"
      end

      freeze
    end

    # @!macro type_check
    def type_check(symtab)
      enum_def_type = @enum_def_type

      type_error "No symbol #{@enum_class_name} has been defined" if enum_def_type.nil?

      type_error "#{@enum_class_name} is not an enum type" unless enum_def_type.is_a?(EnumerationType)
      type_error "#{@enum_class_name} has no member '#{@member_name}'" if enum_def_type.value(@member_name).nil?
    end

    # @!macro type
    def type(symtab)
      internal_error "Not frozen?" unless frozen?
      type_error "No enum named #{@enum_class_name}" if @enum_def_type.nil?

      @enum_def_type.ref_type
    end

    # @!macro value_no
    def value(symtab)
      @enum_def_type ||= begin
        enum_def_ast = symtab.get(@enum_class_name)
        if enum_def_ast.is_a?(BuiltinEnumDefinitionAst)
          enum_def_ast.type(symtab)
        else
          enum_def_ast.type(nil)
        end
      end
      internal_error "Must call type_check first" if @enum_def_type.nil?

      @enum_def_type.value(@member_name)
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{@enum_class_name}::#{@member_name}"
  end

  class UnaryOperatorExpressionSyntaxNode < SyntaxNode
    def to_ast
      UnaryOperatorExpressionAst.new(input, interval, send(:o).text_value, send(:e).to_ast)
    end
  end

  # represents a unary operator
  #
  # for example:
  #   -value
  #   ~value
  #   !bool_variable
  class UnaryOperatorExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = expression.const_eval?(symtab)

    def expression = @children[0]

    def initialize(input, interval, op, expression)
      super(input, interval, [expression])

      @op = op
    end

    def invert(symtab)
      unless symtab.nil?
        type_error "Not a boolean operator" unless type(symtab).kind == :boolean
      end

      type_error "Invert only works with !" unless op == "!"

      expression
    end

    # @!macro type
    def type(symtab)
      case op
      when "-", "~"
        exp.type(symtab).clone
      when "!"
        if exp.type(symtab).const?
          ConstBoolType
        else
          BoolType
        end
      else
        internal_error "unhandled op #{op}"
      end
    end

    # @!macro type_check
    def type_check(symtab)
      exp.type_check(symtab)

      case op
      when "-"
        unless [:bits, :bitfield].include?(exp.type(symtab).kind)
          type_error "#{exp.type(symtab)} does not support unary #{op} operator"
        end

        # type_error "Unary minus only works on signed values" unless exp.type(symtab).signed?
      when "~"
        unless [:bits, :bitfield].include?(exp.type(symtab).kind)
          type_error "#{exp.type(symtab)} does not support unary #{op} operator"
        end
      when "!"
        unless exp.type(symtab).convertable_to?(:boolean)
          if exp.type(symtab).kind == :bits
            type_error "#{exp.type(symtab)} does not support unary #{op} operator. Perhaps you want '#{exp.text_value} != 0'?"
          else
            type_error "#{exp.type(symtab)} does not support unary #{op} operator"
          end
        end
      else
        internal_error "Unhandled op #{op}"
      end
    end

    # @!macro value
    def value(symtab)
      val = val_trunc =
        case op
        when "-"
          -exp.value(symtab)
        when "~"
          ~exp.value(symtab)
        when "!"
          !exp.value(symtab)
        else
          internal_error "Unhandled unary op #{op}"
        end
      t = type(symtab)
      if t.integral?
        if t.width == :unknown
          value_error("Unknown width for truncation")
        end
        val_trunc = truncate(val, t.width, t.signed?)
      end

      if op != "~"
        truncation_warn "#{text_value} is truncated due to insufficient bit width (from #{val} to #{val_trunc})" if val_trunc != val
      end

      val_trunc
    end

    # @return [AstNode] the operated-on expression
    def exp
      expression
    end

    # @return [String] The operator
    def op
      @op
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{op}#{expression.to_idl}"
  end

  class TernaryOperatorExpressionSyntaxNode < SyntaxNode
    def to_ast
      TernaryOperatorExpressionAst.new(input, interval, send(:e).to_ast, send(:t).to_ast, send(:f).to_ast)
    end
  end

  # Represents a ternary operator
  #
  # for example:
  #   condition ? a : b
  #   (a < b) ? c : d
  class TernaryOperatorExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = condition.const_eval?(symtab) && true_expression.const_eval?(symtab) && false_expression.const_eval?(symtab)

    def condition = @children[0]
    def true_expression = @children[1]
    def false_expression = @children[2]

    def initialize(input, interval, condition, true_expression, false_expression)
      super(input, interval, [condition, true_expression, false_expression])
    end

    # @!macro type_check
    def type_check(symtab)
      condition.type_check(symtab)
      if condition.type(symtab).kind == :bits
        type_error "ternary selector must be bool (maybe you meant '#{condition.text_value} != 0'?)"
      else
        type_error "ternary selector must be bool" unless condition.type(symtab).kind == :boolean
      end

      value_result = value_try do
        cond = condition.value(symtab)
        # if the condition is compile-time-known, only check the used field
        cond ? true_expression.type_check(symtab) : false_expression.type_check(symtab)
      end
      value_else(value_result) do
        true_expression.type_check(symtab)
        false_expression.type_check(symtab)

        unless true_expression.type(symtab).equal_to?(false_expression.type(symtab))
          # we'll allow dissimilar if they are both bits type
          unless true_expression.type(symtab).kind == :bits && false_expression.type(symtab).kind == :bits
            type_error "True and false options must be same type (have #{true_expression.type(symtab)} and #{false_expression.type(symtab)})"
          end
        end
      end
    end

    # @!macro type
    def type(symtab)
      condition.type_check(symtab)
      value_result = value_try do
        cond = condition.value(symtab)
        # if the condition is compile-time-known, only check the used field
        if cond
          return true_expression.type(symtab)
        else
          return false_expression.type(symtab)
        end
      end
      value_else(value_result) do
        t =
          if true_expression.type(symtab).kind == :bits && false_expression.type(symtab).kind == :bits
            true_width = true_expression.type(symtab).width
            false_width = false_expression.type(symtab).width
            known = true_expression.type(symtab).known? && false_expression.type(symtab).known?
            if true_width == :unknown || false_width == :unknown
              if known
                Type.new(:bits, width: :unknown, qualifiers: [:known])
              else
                Type.new(:bits, width: :unknown)
              end
            else
              if known
                Type.new(:bits, width: [true_width, false_width].max, qualifiers: [:known])
              else
                Type.new(:bits, width: [true_width, false_width].max)
              end
            end
          else
            true_expression.type(symtab).clone
          end
        if condition.type(symtab).const? && true_expression.type(symtab).const? && false_expression.type(symtab).const?
          t.make_const!
        end
        return t
      end
    end

    # @!macro value
    def value(symtab)
      condition.value(symtab) ? true_expression.value(symtab) : false_expression.value(symtab)
    end

    # @!macro values
    def values(symtab)
      value_result = value_try do
        return condition.value(symtab) ? true_expression.values(symtab) : false_expression.values(symtab)
      end
      value_else(value_result) do
        (true_expression.values(symtab) + false_expression.values(symtab)).uniq
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{condition.to_idl} ? #{true_expression.to_idl} : #{false_expression.to_idl}"
  end

  class StatementSyntaxNode < SyntaxNode
    def to_ast
      StatementAst.new(input, interval, send(:a).to_ast)
    end
  end

  class NoopAst < AstNode
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize
      super("", 0...0, EMPTY_ARRAY)
    end

    # @!macro type_check
    def type_check(symtab); end

    # @!macro execute
    def execute(symtab); end

    # @!macro execute_unknown
    def execute_unknown(symtab); end

    # @1macro to_idl
    sig { override.returns(String) }
    def to_idl = ""
  end

  # represents a simple, one-line statement
  #
  # for example:
  #   Bits<64> new_variable;
  #   new_variable = 4;
  #   func();
  class StatementAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = action.const_eval?(symtab)

    def action = @children[0]

    def initialize(input, interval, action)
      super(input, interval, [action])
    end

    # @!macro type_check
    def type_check(symtab)
      action.type_check(symtab)
    end

    # @!macro execute
    def execute(symtab)
      if action.is_a?(Declaration)
        action.add_symbol(symtab)
      end
      if action.is_a?(Executable)
        action.execute(symtab)
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      if action.is_a?(Declaration)
        action.add_symbol(symtab)
      end
      if action.is_a?(Executable)
        action.execute_unknown(symtab)
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{action.to_idl};"
  end

  class ConditionalStatementSyntaxNode < SyntaxNode
    def to_ast
      ConditionalStatementAst.new(input, interval, send(:a).to_ast, send(:expression).to_ast)
    end
  end

  # represents a predicated simple statement
  #
  # for example:
  #   a = 2 if condition;
  class ConditionalStatementAst < AstNode
    def action = @children[0]
    def condition = @children[1]

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = action.const_eval?(symtab) && condition.const_eval?(symtab)

    def initialize(input, interval, action, condition)
      super(input, interval, [action, condition])
    end

    # @!macro type_check
    def type_check(symtab)
      action.type_check(symtab)
      type_error "Cannot declare from a conditional statement" if action.is_a?(Declaration)

      condition.type_check(symtab)
      type_error "condition is not boolean" unless condition.type(symtab).convertable_to?(:boolean)
    end

    # @!macro execute
    def execute(symtab)
      value_result = value_try do
        cond = condition.value(symtab)

        if (cond)
          action.execute(symtab)
        end
      end
      value_else(value_result) do
        # force action to set any values to nil
        action.execute_unknown(symtab)
        value_error ""
      end
    end

      # @!macro execute
    def execute_unknown(symtab)
      action.execute_unknown(symtab)
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      "#{action.to_idl} if (#{condition.to_idl});"
    end
  end

  class DontCareReturnSyntaxNode < SyntaxNode
    def to_ast
      DontCareReturnAst.new(input, interval)
    end
  end

  # represents a don't care return value
  #
  # for example:
  #   return -;
  class DontCareReturnAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
    end

    # @!macro type_check_no_args
    def type_check(_symtab)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab)
      Type.new(:dontcare)
    end

    # @!macro value_no_args
    def value(_symtab)
      internal_error "Must call set_expected_type first" if @expected_type.nil?

      case @expected_type.kind
      when :bits
        0
      when :boolean
        false
      else
        internal_error "Unhandled expected type"
      end
    end

    def set_expected_type(t)
      @expected_type = t
    end

    sig { override.returns(String) }
    def to_idl = "-"
  end

  class DontCareLvalueSyntaxNode < SyntaxNode
    def to_ast = DontCareLvalueAst.new(input, interval)
  end

  class DontCareLvalueAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval) = super(input, interval, EMPTY_ARRAY)

    # @!macro type_check_no_args
    def type_check(_symtab)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab)
      Type.new(:dontcare)
    end

    # @!macro value_no_args
    def value(_symtab) = internal_error "Why are you calling value for an lval?"

    sig { override.returns(String) }
    def to_idl = "-"
  end

  class ReturnStatementSyntaxNode < SyntaxNode
    def to_ast
      ReturnStatementAst.new(input, interval, send(:return_expression).to_ast)
    end
  end

  # represents a function return statement
  #
  # for example:
  #   return 5;
  #   return X[rs1] + 1;
  class ReturnStatementAst < AstNode
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = return_expression.const_eval?(symtab)

    def return_expression
      @children[0]
    end

    def initialize(input, interval, return_expression)
      super(input, interval, [return_expression])
    end

    # @return [Array<Type>] List of actual return types
    def return_types(symtab)
      return_expression.return_types(symtab)
    end

    # @return [Type] The actual return type
    def return_type(symtab)
      return_expression.return_type(symtab)
    end

    # @return [Type] The expected return type (as defined by the encolsing function)
    def expected_return_type(symtab)
      return_expression.expected_return_type(symtab)
    end

    # @!macro type_check
    def type_check(symtab)
      return_expression.type_check(symtab)
    end

    # @return [Array<AstNode>] List of return value nodes
    def return_value_nodes
      return_expression.return_value_nodes
    end

    def enclosing_function
      return_expression.enclosing_function
    end

    # @!macro return_value
    def return_value(symtab)
      return_expression.return_value(symtab)
    end

    # @!macro return_values
    def return_values(symtab)
      return_expression.return_values(symtab)
    end

    sig { override.returns(String) }
    def to_idl = "#{return_expression.to_idl};"
  end

  class ReturnExpressionSyntaxNode < SyntaxNode
    def to_ast
      return_asts =
        if send(:vals).empty?
          []
        else
          [send(:vals).first.e.to_ast] + \
            send(:vals).rest.elements.map { |r| r.e.to_ast }
        end
      ReturnExpressionAst.new(input, interval, return_asts)
    end
  end

  class ReturnExpressionAst < AstNode
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = return_value_nodes.all? { |node| node.const_eval?(symtab) }

    def return_value_nodes = @children

    def initialize(input, interval, return_nodes)
      super(input, interval, return_nodes)
      @func_type_cache = {}
    end

    # @return [Array<Type>] List of actual return types
    def return_types(symtab)
      if return_value_nodes.empty?
        [Type.new(:void)]
      elsif return_value_nodes[0].type(symtab).kind == :tuple
        return_value_nodes[0].type(symtab).tuple_types
      else
        return_value_nodes.map { |v| v.type(symtab) }
      end
    end

    # @return [Type] The actual return type
    def return_type(symtab)
      types = return_types(symtab)
      if types.empty?
        return Type.new(:void)
      elsif types.size > 1
        Type.new(:tuple, tuple_types: types)
      else
        types[0]
      end
    end

    # @!macro type_check
    def type_check(symtab)
      return_value_nodes.each do |v|
        v.type_check(symtab)
        type_error "Unknown type for #{v.text_value}" if v.type(symtab).nil?
      end

      if !return_value_nodes.empty? && return_value_nodes[0].type(symtab).kind == :tuple
        type_error("Can't combine tuple types in return") unless return_value_nodes.size == 1
      end

      unless return_type(symtab).convertable_to?(expected_return_type(symtab))
        type_error "Return type (#{return_type(symtab)}) not convertible to expected return type (#{expected_return_type(symtab)})"
      end
    end

    def enclosing_function
      find_ancestor(FunctionDefAst)
    end

    # @!macro return_value
    def return_value(symtab)
      if return_value_nodes.empty?
        :void
      elsif return_value_nodes.size == 1
        return_value_nodes[0].value(symtab)
      else
        return_value_nodes.map { |v| v.value(symtab) }
      end
    end

    # @!macro return_values
    def return_values(symtab)
      if return_value_nodes.empty?
        [:void]
      elsif return_value_nodes.size == 1
        return_value_nodes[0].values(symtab)
      else
        return_value_nodes.map { |v| v.values(symtab) }
      end
    end

    sig { override.returns(String) }
    def to_idl = "return #{return_value_nodes.map(&:to_idl).join(',')}"
  end

  class ConditionalReturnStatementSyntaxNode < SyntaxNode
    def to_ast
      ConditionalReturnStatementAst.new(input, interval, send(:return_expression).to_ast, send(:expression).to_ast)
    end
  end

  class ConditionalReturnStatementAst < AstNode
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = condition.const_eval?(symtab) && return_expression.const_eval?(symtab)

    def return_expression = @children[0]
    def condition = @children[1]

    def initialize(input, interval, return_expression, condition)
      super(input, interval, [return_expression, condition])
    end

    # @!macro type_check
    def type_check(symtab)
      condition.type_check(symtab)
      type_error "Condition must be boolean" unless condition.type(symtab).kind == :boolean
      return_expression.type_check(symtab)
    end

    # @return [Type] The actual return type
    def return_type(symtab)
      return_expression.return_type(symtab)
    end

    # @return [Array<Type>] List of actual return types
    def return_types(symtab)
      return_expression.return_types(symtab)
    end


    # @!macro return_value
    def return_value(symtab)
      cond = condition.value(symtab)

      if cond
        return_expression.return_value(symtab)
      end
    end

    # @!macro return_values
    def return_values(symtab)
      value_result = value_try do
        cond = condition.value(symtab)

        return cond ? return_expression.return_values(symtab) : EMPTY_ARRAY

      end
      value_else(value_result) do
        # condition isn't known, so the return value is always possible
        return_expression.return_values(symtab)
      end
    end

    sig { override.returns(String) }
    def to_idl = "#{return_expression.to_idl} if (#{condition.to_idl});"
  end

  # @api private
  class CommentSyntaxNode < SyntaxNode
    def to_ast = CommentAst.new(input, interval)
  end

  # represents a comment
  class CommentAst < AstNode
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
    end

    # @!macro type_check
    def type_check(symtab); end

    # @return [String] The comment text, with the leading hash and any leading space removed
    # @example
    #    # This is a comment     #=> "This is a comment"
    def content = T.must(text_value[1..]).strip

    sig { override.returns(String) }
    def to_idl = "# #{content}\n"
  end

  # @api private
  class BuiltinTypeNameSyntaxNode < SyntaxNode
    def to_ast
      if !respond_to?(:i)
        BuiltinTypeNameAst.new(input, interval, elements[0].text_value, nil)
      else
        BuiltinTypeNameAst.new(input, interval, elements[0].text_value, send(:i).to_ast)
      end
    end
  end

  # represents a type name of one of the builtin types:
  #
  #  * Bits<N>
  #  * Boolean
  #  * String
  #
  # And their aliases:
  #
  #  * XReg (Bits<XLEN>)
  #  * U32 (Bits<32>)
  #  * U64 (Bits<64>)
  class BuiltinTypeNameAst < AstNode

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = (@type_name == "bits") ? bits_expression.const_eval?(symtab) : true

    def bits_expression = @children[0]

    def initialize(input, interval, type_name, bits_expression)
      if bits_expression.nil?
        super(input, interval, EMPTY_ARRAY)
      else
        super(input, interval, [bits_expression])
      end
      @type_name = type_name
    end

    # @!macro type_check
    def type_check(symtab)
      if @type_name == "Bits"
        bits_expression.type_check(symtab)
        value_result = value_try do
          unless bits_expression.value(symtab).positive?
            type_error "Bits width (#{bits_expression.value(symtab)}) must be positive"
          end
        end
        type_error "Bits width (#{bits_expression.text_value}) must be const" unless bits_expression.type(symtab).const?
      end
      unless ["Bits", "String", "XReg", "Boolean", "U32", "U64"].include?(@type_name)
        type_error "Unimplemented builtin type #{text_value}"
      end
    end

    def freeze_tree(symtab)
      return if frozen?

      if @type_name == "Bits"
        # precalculate size if possible
        begin
          value_try do
            @bits_type = Type.new(:bits, width: bits_expression.value(symtab))
          end
        rescue TypeError
          # ok, probably in a function template
        end
        bits_expression&.freeze_tree(symtab)
      end
      freeze
    end

    # @!macro type
    sig { params(symtab: SymbolTable).returns(Type) }
    def type(symtab)
      case @type_name
      when "XReg"
        if symtab.mxlen == 32
          PossiblyUnknownBits32Type
        elsif symtab.mxlen == 64
          PossiblyUnknownBits64Type
        else
          Type.new(:bits, width: :unknown, max_width: 64)
        end
      when "Boolean"
        BoolType
      when "U32"
        PossiblyUnknownBits32Type
      when "U64"
        PossiblyUnknownBits64Type
      when "String"
        StringType
      when "Bits"
        return @bits_type unless @bits_type.nil?

        value_result = value_try do
          return Type.new(:bits, width: bits_expression.value(symtab))
        end
        value_else(value_result) do
          return Type.new(:bits, width: :unknown, width_ast: bits_expression)
        end
      else
        internal_error "TODO: #{text_value}"
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      if @type_name == "Bits"
        "Bits<#{bits_expression.to_idl}>"
      else
        @type_name
      end
    end
  end

  module StringLiteralSyntaxNode
    def to_ast
      T.bind(self, Treetop::Runtime::SyntaxNode)
      StringLiteralAst.new(input, interval)
    end
  end

  # represents a string literal
  #
  # @example
  #   ">= 1.0"
  #   "by_byte"
  class StringLiteralAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @type = Type.new(:string, width: value(nil).length, qualifiers: [:const])
    end

    # @!macro type_check
    def type_check(_symtab); end

    def type(symtab)
      @type
    end

    # @!macro value
    def value(_symtab)
      text_value.gsub('"', "")
    end

    sig { override.returns(String) }
    def to_idl = text_value
  end

  module IntLiteralSyntaxNode
    def to_ast
      T.bind(self, Treetop::Runtime::SyntaxNode)
      IntLiteralAst.new(input, interval)
    end
  end

  class UnknownLiteral
    def initialize(known_value, unknown_mask)
      @known_value = known_value
      @unknown_mask = unknown_mask
    end
    def bit_length
      [@known_value.bit_length, @unknown_mask.bit_length].max
    end
    def to_s
      known_str = @known_value.to_s(2).reverse
      x = @unknown_mask.to_s(2).reverse
      v = []
      ([known_str.size, x.size].max).times do |i|
        if i >= known_str.size
          v << ((x[i] == "1") ? "x" : "0")
        elsif i >= x.size
          v << known_str[i]
        else
          if x[i] == "1"
            v << "x"
          else
            v << known_str[i]
          end
        end
      end
      "0b#{v.reverse.join("")}"
    end
  end

  # TODO: move this into a unit test
  tmp = UnknownLiteral.new(5, 4)
  raise tmp.to_s unless tmp.to_s == "0bx01"
  tmp = UnknownLiteral.new(0x7fff_ffff, 0b1000_0000_0000)
  raise tmp.to_s unless tmp.to_s == "0b1111111111111111111x11111111111"

  # represents an integer literal
  class IntLiteralAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
    end

    def freeze_tree(global_symtab)
      return if frozen?

      # initialize the cached objects
      type(global_symtab)
      value(global_symtab)
      freeze
    end

    # @!macro type_check
    def type_check(symtab)
      if text_value.delete("_") =~ /^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        value_text = ::Regexp.last_match(6)

        if width.nil? || width == "MXLEN"
          width = symtab.mxlen.nil? ? 32 : symtab.mxlen # 32 is the min width, which is what we care about here
        end

        # ensure we actually have enough bits to represent the value
        type_error("#{value_text} cannot be represented in #{width} bits") if unsigned_value.bit_length > width.to_i
      end
    end

    # @!macro type
    def type(symtab)
      return @type unless @type.nil?

      case text_value.delete("_")
      when /^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        signed = ::Regexp.last_match(4)
        value = ::Regexp.last_match(6)

        width = width(symtab)

        unless width == :unknown
          type_error("integer width must be positive (is #{width})") unless width.is_a?(Integer) && width.positive?
        end

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        qualifiers << :known unless T.must(value).include?("x")
        @type = Type.new(:bits, width:, qualifiers:)
      when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
        # C++-style literal
        signed = ::Regexp.last_match(3)

        qualifiers = signed == "s" ? [:signed, :const, :known] : [:const, :known]
        @type = Type.new(:bits, width: width(symtab), qualifiers:)
      when /^([0-9]*)(s?)$/
        # basic decimal
        signed = ::Regexp.last_match(2)

        qualifiers = signed == "s" ? [:signed, :const, :known] : [:const, :known]
        @type = Type.new(:bits, width: width(symtab), qualifiers:)
      else
        internal_error "Unhandled int value '#{text_value}'"
      end
    end

    def width(symtab)
      return @width unless @width.nil?

      text_value_no_underscores = text_value.delete("_")

      case text_value_no_underscores
      when /^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        if width.nil? || width == "MXLEN"
          width = symtab.mxlen.nil? ? :unknown : symtab.mxlen
        else
          width = width.to_i
        end
        @width = width
      when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
        signed = ::Regexp.last_match(3)

        width = signed == "s" ? value(symtab).bit_length + 1 : value(symtab).bit_length
        width = 1 if width.zero? # happens when the literal is '0'

        @width = width
      when /^([0-9]*)(s?)$/
        signed = ::Regexp.last_match(3)

        width = signed == "s" ? value(symtab).bit_length + 1 : value(symtab).bit_length
        width = 1 if width.zero? # happens when the literal is '0'

        @width = width
      else
        internal_error "No match on int literal"
      end
    end

    # @!macro value
    def value(symtab)
      return @value unless @value.nil?

      if text_value.delete("_") =~ /^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        signed = T.must(::Regexp.last_match(4))
        width = width(symtab)

        v =
          if width == :unknown
            if !signed.empty?
              if unsigned_value > 0x7fff_ffff
                value_error("Don't know if value will be negative")
              else
                if unsigned_value > 0xffff_ffff
                  value_error("Don't know if value will fit in literal")
                end
                unsigned_value
              end
            else
              if unsigned_value > 0xffff_ffff
                value_error("Don't know if value will fit in literal")
              end
              unsigned_value
            end
          else
            if unsigned_value.bit_length > width
              value_error("Value does not fit in literal")
            end
            if !signed.empty? && ((unsigned_value >> (width - 1)) == 1)
              if unsigned_value.bit_length > (width - 1)
                value_error("Value does not fit in literal")
              end
              -(2**width.to_i - unsigned_value)
            else
              unsigned_value
            end
          end

        @value = v
      else
        @value = unsigned_value
      end
    end


    # @return [Integer] the unsigned value of this literal (i.e., treating it as unsigned even if the signed specifier is present)
    def unsigned_value
      return @unsigned_value unless @unsigned_value.nil?

      @unsigned_value =
        case text_value.delete("_")
        when /^((MXLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
          # verilog-style literal
          radix_id = T.must(::Regexp.last_match(5))
          value = T.must(::Regexp.last_match(6))

          radix_id = "d" if radix_id.empty?

          if value.index("x").nil? && value.index("X").nil?
            case radix_id
            when "b"
              value.to_i(2)
            when "o"
              value.to_i(8)
            when "d"
              value.to_i(10)
            when "h"
              value.to_i(16)
            end
          else
            # there is unknown bit(s) in the value
            known_value =
              case radix_id
              when "b"
                value.gsub(/xX/, "0").to_i(2)
              when "o"
                value.gsub(/xX/, "0").to_i(8)
              when "d"
                raise "impossible"
              when "h"
                value.gsub(/xX/, "0").to_i(16)
              end
            unknown_mask =
              case radix_id
              when "b"
                value.gsub("1", "0").gsub(/[xX]/, "1").to_i(2)
              when "o"
                value.gsub(/[0-7]/, "0").gsub(/[xX]/, "7").to_i(8)
              when "d"
                raise "impossible"
              when "h"
                value.gsub(/[0-9a-fA-F]/, "0").gsub(/[xX]/, "f").to_i(16)
              end
            UnknownLiteral.new(known_value, unknown_mask)
          end
        when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
          # C++-style literal
          radix_id = T.must(::Regexp.last_match(1))
          value = T.must(::Regexp.last_match(2))

          radix_id = "o" if radix_id.empty?

          # @unsigned_value =
          case radix_id
          when "b"
            value.to_i(2)
          when "o"
            value.to_i(8)
          when "d"
            value.to_i(10)
          when "x"
            value.to_i(16)
          end

        when /^([0-9]*)(s?)$/
          # basic decimal
          value = T.must(::Regexp.last_match(1))

          # @unsigned_value = value.to_i(10)
          value.to_i(10)
        else
          internal_error "Unhandled int value '#{text_value}'"
        end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = text_value

    sig { override.returns(String) }
    def to_idl_verbose
      if @width == :unknown
        "MXLEN'#{@type.signed? ? 's' : ''}d#{unsigned_value}"
      else
        "#{@width}'#{@type.signed? ? 's' : ''}d#{unsigned_value}"
      end
    end
  end

  class FunctionCallExpressionSyntaxNode < SyntaxNode
    def to_ast
      targs = send(:t).empty? ? EMPTY_ARRAY : [send(:t).targs.first.to_ast] + send(:t).targs.rest.elements.map { |e| e.arg.to_ast }
      args = []
      args << send(:function_arg_list).first.to_ast unless send(:function_arg_list).first.empty?
      args += send(:function_arg_list).rest.elements.map { |e| e.expression.to_ast }
      FunctionCallExpressionAst.new(input, interval, send(:function_name).text_value, targs, args)
    end
  end

  class FunctionCallExpressionAst < AstNode
    # a function call can be both Lvalue (when void or return is ignored) and Rvalue
    include Rvalue
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      targs.all? { |targ| targ.const_eval?(symtab) } && \
        args.all? { |arg| arg.const_eval?(symtab) } && \
        func_type(symtab).func_def_ast.const_eval?(symtab)
    end

    def targs = children[0...@num_targs]
    def args = children[@num_targs..]

    def initialize(input, interval, function_name, targs, args)
      raise ArgumentError, "targs should be an array" unless targs.is_a?(Array)
      raise ArgumentError, "args should be an array" unless args.is_a?(Array)

      super(input, interval, targs + args)
      @num_targs = targs.size

      @name = function_name
      @reachable_exceptions_func_call_cache = {}
      @func_def_type_cache = {}
    end

    # @return [Boolean] whether or not the function call has a template argument
    def template?
      !targs.empty?
    end

    # @return [Array<AstNode>] Template argument nodes
    def template_arg_nodes
      targs
    end

    def template_values(symtab, unknown_ok: false)
      return EMPTY_ARRAY unless template?

      if unknown_ok
        template_arg_nodes.map do |e|
          val = T.let(nil, T.nilable(T.any(Integer, Symbol)))
          value_result = value_try do
            val = e.value(symtab)
          end
          value_else(value_result) do
            val = :unknown
          end
          val
        end
      else
        template_arg_nodes.map { |e| e.value(symtab) }
      end
    end

    # @return [Array<AstNode>] Function argument nodes
    def arg_nodes
      args
    end

    def func_type(symtab)
      func_def_type = @func_def_type_cache[symtab.name]
      return func_def_type unless func_def_type.nil?

      func_def_type = symtab.get(@name)
      type_error "No symbol #{@name}" if func_def_type.nil?

      unless func_def_type.is_a?(FunctionType)
        type_error "#{@name} is not a function (it's a #{func_def_type.class.name})"
      end

      @func_def_type_cache[symtab.name] = func_def_type
    end

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels

      tvals = template_values(symtab, unknown_ok: true)

      func_def_type = func_type(symtab)

      type_error "Template arguments provided in call to non-template function #{@name}" if template? && func_def_type.template_names.empty?

      type_error "Missing template arguments in call to #{@name}" if !template? && !func_def_type.template_names.empty?

      if template?
        num_targs = template_arg_nodes.size
        if func_def_type.template_names.size != num_targs
          type_error "Wrong number of template arguments (expecting #{func_def_type.template_names.size}, got #{num_targs})"
        end

        template_arg_nodes.each_with_index do |t, idx|
          t.type_check(symtab)
          unless t.type(symtab).convertable_to?(func_def_type.template_types(symtab)[idx])
            type_error "Template argument #{idx + 1} has wrong type"
          end
        end

        func_def_type.type_check_call(tvals, arg_nodes, symtab, self)
      else
        # no need to type check this function; it will be done on its own
        # func_def_type.type_check_call([], arg_nodes, symtab, self)
      end

      num_args = arg_nodes.size
      if func_def_type.num_args != num_args
        type_error "Wrong number of arguments to '#{name}' function call. Expecting #{func_def_type.num_args}, got #{num_args}"
      end
      arg_nodes.each do |a|
        a.type_check(symtab)
      end
      arg_nodes.each_with_index do |a, idx|
        unless a.type(symtab).convertable_to?(func_def_type.argument_type(idx, tvals, arg_nodes, symtab, self))
          type_error "Wrong type for argument number #{idx + 1}. Expecting #{func_def_type.argument_type(idx, tvals, arg_nodes, symtab, self)}, got #{a.type(symtab)}"
        end
      end

      if func_def_type.return_type(tvals, arg_nodes, self).nil?
        internal_error "No type determined for function"
      end

      internal_error "Function call symtab not at same level post type check (#{symtab.levels} #{level})" unless symtab.levels == level
    end

    # @!macro type
    def type(symtab)
      return ConstBoolType if name == "implemented?" || name == "implemented_version?" || name == "implemented_csr?"

      rtype = func_type(symtab).return_type(template_values(symtab, unknown_ok: true), arg_nodes, self)
      rtype = rtype.make_const if arg_nodes.all? { |a| a.type(symtab).const? } && func_type(symtab).func_def_ast.const_eval?(symtab)
      rtype
    end

    # @!macro value
    def value(symtab)
      # sometimes we want to evaluate for a specific XLEN
      if name == "xlen" && !symtab.get("__effective_xlen").nil?
        return symtab.get("__effective_xlen").value
      end

      func_def_type = func_type(symtab)
      type_error "#{name} is not a function" unless func_def_type.is_a?(FunctionType)
      if func_def_type.generated?
        value_error "builtin functions not provided" if @builtin_funcs.nil?

        if name == "implemented?"
          extname_ref = arg_nodes[0]
          type_error "First argument should be a ExtensionName" unless extname_ref.type(symtab).kind == :enum_ref && extname_ref.class_name == "ExtensionName"

          v = @builtin_funcs.implemented?.call(extname_ref.member_name)
          if v.nil?
            value_error "implemented? is only known when evaluating in the context of a fully-configured arch def"
          end
          return v

        elsif name == "implemented_version?"
          extname_ref = arg_nodes[0]
          type_error "First argument should be a ExtensionName" unless extname_ref.type(symtab).kind == :enum_ref && extname_ref.class_name == "ExtensionName"

          ver_req = arg_nodes[1].text_value[1..-2]

          v = @builtin_funcs.implemented_version?.call(extname_ref.member_name, ver_req)
          if v.nil?
            value_error "implemented_version? is only known when evaluating in the context of a fully-configured arch def"
          end
          return v

        elsif name == "implemented_csr?"
          csr_addr = arg_nodes[0].value(symtab)
          v = @builtin_funcs.implemented_csr?.call(csr_addr)
          if v.nil?
            value_error "implemented_csr? is only known when evaluating in the context of a fully-configured arch def"
          end
          return v

        elsif name == "cached_translation"
          value_error "cached_translation is not compile-time-knowable"
        elsif name == "maybe_cache_translation"
          value_error "maybe_cache_translation is not compile-time-knowable"
        elsif name == "invalidate_translations"
          value_error "invalidate_translations is not compile-time-knowable"
        elsif name == "direct_csr_lookup"
          value_error "direct_csr_lookup is not compile-time-knowable"
        elsif name == "indirect_csr_lookup"
          value_error "indirect_csr_lookup is not compile-time-knowable"
        elsif name == "csr_hw_read"
          value_error "csr_hw_read is not compile-time-knowable"
        elsif name == "csr_sw_read"
          value_error "csr_sw_read is not compile-time-knowable"
        elsif name == "csr_sw_write"
          value_error "csr_sw_write is not compile-time-knowable"
        else
          internal_error "Unimplemented generated: '#{name}'"
        end
      end
      if func_def_type.builtin?
        value_error "value of builtin functions aren't knowable"
      end

      template_values =
        if !template?
          EMPTY_ARRAY
        else
          template_arg_nodes.map do |targ|
            targ.value(symtab)
          end
        end

      func_def_type.return_value(template_values, arg_nodes, symtab, self)
    end
    alias execute value

    def name
      @name
    end

    # @!macro execute_unknown
    #  nothing to do for a function call
    def execute_unknown(symtab); end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      if template?
        "#{name}<#{template_arg_nodes.map(&:to_idl).join(',')}>(#{arg_nodes.map(&:to_idl).join(',')})"
      else
        "#{name}(#{arg_nodes.map(&:to_idl).join(',')})"
      end
    end
  end


  class UserTypeNameSyntaxNode < SyntaxNode
    def to_ast
      UserTypeNameAst.new(input, interval)
    end
  end

  class UserTypeNameAst < AstNode
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = true

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @type_cache = {}
    end

    # @!macro type_check
    def type_check(symtab)
      type = type(symtab)

      type_error "#{text_value} is not a type" unless type.is_a?(Type)
    end

    # @!macro type_no
    sig { params(symtab: SymbolTable).returns(Type) }
    def type(symtab)
      t = symtab.get(text_value)
      type_error "Undefined user type: '#{text_value}'" if t.nil?

      T.must(t)
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = text_value
  end

  TypeNameAst = T.type_alias { T.any(UserTypeNameAst, BuiltinTypeNameAst) }

  class InstructionOperationSyntaxNode < SyntaxNode
    def to_ast
      FunctionBodyAst.new(input, interval, send(:op_stmt_list).elements.map(&:choice).map(&:to_ast))
    end
  end

  class FunctionBodySyntaxNode < SyntaxNode
    # @!macro to_ast
    def to_ast
      FunctionBodyAst.new(input, interval, send(:func_stmt_list).elements.map(&:choice).map(&:to_ast))
    end
  end

  class FunctionBodyAst < AstNode
    include Executable
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      stmts.all? do |stmt|
        stmt.const_eval?(symtab)
      end
    end

    def initialize(input, interval, stmts)
      super(input, interval, stmts)
    end

    def statements = @children

    def stmts = @children

    # @!macro type_check
    def type_check(symtab)
      internal_error "Function bodies should be at global + 1 scope (at #{symtab.levels})" unless symtab.levels == 2

      return_value_might_be_known = true

      stmts.each do |s|
        s.type_check(symtab)
        # next unless return_value_might_be_known

        # begin
        #   if s.is_a?(Returns)
        #     s.return_value(symtab)
        #     # if we reach here, the return value is known, so we don't have to go further
        #     break
        #   else
        #     s.execute(symtab)
        #   end
        # rescue ValueError
        #   return_value_might_be_known = false
        # end
      end
    end

    def return_type(symtab)
      # go through the statements, and return the first one that has a return type
      stmts.each do |s|
        if s.is_a?(Returns)
          return s.return_type(symtab)
        elsif s.action.is_a?(Declaration)
          s.action.add_symbol(symtab)
        end
      end
      VoidType
    end

    # @!macro return_value
    #
    # @note arguments and template arguments must be put on the symtab before calling
    def return_value(symtab)
      internal_error "Function bodies should be at global + 1 scope" unless symtab.levels == 2

      # go through the statements, and return the first one that has a return value
      stmts.each do |s|
        if s.is_a?(Returns)
          v = s.return_value(symtab)
          return v unless v.nil?
        else
          s.execute(symtab)
        end
      end

      value_error "No function body statement returned a value"
    end
    alias execute return_value

    sig { override.params(symtab: SymbolTable).void }
    def execute_unknown(symtab)
      stmts.each do |s|
        s.execute(symtab)
      end
    end

    # @!macro return_values
    def return_values(symtab)
      internal_error "Function bodies should be at global + 1 scope" unless symtab.levels == 2

      values = T.let([], T::Array[ValueRbType])
      value_result = value_try do
        # if there is a definite return value, then just return that
        return [return_value(symtab)]
      end
      value_else(value_result) do
        # go through the statements, and collect return values
        # we can stop if we encounter a statement with a known return value
        stmts.each do |s|
          if s.is_a?(Returns)
            value_result = value_try do
              v = s.return_value(symtab)
              return values.push(v).uniq unless v.nil?
            end
            value_else(value_result) do
              values += s.return_values(symtab)
            end
          else
            s.execute(symtab)
          end
        end
      end

      values.uniq
    end

    sig { override.returns(String) }
    def to_idl
      stmts.map(&:to_idl).join("\n")
    end
  end

  class FetchSyntaxNode < SyntaxNode
    def to_ast
      FetchAst.new(input, interval, send(:function_body).to_ast)
    end
  end

  class FetchAst < AstNode
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = body.const_eval?(symtab)

    def body = @children[0]

    def initialize(input, interval, body)
      super(input, interval, [body])
    end

    def type_check(symtab)
      body.type_check(symtab)
    end

    def return_type(symtab)
      @ret_type = Type.new(:bits, width: symtab.get("INSTR_ENC_WIDTH").value)
    end

    sig { override.returns(String) }
    def to_idl
      <<~IDL
        fetch {
          #{body.to_idl}
        }
      IDL
    end
  end

  class FunctionDefSyntaxNode < SyntaxNode
    def to_ast
      FunctionDefAst.new(
        input,
        interval,
        send(:function_name).text_value,
        (!respond_to?(:targs) || send(:targs).empty?) ? [] : [send(:targs).first.to_ast] + send(:targs).rest.elements.map { |r| r.single_declaration.to_ast },
        if send(:ret).empty?
          []
else
  [send(:ret).first.to_ast] + (send(:ret).respond_to?(:rest) ? send(:ret).rest.elements.map { |r| r.type_name.to_ast } : [])
end,
        send(:args).empty? ? [] : [send(:args).first.to_ast] + send(:args).rest.elements.map { |r| r.single_declaration.to_ast },
        send(:desc).text_value,
        respond_to?(:type) ? send(:type).text_value.strip.to_sym : :normal,
        respond_to?(:body_block) ? send(:body_block).function_body.to_ast : nil
      )
    end
  end

  class FunctionDefAst < AstNode
    include Declaration

    attr_reader :return_type_nodes

    # @param input [String] The source code
    # @param interval [Range] The range in the source code for this function definition
    # @param name [String] The name of the function
    # @param targs [Array<AstNode>] Template arguments
    # @param return_types [Array<AstNode>] Return types
    # @param arguments [Array<AstNode>] Arguments
    # @param desc [String] Description
    # @param type [:normal, :builtin, :generated, :external] Type of function
    # @param body [AstNode,nil] Body, unless the function is builtin
    def initialize(input, interval, name, targs, return_types, arguments, desc, type, body)
      if body.nil?
        super(input, interval, targs + return_types + arguments)
      else
        super(input, interval, targs + return_types + arguments + [body])
      end

      @name = name
      @targs = targs
      @return_type_nodes = return_types
      @argument_nodes = arguments
      @desc = desc
      @body = body
      @builtin = type == :builtin
      @generated = type == :generated
      @external = type == :external

      @cached_return_type = {}
      @reachable_functions_cache ||= {}
    end

    attr_reader :reachable_functions_cache, :argument_nodes

    # @!macro freeze_tree
    def freeze_tree(global_symtab)
      return if frozen?

      unless templated?
        arguments(global_symtab)
      end

      @children.each { |child| child.freeze_tree(global_symtab) }
      freeze
    end

    # @return [String] Asciidoc formatted function description
    def description
      unindent(@desc)
    end

    # @return [Boolean] whether or not the function is templated
    def templated?
      !@targs.empty?
    end

    # @return [Integer] The number of arguments to the function
    def num_args
      @argument_nodes.size
    end

    # @return [Array<Array(Type,String)>] containing the argument types and names, in order
    def arguments(symtab)
      return @arglist unless @arglist.nil?

      if templated?
        template_names.each do |tname|
          internal_error "Template values missing in symtab" unless symtab.get(tname)
        end
      end

      return EMPTY_ARRAY if @argument_nodes.empty?

      arglist = []

      @argument_nodes.each do |a|
        atype = a.type(symtab)
        type_error "No type for #{a.text_value}" if atype.nil?

        atype = atype.ref_type if atype.kind == :enum

        arglist << [atype, a.name]
      end

      arglist.freeze
      unless templated?
        @arglist = arglist
      end
      arglist
    end

    # returns an array of arguments, as a string
    # function (or template instance) does not need to be resolved
    def arguments_list_str
      @argument_nodes.map(&:text_value)
    end

    # return the return type, which may be a tuple of multiple types
    def return_type(symtab)
      cached = @cached_return_type[symtab.name] # only chaced for non-template functions
      return cached unless cached.nil?

      unless symtab.levels == 2
        internal_error "Function bodies should be at global + 1 scope (at global + #{symtab.levels - 1})"
      end

      if @return_type_nodes.empty?
        @cached_return_type[symtab.name] = VoidType
        return VoidType
      end

      rtype = T.let(nil, T.nilable(Type))

      unless templated?
        # with no templates, the return type does not change
        rtype =
          if @return_type_nodes.size == 1
            rtype = @return_type_nodes[0].type(symtab)
            rtype = rtype.ref_type if rtype.kind == :enum
            rtype
          else
            tuple_types = @return_type_nodes.map do |r|
              rtype = r.type(symtab)
              rtype = rtype.ref_type if rtype.kind == :enum
              rtype
            end

            Type.new(:tuple, tuple_types:)
          end

        raise "??????" if rtype.nil?

        return @cached_return_type[symtab.name] = rtype
      end

      if templated?
        template_names.each do |tname|
          internal_error "Template values missing" unless symtab.get(tname)
        end
      end



      if @return_type_nodes.size == 1
        rtype = @return_type_nodes[0].type(symtab)
        rtype = rtype.ref_type if rtype.kind == :enum
        rtype
      else

        tuple_types = @return_type_nodes.map do |r|
          rtype = r.type(symtab)
          rtype = rtype.ref_type if rtype.kind == :enum
          rtype
        end

        Type.new(:tuple, tuple_types:)
      end
    end

    # @return [Array<String>] return type strings
    # function (or template instance) does not need to be resolved
    def return_type_list_str
      if @return_type_nodes.empty?
        ["void"]
      else
        @return_type_nodes.map(&:text_value)
      end
    end

    # if the arguments are all consts, will the return value be const/knowable?
    # if const_if_args_const? is true, then the return value of the function is gauranteed
    # to be known at compile time when all argument values are known at compile time
    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      return false if builtin? || generated?

      # set up the template args (if present) and dummy const args, and see if the type comes out
      # const
      symtab = symtab.global_clone
      symtab.push(self)

      template_names.each_with_index do |tname, index|
        symtab.add(tname, Var.new(tname, template_types(symtab)[index], template_index: index, function_name: name))
      end

      arguments(symtab).each do |arg_type, arg_name|
        # make the argument constant for this evaluation
        arg_type = arg_type.make_const
        symtab.add(arg_name, Var.new(arg_name, arg_type))
      end

      symtab.add(
        "__expected_return_type",
        return_type(symtab)
      )

      is_const_eval = @body.const_eval?(symtab)
      symtab.release

      is_const_eval
    end

    def name
      @name
    end

    # @param [Array<Integer>] template values to apply
    def type_check_template_instance(symtab)
      internal_error "Function definitions should be at global + 1 scope" unless symtab.levels == 2

      internal_error "Not a template function" unless templated?

      template_names.each do |tname|
        internal_error "Template values missing" unless symtab.get(tname)
      end

      type_check_return(symtab)
      type_check_args(symtab)
      @argument_nodes.each { |a| symtab.add(a.name, Var.new(a.name, a.type(symtab))) }
      type_check_body(symtab)
    end

    # we do lazy type checking of the function body so that we never check
    # uncalled functions, which avoids dealing with mentions of CSRs that
    # may not exist in a given implementation
    def type_check_from_call(symtab)
      internal_error "Function definitions should be at global + 1 scope" unless symtab.levels == 2

      type_check_return(symtab)
      type_check_args(symtab)
      # @argument_nodes.each do |a|
      #   value_result = value_try do
      #     symtab.add(a.name, Var.new(a.name, a.type(symtab), a.value(symtab)))
      #   end
      #   value_else(value_result) do
      #     symtab.add(a.name, Var.new(a.name, a.type(symtab)))
      #   end
      # end
      type_check_body(symtab)
    end

    def apply_template_and_arg_syms(symtab)
      template_names.each_with_index do |tname, index|
        symtab.add(tname, Var.new(tname, template_types(symtab)[index], template_index: index, function_name: name))
      end

      arguments(symtab).each do |arg_type, arg_name|
        symtab.add(arg_name, Var.new(arg_name, arg_type))
      end
    end

    # @!macro type_check
    def type_check(symtab)
      internal_error "Functions must be declared at global scope (at #{symtab.levels})" unless symtab.levels == 1

      type_check_targs(symtab)

      symtab = symtab.deep_clone
      symtab.push(self)
      template_names.each_with_index do |tname, index|
        symtab.add(tname, Var.new(tname, template_types(symtab)[index], template_index: index))
      end

      type_check_return(symtab)

      arguments(symtab).each do |arg_type, arg_name|
        symtab.add(arg_name, Var.new(arg_name, arg_type))
      end
      type_check_args(symtab)


      # template functions are checked as they are called
      unless templated?
        type_check_body(symtab)
      end
      symtab.pop
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      internal_error "Functions should be declared at global scope" unless symtab.levels == 1

      # now add the function in global scope
      def_type = FunctionType.new(
        name,
        self,
        symtab
      )

      symtab.add!(name, def_type)
    end

    # @return [Array<String>] Template argument names, in order
    def template_names
      @targs.map(&:name)
    end

    # @param symtab [SymbolTable] The context for evaluation
    # @return [Array<Type>] Template argument types, in order
    def template_types(symtab)
      return EMPTY_ARRAY unless templated?

      ttypes = T.let([], T::Array[Type])
      @targs.each do |a|
        ttype = a.type(symtab)
        ttype = ttype.ref_type if ttype.kind == :enum
        ttypes << ttype.make_const
        T.must(ttypes.last).qualify(:template_var)
      end
      ttypes
    end

    def type_check_targs(symtab)
      @targs.each { |t| type_error "Template arguments must be uppercase" unless t.text_value[0] == t.text_value[0].upcase }
      @targs.each { |t| type_error "Template types must be integral" unless t.type(symtab).integral? }
    end

    def type_check_return(symtab)
      @return_type_nodes.each { |r| r.type_check(symtab) }
    end

    def type_check_args(symtab)
      @argument_nodes.each { |a| a.type_check(symtab, false) }
    end

    def type_check_body(symtab)
      return if @body.nil?

      @body.type_check(symtab)
    end

    def body
      internal_error "Function has no body" if builtin? || generated?

      @body
    end

    def builtin?
      @builtin
    end

    def generated?
      @generated
    end

    def external?
      @external
    end

    sig { override.returns(String) }
    def to_idl
      qualifier =
        if external?
          "external"
        elsif builtin?
          "builtin"
        elsif generated?
          "generated"
        else
          ""
        end

      targs_idl =
        if templated?
          "template #{@targs.map(&:to_idl).join(', ')}"
        else
          ""
        end

      returns_idl =
        if return_type_nodes.empty?
          ""
        else
          "returns #{return_type_nodes.map(&:to_idl).join(', ')}"
        end

      args_idl =
        if @argument_nodes.empty?
          ""
        else
          "arguments #{@argument_nodes.map(&:to_idl).join(", ")}"
        end

      body_idl =
        if builtin? || generated?
          ""
        else
          "body { #{@body.to_idl} }"
        end

      <<~IDL
        #{qualifier} function #{name} {
          #{targs_idl}
          #{returns_idl}
          #{args_idl}
          description { #{description} }
          #{body_idl}
        }
      IDL
    end
  end

  class ForLoopSyntaxNode < SyntaxNode
    def to_ast
      ForLoopAst.new(
        input, interval,
        send(:for_loop_iteration_variable_declaration).to_ast,
        send(:condition).to_ast,
        send(:action).to_ast,
        send(:stmts).elements.map(&:s).map(&:to_ast)
      )
    end
  end

  class ForLoopAst < AstNode
    include Executable
    include Returns # a return statement in a for loop can make it return a value

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      init.const_eval?(symtab) && \
        condition.const_eval?(symtab) && \
        update.const_eval?(symtab) && \
        stmts.all? { |stmt| stmt.const_eval?(symtab) }
    end

    sig { returns(VariableDeclarationWithInitializationAst) }
    def init = T.cast(@children.fetch(0), VariableDeclarationWithInitializationAst)

    sig { returns(RvalueAst) }
    def condition = T.cast(@children.fetch(1), RvalueAst)

    sig { returns(ExecutableAst) }
    def update = T.cast(@children.fetch(2), ExecutableAst)

    sig { returns(T::Array[T.any(StatementAst, ReturnStatementAst, IfAst, ForLoopAst)]) }
    def stmts = T.cast(@children[3..], T::Array[T.any(StatementAst, ReturnStatementAst, IfAst, ForLoopAst)])

    def initialize(input, interval, init, condition, update, stmts)
      super(input, interval, [init, condition, update] + stmts)
    end

    # @!macro type_check
    def type_check(symtab)
      symtab.push(self)
      init.type_check(symtab)
      condition.type_check(symtab)
      update.type_check(symtab)

      stmts.each { |stmt| stmt.type_check(symtab) }

      symtab.pop
    end

    # @!macro return_value
    def return_value(symtab)
      symtab.push(self)

      begin
        value_result = value_try do
          init.execute(symtab)

          while condition.value(symtab)
            stmts.each do |s|
              if s.is_a?(Returns)
                v = s.return_value(symtab)
                unless v.nil?
                  return v
                end
              else
                s.execute(symtab)
              end
            end
            update.execute(symtab)
          end
        end
        value_else(value_result) do
          value_error ""
        end
      ensure
        symtab.pop
      end
      nil
    end

    sig { override.params(symtab: SymbolTable).returns(Type) }
    def return_type(symtab)
      # the return type is determined by the function
      expected_return_type(symtab)
    end

    # @!macro return_values
    def return_values(symtab)
      value_result = value_try do
        # if there is a known return value, then we are done
        return [return_value(symtab)]
      end
      value_else(value_result) do
        # see if we can collect a list
        values = T.let([], T::Array[ValueRbType])
        symtab.push(self)

        begin
          value_result = value_try do
            init.execute(symtab)

            while condition.value(symtab)
              stmts.each do |s|
                if s.is_a?(Returns)
                  value_result = value_try do
                    v = s.return_value(symtab)
                    unless v.nil?
                      return values.push(v).uniq
                    end
                  end
                  value_else(value_result) do
                    values += s.return_values(symtab)
                  end
                else
                  s.execute(symtab)
                end
              end
              update.execute(symtab)
            end
            :ok
          end
        ensure
          symtab.pop
        end

        values.uniq
      end
    end

    # @!macro execute
    alias execute return_value

    sig { override.params(symtab: SymbolTable).void }
    def execute_unknown(symtab)
      symtab.push(self)

      begin
        value_result = value_try do
          init.execute_unknown(symtab)

          stmts.each do |s|
            unless s.is_a?(ReturnStatementAst)
              s.execute_unknown(symtab)
            end
          end
          update.execute_unknown(symtab)
        end
      ensure
        symtab.pop
      end
      nil
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      idl = "for (#{init.to_idl}; #{condition.to_idl}; #{update.to_idl}) {"
      stmts.each do |s|
        idl << s.to_idl
      end
      idl << "}"
      idl
    end
  end

  class IfBodyAst < AstNode
    include Executable
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      stmts.all? { |stmt| stmt.const_eval?(symtab) }
    end

    def stmts = @children

    def initialize(input, interval, body_stmts)
      if body_stmts.empty?
        super("", 0...0, EMPTY_ARRAY)
      else
        super(input, interval, body_stmts)
      end
    end

    # @!macro type_check
    def type_check(symtab)
      symtab.push(self)

      begin
        stmts.each do |s|
          s.type_check(symtab)
        end
      ensure
        symtab.pop
      end
    end

    sig { override.params(symtab: SymbolTable).returns(Type) }
    def return_type(symtab)
      # the return type is determined by the function
      t = expected_return_type(symtab)
    end

    # @!macro return_value
    def return_value(symtab)
      symtab.push(self)
      begin
        stmts.each do |s|
          if s.is_a?(Returns)
            v = s.return_value(symtab)
            unless v.nil?
              return v
            end
          else
            s.execute(symtab)
          end
        end
      ensure
        symtab.pop
      end

      nil
    end

    # @!macro return_values
    def return_values(symtab)
      values = T.let([], T::Array[ValueRbType])
      symtab.push(self)
      begin
        value_try do
          stmts.each do |s|
            if s.is_a?(Returns)
              value_result = value_try do
                v = s.return_value(symtab)

                return values.push(v).uniq unless v.nil?
              end
              value_else(value_result) do
                values += s.return_values(symtab)
              end
            else
              s.execute(symtab)
            end
          end
        end
      ensure
        symtab.pop
      end

      values.uniq
    end

    # @!macro execute
    def execute(symtab)
      err = T.let(nil, T.nilable(Symbol))
      stmts.each do |s|
        value_result = value_try do
          if s.is_a?(Returns)
            value_result2 = value_try do
              v = s.return_value(symtab)
              break unless v.nil? # nil means this is a conditional return and the condition is false
            end
            value_else(value_result2) do
              # not known, keep going
              err = :value_error
            end
          else
            s.execute(symtab)
          end
        end
        value_else(value_result) do
          # keep going so that we invalidate everything
          err = :value_error
        end
      end
      throw err unless err.nil?
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      stmts.each do |s|
        s.execute_unknown(symtab)
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      stmts.map(&:to_idl).join("")
    end

  end

  class ElseIfAst < AstNode
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      cond.const_eval?(symtab) && body.const_eval?(symtab)
    end

    sig { returns(RvalueAst) }
    def cond = T.cast(@children.fetch(0), RvalueAst)

    sig { returns(IfBodyAst) }
    def body = T.cast(@children.fetch(1), IfBodyAst)

    def initialize(input, interval, body_interval, cond, body_stmts)
      body = IfBodyAst.new(input, body_interval, body_stmts)
      super(input, interval, [cond, body])
    end

    def type_check(symtab)
      cond.type_check(symtab)

      cond_value = T.let(nil, T.nilable(ValueRbType))
      value_try do
        cond_value = cond.value(symtab)
      end

      unless cond.type(symtab).convertable_to?(:boolean)
        type_error "'#{cond.text_value}' is not boolean"
      end

      body.type_check(symtab) unless cond_value == false
    end

    sig { override.params(symtab: SymbolTable).returns(Type) }
    def return_type(symtab)
      # the return type is determined by the function
      t = expected_return_type(symtab)
    end

    def return_value(symtab)
      value_result = value_try do
        if cond.value(symtab)
          body.return_value(symtab)
        else
          nil
        end
      end
    end

    # @!macro return_values
    def return_values(symtab)
      value_result = value_try do
        return cond.value(symtab) ? body.return_values(symtab) : EMPTY_ARRAY
      end
      value_else(value_result) do
        # might be taken, so add the possible return values
        body.return_values(symtab)
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      " else if (#{cond.to_idl}) { #{body.to_idl} }"
    end
  end

  class IfSyntaxNode < SyntaxNode
    def to_ast
      if_body_stmts = T.let([], T::Array[AstNode])
      send(:if_body).elements.each do |e|
        if_body_stmts << e.e.to_ast
      end
      eifs = T.let([], T::Array[ElseIfAst])
      unless send(:elseifs).empty?
        send(:elseifs).elements.each do |eif|
          stmts = []
          eif.body.elements.each do |e|
            stmts << e.e.to_ast
          end
          eifs << ElseIfAst.new(input, eif.interval, eif.body.interval, eif.expression.to_ast, stmts)
        end
      end
      final_else_stmts = T.let([], T::Array[AstNode])
      unless send(:final_else).empty?
        send(:final_else).body.elements.each do |e|
          final_else_stmts << e.e.to_ast
        end
      end
      if_body_ast = IfBodyAst.new(input, send(:if_body).interval, if_body_stmts)
      final_else_ast =
        if send(:final_else).empty?
          IfBodyAst.new(input, 0..0, final_else_stmts)
        else
          IfBodyAst.new(input, send(:final_else).body.interval, final_else_stmts)
        end
      ast = IfAst.new(input, interval, send(:if_cond).to_ast, if_body_ast, eifs, final_else_ast)
      ast
    end
  end

  class IfAst < AstNode
    include Executable
    include Returns

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      if_cond.const_eval?(symtab) && \
        if_body.const_eval?(symtab) && \
        elseifs.all? { |eif| eif.const_eval?(symtab) } && \
        final_else_body.const_eval?(symtab)
    end

    sig { returns(RvalueAst) }
    def if_cond = T.cast(@children.fetch(0), RvalueAst)

    sig { returns(IfBodyAst) }
    def if_body = T.cast(@children.fetch(1), IfBodyAst)

    sig { returns(T::Array[ElseIfAst]) }
    def elseifs = T.cast(T.must(@children[2..-2]), T::Array[ElseIfAst])

    sig { returns(IfBodyAst) }
    def final_else_body = T.cast(T.must(@children.last), IfBodyAst)

    def initialize(input, interval, if_cond, if_body, elseifs, final_else_body)
      children_nodes = [if_cond, if_body]
      children_nodes += elseifs
      children_nodes << final_else_body

      @func_type_cache = {}

      super(input, interval, children_nodes)
    end

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels
      if_cond.type_check(symtab)


      unless if_cond.type(symtab).convertable_to?(:boolean)
        if if_cond.type(symtab).kind == :bits
          type_error "'#{if_cond.text_value}' is not boolean. Maybe you meant 'if ((#{if_cond.text_value}) != 0)'?"
        else
          type_error "'#{if_cond.text_value}' is not boolean"
        end
      end

      if_cond_value = T.let(nil, T.nilable(ValueRbType))
      value_try do
        if_cond_value = if_cond.value(symtab)
      end

      # short-circuit the if body if we can
      if_body.type_check(symtab) unless if_cond_value == false

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      unless (if_cond_value == true) || elseifs.empty?
        elseifs.each do |eif|
          eif.type_check(symtab)
        end
      end

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      final_else_body.type_check(symtab) unless if_cond_value == true

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels
    end

    # @return [Boolean] true if the taken path is knowable at compile-time
    # @raise ValueError if the take path is not known at compile time
    def taken_body(symtab)
      return if_body if if_cond.value(symtab)

      unless elseifs.empty?
        elseifs.each do |eif|
          return eif.body if eif.cond.value(symtab)
        end
      end

      final_else_body.stmts.empty? ? nil : final_else_body
    end

    sig { override.params(symtab: SymbolTable).returns(Type) }
    def return_type(symtab)
      begin
        rt = if_body.return_type(symtab)
        rt = elseifs.map { |eif| eif.return_type(symtab) }.compact[0] if rt.nil?
        rt ||= final_else_body.return_type(symtab)
      end
    end

    # @!macro return_value
    def return_value(symtab)

      body = taken_body(symtab)
      return nil if body.nil?

      body.return_value(symtab)
    end

    # return values starting at the first else if
    def return_values_after_if(symtab)
      values = T.let([], T::Array[ValueRbType])

      unless elseifs.empty?
        elseifs.each do |eif|
          values += eif.return_values(symtab)
          value_result = value_try do
            elseif_cond_value = eif.cond.value(symtab)
            if elseif_cond_value
              # this else if is defintately taken, so we are done
              return (values + eif.return_values(symtab)).uniq
            else
              next :ok # we know the else if isn't taken, so we can just go to the next
            end
          end
          value_else(value_result) do
            # else if path not known; body return paths are possible
            values += eif.return_values(symtab)
          end
        end
      end

      # now add the returns from the final else
      (values + final_else_body.return_values(symtab)).uniq
    end
    private :return_values_after_if

    # Returns a list of all possible return values, if known. Otherwise, raises a ValueError
    #
    # @param symtab [SymbolTable] Context for the evaluation
    # @return [Array<Integer,Bool>] List of all possible return values
    # @raise ValueError if it is not possible to determine all return values at compile time
    def return_values(symtab)
      value_result = value_try do
        if_cond_value = if_cond.value(symtab)
        if if_cond_value
          # if is taken, so the only possible return values are those in the if body
          return if_body.return_values(symtab)
        else
          # if cond not taken; check else ifs and possibly final else
          return return_values_after_if(symtab)
        end
      end
      value_else(value_result) do
        # if condition not known; both paths are possible
        (if_body.return_values(symtab) + return_values_after_if(symtab)).uniq
      end
    end

    # return values starting at the first else if
    def execute_after_if(symtab)
      err = T.let(nil, T.nilable(Symbol))
      unless elseifs.empty?
        elseifs.each do |eif|
          value_result = value_try do
            elseif_cond_value = eif.cond.value(symtab)
            if elseif_cond_value
              # this else if is defintately taken, so we are done
              eif.body.execute(symtab)
              return
            else
              next :ok # we know the else if isn't taken, so we can just go to the next
            end
          end
          value_else(value_result) do
            # else if path not known; body return paths are possible
            value_result = value_try do
              eif.body.execute(symtab)
            end
            value_else(value_result) do
              err = :value_error if err.nil?
            end
          end
        end
      end

      # now do the final else
      value_result = value_try do
        final_else_body.execute(symtab) unless final_else_body.nil?
      end
      value_else(value_result) do
        err = :value_error if err.nil?
      end

      value_error "" unless err.nil?
    end
    private :execute_after_if

    # @!macro execute
    def execute(symtab)
      err = T.let(nil, T.nilable(Symbol))
      value_result = value_try do
        if_cond_value = if_cond.value(symtab)
        if if_cond_value
          # if is taken, so only the taken body is executable
          value_result2 = value_try do
            if_body.execute(symtab)
          end
          value_else(value_result2) do
            err = :value_error if err.nil?
          end
        else
          execute_after_if(symtab)
        end
      end
      value_else(value_result) do
        # condition not known; both paths can execute
        value_result2 = value_try do
          if_body.execute(symtab)
        end
        value_else(value_result2) do
          err = :value_error if err.nil?
        end

        value_result2 = value_try do
          execute_after_if(symtab)
        end
        value_else(value_result2) do
          err = :value_error if err.nil?
        end
      end

      value_error "" unless err.nil?
    end

    # return values starting at the first else if
    def execute_unknown_after_if(symtab)
      elseifs.each do |eif|
        eif.body.execute_unknown(symtab)
      end
      final_else_body.execute_unknown(symtab) unless final_else_body.nil?
    end
    private :execute_unknown_after_if

    # @!macro execute_unknown
    def execute_unknown(symtab)
      if_body.execute_unknown(symtab)
      execute_unknown_after_if(symtab)
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      result = "if (#{if_cond.to_idl}) { "
      result << if_body.to_idl
      result << "} "
      elseifs.each do |eif|
        result << eif.to_idl
      end
      unless final_else_body.stmts.empty?
        result << " else { "
        result << final_else_body.to_idl
        result << "} "
      end
      result
    end
  end

  class CsrFieldReadExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = !@value.nil?

    def initialize(input, interval, csr, field_name)
      super(input, interval, [csr])

      @csr = csr
      @field_name = field_name
    end

    def freeze_tree(symtab)
      return if frozen?

      @children.each { |child| child.freeze_tree(symtab) }

      @csr_obj = @csr.csr_def(symtab)
      type_error "No CSR '#{@csr.text_value}'" if @csr_obj.nil?

      value_result = value_try do
        @value = calc_value(symtab)
      end
      value_else(value_result) do
        @value = nil
      end

      @type = calc_type(symtab)

      freeze
    end

    # @!macro type_check
    def type_check(symtab)
      @csr.type_check(symtab)

      type_error "CSR[#{csr_name}] has no field named #{@field_name}" if field_def(symtab).nil?
      type_error "CSR[#{csr_name}].#{@field_name} is not defined in RV32" if symtab.mxlen == 32 && !field_def(symtab).defined_in_base32?
      type_error "CSR[#{csr_name}].#{@field_name} is not defined in RV64" if symtab.mxlen == 64 && !field_def(symtab).defined_in_base64?
    end

    def csr_def(symtab)
      @csr_obj
    end

    def csr_name = @csr.csr_name

    def field_def(symtab)
      @csr_obj.fields.find { |f| f.name == @field_name }
    end

    def field_name(symtab)
      field_def(symtab)&.name
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      "CSR[#{csr_name}].#{@field_name}"
    end

    # @!macro type
    def type(symtab)
      @type
    end

    def calc_type(symtab)
      fd = field_def(symtab)
      internal_error "Could not find #{@csr.text_value}.#{@field_name}" if fd.nil?

      if fd.defined_in_all_bases?
        Type.new(:bits, width: symtab.possible_xlens.map { |xlen| fd.width(xlen) }.max)
      elsif fd.base64_only?
        if symtab.possible_xlens.include?(64)
          Type.new(:bits, width: fd.width(64))
        end
      elsif fd.base32_only?
        if symtab.possible_xlens.include?(32)
          Type.new(:bits, width: fd.width(32))
        end
      else
        internal_error "unexpected field base"
      end
    end

    # @!macro value
    def value(symtab)
      if @value.nil?
        value_error "'#{csr_name}.#{field_name(symtab)}' is not RO"
      else
        @value
      end
    end

    def calc_value(symtab)
      # field isn't implemented, so it must be zero
      return 0 if field_def(symtab).nil? || !field_def(symtab).exists?

      symtab.possible_xlens.each do |effective_xlen|
        unless field_def(symtab).type(effective_xlen) == "RO"
          value_error "'#{csr_name}.#{field_name(symtab)}' is not RO"
        end
      end

      v = field_def(symtab).reset_value
      v = nil if v == "UNDEFINED_LEGAL"
    end
  end

  class CsrReadExpressionSyntaxNode < SyntaxNode
    def to_ast
      CsrReadExpressionAst.new(input, interval, send(:csr_name).text_value)
    end
  end

  class CsrFieldReadExpressionSyntaxNode < SyntaxNode
    def to_ast
      CsrFieldReadExpressionAst.new(input, interval, send(:csr).to_ast, send(:csr_field_name).text_value)
    end
  end

  class CsrReadExpressionAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = !@csr_obj.value.nil?

    attr_reader :csr_name

    def initialize(input, interval, csr_name)
      super(input, interval, [])

      @csr_name = csr_name
    end

    def freeze_tree(symtab)
      return if frozen?

      type_error "CSR '#{@csr_name}' is not defined" unless symtab.csr?(@csr_name)
      @csr_obj = symtab.csr(@csr_name)

      @type = CsrType.new(@csr_obj).freeze

      @children.each { |child| child.freeze_tree(symtab) }
      freeze
    end

    # @!macro type
    def type(symtab) = @type

    # @!macro type_check
    def type_check(symtab)
      type_error "CSR '#{@csr_name}' is not defined" unless symtab.csr?(@csr_name)
    end

    def csr_def(symtab)
      @csr_obj
    end

    def csr_known?(symtab)
      !csr_def(symtab).nil?
    end

    # @!macro value
    def value(symtab)
      v = @csr_obj.value
      if v.nil?
        value_error "CSR is not defined"
      end
      v
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "CSR[#{@csr_name}]"
  end

  class CsrSoftwareWriteSyntaxNode < SyntaxNode
    def to_ast
      CsrSoftwareWriteAst.new(input, interval, send(:csr).to_ast, send(:expression).to_ast)
    end
  end

  class CsrSoftwareWriteAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    def csr = @children[0]
    def expression = @children[1]

    def initialize(input, interval, csr, expression)
      super(input, interval, [csr, expression])
    end

    def type_check(symtab)
      csr.type_check(symtab)
      expression.type_check(symtab)

      e_type = expression.type(symtab)
      return if e_type.kind == :bits && ((e_type.width == :unknown || symtab.mxlen.nil?) || (e_type.width == symtab.mxlen))

      type_error "CSR value must be an XReg"
    end

    def csr_known?(symtab)
      csr.csr_known?(symtab)
    end

    def csr_name = csr.csr_name

    # @!macro value
    def value(_symtab)
      value_error "CSR writes are global"
    end

    # @!macro execute
    def execute(_symtab) = value_error "CSR writes are global"

    # @!macro execute_unknown
    def execute_unknown(_symtab); end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "#{csr.to_idl}.sw_write(#{expression.to_idl})"
  end

  # @api private
  class CsrFunctionCallSyntaxNode < SyntaxNode
    def to_ast
      args = []
      args << send(:function_arg_list).first.to_ast unless send(:function_arg_list).first.empty?
      args += send(:function_arg_list).rest.elements.map { |e| e.expression.to_ast }

      CsrFunctionCallAst.new(input, interval, send(:function_name).text_value, send(:csr).to_ast, args)
    end
  end

  # represents a function call for a CSR register
  # for example:
  #
  #   CSR[mstatus].address()
  #   CSR[mtval].sw_read()
  class CsrFunctionCallAst < AstNode
    include Rvalue

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab)
      if csr.csr_known?(symtab) && function_name == "address"
        true
      else
        false
      end
    end

    # @return [String] The function being called
    attr_reader :function_name

    def csr = @children[0]
    def args = @children[1..]

    def initialize(input, interval, function_name, csr, args)
      super(input, interval, [csr] + args)
      @function_name = function_name
    end

    def type_check(symtab)
      csr.type_check(symtab)

      if ["sw_read", "address"].include?(function_name)
        type_error "unexpected argument(s)" unless args.empty?
      elsif ["implemented_without?"].include?(function_name)
        type_error "Expecting one argument" unless args.size == 1
        type_error "Expecting an ExtensionName" unless args[0].type(symtab).kind == :enum_ref && args[0].class_name == "ExtensionName"
      else
        type_error "'#{function_name}' is not a supported CSR function call"
      end
    end

    def type(symtab)

      case function_name
      when "sw_read"
        if csr_known?(symtab)
          l = symtab.csr(csr.csr_name).length
          Type.new(:bits, width: (l.nil? ? :unknown : l))
        else
          Type.new(:bits, width: symtab.mxlen.nil? ? :unknown : symtab.mxlen)
        end
      when "address"
        Type.new(:bits, width: 12, qualifiers: [:const, :known])
      when "implemented_without?"
        ConstBoolType
      else
        internal_error "No function '#{function_name}' for CSR. call type check first!"
      end
    end

    def csr_known?(symtab)
      csr.csr_known?(symtab)
    end

    def csr_name = csr.csr_name

    def csr_def(symtab)
      csr.csr_def(symtab)
    end

    # @todo check the sw_read function body
    def value(symtab)
      case function_name
      when "sw_read"
        value_error "CSR not knowable" unless csr_known?(symtab)
        cd = csr_def(symtab)
        cd.fields.each { |f| value_error "#{csr_name}.#{f.name} not RO" unless f.type == "RO" }

        value_error "TODO: CSRs with sw_read function"
      when "address"
        value_error "CSR not knowable" unless csr_known?(symtab)
        cd = csr_def(symtab)
        cd.address
      when "implemented_without?"
        value_error "CSR not knowable" unless csr_known?(symtab)
        cd = csr_def(symtab)
        extension_name_enum_type = symtab.get("ExtensionName")
        enum_value = args[0].value(symtab)
        idx = extension_name_enum_type.element_values.index(enum_value)
        ext_name = extension_name_enum_type.element_names[idx]

        cd.implemented_without?(ext_name)
      else
        internal_error "TODO: #{function_name}"
      end
    end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl
      "#{csr_name}.#{function_name}(#{args.map(&:to_idl).join(', ')})"
    end
  end

  class CsrWriteSyntaxNode < SyntaxNode
    def to_ast = CsrWriteAst.new(input, interval, send(:idx).to_ast)
  end

  class CsrWriteAst < AstNode
    include Executable

    sig { override.params(symtab: SymbolTable).returns(T::Boolean) }
    def const_eval?(symtab) = false

    def idx = @children[0]

    def initialize(input, interval, idx)
      super(input, interval, [idx])
    end

    # @!macro type_check
    def type_check(symtab)
      if idx.is_a?(IntLiteralAst)
        # make sure this value is a defined CSR
        index = symtab.csrs.index { |csr| csr.address == idx.value(symtab) }
        type_error "No csr number '#{idx.value(symtab)}' was found" if index.nil?
      else
        csr = symtab.csr(idx.text_value)
        type_error "No csr named '#{idx.text_value}' was found" if csr.nil?
      end
    end

    def csr_def(symtab)
      if idx.is_a?(IntLiteralAst)
        # make sure this value is a defined CSR
        symtab.csrs.find { |csr| csr.address == idx.value(symtab) }
      else
        symtab.csr(idx.text_value)
      end
    end

    # @!macro type
    def type(symtab)
      CsrType.new(csr_def(symtab))
    end

    def name(symtab)
      csr_def(symtab).name
    end

    # @!macro execute
    def execute(symtab)
      value_error "CSR write"
    end

    # @!macro execute_unknown
    def execute_unknown(symtab); end

    # @!macro to_idl
    sig { override.returns(String) }
    def to_idl = "CSR[#{idx.text_value}]"
  end
end
