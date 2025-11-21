# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "simplecov"
require "simplecov-cobertura"

UDB_ROOT = (Pathname.new(__dir__) / "..").realpath

require_relative "test_logic"
require_relative "test_conditions"
require_relative "test_cli"
require_relative "test_yaml_loader"
require_relative "test_cfg_arch"
