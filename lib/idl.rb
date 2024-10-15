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

    def compile_file(path)
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

      ast.children.each do |child|
        next unless child.is_a?(IncludeStatementAst)

        if child.filename.empty?
          raise SyntaxError, <<~MSG
            While parsing #{path}:#{child.lineno}:

            Empty include statement
          MSG
        end

        include_path =
          if child.filename[0] == "/"
            Pathname.new(child.filename)
          else
            (path.dirname / child.filename)
          end

        unless include_path.exist?
          raise SyntaxError, <<~MSG
            While parsing #{path}:#{child.lineno}:

            Path #{include_path} does not exist
          MSG
        end
        unless include_path.readable?
          raise SyntaxError, <<~MSG
            While parsing #{path}:#{child.lineno}:

            Path #{include_path} cannot be read
          MSG
        end

        include_ast = compile_file(include_path)
        include_ast.set_input_file_unless_already_set(include_path)
        ast.replace_include!(child, include_ast)
      end

      # we may have already set an input file from an include, so only set it if it's not already set
      ast.set_input_file_unless_already_set(path.to_s)

      ast
    end

    # compile a function body, and return the abstract syntax tree
    #
    # @param body [String] Function body source code
    # @param return_type [Type] Expected return type, if known
    # @param symtab [SymbolTable] Symbol table to use for type checking
    # @param name [String] Function name, used for error messages
    # @param input_file [Pathname] Path to the input file this source comes from
    # @param input_line [Integer] Starting line in the input file that this source comes from
    # @param no_rescue [Boolean] Whether or not to automatically catch any errors
    # @return [Ast] The root of the abstract syntax tree
    def compile_func_body(body, return_type: nil, symtab: nil, name: nil, input_file: nil, input_line: 0, no_rescue: false, extra_syms: {}, type_check: true)
      @parser.set_input_file(input_file, input_line)

      m = @parser.parse(body, root: :function_body)
      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{name} at #{input_file}:#{input_line + @parser.failure_line}

          #{@parser.failure_reason}
        MSG
      end

      # fix up left recursion
      ast = m.to_ast
      ast.set_input_file(input_file, input_line)
      ast.freeze_tree(symtab)

      # type check
      unless type_check == false
        cloned_symtab = symtab.deep_clone

        cloned_symtab.push(ast)
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

      end

      ast
    end

    # compile an instruction operation, and return the abstract syntax tree
    #
    # @param inst [Instruction] Instruction object
    # @param symtab [SymbolTable] Symbol table
    # @param input_file [Pathname] Path to the input file this source comes from
    # @param input_line [Integer] Starting line in the input file that this source comes from
    # @return [Ast] The root of the abstract syntax tree
    def compile_inst_operation(inst, symtab:, input_file: nil, input_line: 0)
      operation = inst["operation()"]
      @parser.set_input_file(input_file, input_line)

      m = @parser.parse(operation, root: :instruction_operation)
      if m.nil?
        raise SyntaxError, <<~MSG
          While parsing #{input_file}:#{input_line + @parser.failure_line}

          #{@parser.failure_reason}
        MSG
      end

      # fix up left recursion
      ast = m.to_ast
      ast.set_input_file(input_file, input_line)
      ast.freeze_tree(symtab)

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
      raise "Tree should be frozen" unless ast.frozen?

      begin
        value_result = AstNode.value_try do
          ast.type_check(symtab)
        end
        AstNode.value_else(value_result) do
          warn "While type checking #{what}, got a value error on:"
          warn ast.text_value
          warn AstNode.value_error_reason
          warn symtab.callstack
          unless AstNode.value_error_ast.nil?
            warn "At #{AstNode.value_error_ast.input_file}:#{AstNode.value_error_ast.lineno}"
          end
          exit 1
        end
      rescue AstNode::InternalError => e
        warn "While type checking #{what}:"
        warn e.what
        warn e.backtrace
        exit 1
      end

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
      ast.set_input_file("[EXPRESSION]", 0)
      ast.freeze_tree(symtab)
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


      ast
    end
  end
end
