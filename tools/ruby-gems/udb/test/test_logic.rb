# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "fileutils"
require "tmpdir"
require "yaml"

require "minitest/autorun"
require "udb/logic"
require "udb/cfg_arch"
require "udb/resolver"


class TestConditions < Minitest::Test
  extend T::Sig
  include Udb

  sig { returns(ConfiguredArchitecture) }
  def cfg_arch
    return @cfg_arch unless @cfg_arch.nil?

    udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @gen_path = Pathname.new(Dir.mktmpdir)
    $resolver ||= Udb::Resolver.new(
      schemas_path_override: udb_gem_root / "schemas",
      cfgs_path_override: udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @gen_path,
      std_path_override: udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: false
    )
    @cfg_arch = T.let(nil, T.nilable(ConfiguredArchitecture))
    capture_io do
      @cfg_arch = $resolver.cfg_arch_for("_")
    end
    T.must(@cfg_arch)
  end

  sig { returns(ConfiguredArchitecture) }
  def partial_cfg_arch
    return @partial_cfg_arch unless @partial_cfg_arch.nil?

    udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @partial_gen_path = Pathname.new(Dir.mktmpdir)
    $resolver ||= Udb::Resolver.new(
      schemas_path_override: udb_gem_root / "schemas",
      cfgs_path_override: udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @partial_gen_path,
      std_path_override: udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: false
    )
    @partial_cfg_arch = T.let(nil, T.nilable(ConfiguredArchitecture))
    capture_io do
      @partial_cfg_arch = $resolver.cfg_arch_for("little_is_better")
    end
    T.must(@partial_cfg_arch)
  end

  sig { void }
  def test_simple_or
    n =
      LogicNode.new(
        LogicNodeType::Or,
        [
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
        ]
      )

    assert_equal "(A@1.0.0 OR B@1.0.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = (a | b)", n.to_eqntott.eqn
    assert n.satisfiable?
    assert n.is_cnf?
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |_term| SatisfiedResult::Yes })
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |_term| SatisfiedResult::No })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |_term| SatisfiedResult::Maybe })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Yes : SatisfiedResult::Maybe })
  end

  sig { void }
  def test_simple_and
    n =
      LogicNode.new(
        LogicNodeType::And,
        [
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
        ]
      )

    assert_equal "(A@1.0.0 AND B@1.0.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = (a & b)", n.to_eqntott.eqn
    assert n.is_cnf?
    assert n.satisfiable?
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |_term| SatisfiedResult::Yes })
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |_term| SatisfiedResult::No })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |_term| SatisfiedResult::Maybe })
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Yes : SatisfiedResult::Maybe })
  end

  sig { void }
  def test_simple_not
    n =
      LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])])

    assert_equal "NOT A@1.0.0", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = !(a)", n.to_eqntott.eqn
    assert n.satisfiable?
    assert n.is_cnf?
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Yes : SatisfiedResult::No })
    assert_equal SatisfiedResult::No, n.eval_cb(proc { |_term| SatisfiedResult::Yes })
    assert_equal SatisfiedResult::Yes, n.eval_cb(proc { |_term| SatisfiedResult::No })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |_term| SatisfiedResult::Maybe })
    assert_equal SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No })
  end

  sig { void }
  def test_ext_ver_convert
    term = ExtensionTerm.new("A", "1.0.0")

    assert_equal ExtensionVersion.new("A", "1.0.0", cfg_arch), term.to_ext_ver(cfg_arch)
    assert_equal ["name", "version"], term.to_h.keys
    puts term.to_h
    assert_equal ExtensionVersion.new("A", "1.0.0", cfg_arch), ExtensionVersion.new(term.to_h["name"], term.to_h["version"].gsub("= ", ""), cfg_arch)
  end

  sig { void }
  def test_parenthesize
    n =
      LogicNode.new(
        LogicNodeType::And,
        [
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("D", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("E", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("F", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("G", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("H", "1.0.0")]),
        ]
      )

    assert n.satisfiable?
    assert_equal "(A@1.0.0 AND B@1.0.0 AND C@1.0.0 AND D@1.0.0 AND E@1.0.0 AND F@1.0.0 AND G@1.0.0 AND H@1.0.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = (a & b & c & d & e & f & g & h)", n.to_eqntott.eqn
    assert_equal "(((((((A@1.0.0 AND B@1.0.0) AND C@1.0.0) AND D@1.0.0) AND E@1.0.0) AND F@1.0.0) AND G@1.0.0) AND H@1.0.0)", n.parenthesize.to_s(format: LogicNode::LogicSymbolFormat::English)
  end

  sig { void }
  def test_duplicate_and_terms
    n =
      LogicNode.new(
        LogicNodeType::And,
        [
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
        ]
      )

    assert n.satisfiable?
    assert_equal "(A@1.0.0 AND B@1.0.0 AND A@1.0.0 AND B@1.0.0 AND A@1.0.0 AND B@1.0.0 AND A@1.0.0 AND B@1.0.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = (a & b & a & b & a & b & a & b)", n.to_eqntott.eqn
    assert_equal "(((((((A@1.0.0 AND B@1.0.0) AND A@1.0.0) AND B@1.0.0) AND A@1.0.0) AND B@1.0.0) AND A@1.0.0) AND B@1.0.0)", n.parenthesize.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_includes ["(A@1.0.0 AND B@1.0.0)", "(B@1.0.0 AND A@1.0.0)"], n.minimize.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert n.equivalent?(n.minimize)
  end

  sig { void }
  def test_duplicate_or_terms
    n =
      LogicNode.new(
        LogicNodeType::Or,
        [
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
          LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]),
        ]
      )

    assert n.satisfiable?
    assert_equal "(A@1.0.0 OR B@1.0.0 OR A@1.0.0 OR B@1.0.0 OR A@1.0.0 OR B@1.0.0 OR A@1.0.0 OR B@1.0.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "out = (a | b | a | b | a | b | a | b)", n.to_eqntott.eqn
    assert_equal "(((((((A@1.0.0 OR B@1.0.0) OR A@1.0.0) OR B@1.0.0) OR A@1.0.0) OR B@1.0.0) OR A@1.0.0) OR B@1.0.0)", n.parenthesize.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_includes ["(A@1.0.0 OR B@1.0.0)", "(B@1.0.0 OR A@1.0.0)"], n.minimize.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert n.equivalent?(n.minimize)
  end

  def test_array_param_terms
    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 3,
      "equal" => true,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal h, term.to_h
    assert_equal "(SCOUNTENABLE_EN[3]=true)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(true)
    assert_equal SatisfiedResult::No, term.eval_value(false)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 4,
      "not_equal" => true,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[4]!=true)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(false)
    assert_equal SatisfiedResult::No, term.eval_value(true)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 4,
      "equal" => false,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[4]=false)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(false)
    assert_equal SatisfiedResult::No, term.eval_value(true)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 4,
      "not_equal" => false,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[4]!=false)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(true)
    assert_equal SatisfiedResult::No, term.eval_value(false)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 10,
      "less_than" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[10]<5)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(4)
    assert_equal SatisfiedResult::No, term.eval_value(5)
    assert_equal SatisfiedResult::No, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 10,
      "greater_than" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[10]>5)", term.to_s
    assert_equal SatisfiedResult::No, term.eval_value(4)
    assert_equal SatisfiedResult::No, term.eval_value(5)
    assert_equal SatisfiedResult::Yes, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 10,
      "less_than_or_equal" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[10]<=5)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(4)
    assert_equal SatisfiedResult::Yes, term.eval_value(5)
    assert_equal SatisfiedResult::No, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 10,
      "greater_than_or_equal" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN[10]>=5)", term.to_s
    assert_equal SatisfiedResult::No, term.eval_value(4)
    assert_equal SatisfiedResult::Yes, term.eval_value(5)
    assert_equal SatisfiedResult::Yes, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "index" => 10,
      "not_a_comparison" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_raises { term.to_s }
    assert_raises { term.eval_value(5) }
  end

  def test_scalar_param_terms
    h = {
      "name" => "SCOUNTENABLE_EN",
      "equal" => true,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal h, term.to_h
    assert_equal "(SCOUNTENABLE_EN=true)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(true)
    assert_equal SatisfiedResult::No, term.eval_value(false)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "not_equal" => true,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN!=true)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(false)
    assert_equal SatisfiedResult::No, term.eval_value(true)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "equal" => false,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN=false)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(false)
    assert_equal SatisfiedResult::No, term.eval_value(true)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "not_equal" => false,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN!=false)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(true)
    assert_equal SatisfiedResult::No, term.eval_value(false)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "less_than" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN<5)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(4)
    assert_equal SatisfiedResult::No, term.eval_value(5)
    assert_equal SatisfiedResult::No, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "greater_than" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN>5)", term.to_s
    assert_equal SatisfiedResult::No, term.eval_value(4)
    assert_equal SatisfiedResult::No, term.eval_value(5)
    assert_equal SatisfiedResult::Yes, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "less_than_or_equal" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN<=5)", term.to_s
    assert_equal SatisfiedResult::Yes, term.eval_value(4)
    assert_equal SatisfiedResult::Yes, term.eval_value(5)
    assert_equal SatisfiedResult::No, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "greater_than_or_equal" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_equal "(SCOUNTENABLE_EN>=5)", term.to_s
    assert_equal SatisfiedResult::No, term.eval_value(4)
    assert_equal SatisfiedResult::Yes, term.eval_value(5)
    assert_equal SatisfiedResult::Yes, term.eval_value(6)

    h = {
      "name" => "SCOUNTENABLE_EN",
      "not_a_comparison" => 5,
      "reason" => "blah"
    }
    term = ParameterTerm.new(h)
    assert_raises { term.to_s }
    assert_raises { term.eval_value(5) }
  end

  def test_bad_logic_nodes
    assert_raises { LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0"), ExtensionTerm.new("B", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::Term, [5]) }
    assert_raises { LogicNode.new(LogicNodeType::Not, [5]) }
    assert_raises { LogicNode.new(LogicNodeType::Not, [ExtensionTerm.new("A", "1.0.0"), ExtensionTerm.new("B", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::And, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::Or, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::Xor, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::None, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::If, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::True, [ExtensionTerm.new("A", "1.0.0")]) }
    assert_raises { LogicNode.new(LogicNodeType::False, [ExtensionTerm.new("A", "1.0.0")]) }
  end

  def test_eval
    n = LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))

    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]) # which isn't defined
      ]
    )
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))


    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])
      ]
    )
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))

    n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])
      ]
    )
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))

    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])
      ]
    )
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))


    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0")])
      ]
    )
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("C", "1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch), ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "C" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "C" ? SatisfiedResult::Maybe : SatisfiedResult::No }))

    n = LogicNode.new(
      LogicNodeType::None,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])
      ]
    )
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::No, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))

    n = LogicNode.new(
      LogicNodeType::Not,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
      ]
    )
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))

    n = LogicNode.new(
      LogicNodeType::If,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")]),
      ]
    )
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| SatisfiedResult::Maybe }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::Yes }))
    assert_equal(SatisfiedResult::Maybe, n.eval_cb(proc { |term| term.name == "A" ? SatisfiedResult::Maybe : SatisfiedResult::No }))
    assert_equal(SatisfiedResult::Yes, n.eval_cb(proc { |term| term.name == "B" ? SatisfiedResult::Maybe : SatisfiedResult::No }))

    n = LogicNode.new(
      LogicNodeType::If,
      [
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0")])
          ]
        ),
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")]),
      ]
    )
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch)]))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("C", "1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("A", "1.0.0", cfg_arch), ExtensionVersion.new("B", "2.1.0", cfg_arch)]))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, [ExtensionVersion.new("C", "1.0", cfg_arch), ExtensionVersion.new("B", "2.1.0", cfg_arch)]))

    n = LogicNode.new(LogicNodeType::True, [])
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(cfg_arch, cfg_arch.symtab, []))

    n = LogicNode.new(LogicNodeType::False, [])
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::No, n.eval(cfg_arch, cfg_arch.symtab, []))

    n = LogicNode.new(LogicNodeType::Term, [ParameterTerm.new({
      "name" => "MXLEN",
      "equal" => 32,
      "reason" => "blah"
    })])
    assert_equal(SatisfiedResult::Maybe, n.eval(cfg_arch, cfg_arch.symtab, cfg_arch.possible_extension_versions))
    assert_equal(SatisfiedResult::Yes, n.eval(partial_cfg_arch, partial_cfg_arch.symtab, partial_cfg_arch.possible_extension_versions))

    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "LITTLE_IS_BETTER",
                                "equal" => true,
                                "reason" => "blah"
                              })
          ])
      ]
    )
    assert n.satisfiable?
    assert n.equivalent?(n.minimize)
    assert_equal(SatisfiedResult::Maybe, n.eval(cfg_arch, cfg_arch.symtab, []))
    assert_equal(SatisfiedResult::Yes, n.eval(partial_cfg_arch, partial_cfg_arch.symtab, []))
  end

  def test_to_s
    n = LogicNode.new(LogicNodeType::True, [])
    assert_equal "1", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "ONE", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "true", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "true", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::False, [])
    assert_equal "0", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "ZERO", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "false", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "false", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])])
    assert_equal "!A@1.0.0", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "!A@1.0.0", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "NOT A@1.0.0", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "\u00acA@1.0.0", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::And, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])])
    assert_equal "(A@1.0.0 && B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "(A@1.0.0 & B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "(A@1.0.0 AND B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "(A@1.0.0 \u2227 B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::Or, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])])
    assert_equal "(A@1.0.0 || B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "(A@1.0.0 | B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "(A@1.0.0 OR B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "(A@1.0.0 \u2228 B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::Xor, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])])
    assert_equal "(A@1.0.0 ^ B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "(A@1.0.0 XOR B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "(A@1.0.0 \u2295 B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::If, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])])
    assert_equal "(A@1.0.0 IMPLIES B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "(A@1.0.0 \u2192 B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

    n = LogicNode.new(LogicNodeType::None, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")])])
    assert_equal "!(A@1.0.0 || B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::C)
    assert_equal "!(A@1.0.0 | B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Eqn)
    assert_equal "NOT (A@1.0.0 OR B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::English)
    assert_equal "\u00ac(A@1.0.0 \u2228 B@2.1.0)", n.to_s(format: LogicNode::LogicSymbolFormat::Predicate)

  end

  def test_to_h
    assert LogicNode.new(LogicNodeType::True, []).to_h
    refute LogicNode.new(LogicNodeType::False, []).to_h

    a_node = LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])
    assert_equal ({ "extension" => { "name" => "A", "version" => "= 1.0.0" } }), a_node.to_h
    assert_equal ({ "param" => { "name" => "A", "equal" => true } }), LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true)]).to_h

    n = LogicNode.new(LogicNodeType::Not, [a_node])
    assert_equal ({ "extension" => { "not" => { "name" => "A", "version" => "= 1.0.0" } } }), n.to_h

    n = LogicNode.new(LogicNodeType::Not, [n])
    assert_equal ({ "extension" => { "not" => { "not" => { "name" => "A", "version" => "= 1.0.0" } } } }), n.to_h

    n = LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ParameterTerm.new({ "name" => "A", "equal" => true, "reason" => "blah" })])])
    assert_equal ({ "param" => { "not" => { "name" => "A", "equal" => true, "reason" => "blah" } } }), n.to_h

    n = LogicNode.new(LogicNodeType::Not, [n])
    assert_equal ({ "param" => { "not" => { "not" => { "name" => "A", "equal" => true, "reason" => "blah" } } } }), n.to_h


    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "LITTLE_IS_BETTER",
                                "equal" => true,
                                "reason" => "blah"
                              })
          ])
      ]
    )
    h = {
      "param" => {
        "allOf" => [
          { "name" => "MXLEN", "equal" => 32, "reason" => "blah" },
          { "name" => "LITTLE_IS_BETTER", "equal" => true, "reason" => "blah" }
        ]
      }
    }
    assert_equal h, n.to_h
    assert n.equivalent?(n.minimize)
    assert n.satisfiable?

    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("A", "1.0.0")
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
      "extension" => {
        "allOf" => [
          { "name" => "A", "version" => "= 1.0.0" },
          { "name" => "B", "version" => "= 1.0.0" }
        ]
      }
    }
    assert_equal h, n.to_h
    assert n.equivalent?(n.minimize)
    assert n.satisfiable?

    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
        "allOf" => [
          { "param" => { "name" => "MXLEN", "equal" => 32, "reason" => "blah" } },
          { "extension" => { "name" => "B", "version" => "= 1.0.0" } }
        ]
      }
    assert_equal h, n.to_h
    assert n.equivalent?(n.minimize)
    assert n.satisfiable?

    n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "LITTLE_IS_BETTER",
                                "equal" => true,
                                "reason" => "blah"
                              })
          ])
      ]
    )
    h = {
      "param" => {
        "anyOf" => [
          { "name" => "MXLEN", "equal" => 32, "reason" => "blah" },
          { "name" => "LITTLE_IS_BETTER", "equal" => true, "reason" => "blah" }
        ]
      }
    }
    assert_equal h, n.to_h
    assert n.equivalent?(n.minimize)
    assert n.satisfiable?

    n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("A", "1.0.0")
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
      "extension" => {
        "anyOf" => [
          { "name" => "A", "version" => "= 1.0.0" },
          { "name" => "B", "version" => "= 1.0.0" }
        ]
      }
    }
    assert_equal h, n.to_h
    assert n.equivalent?(n.minimize)
    assert n.satisfiable?

    n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
        "anyOf" => [
          { "param" => { "name" => "MXLEN", "equal" => 32, "reason" => "blah" } },
          { "extension" => { "name" => "B", "version" => "= 1.0.0" } }
        ]
      }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "LITTLE_IS_BETTER",
                                "equal" => true,
                                "reason" => "blah"
                              })
          ])
      ]
    )
    h = {
      "param" => {
        "oneOf" => [
          { "name" => "MXLEN", "equal" => 32, "reason" => "blah" },
          { "name" => "LITTLE_IS_BETTER", "equal" => true, "reason" => "blah" }
        ]
      }
    }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("A", "1.0.0")
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
      "extension" => {
        "oneOf" => [
          { "name" => "A", "version" => "= 1.0.0" },
          { "name" => "B", "version" => "= 1.0.0" }
        ]
      }
    }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
        "oneOf" => [
          { "param" => { "name" => "MXLEN", "equal" => 32, "reason" => "blah" } },
          { "extension" => { "name" => "B", "version" => "= 1.0.0" } }
        ]
      }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::None,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "LITTLE_IS_BETTER",
                                "equal" => true,
                                "reason" => "blah"
                              })
          ])
      ]
    )
    h = {
      "param" => {
        "noneOf" => [
          { "name" => "MXLEN", "equal" => 32, "reason" => "blah" },
          { "name" => "LITTLE_IS_BETTER", "equal" => true, "reason" => "blah" }
        ]
      }
    }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::None,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("A", "1.0.0")
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
      "extension" => {
        "noneOf" => [
          { "name" => "A", "version" => "= 1.0.0" },
          { "name" => "B", "version" => "= 1.0.0" }
        ]
      }
    }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::None,
      [
        LogicNode.new(
          LogicNodeType::Term,
          [
            ParameterTerm.new({
                                "name" => "MXLEN",
                                "equal" => 32,
                                "reason" => "blah"
                              })
          ]),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )
    h = {
        "noneOf" => [
          { "param" => { "name" => "MXLEN", "equal" => 32, "reason" => "blah" } },
          { "extension" => { "name" => "B", "version" => "= 1.0.0" } }
        ]
      }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::If,
      [
        LogicNode.new(LogicNodeType::True, []),
        LogicNode.new(
          LogicNodeType::Term,
          [
            ExtensionTerm.new("B", "1.0.0")
          ])
      ]
    )

    h = {
      "if" => true,
      "then" => {
        "extension" => {
          "name" => "B", "version" => "= 1.0.0"
        }
      }
    }
    assert_equal h, n.to_h

    n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]),
        LogicNode.new(LogicNodeType::If,
          [
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "2.1.0")]),
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0.0")])
          ]
        ),
        LogicNode.new(LogicNodeType::If,
          [
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("D", "2.1.0")]),
            LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("E", "1.0.0")])
          ]
        ),
      ]
    )

    h = {
      "extension" => {
        "allOf" => [
          { "name" => "A", "version" => "= 1.0.0" },
          {
            "if" => { "extension" => { "name" => "B", "version" => "= 2.1.0" } },
            "then" => { "name" => "C", "version" => "= 1.0.0" }
          },
          {
            "if" => { "extension" => { "name" => "D", "version" => "= 2.1.0" } },
            "then" => { "name" => "E", "version" => "= 1.0.0" }
          }
        ]
      }
    }
    assert_equal h, n.to_h
  end

  def test_nnf
    n = LogicNode.new(
      LogicNodeType::Not,
      [
        LogicNode.new(
          LogicNodeType::Not,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(
                  LogicNodeType::Term,
                  [
                    ExtensionTerm.new("A", "1.0.0")
                  ]
                )
              ]
            )
          ]
        )
      ]
    )

    nnf_n =
      LogicNode.new(
        LogicNodeType::Not,
        [
          LogicNode.new(
            LogicNodeType::Term,
            [
              ExtensionTerm.new("A", "1.0.0")
            ]
          )
        ]
      )

    assert n.nnf.is_nnf?
    # nnf_n is also the minimal form
    assert_equal n.minimize.to_s, n.nnf.to_s
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)

    n = LogicNode.new(
      LogicNodeType::If,
      [
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
      ]
    )

    nnf_n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(
          LogicNodeType::Not,
          [
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
          ]
        ),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
      ]
    )

    assert n.nnf.is_nnf?
    puts n.cnf
    puts nnf_n.cnf
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)

    n = LogicNode.new(
      LogicNodeType::Xor,
      [
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")]),
      ]
    )

    nnf_n = LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(
          LogicNodeType::And,
          [
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")]),
              ]
            )
          ]
        ),
        LogicNode.new(
          LogicNodeType::And,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")]),
              ]
            )
          ]
        ),
        LogicNode.new(
          LogicNodeType::And,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")])
          ]
        ),
      ]
    )

    assert n.nnf.is_nnf?
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)

    n = LogicNode.new(LogicNodeType::Not, [n])

    nnf_n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")]),
              ]
            )
          ]
        ),
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")]),
              ]
            )
          ]
        ),
        LogicNode.new(
          LogicNodeType::Or,
          [
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(
              LogicNodeType::Not,
              [
                LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
              ]
            ),
            LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")])
          ]
        ),
      ]
    )

    assert n.nnf.is_nnf?
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)

    n = LogicNode.new(
      LogicNodeType::None,
      [
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")])
      ]
    )

    nnf_n = LogicNode.new(
      LogicNodeType::And,
      [
        LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")])]),
        LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")])]),
        LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")])])
      ]
    )

    assert n.nnf.is_nnf?
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)

    n = LogicNode.new(LogicNodeType::Not, [n])

    nnf_n =
    LogicNode.new(
      LogicNodeType::Or,
      [
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "B", "equal" => true, "reason" => "blah")]),
        LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "C", "equal" => true, "reason" => "blah")])
      ]
    )

    assert n.nnf.is_nnf?
    assert n.equivalent?(nnf_n)
    assert nnf_n.equivalent?(n)
  end

  def test_equivalence
    n = LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])
    m = LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])

    assert n.equivalent?(m)
    assert m.equivalent?(n)


    n = LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])
    m = LogicNode.new(LogicNodeType::Term, [ParameterTerm.new("name" => "A", "equal" => true, "reason" => "blah")])

    refute n.equivalent?(m)
    refute m.equivalent?(n)


    n = LogicNode.new(LogicNodeType::None, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0.0")])])
    m = LogicNode.new(LogicNodeType::And, [LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])]), LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")])]), LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("C", "1.0.0")])])])

    assert n.cnf.is_cnf?
    assert m.cnf.is_cnf?
    assert n.equivalent?(m)
    assert m.equivalent?(n)

    n = LogicNode.new(LogicNodeType::None, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")]), LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")])])
    m = LogicNode.new(LogicNodeType::And, [LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("A", "1.0.0")])]), LogicNode.new(LogicNodeType::Not, [LogicNode.new(LogicNodeType::Term, [ExtensionTerm.new("B", "1.0.0")])])])

    assert n.cnf.is_cnf?
    assert m.cnf.is_cnf?
    assert n.equivalent?(m)
    assert m.equivalent?(n)


  end
end
