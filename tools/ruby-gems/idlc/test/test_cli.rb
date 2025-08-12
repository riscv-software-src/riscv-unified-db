# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "open3"

require "minitest/autorun"

class CliTest < Minitest::Test
  CommandResult = Struct.new(:status, :out, :err)

  def run_cmd(cmd)
    require "idlc/cli"
    out, err = capture_io do
      Idl::Cli.new(cmd.split(" ")[1..]).run
    end
    CommandResult.new(0, out, err)
  end
end

# Test Command Line Interface
class TestCli < CliTest
  def test_eval_addition
    result = run_cmd("idlc eval -DA=5 -DB=10 A+B")
    # assert_equal 0, result.status
    assert_empty result.err, "nothing should be written to STDERR"
    assert_equal 15, eval(result.out)
  end

  def test_operation_tc
    Tempfile.open("idl") do |f|
      f.write <<~YAML
        operation(): |
          XReg src1 = X[xs1];
          XReg src2 = X[xs2];

          X[xd] = src1 + src2;
      YAML
      f.flush

      result = run_cmd("idlc tc inst --trace -k operation() -d xs1=5 -d xs2=5 -d xd=5 #{f.path}")
      puts result.out
      # assert_equal 0, result.status
      assert_empty result.err, "nothing should be written to STDERR"
      assert_empty result.out, "nothing should be written to STDOUT"
    end
  end
end
