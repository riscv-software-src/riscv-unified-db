# frozen_string_literal: true

# This file contains tasks related to the generation of a configured architecture specification

require_relative File.join("..", "lib", "arch_gen.rb")

# checkout riscv-opcodes submodule, if needed
file "ext/riscv-opcodes/parse.py" do
  "git submodule update --init ext/riscv-opcodes"
end

# setup python venv, needed to use pip with Ubuntu's python install
file "ext/riscv-opcodes/.venv/bin/pip" => "ext/riscv-opcodes/parse.py" do
  Dir.chdir "#{$root}/ext/riscv-opcodes" do
    sh "python3 -m venv #{$root}/ext/riscv-opcodes/.venv"
  end
end

# run pip to install riscv-opcodes python dependencies
file "ext/riscv-opcodes/.venv/lib/python3.12/site-packages/yaml/__init__.py" => "ext/riscv-opcodes/.venv/bin/pip" do
  Dir.chdir "#{$root}/ext/riscv-opcodes" do
    sh "#{$root}/ext/riscv-opcodes/.venv/bin/pip install -r requirements.txt"
  end
end

# generate the instruction dictionary from riscv-opcodes
file "ext/riscv-opcodes/instr_dict.yaml" => "ext/riscv-opcodes/.venv/lib/python3.12/site-packages/yaml/__init__.py" do
  Dir.chdir "#{$root}/ext/riscv-opcodes" do
    sh "#{$root}/ext/riscv-opcodes/.venv/bin/python parse.py 'rv*'"
  end
end

# stamp to indicate completion of Arch Gen for a given config
rule %r{#{$root}/\.stamps/arch-gen-.*\.stamp} => proc { |tname|
  config_name = Pathname.new(tname).basename(".stamp").sub("arch-gen-", "")
  arch_files = Dir.glob($root / "arch" / "**" / "*.yaml")
  config_files =
    Dir.glob($root / config_name / "overrides" / "**" / "*.yaml") +
    [$root / "cfgs" / config_name / "params.yaml"]
  [
    "#{$root}/.stamps",
    "#{$root}/lib/arch_gen.rb",
    "#{$root}/tasks/arch_gen.rake",
    "ext/riscv-opcodes/instr_dict.yaml"
  ] + arch_files + config_files
} do |t|
  config_name = Pathname.new(t.name).basename(".stamp").sub("arch-gen-", "")

  arch_gen = ArchGen.new(config_name)
  puts "Generating architecture definition in #{arch_gen.gen_dir.relative_path_from($root)}"

  arch_gen.generate

  puts "  Found #{arch_gen.implemented_csrs.size} CSRs"
  puts "  Found #{arch_gen.implemented_extensions.size} Extensions"
  puts "  Found #{arch_gen.implemented_instructions.size} Instructions"

  FileUtils.touch t.name
end

namespace :gen do
  desc "Generate the architecture files for config_name"
  task :arch, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    Rake::Task["#{$root}/.stamps/arch-gen-#{args[:config_name]}.stamp"].invoke(args[:config_name])
  end
end

file ".venv/bin/pip" do
  Dir.chdir $root do
    sh "python3 -m venv #{$root}/.venv"
  end
end

file ".venv/lib/python3.12/site-packages/json_schema_for_humans/__init__.py" => ".venv/bin/pip" do
  sh "#{$root}/.venv/bin/pip install json-schema-for-humans"
end

file "docs/schema/arch_schema.md" => Rake::FileList[
  ".venv/lib/python3.12/site-packages/json_schema_for_humans/__init__.py",
  "arch/**/*.json",
  "arch/*.json"
] do |t|
  sh ".venv/bin/generate-schema-doc --config template_name=md arch/*.json,arch/**/*.json #{File.dirname(t.name)}"
end

file "docs/schema/arch_schema.html" => Rake::FileList[
  ".venv/lib/python3.12/site-packages/json_schema_for_humans/__init__.py",
  "arch/**/*.json",
  "arch/*.json"
] do |t|
  sh ".venv/bin/generate-schema-doc --config template_name=js arch/*.json,arch/**/*.json #{File.dirname(t.name)}"
end

namespace :doc do
  desc "Generate documentation for the architecture spec format"
  task arch_format: ["docs/schema/arch_schema.md", "docs/schema/arch_schema.html"]
end
