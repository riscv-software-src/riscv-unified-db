# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "simplecov"

UDB_ROOT = (Pathname.new(__dir__) / "..").realpath

SimpleCov.start do
  enable_coverage :branch
  add_filter "/test/"
  root UDB_ROOT.to_s
  coverage_dir (UDB_ROOT / "coverage").to_s
  formatter SimpleCov::Formatter::MultiFormatter.new([
    SimpleCov::Formatter::CoberturaFormatter,
    SimpleCov::Formatter::HTMLFormatter,
  ])
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_logic"
require_relative "test_conditions"
require_relative "test_cli"
require_relative "test_yaml_loader"
