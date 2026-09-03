#pragma once

#include <algorithm>
#include <fmt/core.h>

#include <cstdint>
#include <cstdio>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <vector>

#include "udb/soc_model.hpp"
#include "udb/NotificationHandler.hpp"


namespace udb {
  enum MEM_NOTIFICATION_EVENT
  {
    MEMREAD_EVENT = 0,
    MEMWRITE_EVENT
  };


  class MemAccessRange
  {
  public:
    MemAccessRange(uint64_t addr, size_t size) {m_addr = addr; m_size = size;}
    uint64_t GetAddress() {return  m_addr;}
    size_t GetSize() {return m_size;}

    bool operator==(const MemAccessRange& mr) const {
        return (this->m_addr == mr.m_addr && this->m_size == mr.m_size);
    }

  protected:
    uint64_t m_addr;
    size_t m_size;
  };

  class MemAccess : public MemAccessRange
  {
  public:
    MemAccess(uint64_t addr, size_t size, uint64_t data)
      : MemAccessRange(addr, size)
    {m_data = data;}

    uint64_t GetData() {return m_data;}
  private:
    uint64_t m_data;
  };



  class IssSocModel : public NotificationSource {
    class DenseMemory {
     public:
      DenseMemory(uint64_t size, uint64_t base_addr, NotificationSource* pNotifier) : m_offset(base_addr) {
        m_data.resize(size);
        m_addend = &m_data[0] - base_addr;
        m_pNotifier = pNotifier;
      }
      ~DenseMemory() = default;

      // subclasses only need to override these functions:
      virtual uint64_t read(uint64_t addr, size_t bytes) {
        check_bounds(addr, bytes);
        MemAccessRange memAccessData(addr, bytes);
        this->Notify(MEMREAD_EVENT, &memAccessData);

        switch (bytes) {
          case 1:
            return m_data[addr - m_offset];
          case 2:
            return *(uint16_t *)(addr + m_addend);
          case 4:
            return *(uint32_t *)(addr + m_addend);
          case 8:
            return *(uint64_t *)(addr + m_addend);
          default:
            __builtin_unreachable();
        }
      }

      void write(uint64_t addr, uint64_t data, size_t bytes) {
        check_bounds(addr, bytes);
        MemAccess memAccess(addr, bytes, data);
        switch (bytes) {
          case 1:
            m_data[addr - m_offset] = data;
            break;
          case 2:
            *(uint16_t *)(addr + m_addend) = data;
            break;
          case 4:
            *(uint32_t *)(addr + m_addend) = data;
            break;
          case 8:
            *(uint64_t *)(addr + m_addend) = data;
            break;
          default:
            __builtin_unreachable();
        }
        this->Notify(MEMWRITE_EVENT, &memAccess);
      }

      bool contains(uint64_t addr, size_t bytes) const {
        if (addr < m_offset) {
          return false;
        }

        const uint64_t offset = addr - m_offset;
        const uint64_t size = m_data.size();
        return offset <= size && bytes <= size - offset;
      }

      int memcpy_from_host(uint64_t guest_paddr, const uint8_t *host_ptr,
                           std::size_t size) {
        if(guest_paddr < m_offset || guest_paddr >= m_offset + m_data.size() ||
            guest_paddr + size < m_offset || guest_paddr + size >= m_offset + m_data.size()) {
          //out of bounds
          return -1;
        }
        memcpy(&m_data[guest_paddr - m_offset], host_ptr, size);
        return size;
      }

      int memcpy_to_host(uint8_t *host_ptr, uint64_t guest_paddr,
                         std::size_t size) {
        if(guest_paddr < m_offset || guest_paddr >= m_offset + m_data.size() ||
            guest_paddr + size < m_offset || guest_paddr + size >= m_offset + m_data.size()) {
          //out of bounds
          return -1;
        }

        memcpy(host_ptr, &m_data[guest_paddr - m_offset], size);
        return size;
      }

     private:
      void check_bounds(uint64_t addr, size_t bytes) const {
        if (contains(addr, bytes)) {
          return;
        }

        if (addr < m_offset) {
          throw std::out_of_range(fmt::format(
              "Physical memory access below the configured RAM region: address 0x{:x}, size {}",
              addr, bytes));
        }

        const uint64_t offset = addr - m_offset;
        const uint64_t size = m_data.size();
        if (offset > size || bytes > size - offset) {
          throw std::out_of_range(fmt::format(
              "Physical memory access outside the configured RAM region: address 0x{:x}, size {}",
              addr, bytes));
        }
      }

