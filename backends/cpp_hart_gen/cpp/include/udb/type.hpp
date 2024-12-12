#pragma once


#include <cmath>
#include <bit>
#include <concepts>
#include <string>
#include <type_traits>
#include <limits>

#include <iss/defines.hpp>

#include ISS_FORMAT_INCLUDE
#include ISS_FORMATTER_INCLUDE

// extern "C" {
// #include "softfloat.h"
// }

namespace riscv {

  // empty struct used as the parent of any user-defined enum
  // we use this to identify enum types at compile time
  struct Enum { };

  template <unsigned N>
  static consteval bool is_power_of_2()
  {
    if constexpr (N == 0) {
      return true;
    } else {
      unsigned M = N;
      while ((M & 1) == 0) {
        M = M >> 1;
      }
      return M == 1;
    }
  }
  static_assert(is_power_of_2<128>());
  static_assert(is_power_of_2<64>());
  static_assert(is_power_of_2<32>());
  static_assert(is_power_of_2<16>());
  static_assert(is_power_of_2<32>());
  static_assert(is_power_of_2<16>());
  static_assert(is_power_of_2<8>());
  static_assert(is_power_of_2<4>());
  static_assert(is_power_of_2<2>());
  static_assert(is_power_of_2<1>());

  using uint128_t = unsigned __int128;
  using int128_t = __int128;

  struct __not_impl_type {
      constexpr __not_impl_type() = default;
      constexpr explicit __not_impl_type(const __not_impl_type& o) {}

      template <typename T, typename... Args>
        requires (!std::same_as<T, __not_impl_type>)
      constexpr __not_impl_type(T a, Args... args) {}

      template <typename T>
        requires (!std::convertible_to<T, __not_impl_type>)
      constexpr // required since C++14
      void operator=(T&&) const noexcept {}

      template <typename T>
      constexpr // required since C++14
      bool operator==(T&&) const noexcept { return false; }

  };

  template <unsigned N>
  struct BitsStorageType {
    static_assert(N <= 128, "Need to get unlimited precision implemented");

    using type =
      // std::conditional_t<(N > 1024), boost::multiprecision::uint1024_t, //boost::multiprecision::cpp_int,
        // std::conditional_t<(N > 512), boost::multiprecision::uint1024_t,
          // std::conditional_t<(N > 256), boost::multiprecision::uint512_t,
            // std::conditional_t<(N > 128), boost::multiprecision::uint256_t,
              std::conditional_t<(N > 64), uint128_t,
                std::conditional_t<(N > 32), uint64_t,
                  std::conditional_t<(N > 16), uint32_t,
                    std::conditional_t<(N > 8), uint16_t,
                      uint8_t>>>>;
                      // uint8_t>>>>>>>>;
  };

  template <unsigned N>
  struct BitsSignedStorageType {
    static_assert(N <= 128, "Need to get unlimited precision implemented");

    using type =
      // std::conditional_t<(N > 1024), boost::multiprecision::int1024_t, //boost::multiprecision::cpp_int,
        // std::conditional_t<(N > 512), boost::multiprecision::int1024_t,
          // std::conditional_t<(N > 256), boost::multiprecision::int512_t,
            // std::conditional_t<(N > 128), boost::multiprecision::int256_t,
              std::conditional_t<(N > 64), int128_t,
                std::conditional_t<(N > 32), int64_t,
                  std::conditional_t<(N > 16), int32_t,
                    std::conditional_t<(N > 8), int16_t,
                      int8_t>>>>;
                      // int8_t>>>>>>>>;
  };

  // used to hold compile-time-known-bit-width integer
  // When Strict is true, the underlying value is masked to ensure it never
  // holds a value larger than the max for N.
  // When Strict is false, there is no masking, so the underlying value could
  // be too big for the width (N), but performance is better
  template<unsigned N, bool Signed=false, bool Strict=true>
  class _Bits {
    public:
    constexpr static unsigned InfinitePrecision = 1025;
    constexpr static unsigned MaxPrecision = 128;

    private:
    template <unsigned M, bool _Signed, bool _Strict> friend class _Bits;

    template <unsigned _N = N>
    static consteval bool needs_mask()
    {
      if constexpr (Strict) {
        using _StorageType =
          std::conditional_t<Signed,
            typename BitsSignedStorageType<_N>::type,
            typename BitsStorageType<_N>::type>;
        if constexpr (std::integral<_StorageType>) {
          return _N != sizeof(_StorageType)*8;
        } else {
          if constexpr (_N >= InfinitePrecision) {
            return false;
          } else {
            return _N != std::numeric_limits<_StorageType>::digits;
          }
        }
      } else {
        return false;
      }
    }
    // static_assert(needs_mask<4>() == true);
    // static_assert(needs_mask<8>() == false);
    // static_assert(needs_mask<16>() == false);
    // static_assert(needs_mask<32>() == false);
    // static_assert(needs_mask<64>() == false);
    // static_assert(needs_mask<128>() == false);
    // static_assert(needs_mask<256>() == false);
    // static_assert(needs_mask<512>() == false);
    // static_assert(needs_mask<768>() == true);
    // static_assert(needs_mask<1024>() == false);
    // static_assert(needs_mask<1025>() == false);
    // static_assert(needs_mask<std::numeric_limits<unsigned>::max()>() == false);

    template <unsigned ..._N>
    struct constmax {
      template <unsigned A, unsigned B, unsigned... Nums>
      consteval static unsigned Max() {
        constexpr unsigned AorB = (A > B) ? A : B;
        if constexpr (sizeof...(Nums) > 0) {
          return Max<AorB, Nums...>();
        } else {
          return AorB;
        }
      }
      constexpr static unsigned value = Max<_N...>();
    };
    static_assert(constmax<std::numeric_limits<unsigned>::max(), std::numeric_limits<unsigned>::max()>::value == std::numeric_limits<unsigned>::max());

