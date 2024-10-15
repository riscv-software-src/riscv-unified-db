# frozen_string_literal: true

require 'benchmark'

require_relative "type"
require_relative "symbol_table"

module Treetop
  module Runtime
    class SyntaxNode
      # Sets the input file for this syntax node unless it has already been set.
      #
      # If the input file has not been set, it will be set with the given filename and starting line number.
      #
      # @param [String] filename The name of the input file.
      # @param [Integer] starting_line The starting line number in the input file.
      def set_input_file_unless_already_set(filename, starting_line = 0)
        if @input_file.nil?
          set_input(filename, starting_line)
        end
      end

      # remember where the code comes from
      #
      # @param filename [String] Filename
      # @param starting_line [Integer] Starting line in the file
      def set_input_file(filename, starting_line = 0)
        @input_file = filename
        @starting_line = starting_line
        elements&.each do |child|
          child.set_input_file(filename, starting_line)
        end
        raise "?" if @starting_line.nil?
      end

      def space? = false
    end
  end
end

module Idl
  EMPTY_ARRAY = [].freeze

  # base class for all nodes considered part of the Ast
  # @abstract
  class AstNode
    Bits1Type = Type.new(:bits, width: 1).freeze
    Bits32Type = Type.new(:bits, width: 32).freeze
    Bits64Type = Type.new(:bits, width: 64).freeze
    ConstBoolType = Type.new(:boolean, qualifiers: [:const]).freeze
    BoolType = Type.new(:boolean).freeze
    VoidType = Type.new(:void).freeze
    StringType = Type.new(:string).freeze

    # @return [String] Source input file
    attr_reader :input_file

    # @return [Integer] Starting line in the source input file (i.e., position 0 of {#input} in the file)
    attr_reader :starting_line

    # @return [String] Source string
    attr_reader :input

    # @retrun [Range] Range within the input for this node
    attr_reader :interval

    # @return [String] The IDL source of this node
    attr_reader :text_value

    # @retrun [AstNode] The parent node
    # @retrun [nil] if this is the root of the tree
    attr_reader :parent

    # @return [Array<AstNode>] Children of this node
    attr_reader :children

    # error that is thrown when compilation reveals a type error
    class TypeError < StandardError
      # @return [String] The error message
      attr_reader :what

      # The backtrace starting from the 'type_error' call site
      #
      # Note, this will be different (truncated) from #backtrace
      #
      # @return [Array<String>] The compiler backtrace at the error point
      attr_reader :bt

      # @param what [String] Error message
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
      # @return [String] The error message
      attr_reader :what

      # The backtrace starting from the 'internal_error' call site
      #
      # Note, this will be different (truncated) from #backtrace
      #
      # @return [Array<String>] The compiler backtrace at the error point
      attr_reader :bt

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
      attr_reader :lineno, :file, :reason

      def initialize(lineno, file, reason)
        super(reason)
        @lineno = lineno
        @file = file
        @reason = reason
      end

      def what = message

      def message
        <<~WHAT
          In file #{file}
          On line #{lineno}
            A value error occured
            #{reason}
        WHAT
      end
    end

    def self.value_try(&block)
      catch(:value_error) do
        yield block
      end
    end
    def value_try(&block) = return self.class.value_try(&block)

    def self.value_else(value_result, &block)
      return unless value_result == :unknown_value

      yield block
    end
    def value_else(value_result, &block) = self.class.value_else(value_result, &block)

    # @param input [String] The source being compiled
    # @param interval [Range] The range in the source corresponding to this AstNode
    # @param children [Array<AstNode>] Children of this node
    def initialize(input, interval, children)
      @input = input
      @input_file = nil
      @starting_line = 0
      @interval = interval
      @text_value = input[interval]
      children.each { |child| raise ArgumentError, "Children of #{self.class.name} must be AstNodes (found a #{child.class.name})" unless child.is_a?(AstNode)}
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
    def set_input_file_unless_already_set(filename, starting_line = 0)
      return unless @input_file.nil?

      @input_file = filename
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
    def set_input_file(filename, starting_line = 0)
      @input_file = filename
      @starting_line = starting_line
      children.each do |child|
        child.set_input_file(filename, starting_line)
      end
      raise "?" if @starting_line.nil?
    end

    # @return [Integer] the current line number
    def lineno
      input[0..interval.first].count("\n") + 1 + (@starting_line.nil? ? 0 : @starting_line)
    end

    # @return [AstNode] the first ancestor that is_a?(+klass+)
    # @return [nil] if no ancestor is found
    def find_ancestor(klass)
      if parent.nil?
        nil
      elsif parent.is_a?(klass)
        parent
      else
        parent.find_ancestor(klass)
      end
    end

    # @return [String] returns +-2 lines around the current interval
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

        interval_end += 1
      end

      [
        input[interval_start..interval_end],
        (interval.min - interval_start..interval.max - interval_start),
        (interval_start + 1)..interval_end
      ]
    end

    # raise a type error
    #
    # @param reason [String] Error message
    # @raise [AstNode::TypeError] always
    def type_error(reason)
      lines, problem_interval, lines_interval = lines_around

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

      starting_lineno = input[0..lines_interval.min].count("\n")
      lines = lines.lines.map do |line|
        starting_lineno += 1
        "#{@starting_line + starting_lineno - 1}: #{line}"
      end.join("")

      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
        In the code:

          #{lines.gsub("\n", "\n  ")}

        A type error occured
          #{$stdout.isatty ? "\u001b[31m#{reason}\u001b[0m" : reason}
      WHAT
      raise AstNode::TypeError, msg
    end

    # raise an internal error
    #
    # @param reason [String] Error message
    # @raise [AstNode::TypeError] always
    def internal_error(reason)
      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
          An internal error occured
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
    def self.value_error(reason, ast = nil)
      AstNode.value_error_reason = reason
      AstNode.value_error_ast = ast
      # warn reason
      # warn "At #{ast.input_file}:#{ast.lineno}" unless ast.nil?
      throw(:value_error, :unknown_value)
      #raise AstNode::ValueError.new(lineno, input_file, reason), reason, []
    end
    def value_error(reason) = self.class.value_error(reason, self)

    # unindent a multiline string, getting rid of all common leading whitespace (like <<~ heredocs)
    #
    # borrowed from https://stackoverflow.com/questions/33527064/multiline-strings-with-no-indent
    #
    # @param s [String] A string (presumably with newlines)
    # @return [String] Unindented string
    def unindent(s)
      s.gsub(/^#{s.scan(/^[ \t]+(?=\S)/).min}/, "")
    end

    # pretty print the AST rooted at this node
    #
    # @param indent [Integer] The starting indentation, in # of spaces
    # @param indent_size [Integer] The extra indentation applied to each level of the tree
    # @param io [IO] Where to write the output
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
    def freeze_tree(global_symtab)
      @children.each { |child| child.freeze_tree(global_symtab) }
      freeze
    end

    # @return [String] A string representing the path to this node in the tree
    def path
      if parent.nil?
        self.class.name
      else
        "#{parent.path}.#{self.class.name}"
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
    def type_check(symtab) = raise NotImplementedError, "#{self.class.name} must implement type_check"

    # @!macro [new] to_idl
    #   Return valid IDL representation of the node (and its subtree)
    #
    #   @return [String] IDL code for the node

    # @!macro to_idl
    # @abstract
    def to_idl = raise NotImplementedError, "#{self.class.name} must implement to_idl"

    def inspect = self.class.name.to_s
  end

  # interface for nodes that can be executed, but don't have a value (e.g., statements)
  module Executable
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
    def execute(symtab) = raise NotImplementedError, "#{self.class.name} must implement execute"

    # @!macro execute_unknown
    def execute_unknown(symtab) = raise NotImplementedError, "#{self.class.name} must implement execute_unknown"
  end

  # interface for nodes that *might* return a value in a function body
  module Returns
    # @!macro [new] retrun_value
    #   Evaluate the compile-time return value of this node, or, if the node does not return
    #   (e.g., because it is an IfAst but there is no return on the taken path), execute the node
    #   and update the symtab
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if, during evaulation, a node without a compile-time value is found
    #   @return [Integer] The return value, if it is integral
    #   @return [Boolean] The return value, if it is boolean
    #   @return [nil]     if the return value is not compile-time-known

    # @!macro return_value
    def return_value(symtab) = raise NotImplementedError, "#{self.class.name} must implement return_value"

    # @!macro [new] retrun_values
    #   Evaluate all possible compile-time return values of this node, or, if the node does not return
    #   (e.g., because it is an IfAst but there is no return on a possible path), execute the node
    #   and update the symtab
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if, during evaulation, a node without a compile-time value is found
    #   @return [Array<Integer>] The possible return values. Will be an empty array if there are no return values
    #   @return [Array<Boolean>] The possible return values. Will be an empty array if there are no return values

    # @!macro return_values
    def return_values(symtab) = raise NotImplementedError, "#{self.class.name} must implement return_values"
  end

  # interface for R-values (e.g., expressions that have a value)
  module Rvalue
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
    def type(symtab) = raise NotImplementedError, "#{self.class.name} has no type"

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
    def value(symtab) = raise NotImplementedError, "#{self.class.name} must implement value(symtab)"

    # @!macro [new] values
    #  Return a complete list of possible compile-time-known values of the node, or raise a ValueError if
    #  the full list cannot be determined
    #
    #  For most AstNodes, this will just be a single-entry array
    #
    #  @param symtab [SymbolTable] The context for the evaulation
    #  @return [Array<Integer>] The complete list of compile-time-known values, when they are integral
    #  @return [Array<Boolean>] The complete list of compile-time-known values, when they are booleans
    #  @return [AstNode::ValueError] if the list of values is not knowable at compile time

    # @!macro values
    def values(symtab) = [value(symtab)]
  end

  # interface for any AstNode that introduces a new symbol into scope
  module Declaration
    # @!macro [new] add_symbol
    #  Add symbol(s) at the outermost scope of the symbol table
    #
    #  @param symtab [SymbolTable] Symbol table at the scope that the symbol(s) will be inserted
    def add_symbol(symtab) = raise NotImplementedError, "#{self.class.name} must implment add_symbol"
  end

  class IncludeStatementSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast = IncludeStatementAst.new(input, interval, string.to_ast)
  end

  class IncludeStatementAst < AstNode
    # @return [String] filename to include
    def filename = @children[0].text_value[1..-2]

    def initialize(input, interval, filename)
      super(input, interval, [filename])
    end
  end

  class IdSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast = IdAst.new(input, interval)
  end

  # an identifier
  #
  # Used for variables
  class IdAst < AstNode
    include Rvalue

    # @return [String] The ID name
    def name = text_value

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @const = (text_value[0] == text_value[0].upcase)
      @vars = {}
    end

    # @!macro type_check
    def type_check(symtab)
      type_error "no symbol named '#{name}' on line #{lineno}" if symtab.get(name).nil?
    end

    # @!macro type_no_archdef
    def type(symtab)
      return @type unless @type.nil?

      internal_error "Symbol '#{name}' not found" if symtab.get(name).nil?

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
    def const? = @const

    # @!macro value
    def value(symtab)
      # can't do this.... a const might be in a template function, with different values at call time
      # if @const
      #   # consts never change, so we can look them up by arch_def
      #   var = @vars[symtab.archdef]
      #   if var.nil?
      #     var = symtab.get(name)
      #     @vars[symtab.archdef] = var
      #   end
      #   type_error "Variable '#{name}' was not found" if var.nil?
      #   value_error "Value of '#{name}' not known" if var.value.nil?
      #   value_error "Value of #{name} is unknown" if var.value == :unknown

      #   return var.value
      # end

      var = symtab.get(name)

      type_error "Variable '#{name}' was not found" if var.nil?

      value_error "Value of '#{name}' not known" if var.value.nil?

      v = var.value
      value_error "Value of #{name} is unknown" if v == :unknown
      v
    end

    # @!macro to_idl
    def to_idl = name
  end

  class GlobalWithInitializationSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      GlobalWithInitializationAst.new(input, interval, single_declaration_with_initialization.to_ast)
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

    # @return [VariableDeclationWithInitializationAst] The initializer
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
      var_decl_with_init.type(symtab)
    end

    # @1macro value
    def value(symtab)
      var_decl_with_init.value(symtab)
    end

    def add_symbol(symtab)
      raise "Symtab should be at global scope" unless symtab.levels == 1

      # globals never have a compile-time value
      var_decl_with_init.add_symbol(symtab)
    end

    # @1macro to_idl
    def to_idl
      var_decl_with_init.to_idl
    end
  end

  class GlobalSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      GlobalAst.new(input, interval, declaration.to_ast)
    end
  end

  class GlobalAst < AstNode
    include Declaration

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

  end

  # @api private
  class IsaSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      IsaAst.new(
        input,
        interval,
        definitions.elements.reject do |e|
          e.elements.all?(&:space?)
        end.map(&:to_ast)
      )
    end
  end

  # top-level AST node
  class IsaAst < AstNode
    def definitions = children

    # @return [Array<AstNode>] List of all global variable definitions
    def globals = definitions.select { |d| d.is_a?(GlobalWithInitializationAst) || d.is_a?(GlobalAst) }

    # @return {Array<AstNode>] List of all enum definitions
    def enums = definitions.select { |e| e.is_a?(EnumDefinitionAst) || e.is_a?(BuiltinEnumDefinitionAst) }

    # @return {Array<AstNode>] List of all bitfield definitions
    def bitfields = definitions.select { |e| e.is_a?(BitfieldDefinitionAst) }

    # @return [Array<AstNode>] List of all struct definitions
    def structs = definitions.select { |e| e.is_a?(StructDefinitionAst) }

    # @return {Array<AstNode>] List of all function definitions
    def functions = definitions.select { |e| e.is_a?(FunctionDefAst) }

    # Add all the global symbols to symtab
    #
    # @param symtab [SymbolTable] symbol table
    def add_global_symbols(symtab)
      raise "Symtab is not at global scope" unless symtab.levels == 1

      enums.each { |g| g.add_symbol(symtab) }
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
    end
  end

  class ArraySizeSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ArraySizeAst.new(input, interval, expression.to_ast)
    end
  end

  class ArraySizeAst < AstNode
    # @return [AstNode] Array expression
    def expression = children[0]

    def initialize(input, interval, expression)
      super(input, interval, [expression])
    end

    def type_check(symtab)
      expression.type_check(symtab)
      expression_type = expression.type(symtab)
      type_error "#{expression.text_value} is not an array" unless expression_type.kind == :array
      type_error "#{expression.text_value} must be a constant" unless expression_type.const?

      if symtab.archdef.fully_configured? && (expression_type.width == :unknown)
        type_error "#{expression.text_value} must have a known value at compile time"
      end
    end

    def type(symtab)
      if expression.type(symtab).width == :unknown
        Type.new(:bits, width: :unknown, qualifiers: [:const])
      else
        Type.new(:bits, width: expression.type(symtab).width.bit_length, qualifiers: [:const])
      end
    end

    def value(symtab)
      expression.type(symtab).width
    end

    def to_idl = "$array_size(#{expression.to_idl})"
  end


  class EnumSizeSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      EnumSizeAst.new(input, interval, user_type_name.to_ast)
    end
  end

  # represents the builtin that returns the nymber of elements in an enum class
  #
  #  $enum_size(XRegWidth) #=> 2
  class EnumSizeAst < AstNode
    def enum_class = children[0]

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
        qualifiers: [:const]
      )
    end

    def value(symtab)
      enum_class.type(symtab).element_names.size
    end

    def to_idl = "$enum_size(#{enum_class.to_idl})"
  end

  class EnumElementSizeSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      EnumElementSizeAst.new(input, interval, user_type_name.to_ast)
    end
  end

  # represents the builtin that returns the bitwidth of an element in an enum class
  #
  #  $enum_element_size(PrivilegeMode) #=> 3
  class EnumElementSizeAst < AstNode
    def enum_class = children[0]

    def initialize(input, interval, enum_class_name)
      super(input, interval, [enum_class_name])
    end

    def type_check(symtab)
      enum_class.type_check(symtab)
    end

    def type(symtab)
      Type.new(:bits, width: enum_class.type(symtab).width, qualifiers: [:const])
    end

    def value(symtab)
      enum_class.type(symtab).width
    end

    def to_idl = "$enum_element_size(#{enum_class.to_idl})"
  end

  class EnumCastSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      EnumCastAst.new(input, interval, user_type_name.to_ast, expression.to_ast)
    end
  end

  class EnumCastAst < AstNode
    include Rvalue

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

    def to_idl = "$enum(#{enum_name.to_idl}, #{expression.to_idl})"
  end

  class EnumArrayCastSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      EnumArrayCastAst.new(input, interval, user_type_name.to_ast)
    end
  end

  # represents the builtin that returns an array with all elements of an Enum type
  #
  #  $enum_to_a(PrivilegeMode) #=> [3, 1, 1, 0, 5, 4]
  class EnumArrayCastAst < AstNode
    def enum_class = children[0]

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
        sub_type: Type.new(:bits, width: enum_class.type(symtab).width, qualifiers: [:const]),
        qualifiers: [:const]
      )
    end

    def value(symtab)
      enum_class.type(symtab).element_values
    end

    def to_idl = "$enum_to_a(#{enum_class.to_idl})"
  end

  class EnumDefinitionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      values = []

      e.elements.each do |e|
        if e.i.empty?
          values << nil
        else
          values << e.i.int.to_ast
        end
      end

      EnumDefinitionAst.new(
        input,
        interval,
        user_type_name.to_ast,
        e.elements.map { |entry| entry.user_type_name.to_ast },
        values
      )
    end
  end

  # Node representing an IDL enum defintion
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

    def initialize(input, interval, user_type, element_names, element_values)
      super(input, interval, [user_type] + element_names + element_values.reject{ |e| e.nil? })
      @user_type = user_type
      @element_name_asts = element_names
      @element_value_asts = element_values

      @type = EnumerationType.new(name, self.element_names, self.element_values)
    end

    # @return [Array<String>] Array of all element names, in the same order as those from {#element_values}
    def element_names
      return @element_names unless @element_names.nil?

      @element_names = @element_name_asts.map(&:text_value)
    end

    # @return [Array<Integer>]
    #    Array of all element values, in the same order as those from {#element_names}.
    #    All values will be assigned their final values, even those with auto-numbers
    def element_values
      return @element_values unless @element_values.nil?

      next_auto_value = 0
      @element_values = []

      @element_value_asts.each do |e|
        if e.nil?
          @element_values << next_auto_value
          next_auto_value += 1
        else
          @element_values << e.value(nil)
          next_auto_value = @element_values.last + 1
        end
      end

      @element_values
    end

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
    def value(_symtab, _archdef) = raise InternalError, "Enum defintions have no value"

    # @return [String] enum name
    def name = @user_type.text_value

    # @!macro to_idl
    def to_idl
      idl = "enum #{name} { "
      element_names.each_index do |idx|
        idl << "#{element_names[idx]} #{element_values[idx]} "
      end
      idl << "}"
      idl
    end
  end

  class BuiltinEnumDefinitionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      BuiltinEnumDefinitionAst.new(input, interval, user_type_name.to_ast)
    end
  end

  # represents a builtin (auto-generated from config) enum definition
  #
  #   # this will result in a BuiltinEnumDefinitionAst
  #   builtin enum ExtensionName
  #
  class BuiltinEnumDefinitionAst < AstNode
    include Declaration

    def initialize(input, interval, user_type)
      super(input, interval, [user_type])
      @user_type = user_type
    end

    def freeze_tree(global_symtab)
      # call type to get it set before we freeze the object
      type(global_symtab)
      freeze
    end

    # @!macro type_check_no_args
    def type_check(_symtab)
      case @user_type.text_value
      when "ExtensionName", "ExceptionCode", "InterruptCode"
        # OK
      else
        type_error "Unsupported builtin enum type '#{@user_type.text_value}'"
      end
    end

    def element_names(symtab)
      case name
      when "ExtensionName"
        symtab.archdef.extensions.map(&:name)
      when "ExceptionCode"
        symtab.archdef.exception_codes.map(&:var)
      when "InterruptCode"
        symtab.archdef.interrupt_codes.map(&:var)
      else
        type_error "Unknown builtin enum type '#{name}'"
      end
    end

    def element_values(symtab)
      case name
      when "ExtensionName"
        (0...symtab.archdef.extensions.size).to_a
      when "ExceptionCode"
        symtab.archdef.exception_codes.map(&:num)
      when "InterruptCode"
        symtab.archdef.interrupt_codes.map(&:num)
      else
        type_error "Unknown builtin enum type '#{name}'"
      end
    end

    # @!macro type_no_archdef
    def type(symtab)
      return @type unless @type.nil?

      @type = EnumerationType.new(name, element_names(symtab), element_values(symtab))
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      internal_error "All enums should be declared in global scope" unless symtab.levels == 1

      symtab.add!(name, type(symtab))
    end

    # @return [String] name of the enum class
    def name = @user_type.text_value

    # @!macro to_idl
    def to_idl = "builtin enum #{@user_type.text_value}"
  end

  class BitfieldFieldDefinitionAst < AstNode
    # @return [String] The field name
    attr_reader :name

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

    def to_idl
      if @lsb.nil?
        "#{@name} #{@msb.to_idl}"
      else
        "#{@name} #{@msb.to_idl}-#{@lsb.to_idl}"
      end
    end
  end

  class BitfieldDefinitionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      fields = []
      e.elements.each do |f|
        fields << BitfieldFieldDefinitionAst.new(f.input, f.interval, f.field_name.text_value, f.range.int.to_ast, f.range.lsb.empty? ? nil : f.range.lsb.int.to_ast)
      end
      BitfieldDefinitionAst.new(input, interval, user_type_name.to_ast, int.to_ast, fields)
    end
  end

  # represents a bitfield defintion
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

    def initialize(input, interval, name, size, fields)
      super(input, interval, [name, size] + fields)

      @name = name
      @size = size
      @fields = fields
    end

    # @!macro freeze_tree
    def freeze_tree(global_symtab)
      type(global_symtab)
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

      @element_ranges = @fields.map{ |f| f.range(symtab) }
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
    def value(_symtab, _archdef) = raise AstNode::InternalError, "Bitfield defintions have no value"

    # @!macro to_idl
    def to_idl
      idl = ["bitfield (#{@size.to_idl}) #{@name.to_idl} { "]
      @fields.each do |f|
        idl << f.to_idl
      end
      idl << "}"
      idl.join("\n")
    end
  end

  class StructDefinitionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      member_types = []
      member_names = []
      member.elements.each do |m|
        member_types << m.type_name.to_ast
        member_names << m.id.text_value
      end
      StructDefinitionAst.new(input, interval, user_type_name.text_value, member_types, member_names)
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
      @type = StructType.new(@name, @member_types.map do |t|
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
  class AryAccessSyntaxNode < Treetop::Runtime::SyntaxNode
    # fix up left recursion
    #
    # @return [AstNode] New tree rooted at the array access
    def to_ast
      var = a.to_ast
      brackets.elements.each do |bracket|
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

    # @!macro to_idl
    def to_idl
      if bracket.msb.empty?
        "#{a.to_idl}[#{brackets.lsb.to_idl}]"
      else
        "#{a.to_idl}[#{brackets.msb.to_idl}:#{brackets.lsb.to_idl}]"
      end
    end
  end

  class AryElementAccessAst < AstNode
    include Rvalue

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

      if var.type(symtab).kind == :array
        value_result = value_try do
          index_value = index.value(symtab)
          type_error "Array index out of range" if index_value >= var.type(symtab).width
        end # Ok, doesn't need to be known

      elsif var.type(symtab).integral?
        if var.type(symtab).kind == :bits
          value_result = value_try do
            index_value = index.value(symtab)
            if index_value >= var.type(symtab).width
              type_error "Bits element index (#{index_value}) out of range (max #{var.type(symtab).width - 1}) in access '#{text_value}'"
            end
          end # OK, doesn need to be known
        end

      else
        type_error "Array element access can only be used with integral types and arrays"
      end
    end

    def type(symtab)
      if var.type(symtab).kind == :array
        var.type(symtab).sub_type
      elsif var.type(symtab).integral?
        Bits1Type
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
    def to_idl = "#{var.to_idl}[#{index.to_idl}]"
  end

  class AryRangeAccessAst < AstNode
    include Rvalue

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

        if var.type(symtab).kind == :bits && msb_value >= var.type(symtab).width
          type_error "Range too large for bits (msb = #{msb_value}, range size = #{var.type(symtab).width})"
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
        return Type.new(:bits, width: range_size)
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
    def to_idl = "#{var.to_idl}[#{msb.to_idl}:#{lsb.to_idl}]"

  end

  class PcAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      PcAssignmentAst.new(input, interval, rval.to_ast)
    end
  end

  class PcAssignmentAst < AstNode
    include Executable

    # @return [AstNode] Right-hand side expression
    def rhs = children[0]

    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    # @macro execute
    def execute(symtab) = value_error "$pc is never statically known"

    # @macro execute_unknown
    def execute_unknown(symtab); end

    # @!macro type_check
    def type_check(symtab)
    end

    # @!macro value
    def value(symtab) = value_error "$pc is never statically known"

    # @!macro type
    def type(symtab) = symtab.xreg_type

    # @!macro to_idl
    def to_idl = "$pc = #{rhs.to_idl}"
  end

  class VariableAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      VariableAssignmentAst.new(input, interval, var.to_ast, rval.to_ast)
    end
  end

  # represents a scalar variable assignment statement
  #
  # for example, these will result in a VariableAssignmentAst
  #   # given: Bits<XLEN> zero;
  #   zero = XLEN'b0
  class VariableAssignmentAst < AstNode
    include Executable

    def lhs = @children[0]
    def rhs = @children[1]

    def initialize(input, interval, lhs_ast, rhs_ast)
      super(input, interval, [lhs_ast, rhs_ast])
      @vars = {}
    end

    # @!macro type_check
    def type_check(symtab)
      lhs.type_check(symtab)
      type_error "Cannot assign to a const" if lhs.type(symtab).const?

      rhs.type_check(symtab)
      unless rhs.type(symtab).convertable_to?(lhs.type(symtab))
        type_error "Incompatible type in assignment (#{lhs.type(symtab)}, #{rhs.type(symtab)})"
      end
    end

    def var(symtab)
      variable = @vars[symtab.archdef]
      if variable.nil?
        variable = symtab.get(lhs.text_value)
        @vars[symtab.archdef] = variable
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

        value_result = value_try do
          variable.value = rhs.value(symtab)
        end
        value_else(value_result) do
          variable.value = nil
          value_error ""
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
    def to_idl = "#{lhs.to_idl} = #{rhs.to_idl}"
  end

  class AryElementAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      AryElementAssignmentAst.new(input, interval, var.to_ast, idx.to_ast, rval.to_ast)
    end
  end

  # represents an array element assignement
  #
  # for example:
  #   X[rs1] = XLEN'd0
  class AryElementAssignmentAst < AstNode
    include Executable

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
      type_errpr "Assigning to a constant" if lhs.type(symtab).const?

      idx.type_check(symtab)

      type_error "Index must be integral" unless idx.type(symtab).integral?

      value_result = value_try do
        idx_value = idx.value(symtab)
        type_error "Array index (#{idx.text_value} = #{idx_value}) out of range (< #{var.type(symtab).width})" if idx_value >= lhs.type(symtab).width
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
          type_error "Incompatible type in integer slice assignement"
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
          var.value = (lhs.value & ~0) | ((v & 1) << idx.value(symtab))
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
      case lhs.type(symtab).kind
      when :array
        lhs_value = lhs.value(symtab)
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
    def to_idl = "#{lhs.to_idl}[#{idx.to_idl}] = #{rhs.to_idl}"
  end

  class AryRangeAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      AryRangeAssignmentAst.new(input, interval, var.to_ast, msb.to_ast, lsb.to_ast, rval.to_ast)
    end
  end

  # represents an array range assignement
  #
  # for example:
  #   vec[8:0] = 8'd0
  class AryRangeAssignmentAst < AstNode
    include Executable

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
      type_error "#{varible.text_value} must be integral" unless variable.type(symtab).kind == :bits
      type_errpr "Assigning to a constant" if variable.type(symtab).const?

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
        value_error "Either the range or right-hand side of an array range assignemnt is unknown"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.add(variable.name, Var.new(variable.name, variable.type(symtab)))
    end

    # @!macro to_idl
    def to_idl = "#{variable.to_idl}[#{msb.to_idl}:#{lsb.to_idl}] = #{write_value.to_idl}"
  end

  class FieldAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      FieldAssignmentAst.new(input, interval, field_access_expression.to_ast, rval.to_ast)
    end
  end

  # represents a bitfield or struct assignement
  #
  # for example:
  #   Sv39PageTableEntry entry;
  #   entry.PPN = 0
  #
  class FieldAssignmentAst < AstNode
    include Executable

    def field_access = @children[0]
    def write_value = @children[1]

    def initialize(input, interval, field_access, write_value)
      super(input, interval, [field_access, write_value])
    end

    # @!macro type
    def type(symtab)
      field_access.type(symtab)
    end

    # @!macro type_check
    def type_check(symtab)
      field_access.type_check(symtab)

      type_error "Cannot write const variable" if field_access.type(symtab).const?

      write_value.type_check(symtab)
      return if write_value.type(symtab).convertable_to?(type(symtab))

      type_error "Incompatible type in assignment (#{type(symtab)}, #{write_value.type(symtab)})"
    end

    # @!macro execute
    def execute(symtab)
      if field_access.type(symtab).kind == :struct
        struct_val = field_access.obj.value(symtab)
        struct_val[field_access.field_name] = write_value.value(symtab)
        symtab.add(field_access.obj.name, Var.new(field_access.obj.name, field_access.obj.type(symtab), struct_val))
      else
        value_error "TODO: Field assignement execution"
      end
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.add(field_access.obj.name, Var.new(field_access.obj.name, field_access.obj.type(symtab), nil))
    end

    # @!macro to_idl
    def to_idl = "#{field_access.to_idl} = #{write_value.to_idl}"
  end

  class CsrFieldAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      CsrFieldAssignmentAst.new(input, interval, csr_field_access_expression.to_ast, rval.to_ast)
    end
  end

  class CsrFieldAssignmentAst < AstNode
    include Executable

    def csr_field = @children[0]
    def write_value = @children[1]

    def initialize(input, interval, csr_field, write_value)
      super(input, interval, [csr_field, write_value])
    end

    def type(symtab)
      if field(symtab).defined_in_all_bases?
        if symtab.archdef.mxlen == 64 && symtab.archdef.multi_xlen?
          Type.new(:bits, width: [field(symtab).location(symtab.archdef, 32).size, field(symtab).location(symtab.archdef, 64).size].max)
        else
          Type.new(:bits, width: field(symtab).location(symtab.archdef, symtab.archdef.mxlen).size)
        end
      elsif field(symtab).base64_only?
        Type.new(:bits, width: field(symtab).location(symtab.archdef, 64).size)
      elsif field(symtab).base32_only?
        Type.new(:bits, width: field(symtab).location(symtab.archdef, 32).size)
      else
        internal_error "Unexpected base for field"
      end
    end

    def field(symtab)
      csr_field.field_def(symtab)
    end

    def type_check(symtab)
      csr_field.type_check(symtab)
      value_try do
        if ["RO", "RO-H"].any?(csr_field.field_def(symtab).type(symtab))
          type_error "Cannot write to read-only CSR field"
        end
      end
      # ok, we don't know the type because the archdef isn't configured

      write_value.type_check(symtab)
      type_error "Incompatible type in assignment" unless write_value.type(symtab).convertable_to?(type(symtab))
    end

    # @!macro execute
    def execute(symtab)
      value_error "CSR field writes are never compile-time-executable"
    end

    # @!macro execute_unknown
    def execute_unknown(symtab); end

    def to_idl = "#{csr_field.to_idl} = #{write_value.to_idl}"
  end

  class MultiVariableAssignmentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      MultiVariableAssignmentAst.new(input, interval, [first.to_ast] + rest.elements.map { |r| r.var.to_ast }, function_call.to_ast)
    end
  end

  # represents assignement of multiple variable from a function call that returns multiple values
  #
  # for example:
  #   (match_result, cfg) = pmp_match<access_size>(paddr);
  class MultiVariableAssignmentAst < AstNode
    include Executable

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
    def to_idl = "(#{variables.map(&:to_idl).join(', ')}) = #{function_call.to_idl}"
  end

  class MultiVariableDeclarationSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      MultiVariableDeclarationAst.new(input, interval, type_name.to_ast, [first.to_ast] + rest.elements.map { |r| r.id.to_ast })
    end
  end

  # represents the declaration of multiple variables
  #
  # for example:
  #   Bits<64> a, b;
  #   Bits<64> a, b, c, d;
  class MultiVariableDeclarationAst < AstNode
    include Declaration

    def type_name = @children[0]
    def var_names = @children[1..]

    def initialize(input, interval, type_name, var_names)
      super(input, interval, [type_name] + var_names)

      @global = false
    end

    def make_global
      @global = true
    end

    # @return [Array<String>] Variables being declared
    def var_names
      var_names.map(&:text_value)
    end

    # @!macro type_check
    def type_check(symtab)
      type_name.type_check(symtab)

      add_symbol(symtab)
    end

    def type(symtab)
      if @global
        type_name.type(symtab).clone.make_global
      else
        type_name.type(symtab)
      end
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      var_names.each do |vname|
        symtab.add(vname.text_values, Var.new(vname.text_value, type(symtab), type(symtab).default))
      end
    end

    # @!macro to_idl
    def to_idl = "#{type_name.to_idl} #{var_names.map(&:to_idl).join(', ')}"
  end

  class VariableDeclarationSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      VariableDeclarationAst.new(input, interval, type_name.to_ast, id.to_ast, ary_size.empty? ? nil : ary_size.ary_size_decl.expression.to_ast)
    end
  end

  # represents a single variable declaration (without assignement)
  #
  # for example:
  #   Bits<64> doubleword
  #   Boolean has_property
  class VariableDeclarationAst < AstNode
    include Declaration

    def type_name = children[0]
    def id = children[1]
    def ary_size = children[2]

    def name = id.text_value

    def initialize(input, interval, type_name, id, ary_size)
      if ary_size.nil?
        super(input, interval, [type_name, id])
      else
        super(input, interval, [type_name, id, ary_size])
      end

      @global = false
    end

    def make_global
      @global = true
    end

    def decl_type(symtab)
      dtype = type_name.type(symtab)

      return nil if dtype.nil?

      qualifiers = []
      qualifiers << :const if id.text_value[0].upcase == id.text_value[0]
      qualifiers << :global if @global

      dtype = Type.new(:enum_ref, enum_class: dtype, qualifiers:) if dtype.kind == :enum

      # dtype = dtype.clone.qualify(q.text_value.to_sym) unless q.empty?

      unless ary_size.nil?
        value_result = value_try do
          dtype = Type.new(:array, width: ary_size.value(symtab), sub_type: dtype, qualifiers:)
        end
        value_else(value_result) do
          type_error "Array size must be known at compile time" if symtab.archdef.fully_configured?
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

      type_error "Constants must be initialized at declaration" if id.text_value[0] == id.text_value[0].upcase

      unless ary_size.nil?
        ary_size.type_check(symtab)
        value_result = value_try do
          ary_size.value(symtab)
        end
        value_else(value_result) do
          # if this is a fully configured ArchDef, this is an error because all constants are supposed to be known
          if symtab.archdef.fully_configured?
            type_error "Array size (#{ary_size.text_value}) must be known at compile time"
          else
            # otherwise, it's ok that we don't know the value yet, as long as the value is a const
            type_error "Array size (#{ary_size.text_value}) must be a constant" unless ary_size.type(symtab).const?
          end
        end
      end

      add_symbol(symtab) if add_sym

      id.type_check(symtab)
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      if @global
        # fill global with nil to prevent its use in compile-time evaluation
        symtab.add!(id.text_value, Var.new(id.text_value, decl_type(symtab), nil))
      else
        type_error "No Type '#{type_name.text_value}'" if decl_type(symtab).nil?
        symtab.add(id.text_value, Var.new(id.text_value, decl_type(symtab), decl_type(symtab).default))
      end
    end

    # @!macro to_idl
    def to_idl
      if ary_size.nil?
        "#{type_name.to_idl} #{id.to_idl}"
      else
        "#{type_name.to_idl} #{id.to_idl}[#{ary_size.to_idl}]"
      end
    end
  end

  class VariableDeclarationWithInitializationSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ary_size_ast = ary_size.empty? ? nil : ary_size.expression.to_ast
      VariableDeclarationWithInitializationAst.new(
        input, interval,
        type_name.to_ast, id.to_ast, ary_size_ast, rval.to_ast
      )
    end
  end

  # reprents a single variable declaration with initialization
  #
  # for example:
  #   Bits<64> doubleword = 64'hdeadbeef
  #   Boolean has_property = true
  class VariableDeclarationWithInitializationAst < AstNode
    include Executable
    include Declaration

    def type_name = @children[0]
    def lhs = @children[1]
    def ary_size = @children[3]
    def rhs = @children[2]

    def initialize(input, interval, type_name_ast, var_write_ast, ary_size, rval_ast)
      if ary_size.nil?
        super(input, interval, [type_name_ast, var_write_ast, rval_ast])
      else
        super(input, interval, [type_name_ast, var_write_ast, rval_ast, ary_size])
      end
      @global = false
    end

    def make_global
      @global = true
    end

    def lhs_type(symtab)
      decl_type = type_name.type(symtab).clone
      type_error "No type '#{type_name.text_value}' on line #{lineno}" if decl_type.nil?

      qualifiers = []
      qualifiers << :const if lhs.text_value[0].upcase == lhs.text_value[0]
      qualifiers << :global if @global

      decl_type = Type.new(:enum_ref, enum_class: decl_type) if decl_type.kind == :enum

      qualifiers.each do |q|
        decl_type.qualify(q)
      end

      unless ary_size.nil?
        value_result = value_try do
          decl_type = Type.new(:array, sub_type: decl_type, width: ary_size.value(symtab), qualifiers:)
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
          symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone, rhs.value(symtab)))
        end
        value_else(value_result) do
          unless rhs.type(symtab).const?
            type_error "Declaring constant with a non-constant value (#{e})"
          end
          symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone))
        end
      else
        symtab.add(lhs.text_value, Var.new(lhs.text_value, decl_type.clone))
      end

      lhs.type_check(symtab)

      # now check that the assignment is compatible
      return if rhs.type(symtab).convertable_to?(decl_type)

      type_error "Incompatible type (#{decl_type}, #{rhs.type(symtab)}) in assignment"
    end

    # @!macro add_symbol
    def add_symbol(symtab)
      if @global
        if lhs.text_value[0] == lhs.text_value[0].upcase
          # const, add the value if it's known
          value_result = value_try do
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs.value(symtab)))
          end
          value_else(value_result) do
            symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab)))
          end
        else
          # mutable globals never have a compile-time value
          symtab.add!(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab)))
        end
      else
        value_result = value_try do
          symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs.value(symtab)))
        end
        value_else(value_result) do
          symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab)))
        end
      end
    end

    # @!macro execute
    def execute(symtab)
      value_error "TODO: Array declaration" unless ary_size.nil?
      rhs_value = nil
      return if @global # never executed at compile time

      value_result = value_try do
        rhs_value = rhs.value(symtab)
      end
      value_else(value_result) do
        symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), nil))
        value_error "value of right-hand side of variable initialization is unknown"
      end
      symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs_value))
    end

    # @!macro execute_unknown
    def execute_unknown(symtab)
      symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), nil))
    end

    # @!macro to_idl
    def to_idl
      if ary_size.nil?
        "#{type_name.to_idl} #{lhs.to_idl} = #{rhs.to_idl}"
      else
        "#{type_name.to_idl} #{lhs.to_idl}[#{ary_size.to_idl}] = #{rhs.to_idl}"
      end
    end
  end

  class BinaryExpressionRightSyntaxNode < Treetop::Runtime::SyntaxNode

    # fix up left recursion
    # i.e., xlen() - 1 - i => (xlen() - 1) - i
    def to_ast
      first =
        BinaryExpressionAst.new(
          input, (interval.begin...r.elements[0].r.interval.end),
          l.to_ast, r.elements[0].op.text_value, r.elements[0].r.to_ast
        )

      if r.elements.size == 1
        first
      else
        r.elements[1..].inject(first) do |lhs, el|
          BinaryExpressionAst.new(input, (lhs.interval.begin...el.r.interval.end),
                                  lhs, el.op.text_value, el.r.to_ast)
        end
      end
    end

    def type_check(_symtab)
      raise "you must have forgotten the to_ast pass"
    end
  end

  class SignCastSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      SignCastAst.new(input, interval, expression.to_ast)
    end
  end

  class SignCastAst < AstNode
    include Rvalue

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
    def to_idl = "$signed(#{expression.to_idl})"
  end

  class BitsCastSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      BitsCastAst.new(input, interval, expression.to_ast)
    end
  end

  # Node for a cast to a Bits<N> type
  #
  # This will result in a BitsCaseAst:
  #
  #   $bits(ExceptionCode::LoadAccessFault) 
  class BitsCastAst < AstNode
    include Rvalue

    # @return [AstNode] The casted expression
    def expression = @children[0]

    def initialize(input, interval, exp) = super(input, interval, [exp])

    # @!macro type_check
    def type_check(symtab)
      expression.type_check(symtab)

      unless [:bits, :enum_ref, :csr].include?(expression.type(symtab).kind)
        type_error "#{expression.type(symtab)} Cannot be cast to bits"
      end
    end

    # @!macro type
    def type(symtab)
      etype = expression.type(symtab)

      case etype.kind
      when :bits
        etype
      when :enum_ref
        Type.new(:bits, width: etype.enum_class.width)
      when :csr
        if etype.csr.dynamic_length?(symtab.archdef)
          Type.new(:bits, width: :unknown)
        else
          Type.new(:bits, width: etype.csr.length(symtab.archdef))
        end
      end
    end

    # @!macro value
    def value(symtab)
      etype = expression.type(symtab)

      case etype.kind
      when :bits
        expression.value(symtab)
      when :enum_ref
        if expression.is_a?(EnumRefAst)
          element_name = expression.text_value.split(":")[2]
          etype.enum_class.value(element_name)
        else
          # this is an expression with an EnumRef type
          expression.value(symtab)
        end
      when :csr
        expression.value(symtab)
      else
        internal_error "TODO: Bits cast for #{etype.kind}"
      end
    end

    # @!macro to_idl
    def to_idl = "$signed(#{expression.to_idl})"
  end

  class BinaryExpressionAst < AstNode
    include Rvalue

    LOGICAL_OPS = ["==", "!=", ">", "<", ">=", "<=", "&&", "||"].freeze
    BIT_OPS = ["&", "|", "^"].freeze
    ARITH_OPS = ["+", "-", "/", "*", "%", "<<", ">>", ">>>"].freeze
    OPS = (LOGICAL_OPS + ARITH_OPS + BIT_OPS).freeze

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
    def to_idl
      "(#{lhs.to_idl} #{op} #{rhs.to_idl})"
    end

    # @!macro type
    def type(symtab)
      lhs_type = lhs.type(symtab)
      short_circuit = false

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
      elsif op == "<<"
        value_result = value_try do
          # if shift amount is known, then the result width is increased by the shift
          # otherwise, the result is the width of the left hand side
          value_error "lhs width unknown" if lhs_type.width == :unknown
          return Type.new(:bits, width: lhs_type.width + rhs.value(symtab), qualifiers:)
        end
        value_else(value_result) do
          Type.new(:bits, width: lhs_type.width, qualifiers:)
        end
      #elsif ["+", "-", "*", "/", "%"].include?(op)
      elsif lhs_type.const? && rhs_type.const?
        # if both types are const and the operator results in a Bits type,
        # then the result type is the largest of:
        #
        #  * the minimum bit width needed to represent `lhs op rhs`
        #  * the largest width of either lhs or rhs
        result_width =
          case op
          when "*"
            if [lhs_type.width, rhs_type.width].include?(:unknown)
              :unknown
            else
              lhs_type.width + rhs_type.width
            end
          when "+", "-"
            if [lhs_type.width, rhs_type.width].include?(:unknown)
              :unknown
            else
              [lhs_type.width, rhs_type.width].max + 1
            end
          when "/", "%", ">>", ">>>"
            lhs_type.width
          when "&", "|", "^"
            if [lhs_type.width, rhs_type.width].include?(:unknown)
              :unknown
            else
              [lhs_type.width, rhs_type.width].max
            end
          end
        qualifiers << :signed if lhs_type.signed? && rhs_type.signed?
        Type.new(:bits, width: result_width, qualifiers:)
      else
        qualifiers << :signed if lhs_type.signed? && rhs_type.signed?
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
      short_circuit = false
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
      elsif op == ">>" || op == ">>>"
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        type_error "Unsupported type for right shift: #{lhs_type(symtab)}" unless lhs_type.kind == :bits
        type_error "Unsupported shift for right shift: #{rhs_type(symtab)}" unless rhs_type.kind == :bits
      elsif ["*", "/", "%"].include?(op)
        rhs_type = rhs.type(symtab)
        lhs_type = lhs.type(symtab)
        unless lhs_type.integral? && rhs_type.integral?
          type_error "Multiplication/division is only defined for integral types. Maybe you forgot a $bits cast?"
        end
      elsif ["+", "-"].include?(op)
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

    # @!macro value
    def value(symtab)
      # cached_value = @value_cache[symtab]
      # return cached_value unless cached_value.nil?

      value = 
        if op == ">>>"
          lhs_value = lhs.value(symtab)
          if lhs_value & (1 << (lhs.type(symtab).width - 1)).zero?
            lhs_value >> rhs.value(symtab)
          else
            # need to shift in ones
            shift_amount = rhs.value(symtab)
            shifted_value = lhs_value >> shift_amount
            mask_len = lhs.type(symtab).width - shift_amount
            mask = ((1 << mask_len) - 1) << shift_amount

            shifted_value | mask
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
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value <= rhs_value} }
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
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value >= rhs_value} }
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
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value < rhs_value} }
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
            if lhs.values(symtab).all? { |lhs_value| rhs_values.all? { |rhs_value| lhs_value > rhs_value} }
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
          # ok, trye rhs

          return 0 if rhs.value(symtab).zero?

          lhs.value(symtab) & rhs.value(symtab)

        elsif op == "|"
          # if one side is all ones, we don't need to know the other side
          value_result = value_try do
            rhs_mask = ((1 << rhs.type(symtab).width) - 1)
            return rhs_mask if (rhs.value(symtab) == rhs_mask) && (lhs.type(symtab).width <= rhs.type(symtab).width)
          end
          # ok, trye rhs

          lhs_mask = ((1 << lhs.type(symtab).width) - 1)
          return lhs_mask if (lhs.value(symtab) == lhs_mask) && (rhs.type(symtab).width <= lhs.type(symtab).width)

          lhs.value(symtab) | rhs.value(symtab)

        else
          v =
            case op
            when "+"
              lhs.value(symtab) + rhs.value(symtab)
            when "-"
              lhs.value(symtab) - rhs.value(symtab)
            when "*"
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
            when "<<"
              lhs.value(symtab) << rhs.value(symtab)
            else
              internal_error "Unhandled binary op #{op}"
            end

          v_trunc =
            if !lhs.type(symtab).const? || !rhs.type(symtab).const?
              # when both sides are constant, the value is not truncated
              v & ((1 << type(symtab).width) - 1)
            else
              v
            end
  
          warn "WARNING: The value of '#{text_value}' (#{lhs.type(symtab).const?}, #{rhs.type(symtab).const?}) is truncated from #{v} to #{v_trunc} because the result is only #{type(symtab).width} bits" if v != v_trunc
          v_trunc
        end
      # @value_cache[symtab] = value
      value
    end

    # returns the operator as a string
    attr_reader :op
  end

  class ParenExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ParenExpressionAst.new(input, interval, e.to_ast)
    end
  end

  # represents a parenthesized expression
  #
  # for example:
  #  (a + b)
  class ParenExpressionAst < AstNode
    include Rvalue

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
    def to_idl = "(#{expression.to_idl})"
  end

  class ArrayLiteralSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ArrayLiteralAst.new(input, interval, [first.to_ast] + rest.elements.map { |r| r.expression.to_ast })
    end
  end

  class ArrayLiteralAst < AstNode
    include Rvalue

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

    def to_idl = "[#{element_nodes.map(&:to_idl).join(',')}]"
  end

  class ConcatenationExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ConcatenationExpressionAst.new(input, interval, [first.to_ast] + rest.elements.map{ |e| e.expression.to_ast })
    end
  end

  # represents a concatenation expression
  #
  # for example:
  #   {1'b0, 5'd3}
  class ConcatenationExpressionAst < AstNode
    include Rvalue

    def expressions = @children

    # @!macro type_check
    def type_check(symtab)
      type_error "Must concatenate at least two objects" if expressions.size < 2

      expressions.each do |exp|
        exp.type_check(symtab)
        type_error "Concatenation only supports Bits<> types" unless exp.type(symtab).kind == :bits

        internal_error "Negative width for element #{exp.text_value}" if exp.type(symtab).width <= 0
      end
    end

    # @!macro type
    def type(symtab)
      total_width = expressions.reduce(0) { |sum, exp| sum + exp.type(symtab).width }

      Type.new(:bits, width: total_width)
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
    def to_idl = "{#{expressions.map { |exp| exp.to_idl }.join(',')}}"
  end

  class ReplicationExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ReplicationExpressionAst.new(input, interval, n.to_ast, v.to_ast)
    end
  end

  # represents a replication expression
  #
  # for example:
  #   {5{5'd3}}
  class ReplicationExpressionAst < AstNode
    include Rvalue

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
        return Type.new(:bits, width:)
      end
      value_else(value_result) do
        Type.new(:bits, width: :unknown)
      end
    end

    # @!macro to_idl
    def to_idl = "{#{n.to_idl}{#{v.to_idl}}}"
  end

  class PostDecrementExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      PostDecrementExpressionAst.new(input, interval, rval.to_ast)
    end
  end

  # represents a post-decrement expression
  #
  # for example:
  #   i--
  class PostDecrementExpressionAst < AstNode
    include Executable

    def rval = @children[0]

    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    def type_check(symtab)
      rval.type_check(symtab)
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

    def to_idl = "#{rval.to_idl}--"
  end

  class BuiltinVariableSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      BuiltinVariableAst.new(input, interval)
    end
  end

  class BuiltinVariableAst < AstNode

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
        Type.new(:bits, width: sz.value, qualifiers: [:const])
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

    def to_idl = name
  end

  class PostIncrementExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      PostIncrementExpressionAst.new(input, interval, rval.to_ast)
    end
  end

  # represents a post-increment expression
  #
  # for example:
  #   i++
  class PostIncrementExpressionAst < AstNode
    include Executable

    def rval = @children[0]

    def initialize(input, interval, rval)
      super(input, interval, [rval])
    end

    # @!macro type_check
    def type_check(symtab)
      rval.type_check(symtab)
      var = symtab.get(rval.text_value)
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
    def to_idl = "#{rval.to_idl}++"
  end

  class FieldAccessExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      FieldAccessExpressionAst.new(input, interval, field_access_eligible_expression.to_ast, field_name.text_value)
    end
  end

  # represents a bitfield or struct field access (rvalue)
  #
  # for example:
  #   entry.PPN
  class FieldAccessExpressionAst < AstNode
    include Rvalue

    def obj = @children[0]

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
        Type.new(:bits, width: obj_type.range(@field_name).size)
      elsif obj_type.kind == :struct
        obj_type.member_type(@field_name)
      else
        internal_error "huh? #{obj.text_value} #{obj_type.kind}"
      end
    end

    def type_check(symtab)
      obj.type_check(symtab)

      obj_type = obj.type(symtab)

      if obj_type.kind == :bitfield
        internal_error "#{bitfield.text_value} Not a BitfieldType (is a #{obj_type.class.name})" unless obj_type.respond_to?(:field_names)
        unless obj_type.field_names.include?(@field_name)
          type_error "#{@field_name} is not a member of #{obj_type}"
        end
      elsif obj_type.kind == :struct
        type_error "#{@field_name} is not a member of #{obj_type}" unless obj_type.member?(@field_name)
      else
        type_error "#{obj.text_value} is not a bitfield (is #{obj.type(symtab)})"
      end
    end

    # @!macro value
    def value(symtab)
      if kind(symtab) == :bitfield
        range = obj.type(symtab).range(@field_name)
        (obj.value(symtab) >> range.first) & ((1 << range.size) - 1)
      elsif kind(symtab) == :struct
        obj.value(symtab)[@field_name]
      else
        type_error "#{obj.text_value} is Not a bitfield."
      end
    end

    # @!macro to_idl
    def to_idl = "#{obj.to_idl}.#{@field_name}"
  end

  class EnumRefSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      EnumRefAst.new(input, interval, enum_class.text_value, member.text_value)
    end
  end

  # represents an enum reference
  #
  # for example:
  #  ExtensionName::C
  #  PrivilegeMode::M
  class EnumRefAst < AstNode
    include Rvalue

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
      enum_def_ast = global_symtab.archdef.global_ast.enums.find { |e| e.name == @enum_class_name }

      @enum_def_type =
        if enum_def_ast.is_a?(BuiltinEnumDefinitionAst)
          enum_def_ast&.type(global_symtab)
        else
          enum_def_ast&.type(nil)
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

    # @!macro type_no_archdef
    def type(symtab)
      internal_error "Not frozen?" unless frozen?
      type_error "No enum named #{@enum_class_name}" if @enum_def_type.nil?

      @enum_def_type.ref_type
    end

    # @!macro value_no_archdef
    def value(symtab)
      internal_error "Must call type_check first" if @enum_def_type.nil?

      @enum_def_type.value(@member_name)
    end

    # @!macro to_idl
    def to_idl = "#{@enum_class_name}::#{@member_name}"
  end

  class UnaryOperatorExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      UnaryOperatorExpressionAst.new(input, interval, o.text_value, e.to_ast)
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
          type_error "#{exp.type(symtab)} does not support unary #{op} operator"
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
      if type(symtab).integral?
        val_trunc = val & ((1 << type(symtab).width) - 1)
        if type(symtab).signed? && ((((val_trunc >> (type(symtab).width - 1))) & 1) == 1)
          # need to make this negative!
          # take the twos compliment
          val_trunc = -((1 << type(symtab).width) - val_trunc)
        end
      end

      if op != "~"
        warn "#{text_value} is truncated due to insufficient bit width (from #{val} to #{val_trunc} on line #{lineno})" if val_trunc != val
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
    def to_idl = "#{op}#{expression.to_idl}"
  end

  class TernaryOperatorExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      TernaryOperatorExpressionAst.new(input, interval, e.to_ast, t.to_ast, f.to_ast)
    end
  end

  # Represents a ternary operator
  #
  # for example:
  #   condition ? a : b
  #   (a < b) ? c : d
  class TernaryOperatorExpressionAst < AstNode
    include Rvalue

    def condition = @children[0]
    def true_expression = @children[1]
    def false_expression = @children[2]

    def initialize(input, interval, condition, true_expression, false_expression)
      super(input, interval, [condition, true_expression, false_expression])
    end

    # @!macro type_check
    def type_check(symtab)
      condition.type_check(symtab)
      type_error "ternary selector must be bool" unless condition.type(symtab).kind == :boolean

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
            if true_width == :unknown || false_width == :unknown
              Type.new(:bits, width: :unknown)
            else
              Type.new(:bits, width: [true_width, false_width].max)
            end
          else
            true_expression.type(symtab).clone
          end
        if condition.type(symtab).const? && true_expression.type(symtab).const? && false_expression.type(symtab).const?
          t.make_const
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
    def to_idl = "#{condition.to_idl} ? #{true_expression.to_idl} : #{false_expression.to_idl}"
  end

  class StatementSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      StatementAst.new(input, interval, a.to_ast)
    end
  end

  class NoopAst < AstNode
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
    def to_idl = "#{action.to_idl};"
  end

  class ConditionalStatementSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ConditionalStatementAst.new(input, interval, a.to_ast, expression.to_ast)
    end
  end

  # represents a predicated simple statement
  #
  # for example:
  #   a = 2 if condition;
  class ConditionalStatementAst < AstNode
    def action = @children[0]
    def condition = @children[1]

    def initialize(input, interval, action, condition)
      super(input, interval, [action, condition])
    end

    # @!macro type_check
    def type_check(symtab)
      action.type_check(symtab)
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
    def to_idl
      "#{action.to_idl} if (#{condition.to_idl});"
    end
  end

  class DontCareReturnSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      DontCareReturnAst.new(input, interval)
    end
  end

  # represents a don't care return value
  #
  # for exaple:
  #   return -;
  class DontCareReturnAst < AstNode
    include Rvalue

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

    def to_idl = "-"
  end

  class DontCareLvalueSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast = DontCareLvalueAst.new(input, interval)
  end

  class DontCareLvalueAst < AstNode
    include Rvalue

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
    def value(_symtab, _archdef) = internal_error "Why are you calling value for an lval?"

    def to_idl = "-"
  end

  class ReturnStatementSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ReturnStatementAst.new(input, interval, return_expression.to_ast)
    end
  end

  # represents a function return statement
  #
  # for example:
  #   return 5;
  #   return X[rs1] + 1;
  class ReturnStatementAst < AstNode
    include Returns

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

    # @retrun [Type] The actual return type
    def return_type(symtab)
      return_expression.retrun_type(symtab)
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

    def to_idl = "#{return_expression.to_idl};"
  end

  class ReturnExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ReturnExpressionAst.new(input, interval, [first.to_ast] + rest.elements.map { |r| r.e.to_ast })
    end
  end

  class ReturnExpressionAst < AstNode
    def return_value_nodes = @children

    def initialize(input, interval, return_nodes)
      super(input, interval, return_nodes)
      @func_type_cache = {}
    end

    # @return [Array<Type>] List of actual return types
    def return_types(symtab)
      if return_value_nodes[0].type(symtab).kind == :tuple
        return_value_nodes[0].type(symtab).tuple_types
      else
        return_value_nodes.map{ |v| v.type(symtab) }
      end
    end

    # @retrun [Type] The actual return type
    def return_type(symtab)
      types = return_types(symtab)
      if types.size > 1
        Type.new(:tuple, tuple_types: types)
      else
        types[0]
      end
    end

    # @return [Type] The expected return type (as defined by the encolsing function)
    def expected_return_type(symtab)
      func_def = find_ancestor(FunctionDefAst)
      if func_def.nil?
        if symtab.get("__expected_return_type").nil?
          internal_error "Forgot to set __expected_return_type in the symbol table"
        end

        symtab.get("__expected_return_type")
      else
        # need to find the type to get the right symbol table
        func_type = @func_type_cache[symtab.archdef]
        return func_type.return_type(EMPTY_ARRAY, self) unless func_type.nil?

        func_type = symtab.get_global(func_def.name)
        internal_error "Couldn't find function type for '#{func_def.name}' #{symtab.keys} " if func_type.nil?

        # to get the return type, we need to find the template values in case this is
        # a templated function definition
        #
        # that information should be up the stack in the symbol table
        if func_type.templated?
          template_values = symtab.find_all(single_scope: true) do |o|
            o.is_a?(Var) && o.template_value_for?(func_def.name)
          end
          unless template_values.size == func_type.template_names.size
            internal_error "Did not find correct number of template arguments (found #{template_values.size}, need #{func_type.template_names.size}) #{symtab.keys_pretty}"
          end
          func_type.return_type(template_values.sort { |a, b| a.template_index <=> b.template_index }.map(&:value), self)
        else
          @func_type_cache[symtab.archdef]= func_type
          func_type.return_type(EMPTY_ARRAY, self)
        end
      end
    end

    # @!macro type_check
    def type_check(symtab)
      return_value_nodes.each do |v|
        v.type_check(symtab)
        type_error "Unknown type for #{v.text_value}" if v.type(symtab).nil?
      end

      if return_value_nodes[0].type(symtab).kind == :tuple
        type_error("Can't combine tuple types in return") unless return_value_nodes.size == 1
      end

      unless return_type(symtab).convertable_to?(expected_return_type(symtab))
        type_error "Return type (#{return_type(symtab)}) not convertable to expected return type (#{expected_return_type(symtab)})"
      end
    end

    def enclosing_function
      find_ancestor(FunctionDefAst)
    end

    # @!macro return_value
    def return_value(symtab)
      if return_value_nodes.size == 1
        return_value_nodes[0].value(symtab)
      else
        return_value_nodes.map { |v| v.value(symtab) }
      end
    end

    # @!macro return_values
    def return_values(symtab)
      if return_value_nodes.size == 1
        return_value_nodes[0].values(symtab)
      else
        return_value_nodes.map { |v| v.values(symtab) }
      end
    end

    def to_idl = "return #{return_value_nodes.map(&:to_idl).join(',')}"
  end

  class ConditionalReturnStatementSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ConditionalReturnStatementAst.new(input, interval, return_expression.to_ast, expression.to_ast)
    end
  end

  class ConditionalReturnStatementAst < AstNode
    include Returns

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

    # @retrun [Type] The actual return type
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
      else
        nil
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

    def to_idl = "#{return_expression.to_idl} if (#{condition.to_idl});"
  end

  # @api private
  class CommentSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast = CommentAst(input, interval)
  end

  # represents a comment
  class CommentAst < AstNode
    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
    end

    # @!macro type_check
    def type_check(symtab); end

    # @return [String] The comment text, with the leading hash and any leading space removed
    # @example
    #    # This is a comment     #=> "This is a comment"
    def content = text_value[1..].strip
  end

  # @api private
  class BuiltinTypeNameSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      if !respond_to?(:i)
        BuiltinTypeNameAst.new(input, interval, elements[0].text_value, nil)
      else
        BuiltinTypeNameAst.new(input, interval, elements[0].text_value, i.to_ast)
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
        value_else(value_result) do
          type_error "Bit width must be known at compile time" if symtab.archdef.fully_configured?
        end
      end
      unless ["Bits", "String", "XReg", "Boolean", "U32", "U64"].include?(@type_name)
        type_error "Unimplemented builtin type #{text_value}"
      end
    end

    def freeze_tree(symtab)
      if @type_name == "Bits"
        # precalculate size if possible
        begin
          value_try do
            @bits_type = Type.new(:bits, width: bits_expression.value(symtab))
          end
        rescue TypeError
          # ok, probably in a function template
        end
        bits_expression.freeze_tree(symtab)
      end
      freeze
    end

    # @!macro type
    def type(symtab)
      case @type_name
      when "XReg"
        if symtab.mxlen == 32
          Bits32Type
        else
          Bits64Type
        end
      when "Boolean"
        BoolType
      when "U32"
        Bits32Type
      when "U64"
        Bits64Type
      when "String"
        StringType
      when "Bits"
        return @bits_type unless @bits_type.nil?

        value_result = value_try do
          return Type.new(:bits, width: bits_expression.value(symtab))
        end
        value_else(value_result) do
          return Type.new(:bits, width: :unknown)
        end
      else
        internal_error "TODO: #{text_value}"
      end
    end

    # @!macro to_idl
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

    def to_idl = text_value
  end

  module IntLiteralSyntaxNode
    def to_ast
      IntLiteralAst.new(input, interval)
    end
  end

  # represents an integer literal
  class IntLiteralAst < AstNode
    include Rvalue

    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @types = [nil, nil]
    end

    # @!macro type_check
    def type_check(symtab)
      if text_value.delete("_") =~ /^((XLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        value_text = ::Regexp.last_match(6)

        if width.nil? || width == "XLEN"
          width = symtab.mxlen
          memoize = false
        end

        # ensure we actually have enough bits to represent the value
        type_error("#{value_text} cannot be represented in #{width} bits") if unsigned_value.bit_length > width.to_i
      end
    end

    # @!macro type
    def type(symtab)
      cache_idx = symtab.mxlen >> 6 # 0 = 32, 1 = 64
      return @types[cache_idx] unless @types[cache_idx].nil?

      case text_value.delete("_")
      when /^((XLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        signed = ::Regexp.last_match(4)

        memoize = true
        if width.nil? || width == "XLEN"
          width = symtab.mxlen
          memoize = false
        end

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        t = Type.new(:bits, width: width.to_i, qualifiers:)
        @types[cache_idx] = t if memoize
        t
      when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
        # C++-style literal
        signed = ::Regexp.last_match(3)

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        type = Type.new(:bits, width: width(symtab), qualifiers:)
        @types[cache_idx] = type
        type
      when /^([0-9]*)(s?)$/
        # basic decimal
        signed = ::Regexp.last_match(2)

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        type = Type.new(:bits, width: width(symtab), qualifiers:)
        @types[cache_idx] = type
        type
      else
        internal_error "Unhandled int value"
      end
    end

    def width(symtab)
      # return @width unless @width.nil?

      text_value_no_underscores = text_value.delete("_")

      case text_value_no_underscores
      when /^((XLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        memoize = true
        if width.nil? || width == "XLEN"
          width = symtab.mxlen
          memoize = false
        end
        # @width = width if memoize
        width
      when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
        signed = ::Regexp.last_match(3)

        width = signed == "s" ? value(symtab).bit_length + 1 : value(symtab).bit_length
        width = 1 if width.zero? # happens when the literal is '0'

        # @width = width
        width
      when /^([0-9]*)(s?)$/
        signed = ::Regexp.last_match(3)

        width = signed == "s" ? value(symtab).bit_length + 1 : value(symtab).bit_length
        width = 1 if width.zero? # happens when the literal is '0'

        # @width = width
        width
      else
        internal_error "No match on int literal"
      end
    end

    # @!macro value
    def value(symtab)
      # return @value unless @value.nil?

      if text_value.delete("_") =~ /^((XLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        width = ::Regexp.last_match(1)
        signed = ::Regexp.last_match(4)

        memoize = true
        if width.nil? || width == "XLEN"
          width = symtab.mxlen
          memoize = false
        end

        v =
          if !signed.empty? && ((unsigned_value >> (width.to_i - 1)) == 1)
            -(2**width.to_i - unsigned_value)
          else
            unsigned_value
          end

        # @value = v if memoize
        v
      else
        # @value = unsigned_value
        unsigned_value
      end
    end


    # @return [Integer] the unsigned value of this literal (i.e., treating it as unsigned even if the signed specifier is present)
    def unsigned_value
      # return @unsigned_value unless @unsigned_value.nil?

      case text_value.delete("_")
      when /^((XLEN)|([0-9]+))?'(s?)([bodh]?)(.*)$/
        # verilog-style literal
        radix_id = ::Regexp.last_match(5)
        value = ::Regexp.last_match(6)

        radix_id = "d" if radix_id.empty?

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
      when /^0([bdx]?)([0-9a-fA-F]*)(s?)$/
        # C++-style literal
        radix_id = ::Regexp.last_match(1)
        value = ::Regexp.last_match(2)

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
        value = ::Regexp.last_match(1)

        # @unsigned_value = value.to_i(10)
        value.to_i(10)
      else
        internal_error "Unhandled int value '#{text_value}'"
      end
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  class FunctionCallExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      targs = t.empty? ? EMPTY_ARRAY : [t.targs.first.to_ast] + t.targs.rest.elements.map { |e| e.arg.to_ast }
      args = []
      args << function_arg_list.first.to_ast unless function_arg_list.first.empty?
      args += function_arg_list.rest.elements.map { |e| e.expression.to_ast }
      FunctionCallExpressionAst.new(input, interval, function_name.text_value, targs, args)
    end
  end

  class FunctionCallExpressionAst < AstNode
    # a function call can be both Lvalue (when void or return is ignored) and Rvalue
    include Rvalue
    include Executable

    def targs = children[0...@num_targs]
    def args = children[@num_targs..]

    def initialize(input, interval, function_name, targs, args)
      raise ArgumentError, "targs shoudl be an array" unless targs.is_a?(Array)
      raise ArgumentError, "args shoudl be an array" unless args.is_a?(Array)

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
          val = nil
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
      func_def_type = @func_def_type_cache[symtab.archdef]
      return func_def_type unless func_def_type.nil?

      func_def_type = symtab.get(@name)
      type_error "No symbol #{@name}" if func_def_type.nil?

      unless func_def_type.is_a?(FunctionType)
        type_error "#{@name} is not a function (it's a #{func_def_type.class.name})"
      end

      @func_def_type_cache[symtab.archdef] = func_def_type
    end

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels

      unknown_ok = symtab.archdef.partially_configured?
      tvals = template_values(symtab, unknown_ok:)

      func_def_type = func_type(symtab)

      type_error "Missing template arguments in call to #{@name}" if template? && func_def_type.template_names.empty?

      type_error "Template arguments provided in call to non-template function #{@name}" if !template? && !func_def_type.template_names.empty?

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

      if func_def_type.return_type(tvals, self).nil?
        internal_error "No type determined for function"
      end

      internal_error "Function call symtab not at same level post type check (#{symtab.levels} #{level})" unless symtab.levels == level
    end

    # @!macro type
    def type(symtab)
      return ConstBoolType if name == "implemented?"

      func_type(symtab).return_type(template_values(symtab, unknown_ok: symtab.archdef.partially_configured?), self)
    end

    # @!macro value
    def value(symtab)
      # sometimes we want to evaluate for a specific XLEN
      if name == "xlen" && !symtab.get("__effective_xlen").nil?
        return symtab.get("__effective_xlen").value
      end

      func_def_type = func_type(symtab)
      type_error "#{name} is not a function" unless func_def_type.is_a?(FunctionType)
      if func_def_type.builtin?
        if name == "implemented?"
          extname_ref = arg_nodes[0]
          type_error "First argument should be a ExtensionName" unless extname_ref.type(symtab).kind == :enum_ref && extname_ref.class_name == "ExtensionName"

          return symtab.archdef.ext?(arg_nodes[0].member_name) if symtab.archdef.fully_configured?

          if symtab.archdef.ext?(arg_nodes[0].member_name)
            # we can know if it is implemented, but not if it's not implemented for a partially configured
            return true
          end
          value_error "implemented? is only known when evaluating in the context of a fully-configured arch def"
        else
          value_error "value of builtin function cannot be known"
        end
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
    def to_idl
      if template?
        "#{name}<#{template_arg_nodes.map(&:to_idl).join(',')}>(#{arg_nodes.map(&:to_idl).join(',')})"
      else
        "#{name}(#{arg_nodes.map(&:to_idl).join(',')})"
      end
    end
  end


  class UserTypeNameSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      UserTypeNameAst.new(input, interval)
    end
  end

  class UserTypeNameAst < AstNode
    def initialize(input, interval)
      super(input, interval, EMPTY_ARRAY)
      @type_cache = {}
    end

    # @!macro type_check
    def type_check(symtab)
      type = type(symtab)

      type_error "#{text_value} is not a type" unless type.is_a?(Type)
    end

    # @!macro type_no_archdef
    def type(symtab)
      typ = @type_cache[symtab.archdef]
      return typ unless typ.nil?

      @type_cache[symtab.archdef] = symtab.get(text_value)
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  class InstructionOperationSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      FunctionBodyAst.new(input, interval, op_stmt_list.elements.map(&:choice).map(&:to_ast))
    end
  end

  class FunctionBodySyntaxNode < Treetop::Runtime::SyntaxNode
    # @!macro to_ast
    def to_ast
      FunctionBodyAst.new(input, interval, func_stmt_list.elements.map(&:choice).map(&:to_ast))
    end
  end

  class FunctionBodyAst < AstNode
    include Executable
    include Returns

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
        #     # if we reach here, the return value is known, so we don't have to go futher
        #     break
        #   else
        #     s.execute(symtab)
        #   end
        # rescue ValueError
        #   return_value_might_be_known = false
        # end
      end
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

    # @!macro return_values
    def return_values(symtab)
      internal_error "Function bodies should be at global + 1 scope" unless symtab.levels == 2

      values = []
      value_result = value_try do
        # if there is a definate return value, then just return that
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

    def to_idl
      result = ""
      # go through the statements, and return the first one that has a return value
      stmts.each do |s|
        result << s.to_idl
      end
      result
    end
  end

  class FunctionDefSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      FunctionDefAst.new(
        input,
        interval,
        function_name.text_value,
        targs.empty? ? [] : [targs.first.to_ast] + targs.rest.elements.map { |r| r.single_declaration.to_ast },
        ret.empty? ? [] : [ret.first.to_ast] + ret.rest.elements.map { |r| r.type_name.to_ast },
        args.empty? ? [] : [args.first.to_ast] + args.rest.elements.map { |r| r.single_declaration.to_ast},
        desc.text_value,
        respond_to?(:body_block) ? body_block.function_body.to_ast : nil
      )
    end
  end

  class FunctionDefAst < AstNode
    include Declaration

    # @param input [String] The source code
    # @param interval [Range] The range in the source code for this function definition
    # @param name [String] The name of the function
    # @param targs [Array<AstNode>] Template arguments
    # @params return_types [Array<AstNode>] Return types
    # @param arguments [Array<AstNode>] Arguments
    # @param desc [String] Description
    # @param body [AstNode,nil] Body, unless the function is builtin
    def initialize(input, interval, name, targs, return_types, arguments, desc, body)
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

      @cached_return_type = {}
      @reachable_functions_cache ||= {}
    end

    attr_reader :reachable_functions_cache

    # @!macro freeze_tree
    def freeze_tree(global_symtab)
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
      cached = @cached_return_type[symtab.archdef]
      return cached unless cached.nil?

      unless symtab.levels == 2
        internal_error "Function bodies should be at global + 1 scope (at global + #{symtab.levels - 1})"
      end

      if @return_type_nodes.empty?
        @cached_return_type[symtab.archdef] = VoidType
        return VoidType
      end

      unless templated?
        # with no templates, the return type does not change for a given arch_def
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

        return @cached_return_type[symtab.archdef] = rtype
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
    # may not exist in a given implmentation
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

    # @!macro type_check
    def type_check(symtab)
      internal_error "Functions must be declared at global scope (at #{symtab.levels})" unless symtab.levels == 1

      type_check_targs(symtab)

      symtab = symtab.deep_clone
      symtab.push(self)
      template_names.each_with_index do |tname, index|
        symtab.add(tname, Var.new(tname, template_types(symtab)[index]))
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

    # @return [Array<String>] Template arugment names, in order
    def template_names
      @targs.map(&:name)
    end

    # @param symtab [SymbolTable] The context for evaluation
    # @return [Array<Type>] Template argument types, in order
    def template_types(symtab)
      return EMPTY_ARRAY unless templated?

      ttypes = []
      @targs.each do |a|
        ttype = a.type(symtab)
        ttype = ttype.ref_type if ttype.kind == :enum
        ttypes << ttype.clone.make_const
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
      internal_error "Function has no body" if builtin?

      @body
    end

    def builtin?
      @body.nil?
    end
  end

  class ForLoopSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      ForLoopAst.new(
        input, interval,
        single_declaration_with_initialization.to_ast,
        condition.to_ast,
        action.to_ast,
        stmts.elements.map(&:s).map(&:to_ast)
      )
    end
  end

  class ForLoopAst < AstNode
    include Executable
    include Returns # a return statement in a for loop can make it return a value

    def init = @children[0]
    def condition = @children[1]
    def update = @children[2]
    def stmts = @children[3..]

    def initialize(input, interval, init, condition, update, stmts)
      super(input, interval, [init, condition, update] + stmts)
    end

    # @!macro type_check
    def type_check(symtab)
      symtab.push(self)
      init.type_check(symtab)
      condition.type_check(symtab)
      update.type_check(symtab)

      stmts.each do |s|
        s.type_check(symtab)
      end
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

    # @!macro return_values
    def return_values(symtab)
      value_result = value_try do
        # if there is a known return value, then we are done
        return [return_value(symtab)]
      end
      value_else(value_result) do
        # see if we can collect a list
        values = []
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

    # @!macro to_idl
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
      values = []
      symtab.push(self)
      begin
        value_result = value_try do
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
        end
      ensure
        symtab.pop
      end

      values.uniq
    end

    # @!macro execute
    def execute(symtab)
      err = nil
      stmts.each do |s|
        value_result = value_try do
          if s.is_a?(Returns)
            value_result = value_try do
              v = s.return_value(symtab)
              break unless v.nil? # nil means this is a conditional return and the condition is false

            end
            value_else(value_result) do
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
    def to_idl
      stmts.map(&:to_idl).join("")
    end

  end

  class ElseIfAst < AstNode
    include Returns

    def cond = @children[0]
    def body = @children[1]

    def initialize(input, interval, body_interval, cond, body_stmts)
      body = IfBodyAst.new(input, body_interval, body_stmts)
      super(input, interval, [cond, body])
    end

    def type_check(symtab)
      cond.type_check(symtab)

      cond_value = nil
      value_try do
        cond_value = cond.value(symtab)
      end

      unless cond.type(symtab).convertable_to?(:boolean)
        type_error "'#{cond.text_value}' is not boolean"
      end

      body.type_check(symtab) unless cond_value == false
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
    def to_idl
      " else if (#{cond.to_idl}) { #{body.to_idl} }"
    end
  end

  class IfSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      if_body_stmts = []
      if_body.elements.each do |e|
        if_body_stmts << e.e.to_ast
      end
      eifs = []
      unless elseifs.empty?
        elseifs.elements.each do |eif|
          stmts = []
          eif.body.elements.each do |e|
            stmts << e.e.to_ast
          end
          eifs << ElseIfAst.new(input, eif.interval, eif.body.interval, eif.expression.to_ast, stmts)
        end
      end
      final_else_stmts = []
      unless final_else.empty?
        final_else.body.elements.each do |e|
          final_else_stmts << e.e.to_ast
        end
      end
      if_body_ast = IfBodyAst.new(input, if_body.interval, if_body_stmts)
      final_else_ast =
        if final_else.empty?
          IfBodyAst.new(input, 0..0, final_else_stmts)
        else
          IfBodyAst.new(input, final_else.body.interval, final_else_stmts)
        end
      ast = IfAst.new(input, interval, if_cond.to_ast, if_body_ast, eifs, final_else_ast)
      ast
    end
  end

  class IfAst < AstNode
    include Executable
    include Returns

    def if_cond = @children[0]
    def if_body = @children[1]
    def elseifs = @children[2..-2]
    def final_else_body = @children.last

    def initialize(input, interval, if_cond, if_body, elseifs, final_else_body)
      children_nodes = [if_cond, if_body]
      children_nodes += elseifs
      children_nodes << final_else_body

      super(input, interval, children_nodes)
    end

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels
      if_cond.type_check(symtab)

      type_error "'#{if_cond.text_value}' is not boolean" unless if_cond.type(symtab).convertable_to?(:boolean)

      if_cond_value = nil
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

    # @!macro return_value
    def return_value(symtab)

      body = taken_body(symtab)
      return nil if body.nil?

      body.return_value(symtab)
    end
    alias execute return_value

    # return values starting at the first else if
    def return_values_after_if(symtab)
      values = []

      unless elseifs.empty?
        elseifs.each do |eif|
          values += eif.return_values(symtab)
          value_result = value_try do
            elseif_cond_value = eif.value(symtab)
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
      err = nil
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
      err = nil
      value_result = value_try do
        if_cond_value = if_cond.value(symtab)
        if if_cond_value
          # if is taken, so only the taken body is executable
          value_result = value_try do
            if_body.execute(symtab)
          end
          value_else(value_result) do
            err = :value_error if err.nil?
          end
        else
          execute_after_if(symtab)
        end
      end
      value_else(value_result) do
        # condition not known; both paths can execute
        value_result = value_try do
          if_body.execute(symtab)
        end
        value_else(value_result) do
          err = :value_error if err.nil?
        end

        value_result = value_try do
          execute_after_if(symtab)
        end
        value_else(value_result) do
          err = e if err.nil?
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

    def initialize(input, interval, idx, field_name)
      if idx.is_a?(AstNode)
        super(input, interval, [idx])
      else
        super(input, interval, EMPTY_ARRAY)
      end

      @idx = idx
      @field_name = field_name
    end

    def freeze_tree(symtab)
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
      if @idx.is_a?(IntLiteralAst)
        type_error "No CSR at address #{@idx.text_value}" if csr_def(symtab).nil?
      else
        # idx is a csr name
        csr_name = @idx
        type_error "No CSR named #{csr_name}" if csr_def(symtab).nil?
      end
      type_error "CSR[#{csr_name(symtab)}] has no field named #{@field_name}" if field_def(symtab).nil?
      type_error "CSR[#{csr_name(symtab)}].#{@field_name} is not defined in RV32" if symtab.archdef.mxlen == 32 && !field_def(symtab).defined_in_base32?
      type_error "CSR[#{csr_name(symtab)}].#{@field_name} is not defined in RV64" if symtab.archdef.mxlen == 64 && !field_def(symtab).defined_in_base64?
    end

    def csr_def(symtab)
      archdef = symtab.archdef

      if @idx.is_a?(IntLiteralAst)
        archdef.csrs.find { |c| c.address == @idx.value(symtab) }
      else
        archdef.csr(@idx)
      end
    end

    def csr_name(symtab)
      csr_def(symtab).name
    end

    def field_def(symtab)
      csr_def(symtab).fields.find { |f| f.name == @field_name }
    end

    def field_name(symtab)
      field_def(symtab).name
    end

    # @!macro to_idl
    def to_idl
      if @idx.is_a?(IntLiteralAst)
        "CSR[#{@idx.to_idl}].#{@field_name}"
      else
        "CSR[#{@idx}].#{@field_name}"
      end
    end

    # @!macro type
    def type(symtab)
      @type
    end

    def calc_type(symtab)
      fd = field_def(symtab)
      if fd.nil?
        if @idx.is_a?(IntLiteralAst)
          internal_error "Could not find CSR[#{@idx.to_idl}]"
        else
          internal_error "Could not find CSR[#{@idx}]"
        end
      end
      if fd.defined_in_all_bases?
        Type.new(:bits, width: symtab.archdef.possible_xlens.map{ |xlen| fd.width(symtab.archdef, xlen) }.max)
      elsif fd.base64_only?
        if symtab.archdef.possible_xlens.include?(64)
          Type.new(:bits, width: fd.width(symtab.archdef, 64))
        end
      elsif fd.base32_only?
        if symtab.archdef.possible_xlens.include?(32)
          Type.new(:bits, width: fd.width(symtab.archdef, 32))
        end
      else
        internal_error "unexpected field base"
      end
    end

    # @!macro value
    def value(symtab)
      if @value.nil?
        value_error "'#{csr_name(symtab)}.#{field_name(symtab)}' is not RO"
      else
        @value
      end
    end

    def calc_value(symtab)
      # field isn't implemented, so it must be zero
      return 0 if field_def(symtab).nil?

      unless field_def(symtab).type(symtab) == "RO"
        value_error "'#{csr_name(symtab)}.#{field_name(symtab)}' is not RO"
      end

      field_def(symtab).reset_value(symtab.archdef)
    end
  end

  class CsrReadExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      if idx.respond_to?(:to_ast)
        CsrReadExpressionAst.new(input, interval, idx.to_ast)
      else
        CsrReadExpressionAst.new(input, interval, idx.text_value)
      end
    end
  end

  class CsrFieldReadExpressionSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      if idx.respond_to?(:to_ast)
        CsrFieldReadExpressionAst.new(input, interval, idx.to_ast, csr_field_name.text_value)
      else
        CsrFieldReadExpressionAst.new(input, interval, idx.text_value, csr_field_name.text_value)
      end
    end
  end

  class CsrReadExpressionAst < AstNode
    include Rvalue

    def initialize(input, interval, idx)
      if idx.is_a?(AstNode)
        super(input, interval, [idx])
      else
        super(input, interval, EMPTY_ARRAY)
      end

      @idx = idx
    end

    # @!macro type
    def type(symtab)
      archdef = symtab.archdef

      cd = csr_def(symtab)
      if cd.nil?
        # we don't know anything about this index, so we can only
        # treat this as a generic
        if symtab.mxlen == 32
          Bits32Type
        else
          Bits64Type
        end
      else
        CsrType.new(cd, archdef)
      end
    end

    # @!macro type_check
    def type_check(symtab)
      archdef = symtab.archdef

      idx_text = @idx.is_a?(String) ? @idx : @idx.text_value
      if !archdef.csr(idx_text).nil?
        # this is a known csr name
        # nothing else to check

      else
        # this is an expression
        @idx.type_check(symtab)
        type_error "Csr index must be integral" unless @idx.type(symtab).integral?

        value_result = value_try do
          idx_value = @idx.value(symtab)
          csr_index = archdef.csrs.index { |csr| csr.address == idx_value }
          type_error "No csr number '#{idx_value}' was found" if csr_index.nil?
          :ok
        end
        # OK, index doesn't have to be known
      end
    end

    def csr_def(symtab)
      archdef = symtab.archdef
      idx_text = @idx.is_a?(String) ? @idx : @idx.text_value
      csr = archdef.csr(idx_text)
      if !csr.nil?
        # this is a known csr name
        csr
      else
        # this is an expression
        value_result = value_try do
          idx_value = @idx.value(symtab)
          return archdef.csrs.find { |csr| csr.address == idx_value }
        end
        # || we don't know at compile time which CSR this is...
        nil
      end
    end

    def csr_known?(symtab)
      !csr_def(symtab).nil?
    end

    def csr_name(symtab)
      internal_error "No CSR" unless csr_known?(symtab)

      csr_def(symtab).name
    end

    # @!macro value
    def value(symtab)
      cd = csr_def(symtab)
      value_error "CSR number not knowable" if cd.nil?
      if symtab.archdef.fully_configured?
        value_error "CSR is not implemented" unless symtab.archdef.implemented_csrs.any? { |icsr| icsr.name == cd.name }
      else
        value_error "CSR is not defined" unless symtab.archdef.csrs.any? { |icsr| icsr.name == cd.name }
      end
      cd.fields.each { |f| value_error "#{csr_name(symtab)}.#{f.name} not RO" unless f.type(symtab) == "RO" }

      csr_def(symtab).fields.reduce(0) { |val, f| val | (f.value << f.location.begin) }
    end

    # @!macro to_idl
    def to_idl = "CSR[#{@idx.to_idl}]"
  end

  class CsrSoftwareWriteSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      CsrSoftwareWriteAst.new(input, interval, csr.to_ast, expression.to_ast)
    end
  end

  class CsrSoftwareWriteAst < AstNode
    include Executable

    def csr = @children[0]
    def expression = @children[1]

    def initialize(input, interval, csr, expression)
      super(input, interval, [csr, expression])
    end

    def type_check(symtab)
      archdef = symtab.archdef

      csr.type_check(symtab)
      expression.type_check(symtab)

      return if expression.type(symtab).kind == :bits && expression.type(symtab).width == symtab.mxlen

      type_error "CSR value must be an XReg"
    end

    def csr_known?(symtab)
      csr.csr_known?(symtab)
    end

    def csr_name(symtab)
      csr.csr_name(symtab)
    end

    # @!macro value
    def value(_symtab)
      value_error "CSR writes are global"
    end

    # @!macro execute
    def execute(_symtab) = value_error "CSR writes are global"

    # @!macro execute_unknown
    def execute_unknown(_symtab); end

    # @!macro to_idl
    def to_idl = "#{csr.to_idl}.sw_write(#{expression.to_idl})"
  end

  # @api private
  class CsrFunctionCallSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast
      CsrFunctionCallAst.new(input, interval, function_name.text_value, csr.to_ast)
    end
  end

  # represents a function call for a CSR register
  # for example:
  #
  #   CSR[mstatus].address()
  #   CSR[mtval].sw_read()
  class CsrFunctionCallAst < AstNode
    include Rvalue

    # @return [String] The function being called
    attr_reader :function_name

    def csr = @children[0]

    def initialize(input, interval, function_name, csr)
      super(input, interval, [csr])
      @function_name = function_name
    end

    def type_check(symtab)
      unless ["sw_read", "address"].include?(function_name)
        type_error "'#{function_name}' is not a supported CSR function call"
      end

      csr.type_check(symtab)
    end

    def type(symtab)
      archdef = symtab.archdef

      case function_name
      when "sw_read"
        if csr_known?(symtab)
          Type.new(:bits, width: archdef.csr(csr.csr_name(symtab)).length(archdef))
        else
          Type.new(:bits, width: symtab.mxlen)
        end
      when "address"
        Type.new(:bits, width: 12)
      else
        internal_error "No function '#{function_name}' for CSR. call type check first!"
      end
    end

    def csr_known?(symtab)
      csr.csr_known?(symtab)
    end

    def csr_name(symtab)
      csr.csr_name(symtab)
    end

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
      else
        internal_error "TODO: #{function_name}"
      end
    end

    # @!macro to_idl
    def to_idl = "#{csr.to_idl}.#{function_call}()"
  end

  class CsrWriteSyntaxNode < Treetop::Runtime::SyntaxNode
    def to_ast = CsrWriteAst.new(input, interval, idx.to_ast)
  end

  class CsrWriteAst < AstNode
    include Executable

    def idx = @children[0]

    def initialize(input, interval, idx)
      super(input, interval, [idx])
    end

    # @!macro type_check
    def type_check(symtab)
      if idx.is_a?(IntLiteralAst)
        # make sure this value is a defined CSR
        index = symtab.archdef.csrs.index { |csr| csr.address == idx.value(symtab) }
        type_error "No csr number '#{idx.value(symtab)}' was found" if index.nil?
      else
        csr = symtab.archdef.csr(idx.text_value)
        type_error "No csr named '#{idx.text_value}' was found" if csr.nil?
      end
    end

    def csr_def(symtab)
      if idx.is_a?(IntLiteralAst)
        # make sure this value is a defined CSR
        symtab.archdef.csrs.find { |csr| csr.address == idx.text_value.to_i }
      else
        symtab.archdef.csr(idx.text_value)
      end
    end

    # @!macro type
    def type(symtab)
      CsrType.new(csr_def(symtab), symtab.archdef)
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
    def to_idl = "CSR[#{idx.text_value}]"
  end
end
