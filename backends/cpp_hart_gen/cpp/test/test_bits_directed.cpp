
#include <fmt/core.h>

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <catch2/generators/catch_generators_adapters.hpp>
#include <catch2/generators/catch_generators_random.hpp>
#include <catch2/matchers/catch_matchers_string.hpp>
#include <iostream>
#include <udb/bits.hpp>
#include <udb/defines.hpp>

using Catch::Matchers::Equals;

consteval __uint128_t operator""_u128(const char *x) {
  __uint128_t y = 0;
  auto len = strlen(x);

  if (x[0] == '0' && (x[1] == 'x' || x[1] == 'X')) {
    for (int i = 2; x[i] != '\0'; ++i) {
      if (x[i] == '\'') {
        continue;
      }
      y *= 16ull;
      if ('0' <= x[i] && x[i] <= '9')
        y += x[i] - '0';
      else if ('A' <= x[i] && x[i] <= 'F')
        y += x[i] - 'A' + 10;
      else if ('a' <= x[i] && x[i] <= 'f')
        y += x[i] - 'a' + 10;
    }
  } else if (x[0] == '0' && (x[1] == 'o' || x[1] == 'O')) {
    for (int i = 2; x[i] != '\0'; ++i) {
      if (x[i] == '\'') {
        continue;
      }
      y *= 8ull;
      if ('0' <= x[i] && x[i] <= '7') y += x[i] - '0';
    }
  } else if (x[0] == '0' && (x[1] == 'b' || x[1] == 'B')) {
    for (int i = 2; x[i] != '\0'; ++i) {
      if (x[i] == '\'') {
        continue;
      }
      y *= 2ull;
      if ('0' <= x[i] && x[i] <= '1') y += x[i] - '0';
    }
  } else {
    __uint128_t pow = 1;
    for (int i = len - 1; i >= '\0'; i--) {
      if (x[i] == '\'') {
        continue;
      }
      if ('0' <= x[i] && x[i] <= '9') y += ((unsigned __int128)(x[i] - '0')) * pow;
      else throw std::runtime_error("bad literal");
      pow *= 10;
    }
  }
  return y;
}

std::ostream &operator<<(std::ostream &stream, const __uint128_t &val) {
  stream << fmt::format("0x{:x}", val);
  return stream;
}

std::ostream &operator<<(std::ostream &stream, const __int128_t &val) {
  stream << fmt::format("0x{:x}", val);
  return stream;
}

using namespace udb;

constexpr unsigned InfinitePrecision = Bits<64>::InfinitePrecision;
constexpr Bits<64> InfinitePrecisionBits = Bits<64>{Bits<64>::InfinitePrecision};
constexpr unsigned GmpPrecision = Bits<64>::MaxNativePrecision + 1;

static_assert(Bits<32>{0xffffffffffffffffull}.get() == 0xffffffffu);
static_assert(static_cast<int32_t>(Bits<32>{0xffffffffffffffffull}.get()) == -1);
static_assert(static_cast<int32_t>(Bits<32>{0xffffffffffffffffull}.get()) < 0);

