# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

IDLC_ROOT = (Pathname.new(__dir__) / "..").realpath

require "simplecov"
require "simplecov-cobertura"

SimpleCov.start do
  enable_coverage :branch
  root IDLC_ROOT.to_s
  coverage_dir (IDLC_ROOT / "coverage").to_s
  formatter SimpleCov::Formatter::CoberturaFormatter
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_expressions"
require_relative "test_cli"
require_relative "test_loops"
