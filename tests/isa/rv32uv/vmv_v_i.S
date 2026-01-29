# Copyright (c) Ishaan Arora
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#include "riscv_test.h"
#undef RVTEST_RV64U
#define RVTEST_RV64U RVTEST_RV32U

#include "../rv64uv/vmv_v_i.S"
