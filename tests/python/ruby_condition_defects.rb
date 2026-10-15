# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Durable reproductions for intentional Python condition corrections.

require "json"
require "pathname"
require "tmpdir"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/udb/lib").to_s)
require "udb"

gem_root = repo_root / "tools/ruby-gems/udb"
resolver = Udb::Resolver.new(
  schemas_path_override: repo_root / "spec/schemas",
  cfgs_path_override: gem_root / "test/mock_cfgs",
  gen_path_override: Pathname.new(Dir.mktmpdir),
  std_path_override: gem_root / "test/mock_spec/isa",
  quiet: true
)
architecture = resolver.cfg_arch_for("_")

free = Udb::LogicNode.new(Udb::LogicNodeType::Term, [Udb::FreeTerm.new])
range_term = Udb::ParameterTerm.new("name" => "P", "range" => "1-0", "equal" => 3)

puts JSON.generate({
  "empty_conjunction" => Udb::Condition.conjunction([], architecture).to_h,
  "one_way_equivalence" => free.equivalent?(Udb::LogicNode::True, architecture),
  "bit_range_three" => range_term.send(:_eval, {"P" => 3}).serialize
})
