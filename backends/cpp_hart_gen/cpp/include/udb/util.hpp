#pragma once

#include <concepts>

#include "udb/bits.hpp"
#include "udb/defines.hpp"
#include "udb/xregister.hpp"

namespace udb {

  // extract bits from an integral type
  template <unsigned start, unsigned size, std::integral Type>
  constexpr Bits<size> extract(Type value) {
    static_assert(size > 0, "Must extract at least one bit");
    static_assert((start + size) <= sizeof(Type) * 8,
                  "Cannot extract more bits than type contains");

    if constexpr (size == sizeof(Type) * 8) {
      return value;
    } else {
      constexpr Type mask = (static_cast<Type>(1) << size) - 1;
      return (value >> start) & mask;
    }
  }
  static_assert(extract<0, 8>(0xeeff) == 0xff, "Did not extract a byte");
  static_assert(extract<8, 8>(0xeeff) == 0xee, "Did not extract a byte");
  static_assert(extract<24, 8>(0xccddeeffu) == 0xcc, "Did not extract a byte");
  static_assert(extract<0, 32>(0xccddeeffu) == 0xccddeeff,
                "Did not extract a byte");
  static_assert(extract<0, 1>(0xeeff) == 0x1, "Did not extract a bit");
  static_assert(extract<8, 1>(0xeeff) == 0x0, "Did not extract a bit");

  // extract bits from a Bits type
  template <unsigned START, unsigned SIZE, unsigned BITS_LEN>
    requires(BITS_LEN <= BitsMaxNativePrecision)
  constexpr Bits<SIZE> extract(const Bits<BITS_LEN> &value) {
    static_assert((START + SIZE) <= BITS_LEN,
                  "Cannot extract more bits than type contains");

    if constexpr (SIZE == BITS_LEN) {
      return value;
    } else {
      constexpr Bits<BITS_LEN> mask =
          (static_cast<Bits<BITS_LEN>>(1).template sll<SIZE>()) - 1;
      return (value >> START) & mask;
    }
  }

  // extract bits from an integral type
  template <unsigned START, unsigned SIZE, unsigned BITS_LEN,
            std::integral IntType>
    requires(BITS_LEN <= BitsMaxNativePrecision)
  constexpr Bits<SIZE> extract(const IntType &value) {
    static_assert((START + SIZE) <= BITS_LEN,
                  "Cannot extract more bits than type contains");

    if constexpr (SIZE == BITS_LEN) {
      return value;
    } else {
      constexpr Bits<BITS_LEN> mask =
          (static_cast<Bits<BITS_LEN>>(1).template sll<SIZE>()) - 1;
      return (value >> START) & mask;
    }
  }

  // extract bits from a PossiblyUnknownBits type
  template <unsigned START, unsigned SIZE, unsigned BITS_LEN>
    requires(BITS_LEN <= BitsMaxNativePrecision)
  constexpr PossiblyUnknownBits<SIZE> extract(
      const PossiblyUnknownBits<BITS_LEN> &value) {
    static_assert((START + SIZE) <= BITS_LEN,
                  "Cannot extract more bits than type contains");

    if constexpr (SIZE == BITS_LEN) {
      return value;
    } else {
      constexpr Bits<BITS_LEN> mask =
          (static_cast<Bits<BITS_LEN>>(1).template sll<SIZE>()) - 1;
      return (value >> START) & mask;
    }
  }

  template <unsigned START, unsigned SIZE, unsigned BITS_LEN>
    requires(BITS_LEN > BitsMaxNativePrecision)
  Bits<SIZE> extract(const Bits<BITS_LEN> &value) {
    static_assert((START + SIZE) <= BITS_LEN,
                  "Cannot extract more bits than type contains");

    if constexpr (SIZE == BITS_LEN) {
      return value;
    } else {
      Bits<BITS_LEN> mask =
          (static_cast<Bits<BITS_LEN>>(1).template sll<SIZE>()) - 1;
      return (value >> START) & mask;
    }
  }

  template <unsigned START, unsigned SIZE, unsigned MAX_BITS_LEN, bool SIGNED>
  Bits<SIZE> extract(const _RuntimeBits<MAX_BITS_LEN, SIGNED> &value) {
    static_assert((START + SIZE) <= MAX_BITS_LEN,
                  "Cannot extract more bits than type contains");
    if (value.width_known()) {
      udb_assert((START + SIZE) <= value.width(),
                 "Cannot extract more bits than type contains");
    }

    if (value.width_known() && (SIZE == value.width())) {
      return value;
    } else {
      Bits<MAX_BITS_LEN> mask =
          (static_cast<Bits<MAX_BITS_LEN>>(1).template sll<SIZE>()) - 1;
      return (value >> START) & mask;
    }
  }

