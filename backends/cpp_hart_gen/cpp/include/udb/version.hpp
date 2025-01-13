#pragma once

#include <compare>
#include <string>
#include <stdexcept>

namespace udb {
  class Version {
  public:
    Version() = default;
    Version(const std::string& ver_str) { set(ver_str); }
    Version(unsigned major, unsigned minor, unsigned patch, bool pre)
      : m_major(major), m_minor(minor), m_patch(patch), m_pre(pre)
    {}

    void set(const std::string& ver_str);
    void set(unsigned major, unsigned minor, unsigned patch, bool pre)
    {
      m_major = major;
      m_minor = minor;
      m_patch = patch;
      m_pre = pre;
    }

    std::strong_ordering operator<=>(const Version& other) const {
      if (m_major != other.m_major) {
        return m_major <=> other.m_major;
      } else if (m_minor != other.m_minor) {
        return m_minor <=> other.m_minor;
      } else if (m_patch != other.m_patch) {
        return m_patch <=> other.m_patch;
      } else {
        return m_pre == other.m_pre ? std::strong_ordering::equivalent : (m_pre ? std::strong_ordering::less : std::strong_ordering::greater);
      }
    }
    bool operator==(const Version& other) const {
      return \
        m_major == other.m_major && \
        m_minor == other.m_minor && \
        m_patch == other.m_patch && \
        m_pre == other.m_pre;
    }

    unsigned major() const { return m_major; }
    unsigned minor() const { return m_minor; }
    unsigned patch() const { return m_patch; }
    bool pre() const { return m_pre; }

  private:
    unsigned m_major;
    unsigned m_minor;
    unsigned m_patch;
    bool m_pre;
  };

  class VersionRequirement {
  public:
    enum class OpKind : unsigned {
      INVALID,
      GTE,
      LTE,
      GT,
      LT,
      EQ,
      NE,
      COMPAT
    };

    class Op {
    public:
      Op() : m_kind(OpKind::INVALID) {}
      Op(const std::string& op) {
        set(op);
      }
      Op(const OpKind& kind)
        : m_kind(kind)
      {}

      void set(const std::string& op) {
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
          throw std::runtime_error("Invalid operator: " + op);
        }
      }

      bool operator==(const Op& other) const { return m_kind == other.m_kind; }
      bool operator==(const OpKind& other) const { return m_kind == other; }
      bool operator!=(const Op& other) const { return m_kind != other.m_kind; }
      bool operator!=(const OpKind& other) const { return m_kind != other; }

      const OpKind& kind() const { return m_kind; }

    private:
      OpKind m_kind;
    };

    // default requiremnt is >= 0
    VersionRequirement() : m_op(OpKind::GTE), m_version(0,0,0,false) {}

    VersionRequirement(const std::string& req) { set(req); }
    VersionRequirement(const OpKind& op_kind, unsigned major, unsigned minor, unsigned patch, bool pre)
      : m_op(op_kind), m_version(major, minor, patch, pre)
    {}

    void set(const std::string& req);

    Op op() const { return m_op; }
    unsigned major() const { return m_version.major(); }
    unsigned minor() const { return m_version.minor(); }
    unsigned patch() const { return m_version.patch(); }
    bool pre() const { return m_version.pre(); }

    bool satisfied_by(const Version& version);

  private:
    Op m_op;
    Version m_version;
  };
}
