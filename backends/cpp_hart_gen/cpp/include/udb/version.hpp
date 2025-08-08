#pragma once

#include <fmt/core.h>

#include <compare>
#include <ctre.hpp>
#include <stdexcept>
#include <string>
#include <string_view>

#include "udb/defines.hpp"

#if !defined(__cpp_lib_constexpr_charconv) || \
    (__cpp_lib_constexpr_charconv < 202207L)
#error "No conexpr from_char"
#endif

using namespace std::literals;

namespace udb {
  class Version {
   public:
    Version() = default;
    constexpr Version(const std::string_view& ver_str) { set(ver_str); }
    Version(const std::string& ver_str) { set(ver_str); }
    constexpr Version(unsigned major, unsigned minor, unsigned patch, bool pre)
        : m_major(major), m_minor(minor), m_patch(patch), m_pre(pre) {}

    constexpr void set(const std::string_view& ver_str) {
      auto result =
          ctre::match<"(([0-9]+)(?:\\.([0-9]+)(?:\\.([0-9]+)(?:-(pre))?)?)?)">(
              ver_str);
      if (!result) {
        throw std::runtime_error(
            fmt::format("Bad version string '{}'", ver_str));
      }
      m_major = result.get<1>().to_number<unsigned>();
      m_minor = 0;
      m_patch = 0;
      m_pre = false;
      if (!result.get<3>().str().empty()) {
        m_minor = result.get<3>().to_number<unsigned>();
      }
      if (!result.get<4>().str().empty()) {
        m_patch = result.get<4>().to_number<unsigned>();
      }
      if (!result.get<5>().str().empty()) {
        m_pre = true;
      }
    }
    constexpr void set(unsigned major, unsigned minor, unsigned patch,
                       bool pre) {
      m_major = major;
      m_minor = minor;
      m_patch = patch;
      m_pre = pre;
    }

    constexpr std::strong_ordering operator<=>(const Version& other) const {
      if (m_major != other.m_major) {
        return m_major <=> other.m_major;
      } else if (m_minor != other.m_minor) {
        return m_minor <=> other.m_minor;
      } else if (m_patch != other.m_patch) {
        return m_patch <=> other.m_patch;
      } else {
        return m_pre == other.m_pre ? std::strong_ordering::equivalent
                                    : (m_pre ? std::strong_ordering::less
                                             : std::strong_ordering::greater);
      }
    }
    constexpr bool operator==(const Version& other) const {
      return m_major == other.m_major && m_minor == other.m_minor &&
             m_patch == other.m_patch && m_pre == other.m_pre;
    }

    constexpr unsigned major() const { return m_major; }
    constexpr unsigned minor() const { return m_minor; }
    constexpr unsigned patch() const { return m_patch; }
    constexpr bool pre() const { return m_pre; }

   private:
    unsigned m_major;
    unsigned m_minor;
    unsigned m_patch;
    bool m_pre;
  };

  static_assert(Version{"1.2.3"sv}.major() == 1, "Bad major");
  static_assert(Version{"1.2.3"sv}.minor() == 2, "Bad minor");
  static_assert(Version{"1.2.3"sv}.patch() == 3, "Bad patch");
  static_assert(Version{"1.2.3"sv}.pre() == false, "Bad pre");
  static_assert(Version{"1.2.3-pre"sv}.pre() == true, "Bad pre");
  static_assert(Version{"1"sv}.major() == 1, "Bad major");
  static_assert(Version{"1"sv}.minor() == 0, "Bad minor");
  static_assert(Version{"1"sv}.patch() == 0, "Bad patch");
  static_assert(Version{"1"sv}.pre() == false, "Bad pre");

  class VersionRequirement {
   public:
    enum class OpKind : unsigned { INVALID, GTE, LTE, GT, LT, EQ, NE, COMPAT };

    class Op {
     public:
      Op() : m_kind(OpKind::INVALID) {}
      constexpr Op(const std::string_view& op) { set(op); }
      constexpr Op(const OpKind& kind) : m_kind(kind) {}

      constexpr void set(const std::string_view& op) {
        if (op == ">=") {
          m_kind = OpKind::GTE;
        } else if (op == ">") {
          m_kind = OpKind::GT;
        } else if (op == "<=") {
          m_kind = OpKind::LTE;
        } else if (op == "<") {
          m_kind = OpKind::LT;
        } else if (op == "=") {
          m_kind = OpKind::EQ;
        } else if (op == "!=") {
          m_kind = OpKind::NE;
        } else if (op == "~>") {
          m_kind = OpKind::COMPAT;
        } else {
          throw std::runtime_error("Invalid operator");
        }
      }

      constexpr bool operator==(const Op& other) const {
        return m_kind == other.m_kind;
      }
      constexpr bool operator==(const OpKind& other) const {
        return m_kind == other;
      }
      constexpr bool operator!=(const Op& other) const {
        return m_kind != other.m_kind;
      }
      constexpr bool operator!=(const OpKind& other) const {
        return m_kind != other;
      }

      constexpr OpKind kind() const { return m_kind; }

     private:
      OpKind m_kind;
    };

    // default requirement is >= 0
    VersionRequirement() : m_op(OpKind::GTE), m_version(0, 0, 0, false) {}

    constexpr VersionRequirement(const std::string_view& req)
        : m_op(op_from_str(req)) {
      set(req);
    }
    constexpr VersionRequirement(const OpKind& op_kind, unsigned major,
                                 unsigned minor, unsigned patch, bool pre)
        : m_op(op_kind), m_version(major, minor, patch, pre) {}

    constexpr Op op_from_str(const std::string_view& req) {
      auto result = ctre::match<
          "((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))\\s*(([0-9]+)(?:\\.(["
          "0-9]"
          "+)(?:\\.([0-9]+)(?:-(pre))?)?)?)">(req);

      if (!result) {
        throw std::runtime_error(
            fmt::format("Bad version requirement string '{}'", req));
      }

      return static_cast<OpKind>(result.get<1>().to_number<unsigned>());
    }
    constexpr void set(const std::string_view& req) {
      auto result = ctre::match<
          "((?:>=)|(?:>)|(?:~>)|(?:<)|(?:<=)|(?:!=)|(?:=))\\s*(([0-9]+)(?:\\.(["
          "0-9]"
          "+)(?:\\.([0-9]+)(?:-(pre))?)?)?)">(req);

      if (!result) {
        throw std::runtime_error(
            fmt::format("Bad version requirement string '{}'", req));
      }

      m_op.set(result.get<1>());
      m_version.set(result.get<2>());
    }

    constexpr Op op() const { return m_op; }
    constexpr unsigned major() const { return m_version.major(); }
    constexpr unsigned minor() const { return m_version.minor(); }
    constexpr unsigned patch() const { return m_version.patch(); }
    constexpr bool pre() const { return m_version.pre(); }

    constexpr bool satisfied_by(const Version& version) const {
      switch (m_op.kind()) {
        case OpKind::COMPAT:
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
         return false;
      }
      udb_unreachable();
    }

   private:
    Op m_op;
    Version m_version;
  };
}  // namespace udb
