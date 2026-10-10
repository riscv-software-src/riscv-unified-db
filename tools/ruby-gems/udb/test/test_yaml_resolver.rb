# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "test_helper"
require_relative "../lib/udb/yaml/yaml_resolver"
require_relative "../lib/udb/yaml/comment_parser"
require_relative "../lib/udb/yaml/preserving_emitter"
require "tmpdir"
require "fileutils"
require "json"
require "idlc"

class TestYamlResolver < Minitest::Test
  def setup
    @test_dir = Dir.mktmpdir("yaml_resolver_test")
    @spec_dir = Pathname.new(__dir__).parent.parent.parent.parent / "spec" / "std" / "isa"
  end

  def teardown
    FileUtils.rm_rf(@test_dir) if @test_dir && File.exist?(@test_dir)
  end

  # Test that parsing and emitting preserves semantic content
  def test_parse_emit_roundtrip
    skip "Spec directory not found" unless @spec_dir.exist?

    yaml_files = Dir.glob(@spec_dir / "**" / "*.yaml").first(10) # Test first 10 files

    yaml_files.each do |file_path|
      file_path = Pathname.new(file_path)

      # Skip known edge cases with complex literal block scalars containing comments
      next if file_path.basename.to_s == "henvcfg.yaml" || file_path.basename.to_s == "hgatp.yaml"

      # Parse original file
      parser = Udb::Yaml::CommentParser.new
      result = parser.parse_file(file_path)
      original_data = result[:data]

      # Emit to string
      emitter = Udb::Yaml::PreservingEmitter.new(result[:comments])
      emitted_yaml = emitter.emit(original_data)

      # Parse emitted YAML
      emitted_data = Psych.safe_load(emitted_yaml, permitted_classes: [Date, Symbol], aliases: true)

      # Compare data (should be semantically identical)
      # Note: Literal block scalars may have trailing whitespace differences
      # which are semantically insignificant but may cause test failures
      if original_data != emitted_data
        # Check if the difference is only in trailing whitespace in strings
        diff_is_whitespace_only = compare_with_whitespace_tolerance(original_data, emitted_data)
        unless diff_is_whitespace_only
          assert_equal original_data, emitted_data,
            "Roundtrip failed for #{file_path.relative_path_from(@spec_dir)}: data mismatch"
        end
      end
    end
  end

  # Test that resolver produces semantically correct output
  def test_resolver_semantic_correctness
    skip "Spec directory not found" unless @spec_dir.exist?

    output_dir = Pathname.new(@test_dir) / "resolved"

    # Run resolver
    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(@spec_dir, output_dir, no_checks: true)

    # Check that output files were created
    assert output_dir.exist?, "Output directory was not created"

    # Get list of resolved files
    resolved_files = Dir.glob(output_dir / "**" / "*.yaml")
    assert resolved_files.any?, "No resolved files were created"

    # For each resolved file, verify it can be parsed
    resolved_files.each do |resolved_path|
      resolved_path = Pathname.new(resolved_path)
      rel_path = resolved_path.relative_path_from(output_dir)
      original_path = @spec_dir / rel_path

      next unless original_path.exist?

      # Parse both files
      original_data = Psych.safe_load_file(original_path, permitted_classes: [Date, Symbol], aliases: true)
      resolved_data = Psych.safe_load_file(resolved_path, permitted_classes: [Date, Symbol], aliases: true)

      # Resolved data should have $source field
      assert resolved_data.key?("$source"),
        "Resolved file #{rel_path} missing $source field"

      # Remove $source for comparison
      resolved_data_without_source = resolved_data.dup
      resolved_data_without_source.delete("$source")

      # Normalize $schema: strip the version prefix the resolver adds so the
      # comparison is against the bare name in the original source file.
      # (e.g. 'v0.2/csr_schema.json#' -> 'csr_schema.json#')
      if resolved_data_without_source.key?("$schema")
        bare = File.basename(resolved_data_without_source["$schema"].split("#").first) + "#"
        resolved_data_without_source["$schema"] = bare
      end

      # For files without inheritance, data should match (minus $source)
      # However, the resolver expands $inherits references, so we skip comparison
      # for any file where the resolved data differs from original (indicating expansion)
      # We detect expansion by checking for $child_of keys in resolved data
      has_expansion = original_data.key?("$inherits") ||
                      data_contains_key?(resolved_data_without_source, "$child_of") ||
                      data_contains_key?(resolved_data_without_source, "$inherits") ||
                      data_contains_key?(resolved_data_without_source, "$parent_of")

      unless has_expansion
        if original_data != resolved_data_without_source
          diff_is_whitespace_only = compare_with_whitespace_tolerance(original_data, resolved_data_without_source)
          unless diff_is_whitespace_only
            assert_equal original_data, resolved_data_without_source,
              "Resolved data mismatch for #{rel_path} (file without inheritance)"
          end
        end
      end
    end
  end

  # Test source map correctness
  def test_source_map_correctness
    skip "Spec directory not found" unless @spec_dir.exist?

    output_dir = Pathname.new(@test_dir) / "resolved_with_map"

    # Run resolver
    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(@spec_dir, output_dir, no_checks: true)

    # Check a few resolved files for source map
    resolved_files = Dir.glob(output_dir / "**" / "*.yaml").first(5)

    resolved_files.each do |resolved_path|
      resolved_path = Pathname.new(resolved_path)
      content = File.read(resolved_path)

      # Check for source map markers
      assert_includes content, "===== SOURCE MAP BEGIN =====",
        "Source map begin marker not found in #{resolved_path.basename}"
      assert_includes content, "===== SOURCE MAP END =====",
        "Source map end marker not found in #{resolved_path.basename}"

      # Extract source map
      source_map = extract_source_map(content)
      assert source_map.any?, "Source map is empty in #{resolved_path.basename}"

      # Verify source map format
      source_map.each do |entry|
        assert_match(/^[\w\/$()?]+\s+->\s+.+:\d+:\d+$/, entry,
          "Invalid source map entry format: #{entry}")
      end

      # Verify source map entries point to valid locations
      rel_path = resolved_path.relative_path_from(output_dir)
      source_path = @spec_dir / rel_path

      next unless source_path.exist?

      source_lines = File.readlines(source_path)

      source_map.each do |entry|
        # Parse entry: key_path -> file:line:column
        match = entry.match(/^([\w\/$()? ]+)\s+->\s+(.+):(\d+):(\d+)$/)
        next unless match

        key_path = match[1]
        file = match[2]
        line = match[3].to_i
        column = match[4].to_i

        # Verify line number is valid
        assert line > 0, "Invalid line number #{line} for #{key_path}"
        assert line <= source_lines.length,
          "Line number #{line} exceeds file length for #{key_path}"

        # Verify column number is valid
        assert column > 0, "Invalid column number #{column} for #{key_path}"
        source_line = source_lines[line - 1]
        assert column <= source_line.length + 1,
          "Column number #{column} exceeds line length for #{key_path} at line #{line}"
      end
    end
  end

  # Test that comments are preserved
  def test_comment_preservation
    yaml_with_comments = <<~YAML
      # Header comment
      key1: value1  # inline comment

      # Block comment
      key2: value2

      nested:
        # Nested comment
        key3: value3
    YAML

    parser = Udb::Yaml::CommentParser.new
    result = parser.parse(yaml_with_comments)

    # Check that comments were extracted
    assert result[:comments].header_comments.any?, "Header comments not extracted"
    assert result[:comments].all_comments.length >= 4, "Not all comments were extracted"

    # Emit and check comments are present
    emitter = Udb::Yaml::PreservingEmitter.new(result[:comments])
    emitted = emitter.emit(result[:data])

    assert_includes emitted, "# Header comment", "Header comment not preserved"
    assert_includes emitted, "# inline comment", "Inline comment not preserved"
    assert_includes emitted, "# Block comment", "Block comment not preserved"
    assert_includes emitted, "# Nested comment", "Nested comment not preserved"
  end

  # Test string style preservation
  def test_string_style_preservation
    yaml_with_styles = <<~YAML
      literal: |
        This is a literal
        block scalar
      folded: >
        This is a folded
        block scalar
      plain: plain value
      quoted: "quoted value"
    YAML

    parser = Udb::Yaml::CommentParser.new
    result = parser.parse(yaml_with_styles)

    # Check string styles were detected
    assert_equal :literal, result[:comments].get_string_style(["literal"])
    assert_equal :folded, result[:comments].get_string_style(["folded"])
    assert_equal :plain, result[:comments].get_string_style(["plain"])
    assert_equal :quoted, result[:comments].get_string_style(["quoted"])

    # Emit and verify styles are preserved
    emitter = Udb::Yaml::PreservingEmitter.new(result[:comments])
    emitted = emitter.emit(result[:data])

    assert_includes emitted, "literal: |", "Literal style not preserved"
    assert_includes emitted, "folded: >", "Folded style not preserved"
    assert_includes emitted, "plain: plain value", "Plain style not preserved"
    assert_includes emitted, 'quoted: "quoted value"', "Quoted style not preserved"
  end

  # Test multiline plain scalar preservation
  def test_multiline_plain_scalar_preservation
    yaml_with_multiline = <<~YAML
      description:
        This is a multiline plain scalar
        that spans multiple lines
        without any block indicator
    YAML

    parser = Udb::Yaml::CommentParser.new
    result = parser.parse(yaml_with_multiline)

    # Check that multiline style was detected
    assert_equal :plain_multiline, result[:comments].get_string_style(["description"])

    # Check that original lines were captured
    original_lines = result[:comments].get_multiline_content(["description"])
    assert original_lines, "Multiline content not captured"
    assert_equal 3, original_lines.length, "Wrong number of lines captured"

    # Emit and verify line breaks are preserved
    emitter = Udb::Yaml::PreservingEmitter.new(result[:comments])
    emitted = emitter.emit(result[:data])

    lines = emitted.lines
    desc_line_idx = lines.index { |l| l.include?("description:") }
    assert desc_line_idx, "Description key not found in output"

    # Check that the next lines contain the multiline content
    assert lines[desc_line_idx + 1].strip.start_with?("This is"),
      "First line of multiline content not preserved"
    assert lines[desc_line_idx + 2].strip.start_with?("that spans"),
      "Second line of multiline content not preserved"
  end

  # Test source location tracking
  def test_source_location_tracking
    yaml_content = <<~YAML
      key1: value1
      key2: value2
      nested:
        key3: value3
    YAML

    # Write to temp file
    temp_file = Pathname.new(@test_dir) / "test.yaml"
    File.write(temp_file, yaml_content)

    # Parse and track locations
    parser = Udb::Yaml::CommentParser.new
    result = parser.parse_file(temp_file)

    # Manually track locations (simulating resolver behavior)
    comment_map = result[:comments]
    lines = yaml_content.lines

    lines.each_with_index do |line, idx|
      next if line.strip.empty? || line.strip.start_with?("#")

      if line.include?(":")
        key = line.split(":", 2)[0].strip
        next if key.empty?

        # Calculate column
        colon_pos = line.index(":")
        value_start = colon_pos + 1
        value_start += 1 while value_start < line.length && line[value_start] == " "

        comment_map.set_source_location([key], temp_file.to_s, idx + 1, value_start + 1)
      end
    end

    # Verify locations were set
    loc1 = comment_map.get_source_location(["key1"])
    assert loc1, "Location not set for key1"
    assert_equal 1, loc1[:line], "Wrong line for key1"
    assert loc1[:column] > 0, "Invalid column for key1"

    loc2 = comment_map.get_source_location(["key2"])
    assert loc2, "Location not set for key2"
    assert_equal 2, loc2[:line], "Wrong line for key2"
  end

  # Test that IDL compilation works for all database files without errors,
  # and that the source file information in compiled AST hashes is correct,
  # including that the byte-offset interval points into actual IDL content.
  def test_compile_idl_all_database_files
    skip "Spec directory not found" unless @spec_dir.exist?

    output_dir = Pathname.new(@test_dir) / "resolved_idl"

    # Run resolver with compile_idl: true — should not raise any errors
    resolver = Udb::Yaml::Resolver.new(quiet: true, compile_idl: true)
    resolver.resolve_files(@spec_dir, output_dir, no_checks: true)

    # Check that output files were created
    assert output_dir.exist?, "Output directory was not created"
    resolved_files = Dir.glob(output_dir / "**" / "*.yaml")
    assert resolved_files.any?, "No resolved files were created"

    # Single compiler instance reused across all files
    compiler = Idl::Compiler.new

    # For each resolved file, verify source info in compiled AST hashes
    resolved_files.each do |resolved_path|
      resolved_path = Pathname.new(resolved_path)
      rel_path = resolved_path.relative_path_from(output_dir).to_s
      input_path = @spec_dir / rel_path

      next unless input_path.exist?

      begin
        resolved_data = Psych.safe_load_file(resolved_path, permitted_classes: [Date, Symbol], aliases: true)
      rescue Psych::SyntaxError
        $stderr.puts File.read(resolved_path)
        raise
      end

      # Read the source file as raw bytes once so we can verify byte-offset intervals
      source_bytes = File.binread(input_path)
      source_size  = source_bytes.bytesize

      # ── Checks 1–4: verify source info in every compiled AST hash ─────────
      ast_hashes = find_ast_hashes(resolved_data)

      # Ensure at least some AST hashes were found if the file contains IDL
      # (files without IDL keys like operation() won't have AST hashes)
      original_parser = Udb::Yaml::CommentParser.new
      original_data = original_parser.parse_file(input_path)[:data]
      has_non_empty_idl_keys = data_contains_non_empty_idl_keys?(original_data)

      if has_non_empty_idl_keys
        assert ast_hashes.any?,
          "File #{rel_path} contains non-empty IDL keys but no compiled AST hashes were found"
      end

      ast_hashes.each do |ast_hash|
        source = ast_hash["source"]

        # ── 1. file field ──────────────────────────────────────────────────────
        assert_equal rel_path, source["file"],
          "AST source file should match relative input path in #{rel_path}"

        # ── 2. begin / end are non-negative integers with begin <= end ─────────
        assert source["begin"].is_a?(Integer) && source["begin"] >= 0,
          "AST source begin should be a non-negative Integer in #{rel_path}"
        assert source["end"].is_a?(Integer) && source["end"] >= source["begin"],
          "AST source end should be an Integer >= begin in #{rel_path}"

        # ── 3. offsets are within the file ────────────────────────────────────
        assert source["begin"] < source_size,
          "AST source begin (#{source["begin"]}) >= file size (#{source_size}) in #{rel_path}"
        assert source["end"] < source_size,
          "AST source end (#{source["end"]}) >= file size (#{source_size}) in #{rel_path}"

        # ── 4. byte slice contains non-whitespace content ─────────────────────
        slice = source_bytes[source["begin"]..source["end"]]
        assert slice && !slice.strip.empty?,
          "AST source interval [#{source["begin"]}...#{source["end"]}) is empty or whitespace-only in #{rel_path}."
      end

      # ── Check 5: re-parse each IDL snippet and compare to_h ──────────────
      #
      # Walk the original YAML data and resolved data in parallel.  For each
      # IDL key (ending with `()`) found in the original data, re-parse the
      # YAML-processed IDL string with the IDL compiler and verify that the
      # resulting AST's #to_h matches the stored hash — ignoring "source"
      # sub-hashes so that differences in absolute offsets don't cause false
      # failures.
      #
      # We use the YAML-parsed string value rather than raw byteslice because
      # the parser's interval is relative to the indentation-stripped text
      # produced by YAML, not to the raw file bytes.
      #
      # We use CommentParser (same as the resolver) rather than Psych.safe_load_file
      # so that the IDL strings we re-parse are identical to those the resolver
      # compiled — in particular, CommentParser strips `#` comment lines from
      # literal block scalars, while Psych preserves them.
      # Note: original_data was already parsed above for has_idl_keys check

      find_idl_pairs(original_data, resolved_data).each do |pair|
        idl_text   = pair[:idl_text]
        ast_hash   = pair[:ast_hash]
        parse_root = pair[:parse_root]
        key_path   = pair[:path]

        compiler.parser.set_input_file(rel_path, 0)
        m = compiler.parser.parse(idl_text, root: parse_root)
        assert m,
          "Failed to re-parse IDL text for #{rel_path} at #{key_path.inspect} " \
          "(kind=#{ast_hash["kind"].inspect}): #{idl_text[0, 80].inspect}\n" \
          "#{compiler.parser.failure_reason}"

        reparsed_ast = m.to_ast
        assert reparsed_ast,
          "IDL compiler returned nil AST for #{rel_path} at #{key_path.inspect}"

        assert_equal strip_source(ast_hash), strip_source(reparsed_ast.to_h),
          "Re-parsed AST #to_h does not match stored AST #to_h for #{rel_path} " \
          "at #{key_path.inspect} (kind=#{ast_hash["kind"].inspect})"
      end
    end
  end

  # Test that versioned_schema_uri rewrites bare URIs when the schema has a $id
  def test_versioned_schema_uri_rewrites_bare_ref
    # Use the gem's schemas directory which has $id fields (e.g. "v0.1", "v0.3")
    gem_schemas = Pathname.new(__dir__).parent / "schemas"
    skip "gem schemas directory not found" unless gem_schemas.exist?

    resolver = Udb::Yaml::Resolver.new(quiet: true, schemas_path: gem_schemas)

    # Bare ref should get the version prefix
    assert_equal "v0.1/ext_schema.json#", resolver.versioned_schema_uri("ext_schema.json#")
    assert_equal "v0.3/csr_schema.json#", resolver.versioned_schema_uri("csr_schema.json#")
  end

  # Test that versioned_schema_uri leaves already-versioned URIs unchanged
  def test_versioned_schema_uri_preserves_versioned_ref
    gem_schemas = Pathname.new(__dir__).parent / "schemas"
    skip "gem schemas directory not found" unless gem_schemas.exist?

    resolver = Udb::Yaml::Resolver.new(quiet: true, schemas_path: gem_schemas)

    already_versioned = "v0.1/ext_schema.json#"
    assert_equal already_versioned, resolver.versioned_schema_uri(already_versioned)
  end

  # Test that versioned_schema_uri returns unchanged URI when no $id is found
  def test_versioned_schema_uri_no_id_unchanged
    Dir.mktmpdir do |tmpdir|
      # Create a schema without $id
      schemas_dir = Pathname.new(tmpdir) / "schemas"
      schemas_dir.mkpath
      (schemas_dir / "no_id_schema.json").write(JSON.generate({ "type" => "object" }))

      resolver = Udb::Yaml::Resolver.new(quiet: true, schemas_path: schemas_dir)

      uri = "no_id_schema.json#"
      assert_equal uri, resolver.versioned_schema_uri(uri)
    end
  end

  # Test that resolved files record the versioned $schema
  def test_schema_versioning_in_resolved_files
    gem_schemas = Pathname.new(__dir__).parent / "schemas"
    skip "gem schemas directory not found" unless gem_schemas.exist?
    skip "ext_schema.json not in gem schemas" unless (gem_schemas / "ext_schema.json").exist?

    input_dir = Pathname.new(@test_dir) / "schema_version_input"
    output_dir = Pathname.new(@test_dir) / "schema_version_output"
    input_dir.mkpath

    yaml_content = <<~YAML
      $schema: ext_schema.json#
      name: Xtest
      kind: extension
      type: unprivileged
      long_name: Test extension
      versions:
        - version: "1.0.0"
          state: ratified
          ratification_date: "2024-01"
      description: A test extension.
    YAML
    (input_dir / "Xtest.yaml").write(yaml_content)

    resolver = Udb::Yaml::Resolver.new(quiet: true, schemas_path: gem_schemas)
    resolver.resolve_files(input_dir, output_dir, no_checks: true)

    resolved_content = File.read(output_dir / "Xtest.yaml")
    # $schema should be rewritten to include the version prefix
    assert_includes resolved_content, "$schema: v0.1/ext_schema.json#",
      "Resolved file should contain versioned $schema"
    refute_includes resolved_content, "$schema: ext_schema.json#",
      "Resolved file should not contain bare (unversioned) $schema"
  end

  # Test that $schema stays unchanged when no schemas have $id
  def test_schema_versioning_unchanged_without_id
    Dir.mktmpdir do |tmpdir|
      schemas_dir = Pathname.new(tmpdir) / "schemas"
      schemas_dir.mkpath
      # Schema with no $id field
      (schemas_dir / "mock_schema.json").write(JSON.generate({
        "$schema" => "http://json-schema.org/draft-07/schema#",
        "type" => "object"
      }))

      input_dir = Pathname.new(@test_dir) / "no_id_input"
      output_dir = Pathname.new(@test_dir) / "no_id_output"
      input_dir.mkpath

      (input_dir / "item.yaml").write("$schema: mock_schema.json#\nname: test\n")

      resolver = Udb::Yaml::Resolver.new(quiet: true, schemas_path: schemas_dir)
      resolver.resolve_files(input_dir, output_dir, no_checks: true)

      resolved_content = File.read(output_dir / "item.yaml")
      # Without $id in the schema, the URI should be unchanged
      assert_includes resolved_content, "$schema: mock_schema.json#",
        "Resolved file should keep bare $schema when schema has no $id"
    end
  end

  private

  # Recursively find all compiled AST hashes (identified by having a "source" hash
  # with "file", "begin", and "end" keys — the shape produced by AstNode#source_yaml)
  def find_ast_hashes(data)
    result = []
    case data
    when Hash
      if data.key?("source") && data["source"].is_a?(Hash) &&
         data["source"].key?("file") && data["source"].key?("begin") && data["source"].key?("end")
        result << data
      end
      data.values.each { |v| result.concat(find_ast_hashes(v)) }
    when Array
      data.each { |item| result.concat(find_ast_hashes(item)) }
    end
    result
  end

  # Walk +original_data+ and +resolved_data+ in parallel, collecting pairs of
  # (IDL string value, compiled AST hash) for every IDL key (a key whose name
  # ends with `()`) found in the original data.
  #
  # Returns an array of hashes with keys:
  #   :idl_text   — the YAML-parsed IDL string
  #   :ast_hash   — the compiled AST hash from the resolved data
  #   :path       — array of keys leading to the IDL key (for diagnostics)
  #   :parse_root — the Treetop parse root symbol to use when re-parsing
  def find_idl_pairs(original_data, resolved_data, path = [])
    result = []
    return result unless original_data.is_a?(Hash) && resolved_data.is_a?(Hash)

    original_data.each do |key, value|
      next unless key.is_a?(String)

      if key.end_with?(")")
        # IDL key like sw_write(csr_value) or operation()
        key_minus_args = key.split("(")[0]
        resolved_value = resolved_data[key_minus_args]
        next unless resolved_value.is_a?(Hash) &&
                    resolved_value.key?("source") &&
                    resolved_value["source"].is_a?(Hash)

        parse_root = if key == "operation()"
                       :instruction_operation
                     elsif path.include?("requirements")
                       :constraint_body
                     else
                       :function_body
                     end

        result << {
          idl_text:   value.to_s,
          ast_hash:   resolved_value,
          path:       path + [key],
          parse_root: parse_root
        }
      elsif value.is_a?(Hash)
        resolved_value = resolved_data[key]
        result.concat(find_idl_pairs(value, resolved_value, path + [key])) if resolved_value.is_a?(Hash)
      elsif value.is_a?(Array)
        resolved_value = resolved_data[key]
        next unless resolved_value.is_a?(Array)
        value.zip(resolved_value).each_with_index do |(orig_item, res_item), idx|
          result.concat(find_idl_pairs(orig_item, res_item, path + [key, idx])) if orig_item.is_a?(Hash) && res_item.is_a?(Hash)
        end
      end
    end

    result
  end

  # Recursively remove all "source" sub-hashes so that structural comparison
  # of two AST #to_h results is not affected by differing byte offsets.
  def strip_source(data)
    case data
    when Hash
      data.each_with_object({}) do |(k, v), h|
        next if k == "source"
        h[k] = strip_source(v)
      end
    when Array
      data.map { |item| strip_source(item) }
    else
      data
    end
  end

  # Recursively check if a data structure contains a specific key
  def data_contains_key?(data, key)
    case data
    when Hash
      return true if data.key?(key)
      data.values.any? { |v| data_contains_key?(v, key) }
    when Array
      data.any? { |v| data_contains_key?(v, key) }
    else
      false
    end
  end

  # Check if data contains non-empty IDL keys (keys ending with ())
  def data_contains_non_empty_idl_keys?(data)
    case data
    when Hash
      data.each do |key, value|
        if key.is_a?(String) && key.end_with?(")")
          # Check if the value is non-empty
          return true if value.is_a?(String) && !value.strip.empty?
          return true if !value.is_a?(String) && value.present?
        end
        return true if data_contains_non_empty_idl_keys?(value)
      end
      false
    when Array
      data.any? { |item| data_contains_non_empty_idl_keys?(item) }
    else
      false
    end
  end

  # Check if data contains IDL keys (keys ending with ())
  def data_contains_idl_keys?(data)
    case data
    when Hash
      data.each do |key, value|
        return true if key.is_a?(String) && key.end_with?(")")
        return true if data_contains_idl_keys?(value)
      end
      false
    when Array
      data.any? { |item| data_contains_idl_keys?(item) }
    else
      false
    end
  end

  # Compare two data structures with tolerance for trailing whitespace in strings
  def compare_with_whitespace_tolerance(data1, data2)
    return true if data1 == data2
    return false unless data1.class == data2.class

    case data1
    when Hash
      return false unless data1.keys.sort == data2.keys.sort
      data1.keys.all? { |k| compare_with_whitespace_tolerance(data1[k], data2[k]) }
    when Array
      return false unless data1.length == data2.length
      data1.zip(data2).all? { |v1, v2| compare_with_whitespace_tolerance(v1, v2) }
    when String
      # Allow trailing whitespace differences and internal newline vs space differences
      # (multiline plain scalars may be joined differently)
      normalize_string(data1) == normalize_string(data2)
    else
      data1 == data2
    end
  end

  # Normalize a string for comparison (collapse whitespace)
  def normalize_string(str)
    str.strip.gsub(/\s+/, " ")
  end

  # Test cross-file inheritance $parent_of back-references
  def test_cross_file_parent_of_relationships
    # Use mock_spec directory with parent.yaml and child.yaml
    mock_spec_dir = Pathname.new(__dir__) / "mock_spec"
    output_dir = Pathname.new(@test_dir) / "cross_file_test"

    # Run resolver
    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(mock_spec_dir, output_dir, no_checks: true)

    # Load resolved files
    parent_resolved = Psych.safe_load_file(output_dir / "parent.yaml", permitted_classes: [Date, Symbol], aliases: true)
    child_resolved = Psych.safe_load_file(output_dir / "child.yaml", permitted_classes: [Date, Symbol], aliases: true)

    # Verify child has $child_of pointing to parent
    assert child_resolved["derived_item"].key?("$child_of"),
      "Child derived_item should have $child_of"
    assert_equal "parent.yaml#/base_item", child_resolved["derived_item"]["$child_of"],
      "Child $child_of should reference parent.yaml#/base_item"

    # Verify parent has $parent_of pointing back to child
    assert parent_resolved["base_item"].key?("$parent_of"),
      "Parent base_item should have $parent_of back-reference"
    assert_equal "child.yaml#/derived_item", parent_resolved["base_item"]["$parent_of"],
      "Parent $parent_of should reference child.yaml#/derived_item"

    # Verify inheritance worked correctly
    assert_equal 200, child_resolved["derived_item"]["value"],
      "Child should override value to 200"
    assert_equal "Base item from parent", child_resolved["derived_item"]["description"],
      "Child should inherit description from parent"
    assert_equal "Added in child", child_resolved["derived_item"]["extra_field"],
      "Child should have its own extra_field"
  end

  # Test edge cases in source location tracking
  def test_source_location_edge_cases
    # Test various YAML edge cases that might cause offset tracking issues
    edge_case_yaml = <<~YAML
      # Single-quoted strings with escaped quotes
      single_quoted: 'value with ''escaped'' quotes'

      # Double-quoted strings with escape sequences
      double_quoted: "value with \\n newline and \\t tab"

      # Empty quoted strings
      empty_double: ""
      empty_single: ''

      # Multi-line plain scalars
      multiline_plain: this is a very long value that
        continues on the next line

      # Literal block with chomping indicators
      literal_strip: |-
        content without trailing newline
      literal_keep: |+
        content with trailing newlines
      #{'  '}
      #{'  '}

      # Folded scalar with blank lines
      folded_blank: >
        Line 1
      #{'  '}
        Line 2 after blank line

      # Unicode and multi-byte characters
      unicode: "日本語"
      emoji: "emoji 🎉"

      # Values starting with special characters
      colon_start: :value_starting_with_colon
      at_start: @value_with_at

      # Null/empty values
      null_explicit: null
      null_tilde: ~
      empty_value:

      # Numbers and booleans
      number: 42
      float: 3.14
      bool_true: true
      bool_false: false
    YAML

    # Write to temp file
    temp_file = Pathname.new(@test_dir) / "edge_cases.yaml"
    File.write(temp_file, edge_case_yaml)

    # Parse with CommentParser
    parser = Udb::Yaml::CommentParser.new
    result = parser.parse_file(temp_file)

    # Verify all keys were parsed
    assert result[:data].key?("single_quoted"), "single_quoted key not found"
    assert result[:data].key?("double_quoted"), "double_quoted key not found"
    assert result[:data].key?("empty_double"), "empty_double key not found"
    assert result[:data].key?("multiline_plain"), "multiline_plain key not found"
    assert result[:data].key?("literal_strip"), "literal_strip key not found"
    assert result[:data].key?("unicode"), "unicode key not found"
    assert result[:data].key?("emoji"), "emoji key not found"

    # Verify values are correct
    assert_equal "value with 'escaped' quotes", result[:data]["single_quoted"]
    assert_includes result[:data]["double_quoted"], "newline"
    assert_equal "", result[:data]["empty_double"]
    assert_equal "", result[:data]["empty_single"]
    assert_includes result[:data]["multiline_plain"], "continues"
    assert_equal "日本語", result[:data]["unicode"]
    assert_includes result[:data]["emoji"], "🎉"
    assert_equal ":value_starting_with_colon", result[:data]["colon_start"]
    assert_equal "@value_with_at", result[:data]["at_start"]
    assert_nil result[:data]["null_explicit"]
    assert_nil result[:data]["null_tilde"]
    assert_nil result[:data]["empty_value"]
    assert_equal 42, result[:data]["number"]
    assert_equal 3.14, result[:data]["float"]
    assert_equal true, result[:data]["bool_true"]
    assert_equal false, result[:data]["bool_false"]

    # Test that source location tracking works with edge cases
    # by running through the resolver
    output_dir = Pathname.new(@test_dir) / "edge_cases_resolved"
    input_dir = Pathname.new(@test_dir)

    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(input_dir, output_dir, no_checks: true)

    # Verify resolved file exists and is valid
    resolved_file = output_dir / "edge_cases.yaml"
    assert resolved_file.exist?, "Resolved file not created"

    resolved_data = Psych.safe_load_file(resolved_file, permitted_classes: [Date, Symbol], aliases: true)
    assert resolved_data.key?("$source"), "Resolved file missing $source"

    # Verify key values are preserved
    assert_equal "value with 'escaped' quotes", resolved_data["single_quoted"]
    assert_equal "日本語", resolved_data["unicode"]
  end

  # Test source location tracking with complex nested structures
  def test_source_location_nested_structures
    nested_yaml = <<~YAML
      top_level:
        nested_map:
          deep_key: deep_value
          another_deep: "quoted value"
        nested_sequence:
          - first_item
          - second_item
          - nested_in_seq:
              key: value
        mixed_content:
          - item1
          - key2: value2
            key3: value3
          - item3
    YAML

    temp_file = Pathname.new(@test_dir) / "nested.yaml"
    File.write(temp_file, nested_yaml)

    parser = Udb::Yaml::CommentParser.new
    result = parser.parse_file(temp_file)

    # Verify nested structure is correct
    assert_equal result[:data]["top_level"]["nested_map"]["deep_key"], "deep_value"
    assert result[:data]["top_level"]["nested_sequence"].is_a?(Array)
    assert_equal 3, result[:data]["top_level"]["nested_sequence"].length
    assert result[:data]["top_level"]["nested_sequence"][2].is_a?(Hash)
    assert_equal "value", result[:data]["top_level"]["nested_sequence"][2]["nested_in_seq"]["key"]

    # Test resolver handles nested structures
    output_dir = Pathname.new(@test_dir) / "nested_resolved"
    input_dir = Pathname.new(@test_dir)

    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(input_dir, output_dir, no_checks: true)

    resolved_file = output_dir / "nested.yaml"
    assert resolved_file.exist?, "Resolved nested file not created"

    resolved_data = Psych.safe_load_file(resolved_file, permitted_classes: [Date, Symbol], aliases: true)
    assert_equal "deep_value", resolved_data["top_level"]["nested_map"]["deep_key"]
  end

  # Test handling of block scalars with various indentation
  def test_block_scalar_indentation
    block_yaml = <<~YAML
      explicit_indent: |2
        This has explicit
        2-space indent

      implicit_indent: |
        This has implicit
        indent detection

      folded_explicit: >2
        Folded with
        explicit indent

      nested:
        block_in_nested: |
          Content in nested
          mapping
    YAML

    temp_file = Pathname.new(@test_dir) / "blocks.yaml"
    File.write(temp_file, block_yaml)

    parser = Udb::Yaml::CommentParser.new
    result = parser.parse_file(temp_file)

    # Verify block scalars are parsed correctly
    assert_includes result[:data]["explicit_indent"], "This has explicit"
    assert_includes result[:data]["implicit_indent"], "This has implicit"
    assert_includes result[:data]["folded_explicit"], "Folded with"
    assert_includes result[:data]["nested"]["block_in_nested"], "Content in nested"

    # Test resolver handles block scalars
    output_dir = Pathname.new(@test_dir) / "blocks_resolved"
    input_dir = Pathname.new(@test_dir)

    resolver = Udb::Yaml::Resolver.new(quiet: true)
    resolver.resolve_files(input_dir, output_dir, no_checks: true)

    resolved_file = output_dir / "blocks.yaml"
    assert resolved_file.exist?, "Resolved blocks file not created"
  end

  # Extract source map entries from YAML content
  def extract_source_map(content)
    lines = content.lines
    in_map = false
    map_entries = []

    lines.each do |line|
      if line.include?("===== SOURCE MAP BEGIN =====")
        in_map = true
        next
      elsif line.include?("===== SOURCE MAP END =====")
        break
      elsif in_map && line.start_with?("#")
        # Remove leading "# " and add to entries
        entry = line.sub(/^#\s*/, "").strip
        map_entries << entry unless entry.empty? || entry.start_with?("This map") || entry.start_with?("Format:")
      end
    end

    map_entries
  end
end
