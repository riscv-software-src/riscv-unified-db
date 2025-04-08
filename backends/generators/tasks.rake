# frozen_string_literal: true

directory "#{$root}/gen/go"

namespace :gen do
  desc <<~DESC
    Generate Go code from RISC-V instruction and CSR definitions

    Options:
     * CONFIG - Configuration name (defaults to "_")
     * OUTPUT_DIR - Output directory for generated Go code (defaults to "#{$root}/gen/go")
  DESC
  task :go => "#{$root}/gen/go" do
    config_name = ENV["CONFIG"] || "_"
    output_dir = ENV["OUTPUT_DIR"] || "#{$root}/gen/go/"

    # Ensure the output directory exists
    FileUtils.mkdir_p output_dir

    # Make sure the architecture is resolved
    Rake::Task["#{$root}/.stamps/resolve-#{config_name}.stamp"].invoke

    # Get the arch paths based on the config
    inst_dir = $root / "arch" / "inst"
    csr_dir = $root / "arch" / "csr"

    # If using a specific config other than the default, use the resolved arch
    if config_name != "_"
      inst_dir = $root / "gen" / "resolved_arch" / config_name / "inst"
      csr_dir = $root / "gen" / "resolved_arch" / config_name / "csr"
    end

    # Run the Go generator script using the same Python environment
    # Note: The script uses --output not --output-dir
    sh "#{$root}/.home/.venv/bin/python3 #{$root}/backends/generators/Go/go_generator.py --inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --output=#{output_dir}inst.go"
  end
end