  // extract bits from an XRegister type
  template <unsigned start, unsigned size, unsigned XLEN>
  constexpr Bits<size> extract(const XRegister<XLEN> &value) {
    static_assert((start + size) <= XLEN,
                  "Cannot extract more bits than type contains");

    if constexpr (size == XLEN) {
      return value;
    } else {
      constexpr Bits<XLEN> mask =
          (static_cast<Bits<XLEN>>(1).template sll<size>()) - 1;
      return (value >> start) & mask;
    }
  }

  // extract from a bitfield member
  template <unsigned start, unsigned size, unsigned BitfieldParentSize,
            unsigned BitfieldMemberStart, unsigned BitfieldMemberSize>
  constexpr Bits<size> extract(
      const BitfieldMember<BitfieldParentSize, BitfieldMemberStart,
                           BitfieldMemberSize> &value) {
    static_assert((start + size) <= (BitfieldMemberSize),
                  "Cannot extract more bits than type contains");

    if constexpr (size == BitfieldMemberSize) {
      return value;
    } else {
      constexpr Bits<BitfieldMemberSize> mask =
          (static_cast<Bits<BitfieldMemberSize>>(1).template sll<size>()) - 1;
      return (value >> start) & mask;
    }
  }

  // extract bits, where the extraction is not known at compile time
  template <typename ValueType, typename StartType, typename SizeType>
    requires((std::integral<ValueType> || ValueType::IsABits) &&
             (std::integral<StartType> || StartType::IsABits) &&
             (std::integral<SizeType> || SizeType::IsABits))
  RuntimeBits extract(const ValueType &value, const StartType &start,
                      const SizeType &size) {
    udb_assert((start + size) <= sizeof(ValueType) * 8,
               "extraction out of bound");

    if (size == sizeof(ValueType) * 8) {
      return {value, size};
    } else {
      ValueType mask = (static_cast<ValueType>(1) << size) - 1;
      return {(value >> start) & mask, size};
    }
  }

  template <unsigned P, unsigned N, unsigned M, typename StartType,
            typename SizeType>
  Bits<BitfieldMember<P, N, M>::Width> extract(
      const BitfieldMember<P, N, M> &value, const StartType &start,
      const SizeType &size) {
    udb_assert((start + size) <= (BitfieldMember<P, N, M>::Width),
               "extraction out of bound");

    if (size == BitfieldMember<P, N, M>::Width) {
      return static_cast<const Bits<BitfieldMember<P, N, M>::Width>>(value);
    } else {
      if constexpr (BitfieldMember<P, N, M>::Width < 64) {
        uint64_t mask = (1ull << size) - 1;
        return (value >> start) & mask;
      } else {
        Bits<BitfieldMember<P, N, M>::Width> mask =
            (static_cast<Bits<BitfieldMember<P, N, M>::Width>>(1) << size) - 1;
        return (value >> start) & mask;
      }
    }
  }

  template <unsigned MSB, unsigned LSB, unsigned T>
  constexpr Bits<T> bit_insert(const Bits<T> &target,
                               const Bits<MSB - LSB + 1> &value) {
    static_assert(MSB < T, "MSB is outside target range");
    static_assert(LSB <= MSB, "LSB is greater than MSB");
    static_assert(T <= Bits<T>::MaxNativePrecision,
                  "Multi-precision Bits is not constexpr");
    Bits<T> mask =
        ((Bits<1>{1}.template sll<MSB - LSB + 1>()) - 1).template sll<LSB>();
    return (target & ~mask) | ((value.template sll<LSB>()) & mask);
  }