static_assert(Bits<31>{Bits<31>{0x7fff'ffffu}}.get() == 2147483647);
static_assert(Bits<31>{Bits<31>{-1}}.get() == 2147483647);
static_assert(Bits<31>{Bits<31>{1234}}.get() == 1234);
static_assert(Bits<32>{Bits<32>{-1}}.get() == 4294967295);
static_assert(Bits<32>{Bits<32>{1234}}.get() == 1234);

static_assert((0b010101_b).width() == 5);
static_assert(("0b010101"_xb).width() == 5);
static_assert(("0bx10101"_xb).width() == 6);

TEST_CASE("InifitePrecision conversion", "[bits]") {
  Bits<InfinitePrecision> a{Bits<InfinitePrecision>{0x7fff'ffffu}};
  REQUIRE(a.get() == 2147483647);

  REQUIRE(_Bits<InfinitePrecision, true>{-1} == _Bits<8, true>{-1});
  REQUIRE(_Bits<InfinitePrecision, true>{_Bits<8, true>{-1}} == _Bits<8, true>{-1});
  REQUIRE(_Bits<8, true>{_Bits<InfinitePrecision, true>{-1}} == _Bits<8, true>{-1});
  REQUIRE(_Bits<7, true>{_Bits<InfinitePrecision, true>{-1}} == _Bits<8, true>{-1});
  REQUIRE(_Bits<9, true>{_Bits<InfinitePrecision, true>{-1}} == _Bits<8, true>{-1});

  REQUIRE(_Bits<InfinitePrecision, true>{-1} == _Bits<128, true>{-1});
  REQUIRE(_Bits<InfinitePrecision, true>{_Bits<128, true>{-1}} == _Bits<128, true>{-1});
  REQUIRE(_Bits<128, true>{_Bits<InfinitePrecision, true>{-1}} == _Bits<128, true>{-1});
  REQUIRE(_Bits<GmpPrecision, true>{_Bits<InfinitePrecision, true>{-1}} == _Bits<128, true>{-1});
}

// negation
static_assert((-(-Bits<64>(5))).get() == Bits<64>(5).get());
static_assert((-(-Bits<64>(5))).get() == 5);
static_assert(_Bits<64, true>(-Bits<64>(5)).get() == -5);
static_assert((-Bits<64>(5)).get() == 18446744073709551611ull);
static_assert(_Bits<64, true>(-Bits<64>(5)).get() < 0);

TEST_CASE("Negation", "[bits]") {
  REQUIRE((-(-Bits<65>(5))).get() == Bits<64>(5).get());
  REQUIRE((-(-Bits<65>(5))).get() == 5);
  REQUIRE(_Bits<65, true>(-Bits<65>(5)).get() == -5);
  REQUIRE(_Bits<65, true>(-Bits<65>(5)).get() < 0);

  REQUIRE((-(-Bits<GmpPrecision>(5))).get() == Bits<64>(5).get());
  REQUIRE((-(-Bits<GmpPrecision>(5))).get() == 5);
  REQUIRE(_Bits<GmpPrecision, true>(-Bits<GmpPrecision>(5)).get() == -5_mpz);
  REQUIRE(_Bits<GmpPrecision, true>(-Bits<GmpPrecision>(5)).get() < 0);

  REQUIRE((-(-Bits<InfinitePrecision>(5))).get() == Bits<64>(5).get());
  REQUIRE((-(-Bits<InfinitePrecision>(5))).get() == 5);
  REQUIRE(_Bits<InfinitePrecision, true>(-Bits<InfinitePrecision>(5)).get() == -5_mpz);
  REQUIRE(_Bits<InfinitePrecision, true>(-Bits<InfinitePrecision>(5)).get() < 0);
}

// inversion
static_assert((~(~Bits<64>(5))).get() == Bits<64>(5).get());
static_assert((~(~Bits<64>(5))).get() == 5);
static_assert(_Bits<64, true>(~Bits<64>(5)).get() == -6);
static_assert((~Bits<64>(5)).get() == 18446744073709551610ull);
static_assert(_Bits<64, true>(~Bits<64>(5)).get() < 0);

TEST_CASE("Inversion", "[bits]") {
  REQUIRE((~(~Bits<65>(5))).get() == Bits<64>(5).get());
  REQUIRE((~(~Bits<65>(5))).get() == 5);
  REQUIRE(_Bits<65, true>(~Bits<65>(5)).get() == -6);
  REQUIRE((~Bits<65>(5)).get() == 0x1fffffffffffffffa_u128);
  REQUIRE(_Bits<65, true>(~Bits<65>(5)).get() < 0);

  REQUIRE((~(~Bits<GmpPrecision>(5))).get() == Bits<GmpPrecision>(5).get());
  REQUIRE((~(~Bits<GmpPrecision>(5))).get() == 5);
  REQUIRE(_Bits<GmpPrecision, true>(~Bits<GmpPrecision>(5)).get() == -6);
  REQUIRE((~Bits<GmpPrecision>(5)).get() == 0x1fffffffffffffffffffffffffffffffa_mpz);
  REQUIRE(_Bits<64, true>(~Bits<GmpPrecision>(5)).get() < 0);

  REQUIRE((~(~Bits<InfinitePrecision>(5))).get() == Bits<InfinitePrecision>(5).get());
  REQUIRE((~(~Bits<InfinitePrecision>(5))).get() == 5);
  REQUIRE(_Bits<InfinitePrecision, true>(~Bits<InfinitePrecision>(5)).get() == -6);
  REQUIRE(_Bits<64, true>(~Bits<InfinitePrecision>(5)).get() < 0);
  REQUIRE(_Bits<128, true>(~Bits<InfinitePrecision>(5)).get() < 0);
  REQUIRE(_Bits<128, true>(~Bits<InfinitePrecision>(0x1'ffffffff'ffffffff_u128)).get() < 0);
}
TEST_CASE("64-bit Assignment", "[bits]") {
  Bits<64> a{5};
  Bits<64> b;
  b = a;
  REQUIRE(a.get() == b.get());
  REQUIRE(a.get() == 5);
}
TEST_CASE("65-bit Assignment", "[bits]") {
  Bits<65> a{5};
  Bits<65> b;
  b = a;
  REQUIRE(a.get() == b.get());
  REQUIRE(a.get() == 5);
}

TEST_CASE("GmpPrecision-bit Assignement", "[bits]") {
  Bits<GmpPrecision> a{5};
  Bits<GmpPrecision> b;
  b = a;
  REQUIRE(a.get() == b.get());
  REQUIRE(a.get() == 5);
}

TEST_CASE("64-bit unsigned negation", "[bits]") {
  Bits<64> a;
  a = 5_b;
  REQUIRE(a.get() == 5);
  a = -5_sb;
  REQUIRE(a.get() == 18446744073709551611ull);
}

TEST_CASE("65-bit unsigned negation", "[bits]") {
  Bits<65> a;
  a = 5_b;
  REQUIRE(a.get() == 5);
  a = -5_sb;
  REQUIRE(a.get() == 0x1fffffffffffffffb_u128);
}

TEST_CASE("GmpPrecision-bit unsigned negation", "[bits]") {
  Bits<GmpPrecision> a;
  a = 5_b;
  REQUIRE(a.get() == 5);
  a = -5_sb;
  REQUIRE(a.get() == 0x1fffffffffffffffffffffffffffffffb_mpz);
}

TEST_CASE("mixed-bit assignment", "[bits]") {
  Bits<GmpPrecision> a;
  Bits<64> b = 5_b;
  a = b;
  REQUIRE(a.get() == 5);
}

TEST_CASE("mixed-bit assignment, reversed", "[bits]") {
  Bits<64> a;
  Bits<GmpPrecision> b = 5_b;
  a = b;
  REQUIRE(a.get() == 5);
}

TEST_CASE("mixed-bit assignment, negated", "[bits]") {
  Bits<64> a;
  Bits<GmpPrecision> b = -5_sb;
  a = b;
  REQUIRE(a.get() == 0xfffffffffffffffbull);
}

TEST_CASE("mixed-bit assignment, negated, reversed", "[bits]") {
  Bits<64> a{Bits<GmpPrecision>{-5}};
  REQUIRE(a.get() == 0xfffffffffffffffbull);
}

TEST_CASE("mixed-bit assignment, negated, constructor", "[bits]") {
  Bits<GmpPrecision> a{Bits<65>{-5}};
  REQUIRE(a.get() == 0x1fffffffffffffffb_mpz);
}

TEST_CASE("Signed 128 assignment to gmp", "[bits]") {
  _Bits<GmpPrecision, true> a{_Bits<128, true>{std::numeric_limits<__int128>::min()}};
  REQUIRE(a.get().get_ui() == static_cast<uint64_t>(std::numeric_limits<__int128>::min()));
  // REQUIRE((a.get() >> 64).get_ui() ==
  // static_cast<uint64_t>(std::numeric_limits<__int128>::min()
  // >> 64));
  REQUIRE(a < 0_b);
  REQUIRE(a.get() == to_gmp(std::numeric_limits<__int128>::min()));
}

TEST_CASE("Signed assignment to gmp", "[bits]") {
  _Bits<GmpPrecision, true> a{-5};
  REQUIRE(a < 0_b);
  REQUIRE(a == -5_sb);

  _Bits<GmpPrecision, true> b{static_cast<__int128>(-5)};
  REQUIRE(b < 0_b);
  REQUIRE(b == -5_sb);
  REQUIRE(b.get() == to_gmp(static_cast<__int128>(-5)));
  REQUIRE(b + 1_sb == -4_sb);
  REQUIRE((b + 1_sb).get() == -4_mpz);
  REQUIRE((b + 1_b).get() == 680564733841876926926749214863536422908_mpz);
  REQUIRE(b + 6_b > 0_b);
}

TEST_CASE("mixed-bit assignment, bits comparison", "[bits]") {
  Bits<GmpPrecision> a;
  Bits<64> b{5};
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("mixed-bit assignment, bits comparison, reversed", "[bits]") {
  Bits<64> a;
  Bits<GmpPrecision> b{5};
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("mixed-bit multiplication", "[bits]") {
  Bits<64> a{5};
  Bits<GmpPrecision> b{5};
  REQUIRE(a * b == 25_b);
}

TEST_CASE("mixed-bit multiplication, reversed", "[bits]") {
  Bits<GmpPrecision> a{5};
  Bits<64> b{5};
  REQUIRE(a * b == 25_b);
}

TEST_CASE("GmpPrecision-bit multiplication, reversed", "[bits]") {
  Bits<GmpPrecision> a;
  Bits<GmpPrecision> b{5};
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("GmpPrecision-bit multiplication, literal", "[bits]") {
  Bits<GmpPrecision> a{5};
  REQUIRE(a * 5_b == 25_b);
}

TEST_CASE("GmpPrecision-bit multiplication, literal, reversed", "[bits]") {
  Bits<GmpPrecision> a{5};
  REQUIRE(5_b * a == 25_b);
}

TEST_CASE("8-bit multiplication, literal, reversed", "[bits]") {
  Bits<8> a{5};
  REQUIRE(a * 255_b == 0xfb_b);
}

TEST_CASE("8-bit SRA", "[bits]") {
  Bits<8> a(0x80);
  REQUIRE(a.sra(3_b) == 0xf0_b);
}

TEST_CASE("9-bit SRA", "[bits]") {
  Bits<9> a{0x100};
  REQUIRE(a.sra(3_b) == 0x1e0_b);
}

TEST_CASE("65-bit SRA", "[bits]") {
  Bits<65> a{0x10000000000000000_mpz};
  REQUIRE(a.sra(3_b).get() == 0x1e000000000000000_u128);
}

TEST_CASE("multiplication", "[bits]") {
  REQUIRE(Bits<64>{32} * Bits<64>{8} == 256_b);
  REQUIRE(Bits<8>{32} * Bits<8>{8} == 0_b);
  REQUIRE(Bits<8>{32}.widening_mul(Bits<8>{8}) == 256_b);

  REQUIRE(Bits<64>{33} * Bits<64>{8} == 264_b);
  REQUIRE(Bits<8>{33} * Bits<8>{8} == 8_b);
  REQUIRE(Bits<8>{33}.widening_mul(Bits<8>{8}) == 264_b);

  REQUIRE(Bits<64>{255} * Bits<64>{255} == 65025_b);
  REQUIRE(Bits<8>{255} * Bits<8>{255} == 1_b);
  REQUIRE(Bits<8>{255}.widening_mul(Bits<8>{255}) == 65025_b);

  REQUIRE(Bits<64>{255} * Bits<64>{256} == 65280_b);
  REQUIRE(Bits<8>{255} * Bits<9>{256} == 256_b);
  REQUIRE(Bits<8>{255}.widening_mul(Bits<9>{256}) == 65280_b);
}

TEST_CASE("Printing", "[bits]") {
  REQUIRE_THAT(fmt::format("{}", Bits<GmpPrecision>{16}), Equals("16"));
  REQUIRE_THAT(fmt::format("{:x}", Bits<GmpPrecision>{16}), Equals("10"));
  REQUIRE_THAT(fmt::format("{:#x}", Bits<GmpPrecision>{16}), Equals("0x10"));
  REQUIRE_THAT(fmt::format("{:#10x}", Bits<GmpPrecision>{16}), Equals("      0x10"));
  REQUIRE_THAT(fmt::format("{:#010x}", Bits<GmpPrecision>{16}), Equals("0x00000010"));
  // fmt::print("{+:#10x}\n", Bits<GmpPrecision>{16});
}

TEST_CASE("Runtime", "[bits]") {
  REQUIRE(_RuntimeBits<8, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<8, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<8, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<8, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<8, false>{0_b, 9_b}), std::runtime_error);

  REQUIRE(_RuntimeBits<16, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<16, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<16, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<16, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<16, false>{0_b, 65_b}), std::runtime_error);

  REQUIRE(_RuntimeBits<32, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<32, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<32, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<32, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<32, false>{0_b, 65_b}), std::runtime_error);

  REQUIRE(_RuntimeBits<64, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<64, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<64, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<64, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<64, false>{0_b, 65_b}), std::runtime_error);

  REQUIRE(_RuntimeBits<128, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<128, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<128, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<128, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<128, false>{0_b, 129_b}), std::runtime_error);

  REQUIRE(_RuntimeBits<GmpPrecision, false>(0_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<GmpPrecision, false>(255_b, 8_b) == 255_b);
  REQUIRE(_RuntimeBits<GmpPrecision, false>(256_b, 8_b) == 0_b);
  REQUIRE(_RuntimeBits<GmpPrecision, false>(257_b, 8_b) == 1_b);
  REQUIRE_THROWS_AS((_RuntimeBits<GmpPrecision, false>{0_b, 130_b}), std::runtime_error);

  _RuntimeBits<64, false> a(0_b, 8_b);
  a = 255_b;
  REQUIRE(a == 255_b);
  a = a + 1_b;
  REQUIRE(a == 0_b);

  REQUIRE(static_cast<int8_t>(128) == -128);
  REQUIRE(_Bits<8, true>(128) == -128_sb);
  REQUIRE(_RuntimeBits<8, true>(128_b, 8_b) == -128_sb);

  _RuntimeBits<64, true> b(128_b, 8_b);
  REQUIRE(b == -128_sb);
  REQUIRE(b.get() == -128);
  REQUIRE(_RuntimeBits<64, false>(b).get() == 128);
  // REQUIRE(static_cast<uint16_t>(b) == 65408);
  // REQUIRE(static_cast<uint32_t>(b) == 4294967168);
  // REQUIRE(static_cast<uint64_t>(b) == 0xffffffffffffff80ull);
  // REQUIRE(static_cast<unsigned __int128>(b) ==
  // 0xffffffffffffffffffffffffffffff80_u128);

  b = -128_sb;
  REQUIRE(b == -128_sb);
  b = b - 1_b;
  REQUIRE(b == 127_b);
  b = -128_sb;
  b = b + 1_b;
  REQUIRE(b == -127_sb);
  b = 127_b;
  REQUIRE(b == 127_b);
  b = b + 1_b;
  REQUIRE(b == -128_sb);
  b = 128_b;
  REQUIRE(b == -128_sb);
  b = 129_b;
  REQUIRE(b == -127_sb);

  _RuntimeBits<32, true> c(b);
  REQUIRE(c == -127_sb);

  _RuntimeBits<8, true> d(b);
  REQUIRE(d == -127_sb);
  REQUIRE(b == c);
  REQUIRE(b == d);
  REQUIRE(c == d);

  REQUIRE_THROWS_AS((_RuntimeBits<7, true>(b)), std::runtime_error);

  _RuntimeBits<GmpPrecision, false> f(0_b, 64_b);
  REQUIRE(f == 0_b);
  f = -1_sb;
  REQUIRE(f == 0xffffffffffffffff_b);

  _RuntimeBits<BitsInfinitePrecision, false> g(0_b, 64_b);
  REQUIRE(g == 0_b);
  g = -1_sb;
  REQUIRE(g == 0xffffffffffffffff_b);

  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b) << 1_b == 2_b);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b) << 8_b == 0_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b) << 1_b == 2_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b) << 8_b == 0_b);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b).widening_sll(1_b) == 2_b);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b).widening_sll(8_b) == 256_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll(1_b) == 2_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll(1_b).width() == 9);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll(8_b) == 256_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll(8_b).width() == 16);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b).widening_sll<1>() == 2_b);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b).widening_sll<8>() == 256_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll<1>() == 2_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll<1>().width() == 9);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll<8>() == 256_b);
  REQUIRE(_RuntimeBits<16, false>(1_b, 8_b).widening_sll<8>().width() == 16);

  // arithmetic
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b) + _RuntimeBits<8, false>(20_b, 8_b) == 21_b);
  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b) - _RuntimeBits<8, false>(20_b, 8_b) == 237_b);
  REQUIRE(_RuntimeBits<8, false>(10_b, 8_b) * _RuntimeBits<8, false>(20_b, 8_b) == 200_b);
  REQUIRE(_RuntimeBits<8, false>(20_b, 8_b) * _RuntimeBits<8, false>(20_b, 8_b) == 144_b);
  REQUIRE(_RuntimeBits<8, false>(20_b, 8_b).widening_mul(_RuntimeBits<8, false>(20_b, 8_b)) ==
          400_b);

  REQUIRE(_RuntimeBits<8, false>(1_b, 8_b) * _RuntimeBits<8, true>(-3_sb, 8_b) == 253_b);
  REQUIRE(_RuntimeBits<8, true>(-3_sb, 8_b) * _RuntimeBits<8, false>(1_b, 8_b) == 253_b);
  REQUIRE(_RuntimeBits<8, true>(1_b, 8_b) * _RuntimeBits<8, true>(-3_sb, 8_b) == -3_sb);

  REQUIRE(_RuntimeBits<GmpPrecision, false>(1_b, 8_b) * _RuntimeBits<8, true>(-3_sb, 8_b) == 253_b);
  REQUIRE(_RuntimeBits<GmpPrecision, true>(-3_sb, 8_b) * _RuntimeBits<8, false>(1_b, 8_b) == 253_b);
  static_assert(std::same_as<decltype(_RuntimeBits<GmpPrecision, true>(1_b, 8_b) *
                                      _RuntimeBits<8, true>(-3_sb, 8_b)),
                             _RuntimeBits<GmpPrecision, true>>);
  REQUIRE(_RuntimeBits<GmpPrecision, true>(1_b, 8_b) * _RuntimeBits<8, true>(-3_sb, 8_b) == -3_sb);

  REQUIRE(_RuntimeBits<GmpPrecision, false>(1_b, 8_b) * _RuntimeBits<128, true>(-3_sb, 8_b) ==
          253_b);
  REQUIRE(_RuntimeBits<GmpPrecision, true>(-3_sb, 8_b) * _RuntimeBits<128, false>(1_b, 8_b) ==
          253_b);
  REQUIRE(_RuntimeBits<GmpPrecision, true>(1_b, 8_b) * _RuntimeBits<128, true>(-3_sb, 8_b) ==
          -3_sb);

  REQUIRE_THROWS_AS((_RuntimeBits<BitsInfinitePrecision, false>(1_b, InfinitePrecisionBits) *
                     _RuntimeBits<BitsInfinitePrecision, true>(-3_sb, 8_b)),
                    std::runtime_error);
  REQUIRE_THROWS_AS((_RuntimeBits<BitsInfinitePrecision, true>(-3_sb, InfinitePrecisionBits) *
                     _RuntimeBits<BitsInfinitePrecision, false>(1_b, InfinitePrecisionBits)),
                    std::runtime_error);
  REQUIRE(_RuntimeBits<BitsInfinitePrecision, true>(1_b, InfinitePrecisionBits) *
              _RuntimeBits<BitsInfinitePrecision, true>(-3_sb, InfinitePrecisionBits) ==
          -3_sb);
  REQUIRE(_RuntimeBits<BitsInfinitePrecision, false>(1_b, InfinitePrecisionBits) *
              _RuntimeBits<BitsInfinitePrecision, false>(3_sb, InfinitePrecisionBits) ==
          3_b);
}

