# frozen_string_literal: true

require "treetop"

module Treetop
  module Runtime
    # open up Treetop::Runtime::CompiledParser and add a few utility functions
    # so we can track where the code is coming from
    class CompiledParser
      attr_reader :input_file

      def set_input_file(filename, starting_line = 0)
        @input_file = filename
        @starting_line = starting_line
      end

      # alias instantiate_node so we can call it from the override
      alias orig_instantiate_node instantiate_node

      # override instatiate_node so we can set the input file
      def instantiate_node(node_type, *args)
        node = orig_instantiate_node(node_type, *args)
        node.set_input_file(input_file, @starting_line.nil? ? 0 : @starting_line)
        node
      end
    end
  end
end

require_relative "idl/ast"
require_relative "idl/symbol_table"

Treetop.load(($root / "lib" / "idl" / "idl").to_s)

module Idl
  # the Idl compiler
  class Compiler
    # @param arch_def [ArchDef] Architecture defintion, the context of the compilation
    def initialize(arch_def)
      @parser = IdlParser.new
      @arch_def = arch_def
    end

    def compile_file(path, symtab: nil, type_check: true)
      @parser.set_input_file(path.to_s)

      m = @parser.parse path.read

      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{@parser.input_file}:#{@parser.failure_line}:#{@parser.failure_column}

          #{@parser.failure_reason}
        MSG
      end

      raise "unexpected type #{m.class.name}" unless m.is_a?(IsaSyntaxNode)

      ast = m.to_ast

      ast.set_input_file(path.to_s)
      if type_check
        begin
          ast.type_check(symtab)
        rescue AstNode::TypeError, AstNode::InternalError => e
          warn e.what
          warn e.bt
          exit 1
        end
        ast.freeze_tree
      end

      ast
    end

    # compile a function body, and return the abstract syntax tree
    #
    # @param body [String] Function body source code
    # @param return_type [Type] Expected return type, if known
    # @param symtab [SymbolTable] Symbol table to use for type checking
    # @param name [String] Function name, used for error messages
    # @param parent [String] Parent class of the function, used for error messages
    # @param input_file [Pathname] Path to the input file this source comes from
    # @param input_line [Integer] Starting line in the input file that this source comes from
    # @param no_rescue [Boolean] Whether or not to automatically catch any errors
    # @return [Ast] The root of the abstract syntax tree
    def compile_func_body(body, return_type: nil, symtab: SymbolTable.new, name: nil, parent: nil, input_file: nil, input_line: 0, no_rescue: false, extra_syms: {})
      @parser.set_input_file(input_file, input_line)

      cloned_symtab = symtab.deep_clone

      m = @parser.parse(body, root: :function_body)
      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{parent}::#{name} #{@parser.failure_line}:#{@parser.failure_column}

          #{@parser.failure_reason}
        MSG
      end

      # fix up left recursion
      ast = m.to_ast

      # type check
      cloned_symtab.push
      cloned_symtab.add("__expected_return_type", return_type) unless return_type.nil?

      extra_syms.each { |k, v|
        cloned_symtab.add(k, v)
      }

      begin
        ast.statements.each do |s|
          s.type_check(cloned_symtab)
        end
      rescue AstNode::TypeError => e
        raise e if no_rescue

        if name && parent
          warn "In function #{name} of #{parent}:"
        elsif name && parent.nil?
          warn "In function #{name}:"
        end
        warn e.what
        exit 1
      rescue AstNode::InternalError => e
        raise if no_rescue

        if name && parent
          warn "In function #{name} of #{parent}:"
        elsif name && parent.nil?
          warn "In function #{name}:"
        end
        warn e.what
        warn e.backtrace
        exit 1
      ensure
        cloned_symtab.pop
      end

      ast.freeze_tree

      ast
    end

    # compile an instruction operation, and return the abstract syntax tree
    #
    # @param inst [Instruction] Instruction object
    # @param symtab [SymbolTable] Symbol table to use for type checking
    # @param input_file [Pathname] Path to the input file this source comes from
    # @param input_line [Integer] Starting line in the input file that this source comes from
    # @return [Ast] The root of the abstract syntax tree
    def compile_inst_operation(inst, input_file: nil, input_line: 0)
      operation = inst["operation()"]
      @parser.set_input_file(input_file, input_line)

      m = @parser.parse(operation, root: :instruction_operation)
      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{input_file}:#{@parser.failure_line}:#{@parser.failure_column}

          #{@parser.failure_reason}
        MSG
      end

      # fix up left recursion
      ast = m.to_ast
      ast.set_input_file("Inst #{inst.name} (#{input_file})", input_line)
      ast.freeze_tree

      ast
    end

    # Type check an abstract syntax tree
    #
    # @param ast [AstNode] An abstract syntax tree
    # @param symtab [SymbolTable] The compilation context
    # @param what [String] A description of what you are type checking (for error messages)
    # @raise AstNode::TypeError if a type error is found
    def type_check(ast, symtab, what)
      # type check
      begin
        ast.type_check(symtab)
      rescue AstNode::TypeError => e
        warn "While type checking #{what}:"
        warn e.what
        exit 1
      rescue AstNode::InternalError => e
        warn "While type checking #{what}:"
        warn e.what
        warn e.backtrace
        exit 1
      end

      ast.freeze_tree

      ast
    end

    def compile_expression(expression, symtab, pass_error: false)
      m = @parser.parse(expression, root: :expression)
      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{expression}:#{@parser.failure_line}:#{@parser.failure_column}

          #{@parser.failure_reason}
        MSG
      end

      ast = m.to_ast
      begin
        ast.type_check(symtab)
      rescue AstNode::TypeError => e
        raise e if pass_error

        warn "Compiling #{expression}"
        warn e.what
        warn e.backtrace
        exit 1
      rescue AstNode::InternalError => e
        raise e if pass_error

        warn "Compiling #{expression}"
        warn e.what
        warn e.backtrace
        exit 1
      end

      ast.freeze_tree

      ast
    end
  end
end
