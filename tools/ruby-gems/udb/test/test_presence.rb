# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "test_helper"

require_relative "../lib/udb/presence"

class TestPresence < Minitest::Test
  def test_from_yaml_accepts_known_string_values
    assert_equal Udb::Presence::Mandatory, Udb::Presence.from_yaml("mandatory")
    assert_equal Udb::Presence::Option, Udb::Presence.from_yaml("optional")
    assert_equal Udb::Presence::Option, Udb::Presence.from_yaml("option")
  end

  def test_from_yaml_rejects_unknown_string_values
    error = assert_raises(RuntimeError) do
      Udb::Presence.from_yaml("Mandatory")
    end

    assert_equal "Unrecognized presence string 'Mandatory'", error.message

    error = assert_raises(RuntimeError) do
      Udb::Presence.from_yaml("manditory")
    end

    assert_equal "Unrecognized presence string 'manditory'", error.message
  end
end
