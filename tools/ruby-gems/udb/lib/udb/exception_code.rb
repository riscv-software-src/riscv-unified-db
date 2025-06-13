# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: strict
# frozen_string_literal: true

require "sorbet-runtime"

module Udb
  class DatabaseObject; end
  class TopLevelDatabaseObject < DatabaseObject; end
  class Extension < TopLevelDatabaseObject; end

  # a synchroncous exception code
  class ExceptionCode
    extend T::Sig

    # @return [String] Long-form display name (can include special characters)
    sig { returns(String) }
    attr_reader :name

    # @return [String] Field name for an IDL enum
    sig { returns(String) }
    attr_reader :var

    # @return [Integer] Code, written into *mcause
    sig { returns(Integer) }
    attr_reader :num

    # @return [Extension] Extension that defines this code
    sig { returns(Extension) }
    attr_reader :ext

    sig { params(name: String, var: String, number: Integer, ext: Extension).void }
    def initialize(name, var, number, ext)
      @name = T.let(name, String)
      @name.freeze
      @var = T.let(var, String)
      @num = T.let(number, Integer)
      @ext = T.let(ext, Extension)
    end
  end

  # all the same information as ExceptinCode, but for interrupts
  InterruptCode = Class.new(ExceptionCode)
end
