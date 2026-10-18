# frozen_string_literal: true

require "json"
require "tmpdir"
require "yaml"
require_relative "errors"

module XceJson
  module TestRunner
    REQUIRED_FIELDS = %w[name cfg extension instruction expected].freeze

    def self.load_manifest(path)
      document = YAML.safe_load(File.read(path), permitted_classes: [], aliases: false)
      cases = document.is_a?(Hash) ? document["cases"] : nil
      raise TestError, "#{path}: 'cases' must be an array" unless cases.is_a?(Array)
      raise TestError, "#{path}: 'cases' must not be empty" if cases.empty?

      cases.each_with_index do |test_case, index|
        entry = "#{path}: test entry #{index + 1}"
        raise TestError, "#{entry} must be a mapping" unless test_case.is_a?(Hash)

        missing = REQUIRED_FIELDS.reject { |field| test_case.key?(field) }
        raise TestError, "#{entry} is missing #{missing.join(', ')}" unless missing.empty?

        REQUIRED_FIELDS.each do |field|
          value = test_case[field]
          next if value.is_a?(String) && !value.strip.empty?

          raise TestError, "#{entry} field '#{field}' must be a non-empty string"
        end
      end
      cases
    rescue Psych::Exception => e
      raise TestError, "#{path}: #{e.message}"
    end

    def self.verify(cases, test_root, &generator)
      raise TestError, "backend generator callback is required" unless generator

      Dir.mktmpdir("udb-xce-json-test-") do |dir|
        cases.group_by { |test_case| [test_case["cfg"], test_case["extension"]] }.each do |selector, grouped|
          cfg, extension = selector
          output_dir = File.join(dir, "#{cfg}-#{extension}")
          mnemonics = grouped.map { |test_case| test_case["instruction"] }
          result = generator.call(
            cfg_name: cfg,
            extension_filter: [extension],
            instruction_filter: mnemonics,
            output_dir: output_dir
          )
          unless result.exported == mnemonics.size
            raise TestError, "#{selector.join('/')}: expected #{mnemonics.size} exports, got #{result.exported}"
          end
          unless result.skipped.empty?
            raise TestError, "#{selector.join('/')}: unexpected skipped instructions"
          end
          unless [32, 64].include?(result.xlen)
            raise TestError, "#{selector.join('/')}: exporter returned invalid XLEN #{result.xlen.inspect}"
          end
          module_path = File.join(output_dir, "#{extension}.json")
          raise TestError, "#{selector.join('/')}: output not found" unless File.file?(module_path)

          document = JSON.parse(File.read(module_path))
          validate_module(document, extension, mnemonics, result.xlen, module_path)

          grouped.each { |test_case| verify_case(test_case, document["instructions"], test_root) }
        end
      end
    rescue JSON::ParserError => e
      raise TestError, e.message
    end

    def self.validate_module(document, extension, mnemonics, xlen, path)
      expected_keys = %w[name arch type instructions]
      raise TestError, "#{path}: unexpected module fields" unless document.keys.sort == expected_keys.sort
      raise TestError, "#{path}: wrong module name" unless document["name"] == extension
      raise TestError, "#{path}: expected arch rv#{xlen}" unless document["arch"] == "rv#{xlen}"
      raise TestError, "#{path}: type must be a string" unless document["type"].is_a?(String)

      instructions = document["instructions"]
      raise TestError, "#{path}: flat instructions array not found" unless instructions.is_a?(Array)

      actual = instructions.map { |instruction| instruction["asm"]&.split(" ", 2)&.first }
      raise TestError, "#{path}: expected only #{mnemonics.join(', ')}" unless actual.sort == mnemonics.sort

      forbidden = %w[execute uses defs etype]
      unexpected = instructions.flat_map { |instruction| instruction.keys & forbidden }.uniq
      raise TestError, "#{path}: forbidden instruction fields: #{unexpected.join(', ')}" unless unexpected.empty?
    end

    def self.verify_case(test_case, instructions, test_root)
      mnemonic = test_case["instruction"]
      matches = instructions.select { |instruction| instruction["asm"]&.split(" ", 2)&.first == mnemonic }
      raise TestError, "#{test_case['name']}: expected one #{mnemonic}, found #{matches.size}" unless matches.one?

      expected_path = File.expand_path(test_case["expected"], test_root)
      expected = JSON.parse(File.read(expected_path))
      return if expected == matches.first

      raise TestError, "#{test_case['name']}: generated JSON does not match #{test_case['expected']}"
    end

    private_class_method :validate_module, :verify_case
  end
end
