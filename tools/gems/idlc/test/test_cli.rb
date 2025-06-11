# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "open3"

require "idlc/cli"
require "minitest/autorun"

class CliTest < Minitest::Test
  CommandResult = Struct.new(:status, :out, :err)

  def result
    @result ||= CommandResult.new
  end

  def run_cmd(cmd)
    puts "> #{cmd}"
    result.out, result.err, result.status = Open3.capture3(cmd)
  end
end

# Test Command Line Interface
class TestCli < CliTest
  def test_eval_addition
    run_cmd("idlc eval -DA=5 -DB=10 A+B")
    assert_equal 0, result.status
    assert_empty result.err, "nothing should be written to STDERR"
    assert_equal 15, eval(result.out)
  end

  def test_operation_tc
    Tempfile.open('idl') do |f|
      f.write <<~YAML
        operation(): |
          XReg src1 = X[xs1];
          XReg src2 = X[xs2];

          X[xd] = src1 + src2;
      YAML
      f.flush

      run_cmd("idlc tc inst -k 'operation()' -d xs1=5 -d xs2=5 -d xd=5 #{f.path}")
      puts result.out
      assert_equal 0, result.status
      assert_empty result.err, "nothing should be written to STDERR"
      assert_empty result.out, "nothing should be written to STDOUT"
    end
  end
end
