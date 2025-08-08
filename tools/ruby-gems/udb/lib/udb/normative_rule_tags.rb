# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

#
# Provides normative rule tags from standards documents.
#

module Udb
class NormativeRuleTags
  def initialize
    # Contains tag entries as a flat hash across all documents.
    # The hash key is the tag name and the hash value is a NormativeRuleTag object
    # The tag names must be unique across all documents.
    # The tag_map can be empty if for some portfolio types. They never call add_doc_tags().
    @tag_map = {}
    @missing_tags = false
  end

  # Add tags for specified standards document.
  #
  # param doc_name [String] Name of the standards document that has tags.
  # param tags [Hash<String,String>] Hash key is tag name (AKA anchor name) and value is tag text.
  def add_doc_tags(doc_name, tags)
    raise ArgumentError, "Need String but was passed a #{doc_name.String}" unless doc_name.is_a?(String)
    raise ArgumentError, "Need Hash but was passed a #{tags.String}" unless tags.is_a?(Hash)

    tags.each do |tag_name, tag_text|
      raise ArgumentError, "Duplicate normative rule tag name #{tag_name} found in document #{doc_name}" unless @tag_map[tag_name].nil?
      @tag_map[tag_name] = NormativeRuleTag.new(tag_name, doc_name, tag_text)
    end
  end

  # @return [Boolean] Are there any tags available? Not always available for all portfolio types.
  def tags_available? = !@tag_map.empty?

  # @param [String] Normative rule tag name
  # @return [NormativeRuleTag] Normative rule tag corresponding to tag name. Returns nil if not found.
  def get_normative_rule_tag(tag_name)
    raise ArgumentError, "Called to lookup tag_name #{tag_name} but normative rule tags not available in this Portofolio type" unless tags_available?
    @tag_map[tag_name]
  end

  # Called to indicate that at least one normative rule referenced one missing tag.
  # Used to allow all these to be detected and then exit with a failure status
  # instead of finding out about these all one at a time.
  def discovered_missing_tag
    @missing_tags = true
  end

  # @return [Boolean] Were there one or more missing tags?
  def missing_tags? = @missing_tags
end

class NormativeRuleTag
  # @return [String] Name of normative rule tag into standards document
  attr_reader :tag_name

  # @return [String] Name of standards document tag is located in.
  attr_reader :doc_name

  # @return [String] Text associated with normative rule tag from standards document. Can have newlines.
  attr_reader :tag_text

  # @param tag_name [String]
  # @param doc_name [String]
  # @param tag_text [String]
  def initialize(tag_name, doc_name, tag_text)
    @tag_name = tag_name
    @doc_name = doc_name
    @tag_text = tag_text
  end
end
end