      std::vector<uint8_t> m_data;
      uint64_t m_offset;
      uint8_t *m_addend = nullptr;
      NotificationSource* m_pNotifier;

      inline int Notify(uint64_t uiEvent, void* pData) {
        if(m_pNotifier) {
          return m_pNotifier->Notify(uiEvent, pData);
        }
        return 0;
      }
    };

   public:
    IssSocModel(uint64_t size, uint64_t base_addr,
                std::optional<uint64_t> uart_base = std::nullopt,
                std::optional<uint64_t> clint_base = std::nullopt,
                uint64_t misaligned_max_atomicity_granule_size = 0)
        : m_memory(size, base_addr, this),
          m_uart_base(uart_base),
          m_clint_base(clint_base),
          m_misaligned_max_atomicity_granule_size(
              misaligned_max_atomicity_granule_size) {}
    IssSocModel() = delete;
    virtual ~IssSocModel() = default;

    uint64_t read_hpm_counter(uint64_t n) { return 0; }
    uint64_t read_mcycle() { return 0; }
    uint64_t read_mtime() { return m_clint_mtime; }
    uint64_t sw_write_mcycle(uint64_t value) { return value; }
    virtual UdbEntropySourceSample poll_entropy_source() { return {0b01, 0, 0}; }
    void cache_block_zero(uint64_t cache_block_physical_address) {}
    void eei_ecall_from_m() {}
    void eei_ecall_from_s() {}
    void eei_ecall_from_u() {}
    void eei_ecall_from_vs() {}
    void eei_ebreak() {}
    void memory_model_acquire() {}
    void memory_model_release() {}
    void assert(uint8_t test, const char *message) {}
    void notify_mode_change(PrivilegeMode new_mode, PrivilegeMode old_mode) {}
    void prefetch_instruction(uint64_t virtual_address) {}
    void prefetch_read(uint64_t virtual_address) {}
    void prefetch_write(uint64_t virtual_address) {}
    void fence(uint8_t pi, uint8_t pr, uint8_t po, uint8_t pw, uint8_t si,
               uint8_t sr, uint8_t so, uint8_t sw) {}
    void fence_tso() {}
    void ifence() {}
    void order_pgtbl_writes_before_vmafence() {}
    void order_pgtbl_reads_after_vmafence() {}

    // Sail's ACT platform advances mtime after every two executed
    // instructions. While WFI is blocked, its clock advances on each poll.
    // The ISS samples pending lines at the next instruction boundary.
    void tick(bool waiting_for_interrupt) {
      if (!m_clint_base.has_value()) {
        return;
      }

      if (waiting_for_interrupt) {
        ++m_clint_mtime;
        return;
      }

      if (m_clint_instructions_since_tick == kClintInstructionsPerTick) {
        ++m_clint_mtime;
        m_clint_instructions_since_tick = 0;
      }
      ++m_clint_instructions_since_tick;
    }

    bool machine_software_interrupt_pending() const {
      return (m_clint_msip & 1) != 0;
    }
    bool supervisor_software_interrupt_pending() const {
      return m_test_ssip_pending;
    }
    bool machine_timer_interrupt_pending() const {
      return m_clint_base.has_value() && m_clint_mtime >= m_clint_mtimecmp;
    }
    bool machine_external_interrupt_pending() const {
      return m_test_meip_pending;
    }
    bool supervisor_external_interrupt_pending() const {
      return m_test_seip_pending;
    }

