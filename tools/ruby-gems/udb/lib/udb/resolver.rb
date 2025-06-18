# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "bundler"
require "sorbet-runtime"

require_relative "cfg_arch"

module Udb
  extend T::Sig

  sig { returns(Pathname) }
  def self.gem_path
    @gem_path ||= Pathname.new(Bundler.definition.specs.find { |s| s.name == "udb" }.full_gem_path)
  end

  sig { params(from_dir: Pathname).returns(Pathname) }
  def self.find_udb_root(from_dir)
    if (from_dir / "do").executable?
      from_dir
    else
      raise "Cannot find UDB repository root in directory hierarchy" if from_dir.dirname == from_dir

      find_udb_root(from_dir.dirname)
    end
  end
  private_class_method :find_udb_root

  sig { returns(Pathname) }
  def self.repo_root
    @root ||=
      if ENV.key?("UDB_ROOT")
        Pathname.new(ENV["UDB_ROOT"])
      else
        # try to find the root in the directory hierarchy by looking for the do script
        find_udb_root(Pathname.new(__dir__))
      end
  end

  sig { returns(Pathname) }
  def self.default_std_isa_path
    repo_root / "spec" / "std" / "isa"
  end

  sig { returns(Pathname) }
  def self.default_custom_isa_path
    repo_root / "spec" / "custom" / "isa"
  end

  sig { returns(Pathname) }
  def self.default_gen_path
    repo_root / "gen"
  end

  sig { returns(Pathname) }
  def self.default_cfgs_path
    repo_root / "cfgs"
  end

  # resolves the specification in the context of a config, and writes to a generation folder
  #
  # The primary interface for users will be #cfg_arch_for
  class Resolver
    extend T::Sig

    # path to find database schema files
    sig { returns(Pathname) }
    attr_reader :schemas_path

    # path to find configuration files
    sig { returns(Pathname) }
    attr_reader :cfgs_path

    # path to put generated files into
    sig { returns(Pathname) }
    attr_reader :gen_path

    # path to the standard specification
    sig { returns(Pathname) }
    attr_reader :std_path

    # path to custom overlay specifications
    sig { returns(Pathname) }
    attr_reader :custom_path

    # path to a python binary
    sig { returns(Pathname) }
    attr_reader :python_path

    # create a new resolver.
    #
    # With no arguments, resolver will assume it exists in the riscv-unified-db repository
    # and use standard paths
    #
    # If repo_root is given, use it as the path to a riscv-unified-db repository
    #
    # Any specific path can be overridden. If all paths are overridden, it doesn't matter what repo_root is.
    sig {
      params(
        repo_root: Pathname,
        schemas_path_override: T.nilable(Pathname),
        cfgs_path_override: T.nilable(Pathname),
        gen_path_override: T.nilable(Pathname),
        std_path_override: T.nilable(Pathname),
        custom_path_override: T.nilable(Pathname),
        python_path_override: T.nilable(Pathname)
      ).void
    }
    def initialize(
      repo_root = Udb.repo_root,
      schemas_path_override: nil,
      cfgs_path_override: nil,
      gen_path_override: nil,
      std_path_override: nil,
      custom_path_override: nil,
      python_path_override: nil
    )
      @repo_root = repo_root
      @schemas_path = schemas_path_override || (@repo_root / "spec" / "schemas")
      @cfgs_path = cfgs_path_override || (@repo_root / "cfgs")
      @gen_path = gen_path_override || (@repo_root / "gen")
      @std_path = std_path_override || (@repo_root / "spec" / "std" / "isa")
      @custom_path = custom_path_override || (@repo_root / "spec" / "custom" / "isa")
      @python_path = python_path_override || (@repo_root / ".home" / ".venv" / "bin" / "python3")

      FileUtils.mkdir_p @gen_path
    end

    # returns true if either +target+ does not exist, or if any of +deps+ are newer than +target+
    sig { params(target: Pathname, deps: T::Array[Pathname]).returns(T::Boolean) }
    def any_newer?(target, deps)
      if target.exist?
        deps.any? { |d| target.mtime < d.mtime }
      else
        true
      end
    end

    # run command in the shell. raise if exit is not zero
    sig { params(cmd: T::Array[String]).void }
    def run(cmd)
      puts cmd.join(" ")
      T.unsafe(self).send(:system, *cmd)
      raise unless $?.success?
    end

    # resolve config file and write it to gen_path
    # returns the config data
    sig { params(config_path: Pathname).returns(T::Hash[String, T.untyped]) }
    def resolve_config(config_path)
      config_yaml = T.nilable(T::Hash[String, T.untyped])
      config_name = config_path.basename(".yaml")

      # write the config with arch_overlay expanded
      if any_newer?(gen_path / "cfgs" / "#{config_name}.yaml", [config_path])
        config_yaml = YAML.load_file(config_path)

        # is there anything to do here? validate?

        FileUtils.mkdir_p gen_path / "cfgs"
        File.write(gen_path / "cfgs" / "#{config_name}.yaml", YAML.dump(config_yaml))
      else
        config_yaml = YAML.load_file(gen_path / "cfgs" / "#{config_name}.yaml")
      end

      config_yaml["$source"] = config_path.realpath
      config_yaml
    end

    sig { params(config_yaml: T::Hash[String, T.untyped]).void }
    def merge_arch(config_yaml)
      config_name = config_yaml["name"]

      deps = Dir[std_path / "**" / "*.yaml"].map { |p| Pathname.new(p) }
      deps += Dir[custom_path / config_yaml["arch_overlay"] / "**" / "*.yaml"].map { |p| Pathname.new(p) } unless config_yaml["arch_overlay"].nil?

      overlay_path =
        if config_yaml["arch_overlay"].nil?
          nil
        else
          if config_yaml.fetch("arch_overlay")[0] == "/"
            Pathname.new(config_yaml.fetch("arch_overlay"))
          else
            custom_path / config_yaml.fetch("arch_overlay")
          end
        end
      raise "custom directory '#{overlay_path}' does not exist" if !overlay_path.nil? && !overlay_path.directory?

      if any_newer?(gen_path / "spec" / config_name / ".stamp", deps)
        run [
          python_path.to_s,
          "#{Udb.gem_path}/python/yaml_resolver.py",
          "merge",
          std_path.to_s,
          overlay_path.nil? ? "/does/not/exist" : overlay_path.to_s,
          "#{gen_path}/spec/#{config_name}"
        ]
        FileUtils.touch(gen_path / "spec" / config_name / ".stamp")
      end
    end

    sig { params(config_yaml: T::Hash[String, T.untyped]).void }
    def resolve_arch(config_yaml)
      merge_arch(config_yaml)
      config_name = config_yaml["name"]

      deps = Dir[gen_path / "arch" / config_yaml["name"] / "**" / "*.yaml"].map { |p| Pathname.new(p) }
      if any_newer?(gen_path / "resolved_spec" / config_yaml["name"] / ".stamp", deps)
        run [
          python_path.to_s,
          "#{Udb.gem_path}/python/yaml_resolver.py",
          "resolve",
          "#{gen_path}/spec/#{config_name}",
          "#{gen_path}/resolved_spec/#{config_name}"
        ]
        FileUtils.touch(gen_path / "resolved_spec" / config_yaml["name"] / ".stamp")
      end
    end

    # resolve the specification for a config, and return a ConfiguredArchitecture
    sig { params(config_path_or_name: T.any(Pathname, String)).returns(Udb::ConfiguredArchitecture) }
    def cfg_arch_for(config_path_or_name)
      config_path =
        case config_path_or_name
        when Pathname
          raise "Path does not exist: #{config_path_or_name}" unless config_path_or_name.file?

          config_path_or_name
        when String
          @repo_root / "cfgs" / "#{config_path_or_name}.yaml"
        else
          T.absurd(config_path_or_name)
        end

      @cfg_archs ||= {}
      return @cfg_archs[config_path] if @cfg_archs.key?(config_path)

      config_yaml = resolve_config(config_path)
      config_name = config_yaml["name"]

      resolve_arch(config_yaml)

      @cfg_archs[config_path] = Udb::ConfiguredArchitecture.new(
        config_name,
        Udb::AbstractConfig.create(gen_path / "cfgs" / "#{config_name}.yaml"),
        gen_path / "resolved_spec" / config_name
      )
    end
  end
end
