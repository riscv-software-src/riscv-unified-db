# frozen_string_literal: true

$jobs = ENV["JOBS"].nil? ? 1 : ENV["JOBS"].to_i
Rake.application.options.thread_pool_size = $jobs
puts "Running with #{Rake.application.options.thread_pool_size} job(s)"

require "etc"

$root = Pathname.new(__FILE__).dirname.realpath
$lib = $root / "lib"

require "ruby-progressbar"
require "yard"
require "minitest/test_task"

require_relative $root / "lib" / "architecture"
require_relative $root / "lib" / "design"
require_relative $root / "lib" / "portfolio_design"
require_relative $root / "lib" / "proc_cert_design"

directory "#{$root}/.stamps"

# Load and execute Rakefile for each backend.
Dir.glob("#{$root}/backends/*/tasks.rake") do |rakefile|
  load rakefile
end

directory "#{$root}/.stamps"

# @return [ConfiguredArchitecture]
def cfg_arch_for(config_name)
  raise ArgumentError, "expecting String or Pathname" unless config_name.is_a?(String) || config_name.is_a?(Pathname)
  config_name = config_name.to_s

  $cfg_archs ||= {}
  return $cfg_archs[config_name] unless $cfg_archs[config_name].nil?

  # does the gen cfg already exist?
  if File.exist?("#{$root}/gen/cfgs/#{config_name}.yaml")
    config_yaml = YAML.load_file("#{$root}/gen/cfgs/#{config_name}.yaml")
    if File.mtime("#{$root}/gen/cfgs/#{config_name}.yaml") < File.mtime(config_yaml["$source"])

      cfg_arch =
        ConfiguredArchitecture.new(
          config_name,
          ConfigFromFile.create("#{$root}/gen/cfgs/#{config_name}.yaml"),
          $root / "gen" / "resolved_arch" / config_name
        )
      $cfg_archs[config_name] = cfg_arch
      return cfg_arch
    end
  end

  config_path =
    if File.exist?("#{$root}/cfgs/#{config_name}.yaml")
      "#{$root}/cfgs/#{config_name}.yaml"
    elsif File.exist? config_name
      File.realpath(config_name)
    else
      raise ArgumentError, "Can't find config #{config_name}"
    end

  config_yaml = YAML.load_file(config_path)
  config_name = config_yaml["name"]

  overlay_dir =
    if config_yaml["arch_overlay"].nil?
      "/does/not/exist"
    elsif File.exist?("#{$root}/arch_overlay/#{config_yaml['arch_overlay']}")
      "#{$root}/arch_overlay/#{config_yaml['arch_overlay']}"
    elsif File.directory?(config_yaml["arch_overlay"])
      File.realpath(config_yaml["arch_overlay"])
    else
      raise ArgumentError, "Can't find arch_overlay #{config_yaml['arch_overlay']}"
    end

  config_yaml["arch_overlay"] = overlay_dir
  config_yaml["$source"] = config_path

  # write the config with arch_overlay expanded
  unless File.exist?("#{$root}/gen/cfgs/#{config_name}.yaml") && (File.mtime("#{$root}/gen/cfgs/#{config_name}.yaml") < File.mtime(config_path))
    FileUtils.mkdir_p "#{$root}/gen/cfgs"
    File.write "#{$root}/gen/cfgs/#{config_name}.yaml", YAML.dump(config_yaml)
  end
  Rake::Task["#{$root}/.stamps/resolve-#{config_name}.stamp"].invoke

  $cfg_archs[config_name] =
    ConfiguredArchitecture.new(
      config_name,
      ConfigFromFile.create("#{$root}/gen/cfgs/#{config_name}.yaml"),
      $root / "gen" / "resolved_arch" / config_name
    )
end

file "#{$root}/.stamps/dev_gems" => ["#{$root}/.stamps"] do |t|
  #sh "bundle exec yard config --gem-install-yri"
  sh "bundle exec yard gem"
  FileUtils.touch t.name
end

namespace :gen do
  desc "Generate documentation for the ruby tooling"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc --yardopts cfg_arch.yardopts"
      sh "bundle exec yard doc --yardopts idl.yardopts"
    end
  end

  desc "Resolve the standard in arch/, and write it to gen/resolved_arch/_"
  task "resolved_arch" => "#{$root}/.stamps/resolve-_.stamp"
end

# rule to generate standard for any configurations with an overlay
rule %r{#{$root}/.stamps/resolve-.+\.stamp} => proc { |tname|
  cfg_name = File.basename(tname, ".stamp").sub("resolve-", "")
  raise "Missing gen/cfgs/#{tname}" unless File.exist?("#{$root}/cfgs/#{cfg_name}.yaml")

  cfg_path = "#{$root}/cfgs/#{cfg_name}.yaml"
  cfg = ConfigFromFile.create(cfg_path)
  arch_files = Dir.glob("#{$root}/arch/**/*.yaml")
  overlay_files = cfg.overlay? ? Dir.glob("#{cfg.arch_overlay_abs}/**/*.yaml") : []
  [
    "#{$root}/.stamps",
    "#{$root}/lib/yaml_resolver.py"
  ] + arch_files + overlay_files
} do |t|
  cfg_name = File.basename(t.name, ".stamp").sub("resolve-", "")
  cfg_path = "#{$root}/cfgs/#{cfg_name}.yaml"
  cfg = ConfigFromFile.create(cfg_path)

  overlay_dir = cfg.overlay? ? cfg.arch_overlay_abs : "/does/not/exist"
  sh "#{$root}/.home/.venv/bin/python3 lib/yaml_resolver.py merge arch #{overlay_dir} gen/arch/#{cfg_name}"
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

