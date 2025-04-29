#pragma once

#include <fmt/core.h>
#include <fmt/format.h>
#include <gmpxx.h>

#include <bit>
#include <concepts>
#include <cstdint>
#include <iostream>
#include <limits>
#include <type_traits>

#include "udb/cpp_exceptions.hpp"
#include "udb/defines.hpp"

// Bits classes implement the IDL Bits<N> type.
//
// There are four Bits types in C++:
//
//  * _Bits<N, Signed>: Compile-time known vector length holding a known value
//
//  * _PossiblyUnknownBits<N, Signed>: Compile-time known vector length holding a
//     possibly unknown value
//
//  * _RuntimeBits<MaxN, Signed>: Compile-time unknown vector length, at most MaxN,
//     holding a known value
//
//  * _PossiblyUnknownRuntimeBits<MaxN, Signed>: Compile-time unknown vector length, at most MaxN,
//     holding a possibly unknown value
//
// You can convert:
//
//   - _Bits<N, Signed>                          -> *any
//   - _PossiblyUnknownBits<N, Signed>           -> _PossiblyUnknownRuntimeBits<MaxN, Signed>
//   - _RuntimeBits<MaxN, Signed>                -> _PossiblyUnknownRuntimeBits<MaxN, Signed>
//   - _PossiblyUnknownRuntimeBits<MaxN, Signed> ->  none
//
// The bits classes attempt to hold the smallest native type to hold the value,
// falling back on GMP when it will not fit in any native type. The bits classes
// attempt to drop state (and checks) for unknown values when the value must be
// known; thus the multiple class types. The bits classes handle when the vector
// length isn't known at compile-time (e.g., because the length is a config
// parameter).
//
//                                        Value always known at runtime?
//                                          Yes                No
//                                       ----------------------------
//   Width known at compile time?   Yes  | Bits        |  PossiblyUnknownBits
//                                   No  | RuntimeBits |  PossiblyUnknownRuntimeBits
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

  static_assert(
      constmax<std::numeric_limits<unsigned>::max(), std::numeric_limits<unsigned>::max()>::value ==
      std::numeric_limits<unsigned>::max());

  // N that actually means infinite
  constexpr static unsigned BitsInfinitePrecision = std::numeric_limits<unsigned>::max();

  // max N value where storage is using a native integer type
  // above this, the storage is GMP, and the Bits type can't be constexpr
  constexpr static unsigned BitsMaxNativePrecision = 128;

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
            std::conditional_t<(N > 32), int64_t,
                               std::conditional_t<(N > 16), int32_t,
                                                  std::conditional_t<(N > 8), int16_t, int8_t>>>>>;
  };

  template <std::integral IntType>
  static mpz_class to_gmp(const IntType &val) {
    if constexpr (sizeof(IntType) == 16) {
      if constexpr (std::is_signed_v<IntType>) {
        if (val == std::numeric_limits<__int128>::min()) {
          // can't just negate this, so it's a special case
          return -(1_mpz << 127);
        } else {
          __int128 abs = (val < 0) ? -val : val;
          mpz_class gmp_val = static_cast<uint64_t>(abs >> 64);
          gmp_val <<= 64;
          gmp_val |= static_cast<uint64_t>(abs);
          if (val < 0) {
            gmp_val = -gmp_val;
          }
          return gmp_val;
        }
      } else {
        mpz_class gmp_val = static_cast<uint64_t>(val >> 64);
        gmp_val <<= 64;
        gmp_val |= static_cast<uint64_t>(val);
        return gmp_val;
      }
    } else {
      return val;
    }
  }

  static mpz_class to_gmp(const mpz_class &val) { return val; }

  template <unsigned ToN>
  static typename BitsStorageType<ToN>::type from_gmp(const mpz_class &val) {
    if constexpr (ToN <= 64) {
      if (val < 0) {
        return static_cast<typename BitsStorageType<ToN>::type>(0) -
               static_cast<mpz_class>(abs(val)).get_ui();
      } else {
        return val.get_ui();
      }
    } else if constexpr (ToN <= BitsMaxNativePrecision) {
      if (val < 0) {
        typename BitsStorageType<ToN>::type result =
            static_cast<mpz_class>(abs(val) >> 64).get_ui();
        result <<= 64;
        result |= static_cast<mpz_class>(abs(val)).get_ui();
        return 0 - result;
      } else {
        typename BitsStorageType<ToN>::type result =
            static_cast<mpz_class>(abs(val) >> 64).get_ui();
        result <<= 64;
        result |= static_cast<mpz_class>(abs(val)).get_ui();
        return result;
      }
    } else {
      // this is gmp
      return val;
    }
  }

  template <unsigned ToN>
  static std::conditional_t<(ToN > BitsMaxNativePrecision), mpz_class &&,
                            typename BitsStorageType<ToN>::type>
  from_gmp(mpz_class &&val) {
    if constexpr (ToN <= 64) {
      if (val < 0) {
        return static_cast<typename BitsStorageType<ToN>::type>(0) -
               static_cast<mpz_class>(abs(val)).get_ui();
      } else {
        return val.get_ui();
      }
    } else if constexpr (ToN <= BitsMaxNativePrecision) {
      if (val < 0) {
        typename BitsStorageType<ToN>::type result =
            static_cast<mpz_class>(abs(val) >> 64).get_ui();
        result <<= 64;
        result |= static_cast<mpz_class>(abs(val)).get_ui();
        return 0 - result;
      } else {
        typename BitsStorageType<ToN>::type result =
            static_cast<mpz_class>(abs(val) >> 64).get_ui();
        result <<= 64;
        result |= static_cast<mpz_class>(abs(val)).get_ui();
        return result;
      }
    } else {
      // this is gmp
      return std::move(val);
    }
  }

  template <template <unsigned, bool> class BitsType, unsigned N, bool Signed>
  static mpz_class to_gmp(const BitsType<N, Signed> &val) {
    if constexpr (N > BitsMaxNativePrecision) {
      return val.m_val;
    } else {
      return to_gmp(val.m_val);
    }
  }

#define GMP_OP(op)                                                                                \
  mpz_class operator op(const mpz_class &lhs, const __int128 &rhs) { return lhs op to_gmp(rhs); } \
  mpz_class operator op(const mpz_class &lhs, const unsigned __int128 &rhs) {                     \
    return lhs op to_gmp(rhs);                                                                    \
  }

  GMP_OP(+)
  GMP_OP(-)
  GMP_OP(*)
  GMP_OP(/)
  GMP_OP(%)

#undef GMP_OP

#define GMP_BOOL_OP(op)                                                                      \
  bool operator op(const mpz_class &lhs, const __int128 &rhs) { return lhs op to_gmp(rhs); } \
  bool operator op(const mpz_class &lhs, const unsigned __int128 &rhs) {                     \
    return lhs op to_gmp(rhs);                                                               \
  }

  GMP_BOOL_OP(==)
  GMP_BOOL_OP(!=)
  GMP_BOOL_OP(<)
  GMP_BOOL_OP(<=)
  GMP_BOOL_OP(>)
  GMP_BOOL_OP(>=)

