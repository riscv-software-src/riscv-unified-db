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

class TestCfg < Minitest::Test
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
      result = cfg_arch.valid?
      assert result.valid, <<~MSG
        Config '#{File.basename(cfg_path, ".yaml")}' is not valid.
        To see why, run `./bin/udb validate cfg #{cfg_path}`
      MSG
    end
  end
end
