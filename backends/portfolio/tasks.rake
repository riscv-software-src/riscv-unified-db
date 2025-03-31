# frozen_string_literal: true
#
# Contains common methods called from portfolio-based tasks.rake files.

require "pathname"
require "asciidoctor-pdf"
require "asciidoctor-diagram"
require_relative "#{$lib}/idl/passes/gen_adoc"

# @return [ConfiguredArchitecture]
def pf_create_arch
  # Ensure that unconfigured resolved architecture called "_" exists.
  Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

  # Create architecture object so we can have it create the ProcCertModel.
  # Use the unconfigured resolved architecture called "_".
  cfg_arch_for("_")
end

# Clones the CSC fork of the ISA manual repository or updates it if it already exists.
# Does the same for the docs-resources repository which is used by the ISA manual.
#
# @param target_pname [String] Full pathname of target file being generated
def pf_get_latest_csc_isa_manual(target_pname)
  # Directory path for target file.
  target_dir = File.dirname(target_pname)

  pf_ensure_repository("https://github.com/RISC-V-Certification-Steering-Committee/riscv-isa-manual",
    target_dir + "/ext/riscv-isa-manual")

  pf_ensure_repository("https://github.com/riscv/docs-resources", target_dir + "/ext/riscv-isa-manual/docs-resources")
end

# @param url [String] Where to clone repository from
# @param workspace_dir [String] Path to desired workspace directory
def pf_ensure_repository(url, workspace_dir)
  if Dir.exist?(workspace_dir) && !Dir.empty?(workspace_dir)
    # Workspace already exists so just make sure it is up-to-date.
    sh "git -C #{workspace_dir} fetch"
    sh "git -C #{workspace_dir} pull origin main"
  else
    # Need to clone repository.
    sh "git clone #{url} #{workspace_dir}"
  end
end

# @param erb_template_pname [String] Path to ERB template file
# @param erb_binding [Binding] Path to ERB template file
# @param target_pname [String] Full pathname of adoc file being generated
# @param portfolio_design [PortfolioDesign] Portfolio design being generated
def pf_create_adoc(erb_template_pname, erb_binding, target_pname, portfolio_design)
  template_path = Pathname.new(erb_template_pname)
  erb = ERB.new(File.read(template_path), trim_mode: "-")
  erb.filename = template_path.to_s

  # Ensure directory holding target adoc file is present.
  FileUtils.mkdir_p File.dirname(target_pname)

  # Convert ERB to final ASCIIDOC. Note that this code is broken up into separate function calls
  # each with a variable name to aid in running a command-line debugger on this code.
  puts "UPDATE: Converting ERB template to adoc for #{portfolio_design.name}"
  begin
    erb_result = erb.result(erb_binding)
  rescue Encoding::CompatibilityError => e
    warn "You've encountered a Ruby Encoding::CompatibilityError error in #{erb_template_pname} or a file it includes."
    warn "Ruby won't tell you where the non UTF-8 character(s) are located."
    warn "Instead, run 'grep -RP \"[\\x80-\\xFF]\" arch' to see these nasty characters in any line in the whole 'arch' directory."
    raise e
  end
  erb_result_monospace_converted_to_links = portfolio_design.convert_monospace_to_links(erb_result)
  erb_result_with_links_resolved = AsciidocUtils.resolve_links(erb_result_monospace_converted_to_links)

  File.write(target_pname, erb_result_with_links_resolved)
  puts "UPDATE: Generated adoc in #{target_pname}"
end

# @param adoc_file [String] Full name of source adoc file
# @param target_pname [String] Full name of PDF file being generated
def pf_adoc2pdf(adoc_file, target_pname)
  FileUtils.mkdir_p File.dirname(target_pname)

  puts "UPDATE: Generating PDF in #{target_pname}"
  cmd = [
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
    "-o #{target_pname}",
    adoc_file
  ].join(" ")

  puts "UPDATE: bundle exec #{cmd}"

  # Write out command used to convert adoc to PDF to allow running this
  # manually during development.
  run_pname = File.dirname(adoc_file) + "/adoc2pdf.sh"
  sh "rm -f #{run_pname}"
  sh "echo '#!/bin/bash' >#{run_pname}"
  sh "echo >>#{run_pname}"
  sh "echo bundle exec #{cmd} >>#{run_pname}"
  sh "chmod +x #{run_pname}"

  # Now run the actual command.
  sh cmd

  puts "UPDATE: Generated PDF in #{target_pname}"
end

# @param adoc_file [String] Full name of source adoc file
# @param target_pname [String] Full name of HTML file being generated
def pf_adoc2html(adoc_file, target_pname)
  FileUtils.mkdir_p File.dirname(target_pname)

  puts "UPDATE: Generating HTML in #{target_pname}"
  cmd = [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
    "-o #{target_pname}",
    adoc_file
  ].join(" ")

  puts "UPDATE: bundle exec #{cmd}"

   # Write out command used to convert adoc to HTML to allow running this
  # manually during development.
  run_pname = File.dirname(adoc_file) + "/adoc2html.sh"
  sh "rm -f #{run_pname}"
  sh "echo '#!/bin/bash' >#{run_pname}"
  sh "echo >>#{run_pname}"
  sh "echo bundle exec #{cmd} >>#{run_pname}"
  sh "chmod +x #{run_pname}"

  # Now run the actual command.
  sh cmd

  puts "UPDATE: Generated HTML in #{target_pname}"
end