#undef GMP_BOOL_OP

  template <unsigned MaxN, bool Signed>
  class _RuntimeBits;

  template <unsigned N, bool Signed>
  class _PossiblyUnknownBits;

  template <unsigned MaxN, bool Signed>
  class _PossiblyUnknownRuntimeBits;

  // saturating add
  template <unsigned A, unsigned B>
  struct addsat {
    static constexpr unsigned value =
        (((A + B) < A) || ((A + B) < B)) ? std::numeric_limits<unsigned>::max() : A + B;
  };
  template <unsigned A, unsigned B>
  static constexpr unsigned addsat_v = addsat<A, B>::value;

  // common interface for all Bits classes
  template <class T>
  concept BitsType = requires(T a) {
    { T::IsABits == true };
    { std::same_as<decltype(T::RuntimeWidth), bool> };
    { std::same_as<decltype(T::PossiblyUnknown), bool> };
    { std::same_as<decltype(T::IsSigned), bool> };
    { a.width() } -> std::same_as<unsigned>;
    { std::remove_cvref_t<decltype(a.value())>::IsABits == true };
    { std::remove_cvref_t<decltype(a.value())>::PossiblyUnknown == false };
    { std::same_as<std::remove_cvref_t<decltype(a.unknown_mask())>, typename T::MaskType> };
  };

  template <class T>
  concept RuntimeBitsType = requires(T a) {
    requires BitsType<T>;
    T::RuntimeWidth == true;
  };

  template <class T>
  concept StaticBitsType = requires(T a) {
    requires BitsType<T>;
    T::RuntimeWidth == false;
  };

  template <class T>
  concept PossiblyUnknownBitsType = requires(T a) {
    requires BitsType<T>;
    T::PossiblyUnknown == true;
  };

  template <class T>
  concept KnownBitsType = requires(T a) {
    requires BitsType<T>;
    T::PossiblyUnknown == false;
  };

  template <class T>
  concept SignedBitsType = requires(T a) {
    requires BitsType<T>;
    T::IsSigned == true;
  };

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
    constexpr static bool RuntimeWidth = false;
    constexpr static bool PossiblyUnknown = false;
    constexpr static bool IsSigned = Signed;

    using MaskType = _Bits<N, false>;

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
        // gmp, but not infinite. always mask this
        return true;
      } else if constexpr (_N == (sizeof(_StorageType) * 8)) {
        // we fit exactly in our native storage
        return false;
      } else {
        // using native storage, but there are unused bits
        return true;
      }
    }

    constexpr const _Bits &value() const { return *this; }
    template <unsigned _N = N>
      requires(N <= MaxNativePrecision)
    consteval static _Bits<N, false> unknown_mask() {
      return _Bits<N, false>{0};
    }

    template <unsigned _N = N>
      requires(N > MaxNativePrecision)
    static _Bits<N, false> unknown_mask() {
      return _Bits<N, false>{0};
    }

   public:
    // mask of all ones for the Bits type
    template <unsigned _N = N>
      requires(N <= MaxNativePrecision)
    static consteval StorageType mask() {
      if constexpr (std::integral<StorageType> && (N == (sizeof(StorageType) * 8))) {
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
    static constexpr SignedStorageType cast_to_signed(const StorageType &unsigned_value) {
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
          // the number is negative
          // The two's compliment value is 2^N - value
          v = -((StorageType{1} << N) - v);
        }
        return v;
      }
    }

    // return a signed version of self
    constexpr SignedStorageType cast_to_signed() const { return cast_to_signed(m_val); }

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

    constexpr StorageType sign_extend() const { return sign_extend(m_val); }

    static constexpr std::conditional_t<needs_mask(), StorageType, const StorageType &> apply_mask(
        const StorageType &value) {
      if constexpr (needs_mask()) {
        return value & mask();
      } else {
        return value;
      }
    }

    constexpr void apply_mask() { m_val = apply_mask(m_val); }

    static _Bits from_string(const std::string &str) {
      if constexpr (std::is_same_v<StorageType, mpz_class>) {
        mpz_class gmp_int(str.c_str());
        return _Bits{gmp_int};
      } else if constexpr (N <= 64 && N > 32) {
        static_assert(sizeof(long long) == sizeof(uint64_t), "Unexpected long long type");
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

    // from a bits of same width and different sign
    constexpr _Bits(const _Bits<N, !Signed> &other) : m_val(other.m_val) {}
    constexpr _Bits(_Bits<N, !Signed> &&other) : m_val(std::move(other.m_val)) {}

    // from a KNOWN bits of different width and sign
    template <template <unsigned, bool> class OtherBitsType, unsigned OtherN, bool OtherSigned>
      requires(KnownBitsType<OtherBitsType<OtherN, OtherSigned>>)
    constexpr _Bits(const OtherBitsType<OtherN, OtherSigned> &other) {
      if constexpr (OtherN > MaxNativePrecision) {
        m_val = from_gmp<N>(other.get());
      } else if constexpr (N > MaxNativePrecision) {
        m_val = to_gmp(other.get());
      } else {
        m_val = other.get();
      }
      apply_mask();
    }

    // from a KNOWN bits of different width and sign
    template <template <unsigned, bool> class OtherBitsType, unsigned OtherN, bool OtherSigned>
      requires(KnownBitsType<OtherBitsType<OtherN, OtherSigned>>)
    constexpr _Bits(OtherBitsType<OtherN, OtherSigned> &&other) {
      if constexpr (OtherN == InfinitePrecision) {
        m_val = from_gmp<N>(std::move(other.m_val));
      } else if constexpr (OtherN > MaxNativePrecision) {
        if constexpr (OtherSigned) {
          m_val = from_gmp<N>(other.get());
        } else {
          m_val = from_gmp<N>(std::move(other.m_val));
        }
      } else if constexpr (N > MaxNativePrecision) {
        m_val = to_gmp(other.get());
      } else {
        m_val = other.get();
      }
      apply_mask();
    }

    // from a native integer (excluding int128 into a gmp, which needs a special
    // func)
    template <std::integral IntType>
      requires((sizeof(IntType) != 16) || (N <= MaxNativePrecision))
    explicit constexpr _Bits(const IntType &val) : m_val(val) {
      apply_mask();
    }

    // from in128 to gmp
    template <std::integral IntType>
      requires((sizeof(IntType) == 16) && (N > MaxNativePrecision))
    explicit constexpr _Bits(const IntType &val) : m_val(to_gmp(val)) {
      apply_mask();
    }

    // from gmp
    explicit _Bits(const mpz_class &val) {
      m_val = from_gmp<N>(val);
      apply_mask();
    }
    explicit _Bits(const mpz_class &&val) {
      m_val = from_gmp<N>(val);
      apply_mask();
    }

    constexpr ~_Bits() noexcept = default;

    // get the value in the underlying storage type
    constexpr std::conditional_t<Signed, SignedStorageType, const StorageType &> get() const {
      if constexpr (Signed) {
        return cast_to_signed();
      } else {
        return m_val;
      }
    }

    // assignment
    _Bits &operator=(const _Bits &o) = default;
    _Bits &operator=(_Bits &&o) noexcept = default;

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    _Bits &operator=(const RhsBitsType<RhsN, RhsSigned> &rhs) {
      if constexpr (RhsN > MaxNativePrecision) {
        if constexpr (N > MaxNativePrecision) {
          m_val = rhs.get();
        } else if constexpr (sizeof(StorageType) == 16) {
          mpz_class rhs_val = rhs.get();
          m_val = static_cast<mpz_class>(rhs_val >> 64).get_ui();
          m_val <<= 64;
          m_val |= rhs_val.get_ui();
        } else {
          m_val = rhs.get().get_ui();
        }
      } else {
        m_val = rhs.get();
      }
      apply_mask();

      return *this;
    }

    // negate operator
    constexpr _Bits operator-() const {
      _Bits negated_value{*this};
      negated_value.m_val = -negated_value.m_val;
      negated_value.apply_mask();
      return negated_value;
    }

    // invert operator
    constexpr _Bits operator~() const & {
      _Bits inverted_val{*this};
      inverted_val.m_val = ~inverted_val.m_val;
      inverted_val.apply_mask();
      return inverted_val;
    }

#define BITS_COMPARISON_OPERATOR(op)                                                     \
  constexpr bool operator op(const _Bits &o) const noexcept { return get() op o.get(); } \
                                                                                         \
  template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>  \
    requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)                                     \
  constexpr bool operator op(const RhsBitsType<RhsN, RhsSigned> &rhs) const noexcept {   \
    return get() op rhs.get();                                                           \
  }

    BITS_COMPARISON_OPERATOR(==)
    BITS_COMPARISON_OPERATOR(!=)
    BITS_COMPARISON_OPERATOR(<)
    BITS_COMPARISON_OPERATOR(>)
    BITS_COMPARISON_OPERATOR(<=)
    BITS_COMPARISON_OPERATOR(>=)

#undef BITS_COMPARISON_OPERATOR

    //
    // bitwise operators, which are only defined for known bits types
    //

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    using ArithmeticReturnType =
        typename std::conditional_t<RhsBitsType<RhsN, RhsSigned>::RuntimeWidth,
                                    _RuntimeBits<constmax<N, RhsN>::value, Signed && RhsSigned>,
                                    _Bits<constmax_v<N, RhsN>, Signed && RhsSigned>>;

#define BITS_ARITHMETIC_OPERATOR(op)                                                               \
  constexpr _Bits operator op(const _Bits &o) const { return _Bits{get() op o.get()}; }            \
                                                                                                   \
  template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>            \
    requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)                                          \
  constexpr ArithmeticReturnType<RhsBitsType, RhsN, RhsSigned> operator op(                        \
      const RhsBitsType<RhsN, RhsSigned> &rhs) const {                                             \
    if constexpr (!RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {                                   \
      return ArithmeticReturnType<RhsBitsType, RhsN, RhsSigned>{                                   \
          _Bits<constmax<N, RhsN>::value, Signed>{*this}                                           \
              .get() op RhsBitsType<constmax_v<N, RhsN>, RhsSigned>{rhs}                           \
              .get()};                                                                             \
    } else {                                                                                       \
      return {                                                                                     \
          _Bits<constmax<N, RhsN>::value, Signed>{*this}                                           \
              .get() op RhsBitsType<constmax_v<N, RhsN>, RhsSigned>{rhs, std::max(N, rhs.width())} \
              .get(),                                                                              \
          std::max(N, rhs.width())};                                                               \
    }                                                                                              \
  }

    BITS_ARITHMETIC_OPERATOR(+)
    BITS_ARITHMETIC_OPERATOR(-)
    BITS_ARITHMETIC_OPERATOR(*)
    BITS_ARITHMETIC_OPERATOR(/)
    BITS_ARITHMETIC_OPERATOR(%)

#undef BITS_ARITHMETIC_OPERATOR

    //
    // bitwise operators, for which the return type may be unknown if the rhs is
    // unknown
    //

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    using BitwiseReturnType = typename std::conditional_t<
        RhsBitsType<RhsN, RhsSigned>::RuntimeWidth,

        std::conditional_t<RhsBitsType<RhsN, RhsSigned>::PossiblyUnknown,
                           _PossiblyUnknownRuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>,
                           _RuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>>,

        std::conditional_t<RhsBitsType<RhsN, RhsSigned>::PossiblyUnknown,
                           _PossiblyUnknownBits<constmax_v<N, RhsN>, Signed && RhsSigned>,
                           _Bits<constmax_v<N, RhsN>, Signed && RhsSigned>>>;

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator&(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUnknown) {
        _Bits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        // any bit that is 0 in lhs is known in the result, regardless of its
        // status in rhs
        typename _Bits<constmax_v<N, RhsN>, false>::StorageType result_unknown_mask =
            rhs.unknown_mask().get() & lhs.get();

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _PossiblyUnknownBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() & rhs.get_ignore_unknown(), result_unknown_mask};
        } else {
          return _PossiblyUnknownRuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() & rhs.get(), std::max(N, rhs.width()), result_unknown_mask};
        }
      } else {
        // both rhs and lhs are known
        _RuntimeBits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _RuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() & rhs.get(),
                                                                        std::max(N, rhs.width())};
        } else {
          return _Bits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() & rhs.get()};
        }
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator|(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUnknown) {
        _Bits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        // any bit that is 1 in lhs is known in the result, regardless of its
        // status in rhs
        typename _Bits<constmax_v<N, RhsN>, false>::StorageType result_unknown_mask =
            rhs.unknown_mask().get() & ~(lhs.get());

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _PossiblyUnknownBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() | rhs.get_ignore_unknown(), result_unknown_mask};
        } else {
          return _PossiblyUnknownRuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() | rhs.get(), std::max(N, rhs.width()), result_unknown_mask};
        }
      } else {
        // both rhs and lhs are known
        _RuntimeBits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _RuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() | rhs.get(),
                                                                        std::max(N, rhs.width())};
        } else {
          return _Bits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() | rhs.get()};
        }
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator^(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUknown) {
        _Bits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _PossiblyUnknownBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() ^ rhs.get_ignore_unknown(), rhs.unknown_mask()};
        } else {
          return _PossiblyUnknownRuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{
              lhs.get() ^ rhs.get(), std::max(N, rhs.width()), rhs.unknown_mask()};
        }
      } else {
        // both rhs and lhs are known
        _RuntimeBits<constmax_v<N, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<N, RhsN>, RhsSigned> rhs{_rhs};

        if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
          return _RuntimeBits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() ^ rhs.get(),
                                                                        std::max(N, rhs.width())};
        } else {
          return _Bits<constmax_v<N, RhsN>, Signed && RhsSigned>{lhs.get() ^ rhs.get()};
        }
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    using WideningAddReturnType =
        std::conditional_t<RhsBitsType<RhsN, RhsSigned>::RuntimeWidth,
                           _RuntimeBits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>,
                           _Bits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>>;

    // widening ops
    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    constexpr WideningAddReturnType<RhsBitsType, RhsN, RhsSigned> widening_add(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      // have to widen ahead of the computation to make sure we don't lose bits
      _Bits<constmax_v<N, RhsN> + 1, Signed> lhs{*this};

      if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
        const unsigned result_width =
            std::clamp(std::max(N, _rhs.width()) + 1, 0, std::numeric_limits<unsigned>::max());
        RhsBitsType<addsat_v<constmax_v<N, RhsN>, 1>, RhsSigned> rhs{_rhs.get(), result_width};

        return _RuntimeBits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>{
            lhs.get() + rhs.get(), result_width};
      } else {
        RhsBitsType<addsat_v<constmax_v<N, RhsN>, 1>, RhsSigned> rhs{_rhs.get()};
        return _Bits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>{lhs.get() + rhs.get()};
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    constexpr WideningAddReturnType<RhsBitsType, RhsN, RhsSigned> widening_sub(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      // have to widen ahead of the computation to make sure we don't lose bits
      _Bits<constmax_v<N, RhsN> + 1, Signed> lhs{*this};

      if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
        const unsigned result_width =
            std::clamp(std::max(N, _rhs.width()) + 1, 0, std::numeric_limits<unsigned>::max());

        RhsBitsType<addsat_v<constmax_v<N, RhsN>, 1>, RhsSigned> rhs{_rhs.get(), result_width};
        return _RuntimeBits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>{
            lhs.get() - rhs.get(), result_width};
      } else {
        RhsBitsType<addsat_v<constmax_v<N, RhsN>, 1>, RhsSigned> rhs{_rhs.get()};
        return _Bits<addsat_v<constmax_v<N, RhsN>, 1>, Signed && RhsSigned>{lhs.get() - rhs.get()};
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    using WideningMulReturnType =
        std::conditional_t<RhsBitsType<RhsN, RhsSigned>::RuntimeWidth,
                           _RuntimeBits<addsat_v<N, RhsN>, Signed && RhsSigned>,
                           _Bits<addsat_v<N, RhsN>, Signed && RhsSigned>>;

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    constexpr WideningMulReturnType<RhsBitsType, RhsN, RhsSigned> widening_mul(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      _Bits<addsat_v<N, RhsN>, Signed> lhs{*this};

      if constexpr (RhsBitsType<RhsN, RhsSigned>::RuntimeWidth) {
        const unsigned result_width =
            std::clamp(N + _rhs.width(), 0, std::numeric_limits<unsigned>::max());
        RhsBitsType<addsat_v<N, RhsN>, RhsSigned> rhs{_rhs.get(), result_width};

        return _RuntimeBits<addsat_v<N, RhsN>, Signed && RhsSigned>{lhs * rhs, result_width};
      } else {
        RhsBitsType<addsat_v<N, RhsN>, RhsSigned> rhs{_rhs.get()};

        return _Bits<addsat_v<N, RhsN>, Signed && RhsSigned>{lhs * rhs};
      }
    }

    constexpr _Bits operator<<(const _Bits &shamt) const { return _Bits{m_val << shamt.get()}; }

    template <template <unsigned, bool> class ShiftBitsType, unsigned ShiftN>
      requires(BitsType<ShiftBitsType<ShiftN, false>>)
    constexpr _Bits operator<<(const ShiftBitsType<ShiftN, false> &shamt) const {
      return _Bits{m_val << shamt.get()};
    }

    // widening left shift when the shift amount is known at compile time
    template <template <unsigned, bool> class ShiftBitsType, unsigned ShiftN,
              ShiftBitsType<ShiftN, false> SHAMT>
      requires(KnownBitsType<ShiftBitsType<ShiftN, false>>)
    constexpr _Bits<addsat_v<N, SHAMT>, Signed> widening_sll() const {
      using ReturnType = _Bits<addsat_v<N, SHAMT.get()>, Signed>;
      if constexpr (N >= MaxNativePrecision) {
        return {ReturnType{get()}.get() << SHAMT.get()};
      } else {
        return {ReturnType{get()}.get() << SHAMT.get()};
      }
    }

    // widening left shift when the shift amount is not known at compile time
    template <template <unsigned, bool> class ShiftBitsType, unsigned ShiftN>
      requires(BitsType<ShiftBitsType<ShiftN, false>>)
    constexpr _Bits<InfinitePrecision, Signed> widening_sll(
        const ShiftBitsType<ShiftN, false> &shamt) const {
      using ReturnType = _Bits<InfinitePrecision, Signed>;
      return _Bits<InfinitePrecision, Signed>{ReturnType{get()}.get() << shamt.get()};
    }

    constexpr _Bits operator>>(const _Bits &shamt) const { return {m_val >> shamt.get()}; }

    template <template <unsigned, bool> class ShiftBitsType, unsigned ShiftN>
      requires(BitsType<ShiftBitsType<ShiftN, false>>)
    constexpr _Bits operator>>(const ShiftBitsType<ShiftN, false> &shamt) const {
      // do not use get() here; that will make it an sra
      return _Bits{m_val >> shamt.get()};
    }

    constexpr _Bits sra(const _Bits &shamt) const { return {cast_to_signed() >> shamt.get()}; }

    template <template <unsigned, bool> class ShiftBitsType, unsigned ShiftN>
      requires(BitsType<ShiftBitsType<ShiftN, false>>)
    constexpr _Bits sra(const ShiftBitsType<ShiftN, false> &shamt) const {
      return _Bits{cast_to_signed() >> shamt.get()};
    }

    // pre-increment. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits &operator++() {
      m_val += 1;
      apply_mask();
      return *this;
    }

    // post-increment
    _Bits operator++(int) {
      _Bits tmp{m_val};
      m_val += 1;
      apply_mask();
      return tmp;
    }

    // pre-decrement. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits &operator--() {
      m_val -= 1;
      apply_mask();
      return *this;
    }

    // post-increment
    _Bits operator--(int) {
      _Bits tmp{m_val};
      m_val -= 1;
      apply_mask();
      return tmp;
    }

    friend std::ostream &operator<<(std::ostream &stream, const _Bits &val) {
      if constexpr (std::same_as<StorageType, unsigned __int128> ||
                    std::same_as<StorageType, __int128>) {
        stream << fmt::format("{:x}", val.m_val);
      } else {
        stream << val.m_val;
      }
      return stream;
    }

    template <unsigned msb, unsigned lsb>
    constexpr _Bits<msb - lsb + 1, false> extract() const {
      static_assert(msb >= lsb);
      return _Bits<msb - lsb + 1, false>{m_val >> lsb};  // masking will happen in the constructor
    }

    template <typename IndexType, typename ValueType>
    constexpr _Bits &setBit(const IndexType &idx, const ValueType &value) {
      StorageType pos_mask = static_cast<StorageType>(1) << idx;
      m_val = (m_val & ~pos_mask) | ((static_cast<_Bits>(value) << idx) & pos_mask);
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

  static_assert(BitsType<_Bits<1, false>>, "_Bits is not a BitsType");

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
        } else if (strncmp(str, "0b", 2) == 0) {
          base = 2;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 2) {
        // the number of bits is the number of characters after the first x or 1
        while (*ptr != '1' && *ptr != 'x' && *ptr != 'X') {
          ptr++;
          if (*ptr != '1' && *ptr != '0' && *ptr != 'x' && *ptr != 'X') {
            // bad character
            return 0;
          }
        }
        width = strlen(ptr);
      } else if (base == 10) {
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
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'A' + (uint32_t)10);
        } else if (*ptr >= 'a' && *ptr <= 'f') {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'a' + (uint32_t)10);
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
        } else if (strncmp(str, "0b", 2) == 0) {
          base = 2;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 2) {
        unsigned __int128 pow = 1;
        for (int i = len - 1; i >= 0; i--) {
          if (ptr[i] == '1') {
            val += pow;
          }
          pow *= 2;
        }
      } else if (base == 10) {
        // we only support base-10 literals up to 64 bits. (otherwise, it's hard
        // to know bitwidth at compile time)
        unsigned __int128 pow = 1;
        for (int i = len - 1; i >= 0; i--) {
          val += ((unsigned __int128)(ptr[i] - '0')) * pow;
          pow *= 10;
        }
      } else if (base == 16) {
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
        } else if (strncmp(str, "0b", 2) == 0) {
          base = 2;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 2) {
        unsigned __int128 shamt = 0;
        for (int i = len - 1; i >= 0; i--) {
          if (ptr[i] == 'x' || ptr[i] == 'X') {
            mask |= static_cast<__int128>(1) << shamt;
          }
          shamt += 1;
        }
      } else if (base == 10) {
        return 0;  // there are no unknowns in a base-10 literal
      } else if (base == 16) {
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

    static constexpr unsigned width = BitsStrHelpers::get_width<AllowUnknown>(str);
    static_assert(width <= 128,
                  "Cannot create bits literal of width >= 128 (use \"\"_mpz instead)");
    static constexpr _Bits<128, false> val{BitsStrHelpers::get_val(str)};
    static constexpr _Bits<128, false> unknown_mask{BitsStrHelpers::get_unknown_mask(str)};
  };

  template <bool AllowUnknown, TemplateString Str>
  struct BitsTemplateStr {
    static constexpr unsigned width = BitsStrHelpers::get_width<AllowUnknown>(Str.cstr_value);
    static_assert(width <= 128,
                  "Cannot create bits literal of width >= 128 (use \"\"_mpz instead)");
    static constexpr _Bits<128, false> val{BitsStrHelpers::get_val(Str.cstr_value)};
    static constexpr _Bits<128, false> unknown_mask{
        BitsStrHelpers::get_unknown_mask(Str.cstr_value)};
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
                  _Bits<BitsStr<false, Str..., '\0'>::width, false>::MaxNativePrecision) {
      return BitsStr<false, Str..., '\0'>::val;
    } else {
      return mpz_class{BitsStr<false, Str..., '\0'>::str};
    }
  }

  // signed bits
  template <char... Str>
  constexpr _Bits<BitsStr<false, Str..., '\0'>::width + 1, true> operator""_sb() {
    if constexpr ((BitsStr<false, Str..., '\0'>::width + 1) <=
                  _Bits<(BitsStr<false, Str..., '\0'>::width + 1), false>::MaxNativePrecision) {
      return BitsStr<false, Str..., '\0'>::val;
    } else {
      return mpz_class{BitsStr<false, Str..., '\0'>::str};
    }
  }

  static_assert((0x0_b).width() == 1);
  static_assert((0x1_b).width() == 1);
  static_assert((0_b).width() == 1);
  static_assert((1_b).width() == 1);
  static_assert((0x2_b).width() == 2);
  static_assert((0x7_b).width() == 3);
  static_assert((0x8_b).width() == 4);
  static_assert((0xf_b).width() == 4);
  static_assert((0x1f_b).width() == 5);
  static_assert((0xffffffffffffffff_b).width() == 64);

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
    return fmt::formatter<typename udb::_Bits<N, Signed>::StorageType>::format(value.get(), ctx);
  }
};

