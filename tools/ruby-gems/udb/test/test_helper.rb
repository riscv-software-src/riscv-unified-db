# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "simplecov"
require "simplecov-cobertura"

UDB_ROOT = (Pathname.new(__dir__) / "..").realpath

unless SimpleCov.running
  SimpleCov.start do
    enable_coverage :branch
    add_filter "/test/"
    root UDB_ROOT.to_s
    coverage_dir (UDB_ROOT / "coverage").to_s
    enable_coverage_for_eval
    formatter SimpleCov::Formatter::MultiFormatter.new([
      SimpleCov::Formatter::CoberturaFormatter,
      SimpleCov::Formatter::HTMLFormatter,
    ])
  end

  puts "[SimpleCov] Coverage started."
end

require "minitest/autorun"
