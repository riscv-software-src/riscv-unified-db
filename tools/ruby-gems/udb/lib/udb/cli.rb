#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "thor"
require "terminal-table"

require_relative "resolver"

class SubCommandBase < Thor
  def self.banner(command, _namespace = nil, _subcommand = false)
    "#{basename} #{subcommand_prefix} #{command.usage}"
  end

  def self.subcommand_prefix
    T.must(name).gsub(/.*::/, "").gsub(/^[A-Z]/) { |match| T.must(match[0]).downcase }.gsub(/[A-Z]/) do |match|
      "-#{T.must(match[0]).downcase}"
    end
  end
end

module Udb
  module CliCommands
    class Validate < SubCommandBase
      include Thor::Actions

      desc "cfg NAME_OR_PATH", "Validate a configuration file"
      long_desc <<~DESC
        Check that a configuration file is valid for the given spec.

        NAME_OR_PATH can be a configuration name found in the cfgs directory
        or a path to a config file.
      DESC
      method_option :std, aliases: "-a", type: :string, desc: "Path to standard specification database", default: Udb.default_std_isa_path.to_s
      method_option :custom, type: :string, desc: "Path to custom specification directory, if needed", default: Udb.default_custom_isa_path.to_s
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      def cfg(name_or_path)
        raise ArgumentError, "Spec directory does not exist: #{options[:std]}" unless File.directory?(options[:std])

        cfg_file =
          if File.file?(name_or_path)
            Pathname.new(name_or_path)
          elsif File.file?("#{options[:config_dir]}/#{name_or_path}.yaml")
            Pathname.new("#{options[:config_dir]}/#{name_or_path}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{name_or_path}"
          end
        result = ConfiguredArchitecture.validate(cfg_file)

        cfg_spec = YAML.load_file(cfg_file)
        if result
          say "Config #{cfg_spec.fetch('name')} is valid"
        else
          say "Config #{cfg_spec.fetch('name')} is invalid"
          exit 1
        end
      end
    end

    class Show < SubCommandBase
      include Thor::Actions

      desc "extension NAME", "Show information about an extension"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      def extension(ext_name)
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        resolver =
          Udb::Resolver.new(
            std_path_override: Pathname.new(options[:arch]),
            gen_path_override: Pathname.new(options[:gen]),
            custom_path_override: Pathname.new(options[:arch_overlay])
          )
        cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)
        ext = cfg_arch.extension(ext_name)
        if ext.nil?
          say "Could not find an extension named '#{ext_name}'", :red
        else
          say <<~INFO
            #{ext.name} Extension
              #{ext.long_name}

            Versions:
            #{ext.versions.map { |ext_ver| "  * #{ext_ver.version_str}" }.join("\n") }

          INFO
          say "Includes #{ext.instructions.count} instructions" if ext.instructions.count.positive?
        end
      end

      desc "parameter NAME", "Show information about a parameter"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      def parameter(param_name)
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        resolver =
          Udb::Resolver.new(
            std_path_override: Pathname.new(options[:arch]),
            gen_path_override: Pathname.new(options[:gen]),
            custom_path_override: Pathname.new(options[:arch_overlay])
          )
        cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)
        param = cfg_arch.param(param_name)
        if param.nil?
          say "Could not find parameter named #{param_name}"
        else
          say <<~INFO
            #{param_name}

              Defined by extension:
              #{param.exts.map { |e| "    - #{e.name}" }.join("\n")}

              Description:
                #{param.desc.gsub("\n", "\n    ")}

              Value:
                #{param.schema.to_pretty_s}
          INFO
        end
      end
    end

    class List < SubCommandBase
      desc "extensions", "list all extensions, including those implied, for a config"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      method_option :output, aliases: "-o", type: :string, desc: "Output file, or '-' for stdout", default: "-"
      def extensions
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        out =
          if options[:output] == "-"
            $stdout
          else
            File.open(options[:output], "w")
          end

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        resolver =
          Udb::Resolver.new(
            std_path_override: Pathname.new(options[:arch]),
            gen_path_override: Pathname.new(options[:gen]),
            custom_path_override: Pathname.new(options[:arch_overlay])
          )
        cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)
        cfg_arch.possible_extensions.each do |ext|
          out.puts ext.name
        end
      end


      desc "parameters", "list all parameters applicable to  a config"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :extensions, aliases: "-e", type: :array, desc: "Only list parameters from extensions"
      method_option :output_format, aliases: "-f", enum: ["ascii", "yaml", "json"], type: :string, desc: "Output format. 'ascii' prints a table to stdout. 'yaml' prints YAML to stdout. 'json' prints JSON to stdout", default: 'ascii'
      method_option :output, aliases: "-o", type: :string, desc: "Output file, or '-' for stdout", default: "-"
      def parameters
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        out =
          if options[:output] == "-"
            $stdout
          else
            File.open(options[:output], "w")
          end

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        resolver =
          Udb::Resolver.new(
            std_path_override: Pathname.new(options[:arch]),
            gen_path_override: Pathname.new(options[:gen]),
            custom_path_override: Pathname.new(options[:arch_overlay])
          )
        cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)
        params =
          if options[:extensions]
            cfg_arch.possible_extensions.select{ |e| options[:extensions].include?(e.name) }.map(&:params).flatten.uniq(&:name).sort
          else
            cfg_arch.possible_extensions.map(&:params).flatten.uniq(&:name).sort
          end
        if options[:output_format] == "ascii"
          table = ::Terminal::Table.new(
            headings: ["Name", "Extension(s)", "description"],
            rows: params.map { |p| [p.name, p.exts.map(&:name).join(", "), p.desc] },
          )
          table.style = { all_separators: true }
          out.puts table
        elsif options[:output_format] == "yaml"
          yaml = []
          params.each do |p|
            yaml << { "name" => p.name, "exts" => p.exts.map(&:name), "description" => p.desc }
          end
          out.puts YAML.dump(yaml)
        elsif options[:output_format] == "json"
          yaml = []
          params.each do |p|
            yaml << { "name" => p.name, "exts" => p.exts.map(&:name), "description" => p.desc }
          end
          out.puts JSON.dump(yaml)
        end
      end


      desc "csrs", "list all csrs for a config"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      def csrs
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        resolver =
          Udb::Resolver.new(
            std_path_override: Pathname.new(options[:arch]),
            custom_path_override: Pathname.new(options[:arch_overlay]),
            gen_path_override: Pathname.new(options[:gen])
          )
        cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)
        count = 0
        cfg_arch.csrs.each do |csr|
          puts csr.name
          count += 1
        end
        count
      end
    end
  end

  class Cli < Thor
    include Thor::Actions
    check_unknown_options!

    def self.exit_on_failure?
      true
    end

    desc "version", "Display UDB version and exit"
    def version
      puts Udb.version
    end

    desc "validate", "Validate "
    subcommand "validate", CliCommands::Validate

    desc "list", "List "
    subcommand "list", CliCommands::List

    desc "show", "Show "
    subcommand "show", CliCommands::Show

    desc "disasm ENCODING", "Disassemble an instruction encoding"
    method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_std_isa_path.to_s
    method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_custom_isa_path.to_s
    method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
    method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
    method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
    def disasm(encoding_str)
      raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])
      raise MalformattedArgumentError, "encoding must be a hex string" unless encoding_str =~ /\A(0[xX])?[a-fA-F0-9]+\z/

      cfg_file =
        if File.file?(options[:config])
          Pathname.new(options[:config])
        elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
          Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
        else
          raise ArgumentError, "Cannot find config: #{options[:config]}"
        end

      resolver =
        Udb::Resolver.new(
          std_path_override: Pathname.new(options[:arch]),
          gen_path_override: Pathname.new(options[:gen]),
          custom_path_override: Pathname.new(options[:arch_overlay])
        )
      cfg_arch = resolver.cfg_arch_for(cfg_file.realpath)

      encoding = encoding_str.to_i(16)

      matches = { 32 => [], 64 => [] }

      cfg_arch.possible_xlens.each do |xlen|
        say "RV#{xlen}:"

        matches[xlen] = cfg_arch.instructions.select do |i|
          next unless i.defined_in_base?(xlen)

          opcode_mask = i.encoding(xlen).format.gsub(/[01]/, "1").gsub("-", "0").to_i(2)
          match = i.encoding(xlen).format.gsub("-", "0").to_i(2)
          (opcode_mask & encoding) == match
        end

        if matches[xlen].empty?
          say "  Illegal Instruction"
        else
          matches[xlen].each do |inst|
            say "  #{inst.name}"
          end
        end
      end
    end
  end
end
