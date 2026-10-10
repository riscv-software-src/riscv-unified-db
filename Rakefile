# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
T.bind(self, T.all(Rake::DSL, Object))
extend T::Sig

require "pathname"
require "erb"
require "tty-command"

Encoding.default_external = "UTF-8"

$jobs = ENV["JOBS"].nil? ? 1 : ENV["JOBS"].to_i
Rake.application.options.thread_pool_size = $jobs
puts "Running with #{Rake.application.options.thread_pool_size} job(s)"

require "etc"

$root = Pathname.new(__dir__).realpath
$rake_cmd_runner = TTY::Command.new
$lib = $root / "lib"

require "udb/resolver"
$resolver = Udb::Resolver.new($root)

require "logger"
require "ruby-progressbar"
require "yard"
require "minitest/test_task"

require "udb/architecture"
require "udb/portfolio_design"

$logger = Logger.new(STDOUT, datetime_format: "%v %r")
$logger.level = Logger::INFO
$logger.formatter = proc do |severity, datetime, progname, msg|
  "[#{severity}] #{datetime.strftime('%F %T')}: #{msg}\n"
end

directory "#{$root}/.stamps"

# Load and execute Rakefile for each backend.
Dir.glob("#{$root}/backends/*/tasks.rake") do |rakefile|
  load rakefile
end

# Load and execute tools Rakefiles
Dir.glob("#{$root}/tools/*/tasks.rake") do |rakefile|
  load rakefile
end

directory "#{$root}/.stamps"

file "#{$root}/.stamps/dev_gems" => ["#{$root}/.stamps"] do |t|
  #sh "bundle exec yard config --gem-install-yri"
  sh "bundle exec yard gem"
  FileUtils.touch t.name
end

namespace :chore do
  desc "Update golden instruction appendix"
  task :update_golden_appendix do
    Rake::Task["gen:instruction_appendix_adoc"].invoke
    sh "mv #{$root}/gen/instructions_appendix/all_instructions.adoc #{$root}/tests/golden/all_instructions.golden.adoc"
  end
end

namespace :gen do
  desc "Generate documentation for the ruby tooling"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc --yardopts cfg_arch.yardopts"
      sh "bundle exec yard doc --yardopts idl.yardopts"
    end
  end

  desc "Resolve the configuration CFG with spec/ and write it to gen/resolved_arch/<CFG>. Default CFG is the standard \"_\"."
  task "resolved_arch" do
    cfg = ENV["CFG"]
    if cfg.nil?
      cfg = "_"
    end
    if ENV.key?("COMPILE_IDL")
      resolver = Udb::Resolver.new($root, compile_idl: true)
      resolver.cfg_arch_for(cfg)
      Dir.glob(resolver.std_path / "isa" / "globals.isa") do |idl_file|
        compiler = Idl::Compiler.new
        ast = compiler.compile_file(Pathname.new(idl_file), {})
        dst = resolver.cfg_info(cfg).resolved_spec_path / Pathname.new(idl_file).relative_path_from(resolver.std_path)
        dst = dst.dirname / "#{dst.basename(".isa")}.yaml"
        File.write dst, YAML.dump(ast.to_h)
      end
    else
      $resolver.cfg_arch_for(cfg)
    end
  end

  desc "Resolve schema files and write them to gen/schemas/VERSION/SCHEMA with full $id URLs"
  task :schemas do
    $resolver.resolve_schemas
    puts "Resolved schema files written to gen/schemas/"
  end
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

sig { params(test_files: T::Array[String]).returns(String) }
def make_test_cmd(test_files)
  "-Ilib:test -w -e 'require \"minitest/autorun\"; #{test_files.map { |f| "require \"#{f}\"" }.join("; ")}' --"
end

