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
TEST_CASE("bits_382")
{
  // 64'8638455028337470164 + 64'8843888942065340551 = 64'17482343970402810715
  {
    _Bits<64, false> lhs{8638455028337470164llu};
    _Bits<64, false> rhs{8843888942065340551llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{17482343970402810715llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8638455028337470164llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{8843888942065340551llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{17482343970402810715llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x77e1f5146c3dead4_b};
    _PossiblyUnknownBits<64, false> rhs{0x7abbce22c8cf5087_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{17482343970402810715llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x77e1f5146c3dead4_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x7abbce22c8cf5087_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{17482343970402810715llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_383")
{
  // 64'11064669831532093946 + 64'12482318021774562087 = 64'5100243779597104417
  {
    _Bits<64, false> lhs{11064669831532093946llu};
    _Bits<64, false> rhs{12482318021774562087llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5100243779597104417llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{11064669831532093946llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12482318021774562087llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5100243779597104417llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x998d9a96b173a1fa_b};
    _PossiblyUnknownBits<64, false> rhs{0xad3a1a1b4d545327_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5100243779597104417llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x998d9a96b173a1fa_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xad3a1a1b4d545327_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5100243779597104417llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_384")
{
  // 64'9782476282638822986 + 64'9896407774136070211 = 64'1232139983065341581
  {
    _Bits<64, false> lhs{9782476282638822986llu};
    _Bits<64, false> rhs{9896407774136070211llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{1232139983065341581llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9782476282638822986llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{9896407774136070211llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{1232139983065341581llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x87c256596a5eee4a_b};
    _PossiblyUnknownBits<64, false> rhs{0x89571a6fe9cb7043_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{1232139983065341581llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x87c256596a5eee4a_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x89571a6fe9cb7043_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{1232139983065341581llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_385")
{
  // 64'17151564439321484897 + 64'5941057680956897236 = 64'4645878046568830517
  {
    _Bits<64, false> lhs{17151564439321484897llu};
    _Bits<64, false> rhs{5941057680956897236llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{4645878046568830517llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{17151564439321484897llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{5941057680956897236llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{4645878046568830517llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xee0698fc13fa9e61_b};
    _PossiblyUnknownBits<64, false> rhs{0x5272e07bd78ab7d4_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{4645878046568830517llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xee0698fc13fa9e61_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5272e07bd78ab7d4_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{4645878046568830517llu};
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
TEST_CASE("bits_386")
{
  // 64'3199764993357124668 + 64'4285251330339510836 = 64'7485016323696635504
  {
    _Bits<64, false> lhs{3199764993357124668llu};
    _Bits<64, false> rhs{4285251330339510836llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{7485016323696635504llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{3199764993357124668llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4285251330339510836llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{7485016323696635504llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2c67d94ef1c8143c_b};
    _PossiblyUnknownBits<64, false> rhs{0x3b78456176281a34_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{7485016323696635504llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2c67d94ef1c8143c_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x3b78456176281a34_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{7485016323696635504llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_387")
{
  // 64'8969739434461155044 + 64'411509802012219840 = 64'9381249236473374884
  {
    _Bits<64, false> lhs{8969739434461155044llu};
    _Bits<64, false> rhs{411509802012219840llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{9381249236473374884llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{8969739434461155044llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{411509802012219840llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{9381249236473374884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x7c7aea7deedecee4_b};
    _PossiblyUnknownBits<64, false> rhs{0x5b5f9fc128799c0_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{9381249236473374884llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x7c7aea7deedecee4_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5b5f9fc128799c0_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{9381249236473374884llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_388")
{
  // 64'12349161602775381867 + 64'11149317675906716397 = 64'5051735204972546648
  {
    _Bits<64, false> lhs{12349161602775381867llu};
    _Bits<64, false> rhs{11149317675906716397llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5051735204972546648llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{12349161602775381867llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{11149317675906716397llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5051735204972546648llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xab61090c8f51f76b_b};
    _PossiblyUnknownBits<64, false> rhs{0x9aba555ac86752ed_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5051735204972546648llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xab61090c8f51f76b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x9aba555ac86752ed_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{5051735204972546648llu};
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
TEST_CASE("bits_389")
{
  // 64'6780105239838272129 + 64'1749093748137847299 = 64'8529198987976119428
  {
    _Bits<64, false> lhs{6780105239838272129llu};
    _Bits<64, false> rhs{1749093748137847299llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8529198987976119428llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{6780105239838272129llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{1749093748137847299llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8529198987976119428llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x5e17c5cb08532a81_b};
    _PossiblyUnknownBits<64, false> rhs{0x1846077f309cea03_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8529198987976119428llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5e17c5cb08532a81_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x1846077f309cea03_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8529198987976119428llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_390")
{
  // 64'3994711382737878559 + 64'17692695778173028928 = 64'3240663087201355871
  {
    _Bits<64, false> lhs{3994711382737878559llu};
    _Bits<64, false> rhs{17692695778173028928llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{3240663087201355871llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3994711382737878559llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17692695778173028928llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{3240663087201355871llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x377010d6744cfe1f_b};
    _PossiblyUnknownBits<64, false> rhs{0xf5891512010e8a40_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{3240663087201355871llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x377010d6744cfe1f_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf5891512010e8a40_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{3240663087201355871llu};
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
TEST_CASE("bits_391")
{
  // 64'11793257201970993096 + 64'15527722062273855616 = 64'8874235190535297096
  {
    _Bits<64, false> lhs{11793257201970993096llu};
    _Bits<64, false> rhs{15527722062273855616llu};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8874235190535297096llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{11793257201970993096llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15527722062273855616llu}, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8874235190535297096llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xa3aa10f11c4c57c8_b};
    _PossiblyUnknownBits<64, false> rhs{0xd77d8cf23cd44080_b};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8874235190535297096llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa3aa10f11c4c57c8_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd77d8cf23cd44080_b, Bits<32>{64}};
    auto result = lhs + rhs;
    auto expected = _Bits<64, false>{8874235190535297096llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_392")
{
  // 64'11603162513810824527 `+ 64'5469178520143408854 = 65'17072341033954233381
  {
    _Bits<64, false> lhs{11603162513810824527llu};
    _Bits<64, false> rhs{5469178520143408854llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{17072341033954233381_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{11603162513810824527llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{5469178520143408854llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{17072341033954233381_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xa106b6d482d29d4f_b};
    _PossiblyUnknownBits<64, false> rhs{0x4be66ce31a582ed6_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{17072341033954233381_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa106b6d482d29d4f_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x4be66ce31a582ed6_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{17072341033954233381_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_393")
{
  // 64'7608716430546009111 `+ 64'12031130447890490078 = 65'19639846878436499189
  {
    _Bits<64, false> lhs{7608716430546009111llu};
    _Bits<64, false> rhs{12031130447890490078llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{19639846878436499189_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{7608716430546009111llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12031130447890490078llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{19639846878436499189_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0x69979747e75f7c17_b};
    _PossiblyUnknownBits<64, false> rhs{0xa6f7296610e622de_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{19639846878436499189_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x69979747e75f7c17_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xa6f7296610e622de_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{19639846878436499189_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_394")
{
  // 64'3748315439145172288 `+ 64'15023147053359081158 = 65'18771462492504253446
  {
    _Bits<64, false> lhs{3748315439145172288llu};
    _Bits<64, false> rhs{15023147053359081158llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18771462492504253446_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3748315439145172288llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15023147053359081158llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18771462492504253446_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0x3404b108505c3d40_b};
    _PossiblyUnknownBits<64, false> rhs{0xd07cf0a623eca6c6_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18771462492504253446_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x3404b108505c3d40_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd07cf0a623eca6c6_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18771462492504253446_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_395")
{
  // 64'13749359607349584023 `+ 64'17114999702501798535 = 65'30864359309851382558
  {
    _Bits<64, false> lhs{13749359607349584023llu};
    _Bits<64, false> rhs{17114999702501798535llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{30864359309851382558_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{13749359607349584023llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17114999702501798535llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{30864359309851382558_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0xbecf89b7352d2097_b};
    _PossiblyUnknownBits<64, false> rhs{0xed84b18cde893287_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{30864359309851382558_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xbecf89b7352d2097_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xed84b18cde893287_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{30864359309851382558_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_396")
{
  // 64'7686257126303383638 `+ 64'12577152225803484260 = 65'20263409352106867898
  {
    _Bits<64, false> lhs{7686257126303383638llu};
    _Bits<64, false> rhs{12577152225803484260llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{20263409352106867898_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{7686257126303383638llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12577152225803484260llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{20263409352106867898_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0x6aab122201a0c056_b};
    _PossiblyUnknownBits<64, false> rhs{0xae8b05501107bc64_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{20263409352106867898_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6aab122201a0c056_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xae8b05501107bc64_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{20263409352106867898_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_397")
{
  // 64'13950218257043501715 `+ 64'18097420375582150765 = 65'32047638632625652480
  {
    _Bits<64, false> lhs{13950218257043501715llu};
    _Bits<64, false> rhs{18097420375582150765llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{32047638632625652480_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{13950218257043501715llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{18097420375582150765llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{32047638632625652480_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc1992197e63f3293_b};
    _PossiblyUnknownBits<64, false> rhs{0xfb26f3f2857d906d_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{32047638632625652480_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc1992197e63f3293_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xfb26f3f2857d906d_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{32047638632625652480_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_398")
{
  // 64'12261343169096502305 `+ 64'6113797733405260698 = 65'18375140902501763003
  {
    _Bits<64, false> lhs{12261343169096502305llu};
    _Bits<64, false> rhs{6113797733405260698llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18375140902501763003_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12261343169096502305llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{6113797733405260698llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18375140902501763003_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xaa290aa61f28cc21_b};
    _PossiblyUnknownBits<64, false> rhs{0x54d892a570357b9a_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18375140902501763003_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xaa290aa61f28cc21_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x54d892a570357b9a_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18375140902501763003_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_399")
{
  // 64'1108002463429679116 `+ 64'13797636960705901075 = 65'14905639424135580191
  {
    _Bits<64, false> lhs{1108002463429679116llu};
    _Bits<64, false> rhs{13797636960705901075llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{14905639424135580191_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{1108002463429679116llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{13797636960705901075llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{14905639424135580191_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0xf606a5ebafbd80c_b};
    _PossiblyUnknownBits<64, false> rhs{0xbf7b0db676acf213_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{14905639424135580191_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf606a5ebafbd80c_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xbf7b0db676acf213_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{14905639424135580191_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_400")
{
  // 64'6766969393852730149 `+ 64'6953352091166272654 = 65'13720321485019002803
  {
    _Bits<64, false> lhs{6766969393852730149llu};
    _Bits<64, false> rhs{6953352091166272654llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{13720321485019002803_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{6766969393852730149llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{6953352091166272654llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{13720321485019002803_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x5de91acf8e884b25_b};
    _PossiblyUnknownBits<64, false> rhs{0x607f44e2f02f6c8e_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{13720321485019002803_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5de91acf8e884b25_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x607f44e2f02f6c8e_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{13720321485019002803_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_401")
{
  // 64'2048523995591009677 `+ 64'16809385428154596538 = 65'18857909423745606215
  {
    _Bits<64, false> lhs{2048523995591009677llu};
    _Bits<64, false> rhs{16809385428154596538llu};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18857909423745606215_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2048523995591009677llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16809385428154596538llu}, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18857909423745606215_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x1c6dd1b86f10e58d_b};
    _PossiblyUnknownBits<64, false> rhs{0xe946eefca9c83cba_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18857909423745606215_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x1c6dd1b86f10e58d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xe946eefca9c83cba_b, Bits<32>{64}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<65, false>{18857909423745606215_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_402")
{
  // 64'1400054397692763497 - 64'4876007767527219840 = 64'14970790703875095273
  {
    _Bits<64, false> lhs{1400054397692763497llu};
    _Bits<64, false> rhs{4876007767527219840llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14970790703875095273llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{1400054397692763497llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4876007767527219840llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14970790703875095273llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x136dfe0e90b35d69_b};
    _PossiblyUnknownBits<64, false> rhs{0x43ab0f3af9816280_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14970790703875095273llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x136dfe0e90b35d69_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x43ab0f3af9816280_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14970790703875095273llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_403")
{
  // 64'542312570984250988 - 64'15036049727487229511 = 64'3953006917206573093
  {
    _Bits<64, false> lhs{542312570984250988llu};
    _Bits<64, false> rhs{15036049727487229511llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3953006917206573093llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{542312570984250988llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15036049727487229511llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3953006917206573093llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x786ae68f6bebe6c_b};
    _PossiblyUnknownBits<64, false> rhs{0xd0aac7900ffc3e47_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3953006917206573093llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x786ae68f6bebe6c_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd0aac7900ffc3e47_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3953006917206573093llu};
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
TEST_CASE("bits_404")
{
  // 64'18221718978889201878 - 64'17920562820797104895 = 64'301156158092096983
  {
    _Bits<64, false> lhs{18221718978889201878llu};
    _Bits<64, false> rhs{17920562820797104895llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{301156158092096983llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{18221718978889201878llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17920562820797104895llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{301156158092096983llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xfce08cde55af38d6_b};
    _PossiblyUnknownBits<64, false> rhs{0xf8b2a0f034af02ff_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{301156158092096983llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xfce08cde55af38d6_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf8b2a0f034af02ff_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{301156158092096983llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_405")
{
  // 64'3371150746815839359 - 64'16618833670966200806 = 64'5199061149559190169
  {
    _Bits<64, false> lhs{3371150746815839359llu};
    _Bits<64, false> rhs{16618833670966200806llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{5199061149559190169llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3371150746815839359llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16618833670966200806llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{5199061149559190169llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2ec8bbbe3c403c7f_b};
    _PossiblyUnknownBits<64, false> rhs{0xe6a1f52c633dc9e6_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{5199061149559190169llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2ec8bbbe3c403c7f_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xe6a1f52c633dc9e6_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{5199061149559190169llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_406")
{
  // 64'21469201849662084 - 64'2105603610974404024 = 64'16362609664584809676
  {
    _Bits<64, false> lhs{21469201849662084llu};
    _Bits<64, false> rhs{2105603610974404024llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{16362609664584809676llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{21469201849662084llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2105603610974404024llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{16362609664584809676llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4c462015dc3a84_b};
    _PossiblyUnknownBits<64, false> rhs{0x1d389b5405e8bdb8_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{16362609664584809676llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4c462015dc3a84_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x1d389b5405e8bdb8_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{16362609664584809676llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_407")
{
  // 64'10989267027899734583 - 64'9076347540666850463 = 64'1912919487232884120
  {
    _Bits<64, false> lhs{10989267027899734583llu};
    _Bits<64, false> rhs{9076347540666850463llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{1912919487232884120llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{10989267027899734583llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{9076347540666850463llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{1912919487232884120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x9881b82363e05a37_b};
    _PossiblyUnknownBits<64, false> rhs{0x7df5a9ffeb701c9f_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{1912919487232884120llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x9881b82363e05a37_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x7df5a9ffeb701c9f_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{1912919487232884120llu};
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
TEST_CASE("bits_408")
{
  // 64'13844915880404588595 - 64'17603090254042142519 = 64'14688569700071997692
  {
    _Bits<64, false> lhs{13844915880404588595llu};
    _Bits<64, false> rhs{17603090254042142519llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14688569700071997692llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{13844915880404588595llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17603090254042142519llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14688569700071997692llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc02305a3c4ae1833_b};
    _PossiblyUnknownBits<64, false> rhs{0xf44abd5225529737_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14688569700071997692llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc02305a3c4ae1833_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf44abd5225529737_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{14688569700071997692llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_409")
{
  // 64'13903972055372936790 - 64'1837436975880462856 = 64'12066535079492473934
  {
    _Bits<64, false> lhs{13903972055372936790llu};
    _Bits<64, false> rhs{1837436975880462856llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{12066535079492473934llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{13903972055372936790llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{1837436975880462856llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{12066535079492473934llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc0f4d4eaff763656_b};
    _PossiblyUnknownBits<64, false> rhs{0x197fe331c485e208_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{12066535079492473934llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc0f4d4eaff763656_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x197fe331c485e208_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{12066535079492473934llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_410")
{
  // 64'12133582626612697045 - 64'2520594810578065441 = 64'9612987816034631604
  {
    _Bits<64, false> lhs{12133582626612697045llu};
    _Bits<64, false> rhs{2520594810578065441llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{9612987816034631604llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12133582626612697045llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2520594810578065441llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{9612987816034631604llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xa863251cc819d7d5_b};
    _PossiblyUnknownBits<64, false> rhs{0x22faf3a02332d821_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{9612987816034631604llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa863251cc819d7d5_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x22faf3a02332d821_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{9612987816034631604llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_411")
{
  // 64'8605939944951279660 - 64'4787020973736617672 = 64'3818918971214661988
  {
    _Bits<64, false> lhs{8605939944951279660llu};
    _Bits<64, false> rhs{4787020973736617672llu};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3818918971214661988llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8605939944951279660llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4787020973736617672llu}, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3818918971214661988llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x776e70c8a12a702c_b};
    _PossiblyUnknownBits<64, false> rhs{0x426eea367fea66c8_b};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3818918971214661988llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x776e70c8a12a702c_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x426eea367fea66c8_b, Bits<32>{64}};
    auto result = lhs - rhs;
    auto expected = _Bits<64, false>{3818918971214661988llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_412")
{
  // 64'8068611698640020676 `- 64'411855633057257996 = 65'7656756065582762680
  {
    _Bits<64, false> lhs{8068611698640020676llu};
    _Bits<64, false> rhs{411855633057257996llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{7656756065582762680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8068611698640020676llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{411855633057257996llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{7656756065582762680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6ff977972fffe4c4_b};
    _PossiblyUnknownBits<64, false> rhs{0x5b73484231f1a0c_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{7656756065582762680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6ff977972fffe4c4_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5b73484231f1a0c_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{7656756065582762680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_413")
{
  // 64'4305182576384542834 `- 64'12863809525807445230 = 65'28334861197996200836
  {
    _Bits<64, false> lhs{4305182576384542834llu};
    _Bits<64, false> rhs{12863809525807445230llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{28334861197996200836_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{4305182576384542834llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12863809525807445230llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{28334861197996200836_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x3bbf14be4e9a0872_b};
    _PossiblyUnknownBits<64, false> rhs{0xb2856e9bbc09f4ee_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{28334861197996200836_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x3bbf14be4e9a0872_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xb2856e9bbc09f4ee_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{28334861197996200836_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_414")
{
  // 64'2274110296855726913 `- 64'7260407123794310100 = 65'31907191320480520045
  {
    _Bits<64, false> lhs{2274110296855726913llu};
    _Bits<64, false> rhs{7260407123794310100llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{31907191320480520045_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2274110296855726913llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{7260407123794310100llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{31907191320480520045_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x1f8f43442824cb41_b};
    _PossiblyUnknownBits<64, false> rhs{0x64c225cfd279b3d4_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{31907191320480520045_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x1f8f43442824cb41_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x64c225cfd279b3d4_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{31907191320480520045_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_415")
{
  // 64'339714723386239734 `- 64'7881912231781404658 = 65'29351290639023938308
  {
    _Bits<64, false> lhs{339714723386239734llu};
    _Bits<64, false> rhs{7881912231781404658llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{29351290639023938308_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{339714723386239734llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{7881912231781404658llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{29351290639023938308_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0x4b6e8bdb4682af6_b};
    _PossiblyUnknownBits<64, false> rhs{0x6d622d6a26230ff2_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{29351290639023938308_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4b6e8bdb4682af6_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x6d622d6a26230ff2_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{29351290639023938308_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_416")
{
  // 64'16212387268652364101 `- 64'11822238745149968812 = 65'4390148523502395289
  {
    _Bits<64, false> lhs{16212387268652364101llu};
    _Bits<64, false> rhs{11822238745149968812llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{4390148523502395289_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{16212387268652364101llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{11822238745149968812llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{4390148523502395289_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xe0fdf852ed16f145_b};
    _PossiblyUnknownBits<64, false> rhs{0xa4110780768611ac_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{4390148523502395289_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xe0fdf852ed16f145_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xa4110780768611ac_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{4390148523502395289_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_417")
{
  // 64'17844502595182374858 `- 64'12285458503787096893 = 65'5559044091395277965
  {
    _Bits<64, false> lhs{17844502595182374858llu};
    _Bits<64, false> rhs{12285458503787096893llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{5559044091395277965_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{17844502595182374858llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12285458503787096893llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{5559044091395277965_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xf7a46890eb61afca_b};
    _PossiblyUnknownBits<64, false> rhs{0xaa7eb76b05082b3d_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{5559044091395277965_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf7a46890eb61afca_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xaa7eb76b05082b3d_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{5559044091395277965_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_418")
{
  // 64'14124216202910950017 `- 64'2124301257506637929 = 65'11999914945404312088
  {
    _Bits<64, false> lhs{14124216202910950017llu};
    _Bits<64, false> rhs{2124301257506637929llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{11999914945404312088_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{14124216202910950017llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2124301257506637929llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{11999914945404312088_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc4034bcda152e281_b};
    _PossiblyUnknownBits<64, false> rhs{0x1d7b08bd19994869_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{11999914945404312088_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc4034bcda152e281_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x1d7b08bd19994869_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{11999914945404312088_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_419")
{
  // 64'225332034575639856 `- 64'3945092359042695015 = 65'33173727822952048073
  {
    _Bits<64, false> lhs{225332034575639856llu};
    _Bits<64, false> rhs{3945092359042695015llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{33173727822952048073_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{225332034575639856llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{3945092359042695015llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{33173727822952048073_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x3208a4aa565a530_b};
    _PossiblyUnknownBits<64, false> rhs{0x36bfc8993ad8ff67_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{33173727822952048073_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x3208a4aa565a530_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x36bfc8993ad8ff67_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{33173727822952048073_u128};
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
TEST_CASE("bits_420")
{
  // 64'5959805101637317411 `- 64'4599631084952404317 = 65'1360174016684913094
  {
    _Bits<64, false> lhs{5959805101637317411llu};
    _Bits<64, false> rhs{4599631084952404317llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{1360174016684913094_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5959805101637317411llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4599631084952404317llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{1360174016684913094_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x52b57b29dda73323_b};
    _PossiblyUnknownBits<64, false> rhs{0x3fd52c1a146ec15d_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{1360174016684913094_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x52b57b29dda73323_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x3fd52c1a146ec15d_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{1360174016684913094_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_421")
{
  // 64'5694779316714847743 `- 64'17219892445862093195 = 65'25368375018271857780
  {
    _Bits<64, false> lhs{5694779316714847743llu};
    _Bits<64, false> rhs{17219892445862093195llu};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{25368375018271857780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5694779316714847743llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17219892445862093195llu}, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{25368375018271857780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4f07eb9dc707bdff_b};
    _PossiblyUnknownBits<64, false> rhs{0xeef958f1d20ae18b_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{25368375018271857780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4f07eb9dc707bdff_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xeef958f1d20ae18b_b, Bits<32>{64}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<65, false>{25368375018271857780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_422")
{
  // 64'731022248302706699 * 64'2583213266031728259 = 64'532568365707343777
  {
    _Bits<64, false> lhs{731022248302706699llu};
    _Bits<64, false> rhs{2583213266031728259llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{532568365707343777llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{731022248302706699llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2583213266031728259llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{532568365707343777llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xa251cdc98fd800b_b};
    _PossiblyUnknownBits<64, false> rhs{0x23d96ac76ce5d683_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{532568365707343777llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa251cdc98fd800b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x23d96ac76ce5d683_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{532568365707343777llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_423")
{
  // 64'11455054943077086199 * 64'7765535062797270955 = 64'1889240825017171709
  {
    _Bits<64, false> lhs{11455054943077086199llu};
    _Bits<64, false> rhs{7765535062797270955llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1889240825017171709llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{11455054943077086199llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{7765535062797270955llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1889240825017171709llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x9ef887c77cb133f7_b};
    _PossiblyUnknownBits<64, false> rhs{0x6bc4b8fefcdf3fab_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1889240825017171709llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x9ef887c77cb133f7_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x6bc4b8fefcdf3fab_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1889240825017171709llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_424")
{
  // 64'4782503642206780878 * 64'16656410193554348193 = 64'2529405802905087630
  {
    _Bits<64, false> lhs{4782503642206780878llu};
    _Bits<64, false> rhs{16656410193554348193llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{2529405802905087630llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{4782503642206780878llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16656410193554348193llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{2529405802905087630llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x425eddb94abf3dce_b};
    _PossiblyUnknownBits<64, false> rhs{0xe72774d2540098a1_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{2529405802905087630llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x425eddb94abf3dce_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xe72774d2540098a1_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{2529405802905087630llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_425")
{
  // 64'8283999101734300483 * 64'5802597695687385129 = 64'8070954478615203259
  {
    _Bits<64, false> lhs{8283999101734300483llu};
    _Bits<64, false> rhs{5802597695687385129llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8070954478615203259llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8283999101734300483llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{5802597695687385129llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8070954478615203259llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x72f6ad4ae2872b43_b};
    _PossiblyUnknownBits<64, false> rhs{0x5086f7dc59f26029_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8070954478615203259llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x72f6ad4ae2872b43_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5086f7dc59f26029_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8070954478615203259llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_426")
{
  // 64'9633298256517493861 * 64'7367450861513215260 = 64'7225196031377792012
  {
    _Bits<64, false> lhs{9633298256517493861llu};
    _Bits<64, false> rhs{7367450861513215260llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{7225196031377792012llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9633298256517493861llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{7367450861513215260llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{7225196031377792012llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x85b059b9931d7465_b};
    _PossiblyUnknownBits<64, false> rhs{0x663e71862ca40d1c_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{7225196031377792012llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x85b059b9931d7465_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x663e71862ca40d1c_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{7225196031377792012llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_427")
{
  // 64'10708363026858691495 * 64'10322665699184654197 = 64'14337526180172624979
  {
    _Bits<64, false> lhs{10708363026858691495llu};
    _Bits<64, false> rhs{10322665699184654197llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{14337526180172624979llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{10708363026858691495llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{10322665699184654197llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{14337526180172624979llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x949bbf7005d6cba7_b};
    _PossiblyUnknownBits<64, false> rhs{0x8f4179c2f702b775_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{14337526180172624979llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x949bbf7005d6cba7_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x8f4179c2f702b775_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{14337526180172624979llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_428")
{
  // 64'14673945749211968258 * 64'17818230798747462220 = 64'8212841164038666392
  {
    _Bits<64, false> lhs{14673945749211968258llu};
    _Bits<64, false> rhs{17818230798747462220llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8212841164038666392llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{14673945749211968258llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17818230798747462220llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8212841164038666392llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xcba453e9bb21f302_b};
    _PossiblyUnknownBits<64, false> rhs{0xf7471281a5446a4c_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8212841164038666392llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xcba453e9bb21f302_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf7471281a5446a4c_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{8212841164038666392llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_429")
{
  // 64'9387568778082994896 * 64'17976197972657150349 = 64'10200481600659162256
  {
    _Bits<64, false> lhs{9387568778082994896llu};
    _Bits<64, false> rhs{17976197972657150349llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{10200481600659162256llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9387568778082994896llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17976197972657150349llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{10200481600659162256llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x82475810f22f4ad0_b};
    _PossiblyUnknownBits<64, false> rhs{0xf97848d06c53998d_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{10200481600659162256llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x82475810f22f4ad0_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf97848d06c53998d_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{10200481600659162256llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_430")
{
  // 64'18444815891639981182 * 64'1526456558864955891 = 64'3151897603948331418
  {
    _Bits<64, false> lhs{18444815891639981182llu};
    _Bits<64, false> rhs{1526456558864955891llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{3151897603948331418llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{18444815891639981182llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{1526456558864955891llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{3151897603948331418llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xfff9265420ae547e_b};
    _PossiblyUnknownBits<64, false> rhs{0x152f10271c35f9f3_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{3151897603948331418llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xfff9265420ae547e_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x152f10271c35f9f3_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{3151897603948331418llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_431")
{
  // 64'6498301652070767133 * 64'3276924875871921771 = 64'1310925664354220063
  {
    _Bits<64, false> lhs{6498301652070767133llu};
    _Bits<64, false> rhs{3276924875871921771llu};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1310925664354220063llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{6498301652070767133llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{3276924875871921771llu}, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1310925664354220063llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x5a2e9aec4f031a1d_b};
    _PossiblyUnknownBits<64, false> rhs{0x2d79f9d00dfca66b_b};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1310925664354220063llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5a2e9aec4f031a1d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x2d79f9d00dfca66b_b, Bits<32>{64}};
    auto result = lhs * rhs;
    auto expected = _Bits<64, false>{1310925664354220063llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_432")
{
  // 64'5568144847824536778 `* 64'15579114551236340336 = 128'86746766422134898837205976569156877408
  {
    _Bits<64, false> lhs{5568144847824536778llu};
    _Bits<64, false> rhs{15579114551236340336llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{86746766422134898837205976569156877408_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5568144847824536778llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15579114551236340336llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{86746766422134898837205976569156877408_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4d46063ce080c4ca_b};
    _PossiblyUnknownBits<64, false> rhs{0xd8342224858faa70_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{86746766422134898837205976569156877408_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4d46063ce080c4ca_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd8342224858faa70_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{86746766422134898837205976569156877408_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_433")
{
  // 64'3402414427081249879 `* 64'14897831854572820048 = 128'50688598034229175888936419721588774192
  {
    _Bits<64, false> lhs{3402414427081249879llu};
    _Bits<64, false> rhs{14897831854572820048llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{50688598034229175888936419721588774192_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3402414427081249879llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{14897831854572820048llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{50688598034229175888936419721588774192_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2f37cde508d79457_b};
    _PossiblyUnknownBits<64, false> rhs{0xcebfbb23bf4fd650_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{50688598034229175888936419721588774192_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2f37cde508d79457_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xcebfbb23bf4fd650_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{50688598034229175888936419721588774192_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_434")
{
  // 64'3385129742679662176 `* 64'3333489586857009420 = 128'11284294747382601675092745663249697920
  {
    _Bits<64, false> lhs{3385129742679662176llu};
    _Bits<64, false> rhs{3333489586857009420llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{11284294747382601675092745663249697920_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3385129742679662176llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{3333489586857009420llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{11284294747382601675092745663249697920_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0x2efa6590d707de60_b};
    _PossiblyUnknownBits<64, false> rhs{0x2e42ef1e1f13610c_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{11284294747382601675092745663249697920_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2efa6590d707de60_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x2e42ef1e1f13610c_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{11284294747382601675092745663249697920_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_435")
{
  // 64'15545452742661645304 `* 64'17775033707536483623 = 128'276320946499726222983236668063830856392
  {
    _Bits<64, false> lhs{15545452742661645304llu};
    _Bits<64, false> rhs{17775033707536483623llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{276320946499726222983236668063830856392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{15545452742661645304llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17775033707536483623llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{276320946499726222983236668063830856392_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0xd7bc8ae7f6f823f8_b};
    _PossiblyUnknownBits<64, false> rhs{0xf6ad9afb184e8527_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{276320946499726222983236668063830856392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xd7bc8ae7f6f823f8_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf6ad9afb184e8527_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{276320946499726222983236668063830856392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_436")
{
  // 64'1115302163399558853 `* 64'8949243053561527736 = 128'9981110138425646027244554555123846808
  {
    _Bits<64, false> lhs{1115302163399558853llu};
    _Bits<64, false> rhs{8949243053561527736llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{9981110138425646027244554555123846808_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{1115302163399558853llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{8949243053561527736llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{9981110138425646027244554555123846808_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xf7a596892a7c6c5_b};
    _PossiblyUnknownBits<64, false> rhs{0x7c321924602abdb8_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{9981110138425646027244554555123846808_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf7a596892a7c6c5_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x7c321924602abdb8_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{9981110138425646027244554555123846808_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_437")
{
  // 64'3383273306363755942 `* 64'6060244401536804311 = 128'20503463113759865312983268665817465962
  {
    _Bits<64, false> lhs{3383273306363755942llu};
    _Bits<64, false> rhs{6060244401536804311llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{20503463113759865312983268665817465962_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{3383273306363755942llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{6060244401536804311llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{20503463113759865312983268665817465962_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2ef3cd2593df7da6_b};
    _PossiblyUnknownBits<64, false> rhs{0x541a502cb5a6a5d7_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{20503463113759865312983268665817465962_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2ef3cd2593df7da6_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x541a502cb5a6a5d7_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{20503463113759865312983268665817465962_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_438")
{
  // 64'17427602668001674939 `* 64'15105470797481658663 = 128'263252143171612742938516176015879346557
  {
    _Bits<64, false> lhs{17427602668001674939llu};
    _Bits<64, false> rhs{15105470797481658663llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{263252143171612742938516176015879346557_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{17427602668001674939llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15105470797481658663llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{263252143171612742938516176015879346557_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xf1db484a88e3c6bb_b};
    _PossiblyUnknownBits<64, false> rhs{0xd1a169a878ee4927_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{263252143171612742938516176015879346557_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf1db484a88e3c6bb_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd1a169a878ee4927_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{263252143171612742938516176015879346557_u128};
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
TEST_CASE("bits_439")
{
  // 64'13825136445369460827 `* 64'12806879693535439720 = 128'177056859202558878934935705512759848440
  {
    _Bits<64, false> lhs{13825136445369460827llu};
    _Bits<64, false> rhs{12806879693535439720llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{177056859202558878934935705512759848440_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{13825136445369460827llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12806879693535439720llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{177056859202558878934935705512759848440_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xbfdcc0592d8da85b_b};
    _PossiblyUnknownBits<64, false> rhs{0xb1bb2d3a3e57eb68_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{177056859202558878934935705512759848440_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xbfdcc0592d8da85b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xb1bb2d3a3e57eb68_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{177056859202558878934935705512759848440_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_440")
{
  // 64'12028754495252499624 `* 64'2808630132363048090 = 128'33784322330163637736865404424218918160
  {
    _Bits<64, false> lhs{12028754495252499624llu};
    _Bits<64, false> rhs{2808630132363048090llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{33784322330163637736865404424218918160_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12028754495252499624llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2808630132363048090llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{33784322330163637736865404424218918160_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xa6eeb87b7be88ca8_b};
    _PossiblyUnknownBits<64, false> rhs{0x26fa423980f5349a_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{33784322330163637736865404424218918160_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa6eeb87b7be88ca8_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x26fa423980f5349a_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{33784322330163637736865404424218918160_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_441")
{
  // 64'7849698807593858008 `* 64'16768057415202456134 = 128'131624200297780068753151391654444621072
  {
    _Bits<64, false> lhs{7849698807593858008llu};
    _Bits<64, false> rhs{16768057415202456134llu};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{131624200297780068753151391654444621072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7849698807593858008llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16768057415202456134llu}, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{131624200297780068753151391654444621072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6cefbb79dc7073d8_b};
    _PossiblyUnknownBits<64, false> rhs{0xe8b41b60ce7f4246_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{131624200297780068753151391654444621072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6cefbb79dc7073d8_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xe8b41b60ce7f4246_b, Bits<32>{64}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<128, false>{131624200297780068753151391654444621072_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_442")
{
  // 64'12110739680157931004 / 64'18163151516869966686 = 64'0
  {
    _Bits<64, false> lhs{12110739680157931004llu};
    _Bits<64, false> rhs{18163151516869966686llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12110739680157931004llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{18163151516869966686llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xa811fd92db0a95fc_b};
    _PossiblyUnknownBits<64, false> rhs{0xfc107a1274a1bb5e_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xa811fd92db0a95fc_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xfc107a1274a1bb5e_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_443")
{
  // 64'8263500291069871931 / 64'15675425459831481863 = 64'0
  {
    _Bits<64, false> lhs{8263500291069871931llu};
    _Bits<64, false> rhs{15675425459831481863llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{8263500291069871931llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15675425459831481863llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x72add9bb9a8e873b_b};
    _PossiblyUnknownBits<64, false> rhs{0xd98a4c675c5ea607_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x72add9bb9a8e873b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd98a4c675c5ea607_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_444")
{
  // 64'8586003694607552743 / 64'9843169817651990496 = 64'0
  {
    _Bits<64, false> lhs{8586003694607552743llu};
    _Bits<64, false> rhs{9843169817651990496llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8586003694607552743llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{9843169817651990496llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x77279cdea14650e7_b};
    _PossiblyUnknownBits<64, false> rhs{0x8899f6cc3cfe4fe0_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x77279cdea14650e7_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x8899f6cc3cfe4fe0_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_445")
{
  // 64'16143898066550154015 / 64'2070213953773040045 = 64'7
  {
    _Bits<64, false> lhs{16143898066550154015llu};
    _Bits<64, false> rhs{2070213953773040045llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{7llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{16143898066550154015llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{2070213953773040045llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{7llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xe00aa5c1ead6631f_b};
    _PossiblyUnknownBits<64, false> rhs{0x1cbae09f5bb2f1ad_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{7llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xe00aa5c1ead6631f_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x1cbae09f5bb2f1ad_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{7llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_446")
{
  // 64'15573073848075588809 / 64'4631537802016568302 = 64'3
  {
    _Bits<64, false> lhs{15573073848075588809llu};
    _Bits<64, false> rhs{4631537802016568302llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{3llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{15573073848075588809llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4631537802016568302llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{3llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xd81eac27b77894c9_b};
    _PossiblyUnknownBits<64, false> rhs{0x404687178cfdb3ee_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{3llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xd81eac27b77894c9_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x404687178cfdb3ee_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{3llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_447")
{
  // 64'7832750477593601926 / 64'1580819684496278487 = 64'4
  {
    _Bits<64, false> lhs{7832750477593601926llu};
    _Bits<64, false> rhs{1580819684496278487llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{4llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7832750477593601926llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{1580819684496278487llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{4llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6cb3850f473ce786_b};
    _PossiblyUnknownBits<64, false> rhs{0x15f03320a45883d7_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{4llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6cb3850f473ce786_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x15f03320a45883d7_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{4llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_448")
{
  // 64'15166310165530033634 / 64'9593132159408474872 = 64'1
  {
    _Bits<64, false> lhs{15166310165530033634llu};
    _Bits<64, false> rhs{9593132159408474872llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{15166310165530033634llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{9593132159408474872llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xd2798ebdb1d03de2_b};
    _PossiblyUnknownBits<64, false> rhs{0x8521a6df54eb0af8_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xd2798ebdb1d03de2_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x8521a6df54eb0af8_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_449")
{
  // 64'11509718810875827663 / 64'4172252624963492201 = 64'2
  {
    _Bits<64, false> lhs{11509718810875827663llu};
    _Bits<64, false> rhs{4172252624963492201llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{2llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{11509718810875827663llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{4172252624963492201llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{2llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x9fbabc4702e295cf_b};
    _PossiblyUnknownBits<64, false> rhs{0x39e6d1a82823d969_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{2llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x9fbabc4702e295cf_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x39e6d1a82823d969_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{2llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_450")
{
  // 64'7402946602167618141 / 64'3766319818443645676 = 64'1
  {
    _Bits<64, false> lhs{7402946602167618141llu};
    _Bits<64, false> rhs{3766319818443645676llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{7402946602167618141llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{3766319818443645676llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x66bc8cb65162ca5d_b};
    _PossiblyUnknownBits<64, false> rhs{0x3444a7eb88d8e2ec_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x66bc8cb65162ca5d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x3444a7eb88d8e2ec_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{1llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_451")
{
  // 64'5358238443092201757 / 64'14605238724674252267 = 64'0
  {
    _Bits<64, false> lhs{5358238443092201757llu};
    _Bits<64, false> rhs{14605238724674252267llu};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5358238443092201757llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{14605238724674252267llu}, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4a5c49798e5a511d_b};
    _PossiblyUnknownBits<64, false> rhs{0xcab03b3cfbfcedeb_b};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4a5c49798e5a511d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xcab03b3cfbfcedeb_b, Bits<32>{64}};
    auto result = lhs / rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_452")
{
  // 64'17481181402529406630 % 64'8261242282415665387 = 64'958696837698075856
  {
    _Bits<64, false> lhs{17481181402529406630llu};
    _Bits<64, false> rhs{8261242282415665387llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{958696837698075856llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{17481181402529406630llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{8261242282415665387llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{958696837698075856llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xf299a1ddc7ee1ea6_b};
    _PossiblyUnknownBits<64, false> rhs{0x72a5d415fed2b0eb_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{958696837698075856llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf299a1ddc7ee1ea6_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x72a5d415fed2b0eb_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{958696837698075856llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_453")
{
  // 64'13152441023505763610 % 64'17732814064330520310 = 64'13152441023505763610
  {
    _Bits<64, false> lhs{13152441023505763610llu};
    _Bits<64, false> rhs{17732814064330520310llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{13152441023505763610llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{13152441023505763610llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17732814064330520310llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{13152441023505763610llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xb686db6d1f560d1a_b};
    _PossiblyUnknownBits<64, false> rhs{0xf6179c706478b6f6_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{13152441023505763610llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xb686db6d1f560d1a_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf6179c706478b6f6_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{13152441023505763610llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_454")
{
  // 64'14113894628620328697 % 64'6800793116467478864 = 64'512308395685370969
  {
    _Bits<64, false> lhs{14113894628620328697llu};
    _Bits<64, false> rhs{6800793116467478864llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{512308395685370969llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{14113894628620328697llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{6800793116467478864llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{512308395685370969llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc3dea062d8355ef9_b};
    _PossiblyUnknownBits<64, false> rhs{0x5e61454ea9f74150_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{512308395685370969llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc3dea062d8355ef9_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5e61454ea9f74150_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{512308395685370969llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_455")
{
  // 64'2633438433826137145 % 64'15211605953483065724 = 64'2633438433826137145
  {
    _Bits<64, false> lhs{2633438433826137145llu};
    _Bits<64, false> rhs{15211605953483065724llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2633438433826137145llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2633438433826137145llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15211605953483065724llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2633438433826137145llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x248bda4d92116439_b};
    _PossiblyUnknownBits<64, false> rhs{0xd31a7b052893497c_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2633438433826137145llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x248bda4d92116439_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd31a7b052893497c_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2633438433826137145llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_456")
{
  // 64'10819024374062935362 % 64'14896288609971008183 = 64'10819024374062935362
  {
    _Bits<64, false> lhs{10819024374062935362llu};
    _Bits<64, false> rhs{14896288609971008183llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{10819024374062935362llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{10819024374062935362llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{14896288609971008183llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{10819024374062935362llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x9624e558b8506d42_b};
    _PossiblyUnknownBits<64, false> rhs{0xceba3f911d04f2b7_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{10819024374062935362llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x9624e558b8506d42_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xceba3f911d04f2b7_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{10819024374062935362llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_457")
{
  // 64'226129869102155848 % 64'15510226352002680665 = 64'226129869102155848
  {
    _Bits<64, false> lhs{226129869102155848llu};
    _Bits<64, false> rhs{15510226352002680665llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{226129869102155848llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{226129869102155848llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15510226352002680665llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{226129869102155848llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x3235feaf8f08848_b};
    _PossiblyUnknownBits<64, false> rhs{0xd73f64b0c105c759_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{226129869102155848llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x3235feaf8f08848_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xd73f64b0c105c759_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{226129869102155848llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_458")
{
  // 64'11276532167251579089 % 64'17708613549874262237 = 64'11276532167251579089
  {
    _Bits<64, false> lhs{11276532167251579089llu};
    _Bits<64, false> rhs{17708613549874262237llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{11276532167251579089llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{11276532167251579089llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17708613549874262237llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{11276532167251579089llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x9c7e4a42af4bd0d1_b};
    _PossiblyUnknownBits<64, false> rhs{0xf5c1a23308ecb0dd_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{11276532167251579089llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x9c7e4a42af4bd0d1_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf5c1a23308ecb0dd_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{11276532167251579089llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_459")
{
  // 64'8661415091934179552 % 64'6971070159124922367 = 64'1690344932809257185
  {
    _Bits<64, false> lhs{8661415091934179552llu};
    _Bits<64, false> rhs{6971070159124922367llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{1690344932809257185llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{8661415091934179552llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{6971070159124922367llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{1690344932809257185llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x78338722cef1b0e0_b};
    _PossiblyUnknownBits<64, false> rhs{0x60be37601af77fff_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{1690344932809257185llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x78338722cef1b0e0_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x60be37601af77fff_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{1690344932809257185llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_460")
{
  // 64'8329714267503192008 % 64'12128840421186262783 = 64'8329714267503192008
  {
    _Bits<64, false> lhs{8329714267503192008llu};
    _Bits<64, false> rhs{12128840421186262783llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{8329714267503192008llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{8329714267503192008llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12128840421186262783llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{8329714267503192008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x739916fe5b07e7c8_b};
    _PossiblyUnknownBits<64, false> rhs{0xa8524c1a0a34d6ff_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{8329714267503192008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x739916fe5b07e7c8_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xa8524c1a0a34d6ff_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{8329714267503192008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_461")
{
  // 64'2247475723620437624 % 64'17168017027168575779 = 64'2247475723620437624
  {
    _Bits<64, false> lhs{2247475723620437624llu};
    _Bits<64, false> rhs{17168017027168575779llu};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2247475723620437624llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2247475723620437624llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{17168017027168575779llu}, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2247475723620437624llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x1f30a34353b5ce78_b};
    _PossiblyUnknownBits<64, false> rhs{0xee410c86b23da123_b};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2247475723620437624llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x1f30a34353b5ce78_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xee410c86b23da123_b, Bits<32>{64}};
    auto result = lhs % rhs;
    auto expected = _Bits<64, false>{2247475723620437624llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_462")
{
  // 64'10440826240205142330 >> 64'26 = 64'155580434802
  {
    _Bits<64, false> lhs{10440826240205142330llu};
    _Bits<64, false> rhs{26llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{155580434802llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{10440826240205142330llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{26llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{155580434802llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x90e54425c901393a_b};
    _PossiblyUnknownBits<64, false> rhs{0x1a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{155580434802llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x90e54425c901393a_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x1a_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{155580434802llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_463")
{
  // 64'5432875977445311319 >> 64'64 = 64'0
  {
    _Bits<64, false> lhs{5432875977445311319llu};
    _Bits<64, false> rhs{64llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5432875977445311319llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{64llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4b6573eab8618357_b};
    _PossiblyUnknownBits<64, false> rhs{0x40_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4b6573eab8618357_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x40_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
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
TEST_CASE("bits_464")
{
  // 64'15482798253716381907 >> 64'58 = 64'53
  {
    _Bits<64, false> lhs{15482798253716381907llu};
    _Bits<64, false> rhs{58llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{53llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{15482798253716381907llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{58llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{53llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xd6ddf2faf9cda0d3_b};
    _PossiblyUnknownBits<64, false> rhs{0x3a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{53llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xd6ddf2faf9cda0d3_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x3a_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{53llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_465")
{
  // 64'5280320674610990181 >> 64'101 = 64'0
  {
    _Bits<64, false> lhs{5280320674610990181llu};
    _Bits<64, false> rhs{101llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{5280320674610990181llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{101llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x494777ad5e56cc65_b};
    _PossiblyUnknownBits<64, false> rhs{0x65_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x494777ad5e56cc65_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x65_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_466")
{
  // 64'14478666359383237514 >> 64'87 = 64'0
  {
    _Bits<64, false> lhs{14478666359383237514llu};
    _Bits<64, false> rhs{87llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{14478666359383237514llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{87llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xc8ee8e57b46fa38a_b};
    _PossiblyUnknownBits<64, false> rhs{0x57_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xc8ee8e57b46fa38a_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x57_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_467")
{
  // 64'7632355301130892041 >> 64'21 = 64'3639390612187
  {
    _Bits<64, false> lhs{7632355301130892041llu};
    _Bits<64, false> rhs{21llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{3639390612187llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7632355301130892041llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{21llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{3639390612187llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x69eb92b55b79f309_b};
    _PossiblyUnknownBits<64, false> rhs{0x15_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{3639390612187llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x69eb92b55b79f309_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x15_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{3639390612187llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_468")
{
  // 64'8582070131319343532 >> 64'122 = 64'0
  {
    _Bits<64, false> lhs{8582070131319343532llu};
    _Bits<64, false> rhs{122llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{8582070131319343532llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{122llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x7719a3508ec789ac_b};
    _PossiblyUnknownBits<64, false> rhs{0x7a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x7719a3508ec789ac_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x7a_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_469")
{
  // 64'17893845215956448370 >> 64'33 = 64'2083117749
  {
    _Bits<64, false> lhs{17893845215956448370llu};
    _Bits<64, false> rhs{33llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{2083117749llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{17893845215956448370llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{33llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{2083117749llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xf853b56b12e83472_b};
    _PossiblyUnknownBits<64, false> rhs{0x21_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{2083117749llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xf853b56b12e83472_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x21_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{2083117749llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_470")
{
  // 64'3979921870520613867 >> 64'16 = 64'60728788307504
  {
    _Bits<64, false> lhs{3979921870520613867llu};
    _Bits<64, false> rhs{16llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{60728788307504llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3979921870520613867llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{60728788307504llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x373b85dace307beb_b};
    _PossiblyUnknownBits<64, false> rhs{0x10_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{60728788307504llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x373b85dace307beb_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x10_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{60728788307504llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_471")
{
  // 64'407686112715034851 >> 64'10 = 64'398130969448276
  {
    _Bits<64, false> lhs{407686112715034851llu};
    _Bits<64, false> rhs{10llu};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{398130969448276llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{407686112715034851llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{10llu}, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{398130969448276llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x5a8645c083d50e3_b};
    _PossiblyUnknownBits<64, false> rhs{0xa_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{398130969448276llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5a8645c083d50e3_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xa_b, Bits<32>{64}};
    auto result = lhs >> rhs;
    auto expected = _Bits<64, false>{398130969448276llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_472")
{
  // 64'6627502221026677820 >>> 64'86 = 64'0
  {
    _Bits<64, false> lhs{6627502221026677820llu};
    _Bits<64, false> rhs{86llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{6627502221026677820llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{86llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x5bf99e27f068543c_b};
    _PossiblyUnknownBits<64, false> rhs{0x56_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5bf99e27f068543c_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x56_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_473")
{
  // 64'1146919884445348322 >>> 64'88 = 64'0
  {
    _Bits<64, false> lhs{1146919884445348322llu};
    _Bits<64, false> rhs{88llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{1146919884445348322llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{88llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xfeaad8eea3271e2_b};
    _PossiblyUnknownBits<64, false> rhs{0x58_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xfeaad8eea3271e2_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x58_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_474")
{
  // 64'5293706533100762537 >>> 64'85 = 64'0
  {
    _Bits<64, false> lhs{5293706533100762537llu};
    _Bits<64, false> rhs{85llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{5293706533100762537llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{85llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x4977060b6aa2b5a9_b};
    _PossiblyUnknownBits<64, false> rhs{0x55_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4977060b6aa2b5a9_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x55_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_475")
{
  // 64'7654033706035494025 >>> 64'76 = 64'0
  {
    _Bits<64, false> lhs{7654033706035494025llu};
    _Bits<64, false> rhs{76llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7654033706035494025llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{76llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6a38971a531cbc89_b};
    _PossiblyUnknownBits<64, false> rhs{0x4c_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6a38971a531cbc89_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x4c_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_476")
{
  // 64'6808667372384569483 >>> 64'21 = 64'3246625600998
  {
    _Bits<64, false> lhs{6808667372384569483llu};
    _Bits<64, false> rhs{21llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{3246625600998llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{6808667372384569483llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{21llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{3246625600998llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x5e7d3ee6bcc6488b_b};
    _PossiblyUnknownBits<64, false> rhs{0x15_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{3246625600998llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x5e7d3ee6bcc6488b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x15_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{3246625600998llu};
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
TEST_CASE("bits_477")
{
  // 64'2524536455840187417 >>> 64'110 = 64'0
  {
    _Bits<64, false> lhs{2524536455840187417llu};
    _Bits<64, false> rhs{110llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2524536455840187417llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{110llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2308f487f0e0c419_b};
    _PossiblyUnknownBits<64, false> rhs{0x6e_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2308f487f0e0c419_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x6e_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{0llu};
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
TEST_CASE("bits_478")
{
  // 64'5393049222619803067 >>> 64'5 = 64'168532788206868845
  {
    _Bits<64, false> lhs{5393049222619803067llu};
    _Bits<64, false> rhs{5llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{168532788206868845llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{5393049222619803067llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{5llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{168532788206868845llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x4ad7f5b1c2732dbb_b};
    _PossiblyUnknownBits<64, false> rhs{0x5_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{168532788206868845llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x4ad7f5b1c2732dbb_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{168532788206868845llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_479")
{
  // 64'10459354091436642735 >>> 64'53 = 64'18446744073709550729
  {
    _Bits<64, false> lhs{10459354091436642735llu};
    _Bits<64, false> rhs{53llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18446744073709550729llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{10459354091436642735llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{53llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18446744073709550729llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x91271721501c11af_b};
    _PossiblyUnknownBits<64, false> rhs{0x35_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18446744073709550729llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x91271721501c11af_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x35_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18446744073709550729llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_480")
{
  // 64'7983823436375068914 >>> 64'43 = 64'907655
  {
    _Bits<64, false> lhs{7983823436375068914llu};
    _Bits<64, false> rhs{43llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{907655llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7983823436375068914llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{43llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{907655llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6ecc3d1d829310f2_b};
    _PossiblyUnknownBits<64, false> rhs{0x2b_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{907655llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6ecc3d1d829310f2_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x2b_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{907655llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_481")
{
  // 64'12828436137336719142 >>> 64'12 = 64'18445372416498523092
  {
    _Bits<64, false> lhs{12828436137336719142llu};
    _Bits<64, false> rhs{12llu};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18445372416498523092llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12828436137336719142llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{12llu}, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18445372416498523092llu};
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
    _PossiblyUnknownBits<64, false> lhs{0xb207c2b2edbd4726_b};
    _PossiblyUnknownBits<64, false> rhs{0xc_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18445372416498523092llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xb207c2b2edbd4726_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xc_b, Bits<32>{64}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<64, false>{18445372416498523092llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_482")
{
  // 64'9146828166852672344 << 64'76 = 64'0
  {
    _Bits<64, false> lhs{9146828166852672344llu};
    _Bits<64, false> rhs{76llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9146828166852672344llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{76llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x7ef00fc17aca7b58_b};
    _PossiblyUnknownBits<64, false> rhs{0x4c_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x7ef00fc17aca7b58_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x4c_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_483")
{
  // 64'1797012766500905510 << 64'57 = 64'5476377146882523136
  {
    _Bits<64, false> lhs{1797012766500905510llu};
    _Bits<64, false> rhs{57llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{5476377146882523136llu};
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
    _RuntimeBits<64, false> lhs{Bits<64>{1797012766500905510llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{57llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{5476377146882523136llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x18f045971420e226_b};
    _PossiblyUnknownBits<64, false> rhs{0x39_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{5476377146882523136llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x18f045971420e226_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x39_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{5476377146882523136llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_484")
{
  // 64'3213524367755921197 << 64'102 = 64'0
  {
    _Bits<64, false> lhs{3213524367755921197llu};
    _Bits<64, false> rhs{102llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{3213524367755921197llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{102llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x2c98bb62f127472d_b};
    _PossiblyUnknownBits<64, false> rhs{0x66_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x2c98bb62f127472d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x66_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_485")
{
  // 64'5229343187360192685 << 64'9 = 64'2645821240533670400
  {
    _Bits<64, false> lhs{5229343187360192685llu};
    _Bits<64, false> rhs{9llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{2645821240533670400llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{5229343187360192685llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{9llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{2645821240533670400llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x48925bec333698ad_b};
    _PossiblyUnknownBits<64, false> rhs{0x9_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{2645821240533670400llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x48925bec333698ad_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x9_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{2645821240533670400llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_486")
{
  // 64'1766016864572746107 << 64'126 = 64'0
  {
    _Bits<64, false> lhs{1766016864572746107llu};
    _Bits<64, false> rhs{126llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{1766016864572746107llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{126llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x188226fb4835297b_b};
    _PossiblyUnknownBits<64, false> rhs{0x7e_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x188226fb4835297b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x7e_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_487")
{
  // 64'6196613679786619712 << 64'16 = 64'14650079853840171008
  {
    _Bits<64, false> lhs{6196613679786619712llu};
    _Bits<64, false> rhs{16llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14650079853840171008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{6196613679786619712llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14650079853840171008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x55fecb4f8a01f340_b};
    _PossiblyUnknownBits<64, false> rhs{0x10_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14650079853840171008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x55fecb4f8a01f340_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x10_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14650079853840171008llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_488")
{
  // 64'2094005791217449096 << 64'16 = 64'7434368901389484032
  {
    _Bits<64, false> lhs{2094005791217449096llu};
    _Bits<64, false> rhs{16llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{7434368901389484032llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2094005791217449096llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{16llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{7434368901389484032llu};
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
    _PossiblyUnknownBits<64, false> lhs{0x1d0f672c2f207888_b};
    _PossiblyUnknownBits<64, false> rhs{0x10_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{7434368901389484032llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x1d0f672c2f207888_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x10_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{7434368901389484032llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_489")
{
  // 64'9329121873530426030 << 64'111 = 64'0
  {
    _Bits<64, false> lhs{9329121873530426030llu};
    _Bits<64, false> rhs{111llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9329121873530426030llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{111llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x8177b2ea8a1b92ae_b};
    _PossiblyUnknownBits<64, false> rhs{0x6f_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x8177b2ea8a1b92ae_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x6f_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{0llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_490")
{
  // 64'2467777390395153983 << 64'39 = 64'11470421410552217600
  {
    _Bits<64, false> lhs{2467777390395153983llu};
    _Bits<64, false> rhs{39llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{11470421410552217600llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{2467777390395153983llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{39llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{11470421410552217600llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x223f4e76333e5e3f_b};
    _PossiblyUnknownBits<64, false> rhs{0x27_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{11470421410552217600llu};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x223f4e76333e5e3f_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x27_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{11470421410552217600llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_491")
{
  // 64'14936638678389191035 << 64'0 = 64'14936638678389191035
  {
    _Bits<64, false> lhs{14936638678389191035llu};
    _Bits<64, false> rhs{0llu};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14936638678389191035llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{14936638678389191035llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{0llu}, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14936638678389191035llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xcf4999bd83bf717b_b};
    _PossiblyUnknownBits<64, false> rhs{0x0_b};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14936638678389191035llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xcf4999bd83bf717b_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x0_b, Bits<32>{64}};
    auto result = lhs << rhs;
    auto expected = _Bits<64, false>{14936638678389191035llu};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_492")
{
  // 64'12455000978737783322 `<< 64'95 = 159'493393420829379240306920941648378885019948548096
  {
    _Bits<64, false> lhs{12455000978737783322llu};
    _Bits<64, false> rhs{95llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<159, false>{493393420829379240306920941648378885019948548096_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12455000978737783322llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{95llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<159, false>{493393420829379240306920941648378885019948548096_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xacd90d6696cee21a_b};
    _PossiblyUnknownBits<64, false> rhs{0x5f_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<159, false>{493393420829379240306920941648378885019948548096_mpz};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xacd90d6696cee21a_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5f_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<159, false>{493393420829379240306920941648378885019948548096_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_493")
{
  // 64'9720257566191347085 `<< 64'5 = 69'311048242118123106720
  {
    _Bits<64, false> lhs{9720257566191347085llu};
    _Bits<64, false> rhs{5llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<69, false>{311048242118123106720_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{9720257566191347085llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{5llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<69, false>{311048242118123106720_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x86e54ac19e23658d_b};
    _PossiblyUnknownBits<64, false> rhs{0x5_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<69, false>{311048242118123106720_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x86e54ac19e23658d_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<69, false>{311048242118123106720_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_494")
{
  // 64'1015262587125100534 `<< 64'51 = 115'2286168104529904247369701032722432
  {
    _Bits<64, false> lhs{1015262587125100534llu};
    _Bits<64, false> rhs{51llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<115, false>{2286168104529904247369701032722432_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{1015262587125100534llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{51llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<115, false>{2286168104529904247369701032722432_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xe16eff1a355eff6_b};
    _PossiblyUnknownBits<64, false> rhs{0x33_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<115, false>{2286168104529904247369701032722432_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xe16eff1a355eff6_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x33_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<115, false>{2286168104529904247369701032722432_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_495")
{
  // 64'12350915607702870584 `<< 64'22 = 86'51803494737050580901953536
  {
    _Bits<64, false> lhs{12350915607702870584llu};
    _Bits<64, false> rhs{22llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<86, false>{51803494737050580901953536_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12350915607702870584llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{22llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<86, false>{51803494737050580901953536_u128};
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
    _PossiblyUnknownBits<64, false> lhs{0xab67444ea7f51a38_b};
    _PossiblyUnknownBits<64, false> rhs{0x16_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<86, false>{51803494737050580901953536_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xab67444ea7f51a38_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x16_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<86, false>{51803494737050580901953536_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_496")
{
  // 64'3844505653124554262 `<< 64'15 = 79'125976761241585394057216
  {
    _Bits<64, false> lhs{3844505653124554262llu};
    _Bits<64, false> rhs{15llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<79, false>{125976761241585394057216_u128};
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
    _RuntimeBits<64, false> lhs{Bits<64>{3844505653124554262llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{15llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<79, false>{125976761241585394057216_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x355a6d85bf785e16_b};
    _PossiblyUnknownBits<64, false> rhs{0xf_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<79, false>{125976761241585394057216_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x355a6d85bf785e16_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0xf_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<79, false>{125976761241585394057216_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_497")
{
  // 64'978970339085644293 `<< 64'69 = 133'577882089627697250796745992303978479616
  {
    _Bits<64, false> lhs{978970339085644293llu};
    _Bits<64, false> rhs{69llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<133, false>{577882089627697250796745992303978479616_mpz};
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
    _RuntimeBits<64, false> lhs{Bits<64>{978970339085644293llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{69llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<133, false>{577882089627697250796745992303978479616_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xd9600562ad7f205_b};
    _PossiblyUnknownBits<64, false> rhs{0x45_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<133, false>{577882089627697250796745992303978479616_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xd9600562ad7f205_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x45_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<133, false>{577882089627697250796745992303978479616_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_498")
{
  // 64'12578811803643031725 `<< 64'44 = 108'221288797467384196780709747097600
  {
    _Bits<64, false> lhs{12578811803643031725llu};
    _Bits<64, false> rhs{44llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<108, false>{221288797467384196780709747097600_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{12578811803643031725llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{44llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<108, false>{221288797467384196780709747097600_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0xae90eab0a4a230ad_b};
    _PossiblyUnknownBits<64, false> rhs{0x2c_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<108, false>{221288797467384196780709747097600_u128};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xae90eab0a4a230ad_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x2c_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<108, false>{221288797467384196780709747097600_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_499")
{
  // 64'7916774412827035387 `<< 64'96 = 160'627231489768229986910981901879418872099642540032
  {
    _Bits<64, false> lhs{7916774412827035387llu};
    _Bits<64, false> rhs{96llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<160, false>{627231489768229986910981901879418872099642540032_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<64, false> lhs{Bits<64>{7916774412827035387llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{96llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<160, false>{627231489768229986910981901879418872099642540032_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x6dde0862337506fb_b};
    _PossiblyUnknownBits<64, false> rhs{0x60_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<160, false>{627231489768229986910981901879418872099642540032_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x6dde0862337506fb_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x60_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<160, false>{627231489768229986910981901879418872099642540032_mpz};
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
TEST_CASE("bits_500")
{
  // 64'8083503741482503523 `<< 64'74 = 138'152693068531713391860544333608417631404032
  {
    _Bits<64, false> lhs{8083503741482503523llu};
    _Bits<64, false> rhs{74llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<138, false>{152693068531713391860544333608417631404032_mpz};
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
    _RuntimeBits<64, false> lhs{Bits<64>{8083503741482503523llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{74llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<138, false>{152693068531713391860544333608417631404032_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<64, false> lhs{0x702e5fd31b9b0d63_b};
    _PossiblyUnknownBits<64, false> rhs{0x4a_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<138, false>{152693068531713391860544333608417631404032_mpz};
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
    _PossiblyUnknownRuntimeBits<64, false> lhs{0x702e5fd31b9b0d63_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x4a_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<138, false>{152693068531713391860544333608417631404032_mpz};
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
TEST_CASE("bits_501")
{
  // 64'16980490702531215538 `<< 64'91 = 155'42041658654753054932879014583680182836761985024
  {
    _Bits<64, false> lhs{16980490702531215538llu};
    _Bits<64, false> rhs{91llu};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<155, false>{42041658654753054932879014583680182836761985024_mpz};
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
    _RuntimeBits<64, false> lhs{Bits<64>{16980490702531215538llu}, Bits<32>{64}};
    _RuntimeBits<64, false> rhs{Bits<64>{91llu}, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<155, false>{42041658654753054932879014583680182836761985024_mpz};
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
    _PossiblyUnknownBits<64, false> lhs{0xeba6d253d43240b2_b};
    _PossiblyUnknownBits<64, false> rhs{0x5b_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<155, false>{42041658654753054932879014583680182836761985024_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<64, false> lhs{0xeba6d253d43240b2_b, Bits<32>{64}};
    _PossiblyUnknownRuntimeBits<64, false> rhs{0x5b_b, Bits<32>{64}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<155, false>{42041658654753054932879014583680182836761985024_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
