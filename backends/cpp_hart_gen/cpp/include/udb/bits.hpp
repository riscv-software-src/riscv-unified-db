#pragma once

#include <fmt/core.h>
#include <fmt/format.h>
#include <gmpxx.h>

#include <bit>
#include <concepts>
#include <cstdint>
#include <limits>
#include <type_traits>

#include "udb/cpp_exceptions.hpp"
#include "udb/defines.hpp"

// Bits classes implement the IDL Bits<N> type.
//
// There are four Bits types in C++:
//
//  _Bits<N, Signed>:                          Compile-time known vector length
//  holding a known value _PossiblyUnknownBits<N, Signed>: Compile-time known
//  vector length holding a possibly unknown value _RuntimeBits<MaxN, Signed>:
//  Compile-time unknown vector length, at most MaxN, holding a known value
//  _PossiblyUnknownRuntimeBits<MaxN, Signed>: Compile-time unknown vector
//  length, at most MaxN, holding a possibly unknown value
//
// You can convert:
//
//   - _Bits<N, Signed>                          -> *any
//   - _PossiblyUnknownBits<N, Signed>           ->
//   _PossiblyUnknownRuntimeBits<MaxN, Signed>
//   - _RuntimeBits<MaxN, Signed>                ->
//   _PossiblyUnknownRuntimeBits<MaxN, Signed>
//   - _PossiblyUnknownRuntimeBits<MaxN, Signed> ->  none
//
// The bits classes attempt to hold the smallest native type to hold the value,
// falling back on GMP when it will not fit in any native type. The bits classes
// attempt to drop state (and checks) for unknown values when the value must be
// known; thus the multiple class types. The bits classes handle when the vector
// length isn't known at compile-time (e.g., because the length is a config
// parameter).
//

// we need this to be true for GMP
static_assert(sizeof(long unsigned int) == sizeof(long long unsigned int));

// we make this assumption frequently
static_assert(sizeof(1ull) == 8);

#ifndef __SIZEOF_INT128__
#error "Compiler does not support __int128"
#endif

namespace udb {

  // helper to find the max of N unsigned values at compile time
  // example:
  //   static_assert(constmax<5, 43, 1>::value == 43);
  template <unsigned... _N>
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
  template <unsigned... _N>
  static constexpr unsigned constmax_v = constmax<_N...>::value;

  static_assert(constmax<std::numeric_limits<unsigned>::max(),
                         std::numeric_limits<unsigned>::max()>::value ==
                std::numeric_limits<unsigned>::max());

  // given the Bits vector length, get the type of the underlying storage for
  // unsigned values
  // clang-format off
  template <unsigned N>
  struct BitsStorageType {
    using type = std::conditional_t<
        (N > 128), mpz_class,               // > 128 bits          --> GMP
        std::conditional_t<
            (N > 64), unsigned __int128,    // between 65-128 bits --> uint128_t (g++/clang builtin)
            std::conditional_t<
                (N > 32), uint64_t,         // between 33-64 bits  --> uint64_t
                std::conditional_t<
                    (N > 16), uint32_t,     // between 17-32 bits  --> uint32_t
                    std::conditional_t<(N > 8),
                      uint16_t,             // between 9-16 bits   --> uint16_t
                      uint8_t>>>>>;         // <= 8 bits           --> uint8_t
  };
  // clang-format on

  // given the Bits vector length, get the type of the underlying storage for
  // signed values
  template <unsigned N>
  struct BitsSignedStorageType {
    using type = std::conditional_t<
        (N > 128), mpz_class,
        std::conditional_t<
            (N > 64), __int128,
            std::conditional_t<
                (N > 32), int64_t,
                std::conditional_t<
                    (N > 16), int32_t,
                    std::conditional_t<(N > 8), int16_t, int8_t>>>>>;
  };

  // need to define the conversion since GMP doesn (int128 isn't standard)
  static inline auto to_mpz(const unsigned __int128 &rhs) {
    mpz_class i = static_cast<uint64_t>(rhs >> 64);
    i <<= 64;
    i |= static_cast<uint64_t>(rhs);
    return i;
  }

  // need to define the conversion since GMP doesn (int128 isn't standard)
  static inline mpz_class to_mpz(const __int128 &rhs) {
    if (rhs < 0) {
      if (rhs == std::numeric_limits<__int128>::min()) {
        // special case, since we can't represent -rhs
        return (-to_mpz(static_cast<unsigned __int128>(-(rhs + 1)))) - 1;
      } else {
        return -to_mpz(static_cast<unsigned __int128>(-rhs));
      }
    } else {
      return to_mpz(static_cast<unsigned __int128>(rhs));
    }
  }

  template <std::integral IntType>
    requires(sizeof(IntType) < 16)
  mpz_class to_mpz(const IntType &rhs) {
    return {rhs};
  }

  // N that actually means infinite
  constexpr static unsigned BitsInfinitePrecision =
      std::numeric_limits<unsigned>::max();

  // max N value where storage is using a native integer type
  // above this, the storage is GMP, and the Bits type can't be constexpr
  constexpr static unsigned BitsMaxNativePrecision = 128;

  template <unsigned MaxN, bool Signed>
  class _RuntimeBits;

  template <unsigned N, bool Signed>
  class _PossiblyUnknownBits;

  // saturating add
  template <unsigned A, unsigned B>
  struct addsat {
    static constexpr unsigned value = (((A + B) < A) || ((A + B) < B))
                                          ? std::numeric_limits<unsigned>::max()
                                          : A + B;
  };
  template <unsigned A, unsigned B>
  static constexpr unsigned addsat_v = addsat<A, B>::value;

  // The _Bits class represents an arbitrary-width integer.
  // N is the width of the integer, known at compile time.
  // If N == BitsInfinitePrecision, then the width is infinite (i.e., not known)
  //
  // The underlying storage is optimized for N.
  // When N <= BitsMaxNativePrecision, The underlying storage is native.
  // When N > BitsMaxNativePrecison, the underlying storage is a libgmp
  // multiprecision object.
  //
  // The operators are implemented to match the semantics of the Bits<N> type in
  // IDL.
  template <unsigned N, bool Signed>
  class _Bits {
    static_assert(N > 0);

   public:
    // used for template concept resolution
    constexpr static bool IsABits = true;

    // value of N that represents unknown precision (happens when there is a
    // left shift by unknown value)
    constexpr static unsigned InfinitePrecision = BitsInfinitePrecision;

    // largest value of N that still uses a native underlying type
    // beyond this, the number of bits is still tracked, but the storage is
    // using gmp
    constexpr static unsigned MaxNativePrecision = BitsMaxNativePrecision;

    // advertise the width
    constexpr static unsigned Width = N;
    constexpr static unsigned width() { return N; }

    using StorageType = typename BitsStorageType<N>::type;
    using SignedStorageType = typename BitsSignedStorageType<N>::type;

    // returns true if this Bits width requires storage masking (i.e., N != #
    // bits in the underlying type)
    template <unsigned _N = N>
    static consteval bool needs_mask() {
      using _StorageType = typename BitsStorageType<_N>::type;

      if constexpr (_N == InfinitePrecision) {
        return false;
      } else if constexpr (_N > MaxNativePrecision) {
        // gmp (infinite) storage, so everything needs masked
        return true;
      } else if constexpr (_N == (sizeof(_StorageType) * 8)) {
        // we fit exactly in our native storage
        return false;
      } else {
        // using native storage, but there are unused bits
        return true;
      }
    }

   public:
    // mask of all ones for the Bits type
    template <unsigned _N = N>
      requires(N <= MaxNativePrecision)
    static consteval StorageType mask() {
      if constexpr (std::integral<StorageType> &&
                    (N == (sizeof(StorageType) * 8))) {
        return ~StorageType{0};
      } else {
        return ((StorageType{1} << N) - 1);
      }
    }
    template <unsigned _N = N>
      requires(N > MaxNativePrecision)
    static StorageType mask() {
      static_assert(N != InfinitePrecision);  // this isn't a good idea ;)
      return ((StorageType{1} << N) - 1);
    }
    static_assert(needs_mask<4>() == true);
    static_assert(needs_mask<8>() == false);
    static_assert(needs_mask<16>() == false);
    static_assert(needs_mask<32>() == false);
    static_assert(needs_mask<64>() == false);
    static_assert(needs_mask<65>() == true);
    static_assert(needs_mask<128>() == false);
    static_assert(needs_mask<129>() == true);
    static_assert(needs_mask<256>() == true);
    static_assert(needs_mask<512>() == true);
    static_assert(needs_mask<InfinitePrecision>() == false);

   public:
    // given storage for a Bits<N> type, return a signed version of it in the
    // storage class
    template <unsigned _N = N>
      requires(_N <= MaxNativePrecision)
    static constexpr SignedStorageType cast_to_signed(
        const StorageType &unsigned_value) {
      if constexpr (N == (sizeof(StorageType) * 8)) {
        // exactly fits in a native type, so just cast it
        return static_cast<SignedStorageType>(unsigned_value);
      } else {
        // we have a native type, but some bits are unused. need to sign extend
        // the storage to the native width
        return static_cast<SignedStorageType>(sign_extend(unsigned_value));
      }
    }

