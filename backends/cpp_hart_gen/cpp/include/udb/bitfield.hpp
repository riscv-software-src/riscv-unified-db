#pragma once

#include <gmpxx.h>

#include <bit>
#include <cmath>
#include <concepts>
#include <cstdint>
#include <limits>
#include <string>
#include <type_traits>
#include <udb/bits.hpp>
#include <udb/defines.hpp>

namespace udb {

  using uint128_t = unsigned __int128;
  using int128_t = __int128;

  struct __not_impl_type {
    constexpr __not_impl_type() = default;
    constexpr explicit __not_impl_type(const __not_impl_type &o) {}

    template <typename T, typename... Args>
      requires(!std::same_as<T, __not_impl_type>)
    constexpr __not_impl_type(T a, Args... args) {}

    template <typename T>
      requires(!std::convertible_to<T, __not_impl_type>)
    constexpr  // required
               // since C++14
        void
        operator=(T &&) const noexcept {}

    template <typename T>
    constexpr  // required since C++14
        bool
        operator==(T &&) const noexcept {
      return false;
    }
  };

  template <unsigned N>
  using Bits = _Bits<N, false>;

  // static_assert(static_cast<uint64_t>(_Bits<1023> { 5 }) == 5);

}  // namespace udb

namespace udb {
  template <unsigned Size>
  class Bitfield;

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  class BitfieldMember {
   public:
    static constexpr unsigned Width = Size;

    template <unsigned _Size>
    using BitsType = PossiblyUnknownBits<_Size>;

    explicit BitfieldMember(Bitfield<ParentSize> &parent) : m_parent(parent) {}
    explicit BitfieldMember(const BitfieldMember &other) : m_parent(other.m_parent) {}

    static constexpr Bits<Size> MaximumValue =
        (Bits<1>(1).template widening_sll<Size>()) - 1_b;
    static constexpr Bits<ParentSize> Mask = MaximumValue.template widening_sll<Start>();

    template <template <unsigned, bool> class BitsClass, unsigned N, bool Signed>
      requires ((N >= Size) && (BitsClass<N, Signed>::IsABits))
    operator BitsClass<N, Signed>() const;

    Bits<Size>::StorageType get() const { return this.operator BitsType<Size>().get(); }

    bool operator!() const { return !static_cast<BitsType<Size>>(*this).get(); }

    template <unsigned N>
    BitfieldMember &operator=(const BitsType<N> &value);

    BitfieldMember &operator=(const BitfieldMember &other);

    template <typename OtherType>
    bool operator==(const OtherType &other) const {
      return other == static_cast<BitsType<Size>>(*this);
    }

    template <typename OtherType>
    bool operator>(const OtherType &other) const {
      return static_cast<BitsType<Size>>(*this) > other;
    }

    template <typename OtherType>
    friend bool operator<(const OtherType &lhs,
                          const BitfieldMember &rhs);

    template <typename OtherType>
    bool operator>=(const OtherType &other) const {
      return static_cast<BitsType<Size>>(*this) >= other;
    }

    template <typename OtherType>
    bool operator<=(const OtherType &other) const {
      return static_cast<BitsType<Size>>(*this) <= other;
    }

    template <unsigned OtherParentSize, unsigned OtherStart, unsigned OtherSize>
    bool operator<(const BitfieldMember<OtherParentSize, OtherStart, OtherSize>
                       &other) const {
      return static_cast<BitsType<Size>>(*this) >
             static_cast<typename BitfieldMember<OtherParentSize, OtherStart, OtherSize>::BitsType<OtherSize>>(*this);
    }

    template <typename OtherType>
    Bits<Size> operator>>(const OtherType &shamt) const {
      return static_cast<BitsType<Size>>(*this) >> Bits<Size>(shamt);
    }

    template <typename OtherType>
    Bits<Size> operator&(const OtherType &other) const {
      return static_cast<BitsType<Size>>(*this) & Bits<Size>(other);
    }

    BitsType<Bits<Size>::InfinitePrecision> operator<<(const int &shamt) const {
      return static_cast<BitsType<Size>>(*this) << shamt;
    }

    template <unsigned Shamt>
    BitsType<Size + Shamt> sll() const {
      return static_cast<BitsType<Size>>(*this).template sll<Shamt>();
    }

   private:
    Bitfield<ParentSize> &m_parent;
  };

  template <unsigned Size>
  class Bitfield {
   public:

    template <unsigned _Size>
    using BitsType = PossiblyUnknownBits<_Size>;

    Bitfield() = default;

    template <template <unsigned, bool> class OtherBitsType, unsigned N, bool Signed>
    explicit Bitfield(const OtherBitsType<N, Signed> &value) : m_value(value) {}

    Bitfield &operator=(const BitsType<Size> &value) {
      m_value = value;
      return *this;
    }
    template <std::integral Type>
    Bitfield &operator=(const Type &value) {
      m_value = value;
      return *this;
    }
    operator BitsType<Size> &() { return m_value; }
    operator BitsType<Size>() const { return m_value; }

   protected:
    BitsType<Size> m_value;
  };

  static_assert(std::is_copy_constructible_v<BitfieldMember<64, 0, 1>>);

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <template <unsigned, bool> class BitsClass, unsigned N, bool Signed>
    requires ((N >= Size) && (BitsClass<N, Signed>::IsABits))
  BitfieldMember<ParentSize, Start, Size>::template operator BitsClass<N, Signed>() const {
    return BitsClass<N, Signed> {(static_cast<BitsType<ParentSize>>(m_parent) >> Bits<ParentSize>(Start)) & MaximumValue};
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N>
  BitfieldMember<ParentSize, Start, Size>
      &BitfieldMember<ParentSize, Start, Size>::template operator=(
          const typename BitfieldMember<ParentSize, Start, Size>::template BitsType<N> &value) {
    m_parent = (static_cast<BitsType<ParentSize>>(m_parent) & ~Mask) |
               ((value.template sll<Size>()) & Mask);
    return *this;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  BitfieldMember<ParentSize, Start, Size>
      &BitfieldMember<ParentSize, Start, Size>::template operator=(
          const BitfieldMember<ParentSize, Start, Size> &other) {
    m_parent = (static_cast<BitsType<ParentSize>>(m_parent) & ~Mask) |
               ((static_cast<BitsType<Size>>(other).template widening_sll<Start>()) & Mask);
    return *this;
  }

}  // namespace udb
