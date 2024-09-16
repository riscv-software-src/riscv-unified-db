# frozen_string_literal: true

# This file contains tasks related to the generation of a configured architecture specification

require_relative "lib/arch_gen"

ARCH_GEN_DIR = Pathname.new(__FILE__).dirname

def arch_def_for(config_name)
  config_name = "_" if config_name.nil?
  @arch_defs ||= {}
  return @arch_defs[config_name] if @arch_defs.key?(config_name)

  if config_name == "_"
    @arch_defs[config_name] = ArchDef.new
  else
    @arch_defs[config_name] = ImplArchDef.new(config_name)
  end
end

file "#{$root}/.stamps/arch-gen.stamp" => (
  [
    "#{$root}/.stamps",
    "#{ARCH_GEN_DIR}/lib/arch_gen.rb",
    "#{$root}/lib/idl/ast.rb",
    "#{ARCH_GEN_DIR}/tasks.rake",
    __FILE__
  ] + Dir.glob($root / "arch" / "**" / "*.yaml")
) do |t|
  csr_hash = Dir.glob($root / "arch" / "csr" / "**" / "*.yaml").map do |f|
    csr_obj = YAML.load_file(f)
    csr_name = csr_obj.keys[0]
    csr_obj[csr_name]["name"] = csr_name
    csr_obj[csr_name]["fields"].map do |k, v|
      v["name"] = k
      [k, v]
    end
    csr_obj[csr_name]["__source"] = f
    [csr_name, csr_obj[csr_name]]
  end.to_h
  inst_hash = Dir.glob($root / "arch" / "inst" / "**" / "*.yaml").map do |f|
    inst_obj = YAML.load_file(f)
    inst_name = inst_obj.keys[0]
    inst_obj[inst_name]["name"] = inst_name
    inst_obj[inst_name]["__source"] = f
    [inst_name, inst_obj[inst_name]]
  end.to_h
  ext_hash = Dir.glob($root / "arch" / "ext" / "**" / "*.yaml").map do |f|
    ext_obj = YAML.load_file(f)
    ext_name = ext_obj.keys[0]
    ext_obj[ext_name]["name"] = ext_name
    ext_obj[ext_name]["__source"] = f
    [ext_name, ext_obj[ext_name]]
  end.to_h
  profile_family_hash = Dir.glob($root / "arch" / "profile_family" / "**" / "*.yaml").map do |f|
    profile_obj = YAML.load_file(f)
    profile_name = profile_obj.keys[0]
    profile_obj[profile_name]["name"] = profile_name
    profile_obj[profile_name]["__source"] = f
    [profile_name, profile_obj[profile_name]]
  end.to_h
  profile_hash = Dir.glob($root / "arch" / "profile" / "**" / "*.yaml").map do |f|
    profile_obj = YAML.load_file(f)
    profile_name = profile_obj.keys[0]
    profile_obj[profile_name]["name"] = profile_name
    profile_obj[profile_name]["__source"] = f
    [profile_name, profile_obj[profile_name]]
  end.to_h

  arch_def = {
    "instructions" => inst_hash,
    "extensions" => ext_hash,
    "csrs" => csr_hash,
    "profile_families" => profile_family_hash,
    "profiles" => profile_hash
  }

  dest = "#{$root}/gen/_/arch/arch_def.yaml"
  FileUtils.mkdir_p File.dirname(dest)
  File.write(dest, YAML.dump(arch_def))

  FileUtils.touch(t.name)
end

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

  desc "Generate a unified architecture file (configuration independent)"
  task :arch do
    Rake::Task["#{$root}/.stamps/arch-gen.stamp"].invoke
  end
end

namespace :validate do
  desc "Validate that a configuration folder valid for the list of extensions it claims to implement"
  task :cfg, [:config_name] do |_t, args|
    raise "No config '#{args[:config_name]}' found in cfgs/" unless ($root / "cfgs" / args[:config_name]).directory?

    ArchGen.new(args[:config_name]).validate_params

    puts "Success! The '#{args[:config_name]}' configuration passes validation checks"
  end
end
