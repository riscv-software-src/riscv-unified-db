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
    class Show < SubCommandBase
      include Thor::Actions

      desc "extension NAME", "Show information about an extension"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_arch_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_arch_overlay_isa_path.to_s
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

        cfg_arch =
          Udb::Resolver.new.cfg_arch_for(
            cfg_file.realpath,
            arch_path: Pathname.new(options[:arch]),
            gen_path: Pathname.new(options[:gen]),
            arch_overlay_path: Pathname.new(options[:arch_overlay])
          )
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
        end
      end
    end

    class List < SubCommandBase
      desc "extensions", "list all extensions, including those implied, for a config"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_arch_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_arch_overlay_isa_path.to_s
      method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
      method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
      method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
      def extensions
        raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])

        cfg_file =
          if File.file?(options[:config])
            Pathname.new(options[:config])
          elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
            Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
          else
            raise ArgumentError, "Cannot find config: #{options[:config]}"
          end

        cfg_arch =
          Udb::Resolver.new.cfg_arch_for(
            cfg_file.realpath,
            arch_path: Pathname.new(options[:arch]),
            gen_path: Pathname.new(options[:gen]),
            arch_overlay_path: Pathname.new(options[:arch_overlay])
          )
        cfg_arch.possible_extensions.each do |ext|
          puts ext.name
        end
      end


      desc "parameters", "list all parameters applicable to  a config"
      method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_arch_isa_path.to_s
      method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_arch_overlay_isa_path.to_s
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

        cfg_arch =
          Udb::Resolver.new.cfg_arch_for(
            cfg_file.realpath,
            arch_path: Pathname.new(options[:arch]),
            gen_path: Pathname.new(options[:gen]),
            arch_overlay_path: Pathname.new(options[:arch_overlay])
          )
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

    desc "list", "List "
    subcommand "list", CliCommands::List

    desc "show", "Show "
    subcommand "show", CliCommands::Show

    desc "disasm ENCODING", "Disassemble an instruction encoding"
    method_option :arch, aliases: "-a", type: :string, desc: "Path to architecture database", default: Udb.default_arch_isa_path.to_s
    method_option :arch_overlay, type: :string, desc: "Path to architecture overlay directory", default: Udb.default_arch_overlay_isa_path.to_s
    method_option :config, type: :string, required: true, desc: "Configuration name, or path to a config file", default: "_"
    method_option :config_dir, type: :string, desc: "Path to directory with config files", default: Udb.default_cfgs_path.to_s
    method_option :gen, type: :string, desc: "Path to folder used for generation", default: Udb.default_gen_path.to_s
    def disasm(encoding_str)
      raise ArgumentError, "Arch directory does not exist: #{options[:arch]}" unless File.directory?(options[:arch])
      raise MalformattedArgumentError, "encoding must be a hex string" unless encoding_str =~ /^(0[xX])?[a-fA-F0-9]+$/

      cfg_file =
        if File.file?(options[:config])
          Pathname.new(options[:config])
        elsif File.file?("#{options[:config_dir]}/#{options[:config]}.yaml")
          Pathname.new("#{options[:config_dir]}/#{options[:config]}.yaml")
        else
          raise ArgumentError, "Cannot find config: #{options[:config]}"
        end

      cfg_arch =
        Udb::Resolver.new.cfg_arch_for(
          cfg_file.realpath,
          arch_path: Pathname.new(options[:arch]),
          gen_path: Pathname.new(options[:gen]),
          arch_overlay_path: Pathname.new(options[:arch_overlay])
        )

      encoding = encoding_str.to_i(16)

      matches = { 32 => [], 64 => [] }

      cfg_arch.possible_xlens.each do |xlen|
        say "RV#{xlen}:"

        matches[xlen] = cfg_arch.instructions.select do |i|
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
