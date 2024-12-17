#include <udb/version.hpp>

#include <catch2/catch_test_macros.hpp>

using namespace udb;

TEST_CASE("major only", "[version]") {
  VersionRequirement r { ">= 2"};
  REQUIRE(r.major() == 2);
  REQUIRE(r.minor() == 0);
  REQUIRE(r.patch() == 0);
  REQUIRE(r.pre() == false);
}
