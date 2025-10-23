# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative '../../tools/ruby-gems/udb/lib/udb/prm_generator'
require 'udb_helpers/backend_helpers'

# Task to generate AsciiDoc files from PRM
task :generate_prm_adoc, [:prm_name] do |t, args|
  prm_name = args[:prm_name]
  raise ArgumentError, "PRM name is required" unless prm_name

  generator = PrmGenerator::Generator.new(
    prm_name,
    resolver: $resolver,
    output_dir: PRM_PDF_OUTPUT_DIR.to_s,
    template_dir: PRM_PDF_DIR.to_s,
    root_dir: $root.to_s
  )

  generator.generate_adoc
end
