# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Udb

# Contains all normative rules for a RISC-V standard.
class NormativeRules
  # param data [Array<Hash>] Array of all normative rules defined in the architecture
  def initialize(data)
    raise ArgumentError, "Need array for data but was passed a #{data.class}" unless data.is_a?(Array)

    @normative_rule_hash = {}
    data.each do |nr_data|
      nr = NormativeRule.new(nr_data)
      unless @normative_rule_hash[nr.name].nil?
        raise "Duplicate normative rule #{nr.name} defined in #{nr.source} (already defined in #{@normative_rule_hash[nr.name].source})"
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
  attr_reader :name         # String (mandatory)
  attr_reader :source       # String (mandatory - Filename in ISA manual repo that defines normative rule)
  attr_reader :summary      # String (optional - a few words)
  attr_reader :description  # String (optional - sentence, paragraph, or more)
  attr_reader :tags         # Array<NormativeRuleTag> (optional - can be empty array, never nil)

  # @param data [Hash<String, Object>]
  def initialize(data)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @name = data["name"]
    raise ArgumentError, "Missing name in normative rule entry" if @name.nil?

    @source = data["source"]
    raise ArgumentError, "Missing source in normative rule entry #{name}" if @source.nil?

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

  # @return [String] Filename of ISA manual (priv or unpriv) with the tag
  attr_reader :source

  # @return [String] Text associated with normative rule tag from standards document. Can have newlines.
  attr_reader :tag_text

  # @param data [Hash<String, Object>]
  # @param nr_name String
  def initialize(data, nr_name)
    raise ArgumentError, "Need Hash for data but was passed a #{data.class}" unless data.is_a?(Hash)

    @tag_name = data["tag_name"]
    raise ArgumentError, "Missing tag_name in normative rule tag entry in normative rule #{nr_name}" if @tag_name.nil?

    @source = data["source"]
    raise ArgumentError, "Missing source in normative rule tag entry named #{tag_name} in normative rule #{nr_name}" if @source.nil?

    @tag_text = data["tag_text"]
    raise ArgumentError, "Missing tag_text in normative rule tag entry named #{tag_name} in normative rule #{nr_name}" if @tag_text.nil?
  end
end

end
