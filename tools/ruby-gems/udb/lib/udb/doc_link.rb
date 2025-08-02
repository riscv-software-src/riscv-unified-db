# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Creates links into RISC-V documentation with the following formats for the link name.
# The <id> is a unique suffix that describes the tagged text.
#
#   Documentation Format                                                    Associated ISA features
#   ============  =======================================================   ================================================
#   ISA manuals   norm:base:<base-name>:<id>                                Single base ISA (rv32i/rv32e/rv64i)
#                 norm:bases:<base-name>[_<base-name>]+:<id>                List of bases
#                 norm:basegrp:<group-name>:<id>                            Named group of bases (e.g., rv32, all)
#                 norm:ext:<ext-name>:<id>                                  Single extension
#                 norm:exts:<ext-name>[_<ext-name>]:<id>                    List of extensions
#                 norm:extgrp:<group-name>:<id>                             Named group of extensions
#                 norm:enc:insttable:<inst-name>                            Table cell for instruction encoding
#                 norm:inst:<inst-name>:<id>                                Single instruction
#                 norm:insts:<inst-name>[_<inst-name>]+:<id>                List of instructions
#                 norm:instgrp:<group-name>:<id>                            Named group of insts (e.g., branch, load)
#                 norm:csr:<csr-name>:<id>                                  Single CSR
#                 norm:csrs:<csr-name>[_<csr-name>]+:<id>                   List of CSRs
#                 norm:csrgrp:<group-name>:<id>                             Named group of CSRs
#                 norm:csrfld:<csr-name>:<field-name>:<id>                  Single CSR field
#                 norm:csrflds:<csr-name>:<field-name>[_<field-name>]+:<id> List of fields in the same CSR
#                 norm:csrfldgrp:<csr-name>:<group-name>:<id>               Named group of CSR fields in the same CSR
#                 norm:csrsfld:<csr-name>[_<csr-name>]+:<field-name>:<id>   Same field in the listed CSRs
#                 norm:param:<param-name>:<id>                              Single parameter
#                 norm:params:<param-name>[_<param-name>]+:<id>             List of parameters
#                 norm:paramgrp:<group-name>:<id>                           Named group of parameters
#   UDB encoding  udb:enc:inst:<inst-name>
#   UDB doc       udb:doc:ext:<ext-name>
#                 udb:doc:inst:<inst-name>
#                 udb:doc:csr:<csr-name>
#                 udb:doc:csr_field:<csr-name>:<field-name>
#                 udb:doc:param:<ext-name>:<param-name>
#                 udb:doc:func:<func-name>  (Documentation of common/built-in IDL functions)
#                 udb:doc:covpt:<fmt>:<name>
#                   where <fmt> is:
#                      sep for UDB documentation that "separates" normative rules from test plans
#                      combo for UDB documentation that "combines" normative rules with test plans
#                      appendix for UDB documentation that has normative rules and test plans in appendices
#                   where <name> is the name of the normative rule
#   IDL code      idl:code:inst:<inst-name>:<location>
#                 TODO for CSR and CSR Fields
#
# See the following AsciiDoc documents to understand how links and anchors work:
#   - How to make cross-references: https://docs.asciidoctor.org/asciidoc/latest/macros/xref/
#   - How to create anchors: https://docs.asciidoctor.org/asciidoc/latest/attributes/id/
#   - The types of anchors we care about are are:
#     - What I call the "inline syntax" such as "We must [#free_the_world]#free the world#."
#     - What I call the "paragraph syntax" such as:
#           [[foo]]
#           This is an anchor for the entire paragraph.
#
#           This isn't part of the anchor since it is the next paragraph.
#     - You can also use the "paragraph syntax" for table cells and list items as long as it begins before the text such as:
#           | [[foo]] Here is the table cell contents | next cell
#
# AsciiDoc Anchor Naming Restrictions:
#   - Start with a letter, ":", or "_" followed by letters, ":", "_", "-", ".", or digits. No spaces allowed.
#   - However, you can't put a "." in inline anchors (see https://docs.asciidoctor.org/asciidoc/latest/attributes/id/#block-assignment)
#     for other reasons.
#
# Naming restrictions:
#   - Start anchor names with a letter and use ":" to separate fields in the anchor name.
#   - Use underscores to separate lists of items between colons (e.g., ":insts:add_sub") since RISC-V uses "-" same names.
#   - Replace "." in items with "-" (e.g., fence.tso becomes fence-tso) so all anchors types used work properly.
#
# Adding anchors into AsciiDoc files
# ==================================
#  1) Anchor to part of a paragraph
#     Syntax:      [#<anchor-name>]# ... #
#     Example:     Here is an example of [#foo]#anchoring part# of a paragraph
#                  and can have [#bar]#multiple anchors# if needed.
#     Tagged text: "anchoring part" and "multiple anchors"
#     Limitations:
#       - Can't anchor text across multiple paragraphs.
#       - Must have text next to the 2nd hash symbol (i.e., can't have newline after [#<anchor-name]#).
#       - Can't put inside admonitions such as [NOTE] (see #3 below for solution).
#       - Can't have "." in anchor-name (replace with "-")
#
#  2) Anchor to entire paragraph, inside a table cell, or inside a list entry
#     Syntax:     [[<anchor-name]]
#     Example:    [[zort]]
#                 Here is an example of anchoring a whole paragraph.
#     Tagged text: Entire paragraph
#     Example:    | Alan Turing | [[Alan_Turing_Birthday]] June 23, 1912 | London
#     Tagged text: None (just creates hyperlink to anchor in table/list)
#
#  3) Anchor inside admonition (e.g. [NOTE])
#     - Must use [[<anchor-name]] before each paragraph (with unique anchor names of course) being tagged
#     - Can't use [#<anchor-name]#Here's some note text.# since it just shows up in HTML as normal text
#     - Don't put [[<<anchor-name]] before the entire admonition (e.g., before [NOTE]) to apply to entire admonition
#       (one or more paragraphs) since it will just create a hyperlink with no associated text.

