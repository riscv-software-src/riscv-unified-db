# frozen_string_literal: true

require "etc"

$root = Pathname.new(__FILE__).dirname.realpath
$lib = $root / "lib"

require "ruby-progressbar"
require "yard"
require "minitest/test_task"

require_relative $root / "lib" / "validate"

directory "#{$root}/.stamps"

Dir.glob("#{$root}/backends/*/tasks.rake") do |rakefile|
  load rakefile
end

directory "#{$root}/.stamps"

file "#{$root}/.stamps/dev_gems" => "#{$root}/.stamps" do
  Dir.chdir($root) do
    sh "bundle config set --local with development"
    sh "bundle install"
    FileUtils.touch "#{$root}/.stamps/dev_gems"
  end
end

namespace :gen do
  desc "Generate documentation for the ruby tooling"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc"
    end
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

Minitest::TestTask.create :idl_test do |t|
  t.test_globs = ["#{$root}/lib/idl/tests/test_*.rb"]
end

desc "Clean up all generated files"
task :clean do
  FileUtils.rm_rf $root / "gen"
  FileUtils.rm_rf $root / ".stamps"
end

namespace :validate do
  task :insts do
    puts "Checking instruction encodings..."
    inst_paths = Dir.glob("#{$root}/arch/inst/**/*.yaml").map { |f| Pathname.new(f) }
    inst_paths.each do |inst_path|
      Validator.instance.validate_instruction(inst_path)
    end
    puts "All instruction encodings pass basic sanity tests"
  end
  task schema: "gen:arch" do
    validator = Validator.instance
    puts "Checking arch files against schema.."
    arch_files = Dir.glob("#{$root}/arch/**/*.yaml")
    progressbar = ProgressBar.create(total: arch_files.size)
    arch_files.each do |f|
      progressbar.increment
      validator.validate(f)
    end
    puts "All files validate against their schema"  
  end
  task idl: ["gen:arch", "#{$root}/.stamps/arch-gen-_32.stamp", "#{$root}/.stamps/arch-gen-_64.stamp"]  do
    print "Parsing IDL code for RV32..."
    arch_def_32 = arch_def_for("_32")
    puts "done"

    arch_def_32.type_check

    print "Parsing IDL code for RV64..."
    arch_def_64 = arch_def_for("_64")
    puts "done"

    arch_def_64.type_check

    # arch_def_64 = arch_def_for("_64")
    # arch_def_64.type_check

    # puts "Type checking IDL code..."
    # progressbar = ProgressBar.create(title: "Instructions", total: arch_def_32.instructions.size + arch_def_64.instructions.size)
    # arch_def_32.instructions.each do |inst|
    #   progressbar.increment
    #   inst.type_checked_operation_ast(arch_def_32.idl_compiler, arch_def_32.symtab, 32) if inst.rv32?
    # end
    # arch_def_64.instructions.each do |inst|
    #   progressbar.increment
    #   inst.type_checked_operation_ast(arch_def_64.idl_compiler, arch_def_64.symtab, 64) if inst.rv64?
    #   # also need to check for an RV64 machine running with effective XLEN of 32
    #   inst.type_checked_operation_ast(arch_def_64.idl_compiler, arch_def_64.symtab, 32) if inst.rv64? && inst.rv32?
    # end

    # progressbar = ProgressBar.create(title: "CSRs", total: arch_def_32.csrs.size + arch_def_64.csrs.size)
    # arch_def_32.csrs.each do |csr|
    #   progressbar.increment
    #   profile = RubyProf::Profile.new
    #   result = profile.profile do
    #     if csr.has_custom_sw_read?
    #       csr.type_checked_sw_read_ast(arch_def_32.symtab) if csr.defined_in_base32?
    #     end
    #     csr.fields.each do |field|
    #       unless field.type_ast(arch_def_32.symtab).nil?
    #         field.type_checked_type_ast(arch_def_32.symtab) if csr.defined_in_base32? && field.defined_in_base32?
    #       end
    #       unless field.reset_value_ast(arch_def_32.symtab).nil?
    #         field.type_checked_reset_value_ast(arch_def_32.symtab) if csr.defined_in_base32? && field.defined_in_base32?
    #       end
    #       unless field.sw_write_ast(arch_def_32.symtab).nil?
    #         field.type_checked_sw_write_ast(arch_def_32.symtab, 32) if csr.defined_in_base32? && field.defined_in_base32?
    #       end
    #     end
    #   end
    #   RubyProf::GraphHtmlPrinter.new(result).print(File.open("#{csr.name}-prof.html", "w+"), {})
    # end
    # arch_def_64.csrs.each do |csr|
    #   progressbar.increment
    #   if csr.has_custom_sw_read?
    #     csr.type_checked_sw_read_ast(arch_def_64.symtab) if csr.defined_in_base64?
    #   end
    #   csr.fields.each do |field|
    #     unless field.type_ast(arch_def_64.symtab).nil?
    #       field.type_checked_type_ast(arch_def_64.symtab) if csr.defined_in_base64? && field.defined_in_base64?
    #     end
    #     unless field.reset_value_ast(arch_def_64.symtab).nil?
    #       field.type_checked_reset_value_ast(arch_def_64.symtab) if csr.defined_in_base64? && field.defined_in_base64?
    #     end
    #     unless field.sw_write_ast(arch_def_64.symtab).nil?
    #       field.type_checked_sw_write_ast(arch_def_64.symtab, 32) if csr.defined_in_base32? && field.defined_in_base32?
    #       field.type_checked_sw_write_ast(arch_def_64.symtab, 64) if csr.defined_in_base64? && field.defined_in_base64?
    #     end
    #   end
    # end
    # progressbar = ProgressBar.create(title: "Functions", total: arch_def_32.functions.size + arch_def_64.functions.size)
    # arch_def_32.functions.each do |func|
    #   progressbar.increment
    #   func.type_check(arch_def_32.symtab)
    # end
    # arch_def_64.functions.each do |func|
    #   progressbar.increment
    #   func.type_check(arch_def_64.symtab)
    # end
    puts "All IDL passed type checking"
  end
