# frozen_string_literal: true

require "etc"

$root = Pathname.new(__FILE__).dirname.realpath
$lib = $root / "lib"

require "ruby-progressbar"
require "yard"
require "minitest/test_task"

require_relative $root / "lib" / "architecture"

directory "#{$root}/.stamps"

Dir.glob("#{$root}/backends/*/tasks.rake") do |rakefile|
  load rakefile
end

directory "#{$root}/.stamps"

def cfg_arch_for(config_name)
  Rake::Task["#{$root}/.stamps/resolve-#{config_name}.stamp"].invoke

  @cfg_archs ||= {}
  return @cfg_archs[config_name] if @cfg_archs.key?(config_name)

  @cfg_archs[config_name] =
    ConfiguredArchitecture.new(
      config_name,
      $root / "gen" / "resolved_arch" / config_name,
      overlay_path: $root / "cfgs" / config_name / "arch_overlay"
    )
end

namespace :gen do
  desc "Generate documentation for the ruby tooling"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc --yardopts cfg_arch.yardopts"
      sh "bundle exec yard doc --yardopts idl.yardopts"
    end
  end

  desc "Resolve the standard in arch/, and write it to resolved_arch/"
  task "resolved_arch" do
    sh "#{$root}/.home/.venv/bin/python3 lib/yaml_resolver.py resolve arch resolved_arch"
  end
end

# rule to generate standard for any configurations with an overlay
rule %r{#{$root}/.stamps/resolve-.+\.stamp} => proc { |tname|
  cfg_name = File.basename(tname, ".stamp").sub("resolve-", "")
  arch_files = Dir.glob("#{$root}/arch/**/*.yaml")
  overlay_files = Dir.glob("#{$root}/cfgs/#{cfg_name}/arch_overlay/**/*.yaml")
  [
    "#{$root}/.stamps",
    "#{$root}/lib/yaml_resolver.py"
  ] + arch_files + overlay_files
} do |t|
  cfg_name = File.basename(t.name, ".stamp").sub("resolve-", "")
  sh "#{$root}/.home/.venv/bin/python3 lib/yaml_resolver.py merge arch cfgs/#{cfg_name}/arch_overlay gen/arch/#{cfg_name}"
  sh "#{$root}/.home/.venv/bin/python3 lib/yaml_resolver.py resolve gen/arch/#{cfg_name} gen/resolved_arch/#{cfg_name}"

  FileUtils.touch t.name
end

namespace :serve do
  desc <<~DESC
    Start an HTML server to view the generated HTML documentation for the tool

    The default port is 8000, though it can be overridden with an argument
  DESC
  task :tool_doc, [:port] => "gen:tool_doc" do |_t, args|
    args.with_defaults(port: 8000)

    puts <<~MSG
      Server will come up on http://#{`hostname`.strip}:#{args[:port]}.
      It will regenerate the documentation on every access

    MSG
    sh "yard server -p #{args[:port]} --reload"
  end
end

namespace :test do
  # "Run the IDL compiler test suite"
  task :idl_compiler do
    t = Minitest::TestTask.new(:lib_test)
    t.test_globs = ["#{$root}/lib/idl/tests/test_*.rb"]
    t.process_env
    ruby t.make_test_cmd
  end

  # "Run the Ruby library test suite"
  task :lib do
    t = Minitest::TestTask.new(:lib_test)
    t.test_globs = ["#{$root}/lib/test/test_*.rb"]
    t.process_env
    ruby t.make_test_cmd
  end
end

desc "Clean up all generated files"
task :clean do
  warn "Don't run clean using Rake. Run `./do clean` (alias for `./bin/clean`) instead."
end

