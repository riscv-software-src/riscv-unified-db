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

      # @return [Boolean] whether or not this SyntaxNode represents a function name (overriden in the parser)
      def is_function_name? = false

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

    # exception type raised when the value of IDL code is requested (via node.value(...)) but
    # cannot be provided because some part the code isn't known at compile time
    class ValueError < StandardError
      attr_reader :lineno, :file

      def initialize(what, lineno, file)
        super(what)
        @lineno = lineno
        @file = file
      end
    end
  end

  # functions added to all Ast nodes
  module AstNodeFuncs
    # raise a type error
    #
    # @param reason [String] Error message
    # @raise [AstNode::TypeError] always
    def type_error(reason)
      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
          A type error occured
          #{reason}
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

    # raise a value error, indicating that the value is not known at compile time
    #
    # @param reason [String] Error message
    # @raise [AstNode::ValueError] always
    def value_error(reason)
      msg = <<~WHAT
        In file #{input_file}
        On line #{lineno}
          A value error occured
          #{reason}
      WHAT
      raise AstNode::ValueError.new(msg, lineno, input_file)
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
    def type_check(symtab) = raise NotImplementedError, "Subclass of AstNode must implement type_check"

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

  # interface for nodes that can be executed, but don't have a value (e.g., statements)
  module Executable
    # @!macro [new] execute
    #   "execute" the statement by updating the variables in the symbol table
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if some part of the statement cannot be executed at compile time
    #   @return [void]

    # @!macro execute
    def execute(symtab) = raise NotImplementedError, "#{self.class.name} must implement update_value"
  end

  # interface for nodes that *might* return a value in a function body
  module Returns
    # @!macro [new] retrun_value
    #   Evaluate the compile-time return value of this node, or, if the node does not return
    #   (e.g., because it is an IfAst and the return in the not-taken path), execute the node
    #   and update the symtab
    #
    #   @param symtab [SymbolTable] The symbol table for the context
    #   @raise ValueError if, during evaulation, a node without a compile-time value is found
    #   @return [Integer, nil] The return value, or nil if the node doesn't return

    # @!macro return_value
    def return_value(symtab) = raise NotImplementedError, "#{self.class.name} must implement return_value"
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
    #   @return [Integer] if the compile-time-known value is an integer
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
  end

  # an identifier
  #
  # Used for variables
  class IdAst < AstNode
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      type_error "no symbol named '#{text_value}' on line #{lineno}" if symtab.get(text_value).nil?
    end

    # @return [String] The ID name
    def name = text_value

    # @!macro type_no_archdef
    def type(symtab)
      internal_error "Symbol not found (should have called type_check)" if symtab.get(text_value).nil?

      symtab.get(text_value).type
    end

    # @!macro value_no_archdef
    def value(symtab)
      var = symtab.get(text_value)

      internal_error "Var was not found, call type_check first!" if var.nil?

      value_error "Value of '#{text_value}' not known" if var.value.nil?

      var.value
    end

    # @!macro to_idl
    def to_idl = text_value
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

    def type_check(symtab)
      single_declaration_with_initialization.type_check(symtab)
    end

    def type(symtab)
      single_declartion_with_initialization.type(symtab)
    end

    def value(symtab)
      single_declartion_with_initialization.value(symtab)
    end

    def to_idl
      "TODO"
    end
  end

  class GlobalAst < AstNode
    include Executable

    def type_check(symtab)
      declaration.type_check(symtab)
    end

    def type(symtab)
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

    def type_check(symtab)
      definitions.elements.each do |e|
        next unless e.is_a?(EnumDefinitionAst) || e.is_a?(BitfieldDefinitionAst) || e.is_a?(FunctionDefAst) || e.is_a?(GlobalAst) || e.is_a?(GlobalWithInitializationAst)

        e.type_check(symtab)
        raise "level = #{symtab.levels} #{e.name}" unless symtab.levels == 1
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
          @element_values << e.i.int.value(nil)
          next_auto_value = element_values.last + 1
        end
      end

      @element_values
    end

    # @!macro type_check
    def type_check(symtab)
      e.elements.each do |e|
        unless e.i.empty?
          e.i.int.type_check(symtab)
        end
      end

      et = EnumerationType.new(user_type_name.text_value, element_names, element_values)
      symtab.add!(et.name, et)
    end

    # @!macro type_no_args
    def type(_symtab, _archdef)
      EnumerationType.new(user_type_name.text_value, element_names, element_values)
    end

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
    def type_check(_symtab)
      unless user_type_name.text_value == "ExtensionName"
        type_error "Unsupported builtin enum type '#{user_type_name.text_value}'"
      end
    end

    # @!macro type_no_archdef
    def type(symtab) = symtab.get(user_type_name.text_value)

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
    def type_check(symtab)
      int.type_check(symtab)
      bf_size = int.text_value.to_i

      e.elements.each do |field|
        a = field.range.int.text_value.to_i
        type_error "Field position (#{a}) is larger than the bitfield width (#{bf_size})" if a >= bf_size

        b = field.range.lsb.empty? ? a : field.range.lsb.int.text_value.to_i
        type_error "Field position (#{b}) is larger than the bitfield width (#{bf_size})" if b >= bf_size
      end

      t = type(symtab)
      symtab.add!(name, t)
    end

    # @!macro type_no_args
    def type(symtab) = BitfieldType.new(name, int.value(symtab), element_names, element_ranges)

    # @return [String] bitfield name
    def name = user_type_name.text_value

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
    include Rvalue

    attr_reader :var, :index

    def initialize(input, interval, var, index)
      super(input, interval, [var, index])
      @var = var
      @index = index
    end

    # @!macro type_check
    def type_check(symtab)
      @var.type_check(symtab)
      @index.type_check(symtab)

      type_error "Array index must be integral" unless @index.type(symtab).integral?

      if @var.type(symtab).kind == :array
        begin
          index_value = @index.value(symtab)
          type_error "Array index out of range" if index_value >= @var.type(symtab).width
        rescue ValueError
          # Ok, doesn't need to be known
        end

      elsif @var.type(symtab).integral?
        if @var.type(symtab).kind == :bits
          begin
            index_value = @index.value(symtab)
            if index_value >= @var.type(symtab).width
              type_error "Bits element index (#{index_value}) out of range (max #{@var.type(symtab).width - 1}) in access '#{text_value}'"
            end
          rescue ValueError
            # OK, doesn need to be known
          end
        end

      else
        type_error "Array element access can only be used with integral types and arrays"
      end
    end

    def type(symtab)
      if @var.type(symtab).kind == :array
        @var.type(symtab).sub_type
      elsif @var.type(symtab).integral?
        Type.new(:bits, width: 1)
      else
        internal_error "Bad ary element access"
      end
    end

    def value(symtab)
      if @var.type(symtab).integral?
        (@var.value(symtab) >> @index.value(symtab)) & 1
      else
        value_error "X registers are not compile-time-known" if @var.text_value == "X"

        ary = symtab.get(@var.text_value)
        internal_error "Not an array" unless ary.type.kind == :array

        internal_error "Not an array (is a #{ary.value.class.name})" unless ary.value.is_a?(Array)

        idx = @index.value(symtab)
        internal_error "Index out of range; make sure type_check is called" if idx >= ary.value.size

        ary.value[idx].value
      end
    end
  end

  class AryRangeAccessAst < AstNode
    include Rvalue

    attr_reader :var, :msb, :lsb

    def initialize(input, interval, var, msb, lsb)
      super(input, interval, [var, msb, lsb])
      @var = var
      @msb = msb
      @lsb = lsb
    end

    def type_check(symtab)
      @var.type_check(symtab)
      @msb.type_check(symtab)
      @lsb.type_check(symtab)

      type_error "Range operator only defined for integral types (found #{@var.type(symtab)})" unless @var.type(symtab).integral?

      type_error "Range MSB must be an integral type" unless @msb.type(symtab).integral?
      type_error "Range LSB must be an integral type" unless @lsb.type(symtab).integral?

      begin
        msb_value = @msb.value(symtab)
        lsb_value = @lsb.value(symtab)

        if @var.type(symtab).kind == :bits && msb_value >= @var.type(symtab).width
          type_error "Range too large for bits (range top = #{msb_value}, range width = #{@var.type(symtab).width})"
        end  

        range_size = msb_value - lsb_value + 1
        type_error "zero/negative range (#{msb_value}:#{lsb_value})" if range_size <= 0
      rescue ValueError
        # OK, don't have to know
      end
    end

    def type(symtab)
      begin
        msb_value = @msb.value(symtab)
        lsb_value = @lsb.value(symtab)
        range_size = msb_value - lsb_value + 1
        Type.new(:bits, width: range_size)
      rescue ValueError
        # don't know the width at compile time....assume the worst
        @var.type(symtab)
      end
    end

    def value(symtab)
      mask = (1 << (@msb.value(symtab) - @lsb.value(symtab) + 1)) - 1
      (@var.value(symtab) >> @lsb.value(symtab)) & mask
    end
  end

  # base class for all nodes representing an assignment
  # @abstract
  class AssignmentAst < AstNode
    include Executable

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
    def type_check(symtab)
      var.type_check(symtab)
      rval.type_check(symtab)
      unless rval.type(symtab).convertable_to?(var.type(symtab))
        type_error "Incompatible type in assignment (#{var.type(symtab)}, #{rval.type(symtab)}) on line #{lineno}"
      end
    end

    def lhs
      var
    end

    def rhs
      rval
    end

    def execute(symtab)
      if var.is_a?(CsrWriteAst)
        value_error "CSR writes are never compile-time-known"
      else
        variable = symtab.get(var.text_value)

        internal_error "No variable #{var.text_value}" if variable.nil?

        variable.value = rval.value(symtab)
      end
    end

    # @!macro to_idl
    def to_idl = "#{var.to_idl} = #{rval.to_idl}"
  end

  # represents an array element assignement
  #
  # for example:
  #   X[rs1] = XLEN'd0
  class AryElementAssignmentAst < AssignmentAst
     # @!macro type_check
    def type_check(symtab)
      var.type_check(symtab)
      type_error "#{var.text_value} must be an array or an integral type" unless [:array, :bits].include?(var.type(symtab).kind)
      type_errpr "Assigning to a constant" if var.type(symtab).const?

      idx.type_check(symtab)

      type_error "Index must be integral" unless idx.type(symtab).integral?

      begin
        idx_value = idx.value(symtab)
        type_error "Array index out of range" if idx_value(symtab) >= var.type(symtab).width
      rescue ValueError
        # OK, doesn't need to be known
      end

      rval.type_check(symtab)

      case var.type(symtab).kind
      when :array
        unless rval.type(symtab).convertable_to?(var.type(symtab).sub_type)
          type_error "Incompatible type in array assignment"
        end
      when :bits
        unless rval.type(symtab).convertable_to?(Type.new(:bits, width: 1))
          type_error "Incompatible type in integer slice assignement"
        end
      else
        internal_error "Unexpected type on array element assignment"
      end
    end

    def lhs
      internal_error "What's this used for?"
    end

    def rhs
      rval
    end

    def execute(symtab)
      case var.type(symtab).kind
      when :array
        value_error "TODO: array element assignement execution"
      when :bits
        v = rhs.value(symtab)
        var = symtab.get(var.text_value)
        mask = 1 << idx.value(symtab)
        var.value = (var.value & ~0) | ((v & 1) << idx.value(symtab))
      else
        internal_error "unexpected type for array element assignment"
      end
    end

    # @!macro to_idl
    def to_idl = "#{var.to_idl}[#{idx.to_idl}] = #{rval.to_idl}"
  end

  # represents an array range assignement
  #
  # for example:
  #   vec[8:0] = 8'd0
  class AryRangeAssignmentAst < AssignmentAst
    # @!macro type_check
    def type_check(symtab)
      var.type_check(symtab)
      type_error "#{var.text_value} must be integral" unless var.type(symtab).kind == :bits
      type_errpr "Assigning to a constant" if var.type(symtab).const?

      msb.type_check(symtab)
      lsb.type_check(symtab)

      type_error "MSB must be integral" unless msb.type(symtab).integral?
      type_error "LSB must be integral" unless lsb.type(symtab).integral?

      begin
        msb_value = msb.value(symtab)
        lsb_value = lsb.value(symtab)

        type_error "MSB must be > LSB" unless msb_value > lsb_value
        type_error "MSB is out of range" if msb_value >= var.type(symtab).width
      rescue ValueError
        # OK, don't have to know the value
      end

      rval.type_check(symtab)

      unless rval.type(symtab).integral?
        type_error "Incompatible type in range assignment"
      end
    end

    def lhs
      internal_error "What's this used for?"
    end

    def rhs
      rval
    end

    def execute(symtab)
      var_val = var.value(symtab)

      msb_val = msb.value(symtab)
      lsb_val = lsb.value(symtab)

      type_error "MSB is <= LSB" if msb_val <= lsb_val

      rval_val = rval.value(symtab)

      mask = ((1 << msb_val) - 1) << lsb_val

      var_val &= ~mask

      var_val | ((rval_val << lsb_val) & mask)
    end

    # @!macro to_idl
    def to_idl = "#{var.to_idl}[#{msb.to_idl}:#{lsb.to_idl}] = #{rval.to_idl}"
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
    def kind(symtab)
      var.type(symtab).kind
    end

    # @return [BitfieldType] Type of the bitfield being assigned
    # @raise [AstNode::InternalError] if this is not a bitfield assignment
    def bf_type(symtab)
      internal_error "Not a bitfield variable" unless kind(symtab) == :bitfield

      var.type(symtab)
    end

    # @return [CsrField] field being assigned
    # @raise [AstNode::InternalError] if this is not a CSR assignment
    def field(symtab)
      internal_error "Not a CSR field type" unless kind(symtab) == :csr
      var.type(symtab).csr.fields.select { |f| f.name == field_name.text_value }[0]
    end

    # @!macro type
    def type(symtab)
      case kind(symtab)
      when :bitfield
        Type.new(:bits, width: var.type(symtab).range(field_name.text_value).size)
      when :csr
        if field(symtab).defined_in_all_bases?
          Type.new(:bits, width: [field(symtab).location(32).size, field(symtab).location(64).size].max)
        elsif field(symtab).base64_only?
          Type.new(:bits, width: field(symtab).location(64).size)
        elsif field(symtab).base32_only?
          Type.new(:bits, width: field(symtab).location(32).size)
        else
          internal_error "Unexpected base for field"
        end
      else
        internal_error "Unhandled kind"
      end
    end

    # @!macro type_check
    def type_check(symtab)
      var.type_check(symtab)

      type_error "Cannot write const variable" if var.type(symtab).const?

      if var.type(symtab).kind == :bitfield
        unless var.type(symtab).field_names.include?(field_name.text_value)
          type_error "#{field_name.text_value} is not a member of #{var.type(symtab)} on line #{lineno}"
        end

      elsif var.type(symtab).kind == :csr
        fields = var.type(symtab).csr.fields.select { |f| f.name == field_name.text_value }
        type_error "#{field_name.text_value} is not a field of CSR #{rval.type(symtab).csr.name}" unless fields.size == 1

        type_error "Cannot write to read-only CSR field" if ["RO", "RO-H"].any?(field(symtab).type)
      else
        type_error "Field assignment on type that is not a bitfield or csr (#{var.type(symtab)})"
      end

      rval.type_check(symtab)
      return if rval.type(symtab).convertable_to?(type(symtab))

      type_error "Incompatible type in assignment (#{type(symtab)}, #{rval.type(symtab)})"
    end

    def execute(symtab)
      value_error "TODO: Field assignement execution"
    end

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
    def type_check(symtab)
      function_call.type_check(symtab)
      vars.each { |var| var.type_check(symtab) }

      type_error "Assigning value to a constant" if vars.any? { |v| v.type(symtab).const? }

      type_error "Function '#{function_call.name}' has no return type" if function_call.type(symtab).nil?
      unless function_call.type(symtab).kind == :tuple
        type_error "Function '#{function_call.name}' only returns 1 variable on line #{lineno}"
      end

      if function_call.type(symtab).tuple_types.size != vars.size
        type_error "function '#{function_call.name}' returns #{function_call.type(symtab).tuple_types.size} arguments, but  #{vars.size} were specified"
      end

      function_call.type(symtab).tuple_types.each_index do |i|
        next if vars[i].is_a?(DontCareLvalueAst)
        raise "Implementation error" if vars[i].is_a?(DontCareReturnAst)

        var = symtab.get(vars[i].text_value)
        type_error "No symbol named '#{vars[i].text_value}' on line #{lineno}" if var.nil?

        internal_error "Cannot determine type of #{vars[i].text_value}" unless var.respond_to?(:type)

        unless var.type.convertable_to?(function_call.type(symtab).tuple_types[i])
          raise "'#{function_call.name}' expecting a #{function_call.type(symtab).tuple_types[i]} in argument #{i}, but was given #{var.type(symtab)} on line #{lineno}"
        end
      end
    end

    def execute(symtab)
      values = function_call.execute(symtab)

      i = 0
      vars.each do |v|
        var = symtab.get(v.text_value)
        internal_error "call type check" if var.nil?

        var.value = values[i]
        i += 1
      end
    end

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

    # @!macro type_check
    def type_check(symtab)
      type_error "No type named '#{type_name.text_value}' on line #{lineno}" if type.nil?

      type_error "Attempt to write read-only/constant variable #{text_value}" if type.const?

      var_names.each do |vname|
        symtab.add(vname, Var.new(vname, type.clone))
      end
    end

    def execute(symtab)
      var_names.each do |name|
        symtab.add(name, Var.new(name, type.clone))
      end
    end

    # @!macro to_idl
    def to_idl = "#{type.to_idl} #{var_names.map(&:to_idl).join(', ')}"
  end

  # represents a single variable declaration (without assignement)
  #
  # for example:
  #   Bits<64> doubleword
  #   Boolean has_property
  class VariableDeclarationAst < AstNode
    include Executable

    def decl_type(symtab)
      dtype = type_name.type(symtab)

      return nil if dtype.nil?

      dtype = Type.new(:enum_ref, enum_class: dtype) if dtype.kind == :enum

      dtype = dtype.clone.qualify(q.text_value.to_sym) unless q.empty?

      unless ary_size.empty?
        dtype = Type.new(:array, width: ary_size.expression.value(symtab), sub_type: dtype.clone)
      end

      dtype
    end

    # @!macro type_check
    def type_check(symtab)
      type_name.type_check(symtab)
      dtype = type_name.type(symtab)

      type_error "No type '#{type_name.text_value}' on line #{lineno}" if dtype.nil?

      type_error "Constants must be initialized at declaration" if var_write.text_value == var_write.text_value.upcase

      unless ary_size.empty?
        ary_size.expression.type_check(symtab)
        begin
          ary_size_value = ary_size.expression.value(symtab)
        rescue ValueError
          type_error "Array size must be known at compile time"
        end
      end

      symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type(symtab)))

      var_write.type_check(symtab)
    end

    def execute(symtab)
      value_error "TODO: array declration execution" unless ary_size.empty?
      symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type(symtab)))
    end

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
    include Executable

    def lhs_type(symtab)
      decl_type = type_name.type(symtab).clone
      type_error "No type '#{type_name.text_value}' on line #{lineno}" if decl_type.nil?

      decl_type = Type.new(:enum_ref, enum_class: decl_type) if decl_type.kind == :enum

      decl_type = decl_type.clone.qualify(q.text_value.to_sym) unless q.empty?

      decl_type
    end

    def type_check(symtab)
      rval.type_check(symtab)

      type_name.type_check(symtab)

      decl_type = lhs_type(symtab)

      unless ary_size.empty?
        ary_size.expression.type_check(symtab)
        begin
          ary_size_value = ary_size.expression.value(symtab)
        rescue ValueError
          type_error "Array size must be known at compile time"
        end

        decl_type = Type.new(:array, width: ary_size_value, sub_type: decl_type)
      end

      if (var_write.text_value == var_write.text_value.upcase) && ary_size.empty?
        # this is a constant; ensure we are assigning a constant value
        begin
          symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type.clone.make_const, rval.value(symtab)))
        rescue ValueError => e
          type_error "Declaring constant with a non-constant value (#{e})"
        end
      else
        symtab.add(var_write.text_value, Var.new(var_write.text_value, decl_type.clone))
      end

      var_write.type_check(symtab)

      # now check that the assignment is compatible
      return if rval.type(symtab).convertable_to?(decl_type)

      type_error "Incompatible type (#{decl_type}, #{rval.type(symtab)}) in assignment"
    end

    def lhs
      var_write
    end

    def rhs
      # if rhs is nil, this is the non-initializing variant
      return nil unless respond_to?(:rval)

      return rval if rval.is_a?(Rvalue)

      internal_error "unexpected #{rval.inspect}" unless rval.is_a?(MemoryRValAst)

      rval
    end

    def execute(symtab)
      value_error "TODO: Array declaration" unless ary_size.empty?
      symtab.add(lhs.text_value, Var.new(lhs.text_value, lhs_type(symtab), rhs.value(symtab)))
    end
  end

  class BinaryExpressionRightAst < AstNode

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

    def type_check(_symtab, _archdef)
      raise "you must have forgotten the make_left pass"
    end
  end

  class SignCastAst < AstNode
    include Rvalue

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

  # Node for a cast to a Bits<N> type
  #
  # This will result in a BitsCaseAst:
  #
  #   $bits(ExceptionCode::LoadAccessFault) 
  class BitsCastAst < AstNode
    include Rvalue

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
        type_error "Cannot $bits cast CSR #{etype.csr.name} because its length is dynamic" if etype.csr.dynamic_length?
        Type.new(:bits, width: etype.csr.length)
      end
    end

    # @!macro value
    def value(symtab)
      etype = expression.type(symtab)

      case etype.kind
      when :bits
        expression.value(symtab)
      when :enum_ref
        element_name = expression.text_value.split(":")[2]
        etype.enum_class.value(element_name)
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

    # create a new, left-recursion-fixed, binary expression
    def initialize(input, interval, lhs, op, rhs)
      super(input, interval, [lhs, op, rhs])
      @lhs = lhs
      @op = op.text_value
      type_error "Bad op '#{@op}'" unless OPS.include?(@op)
      @rhs = rhs
    end

    # @return [BinaryExpressionAst] this expression, but with an inverted condition
    def invert(symtab)
      type_error "Not a boolean operator" unless type(symtab).kind == :boolean

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
    def type(symtab)
      qualifiers = []

      if LOGICAL_OPS.include?(op)
        Type.new(:boolean, qualifiers:)
      elsif op == "<<"
        begin
          # if shift amount is known, then the result width is increased by the shift
          # otherwise, the result is the width of the left hand side
          Type.new(:bits, width: @lhs.type(symtab).width + @rhs.value(symtab), qualifiers:)
        rescue ValueError
          Type.new(:bits, width: @lhs.type(symtab).width, qualifiers:)
        end
      elsif ["+", "-", "*"].include?(op)
        qualifiers << :signed if @lhs.type(symtab).signed? || @rhs.type(symtab).signed?
        Type.new(:bits, width: [@lhs.type(symtab).width, @rhs.type(symtab).width].max, qualifiers:)
      else
        @lhs.type(symtab).clone
      end
    end

    # @!macro type_check
    def type_check(symtab)
      internal_error "No type_check function #{@lhs.inspect}" unless @lhs.respond_to?(:type_check)

      @lhs.type_check(symtab)
      short_circuit = false
      begin
        if (@lhs.value(symtab) == true && op == "||") || (@lhs.value(symtab) == false && op == "&&")
          short_circuit = true
        end
      rescue ValueError
        short_circuit = false
      end
      @rhs.type_check(symtab) unless short_circuit

      if ["<=", ">=", "<", ">", "!=", "=="].include?(op)
        internal_error text_value if @rhs.type(symtab).nil?
        unless @rhs.type(symtab).comparable_to?(@lhs.type(symtab))
          type_error "#{@lhs.text_value} (type = #{@lhs.type(symtab)}) and #{@rhs.text_value} (type = #{@rhs.type(symtab)}) are not comparable on line #{lineno}"
        end

      elsif ["&&", "||"].include?(op)
        unless @lhs.type(symtab).convertable_to?(:boolean)
          type_error "left-hand side of #{op} needs to be boolean (is #{@lhs.type(symtab)}) on line #{lineno} (#{text_value})"
        end

        unless short_circuit
          unless @rhs.type(symtab).convertable_to?(:boolean)
            type_error "right-hand side of #{op} needs to be boolean (is #{@rhs.type(symtab)}) on line #{lineno} (#{text_value})"
          end
        end

      elsif op == "<<"
        type_error "Unsupported type for left shift: #{@lhs.type(symtab)}" unless @lhs.type(symtab).kind == :bits
        type_error "Unsupported shift for left shift: #{@rhs.type(symtab)}" unless @rhs.type(symtab).kind == :bits
      elsif op == ">>"
        type_error "Unsupported type for right shift: #{@lhs.type(symtab)}" unless @lhs.type(symtab).kind == :bits
        type_error "Unsupported shift for right shift: #{@rhs.type(symtab)}" unless @rhs.type(symtab).kind == :bits
      elsif op == "*"
        # TODO: this needs to be op-aware
        unless @lhs.type(symtab).integral? && @rhs.type(symtab).integral?
          type_error "Addition/subtraction is only defined for integral types"
        end

        # result is width of the largest operand
        unless [:bits, :xreg, :enum_ref].any?(@lhs.type(symtab).kind) && [:bits, :xreg, :enum_ref].any?(@rhs.type(symtab).kind)
          internal_error "Need to handle another integral type"
        end
      elsif ["+", "-"].include?(op)
        unless @lhs.type(symtab).integral? && @rhs.type(symtab).integral?
          type_error "Addition/subtraction is only defined for integral types"
        end

        # result is width of the largest operand
        unless [:bits, :xreg, :enum_ref].any?(@lhs.type(symtab).kind) && [:bits, :xreg, :enum_ref].any?(@rhs.type(symtab).kind)
          internal_error "Need to handle another integral type"
        end
      end
    end

    # @!macro value
    def value(symtab)
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
          eval "lhs_value #{op} rhs.value(symtab)", binding, __FILE__, __LINE__
        end
      else
        eval "lhs.value(symtab) #{op} rhs.value(symtab)", binding, __FILE__, __LINE__
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
    include Rvalue

    def invert(symtab) = e.invert(symtab)

    # @!macro type_check
    def type_check(symtab) = e.type_check(symtab)

    # @!macro type
    def type(symtab) = e.type(symtab)

    # @!macro value
    def value(symtab) = e.value(symtab)

    # @!macro to_idl
    def to_idl = "(#{e.to_idl})"
  end

  class ArrayLiteralAst < AstNode
    include Rvalue

    def element_nodes
      [first] + rest.elements.map(&:expression)
    end

    # @!macro type_check
    def type_check(symtab)
      element_nodes.each do |node|
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

  # represents a concatenation expression
  #
  # for example:
  #   {1'b0, 5'd3}
  class ConcatenationExpressionAst < AstNode
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      first.type_check(symtab)
      type_error "Concatenation only supports Bits<> types" unless first.type(symtab).kind == :bits

      type_error "Must concatenate at least two objects" if rest.elements.empty?

      rest.elements.each do |e|
        e.expression.type_check(symtab)
        type_error "Concatenation only supports Bits<> types" unless e.expression.type(symtab).kind == :bits

        internal_error "Negative width for element #{e.expression.text_value}" if e.expression.type(symtab).width <= 0
      end
    end

    # @!macro type
    def type(symtab)
      total_width = first.type(symtab).width

      rest.elements.each do |e|
        total_width += e.expression.type(symtab).width
      end

      Type.new(:bits, width: total_width)
    end

    # @!macro value
    def value(symtab)
      result = first.value(symtab)
      total_width = first.type(symtab).width
      rest.elements.each do |e|
        result |= (e.expression.value(symtab) << total_width)
        total_width += e.expression.type(symtab).width
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
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      n.type_check(symtab)
      v.type_check(symtab)

      type_error "value of replication must be a Bits type" unless v.type(symtab).kind == :bits
      begin
        type_error "replication amount must be positive (#{n.value(symtab)})" unless n.value(symtab).positive?
      rescue ValueError
        type_error "replication amount must be known at compile time"
      end
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
      width = (n.value(symtab) * v.type(symtab).width)
      Type.new(:bits, width:)
    end

    # @!macro to_idl
    def to_idl = "{#{n.to_idl}{#{v.to_idl}}}"
  end

  # represents a post-decrement expression
  #
  # for example:
  #   i--
  class PostDecrementExpressionAst < AstNode
    include Executable

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
      internal_error "No symbol #{rval.text_value}" if var.nil?

      var.value = var.value - 1
    end

    def to_idl = "#{rval.to_idl}--"
  end

  # represents a post-increment expression
  #
  # for example:
  #   i++
  class PostIncrementExpressionAst < AstNode
    include Executable

    # @!macro type_check
    def type_check(symtab)
      rval.type_check(symtab)
      var = symtab.get(rval.text_value)
    end

    # @!macro type
    def type(symtab)
      rval.type(symtab)
    end

    # @!macro execute
    def execute(symtab)
      var = symtab.get(rval)
      internal_error "Call type check first" if var.nil?

      var.value = var.value + 1
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
    include Rvalue

    def kind(symtab)
      rval.type(symtab).kind
    end

    # @!macro type
    def type(symtab)
      rval_type = rval.type(symtab)

      if rval_type.kind == :bitfield
        Type.new(:bits, width: rval.type(symtab).range(field_name.text_value).size)
      elsif rval_type.kind == :enum_ref
        Type.new(:bits, width: rval_type.enum_class.width)
      else
        internal_error "todo"
      end
    end

    def type_check(symtab)
      rval.type_check(symtab)

      rval_type = rval.type(symtab)

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
        # qualifiers << :const if @field.type == "RO-H"

        # @kind = :csr
        # @type = Type.new(:bits, width: @field.location.size, qualifiers:)
      else
        type_error "#{rval.text_value} is not a bitfield or CSR (is #{rval.type(symtab)})"
      end
    end

    # @!macro value
    def value(symtab)
      if kind(symtab) == :bitfield
        range = rval.type(symtab).range(field_name.text_value)
        (rval.value(symtab) >> range.first) & ((1 << range.size) - 1)
      elsif kind(symtab) == :enum_ref
        symtab.get(rval.text_value).value
      else
      internal_error "TODO"
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
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      enum_def_type = symtab.get(enum_class.text_value)
      type_error "No symbol #{enum_class.text_value} has been defined" if enum_def_type.nil?

      type_error "#{enum_class.text_value} is not an enum type" unless enum_def_type.is_a?(EnumerationType)
    end

    # @!macro type_no_archdef
    def type(symtab)
      internal_error "Must call type_check first" if symtab.get(enum_class.text_value).nil?

      Type.new(:enum_ref, enum_class: symtab.get(enum_class.text_value))
    end

    # @!macro value_no_archdef
    def value(symtab)
      internal_error "Must call type_check first" if symtab.get(enum_class.text_value).nil?

      symtab.get(enum_class.text_value).value(member.text_value)
    end

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
    include Rvalue

    # @!macro type
    def type(symtab)
      case op
      when "-", "~"
        exp.type(symtab).clone
      when "!"
        Type.new(:boolean, qualifiers: exp.type(symtab).qualifiers.select { |q| [:const].any?(q) })
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

        type_error "Unary minus only works on signed values" unless exp.type(symtab).signed?
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
      val = eval("#{op}#{exp.value(symtab)}", binding, __FILE__, __LINE__)
      if type(symtab).integral? && type(symtab).width > val.bit_length
        # need to truncate
        val &= ((1 << type(symtab).width) - 1)
        if type(symtab).signed? && ((((val >> (type(symtab).width - 1))) & 1) == 1)
          # need to make this negative!
          # take the twos compliment
          val = -((1 << type(symtab).width) - val)
        end
      end

      val
    end

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
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      p9_binary_expression.type_check(symtab)
      begin
        cond = p9_binary_expression.value(symtab)
        # if the condition is compile-time-known, only check the used field
        if (cond)
          t.type_check(symtab)
        else
          f.type_check(symtab)
        end
      rescue ValueError
        t.type_check(symtab)
        f.type_check(symtab)

        unless t.type(symtab).equal_to?(f.type(symtab))
          # we'll allow dissimilar if they are both bits type
          unless t.type(symtab).kind == :bits && f.type(symtab).kind == :bits
            type_error "True and false options must be same type (have #{t.type(symtab)} and #{f.type(symtab)})"
          end
        end
      end

      type_error "ternary selector must be bool" unless p9_binary_expression.type(symtab).kind == :boolean


    end

    # @!macro type
    def type(symtab)
      p9_binary_expression.type_check(symtab)
      begin
        cond = p9_binary_expression.value(symtab)
        # if the condition is compile-time-known, only check the used field
        if (cond)
          t.type(symtab)
        else
          f.type(symtab)
        end
      rescue ValueError
        if t.type(symtab).kind == :bits && f.type(symtab).kind == :bits
          Type.new(:bits, width: [t.type(symtab).width, f.type(symtab).width].max)
        else
          t.type(symtab)
        end
      end
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
    def value(symtab)
      condition.value(symtab) ? t.value(symtab) : f.value(symtab)
    end

    # @!macro to_idl
    def to_idl = "#{condition.to_idl} ? #{true_expression.to_idl} : #{false_expression.to_idl}"
  end

  module VarReadExpressionAst
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      var = symtab.get(text_value)

      type_error "No symbol named '#{text_value}'" if var.nil?

      type_error "'#{text_value}' is not a variable" unless var.is_a?(Var)
    end

    # @!macro type_no_archdef
    def type(symtab)
      internal_error "While checking VarRead type, no symbol '#{text_value}' found" if symtab.get(text_value).nil?

      symtab.get(text_value).type
    end

    # @!macro value_no_archdef
    def value(symtab)
      var = symtab.get(text_value)

      internal_error "Call type_check first" if var.nil?

      value_error "The value of '#{text_value}' is not known" if var.value.nil?
      
      var.value
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
    include Executable

    def action = a

    # @!macro type_check
    def type_check(symtab)
      a.type_check(symtab)
    end

    def execute(symtab)
      a.execute(symtab)
    end

    def to_idl = "#{action.to_idl};"
  end

  # represents a predicated simple statement
  #
  # for example:
  #   a = 2 if condition;
  class ConditionalStatementAst < StatementAst
    # @!macro type_check
    def type_check(symtab)
      action.type_check(symtab)
      condition.type_check(symtab)
      type_error "condition is not boolean" unless condition.type(symtab).convertable_to?(:boolean)
    end

    def action = a

    def condition
      expression
    end

    def execute(symtab)
      cond = condition.value(symtab)

      if (cond)
        action.execute(symtab)
      end
    end
  end

  # represents a don't care return value
  #
  # for exaple:
  #   return -;
  class DontCareReturnAst < AstNode
    include Rvalue

    # @!macro type_check_no_args
    def type_check(_symtab)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab)
      Type.new(:dontcare)
    end

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
    include Rvalue

    # @!macro type_check_no_args
    def type_check(_symtab)
      # nothing to do!
    end

    # @!macro type_no_args
    def type(_symtab, _archdef)
      Type.new(:dontcare)
    end

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
    include Returns

    # @return [Array<Type>] List of actual return types
    def return_types(symtab)
      if first.type(symtab).kind == :tuple
        first.type(symtab).tuple_types
      else
        rtypes = [first.type(symtab)]
        rest.elements.each do |e|
          rtypes << e.e.type(symtab)
        end
        rtypes
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
        func_type = symtab.get_global(func_def.name)
        internal_error "Couldn't find function type for '#{func_def.name}' #{symtab.keys} " if func_type.nil?

        # to get the return type, we need to find the template values in case this is
        # a templated function definition
        #
        # that information should be up the stack in the symbol table
        template_values = symtab.find_all(single_scope: true) do |o|
          o.is_a?(Var) && o.template_value_for?(func_def.name)
        end
        unless template_values.size == func_type.template_names.size
          internal_error "Did not find correct number of template arguments (found #{template_values.size}, need #{func_type.template_names.size}) #{symtab.keys_pretty}"
        end
        func_type.return_type(template_values.sort { |a, b| a.template_index <=> b.template_index }.map(&:value))
      end
    end

    # @!macro type_check
    def type_check(symtab)
      first.type_check(symtab)
      if first.type(symtab).nil?
        type_error "Unknown type for first return argument #{first.class} #{first.text_value}"
      end

      types = []
      if first.type(symtab).kind == :tuple
        type_error("Can't combine tuple types in return") unless rest.elements.empty?
        num_values = first.type(symtab).tuple_types.size
        types = first.type(symtab).tuple_types
      else
        types = [first.type(symtab)]
        rest.elements.each do |e|
          e.e.type_check(symtab)
          types << e.e.type(symtab)
        end
      end

      unless return_type(symtab).convertable_to?(expected_return_type(symtab))
        type_error "Return type (#{return_type(symtab)}) not convertable to expected return type (#{expected_return_type(symtab)})"
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

    def return_value(symtab)
      if return_value_nodes.size == 1
        return_value_nodes[0].value(symtab)
      else
        return_value_nodes.map { |v| v.value(symtab) }
      end
    end

    def to_idl = "return #{return_value_nodes.map(&:to_idl).join(',')};"
  end

  class ConditionalReturnStatementAst < ReturnStatementAst
    include Returns

    def condition
      expression
    end

    def return_value(symtab)
      cond = condition.value(symtab)

      if cond
        return_value_nodes.map do |n|
          n.value(symtab)
        end
      else
        nil
      end
    end
  end

  class ExecutionCommentAst < AstNode
    def type_check(_symtab, _global); end
  end

  class BitsTypeAst < AstNode
    # @!macro type_check
    def type_check(symtab)
      i.type_check(symtab)

      begin
        i.value(symtab)
      rescue ValueError
        type_error "Bit width is not compile-time known"
      end
      type_error "Bit widht must be integral" unless i.type(symtab).integral?
    end

    # @!macro type
    def type(symtab)
      Type.new(:bits, width: i.value(symtab).to_i)
    end

  end

  class BuiltinTypeNameAst < AstNode
    # @!macro type_check
    def type_check(symtab)
      type_error "Unimplemented builtin type #{text_value}" unless ["XReg", "Boolean", "U32", "U64"].include?(text_value)
    end

    # @!macro type
    def type(symtab)
      archdef = symtab.archdef
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
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      archdef = symtab.archdef
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

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
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

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        width = signed == "s" ? @value.bit_length + 1 : @value.bit_length
        width = 1 if width.zero? # happens when the literal is '0'
        @type = Type.new(:bits, width:, qualifiers:)
      elsif text_value_no_underscores =~ /([0-9]*)(s?)/
        value = ::Regexp.last_match(1)
        signed = ::Regexp.last_match(2)

        @value = value.to_i(10)

        qualifiers = signed == "s" ? [:signed, :const] : [:const]
        width = signed == "s" ? @value.bit_length + 1 : @value.bit_length
        width = 1 if width.zero? # happens when the literal is '0'
        @type = Type.new(:bits, width:, qualifiers:)
      else
        internal_error "Unhandled int value"
      end
      type_error(text_value) if @value.nil?
    end

    # @!macro type
    def type(symtab)
      @type
    end

    # @!macro value
    def value(symtab)
      internal_error("Did not type check #{text_value}") if @value.nil?

      @value
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  class FunctionCallExpressionAst < AstNode
    # a function call can be both Lvalue (when void or return is ignored) and Rvalue
    include Rvalue
    include Executable

    # @return [Boolean] whether or not the function call has a template argument
    def template?
      !t.empty?
    end

    # @return [Array<AstNode>] Template argument nodes
    def template_arg_nodes
      return [] unless template?

      [t.targs.first] + t.targs.rest.elements.map(&:arg)
    end

    def template_values(symtab)
      return [] unless template?

      template_arg_nodes.map { |e| e.value(symtab) }
    end

    # @return [Array<AstNode>] Function argument nodes
    def arg_nodes
      nodes = []
      nodes << function_arg_list.first unless function_arg_list.first.empty?
      nodes + function_arg_list.rest.elements.map(&:expression)
    end

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels

      func_def_type = symtab.get(name)
      type_error "No symbol #{name}" if func_def_type.nil?

      unless func_def_type.is_a?(FunctionType)
        type_error "#{name} is not a function (it's a #{func_def_type.class.name})"
      end

      type_error "Missing template arguments in call to #{name}" if template? && func_def_type.template_names.empty?

      type_error "Template arguments provided in call to non-template function #{name}" if !template? && !func_def_type.template_names.empty?

      if template?
        num_targs = template_arg_nodes.size
        if func_def_type.template_names.size != num_targs
          type_error "Wrong number of template arguments (expecting #{func_def_type.template_names.size}, got #{num_targs})"
        end

        template_arg_nodes.each_with_index do |t, idx|
          t.type_check(symtab)
          unless t.type(symtab).convertable_to?(func_def_type.template_types[idx])
            type_error "Template argument #{idx + 1} has wrong type"
          end
        end

        func_def_type.type_check_call(template_values(symtab))
      else
        func_def_type.type_check_call
      end

      num_args = arg_nodes.size
      if func_def_type.num_args != num_args
        type_error "Wrong number of arguments to '#{name}' function call. Expecting #{func_def_type.num_args}, got #{num_args}"
      end
      arg_nodes.each_with_index do |a, idx|
        a.type_check(symtab)
      end
      arg_nodes.each_with_index do |a, idx|
        unless a.type(symtab).convertable_to?(func_def_type.argument_type(idx, template_values(symtab), arg_nodes, symtab))
          type_error "Wrong type for argument number #{idx + 1}. Expecting #{func_def_type.argument_type(idx, template_values(symtab))}, got #{a.type(symtab)}"
        end
      end

      if func_def_type.return_type(template_values(symtab)).nil?
        internal_error "No type determined for function"
      end

      internal_error "Function call symtab not at same level post type check (#{symtab.levels} #{level})" unless symtab.levels == level
    end

    # @!macro type
    def type(symtab)
      func_def_type = symtab.get(name)
      func_def_type.return_type(template_values(symtab))
    end

    # @!macro value
    def value(symtab)
      func_def_type = symtab.get(name)
      type_error "not a function" unless func_def_type.is_a?(FunctionType)
      if func_def_type.builtin?
        if name == "implemented?"
          extname = arg_nodes[0].text_value
          return symtab.archdef.ext?(extname)
        else
          value_error "value of builtin function cannot be known"
        end
      end

      template_values = []
      template_arg_nodes.each_with_index do |targ, idx|
        # targ_name = func_def_type.template_names[idx]
        # targ_type = func_def_type.template_types[idx]
        template_values << targ.value(symtab)
      end

      func_def_type.return_value(template_values, arg_nodes, symtab)
    end
    alias execute value

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
    # @!macro type_check
    def type_check(symtab)
      type = symtab.get(text_value)

      type_error "#{text_value} is not a type" unless type.is_a?(Type)
    end

    # @!macro type_no_archdef
    def type(symtab)
      symtab.get(text_value)
    end

    # @!macro to_idl
    def to_idl = text_value
  end

  class FieldNameAst < AstNode
    # @!macro type_check
    def type_check(_symtab, _archdef)
      # nothing to do
    end
  end

  module FunctionStatementAst
    include Executable
    include AstNodeFuncs

    def execute(symtab)
      raise "WHere is this AST?"
    end
  end

  class InstructionOperationAst < AstNode
    include Executable

    # @!macro type_check
    def type_check(symtab)
      op_stmt_list.elements.each do |e|
        e.choice.type_check(symtab)
      end
    end

    def execute(symtab)
      op_stmt_list.elements.each do |e|
        e.choice.execute(symtab)
      end
    end
  end

  class FunctionBodyAst < AstNode
    include Executable
    include Returns

    def statements
      func_stmt_list.elements.map(&:choice)
    end

    # @!macro type_check
    def type_check(symtab)
      internal_error "Function bodies should be at global + 1 scope" unless symtab.levels == 2

      return_value_might_be_known = true

      statements.each do |s|
        s.type_check(symtab)
        next unless return_value_might_be_known

        begin
          if s.is_a?(Returns)
            s.return_value(symtab)
            # if we reach here, the return value is known, so we don't have to go futher
            return
          else
            s.execute(symtab)
          end
        rescue ValueError
          return_value_might_be_known = false
        end
      end
    end

    # @!macro return_value
    #
    # @note arguments and template arguments must be put on the symtab before calling
    def return_value(symtab)
      internal_error "Function bodies should be at global + 1 scope" unless symtab.levels == 2

      # go through the statements, and return the first one that has a return value
      statements.each do |s|
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
    def arguments(symtab)
      if templated?
        template_names.each do |tname|
          internal_error "Template values missing" unless symtab.get(tname)
        end
      end

      arglist = []
      return arglist if args.empty?

      atype = args.first.type_name.type(symtab)
      atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum

      arglist << [atype, args.first.id.text_value]

      args.rest.elements.each do |a|
        atype = a.function_argument_definition.type_name.type(symtab)
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

    # return the return type, which may be a tuple of multiple types
    def return_type(symtab)
      unless symtab.levels == 2
        internal_error "Function bodies should be at global + 1 scope (at global + #{symtab.levels - 1})"
      end

      if templated?
        template_names.each do |tname|
          internal_error "Template values missing" unless symtab.get(tname)
        end
      end

      if ret.empty?
        return Type.new(:void)
      end

      rtype = ret.first.type(symtab)
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
    def type_check_template_instance(symtab)
      internal_error "Function definitions should be at global + 1 scope" unless symtab.levels == 2

      internal_error "Not a template function" unless templated?

      template_names.each do |tname|
        internal_error "Template values missing" unless symtab.get(tname)
      end

      type_check_return(symtab)
      type_check_args(symtab)
      type_check_body(symtab)
    end

    # we do lazy type checking of the function body so that we never check
    # uncalled functions, which avoids dealing with mentions of CSRs that
    # may not exist in a given implmentation
    def type_check_from_call(symtab)
      internal_error "Function definitions should be at global + 1 scope" unless symtab.levels == 2

      global_scope = symtab.deep_clone
      global_scope.pop while global_scope.levels != 1

      global_scope.push # push function scope
      type_check_return(global_scope)
      type_check_args(global_scope)
      type_check_body(global_scope)
      global_scope.pop
    end

    # @!macro type_check
    def type_check(symtab)
      internal_error "Functions must be declared at global scope (at #{symtab.levels})" unless symtab.levels == 1

      type_check_targs(symtab)

      # now add the function in global scope
      def_type = FunctionType.new(
          name,
          self,
          symtab
        )

      # recursion isn't supported (doesn't map well to hardware), so we can add the function after type checking the body
      symtab.add!(name, def_type)
    end

    attr_reader :template_names
    attr_reader :template_types
    def type_check_targs(symtab)
      @template_names = []
      @template_types = []
      return unless templated?

      targs.first.type_name.type_check(symtab)
      ttype = targs.first.type_name.type(symtab)
      type_error "No type '#{targs.first.type_name.text_value}' on line #{lineno}" if ttype.nil?

      ttype = Type.new(:enum_ref, enum_class: ttype) if ttype.kind == :enum

      @template_names << targs.first.id.text_value
      @template_types << ttype.clone

      targs.rest.elements.each do |a|
        a.function_argument_definition.type_name.type_check(symtab)
        ttype = a.function_argument_definition.type_name.type(symtab)
        if ttype.nil?
          internal_error "No type '#{a.function_argument_definition.type_name.text_value}"
        end
        ttype = Type.new(:enum_ref, enum_class: ttype) if ttype.kind == :enum

        @template_names << a.function_argument_definition.id.text_value
        @template_types << ttype.clone
      end
    end

    def type_check_return(symtab)
      return if ret.empty?

      ret.first.type_check(symtab)
      rtype = ret.first.type(symtab)
      type_error "No type '#{ret.first.text_value}" if rtype.nil?

      return if ret.rest.empty?

      ret.rest.elements.each do |r|
        r.type_name.type_check(symtab)
        rtype = symtab.get(r.type_name.text_value)

        type_error "No type '#{r.type_name.text_value}" if rtype.nil?
      end
    end

    def type_check_args(symtab)
      @arguments = []
      return if args.empty?

      args.first.type_name.type_check(symtab)

      atype = args.first.type_name.type(symtab)
      type_error "No type '#{args.first.type_name.text_value}" if atype.nil?
      atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum
      begin
        symtab.add!(args.first.id.text_value, Var.new(args.first.id.text_value, atype))
      rescue SymbolTable::DuplicateSymError => e
        type_error "#{e} "
      end

      args.rest.elements.each do |a|
        a.function_argument_definition.type_name.type_check(symtab)
        atype = a.function_argument_definition.type_name.type(symtab)
        type_error "No type '#{a.function_argument_definition.type_name.text_value}" if atype.nil?
        atype = Type.new(:enum_ref, enum_class: atype) if atype.kind == :enum
        symtab.add!(a.function_argument_definition.id.text_value, Var.new(a.function_argument_definition.id.text_value, atype))
      end
    end

    def type_check_body(symtab)

      if respond_to?(:body_block)
        body_block.function_body.type_check(symtab)
      end

      # now find all the return don't cares, and let them know what the expected
      # return type is
      # find_returns_from(self)
    end

    def body
      internal_error "Function has no body" if builtin?

      body_block.function_body
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

  end

  class ForLoopAst < AstNode
    include Executable
    include Returns # a return statement in a for loop can make it return a value

    # @!macro type_check
    def type_check(symtab)
      symtab.push
      single_declaration_with_initialization.type_check(symtab)
      condition.type_check(symtab)
      action.type_check(symtab)

      stmts.elements.each do |s|
        s.s.type_check(symtab)
      end
      symtab.pop
    end

    def return_value(symtab)
      symtab.push

      begin
        single_declaration_with_initialization.execute(symtab)

        while condition.value(symtab)
          stmts.elements.each do |s|
            if s.s.is_a?(Returns)
              v = s.s.return_value(symtab)
              unless v.nil?
                symtab.pop
                return v
              end
            else
              s.s.execute(symtab)
            end
          end
          action.execute(symtab)
        end
      rescue ValueError => e
        symtab.pop
        raise e
      end

      symtab.pop
      nil
    end
    alias execute return_value
  end

  class IfAst < AstNode
    include Executable
    include Returns

    # @!macro type_check
    def type_check(symtab)
      level = symtab.levels
      if_cond.type_check(symtab)

      type_error "'#{if_cond.text_value}' is not boolean" unless if_cond.type(symtab).convertable_to?(:boolean)

      symtab.push

      begin
        # only type check the body if it is reachable
        if if_cond.value(symtab) == true
          if_body.elements.each do |e|
            e.e.type_check(symtab)
          end
          return # don't bother with the rest
        end
      rescue ValueError
        # we don't know if the body is reachable; type check it
        if_body.elements.each do |e|
          e.e.type_check(symtab)
        end
      ensure
        symtab.pop
      end

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      unless elseifs.empty?
        elseifs.elements.each do |eif|
          eif.expression.type_check(symtab)
          unless eif.expression.type(symtab).convertable_to?(:boolean)
            type_error "'#{eif.expression.text_value}' is not boolean"
          end

          symtab.push
          begin
            # only type check the body if it is reachable
            if eif.expression.value(symtab) == true
              eif.body.elements.each do |e|
                e.e.type_check(symtab)
              end
              return # don't bother with the rest
            end
          rescue ValueError
            # condition isn't compile-time-known; have to check the body
            eif.body.elements.each do |e|
              e.e.type_check(symtab)
            end
          ensure
            symtab.pop
          end
        end
      end

      return if final_else.empty?

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels

      symtab.push
      final_else.body.elements.each do |e|
        e.e.type_check(symtab)
      end
      symtab.pop

      internal_error "not at same level #{level} #{symtab.levels}" unless level == symtab.levels
    end

    # @return [Boolean] true if the taken path is knowable at compile-time
    # @raise ValueError if the take path is not known at compile time
    def taken_body(symtab)
      return if_body if if_cond.value(symtab)

      unless elseifs.empty?
        elseifs.elements.each do |eif|
          return eif.body if eif.expression.value(symtab)
        end
      end

      final_else.empty? ? nil : final_else.body
    end

    def return_values(symtab)
      begin
        # the if condition is known
        if if_cond.value(symtab)

        else
        end
      rescue ValueError
      end
    end

    def return_value(symtab)

      body = taken_body(symtab)
      return nil if body.nil?

      symtab.push
      begin
        body.elements.each do |e|
          if e.e.is_a?(Returns)
            v = e.e.return_value(symtab)
            unless v.nil?
              return v
            end
          else
            e.e.execute(symtab)
          end
        end
      ensure
        symtab.pop
      end

      nil
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
    include Rvalue

    # @!macro type_check
    def type_check(symtab)
      archdef = symtab.archdef



      if idx.is_a?(IntAst)
        type_error "No CSR at address #{idx.text_value}" if csr_def(symtab).nil?
      else
        # idx is a csr name
        csr_name = idx.text_value
        type_error "No CSR named #{csr_name}" if csr_def(symtab).nil?
      end
      type_error "CSR[#{csr_name(symtab)}] has no field named #{csr_field_name.text_value} on line #{lineno}" if field_def(symtab).nil?
    end

    def csr_def(symtab)
      archdef = symtab.archdef

      if idx.is_a?(IntAst)
        archdef.implemented_csrs.find { |c| c.address == idx.value(symtab) }
      else
        archdef.implemented_csrs.find { |c| c.name == idx.text_value }
      end
    end

    def csr_name(symtab)
      csr_def(symtab).name
    end

    def field_def(symtab)
      csr_def(symtab).implemented_fields.find { |f| f.name == csr_field_name.text_value }
    end

    def field_name(symtab)
      field_def(symtab).name
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
    def type(symtab)
      fd = field_def(symtab)
      if fd.defined_in_all_bases?
        Type.new(:bits, width: [fd.width(32), fd.width(64)].max)
      elsif fd.base64_only?
        Type.new(:bits, width: fd.width(64))
      elsif fd.base32_only?
        Type.new(:bits, width: fd.width(32))
      else
        internal_error "unexpected field base"
      end
    end

    # @!macro value
    def value(symtab)
      value_error "'#{csr_name(symtab)}.#{field_name(symtab)}' is not RO" unless field_def(symtab).type == "RO"
      field_def(symtab).reset_value
    end
  end

  class CsrReadExpressionAst < AstNode
    include Rvalue

    # @!macro type
    def type(symtab)
      archdef = symtab.archdef

      cd = csr_def(symtab)
      if cd.nil?
        # we don't know anything about this index, so we can only
        # treat this as a generic
        Type.new(:bits, width: archdef.config_params["XLEN"])
      else
        CsrType.new(cd)
      end
    end

    # @!macro type_check
    def type_check(symtab)
      archdef = symtab.archdef

      if !archdef.all_known_csr_names.index { |csr_name| csr_name == idx.text_value }.nil?
        # this is a known csr name
        # nothing else to check

      else
        # this is an expression
        idx.type_check(symtab)
        type_error "Csr index must be integral" unless idx.type(symtab).integral?

        begin
          idx_value = idx.value(symtab)
          csr_index = archdef.csrs.index { |csr| csr.address == idx_value }
          type_error "No csr number '#{idx_value}' was found" if csr_index.nil?
        rescue ValueError
          # OK, index doesn't have to be known
        end
      end
    end

    def csr_def(symtab)
      archdef = symtab.archdef
      if !archdef.all_known_csr_names.index { |csr_name| csr_name == idx.text_value }.nil?
        # this is a known csr name
        csr_index = archdef.csrs.index { |csr| csr.name == idx.text_value }

        archdef.csrs[csr_index]
      else
        # this is an expression
        begin
          idx_value = idx.value(symtab)
          csr_index = archdef.csrs.index { |csr| csr.address == idx_value }

          archdef.csrs[csr_index]
        rescue ValueError
          # we don't know at compile time which CSR this is...
          nil
        end
      end
    end

    def csr_known?(symtab)
      !csr_def(symtab).nil?
    end

    def csr_name(symtab)
      internal_error "No CSR" unless csr_known?(symtab)

      csr_def(symtab).name
    end

    def value(symtab)
      cd = csr_def(symtab)
      value_error "CSR number not knowable" if cd.nil?
      value_error "CSR is not implemented" unless symtab.archdef.implemented_csrs.any? { |icsr| icsr.name == cd.name }
      cd.fields.each { |f| value_error "#{csr_name(symtab)}.#{f.name} not RO" unless f.type == "RO" }

      csr_def(symtab).fields.reduce(0) { |val, f| val | (f.value << f.location.begin) }
    end
  end

  class CsrSoftwareWriteAst < AstNode
    include Executable

    def type_check(symtab)
      archdef = symtab.archdef

      csr.type_check(symtab)
      expression.type_check(symtab)

      return if expression.type(symtab).kind == :bits && expression.type(symtab).width == archdef.config_params["XLEN"]

      type_error "CSR value must be an XReg"
    end

    def csr_known?(symtab)
      csr.csr_known?(symtab)
    end

    def csr_name(symtab)
      csr.csr_name(symtab)
    end

    def value(_symtab)
      value_error "CSR writes are global"
    end

  end

  class CsrSoftwareReadAst < AstNode
    include Rvalue

    def type_check(symtab)
      csr.type_check(symtab)
    end

    def type(symtab)
      archdef = symtab.archdef

      if csr_known?(symtab)
        Type.new(:bits, width: archdef.csr(csr.csr_name(symtab)).length)
      else
        Type.new(:bits, width: archdef.config_params["XLEN"])
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
      value_error "CSR not knowable" unless csr_known?
      cd = csr_def(symtab)
      cd.fields.each { |f| value_error "#{csr_name}.#{f.name} not RO" unless f.type == "RO" }

      value_error "TODO: CSRs with sw_read function"
    end
  end

  class CsrWriteAst < AstNode
    include Executable

    def type_check(symtab)
      if idx.is_a?(IntAst)
        # make sure this value is a defined CSR
        index = symtab.archdef.csrs.index { |csr| csr.address == idx.value(symtab) }
        type_error "No csr number '#{idx.value(symtab)}' was found" if index.nil?
      else
        index = symtab.archdef.csrs.index { |csr| csr.name == idx.text_value }
        type_error "No csr named '#{idx.text_value}' was found" if index.nil?
      end

      symtab.archdef.csrs[index]
    end

    def csr_def(symtab)
      index =
        if idx.is_a?(IntAst)
          # make sure this value is a defined CSR
          symtab.archdef.csrs.index { |csr| csr.address == idx.text_value.to_i }
        else
          symtab.archdef.csrs.index { |csr| csr.name == idx.text_value }
        end

      symtab.archdef.csrs[index]
    end

    def type(symtab)
      CsrType.new(csr_def(symtab))
    end

    def name(symtab)
      csr_def(symtab).name
    end

    def execute(symtab)
      value_error "CSR write"
    end
  end
end
