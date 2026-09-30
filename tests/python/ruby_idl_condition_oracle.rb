# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Oracle for Ruby's translation of `idl()` conditions into UDB conditions.
#
# Usage: ruby ruby_idl_condition_oracle.rb <repo-root> <config> < cases.json
#
# Input: [{"id": str, "file": str, "text": str}, ...] where `text` is the body
# of an `idl()` key. For each case, prints Ruby's `IdlCondition#to_h` (the
# condition produced by `Idl::AstNode#to_udb_h` in
# `udb/idl/condition_to_udb.rb`) and `satisfied_by_cfg_arch?` for <config>,
# or the exception class and message when Ruby cannot translate it.

require "json"
require "pathname"
require "udb"

root = Pathname.new(ARGV.fetch(0))
config = ARGV.fetch(1)
resolver = Udb::Resolver.new(root, quiet: true)
architecture = resolver.cfg_arch_for(config)

def normalize_error(error, root)
  "#{error.class}: #{error.message.gsub(root.to_s + '/', '')}"
end

results = JSON.parse($stdin.read).map do |data|
  result = {"id" => data.fetch("id")}
  begin
    condition = Udb::IdlCondition.new(
      {"idl()" => data.fetch("text")}, architecture,
      input_file: root / data.fetch("file"), input_line: nil
    )
    result["to_h"] = condition.to_h
    begin
      result["satisfied"] = condition.satisfied_by_cfg_arch?(architecture).serialize
    rescue StandardError, NotImplementedError => e
      result["satisfied_error"] = normalize_error(e, root)
    end
  rescue StandardError, NotImplementedError => e
    result["error"] = normalize_error(e, root)
  end
  result
end

puts JSON.generate({"config" => config, "results" => results})