template <unsigned N, bool Signed>
  requires(N > udb::BitsMaxNativePrecision)
struct fmt::formatter<udb::_Bits<N, Signed>> {
 private:
  fmt::detail::dynamic_format_specs<char> specs_;

 public:
  constexpr auto parse(fmt::format_parse_context &ctx) -> decltype(ctx.begin()) {
    auto end = parse_format_specs(ctx.begin(), ctx.end(), specs_, ctx, fmt::detail::type::int_type);
    return end;
  }

  template <class FormatContext>
  auto format(const udb::_Bits<N, Signed> &c, FormatContext &ctx) -> decltype(ctx.out()) {
    fmt::detail::handle_dynamic_spec<fmt::detail::precision_checker>(specs_.width, specs_.width_ref,
                                                                     ctx);
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
    size_t strwidth = std::max((size_t)specs_.width, mpz_sizeinbase(c.get().get_mpz_t(), base));
    char *str = new char[strwidth + 100];
    gmp_snprintf(str, strwidth + 100, gmp_fmt_string.c_str(), c.get().get_mpz_t());
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
    static constexpr std::float_round_style round_style = std::round_toward_zero;
    static constexpr bool is_iec559 = false;
    static constexpr bool is_bounded = (N != udb::_Bits<N, Signed>::InfinitePrecision);
    static constexpr int digits = Signed ? N - 1 : N;
    static constexpr int digits10 =
        N < udb::_Bits<N, Signed>::InfinitePrecision ? digits * std::log10(2) : 0;
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
        return -typename udb::_Bits<N, Signed>{typename udb::_Bits<N, Signed>::SignedStorageType{1}
                                               << (N - 1)};
      } else {
        return udb::_Bits<N, Signed>(0);
      }
    }
    static consteval udb::_Bits<N, Signed> lowest() noexcept { return min(); }
    static consteval udb::_Bits<N, Signed> max() noexcept {
      if constexpr (N <= udb::_Bits<N, Signed>::MaxNativePrecision) {
        if (N == sizeof(typename udb::_Bits<N, Signed>::StorageType) * 8) {
          if (Signed) {
            return udb::_Bits<N, Signed>{
                std::numeric_limits<typename udb::_Bits<N, Signed>::SignedStorageType>::max()};
          } else {
            return udb::_Bits<N, Signed>{
                std::numeric_limits<typename udb::_Bits<N, Signed>::StorageType>::max()};
          }
        } else {
          if (Signed) {
            return udb::_Bits<N, Signed>{
                (typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) - 1};
          } else {
            return udb::_Bits<N, Signed>{(typename udb::_Bits<N, Signed>::StorageType{1} << (N)) -
                                         1};
          }
        }
      } else {
        if (Signed) {
          return udb::_Bits<N, Signed>{(typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) -
                                       1};
        } else {
          return udb::_Bits<N, Signed>{(typename udb::_Bits<N, Signed>::StorageType{1} << N) - 1};
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

static_assert(std::numeric_limits<udb::_Bits<8, false>>::min().get() == 0);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::min().get() == -128);
static_assert(std::numeric_limits<udb::_Bits<8, false>>::max().get() == 255);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::max().get() == 127);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::min().get() == 0);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::min().get() == -256);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::max().get() == 511);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::max().get() == 255);