namespace :test do
  task :insts do
    puts "Checking instruction encodings..."
    inst_paths = Dir.glob("#{$root}/arch/inst/**/*.yaml").map { |f| Pathname.new(f) }
    inst_paths.each do |inst_path|
      Validator.instance.validate_instruction(inst_path)
    end
    puts "All instruction encodings pass basic sanity tests"
  end
  task schema: "gen:resolved_arch" do
    puts "Checking arch files against schema.."
    Architecture.new("#{$root}/resolved_arch").validate(show_progress: true)
    puts "All files validate against their schema"
  end
  task idl: ["gen:resolved_arch", "#{$root}/.stamps/resolve-rv32.stamp", "#{$root}/.stamps/resolve-rv64.stamp"]  do
    print "Parsing IDL code for RV32..."
    cfg_arch32 = cfg_arch_for("rv32")
    puts "done"

    cfg_arch32.type_check

    print "Parsing IDL code for RV64..."
    cfg_arch64 = cfg_arch_for("rv64")
    puts "done"

    cfg_arch64.type_check

    puts "All IDL passed type checking"
  end
end

def insert_warning(str, from)
  # insert a warning on the second line
  lines = str.lines
  first_line = lines.shift
  lines.unshift(first_line, "\n# WARNING: This file is auto-generated from #{Pathname.new(from).relative_path_from($root)}").join("")
end
private :insert_warning

(3..31).each do |hpm_num|
  file "#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmcounterN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmcounterNh.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmcounterNh.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmcounterNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmeventN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmeventN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmeventN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmeventNh.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmeventNh.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmeventNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/hpmcounterN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/hpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/hpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/hpmcounterNh.layout",
    __FILE__
    ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/hpmcounterNh.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/hpmcounterNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

