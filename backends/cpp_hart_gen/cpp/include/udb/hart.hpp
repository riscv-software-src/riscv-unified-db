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

#include "udb/bits.hpp"
#include "udb/csr.hpp"
#include "udb/enum.hxx"
#include "udb/soc_model.hpp"
#include "udb/stop_reason.h"
#include "udb/version.hpp"

#if !defined(JSON_ASSERT)
#define JSON_ASSERT(cond) udb_assert(cond, "JSON assert");
#endif
#include <nlohmann/json.hpp>

#ifdef assert
#undef assert
#endif

namespace udb {
  // base class for tracers; defines the tracepoints
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

  template <SocModel SocType>
  class HartBase {
   public:
    HartBase(unsigned hart_id, SocType& soc, const nlohmann::json& cfg)
        : m_hart_id(hart_id),
          m_soc(soc),
          m_tracer(nullptr),
          m_current_priv_mode(PrivilegeMode::M),
          m_exit_requested(false),
          m_num_inst_exec(0) {}

    virtual void reset(uint64_t reset_pc) {
      m_exit_requested = 0;
      m_num_inst_exec = 0;
    }

    void attach_tracer(AbstractTracer* t) {
      udb_assert(m_tracer == nullptr, "m_tracer NULL ptr");
      m_tracer = t;
    }

    virtual void set_pc(uint64_t new_pc) = 0;
    virtual void set_next_pc(uint64_t next_pc) = 0;
    virtual uint64_t pc() const = 0;
    virtual void advance_pc() = 0;

    // get the next instruction encoding
    virtual uint64_t fetch() = 0;

    PrivilegeMode mode() const { return m_current_priv_mode; }
    void set_mode(const PrivilegeMode& next_mode) {
      m_current_priv_mode = next_mode;
    }

    // access a physical address. All translations and physical checks
    // should have already occurred
    // template <unsigned Len, typename AddrBitsType>
    // Bits<Len> read_physical_memory(AddrBitsType paddr) {
    //   if (m_tracer != nullptr) {
    //     m_tracer->trace_mem_read_phys(paddr.get(), Len);
    //   }
    //   if constexpr (Len == 8) {
    //     return m_soc.read_physical_memory_8(paddr.get());
    //   } else if constexpr (Len == 16) {
    //     return m_soc.read_physical_memory_16(paddr.get());
    //   } else if constexpr (Len == 32) {
    //     return m_soc.read_physical_memory_32(paddr.get());
    //   } else if constexpr (Len == 64) {
    //     return m_soc.read_physical_memory_64(paddr.get());
    //   } else {
    //     udb_assert(false, "TODO");
    //     return 0;
    //   }
    // }

    void assert(bool arg, const char* str) { udb_assert(arg, str); }
    void assert(bool arg, const std::string_view& str) { udb_assert(arg, str); }

    // write a physical address. All translations and physical checks
    // should have already occurred
    // template <unsigned Len>
    // void write_physical_memory(uint64_t paddr, const Bits<Len> &value) {
    //   if (m_tracer != nullptr) {
    //     m_tracer->trace_mem_write_phys(paddr, Len, value.get());
    //   }
    //   if constexpr (Len == 8) {
    //     m_soc.write_physical_memory_8(paddr, value);
    //   } else if constexpr (Len == 16) {
    //     m_soc.write_physical_memory_16(paddr, value);
    //   } else if constexpr (Len == 32) {
    //     m_soc.write_physical_memory_32(paddr, value);
    //   } else if constexpr (Len == 64) {
    //     m_soc.write_physical_memory_64(paddr, value);
    //   } else {
    //     udb_assert(false, "TODO");
    //   }
    // }

    [[noreturn]] void abort_current_instruction() {
      if (m_tracer != nullptr) {
        m_tracer->trace_exception();
      }
      throw AbortInstruction();
    }

    void wfi() { throw WfiException(); }

    void pause() { throw PauseException(); }

