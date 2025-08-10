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
TEST_CASE("bits_22")
{
  // 8'173 + 8'43 = 8'216
  {
    _Bits<8, false> lhs{173u};
    _Bits<8, false> rhs{43u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{173u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{43u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xad_b};
    _PossiblyUnknownBits<8, false> rhs{0x2b_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xad_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x2b_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_23")
{
  // 8'144 + 8'92 = 8'236
  {
    _Bits<8, false> lhs{144u};
    _Bits<8, false> rhs{92u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{144u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{92u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x90_b};
    _PossiblyUnknownBits<8, false> rhs{0x5c_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x90_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x5c_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_24")
{
  // 8'249 + 8'242 = 8'235
  {
    _Bits<8, false> lhs{249u};
    _Bits<8, false> rhs{242u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{235u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{249u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{242u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{235u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf9_b};
    _PossiblyUnknownBits<8, false> rhs{0xf2_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{235u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf9_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf2_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{235u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_25")
{
  // 8'190 + 8'35 = 8'225
  {
    _Bits<8, false> lhs{190u};
    _Bits<8, false> rhs{35u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{225u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{190u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{35u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{225u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xbe_b};
    _PossiblyUnknownBits<8, false> rhs{0x23_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{225u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xbe_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x23_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{225u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_26")
{
  // 8'234 + 8'52 = 8'30
  {
    _Bits<8, false> lhs{234u};
    _Bits<8, false> rhs{52u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{30u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{234u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{52u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{30u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xea_b};
    _PossiblyUnknownBits<8, false> rhs{0x34_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{30u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xea_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x34_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{30u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_27")
{
  // 8'22 + 8'102 = 8'124
  {
    _Bits<8, false> lhs{22u};
    _Bits<8, false> rhs{102u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{124u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{22u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{102u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{124u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x16_b};
    _PossiblyUnknownBits<8, false> rhs{0x66_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{124u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x16_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x66_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{124u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_28")
{
  // 8'88 + 8'145 = 8'233
  {
    _Bits<8, false> lhs{88u};
    _Bits<8, false> rhs{145u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{233u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{88u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{145u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{233u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x58_b};
    _PossiblyUnknownBits<8, false> rhs{0x91_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{233u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x58_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x91_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{233u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_29")
{
  // 8'22 + 8'19 = 8'41
  {
    _Bits<8, false> lhs{22u};
    _Bits<8, false> rhs{19u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{41u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{22u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{19u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{41u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x16_b};
    _PossiblyUnknownBits<8, false> rhs{0x13_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{41u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x16_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x13_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{41u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_30")
{
  // 8'251 + 8'99 = 8'94
  {
    _Bits<8, false> lhs{251u};
    _Bits<8, false> rhs{99u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{94u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{251u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{99u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{94u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xfb_b};
    _PossiblyUnknownBits<8, false> rhs{0x63_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{94u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xfb_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x63_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{94u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_31")
{
  // 8'24 + 8'69 = 8'93
  {
    _Bits<8, false> lhs{24u};
    _Bits<8, false> rhs{69u};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{93u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{24u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{69u}, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{93u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x18_b};
    _PossiblyUnknownBits<8, false> rhs{0x45_b};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{93u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x18_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x45_b, Bits<32>{8}};
    auto result = lhs + rhs;
    auto expected = _Bits<8, false>{93u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_32")
{
  // 8'139 `+ 8'252 = 9'391
  {
    _Bits<8, false> lhs{139u};
    _Bits<8, false> rhs{252u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{391u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{139u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{252u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{391u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8b_b};
    _PossiblyUnknownBits<8, false> rhs{0xfc_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{391u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xfc_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{391u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_33")
{
  // 8'194 `+ 8'238 = 9'432
  {
    _Bits<8, false> lhs{194u};
    _Bits<8, false> rhs{238u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{432u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{194u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{238u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{432u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xc2_b};
    _PossiblyUnknownBits<8, false> rhs{0xee_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{432u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xc2_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xee_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{432u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_34")
{
  // 8'86 `+ 8'129 = 9'215
  {
    _Bits<8, false> lhs{86u};
    _Bits<8, false> rhs{129u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{215u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{86u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{129u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{215u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x56_b};
    _PossiblyUnknownBits<8, false> rhs{0x81_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{215u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x56_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x81_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{215u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_35")
{
  // 8'179 `+ 8'76 = 9'255
  {
    _Bits<8, false> lhs{179u};
    _Bits<8, false> rhs{76u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{179u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{76u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xb3_b};
    _PossiblyUnknownBits<8, false> rhs{0x4c_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xb3_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4c_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_36")
{
  // 8'205 `+ 8'65 = 9'270
  {
    _Bits<8, false> lhs{205u};
    _Bits<8, false> rhs{65u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{270u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{205u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{65u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{270u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xcd_b};
    _PossiblyUnknownBits<8, false> rhs{0x41_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{270u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xcd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x41_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{270u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_37")
{
  // 8'109 `+ 8'250 = 9'359
  {
    _Bits<8, false> lhs{109u};
    _Bits<8, false> rhs{250u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{359u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{109u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{250u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{359u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x6d_b};
    _PossiblyUnknownBits<8, false> rhs{0xfa_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{359u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x6d_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xfa_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{359u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_38")
{
  // 8'242 `+ 8'44 = 9'286
  {
    _Bits<8, false> lhs{242u};
    _Bits<8, false> rhs{44u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{286u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{242u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{44u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{286u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf2_b};
    _PossiblyUnknownBits<8, false> rhs{0x2c_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{286u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf2_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x2c_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{286u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_39")
{
  // 8'0 `+ 8'90 = 9'90
  {
    _Bits<8, false> lhs{0u};
    _Bits<8, false> rhs{90u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{90u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{0u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{90u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{90u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x0_b};
    _PossiblyUnknownBits<8, false> rhs{0x5a_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{90u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x0_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x5a_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{90u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_40")
{
  // 8'107 `+ 8'218 = 9'325
  {
    _Bits<8, false> lhs{107u};
    _Bits<8, false> rhs{218u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{325u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{107u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{218u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{325u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x6b_b};
    _PossiblyUnknownBits<8, false> rhs{0xda_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{325u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x6b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xda_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{325u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_41")
{
  // 8'205 `+ 8'226 = 9'431
  {
    _Bits<8, false> lhs{205u};
    _Bits<8, false> rhs{226u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{431u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{205u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{226u}, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{431u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xcd_b};
    _PossiblyUnknownBits<8, false> rhs{0xe2_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{431u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xcd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xe2_b, Bits<32>{8}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<9, false>{431u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_42")
{
  // 8'18 - 8'189 = 8'85
  {
    _Bits<8, false> lhs{18u};
    _Bits<8, false> rhs{189u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{85u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{18u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{189u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{85u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x12_b};
    _PossiblyUnknownBits<8, false> rhs{0xbd_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{85u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x12_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xbd_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{85u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_43")
{
  // 8'249 - 8'86 = 8'163
  {
    _Bits<8, false> lhs{249u};
    _Bits<8, false> rhs{86u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{163u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{249u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{86u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{163u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf9_b};
    _PossiblyUnknownBits<8, false> rhs{0x56_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{163u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf9_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x56_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{163u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_44")
{
  // 8'206 - 8'146 = 8'60
  {
    _Bits<8, false> lhs{206u};
    _Bits<8, false> rhs{146u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{60u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{206u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{146u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{60u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xce_b};
    _PossiblyUnknownBits<8, false> rhs{0x92_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{60u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xce_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x92_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{60u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_45")
{
  // 8'221 - 8'204 = 8'17
  {
    _Bits<8, false> lhs{221u};
    _Bits<8, false> rhs{204u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{17u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{221u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{204u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{17u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xdd_b};
    _PossiblyUnknownBits<8, false> rhs{0xcc_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{17u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xdd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xcc_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{17u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_46")
{
  // 8'221 - 8'26 = 8'195
  {
    _Bits<8, false> lhs{221u};
    _Bits<8, false> rhs{26u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{221u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{26u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xdd_b};
    _PossiblyUnknownBits<8, false> rhs{0x1a_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xdd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1a_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_47")
{
  // 8'215 - 8'150 = 8'65
  {
    _Bits<8, false> lhs{215u};
    _Bits<8, false> rhs{150u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{65u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{215u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{150u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{65u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xd7_b};
    _PossiblyUnknownBits<8, false> rhs{0x96_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{65u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xd7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x96_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{65u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_48")
{
  // 8'221 - 8'247 = 8'230
  {
    _Bits<8, false> lhs{221u};
    _Bits<8, false> rhs{247u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{230u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{221u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{247u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{230u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xdd_b};
    _PossiblyUnknownBits<8, false> rhs{0xf7_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{230u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xdd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf7_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{230u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_49")
{
  // 8'65 - 8'148 = 8'173
  {
    _Bits<8, false> lhs{65u};
    _Bits<8, false> rhs{148u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{65u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{148u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x41_b};
    _PossiblyUnknownBits<8, false> rhs{0x94_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x41_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x94_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_50")
{
  // 8'156 - 8'170 = 8'242
  {
    _Bits<8, false> lhs{156u};
    _Bits<8, false> rhs{170u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{156u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{170u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9c_b};
    _PossiblyUnknownBits<8, false> rhs{0xaa_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9c_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xaa_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_51")
{
  // 8'171 - 8'17 = 8'154
  {
    _Bits<8, false> lhs{171u};
    _Bits<8, false> rhs{17u};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{154u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{171u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{17u}, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{154u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xab_b};
    _PossiblyUnknownBits<8, false> rhs{0x11_b};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{154u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xab_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x11_b, Bits<32>{8}};
    auto result = lhs - rhs;
    auto expected = _Bits<8, false>{154u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_52")
{
  // 8'126 `- 8'38 = 9'88
  {
    _Bits<8, false> lhs{126u};
    _Bits<8, false> rhs{38u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{126u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{38u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x7e_b};
    _PossiblyUnknownBits<8, false> rhs{0x26_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x7e_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x26_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_53")
{
  // 8'127 `- 8'238 = 9'401
  {
    _Bits<8, false> lhs{127u};
    _Bits<8, false> rhs{238u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{401u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{127u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{238u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{401u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x7f_b};
    _PossiblyUnknownBits<8, false> rhs{0xee_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{401u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x7f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xee_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{401u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_54")
{
  // 8'77 `- 8'89 = 9'500
  {
    _Bits<8, false> lhs{77u};
    _Bits<8, false> rhs{89u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{77u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{89u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x4d_b};
    _PossiblyUnknownBits<8, false> rhs{0x59_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x4d_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x59_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_55")
{
  // 8'117 `- 8'157 = 9'472
  {
    _Bits<8, false> lhs{117u};
    _Bits<8, false> rhs{157u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{472u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{117u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{157u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{472u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x75_b};
    _PossiblyUnknownBits<8, false> rhs{0x9d_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{472u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x75_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x9d_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{472u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_56")
{
  // 8'227 `- 8'175 = 9'52
  {
    _Bits<8, false> lhs{227u};
    _Bits<8, false> rhs{175u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{52u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{227u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{175u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{52u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xe3_b};
    _PossiblyUnknownBits<8, false> rhs{0xaf_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{52u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xe3_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xaf_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{52u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_57")
{
  // 8'199 `- 8'24 = 9'175
  {
    _Bits<8, false> lhs{199u};
    _Bits<8, false> rhs{24u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{199u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{24u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xc7_b};
    _PossiblyUnknownBits<8, false> rhs{0x18_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xc7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x18_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_58")
{
  // 8'248 `- 8'219 = 9'29
  {
    _Bits<8, false> lhs{248u};
    _Bits<8, false> rhs{219u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{29u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{248u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{219u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{29u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf8_b};
    _PossiblyUnknownBits<8, false> rhs{0xdb_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{29u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf8_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xdb_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{29u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_59")
{
  // 8'53 `- 8'70 = 9'495
  {
    _Bits<8, false> lhs{53u};
    _Bits<8, false> rhs{70u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{495u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{53u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{70u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{495u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x35_b};
    _PossiblyUnknownBits<8, false> rhs{0x46_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{495u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x35_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x46_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{495u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_60")
{
  // 8'90 `- 8'251 = 9'351
  {
    _Bits<8, false> lhs{90u};
    _Bits<8, false> rhs{251u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{351u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{90u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{251u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{351u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x5a_b};
    _PossiblyUnknownBits<8, false> rhs{0xfb_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{351u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x5a_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xfb_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{351u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_61")
{
  // 8'159 `- 8'98 = 9'61
  {
    _Bits<8, false> lhs{159u};
    _Bits<8, false> rhs{98u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{61u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{159u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{98u}, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{61u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9f_b};
    _PossiblyUnknownBits<8, false> rhs{0x62_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{61u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x62_b, Bits<32>{8}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<9, false>{61u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_62")
{
  // 8'198 * 8'192 = 8'128
  {
    _Bits<8, false> lhs{198u};
    _Bits<8, false> rhs{192u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{198u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{192u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xc6_b};
    _PossiblyUnknownBits<8, false> rhs{0xc0_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xc6_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xc0_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_63")
{
  // 8'233 * 8'180 = 8'212
  {
    _Bits<8, false> lhs{233u};
    _Bits<8, false> rhs{180u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{212u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{233u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{180u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{212u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xe9_b};
    _PossiblyUnknownBits<8, false> rhs{0xb4_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{212u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xe9_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb4_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{212u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_64")
{
  // 8'145 * 8'230 = 8'70
  {
    _Bits<8, false> lhs{145u};
    _Bits<8, false> rhs{230u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{70u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{145u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{230u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{70u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x91_b};
    _PossiblyUnknownBits<8, false> rhs{0xe6_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{70u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x91_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xe6_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{70u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_65")
{
  // 8'99 * 8'58 = 8'110
  {
    _Bits<8, false> lhs{99u};
    _Bits<8, false> rhs{58u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{110u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{99u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{58u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{110u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x63_b};
    _PossiblyUnknownBits<8, false> rhs{0x3a_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{110u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x63_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x3a_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{110u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_66")
{
  // 8'208 * 8'244 = 8'64
  {
    _Bits<8, false> lhs{208u};
    _Bits<8, false> rhs{244u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{64u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{208u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{244u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{64u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xd0_b};
    _PossiblyUnknownBits<8, false> rhs{0xf4_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{64u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xd0_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf4_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{64u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_67")
{
  // 8'31 * 8'80 = 8'176
  {
    _Bits<8, false> lhs{31u};
    _Bits<8, false> rhs{80u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{31u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{80u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x1f_b};
    _PossiblyUnknownBits<8, false> rhs{0x50_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x1f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x50_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_68")
{
  // 8'9 * 8'134 = 8'182
  {
    _Bits<8, false> lhs{9u};
    _Bits<8, false> rhs{134u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{182u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{9u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{134u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{182u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9_b};
    _PossiblyUnknownBits<8, false> rhs{0x86_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{182u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x86_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{182u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_69")
{
  // 8'43 * 8'63 = 8'149
  {
    _Bits<8, false> lhs{43u};
    _Bits<8, false> rhs{63u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{149u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{43u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{63u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{149u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x2b_b};
    _PossiblyUnknownBits<8, false> rhs{0x3f_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{149u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x2b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x3f_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{149u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_70")
{
  // 8'233 * 8'186 = 8'74
  {
    _Bits<8, false> lhs{233u};
    _Bits<8, false> rhs{186u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{74u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{233u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{186u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{74u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xe9_b};
    _PossiblyUnknownBits<8, false> rhs{0xba_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{74u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xe9_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xba_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{74u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_71")
{
  // 8'139 * 8'212 = 8'28
  {
    _Bits<8, false> lhs{139u};
    _Bits<8, false> rhs{212u};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{28u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{139u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{212u}, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{28u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8b_b};
    _PossiblyUnknownBits<8, false> rhs{0xd4_b};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{28u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xd4_b, Bits<32>{8}};
    auto result = lhs * rhs;
    auto expected = _Bits<8, false>{28u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_72")
{
  // 8'171 `* 8'88 = 16'15048
  {
    _Bits<8, false> lhs{171u};
    _Bits<8, false> rhs{88u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{15048u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{171u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{88u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{15048u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xab_b};
    _PossiblyUnknownBits<8, false> rhs{0x58_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{15048u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xab_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x58_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{15048u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_73")
{
  // 8'1 `* 8'238 = 16'238
  {
    _Bits<8, false> lhs{1u};
    _Bits<8, false> rhs{238u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{238u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result == rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{1u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{238u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{238u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x1_b};
    _PossiblyUnknownBits<8, false> rhs{0xee_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{238u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs == result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x1_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xee_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{238u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
}
TEST_CASE("bits_74")
{
  // 8'113 `* 8'115 = 16'12995
  {
    _Bits<8, false> lhs{113u};
    _Bits<8, false> rhs{115u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{12995u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{113u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{115u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{12995u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x71_b};
    _PossiblyUnknownBits<8, false> rhs{0x73_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{12995u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x71_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x73_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{12995u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_75")
{
  // 8'198 `* 8'39 = 16'7722
  {
    _Bits<8, false> lhs{198u};
    _Bits<8, false> rhs{39u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{198u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{39u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xc6_b};
    _PossiblyUnknownBits<8, false> rhs{0x27_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xc6_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x27_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_76")
{
  // 8'46 `* 8'147 = 16'6762
  {
    _Bits<8, false> lhs{46u};
    _Bits<8, false> rhs{147u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{6762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{46u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{147u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{6762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x2e_b};
    _PossiblyUnknownBits<8, false> rhs{0x93_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{6762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x2e_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x93_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{6762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_77")
{
  // 8'202 `* 8'84 = 16'16968
  {
    _Bits<8, false> lhs{202u};
    _Bits<8, false> rhs{84u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{16968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{202u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{84u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{16968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xca_b};
    _PossiblyUnknownBits<8, false> rhs{0x54_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{16968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xca_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x54_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{16968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_78")
{
  // 8'154 `* 8'48 = 16'7392
  {
    _Bits<8, false> lhs{154u};
    _Bits<8, false> rhs{48u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7392u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{154u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{48u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7392u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9a_b};
    _PossiblyUnknownBits<8, false> rhs{0x30_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7392u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9a_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x30_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{7392u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_79")
{
  // 8'177 `* 8'251 = 16'44427
  {
    _Bits<8, false> lhs{177u};
    _Bits<8, false> rhs{251u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{44427u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{177u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{251u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{44427u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xb1_b};
    _PossiblyUnknownBits<8, false> rhs{0xfb_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{44427u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xb1_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xfb_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{44427u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_80")
{
  // 8'5 `* 8'116 = 16'580
  {
    _Bits<8, false> lhs{5u};
    _Bits<8, false> rhs{116u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{580u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{5u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{116u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{580u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x5_b};
    _PossiblyUnknownBits<8, false> rhs{0x74_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{580u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x5_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x74_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{580u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_81")
{
  // 8'88 `* 8'1 = 16'88
  {
    _Bits<8, false> lhs{88u};
    _Bits<8, false> rhs{1u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{88u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{1u}, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x58_b};
    _PossiblyUnknownBits<8, false> rhs{0x1_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x58_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1_b, Bits<32>{8}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<16, false>{88u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_82")
{
  // 8'189 / 8'50 = 8'3
  {
    _Bits<8, false> lhs{189u};
    _Bits<8, false> rhs{50u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{189u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{50u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xbd_b};
    _PossiblyUnknownBits<8, false> rhs{0x32_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xbd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x32_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_83")
{
  // 8'111 / 8'150 = 8'0
  {
    _Bits<8, false> lhs{111u};
    _Bits<8, false> rhs{150u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{111u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{150u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x6f_b};
    _PossiblyUnknownBits<8, false> rhs{0x96_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x6f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x96_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_84")
{
  // 8'155 / 8'3 = 8'51
  {
    _Bits<8, false> lhs{155u};
    _Bits<8, false> rhs{3u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{51u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{155u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{3u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{51u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9b_b};
    _PossiblyUnknownBits<8, false> rhs{0x3_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{51u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x3_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{51u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_85")
{
  // 8'86 / 8'78 = 8'1
  {
    _Bits<8, false> lhs{86u};
    _Bits<8, false> rhs{78u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{86u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{78u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x56_b};
    _PossiblyUnknownBits<8, false> rhs{0x4e_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x56_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4e_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_86")
{
  // 8'22 / 8'106 = 8'0
  {
    _Bits<8, false> lhs{22u};
    _Bits<8, false> rhs{106u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{22u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{106u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x16_b};
    _PossiblyUnknownBits<8, false> rhs{0x6a_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x16_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x6a_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_87")
{
  // 8'157 / 8'151 = 8'1
  {
    _Bits<8, false> lhs{157u};
    _Bits<8, false> rhs{151u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{157u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{151u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x9d_b};
    _PossiblyUnknownBits<8, false> rhs{0x97_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x9d_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x97_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_88")
{
  // 8'68 / 8'31 = 8'2
  {
    _Bits<8, false> lhs{68u};
    _Bits<8, false> rhs{31u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{68u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{31u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x44_b};
    _PossiblyUnknownBits<8, false> rhs{0x1f_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x44_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1f_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_89")
{
  // 8'39 / 8'171 = 8'0
  {
    _Bits<8, false> lhs{39u};
    _Bits<8, false> rhs{171u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{39u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{171u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x27_b};
    _PossiblyUnknownBits<8, false> rhs{0xab_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x27_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xab_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_90")
{
  // 8'36 / 8'166 = 8'0
  {
    _Bits<8, false> lhs{36u};
    _Bits<8, false> rhs{166u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{36u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{166u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x24_b};
    _PossiblyUnknownBits<8, false> rhs{0xa6_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x24_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xa6_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_91")
{
  // 8'23 / 8'178 = 8'0
  {
    _Bits<8, false> lhs{23u};
    _Bits<8, false> rhs{178u};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{23u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{178u}, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x17_b};
    _PossiblyUnknownBits<8, false> rhs{0xb2_b};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x17_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb2_b, Bits<32>{8}};
    auto result = lhs / rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_92")
{
  // 8'73 % 8'135 = 8'73
  {
    _Bits<8, false> lhs{73u};
    _Bits<8, false> rhs{135u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{73u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{73u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{135u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{73u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x49_b};
    _PossiblyUnknownBits<8, false> rhs{0x87_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{73u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x49_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x87_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{73u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_93")
{
  // 8'176 % 8'223 = 8'176
  {
    _Bits<8, false> lhs{176u};
    _Bits<8, false> rhs{223u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{176u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{223u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xb0_b};
    _PossiblyUnknownBits<8, false> rhs{0xdf_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xb0_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xdf_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_94")
{
  // 8'84 % 8'15 = 8'9
  {
    _Bits<8, false> lhs{84u};
    _Bits<8, false> rhs{15u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{9u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{84u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{15u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{9u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x54_b};
    _PossiblyUnknownBits<8, false> rhs{0xf_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{9u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x54_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{9u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_95")
{
  // 8'238 % 8'202 = 8'36
  {
    _Bits<8, false> lhs{238u};
    _Bits<8, false> rhs{202u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{36u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{238u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{202u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{36u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xee_b};
    _PossiblyUnknownBits<8, false> rhs{0xca_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{36u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xee_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xca_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{36u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_96")
{
  // 8'168 % 8'240 = 8'168
  {
    _Bits<8, false> lhs{168u};
    _Bits<8, false> rhs{240u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{168u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{168u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{240u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{168u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xa8_b};
    _PossiblyUnknownBits<8, false> rhs{0xf0_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{168u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xa8_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf0_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{168u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_97")
{
  // 8'86 % 8'25 = 8'11
  {
    _Bits<8, false> lhs{86u};
    _Bits<8, false> rhs{25u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{11u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{86u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{25u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{11u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x56_b};
    _PossiblyUnknownBits<8, false> rhs{0x19_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{11u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x56_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x19_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{11u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_98")
{
  // 8'221 % 8'245 = 8'221
  {
    _Bits<8, false> lhs{221u};
    _Bits<8, false> rhs{245u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{221u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{221u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{245u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{221u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xdd_b};
    _PossiblyUnknownBits<8, false> rhs{0xf5_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{221u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xdd_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf5_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{221u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_99")
{
  // 8'175 % 8'231 = 8'175
  {
    _Bits<8, false> lhs{175u};
    _Bits<8, false> rhs{231u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{175u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{231u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xaf_b};
    _PossiblyUnknownBits<8, false> rhs{0xe7_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xaf_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xe7_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{175u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_100")
{
  // 8'127 % 8'167 = 8'127
  {
    _Bits<8, false> lhs{127u};
    _Bits<8, false> rhs{167u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{127u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{127u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{167u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{127u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x7f_b};
    _PossiblyUnknownBits<8, false> rhs{0xa7_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{127u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x7f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xa7_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{127u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_101")
{
  // 8'134 % 8'68 = 8'66
  {
    _Bits<8, false> lhs{134u};
    _Bits<8, false> rhs{68u};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{66u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{134u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{68u}, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{66u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x86_b};
    _PossiblyUnknownBits<8, false> rhs{0x44_b};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{66u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x86_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x44_b, Bits<32>{8}};
    auto result = lhs % rhs;
    auto expected = _Bits<8, false>{66u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_102")
{
  // 8'231 >> 8'5 = 8'7
  {
    _Bits<8, false> lhs{231u};
    _Bits<8, false> rhs{5u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{231u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{5u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xe7_b};
    _PossiblyUnknownBits<8, false> rhs{0x5_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xe7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x5_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_103")
{
  // 8'87 >> 8'11 = 8'0
  {
    _Bits<8, false> lhs{87u};
    _Bits<8, false> rhs{11u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{87u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{11u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x57_b};
    _PossiblyUnknownBits<8, false> rhs{0xb_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x57_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_104")
{
  // 8'47 >> 8'10 = 8'0
  {
    _Bits<8, false> lhs{47u};
    _Bits<8, false> rhs{10u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{47u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{10u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x2f_b};
    _PossiblyUnknownBits<8, false> rhs{0xa_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x2f_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xa_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_105")
{
  // 8'19 >> 8'2 = 8'4
  {
    _Bits<8, false> lhs{19u};
    _Bits<8, false> rhs{2u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{19u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{2u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x13_b};
    _PossiblyUnknownBits<8, false> rhs{0x2_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x13_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x2_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_106")
{
  // 8'236 >> 8'6 = 8'3
  {
    _Bits<8, false> lhs{236u};
    _Bits<8, false> rhs{6u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{236u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{6u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xec_b};
    _PossiblyUnknownBits<8, false> rhs{0x6_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xec_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x6_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_107")
{
  // 8'150 >> 8'1 = 8'75
  {
    _Bits<8, false> lhs{150u};
    _Bits<8, false> rhs{1u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{75u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{150u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{1u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{75u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x96_b};
    _PossiblyUnknownBits<8, false> rhs{0x1_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{75u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x96_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{75u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_108")
{
  // 8'8 >> 8'13 = 8'0
  {
    _Bits<8, false> lhs{8u};
    _Bits<8, false> rhs{13u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{8u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{13u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8_b};
    _PossiblyUnknownBits<8, false> rhs{0xd_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xd_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_109")
{
  // 8'131 >> 8'4 = 8'8
  {
    _Bits<8, false> lhs{131u};
    _Bits<8, false> rhs{4u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{8u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{131u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{4u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{8u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x83_b};
    _PossiblyUnknownBits<8, false> rhs{0x4_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{8u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x83_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{8u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_110")
{
  // 8'80 >> 8'11 = 8'0
  {
    _Bits<8, false> lhs{80u};
    _Bits<8, false> rhs{11u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{80u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{11u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x50_b};
    _PossiblyUnknownBits<8, false> rhs{0xb_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x50_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_111")
{
  // 8'67 >> 8'0 = 8'67
  {
    _Bits<8, false> lhs{67u};
    _Bits<8, false> rhs{0u};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{67u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{67u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{0u}, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{67u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x43_b};
    _PossiblyUnknownBits<8, false> rhs{0x0_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{67u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x43_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x0_b, Bits<32>{8}};
    auto result = lhs >> rhs;
    auto expected = _Bits<8, false>{67u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_112")
{
  // 8'142 >>> 8'1 = 8'199
  {
    _Bits<8, false> lhs{142u};
    _Bits<8, false> rhs{1u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{142u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{1u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8e_b};
    _PossiblyUnknownBits<8, false> rhs{0x1_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8e_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_113")
{
  // 8'139 >>> 8'9 = 8'255
  {
    _Bits<8, false> lhs{139u};
    _Bits<8, false> rhs{9u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{139u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{9u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8b_b};
    _PossiblyUnknownBits<8, false> rhs{0x9_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x9_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_114")
{
  // 8'72 >>> 8'12 = 8'0
  {
    _Bits<8, false> lhs{72u};
    _Bits<8, false> rhs{12u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{72u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{12u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x48_b};
    _PossiblyUnknownBits<8, false> rhs{0xc_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x48_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xc_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_115")
{
  // 8'247 >>> 8'4 = 8'255
  {
    _Bits<8, false> lhs{247u};
    _Bits<8, false> rhs{4u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{247u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{4u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf7_b};
    _PossiblyUnknownBits<8, false> rhs{0x4_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_116")
{
  // 8'214 >>> 8'8 = 8'255
  {
    _Bits<8, false> lhs{214u};
    _Bits<8, false> rhs{8u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{214u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{8u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xd6_b};
    _PossiblyUnknownBits<8, false> rhs{0x8_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xd6_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x8_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_117")
{
  // 8'58 >>> 8'2 = 8'14
  {
    _Bits<8, false> lhs{58u};
    _Bits<8, false> rhs{2u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{14u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{58u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{2u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{14u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x3a_b};
    _PossiblyUnknownBits<8, false> rhs{0x2_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{14u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x3a_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x2_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{14u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_118")
{
  // 8'52 >>> 8'1 = 8'26
  {
    _Bits<8, false> lhs{52u};
    _Bits<8, false> rhs{1u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{26u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{52u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{1u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{26u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x34_b};
    _PossiblyUnknownBits<8, false> rhs{0x1_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{26u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x34_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x1_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{26u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_119")
{
  // 8'104 >>> 8'4 = 8'6
  {
    _Bits<8, false> lhs{104u};
    _Bits<8, false> rhs{4u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{6u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{104u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{4u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{6u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x68_b};
    _PossiblyUnknownBits<8, false> rhs{0x4_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{6u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x68_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{6u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_120")
{
  // 8'218 >>> 8'13 = 8'255
  {
    _Bits<8, false> lhs{218u};
    _Bits<8, false> rhs{13u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{218u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{13u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xda_b};
    _PossiblyUnknownBits<8, false> rhs{0xd_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xda_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xd_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_121")
{
  // 8'179 >>> 8'11 = 8'255
  {
    _Bits<8, false> lhs{179u};
    _Bits<8, false> rhs{11u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{179u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{11u}, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xb3_b};
    _PossiblyUnknownBits<8, false> rhs{0xb_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xb3_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb_b, Bits<32>{8}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<8, false>{255u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_122")
{
  // 8'177 << 8'4 = 8'16
  {
    _Bits<8, false> lhs{177u};
    _Bits<8, false> rhs{4u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{16u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{177u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{4u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{16u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xb1_b};
    _PossiblyUnknownBits<8, false> rhs{0x4_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{16u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xb1_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{16u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_123")
{
  // 8'142 << 8'5 = 8'192
  {
    _Bits<8, false> lhs{142u};
    _Bits<8, false> rhs{5u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{142u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{5u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x8e_b};
    _PossiblyUnknownBits<8, false> rhs{0x5_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x8e_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x5_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_124")
{
  // 8'64 << 8'7 = 8'0
  {
    _Bits<8, false> lhs{64u};
    _Bits<8, false> rhs{7u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{64u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{7u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x40_b};
    _PossiblyUnknownBits<8, false> rhs{0x7_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x40_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x7_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_125")
{
  // 8'96 << 8'8 = 8'0
  {
    _Bits<8, false> lhs{96u};
    _Bits<8, false> rhs{8u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{96u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{8u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x60_b};
    _PossiblyUnknownBits<8, false> rhs{0x8_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x60_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x8_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_126")
{
  // 8'136 << 8'12 = 8'0
  {
    _Bits<8, false> lhs{136u};
    _Bits<8, false> rhs{12u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{136u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{12u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x88_b};
    _PossiblyUnknownBits<8, false> rhs{0xc_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x88_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xc_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_127")
{
  // 8'128 << 8'9 = 8'0
  {
    _Bits<8, false> lhs{128u};
    _Bits<8, false> rhs{9u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{128u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{9u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x80_b};
    _PossiblyUnknownBits<8, false> rhs{0x9_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x80_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x9_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_128")
{
  // 8'240 << 8'2 = 8'192
  {
    _Bits<8, false> lhs{240u};
    _Bits<8, false> rhs{2u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{240u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{2u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xf0_b};
    _PossiblyUnknownBits<8, false> rhs{0x2_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xf0_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x2_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{192u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_129")
{
  // 8'149 << 8'7 = 8'128
  {
    _Bits<8, false> lhs{149u};
    _Bits<8, false> rhs{7u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{149u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{7u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x95_b};
    _PossiblyUnknownBits<8, false> rhs{0x7_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x95_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x7_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{128u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_130")
{
  // 8'5 << 8'4 = 8'80
  {
    _Bits<8, false> lhs{5u};
    _Bits<8, false> rhs{4u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{80u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{5u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{4u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{80u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x5_b};
    _PossiblyUnknownBits<8, false> rhs{0x4_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{80u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x5_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x4_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{80u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_131")
{
  // 8'215 << 8'13 = 8'0
  {
    _Bits<8, false> lhs{215u};
    _Bits<8, false> rhs{13u};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{215u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{13u}, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xd7_b};
    _PossiblyUnknownBits<8, false> rhs{0xd_b};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xd7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xd_b, Bits<32>{8}};
    auto result = lhs << rhs;
    auto expected = _Bits<8, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_132")
{
  // 8'75 `<< 8'7 = 15'9600
  {
    _Bits<8, false> lhs{75u};
    _Bits<8, false> rhs{7u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{9600u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{75u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{7u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{9600u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x4b_b};
    _PossiblyUnknownBits<8, false> rhs{0x7_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{9600u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x4b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x7_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{9600u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_133")
{
  // 8'30 `<< 8'7 = 15'3840
  {
    _Bits<8, false> lhs{30u};
    _Bits<8, false> rhs{7u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{3840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{30u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{7u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{3840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x1e_b};
    _PossiblyUnknownBits<8, false> rhs{0x7_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{3840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x1e_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x7_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{3840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_134")
{
  // 8'34 `<< 8'6 = 14'2176
  {
    _Bits<8, false> lhs{34u};
    _Bits<8, false> rhs{6u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<14, false>{2176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{34u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{6u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<14, false>{2176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x22_b};
    _PossiblyUnknownBits<8, false> rhs{0x6_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<14, false>{2176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x22_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x6_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<14, false>{2176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_135")
{
  // 8'7 `<< 8'11 = 19'14336
  {
    _Bits<8, false> lhs{7u};
    _Bits<8, false> rhs{11u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<19, false>{14336u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{7u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{11u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<19, false>{14336u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x7_b};
    _PossiblyUnknownBits<8, false> rhs{0xb_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<19, false>{14336u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x7_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xb_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<19, false>{14336u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_136")
{
  // 8'48 `<< 8'10 = 18'49152
  {
    _Bits<8, false> lhs{48u};
    _Bits<8, false> rhs{10u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{49152u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{48u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{10u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{49152u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x30_b};
    _PossiblyUnknownBits<8, false> rhs{0xa_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{49152u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x30_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xa_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{49152u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_137")
{
  // 8'174 `<< 8'7 = 15'22272
  {
    _Bits<8, false> lhs{174u};
    _Bits<8, false> rhs{7u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{22272u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{174u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{7u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{22272u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xae_b};
    _PossiblyUnknownBits<8, false> rhs{0x7_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{22272u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xae_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x7_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<15, false>{22272u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_138")
{
  // 8'131 `<< 8'15 = 23'4292608
  {
    _Bits<8, false> lhs{131u};
    _Bits<8, false> rhs{15u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{4292608u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{131u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{15u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{4292608u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x83_b};
    _PossiblyUnknownBits<8, false> rhs{0xf_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{4292608u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x83_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xf_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{4292608u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_139")
{
  // 8'164 `<< 8'9 = 17'83968
  {
    _Bits<8, false> lhs{164u};
    _Bits<8, false> rhs{9u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{83968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{164u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{9u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{83968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0xa4_b};
    _PossiblyUnknownBits<8, false> rhs{0x9_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{83968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0xa4_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x9_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{83968u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_140")
{
  // 8'49 `<< 8'10 = 18'50176
  {
    _Bits<8, false> lhs{49u};
    _Bits<8, false> rhs{10u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{50176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{49u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{10u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{50176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x31_b};
    _PossiblyUnknownBits<8, false> rhs{0xa_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{50176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x31_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0xa_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<18, false>{50176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_141")
{
  // 8'59 `<< 8'9 = 17'30208
  {
    _Bits<8, false> lhs{59u};
    _Bits<8, false> rhs{9u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{30208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<8, false> lhs{Bits<8>{59u}, Bits<32>{8}};
    _RuntimeBits<8, false> rhs{Bits<8>{9u}, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{30208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<8, false> lhs{0x3b_b};
    _PossiblyUnknownBits<8, false> rhs{0x9_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{30208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<8, false> lhs{0x3b_b, Bits<32>{8}};
    _PossiblyUnknownRuntimeBits<8, false> rhs{0x9_b, Bits<32>{8}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{30208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
