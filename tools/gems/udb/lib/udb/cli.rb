#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

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
    def self.exit_on_failure?
      true
    end

    desc "version", "Display UDB version and exit"
    def version
      puts Udb.version
    end

    desc "list", "List "
    subcommand "list", CliCommands::List
  end
end
