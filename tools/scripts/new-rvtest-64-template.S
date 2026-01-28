# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# See LICENSE for license details

#*****************************************************************************
# __INSTR__.S
#-----------------------------------------------------------------------------
#
# Test __INSTR__ instruction.
#
# __INSTR__

#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64UV
RVTEST_CODE_BEGIN

# Write tests for __INSTR__
  li      x3, 1         # x3 (gp) is TESTNUM register
  la      x5, input     # Use x5 to hold addresses.
  lw      x2, (x5)
  addi    x2, x2, 1     # Should be 45 in x2.
  la      x5, result
  sw      x2, (x5)      # Store result into memory overwriting 1s.
  li      x4, 45        # Desired result.
  bne     x2, x4, fail  # Fail out if doesn't match.
  RVTEST_PASS           # Signal success.
fail:
  RVTEST_FAIL

RVTEST_CODE_END

# Input data section.
# This section is optional, and this data is NOT saved in the output.
.data
  .balign 8
input:
  .word 44

# Output data section.
# This section is optional, but this data IS saved in the output.
RVTEST_DATA_BEGIN

result:
  .word -1

RVTEST_DATA_END