namespace udb {
  // Bits where the width is only known at runtime (usually because the width is
  // parameter-dependent)
  template <unsigned MaxN, bool Signed>
  class _RuntimeBits {
    // befriend all bits
    template <unsigned, bool>
    friend class _RuntimeBits;

    template <unsigned, bool>
    friend class _Bits;

    template <unsigned, bool>
    friend class _PossiblyUnknownBits;

    template <unsigned, bool>
    friend class _PossiblyUnknownRuntimeBits;

    using StorageType = BitsStorageType<MaxN>::type;
    using SignedStorageType = _Bits<MaxN, Signed>::SignedStorageType;

    static constexpr unsigned MaxNativePrecision = BitsMaxNativePrecision;
    static constexpr unsigned InfinitePrecision = BitsInfinitePrecision;

    // returns true if this Bits width requires storage masking (i.e., N != #
    // bits in the underlying type)
    bool needs_mask() const {
      if constexpr (MaxN > MaxNativePrecision) {
        if (m_width == InfinitePrecision) {
          // special case: we store infinite numbers with their sign
          return false;
        } else {
          // gmp storage, without upper bound, so everything needs masked
          return true;
        }
      } else {
        if (m_width == (sizeof(StorageType) * 8)) {
          // we fit exactly in our native storage
          return false;
        } else {
          // using native storage, but there are unused bits
          return true;
        }
      }
    }

    StorageType mask() const {
      if constexpr (MaxN == BitsInfinitePrecision) {
        udb_assert(m_width != BitsInfinitePrecision,
                   "Can't produce a mask of a inifitely wide number");
      }
      if constexpr (MaxN <= BitsMaxNativePrecision) {
        if (m_width == (sizeof(StorageType) * 8)) {
          return ~StorageType{0};
        } else {
          return (StorageType{1} << m_width) - 1;
        }
      } else {
        return (StorageType{1} << m_width) - 1;
      }
    }

    void apply_mask() {
      if (needs_mask()) {
        m_val = m_val & mask();
      }
    }

    constexpr StorageType sign_extend() const {
      if (needs_mask()) {
        udb_assert(m_width != BitsInfinitePrecision,
                   "Can't signe extend an infinite precision number");

        if ((m_val & (StorageType{1} << (m_width - 1))) != 0) {
          // negative, fill with ones
          return m_val | ~mask();
        } else {
          // positive, no extension needed
          return m_val;
        }
      } else {
        return m_val;
      }
    }

    template <unsigned N = MaxN>
      requires(N <= BitsMaxNativePrecision)
    constexpr SignedStorageType cast_to_signed() const {
      if (m_width == (sizeof(StorageType) * 8)) {
        // exactly fits in a native type, so just cast it
        return static_cast<SignedStorageType>(m_val);
      } else {
        // we have a native type, but some bits are unsed. need to sign extend
        // the storage to the native width
        return static_cast<SignedStorageType>(sign_extend());
      }
    }

