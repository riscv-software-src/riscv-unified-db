# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "json"
require "pathname"
require "udb"
require "udb/resolver"

architecture = Udb::Resolver.new(Pathname.new(ARGV.fetch(0))).cfg_arch_for("_")
results = architecture.profiles.sort_by(&:name).to_h do |profile|
  warn "Capturing #{profile.name}"
  [profile.name, { "declared" => profile.to_config, "strict" => profile.to_strict_config }]
end
puts JSON.generate(results)
