# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Capture the real Thor entrypoint, in separate processes, without rewriting output.
require "digest"
require "fileutils"
require "json"
require "open3"
require "pathname"
require "rbconfig"

root = Pathname.new(Dir.pwd)
fixtures = root / "tests/python/fixtures/query_reports"
FileUtils.mkdir_p(fixtures)
common = %w[--arch spec/std/isa --arch-overlay spec/custom/isa --config-dir cfgs --gen gen/query-report-native]
cases = {
  "show-extension-I" => %w[show extension I],
  "show-extension-Zicsr" => %w[show extension Zicsr],
  "show-extension-missing" => %w[show extension NoSuchExtension],
  "show-parameter-MXLEN" => %w[show parameter MXLEN],
  "show-parameter-missing" => %w[show parameter NO_SUCH_PARAMETER],
  "show-parameter-full-MXLEN" => %w[show parameter MXLEN --config mc100-32-full-example],
  "list-extensions-all" => %w[list extensions],
  "list-extensions-rv32" => %w[list extensions --config rv32],
  "list-extensions-full" => %w[list extensions --config mc100-32-full-example],
  "list-csrs-full" => %w[list csrs --config mc100-32-full-example],
  "list-csrs-all" => %w[list csrs],
  "list-parameters-I-ascii" => %w[list parameters -e I],
  "list-parameters-I-json" => %w[list parameters -e I -f json],
  "list-parameters-I-yaml" => %w[list parameters -e I -f yaml],
  "list-parameters-empty-ascii" => %w[list parameters -e NoSuchExtension],
  "list-parameters-all-json" => %w[list parameters -f json],
  "list-parameters-full-json" => %w[list parameters --config mc100-32-full-example -f json]
}
{
  "show-parameter-SXLEN" => %w[show parameter SXLEN],
  "show-parameter-ARCH_ID_VALUE" => %w[show parameter ARCH_ID_VALUE],
  "show-parameter-NUM_PMP_ENTRIES" => %w[show parameter NUM_PMP_ENTRIES],
  "list-parameters-Sm-ascii" => %w[list parameters -e Sm],
  "list-parameters-Sm-json" => %w[list parameters -e Sm -f json],
  "list-parameters-Sm-yaml" => %w[list parameters -e Sm -f yaml],
  "show-extension-C" => %w[show extension C],
  "disasm-custom-ambiguous" => %w[disasm 13 --arch-overlay tests/python/fixtures/query_reports --config tests/python/fixtures/query_reports/custom.yaml],
  "disasm-custom-rv32" => %w[disasm 13 --arch-overlay tests/python/fixtures/query_reports --config tests/python/fixtures/query_reports/custom-rv32.yaml]
}.each { |name, arguments| cases[name] = arguments }
{
  "addi" => "fff10093", "compressed" => "0001", "xlen-dependent" => "2081",
  "rv64-only" => "00003003", "illegal" => "ffffffff", "zero" => "0",
  "overwide" => "100000013", "malformed" => "0xz"
}.each { |name, encoding| cases["disasm-#{name}"] = ["disasm", encoding] }
cases["disasm-rv32"] = %w[disasm 00003003 --config rv32]
cases["disasm-rv64"] = %w[disasm 00003003 --config rv64]
cases["disasm-full-catalog"] = %w[disasm 00003003 --config mc100-32-full-example]
cases["missing-config"] = %w[list extensions --config NO_SUCH_CONFIGURATION]

manifest = {
  "transport" => "Open3.capture3 of the unmodified tools/ruby-gems/udb/bin/udb Thor entrypoint; RUBYLIB selects this worktree; output bytes unmodified",
  "cwd" => root.to_s,
  "ruby" => RUBY_DESCRIPTION,
  "base" => "a67618c2",
  "sources" => {},
  "cases" => {}
}
%w[spec/std/isa spec/custom/isa cfgs tools/ruby-gems/udb/lib tools/ruby-gems/idlc/lib tools/ruby-gems/udb_helpers/lib tests/python/fixtures/query_reports/overlay].each do |directory|
  Dir.glob((root / directory / "**/*").to_s).sort.each do |file|
    next unless File.file?(file)
    relative = Pathname.new(file).relative_path_from(root).to_s
    manifest["sources"][relative] = Digest::SHA256.file(file).hexdigest
  end
end
%w[custom.yaml custom-rv32.yaml].each do |name|
  file = fixtures / name
  manifest["sources"][file.relative_path_from(root).to_s] = Digest::SHA256.file(file).hexdigest
end
if ARGV.any? && (fixtures / "manifest.json").file?
  manifest["cases"] = JSON.parse((fixtures / "manifest.json").read)["cases"]
end
rubylib = %w[udb idlc udb_helpers].map { |gem| (root / "tools/ruby-gems" / gem / "lib").to_s }.join(":")
cases.each do |name, arguments|
  next if ARGV.any? && !ARGV.include?(name)
  defaults = common.each_slice(2).reject { |flag, _| arguments.include?(flag) }.map do |flag, value|
    [flag, flag == "--gen" ? "gen/query-report-native/#{name}" : value]
  end.flatten
  command = [RbConfig.ruby, "tools/ruby-gems/udb/bin/udb", *arguments, *defaults]
  stdout, stderr, status = Open3.capture3({ "RUBYLIB" => rubylib }, *command)
  File.binwrite(fixtures / "#{name}.stdout.txt", stdout)
  File.binwrite(fixtures / "#{name}.stderr.txt", stderr)
  manifest["cases"][name] = {
    "command" => command, "arguments" => arguments, "exit_status" => status.exitstatus,
    "stdout_sha256" => Digest::SHA256.hexdigest(stdout), "stderr_sha256" => Digest::SHA256.hexdigest(stderr)
  }
  puts "#{name}: #{status.exitstatus}"
end
File.write(fixtures / "manifest.json", JSON.pretty_generate(manifest) + "\n")
