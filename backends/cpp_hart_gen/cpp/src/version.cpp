#include "udb/version.hpp"

#include <fmt/core.h>
#include <fmt/std.h>

#include <regex>
#include <string>

#include "udb/defines.hpp"

using namespace udb;

void Version::set(const std::string& version) {
  std::regex req_regex{"(([0-9]+)(?:\\.([0-9]+)(?:\\.([0-9]+)(?:-(pre))?)?)?)",
                       std::regex_constants::ECMAScript};
  std::smatch result;
  if (!std::regex_match(version, result, req_regex)) {
    throw std::runtime_error(fmt::format("Bad version string '{}'", version));
  }
  m_major = std::stoul(result[1].str());
  m_minor = 0;
  m_patch = 0;
  m_pre = false;
  if (!result[3].str().empty()) {
    m_minor = std::stoul(result[3].str());
  }
  if (!result[4].str().empty()) {
    m_patch = std::stoul(result[4].str());
  }
  if (!result[5].str().empty()) {
    m_pre = true;
  }
}

void VersionRequirement::set(const std::string& version) {
  std::regex req_regex{
      "((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))\\s*(([0-9]+)(?:\\.([0-9]"
      "+)(?:\\.([0-9]+)(?:-(pre))?)?)?)",
      std::regex_constants::ECMAScript};

  std::smatch result;

  if (!std::regex_match(version, result, req_regex)) {
    throw std::runtime_error(
        fmt::format("Bad version requirement string '{}'", version));
  }

  m_op.set(result[1].str());
  fmt::print("ver = {}\n", result[2].str());
  m_version.set(result[2].str());
}

bool VersionRequirement::satisfied_by(const Version& version) {
  switch (m_op.kind()) {
    case OpKind::GTE:
      return version >= m_version;
    case OpKind::LTE:
      return version <= m_version;
    case OpKind::GT:
      return version > m_version;
    case OpKind::LT:
      return version < m_version;
    case OpKind::EQ:
      return version == m_version;
    case OpKind::NE:
      return version != m_version;
    default:
      throw std::runtime_error("Bad op?");
  }
  udb_unreachable();
}
