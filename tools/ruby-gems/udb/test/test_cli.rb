# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "test_helper"


require "stringio"
require "udb/cli"

# this is needed for tty-progressbar to work with minitest
unless StringIO.method_defined? :ioctl
  class StringIO
    def ioctl(*)
      # :nocov:
      80
      # :nocov:
    end
  end
end

class TestCli < Minitest::Test
  def run_cmd(cmdline)
    Udb::Cli.start(cmdline.split(" "))
  end

  def test_list_extensions
    out, err = capture_io do
      run_cmd("list extensions")
    end
    assert_match /Zvkg/, out
    assert_empty err
  end

  def test_list_qc_iu_extensions
    out, err = capture_io do
      run_cmd("list extensions --config qc_iu")
    end
    assert_match /Xqci/, out
  end

  def test_list_params
    out, err = capture_io do
      run_cmd("list parameters")
    end
    assert_match /MXLEN/, out
    assert_empty err
  end

  def test_list_params_filtered
    out, _err = capture_io do
      run_cmd("list parameters -e Sm H")
    end
    assert_match /MXLEN/, out
    refute_match /MUTABLE_ISA_S/, out
  end

  def test_list_params_yaml
    t = Tempfile.new
    _out, _err = capture_io do
      run_cmd("list parameters -f yaml -o #{t.path}")
    end
    data = YAML.load_file(t.path)
    assert_equal data.any? { |p| p["name"] == "MXLEN" }, true
  end

  def test_disasm
    out, err = capture_io do
      run_cmd("disasm 0x00000037")
    end

    assert_match "  lui", out
  end

  def test_list_csrs
    num_listed = nil
    _out, _err = capture_io do
      num_listed = run_cmd("list csrs")
    end

    repo_top = Udb.repo_root
    num_csr_yaml_files = `find #{repo_top}/spec/std/isa/csr/ -name '*.yaml' | wc -l`.to_i

    assert_equal num_csr_yaml_files, num_listed
  end

end
