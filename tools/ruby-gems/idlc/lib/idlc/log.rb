# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "logger"

require "sorbet-runtime"

module Idl
  extend T::Sig

  sig { returns(Logger).checked(:tests) }
  def self.logger
    @logger ||= Logger.new($stdout, level: :warn)
  end

  sig { params(logger: Logger).returns(Logger) }
  def self.set_logger(logger)
    @logger = logger
  end
end
