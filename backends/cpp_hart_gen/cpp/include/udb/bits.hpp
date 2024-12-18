#pragma once

#include <bit>
#include <cstdint>
#include <concepts>
#include <type_traits>
#include <limits>
#include <gmpxx.h>

#include <fmt/core.h>
#include <fmt/format.h>

// we need this to be true for GMP
static_assert(sizeof(long unsigned int) == sizeof(long long unsigned int));

namespace udb
{

  template <unsigned N>
  struct BitsStorageType
  {
    using type =
        std::conditional_t<(N > 64), mpz_class,
                           std::conditional_t<(N > 32), uint64_t,
                                              std::conditional_t<(N > 16), uint32_t,
                                                                 std::conditional_t<(N > 8), uint16_t,
                                                                                    uint8_t>>>>;
  };

  template <unsigned N>
  struct BitsSignedStorageType
  {
    using type =
        std::conditional_t<(N > 64), mpz_class,
                           std::conditional_t<(N > 32), int64_t,
                                              std::conditional_t<(N > 16), int32_t,
                                                                 std::conditional_t<(N > 8), int16_t,
                                                                                    int8_t>>>>;
  };

  // N that actually means infinite
  constexpr static unsigned BitsInfinitePrecision = std::numeric_limits<unsigned>::max();

  // max N value where storage is using a native integer type
  // above this, the storage is GMP, and the Bits type can't be constexpr
  constexpr static unsigned BitsMaxNativePrecision = 64;

  // used to hold compile-time-known-bit-width integer
  template <unsigned N, bool Signed>
  class _Bits
  {
    static_assert(N > 0);

  public:
    // value of N that represents unknown precision (happens when there is a left shift by unknown value)
    constexpr static unsigned InfinitePrecision = BitsInfinitePrecision;

    // largest value of N that still uses a native underlying type
    // beyond this, the number of bits is still tracked, but the storage is using gmp
    constexpr static unsigned MaxNativePrecision = BitsMaxNativePrecision;

    // advertise the width
    constexpr static unsigned Width = N;

    using StorageType = typename BitsStorageType<N>::type;
    using SignedStorageType = typename BitsSignedStorageType<N>::type;

    // befriend other Bits templates so we can access the state
    // template <unsigned M, bool _Signed>
    //   requires((M != N) || (Signed != _Signed))
    // friend class _Bits;

    // returns true if this Bits width requires storage masking
    template <unsigned _N = N>
    static consteval bool needs_mask()
    {
      using _StorageType = typename BitsStorageType<_N>::type;

      if constexpr (_N == InfinitePrecision)
      {
        // infinite bits, so there is no masking
        return false;
      }
      else if constexpr (_N > MaxNativePrecision)
      {
        // gmp (infinite) storage, so everything needs masked
        return true;
      }
      else if constexpr (_N == (sizeof(_StorageType) * 8))
      {
        // we fit exactly in our native storage
        return false;
      }
      else
      {
        // using native storage, but there are unused bits
        return true;
      }
    }

  public:
    // mask of all ones for the Bits type
    template <unsigned _N = N>
      requires(N <= MaxNativePrecision)
    static consteval StorageType mask()
    {
      if constexpr (std::integral<StorageType> && (N == (sizeof(StorageType) * 8)))
      {
        return ~StorageType{0};
      }
      else
      {
        return ((StorageType{1} << N) - 1);
      }
    }
    template <unsigned _N = N>
      requires(N > MaxNativePrecision)
    static StorageType mask()
    {
      static_assert(N != InfinitePrecision); // this isn't a good idea ;)
      return ((StorageType{1} << N) - 1);
    }
    static_assert(needs_mask<4>() == true);
    static_assert(needs_mask<8>() == false);
    static_assert(needs_mask<16>() == false);
    static_assert(needs_mask<32>() == false);
    static_assert(needs_mask<64>() == false);
    static_assert(needs_mask<65>() == true);
    static_assert(needs_mask<128>() == true);
    static_assert(needs_mask<129>() == true);
    static_assert(needs_mask<256>() == true);
    static_assert(needs_mask<512>() == true);
    static_assert(needs_mask<InfinitePrecision>() == false);

