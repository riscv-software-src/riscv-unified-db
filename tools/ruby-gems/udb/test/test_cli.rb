# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "minitest/autorun"
require "udb/cli"

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
    assert_empty err
  end

  def test_list_params
    out, err = capture_io do
      run_cmd("list parameters")
    end
    assert_match /MXLEN/, out
    assert_empty err
  end

  def test_list_params_filtered
    out, err = capture_io do
      run_cmd("list parameters -e Sm H")
    end
    assert_match /MXLEN/, out
    refute_match /MUTABLE_ISA_S/, out
    assert_empty err
  end

  def test_list_params_yaml
    t = Tempfile.new
    _out, err = capture_io do
      run_cmd("list parameters -f yaml -o #{t.path}")
    end
    data = YAML.load_file(t.path)
    assert_equal data.any? { |p| p["name"] == "MXLEN" }, true
    assert_empty err
  end

  def test_disasm
    out, err = capture_io do
      run_cmd("disasm 0x00000037")
    end

    assert_match "  lui", out
    assert_empty err
  end

  def test_list_csrs
    out, err = capture_io do
      run_cmd("list csrs")
    end
    assert_empty err

    # Matching just one or a few CSRs is a weak check!
    # assert_match "misa", out

    # The number of reported CSRs for an Unconfigured config should match
    # the number of yaml files under csr directory.
    num_csr_yaml_files = `find spec/std/isa/csr/ -name '*.yaml' | wc -l`.to_i
    puts num_csr_yaml_files
    assert_equal num_csr_yaml_files, out.split.length
    # The puts above is reported when the individual test is run in the VSCode
    # terminal from the root of the riscv-unified-db repo with:
    # ./bin/ruby -Itest tools/ruby-gems/udb/test/test_cli.rb --name test_list_csrs

    # Don't hard code the number of reported CSRs!
    # assert_equal 371, out.split.length
  end

end
