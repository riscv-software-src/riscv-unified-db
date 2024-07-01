# frozen_string_literal: false

require_relative "type"
require_relative "symbol_table"

require_relative "../opcodes"

module Treetop
  module Runtime
    # open up SyntaxNode to add utiilities that need to apply to all nodes (not just Asts)
    class SyntaxNode
      attr_reader :input_file

      # @return [Boolean] whether or not this node is part of a template function
      def has_template_ancestor?
        if parent.nil?
          nil
        elsif ["BitTypeAst", "FunctionCallTemplateArguments"].include?(parent_expression.node_class_name)
          true
        elsif parent_expression.node_class_name == "ParenExpressionAst"
          false # parens isolate the >, so we can allow at this point
        else
          parent.has_template_ancestor?
        end
      end

      # Fix up left recursion for the PEG
      #
      # This is the default for anything that isn't a left-recursive binary op
      #
      # Only left-recursive binary ops need to override this
      #
      # @note This may alter the SyntaxTree. You shouldn't use pointers within the
      #       tree from before a call to make_left
      # @return [SyntaxNode] A fixed syntax tree
      def make_left
        elements.nil? || elements.length.times do |i|
          elements[i] = elements[i].make_left
        end
        self
      end

      # remember where the code for this SyntaxNode comes from
      #
      # @param filename [String] Filename
      # @param starting_line [Integer] Starting line in the file
      def set_input_file(filename, starting_line = 0)
        @input_file = filename
        @starting_line = starting_line
        raise "?" if @starting_line.nil?
      end

      # @return [Integer] the current line number
      def lineno
        input[0..interval.first].count("\n") + 1 + (@starting_line.nil? ? 0 : @starting_line)
      end

      # @return [SyntaxNode,nil] the first ancestor that is_a?(klass), or nil if none is found
      def find_ancestor(klass)
        if parent.nil?
          nil
        elsif parent.is_a?(klass)
          parent
        else
          parent.find_ancestor(klass)
        end
      end

      # @return [SyntaxNode] A deep clone of the node
      def clone
        new_elements = nil
        unless terminal?
          new_elements = []
          elements.each do |child|
            new_elements << child.clone
          end
        end
        new_node = super
        new_node.instance_exec do
          @input = input
          @interval = interval
          @elements = new_elements
          @comprehensive_elements = nil
        end
        unless terminal?
          new_node.elements.each do |child|
            child.parent = new_node
          end
        end

        new_node
      end
    end
  end
end

