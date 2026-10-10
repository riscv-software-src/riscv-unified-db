# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "json"
require "pathname"
require "tmpdir"
require "udb"

root = Pathname.new(ARGV.fetch(0))
gemroot = root / "tools/ruby-gems/udb"
resolver = Udb::Resolver.new(
  schemas_path_override: root / "spec/schemas",
  cfgs_path_override: gemroot / "test/mock_cfgs",
  gen_path_override: Pathname.new(Dir.mktmpdir),
  std_path_override: gemroot / "test/mock_spec/isa",
  quiet: true
)

results = JSON.parse($stdin.read).to_h do |name|
  architecture = resolver.cfg_arch_for(name)
  [
    name,
    {
      possible_versions: architecture.possible_extension_versions.map do |version|
        "#{version.name}@#{version.version_spec.canonical}"
      end.sort,
      params_with_value: architecture.params_with_value.map(&:name).sort,
      params_without_value: architecture.params_without_value.map(&:name).sort
    }
  ]
end

puts JSON.generate(results)
