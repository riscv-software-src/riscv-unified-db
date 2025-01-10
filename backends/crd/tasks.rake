# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

puts "UPDATE: Inside crd tasks.rake"

CERT_DOC_DIR = Pathname.new "#{$root}/backends/crd"

Dir.glob("#{$root}/arch/proc_cert_model/*.yaml") do |f|
  proc_cert_model_name = File.basename(f, ".yaml")
  proc_cert_model_obj = YAML.load_file(f, permitted_classes: [Date])
  proc_cert_class_name = File.basename(proc_cert_model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed processor certificate model file #{f}: missing 'class' field" if proc_cert_model_obj['class'].nil?

  file "#{$root}/gen/crd/adoc/#{proc_cert_model_name}.adoc" => [
    __FILE__,
    "#{$root}/arch/proc_cert_class/#{proc_cert_class_name}.yaml",
    "#{$root}/arch/proc_cert_model/#{proc_cert_model_name}.yaml",
    "#{$root}/lib/arch_obj_models/certificate.rb",
    "#{$root}/lib/arch_obj_models/portfolio.rb",
    "#{$root}/lib/portfolio_design.rb",
    "#{$root}/lib/design.rb",
    "#{CERT_DOC_DIR}/templates/crd.adoc.erb"
  ] do |t|
    # Ensure that unconfigured resolved architecture called "_" exists.
    Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

    # Create architecture object so we can have it create the ProcCertModel.
    # Use the unconfigured resolved architecture called "_".
    arch = Architecture.new("RISC-V Architecture", $root / "gen" / "resolved_arch" / "_")

    # Create ProcCertModel for specific processor certificate model as specified in its arch YAML file.
    # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
    # None of these objects are provided with a Design object when created.
    puts "UPDATE: Creating ProcCertModel for #{proc_cert_model_name}"
    proc_cert_model = arch.proc_cert_model(proc_cert_model_name)

    puts "UPDATE: Creating PortfolioDesign using processor certificate model #{proc_cert_model_name}"
    # Create the one PortfolioDesign object required for the ERB evaluation.
    portfolio_design = PortfolioDesign.new(proc_cert_model_name, arch, [proc_cert_model])

    # Create empty binding and then specify explicitly which variables the ERB template can access.
    # Seems to use this method name in stack backtraces (hence its name).
    def evaluate_erb
      binding
    end
    erb_binding = evaluate_erb
    erb_binding.local_variable_set(:arch, arch)
    erb_binding.local_variable_set(:design, portfolio_design)
    erb_binding.local_variable_set(:proc_cert_class, proc_cert_model.proc_cert_class)
    erb_binding.local_variable_set(:portfolio_class, proc_cert_model.proc_cert_class)
    erb_binding.local_variable_set(:proc_cert_model, proc_cert_model)
    erb_binding.local_variable_set(:portfolio, proc_cert_model)

    template_path = Pathname.new("#{CERT_DOC_DIR}/templates/crd.adoc.erb")
    erb = ERB.new(File.read(template_path), trim_mode: "-")
    erb.filename = template_path.to_s

    FileUtils.mkdir_p File.dirname(t.name)

    # Convert ERB to final ASCIIDOC. Note that this code is broken up into separate function calls
    # each with a variable name to aid in running a command-line debugger on this code.
    puts "UPDATE: Converting ERB template to adoc for #{proc_cert_model_name}"
    erb_result = erb.result(erb_binding)
    erb_result_monospace_converted_to_links = portfolio_design.find_replace_links(erb_result)
    erb_result_with_links_added = portfolio_design.find_replace_links(erb_result_monospace_converted_to_links)
    erb_result_with_links_resolved = AsciidocUtils.resolve_links(erb_result_with_links_added)

    File.write(t.name, erb_result_with_links_resolved)
    puts "UPDATE: Generated adoc source at #{t.name}"
  end

  file "#{$root}/gen/crd/pdf/#{proc_cert_model_name}.pdf" => [
    __FILE__,
    "#{$root}/gen/crd/adoc/#{proc_cert_model_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/crd/adoc/#{proc_cert_model_name}.adoc"
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

  file "#{$root}/gen/crd/html/#{proc_cert_model_name}.html" => [
    __FILE__,
    "#{$root}/gen/crd/adoc/#{proc_cert_model_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/crd/adoc/#{proc_cert_model_name}.adoc"
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
      proc_cert_model_name - The key of the certification model under arch/proc_cert_model
  DESC
  task :proc_cert_model_pdf, [:proc_cert_model_name] do |_t, args|
    proc_cert_model_name = args[:proc_cert_model_name]
    if proc_cert_model_name.nil?
      warn "Missing required option: 'proc_cert_model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{proc_cert_model_name}.yaml")
      warn "No certification model named '#{proc_cert_model_name}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/crd/pdf/#{proc_cert_model_name}.pdf"].invoke
  end

  task :proc_cert_model_html, [:proc_cert_model_name] do |_t, args|
    if args[:proc_cert_model_name].nil?
      warn "Missing required option: 'proc_cert_model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{args[:proc_cert_model_name]}.yaml")
      warn "No certification model named '#{args[:proc_cert_model_name]}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/crd/html/#{args[:proc_cert_model_name]}.html"].invoke
  end
end
