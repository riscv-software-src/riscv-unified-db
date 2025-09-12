# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb

# Contains all normative rules for a RISC-V standard.
class NormativeRules
  extend T::Sig
  # data - Hash with one key called "normative_rules" with an array of all normative rules.
  sig { params(data: T::Hash[String, T.untyped]).void }
  def initialize(data)
    raise ArgumentError, "Need hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    nr_array = data["normative_rules"]
    raise ArgumentError, "Expecting an array for key normative_rules but got an #{nr_array.class}" unless nr_array.is_a?(Array)

    @normative_rule_hash = {}
    nr_array.each do |nr_data|
      nr = NormativeRule.new(nr_data)
      unless @normative_rule_hash[nr.name].nil?
        raise "Duplicate normative rule #{nr.name} defined in #{nr.def_filename} (already defined in #{@normative_rule_hash[nr.name].def_filename})"
      end
      @normative_rule_hash[nr.name] = nr
    end
  end

  # Returns a list of all normative rules defined in the architecture
  sig { returns(T::Array[NormativeRule]) }
  def normative_rules = @normative_rule_hash.values

  # Returns named normative rule or nil if doesn't exist
  sig { params(name: String).returns(T.nilable(NormativeRule)) }
  def normative_rule(name) = @normative_rule_hash[name]
end

# Contains one Normative Rule
class NormativeRule
  extend T::Sig
  # @return [String] Normative rule name (mandatory)
  attr_reader :name

  # @return [String] Filename in ISA manual repo of norm rule definition file (e.g. rv32.yaml), mandatory
  attr_reader :def_filename

  # @return [String] (optional - a few words)
  attr_reader :summary

  # @return [String] (optional - sentence, paragraph, or more)
  attr_reader :description

  # @return [String] Kind of ISA object associated with rule (can be nil)
  attr_reader :kind

  # @return [String] Instance name(s) of ISA object associated with rule (nil if kind is nil, otherwise an array)
  attr_reader :instances

  attr_reader :tags               # Array<NormativeRuleTag> (optional - can be empty array, never nil)

  sig { params(data: T::Hash[String, T.untyped]).void }
  def initialize(data)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @name = data["name"]
    raise ArgumentError, "Missing name in normative rule entry" if @name.nil?

    @def_filename = data["def_filename"]
    raise ArgumentError, "Missing def_filename in normative rule entry #{name}" if @def_filename.nil?

    @summary = data["summary"]
    @description = data["description"]

    @tags = []
    data["tags"]&.each do |tag_data|
      @tags.append(NormativeRuleTag.new(tag_data, @name))
    end
  end
end

# Holds all information for one tag.
class NormativeRuleTag
  extend T::Sig
  # @return [String] Name of normative rule tag into standards document
  attr_reader :name

  # @return [String] Filename of norm tags file per ISA manual (optional, can be nil)
  attr_reader :tag_filename

  # @return [String] Text associated with normative rule tag from standards doc. Can have newlines. (optional, can be nil)
  attr_reader :text

  # @return [String] Kind of ISA object associated with tag (can be nil)
  attr_reader :kind

  # @return [String] Instance name(s) of ISA object associated with tag (nil if kind is nil, otherwise an array)
  attr_reader :instances

  # nr_name is normative rule name
  sig { params(data: T::Hash[String, T.untyped], nr_name: String).void }
  def initialize(data, nr_name)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @name = data["name"]
    raise ArgumentError, "Missing tag name in normative rule tag entry in normative rule #{nr_name}" if @name.nil?

    @tag_filename = data["tag_filename"]
    @text = data["text"]
    @kind = data["kind"]
    @instances = data["instances"]
  end

  # Returns "Priv" or "Unpriv" if tag_filename present. If tag_filename not present, returns empty String.
  sig { returns(String) }
  def manual_name
    if @tag_filename.nil?
      ret = ""
    else
      case @tag_filename
      when /-privileged-/
        ret = "Priv"
      when /-unprivileged-/
        ret = "Unpriv"
      else
        raise ArgumentError, "Can't determine if ISA manual name is Priv or Unpriv from tag filename #{@tag_filename}"
      end
    end

    return ret
  end

  sig { returns(String) }
  def adoc_link
    ret = "<<#{name},#{name}>>"   # default

    if text.nil?
      # No tag text available (typically a link to a table cell).
      # Utilize kind and instances if provided.
      unless kind.nil?
        if instances.empty?
          ret = "<<#{name},#{kind} => #{name}>>"
        else
          ret = "<<#{name},#{kind} #{instances.join(',')} => #{name}>>"
        end
      end
    else
      ret = "<<#{name},#{name}>> => #{text}"
    end

    return ret
  end
end

end