namespace :test do

  # "Run the cross-validation against LLVM"
  task :llvm do
    begin
      sh "uv run pytest tools/python/auto-inst/test_parsing.py -v"
    rescue => e
      raise unless e.message.include?("status (5)") # don't fail on skipped tests
    end
  end
  # "Run the IDL compiler test suite"
  task :idl_compiler do
    test_files = Dir["#{$root}/lib/idl/tests/test_*.rb"]
    ruby make_test_cmd(test_files)
  end

  # "Run the Ruby library test suite"
  task :lib do
    test_files = Dir["#{$root}/lib/test/test_*.rb"]

    ruby make_test_cmd(test_files)
  end

  desc "Type-check the Ruby library"
  task :sorbet do
    Dir.chdir($root) do
      sh "./bin/bundle exec srb tc"
    end
  end
end

desc "Clean up all generated files"
task :clean do
  warn "Don't run clean using Rake. Run `./do clean` (alias for `./bin/clean`) instead."
end

desc "Clean up all generated files and container"
task :clobber do
  warn "Don't run clobber using Rake. Run `./do clobber` (alias for `./bin/clobber`) instead."
end


namespace :test do
  desc "Check that instruction encodings in the DB are consistent and do not conflict"
  task :inst_encodings do
    Udb.logger.info "Checking for conflicts in instruction encodings.."

    failed = T.let(false, T::Boolean)

    cfg_arch = $resolver.cfg_arch_for("_")
    insts = cfg_arch.instructions
    inst_names = T.let(Set.new, T::Set[String])
    insts.each do |i|
      if inst_names.include?(i.name)
        Udb.logger.warn "Duplicate instruction name: #{i.name}"
        failed = true
      end
      inst_names.add(i.name)
    end
    insts.each_with_index do |inst, idx|
      [32, 64].each do |xlen|
        next unless inst.defined_in_base?(xlen)

        (idx...insts.size).each do |other_idx|
          other_inst = T.must(insts[other_idx])
          next unless other_inst.defined_in_base?(xlen)
          next if other_inst == inst

          if inst.bad_encoding_conflict?(xlen, other_inst)
            warn "In RV#{xlen}: #{inst.name} (#{inst.encoding(xlen).format}) conflicts with #{other_inst.name} (#{other_inst.encoding(xlen).format})"
            failed = true
          end
        end
      end
    end
    if failed
      Udb.logger.error "Encoding test failed"
      exit 1
    end

    Udb.logger.info "Encoding test PASSED"
  end

  desc "Check that CSR definitions in the DB are consistent and do not conflict"
  task :csrs do
    print "Checking for conflicts in CSRs.."

    cfg_arch = $resolver.cfg_arch_for("_")
    csrs = cfg_arch.csrs
    failed = T.let(false, T::Boolean)
    csrs.each_with_index do |csr, idx|
      [32, 64].each do |xlen|
        next unless csr.defined_in_base?(xlen)

        (idx...csrs.size).each do |other_idx|
          other_csr = T.must(csrs[other_idx])
          next unless other_csr.defined_in_base?(xlen)
          next if other_csr == csr

          if csr.address == other_csr.address && !csr.address.nil?
            warn "CSRs #{csr.name} and #{other_csr.name} have conflicting addresses (#{csr.address})"
            failed = true
          end

          if csr.indirect? && other_csr.indirect? &&
              csr.priv_mode == other_csr.priv_mode &&
              csr.indirect_address == other_csr.indirect_address &&
              csr.indirect_slot == other_csr.indirect_slot
            warn "Indirect CSRs #{csr.name} and #{other_csr.name} have conflicting keys in RV#{xlen} " \
              "(priv_mode: #{csr.priv_mode}, indirect_address: 0x#{csr.indirect_address.to_s(16)}, " \
              "indirect_slot: #{csr.indirect_slot})"
            failed = true
          end
        end
      end
    end
    raise "CSR test failed" if failed

    puts "done"
  end

  task :schema do
    puts "Checking arch files against schema.."
    $resolver.cfg_arch_for("_").validate($resolver, show_progress: true)
    puts "All files validate against their schema"
  end

  task :idl do
    cfg = ENV["CFG"]
    raise "Missing CFG environment variable" if cfg.nil?

    print "Parsing IDL code for #{cfg}..."
    cfg_arch = $resolver.cfg_arch_for(cfg)
    puts "done"

    cfg_arch.type_check

    puts "All IDL passed type checking"
  end
