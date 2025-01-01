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

  base_isa_name = "rv#{base}"

  puts "UPDATE: Extracted base=#{base} from #{f}"

  file "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc" => [
    __FILE__,
    "#{$root}/arch/certificate_class/#{cert_class_name}.yaml",
    "#{$root}/arch/certificate_model/#{cert_model_name}.yaml",
    "#{$root}/lib/arch_obj_models/certificate.rb",
    "#{$root}/lib/arch_obj_models/portfolio.rb",
    "#{$root}/lib/portfolio_design.rb",
    "#{$root}/lib/design.rb",
    "#{CERT_DOC_DIR}/templates/certificate.adoc.erb"
  ] do |t|
    # Create BaseArchitecture object. Function located in top-level Rakefile.
    puts "UPDATE: Creating BaseArchitecture #{base_isa_name} for #{t}"
    base_arch = base_arch_for(base_isa_name, base)

    # Create CertModel for specific certificate model as specified in its arch YAML file.
    # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
    # None of these objects are provided with a Design object when created.
    puts "UPDATE: Creating CertModel for #{cert_model_name} using base #{base_isa_name}"
    cert_model = base_arch.cert_model(cert_model_name)

    puts "UPDATE: Creating PortfolioDesign using CertModel #{cert_model_name}"
    # Create the one PortfolioDesign object required for the ERB evaluation.
    portfolio_design = portfolio_design_for(cert_model_name, base_arch, base, [cert_model])

    # Create empty binding and then specify explicitly which variables the ERB template can access.
    def create_empty_binding
      binding
    end
    erb_binding = create_empty_binding
    erb_binding.local_variable_set(:arch, base_arch)
    erb_binding.local_variable_set(:design, portfolio_design)
    erb_binding.local_variable_set(:cert_class, cert_model.cert_class)
    erb_binding.local_variable_set(:portfolio_class, cert_model.cert_class)
    erb_binding.local_variable_set(:cert_model, cert_model)
    erb_binding.local_variable_set(:portfolio, cert_model)

    template_path = Pathname.new("#{CERT_DOC_DIR}/templates/certificate.adoc.erb")
    erb = ERB.new(File.read(template_path), trim_mode: "-")
    erb.filename = template_path.to_s

    FileUtils.mkdir_p File.dirname(t.name)

    # Convert ERB to final ASCIIDOC. Note that this code is broken up into separate function calls
    # each with a variable name to aid in running a command-line debugger on this code.
    puts "UPDATE: Converting ERB template to adoc for #{cert_model_name}"
    erb_result = erb.result(erb_binding)
    erb_result_monospace_converted_to_links = portfolio_design.find_replace_links(erb_result)
    erb_result_with_links_added = portfolio_design.find_replace_links(erb_result_monospace_converted_to_links)
    erb_result_with_links_resolved = AsciidocUtils.resolve_links(erb_result_with_links_added)

    File.write(t.name, erb_result_with_links_resolved)
    puts "UPDATE: Generated adoc source at #{t.name}"
  end

  file "#{$root}/gen/certificate_doc/pdf/#{cert_model_name}.pdf" => [
    __FILE__,
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
    puts "UPDATE: Generated PDF at #{t.name}"
  end

  file "#{$root}/gen/certificate_doc/html/#{cert_model_name}.html" => [
    __FILE__,
    "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/certificate_doc/adoc/#{cert_model_name}.adoc"
    FileUtils.mkdir_p File.dirname(t.name)

    puts "UPDATE: Generating PDF at #{t.name}"
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
    puts "UPDATE: Generated PDF at #{t.name}"
  end
end

namespace :gen do
  desc <<~DESC
    Generate certificate documentation for a specific version as a PDF.

    Required options:
      cert_model_name - The key of the certification model under arch/certificate_model
  DESC
  task :cert_model_pdf, [:cert_model_name] do |_t, args|
    cert_model_name = args[:cert_model_name]
    if cert_model_name.nil?
      warn "Missing required option: 'cert_model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/certificate_model/#{cert_model_name}.yaml")
      warn "No certification model named '#{cert_model_name}' found in arch/certificate_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/certificate_doc/pdf/#{cert_model_name}.pdf"].invoke
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
