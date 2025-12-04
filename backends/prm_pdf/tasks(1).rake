# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "udb_helpers/backend_helpers"
require_relative '../../tools/ruby-gems/udb/lib/udb/prm_generator'

PRM_PDF_DIR = Pathname.new(__FILE__).dirname
PRM_PDF_OUTPUT_DIR = $root / "gen" / "prm_pdf"

load "#{PRM_PDF_DIR}/adoc_gen.rake"
load "#{PRM_PDF_DIR}/pdf_gen.rake"

namespace :prm do
  desc "Generate AsciiDoc files for PRM"
  task :adoc, [:prm_name] do |_t, args|
    raise "No PRM name specified" unless args[:prm_name]

    puts "[INFO] Generating AsciiDoc files for #{args[:prm_name]}..."
    generator = PrmGenerator::Generator.new(
      args[:prm_name],
      resolver: $resolver,
      output_dir: PRM_PDF_OUTPUT_DIR.to_s,
      template_dir: PRM_PDF_DIR.to_s,
      root_dir: $root.to_s
    )

    generator.generate_adoc
  end

  desc "Generate PDF documentation for PRM"
  task :pdf, [:prm_name] => :ensure_pdf_tooling do |_t, args|
    raise "No PRM name specified" unless args[:prm_name]

    puts "[INFO] Generating PDF for #{args[:prm_name]}..."
    generator = PrmGenerator::Generator.new(
      args[:prm_name],
      resolver: $resolver,
      output_dir: PRM_PDF_OUTPUT_DIR.to_s,
      template_dir: PRM_PDF_DIR.to_s,
      root_dir: $root.to_s
    )

    # First generate AsciiDoc files
    generator.generate_adoc
    # Then generate PDF
    generator.generate_pdf
  end

  desc "View generated PDF"
  task :view, [:prm_name] do |_t, args|
    raise "No PRM name specified" unless args[:prm_name]

    pdf_path = PRM_PDF_OUTPUT_DIR / args[:prm_name] / "pdf" / "#{args[:prm_name]}-specification.pdf"

    unless File.exist?(pdf_path)
      puts "PDF not found at: #{pdf_path}"
      puts "Generate it first using: ./do prm:pdf[#{args[:prm_name]}]"
      next
    end

    puts "Opening PDF: #{pdf_path}"
    case RbConfig::CONFIG['host_os']
    when /linux/
      system("xdg-open #{pdf_path} &")
    when /darwin/
      system("open #{pdf_path}")
    when /mswin|mingw/
      system("start \"\" #{pdf_path}")
    else
      puts "Please open: #{pdf_path}"
    end
  end
end
