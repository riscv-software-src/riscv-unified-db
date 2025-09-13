# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a CTP (Certification Test Plan).

require "pathname"
require "json"

PROC_CTP_DOC_DIR = Pathname.new "#{$root}/backends/proc_ctp"
PROC_CTP_GEN_DIR = $resolver.gen_path / "proc_ctp"

Dir.glob("#{$resolver.std_path}/proc_cert_model/*.yaml") do |f|
  model_name = File.basename(f, ".yaml")
  model_obj = YAML.load_file(f, permitted_classes: [Date])
  class_name = File.basename(model_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed processor certificate model file #{f}: missing 'class' field" if model_obj['class'].nil?

  file "#{PROC_CTP_GEN_DIR}/adoc/#{model_name}-CTP.adoc" => [
    __FILE__,
    "#{$resolver.std_path}/proc_cert_class/#{class_name}.yaml",
    "#{$resolver.std_path}/proc_cert_model/#{model_name}.yaml",
    "#{Udb.gem_path}/lib/udb/obj/certificate.rb",
    "#{Udb.gem_path}/lib/udb/obj/portfolio.rb",
    "#{Udb.gem_path}/lib/udb/portfolio_design.rb",
    "#{$root}/backends/portfolio/templates/ext_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/inst_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/csr_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/beginning.adoc.erb",
    "#{$root}/backends/portfolio/templates/normative_rules.adoc.erb",
    "#{$root}/backends/proc_cert/templates/typographic.adoc.erb",
    "#{$root}/backends/proc_cert/templates/rev_history.adoc.erb",
    "#{$root}/backends/proc_cert/templates/related_specs.adoc.erb",
    "#{$root}/backends/proc_cert/templates/priv_modes.adoc.erb",
    "#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb"
  ] do |t|
    begin
      pf_get_latest_csc_isa_manual(t.name)

      # Figure out some pathnames/filenames.
      norm_tags_json_suffix = "-norm-tags.json"
      isa_manual_dir = "#{PROC_CTP_GEN_DIR}/adoc/ext/riscv-isa-manual"
      unpriv_adoc = "#{isa_manual_dir}/src/riscv-unprivileged.adoc"
      priv_adoc = "#{isa_manual_dir}/src/riscv-privileged.adoc"
      unpriv_tags_json = "#{PROC_CTP_GEN_DIR}/adoc/riscv-unprivileged#{norm_tags_json_suffix}"
      priv_tags_json = "#{PROC_CTP_GEN_DIR}/adoc/riscv-privileged#{norm_tags_json_suffix}"
      norm_rules_json = "#{PROC_CTP_GEN_DIR}/adoc/norm-rules.json"

      # Extract normative rule tags from ISA manuals into JSON files.
      pf_adoc2norm_tags(unpriv_adoc, unpriv_tags_json, isa_manual_dir, norm_tags_json_suffix)
      pf_adoc2norm_tags(priv_adoc, priv_tags_json, isa_manual_dir, norm_tags_json_suffix)

      # Create normative rules using ISA manual repository.
      pf_build_norm_rules(isa_manual_dir, unpriv_tags_json, priv_tags_json, norm_rules_json)

      # Read in normative rule JSON file to Ruby object.
      data = JSON.parse(File.read(norm_rules_json))

      # Load normative rules into a Ruby class to provide access to rules when generating CTP.
      normative_rules = Udb::NormativeRules.new(data)

      proc_cert_create_adoc("#{PROC_CTP_DOC_DIR}/templates/proc_ctp.adoc.erb", t.name, model_name, normative_rules)
    rescue => e
      # Send to stdout since UDB sends tons of cr*p to stderr that floods one with useless information.
      # Note that the $logger sends to stdout so anything send to $logger actually gets displayed as useful
      # information if one just redirects stderr to /dev/null (e.g., in bash, run "./do <task-name> 2>/dev/null).
      puts "Caught error: #{e.message}"

      # Only print out 1st two lines of stack backtrace to stdout.
      puts e.backtrace.take(2)

      # Send full stacktrace to stderr with "warn".
      warn e.backtrace
    end
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

    unless File.exist?("#{$resolver.std_path}/proc_cert_model/#{model_name}.yaml")
      warn "No certification model named '#{model_name}' found in #{$resolver.std_path}/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CTP_GEN_DIR}/pdf/#{model_name}-CTP.pdf"].invoke
  end

  desc <<~DESC
    Generate Processor CTP (Certification Test Plan) as an HTML file.

    Required options:
      model_name - The name of the certification model under spec/std/isa/proc_cert_model
  DESC
  task :proc_ctp_html, [:model_name] do |_t, args|
    if args[:model_name].nil?
      warn "Missing required option: 'model_name'"
      exit 1
    end

    unless File.exist?("#{$resolver.std_path}/proc_cert_model/#{args[:model_name]}.yaml")
      warn "No certification model named '#{args[:model_name]}' found in #{$resolver.std_path}/proc_cert_model"
      exit 1
    end

    Rake::Task["#{PROC_CTP_GEN_DIR}/html/#{args[:model_name]}-CTP.html"].invoke
  end
end
