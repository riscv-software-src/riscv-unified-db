# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

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
          "xref:insns-#{name.gsub(',', '_')}[#{link_text.gsub(']', '\]')}]"
        when "csr"
          # "xref:csrs:#{name}.adoc##{name}-def[#{link_text.gsub(']', '\]')}]"
          link_text
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

rule %r{#{$root}/gen/ext_pdf_doc/.*/pdf/.*_extension\.pdf} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from($root / "gen" / "ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".pdf").to_s.split("_")[0..-2].join("_")
  [
    "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from($root / "gen" / "ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(t.name).basename(".pdf").to_s.split("_")[0..-2].join("_")
  adoc_file = "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Asciidoctor.convert_file(adoc_file, backend: "pdf", safe: :safe)
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/adoc/.*_extension\.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from($root / "gen" / "ext_pdf_doc").to_s.split("/")[0]
  [
    "#{$root}/.stamps/arch-gen-#{config_name}.stamp",
    (EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb").to_s,
    __FILE__
  ]
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(t.name).basename(".pdf").to_s.split("_")[0..-2].join("_")

  template_path = EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  arch_def = ArchDef.new(config_name)
  ext = arch_def.extension(ext_name)
  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AsciidocUtils.resolve_links(arch_def.find_replace_links(erb.result(binding)))
end


namespace :gen do
  desc <<~DESC
    Generate PDF documentation for :extension using configuration :config_name
  DESC
  task :ext_pdf, [:extension, :config_name] do |_t, args|
    config = args[:config_name]
    extension = args[:extension]

    Rake::Task[$root / "gen" / "ext_pdf_doc" / config.to_s / "pdf" / "#{extension}_extension.pdf"].invoke
  end
end
