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
  s.homepage    = "https://github.com/riscv/riscv-unified-db"
  s.files       = Dir["lib/**/*.rb", "LICENSE", "ext/udb_download/extconf.rb", "lib/udb/Z3_VERSION", "lib/udb/ESPRESSO_VERSION", "lib/udb/MUST_VERSION", "lib/udb/EQNTOTT_VERSION", ".data/**/*"]
  s.extensions  = ["ext/udb_download/extconf.rb"]
  s.license     = "BSD-3-Clause-Clear"
  s.metadata    = {
    "homepage_uri" => "https://github.com/riscv/riscv-unified-db",
    "mailing_list_uri" => "https://lists.riscv.org/g/sig-unifieddb",
    "bug_tracker_uri" => "https://github.com/riscv/riscv-unified-db/issues"
  }
  s.required_ruby_version = "~> 3.2"
  s.require_paths = ["lib"]
  s.bindir = "bin"
  s.executables << "udb"

  s.add_dependency "activesupport"
  s.add_dependency "asciidoctor"
  s.add_dependency "awesome_print"
  s.add_dependency "concurrent-ruby"
  s.add_dependency "idlc", "= 0.1.8"
  s.add_dependency "json_schemer"
  s.add_dependency "numbers_and_words"
  s.add_dependency "ostruct"
  s.add_dependency "pastel"
  s.add_dependency "rubyzip"
  s.add_dependency "sorbet-runtime"
  s.add_dependency "terminal-table"
  s.add_dependency "thor"
  s.add_dependency "tilt"
  s.add_dependency "tty-command"
  s.add_dependency "tty-logger"
  s.add_dependency "tty-progressbar"
  s.add_dependency "udb_helpers", "= 0.1.4"
  s.add_dependency "z3"

  s.add_development_dependency "rake"
  s.add_development_dependency "rubocop-github"
  s.add_development_dependency "rubocop-minitest"
  s.add_development_dependency "rubocop-performance"
  s.add_development_dependency "rubocop-sorbet"
  s.add_development_dependency "simplecov"
  s.add_development_dependency "simplecov-cobertura"
  s.add_development_dependency "sorbet"
  s.add_development_dependency "tapioca", ">= 0.17.10"
  s.add_development_dependency "yard"
  s.add_development_dependency "yard-sorbet"
end