module Idl
  # base class for all nodes considered part of the Ast
  # @abstract
  class AstNode < Treetop::Runtime::SyntaxNode
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
  end

  # functions added to all Ast nodes
  module AstNodeFuncs
    # raise a type error
    #
    # @param reason [String] Error message
    # @raise [Ast::TypeError] always
    def type_error(reason)
      e = AstNode::TypeError.new <<~WHAT
        In file #{input_file}
        On line #{lineno}
          A type error occured
          #{reason}
      WHAT
      raise e
    end

    # raise an internal error
    #
    # @param reason [String] Error message
    # @raise [Ast::TypeError] always
    def internal_error(reason)
      e = AstNode::InternalError.new <<~WHAT
        In file #{input_file}
        On line #{lineno}
          An internal error occured
          #{reason}
      WHAT
      raise e
    end

    # unindent a multiline string, getting rid of all common leading whitespace (like <<~ heredocs)
    #
    # borrowed from https://stackoverflow.com/questions/33527064/multiline-strings-with-no-indent
    #
    # @param s [String] A string (presumably with newlines)
    # @return [String] Unindented string
    def unindent(s)
      s.gsub(/^#{s.scan(/^[ \t]+(?=\S)/).min}/, "")
    end

    # @return [Array<AstNode>] list of children, or an empty array for a terminal
    def children
      if terminal?
        []
      else
        # child classes need to override this
        internal_error "Children function not implemented"
      end
    end

    def nodes_helper(elem)
      return unless elem.respond_to?(:elements) && !elem.elements.nil?

      elem.elements.each do |e2|
        if e2.is_a?(AstNode)
          @nodes << e2
        else
          nodes_helper(e2)
        end
      end
    end
    private :nodes_helper

    # @return [Array<AstNode>] an array of AST sub nodes
    #                          (notably, excludes anything, like whitespace, that wasn't subclassed to AST)
    def nodes
      return @nodes unless @nodes.nil?

      @nodes = []

      elements.each do |e|
        if e.is_a?(AstNode)
          @nodes << e
        else
          nodes_helper(e)
        end
      end

      @nodes
    end

    # pretty print the AST rooted at this node
    #
    # @param indent [Integer] The starting indentation, in # of spaces
    # @param indent_size [Integer] The extra indentation applied to each level of the tree
    # @param io [IO] Where to write the output
    def print_ast(indent = 0, indent_size: 2, io: $stdout)
      io.puts "#{' ' * indent}#{self.class.name}:"
      nodes.each do |node|
        node.print_ast(indent + indent_size, indent_size:)
      end
    end

    # @!macro [new] type_check
    #   type check this node and all children, and memoize any symtab- or archdef-dependent type
    #
    #   Calls to {#type}, {#constexpr?}, and/or {#value} may depend on type_check being called first
    #   with the same symtab and archdef. If not, those functions may raise an AstNode::InternalError
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @param archdef [ArchDef] Configured architecture definition
    #   @raise [AstNode::TypeError] if there is a type error
    #   @raise [AstNode::InternalError] if there is an internal compiler error during type check
    #   @return [void]

    # @!macro [new] type_check_no_archdef
    #   type check this node and all children, and memoize any symtab- or archdef-dependent type
    #
    #   Calls to {#type}, {#constexpr?}, and/or {#value} may depend on type_check being called first
    #   with the same symtab and archdef. If not, those functions may raise an AstNode::InternalError
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @param _archdef [ArchDef] Not used
    #   @raise [AstNode::TypeError] if there is a type error
    #   @raise [AstNode::InternalError] if there is an internal compiler error during type check
    #   @return [void]

    # @!macro type_check
    # @abstract
    def type_check(symtab, archdef) = raise NotImplementedError, "Subclass of AstNode must implement type_check"

    # @!macro [new] to_idl
    #   Return valid IDL representation of the node (and its subtree)
    #
    #   @return [String] IDL code for the node

    # @!macro to_idl
    # @abstract
    def to_idl = raise NotImplementedError, "#{self.class.name} must implement to_idl"
  end

  # reopen AstNode, and add functions
  class AstNode < Treetop::Runtime::SyntaxNode
    include AstNodeFuncs
  end

  # interface for statements
  module Statement
    # @!macro [new] update_value
    #   "execute" the statement by updating the variables in the symbol table
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @param archdef [ArchDef] Architecture defintion
    #   @return [void]

    # @!macro update_value
    def update_value(symtab, archdef) = raise NotImplementedError, "#{self.class.name} must implement update_value"
  end

  # interface for l-values (e.g., expressions)
  module Lvalue
    # @!macro [new] type
    #  Given a specific symbol table and arch def, return the type of this node.
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #  @param symtab [SymbolTable] Symbol table for lookup
    #  @param archdef [ArchDef] Configured architecture definition
    #  @return [Type] The type of the node
    #  @raise [AstNode::InternalError] if the type is dependent on symtab and/or archdef, and type_check was not called first

    # @!macro [new] type_no_archdef
    #  Given a specific symbol table, return the type of this node
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #  @param symtab [SymbolTable] Symbol table for lookup
    #  @param _archdef [ArchDef] Not used
    #  @return [Type] The type of the node
    #  @raise [AstNode::InternalError] if the type is dependent on symtab and/or archdef, and type_check was not called first

    # @!macro [new] type_no_args
    #  Return the type of this node
    #
    #  @param _symtab [SymbolTable] Not used
    #  @param _archdef [ArchDef] Not used
    #  @return [Type] The type of the node

    # @!macro type
    # @abstract
    def type(symtab, archdef) = internal_error "#{self.class.name} has no type"

    # @!macro [new] constexpr?
    #   Whether or not the *value* of this node can be determined at compile time, given
    #   a specific symbol table and architecture definition
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #  @param symtab [SymbolTable] Symbol table for lookup
    #  @param archdef [ArchDef] Configured architecture definition
    #  @return [Boolean] whether or not a value can be determined at compile time
    #  @raise [AstNode::InternalError] if the value is dependent on symtab and/or archdef, and type_check was not called first

    # @!macro [new] constexpr_no_archdef?
    #   Whether or not the *value* of this node can be determined at compile time, given
    #   a specific symbol table
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #  @param symtab [SymbolTable] Symbol table for lookup
    #  @param _archdef [ArchDef] Not used
    #  @return [Boolean] whether or not a value can be determined at compile time
    #  @raise [AstNode::InternalError] if the value is dependent on symtab and/or archdef, and type_check was not called first

    # @!macro [new] constexpr_no_args?
    #   Whether or not the *value* of this node can be determined at compile time
    #
    #  @param symtab [SymbolTable] Not used
    #  @param _archdef [ArchDef] Not used
    #  @return [Boolean] whether or not a value can be determined at compile time


    # @!macro constexpr?
    # @abstract
    def constexpr?(symtab, archdef) = false

    # @!macro [new] value
    #   Return the compile-time-known value of the node
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @param archdef [ArchDef] Configured architecture definition
    #   @return [Integer] if the compile-time-known value is an integer
    #   @return [Boolean] if the compile-time-known value is a boolean
    #   @raise [AstNode::InternalError] if the node is not constexpr
    #   @raise [AstNode::InternalError] if the value is dependent on symtab and/or archdef, and type_check was not called first

    # @!macro [new] value_no_archdef
    #   Return the compile-time-known value of the node
    #
    #  Should not be called until {#type_check} is called with the same arguments
    #
    #   @param symtab [SymbolTable] Symbol table for lookup
    #   @param _archdef [ArchDef] Not used
    #   @return [Integer] if the compile-time-known value is an integer
    #   @return [Boolean] if the compile-time-known value is a boolean
    #   @raise [AstNode::InternalError] if the node is not constexpr
    #   @raise [AstNode::InternalError] if the value is dependent on symtab and type_check was not called first

    # @!macro [new] value_no_args
    #   Return the compile-time-known value of the node
    #
    #   @param _symtab [SymbolTable] Not used
    #   @param _archdef [ArchDef] Not used
    #   @return [Integer] if the compile-time-known value is an integer
    #   @return [Boolean] if the compile-time-known value is a boolean
    #   @raise [AstNode::InternalError] if the node is not constexpr

    # @!macro value
    # @abstract
    def value(symtab, archdef) = internal_error "#{self.class.name} is not constexpr"  
  end

  # an ID
  class IdAst < AstNode
    include Lvalue

    # @!macro type_check_no_archdef
    def type_check(symtab, _archdef)
      type_error "no symbol named '#{text_value}' on line #{lineno}" if symtab.get(text_value).nil?
    end

    # @return [String] The ID name
    def name = text_value

    # @!macro type_no_archdef
    def type(symtab, _archdef)
      internal_error "Symbol not found (should have called type_check)" if symtab.get(text_value).nil?

      symtab.get(text_value).type
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef) = type(symtab, archdef).constexpr?

    # @!macro value_no_archdef
    def value(symtab, _archdef)
      internal_error "Id is not constexpr; no value" unless constexpr?(symtab, archdef)

      symtab.get(text_value).value
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  class GlobalWithInitializationAst < AstNode
    def type_check(syms, archdef)
      single_declaration_with_initialization.type_check(syms, archdef)
    end

    def type(syms, archdef)
      single_declartion_with_initialization.type(syms, archdef)
    end

    def value(syms, archdef)
      single_declartion_with_initialization.value(syms, archdef)
    end

    def to_idl
      "TODO"
    end
  end

  class GlobalAst < AstNode
    def type_check(syms, archdef)
      declaration.type_check(syms, archdef)
    end

    def type(syms, archdef)
      declaration.type
    end
  end

  # top-level AST node
  class IsaAst < AstNode
    def children
      enums + bitfields + functions + globals
    end

    def globals
      return @globals unless @globals.nil?

      @globals = []
      definitions.elements.each do |e|
        @globals << e if e.is_a?(GlobalWithInitializationAst) || e.is_a?(GlobalAst)
      end

      @globals
    end

    # return array of EnumAsts
    def enums
      return @enums unless @enums.nil?

      @enums = []
      definitions.elements.each do |e|
        @enums << e if e.is_a?(EnumDefinitionAst)
      end

      @enums
    end

    def bitfields
      return @bitfields unless @bitfields.nil?

      @bitfields = []
      definitions.elements.each do |e|
        @bitfields << e if e.is_a?(BitfieldDefinitionAst)
      end
      @bitfields
    end

    def functions
      return @functions unless @functions.nil?

      @functions = []
      definitions.elements.each do |e|
        @functions << e if e.is_a?(FunctionDefAst)
      end

      @functions
    end

    def type_check(syms, archdef)
      definitions.elements.each do |e|
        next unless e.is_a?(EnumDefinitionAst) || e.is_a?(BitfieldDefinitionAst) || e.is_a?(FunctionDefAst)

        e.type_check(syms, archdef)
        raise "level = #{syms.levels} #{e.name}" unless syms.levels == 1
      end
    end

    def instructions
      return @instructions unless @instructions.nil?

      @instructions = []
      definitions.elements.each do |e|
        @instructions << e if e.is_a?(InstructionDefinitionAst)
      end
      @instructions
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
    # @return [Array<String>] Array of all element names, in the same order as those from {#element_values}
    def element_names
      return @element_names unless @element_names.nil?

      @element_names = e.elements.map { |e| e.user_type_name.text_value }
    end

    # @return [Array<Integer>]
    #    Array of all element values, in the same order as those from {#element_names}.
    #    All values will be assigned their final values, even those with auto-numbers
    def element_values
      return @element_values unless @element_values.nil?

      next_auto_value = 0
      @element_values = []

      e.elements.each do |e|
        if e.i.empty?
          @element_values << next_auto_value
          next_auto_value += 1
        else
          @element_values << e.i.int.value(nil, nil)
          next_auto_value = element_values.last + 1
        end
      end

      @element_values
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      e.elements.each do |e|
        unless e.i.empty?
          e.i.int.type_check(symtab, archdef)
        end
      end

      et = EnumerationType.new(user_type_name.text_value, element_names, element_values)
      symtab.add!(et.name, et)
    end

    # @!macro type_no_args
    def type(_symtab, _archdef)
      EnumerationType.new(user_type_name.text_value, element_names, element_values)
    end

    # @!macro constexpr_no_args?
    def constexpr?(_symtab, _archdef) = false

    # @!macro value_no_args
    def value(_symtab, _archdef) = raise InternalError, "Enum defintions have no value"

    # @return [String] enum name
    def name = user_type_name.text_value

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

  # represents a builtin (auto-generated from config) enum definition
  #
  #   # this will result in a BuiltinEnumDefinitionAst
  #   builtin enum ExtensionName
  #
  class BuiltinEnumDefinitionAst < EnumDefinitionAst
    # @!macro type_check_no_args
    def type_check(_symtab, _archdef)
      unless user_type_name.text_value == "ExtensionName"
        type_error "Unsupported builtin enum type '#{user_type_name.text_value}'"
      end
    end

    # @!macro type_no_archdef
    def type(symtab, _archdef) = symtab.get(user_type_name.text_value)

    # @!macro to_idl
    def to_idl = "builtin enum #{user_type_name.text_value}"
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
    # @return [Array<String>] Array of all element names, in the same order as those from {#element_ranges}
    def element_names
      return @element_names unless @element_names.nil?

      @element_names = e.elements.map { |field| field.field_name.text_value }
    end

    # @return [Array<Range>]
    #    Array of all element ranges, in the same order as those from {#element_names}.
    def element_ranges
      return @element_ranges unless @element_ranges.nil?

      @element_ranges = []
      e.elements.each do |field|
        a = field.range.int.text_value.to_i

        b = field.range.lsb.empty? ? a : field.range.lsb.int.text_value.to_i

        @element_ranges << (a > b ? b..a : a..b)
      end
      @element_ranges
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      int.type_check(symtab, archdef)
      bf_size = int.text_value.to_i

      e.elements.each do |field|
        a = field.range.int.text_value.to_i
        type_error "Field position (#{a}) is larger than the bitfield width (#{bf_size})" if a >= bf_size

        b = field.range.lsb.empty? ? a : field.range.lsb.int.text_value.to_i
        type_error "Field position (#{b}) is larger than the bitfield width (#{bf_size})" if b >= bf_size
      end

      t = type(symtab, archdef)
      symtab.add!(name, t)
    end

    # @!macro type_no_args
    def type(symtab, archdef) = BitfieldType.new(name, int.value(symtab, archdef), element_names, element_ranges)

    # @return [String] bitfield name
    def name = user_type_name.text_value

    # @!macro constexpr_no_args?
    def constexpr?(_symtab, _archdef) = false

    # @!macro value_no_args
    def value(_symtab, _archdef) = raise AstNode::InternalError, "Bitfield defintions have no value"

    # @!macro to_idl
    def to_idl
      idl = "bitfield (#{bf_size}) #{name} { "
      element_names.each_index do |idx|
        idl << "#{element_names[idx]} #{element_ranges[idx].last}-#{element_ranges[idx].first} "
      end
      idl << "}"
      idl
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
  class AryAccess < Treetop::Runtime::SyntaxNode
    # fix up left recursion
    #
    # @return [AstNode] New tree rooted at the array access
    def make_left
      var = a.make_left
      interval_start = interval.begin
      brackets.elements.each do |bracket|
        var = if bracket.msb.empty?
                AryElementAccessAst.new(input, interval_start...bracket.interval.end, var, bracket.lsb.make_left)
              else
                AryRangeAccessAst.new(input, interval_start...bracket.interval.end, var,
                                      bracket.msb.expression.make_left, bracket.lsb.make_left)
              end
        interval_start = bracket.interval.end
      end
      internal_error "missing interval" unless var.interval.end == interval.end

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
    include Lvalue

    attr_reader :var, :index

    def initialize(input, interval, var, index)
      super(input, interval, [var, index])
      @var = var
      @index = index
    end

    # @!macro type_check
    def type_check(syms, archdef)
      @var.type_check(syms, archdef)
      @index.type_check(syms, archdef)

      type_error 'Array index must be integral' unless @index.type(syms, archdef).integral?

      if @var.type(syms, archdef).kind == :array
        if @index.constexpr?(syms, archdef)
          type_error 'Array index out of range' if @index.value(syms, archdef) >= @var.type(syms, archdef).width
        end

        if @var.text_value == 'X'
          index_var = syms.get(@index.text_value)
          if !@index.constexpr?(syms, archdef) && !index_var.decode_var?
            type_error 'X registers must be accessed with an index known at decode time'
          end
        end

        @type = @var.type(syms, archdef).sub_type
      elsif @var.type(syms, archdef).integral?
        if @var.type(syms, archdef).kind == :bits
          if @index.constexpr?(syms, archdef)
            type_error 'Bits element index out of range' if @index.value(syms, archdef) >= @var.type(syms, archdef).width
          end
          @type = Type.new(:bits, width: 1)
          @type.make_constexpr if @var.constexpr?(syms, archdef) && @index.constexpr?(syms, archdef)
        end
      else
        type_error 'Array element access can only be used with integral types and arrays'
      end
    end

    def type(syms, archdef)
      internal_error 'must call type_check' if @type.nil?

      @type
    end

    def value(syms, archdef)
      type_error 'array access is not constexpr' unless @var.type.constexpr? && @index.type.constexpr?

      if @var.type.integral?
        return (@var.value >> @index.value) & 1
      else
        internal_error 'TODO: constexpr array access'
      end
    end
  end

  class AryRangeAccessAst < AstNode
    include Lvalue

    attr_reader :var, :msb, :lsb

    def initialize(input, interval, var, msb, lsb)
      super(input, interval, [var, msb, lsb])
      @var = var
      @msb = msb
      @lsb = lsb
    end

    def type_check(syms, archdef)
      @var.type_check(syms, archdef)
      @msb.type_check(syms, archdef)
      @lsb.type_check(syms, archdef)

      type_error "Range operator only defined for integral types (found #{@var.type(syms, archdef)})" unless @var.type(syms, archdef).integral?

      type_error 'Range MSB must be an integral type' unless @msb.type(syms, archdef).integral?
      type_error 'Range LSB must be an integral type' unless @lsb.type(syms, archdef).integral?

      # could relax this later...
      type_error 'Range operator only defined for constexpr indicies' unless @msb.constexpr?(syms, archdef) && @lsb.constexpr?(syms, archdef)

      if @var.type(syms, archdef).kind == :bits
        type_error "Range too large for bits (range top = #{@msb.value(syms, archdef)}, range width = #{@var.type(syms, archdef).width})" if @msb.value(syms, archdef) >= @var.type(syms, archdef).width
      end
      range_size = @msb.value(syms, archdef) - @lsb.value(syms, archdef) + 1
      type_error "zero/negative range" if range_size <= 0

      @type = Type.new(:bits, width: range_size)
      @type.make_constexpr if @var.constexpr?(syms, archdef) && @msb.constexpr?(syms, archdef) && @lsb.constexpr?(syms, archdef)
    end

    def type(syms, archdef)
      internal_error 'must call type_check' if @type.nil?

      @type
    end

    def value(syms, archdef)
      type_error 'array access is not constexpr' unless @var.type.constexpr? && @msb.type.constexpr? && @lsb.type.constexpr?

      mask = (1 << (@msb.value - @lsb.value + 1)) - 1
      (@var.value >> @lsb.value) & mask
    end
  end

  # base class for all nodes representing an assignment
  # @abstract
  class AssignmentAst < AstNode
    # returns an LValAst
    def lhs
      internal_error "#{self.class} must implement lhs"
    end

    # Returns an RValAst
    def rhs
      internal_error "#{calss} must implement rhs"
    end
  end

  # represents a variable assignment statement
  #
  # for example, these will result in a VariableAssignmentAst
  #   X[rs1] = XLEN'b0
  #   CSR[mepc] = PC + 4
  class VariableAssignmentAst < AssignmentAst
    # @!macro type_check
    def type_check(symtab, archdef)
      var.type_check(symtab, archdef)
      rval.type_check(symtab, archdef)
      unless rval.type(symtab, archdef).convertable_to?(var.type(symtab, archdef))
        type_error "Incompatible type in assignment (#{var.type(symtab, archdef)}, #{rval.type(symtab, archdef)}) on line #{lineno}"
      end
      var.type(symtab, archdef).remove_constexpr
    end

    def lhs
      var
    end

    def rhs
      rval
    end

    def constexpr_compatible?(symtab, archdef) = var.constexpr?(symtab, archdef) && rval.constexpr?(symtab, archdef)

    # @!macro to_idl
    def to_idl = "#{var.to_idl} = #{rval.to_idl}"

  end

  # represents an array element assignement
  #
  # for example:
  #   X[rs1] = XLEN'd0
  class AryElementAssignmentAst < AssignmentAst
     # @!macro type_check
    def type_check(symtab, archdef)
      var.type_check(symtab, archdef)
      type_error "#{var.text_value} must be an array" unless var.type(symtab, archdef).kind == :array
      type_errpr "Assigning to a constant" if var.constexpr?(symtab, archdef)

      idx.type_check(symtab, archdef)

      type_error "Index must be integral" unless idx.type(symtab, archdef).integral?

      type_error "Array index out of range" if idx.constexpr?(symtab, archdef) && (idx.value(symtab, archdef) >= var.type(symtab, archdef).width)

      rval.type_check(symtab, archdef)

      type_error "Incompatible type in array assignment" unless rval.type(symtab, archdef).convertable_to?(var.type(symtab, archdef).sub_type)
    end

    def lhs
      internal_error "What's this used for?"
    end

    def rhs
      rval
    end

    def constexpr_compatible?(_symtab, _archdef) = false

    # @!macro to_idl
    def to_idl = "#{var.to_idl}[#{idx.to_idl}] = #{rval.to_idl}"
  end

  # represents a bitfield assignement or CSR field assignement
  #
  # for example:
  #   Sv39PageTableEntry entry;
  #   entry.PPN = 0
  #
  #   CSR[mstatus].SXL = 0
  class FieldAssignmentAst < AssignmentAst
    # @return [Symbol] either :bitfield or :csr
    def kind(symtab, archdef)
      var.type(symtab, archdef).kind
    end

    # @return [BitfieldType] Type of the bitfield being assigned
    # @raise [AstNode::InternalError] if this is not a bitfield assignment
    def bf_type(symtab, archdef)
      internal_error "Not a bitfield variable" unless kind(symtab, archdef) == :bitfield

      var.type(symtab, archdef)
    end

    # @return [CsrField] field being assigned
    # @raise [AstNode::InternalError] if this is not a CSR assignment
    def field(symtab, archdef)
      internal_error "Not a CSR field type" unless kind(symtab, archdef) == :csr
      var.type(symtab, archdef).csr.fields.select { |f| f.name == field_name.text_value }[0]
    end

    # @!macro type
    def type(symtab, archdef)
      case kind(symtab, archdef)
      when :bitfield
        Type.new(:bits, width: var.type(symtab, archdef).range(field_name.text_value).size)
      when :csr
        Type.new(:bits, width: field.location.size)
      else
        internal_error "Unhandled kind"
      end
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      var.type_check(symtab, archdef)

      type_error "Cannot write constexpr variable" if var.constexpr?(symtab, archdef)
      type_error "Cannot write const variable" if var.type(symtab, archdef).const?

      if var.type(symtab, archdef).kind == :bitfield
        unless var.type(symtab, archdef).field_names.include?(field_name.text_value)
          type_error "#{field_name.text_value} is not a member of #{var.type(symtab, archdef)} on line #{lineno}"
        end

      elsif var.type.kind == :csr
        fields = var.type.csr.fields.select { |f| f.name == field_name.text_value }
        type_error "#{field_name.text_value} is not a field of CSR #{rval.type(symtab, archdef).csr.name}" unless fields.size == 1

        type_error "Cannot write to read-only CSR field" if ["RO", "RO-H"].any?(field.type)
      else
        type_error "Field assignment on type that is not a bitfield or csr (#{var.type(symtab, archdef)})"
      end

      rval.type_check(symtab, archdef)
      return if rval.type(symtab, archdef).convertable_to?(@type)

      raise "Incompatible type in assignment (#{@type}, #{rval.type(symtab, archdef)}) on line #{lineno}"
    end

    def constexpr_compatible?(symtab, archdef) = rval.constexpr?(symtab, archdef) && var.constexpr?(symtab, archdef)

    # @!macro to_idl
    def to_idl = "#{var.to_idl}.#{field_name.to_idl} = #{rval.to_idl}"
  end

  # represents assignement of multiple variable from a function call that returns multiple values
  #
  # for example:
  #   (match_result, cfg) = pmp_match<access_size>(paddr);
  class MultiVariableAssignmentAst < AssignmentAst
    # @return [Array<AstNode>] The variables being assigned, in order
    def vars
      [first] + rest.elements.map(&:var)
    end

    def rhs
      function_call
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      function_call.type_check(symtab, archdef)
      vars.each { |var| var.type_check(symtab, archdef) }

      type_error "Assigning value to a constant" if vars.any? { |v| v.constexpr?(symtab, archdef) }

      type_error "Function '#{function_call.name}' has no return type" if function_call.type(symtab, archdef).nil?
      unless function_call.type(symtab, archdef).kind == :tuple
        type_error "Function '#{function_call.name}' only returns 1 variable on line #{lineno}"
      end

      if function_call.type(symtab, archdef).tuple_types.size != vars.size
        type_error "function '#{function_call.name}' returns #{function_call.type(symtab, archdef).tuple_types.size} arguments, but  #{vars.size} were specified"
      end

      function_call.type(symtab, archdef).tuple_types.each_index do |i|
        next if vars[i].is_a?(DontCareLvalueAst)
        raise "Implementation error" if vars[i].is_a?(DontCareReturnAst)

        var = symtab.get(vars[i].text_value)
        type_error "No symbol named '#{vars[i].text_value}' on line #{lineno}" if var.nil?

        internal_error "Cannot determine type of #{vars[i].text_value}" unless var.respond_to?(:type)

        unless var.type.convertable_to?(function_call.type(symtab, archdef).tuple_types[i])
          raise "'#{function_call.name}' expecting a #{function_call.type(symtab, archdef).tuple_types[i]} in argument #{i}, but was given #{var.type(symtab, archdef)} on line #{lineno}"
        end
      end
    end

    def constexpr_compatible?(symtab, archdef) = function_call.constexpr?(symtab, archdef) && vars.all? { |v| v.constexpr?(symtab, archdef) }

    # @!macro to_idl
    def to_idl = "(#{vars.map(&:to_idl).join(', ')}) = #{function_call.to_idl}"
  end

  # class MemoryWriteAst < AssignmentAst
  #   def lhs
  #     memory_write
  #   end

  #   def rhs
  #     expression
  #   end
  # end

  # class ConditionalVariableWriteAst < AssignmentAst
  #   def lhs
  #     var
  #   end

  #   def rhs
  #     expression
  #   end
  # end

  # represents the declaration of multiple variables
  #
  # for example:
  #   Bits<64> a, b;
  #   Bits<64> a, b, c, d;
  class MultiVariableDeclarationAst < AssignmentAst
    # @return [Array<String>] Variables being declared
    def var_names
      return @var_names unless @var_names.nil?

      @var_names = [first.text_value]
      rest.elements.each do |e|
        @var_names << e.var_write.text_value
      end

      @var_names
    end

    # @!macro type_check_no_archdef
    def type_check(symtab, _archdef)
      type_error "No type named '#{type_name.text_value}' on line #{lineno}" if type.nil?

      type_error "Attempt to write read-only/constant variable #{text_value}" if type.const? || type.constexpr?

      var_names.each do |vname|
        syms.add(vname, Var.new(vname, type.clone))
      end
    end

    def constexpr_compatible?(_symtab, _archdef) = true

    # @!macro to_idl
    def to_idl = "#{type.to_idl} #{var_names.map(&:to_idl).join(', ')}"
  end

  # represents a single variable declaration (without assignement)
  #
  # for example:
  #   Bits<64> doubleword
  #   Boolean has_property
  class VariableDeclarationAst < AstNode
    # @!macro type_check
    def type_check(symtab, archdef)
      decl_type = symtab.get(type_name.text_value)

      type_error "No type '#{type_name.text_value}' on line #{lineno}" if decl_type.nil?
      
      decl_type = Type.new(:enum_ref, enum_class: decl_type) if decl_type.kind == :enum

      decl_type = decl_type.clone.qualify(q.text_value.to_sym) unless q.empty?

      type_error "Constants must be initialized at declaration" if var_write.text_value == var_write.text_value.upcase

      unless ary_size.empty?
        ary_size.expression.type_check(symtab, archdef)
        type_error "Array size must be known at compile time" unless ary_size.expression.type.constexpr?

        ary_size = ary_size.expression.value
        decl_type = Type.new(:array, width: ary_size, sub_type: decl_type.clone)
      end
      symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type))

      var_write.type_check(symtab, archdef)
    end

    # don't want to deal with arrays, though we could...
    def constexpr_compatible?(_symtab, _archdef) = ary_size.empty?

    # @!macro to_idl
    def to_idl
      if ary_size.empty?
        "#{type.to_idl} #{var_write.to_idl}"
      else
        "#{type.to_idl} #{var_write.to_idl}[#{ary_size.expression.to_idl}]"
      end
    end
  end

  # reprents a single variable declaration with initialization
  #
  # for example:
  #   Bits<64> doubleword = 64'hdeadbeef
  #   Boolean has_property = true
  class VariableDeclarationWithInitializationAst < AssignmentAst
    def type_check(symtab, archdef)
      rval.type_check(symtab, archdef)

      type_name.type_check(symtab, archdef)

      decl_type = type_name.type(symtab, archdef).clone
      type_error "No type '#{type_name.text_value}' on line #{lineno}" if decl_type.nil?

      decl_type = Type.new(:enum_ref, enum_class: decl_type) if decl_type.kind == :enum
      decl_type.make_constexpr if rval.constexpr?(symtab, archdef)

      decl_type = decl_type.clone.qualify(q.text_value.to_sym) unless q.empty?

      unless ary_size.empty?
        ary_size.expression.type_check(symtab, archdef)
        type_error "Array size must be known at compile time" unless ary_size.expression.type.constexpr?

        decl_type = Type.new(:array, width: ary_size.expression.value, sub_type: decl_type)
        decl_type.remove_constexpr
      end

      if (var_write.text_value == var_write.text_value.upcase) && ary_size.empty?
        # this is a constant; ensure we are assigning a constant value
        type_error "Declaring constant with a non-constant value" unless rval.constexpr?(symtab, arch_def)
        decl_type.qualify(:constexpr)
        symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type.clone, rval.value(symtab, archdef)))
      else
        if rval.constexpr?(symtab, archdef)
          decl_type.qualify(:constexpr)
          symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type.clone, rval.value(symtab, archdef)))
        else
          symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type.clone))
        end
      end

      var_write.type_check(symtab, archdef)

      # now check that the assignment is compatible
      return if rval.type(symtab, archdef).convertable_to?(decl_type)

      type_error "Incompatible type (#{decl_type}, #{rval.type(symtab, archdef)}) in assignment"
    end

    def lhs
      return @lhs unless @lhs.nil?

      internal_error "unexpected" unless var_write.is_a?(VariableWriteAst)

      @lhs = var_write
    end

    def rhs
      # if rhs is nil, this is the non-initializing variant
      return nil unless respond_to?(:rval)

      return rval if rval.is_a?(Lvalue)

      internal_error "unexpected #{rval.inspect}" unless rval.is_a?(MemoryRValAst)

      rval
    end

    def constexpr_compatible?(symtab, archdef)
      rval.constexpr?(symtab, archdef) && ary_size.empty?
    end
  end

  class BinaryExpressionRightAst < AstNode
    include Lvalue

    def make_left
      first =
        BinaryExpressionAst.new(
          input, (interval.begin...r.elements[0].r.interval.end),
          l.make_left, r.elements[0].op, r.elements[0].r.make_left
        )

      if r.elements.size == 1
        first
      else
        r.elements[1, -1].inject(first) do |lhs, r|
          BinaryExpressionAst.new(input, (r.interval.begin...r.r.interval.end),
                                  lhs, r.op, r.r.make_left)
        end
      end
      first
    end

    def type_check(_syms, _archdef)
      raise "you must have forgotten the make_left pass"
    end
  end

  class SignCastAst < AstNode
    # @!macro type_check
    def type_check(syms, archdef)
      expression.type_check(syms, archdef)
    end

    # @!macro type
    def type(symtab, archdef) = expression.type(symtab, archdef).clone.make_signed

    # @!macro constexpr?
    def constexpr?(symtab, archdef) = expression.constexpr?(symtab, archdef)

    # @!macro value
    def value(symtab, archdef)
      t = expression.type(symtab, archdef)
      internal_error "Expecting a bits type" unless t.kind == :bits
      v = expression.value(symtab, archdef)

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

  
  class BitsCastAst < AstNode
    # @!macro type_check
    def type_check(symtab, archdef)
      expression.type_check(symtab, archdef)

      type_error "#{expression.type(symtab, archdef)} Cannot be cast to bits" unless [:bits, :enum_ref, :csr].include?(expression.type(symtab,archdef).kind)
    end

    # @!macro type
    def type(symtab, archdef)
      etype = expression.type(symtab, archdef)

      case etype.kind
      when :bits
        etype
      when :enum_ref
        Type.new(:bits, width: etype.enum_class.width)
      when :csr
        type_error "Cannot $bits cast CSR because its length is dynamic" if etype.csr.dynamic_length?
        Type.new(:bits, width: etype.csr.length)
      end
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef) = expression.constexpr?(symtab, archdef)

    # @!macro value
    def value(symtab, archdef)
      etype = expression.type(symtab, archdef)

      case etype.kind
      when :bits
        expression.value(symtab, archdef)
      when :enum_ref
        symtab.get(expression.text_value).value
      when :csr
        internal_error "TODO"
      end
    end

    # @!macro to_idl
    def to_idl = "$signed(#{expression.to_idl})"
  end

  class BinaryExpressionAst < AstNode
    include Lvalue

    LOGICAL_OPS = ["==", "!=", ">", "<", ">=", "<=", "&&", "||"].freeze
    BIT_OPS = ["&", "|", "^"].freeze
    ARITH_OPS = ["+", "-", "/", "*", "%", "<<", ">>", ">>>"].freeze
    OPS = (LOGICAL_OPS + ARITH_OPS + BIT_OPS).freeze

    # create a new, left-recursion-fixed, binary expression
    def initialize(input, interval, lhs, op, rhs)
      super(input, interval, [lhs, op, rhs])
      @lhs = lhs
      @op = op.text_value
      type_error "Bad op '#{@op}'" unless OPS.include?(@op)
      @rhs = rhs
    end

    # @return [BinaryExpressionAst] this expression, but with an inverted condition
    def invert(symtab, archdef)
      type_error "Not a boolean operator" unless type(symtab, archdef).kind == :boolean

      inverted_op_map = {
        "==" => "!=",
        "!=" => "==",
        ">" => "<=",
        "<" => ">=",
        "<=" => ">",
        ">=" => "<"
      }

      raise "TODO" unless inverted_op_map.key?(op)

      inverted_text = "#{lhs.to_idl} #{op} #{rhs.to_idl}"
      inverted_op_node = Treetop::Runtime::SyntaxNode.new(inverted_op_map[op], (0..inverted_op_map[op].size))
      BinaryExpressionAst.new(inverted_text, 0..(inverted_text.size - 1), lhs, inverted_op_node, rhs)
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
      "#{lhs.to_idl} #{op} #{rhs.to_idl}"
    end

    # @!macro type
    def type(symtab, archdef)
      qualifiers =
        if @lhs.type(symtab, archdef).constexpr? && @rhs.type(symtab, archdef).constexpr?
          [:constexpr]
        else
          []
        end

      if LOGICAL_OPS.include?(op)
        Type.new(:boolean, qualifiers:)
      elsif op == "<<"
        # if shift amount is constexpr, then the result width is increased by the shift
        # otherwise, the result is the width of the left hand side
        if @rhs.type(symtab, archdef).constexpr?
          Type.new(:bits, width: @lhs.type(symtab, archdef).width + @rhs.value(symtab, archdef), qualifiers:)
        else
          Type.new(:bits, width: @lhs.type(symtab, archdef).width, qualifiers:)
        end
      elsif ["+", "-", "*"].include?(op)
        qualifiers << :signed if @lhs.type(symtab, archdef).signed? || @rhs.type(symtab, archdef).signed?
        Type.new(:bits, width: [@lhs.type(symtab, archdef).width, @rhs.type(symtab, archdef).width].max, qualifiers:)
      else
        t = @lhs.type(symtab, archdef).clone
        # make sure we don't inherit constexpr from lhs when we shouldn't
        t.remove_constexpr unless @rhs.constexpr?(symtab, archdef)
        t
      end
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      internal_error "No type_check function #{@lhs.inspect}" unless @lhs.respond_to?(:type_check)

      @lhs.type_check(symtab, archdef)
      @rhs.type_check(symtab, archdef)

      if ["<=", ">=", "<", ">", "!=", "=="].include?(op)
        internal_error text_value if @rhs.type(symtab, archdef).nil?
        unless @rhs.type(symtab, archdef).comparable_to?(@lhs.type(symtab, archdef))
          type_error "#{@lhs.text_value} (type = #{@lhs.type(symtab, archdef)}) and #{@rhs.text_value} (type = #{@rhs.type(symtab, archdef)}) are not comparable on line #{lineno}"
        end

      elsif ["&&", "||"].include?(op)
        unless @lhs.type(symtab, archdef).convertable_to?(:boolean)
          type_error "left-hand side of #{op} needs to be boolean (is #{@lhs.type(symtab, archdef)}) on line #{lineno} (#{text_value})"
        end

        unless @rhs.type(symtab, archdef).convertable_to?(:boolean)
          type_error "right-hand side of #{op} needs to be boolean (is #{@rhs.type(symtab, archdef)}) on line #{lineno} (#{text_value})"
        end

      elsif op == "<<"
        type_error "Unsupported type for left shift: #{@lhs.type(symtab, archdef)}" unless @lhs.type(symtab, archdef).kind == :bits
        type_error "Unsupported shift for left shift: #{@rhs.type(symtab, archdef)}" unless @rhs.type(symtab, archdef).kind == :bits
      elsif op == ">>"
        type_error "Unsupported type for right shift: #{@lhs.type(symtab, archdef)}" unless @lhs.type(symtab, archdef).kind == :bits
        type_error "Unsupported shift for right shift: #{@rhs.type(symtab, archdef)}" unless @rhs.type(symtab, archdef).kind == :bits
      elsif op == "*"
        # TODO: this needs to be op-aware
        unless @lhs.type(symtab, archdef).integral? && @rhs.type(symtab, archdef).integral?
          type_error "Addition/subtraction is only defined for integral types"
        end

        # result is width of the largest operand
        unless [:bits, :xreg, :enum_ref].any?(@lhs.type(symtab, archdef).kind) && [:bits, :xreg, :enum_ref].any?(@rhs.type(symtab, archdef).kind)
          internal_error "Need to handle another integral type"
        end
      elsif ["+", "-"].include?(op)
        unless @lhs.type(symtab, archdef).integral? && @rhs.type(symtab, archdef).integral?
          type_error "Addition/subtraction is only defined for integral types"
        end

        # result is width of the largest operand
        unless [:bits, :xreg, :enum_ref].any?(@lhs.type(symtab, archdef).kind) && [:bits, :xreg, :enum_ref].any?(@rhs.type(symtab, archdef).kind)
          internal_error "Need to handle another integral type"
        end
      end
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      lhs.constexpr?(symtab, archdef) && rhs.constexpr?(symtab, archdef)
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Binary expression is not constexpr; no value" unless constexpr?(symtab, archdef)

      if op == "-"
        lhs.value(symtab, archdef) - rhs.value(symtab, archdef)
      elsif op == "*"
        lhs.value(symtab, archdef) * rhs.value(symtab, archdef)
      elsif op == "=="
        lhs.value(symtab, archdef) == rhs.value(symtab, archdef)
      elsif op == "/"
        lhs.value(symtab, archdef) / rhs.value(symtab, archdef)
      elsif op == "||"
        lhs.value(symtab, archdef) || rhs.value(symtab, archdef)
      elsif op == "+"
        lhs.value(symtab, archdef) + rhs.value(symtab, archdef)
      elsif op == "<"
        lhs.value(symtab, archdef) < rhs.value(symtab, archdef)
      else
        internal_error "Todo: Op #{op}"
      end
    end

    # returns left-hand side expression
    attr_reader :lhs

    # returns right-hand side expression
    attr_reader :rhs

    # returns the operator as a string
    attr_reader :op
  end

  # represents a parenthesized expression
  #
  # for example:
  #  (a + b)
  class ParenExpressionAst < AstNode
    include Lvalue

    def invert(symtab, archdef) = e.invert(symtab, archdef)

    # @!macro type_check
    def type_check(symtab, archdef) = e.type_check(symtab, archdef)

    # @!macro type
    def type(symtab, archdef) = e.type(symtab, archdef)

    # @!machro constexpr?
    def constexpr?(symtab, archdef) = e.constexpr?(symtab, archdef)

    # @!macro value
    def value(symtab, archdef) = e.value(symtab, archdef)

    # @!macro to_idl
    def to_idl = "(#{e.to_idl})"
  end

  class ArrayLiteralAst < AstNode
    def element_nodes
      [first] + rest.elements.map(&:expression)
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      element_nodes.each do |node|
        node.type_check(symtab, archdef)
      end

      unless element_nodes.all? { |e| e.type(symtab, archdef).equal_to?(element_nodes[0].type(symtab, archdef)) }
        type_error "Array elements must be identical"
      end
    end

    def type(symtab, archdef)
      qualifiers = constexpr?(symtab, archdef) ? [:constexpr] : []
      Type.new(:array, width: element_nodes.size, sub_type: element_nodes[0].type(symtab, archdef), qualifiers:)
    end

    def constexpr?(symtab, archdef)
      element_nodes.all? { |e| e.constexpr?(symtab, archdef) }
    end

    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      element_nodes.map { |e| e.value(symtab, archdef) }
    end

    def to_idl = "[#{element_nodes.map(&:to_idl).join(',')}]"
  end

  # represents a concatenation expression
  #
  # for example:
  #   {1'b0, 5'd3}
  class ConcatenationExpressionAst < AstNode
    include Lvalue

    # @!macro type_check
    def type_check(symtab, archdef)
      first.type_check(symtab, archdef)
      type_error "Concatenation only supports Bits<> types" unless first.type(symtab, archdef).kind == :bits

      type_error "Must concatenate at least two objects" if rest.elements.empty?

      rest.elements.each do |e|
        e.expression.type_check(symtab, archdef)
        type_error "Concatenation only supports Bits<> types" unless e.expression.type(symtab, archdef).kind == :bits

        internal_error "Negative width for element #{e.expression.text_value}" if e.expression.type(symtab, archdef).width <= 0
      end
    end

    # @!macro type
    def type(symtab, archdef)
      total_width = first.type(symtab, archdef).width

      rest.elements.each do |e|
        total_width += e.expression.type(symtab, archdef).width
      end

      t = Type.new(:bits, width: total_width)
      t.make_constexpr if constexpr?(symtab, archdef)
      t
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      first.constexpr?(symtab, archdef) && rest.elements.all? { |e| e.expression.constexpr?(symtab, archdef) }
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      result = first.value(symtab, archdef)
      total_width = first.type(symtab, archdef).width
      rest.elements.each do |e|
        result |= (e.expression.value(symtab, archdef) << total_width)
        total_width += e.expression.type(symtab, archdef).width
      end
      result
    end

    # @!macro to_idl
    def to_idl = "{#{first.to_idl},#{rest.elements.map { |e| e.expression.to_idl }.join(',')}}"
  end

  # represents a replication expression
  #
  # for example:
  #   {5{5'd3}}
  class ReplicationExpressionAst < AstNode
    include Lvalue

    # @!macro type_check
    def type_check(symtab, archdef)
      n.type_check(symtab, archdef)
      v.type_check(symtab, archdef)

      type_error "value of replication must be a Bits type" unless v.type(symtab, archdef).kind == :bits
      type_error "replication amount must be constexpr" unless n.constexpr?(symtab, archdef)
      type_error "replication amount must be positive (#{n.value(symtab, archdef)})" unless n.value(symtab, archdef) > 0
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      n.constexpr?(symtab, archdef) && v.constexpr?(symtab, archdef)
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      result = 0
      n.value(symtab, archdef).times do |i|
        result |= v.value(symtab, archdef) << (i * v.type(symtab, archdef).width)
      end
      result
    end

    # @!macro type
    def type(symtab, archdef)
      width = (n.value(symtab, archdef) * v.type(symtab, archdef).width)
      t = Type.new(:bits, width:)
      t.make_constexpr if constexpr?(symtab, archdef)
      t
    end

    # @!macro to_idl
    def to_idl = "{#{n.to_idl}{#{v.to_idl}}}"
  end

  # represents a post-decrement expression
  #
  # for example:
  #   i--
  class PostDecrementExpressionAst < AstNode
    include Lvalue

    def type_check(symtab, archdef)
      rval.type_check(symtab, archdef)
      var = symtab.get(rval.text_value)
      var.type.remove_constexpr
    end

    def type(symtab, archdef)
      rval.type(symtab, archdef)
    end

    def to_idl = "#{rval.to_idl}--"
  end

  # represents a post-increment expression
  #
  # for example:
  #   i++
  class PostIncrementExpressionAst < AstNode
    include Lvalue

    # @!macro type_check
    def type_check(symtab, archdef)
      rval.type_check(symtab, archdef)
      var = symtab.get(rval.text_value)
      var.type.remove_constexpr
    end

    # @!macro type
    def type(symtab, archdef)
      rval.type(symtab, archdef)
    end

    # @!macro to_idl
    def to_idl = "#{rval.to_idl}++"
  end

  # represents a bitfield or CSR field access (rvalue)
  #
  # for example:
  #   entry.PPN
  #   CSR[mstatus].SXL
  class BitfieldAccessExpressionAst < AstNode
    include Lvalue

    def kind(symtab, archdef)
      rval.type(symtab, archdef).kind
    end

    # @!macro type
    def type(symtab, archdef)
      rval_type = rval.type(symtab, archdef)

      qualifiers = constexpr?(symtab, archdef) ? [:constexpr] : []
      if rval_type.kind == :bitfield
        Type.new(:bits, width: rval.type(symtab, archdef).range(field_name.text_value).size, qualifiers:)
      elsif rval_type.kind == :enum_ref
        Type.new(:bits, width: rval_type.enum_class.width, qualifiers:)
      else
        internal_error "todo"
      end
    end

    def type_check(symtab, archdef)
      rval.type_check(symtab, archdef)

      rval_type = rval.type(symtab, archdef)

      if rval_type.kind == :bitfield
        internal_error "#{rval.text_value} Not a BitfieldType #{rval_type.class.name}" unless rval_type.respond_to?(:field_names)
        unless rval_type.field_names.include?(field_name.text_value)
          type_error "#{field_name.text_value} is not a member of #{rval_type}"
        end

      elsif rval_type.kind == :enum_ref
        type_error "#{field_name.text_value} is not an enum_ref function" unless field_name.text_value == 'value'
      elsif rval_type.kind == :csr
        raise "Shouldn't get here anymore"
        # fields = rval.type.csr.fields.select { |f| f.name == field_name.text_value }
        # raise "#{field_name.text_value} is not a field of CSR #{rval.type.csr.name}" unless fields.size == 1

        # @field = fields[0]

        # qualifiers = rval.type.qualifiers
        # qualifiers << :constexpr if @field.type == "RO"
        # qualifiers << :const if @field.type == "RO-H"

        # @kind = :csr
        # @type = Type.new(:bits, width: @field.location.size, qualifiers:)
      else
        type_error "#{rval.text_value} is not a bitfield or CSR (is #{rval.type(symtab, archdef)})"
      end
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      rval.constexpr?(symtab, archdef)
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      if kind(symtab, archdef) == :bitfield
        range = rval.type(symtab, archdef).range(field_name.text_value)
        (rval.value(symtab, archdef) >> range.first) & ((1 << range.size) - 1)
      elsif kind(symtab, archdef) == :enum_ref
        symtab.get(rval.text_value).value
      else
        raise "TODO"
      end
    end

    # @!macro to_idl
    def to_idl = "#{rval.to_idl}.#{field_name.to_idl}"
  end

  # represents an enum reference
  #
  # for example:
  #  ExtensionName::C
  #  PrivilegeMode::M
  class EnumRefAst < AstNode
    include Lvalue

    # @!macro type_check_no_archdef
    def type_check(symtab, _archdef)
      enum_def_type = symtab.get(enum_class.text_value)
      type_error "No symbol #{enum_class.text_value} has been defined" if enum_def_type.nil?

      type_error "#{enum_class.text_value} is not an enum type" unless enum_def_type.is_a?(EnumerationType)
    end

    # @!macro type_no_archdef
    def type(symtab, _archdef)
      internal_error "Must call type_check first" if symtab.get(enum_class.text_value).nil?

      Type.new(:enum_ref, enum_class: symtab.get(enum_class.text_value), qualifiers: [:constexpr])
    end

    # @!macro value_no_archdef
    def value(symtab, _archdef)
      internal_error "Must call type_check first" if symtab.get(enum_class.text_value).nil?

      symtab.get(enum_class.text_value).value(member.text_value)
    end

    # @!macro constexpr_no_args?
    def constexpr?(_symtab, _archdef) = true

    # @!macro to_idl
    def to_idl = "#{enum_class.to_idl}::#{member.to_idl}"
  end

  # represents a unary operator
  #
  # for example:
  #   -value
  #   ~value
  #   !bool_variable
  class UnaryOperatorExpressionAst < AstNode
    include Lvalue

    # @!macro type
    def type(symtab, archdef)
      case op
      when "-", "~"
        exp.type(symtab, archdef).clone
      when "!"
        Type.new(:boolean, qualifiers: exp.type(symtab, archdef).qualifiers.select { |q| [:const, :constexpr].any?(q) })
      else
        internal_error "unhandled op #{op}"
      end
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      exp.type_check(symtab, archdef)

      case op
      when "-"
        unless [:bits, :bitfield].include?(exp.type(symtab, archdef).kind)
          type_error "#{exp.type(symtab, archdef)} does not support unary #{op} operator"
        end

        type_error "Unary minus only works on signed values" unless exp.type(symtab, archdef).signed?
      when "~"
        unless [:bits, :bitfield].include?(exp.type(symtab, archdef).kind)
          type_error "#{exp.type(symtab, archdef)} does not support unary #{op} operator"
        end
      when "!"
        unless exp.type(symtab, archdef).convertable_to?(:boolean)
          type_error "#{exp.type(symtab, archdef)} does not support unary #{op} operator"
        end
      else
        internal_error "Unhandled op #{op}"
      end
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      eval("val = #{op}#{exp.value(symtab, archdef)}", binding, __FILE__, __LINE__)
      if type(symtab, archdef).width > val.bit_length
        # need to truncate
        val &= ((1 << type(symtab, archdef).width) - 1)
        if type(symtab, archdef).signed? && ((((val >> (type(symtab, archdef).width - 1))) & 1) == 1)
          # need to make this negative!
          # take the twos compliment
          val = -((1 << type(symtab, archdef).width) - val)
        end
      end

      val
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef) = e.constexpr?(symtab, archdef)

    # return the operated-on expression
    def exp
      e
    end

    # @return [String] The operator
    def op
      o.text_value
    end

    # @!macro to_idl
    def to_idl = "#{op}#{e.to_idl}"
  end

  # Represents a ternary operator
  #
  # for example:
  #   condition ? a : b
  #   (a < b) ? c : d
  class TernaryOperatorExpressionAst < AstNode
    include Lvalue

    # @!macro type_check
    def type_check(symtab, archdef)
      t.type_check(symtab, archdef)
      f.type_check(symtab, archdef)
      p9_binary_expression.type_check(symtab, archdef)

      type_error "ternary selector must be bool" unless p9_binary_expression.type(symtab, archdef).kind == :boolean
      unless t.type(symtab, archdef).equal_to?(f.type(symtab, archdef))
        type_error "True and false options must be same type (have #{t.type(symtab, archdef)} and #{f.type(symtab, archdef)})"
      end
    end

    # @!macro type
    def type(symtab, archdef)
      result_type = t.type(symtab, archdef)
      result_type.remove_constexpr
      result_type.make_constexpr if constexpr?(symtab, archdef)
      result_type
    end

    def condition
      p9_binary_expression
    end

    def true_expression
      t
    end

    def false_expression
      f
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      condition.value(symtab, archdef) ? t.value(symtab, archdef) : f.value(symtab, archdef)
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      if p9_binary_expression.constexpr?(symtab, archdef)
        if p9_binary_expression.value(symtab, archdef)
          t.constexpr?(symtab, archdef)
        else
          f.constexpr?(symtab, archdef)
        end
      else
       false
      end
    end

    # @!macro to_idl
    def to_idl = "#{condition.to_idl} ? #{true_expression.to_idl} : #{false_expression.to_idl}"
  end

  module VarReadExpressionAst
    include Lvalue

    # @!macro type_check_no_archdef
    def type_check(symtab, _archdef)
      var = symtab.get(text_value)

      type_error "No symbol named '#{text_value}'" if var.nil?

      type_error "'#{text_value}' is not a variable" unless var.is_a?(Var)
    end

    # @!macro type_no_archdef
    def type(symtab, _archdef)
      internal_error "Must call type_check first" if symtab.get(text_value).nil?

      symtab.get(text_value).type
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      type(symtab, archdef).constexpr?
    end

    # @!macro value_no_archdef
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      symtab.get(text_value).value
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  # represents a simple, one-line statement
  #
  # for example:
  #   Bits<64> new_variable;
  #   new_variable = 4;
  #   func();
  class StatementAst < AstNode
    def action = a

    # @!macro type_check
    def type_check(symtab, archdef)
      a.type_check(symtab, archdef)
    end

    def constexpr_compatible?(symtab, archdef) = action.constexpr_compatible?(symtab, archdef)

    def constexpr_returns?(symtab, archdef)
      false
    end

    def to_idl = "#{action.to_idl};"
  end

  # represents a predicated simple statement
  #
  # for example:
  #   a = 2 if condition;
  class ConditionalStatementAst < StatementAst
    # @!macro type_check
    def type_check(symtab, archdef)
      action.type_check(symtab, archdef)
      condition.type_check(symtab, archdef)
      type_error "condition is not boolean" unless condition.type(symtab, archdef).convertable_to?(:boolean)
    end

    def action = a

    def condition
      expression
    end

    def constexpr_compatible?(symtab, archdef) = condition.type(symtab, archdef).constexpr? && action.constexpr_compatible?(symtab, archdef)
  end

  # represents a don't care return value
  #
  # for exaple:
  #   return -;
  class DontCareReturnAst < AstNode
    include Lvalue

    # @!macro type_check_no_args
    def type_check(_symtab, archdef)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab, _archdef)
      Type.new(:dontcare, qualifiers: [:constexpr])
    end

    # @!macro constexpr_no_args?
    def constexpr?(_symtab, _archdef) = true

    # @!macro value_no_args
    def value(_symtab, _archdef)
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

  class DontCareLvalueAst < AstNode
    # @!macro type_check_no_args
    def type_check(_symtab, _archdef)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab, _archdef)
      Type.new(:dontcare)
    end

    # @!macro constexpr_no_args?
    def constexpr?(_symtab, _archdef) = true

    # @!macro value_no_args
    def value(_symtab, _archdef) = internal_error "Why are you calling value for an lval?"

    def to_idl = "-"
  end

  # represents a function return statement
  #
  # for example:
  #   return 5;
  #   return X[rs1] + 1;
  class ReturnStatementAst < AstNode
    # @return [Array<Type>] List of actual return types
    def return_types(symtab, archdef)
      if first.type(symtab, archdef).kind == :tuple
        first.type(symtab, archdef).tuple_types
      else
        rtypes = [first.type(symtab, archdef)]
        rest.elements.each do |e|
          rtypes << e.e.type(symtab, archdef)
        end
        rtypes
      end
    end

    # @retrun [Type] The actual return type
    def return_type(symtab, archdef)
      types = return_types(symtab, archdef)
      if types.size > 1
        Type.new(:tuple, tuple_types: types)
      else
        types[0]
      end
    end

    # @return [Type] The expected return type (as defined by the encolsing function)
    def expected_return_type(symtab, archdef)
      func_def = find_ancestor(FunctionDefAst)
      if func_def.nil?
        if symtab.get("__expected_return_type").nil?
          internal_error "Forgot to set __expected_return_type in the symbol table"
        end

        symtab.get("__expected_return_type")
      else
        func_def.return_type(symtab, archdef)
      end
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      first.type_check(symtab, archdef)
      type_error "Unknown type for first return argument #{first.class} #{first.text_value}" if first.type(symtab, archdef).nil?

      types = []
      if first.type(symtab, archdef).kind == :tuple
        type_error("Can't combine tuple types in return") unless rest.elements.empty?
        num_values = first.type(symtab, archdef).tuple_types.size
        types = first.type(symtab, archdef).tuple_types
      else
        types = [first.type(symtab, archdef)]
        rest.elements.each do |e|
          e.e.type_check(symtab, archdef)
          types << e.e.type(symtab, archdef)
        end
      end

      unless return_type(symtab, archdef).convertable_to?(expected_return_type(symtab, archdef))
        type_error "Return type (#{return_type(symtab, archdef)}) not convertable to expected return type (#{expected_return_type(symtab, archdef)})"
      end
    end

    # list of return value nodes
    def return_value_nodes
      v = [first]
      unless rest.empty?
        rest.elements.each do |e|
          v << e.e
        end
      end
      v
    end

    def enclosing_function
      find_ancestor(FunctionDefAst)
    end

    def constexpr_compatible?(symtab, archdef)
      return_value_nodes.all? { |v| v.constexpr?(symtab, archdef) }
    end

    def constexpr_returns?(symtab, archdef) = constexpr_compatible?(symtab, archdef)

    def return_value(symtab, archdef)
      internal_error "Not constexpr_returns?" unless constexpr_returns?(symtab, archdef)

      if return_value_nodes.size == 1
        return_value_nodes[0].value(symtab, archdef)
      else
        return_value_nodes.map { |v| v.value(symtab, archdef) }
      end
    end

    def update_value(symtab, archdef)
    end

    def to_idl = "return #{return_value_nodes.map(&:to_idl).join(',')};"
  end

  class ConditionalReturnStatementAst < ReturnStatementAst
    def condition
      expression
    end

    def constexpr_compatible?
      return false unless condition.type.constexpr?

      if condition.value == false
        true
      else
        values.all? { |v| v.type.constexpr? }
      end
    end

    def constexpr_returns?
      condition.type.constexpr? && condition.value && values.all? { |v| v.type.constexpr? }
    end
  end

  module BoolExpressionAst
  end

  class ExecutionCommentAst < AstNode
    def type_check(_syms, _global); end
  end

  class BitsTypeAst < AstNode
    # @!macro type_check
    def type_check(symtab, archdef)
      i.type_check(symtab, archdef)

      type_error "Bit width is not compile-time known" unless i.constexpr?(symtab, archdef)
      type_error "Bit widht must be integral" unless i.type(symtab, archdef).integral?
    end

    # @!macro type
    def type(symtab, archdef)
      Type.new(:bits, width: i.value(symtab, archdef).to_i)
    end

  end

  class BuiltinTypeNameAst < AstNode
    # @!macro type_check
    def type_check(_symtab, archdef)
      type_error "Unimplemented builtin type #{text_value}" unless ["XReg", "Boolean", "U32", "U64"].include?(text_value)
    end

    # @!macro type
    def type(_symtab, archdef)
      case text_value
      when "XReg"
        Type.new(:bits, width: archdef.config_params["XLEN"])
      when "Boolean"
        Type.new(:boolean)
      when "U32"
        Type.new(:bits, width: 32)
      when "U64"
        Type.new(:bits, width: 64)
      else
        internal_error "TODO: #{text_value}"
      end
    end
  end

  module IntAst
    include AstNodeFuncs
    include Lvalue

    # @!macro type_check
    def type_check(_syms, archdef)
      text_value_no_underscores = text_value.delete("_")
      if text_value_no_underscores =~ /([0-9]+)?'(s?)([bodh]?)(.*)/
        width = ::Regexp.last_match(1)
        signed = ::Regexp.last_match(2)
        radix_id = ::Regexp.last_match(3)
        value = ::Regexp.last_match(4)

        width = archdef.config_params["XLEN"] if width.nil?
        radix_id = "d" if radix_id.empty?

        # ensure we actually have enough bits to represent the value
        case radix_id
        when "b"
          @value = value.to_i(2)
          type_error("#{value} cannot be represented in #{width} bits") if @value.bit_length > width.to_i
        when "o"
          @value = value.to_i(8)
          type_error("#{value} cannot be represented in #{width} bits") if @value.bit_length > width.to_i
        when "d"
          @value = value.to_i(10)
          type_error("#{value} cannot be represented in #{width} bits") if @value.bit_length > width.to_i
        when "h"
          @value = value.to_i(16)
          type_error("#{value} cannot be represented in #{width} bits") if @value.bit_length > width.to_i
        end

        qualifiers = signed == "s" ? [:signed, :constexpr] : [:constexpr]
        @type = Type.new(:bits, width: width.to_i, qualifiers:)
      elsif text_value_no_underscores =~ /0([bdx]?)([0-9a-fA-F]*)(s?)/
        radix_id = ::Regexp.last_match(1)
        value = ::Regexp.last_match(2)
        signed = ::Regexp.last_match(3)

        radix_id = "o" if radix_id.empty?

        case radix_id
        when "b"
          @value = value.to_i(2)
        when "o"
          @value = value.to_i(8)
        when "d"
          @value = value.to_i(10)
        when "x"
          @value = value.to_i(16)
        end

        qualifiers = signed == "s" ? [:signed, :constexpr] : [:constexpr]
        width = signed == "s" ? @value.bit_length + 1 : @value.bit_length
        width = 1 if width.zero? # happens when the literal is '0'
        @type = Type.new(:bits, width:, qualifiers:)
      elsif text_value_no_underscores =~ /([0-9]*)(s?)/
        value = ::Regexp.last_match(1)
        signed = ::Regexp.last_match(2)

        @value = value.to_i(10)

        qualifiers = signed == "s" ? [:signed, :constexpr] : [:constexpr]
        width = signed == "s" ? @value.bit_length + 1 : @value.bit_length
        width = 1 if width.zero? # happens when the literal is '0'
        @type = Type.new(:bits, width:, qualifiers:)
      else
        internal_error "Unhandled int value"
      end
      type_error(text_value) if @value.nil?
    end

    # @!macro type
    def type(symtab, archdef)
      @type
    end

    # @!macro value
    def value(symtab, archdef)
      type_error("Did not type check #{text_value}") if @value.nil?

      @value
    end

    def constexpr?(symtab, archdef) = true

    # @!macro to_idl
    def to_idl = text_value
  end

  class FunctionCallExpressionAst < AstNode
    include Lvalue

    # @return [Boolean] whether or not the function call has a template argument
    def template?
      !t.empty?
    end

    # @return [Array<AstNode>] Template argument nodes
    def template_arg_nodes
      return [] unless template?

      [t.targs.first] + t.targs.rest.elements.map(&:arg)
    end

    def template_values(symtab, archdef)
      return [] unless template?

      template_arg_nodes.map { |e| e.value(symtab, archdef) }
    end

    # @return [Array<AstNode>] Function argument nodes
    def arg_nodes
      nodes = []
      nodes << function_arg_list.first unless function_arg_list.first.empty?
      nodes + function_arg_list.rest.elements.map(&:expression)
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      level = symtab.levels

      func_def_type = symtab.get(name)
      type_error "No symbol #{name}" if func_def_type.nil?

      unless func_def_type.is_a?(FunctionType)
        type_error "#{name} is not a function (it's a #{func_def_type.class.name})"
      end

      unless func_def_type.template_names.empty?
        type_error "Missing template parameters in call to #{name}" unless template?

        num_targs = template_arg_nodes.size
        if func_def_type.template_names.size != num_targs
          type_error "Wrong number of template arguments (expecting #{func_def_type.template_names.size}, got #{num_targs})"
        end

        template_arg_nodes.each_with_index do |t, idx|
          t.type_check(symtab, archdef)
          unless t.type(symtab, archdef).convertable_to?(func_def_type.template_types[idx])
            type_error "Template argument #{idx + 1} has wrong type"
          end
        end

        func_def_type.type_check_call(template_values(symtab, archdef))
      else
        type_error "#{name} is not a template function, but the call has template arguments" if template?
      end

      num_args = arg_nodes.size
      if func_def_type.num_args != num_args
        type_error "Wrong number of arguments to '#{name}' function call. Expecting #{func_def_type.num_args}, got #{num_args}"
      end
      arg_nodes.each_with_index do |a, idx|
        a.type_check(symtab, archdef)
        unless a.type(symtab, archdef).convertable_to?(func_def_type.argument_type(idx, template_values(symtab, archdef)))
          type_error "Wrong type for argument number #{idx + 1}. Expecting #{func_def_type.argument_type(idx, template_values(symtab, archdef))}, got #{a.type(symtab, archdef)}"
        end
      end

      internal_error "No type determined for function" if func_def_type.return_type(template_values(symtab, archdef)).nil?

      internal_error "Function call symtab not at same level post type check (#{symtab.levels} #{level})" unless symtab.levels == level
    end

    # @!macro type
    def type(symtab, archdef)
      func_def_type = symtab.get(name)
      t = func_def_type.return_type(template_values(symtab, archdef))
      t.qualify(:constexpr) if constexpr?(symtab, archdef)
      t
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      func_def_type = symtab.get(name)
      template_arg_nodes.all? { |targ| targ.constexpr?(symtab, archdef) } &&
        arg_nodes.all? { |arg| arg.constexpr?(symtab, archdef) } &&
        func_def_type.constexpr?(template_values(symtab, archdef))
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      symtab.push

      func_def_type = symtab.get(name)
      template_arg_nodes.each_with_index do |targ, idx|
        targ_name = func_def_type.template_names[idx]
        targ_type = func_def_type.template_types[idx]
        symtab.add!(targ_name, Var.new(targ_name, targ_type, targ.value(symtab, archdef)))
      end

      arg_nodes.each_with_index do |arg, idx|
        arg_name = func_def_type.argument_name(idx)
        arg_type = func_def_type.argument_type(idx)
        symtab.add!(arg_name, Var.new(arg_name, arg_type, arg.value(symtab, archdef)))
      end

      v = func_def_type.body.value(symtab, archdef)

      symtab.pop

      v
    end

    def name
      function_name.text_value
    end

  end

  # class ExecutionAst < AstNode
  #   def statement_text
  #     exec_stmt_list.elements.map { |e| e.choice.text_value }.join("\n")
  #   end
  # end

  class UserTypeNameAst < AstNode
    # @!macro type_check_no_archdef
    def type_check(symtab, _archdef)
      type = symtab.get(text_value)

      type_error "#{text_value} is not a type" unless type.is_a?(Type)
    end

    # @!macro type_no_archdef
    def type(symtab, _archdef)
      symtab.get(text_value)
    end
  end

  class FieldNameAst < AstNode
    # @!macro type_check_no_args
    def type_check(_symtab, _archdef)
      # nothing to do
    end
  end

  module FunctionStatementAst
    include AstNodeFuncs

    # true if the statement is constexpr
    def constexpr?
      internal_error "FunctionStatementAst type must implement constexpr?"
    end

    # true if the statement is constexpr *and* it returns from the function
    def constexpr_returns?(symtab, archdef) = raise NotImplementedError, "#{self.class.name} needs to implement constexpr_returns?"
  end

  class InstructionOperationAst < AstNode
    # @!macro type_check
    def type_check(symtab, archdef)
      op_stmt_list.elements.each do |e|
        e.choice.type_check(symtab, archdef)
      end
    end
  end

  class FunctionBodyAst < AstNode

    def statements
      func_stmt_list.elements.map(&:choice)
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      func_stmt_list.elements.each do |e|
        e.choice.type_check(symtab, archdef)
      end
    end

    # considered constexpr if everything on the path to a constexpr return is constexpr,
    # or if all statements are constexpr
    #
    # @param symtab [SymbolTable] symbol table to use
    # @param archdef [ArchDef] Architecture defintion
    # @return [Boolean] whether or not the function body is constexpr
    def constexpr?(symtab, archdef)
      # see if there is a short-circuit path to a constexpr return
      statements.each do |s|
        return true if s.constexpr_returns?(symtab, archdef)
        return false unless s.constexpr_compatible?(symtab, archdef)
      end

      # if we get here, we didn't return a constexpr, but everything along the way was idempotent
      true
    end

    def constexpr_returns?(symtab, archdef) = constexpr?(symtab, archdef)

    # @!macro value
    #
    # @note arguments and template arguments must be put on the symtab before calling
    def value(symtab, archdef)
      internal_error "Function body is not constexpr" unless constexpr?(symtab, archdef)

      # go through the statements, and return the first one that has a return value
      statements.each do |s|
        s.update_value(symtab, archdef) # update the symbol table with any constexpr updates
        return s.return_value(symtab, archdef) if s.constexpr_returns?(symtab, archdef)
      end

      internal_error "No function body statement returned a value"
    end

    def return_value(symtab, archdef) = value(symtab, archdef)

    def to_idl
      result = ""
      # go through the statements, and return the first one that has a return value
      statements.each do |s|
        result << s.to_idl
      end
      result
    end
  end

  class FunctionDefAst < AstNode
    def description
      unindent(desc.text_value)
    end

    def templated?
      !targs.empty?
    end

    def num_args
      return 0 if args.empty?

      1 + args.rest.elements.size
    end

    # @return [Array] containing the argument types, in order
    def arguments(symtab, archdef)
      if templated?
        template_names.each do |tname|
          internal_error "Template values missing" unless symtab.get(tname)
        end
      end

      arglist = []
      return arglist if args.empty?

      atype = args.first.type_name.type(symtab, archdef)
      atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum

      arglist << [atype, args.first.id.text_value]

      args.rest.elements.each do |a|
        atype = a.function_argument_definition.type_name.type(symtab, archdef)
        atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum

        arglist << [atype, a.function_argument_definition.id.text_value]
      end

      arglist
    end

    # returns an array of arguments, as a string
    # function (or template instance) does not need to be resolved
    def arguments_list_str
      list = []
      unless args.empty?
        list << args.first.text_value
        args.rest.elements.each do |e|
          list << e.function_argument_definition.text_value
        end
      end
      list
    end

    # return an array of all the return types, in order
    # function (or template instance) must be resolved
    def return_types(symtab, archdef)
      t = return_type(symtab, archdef)
      if t.kind == :tuple
        t.tuple_types
      elsif t.kind == :void
        []
      else
        [t]
      end
    end

    # return the return type, which may be a tuple of multiple types
    def return_type(symtab, archdef)
      if templated?
        template_names.each do |tname|
          internal_error "Template values missing" unless symtab.get(tname)
        end
      end

      if ret.empty?
        return Type.new(:void)
      end

      rtype = ret.first.type(symtab, archdef)
      rtype = Type.new(:enum_ref, enum_class: rtype) if rtype.kind == :enum

      if ret.rest.empty?
        return rtype
      end

      tuple_types = [rtype]
      ret.rest.elements.each do |r|
        rtype = symtab.get(r.type_name.text_value)
        rtype = Type.new(:enum_ref, enum_class: rtype) if rtype.kind == :enum

        tuple_types << rtype
      end

      Type.new(:tuple, tuple_types:)
    end

    # return an array of return type strings
    # function (or template instance) does not need to be resolved
    def return_type_list_str
      list = []
      if ret.empty?
        list << "void"
      else
        list << ret.first.text_value
        ret.rest.elements.each do |e|
          list << e.type_name.text_value
        end
      end
      list
    end

    def name
      function_name.text_value
    end

    # @param [Array<Integer>] template values to apply
    def type_check_template_instance(symtab, archdef)
      internal_error "Not a template function" unless templated?

      template_names.each do |tname|
        internal_error "Template values missing" unless symtab.get(tname)
      end

      type_check_return(symtab, archdef)
      type_check_args(symtab, archdef)
      type_check_body(symtab, archdef)
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      internal_error "Functions must be declared at global scope (at #{symtab.levels})" unless symtab.levels == 1

      type_check_targs(symtab, archdef)

      if templated?
        # because a return type or arg type can depend on a tepmlate value,
        # we can't type check anything else with an unresolved template arg
        #
        # For template functions, these type checks are deferred until the call site
      else
        symtab.push # push function scope
        type_check_return(symtab, archdef)
        type_check_args(symtab, archdef)
        type_check_body(symtab, archdef)
        symtab.pop
      end


      # now add the function in global scope
      def_type = FunctionType.new(
          name,
          self,
          symtab.clone,
          archdef
        )

      # recursion isn't supported (doesn't map well to hardware), so we can add the function after type checking the body
      symtab.add!(name, def_type)
    end

    attr_reader :template_names
    attr_reader :template_types
    def type_check_targs(symtab, archdef)
      @template_names = []
      @template_types = []
      return unless templated?

      targs.first.type_name.type_check(symtab, archdef)
      ttype = targs.first.type_name.type(symtab, archdef)
      type_error "No type '#{targs.first.type_name.text_value}' on line #{lineno}" if ttype.nil?

      ttype = Type.new(:enum_ref, enum_class: ttype) if ttype.kind == :enum

      @template_names << targs.first.id.text_value
      @template_types << ttype.clone.qualify(:constexpr)

      targs.rest.elements.each do |a|
        a.function_argument_definition.type_name.type_check(symtab, archdef)
        ttype = a.function_argument_definition.type_name.type(symtab, archdef)
        if ttype.nil?
          internal_error "No type '#{a.function_argument_definition.type_name.text_value}"
        end
        ttype = Type.new(:enum_ref, enum_class: ttype) if ttype.kind == :enum

        @template_names << a.function_argument_definition.id.text_value
        @template_types << ttype.clone.qualify(:constexpr)
      end
    end

    def type_check_return(symtab, archdef)
      return if ret.empty?

      ret.first.type_check(symtab, archdef)
      rtype = ret.first.type(symtab, archdef)
      type_error "No type '#{ret.first.text_value}" if rtype.nil?

      return if ret.rest.empty?

      ret.rest.elements.each do |r|
        r.type_name.type_check(symtab, archdef)
        rtype = symtab.get(r.type_name.text_value)

        type_error "No type '#{r.type_name.text_value}" if rtype.nil?
      end
    end

    def type_check_args(symtab, archdef)
      @arguments = []
      return if args.empty?

      args.first.type_name.type_check(symtab, archdef)

      atype = args.first.type_name.type(symtab, archdef)
      type_error "No type '#{args.first.type_name.text_value}" if atype.nil?
      atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum
      begin
        symtab.add!(args.first.id.text_value, Var.new(args.first.id.text_value, atype))
      rescue SymbolTable::DuplicateSymError => e
        type_error "#{e} "
      end

      args.rest.elements.each do |a|
        a.function_argument_definition.type_name.type_check(symtab, archdef)
        atype = a.function_argument_definition.type_name.type(symtab, archdef)
        type_error "No type '#{a.function_argument_definition.type_name.text_value}" if atype.nil?
        atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum
        symtab.add!(a.function_argument_definition.id.text_value, Var.new(a.function_argument_definition.id.text_value, atype))
      end
    end

    def type_check_body(symtab, archdef)

      if respond_to?(:body_block)
        body_block.function_body.type_check(symtab, archdef)
      end

      # now find all the return don't cares, and let them know what the expected
      # return type is
      # find_returns_from(self)
    end

    # def find_returns_from(node)
    #   if node.is_a?(ReturnStatementAst)
    #     node.values.each_index do |i|
    #       node.values[i].set_expected_type(@current_type.return_types[i]) if node.values[i].is_a?(DontCareReturnAst)
    #     end
    #   elsif !node.terminal?
    #     node.elements.each { |e| find_returns_from(e) }
    #   end
    # end

    def builtin?
      !respond_to?(:body_block)
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      # conservativelly assume builtin functions are not constexpr
      return false if builtin?

      # constexpr void doesn't even make sense...
      return false if return_type(symtab, archdef).kind == :void

      body_block.function_body.constexpr?(symtab, archdef)
    end

  end

  class ForLoopAst < AstNode
    # @!macro type_check
    def type_check(symtab, archdef)
      symtab.push
      single_declaration_with_initialization.type_check(symtab, archdef)
      condition.type_check(symtab, archdef)
      action.type_check(symtab, archdef)

      stmts.elements.each do |s|
        s.s.type_check(symtab, archdef)
      end
      symtab.pop
    end

    def constexpr_compatible?(symtab, archdef)
      syms.push

      compat = single_declaration_with_initialization.constexpr_compatible?(symtab, archdef)

      unless compat
        syms.pop
        return false
      end

      single_declaration_with_initialization.update_value(symtab, archdef)

      compat = condition.constexpr?(symtab, archdef)
      found_return = false
      while compat && condition.value(symtab, archdef)
        stmts.elements.each do |s|
          compat = s.s.constexpr_compatible?(symtab, archdef)
          break unless compat
          s.s.update_value(symtab, archdef)
          found_return = s.s.contexpr_return?(symtab, archdef)
          break if found_return
        end
        break if !compat || found_return
        compat = action.constexpr_compatible?(symtab, archdef)
        break unless compat
        action.update_value(symtab, archdef)
      end

      syms.pop
      compat
    end

    def constexpr_return?(symtab, archdef)
      return false unless constexpr_compatible?(symtab, archdef)

      syms.push

      single_declaration_with_initialization.update_value(symtab, archdef)

      while condition.value(symtab, archdef)
        stmts.elements.each do |s|
          s.s.update_value(symtab, archdef)
          if s.s.contexpr_return?(symtab, archdef)
            symtab.pop
            return true
          end
        end
        action.update_value(symtab, archdef)
      end

      syms.pop
      return false
    end

    def return_value(symtab, archdef)
      internal_error "Not constexpr_return" unless constexpr_return?(symtab, archdef)

      syms.push

      single_declaration_with_initialization.update_value(symtab, archdef)

      while condition.value(symtab, archdef)
        stmts.elements.each do |s|
          s.s.update_value(symtab, archdef)
          if s.s.contexpr_return?(symtab, archdef)
            v = s.s.return_value(symtab, archdef)
            symtab.pop
            return v
          end
        end
        action.update_value(symtab, archdef)
      end

      internal_error "Didn't find return?"
    end

    def update_value(symtab, archdef)
      internal_error "Not constexpr_compatible" unless constexpr_compatible?(symtab, archdef)

      syms.push

      single_declaration_with_initialization.update_value(symtab, archdef)
      found_return = false
      while condition.value(symtab, archdef)
        stmts.elements.each do |s|
          s.s.update_value(symtab, archdef)
          found_return = s.s.constexpr_return?(symtab, archdef)
          break if found_return
        end
        break if found_return
        action.update_value(symtab, archdef)
      end

      syms.pop
    end
  end

  class IfAst < AstNode
    include Statement

    # @!macro type_check
    def type_check(symtab, archdef)
      level = symtab.levels
      if_cond.type_check(symtab, archdef)

      type_error "'#{if_cond.text_value}' is not boolean" unless if_cond.type(symtab, archdef).convertable_to?(:boolean)

      symtab.push

      if_body.elements.each do |e|
        e.e.type_check(symtab, archdef)
      end

      symtab.pop

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      unless elseifs.empty?
        elseifs.elements.each do |eif|
          eif.expression.type_check(symtab, archdef)
          unless eif.expression.type(symtab, archdef).convertable_to?(:boolean)
            type_error "'#{eif.expression.text_value}' is not boolean"
          end

          symtab.push
          eif.body.elements.each do |e|
            e.e.type_check(symtab, archdef)
          end
          symtab.pop
        end
      end

      return if final_else.empty?

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      symtab.push
      final_else.body.elements.each do |e|
        e.e.type_check(symtab, archdef)
      end
      symtab.pop

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels
    end

    # @return [Boolean] true if the taken path is knowable at compile-time
    def constexpr_cond?(symtab, archdef)
      # constexpr here includes short-circuiting
      return true if if_cond.constexpr?(symtab, archdef) && if_cond.value(symtab, archdef)

      unless elseifs.empty?
        elseifs.elements.each do |eif|
          return true if eif.expression.constexpr?(symtab, archdef) && eif.expression.value(symtab, archdef)
        end
      end

      # else is constexpr if everything else was
      if_cond.constexpr?(symtab, archdef) && (elseifs.empty? || elseifs.all? { |eif| eifconstexpr?(symtab, archdef) })
    end

    # @return [Boolean] true if the taken path is knowable at compile-time
    def taken_body(symtab, archdef)
      internal_error "Not constexpr_cond" unless constexpr_cond?(symtab, archdef)

      # constexpr here includes short-circuiting
      return if_body if if_cond.constexpr?(symtab, archdef) && if_cond.value(symtab, archdef)

      unless elseifs.empty?
        elseifs.each do |eif|
          return eif.body if eif.expression.constexpr?(symtab, archdef) && eif.expression.value(symtab, archdef)
        end
      end

      # else is constexpr if everything else was
      final_else.body
    end

    # @return [Boolean] true if the taken path is knowable at compile-time *and* the taken body is all constexpr
    def constexpr_compatible?(symtab, archdef)
      return false unless constexpr_cond?(symtab, archdef)

      body = taken_body(symtab, archdef)
      symtab.push
      body.elements.each do |e|
        if e.e.constexpr_returns?(symtab, archdef)
          symtab.pop
          return true
        end
        unless e.e.constexpr_compatible?(symtab, archdef)
          symtab.pop
          return false
        end
      end
      symtab.pop

      # if we get here, everything was constexpr_compatible
      true
    end

    def update_value(symtab, archdef)
      internal_error "Not contexpr_compatible" unless constexpr_compatible?(symtab, archdef)
    end

    def constexpr_returns?(symtab, archdef)
      return false unless constexpr_cond?(symtab, archdef)

      body = taken_body(symtab, archdef)
      symtab.push
      body.elements.each do |e|
        if e.e.constexpr_returns?(symtab, archdef)
          symtab.pop
          return true
        end
        unless e.e.constexpr_compatible?(symtab, archdef)
          symtab.pop
          return false
        end
      end

      # if we get here, didn't find a constexpr returns
      false
    end

    def return_value(symtab, archdef)
      internal_error "Not constexpr returns" unless constexpr_returns?(symtab, archdef)

      body = taken_body(symtab, archdef)
      symtab.push
      body.elements.each do |e|
        e.e.update_value(symtab, archdef)
        if e.e.constexpr_returns?(symtab, archdef)
          v = e.e.return_value(symtab, archdef)
          symtab.pop
          return v
        end
      end

      internal_error "No return value found?"
    end

    def to_idl
      result = "if (#{if_cond.to_idl}) { "
      if_body.elements.each do |e|
        result << e.e.to_idl
      end
      result << "} "
      elseifs.elements.each do |eif|
        result << " else if (#{eif.expression.to_idl}) { "
        eif.body.elements.each do |e|
          result << e.e.to_idl
        end
        result << "} "
      end
      unless final_else.empty?
        result << " else { "
        final_else.body.elements.each do |e|
          result << e.e.to_idl
        end
        result << "} "
      end
    end
  end

  class CsrFieldReadExpressionAst < AstNode
    include Lvalue

    # @!macro type_check
    def type_check(symtab, archdef)
      if idx.is_a?(IntAst)
        # make sure this value is a defined CSR
        type_error "No CSR at address #{idx.text_value}" unless archdef.csrs.index do |c|
                                                             c.address == idx.value(symtab, archdef)
                                                           end.nil?

        csr = archdef.csrs.find { |c| c.address == idx.value(symtab, archdef) }
        type_error "CSR[#{csr_name}] has no field named #{csr_field_name.text_value}" if csr.fields.index do |f|
                                                                                      f.name == csr_field_name.text_value
                                                                                    end.nil?
      else
        # idx is a csr name
        csr_name = idx.text_value
        type_error "no CSR named #{csr_name}" if archdef.csrs.index { |c| c.name == csr_name }.nil?

        csr = archdef.csrs.find { |c| c.name == csr_name }
        type_error "CSR[#{csr_name}] has no field named #{csr_field_name.text_value} on line #{lineno}" if csr.fields.index do |f|
                                                                                                        f.name == csr_field_name.text_value
                                                                                                      end.nil?
      end
    end

    def csr_def(symtab, archdef)
      if idx.is_a?(IntAst)
        archdef.csrs.find { |c| c.address == idx.value(symtab, archdef) }
      else
        archdef.csrs.find { |c| c.name == idx.text_value }
      end
    end

    def csr_name(symtab, archdef)
      csr_def(symtab, archdef).name
    end

    def field_def(symtab, archdef)
      csr_def(symtab, archdef).fields.find { |f| f.name == csr_field_name.text_value }
    end

    def field_name(symtab, archdef)
      field_def(symtab, archdef).name
    end

    # @!macro to_idl
    def to_idl
      if idx.is_a?(IntAst)
        "CSR[#{idx.to_idl}].#{csr_field_name.text_value}"
      else
        "CSR[#{idx.text_value}].#{csr_field_name.text_value}"
      end
    end

    # @!macro type
    def type(symtab, archdef)
      fd = field_def(symtab, archdef)
      qualifiers = fd.type == "RO" ? [:constexpr] : []
      Type.new(:bits, width: fd.width, qualifiers:)
    end

    # @!macro constexpr?
    def constexpr?(symtab, archdef)
      field_def(symtab, archdef).type == "RO"
    end

    # @!macro value
    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      field_def(symtab, archdef).reset_value
    end
  end

  class CsrReadExpressionAst < AstNode
    include Lvalue

    # @!macro type
    def type(symtab, archdef)
      cd = csr_def(symtab, archdef)
      if cd.nil?
        # we don't know anything about this index, so we can only
        # treat this as a generic
        Type.new(:bits, width: archdef.config_params["XLEN"])
      else
        qualifiers = cd.fields.all? { |f| f.type == "RO" } ? [:constexpr] : []
        CsrType.new(cd, qualifiers:)
      end
    end

    # @!macro type_check
    def type_check(symtab, archdef)
      idx_var = symtab.get(idx.text_value)
      if !idx_var.nil?
        # this is a variable
        idx.type_check(symtab, archdef)
        type_error "Csr index must be integral" unless idx_var.type.integral?

        if idx.constexpr?(symtab, archdef)
          csr_index = archdef.csrs.index { |csr| csr.address == idx_var.value }
          type_error "No csr number '#{idx.value(symtab, archdef)}' was found" if csr_index.nil?
        end
      elsif !archdef.csrs.index { |csr| csr.name == idx.text_value }.nil?
        # this is a known csr name
        # nothing else to check
      else
        # a generic expression
        idx.type_check(symtab, archdef)

        type_error "Csr index must be integral" unless idx.type(symtab, archdef).integral?

        if idx.constexpr?(symtab, archdef)
          csr_index = archdef.csrs.index { |csr| csr.address == idx.value(symtab, archdef) }
          type_error "No csr number #{idx.value(symtab, archdef)}" if csr_index.nil?
        end
      end
    end

    def csr_def(symtab, archdef)
      idx_var = symtab.get(idx.text_value)
      if !idx_var.nil?
        # this is a variable
        if idx.constexpr?(symtab, archdef)
          csr_index = archdef.csrs.index { |csr| csr.address == idx_var.value }

          return archdef.csrs[csr_index]
        else
          # we don't know at compile time which CSR this is...
          return nil
        end
      elsif !archdef.csrs.index { |csr| csr.name == idx.text_value }.nil?
        # this is a known csr name
        csr_index = archdef.csrs.index { |csr| csr.name == idx.text_value }
        return archdef.csrs[csr_index]
      else
        # a generic expression
        if idx.constexpr?(symtab, archdef)
          csr_index = archdef.csrs.index { |csr| csr.address == idx.value(symtab, archdef) }

          return archdef.csrs[csr_index]
        else
          # we don't know anything about this index
          return nil
        end
      end
    end

    def csr_known?(symtab, archdef)
      !csr_def(symtab, archdef).nil?
    end

    def csr_name(symtab, archdef)
      internal_error "No CSR" unless csr_known?(symtab, archdef)

      csr_def(symtab, archdef).name
    end

    def constexpr?(symtab, archdef)
      cd = csr_def(symtab, archdef)
      return false if cd.nil?
      cd.fields.all? { |f| f.type == "RO" }
    end

    def value(symtab, archdef)
      internal_error "Not constexpr" unless constexpr?(symtab, archdef)

      csr_def(symtab, archdef).fields.reduce(0) { |val, f| val | (f.value << f.location.begin) }
    end
  end

  class CsrSoftwareWriteAst < AstNode
    def type_check(symtab, archdef)
      csr.type_check(symtab, archdef)
      expression.type_check(symtab, archdef)

      return if expression.type(symtab, archdef).kind == :bits && expression.type(symtab, archdef).width == archdef.config_params["XLEN"]

      type_error "CSR value must be an XReg"
    end

    def csr_known?(symtab, archdef)
      csr.csr_known?(symtab, archdef)
    end

    def csr_name(symtab, archdef)
      csr.csr_name(symtab, archdef)
    end

    def constexpr_compatible?(symtab, archdef) = false
  end

  class CsrSoftwareReadAst < AstNode
    include Lvalue

    def type_check(symtab, archdef)
      csr.type_check(symtab, archdef)
    end

    def type(symtab, archdef)
      if csr_known?(symtab, archdef)
        Type.new(:bits, width: archdef.csr(csr.csr_name(symtab, archdef)).length)
      else
        Type.new(:bits, width: archdef.config_params["XLEN"])
      end
    end

    def csr_known?(symtab, archdef)
      csr.csr_known?(symtab, archdef)
    end

    def csr_name(symtab, archdef)
      csr.csr_name(symtab, archdef)
    end

    # @todo check the sw_read function body
    def constexpr?(symtab, archdef) = false
  end

  class CsrWriteAst < AstNode
    def type_check(symtab, archdef)
      if idx.is_a?(IntAst)
        # make sure this value is a defined CSR
        index = archdef.csrs.index { |csr| csr.address == idx.value(symtab, archdef) }
        type_error "No csr number '#{idx.value(symtab, archdef)}' was found" if index.nil?

        archdef.csrs[index]
      else
        index = archdef.csrs.index { |csr| csr.name == idx.text_value }
        type_error "No csr named '#{idx.text_value}' was found" if index.nil?

        archdef.csrs[index]
      end
    end

    def csr_def(symtab, archdef)
      if idx.is_a?(IntAst)
        # make sure this value is a defined CSR
        index = archdef.csrs.index { |csr| csr.address == idx.text_value.to_i }
        archdef.csrs[index]
      else
        index = archdef.csrs.index { |csr| csr.name == idx.text_value }
        archdef.csrs[index]
      end
    end

    def type(symtab, archdef)
      CsrType.new(csr_def(symtab, archdef))
    end

    def name(symtab, archdef)
      csr_def(symtab, archdef).name
    end
  end
end
