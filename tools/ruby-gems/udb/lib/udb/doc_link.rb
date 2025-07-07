# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Creates links into RISC-V documentation with the following formats for the destination link.
#
#   Documentation Format
#   ============  ===============================================================
#   ISA manuals   manual:ext:<ext_name>:<identifier>
#                 manual:inst:<inst_name>:<identifier>
#                 manual:insts:<inst_name>[_<inst_name>]+:<identifier>      List of instructions separated by "_"
#                 manual:instgrp:<group_name>:<identifier>                  Named group of insts (e.g., branch, load, store, etc.)
#                 manual:csr:<csr_name>:<identifier>
#                 manual:csr_field:<csr_name>:<field_name>:<identifier>
#                 manual:param:<ext_name>:<param_name>:<identifier>
#                   where <identifier> is a string that describes the tagged text
#   UDB doc       udb:doc:ext:<ext_name>
#                 udb:doc:ext_param:<ext_name>:<param_name>
#                 udb:doc:inst:<inst_name>
#                 udb:doc:csr:<csr_name>
#                 udb:doc:csr_field:<csr_name>:<field_name>
#                 udb:doc:func:<func_name>  (Documentation of common/built-in IDL functions)
#                 udb:doc:cov_pt:<org>:<id>
#                   where <org> is:
#                      sep for UDB documentation that "separates" normative rules from test plans
#                      combo for UDB documentation that "combines" normative rules with test plans
#                      appendix for UDB documentation that has normative rules and test plans in appendices
#                   where <id> is the ID of the normative rule
#   IDL code      idl:code:inst:<inst_name>:<location>
#                 TODO for CSR and CSR Fields
#
# Use underscores to replace blanks in names between colons since RISC-V uses minus signs in the names.
#
# Adding anchors into AsciiDoc files
# ==================================
#  1) Anchor to part of a paragraph
#     Syntax:      [#<anchor-name>]# ... #
#     Example:     Here is an example of [#foo]#anchoring part# of a paragraph
#                  and can have [#bar]multiple anchors# if needed.
#     Tagged text: "anchoring part" and "multiple anchors"
#     HTML:        <div class="paragraph">
#                  <p>Here is an example of <span id="foo">anchoring part</span> of a paragraph
#                  and can have [<mark>bar]multiple anchors</mark> if needed.</p>
#                  </div>
#     Example:    [#monkey]#Anchoring part of a paragraph#
#                 [#zebra]#and can have multiple anchors# if needed.
#                 and create a span for each one.
#     HTML:       <div class="paragraph">
#                 <p><span id="monkey">Anchoring part of a paragraph</span>
#                 <span id="zebra">and can have multiple anchors</span> if needed.
#                 and create a span for each one.</p>
#                 </div>
#     Limitations:
#       - Can't anchor text across multiple paragraphs.
#       - Must have text next to the 2nd hash symbol (i.e., can't have newline after [#<anchor-name]#).
#       - Can't put inside admonitions such as [NOTE] (see #3 below for solution).
#       - Seems to just use <span> for first anchor in paragraph and then either <span> or <mark> if more.
#         Still allows a tool to pull out the anchored text but has to handle both <span> and <mark>.
#
#  2) Anchor to entire paragraph
#     Syntax:     [[<anchor-name]]
#     Example:    [[zort]]
#                 Here is an example of anchoring a whole paragraph.
#     Tagged text: Entire paragraph
#     HTML:       <div id="zort" class="paragraph">
#                 <p>Here is an example of anchoring a whole paragraph.</p>
#                 </div>
#
#  3) Anchor inside admonition (e.g. [NOTE])
#     - Must use [[<anchor-name]] before each paragraph (with unique anchor names of course) being tagged
#     - Can't use [#<anchor-name]## since it just shows up in HTML as normal text
#     - Don't put [[<<anchor-name]] anchor before admonition to apply to entire admonition (one or more paragraphs)
#       since the HTML won't tag the text, just its location.
#
#  4) Anchor in table cell
#     - Must use [[<anchor-name]] after "|" and before cell contents and will tag all text in the cell.
#     Example:    |===
#                 |name|number
#
#                 |Bob|[[BobNumber]]415-555-1212
#                 |Pat| [[PatNumber]]  408-555-1212
#                 |===
#     Tagged text: "415-555-1212" and "  408-555-1212"
#     HTML:       <tr>
#                 <td class="tableblock"><p class="tableblock">Bob</p></td>
#                 <td class="tableblock"><p class="tableblock"><a id="BobNumber"></a>413-555-1212</p></td>
#                 </tr>
#                 <tr>
#                 <td class="tableblock"><p class="tableblock">Pat</p></td>
#                 <td class="tableblock"><p class="tableblock"><a id="PatNumber"></a>  408-555-1212</p></td>
#                 </tr>

class Udb::DocLink
  # @param dst_link [String] The documentation link provided in the YAML
  # @param db_obj [String] Database object
  def initialize(dst_link, db_obj)
    raise ArgumentError, "Need String but was passed a #{data.class}" unless dst_link.is_a?(String)
    @dst_link = dst_link

    raise ArgumentError, "Missing documentation link for #{db_obj.name} of kind #{db_obj.kind}" if @dst_link.nil?
  end

  # @return [String] Unique ID of the linked to normative rule
  def dst_link = @dst_link

  # @return [String] Asciidoc to create desired link.
  def to_adoc
    "<<#{@dst_link},#{@dst_link}>>"
  end
end