desc "Clean up all generated files and container"
task :clobber do
  warn "Don't run clean using Rake. Run `./do clean` (alias for `./bin/clean`) instead."
end


namespace :test do
  desc "Check that instruction encodings in the DB are consistent and do not conflict"
  task :inst_encodings do
    print "Checking for conflicts in instruction encodings.."

    cfg_arch = cfg_arch_for("_")
    insts = cfg_arch.instructions
    failed = false
    insts.each_with_index do |inst, idx|
      [32, 64].each do |xlen|
        next unless inst.defined_in_base?(xlen)

        (idx...insts.size).each do |other_idx|
          other_inst = insts[other_idx]
          next unless other_inst.defined_in_base?(xlen)
          next if other_inst == inst

          if inst.bad_encoding_conflict?(xlen, other_inst)
            warn "In RV#{xlen}: #{inst.name} (#{inst.encoding(xlen).format}) conflicts with #{other_inst.name} (#{other_inst.encoding(xlen).format})"
            failed = true
          end
        end
      end
    end
    raise "Encoding test failed" if failed

    puts "done"
  end

  desc "Check that CSR definitions in the DB are consistent and do not conflict"
  task :csrs do
    print "Checking for conflicts in CSRs.."

    cfg_arch = cfg_arch_for("_")
    csrs = cfg_arch.csrs
    failed = false
    csrs.each_with_index do |csr, idx|
      [32, 64].each do |xlen|
        next unless csr.defined_in_base?(xlen)

        (idx...csrs.size).each do |other_idx|
          other_csr = csrs[other_idx]
          next unless other_csr.defined_in_base?(xlen)
          next if other_csr == csr

          if csr.address == other_csr.address && !csr.address.nil?
            warn "CSRs #{csr.name} and #{other_csr.name} have conflicting addresses (#{csr.address})"
            failed = true
          end
        end
      end
    end
    raise "CSR test failed" if failed

    puts "done"
  end

  task schema: "#{$root}/.stamps/resolve-_.stamp" do
    puts "Checking arch files against schema.."
    Architecture.new("#{$root}/gen/resolved_arch/_").validate(show_progress: true)
    puts "All files validate against their schema"
  end

  task idl: ["#{$root}/.stamps/resolve-rv32.stamp", "#{$root}/.stamps/resolve-rv64.stamp"]  do
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
    puts "UPDATE: Starting test:smoke"
    #puts "UPDATE: Running gen:isa_explorer_spreadsheet"
    #Rake::Task["gen:isa_explorer_spreadsheet"].invoke
    puts "UPDATE: Running test:idl_compiler"
    Rake::Task["test:idl_compiler"].invoke
    puts "UPDATE: Running test:lib"
    Rake::Task["test:lib"].invoke
    puts "UPDATE: Running test:schema"
    Rake::Task["test:schema"].invoke
    puts "UPDATE: Running test:idl"
    Rake::Task["test:idl"].invoke
    puts "UPDATE: Running test:inst_encodings"
    Rake::Task["test:inst_encodings"].invoke
    puts "UPDATE: Done test:smoke"
  end

  desc <<~DESC
    Run the regression tests

    These tests must pass before a commit will be allowed in the main branch on GitHub
  DESC
  task :regress do
    puts "UPDATE: Starting test:regress"
    Rake::Task["test:smoke"].invoke

    puts "UPDATE: Running gen:isa_explorer_browser"
    Rake::Task["gen:isa_explorer_browser"].invoke

    puts "UPDATE: Running gen:html_manual MANUAL_NAME=isa VERSIONS=all"
    ENV["MANUAL_NAME"] = "isa"
    ENV["VERSIONS"] = "all"
    Rake::Task["gen:html_manual"].invoke

    puts "UPDATE: Running gen:ext_pdf EXT=B VERSION=latest"
    ENV["EXT"] = "B"
    ENV["VERSION"] = "latest"
    Rake::Task["gen:ext_pdf"].invoke

    puts "UPDATE: Running gen:html for example_rv64_with_overlay"
    Rake::Task["gen:html"].invoke("example_rv64_with_overlay")

    puts "UPDATE: Generating MockProcessor-CRD.pdf"
    Rake::Task["#{$root}/gen/proc_crd/pdf/MockProcessor-CRD.pdf"].invoke

    puts "UPDATE: Generating MockProcessor-CTP.pdf"
    Rake::Task["#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.pdf"].invoke

    puts "UPDATE: Generating MockProfileRelease.pdf"
    Rake::Task["#{$root}/gen/profile/pdf/MockProfileRelease.pdf"].invoke

    puts "UPDATE: Done test:regress"
    puts "Regression test PASSED"
  end

  desc <<~DESC
    Run the nightly regression tests

    Generally, this tries to build all artifacts
  DESC
  task :nightly do
    Rake::Task["test:regress"].invoke
    Rake::Task["portfolios"].invoke
    puts
    puts "Nightly regression test PASSED"
  end