    template <unsigned _N = N>
      requires(_N > MaxNativePrecision)
    static SignedStorageType cast_to_signed(const StorageType &unsigned_value) {
      // this is gmp storage. We can't just sign extend, so we'll need to do the
      // compliment
      if constexpr (N == InfinitePrecision) {
        // our 'unsigned' value is actually signed
        return unsigned_value;
      } else {
        auto v = unsigned_value;
        if (((v >> (N - 1)) & 1) == 1) {
          // the number is now negative!
          // The two's compliment value is 2^N - value
          v = -((StorageType{1} << N) - v);
        }
        return v;
      }
    }

    // return a signed version of self
    constexpr SignedStorageType cast_to_signed() const {
      return cast_to_signed(m_val);
    }

    template <bool _Signed = Signed>
      requires(_Signed == false)
    constexpr _Bits<N, true> make_signed() const {
      return _Bits<N, true>{m_val};
    }
    template <bool _Signed = Signed>
      requires(_Signed == true)
    constexpr _Bits<N, true> &make_signed() const {
      return *this;
    }

    // given a Bits<N> storage type, sign extend it to the full width of
    // StorageType
    static constexpr StorageType sign_extend(const StorageType &value) {
      static_assert(N <= MaxNativePrecision);  // doesn't make sense with gmp
      if constexpr (N == sizeof(StorageType) * 8) {
        // exact fit, no extension needed
        return value;  // no extension needed
      } else {
        if (value & (StorageType{1} << (N - 1))) {
          // fill with ones
          return value | ~mask();
        } else {
          // no extension needed
          return value;
        }
      }
    }

    static constexpr std::conditional_t<needs_mask(), StorageType,
                                        const StorageType &>
    apply_mask(const StorageType &value) {
      if constexpr (needs_mask()) {
        return value & mask();
      } else {
        return value;
      }
    }

    static _Bits from_string(const std::string &str) {
      if constexpr (std::is_same_v<StorageType, mpz_class>) {
        mpz_class gmp_int(str.c_str());
        return _Bits{gmp_int};
      } else if constexpr (N <= 64 && N > 32) {
        static_assert(sizeof(long long) == sizeof(uint64_t),
                      "Unexpected long long type");
        if constexpr (Signed) {
          return _Bits(std::stoll(str, nullptr, 0));
        } else {
          return _Bits(std::stoull(str, nullptr, 0));
        }
      } else if constexpr (N <= 32 && N > 16) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long
        // type");
        if constexpr (Signed) {
          return _Bits(std::stol(str, nullptr, 0));
        } else {
          return _Bits(std::stoul(str, nullptr, 0));
        }
      } else if constexpr (N <= 16 && N > 8) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long
        // type");
        if constexpr (Signed) {
          int32_t tmp = std::stol(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<int16_t>::max() && tmp >=
          // std::numeric_limits<int16_t>::min());
          return _Bits(tmp);
        } else {
          uint32_t tmp = std::stoul(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<uint16_t>::max());
          return _Bits(tmp);
        }
      } else if constexpr (N <= 8) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long
        // type");
        if constexpr (Signed) {
          int32_t tmp = std::stol(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<int8_t>::max() && tmp >=
          // std::numeric_limits<int8_t>::min());
          return _Bits(tmp);
        } else {
          uint32_t tmp = std::stoul(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<uint8_t>::max());
          return _Bits(tmp);
        }
      }
    }

    constexpr _Bits() : m_val(0) {}
    constexpr _Bits(const _Bits &) = default;
    _Bits(_Bits &&) noexcept = default;

    constexpr _Bits(const _Bits<N, !Signed> &other) : m_val(other.m_val) {}

    constexpr _Bits(const StorageType &val) : m_val(val) {}

    // also make a gmp constructor for native widths
    template <unsigned _N = N>
      requires(N <= MaxNativePrecision)
    constexpr _Bits(const mpz_class &val) {
      m_val = val.get_ui();
    }

    template <unsigned MaxN, bool _Signed>
    _Bits(const _RuntimeBits<MaxN, _Signed> &);

