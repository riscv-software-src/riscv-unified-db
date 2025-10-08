

#include "udb/enum.hxx"
#include "udb/hart.hpp"
#include "udb/hart_factory.hxx"

#define UDB_EXPORT __attribute__((visibility("default")))

#include "udb/renode_imports.h"

EXTERNAL_AS(uint64_t, ReadByteFromBus, renode_read_byte, uint64_t)
EXTERNAL_AS(uint64_t, ReadWordFromBus, renode_read_word, uint64_t)
EXTERNAL_AS(uint64_t, ReadDoubleWordFromBus, renode_read_double, uint64_t)
EXTERNAL_AS(uint64_t, ReadQuadWordFromBus, renode_read_quad, uint64_t)

EXTERNAL_AS(void, WriteByteToBus, renode_write_byte, uint64_t, uint64_t)
EXTERNAL_AS(void, WriteWordToBus, renode_write_word, uint64_t, uint64_t)
EXTERNAL_AS(void, WriteDoubleWordToBus, renode_write_double, uint64_t, uint64_t)
EXTERNAL_AS(void, WriteQuadWordToBus, renode_write_quad, uint64_t, uint64_t)

struct RenodeSocModel {
  uint64_t read_hpm_counter(uint64_t counternum) { return 0; }

  uint64_t read_mcycle() { return 0; }
  uint64_t read_mtime() { return 0; }

  // returns new value of mcycle (could be different than new_value)
  uint64_t sw_write_mcycle(uint64_t new_value) { return 0; }

  void cache_block_zero(uint64_t paddr) {}

  // eei_* occur when the configuration indicates that ecall/ebreak don't cause
  // exceptions
  void eei_ecall_from_m() {}
  void eei_ecall_from_s() {}
  void eei_ecall_from_u() {}
  void eei_ecall_from_vs() {}
  void eei_ebreak() {}

  void memory_model_acquire() {}
  void memory_model_release() {}
  void notify_mode_change(udb::PrivilegeMode::ValueType from,
                          udb::PrivilegeMode::ValueType to) {}
  void prefetch_instruction(uint64_t paddr) {}
  void prefetch_read(uint64_t paddr) {}
  void prefetch_write(uint64_t paddr) {}
  void fence(uint8_t pi, uint8_t pr, uint8_t po, uint8_t pw, uint8_t si,
             uint8_t sr, uint8_t so, uint8_t sw) {}
  void fence_tso() {}
  void ifence() {}
  void order_pgtbl_writes_before_vmafence() {}
  void order_pgtbl_reads_after_vmafence() {}

  uint64_t read_physical_memory_8(uint64_t paddr) {
    return renode_read_byte(paddr);
  }
  uint64_t read_physical_memory_16(uint64_t paddr) {
    return renode_read_word(paddr);
  }
  uint64_t read_physical_memory_32(uint64_t paddr) {
    return renode_read_double(paddr);
  }
  uint64_t read_physical_memory_64(uint64_t paddr) {
    return renode_read_quad(paddr);
  }
  void write_physical_memory_8(uint64_t paddr, uint64_t value) {
    renode_write_byte(paddr, value);
  }
  void write_physical_memory_16(uint64_t paddr, uint64_t value) {
    renode_write_word(paddr, value);
  }
  void write_physical_memory_32(uint64_t paddr, uint64_t value) {
    renode_write_double(paddr, value);
  }
  void write_physical_memory_64(uint64_t paddr, uint64_t value) {
    renode_write_quad(paddr, value);
  }

  int memcpy_from_host(uint64_t guest_paddr, const uint8_t* host_ptr,
                       uint64_t size) {
    return -1;
  }
  int memcpy_to_host(uint8_t* host_ptr, uint64_t guest_paddr, uint64_t size) {
    return -1;
  }

  uint8_t atomic_check_then_write_32(uint64_t, uint32_t, uint32_t) { return 0; }
  uint8_t atomic_check_then_write_64(uint64_t, uint64_t, uint64_t) { return 0; }
  uint8_t atomically_set_pte_a(uint64_t, uint64_t, uint32_t) { return 0; }
  uint8_t atomically_set_pte_a_d(uint64_t, uint64_t, uint32_t) { return 0; }
  uint64_t atomic_read_modify_write_32(uint64_t, uint64_t,
                                       udb::AmoOperation::ValueType) {
    return 0;
  }
  uint64_t atomic_read_modify_write_64(uint64_t, uint64_t,
                                       udb::AmoOperation::ValueType) {
    return 0;
  }

  // returns 1 if pma applies to the *entire* region [paddr, paddr + len)
  // returns 0 otherwise
  uint8_t pma_applies_Q_(udb::PmaAttribute::ValueType pma, uint64_t paddr,
                         uint32_t len) {
    return 0;
  }
  uint16_t read_entropy() {
      return (uint16_t)(rand() & 0xffff);
  }
};

static RenodeSocModel callbacks;
static udb::HartBase<RenodeSocModel>* hart = nullptr;

extern "C" UDB_EXPORT int32_t renode_init_ex(uint32_t hart_id,
                                             const char* model_name,
                                             const char* cfg_path) {
  if (hart != nullptr) {
    return -1;
  }

  hart = udb::HartFactory::create<RenodeSocModel>(
      model_name, hart_id, std::filesystem::path{cfg_path}, callbacks);

  return 0;
}

extern "C" UDB_EXPORT const char* renode_exit_reason_ex() {
  return hart->exit_reason().c_str();
}

extern "C" UDB_EXPORT void renode_destruct_ex() {
  if (hart != nullptr) {
    delete hart;
    hart = nullptr;
  }
}

extern "C" UDB_EXPORT int64_t renode_execute_ex(int64_t n) {
  return hart->run_n(n);
}

extern "C" UDB_EXPORT void renode_set_register_value64_ex(int32_t reg,
                                                          uint64_t value) {
  if (reg == 32) {
    hart->set_pc(value);
  } else {
    udb_assert(false, "TODO: reg num");
  }
}

extern "C" UDB_EXPORT uint32_t renode_get_register_value64_ex(int32_t reg) {
  if (reg == 32) {
    return hart->pc();
  } else {
    udb_assert(false, "TODO: reg num");
  }
}

extern "C" UDB_EXPORT uint64_t renode_get_icount_ex() {
  return hart->num_insts_exec();
}