end

def insert_warning(str, from)
  # insert a warning on the second line
  lines = str.lines
  first_line = lines.shift
  lines.unshift(first_line, "\n# WARNING: This file is auto-generated from #{Pathname.new(from).relative_path_from($root)}\n\n").join("")
end

(3..31).each do |hpm_num|
  file "#{$resolver.std_path}/csr/Zihpm/mhpmcounter#{hpm_num}.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/mhpmcounterN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/mhpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/mhpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/csr/Zihpm/mhpmcounter#{hpm_num}h.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/mhpmcounterNh.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/mhpmcounterNh.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/mhpmcounterNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/csr/Zihpm/mhpmevent#{hpm_num}.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/mhpmeventN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/mhpmeventN.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/mhpmeventN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/csr/Zihpm/mhpmevent#{hpm_num}h.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/mhpmeventNh.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/mhpmeventNh.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/mhpmeventNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/csr/Zihpm/hpmcounter#{hpm_num}.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/hpmcounterN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/hpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/hpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/csr/Zihpm/hpmcounter#{hpm_num}h.yaml" => [
    "#{$resolver.std_path}/csr/Zihpm/hpmcounterNh.layout",
    __FILE__
    ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/Zihpm/hpmcounterNh.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/Zihpm/hpmcounterNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$resolver.std_path}/param/HPM_COUNTER#{hpm_num}_WIDTH.yaml" => [
    "#{$resolver.std_path}/param/HPM_COUNTERN_WIDTH.layout",
    __FILE__
  ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "param/HPM_COUNTERN_WIDTH.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/param/HPM_COUNTERN_WIDTH.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

