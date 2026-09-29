# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for parsing, with no IDL compilation or architecture solving.
require "json"
require "udb"
require "udb/resolver"
require "udb/config"
require "udb/version_spec"

root = Pathname.new(ARGV.fetch(0))
resolver = Udb::Resolver.new(root)
results = JSON.parse($stdin.read).map do |data|
  info = Udb::Resolver::ConfigInfo.new(
    name: data.fetch("name"), path: root / "test.yaml", overlay_path: nil,
    unresolved_yaml: data, spec_path: root / "spec", merged_spec_path: root / "spec",
    resolved_spec_path: root / "spec", resolver: resolver
  )
  cfg = Udb::AbstractConfig.create_from_data(data, info)
  selections = []
  if cfg.fully_configured?
    cfg.implemented_extensions.each do |item|
      selections << [item.fetch("name"), "mandatory", ["= #{Udb::VersionSpec.new(item.fetch('version')).canonical}"]]
    end
  elsif cfg.partially_configured?
    [[:mandatory_extensions, "mandatory"], [:non_mandatory_extensions, "optional"], [:prohibited_extensions, "prohibited"]].each do |method, presence|
      cfg.public_send(method).each do |item|
        requirements = Array(item.fetch("version")).map do |value|
          req = Udb::RequirementSpec.new(value)
          "#{req.op} #{req.version_spec.canonical}"
        end
        selections << [item.fetch("name"), presence, requirements]
      end
    end
  end
  {name: cfg.name, mxlen: cfg.mxlen, params: cfg.param_values, extensions: selections}
end
puts JSON.generate(results)
