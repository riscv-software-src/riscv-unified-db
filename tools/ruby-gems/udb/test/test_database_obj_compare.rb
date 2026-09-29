# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "udb/obj/database_obj"

class TestDatabaseObjectCompare < Minitest::Test
  KIND = Udb::DatabaseObject::Kind

  def build(name, kind)
    obj = Udb::DatabaseObject.allocate
    obj.instance_variable_set(:@name, name)
    obj.instance_variable_set(:@kind, kind)
    obj
  end

  def test_same_kind_compares_by_name
    a = build("aaa", KIND::Csr)
    b = build("bbb", KIND::Csr)

    assert_equal(-1, a <=> b)
    assert_equal(1, b <=> a)
    assert_equal(0, a <=> build("aaa", KIND::Csr))
  end

  def test_sort_of_same_kind_objects
    objs = [build("ccc", KIND::Csr), build("aaa", KIND::Csr), build("bbb", KIND::Csr)]

    assert_equal %w[aaa bbb ccc], objs.sort.map(&:name)
  end

  def test_different_kind_returns_nil
    a = build("aaa", KIND::Csr)
    b = build("bbb", KIND::CsrField)

    assert_nil(a <=> b)
  end

  def test_non_database_object_returns_nil
    assert_nil(build("aaa", KIND::Csr) <=> "not a database object")
  end
end