end

desc "Validate the arch docs"
task validate: ["validate:schema", "validate:idl", "validate:insts"]

def insert_warning(str, from)
  # insert a warning on the second line
  lines = str.lines
  first_line = lines.shift
  lines.unshift(first_line, "\n# WARNING: This file is auto-generated from #{Pathname.new(from).relative_path_from($root)}\n\n").join("")
end
private :insert_warning

(3..31).each do |hpm_num|
  file "#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmcounterN.layout",
    __FILE__
   ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmcounter#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmcounterNh.layout",
    __FILE__
   ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmcounterNh.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmcounterNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmeventN.layout",
    __FILE__
   ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmeventN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmeventN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/mhpmevent#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/mhpmeventNh.layout",
    __FILE__
   ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/mhpmeventNh.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/mhpmeventNh.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}.yaml" => [
    "#{$root}/arch/csr/Zihpm/hpmcounterN.layout",
    __FILE__
   ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/Zihpm/hpmcounterN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/Zihpm/hpmcounterN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
  file "#{$root}/arch/csr/Zihpm/hpmcounter#{hpm_num}h.yaml" => [
    "#{$root}/arch/csr/Zihpm/hpmcounterNh.layout",
    __FILE__
    ] do |t|
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
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
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
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
    puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
    erb = ERB.new(File.read($root / "arch/csr/I/pmpcfgN.layout"), trim_mode: "-")
    erb.filename = "#{$root}/arch/csr/I/pmpcfgN.layout"
    File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
  end
end

file "#{$root}/arch/csr/I/mcounteren.yaml" => [
  "#{$root}/arch/csr/I/mcounteren.layout",
  __FILE__
] do |t|
  puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
  erb = ERB.new(File.read($root / "arch/csr/I/mcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/I/mcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/S/scounteren.yaml" => [
  "#{$root}/arch/csr/S/scounteren.layout",
  __FILE__
] do |t|
  puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
  erb = ERB.new(File.read($root / "arch/csr/S/scounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/S/scounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/H/hcounteren.yaml" => [
  "#{$root}/arch/csr/H/hcounteren.layout",
  __FILE__
] do |t|
  puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
  erb = ERB.new(File.read($root / "arch/csr/H/hcounteren.layout"), trim_mode: "-")
  erb.filename = "#{$root}/arch/csr/H/hcounteren.layout"
  File.write(t.name, insert_warning(erb.result(binding), t.prerequisites.first))
end

file "#{$root}/arch/csr/Zicntr/mcountinhibit.yaml" => [
  "#{$root}/arch/csr/Zicntr/mcountinhibit.layout",
  __FILE__
] do |t|
  puts "Generating #{Pathname.new(t.name).relative_path_from($root)}"
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
