# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

require_relative "version"

module Udb

  class Presence < T::Enum
    enums do
      Mandatory = new("mandatory")
      ExpansionOption = new("expansion option")
      LocalizedOption = new("localized option")
      DevelopmentOption = new("development option")
      TransitoryOption = new("transitory option")
      Option = new("option") # legacy option
    end

    sig { params(yaml: T.any(String, T::Hash[String, String])).returns(Presence) }
    def self.from_yaml(yaml)
      if yaml.is_a?(String)
        if yaml == "mandatory"
          Mandatory
        else
          Option
        end
      else
        if yaml.key?("optional")
          case yaml.fetch("optional")
          when "expansion"
            ExpansionOption
          when "localized"
            LocalizedOption
          when "development"
            DevelopmentOption
          when "transitory"
            TransitoryOption
          else
            raise "unexpected"
          end
        else
          raise "unexpected"
        end
      end
    end

    def presence
      case self
      when Mandatory
        "mandatory"
      when ExpansionOption, LocalizedOption, DevelopmentOption, TransitoryOption, Option
        "optional"
      else
        T.absurd(self)
      end
    end

    sig { returns(T.nilable(String)) }
    def optional_type
      case self
      when ExpansionOption
        "expansion"
      when LocalizedOption
        "localized"
      when DevelopmentOption
        "development"
      when TransitoryOption
        "transitory"
      when Option
        nil
      when Mandatory
        Udb.logger.fatal "There is no optional_type for a mandatory presence"
        raise "unexpected"
      else
        T.absurd(self)
      end
    end

    sig { returns(T::Boolean) }
    def mandatory? = (self == Mandatory)

    sig { returns(T::Boolean) }
    def optional? = (self != Mandatory)

    sig { override.returns(String) }
    def to_s = serialize

    sig { returns(String) }
    def to_s_concise
      if self == Mandatory
        "mandatory"
      else
        "optional"
      end
    end
  end
end
