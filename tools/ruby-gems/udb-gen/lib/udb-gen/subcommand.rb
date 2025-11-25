# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "tty-option"

require "udb/cfg_arch"

module UdbGen
  class Subcommand
    extend T::Sig
    extend T::Helpers

    include TTY::Option

    abstract!

    attr_reader :name
    attr_reader :desc

    sig { params(name: String, desc: String).void }
    def initialize(name:, desc:)
      @name = name
      @desc = desc
    end

    # run, and return exit code
    sig { abstract.params(argv: T::Array[String]).returns(T.noreturn) }
    def run(argv); end
  end
end
