# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "idlc/cli"
require "minitest/autorun"

# Test Command Line Interface
class TestCli < Minitest::Test
  def test_eval_addition
    out, err = capture_io { Idl::Cli.new(["-DA=5", "-DB=10", "-eA+B"]).run }
    assert_empty err, "nothing should be written to STDERR"
    assert_equal eval(out), 15
  end
end