    // return a signed version of self
    template <unsigned N = MaxN>
      requires(N > BitsMaxNativePrecision)
    SignedStorageType cast_to_signed() const {
      if constexpr (MaxN == BitsInfinitePrecision) {
        // inifinite is never masked
        if (m_width == BitsInfinitePrecision) {
          return m_val;
        }
      }

      auto v = m_val;
      if (((v >> (m_width - 1)) & 1) == 1) {
        // the number is negative
        // The two's compliment value is 2^N - value
        v = -((StorageType{1} << m_width) - v);
      }
      return v;
    }

   public:
    // used for template concept resolution
    constexpr static bool IsABits = true;
    constexpr static bool RuntimeWidth = true;
    constexpr static bool PossiblyUnknown = false;
    constexpr static bool IsSigned = Signed;

    using MaskType = _Bits<MaxN, false>;

    constexpr _Bits<MaxN, Signed> value() const { return _Bits<MaxN, Signed>{m_val}; }
    consteval static _Bits<MaxN, false> unknown_mask() { return _Bits<MaxN, false>(0); }
    unsigned width() const { return m_width; }

    // must have a width to construct a RuntimeBits
    _RuntimeBits() = delete;
    _RuntimeBits(const _RuntimeBits &) = default;
    _RuntimeBits(_RuntimeBits &&) = default;
    _RuntimeBits(unsigned width) : m_width() {}

    template <template <unsigned, bool> class OtherBitsType, unsigned OtherN, bool OtherSigned>
      requires(KnownBitsType<OtherBitsType<OtherN, OtherSigned>>)
    _RuntimeBits(const OtherBitsType<OtherN, OtherSigned> &initial_value)
        : m_width(initial_value.width()) {
      if constexpr (OtherN > MaxNativePrecision) {
        m_val = from_gmp<MaxN>(initial_value.get());
      } else if constexpr (MaxN > MaxNativePrecision) {
        m_val = to_gmp(initial_value.get());
      } else {
        m_val = initial_value.get();
      }

      if (m_width > MaxN) {
        throw std::runtime_error("width is larger than MaxN");
      }

      apply_mask();

      if constexpr (MaxN == InfinitePrecision && !Signed) {
        if ((m_width == InfinitePrecision) && (m_val < 0)) {
          throw std::runtime_error("Cannot represent a negative number in infinite precision");
        }
      }
    }

    template <template <unsigned, bool> class ValueBitsType, unsigned ValueN, bool ValueSigned,
              template <unsigned, bool> class WidthBitsType, unsigned WidthN>
      requires(KnownBitsType<ValueBitsType<ValueN, ValueSigned>> &&
               KnownBitsType<WidthBitsType<WidthN, false>>)
    _RuntimeBits(const ValueBitsType<ValueN, ValueSigned> &initial_value,
                 const WidthBitsType<WidthN, false> &width)
        : m_width((WidthN > MaxNativePrecision) ? from_gmp<32>(width.get()) : width.get()) {
      if constexpr (ValueN > MaxNativePrecision) {
        m_val = from_gmp<MaxN>(initial_value.get());
      } else if constexpr (MaxN > MaxNativePrecision) {
        m_val = to_gmp(initial_value.get());
      } else {
        m_val = initial_value.get();
      }

      if (m_width > MaxN) {
        throw std::runtime_error("width is larger than MaxN");
      }

      apply_mask();

      if constexpr (MaxN == InfinitePrecision && !Signed) {
        if ((m_width == InfinitePrecision) && (m_val < 0)) {
          throw std::runtime_error("Cannot represent a negative number in infinite precision");
        }
      }
    }

    template <template <unsigned, bool> class ValueBitsType, unsigned ValueN, bool ValueSigned>
      requires(KnownBitsType<ValueBitsType<ValueN, ValueSigned>>)
    _RuntimeBits(const ValueBitsType<ValueN, ValueSigned> &initial_value, const unsigned &width)
        : m_width(width) {
      if constexpr (ValueN > MaxNativePrecision) {
        m_val = from_gmp<MaxN>(initial_value.get());
      } else if constexpr (MaxN > MaxNativePrecision) {
        m_val = to_gmp(initial_value.get());
      } else {
        m_val = initial_value.get();
      }

      if (m_width > MaxN) {
        throw std::runtime_error("width is larger than MaxN");
      }

      apply_mask();

      if constexpr (MaxN == InfinitePrecision && !Signed) {
        if ((m_width == InfinitePrecision) && (m_val < 0)) {
          throw std::runtime_error("Cannot represent a negative number in infinite precision");
        }
      }
    }

   private:
    // construct from StorageType; only for internal use
    _RuntimeBits(const StorageType &val, unsigned width) : m_val(val), m_width(width) {
      if (m_width > MaxN) {
        throw std::runtime_error("width is larger than MaxN");
      }
      apply_mask();

      if constexpr (MaxN == InfinitePrecision && !Signed) {
        if ((m_width == InfinitePrecision) && m_val < 0) {
          throw std::runtime_error("Cannot represent a negative number in infinite precision");
        }
      }
    }

   public:
    std::conditional_t<Signed, SignedStorageType, const StorageType &> get() const {
      if constexpr (Signed) {
        return cast_to_signed();
      } else {
        return m_val;
      }
    }

    template <typename T>
      requires(BitsType<T>)
    _RuntimeBits operator<<(const T &shamt) const {
      return _RuntimeBits{m_val << shamt.get(), m_width};
    }

    template <unsigned shamt>
    _RuntimeBits<addsat_v<MaxN, shamt>, Signed> widening_sll() const {
      using ReturnType = _RuntimeBits<addsat_v<MaxN, shamt>, Signed>;
      unsigned result_width = std::clamp(m_width + shamt, 0u, std::numeric_limits<unsigned>::max());
      return {ReturnType{get(), m_width}.get() << shamt, result_width};
    }

    template <typename T>
      requires(BitsType<T>)
    _RuntimeBits<BitsInfinitePrecision, Signed> widening_sll(const T &shamt) const {
      unsigned result_width =
          std::clamp(m_width + shamt.get(), 0u, std::numeric_limits<unsigned>::max());

      return _RuntimeBits<BitsInfinitePrecision, Signed>{
          _RuntimeBits<BitsInfinitePrecision, Signed>{get(), m_width}.get() << shamt.get(),
          result_width};
    }

    template <typename T>
      requires(BitsType<T>)
    _RuntimeBits operator>>(const T &shamt) const {
      return {m_val >> shamt.get(), m_width};
    }

    // bitwise operators, for which the return type may be unknown if the rhs is
    // unknown
    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    using BitwiseReturnType = typename std::conditional_t<
        RhsBitsType<RhsN, RhsSigned>::PossiblyUnknown,
        _PossiblyUnknownRuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>,
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>>;

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator&(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUknown) {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        // any bit that is 0 in lhs is known in the result, regardless of its
        // status in rhs
        typename _Bits<constmax_v<MaxN, RhsN>, false>::StorageType result_unknown_mask =
            rhs.unknown_mask().get() & lhs.get();

        return _PossiblyUnknownRuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() & rhs.get(), std::max(m_width, _rhs.width()), result_unknown_mask};
      } else {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        return _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() & rhs.get(), std::max(m_width, _rhs.width())};
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator|(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUknown) {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        // any bit that is | in lhs is known in the result, regardless of its
        // status in rhs
        typename _Bits<constmax_v<MaxN, RhsN>, false>::StorageType result_unknown_mask =
            rhs.unknown_mask().get() & ~(lhs.get());

        return _PossiblyUnknownRuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() | rhs.get(), std::max(m_width, _rhs.width()), result_unknown_mask};
      } else {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        return _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() | rhs.get(), std::max(m_width, _rhs.width())};
      }
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    BitwiseReturnType<RhsBitsType, RhsN, RhsSigned> operator^(
        const RhsBitsType<RhsN, RhsSigned> &_rhs) const {
      if constexpr (RhsBitsType<RhsN, RhsSigned>::PossiblyUknown) {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        return _PossiblyUnknownRuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() ^ rhs.get(), std::max(m_width, _rhs.width()), rhs.unknown_mask()};
      } else {
        _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};
        RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};

        return _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{
            lhs.get() ^ rhs.get(), std::max(m_width, _rhs.width())};
      }
    }

    // arithmetic operators that are not defined for unknown values; the return
    // type is known
#define RUNTIME_BITS_BINARY_OP(op)                                                      \
  template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned> \
    requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)                                    \
  _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned> operator op(                \
      const RhsBitsType<RhsN, RhsSigned> &_rhs) const {                                 \
    _RuntimeBits<constmax_v<MaxN, RhsN>, Signed> lhs{*this};                            \
    RhsBitsType<constmax_v<MaxN, RhsN>, RhsSigned> rhs{_rhs};                           \
    return _RuntimeBits<constmax_v<MaxN, RhsN>, Signed && RhsSigned>{                   \
        lhs.get() op rhs.get(), std::max(m_width, _rhs.width())};                       \
  }

    RUNTIME_BITS_BINARY_OP(+)
    RUNTIME_BITS_BINARY_OP(-)
    RUNTIME_BITS_BINARY_OP(*)
    RUNTIME_BITS_BINARY_OP(/)
    RUNTIME_BITS_BINARY_OP(%)

