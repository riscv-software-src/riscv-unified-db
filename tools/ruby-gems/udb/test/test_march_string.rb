# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"
require "tmpdir"
require "udb/resolver"
require "udb/cfg_arch"

class TestMarchString < Minitest::Test
  include Udb

  def setup
    @gen_dir = Dir.mktmpdir
    @resolver = Udb::Resolver.new(
      Udb.repo_root,
      gen_path_override: Pathname.new(@gen_dir)
    )
  end

  def teardown
    FileUtils.rm_rf(@gen_dir)
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
    # Canonical single letter order: I, M, C -> rv32imc
    assert_match(/^rv32imc/, march)
    refute_includes march, "Sm"
  end

  def test_march_string_multi_letter_z_extensions
    cfg_arch = @resolver.cfg_arch_for("mc100-32-full-example")
    march = cfg_arch.march_string
    # Multi-letter extensions grouped by Z/S/X prefix and separated by underscore
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
