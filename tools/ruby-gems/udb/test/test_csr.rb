# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require_relative "test_helper"

require "concurrent"
require "sorbet-runtime"
require "udb/obj/csr"
require "udb/cfg_arch"

# Tests for Csr's XLEN reasoning: Csr#dynamic_length?, Csr#length_cond32,
# Csr#length_cond64 and Csr#length_pretty in the "XLEN" case.
#
# An XLEN-length CSR is dynamic when the effective XLEN can vary in ANY privilege
# mode that can reach it.
class TestCsr < Minitest::Test
  include Udb

  # Build a genuine ConfiguredArchitecture (so Sorbet sig checks pass) with just
  # enough state injected to exercise the XLEN paths. Mirrors the approach in
  # test_register_file_obj.rb (allocate + define_singleton_method).
  #
  # @param dynamic_modes [Array<String>] modes whose effective XLEN can vary
  def make_cfg_arch(dynamic_modes:)
    arch = Udb::ConfiguredArchitecture.allocate
    arch.instance_variable_set(:@objects, Concurrent::Hash.new)
    arch.instance_variable_set(:@object_hashes, Concurrent::Hash.new)
    arch.define_singleton_method(:multi_xlen_in_mode?) { |mode| dynamic_modes.include?(mode) }
    arch
  end

  # Build a real Csr with the given length. base is seeded to nil (CSR defined in
  # all bases) so dynamic_length? reaches the length-based branches without invoking
  # the SAT/logic-tree machinery, which would require the full architecture database.
  def make_csr(arch, length:, priv_mode: "M")
    data = {
      "$schema" => "csr_schema.json#",
      "kind" => "csr",
      "name" => "xtest",
      "long_name" => "Test CSR",
      "length" => length,
      "priv_mode" => priv_mode,
      "description" => "A test CSR."
    }
    csr = Csr.new(data, Pathname.new("/mock/csr/xtest.yaml"), arch)
    csr.instance_variable_set(:@base, nil)
    csr
  end

  # S-mode alone makes the effective XLEN variable, so the CSR IS dynamic.
  # (Regression pin: the buggy `A || B && C` precedence returns false here.)
  def test_xlen_dynamic_when_only_sxlen_mutable
    arch = make_cfg_arch(dynamic_modes: %w[S])
    csr = make_csr(arch, length: "XLEN", priv_mode: "S")
    assert csr.dynamic_length?,
      "XLEN CSR must be dynamic when S-mode is possible and SXLEN is mutable, even without H"
  end

  # VS-mode alone makes the effective XLEN variable, so the CSR IS dynamic.
  def test_xlen_dynamic_when_only_vsxlen_mutable
    arch = make_cfg_arch(dynamic_modes: %w[VS])
    csr = make_csr(arch, length: "XLEN", priv_mode: "S")
    assert csr.dynamic_length?,
      "XLEN CSR must be dynamic when H-mode is possible and VSXLEN is mutable, even without S"
  end

  # Both S and VS vary -> still dynamic.
  def test_xlen_dynamic_when_both_conditions_hold
    arch = make_cfg_arch(dynamic_modes: %w[S VS])
    csr = make_csr(arch, length: "XLEN", priv_mode: "S")
    assert csr.dynamic_length?,
      "XLEN CSR must be dynamic when both SXLEN and VSXLEN are mutable"
  end

  # MXLEN unknown -> M-mode varies -> dynamic regardless of S/H.
  def test_xlen_dynamic_when_mxlen_unknown
    arch = make_cfg_arch(dynamic_modes: %w[M])
    csr = make_csr(arch, length: "XLEN", priv_mode: "M")
    assert csr.dynamic_length?,
      "XLEN CSR must be dynamic when MXLEN is unknown"
  end

  # No mode with access varies -> NOT dynamic.
  # Guards against an over-broad fix that makes everything dynamic.
  def test_xlen_not_dynamic_when_fully_pinned
    arch = make_cfg_arch(dynamic_modes: [])
    csr = make_csr(arch, length: "XLEN", priv_mode: "S")
    refute csr.dynamic_length?,
      "XLEN CSR must not be dynamic when no mode with access can change XLEN"
  end

  # U-mode is reachable for a priv_mode: U CSR, so UXLEN alone makes it dynamic.
  def test_xlen_dynamic_when_only_umode_varies
    arch = make_cfg_arch(dynamic_modes: %w[U])
    csr = make_csr(arch, length: "XLEN", priv_mode: "U")
    assert csr.dynamic_length?,
      "XLEN CSR readable in U-mode must be dynamic when UXLEN is mutable"
  end

  # VU-mode likewise.
  def test_xlen_dynamic_when_only_vumode_varies
    arch = make_cfg_arch(dynamic_modes: %w[VU])
    csr = make_csr(arch, length: "XLEN", priv_mode: "U")
    assert csr.dynamic_length?,
      "XLEN CSR readable in VU-mode must be dynamic when VUXLEN is mutable"
  end

  # A varying mode that cannot reach the CSR must not make it dynamic.
  def test_xlen_not_dynamic_when_varying_mode_has_no_access
    arch = make_cfg_arch(dynamic_modes: %w[U VU])
    csr = make_csr(arch, length: "XLEN", priv_mode: "M")
    refute csr.dynamic_length?,
      "M-mode-only CSR must not be dynamic because U-mode XLEN varies"
  end

  # The emitted condition must name every reachable mode that can vary, U and VU included.
  def test_length_cond_covers_u_and_vu
    arch = make_cfg_arch(dynamic_modes: %w[M S U VS VU])
    csr = make_csr(arch, length: "XLEN", priv_mode: "U")

    assert_equal(
      "(priv_mode() == PrivilegeMode::M && CSR[misa].MXL == 0) || " \
      "(priv_mode() == PrivilegeMode::S && CSR[mstatus].SXL == 0) || " \
      "(priv_mode() == PrivilegeMode::U && CSR[mstatus].UXL == 0) || " \
      "(priv_mode() == PrivilegeMode::VS && CSR[hstatus].VSXL == 0) || " \
      "(priv_mode() == PrivilegeMode::VU && CSR[vsstatus].UXL == 0)",
      csr.length_cond32
    )
    assert_includes csr.length_cond64, "CSR[mstatus].UXL == 1"
    assert_includes csr.length_cond64, "CSR[vsstatus].UXL == 1"
  end

  # ...and must name only those modes. An M-mode CSR gets the M disjunct alone.
  def test_length_cond_is_limited_to_modes_with_access
    arch = make_cfg_arch(dynamic_modes: %w[M S U VS VU])
    csr = make_csr(arch, length: "XLEN", priv_mode: "M")

    assert_equal "(priv_mode() == PrivilegeMode::M && CSR[misa].MXL == 0)", csr.length_cond32
    refute_includes csr.length_cond32, "SXL"
    refute_includes csr.length_cond32, "VSXL"
  end

  # Every disjunct must carry the xlen encoding. The previous String#sub filled in
  # only the first, leaving a literal "%%" in the rendered docs.
  def test_length_pretty_fills_every_disjunct
    arch = make_cfg_arch(dynamic_modes: %w[M S VS])
    csr = make_csr(arch, length: "XLEN", priv_mode: "S")

    pretty = csr.length_pretty
    refute_includes pretty, "%%", "length_pretty must not leak the substitution placeholder"
    assert_equal 3, pretty.scan("== 0").size
    assert_equal 3, pretty.scan("== 1").size
  end

  # The fixed-width lengths name one field and do not consult the mode list.
  def test_length_cond_for_fixed_width_lengths
    arch = make_cfg_arch(dynamic_modes: %w[M S U VS VU])

    mxlen = make_csr(arch, length: "MXLEN", priv_mode: "M")
    assert_equal "CSR[misa].MXL == 0", mxlen.length_cond32
    assert_equal "CSR[misa].MXL == 1", mxlen.length_cond64

    sxlen = make_csr(arch, length: "SXLEN", priv_mode: "S")
    assert_equal "CSR[mstatus].SXL == 0", sxlen.length_cond32
    assert_equal "CSR[mstatus].SXL == 1", sxlen.length_cond64

    vsxlen = make_csr(arch, length: "VSXLEN", priv_mode: "VS")
    assert_equal "CSR[hstatus].VSXL == 0", vsxlen.length_cond32
    assert_equal "CSR[hstatus].VSXL == 1", vsxlen.length_cond64
  end

  # A CSR of fixed integer width has no xlen condition to report.
  def test_length_cond_raises_for_integer_length
    arch = make_cfg_arch(dynamic_modes: %w[M])
    csr = make_csr(arch, length: 32, priv_mode: "M")

    err = assert_raises(RuntimeError) { csr.length_cond32 }
    assert_match(/Unexpected length/, err.message)
  end

  # Asking for the condition when nothing can vary is a caller error, not an
  # empty string. The templates only reach it when some mode does vary.
  def test_length_cond_raises_when_no_mode_varies
    arch = make_cfg_arch(dynamic_modes: [])
    csr = make_csr(arch, length: "XLEN", priv_mode: "U")

    err = assert_raises(RuntimeError) { csr.length_cond32 }
    assert_match(/has a dynamic XLEN/, err.message)
  end
end
