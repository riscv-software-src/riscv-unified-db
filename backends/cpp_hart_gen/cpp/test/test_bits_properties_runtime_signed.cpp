// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

template <template <unsigned, bool> class Family, unsigned Capacity>
void signed_runtime_arithmetic() {
  using Bits = Family<Capacity, true>;
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ Capacity ^ 0x5349474e52554eULL);
  CAPTURE(replay_seed, Capacity, Bits::PossiblyUnknown);
  for (unsigned width : {1u, 7u, 8u, 9u, 16u, 17u, 31u, 32u, 33u, 63u, 64u, 65u, 127u, 128u}) {
    if (width > Capacity) continue;
    CAPTURE(width);
    const auto boundaries = bits_test::edges(width);
    for (const auto& lhs : boundaries) {
      for (const auto& rhs : boundaries) {
        bits_test::arithmetic(bits_test::make<Bits>(lhs, width),
                              bits_test::make<Bits>(rhs, width), lhs, rhs);
      }
    }
    for (unsigned rhs_width : {1u, width, Capacity}) {
      CAPTURE(rhs_width);
      for (unsigned sample = 0; sample < 64; ++sample) {
        CAPTURE(sample);
        const auto lhs = bits_test::random_raw(rng, width);
        const auto rhs = bits_test::random_raw(rng, rhs_width);
        bits_test::arithmetic(bits_test::make<Bits>(lhs, width),
                              bits_test::make<Bits>(rhs, rhs_width), lhs, rhs);
      }
    }
  }
}

template <template <unsigned, bool> class Family, unsigned Capacity>
void signed_runtime_shifts() {
  using Bits = Family<Capacity, true>;
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ Capacity ^ 0x5349474e534846ULL);
  CAPTURE(replay_seed, Capacity, Bits::PossiblyUnknown);
  for (unsigned width : {1u, 7u, 8u, 9u, 16u, 17u, 31u, 32u, 33u, 63u, 64u, 65u, 127u, 128u}) {
    if (width > Capacity) continue;
    CAPTURE(width);
    for (const auto& raw : bits_test::edges(width)) {
      for (unsigned count : {0u, 1u, width - 1, width, width + 1, 2 * width}) {
        bits_test::shifts(bits_test::make<Bits>(raw, width),
                          udb::_Bits<32, false>{count}, raw, count);
      }
    }
    for (unsigned sample = 0; sample < 64; ++sample) {
      CAPTURE(sample);
      const auto raw = bits_test::random_raw(rng, width);
      const unsigned count = rng() % (2 * width + 1);
      bits_test::shifts(bits_test::make<Bits>(raw, width),
                        udb::_Bits<32, false>{count}, raw, count);
    }
  }
}

TEST_CASE("Signed known runtime arithmetic and relations",
          "[bits][native][signed-runtime][known-runtime][arithmetic]") {
  signed_runtime_arithmetic<udb::_RuntimeBits, 64>();
  signed_runtime_arithmetic<udb::_RuntimeBits, 128>();
}

TEST_CASE("Signed unknown-capable runtime arithmetic and relations",
          "[bits][native][signed-runtime][unknown-runtime][arithmetic]") {
  signed_runtime_arithmetic<udb::_PossiblyUnknownRuntimeBits, 64>();
  signed_runtime_arithmetic<udb::_PossiblyUnknownRuntimeBits, 128>();
}

TEST_CASE("Signed known runtime shifts and relations",
          "[bits][native][signed-runtime][known-runtime][shifts]") {
  signed_runtime_shifts<udb::_RuntimeBits, 64>();
  signed_runtime_shifts<udb::_RuntimeBits, 128>();
}

TEST_CASE("Signed unknown-capable runtime shifts and relations",
          "[bits][native][signed-runtime][unknown-runtime][shifts]") {
  signed_runtime_shifts<udb::_PossiblyUnknownRuntimeBits, 64>();
  signed_runtime_shifts<udb::_PossiblyUnknownRuntimeBits, 128>();
}