TEST_CASE("PossiblyUnknownBits", "[bits]") {
  _PossiblyUnknownBits<8, false> a(0_b);
  a = 255_b;
  REQUIRE(a == 255_b);
  a = a + 1_b;
  REQUIRE(a == 0_b);

  _PossiblyUnknownBits<16, false> b("0x1xx0"_xb);
  REQUIRE_THROWS_AS(b == 1_b, UndefinedValueError);
  REQUIRE(((b & 0xf_b) == 0_b));
  REQUIRE(((b & 0x1000_b) == 0x1000_b));
  REQUIRE_THROWS_AS((b & 0x1f00_b) == 0x1000_b, UndefinedValueError);
  REQUIRE((b & 0x1f00_b).unknown_mask() == 0x0f00_b);

  _PossiblyUnknownBits<16, false> c("0x10x0"_xb);
  REQUIRE((b & c).unknown_mask() == 0xf0_b);
  REQUIRE_THROWS_AS((b & c) == "0x10x0"_xb, UndefinedValueError);

  REQUIRE(((b | 0x0ff0_b) == 0x1ff0_b));
  REQUIRE(((b | 0x1fff_b) == 0x1fff_b));
  REQUIRE_THROWS_AS((b | 0x1f00_b) == 0x1000_b, UndefinedValueError);
  REQUIRE((b | 0x1f00_b).unknown_mask() == 0xf0_b);

  _PossiblyUnknownBits<8, true> d("0x80"_xb);
  REQUIRE(((d & 0x3200_b) == 0x3200_b));  // sign extension should happen on d

  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) | _PossiblyUnknownBits<2, false>(3_b)) == 3_b));
  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) | _PossiblyUnknownBits<2, true>(3_b)) == 0xf_b));
  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) + _PossiblyUnknownBits<2, false>(3_b)) == 4_b));
  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) + _PossiblyUnknownBits<2, true>(3_b)) == 0_b));
  REQUIRE(((_PossiblyUnknownBits<4, true>(1_b) | _PossiblyUnknownBits<2, false>(3_b)) == 3_b));

  REQUIRE(((_PossiblyUnknownBits<4, true>(1_b) | _PossiblyUnknownBits<2, false>(3_b)) == 3_b));

  REQUIRE(((_PossiblyUnknownBits<4, false>(0x8_b) & _PossiblyUnknownBits<2, false>(3_b)) == 0_b));
  REQUIRE(((_PossiblyUnknownBits<4, false>(0x8_b) & _PossiblyUnknownBits<2, true>(3_b)) == 0x8_b));
  REQUIRE((_PossiblyUnknownBits<4, false>(1_b) - _PossiblyUnknownBits<2, false>(3_b)).get() == 0xe);
  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) - _PossiblyUnknownBits<2, false>(3_b)) == 0xe_b));
  REQUIRE(((_PossiblyUnknownBits<4, false>(1_b) - _PossiblyUnknownBits<2, true>(3_b)) == 2_b));

  bool result = ("0b0x110"_xb & "0bx00x0"_xb).unknown_mask() == 2_b;
  REQUIRE(result);
}

