# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for the Ruby condition implementation.

require "json"
require "pathname"
require "tmpdir"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/udb/lib").to_s)
require "udb"

input = JSON.parse($stdin.read)
gem_root = repo_root / "tools/ruby-gems/udb"
resolver = Udb::Resolver.new(
  schemas_path_override: repo_root / "spec/schemas",
  cfgs_path_override: gem_root / "test/mock_cfgs",
  gen_path_override: Pathname.new(Dir.mktmpdir),
  std_path_override: gem_root / "test/mock_spec/isa",
  quiet: true
)
architecture = resolver.cfg_arch_for(input.fetch("config", "_"))

results = input.fetch("conditions").map do |data|
  condition = Udb::Condition.new(data, architecture)
  {
    "data" => condition.to_h,
    "evaluation" => condition.satisfied_by_cfg_arch?(architecture).serialize,
    "satisfiable" => condition.satisfiable?
  }
end

puts JSON.generate(results)
