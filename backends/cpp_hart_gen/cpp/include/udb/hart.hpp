#pragma once

#include <array>
#include <string>
#include <tuple>
#include <utility>

#include <vector>
#include <map>
#include <memory>
#include <unordered_map>
#include <set>

// #include "iss/util.hpp"
// #include "iss/types.hxx"
#include "udb/xregister.hpp"
#include "udb/csr.hpp"
#include "udb/memory.hpp"
#include "udb/enum.hxx"
// #include "iss/bitfield_types.hxx"
// #include "iss/csr_types.hxx"
// #include "iss/inst.hpp"


namespace udb {

  // probably unwise to change these
  static constexpr uint64_t LOG_MEM_REGION_SZ = 12; // 4k regions
  static constexpr uint64_t LOG_EXECMAP_CHUNK_SZ = 12;

  // derived values - do not modify
  static constexpr uint64_t MEM_REGION_SZ = 1UL << LOG_MEM_REGION_SZ;
  static constexpr uint64_t MEM_REGION_MASK = ~(MEM_REGION_SZ - 1);

  static const constexpr uint64_t NS_BIT_OFFSET = 52; // non-secure bit
  static const constexpr uint64_t NS_MASK = 1UL << NS_BIT_OFFSET;

  // hash used to initialize each 64-bit word in memory
  // assumes addr is the aligned physical address plus NS bit
  inline uint64_t mem_init_hash(uint64_t addr) {
    uint8_t ns = addr >> NS_BIT_OFFSET;                    // NOLINT
    return ((addr ^ (addr >> 4)) & 0x0f0f0f0f0f0f0f0eUL) | // NOLINT
           (0x1010101010101010UL << ns);                   // NOLINT
  }

  class AbstractTracer {
    public:
    AbstractTracer() = default;

    virtual void trace_exception() {}

    virtual void trace_mem_read_phys(uint64_t paddr, unsigned len) {}
    virtual void trace_mem_write_phys(uint64_t paddr, unsigned len, uint64_t data) {}
  };

  class HartBase {
    // object that is thrown when an instruction encounters an exception
    class AbortInstruction : public std::exception {
      public:
      const char* what() const noexcept override { return "Instruction Abort"; }
    };
    public:

    HartBase(unsigned hart_id, Memory& mem, const nlohmann::json& cfg)
     : m_hart_id(hart_id),
       m_mem(mem),
       m_tracer(nullptr),
       m_current_priv_mode(PrivilegeMode::M)
    {
    }

    void attach_tracer(AbstractTracer* t) {
      assert(m_tracer == nullptr);
      m_tracer = t;
    }

    virtual void set_pc(uint64_t new_pc) = 0;
    virtual void set_next_pc(uint64_t next_pc) = 0;
    virtual uint64_t pc() const = 0;
    virtual void advance_pc() = 0;

    PrivilegeMode mode() const { return m_current_priv_mode; }
    void set_mode(const PrivilegeMode& next_mode) { m_current_priv_mode = next_mode; }

    // access a physical address. All translations and physical checks
    // should have already occurred
    template <unsigned Len>
    Bits<Len> read_physical_memory(uint64_t paddr)
    {
      if (m_tracer != nullptr) {
        m_tracer->trace_mem_read_phys(paddr, Len);
      }
      if constexpr (Len == 8) {
        return m_mem.read<uint8_t>(paddr);
      } else if constexpr (Len == 16) {
        return m_mem.read<uint16_t>(paddr);
      } else if constexpr (Len == 32) {
        return m_mem.read<uint32_t>(paddr);
      } else if constexpr (Len == 64) {
        return m_mem.read<uint64_t>(paddr);
      } else {
        assert(!"TODO");
        return 0;
      }
    }

    // write a physical address. All translations and physical checks
    // should have already occurred
    template <unsigned Len>
    void write_physical_memory(uint64_t paddr, const Bits<Len>& value)
    {
      if (m_tracer != nullptr) {
        m_tracer->trace_mem_write_phys(paddr, Len, value.get());
      }
      if constexpr (Len == 8) {
        m_mem.write<uint8_t>(paddr, value);
      } else if constexpr (Len == 16) {
        m_mem.write<uint16_t>(paddr, value);
      } else if constexpr (Len == 32) {
        m_mem.write<uint32_t>(paddr, value);
      } else if constexpr (Len == 64) {
        m_mem.write<uint64_t>(paddr, value);
      } else {
        assert(!"TODO");
      }
    }

    [[noreturn]] void abort_current_instruction()
    {
      if (m_tracer != nullptr) {
        m_tracer->trace_exception();
      }
      throw AbortInstruction();
    }

    //
    // virtual memory caching builtins
    //

    void invalidate_all_translations() {}
    void invalidate_asid_translations(Bits<16> asid) {}
    void invalidate_vaddr_translations(uint64_t vaddr) {}
    void invalidate_asid_vaddr_translations(Bits<16> asid, uint64_t vaddr) {}

    void sfence_all() {}
    void sfence_asid(Bits<16> asid) {}
    void sfence_vaddr(uint64_t vaddr) {}
    void sfence_asid_vaddr(Bits<16> asid, uint64_t vaddr) {}


    // Return true if the address at paddr has the PMA attribute 'attr'
    bool check_pma(const uint64_t& paddr, const PmaAttribute& attr) const
    {
      return true;
    }

    // xlen of M-mode, i.e., MXLEN
    virtual unsigned mxlen() = 0;

    // the current effective XLEN, in the current mode
    virtual unsigned xlen() = 0;

    virtual uint64_t xreg(unsigned num) const = 0;
    virtual void set_xreg(unsigned num, uint64_t value) = 0;

    virtual CsrBase* csr(unsigned address) = 0;

    virtual const CsrBase* csr(unsigned address) const = 0;

    virtual void printState(FILE* out = stdout) const = 0;

    protected:
    const unsigned m_hart_id;
    Memory& m_mem;
    AbstractTracer* m_tracer;
    PrivilegeMode m_current_priv_mode;
  };

  // static_assert(HartBase<64>::sext(15, 3) == 0xffffffffffffffffull);
  // static_assert(HartBase<64>::sext(14, 3) == 0xfffffffffffffffeull);
  // static_assert(HartBase<64>::sext(7, 3) == 7);
}
