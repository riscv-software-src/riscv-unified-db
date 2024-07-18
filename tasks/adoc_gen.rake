# frozen_string_literal: true

require_relative "../lib/arch_def"

["csr", "inst", "ext", "func"].each do |type|
  rule %r{#{$root}/\.stamps/adoc-gen-#{type}s-.*\.stamp} => proc { |tname|
    config_name = Pathname.new(tname).basename(".stamp").sub("adoc-gen-#{type}s-", "")
    [
      "#{$root}/.stamps/arch-gen-#{config_name}.stamp",
      ($root / "views" / "adoc" / "#{type}.adoc.erb").to_s,
      "lib/arch_def.rb",
      "lib/idl/passes/gen_adoc.rb",
      "tasks/adoc_gen.rake",
      "#{$root}/.stamps"
    ]
  } do |t|
    config_name = Pathname.new(t.name).basename(".stamp").sub("adoc-gen-#{type}s-", "")

    arch_def = ArchDef.new(config_name)
    adoc_template_path = $root / "views" / "adoc" / "#{type}.adoc.erb"
    adoc_template = adoc_template_path.read
    erb = ERB.new(adoc_template, trim_mode: "-")
    erb.filename = adoc_template_path.to_s

    dir_path = $root / "gen" / config_name / "adoc" / "#{type}s"
    FileUtils.mkdir_p dir_path

    case type
    when "csr"
      arch_def.implemented_csrs.each do |csr|
        path = dir_path / "#{csr.name}.adoc"
        File.write(path, erb.result(binding))
      end
    when "inst"
      arch_def.implemented_instructions.each do |inst|
        path = dir_path / "#{inst.name}.adoc"
        File.write(path, erb.result(binding))
      end
    when "ext"
      arch_def.implemented_extensions.each do |ext|
        ext = arch_def.extension(ext.name)
        path = dir_path / "#{ext.name}.adoc"
        File.write(path, erb.result(binding))
      end
    when "func"
      isa_def = arch_def.global_ast
      global_symtab = arch_def.sym_table
      path = dir_path / "funcs.adoc"
      File.write(path, erb.result(binding))
    else
      raise "todo"
    end

    FileUtils.touch(t.name)
  end
end

# rule %r{#{$root}/\.stamps/adoc-gen-insts-.*\.stamp} => proc { |tname|
#   config_name = Pathname.new(tname).basename(".stamp").sub("adoc-gen-insts-", "")
#   [
#     "#{$root}/.stamps/arch-gen-#{config_name}.stamp",
#     "lib/arch_def.rb",
#     "tasks/adoc_gen.rake"
#   ]
# } do |t|
#   config_name = Pathname.new(t.name).basename(".stamp").sub("adoc-gen-insts-", "")

#   arch_def = ArchDef.new(config_name)
#   inst_adoc_template_path = $root / "views" / "adoc" / "inst.adoc.erb"
#   inst_adoc_template = inst_adoc_template_path.read
#   erb = ERB.new(inst_adoc_template, trim_mode: "-")
#   erb.filename = inst_adoc_template_path.to_s

#   dir_path = $root / "gen" / config_name / "adoc" / "insts"
#   FileUtils.mkdir_p dir_path

#   arch_def.instructions.each do |inst|
#     path = dir_path / "#{inst.name}.adoc"
#     File.write(path, erb.result(binding))
#   end

#   FileUtils.touch(t.name)
# end

namespace :gen do
  desc "Generate Asciidoc source for config into gen/CONFIG_NAME/adoc"
  task :adoc, [:config_name] do |_t, args|
    raise "No config named #{args[:config_name]}" unless File.directory?($root / "cfgs" / args[:config_name])

    Rake::Task["#{$root}/.stamps/adoc-gen-insts-#{args[:config_name]}.stamp"].invoke
    Rake::Task["#{$root}/.stamps/adoc-gen-csrs-#{args[:config_name]}.stamp"].invoke
    Rake::Task["#{$root}/.stamps/adoc-gen-exts-#{args[:config_name]}.stamp"].invoke
    Rake::Task["#{$root}/.stamps/adoc-gen-funcs-#{args[:config_name]}.stamp"].invoke
  end
end
