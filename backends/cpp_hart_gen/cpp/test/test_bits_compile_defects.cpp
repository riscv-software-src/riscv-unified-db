// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

template <unsigned Capacity>
void signed_storage_regression() {
  using Bits = udb::_RuntimeBits<Capacity, true>;
  const uint64_t replay_seed = bits_test::seed();
  std::mt19937_64 rng(replay_seed ^ Capacity ^ 0x53544f52414745ULL);
  CAPTURE(replay_seed, Capacity);
  for (unsigned width : {1u, 7u, 8u, 17u, 32u, 64u, 128u}) {
    if (width > Capacity) continue;
    CAPTURE(width);
    auto check = [&](const mpz_class& raw_lhs, const mpz_class& raw_rhs) {
      INFO("raw lhs=" << raw_lhs.get_str(16) << " rhs=" << raw_rhs.get_str(16));
      const auto lhs = bits_test::make<Bits>(raw_lhs, width);
      const auto rhs = bits_test::make<Bits>(raw_rhs, width);
      const mpz_class expected = bits_test::interpret(raw_lhs, width, true)
                                 + bits_test::interpret(raw_rhs, width, true);
      bits_test::value<true>(lhs + rhs, expected, width);
      bits_test::value<true>(lhs.widening_add(rhs), expected, width + 1);
    };
    for (const auto& lhs : bits_test::edges(width)) {
      for (const auto& rhs : bits_test::edges(width)) check(lhs, rhs);
    }
    for (unsigned sample = 0; sample < 64; ++sample) {
      CAPTURE(sample);
      const auto lhs = bits_test::random_raw(rng, width);
      const auto rhs = bits_test::random_raw(rng, width);
      check(lhs, rhs);
    }
  }
}

TEST_CASE("Signed runtime native storage casts preserve addition", "[bits][defect][signed]") {
  signed_storage_regression<32>();
  signed_storage_regression<64>();
  signed_storage_regression<128>();
}

TEST_CASE("Signed unknown-capable logical shift retains a known mask", "[bits][defect][signed]") {
  const udb::_PossiblyUnknownBits<8, true> lhs{udb::_Bits<8, true>{-1}};
  for (unsigned count : {0u, 1u, 7u, 8u, 9u}) {
    CAPTURE(count);
    mpz_class expected;
    const mpz_class raw = 255;
    mpz_fdiv_q_2exp(expected.get_mpz_t(), raw.get_mpz_t(), count);
    bits_test::value<true>(lhs >> udb::_Bits<8, false>{count}, expected, 8);
  }
  const udb::_PossiblyUnknownBits<8, true> partial{
      udb::_Bits<8, true>{-2}, udb::_Bits<8, false>{1}};
  const auto unshifted = partial >> udb::_Bits<8, false>{0};
  CHECK(unshifted.unknown_mask().get() == 1);
  CHECK_THROWS_AS(unshifted.get(), udb::UndefinedValueError);
  bits_test::value<true>(partial >> udb::_Bits<8, false>{1}, mpz_class{127}, 8);
}

TEST_CASE("GMP arithmetic right shift handles sign and oversized counts", "[bits][defect][gmp]") {
  for (const auto& raw : bits_test::edges(129)) {
    INFO("raw=" << raw.get_str(16));
    for (unsigned count : {0u, 1u, 64u, 128u, 129u, 130u, 258u}) {
      CAPTURE(count);
      const udb::_Bits<129, false> lhs{raw};
      const mpz_class signed_raw = bits_test::interpret(raw, 129, true);
      mpz_class expected;
      mpz_fdiv_q_2exp(expected.get_mpz_t(), signed_raw.get_mpz_t(), count);
      bits_test::value<false>(lhs.sra(udb::_Bits<32, false>{count}), expected, 129);
    }
  }
}
