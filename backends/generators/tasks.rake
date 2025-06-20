# frozen_string_literal: true

require "udb/resolver"

directory "#{$root}/gen/go"
directory "#{$root}/gen/c_header"

namespace :gen do
  desc <<~DESC
    Generate Go code from RISC-V instruction and CSR definitions

    Options:
     * CONFIG - Configuration name (defaults to "_")
     * OUTPUT_DIR - Output directory for generated Go code (defaults to "#{$root}/gen/go")
  DESC
  task go: "#{$root}/gen/go" do
    config_name = ENV["CONFIG"] || "_"
    output_dir = ENV["OUTPUT_DIR"] || "#{$root}/gen/go/"

    # Ensure the output directory exists
    FileUtils.mkdir_p output_dir

    # Get the arch paths based on the config
    resolver = Udb::Resolver.new
    cfg_arch = resolver.cfg_arch_for(config_name)
    inst_dir = cfg_arch.path / "inst"
    csr_dir = cfg_arch.path / "csr"

    # Run the Go generator script using the same Python environment
    # Note: The script uses --output not --output-dir
    sh "#{$root}/.home/.venv/bin/python3 #{$root}/backends/generators/Go/go_generator.py --inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --output=#{output_dir}inst.go"
  end

  desc <<~DESC
    Generate C encoding header from RISC-V instruction and CSR definitions
    This is used by Spike, ACTs and the Sail Model

    Options:
     * CONFIG - Configuration name (defaults to "_")
     * OUTPUT_DIR - Output directory for generated C Header headers (defaults to "#{$root}/gen/c_header")
  DESC
  task c_header: "#{$root}/gen/c_header" do
    config_name = ENV["CONFIG"] || "_"
    output_dir = ENV["OUTPUT_DIR"] || "#{$root}/gen/c_header/"

    # Ensure the output directory exists
    FileUtils.mkdir_p output_dir

    # Get the arch paths based on the config
    resolver = Udb::Resolver.new
    cfg_arch = resolver.cfg_arch_for(config_name)
    inst_dir = cfg_arch.path / "inst"
    csr_dir = cfg_arch.path / "csr"
    ext_dir = cfg_arch.path / "ext"

    # Run the C header generator script using the same Python environment
    # The script generates encoding.h for inclusion in C programs
    sh "#{$root}/.home/.venv/bin/python3 #{$root}/backends/generators/c_header/generate_encoding.py --inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --ext-dir=#{ext_dir} --output=#{output_dir}encoding.out.h --include-all"
  end
end
