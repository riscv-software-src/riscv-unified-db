# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "lib/gem_versions.rb"
require_relative "lib/udb-gen/version"

Gem::Specification.new do |s|
  s.name        = "udb-gen"
  s.version     = UdbGen.version
  s.summary     = "Command line interface for UDB-based generators"
  s.description = <<~DESC
    A tool to generate artifacts using UDB data
  DESC
  s.date        = Time.now.strftime("%Y-%m-%d")
  s.authors     = ["Derek Hower"]
  s.email       = ["dhower@qti.qualcomm.com"]
  s.homepage    = "https://github.com/riscv-software-src/riscv-unified-db"
  s.platform    = Gem::Platform::RUBY
  s.files       = Dir["lib/**/*.rb", "templates/*.erb", "LICENSE"]
  s.license     = "BSD-3-Clause-Clear"
  s.metadata    = {
    "homepage_uri" => "https://github.com/riscv-software-src/riscv-unified-db",
    "mailing_list_uri" => "https://lists.riscv.org/g/tech-unifieddb",
    "bug_tracker_uri" => "https://github.com/riscv-software-src/riscv-unified-db/issues"
  }
  s.required_ruby_version = "~> 3.2"

  s.require_paths = ["lib"]
  s.bindir = "bin"
  s.executables << "udb-gen"

  s.add_dependency "sorbet-runtime", "= #{UdbGems::SORBET_VERSION}"
  s.add_dependency "tty-exit"
  s.add_dependency "tty-option"
  s.add_dependency "tty-progressbar"
  s.add_dependency "tty-table"
  s.add_dependency "udb"
  s.add_dependency "write_xlsx"

  s.add_development_dependency "sorbet", "= #{UdbGems::SORBET_VERSION}"
  s.add_development_dependency "tapioca", "= #{UdbGems::TAPIOCA_VERSION}"
end
