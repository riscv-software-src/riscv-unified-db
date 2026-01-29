# Copyright (c) Ishaan Arora
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vmv_v_i.S
#-----------------------------------------------------------------------------
#
# Test vmv.v.i instruction.
#
# vmv.v.i vd, imm
# Copies sign-extended 5-bit immediate to all elements of vd

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64UV
RVTEST_CODE_BEGIN

# Test 1: vmv.v.i with positive immediate (imm = 5)
# VLEN=128, SEW=64, LMUL=1 -> VLMAX=2
# Expected: all elements = 5
  TEST_CASE(1, x5, 5, \
    vsetivli x0, 2, 0x1b; \
    vmv.v.i v1, 5; \
    vmv.x.s x5, v1; \
  )

# Test 2: vmv.v.i with negative immediate (imm = -1 = 0x1f in 5-bit)
# VLEN=128, SEW=64, LMUL=1 -> VLMAX=2
# Expected: all elements = -1 (0xFFFFFFFFFFFFFFFF)
  TEST_CASE(2, x5, -1, \
    vsetivli x0, 2, 0x1b; \
    vmv.v.i v2, -1; \
    vmv.x.s x5, v2; \
  )

# Test 3: vmv.v.i with zero immediate
# VLEN=128, SEW=32, LMUL=1 -> VLMAX=4
# Expected: all elements = 0
  TEST_CASE(3, x5, 0, \
    vsetivli x0, 4, 0x13; \
    vmv.v.i v3, 0; \
    vmv.x.s x5, v3; \
  )

# Test 4: vmv.v.i with max positive 5-bit immediate (imm = 15)
# VLEN=128, SEW=8, LMUL=1 -> VLMAX=16
# Expected: all elements = 15
  TEST_CASE(4, x5, 15, \
    vsetivli x0, 16, 0x03; \
    vmv.v.i v4, 15; \
    vmv.x.s x5, v4; \
  )

# Test 5: vmv.v.i with min negative 5-bit immediate (imm = -16)
# VLEN=128, SEW=16, LMUL=1 -> VLMAX=8
# Expected: all elements = -16 (sign-extended)
  TEST_CASE(5, x5, -16, \
    vsetivli x0, 8, 0x0b; \
    vmv.v.i v5, -16; \
    vmv.x.s x5, v5; \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN

RVTEST_DATA_END
