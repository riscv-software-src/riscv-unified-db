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
# For example use "_":
#   "manual:ext:I:R-type_operands"
#                       ^
#                       ^
# and not "-"
#   "manual:ext:I:R-type-operands"
#                       ^
#                       ^
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
