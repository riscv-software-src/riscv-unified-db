# frozen_string_literals: true

# This file contains validation checks above and beyond what is checked
# by the schema. It can use the entire configuration (params, extension list, etc)
# to check for invalid scenarios.
#
# It should only be used for scenarios too complex to express in JSONSchema

# SXLEN must be specified if S is used
require_param :SXLEN if ext?(:S)

# SXLEN is fixed in RV32
assert SXLEN == 32 if ext?(:S) && MXLEN == 32

# UXLEN should not be set unless U-mode is implemented
require_param :UXLEN if ext?(:U)

# UXLEN is fixed in RV32
assert [nil, 32].include?(UXLEN) if ext?(:U) && MXLEN == 32

# is SXLEN is fixed to 32, then UXLEN cannot be > 32
assert [nil, 32].include?(UXLEN) if ext?(:S) && ext?(:U) && SXLEN == 32

max_va_width =
  if ext?(:Sv57)
    57
  elsif ext?(:Sv48)
    48
  elsif ext?(:Sv39)
    39
  elsif ext?(:Sv32)
    32
  else
    PHYS_ADDR_WIDTH
  end
mtval_holds_va =
  REPORT_VA_IN_MTVAL_ON_BREAKPOINT ||
  REPORT_VA_IN_MTVAL_ON_LOAD_MISALIGNED ||
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_MISALIGNED ||
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_MISALIGNED ||
  REPORT_VA_IN_MTVAL_ON_LOAD_ACCESS_FAULT ||
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_ACCESS_FAULT ||
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_ACCESS_FAULT ||
  REPORT_VA_IN_MTVAL_ON_LOAD_PAGE_FAULT ||
  REPORT_VA_IN_MTVAL_ON_STORE_AMO_PAGE_FAULT ||
  REPORT_VA_IN_MTVAL_ON_INSTRUCTION_PAGE_FAULT ||
  ext?(:Sdext)

assert(MTVAL_WIDTH >= max_va_width) if mtval_holds_va

# 32 stands for ILEN below. Update this if/when instructions become longer than 32
assert(MTVAL_WIDTH >= [MXLEN, 32].min) if REPORT_ENCODING_IN_MTVAL_ON_ILLEGAL_INSTRUCTION

assert(COUNTENABLE_EN[0] == false) unless ext?(:Zicntr)
assert(COUNTENABLE_EN[2] == false) unless ext?(:Zicntr)
(3..31).each do |hpm_num|
  assert(COUNTENABLE_EN[hpm_num] == false) unless ext?(:Zihpm) && (NUM_HPM_COUNTERS > (hpm_num - 3))
end

assert(COUNTINHIBIT_EN[0] == false) unless ext?(:Zicntr)
assert(COUNTINHIBIT_EN[2] == false) unless ext?(:Zicntr)
(3..31).each do |hpm_num|
  assert(COUNTINHIBIT_EN[hpm_num] == false) unless ext?(:Zihpm) && (NUM_HPM_COUNTERS > (hpm_num - 3))
end

# check for conditionally required params
require_param :MUTABLE_MISA_A    if ext?(:A)
require_param :MUTABLE_MISA_B    if ext?(:B)
require_param :MUTABLE_MISA_C    if ext?(:C)
require_param :MUTABLE_MISA_D    if ext?(:D)
if ext?(:D) && MUTABLE_MISA_F
  assert MUTABLE_MISA_D # if F can be disabled, then D must also be mutable since D relies on F
end
require_param :MUTABLE_MISA_F    if ext?(:F)
require_param :MUTABLE_MISA_H    if ext?(:H)
require_param :MUTABLE_MISA_M    if ext?(:M)
# require_param :MUTABLE_MISA_S    if ext?(:S)  ## Needs definition of what happens
# require_param :MUTABLE_MISA_U    if ext?(:U)  ## Needs definition of what happens
require_param :MUTABLE_MISA_V    if ext?(:V)

require_param :S_MODE_ENDIANNESS  if ext?(:S)
require_param :U_MODE_ENDIANNESS  if ext?(:U)
require_param :VU_MODE_ENDIANNESS if ext?(:H)
require_param :VS_MODE_ENDIANNESS if ext?(:H)
require_param :SXLEN             if ext?(:S) && MXLEN > 32
require_param :UXLEN             if ext?(:U) && MXLEN > 32
require_param :VSXLEN            if ext?(:H) && MXLEN > 32
require_param :VUXLEN            if ext?(:H) && MXLEN > 32
require_param :ASID_WIDTH        if ext?(:S)
require_param :PMP_GRANULARITY   unless NUM_PMP_ENTRIES.zero?
require_param :NUM_EXTERNAL_GUEST_INTERRUPTS if ext?(:H)

require_ext :U if ext?(:S)
