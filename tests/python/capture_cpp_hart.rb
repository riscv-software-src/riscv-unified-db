# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Development oracle only. Outputs and resolver caches live under the explicit
# capture directory, never in the production generator's destination.
require "pathname"
require "fileutils"
require "json"
require "digest"
require "erb"
require "active_support"
require "active_support/core_ext/string/inflections"

root = Pathname.new(ARGV.shift).realpath
out = Pathname.new(ARGV.shift).expand_path
configs = ARGV
$LOAD_PATH.unshift((root / "tools/ruby-gems/udb/lib").to_s)
$LOAD_PATH.unshift((root / "tools/ruby-gems/idlc/lib").to_s)
require "udb"
require "udb/resolver"
require_relative "../../backends/cpp_hart_gen/lib/template_helpers"
require_relative "../../backends/cpp_hart_gen/lib/csr_template_helpers"
require_relative "../../backends/cpp_hart_gen/lib/gen_cpp"
require_relative "../../backends/cpp_hart_gen/lib/decode_tree"
require "idlc/passes/find_src_registers"

FileUtils.mkdir_p(out)
resolver = Udb::Resolver.new(
  root,
  schemas_path_override: root / "spec/schemas",
  cfgs_path_override: root / "cfgs",
  gen_path_override: out / "resolver",
  std_path_override: root / "spec/std/isa",
  custom_path_override: root / "spec/custom/isa",
  quiet: true
)
$resolver = resolver
$root = root
manifest = {
  "root" => root.to_s, "selectors" => configs, "ruby" => RUBY_DESCRIPTION,
  "inputs" => {}, "outputs" => {}, "errors" => {}
}
paths = Dir.glob(root / "spec/{std/isa,custom/isa,schemas}/**/*").select { |p| File.file?(p) }
paths += Dir.glob(root / "backends/cpp_hart_gen/{lib,templates}/**/*").select { |p| File.file?(p) }
paths += Dir.glob(root / "tools/ruby-gems/{udb,idlc}/lib/**/*").select { |p| File.file?(p) }
paths += configs.map { |c| File.file?(c) ? c : (root / "cfgs/#{c}.yaml").to_s }
paths.each do |path|
  manifest["inputs"][path.delete_prefix("#{root}/")] = Digest::SHA256.file(path).hexdigest
end
configs.each do |selector|
  begin
    arch = resolver.cfg_arch_for(File.file?(selector) ? Pathname.new(selector) : selector)
    ENV["CONFIG"] = arch.name
    env = CppHartGen::TemplateEnv.new(arch)
    Dir.glob(root / "backends/cpp_hart_gen/templates/*.erb").sort.each do |path|
      basename = File.basename(path, ".erb")
      destination = out / "raw" / arch.name / basename
      begin
        erb = ERB.new(File.read(path), trim_mode: "-")
        erb.filename = path
        text = erb.result(env.get_binding)
        FileUtils.mkdir_p(destination.dirname)
        destination.write(text)
        manifest["outputs"][destination.relative_path_from(out).to_s] = Digest::SHA256.hexdigest(text)
      rescue Exception => error
        manifest["errors"]["#{selector}/#{basename}"] = {
          "class" => error.class.to_s, "message" => error.message,
          "backtrace" => error.backtrace.first(12)
        }
      end
      (out / "manifest.json").write(JSON.pretty_generate(manifest) + "\n")
    end
  rescue Exception => error
    manifest["errors"][selector] = {
      "class" => error.class.to_s, "message" => error.message,
      "backtrace" => error.backtrace.first(12)
    }
  end
  (out / "manifest.json").write(JSON.pretty_generate(manifest) + "\n")
end
