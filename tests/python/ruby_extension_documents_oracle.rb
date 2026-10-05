# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Development-only oracle. Source generation uses the genuine ERB generator.
require "sorbet-runtime"
T::Configuration.default_checked_level = :never
require "json"
require "digest"
require "shellwords"
require "udb-gen/generators/ext_doc/generator"

root = Pathname.new(ENV.fetch("UDB_ORACLE_ROOT", Dir.pwd))
out = Pathname.new(Dir.pwd) / "tests/python/fixtures/extension_docs"
FileUtils.mkdir_p(out)
resolver = Udb::Resolver.new(root, gen_path_override: Pathname.new(Dir.pwd) / "gen/extension-oracle")
observations = []
cases = [
  ["zba-all", "_", ["Zba"], []],
  ["zba-latest", "rv64", ["Zba@latest"], []],
  ["zicsr-all", "_", ["Zicsr"], []],
  ["zicsr-full", root / "cfgs/mc100-32-full-example.yaml", ["Zicsr"], []],
  ["qcicsr", "qc_iu", ["Xqcicsr"], ["-i", "--no-csr-field-desc"]]
]
cases.each do |name, cfg, selectors, flags|
  generator = UdbGen::GenExtPdfOptions.new
  generator.define_singleton_method(:resolver) { resolver }
  argv = ["-c", cfg.to_s, "-o", (out / name).to_s, "-b", name, *flags, *selectors]
  record = {id: name, cfg: cfg.to_s, selectors: selectors, argv: argv}
  begin
    generator.parse(argv)
    generator.gen_adoc
    file = out / name / "#{name}.adoc"
    record.merge!(ok: true, artifact: file.relative_path_from(out).to_s,
                  sha256: Digest::SHA256.file(file).hexdigest, bytes: file.size)
  rescue Exception => error
    record.merge!(ok: false, error: {class: error.class.name, message: error.message,
                                   backtrace: error.backtrace&.first(8)})
  end
  observations << record
  File.write(out / "manifest.json", JSON.pretty_generate({root: root.to_s,
             head: `git rev-parse HEAD`.strip, outcomes: observations}))
end

# Execute the original script unchanged. Only intercept its process boundary to
# capture the real generator's source rather than start the external PDF renderer.
original = root / "tools/scripts/gen_xqci.rb"
original_hash = Digest::SHA256.file(original).hexdigest
capture = Module.new do
  define_method(:system) do |command|
    words = Shellwords.split(command)
    generator = UdbGen::GenExtPdfOptions.new
    generator.define_singleton_method(:resolver) { resolver }
    original_argv = words.drop(2)
    record = {id: "xqci-original-script", cfg: "qc_iu", command: command,
              script_sha256: original_hash, argv: original_argv}
    begin
      argv = original_argv.dup
      output_index = argv.index("-o") + 1
      argv[output_index] = (out / "xqci-original").to_s
      generator.parse(argv)
      generator.gen_adoc
      file = out / "xqci-original" / "#{generator.basename}.adoc"
      record.merge!(ok: true, artifact: file.relative_path_from(out).to_s,
                    sha256: Digest::SHA256.file(file).hexdigest, bytes: file.size)
    rescue Exception => error
      record.merge!(ok: false, error: {class: error.class.name, message: error.message,
                                     backtrace: error.backtrace&.first(8)})
    end
    observations << record
    true
  end
end
Kernel.prepend(capture)
ARGV.clear
begin
  load original
rescue SystemExit, NoMethodError => error
  # The untouched script reads $? after the intercepted source-only boundary.
end
File.write(out / "manifest.json", JSON.pretty_generate({root: root.to_s,
           head: `git rev-parse HEAD`.strip, outcomes: observations}))
