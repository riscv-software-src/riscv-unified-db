#pragma once

#include <string>
#include <stdexcept>

namespace udb {
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
      Op(const OpKind& kind)
        : m_kind(kind)
      {}

      bool operator==(const Op& other) const { return m_kind == other.m_kind; }
      bool operator==(const OpKind& other) const { return m_kind == other; }
      bool operator!=(const Op& other) const { return m_kind != other.m_kind; }
      bool operator!=(const OpKind& other) const { return m_kind != other; }

    private:
      OpKind m_kind;
    };

    VersionRequirement(const std::string& req);
    VersionRequirement(const OpKind& op_kind, unsigned major, unsigned minor, unsigned patch, bool pre)
      : m_op(op_kind), m_major(major), m_minor(minor), m_patch(patch), m_pre(pre)
    {}

  private:
    Op m_op;
    unsigned m_major;
    unsigned m_minor;
    unsigned m_patch;
    bool m_pre;
  };
}
