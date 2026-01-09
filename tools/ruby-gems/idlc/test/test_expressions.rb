# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"

require "yaml"

require_relative "helpers"
require "idlc"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

class ExpressionTestFactory
  def self.create(klass_name, yaml_path)
    raise ArgumentError, "klass_name must be a String" unless klass_name.is_a?(String) && klass_name.size > 0
    raise ArgumentError, "klass_name must be uppercase" unless klass_name[0] == klass_name[0].upcase

    # Test IDL expressions
    Object.const_set(klass_name,
      Class.new(Minitest::Test) do
        include TestMixin
        make_my_diffs_pretty!

        def setup
          @symtab = Idl::SymbolTable.new
          @compiler = Idl::Compiler.new
        end

        exprs = YAML.load(File.read("#{Kernel.__dir__}/#{yaml_path}"))
        exprs["tests"].each_with_index do |expr, i|
          define_method "test_#{i}" do
            if expr.key?("p")
              @symtab.push(nil)
              expr["p"].each do |name, value|
                case value
                when Integer
                  width = value.zero? ? 1 : value.bit_length
                  @symtab.add!(name, Idl::Var.new(name, Idl::Type.new(:bits, width:), value))
                when String
                  @symtab.add!(name, Idl::Var.new(name, Idl::Type.new(:string), value))
                when TrueClass, FalseClass
                  @symtab.add!(name, Idl::Var.new(name, Idl::Type.new(:boolean), value))
                else
                  raise "Unexepected type"
                end
              end
            end
            expr_ast = nil
            out, err = capture_io do
              expr_ast = @compiler.compile_expression(expr["e"], @symtab)
            end

            # assert_empty out, expr["d"]
            # assert_empty err, expr["d"]

            expr_value = nil
            out, err = capture_io do
              expr_value = expr_ast.value(@symtab)
            end
            # assert_empty out
            # if expr["w"]
            #   assert_equal expr["w"].strip, err.strip, expr["d"]
            # else
            #   assert_empty err, expr["d"]
            # end

            result_ast = @compiler.compile_expression(expr["="], @symtab)

            assert_equal result_ast.value(@symtab), expr_value, expr["d"]
            # assert_equal expr["="], result_ast.to_idl_verbose, expr["d"]

            @symtab.pop if expr.key?("p")
          end
        end

        # def test_that_operators_are_left_recusrive
        #   idl = <<~IDL.strip
        #     4 - 3 - 1
        #   IDL

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 0, ast.value(@symtab)
        #   assert_equal "((4 - 3) - 1)", ast.to_idl
        # end

        # def test_that_values_are_tuncated
        #   idl = <<~IDL.strip
        #     a + b
        #   IDL
        #   @symtab.add("a", Idl::Var.new("a", Idl::Type.new(:bits, width:4), 0xf))
        #   @symtab.add("b", Idl::Var.new("b", Idl::Type.new(:bits, width:4), 0x1))

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 0, ast.value(@symtab)

        #   idl = <<~IDL.strip
        #     4'hf + 5'h1
        #   IDL

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 16, ast.value(@symtab)
        # end

        # def test_that_const_values_are_not_tuncated
        #   idl = <<~IDL.strip
        #     4'hf + 4'h1
        #   IDL

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 0x10, ast.value(@symtab)

        #   idl = <<~IDL.strip
        #     4'hf + 5'h1
        #   IDL

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 16, ast.value(@symtab)
        # end

        # def test_that_multplication_is_higher_precedence_than_addition
        #   idl = <<~IDL.strip
        #     4 + 5'd3 * 2
        #   IDL

        #   ast = @compiler.compile_expression(idl, @symtab)
        #   warn ast.value(@symtab)
        #   refute_equal 14, ast.value(@symtab)
        #   assert_equal 10, ast.value(@symtab)
        # end

        # def test_that_integer_literals_give_correct_values
        #   idl = "8'd13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   idl = "16'hd"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   idl = "12'o15"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   idl = "4'b1101"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   idl = "-8'sd13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal(-13, ast.value(@symtab))

        #   idl = "-16'shd"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal(-13, ast.value(@symtab))

        #   idl = "-12'so15"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal(-13, ast.value(@symtab))

        #   idl = "-4'sb1101"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

        #   idl = "4'sb1101"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

        #   idl = "32'h80000000"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 0x80000000, ast.value(@symtab)

        #   idl = "32'h8000_0000"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 0x80000000, ast.value(@symtab)

        #   idl = "8'13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   # 13 decimal, unsigned XLEN-bit wide
        #   idl = "'13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   # 13 decimal, signed XLEN-bit wide
        #   idl = "'s13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 13, ast.value(@symtab)

        #   # compilation error: 300 does not fit in 8 bits
        #   idl = "8'h1_0000_0000"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

        #   # 3 decimal: the literal is 13, unsigned, in 4-bits. when negated, the sign bit is lost
        #   idl = "-4'd13"
        #   ast = @compiler.compile_expression(idl, @symtab)
        #   assert_equal 3, ast.value(@symtab)

        #   # compilation error: 300 does not fit in 8 bits
        #   idl = "8'sd300"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

        #   # compilation error: bit width must be positive
        #   idl = "0'15"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }

        #   # compilation error: value does not fit in four bita
        #   idl = "4'hff"
        #   assert_raises(Idl::AstNode::TypeError) { @compiler.compile_expression(idl, @symtab, pass_error: true) }
        # end
      end
    )
  end
end

# now list all the YAML files that specify expressions to test
ExpressionTestFactory.create("Literals", "idl/literals.yaml")
ExpressionTestFactory.create("Expressions", "idl/expressions.yaml")
