# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "logger"
require "tty-logger"
require "tty-progressbar"

require "sorbet-runtime"

module Udb
  extend T::Sig

  class LogLevel < T::Enum
    include Comparable

    enums do
      Debug = new("debug")
      Info = new("info")
      Warn = new("warn")
      Error = new("error")
      Fatal = new("fatal")
    end

    sig { returns(Integer) }
    def rank
      case self
      when Debug then 5
      when Info then 4
      when Warn then 3
      when Error then 2
      when Fatal then 1
      else
        T.absurd(self)
      end
    end

    def <=>(other)
      return nil unless other.is_a?(LogLevel)

      rank <=> other.rank
    end
  end

  # default log level is info
  @log_level = ENV.key?("LOG") ? LogLevel.deserialize(ENV["LOG"]) : LogLevel::Info

  sig { returns(LogLevel) }
  def self.log_level
    @log_level
  end

  sig { params(level: LogLevel).void }
  def self.log_level=(level)
    @log_level = level
  end

  sig { returns(T.any(Logger, TTY::Logger)).checked(:never) }
  def self.logger
    @logger ||= TTY::Logger.new do |config|
      config.level = @log_level.serialize.to_sym
    end
  end

  sig { params(logger: T.any(Logger, TTY::Logger)).returns(T.any(Logger, TTY::Logger)) }
  def self.set_logger(logger)
    @logger = logger
  end



  class DummyProgressBar
    extend T::Sig

    sig { void }
    def advance
      # do nothing
    end

    sig { void }
    def finish
      # do nothing
    end
  end

  class DummyMultiProgressBar
    extend T::Sig

    sig { params(fmt: String, options: T.untyped).returns(DummyProgressBar) }
    def register(fmt, **options)
      DummyProgressBar.new
    end
  end

  DEFAULT_PROGRESSBAR_LOG_LEVEL = LogLevel::Info

  sig { returns(T.nilable(TTY::ProgressBar::Multi)) }
  def self.top_level_progressbar
    @top_level_progressbar
  end

  sig { void }
  def self.delete_top_level_progressbar
    raise "Top-level progressbar does not exist" if @top_level_progressbar.nil?

    @top_level_progressbar = nil
  end

  sig {
    params(
      fmt: T.nilable(String),
      level: LogLevel,
      clear: T::Boolean
    ).returns(T.any(TTY::ProgressBar::Multi, DummyMultiProgressBar))
  }
  def self.create_top_level_progressbar(fmt: nil, level: LogLevel::Info, clear: true)
    raise "Top-level progressbar already exists" unless @top_level_progressbar.nil?

    @top_level_log_level = level
    if level <= @log_level
      if fmt.nil?
        @top_level_progressbar = TTY::ProgressBar::Multi.new
      else
        @top_level_progressbar = TTY::ProgressBar::Multi.new(fmt)
      end
    else
      @top_level_progressbar = DummyMultiProgressBar.new
    end
  end

  sig { params(fmt: String, options: T.untyped).returns(T.any(TTY::ProgressBar, DummyProgressBar)) }
  def self.create_progressbar(fmt, **options)
    if @top_level_progressbar.nil?

      target_level = options.key?(:level) ? LogLevel.deserialize(options[:level].to_s) : LogLevel::Info
      if target_level <= @log_level
        TTY::ProgressBar.new(fmt, **options)
      else
        DummyProgressBar.new
      end
    else
      @top_level_progressbar.register(fmt, **options)
    end
  end
end
