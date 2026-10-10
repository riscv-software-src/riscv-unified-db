# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional, narrowly scoped artifact oracle. Stdout is only the full header.
require "pathname"
require "json"
require "udb"
require "udb/resolver"
require "udb-gen/generators/cfg_c_header/generator"
require "udb-gen/generators/cfg_svh_header/generator"

root = Pathname.new(ARGV.fetch(0))
generator = ARGV.fetch(1) == "c" ? UdbGen::GenCfgCHeaderOptions.new : UdbGen::GenCfgSvhHeaderOptions.new
if ARGV[2] && !["_", "rv32", "rv64"].include?(ARGV[2])
  # Typed architecture test double: only the input accessors are substituted.
  # All comments, guards, literals, sorting, and macro dispatch are genuine Ruby.
  class HeaderFixtureArchitecture < Udb::ConfiguredArchitecture
    def initialize(data)
      @fixture = data
    end

    def fully_configured? = true
    def name = @fixture.fetch("name")
    def param_values = @fixture.fetch("params")
    def implemented_extension_versions = []
  end
  architecture = HeaderFixtureArchitecture.new(JSON.parse(File.read(ARGV.fetch(2))))
  generator.define_singleton_method(:cfg_arch) { architecture }
else
  resolver = Udb::Resolver.new(root, gen_path_override: root / "gen" / "header-ruby-oracle")
  generator.instance_variable_set(:@resolver, resolver)
  generator.parse(["--cfg", ARGV[2] || "mc100-32-full-example"])
end
$stdout.write(generator.generate_header)
