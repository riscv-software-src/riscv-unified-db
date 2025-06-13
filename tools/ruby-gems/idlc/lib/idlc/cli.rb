# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "idlc"
# require "gli"
require "commander"
require "forwardable"
require "optparse"
require "yaml"

module Idl
  class Cli
    extend Forwardable
    def_delegators :@runner,
      :alias_command,
      :always_trace!,
      :command,
      :default_command,
      :global_option,
      :never_trace!,
      :program,
      :run!

    def initialize(args)
      @defines = {}
      @runner = Commander::Runner.new(args)
    end

    def add_defines(compiler, symtab)
      @defines.each do |name, value_str|
        expr_ast = compiler.compile_expression(value_str, symtab)
        symtab.add!(name, Var.new(name, expr_ast.type(symtab), expr_ast.value(symtab)))
      end
    end

    def do_eval(args, options)
      if args.size != 1
        if args.empty?
          warn "Missing expression to evaluate"
        else
          warn "Unexpected arguments: #{args[1..]}"
        end
        @runner.commands["help"].run
        exit 1
      end

      compiler = Compiler.new
      symtab = SymbolTable.new

      add_defines(compiler, symtab)
      expr_ast = compiler.compile_expression(args[0], symtab)

      case options.output
      when "-"
        $stdout.puts expr_ast.value(symtab)
      else
        f = File.open(options.output, "w")
        f.puts expr_ast.value(symtab)
      end
    end

    def do_tc_inst(args, options, vars)
      compiler = Compiler.new
      symtab = SymbolTable.new

      add_defines(compiler, symtab)
      symtab.push(nil)

      vars.each do |name, width|
        symtab.add!(name, Var.new(name, Type.new(:bits, width: width.to_i), decode_var: true))
      end

      io =
        if args[0] == "-"
          $stdin
        else
          File.open(args[0], "r")
        end

      idl =
        if !options.key.nil?
          yaml_contents = YAML.safe_load(io.read, permitted_classes: [String, Array, Hash], permitted_symbols: [])
          raise "#{args[0]} has no key named '#{options.key}'" unless yaml_contents.key?(options.key)

          yaml_contents[options.key]
        else
          io.read
        end

      ast = compiler.compile_inst_scope(idl, symtab:, input_file: args[0])
      ast.type_check(symtab)
    end

    def run
      default_command :help

      program :name, "IDL Compiler"
      program :version, Idl::Compiler.version
      program :description, "Command line for the IDL reference compiler"

      add_define_option = lambda do |c|
        c.option "-D,--define PARM_NAME=PARAM_VALUE", (<<~DESC
          Define a parameter (e.g., -DMXLEN=64).
          PARAM_VALUE can be any IDL expression with a knowable value
        DESC
        ) do |varandval|
          raise ArgumentError, "Define (#{varandval}) must be in the format VAR=VAL" unless varandval =~ /.+=.+/

          var, val = varandval.split("=")
          @defines[var] = val
        end
      end

      command :eval do |c|
        c.syntax = "idlc eval [options] EXPRESSION"
        c.summary = "Evaluate an IDL expression"
        c.example "Print '15'", "idlc eval -DA=5 -DB=10 A+B"

        c.option "-o,--output FILE", String, "Output file (- for STDOUT)"
        add_define_option.call(c)

        c.action do |args, options|
          options.default output: "-"
          do_eval(args, options)
        end
      end

      command "tc inst" do |c|
        vars = {}
        c.syntax = "idlc tc inst [options] FILE"
        c.summary = "Type check an instruction 'operation()' block. Exits 0 if type checking succeeds, 1 otherwise."
        c.example "Exit 0", "idlc tc inst -k 'operation()' -v xs1=5 -v xs2=5 -v xd=5 add.yaml"
        c.example "Exit 1 (variables not defined)", "idlc tc inst -k 'operation()' add.yaml"
        c.example "Exit 0", "echo 'X[2] = 15;' | idlc tc inst -"

        add_define_option.call(c)
        c.option "-k", "--key KEY", String, "When FILE is a YAML file, type check just the contents of KEY"
        c.option "-d", "--var NAME=WIDTH", (<<~DESC
          Define decode variable, e.g., xs2=5
          NAME is the name of the variable, and must be a valid IDL identifier
          WIDTH is the bit width of the variable, and must be an integer
        DESC
        ) do |nameandwidth|
          unless nameandwidth =~ /.+=.+/
            raise ArgumentError, "Define (#{nameandwidth}) must be in the format NAME=WIDTH"
          end

          name, width = nameandwidth.split("=")
          vars[name] = width.to_i
        end

        c.action do |args, options|
          if args.size != 1
            if args.empty?
              warn "Missing file to type check"
            else
              warn "Unexpected arguments: #{args[1..]}"
            end
            @runner.commands["help"].run
            exit 1
          end

          do_tc_inst(args, options, vars)
        end
      end

      run!
    end
  end
end