    // other is smaller N
    // everything fits, so just copy the storage
    template <unsigned M, bool _Signed>
      requires(M < N)
    constexpr _Bits(const _Bits<M, _Signed> &o) {
      if constexpr (N <= MaxNativePrecision && M > MaxNativePrecision) {
        static_assert(false, "this can never happen??");
        m_val = o.m_val.get_ui();
      } else if constexpr ((N > MaxNativePrecision) &&
                           (M <= MaxNativePrecision) &&
                           (sizeof(typename _Bits<M, _Signed>::StorageType) ==
                            16)) {
        if constexpr (!_Signed) {
          static_assert(std::same_as<typename _Bits<M, _Signed>::StorageType,
                                     unsigned __int128>);
          // libgmp can't convert __int128, so we have to do it manually
          m_val = static_cast<uint64_t>(o.get() & 0xffffffff'ffffffffull);
          m_val <<= 64;
          m_val |= static_cast<uint64_t>(o.get() >> 64);
        } else {
          static_assert(
              std::same_as<typename _Bits<M, _Signed>::StorageType, __int128>);
          // libgmp can't convert __int128, so we have to do it manually
          if (o.get() == std::numeric_limits<__int128>::min()) {
            // can't just negate this, so it's a special case
            __int128 neg = -(o.get() + 1);
            m_val = static_cast<uint64_t>(neg & 0xffffffff'ffffffffull);
            m_val <<= 64;
            m_val |= static_cast<uint64_t>(neg >> 64);
            m_val = (-m_val) - 1;

          } else {
            __int128 abs = (o.get() < 0) ? -o.get() : o.get();
            m_val = static_cast<uint64_t>(abs & 0xffffffff'ffffffffull);
            m_val <<= 64;
            m_val |= static_cast<uint64_t>(abs >> 64);
            if (o.get() < 0) {
              m_val = -m_val;
            }
          }
        }
      } else {
        m_val = o.get();
      }
    }

    // other is bigger N
    // the other value will be truncated
    template <unsigned M, bool _Signed>
      requires(M > N)
    constexpr _Bits(const _Bits<M, _Signed> &o) {
      if constexpr (N <= MaxNativePrecision && M > MaxNativePrecision) {
        m_val = apply_mask(o.m_val.get_ui());
      } else {
        m_val = apply_mask(o.m_val);
      }
    }

    // built-in integer type, mask needed
    template <class IntType, unsigned _N = N>
      requires(!std::is_same_v<StorageType, IntType> &&
               std::integral<IntType> && needs_mask() &&
               _N <= BitsMaxNativePrecision)
    constexpr _Bits(const IntType &val) : m_val(apply_mask(val)) {}

    // built-in integer type, mask needed, integral conversion to mpz
    template <class IntType, unsigned _N = N>
      requires(!std::is_same_v<StorageType, IntType> &&
               std::integral<IntType> && needs_mask() &&
               _N > BitsMaxNativePrecision)
    constexpr _Bits(const IntType &val) : m_val(apply_mask(to_mpz(val))) {}

    // built-in integer type, no mask needed
    template <class IntType>
      requires(!std::is_same_v<StorageType, IntType> &&
               std::integral<IntType> && !needs_mask())
    constexpr _Bits(const IntType &val) {
      if constexpr (N == InfinitePrecision && std::is_signed_v<IntType>) {
        if (val < 0) {
          abort();  // Can't mask off a negative value with infinite precision!
        }
      }
      if constexpr (N <= MaxNativePrecision) {
        m_val = val;
      } else {
        m_val = to_mpz(val);
      }
    }

    constexpr ~_Bits() noexcept = default;

    template <typename T>
      requires(std::integral<T> && std::is_unsigned_v<T>)
    constexpr operator T() const noexcept {
      if constexpr (N > MaxNativePrecision) {
        return m_val.get_ui();
      } else {
        return m_val;
      }
    }

    template <typename T>
      requires(std::integral<T> && std::is_signed_v<T>)
    constexpr operator T() const noexcept {
      if constexpr (N > MaxNativePrecision) {
        return cast_to_signed().get_si();
      } else {
        return cast_to_signed();
      }
    }

    // cast to any other Bits type
    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr explicit operator _Bits<M, _Signed>() const noexcept {
      if constexpr (Signed) {
        return cast_to_signed();
      } else {
        return m_val;
      }
    }

    template <
        typename T = std::conditional_t<Signed, SignedStorageType, StorageType>>
    constexpr T get() const {
      if constexpr (std::integral<T> && std::is_signed_v<T>) {
        if constexpr (N > MaxNativePrecision) {
          return cast_to_signed().get_si();
        } else {
          return cast_to_signed();
        }
      } else {
        return m_val;
      }
    }

    // assignment
    _Bits &operator=(const _Bits &o) = default;
    _Bits &operator=(_Bits &&o) noexcept = default;

    template <typename IntType>
      requires std::integral<IntType>
    _Bits &operator=(const IntType &o) {
      m_val = apply_mask(o);
      return *this;
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    _Bits &operator=(const _Bits<M, _Signed> &o) {
      if constexpr ((N <= MaxNativePrecision) && (M > MaxNativePrecision)) {
        m_val = apply_mask(o.m_val.get_ui());
      } else {
        m_val = apply_mask(o.m_val);
      }

      return *this;
    }

    // negate operator
    constexpr _Bits operator-() const {
      _Bits negated_value;
      negated_value.m_val = apply_mask(-m_val);
      return negated_value;
    }

    // invert operator
    constexpr _Bits operator~() const & { return apply_mask(~m_val); }

#define BITS_COMPARISON_OPERATOR(op)                                          \
  constexpr bool operator op(const _Bits &o) const noexcept {                 \
    if constexpr (Signed) {                                                   \
      return cast_to_signed() op o.cast_to_signed();                          \
    } else {                                                                  \
      return m_val op o.m_val;                                                \
    }                                                                         \
  }                                                                           \
                                                                              \
  template <typename IntType>                                                 \
    requires(std::integral<IntType>)                                          \
  constexpr bool operator op(const IntType &o) const noexcept {               \
    if constexpr (Signed) {                                                   \
      return cast_to_signed() op o;                                           \
    } else {                                                                  \
      return m_val op o;                                                      \
    }                                                                         \
  }                                                                           \
                                                                              \
  constexpr bool operator op(const mpz_class &o) const noexcept {             \
    if constexpr (Signed) {                                                   \
      return cast_to_signed() op SignedStorageType{o};                        \
    } else {                                                                  \
      return m_val op o;                                                      \
    }                                                                         \
  }                                                                           \
                                                                              \
  constexpr friend bool operator op(const mpz_class &lhs, const _Bits &rhs) { \
    if constexpr (Signed) {                                                   \
      return SignedStorageType{lhs} op rhs.cast_to_signed();                  \
    } else {                                                                  \
      return lhs op rhs.m_val;                                                \
    }                                                                         \
  }                                                                           \
                                                                              \
  template <typename IntType>                                                 \
    requires(std::integral<IntType>)                                          \
  constexpr friend bool operator op(const IntType &lhs, const _Bits &rhs) {   \
    if constexpr (Signed) {                                                   \
      return lhs op rhs.cast_to_signed();                                     \
    } else {                                                                  \
      return lhs op rhs.m_val;                                                \
    }                                                                         \
  }                                                                           \
                                                                              \
  template <unsigned M, bool _Signed>                                         \
    requires((N != M) || (Signed != _Signed))                                 \
  constexpr bool operator op(const _Bits<M, _Signed> &o) const noexcept {     \
    if constexpr (Signed && _Signed) {                                        \
      return cast_to_signed() op o.cast_to_signed();                          \
    } else if constexpr (Signed && !_Signed) {                                \
      return cast_to_signed() op o.m_val;                                     \
    } else if constexpr (!Signed && _Signed) {                                \
      return m_val op o.cast_to_signed();                                     \
    } else {                                                                  \
      return m_val op o.m_val;                                                \
    }                                                                         \
  }

    BITS_COMPARISON_OPERATOR(==)
    BITS_COMPARISON_OPERATOR(!=)
    BITS_COMPARISON_OPERATOR(<)
    BITS_COMPARISON_OPERATOR(>)
    BITS_COMPARISON_OPERATOR(<=)
    BITS_COMPARISON_OPERATOR(>=)

#undef BITS_COMPARISON_OPERATOR

#define BITS_ARITHMETIC_OPERATOR(op)                                          \
  constexpr _Bits operator op(const _Bits &o) const {                         \
    return _Bits{get() op o.get()};                                           \
  }                                                                           \
                                                                              \
  template <unsigned M, bool _Signed>                                         \
    requires((M != N) || (Signed != _Signed))                                 \
  constexpr _Bits<constmax<N, M>::value, Signed && _Signed> operator op(      \
      const _Bits<M, _Signed> &o) const {                                     \
    if constexpr (M > N) {                                                    \
      return _Bits<constmax<N, M>::value, Signed && _Signed>{                 \
          _Bits<M, Signed>{get()}.get() op o.get()};                          \
    } else {                                                                  \
      return _Bits<constmax<N, M>::value, Signed && _Signed>{                 \
          get() op _Bits<N, _Signed>{o.get()}.get()};                         \
    }                                                                         \
  }                                                                           \
                                                                              \
  constexpr _Bits operator op(const mpz_class &o) const {                     \
    return _Bits{get() op o};                                                 \
  }                                                                           \
                                                                              \
  template <std::integral IntType>                                            \
  constexpr _Bits operator op(const IntType &_rhs) const {                    \
    if constexpr (std::is_signed_v<IntType>) {                                \
      SignedStorageType rhs = _rhs;                                           \
      return _Bits{get() op rhs};                                             \
    } else {                                                                  \
      StorageType rhs = _rhs;                                                 \
      return _Bits{get() op rhs};                                             \
    }                                                                         \
  }                                                                           \
                                                                              \
  template <std::integral IntType>                                            \
  constexpr friend _Bits operator op(const IntType &_lhs, const _Bits &rhs) { \
    if constexpr (std::is_signed_v<IntType>) {                                \
      SignedStorageType lhs = _lhs;                                           \
      return _Bits{lhs op rhs.get()};                                         \
    } else {                                                                  \
      StorageType lhs = _lhs;                                                 \
      return _Bits{lhs op rhs.get()};                                         \
    }                                                                         \
  }

    BITS_ARITHMETIC_OPERATOR(+)
    BITS_ARITHMETIC_OPERATOR(-)
    BITS_ARITHMETIC_OPERATOR(*)
    BITS_ARITHMETIC_OPERATOR(/)
    BITS_ARITHMETIC_OPERATOR(%)
    BITS_ARITHMETIC_OPERATOR(&)
    BITS_ARITHMETIC_OPERATOR(|)
    BITS_ARITHMETIC_OPERATOR(^)

#undef BITS_ARITHMETIC_OPERATOR

    constexpr _Bits operator<<(const _Bits &shamt) const {
      return _Bits{m_val << shamt.get()};
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits operator<<(const _Bits<M, _Signed> &shamt) const {
      return _Bits{m_val << shamt.get()};
    }

    template <std::integral IntType>
    constexpr _Bits operator<<(const IntType &shamt) const {
      return _Bits{m_val << shamt};
    }

    constexpr _Bits operator<<(const mpz_t &shamt) const {
      return _Bits{m_val << shamt};
    }

    template <std::integral IntType>
    constexpr friend IntType operator<<(const IntType &val,
                                        const _Bits &shamt) {
      if constexpr (N > MaxNativePrecision) {
        if constexpr (std::is_signed_v<IntType>) {
          return (val << shamt.m_val).get_si();
        } else {
          return (val << shamt.m_val).get_ui();
        }
      } else {
        return val << shamt.m_val;
      }
    }

    // left shift when the shift amount is not known at compile time.
    // MSB shifted bits are discarded
    constexpr friend mpz_class operator<<(const mpz_class &val,
                                          const _Bits &shamt) {
      return val << shamt.m_val;
    }

    // widening left shift when the shift amount is known at compile time
    template <unsigned SHAMT>
    constexpr _Bits<addsat_v<N, SHAMT>, Signed> sll() const {
      using ReturnType = _Bits<addsat_v<N, SHAMT>, Signed>;
      if constexpr (N >= MaxNativePrecision) {
        return ReturnType{ReturnType{m_val}.m_val << SHAMT};
      } else {
        return ReturnType{m_val}.m_val << SHAMT;
      }
    }

    // widening left shift when the shift amount is not known at compile time
    constexpr _Bits<InfinitePrecision, Signed> widening_sll(
        unsigned shamt) const {
      using ReturnType = _Bits<InfinitePrecision, Signed>;
      return ReturnType{m_val} << shamt;
    }

    constexpr _Bits operator>>(const _Bits &shamt) const {
      return _Bits{m_val >> shamt.m_val};
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits operator>>(const _Bits<M, _Signed> &shamt) const {
      return _Bits{m_val >> shamt.m_val};
    }

    template <std::integral IntType>
    constexpr _Bits operator>>(const IntType &shamt) const {
      return _Bits{m_val >> shamt};
    }

    _Bits operator>>(const mpz_class &shamt) const {
      return _Bits{m_val >> shamt};
    }

    template <std::integral IntType>
    constexpr friend IntType operator>>(const IntType &val,
                                        const _Bits &shamt) {
      return val >> shamt.get();
    }

    friend mpz_class operator>>(const mpz_class &val, const _Bits &shamt) {
      return val >> shamt.get();
    }

    constexpr _Bits sra(const _Bits &shamt) const {
      return apply_mask(cast_to_signed() >> shamt.get());
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits sra(const _Bits<M, _Signed> &shamt) const {
      return apply_mask(cast_to_signed() >> shamt.get());
    }

    template <std::integral IntType>
    constexpr _Bits sra(const IntType &shamt) const {
      return apply_mask(cast_to_signed() >> shamt);
    }

    template <std::integral IntType>
    constexpr friend IntType sra(const IntType &val, const _Bits &shamt) {
      if constexpr (N > MaxNativePrecision) {
        if (Signed) {
          return (val >> shamt.get()).get_si();
        } else {
          return (val >> shamt.get()).get_ui();
        }
      } else {
        return val >> shamt.get();
      }
    }

    _Bits sra(const mpz_class &shamt) const {
      return apply_mask(cast_to_signed() >> shamt);
    }

    friend mpz_class sra(const mpz_class &val, const _Bits &shamt) {
      return val >> shamt.get();
    }

#define BITS_OP_ASSIGN(op)                       \
  template <typename T>                          \
  constexpr _Bits &operator op##=(const T & o) { \
    m_val = (*this op o).m_val;                  \
    return *this;                                \
  }

    BITS_OP_ASSIGN(+)
    BITS_OP_ASSIGN(-)
    BITS_OP_ASSIGN(/)
    BITS_OP_ASSIGN(*)
    BITS_OP_ASSIGN(%)
    BITS_OP_ASSIGN(&)
    BITS_OP_ASSIGN(|)
    BITS_OP_ASSIGN(^)

#undef BITS_OP_ASSIGN

    // pre-increment. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits &operator++() {
      m_val = apply_mask(m_val + 1);
      return *this;
    }

    // post-increment
    _Bits operator++(int) {
      _Bits tmp{m_val};
      m_val = apply_mask(m_val + 1);
      return tmp;
    }

    // pre-decrement. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits &operator--() {
      m_val = apply_mask(m_val - 1);
      return *this;
    }

    // post-increment
    _Bits operator--(int) {
      _Bits tmp{m_val};
      m_val = apply_mask(m_val - 1);
      return tmp;
    }

    friend std::ostream &operator<<(std::ostream &stream, const _Bits &val) {
      if constexpr (std::same_as<StorageType, unsigned __int128> ||
                    std::same_as<StorageType, __int128>) {
        stream << fmt::format("{}", val.m_val);
      } else {
        stream << val.m_val;
      }
      return stream;
    }

    template <unsigned msb, unsigned lsb>
    constexpr _Bits<msb - lsb + 1, false> extract() const {
      static_assert(msb >= lsb);
      return _Bits<msb - lsb + 1, false>{
          m_val >> lsb};  // masking will happen in the constructor
    }

    template <typename IndexType, typename ValueType>
    constexpr _Bits &setBit(const IndexType &idx, const ValueType &value) {
      StorageType pos_mask = static_cast<StorageType>(1) << idx;
      m_val =
          (m_val & ~pos_mask) | ((static_cast<_Bits>(value) << idx) & pos_mask);
      return *this;
    }

    // private:
    // If m_val is private, then _Bits cannot be used as a template parameter
    //  (Would not be 'structural'):
    //  https://en.cppreference.com/w/cpp/language/template_parameters
    // We want to be able to use it as a template parameter because templated
    // IDL functions will do so.
    StorageType m_val;
  };

  struct BitsStrHelpers {
    template <bool AllowUnknown>
    static consteval unsigned get_width(const char *str) {
      uint64_t val = 0;
      unsigned width = 0;
      auto len = strlen(str);
      unsigned base = 10;
      const char *ptr = str;
      if (len >= 3) {
        if (strncmp(str, "0x", 2) == 0) {
          base = 16;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 10) {
        uint64_t pow = 1;
        uint64_t last_val = val;
        for (int i = len - 1; i >= 0; i--) {
          val += (ptr[i] - '0') * pow;
          if (val < last_val) {
            // we overflowed; can't represent this value in 64 bits.
            // For now, we'll just return an overappoximation because
            // trying to find the width from the decimal string at compile time
            // is tricky
            return 1 + (10 * len) / (3);  // 2^3 fits in one decimal digit
          }
          last_val = val;
          pow *= 10;
        }
        width = val == 0 ? 1 : 64 - std::countl_zero(val);
      }
      if (base == 16) {
        // the msb only needs enough bits to hold itself
        if (*ptr >= '0' && *ptr <= '9') {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'0');
        } else if (*ptr >= 'A' && *ptr <= 'F') {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'A' +
                                         (uint32_t)10);
        } else if (*ptr >= 'a' && *ptr <= 'f') {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'a' +
                                         (uint32_t)10);
        }
        if constexpr (AllowUnknown) {
          if (*ptr == 'x' || *ptr == 'X') {
            // unknown is full width
            width += 4;
          }
        }

        // the lsbs need full bits
        width += (len - 1) * 4;

        // special case: if zero, need one bit
        width = width == 0 ? 1 : width;
      }
      return width;
    }

    static consteval unsigned __int128 get_val(const char *str) {
      unsigned __int128 val = 0;
      auto len = strlen(str);
      unsigned base = 10;
      const char *ptr = str;
      if (len >= 3) {
        if (strncmp(str, "0x", 2) == 0) {
          base = 16;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 10) {
        // we only support base-10 literals up to 64 bits. (otherwise, it's hard
        // to know bitwidth at compile time)
        unsigned __int128 pow = 1;
        for (int i = len - 1; i >= 0; i--) {
          val += ((unsigned __int128)(ptr[i] - '0')) * pow;
          pow *= 10;
        }
      }
      if (base == 16) {
        unsigned __int128 pow = 1;
        for (int i = len - 1; i >= 0; i--) {
          if (ptr[i] >= '0' && ptr[i] <= '9') {
            val += ((unsigned __int128)(ptr[i] - '0')) * pow;
          } else if (ptr[i] >= 'A' && ptr[i] <= 'F') {
            val += ((unsigned __int128)(ptr[i] - 'A' + 10)) * pow;
          } else if (ptr[i] >= 'a' && ptr[i] <= 'f') {
            val += ((unsigned __int128)(ptr[i] - 'a' + 10)) * pow;
          }
          pow *= 16;
        }
      }
      return val;
    }

    static consteval unsigned __int128 get_unknown_mask(const char *str) {
      unsigned __int128 mask = 0;
      auto len = strlen(str);
      unsigned base = 10;
      const char *ptr = str;
      if (len >= 3) {
        if (strncmp(str, "0x", 2) == 0) {
          base = 16;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 10) {
        return 0;  // there are no unknowns in a base-10 literal
      }
      if (base == 16) {
        unsigned __int128 shamt = 0;
        for (int i = len - 1; i >= 0; i--) {
          if (ptr[i] == 'x' || ptr[i] == 'X') {
            mask |= static_cast<__int128>(0xf) << shamt;
          }
          shamt += 4;
        }
      }
      return mask;
    }
  };

  // used to translate literal strings into a Bits<N> type
  template <bool AllowUnknown, char... Str>
  struct BitsStr {
    static constexpr char str[sizeof...(Str)] = {Str...};

    static constexpr unsigned width =
        BitsStrHelpers::get_width<AllowUnknown>(str);
    static_assert(
        width <= 128,
        "Cannot create bits literal of width >= 128 (use \"\"_mpz instead)");
    static constexpr unsigned __int128 val = BitsStrHelpers::get_val(str);
    static constexpr unsigned __int128 unknown_mask =
        BitsStrHelpers::get_unknown_mask(str);
  };

  template <bool AllowUnknown, TemplateString Str>
  struct BitsTemplateStr {
    static constexpr unsigned width =
        BitsStrHelpers::get_width<AllowUnknown>(Str.cstr_value);
    static_assert(
        width <= 128,
        "Cannot create bits literal of width >= 128 (use \"\"_mpz instead)");
    static constexpr unsigned __int128 val =
        BitsStrHelpers::get_val(Str.cstr_value);
    static constexpr unsigned __int128 unknown_mask =
        BitsStrHelpers::get_unknown_mask(Str.cstr_value);
  };

  static_assert(BitsStr<false, '0', 'x', '1', '\0'>::width == 1);
  static_assert(BitsStr<false, '0', 'x', '2', '\0'>::width == 2);
  static_assert(BitsStr<false, '0', 'x', '8', '\0'>::width == 4);
  static_assert(BitsStr<false, '0', 'x', '1', 'f', '\0'>::width == 5);

  // be careful with negative numbers here, since literals are always unsigned
  //
  // auto b = -15_b; // b will be +1, because 15_b is only four bits, and
  // negation loses the sign bit
  template <char... Str>
  constexpr _Bits<BitsStr<false, Str..., '\0'>::width, false> operator""_b() {
    if constexpr (BitsStr<false, Str..., '\0'>::width <=
                  _Bits<BitsStr<false, Str..., '\0'>::width,
                        false>::MaxNativePrecision) {
      return BitsStr<false, Str..., '\0'>::val;
    } else {
      return mpz_class{BitsStr<false, Str..., '\0'>::str};
    }
  }

  // signed bits
  template <char... Str>
  constexpr _Bits<BitsStr<false, Str..., '\0'>::width + 1, false>
  operator""_sb() {
    if constexpr ((BitsStr<false, Str..., '\0'>::width + 1) <=
                  _Bits<(BitsStr<false, Str..., '\0'>::width + 1),
                        false>::MaxNativePrecision) {
      return BitsStr<false, Str..., '\0'>::val;
    } else {
      return mpz_class{BitsStr<false, Str..., '\0'>::str};
    }
  }

  static_assert((0x0_b).Width == 1);
  static_assert((0x1_b).Width == 1);
  static_assert((0_b).Width == 1);
  static_assert((1_b).Width == 1);
  static_assert((0x2_b).Width == 2);
  static_assert((0x7_b).Width == 3);
  static_assert((0x8_b).Width == 4);
  static_assert((0xf_b).Width == 4);
  static_assert((0x1f_b).Width == 5);
  static_assert((0xffffffffffffffff_b).Width == 64);

  static_assert((0x1_b).get() == 1);
  static_assert((0x2_b).get() == 2);
  static_assert((0x7_b).get() == 7);
  static_assert((0x8_b).get() == 8);
  static_assert((0xf_b).get() == 15);
  static_assert((0x1f_b).get() == 0x1f);
  static_assert((0xff_b).get() == 0xff);
  static_assert((0xffffffff_b).get() == 0xfffffffful);
  static_assert((0xfffffffff_b).get() == 0xffffffffful);
  static_assert((0xffffffff1_b).get() == 0xffffffff1ul);
  static_assert((0xfffffffffffffff_b).get() == 0xffffffffffffffful);
  static_assert((0xffffffffffffffff_b).get() == 0xfffffffffffffffful);

  static_assert((1_b).get() == 1);
  static_assert((2_b).get() == 2);
  static_assert((7_b).get() == 7);
  static_assert((8_b).get() == 8);
  static_assert((15_b).get() == 15);
  static_assert((31_b).get() == 31);
  static_assert((1152921504606846975_b).get() == 0xfffffffffffffff);
  static_assert((18446744073709551615_b).get() == 0xffffffffffffffff);
}  // namespace udb

// format Bits as their underlying type when using format()
template <unsigned N, bool Signed>
  requires(N <= udb::BitsMaxNativePrecision)
struct fmt::formatter<udb::_Bits<N, Signed>>
    : formatter<typename udb::_Bits<N, Signed>::StorageType> {
  template <typename CONTEXT_TYPE>
  auto format(udb::_Bits<N, Signed> value, CONTEXT_TYPE &ctx) const {
    return fmt::formatter<typename udb::_Bits<N, Signed>::StorageType>::format(
        value.get(), ctx);
  }
};

template <unsigned N, bool Signed>
  requires(N > udb::BitsMaxNativePrecision)
struct fmt::formatter<udb::_Bits<N, Signed>> {
 private:
  fmt::detail::dynamic_format_specs<char> specs_;

 public:
  constexpr auto parse(fmt::format_parse_context &ctx)
      -> decltype(ctx.begin()) {
    auto end = parse_format_specs(ctx.begin(), ctx.end(), specs_, ctx,
                                  fmt::detail::type::int_type);
    return end;
  }

  template <class FormatContext>
  auto format(const udb::_Bits<N, Signed> &c, FormatContext &ctx)
      -> decltype(ctx.out()) {
    fmt::detail::handle_dynamic_spec<fmt::detail::precision_checker>(
        specs_.width, specs_.width_ref, ctx);
    int base = 10;
    std::string gmp_fmt_string = "%";
    if (specs_.fill.data()[0] == '0') gmp_fmt_string += "0";
    if (specs_.alt) gmp_fmt_string += "#";
    if (specs_.sign == fmt::sign_t::plus) gmp_fmt_string += "+";
    if (specs_.sign == fmt::sign_t::minus) gmp_fmt_string += "-";
    if (specs_.sign == fmt::sign_t::space) gmp_fmt_string += " ";
    if (specs_.width != 0) gmp_fmt_string += std::to_string(specs_.width);
    gmp_fmt_string += "Z";
    if (specs_.type == fmt::presentation_type::hex_lower) {
      base = 16;
      gmp_fmt_string += "x";
    } else if (specs_.type == fmt::presentation_type::hex_upper) {
      base = 16;
      gmp_fmt_string += "X";
    } else if (specs_.type == fmt::presentation_type::oct) {
      base = 8;
      gmp_fmt_string += "o";
    } else {
      base = 10;
      gmp_fmt_string += "d";
    }
    size_t strwidth = std::max((size_t)specs_.width,
                               mpz_sizeinbase(c.get().get_mpz_t(), base));
    char *str = new char[strwidth + 100];
    gmp_snprintf(str, strwidth + 100, gmp_fmt_string.c_str(),
                 c.get().get_mpz_t());
    auto ret_val = fmt::format_to(ctx.out(), "{}", str);
    delete[] str;
    return ret_val;
  }
};

namespace std {
  template <unsigned N, bool Signed>
  std::string to_string(const udb::_Bits<N, Signed> &i) {
    if constexpr (N > udb::_Bits<64, false>::MaxNativePrecision) {
      return i.get_str();
    } else {
      return to_string(i.get());
    }
  }
}  // namespace std

namespace std {

  template <unsigned N, bool Signed>
  struct hash<udb::_Bits<N, Signed>> {
    std::size_t operator()(const udb::_Bits<N, Signed> &s) const noexcept {
      return std::hash<typename udb::_Bits<N, Signed>::StorageType>{}(s.get());
    }
  };

  template <unsigned N, bool Signed>
  class numeric_limits<udb::_Bits<N, Signed>> {
   public:
    static constexpr bool is_specialized = true;
    static constexpr bool is_signed = Signed;
    static constexpr bool is_integer = true;
    static constexpr bool is_exact = true;
    static constexpr bool has_infinity = false;
    static constexpr bool has_quiet_NaN = false;
    static constexpr bool has_signaling_NaN = false;
    static constexpr bool has_dermon_loss = false;
    static constexpr std::float_round_style round_style =
        std::round_toward_zero;
    static constexpr bool is_iec559 = false;
    static constexpr bool is_bounded =
        (N != udb::_Bits<N, Signed>::InfinitePrecision);
    static constexpr int digits = Signed ? N - 1 : N;
    static constexpr int digits10 = N < udb::_Bits<N, Signed>::InfinitePrecision
                                        ? digits * std::log10(2)
                                        : 0;
    static constexpr int max_digits10 = 0;
    static constexpr int radix = 2;
    static constexpr int min_exponent = 0;
    static constexpr int min_exponent10 = 0;
    static constexpr int max_exponent = 0;
    static constexpr int max_exponent10 = 0;
    static constexpr bool trap = true;
    static constexpr bool tinyness_before = false;

    static consteval udb::_Bits<N, Signed> min() noexcept {
      if constexpr (Signed) {
        return -typename udb::_Bits<N, Signed>{
            typename udb::_Bits<N, Signed>::SignedStorageType{1} << (N - 1)};
      } else {
        return 0;
      }
    }
    static consteval udb::_Bits<N, Signed> lowest() noexcept { return min(); }
    static consteval udb::_Bits<N, Signed> max() noexcept {
      if constexpr (N <= udb::_Bits<N, Signed>::MaxNativePrecision) {
        if (N == sizeof(typename udb::_Bits<N, Signed>::StorageType) * 8) {
          if (Signed) {
            return std::numeric_limits<
                typename udb::_Bits<N, Signed>::SignedStorageType>::max();
          } else {
            return std::numeric_limits<
                typename udb::_Bits<N, Signed>::StorageType>::max();
          }
        } else {
          if (Signed) {
            return (typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) -
                   1;
          } else {
            return (typename udb::_Bits<N, Signed>::StorageType{1} << (N)) - 1;
          }
        }
      } else {
        if (Signed) {
          return (typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) -
                 1;
        } else {
          return (typename udb::_Bits<N, Signed>::StorageType{1} << N) - 1;
        }
      }
    }
    static consteval udb::_Bits<N, Signed> epsilon() noexcept { return 0; }
    static consteval udb::_Bits<N, Signed> round_error() noexcept { return 0; }
    static consteval udb::_Bits<N, Signed> infinity() noexcept { return 0; }
    static consteval udb::_Bits<N, Signed> quiet_NaN() noexcept { return 0; }
    static consteval udb::_Bits<N, Signed> denorm_min() noexcept { return 0; }
  };
}  // namespace std

static_assert(std::numeric_limits<udb::_Bits<8, false>>::min() == 0);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::min() == -128);
static_assert(std::numeric_limits<udb::_Bits<8, false>>::max() == 255);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::max() == 127);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::min() == 0);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::min() == -256);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::max() == 511);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::max() == 255);

