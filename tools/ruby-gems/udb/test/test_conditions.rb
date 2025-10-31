# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "tmpdir"
require "yaml"

require "udb/condition"
require "udb/resolver"

begin
  $db_resolver = Udb::Resolver.new(Udb.repo_root)
  $db_cfg_arch = $db_resolver.cfg_arch_for("_")
rescue RuntimeError
  $db_cfg_arch = nil
end

gen_path = Pathname.new(Dir.mktmpdir)
udb_gem_root = (Pathname.new(__dir__) / "..").realpath
$mock_resolver = Udb::Resolver.new(
  schemas_path_override: udb_gem_root / "schemas",
  cfgs_path_override: udb_gem_root / "test" / "mock_cfgs",
  gen_path_override: gen_path,
  std_path_override: udb_gem_root / "test" / "mock_spec" / "isa",
  quiet: false
)
$mock_cfg_arch = $mock_resolver.cfg_arch_for("_")

# clean up the temp dir when we are done
Minitest.after_run { FileUtils.rm_rf(gen_path) }

class TestConditions < Minitest::Test
  include Udb

  # def setup

  #   capture_io do
  #     $mock_cfg_arch = $mock_resolver.cfg_arch_for("_")
  #   end
  # end

  # def teardown
  #   FileUtils.rm_rf @gen_path
  # end

  def test_single_extension_req
    cond_str = <<~COND
      extension:
        name: A
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?($mock_cfg_arch)
    assert cond.could_be_satisfied_by_cfg_arch?($mock_cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree(expand: true)
    assert_equal 2, tree.terms.size # A has two version
    assert_equal [ExtensionTerm.new("A", "=", "1.0.0"), ExtensionTerm.new("A", "=", "2.0.0")], tree.terms
    cb = LogicNode.make_eval_cb do |term|
      case term
      when ExtensionTerm
        [ExtensionVersion.new("A", "1.0", $mock_cfg_arch)].any? do |ext_ver|
          term.to_ext_req($mock_cfg_arch).satisfied_by?(ext_ver)
        end ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterTerm
        term.eval(symtab)
      end
    end
    assert_equal SatisfiedResult::Yes, tree.eval_cb(cb)
    cb = LogicNode.make_eval_cb do |term|
      case term
      when ExtensionTerm
        [ExtensionVersion.new("B", "2.1.0", $mock_cfg_arch)].any? do |ext_ver|
          term.to_ext_req($mock_cfg_arch).satisfied_by?(ext_ver)
        end ? SatisfiedResult::Yes : SatisfiedResult::No
      when ParameterTerm
        term.eval(symtab)
      end
    end
    assert_equal SatisfiedResult::No, tree.eval_cb(cb)
    assert_equal "((A=1.0 ∨ A=2.0) ∧ (A=1.0 → (true ∧ true)) ∧ (A=2.0 → (true ∧ true)))", tree.to_s
  end

  def test_requirements_with_single_unconditional_implication
    req_str = <<~COND
      name: A
      version: = 1.0
    COND

    req_yaml = YAML.load(req_str)


    reqs = ExtensionRequirementList.new(req_yaml, $mock_cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal ExtensionVersion.new("A", "1.0", $mock_cfg_arch), ext_vers.fetch(0).ext_ver
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

    reqs = ExtensionRequirementList.new(req_yaml, $mock_cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 2, ext_vers.size
    assert_equal [ExtensionVersion.new("A", "1.0", $mock_cfg_arch), ExtensionVersion.new("C", "1.0", $mock_cfg_arch)], ext_vers.map(&:ext_ver)
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

    reqs = ExtensionRequirementList.new(req_yaml, $mock_cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [ExtensionVersion.new("A", "1.0", $mock_cfg_arch)], ext_vers.map(&:ext_ver)
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

    reqs = ExtensionRequirementList.new(req_yaml, $mock_cfg_arch)
    ext_vers = reqs.implied_extension_versions

    assert_equal 1, ext_vers.size
    assert_equal [ExtensionVersion.new("C", "1.0", $mock_cfg_arch)], ext_vers.map(&:ext_ver)
    assert_instance_of Condition, ext_vers.fetch(0).cond
    assert_equal [ExtensionTerm.new("A", "=", "1.0"), ExtensionTerm.new("A", "=", "2.0")], ext_vers.fetch(0).cond.to_logic_tree(expand: true).terms
    assert ext_vers.fetch(0).cond.satisfiability_depends_on_ext_req?(ExtensionRequirement.new("A", ">= 1.0", arch: $mock_cfg_arch))
    refute ext_vers.fetch(0).cond.satisfiability_depends_on_ext_req?(ExtensionVersion.new("B", "2.1.0", $mock_cfg_arch).to_ext_req)
  end

  def test_single_extension_req_with_implication
    cond_str = <<~COND
      extension:
        name: B
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?($mock_cfg_arch)
    assert cond.could_be_satisfied_by_cfg_arch?($mock_cfg_arch)
    refute_empty cond

    tree = cond.to_logic_tree(expand: true)
    assert_equal 2, tree.terms.size
    def make_cb(ext_vers)
      LogicNode.make_eval_cb do |term|
        case term
        when ExtensionTerm
          ext_vers.any? { |ext_ver| term.to_ext_req($mock_cfg_arch).satisfied_by?(ext_ver) } ? SatisfiedResult::Yes : SatisfiedResult::No
        when ParameterTerm
          term.eval(symtab)
        end
      end
    end
    assert_equal SatisfiedResult::No, tree.eval_cb(make_cb([ExtensionVersion.new("A", "1.0", $mock_cfg_arch)]))
    assert_equal SatisfiedResult::No, tree.eval_cb(make_cb([ExtensionVersion.new("B", "2.1.0", $mock_cfg_arch)]))
    assert_equal SatisfiedResult::Yes, tree.eval_cb(make_cb([ExtensionVersion.new("A", "1.0", $mock_cfg_arch), ExtensionVersion.new("B", "2.1.0", $mock_cfg_arch)]))
  end

  def test_single_extension_req_with_conditional_implication
    cond_str = <<~COND
      extension:
        name: D
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?($mock_cfg_arch)
    assert cond.could_be_satisfied_by_cfg_arch?($mock_cfg_arch)
    refute_empty cond

    # D alone should satisfy
    assert cond.satisfiability_depends_on_ext_req?(ExtensionRequirement.new("D", ">= 0", arch: $mock_cfg_arch))

    # D with C but not A should not satisfy
    cb = LogicNode.make_eval_cb do |term|
      case term
      when ExtensionTerm
        if term.name == "D"
          SatisfiedResult::Yes
        elsif term.name == "C"
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      when ParameterTerm
        raise "?"
      end
    end
    assert_equal SatisfiedResult::No, cond.to_logic_tree(expand: true).eval_cb(cb)

    # D with C and A should
    cb = LogicNode.make_eval_cb do |term|
      case term
      when ExtensionTerm
        if term.name == "D"
          SatisfiedResult::Yes
        elsif term.name == "C"
          SatisfiedResult::Yes
        elsif term.name == "A"
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      when ParameterTerm
        raise "?"
      end
    end
    assert_equal SatisfiedResult::Yes, cond.to_logic_tree(expand: true).eval_cb(cb)
  end

  def test_single_param_req
    cond_str = <<~COND
      idl(): (MXLEN == 32) -> LITTLE_IS_BETTER;
      reason: because
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert_equal SatisfiedResult::Maybe, cond.satisfied_by_cfg_arch?($mock_cfg_arch)

    good_cfg_arch = $mock_resolver.cfg_arch_for("little_is_better")
    good_cond = Condition.new(cond_yaml, good_cfg_arch)

    assert_equal SatisfiedResult::Yes, good_cond.satisfied_by_cfg_arch?(good_cfg_arch)

    bad_cfg_arch = $mock_resolver.cfg_arch_for("little_is_not_better")
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

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert Condition.new(cond.to_h, $mock_cfg_arch).equivalent?(cond)
    assert cond.equivalent?(Condition.new(cond.to_h, $mock_cfg_arch))

    cond_str = <<~COND
      idl(): true -> implemented?(ExtensionName::A);
      reason: Something compelling
    COND

    cond_yaml = YAML.load(cond_str)

    cond = Condition.new(cond_yaml, $mock_cfg_arch)

    assert Condition.new(cond.to_h, $mock_cfg_arch).equivalent?(cond)
    assert cond.equivalent?(Condition.new(cond.to_h, $mock_cfg_arch))
  end

  def test_cnf
    cond_str = <<~COND
      extension:
        allOf:
          - name: A
          - name: B
    COND

    cond_yaml = YAML.load(cond_str)

    a_and_b = Condition.new(cond_yaml, $mock_cfg_arch)

    assert a_and_b.satisfiable?

    cond_str = <<~COND
      extension:
        anyOf:
          - name: A
          - name: B
    COND

    cond_yaml = YAML.load(cond_str)

    a_or_b = Condition.new(cond_yaml, $mock_cfg_arch)

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

  # skip checks on the real data if we can't find the repository root
  unless $db_cfg_arch.nil?

    # test all instruction definedBy:
    $db_cfg_arch.instructions.each do |inst|
      define_method("test_inst_#{inst.name.gsub(".", "_")}_defined_by") do
        assert inst.defined_by_condition.satisfiable?
        assert inst.defined_by_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)
        h = inst.defined_by_condition.to_h
        idl = inst.defined_by_condition.to_idl($db_cfg_arch)

        idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
        h_cond = Condition.new(h, $db_cfg_arch)

        assert idl_cond.equivalent?(h_cond)

      end
    end

    # test all param defined_by
    $db_cfg_arch.params.each do |param|
      define_method("test_param_#{param.name.gsub(".", "_")}_defined_by") do
        assert param.defined_by_condition.satisfiable?
        assert param.defined_by_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)

        h = param.defined_by_condition.to_h
        idl = param.defined_by_condition.to_idl($db_cfg_arch)

        idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
        assert idl_cond.equivalent?(param.defined_by_condition)
        h_cond = Condition.new(h, $db_cfg_arch)
        assert h_cond.equivalent?(param.defined_by_condition)

        assert idl_cond.equivalent?(h_cond), "#{idl_cond.to_s_pretty} is not equivalent to #{h_cond.to_s_pretty}"
      end
    end

    # test all param requirements
    $db_cfg_arch.params.each do |param|
      define_method("test_param_#{param.name.gsub(".", "_")}_requirements") do
        assert param.requirements_condition.satisfiable?
        assert param.requirements_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)

        h = param.requirements_condition.to_h
        idl = param.requirements_condition.to_idl($db_cfg_arch)

        idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
        assert idl_cond.equivalent?(param.requirements_condition), "Condition coversion to IDL is not logically equivalent: \n\nOriginal:\n#{param.requirements_condition}\n\nConversion:\n#{idl}"
        h_cond = Condition.new(h, $db_cfg_arch)
        assert h_cond.satisfiable?
        assert h_cond.equivalent?(param.requirements_condition), "Condition coversion to YAML is not logically equivalent: \n\nOriginal:\n#{param.requirements_condition}\n\nConversion:\n#{h}"

        assert idl_cond.equivalent?(h_cond), "#{idl_cond.to_s_pretty} is not equivalent to #{h_cond.to_s_pretty}"
      end
    end


    # test all csr definedBy: and csr field definedBy:
    $db_cfg_arch.csrs.each do |csr|
      define_method("test_csr_#{csr.name.gsub(".", "_")}_defined_by") do
        assert csr.defined_by_condition.satisfiable?
        assert csr.defined_by_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)
        h = csr.defined_by_condition.to_h
        idl = csr.defined_by_condition.to_idl($db_cfg_arch)

        idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
        assert idl_cond.equivalent?(csr.defined_by_condition)
        h_cond = Condition.new(h, $db_cfg_arch)
        assert h_cond.equivalent?(csr.defined_by_condition)

        assert idl_cond.equivalent?(h_cond), "#{idl_cond.to_s_pretty} is not equivalent to #{h_cond.to_s_pretty}"

        csr.fields.each do |field|
          next if field.defined_by_condition.empty?

          assert field.defined_by_condition.satisfiable?
          assert field.defined_by_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)
          h = field.defined_by_condition.to_h
          idl = field.defined_by_condition.to_idl($db_cfg_arch)

          idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
          assert idl_cond.equivalent?(field.defined_by_condition)
          h_cond = Condition.new(h, $db_cfg_arch)
          assert h_cond.equivalent?(field.defined_by_condition)

        end

      end
    end

    # test all extension requirements
    $db_cfg_arch.extensions.each do |ext|
      define_method("test_ext_#{ext.name.gsub(".", "_")}_requirements") do
        unless ext.requirements_condition.empty?
          # check that the requirement makes sense
          assert ext.requirements_condition.satisfiable?

          # and check that it could be satisfied by at least the unconfig
          assert ext.requirements_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)

          # conver to YAML and IDL
          h = ext.defined_by_condition.to_h
          idl = ext.defined_by_condition.to_idl($db_cfg_arch)

          # and then assert that they are equivalent (not necessarily identical) to each other
          idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
          assert idl_cond.equivalent?(ext.defined_by_condition)
          h_cond = Condition.new(h, $db_cfg_arch)
          assert h_cond.equivalent?(ext.defined_by_condition)
        end

        # do the same for any version requirements
        ext.versions.each do |ext_ver|
          # skip if this is trivial
          next if ext_ver.requirements_condition.empty?

          assert ext_ver.requirements_condition.satisfiable?
          assert ext_ver.requirements_condition.could_be_satisfied_by_cfg_arch?($db_cfg_arch)

          h = ext_ver.requirements_condition.to_h
          idl = ext_ver.requirements_condition.to_idl($db_cfg_arch)

          idl_cond = IdlCondition.new({ "idl()" => idl }, $db_cfg_arch, input_file: nil, input_line: nil)
          assert idl_cond.equivalent?(ext_ver.requirements_condition)
          h_cond = Condition.new(h, $db_cfg_arch)
          assert h_cond.equivalent?(ext_ver.requirements_condition)
        end

      end
    end
  end
end
