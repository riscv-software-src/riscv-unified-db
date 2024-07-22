# frozen_string_literal: true

# This file contains tasks related to the generation of a configured architecture specification

require_relative "lib/arch_gen"

ARCH_GEN_DIR = Pathname.new(__FILE__).dirname

# stamp to indicate completion of Arch Gen for a given config
rule %r{#{$root}/\.stamps/arch-gen-.*\.stamp} => proc { |tname|
  config_name = Pathname.new(tname).basename(".stamp").sub("arch-gen-", "")
  arch_files = Dir.glob($root / "arch" / "**" / "*.yaml")
  config_files =
    Dir.glob($root / "cfgs" / config_name / "arch_overlay" / "**" / "*.yaml") +
    [($root / "cfgs" / config_name / "params.yaml").to_s]
  [
    "#{$root}/.stamps",
    "#{ARCH_GEN_DIR}/lib/arch_gen.rb",
    "#{$root}/lib/idl/ast.rb",
    "#{ARCH_GEN_DIR}/tasks.rake"
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
  desc "Generate the cfg-specific architecture files for config_name"
  task :cfg_arch, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    Rake::Task["#{$root}/.stamps/arch-gen-#{args[:config_name]}.stamp"].invoke(args[:config_name])
  end
end
