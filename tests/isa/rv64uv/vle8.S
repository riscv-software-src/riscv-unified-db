# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# vle8.S
#-----------------------------------------------------------------------------
#
# Test vle8 instruction.
#
# vle8

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64UV
RVTEST_CODE_BEGIN

# Write tests for vle8

# SEW=8, LMUL=1. x6 should contain VL == 2 (AVL, since its < VLMAX==128)
# Use x5 to hold addresses
# v2 == 0x2d2c
# Store 0x2d2c to result[0..1] leaving other bits as 1
# Load 4-bytes from result into x2 to compare with expected value

  TEST_CASE(1, x2, 0xFFFFffffFFFF2d2c, \
    vsetivli x6, 2, e8, m1; \
    la      x5, input; \
    vle8.v  v2, (x5); \
    la      x5, result; \
    vse8.v  v2, (x5); \
    lw      x2, (x5); \
    )

  TEST_PASSFAIL

RVTEST_CODE_END

# Input data section.
# This section is optional, and this data is NOT saved in the output.
.data
  .balign 4
input:
  .word 0xBABA2d2c

# Output data section.
# This section is optional, but this data IS saved in the output.
RVTEST_DATA_BEGIN

result:
  .word -1

RVTEST_DATA_END