#undef RUNTIME_BITS_BINARY_OP

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(BitsType<RhsBitsType<RhsN, RhsSigned>>)
    _RuntimeBits<addsat_v<MaxN, RhsN>, Signed && RhsSigned> widening_mul(
        const RhsBitsType<RhsN, RhsSigned> &other) const {
      _RuntimeBits<addsat_v<MaxN, RhsN>, Signed> lhs{
          m_val, std::clamp(m_width + other.width(), 0u, std::numeric_limits<unsigned>::max())};

      const unsigned result_width =
          std::clamp(m_width + other.width(), 0u, std::numeric_limits<unsigned>::max());

      if constexpr (RhsBitsType<addsat_v<MaxN, RhsN>, RhsSigned>::RuntimeWidth) {
        RhsBitsType<addsat_v<MaxN, RhsN>, RhsSigned> rhs{other, result_width};

        return {lhs.value() * rhs.value(), result_width};
      } else {
        RhsBitsType<addsat_v<MaxN, RhsN>, RhsSigned> rhs{other};

        return {lhs.value() * rhs.value(), result_width};
      }
    }

#define RUNTIME_BITS_BINARY_OP(op)                                                     \
  template <template <unsigned, bool> typename BitsType, unsigned _MaxN, bool _Signed> \
    requires(BitsType<_MaxN, _Signed>::IsABits)                                        \
  bool operator op(const BitsType<_MaxN, _Signed> &other) const {                      \
    return get() op other.get();                                                       \
  }

    RUNTIME_BITS_BINARY_OP(==)
    RUNTIME_BITS_BINARY_OP(!=)
    RUNTIME_BITS_BINARY_OP(>)
    RUNTIME_BITS_BINARY_OP(>=)
    RUNTIME_BITS_BINARY_OP(<)
    RUNTIME_BITS_BINARY_OP(<=)

