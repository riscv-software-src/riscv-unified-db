#include <catch2/catch_test_macros.hpp>
#include <udb/version.hpp>

using namespace std::literals;
using namespace udb;

TEST_CASE("major only", "[version]") {
  VersionRequirement r{">= 2"sv};
  REQUIRE(r.major() == 2);
  REQUIRE(r.minor() == 0);
  REQUIRE(r.patch() == 0);
  REQUIRE(r.pre() == false);
}

TEST_CASE("major and minor", "[version]") {
  VersionRequirement r{">= 2.1"sv};
  REQUIRE(r.major() == 2);
  REQUIRE(r.minor() == 1);
  REQUIRE(r.patch() == 0);
  REQUIRE(r.pre() == false);
}

TEST_CASE("major, minor,  and patch", "[version]") {
  VersionRequirement r{">= 2.1.3"sv};
  REQUIRE(r.major() == 2);
  REQUIRE(r.minor() == 1);
  REQUIRE(r.patch() == 3);
  REQUIRE(r.pre() == false);
}

TEST_CASE("major, minor, patch, and pre", "[version]") {
  VersionRequirement r{">= 2.1.3-pre"sv};
  REQUIRE(r.major() == 2);
  REQUIRE(r.minor() == 1);
  REQUIRE(r.patch() == 3);
  REQUIRE(r.pre() == true);
}

TEST_CASE("version ordering", "[version]") {
  Version v1("2.1.3"sv);
  Version v2("3.4"sv);

  REQUIRE(v1 < v2);
  REQUIRE(v1 <= v2);
  REQUIRE(v1 != v2);
  REQUIRE(v2 > v1);
  REQUIRE(v2 >= v1);
}

TEST_CASE("version ordering iwth pre", "[version]") {
  Version v1("2.1.3-pre"sv);
  Version v2("2.1.3"sv);

  REQUIRE(v1 < v2);
  REQUIRE(v1 <= v2);
  REQUIRE(v1 != v2);
  REQUIRE(v2 > v1);
  REQUIRE(v2 >= v1);
}

TEST_CASE("version requirement satisfaction", "[version]") {
  VersionRequirement req(">= 2.1.3"sv);
  Version v1("2.1.3"sv);
  Version v2("2.1.2"sv);
  Version v3("2.1.3-pre"sv);

  REQUIRE(req.satisfied_by(v1));
  REQUIRE(!req.satisfied_by(v2));
  REQUIRE(!req.satisfied_by(v3));

  req.set("< 2.1.3"sv);
  REQUIRE(!req.satisfied_by(v1));
  REQUIRE(req.satisfied_by(v2));
  REQUIRE(req.satisfied_by(v3));
}
