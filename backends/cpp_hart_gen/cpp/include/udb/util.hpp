#pragma once

#include <concepts>

#include "udb/bits.hpp"
#include "udb/defines.hpp"

namespace udb {


  static_assert((0xeeff_b).extract<7, 0>() == 0xff_b, "Did not extract a byte");
  static_assert((0xeeff_b).extract<15, 8>() == 0xee_b, "Did not extract a byte");
  static_assert((0xccddeeff_b).extract<31, 24>() == 0xcc_b, "Did not extract a byte");
  static_assert((0xccddeeff_b).extract<31, 0>() == 0xccddeeff_b,
                "Did not extract entire word");
  static_assert((0xeeff_b).extract<0, 0>() == 0x1_b, "Did not extract a bit");
  static_assert((0xeeff_b).extract<8, 8>() == 0x0_b, "Did not extract a bit");

  template <unsigned MSB, unsigned LSB, unsigned TargetN,
    template <unsigned, bool> class TargetBitsType, unsigned ArgN, bool ArgSign,
    template <unsigned, bool> class ValueBitsType>
    requires (ValueBitsType<MSB - LSB + 1, false>::IsABits)
  constexpr TargetBitsType<TargetN, ArgSign> bit_insert(
    const TargetBitsType<ArgN, ArgSign> &target,
    const ValueBitsType<MSB - LSB + 1, false> &value) {
    static_assert(MSB < TargetN, "MSB is outside target range");
    static_assert(LSB <= MSB, "LSB is greater than MSB");
    static_assert(TargetN <= BitsMaxNativePrecision,
                  "Multi-precision Bits is not constexpr");
    TargetBitsType<TargetN, ArgSign> mask =
        ((Bits<1>{1}.template widening_sll<MSB - LSB + 1>()) - 1_b).template widening_sll<LSB>();
    return (target & ~mask) | ((value.template widening_sll<LSB>()) & mask);
  }

  static_assert(bit_insert<0, 0, 32>(0x000000000_b, 1_b) == 0x1_b, "Did not insert bit");
  static_assert(bit_insert<1, 1, 32>(0_b, 1_b) == 0x2_b, "Did not insert bit");
  static_assert(bit_insert<8, 8, 32>(0_b, 1_b) == 0x100_b, "Did not insert bit");
  static_assert(bit_insert<15, 15, 32>(0_b, 1_b) == 0x8000_b, "Did not insert bit");
  static_assert(bit_insert<31, 31, 32>(0_b, 1_b) == 0x80000000_b, "Did not insert bit");
  static_assert(bit_insert<3, 0, 32>(0_b, 0xa_b) == 0xa_b, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0_b, 0xa_b) == 0xa0_b, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xf_b, 0xa_b) == 0xaf_b, "Did not insert nibble");
  static_assert(bit_insert<7, 4, 32>(0xff_b, 0xa_b) == 0xaf_b, "Did not insert nibble");

  template <
    template <unsigned, bool> class BitsClass, unsigned T, bool Signed,
    typename MsbType, typename LsbType, typename ValueType
  >
  void bit_insert(BitsClass<T, Signed> &target, const MsbType &msb, const LsbType &lsb,
                  const ValueType &value) {
    BitsClass<T, Signed> mask = ((BitsClass<T + 1, Signed>{1_b} << msb) - 1_b) << lsb;
    target = (target & ~mask) | ((BitsClass<T, Signed>{value} << lsb) & mask);
  }

  template <unsigned FirstExtendedBit, unsigned ResultWidth,
            unsigned InputWidth>
  constexpr Bits<ResultWidth> sign_extend(const Bits<InputWidth> &value) {
    bool zero = (value & (static_cast<Bits<InputWidth>>(1)
                              .template widening_sll<FirstExtendedBit - 1>())) == 0_b;
    constexpr Bits<ResultWidth> zero_mask =
        static_cast<Bits<InputWidth>>(1).template widening_sll<FirstExtendedBit>() - 1_b;
    if (zero) {
      return Bits<ResultWidth>(value) & zero_mask;
    } else {
      return Bits<ResultWidth>(value) | ~zero_mask;
    }
  }

  static_assert(sign_extend<5, 8, 8>(0x10_b) == 0xf0_b);
  static_assert(sign_extend<5, 16, 8>(0x10_b) == 0xfff0_b);
  static_assert(sign_extend<6, 8, 8>(0x10_b) == 0x10_b);
  static_assert(sign_extend<6, 16, 8>(0x10_b) == 0x10_b);

  template <typename... BitsTypes>
  struct ConcatWidth;

  template <typename BitsType, typename... BitsTypes>
    requires (!BitsType::RuntimeWidth && !(BitsTypes::RuntimeWidth || ...))
  struct ConcatWidth<BitsType, BitsTypes...> {
    static constexpr unsigned Width =
        BitsType::width() + ConcatWidth<BitsTypes...>::Width;
  };

  template <typename BitsType, typename... BitsTypes>
    requires (BitsType::RuntimeWidth || (BitsTypes::RuntimeWidth || ...))
  struct ConcatWidth<BitsType, BitsTypes...> {
    static constexpr unsigned Width = 1; // should never be used, but need it defined since the compiler tries out every path of std::conditional (in ConcatReturnType)
  };

  template <>
  struct ConcatWidth<> {
    static constexpr unsigned Width = 0;
  };

  // template <typename BitsType, typename... BitsTypes>
  //   requires(((BitsTypes::width() != BitsInfinitePrecision) && (BitsTypes::PossiblyUnknown == false)) && ...)
  // constexpr Bits<ConcatWidth<BitsType, BitsTypes...>::Width> __concat(
  //     const BitsType &a, const BitsTypes &...bits) {
  //   if constexpr (sizeof...(BitsTypes) == 0) {
  //     return a;
  //   } else {
  //     return (Bits<ConcatWidth<BitsType, BitsTypes...>::Width>{a}
  //             << Bits<32>{ConcatWidth<BitsTypes...>::Width}) |
  //            __concat(bits...);
  //   }
  // }

  // template <typename... BitsTypes>
  //   requires(((BitsTypes::width() != BitsInfinitePrecision) && (BitsTypes::PossiblyUnknown == false)) && ...)
  // constexpr Bits<ConcatWidth<BitsTypes...>::Width> concat(BitsTypes... bits) {
  //   return __concat(bits...);
  // }

  // template <typename BitsType, typename... BitsTypes>
  //   requires (
  //     (BitsType::width() != BitsInfinitePrecision) &&
  //     ((BitsTypes::width() != BitsInfinitePrecision) && ...) &&
  //     ((BitsType::PossiblyUnknown == true) ||((BitsTypes::PossiblyUnknown == true) || ...))
  //   )
  // constexpr PossiblyUnknownBits<ConcatWidth<BitsType, BitsTypes...>::Width> __unknown_concat(
  //     const BitsType &a, const BitsTypes &...bits) {
  //   if constexpr (sizeof...(BitsTypes) == 0) {
  //     return a;
  //   } else {
  //     return (PossiblyUnknownBits<ConcatWidth<BitsType, BitsTypes...>::Width>{a}
  //             << Bits<ConcatWidth<BitsTypes...>::Width>(ConcatWidth<BitsTypes...>::Width)) |
  //           __unknown_concat(bits...);
  //   }
  // }

  // template <typename... BitsTypes>
  //   requires(
  //     ((BitsTypes::width() != BitsInfinitePrecision) && ...) &&
  //     ((BitsTypes::PossiblyUnknown == true) || ...)
  //   )
  // constexpr PossiblyUnknownBits<ConcatWidth<BitsTypes...>::Width> concat(BitsTypes... bits) {
  //   return __unknown_concat(bits...);
  // }

  // template <typename BitsType, typename... BitsTypes>
  // RuntimeBits<> __runtime_concat(const BitsType &a, const BitsTypes &...bits) {
  //   if constexpr (sizeof...(BitsTypes) == 0) {
  //     return a;
  //   } else {
  //     auto shamt = (bits.width() + ...);
  //     return (RuntimeBits{a} << shamt) | __runtime_concat(bits...);
  //   }
  // }

  // template <typename... BitsTypes>
  //   requires((std::same_as<BitsTypes, RuntimeBits<>> || ...))
  // RuntimeBits<> concat(BitsTypes... bits) {
  //   return __runtime_concat(bits...);
  // }

  // static_assert(
  //     std::is_same_v<decltype(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3))),
  //                    Bits<12>>);
  // static_assert(concat(Bits<4>{1}, Bits<4>(2), Bits<4>(3)) == Bits<12>(0x123));
  // static_assert(
  //   std::is_same_v<decltype(concat(Bits<4>{1}, PossiblyUnknownBits<4>(2_b), Bits<4>(3))),
  //                  PossiblyUnknownBits<12>>);

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

