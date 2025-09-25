# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative '../../tools/ruby-gems/udb/lib/udb/prm_generator'

# Set default encoding to UTF-8 to avoid encoding conflicts
Encoding.default_external = Encoding::UTF_8
Encoding.default_internal = Encoding::UTF_8

task :ensure_pdf_tooling do
  # Ensure theme directory exists
  theme_dir = PRM_PDF_DIR / "pdf-theme"
  FileUtils.mkdir_p(theme_dir)
  puts "[INFO] PDF tooling ready"
end

# Task to generate PDF from PRM
task :generate_prm_pdf, [:prm_name] do |t, args|
  prm_name = args[:prm_name]
  raise ArgumentError, "PRM name is required" unless prm_name

  generator = PrmGenerator::Generator.new(
    prm_name,
    resolver: $resolver,
    output_dir: PRM_PDF_OUTPUT_DIR.to_s,
    template_dir: PRM_PDF_DIR.to_s,
    root_dir: $root.to_s
  )

  generator.generate_pdf
end
