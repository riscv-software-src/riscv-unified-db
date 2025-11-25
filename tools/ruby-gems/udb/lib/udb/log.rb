# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "logger"
require "tty-logger"

require "sorbet-runtime"

module Udb
  extend T::Sig

  sig { returns(T.any(Logger, TTY::Logger)).checked(:never) }
  def self.logger
    @logger ||= TTY::Logger.new do |config|
      config.level = :warn
    end
  end

  sig { params(logger: T.any(Logger, TTY::Logger)).returns(T.any(Logger, TTY::Logger)) }
  def self.set_logger(logger)
    @logger = logger
  end
end
