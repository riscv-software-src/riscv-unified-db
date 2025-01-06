#pragma once

#include <fmt/format.h>

#include "udb/defines.hpp"

#include "udb/types.hpp"

namespace udb {
  // XRegister class represents a general purpose X register in a hart
  //
  // The class just wraps an XReg (primitive integral) type, with the caveat
  // that an XRegister can be declared a "ZeroReg," in which case all assignments
  // are ignored
  //
  // This class just lets us pass around X register references without having
  // to do explicit zero index checks all over the place
  template <unsigned XLEN>
  class XRegister {
    public:
    using XReg = Bits<XLEN>;

    XRegister() : m_value(0), m_zero_reg(false) {}
    XRegister(const XRegister& other) : m_value(other.m_value), m_zero_reg(other.m_zero_reg) {}
    XRegister(const XReg& value) : m_value(value), m_zero_reg(false) {}

    void makeZeroReg() { m_zero_reg = true; }

    XReg get() const { return m_value; }
    operator XReg() const { return m_value; }
    XRegister& operator=(const XRegister& other) {
      if (!m_zero_reg) {
        m_value = other.m_value;
      }
      return *this;
    }
    XRegister& operator=(const XReg& other) {
      if (!m_zero_reg) {
        m_value = other;
      }
      return *this;
    }

#define BINARY_ARITH_OP(op)   \
    template <unsigned XLEN2>  \
    friend XReg operator op(const XRegister<XLEN2>& lhs, const XRegister<XLEN2>& rhs); \
    template <unsigned XLEN2>  \
    friend XReg operator op(const XRegister<XLEN2>& lhs, const XReg& rhs); \
    template <unsigned XLEN2>  \
    friend XReg operator op(const XReg& lhs, const XRegister<XLEN2>& rhs);

    BINARY_ARITH_OP(+)
    BINARY_ARITH_OP(-)
    BINARY_ARITH_OP(*)
    BINARY_ARITH_OP(/)
    BINARY_ARITH_OP(%)
    BINARY_ARITH_OP(^)
    BINARY_ARITH_OP(&)
    BINARY_ARITH_OP(|)
    BINARY_ARITH_OP(>>)
    BINARY_ARITH_OP(<<)

#undef BINARY_ARITH_OP

#define BINARY_LOGICAL_OP(op)   \
    template <unsigned XLEN2>  \
    friend bool operator op(const XRegister<XLEN2>& lhs, const XRegister<XLEN2>& rhs); \
    template <unsigned XLEN2>  \
    friend bool operator op(const XRegister<XLEN2>& lhs, const XReg& rhs); \
    template <unsigned XLEN2>  \
    friend bool operator op(const XReg& lhs, const XRegister<XLEN2>& rhs);

    BINARY_LOGICAL_OP(<)
    BINARY_LOGICAL_OP(>)
    BINARY_LOGICAL_OP(==)
    BINARY_LOGICAL_OP(!=)
    BINARY_LOGICAL_OP(<=)
    BINARY_LOGICAL_OP(>=)
    // BINARY_LOGICAL_OP(&&) // will be automatically generated
    // BINARY_LOGICAL_OP(||) // will be automatically generated

#undef BINARY_LOGICAL_OP

#define UNARY_ARITH_OP(op) \
    XReg operator op() const { return op(m_value); }

    UNARY_ARITH_OP(-)
    UNARY_ARITH_OP(~)
    UNARY_ARITH_OP(!)

#undef UNARY_ARITH_OP

    // prefix
    XRegister& operator++() {
      m_value++;
      return *this;
    }
    XRegister& operator--() {
      m_value--;
      return *this;
    }

    // postfix
    XReg operator++(int) {
      XReg old = m_value;
      m_value++;
      return old;
    }

    XReg operator--(int) {
      XReg old = m_value;
      m_value--;
      return old;
    }

#define BINARY_ARITH_ASSIGN_OP(op) \
    XRegister& operator op(const XRegister& other) {  \
      if (!m_zero_reg) {                              \
        m_value op other.m_value;                     \
      }                                               \
      return *this;                                   \
    }                                                 \
    XRegister& operator op(const XReg& other) {       \
      if (!m_zero_reg) {                              \
        m_value op other;                             \
      }                                               \
      return *this;                                   \
    }

