# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb

# Contains all normative rules for a RISC-V standard.
class NormativeRules
  # param data [Hash<String, Array>] Hash with one key called "normative_rules" with an array of all normative rules.
  def initialize(data)
    raise ArgumentError, "Need hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    nr_array = data["normative_rules"]
    raise ArgumentError, "Expecting an array for key normative_rules but got an #{nr_array.class}" unless nr_array.is_a?(Array)

    @normative_rule_hash = {}
    nr_array.each do |nr_data|
      nr = NormativeRule.new(nr_data)
      unless @normative_rule_hash[nr.name].nil?
        raise "Duplicate normative rule #{nr.name} defined in #{nr.creation_filename} (already defined in #{@normative_rule_hash[nr.name].creation_filename})"
      end
      @normative_rule_hash[nr.name] = nr
    end
  end

  # @return [Array<NormativeRule>] List of all normative rules defined in the architecture
  def normative_rules = @normative_rule_hash.values

  # @return [NormativeRule] Returns named normative rule or nil if doesn't exist
  def normative_rule(name) = @normative_rule_hash[name]
end

# Contains one Normative Rule
class NormativeRule
  attr_reader :name               # String (mandatory)
  attr_reader :creation_filename  # String (mandatory - Filename in ISA manual repo of norm rule creation file (e.g. rv32.yaml)
  attr_reader :summary            # String (optional - a few words)
  attr_reader :description        # String (optional - sentence, paragraph, or more)
  attr_reader :tags               # Array<NormativeRuleTag> (optional - can be empty array, never nil)

  # @param data [Hash<String, Object>]
  def initialize(data)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @name = data["name"]
    raise ArgumentError, "Missing name in normative rule entry" if @name.nil?

    @creation_filename = data["filename"]
    raise ArgumentError, "Missing filename in normative rule entry #{name}" if @creation_filename.nil?

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
  # @return [String] Name of normative rule tag into standards document
  attr_reader :tag_name

  # @return [String] Filename of norm tags file per ISA manual (optional, can be nil)
  attr_reader :filename

  # @return [String] Text associated with normative rule tag from standards doc. Can have newlines. (optional, can be nil)
  attr_reader :tag_text

  # @param data [Hash<String, Object>]
  # @param nr_name String
  def initialize(data, nr_name)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @tag_name = data["tag_name"]
    raise ArgumentError, "Missing tag_name in normative rule tag entry in normative rule #{nr_name}" if @tag_name.nil?

    @filename = data["filename"]
    @tag_text = data["tag_text"]
  end

  # @return [String] Returns "Priv" or "Unpriv" if filename present. If filename not present, returns empty String.
  def manual_name
    if @filename.nil?
      ret = ""
    else
      case @filename
      when /-privileged-/
        ret = "Priv"
      when /-unprivileged-/
        ret = "Unpriv"
      else
        raise ArgumentError, "Can't determine if ISA manual name is Priv or Unpriv in tag filename #{@filename}"
      end
    end

    return ret
  end
end

end
