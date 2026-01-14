# frozen_string_literal: true

require "udb/resolver"
require 'json'
require 'tempfile'

directory "#{$root}/gen/go"
directory "#{$root}/gen/c_header"
directory "#{$root}/gen/sverilog"
directory "#{$root}/gen/qemu"

def with_resolved_exception_codes(cfg_arch)
  # Process ERB templates in exception codes using Ruby ERB processing
  resolved_exception_codes = []

  # Collect all exception codes from extensions and resolve ERB templates
  cfg_arch.extensions.each do |ext|
    ext.exception_codes.each do |ecode|
      # Use Ruby's ERB processing to resolve templates in exception names
      resolved_name = cfg_arch.render_erb(
        ecode.name,
        "exception code name: #{ecode.name}"
      )

      resolved_exception_codes << {
        "num"  => ecode.num,
        "name" => resolved_name,
        "var"  => ecode.var,
        "ext"  => ext.name
      }
    end
  end

  # Write resolved exception codes to a temporary JSON file
  tempfile = Tempfile.new(["resolved_exception_codes", ".json"])
  tempfile.write(JSON.pretty_generate(resolved_exception_codes))
  tempfile.flush

  begin
    yield tempfile.path # Run the generator script
  ensure
    tempfile.close
    tempfile.unlink
  end
end

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

    # Run the Go generator script
    # Note: The script uses --output not --output-dir
    sh "/opt/venv/bin/python3 #{$root}/backends/generators/Go/go_generator.py --inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --output=#{output_dir}inst.go"
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

    with_resolved_exception_codes(cfg_arch) do |resolved_codes|
      sh "/opt/venv/bin/python3 #{$root}/backends/generators/c_header/generate_encoding.py " \
         "--inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --ext-dir=#{ext_dir} " \
         "--resolved-codes=#{resolved_codes} " \
         "--output=#{output_dir}encoding.out.h --include-all"
    end
  end

  desc <<~DESC
    Generate SystemVerilog package from RISC-V instruction and CSR definitions

    Options:
     * CONFIG - Configuration name (defaults to "_")
     * OUTPUT_DIR - Output directory for generated SystemVerilog code (defaults to "#{$root}/gen/sverilog")
  DESC
  task sverilog: "#{$root}/gen/sverilog" do
    config_name = ENV["CONFIG"] || "_"
    output_dir = ENV["OUTPUT_DIR"] || "#{$root}/gen/sverilog/"

    # Ensure the output directory exists
    FileUtils.mkdir_p output_dir

    # Get the arch paths based on the config
    resolver = Udb::Resolver.new
    cfg_arch = resolver.cfg_arch_for(config_name)
    inst_dir = cfg_arch.path / "inst"
    csr_dir = cfg_arch.path / "csr"
    ext_dir = cfg_arch.path / "ext"

    with_resolved_exception_codes(cfg_arch) do |resolved_codes|
      sh "/opt/venv/bin/python3 #{$root}/backends/generators/sverilog/sverilog_generator.py " \
         "--inst-dir=#{inst_dir} --csr-dir=#{csr_dir} --ext-dir=#{ext_dir} " \
         "--resolved-codes=#{resolved_codes} " \
         "--output=#{output_dir}riscv_decode_package.svh --include-all"
    end
  end

  desc <<~DESC
    Generate QEMU RISC-V files from instruction and CSR definitions

    Options:
     * CONFIG - Configuration name (defaults to "_")
     * OUTPUT_DIR - Output directory for generated QEMU files (defaults to "#{$root}/gen/qemu")
     * EXTENSIONS - Comma-separated list of extensions (defaults to all)
     * ARCH - Target architecture: RV32, RV64, or BOTH (defaults to "RV64")
  DESC
  task qemu: "#{$root}/gen/qemu" do
    config_name = ENV["CONFIG"] || "_"
    output_dir = ENV["OUTPUT_DIR"] || "#{$root}/gen/qemu/"
    extensions = ENV["EXTENSIONS"] || ""
    arch = ENV["ARCH"] || "RV64"

    # Ensure the output directory exists
    FileUtils.mkdir_p output_dir

    # Get the arch paths based on the config
    resolver = Udb::Resolver.new
    cfg_arch = resolver.cfg_arch_for(config_name)
    inst_dir = cfg_arch.path / "inst"
    csr_dir = cfg_arch.path / "csr"

    # Build command with optional extensions, using argument array to avoid shell interpolation
    cmd = [
      "/opt/venv/bin/python3",
      "#{$root}/backends/generators/qemu/qemu_generator.py",
      "--inst-dir=#{inst_dir}",
      "--csr-dir=#{csr_dir}",
      "--output-dir=#{output_dir}",
      "--arch=#{arch}"
    ]

    if extensions.empty?
      cmd << "--include-all"
    else
      cmd << "--extensions=#{extensions}"
    end

    sh(*cmd)
  end
end
