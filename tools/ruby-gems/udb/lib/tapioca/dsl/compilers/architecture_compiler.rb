# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

require "active_support/inflector/methods"

require "udb/architecture"

module Tapioca
  module Compilers
    class Encryptable < Tapioca::Dsl::Compiler
      extend T::Sig

      ConstantType = type_member { { fixed: T.class_of(Udb::Architecture) } }

      sig { override.returns(T::Enumerable[Module]) }
      def self.gather_constants
        [Udb::Architecture]
      end

      sig { override.void }
      def decorate
        # Create a RBI definition for each class that includes Encryptable
        root.create_path(constant) do |klass|
          Udb::Architecture::OBJS.each do |obj_data|
            plural_fn = ActiveSupport::Inflector.pluralize(obj_data[:fn_name])

            klass.create_method(plural_fn, return_type: "T::Array[#{obj_data[:klass]}]")
            klass.create_method("#{obj_data[:fn_name]}_hash", return_type: "T::Hash[String, #{obj_data[:klass]}]")
            klass.create_method(obj_data[:fn_name], parameters: [create_param("name", type: "String")], return_type: "T.nilable(#{obj_data[:klass]})")
          end
        end
      end
    end
  end
end
