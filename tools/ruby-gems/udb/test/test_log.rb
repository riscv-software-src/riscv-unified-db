# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "udb/log"

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

class TestLog < Minitest::Test
  include Udb

  def test_dummy_progressbar_supports_format_interface
    bar = Udb::DummyProgressBar.new

    # idlc's compiler calls format= and format on the progress bar it is given.
    bar.format = "Parsing foo [:bar]"
    assert_kind_of String, bar.format
  end

  def test_create_progressbar_at_quiet_log_levels_returns_a_dummy_that_accepts_format
    [LogLevel::Warn, LogLevel::Error, LogLevel::Fatal].each do |level|
      old = Udb.log_level
      Udb.log_level = level
      begin
        bar = Udb.create_progressbar("Compiling IDL for x [:bar]")
        assert_kind_of Udb::DummyProgressBar, bar
        bar.format = "Parsing foo [:bar]"
        assert_kind_of String, bar.format
        bar.advance
        bar.finish
      ensure
        Udb.log_level = old
      end
    end
  end

  def test_create_progressbar_at_default_level_returns_a_real_progress_bar
    old = Udb.log_level
    Udb.log_level = LogLevel::Info
    begin
      bar = Udb.create_progressbar("Compiling IDL for x [:bar]")
      assert_kind_of TTY::ProgressBar, bar
    ensure
      Udb.log_level = old
    end
  end
end
