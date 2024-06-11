# frozen_string_literal: true

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
rule %r{#{$root}/.stamps/arch-gen-.*\.stamp} => proc { |tname|
  config_name = Pathname.new(tname).basename(".stamp").sub("arch-gen-", "")
  arch_files = Dir.glob($root / "arch" / "**" / "*.yaml")
  config_files = Dir.glob($root / config_name / "overrides" / "**" / "*.yaml") + [$root / "cfgs" / config_name / "params.yaml"]
  [
    "#{$root}/lib/arch_gen.rb",
    "#{$root}/tasks/arch_gen.rake",
    "ext/riscv-opcodes/instr_dict.yaml"
  ] + arch_files + config_files
} do |t|
  config_name = Pathname.new(t.name).basename(".stamp").sub("arch-gen-", "")

  arch_gen = ArchGen.new(config_name)
  puts "Generating architecture definition in #{arch_gen.gen_dir.relative_path_from($root)}"

  # remove anything old
  FileUtils.rm_rf arch_gen.gen_dir

  arch_gen.generate
  FileUtils.touch t.name
end

namespace :gen do
  desc "Generate the architecture files for config_name"
  task :arch, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    Rake::Task["#{$root}/.stamps/arch-gen-#{args[:config_name]}.stamp"].invoke(args[:config_name])
  end
end
