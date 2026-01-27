#pragma once

#include <fmt/core.h>

#include <cstdint>
#include <cstdio>
#include <vector>

#include "udb/soc_model.hpp"

namespace udb {
  class IssSocModel {
    class DenseMemory {
     public:
      DenseMemory(uint64_t size, uint64_t base_addr) : m_offset(base_addr) {
        m_data.resize(size);
        m_addend = &m_data[0] - base_addr;
      }
      ~DenseMemory() = default;

      // subclasses only need to override these functions:
      virtual uint64_t read(uint64_t addr, size_t bytes) {
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
      }

      int memcpy_from_host(uint64_t guest_paddr, const uint8_t *host_ptr,
                           std::size_t size) {
        const size_t SZ_64 = sizeof(uint64_t);
        auto host_ptr64 = (const uint64_t *)host_ptr;  // NOLINT
        while (size >= SZ_64) {
          write((guest_paddr += SZ_64) - SZ_64, *host_ptr64++, 8);
          size -= SZ_64;
        }

        auto host_ptr8 = (const uint8_t *)host_ptr64;  // NOLINT
        while (size > 0) {
          write(guest_paddr++, *host_ptr8++, 1);
          size--;
        }
        return size;
      }

      int memcpy_to_host(uint8_t *host_ptr, uint64_t guest_paddr,
                         std::size_t size) {
        const size_t SZ_64 = sizeof(uint64_t);
        auto host_ptr64 = (uint64_t *)host_ptr;  // NOLINT
        while (size >= SZ_64) {
          *(host_ptr64++) = read(guest_paddr += SZ_64, 8);
          size -= SZ_64;
        }

        auto host_ptr8 = (uint8_t *)host_ptr64;  // NOLINT
        while (size > 0) {
          *(host_ptr8++) = read(guest_paddr += SZ_64, 1);
          size--;
        }
        return size;
      }

     private:
      std::vector<uint8_t> m_data;
      uint64_t m_offset;
      uint8_t *m_addend = nullptr;
    };

   public:
    IssSocModel(uint64_t size, uint64_t base_addr)
        : m_memory(size, base_addr) {}
    IssSocModel() = delete;
    ~IssSocModel() = default;

    uint64_t read_hpm_counter(uint64_t n) { return 0; }
    uint64_t read_mcycle() { return 0; }
    uint64_t read_mtime() { return 0; }
    uint64_t sw_write_mcycle(uint64_t value) { return value; }
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

    uint64_t read_physical_memory_8(uint64_t paddr) {
      return m_memory.read(paddr, 1);
    }
    uint64_t read_physical_memory_16(uint64_t paddr) {
      return m_memory.read(paddr, 2);
    }
    uint64_t read_physical_memory_32(uint64_t paddr) {
      return m_memory.read(paddr, 4);
    }
    uint64_t read_physical_memory_64(uint64_t paddr) {
      return m_memory.read(paddr, 8);
    }
    void write_physical_memory_8(uint64_t paddr, uint64_t value) {
      m_memory.write(paddr, value, 1);
    }
    void write_physical_memory_16(uint64_t paddr, uint64_t value) {
      m_memory.write(paddr, value, 2);
    }
    void write_physical_memory_32(uint64_t paddr, uint64_t value) {
      m_memory.write(paddr, value, 4);
    }
    void write_physical_memory_64(uint64_t paddr, uint64_t value) {
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
              4);
          return orig;
        }
        case AmoOperation::Maxu: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, std::max(orig, value & 0xffffffff), 4);
          return orig;
        }
        case AmoOperation::Min: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(
              phys_addr,
              std::min(static_cast<int64_t>(orig), static_cast<int64_t>(value)),
              4);
          return orig;
        }
        case AmoOperation::Minu: {
          uint64_t orig = m_memory.read(phys_addr, 8);
          m_memory.write(phys_addr, std::min(orig, value), 4);
          return orig;
        }
        default:
          __builtin_unreachable();
      }
    }

    uint8_t pma_applies_Q_(PmaAttribute attr, uint64_t paddr, uint32_t len) {
      return true;
    }


    // builtins for qc_iu

    void delay(uint64_t) { }

    void iss_syscall(uint64_t, uint64_t) { }

    uint32_t read_device_32(uint64_t) { return 0; }

    void write_device_32(uint64_t, uint32_t) { }

    void sync_read_after_write_device(bool, uint32_t) {}

    void sync_write_after_read_device(bool, uint32_t) {}

   private:
    DenseMemory m_memory;
  };

  static_assert(SocModel<IssSocModel>,
                "IssSocModel does not obey SocModel interface");
}  // namespace udb
