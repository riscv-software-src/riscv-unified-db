// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

TEST_CASE("Native Bits storage transition widths", "[bits][native][boundary]") {
  SECTION("7") { bits_test::same_width<udb::_Bits, 7>(); }
  SECTION("9") { bits_test::same_width<udb::_Bits, 9>(); }
  SECTION("15") { bits_test::same_width<udb::_Bits, 15>(); }
  SECTION("17") { bits_test::same_width<udb::_Bits, 17>(); }
  SECTION("31") { bits_test::same_width<udb::_Bits, 31>(); }
  SECTION("33") { bits_test::same_width<udb::_Bits, 33>(); }
  SECTION("63") { bits_test::same_width<udb::_Bits, 63>(); }
  SECTION("65") { bits_test::same_width<udb::_Bits, 65>(); }
  SECTION("127") { bits_test::same_width<udb::_Bits, 127>(); }
  SECTION("129 arithmetic") {
    // GMP shifts have dedicated defect regressions.
    const auto boundaries = bits_test::edges(129);
    for (const auto& lhs : boundaries) {
      for (const auto& rhs : boundaries) {
        bits_test::arithmetic(udb::_Bits<129, false>{lhs}, udb::_Bits<129, false>{rhs}, lhs, rhs);
      }
    }
  }
}

TEST_CASE("Native Bits one-bit shifts with a wider count", "[bits][native][boundary]") {
  for (unsigned raw : {0u, 1u}) {
    for (unsigned count : {0u, 1u, 2u, 3u, 32u, 128u}) {
      bits_test::shifts(udb::_Bits<1, false>{raw}, udb::_Bits<32, false>{count}, mpz_class(raw),
                        count);
    }
  }
}

template <unsigned L, unsigned R, bool LS, bool RS>
void different_widths() {
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ (uint64_t{L} << 32) ^ R);
  CAPTURE(replay_seed, L, R, LS, RS);
  for (unsigned sample = 0; sample < 64; ++sample) {
    CAPTURE(sample);
    const auto lhs_raw = bits_test::random_raw(rng, L);
    const auto rhs_raw = bits_test::random_raw(rng, R);
    bits_test::arithmetic(udb::_Bits<L, LS>{lhs_raw}, udb::_Bits<R, RS>{rhs_raw}, lhs_raw, rhs_raw);
  }
}

TEST_CASE("Native Bits unequal-width extension and result widths", "[bits][native][types]") {
  SECTION("unsigned 7/17") { different_widths<7, 17, false, false>(); }
  SECTION("unsigned 17/7") { different_widths<17, 7, false, false>(); }
  SECTION("unsigned 64/128") { different_widths<64, 128, false, false>(); }
  SECTION("unsigned 128/64") { different_widths<128, 64, false, false>(); }
  SECTION("signed 7/17") { different_widths<7, 17, true, true>(); }
  SECTION("signed 17/7") { different_widths<17, 7, true, true>(); }
}

TEST_CASE("Native Bits mixed signedness return types", "[bits][native][types]") {
  // Positive operands isolate the result signedness rule from C++ mixed-sign division.
  for (unsigned lhs = 0; lhs < 16; ++lhs) {
    for (unsigned rhs = 0; rhs < 16; ++rhs) {
      bits_test::arithmetic(udb::_Bits<7, true>{lhs}, udb::_Bits<17, false>{rhs}, mpz_class(lhs),
                            mpz_class(rhs));
      bits_test::arithmetic(udb::_Bits<17, false>{rhs}, udb::_Bits<7, true>{lhs}, mpz_class(rhs),
                            mpz_class(lhs));
    }
  }
}
