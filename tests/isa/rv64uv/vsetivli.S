# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vsetivli.S
#-----------------------------------------------------------------------------
#
# Test vsetivli instruction.
#
# vsetivli xd, uimm, vtypei
# vtypei[7:0] = VLMUL[2:0], VSEW[5:3], VTA[6], VMA[7]
# uimm[4:0] = AVL

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64UV
RVTEST_CODE_BEGIN

# tests for VLEN=128bits, AVL < VLMAX

  TEST_CASE(2, x2, 0x2, \
    vsetivli x2, 0x2, 3; \
  )

  TEST_CASE(3, x2, 0x2, \
    vsetivli x2, 0x2, 0x23; \
  )

  TEST_CASE(4, x2, 0x2, \
    vsetivli x2, 0x2, 0xeb; \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN

RVTEST_DATA_END
