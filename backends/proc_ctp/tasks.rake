# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a CTP (Certification Test Plan).

require "pathname"

PROC_CTP_DOC_DIR = Pathname.new "#{$root}/backends/proc_ctp"
PROC_CTP_GEN_DIR = $root / "gen" / "proc_ctp"

Dir.glob("#{$root}/arch/proc_cert_model/*.yaml") do |f|
  model_name = File.basename(f, ".yaml")
  model_obj = YAML.load_file(f, permitted_classes: [Date])
  class_name = File.basename(model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed processor certificate model file #{f}: missing 'class' field" if model_obj['class'].nil?

  file "#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc" => [
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
    "#{$root}/backends/portfolio/templates/normative_rules.adoc.erb",
    "#{$root}/backends/portfolio/templates/test_procedures.adoc.erb",
    "#{$root}/backends/proc_cert/templates/typographic.adoc.erb",
    "#{$root}/backends/proc_cert/templates/rev_history.adoc.erb",
    "#{$root}/backends/proc_cert/templates/related_specs.adoc.erb",
    "#{$root}/backends/proc_cert/templates/priv_modes.adoc.erb",
    "#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb"
  ] do |t|
    pf_get_latest_csc_isa_manual(t.name)
    proc_cert_create_adoc("#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb", t.name, model_name)
  end

  file "#{PROC_CTP_GEN_DIR}/pdf/#{model_name}-CTP.pdf" => [
    __FILE__,
    "#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc"
  ] do |t|
    pf_adoc2pdf("#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc", t.name)
  end

  file "#{PROC_CTP_GEN_DIR}/html/#{model_name}-CTP.html" => [
    __FILE__,
    "#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc"
  ] do |t|
    pf_adoc2html("#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc", t.name)
  end
end

namespace :gen do
  desc <<~DESC
    Generate Processor CTP (Certification Test Plan) as a PDF.

    Required options:
      model_name - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_ctp_pdf, [:model_name] do |_t, args|
    model_name = args[:model_name]
    if model_name.nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{model_name}.yaml")
      warn "No certification model named '#{model_name}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CTP_GEN_DIR}/pdf/#{model_name}-CTP.pdf"].invoke
  end

  desc <<~DESC
    Generate Processor CTP (Certification Test Plan) as an HTML file.

    Required options:
      model_name - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_ctp_html, [:model_name] do |_t, args|
    if args[:model_name].nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/proc_cert_model/#{args[:model_name]}.yaml")
      warn "No certification model named '#{args[:model_name]}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CTP_GEN_DIR}/html/#{args[:model_name]}-CTP.html"].invoke
  end
end
