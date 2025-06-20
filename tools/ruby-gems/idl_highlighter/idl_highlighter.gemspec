# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative 'lib/idl_highlighter/version'

Gem::Specification.new do |s|
  s.name        = "idl_highlighter"
  s.version     = Rouge::Lexers::Idl.version
  s.summary     = "Syntax Highlighter for the ISA Description Language"
  s.description = <<~DESC
    Provides a Rouge Lexer for IDL

    Part of the RISC-V Unified Database project
  DESC
  s.date        = Time.now.strftime("%Y-%m-%d")
  s.authors     = ["Derek Hower"]
  s.email       = ["dhower@qti.qualcomm.com"]
  s.homepage    = "https://github.com/riscv-software-src/riscv-unified-db"
  s.platform    = Gem::Platform::RUBY
  s.files       = Dir["lib/**/*.rb", "LICENSE"]
  s.license     = "BSD-3-Clause-Clear"
  s.metadata    = {
    "homepage_uri"      => "https://github.com/riscv-software-src/riscv-unified-db",
    "mailing_list_uri"  => "https://lists.riscv.org/g/tech-unifieddb",
    "bug_tracker_uri"   => "https://github.com/riscv-software-src/riscv-unified-db/issues"
  }
  s.required_ruby_version = "~> 3.2" # only supported in UDB container

  s.require_paths = ["lib"]

  s.add_dependency "rouge"

  s.add_development_dependency "minitest"
end
