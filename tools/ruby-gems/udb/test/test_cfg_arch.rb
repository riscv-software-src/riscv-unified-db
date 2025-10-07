# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "fileutils"
require "tmpdir"
require "yaml"

require "minitest/autorun"
require "udb/logic"
require "udb/cfg_arch"
require "udb/resolver"

class TestCfgArch < Minitest::Test
  include Udb

  def setup
    @gen_dir = Dir.mktmpdir
    @resolver = Udb::Resolver.new(
      Udb.repo_root,
      gen_path_override: @gen_path
    )
  end

  def teardown
    FileUtils.rm_rf @gen_dir
  end


  def test_cfg_arch_properties
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32
      description: A generic RV32 system; only MXLEN is known
      params:
        MXLEN: 32
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    CFG

    Tempfile.create(%w/cfg .yaml/) do |f|
      f.write cfg
      f.flush

      puts "creating cfg_arch"
      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      puts "done"

      puts "type checking"
      cfg_arch.type_check(show_progress: true)
      puts "done"

      puts "checking params"
      assert_equal cfg_arch.config.param_values.size, cfg_arch.params_with_value.size

      total_params = cfg_arch.params_with_value.size + cfg_arch.params_without_value.size + cfg_arch.out_of_scope_params.size
      assert_equal cfg_arch.params.size, total_params
      puts "done"

      puts "checking extensions"
      if cfg_arch.fully_configured?
        assert_equal cfg_arch.config.implemented_extensions.size, cfg_arch.explicitly_implemented_extensions.size
        assert cfg_arch.config.implemented_extensions.size <= cfg_arch.transitive_implemented_extensions.size
        assert cfg_arch.config.implemented_extensions.size <= cfg_arch.implemented_extensions.size
      elsif cfg_arch.partially_configured?
        mandatory = cfg_arch.mandatory_extension_reqs
        mandatory.each do |ext_req|
          assert ext_req.to_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
        end
      end
      puts "done"

      possible = cfg_arch.possible_extension_versions

      possible.each do |ext_ver|
        assert ext_ver.to_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
      end

      cfg_arch.not_prohibited_extensions.each do |ext|
        assert \
          ext.versions.any? do |ext_ver|
            ext_ver.to_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
          end
      end

      cfg_arch.transitive_prohibited_extension_versions.each do |ext_ver|
        refute ext_ver.to_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
        assert cfg_arch.prohibited_ext?(ext_ver)
        assert cfg_arch.prohibited_ext?(ext_ver.name)
        assert cfg_arch.prohibited_ext?(ext_ver.name.to_s)
      end
    end
  end

  def test_transitive
    cfg_arch = @resolver.cfg_arch_for("rv64")

    # make that RV32-only extensions are not possible
    refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zclsd"

  end

  def test_transitive_full
    # cfg = <<~CFG
    #   $schema: config_schema.json#
    #   kind: architecture configuration
    #   type: fully configured
    #   name: test
    #   description: test for transitivity
    #   params:
    #     MXLEN: 32
    #   implemented_extensions:
    #     - [ "C", "= 2.0.0" ]
    # CFG

    # Tempfile.create(%w/cfg .yaml/) do |f|
    #   f.write cfg
    #   f.flush

    #   cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)

    #   assert_includes cfg_arch.possible_extension_versions.map(&:name), "C"
    #   assert_includes cfg_arch.possible_extension_versions.map(&:name), "Zca"
    #   refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zcf"
    #   refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zcd"
    # end

    cfg_arch = @resolver.cfg_arch_for("rv64")

    # puts cfg_arch.expand_implemented_extension_list(
    #     [
    #       ExtensionVersion.new("C", "2.0.0", cfg_arch),
    #       ExtensionVersion.new("D", "2.2.0", cfg_arch)
    #     ]
    #   )

    assert_equal \
      [
        ExtensionVersion.new("C", "2.0.0", cfg_arch),
        ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          ExtensionVersion.new("C", "2.0.0", cfg_arch)
        ]
      ).sort

    assert_equal \
      [
        ExtensionVersion.new("C", "2.0.0", cfg_arch),
        ExtensionVersion.new("F", "2.2.0", cfg_arch),
        ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcf", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zicsr", "2.0.0", cfg_arch)
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          ExtensionVersion.new("C", "2.0.0", cfg_arch),
          ExtensionVersion.new("F", "2.2.0", cfg_arch)
        ]
      ).sort

    assert_equal \
      [
        ExtensionVersion.new("C", "2.0.0", cfg_arch),
        ExtensionVersion.new("D", "2.2.0", cfg_arch),
        ExtensionVersion.new("F", "2.2.0", cfg_arch),
        ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcd", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcf", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zicsr", "2.0.0", cfg_arch)
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          ExtensionVersion.new("C", "2.0.0", cfg_arch),
          ExtensionVersion.new("D", "2.2.0", cfg_arch)
        ]
      ).sort

    assert_equal \
      [
        ExtensionVersion.new("C", "2.0.0", cfg_arch),
        ExtensionVersion.new("D", "2.2.0", cfg_arch),
        ExtensionVersion.new("F", "2.2.0", cfg_arch),
        ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcd", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcf", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zicsr", "2.0.0", cfg_arch)
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
          ExtensionVersion.new("Zcf", "1.0.0", cfg_arch),
          ExtensionVersion.new("Zcd", "1.0.0", cfg_arch)
        ]
      ).sort

    # cfg = <<~CFG
    #   $schema: config_schema.json#
    #   kind: architecture configuration
    #   type: fully configured
    #   name: test
    #   description: test for transitivity
    #   params:
    #     MXLEN: 32
    #     PHYS_ADDR_WIDTH: 32
    #   implemented_extensions:
    #     - [ "C", "= 2.0.0" ]
    #     - [ "F", "= 2.2.0" ]
    # CFG

    # Tempfile.create(%w/cfg .yaml/) do |f|
    #   f.write cfg
    #   f.flush

    #   cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)

    #   puts cfg_arch.possible_extension_versions.map(&:name)
    #   assert_includes cfg_arch.possible_extension_versions.map(&:name), "C"
    #   assert_includes cfg_arch.possible_extension_versions.map(&:name), "Zca"
    #   assert_includes cfg_arch.possible_extension_versions.map(&:name), "Zcf"
    #   refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zcd"
    # end
  end
end