    BINARY_ARITH_ASSIGN_OP(+=)
    BINARY_ARITH_ASSIGN_OP(-=)
    BINARY_ARITH_ASSIGN_OP(*=)
    BINARY_ARITH_ASSIGN_OP(/=)
    BINARY_ARITH_ASSIGN_OP(%=)
    BINARY_ARITH_ASSIGN_OP(^=)
    BINARY_ARITH_ASSIGN_OP(&=)
    BINARY_ARITH_ASSIGN_OP(|=)
    BINARY_ARITH_ASSIGN_OP(>>=)
    BINARY_ARITH_ASSIGN_OP(<<=)

    auto operator<=>(const XRegister& other) const { return m_value <=> other.m_value; }

    private:
    XReg m_value;
    bool m_zero_reg;
  };

#define BINARY_ARITH_OP(op)                                              \
  template <unsigned XLEN>                                               \
  inline typename udb::XRegister<XLEN>::XReg operator op(const udb::XRegister<XLEN>& lhs, const udb::XRegister<XLEN>& rhs) {  \
    return lhs.m_value op rhs.m_value;                                   \
  }                                                                      \
  template <unsigned XLEN>                                               \
  inline typename udb::XRegister<XLEN>::XReg operator op(const udb::XRegister<XLEN>& lhs, const typename udb::XRegister<XLEN>::XReg& rhs) {       \
    return lhs.m_value op rhs;                                           \
  }                                                                      \
  template <unsigned XLEN>                                               \
  inline typename udb::XRegister<XLEN>::XReg operator op(const typename udb::XRegister<XLEN>::XReg& lhs, const udb::XRegister<XLEN>& rhs) {       \
    return lhs op rhs.m_value;                                           \
  }
} // namespace iss

BINARY_ARITH_OP(+)
BINARY_ARITH_OP(-)
BINARY_ARITH_OP(*)
BINARY_ARITH_OP(/)
BINARY_ARITH_OP(%)
BINARY_ARITH_OP(^)
BINARY_ARITH_OP(&)
BINARY_ARITH_OP(|)
BINARY_ARITH_OP(>>)
BINARY_ARITH_OP(<<)

#undef BINARY_ARITH_OP

#define BINARY_LOGICAL_OP(op)                                            \
template <unsigned XLEN>                                               \
inline bool operator op(const udb::XRegister<XLEN>& lhs, const udb::XRegister<XLEN>& rhs) {  \
  return lhs.m_value op rhs.m_value;                                   \
}                                                                      \
template <unsigned XLEN>                                               \
inline bool operator op(const udb::XRegister<XLEN>& lhs, const typename udb::XRegister<XLEN>::XReg& rhs) {       \
  return lhs.m_value op rhs;                                           \
}                                                                      \
template <unsigned XLEN>                                               \
inline bool operator op(const typename udb::XRegister<XLEN>::XReg& lhs, const udb::XRegister<XLEN>& rhs) {       \
  return lhs op rhs.m_value;                                           \
}

BINARY_LOGICAL_OP(<)
BINARY_LOGICAL_OP(>)
BINARY_LOGICAL_OP(==)
BINARY_LOGICAL_OP(!=)
BINARY_LOGICAL_OP(<=)
BINARY_LOGICAL_OP(>=)
// BINARY_LOGICAL_OP(&&) // will be automatically generated
// BINARY_LOGICAL_OP(||) // will be automatically generated

#undef BINARY_LOGICAL_OP

// format XRegister as an XReg (integral) when using format()
template <unsigned XLEN>
struct fmt::formatter<udb::XRegister<XLEN>>: formatter<typename udb::XRegister<XLEN>::XReg> {
  template <typename CONTEXT_TYPE>
  auto format(udb::XRegister<XLEN> value, CONTEXT_TYPE& ctx) const {
    return fmt::formatter<typename udb::XRegister<XLEN>::XReg>::format((typename udb::XRegister<XLEN>::XReg) value, ctx);
  }
};
