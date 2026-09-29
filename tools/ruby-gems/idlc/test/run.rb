# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "pathname"

IDLC_ROOT = (Pathname.new(__dir__) / "..").realpath

require "simplecov"
require "simplecov-cobertura"

SimpleCov.start do
  enable_coverage :branch
  skip "/test/"
  root IDLC_ROOT.to_s
  coverage_dir (IDLC_ROOT / "coverage").to_s
  formatter SimpleCov::Formatter::MultiFormatter.new([
    SimpleCov::Formatter::CoberturaFormatter,
    SimpleCov::Formatter::HTMLFormatter,
  ])
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_arrays"
require_relative "test_ast_type"
require_relative "test_cli"
require_relative "test_const_function_arguments"
require_relative "test_constraints"
require_relative "test_control_flow"
require_relative "test_expressions"
require_relative "test_functions"
require_relative "test_loops"
require_relative "test_prune"
require_relative "test_std"
require_relative "test_strictness_and_unknowns"
require_relative "test_type_checking_comprehensive"
require_relative "test_type_checking_data_driven"
require_relative "test_type_to_idl"
require_relative "test_values"
require_relative "test_variables"
require_relative "test_control_flow"
require_relative "test_reserved_words"
require_relative "test_register_files"
