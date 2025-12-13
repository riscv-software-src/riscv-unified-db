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

  TEST_CASE(1, x5, 0x2, \
    li x4, 0x2; \
    vsetvli x5, x4, 0x3; \
  )

  # vtypei = 0x23 -> VMA_VTA_VSEW_VLMUL == 0_0_100_011 -> SEW=RESERVED, LMUL=8
  # So vl should be zero
  TEST_CASE(2, x5, 0x0, \
    li x4, 0x2; \
    vsetvli x5, x4, 0x23; \
  )

  # vtypei = 0xeb-> VMA_VTA_VSEW_VLMUL == 1_1_101_011 -> SEW=RESERVED, LMUL=8
  # So vl should be zero
  TEST_CASE(3, x5, 0x0, \
    li x4, 0x2; \
    vsetvli x5, x4, 0xeb; \
  )

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN

RVTEST_DATA_END
