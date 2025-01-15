#pragma once

// #include <boost/multiprecision/cpp_int.hpp>

#include <cmath>
#include <cstdint>
#include <bit>
#include <concepts>
#include <string>
#include <type_traits>
#include <limits>
#include <gmpxx.h>

#include <udb/defines.hpp>
#include <udb/bits.hpp>

// extern "C" {
// #include "softfloat.h"
// }

namespace udb {

  // empty struct used as the parent of any user-defined enum
  // we use this to identify enum types at compile time
  struct Enum { };

  template<unsigned N>
  struct FixedString {
      char buf[N + 1]{};
      constexpr FixedString(char const* s) {
          for (unsigned i = 0; i != N; ++i) buf[i] = s[i];
      }
      constexpr operator char const*() const { return buf; }
  };
  template<unsigned N> FixedString(char const (&)[N]) -> FixedString<N - 1>;

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

  template<unsigned N>
  using Bits = _Bits<N, false>;

    // static_assert(static_cast<uint64_t>(_Bits<1023> { 5 }) == 5);

}




namespace udb {
  template <unsigned Size>
  class Bitfield;

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  class BitfieldMember {
    public:
    static constexpr unsigned Width = Size;

    BitfieldMember(Bitfield<ParentSize>& parent)
      : m_parent(parent)
    {}
    BitfieldMember(const BitfieldMember& other)
      : m_parent(other.m_parent)
    {}

    static constexpr Bits<Size> MaximumValue = (Bits<1>(1).template sll<Size>()) - 1;
    static constexpr Bits<ParentSize> Mask = MaximumValue.template sll<Start>();

    template <unsigned N>
      requires (N >= Size)
    operator Bits<N>() const;

    operator PossiblyUndefinedBits() const;

    bool operator!() const {
      return !static_cast<Bits<Size>>(*this).get();
    }

    template <unsigned N, bool Signed>
    BitfieldMember& operator=(const _Bits<N, Signed>& value);

    template <std::integral Type>
    bool operator==(const Type& other) const { return other == static_cast<Bits<Size>>(*this); }

    template <unsigned N, bool Signed>
    bool operator==(const _Bits<N, Signed>& other) const { return other == static_cast<Bits<Size>>(*this); }

    template <unsigned N, bool Signed>
    bool operator>(const _Bits<N, Signed>& other) const { return static_cast<Bits<Size>>(*this) > other; }

    template <unsigned N, bool Signed>
    bool operator>=(const _Bits<N, Signed>& other) const { return static_cast<Bits<Size>>(*this) >= other; }

    template <unsigned N, bool Signed>
    bool operator<=(const _Bits<N, Signed>& other) const { return static_cast<Bits<Size>>(*this) <= other; }

    template <unsigned OtherParentSize, unsigned OtherStart, unsigned OtherSize>
    bool operator<(const BitfieldMember<OtherParentSize, OtherStart, OtherSize>& other) const { return static_cast<Bits<Size>>(*this) > static_cast<Bits<OtherSize>>(*this); }



    template <unsigned N, bool Signed>
    Bits<Size> operator>>(const _Bits<N, Signed>& shamt) const { return static_cast<Bits<Size>>(*this) >> shamt; }
    template <typename T>
      requires (std::integral<T>)
    Bits<Size> operator>>(const T& shamt) const { return static_cast<Bits<Size>>(*this) >> shamt; }


    template <unsigned N, bool Signed>
    Bits<Size> operator&(const _Bits<N, Signed>& other) const { return static_cast<Bits<Size>>(*this) & other; }

    Bits<Bits<Size>::InfinitePrecision> operator<<(const int& shamt) const { return static_cast<Bits<Size>>(*this) << shamt; }

    template <unsigned Shamt>
    Bits<Size + Shamt> sll() const { return static_cast<Bits<Size>>(*this).template sll<Shamt>(); }

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
    template <std::integral Type>
    Bitfield& operator=(const Type& value) {
      m_value = value;
      return *this;
    }
    operator Bits<Size>&() { return m_value; }
    operator Bits<Size>() const { return m_value; }

    protected:
    Bits<Size> m_value;
  };

  static_assert(std::is_copy_constructible_v<BitfieldMember<64, 0, 1>>);

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N>
    requires (N >= Size)
  BitfieldMember<ParentSize, Start, Size>::template operator Bits<N>() const
  {
    return (static_cast<Bits<ParentSize>>(m_parent) >> Start) & MaximumValue;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  BitfieldMember<ParentSize, Start, Size>::operator PossiblyUndefinedBits() const
  {
    return (static_cast<Bits<ParentSize>>(m_parent) >> Start) & MaximumValue;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N, bool Signed>
  BitfieldMember<ParentSize, Start, Size>& BitfieldMember<ParentSize, Start, Size>::template operator=(const _Bits<N, Signed>& value)
  {
    m_parent = (static_cast<Bits<ParentSize>>(m_parent) & ~Mask) | ((value.template sll<Size>()) & Mask);
    return *this;
  }
}
