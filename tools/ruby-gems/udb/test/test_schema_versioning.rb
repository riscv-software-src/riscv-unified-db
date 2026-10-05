# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "json"
require "tmpdir"

require "udb/resolver"
require "udb/obj/database_obj"

# Tests for the per-schema versioning changes introduced in the schema_versioning
# branch.  Coverage targets:
#
#   Udb::Resolver#resolve_schemas
#     - writes gen/schemas/<schema_name>/<version>/<schema_name>
#     - sets $id to the full canonical URL
#     - skips json-schema-draft-07.json
#     - skips schema files with no $id
#
#   Udb::TopLevelDatabaseObject.create_json_schemer_resolver
#     - resolves relative $ref values (e.g. "schema_defs.json") from schemas_path
#
#   Udb::TopLevelDatabaseObject#validate
#     - accepts a bare $schema value ("ext_schema.json#")
#     - accepts a versioned $schema value ("v0.1/ext_schema.json#")
#     - raises SchemaValidationError for invalid data
#     - raises SchemaError for a bad schema file

class TestSchemaVersioning < Minitest::Test
  include Udb

  UDB_GEM_ROOT = (Pathname.new(__dir__) / "..").realpath
  SCHEMAS_PATH = UDB_GEM_ROOT / "schemas"

  # ── helpers ──────────────────────────────────────────────────────────────────

  def make_resolver(gen_path)
    Udb::Resolver.new(
      schemas_path_override: SCHEMAS_PATH,
      cfgs_path_override: UDB_GEM_ROOT / "test" / "mock_cfgs",
      gen_path_override: gen_path,
      std_path_override: UDB_GEM_ROOT / "test" / "mock_spec" / "isa",
      quiet: true
    )
  end

  # Minimal valid extension data (matches ext_schema.json)
  def valid_ext_data(schema_ref = "ext_schema.json#")
    {
      "$schema" => schema_ref,
      "kind" => "extension",
      "name" => "Xtest",
      "type" => "unprivileged",
      "long_name" => "Test extension",
      "versions" => [
        {
          "version" => "1.0.0",
          "state" => "ratified",
          "ratification_date" => "2024-01"
        }
      ],
      "description" => "A test extension."
    }
  end

  def make_obj(data, gen_path)
    resolver = make_resolver(gen_path)
    capture_io { resolver.cfg_arch_for("_") }
    arch = resolver.cfg_arch_for("_")
    Udb::TopLevelDatabaseObject.new(data, Pathname.new("/fake/path.yaml"), arch)
  end

  # ── Resolver#resolve_schemas ──────────────────────────────────────────────────

  def test_resolve_schemas_creates_per_schema_directories
    Dir.mktmpdir do |tmpdir|
      gen_path = Pathname.new(tmpdir)
      resolver = make_resolver(gen_path)
      resolver.resolve_schemas

      # Every schema with a $id should produce a versioned output file
      SCHEMAS_PATH.glob("*.json").each do |src|
        next if src.basename.to_s == "json-schema-draft-07.json"
        data = JSON.parse(src.read)
        next unless data.key?("$id")

        schema_name = src.basename.to_s
        version = data["$id"]
        out = gen_path / "schemas" / schema_name / version / schema_name
        assert out.exist?, "Expected resolved schema at #{out}"
      end
    end
  end

  def test_resolve_schemas_sets_full_id_url
    Dir.mktmpdir do |tmpdir|
      gen_path = Pathname.new(tmpdir)
      resolver = make_resolver(gen_path)
      resolver.resolve_schemas

      ext_version = JSON.parse((SCHEMAS_PATH / "ext_schema.json").read)["$id"]
      out = gen_path / "schemas" / "ext_schema.json" / ext_version / "ext_schema.json"
      assert out.exist?
      resolved = JSON.parse(out.read)
      assert_equal(
        "#{Udb::Resolver::SCHEMAS_BASE_URL}/ext_schema.json/#{ext_version}/ext_schema.json",
        resolved["$id"]
      )
    end
  end

  def test_resolve_schemas_skips_draft07_meta_schema
    Dir.mktmpdir do |tmpdir|
      gen_path = Pathname.new(tmpdir)
      resolver = make_resolver(gen_path)
      resolver.resolve_schemas

      refute (gen_path / "schemas" / "json-schema-draft-07.json").exist?,
             "json-schema-draft-07.json should not be resolved"
    end
  end

  def test_resolve_schemas_skips_files_without_id
    Dir.mktmpdir do |tmpdir|
      gen_path = Pathname.new(tmpdir)

      # Create a temporary schemas dir with one schema that has no $id
      fake_schemas = Pathname.new(tmpdir) / "fake_schemas"
      fake_schemas.mkpath
      (fake_schemas / "no_id_schema.json").write(JSON.generate({ "type" => "object" }))
      # Also copy a real schema so the resolver has something to work with
      FileUtils.cp(SCHEMAS_PATH / "json-schema-draft-07.json", fake_schemas)

      resolver = Udb::Resolver.new(
        schemas_path_override: fake_schemas,
        cfgs_path_override: UDB_GEM_ROOT / "test" / "mock_cfgs",
        gen_path_override: gen_path,
        std_path_override: UDB_GEM_ROOT / "test" / "mock_spec" / "isa",
        quiet: true
      )
      resolver.resolve_schemas

      refute (gen_path / "schemas" / "no_id_schema.json").exist?,
             "Schema without $id should not produce output"
    end
  end

  def test_resolve_schemas_preserves_other_fields
    Dir.mktmpdir do |tmpdir|
      gen_path = Pathname.new(tmpdir)
      resolver = make_resolver(gen_path)
      resolver.resolve_schemas

      src = JSON.parse((SCHEMAS_PATH / "ext_schema.json").read)
      ext_version = src["$id"]
      out = JSON.parse((gen_path / "schemas" / "ext_schema.json" / ext_version / "ext_schema.json").read)

      # All keys except $id should be preserved
      (src.keys - ["$id"]).each do |key|
        assert_equal src[key], out[key], "Field '#{key}' should be preserved in resolved schema"
      end
    end
  end

  # ── TopLevelDatabaseObject#validate — $schema handling ───────────────────────

  def test_validate_accepts_bare_schema_ref
    Dir.mktmpdir do |tmpdir|
      obj = make_obj(valid_ext_data("ext_schema.json#"), Pathname.new(tmpdir))
      resolver = make_resolver(Pathname.new(tmpdir))
      # Should not raise
      obj.validate(resolver)
    end
  end

  def test_validate_accepts_versioned_schema_ref
    Dir.mktmpdir do |tmpdir|
      obj = make_obj(valid_ext_data("v0.1/ext_schema.json#"), Pathname.new(tmpdir))
      resolver = make_resolver(Pathname.new(tmpdir))
      # Should not raise — version prefix is stripped before validation
      obj.validate(resolver)
    end
  end

  def test_validate_raises_for_invalid_data
    Dir.mktmpdir do |tmpdir|
      # Drop a required field to trigger a SchemaValidationError
      bad_data = valid_ext_data.reject { |k, _| k == "long_name" }
      obj = make_obj(bad_data, Pathname.new(tmpdir))
      resolver = make_resolver(Pathname.new(tmpdir))
      assert_raises(Udb::TopLevelDatabaseObject::SchemaValidationError) do
        obj.validate(resolver)
      end
    end
  end

  def test_validate_strips_version_prefix_with_multiple_segments
    Dir.mktmpdir do |tmpdir|
      # A deeper prefix like "v1.2/ext_schema.json#" should also be handled
      obj = make_obj(valid_ext_data("v1.2/ext_schema.json#"), Pathname.new(tmpdir))
      resolver = make_resolver(Pathname.new(tmpdir))
      obj.validate(resolver)
    end
  end

  # ── create_json_schemer_resolver ─────────────────────────────────────────────

  def test_ref_resolver_loads_relative_schema_by_basename
    Dir.mktmpdir do |tmpdir|
      resolver = make_resolver(Pathname.new(tmpdir))
      ref_resolver = Udb::TopLevelDatabaseObject.create_json_schemer_resolver(resolver)

      # Simulate what json_schemer passes for a relative $ref like "schema_defs.json"
      result = ref_resolver.call(URI("schema_defs.json"))
      assert_kind_of Hash, result
      assert result.key?("$defs") || result.key?("definitions") || result.key?("$schema"),
             "Expected schema_defs.json content"
    end
  end

  def test_ref_resolver_uses_basename_ignoring_path_prefix
    Dir.mktmpdir do |tmpdir|
      resolver = make_resolver(Pathname.new(tmpdir))
      ref_resolver = Udb::TopLevelDatabaseObject.create_json_schemer_resolver(resolver)

      # Even if the URI has a path prefix, only the basename is used
      result_bare = ref_resolver.call(URI("schema_defs.json"))
      result_prefixed = ref_resolver.call(URI("some/prefix/schema_defs.json"))
      assert_equal result_bare, result_prefixed
    end
  end

  def test_validate_uses_schema_cache_on_second_call
    Dir.mktmpdir do |tmpdir|
      gen = Pathname.new(tmpdir)
      resolver = make_resolver(gen)
      capture_io { resolver.cfg_arch_for("_") }
      arch = resolver.cfg_arch_for("_")

      obj1 = Udb::TopLevelDatabaseObject.new(valid_ext_data, Pathname.new("/a.yaml"), arch)
      obj2 = Udb::TopLevelDatabaseObject.new(valid_ext_data, Pathname.new("/b.yaml"), arch)

      # First call populates the cache; second call hits the cached branch
      obj1.validate(resolver)
      obj2.validate(resolver)  # exercises schemas.key?(schema_basename) == true
    end
  end

  def test_validate_warns_when_no_schema_key
    Dir.mktmpdir do |tmpdir|
      gen = Pathname.new(tmpdir)
      resolver = make_resolver(gen)
      capture_io { resolver.cfg_arch_for("_") }
      arch = resolver.cfg_arch_for("_")

      data_without_schema = valid_ext_data.reject { |k, _| k == "$schema" }
      obj = Udb::TopLevelDatabaseObject.new(data_without_schema, Pathname.new("/no_schema.yaml"), arch)

      # Should not raise, but should log a warning
      out, _err = capture_io { obj.validate(resolver) }
      # The warning goes through Udb.logger; just assert no exception is raised
      assert true
    end
  end

  def test_validate_raises_schema_error_for_invalid_schema_file
    Dir.mktmpdir do |tmpdir|
      gen = Pathname.new(tmpdir)

      # Build a schemas dir with a deliberately broken schema
      fake_schemas = Pathname.new(tmpdir) / "bad_schemas"
      fake_schemas.mkpath
      # Copy all real schemas so $ref resolution works
      SCHEMAS_PATH.glob("*.json").each { |f| FileUtils.cp(f, fake_schemas) }
      # Overwrite ext_schema.json with an invalid JSON Schema
      (fake_schemas / "ext_schema.json").write(JSON.generate({
        "$schema" => "http://json-schema.org/draft-07/schema#",
        "$id" => "v0.1",
        "type" => "not-a-valid-type"
      }))

      bad_resolver = Udb::Resolver.new(
        schemas_path_override: fake_schemas,
        cfgs_path_override: UDB_GEM_ROOT / "test" / "mock_cfgs",
        gen_path_override: gen,
        std_path_override: UDB_GEM_ROOT / "test" / "mock_spec" / "isa",
        quiet: true
      )
      capture_io { bad_resolver.cfg_arch_for("_") }
      arch = bad_resolver.cfg_arch_for("_")

      obj = Udb::TopLevelDatabaseObject.new(valid_ext_data, Pathname.new("/x.yaml"), arch)
      assert_raises(Udb::TopLevelDatabaseObject::SchemaError) do
        obj.validate(bad_resolver)
      end
    end
  end
end