#define TEMPLATE(N)                                             \
  TEST_CASE("Random inputs with Bits<" #N ">", "[bits]") {      \
    auto i = GENERATE(take(100, random(0ul, (1ul << 63) - 1))); \
    auto j = GENERATE(take(100, random(0ul, (1ul << 63) - 1))); \
                                                                \
    Bits<N> bi{i};                                              \
    Bits<N> bj{j};                                              \
                                                                \
    uint64_t native_sum = i + j;                                \
    Bits<N> bits_sum = bi + bj;                                 \
                                                                \
    REQUIRE(bits_sum == Bits<N>{native_sum});                   \
    REQUIRE(bits_sum.get() == native_sum);                      \
  }

TEMPLATE(64)
TEMPLATE(65)
TEMPLATE(128)
TEMPLATE(129)
TEMPLATE(InfinitePrecision)

#undef TEMPLATE

#define TEMPLATE(N, M)                                                    \
  TEST_CASE("Random inputs with RuntimeBits<" #N ">(" #M ")", "[bits]") { \
    auto i = GENERATE(take(100, random(0ul, (1ul << 63) - 1)));           \
    auto j = GENERATE(take(100, random(0ul, (1ul << 63) - 1)));           \
                                                                          \
    _RuntimeBits<N, false> bi{Bits<N>{i}, M};                             \
    _RuntimeBits<N, false> bj{Bits<N>{j}, M};                             \
                                                                          \
    mpz_class native_sum = (mpz_class{i} + mpz_class{j});                 \
    if (M != InfinitePrecision) {                                         \
      native_sum &= ((1_mpz << M) - 1);                                   \
    }                                                                     \
    _RuntimeBits<N, false> bits_sum{M};                                   \
    bits_sum = bi + bj;                                                   \
                                                                          \
    REQUIRE(bits_sum == Bits<M>{i + j});                                  \
    REQUIRE(to_gmp(bits_sum.get()) == native_sum);                        \
  }

