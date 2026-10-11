# Copyright (c) AINEKKO.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "fileutils"
require "tmpdir"
require "yaml"

require "udb/logic"
require "udb/cfg_arch"
require "udb/resolver"

# this is needed for tty-progressbar to work with minitest
unless StringIO.method_defined? :ioctl
  class StringIO
    def ioctl(*)
      # :nocov:
      80
      # :nocov:
    end
  end
end

class TestMmr < Minitest::Test
  include Udb

  def cfg_arch
    return @cfg_arch unless @cfg_arch.nil?

    udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @gen_path = Pathname.new(Dir.mktmpdir)
    $resolver ||= Udb::Resolver.new(
      schemas_path_override: udb_gem_root / "schemas",
      cfgs_path_override: udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @gen_path,
      std_path_override: udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: false
    )
    @cfg_arch = T.let(nil, T.nilable(ConfiguredArchitecture))
    capture_io do
      @cfg_arch = $resolver.cfg_arch_for("_")
    end
    T.must(@cfg_arch)
  end

  def partial_cfg_arch
    return @partial_cfg_arch unless @partial_cfg_arch.nil?

    udb_gem_root = (Pathname.new(__dir__) / "..").realpath
    @partial_gen_path = Pathname.new(Dir.mktmpdir)
    $partial_resolver ||= Udb::Resolver.new(
      schemas_path_override: udb_gem_root / "schemas",
      cfgs_path_override: udb_gem_root / "test" / "mock_cfgs",
      gen_path_override: @partial_gen_path,
      std_path_override: udb_gem_root / "test" / "mock_spec" / "isa",
      quiet: false
    )
    @partial_cfg_arch = T.let(nil, T.nilable(ConfiguredArchitecture))
    capture_io do
      @partial_cfg_arch = $partial_resolver.cfg_arch_for("little_is_better")
    end
    T.must(@partial_cfg_arch)
  end

  def make_mmr(overrides = {})
    data = {
      "$schema" => "mmr_schema.json#",
      "kind" => "mmr",
      "name" => "test_reg0",
      "long_name" => "Test Register 0",
      "length" => 32,
      "description" => "A test memory-mapped register.",
      "writable" => true,
      "physical_address" => 0x1000,
      "definedBy" => { "extension" => { "name" => "A" } }
    }.merge(overrides)
    arch = overrides.delete(:arch) || cfg_arch
    Mmr.new(data, Pathname.new("/mock/test_reg.yaml"), arch)
  end

  # ── Mmr-specific methods ──

  def test_name
    mmr = make_mmr
    assert_equal "test_reg0", mmr.name
  end

  def test_long_name
    mmr = make_mmr
    assert_equal "Test Register 0", mmr.long_name
  end

  def test_physical_address
    mmr = make_mmr
    assert_equal 0x1000, mmr.physical_address
  end

  def test_physical_address_zero
    mmr = make_mmr("physical_address" => 0)
    assert_equal 0, mmr.physical_address
  end

  def test_length_32
    mmr = make_mmr("length" => 32)
    assert_equal 32, mmr.length
    assert_equal 32, mmr.length(32)
    assert_equal 32, mmr.length(64)
  end

  def test_length_64
    mmr = make_mmr("length" => 64)
    assert_equal 64, mmr.length
    assert_equal 64, mmr.max_length
    assert_equal 64, mmr.min_length
  end

  def test_length_pretty
    mmr = make_mmr("length" => 32)
    assert_equal "32-bit", mmr.length_pretty
  end

  def test_dynamic_length_always_false
    mmr = make_mmr
    refute mmr.dynamic_length?
  end

  def test_defined_in_all_bases
    mmr = make_mmr
    assert mmr.defined_in_base32?
    assert mmr.defined_in_base64?
    assert mmr.defined_in_all_bases?
    assert mmr.defined_in_base?(32)
    assert mmr.defined_in_base?(64)
  end

  def test_base_always_nil
    mmr = make_mmr
    assert_nil mmr.base
  end

  def test_format_changes_with_xlen_always_false
    mmr = make_mmr
    refute mmr.format_changes_with_xlen?
  end

  def test_writable_true
    mmr = make_mmr("writable" => true)
    assert mmr.writable
  end

  def test_writable_false
    mmr = make_mmr("writable" => false)
    refute mmr.writable
  end

  def test_kind
    mmr = make_mmr
    assert_equal "mmr", mmr.kind
  end

  def test_exists_in_cfg
    mmr = make_mmr("definedBy" => { "extension" => { "name" => "A" } })
    assert mmr.exists_in_cfg?(cfg_arch)
  end

  def test_equality
    mmr1 = make_mmr("name" => "reg_a")
    mmr2 = make_mmr("name" => "reg_a")
    mmr3 = make_mmr("name" => "reg_b")
    assert_equal mmr1, mmr2
    refute_equal mmr1, mmr3
  end

  def test_priv_mode_raises
    mmr = make_mmr
    assert_raises(NotImplementedError) { mmr.priv_mode }
  end

  def test_bitfield_type_raises
    mmr = make_mmr
    assert_raises(NotImplementedError) { mmr.bitfield_type(cfg_arch) }
  end

  # ── HasFields methods ──

  def test_fields_empty_when_no_fields
    mmr = make_mmr  # no "fields" key
    assert_empty mmr.fields
  end

  def test_fields_with_single_field
    mmr = make_mmr(
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable bit",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert_equal 1, mmr.fields.size
    assert_equal "EN", mmr.fields[0].name
  end

  def test_fields_with_multiple_fields
    mmr = make_mmr(
      "length" => 32,
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable bit",
          "type" => "RW",
          "reset_value" => 0
        },
        "STATUS" => {
          "location" => "7-1",
          "description" => "Status field",
          "type" => "RO",
          "reset_value" => 0
        }
      }
    )
    assert_equal 2, mmr.fields.size
    names = mmr.fields.map(&:name).sort
    assert_equal %w[EN STATUS], names
  end

  def test_field_hash
    mmr = make_mmr(
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert_instance_of Hash, mmr.field_hash
    assert_same mmr.field_hash, mmr.field_hash
    assert mmr.field_hash.key?("EN")
    assert_equal "EN", mmr.field_hash["EN"].name
  end

  def test_field_lookup
    mmr = make_mmr(
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert mmr.field?("EN")
    refute mmr.field?("NONEXISTENT")
    assert_equal "EN", mmr.field("EN").name
    assert_nil mmr.field("NONEXISTENT")
  end

  def test_fields_for_xlen
    mmr = make_mmr(
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    # MMR fields have no base restriction, so they appear for any XLEN
    assert_equal 1, mmr.fields_for(32).size
    assert_equal 1, mmr.fields_for(64).size
    assert_equal 1, mmr.fields_for(nil).size
  end

  def test_possible_fields
    mmr = make_mmr(
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert_equal 1, mmr.possible_fields.size
  end

  def test_possible_fields_for_xlen
    mmr = make_mmr(
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert_equal 1, mmr.possible_fields_for(32).size
    assert_equal 1, mmr.possible_fields_for(64).size
  end

  def test_wavedrom_desc
    mmr = make_mmr(
      "length" => 32,
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        },
        "DATA" => {
          "location" => "15-8",
          "description" => "Data field",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    desc = mmr.wavedrom_desc(cfg_arch, 32)
    assert_instance_of Hash, desc
    assert desc.key?("reg")
    assert desc.key?("config")
    assert_equal 32, desc["config"]["bits"]
    # Should contain field entries and reserved-space entries
    assert desc["reg"].size >= 2
  end

  def test_wavedrom_desc_exclude_unimplemented
    mmr = make_mmr(
      "length" => 32,
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    desc = mmr.wavedrom_desc(cfg_arch, 32, exclude_unimplemented: true)
    assert_instance_of Hash, desc
    assert desc.key?("reg")
    assert_equal 32, desc["config"]["bits"]
  end

  def test_wavedrom_desc_with_partial_cfg
    mmr = make_mmr(
      "length" => 32,
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      },
      :arch => partial_cfg_arch
    )
    desc = mmr.wavedrom_desc(partial_cfg_arch, 32)
    assert_instance_of Hash, desc
    assert desc.key?("reg")
  end

  def test_equality_raises_for_non_mmr
    mmr = make_mmr
    assert_raises(ArgumentError) { mmr == "not_an_mmr" }
  end

  def test_optional_in_cfg_with_partial_arch
    mmr = make_mmr(
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      },
      :arch => partial_cfg_arch
    )
    # Should not raise — returns a boolean
    result = mmr.optional_in_cfg?(partial_cfg_arch)
    assert_includes [true, false], result
  end

  def test_affected_by
    mmr = make_mmr(
      "definedBy" => { "extension" => { "name" => "A" } },
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    # Get an extension version from the arch to test with
    a_ext = cfg_arch.extension("A")
    refute_nil a_ext
    a_ver = a_ext.versions.first
    refute_nil a_ver
    result = mmr.affected_by?(a_ver)
    assert_includes [true, false], result
  end

  # ── Extension#mmrs integration ──

  def test_extension_mmrs_returns_array
    a_ext = cfg_arch.extension("A")
    refute_nil a_ext
    result = a_ext.mmrs
    assert_instance_of Array, result
  end

  # ── HasFields argument validation ──

  def test_wavedrom_desc_raises_for_bad_cfg_arch
    mmr = make_mmr(
      "length" => 32,
      "fields" => {
        "EN" => {
          "location" => 0,
          "description" => "Enable",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    assert_raises(ArgumentError) { mmr.wavedrom_desc("not_an_arch", 32) }
  end

  # ── CsrField integration (coverage for csr_field.rb dynamic_location? fix) ──

  def test_mmr_field_dynamic_location_always_false
    # An MMR field without an explicit location triggers the dynamic_location?
    # code path (line 353 passes through), then hits our MMR guard (lines 356-357)
    mmr = make_mmr(
      "fields" => {
        "DYN" => {
          "location_rv32" => 0,
          "location_rv64" => 0,
          "description" => "Field with no fixed location",
          "type" => "RW",
          "reset_value" => 0
        }
      }
    )
    field = mmr.field("DYN")
    refute_nil field
    # MMR fields should never be dynamic (no privilege modes)
    refute field.dynamic_location?
  end
end
