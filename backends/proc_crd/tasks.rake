# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a CRD.

require "pathname"

PROC_CRD_DOC_DIR = Pathname.new "#{$root}/backends/proc_crd"
PROC_CRD_GEN_DIR = $root / "gen" / "proc_crd"

Dir.glob("#{$root}/arch/proc_cert_model/*.yaml") do |f|
  model_name = File.basename(f, ".yaml")
  model_obj = YAML.load_file(f, permitted_classes: [Date])
  class_name = File.basename(model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed processor certificate model file #{f}: missing 'class' field" if model_obj['class'].nil?

  file "#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc" => [
    __FILE__,
    "#{$root}/arch/proc_cert_class/#{class_name}.yaml",
    "#{$root}/arch/proc_cert_model/#{model_name}.yaml",
    "#{$root}/lib/arch_obj_models/certificate.rb",
    "#{$root}/lib/arch_obj_models/portfolio.rb",
    "#{$root}/lib/portfolio_design.rb",
    "#{$root}/lib/idesign.rb",
    "#{$root}/backends/portfolio/templates/ext_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/inst_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/csr_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/beginning.adoc.erb",
    "#{$root}/backends/proc_cert/templates/typographic.adoc.erb",
    "#{$root}/backends/proc_cert/templates/rev_history.adoc.erb",
    "#{$root}/backends/proc_cert/templates/related_specs.adoc.erb",
    "#{$root}/backends/proc_cert/templates/priv_modes.adoc.erb",
    "#{$root}/backends/proc_cert/templates/rev_history.adoc.erb",
    "#{PROC_CRD_DOC_DIR}/templates/proc_crd.adoc.erb"
  ] do |t|
    proc_cert_create_adoc("#{PROC_CRD_DOC_DIR}/templates/proc_crd.adoc.erb", t.name, model_name)
  end

  file "#{PROC_CRD_GEN_DIR}/pdf/#{model_name}-CRD.pdf" => [
    __FILE__,
    "#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc"
  ] do |t|
    pf_adoc2pdf("#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc", t.name)
  end

  file "#{PROC_CRD_GEN_DIR}/html/#{model_name}-CRD.html" => [
    __FILE__,
    "#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc"
  ] do |t|
    pf_adoc2html("#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc", t.name)
  end
end

namespace :gen do
  desc <<~DESC
    Generate Processor CRD (Certification Requirements Document) as a PDF.

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

    Rake::Task["#{PROC_CRD_GEN_DIR}/pdf/#{model_name}-CRD.pdf"].invoke
  end

  desc <<~DESC
    Generate Processor CRD (Certification Requirements Document) as an HTML file.

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

    Rake::Task["#{PROC_CRD_GEN_DIR}/html/#{args[:model_name]}-CRD.html"].invoke
  end
end
