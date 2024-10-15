# frozen_string_literal: true

require "ruby-prof"

# fill out templates for every csr, inst, ext, and func
["csr", "inst", "ext", "func"].each do |type|
  rule %r{#{$root}/\.stamps/adoc-gen-#{type}s-.*\.stamp} => proc { |tname|
    config_name = Pathname.new(tname).basename(".stamp").sub("adoc-gen-#{type}s-", "")
    [
      "#{$root}/.stamps/arch-gen-#{config_name}.stamp",
      "#{CFG_HTML_DOC_DIR}/templates/#{type}.adoc.erb",
      "#{$root}/lib/arch_def.rb",
      "#{$root}/lib/idl/passes/gen_adoc.rb",
      __FILE__,
      "#{$root}/.stamps"
    ]
  } do |t|
    config_name = Pathname.new(t.name).basename(".stamp").sub("adoc-gen-#{type}s-", "")

    arch_def = arch_def_for(config_name)
    adoc_template_path = CFG_HTML_DOC_DIR / "templates" / "#{type}.adoc.erb"
    adoc_template = adoc_template_path.read
    erb = ERB.new(adoc_template, trim_mode: "-")
    erb.filename = adoc_template_path.to_s

    dir_path = $root / "gen" / "cfg_html_doc" / config_name / "adoc" / "#{type}s"
    FileUtils.mkdir_p dir_path

    case type
    when "csr"
      arch_def.implemented_csrs.each do |csr|
        path = dir_path / "#{csr.name}.adoc"
        puts "  Generating #{path}"
        File.write(path, arch_def.find_replace_links(erb.result(binding)))
      end
    when "inst"
      arch_def.implemented_instructions.each do |inst|
        path = dir_path / "#{inst.name}.adoc"
        puts "  Generating #{path}"
        # RubyProf.start
        File.write(path, arch_def.find_replace_links(erb.result(binding)))
        # result = RubyProf.stop
        # RubyProf::FlatPrinter.new(result).print(STDOUT)
      end
    when "ext"
      arch_def.implemented_extensions.each do |ext_version|
        ext = arch_def.extension(ext_version.name)
        path = dir_path / "#{ext.name}.adoc"
        puts "  Generating #{path}"
        File.write(path, arch_def.find_replace_links(erb.result(binding)))
      end
    when "func"
      global_symtab = arch_def.symtab
      path = dir_path / "funcs.adoc"
      puts "  Generating #{path}"
      File.write(path, arch_def.find_replace_links(erb.result(binding)))
    else
      raise "todo"
    end

    FileUtils.touch(t.name)
  end

  rule %r{#{$root}/gen/cfg_html_doc/.*/adoc/#{type}s/all_#{type}s.adoc} => proc { |tname|
    config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
    ["#{$root}/.stamps/adoc-gen-#{type}s-#{config_name}.stamp"]
  } do |t|
    to_long = {
      "csr" => "CSRs",
      "inst" => "Instructions",
      "ext" => "Extensions",
      "func" => "Functions"
    }

    config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

    arch_def = arch_def_for(config_name)

    lines = [
      "= Implemented #{to_long[type]}",
      "",
      "The following are implemented by the #{arch_def.name} configuration:",
      ""
    ]

    case type
    when "csr"
      puts "Generting full CSR list"
      arch_def.implemented_csrs.each do |csr|
        lines << " * `#{csr.name}` #{csr.long_name}"
      end
    when "ext"
      puts "Generting full extension list"
      arch_def.implemented_extensions.each do |ext_version|
        lines << " * `#{ext_version.name}` #{ext_version.ext(arch_def).long_name}"
      end
    when "inst"
      puts "Generting full instruction list"
      arch_def.implemented_instructions.each do |inst|
        lines << " * `#{inst.name}` #{inst.long_name}"
      end
    when "func"
      puts "Generting function list"
      arch_def.implemented_functions.each do |func|
        lines << " * `#{func.name}`"
      end
    else
      raise "Unsupported type"
    end

    File.write t.name, arch_def.find_replace_links(lines.join("\n"))
  end
end

rule %r{#{$root}/gen/cfg_html_doc/.*/adoc/ROOT/landing.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]
  [
    "#{$root}/\.stamps/arch-gen-#{config_name}\.stamp",
    "#{CFG_HTML_DOC_DIR}/templates/landing.adoc.erb",
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

  arch_def = arch_def_for(config_name)

  puts "Generating landing page for #{config_name}"
  erb = ERB.new(File.read("#{CFG_HTML_DOC_DIR}/templates/landing.adoc.erb"), trim_mode: "-")

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end


namespace :gen do
  desc "Generate Asciidoc source for config into gen/CONFIG_NAME/adoc"
  task :adoc, [:config_name] do |_t, args|
    raise "No config named #{args[:config_name]}" unless File.directory?($root / "cfgs" / args[:config_name])

    ["inst", "csr", "ext", "func"].each do |type|
      Rake::Task["#{$root}/.stamps/adoc-gen-#{type}s-#{args[:config_name]}.stamp"].invoke
      Rake::Task["#{$root}/gen/cfg_html_doc/#{args[:config_name]}/adoc/#{type}s/all_#{type}s.adoc"].invoke
    end

    Rake::Task["#{$root}/gen/cfg_html_doc/#{args[:config_name]}/adoc/ROOT/landing.adoc"].invoke
  end
end