template <typename... BitsTypes>
struct ConcatReturnType {
  using Type = std::conditional_t<
    (((BitsTypes::RuntimeWidth == false) && (BitsTypes::IsABits) && (BitsTypes::PossiblyUnknown == false)) && ...),
    _Bits<ConcatWidth<BitsTypes...>::Width, false>,
    std::conditional_t<
      (((BitsTypes::IsABits) && (BitsTypes::PossiblyUnknown == false)) && ...),
      UnboundRuntimeBits,
      std::conditional_t<
        (((BitsTypes::IsABits) && (BitsTypes::RuntimeWidth == false)) && ...),
        _PossiblyUnknownBits<ConcatWidth<BitsTypes...>::Width, false>,
        UnboundPossiblyUnknownRuntimeBits
      >
    >
  >;
};

template <typename... BitsTypes>
using concat_return_t = ConcatReturnType<BitsTypes...>::Type;


template <typename BitsType, typename... BitsTypes>
constexpr unsigned __concat_width(const BitsType& a, const BitsTypes &...bits)
{
  if constexpr (sizeof...(BitsTypes) == 0) {
    return a.width();
  } else {
    return a.width() + __concat_width(bits...);
  }
}

template <typename BitsType, typename... BitsTypes>
consteval unsigned __concat_width_static()
{
  if constexpr (sizeof...(BitsTypes) == 0) {
    return BitsType::width();
  } else {
    return BitsType::width() + __concat_width_static<BitsTypes...>();
  }
}

  template <typename ReturnType, typename BitsType, typename... BitsTypes>
  constexpr ReturnType __concat(
      const BitsType &a, const BitsTypes &...bits) {
    if constexpr (sizeof...(BitsTypes) == 0) {
      return a;
    } else {
      if constexpr (ReturnType::RuntimeWidth) {
        unsigned shamt = __concat_width(bits...);
        return a.widening_sll(Bits<64>{shamt}) | __concat<concat_return_t<BitsTypes...>>(bits...);
      } else {
        return
          a.template widening_sll<__concat_width_static<BitsTypes...>()>() | \
            __concat<concat_return_t<BitsTypes...>>(bits...);
      }
    }
  }

  template <typename... BitsTypes>
  constexpr concat_return_t<BitsTypes...> concat(BitsTypes... bits) {
    return __concat<concat_return_t<BitsTypes...>>(bits...);
  }

}  // namespace udb