#undef RUNTIME_BITS_BINARY_OP

    _RuntimeBits operator~() { return {~m_val, m_width}; }

    _RuntimeBits operator-() {
      if constexpr (Signed) {
        return {-sign_extend(), m_width};
      } else {
        return {-m_val, m_width};
      }
    }

    // post-increment
    _RuntimeBits operator++(int) {
      _RuntimeBits tmp{*this};
      m_val++;
      apply_mask();
      return tmp;
    }

    // assignment
    _RuntimeBits &operator=(const _RuntimeBits &o) {
      if (&o == this) {
        return *this;
      }
      m_val = o.m_val;
      return *this;
    }

    template <template <unsigned, bool> class RhsBitsType, unsigned RhsN, bool RhsSigned>
      requires(KnownBitsType<RhsBitsType<RhsN, RhsSigned>>)
    _RuntimeBits &operator=(const RhsBitsType<RhsN, RhsSigned> &o) {
      if constexpr (RhsSigned) {
        m_val = o.cast_to_signed();
      } else {
        m_val = o.m_val;
      }
      apply_mask();
      return *this;
    }

    friend std::ostream &operator<<(std::ostream &stream, const _RuntimeBits &val) {
      if constexpr (std::same_as<StorageType, unsigned __int128> ||
                    std::same_as<StorageType, __int128>) {
        stream << fmt::format("{:x}", val.m_val);
      } else {
        stream << val.m_val;
      }
      return stream;
    }

   private:
    StorageType m_val;
    const unsigned m_width;
  };

  static_assert(BitsType<_RuntimeBits<64, false>>);
  static_assert(BitsType<_RuntimeBits<64, true>>);
  static_assert(KnownBitsType<_RuntimeBits<64, true>>);
  static_assert(KnownBitsType<_RuntimeBits<64, false>>);

  using RuntimeBits = _RuntimeBits<BitsInfinitePrecision, false>;

  template <unsigned N, bool Signed>
  class _PossiblyUnknownBits {
   public:
    // used for template concept resolution
    constexpr static bool IsABits = true;
    constexpr static bool RuntimeWidth = false;
    constexpr static bool PossiblyUnknown = true;
    constexpr static bool IsSigned = Signed;

    using MaskType = _Bits<N, false>;

    constexpr static unsigned width() { return N; }
    constexpr const _Bits<N, Signed> &value() const { return m_val; }
    constexpr _Bits<N, Signed> unknown_mask() const { return m_unknown_mask; }

    using StorageType = typename _Bits<N, Signed>::StorageType;
    using SignedStorageType = typename _Bits<N, Signed>::SignedStorageType;

   private:
    template <char... Str>
    friend constexpr _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, false>
    operator""_xb();

    template <TemplateString Str>
    friend constexpr _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, false> operator""_xb();

    template <unsigned _N, bool _Signed>
    friend class _PossiblyUnknownBits;

    static consteval bool needs_mask() { return _Bits<N, Signed>::needs_mask(); }

    template <unsigned _N = N>
      requires(N <= BitsMaxNativePrecision)
    static consteval StorageType mask() {
      return _Bits<N, Signed>::mask();
    }

    template <unsigned _N = N>
      requires(N > BitsMaxNativePrecision)
    static StorageType mask() {
      return _Bits<N, Signed>::mask();
    }

   public:
    //
    // constructors
    //

    // default: every bit is unknown
    explicit constexpr _PossiblyUnknownBits() : m_unknown_mask(~static_cast<StorageType>(0)) {}

    constexpr _PossiblyUnknownBits(const _PossiblyUnknownBits &) = default;
    constexpr _PossiblyUnknownBits(_PossiblyUnknownBits &&) = default;

    // from another bits type
    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>
      requires(BitsType<M, _Signed>::IsABits)
    explicit constexpr _PossiblyUnknownBits(const BitsType<M, _Signed> &other)
        : m_val(other.value()), m_unknown_mask(other.unknown_mask()) {}

    // from an explicit (known) value and mask
    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed, unsigned MaskN>
      requires(BitsType<M, _Signed>::IsABits && !BitsType<M, _Signed>::PossiblyUnknown)
    explicit constexpr _PossiblyUnknownBits(const BitsType<M, _Signed> &value,
                                            const _Bits<MaskN, false> &unknown_mask)
        : m_val(value.value()), m_unknown_mask(unknown_mask) {}

   private:
    // from a storagetype, only to be used internally
    template <bool _Signed = Signed>
      requires(!_Signed)
    explicit constexpr _PossiblyUnknownBits(const StorageType &val, const StorageType &unknown_mask)
        : m_val(val), m_unknown_mask(unknown_mask) {}
    template <bool _Signed = Signed>
      requires(_Signed)
    explicit constexpr _PossiblyUnknownBits(const SignedStorageType &val,
                                            const StorageType &unknown_mask)
        : m_val(val), m_unknown_mask(mask) {}

   public:
    constexpr ~_PossiblyUnknownBits() noexcept = default;

    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>
      requires(BitsType<M, _Signed>::IsABits && BitsType<M, _Signed>::PossiblyUknown)
    constexpr operator BitsType<M, Signed>() const {
      if constexpr (!BitsType<M, _Signed>::PossiblyUnknown) {
        if (m_unknown_mask != 0) {
          throw UndefinedValueError("Cannot convert value with unknowns to Bits type");
        }
      }
      return {*this};
    }

    template <typename T = std::conditional_t<Signed, SignedStorageType, StorageType>>
    constexpr T get() const {
      if (m_unknown_mask == 0_b) {
        return m_val.get();
      } else {
        throw UndefinedValueError("Cannot convert value with unknowns to a native C++ type");
      }
    }

    template <typename T = std::conditional_t<Signed, SignedStorageType, StorageType>>
    constexpr T get_ignore_unknown() const {
      return m_val.get();
    }

    // assignment
    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits &operator=(const BitsType<M, _Signed> &rhs) {
      m_val = rhs.value();
      m_unknown_mask = rhs.unknown_mask();
      return *this;
    }

    // negate operator
    constexpr _PossiblyUnknownBits operator-() const { return {-m_val, m_unknown_mask}; }

    // invert operator
    constexpr _PossiblyUnknownBits operator~() const & { return {~m_val, m_unknown_mask}; }

#define BITS_COMPARISON_OPERATOR(op)                                              \
  template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>   \
  constexpr bool operator op(const BitsType<M, _Signed> &rhs) {                   \
    if (m_unknown_mask != 0_b ||                                                  \
        (BitsType<M, _Signed>::PossiblyUnknown && (rhs.unknown_mask() != 0_b))) { \
      throw UndefinedValueError("Cannot compare unknown value");                  \
    }                                                                             \
    return get() op rhs.get();                                                    \
  }

    BITS_COMPARISON_OPERATOR(==)
    BITS_COMPARISON_OPERATOR(!=)
    BITS_COMPARISON_OPERATOR(<)
    BITS_COMPARISON_OPERATOR(>)
    BITS_COMPARISON_OPERATOR(<=)
    BITS_COMPARISON_OPERATOR(>=)

#undef BITS_COMPARISON_OPERATOR

    // the arithmetic operators are undefined with unknown values, so
    // these operators return {Runtime}Bits
#define BITS_ARITHMETIC_OPERATOR(op)                                                 \
  template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>      \
    requires(BitsType<M, _Signed>::RuntimeWidth == false)                            \
  constexpr _Bits<constmax_v<N, M>, Signed && _Signed> operator op(                  \
      const BitsType<M, _Signed> &rhs) const {                                       \
    return _Bits<constmax_v<N, M>, Signed && _Signed>{get() op rhs.get()};           \
  }                                                                                  \
                                                                                     \
  template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>      \
    requires(BitsType<M, _Signed>::RuntimeWidth == true)                             \
  constexpr _RuntimeBits<constmax_v<N, M>, Signed && _Signed> operator op(           \
      const BitsType<M, _Signed> &rhs) const {                                       \
    return _RuntimeBits<constmax_v<N, M>, Signed && _Signed>{                        \
        get() op rhs.get(),                                                          \
        std::clamp(width() + rhs.width(), 0, std::numeric_limits<unsigned>::max())}; \
  }

    BITS_ARITHMETIC_OPERATOR(+)
    BITS_ARITHMETIC_OPERATOR(-)
    BITS_ARITHMETIC_OPERATOR(*)
    BITS_ARITHMETIC_OPERATOR(/)
    BITS_ARITHMETIC_OPERATOR(%)

#undef BITS_ARITHMETIC_OPERATOR

    template <unsigned ToN, bool ToSign>
    using CastType = typename std::conditional_t<
        ToSign, typename BitsSignedStorageType<ToN>::type,
        std::conditional_t<ToN == N, const typename BitsStorageType<N>::type &,
                           typename BitsStorageType<ToN>::type>>;

    template <unsigned ToN, bool ToSign>
    CastType<ToN, ToSign> cast_to() const {
      if constexpr (N == ToN) {
        if constexpr (Signed) {
          // sign extend to the underlying width
          return m_val.sign_extend();
        } else {
          return m_val.m_val;
        }
      } else if constexpr (N < ToN) {
        // growing the value
        if constexpr (Signed) {
          // sign extension
          return m_val.cast_to_signed();
        } else {
          // zero extension
          return m_val.m_val;
        }
      } else {
        // +N > ToN
        // shrinking the value
        if constexpr (ToSign) {
          return _Bits<ToN, ToSign>{m_val}.sign_extend();
        } else {
          return _Bits<ToN, ToSign>{m_val}.m_val;
        }
      }
    }

    // bitwise operators (&, |, ^)
    // these are all different because & and | can change the unknown mask based
    // on value

    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && !BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator&(
        const BitsType<_N, _Signed> &rhs) const {
      return _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed>{
          m_val & rhs.value(), m_unknown_mask & rhs.value()};
    }

    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator&(
        const BitsType<_N, _Signed> &rhs) const {
      _Bits<N, false> lhs_known_zeros = ~m_val & ~m_unknown_mask;
      _Bits<_N, false> rhs_known_zeros = ~rhs.value() & ~rhs.unknown_mask();
      _Bits<constmax_v<N, _N>, false> result_unknown_mask =
          (m_unknown_mask | rhs.unknown_mask()) & ~lhs_known_zeros & ~rhs_known_zeros;
      return _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed>{m_val & rhs.value(),
                                                                        result_unknown_mask};
    }

    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && !BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator|(
        const BitsType<_N, _Signed> &rhs) const {
      return _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed>{
          m_val | rhs.value(), m_unknown_mask & ~rhs.value()};
    }
    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator|(
        const BitsType<_N, _Signed> &rhs) const {
      auto val =
          cast_to<constmax_v<N, _N>, Signed>() | rhs.template cast_to<constmax_v<N, _N>, _Signed>();
      return _PossiblyUnknownBits < constmax_v<N, _N>,
             Signed && _Signed > (val, m_unknown_mask.m_val & rhs.m_unknown_mask.m_val);
    }

    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && !BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator^(
        const BitsType<_N, _Signed> &rhs) const {
      auto val =
          cast_to<constmax_v<N, _N>, Signed>() ^ rhs.template cast_to<constmax_v<N, _N>, _Signed>();
      return _PossiblyUnknownBits < constmax_v<N, _N>,
             Signed && _Signed > (m_val ^ rhs.m_val, m_unknown_mask.m_val);
    }
    template <template <unsigned, bool> class BitsType, unsigned _N, bool _Signed>
      requires(BitsType<_N, _Signed>::IsABits && BitsType<_N, _Signed>::PossiblyUnknown)
    constexpr _PossiblyUnknownBits<constmax_v<N, _N>, Signed && _Signed> operator^(
        const BitsType<_N, _Signed> &rhs) const {
      auto val =
          cast_to<constmax_v<N, _N>, Signed>() ^ rhs.template cast_to<constmax_v<N, _N>, _Signed>();
      return _PossiblyUnknownBits < constmax_v<N, _N>,
             Signed && _Signed > (val, m_unknown_mask.m_val & rhs.m_unknown_mask.m_val);
    }

#undef BITS_BITWISE_OPERATOR

    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator<<(const BitsType<M, false> &shamt) {
      if constexpr (BitsType<M, _Signed>::PossiblyUnknown) {
        if (shamt.unknown_mask() != 0) {
          throw UndefinedValueError("Cannot shift an unknown amount");
        }
      }
      return {m_val << shamt, m_unknown_mask << shamt};
    }

    template <template <unsigned, bool> class BitsType, unsigned M, bool _Signed>
    constexpr _PossiblyUnknownBits operator>>(const BitsType<M, _Signed> &shamt) const {
      if constexpr (BitsType<M, _Signed>::PossiblyUnknown) {
        if (shamt.unknown_mask() != 0) {
          throw UndefinedValueError("Cannot shift an unknown amount");
        }
      }
      return {m_val >> shamt, m_unknown_mask >> shamt};
    }

    // widening left shift when the shift amount is known at compile time
    template <unsigned SHAMT>
    constexpr _PossiblyUnknownBits<addsat_v<N, SHAMT>, Signed> widening_sll() const {
      using ReturnType = _PossiblyUnknownBits<addsat_v<N, SHAMT>, Signed>;
      return {ReturnType{m_val}.m_val << SHAMT, ReturnType{m_val}.m_unknown_mask << SHAMT};
    }

    friend std::ostream &operator<<(std::ostream &stream, const _PossiblyUnknownBits &val) {
      if (val.m_unknown_mask == 0_b) {
        stream << val.m_val;
      } else {
        stream << fmt::format("{} (unknown mask: {})", val.m_val, val.m_unknown_mask);
      }
      return stream;
    }

    template <unsigned msb, unsigned lsb>
    constexpr _PossiblyUnknownBits<msb - lsb + 1, false> extract() const {
      static_assert(msb >= lsb);
      return _PossiblyUnknownBits<msb - lsb + 1, false>{
          m_val >> lsb, m_unknown_mask >> lsb};  // masking will happen in the constructor
    }

    template <typename IndexType, typename ValueType>
    constexpr _PossiblyUnknownBits &setBit(const IndexType &idx, const ValueType &value) {
      StorageType pos_mask = static_cast<StorageType>(1) << idx;
      m_val = (m_val & ~pos_mask) | ((static_cast<StorageType>(value) << idx) & pos_mask);
      m_unknown_mask &= ~pos_mask;
      return *this;
    }

    //  private:
    _Bits<N, Signed> m_val;
    _Bits<N, false> m_unknown_mask;
  };

  static_assert(PossiblyUnknownBitsType<_PossiblyUnknownBits<64, false>>);
  static_assert(PossiblyUnknownBitsType<_PossiblyUnknownBits<64, true>>);

  template <char... Str>
  constexpr _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, false> operator""_xb() {
    if constexpr (BitsStr<true, Str..., '\0'>::width <= BitsMaxNativePrecision) {
      return _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, false>(
          BitsStr<true, Str..., '\0'>::val, BitsStr<true, Str..., '\0'>::unknown_mask);
    } else {
      return mpz_class{BitsStr<true, Str..., '\0'>::str};
    }
  }

  template <TemplateString Str>
  constexpr _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, false> operator""_xb() {
    if constexpr (BitsTemplateStr<true, Str>::width <= BitsMaxNativePrecision) {
      return _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, false>(
          BitsTemplateStr<true, Str>::val, BitsTemplateStr<true, Str>::unknown_mask);
    } else {
      return mpz_class{BitsTemplateStr<true, Str>::str};
    }
  }

  template <char... Str>
  constexpr _PossiblyUnknownBits<BitsStr<true, Str..., '\0'>::width, true> operator""_xsb() {
    if constexpr (BitsStr<true, Str..., '\0'>::width <= BitsMaxNativePrecision) {
      return {BitsStr<true, Str..., '\0'>::val, BitsStr<true, Str..., '\0'>::unknown_mask};
    } else {
      return mpz_class{BitsStr<true, Str..., '\0'>::str};
    }
  }

  template <TemplateString Str>
  constexpr _PossiblyUnknownBits<BitsTemplateStr<true, Str>::width, true> operator""_xsb() {
    if constexpr (BitsTemplateStr<true, Str>::width <= BitsMaxNativePrecision) {
      return {BitsTemplateStr<true, Str>::val, BitsTemplateStr<true, Str>::unknown_mask};
    } else {
      return mpz_class{BitsTemplateStr<true, Str>::str};
    }
  }

  static_assert((0x0_xb).width() == 1);
  static_assert((0x1_xb).width() == 1);
  static_assert((0_xb).width() == 1);
  static_assert((1_xb).width() == 1);
  static_assert((0x2_xb).width() == 2);
  static_assert((0x7_xb).width() == 3);
  static_assert((0x8_xb).width() == 4);
  static_assert((0xf_xb).width() == 4);
  static_assert((0x1f_xb).width() == 5);
  static_assert((0xffffffffffffffff_xb).width() == 64);

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

  static_assert(("0x1x"_xb).width() == 5);
  static_assert(("0x1x"_xb).unknown_mask().get() == 0xf);

  template <unsigned N>
  using Bits = _Bits<N, false>;

  template <unsigned N>
  using SignedBits = _Bits<N, true>;

  // special values
  static constexpr Bits<65> UNDEFINED_LEGAL = 0x10000000000000000_b;
  static constexpr Bits<66> UNDEFINED_LEGAL_DETERMINISTIC = 0x20000000000000000_b;

  template <unsigned N>
  using PossiblyUnknownBits = _PossiblyUnknownBits<N, false>;

  // Bits where the width is only known at runtime (usually because the width is
  // parameter-dependent)
  // And the value may be an unknown
  template <unsigned MaxN, bool Signed>
  class _PossiblyUnknownRuntimeBits {
    // befriend other bits
    template <unsigned, bool>
    friend class _PossiblyUnknownRuntimeBits;

    template <unsigned, bool>
    friend class _Bits;

    template <unsigned, bool>
    friend class _RuntimeBits;

    template <unsigned, bool>
    friend class _PossiblyUnknownBits;

    using StorageType = _Bits<MaxN, Signed>::StorageType;
    using SignedStorageType = _Bits<MaxN, Signed>::SignedStorageType;

    StorageType mask() const {
      if (m_width == MaxN) {
        return ~StorageType{0};
      } else {
        return (StorageType{1} << m_width) - 1;
      }
    }

    void apply_mask() { m_val = m_val & mask(); }

   public:
    // used for template concept resolution
    constexpr static bool IsABits = true;
    constexpr static bool RuntimeWidth = true;
    constexpr static bool PossiblyUnknown = true;
    constexpr static bool IsSigned = Signed;

    // width must always be supplied
    _PossiblyUnknownRuntimeBits() = delete;

    constexpr _PossiblyUnknownRuntimeBits(unsigned width) : m_width(width) {}

    template <typename T>
    constexpr _PossiblyUnknownRuntimeBits(const T &initial_value, unsigned width)
        : m_val(initial_value), m_width(width) {
      apply_mask();
    }

    _PossiblyUnknownRuntimeBits(const _PossiblyUnknownRuntimeBits &initial_value)
        : m_val(initial_value.value()), m_width(initial_value.m_width) {}

    template <unsigned OtherMaxN>
      requires(OtherMaxN <= MaxN)
    _PossiblyUnknownRuntimeBits(const _PossiblyUnknownRuntimeBits<OtherMaxN, Signed> &initial_value)
        : m_val(initial_value.value()), m_width(initial_value.m_width) {
      apply_mask();
    }

   private:
    _PossiblyUnknownRuntimeBits(const StorageType &value, unsigned width,
                                const _Bits<MaxN, false> &unknown_mask)
        : m_val(value, unknown_mask.get()), m_width(width) {}

   public:
    template <bool _Signed = Signed>
      requires(_Signed == false)
    _PossiblyUnknownRuntimeBits<MaxN, true> make_signed() const {
      return _PossiblyUnknownRuntimeBits<MaxN, true>{sign_extend(m_val.get()), m_width};
    }
    template <bool _Signed = Signed>
      requires(_Signed == true)
    const _PossiblyUnknownRuntimeBits<MaxN, true> &make_signed() const {
      return *this;
    }

    constexpr ~_PossiblyUnknownRuntimeBits() noexcept = default;

    constexpr _RuntimeBits<MaxN, Signed> &value() const { return m_val.value(); }
    constexpr _Bits<MaxN, false> unknown_mask() const { return m_val.unknown_mask(); }

    StorageType sign_extend(const StorageType &value) const {
      udb_assert(m_width <= BitsMaxNativePrecision, "Can't sign extend a GMP number");
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
    }

    unsigned width() const { return m_width; }
    auto get() const { return m_val.get(); }
    auto get_ignore_unknown() const { return m_val.get_ignore_unknown(); }

    template <typename IntType>
      requires(std::integral<IntType>)
    operator IntType() const noexcept {
      return static_cast<IntType>(m_val);
    }

    template <typename T>
    _PossiblyUnknownRuntimeBits operator<<(const T &shamt) const {
      return {m_val << shamt, m_width};
    }

    template <typename T>
    _PossiblyUnknownRuntimeBits<BitsInfinitePrecision, Signed> widening_sll(const T &shamt) const {
      return {m_val << shamt,
              std::clamp(m_width + shamt, 0u, std::numeric_limits<unsigned>::max())};
    }

    template <unsigned shamt, typename T>
    _PossiblyUnknownRuntimeBits<addsat_v<MaxN, shamt>, Signed> widening_sll() const {
      return {m_val << shamt,
              std::clamp(m_width + shamt, 0u, std::numeric_limits<unsigned>::max())};
    }

    template <typename T>
    _PossiblyUnknownRuntimeBits operator>>(const T &shamt) const {
      return {m_val >> shamt, m_width};
    }

#define RUNTIME_BITS_BINARY_OP(op)                                                          \
  template <unsigned N, bool _Signed>                                                       \
    requires(MaxN >= N)                                                                     \
  _PossiblyUnknownRuntimeBits operator op(const _Bits<N, _Signed> &other) const {           \
    return {m_val op _Bits<MaxN, _Signed>{other}.get(), std::max(N, m_width)};              \
  }                                                                                         \
                                                                                            \
  template <unsigned N, bool _Signed>                                                       \
    requires(MaxN < N)                                                                      \
  _PossiblyUnknownRuntimeBits operator op(const _Bits<N, _Signed> &other) const {           \
    return {m_val op other.get(), std::max(N, m_width)};                                    \
  }                                                                                         \
                                                                                            \
  _PossiblyUnknownRuntimeBits operator op(const _PossiblyUnknownRuntimeBits &other) const { \
    return {m_val op other.m_val, std::max(other.m_width, m_width)};                        \
  }

    RUNTIME_BITS_BINARY_OP(|)
    RUNTIME_BITS_BINARY_OP(&)
    RUNTIME_BITS_BINARY_OP(^)

#undef RUNTIME_BITS_BINARY_OP

#define RUNTIME_BITS_BINARY_OP(op)                                                               \
  _PossiblyUnknownRuntimeBits operator op(const _PossiblyUnknownRuntimeBits &other) const {      \
    if (other.m_width != m_width) {                                                              \
      if (other.m_width > m_width) {                                                             \
        return {_PossiblyUnknownRuntimeBits{m_val, other.m_width}.m_val op other.m_val,          \
                std::max(other.m_width, m_width)};                                               \
      } else {                                                                                   \
        return {m_val op _PossiblyUnknownRuntimeBits{other.m_val, m_width}.m_val,                \
                std::max(other.m_width, m_width)};                                               \
      }                                                                                          \
    } else {                                                                                     \
      return {m_val op other.m_val, std::max(other.m_width, m_width)};                           \
    }                                                                                            \
  }                                                                                              \
                                                                                                 \
  template <unsigned N, bool _Signed>                                                            \
  _PossiblyUnknownRuntimeBits<constmax<MaxN, N>::value, Signed && _Signed> operator op(          \
      const _Bits<N, _Signed> &other) const {                                                    \
    using ReturnType = _PossiblyUnknownRuntimeBits<constmax<MaxN, N>::value, Signed && _Signed>; \
    if (N != m_width) {                                                                          \
      if (N > m_width) {                                                                         \
        return {ReturnType{m_val, N}.m_val op other.get(), N};                                   \
      } else {                                                                                   \
        return {m_val op ReturnType{other.get(), m_width}.m_val, m_width};                       \
      }                                                                                          \
    } else {                                                                                     \
      return {m_val op other.m_val, N};                                                          \
    }                                                                                            \
  }

    RUNTIME_BITS_BINARY_OP(+)
    RUNTIME_BITS_BINARY_OP(-)
    RUNTIME_BITS_BINARY_OP(*)
    RUNTIME_BITS_BINARY_OP(/)
    RUNTIME_BITS_BINARY_OP(%)

#undef RUNTIME_BITS_BINARY_OP

#define RUNTIME_BITS_BINARY_OP(op)                                         \
  bool operator op(const _PossiblyUnknownRuntimeBits &other) const {       \
    return m_val op other.m_val;                                           \
  }                                                                        \
  template <typename PossiblyUnknownBitsCompatibleType>                    \
  bool operator op(const PossiblyUnknownBitsCompatibleType &other) const { \
    return m_val op other.m_val;                                           \
  }

    RUNTIME_BITS_BINARY_OP(==)
    RUNTIME_BITS_BINARY_OP(!=)
    RUNTIME_BITS_BINARY_OP(>)
    RUNTIME_BITS_BINARY_OP(>=)
    RUNTIME_BITS_BINARY_OP(<)
    RUNTIME_BITS_BINARY_OP(<=)

#undef RUNTIME_BITS_BINARY_OP

    _PossiblyUnknownRuntimeBits operator~() { return {~m_val, m_width}; }

    _PossiblyUnknownRuntimeBits operator-() { return {-m_val, m_width}; }

#define RUNTIME_BITS_ASSIGN_OP(op)                                                      \
  template <unsigned N, bool _Signed>                                                   \
  _PossiblyUnknownRuntimeBits &operator op(const _Bits<N, _Signed> &other) {            \
    m_val op other;                                                                     \
    return *this;                                                                       \
  }                                                                                     \
                                                                                        \
  _PossiblyUnknownRuntimeBits &operator op(const _PossiblyUnknownRuntimeBits & other) { \
    m_val op other.m_val;                                                               \
    return *this;                                                                       \
  }                                                                                     \
                                                                                        \
  template <std::integral IntType>                                                      \
  _PossiblyUnknownRuntimeBits &operator op(const IntType & other) {                     \
    m_val op other;                                                                     \
    return *this;                                                                       \
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

    template <typename PossiblyUnknownBitsCompatibleType>
    _PossiblyUnknownRuntimeBits &operator=(const PossiblyUnknownBitsCompatibleType &rhs) {
      m_val = rhs;
      apply_mask();
      return *this;
    }

   private:
    _PossiblyUnknownBits<MaxN, Signed> m_val;
    unsigned m_width;
  };

}  // namespace udb
