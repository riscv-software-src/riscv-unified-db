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

    BitfieldMember(Bitfield<ParentSize> &parent) : m_parent(parent) {}
    BitfieldMember(const BitfieldMember &other) : m_parent(other.m_parent) {}

    static constexpr Bits<Size> MaximumValue =
        (Bits<1>(1).template sll<Size>()) - 1;
    static constexpr Bits<ParentSize> Mask = MaximumValue.template sll<Start>();

    template <unsigned N>
      requires(N >= Size)
    operator Bits<N>() const;

    template <unsigned N>
      requires(N >= Size)
    operator PossiblyUnknownBits<N>() const;

    bool operator!() const { return !static_cast<Bits<Size>>(*this).get(); }

    template <unsigned N, bool Signed>
    BitfieldMember &operator=(const _Bits<N, Signed> &value);

    BitfieldMember &operator=(const BitfieldMember &other);

    template <std::integral Type>
    bool operator==(const Type &other) const {
      return other == static_cast<Bits<Size>>(*this);
    }

    template <unsigned N, bool Signed>
    bool operator==(const _Bits<N, Signed> &other) const {
      return other == static_cast<Bits<Size>>(*this);
    }

    template <unsigned N, bool Signed>
    bool operator==(const _PossiblyUnknownBits<N, Signed> &other) const {
      return other == static_cast<Bits<Size>>(*this);
    }

    template <unsigned N, bool Signed>
    bool operator>(const _Bits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) > other;
    }

    template <unsigned N, bool Signed>
    bool operator>(const _PossiblyUnknownBits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) > other;
    }

    template <unsigned N, bool Signed>
    friend bool operator<(const _PossiblyUnknownBits<N, Signed> &lhs,
                          const BitfieldMember &rhs);

    template <unsigned N, bool Signed>
    bool operator>=(const _Bits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) >= other;
    }

    template <unsigned N, bool Signed>
    bool operator>=(const _PossiblyUnknownBits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) >= other;
    }

    template <unsigned N, bool Signed>
    bool operator<=(const _Bits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) <= other;
    }

    template <unsigned N, bool Signed>
    bool operator<=(const _PossiblyUnknownBits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) <= other;
    }

    template <unsigned OtherParentSize, unsigned OtherStart, unsigned OtherSize>
    bool operator<(const BitfieldMember<OtherParentSize, OtherStart, OtherSize>
                       &other) const {
      return static_cast<Bits<Size>>(*this) >
             static_cast<Bits<OtherSize>>(*this);
    }

    template <unsigned N, bool Signed>
    Bits<Size> operator>>(const _Bits<N, Signed> &shamt) const {
      return static_cast<Bits<Size>>(*this) >> shamt;
    }
    template <typename T>
      requires(std::integral<T>)
    Bits<Size> operator>>(const T &shamt) const {
      return static_cast<Bits<Size>>(*this) >> shamt;
    }

    template <unsigned N, bool Signed>
    Bits<Size> operator&(const _Bits<N, Signed> &other) const {
      return static_cast<Bits<Size>>(*this) & other;
    }

    Bits<Bits<Size>::InfinitePrecision> operator<<(const int &shamt) const {
      return static_cast<Bits<Size>>(*this) << shamt;
    }

    template <unsigned Shamt>
    Bits<Size + Shamt> sll() const {
      return static_cast<Bits<Size>>(*this).template sll<Shamt>();
    }

   private:
    Bitfield<ParentSize> &m_parent;
  };

  template <unsigned Size>
  class Bitfield {
   public:
    Bitfield() = default;
    Bitfield(const Bits<Size> &value) : m_value(value) {}

    Bitfield &operator=(const Bits<Size> &value) {
      m_value = value;
      return *this;
    }
    template <std::integral Type>
    Bitfield &operator=(const Type &value) {
      m_value = value;
      return *this;
    }
    operator Bits<Size> &() { return m_value; }
    operator Bits<Size>() const { return m_value; }

   protected:
    Bits<Size> m_value;
  };

  static_assert(std::is_copy_constructible_v<BitfieldMember<64, 0, 1>>);

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N>
    requires(N >= Size)
  BitfieldMember<ParentSize, Start, Size>::template operator Bits<N>() const {
    return (static_cast<Bits<ParentSize>>(m_parent) >> Start) & MaximumValue;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N>
    requires(N >= Size)
  BitfieldMember<ParentSize, Start, Size>::template
  operator PossiblyUnknownBits<N>() const {
    return (static_cast<Bits<ParentSize>>(m_parent) >> Start) & MaximumValue;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  template <unsigned N, bool Signed>
  BitfieldMember<ParentSize, Start, Size>
      &BitfieldMember<ParentSize, Start, Size>::template operator=(
          const _Bits<N, Signed> &value) {
    m_parent = (static_cast<Bits<ParentSize>>(m_parent) & ~Mask) |
               ((value.template sll<Size>()) & Mask);
    return *this;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size>
  BitfieldMember<ParentSize, Start, Size>
      &BitfieldMember<ParentSize, Start, Size>::template operator=(
          const BitfieldMember<ParentSize, Start, Size> &other) {
    m_parent = (static_cast<Bits<ParentSize>>(m_parent) & ~Mask) |
               ((static_cast<Bits<Size>>(other).template sll<Size>()) & Mask);
    return *this;
  }

  template <unsigned ParentSize, unsigned Start, unsigned Size, unsigned N,
            bool Signed>
  bool operator<(const _PossiblyUnknownBits<N, Signed> &lhs,
                 const BitfieldMember<ParentSize, Start, Size> &rhs) {
    return lhs < static_cast<Bits<Size>>(rhs);
  }

}  // namespace udb
