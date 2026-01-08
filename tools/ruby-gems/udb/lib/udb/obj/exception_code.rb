# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: strict
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "database_obj"

module Udb

  module Code
    extend T::Sig

    # @return [String] Long-form display name (can include special characters)
    sig { returns(String) }
    def display_name = T.unsafe(self).data.fetch("display_name")

    # @return [String] Field name for an IDL enum
    sig { returns(String) }
    def var = T.unsafe(self).name

    # @return [Integer] Code, written into *mcause
    sig { returns(Integer) }
    def num = T.unsafe(self).data.fetch("num")
  end

  # a synchroncous exception code
  class ExceptionCode < TopLevelDatabaseObject
    extend T::Sig
    include Code
    include Comparable

    sig { override.params(resolver: Resolver).void }
    def validate(resolver)
      super(resolver)

      @arch.exception_codes.each do |code|
        next if code == self

        if num == code.num
          raise ValidationError, "Duplicate exception code #{num} for #{name}, #{code.name}"
        end
      end
    end

    sig { override.params(other: BasicObject).returns(T.nilable(Integer)) }
    def <=>(other)
      return nil unless T.cast(other, Object).is_a?(ExceptionCode)

      num <=> T.cast(other, ExceptionCode).num
    end

    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      (self <=> other) == 0
    end

    sig { override.returns(Integer) }
    def hash = [ExceptionCode, num].hash
  end

  # an asynchroncous interrupt code
  class InterruptCode < TopLevelDatabaseObject
    extend T::Sig
    include Code
    include Comparable

    sig { override.params(resolver: Resolver).void }
    def validate(resolver)
      super(resolver)

      @arch.interrupt_codes.each do |code|
        next if code == self

        if num == code.num
          raise ValidationError, "Duplicate interrupt code #{num} for #{name}, #{code.name}"
        end
      end
    end

    sig { override.params(other: BasicObject).returns(T.nilable(Integer)) }
    def <=>(other)
      return nil unless T.cast(other, Object).is_a?(ExceptionCode)

      num <=> T.cast(other, ExceptionCode).num
    end

    sig { override.params(other: BasicObject).returns(T::Boolean) }
    def eql?(other)
      (self <=> other) == 0
    end

    sig { override.returns(Integer) }
    def hash = [ExceptionCode, num].hash
  end
end
