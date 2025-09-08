# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

# Contains common methods called from portfolio-based tasks.rake files.

require "sorbet-runtime"

require "pathname"
require "idlc/passes/gen_adoc"

require "udb/config"

sig { returns(Udb::ConfiguredArchitecture) }
def pf_create_arch
  $resolver.cfg_arch_for("_")
end

# @param portfolio_grp_with_arch Contains one or more Portfolio objects that have an arch (not a cfg_arch).
sig { params(portfolio_grp_with_arch: Udb::PortfolioGroup).returns(Udb::ConfiguredArchitecture) }
def pf_create_cfg_arch(portfolio_grp_with_arch)
  # Create a ConfiguredArchitecture object and provide it a PortfolioGroupConfig object to implement the AbstractConfig API.
  # The DatabaseObjects in PortfolioGroup only have an Architecture object and not a ConfiguredArchitecture object
  # otherwise there would be a circular dependency. To avoid this circular dependency, none of the routines
  # called in the PortfolioGroup object to satisfy the requests from the AbstractConfig API for the ConfiguredArchitecture
  # object can require that the PortfolioGroup DatabaseObjects contain a ConfiguredArchitecture.
  Udb::ConfiguredArchitecture.new(
    portfolio_grp_with_arch.name,
    Udb::AbstractConfig.create(portfolio_grp_with_arch, $resolver.cfg_info("_"))
  )
end

# Clones the CSC fork of the ISA manual repository or updates it if it already exists.
# Does the same for the docs-resources repository which is used by the ISA manual.
#
# @param target_pname [String] Full pathname of target file being generated
def pf_get_latest_csc_isa_manual(target_pname)
  # Directory path for target file.
  target_dir = File.dirname(target_pname)

  # TODO: Remove this branch name and use "main" when dependent PRs are checked into upstream.
  pf_ensure_repository("https://github.com/RISC-V-Certification-Steering-Committee/riscv-isa-manual",
    target_dir + "/ext/riscv-isa-manual", "21-create-yaml-files-for-norm-rules")

  # TODO: Remove this branch name and use "main" when dependent PRs are merged.
  pf_ensure_repository("https://github.com/riscv/docs-resources", target_dir + "/ext/riscv-isa-manual/docs-resources",
    "67-rename-creation-to-definition-and-add-isa-object-names")
end

# @param url [String] Where to clone repository from
# @param workspace_dir [String] Path to desired workspace directory
# @param branch [String] Optional branch to checkout after clone (can be nil)
def pf_ensure_repository(url, workspace_dir, branch)
  if Dir.exist?(workspace_dir) && !Dir.empty?(workspace_dir)
    # Workspace already exists so just make sure it is up-to-date.
    sh "git -C #{workspace_dir} fetch"
    sh "git -C #{workspace_dir} pull origin main"
  else
    # Need to clone repository.
    branch_opt = branch.nil? ? "" : "-b #{branch} "
    sh "git clone #{branch_opt}#{url} #{workspace_dir}"
  end
end

# @param erb_template_pname [String] Path to ERB template file
# @param erb_binding [Binding] Path to ERB template file
# @param target_pname [String] Full pathname of adoc file being generated
# @param portfolio_design [PortfolioDesign] PortfolioDesign being generated
def pf_create_adoc(erb_template_pname, erb_binding, target_pname, portfolio_design)
  $logger.info "Reading ERB adoc template for #{portfolio_design.name}"
  template_path = Pathname.new(erb_template_pname)
  erb = ERB.new(File.read(template_path), trim_mode: "-")
  erb.filename = template_path.to_s

  # Ensure directory holding target adoc file is present.
  FileUtils.mkdir_p File.dirname(target_pname)

  # Convert ERB to final ASCIIDOC. Note that this code is broken up into separate function calls
  # each with a variable name to aid in running a command-line debugger on this code.
  $logger.info "Starting ERB adoc template evaluation for #{portfolio_design.name}"
  erb_result = erb.result(erb_binding)
  $logger.info "Converting monospace formatting to internal link format"
  erb_result_monospace_converted_to_links = portfolio_design.convert_monospace_to_links(erb_result)
  $logger.info "Converting internal link format to adoc links"
  erb_result_with_links_resolved = Udb::Helpers::AsciidocUtils.resolve_links(erb_result_monospace_converted_to_links)
  $logger.info "Writing adoc to #{target_pname}"
  File.write(target_pname, erb_result_with_links_resolved)
end

# @param adoc_file [String] Full name of source adoc file
# @param target_pname [String] Full name of PDF file being generated
def pf_adoc2pdf(adoc_file, target_pname)
  FileUtils.mkdir_p File.dirname(target_pname)

  $logger.info "Generating PDF in #{target_pname}"
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
    "-r idl_highlighter",
    "-o #{target_pname}",
    adoc_file
  ].join(" ")

  $logger.info "bundle exec #{cmd}"

  # Write out command used to convert adoc to PDF to allow running this
  # manually during development.
  run_pname = File.dirname(adoc_file) + "/adoc2pdf.sh"
  sh "rm -f #{run_pname}"
  sh "echo '#!/bin/bash' >#{run_pname}"
  sh "echo >>#{run_pname}"
  sh "echo bundle exec #{cmd} >>#{run_pname}"
  sh "chmod +x #{run_pname}"

  # Now run the actual command.
  sh(cmd)

  $logger.info "Generated PDF in #{target_pname}"
