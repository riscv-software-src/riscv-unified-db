# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "lib/gem_versions.rb"
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
    "homepage_uri" => "https://github.com/riscv-software-src/riscv-unified-db",
    "mailing_list_uri" => "https://lists.riscv.org/g/tech-unifieddb",
    "bug_tracker_uri" => "https://github.com/riscv-software-src/riscv-unified-db/issues"
  }
  s.required_ruby_version = "~> 3.2"

  s.require_paths = ["lib"]
  s.bindir = "bin"
  s.executables << "udb"

  s.add_dependency "activesupport"
  s.add_dependency "asciidoctor"
  s.add_dependency "awesome_print"
  s.add_dependency "concurrent-ruby"
  s.add_dependency "idlc"
  s.add_dependency "json_schemer"
  s.add_dependency "numbers_and_words"
  s.add_dependency "pastel"
  s.add_dependency "ruby-minisat", ">= 2.2.0.3"
  s.add_dependency "sorbet-runtime", "= #{UdbGems::SORBET_VERSION}"
  s.add_dependency "terminal-table"
  s.add_dependency "thor"
  s.add_dependency "tilt"
  s.add_dependency "tty-logger"
  s.add_dependency "tty-progressbar"
  s.add_dependency "udb_helpers"

  s.add_development_dependency "rubocop-github"
  s.add_development_dependency "rubocop-minitest"
  s.add_development_dependency "rubocop-performance"
  s.add_development_dependency "rubocop-sorbet"
  s.add_development_dependency "simplecov"
  s.add_development_dependency "simplecov-cobertura"
  s.add_development_dependency "sorbet", "= #{UdbGems::SORBET_VERSION}"
  s.add_development_dependency "tapioca", "= #{UdbGems::TAPIOCA_VERSION}"
  s.add_development_dependency "yard"
  s.add_development_dependency "yard-sorbet"
end