namespace udb {
  // Bits where the width is only known at runtime (usually because the width is
  // parameter-dependent)
  template <unsigned MaxN, bool Signed>
  class _RuntimeBits {
    struct UnknownWidthType {};
    UnknownWidthType UnknownWidth;

    template <typename T>
    _RuntimeBits(const T &initial_value, const UnknownWidthType &)
        : m_value(initial_value), m_width_known(false) {}

    template <unsigned OtherMaxN, bool OtherSigned>
    friend class _RuntimeBits;

    using StorageType = _Bits<MaxN, Signed>::StorageType;

    StorageType mask() const {
      if (m_width == MaxN) {
        return ~StorageType{0};
      } else {
        return (StorageType{1} << m_width) - 1;
      }
    }

    void apply_mask() {
      if (m_width_known) {
        m_value = m_value & mask();
      }
    }

   public:
    static constexpr bool IsABits = true;

    _RuntimeBits() : m_width_known(false) {}

    template <std::integral IntType>
    _RuntimeBits(const IntType &initial_value)
        : m_value(initial_value), m_width_known(false) {}

    template <unsigned N, bool _Signed>
    _RuntimeBits(const _Bits<N, _Signed> &initial_value)
        : m_value(initial_value), m_width(N), m_width_known(true) {}

    template <typename T>
    _RuntimeBits(const T &initial_value, unsigned width)
        : m_value(initial_value), m_width(width), m_width_known(true) {
      apply_mask();
    }