    // SoC functions
    uint64_t read_hpm_counter(uint64_t counternum) {
      return m_soc.read_hpm_counter(counternum);
    }
    uint64_t read_mcycle() { return m_soc.read_mcycle(); }
    uint64_t read_mtime() { return m_soc.read_mtime(); }
    Bits<64> sw_write_mcycle(const Bits<64>& value) {
      return m_soc.sw_write_mcycle(value);
    }
    void cache_block_zero(uint64_t paddr) { m_soc.cache_block_zero(paddr); }
    void eei_ecall_from_m() { m_soc.eei_ecall_from_m(); }
    void eei_ecall_from_s() { m_soc.eei_ecall_from_s(); }
    void eei_ecall_from_u() { m_soc.eei_ecall_from_u(); }
    void eei_ecall_from_vs() { m_soc.eei_ecall_from_vs(); }
    void eei_ebreak() { m_soc.eei_ebreak(); }
    void memory_model_acquire() { m_soc.memory_model_acquire(); }
    void memory_model_release() { m_soc.memory_model_release(); }
    void notify_mode_change(const PrivilegeMode& from,
                            const PrivilegeMode& to) {
      m_soc.notify_mode_change(from, to);
    }
    void ebreak() { m_soc.ebreak(); }
    void prefetch_instruction(uint64_t paddr) {
      m_soc.prefetch_instruction(paddr);
    }
    void prefetch_read(uint64_t paddr) { m_soc.prefetch_read(paddr); }
    void prefetch_write(uint64_t paddr) { m_soc.prefetch_write(paddr); }
    void fence(bool pi, bool pr, bool po, bool pw, bool si, bool sr, bool so,
               bool sw) {
      m_soc.fence(pi, pr, po, pw, si, sr, so, sw);
    }
    void fence_tso() { m_soc.fence_tso(); }
    void ifence() { m_soc.ifence(); }
    template <typename... Args>
    void order_pgtbl_writes_before_vmafence(Args...) {
      // TODO: pass along order info (not easy now because VmaOrderType is
      // cfg-dependent)
      m_soc.order_pgtbl_writes_before_vmafence();
    }
    template <typename... Args>
    void order_pgtbl_reads_after_vmafence(Args...) {
      // TODO: pass along order info
      m_soc.order_pgtbl_reads_after_vmafence();
    }
    Bits<8> read_physical_memory_8(const Bits<64>& paddr) {
      return m_soc.read_physical_memory_8(paddr);
    }
    Bits<16> read_physical_memory_16(const Bits<64>& paddr) {
      return m_soc.read_physical_memory_16(paddr);
    }
    Bits<32> read_physical_memory_32(const Bits<64>& paddr) {
      return m_soc.read_physical_memory_32(paddr);
    }
    Bits<64> read_physical_memory_64(const Bits<64>& paddr) {
      return m_soc.read_physical_memory_64(paddr);
    }
    void write_physical_memory_8(const Bits<64>& paddr, const Bits<8>& value) {
      m_soc.write_physical_memory_8(paddr, value);
    }
    void write_physical_memory_16(const Bits<64>& paddr,
                                  const Bits<16>& value) {
      m_soc.write_physical_memory_16(paddr, value);
    }
    void write_physical_memory_32(const Bits<64>& paddr,
                                  const Bits<32>& value) {
      m_soc.write_physical_memory_32(paddr, value);
    }
    void write_physical_memory_64(const Bits<64>& paddr,
                                  const Bits<64>& value) {
      m_soc.write_physical_memory_64(paddr, value);
    }
    bool atomic_check_then_write_32(uint64_t paddr, uint32_t compare_value,
                                    uint32_t write_value) {
      return m_soc.atomic_check_then_write_32(paddr, compare_value,
                                              write_value);
    }
    bool atomic_check_then_write_64(uint64_t paddr, uint64_t compare_value,
                                    uint64_t write_value) {
      return m_soc.atomic_check_then_write_64(paddr, compare_value,
                                              write_value);
    }
    bool atomically_set_pte_a(uint64_t pte_paddr, uint64_t pte_value,
                              uint32_t pte_len) {
      return atomically_set_pte_a(pte_paddr, pte_value, pte_len);
    }
    bool atomically_set_pte_a_d(uint64_t pte_paddr, uint64_t pte_value,
                                uint32_t pte_len) {
      return atomically_set_pte_a_d(pte_paddr, pte_value, pte_len);
    }
    uint64_t atomic_read_modify_write_32(uint64_t paddr, uint32_t value,
                                         AmoOperation op) {
      return m_soc.atomic_read_modify_write_32(paddr, value, op);
    }
    uint64_t atomic_read_modify_write_64(uint64_t paddr, uint64_t value,
                                         AmoOperation op) {
      return m_soc.atomic_read_modify_write_64(paddr, value, op);
    }
    bool pma_applies_Q_(const PmaAttribute& attr, uint64_t start_paddr,
                        uint32_t len) {
      return m_soc.pma_applies_Q_(attr, start_paddr, len);
    }