template <unsigned Capacity>
void unknown_runtime_widening() {
  using Bits = udb::_PossiblyUnknownRuntimeBits<Capacity, true>;
  for (unsigned width : {1u, 8u, 17u, 33u, 64u, 65u, 128u}) {
    if (width > Capacity) continue;
    CAPTURE(Capacity, width);
    for (const auto& lhs_raw : bits_test::edges(width)) {
      for (const auto& rhs_raw : bits_test::edges(width)) {
        INFO("raw lhs=" << lhs_raw.get_str(16) << " rhs=" << rhs_raw.get_str(16));
        const auto lhs = bits_test::make<Bits>(lhs_raw, width);
        const auto rhs = bits_test::make<Bits>(rhs_raw, width);
        const mpz_class lv = bits_test::interpret(lhs_raw, width, true);
        const mpz_class rv = bits_test::interpret(rhs_raw, width, true);
        bits_test::value<true>(lhs.widening_add(rhs), lv + rv, width + 1);
        bits_test::value<true>(lhs.widening_sub(rhs), lv - rv, width + 1);
        bits_test::value<true>(lhs.widening_mul(rhs), lv * rv, 2 * width);
      }
    }
  }
}

TEST_CASE("Signed unknown-capable runtime widening value regression",
          "[bits][native][signed-runtime][unknown-runtime][widening-values]") {
  unknown_runtime_widening<64>();
  unknown_runtime_widening<128>();
}

template <template <unsigned, bool> class Family>
void literal_signed_widening() {
  const auto minus_one = bits_test::make<Family<64, true>>(mpz_class{1}, 1);
  const auto zero = bits_test::make<Family<64, true>>(mpz_class{0}, 1);
  const auto sub = minus_one.widening_sub(zero);
  CHECK(sub.width() == 2);
  CHECK(sub.get() == -1);
  const auto mul = minus_one.widening_mul(minus_one);
  CHECK(mul.width() == 2);
  CHECK(mul.get() == 1);
}

TEST_CASE("Signed known runtime widening literal regression",
          "[bits][native][signed-runtime][known-runtime][literal]") {
  literal_signed_widening<udb::_RuntimeBits>();
}

TEST_CASE("Signed unknown-capable runtime active-sign literal regressions",
          "[bits][native][signed-runtime][unknown-runtime][literal]") {
  using Bits = udb::_PossiblyUnknownRuntimeBits<64, true>;
  literal_signed_widening<udb::_PossiblyUnknownRuntimeBits>();
  const auto minus_one = bits_test::make<Bits>(mpz_class{255}, 8);
  const auto zero = bits_test::make<Bits>(mpz_class{0}, 8);
  const auto two = bits_test::make<Bits>(mpz_class{2}, 8);
  CHECK(minus_one.widening_add(zero).get() == -1);
  CHECK((minus_one / two).get() == 0);
  CHECK((minus_one % two).get() == -1);
  CHECK(minus_one < zero);
  CHECK(zero > minus_one);
  const udb::_RuntimeBits<64, true> known_minus_one{
      udb::_Bits<8, true>{-1}, udb::_Bits<32, false>{8}};
  CHECK(minus_one == known_minus_one);
  CHECK(known_minus_one == minus_one);
  const udb::_Bits<17, true> fixed_two{2};
  bits_test::arithmetic(minus_one, fixed_two, mpz_class{255}, mpz_class{2});
  const udb::_RuntimeBits<64, true> known_minus_two{
      udb::_Bits<9, true>{-2}, udb::_Bits<32, false>{9}};
  bits_test::arithmetic(minus_one, known_minus_two, mpz_class{255}, mpz_class{510});
  const udb::_PossiblyUnknownBits<64, true> fixed_partial{
      udb::_Bits<64, true>{255}, udb::_Bits<64, false>{1}};
  const Bits partial{fixed_partial, udb::_Bits<32, false>{8}};
  CHECK_THROWS_AS(partial.widening_add(zero), udb::UndefinedValueError);
  CHECK_THROWS_AS(partial.widening_sub(zero), udb::UndefinedValueError);
  CHECK_THROWS_AS(partial.widening_mul(zero), udb::UndefinedValueError);
  CHECK_THROWS_AS(partial / two, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial % two, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial == zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial != zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial < zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial <= zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial > zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial >= zero, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial / fixed_two, udb::UndefinedValueError);
  CHECK_THROWS_AS(partial < known_minus_two, udb::UndefinedValueError);
}
