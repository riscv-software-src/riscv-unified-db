# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "lib/udb/version"

Gem::Specification.new do |s|
  s.name        = "udb"
  s.version     = Udb.version
  s.summary     = "Interface to the RISC-V Unified Database"
  s.description = <<~DESC
    A Ruby interface to the data in the RISC-V Unified Database.
    Contains object models for the data and common functions to
    extract information.
  DESC
  s.date        = Time.now.strftime("%Y-%m-%d")
  s.authors     = ["Derek Hower", "James Ball"]
  s.email       = ["dhower@qti.qualcomm.com", "jamesball@qti.qualcomm.com"]
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

  s.add_dependency "activesupport"
  s.add_dependency "asciidoctor"
  s.add_dependency "awesome_print"
  s.add_dependency "idlc"
  s.add_dependency "json_schemer"
  s.add_dependency "sorbet-runtime"
  s.add_dependency "udb_helpers"

  s.add_development_dependency "yard"
end
