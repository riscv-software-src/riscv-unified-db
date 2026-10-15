# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "sorbet-runtime"
T::Configuration.default_checked_level = :never
require "udb-gen/generators/inst_table/table_builder"

root = Pathname.new(Dir.pwd)
resolver = Udb::Resolver.new(root, gen_path_override: root / "gen/table-oracle")
fixtures = root / "tests/python/fixtures/instruction_table"
{
  "all" => "_",
  "rv32" => "rv32",
  "rv64" => "rv64",
  "full" => root / "cfgs/mc100-32-full-example.yaml"
}.each do |name, cfg|
  arch = resolver.cfg_arch_for(cfg)
  builder = UdbGen::InstTable::TableBuilder.new(arch, nil)
  File.write(fixtures / "native-#{name}-stdout.txt", builder.generate)
end
