# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module UdbGen
  extend T::Sig

  sig { returns(Pathname) }
  def self.root = (Pathname.new(__dir__) / ".." / "..").realpath
end
