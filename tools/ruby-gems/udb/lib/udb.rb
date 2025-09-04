# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

module Udb; end

require_relative "udb/normative_rules"
require_relative "udb/cert_test_procedure"
require_relative "udb/doc_link"
require_relative "udb/exception_code"
require_relative "udb/req_expression"
require_relative "udb/schema"
require_relative "udb/version"

require_relative "udb/obj/can_have_normative_rule_reqs"
require_relative "udb/obj/can_define_coverage_points"
require_relative "udb/obj/can_define_cert_test_procedures"
require_relative "udb/obj/certificate"
require_relative "udb/obj/csr_field"
require_relative "udb/obj/csr"
require_relative "udb/obj/database_obj"
require_relative "udb/obj/extension"
require_relative "udb/obj/instruction"
require_relative "udb/obj/manual"
require_relative "udb/obj/parameter"
require_relative "udb/obj/portfolio"
