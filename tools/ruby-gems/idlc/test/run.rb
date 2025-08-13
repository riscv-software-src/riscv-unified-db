# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

IDLC_ROOT = (Pathname.new(__dir__) / "..").realpath

# force the parser to rebuild once
parser_rb = IDLC_ROOT / "lib" / "idlc" / "idl_parser.rb"
FileUtils.rm parser_rb if parser_rb.exist?

require "simplecov"
require "simplecov-cobertura"

SimpleCov.start do
  enable_coverage :branch
  root IDLC_ROOT.to_s
  coverage_dir (IDLC_ROOT / "coverage").to_s
  add_filter "/test/"
  formatter SimpleCov::Formatter::MultiFormatter.new([
    SimpleCov::Formatter::CoberturaFormatter,
    SimpleCov::Formatter::HTMLFormatter
  ])
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_expressions"
require_relative "test_cli"
require_relative "test_loops"