    // helper to find the max of two numbers at compile time
    template <unsigned... _N>
    struct constmax
    {
      template <unsigned A, unsigned B, unsigned... Nums>
      consteval static unsigned Max()
      {
        constexpr unsigned AorB = (A > B) ? A : B;
        if constexpr (sizeof...(Nums) > 0)
        {
          return Max<AorB, Nums...>();
        }
        else
        {
          return AorB;
        }
      }
      constexpr static unsigned value = Max<_N...>();
    };
    static_assert(constmax<std::numeric_limits<unsigned>::max(), std::numeric_limits<unsigned>::max()>::value == std::numeric_limits<unsigned>::max());

  public:
    // given storage for a Bits<N> type, return a signed version of it in the storage class
    template <unsigned _N = N>
      requires(_N <= MaxNativePrecision)
    static constexpr SignedStorageType cast_to_signed(const StorageType &unsigned_value)
    {
      if constexpr (N == (sizeof(StorageType) * 8))
      {
        // exactly fits in a native type, so just cast it
        return static_cast<SignedStorageType>(unsigned_value);
      }
      else
      {
        // we have a native type, but some bits are unsed. need to sign extend the storage
        return static_cast<SignedStorageType>(sign_extend(unsigned_value));
      }
    }

    template <unsigned _N = N>
      requires(_N > MaxNativePrecision)
    static SignedStorageType cast_to_signed(const StorageType &unsigned_value)
    {
      // this is gmp storage. We can't just sign extend, so we'll need to do the compliment
      if constexpr (N == InfinitePrecision)
      {
        // our 'unsigned' value is actually signed
        return unsigned_value;
      }
      else
      {
        auto v = unsigned_value;
        if (((v >> (N - 1)) & 1) == 1)
        {
          // the number is now negative!
          // The two's compliment value is 2^N - value
          v = -((StorageType{1} << N) - v);
        }
        return v;
      }
    }

    // return a signed version of self
    constexpr SignedStorageType cast_to_signed() const
    {
      return cast_to_signed(m_val);
    }

    template <bool _Signed = Signed>
      requires(_Signed == false)
    constexpr _Bits<N, true> make_signed() const
    {
      return _Bits<N, true>{m_val};
    }
    template <bool _Signed = Signed>
      requires(_Signed == true)
    constexpr _Bits<N, true> &make_signed() const
    {
      return *this;
    }

    // given a Bits<N> storage type, sign extend it to the full width of StorageType
    static constexpr StorageType sign_extend(const StorageType &value)
    {
      static_assert(N <= MaxNativePrecision); // doesn't make sense with gmp
      if constexpr (N == sizeof(StorageType) * 8)
      {
        // exact fit, no extension needed
        return value; // no extension needed
      }
      else
      {
        if (value & (StorageType{1} << (N - 1)))
        {
          // fill with ones
          return value | ~mask();
        }
        else
        {
          // no extension needed
          return value;
        }
      }
    }

    static constexpr std::conditional_t<needs_mask(), StorageType, const StorageType &>
    apply_mask(const StorageType &value)
    {
      if constexpr (needs_mask())
      {
        return value & mask();
      }
      else
      {
        return value;
      }
    }

