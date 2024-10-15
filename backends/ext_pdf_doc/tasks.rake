# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

EXT_PDF_DOC_DIR = Pathname.new "#{$root}/backends/ext_pdf_doc"

# Utilities for generating an Antora site out of an architecture def
module AsciidocUtils
  class << self
    def resolve_links(path_or_str)
      str =
        if path_or_str.is_a?(Pathname)
          path_or_str.read
        else
          path_or_str
        end
      str.gsub(/%%LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "inst"
          "xref:#inst-#{name.gsub('.', '_')}-def[#{link_text.gsub(']', '\]')}]"
        when "csr"
          "xref:#csr-#{name}-def[#{link_text.gsub(']', '\]')}]"
        when "csr_field"
          csr_name, field_name = name.split('.')
          # "xref:csrs:#{csr_name}.adoc##{csr_name}-#{field_name}-def[#{link_text.gsub(']', '\]')}]"
          link_text
        when "ext"
          # "xref:exts:#{name}.adoc##{name}-def[#{link_text.gsub(']', '\]')}]"
          link_text
        when "func"
          # "xref:funcs:funcs.adoc##{name}-func-def[#{link_text.gsub(']', '\]')}]"
          link_text
        else
          raise "Unhandled link type '#{type}' for '#{name}' #{match.captures}"
        end
      end
    end
  end
end

file "#{$root}/ext/docs-resources/themes/riscv-pdf.yml" => "#{$root}/.gitmodules" do |t|
  system "git submodule update --init ext/docs-resources"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/pdf/.*_extension\.pdf} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".pdf").to_s.split("_")[0..-2].join("_")
  [
    "#{$root}/ext/docs-resources/themes/riscv-pdf.yml",
    "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"
  ]
} do |t|
  ext_name = Pathname.new(t.name).basename(".pdf").to_s.split("_")[0..-2].join("_")
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  adoc_file = "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor-pdf",
    "-w",
    "-v",
    "-a toc",
    "-a compress",
    "-a pdf-theme=#{$root}/ext/docs-resources/themes/riscv-pdf.yml",
    "-a pdf-fontsdir=#{$root}/ext/docs-resources/fonts",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
    "-o #{t.name}",
    adoc_file
  ].join(" ")

  puts
  puts "Success!! File written to #{t.name}"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/html/.*_extension\.html} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".html").to_s.split("_")[0..-2].join("_")
  [
    "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"
  ]
} do |t|
  ext_name = Pathname.new(t.name).basename(".html").to_s.split("_")[0..-2].join("_")
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  adoc_file = "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-r asciidoctor-diagram",
    "-o #{t.name}",
    adoc_file
  ].join(" ")

  puts
  puts "Success!! File written to #{t.name}"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/adoc/.*_extension\.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".adoc").to_s.split("_")[0..-2].join("_")
  arch_yaml_paths =
    if File.exist?("#{$root}/arch/ext/#{ext_name}.yaml")
      ["#{$root}/arch/ext/#{ext_name}.yaml"] + Dir.glob("#{$root}/cfgs/*/arch_overlay/ext/#{ext_name}.yaml")
    else
      Dir.glob("#{$root}/cfgs/*/arch_overlay/ext/#{ext_name}.yaml")
    end
  raise "Can't find extension '#{ext_name}'" if arch_yaml_paths.empty?

  stamp = config_name == "_" ? "#{$root}/.stamps/arch-gen.stamp" : "#{$root}/.stamps/arch-gen-#{config_name}.stamp"

  [
    stamp,
    (EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb").to_s,
    arch_yaml_paths,
    __FILE__
  ].flatten
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]

  arch_def =
    if config_name == "_"
      arch_def_for("_64")
    else
      arch_def_for(config_name)
    end

  ext_name = Pathname.new(t.name).basename(".adoc").to_s.split("_")[0..-2].join("_")

  template_path = EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  ext = arch_def.extension(ext_name)
  version_num = ENV.key?("EXT_VERSION") ? ENV["EXT_VERSION"] : ext.versions.sort { |v| Gem::Version.new(v["version"]) }.last["version"]
  ext_version = ext.versions.find { |v| v["version"] == version_num }
  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AsciidocUtils.resolve_links(arch_def.find_replace_links(erb.result(binding)))
end

namespace :gen do
  desc <<~DESC
    Generate PDF documentation for :extension

    If the extension is custom (from an arch_overlay), also give the config name
  DESC
  task :ext_pdf, [:extension] do |_t, args|
    extension = args[:extension]

    Rake::Task[$root / "gen" / "ext_pdf_doc" / "_" / "pdf" / "#{extension}_extension.pdf"].invoke
  end

  desc <<~DESC
    Generate PDF documentation for :extension that is defined or overlayed in :cfg

    The latest version will be used, but can be overloaded by setting the EXT_VERSION environment variable.
  DESC
  task :cfg_ext_pdf, [:extension, :cfg] do |_t, args|
    raise ArgumentError, "Missing required argument :extension" if args[:extension].nil?
    raise ArgumentError, "Missing required argument :cfg" if args[:cfg].nil?

    extension = args[:extension]

    Rake::Task[$root / "gen" / "ext_pdf_doc" / args[:cfg] / "pdf" / "#{extension}_extension.pdf"].invoke(args)
  end

  desc <<~DESC
    Generate HTML documentation for :extension that is defined or overlayed in :cfg

    The latest version will be used, but can be overloaded by setting the EXT_VERSION environment variable.
  DESC
  task :cfg_ext_html, [:extension, :cfg] do |_t, args|
    raise ArgumentError, "Missing required argument :extension" if args[:extension].nil?
    raise ArgumentError, "Missing required argument :cfg" if args[:cfg].nil?

    extension = args[:extension]

    Rake::Task[$root / "gen" / "ext_pdf_doc" / args[:cfg] / "html" / "#{extension}_extension.html"].invoke(args)
  end
end