    // external interrupt interface
    virtual void set_mmode_ext_int() = 0;
    virtual void clear_mmode_ext_int() = 0;
    virtual void set_smode_ext_int() = 0;
    virtual void clear_smode_ext_int() = 0;
    // virtual void set_vsmode_ext_int() = 0;
    // virtual void clear_vsmode_ext_int() = 0;

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
    void invalidate_translations(const VmaOrderType&) {}

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
    bool check_pma(const uint64_t& paddr, const PmaAttribute& attr) const {
      return true;
    }

    // xlen of M-mode, i.e., MXLEN
    virtual unsigned mxlen() = 0;

    virtual uint64_t xreg(unsigned num) const = 0;
    virtual void set_xreg(unsigned num, uint64_t value) = 0;

    virtual CsrBase* csr(unsigned address) = 0;
    virtual const CsrBase* csr(unsigned address) const = 0;

    virtual CsrBase* csr(const std::string& name) = 0;
    virtual const CsrBase* csr(const std::string& name) const = 0;

    virtual void printState(FILE* out = stdout) const = 0;

    virtual bool implemented_Q_(const ExtensionName& ext) const = 0;
    virtual bool implemented_version_Q_(
        const ExtensionName& ext, const VersionRequirement& req) const = 0;

    [[noreturn]] void unpredictable(const char* why) {
      fmt::print(stderr, "Encountered unpredictable behavior: {}\n", why);
      throw UnpredictableBehaviorException();
    }
    [[noreturn]] void unpredictable(const std::string_view& why) {
      fmt::print(stderr, "Encountered unpredictable behavior: {}\n", why);
      throw UnpredictableBehaviorException();
    }

    unsigned hartid() const { return m_hart_id; }

    virtual int run_one() = 0;
    virtual int run_bb() = 0;
    virtual int run_n(uint64_t n) = 0;

    // called by the ISS; ask the hart to exit (from run_*) immediately
    void request_exit() { m_exit_requested = true; }

    // after run*() returns ExitSuccess or ExitFailure, this will return the
    // exit code from the running program (if run in a way that produces an
    // exit)
    int exit_code() { return m_exit_code; }

    // after run*() returns ExitSuccess or ExitFailure, this will return the
    // exit message from the running program (if run in a way that produces an
    // exit)
    const std::string& exit_reason() { return m_exit_reason; }

    uint64_t num_insts_exec() const { return m_num_inst_exec; }

   protected:
    const unsigned m_hart_id;
    SocType& m_soc;
    AbstractTracer* m_tracer;
    PrivilegeMode m_current_priv_mode;

    int m_exit_code;
    std::string m_exit_reason;

    bool m_exit_requested;

    // the number of instruction *executed*
    // THIS IS NOT minstret (some executed instructions do not retire)
    uint64_t m_num_inst_exec;
  };

}  // namespace udb
