// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

template <template <unsigned, bool> class Family, unsigned Capacity>
void runtime_widths() {
  using Bits = Family<Capacity, false>;
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ Capacity ^ 0x52554e54494d45ULL);
  CAPTURE(replay_seed, Capacity, Bits::PossiblyUnknown);
  for (unsigned lw : {1u, 7u, 8u, 9u, 16u, 17u, 31u, 32u, 33u, 63u, 64u, 65u, 127u, 128u}) {
    if (lw > Capacity) continue;
    for (unsigned rw : {1u, lw, Capacity}) {
      CAPTURE(lw, rw);
      for (unsigned sample = 0; sample < 16; ++sample) {
        CAPTURE(sample);
        const auto lhs_raw = bits_test::random_raw(rng, lw);
        const auto rhs_raw = bits_test::random_raw(rng, rw);
        bits_test::arithmetic(bits_test::make<Bits>(lhs_raw, lw),
                              bits_test::make<Bits>(rhs_raw, rw), lhs_raw, rhs_raw);
      }
    }
    for (const auto& raw : bits_test::edges(lw)) {
      for (unsigned count : {0u, 1u, lw - 1, lw, lw + 1, 2 * lw}) {
        bits_test::shifts(bits_test::make<Bits>(raw, lw), udb::_Bits<32, false>{count}, raw, count);
      }
    }
  }
}

TEST_CASE("Native Bits runtime widths below 64-bit capacity", "[bits][native][runtime]") {
  runtime_widths<udb::_RuntimeBits, 64>();
  runtime_widths<udb::_PossiblyUnknownRuntimeBits, 64>();
}
TEST_CASE("Native Bits runtime widths below 128-bit capacity", "[bits][native][runtime]") {
  runtime_widths<udb::_RuntimeBits, 128>();
  runtime_widths<udb::_PossiblyUnknownRuntimeBits, 128>();
}

TEST_CASE("Native Bits known fixed/runtime operands", "[bits][native][types]") {
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ 0x5459504553ULL);
  CAPTURE(replay_seed);
  for (unsigned sample = 0; sample < 64; ++sample) {
    CAPTURE(sample);
    const auto lhs_raw = bits_test::random_raw(rng, 16);
    const auto rhs_raw = bits_test::random_raw(rng, 8);
    const udb::_Bits<16, false> lhs{lhs_raw};
    const auto rhs = bits_test::make<udb::_RuntimeBits<16, false>>(rhs_raw, 8);
    bits_test::arithmetic(lhs, rhs, lhs_raw, rhs_raw);
    bits_test::arithmetic(rhs, lhs, rhs_raw, lhs_raw);
  }
}

TEST_CASE("Native Bits runtime construction truncates at active width",
          "[bits][native][boundary]") {
  using namespace bits_test;
  for (unsigned width : {1u, 7u, 17u, 33u, 63u}) {
    CAPTURE(width);
    for (const auto& raw :
         std::vector<mpz_class>{-1, power(width), power(width) + 1, power(64) - 1}) {
      INFO("raw=" << raw.get_str(16));
      value<false>(make<udb::_RuntimeBits<64, false>>(raw, width), raw, width);
      value<true>(make<udb::_RuntimeBits<64, true>>(raw, width), raw, width);
      value<false>(make<udb::_PossiblyUnknownRuntimeBits<64, false>>(raw, width), raw, width);
    }
  }
}