TEMPLATE(64, 8)
TEMPLATE(64, 9)
TEMPLATE(64, 16)
TEMPLATE(64, 32)
TEMPLATE(64, 64)
TEMPLATE(65, 65)
TEMPLATE(128, 128)
TEMPLATE(129, 129)
TEMPLATE(InfinitePrecision, 32)
TEMPLATE(InfinitePrecision, InfinitePrecision)

#undef TEMPLATE

#define TEMPLATE(N)                                                                              \
  TEST_CASE("Random inputs with signed Bits<" #N ">", "[bits]") {                                \
    auto i = GENERATE(take(                                                                      \
        100, random(std::numeric_limits<int64_t>::min(), std::numeric_limits<int64_t>::max()))); \
    auto j = GENERATE(take(                                                                      \
        100, random(std::numeric_limits<int64_t>::min(), std::numeric_limits<int64_t>::max()))); \
                                                                                                 \
    _Bits<N, true> bi{i};                                                                        \
    _Bits<N, true> bj{j};                                                                        \
                                                                                                 \
    mpz_class native_sum = static_cast<mpz_class>(i) + static_cast<mpz_class>(j);                \
    _Bits<N, true> bits_sum = bi + bj;                                                           \
                                                                                                 \
    REQUIRE(bits_sum == _Bits<N, true>{native_sum});                                             \
    if ((N > 64) || ((native_sum >> 63)) == 0) {                                                 \
      bool result = to_gmp(bits_sum.get()) == native_sum;                                        \
      REQUIRE(result);                                                                           \
    }                                                                                            \
  }

