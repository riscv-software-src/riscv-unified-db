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
TEST_CASE("bits_142")
{
  // 16'3883 + 16'56965 = 16'60848
  {
    _Bits<16, false> lhs{3883u};
    _Bits<16, false> rhs{56965u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{60848u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{3883u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{56965u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{60848u};
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
    _PossiblyUnknownBits<16, false> lhs{0xf2b_b};
    _PossiblyUnknownBits<16, false> rhs{0xde85_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{60848u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf2b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xde85_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{60848u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_143")
{
  // 16'25229 + 16'6312 = 16'31541
  {
    _Bits<16, false> lhs{25229u};
    _Bits<16, false> rhs{6312u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31541u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{25229u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{6312u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31541u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x628d_b};
    _PossiblyUnknownBits<16, false> rhs{0x18a8_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31541u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x628d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x18a8_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31541u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_144")
{
  // 16'32369 + 16'64994 = 16'31827
  {
    _Bits<16, false> lhs{32369u};
    _Bits<16, false> rhs{64994u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31827u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{32369u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{64994u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31827u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7e71_b};
    _PossiblyUnknownBits<16, false> rhs{0xfde2_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31827u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7e71_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xfde2_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{31827u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_145")
{
  // 16'59290 + 16'36776 = 16'30530
  {
    _Bits<16, false> lhs{59290u};
    _Bits<16, false> rhs{36776u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{30530u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{59290u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{36776u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{30530u};
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
    _PossiblyUnknownBits<16, false> lhs{0xe79a_b};
    _PossiblyUnknownBits<16, false> rhs{0x8fa8_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{30530u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe79a_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x8fa8_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{30530u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_146")
{
  // 16'52228 + 16'37892 = 16'24584
  {
    _Bits<16, false> lhs{52228u};
    _Bits<16, false> rhs{37892u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{24584u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{52228u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{37892u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{24584u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xcc04_b};
    _PossiblyUnknownBits<16, false> rhs{0x9404_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{24584u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xcc04_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x9404_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{24584u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_147")
{
  // 16'32541 + 16'1809 = 16'34350
  {
    _Bits<16, false> lhs{32541u};
    _Bits<16, false> rhs{1809u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{34350u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{32541u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{1809u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{34350u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7f1d_b};
    _PossiblyUnknownBits<16, false> rhs{0x711_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{34350u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7f1d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x711_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{34350u};
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
TEST_CASE("bits_148")
{
  // 16'25864 + 16'24040 = 16'49904
  {
    _Bits<16, false> lhs{25864u};
    _Bits<16, false> rhs{24040u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{49904u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{25864u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{24040u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{49904u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x6508_b};
    _PossiblyUnknownBits<16, false> rhs{0x5de8_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{49904u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x6508_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x5de8_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{49904u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_149")
{
  // 16'62199 + 16'51187 = 16'47850
  {
    _Bits<16, false> lhs{62199u};
    _Bits<16, false> rhs{51187u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{47850u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{62199u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{51187u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{47850u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf2f7_b};
    _PossiblyUnknownBits<16, false> rhs{0xc7f3_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{47850u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf2f7_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xc7f3_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{47850u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_150")
{
  // 16'47312 + 16'59176 = 16'40952
  {
    _Bits<16, false> lhs{47312u};
    _Bits<16, false> rhs{59176u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{40952u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{47312u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{59176u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{40952u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb8d0_b};
    _PossiblyUnknownBits<16, false> rhs{0xe728_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{40952u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb8d0_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe728_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{40952u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_151")
{
  // 16'43487 + 16'57121 = 16'35072
  {
    _Bits<16, false> lhs{43487u};
    _Bits<16, false> rhs{57121u};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{35072u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{43487u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{57121u}, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{35072u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xa9df_b};
    _PossiblyUnknownBits<16, false> rhs{0xdf21_b};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{35072u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xa9df_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xdf21_b, Bits<32>{16}};
    auto result = lhs + rhs;
    auto expected = _Bits<16, false>{35072u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_152")
{
  // 16'3843 `+ 16'7646 = 17'11489
  {
    _Bits<16, false> lhs{3843u};
    _Bits<16, false> rhs{7646u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{11489u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{3843u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{7646u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{11489u};
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
    _PossiblyUnknownBits<16, false> lhs{0xf03_b};
    _PossiblyUnknownBits<16, false> rhs{0x1dde_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{11489u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf03_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1dde_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{11489u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_153")
{
  // 16'8587 `+ 16'65250 = 17'73837
  {
    _Bits<16, false> lhs{8587u};
    _Bits<16, false> rhs{65250u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{73837u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{8587u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{65250u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{73837u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x218b_b};
    _PossiblyUnknownBits<16, false> rhs{0xfee2_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{73837u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x218b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xfee2_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{73837u};
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
TEST_CASE("bits_154")
{
  // 16'6162 `+ 16'44304 = 17'50466
  {
    _Bits<16, false> lhs{6162u};
    _Bits<16, false> rhs{44304u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{50466u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{6162u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{44304u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{50466u};
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
    _PossiblyUnknownBits<16, false> lhs{0x1812_b};
    _PossiblyUnknownBits<16, false> rhs{0xad10_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{50466u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x1812_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xad10_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{50466u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_155")
{
  // 16'56105 `+ 16'8839 = 17'64944
  {
    _Bits<16, false> lhs{56105u};
    _Bits<16, false> rhs{8839u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{64944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{56105u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{8839u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{64944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xdb29_b};
    _PossiblyUnknownBits<16, false> rhs{0x2287_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{64944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xdb29_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2287_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{64944u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_156")
{
  // 16'53173 `+ 16'53199 = 17'106372
  {
    _Bits<16, false> lhs{53173u};
    _Bits<16, false> rhs{53199u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{106372u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{53173u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{53199u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{106372u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xcfb5_b};
    _PossiblyUnknownBits<16, false> rhs{0xcfcf_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{106372u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xcfb5_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xcfcf_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{106372u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_157")
{
  // 16'35965 `+ 16'1074 = 17'37039
  {
    _Bits<16, false> lhs{35965u};
    _Bits<16, false> rhs{1074u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{37039u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{35965u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{1074u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{37039u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8c7d_b};
    _PossiblyUnknownBits<16, false> rhs{0x432_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{37039u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8c7d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x432_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{37039u};
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
TEST_CASE("bits_158")
{
  // 16'36591 `+ 16'58809 = 17'95400
  {
    _Bits<16, false> lhs{36591u};
    _Bits<16, false> rhs{58809u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{95400u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{36591u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{58809u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{95400u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8eef_b};
    _PossiblyUnknownBits<16, false> rhs{0xe5b9_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{95400u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8eef_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe5b9_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{95400u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_159")
{
  // 16'44644 `+ 16'27369 = 17'72013
  {
    _Bits<16, false> lhs{44644u};
    _Bits<16, false> rhs{27369u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{72013u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{44644u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{27369u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{72013u};
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
    _PossiblyUnknownBits<16, false> lhs{0xae64_b};
    _PossiblyUnknownBits<16, false> rhs{0x6ae9_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{72013u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xae64_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x6ae9_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{72013u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_160")
{
  // 16'10551 `+ 16'10143 = 17'20694
  {
    _Bits<16, false> lhs{10551u};
    _Bits<16, false> rhs{10143u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{20694u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{10551u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{10143u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{20694u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x2937_b};
    _PossiblyUnknownBits<16, false> rhs{0x279f_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{20694u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x2937_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x279f_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{20694u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_161")
{
  // 16'41499 `+ 16'12451 = 17'53950
  {
    _Bits<16, false> lhs{41499u};
    _Bits<16, false> rhs{12451u};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{53950u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{41499u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{12451u}, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{53950u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xa21b_b};
    _PossiblyUnknownBits<16, false> rhs{0x30a3_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{53950u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xa21b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x30a3_b, Bits<32>{16}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<17, false>{53950u};
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
TEST_CASE("bits_162")
{
  // 16'28872 - 16'16677 = 16'12195
  {
    _Bits<16, false> lhs{28872u};
    _Bits<16, false> rhs{16677u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{12195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{28872u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{16677u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{12195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x70c8_b};
    _PossiblyUnknownBits<16, false> rhs{0x4125_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{12195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x70c8_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x4125_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{12195u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_163")
{
  // 16'30756 - 16'33010 = 16'63282
  {
    _Bits<16, false> lhs{30756u};
    _Bits<16, false> rhs{33010u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{63282u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{30756u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{33010u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{63282u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7824_b};
    _PossiblyUnknownBits<16, false> rhs{0x80f2_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{63282u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7824_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x80f2_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{63282u};
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
TEST_CASE("bits_164")
{
  // 16'57831 - 16'18805 = 16'39026
  {
    _Bits<16, false> lhs{57831u};
    _Bits<16, false> rhs{18805u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{39026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{57831u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{18805u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{39026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe1e7_b};
    _PossiblyUnknownBits<16, false> rhs{0x4975_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{39026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe1e7_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x4975_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{39026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_165")
{
  // 16'28766 - 16'34250 = 16'60052
  {
    _Bits<16, false> lhs{28766u};
    _Bits<16, false> rhs{34250u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{60052u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{28766u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{34250u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{60052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x705e_b};
    _PossiblyUnknownBits<16, false> rhs{0x85ca_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{60052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x705e_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x85ca_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{60052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_166")
{
  // 16'63714 - 16'24717 = 16'38997
  {
    _Bits<16, false> lhs{63714u};
    _Bits<16, false> rhs{24717u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{38997u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{63714u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{24717u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{38997u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf8e2_b};
    _PossiblyUnknownBits<16, false> rhs{0x608d_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{38997u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf8e2_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x608d_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{38997u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_167")
{
  // 16'16935 - 16'32725 = 16'49746
  {
    _Bits<16, false> lhs{16935u};
    _Bits<16, false> rhs{32725u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{49746u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{16935u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{32725u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{49746u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x4227_b};
    _PossiblyUnknownBits<16, false> rhs{0x7fd5_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{49746u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x4227_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x7fd5_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{49746u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_168")
{
  // 16'33142 - 16'46993 = 16'51685
  {
    _Bits<16, false> lhs{33142u};
    _Bits<16, false> rhs{46993u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{51685u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{33142u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{46993u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{51685u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8176_b};
    _PossiblyUnknownBits<16, false> rhs{0xb791_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{51685u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8176_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xb791_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{51685u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_169")
{
  // 16'41859 - 16'62711 = 16'44684
  {
    _Bits<16, false> lhs{41859u};
    _Bits<16, false> rhs{62711u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{44684u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{41859u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{62711u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{44684u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xa383_b};
    _PossiblyUnknownBits<16, false> rhs{0xf4f7_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{44684u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xa383_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xf4f7_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{44684u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_170")
{
  // 16'57656 - 16'24968 = 16'32688
  {
    _Bits<16, false> lhs{57656u};
    _Bits<16, false> rhs{24968u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{32688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{57656u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{24968u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{32688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe138_b};
    _PossiblyUnknownBits<16, false> rhs{0x6188_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{32688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe138_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x6188_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{32688u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_171")
{
  // 16'20315 - 16'59152 = 16'26699
  {
    _Bits<16, false> lhs{20315u};
    _Bits<16, false> rhs{59152u};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{26699u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{20315u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{59152u}, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{26699u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x4f5b_b};
    _PossiblyUnknownBits<16, false> rhs{0xe710_b};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{26699u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x4f5b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe710_b, Bits<32>{16}};
    auto result = lhs - rhs;
    auto expected = _Bits<16, false>{26699u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_172")
{
  // 16'3957 `- 16'40883 = 17'94146
  {
    _Bits<16, false> lhs{3957u};
    _Bits<16, false> rhs{40883u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{94146u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{3957u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{40883u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{94146u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf75_b};
    _PossiblyUnknownBits<16, false> rhs{0x9fb3_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{94146u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf75_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x9fb3_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{94146u};
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
TEST_CASE("bits_173")
{
  // 16'49361 `- 16'60348 = 17'120085
  {
    _Bits<16, false> lhs{49361u};
    _Bits<16, false> rhs{60348u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{120085u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{49361u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{60348u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{120085u};
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
    _PossiblyUnknownBits<16, false> lhs{0xc0d1_b};
    _PossiblyUnknownBits<16, false> rhs{0xebbc_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{120085u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc0d1_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xebbc_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{120085u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_174")
{
  // 16'62818 `- 16'6945 = 17'55873
  {
    _Bits<16, false> lhs{62818u};
    _Bits<16, false> rhs{6945u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{55873u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{62818u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{6945u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{55873u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf562_b};
    _PossiblyUnknownBits<16, false> rhs{0x1b21_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{55873u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf562_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1b21_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{55873u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_175")
{
  // 16'59004 `- 16'16978 = 17'42026
  {
    _Bits<16, false> lhs{59004u};
    _Bits<16, false> rhs{16978u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{42026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{59004u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{16978u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{42026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe67c_b};
    _PossiblyUnknownBits<16, false> rhs{0x4252_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{42026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe67c_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x4252_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{42026u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_176")
{
  // 16'37601 `- 16'18237 = 17'19364
  {
    _Bits<16, false> lhs{37601u};
    _Bits<16, false> rhs{18237u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19364u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{37601u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{18237u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19364u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x92e1_b};
    _PossiblyUnknownBits<16, false> rhs{0x473d_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19364u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x92e1_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x473d_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19364u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_177")
{
  // 16'64515 `- 16'15655 = 17'48860
  {
    _Bits<16, false> lhs{64515u};
    _Bits<16, false> rhs{15655u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{48860u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{64515u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{15655u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{48860u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xfc03_b};
    _PossiblyUnknownBits<16, false> rhs{0x3d27_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{48860u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xfc03_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3d27_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{48860u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_178")
{
  // 16'33574 `- 16'22811 = 17'10763
  {
    _Bits<16, false> lhs{33574u};
    _Bits<16, false> rhs{22811u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{10763u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{33574u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{22811u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{10763u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8326_b};
    _PossiblyUnknownBits<16, false> rhs{0x591b_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{10763u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8326_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x591b_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{10763u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_179")
{
  // 16'42365 `- 16'60387 = 17'113050
  {
    _Bits<16, false> lhs{42365u};
    _Bits<16, false> rhs{60387u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{113050u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{42365u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{60387u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{113050u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xa57d_b};
    _PossiblyUnknownBits<16, false> rhs{0xebe3_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{113050u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xa57d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xebe3_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{113050u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_180")
{
  // 16'26938 `- 16'7787 = 17'19151
  {
    _Bits<16, false> lhs{26938u};
    _Bits<16, false> rhs{7787u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19151u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{26938u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{7787u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19151u};
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
    _PossiblyUnknownBits<16, false> lhs{0x693a_b};
    _PossiblyUnknownBits<16, false> rhs{0x1e6b_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19151u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x693a_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1e6b_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{19151u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_181")
{
  // 16'39622 `- 16'3836 = 17'35786
  {
    _Bits<16, false> lhs{39622u};
    _Bits<16, false> rhs{3836u};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{35786u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{39622u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{3836u}, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{35786u};
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
    _PossiblyUnknownBits<16, false> lhs{0x9ac6_b};
    _PossiblyUnknownBits<16, false> rhs{0xefc_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{35786u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x9ac6_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xefc_b, Bits<32>{16}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<17, false>{35786u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_182")
{
  // 16'54838 * 16'7710 = 16'28244
  {
    _Bits<16, false> lhs{54838u};
    _Bits<16, false> rhs{7710u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{28244u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{54838u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{7710u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{28244u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xd636_b};
    _PossiblyUnknownBits<16, false> rhs{0x1e1e_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{28244u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd636_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1e1e_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{28244u};
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
TEST_CASE("bits_183")
{
  // 16'60356 * 16'44132 = 16'51344
  {
    _Bits<16, false> lhs{60356u};
    _Bits<16, false> rhs{44132u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{51344u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{60356u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{44132u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{51344u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xebc4_b};
    _PossiblyUnknownBits<16, false> rhs{0xac64_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{51344u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xebc4_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xac64_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{51344u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_184")
{
  // 16'63607 * 16'14726 = 16'36170
  {
    _Bits<16, false> lhs{63607u};
    _Bits<16, false> rhs{14726u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{36170u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{63607u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{14726u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{36170u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf877_b};
    _PossiblyUnknownBits<16, false> rhs{0x3986_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{36170u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf877_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3986_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{36170u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_185")
{
  // 16'45460 * 16'34266 = 16'7176
  {
    _Bits<16, false> lhs{45460u};
    _Bits<16, false> rhs{34266u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{7176u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{45460u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{34266u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{7176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb194_b};
    _PossiblyUnknownBits<16, false> rhs{0x85da_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{7176u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb194_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x85da_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{7176u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_186")
{
  // 16'28969 * 16'63662 = 16'41438
  {
    _Bits<16, false> lhs{28969u};
    _Bits<16, false> rhs{63662u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{41438u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{28969u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{63662u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{41438u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7129_b};
    _PossiblyUnknownBits<16, false> rhs{0xf8ae_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{41438u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7129_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xf8ae_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{41438u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_187")
{
  // 16'62390 * 16'23728 = 16'62752
  {
    _Bits<16, false> lhs{62390u};
    _Bits<16, false> rhs{23728u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{62752u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{62390u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{23728u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{62752u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xf3b6_b};
    _PossiblyUnknownBits<16, false> rhs{0x5cb0_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{62752u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xf3b6_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x5cb0_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{62752u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_188")
{
  // 16'34662 * 16'48242 = 16'13164
  {
    _Bits<16, false> lhs{34662u};
    _Bits<16, false> rhs{48242u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{13164u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{34662u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{48242u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{13164u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8766_b};
    _PossiblyUnknownBits<16, false> rhs{0xbc72_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{13164u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8766_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xbc72_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{13164u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_189")
{
  // 16'3534 * 16'44859 = 16'122
  {
    _Bits<16, false> lhs{3534u};
    _Bits<16, false> rhs{44859u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{122u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{3534u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{44859u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{122u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xdce_b};
    _PossiblyUnknownBits<16, false> rhs{0xaf3b_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{122u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xdce_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xaf3b_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{122u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_190")
{
  // 16'54526 * 16'38507 = 16'55850
  {
    _Bits<16, false> lhs{54526u};
    _Bits<16, false> rhs{38507u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{55850u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{54526u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{38507u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{55850u};
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
    _PossiblyUnknownBits<16, false> lhs{0xd4fe_b};
    _PossiblyUnknownBits<16, false> rhs{0x966b_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{55850u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd4fe_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x966b_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{55850u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_191")
{
  // 16'3668 * 16'38463 = 16'48812
  {
    _Bits<16, false> lhs{3668u};
    _Bits<16, false> rhs{38463u};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{48812u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{3668u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{38463u}, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{48812u};
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
    _PossiblyUnknownBits<16, false> lhs{0xe54_b};
    _PossiblyUnknownBits<16, false> rhs{0x963f_b};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{48812u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe54_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x963f_b, Bits<32>{16}};
    auto result = lhs * rhs;
    auto expected = _Bits<16, false>{48812u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_192")
{
  // 16'22773 `* 16'46269 = 32'1053683937
  {
    _Bits<16, false> lhs{22773u};
    _Bits<16, false> rhs{46269u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1053683937u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{22773u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{46269u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1053683937u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x58f5_b};
    _PossiblyUnknownBits<16, false> rhs{0xb4bd_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1053683937u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x58f5_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xb4bd_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1053683937u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_193")
{
  // 16'28165 `* 16'57777 = 32'1627289205
  {
    _Bits<16, false> lhs{28165u};
    _Bits<16, false> rhs{57777u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1627289205u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{28165u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{57777u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1627289205u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x6e05_b};
    _PossiblyUnknownBits<16, false> rhs{0xe1b1_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1627289205u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x6e05_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe1b1_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1627289205u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_194")
{
  // 16'38271 `* 16'14097 = 32'539506287
  {
    _Bits<16, false> lhs{38271u};
    _Bits<16, false> rhs{14097u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{539506287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{38271u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{14097u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{539506287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x957f_b};
    _PossiblyUnknownBits<16, false> rhs{0x3711_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{539506287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x957f_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3711_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{539506287u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_195")
{
  // 16'53231 `* 16'50195 = 32'2671930045
  {
    _Bits<16, false> lhs{53231u};
    _Bits<16, false> rhs{50195u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{2671930045u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{53231u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{50195u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{2671930045u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xcfef_b};
    _PossiblyUnknownBits<16, false> rhs{0xc413_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{2671930045u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xcfef_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xc413_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{2671930045u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_196")
{
  // 16'13756 `* 16'10967 = 32'150862052
  {
    _Bits<16, false> lhs{13756u};
    _Bits<16, false> rhs{10967u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{150862052u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{13756u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{10967u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{150862052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x35bc_b};
    _PossiblyUnknownBits<16, false> rhs{0x2ad7_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{150862052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x35bc_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2ad7_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{150862052u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_197")
{
  // 16'48476 `* 16'24398 = 32'1182717448
  {
    _Bits<16, false> lhs{48476u};
    _Bits<16, false> rhs{24398u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1182717448u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{48476u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{24398u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1182717448u};
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
    _PossiblyUnknownBits<16, false> lhs{0xbd5c_b};
    _PossiblyUnknownBits<16, false> rhs{0x5f4e_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1182717448u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xbd5c_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x5f4e_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1182717448u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_198")
{
  // 16'30941 `* 16'9997 = 32'309317177
  {
    _Bits<16, false> lhs{30941u};
    _Bits<16, false> rhs{9997u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{309317177u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{30941u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{9997u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{309317177u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x78dd_b};
    _PossiblyUnknownBits<16, false> rhs{0x270d_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{309317177u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x78dd_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x270d_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{309317177u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_199")
{
  // 16'25065 `* 16'31684 = 32'794159460
  {
    _Bits<16, false> lhs{25065u};
    _Bits<16, false> rhs{31684u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{794159460u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{25065u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{31684u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{794159460u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x61e9_b};
    _PossiblyUnknownBits<16, false> rhs{0x7bc4_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{794159460u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x61e9_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x7bc4_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{794159460u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_200")
{
  // 16'55093 `* 16'29288 = 32'1613563784
  {
    _Bits<16, false> lhs{55093u};
    _Bits<16, false> rhs{29288u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1613563784u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{55093u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{29288u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1613563784u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xd735_b};
    _PossiblyUnknownBits<16, false> rhs{0x7268_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1613563784u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd735_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x7268_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{1613563784u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_201")
{
  // 16'18176 `* 16'36654 = 32'666223104
  {
    _Bits<16, false> lhs{18176u};
    _Bits<16, false> rhs{36654u};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{666223104u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{18176u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{36654u}, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{666223104u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x4700_b};
    _PossiblyUnknownBits<16, false> rhs{0x8f2e_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{666223104u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x4700_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x8f2e_b, Bits<32>{16}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<32, false>{666223104u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_202")
{
  // 16'58115 / 16'60509 = 16'0
  {
    _Bits<16, false> lhs{58115u};
    _Bits<16, false> rhs{60509u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{58115u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{60509u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe303_b};
    _PossiblyUnknownBits<16, false> rhs{0xec5d_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe303_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xec5d_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_203")
{
  // 16'58205 / 16'15329 = 16'3
  {
    _Bits<16, false> lhs{58205u};
    _Bits<16, false> rhs{15329u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{58205u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{15329u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe35d_b};
    _PossiblyUnknownBits<16, false> rhs{0x3be1_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe35d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3be1_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_204")
{
  // 16'27409 / 16'20107 = 16'1
  {
    _Bits<16, false> lhs{27409u};
    _Bits<16, false> rhs{20107u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{1u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{27409u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{20107u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{1u};
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
    _PossiblyUnknownBits<16, false> lhs{0x6b11_b};
    _PossiblyUnknownBits<16, false> rhs{0x4e8b_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{1u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x6b11_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x4e8b_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{1u};
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
TEST_CASE("bits_205")
{
  // 16'38065 / 16'44445 = 16'0
  {
    _Bits<16, false> lhs{38065u};
    _Bits<16, false> rhs{44445u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{38065u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{44445u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0x94b1_b};
    _PossiblyUnknownBits<16, false> rhs{0xad9d_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x94b1_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xad9d_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
TEST_CASE("bits_206")
{
  // 16'15862 / 16'3635 = 16'4
  {
    _Bits<16, false> lhs{15862u};
    _Bits<16, false> rhs{3635u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{4u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{15862u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{3635u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x3df6_b};
    _PossiblyUnknownBits<16, false> rhs{0xe33_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3df6_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe33_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{4u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_207")
{
  // 16'31061 / 16'9735 = 16'3
  {
    _Bits<16, false> lhs{31061u};
    _Bits<16, false> rhs{9735u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{31061u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{9735u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
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
    _PossiblyUnknownBits<16, false> lhs{0x7955_b};
    _PossiblyUnknownBits<16, false> rhs{0x2607_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7955_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2607_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{3u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_208")
{
  // 16'26503 / 16'5193 = 16'5
  {
    _Bits<16, false> lhs{26503u};
    _Bits<16, false> rhs{5193u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{5u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{26503u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{5193u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{5u};
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
    _PossiblyUnknownBits<16, false> lhs{0x6787_b};
    _PossiblyUnknownBits<16, false> rhs{0x1449_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{5u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x6787_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1449_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{5u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_209")
{
  // 16'7877 / 16'13897 = 16'0
  {
    _Bits<16, false> lhs{7877u};
    _Bits<16, false> rhs{13897u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{7877u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{13897u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x1ec5_b};
    _PossiblyUnknownBits<16, false> rhs{0x3649_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x1ec5_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3649_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_210")
{
  // 16'47444 / 16'60692 = 16'0
  {
    _Bits<16, false> lhs{47444u};
    _Bits<16, false> rhs{60692u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{47444u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{60692u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb954_b};
    _PossiblyUnknownBits<16, false> rhs{0xed14_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb954_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xed14_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_211")
{
  // 16'21874 / 16'41830 = 16'0
  {
    _Bits<16, false> lhs{21874u};
    _Bits<16, false> rhs{41830u};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{21874u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{41830u}, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x5572_b};
    _PossiblyUnknownBits<16, false> rhs{0xa366_b};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x5572_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xa366_b, Bits<32>{16}};
    auto result = lhs / rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_212")
{
  // 16'16718 % 16'56388 = 16'16718
  {
    _Bits<16, false> lhs{16718u};
    _Bits<16, false> rhs{56388u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{16718u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{16718u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{56388u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{16718u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x414e_b};
    _PossiblyUnknownBits<16, false> rhs{0xdc44_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{16718u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x414e_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xdc44_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{16718u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_213")
{
  // 16'9531 % 16'27763 = 16'9531
  {
    _Bits<16, false> lhs{9531u};
    _Bits<16, false> rhs{27763u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{9531u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{9531u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{27763u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{9531u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x253b_b};
    _PossiblyUnknownBits<16, false> rhs{0x6c73_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{9531u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x253b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x6c73_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{9531u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_214")
{
  // 16'17569 % 16'27041 = 16'17569
  {
    _Bits<16, false> lhs{17569u};
    _Bits<16, false> rhs{27041u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{17569u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{17569u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{27041u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{17569u};
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
    _PossiblyUnknownBits<16, false> lhs{0x44a1_b};
    _PossiblyUnknownBits<16, false> rhs{0x69a1_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{17569u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x44a1_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x69a1_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{17569u};
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
TEST_CASE("bits_215")
{
  // 16'37392 % 16'13446 = 16'10500
  {
    _Bits<16, false> lhs{37392u};
    _Bits<16, false> rhs{13446u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{10500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{37392u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{13446u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{10500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x9210_b};
    _PossiblyUnknownBits<16, false> rhs{0x3486_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{10500u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x9210_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3486_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{10500u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_216")
{
  // 16'29499 % 16'5883 = 16'84
  {
    _Bits<16, false> lhs{29499u};
    _Bits<16, false> rhs{5883u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{84u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{29499u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{5883u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{84u};
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
    _PossiblyUnknownBits<16, false> lhs{0x733b_b};
    _PossiblyUnknownBits<16, false> rhs{0x16fb_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{84u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x733b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x16fb_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{84u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_217")
{
  // 16'18959 % 16'54572 = 16'18959
  {
    _Bits<16, false> lhs{18959u};
    _Bits<16, false> rhs{54572u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{18959u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{18959u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{54572u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{18959u};
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
    _PossiblyUnknownBits<16, false> lhs{0x4a0f_b};
    _PossiblyUnknownBits<16, false> rhs{0xd52c_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{18959u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x4a0f_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xd52c_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{18959u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_218")
{
  // 16'4774 % 16'49714 = 16'4774
  {
    _Bits<16, false> lhs{4774u};
    _Bits<16, false> rhs{49714u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{4774u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{4774u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{49714u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{4774u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x12a6_b};
    _PossiblyUnknownBits<16, false> rhs{0xc232_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{4774u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x12a6_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xc232_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{4774u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_219")
{
  // 16'31249 % 16'59226 = 16'31249
  {
    _Bits<16, false> lhs{31249u};
    _Bits<16, false> rhs{59226u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{31249u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{31249u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{59226u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{31249u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7a11_b};
    _PossiblyUnknownBits<16, false> rhs{0xe75a_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{31249u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7a11_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe75a_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{31249u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_220")
{
  // 16'51451 % 16'10913 = 16'7799
  {
    _Bits<16, false> lhs{51451u};
    _Bits<16, false> rhs{10913u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{7799u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{51451u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{10913u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{7799u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc8fb_b};
    _PossiblyUnknownBits<16, false> rhs{0x2aa1_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{7799u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc8fb_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2aa1_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{7799u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_221")
{
  // 16'118 % 16'57436 = 16'118
  {
    _Bits<16, false> lhs{118u};
    _Bits<16, false> rhs{57436u};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{118u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{118u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{57436u}, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{118u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x76_b};
    _PossiblyUnknownBits<16, false> rhs{0xe05c_b};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{118u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x76_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe05c_b, Bits<32>{16}};
    auto result = lhs % rhs;
    auto expected = _Bits<16, false>{118u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_222")
{
  // 16'56193 >> 16'27 = 16'0
  {
    _Bits<16, false> lhs{56193u};
    _Bits<16, false> rhs{27u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{56193u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{27u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0xdb81_b};
    _PossiblyUnknownBits<16, false> rhs{0x1b_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xdb81_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1b_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_223")
{
  // 16'38265 >> 16'10 = 16'37
  {
    _Bits<16, false> lhs{38265u};
    _Bits<16, false> rhs{10u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{37u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{38265u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{10u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{37u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x9579_b};
    _PossiblyUnknownBits<16, false> rhs{0xa_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{37u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x9579_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xa_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{37u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_224")
{
  // 16'16717 >> 16'16 = 16'0
  {
    _Bits<16, false> lhs{16717u};
    _Bits<16, false> rhs{16u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{16717u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{16u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x414d_b};
    _PossiblyUnknownBits<16, false> rhs{0x10_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x414d_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x10_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_225")
{
  // 16'49238 >> 16'25 = 16'0
  {
    _Bits<16, false> lhs{49238u};
    _Bits<16, false> rhs{25u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{49238u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{25u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0xc056_b};
    _PossiblyUnknownBits<16, false> rhs{0x19_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc056_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x19_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_226")
{
  // 16'1679 >> 16'21 = 16'0
  {
    _Bits<16, false> lhs{1679u};
    _Bits<16, false> rhs{21u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{1679u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{21u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x68f_b};
    _PossiblyUnknownBits<16, false> rhs{0x15_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x68f_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x15_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_227")
{
  // 16'185 >> 16'0 = 16'185
  {
    _Bits<16, false> lhs{185u};
    _Bits<16, false> rhs{0u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{185u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{185u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{0u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{185u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb9_b};
    _PossiblyUnknownBits<16, false> rhs{0x0_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{185u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb9_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x0_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{185u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_228")
{
  // 16'34678 >> 16'3 = 16'4334
  {
    _Bits<16, false> lhs{34678u};
    _Bits<16, false> rhs{3u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{4334u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{34678u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{3u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{4334u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x8776_b};
    _PossiblyUnknownBits<16, false> rhs{0x3_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{4334u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x8776_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x3_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{4334u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_229")
{
  // 16'3707 >> 16'9 = 16'7
  {
    _Bits<16, false> lhs{3707u};
    _Bits<16, false> rhs{9u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{3707u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{9u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe7b_b};
    _PossiblyUnknownBits<16, false> rhs{0x9_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe7b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x9_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_230")
{
  // 16'50233 >> 16'10 = 16'49
  {
    _Bits<16, false> lhs{50233u};
    _Bits<16, false> rhs{10u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{49u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{50233u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{10u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{49u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc439_b};
    _PossiblyUnknownBits<16, false> rhs{0xa_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{49u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc439_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xa_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{49u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_231")
{
  // 16'50307 >> 16'16 = 16'0
  {
    _Bits<16, false> lhs{50307u};
    _Bits<16, false> rhs{16u};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{50307u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{16u}, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc483_b};
    _PossiblyUnknownBits<16, false> rhs{0x10_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc483_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x10_b, Bits<32>{16}};
    auto result = lhs >> rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_232")
{
  // 16'31906 >>> 16'12 = 16'7
  {
    _Bits<16, false> lhs{31906u};
    _Bits<16, false> rhs{12u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{7u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{31906u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{12u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x7ca2_b};
    _PossiblyUnknownBits<16, false> rhs{0xc_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{7u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x7ca2_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xc_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{7u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_233")
{
  // 16'57815 >>> 16'18 = 16'65535
  {
    _Bits<16, false> lhs{57815u};
    _Bits<16, false> rhs{18u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{57815u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{18u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe1d7_b};
    _PossiblyUnknownBits<16, false> rhs{0x12_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe1d7_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x12_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_234")
{
  // 16'59068 >>> 16'18 = 16'65535
  {
    _Bits<16, false> lhs{59068u};
    _Bits<16, false> rhs{18u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{59068u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{18u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xe6bc_b};
    _PossiblyUnknownBits<16, false> rhs{0x12_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xe6bc_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x12_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_235")
{
  // 16'50394 >>> 16'6 = 16'65299
  {
    _Bits<16, false> lhs{50394u};
    _Bits<16, false> rhs{6u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65299u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{50394u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{6u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65299u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc4da_b};
    _PossiblyUnknownBits<16, false> rhs{0x6_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65299u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc4da_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x6_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65299u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_236")
{
  // 16'195 >>> 16'29 = 16'0
  {
    _Bits<16, false> lhs{195u};
    _Bits<16, false> rhs{29u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{195u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{29u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc3_b};
    _PossiblyUnknownBits<16, false> rhs{0x1d_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc3_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1d_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
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
TEST_CASE("bits_237")
{
  // 16'45767 >>> 16'27 = 16'65535
  {
    _Bits<16, false> lhs{45767u};
    _Bits<16, false> rhs{27u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{45767u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{27u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb2c7_b};
    _PossiblyUnknownBits<16, false> rhs{0x1b_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb2c7_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1b_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_238")
{
  // 16'16698 >>> 16'20 = 16'0
  {
    _Bits<16, false> lhs{16698u};
    _Bits<16, false> rhs{20u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{16698u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{20u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x413a_b};
    _PossiblyUnknownBits<16, false> rhs{0x14_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x413a_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x14_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_239")
{
  // 16'15116 >>> 16'15 = 16'0
  {
    _Bits<16, false> lhs{15116u};
    _Bits<16, false> rhs{15u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{15116u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{15u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0x3b0c_b};
    _PossiblyUnknownBits<16, false> rhs{0xf_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3b0c_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xf_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_240")
{
  // 16'8116 >>> 16'30 = 16'0
  {
    _Bits<16, false> lhs{8116u};
    _Bits<16, false> rhs{30u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{8116u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{30u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0x1fb4_b};
    _PossiblyUnknownBits<16, false> rhs{0x1e_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x1fb4_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1e_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{0u};
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
TEST_CASE("bits_241")
{
  // 16'50483 >>> 16'29 = 16'65535
  {
    _Bits<16, false> lhs{50483u};
    _Bits<16, false> rhs{29u};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{50483u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{29u}, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc533_b};
    _PossiblyUnknownBits<16, false> rhs{0x1d_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc533_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1d_b, Bits<32>{16}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<16, false>{65535u};
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
TEST_CASE("bits_242")
{
  // 16'13936 << 16'6 = 16'39936
  {
    _Bits<16, false> lhs{13936u};
    _Bits<16, false> rhs{6u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{39936u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{13936u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{6u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{39936u};
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
    _PossiblyUnknownBits<16, false> lhs{0x3670_b};
    _PossiblyUnknownBits<16, false> rhs{0x6_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{39936u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3670_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x6_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{39936u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_243")
{
  // 16'53679 << 16'18 = 16'0
  {
    _Bits<16, false> lhs{53679u};
    _Bits<16, false> rhs{18u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{53679u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{18u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0xd1af_b};
    _PossiblyUnknownBits<16, false> rhs{0x12_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd1af_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x12_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
TEST_CASE("bits_244")
{
  // 16'64069 << 16'28 = 16'0
  {
    _Bits<16, false> lhs{64069u};
    _Bits<16, false> rhs{28u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{64069u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{28u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0xfa45_b};
    _PossiblyUnknownBits<16, false> rhs{0x1c_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xfa45_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1c_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_245")
{
  // 16'46271 << 16'25 = 16'0
  {
    _Bits<16, false> lhs{46271u};
    _Bits<16, false> rhs{25u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{46271u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{25u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xb4bf_b};
    _PossiblyUnknownBits<16, false> rhs{0x19_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xb4bf_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x19_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_246")
{
  // 16'20854 << 16'2 = 16'17880
  {
    _Bits<16, false> lhs{20854u};
    _Bits<16, false> rhs{2u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{17880u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{20854u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{2u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{17880u};
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
    _PossiblyUnknownBits<16, false> lhs{0x5176_b};
    _PossiblyUnknownBits<16, false> rhs{0x2_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{17880u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x5176_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{17880u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_247")
{
  // 16'7145 << 16'1 = 16'14290
  {
    _Bits<16, false> lhs{7145u};
    _Bits<16, false> rhs{1u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{14290u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{7145u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{1u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{14290u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x1be9_b};
    _PossiblyUnknownBits<16, false> rhs{0x1_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{14290u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x1be9_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{14290u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_248")
{
  // 16'50903 << 16'9 = 16'44544
  {
    _Bits<16, false> lhs{50903u};
    _Bits<16, false> rhs{9u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{44544u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{50903u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{9u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{44544u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xc6d7_b};
    _PossiblyUnknownBits<16, false> rhs{0x9_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{44544u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xc6d7_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x9_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{44544u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_249")
{
  // 16'13827 << 16'2 = 16'55308
  {
    _Bits<16, false> lhs{13827u};
    _Bits<16, false> rhs{2u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{55308u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{13827u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{2u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{55308u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x3603_b};
    _PossiblyUnknownBits<16, false> rhs{0x2_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{55308u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3603_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x2_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{55308u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_250")
{
  // 16'24171 << 16'23 = 16'0
  {
    _Bits<16, false> lhs{24171u};
    _Bits<16, false> rhs{23u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{24171u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{23u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x5e6b_b};
    _PossiblyUnknownBits<16, false> rhs{0x17_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x5e6b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x17_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_251")
{
  // 16'15162 << 16'23 = 16'0
  {
    _Bits<16, false> lhs{15162u};
    _Bits<16, false> rhs{23u};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{15162u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{23u}, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
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
    _PossiblyUnknownBits<16, false> lhs{0x3b3a_b};
    _PossiblyUnknownBits<16, false> rhs{0x17_b};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3b3a_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x17_b, Bits<32>{16}};
    auto result = lhs << rhs;
    auto expected = _Bits<16, false>{0u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_252")
{
  // 16'65127 `<< 16'1 = 17'130254
  {
    _Bits<16, false> lhs{65127u};
    _Bits<16, false> rhs{1u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{130254u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{65127u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{1u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{130254u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xfe67_b};
    _PossiblyUnknownBits<16, false> rhs{0x1_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{130254u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xfe67_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<17, false>{130254u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_253")
{
  // 16'60844 `<< 16'7 = 23'7788032
  {
    _Bits<16, false> lhs{60844u};
    _Bits<16, false> rhs{7u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{7788032u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{60844u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{7u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{7788032u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xedac_b};
    _PossiblyUnknownBits<16, false> rhs{0x7_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{7788032u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xedac_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x7_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{7788032u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_254")
{
  // 16'52035 `<< 16'29 = 45'27936077905920
  {
    _Bits<16, false> lhs{52035u};
    _Bits<16, false> rhs{29u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{27936077905920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{52035u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{29u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{27936077905920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xcb43_b};
    _PossiblyUnknownBits<16, false> rhs{0x1d_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{27936077905920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xcb43_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1d_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<45, false>{27936077905920llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_255")
{
  // 16'11366 `<< 16'20 = 36'11918114816
  {
    _Bits<16, false> lhs{11366u};
    _Bits<16, false> rhs{20u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<36, false>{11918114816llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{11366u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{20u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<36, false>{11918114816llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x2c66_b};
    _PossiblyUnknownBits<16, false> rhs{0x14_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<36, false>{11918114816llu};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x2c66_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x14_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<36, false>{11918114816llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_256")
{
  // 16'17963 `<< 16'7 = 23'2299264
  {
    _Bits<16, false> lhs{17963u};
    _Bits<16, false> rhs{7u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{2299264u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{17963u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{7u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{2299264u};
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
    _PossiblyUnknownBits<16, false> lhs{0x462b_b};
    _PossiblyUnknownBits<16, false> rhs{0x7_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{2299264u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x462b_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x7_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<23, false>{2299264u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_257")
{
  // 16'15274 `<< 16'30 = 46'16400332619776
  {
    _Bits<16, false> lhs{15274u};
    _Bits<16, false> rhs{30u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<46, false>{16400332619776llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{15274u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{30u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<46, false>{16400332619776llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0x3baa_b};
    _PossiblyUnknownBits<16, false> rhs{0x1e_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<46, false>{16400332619776llu};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0x3baa_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x1e_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<46, false>{16400332619776llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_258")
{
  // 16'48866 `<< 16'15 = 31'1601241088
  {
    _Bits<16, false> lhs{48866u};
    _Bits<16, false> rhs{15u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<31, false>{1601241088u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{48866u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{15u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<31, false>{1601241088u};
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
    _PossiblyUnknownBits<16, false> lhs{0xbee2_b};
    _PossiblyUnknownBits<16, false> rhs{0xf_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<31, false>{1601241088u};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xbee2_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xf_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<31, false>{1601241088u};
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
TEST_CASE("bits_259")
{
  // 16'54095 `<< 16'25 = 41'1815126999040
  {
    _Bits<16, false> lhs{54095u};
    _Bits<16, false> rhs{25u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<41, false>{1815126999040llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{54095u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{25u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<41, false>{1815126999040llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xd34f_b};
    _PossiblyUnknownBits<16, false> rhs{0x19_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<41, false>{1815126999040llu};
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
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd34f_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x19_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<41, false>{1815126999040llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_260")
{
  // 16'56478 `<< 16'14 = 30'925335552
  {
    _Bits<16, false> lhs{56478u};
    _Bits<16, false> rhs{14u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<30, false>{925335552u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<16, false> lhs{Bits<16>{56478u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{14u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<30, false>{925335552u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<16, false> lhs{0xdc9e_b};
    _PossiblyUnknownBits<16, false> rhs{0xe_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<30, false>{925335552u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xdc9e_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0xe_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<30, false>{925335552u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_261")
{
  // 16'55475 `<< 16'9 = 25'28403200
  {
    _Bits<16, false> lhs{55475u};
    _Bits<16, false> rhs{9u};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<25, false>{28403200u};
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
    _RuntimeBits<16, false> lhs{Bits<16>{55475u}, Bits<32>{16}};
    _RuntimeBits<16, false> rhs{Bits<16>{9u}, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<25, false>{28403200u};
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
    _PossiblyUnknownBits<16, false> lhs{0xd8b3_b};
    _PossiblyUnknownBits<16, false> rhs{0x9_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<25, false>{28403200u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<16, false> lhs{0xd8b3_b, Bits<32>{16}};
    _PossiblyUnknownRuntimeBits<16, false> rhs{0x9_b, Bits<32>{16}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<25, false>{28403200u};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
