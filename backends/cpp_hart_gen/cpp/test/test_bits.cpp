
#include <fmt/core.h>

#include <catch2/catch_test_macros.hpp>
#include <udb/bits.hpp>
#include <udb/defines.hpp>

constexpr __uint128_t operator""_u128(const char* x) {
  __uint128_t y = 0;
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
      if ('0' <= x[i] && x[i] <= '8') y += x[i] - '0';
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
    for (int i = 0; x[i] != '\0'; ++i) {
      if (x[i] == '\'') {
        continue;
      }
      y *= 10ull;
      if ('0' <= x[i] && x[i] <= '8') y += x[i] - '0';
    }
  }
  return y;
}

using namespace udb;

constexpr unsigned InfinitePrecision = Bits<64>::InfinitePrecision;
constexpr unsigned GmpPrecision = Bits<64>::MaxNativePrecision + 1;

static_assert(Bits<32>{0xffffffffffffffffull}.get() == 0xffffffffu);
static_assert(Bits<32>{0xffffffffffffffffull}.get<int32_t>() == -1);
static_assert(Bits<32>{0xffffffffffffffffull}.get<int32_t>() < 0);
static_assert(Bits<31>{0x7fffffffu}.get<int32_t>() == -1);
static_assert(Bits<31>{0x7fffffffu}.get<int32_t>() < 0);

