# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a CRD.

require "pathname"

CERT_DOC_DIR = Pathname.new "#{$root}/backends/crd"

Dir.glob("#{$root}/arch/proc_cert_model/*.yaml") do |f|
  model_name = File.basename(f, ".yaml")
  model_obj = YAML.load_file(f, permitted_classes: [Date])
  class_name = File.basename(model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed processor certificate model file #{f}: missing 'class' field" if model_obj['class'].nil?

  file "#{$root}/gen/crd/adoc/#{model_name}.adoc" => [
    __FILE__,
    "#{$root}/arch/proc_cert_class/#{class_name}.yaml",
    "#{$root}/arch/proc_cert_model/#{model_name}.yaml",
    "#{$root}/lib/arch_obj_models/certificate.rb",
    "#{$root}/lib/arch_obj_models/portfolio.rb",
    "#{$root}/lib/portfolio_design.rb",
    "#{$root}/lib/design.rb",
    "#{$root}/backends/portfolio/templates/ext_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/inst_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/csr_appendix.adoc.erb",
    "#{CERT_DOC_DIR}/templates/crd.adoc.erb"
  ] do |t|
    arch = pf_create_arch

    # Create ProcCertModel for specific processor certificate model as specified in its arch YAML file.
    # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
    # None of these objects are provided with a Design object when created.
    puts "UPDATE: Creating ProcCertModel for #{model_name}"
    proc_cert_model = arch.proc_cert_model(model_name)
    proc_cert_class = proc_cert_model.proc_cert_class

    # Create the one PortfolioDesign object required for the ERB evaluation.
    puts "UPDATE: Creating PortfolioDesign using processor certificate model #{model_name}"
    portfolio_design = PortfolioDesign.new(model_name, arch, [proc_cert_model], proc_cert_class)

    # Create empty binding and then specify explicitly which variables the ERB template can access.
    # Seems to use this method name in stack backtraces (hence its name).
    def evaluate_erb
      binding
    end
    erb_binding = evaluate_erb
    portfolio_design.init_erb_binding(erb_binding)
    erb_binding.local_variable_set(:proc_cert_model, proc_cert_model)
    erb_binding.local_variable_set(:proc_cert_class, proc_cert_class)

    pf_create_adoc("#{CERT_DOC_DIR}/templates/crd.adoc.erb", erb_binding, t.name, portfolio_design)
  end

  file "#{$root}/gen/crd/pdf/#{model_name}.pdf" => [
    __FILE__,
    "#{$root}/gen/crd/adoc/#{model_name}.adoc"
  ] do |t|
    pf_adoc2pdf("#{$root}/gen/crd/adoc/#{model_name}.adoc", t.name)
  end

  file "#{$root}/gen/crd/html/#{model_name}.html" => [
    __FILE__,
    "#{$root}/gen/crd/adoc/#{model_name}.adoc"
  ] do |t|
    pf_adoc2html("#{$root}/gen/crd/adoc/#{model_name}.adoc", t.name)
  end
end

namespace :gen do
  desc <<~DESC
    Generate CRD (Certification Requirements Document) as a PDF.

    Required options:
      model_name - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_crd_pdf, [:model_name] do |_t, args|
    model_name = args[:model_name]
    if model_name.nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{model_name}.yaml")
      warn "No certification model named '#{model_name}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/crd/pdf/#{model_name}.pdf"].invoke
  end

  desc <<~DESC
    Generate CRD (Certification Requirements Document) as an HTML file.

    Required options:
      model_name - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_crd_html, [:model_name] do |_t, args|
    if args[:model_name].nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{args[:model_name]}.yaml")
      warn "No certification model named '#{args[:model_name]}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{$root}/gen/crd/html/#{args[:model_name]}.html"].invoke
  end
end
