# frozen_string_literal: true

require "fileutils"
require "json"
require "tempfile"
require "udb/resolver"

require_relative "errors"
require_relative "instruction_selector"
require_relative "instruction_converter"

module XceJson
  ExportResult = Data.define(:xlen, :exported, :skipped, :output_paths)

  module Exporter
    def self.generate(cfg_name:, extension_filter: nil, instruction_filter: nil, output_dir:)
      cfg_arch = load_config(cfg_name)
      xlen = cfg_arch.mxlen
      unless [32, 64].include?(xlen)
        raise ConfigurationError, "Config '#{cfg_name}' must determine MXLEN as 32 or 64"
      end

      selection = InstructionSelector.select(
        cfg_arch,
        xlen:,
        extension_filter:,
        instruction_filter:
      )
      export_modules(selection, instruction_filter, output_dir, xlen)
    end

    def self.load_config(cfg_name)
      Udb::Resolver.new.cfg_arch_for(cfg_name)
    rescue StandardError => e
      raise ConfigurationError, "Failed to load config '#{cfg_name}': #{e.message}"
    end

    def self.export_modules(selection, instruction_filter, output_dir, xlen)
      exported = 0
      skipped = selection.skipped.dup
      output_paths = []

      selection.groups.each do |extension_name, instructions|
        instruction_data = instructions.filter_map do |instruction|
          InstructionConverter.convert(instruction, xlen)
        rescue UnsupportedInstructionError => e
          raise if instruction_filter && !instruction_filter.empty?

          skipped << SkippedInstruction.new(e.instruction, e.reason)
          nil
        end
        next if instruction_data.empty?

        document = build_module(extension_name, instruction_data, xlen)
        output_path = File.join(output_dir, "#{extension_name}.json")
        write_output(document, output_path)
        output_paths << output_path
        exported += instruction_data.size
      end

      raise NoInstructionsGeneratedError.new(skipped:) if exported.zero?

      ExportResult.new(xlen:, exported:, skipped:, output_paths:)
    end

    def self.build_module(extension_name, instructions, xlen)
      types = instructions.map { |instruction| instruction["type"] }.uniq
      {
        "name" => extension_name,
        "arch" => "rv#{xlen}",
        "type" => types.one? ? types.first : "",
        "instructions" => instructions
      }
    end

    def self.write_output(document, path)
      directory = File.dirname(path)
      FileUtils.mkdir_p(directory)

      Tempfile.create([".#{File.basename(path)}", ".tmp"], directory) do |file|
        file.write(JSON.pretty_generate(document))
        file.write("\n")
        file.flush
        file.fsync
        file.chmod(0o666 & ~File.umask)
        File.rename(file.path, path)
      end
    rescue SystemCallError => e
      raise OutputError, "Failed to write '#{path}': #{e.message}"
    end

    private_class_method :load_config, :export_modules, :build_module, :write_output
  end
end
