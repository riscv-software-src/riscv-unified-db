# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vsetvli.S
#-----------------------------------------------------------------------------
#
# Test vsetvli instruction.
#
# vsetvli xd, xs1, vtypei
# vtypei[7:0] = VLMUL[2:0], VSEW[5:3], VTA[6], VMA[7]
# xs1[4:0] = AVL

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64U
RVTEST_CODE_BEGIN

# tests for VLEN=128bits, AVL < VLMAX

  TEST_CASE(2, x2, 0x2, \
    li x3, 0x2; \
    vsetvli x2, x3, 0x3; \
  )

  TEST_CASE(3, x2, 0x2, \
    li x3, 0x2; \
    vsetvli x2, x3, 0x23; \
  )

  TEST_CASE(4, x2, 0x2, \
    li x3, 0x2; \
    vsetvli x2, x3, 0xeb; \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN

RVTEST_DATA_END
