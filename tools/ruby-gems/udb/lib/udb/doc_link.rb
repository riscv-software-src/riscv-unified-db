# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Creates links into RISC-V documentation with the following formats for the destination link.
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
#                 udb:doc:covpt:<org>:<id>
#                   where <org> is:
#                      sep for UDB documentation that "separates" normative rules from test plans
#                      combo for UDB documentation that "combines" normative rules with test plans
#                      appendix for UDB documentation that has normative rules and test plans in appendices
#                   where <id> is the ID of the normative rule
#   IDL code      idl:code:inst:<inst-name>:<location>
#                 TODO for CSR and CSR Fields
#
# Use underscores to replace blanks in names between colons since RISC-V uses minus signs in the names.
#
# Adding anchors into AsciiDoc files
# ==================================
#  1) Anchor to part of a paragraph or inside a table cell
#     Syntax:      [#<anchor-name>]# ... #
#     Example:     Here is an example of [#foo]#anchoring part# of a paragraph
#                  and can have [#bar]#multiple anchors# if needed.
#     Tagged text: "anchoring part" and "multiple anchors"
#     HTML:        <div class="paragraph">
#                  <p>Here is an example of <span id="foo">anchoring part</span> of a paragraph
#                  and can have <span id="bar">multiple anchors</span> if needed.</p>
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
