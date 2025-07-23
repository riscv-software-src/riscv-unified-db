# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "fileutils"
require "tmpdir"
require "yaml"

require "simplecov"

SimpleCov.start do
  enable_coverage :branch
  add_filter "/test/"
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"
require "udb/condition"
require "udb/resolver"

class TestConditions < Minitest::Test
  include Udb

  def setup
    @udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @gen_path = Pathname.new(Dir.mktmpdir)
    $resolver = Resolver.new(
      schemas_path_override: @udb_gem_root / "schemas",
      cfgs_path_override: @udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @gen_path,
      std_path_override: @udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: false
    )
    capture_io do
      @cfg_arch = $resolver.cfg_arch_for("_")
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

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 2, tree.terms.size # A has two version
    assert_equal [ExtensionTerm.new("A", "1.0.0"), ExtensionTerm.new("A", "2.0.0")], tree.terms
    assert_equal tree.eval(@cfg_arch, @cfg_arch.symtab, [ExtensionVersion.new("A", "1.0", @cfg_arch)]), SatisfiedResult::Yes
    assert_equal tree.eval(@cfg_arch, @cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", @cfg_arch)]), SatisfiedResult::No
    assert_equal "(A@1.0 \u2228 A@2.0)", tree.to_s
  end

  def test_requirements_with_single_unconditional_implication
    req_str = <<~COND
      name: A
      version: = 1.0
    COND

    req_yaml = YAML.load(req_str)


    reqs = ExtensionRequirementList.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal ExtensionVersion.new("A", "1.0", @cfg_arch), ext_vers.fetch(0).ext_ver
    assert_instance_of AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_two_unconditional_implication
    req_str = <<~COND
      allOf:
        - name: A
          version: = 1.0
        - name: C
          version: = 1.0
    COND

    req_yaml = YAML.load(req_str)

    reqs = ExtensionRequirementList.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 2, ext_vers.size
    assert_equal [ExtensionVersion.new("A", "1.0", @cfg_arch), ExtensionVersion.new("C", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_one_unconditional_implication_and_a_requirement
    req_str = <<~COND
      allOf:
        - name: A
          version: = 1.0
        - name: C
          version: ">= 1.0"
    COND

    req_yaml = YAML.load(req_str)

    reqs = ExtensionRequirementList.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [ExtensionVersion.new("A", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of AlwaysTrueCondition, ext_vers.fetch(0).cond
  end

  def test_requirements_with_one_conditional_implication
    req_str = <<~COND
      name: C
      version: "= 1.0"
      when:
        extension:
          name: A
          version: ">= 1.0"
    COND

    req_yaml = YAML.load(req_str)

    reqs = ExtensionRequirementList.new(req_yaml, @cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [ExtensionVersion.new("C", "1.0", @cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of Condition, ext_vers.fetch(0).cond
    assert_equal [ExtensionTerm.new("A", "1.0"), ExtensionTerm.new("A", "2.0")], ext_vers.fetch(0).cond.to_logic_tree.terms
    assert_equal ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("A", "1.0", @cfg_arch)]), SatisfiedResult::Yes
    assert_equal ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("A", "2.0", @cfg_arch)]), SatisfiedResult::Yes
    assert_equal ext_vers.fetch(0).cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("B", "2.1.0", @cfg_arch)]), SatisfiedResult::No
  end

  def test_single_extension_req_with_implication
    cond_str = <<~COND
      extension:
        name: B
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 2, tree.terms.size
    assert_equal tree.eval(@cfg_arch, @cfg_arch.symtab, [ExtensionVersion.new("A", "1.0", @cfg_arch)]), SatisfiedResult::No
    assert_equal tree.eval(@cfg_arch, @cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", @cfg_arch)]), SatisfiedResult::No
    assert_equal tree.eval(@cfg_arch, @cfg_arch.symtab, [ExtensionVersion.new("A", "1.0", @cfg_arch), ExtensionVersion.new("B", "2.1.0", @cfg_arch)]), SatisfiedResult::Yes
  end

  def test_single_extension_req_with_conditional_implication
    cond_str = <<~COND
      extension:
        name: D
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)
    assert cond.could_be_true?(@cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree
    assert_equal 5, tree.terms.size # D, C x2 (used in requires condition), and A x2 (target of requires)

    # D alone should satisfy
    assert_equal cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("D", "2.0", @cfg_arch)]), SatisfiedResult::Yes

    # D with C but not A should not satisfy
    assert_equal cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("D", "2.0", @cfg_arch), ExtensionVersion.new("C", "2.0", @cfg_arch)]), SatisfiedResult::No

    # D with C and A should
    assert_equal cond.satisfied_by_ext_ver_list?([ExtensionVersion.new("A", "1.0", @cfg_arch), ExtensionVersion.new("C", "2.0", @cfg_arch), ExtensionVersion.new("D", "2.0", @cfg_arch)]), SatisfiedResult::Yes
  end

  def test_single_param_req
    cond_str = <<~COND
      idl(): (MXLEN == 32) -> LITTLE_IS_BETTER;
      reason: because
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?(@cfg_arch)

    good_cfg_arch = $resolver.cfg_arch_for("little_is_better")
    good_cond = Condition.new(cond_yaml, good_cfg_arch)

    assert_equal SatisfiedResult::Yes, good_cond.satisfied_by_cfg_arch?(good_cfg_arch)

    bad_cfg_arch = $resolver.cfg_arch_for("little_is_not_better")
    bad_cond = Condition.new(cond_yaml, bad_cfg_arch)

    assert_equal SatisfiedResult::No, bad_cond.satisfied_by_cfg_arch?(bad_cfg_arch)
  end

  def test_constraint_to_yaml
    cond_str = <<~COND
      idl(): |
        for (U32 i = 0; i < 32; i++) {
          HPM_COUNTER_EN[i] -> SCOUNTENABLE_EN[i];
        }
      reason: Something compelling
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert Condition.new(cond.to_h, @cfg_arch).equivalent?(cond)
    assert cond.equivalent?(Condition.new(cond.to_h, @cfg_arch))


    cond_str = <<~COND
      idl(): true -> implemented?(ExtensionName::A);
      reason: Something compelling
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, @cfg_arch)

    assert Condition.new(cond.to_h, @cfg_arch).equivalent?(cond)
    assert cond.equivalent?(Condition.new(cond.to_h, @cfg_arch))
  end

  def test_cnf
    cond_str = <<~COND
      extension:
        allOf:
          - name: A
          - name: B
    COND

    cond_yaml = YAML.load(cond_str)

    a_and_b = Condition.new(cond_yaml, @cfg_arch)

    assert a_and_b.satisfiable?

    cond_str = <<~COND
      extension:
        anyOf:
          - name: A
          - name: B
    COND

    cond_yaml = YAML.load(cond_str)

    a_or_b = Condition.new(cond_yaml, @cfg_arch)

    assert a_or_b.satisfiable?

    assert a_and_b.compatible?(a_or_b)
    assert a_or_b.compatible?(a_and_b)
  end

  def test_idl_funcs
    cond_str = <<~COND
      idl(): implemented?(ExtensionName::A) && implemented?(ExtensionName::C) -> implemented?(ExtensionName::B)
      reason: because
    COND


  end
end
