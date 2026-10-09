# Copyright (c) Abhiraj Singh
# SPDX-License-Identifier: BSD-3-Clause-Clear
# typed: false

# frozen_string_literal: true

require_relative "test_helper"

require "set"

require "udb/version_spec"

class TestVersionSpec < Minitest::Test
  include Udb

  # A derived spec must be a fully distinct object: to_s, hash and eql? all
  # agreeing with its live major/minor/patch rather than the source's.
  def assert_derived(v, d, major, minor, patch)
    assert_equal major, d.major
    assert_equal minor, d.minor
    assert_equal patch, d.patch

    assert_equal d.canonical, d.to_s

    refute v.eql?(d)
    refute_equal v.hash, d.hash
    refute_equal 0, (v <=> d)
    assert_equal((v <=> d).zero?, v.eql?(d))

    assert_equal 2, [v, d].uniq.size
    assert_equal 2, Set[v, d].size
    assert_nil({ v => :a }[d])
    assert_equal(:b, { d => :b }[d])
  end

  def test_increment_patch
    v = VersionSpec.new("1.0.0")
    assert_derived(v, v.increment_patch, 1, 0, 1)
  end

  def test_decrement_patch_within_minor
    v = VersionSpec.new("1.0.5")
    assert_derived(v, v.decrement_patch, 1, 0, 4)
  end

  def test_decrement_patch_minor_rollover
    v = VersionSpec.new("1.3.0")
    assert_derived(v, v.decrement_patch, 1, 2, 9999)
  end

  def test_decrement_patch_major_rollover
    v = VersionSpec.new("2.0.0")
    assert_derived(v, v.decrement_patch, 1, 9999, 9999)
  end

  def test_decrement_patch_at_zero_raises
    assert_raises(RuntimeError) { VersionSpec.new("0.0.0").decrement_patch }
  end

  def test_increment_patch_preserves_pre_release
    v = VersionSpec.new("1.2.3-pre")
    d = v.increment_patch

    assert_derived(v, d, 1, 2, 4)
    assert d.pre
    assert_equal "1.2.4-pre", d.to_s
    assert_equal "1p2p4-pre", d.to_rvi_s
  end

  def test_to_rvi_s_preserves_source_given_ness
    d = VersionSpec.new("1.0").increment_patch

    # to_s reflects the canonical live version while to_rvi_s preserves the
    # source's given-ness; they are INTENTIONALLY divergent, do not "reconcile"
    # them
    assert_equal "1.0.1", d.to_s
    assert_equal "1p0", d.to_rvi_s
  end

  def test_directly_constructed_spec
    v = VersionSpec.new("1.2.3")

    assert_equal "1.2.3", v.to_s
    assert_equal "1.2.3", v.canonical
    assert_equal "1p2p3", v.to_rvi_s
    refute v.pre
  end

  def test_directly_constructed_spec_omitting_patch
    v = VersionSpec.new("1.0")

    assert_equal "1.0", v.to_s
    assert_equal "1.0.0", v.canonical
    assert_equal "1p0", v.to_rvi_s
  end

  def test_equal_specs_are_eql_and_ordered
    assert_equal VersionSpec.new("1.0.0"), VersionSpec.new("1.0.0")
    assert VersionSpec.new("1.0.0").eql?(VersionSpec.new("1.0.0"))
    assert_equal VersionSpec.new("1.0.0").hash, VersionSpec.new("1.0.0").hash
    assert_operator VersionSpec.new("1.0.0"), :<, VersionSpec.new("1.0.1")
  end
end