    _RuntimeBits(const _RuntimeBits &initial_value)
        : m_value(initial_value.value()),
          m_width(initial_value.m_width),
          m_width_known(initial_value.m_width_known) {}

    template <unsigned OtherMaxN>
    _RuntimeBits(const _RuntimeBits<OtherMaxN, Signed> &initial_value)
        : m_value(initial_value.value()),
          m_width(initial_value.m_width),
          m_width_known(initial_value.m_width_known) {
      apply_mask();
    }

    template <bool _Signed = Signed>
      requires(_Signed == false)
    _RuntimeBits<MaxN, true> make_signed() const {
      return _RuntimeBits<MaxN, true>{sign_extend(m_value.get()), m_width};
    }
    template <bool _Signed = Signed>
      requires(_Signed == true)
    const _RuntimeBits<MaxN, true> &make_signed() const {
      return *this;
    }

    StorageType sign_extend(const StorageType &value) const {
      if (m_width_known) {
        udb_assert(m_width <= BitsMaxNativePrecision,
                   "Can't sign extend a GMP number");
        if (m_width == sizeof(StorageType) * 8) {
          // exact fit, no extension needed
          return value;  // no extension needed
        } else {
          if ((value & (StorageType{1} << (m_width - 1))) != 0) {
            // fill with ones
            return value | ~mask();
          } else {
            // no extension needed
            return value;
          }
        }
      } else {
        throw UndefinedValueError(
            "Can't sign extend when the width is unknown");
      }
    }

