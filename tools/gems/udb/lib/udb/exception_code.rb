# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# a synchroncous exception code
class Udb::ExceptionCode
  # @return [String] Long-form display name (can include special characters)
  attr_reader :name

  # @return [String] Field name for an IDL enum
  attr_reader :var

  # @return [Integer] Code, written into *mcause
  attr_reader :num

  # @return [Extension] Extension that defines this code
  attr_reader :ext

  def initialize(name, var, number, ext)
    @name = name
    @name.freeze
    @var = var
    @num = number
    @ext = ext
  end
end

module Udb
  # all the same information as ExceptinCode, but for interrupts
  InterruptCode = Class.new(ExceptionCode)
end
