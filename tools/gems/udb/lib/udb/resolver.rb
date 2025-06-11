# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

require "bundler"
require "sorbet-runtime"

require_relative "cfg_arch"

module Udb
  extend T::Sig

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
  def self.default_arch_isa_path
    repo_root / "data" / "arch" / "isa"
  end

  sig { returns(Pathname) }
  def self.default_arch_overlay_isa_path
    repo_root / "data" / "arch_overlay" / "isa"
  end

  sig { returns(Pathname) }
  def self.default_gen_path
    repo_root / "gen"
  end

  sig { returns(Pathname) }
  def self.default_cfgs_path
    repo_root / "cfgs"
  end


  class Resolver
    extend T::Sig

    sig {
      params(repo_root: T.nilable(Pathname)).void
    }
    def initialize(repo_root = nil)
      @repo_root = repo_root || Udb.repo_root
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
    sig { params(cmd: String).void }
    def run(cmd)
      puts cmd
      system cmd
      raise unless $?.success?
    end

    # resolve config file and write it to gen_path
    # returns the config data
    sig {
      params(
        config_path: Pathname,
        gen_path: Pathname,
        arch_path: Pathname,
        arch_overlay_path: Pathname,
      ).returns(T::Hash[String, T.untyped])
    }
    def resolve_config(
      config_path,
      gen_path: @repo_root / "gen",
      arch_path: @repo_root / "data" / "arch" / "isa",
      arch_overlay_path: @repo_root / "data" / "arch_overlay" / "isa"
    )
      config_yaml = T.nilable(T::Hash[String, T.untyped])
      config_name = config_path.basename(".yaml")

      # write the config with arch_overlay expanded
      if any_newer?(gen_path / "cfgs" / "#{config_name}.yaml", [config_path])
        config_yaml = YAML.load_file(config_path)
        FileUtils.mkdir_p gen_path / "cfgs"
        if config_yaml["arch_overlay"].nil?
          config_yaml["arch_overlay"] = "/does/not/exist"
        else
          unless config_yaml["arch_overlay"][0] == "/"
            # expand to an absolute path
            config_yaml["arch_overlay"] = (arch_overlay_path / config_yaml["arch_overlay"]).to_s
          end

          raise "Cannot determine arch_overlay path" unless File.directory?(config_yaml["arch_overlay"])
        end
        File.write(gen_path / "cfgs" / "#{config_name}.yaml", YAML.dump(config_yaml))
      else
        config_yaml = YAML.load_file(gen_path / "cfgs" / "#{config_name}.yaml")
      end

      config_yaml["$source"] = config_path.realpath
      config_yaml
    end

    sig do
      params(
        config_yaml: T::Hash[String, T.untyped],
        gen_path: Pathname,
        arch_path: Pathname,
        arch_overlay_path: Pathname,
        python_path: Pathname
      ).void
    end
    def merge_arch(
      config_yaml,
      gen_path: @repo_root / "gen",
      arch_path: @repo_root / "data" / "arch" / "isa",
      arch_overlay_path: @repo_root / "data" / "arch_overlay" / "isa",
      python_path: @repo_root / ".home" / ".venv" / "bin" / "python3"
    )
      config_name = config_yaml["name"]

      deps = Dir[arch_path / "**" / "*.yaml"].map { |p| Pathname.new(p) }
      deps += Dir[arch_overlay_path / config_yaml["arch_overlay"] / "**" / "*.yaml"].map { |p| Pathname.new(p) } unless config_yaml["arch_overlay"].nil?

      if any_newer?(gen_path / "arch" / config_name / ".stamp", deps)
        udb_gem_path = Bundler.definition.specs.find { |s| s.name == "udb" }.full_gem_path
        run "#{python_path} #{udb_gem_path}/python/yaml_resolver.py merge #{arch_path} #{config_yaml["arch_overlay"]} #{gen_path}/arch/#{config_name}"
        FileUtils.touch(gen_path / "arch" / config_name / ".stamp")
      end
    end

    sig {
      params(
        config_yaml: T::Hash[String, T.untyped],
        gen_path: Pathname,
        arch_path: Pathname,
        arch_overlay_path: Pathname,
        python_path: Pathname
      ).void
    }
    def resolve_arch(
      config_yaml,
      gen_path: @repo_root / "gen",
      arch_path: @repo_root / "data" / "arch" / "isa",
      arch_overlay_path: @repo_root / "data" / "arch_overlay" / "isa",
      python_path: @repo_root / ".home" / ".venv" / "bin" / "python3"
    )
      merge_arch(config_yaml, gen_path:, arch_path:, arch_overlay_path:, python_path:)
      config_name = config_yaml["name"]

      deps = Dir[gen_path / "arch" / config_yaml["name"] / "**" / "*.yaml"].map { |p| Pathname.new(p) }
      if any_newer?(gen_path / "resolved_arch" / config_yaml["name"] / ".stamp", deps)
        udb_gem_path = Bundler.definition.specs.find { |s| s.name == "udb" }.full_gem_path
        run "#{python_path} #{udb_gem_path}/python/yaml_resolver.py resolve #{gen_path}/arch/#{config_name} #{gen_path}/resolved_arch/#{config_name}"
        FileUtils.touch(gen_path / "resolved_arch" / config_yaml["name"] / ".stamp")
      end
    end

    sig {
      params(
        config_path_or_name: T.any(Pathname, String),
        gen_path: Pathname,
        arch_path: Pathname,
        arch_overlay_path: Pathname
      ).returns(Udb::ConfiguredArchitecture)
    }
    def cfg_arch_for(
      config_path_or_name,
      gen_path: @repo_root / "gen",
      arch_path: @repo_root / "data" / "arch" / "isa",
      arch_overlay_path: @repo_root / "data" / "arch_overlay" / "isa"
    )
      config_path =
        case config_path_or_name
        when Pathname
          config_path_or_name
        when String
          @repo_root / "cfgs" / "#{config_path_or_name}.yaml"
        else
          T.absurd(config_path_or_name)
        end

      @cfg_archs ||= {}
      return @cfg_archs[config_path] if @cfg_archs.key?(config_path)

      config_yaml = resolve_config(config_path, gen_path:, arch_path:, arch_overlay_path:)
      config_name = config_yaml["name"]

      resolve_arch(config_yaml)

      @cfg_archs[config_path] = Udb::ConfiguredArchitecture.new(
        config_name,
        Udb::FileConfig.create(gen_path / "cfgs" / "#{config_name}.yaml"),
        gen_path / "resolved_arch" / config_name
      )
    end
  end
end
