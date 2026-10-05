# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "json"
require "json_schemer"
require "tmpdir"
require "yaml"

require "udb/logic"
require "udb/cfg_arch"
require "udb/resolver"
require "udb/obj/non_isa_specification"

class TestCfgArch < Minitest::Test
  include Udb

  SCHEMA_DIR = (Pathname.new(__dir__) / ".." / ".." / ".." / ".." / "spec" / "schemas").realpath
  CONFIG_SCHEMA_PATH = SCHEMA_DIR / "config_schema.json"

  def setup
    @gen_dir = Dir.mktmpdir
    @resolver = Udb::Resolver.new(
      Udb.repo_root,
      gen_path_override: Pathname.new(@gen_dir)
    )
    @config_schemer = JSONSchemer.schema(
      JSON.parse(File.read(CONFIG_SCHEMA_PATH)),
      ref_resolver: proc { |uri|
        data = JSON.parse(File.read(SCHEMA_DIR / File.basename(uri.path)))
        data["definitions"] = data["$defs"] if data["$defs"] && !data.key?("definitions")
        data
      }
    )
  end

  def teardown
    FileUtils.rm_rf @gen_dir
  end

  def test_invalid_partial_config
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32-bad
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
    end

    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32-bad2
      description: A generic RV32 system; only MXLEN is known
      params:
        MXLEN: 32
        CACHE_BLOCK_SIZE: 64

      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
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
      param_reasons = result.reasons.select { |r| r.include?("Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'") }
      assert_equal 1, param_reasons.size, "Expected exactly one reason about CACHE_BLOCK_SIZE"
      assert param_reasons.first.include?("Failing condition(s):"), "Expected failing conjuncts header in: #{param_reasons.first}"
      assert param_reasons.first.include?("  - "), "Expected at least one failing conjunct line in: #{param_reasons.first}"
      assert result.reasons.any? { |r| r =~ /Mandatory extension requirements conflict: This is not satisfiable: / }
    end
  end

  def test_implemented_extensions_hash_versions_match_schema
    info = Udb::Resolver::ConfigInfo.new(
      name: "test",
      path: Pathname.new("test.yaml"),
      overlay_path: nil,
      unresolved_yaml: {},
      spec_path: Pathname.new("spec"),
      merged_spec_path: Pathname.new("merged_spec"),
      resolved_spec_path: Pathname.new("resolved_spec"),
      resolver: @resolver
    )

    bare_cfg = Udb::AbstractConfig.create_from_data({
      "type" => "fully configured",
      "name" => "test",
      "params" => { "MXLEN" => 32 },
      "implemented_extensions" => [{ "name" => "I", "version" => "2.1" }]
    }, info)
    equal_cfg = Udb::AbstractConfig.create_from_data({
      "type" => "fully configured",
      "name" => "test",
      "params" => { "MXLEN" => 32 },
      "implemented_extensions" => [{ "name" => "I", "version" => "= 2.1" }]
    }, info)

    assert_equal [{ "name" => "I", "version" => "2.1" }], bare_cfg.implemented_extensions
    assert_equal [{ "name" => "I", "version" => "2.1" }], equal_cfg.implemented_extensions

    base_schema_data = {
      "$schema" => "config_schema.json#",
      "kind" => "architecture configuration",
      "type" => "fully configured",
      "name" => "test",
      "description" => "test",
      "params" => { "MXLEN" => 32 },
      "implemented_extensions" => [{ "name" => "I", "version" => "2.1" }]
    }
    assert_empty @config_schemer.validate(base_schema_data).to_a
    base_schema_data["implemented_extensions"][0]["version"] = "= 2.1"
    assert_empty @config_schemer.validate(base_schema_data).to_a
    base_schema_data["implemented_extensions"][0]["version"] = ">= 2.1"
    refute_empty @config_schemer.validate(base_schema_data).to_a

    assert_raises(ArgumentError) do
      Udb::AbstractConfig.create_from_data({
        "type" => "fully configured",
        "name" => "test",
        "params" => { "MXLEN" => 32 },
        "implemented_extensions" => [{ "name" => "I", "version" => ">= 2.1" }]
      }, info).implemented_extensions
    end
  end

  def test_invalid_full_config
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: fully configured
      name: rv32-bad
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
      assert_includes result.reasons, "Znotanextension is not a known extension"
      assert result.reasons.any? { |r| r.include?("0.1") && r.include?("is not a known version of extension") }, "Unknown version should be rejected"
      # ... and more, which are not being explictly checked because the above need resolved before they will print
      # assert_includes result.reasons, "Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'. Needs: (Zicbom>=0 || Zicbop>=0 || Zicboz>=0)"
      # assert_includes result.reasons, "Extension requirement is unmet: Zcmp@1.0.0. Needs: (Zca>=0 && !Zcd>=0)"
      # assert_includes result.reasons, "Parameter is required but missing: 'M_MODE_ENDIANNESS'"
      # assert_includes result.reasons, "Parameter is required but missing: 'PHYS_ADDR_WIDTH'"
      # assert_includes result.reasons, "Extension version has no definition: F@0.1.0"
      # assert_includes result.reasons, "Extension version has no definition: Znotanextension@1.0.0"
    end

    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: fully configured
      name: rv32-bad-version-only
      description: A generic RV32 system
      params:
        MXLEN: 32

      implemented_extensions:
        - [I, "9.9.9"]
    CFG

    Tempfile.create do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      assert result.reasons.any? { |r| r.include?("9.9.9") && r.include?("is not a known version of extension") }, "Unknown version should be rejected"
    end


    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: fully configured
      name: rv32-bad2
      description: A generic RV32 system
      params:

        MXLEN: 32
        CACHE_BLOCK_SIZE: 64

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
      assert result.reasons.any? { |r| r =~ /Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'/ }, "Parameter CACHE_BLOCK_SIZE should not be allowed"
      assert result.reasons.any? { |r| r =~ /Extension requirement is unmet: Zcmp@1\.0\.0/ }, "Zcmp requirements haven't been met, but the config does't pick that up"
      assert_includes result.reasons, "Parameter is required but missing: 'M_MODE_ENDIANNESS'"
      assert_includes result.reasons, "Parameter is required but missing: 'PHYS_ADDR_WIDTH'"
      # ... plus more
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

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)

      cfg_arch.type_check(show_progress: true)

      assert_equal cfg_arch.config.param_values.size, cfg_arch.params_with_value.size

      total_params = cfg_arch.params_with_value.size + cfg_arch.params_without_value.size + cfg_arch.out_of_scope_params.size
      assert_equal cfg_arch.params.size, total_params

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
    cfg = <<~YAML
      ---
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv64_no32
      description: A generic RV64 system, no RV32 possible
      params:
        MXLEN: 64
        SXLEN: [64]
        UXLEN: [64]
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
      prohibited_extensions:
        - name: H
          version: ">= 0"
    YAML
    cfg_arch = nil

    Tempfile.create do |f|
      f.write cfg
      f.flush
      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
    end

    refute Udb::Condition.new({ "xlen" => 32 }, cfg_arch).satisfiable_by_cfg_arch?(cfg_arch)
    assert Udb::Condition.new({ "xlen" => 64 }, cfg_arch).satisfiable_by_cfg_arch?(cfg_arch)

    # make sure that RV32-only extensions are not possible
    refute_includes cfg_arch.possible_extension_versions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zilsd"
    refute_includes cfg_arch.possible_extensions.map(&:name), "Zclsd"

  end

  def test_transitive_full

    cfg_arch = @resolver.cfg_arch_for("rv64")

    assert_equal cfg_arch.extension_version("C", "2.0.0"), cfg_arch.extension_version("C", "2.0.0")
    assert cfg_arch.extension_version("C", "2.0.0").eql?(cfg_arch.extension_version("C", "2.0.0"))
    assert_equal cfg_arch.extension_version("C", "2.0.0").hash, cfg_arch.extension_version("C", "2.0.0").hash

    assert_equal \
      [
        cfg_arch.extension_version("C", "2.0.0"),
        cfg_arch.extension_version("Zca", "1.0.0"),
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          cfg_arch.extension_version("C", "2.0.0")
        ]
      ).sort

    assert_equal \
      [
        cfg_arch.extension_version("C", "2.0.0"),
        cfg_arch.extension_version("F", "2.2.0"),
        cfg_arch.extension_version("Zca", "1.0.0"),
        cfg_arch.extension_version("Zcf", "1.0.0"),
        cfg_arch.extension_version("Zicsr", "2.0.0")
      ],
      [
        cfg_arch.extension_version("C", "2.0.0"),
        cfg_arch.extension_version("F", "2.2.0"),
        cfg_arch.extension_version("Zca", "1.0.0"),
        cfg_arch.extension_version("Zcf", "1.0.0"),
        cfg_arch.extension_version("Zicsr", "2.0.0")
    ].uniq

    assert_equal \
      [
        cfg_arch.extension_version("C", "2.0.0"),
        cfg_arch.extension_version("F", "2.2.0"),
        cfg_arch.extension_version("Zca", "1.0.0"),
        cfg_arch.extension_version("Zicsr", "2.0.0")
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          cfg_arch.extension_version("C", "2.0.0"),
          cfg_arch.extension_version("F", "2.2.0")
        ]
      ).sort

    assert_equal \
      [
        cfg_arch.extension_version("C", "2.0.0"),
        cfg_arch.extension_version("D", "2.2.0"),
        cfg_arch.extension_version("F", "2.2.0"),
        cfg_arch.extension_version("Zca", "1.0.0"),
        cfg_arch.extension_version("Zcd", "1.0.0"),
        cfg_arch.extension_version("Zicsr", "2.0.0")
      ],
      cfg_arch.expand_implemented_extension_list(
        [
          cfg_arch.extension_version("C", "2.0.0"),
          cfg_arch.extension_version("D", "2.2.0")
        ]
      ).sort
  end

  def test_xqci

    cfg_arch = @resolver.cfg_arch_for("qc_iu")

    exts = [
      cfg_arch.extension("Xqci"),
      cfg_arch.extension("Xqcia"),
      cfg_arch.extension("Xqciac"),
      cfg_arch.extension("Xqcibi"),
      cfg_arch.extension("Xqcibm"),
      cfg_arch.extension("Xqcicli"),
      cfg_arch.extension("Xqcicm"),
      cfg_arch.extension("Xqcics"),
      cfg_arch.extension("Xqcicsr"),
      cfg_arch.extension("Xqciint"),
      cfg_arch.extension("Xqciio"),
      cfg_arch.extension("Xqcilb"),
      cfg_arch.extension("Xqcili"),
      cfg_arch.extension("Xqcilia"),
      cfg_arch.extension("Xqcilo"),
      cfg_arch.extension("Xqcilsm"),
      cfg_arch.extension("Xqcisim"),
      cfg_arch.extension("Xqcisls"),
      cfg_arch.extension("Xqcisync")
    ]

    assert_equal 11, cfg_arch.extension("Xqcia").max_version.directly_defined_instructions.size
    assert_equal 157, cfg_arch.extension("Xqci").max_version.implied_instructions.count { |i| exts.any? { |e| i.defined_by_condition.mentions?(e) } }
  end

  def test_full_config_extension_requirement_failure_reports_failing_conjuncts
    # Zcd requires D, but D is not in the config — verify the error uses failing_conjuncts format
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: fully configured
      name: rv32-zcd-no-d
      description: A config with Zcd but without D
      params:
        MXLEN: 32
        TRAP_ON_EBREAK: true
        TRAP_ON_ECALL_FROM_M: true
        TRAP_ON_ILLEGAL_WLRL: true
        TRAP_ON_RESERVED_INSTRUCTION: true
        TRAP_ON_UNIMPLEMENTED_CSR: true
        TRAP_ON_UNIMPLEMENTED_INSTRUCTION: true
        M_MODE_ENDIANNESS: little
        PHYS_ADDR_WIDTH: 32

      implemented_extensions:
        - [I, "2.1.0"]
        - [Sm, "1.13.0"]
        - [C, "2.0.0"]
        - [Zca, "1.0.0"]
        - [Zcd, "1.0.0"]
    CFG

    Tempfile.create(%w/cfg .yaml/) do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      unmet = result.reasons.select { |r| r.include?("Extension requirement is unmet: Zcd@") }
      assert_equal 1, unmet.size, proc { "Expected exactly one unmet-extension reason for Zcd. Got: \n #{unmet}" }
      assert unmet.first.include?("Failing condition(s):"), "Expected failing conjuncts header in: #{unmet.first}"
      assert unmet.first.include?("  - "), "Expected at least one failing conjunct line in: #{unmet.first}"
    end
  end

  def test_partial_config_parameter_defined_by_reports_failing_conjuncts
    # rv32-bad2 config has CACHE_BLOCK_SIZE but no Zicbom/Zicbop/Zicboz — verify failing_conjuncts format
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32-bad2
      description: A generic RV32 system; only MXLEN is known
      params:
        MXLEN: 32
        CACHE_BLOCK_SIZE: 64

      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
        - name: Zcd
          version: ">= 0"
        - name: Zcmp
          version: ">= 0"
    CFG

    Tempfile.create(%w/cfg .yaml/) do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      param_reasons = result.reasons.select { |r| r.include?("Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'") }
      assert_equal 1, param_reasons.size, "Expected exactly one reason about CACHE_BLOCK_SIZE"
      assert param_reasons.first.include?("Failing condition(s):"), "Expected failing conjuncts header in: #{param_reasons.first}"
      assert param_reasons.first.include?("  - "), "Expected at least one failing conjunct line in: #{param_reasons.first}"
    end
  end

  def test_partial_config_parameter_defined_by_unknown_terms
    # When the defining extensions are possible but not mandatory, terms show as {unknown}.
    # failing_conjuncts should still return the whole unsatisfied clause (not an empty list),
    # so the error message remains actionable.
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: rv32-maybe-cache
      description: I+Sm only; Zicbom/Zicbop/Zicboz are possible but not mandatory
      params:
        MXLEN: 32
        CACHE_BLOCK_SIZE: 64

      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    CFG

    Tempfile.create(%w/cfg .yaml/) do |f|
      f.write cfg
      f.flush

      cfg_arch = @resolver.cfg_arch_for(Pathname.new f.path)
      result = cfg_arch.valid?

      refute result.valid
      param_reasons = result.reasons.select { |r| r.include?("Parameter is not defined by this config: 'CACHE_BLOCK_SIZE'") }
      assert_equal 1, param_reasons.size, "Expected exactly one reason about CACHE_BLOCK_SIZE"
      # The message must still have a bullet line — not an empty list — even though terms are unknown
      assert param_reasons.first.include?("  - "), "Expected at least one failing conjunct line even with unknown terms"
      # The bullet should contain {unknown} annotations, not {false}, since the extensions are possible
      assert param_reasons.first.include?("{unknown}"), "Expected {unknown} annotations for possible-but-not-mandatory extensions"
    end
  end

  def test_compatible
    base_64_yaml = <<~YAML
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: compat_test_base_64
      description: Base 64-bit config for compatibility tests
      params:
        MXLEN: 64
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    YAML

    compat_64_yaml = <<~YAML
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: compat_test_compat_64
      description: Compatible 64-bit config
      params:
        MXLEN: 64
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
        - name: "M"
          version: ">= 0"
    YAML

    incompat_32_yaml = <<~YAML
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: compat_test_incompat_32
      description: Incompatible 32-bit config (MXLEN conflict)
      params:
        MXLEN: 32
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    YAML

    also_compat_64_yaml = <<~YAML
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: compat_test_also_compat_64
      description: Another compatible 64-bit config
      params:
        MXLEN: 64
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    YAML

    Tempfile.create(%w/compat_64 .yaml/) do |compat_64_file|
      compat_64_file.write(compat_64_yaml)
      compat_64_file.flush

      Tempfile.create(%w/incompat_32 .yaml/) do |incompat_32_file|
        incompat_32_file.write(incompat_32_yaml)
        incompat_32_file.flush

        Tempfile.create(%w/also_compat_64 .yaml/) do |also_compat_64_file|
          also_compat_64_file.write(also_compat_64_yaml)
          also_compat_64_file.flush

          # 1. Valid single compatible pointer
          Tempfile.create(%w/cfg .yaml/) do |f|
            f.write(base_64_yaml.sub("mandatory_extensions:", "compatible: #{compat_64_file.path}\nmandatory_extensions:"))
            f.flush
            result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
            assert result.valid, "Expected valid for compatible with matching MXLEN, got: #{result.reasons}"
          end

          # Name-based pointer: use a known repo config name (no '/' → name lookup branch)
          Tempfile.create(%w/cfg .yaml/) do |f|
            f.write(base_64_yaml.sub("mandatory_extensions:", "compatible: rv64\nmandatory_extensions:"))
            f.flush
            result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
            assert result.valid,
              "Expected valid when compatible pointer is the known config name 'rv64', got: #{result.reasons}"
          end

          # Relative-path pointer: reference the compatible config via a relative path
          Dir.mktmpdir do |dir|
            dir_path = Pathname.new(dir)
            rel_compat_path = dir_path / "compat_64.yaml"
            rel_compat_path.write(compat_64_yaml)

            cfg_path = dir_path / "cfg.yaml"
            cfg_path.write(base_64_yaml.sub("mandatory_extensions:", "compatible: ./compat_64.yaml\nmandatory_extensions:"))

            result = @resolver.cfg_arch_for(cfg_path).valid?
            assert result.valid,
              "Expected valid when compatible pointer is a relative path './compat_64.yaml', got: #{result.reasons}"
          end

          # 2. Invalid single compatible pointer
          Tempfile.create(%w/cfg .yaml/) do |f|
            f.write(base_64_yaml.sub("mandatory_extensions:", "compatible: #{incompat_32_file.path}\nmandatory_extensions:"))
            f.flush
            result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
            refute result.valid, "Expected invalid for compatible with conflicting MXLEN"
            assert result.reasons.any? { |r| r.include?("not compatible with") },
              "Expected 'not compatible with' in reasons, got: #{result.reasons}"
          end

          # 3. Valid multiple compatible pointers (non-overlapping)
          Tempfile.create(%w/cfg .yaml/) do |f|
            f.write(base_64_yaml.sub("mandatory_extensions:", "compatible:\n  - #{compat_64_file.path}\n  - #{also_compat_64_file.path}\nmandatory_extensions:"))
            f.flush
            result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
            assert result.valid, "Expected valid for compatible with multiple matching configs, got: #{result.reasons}"
          end

          # 4. Invalid multiple compatible pointers (one incompatible)
          Tempfile.create(%w/cfg .yaml/) do |f|
            f.write(base_64_yaml.sub("mandatory_extensions:", "compatible:\n  - #{compat_64_file.path}\n  - #{incompat_32_file.path}\nmandatory_extensions:"))
            f.flush
            result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
            refute result.valid, "Expected invalid when one of multiple compatible configs conflicts"
            assert result.reasons.any? { |r| r.include?("not compatible with") },
              "Expected 'not compatible with' in reasons, got: #{result.reasons}"
          end

          # 5. Valid transitive compatible (base_64 -> transitive_b -> compat_64, all satisfiable)
          transitive_compat_b_yaml = <<~YAML
            $schema: config_schema.json#
            kind: architecture configuration
            type: partially configured
            name: compat_test_transitive_compat_b
            description: Transitive-compatible 64-bit config
            compatible: #{compat_64_file.path}
            params:
              MXLEN: 64
            mandatory_extensions:
              - name: "I"
                version: ">= 0"
              - name: "Sm"
                version: ">= 0"
              - name: "M"
                version: ">= 0"
          YAML
          Tempfile.create(%w/transitive_compat_b .yaml/) do |trans_compat_file|
            trans_compat_file.write(transitive_compat_b_yaml)
            trans_compat_file.flush

            Tempfile.create(%w/cfg .yaml/) do |f|
              f.write(base_64_yaml.sub("mandatory_extensions:", "compatible: #{trans_compat_file.path}\nmandatory_extensions:"))
              f.flush
              result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
              assert result.valid, "Expected valid for transitive compatible chain where all are satisfiable, got: #{result.reasons}"
            end
          end

          # 6. Invalid transitive compatible (base_64 -> transitive_b -> incompat_32, unsatisfiable transitively)
          transitive_incompat_b_yaml = <<~YAML
            $schema: config_schema.json#
            kind: architecture configuration
            type: partially configured
            name: compat_test_transitive_incompat_b
            description: Config that is directly compatible with base_64 but transitively points to an incompatible config
            compatible: #{incompat_32_file.path}
            params:
              MXLEN: 64
            mandatory_extensions:
              - name: "I"
                version: ">= 0"
              - name: "Sm"
                version: ">= 0"
              - name: "M"
                version: ">= 0"
          YAML
          Tempfile.create(%w/transitive_incompat_b .yaml/) do |trans_incompat_file|
            trans_incompat_file.write(transitive_incompat_b_yaml)
            trans_incompat_file.flush

            Tempfile.create(%w/cfg .yaml/) do |f|
              f.write(base_64_yaml.sub("mandatory_extensions:", "compatible: #{trans_incompat_file.path}\nmandatory_extensions:"))
              f.flush
              result = @resolver.cfg_arch_for(Pathname.new(f.path)).valid?
              refute result.valid, "Expected invalid for transitive chain that leads to an incompatible config"
              assert result.reasons.any? { |r| r.include?("not compatible with") },
                "Expected 'not compatible with' in reasons, got: #{result.reasons}"
            end
          end

        end
      end
    end
  end

  def test_march_string_rv64_base
    cfg_arch = @resolver.cfg_arch_for("rv64")
    march = cfg_arch.march_string
    assert_includes march, "rv64i"
    refute_includes march, "Sm"
  end

  def test_march_string_rv32_base
    cfg_arch = @resolver.cfg_arch_for("rv32")
    march = cfg_arch.march_string
    assert_includes march, "rv32i"
  end

  def test_march_string_partial_config
    cfg_arch = @resolver.cfg_arch_for("rv64")
    refute cfg_arch.fully_configured?
    march = cfg_arch.march_string
    assert_equal "rv64i", march
  end

  def test_march_string_single_letter_canonical_ordering
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march = cfg_arch.march_string
    assert_match(/^rv32imc/, march)
    refute_includes march, "Sm"
  end

  def test_march_string_multi_letter_z_extensions
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march = cfg_arch.march_string
    assert_includes march, "_zca_zicntr_zicsr"
  end

  def test_march_string_include_non_isa
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march_non_isa = cfg_arch.march_string(include_non_isa: true)
    assert_includes march_non_isa, "sm"
  end

  def test_march_string_include_versions
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march_ver = cfg_arch.march_string(include_versions: true)
    assert_match(/i2p1/, march_ver)
    assert_match(/_zca1p0/, march_ver)
  end

  def test_march_string_with_versions_and_non_isa
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march_all = cfg_arch.march_string(include_versions: true, include_non_isa: true)
    assert_match(/sm1p11/, march_all)
    assert_match(/i2p1/, march_all)
  end
end