    unsigned width() const {
      if (!m_width_known) {
        throw UndefinedValueError("RuntimeBits width is not known");
      }
      return m_width;
    }
    bool width_known() const { return m_width_known; }
    auto value() const { return m_value; }
    auto get() const { return m_value.get(); }

    template <typename IntType>
      requires(std::integral<IntType>)
    operator IntType() const noexcept {
      return static_cast<IntType>(m_value);
    }

    template <typename T>
    _RuntimeBits operator<<(const T &shamt) const {
      if (m_width_known) {
        return {m_value << shamt, m_width + shamt};
      } else {
        return {m_value << shamt, UnknownWidth};
      }
    }

    template <typename T>
    _RuntimeBits operator>>(const T &shamt) const {
      if (m_width_known) {
        return {m_value >> shamt, m_width};
      } else {
        return {m_value >> shamt, UnknownWidth};
      }
    }

#define RUNTIME_BITS_BINARY_OP(op)                                         \
  template <unsigned N, bool _Signed>                                      \
    requires(MaxN >= N)                                                    \
  _RuntimeBits operator op(const _Bits<N, _Signed> &other) const {         \
    if (m_width_known) {                                                   \
      return {m_value op _Bits<MaxN, _Signed>{other}.get(),                \
              std::max(N, m_width)};                                       \
    } else {                                                               \
      return {m_value op _Bits<MaxN, _Signed>{other}.get(), UnknownWidth}; \
    }                                                                      \
  }                                                                        \
                                                                           \
  template <unsigned N, bool _Signed>                                      \
    requires(MaxN < N)                                                     \
  _RuntimeBits operator op(const _Bits<N, _Signed> &other) const {         \
    if (m_width_known) {                                                   \
      return {m_value op other.get(), std::max(N, m_width)};               \
    } else {                                                               \
      return {m_value op other.get(), UnknownWidth};                       \
    }                                                                      \
  }                                                                        \
                                                                           \
  _RuntimeBits operator op(const _RuntimeBits &other) const {              \
    if (m_width_known && other.m_width_known) {                            \
      return {m_value op other.m_value, std::max(other.m_width, m_width)}; \
    } else {                                                               \
      return {m_value op other.m_value, UnknownWidth};                     \
    }                                                                      \
  }

    RUNTIME_BITS_BINARY_OP(|)
    RUNTIME_BITS_BINARY_OP(&)
    RUNTIME_BITS_BINARY_OP(^)

#undef RUNTIME_BITS_BINARY_OP

#define RUNTIME_BITS_BINARY_OP(op)                                           \
  _RuntimeBits operator op(const _RuntimeBits &other) const {                \
    if (m_width_known && other.m_width_known) {                              \
      if (other.m_width != m_width) {                                        \
        if (other.m_width > m_width) {                                       \
          return {                                                           \
              _RuntimeBits{m_value, other.m_width}.m_value op other.m_value, \
              std::max(other.m_width, m_width)};                             \
        } else {                                                             \
          return {m_value op _RuntimeBits{other.m_value, m_width}.m_value,   \
                  std::max(other.m_width, m_width)};                         \
        }                                                                    \
      } else {                                                               \
        return {m_value op other.m_value, std::max(other.m_width, m_width)}; \
      }                                                                      \
    } else {                                                                 \
      return {m_value op other.m_value, UnknownWidth};                       \
    }                                                                        \
  }                                                                          \
                                                                             \
  template <unsigned N, bool _Signed>                                        \
  _RuntimeBits<constmax<MaxN, N>::value, Signed && _Signed> operator op(     \
      const _Bits<N, _Signed> &other) const {                                \
    using ReturnType =                                                       \
        _RuntimeBits<constmax<MaxN, N>::value, Signed && _Signed>;           \
    if (m_width_known) {                                                     \
      if (N != m_width) {                                                    \
        if (N > m_width) {                                                   \
          return {ReturnType{m_value, N}.m_value op other.get(), N};         \
        } else {                                                             \
          return {m_value op ReturnType{other.get(), m_width}.m_value,       \
                  m_width};                                                  \
        }                                                                    \
      } else {                                                               \
        return {m_value op other.m_val, N};                                  \
      }                                                                      \
    } else {                                                                 \
      constexpr unsigned BigN = constmax<MaxN, N>::value;                    \
      return {_RuntimeBits<BigN, Signed>{m_value, UnknownWidth}              \
                  .m_value op _Bits<BigN, _Signed>{other.m_val}              \
                  .get(),                                                    \
              UnknownWidth};                                                 \
    }                                                                        \
  }

    RUNTIME_BITS_BINARY_OP(+)
    RUNTIME_BITS_BINARY_OP(-)
    RUNTIME_BITS_BINARY_OP(*)
    RUNTIME_BITS_BINARY_OP(/)
    RUNTIME_BITS_BINARY_OP(%)

#undef RUNTIME_BITS_BINARY_OP

#define RUNTIME_BITS_BINARY_OP(op)                    \
  bool operator op(const _RuntimeBits &other) const { \
    return m_value op other.m_value;                  \
  }

    RUNTIME_BITS_BINARY_OP(==)
    RUNTIME_BITS_BINARY_OP(!=)
    RUNTIME_BITS_BINARY_OP(>)
    RUNTIME_BITS_BINARY_OP(>=)
    RUNTIME_BITS_BINARY_OP(<)
    RUNTIME_BITS_BINARY_OP(<=)

#undef RUNTIME_BITS_BINARY_OP

    _RuntimeBits operator~() { return {~m_value, m_width}; }

    _RuntimeBits operator-() { return {-m_value, m_width}; }

#define RUNTIME_BITS_ASSIGN_OP(op)                            \
  template <unsigned N, bool _Signed>                         \
  _RuntimeBits &operator op(const _Bits<N, _Signed> &other) { \
    m_value op other;                                         \
    return *this;                                             \
  }                                                           \
                                                              \
  _RuntimeBits &operator op(const _RuntimeBits & other) {     \
    m_value op other.m_value;                                 \
    return *this;                                             \
  }                                                           \
                                                              \
  template <std::integral IntType>                            \
  _RuntimeBits &operator op(const IntType & other) {          \
    m_value op other;                                         \
    return *this;                                             \
  }

    RUNTIME_BITS_ASSIGN_OP(|=)
    RUNTIME_BITS_ASSIGN_OP(&=)
    RUNTIME_BITS_ASSIGN_OP(^=)
    RUNTIME_BITS_ASSIGN_OP(+=)
    RUNTIME_BITS_ASSIGN_OP(-=)
    RUNTIME_BITS_ASSIGN_OP(*=)
    RUNTIME_BITS_ASSIGN_OP(/=)
    RUNTIME_BITS_ASSIGN_OP(%=)

#undef RUNTIME_BITS_ASSIGN_OP

    // left shift when the shift amount is known at compile time
    template <unsigned SHAMT>
    _RuntimeBits<addsat_v<MaxN, SHAMT>, Signed> sll() const {
      if (m_width_known) {
        auto result_width = m_width + SHAMT;
        return {_Bits<addsat_v<MaxN, SHAMT>, Signed>{m_value} << SHAMT,
                result_width};
      } else {
        return {_Bits<addsat_v<MaxN, SHAMT>, Signed>{m_value} << SHAMT};
      }
    }

    // widening left shift when the shift amount is not known at compile time
    _RuntimeBits<BitsInfinitePrecision, Signed> widening_sll(
        unsigned shamt) const {
      if (m_width_known) {
        return {_Bits<BitsInfinitePrecision, Signed>{m_value} << shamt,
                m_width + shamt};
      } else {
        return _Bits<BitsInfinitePrecision, Signed>{m_value} << shamt;
      }
    }

   private:
    _Bits<MaxN, Signed> m_value;
    unsigned m_width;
    bool m_width_known;
  };

  template <unsigned N, unsigned MaxN, bool ASigned, bool BSigned>
  bool operator==(const _Bits<N, ASigned> &a,
                  const _RuntimeBits<MaxN, BSigned> &b) {
    return a == b.value();
  }

  // construct Bits from RuntimeBits
  template <unsigned N, bool BitsSigned>
  template <unsigned MaxN, bool RuntimeSigned>
  _Bits<N, BitsSigned>::_Bits(const _RuntimeBits<MaxN, RuntimeSigned> &val) {
    if constexpr (RuntimeSigned) {
      m_val = _Bits<N, BitsSigned>{val.make_signed().value().get()}.m_val;
    } else {
      m_val = _Bits<N, BitsSigned>{val.value().get()}.m_val;
    }
  }

  using RuntimeBits = _RuntimeBits<BitsInfinitePrecision, false>;

  template <unsigned N, bool Signed>
  class _PossiblyUnknownBits {
   public:
    // used for template concept resolution
    constexpr static bool IsABits = true;

    // advertise the width
    constexpr static unsigned Width = N;

    constexpr static unsigned width() { return N; }

    using StorageType = typename _Bits<N, Signed>::StorageType;
    using SignedStorageType = typename _Bits<N, Signed>::SignedStorageType;

