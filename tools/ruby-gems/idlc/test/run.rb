# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

IDLC_ROOT = (Pathname.new(__dir__) / "..").realpath

require "simplecov"
require "simplecov-cobertura"

SimpleCov.start do
  enable_coverage :branch
  add_filter "/test/"
  root IDLC_ROOT.to_s
  coverage_dir (IDLC_ROOT / "coverage").to_s
  formatter SimpleCov::Formatter::MultiFormatter.new([
    SimpleCov::Formatter::CoberturaFormatter,
    SimpleCov::Formatter::HTMLFormatter,
  ])
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_expressions"
require_relative "test_constraints"
require_relative "test_functions"
require_relative "test_variables"
require_relative "test_cli"
require_relative "test_loops"
