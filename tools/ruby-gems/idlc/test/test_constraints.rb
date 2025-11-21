# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "minitest/autorun"

require "yaml"

require_relative "helpers"
require "idlc"

$root ||= (Pathname.new(__FILE__) / ".." / ".." / ".." / "..").realpath

def to_idl_type(value)
  case value
  when Integer
    width = value.zero? ? 1 : value.bit_length
    Idl::Type.new(:bits, width:)
  when String
    Idl::Type.new(:string)
  when TrueClass, FalseClass
    Idl::Type.new(:boolean)
  when Array
    Idl::Type.new(:array, sub_type: to_idl_type(value[0]))
  else
    raise "Unexepected type"
  end
end

class ConstraintTestFactory
  def self.create(klass_name, yaml_path)
    raise ArgumentError, "klass_name must be a String" unless klass_name.is_a?(String) && klass_name.size > 0
    raise ArgumentError, "klass_name must be uppercase" unless klass_name[0] == klass_name[0].upcase

    # Test IDL constraints
    Object.const_set(klass_name,
      Class.new(Minitest::Test) do
        include TestMixin
        make_my_diffs_pretty!

        def setup
          @symtab = Idl::SymbolTable.new
          @compiler = Idl::Compiler.new
        end

        test_yaml = YAML.load(File.read("#{Kernel.__dir__}/#{yaml_path}"))
        test_yaml["tests"].each_with_index do |test, i|
          define_method "test_#{i}" do
            if test.key?("p")
              @symtab.push(nil)
              test["p"].each do |name, value|
                @symtab.add!(name, Idl::Var.new(name, to_idl_type(value), value))
              end
            end
            constraint_ast = nil
            if test["r"].nil?
              assert_raises Idl::AstNode::TypeError do
                ast = @compiler.compile_constraint(test["c"], @symtab, pass_error: true)
                ast.type_check(@symtab)
              end
            else
              out, err = capture_io do
                constraint_ast = @compiler.compile_constraint(test["c"], @symtab)
                constraint_ast.type_check(@symtab)
              end

              if test["r"]
                assert constraint_ast.satisfied?(@symtab), "Expected '#{constraint_ast.text_value}' to be true"
              else
                refute constraint_ast.satisfied?(@symtab), "Expected '#{constraint_ast.text_value}' to be false"
              end
            end

            @symtab.pop if test.key?("p")
          end
        end
      end
    )
  end
end

# now list all the YAML files that specify constraints to test
ConstraintTestFactory.create("Constraints", "idl/constraints.yaml")
ConstraintTestFactory.create("BadConstraints", "idl/constraint_errors.yaml")
