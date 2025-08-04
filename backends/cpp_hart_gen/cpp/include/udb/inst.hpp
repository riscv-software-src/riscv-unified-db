#pragma once

#include "udb/bits.hpp"
#include "udb/bitfield.hpp"
#include "udb/pool_alloc.hpp"

namespace udb {

  class Reg {
   public:
    enum Enum {
      X0 = 0,
      X1 = 1,
      X2 = 2,
      X3 = 3,
      X4 = 4,
      X5 = 5,
      X6 = 6,
      X7 = 7,
      X8 = 8,
      X9 = 9,
      X10 = 10,
      X11 = 11,
      X12 = 12,
      X13 = 13,
      X14 = 14,
      X15 = 15,
      X16 = 16,
      X17 = 17,
      X18 = 18,
      X19 = 19,
      X20 = 20,
      X21 = 21,
      X22 = 22,
      X23 = 23,
      X24 = 24,
      X25 = 25,
      X26 = 26,
      X27 = 27,
      X28 = 28,
      X29 = 29,
      X30 = 30,
      X31 = 31,
      F0 = 32,
      F1 = 33,
      F2 = 34,
      F3 = 35,
      F4 = 36,
      F5 = 37,
      F6 = 38,
      F7 = 39,
      F8 = 40,
      F9 = 41,
      F10 = 42,
      F11 = 43,
      F12 = 44,
      F13 = 45,
      F14 = 46,
      F15 = 47,
      F16 = 48,
      F17 = 49,
      F18 = 50,
      F19 = 51,
      F20 = 52,
      F21 = 53,
      F22 = 54,
      F23 = 55,
      F24 = 56,
      F25 = 57,
      F26 = 58,
      F27 = 59,
      F28 = 60,
      F29 = 61,
      F30 = 62,
      F31 = 63,
      INVALID = 64
    };

    Reg(Enum r) : m_reg(r) {}
    Reg(uint64_t r, bool is_fp = false) : m_reg(Enum(is_fp ? r + 32 : r)) {}

    template <typename BitsClass>
      requires (BitsClass::IsABits)
    Reg(const BitsClass& r, bool is_fp = false) : m_reg(Enum(is_fp ? r.get() + 32 : r.get())) {}
    operator Enum() const { return m_reg; }
    bool operator==(const Reg &other) const { return m_reg == other.m_reg; }
    bool operator==(Enum other) const { return m_reg == other; }
    std::ostream &operator<<(std::ostream &o) const {
      o << to_string();
      return o;
    }

    bool is_int() const { return m_reg <= X31; }
    bool is_fp() const { return m_reg >= F0 && m_reg <= F31; }

    uint64_t get_num() const {
      uint64_t num = static_cast<uint64_t>(m_reg);
      return (m_reg <= X31) ? num : num - 32;  // NOLINT
    }

    std::string to_string(uint64_t size = 64) const {
      if (is_fp()) {
        return "f" + std::to_string(get_num());
      }
      return "x" + std::to_string(get_num());
    }

   private:
    Enum m_reg = INVALID;
  };

  class InstBase {
   public:
    InstBase() = default;
    ~InstBase() = default;

    virtual uint64_t pc() const = 0;
    virtual uint64_t encoding() const = 0;

    // return encoding length, in bytes
    virtual size_t enc_len() const = 0;

    // execute the instruction, updating the hart state
    // if the instruction causes a synchronous exception, a
    // HartBase::SynchronousException will be raised in C++
    virtual void execute() = 0;

    virtual const std::string_view &name() = 0;
    virtual std::string disassemble(bool use_abi_reg_names = false) const = 0;

    // true if the instruction could change the pc without causing an exception
    // i.e., is a branch
    virtual bool control_flow() const = 0;

    // return the
    virtual std::vector<Reg> srcRegs() const = 0;
    virtual std::vector<Reg> dstRegs() const = 0;

  };

  template <unsigned XLEN, unsigned EncodingLength>
    requires (EncodingLength % 8 == 0)
  class InstWithKnownLength : public InstBase {
   public:
    using EncodingType = Bits<EncodingLength>;

    InstWithKnownLength(Bits<XLEN> pc, EncodingType encoding)
      : m_pc(pc),
        m_encoding(encoding)
    {
    }

    uint64_t pc() const override { return m_pc.get(); }
    const Bits<XLEN> _pc() const { return m_pc; }
    uint64_t encoding() const override { return m_encoding.get(); }
    const EncodingType& _encoding() const { return m_encoding; }
    size_t enc_len() const override { return EncodingLength / 8; }

   protected:
    const Bits<XLEN> m_pc;
    const EncodingType m_encoding;
  };

}  // namespace udb