TEMPLATE(64)
TEMPLATE(65)
TEMPLATE(128)
TEMPLATE(129)
TEMPLATE(InfinitePrecision)

#undef TEMPLATE

#define TEMPLATE(N)                                                       \
  TEST_CASE("Random inputs with PossiblyUnknownBits<" #N ">", "[bits]") { \
    auto i = GENERATE(take(100, random(0ul, (1ul << 63) - 1)));           \
    auto j = GENERATE(take(100, random(0ul, (1ul << 63) - 1)));           \
                                                                          \
    _PossiblyUnknownBits<N, false> bi{Bits<N>{i}};                        \
    _PossiblyUnknownBits<N, false> bj{Bits<N>{j}};                        \
                                                                          \
    mpz_class native_sum = i + j;                                         \
    if (N != InfinitePrecision) {                                         \
      native_sum &= (1_mpz << N) - 1;                                     \
    }                                                                     \
    _PossiblyUnknownBits<N, false> bits_sum{bi + bj};                     \
                                                                          \
    REQUIRE(bits_sum == Bits<N>{native_sum});                             \
    REQUIRE(to_gmp(bits_sum.get()) == native_sum);                        \
  }

TEMPLATE(64)
TEMPLATE(65)
TEMPLATE(128)
TEMPLATE(129)
TEMPLATE(InfinitePrecision)

#undef TEMPLATE
