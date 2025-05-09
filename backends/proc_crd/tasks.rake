# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a CRD.

require "pathname"

PROC_CRD_DOC_DIR = Pathname.new "#{$root}/backends/proc_crd"
PROC_CRD_GEN_DIR = $root / "gen" / "proc_crd"

rule %r{#{PROC_CRD_GEN_DIR}/adoc/[^/]+-CRD.adoc} => [
  __FILE__,
  "#{$root}/lib/arch_obj_models/certificate.rb",
  "#{$root}/lib/arch_obj_models/portfolio.rb",
  "#{$root}/lib/portfolio_design.rb",
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
  model_name = File.basename(t.name, ".adoc")[0...-4]
  proc_cert_create_adoc("#{PROC_CRD_DOC_DIR}/templates/proc_crd.adoc.erb", t.name, model_name, ENV["CONFIG"])
end

rule %r{#{PROC_CRD_GEN_DIR}/pdf/[^/]+-CRD.pdf} => proc { |tname|
  model_name = File.basename(tname, ".pdf")[0...-4]
  [
    __FILE__,
    "#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc"
  ]
} do |t|
  model_name = File.basename(t.name, ".pdf")[0...-4]
  pf_adoc2pdf("#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc", t.name)
end

rule %r{#{PROC_CRD_GEN_DIR}/html/[^/]+-CRD.html"} => proc { |tname|
  model_name = File.basename(tname, ".html")[0...-4]
  [
    __FILE__,
    "#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc"
  ]
} do |t|
  model_name = File.basename(t.name, ".html")[0...-4]
  pf_adoc2html("#{PROC_CRD_GEN_DIR}/adoc/#{model_name}-CRD.adoc", t.name)
end

namespace :gen do
  desc <<~DESC
    Generate Processor CRD (Certification Requirements Document) as a PDF.

    Required options:
      CONFIG       - Configuration to use for base architecture
      MODE         - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_crd_pdf do
    raise "Missing required argument 'CONFIG'" unless ENV.key?("CONFIG")
    raise "Missing required argument 'MODEL'" unless ENV.key?("MODEL")

    model_name = ENV["MODEL"]
    if model_name.nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    cfg_arch = cfg_arch_for(ENV["CONFIG"])

    unless cfg_arch.proc_cert_models.any? { |model| model.name == model_name }
      warn "No certification model named '#{model_name}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CRD_GEN_DIR}/pdf/#{model_name}-CRD.pdf"].invoke
  end

  desc <<~DESC
    Generate Processor CRD (Certification Requirements Document) as an HTML file.

    Required options:
      CONFIG       - Configuration to use for base architecture
      MODE         - The name of the certification model under arch/proc_cert_model
  DESC
  task :proc_crd_html do
    raise "Missing required argument 'CONFIG'" unless ENV.key?("CONFIG")
    raise "Missing required argument 'MODEL'" unless ENV.key?("MODEL")

    model_name = ENV["MODEL"]
    if model_name.nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    cfg_arch = cfg_arch_for(ENV["CONFIG"])

    unless cfg_arch.proc_cert_models.any? { |model| model.name == model_name }
      warn "No certification model named '#{model_name}' found in arch/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CRD_GEN_DIR}/html/#{model_name}-CRD.html"].invoke
  end
end
