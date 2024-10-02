# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

CSC_CRD_DOC_DIR = Pathname.new "#{$root}/backends/csc_crd_doc"

Dir.glob("#{$root}/arch/csc_crd/*.yaml") do |f|
  crd_name = File.basename(f, ".yaml")
  crd_obj = YAML.load_file(f, permitted_classes: [Date])
  raise "Ill-formed CSC CRD file #{f}: missing 'family' field" if crd_obj.dig(crd_name, 'family').nil?
  
  file "#{$root}/gen/csc_crd_doc/adoc/#{crd_name}.adoc" => [
    "#{$root}/arch/csc_crd/#{crd_name}.yaml",
    "#{$root}/arch/csc_crd_family/#{crd_obj[crd_name]['family']}.yaml",
    "#{CSC_CRD_DOC_DIR}/templates/crd.adoc.erb",
    __FILE__,
    "gen:arch"
  ] do |t|
    # TODO: schema validation
    arch_def = arch_def_for("_")
    crd = arch_def.csc_crd(crd_name)
    raise "No CSC CRD defined for #{crd_name}" if crd.nil?

    version = File.basename(t.name, '.adoc').split('-')[1..].join('-')

    erb = ERB.new(File.read("#{CSC_CRD_DOC_DIR}/templates/crd.adoc.erb"), trim_mode: "-")
    erb.filename = "#{CSC_CRD_DOC_DIR}/templates/crd.adoc.erb"
    
    FileUtils.mkdir_p File.dirname(t.name)
    File.write t.name, AsciidocUtils.resolve_links(arch_def.find_replace_links(erb.result(binding)))
    puts "Generated adoc source at #{t.name}"
  end

  file "#{$root}/gen/csc_crd_doc/pdf/#{crd_name}.pdf" => [
    "#{$root}/gen/csc_crd_doc/adoc/#{crd_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/csc_crd_doc/adoc/#{crd_name}.adoc"
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
  end

  file "#{$root}/gen/csc_crd_doc/html/#{crd_name}.html" => [
    "#{$root}/gen/csc_crd_doc/adoc/#{crd_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/csc_crd_doc/adoc/#{crd_name}.adoc"
    FileUtils.mkdir_p File.dirname(t.name)
    sh [
      "asciidoctor",
      "-w",
      "-v",
      "-a toc",
      "-a imagesdir=#{$root}/ext/docs-resources/images",
      "-b html5",
      "-r asciidoctor-diagram",
      "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
      "-o #{t.name}",
      adoc_file
    ].join(" ")
  end

end

namespace :gen do
  desc <<~DESC
    Generate CSC CRD documentation for a specific version as a PDF

    Required options:
      crd_name - The key of the CSC CRD Family under arch/csc_crd
  DESC
  task :csc_crd_pdf, [:crd_name] do |_t, args|
    if args[:crd_name].nil?
      warn "Missing required option: 'crd_family_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/csc_crd/#{args[:crd_name]}.yaml")
      warn "No CRD named '#{args[:crd_name]}' found in arch/csc_crd"
      exit 1
    end

    Rake::Task["#{$root}/gen/csc_crd_doc/pdf/#{args[:crd_name]}.pdf"].invoke
  end

  task :csc_crd_html, [:crd_name] do |_t, args|
    if args[:crd_name].nil?
      warn "Missing required option: 'crd_family_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/csc_crd/#{args[:crd_name]}.yaml")
      warn "No CRD named '#{args[:crd_name]}' found in arch/csc_crd"
      exit 1
    end

    Rake::Task["#{$root}/gen/csc_crd_doc/html/#{args[:crd_name]}.html"].invoke
  end
end