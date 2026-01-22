# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "subcommand"

module UdbGen
  class SubcommandWithCommonOptions < Subcommand
    extend T::Sig
    include TTY::Option

    option :cfg do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-c"
      long "--cfg=cfg_name"
      default "_"
    end

    flag :help do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-h"
      long "--help"
      desc "Print usage"
    end

    sig { params(name: String, desc: String).void }
    def initialize(name:, desc:)
      super(name:, desc:)
    end

    sig { returns(Udb::Resolver) }
    def resolver
      @resolver ||= Udb::Resolver.new
    end

    sig { returns(Udb::ConfiguredArchitecture) }
    def cfg_arch
      @cfg_arch ||=
        resolver.cfg_arch_for(params[:cfg])
    end

    sig { override.params(argv: T::Array[String]).returns(T.noreturn) }
    def run(argv)
      raise "must override #run in #{self.class.name}"
    end
  end
end
