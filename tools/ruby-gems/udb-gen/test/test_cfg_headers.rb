# Copyright (c) Jordan Carlin, Harvey Mudd College.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "tmpdir"
require "pathname"

require "udb/resolver"
require "udb-gen/generators/cfg_c_header/generator"
require "udb-gen/generators/cfg_svh_header/generator"

class TestCfgHeaders < Minitest::Test
  GOLDEN_DIR = Pathname.new(__dir__).parent.parent.parent.parent / "tests" / "golden"
  TEST_CONFIG = "mc100-32-full-example"

  module GeneratorTestHelper
    def configure_for_test(resolver:, cfg:)
      @resolver = resolver
      parse(["--cfg", cfg])
      self
    end
  end

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

  def test_cfg_c_header_matches_golden
    gen = UdbGen::GenCfgCHeaderOptions.new
    gen.extend(GeneratorTestHelper).configure_for_test(resolver: @resolver, cfg: TEST_CONFIG)
    output = gen.generate_header
    golden = File.read(GOLDEN_DIR / "#{TEST_CONFIG}.golden.h")
    assert_equal golden, output,
      "C header output does not match golden file. " \
      "If this is expected, update the golden file with: ./bin/chore gen cfg-headers"
  end

  def test_cfg_svh_header_matches_golden
    gen = UdbGen::GenCfgSvhHeaderOptions.new
    gen.extend(GeneratorTestHelper).configure_for_test(resolver: @resolver, cfg: TEST_CONFIG)
    output = gen.generate_header
    golden = File.read(GOLDEN_DIR / "#{TEST_CONFIG}.golden.svh")
    assert_equal golden, output,
      "SystemVerilog header output does not match golden file. " \
      "If this is expected, update the golden file with: ./bin/chore gen cfg-headers"
  end

  def test_boolean_array_mask_packs_true_elements
    values = Array.new(32, false)
    values[1] = true
    values[31] = true

    c_lines = []
    UdbGen::GenCfgCHeaderOptions.new.send(:emit_array_param, c_lines, "UDB_X", values)
    assert_includes c_lines, "#define UDB_X_1"
    assert_includes c_lines, "#define UDB_X_31"
    assert_includes c_lines, "#define UDB_X_MASK 0x80000002"

    svh_lines = []
    UdbGen::GenCfgSvhHeaderOptions.new.send(:emit_array_param, svh_lines, "UDB_X", values)
    assert_includes svh_lines, "`define UDB_X_MASK 32'h80000002"
  end

  def test_boolean_array_mask_with_bit_63_uses_unsigned_c_literal
    values = Array.new(64, false)
    values[63] = true

    c_lines = []
    UdbGen::GenCfgCHeaderOptions.new.send(:emit_array_param, c_lines, "UDB_X", values)
    assert_includes c_lines, "#define UDB_X_MASK 0x8000000000000000"

    svh_lines = []
    UdbGen::GenCfgSvhHeaderOptions.new.send(:emit_array_param, svh_lines, "UDB_X", values)
    assert_includes svh_lines, "`define UDB_X_MASK 64'h8000000000000000"
  end

  def test_empty_array_emits_nothing
    lines = []
    UdbGen::GenCfgCHeaderOptions.new.send(:emit_array_param, lines, "UDB_X", [])
    assert_empty lines
  end
end
