#include <catch2/catch_test_macros.hpp>
#include <udb/hart_factory.hxx>
#include <udb/memory.hpp>
#include <udb/version.hpp>

using namespace udb;

const std::string cfg_yaml = R"(

$schema: config_schema.json#
kind: architecture configuration
type: fully configured
name: test_cfg
description: For testing

implemented_extensions:
  - [I, "2.1.0"]
  - [Sm, "1.12.0"]

params:
  MXLEN: 64
  NAME: test
  ARCH_ID: 0x1000000000000000
  IMP_ID: 0x0
  VENDOR_ID_BANK: 0x0
  VENDOR_ID_OFFSET: 0x0
  MISALIGNED_LDST: true
  MISALIGNED_LDST_EXCEPTION_PRIORITY: high
  MISALIGNED_MAX_ATOMICITY_GRANULE_SIZE: 0
  MISALIGNED_SPLIT_STRATEGY: by_byte
  PRECISE_SYNCHRONOUS_EXCEPTIONS: true
  TRAP_ON_ECAL_FROM_M: true
  TRAP_ON_EBREAK: true
  TRAP_ON_ILLEGAL_WLRL: true
  TRAP_ON_UNIMPLEMENTED_INSTRUCTION: true
  TRAP_ON_RESERVED_INSTRUCTION: true
  TRAP_ON_UNIMPLEMENTED_CSR: true
  REPORT_VA_IN_MTVAL_ON_BREAKPOINT: true
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_MISALIGNED: true
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_MISALIGNED: true
  REPORT_VA_IN_MTVAL_ON_LOAD_ACCESS_FAULT: true
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_ACCESS_FAULT: true
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_ACCESS_FAULT: true
  REPORT_VA_IN_MTVAL_ON_LOAD_PAGE_FAULT: true
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_PAGE_FAULT: true
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_PAGE_FAULT: true
  REPORT_ENCODING_IN_MTVAL_ON_ILLEGAL_INSTRUCTION: true
  MTVAL_WIDTH: 64
  CONFIG_PTR_ADDRESS: 0
  PMA_GRANULARITY: 12
  PHYS_ADDR_WIDTH: 54
  M_MODE_ENDIANESS: little
  MISA_CSR_IMPLEMENTED: true
  MTVEC_MODES: [0, 1]
  MTVEC_BASE_ALIGNMENT_DIRECT: 4
  MTVEC_BASE_ALIGNMENT_VECTORED: 4
)";

udb::Memory mem;
auto hart = udb::HartFactory::create("_", 0, cfg_yaml, mem);

TEST_CASE("Hints", "[version]") {
  hart->decode(
      0, 0b00000000000000000000000000010111ull);  // auipc, or lpad if Zicfilp
}
