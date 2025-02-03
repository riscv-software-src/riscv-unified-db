#pragma once

#include <array>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#include "udb/csr.hpp"
#include "udb/enum.hxx"
#include "udb/memory.hpp"
#include "udb/version.hpp"
#include "udb/xregister.hpp"

#ifdef assert
#undef assert
#endif

namespace udb {

  class ExitEvent : public std::exception {
   public:
    ExitEvent(int exit_code) : std::exception(), m_exit_code(exit_code) {}
    virtual ~ExitEvent() = default;

    int code() const { return m_exit_code; }

   private:
    int m_exit_code;
  };

  class AbstractTracer {
   public:
    AbstractTracer() = default;
    virtual ~AbstractTracer() = default;

    virtual void trace_exception() {}

    virtual void trace_mem_read_phys(uint64_t paddr, unsigned len) {}
    virtual void trace_mem_write_phys(uint64_t paddr, unsigned len,
                                      uint64_t data) {}
  };

  class InstBase;
  class HartBase {
    // object that is thrown when an instruction encounters an exception
    class AbortInstruction : public std::exception {
     public:
      const char *what() const noexcept override { return "Instruction Abort"; }
    };

   public:
    HartBase(unsigned hart_id, Memory &mem, const nlohmann::json &cfg)
        : m_hart_id(hart_id),
          m_mem(mem),
          m_tracer(nullptr),
          m_current_priv_mode(PrivilegeMode::M) {}

    void attach_tracer(AbstractTracer *t) {
      udb_assert(m_tracer == nullptr, "m_tracer NULL ptr");
      m_tracer = t;
    }

    virtual void set_pc(uint64_t new_pc) = 0;
    virtual void set_next_pc(uint64_t next_pc) = 0;
    virtual uint64_t pc() const = 0;
    virtual void advance_pc() = 0;

    virtual InstBase *decode(const uint64_t &pc, const uint64_t &encoding) = 0;

    PrivilegeMode mode() const { return m_current_priv_mode; }
    void set_mode(const PrivilegeMode &next_mode) {
      m_current_priv_mode = next_mode;
    }

    // access a physical address. All translations and physical checks
    // should have already occurred
    template <unsigned Len, typename AddrBitsType>
    Bits<Len> read_physical_memory(AddrBitsType paddr) {
      if (m_tracer != nullptr) {
        m_tracer->trace_mem_read_phys(paddr.get(), Len);
      }
      if constexpr (Len == 8) {
        return m_mem.read<uint8_t>(paddr.get());
      } else if constexpr (Len == 16) {
        return m_mem.read<uint16_t>(paddr.get());
      } else if constexpr (Len == 32) {
        return m_mem.read<uint32_t>(paddr.get());
      } else if constexpr (Len == 64) {
        return m_mem.read<uint64_t>(paddr.get());
      } else {
        udb_assert(false, "TODO");
        return 0;
      }
    }

    void assert(bool arg, const char *str) { udb_assert(arg, str); }

    // write a physical address. All translations and physical checks
    // should have already occurred
    template <unsigned Len>
    void write_physical_memory(uint64_t paddr, const Bits<Len> &value) {
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
        udb_assert(false, "TODO");
      }
    }

    [[noreturn]] void abort_current_instruction() {
      if (m_tracer != nullptr) {
        m_tracer->trace_exception();
      }
      throw AbortInstruction();
    }

    //
    // virtual memory caching builtins
    //

    struct SoftTlbEntry {
      bool valid;
      bool global;
      bool smode;   // was translation satp-based?
      bool vsmode;  // was translation vsatp-based?
      bool gstage;  // was translation hgatp-based?

      Bits<16> asid;
      Bits<16> vmid;

      uint64_t vpn;     // virtual page number
      uint64_t ppn;     // physical page number
      uintptr_t vaddr;  // offset to the page in *host* memory; ~0 = not valid
      uintptr_t paddr;  // offset to the page in *host* memory; ~0 = not valid
    };

    constexpr static unsigned SOFT_TLB_SIZE = 1024;

    SoftTlbEntry m_va_smode_read_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_smode_write_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_smode_exe_tlb[SOFT_TLB_SIZE];

    SoftTlbEntry m_va_vsmode_read_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_vsmode_write_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_vsmode_exe_tlb[SOFT_TLB_SIZE];

    SoftTlbEntry m_va_gstage_read_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_gstage_write_tlb[SOFT_TLB_SIZE];
    SoftTlbEntry m_va_gstage_exe_tlb[SOFT_TLB_SIZE];

    template <typename VmaOrderType>
    void invalidate_translations(const VmaOrderType &) {}

    void invalidate_all_translations() {}
    void invalidate_asid_translations(Bits<16> asid) {}
    void invalidate_vaddr_translations(uint64_t vaddr) {}
    void invalidate_asid_vaddr_translations(Bits<16> asid, uint64_t vaddr) {}

    template <typename TranslationResult>
    void maybe_cache_translation(Bits<64> vaddr, MemoryOperation op,
                                 TranslationResult result) {}

    void sfence_all() {}
    void sfence_asid(Bits<16> asid) {}
    void sfence_vaddr(uint64_t vaddr) {}
    void sfence_asid_vaddr(Bits<16> asid, uint64_t vaddr) {}

    // Return true if the address at paddr has the PMA attribute 'attr'
    bool check_pma(const uint64_t &paddr, const PmaAttribute &attr) const {
      return true;
    }

    // xlen of M-mode, i.e., MXLEN
    virtual unsigned mxlen() = 0;

    virtual uint64_t xreg(unsigned num) const = 0;
    virtual void set_xreg(unsigned num, uint64_t value) = 0;

    virtual CsrBase *csr(unsigned address) = 0;
    virtual const CsrBase *csr(unsigned address) const = 0;

    virtual CsrBase *csr(const std::string &name) = 0;
    virtual const CsrBase *csr(const std::string &name) const = 0;

    virtual void printState(FILE *out = stdout) const = 0;

    virtual bool implemented_Q_(const ExtensionName &ext) = 0;
    virtual bool implemented_Q_(const ExtensionName &ext,
                                const VersionRequirement &req) = 0;

    template <unsigned M>
    Bits<64> read_hpm_counter(const Bits<M> &hpm_num) {
      return 0;
    }

    Bits<64> read_mcycle() { return 0; }

    Bits<64> sw_write_mcycle(const Bits<64> &cycle) { return 0; }

    unsigned hartid() const { return m_hart_id; }

   protected:
    const unsigned m_hart_id;
    Memory &m_mem;
    AbstractTracer *m_tracer;
    PrivilegeMode m_current_priv_mode;
  };

  // static_assert(HartBase<64>::sext(15, 3) == 0xffffffffffffffffull);
  // static_assert(HartBase<64>::sext(14, 3) == 0xfffffffffffffffeull);
  // static_assert(HartBase<64>::sext(7, 3) == 7);
}  // namespace udb