end

desc <<~DESC
  Generate all portfolio-based PDF artifacts (certificates and profiles)
DESC
task :portfolios do
  portfolio_start_msg("MockProcessor-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MockProcessor-CRD.pdf"].invoke
  portfolio_start_msg("MockProcessor-CTP")
  Rake::Task["#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.pdf"].invoke
  portfolio_start_msg("MockProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/MockProfileRelease.pdf"].invoke
  portfolio_start_msg("MC100-32-CTP")
  Rake::Task["#{$root}/gen/proc_ctp/pdf/MC100-32-CTP.pdf"].invoke
  portfolio_start_msg("MC100-32-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC100-32-CRD.pdf"].invoke
  portfolio_start_msg("MC100-64-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC100-64-CRD.pdf"].invoke
  portfolio_start_msg("MC200-32-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC200-32-CRD.pdf"].invoke
  portfolio_start_msg("MC200-64-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC200-64-CRD.pdf"].invoke
  portfolio_start_msg("MC300-32-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC300-32-CRD.pdf"].invoke
  portfolio_start_msg("MC300-64-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/MC300-64-CRD.pdf"].invoke
  portfolio_start_msg("AC100-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/AC100-CRD.pdf"].invoke
  portfolio_start_msg("AC200-CRD")
  Rake::Task["#{$root}/gen/proc_crd/pdf/AC200-CRD.pdf"].invoke
  portfolio_start_msg("RVI20ProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/RVI20ProfileRelease.pdf"].invoke
  portfolio_start_msg("RVA20ProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/RVA20ProfileRelease.pdf"].invoke
  portfolio_start_msg("RVA22ProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/RVA22ProfileRelease.pdf"].invoke
  portfolio_start_msg("RVA23ProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/RVA23ProfileRelease.pdf"].invoke
  portfolio_start_msg("RVB23ProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/RVB23ProfileRelease.pdf"].invoke
end

def portfolio_start_msg(name)
  puts ""
  puts "================================================================================================="
  puts "#{name}"
  puts "================================================================================================="
  puts ""
end

# Shortcut targets for building CRDs, CTPs, and Profile Releases.
task "MockCRD": "#{$root}/gen/proc_crd/pdf/MockProcessor-CRD.pdf"
task "MockProcessorCRD": "#{$root}/gen/proc_crd/pdf/MockProcessor-CRD.pdf"
task "MockCTP": "#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.pdf"
task "MockProcessorCTP": "#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.pdf"
task "MockCTP-HTML": "#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.html"
task "MockProcessorCTP-HTML": "#{$root}/gen/proc_ctp/pdf/MockProcessor-CTP.html"
task "MC100-32-CTP": "#{$root}/gen/proc_ctp/pdf/MC100-32-CTP.pdf"
task "MC100-32-CTP-HTML": "#{$root}/gen/proc_ctp/pdf/MC100-32-CTP.html"
task "MC100-32-CRD": "#{$root}/gen/proc_crd/pdf/MC100-32-CRD.pdf"
task "MC100-64-CRD": "#{$root}/gen/proc_crd/pdf/MC100-64-CRD.pdf"
task "MC200-32-CRD": "#{$root}/gen/proc_crd/pdf/MC200-32-CRD.pdf"
task "MC200-64-CRD": "#{$root}/gen/proc_crd/pdf/MC200-64-CRD.pdf"
task "MC300-32-CRD": "#{$root}/gen/proc_crd/pdf/MC300-32-CRD.pdf"
task "MC300-64-CRD": "#{$root}/gen/proc_crd/pdf/MC300-64-CRD.pdf"
task "AC100-CRD": "#{$root}/gen/proc_crd/pdf/AC100-CRD.pdf"
task "AC200-CRD": "#{$root}/gen/proc_crd/pdf/AC200-CRD.pdf"
task "MockProfile": "#{$root}/gen/profile/pdf/MockProfileRelease.pdf"
task "MockProfileRelease": "#{$root}/gen/profile/pdf/MockProfileRelease.pdf"
task "RVI20": "#{$root}/gen/profile/pdf/RVI20ProfileRelease.pdf"
task "RVA20": "#{$root}/gen/profile/pdf/RVA20ProfileRelease.pdf"
task "RVA22": "#{$root}/gen/profile/pdf/RVA22ProfileRelease.pdf"
task "RVA23": "#{$root}/gen/profile/pdf/RVA23ProfileRelease.pdf"
task "RVB23": "#{$root}/gen/profile/pdf/RVB23ProfileRelease.pdf"
