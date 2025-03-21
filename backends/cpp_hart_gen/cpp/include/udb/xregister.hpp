#pragma once

#include <fmt/format.h>

#include <utility>

#include "udb/bitfield.hpp"
#include "udb/bits.hpp"
#include "udb/defines.hpp"

namespace udb {
  // XRegister class represents a general purpose X register in a hart
  //
  // The class just wraps an XReg (primitive integral) type, with the caveat
  // that an XRegister can be declared a "ZeroReg," in which case all
  // assignments are ignored
  //
  // This class just lets us pass around X register references without having
  // to do explicit zero index checks all over the place
  template <unsigned XLEN>
  class XRegister {
   public:
    using ValueType = Bits<XLEN>;
    using ValueTypeCRef =
        std::add_const_t<std::add_lvalue_reference_t<ValueType>>;

    XRegister() : m_value(0), m_zero_reg(false) {}
    XRegister(const XRegister &other)
        : m_value(other.m_value), m_zero_reg(other.m_zero_reg) {}
    XRegister(const ValueType &value) : m_value(value), m_zero_reg(false) {}

    void makeZeroReg() { m_zero_reg = true; }

    ValueType &get() { return m_value; }
    ValueType get() const { return m_value; }

    template <unsigned N>
    operator Bits<N>() const {
      return m_value;
    }

    XRegister &operator=(const XRegister &other) {
      if (!m_zero_reg) {
        m_value = other.m_value;
      }
      return *this;
    }
    template <typename T>
      requires(std::integral<T> || T::IsABits)
    XRegister &operator=(const T &other) {
      if (!m_zero_reg) {
        m_value = other;
      }
      return *this;
    }

    template <unsigned MaxN, bool Signed>
    XRegister &operator=(const _RuntimeBits<MaxN, Signed> &other) {
      if (!m_zero_reg) {
        m_value = other.value();
      }
      return *this;
    }

    template <typename T>
    decltype(std::declval<ValueType>().sra(std::declval<T>())) sra(
        const T &shamt) const {
      return m_value.sra(shamt);
    }

#define UNARY_ARITH_OP(op) \
  ValueType operator op() const { return op(m_value); }

    UNARY_ARITH_OP(-)
    UNARY_ARITH_OP(~)
    UNARY_ARITH_OP(!)

#undef UNARY_ARITH_OP

    // prefix
    XRegister &operator++() {
      m_value++;
      return *this;
    }
    XRegister &operator--() {
      m_value--;
      return *this;
    }

    // postfix
    ValueType operator++(int) {
      ValueType old = m_value;
      m_value++;
      return old;
    }

    ValueType operator--(int) {
      ValueType old = m_value;
      m_value--;
      return old;
    }

#define BINARY_ARITH_ASSIGN_OP(op)                  \
  XRegister &operator op(const XRegister & other) { \
    if (!m_zero_reg) {                              \
      m_value op other.m_value;                     \
    }                                               \
    return *this;                                   \
  }                                                 \
  XRegister &operator op(const ValueType & other) { \
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

    auto operator<=>(const XRegister &other) const {
      return m_value <=> other.m_value;
    }

   private:
    ValueType m_value;
    bool m_zero_reg;
  };
}  // namespace udb

#define BINARY_ARITH_OP(op)                                                    \
  template <unsigned XLEN>                                                     \
  inline decltype(std::declval<                                                \
                  const typename udb::XRegister<XLEN>::ValueType &>()          \
                      op std::declval<                                         \
                          const typename udb::XRegister<XLEN>::ValueType &>()) \
  operator op(const udb::XRegister<XLEN> &lhs,                                 \
              const udb::XRegister<XLEN> &rhs) {                               \
    return lhs.get() op rhs.get();                                             \
  }                                                                            \
  template <unsigned XLEN, unsigned N, bool Signed>                            \
  inline decltype(std::declval<typename udb::XRegister<XLEN>::ValueTypeCRef>() \
                      op std::declval<udb::_Bits<N, Signed>>())                \
  operator op(const udb::XRegister<XLEN> &lhs,                                 \
              const udb::_Bits<N, Signed> &rhs) {                              \
    return lhs.get() op rhs;                                                   \
  }                                                                            \
  template <unsigned XLEN, unsigned N, bool Signed>                            \
  inline decltype(std::declval<const udb::_Bits<N, Signed> &>()                \
                      op std::declval<                                         \
                          typename udb::XRegister<XLEN>::ValueTypeCRef>())     \
  operator op(const udb::_Bits<N, Signed> &lhs,                                \
              const udb::XRegister<XLEN> &rhs) {                               \
    return lhs op rhs.get();                                                   \
  }                                                                            \
  template <unsigned XLEN, typename T>                                         \
    requires(std::integral<T>)                                                 \
  inline decltype(std::declval<                                                \
                  const typename udb::XRegister<XLEN>::ValueType &>()          \
                      op std::declval<const T &>())                            \
  operator op(const udb::XRegister<XLEN> &lhs, const T &rhs) {                 \
    return lhs.get() op rhs;                                                   \
  }                                                                            \
  template <unsigned XLEN, typename T>                                         \
    requires(std::integral<T>)                                                 \
  inline decltype(std::declval<const T &>() op std::declval<                   \
                  const typename udb::XRegister<XLEN>::ValueType &>())         \
  operator op(const T &lhs, const udb::XRegister<XLEN> &rhs) {                 \
    return lhs op rhs.get();                                                   \
  }

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

#define BINARY_LOGICAL_OP(op)                                                  \
  template <unsigned XLEN>                                                     \
  inline bool operator op(const udb::XRegister<XLEN> &lhs,                     \
                          const udb::XRegister<XLEN> &rhs) {                   \
    return lhs.get() op rhs.get();                                             \
  }                                                                            \
  template <unsigned XLEN>                                                     \
  inline bool operator op(udb::XRegister<XLEN> &lhs,                           \
                          udb::XRegister<XLEN> &rhs) {                         \
    return lhs.get() op rhs.get();                                             \
  }                                                                            \
  template <unsigned XLEN>                                                     \
  inline bool operator op(                                                     \
      const udb::XRegister<XLEN> &lhs,                                         \
      const typename udb::XRegister<XLEN>::ValueType &rhs) {                   \
    return lhs.get() op rhs;                                                   \
  }                                                                            \
  template <unsigned XLEN>                                                     \
  inline bool operator op(const typename udb::XRegister<XLEN>::ValueType &lhs, \
                          const udb::XRegister<XLEN> &rhs) {                   \
    return lhs op rhs.get();                                                   \
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
struct fmt::formatter<udb::XRegister<XLEN>>
    : formatter<typename udb::XRegister<XLEN>::ValueType> {
  template <typename CONTEXT_TYPE>
  auto format(udb::XRegister<XLEN> value, CONTEXT_TYPE &ctx) const {
    return fmt::formatter<typename udb::XRegister<XLEN>::ValueType>::format(
        (typename udb::XRegister<XLEN>::ValueType)value, ctx);
  }
};
