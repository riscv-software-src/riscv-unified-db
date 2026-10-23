# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vadd.vi.S
#-----------------------------------------------------------------------------
#
# Verify that a signed vector immediate is extended to SEW, rather than XLEN.
# The RV32 wrapper exercises the SEW=64 case where this distinction matters.

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64UV
RVTEST_CODE_BEGIN

  # SEW=64, LMUL=1, VL=1.  Both halves of the stored element must be all ones.
  TEST_CASE(1, x2, -1, \
    vsetivli x0, 1, e64, m1; \
    vmv.v.i v2, 0; \
    vadd.vi v3, v2, -1; \
    la x5, result; \
    vse64.v v3, (x5); \
    lw x2, 0(x5); \
  )

  TEST_CASE(2, x2, -1, \
    vsetivli x0, 1, e64, m1; \
    vmv.v.i v2, 0; \
    vadd.vi v3, v2, -1; \
    la x5, result; \
    vse64.v v3, (x5); \
    lw x2, 4(x5); \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

RVTEST_DATA_BEGIN

  .balign 8
result:
  .dword -1

RVTEST_DATA_END
