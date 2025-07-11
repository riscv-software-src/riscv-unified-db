
#include <catch2/catch_test_macros.hpp>
#include <udb/defines.hpp>
#include <udb/util.hpp>

using namespace udb;

TEST_CASE("concat", "[util]") {
  Bits<4> a{0x1};
  Bits<4> b{0x2};
  Bits<4> c{0x3};
  REQUIRE(concat(a, b, c) == 0x123_b);
}