    public:
    using StorageType = std::conditional_t<Signed, typename BitsSignedStorageType<N>::type, typename BitsStorageType<N>::type>;
    static_assert((Signed && std::is_signed_v<StorageType>) || (!Signed && std::is_unsigned_v<StorageType>));

    template <unsigned _N>
    static consteval bool fits_in_storage() {
      return std::same_as<typename BitsStorageType<N>::type, typename BitsStorageType<_N>::type>;
    }

    constexpr _Bits() : m_val(0) {}
    constexpr _Bits(const _Bits&) = default;
    _Bits(_Bits&&) noexcept = default;

    // same N, opposite sign
    template <bool _Strict>
    constexpr _Bits(const _Bits<N, !Signed, _Strict>& o)
      : m_val(static_cast<StorageType>(o.m_val)) {}
    template <bool _Strict>
    constexpr _Bits(_Bits<N, !Signed, _Strict>&& o) noexcept
      : m_val(static_cast<StorageType>(std::move(o.m_val))) {}

    // different N, potentially different sign, no mask needed
    template <unsigned M, bool _Signed, bool _Strict>
      requires ((M != N) && !needs_mask())
    constexpr _Bits(const _Bits<M, _Signed, _Strict>& o)
     : m_val(o.m_val)
     {}
    template <unsigned M, bool _Signed, bool _Strict>
      requires ((M != N) && !needs_mask())
    constexpr _Bits(_Bits<M, _Signed, _Strict>&& o) noexcept
     : m_val(std::move(o.m_val))
     {}

    // different N, potentially different sign, mask needed
    template <unsigned M, bool _Signed, bool _Strict>
      requires ((M != N) && needs_mask())
    constexpr _Bits(const _Bits<M, _Signed, _Strict>& o)
     : m_val(maskIntegral(o.m_val))
    {
    }
    template <unsigned M, bool _Signed, bool _Strict>
      requires ((M != N) && needs_mask())
    constexpr _Bits(_Bits<M, _Signed, _Strict>&& o) noexcept
     : m_val(maskIntegral(std::move(o.m_val)))
    {
    }

    // built-in integer type, mask needed
    template <class IntType>
      requires (std::integral<IntType> && needs_mask())
    constexpr _Bits(const IntType& val)
      : m_val(maskIntegral(val))
    {}
    template <class IntType>
      requires (std::integral<IntType> && needs_mask())
    constexpr _Bits(IntType&& val) noexcept
      : m_val(maskIntegral(std::move(val)))
    {}

    // built-in integer type, no mask needed
    template <class IntType>
      requires (std::integral<IntType> && !needs_mask())
    constexpr _Bits(const IntType& val)
      : m_val(val)
    {}
    template <class IntType>
      requires (std::integral<IntType> && !needs_mask())
    constexpr _Bits(IntType&& val) noexcept
      : m_val(std::move(val))
    {}

    // SPR
    template <typename T>
      requires requires (T a) { a.hw_read(); }
    constexpr explicit _Bits(const T& f)
      : m_val(f.hw_read())
    {}

    // boost multiprecision
    // template <typename Op, typename T1, typename T2, typename T3, typename T4>
    // constexpr _Bits(const boost::multiprecision::detail::expression<Op, T1, T2, T3, T4>& val)
    //   : m_val(val)
    // {}
    // template <typename Op, typename T1, typename T2, typename T3, typename T4>
    // constexpr _Bits(boost::multiprecision::detail::expression<Op, T1, T2, T3, T4>&& val) noexcept
    //   : m_val(std::move(val))
    // {}
    // template <typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits(const boost::multiprecision::number<Backend, E>& val)
    //   : m_val(val)
    // {}
    // template <typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits(boost::multiprecision::number<Backend, E>&& val) noexcept
    //   : m_val(std::move(val))
    // {}
    constexpr ~_Bits() noexcept = default;

    uint64_t msb() const {
      if constexpr ( N > 128 ) {
        static_assert(N <= 128);
        // return boost::multiprecision::msb(m_val);
      } else {
        static_assert("msb() only available for integer_t");
      }
      return 0; // REMOVE WHEN multiprecision is added back
    }

    template <unsigned _N, typename T = StorageType>
    consteval static T make_wide_mask() {
      if constexpr (_N >= InfinitePrecision) {
        return ~static_cast<T>(0);
      } else {
        if constexpr (_N == 0) {
          return 0;
        } else {
          return static_cast<T>(
            (static_cast<BitsStorageType<_N + 1>::type>(1) << _N)
            - static_cast<BitsStorageType<_N + 1>::type>(1)
          );
        }
      }
    }
    static_assert(make_wide_mask<1, uint8_t>() == 0x1);
    static_assert(make_wide_mask<52, uint64_t>() == 0xF'FFFF'FFFF'FFFFul);

    constexpr void mask() {
      if constexpr (N >= InfinitePrecision || !needs_mask()) {
        return;
      } else {
        if constexpr (!Signed) {
          m_val &= make_wide_mask<N>();
        } else {
          if (m_val & signBitMask()) {
            m_val |= ~make_wide_mask<N>();
          } else {
            m_val &= make_wide_mask<N>();
          }
        }
      }
    }

    static consteval StorageType signBitMask()
    {
      if constexpr (N == 0) {
        // gibberish...but need to not fail since Bits<0> might appear in
        // generated code
        return 0;
      } else {
        return static_cast<StorageType>(1) << (N-1);
      }
    }

    template <typename T>
    static constexpr T maskIntegral(const T& o) {
      static_assert(!std::is_reference_v<T>);
      constexpr T mask = make_wide_mask<N, T>();
      if constexpr (N >= sizeof(T)*8) {
        return o;
      } else {
        if constexpr (Signed) {
          if (o & signBitMask()) {
            return o | ~mask;
          } else {
            return o & mask;
          }
        } else {
          return o & mask;
        }
      }
    }

    template <typename T>
    static constexpr T maskIntegral(T&& o) {
      static_assert(!std::is_reference_v<T>);
      if constexpr (N >= sizeof(T)*8) {
        return o;
      } else {
        if constexpr (Signed) {
          if (o & signBitMask()) {
            o |= ~make_wide_mask<N, T>();
          } else {
            o &= make_wide_mask<N, T>();
          }
          return o;
        } else {
          o &= make_wide_mask<N, T>();
          return o;
        }
      }
    }
    static_assert(N != 1 || !Signed || maskIntegral<int>(-1) == -1);

    template <typename T>
      requires std::integral<T>
    constexpr operator T() const noexcept { return static_cast<T>(m_val); }

    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr explicit operator _Bits<_N, _Signed, _Strict>() const noexcept {
      if constexpr (fits_in_storage<_N>() && (_N >= N)) {
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          return *std::bit_cast<_Bits<_N, _Signed, _Strict>*>(this);
        } else {
          // can't bit cast, so need to create a new temp in the return
          return m_val;
        }
      } else {
        return _Bits<_N, _Signed, _Strict> {m_val};
      }
    }