  static_assert(bit_insert<0, 0, 32>(0, 1).get() == 0x1, "Did not insert bit");
  static_assert(bit_insert<1, 1, 32>(0, 1) == 0x2, "Did not insert bit");
  static_assert(bit_insert<8, 8, 32>(0, 1) == 0x100, "Did not insert bit");
  static_assert(bit_insert<15, 15, 32>(0, 1) == 0x8000, "Did not insert bit");
  static_assert(bit_insert<31, 31, 32>(0, 1).get() == 0x80000000,
                "Did not insert bit");
  static_assert(bit_insert<3, 0, 32>(0, 0xa) == 0xa, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0, 0xa) == 0xa0, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xf, 0xa) == 0xaf,
                "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xff, 0xa) == 0xaf,
                "Did not insert nibble");

  template <unsigned T, typename MsbType, typename LsbType, typename ValueType>
  void bit_insert(Bits<T> &target, const MsbType &msb, const LsbType &lsb,
                  const ValueType &value) {
    Bits<T> mask = ((Bits<T + 1>{1} << msb) - 1) << lsb;
    target = (target & ~mask) | ((Bits<T>{value} << lsb) & mask);
  }

  template <unsigned N, unsigned M>
  constexpr Bits<N * M> replicate(const Bits<M> &_value) {
    static_assert(N > 0, "Must replicate at least once");
    static_assert(M < BitsMaxNativePrecision,
                  "Please don't replicate multiprecision numbers ;(");

    Bits<N * M> value = _value;
    Bits<N * M> result = value;
    for (unsigned i = 1; i < N; i++) {
      result |= value << (i * M);
    }
    return result;
  }

  template <unsigned M, typename T>
  constexpr RuntimeBits replicate(const Bits<M> &_value, const T &N) {
    udb_assert(N > 0, "Must replicate at least once");
    static_assert(M < BitsMaxNativePrecision,
                  "Please don't replicate multiprecision numbers ;(");

    Bits<BitsInfinitePrecision> value = _value;
    Bits<BitsInfinitePrecision> result = value;
    for (unsigned i = 1; i < N; i++) {
      result |= value << (i * M);
    }
    return {result, M * N};
  }

  template <unsigned MaxN, bool Signed, typename T>
  constexpr RuntimeBits replicate(const _RuntimeBits<MaxN, Signed> &_value,
                                  const T &N) {
    udb_assert(N > 0, "Must replicate at least once");

    RuntimeBits value{_value.value(), _value.width() * N};
    RuntimeBits result{value.value(), value.width() * N};
    for (unsigned i = 1; i < N; i++) {
      result |= value.value() << (i * value.width());
    }
    return result;
  }

  template <unsigned FirstExtendedBit, unsigned ResultWidth,
            unsigned InputWidth>
  constexpr Bits<ResultWidth> sign_extend(const Bits<InputWidth> &value) {
    bool zero = (value & (static_cast<Bits<InputWidth>>(1)
                              .template sll<FirstExtendedBit - 1>())) == 0;
    constexpr Bits<ResultWidth> zero_mask =
        static_cast<Bits<InputWidth>>(1).template sll<FirstExtendedBit>() - 1;
    if (zero) {
      return Bits<ResultWidth>(value) & zero_mask;
    } else {
      return Bits<ResultWidth>(value) | ~zero_mask;
    }
  }

  static_assert(sign_extend<5, 8, 8>(0x10).get() == 0xf0);
  static_assert(sign_extend<5, 16, 8>(0x10).get() == 0xfff0);
  static_assert(sign_extend<6, 8, 8>(0x10).get() == 0x10);
  static_assert(sign_extend<6, 16, 8>(0x10).get() == 0x10);

  template <typename... BitsTypes>
  struct ConcatWidth;

  template <typename BitsType, typename... BitsTypes>
  struct ConcatWidth<BitsType, BitsTypes...> {
    static constexpr unsigned Width =
        BitsType::Width + ConcatWidth<BitsTypes...>::Width;
  };

  template <>
  struct ConcatWidth<> {
    static constexpr unsigned Width = 0;
  };

  template <typename BitsType, typename... BitsTypes>
  constexpr Bits<ConcatWidth<BitsType, BitsTypes...>::Width> __concat(
      const BitsType &a, const BitsTypes &...bits) {
    if constexpr (sizeof...(BitsTypes) == 0) {
      return a;
    } else {
      return (Bits<ConcatWidth<BitsType, BitsTypes...>::Width>{a}
              << ConcatWidth<BitsTypes...>::Width) |
             __concat(bits...);
    }
  }

  template <typename... BitsTypes>
    requires((BitsTypes::Width != BitsInfinitePrecision) && ...)
  constexpr Bits<ConcatWidth<BitsTypes...>::Width> concat(BitsTypes... bits) {
    return __concat(bits...);
  }

  template <typename BitsType, typename... BitsTypes>
  RuntimeBits __runtime_concat(const BitsType &a, const BitsTypes &...bits) {
    if constexpr (sizeof...(BitsTypes) == 0) {
      return a;
    } else {
      auto shamt = (bits.width() + ...);
      return (RuntimeBits{a} << shamt) | __runtime_concat(bits...);
    }
  }

  template <typename... BitsTypes>
    requires((std::same_as<BitsTypes, RuntimeBits> || ...))
  RuntimeBits concat(BitsTypes... bits) {
    return __runtime_concat(bits...);
  }

  static_assert(
      std::is_same_v<decltype(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3))),
                     Bits<12>>);
  static_assert(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3)) == Bits<12>(0x123));

  template <unsigned N>
  static consteval bool is_power_of_2() {
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
}  // namespace udb
