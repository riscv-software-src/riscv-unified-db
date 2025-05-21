# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "lib/udb_helpers/version"

Gem::Specification.new do |s|
  s.name        = "udb_helpers"
  s.version     = Udb::Helpers.version
  s.summary     = "Misc helpers for UDB generators"
  s.description = <<~DESC
    Various utilities to help with generating artifacts from UDB.
  DESC
  s.date        = Time.now.strftime("%Y-%m-%d")
  s.authors     = ["Derek Hower", "James Ball", "Afonso Olivera"]
  s.email       = ["dhower@qti.qualcomm.com", "jamesball@qti.qualcomm.com", "Afonso.Oliveira@synopsys.com"]
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

  s.add_development_dependency "yard"
end