    // template <typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr operator boost::multiprecision::number<Backend, E>() const {
    //   return m_val;
    // }

    constexpr uint64_t to_u64() const { return static_cast<uint64_t>(m_val); }

    template <typename T = StorageType>
    constexpr T get() const { return m_val; }

    constexpr const StorageType& get() const& { return m_val; }
    constexpr StorageType&& get() && { return std::move(m_val); }


    constexpr _Bits<N, true, Strict> operator-() const & {
      return -static_cast<typename BitsSignedStorageType<N>::type>(m_val);
    }
    constexpr _Bits<N, true, Strict> operator-() const && {
      return -static_cast<typename BitsSignedStorageType<N>::type>(std::move(m_val));
    }
    constexpr _Bits operator~() const & { return ~m_val; }
    constexpr _Bits operator~() const && { return ~std::move(m_val); }

    _Bits& operator=(const _Bits& o) = default;
    _Bits& operator=(_Bits&& o) noexcept = default;

    template <typename OtherType>
      requires std::integral<OtherType>
    _Bits& operator=(const OtherType& o) {
      m_val = o;
      if constexpr (needs_mask() && (sizeof(o)*8 > N)) {
        mask();
      }
      return *this;
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    _Bits& operator=(OtherType&& o) noexcept {
      m_val = std::move(o);
      if constexpr (needs_mask() && (sizeof(o)*8 > N)) {
        mask();
      }
      return *this;
    }
    // template <typename Backend, boost::multiprecision::expression_template_option E>
    // _Bits& operator=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val = o;
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    // template <typename Backend, boost::multiprecision::expression_template_option E>
    // _Bits& operator=(boost::multiprecision::number<Backend, E>&& o) noexcept {
    //   if constexpr (std::same_as<boost::multiprecision::number<Backend, E>, StorageType>) {
    //     m_val = std::move(o);
    //   } else {
    //     m_val = static_cast<StorageType>(o);
    //   }
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template <unsigned _N, bool _Signed, bool _Strict>
    _Bits& operator=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val = static_cast<StorageType>(o.m_val);
      if constexpr (needs_mask() && (sizeof(o)*8 > N) && (N > _N)) {
        mask();
      }
      return *this;
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    _Bits& operator=(_Bits<_N, _Signed, _Strict>&& o) noexcept {
      if constexpr (std::same_as<typename _Bits<_N, _Signed, _Strict>::StorageType, StorageType>) {
        m_val = std::move(o.m_val);
      } else {
        m_val = static_cast<StorageType>(o.m_val);
      }
      if constexpr (needs_mask() && (sizeof(o)*8 > N) && (N > _N)) {
        mask();
      }
      return *this;
    }
    template <typename T>
      requires requires (T reg) { reg.hw_read(); }
    _Bits& operator=(const T& o) {
      m_val = o.hw_read();
      if constexpr (needs_mask() && (sizeof(decltype(std::declval<T>().hw_read()))*8 > N)) {
        mask();
      }
      return *this;
    }


    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator==(const OtherType& o) const noexcept {
      return m_val == o;
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator==(const _Bits<_N, _Signed, _Strict>& o) const noexcept {
      return m_val == o.m_val;
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator!=(const OtherType& o) const {
      return m_val != o;
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator!=(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val != o.m_val;
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator<(const OtherType& o) const {
      if constexpr (Signed == std::is_signed_v<OtherType>) {
        return m_val < o;
      } else {
        return m_val < static_cast<StorageType>(o);
      }
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator<(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val < static_cast<StorageType>(o.m_val);
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator>(const OtherType& o) const {
      if constexpr (Signed == std::is_signed_v<OtherType>) {
        return m_val > o;
      } else {
        return m_val > static_cast<StorageType>(o);
      }
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator>(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val > static_cast<StorageType>(o.m_val);
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator<=(const OtherType& o) const {
      return m_val <= o;
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator<=(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val <= static_cast<StorageType>(o.m_val);
    }
    template <typename OtherType>
      requires std::integral<OtherType>
    constexpr bool operator>=(const OtherType& o) const {
      return m_val >= static_cast<StorageType>(o);
    }
    template <unsigned _N, bool _Signed, bool _Strict>
    constexpr bool operator>=(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val >= static_cast<StorageType>(o.m_val);
    }
    template <typename T>
      requires requires (T o) { o.hw_read(); }
    constexpr bool operator>=(const T& o) const {
      return m_val >= o.hw_read();
    }
    // template <typename OtherType>
    //   requires std::integral<OtherType>
    // constexpr std::strong_ordering operator<=>(const OtherType& o) const {
    //   if ( m_val < o ) {
    //     return std::strong_ordering::less;
    //   } else if ( m_val == o ) {
    //     return std::strong_ordering::equal;
    //   } else {
    //     return std::strong_ordering::greater;
    //   }
    // }


    template<class T>
      requires std::integral<T>
    friend constexpr T operator*(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o * i.m_val;
      } else {
        return o * static_cast<T>(i.m_val);
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator/(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o / i.m_val;
      } else {
        return o / static_cast<T>(i.m_val);
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator<<(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o << i.m_val;
      } else {
        return o << static_cast<uint64_t>(i.m_val);
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator>>(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o >> i.m_val;
      } else {
        return o >> static_cast<T>(i.m_val);
      }
    }

#   define AARCH64_BITS_COMMUTATIVE_BINARY_OP(OP)                              \
    template<class T>                                                          \
      requires std::integral<T>                                                \
    constexpr friend _Bits operator OP(const _Bits& me, const T& o) {          \
      return me.m_val OP o;                                                    \
    }                                                                          \
    template<class T>                                                          \
      requires std::integral<T>                                                \
    constexpr friend _Bits operator OP(_Bits&& me, const T& o) {               \
      me OP##= o;                                                              \
      return me;                                                               \
    }                                                                          \
    template<class T>                                                          \
      requires std::integral<T>                                                \
    constexpr friend _Bits operator OP(const T& o, const _Bits& me) {          \
      return o OP me.m_val;                                                    \
    }                                                                          \
    template<class T>                                                          \
      requires std::integral<T>                                                \
    constexpr friend _Bits operator OP(const T& o, _Bits&& me)  {              \
      me OP##= o;                                                              \
      return me;                                                               \
    }                                                                          \
    constexpr friend _Bits operator OP(const _Bits& me, const _Bits& o) {      \
      return me.m_val OP o.m_val;                                              \
    }                                                                          \
    constexpr friend _Bits operator OP(_Bits&& me, const _Bits& o) {           \
      me OP##= o.m_val;                                                        \
      return me;                                                               \
    }                                                                          \
    constexpr friend _Bits operator OP(const _Bits& o, _Bits&& me) {           \
      me OP##= o.m_val;                                                        \
      return me;                                                               \
    }                                                                          \
    constexpr friend _Bits operator OP(_Bits&& o, _Bits&& me) {                \
      me OP##= o.m_val;                                                        \
      return me;                                                               \
    }                                                                          \
    template<unsigned _N, bool _Signed, bool _Strict>                          \
      requires ((_N != N) || (_Signed != Signed) || (_Strict != Strict))       \
    constexpr friend _Bits operator OP(const _Bits& me, const _Bits<_N, _Signed, _Strict>& o) { \
      return me.m_val OP o.get();                                              \
    }                                                                          \
    template<unsigned _N, bool _Signed, bool _Strict>                          \
      requires ((_N != N) || (_Signed != Signed) || (_Strict != Strict))       \
    constexpr friend _Bits operator OP(_Bits&& me, const _Bits<_N, _Signed, _Strict>& o) { \
      me OP##= o.get();                                                        \
      return me;                                                               \
    }                                                                          \
    template<unsigned _N, bool _Signed, bool _Strict>                          \
      requires ((_N != N) || (_Signed != Signed) || (_Strict != Strict))       \
    constexpr friend _Bits operator OP(const _Bits& me, _Bits<_N, _Signed, _Strict>&& o) { \
      return me.m_val OP o.get();                                              \
    }                                                                          \
    template<unsigned _N, bool _Signed, bool _Strict>                          \
      requires ((_N != N) || (_Signed != Signed) || (_Strict != Strict))       \
    constexpr friend _Bits operator OP(_Bits&& me, _Bits<_N, _Signed, _Strict>&& o) {   \
      me OP##= o.get();                                                        \
      return me;                                                               \
    }                                                                          \
                                                                               \
    // template <class Backend, boost::multiprecision::expression_template_option ExpressionTemplates> \
    // constexpr friend _Bits operator OP(const _Bits& me, const boost::multiprecision::number<Backend, ExpressionTemplates>& o) { \
    //   return me.m_val OP o;                                                    \
    // }                                                                          \
    // template <class Backend, boost::multiprecision::expression_template_option ExpressionTemplates> \
    // constexpr friend _Bits operator OP(_Bits&& me, const boost::multiprecision::number<Backend, ExpressionTemplates>& o) { \
    //   me OP##= o;                                                              \
    //   return me;                                                               \
    // }                                                                          \
    // template <class Backend, boost::multiprecision::expression_template_option ExpressionTemplates> \
    // constexpr friend _Bits operator OP(const _Bits& me, boost::multiprecision::number<Backend, ExpressionTemplates>&& o) { \
    //   me OP##= o;                                                              \
    //   return me;                                                               \
    // }


    AARCH64_BITS_COMMUTATIVE_BINARY_OP(&)
    AARCH64_BITS_COMMUTATIVE_BINARY_OP(|)
    AARCH64_BITS_COMMUTATIVE_BINARY_OP(^)
    AARCH64_BITS_COMMUTATIVE_BINARY_OP(%)

    template<class T>
      requires std::integral<T>
    friend constexpr T operator+(const _Bits& o, const T& i) {
      if constexpr (std::integral<StorageType>) {
        return o.m_val + i;
      } else {
        return static_cast<T>(o.m_val) + i;
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator+(_Bits&& o, const T& i) {
      o += i;
      return o;
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator+(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o + i.m_val;
      } else {
        return o + static_cast<T>(i.m_val);
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator+(const T& o, _Bits&& i) {
      i += o;
      return i;
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator+(const _Bits& me, const _Bits& o) {
      if constexpr (fits_in_storage<N+1>()) {
        return me.m_val + o.m_val;
      } else {
        return _Bits<N+1, Signed, Strict>(me.m_val).m_val + o.m_val;
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator+(_Bits&& me, const _Bits& o) {
      if constexpr (fits_in_storage<N+1>()) {
        me += o.m_val;
        return static_cast<_Bits<N+1,Signed, Strict>>(me);
      } else {
        _Bits<N+1,Signed> tmp(me.m_val);
        tmp += o.m_val;
        return tmp;
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator+(const _Bits& me, _Bits&& o) {
      if constexpr (fits_in_storage<N+1>()) {
        o += me.m_val;
        return static_cast<_Bits<N+1,Signed, Strict>>(o);
      } else {
        _Bits<N+1,Signed, Strict> tmp(me.m_val);
        tmp += o.m_val;
        return tmp;
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator+(_Bits&& me, _Bits&& o) {
      if constexpr (fits_in_storage<N+1>()) {
        me += o.m_val;
        return static_cast<_Bits<N+1,Signed,Strict>>(me);
      } else {
        _Bits<N+1,Signed> tmp(me.m_val);
        tmp += o.m_val;
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator+(const _Bits& me, const _Bits<_N, _Signed, _Strict>& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>()) {
        if constexpr (Signed == _Signed) {
          return me.m_val + o.get();
        } else {
          return me.m_val + static_cast<StorageType>(o.get());
        }
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp += o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator+(_Bits&& me, const _Bits<_N, _Signed, _Strict>& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>() && !std::is_constant_evaluated()) {
        me += o.get();
        return static_cast<_Bits<return_width, Signed, Strict>>(me);
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp += o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator+(const _Bits& me, _Bits<_N, _Signed, _Strict>&& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      using otype = _Bits<_N, _Signed, _Strict>;
      if constexpr ((Signed == _Signed) && otype::template fits_in_storage<return_width>() && !std::is_constant_evaluated()) {
        o += me.m_val;
        return static_cast<_Bits<return_width, Signed, Strict>>(o);
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp += o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator+(_Bits&& me, _Bits<_N, _Signed, _Strict>&& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>() && !std::is_constant_evaluated()) {
        me += o.get();
        return static_cast<_Bits<return_width, Signed, Strict>>(me);
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp += o.get();
        return tmp;
      }
    }


    template<class T>
      requires std::integral<T>
    friend constexpr _Bits<N+1, Signed, Strict> operator-(const _Bits& o, const T& i) {
      if constexpr (fits_in_storage<N+1>()) {
        return o.m_val - i; // let _Bits constructor handle the mask
      } else {
        _Bits<N+1,Signed, Strict> tmp(o.m_val);
        tmp -= i;
        return tmp;
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr _Bits<N+1, Signed, Strict> operator-(_Bits&& o, const T& i) {
      if constexpr (fits_in_storage<N+1>()) {
        o.m_val -= i;
        if constexpr (needs_mask<N+1>()) {
          o.m_val = _Bits<N+1, Signed, Strict>::maskIntegral(std::move(o.m_val));
        }
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          static_assert(std::is_trivially_copyable_v<_Bits>);
          return std::bit_cast<_Bits<N+1, Signed, Strict>>(std::move(o));
        } else {
          // can't bit_cast, so we have to bite the bullet and create a tmp
          return o.m_val;
        }
      } else {
        _Bits<N+1,Signed, Strict> tmp(o.m_val);
        tmp -= i;
        return tmp;
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator-(const T& o, const _Bits& i) {
      if constexpr (std::integral<StorageType>) {
        return o - i.m_val;
      } else {
        return o - static_cast<T>(i.m_val);
      }
    }
    template<class T>
      requires std::integral<T>
    friend constexpr T operator-(const T& o, _Bits&& i) {
      if constexpr (std::integral<StorageType>) {
        return o - i.m_val;
      } else {
        return o - static_cast<T>(std::move(i.m_val));
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator-(const _Bits& me, const _Bits& o) {
      if constexpr (fits_in_storage<N+1>()) {
        return me.m_val - o.m_val;
      } else {
        return _Bits<N+1, Signed, Strict>(me.m_val).m_val - o.m_val;
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator-(_Bits&& me, const _Bits& o) {
      if constexpr (fits_in_storage<N+1>()) {
        if constexpr (needs_mask<N+1>()){
          me.m_val -= o.m_val;
          me.m_val = _Bits<N+1, Signed, Strict>::maskIntegral(std::move(me.m_val));
        } else {
          me.m_val -= o.m_val;
        }
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          return std::bit_cast<_Bits<N+1,Signed, Strict>>(std::move(me));
        } else {
          // can't bit_cast, so need to create a temp
          return me.m_val;
        }
      } else {
        _Bits<N+1,Signed, Strict> tmp(me.m_val);
        tmp -= o.m_val;
        return tmp;
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator-(const _Bits& me, _Bits&& o) {
      if constexpr (fits_in_storage<N+1>()) {
        return me.m_val - o.m_val;
      } else {
        return static_cast<_Bits<N+1, Signed, Strict>::StorageType>(me.m_val) - static_cast<_Bits<N+1, Signed, Strict>::StorageType>(o.m_val);
      }
    }
    // N + 1 can overflow to 0, so we need to detect that in the return width
    constexpr friend _Bits<N+1, Signed, Strict> operator-(_Bits&& me, _Bits&& o) {
      if constexpr (fits_in_storage<N+1>()) {
        if constexpr (needs_mask<N+1>()) {
          me.m_val -= o.m_val;
          me.m_val = _Bits<N+1,Signed, Strict>::maskIntegral(std::move(me.m_val));
        } else {
          me.m_val -= o.m_val;
        }
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          return std::bit_cast<_Bits<N+1,Signed, Strict>>(std::move(me));
        } else {
          // can't bit_cast, so need to create a temp
          return me.m_val;
        }
      } else {
        _Bits<N+1,Signed, Strict> tmp(me.m_val);
        tmp -= o.m_val;
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator-(const _Bits& me, const _Bits<_N, _Signed, _Strict>& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>()) {
        if constexpr (Signed == _Signed) {
          return me.m_val - o.get();
        } else {
          return me.m_val - static_cast<StorageType>(o.get());
        }
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp -= o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, _Strict> operator-(_Bits&& me, const _Bits<_N, _Signed, _Strict>& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>()) {
        if constexpr (Signed == _Signed) {
          me.m_val -= o.get();
        } else {
          me.m_val -= static_cast<StorageType>(o.get());
        }
        if constexpr (needs_mask<return_width>()) {
          me.m_val = _Bits<return_width, Signed, Strict>::maskIntegral(std::move(me.m_val));
        }
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          return std::bit_cast<_Bits<return_width, Signed, Strict>>(std::move(me));
        } else {
          // can't bit_cast, so need to create a temp
          return me.m_val;
        }
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp -= o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator-(const _Bits& me, _Bits<_N, _Signed, _Strict>&& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>()) {
        if constexpr (Signed == _Signed) {
          return me.m_val - o.get();
        } else {
          return me.m_val - static_cast<StorageType>(o.get());
        }
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp -= o.get();
        return tmp;
      }
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N != _N) || (Signed != _Signed) || (_Strict != Strict))
    constexpr friend _Bits<constmax<N,_N>::value+1, Signed, Strict> operator-(_Bits&& me, _Bits<_N, _Signed, _Strict>&& o) {
      constexpr unsigned return_width = constmax<N,_N>::value+1;
      static_assert(return_width > 0);
      if constexpr (fits_in_storage<return_width>()) {
        if constexpr (Signed == _Signed) {
          me.m_val -= o.get();
        } else {
          me.m_val -= static_cast<StorageType>(o.get());
        }
        if constexpr (needs_mask<return_width>()) {
          me.m_val = _Bits<return_width, Signed, Strict>::maskIntegral(std::move(me.m_val));
        }
        if constexpr (std::is_trivially_copyable_v<StorageType>) {
          return std::bit_cast<_Bits<return_width, Signed, Strict>>(std::move(me));
        } else {
          return me.m_val;
        }
      } else {
        _Bits<N+1, Signed, Strict> tmp(me.m_val);
        tmp -= o.get();
        return tmp;
      }
    }

    template<class T>
      requires std::integral<T>
    constexpr _Bits<constmax<N, N*2>::value, Signed, Strict> operator*(const T& o) const {
      return _Bits<constmax<N, N*2>::value>(m_val).m_val * o;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits<constmax<N, N+_N>::value, Signed, Strict> operator*(const _Bits<_N,_Signed,_Strict>& o) const {
      return _Bits<constmax<N, N+_N>::value, Signed, Strict>(m_val).m_val * _Bits<constmax<N, N+_N>::value, Signed, Strict>(o.m_val).m_val;
    }
    template<class T>
      requires std::integral<T>
    constexpr _Bits operator/(const T& o) const {
      return m_val / o;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits operator/(const _Bits<_N, _Signed, _Strict>& o) const {
      return m_val / o.m_val;
    }
    // can't really know how big the result will be, so need to use an
    // unbounded int in the return
    template<class T>
      requires std::integral<T>
    constexpr _Bits<MaxPrecision, Signed, Strict> operator<<(const T& shift) const {
      return static_cast<_Bits<MaxPrecision, Signed, Strict>>(m_val << shift);
    }
    template<unsigned _N, bool _Signed, bool _Strict>
      requires ((N < 128) && (_N < 64) && ((N + (1ULL << _N)) <= 128))
    constexpr _Bits<MaxPrecision, Signed, Strict> operator<<(const _Bits<_N, _Signed, _Strict>& shift) const {
      static_assert(N + (1ULL << _N) > 0);
      if constexpr (!std::integral<typename _Bits<_N, _Signed, _Strict>::StorageType>) {
        return _Bits<MaxPrecision, Signed, Strict> {_Bits<MaxPrecision, Signed, Strict>(m_val).m_val << static_cast<uint64_t>(shift.m_val)};
      } else {
        return _Bits<MaxPrecision, Signed, Strict> {_Bits<MaxPrecision, Signed, Strict>(m_val).m_val << shift.m_val};
      }
    }
    template <unsigned Shamt>
    constexpr _Bits<N + Shamt> const_sll() const {
      return _Bits<N + Shamt, Signed, Strict>(m_val).m_val << Shamt;
    }
    // template <class Backend, boost::multiprecision::expression_template_option ExpressionTemplates>
    // constexpr _Bits<InfinitePrecision> operator<<(const boost::multiprecision::number<Backend, ExpressionTemplates>& shift) const {
    //   return _Bits<InfinitePrecision>(m_val).m_val << static_cast<uint64_t>(shift);
    // }
    // template<unsigned _N, bool _Signed, bool _Strict>
    //   requires ((N < 128) && (_N < 64) && ((N + (1ULL << _N)) <= 128))
    // constexpr _Bits<N + (1ULL << _N), Signed> operator<<(const _Bits<_N, _Signed, _Strict>& shift) const {
    //   static_assert(N + (1ULL << _N) > 0);
    //   if constexpr (!std::integral<typename _Bits<_N, _Signed, _Strict>::StorageType>) {
    //     return _Bits<N + (1ULL << _N)> {_Bits<N + (1ULL << _N), Signed, Strict>(m_val).m_val << static_cast<uint64_t>(shift.m_val)};
    //   } else {
    //     return _Bits<N + (1ULL << _N)> {_Bits<N + (1ULL << _N), Signed, Strict>(m_val).m_val << shift.m_val};
    //   }
    // }
    // template<unsigned _N, bool _Signed, bool _Strict>
    //   requires ((N > 128) || ( _N >= 64) || ((N + (1ULL << _N)) > 128))
    // constexpr _Bits<InfinitePrecision> operator<<(const _Bits<_N, _Signed, _Strict>& shift) const {
    //   if constexpr (!std::integral<typename _Bits<_N, _Signed, _Strict>::StorageType>) {
    //     return _Bits<InfinitePrecision>(m_val).m_val << static_cast<uint64_t>(shift.m_val);
    //   } else {
    //     return _Bits<InfinitePrecision>(m_val).m_val << shift.m_val;
    //   }
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits operator>>(const T& shift) const {
      return _Bits { m_val >> shift };
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits operator>>(const _Bits<_N, _Signed, _Strict>& shift) const {
      if constexpr (!std::integral<typename _Bits<_N, _Signed, _Strict>::StorageType>) {
        return m_val >> static_cast<uint64_t>(shift.m_val);
      } else {
        return m_val >> shift.m_val;
      }
    }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator+=(const T& o) {
      m_val += o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator+=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val += o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator+=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val += static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator%=(const T& o) {
      m_val %= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator%=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val %= o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator%=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val %= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator-=(const T& o) {
      m_val -= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator-=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val -= o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator-=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val -= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator*=(const T& o) {
      m_val *= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator*=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val *= o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator*=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val *= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator/=(const T& o) {
      m_val /= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator/=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val /= o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator/=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val /= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator<<=(const T& o) {
      m_val <<= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator<<=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val <<= o.m_val;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator<<=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val <<= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator>>=(const T& o) {
      m_val >>= o;
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator>>=(const _Bits<_N, _Signed, _Strict>& o) {
      if constexpr (!std::integral<typename _Bits<_N,_Signed, _Strict>::StorageType>) {
        if constexpr (std::integral<StorageType>) {
          m_val >>= static_cast<StorageType>(o.m_val);
        } else {
          m_val >>= static_cast<uint64_t>(o.m_val);
        }
      } else {
        m_val >>= o.m_val;
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator>>=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val >>= static_cast<StorageType>(o);
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator|=(const T& o) {
      m_val |= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator|=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val |= static_cast<StorageType>(o.m_val);
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator|=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val |= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    constexpr _Bits& operator&=(const T& o) {
      m_val &= o;
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    constexpr _Bits& operator&=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val &= static_cast<StorageType>(o.m_val);
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator&=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val &= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    template<class T>
      requires std::integral<T>
    _Bits& operator^=(const T& o) {
      m_val ^= o;
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    template<unsigned _N, bool _Signed, bool _Strict>
    _Bits& operator^=(const _Bits<_N, _Signed, _Strict>& o) {
      m_val ^= static_cast<StorageType>(o.m_val);
      if constexpr (needs_mask()) {
        mask();
      }
      return *this;
    }
    // template<typename Backend, boost::multiprecision::expression_template_option E>
    // constexpr _Bits& operator^=(const boost::multiprecision::number<Backend, E>& o) {
    //   m_val ^= static_cast<StorageType>(o);
    //   if constexpr (needs_mask()) {
    //     mask();
    //   }
    //   return *this;
    // }
    // pre-increment. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits& operator++() {
      ++m_val;
      return *this;
    }

    // post-increment
    _Bits operator++(int) {
      _Bits tmp{m_val};
      ++m_val;
      return tmp;
    }

    // pre-decrement. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits& operator--() {
      --m_val;
      return *this;
    }

    // post-increment
    _Bits operator--(int) {
      _Bits tmp{m_val};
      --m_val;
      return tmp;
    }

    private:
    StorageType m_val;

  };

  template<unsigned N, bool Signed = false, bool Strict = true>
  using Bits = _Bits<N, Signed, Strict>;

  template<unsigned N, bool Strict = true>
  using SignedBits = _Bits<N, true, Strict>;

  using integer_t = _Bits<_Bits<1, true, false>::InfinitePrecision, true, false>;
  using bits_t = _Bits<_Bits<1, false, true>::InfinitePrecision, false, false>;

    // static_assert(static_cast<uint64_t>(_Bits<1023> { 5 }) == 5);

}

namespace std {

  template <unsigned N, bool Signed, bool Strict>
  class numeric_limits<iss::_Bits<N, Signed, Strict>>
  {
    static constexpr bool is_integral = std::integral<typename iss::_Bits<N, Signed>::StorageType>;
    static constexpr bool is_max = N >= iss::_Bits<N, Signed>::InfinitePrecision;
    public:
    static constexpr bool is_specialized = true;
    static constexpr bool is_signed = Signed;
    static constexpr bool is_integer = true;
    static constexpr bool is_exact = true;
    static constexpr bool has_infinity = false;
    static constexpr bool has_quiet_NaN = false;
    static constexpr bool has_signaling_NaN = false;
    static constexpr bool has_dermon_loss = false;
    static constexpr std::float_round_style round_style = std::round_toward_zero;
    static constexpr bool is_iec559 = false;
    static constexpr bool is_bounded = is_integral ? true : std::numeric_limits<typename iss::_Bits<N, Signed>>::is_bounded;
    static constexpr int  digits = N < iss::_Bits<N, Signed>::InfinitePrecision ? N : std::numeric_limits<typename iss::_Bits<N, Signed>>::digits;
    static constexpr int  digits10 = N < iss::_Bits<N, Signed>::InfinitePrecision ? N * std::log10(2) : std::numeric_limits<typename iss::_Bits<N, Signed>>::digits10;
    static constexpr int  max_digits10 = 0;
    static constexpr int  radix = 2;
    static constexpr int  min_exponent = 0;
    static constexpr int  min_exponent10 = 0;
    static constexpr int  max_exponent = 0;
    static constexpr int  max_exponent10 = 0;
    static constexpr bool trap = true;
    static constexpr bool tinyness_before = true;

    static consteval iss::_Bits<N, Signed, Strict> min() noexcept {
      return !is_max ?
        (Signed ?
          -(static_cast<typename iss::_Bits<N, Signed, Strict>::StorageType>(1) << (N-1)) :
          static_cast<typename iss::_Bits<N, Signed, Strict>::StorageType>(0))
        : std::numeric_limits<typename iss::_Bits<N, Signed, Strict>::StorageType>::min();
    }
    static consteval iss::_Bits<N, Signed, Strict> lowest() noexcept {
      return min();
    }
    static consteval iss::_Bits<N, Signed, Strict> max() noexcept {
      return !is_max ?
        (Signed ?
          (static_cast<typename iss::_Bits<N, Signed, Strict>::StorageType>(1) << (N-1)) - 1 :
          ~static_cast<typename iss::_Bits<N, Signed, Strict>::StorageType>(0))
        : std::numeric_limits<typename iss::_Bits<N, Signed, Strict>::StorageType>::max();
    }
    static consteval iss::_Bits<N, Signed, Strict> epsilon() noexcept {
      return 0;
    }
    static consteval iss::_Bits<N, Signed, Strict> round_error() noexcept {
      return 0;
    }
    static consteval iss::_Bits<N, Signed, Strict> infinity() noexcept {
      return 0;
    }
    static consteval iss::_Bits<N, Signed, Strict> quiet_NaN() noexcept {
      return 0;
    }
    static consteval iss::_Bits<N, Signed, Strict> denorm_min() noexcept {
      return 0;
    }
  };
}

// static_assert(std::numeric_limits<iss::integer_t>::max() == std::numeric_limits<iss::integer_t::StorageType>::max());
// static_assert(std::numeric_limits<iss::integer_t>::min() == std::numeric_limits<iss::integer_t::StorageType>::min());
static_assert(std::numeric_limits<iss::integer_t>::is_signed == true);
static_assert(std::numeric_limits<iss::bits_t>::is_signed == false);
static_assert(std::numeric_limits<iss::_Bits<1, false, true>>::max() == 1u);
static_assert(std::numeric_limits<iss::_Bits<1, true, true>>::max() == 0);
static_assert(std::numeric_limits<iss::_Bits<4, false, true>>::max() == 15u);
static_assert(std::numeric_limits<iss::_Bits<4, true, true>>::max() == 7);
static_assert(std::numeric_limits<iss::_Bits<1, false, true>>::min() == 0u);
static_assert(std::numeric_limits<iss::_Bits<1, true, true>>::min() == -1);
static_assert(std::numeric_limits<iss::_Bits<1, true, true>>::min().get() == -1);
static_assert(std::numeric_limits<iss::_Bits<4, false, true>>::min() == 0u);
static_assert(std::numeric_limits<iss::_Bits<4, true, true>>::min() == -8);

// constexpr iss::integer_t operator<<(const iss::integer_t& o, const iss::integer_t& shift)
// {
//   return o << static_cast<int>(shift);
// }

// template <unsigned N>
// constexpr iss::integer_t operator>>(const iss::integer_t& o, const iss::Bits<N>& shift)
// {
//   return o >> static_cast<int>(shift);
// }

// constexpr iss::integer_t operator>>(const iss::integer_t& o, const iss::integer_t& shift)
// {
//   return o >> static_cast<int>(shift);
// }

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator<=(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o <= static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator>=(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o >= static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator==(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o == static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator!=(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o != static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator<(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o < static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
constexpr bool operator>(const T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o > static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
T& operator+=(T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o += static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
T& operator|=(T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o |= static_cast<T>(i);
}

template<class T, unsigned N, bool Signed, bool Strict>
  requires std::integral<T>
T& operator&=(T& o, const iss::_Bits<N, Signed, Strict>& i) {
  return o &= static_cast<T>(i);
}

// format Bits as their underlying type when using format()
template <unsigned N, bool Signed, bool Strict>
struct ISS_FORMATTER<iss::_Bits<N, Signed, Strict>>: formatter<typename iss::_Bits<N, Signed, Strict>::StorageType> {
  template <typename CONTEXT_TYPE>
  auto format(iss::_Bits<N, Signed, Strict> value, CONTEXT_TYPE& ctx) const {
    return ISS_FORMATTER<typename iss::_Bits<N, Signed, Strict>::StorageType>::format(value.get(), ctx);
  }
};

namespace std {
  template <unsigned N, bool Signed, bool Strict>
  std::string to_string(const iss::_Bits<N, Signed, Strict>& i) {
    return to_string(static_cast<iss::_Bits<N, Signed, Strict>::StorageType>(i));
  }
}

namespace riscv {
  template <unsigned Size>
  class Bitfield;

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  class BitfieldMember {
    public:
    BitfieldMember(Bitfield<ParentSize>& parent)
      : m_parent(parent)
    {}

    static constexpr Bits<Size> MaximumValue = (Bits<Size>(1).template const_sll<Size>()) - 1;
    static constexpr Bits<ParentSize> Mask = MaximumValue.template const_sll<Start>();

    operator Bits<Size>() const;

    BitfieldMember& operator=(const Bits<Size>& value);

    template <std::integral Type>
    bool operator==(const Type& other) { return other == static_cast<Bits<Size>>(*this); }

    Bits<Bits<Size>::MaxPrecision> operator<<(const int& shamt) { return static_cast<Bits<Size>>(*this) << shamt; }

    private:
    Bitfield<ParentSize>& m_parent;
  };

  template <unsigned Size>
  class Bitfield {
    public:
    Bitfield() = default;
    Bitfield(const Bits<Size>& value) : m_value(value) {}

    Bitfield& operator=(const Bits<Size>& value) {
      m_value = value;
      return *this;
    }
    operator Bits<Size>&() { return m_value; }
    operator Bits<Size>() const { return m_value; }

    protected:
    Bits<Size> m_value;
  };

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  BitfieldMember<ParentSize, Start, Size>::operator Bits<Size>() const
  {
    return (static_cast<Bits<ParentSize>>(m_parent) >> Start) & MaximumValue;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  BitfieldMember<ParentSize, Start, Size>& BitfieldMember<ParentSize, Start, Size>::operator=(const Bits<Size>& value)
  {
    m_parent = (static_cast<Bits<ParentSize>>(m_parent) & ~Mask) | ((value << Size) & Mask);
    return *this;
  }
}
