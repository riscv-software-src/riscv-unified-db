# Copyright (c) Jordan Carlin, Harvey Mudd College.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
require "tty-exit"

require_relative "../../common_opts"
require_relative "../../defines"
require_relative "../../cfg_header_base"

module UdbGen
  class GenCfgCHeaderOptions < SubcommandWithCommonOptions
    include TTY::Exit
    include CfgHeaderBase

    NAME = "cfg-c-header"

    sig { void }
    def initialize
      super(name: NAME, desc: "Generate a C header with #defines from a fully configured UDB config")
    end

    usage \
      command: NAME,
      desc: "Generate a C header file with #define directives derived from a fully configured UDB YAML config",
      example: <<~EXAMPLE
        Generate a C header for the rv64 config, printed to stdout
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -c rv64

        Generate a C header for the rv64 config, written to a file
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -c rv64 -o config.h

        Generate a C header for a custom config file
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -c /path/to/my_config.yaml
      EXAMPLE

    option :output do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-o"
      long "--output=file"
      desc "Output file path (default: stdout)"
      convert :path
    end

    sig { override.returns(String) }
    def define_directive = "#define"

    sig { override.returns(String) }
    def command_name = NAME

    sig { override.params(guard_name: String).returns(String) }
    def guard_begin(guard_name) = "#ifndef #{guard_name}"

    sig { override.params(guard_name: String).returns(String) }
    def guard_end(guard_name) = "#endif /* #{guard_name} */"

    sig { override.returns(String) }
    def guard_suffix = "_H"

    sig { override.params(text: String).returns(String) }
    def section_comment(text) = "/* #{text} */"

    sig { override.params(text_lines: T::Array[String]).returns(T::Array[String]) }
    def header_comment(text_lines)
      lines = ["/*"]
      text_lines.each do |line|
        lines << (line.empty? ? " *" : " * #{line}")
      end
      lines << " */"
      lines
    end

    sig { override.returns(String) }
    def file_type_name = "C header"

    sig { override.params(value: Integer).returns(String) }
    def format_integer(value)
      # Values above the signed 64-bit range need an unsigned suffix
      value.bit_length > 63 ? "#{value}ULL" : value.to_s
    end

    sig { override.params(value: Integer).returns(String) }
    def format_mask(value) = "0x#{value.to_s(16).upcase}"

    sig { override.params(argv: T::Array[String]).returns(T.noreturn) }
    def run(argv)
      run_generator(argv)
    end
  end
end
