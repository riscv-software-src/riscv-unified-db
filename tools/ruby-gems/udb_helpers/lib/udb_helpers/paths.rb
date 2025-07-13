# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "bundler"
require "sorbet-runtime"

module Udb
  module Helpers
    extend T::Sig

    # Returns installation path for the gem
    sig { returns(Pathname) }
    def self.gem_path
      @gem_path ||= Pathname.new(Bundler.definition.specs.find { |s| s.name == "udb_helpers" }.full_gem_path)
    end
  end
end
