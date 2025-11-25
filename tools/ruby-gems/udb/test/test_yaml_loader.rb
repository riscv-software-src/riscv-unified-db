# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "test_helper"

require "English"
require "fileutils"
require "open3"
require "tmpdir"
require "yaml"

require_relative "../lib/udb/resolver"

class TestYamlLoader < Minitest::Test
  UDB_GEM_PATH = Bundler.definition.specs.find { |s| s.name == "udb" }.full_gem_path

  def resolve_yaml(yaml)
    Dir.mktmpdir do |dir|
      arch_dir = Pathname.new(dir) / "arch"
      resolved_dir = Pathname.new(dir) / "resolved_arch"
      test_dir = arch_dir / "test"
      FileUtils.mkdir_p test_dir

      File.write(test_dir / "test.yaml", yaml)

      stdout, stderr, status =
        Dir.chdir(Udb.repo_root) do
          Open3.capture3("/opt/venv/bin/python3 #{UDB_GEM_PATH}/python/yaml_resolver.py resolve --no-progress --no-checks #{arch_dir} #{resolved_dir}")
        end
      # puts stdout
      # puts stderr
      # puts status

      if status.to_i.zero?
        YAML.load_file(resolved_dir / "test" / "test.yaml")
      end
    end
  end

  def resolve_multi_yaml(*yamls)
    Dir.mktmpdir do |dir|
      arch_dir = Pathname.new(dir) / "arch"
      resolved_dir = Pathname.new(dir) / "resolved_arch"
      test_dir = arch_dir / "test"
      FileUtils.mkdir_p test_dir

      yamls.each_index do |i|
        yaml = yamls[i]
        yamls.size.times do |j|
          yaml = yaml.gsub("YAML#{j + 1}_REL_PATH", "test/test#{j + 1}.yaml")
        end
        File.write(test_dir / "test#{i + 1}.yaml", yaml)
      end

      system "/opt/venv/bin/python3 #{UDB_GEM_PATH}/python/yaml_resolver.py resolve --no-checks #{arch_dir} #{resolved_dir}"

      if $CHILD_STATUS == 0
        YAML.load_file(resolved_dir / "test" / "test1.yaml")
      end
    end
  end

  def test_remove
    yaml = <<~YAML
      base:
        key1: value1
        key2: value2

      child:
        $inherits: "#/base"
        $remove: key2
        key3: value3
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/base", "key1" => "value1", "key3" => "value3" }, doc["child"])
  end

  def test_multiple_remove
    yaml = <<~YAML
      base:
        key1: value1
        key2: value2
        key3: value3

      child:
        $inherits: "#/base"
        $remove:
        - key2
        - key3
        key4: value4
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/base", "key1" => "value1", "key4" => "value4" }, doc["child"])
  end

  def test_that_inherits_with_nested_replace_works
    yaml = <<~YAML
      base:
        key1:
          sub_key1: value1
        key2: value2

      middle:
        $inherits: "#/base"
        key3: value3
        key4: value4

      bottom:
        $inherits:
        - "#/middle"
        key1:
          sub_key6: value6
        key2: value2_new
        key4: value4_new
        key5: value5
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => ["#/middle"], "key1" => { "sub_key1" => "value1", "sub_key6" => "value6" }, "key2" => "value2_new", "key3" => "value3", "key4" => "value4_new", "key5" => "value5" }, doc["bottom"])
  end

  def test_that_recursive_inherits_works
    yaml = <<~YAML
      base:
        key1: value1
        key2: value2

      middle:
        $inherits: "#/base"
        key3: value3
        key4: value4

      bottom:
        $inherits: "#/middle"
        key2: value2_new
        key4: value4_new
        key5: value5
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/base", "$parent_of" => "test/test.yaml#/bottom", "key1" => "value1", "key2" => "value2", "key3" => "value3", "key4" => "value4" }, doc["middle"])
    assert_equal({ "$child_of" => "#/middle", "key1" => "value1", "key2" => "value2_new", "key3" => "value3", "key4" => "value4_new", "key5" => "value5" }, doc["bottom"])
  end

  def test_that_nested_inherits_works
    yaml = <<~YAML
      top:
        base:
          key1: value1
          key2: value2
          key3: value3

      bottom:
        child:
          $inherits: "#/top/base"
          key3: value3_new
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/top/base", "key1" => "value1", "key2" => "value2", "key3" => "value3_new" }, doc["bottom"]["child"])
  end

  def test_that_inherits_doesnt_delete_keys
    yaml = <<~YAML
      base:
        key1: value1
        key2: value2
        key3: value3

      child:
        $inherits: "#/base"
        key3: value3_new
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/base", "key1" => "value1", "key2" => "value2", "key3" => "value3_new" }, doc["child"])
  end

  def test_that_double_inherits_doesnt_delete_keys
    yaml = <<~YAML
      base1:
        key1: value1
        key2: value2
        key3: value3

      base2:
        key4: value4
        key5: value5
        key6: value6

      child:
        $inherits:
        - "#/base1"
        - "#/base2"
        key3: value3_new
        key6: value6_new
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => ["#/base1", "#/base2"], "key1" => "value1", "key2" => "value2", "key3" => "value3_new", "key4" => "value4", "key5" => "value5", "key6" => "value6_new" }, doc["child"])
  end

  def test_inherits_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash

      obj1:
        $inherits: "#/$defs/target2"

      obj2:
        $inherits: "#/$defs/target2"
        a: Should take precedence

      obj3:
        a: Should take precedence
        $inherits: "#/$defs/target2"
    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => "#/$defs/target2", "a" => "hash" }, doc["obj1"])
    assert_equal({ "$child_of" => "#/$defs/target2", "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "$child_of" => "#/$defs/target2", "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_inherits_in_the_different_document
    yaml2 = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash
    YAML

    yaml1 = <<~YAML
      obj1:
        $inherits: "YAML2_REL_PATH#/$defs/target2"

      obj2:
        $inherits: "YAML2_REL_PATH#/$defs/target2"
        a: Should take precedence

      obj3:
        a: Should take precedence
        $inherits: "YAML2_REL_PATH#/$defs/target2"
    YAML

    doc = resolve_multi_yaml(yaml1, yaml2)
    refute_nil(doc)
    assert_equal({ "$child_of" => "test/test2.yaml#/$defs/target2", "a" => "hash" }, doc["obj1"])
    assert_equal({ "$child_of" => "test/test2.yaml#/$defs/target2", "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "$child_of" => "test/test2.yaml#/$defs/target2", "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_inherits_entire_object
    yaml2 = <<~YAML
      target1: A string
      target2:
        a: hash
        sub1:
          key_a: old_value_a
          key_b: old_value_b
    YAML

    yaml1 = <<~YAML
      $inherits: "YAML2_REL_PATH#"
      target1: Should take precedence
      target2:
        sub1:
          key_a: new_value_a
    YAML

    doc = resolve_multi_yaml(yaml1, yaml2)
    refute_nil(doc)
    assert_equal("test/test2.yaml#", doc["$child_of"])
    assert_equal("Should take precedence", doc["target1"])
    assert_equal({ "a" => "hash", "sub1" => { "key_a" => "new_value_a", "key_b" => "old_value_b" } }, doc["target2"])
  end

  def test_multi_inherits_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1:
          b: nice
        target2:
          a: hash

      obj1:
        $inherits:
        - "#/$defs/target1"
        - "#/$defs/target2"

    YAML

    doc = resolve_yaml(yaml)
    refute_nil(doc)
    assert_equal({ "$child_of" => ["#/$defs/target1", "#/$defs/target2"], "a" => "hash", "b" => "nice" }, doc["obj1"])
  end

  def test_that_invalid_inherits_raise
    yaml = <<~YAML
      $defs:
        target1:
          b: nice
        target2:
          a: hash

      obj1:
        $inherits: "#/path/to/nowwhere"

    YAML

    doc = resolve_yaml(yaml)
    assert_nil doc
  end

  # Commented out until https://github.com/riscv-software-src/riscv-unified-db/issues/369 is fixed.
#   def test_copy_in_the_same_document
#     yaml = <<~YAML
#       $defs:
#         target1: A string
#         target2:
#           a: hash
#         target3: Another string
#
#       obj1:
#         target10: abc
#         target11:
#           $copy: "#/$defs/target1"
#         target12: def
#         target13:
#           $copy: "#/$defs/target3"
#
#     YAML
#
#     doc = resolve_yaml(yaml)
#     assert_equal({
#         "$child_of" => "#/$defs",
#         "target10"  => "abc",
#         "target11"  => "A string",
#         "target12"  => "def",
#         "target13"  => "Another string"
#       }, doc["obj1"])
#   end
#
#   def test_copy_in_the_different_document
#     yaml2 = <<~YAML
#       $defs:
#         target1: A string
#         target2:
#           a: hash
#         target3: Another string
#     YAML
#
#     yaml1 = <<~YAML
#       obj1:
#         target10: abc
#         target11:
#           $copy: "YAML2_REL_PATH#/$defs/target1"
#         target12: def
#         target13:
#           $copy: "YAML2_REL_PATH#/$defs/target3"
#     YAML
#
#     doc = resolve_multi_yaml(yaml1, yaml2)
#     assert_equal({
#         "$child_of" => "test/test2.yaml#/$defs",
#         "target10"  => "abc",
#         "target11"  => "A string",
#         "target12"  => "def",
#         "target13"  => "Another string"
#       }, doc["obj1"])
#   end
end