    uint64_t read_physical_memory_8(uint64_t paddr) {
      if (is_uart_address(paddr)) {
        return uart_read(paddr - *m_uart_base);
      }
      if (is_clint_address(paddr)) {
        return clint_read(paddr - *m_clint_base, 1);
      }
      if (is_test_interrupt_generator_address(paddr)) {
        return 0;
      }
      return m_memory.read(paddr, 1);
    }
    uint64_t read_physical_memory_16(uint64_t paddr) {
      if (is_clint_address(paddr)) {
        return clint_read(paddr - *m_clint_base, 2);
      }
      if (is_test_interrupt_generator_address(paddr)) {
        return 0;
      }
      return m_memory.read(paddr, 2);
    }
    uint64_t read_physical_memory_32(uint64_t paddr) {
      if (is_clint_address(paddr)) {
        return clint_read(paddr - *m_clint_base, 4);
      }
      if (is_test_interrupt_generator_address(paddr)) {
        return 0;
      }
      return m_memory.read(paddr, 4);
    }
    uint64_t read_physical_memory_64(uint64_t paddr) {
      if (is_clint_address(paddr)) {
        return clint_read(paddr - *m_clint_base, 8);
      }
      if (is_test_interrupt_generator_address(paddr)) {
        return 0;
      }
      return m_memory.read(paddr, 8);
    }
    uint8_t physical_memory_accessible_Q_(uint64_t paddr, uint64_t len,
                                          MemoryOperation::ValueType op) const {
      if (len == 0 || (len % 8) != 0) {
        return 0;
      }

      const size_t bytes = len / 8;
      if (op == MemoryOperation::Fetch) {
        return m_memory.contains(paddr, bytes);
      }

      return m_memory.contains(paddr, bytes) ||
             is_uart_access(paddr, bytes) ||
             is_clint_access(paddr, bytes) ||
             is_test_interrupt_generator_access(paddr, bytes);
    }
    void write_physical_memory_8(uint64_t paddr, uint64_t value) {
      if (is_uart_address(paddr)) {
        uart_write(paddr - *m_uart_base, value);
        return;
      }
      if (is_clint_address(paddr)) {
        clint_write(paddr - *m_clint_base, value, 1);
        return;
      }
      if (is_test_interrupt_generator_address(paddr)) {
        test_interrupt_generator_write(value);
        return;
      }
      m_memory.write(paddr, value, 1);
    }
    void write_physical_memory_16(uint64_t paddr, uint64_t value) {
      if (is_clint_address(paddr)) {
        clint_write(paddr - *m_clint_base, value, 2);
        return;
      }
      if (is_test_interrupt_generator_address(paddr)) {
        test_interrupt_generator_write(value);
        return;
      }
      m_memory.write(paddr, value, 2);
    }
    void write_physical_memory_32(uint64_t paddr, uint64_t value) {
      if (is_clint_address(paddr)) {
        clint_write(paddr - *m_clint_base, value, 4);
        return;
      }
      if (is_test_interrupt_generator_address(paddr)) {
        test_interrupt_generator_write(value);
        return;
      }
      m_memory.write(paddr, value, 4);
    }
    void write_physical_memory_64(uint64_t paddr, uint64_t value) {
      if (is_clint_address(paddr)) {
        clint_write(paddr - *m_clint_base, value, 8);
        return;
      }
      if (is_test_interrupt_generator_address(paddr)) {
        test_interrupt_generator_write(value);
        return;
      }
      m_memory.write(paddr, value, 8);
    }

    int memcpy_from_host(uint64_t guest_paddr, const uint8_t *host_ptr,
                         uint64_t size) {
      return m_memory.memcpy_from_host(guest_paddr, host_ptr, size);
    }
    int memcpy_to_host(uint8_t *host_ptr, uint64_t guest_paddr, uint64_t size) {
      return m_memory.memcpy_to_host(host_ptr, guest_paddr, size);
    }

