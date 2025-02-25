#pragma once

#include <cstdint>

#include "udb/enum.hxx"

#ifdef assert
#undef assert
#endif

namespace udb {
  template <typename SocType>
  concept SocModel = requires(SocType s) {
    { s.read_hpm_counter(static_cast<uint64_t>(0)) } -> std::same_as<uint64_t>;
    { s.read_mcycle() } -> std::same_as<uint64_t>;
    { s.read_mtime() } -> std::same_as<uint64_t>;
    { s.sw_write_mcycle(static_cast<uint64_t>(0)) } -> std::same_as<uint64_t>;
    { s.cache_block_zero(static_cast<uint64_t>(0)) };
    { s.eei_ecall_from_m() };
    { s.eei_ecall_from_s() };
    { s.eei_ecall_from_u() };
    { s.eei_ecall_from_vs() };
    { s.eei_ebreak() };
    { s.memory_model_acquire() };
    { s.memory_model_release() };
    {
      s.notify_mode_change(PrivilegeMode::ValueType{},
                           PrivilegeMode::ValueType{})
    };
    { s.prefetch_instruction(static_cast<uint64_t>(0)) };
    { s.prefetch_read(static_cast<uint64_t>(0)) };
    { s.prefetch_write(static_cast<uint64_t>(0)) };
    {
      s.fence(static_cast<uint8_t>(0), static_cast<uint8_t>(0),
              static_cast<uint8_t>(0), static_cast<uint8_t>(0),
              static_cast<uint8_t>(0), static_cast<uint8_t>(0),
              static_cast<uint8_t>(0), static_cast<uint8_t>(0))
    };
    { s.fence_tso() };
    { s.ifence() };
    { s.order_pgtbl_writes_before_vmafence() };
    { s.order_pgtbl_reads_after_vmafence() };

    {
      s.read_physical_memory_8(static_cast<uint64_t>(0))
    } -> std::same_as<uint64_t>;
    {
      s.read_physical_memory_16(static_cast<uint64_t>(0))
    } -> std::same_as<uint64_t>;
    {
      s.read_physical_memory_32(static_cast<uint64_t>(0))
    } -> std::same_as<uint64_t>;
    {
      s.read_physical_memory_64(static_cast<uint64_t>(0))
    } -> std::same_as<uint64_t>;
    {
      s.write_physical_memory_8(static_cast<uint64_t>(0),
                                static_cast<uint64_t>(0))
    };
    {
      s.write_physical_memory_16(static_cast<uint64_t>(0),
                                 static_cast<uint64_t>(0))
    };
    {
      s.write_physical_memory_32(static_cast<uint64_t>(0),
                                 static_cast<uint64_t>(0))
    };
    {
      s.write_physical_memory_64(static_cast<uint64_t>(0),
                                 static_cast<uint64_t>(0))
    };

    {
      s.memcpy_from_host(static_cast<uint64_t>(0),
                         static_cast<const uint8_t*>(0),
                         static_cast<uint64_t>(0))
    } -> std::same_as<int>;
    {
      s.memcpy_to_host(static_cast<uint8_t*>(0), static_cast<uint64_t>(0),
                       static_cast<uint64_t>(0))
    } -> std::same_as<int>;

    {
      s.atomic_check_then_write_32(static_cast<uint64_t>(0),
                                   static_cast<uint32_t>(0),
                                   static_cast<uint32_t>(0))
    } -> std::same_as<uint8_t>;
    {
      s.atomic_check_then_write_64(static_cast<uint64_t>(0),
                                   static_cast<uint64_t>(0),
                                   static_cast<uint64_t>(0))
    } -> std::same_as<uint8_t>;
    {
      s.atomically_set_pte_a(static_cast<uint64_t>(0), static_cast<uint64_t>(0),
                             static_cast<uint32_t>(0))
    } -> std::same_as<uint8_t>;
    {
      s.atomically_set_pte_a_d(static_cast<uint64_t>(0),
                               static_cast<uint64_t>(0),
                               static_cast<uint32_t>(0))
    } -> std::same_as<uint8_t>;
    {
      s.atomic_read_modify_write_32(static_cast<uint64_t>(0),
                                    static_cast<uint32_t>(0),
                                    AmoOperation::ValueType{})
    } -> std::same_as<uint64_t>;
    {
      s.atomic_read_modify_write_64(static_cast<uint64_t>(0),
                                    static_cast<uint64_t>(0),
                                    AmoOperation::ValueType{})
    } -> std::same_as<uint64_t>;

    {
      s.pma_applies_Q_(PmaAttribute::ValueType{}, static_cast<uint64_t>(0),
                       static_cast<uint32_t>(0))
    } -> std::same_as<uint8_t>;
  };
}  // namespace udb
