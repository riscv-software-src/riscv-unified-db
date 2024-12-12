# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

CERT_DOC_DIR = Pathname.new "#{$root}/backends/certificate_doc"

Dir.glob("#{$root}/arch/certificate_model/*.yaml") do |f|
  cert_model_name = File.basename(f, ".yaml")
  cert_model_obj = YAML.load_file(f, permitted_classes: [Date])
  cert_class_name = File.basename(cert_model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed certificate model file #{f}: missing 'class' field" if cert_model_obj['class'].nil?

  base = cert_model_obj["base"]
  raise "Missing certificate model base" if base.nil?

  file "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc" => [
    "#{$root}/arch/certificate_model/#{cert_model_name}.yaml",
    "#{$root}/arch/certificate_class/#{cert_class_name}.yaml",
    "#{CERT_DOC_DIR}/templates/certificate.adoc.erb",
    __FILE__
  ] do |t|
    # TODO: schema validation
    cfg_arch = cfg_arch_for("rv#{base}")
    cert_model = cfg_arch.cert_model(cert_model_name)
    raise "No certificate model defined for #{cert_model_name}" if cert_model.nil?

    # Switch to the generated certificate arch def
    # XXX - Add this to profile releases
    cfg_arch = cert_model.to_cfg_arch
    cert_model = cfg_arch.cert_model(cert_model_name)
    cert_class = cert_model.cert_class

    version = File.basename(t.name, '.adoc').split('-')[1..].join('-')

    erb = ERB.new(File.read("#{CERT_DOC_DIR}/templates/certificate.adoc.erb"), trim_mode: "-")
    erb.filename = "#{CERT_DOC_DIR}/templates/certificate.adoc.erb"

    FileUtils.mkdir_p File.dirname(t.name)
    File.write t.name, AsciidocUtils.resolve_links(cfg_arch.find_replace_links(erb.result(binding)))
    puts "Generated adoc source at #{t.name}"
  end

  file "#{$root}/gen/certificate_doc/pdf/#{cert_model_name}.pdf" => [
    "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
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

  file "#{$root}/gen/certificate_doc/html/#{cert_model_name}.html" => [
    "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
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
    Generate certificate documentation for a specific version as a PDF

    Required options:
      cert_model_name - The key of the certification model under arch/certificate_model
  DESC
  task :cert_model_pdf, [:cert_model_name] do |_t, args|
    if args[:cert_model_name].nil?
      warn "Missing required option: 'cert_model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/certificate_model/#{args[:cert_model_name]}.yaml")
      warn "No certification model named '#{args[:cert_model_name]}' found in arch/certificate_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/certificate_doc/pdf/#{args[:cert_model_name]}.pdf"].invoke
  end

  task :cert_model_html, [:cert_model_name] do |_t, args|
    if args[:cert_model_name].nil?
      warn "Missing required option: 'cert_model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/certificate_model/#{args[:cert_model_name]}.yaml")
      warn "No certification model named '#{args[:cert_model_name]}' found in arch/certificate_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/certificate_doc/html/#{args[:cert_model_name]}.html"].invoke
  end
end