    constexpr _PossiblyUnknownBits()
        : m_unknown_mask(~static_cast<decltype(m_unknown_mask)>(0)) {}

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits(
        const _PossiblyUnknownBits<M, _Signed> &other)
        : m_value(other.m_value), m_unknown_mask(other.m_unknown_mask) {}

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits(const _Bits<M, _Signed> &other)
        : m_value(other), m_unknown_mask(0) {}

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits(const _Bits<M, _Signed> &other,
                                   const _Bits<M, false> &other_mask)
        : m_value(other), m_unknown_mask(other_mask) {}

    template <unsigned M, bool _Signed>
    _PossiblyUnknownBits(_PossiblyUnknownBits<M, Signed> &&other) noexcept
        : m_value(std::move(other.m_value)),
          m_unknown_mask(std::move(other.m_value)) {}

    template <unsigned M, bool _Signed>
    _PossiblyUnknownBits(_Bits<M, Signed> &&other) noexcept
        : m_value(std::move(other)), m_unknown_mask(0) {}

    template <std::integral IntType>
    constexpr _PossiblyUnknownBits(const IntType &val)
        : m_value(val), m_unknown_mask(0) {}

    template <std::integral IntType, std::integral MaskIntType>
    constexpr _PossiblyUnknownBits(const IntType &val, const MaskIntType &mask)
        : m_value(val), m_unknown_mask(mask) {}

    constexpr ~_PossiblyUnknownBits() noexcept = default;

    constexpr _Bits<N, false> unknown_mask() const { return m_unknown_mask; }

    template <std::integral T>
    constexpr operator T() const {
      if (m_unknown_mask == 0) {
        return static_cast<T>(m_value);
      } else {
        throw UndefinedValueError(
            "Cannot convert value with unknowns to a native C++ type");
      }
    }

    template <unsigned M, bool _Signed>
    constexpr operator _Bits<M, Signed>() const {
      if (m_unknown_mask == 0) {
        return m_value;
      } else {
        throw UndefinedValueError(
            "Cannot convert value with unknowns to Bits type");
      }
    }

    template <
        typename T = std::conditional_t<Signed, SignedStorageType, StorageType>>
    constexpr T get() const {
      if (m_unknown_mask == 0) {
        return m_value.get();
      } else {
        throw UndefinedValueError(
            "Cannot convert value with unknowns to a native C++ type");
      }
    }

    // assignment
    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits &operator=(
        const _PossiblyUnknownBits<M, _Signed> &o) {
      m_value = o.m_value;
      m_unknown_mask = o.m_unknown_mask;
      return *this;
    }

    template <unsigned M, bool _Signed>
    _PossiblyUnknownBits &operator=(
        const _PossiblyUnknownBits<M, _Signed> &&o) noexcept {
      m_value = std::move(o.m_value);
      m_unknown_mask = std::move(o.m_unknown_mask);
      return *this;
    }

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits &operator=(const _Bits<M, _Signed> &o) {
      m_value = o;
      m_unknown_mask = 0;
      return *this;
    }

    template <unsigned M, bool _Signed>
    _PossiblyUnknownBits &operator=(const _Bits<M, _Signed> &&o) noexcept {
      m_value = std::move(o);
      m_unknown_mask = 0;
      return *this;
    }

    template <std::integral IntType>
    constexpr _PossiblyUnknownBits &operator=(const IntType &o) {
      m_value = o;
      m_unknown_mask = 0;
      return *this;
    }

    // negate operator
    constexpr _PossiblyUnknownBits operator-() const {
      return {-m_value, m_unknown_mask};
    }