    static _Bits from_string(const std::string &str)
    {
      if constexpr (std::is_same_v<StorageType, mpz_class>) {
        mpz_class gmp_int(str.c_str());
        return _Bits{gmp_int};
      }
      else if constexpr (N <= 64 && N > 32) {
        static_assert(sizeof(long long) == sizeof(uint64_t), "Unexpected long long type");
        if constexpr (Signed) {
          return _Bits(std::stoll(str, nullptr, 0));
        } else {
          return _Bits(std::stoull(str, nullptr, 0));
        }
      } else if constexpr (N <= 32 && N > 16) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long type");
        if constexpr (Signed) {
          return _Bits(std::stol(str, nullptr, 0));
        } else {
          return _Bits(std::stoul(str, nullptr, 0));
        }
      } else if constexpr (N <= 16 && N > 8) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long type");
        if constexpr (Signed) {
          int32_t tmp = std::stol(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<int16_t>::max() && tmp >= std::numeric_limits<int16_t>::min());
          return _Bits(tmp);
        } else {
          uint32_t tmp = std::stoul(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<uint16_t>::max());
          return _Bits(tmp);
        }
      } else if constexpr (N <= 8) {
        // static_assert(sizeof(long) == sizeof(uint32_t), "Unexpected long type");
        if constexpr (Signed) {
          int32_t tmp = std::stol(str, nullptr, 0);
          // assert(tmp <= std::numeric_limits<int8_t>::max() && tmp >= std::numeric_limits<int8_t>::min());
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
    constexpr _Bits(const mpz_class &val)
    {
      m_val = val.get_ui();
    }

    // other is smaller N
    // everything fits, so just copy the storage
    template <unsigned M, bool _Signed>
      requires(M < N)
    constexpr _Bits(const _Bits<M, _Signed> &o)
    {
      if constexpr (N <= MaxNativePrecision && M > MaxNativePrecision)
      {
        m_val = o.m_val.get_ui();
      }
      else
      {
        m_val = o.get();
      }
    }

    // other is bigger N
    // the other value will be truncated
    template <unsigned M, bool _Signed>
      requires(M > N)
    constexpr _Bits(const _Bits<M, _Signed> &o)
    {
      if constexpr (N <= MaxNativePrecision && M > MaxNativePrecision)
      {
        m_val = apply_mask(o.m_val.get_ui());
      }
      else
      {
        m_val = apply_mask(o.m_val);
      }
    }

    // built-in integer type, mask needed
    template <class IntType>
      requires(!std::is_same_v<StorageType, IntType> && std::integral<IntType> && needs_mask())
    constexpr _Bits(const IntType &val)
        : m_val(apply_mask(val))
    {
    }

    // built-in integer type, no mask needed
    template <class IntType>
      requires(!std::is_same_v<StorageType, IntType> && std::integral<IntType> && !needs_mask())
    constexpr _Bits(const IntType &val)
    {
      if constexpr (N == InfinitePrecision && std::is_signed_v<IntType>)
      {
        if (val < 0)
        {
          abort(); // Can't mask off a negative value with infinite precision!
        }
      }
      m_val = val;
    }

    constexpr ~_Bits() noexcept = default;

    template <typename T>
      requires(std::integral<T> && std::is_unsigned_v<T>)
    constexpr operator T() const noexcept
    {
      if constexpr (N > MaxNativePrecision)
      {
        return m_val.get_ui();
      }
      else
      {
        return m_val;
      }
    }

    template <typename T>
      requires(std::integral<T> && std::is_signed_v<T>)
    constexpr operator T() const noexcept
    {
      if constexpr (N > MaxNativePrecision)
      {
        return cast_to_signed().get_si();
      }
      else
      {
        return cast_to_signed();
      }
    }

    // cast to any other Bits type
    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr explicit operator _Bits<M, _Signed>() const noexcept
    {
      if constexpr (Signed)
      {
        return cast_to_signed();
      }
      else
      {
        return m_val;
      }
    }

    template <typename T = std::conditional_t<Signed, SignedStorageType, StorageType>>
    constexpr T get() const
    {
      if constexpr (std::integral<T> && std::is_signed_v<T>)
      {
        if constexpr (N > MaxNativePrecision)
        {
          return cast_to_signed().get_si();
        }
        else
        {
          return cast_to_signed();
        }
      }
      else
      {
        return m_val;
      }
    }

    // assignment
    _Bits &operator=(const _Bits &o) = default;
    _Bits &operator=(_Bits &&o) noexcept = default;

    template <typename IntType>
      requires std::integral<IntType>
    _Bits &operator=(const IntType &o)
    {
      m_val = apply_mask(o);
      return *this;
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    _Bits &operator=(const _Bits<M, _Signed> &o)
    {
      if constexpr ((N <= MaxNativePrecision) && (M > MaxNativePrecision))
      {
        m_val = apply_mask(o.m_val.get_ui());
      }
      else
      {
        m_val = apply_mask(o.m_val);
      }

      return *this;
    }

    // negate operator
    constexpr _Bits operator-() const
    {
      _Bits negated_value;
      negated_value.m_val = apply_mask(-m_val);
      return negated_value;
    }

    // invert operator
    constexpr _Bits operator~() const & { return apply_mask(~m_val); }

#define BITS_COMPARISON_OPERATOR(op)                                        \
  constexpr bool operator op(const _Bits &o) const noexcept                 \
  {                                                                         \
    if constexpr (Signed)                                                   \
    {                                                                       \
      return cast_to_signed() op o.cast_to_signed();                        \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return m_val op o.m_val;                                              \
    }                                                                       \
  }                                                                         \
                                                                            \
  template <typename IntType>                                               \
    requires(std::integral<IntType>)                                        \
  constexpr bool operator op(const IntType &o) const noexcept               \
  {                                                                         \
    if constexpr (Signed)                                                   \
    {                                                                       \
      return cast_to_signed() op o;                                         \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return m_val op o;                                                    \
    }                                                                       \
  }                                                                         \
                                                                            \
  constexpr bool operator op(const mpz_class &o) const noexcept             \
  {                                                                         \
    if constexpr (Signed)                                                   \
    {                                                                       \
      return cast_to_signed() op SignedStorageType{o};                      \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return m_val op o;                                                    \
    }                                                                       \
  }                                                                         \
                                                                            \
  constexpr friend bool operator op(const mpz_class &lhs, const _Bits &rhs) \
  {                                                                         \
    if constexpr (Signed)                                                   \
    {                                                                       \
      return SignedStorageType{lhs} op rhs.cast_to_signed();                \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return lhs op rhs.m_val;                                              \
    }                                                                       \
  }                                                                         \
                                                                            \
  template <typename IntType>                                               \
    requires(std::integral<IntType>)                                        \
  constexpr friend bool operator op(const IntType &lhs, const _Bits &rhs)   \
  {                                                                         \
    if constexpr (Signed)                                                   \
    {                                                                       \
      return lhs op rhs.cast_to_signed();                                   \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return lhs op rhs.m_val;                                              \
    }                                                                       \
  }                                                                         \
                                                                            \
  template <unsigned M, bool _Signed>                                       \
    requires((N != M) || (Signed != _Signed))                               \
  constexpr bool operator op(const _Bits<M, _Signed> &o) const noexcept     \
  {                                                                         \
    if constexpr (Signed && _Signed)                                        \
    {                                                                       \
      return cast_to_signed() op o.cast_to_signed();                        \
    }                                                                       \
    else if constexpr (Signed && !_Signed)                                  \
    {                                                                       \
      return cast_to_signed() op o.m_val;                                   \
    }                                                                       \
    else if constexpr (!Signed && _Signed)                                  \
    {                                                                       \
      return m_val op o.cast_to_signed();                                   \
    }                                                                       \
    else                                                                    \
    {                                                                       \
      return m_val op o.m_val;                                              \
    }                                                                       \
  }

    BITS_COMPARISON_OPERATOR(==)
    BITS_COMPARISON_OPERATOR(!=)
    BITS_COMPARISON_OPERATOR(<)
    BITS_COMPARISON_OPERATOR(>)
    BITS_COMPARISON_OPERATOR(<=)
    BITS_COMPARISON_OPERATOR(>=)

#undef BITS_COMPARISON_OPERATOR

#define BITS_ARITHMETIC_OPERATOR(op)                                                                         \
  constexpr _Bits operator op(const _Bits &o) const                                                          \
  {                                                                                                          \
    return _Bits{get() op o.get()};                                                                          \
  }                                                                                                          \
                                                                                                             \
  template <unsigned M, bool _Signed>                                                                        \
    requires((M != N) || (Signed != _Signed))                                                                \
  constexpr _Bits<constmax<N, M>::value, Signed && _Signed> operator op(const _Bits<M, _Signed> &o) const    \
  {                                                                                                          \
    if constexpr (M > N)                                                                                     \
    {                                                                                                        \
      return _Bits < constmax<N, M>::value, Signed && _Signed > {_Bits<M, _Signed>{get()}.get() op o.get()}; \
    }                                                                                                        \
    else                                                                                                     \
    {                                                                                                        \
      return _Bits < constmax<N, M>::value, Signed && _Signed > {get() op _Bits{o.get()}.get()};             \
    }                                                                                                        \
  }                                                                                                          \
                                                                                                             \
  constexpr _Bits operator op(const mpz_class &o) const                                                      \
  {                                                                                                          \
    return _Bits{get() op o};                                                                                \
  }                                                                                                          \
                                                                                                             \
  template <std::integral IntType>                                                                           \
  constexpr _Bits operator op(const IntType &_rhs) const                                                     \
  {                                                                                                          \
    if constexpr (std::is_signed_v<IntType>)                                                                 \
    {                                                                                                        \
      SignedStorageType rhs = _rhs;                                                                          \
      return _Bits{get() op rhs};                                                                            \
    }                                                                                                        \
    else                                                                                                     \
    {                                                                                                        \
      StorageType rhs = _rhs;                                                                                \
      return _Bits{get() op rhs};                                                                            \
    }                                                                                                        \
  }                                                                                                          \
                                                                                                             \
  template <std::integral IntType>                                                                           \
  constexpr friend _Bits operator op(const IntType &_lhs, const _Bits &rhs)                                  \
  {                                                                                                          \
    if constexpr (std::is_signed_v<IntType>)                                                                 \
    {                                                                                                        \
      SignedStorageType lhs = _lhs;                                                                          \
      return _Bits{lhs op rhs.get()};                                                                        \
    }                                                                                                        \
    else                                                                                                     \
    {                                                                                                        \
      StorageType lhs = _lhs;                                                                                \
      return _Bits{lhs op rhs.get()};                                                                        \
    }                                                                                                        \
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

    constexpr _Bits operator<<(const _Bits &shamt) const
    {
      return _Bits{m_val << shamt.get()};
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits operator<<(const _Bits<M, _Signed> &shamt) const
    {
      return _Bits{m_val << shamt.get()};
    }

    template <std::integral IntType>
    constexpr _Bits operator<<(const IntType &shamt) const
    {
      return _Bits{m_val << shamt};
    }

    constexpr _Bits operator<<(const mpz_t &shamt) const
    {
      return _Bits{m_val << shamt};
    }

    template <std::integral IntType>
    constexpr friend IntType operator<<(const IntType &val, const _Bits &shamt)
    {
      if constexpr (N > MaxNativePrecision)
      {
        if constexpr (std::is_signed_v<IntType>)
        {
          return (val << shamt.m_val).get_si();
        }
        else
        {
          return (val << shamt.m_val).get_ui();
        }
      }
      else
      {
        return val << shamt.m_val;
      }
    }

    constexpr friend mpz_class operator<<(const mpz_class &val, const _Bits &shamt)
    {
      return val << shamt.m_val;
    }

    template <unsigned shamt>
    constexpr _Bits<N + shamt, Signed> sll() const
    {
      return _Bits<N + shamt, Signed>{_Bits<N + shamt, Signed>{m_val}.m_val << shamt};
    }

    constexpr _Bits operator>>(const _Bits &shamt) const
    {
      return _Bits{m_val >> shamt.m_val};
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits operator>>(const _Bits<M, _Signed> &shamt) const
    {
      return _Bits{m_val >> shamt.m_val};
    }

    template <std::integral IntType>
    constexpr _Bits operator>>(const IntType &shamt) const
    {
      return _Bits{m_val >> shamt};
    }

    _Bits operator>>(const mpz_class &shamt) const
    {
      return _Bits{m_val >> shamt};
    }

    template <std::integral IntType>
    constexpr friend IntType operator>>(const IntType &val, const _Bits &shamt)
    {
      return val >> shamt.get();
    }

    friend mpz_class operator>>(const mpz_class &val, const _Bits &shamt)
    {
      return val >> shamt.get();
    }

    constexpr _Bits sra(const _Bits &shamt) const
    {
      return apply_mask(cast_to_signed() >> shamt.get());
    }

    template <unsigned M, bool _Signed>
      requires((M != N) || (Signed != _Signed))
    constexpr _Bits sra(const _Bits<M, _Signed> &shamt) const
    {
      return apply_mask(cast_to_signed() >> shamt.get());
    }

    template <std::integral IntType>
    constexpr _Bits sra(const IntType &shamt) const
    {
      return apply_mask(cast_to_signed() >> shamt);
    }

    template <std::integral IntType>
    constexpr friend IntType sra(const IntType &val, const _Bits &shamt)
    {
      if constexpr (N > MaxNativePrecision)
      {
        if (Signed)
        {
          return (val >> shamt.get()).get_si();
        }
        else
        {
          return (val >> shamt.get()).get_ui();
        }
      }
      else
      {
        return val >> shamt.get();
      }
    }

    _Bits sra(const mpz_class &shamt) const
    {
      return apply_mask(cast_to_signed() >> shamt);
    }

    friend mpz_class sra(const mpz_class &val, const _Bits &shamt)
    {
      return val >> shamt.get();
    }

#define BITS_OP_ASSIGN(op)                     \
  template <typename T>                        \
  constexpr _Bits &operator op##=(const T & o) \
  {                                            \
    m_val = (*this op o).m_val;                \
    return *this;                              \
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
    _Bits &operator++()
    {
      m_val = apply_mask(m_val + 1);
      return *this;
    }

    // post-increment
    _Bits operator++(int)
    {
      _Bits tmp{m_val};
      m_val = apply_mask(m_val + 1);
      return tmp;
    }

    // pre-decrement. Can't add a bit here, so use carefully if overflow could
    // happen
    _Bits &operator--()
    {
      m_val = apply_mask(m_val - 1);
      return *this;
    }

    // post-increment
    _Bits operator--(int)
    {
      _Bits tmp{m_val};
      m_val = apply_mask(m_val - 1);
      return tmp;
    }

    friend std::ostream &operator<<(std::ostream &stream, const _Bits &val)
    {
      stream << val.m_val;
      return stream;
    }

    template <unsigned msb, unsigned lsb>
    constexpr _Bits<msb - lsb + 1, false> extract() const
    {
      static_assert(msb >= lsb);
      return _Bits<msb - lsb + 1, false>{m_val >> lsb}; // masking will happen in the constructor
    }

  // private:
  // If m_val is private, then _Bits cannot be used as a template parameter
  //  (Would not be 'structural'): https://en.cppreference.com/w/cpp/language/template_parameters
  // We want to be able to use it as a template parameter because templated IDL functions
  // will do so.
    StorageType m_val;
  };

  // used to translate literal strings into a Bits<N> type
  template <char... Str>
  struct BitsStr
  {
    static constexpr char str[sizeof...(Str)] = {Str...};

    static constexpr unsigned get_width(const char *str)
    {
      uint64_t val = 0;
      unsigned width = 0;
      auto len = strlen(str);
      unsigned base = 10;
      const char *ptr = str;
      if (len >= 3)
      {
        if (strncmp(str, "0x", 2) == 0)
        {
          base = 16;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 10)
      {
        uint64_t pow = 1;
        uint64_t last_val = val;
        for (int i = len - 1; i >= 0; i--)
        {
          val += (ptr[i] - '0') * pow;
          if (val < last_val)
          {
            // we overflowed; can't represent this value in 64 bits.
            // For now, we'll just return an overappoximation because
            // trying to find the width from the decimal string at compile time is tricky
            return 1 + (10 * len) / (3); // 2^3 fits in one decimal digit
          }
          last_val = val;
          pow *= 10;
        }
        width = 64 - std::countl_zero(val);
      }
      if (base == 16)
      {
        // the msb only needs enough bits to hold itself
        if (*ptr >= '0' && *ptr <= '9')
        {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'0');
        }
        else if (*ptr >= 'A' && *ptr <= 'F')
        {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'A' + (uint32_t)10);
        }
        else if (*ptr >= 'a' && *ptr <= 'f')
        {
          width += 32 - std::countl_zero(((uint32_t)*ptr) - (uint32_t)'a' + (uint32_t)10);
        }

        // the lsbs need full bits
        width += (len - 1) * 4;
      }
      return width;
    }

    static constexpr uint64_t get_val(const char *str)
    {
      uint64_t val = 0;
      auto len = strlen(str);
      unsigned base = 10;
      const char *ptr = str;
      if (len >= 3)
      {
        if (strncmp(str, "0x", 2) == 0)
        {
          base = 16;
          ptr = &str[2];
          len -= 2;
        }
      }
      if (base == 10)
      {
        // we only support base-10 literals up to 64 bits. (otherwise, it's hard to know bitwidth at compile time)
        uint64_t pow = 1;
        for (int i = len - 1; i >= 0; i--)
        {
          val += ((uint64_t)(ptr[i] - '0')) * pow;
          pow *= 10;
        }
      }
      if (base == 16)
      {
        uint64_t pow = 1;
        for (int i = len - 1; i >= 0; i--)
        {
          if (ptr[i] >= '0' && ptr[i] <= '9')
          {
            val += ((uint64_t)(ptr[i] - '0')) * pow;
          }
          else if (ptr[i] >= 'A' && ptr[i] <= 'F')
          {
            val += ((uint64_t)(ptr[i] - 'A' + 10)) * pow;
          }
          else if (ptr[i] >= 'a' && ptr[i] <= 'f')
          {
            val += ((uint64_t)(ptr[i] - 'a' + 10)) * pow;
          }
          pow *= 16;
        }
      }
      return val;
    }

    static constexpr unsigned width = get_width(str);
    static constexpr uint64_t val = get_val(str);
  };
  static_assert(BitsStr<'0', 'x', '1', '\0'>::width == 1);
  static_assert(BitsStr<'0', 'x', '2', '\0'>::width == 2);
  static_assert(BitsStr<'0', 'x', '8', '\0'>::width == 4);
  static_assert(BitsStr<'0', 'x', '1', 'f', '\0'>::width == 5);

  // be careful with negative numbers here, since literals are always unsigned
  //
  // auto b = -15_b; // b will be +1, because 15_b is only four bits, and negation loses the sign bit
  template <char... Str>
  constexpr _Bits<BitsStr<Str..., '\0'>::width, false> operator""_b()
  {
    if constexpr (BitsStr<Str..., '\0'>::width <= _Bits<BitsStr<Str..., '\0'>::width, false>::MaxNativePrecision)
    {
      return BitsStr<Str..., '\0'>::val;
    }
    else
    {
      return mpz_class{BitsStr<Str..., '\0'>::str};
    }
  }

  static_assert((0x1_b).Width == 1);
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
}

// format Bits as their underlying type when using format()
template <unsigned N, bool Signed>
  requires(N <= udb::_Bits<64, false>::MaxNativePrecision)
struct fmt::formatter<udb::_Bits<N, Signed>> : formatter<typename udb::_Bits<N, Signed>::StorageType>
{
  template <typename CONTEXT_TYPE>
  auto format(udb::_Bits<N, Signed> value, CONTEXT_TYPE &ctx) const
  {
    return fmt::formatter<typename udb::_Bits<N, Signed>::StorageType>::format(value.get(), ctx);
  }
};

template <unsigned N, bool Signed>
  requires(N > udb::_Bits<64, false>::MaxNativePrecision)
struct fmt::formatter<udb::_Bits<N, Signed>>
{
private:
  fmt::detail::dynamic_format_specs<char> specs_;

public:
  constexpr auto parse(fmt::format_parse_context &ctx) -> decltype(ctx.begin())
  {
    auto end = parse_format_specs(ctx.begin(), ctx.end(), specs_, ctx, fmt::detail::type::int_type);
    return end;
  }

  template <class FormatContext>
  auto format(const udb::_Bits<N, Signed> &c, FormatContext &ctx) -> decltype(ctx.out())
  {
    fmt::detail::handle_dynamic_spec<fmt::detail::precision_checker>(
        specs_.width, specs_.width_ref, ctx);
    int base = 10;
    std::string gmp_fmt_string = "%";
    if (specs_.fill.data()[0] == '0')
      gmp_fmt_string += "0";
    if (specs_.alt)
      gmp_fmt_string += "#";
    if (specs_.sign == fmt::sign_t::plus)
      gmp_fmt_string += "+";
    if (specs_.sign == fmt::sign_t::minus)
      gmp_fmt_string += "-";
    if (specs_.sign == fmt::sign_t::space)
      gmp_fmt_string += " ";
    if (specs_.width != 0)
      gmp_fmt_string += std::to_string(specs_.width);
    gmp_fmt_string += "Z";
    if (specs_.type == fmt::presentation_type::hex_lower)
    {
      base = 16;
      gmp_fmt_string += "x";
    }
    else if (specs_.type == fmt::presentation_type::hex_upper)
    {
      base = 16;
      gmp_fmt_string += "X";
    }
    else if (specs_.type == fmt::presentation_type::oct)
    {
      base = 8;
      gmp_fmt_string += "o";
    }
    else
    {
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

namespace std
{
  template <unsigned N, bool Signed>
  std::string to_string(const udb::_Bits<N, Signed> &i)
  {
    if constexpr (N > udb::_Bits<64, false>::MaxNativePrecision)
    {
      return i.get_str();
    }
    else
    {
      return to_string(i.get());
    }
  }
}

namespace std
{

  template <unsigned N, bool Signed>
  class numeric_limits<udb::_Bits<N, Signed>>
  {
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
    static constexpr int digits10 = N < udb::_Bits<N, Signed>::InfinitePrecision ? digits * std::log10(2) : 0;
    static constexpr int max_digits10 = 0;
    static constexpr int radix = 2;
    static constexpr int min_exponent = 0;
    static constexpr int min_exponent10 = 0;
    static constexpr int max_exponent = 0;
    static constexpr int max_exponent10 = 0;
    static constexpr bool trap = true;
    static constexpr bool tinyness_before = false;

    static consteval udb::_Bits<N, Signed> min() noexcept
    {
      if constexpr (Signed)
      {
        return -typename udb::_Bits<N, Signed>{typename udb::_Bits<N, Signed>::SignedStorageType{1} << (N - 1)};
      }
      else
      {
        return 0;
      }
    }
    static consteval udb::_Bits<N, Signed> lowest() noexcept
    {
      return min();
    }
    static consteval udb::_Bits<N, Signed> max() noexcept
    {
      if constexpr (N <= udb::_Bits<N, Signed>::MaxNativePrecision)
      {
        if (N == sizeof(typename udb::_Bits<N, Signed>::StorageType) * 8)
        {
          if (Signed)
          {
            return std::numeric_limits<typename udb::_Bits<N, Signed>::SignedStorageType>::max();
          }
          else
          {
            return std::numeric_limits<typename udb::_Bits<N, Signed>::StorageType>::max();
          }
        }
        else
        {
          if (Signed)
          {
            return (typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) - 1;
          }
          else
          {
            return (typename udb::_Bits<N, Signed>::StorageType{1} << (N)) - 1;
          }
        }
      }
      else
      {
        if (Signed)
        {
          return (typename udb::_Bits<N, Signed>::StorageType{1} << (N - 1)) - 1;
        }
        else
        {
          return (typename udb::_Bits<N, Signed>::StorageType{1} << N) - 1;
        }
      }
    }
    static consteval udb::_Bits<N, Signed> epsilon() noexcept
    {
      return 0;
    }
    static consteval udb::_Bits<N, Signed> round_error() noexcept
    {
      return 0;
    }
    static consteval udb::_Bits<N, Signed> infinity() noexcept
    {
      return 0;
    }
    static consteval udb::_Bits<N, Signed> quiet_NaN() noexcept
    {
      return 0;
    }
    static consteval udb::_Bits<N, Signed> denorm_min() noexcept
    {
      return 0;
    }
  };
}

static_assert(std::numeric_limits<udb::_Bits<8, false>>::min() == 0);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::min() == -128);
static_assert(std::numeric_limits<udb::_Bits<8, false>>::max() == 255);
static_assert(std::numeric_limits<udb::_Bits<8, true>>::max() == 127);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::min() == 0);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::min() == -256);
static_assert(std::numeric_limits<udb::_Bits<9, false>>::max() == 511);
static_assert(std::numeric_limits<udb::_Bits<9, true>>::max() == 255);

namespace udb {
  template <unsigned N>
  using Bits = _Bits<N, false>;

  template <unsigned N>
  using SignedBits = _Bits<N, true>;
}