static_assert(Bits<31>{Bits<31>{0x7fff'ffffu}}.get() == 2147483647);
static_assert(Bits<31>{Bits<31>{-1}}.get() == 2147483647);
static_assert(Bits<31>{Bits<31>{1234}}.get() == 1234);
static_assert(Bits<32>{Bits<32>{-1}}.get() == 4294967295);
static_assert(Bits<32>{Bits<32>{1234}}.get() == 1234);

static_assert(Bits<31>{Bits<31>{0x7fff'ffffu}}.get<int32_t>() == -1);
static_assert(Bits<31>{Bits<31>{-1}}.get<int32_t>() == -1);
static_assert(Bits<31>{Bits<31>{1234}}.get<int32_t>() == 1234);
static_assert(Bits<32>{Bits<32>{-1}}.get<int32_t>() == -1);
static_assert(Bits<32>{Bits<32>{1234}}.get<int32_t>() == 1234);

TEST_CASE("InifitePrecision works with int", "[bits]") {
  Bits<InfinitePrecision> a{Bits<InfinitePrecision>{0x7fff'ffffu}};
  REQUIRE(a.get() == 2147483647);
}

// negation
static_assert((-(-Bits<64>(5))).get() == Bits<64>(5).get());
static_assert((-(-Bits<64>(5))).get() == 5);
static_assert((-Bits<64>(5)).get<int64_t>() == -5);
static_assert((-Bits<64>(5)).get() == 18446744073709551611ull);
static_assert((-Bits<64>(5)).get<int64_t>() < 0);

TEST_CASE("Negation", "[bits]") {
  REQUIRE((-(-Bits<65>(5))).get() == Bits<64>(5).get());
  REQUIRE((-(-Bits<65>(5))).get() == 5);
  REQUIRE((-Bits<65>(5)).get<__int128_t>() == -5);
  REQUIRE((-Bits<65>(5)).get<__int128_t>() < 0);

  REQUIRE((-(-Bits<129>(5))).get() == Bits<64>(5).get());
  REQUIRE((-(-Bits<129>(5))).get() == 5);
  REQUIRE((-Bits<129>(5)).get<int64_t>() == -5);
  REQUIRE((-Bits<129>(5)).get<int64_t>() < 0);
}

// inversion
static_assert((~(~Bits<64>(5))).get() == Bits<64>(5).get());
static_assert((~(~Bits<64>(5))).get() == 5);
static_assert((~Bits<64>(5)).get<int64_t>() == -6);
static_assert((~Bits<64>(5)).get() == 18446744073709551610ull);
static_assert((~Bits<64>(5)).get<int64_t>() < 0);

TEST_CASE("Inversion", "[bits]") {
  REQUIRE((~(~Bits<65>(5))).get() == Bits<64>(5).get());
  REQUIRE((~(~Bits<65>(5))).get() == 5);
  REQUIRE((~Bits<65>(5)).get<__int128_t>() == -6);
  REQUIRE((~Bits<65>(5)).get() == 0x1fffffffffffffff_u128);
  REQUIRE((~Bits<65>(5)).get<int64_t>() < 0);

  REQUIRE((~(~Bits<129>(5))).get() == Bits<129>(5).get());
  REQUIRE((~(~Bits<129>(5))).get() == 5);
  REQUIRE((~Bits<129>(5)).get<__int128_t>() == -6);
  REQUIRE((~Bits<129>(5)).get() == 0x1fffffffffffffffffffffffffffffffa_mpz);
  REQUIRE((~Bits<129>(5)).get<int64_t>() < 0);
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

TEST_CASE("129-bit Assignment", "[bits]") {
  Bits<129> a{5};
  Bits<129> b;
  b = a;
  REQUIRE(a.get() == b.get());
  REQUIRE(a.get() == 5);
}

TEST_CASE("64-bit unsigned negation", "[bits]") {
  Bits<64> a;
  a = 5;
  REQUIRE(a.get() == 5);
  a = -5;
  REQUIRE(a.get() == 18446744073709551611ull);
}

TEST_CASE("65-bit unsigned negation", "[bits]") {
  Bits<65> a;
  a = 5;
  REQUIRE(a.get() == 5);
  a = -5;
  REQUIRE(a.get() == 0x1fffffffffffffffb_u128);
}

TEST_CASE("129-bit unsigned negation", "[bits]") {
  Bits<129> a;
  a = 5;
  REQUIRE(a.get() == 5);
  a = -5;
  REQUIRE(a.get() == 0x1fffffffffffffffffffffffffffffffb_mpz);
}

TEST_CASE("mixed-bit assignment", "[bits]") {
  Bits<129> a;
  Bits<64> b = 5;
  a = b;
  REQUIRE(a.get() == 5);
}

TEST_CASE("mixed-bit assignment, reversed", "[bits]") {
  Bits<64> a;
  Bits<129> b = 5;
  a = b;
  REQUIRE(a.get() == 5);
}

TEST_CASE("mixed-bit assignment, negated", "[bits]") {
  Bits<64> a;
  Bits<129> b = -5;
  a = b;
  REQUIRE(a.get() == 0xfffffffffffffffbull);
}

TEST_CASE("mixed-bit assignment, negated, reversed", "[bits]") {
  Bits<64> a{Bits<129>{-5}};
  REQUIRE(a.get() == 0xfffffffffffffffbull);
}

TEST_CASE("mixed-bit assignment, negated, constructor", "[bits]") {
  Bits<129> a{Bits<65>{-5}};
  REQUIRE(a.get() == 0x1fffffffffffffffb_mpz);
}

TEST_CASE("mixed-bit assignment, bits comparison", "[bits]") {
  Bits<129> a;
  Bits<64> b = 5;
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("mixed-bit assignment, bits comparison, reversed", "[bits]") {
  Bits<64> a;
  Bits<129> b = 5;
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("mixed-bit multiplication", "[bits]") {
  Bits<64> a = 5;
  Bits<129> b = 5;
  REQUIRE(a * b == 25);
}

TEST_CASE("mixed-bit multiplication, reversed", "[bits]") {
  Bits<129> a = 5;
  Bits<64> b = 5;
  REQUIRE(a * b == 25);
}

TEST_CASE("129-bit multiplication, reversed", "[bits]") {
  Bits<129> a;
  Bits<129> b = 5;
  a = b;
  REQUIRE(a == b);
}

TEST_CASE("129-bit multiplication, literal", "[bits]") {
  Bits<129> a = 5;
  REQUIRE(a * 5 == 25);
}

TEST_CASE("129-bit multiplication, literal, reversed", "[bits]") {
  Bits<129> a = 5;
  REQUIRE(5 * a == 25);
}

TEST_CASE("8-bit multiplication, literal, reversed", "[bits]") {
  Bits<8> a = 5;
  REQUIRE(a * 255 == 0xfb);
}

TEST_CASE("8-bit SRA", "[bits]") {
  Bits<8> a = 0x80;
  REQUIRE(a.sra(3) == 0xf0);
}

TEST_CASE("9-bit SRA", "[bits]") {
  Bits<9> a = 0x100;
  REQUIRE(a.sra(3) == 0x1e0);
}

TEST_CASE("65-bit SRA", "[bits]") {
  Bits<65> a = 0x10000000000000000_mpz;
  REQUIRE(a.sra(3) == 0x1e000000000000000_u128);
}

TEST_CASE("Printing", "[bits]") {
  fmt::print("{}\n", Bits<129>{16});
  fmt::print("{:x}\n", Bits<129>{16});
  fmt::print("{:#x}\n", Bits<129>{16});
  fmt::print("{:#10x}\n", Bits<129>{16});
  fmt::print("{:#010x}\n", Bits<129>{16});
  // fmt::print("{+:#10x}\n", Bits<129>{16});
}

TEST_CASE("Runtime", "[bits]") {
  _RuntimeBits<64, false> a(0, 8);
  a = 255;
  REQUIRE(a == 255);
  a = a + 1;
  REQUIRE(a == 0);

  _RuntimeBits<64, true> b(128, 8);
  REQUIRE(b == 0);
  b = -128;
  REQUIRE(b == -128);
  b = b - 1;
  REQUIRE(b == 0);
  b = -128;
  b = b + 1;
  REQUIRE(b == -127);
  b = 127;
  REQUIRE(b == 127);
  b = b + 1;
  REQUIRE(b == 0);
  b = 128;
  REQUIRE(b == 0);
  b = 129;
  REQUIRE(b == 1);
}
