# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "idlc"
require "optparse"

module Idl
  # Command line interface
  class Cli
    def initialize(argv)
      @argv = argv
      @options = {
        dump_ast: false,
        output: $stdout,
        defines: []
      }
      @compiler = Compiler.new
    end

    def run
      parse_options

      symtab = SymbolTable.new(nil)

      # load defines
      @options[:defines].each do |name, value_str|
        expr_ast = @compiler.compile_expression(value_str, symtab)
        symtab.add!(name, Var.new(name, expr_ast.type(symtab), expr_ast.value(symtab)))
      end

      if !@options[:input_file].nil?

        ast =
          if !@options[:key].nil?
            yaml_contents = YAML.load(@options[:input].read)
            raise "#{file} has no key named '#{@options[:key]}'" unless yaml_contents.key?(@options[:key])

            if @options[:key] == "operation()"
              @compiler.compile_inst_operation(yaml_contents, symtab:)
            else
              @compiler.compile_func_body(yaml_contents[@options[:key]], symtab:)
            end
          else
            @compiler.compile_file(Pathname.new(@options[:input]))
          end
      elsif !@options[:eval].nil?
        expr_ast = @compiler.compile_expression(@options[:eval], symtab)
        @options[:output].puts expr_ast.value(symtab)
      end

      @options[:output].puts ast.to_idl if @options[:dump_ast]

      exit if @options[:dump_ast]
    end

    def parse_options
      optparser = OptionParser.new do |opts|
        opts.banner = <<~BANNER
          Usage: idlc [options]
        BANNER

        opts.on("-a", "--ast", "Dump the ast as YAML, then exit") do
          @options[:dump_ast] = true
        end

        opts.on("-D", "--define NAME=VALUE", "Define a global variable") do |var_and_value|
          name, value_str = var_and_value.split("=", 2)
          @options[:defines] << [name, value_str]
        end

        opts.on("-e", "--eval IDL",
                "Compile IDL as an expression, and print it's evaluated value. Cannot be used with -i") do |idl|
          @options[:eval] = idl
        end

        opts.on("-i", "--input FILE", "Read input from FILE. If not specified, read from stdin") do |file|
          raise "File #{file} does not exist" unless File.exist?(file)

          @options[:input_file] = file
        end

        opts.on("-f", "--output-format FORMAT", [:idl, :yaml], "Output format. One of: idl, yaml. Default: idl") do |format|
          @options[:output_format] = format
        end

        opts.on("-o", "--output FILE", "Write output to FILE. If not specified, output is written to stdout") do |file|
          @options[:output] = File.open(file, "w")
        end

        opts.on("-k", "--key KEY_NAME", "When input FILE is YAML, select the key to use as IDL source") do |key|
          @options[:key] = key
        end

        opts.on("-h", "--help", "Prints this help") do
          puts opts
          exit
        end

        opts.separator ""
        opts.separator "Examples:"
        opts.separator ""
        opts.separator <<~EXAMPLES
          # Evaluate an expression
          #{opts.program_name} -D A=5 -D B=10 -e "A + B" # => 15
          #{opts.program_name} -D A=5 -D B=10 -e "A > B" # => false
        EXAMPLES
      end.parse!(@argv)

      raise "Unexpected argument(s): #{@argv.join(' ')}" if !@argv.empty?

      if @argv.empty?
        @options[:input] = "-"
      elsif @argv.size == 1
        if File.extname(@argv[0]) == ".yaml" && !@options.key?(:key)
          raise "Must specify a key (-k KEY_NAME) when using a YAML file"
        end

        raise "File #{@argv[0]} does not exist" unless File.exist?(@argv[0])

        @options[:input] = @argv[0]
      else
        puts "Only one input file can be specified"
        puts optparser
        exit
      end
    end

    def self.run(argv)
      Cli.new(argv).run
    end
  end
end
