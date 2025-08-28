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
TEST_CASE("bits_502")
{
  // 128'223677343346409984248291487262230009675 + 128'119067729999140149943043750494688571977 = 128'2462706424611670727960630325150370196
  {
    _Bits<128, false> lhs{223677343346409984248291487262230009675_u128};
    _Bits<128, false> rhs{119067729999140149943043750494688571977_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{2462706424611670727960630325150370196_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{223677343346409984248291487262230009675_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{119067729999140149943043750494688571977_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{2462706424611670727960630325150370196_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xa846b078cb7d4cc54f034fee4aa5574b_b};
    _PossiblyUnknownBits<128, false> rhs{0x59939c5450d342321f365687a724f249_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{2462706424611670727960630325150370196_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa846b078cb7d4cc54f034fee4aa5574b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x59939c5450d342321f365687a724f249_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{2462706424611670727960630325150370196_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_503")
{
  // 128'26424295694728886310902708834139112302 + 128'81073179215118231263166509555280503422 = 128'107497474909847117574069218389419615724
  {
    _Bits<128, false> lhs{26424295694728886310902708834139112302_u128};
    _Bits<128, false> rhs{81073179215118231263166509555280503422_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{107497474909847117574069218389419615724_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{26424295694728886310902708834139112302_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{81073179215118231263166509555280503422_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{107497474909847117574069218389419615724_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x13e1225d25282c12bca13b429b50036e_b};
    _PossiblyUnknownBits<128, false> rhs{0x3cfe2058b76ee3d60467dd0f964fe27e_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{107497474909847117574069218389419615724_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x13e1225d25282c12bca13b429b50036e_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3cfe2058b76ee3d60467dd0f964fe27e_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{107497474909847117574069218389419615724_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_504")
{
  // 128'35072068875040263877390110969926046699 + 128'291721632714986527148806563906270393321 = 128'326793701590026791026196674876196440020
  {
    _Bits<128, false> lhs{35072068875040263877390110969926046699_u128};
    _Bits<128, false> rhs{291721632714986527148806563906270393321_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{326793701590026791026196674876196440020_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{35072068875040263877390110969926046699_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{291721632714986527148806563906270393321_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{326793701590026791026196674876196440020_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x1a62a2800305c81d992b411f8160d3eb_b};
    _PossiblyUnknownBits<128, false> rhs{0xdb778af418f7e9d139815d90ad15f3e9_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{326793701590026791026196674876196440020_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x1a62a2800305c81d992b411f8160d3eb_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xdb778af418f7e9d139815d90ad15f3e9_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{326793701590026791026196674876196440020_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_505")
{
  // 128'7485896648454135085583769035789691027 + 128'149681781922130215469397337612068094155 = 128'157167678570584350554981106647857785182
  {
    _Bits<128, false> lhs{7485896648454135085583769035789691027_u128};
    _Bits<128, false> rhs{149681781922130215469397337612068094155_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{157167678570584350554981106647857785182_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{7485896648454135085583769035789691027_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{149681781922130215469397337612068094155_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{157167678570584350554981106647857785182_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x5a1bb334dc8f2c5e038d2b019b1e893_b};
    _PossiblyUnknownBits<128, false> rhs{0x709ba99fb70860349a9dca5a2bcc80cb_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{157167678570584350554981106647857785182_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x5a1bb334dc8f2c5e038d2b019b1e893_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x709ba99fb70860349a9dca5a2bcc80cb_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{157167678570584350554981106647857785182_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_506")
{
  // 128'82493306758652327126004136010879713321 + 128'213443847156684673203567299024571492000 = 128'295937153915337000329571435035451205321
  {
    _Bits<128, false> lhs{82493306758652327126004136010879713321_u128};
    _Bits<128, false> rhs{213443847156684673203567299024571492000_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{295937153915337000329571435035451205321_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{82493306758652327126004136010879713321_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{213443847156684673203567299024571492000_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{295937153915337000329571435035451205321_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x3e0fa20a4f12d99181acdec950ddc029_b};
    _PossiblyUnknownBits<128, false> rhs{0xa093ca27b5c53e0ca13ee5c853ee66a0_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{295937153915337000329571435035451205321_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3e0fa20a4f12d99181acdec950ddc029_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa093ca27b5c53e0ca13ee5c853ee66a0_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{295937153915337000329571435035451205321_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_507")
{
  // 128'29082280558084320439348441581309857214 + 128'136616362947671244562816711995953199810 = 128'165698643505755565002165153577263057024
  {
    _Bits<128, false> lhs{29082280558084320439348441581309857214_u128};
    _Bits<128, false> rhs{136616362947671244562816711995953199810_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{165698643505755565002165153577263057024_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{29082280558084320439348441581309857214_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{136616362947671244562816711995953199810_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{165698643505755565002165153577263057024_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x15e10b22abcb321b12ff98247f6f0dbe_b};
    _PossiblyUnknownBits<128, false> rhs{0x66c75abbe2ed741f4cfdc42f139f3ac2_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{165698643505755565002165153577263057024_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x15e10b22abcb321b12ff98247f6f0dbe_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x66c75abbe2ed741f4cfdc42f139f3ac2_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{165698643505755565002165153577263057024_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_508")
{
  // 128'336887431264774793529183965587363593953 + 128'185288201008356968795285248726906936965 = 128'181893265352193298861094606882502319462
  {
    _Bits<128, false> lhs{336887431264774793529183965587363593953_u128};
    _Bits<128, false> rhs{185288201008356968795285248726906936965_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{181893265352193298861094606882502319462_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{336887431264774793529183965587363593953_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{185288201008356968795285248726906936965_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{181893265352193298861094606882502319462_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xfd7228bfc3046ba9c7f5fe3166f7fee1_b};
    _PossiblyUnknownBits<128, false> rhs{0x8b65359f966d3ccfe67a0366b4779e85_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{181893265352193298861094606882502319462_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xfd7228bfc3046ba9c7f5fe3166f7fee1_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x8b65359f966d3ccfe67a0366b4779e85_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{181893265352193298861094606882502319462_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_509")
{
  // 128'223991343265045384125458150129975067299 + 128'178717081134764775604118816026270274632 = 128'62426057478871696266202358724477130475
  {
    _Bits<128, false> lhs{223991343265045384125458150129975067299_u128};
    _Bits<128, false> rhs{178717081134764775604118816026270274632_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{62426057478871696266202358724477130475_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{223991343265045384125458150129975067299_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{178717081134764775604118816026270274632_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{62426057478871696266202358724477130475_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xa88329dcf4abbb1617d20ff787ca82a3_b};
    _PossiblyUnknownBits<128, false> rhs{0x8673a8667057df9724d0d0bdf1c69448_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{62426057478871696266202358724477130475_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa88329dcf4abbb1617d20ff787ca82a3_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x8673a8667057df9724d0d0bdf1c69448_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{62426057478871696266202358724477130475_u128};
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
TEST_CASE("bits_510")
{
  // 128'36782861963857377796089454062397669208 + 128'92041947858935424384225645094370365564 = 128'128824809822792802180315099156768034772
  {
    _Bits<128, false> lhs{36782861963857377796089454062397669208_u128};
    _Bits<128, false> rhs{92041947858935424384225645094370365564_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{128824809822792802180315099156768034772_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{36782861963857377796089454062397669208_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{92041947858935424384225645094370365564_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{128824809822792802180315099156768034772_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x1bac1f1c911d021e2f1fdd42327dbf58_b};
    _PossiblyUnknownBits<128, false> rhs{0x453ea264e6a009d64408a025b541507c_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{128824809822792802180315099156768034772_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x1bac1f1c911d021e2f1fdd42327dbf58_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x453ea264e6a009d64408a025b541507c_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{128824809822792802180315099156768034772_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_511")
{
  // 128'224439495310447992998749320786516587323 + 128'291207773067441712164255315906741893118 = 128'175364901456951241699630029261490268985
  {
    _Bits<128, false> lhs{224439495310447992998749320786516587323_u128};
    _Bits<128, false> rhs{291207773067441712164255315906741893118_u128};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{175364901456951241699630029261490268985_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{224439495310447992998749320786516587323_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{291207773067441712164255315906741893118_u128}, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{175364901456951241699630029261490268985_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xa8d9797701d4c0ca18592f2b11fb333b_b};
    _PossiblyUnknownBits<128, false> rhs{0xdb1493b7829182a8ad9ccfc5a0eb77fe_b};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{175364901456951241699630029261490268985_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa8d9797701d4c0ca18592f2b11fb333b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xdb1493b7829182a8ad9ccfc5a0eb77fe_b, Bits<32>{128}};
    auto result = lhs + rhs;
    auto expected = _Bits<128, false>{175364901456951241699630029261490268985_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_512")
{
  // 128'144059059630771037934030500302086489028 `+ 128'327043924786486684678323513679312334979 = 129'471102984417257722612354013981398824007
  {
    _Bits<128, false> lhs{144059059630771037934030500302086489028_u128};
    _Bits<128, false> rhs{327043924786486684678323513679312334979_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{471102984417257722612354013981398824007_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{144059059630771037934030500302086489028_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{327043924786486684678323513679312334979_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{471102984417257722612354013981398824007_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x6c60c402f84a53f69f681bc46e6043c4_b};
    _PossiblyUnknownBits<128, false> rhs{0xf60a5e68dd985dd0d15d7e334bbc3083_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{471102984417257722612354013981398824007_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x6c60c402f84a53f69f681bc46e6043c4_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xf60a5e68dd985dd0d15d7e334bbc3083_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{471102984417257722612354013981398824007_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_513")
{
  // 128'105501546197468293618933471603069773500 `+ 128'255687128244976991778671590609979680957 = 129'361188674442445285397605062213049454457
  {
    _Bits<128, false> lhs{105501546197468293618933471603069773500_u128};
    _Bits<128, false> rhs{255687128244976991778671590609979680957_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{361188674442445285397605062213049454457_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{105501546197468293618933471603069773500_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{255687128244976991778671590609979680957_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{361188674442445285397605062213049454457_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x4f5edbd3c4d15ee9d09173ab6d6b66bc_b};
    _PossiblyUnknownBits<128, false> rhs{0xc05b8cb70d149cace6ca20f6719ba8bd_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{361188674442445285397605062213049454457_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x4f5edbd3c4d15ee9d09173ab6d6b66bc_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xc05b8cb70d149cace6ca20f6719ba8bd_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{361188674442445285397605062213049454457_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_514")
{
  // 128'251468957983943571380246113240452970077 `+ 128'103214686845490532231239103626014978157 = 129'354683644829434103611485216866467948234
  {
    _Bits<128, false> lhs{251468957983943571380246113240452970077_u128};
    _Bits<128, false> rhs{103214686845490532231239103626014978157_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{354683644829434103611485216866467948234_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{251468957983943571380246113240452970077_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{103214686845490532231239103626014978157_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{354683644829434103611485216866467948234_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0xbd2f28dd487e05ce9dee3a905e08365d_b};
    _PossiblyUnknownBits<128, false> rhs{0x4da66cf4c0a9c9426fa39e2d46dd706d_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{354683644829434103611485216866467948234_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xbd2f28dd487e05ce9dee3a905e08365d_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x4da66cf4c0a9c9426fa39e2d46dd706d_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{354683644829434103611485216866467948234_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_515")
{
  // 128'263385662677296653210266332254381080611 `+ 128'300227070083347013340526047289360441521 = 129'563612732760643666550792379543741522132
  {
    _Bits<128, false> lhs{263385662677296653210266332254381080611_u128};
    _Bits<128, false> rhs{300227070083347013340526047289360441521_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{563612732760643666550792379543741522132_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{263385662677296653210266332254381080611_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{300227070083347013340526047289360441521_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{563612732760643666550792379543741522132_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xc6263bc482735d5f22d1f7ed94c50023_b};
    _PossiblyUnknownBits<128, false> rhs{0xe1dda16471dfc08366f1e7638b52e0b1_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{563612732760643666550792379543741522132_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc6263bc482735d5f22d1f7ed94c50023_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe1dda16471dfc08366f1e7638b52e0b1_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{563612732760643666550792379543741522132_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_516")
{
  // 128'128263814497890036770493782765884031099 `+ 128'58969069168029180403713110188062722026 = 129'187232883665919217174206892953946753125
  {
    _Bits<128, false> lhs{128263814497890036770493782765884031099_u128};
    _Bits<128, false> rhs{58969069168029180403713110188062722026_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{187232883665919217174206892953946753125_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{128263814497890036770493782765884031099_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{58969069168029180403713110188062722026_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{187232883665919217174206892953946753125_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x607eb64cfd9097a9421a337da002407b_b};
    _PossiblyUnknownBits<128, false> rhs{0x2c5d07948afc3c492c3c6761dd1cc7ea_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{187232883665919217174206892953946753125_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x607eb64cfd9097a9421a337da002407b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x2c5d07948afc3c492c3c6761dd1cc7ea_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{187232883665919217174206892953946753125_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_517")
{
  // 128'311265896044133303733857397113566059058 `+ 128'270264959576113162678486244380847096222 = 129'581530855620246466412343641494413155280
  {
    _Bits<128, false> lhs{311265896044133303733857397113566059058_u128};
    _Bits<128, false> rhs{270264959576113162678486244380847096222_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{581530855620246466412343641494413155280_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{311265896044133303733857397113566059058_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{270264959576113162678486244380847096222_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{581530855620246466412343641494413155280_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0xea2ba18848ed384e869293511f40da32_b};
    _PossiblyUnknownBits<128, false> rhs{0xcb53234a925c8c763e1b37582f83c19e_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{581530855620246466412343641494413155280_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xea2ba18848ed384e869293511f40da32_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xcb53234a925c8c763e1b37582f83c19e_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{581530855620246466412343641494413155280_mpz};
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
TEST_CASE("bits_518")
{
  // 128'242806248327389912169284231454038037747 `+ 128'30455190773500971270036614559154865996 = 129'273261439100890883439320846013192903743
  {
    _Bits<128, false> lhs{242806248327389912169284231454038037747_u128};
    _Bits<128, false> rhs{30455190773500971270036614559154865996_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{273261439100890883439320846013192903743_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{242806248327389912169284231454038037747_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{30455190773500971270036614559154865996_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{273261439100890883439320846013192903743_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb6aac84d94f0f0599fde24eefbf214f3_b};
    _PossiblyUnknownBits<128, false> rhs{0x16e974d5cbd3d9a2b5426245d060874c_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{273261439100890883439320846013192903743_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb6aac84d94f0f0599fde24eefbf214f3_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x16e974d5cbd3d9a2b5426245d060874c_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{273261439100890883439320846013192903743_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_519")
{
  // 128'9964334738126414136621175189602765623 `+ 128'56180413017012564056853535165417067792 = 129'66144747755138978193474710355019833415
  {
    _Bits<128, false> lhs{9964334738126414136621175189602765623_u128};
    _Bits<128, false> rhs{56180413017012564056853535165417067792_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{66144747755138978193474710355019833415_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{9964334738126414136621175189602765623_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{56180413017012564056853535165417067792_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{66144747755138978193474710355019833415_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x77f0fa1f16ed1e1bd534e5bb96f0b37_b};
    _PossiblyUnknownBits<128, false> rhs{0x2a43f4377e1e8ad64affed913c5d1510_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{66144747755138978193474710355019833415_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x77f0fa1f16ed1e1bd534e5bb96f0b37_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x2a43f4377e1e8ad64affed913c5d1510_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{66144747755138978193474710355019833415_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_520")
{
  // 128'90788000705155373848013282657455635566 `+ 128'279689906985429763163053387846488669648 = 129'370477907690585137011066670503944305214
  {
    _Bits<128, false> lhs{90788000705155373848013282657455635566_u128};
    _Bits<128, false> rhs{279689906985429763163053387846488669648_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{370477907690585137011066670503944305214_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{90788000705155373848013282657455635566_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{279689906985429763163053387846488669648_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{370477907690585137011066670503944305214_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x444d2206b62b2171068ff6ececb0fc6e_b};
    _PossiblyUnknownBits<128, false> rhs{0xd26a51134a9320222b582108b9d3bdd0_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{370477907690585137011066670503944305214_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x444d2206b62b2171068ff6ececb0fc6e_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd26a51134a9320222b582108b9d3bdd0_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{370477907690585137011066670503944305214_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_521")
{
  // 128'278830545457527549605626511246931292697 `+ 128'142557527536747592225945239908064748607 = 129'421388072994275141831571751154996041304
  {
    _Bits<128, false> lhs{278830545457527549605626511246931292697_u128};
    _Bits<128, false> rhs{142557527536747592225945239908064748607_u128};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{421388072994275141831571751154996041304_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{278830545457527549605626511246931292697_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{142557527536747592225945239908064748607_u128}, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{421388072994275141831571751154996041304_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xd1c4cf47e2e4777b6e226ff8bc947219_b};
    _PossiblyUnknownBits<128, false> rhs{0x6b3f94c37fd3fbdb5e5825ef6f9ce43f_b};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{421388072994275141831571751154996041304_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xd1c4cf47e2e4777b6e226ff8bc947219_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x6b3f94c37fd3fbdb5e5825ef6f9ce43f_b, Bits<32>{128}};
    auto result = lhs.widening_add(rhs);
    auto expected = _Bits<129, false>{421388072994275141831571751154996041304_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_522")
{
  // 128'211274152456647894992884439178678778600 - 128'177471656786398914886452931574557238031 = 128'33802495670248980106431507604121540569
  {
    _Bits<128, false> lhs{211274152456647894992884439178678778600_u128};
    _Bits<128, false> rhs{177471656786398914886452931574557238031_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{33802495670248980106431507604121540569_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{211274152456647894992884439178678778600_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{177471656786398914886452931574557238031_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{33802495670248980106431507604121540569_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x9ef1ebf2820fc335f81820f07bd63ae8_b};
    _PossiblyUnknownBits<128, false> rhs{0x8583cc3d2d6e2538f0655742d262e30f_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{33802495670248980106431507604121540569_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x9ef1ebf2820fc335f81820f07bd63ae8_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x8583cc3d2d6e2538f0655742d262e30f_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{33802495670248980106431507604121540569_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_523")
{
  // 128'262018351448419486656061087114063471834 - 128'195046255351481288192770978077056663499 = 128'66972096096938198463290109037006808335
  {
    _Bits<128, false> lhs{262018351448419486656061087114063471834_u128};
    _Bits<128, false> rhs{195046255351481288192770978077056663499_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{66972096096938198463290109037006808335_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{262018351448419486656061087114063471834_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{195046255351481288192770978077056663499_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{66972096096938198463290109037006808335_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xc51ee61e87a61df8f536512fed1b64da_b};
    _PossiblyUnknownBits<128, false> rhs{0x92bc8ad8e7948b4e485ff52144937fcb_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{66972096096938198463290109037006808335_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc51ee61e87a61df8f536512fed1b64da_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x92bc8ad8e7948b4e485ff52144937fcb_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{66972096096938198463290109037006808335_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_524")
{
  // 128'95941908650526214364398808028615407302 - 128'54258169271773230834856962227620162197 = 128'41683739378752983529541845800995245105
  {
    _Bits<128, false> lhs{95941908650526214364398808028615407302_u128};
    _Bits<128, false> rhs{54258169271773230834856962227620162197_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{41683739378752983529541845800995245105_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{95941908650526214364398808028615407302_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{54258169271773230834856962227620162197_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{41683739378752983529541845800995245105_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x482dbd4e81c8e616b07a1516f921f6c6_b};
    _PossiblyUnknownBits<128, false> rhs{0x28d1be4870173e9e4254c6c15fc22a95_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{41683739378752983529541845800995245105_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x482dbd4e81c8e616b07a1516f921f6c6_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x28d1be4870173e9e4254c6c15fc22a95_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{41683739378752983529541845800995245105_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_525")
{
  // 128'86074090204626447923308686772119880697 - 128'61795417194443463478655433236540918772 = 128'24278673010182984444653253535578961925
  {
    _Bits<128, false> lhs{86074090204626447923308686772119880697_u128};
    _Bits<128, false> rhs{61795417194443463478655433236540918772_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{24278673010182984444653253535578961925_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{86074090204626447923308686772119880697_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{61795417194443463478655433236540918772_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{24278673010182984444653253535578961925_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x40c1444b703776e2bae0857327fd43f9_b};
    _PossiblyUnknownBits<128, false> rhs{0x2e7d5d4bf1bda49c333ef42c31198bf4_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{24278673010182984444653253535578961925_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x40c1444b703776e2bae0857327fd43f9_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x2e7d5d4bf1bda49c333ef42c31198bf4_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{24278673010182984444653253535578961925_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_526")
{
  // 128'84872199646565244253679286747882589959 - 128'73630846469063727339355973017199901888 = 128'11241353177501516914323313730682688071
  {
    _Bits<128, false> lhs{84872199646565244253679286747882589959_u128};
    _Bits<128, false> rhs{73630846469063727339355973017199901888_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{11241353177501516914323313730682688071_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{84872199646565244253679286747882589959_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{73630846469063727339355973017199901888_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{11241353177501516914323313730682688071_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x3fd9ca83dc50b29a989c9e64df800f07_b};
    _PossiblyUnknownBits<128, false> rhs{0x3764c9032a1611a168ef18bfc09efcc0_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{11241353177501516914323313730682688071_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3fd9ca83dc50b29a989c9e64df800f07_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3764c9032a1611a168ef18bfc09efcc0_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{11241353177501516914323313730682688071_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_527")
{
  // 128'249287416677140407497696301609527000193 - 128'136700002224762509348619263230809567509 = 128'112587414452377898149077038378717432684
  {
    _Bits<128, false> lhs{249287416677140407497696301609527000193_u128};
    _Bits<128, false> rhs{136700002224762509348619263230809567509_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{112587414452377898149077038378717432684_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{249287416677140407497696301609527000193_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{136700002224762509348619263230809567509_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{112587414452377898149077038378717432684_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xbb8b0292e1d6d95ed960517069e7bc81_b};
    _PossiblyUnknownBits<128, false> rhs{0x66d77677fad74c6571d86b8c88ed7115_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{112587414452377898149077038378717432684_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xbb8b0292e1d6d95ed960517069e7bc81_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x66d77677fad74c6571d86b8c88ed7115_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{112587414452377898149077038378717432684_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_528")
{
  // 128'117552042107037457505599234993103017589 - 128'167858249396246731841832416857607527197 = 128'289976159631729189127141425567263701848
  {
    _Bits<128, false> lhs{117552042107037457505599234993103017589_u128};
    _Bits<128, false> rhs{167858249396246731841832416857607527197_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{289976159631729189127141425567263701848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{117552042107037457505599234993103017589_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{167858249396246731841832416857607527197_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{289976159631729189127141425567263701848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x586fb3258dde8bcf2054c7c881c79675_b};
    _PossiblyUnknownBits<128, false> rhs{0x7e4852a914a2426fdf0355482f225b1d_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{289976159631729189127141425567263701848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x586fb3258dde8bcf2054c7c881c79675_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x7e4852a914a2426fdf0355482f225b1d_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{289976159631729189127141425567263701848_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_529")
{
  // 128'247099191259506576226322644261492780508 - 128'155600135761312848233562298014465360937 = 128'91499055498193727992760346247027419571
  {
    _Bits<128, false> lhs{247099191259506576226322644261492780508_u128};
    _Bits<128, false> rhs{155600135761312848233562298014465360937_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{91499055498193727992760346247027419571_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{247099191259506576226322644261492780508_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{155600135761312848233562298014465360937_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{91499055498193727992760346247027419571_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb9e592bb24446449734f857073606ddc_b};
    _PossiblyUnknownBits<128, false> rhs{0x750f7eff2fd9076d87dab3570e218429_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{91499055498193727992760346247027419571_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb9e592bb24446449734f857073606ddc_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x750f7eff2fd9076d87dab3570e218429_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{91499055498193727992760346247027419571_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_530")
{
  // 128'172226532029013522592241371379039457452 - 128'29856593722419874521076192325643809877 = 128'142369938306593648071165179053395647575
  {
    _Bits<128, false> lhs{172226532029013522592241371379039457452_u128};
    _Bits<128, false> rhs{29856593722419874521076192325643809877_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{142369938306593648071165179053395647575_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{172226532029013522592241371379039457452_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{29856593722419874521076192325643809877_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{142369938306593648071165179053395647575_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x81919f9f5a0b0bc248daf2410917d0ac_b};
    _PossiblyUnknownBits<128, false> rhs{0x16762bb8cf9a270c6a65684104603455_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{142369938306593648071165179053395647575_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x81919f9f5a0b0bc248daf2410917d0ac_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x16762bb8cf9a270c6a65684104603455_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{142369938306593648071165179053395647575_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_531")
{
  // 128'15334945055334459502316308917426880875 - 128'307931426420335124907001557289851456867 = 128'47685885555937798058689359059343635464
  {
    _Bits<128, false> lhs{15334945055334459502316308917426880875_u128};
    _Bits<128, false> rhs{307931426420335124907001557289851456867_u128};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{47685885555937798058689359059343635464_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{15334945055334459502316308917426880875_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{307931426420335124907001557289851456867_u128}, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{47685885555937798058689359059343635464_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb89672a34b294c1ec94d929637c816b_b};
    _PossiblyUnknownBits<128, false> rhs{0xe7a96f7cabcc60ee77ff4ef180348d63_b};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{47685885555937798058689359059343635464_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb89672a34b294c1ec94d929637c816b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe7a96f7cabcc60ee77ff4ef180348d63_b, Bits<32>{128}};
    auto result = lhs - rhs;
    auto expected = _Bits<128, false>{47685885555937798058689359059343635464_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_532")
{
  // 128'147603819452692238827723927934399977992 `- 128'286101196208188210086398250530952879072 = 129'542067357086380955668074892266983521832
  {
    _Bits<128, false> lhs{147603819452692238827723927934399977992_u128};
    _Bits<128, false> rhs{286101196208188210086398250530952879072_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{542067357086380955668074892266983521832_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{147603819452692238827723927934399977992_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{286101196208188210086398250530952879072_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{542067357086380955668074892266983521832_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x6f0b762a0a5c77de4390f5fb39b09a08_b};
    _PossiblyUnknownBits<128, false> rhs{0xd73d160a027b1514b80641940be69be0_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{542067357086380955668074892266983521832_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x6f0b762a0a5c77de4390f5fb39b09a08_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd73d160a027b1514b80641940be69be0_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{542067357086380955668074892266983521832_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_533")
{
  // 128'257219239334573515394748109063609630869 `- 128'262929844868184484498890845046645516148 = 129'674854128308265957822606478880500537633
  {
    _Bits<128, false> lhs{257219239334573515394748109063609630869_u128};
    _Bits<128, false> rhs{262929844868184484498890845046645516148_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{674854128308265957822606478880500537633_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{257219239334573515394748109063609630869_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{262929844868184484498890845046645516148_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{674854128308265957822606478880500537633_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xc1829f9fb52c59e0ae594471167bc095_b};
    _PossiblyUnknownBits<128, false> rhs{0xc5ce7236ead961c956f381b17a40e774_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{674854128308265957822606478880500537633_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc1829f9fb52c59e0ae594471167bc095_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xc5ce7236ead961c956f381b17a40e774_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{674854128308265957822606478880500537633_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_534")
{
  // 128'268072181172321647720182260879631777516 `- 128'255309539862879941413222811547974393136 = 129'12762641309441706306959449331657384380
  {
    _Bits<128, false> lhs{268072181172321647720182260879631777516_u128};
    _Bits<128, false> rhs{255309539862879941413222811547974393136_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{12762641309441706306959449331657384380_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{268072181172321647720182260879631777516_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{255309539862879941413222811547974393136_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{12762641309441706306959449331657384380_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xc9acd2f811133baab3dd02bc5b86feec_b};
    _PossiblyUnknownBits<128, false> rhs{0xc012d42ba508aacf29fac74c3e525d30_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{12762641309441706306959449331657384380_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc9acd2f811133baab3dd02bc5b86feec_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xc012d42ba508aacf29fac74c3e525d30_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{12762641309441706306959449331657384380_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_535")
{
  // 128'325891927006346136070610128312411189196 `- 128'23304601054947011566891784748103919110 = 129'302587325951399124503718343564307270086
  {
    _Bits<128, false> lhs{325891927006346136070610128312411189196_u128};
    _Bits<128, false> rhs{23304601054947011566891784748103919110_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{302587325951399124503718343564307270086_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{325891927006346136070610128312411189196_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{23304601054947011566891784748103919110_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{302587325951399124503718343564307270086_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xf52c8088addbfab804d42baa85056fcc_b};
    _PossiblyUnknownBits<128, false> rhs{0x11884d8af1bf010588c3bb5951d06606_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{302587325951399124503718343564307270086_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf52c8088addbfab804d42baa85056fcc_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x11884d8af1bf010588c3bb5951d06606_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{302587325951399124503718343564307270086_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_536")
{
  // 128'178939607173959550553211379527777236464 `- 128'230317263846712936176024627595797348009 = 129'629187077169123541303935966795516311367
  {
    _Bits<128, false> lhs{178939607173959550553211379527777236464_u128};
    _Bits<128, false> rhs{230317263846712936176024627595797348009_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{629187077169123541303935966795516311367_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{178939607173959550553211379527777236464_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{230317263846712936176024627595797348009_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{629187077169123541303935966795516311367_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x869e83c7ec1a01a29f4af6530bb7b5f0_b};
    _PossiblyUnknownBits<128, false> rhs{0xad457dd3f0354d386de9433c40ec3ea9_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{629187077169123541303935966795516311367_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x869e83c7ec1a01a29f4af6530bb7b5f0_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xad457dd3f0354d386de9433c40ec3ea9_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{629187077169123541303935966795516311367_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_537")
{
  // 128'33675194002292941351867698952194949464 `- 128'181802246484754537239874707565285706022 = 129'532437681359415331038742206250445666354
  {
    _Bits<128, false> lhs{33675194002292941351867698952194949464_u128};
    _Bits<128, false> rhs{181802246484754537239874707565285706022_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{532437681359415331038742206250445666354_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{33675194002292941351867698952194949464_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{181802246484754537239874707565285706022_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{532437681359415331038742206250445666354_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x19559b4062e2b807e82a87b751cb0158_b};
    _PossiblyUnknownBits<128, false> rhs{0x88c5d6cbbb17c7cb28d8fd77052f8926_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{532437681359415331038742206250445666354_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x19559b4062e2b807e82a87b751cb0158_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x88c5d6cbbb17c7cb28d8fd77052f8926_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{532437681359415331038742206250445666354_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_538")
{
  // 128'24318251669277751955792308273163097731 `- 128'156977733515244514849087082152130144768 = 129'547905251995910164033454440984569375875
  {
    _Bits<128, false> lhs{24318251669277751955792308273163097731_u128};
    _Bits<128, false> rhs{156977733515244514849087082152130144768_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{547905251995910164033454440984569375875_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{24318251669277751955792308273163097731_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{156977733515244514849087082152130144768_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{547905251995910164033454440984569375875_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x124b8660674bdbcfb97b50b8fce95683_b};
    _PossiblyUnknownBits<128, false> rhs{0x7618cfcf5db5e66ca0be158013e26a00_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{547905251995910164033454440984569375875_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x124b8660674bdbcfb97b50b8fce95683_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x7618cfcf5db5e66ca0be158013e26a00_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{547905251995910164033454440984569375875_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_539")
{
  // 128'235968545445363905796722284436065783248 `- 128'150670644593970459706307140938551637587 = 129'85297900851393446090415143497514145661
  {
    _Bits<128, false> lhs{235968545445363905796722284436065783248_u128};
    _Bits<128, false> rhs{150670644593970459706307140938551637587_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{85297900851393446090415143497514145661_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{235968545445363905796722284436065783248_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{150670644593970459706307140938551637587_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{85297900851393446090415143497514145661_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb185e385d1c7106ec2dab8ff780e8dd0_b};
    _PossiblyUnknownBits<128, false> rhs{0x715a1c515aa8033b20a51e96a701b653_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{85297900851393446090415143497514145661_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb185e385d1c7106ec2dab8ff780e8dd0_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x715a1c515aa8033b20a51e96a701b653_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{85297900851393446090415143497514145661_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_540")
{
  // 128'315541457999917776090024342281564046877 `- 128'188148760802612269962400530661721499218 = 129'127392697197305506127623811619842547659
  {
    _Bits<128, false> lhs{315541457999917776090024342281564046877_u128};
    _Bits<128, false> rhs{188148760802612269962400530661721499218_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{127392697197305506127623811619842547659_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{315541457999917776090024342281564046877_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{188148760802612269962400530661721499218_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{127392697197305506127623811619842547659_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0xed63130314c770d9847cc6fe10cdc61d_b};
    _PossiblyUnknownBits<128, false> rhs{0x8d8c221c3515e67f7cf088636d77e652_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{127392697197305506127623811619842547659_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xed63130314c770d9847cc6fe10cdc61d_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x8d8c221c3515e67f7cf088636d77e652_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{127392697197305506127623811619842547659_mpz};
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
TEST_CASE("bits_541")
{
  // 128'196206400508794901145356013577481970042 `- 128'48968311946060298114709920247910282371 = 129'147238088562734603030646093329571687671
  {
    _Bits<128, false> lhs{196206400508794901145356013577481970042_u128};
    _Bits<128, false> rhs{48968311946060298114709920247910282371_u128};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{147238088562734603030646093329571687671_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{196206400508794901145356013577481970042_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{48968311946060298114709920247910282371_u128}, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{147238088562734603030646093329571687671_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x939bfa6b72c9a5ad995fbfd277cb617a_b};
    _PossiblyUnknownBits<128, false> rhs{0x24d6f42e38fde66bbafcca30c054b483_b};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{147238088562734603030646093329571687671_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x939bfa6b72c9a5ad995fbfd277cb617a_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x24d6f42e38fde66bbafcca30c054b483_b, Bits<32>{128}};
    auto result = lhs.widening_sub(rhs);
    auto expected = _Bits<129, false>{147238088562734603030646093329571687671_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_542")
{
  // 128'329696000537917208566894343358445114662 * 128'223986689067263398779999303492741902621 = 128'94730945242461068813493513741057747790
  {
    _Bits<128, false> lhs{329696000537917208566894343358445114662_u128};
    _Bits<128, false> rhs{223986689067263398779999303492741902621_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{94730945242461068813493513741057747790_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{329696000537917208566894343358445114662_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{223986689067263398779999303492741902621_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{94730945242461068813493513741057747790_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xf80923d6e9d5b2c9011a78392171d526_b};
    _PossiblyUnknownBits<128, false> rhs{0xa8824464b88f7c37b588fa8544bc311d_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{94730945242461068813493513741057747790_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf80923d6e9d5b2c9011a78392171d526_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa8824464b88f7c37b588fa8544bc311d_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{94730945242461068813493513741057747790_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_543")
{
  // 128'74520670084280699008917392816519084881 * 128'287531667429301045869255672904854492999 = 128'9536986224587752977897683508120566391
  {
    _Bits<128, false> lhs{74520670084280699008917392816519084881_u128};
    _Bits<128, false> rhs{287531667429301045869255672904854492999_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{9536986224587752977897683508120566391_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{74520670084280699008917392816519084881_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{287531667429301045869255672904854492999_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{9536986224587752977897683508120566391_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x381028b42a7164a1b6ac36b3c61d7b51_b};
    _PossiblyUnknownBits<128, false> rhs{0xd85095b72af2ace363d8f4402e1f5747_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{9536986224587752977897683508120566391_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x381028b42a7164a1b6ac36b3c61d7b51_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd85095b72af2ace363d8f4402e1f5747_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{9536986224587752977897683508120566391_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_544")
{
  // 128'94768248863846112978564539280918898583 * 128'263352280818903035885782136643234987913 = 128'11798097846798811997278972411106678991
  {
    _Bits<128, false> lhs{94768248863846112978564539280918898583_u128};
    _Bits<128, false> rhs{263352280818903035885782136643234987913_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{11798097846798811997278972411106678991_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{94768248863846112978564539280918898583_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{263352280818903035885782136643234987913_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{11798097846798811997278972411106678991_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x474bb3695bedff2994f12dcd2cf4e797_b};
    _PossiblyUnknownBits<128, false> rhs{0xc61fcdea38992c866a657e77656a7f89_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{11798097846798811997278972411106678991_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x474bb3695bedff2994f12dcd2cf4e797_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xc61fcdea38992c866a657e77656a7f89_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{11798097846798811997278972411106678991_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_545")
{
  // 128'48970263316082783092583780525117425723 * 128'320911904035135891141431402929443452044 = 128'87166352554581710873345443836573613124
  {
    _Bits<128, false> lhs{48970263316082783092583780525117425723_u128};
    _Bits<128, false> rhs{320911904035135891141431402929443452044_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{87166352554581710873345443836573613124_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{48970263316082783092583780525117425723_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{320911904035135891141431402929443452044_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{87166352554581710873345443836573613124_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x24d75463f9986ab4c3434be72fba483b_b};
    _PossiblyUnknownBits<128, false> rhs{0xf16d6271d04e23db46c2a0ba647e348c_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{87166352554581710873345443836573613124_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x24d75463f9986ab4c3434be72fba483b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xf16d6271d04e23db46c2a0ba647e348c_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{87166352554581710873345443836573613124_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_546")
{
  // 128'197873621611198397411381217896434507305 * 128'22488374978756237103319295816187492305 = 128'85146482200471605274516882717860621945
  {
    _Bits<128, false> lhs{197873621611198397411381217896434507305_u128};
    _Bits<128, false> rhs{22488374978756237103319295816187492305_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{85146482200471605274516882717860621945_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{197873621611198397411381217896434507305_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{22488374978756237103319295816187492305_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{85146482200471605274516882717860621945_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x94dd12c437951af5159cb8bfacac1e29_b};
    _PossiblyUnknownBits<128, false> rhs{0x10eb1a7d7ba9c3d296b5a1691d7bb7d1_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{85146482200471605274516882717860621945_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x94dd12c437951af5159cb8bfacac1e29_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x10eb1a7d7ba9c3d296b5a1691d7bb7d1_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{85146482200471605274516882717860621945_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_547")
{
  // 128'286242032003237630496906105835031163241 * 128'17501019930342248504084059332991307516 = 128'107210597795760494468983251697088340316
  {
    _Bits<128, false> lhs{286242032003237630496906105835031163241_u128};
    _Bits<128, false> rhs{17501019930342248504084059332991307516_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{107210597795760494468983251697088340316_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{286242032003237630496906105835031163241_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{17501019930342248504084059332991307516_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{107210597795760494468983251697088340316_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xd75835c7a76d745fb00d7ccbbe70f169_b};
    _PossiblyUnknownBits<128, false> rhs{0xd2a92e6caeb3f315dc4b2a278e0cefc_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{107210597795760494468983251697088340316_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xd75835c7a76d745fb00d7ccbbe70f169_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd2a92e6caeb3f315dc4b2a278e0cefc_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{107210597795760494468983251697088340316_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_548")
{
  // 128'77471639170261295576342296413831379946 * 128'253286644574264911295447300917908912617 = 128'98809307439868117677425290829409657338
  {
    _Bits<128, false> lhs{77471639170261295576342296413831379946_u128};
    _Bits<128, false> rhs{253286644574264911295447300917908912617_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{98809307439868117677425290829409657338_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{77471639170261295576342296413831379946_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{253286644574264911295447300917908912617_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{98809307439868117677425290829409657338_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x3a487eb67a17df03eb69b1a57aaf3bea_b};
    _PossiblyUnknownBits<128, false> rhs{0xbe8d3bbb820973f1478254dcf746b9e9_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{98809307439868117677425290829409657338_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3a487eb67a17df03eb69b1a57aaf3bea_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xbe8d3bbb820973f1478254dcf746b9e9_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{98809307439868117677425290829409657338_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_549")
{
  // 128'122368520385261723424126911797433974050 * 128'74131038063240880883245694220905803093 = 128'215927066177328778853722619525863458378
  {
    _Bits<128, false> lhs{122368520385261723424126911797433974050_u128};
    _Bits<128, false> rhs{74131038063240880883245694220905803093_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{215927066177328778853722619525863458378_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{122368520385261723424126911797433974050_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{74131038063240880883245694220905803093_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{215927066177328778853722619525863458378_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x5c0f51dc2fd0724bbe6efaac845bbd22_b};
    _PossiblyUnknownBits<128, false> rhs{0x37c51e5caa2766f4811cf6b6c460ed55_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{215927066177328778853722619525863458378_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x5c0f51dc2fd0724bbe6efaac845bbd22_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x37c51e5caa2766f4811cf6b6c460ed55_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{215927066177328778853722619525863458378_u128};
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
TEST_CASE("bits_550")
{
  // 128'138044943619200564685986426041217955096 * 128'214834122956403973736405764430597487503 = 128'262775319525282458571502211521575301224
  {
    _Bits<128, false> lhs{138044943619200564685986426041217955096_u128};
    _Bits<128, false> rhs{214834122956403973736405764430597487503_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{262775319525282458571502211521575301224_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{138044943619200564685986426041217955096_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{214834122956403973736405764430597487503_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{262775319525282458571502211521575301224_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x67da7d32f43a7e03c7ba270bf711b518_b};
    _PossiblyUnknownBits<128, false> rhs{0xa19f8c0b52f2b42d4b3ebb4744e07b8f_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{262775319525282458571502211521575301224_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x67da7d32f43a7e03c7ba270bf711b518_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa19f8c0b52f2b42d4b3ebb4744e07b8f_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{262775319525282458571502211521575301224_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_551")
{
  // 128'80222620320208337276598026963024081044 * 128'249160018169599147882011949403748696012 = 128'274634935464214687101975515073211474416
  {
    _Bits<128, false> lhs{80222620320208337276598026963024081044_u128};
    _Bits<128, false> rhs{249160018169599147882011949403748696012_u128};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{274634935464214687101975515073211474416_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{80222620320208337276598026963024081044_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{249160018169599147882011949403748696012_u128}, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{274634935464214687101975515073211474416_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x3c5a508e28f6e5c80c3501b91197f094_b};
    _PossiblyUnknownBits<128, false> rhs{0xbb727957a684874916543302491fffcc_b};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{274634935464214687101975515073211474416_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3c5a508e28f6e5c80c3501b91197f094_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xbb727957a684874916543302491fffcc_b, Bits<32>{128}};
    auto result = lhs * rhs;
    auto expected = _Bits<128, false>{274634935464214687101975515073211474416_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_552")
{
  // 128'335542273725535200397179849607398494977 `* 128'337616592219327324899266333168470236177 = 256'113284639000739927020971923322612785646677584673509499263789474516329538182929
  {
    _Bits<128, false> lhs{335542273725535200397179849607398494977_u128};
    _Bits<128, false> rhs{337616592219327324899266333168470236177_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{113284639000739927020971923322612785646677584673509499263789474516329538182929_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{335542273725535200397179849607398494977_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{337616592219327324899266333168470236177_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{113284639000739927020971923322612785646677584673509499263789474516329538182929_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xfc6f175ca81be3fb303918771c0f1301_b};
    _PossiblyUnknownBits<128, false> rhs{0xfdfe9728e470ef0f95ced564c03e9c11_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{113284639000739927020971923322612785646677584673509499263789474516329538182929_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xfc6f175ca81be3fb303918771c0f1301_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xfdfe9728e470ef0f95ced564c03e9c11_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{113284639000739927020971923322612785646677584673509499263789474516329538182929_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_553")
{
  // 128'39581183346068302761436687941766331342 `* 128'305439403367524452558413088025865230694 = 256'12089653025803697533554403534193462521413703383378673023606478294002872611348
  {
    _Bits<128, false> lhs{39581183346068302761436687941766331342_u128};
    _Bits<128, false> rhs{305439403367524452558413088025865230694_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{12089653025803697533554403534193462521413703383378673023606478294002872611348_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{39581183346068302761436687941766331342_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{305439403367524452558413088025865230694_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{12089653025803697533554403534193462521413703383378673023606478294002872611348_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x1dc70f01fc4e79ec9aa435dddbb1bbce_b};
    _PossiblyUnknownBits<128, false> rhs{0xe5c97d43b0d42e3f1f921801c5221966_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{12089653025803697533554403534193462521413703383378673023606478294002872611348_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x1dc70f01fc4e79ec9aa435dddbb1bbce_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe5c97d43b0d42e3f1f921801c5221966_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{12089653025803697533554403534193462521413703383378673023606478294002872611348_mpz};
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
TEST_CASE("bits_554")
{
  // 128'326090807403877076734564948201969716402 `* 128'171418936266225945431245808768127494958 = 256'55898139331367364266164943231910496697845227827422343785643367317245944901116
  {
    _Bits<128, false> lhs{326090807403877076734564948201969716402_u128};
    _Bits<128, false> rhs{171418936266225945431245808768127494958_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{55898139331367364266164943231910496697845227827422343785643367317245944901116_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{326090807403877076734564948201969716402_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{171418936266225945431245808768127494958_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{55898139331367364266164943231910496697845227827422343785643367317245944901116_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0xf552ce1834ba699b0390fe830c1e8cb2_b};
    _PossiblyUnknownBits<128, false> rhs{0x80f61613c28d302f785e7c48e1e66b2e_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{55898139331367364266164943231910496697845227827422343785643367317245944901116_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf552ce1834ba699b0390fe830c1e8cb2_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x80f61613c28d302f785e7c48e1e66b2e_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{55898139331367364266164943231910496697845227827422343785643367317245944901116_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_555")
{
  // 128'217704168931805297235882581187031799970 `* 128'144151578657619251954103300162904488008 = 256'31382399631864760705535047983975115693297727205871889520595809263327519759760
  {
    _Bits<128, false> lhs{217704168931805297235882581187031799970_u128};
    _Bits<128, false> rhs{144151578657619251954103300162904488008_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{31382399631864760705535047983975115693297727205871889520595809263327519759760_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{217704168931805297235882581187031799970_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{144151578657619251954103300162904488008_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{31382399631864760705535047983975115693297727205871889520595809263327519759760_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xa3c84c3c620685bb209ef6e8c7e518a2_b};
    _PossiblyUnknownBits<128, false> rhs{0x6c72958d431f7194414f2f20afb17848_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{31382399631864760705535047983975115693297727205871889520595809263327519759760_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa3c84c3c620685bb209ef6e8c7e518a2_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x6c72958d431f7194414f2f20afb17848_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{31382399631864760705535047983975115693297727205871889520595809263327519759760_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_556")
{
  // 128'84861376872190620756534438802563417132 `* 128'240672759701012805071583269593860390025 = 256'20423821763857818914808939035107233089981754281278712632753969375806286908300
  {
    _Bits<128, false> lhs{84861376872190620756534438802563417132_u128};
    _Bits<128, false> rhs{240672759701012805071583269593860390025_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{20423821763857818914808939035107233089981754281278712632753969375806286908300_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{84861376872190620756534438802563417132_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{240672759701012805071583269593860390025_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{20423821763857818914808939035107233089981754281278712632753969375806286908300_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x3fd7b4e93e3ff9307c04d4c7a1ca442c_b};
    _PossiblyUnknownBits<128, false> rhs{0xb50fe33146c767e3e75c88520431bc89_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{20423821763857818914808939035107233089981754281278712632753969375806286908300_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3fd7b4e93e3ff9307c04d4c7a1ca442c_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xb50fe33146c767e3e75c88520431bc89_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{20423821763857818914808939035107233089981754281278712632753969375806286908300_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_557")
{
  // 128'242262053788374605563291901037730365447 `* 128'41453754426094510123093273505245517200 = 256'10042671684504580089239684396659452060321405303558137018736633235414524188400
  {
    _Bits<128, false> lhs{242262053788374605563291901037730365447_u128};
    _Bits<128, false> rhs{41453754426094510123093273505245517200_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{10042671684504580089239684396659452060321405303558137018736633235414524188400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{242262053788374605563291901037730365447_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{41453754426094510123093273505245517200_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{10042671684504580089239684396659452060321405303558137018736633235414524188400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb641f970d5ce3eba5e5d6da956888007_b};
    _PossiblyUnknownBits<128, false> rhs{0x1f2fb3e3dcafa39aa4974b12e0e95590_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{10042671684504580089239684396659452060321405303558137018736633235414524188400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb641f970d5ce3eba5e5d6da956888007_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1f2fb3e3dcafa39aa4974b12e0e95590_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{10042671684504580089239684396659452060321405303558137018736633235414524188400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_558")
{
  // 128'339489424722676483081190778413911372706 `* 128'161817490241637567878141342381630601223 = 256'54935326672200853484562652224279580523035682388722834887973378964828012419438
  {
    _Bits<128, false> lhs{339489424722676483081190778413911372706_u128};
    _Bits<128, false> rhs{161817490241637567878141342381630601223_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{54935326672200853484562652224279580523035682388722834887973378964828012419438_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{339489424722676483081190778413911372706_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{161817490241637567878141342381630601223_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{54935326672200853484562652224279580523035682388722834887973378964828012419438_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xff6748ee652282c09285d6a75a83f3a2_b};
    _PossiblyUnknownBits<128, false> rhs{0x79bcea3d525f577720a73e866324b807_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{54935326672200853484562652224279580523035682388722834887973378964828012419438_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xff6748ee652282c09285d6a75a83f3a2_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x79bcea3d525f577720a73e866324b807_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{54935326672200853484562652224279580523035682388722834887973378964828012419438_mpz};
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
TEST_CASE("bits_559")
{
  // 128'92336874186854682752422953805411727291 `* 128'279678215007656413569747041664413392479 = 256'25824612151966063433101198171961128538409257209420912588669704489784498444389
  {
    _Bits<128, false> lhs{92336874186854682752422953805411727291_u128};
    _Bits<128, false> rhs{279678215007656413569747041664413392479_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{25824612151966063433101198171961128538409257209420912588669704489784498444389_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{92336874186854682752422953805411727291_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{279678215007656413569747041664413392479_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{25824612151966063433101198171961128538409257209420912588669704489784498444389_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x45776f62804a4e406ec5f8b3b1f737bb_b};
    _PossiblyUnknownBits<128, false> rhs{0xd268109dc8da9c1d2d875d356d2ade5f_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{25824612151966063433101198171961128538409257209420912588669704489784498444389_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x45776f62804a4e406ec5f8b3b1f737bb_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd268109dc8da9c1d2d875d356d2ade5f_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{25824612151966063433101198171961128538409257209420912588669704489784498444389_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_560")
{
  // 128'3631621238988801083640422992979729061 `* 128'129811441468673955580831893747074502624 = 256'471425987901387942777967880760236725238365179447189226869047004960853556064
  {
    _Bits<128, false> lhs{3631621238988801083640422992979729061_u128};
    _Bits<128, false> rhs{129811441468673955580831893747074502624_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{471425987901387942777967880760236725238365179447189226869047004960853556064_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{3631621238988801083640422992979729061_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{129811441468673955580831893747074502624_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{471425987901387942777967880760236725238365179447189226869047004960853556064_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x2bb6cc049c3577fa2dcb37ace989aa5_b};
    _PossiblyUnknownBits<128, false> rhs{0x61a8c63399b13896ecec3f73f3ae8fe0_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{471425987901387942777967880760236725238365179447189226869047004960853556064_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x2bb6cc049c3577fa2dcb37ace989aa5_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x61a8c63399b13896ecec3f73f3ae8fe0_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{471425987901387942777967880760236725238365179447189226869047004960853556064_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_561")
{
  // 128'171650222820113552478027912413564196460 `* 128'299503998434664084574425509912253702734 = 256'51409928066825030750252987757299933107855684472266558973189679086846415121640
  {
    _Bits<128, false> lhs{171650222820113552478027912413564196460_u128};
    _Bits<128, false> rhs{299503998434664084574425509912253702734_u128};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{51409928066825030750252987757299933107855684472266558973189679086846415121640_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{171650222820113552478027912413564196460_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{299503998434664084574425509912253702734_u128}, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{51409928066825030750252987757299933107855684472266558973189679086846415121640_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x8122a1627bf537c60ad4f07e7e09566c_b};
    _PossiblyUnknownBits<128, false> rhs{0xe1525f3528e27ab772df79e78702224e_b};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{51409928066825030750252987757299933107855684472266558973189679086846415121640_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x8122a1627bf537c60ad4f07e7e09566c_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe1525f3528e27ab772df79e78702224e_b, Bits<32>{128}};
    auto result = lhs.widening_mul(rhs);
    auto expected = _Bits<256, false>{51409928066825030750252987757299933107855684472266558973189679086846415121640_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_562")
{
  // 128'117522159971090190780521906044125519268 / 128'138135514116441359343203533650061142092 = 128'0
  {
    _Bits<128, false> lhs{117522159971090190780521906044125519268_u128};
    _Bits<128, false> rhs{138135514116441359343203533650061142092_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{117522159971090190780521906044125519268_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{138135514116441359343203533650061142092_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x5869f1d7f9214b0e9c975ec5bfab1da4_b};
    _PossiblyUnknownBits<128, false> rhs{0x67ebeeab58555d7565f426253217a84c_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x5869f1d7f9214b0e9c975ec5bfab1da4_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x67ebeeab58555d7565f426253217a84c_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_563")
{
  // 128'9424137542721097191927177792689328274 / 128'82104361838990699726210880540056258100 = 128'0
  {
    _Bits<128, false> lhs{9424137542721097191927177792689328274_u128};
    _Bits<128, false> rhs{82104361838990699726210880540056258100_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{9424137542721097191927177792689328274_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{82104361838990699726210880540056258100_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x71705dac41c05ae784a83ff601cd092_b};
    _PossiblyUnknownBits<128, false> rhs{0x3dc4b9933f13c1bcc1ca8457c2908634_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x71705dac41c05ae784a83ff601cd092_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3dc4b9933f13c1bcc1ca8457c2908634_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_564")
{
  // 128'323685551402939282610420184820006536964 / 128'86318454138278274032697199438091071141 = 128'3
  {
    _Bits<128, false> lhs{323685551402939282610420184820006536964_u128};
    _Bits<128, false> rhs{86318454138278274032697199438091071141_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{3_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{323685551402939282610420184820006536964_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{86318454138278274032697199438091071141_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{3_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xf38391d1630fd79f07daf94dcc084704_b};
    _PossiblyUnknownBits<128, false> rhs{0x40f0545de69b73075f8be58a86c52ea5_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{3_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf38391d1630fd79f07daf94dcc084704_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x40f0545de69b73075f8be58a86c52ea5_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{3_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_565")
{
  // 128'1970093021413593737508039105174415439 / 128'250252600404816022770686888582990115609 = 128'0
  {
    _Bits<128, false> lhs{1970093021413593737508039105174415439_u128};
    _Bits<128, false> rhs{250252600404816022770686888582990115609_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{1970093021413593737508039105174415439_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{250252600404816022770686888582990115609_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x17b6d15d3ef576ee44a8ed67871a84f_b};
    _PossiblyUnknownBits<128, false> rhs{0xbc44e5ce3a63c7795736eef2d1edb319_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x17b6d15d3ef576ee44a8ed67871a84f_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xbc44e5ce3a63c7795736eef2d1edb319_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_566")
{
  // 128'46994740052431739033414210429614611862 / 128'139923215463528023019767108751492626308 = 128'0
  {
    _Bits<128, false> lhs{46994740052431739033414210429614611862_u128};
    _Bits<128, false> rhs{139923215463528023019767108751492626308_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{46994740052431739033414210429614611862_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{139923215463528023019767108751492626308_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x235adb92daacca309cc69cd15a34dd96_b};
    _PossiblyUnknownBits<128, false> rhs{0x69443b269786625f73768032319bb784_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x235adb92daacca309cc69cd15a34dd96_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x69443b269786625f73768032319bb784_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_567")
{
  // 128'197329703933272204687126302344151232006 / 128'180368822617101791200750934285141635376 = 128'1
  {
    _Bits<128, false> lhs{197329703933272204687126302344151232006_u128};
    _Bits<128, false> rhs{180368822617101791200750934285141635376_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{197329703933272204687126302344151232006_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{180368822617101791200750934285141635376_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x9474518df2dfb2607fe755000a4aee06_b};
    _PossiblyUnknownBits<128, false> rhs{0x87b1c58aef1aa6e31cd115d3c7077130_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x9474518df2dfb2607fe755000a4aee06_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x87b1c58aef1aa6e31cd115d3c7077130_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_568")
{
  // 128'290581165580085320218855537290192935500 / 128'34276930516930723107274335307604924333 = 128'8
  {
    _Bits<128, false> lhs{290581165580085320218855537290192935500_u128};
    _Bits<128, false> rhs{34276930516930723107274335307604924333_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{8_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{290581165580085320218855537290192935500_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{34276930516930723107274335307604924333_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{8_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xda9be5951d6bbc8ebd3c01a61a34da4c_b};
    _PossiblyUnknownBits<128, false> rhs{0x19c97f26f8f852b5d4214b57f5cf97ad_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{8_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xda9be5951d6bbc8ebd3c01a61a34da4c_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x19c97f26f8f852b5d4214b57f5cf97ad_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{8_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_569")
{
  // 128'257572798946812318471544838176974416700 / 128'23290615496648078048231000617438899748 = 128'11
  {
    _Bits<128, false> lhs{257572798946812318471544838176974416700_u128};
    _Bits<128, false> rhs{23290615496648078048231000617438899748_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{11_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{257572798946812318471544838176974416700_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{23290615496648078048231000617438899748_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{11_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xc1c6b775665e0e1e9461442a6e5dab3c_b};
    _PossiblyUnknownBits<128, false> rhs{0x11859c0061a66565b1f50ad470d76e24_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{11_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc1c6b775665e0e1e9461442a6e5dab3c_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x11859c0061a66565b1f50ad470d76e24_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{11_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_570")
{
  // 128'16278732317274183983176103416282231659 / 128'309161467141364018902019183163085545888 = 128'0
  {
    _Bits<128, false> lhs{16278732317274183983176103416282231659_u128};
    _Bits<128, false> rhs{309161467141364018902019183163085545888_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{16278732317274183983176103416282231659_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{309161467141364018902019183163085545888_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xc3f2b782fbda08db50ba2d64298336b_b};
    _PossiblyUnknownBits<128, false> rhs{0xe896552d41ea3a1ce147613f1af9e1a0_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc3f2b782fbda08db50ba2d64298336b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe896552d41ea3a1ce147613f1af9e1a0_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_571")
{
  // 128'167192428116046469704128767815327366370 / 128'95870611897618517299452580450370807358 = 128'1
  {
    _Bits<128, false> lhs{167192428116046469704128767815327366370_u128};
    _Bits<128, false> rhs{95870611897618517299452580450370807358_u128};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{167192428116046469704128767815327366370_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{95870611897618517299452580450370807358_u128}, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x7dc81723091b5d9872b500118f373ce2_b};
    _PossiblyUnknownBits<128, false> rhs{0x4820021af869ab068a148406fd8f663e_b};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x7dc81723091b5d9872b500118f373ce2_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x4820021af869ab068a148406fd8f663e_b, Bits<32>{128}};
    auto result = lhs / rhs;
    auto expected = _Bits<128, false>{1_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_572")
{
  // 128'317075098069405313520381795564266595795 % 128'33842309719621329097540352718944786141 = 128'12494310592813351642518621093763520526
  {
    _Bits<128, false> lhs{317075098069405313520381795564266595795_u128};
    _Bits<128, false> rhs{33842309719621329097540352718944786141_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12494310592813351642518621093763520526_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{317075098069405313520381795564266595795_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{33842309719621329097540352718944786141_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12494310592813351642518621093763520526_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xee8a714e2d5a028ca8be77a8eaae25d3_b};
    _PossiblyUnknownBits<128, false> rhs{0x1975cab14875a73c8ceca87f47a2d6dd_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12494310592813351642518621093763520526_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xee8a714e2d5a028ca8be77a8eaae25d3_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1975cab14875a73c8ceca87f47a2d6dd_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12494310592813351642518621093763520526_u128};
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
TEST_CASE("bits_573")
{
  // 128'299848976699225876814717788998110555132 % 128'151090147016508738260326103575112786540 = 128'148758829682717138554391685422997768592
  {
    _Bits<128, false> lhs{299848976699225876814717788998110555132_u128};
    _Bits<128, false> rhs{151090147016508738260326103575112786540_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{148758829682717138554391685422997768592_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{299848976699225876814717788998110555132_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{151090147016508738260326103575112786540_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{148758829682717138554391685422997768592_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xe194cff304482ee00f4552aa74882bfc_b};
    _PossiblyUnknownBits<128, false> rhs{0x71aae76253a2b47582472d2bd165226c_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{148758829682717138554391685422997768592_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xe194cff304482ee00f4552aa74882bfc_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x71aae76253a2b47582472d2bd165226c_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{148758829682717138554391685422997768592_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_574")
{
  // 128'317558110138070712812666343341444061531 % 128'297225670661431421777410130023440724858 = 128'20332439476639291035256213318003336673
  {
    _Bits<128, false> lhs{317558110138070712812666343341444061531_u128};
    _Bits<128, false> rhs{297225670661431421777410130023440724858_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20332439476639291035256213318003336673_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{317558110138070712812666343341444061531_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{297225670661431421777410130023440724858_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20332439476639291035256213318003336673_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xeee777a394a728f66835eef9c968595b_b};
    _PossiblyUnknownBits<128, false> rhs{0xdf9b94f9ce6f4f505a9fba86198c337a_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20332439476639291035256213318003336673_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xeee777a394a728f66835eef9c968595b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xdf9b94f9ce6f4f505a9fba86198c337a_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20332439476639291035256213318003336673_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_575")
{
  // 128'227659521401925632340230755598888717144 % 128'215567960880752246611379035571575127026 = 128'12091560521173385728851720027313590118
  {
    _Bits<128, false> lhs{227659521401925632340230755598888717144_u128};
    _Bits<128, false> rhs{215567960880752246611379035571575127026_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12091560521173385728851720027313590118_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{227659521401925632340230755598888717144_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{215567960880752246611379035571575127026_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12091560521173385728851720027313590118_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xab45a1022a35f554852263c6ee81cb58_b};
    _PossiblyUnknownBits<128, false> rhs{0xa22ce10c1cd3c0245fd5d930fa64fbf2_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12091560521173385728851720027313590118_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xab45a1022a35f554852263c6ee81cb58_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa22ce10c1cd3c0245fd5d930fa64fbf2_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{12091560521173385728851720027313590118_u128};
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
TEST_CASE("bits_576")
{
  // 128'101983303440204271699045968212814619682 % 128'76150230457413210030562108392281952494 = 128'25833072982791061668483859820532667188
  {
    _Bits<128, false> lhs{101983303440204271699045968212814619682_u128};
    _Bits<128, false> rhs{76150230457413210030562108392281952494_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{25833072982791061668483859820532667188_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{101983303440204271699045968212814619682_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{76150230457413210030562108392281952494_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{25833072982791061668483859820532667188_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x4cb945111bb976cbbc8cc3dc19326422_b};
    _PossiblyUnknownBits<128, false> rhs{0x394a003bb3e948adb834d121693350ee_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{25833072982791061668483859820532667188_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x4cb945111bb976cbbc8cc3dc19326422_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x394a003bb3e948adb834d121693350ee_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{25833072982791061668483859820532667188_u128};
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
TEST_CASE("bits_577")
{
  // 128'260428693009422650870988534781975776587 % 128'262042041157788093428269240013110990002 = 128'260428693009422650870988534781975776587
  {
    _Bits<128, false> lhs{260428693009422650870988534781975776587_u128};
    _Bits<128, false> rhs{262042041157788093428269240013110990002_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{260428693009422650870988534781975776587_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs == result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{260428693009422650870988534781975776587_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{262042041157788093428269240013110990002_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{260428693009422650870988534781975776587_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xc3ecbde834fe9feaf54c380a7de0cd4b_b};
    _PossiblyUnknownBits<128, false> rhs{0xc523761cb2f8d82c74f762f1641d54b2_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{260428693009422650870988534781975776587_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xc3ecbde834fe9feaf54c380a7de0cd4b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xc523761cb2f8d82c74f762f1641d54b2_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{260428693009422650870988534781975776587_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_578")
{
  // 128'328095894031955874331572145837441895814 % 128'117898816357510973082593510822831862870 = 128'92298261316933928166385124191778170074
  {
    _Bits<128, false> lhs{328095894031955874331572145837441895814_u128};
    _Bits<128, false> rhs{117898816357510973082593510822831862870_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{92298261316933928166385124191778170074_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{328095894031955874331572145837441895814_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{117898816357510973082593510822831862870_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{92298261316933928166385124191778170074_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xf6d4f87f720e846087b99a8847fd4d86_b};
    _PossiblyUnknownBits<128, false> rhs{0x58b27c6ff0bad885ca070df3ef663456_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{92298261316933928166385124191778170074_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf6d4f87f720e846087b99a8847fd4d86_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x58b27c6ff0bad885ca070df3ef663456_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{92298261316933928166385124191778170074_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_579")
{
  // 128'91755666177046462039243562472414158078 % 128'202017696353467420889943330453626865433 = 128'91755666177046462039243562472414158078
  {
    _Bits<128, false> lhs{91755666177046462039243562472414158078_u128};
    _Bits<128, false> rhs{202017696353467420889943330453626865433_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{91755666177046462039243562472414158078_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs == result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{91755666177046462039243562472414158078_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{202017696353467420889943330453626865433_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{91755666177046462039243562472414158078_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result == lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x45077f9e12c46a611b3a38a553d89cfe_b};
    _PossiblyUnknownBits<128, false> rhs{0x97fb316d0e94b9f7627cfd2ed600c719_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{91755666177046462039243562472414158078_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x45077f9e12c46a611b3a38a553d89cfe_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x97fb316d0e94b9f7627cfd2ed600c719_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{91755666177046462039243562472414158078_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_580")
{
  // 128'238688615530138633895507717631113245533 % 128'131656075523673642689767842749155231141 = 128'107032540006464991205739874881958014392
  {
    _Bits<128, false> lhs{238688615530138633895507717631113245533_u128};
    _Bits<128, false> rhs{131656075523673642689767842749155231141_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{107032540006464991205739874881958014392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{238688615530138633895507717631113245533_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{131656075523673642689767842749155231141_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{107032540006464991205739874881958014392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb391c1550246308fe157428962f1335d_b};
    _PossiblyUnknownBits<128, false> rhs{0x630c09aea5b0099eb5458c3a4d25c5a5_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{107032540006464991205739874881958014392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb391c1550246308fe157428962f1335d_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x630c09aea5b0099eb5458c3a4d25c5a5_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{107032540006464991205739874881958014392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_581")
{
  // 128'20963011951204836905377042471669711359 % 128'68735887824101064261156405561589447099 = 128'20963011951204836905377042471669711359
  {
    _Bits<128, false> lhs{20963011951204836905377042471669711359_u128};
    _Bits<128, false> rhs{68735887824101064261156405561589447099_u128};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20963011951204836905377042471669711359_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{20963011951204836905377042471669711359_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{68735887824101064261156405561589447099_u128}, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20963011951204836905377042471669711359_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xfc5544958020e901bdcadf4041fc1ff_b};
    _PossiblyUnknownBits<128, false> rhs{0x33b60ceb0a9c1d6aacc3f70de96339bb_b};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20963011951204836905377042471669711359_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs < rhs);
    REQUIRE(rhs >= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xfc5544958020e901bdcadf4041fc1ff_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x33b60ceb0a9c1d6aacc3f70de96339bb_b, Bits<32>{128}};
    auto result = lhs % rhs;
    auto expected = _Bits<128, false>{20963011951204836905377042471669711359_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs <= rhs);
    REQUIRE(rhs > lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_582")
{
  // 128'152928510481493896007764567222285861767 >> 128'71 = 128'64767743476174967
  {
    _Bits<128, false> lhs{152928510481493896007764567222285861767_u128};
    _Bits<128, false> rhs{71_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{64767743476174967_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{152928510481493896007764567222285861767_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{71_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{64767743476174967_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x730cf5b366883bf1106583c5b3fd8387_b};
    _PossiblyUnknownBits<128, false> rhs{0x47_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{64767743476174967_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x730cf5b366883bf1106583c5b3fd8387_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x47_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{64767743476174967_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_583")
{
  // 128'7252724787901243879546911329785704499 >> 128'26 = 128'108074021159130988710327615287
  {
    _Bits<128, false> lhs{7252724787901243879546911329785704499_u128};
    _Bits<128, false> rhs{26_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{108074021159130988710327615287_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{7252724787901243879546911329785704499_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{26_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{108074021159130988710327615287_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x574d2f0a9feadbaf18397fcdebf7033_b};
    _PossiblyUnknownBits<128, false> rhs{0x1a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{108074021159130988710327615287_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x574d2f0a9feadbaf18397fcdebf7033_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1a_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{108074021159130988710327615287_u128};
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
TEST_CASE("bits_584")
{
  // 128'241426581690491620425312227846918685102 >> 128'48 = 128'857719519197856145443780
  {
    _Bits<128, false> lhs{241426581690491620425312227846918685102_u128};
    _Bits<128, false> rhs{48_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{857719519197856145443780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{241426581690491620425312227846918685102_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{48_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{857719519197856145443780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xb5a1117c6dac6f2d8bc44e4efc16c1ae_b};
    _PossiblyUnknownBits<128, false> rhs{0x30_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{857719519197856145443780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xb5a1117c6dac6f2d8bc44e4efc16c1ae_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x30_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{857719519197856145443780_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_585")
{
  // 128'231443563766223644758987020534437160338 >> 128'152 = 128'0
  {
    _Bits<128, false> lhs{231443563766223644758987020534437160338_u128};
    _Bits<128, false> rhs{152_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{231443563766223644758987020534437160338_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{152_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xae1e68b385f09867d2693cce30bca592_b};
    _PossiblyUnknownBits<128, false> rhs{0x98_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xae1e68b385f09867d2693cce30bca592_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x98_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_586")
{
  // 128'216452648374322392326763634067722019246 >> 128'71 = 128'91671262346750518
  {
    _Bits<128, false> lhs{216452648374322392326763634067722019246_u128};
    _Bits<128, false> rhs{71_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{91671262346750518_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{216452648374322392326763634067722019246_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{71_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{91671262346750518_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xa2d7438225151b3e5d7a00e1014d21ae_b};
    _PossiblyUnknownBits<128, false> rhs{0x47_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{91671262346750518_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa2d7438225151b3e5d7a00e1014d21ae_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x47_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{91671262346750518_u128};
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
TEST_CASE("bits_587")
{
  // 128'67801515318337700382710440298103656099 >> 128'154 = 128'0
  {
    _Bits<128, false> lhs{67801515318337700382710440298103656099_u128};
    _Bits<128, false> rhs{154_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{67801515318337700382710440298103656099_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{154_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x330218cbfd76117531e1f102484f4ea3_b};
    _PossiblyUnknownBits<128, false> rhs{0x9a_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x330218cbfd76117531e1f102484f4ea3_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x9a_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_588")
{
  // 128'113991454364215390461559604068735579454 >> 128'98 = 128'359693607
  {
    _Bits<128, false> lhs{113991454364215390461559604068735579454_u128};
    _Bits<128, false> rhs{98_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{359693607_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{113991454364215390461559604068735579454_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{98_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{359693607_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x55c1f49e09122fc15a0edb44b1acf53e_b};
    _PossiblyUnknownBits<128, false> rhs{0x62_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{359693607_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x55c1f49e09122fc15a0edb44b1acf53e_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x62_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{359693607_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_589")
{
  // 128'314835285038147331242873969772579058584 >> 128'63 = 128'34134510001345236625
  {
    _Bits<128, false> lhs{314835285038147331242873969772579058584_u128};
    _Bits<128, false> rhs{63_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{34134510001345236625_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{314835285038147331242873969772579058584_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{63_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{34134510001345236625_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xecdb11ff3619c748e09dfa10e768f398_b};
    _PossiblyUnknownBits<128, false> rhs{0x3f_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{34134510001345236625_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xecdb11ff3619c748e09dfa10e768f398_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3f_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{34134510001345236625_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_590")
{
  // 128'312369729631248635927358568649751946188 >> 128'93 = 128'31541282263
  {
    _Bits<128, false> lhs{312369729631248635927358568649751946188_u128};
    _Bits<128, false> rhs{93_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{31541282263_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{312369729631248635927358568649751946188_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{93_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{31541282263_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xeb0038bae387e2e2820bb3f1ee0a63cc_b};
    _PossiblyUnknownBits<128, false> rhs{0x5d_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{31541282263_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xeb0038bae387e2e2820bb3f1ee0a63cc_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x5d_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{31541282263_u128};
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
TEST_CASE("bits_591")
{
  // 128'37086521131907922237737765511090172652 >> 128'248 = 128'0
  {
    _Bits<128, false> lhs{37086521131907922237737765511090172652_u128};
    _Bits<128, false> rhs{248_u128};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{37086521131907922237737765511090172652_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{248_u128}, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x1be69aaa1b18668047de8244f6e472ec_b};
    _PossiblyUnknownBits<128, false> rhs{0xf8_b};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x1be69aaa1b18668047de8244f6e472ec_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xf8_b, Bits<32>{128}};
    auto result = lhs >> rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_592")
{
  // 128'99893183826549444282851785919651699066 >>> 128'55 = 128'2772592817183712318253
  {
    _Bits<128, false> lhs{99893183826549444282851785919651699066_u128};
    _Bits<128, false> rhs{55_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{2772592817183712318253_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{99893183826549444282851785919651699066_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{55_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{2772592817183712318253_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x4b26ba36b37d5dc996af3181042cd97a_b};
    _PossiblyUnknownBits<128, false> rhs{0x37_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{2772592817183712318253_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x4b26ba36b37d5dc996af3181042cd97a_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x37_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{2772592817183712318253_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_593")
{
  // 128'196714543817083815313297143979425569114 >>> 128'27 = 128'340282365851274826303202680292028046488
  {
    _Bits<128, false> lhs{196714543817083815313297143979425569114_u128};
    _Bits<128, false> rhs{27_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282365851274826303202680292028046488_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{196714543817083815313297143979425569114_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{27_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282365851274826303202680292028046488_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x93fdd7d1b0e0cb0e48974ee4c072995a_b};
    _PossiblyUnknownBits<128, false> rhs{0x1b_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282365851274826303202680292028046488_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x93fdd7d1b0e0cb0e48974ee4c072995a_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1b_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282365851274826303202680292028046488_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_594")
{
  // 128'155786282275607675207848924263446025352 >>> 128'232 = 128'0
  {
    _Bits<128, false> lhs{155786282275607675207848924263446025352_u128};
    _Bits<128, false> rhs{232_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{155786282275607675207848924263446025352_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{232_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x753358ba82e008f020d378697ca51488_b};
    _PossiblyUnknownBits<128, false> rhs{0xe8_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x753358ba82e008f020d378697ca51488_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe8_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
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
TEST_CASE("bits_595")
{
  // 128'84034676489189398256631408466375579599 >>> 128'39 = 128'152858186064239631844668853
  {
    _Bits<128, false> lhs{84034676489189398256631408466375579599_u128};
    _Bits<128, false> rhs{39_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{152858186064239631844668853_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{84034676489189398256631408466375579599_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{39_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{152858186064239631844668853_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x3f387d6f71873317c13adadb283d97cf_b};
    _PossiblyUnknownBits<128, false> rhs{0x27_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{152858186064239631844668853_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x3f387d6f71873317c13adadb283d97cf_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x27_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{152858186064239631844668853_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_596")
{
  // 128'249205863078926114403254664220963147746 >>> 128'17 = 128'340281672062358125844744693186596009879
  {
    _Bits<128, false> lhs{249205863078926114403254664220963147746_u128};
    _Bits<128, false> rhs{17_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340281672062358125844744693186596009879_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{249205863078926114403254664220963147746_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{17_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340281672062358125844744693186596009879_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xbb7b4dabc1d80bf07339bb0aef2e8fe2_b};
    _PossiblyUnknownBits<128, false> rhs{0x11_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340281672062358125844744693186596009879_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xbb7b4dabc1d80bf07339bb0aef2e8fe2_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x11_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340281672062358125844744693186596009879_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_597")
{
  // 128'67943755278382240822316569180841526199 >>> 128'210 = 128'0
  {
    _Bits<128, false> lhs{67943755278382240822316569180841526199_u128};
    _Bits<128, false> rhs{210_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{67943755278382240822316569180841526199_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{210_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x331d7dc4b0353ab5d3e5edf541fd43b7_b};
    _PossiblyUnknownBits<128, false> rhs{0xd2_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x331d7dc4b0353ab5d3e5edf541fd43b7_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd2_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_598")
{
  // 128'316320785649608909515780410526519446861 >>> 128'208 = 128'340282366920938463463374607431768211455
  {
    _Bits<128, false> lhs{316320785649608909515780410526519446861_u128};
    _Bits<128, false> rhs{208_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{316320785649608909515780410526519446861_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{208_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xedf92ad4eca276c47555a4933876cd4d_b};
    _PossiblyUnknownBits<128, false> rhs{0xd0_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xedf92ad4eca276c47555a4933876cd4d_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xd0_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_599")
{
  // 128'181035485835922071619141987115319290708 >>> 128'166 = 128'340282366920938463463374607431768211455
  {
    _Bits<128, false> lhs{181035485835922071619141987115319290708_u128};
    _Bits<128, false> rhs{166_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{181035485835922071619141987115319290708_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{166_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x88322a93bd08fc0de98f62c5c275eb54_b};
    _PossiblyUnknownBits<128, false> rhs{0xa6_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x88322a93bd08fc0de98f62c5c275eb54_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa6_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_600")
{
  // 128'121593530845545871339689317528774388276 >>> 128'160 = 128'0
  {
    _Bits<128, false> lhs{121593530845545871339689317528774388276_u128};
    _Bits<128, false> rhs{160_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{121593530845545871339689317528774388276_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{160_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x5b7a0fecfd48195636814d630cd82a34_b};
    _PossiblyUnknownBits<128, false> rhs{0xa0_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x5b7a0fecfd48195636814d630cd82a34_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa0_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_601")
{
  // 128'318036639969574363191673588538795812618 >>> 128'162 = 128'340282366920938463463374607431768211455
  {
    _Bits<128, false> lhs{318036639969574363191673588538795812618_u128};
    _Bits<128, false> rhs{162_u128};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{318036639969574363191673588538795812618_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{162_u128}, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xef43a0fb32933f247fddeb28822ee70a_b};
    _PossiblyUnknownBits<128, false> rhs{0xa2_b};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xef43a0fb32933f247fddeb28822ee70a_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xa2_b, Bits<32>{128}};
    auto result = lhs.sra(rhs);
    auto expected = _Bits<128, false>{340282366920938463463374607431768211455_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_602")
{
  // 128'311231054170383096859978574926112923674 << 128'27 = 128'191534424709157537704671173457993531392
  {
    _Bits<128, false> lhs{311231054170383096859978574926112923674_u128};
    _Bits<128, false> rhs{27_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{191534424709157537704671173457993531392_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{311231054170383096859978574926112923674_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{27_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{191534424709157537704671173457993531392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xea24ebb20306075069162191809ca01a_b};
    _PossiblyUnknownBits<128, false> rhs{0x1b_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{191534424709157537704671173457993531392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xea24ebb20306075069162191809ca01a_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1b_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{191534424709157537704671173457993531392_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_603")
{
  // 128'320259128324434088341744779530951730215 << 128'228 = 128'0
  {
    _Bits<128, false> lhs{320259128324434088341744779530951730215_u128};
    _Bits<128, false> rhs{228_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{320259128324434088341744779530951730215_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{228_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xf0efaa1e014015b83113b28aa3902427_b};
    _PossiblyUnknownBits<128, false> rhs{0xe4_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf0efaa1e014015b83113b28aa3902427_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe4_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
}
TEST_CASE("bits_604")
{
  // 128'51931936122787196099606768803130385871 << 128'69 = 128'238784361224305830309628118433213186048
  {
    _Bits<128, false> lhs{51931936122787196099606768803130385871_u128};
    _Bits<128, false> rhs{69_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{238784361224305830309628118433213186048_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{51931936122787196099606768803130385871_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{69_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{238784361224305830309628118433213186048_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x2711ba223c37d161f59d218fac8c25cf_b};
    _PossiblyUnknownBits<128, false> rhs{0x45_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{238784361224305830309628118433213186048_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x2711ba223c37d161f59d218fac8c25cf_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x45_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{238784361224305830309628118433213186048_u128};
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
TEST_CASE("bits_605")
{
  // 128'46885982986606551193865307444033613006 << 128'158 = 128'0
  {
    _Bits<128, false> lhs{46885982986606551193865307444033613006_u128};
    _Bits<128, false> rhs{158_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{46885982986606551193865307444033613006_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{158_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x2345e96fb2240a7d54a6e6f8b1e3ecce_b};
    _PossiblyUnknownBits<128, false> rhs{0x9e_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x2345e96fb2240a7d54a6e6f8b1e3ecce_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x9e_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_606")
{
  // 128'272384462807161951447113473428640974585 << 128'31 = 128'63147694414759749293798755832214585344
  {
    _Bits<128, false> lhs{272384462807161951447113473428640974585_u128};
    _Bits<128, false> rhs{31_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{63147694414759749293798755832214585344_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{272384462807161951447113473428640974585_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{31_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{63147694414759749293798755832214585344_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xcceb56de5f039b6c1de0bf6bd29346f9_b};
    _PossiblyUnknownBits<128, false> rhs{0x1f_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{63147694414759749293798755832214585344_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xcceb56de5f039b6c1de0bf6bd29346f9_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x1f_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{63147694414759749293798755832214585344_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_607")
{
  // 128'300508048487806088705606508607345955290 << 128'87 = 128'284572820217231294226302747978164600832
  {
    _Bits<128, false> lhs{300508048487806088705606508607345955290_u128};
    _Bits<128, false> rhs{87_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{284572820217231294226302747978164600832_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{300508048487806088705606508607345955290_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{87_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{284572820217231294226302747978164600832_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xe213beb2802a61e0428e73ac2d7691da_b};
    _PossiblyUnknownBits<128, false> rhs{0x57_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{284572820217231294226302747978164600832_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xe213beb2802a61e0428e73ac2d7691da_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x57_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{284572820217231294226302747978164600832_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_608")
{
  // 128'321851702065514170874017221179594891095 << 128'128 = 128'0
  {
    _Bits<128, false> lhs{321851702065514170874017221179594891095_u128};
    _Bits<128, false> rhs{128_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{321851702065514170874017221179594891095_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{128_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result < lhs);
    REQUIRE(rhs != result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xf22262109cfa930c33bad78f5005df57_b};
    _PossiblyUnknownBits<128, false> rhs{0x80_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs > result);
    REQUIRE(result != lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result <= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xf22262109cfa930c33bad78f5005df57_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x80_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_609")
{
  // 128'229661830082150033096870153873921444875 << 128'170 = 128'0
  {
    _Bits<128, false> lhs{229661830082150033096870153873921444875_u128};
    _Bits<128, false> rhs{170_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs > result);
    REQUIRE(result <= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{229661830082150033096870153873921444875_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{170_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0xacc74272c5ea38f9084d309329248c0b_b};
    _PossiblyUnknownBits<128, false> rhs{0xaa_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xacc74272c5ea38f9084d309329248c0b_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xaa_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
TEST_CASE("bits_610")
{
  // 128'223854583768024354778465590481147763433 << 128'63 = 128'272052071591269934120299347064840519680
  {
    _Bits<128, false> lhs{223854583768024354778465590481147763433_u128};
    _Bits<128, false> rhs{63_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{272052071591269934120299347064840519680_u128};
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
    _RuntimeBits<128, false> lhs{Bits<128>{223854583768024354778465590481147763433_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{63_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{272052071591269934120299347064840519680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xa868d3196d056e899956a56ecec59ae9_b};
    _PossiblyUnknownBits<128, false> rhs{0x3f_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{272052071591269934120299347064840519680_u128};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xa868d3196d056e899956a56ecec59ae9_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3f_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{272052071591269934120299347064840519680_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_611")
{
  // 128'54548597616866889286978597014452239022 << 128'136 = 128'0
  {
    _Bits<128, false> lhs{54548597616866889286978597014452239022_u128};
    _Bits<128, false> rhs{136_u128};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs >= result);
    REQUIRE(result < rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{54548597616866889286978597014452239022_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{136_u128}, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
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
    _PossiblyUnknownBits<128, false> lhs{0x2909ad818364944095cc4e1bfe06faae_b};
    _PossiblyUnknownBits<128, false> rhs{0x88_b};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs >= result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x2909ad818364944095cc4e1bfe06faae_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x88_b, Bits<32>{128}};
    auto result = lhs << rhs;
    auto expected = _Bits<128, false>{0_u128};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs > result);
    REQUIRE(result <= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result < rhs);
  }
}
TEST_CASE("bits_612")
{
  // 128'91405457824142868913940533880716006220 `<< 128'242 = 370'645997859445244929063330092322131780655315027759230444092833483162360121242502066956072886951208394718844026880
  {
    _Bits<128, false> lhs{91405457824142868913940533880716006220_u128};
    _Bits<128, false> rhs{242_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<370, false>{645997859445244929063330092322131780655315027759230444092833483162360121242502066956072886951208394718844026880_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{91405457824142868913940533880716006220_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{242_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<370, false>{645997859445244929063330092322131780655315027759230444092833483162360121242502066956072886951208394718844026880_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x44c40d0338806f3b0b9ff4bbf370134c_b};
    _PossiblyUnknownBits<128, false> rhs{0xf2_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<370, false>{645997859445244929063330092322131780655315027759230444092833483162360121242502066956072886951208394718844026880_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x44c40d0338806f3b0b9ff4bbf370134c_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xf2_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<370, false>{645997859445244929063330092322131780655315027759230444092833483162360121242502066956072886951208394718844026880_mpz};
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
TEST_CASE("bits_613")
{
  // 128'92329855051546774089237002099451013416 `<< 128'55 = 183'3326533606442543676308151207861214026039262387988594688
  {
    _Bits<128, false> lhs{92329855051546774089237002099451013416_u128};
    _Bits<128, false> rhs{55_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<183, false>{3326533606442543676308151207861214026039262387988594688_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{92329855051546774089237002099451013416_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{55_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<183, false>{3326533606442543676308151207861214026039262387988594688_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x457615508ee6b79a4bf94ac50050a928_b};
    _PossiblyUnknownBits<128, false> rhs{0x37_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<183, false>{3326533606442543676308151207861214026039262387988594688_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x457615508ee6b79a4bf94ac50050a928_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x37_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<183, false>{3326533606442543676308151207861214026039262387988594688_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_614")
{
  // 128'304186597602502710377672307582799912552 `<< 128'2 = 130'1216746390410010841510689230331199650208
  {
    _Bits<128, false> lhs{304186597602502710377672307582799912552_u128};
    _Bits<128, false> rhs{2_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<130, false>{1216746390410010841510689230331199650208_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{304186597602502710377672307582799912552_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{2_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<130, false>{1216746390410010841510689230331199650208_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0xe4d8352bda5b88107364ca46b49b1e68_b};
    _PossiblyUnknownBits<128, false> rhs{0x2_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<130, false>{1216746390410010841510689230331199650208_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xe4d8352bda5b88107364ca46b49b1e68_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x2_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<130, false>{1216746390410010841510689230331199650208_mpz};
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
TEST_CASE("bits_615")
{
  // 128'131281113679817972396725368456688952454 `<< 128'16 = 144'8603639066120550638991793747177567188025344
  {
    _Bits<128, false> lhs{131281113679817972396725368456688952454_u128};
    _Bits<128, false> rhs{16_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<144, false>{8603639066120550638991793747177567188025344_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{131281113679817972396725368456688952454_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{16_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<144, false>{8603639066120550638991793747177567188025344_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x62c3d2a2d06b7dd381f7eb6f4767e486_b};
    _PossiblyUnknownBits<128, false> rhs{0x10_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<144, false>{8603639066120550638991793747177567188025344_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x62c3d2a2d06b7dd381f7eb6f4767e486_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x10_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<144, false>{8603639066120550638991793747177567188025344_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs != result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_616")
{
  // 128'315371755308642362299596001050505666373 `<< 128'59 = 187'181799439320471166282712342175270406047236785950659969024
  {
    _Bits<128, false> lhs{315371755308642362299596001050505666373_u128};
    _Bits<128, false> rhs{59_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<187, false>{181799439320471166282712342175270406047236785950659969024_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{315371755308642362299596001050505666373_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{59_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<187, false>{181799439320471166282712342175270406047236785950659969024_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0xed426405fb8e58c0f98010ab27325f45_b};
    _PossiblyUnknownBits<128, false> rhs{0x3b_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<187, false>{181799439320471166282712342175270406047236785950659969024_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0xed426405fb8e58c0f98010ab27325f45_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x3b_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<187, false>{181799439320471166282712342175270406047236785950659969024_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_617")
{
  // 128'171423497662509698457903349099680065902 `<< 128'71 = 199'404762289868859386127379433493484949913530628440288076496896
  {
    _Bits<128, false> lhs{171423497662509698457903349099680065902_u128};
    _Bits<128, false> rhs{71_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<199, false>{404762289868859386127379433493484949913530628440288076496896_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{171423497662509698457903349099680065902_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{71_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<199, false>{404762289868859386127379433493484949913530628440288076496896_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x80f6f6f8acd947b85deeee64715d696e_b};
    _PossiblyUnknownBits<128, false> rhs{0x47_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<199, false>{404762289868859386127379433493484949913530628440288076496896_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x80f6f6f8acd947b85deeee64715d696e_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x47_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<199, false>{404762289868859386127379433493484949913530628440288076496896_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_618")
{
  // 128'134521165628551899111703184300535975598 `<< 128'56 = 184'9693271542371057714725184905022330537181524460178505728
  {
    _Bits<128, false> lhs{134521165628551899111703184300535975598_u128};
    _Bits<128, false> rhs{56_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<184, false>{9693271542371057714725184905022330537181524460178505728_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{134521165628551899111703184300535975598_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{56_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<184, false>{9693271542371057714725184905022330537181524460178505728_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x6533d587d374da1e9b7936bb94500eae_b};
    _PossiblyUnknownBits<128, false> rhs{0x38_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<184, false>{9693271542371057714725184905022330537181524460178505728_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x6533d587d374da1e9b7936bb94500eae_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x38_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<184, false>{9693271542371057714725184905022330537181524460178505728_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs < lhs);
    REQUIRE(lhs < result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result >= rhs);
  }
}
TEST_CASE("bits_619")
{
  // 128'156482959448947495503997647594235721432 `<< 128'230 = 358'270001423427937327932881610463201477754996289592305264999754258015490222004210724693045607599015620633427968
  {
    _Bits<128, false> lhs{156482959448947495503997647594235721432_u128};
    _Bits<128, false> rhs{230_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<358, false>{270001423427937327932881610463201477754996289592305264999754258015490222004210724693045607599015620633427968_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{156482959448947495503997647594235721432_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{230_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<358, false>{270001423427937327932881610463201477754996289592305264999754258015490222004210724693045607599015620633427968_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result != lhs);
    REQUIRE(rhs != result);
    REQUIRE(result >= rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x75b98590ae52fab3ec606c85314d76d8_b};
    _PossiblyUnknownBits<128, false> rhs{0xe6_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<358, false>{270001423427937327932881610463201477754996289592305264999754258015490222004210724693045607599015620633427968_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x75b98590ae52fab3ec606c85314d76d8_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xe6_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<358, false>{270001423427937327932881610463201477754996289592305264999754258015490222004210724693045607599015620633427968_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs >= rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs < result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
}
TEST_CASE("bits_620")
{
  // 128'157525678491404393280650140279298852675 `<< 128'151 = 279'449656322337595542799771725720902970126694394997244322927900517119642283496859238400
  {
    _Bits<128, false> lhs{157525678491404393280650140279298852675_u128};
    _Bits<128, false> rhs{151_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<279, false>{449656322337595542799771725720902970126694394997244322927900517119642283496859238400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs != result);
    REQUIRE(result != lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result >= rhs);
  }
  {
    _RuntimeBits<128, false> lhs{Bits<128>{157525678491404393280650140279298852675_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{151_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<279, false>{449656322337595542799771725720902970126694394997244322927900517119642283496859238400_mpz};
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
    _PossiblyUnknownBits<128, false> lhs{0x7682579548d72eb7244112f016c80743_b};
    _PossiblyUnknownBits<128, false> rhs{0x97_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<279, false>{449656322337595542799771725720902970126694394997244322927900517119642283496859238400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs != lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result != rhs);
  }
  {
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x7682579548d72eb7244112f016c80743_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0x97_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<279, false>{449656322337595542799771725720902970126694394997244322927900517119642283496859238400_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs > rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs <= result);
    REQUIRE(result > lhs);
    REQUIRE(rhs <= result);
    REQUIRE(result > rhs);
  }
}
TEST_CASE("bits_621")
{
  // 128'178001136642232585774762713186161522006 `<< 128'205 = 333'9153177548535888723318837803167995070529563980420500789190322610789055874006742783557895739714568192
  {
    _Bits<128, false> lhs{178001136642232585774762713186161522006_u128};
    _Bits<128, false> rhs{205_u128};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<333, false>{9153177548535888723318837803167995070529563980420500789190322610789055874006742783557895739714568192_mpz};
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
    _RuntimeBits<128, false> lhs{Bits<128>{178001136642232585774762713186161522006_u128}, Bits<32>{128}};
    _RuntimeBits<128, false> rhs{Bits<128>{205_u128}, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<333, false>{9153177548535888723318837803167995070529563980420500789190322610789055874006742783557895739714568192_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result >= lhs);
    REQUIRE(rhs < result);
    REQUIRE(result > rhs);
  }
  {
    _PossiblyUnknownBits<128, false> lhs{0x85e9c59c82e9214c379bd8a39aa1f556_b};
    _PossiblyUnknownBits<128, false> rhs{0xcd_b};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<333, false>{9153177548535888723318837803167995070529563980420500789190322610789055874006742783557895739714568192_mpz};
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
    _PossiblyUnknownRuntimeBits<128, false> lhs{0x85e9c59c82e9214c379bd8a39aa1f556_b, Bits<32>{128}};
    _PossiblyUnknownRuntimeBits<128, false> rhs{0xcd_b, Bits<32>{128}};
    auto result = lhs.widening_sll(rhs);
    auto expected = _Bits<333, false>{9153177548535888723318837803167995070529563980420500789190322610789055874006742783557895739714568192_mpz};
    REQUIRE(result == expected);
    REQUIRE(result.width() == expected.width());
    REQUIRE(lhs != rhs);
    REQUIRE(rhs <= lhs);
    REQUIRE(lhs != result);
    REQUIRE(result > lhs);
    REQUIRE(rhs < result);
    REQUIRE(result != rhs);
  }
}
