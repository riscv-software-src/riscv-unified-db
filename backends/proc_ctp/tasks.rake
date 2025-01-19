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

  file "#{$root}/gen/proc_ctp/adoc/#{model_name}-CTP.adoc" => [
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
    "#{$root}/backends/portfolio/templates/beginning.adoc.erb",
    "#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb",
    "#{PROC_CTP_GEN_DIR}/adoc/ext/riscv-isa-manual/README.md",
    "#{PROC_CTP_GEN_DIR}/adoc/ext/riscv-isa-manual/docs-resources/README.md"
  ] do |t|
    proc_cert_create_adoc("#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb", t.name, model_name)
  end

  file "#{$root}/gen/proc_ctp/pdf/#{model_name}-CTP.pdf" => [
    __FILE__,
    "#{$root}/gen/proc_ctp/adoc/#{model_name}-CTP.adoc"
  ] do |t|
    pf_adoc2pdf("#{$root}/gen/proc_ctp/adoc/#{model_name}-CTP.adoc", t.name)
  end

  file "#{$root}/gen/proc_ctp/html/#{model_name}-CTP.html" => [
    __FILE__,
    "#{$root}/gen/proc_ctp/adoc/#{model_name}-CTP.adoc"
  ] do |t|
    pf_adoc2html("#{$root}/gen/proc_ctp/adoc/#{model_name}-CTP.adoc", t.name)
  end
end

# Ensure that the riscv-isa-manual submodule repository is up-to-date.
file $root / "ext" / "csc-riscv-isa-manual" / "README.md" do
  sh "git submodule update --init ext/csc-riscv-isa-manual 2>&1"
end

# Ensure that the docs-resources submodule repository is up-to-date.
file $root / "ext" / "docs-resources" / "README.md" do
  sh "git submodule update --init ext/docs-resources 2>&1"
end

# Rule to copy the riscv-isa-manual submodule repository to the gen directory.
rule %r{#{PROC_CTP_GEN_DIR}/adoc/ext/riscv-isa-manual/README.md} => [
  "#{$root}/ext/csc-riscv-isa-manual/README.md"
] do |t|
  # Pull in the latest version of the csc-riscv-isa-manual.
  sh "cd ext/csc-riscv-isa-manual; git fetch; git merge origin/main 2>&1"

  # Use git archive to extract the latest version of the csc-riscv-isa-manual.
  FileUtils.mkdir_p File.dirname(t.name)
  Dir.chdir($root / "ext" / "csc-riscv-isa-manual") do
    sh "git archive --format=tar HEAD | tar xvf - -C #{File.dirname(t.name)}"
  end
end

# Rule to copy the docs-resources submodule repository to the gen directory.
# Make the rule dependent on the riscv-isa-manual to ensure that gets copied
# to the gen directory first (because it has an empty docs-resources directory).
rule %r{#{PROC_CTP_GEN_DIR}/adoc/ext/riscv-isa-manual/docs-resources/README.md} => [
  "#{$root}/ext/docs-resources/README.md",
  "#{$root}/ext/csc-riscv-isa-manual/README.md",
] do |t|
  # Pull in the latest version of the docs-resources.
  sh "cd ext/docs-resources; git fetch; git merge origin/main 2>&1"

  # Use git archive to extract the latest version of the docs-resources.
  FileUtils.mkdir_p File.dirname(t.name)
  Dir.chdir($root / "ext" / "docs-resources") do
    sh "git archive --format=tar HEAD | tar xvf - -C #{File.dirname(t.name)}"
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

    Rake::Task["#{$root}/gen/proc_ctp/pdf/#{model_name}-CTP.pdf"].invoke
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

    Rake::Task["#{$root}/gen/proc_ctp/html/#{args[:model_name]}-CTP.html"].invoke
  end
end
