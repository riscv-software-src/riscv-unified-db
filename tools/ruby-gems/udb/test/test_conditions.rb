# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "fileutils"
require "tmpdir"
require "yaml"

require "minitest/autorun"
require "udb/condition"
require "udb/resolver"

class TestConditions < Minitest::Test
  def setup
    @udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @gen_path = Pathname.new(Dir.mktmpdir)
    resolver = Udb::Resolver.new(
      schemas_path_override: @udb_gem_root / "schemas",
      cfgs_path_override: @udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @gen_path,
      std_path_override: @udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: true
    )
    capture_io do
      @cfg_arch = resolver.cfg_arch_for("_")
    end
  end

  def teardown
    FileUtils.rm_rf @gen_path
  end

  def test_single_extension_req
    cond_str = <<~COND
      extension:
        name: A
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Udb::Condition.new(cond_yaml, @cfg_arch)

    assert_equal Udb::SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 1, tree.terms.size
    assert_equal Udb::ExtensionRequirement.new("A", ">= 0", arch: @cfg_arch), tree.terms[0]
    assert tree.eval(@cfg_arch.symtab, [Udb::ExtensionVersion.new("A", "1.0", @cfg_arch)])
    refute tree.eval(@cfg_arch.symtab, [Udb::ExtensionVersion.new("B", "2.1.0", @cfg_arch)])
    assert_equal "(A >= 0)", tree.to_s
  end

  def test_requirements_with_single_unconditional_implication
    req_str = <<~COND
      extension:
        name: A
        version: = 1.0
    COND

    req_yaml = YAML.load(req_str)


    reqs = Udb::Requirements.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal Udb::ExtensionVersion.new("A", "1.0", @cfg_arch), ext_vers.fetch(0).ext_ver
    assert_instance_of Udb::AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_two_unconditional_implication
    req_str = <<~COND
      extension:
        allOf:
          - name: A
            version: = 1.0
          - name: C
            version: = 1.0
    COND

    req_yaml = YAML.load(req_str)

    reqs = Udb::Requirements.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 2, ext_vers.size
    assert_equal [Udb::ExtensionVersion.new("A", "1.0", @cfg_arch), Udb::ExtensionVersion.new("C", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of Udb::AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_one_unconditional_implication_and_a_requirement
    req_str = <<~COND
      extension:
        allOf:
          - name: A
            version: = 1.0
          - name: C
            version: ">= 1.0"
    COND

    req_yaml = YAML.load(req_str)

    reqs = Udb::Requirements.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [Udb::ExtensionVersion.new("A", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of Udb::AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_one_conditional_implication
    req_str = <<~COND
      extension:
        if:
          extension:
            name: A
            version: ">= 1.0"
        then:
          name: C
          version: "= 1.0"
    COND

    req_yaml = YAML.load(req_str)

    reqs = Udb::Requirements.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [Udb::ExtensionVersion.new("C", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of Udb::Condition, ext_vers.fetch(0).cond
    assert_equal [Udb::ExtensionRequirement.new("A", ">= 1.0", arch: @cfg_arch)], ext_vers.fetch(0).cond.to_logic_tree.terms
    assert ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("A", "1.0", @cfg_arch)])
    assert ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("A", "2.0", @cfg_arch)])
    refute ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("B", "2.1.0", @cfg_arch)])
  end

  def test_single_extension_req_with_implication
    cond_str = <<~COND
      extension:
        name: B
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Udb::Condition.new(cond_yaml, @cfg_arch)

    assert_equal Udb::SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 2, tree.terms.size
    refute tree.eval(@cfg_arch.symtab, [Udb::ExtensionVersion.new("A", "1.0", @cfg_arch)])
    refute tree.eval(@cfg_arch.symtab, [Udb::ExtensionVersion.new("B", "2.1.0", @cfg_arch)])
    assert tree.eval(@cfg_arch.symtab, [Udb::ExtensionVersion.new("A", "1.0", @cfg_arch), Udb::ExtensionVersion.new("B", "2.1.0", @cfg_arch)])
  end

  def test_single_extension_req_with_conditional_implication
    cond_str = <<~COND
      extension:
        name: D
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Udb::Condition.new(cond_yaml, @cfg_arch)

    assert_equal Udb::SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 3, tree.terms.size # D, C (used in requires condition), and A (target of requires)

    # D alone should satisfy
    assert cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("D", "2.0", @cfg_arch)])

    # D with C but not A should not
    refute cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("D", "2.0", @cfg_arch), Udb::ExtensionVersion.new("C", "2.0", @cfg_arch)])

    # D with C and A should
    assert cond.satisfied_by_ext_ver_list?([Udb::ExtensionVersion.new("A", "1.0", @cfg_arch), Udb::ExtensionVersion.new("C", "2.0", @cfg_arch), Udb::ExtensionVersion.new("D", "2.0", @cfg_arch)])
  end
end
