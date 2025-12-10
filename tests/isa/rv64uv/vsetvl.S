# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vsetvl.S
#-----------------------------------------------------------------------------
#
# Test vsetvl instruction.
#
# vsetvl xd, xs1, xs2
# xs2[7:0] = VLMUL[2:0], VSEW[5:3], VTA[6], VMA[7]
# xs1[4:0] = AVL

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64U
RVTEST_CODE_BEGIN

# tests for VLEN=128bits, AVL < VLMAX

  # SEW=8, LMUL=1, VLMAX=16
  TEST_CASE(2, x5, 0x2, \
    li x2, 0x2; \
    li x4, 0x2; \
    vsetvl x5, x2, x4; \
  )

  # SEW=8, LMUL=2, VLMAX=32
  TEST_CASE(3, x5, 0x2, \
    li x2, 0x2; \
    li x4, 0x23; \
    vsetvl x5, x2, x4; \
  )

  # SEW=8, LMUL=1/2, VLMAX=8
  TEST_CASE(4, x5, 0x2, \
    li x2, 0x2; \
    li x4, 0xeb; \
    vsetvl x5, x2, x4; \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN

RVTEST_DATA_END
