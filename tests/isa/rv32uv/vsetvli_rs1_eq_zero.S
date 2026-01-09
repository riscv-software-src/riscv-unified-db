# See LICENSE for license details

#include "riscv_test.h"
#undef RVTEST_RV64UV
#define RVTEST_RV64UV RVTEST_RV32UV

#include "../rv64uv/vsetvli_rs1_eq_zero.S"
