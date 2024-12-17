#include <fmt/core.h>
#include <regex>

#include "udb/version.hpp"

using namespace udb;

VersionRequirement::VersionRequirement(const std::string& version)
{
  std::regex req_regex {
    "((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))\\s*(([0-9]+)(?:\\.([0-9]+)(?:\\.([0-9]+)(?:-(pre))?)?)?)",
    std::regex_constants::ECMAScript
  };

  std::smatch result;

  if (!std::regex_match(version, result, req_regex)) {
    throw std::runtime_error(fmt::format("Bad version string '{}'", version));
  }

  auto op_match = result[1];
  auto ver_match = result[2];

}
