# frozen_string_literal: true

require_relative "lib/errors"
require_relative "lib/exporter"
require_relative "lib/test_runner"

module XceJson
  module TaskOptions
    def self.list(name, value)
      return nil if value.nil?

      values = value.split(",").map(&:strip).reject(&:empty?).uniq
      raise ConfigurationError, "#{name} must contain at least one value" if values.empty?

      values
    end
  end

  module TaskOutput
    def self.print_skipped(skipped)
      skipped.each { |item| warn "SKIP: #{item.instruction} -- #{item.reason}" }
    end
  end
end

namespace :gen do
  desc <<~DESC
    Generate structural XCE JSON from UDB instruction data

    Environment variables:
     * CONFIG       - Configuration name (required, e.g., "rv64")
     * EXTENSIONS   - Comma-separated extension filter (optional, e.g., "Zicond,Zba")
     * INSTRUCTIONS - Comma-separated instruction filter (optional, e.g., "add,addi")
     * OUTPUT_DIR   - Output directory (defaults to "#{$root}/gen/xce_json")
  DESC
  task :xce_json do
    cfg_name = ENV["CONFIG"]&.strip
    output_dir = ENV["OUTPUT_DIR"]
    abort "ERROR: CONFIG is required" if cfg_name.nil? || cfg_name.empty?
    if output_dir&.strip&.empty?
      abort "ERROR: OUTPUT_DIR must contain at least one non-whitespace character"
    end
    output_dir ||= File.join($root, "gen", "xce_json")

    extension_filter = XceJson::TaskOptions.list("EXTENSIONS", ENV["EXTENSIONS"])
    instruction_filter = XceJson::TaskOptions.list("INSTRUCTIONS", ENV["INSTRUCTIONS"])

    result = XceJson::Exporter.generate(
      cfg_name: cfg_name,
      extension_filter: extension_filter,
      instruction_filter: instruction_filter,
      output_dir: output_dir
    )
    XceJson::TaskOutput.print_skipped(result.skipped)
    result.output_paths.each { |path| puts "Generated: #{path}" }
    puts "Done: #{result.exported} exported, #{result.skipped.size} skipped."
  rescue XceJson::NoInstructionsGeneratedError => e
    XceJson::TaskOutput.print_skipped(e.skipped)
    abort "ERROR: #{e.message}"
  rescue XceJson::Error => e
    abort "ERROR: #{e.message}"
  end
end
namespace :test do
  desc "Run XCE JSON tests"
  task :xce_json do
    test_root = File.expand_path("test", __dir__)
    cases = XceJson::TestRunner.load_manifest(File.join(test_root, "manifest.yaml"))
    XceJson::TestRunner.verify(cases, test_root) do |**options|
      XceJson::Exporter.generate(**options)
    end
    puts "PASS: #{cases.size} XCE JSON test(s)"
  rescue XceJson::Error => e
    abort "ERROR: #{e.message}"
  end
end
