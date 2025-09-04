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
TEST_CASE("bits_1")
{
  // 1'1 + 1'1 = 1'0
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_2")
{
  // 1'1 + 1'0 = 1'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{0u};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{0u}, Bits<32>{1}};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x0_b};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x0_b, Bits<32>{1}};
    auto result = lhs + rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_3")
{
  // 1'1 `+ 1'1 = 2'2
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_4")
{
  // 1'0 `+ 1'1 = 2'1
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs == result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs == result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_5")
{
  // 1'0 - 1'1 = 1'1
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result == rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
}
TEST_CASE("bits_6")
{
  // 1'0 - 1'0 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{0u};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs == result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{0u}, Bits<32>{1}};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x0_b};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs == result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x0_b, Bits<32>{1}};
    auto result = lhs - rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs == result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_7")
{
  // 1'0 `- 1'1 = 2'3
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{3u};
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
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_8")
{
  // 1'1 `- 1'0 = 2'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{0u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{0u}, Bits<32>{1}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x0_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x0_b, Bits<32>{1}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_9")
{
  // 1'1 * 1'1 = 1'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result == rhs);
  }
}
TEST_CASE("bits_10")
{
  // 1'1 * 1'1 = 1'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs == result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs * rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result == rhs);
  }
}
TEST_CASE("bits_11")
{
  // 1'1 `* 1'1 = 2'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result == rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs == result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_12")
{
  // 1'1 `* 1'1 = 2'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<2, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result == rhs);
  }
}
TEST_CASE("bits_13")
{
  // 1'0 % 1'1 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs % rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs % rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs % rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs % rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_14")
{
  // 1'0 >> 1'1 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_15")
{
  // 1'0 >> 1'1 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs >> rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_16")
{
  // 1'0 >>> 1'0 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{0u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result == rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{0u}, Bits<32>{1}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x0_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x0_b, Bits<32>{1}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_17")
{
  // 1'0 >>> 1'1 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
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
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_18")
{
  // 1'1 << 1'0 = 1'1
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{0u};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{0u}, Bits<32>{1}};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x0_b};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x0_b, Bits<32>{1}};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_19")
{
  // 1'0 << 1'1 = 1'0
  {
    _Bits<1, false> lhs{0u};
    _Bits<1, false> rhs{1u};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{0u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x0_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x0_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs << rhs;
    auto expected = _Bits<1, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_20")
{
  // 1'1 `<< 1'1 = 2'2
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_21")
{
  // 1'1 `<< 1'1 = 2'2
  {
    _Bits<1, false> lhs{1u};
    _Bits<1, false> rhs{1u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<1, false> lhs{Bits<1>{1u}, Bits<32>{1}};
    _RuntimeBits<1, false> rhs{Bits<1>{1u}, Bits<32>{1}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<1, false> lhs{0x1_b};
    _PossiblyUnknownBits<1, false> rhs{0x1_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs == rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<1, false> lhs{0x1_b, Bits<32>{1}};
    _PossiblyUnknownRuntimeBits<1, false> rhs{0x1_b, Bits<32>{1}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<2, false>{2u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs == lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