module Udb
class DocLink
  # @return [String] Link name to normative rule. Not allowed to have periods or whitespace.
  attr_reader :link_name

  # @param link_name [String] The documentation link provided in the YAML
  def initialize(link_name)
    raise ArgumentError, "Need String but was passed a #{data.class}" unless link_name.is_a?(String)
    raise ArgumentError, "Link name '#{link_name}' is not allowed to contain periods. Use a hyphen instead." if link_name.include?(".")
    raise ArgumentError, "Link name '#{link_name}' is not allowed to contain whitespace." if link_name =~ /\s/
    raise ArgumentError, "Link name '#{link_name}' must start with a letter" unless link_name =~ /\A\p{L}/
    @link_name = link_name
  end

  # @return [Boolean] Is doc_link expected to have a normative rule tag entry?
  def should_have_normative_rule_tag?
    # Include all links that start with "norm:" except for those in the instruction encoding table
    # since they don't show up in the tags file.
    link_name.start_with?("norm:") && !link_name.start_with?("norm:enc:insttable:")
  end

  # @param normative_rule_tags [NormativeRuleTags] Normative rule tags
  # @return Boolean  Indicates if this doc_link should have a normative rule tag but it wasn't found.
  def missing_normative_rule_tag?(normative_rule_tags)
    raise ArgumentError, "normative_rule_tags needs to be a NormativeRuleTags class but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)

    should_have_normative_rule_tag? && normative_rule_tags.get_normative_rule_tag(link_name).nil?
  end

  # @param normative_rule_tags [NormativeRuleTags] Normative rule tags
  # @return String
  def to_doc_name(normative_rule_tags)
    raise ArgumentError, "normative_rule_tags needs to be a NormativeRuleTags class but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)
    doc_name = "?"

    if should_have_normative_rule_tag? then
      normative_rule_tag = normative_rule_tags.get_normative_rule_tag(link_name)
      unless normative_rule_tag.nil?
        doc_name = normative_rule_tag.doc_name
      end
    end

    return doc_name
  end

  # @param normative_rule_tags [NormativeRuleTags] Normative rule tags
  # @return String
  def to_section(normative_rule_tags)
    raise ArgumentError, "normative_rule_tags needs to be a NormativeRuleTags class but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)
    section = "?"

    if should_have_normative_rule_tag? then
      normative_rule_tag = normative_rule_tags.get_normative_rule_tag(link_name)
      unless normative_rule_tag.nil?
        section = "TBD" # Ask Tim Hutt!
      end
    end

    return section
  end

  # @param normative_rule_tags [NormativeRuleTags] Normative rule tags
  # @return String
  def to_excerpt(normative_rule_tags)
    raise ArgumentError, "normative_rule_tags needs to be a NormativeRuleTags class but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)
    excerpt = "<<#{link_name},#{link_name}>>"   # default

    if should_have_normative_rule_tag? then
      normative_rule_tag = normative_rule_tags.get_normative_rule_tag(link_name)
      unless normative_rule_tag.nil?
        excerpt = "<<#{link_name},#{link_name}>> => #{normative_rule_tag.tag_text}"
      end
    elsif link_name.start_with?("norm:enc:insttable:") then
      # These links are just to a table cell and the tag_text isn't available in the normative rule tags file.
      # So, just create a link with a nice name.
      inst_name = link_name.delete_prefix("norm:enc:insttable:")
      excerpt = "<<#{link_name},Link to opcode table entry for '#{inst_name}' instruction>>"
    end

    return excerpt
  end
end
end