end

# @param adoc_file [String] Full name of source adoc file
# @param target_pname [String] Full name of HTML file being generated
def pf_adoc2html(adoc_file, target_pname)
  FileUtils.mkdir_p File.dirname(target_pname)

  $logger.info "Generating HTML in #{target_pname}"
  cmd = [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r idl_highlighter",
    "-o #{target_pname}",
    adoc_file
  ].join(" ")

  $logger.info "bundle exec #{cmd}"

   # Write out command used to convert adoc to HTML to allow running this
  # manually during development.
  run_pname = File.dirname(adoc_file) + "/adoc2html.sh"
  sh "rm -f #{run_pname}"
  sh "echo '#!/bin/bash' >#{run_pname}"
  sh "echo >>#{run_pname}"
  sh "echo bundle exec #{cmd} >>#{run_pname}"
  sh "chmod +x #{run_pname}"

  # Now run the actual command.
  sh(cmd)

  $logger.info "Generated HTML in #{target_pname}"
end

# @param adoc_file [String] Full pathname of source adoc file
# @param target_pname [String] Full name of tags file being generated
# @param isa_manual_dirname [String] Full pathname of ISA manual root directory
def pf_adoc2norm_tags(adoc_file, target_pname, isa_manual_dirname)
  target_dirname = File.dirname(target_pname)

  # Ensure target directory is present.
  FileUtils.mkdir_p(target_dirname)

  # The tags backend will put the tags file in the same directory as the input adoc file.
  backend_tags_pname = adoc_file.sub(/\.adoc$/, "-norm-tags.json")

  $logger.info "Extracting normative rule tags from #{adoc_file} into #{backend_tags_pname}"
  cmd = [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-a imagesdir=#{isa_manual_dirname}/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r idl_highlighter",
    "--require=#{isa_manual_dirname}/docs-resources/converters/tags.rb",
    "--backend tags",
    "-a tags-match-prefix='norm:'",
    "-a tags-output-suffix='-norm-tags.json'",
    adoc_file
  ].join(" ")

  $logger.info "bundle exec #{cmd}"

  # Write out command used to extract tags to allow running this manually during development.
  run_pname = "#{target_dirname}/adoc2norm_tags.sh"
  sh "rm -f #{run_pname}"
  sh "echo '#!/bin/bash' >#{run_pname}"
  sh "echo >>#{run_pname}"
  sh "echo bundle exec #{cmd} >>#{run_pname}"
  sh "chmod +x #{run_pname}"

  # Now run the actual command.
  sh(cmd)

  $logger.info "Done extracting normative rule tags from #{adoc_file} into #{backend_tags_pname}"

  # Now move the tags to the target_pname.
  FileUtils.mv(backend_tags_pname, target_pname)

  $logger.info "Moved normative rule tags to #{target_pname}"
end

# @param isa_manual_dirname [String] Full pathname of ISA manual root directory
# @param unpriv_tags_json [String] Full pathname of unpriv ISA manual JSON tags file
# @param priv_tags_json [String] Full pathname of priv ISA manual JSON tags file
# @param target_pname [String] Full pathname where normative rules should end up
def pf_build_norm_rules(isa_manual_dir, unpriv_tags_json, priv_tags_json, target_pname)
  target_dirname = File.dirname(target_pname)

  # Ensure target directory is present.
  FileUtils.mkdir_p(target_dirname)

  $logger.info "Building normative rules JSON tag files"

  cmdArray = [
    "ruby",
    "#{isa_manual_dir}/docs-resources/tools/create_normative_rules.rb",
    "-t #{unpriv_tags_json}",
    "-t #{priv_tags_json}"
  ]

  defs_dir = "#{isa_manual_dir}/normative_rule_defs"

  # Add in mock normative rule definition YAML file. Used for test coverage.
  # TBD - Find a better way to do this.
  mock_nr_def_yaml = <<~TEXT
normative_rule_definitions:
  - name: Xmock_nr1
    summary: Here's a summary
    description: Normative rule with multiple tags (one with and without text), description, and summary
    kind: instruction
    intances: [add]
    tags_without_text:
      - name: "norm:add_enc"
        kind: instruction
        instances: [add]
    tags:
      - "norm:add_op"
  - name: Xmock_nr2
    description: |
      Normative rule without any tags.
      Should have lots of room to display this description in the CTP tables.
TEXT

  File.write("#{defs_dir}/mock.yaml", mock_nr_def_yaml)

  # Add -d option for each normative rule definition YAML file
  Dir.glob("#{defs_dir}/*.yaml").each do |def_fname|
    cmdArray.append("-d #{def_fname}")
  end

  # Add output filename as last command line option
  cmdArray.append(target_pname)

  cmd = cmdArray.join(" ")

  $logger.info "bundle exec #{cmd}"

  sh(cmd)

  $logger.info "Done building normative rules into #{target_pname}"
end
