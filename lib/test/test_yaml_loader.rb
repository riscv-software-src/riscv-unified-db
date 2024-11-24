
require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." ).realpath

require_relative "../yaml_loader"

class TestYamlLoader < Minitest::Test


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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key3" => "value3" }, doc["child"])
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
    
    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key4" => "value4" }, doc["child"])
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
        - "#/base"
        - "#/middle"
        key1:
          sub_key6: value6
        key2: value2_new
        key4: value4_new
        key5: value5
    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => {"sub_key1" => "value1", "sub_key6" => "value6"}, "key2" => "value2_new", "key3" => "value3", "key4" => "value4_new", "key5" => "value5" }, doc["bottom"])
  end

  def test_that_spurious_recursive_inherits_works
    yaml = <<~YAML
      base:
        key1: value1
        key2: value2

      middle:
        $inherits: "#/base"
        key3: value3
        key4: value4

      bottom:
        $inherits:
        - "#/base"
        - "#/middle"
        key2: value2_new
        key4: value4_new
        key5: value5
    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key2" => "value2", "key3" => "value3", "key4" => "value4" }, doc["middle"])
    assert_equal({ "key1" => "value1", "key2" => "value2_new", "key3" => "value3", "key4" => "value4_new", "key5" => "value5" }, doc["bottom"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key2" => "value2", "key3" => "value3", "key4" => "value4" }, doc["middle"])
    assert_equal({ "key1" => "value1", "key2" => "value2_new", "key3" => "value3", "key4" => "value4_new", "key5" => "value5" }, doc["bottom"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key2" => "value2", "key3" => "value3_new" }, doc["bottom"]["child"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key2" => "value2", "key3" => "value3_new" }, doc["child"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "key1" => "value1", "key2" => "value2", "key3" => "value3_new", "key4" => "value4", "key5" => "value5", "key6" => "value6_new" }, doc["child"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_inherits_in_the_different_document
    yaml1 = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash
    YAML

    f1 = Tempfile.new("yml")
    f1.write(yaml1)
    f1.flush
    f1_path = Pathname.new(f1.path)

    yaml2 = <<~YAML
      obj1:
        $inherits: "#{f1_path.basename}#/$defs/target2"

      obj2:
        $inherits: "#{f1_path.basename}#/$defs/target2"
        a: Should take precedence

      obj3:
        a: Should take precedence
        $inherits: "#{f1_path.basename}#/$defs/target2"
    YAML

    f2 = Tempfile.new("yml")
    f2.write(yaml2)
    f2.flush

    doc = YamlLoader.load(f2.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_inherits_entire_object
    yaml1 = <<~YAML
      target1: A string
      target2:
        a: hash
    YAML

    f1 = Tempfile.new("yml")
    f1.write(yaml1)
    f1.flush
    f1_path = Pathname.new(f1.path)

    yaml2 = <<~YAML
      $inherits: "#{f1_path.basename}#"

      target1: Should take precedence
    YAML

    f2 = Tempfile.new("yml")
    f2.write(yaml2)
    f2.flush

    doc = YamlLoader.load(f2.path)
    assert_equal("Should take precedence", doc["target1"])
    assert_equal({ "a" => "hash" }, doc["target2"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash", "b" => "nice" }, doc["obj1"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    assert_raises(YamlLoader::DereferenceError) { YamlLoader.load(f.path) }
  end

  def test_that_invalid_refs_raise
    yaml = <<~YAML
      $defs:
        target1:
          b: nice
        target2:
          a: hash

      obj1:
        $ref: "#/path/to/nowwhere"

    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    assert_raises(YamlLoader::DereferenceError) { YamlLoader.load(f.path) }
  end

  def test_copy_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash
        target3: Another string

      obj1:
        target10: abc
        target11: 
          $copy: "#/$defs/target1"
        target12: def
        target13: 
          $copy: "#/$defs/target3"

    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ 
        "target10" => "abc", 
        "target11" => "A string", 
        "target12" => "def", 
        "target13" => "Another string" 
      }, doc["obj1"])
  end

  def test_copy_in_the_different_document
    yaml1 = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash
        target3: Another string
    YAML

    f1 = Tempfile.new("yml")
    f1.write(yaml1)
    f1.flush
    f1_path = Pathname.new(f1.path)

    yaml2 = <<~YAML
      obj1:
        target10: abc
        target11: 
          $copy: "#{f1_path.basename}#/$defs/target1"
        target12: def
        target13: 
          $copy: "#{f1_path.basename}#/$defs/target3"
    YAML

    f2 = Tempfile.new("yml")
    f2.write(yaml2)
    f2.flush

    doc = YamlLoader.load(f2.path)
    assert_equal({ 
        "target10" => "abc", 
        "target11" => "A string", 
        "target12" => "def", 
        "target13" => "Another string" 
      }, doc["obj1"])
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

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash", "b" => "nice" }, doc["obj1"])
  end


end