    uint8_t atomic_check_then_write_32(uint64_t paddr, uint64_t compare_value,
                                       uint64_t write_value) {
      m_memory.write(paddr, write_value, 4);
      return true;
    }
    uint8_t atomic_check_then_write_64(uint64_t paddr, uint64_t compare_value,
                                       uint64_t write_value) {
      m_memory.write(paddr, write_value, 8);
      return true;
    }
    uint8_t atomically_set_pte_a(uint64_t pte_addr, uint64_t pte_value,
                                 uint32_t pte_len) {
      return true;
    }
    uint8_t atomically_set_pte_a_d(uint64_t pte_addr, uint64_t pte_value,
                                   uint32_t pte_len) {
      return true;
    }
    uint64_t atomic_read_modify_write_8(uint64_t phys_addr, uint64_t value,
                                        AmoOperation op) {
      return atomic_read_modify_write_small_<uint8_t>(phys_addr, value, op);
    }
    uint64_t atomic_read_modify_write_16(uint64_t phys_addr, uint64_t value,
                                         AmoOperation op) {
      return atomic_read_modify_write_small_<uint16_t>(phys_addr, value, op);
    }
    uint64_t atomic_read_modify_write_32(uint64_t phys_addr, uint64_t value,
                                         AmoOperation op) {
      switch (op.value()) {
        case AmoOperation::Swap: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr, value, 4);
          return orig;
        }
        case AmoOperation::Add: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr, orig + value, 4);
          return orig;
        }
        case AmoOperation::And: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr, orig & value, 4);
          return orig;
        }
        case AmoOperation::Or: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr, orig | value, 4);
          return orig;
        }
        case AmoOperation::Xor: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr, orig ^ value, 4);
          return orig;
        }
        case AmoOperation::Max: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr,
                         std::max(static_cast<int32_t>(orig),
                                  static_cast<int32_t>(value & 0xffffffff)),
                         4);
          return orig;
        }
        case AmoOperation::Maxu: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(
              phys_addr,
              std::max(orig, static_cast<uint32_t>(value & 0xffffffff)), 4);
          return orig;
        }
        case AmoOperation::Min: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(phys_addr,
                         std::min(static_cast<int32_t>(orig),
                                  static_cast<int32_t>(value & 0xffffffff)),
                         4);
          return orig;
        }
        case AmoOperation::Minu: {
          uint32_t orig = m_memory.read(phys_addr, 4);
          m_memory.write(
              phys_addr,
              std::min(orig, static_cast<uint32_t>(value & 0xffffffff)), 4);
          return orig;
        }
        default:
          __builtin_unreachable();
      }
    }
    uint64_t atomic_read_modify_write_64(uint64_t phys_addr, uint64_t value,
                                         AmoOperation op) {
      switch (op.value()) {
        case AmoOperation::Swap: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, value, 8);
          return orig;
        }
        case AmoOperation::Add: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, orig + value, 8);
          return orig;
        }
        case AmoOperation::And: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, orig & value, 8);
          return orig;
        }
        case AmoOperation::Or: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, orig | value, 8);
          return orig;
        }
        case AmoOperation::Xor: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, orig ^ value, 8);
          return orig;
        }
        case AmoOperation::Max: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(
              phys_addr,
              std::max(static_cast<int64_t>(orig), static_cast<int64_t>(value)),
              8);
          return orig;
        }
        case AmoOperation::Maxu: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, std::max(orig, value), 8);
          return orig;
        }
        case AmoOperation::Min: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(
              phys_addr,
              std::min(static_cast<int64_t>(orig), static_cast<int64_t>(value)),
              8);
          return orig;
        }
        case AmoOperation::Minu: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, std::min(orig, value), 8);
          return orig;
        }
        default:
          __builtin_unreachable();
      }
    }

    uint8_t pma_applies_Q_(PmaAttribute attr, uint64_t paddr, uint32_t len) {
      const size_t bytes = len / 8;
      const bool is_io = is_uart_access(paddr, bytes) || is_clint_access(paddr, bytes) ||
                         is_test_interrupt_generator_access(paddr, bytes);
      const bool is_ram = m_memory.contains(paddr, bytes);

      switch (attr.value()) {
        case PmaAttribute::RsrvNone:
        case PmaAttribute::RsrvNonEventual:
        case PmaAttribute::AmoNone:
          return false;
        case PmaAttribute::MAG16:
          return is_ram && m_misaligned_max_atomicity_granule_size >= 16;
        case PmaAttribute::MAG8:
          return is_ram && m_misaligned_max_atomicity_granule_size >= 8;
        case PmaAttribute::MAG4:
          return is_ram && m_misaligned_max_atomicity_granule_size >= 4;
        case PmaAttribute::MAG2:
          return is_ram && m_misaligned_max_atomicity_granule_size >= 2;
        case PmaAttribute::RsrvEventual:
        case PmaAttribute::AmoSwap:
        case PmaAttribute::AmoLogical:
        case PmaAttribute::AmoArithmetic:
        case PmaAttribute::HardwarePageTableRead:
        case PmaAttribute::HardwarePageTableWrite:
        case PmaAttribute::MainMemory:
        case PmaAttribute::Cacheable:
        case PmaAttribute::Coherent:
        case PmaAttribute::Idempotent:
          return is_ram;
        case PmaAttribute::IO:
          return is_io;
        default:
          __builtin_unreachable();
      }
    }


    // builtins for qc_iu

    void delay(uint64_t) { }

    void iss_syscall(uint64_t, uint64_t) { }

    uint32_t read_device_32(uint64_t) { return 0; }

    void write_device_32(uint64_t, uint32_t) { }

    void sync_read_after_write_device(bool, uint32_t) {}

    void sync_write_after_read_device(bool, uint32_t) {}

   private:
    template <typename T>
    uint64_t atomic_read_modify_write_small_(uint64_t phys_addr, uint64_t value,
                                              AmoOperation op) {
      const T orig = static_cast<T>(m_memory.read(phys_addr, sizeof(T)));
      const T rhs = static_cast<T>(value);
      T result;

      switch (op.value()) {
        case AmoOperation::Swap:
          result = rhs;
          break;
        case AmoOperation::Add:
          result = static_cast<T>(orig + rhs);
          break;
        case AmoOperation::And:
          result = static_cast<T>(orig & rhs);
          break;
        case AmoOperation::Or:
          result = static_cast<T>(orig | rhs);
          break;
        case AmoOperation::Xor:
          result = static_cast<T>(orig ^ rhs);
          break;
        case AmoOperation::Max:
          result = static_cast<T>(std::max(static_cast<std::make_signed_t<T>>(orig),
                                            static_cast<std::make_signed_t<T>>(rhs)));
          break;
        case AmoOperation::Maxu:
          result = std::max(orig, rhs);
          break;
        case AmoOperation::Min:
          result = static_cast<T>(std::min(static_cast<std::make_signed_t<T>>(orig),
                                            static_cast<std::make_signed_t<T>>(rhs)));
          break;
        case AmoOperation::Minu:
          result = std::min(orig, rhs);
          break;
        default:
          __builtin_unreachable();
      }

      m_memory.write(phys_addr, result, sizeof(T));
      return orig;
    }

    static constexpr uint64_t kUartSize = 8;
    static constexpr uint64_t kUartThrOffset = 0;
    static constexpr uint64_t kUartLsrOffset = 5;
    static constexpr uint64_t kClintSize = 0xc000;
    static constexpr uint64_t kClintMsipOffset = 0x0000;
    static constexpr uint64_t kClintMtimecmpOffset = 0x4000;
    static constexpr uint64_t kClintMtimeOffset = 0xbff8;
    static constexpr uint64_t kTestInterruptGeneratorAddress = 0x0c000004;

    bool is_uart_address(uint64_t paddr) const {
      return m_uart_base.has_value() && paddr >= *m_uart_base &&
             paddr - *m_uart_base < kUartSize;
    }

    bool is_uart_access(uint64_t paddr, size_t bytes) const {
      return m_uart_base.has_value() && paddr >= *m_uart_base &&
             paddr - *m_uart_base <= kUartSize &&
             bytes <= kUartSize - (paddr - *m_uart_base);
    }

    bool is_clint_address(uint64_t paddr) const {
      return m_clint_base.has_value() && paddr >= *m_clint_base &&
             paddr - *m_clint_base < kClintSize;
    }

    bool is_clint_access(uint64_t paddr, size_t bytes) const {
      if (!is_clint_address(paddr)) {
        return false;
      }

      const uint64_t offset = paddr - *m_clint_base;
      return clint_access_fits(offset, bytes, kClintMsipOffset, 4) ||
             clint_access_fits(offset, bytes, kClintMtimecmpOffset, 8) ||
             clint_access_fits(offset, bytes, kClintMtimeOffset, 8);
    }

    static bool is_test_interrupt_generator_address(uint64_t paddr) {
      return paddr >= kTestInterruptGeneratorAddress &&
             paddr < kTestInterruptGeneratorAddress + sizeof(uint32_t);
    }

    static bool is_test_interrupt_generator_access(uint64_t paddr, size_t bytes) {
      return paddr >= kTestInterruptGeneratorAddress &&
             paddr - kTestInterruptGeneratorAddress <= sizeof(uint32_t) &&
             bytes <= sizeof(uint32_t) - (paddr - kTestInterruptGeneratorAddress);
    }

    uint64_t uart_read(uint64_t offset) const {
      // Minimal NS16550 console model: the transmit holding register is
      // always ready and unimplemented registers read as zero.
      return offset == kUartLsrOffset ? 0x20 : 0;
    }

    void uart_write(uint64_t offset, uint64_t value) {
      if (offset == kUartThrOffset) {
        std::putchar(static_cast<int>(value & 0xff));
        std::fflush(stdout);
      }
    }

    static bool clint_access_fits(uint64_t offset, size_t bytes,
                                  uint64_t register_offset,
                                  size_t register_bytes) {
      return offset >= register_offset &&
             offset - register_offset <= register_bytes &&
             bytes <= register_bytes - (offset - register_offset);
    }

    static uint64_t low_bits_mask(size_t bytes) {
      return bytes == sizeof(uint64_t) ? ~uint64_t{0}
                                       : (uint64_t{1} << (bytes * 8)) - 1;
    }

    static uint64_t read_clint_register(uint64_t value, uint64_t offset,
                                        uint64_t register_offset,
                                        size_t bytes) {
      return (value >> ((offset - register_offset) * 8)) & low_bits_mask(bytes);
    }

    static void write_clint_register(uint64_t& register_value, uint64_t value,
                                     uint64_t offset, uint64_t register_offset,
                                     size_t bytes) {
      const uint64_t shift = (offset - register_offset) * 8;
      const uint64_t mask = low_bits_mask(bytes) << shift;
      register_value = (register_value & ~mask) | ((value & low_bits_mask(bytes)) << shift);
    }

    uint64_t clint_read(uint64_t offset, size_t bytes) const {
      if (clint_access_fits(offset, bytes, kClintMsipOffset, 4)) {
        return read_clint_register(m_clint_msip, offset, kClintMsipOffset, bytes);
      }
      if (clint_access_fits(offset, bytes, kClintMtimecmpOffset, 8)) {
        return read_clint_register(m_clint_mtimecmp, offset, kClintMtimecmpOffset, bytes);
      }
      if (clint_access_fits(offset, bytes, kClintMtimeOffset, 8)) {
        return read_clint_register(m_clint_mtime, offset, kClintMtimeOffset, bytes);
      }
      throw std::out_of_range(fmt::format(
          "Unsupported CLINT access: offset 0x{:x}, size {}", offset, bytes));
    }

    void clint_write(uint64_t offset, uint64_t value, size_t bytes) {
      if (clint_access_fits(offset, bytes, kClintMsipOffset, 4)) {
        write_clint_register(m_clint_msip, value, offset, kClintMsipOffset, bytes);
        m_clint_msip &= 0xffffffff;
        return;
      }
      if (clint_access_fits(offset, bytes, kClintMtimecmpOffset, 8)) {
        write_clint_register(m_clint_mtimecmp, value, offset, kClintMtimecmpOffset, bytes);
        return;
      }
      if (clint_access_fits(offset, bytes, kClintMtimeOffset, 8)) {
        write_clint_register(m_clint_mtime, value, offset, kClintMtimeOffset, bytes);
        return;
      }
      throw std::out_of_range(fmt::format(
          "Unsupported CLINT access: offset 0x{:x}, size {}", offset, bytes));
    }

    void test_interrupt_generator_write(uint64_t value) {
      const bool set = (value & (uint64_t{1} << 31)) != 0;
      if ((value & (uint64_t{1} << 11)) != 0) {
        m_test_meip_pending = set;
      }
      if ((value & (uint64_t{1} << 9)) != 0) {
        m_test_seip_pending = set;
      }
      if ((value & (uint64_t{1} << 1)) != 0) {
        m_test_ssip_pending = set;
      }
    }

    DenseMemory m_memory;
    std::optional<uint64_t> m_uart_base;
    std::optional<uint64_t> m_clint_base;
    uint64_t m_misaligned_max_atomicity_granule_size;
    static constexpr uint64_t kClintInstructionsPerTick = 2;
    uint64_t m_clint_msip = 0;
    uint64_t m_clint_mtimecmp = ~uint64_t{0};
    uint64_t m_clint_mtime = 0;
    uint64_t m_clint_instructions_since_tick = 0;
    bool m_test_meip_pending = false;
    bool m_test_seip_pending = false;
    bool m_test_ssip_pending = false;

  };

  static_assert(SocModel<IssSocModel>,
                "IssSocModel does not obey SocModel interface");
}  // namespace udb
