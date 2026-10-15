// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include <catch2/matchers/catch_matchers_string.hpp>

#include "bits_property.hpp"

template <class L, class R>
concept LeftShiftable = requires(const L& lhs, const R& rhs) { lhs << rhs; };

TEST_CASE("Native Bits independent oracle and replay contract", "[bits][native][oracle]") {
  using namespace bits_test;
  CHECK(truncate(mpz_class(-1), 8) == 255);
  CHECK(interpret(mpz_class(255), 8, true) == -1);
  CHECK(interpret(mpz_class(128), 8, true) == -128);
  CHECK(interpret(power(128) - 1, 128, true) == -1);
  CHECK(integer_value(std::numeric_limits<int64_t>::min()) == -power(63));
  CHECK(integer_value(std::numeric_limits<__int128>::min()) == -power(127));
  CHECK(integer_value(std::numeric_limits<unsigned __int128>::max()) == power(128) - 1);
  CHECK(integer_value(mpz_class(-123456)) == -123456);
  std::mt19937_64 first(seed()), second(seed());
  for (unsigned i = 0; i < 64; ++i) CHECK(random_raw(first, 128) == random_raw(second, 128));
  // A fixed sentinel guards changes to the native random stream independently of the environment.
  std::mt19937_64 sentinel(1234);
  CHECK(sentinel() == UINT64_C(17473339210090333472));
}

template <unsigned N>
void construction() {
  using namespace bits_test;
  const auto oversized = std::vector<mpz_class>{-1,       -power(N),    -power(N) - 1,
                                                power(N), power(N) + 1, power(2 * N) - 1};
  for (const auto& raw : oversized) {
    INFO("raw=" << raw.get_str(16));
    value<false>(make<udb::_Bits<N, false>>(raw, N), raw, N);
    value<true>(make<udb::_Bits<N, true>>(raw, N), raw, N);
    value<false>(make<udb::_RuntimeBits<N, false>>(raw, N), raw, N);
    value<true>(make<udb::_RuntimeBits<N, true>>(raw, N), raw, N);
    value<false>(make<udb::_PossiblyUnknownBits<N, false>>(raw, N), raw, N);
    value<true>(make<udb::_PossiblyUnknownBits<N, true>>(raw, N), raw, N);
    value<false>(make<udb::_PossiblyUnknownRuntimeBits<N, false>>(raw, N), raw, N);
    value<true>(make<udb::_PossiblyUnknownRuntimeBits<N, true>>(raw, N), raw, N);
  }
}

TEST_CASE("Native Bits constructor wrap and signed interpretation", "[bits][native][boundary]") {
  construction<1>();
  construction<8>();
  construction<16>();
  construction<32>();
  construction<64>();
  construction<128>();
}

template <unsigned N>
void unknown_errors() {
  using namespace udb;
  using Unknown = _PossiblyUnknownBits<N, false>;
  using Runtime = _PossiblyUnknownRuntimeBits<N, false>;
  const _Bits<N, false> known{1};
  const Unknown partial{known, _Bits<N, false>{1}};
  const Unknown defined{known};
  const Runtime runtime{partial, _Bits<32, false>{N}};
  REQUIRE_THROWS_AS(partial.get(), UndefinedValueError);
  REQUIRE_THROWS_AS(partial.to_defined(), UndefinedValueError);
  REQUIRE_THROWS_AS(partial == known, UndefinedValueError);
  REQUIRE_THROWS_AS(partial + defined, UndefinedValueError);
  REQUIRE_THROWS_AS(known + partial, UndefinedValueError);
  REQUIRE_THROWS_AS(partial - defined, UndefinedValueError);
  REQUIRE_THROWS_AS(partial * defined, UndefinedValueError);
  REQUIRE_THROWS_AS(partial / defined, UndefinedValueError);
  REQUIRE_THROWS_AS(partial % defined, UndefinedValueError);
  REQUIRE_THROWS_AS(partial.widening_add(defined), UndefinedValueError);
  REQUIRE_THROWS_AS(partial.widening_sub(defined), UndefinedValueError);
  REQUIRE_THROWS_AS(partial.widening_mul(defined), UndefinedValueError);
  REQUIRE_THROWS_AS(runtime.get(), UndefinedValueError);
  REQUIRE_THROWS_AS(runtime.to_defined(), UndefinedValueError);
  REQUIRE_THROWS_AS(runtime + defined, UndefinedValueError);
  REQUIRE_THROWS_AS(runtime.widening_add(defined), UndefinedValueError);
  REQUIRE_THROWS_AS(runtime.widening_sub(defined), UndefinedValueError);
  REQUIRE_THROWS_AS(runtime.widening_mul(defined), UndefinedValueError);
  REQUIRE((partial & _Bits<N, false>{0}).get() == 0);
  REQUIRE((partial | _Bits<N, false>{bits_test::power(N) - 1}).get() ==
          _Bits<N, false>{bits_test::power(N) - 1}.get());
  REQUIRE(defined.get() == 1);
}

TEST_CASE("Native Bits unknown and unsupported semantics", "[bits][native][errors]") {
  STATIC_REQUIRE_FALSE((LeftShiftable<udb::_Bits<8, false>, udb::_Bits<8, true>>));
  STATIC_REQUIRE_FALSE((std::is_default_constructible_v<udb::_RuntimeBits<8, false>>));
  STATIC_REQUIRE_FALSE(
      (std::is_default_constructible_v<udb::_PossiblyUnknownRuntimeBits<8, false>>));
  unknown_errors<8>();
  unknown_errors<64>();
  unknown_errors<128>();
}

TEST_CASE("Native Bits bounded runtime width errors", "[bits][native][errors]") {
  using namespace udb;
  REQUIRE_THROWS_WITH((_RuntimeBits<8, false>{_Bits<8, false>{0}, _Bits<32, false>{9}}),
                      Catch::Matchers::ContainsSubstring("width is larger than MaxN"));
  REQUIRE_THROWS_WITH((_RuntimeBits<64, false>{_Bits<64, false>{0}, _Bits<32, false>{65}}),
                      Catch::Matchers::ContainsSubstring("width is larger than MaxN"));
  REQUIRE_THROWS_WITH((_RuntimeBits<128, false>{_Bits<128, false>{0}, _Bits<32, false>{129}}),
                      Catch::Matchers::ContainsSubstring("width is larger than MaxN"));
  REQUIRE_THROWS_WITH((_RuntimeBits<BitsInfinitePrecision, false>{
                          _Bits<8, true>{-1}, _Bits<32, false>{BitsInfinitePrecision}}),
                      Catch::Matchers::ContainsSubstring(
                          "Cannot represent a negative number in infinite precision"));
}
