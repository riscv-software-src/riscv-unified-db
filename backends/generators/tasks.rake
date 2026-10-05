# frozen_string_literal: true
# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "pathname"

namespace :gen do
  {
    "go" => ["udb.generators.go", "go", "inst.go"],
    "c_header" => ["udb.generators.c_encoding", "c_header", "encoding.out.h"],
    "sverilog" => ["udb.generators.sv_decode", "sverilog", "riscv_decode_package.svh"]
  }.each do |task_name, (generator, directory, filename)|
    desc "Generate #{task_name} using the offline Python public API (CONFIG/OUTPUT_DIR)"
    task task_name do
      config = ENV.fetch("CONFIG", "_")
      unless ["_", "rv32", "rv64"].include?(config)
        named_path = $root / "cfgs" / "#{config}.yaml"
        config = named_path.to_s if named_path.file?
      end
      output = Pathname.new(ENV.fetch("OUTPUT_DIR", ($root / "gen" / directory).to_s)) / filename
      command = [
        "uv", "run", "--locked", "python", "-m", generator,
        "--path", ($root / "spec/std/isa").to_s,
        "--schemas", ($root / "spec/schemas").to_s,
        "--overlay-root", ($root / "spec/custom/isa").to_s,
        "--config", config, "--output", output.to_s
      ]
      sh(*command)
    end
  end
end
