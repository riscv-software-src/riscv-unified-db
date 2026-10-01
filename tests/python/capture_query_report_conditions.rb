# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Native model caller used by the real show/list commands, not a renderer stub.
require "json"
require "pathname"
require "udb/resolver"
require "udb/condition"

root = Pathname.new(Dir.pwd)
architecture = Udb::Resolver.new(root, gen_path_override: root / "gen/query-report-native").cfg_arch_for("_")
cases = [
  true, false, { "xlen" => 32 }, { "not" => { "xlen" => 64 } },
  { "extension" => { "name" => "H", "version" => "~> 1.0" } },
  { "param" => { "name" => "MXLEN", "oneOf" => [32, 64] } },
  { "param" => { "name" => "COUNTINHIBIT_EN", "includes" => true } },
  { "param" => { "name" => "COUNTINHIBIT_EN", "size" => true, "equal" => 32 } },
  *[0, 1, 21, 31, 104].map { |index| { "param" => { "name" => "COUNTINHIBIT_EN", "index" => index, "equal" => true } } }
]
observations = cases.map do |raw|
  condition = Udb::Condition.new(raw, architecture)
  { "raw" => raw, "text" => condition.to_s, "pretty" => condition.to_s_pretty }
end
File.write("tests/python/fixtures/query_reports/native-condition-observations.json", JSON.pretty_generate(observations) + "\n")
