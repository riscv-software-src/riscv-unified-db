# typed: false
# frozen_string_literal: true

require "udb_helpers/backend_helpers"
require "ruby-prof"

# fill out templates for every csr, inst, ext, and func
["csr", "inst", "ext", "func"].each do |type|
  rule %r{#{$root}/\.stamps/adoc-gen-#{type}s-.*\.stamp} => proc { |tname|
    [
      "#{CFG_HTML_DOC_DIR}/templates/#{type}.adoc.erb",
      __FILE__,
      "#{$root}/.stamps"
    ]
  } do |t|
    config_name = Pathname.new(t.name).basename(".stamp").sub("adoc-gen-#{type}s-", "")

    cfg_arch = $resolver.cfg_arch_for(config_name.to_s)
    adoc_template_path = CFG_HTML_DOC_DIR / "templates" / "#{type}.adoc.erb"
    adoc_template = adoc_template_path.read
    erb = ERB.new(adoc_template, trim_mode: "-")
    erb.filename = adoc_template_path.to_s

    dir_path = $root / "gen" / "cfg_html_doc" / config_name / "adoc" / "#{type}s"
    FileUtils.mkdir_p dir_path

    case type
    when "csr"
      cfg_arch.transitive_implemented_csrs.each do |csr|
        path = dir_path / "#{csr.name}.adoc"
        Udb.logger.info "  Generating #{path}"
        File.write(path, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding))))
      end
    when "inst"
      cfg_arch.transitive_implemented_instructions.each do |inst|
        path = dir_path / "#{inst.name}.adoc"
        Udb.logger.info "  Generating #{path}"
        # RubyProf.start
        File.write(path, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding))))
        # result = RubyProf.stop
        # RubyProf::FlatPrinter.new(result).print(STDOUT)
      end
    when "ext"
      cfg_arch.transitive_implemented_extension_versions.each do |ext_version|
        ext = cfg_arch.extension(ext_version.name)
        path = dir_path / "#{ext.name}.adoc"
        Udb.logger.info "  Generating #{path}"
        File.write(path, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding))))
      end
    when "func"
      global_symtab = cfg_arch.symtab
      path = dir_path / "funcs.adoc"
      Udb.logger.info "  Generating #{path}"
      File.write(path, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding))))
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

    cfg_arch = $resolver.cfg_arch_for(config_name.to_s)

    lines = [
      "= Implemented #{to_long[type]}",
      "",
      "The following are implemented by the #{cfg_arch.name} configuration:",
      ""
    ]

    case type
    when "csr"
      Udb.logger.info "Generating full CSR list"
      cfg_arch.transitive_implemented_csrs.each do |csr|
        lines << " * `#{csr.name}` #{csr.long_name}"
      end
    when "ext"
      Udb.logger.info "Generating full extension list"
      cfg_arch.transitive_implemented_extension_versions.each do |ext_version|
        lines << " * `#{ext_version.name}` #{ext_version.ext.long_name}"
      end
    when "inst"
      Udb.logger.info "Generating full instruction list"
      cfg_arch.transitive_implemented_instructions.each do |inst|
        lines << " * `#{inst.name}` #{inst.long_name}"
      end
    when "func"
      Udb.logger.info "Generating function list"
      cfg_arch.implemented_functions.each do |func|
        lines << " * `#{func.name}`"
      end
    else
      raise "Unsupported type"
    end

    FileUtils.mkdir_p File.dirname(t.name)
    File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(lines.join("\n")))
  end
end

rule %r{#{$root}/gen/cfg_html_doc/.*/adoc/ROOT/landing.adoc} => [
  "#{CFG_HTML_DOC_DIR}/templates/landing.adoc.erb",
  __FILE__
] do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/cfg_html_doc").to_s.split("/")[0]

  cfg_arch = $resolver.cfg_arch_for(config_name.to_s)

  Udb.logger.info "Generating landing page for #{config_name}"
  erb = ERB.new(File.read("#{CFG_HTML_DOC_DIR}/templates/landing.adoc.erb"), trim_mode: "-")

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

namespace :gen do
  desc "Generate Asciidoc source for config into gen/CONFIG_NAME/adoc"
  task :adoc, [:config_name] do |_t, args|
    raise "No config named #{args[:config_name]}" unless File.file?($root / "cfgs" / "#{args[:config_name]}.yaml")

    ["inst", "csr", "ext", "func"].each do |type|
      Rake::Task["#{$root}/.stamps/adoc-gen-#{type}s-#{args[:config_name]}.stamp"].invoke
      Rake::Task["#{$root}/gen/cfg_html_doc/#{args[:config_name]}/adoc/#{type}s/all_#{type}s.adoc"].invoke
    end

    Rake::Task["#{$root}/gen/cfg_html_doc/#{args[:config_name]}/adoc/ROOT/landing.adoc"].invoke
  end
end
