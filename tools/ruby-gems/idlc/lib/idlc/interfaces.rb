# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: strict
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "type"

module Idl
  # interface for a parameter that may only be known at runtime
  module RuntimeParam
    extend T::Sig
    extend T::Helpers
    interface!

    ValueType =
      T.type_alias { T.any(Integer, T::Boolean, String, T::Array[Integer], T::Array[T::Boolean]) }

    sig { abstract.returns(String) }
    def name; end

    sig { abstract.returns(String) }
    def desc; end

    sig { abstract.returns(T::Boolean) }
    def schema_known?; end

    sig { abstract.returns(Schema) }
    def schema; end

    sig { abstract.returns(T::Array[Schema]) }
    def possible_schemas; end

    sig { abstract.returns(T::Boolean) }
    def value_known?; end

    sig { abstract.returns(ValueType) }
    def value; end

    sig { abstract.returns(Type) }
    def idl_type; end
  end

  # basic interface for objects that are described with JSON Schema
  module Schema
    extend T::Sig
    extend T::Helpers
    interface!

    sig { abstract.returns(T::Boolean) }
    def max_val_known?; end

    sig { abstract.returns(Integer) }
    def max_val; end

    sig { abstract.returns(T::Boolean) }
    def min_val_known?; end

    sig { abstract.returns(Integer) }
    def min_val; end

    sig { abstract.returns(Type) }
    def to_idl_type; end
  end

  module CsrField
    extend T::Sig
    extend T::Helpers
    interface!

    sig { abstract.returns(String) }
    def name; end

    # whether or not this field is defined in both RV32 and RV64
    sig { abstract.returns(T::Boolean) }
    def defined_in_all_bases?; end

    sig { abstract.returns(T::Boolean) }
    def defined_in_base32?; end

    sig { abstract.returns(T::Boolean) }
    def defined_in_base64?; end

    # whether or not this field is defined only in RV64
    sig { abstract.returns(T::Boolean) }
    def base64_only?; end

    # whether or not this field is defined only in RV32
    sig { abstract.returns(T::Boolean) }
    def base32_only?; end

    # returns the location of the field in the CSR.
    # base is required when the field moves locations between RV32 and RV64
    sig { abstract.params(base: T.nilable(Integer)).returns(T::Range[Integer]) }
    def location(base); end

    # whether or not the field is supposed to exist/be implemented in the
    # execution context
    sig { abstract.returns(T::Boolean) }
    def exists?; end
  end

  module Csr
    extend T::Sig
    extend T::Helpers
    interface!

    sig { abstract.returns(String) }
    def name; end

    sig { abstract.params(base: T.nilable(Integer)).returns(T.nilable(Integer)) }
    def length(base); end

    sig { abstract.returns(Integer) }
    def max_length; end

    sig { abstract.returns(T::Boolean) }
    def dynamic_length?; end

    sig { abstract.returns(T::Array[CsrField]) }
    def fields; end

    # If the entire CSR is read-only with a known reset value, returns the value
    # otherwise, returns nil
    sig { abstract.returns(T.nilable(Integer)) }
    def value; end
  end
end
