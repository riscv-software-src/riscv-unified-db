# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "simplecov"

SimpleCov.start do
  enable_coverage :branch
end

puts "[SimpleCov] Coverage started."

require "minitest/autorun"

require_relative "test_expressions"

ExpressionTestFactory.create("Literals", "idl/literals.yaml")
ExpressionTestFactory.create("Expressions", "idl/expressions.yaml")
