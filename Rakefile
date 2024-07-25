# frozen_string_literal: true

$root = Pathname.new(__FILE__).dirname.realpath
$lib = $root / "lib"

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

desc "Validate the arch docs"
task validate: "gen:arch" do
  validator = Validator.instance
  Dir.glob("#{$root}/arch/**/*.yaml") do |f|
    validator.validate(f)
  end
  puts "All files validate against their schema"
end

def insert_warning(str, from)
  # insert a warning on the second line
  lines = str.lines
  first_line = lines.shift
  lines.unshift(first_line, "\n# WARNING: This file is auto-generated from #{Pathname.new(from).relative_path_from($root)}\n\n").join("")
end

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
