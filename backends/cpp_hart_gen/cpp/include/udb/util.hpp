#pragma once

#include "udb/defines.hpp"
#include "udb/bits.hpp"

namespace udb {
  // extract bits from an integral type
  template <unsigned start, unsigned size, std::integral Type>
  constexpr Type extract(Type value)
  {
    static_assert(size > 0, "Must extract at least one bit");
    static_assert((start + size) <= sizeof(Type)*8, "Cannot extract more bits than type contains");

    if constexpr (size == sizeof(Type)*8) {
      return value;
    } else {
      constexpr Type mask = (static_cast<Type>(1) << size) - 1;
      return (value >> start) & mask;
    }
  }
  static_assert(extract<0,8>(0xeeff) == 0xff, "Did not extract a byte");
  static_assert(extract<8,8>(0xeeff) == 0xee, "Did not extract a byte");
  static_assert(extract<24,8>(0xccddeeffu) == 0xcc, "Did not extract a byte");
  static_assert(extract<0, 32>(0xccddeeffu) == 0xccddeeff, "Did not extract a byte");
  static_assert(extract<0,1>(0xeeff) == 0x1, "Did not extract a bit");
  static_assert(extract<8,1>(0xeeff) == 0x0, "Did not extract a bit");

  // extract bits from a Bits type
  template <unsigned start, unsigned size, unsigned bits_len>
  constexpr Bits<size> extract(const Bits<bits_len>& value)
  {
    static_assert((start + size) <= bits_len, "Cannot extract more bits than type contains");

    if constexpr (size == bits_len) {
      return value;
    } else {
      constexpr Bits<bits_len> mask = (static_cast<Bits<bits_len>>(1).template const_sll<size>()) - 1;
      return (value >> start) & mask;
    }
  }

  // extract from a bitfield member
  template <unsigned start, unsigned size, unsigned BitfieldParentSize, unsigned BitfieldMemberStart, unsigned BitfieldMemberSize>
  constexpr Bits<size> extract(const BitfieldMember<BitfieldParentSize, BitfieldMemberStart, BitfieldMemberSize>& value)
  {
    static_assert((start + size) <= (BitfieldMemberSize), "Cannot extract more bits than type contains");

    if constexpr (size == BitfieldMemberSize) {
      return value;
    } else {
      constexpr Bits<BitfieldMemberSize> mask = (static_cast<Bits<BitfieldMemberSize>>(1).template const_sll<size>()) - 1;
      return (value >> start) & mask;
    }
  }
  // extract bits, where the extraction is not known at compile time
  template <typename T>
  T extract(T value, unsigned start, unsigned size)
  {
    udb_assert((start + size) <= sizeof(T)*8, "extraction out of bound");

    if (size == sizeof(T)*8) {
      return value;
    } else {
      T mask = (static_cast<T>(1) << size) - 1;
      return (value >> start) & mask;
    }
  }

  template <unsigned MSB, unsigned LSB, unsigned T>
  constexpr Bits<T> bit_insert(const Bits<T>& target, const Bits<MSB - LSB + 1>& value)
  {
    static_assert(MSB < T, "MSB is outside target range");
    static_assert(LSB <= MSB, "LSB is greater than MSB");
    static_assert(T <= Bits<T>::MaxNativePrecision, "Multi-precision Bits is not constexpr");
    Bits<T> mask = ((Bits<1>{1}.template sll<MSB - LSB + 1>()) - 1).template sll<LSB>();
    return (target & ~mask) | ((value.template sll<LSB>()) & mask);
  }

  static_assert(bit_insert<0, 0, 32>(0, 1).get() == 0x1, "Did not insert bit");
  static_assert(bit_insert<1, 1, 32>(0, 1) == 0x2, "Did not insert bit");
  static_assert(bit_insert<8, 8, 32>(0, 1) == 0x100, "Did not insert bit");
  static_assert(bit_insert<15, 15, 32>(0, 1) == 0x8000, "Did not insert bit");
  static_assert(bit_insert<31, 31, 32>(0, 1).get() == 0x80000000, "Did not insert bit");
  static_assert(bit_insert<3, 0, 32>(0, 0xa) == 0xa, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0, 0xa) == 0xa0, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xf, 0xa) == 0xaf, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xff, 0xa) == 0xaf, "Did not insert nibble");

  template <unsigned T, unsigned M, unsigned L, unsigned V>
  void bit_insert(Bits<T>& target, const Bits<M>& msb, const Bits<L>& lsb, const Bits<V>& value)
  {
    Bits<T> mask = ((Bits<T + 1>{1} << msb) - 1) << lsb;
    target = (target & ~mask) | ((Bits<T>{value} << lsb) & mask);
  }

  template <unsigned N, unsigned M>
  constexpr Bits<N*M> replicate(const Bits<M>& value)
  {
    static_assert(N > 0, "Must replicate at least once");
    static_assert(M < BitsMaxNativePrecision, "Please don't replicate multiprecision numbers ;(");

    Bits<N*M> result = value;
    for (unsigned i=1; i<N; i++) {
      result |= value << (i*M);
    }
    return result;
  }

  template <unsigned M, typename T>
  constexpr Bits<BitsInfinitePrecision> replicate(const Bits<M>& value, const T& N)
  {
    udb_assert(N > 0, "Must replicate at least once");
    static_assert(M < BitsMaxNativePrecision, "Please don't replicate multiprecision numbers ;(");

    Bits<BitsInfinitePrecision> result = value;
    for (unsigned i=1; i<N; i++) {
      result |= value << (i*M);
    }
    return result;
  }


  template <unsigned FirstExtendedBit, unsigned ResultWidth, unsigned InputWidth>
  constexpr Bits<ResultWidth> sign_extend(const Bits<InputWidth>& value) {
    bool zero = (value & (static_cast<Bits<InputWidth>>(1).template sll<FirstExtendedBit - 1>())) == 0;
    constexpr Bits<ResultWidth> zero_mask = static_cast<Bits<InputWidth>>(1).template sll<FirstExtendedBit>() - 1;
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
    static constexpr unsigned Width = BitsType::Width + ConcatWidth<BitsTypes...>::Width;
  };

  template <>
  struct ConcatWidth<> {
    static constexpr unsigned Width = 0;
  };

  template <typename BitsType, typename... BitsTypes>
  constexpr Bits<ConcatWidth<BitsType, BitsTypes...>::Width> __concat(const BitsType& a, const BitsTypes&... bits) {
    if constexpr (sizeof...(BitsTypes) == 0) {
      return a;
    } else {
      return (Bits<ConcatWidth<BitsType, BitsTypes...>::Width>{a} << ConcatWidth<BitsTypes...>::Width) | __concat(bits...);
    }
  }

  template <typename... BitsTypes>
  constexpr Bits<ConcatWidth<BitsTypes...>::Width> concat(BitsTypes... bits) {
    return __concat(bits...);
  }

  static_assert(std::is_same_v<decltype(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3))), Bits<12>>);
  static_assert(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3)) == Bits<12>(0x123));
}
