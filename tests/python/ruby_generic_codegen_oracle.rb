# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Development-only witness: execute the original Rake tasks unchanged, retaining
# the exact extension-major exception records passed to the native scripts.
require "pathname"
require "fileutils"
require "json"
require "rake"
require "sorbet-runtime"
T::Configuration.default_checked_level = :never

root = Pathname.new(Dir.pwd)
fixtures = root / "tests/python/fixtures/generic_codegen"
metadata_only = ARGV.delete("--metadata-only")
FileUtils.mkdir_p(fixtures)
Rake.application.init
Rake.application.load_rakefile

Object.class_eval do
  alias_method :original_with_resolved_exception_codes, :with_resolved_exception_codes
end
def with_resolved_exception_codes(architecture, &block)
  original_with_resolved_exception_codes(architecture) do |path|
    FileUtils.cp(path, ENV.fetch("EXCEPTION_CAPTURE"))
    block.call(path)
  end
end

{
  "all" => "_",
  "rv32" => "rv32",
  "rv64" => "rv64",
  "full" => "mc100-32-full-example"
}.each do |label, config|
  next unless ARGV.empty? || ARGV.include?(label)
  directory = fixtures / label
  FileUtils.mkdir_p(directory)
  ENV["CONFIG"] = config
  ENV["OUTPUT_DIR"] = "#{directory}/"
  ENV["EXCEPTION_CAPTURE"] = (directory / "exceptions.json").to_s
  (metadata_only ? [] : %w[c_header sverilog go]).each do |generator|
    task = Rake::Task["gen:#{generator}"]
    task.reenable
    task.invoke
  end
  architecture = Udb::Resolver.new.cfg_arch_for(config)
  validity = architecture.valid?
  File.write(directory / "manifest.json", JSON.pretty_generate({
    config: config,
    resolved_path: architecture.path.to_s,
    valid: validity.valid,
    reason: validity.reasons
  }) + "\n")

  # Controlled name mutation: retain the actual extension-major wrapper and
  # real configuration ERB environment. No standard record is changed on disk.
  extension = architecture.extension("H")
  code = extension.exception_codes.first
  original_name = code.name
  template = '<% if ext?(:H) %>Guest<% else %>Host<% end %>/<%= possible_xlens.include?(32) ? 32 : 64 %>-fault'
  code.define_singleton_method(:name) { template }
  ENV["EXCEPTION_CAPTURE"] = (directory / "interpolated-exceptions.json").to_s
  with_resolved_exception_codes(architecture) { |_path| }
  File.write(directory / "interpolation.json", JSON.pretty_generate({
    ext: extension.name, var: code.var, original_name: original_name, template: template
  }) + "\n")
  code.define_singleton_method(:name) { original_name }
end