(0..63).each do |pmpaddr_num|
  file "#{$root}/arch/csr/I/pmpaddr#{pmpaddr_num}.yaml" => [
    "#{$root}/arch/csr/I/pmpaddrN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/I/pmpaddrN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/I/pmpaddrN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

(0..15).each do |pmpcfg_num|
  file "#{$root}/arch/csr/I/pmpcfg#{pmpcfg_num}.yaml" => [
    "#{$root}/arch/csr/I/pmpcfgN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($root / "arch/csr/I/pmpcfgN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/I/pmpcfgN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

file "#{$root}/arch/csr/I/mcounteren.yaml" => [
  "#{$root}/arch/csr/I/mcounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($root / "arch/csr/I/mcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/I/mcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/S/scounteren.yaml" => [
  "#{$root}/arch/csr/S/scounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($root / "arch/csr/S/scounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/S/scounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/H/hcounteren.yaml" => [
  "#{$root}/arch/csr/H/hcounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($root / "arch/csr/H/hcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/H/hcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/Zicntr/mcountinhibit.yaml" => [
  "#{$root}/arch/csr/Zicntr/mcountinhibit.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($root / "arch/csr/Zicntr/mcountinhibit.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/Zicntr/mcountinhibit.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

namespace :gen do
  desc "Generate architecture files from layouts"
  task :arch do
    (3..31).each do |hpm_num|
      Rake::Task["#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}.yaml"].invoke
      Rake::Task["#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}h.yaml"].invoke
      Rake::Task["#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}.yaml"].invoke
      Rake::Task["#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}h.yaml"].invoke

      Rake::Task["#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}.yaml"].invoke
      Rake::Task["#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}h.yaml"].invoke
    end

    Rake::Task["#{$root}/arch/csr/I/mcounteren.yaml"].invoke
    Rake::Task["#{$root}/arch/csr/S/scounteren.yaml"].invoke
    Rake::Task["#{$root}/arch/csr/H/hcounteren.yaml"].invoke
    Rake::Task["#{$root}/arch/csr/Zicntr/mcountinhibit.yaml"].invoke

    (0..63).each do |pmpaddr_num|
      Rake::Task["#{$root}/arch/csr/I/pmpaddr#{pmpaddr_num}.yaml"].invoke
    end

    (0..15).each do |pmpcfg_num|
      Rake::Task["#{$root}/arch/csr/I/pmpcfg#{pmpcfg_num}.yaml"].invoke
    end
  end
end

namespace :test do
  desc <<~DESC
    Run smoke tests

    These are basic but fast-running tests to check the database and tools
  DESC
  task :smoke do
    Rake::Task["test:idl_compiler"].invoke
    Rake::Task["test:lib"].invoke
    Rake::Task["test:schema"].invoke
    Rake::Task["test:idl"].invoke
  end

  desc <<~DESC
    Run the regression tests

    These tests must pass before a commit will be allowed in the main branch on GitHub
  DESC
  task :regress do
    Rake::Task["test:smoke"].invoke

    ENV["MANUAL_NAME"] = "isa"
    ENV["VERSIONS"] = "all"
    Rake::Task["gen:html_manual"].invoke

    ENV["EXT"] = "B"
    ENV["VERSION"] = "latest"
    Rake::Task["gen:ext_pdf"].invoke

    Rake::Task["gen:html"].invoke("generic_rv64")

    Rake::Task["#{$root}/gen/certificate_doc/pdf/MockCertificateModel.pdf"].invoke
    Rake::Task["#{$root}/gen/profile_doc/pdf/MockProfileRelease.pdf"].invoke

    puts
    puts "Regression test PASSED"
  end

  desc <<~DESC
    Run the nightly regression tests

    Generally, this tries to build all artifacts
  DESC
  task :nightly do
    Rake::Task["regress"].invoke
    Rake::Task["portfolios"].invoke
    puts
    puts "Nightly regression test PASSED"
  end
end

desc <<~DESC
  Generate all portfolio-based PDF artifacts (certificates and profiles)
DESC
task :portfolios do
  portfolio_start_msg("MockCertificateModel")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MockCertificateModel.pdf"].invoke
  portfolio_start_msg("MockProfileRelease")
  Rake::Task["#{$root}/gen/profile_doc/pdf/MockProfileRelease.pdf"].invoke
  portfolio_start_msg("MC100-32")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC100-32.pdf"].invoke
  portfolio_start_msg("MC100-64")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC100-64.pdf"].invoke
  portfolio_start_msg("MC200-32")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC200-32.pdf"].invoke
  portfolio_start_msg("MC200-64")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC200-64.pdf"].invoke
  portfolio_start_msg("MC300-32")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC300-32.pdf"].invoke
  portfolio_start_msg("MC300-64")
  Rake::Task["#{$root}/gen/certificate_doc/pdf/MC300-64.pdf"].invoke
  portfolio_start_msg("RVI20")
  Rake::Task["#{$root}/gen/profile_doc/pdf/RVI20.pdf"].invoke
  portfolio_start_msg("RVA20")
  Rake::Task["#{$root}/gen/profile_doc/pdf/RVA20.pdf"].invoke
  portfolio_start_msg("RVA22")
  Rake::Task["#{$root}/gen/profile_doc/pdf/RVA22.pdf"].invoke
  portfolio_start_msg("RVA23")
  Rake::Task["#{$root}/gen/profile_doc/pdf/RVA23.pdf"].invoke
  portfolio_start_msg("RVB23")
  Rake::Task["#{$root}/gen/profile_doc/pdf/RVB23.pdf"].invoke
end

def portfolio_start_msg(name)
  puts ""
  puts "================================================================================================="
  puts "#{name}"
  puts "================================================================================================="
  puts ""
end

# Shortcut targets for building profiles and certificates.
task "MockCertificateModel": "#{$root}/gen/certificate_doc/pdf/MockCertificateModel.pdf"
task "MC100-32": "#{$root}/gen/certificate_doc/pdf/MC100-32.pdf"
task "MC100-64": "#{$root}/gen/certificate_doc/pdf/MC100-64.pdf"
task "MC200-32": "#{$root}/gen/certificate_doc/pdf/MC200-32.pdf"
task "MC200-64": "#{$root}/gen/certificate_doc/pdf/MC200-64.pdf"
task "MC300-32": "#{$root}/gen/certificate_doc/pdf/MC300-32.pdf"
task "MC300-64": "#{$root}/gen/certificate_doc/pdf/MC300-64.pdf"
task "MockProfileRelease": "#{$root}/gen/profile_doc/pdf/MockProfileRelease.pdf"
task "RVI20": "#{$root}/gen/profile_doc/pdf/RVI20.pdf"
task "RVA20": "#{$root}/gen/profile_doc/pdf/RVA20.pdf"
task "RVA22": "#{$root}/gen/profile_doc/pdf/RVA22.pdf"
task "RVA23": "#{$root}/gen/profile_doc/pdf/RVA23.pdf"
task "RVB23": "#{$root}/gen/profile_doc/pdf/RVB23.pdf"
