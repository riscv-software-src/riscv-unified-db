// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

// Keep the original literal reproducers alongside broader native regressions.
TEST_CASE("Runtime unknown-capable sra must mask to runtime width", "[bits][defect]") {
  const udb::_PossiblyUnknownRuntimeBits<64, false> lhs{udb::_Bits<64, false>{1},
                                                        udb::_Bits<32, false>{1}};
  const auto result = lhs.sra(udb::_Bits<32, false>{0});
  REQUIRE(result.width() == 1);
  REQUIRE(result.get() == 1);
}

TEST_CASE("Runtime signed widening must sign extend before changing width", "[bits][defect]") {
  const udb::_RuntimeBits<8, true> lhs{udb::_Bits<8, true>{-1}};
  const udb::_RuntimeBits<8, true> rhs{udb::_Bits<8, true>{0}};
  const auto result = lhs.widening_add(rhs);
  REQUIRE(result.width() == 9);
  REQUIRE(result.get() == -1);
}

TEST_CASE("Runtime unknown-capable signed get must use runtime sign bit", "[bits][defect]") {
  const udb::_PossiblyUnknownRuntimeBits<16, true> lhs{udb::_Bits<16, true>{255},
                                                       udb::_Bits<32, false>{8}};
  REQUIRE(lhs.width() == 8);
  REQUIRE(lhs.get() == -1);
}

template <unsigned Capacity>
void signed_get_regression() {
  using Bits = udb::_PossiblyUnknownRuntimeBits<Capacity, true>;
  for (unsigned width : {1u, 7u, 8u, 9u, 16u, 17u, 31u, 32u, 33u, 63u, 64u, 65u, 127u, 128u}) {
    if (width > Capacity) continue;
    CAPTURE(Capacity, width);
    for (const auto& raw : bits_test::edges(width)) {
      INFO("raw=" << raw.get_str(16));
      const auto value = bits_test::make<Bits>(raw, width);
      bits_test::value<true>(value, raw, width);
      CHECK(bits_test::integer_value(value.get_ignore_unknown())
            == bits_test::interpret(raw, width, true));
    }
    const udb::_PossiblyUnknownBits<Capacity, true> unknown{
        udb::_Bits<Capacity, true>{0}, udb::_Bits<Capacity, false>{1}};
    const Bits value{unknown, udb::_Bits<32, false>{width}};
    CHECK_THROWS_AS(value.get(), udb::UndefinedValueError);
    CHECK(bits_test::integer_value(value.get_ignore_unknown()) == 0);
  }
}

TEST_CASE("Signed unknown-capable runtime access uses active width", "[bits][defect][signed]") {
  signed_get_regression<64>();
  signed_get_regression<128>();
}

template <unsigned Capacity>
void unknown_sra_regression() {
  using Bits = udb::_PossiblyUnknownRuntimeBits<Capacity, false>;
  for (unsigned width : {1u, 7u, 8u, 17u, 33u, 64u, 65u, 128u, 129u}) {
    if (width > Capacity) continue;
    CAPTURE(Capacity, width);
    const mpz_class sign = bits_test::power(width - 1);
    const mpz_class ones = bits_test::power(width) - 1;
    for (unsigned pattern = 0; pattern < 3; ++pattern) {
      CAPTURE(pattern);
      // Unknown sign, known negative with unknown low bit, known positive
      // with unknown low bit. Unknown value bits are chosen explicitly as 0.
      const mpz_class raw = pattern == 1 ? sign : mpz_class{0};
      const mpz_class unknown_mask = pattern == 0 ? sign : mpz_class{1};
      const udb::_PossiblyUnknownBits<Capacity, false> fixed{
          udb::_Bits<Capacity, false>{raw}, udb::_Bits<Capacity, false>{unknown_mask}};
      const Bits lhs{fixed, udb::_Bits<32, false>{width}};
      for (unsigned count : {0u, 1u, width - 1, width, width + 1}) {
        CAPTURE(count);
        mpz_class expected_value, expected_mask;
        mpz_fdiv_q_2exp(expected_value.get_mpz_t(), raw.get_mpz_t(), count);
        mpz_fdiv_q_2exp(expected_mask.get_mpz_t(), unknown_mask.get_mpz_t(), count);
        const mpz_class fill = ones ^ (count >= width ? mpz_class{0}
                                                    : bits_test::power(width - count) - 1);
        if (pattern == 0 || width == 1) expected_mask |= fill;
        else if (pattern == 1) expected_value |= fill;
        const auto result = lhs.sra(udb::_Bits<32, false>{count});
        REQUIRE(result.width() == width);
        CHECK(bits_test::integer_value(result.get_ignore_unknown()) == expected_value);
        CHECK(bits_test::integer_value(result.unknown_mask().get()) == expected_mask);
        if (expected_mask != 0) CHECK_THROWS_AS(result.get(), udb::UndefinedValueError);
        else CHECK(bits_test::integer_value(result.get()) == expected_value);
      }
    }
  }
}

TEST_CASE("Runtime arithmetic right shift propagates active sign unknowns",
          "[bits][defect][unknown]") {
  unknown_sra_regression<64>();
  unknown_sra_regression<128>();
  unknown_sra_regression<129>();
}
