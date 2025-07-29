# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Creates links into RISC-V documentation with the following formats for the link name.
#
#   Documentation Format                                                  Applies
#   ============  ======================================================= ================================================
#   ISA manuals   norm:base:<base-name>:<identifier>                      Single base ISA (rv32i/rv32e/rv64i)
#                 norm:bases:<base-name>[_<base-name>]+:<identifier>      List of bases separated by "_"
#                 norm:basegrp:<group-name>:<identifier>                  Named group of bases (e.g., rv32, all)
#                 norm:ext:<ext-name>:<identifier>                        Single extension
#                 norm:exts:<ext-name>[_<ext-name>]:<identifier>          List of extensions separated by "_"
#                 norm:extgrp:<ext-name>:<identifier>                     Named group of extensions
#                 norm:enc:insttable:<inst-name>                          Instruction table cell for instruction encoding
#                 norm:inst:<inst-name>:<identifier>                      Single instruction
#                 norm:insts:<inst-name>[_<inst-name>]+:<identifier>      List of instructions separated by "_"
#                 norm:instgrp:<group-name>:<identifier>                  Named group of insts (e.g., branch, load, store, etc.)
#                 norm:csr:<csr-name>:<identifier>                        Single CSR
#                 norm:csr_field:<csr-name>:<field-name>:<identifier>     Single CSR field
#                 norm:param:<ext-name>:<param-name>:<identifier>
#                   where <identifier> is a string that describes the tagged text
#   UDB encoding  udb:enc:inst:<inst-name>
#   UDB doc       udb:doc:ext:<ext-name>
#                 udb:doc:inst:<inst-name>
#                 udb:doc:csr:<csr-name>
#                 udb:doc:csr_field:<csr-name>:<field-name>
#                 udb:doc:param:<ext-name>:<param-name>
#                 udb:doc:func:<func-name>  (Documentation of common/built-in IDL functions)
#                 udb:doc:covpt:<fmt>:<id>
#                   where <fmt> is:
#                      sep for UDB documentation that "separates" normative rules from test plans
#                      combo for UDB documentation that "combines" normative rules with test plans
#                      appendix for UDB documentation that has normative rules and test plans in appendices
#                   where <id> is the ID of the normative rule
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
  # @return [String] Link name to normative rule
  attr_reader :link_name

  # @param link_name [String] The documentation link provided in the YAML
  # @param db_obj [String] Database object
  def initialize(link_name, db_obj)
    raise ArgumentError, "Need String but was passed a #{data.class}" unless link_name.is_a?(String)
    @link_name = link_name

    raise ArgumentError, "Missing documentation link for #{db_obj.name} of kind #{db_obj.kind}" if @link_name.nil?
  end

  # @return [Boolean] Is link to an ISA manual normative rule?
  def is_isa_manual_norm_rule?
    # Include all links that start with "norm:" except for those in the instruction encoding table
    # since there isn't any point in copying the text in the link (just want a normal hypertext link into table).
    link_name.start_with?("norm:") && !link_name.start_with?("norm:enc:insttable:")
  end

  # @param normative_rule_tags [NormativeRuleTags] Provides access to text associated with normative rule tags.
  # @return [String],[Boolean] String contains Asciidoc to create desired link and
  #                            Boolean indicates if tried to find normative rule tag and couldn't find it.
  def to_adoc(normative_rule_tags)
    raise ArgumentError, "normative_rule_tags needs to be a NormativeRuleTags class but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)

    not_found = false
    str = "<<#{@link_name},#{@link_name}>>"   # default

    if link_name.start_with?("norm:") then
      if link_name.start_with?("norm:enc:insttable:") then
        # These links aren't currently useful so just make something that looks reasonable.
        inst_name = link_name.delete_prefix("norm:enc:insttable:")
        str = "<<#{@link_name},Link to opcode table entry for '#{inst_name}' instruction>>"
      elsif normative_rule_tags.tags_available? then
        norm_rule_tag = normative_rule_tags.get_norm_rule_tag(@link_name)
        if norm_rule_tag.nil?
          not_found = true
        else
          str = "<<#{@link_name},#{norm_rule_tag.tag_text}>>"
        end
      end
    end

    return str, not_found
  end
end
end
