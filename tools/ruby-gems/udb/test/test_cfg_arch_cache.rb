# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "tmpdir"

require "udb/cfg_arch"
require "udb/resolver"
require "udb/obj/csr"
require "udb/obj/mmr"
require "udb/obj/has_fields"

class TestCfgArchCache < Minitest::Test
  include Udb

  def setup
    @gen_dir = Dir.mktmpdir
    @resolver = Udb::Resolver.new(
      Udb.repo_root,
      gen_path_override: Pathname.new(@gen_dir)
    )
  end

  def teardown
    FileUtils.rm_rf @gen_dir
  end

  # Records how many times each ConfiguredArchitecture object is queried,
  # and returns a predetermined result for it.
  #
  # ConfiguredArchitecture overrides hash/eql? to be name-based (see
  # cfg_arch.rb), so two distinct objects sharing the same config `name:`
  # are `eql?` to each other. Both internal maps here use
  # compare_by_identity, and are built from an array of [cfg, value] pairs
  # rather than a Hash literal, so that two name-equal-but-distinct
  # ConfiguredArchitecture instances are never silently collapsed into one
  # entry before this class even sees them.
  class RecordingCondition
    def initialize(pairs)
      @results_by_cfg = Hash.new.compare_by_identity
      pairs.each { |cfg, value| @results_by_cfg[cfg] = value }
      @calls = Hash.new(0).compare_by_identity
    end

    def calls
      @calls.dup
    end

    def could_be_satisfied_by_cfg_arch?(cfg_arch)
      @calls[cfg_arch] += 1
      @results_by_cfg.fetch(cfg_arch)
    end

    def satisfied_by_cfg_arch?(cfg_arch)
      @calls[cfg_arch] += 1
      @results_by_cfg.fetch(cfg_arch)
    end

    def empty?
      false
    end
  end

  # Minimal class including HasFields to test optional_in_cfg?
  class OptionalProbe
    include Udb::HasFields

    def initialize(condition)
      @condition = condition
      @data = { "fields" => {} }
    end

    def defined_by_condition
      @condition
    end

    def exists_in_cfg?(_cfg_arch)
      true
    end

    def cfg_arch
      nil
    end

    def name
      "probe"
    end
  end

  # Real ConfiguredArchitecture, built the same way production code and
  # test_cfg_arch.rb build it: through the resolver, from a config name or
  # a config file path — not via ConfiguredArchitecture.allocate.
  def make_cfg_arch(name)
    @resolver.cfg_arch_for(name)
  end

  # Writes a minimal partially-configured YAML config with the given
  # top-level `name:` field to a fresh tempfile, and resolves it into a
  # real ConfiguredArchitecture.
  def make_cfg_arch_from_yaml(config_name)
    cfg = <<~CFG
      $schema: config_schema.json#
      kind: architecture configuration
      type: partially configured
      name: #{config_name}
      description: Minimal config for cache identity tests
      mandatory_extensions:
        - name: "I"
          version: ">= 0"
        - name: "Sm"
          version: ">= 0"
    CFG

    f = Tempfile.create(%w/cfg .yaml/)
    f.write(cfg)
    f.flush
    @resolver.cfg_arch_for(Pathname.new(f.path))
  ensure
    f&.close
  end

  def make_csr(condition)
    csr = Csr.allocate
    csr.define_singleton_method(:defined_by_condition) { condition }
    csr
  end

  def make_mmr(condition)
    mmr = Mmr.allocate
    mmr.define_singleton_method(:defined_by_condition) { condition }
    mmr
  end

  def test_csr_exists_in_cfg_is_keyed_by_cfg_arch
    cfg_true = make_cfg_arch("rv32")
    cfg_false = make_cfg_arch("rv64")
    condition = RecordingCondition.new([[cfg_true, true], [cfg_false, false]])
    csr = make_csr(condition)

    assert_equal true, csr.exists_in_cfg?(cfg_true)
    assert_equal true, csr.exists_in_cfg?(cfg_true)
    assert_equal 1, condition.calls[cfg_true]

    assert_equal false, csr.exists_in_cfg?(cfg_false)
    assert_equal false, csr.exists_in_cfg?(cfg_false)
    assert_equal 1, condition.calls[cfg_false]
  end

  def test_mmr_exists_in_cfg_is_keyed_by_cfg_arch
    cfg_true = make_cfg_arch("rv32")
    cfg_false = make_cfg_arch("rv64")
    condition = RecordingCondition.new([[cfg_true, true], [cfg_false, false]])
    mmr = make_mmr(condition)

    assert_equal true, mmr.exists_in_cfg?(cfg_true)
    assert_equal true, mmr.exists_in_cfg?(cfg_true)
    assert_equal 1, condition.calls[cfg_true]

    assert_equal false, mmr.exists_in_cfg?(cfg_false)
    assert_equal false, mmr.exists_in_cfg?(cfg_false)
    assert_equal 1, condition.calls[cfg_false]
  end

  def test_optional_in_cfg_is_keyed_by_cfg_arch
    cfg_true = make_cfg_arch_from_yaml("optional_probe_true")
    cfg_false = make_cfg_arch_from_yaml("optional_probe_false")
    condition = RecordingCondition.new([
      [cfg_true, Udb::SatisfiedResult::Maybe],
      [cfg_false, Udb::SatisfiedResult::No]
    ])
    probe = OptionalProbe.new(condition)

    assert_equal true, probe.optional_in_cfg?(cfg_true)
    assert_equal true, probe.optional_in_cfg?(cfg_true)
    assert_equal 1, condition.calls[cfg_true]

    assert_equal false, probe.optional_in_cfg?(cfg_false)
    assert_equal false, probe.optional_in_cfg?(cfg_false)
    assert_equal 1, condition.calls[cfg_false]
  end

  # Regression: two distinct real ConfiguredArchitecture objects, built from
  # two separate config files that both declare `name: identical_config`,
  # are `eql?` to each other (ConfiguredArchitecture's hash/eql? are
  # name-based) but must still be cached separately by identity, since
  # exists_in_cfg?'s cache uses compare_by_identity.
  def test_identity_cache_separates_distinct_objects_even_if_logically_equal
    cfg1 = make_cfg_arch_from_yaml("identical_config")
    cfg2 = make_cfg_arch_from_yaml("identical_config")

    refute_same(cfg1, cfg2)
    assert cfg1.eql?(cfg2), "expected cfg1 and cfg2 to be logically equal (same name) as a precondition for this test"

    condition = RecordingCondition.new([[cfg1, true], [cfg2, false]])
    csr = make_csr(condition)

    assert_equal true, csr.exists_in_cfg?(cfg1)
    assert_equal 1, condition.calls[cfg1]
    assert_equal true, csr.exists_in_cfg?(cfg1)  # cached
    assert_equal 1, condition.calls[cfg1]

    assert_equal false, csr.exists_in_cfg?(cfg2)
    assert_equal 1, condition.calls[cfg2]
  end
end
