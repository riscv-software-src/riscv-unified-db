# frozen_string_literals: true

# This file contains validation checks above and beyond what is checked
# by the schema. It can use the entire configuration (params, extension list, etc)
# to check for invalid scenerios.
#
# It should only be used for scenerios too complex to express in JSONSchema

# SXLEN must be specified if S is used
require_param :SXLEN if ext?(:S)

# SXLEN is fixed in RV32
assert SXLEN == 32 if ext?(:S) && XLEN == 32

# UXLEN should not be set unless U-mode is implemented
require_param :UXLEN if ext?(:U)

# UXLEN is fixed in RV32
assert [nil, 32].include?(UXLEN) if ext?(:U) && XLEN == 32

# is SXLEN is fixed to 32, then UXLEN cannot be > 32
assert [nil, 32].include?(UXLEN) if ext?(:S) && ext?(:U) && SXLEN == 32

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

require_param :S_MODE_ENDIANESS  if ext?(:S)
require_param :U_MODE_ENDIANESS  if ext?(:U)
require_param :VU_MODE_ENDIANESS if ext?(:H)
require_param :VS_MODE_ENDIANESS if ext?(:H)
require_param :SXLEN             if ext?(:S) && XLEN > 32
require_param :UXLEN             if ext?(:U) && XLEN > 32
require_param :VSXLEN            if ext?(:H) && XLEN > 32
require_param :VUXLEN            if ext?(:H) && XLEN > 32
require_param :ASID_WIDTH        if ext?(:S)
require_param :PMP_GRANULARITY   unless NUM_PMP_ENTRIES.zero?
require_param :NUM_EXTERNAL_GUEST_INTERRUPTS if ext?(:H)

require_ext :U if ext?(:S)