(0..63).each do |pmpaddr_num|
  file "#{$resolver.std_path}/csr/I/pmpaddr#{pmpaddr_num}.yaml" => [
    "#{$resolver.std_path}/csr/I/pmpaddrN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/I/pmpaddrN.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/I/pmpaddrN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

(0..15).each do |pmpcfg_num|
  file "#{$resolver.std_path}/csr/I/pmpcfg#{pmpcfg_num}.yaml" => [
    "#{$resolver.std_path}/csr/I/pmpcfgN.layout",
    __FILE__
   ] do |t|
    erb = ERB.new(File.read($resolver.std_path / "csr/I/pmpcfgN.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/csr/I/pmpcfgN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

file "#{$resolver.std_path}/csr/I/mcounteren.yaml" => [
  "#{$resolver.std_path}/csr/I/mcounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($resolver.std_path / "csr/I/mcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$resolver.std_path}/csr/I/mcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$resolver.std_path}/csr/S/scounteren.yaml" => [
  "#{$resolver.std_path}/csr/S/scounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($resolver.std_path / "csr/S/scounteren.layout"), trim_mode: "-")
  erb.filename = "#{$resolver.std_path}/csr/S/scounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$resolver.std_path}/csr/Sscofpmf/scountovf.yaml" => [
  "#{$resolver.std_path}/csr/Sscofpmf/scountovf.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($resolver.std_path / "csr/Sscofpmf/scountovf.layout"), trim_mode: "-")
  erb.filename = "#{$resolver.std_path}/csr/Sscofpmf/scountovf.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$resolver.std_path}/csr/H/hcounteren.yaml" => [
  "#{$resolver.std_path}/csr/H/hcounteren.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($resolver.std_path / "csr/H/hcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$resolver.std_path}/csr/H/hcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$resolver.std_path}/csr/Zicntr/mcountinhibit.yaml" => [
  "#{$resolver.std_path}/csr/Zicntr/mcountinhibit.layout",
  __FILE__
] do |t|
  erb = ERB.new(File.read($resolver.std_path / "csr/Zicntr/mcountinhibit.layout"), trim_mode: "-")
  erb.filename = "#{$resolver.std_path}/csr/Zicntr/mcountinhibit.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

# Define all acquire/release combinations
aq_rl_variants = [
  { suffix: "", aq: false, rl: false },           # base instruction
  { suffix: ".aq", aq: true, rl: false },         # acquire only
  { suffix: ".rl", aq: false, rl: true },         # release only
  { suffix: ".aqrl", aq: true, rl: true }         # both acquire and release
]

# AMO instruction generation from layouts
%w[amoadd amoand amomax amomaxu amomin amominu amoor amoswap amoxor].each do |op|
  ["b", "h", "w", "d"].each do |size|
    # Determine target extension directory based on size
    extension_dir = %w[b h].include?(size) ? "Zabha" : "Zaamo"

    aq_rl_variants.each do |variant|
      file "#{$resolver.std_path}/inst/#{extension_dir}/#{op}.#{size}#{variant[:suffix]}.yaml" => [
        "#{$resolver.std_path}/inst/Zaamo/#{op}.SIZE.AQRL.layout",
        __FILE__
      ] do |t|
        FileUtils.rm_f(t.name)
        aq = variant[:aq]
        rl = variant[:rl]
        erb = ERB.new(File.read($resolver.std_path / "inst/Zaamo/#{op}.SIZE.AQRL.layout"), trim_mode: "-")
        erb.filename = "#{$resolver.std_path}/inst/Zaamo/#{op}.SIZE.AQRL.layout"
        File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
        File.chmod(0444, t.name)
      end
    end
  end
end

# AMOCAS instruction generation from Zabha layout (supports both Zabha and Zacas)
# Zabha variants (b, h) -> generated in Zabha directory
["b", "h", "w", "d", "q"].each do |size|
  # Determine target extension directory based on size
  extension_dir = %w[w d q].include?(size) ? "Zacas" : "Zabha"

  aq_rl_variants.each do |variant|
    file "#{$resolver.std_path}/inst/#{extension_dir}/amocas.#{size}#{variant[:suffix]}.yaml" => [
      "#{$resolver.std_path}/inst/Zacas/amocas.SIZE.AQRL.layout",
      __FILE__
    ] do |t|
      FileUtils.rm_f(t.name)
      aq = variant[:aq]
      rl = variant[:rl]
      erb = ERB.new(File.read($resolver.std_path / "inst/Zacas/amocas.SIZE.AQRL.layout"), trim_mode: "-")
      erb.filename = "#{$resolver.std_path}/inst/Zacas/amocas.SIZE.AQRL.layout"
      File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
      File.chmod(0444, t.name)
    end
  end
end

# LR/SC instruction generation from layouts
%w[lr sc].each do |op|
  ["w", "d"].each do |size|
    aq_rl_variants.each do |variant|
      file "#{$resolver.std_path}/inst/Zalrsc/#{op}.#{size}#{variant[:suffix]}.yaml" => [
        "#{$resolver.std_path}/inst/Zalrsc/#{op}.SIZE.AQRL.layout",
        __FILE__
      ] do |t|
        FileUtils.rm_f(t.name)
        aq = variant[:aq]
        rl = variant[:rl]
        erb = ERB.new(File.read($resolver.std_path / "inst/Zalrsc/#{op}.SIZE.AQRL.layout"), trim_mode: "-")
        erb.filename = "#{$resolver.std_path}/inst/Zalrsc/#{op}.SIZE.AQRL.layout"
        File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
        File.chmod(0444, t.name)
      end
    end
  end
end

# Zalasr load-acquire generation from layout
zalasr_load_variants = [
  { suffix: ".aq", rl: false },
  { suffix: ".aqrl", rl: true }
]

["b", "h", "w", "d"].each do |size|
  zalasr_load_variants.each do |variant|
    file "#{$resolver.std_path}/inst/Zalasr/l#{size}#{variant[:suffix]}.yaml" => [
      "#{$resolver.std_path}/inst/Zalasr/lSIZE.AQRL.layout",
      __FILE__
    ] do |t|
      FileUtils.rm_f(t.name)
      rl = variant[:rl]
      erb = ERB.new(File.read($resolver.std_path / "inst/Zalasr/lSIZE.AQRL.layout"), trim_mode: "-")
      erb.filename = "#{$resolver.std_path}/inst/Zalasr/lSIZE.AQRL.layout"
      File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
      File.chmod(0444, t.name)
    end
  end
end

# Zalasr store-release generation from layout
zalasr_store_variants = [
  { suffix: ".rl", aq: false },
  { suffix: ".aqrl", aq: true }
]

["b", "h", "w", "d"].each do |size|
  zalasr_store_variants.each do |variant|
    file "#{$resolver.std_path}/inst/Zalasr/s#{size}#{variant[:suffix]}.yaml" => [
      "#{$resolver.std_path}/inst/Zalasr/sSIZE.AQRL.layout",
      __FILE__
    ] do |t|
      FileUtils.rm_f(t.name)
      aq = variant[:aq]
      erb = ERB.new(File.read($resolver.std_path / "inst/Zalasr/sSIZE.AQRL.layout"), trim_mode: "-")
      erb.filename = "#{$resolver.std_path}/inst/Zalasr/sSIZE.AQRL.layout"
      File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
      File.chmod(0444, t.name)
    end
  end
end

# MOP.R instruction generation from layout (mop.r.0 through mop.r.31)
(0..31).each do |n|
  file "#{$resolver.std_path}/inst/Zimop/mop.r.#{n}.yaml" => [
    "#{$resolver.std_path}/inst/Zimop/mop.r.N.layout",
    __FILE__
  ] do |t|
    FileUtils.rm_f(t.name)
    erb = ERB.new(File.read($resolver.std_path / "inst/Zimop/mop.r.N.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/inst/Zimop/mop.r.N.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
    File.chmod(0444, t.name)
  end
end

# MOP.RR instruction generation from layout (mop.rr.0 through mop.rr.7)
(0..7).each do |n|
  file "#{$resolver.std_path}/inst/Zimop/mop.rr.#{n}.yaml" => [
    "#{$resolver.std_path}/inst/Zimop/mop.rr.N.layout",
    __FILE__
  ] do |t|
    FileUtils.rm_f(t.name)
    erb = ERB.new(File.read($resolver.std_path / "inst/Zimop/mop.rr.N.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/inst/Zimop/mop.rr.N.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
    File.chmod(0444, t.name)
  end
end

# C.MOP instruction generation from layout (c.mop.1, c.mop.3, c.mop.5, c.mop.7, c.mop.9, c.mop.11, c.mop.13, c.mop.15)
[1, 3, 5, 7, 9, 11, 13, 15].each do |n|
  file "#{$resolver.std_path}/inst/Zcmop/c.mop.#{n}.yaml" => [
    "#{$resolver.std_path}/inst/Zcmop/c.mop.N.layout",
    __FILE__
  ] do |t|
    FileUtils.rm_f(t.name)
    erb = ERB.new(File.read($resolver.std_path / "inst/Zcmop/c.mop.N.layout"), trim_mode: "-")
    erb.filename = "#{$resolver.std_path}/inst/Zcmop/c.mop.N.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
    File.chmod(0444, t.name)
  end
end

def gen_arch_file(f)
  FileUtils.rm_f f
  Rake::Task[f].invoke
  FileUtils.chmod 0444, f
end

namespace :gen do
  desc "Generate architecture files from layouts"
  task :arch do
    (3..31).each do |hpm_num|
      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/mhpmcounter#{hpm_num}.yaml")
      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/mhpmcounter#{hpm_num}h.yaml")
      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/mhpmevent#{hpm_num}.yaml")
      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/mhpmevent#{hpm_num}h.yaml")

      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/hpmcounter#{hpm_num}.yaml")
      gen_arch_file("#{$resolver.std_path}/csr/Zihpm/hpmcounter#{hpm_num}h.yaml")
      gen_arch_file("#{$resolver.std_path}/param/HPM_COUNTER#{hpm_num}_WIDTH.yaml")
    end

    gen_arch_file("#{$resolver.std_path}/csr/I/mcounteren.yaml")
    gen_arch_file("#{$resolver.std_path}/csr/S/scounteren.yaml")
    gen_arch_file("#{$resolver.std_path}/csr/Sscofpmf/scountovf.yaml")
    gen_arch_file("#{$resolver.std_path}/csr/H/hcounteren.yaml")
    gen_arch_file("#{$resolver.std_path}/csr/Zicntr/mcountinhibit.yaml")

    (0..63).each do |pmpaddr_num|
      gen_arch_file("#{$resolver.std_path}/csr/I/pmpaddr#{pmpaddr_num}.yaml")
    end

    (0..15).each do |pmpcfg_num|
      gen_arch_file("#{$resolver.std_path}/csr/I/pmpcfg#{pmpcfg_num}.yaml")
    end

    # Generate AMO instruction files
    %w[amoadd amoand amomax amomaxu amomin amominu amoor amoswap amoxor].each do |op|
      ["b", "h", "w", "d"].each do |size|
        extension_dir = %w[b h].include?(size) ? "Zabha" : "Zaamo"
        ["", ".aq", ".rl", ".aqrl"].each do |suffix|
          gen_arch_file("#{$resolver.std_path}/inst/#{extension_dir}/#{op}.#{size}#{suffix}.yaml")
        end
      end
    end

    # Generate AMOCAS instruction files
    ["b", "h", "w", "d", "q"].each do |size|
      ["", ".aq", ".rl", ".aqrl"].each do |suffix|
        # Determine target extension directory based on size
        extension_dir = %w[w d q].include?(size) ? "Zacas" : "Zabha"

        gen_arch_file("#{$resolver.std_path}/inst/#{extension_dir}/amocas.#{size}#{suffix}.yaml")
      end
    end

    # Generate LR/SC instruction files
    %w[lr sc].each do |op|
      ["w", "d"].each do |size|
        aq_rl_variants.each do |variant|
          gen_arch_file("#{$resolver.std_path}/inst/Zalrsc/#{op}.#{size}#{variant[:suffix]}.yaml")
        end
      end
    end

    # Generate Zalasr load/store instruction files
    ["b", "h", "w", "d"].each do |size|
      zalasr_load_variants.each do |variant|
        gen_arch_file("#{$resolver.std_path}/inst/Zalasr/l#{size}#{variant[:suffix]}.yaml")
      end
      zalasr_store_variants.each do |variant|
        gen_arch_file("#{$resolver.std_path}/inst/Zalasr/s#{size}#{variant[:suffix]}.yaml")
      end
    end

    # Generate MOP.R instruction files (mop.r.0 through mop.r.31)
    (0..31).each do |n|
      gen_arch_file("#{$resolver.std_path}/inst/Zimop/mop.r.#{n}.yaml")
    end

    # Generate MOP.RR instruction files (mop.rr.0 through mop.rr.7)
    (0..7).each do |n|
      gen_arch_file("#{$resolver.std_path}/inst/Zimop/mop.rr.#{n}.yaml")
    end

    # Generate C.MOP instruction files (c.mop.1, c.mop.3, c.mop.5, c.mop.7, c.mop.9, c.mop.11, c.mop.13, c.mop.15)
    [1, 3, 5, 7, 9, 11, 13, 15].each do |n|
      gen_arch_file("#{$resolver.std_path}/inst/Zcmop/c.mop.#{n}.yaml")
    end
  end

  desc "DEPRECATED -- Run `./bin/udb-gen ext-doc --help` instead"
  task :ext_pdf do
    warn "DEPRECATED     `./do gen:ext_pdf` was removed in favor of `./bin/generate ext-doc `"
    exit(1)
  end

  desc("DEPRECATED -- Run `./bin/udb-gen isa-explorer -t xlsx -o gen/isa_explorer` instead")
  task :isa_explorer_spreadsheet do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t xlsx -o gen/isa_explorer` instead"
    exit(1)
  end

  desc("DEPRECATED -- Run `./bin/udb-gen isa-explorer -t ext-browser -o gen/isa_explorer` instead")
  task :isa_explorer_browser_ext do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t ext-browser -o gen/isa_explorer` instead"
    exit(1)
  end

  desc("DEPRECATED -- Run `./bin/udb-gen isa-explorer -t inst-browser -o gen/isa_explorer` instead")
  task :isa_explorer_browser_inst do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t inst-browser -o gen/isa_explorer` instead"
    exit(1)
  end

  desc("DEPRECATED -- Run `./bin/udb-gen isa-explorer -t csr-browser -o gen/isa_explorer` instead")
  task :isa_explorer_browser_csr do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t csr-browser -o gen/isa_explorer` instead"
    exit(1)
  end

  desc("DEPRECATED")
  task :isa_explorer_browser do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t csr-browser -o gen/isa_explorer` instead"
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t inst-browser -o gen/isa_explorer` instead"
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate isa-explorer -t ext-browser -o gen/isa_explorer` instead"
    exit(1)
  end

  task :html_manual do
    Udb.logger.warn "DEPRECATED -- Run `./bin/generate manual -h` for help"
    exit(1)
  end

  desc "Generate strict config files for profiles"
  task :cfg do
    cfg_arch = $resolver.cfg_arch_for("_")
    FileUtils.mkdir_p $resolver.cfgs_path / "profile"
    cfg_arch.profiles.each do |profile|
      path = $resolver.cfgs_path / "profile" / "#{profile.name}.yaml"
      FileUtils.rm_f path
      File.write(
        path,
        <<~YAML.strip.concat("\n")
          # SPDX-License-Identifier: CC0-1.0

          # AUTO-GENERATED FILE. DO NOT EDIT
          # To regenerate, run `./do gen:cfg` in the UDB root directory
          # The data comes from the UDB profile definitions in spec/std/isa/profile/

          #{YAML.dump(profile.to_strict_config)}
        YAML
      )
      File.chmod(0444, path)
    end
  end
end

namespace :test do
  task :unit do
    Udb.logger.warn "Running unit tests through do/Rake has been deprecated"
    Udb.logger.warn "Try `./bin/regress --tag unit` instead"
  end

  task :smoke do
    Udb.logger.warn "Running smoke through do/Rake has been deprecated"
    Udb.logger.warn "Try `./bin/regress --tag smoke` instead"
  end

  task :regress do
    Udb.logger.warn "Running regression through do/Rake has been deprecated"
    Udb.logger.warn "Try `./bin/regress --all` instead"
  end

  namespace :scripts do
    desc "Run unit tests for tools/scripts"
    task :unit do
      Dir.chdir($root) do
        sh "#{$root}/bin/ruby -Itools/scripts tools/scripts/test/run.rb"
      end
    end
  end
end

desc <<~DESC
  Generate all portfolio-based PDF artifacts (profiles)
DESC
task :portfolios do
  portfolio_start_msg("MockProfileRelease")
  Rake::Task["#{$root}/gen/profile/pdf/MockProfileRelease.pdf"].invoke
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

# Shortcut targets for building Profile Releases.
task "MockProfile": "#{$root}/gen/profile/pdf/MockProfileRelease.pdf"
task "MockProfileRelease": "#{$root}/gen/profile/pdf/MockProfileRelease.pdf"
task "RVI20": "#{$root}/gen/profile/pdf/RVI20ProfileRelease.pdf"
task "RVA20": "#{$root}/gen/profile/pdf/RVA20ProfileRelease.pdf"
task "RVA22": "#{$root}/gen/profile/pdf/RVA22ProfileRelease.pdf"
task "RVA23": "#{$root}/gen/profile/pdf/RVA23ProfileRelease.pdf"
task "RVB23": "#{$root}/gen/profile/pdf/RVB23ProfileRelease.pdf"
