require "minitest/autorun"

$root ||= (Pathname.new(__FILE__) / ".." / ".." ).realpath

require_relative "../yaml_loader"

class TestYamlLoader < Minitest::Test

  def test_refs_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash

      obj1:
        $ref: "#/$defs/target2"

      obj2:
        $ref: "#/$defs/target2"
        target2: Should disappear

      obj3:
        target2: Should disappear
        $ref: "#/$defs/target2"

    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "hash" }, doc["obj2"])
    assert_equal({ "a" => "hash" }, doc["obj3"])
  end

  def test_refs_in_the_different_document
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
        $ref: "#{f1_path.basename}#/$defs/target2"

      obj2:
        $ref: "#{f1_path.basename}#/$defs/target2"
        target2: Should disappear

      obj3:
        target2: Should disappear
        $ref: "#{f1_path.basename}#/$defs/target2"
    YAML

    f2 = Tempfile.new("yml")
    f2.write(yaml2)
    f2.flush

    doc = YamlLoader.load(f2.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "hash" }, doc["obj2"])
    assert_equal({ "a" => "hash" }, doc["obj3"])
  end

  def test_mrefs_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1: A string
        target2:
          a: hash

      obj1:
        $mref: "#/$defs/target2"

      obj2:
        $mref: "#/$defs/target2"
        a: Should take precedence

      obj3:
        a: Should take precedence
        $mref: "#/$defs/target2"

    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_mrefs_in_the_different_document
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
        $mref: "#{f1_path.basename}#/$defs/target2"

      obj2:
        $mref: "#{f1_path.basename}#/$defs/target2"
        a: Should take precedence

      obj3:
        a: Should take precedence
        $mref: "#{f1_path.basename}#/$defs/target2"
    YAML

    f2 = Tempfile.new("yml")
    f2.write(yaml2)
    f2.flush

    doc = YamlLoader.load(f2.path)
    assert_equal({ "a" => "hash" }, doc["obj1"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj2"])
    assert_equal({ "a" => "Should take precedence" }, doc["obj3"])
  end

  def test_multi_mrefs_in_the_same_document
    yaml = <<~YAML
      $defs:
        target1:
          b: nice
        target2:
          a: hash

      obj1:
        $mref:
        - "#/$defs/target1"
        - "#/$defs/target2"

    YAML

    f = Tempfile.new("yml")
    f.write(yaml)
    f.flush

    doc = YamlLoader.load(f.path)
    assert_equal({ "a" => "hash", "b" => "nice" }, doc["obj1"])
  end

  def test_that_invalid_mrefs_raise
    yaml = <<~YAML
      $defs:
        target1:
          b: nice
        target2:
          a: hash

      obj1:
        $mref: "#/path/to/nowwhere"

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

end
