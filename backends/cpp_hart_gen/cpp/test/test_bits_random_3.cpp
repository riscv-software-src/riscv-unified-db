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
TEST_CASE("bits_262")
{
  // 32'15505179 + 32'2060580523 = 32'2076085702
  {
    _Bits<32, false> lhs{15505179u};
    _Bits<32, false> rhs{2060580523u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2076085702u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{15505179u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2060580523u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2076085702u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xec971b_b};
    _PossiblyUnknownBits<32, false> rhs{0x7ad1f6ab_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2076085702u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xec971b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x7ad1f6ab_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2076085702u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_263")
{
  // 32'3237427776 + 32'2320471351 = 32'1262931831
  {
    _Bits<32, false> lhs{3237427776u};
    _Bits<32, false> rhs{2320471351u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1262931831u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3237427776u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2320471351u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1262931831u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xc0f73a40_b};
    _PossiblyUnknownBits<32, false> rhs{0x8a4f9537_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1262931831u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc0f73a40_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x8a4f9537_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1262931831u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_264")
{
  // 32'2708051004 + 32'1198992487 = 32'3907043491
  {
    _Bits<32, false> lhs{2708051004u};
    _Bits<32, false> rhs{1198992487u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3907043491u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2708051004u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1198992487u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3907043491u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa169943c_b};
    _PossiblyUnknownBits<32, false> rhs{0x47772c67_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3907043491u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa169943c_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x47772c67_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3907043491u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_265")
{
  // 32'1152439379 + 32'2325325327 = 32'3477764706
  {
    _Bits<32, false> lhs{1152439379u};
    _Bits<32, false> rhs{2325325327u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3477764706u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1152439379u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2325325327u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3477764706u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x44b0d453_b};
    _PossiblyUnknownBits<32, false> rhs{0x8a99a60f_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3477764706u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x44b0d453_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x8a99a60f_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3477764706u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_266")
{
  // 32'3786086356 + 32'166095605 = 32'3952181961
  {
    _Bits<32, false> lhs{3786086356u};
    _Bits<32, false> rhs{166095605u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3952181961u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3786086356u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{166095605u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3952181961u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe1ab17d4_b};
    _PossiblyUnknownBits<32, false> rhs{0x9e66af5_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3952181961u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe1ab17d4_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x9e66af5_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{3952181961u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_267")
{
  // 32'668925259 + 32'774241103 = 32'1443166362
  {
    _Bits<32, false> lhs{668925259u};
    _Bits<32, false> rhs{774241103u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1443166362u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{668925259u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{774241103u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1443166362u};
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
    _PossiblyUnknownBits<32, false> lhs{0x27defd4b_b};
    _PossiblyUnknownBits<32, false> rhs{0x2e25fb4f_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1443166362u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x27defd4b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2e25fb4f_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1443166362u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_268")
{
  // 32'3919310471 + 32'2071512427 = 32'1695855602
  {
    _Bits<32, false> lhs{3919310471u};
    _Bits<32, false> rhs{2071512427u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1695855602u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3919310471u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2071512427u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1695855602u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe99bee87_b};
    _PossiblyUnknownBits<32, false> rhs{0x7b78c56b_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1695855602u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe99bee87_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x7b78c56b_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{1695855602u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_269")
{
  // 32'2028660634 + 32'555291553 = 32'2583952187
  {
    _Bits<32, false> lhs{2028660634u};
    _Bits<32, false> rhs{555291553u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2583952187u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2028660634u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{555291553u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2583952187u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x78eae79a_b};
    _PossiblyUnknownBits<32, false> rhs{0x211913a1_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2583952187u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x78eae79a_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x211913a1_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{2583952187u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_270")
{
  // 32'2164588921 + 32'2716383617 = 32'586005242
  {
    _Bits<32, false> lhs{2164588921u};
    _Bits<32, false> rhs{2716383617u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{586005242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2164588921u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2716383617u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{586005242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x81050179_b};
    _PossiblyUnknownBits<32, false> rhs{0xa1e8b981_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{586005242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x81050179_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xa1e8b981_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{586005242u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_271")
{
  // 32'1677043988 + 32'3314596334 = 32'696673026
  {
    _Bits<32, false> lhs{1677043988u};
    _Bits<32, false> rhs{3314596334u};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{696673026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1677043988u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3314596334u}, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{696673026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x63f5a914_b};
    _PossiblyUnknownBits<32, false> rhs{0xc590b9ee_b};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{696673026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x63f5a914_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc590b9ee_b, Bits<32>{32}};
    auto result = lhs + rhs;
    auto expected = _Bits<32, false>{696673026u};
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
TEST_CASE("bits_272")
{
  // 32'1530421073 `+ 32'1242320895 = 33'2772741968
  {
    _Bits<32, false> lhs{1530421073u};
    _Bits<32, false> rhs{1242320895u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2772741968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1530421073u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1242320895u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2772741968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x5b385f51_b};
    _PossiblyUnknownBits<32, false> rhs{0x4a0c4fff_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2772741968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x5b385f51_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x4a0c4fff_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2772741968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_273")
{
  // 32'2632926592 `+ 32'3149811600 = 33'5782738192
  {
    _Bits<32, false> lhs{2632926592u};
    _Bits<32, false> rhs{3149811600u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{5782738192llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2632926592u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3149811600u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{5782738192llu};
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
    _PossiblyUnknownBits<32, false> lhs{0x9cef4580_b};
    _PossiblyUnknownBits<32, false> rhs{0xbbbe4f90_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{5782738192llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9cef4580_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xbbbe4f90_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{5782738192llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_274")
{
  // 32'388210825 `+ 32'266173578 = 33'654384403
  {
    _Bits<32, false> lhs{388210825u};
    _Bits<32, false> rhs{266173578u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{654384403llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{388210825u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{266173578u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{654384403llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x1723a089_b};
    _PossiblyUnknownBits<32, false> rhs{0xfdd7c8a_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{654384403llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x1723a089_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xfdd7c8a_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{654384403llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_275")
{
  // 32'2203727966 `+ 32'722322947 = 33'2926050913
  {
    _Bits<32, false> lhs{2203727966u};
    _Bits<32, false> rhs{722322947u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2926050913llu};
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
    _RuntimeBits<32, false> lhs{Bits<32>{2203727966u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{722322947u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2926050913llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x835a385e_b};
    _PossiblyUnknownBits<32, false> rhs{0x2b0dc603_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2926050913llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x835a385e_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2b0dc603_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2926050913llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_276")
{
  // 32'1071439548 `+ 32'1643581474 = 33'2715021022
  {
    _Bits<32, false> lhs{1071439548u};
    _Bits<32, false> rhs{1643581474u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2715021022llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1071439548u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1643581474u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2715021022llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x3fdcdebc_b};
    _PossiblyUnknownBits<32, false> rhs{0x61f71022_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2715021022llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x3fdcdebc_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x61f71022_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2715021022llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_277")
{
  // 32'3764554486 `+ 32'4185339171 = 33'7949893657
  {
    _Bits<32, false> lhs{3764554486u};
    _Bits<32, false> rhs{4185339171u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{7949893657llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3764554486u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{4185339171u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{7949893657llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe0628af6_b};
    _PossiblyUnknownBits<32, false> rhs{0xf9773523_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{7949893657llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe0628af6_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xf9773523_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{7949893657llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_278")
{
  // 32'183707538 `+ 32'3269110430 = 33'3452817968
  {
    _Bits<32, false> lhs{183707538u};
    _Bits<32, false> rhs{3269110430u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3452817968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{183707538u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3269110430u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3452817968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xaf32792_b};
    _PossiblyUnknownBits<32, false> rhs{0xc2daaa9e_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3452817968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xaf32792_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc2daaa9e_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3452817968llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_279")
{
  // 32'120149597 `+ 32'528987934 = 33'649137531
  {
    _Bits<32, false> lhs{120149597u};
    _Bits<32, false> rhs{528987934u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{649137531llu};
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
    _RuntimeBits<32, false> lhs{Bits<32>{120149597u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{528987934u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{649137531llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x729565d_b};
    _PossiblyUnknownBits<32, false> rhs{0x1f87b71e_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{649137531llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x729565d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1f87b71e_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{649137531llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_280")
{
  // 32'321656817 `+ 32'2142535278 = 33'2464192095
  {
    _Bits<32, false> lhs{321656817u};
    _Bits<32, false> rhs{2142535278u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2464192095llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{321656817u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2142535278u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2464192095llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x132c17f1_b};
    _PossiblyUnknownBits<32, false> rhs{0x7fb47e6e_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2464192095llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x132c17f1_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x7fb47e6e_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{2464192095llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_281")
{
  // 32'1067138776 `+ 32'2638417972 = 33'3705556748
  {
    _Bits<32, false> lhs{1067138776u};
    _Bits<32, false> rhs{2638417972u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3705556748llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1067138776u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2638417972u}, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3705556748llu};
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
    _PossiblyUnknownBits<32, false> lhs{0x3f9b3ed8_b};
    _PossiblyUnknownBits<32, false> rhs{0x9d431034_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3705556748llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x3f9b3ed8_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x9d431034_b, Bits<32>{32}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<33, false>{3705556748llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_282")
{
  // 32'3543976557 - 32'1928809017 = 32'1615167540
  {
    _Bits<32, false> lhs{3543976557u};
    _Bits<32, false> rhs{1928809017u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1615167540u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3543976557u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1928809017u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1615167540u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xd33cca6d_b};
    _PossiblyUnknownBits<32, false> rhs{0x72f74a39_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1615167540u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xd33cca6d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x72f74a39_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1615167540u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_283")
{
  // 32'1608822943 - 32'4164289558 = 32'1739500681
  {
    _Bits<32, false> lhs{1608822943u};
    _Bits<32, false> rhs{4164289558u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1739500681u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1608822943u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{4164289558u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1739500681u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x5fe4b09f_b};
    _PossiblyUnknownBits<32, false> rhs{0xf8360416_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1739500681u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x5fe4b09f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xf8360416_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1739500681u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_284")
{
  // 32'549307455 - 32'2450044380 = 32'2394230371
  {
    _Bits<32, false> lhs{549307455u};
    _Bits<32, false> rhs{2450044380u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2394230371u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{549307455u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2450044380u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2394230371u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x20bdc43f_b};
    _PossiblyUnknownBits<32, false> rhs{0x9208b5dc_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2394230371u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x20bdc43f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x9208b5dc_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2394230371u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_285")
{
  // 32'2390923536 - 32'710304300 = 32'1680619236
  {
    _Bits<32, false> lhs{2390923536u};
    _Bits<32, false> rhs{710304300u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1680619236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2390923536u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{710304300u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1680619236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x8e829910_b};
    _PossiblyUnknownBits<32, false> rhs{0x2a56622c_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1680619236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x8e829910_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2a56622c_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1680619236u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_286")
{
  // 32'3598345194 - 32'2610269435 = 32'988075759
  {
    _Bits<32, false> lhs{3598345194u};
    _Bits<32, false> rhs{2610269435u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{988075759u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3598345194u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2610269435u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{988075759u};
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
    _PossiblyUnknownBits<32, false> lhs{0xd67a63ea_b};
    _PossiblyUnknownBits<32, false> rhs{0x9b958cfb_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{988075759u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xd67a63ea_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x9b958cfb_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{988075759u};
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
TEST_CASE("bits_287")
{
  // 32'2919859465 - 32'11861498 = 32'2907997967
  {
    _Bits<32, false> lhs{2919859465u};
    _Bits<32, false> rhs{11861498u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2907997967u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2919859465u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{11861498u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2907997967u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xae098509_b};
    _PossiblyUnknownBits<32, false> rhs{0xb4fdfa_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2907997967u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xae098509_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xb4fdfa_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{2907997967u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_288")
{
  // 32'1909536744 - 32'1152849104 = 32'756687640
  {
    _Bits<32, false> lhs{1909536744u};
    _Bits<32, false> rhs{1152849104u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{756687640u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1909536744u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1152849104u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{756687640u};
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
    _PossiblyUnknownBits<32, false> lhs{0x71d137e8_b};
    _PossiblyUnknownBits<32, false> rhs{0x44b714d0_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{756687640u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x71d137e8_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x44b714d0_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{756687640u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_289")
{
  // 32'3626576993 - 32'2399374254 = 32'1227202739
  {
    _Bits<32, false> lhs{3626576993u};
    _Bits<32, false> rhs{2399374254u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1227202739u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3626576993u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2399374254u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1227202739u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xd8292c61_b};
    _PossiblyUnknownBits<32, false> rhs{0x8f038bae_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1227202739u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xd8292c61_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x8f038bae_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{1227202739u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_290")
{
  // 32'3971928229 - 32'3141727316 = 32'830200913
  {
    _Bits<32, false> lhs{3971928229u};
    _Bits<32, false> rhs{3141727316u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{830200913u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3971928229u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3141727316u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{830200913u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xecbed0a5_b};
    _PossiblyUnknownBits<32, false> rhs{0xbb42f454_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{830200913u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xecbed0a5_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xbb42f454_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{830200913u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_291")
{
  // 32'2614968480 - 32'3475834303 = 32'3434101473
  {
    _Bits<32, false> lhs{2614968480u};
    _Bits<32, false> rhs{3475834303u};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{3434101473u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2614968480u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3475834303u}, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{3434101473u};
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
    _PossiblyUnknownBits<32, false> lhs{0x9bdd40a0_b};
    _PossiblyUnknownBits<32, false> rhs{0xcf2d05bf_b};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{3434101473u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9bdd40a0_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xcf2d05bf_b, Bits<32>{32}};
    auto result = lhs - rhs;
    auto expected = _Bits<32, false>{3434101473u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_292")
{
  // 32'3305975884 `- 32'3272881378 = 33'33094506
  {
    _Bits<32, false> lhs{3305975884u};
    _Bits<32, false> rhs{3272881378u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{33094506llu};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3305975884u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3272881378u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{33094506llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xc50d304c_b};
    _PossiblyUnknownBits<32, false> rhs{0xc31434e2_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{33094506llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc50d304c_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc31434e2_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{33094506llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_293")
{
  // 32'2849756442 `- 32'1060389036 = 33'1789367406
  {
    _Bits<32, false> lhs{2849756442u};
    _Bits<32, false> rhs{1060389036u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1789367406llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2849756442u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1060389036u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1789367406llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa9dbd51a_b};
    _PossiblyUnknownBits<32, false> rhs{0x3f3440ac_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1789367406llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa9dbd51a_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3f3440ac_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1789367406llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_294")
{
  // 32'2050705470 `- 32'3263172718 = 33'7377467344
  {
    _Bits<32, false> lhs{2050705470u};
    _Bits<32, false> rhs{3263172718u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{7377467344llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2050705470u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3263172718u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{7377467344llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x7a3b483e_b};
    _PossiblyUnknownBits<32, false> rhs{0xc280106e_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{7377467344llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x7a3b483e_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc280106e_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{7377467344llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_295")
{
  // 32'1142560804 `- 32'1277327692 = 33'8455167704
  {
    _Bits<32, false> lhs{1142560804u};
    _Bits<32, false> rhs{1277327692u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8455167704llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1142560804u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1277327692u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8455167704llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x441a1824_b};
    _PossiblyUnknownBits<32, false> rhs{0x4c22794c_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8455167704llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x441a1824_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x4c22794c_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8455167704llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_296")
{
  // 32'1401625149 `- 32'731125167 = 33'670499982
  {
    _Bits<32, false> lhs{1401625149u};
    _Bits<32, false> rhs{731125167u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{670499982llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1401625149u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{731125167u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{670499982llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x538b1a3d_b};
    _PossiblyUnknownBits<32, false> rhs{0x2b9415af_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{670499982llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x538b1a3d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2b9415af_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{670499982llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_297")
{
  // 32'1876742525 `- 32'1716109740 = 33'160632785
  {
    _Bits<32, false> lhs{1876742525u};
    _Bits<32, false> rhs{1716109740u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{160632785llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1876742525u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1716109740u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{160632785llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x6fdcd17d_b};
    _PossiblyUnknownBits<32, false> rhs{0x6649c1ac_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{160632785llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x6fdcd17d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x6649c1ac_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{160632785llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_298")
{
  // 32'2167129851 `- 32'530867176 = 33'1636262675
  {
    _Bits<32, false> lhs{2167129851u};
    _Bits<32, false> rhs{530867176u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1636262675llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2167129851u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{530867176u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1636262675llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x812bc6fb_b};
    _PossiblyUnknownBits<32, false> rhs{0x1fa463e8_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1636262675llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x812bc6fb_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1fa463e8_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{1636262675llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_299")
{
  // 32'1690180378 `- 32'1715487929 = 33'8564627041
  {
    _Bits<32, false> lhs{1690180378u};
    _Bits<32, false> rhs{1715487929u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8564627041llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1690180378u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1715487929u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8564627041llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x64be1b1a_b};
    _PossiblyUnknownBits<32, false> rhs{0x664044b9_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8564627041llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x64be1b1a_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x664044b9_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8564627041llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_300")
{
  // 32'694869272 `- 32'3600139474 = 33'5684664390
  {
    _Bits<32, false> lhs{694869272u};
    _Bits<32, false> rhs{3600139474u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{5684664390llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{694869272u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3600139474u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{5684664390llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x296add18_b};
    _PossiblyUnknownBits<32, false> rhs{0xd695c4d2_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{5684664390llu};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x296add18_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xd695c4d2_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{5684664390llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_301")
{
  // 32'479265627 `- 32'789266075 = 33'8279934144
  {
    _Bits<32, false> lhs{479265627u};
    _Bits<32, false> rhs{789266075u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8279934144llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{479265627u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{789266075u}, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8279934144llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x1c91035b_b};
    _PossiblyUnknownBits<32, false> rhs{0x2f0b3e9b_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8279934144llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x1c91035b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2f0b3e9b_b, Bits<32>{32}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<33, false>{8279934144llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_302")
{
  // 32'1141174635 * 32'2214866455 = 32'4051626653
  {
    _Bits<32, false> lhs{1141174635u};
    _Bits<32, false> rhs{2214866455u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{4051626653u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1141174635u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2214866455u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{4051626653u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x4404f16b_b};
    _PossiblyUnknownBits<32, false> rhs{0x84042e17_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{4051626653u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x4404f16b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x84042e17_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{4051626653u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_303")
{
  // 32'3406659428 * 32'3959722014 = 32'2429365688
  {
    _Bits<32, false> lhs{3406659428u};
    _Bits<32, false> rhs{3959722014u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2429365688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3406659428u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3959722014u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2429365688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xcb0d7f64_b};
    _PossiblyUnknownBits<32, false> rhs{0xec04901e_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2429365688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xcb0d7f64_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xec04901e_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2429365688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_304")
{
  // 32'3664757876 * 32'1415933884 = 32'1913033008
  {
    _Bits<32, false> lhs{3664757876u};
    _Bits<32, false> rhs{1415933884u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1913033008u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3664757876u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1415933884u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1913033008u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xda6fc474_b};
    _PossiblyUnknownBits<32, false> rhs{0x54656fbc_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1913033008u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xda6fc474_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x54656fbc_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1913033008u};
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
TEST_CASE("bits_305")
{
  // 32'870017034 * 32'2845499405 = 32'3442542722
  {
    _Bits<32, false> lhs{870017034u};
    _Bits<32, false> rhs{2845499405u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3442542722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{870017034u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2845499405u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3442542722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x33db680a_b};
    _PossiblyUnknownBits<32, false> rhs{0xa99ae00d_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3442542722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x33db680a_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xa99ae00d_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3442542722u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_306")
{
  // 32'1105117824 * 32'37759251 = 32'816770944
  {
    _Bits<32, false> lhs{1105117824u};
    _Bits<32, false> rhs{37759251u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{816770944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1105117824u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{37759251u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{816770944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x41dec280_b};
    _PossiblyUnknownBits<32, false> rhs{0x2402913_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{816770944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x41dec280_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2402913_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{816770944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_307")
{
  // 32'2468466040 * 32'1780598894 = 32'3447982480
  {
    _Bits<32, false> lhs{2468466040u};
    _Bits<32, false> rhs{1780598894u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3447982480u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2468466040u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1780598894u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3447982480u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x9321cd78_b};
    _PossiblyUnknownBits<32, false> rhs{0x6a21c86e_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3447982480u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9321cd78_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x6a21c86e_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3447982480u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_308")
{
  // 32'3582256185 * 32'1445993116 = 32'2363022524
  {
    _Bits<32, false> lhs{3582256185u};
    _Bits<32, false> rhs{1445993116u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2363022524u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3582256185u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1445993116u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2363022524u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xd584e439_b};
    _PossiblyUnknownBits<32, false> rhs{0x56301a9c_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2363022524u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xd584e439_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x56301a9c_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{2363022524u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_309")
{
  // 32'824929206 * 32'1995747726 = 32'3641087220
  {
    _Bits<32, false> lhs{824929206u};
    _Bits<32, false> rhs{1995747726u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3641087220u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{824929206u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1995747726u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3641087220u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x312b6bb6_b};
    _PossiblyUnknownBits<32, false> rhs{0x76f4b18e_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3641087220u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x312b6bb6_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x76f4b18e_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3641087220u};
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
TEST_CASE("bits_310")
{
  // 32'2001972145 * 32'216170535 = 32'3789137911
  {
    _Bits<32, false> lhs{2001972145u};
    _Bits<32, false> rhs{216170535u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3789137911u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2001972145u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{216170535u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3789137911u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x7753abb1_b};
    _PossiblyUnknownBits<32, false> rhs{0xce28027_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3789137911u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x7753abb1_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xce28027_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{3789137911u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_311")
{
  // 32'3714408263 * 32'889738777 = 32'1512056815
  {
    _Bits<32, false> lhs{3714408263u};
    _Bits<32, false> rhs{889738777u};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1512056815u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3714408263u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{889738777u}, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1512056815u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xdd655f47_b};
    _PossiblyUnknownBits<32, false> rhs{0x35085619_b};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1512056815u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xdd655f47_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x35085619_b, Bits<32>{32}};
    auto result = lhs * rhs;
    auto expected = _Bits<32, false>{1512056815u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_312")
{
  // 32'2050104542 `* 32'2926211160 = 64'5999038789967088720
  {
    _Bits<32, false> lhs{2050104542u};
    _Bits<32, false> rhs{2926211160u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{5999038789967088720llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2050104542u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2926211160u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{5999038789967088720llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x7a321cde_b};
    _PossiblyUnknownBits<32, false> rhs{0xae6a7058_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{5999038789967088720llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x7a321cde_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xae6a7058_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{5999038789967088720llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_313")
{
  // 32'1664713874 `* 32'816917747 = 64'1359934307347721878
  {
    _Bits<32, false> lhs{1664713874u};
    _Bits<32, false> rhs{816917747u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1359934307347721878llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1664713874u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{816917747u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1359934307347721878llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x63398492_b};
    _PossiblyUnknownBits<32, false> rhs{0x30b12cf3_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1359934307347721878llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x63398492_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x30b12cf3_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1359934307347721878llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_314")
{
  // 32'3083641596 `* 32'941100375 = 64'2902016262361198500
  {
    _Bits<32, false> lhs{3083641596u};
    _Bits<32, false> rhs{941100375u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2902016262361198500llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3083641596u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{941100375u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2902016262361198500llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xb7cca2fc_b};
    _PossiblyUnknownBits<32, false> rhs{0x38180d57_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2902016262361198500llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xb7cca2fc_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x38180d57_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2902016262361198500llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_315")
{
  // 32'1133104141 `* 32'1112333331 = 64'1260389503528423671
  {
    _Bits<32, false> lhs{1133104141u};
    _Bits<32, false> rhs{1112333331u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1260389503528423671llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1133104141u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1112333331u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1260389503528423671llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x4389cc0d_b};
    _PossiblyUnknownBits<32, false> rhs{0x424cdc13_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1260389503528423671llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x4389cc0d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x424cdc13_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{1260389503528423671llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_316")
{
  // 32'1917458460 `* 32'1645200602 = 64'3154603812701992920
  {
    _Bits<32, false> lhs{1917458460u};
    _Bits<32, false> rhs{1645200602u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3154603812701992920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1917458460u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1645200602u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3154603812701992920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x724a181c_b};
    _PossiblyUnknownBits<32, false> rhs{0x620fc4da_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3154603812701992920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x724a181c_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x620fc4da_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3154603812701992920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_317")
{
  // 32'2621173667 `* 32'373728442 = 64'979607150779336814
  {
    _Bits<32, false> lhs{2621173667u};
    _Bits<32, false> rhs{373728442u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{979607150779336814llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2621173667u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{373728442u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{979607150779336814llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x9c3befa3_b};
    _PossiblyUnknownBits<32, false> rhs{0x1646a4ba_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{979607150779336814llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9c3befa3_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1646a4ba_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{979607150779336814llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_318")
{
  // 32'1530634355 `* 32'3033453139 = 64'4643107588835990345
  {
    _Bits<32, false> lhs{1530634355u};
    _Bits<32, false> rhs{3033453139u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{4643107588835990345llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1530634355u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3033453139u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{4643107588835990345llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x5b3ba073_b};
    _PossiblyUnknownBits<32, false> rhs{0xb4ced253_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{4643107588835990345llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x5b3ba073_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xb4ced253_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{4643107588835990345llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_319")
{
  // 32'1505017786 `* 32'1523867825 = 64'2293448180138135450
  {
    _Bits<32, false> lhs{1505017786u};
    _Bits<32, false> rhs{1523867825u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2293448180138135450llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1505017786u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1523867825u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2293448180138135450llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x59b4bfba_b};
    _PossiblyUnknownBits<32, false> rhs{0x5ad460b1_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2293448180138135450llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x59b4bfba_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x5ad460b1_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2293448180138135450llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_320")
{
  // 32'2394604471 `* 32'1421596989 = 64'3404162505819537819
  {
    _Bits<32, false> lhs{2394604471u};
    _Bits<32, false> rhs{1421596989u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3404162505819537819llu};
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
    _RuntimeBits<32, false> lhs{Bits<32>{2394604471u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1421596989u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3404162505819537819llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x8ebac3b7_b};
    _PossiblyUnknownBits<32, false> rhs{0x54bbd93d_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3404162505819537819llu};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x8ebac3b7_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x54bbd93d_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{3404162505819537819llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_321")
{
  // 32'868415739 `* 32'2563207556 = 64'2225929783954123884
  {
    _Bits<32, false> lhs{868415739u};
    _Bits<32, false> rhs{2563207556u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2225929783954123884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{868415739u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2563207556u}, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2225929783954123884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x33c2f8fb_b};
    _PossiblyUnknownBits<32, false> rhs{0x98c77184_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2225929783954123884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x33c2f8fb_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x98c77184_b, Bits<32>{32}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<64, false>{2225929783954123884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_322")
{
  // 32'3793175627 / 32'3625580422 = 32'1
  {
    _Bits<32, false> lhs{3793175627u};
    _Bits<32, false> rhs{3625580422u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3793175627u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3625580422u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe217444b_b};
    _PossiblyUnknownBits<32, false> rhs{0xd819f786_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe217444b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xd819f786_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_323")
{
  // 32'257731836 / 32'1358049250 = 32'0
  {
    _Bits<32, false> lhs{257731836u};
    _Bits<32, false> rhs{1358049250u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{257731836u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1358049250u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf5cacfc_b};
    _PossiblyUnknownBits<32, false> rhs{0x50f22fe2_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf5cacfc_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x50f22fe2_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_324")
{
  // 32'1938385201 / 32'1592232864 = 32'1
  {
    _Bits<32, false> lhs{1938385201u};
    _Bits<32, false> rhs{1592232864u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1938385201u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1592232864u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x73896931_b};
    _PossiblyUnknownBits<32, false> rhs{0x5ee78ba0_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x73896931_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x5ee78ba0_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_325")
{
  // 32'4051802147 / 32'829043697 = 32'4
  {
    _Bits<32, false> lhs{4051802147u};
    _Bits<32, false> rhs{829043697u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4051802147u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{829043697u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf1819823_b};
    _PossiblyUnknownBits<32, false> rhs{0x316a33f1_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf1819823_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x316a33f1_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_326")
{
  // 32'2635224314 / 32'3124069601 = 32'0
  {
    _Bits<32, false> lhs{2635224314u};
    _Bits<32, false> rhs{3124069601u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2635224314u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3124069601u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x9d1254fa_b};
    _PossiblyUnknownBits<32, false> rhs{0xba3584e1_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9d1254fa_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xba3584e1_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_327")
{
  // 32'169387905 / 32'2392152391 = 32'0
  {
    _Bits<32, false> lhs{169387905u};
    _Bits<32, false> rhs{2392152391u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{169387905u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2392152391u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa18a781_b};
    _PossiblyUnknownBits<32, false> rhs{0x8e955947_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa18a781_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x8e955947_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_328")
{
  // 32'1502610949 / 32'3626733684 = 32'0
  {
    _Bits<32, false> lhs{1502610949u};
    _Bits<32, false> rhs{3626733684u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1502610949u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3626733684u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
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
    _PossiblyUnknownBits<32, false> lhs{0x59900605_b};
    _PossiblyUnknownBits<32, false> rhs{0xd82b9074_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x59900605_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xd82b9074_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_329")
{
  // 32'3147652082 / 32'2120631692 = 32'1
  {
    _Bits<32, false> lhs{3147652082u};
    _Bits<32, false> rhs{2120631692u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{3147652082u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2120631692u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xbb9d5bf2_b};
    _PossiblyUnknownBits<32, false> rhs{0x7e66458c_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xbb9d5bf2_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x7e66458c_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_330")
{
  // 32'916704336 / 32'3388233424 = 32'0
  {
    _Bits<32, false> lhs{916704336u};
    _Bits<32, false> rhs{3388233424u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{916704336u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3388233424u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x36a3cc50_b};
    _PossiblyUnknownBits<32, false> rhs{0xc9f456d0_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x36a3cc50_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc9f456d0_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_331")
{
  // 32'4268691947 / 32'1321783452 = 32'3
  {
    _Bits<32, false> lhs{4268691947u};
    _Bits<32, false> rhs{1321783452u};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4268691947u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1321783452u}, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{3u};
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
    _PossiblyUnknownBits<32, false> lhs{0xfe6f11eb_b};
    _PossiblyUnknownBits<32, false> rhs{0x4ec8d09c_b};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xfe6f11eb_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x4ec8d09c_b, Bits<32>{32}};
    auto result = lhs / rhs;
    auto expected = _Bits<32, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_332")
{
  // 32'4092746861 % 32'3135712435 = 32'957034426
  {
    _Bits<32, false> lhs{4092746861u};
    _Bits<32, false> rhs{3135712435u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{957034426u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4092746861u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3135712435u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{957034426u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf3f25c6d_b};
    _PossiblyUnknownBits<32, false> rhs{0xbae72cb3_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{957034426u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf3f25c6d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xbae72cb3_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{957034426u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_333")
{
  // 32'724403340 % 32'1324191225 = 32'724403340
  {
    _Bits<32, false> lhs{724403340u};
    _Bits<32, false> rhs{1324191225u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{724403340u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{724403340u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1324191225u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{724403340u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x2b2d848c_b};
    _PossiblyUnknownBits<32, false> rhs{0x4eed8df9_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{724403340u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x2b2d848c_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x4eed8df9_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{724403340u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_334")
{
  // 32'1007123404 % 32'651652038 = 32'355471366
  {
    _Bits<32, false> lhs{1007123404u};
    _Bits<32, false> rhs{651652038u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{355471366u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1007123404u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{651652038u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{355471366u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x3c077bcc_b};
    _PossiblyUnknownBits<32, false> rhs{0x26d76bc6_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{355471366u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x3c077bcc_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x26d76bc6_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{355471366u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_335")
{
  // 32'2642785701 % 32'3378542451 = 32'2642785701
  {
    _Bits<32, false> lhs{2642785701u};
    _Bits<32, false> rhs{3378542451u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{2642785701u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2642785701u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3378542451u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{2642785701u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x9d85b5a5_b};
    _PossiblyUnknownBits<32, false> rhs{0xc9607773_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{2642785701u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9d85b5a5_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc9607773_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{2642785701u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_336")
{
  // 32'2851970496 % 32'974456832 = 32'903056832
  {
    _Bits<32, false> lhs{2851970496u};
    _Bits<32, false> rhs{974456832u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{903056832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2851970496u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{974456832u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{903056832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa9fd9dc0_b};
    _PossiblyUnknownBits<32, false> rhs{0x3a150800_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{903056832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa9fd9dc0_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3a150800_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{903056832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_337")
{
  // 32'2835203497 % 32'1014521171 = 32'806161155
  {
    _Bits<32, false> lhs{2835203497u};
    _Bits<32, false> rhs{1014521171u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{806161155u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2835203497u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1014521171u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{806161155u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa8fdc5a9_b};
    _PossiblyUnknownBits<32, false> rhs{0x3c785d53_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{806161155u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa8fdc5a9_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3c785d53_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{806161155u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_338")
{
  // 32'1506277497 % 32'2208800804 = 32'1506277497
  {
    _Bits<32, false> lhs{1506277497u};
    _Bits<32, false> rhs{2208800804u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1506277497u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1506277497u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{2208800804u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1506277497u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x59c7f879_b};
    _PossiblyUnknownBits<32, false> rhs{0x83a7a024_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1506277497u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x59c7f879_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x83a7a024_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1506277497u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_339")
{
  // 32'403133445 % 32'3228906311 = 32'403133445
  {
    _Bits<32, false> lhs{403133445u};
    _Bits<32, false> rhs{3228906311u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{403133445u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{403133445u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3228906311u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{403133445u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x18075405_b};
    _PossiblyUnknownBits<32, false> rhs{0xc0753347_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{403133445u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x18075405_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc0753347_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{403133445u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_340")
{
  // 32'1557755999 % 32'3760747218 = 32'1557755999
  {
    _Bits<32, false> lhs{1557755999u};
    _Bits<32, false> rhs{3760747218u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1557755999u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1557755999u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3760747218u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1557755999u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x5cd9785f_b};
    _PossiblyUnknownBits<32, false> rhs{0xe02872d2_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1557755999u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x5cd9785f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xe02872d2_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{1557755999u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_341")
{
  // 32'2400814282 % 32'1686265450 = 32'714548832
  {
    _Bits<32, false> lhs{2400814282u};
    _Bits<32, false> rhs{1686265450u};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{714548832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2400814282u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1686265450u}, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{714548832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x8f1984ca_b};
    _PossiblyUnknownBits<32, false> rhs{0x64825e6a_b};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{714548832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x8f1984ca_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x64825e6a_b, Bits<32>{32}};
    auto result = lhs % rhs;
    auto expected = _Bits<32, false>{714548832u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_342")
{
  // 32'3246142841 >> 32'23 = 32'386
  {
    _Bits<32, false> lhs{3246142841u};
    _Bits<32, false> rhs{23u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{386u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3246142841u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{23u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{386u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xc17c3579_b};
    _PossiblyUnknownBits<32, false> rhs{0x17_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{386u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc17c3579_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x17_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{386u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_343")
{
  // 32'1622802957 >> 32'16 = 32'24762
  {
    _Bits<32, false> lhs{1622802957u};
    _Bits<32, false> rhs{16u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{24762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1622802957u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{16u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{24762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x60ba020d_b};
    _PossiblyUnknownBits<32, false> rhs{0x10_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{24762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x60ba020d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x10_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{24762u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_344")
{
  // 32'629570702 >> 32'38 = 32'0
  {
    _Bits<32, false> lhs{629570702u};
    _Bits<32, false> rhs{38u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{629570702u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{38u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x25867c8e_b};
    _PossiblyUnknownBits<32, false> rhs{0x26_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x25867c8e_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x26_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_345")
{
  // 32'2722354100 >> 32'26 = 32'40
  {
    _Bits<32, false> lhs{2722354100u};
    _Bits<32, false> rhs{26u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{40u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2722354100u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{26u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{40u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa243d3b4_b};
    _PossiblyUnknownBits<32, false> rhs{0x1a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{40u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa243d3b4_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1a_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{40u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_346")
{
  // 32'4064453220 >> 32'31 = 32'1
  {
    _Bits<32, false> lhs{4064453220u};
    _Bits<32, false> rhs{31u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4064453220u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{31u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf242a264_b};
    _PossiblyUnknownBits<32, false> rhs{0x1f_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf242a264_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1f_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_347")
{
  // 32'3239698225 >> 32'47 = 32'0
  {
    _Bits<32, false> lhs{3239698225u};
    _Bits<32, false> rhs{47u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3239698225u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{47u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xc119df31_b};
    _PossiblyUnknownBits<32, false> rhs{0x2f_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc119df31_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2f_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_348")
{
  // 32'1370896347 >> 32'51 = 32'0
  {
    _Bits<32, false> lhs{1370896347u};
    _Bits<32, false> rhs{51u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
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
    _RuntimeBits<32, false> lhs{Bits<32>{1370896347u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{51u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x51b637db_b};
    _PossiblyUnknownBits<32, false> rhs{0x33_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x51b637db_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x33_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_349")
{
  // 32'3174196360 >> 32'11 = 32'1549900
  {
    _Bits<32, false> lhs{3174196360u};
    _Bits<32, false> rhs{11u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1549900u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3174196360u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{11u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1549900u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xbd326488_b};
    _PossiblyUnknownBits<32, false> rhs{0xb_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1549900u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xbd326488_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xb_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{1549900u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_350")
{
  // 32'797536812 >> 32'46 = 32'0
  {
    _Bits<32, false> lhs{797536812u};
    _Bits<32, false> rhs{46u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{797536812u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{46u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x2f89722c_b};
    _PossiblyUnknownBits<32, false> rhs{0x2e_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x2f89722c_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2e_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_351")
{
  // 32'1673097720 >> 32'12 = 32'408471
  {
    _Bits<32, false> lhs{1673097720u};
    _Bits<32, false> rhs{12u};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{408471u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1673097720u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{12u}, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{408471u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x63b971f8_b};
    _PossiblyUnknownBits<32, false> rhs{0xc_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{408471u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x63b971f8_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xc_b, Bits<32>{32}};
    auto result = lhs >> rhs;
    auto expected = _Bits<32, false>{408471u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_352")
{
  // 32'722967589 >>> 32'57 = 32'0
  {
    _Bits<32, false> lhs{722967589u};
    _Bits<32, false> rhs{57u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{722967589u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{57u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x2b179c25_b};
    _PossiblyUnknownBits<32, false> rhs{0x39_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x2b179c25_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x39_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_353")
{
  // 32'3098937476 >>> 32'27 = 32'4294967287
  {
    _Bits<32, false> lhs{3098937476u};
    _Bits<32, false> rhs{27u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3098937476u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{27u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xb8b60884_b};
    _PossiblyUnknownBits<32, false> rhs{0x1b_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xb8b60884_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1b_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_354")
{
  // 32'3325948111 >>> 32'54 = 32'4294967295
  {
    _Bits<32, false> lhs{3325948111u};
    _Bits<32, false> rhs{54u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3325948111u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{54u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xc63df0cf_b};
    _PossiblyUnknownBits<32, false> rhs{0x36_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc63df0cf_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x36_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_355")
{
  // 32'3891195042 >>> 32'22 = 32'4294967199
  {
    _Bits<32, false> lhs{3891195042u};
    _Bits<32, false> rhs{22u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3891195042u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{22u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe7eeeca2_b};
    _PossiblyUnknownBits<32, false> rhs{0x16_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967199u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe7eeeca2_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x16_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967199u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_356")
{
  // 32'4256702670 >>> 32'61 = 32'4294967295
  {
    _Bits<32, false> lhs{4256702670u};
    _Bits<32, false> rhs{61u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4256702670u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{61u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xfdb820ce_b};
    _PossiblyUnknownBits<32, false> rhs{0x3d_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xfdb820ce_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3d_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_357")
{
  // 32'2785633523 >>> 32'14 = 32'4294875173
  {
    _Bits<32, false> lhs{2785633523u};
    _Bits<32, false> rhs{14u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294875173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2785633523u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{14u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294875173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xa60964f3_b};
    _PossiblyUnknownBits<32, false> rhs{0xe_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294875173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xa60964f3_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xe_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294875173u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_358")
{
  // 32'3385418562 >>> 32'60 = 32'4294967295
  {
    _Bits<32, false> lhs{3385418562u};
    _Bits<32, false> rhs{60u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3385418562u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{60u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
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
    _PossiblyUnknownBits<32, false> lhs{0xc9c96342_b};
    _PossiblyUnknownBits<32, false> rhs{0x3c_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xc9c96342_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3c_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_359")
{
  // 32'680781567 >>> 32'35 = 32'0
  {
    _Bits<32, false> lhs{680781567u};
    _Bits<32, false> rhs{35u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{680781567u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{35u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x2893e6ff_b};
    _PossiblyUnknownBits<32, false> rhs{0x23_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x2893e6ff_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x23_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_360")
{
  // 32'4206039718 >>> 32'58 = 32'4294967295
  {
    _Bits<32, false> lhs{4206039718u};
    _Bits<32, false> rhs{58u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4206039718u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{58u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
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
    _PossiblyUnknownBits<32, false> lhs{0xfab312a6_b};
    _PossiblyUnknownBits<32, false> rhs{0x3a_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xfab312a6_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3a_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{4294967295u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_361")
{
  // 32'457030338 >>> 32'1 = 32'228515169
  {
    _Bits<32, false> lhs{457030338u};
    _Bits<32, false> rhs{1u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{228515169u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{457030338u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1u}, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{228515169u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x1b3dbac2_b};
    _PossiblyUnknownBits<32, false> rhs{0x1_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{228515169u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x1b3dbac2_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1_b, Bits<32>{32}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<32, false>{228515169u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_362")
{
  // 32'1755715678 << 32'45 = 32'0
  {
    _Bits<32, false> lhs{1755715678u};
    _Bits<32, false> rhs{45u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1755715678u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{45u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x68a6185e_b};
    _PossiblyUnknownBits<32, false> rhs{0x2d_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x68a6185e_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2d_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_363")
{
  // 32'4205852410 << 32'13 = 32'115294208
  {
    _Bits<32, false> lhs{4205852410u};
    _Bits<32, false> rhs{13u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{115294208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4205852410u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{13u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{115294208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xfab036fa_b};
    _PossiblyUnknownBits<32, false> rhs{0xd_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{115294208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xfab036fa_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xd_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{115294208u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_364")
{
  // 32'3408375481 << 32'57 = 32'0
  {
    _Bits<32, false> lhs{3408375481u};
    _Bits<32, false> rhs{57u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3408375481u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{57u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xcb27aeb9_b};
    _PossiblyUnknownBits<32, false> rhs{0x39_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xcb27aeb9_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x39_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_365")
{
  // 32'1118603074 << 32'3 = 32'358890000
  {
    _Bits<32, false> lhs{1118603074u};
    _Bits<32, false> rhs{3u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{358890000u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1118603074u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{358890000u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x42ac8742_b};
    _PossiblyUnknownBits<32, false> rhs{0x3_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{358890000u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x42ac8742_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{358890000u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_366")
{
  // 32'84032623 << 32'22 = 32'465567744
  {
    _Bits<32, false> lhs{84032623u};
    _Bits<32, false> rhs{22u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{465567744u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{84032623u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{22u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{465567744u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x5023c6f_b};
    _PossiblyUnknownBits<32, false> rhs{0x16_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{465567744u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x5023c6f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x16_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{465567744u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_367")
{
  // 32'2565577851 << 32'6 = 32'988225216
  {
    _Bits<32, false> lhs{2565577851u};
    _Bits<32, false> rhs{6u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{988225216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2565577851u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{6u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{988225216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x98eb9c7b_b};
    _PossiblyUnknownBits<32, false> rhs{0x6_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{988225216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x98eb9c7b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x6_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{988225216u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_368")
{
  // 32'932558944 << 32'56 = 32'0
  {
    _Bits<32, false> lhs{932558944u};
    _Bits<32, false> rhs{56u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{932558944u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{56u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x3795b860_b};
    _PossiblyUnknownBits<32, false> rhs{0x38_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x3795b860_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x38_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_369")
{
  // 32'4026776162 << 32'53 = 32'0
  {
    _Bits<32, false> lhs{4026776162u};
    _Bits<32, false> rhs{53u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4026776162u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{53u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf003ba62_b};
    _PossiblyUnknownBits<32, false> rhs{0x35_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf003ba62_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x35_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_370")
{
  // 32'191599167 << 32'35 = 32'0
  {
    _Bits<32, false> lhs{191599167u};
    _Bits<32, false> rhs{35u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{191599167u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{35u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xb6b923f_b};
    _PossiblyUnknownBits<32, false> rhs{0x23_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xb6b923f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x23_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_371")
{
  // 32'4080875970 << 32'11 = 32'3922595840
  {
    _Bits<32, false> lhs{4080875970u};
    _Bits<32, false> rhs{11u};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{3922595840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4080875970u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{11u}, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{3922595840u};
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
    _PossiblyUnknownBits<32, false> lhs{0xf33d39c2_b};
    _PossiblyUnknownBits<32, false> rhs{0xb_b};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{3922595840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf33d39c2_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xb_b, Bits<32>{32}};
    auto result = lhs << rhs;
    auto expected = _Bits<32, false>{3922595840u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_372")
{
  // 32'1977553905 `<< 32'22 = 54'8294462253957120
  {
    _Bits<32, false> lhs{1977553905u};
    _Bits<32, false> rhs{22u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<54, false>{8294462253957120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{1977553905u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{22u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<54, false>{8294462253957120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x75df13f1_b};
    _PossiblyUnknownBits<32, false> rhs{0x16_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<54, false>{8294462253957120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x75df13f1_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x16_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<54, false>{8294462253957120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_373")
{
  // 32'2617246889 `<< 32'13 = 45'21440486514688
  {
    _Bits<32, false> lhs{2617246889u};
    _Bits<32, false> rhs{13u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{21440486514688llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2617246889u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{13u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{21440486514688llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x9c0004a9_b};
    _PossiblyUnknownBits<32, false> rhs{0xd_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{21440486514688llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x9c0004a9_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xd_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{21440486514688llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_374")
{
  // 32'2426702107 `<< 32'32 = 64'10422606186699292672
  {
    _Bits<32, false> lhs{2426702107u};
    _Bits<32, false> rhs{32u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<64, false>{10422606186699292672llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2426702107u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{32u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<64, false>{10422606186699292672llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x90a4891b_b};
    _PossiblyUnknownBits<32, false> rhs{0x20_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<64, false>{10422606186699292672llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x90a4891b_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x20_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<64, false>{10422606186699292672llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_375")
{
  // 32'4137453446 `<< 32'45 = 77'145573701544284176515072
  {
    _Bits<32, false> lhs{4137453446u};
    _Bits<32, false> rhs{45u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<77, false>{145573701544284176515072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4137453446u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{45u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<77, false>{145573701544284176515072_u128};
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
    _PossiblyUnknownBits<32, false> lhs{0xf69c8786_b};
    _PossiblyUnknownBits<32, false> rhs{0x2d_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<77, false>{145573701544284176515072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf69c8786_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x2d_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<77, false>{145573701544284176515072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_376")
{
  // 32'4127000006 `<< 32'63 = 95'38064856451439891980744654848
  {
    _Bits<32, false> lhs{4127000006u};
    _Bits<32, false> rhs{63u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<95, false>{38064856451439891980744654848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4127000006u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{63u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<95, false>{38064856451439891980744654848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf5fd05c6_b};
    _PossiblyUnknownBits<32, false> rhs{0x3f_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<95, false>{38064856451439891980744654848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf5fd05c6_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3f_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<95, false>{38064856451439891980744654848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_377")
{
  // 32'2292921033 `<< 32'11 = 43'4695902275584
  {
    _Bits<32, false> lhs{2292921033u};
    _Bits<32, false> rhs{11u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<43, false>{4695902275584llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2292921033u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{11u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<43, false>{4695902275584llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0x88ab32c9_b};
    _PossiblyUnknownBits<32, false> rhs{0xb_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<43, false>{4695902275584llu};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0x88ab32c9_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0xb_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<43, false>{4695902275584llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_378")
{
  // 32'4131050087 `<< 32'59 = 91'2381388240955143050500243456
  {
    _Bits<32, false> lhs{4131050087u};
    _Bits<32, false> rhs{59u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<91, false>{2381388240955143050500243456_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{4131050087u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{59u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<91, false>{2381388240955143050500243456_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xf63ad267_b};
    _PossiblyUnknownBits<32, false> rhs{0x3b_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<91, false>{2381388240955143050500243456_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xf63ad267_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3b_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<91, false>{2381388240955143050500243456_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_379")
{
  // 32'3828493268 `<< 32'31 = 63'8221626689508081664
  {
    _Bits<32, false> lhs{3828493268u};
    _Bits<32, false> rhs{31u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<63, false>{8221626689508081664llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3828493268u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{31u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<63, false>{8221626689508081664llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xe4322bd4_b};
    _PossiblyUnknownBits<32, false> rhs{0x1f_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<63, false>{8221626689508081664llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xe4322bd4_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1f_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<63, false>{8221626689508081664llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_380")
{
  // 32'3203507597 `<< 32'1 = 33'6407015194
  {
    _Bits<32, false> lhs{3203507597u};
    _Bits<32, false> rhs{1u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<33, false>{6407015194llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{3203507597u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{1u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<33, false>{6407015194llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xbef1a58d_b};
    _PossiblyUnknownBits<32, false> rhs{0x1_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<33, false>{6407015194llu};
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
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xbef1a58d_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x1_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<33, false>{6407015194llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_381")
{
  // 32'2936664591 `<< 32'3 = 35'23493316728
  {
    _Bits<32, false> lhs{2936664591u};
    _Bits<32, false> rhs{3u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<35, false>{23493316728llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<32, false> lhs{Bits<32>{2936664591u}, Bits<32>{32}};
    _RuntimeBits<32, false> rhs{Bits<32>{3u}, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<35, false>{23493316728llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<32, false> lhs{0xaf09f20f_b};
    _PossiblyUnknownBits<32, false> rhs{0x3_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<35, false>{23493316728llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<32, false> lhs{0xaf09f20f_b, Bits<32>{32}};
    _PossiblyUnknownRuntimeBits<32, false> rhs{0x3_b, Bits<32>{32}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<35, false>{23493316728llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