    // invert operator
    constexpr _PossiblyUnknownBits operator~() const & {
      return {~m_value, m_unknown_mask};
    }

#define BITS_COMPARISON_OPERATOR(op)                                    \
  template <unsigned M, bool _Signed>                                   \
  constexpr bool operator op(const _PossiblyUnknownBits<M, _Signed> &o) \
      const {                                                           \
    if (m_unknown_mask != 0 || o.m_unknown_mask != 0) {                 \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return m_value op o;                                                \
  }                                                                     \
                                                                        \
  template <unsigned M, bool _Signed>                                   \
  constexpr bool operator op(const _Bits<M, _Signed> &o) const {        \
    if (m_unknown_mask != 0) {                                          \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return m_value op o;                                                \
  }                                                                     \
                                                                        \
  template <std::integral IntType>                                      \
  constexpr bool operator op(const IntType &o) const {                  \
    if (m_unknown_mask != 0) {                                          \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return m_value op o;                                                \
  }                                                                     \
                                                                        \
  constexpr bool operator op(const mpz_class &o) const {                \
    if (m_unknown_mask != 0) {                                          \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return m_value op o;                                                \
  }                                                                     \
                                                                        \
  constexpr friend bool operator op(const mpz_class &lhs,               \
                                    const _PossiblyUnknownBits &rhs) {  \
    if (rhs.m_unknown_mask != 0) {                                      \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return lhs op rhs.m_value;                                          \
  }                                                                     \
                                                                        \
  template <std::integral IntType>                                      \
  constexpr friend bool operator op(const IntType &lhs,                 \
                                    const _PossiblyUnknownBits &rhs) {  \
    if (rhs.m_unknown_mask != 0) {                                      \
      throw UndefinedValueError("Cannot compare unknown value");        \
    }                                                                   \
    return lhs op rhs.m_value;                                          \
  }

    BITS_COMPARISON_OPERATOR(==)
    BITS_COMPARISON_OPERATOR(!=)
    BITS_COMPARISON_OPERATOR(<)
    BITS_COMPARISON_OPERATOR(>)
    BITS_COMPARISON_OPERATOR(<=)
    BITS_COMPARISON_OPERATOR(>=)

#undef BITS_COMPARISON_OPERATOR

#define BITS_ARITHMETIC_OPERATOR(op)                                       \
  template <unsigned M, bool _Signed>                                      \
  constexpr _PossiblyUnknownBits operator op(                              \
      const _PossiblyUnknownBits<M, _Signed> &o) const {                   \
    if (m_unknown_mask != 0 || o.m_unknown_mask != 0) {                    \
      throw UndefinedValueError("Operator undefined with unknown values"); \
    }                                                                      \
    return {m_value op o.m_value};                                         \
  }                                                                        \
                                                                           \
  template <unsigned M, bool _Signed>                                      \
  constexpr _PossiblyUnknownBits operator op(const _Bits<M, _Signed> &o)   \
      const {                                                              \
    if (m_unknown_mask != 0) {                                             \
      throw UndefinedValueError("Operator undefined with unknown values"); \
    }                                                                      \
    return {m_value op o};                                                 \
  }                                                                        \
                                                                           \
  constexpr _PossiblyUnknownBits operator op(const mpz_class &o) const {   \
    if (m_unknown_mask != 0) {                                             \
      throw UndefinedValueError("Operator undefined with unknown values"); \
    }                                                                      \
    return {m_value op o};                                                 \
  }                                                                        \
                                                                           \
  template <std::integral IntType>                                         \
  constexpr _PossiblyUnknownBits operator op(const IntType &_rhs) const {  \
    if (m_unknown_mask != 0) {                                             \
      throw UndefinedValueError("Operator undefined with unknown values"); \
    }                                                                      \
    return {m_value op _rhs};                                              \
  }                                                                        \
                                                                           \
  template <std::integral IntType>                                         \
  constexpr friend _PossiblyUnknownBits operator op(                       \
      const IntType &_lhs, const _PossiblyUnknownBits &rhs) {              \
    if (rhs.m_unknown_mask != 0) {                                         \
      throw UndefinedValueError("Operator undefined with unknown values"); \
    }                                                                      \
    return {_lhs op rhs.m_value};                                          \
  }

    BITS_ARITHMETIC_OPERATOR(+)
    BITS_ARITHMETIC_OPERATOR(-)
    BITS_ARITHMETIC_OPERATOR(*)
    BITS_ARITHMETIC_OPERATOR(/)
    BITS_ARITHMETIC_OPERATOR(%)

#undef BITS_ARITHMETIC_OPERATOR

#define BITS_BITWISE_OPERATOR(op)                                         \
  template <unsigned M, bool _Signed>                                     \
  constexpr _PossiblyUnknownBits operator op(                             \
      const _PossiblyUnknownBits<M, _Signed> &o) const {                  \
    return {m_value op o.m_value, m_unknown_mask & o.m_unknown_mask};     \
  }                                                                       \
  template <unsigned M, bool _Signed>                                     \
  constexpr _PossiblyUnknownBits operator op(const _Bits<M, _Signed> &o)  \
      const {                                                             \
    return {m_value op o, m_unknown_mask};                                \
  }                                                                       \
  template <unsigned MaxN, bool _Signed>                                  \
  constexpr _PossiblyUnknownBits operator op(                             \
      const _RuntimeBits<MaxN, _Signed> &o) const {                       \
    return {m_value op o, m_unknown_mask};                                \
  }                                                                       \
                                                                          \
  constexpr _PossiblyUnknownBits operator op(const mpz_class &o) const {  \
    return {m_value op o, m_unknown_mask};                                \
  }                                                                       \
  template <std::integral IntType>                                        \
  constexpr _PossiblyUnknownBits operator op(const IntType &_rhs) const { \
    return {m_value op _rhs, m_unknown_mask};                             \
  }                                                                       \
  template <unsigned M, bool _Signed>                                     \
  constexpr friend _PossiblyUnknownBits operator op(                      \
      const _Bits<M, _Signed> &_lhs, const _PossiblyUnknownBits &rhs) {   \
    return {_lhs op rhs.m_value, rhs.m_unknown_mask};                     \
  }                                                                       \
  template <std::integral IntType>                                        \
  constexpr friend _PossiblyUnknownBits operator op(                      \
      const IntType &_lhs, const _PossiblyUnknownBits &rhs) {             \
    return {_lhs op rhs.m_value, rhs.m_unknown_mask};                     \
  }

    BITS_BITWISE_OPERATOR(&)
    BITS_BITWISE_OPERATOR(|)
    BITS_BITWISE_OPERATOR(^)

#undef BITS_BITWISE_OPERATOR

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator<<(
        const _PossiblyUnknownBits<M, _Signed> &shamt) const {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return {m_value << shamt.m_value, m_unknown_mask << shamt.m_value};
    }

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator<<(
        const _Bits<M, _Signed> &shamt) const {
      return {m_value << shamt, m_unknown_mask << shamt};
    }

    template <std::integral IntType>
    constexpr _PossiblyUnknownBits operator<<(const IntType &shamt) const {
      return {m_value << shamt, m_unknown_mask << shamt};
    }

    constexpr _PossiblyUnknownBits operator<<(const mpz_t &shamt) const {
      return {m_value << shamt, m_unknown_mask << shamt};
    }

    // the result has to be known
    template <std::integral IntType>
    constexpr friend IntType operator<<(const IntType &val,
                                        const _PossiblyUnknownBits &shamt) {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return {val << shamt.m_value};
    }

    template <unsigned M, bool _Signed>
    constexpr friend _Bits<M, _Signed> operator<<(
        const _Bits<M, _Signed> &lhs, const _PossiblyUnknownBits &shamt) {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return {lhs << shamt.m_value};
    }

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator>>(
        const _PossiblyUnknownBits<M, _Signed> &shamt) const {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return {m_value >> shamt.m_value, m_unknown_mask >> shamt.m_value};
    }

    template <unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator>>(
        const _Bits<M, _Signed> &shamt) const {
      return {m_value >> shamt, m_unknown_mask >> shamt};
    }

    template <std::integral IntType>
    constexpr _PossiblyUnknownBits operator>>(const IntType &shamt) const {
      return {m_value >> shamt, m_unknown_mask >> shamt};
    }

    _PossiblyUnknownBits operator>>(const mpz_class &shamt) const {
      return {m_value >> shamt, m_unknown_mask >> shamt};
    }

    template <unsigned M, bool _Signed>
    constexpr friend _Bits<M, _Signed> operator>>(
        const _Bits<M, _Signed> &val, const _PossiblyUnknownBits &shamt) {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return val >> shamt.m_value;
    }

    template <std::integral IntType>
    constexpr friend IntType operator>>(const IntType &val,
                                        const _PossiblyUnknownBits &shamt) {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return val >> shamt.m_value;
    }

    friend mpz_class operator>>(const mpz_class &val,
                                const _PossiblyUnknownBits &shamt) {
      if (shamt.m_unknown_mask != 0) {
        throw UndefinedValueError("Cannot shift an unknown amount");
      }
      return val >> shamt.m_value;
    }

    // widening left shift when the shift amount is known at compile time
    template <unsigned SHAMT>
    constexpr _PossiblyUnknownBits<addsat_v<N, SHAMT>, Signed> sll() const {
      using ReturnType = _PossiblyUnknownBits<addsat_v<N, SHAMT>, Signed>;
      if constexpr (addsat_v<N, SHAMT> >= BitsMaxNativePrecision) {
        return ReturnType{ReturnType{m_value}.m_value << SHAMT,
                          ReturnType{m_value}.m_unknown_mask << SHAMT};
      } else {
        return ReturnType{ReturnType{m_value}.m_value << SHAMT,
                          ReturnType{m_value}.m_unknown_mask << SHAMT};
      }
    }

#define BITS_OP_ASSIGN(op)                                      \
  template <typename T>                                         \
  constexpr _PossiblyUnknownBits &operator op##=(const T & o) { \
    *this = (*this op o);                                       \
    return *this;                                               \
  }

    BITS_OP_ASSIGN(+)
    BITS_OP_ASSIGN(-)
    BITS_OP_ASSIGN(/)
    BITS_OP_ASSIGN(*)
    BITS_OP_ASSIGN(%)
    BITS_OP_ASSIGN(&)
    BITS_OP_ASSIGN(|)
    BITS_OP_ASSIGN(^)

#undef BITS_OP_ASSIGN

    friend std::ostream &operator<<(std::ostream &stream,
                                    const _PossiblyUnknownBits &val) {
      if (val.m_unknown_mask == 0) {
        stream << val.m_value;
      } else {
        stream << fmt::format("{} (unknown mask: {})", val.m_value,
                              val.m_unknown_mask);
      }
      return stream;
    }

    template <unsigned msb, unsigned lsb>
    constexpr _PossiblyUnknownBits<msb - lsb + 1, false> extract() const {
      static_assert(msb >= lsb);
      return _PossiblyUnknownBits<msb - lsb + 1, false>{
          m_value >> lsb,
          m_unknown_mask >> lsb};  // masking will happen in the constructor
    }

    template <typename IndexType, typename ValueType>
    constexpr _PossiblyUnknownBits &setBit(const IndexType &idx,
                                           const ValueType &value) {
      StorageType pos_mask = static_cast<StorageType>(1) << idx;
      m_value = (m_value & ~pos_mask) |
                ((static_cast<StorageType>(value) << idx) & pos_mask);
      m_unknown_mask &= ~pos_mask;
      return *this;
    }

    //  private:
    _Bits<N, Signed> m_value;
    _Bits<N, false> m_unknown_mask;
  };

  template <char... Str>
  constexpr _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, false>
  operator""_xb() {
    if constexpr (BitsStr<true, Str..., '\0'>::width <=
                  BitsMaxNativePrecision) {
      return {BitsStr<true, Str..., '\0'>::val,
              BitsStr<true, Str..., '\0'>::unknown_mask};
    } else {
      return mpz_class{BitsStr<true, Str..., '\0'>::str};
    }
  }

  template <TemplateString Str>
  constexpr _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, false>
  operator""_xb() {
    if constexpr (BitsTemplateStr<true, Str>::width <= BitsMaxNativePrecision) {
      return {BitsTemplateStr<true, Str>::val,
              BitsTemplateStr<true, Str>::unknown_mask};
    } else {
      return mpz_class{BitsTemplateStr<true, Str>::str};
    }
  }

  template <char... Str>
  constexpr _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, true>
  operator""_xsb() {
    if constexpr (BitsStr<true, Str..., '\0'>::width <=
                  BitsMaxNativePrecision) {
      return {BitsStr<true, Str..., '\0'>::val,
              BitsStr<true, Str..., '\0'>::unknown_mask};
    } else {
      return mpz_class{BitsStr<true, Str..., '\0'>::str};
    }
  }

  template <TemplateString Str>
  constexpr _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, true>
  operator""_xsb() {
    if constexpr (BitsTemplateStr<true, Str>::width <= BitsMaxNativePrecision) {
      return {BitsTemplateStr<true, Str>::val,
              BitsTemplateStr<true, Str>::unknown_mask};
    } else {
      return mpz_class{BitsTemplateStr<true, Str>::str};
    }
  }

  static_assert((0x0_xb).Width == 1);
  static_assert((0x1_xb).Width == 1);
  static_assert((0_xb).Width == 1);
  static_assert((1_xb).Width == 1);
  static_assert((0x2_xb).Width == 2);
  static_assert((0x7_xb).Width == 3);
  static_assert((0x8_xb).Width == 4);
  static_assert((0xf_xb).Width == 4);
  static_assert((0x1f_xb).Width == 5);
  static_assert((0xffffffffffffffff_xb).Width == 64);

  static_assert((0x1_xb).get() == 1);
  static_assert((0x2_xb).get() == 2);
  static_assert((0x7_xb).get() == 7);
  static_assert((0x8_xb).get() == 8);
  static_assert((0xf_xb).get() == 15);
  static_assert((0x1f_xb).get() == 0x1f);
  static_assert((0xff_xb).get() == 0xff);
  static_assert((0xffffffff_xb).get() == 0xfffffffful);
  static_assert((0xfffffffff_xb).get() == 0xffffffffful);
  static_assert((0xffffffff1_xb).get() == 0xffffffff1ul);
  static_assert((0xfffffffffffffff_xb).get() == 0xffffffffffffffful);
  static_assert((0xffffffffffffffff_xb).get() == 0xfffffffffffffffful);

  static_assert((1_xb).get() == 1);
  static_assert((2_xb).get() == 2);
  static_assert((7_xb).get() == 7);
  static_assert((8_xb).get() == 8);
  static_assert((15_xb).get() == 15);
  static_assert((31_xb).get() == 31);
  static_assert((1152921504606846975_xb).get() == 0xfffffffffffffff);
  static_assert((18446744073709551615_xb).get() == 0xffffffffffffffff);

  static_assert(("0x1x"_xb).Width == 5);
  static_assert(("0x1x"_xb).unknown_mask() == 0xf);

  template <unsigned N>
  using Bits = _Bits<N, false>;

  template <unsigned N>
  using SignedBits = _Bits<N, true>;

  // special values
  static constexpr Bits<65> UNDEFINED_LEGAL = 0x10000000000000000_b;
  static constexpr Bits<66> UNDEFINED_LEGAL_DETERMINISTIC =
      0x20000000000000000_b;

  template <unsigned N>
  using PossiblyUnknownBits = _PossiblyUnknownBits<N, false>;
}  // namespace udb
