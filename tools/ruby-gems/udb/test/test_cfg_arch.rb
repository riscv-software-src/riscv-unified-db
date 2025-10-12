# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "tmpdir"
require "yaml"

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

  # make sure all the configs in the repo are valid
  Dir[Udb.repo_root / "cfgs" / "*.yaml"].each do |cfg_path|
    define_method "test_cfg_#{File.basename(cfg_path, ".yaml")}_valid" do
      cfg_arch = @resolver.cfg_arch_for(Pathname.new cfg_path)
      assert cfg_arch.valid?, <<~MSG
        Config '#{File.basename(cfg_path, ".yaml")}' is not valid.
        To see why, run `./bin/udb validate cfg #{cfg_path}`
      MSG
    end
  end

  def test_invalid_partial_config
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32
      description: A generic RV32 system; only MXLEN is known
      params:
        MXLEN: 31
        NOT_A: false
        CACHE_BLOCK_SIZE: 64

      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
        - name: Znotanextension
          version: ">= 0"
        - name: D
          version: "= 50"
        - name: Zcd
          version: ">= 0"
        - name: Zcmp
          version: ">= 0"
    CFG

    Tempfile.create do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      assert_includes result.reasons, "Extension requirement can never be met (no match in the database): Znotanextension "
      assert_includes result.reasons, "Extension requirement can never be met (no match in the database): D = 50"
      assert_includes result.reasons, "Parameter value violates the schema: 'MXLEN' = '31'"
      assert_includes result.reasons, "Parameter has no definition: 'NOT_A'"
      assert_includes result.reasons, "Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'. Needs (Zicbom>=0 || Zicbop>=0 || Zicboz>=0)"
      assert_includes result.reasons, "Mandatory extension requirements conflict: This is not satisfiable: (Zcd=1.0.0 && Zcmp=1.0.0 && (!Zcmp=1.0.0 || !Zcd=1.0.0))"
      assert_equal 6, result.reasons.size, <<~MSG
        There are unexpected reasons in:

        #{result.reasons.join("\n")}
      MSG
    end
  end

  def test_invalid_full_config
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: fully configured
      name: rv32
      description: A generic RV32 system
      params:

        # bad params
        MXLEN: 31
        NOT_A: false
        CACHE_BLOCK_SIZE: 64

        # good params
        TRAP_ON_EBREAK: true
        TRAP_ON_ECALL_FROM_M: true
        TRAP_ON_ILLEGAL_WLRL: true
        TRAP_ON_RESERVED_INSTRUCTION: true
        TRAP_ON_UNIMPLEMENTED_CSR: true
        TRAP_ON_UNIMPLEMENTED_INSTRUCTION: true

      implemented_extensions:
        - [I, "2.1.0"]
        - [Sm, "1.13.0"]
        - [C, "2.0.0"]
        - [Zca, "1.0.0"]

        # should fail; not a real extension
        - [Znotanextension, "1.0.0"]

        # should cause validation error: Not a known version of F
        - [F, "0.1"]

        # should cause validation error: Zcd requires D
        - [Zcd, "1.0.0"]

        # should cause validation error: Zcmp condlicts with Zcd
        - [Zcmp, "1.0.0"]
    CFG

    Tempfile.create do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      assert_includes result.reasons, "Parameter value violates the schema: 'MXLEN' = '31'"
      assert_includes result.reasons, "Parameter has no definition: 'NOT_A'"
      assert_includes result.reasons, "Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'. Needs: (Zicbom>=0 || Zicbop>=0 || Zicboz>=0)"
      assert_includes result.reasons, "Extension requirement is unmet: Zcmp@1.0.0. Needs: (Zca>=0 && !Zcd>=0)"
      assert_includes result.reasons, "Parameter is required but missing: 'M_MODE_ENDIANNESS'"
      assert_includes result.reasons, "Parameter is required but missing: 'PHYS_ADDR_WIDTH'"
      assert_includes result.reasons, "Extension version has no definition: F@0.1.0"
      assert_includes result.reasons, "Extension version has no definition: Znotanextension@1.0.0"
      # ... and more, which are not being explictly checked ...
    end
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
        assert cfg_arch.config.implemented_extensions.size <= cfg_arch.implemented_extensions.size
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

      cfg_arch.prohibited_extension_versions.each do |ext_ver|
        refute ext_ver.to_condition.could_be_satisfied_by_cfg_arch?(cfg_arch)
        assert cfg_arch.prohibited_ext?(ext_ver)
        assert cfg_arch.prohibited_ext?(ext_ver.name)
        assert cfg_arch.prohibited_ext?(ext_ver.name.to_s)
      end
    end
  end

  def test_transitive
    cfg_arch = @resolver.cfg_arch_for("rv64")

    # make sure that RV32-only extensions are not possible
    refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zclsd"

  end

  def test_transitive_full

    cfg_arch = @resolver.cfg_arch_for("rv64")

    assert_equal ExtensionVersion.new("C", "2.0.0", cfg_arch), ExtensionVersion.new("C", "2.0.0", cfg_arch)
    assert ExtensionVersion.new("C", "2.0.0", cfg_arch).eql?(ExtensionVersion.new("C", "2.0.0", cfg_arch))
    assert_equal ExtensionVersion.new("C", "2.0.0", cfg_arch).hash, ExtensionVersion.new("C", "2.0.0", cfg_arch).hash

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
      [
        ExtensionVersion.new("C", "2.0.0", cfg_arch),
        ExtensionVersion.new("F", "2.2.0", cfg_arch),
        ExtensionVersion.new("Zca", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zcf", "1.0.0", cfg_arch),
        ExtensionVersion.new("Zicsr", "2.0.0", cfg_arch)
    ].uniq

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
  end
end
