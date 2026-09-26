// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

// Tests for register file storage and accessor generation (Layer 4a–4c).

#include <catch2/catch_test_macros.hpp>
#include <udb/hart_factory.hxx>
#include <udb/iss_soc_model.hpp>
#include <filesystem>
#include <stdexcept>

// Use the rv64-riscv-tests config (known-working fully-configured rv64 with F extension).
static udb::HartBase<udb::IssSocModel>* create_rv64_hart(udb::IssSocModel& soc) {
  return udb::HartFactory::create("rv64", 0, std::filesystem::path{UDB_RV64_RISCV_TESTS_CFG}, soc);
}

// ---------------------------------------------------------------------------
// X register file tests (Layer 4a–4c)
// ---------------------------------------------------------------------------

TEST_CASE("X register storage has 32 entries", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  // Write a known value to x31, verify it round-trips; index 32 throws.
  REQUIRE_NOTHROW(hart->set_xreg(31, 42));
  REQUIRE(hart->xreg(31) == 42);
  REQUIRE_THROWS_AS(hart->xreg(32), std::out_of_range);
  delete hart;
}

TEST_CASE("x0 is zero after reset", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  REQUIRE(hart->xreg(0) == 0);
  delete hart;
}

TEST_CASE("writing to x0 leaves it zero (arch_write)", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  hart->set_xreg(0, 42);
  REQUIRE(hart->xreg(0) == 0);
  delete hart;
}

TEST_CASE("xreg throws out_of_range for index >= 32", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  REQUIRE_THROWS_AS(hart->set_xreg(32, 0), std::out_of_range);
  delete hart;
}

// ---------------------------------------------------------------------------
// F register file tests (Layer 4d: hart.hpp adds virtual freg() to HartBase)
// ---------------------------------------------------------------------------

TEST_CASE("F register storage has 32 entries", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  REQUIRE_NOTHROW(hart->set_freg(31, 0xdeadbeef));
  REQUIRE(hart->freg(31) == 0xdeadbeef);
  REQUIRE_THROWS_AS(hart->freg(32), std::out_of_range);
  delete hart;
}

TEST_CASE("freg round-trips a written value", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  hart->set_freg(0, 0x3f800000);
  REQUIRE(hart->freg(0) == 0x3f800000);
  delete hart;
}

TEST_CASE("freg throws out_of_range for index >= 32", "[regfile]") {
  udb::IssSocModel soc(1024 * 1024, 0);
  auto* hart = create_rv64_hart(soc);
  REQUIRE_THROWS_AS(hart->set_freg(32, 0), std::out_of_range);
  delete hart;
}
