# CSR Parameter Extraction - RISC-V Optimized v4.3

**Category:** Control & Status Registers (CSR)  
**Format:** JSON array of parameter objects
**Scope:** RISC-V Standard Extensions (RV32/RV64, Privileged ISA 1.13+) 

## CORE OBJECTIVE (READ CAREFULLY)

Extract **ALL architectural parameters** from RISC-V CSR YAML specifications.

**Priority Order:**
1. **First:** Extract every field listed in the `fields:` section
2. **Then:** Extract field-level behavioral/WARL parameters
3. **Last:** Extract CSR-level constraints (only if significant)

Extract ONLY from specification text provided. DO NOT invent parameters or reference external sources.

 **CRITICAL FOR AGREEMENT:** Field completeness is crucial. Every field must have at least one parameter. Missing fields will significantly reduce agreement with other models. Count the fields in the YAML `fields:` section BEFORE starting extraction, then ensure every field has ≥1 parameter.

---

## FIELD EXTRACTION COMPLETENESS (MANDATORY)

**This section ensures agreement by preventing field omissions.**

**BEFORE EXTRACTING:**
1. Read the entire `fields:` section of the YAML
2. Count exact number of fields (do not estimate)
3. List field names explicitly
4. Allocate extraction for each field

**Example - hstatus.yaml (Hypervisor Status):**
```yaml
fields:
  VSXL:        ← Field 1: Vector Max XLEN in VS
  VTSR:        ← Field 2: Virtual Trap on SINVAL.VMA
  VTW:         ← Field 3: Virtual Trap on WFI
  VTVM:        ← Field 4: Virtual Trap on Virtual Memory Management
  VGEIN:       ← Field 5: Virtual Guest External Interrupt Number
  ...          (potentially more fields)
```

**MINIMUM EXTRACTION for 5-field CSR:**
- Each field MUST have ≥1 parameter
- Minimum total: 1.5 × 5 = 7-8 parameters
- Example allocation:
  - VSXL: 2 params (RESET_VALUE, LEGAL_VALUES)
  - VTSR: 2 params (RESET_VALUE, CONTROLS_TRAP)
  - VTW: 2 params (RESET_VALUE, CONTROLS_WAIT)
  - VTVM: 2 params (RESET_VALUE, CONTROLS_MEMORY)
  - VGEIN: 1-2 params (RESET_VALUE, or LEGAL_VALUES)

**CRITICAL CHECK:** Do NOT skip any field! If you skip VGEIN or VTVM, agreement drops.

**Example - pmpcfg0.yaml (Physical Memory Protection):**
Each pmpcfgX contains 4 (RV32) or 8 (RV64) PMP entries
- Field pmp0cfg contains: L, A, X, W, R bits
- Field pmp1cfg contains: L, A, X, W, R bits (for next entry)
- ...

**MINIMUM EXTRACTION for 8 entries (RV64 pmpcfg0):**
- At minimum, extract for EACH entry:
  - PMPCFG0_PMPX_TYPE_LEGAL_VALUES (e.g., PMPCFG0_PMP0_TYPE_LEGAL_VALUES)
  - PMPCFG0_PMPX_R_MEANING (e.g., PMPCFG0_PMP0_R_MEANING)
  - PMPCFG0_PMPX_W_MEANING (e.g., PMPCFG0_PMP0_W_MEANING)
  - PMPCFG0_PMPX_X_MEANING (e.g., PMPCFG0_PMP0_X_MEANING)
  - PMPCFG0_PMPX_L_CONTROLS_LOCK (e.g., PMPCFG0_PMP0_L_CONTROLS_LOCK)
- Total: 5 × 8 = 40 parameters minimum (or 8 × 1.5 = 12 minimum if grouping)

**DO NOT DO THIS:**
-  Extract only first entry and skip entries 1-7
- "PMPCFG0_ALL_TYPE_LEGAL_VALUES" (too generic, loses field specificity)
-  Skip fields because they're similar to previous ones

**DO THIS INSTEAD:**
-  PMPCFG0_PMP0_TYPE_LEGAL_VALUES: "0=OFF, 1=TOR, 2=NA4, 3=NAPOT"
-  PMPCFG0_PMP1_TYPE_LEGAL_VALUES: "0=OFF, 1=TOR, 2=NA4, 3=NAPOT"
-  (and so on for PMP2-PMP7)

---

## RISC-V FIELD TYPE TAXONOMY

**Critical:** RISC-V CSR fields fall into EXACT types. Recognize and extract these:

| Type | Meaning | RISC-V Context | Extract What |
|------|---------|-----------------|--------------|
| **RO** | Read-Only | Status bits, hardware-generated flags | ACCESS_TYPE, behavioral_impact of read |
| **RW** | Read-Write | User-controlled configuration | LEGAL_VALUES, RESET_VALUE, transformation rules |
| **RO-H** | Read-Only, Hardware Updates | Counters, interrupt status | Hardware update behavior, width constraints |
| **RW-H** | Read-Write, Hardware Updates | Mode bits affected by exceptions | Both user writes AND hardware updates |
| **RW-RH** | Read-Write, Reads are Hardware-driven | Complex interlock patterns | Read-side special behavior |
| **RW-R** | Read-Write, Hardware Resets | Event-triggered resets | Reset conditions and triggers |
| **WLRL** | Write-Legal-Read-Legal (RW with constraints) | WARL enforcement | Legal value set, illegal value handling |
| **WARL** | Write-Any-Read-Legal | Implemented via sw_write() logic | Legal/illegal mapping, field encoding |

**Never extract ambiguous "RW"—always determine actual RISC-V subtype.**

---

## RISC-V PRIVILEGE LEVEL EXTRACTION

For ANY field that changes behavior based on privilege:

**Extract as separate parameters:**

1. **{CSR}_{FIELD}_MACHINE_MODE**: Parameter value/behavior at Machine privilege (priv==3)
2. **{CSR}_{FIELD}_SUPERVISOR_MODE**: Parameter value/behavior at Supervisor privilege (priv==1)
3. **{CSR}_{FIELD}_USER_MODE**: Parameter value/behavior at User privilege (priv==0)

**Example - mstatus.SUM (Supervisor User Memory access):**
```
- Machine mode: always reads as 1 (MIE override)
- Supervisor mode: user-configurable (SUM=0 blocks U-space access, SUM=1 allows)
- User mode: always reads as 0 (no U-space control)
```

**Extract as:**
- MSTATUS_SUM_MACHINE_MODE_BEHAVIOR: "Always 1 (no control)"
- MSTATUS_SUM_SUPERVISOR_MODE_LEGAL_VALUES: "0 (block) or 1 (allow user memory access)"
- MSTATUS_SUM_USER_MODE_LEGAL_VALUES: "Always 0 (read-only)" or "N/A"

---

## RISC-V WARL LEGAL VALUE EXTRACTION

WARL (Write-Any-Read-Legal) is the most important RISC-V pattern. Extract precisely:

**If field has `sw_write()`:**
1. Extract WARL_LEGAL_VALUES (what values survive the write)
2. Extract WARL_ILLEGAL_VALUES (what values do NOT survive)
3. Extract WARL_MAPPING (how illegal values transform)
4. Extract CROSS_FIELD_CONSTRAINTS (if other fields affect legality)
5. Extract SIDE_EFFECTS (if write triggers hardware actions like TLB flush)

**Legal value detection:**
- If `sw_write()` returns `csr_value` unchanged → value is legal
- If `sw_write()` returns 0 or different value → value is illegal, maps to returned value
- If `sw_write()` returns `UNDEFINED_LEGAL_DETERMINISTIC` → implementation chooses legal value (NOT reject)
- If `sw_write()` has conditional `if (condition) return X else return Y` → Extract both branches

**UNDEFINED_LEGAL_DETERMINISTIC handling:**
- NOT the same as reject (return old value)
- Means: implementation has freedom to choose ANY legal value
- Extract as: "May return implementation-chosen legal value" with confidence 3-4
- Example: satp ASID write with illegal value → returns largest_allowed_asid or other valid ASID

**Example - satp.MODE in RV64:**
```yaml
sw_write(csr_value): |
  if (SATP_MODE_BARE && (csr_value.MODE == 0)) {
    # Mode 0 (bare) has constraints
    if (csr_value.ASID == 0 && csr_value.PPN == 0) {
      # Valid bare mode write
      if (CSR[satp].MODE != 0) {
        # Transitioning FROM translation TO bare
        invalidate_translations();  # SIDE EFFECT: TLB flush
      }
      return csr_value.MODE;  # Legal
    } else {
      return UNDEFINED_LEGAL_DETERMINISTIC;  # UNDEFINED (not reject!)
    }
  }
  else if (implemented?(ExtensionName::Sv39) && csr_value.MODE == 8) {
    # Sv39 mode (implementation-dependent available)
    if (CSR[satp].MODE == 0) {
      invalidate_translations();  # SIDE EFFECT: TLB flush on transition
    }
    return csr_value.MODE;  # Legal if Sv39 implemented
  }
  else {
    return UNDEFINED_LEGAL_DETERMINISTIC;  # UNDEFINED
  }
```

**Extract:**
- Name: SATP_MODE_WARL_LEGAL_VALUES
- Type: WARL_LEGAL_VALUES
- Value: "0 (bare, if ASID=0 and PPN=0), 1 (Sv32, if implemented), 8 (Sv39, if implemented), 9 (Sv48, if implemented), 10 (Sv57, if implemented)"
- Confidence: 4 (extension-dependent, cross-field constraints)

- Name: SATP_MODE_WARL_CROSS_FIELD_CONSTRAINT
- Type: WARL_CONSTRAINT
- Value: "When MODE=0 (Bare), ASID and PPN must both be 0; writes with MODE=0 and (ASID≠0 or PPN≠0) return UNDEFINED_LEGAL_DETERMINISTIC"
- Confidence: 5 (explicit in sw_write logic)

- Name: SATP_MODE_SIDE_EFFECT_TLB_INVALIDATION
- Type: BEHAVIORAL (SIDEEFFECT)
- Value: "Transitions involving MODE changes trigger implicit TLB and fetch buffer invalidation (as if sfence.vma executed)"
- Confidence: 5 (explicit in comments: "implicit sfence.vma occurs now")

---

## CROSS-FIELD CONSTRAINTS & SIDE EFFECTS (NEW)

**Some CSR writes depend on OTHER field values—extract these constraints:**

**Pattern 1: Multi-field validation**
```python
if (csr_value.FIELD_A == X && csr_value.FIELD_B == Y) {
  return csr_value;  # Legal only if both conditions met
} else {
  return UNDEFINED_LEGAL_DETERMINISTIC;  # Or reject
}
```
**Extract:** `{CSR}_{FIELD}_CROSS_FIELD_CONSTRAINT_WITH_{OTHER_FIELD}`

**Example (satp):**
- SATP_MODE_CROSS_FIELD_CONSTRAINT: "Bare mode (MODE=0) requires ASID=0 AND PPN=0"

**Pattern 2: Implicit side effects**
```python
if (condition) {
  invalidate_translations();   // TLB flush
  order_pgtbl_writes_before_vmafence();  // Memory barrier
}
return csr_value;
```
**Extract:** `{CSR}_{FIELD}_SIDE_EFFECT_{EFFECT_NAME}`

**Recognized side effects:**
- TLB_INVALIDATION: "Flushes translation lookaside buffer"
- FETCH_BUFFER_INVALIDATION: "Flushes instruction fetch cache"
- MEMORY_BARRIER: "Implicit memory fence (sfence.vma semantics)"
- INTERRUPT_PENDING: "Triggers pending interrupt check"
- PRIVILEGE_CHECK: "Re-evaluates memory protection rules"

**Example (satp):**
- SATP_MODE_SIDE_EFFECT_TLB_INVALIDATION: "MODE changes trigger TLB flush"
- SATP_MODE_SIDE_EFFECT_MEMORY_BARRIER: "Implicit sfence.vma semantics"

**Pattern 3: Implementation-defined results**
```python
if (illegal_condition) {
  return UNDEFINED_LEGAL_DETERMINISTIC;  // NOT reject!
} else if (special_case) {
  return map_to_largest_allowed_value();  // Special mapping
}
```
**Extract:** `{CSR}_{FIELD}_UNDEFINED_LEGAL_{BEHAVIOR}`

**Example (satp.ASID):**
- SATP_ASID_UNDEFINED_LEGAL_ALL_ONES: "Write all-1s maps to largest_allowed_asid"
- SATP_ASID_UNDEFINED_LEGAL_OVERFLOW: "Write value > largest_allowed_asid returns implementation-chosen legal ASID"

---

## RISC-V EXTENSION-CONDITIONAL EXTRACTION

Many CSR fields change BASED ON IMPLEMENTED EXTENSIONS.

**If field has `type():` or `sw_write():`:**

Extract parameters for EACH extension configuration:

1. **{CSR}_{FIELD}_IF_EXTENSION_{EXT_NAME}**: Parameter when extension is implemented
2. **{CSR}_{FIELD}_IF_NOT_EXTENSION_{EXT_NAME}**: Parameter when extension is NOT implemented

**Example - fcsr (Floating-Point Control) with F extension:**
```yaml
type(): |
  if (implemented?(Extension::F)) {
    return RW;
  }
  return RO;  # Hardwired to 0 if F not implemented
```

**Extract:**
- FCSR_IF_EXTENSION_F_ACCESS_TYPE: "RW (read-write control)"
- FCSR_IF_NOT_EXTENSION_F_ACCESS_TYPE: "RO hardwired to 0"
- Confidence: 5 (explicit in type() logic)

**RISC-V Extensions to watch for:**
- F: Floating-Point (affects fcsr, frm, fflags)
- D: Double-Precision (affects fcsr, frm, fflags)
- V: Vector (affects vtype, vl, vcsr)
- C: Compressed (affects certain decode behaviors)
- Zicsr: CSR Instructions (affects all CSRs - assume present unless marked RO)
- Hypervisor (H): affects hstatus, hedeleg, hideleg
- Debug (Sdtrig): affects trigger CSRs
- RVWMO (Memory Ordering): affects memory access semantics

---

## RISC-V COUNTER CSR SPECIAL EXTRACTION

Machine/Supervisor counters (mcycle, minstret, etc.) have special patterns:

**Always extract these parameters:**

1. **{COUNTER}_WIDTH_RV32**: 32-bit width (cycle counter uses [mh]cycle + [mh]cycleh pair)
2. **{COUNTER}_WIDTH_RV64**: 64-bit width (single register)
3. **{COUNTER}_HARDWARE_UPDATE**: "Automatically incremented by hardware on events"
4. **{COUNTER}_CANNOT_WRITE_INDIRECTLY**: "Only via specific CSR address, not indirect access"
5. **{COUNTER}_OVERFLOW_HANDLING**: "Wraps at 2^width" or similar

**Example - mcycle (Machine Cycle Counter):**
```
- MCYCLE_WIDTH_RV32: "32-bit (use MCYCLEH for upper 32 bits)"
- MCYCLE_WIDTH_RV64: "64-bit in single register"
- MCYCLE_HARDWARE_UPDATE: "Increments on every clock cycle, cannot be inhibited"
- MCYCLE_RESET_BEHAVIOR: "Reset via MCYCLE write, hardware then resumes incrementing"
```

---

## RISC-V INTERRUPT/EXCEPTION CSR EXTRACTION

For trap-related CSRs (mtvec, mcause, mtval, mepc, mstatus[MIE]):

**Always extract:**

1. **{CSR}_TRAP_VECTOR_ALIGNMENT**: "MTVEC-BASE must be 4-byte aligned"
2. **{CSR}_TRAP_VECTOR_MODE**: "MODE=0 (direct), MODE=1 (vectored)" + which modes supported
3. **{CSR}_MCAUSE_INTERRUPT_BIT**: "Interrupt=1, Exception=0 (MSB indicates type)"
4. **{CSR}_MEPC_ALIGNMENT**: "MEPC must store valid instruction addresses (4-byte or 2-byte for C)"
5. **{CSR}_NESTED_TRAP_HANDLING**: "xPPC field stores previous PC for nested traps" or "Not supported (xSPRIVILEGE field stores previous mode)"

**Example - mtvec (Machine Trap Vector):**
```yaml
fields:
  BASE:
    location: 63-2        # Bits 63-2 = trap vector base address
    description: |
      Base address of trap vector. Alignment depends on MODE.
    sw_write(csr_value): |
      if ((csr_value & 0x3) == 0) {  # MODE=0 (direct)
        return (csr_value & ~0x3);   # Clear mode bits
      } else if ((csr_value & 0x3) == 1) {  # MODE=1 (vectored)
        return (csr_value & ~0x3) | 1;      # Keep mode bit
      }
      return CSR[mtvec];  # Reject
```

**Extract:**
- MTVEC_BASE_RESET_VALUE: "0x0 (trap vector disabled until set)"
- MTVEC_MODE_LEGAL_VALUES: "0 (direct) or 1 (vectored)" [+ any other supported modes]
- MTVEC_BASE_ALIGNMENT_REQUIREMENT: "4-byte aligned (bits 1-0 ignored for base, used for mode)"
- MTVEC_MODE_CONTROLS_TRAP_DISPATCH: "MODE=0: exceptions jump to BASE. MODE=1: exceptions jump to BASE + 4*cause"
- Confidence: 5 (explicit in sw_write logic)

---

## RISC-V MEMORY PROTECTION CSR EXTRACTION

For PMP (Physical Memory Protection) CSRs (pmpcfg0, pmpaddr0-15):

**Always extract:**

1. **{PMPCFG}_ENTRY_COUNT**: "Each pmpcfgX register contains 4 entries (RV32) or 8 entries (RV64)"
2. **{PMPCFG}_PMP_ENTRY_N_TYPE_LEGAL_VALUES**: "OFF (0)=disabled, TOR (1)=top-of-range, NA4 (2)=4KB page, NAPOT (3)=naturally aligned power-of-2"
3. **{PMPCFG}_PMP_ENTRY_N_PERMISSION_R**: "R (read) bit=0 disallows reads, R=1 allows"
4. **{PMPCFG}_PMP_ENTRY_N_PERMISSION_W**: "W (write) bit=0 disallows writes, W=1 allows"
5. **{PMPCFG}_PMP_ENTRY_N_PERMISSION_X**: "X (execute) bit=0 disallows execution, X=1 allows"
6. **{PMPCFG}_PMP_ENTRY_N_LOCKED**: "L (lock) bit=1 makes this entry read-only until reset (prevents accidental changes)"

**Example - pmpcfg0 (RV32: 4×8-bit entries):**
```
- PMPCFG0_ENTRIES_PER_REGISTER: "4 entries (bits 7-0 for entry 0, bits 15-8 for entry 1, etc.)"
- PMPCFG0_PMP0_TYPE_LEGAL_VALUES: "0 (OFF), 1 (TOR), 2 (NA4), 3 (NAPOT)"
- PMPCFG0_PMP0_R_LEGAL_VALUES: "0 (read disallowed), 1 (read allowed)"
- PMPCFG0_PMP0_W_LEGAL_VALUES: "0 (write disallowed), 1 (write allowed)"
- PMPCFG0_PMP0_X_LEGAL_VALUES: "0 (execute disallowed), 1 (execute allowed)"
- PMPCFG0_PMP0_L_CONTROLS_WRITE_PROTECTION: "If L=1, entry becomes read-only (locked) until reset"
```

**PMPCFG0 CRITICAL EXTRACTION RULES:**

 **Field Name Format:** In YAML, fields are named `pmp0cfg`, `pmp1cfg`, ..., `pmp7cfg` (RV64 has 8 entries per register).

**Extract EVERY entry (0-7 for RV64):**
- For each entry N (0 through 7):
  - PMPCFG0_PMPNCFG_RESET_VALUE (Confidence 5)
  - PMPCFG0_PMPNCFG_ACCESS_TYPE (Confidence 5)
  - PMPCFG0_PMPNCFG_LEGAL_VALUES (Confidence 4, from TYPE bits: 0/1/2/3)
  - PMPCFG0_PMPNCFG_LOCKED (Confidence 5, describes L bit lock behavior)

**Minimum for pmpcfg0 (RV64, 8 fields):** Extract 24+ parameters (3 per entry minimum)

**Example Naming (CORRECT):**
```
 PMPCFG0_PMP0CFG_RESET_VALUE
 PMPCFG0_PMP1CFG_LEGAL_VALUES
 PMPCFG0_PMP7CFG_ACCESS_TYPE
 PMPCFG0_PMP2CFG_LOCKED
```

**Example Naming (WRONG - avoid):**
```
 PMPCFG0_PMP0CFG (incomplete)
 PMPCFG0_PMPCFG0_LOCKED (wrong field name format)
 PMPCFG0_ENTRY_0_R_BIT (too granular for sub-bit fields)
```

---

## RISC-V HYPERVISOR STATUS (HSTATUS) EXTRACTION

**Critical for Low-Agreement CSR:**

hstatus is a Hypervisor extension CSR with multiple independent fields:

**ALWAYS extract for hstatus:**
1. HSTATUS_VSXL_LEGAL_VALUES (extension-conditional: 0=32, 1=64)
2. HSTATUS_VSXL_ACCESS_TYPE (RO or RW depending on implementation)
3. HSTATUS_VSXL_RESET_VALUE (Confidence 4, implementation-dependent)
4. HSTATUS_VTSR_RESET_VALUE (Confidence 5)
5. HSTATUS_VTSR_ACCESS_TYPE (Confidence 5, type: RW)
6. HSTATUS_VTSR_CONTROLS_TRAP (Confidence 5, "causes Virtual Instruction exception")
7. HSTATUS_VTW_RESET_VALUE (Confidence 5)
8. HSTATUS_VTW_ACCESS_TYPE (Confidence 5, type: RW)
9. HSTATUS_VTW_CONTROLS_TRAP (Confidence 5, "causes Virtual Instruction exception")
10. HSTATUS_VTVM_RESET_VALUE (Confidence 5)
11. HSTATUS_VTVM_ACCESS_TYPE (Confidence 5, type: RW)
12. HSTATUS_VTVM_CONTROLS_TRAP (Confidence 5, "controls VirtualMachineMemory behavior")

**Minimum for hstatus (4 fields):** Extract 12+ parameters (3 per field minimum)

**Common hstatus Fields (Don't Miss):**
- VSXL: VS-mode XLEN (bits 33-32)
- VTSR: Virtual Trap SRET (bit 22)
- VTW: Virtual Trap WFI (bit 21)
- VTVM: Virtual Trap VM instructions (bit 20)

---

## RISC-V VIRTUAL MEMORY CSR EXTRACTION

For satp (Supervisor Address Translation and Protection):

**Critical: SATP has CROSS-FIELD CONSTRAINTS and SIDE EFFECTS—extract all:**

1. **SATP_MODE_RV32_LEGAL_VALUES**: "0 (bare/no translation), 1 (Sv32, if implemented)"
   - Sv32 is NOT guaranteed; only legal if `implemented?(ExtensionName::Sv32)`
   - Confidence: 4 (extension-dependent)

2. **SATP_MODE_RV64_LEGAL_VALUES**: "0 (bare), 8 (Sv39, if implemented), 9 (Sv48, if implemented), 10 (Sv57, if implemented)"
   - Each mode requires explicit extension check
   - Confidence: 4 (extension-dependent)

3. **SATP_ASID_FIELD_LEGAL_VALUES**: "Depends on XLEN and system configuration; RV32: 0-511, RV64: typically 0-65535"
   - Reset: `UNDEFINED_LEGAL` (implementation-defined)
   - Confidence: 4 (implementation-dependent)

4. **SATP_PPN_FIELD_MEANING**: "Physical page number of root page table; must be valid page table base (implementation-dependent)"
   - Reset: `UNDEFINED_LEGAL` (implementation-defined)
   - Confidence: 4 (implementation-dependent)

5. **SATP_MODE_CONTROLS_ADDRESS_TRANSLATION**: "MODE=0: physical address = virtual address. MODE!=0: MMU performs page walk starting at PPN"
   - Confidence: 5 (explicit in description)

6. **SATP_CROSS_FIELD_CONSTRAINT_BARE_MODE**: "When MODE=0, ASID and PPN must both be 0; otherwise write is UNDEFINED_LEGAL_DETERMINISTIC (implementation chooses legal value)"
   - This is CRITICAL: write doesn't reject, it returns UNDEFINED_LEGAL_DETERMINISTIC
   - Confidence: 5 (explicit in sw_write() logic)

7. **SATP_MODE_SIDE_EFFECT_TLB_INVALIDATION**: "When switching FROM Bare mode (MODE=0) to translation-enabled mode, implicit sfence.vma executes; TLB and fetch buffers invalidated"
   - Confidence: 5 (explicit in sw_write() comments: "implicit sfence.vma occurs now")

8. **SATP_ASID_WRITE_BEHAVIOR_ALL_ONES**: "When write all-1s to ASID field, maps to largest_allowed_asid; other illegal values return UNDEFINED_LEGAL_DETERMINISTIC"
   - Confidence: 5 (explicit in sw_write() logic)

**Example - Actual satp extraction:**
```
- SATP_MODE_WARL_LEGAL_VALUES: "0 (bare), plus any of [1 (Sv32), 8 (Sv39), 9 (Sv48), 10 (Sv57)] based on implemented extensions"
- SATP_MODE_WARL_CROSS_FIELD_CONSTRAINT: "If MODE=0, writes requiring non-zero ASID or PPN return UNDEFINED_LEGAL_DETERMINISTIC"
- SATP_MODE_SIDE_EFFECT: "MODE change to/from 0 triggers implicit TLB invalidation via sfence.vma semantics"
- SATP_ASID_WRITE_CONSTRAINT_ALL_ONES: "Write value all-1s maps to maximum legal ASID; other illegal values map to UNDEFINED_LEGAL_DETERMINISTIC"
- SATP_PPN_WRITE_CONSTRAINT_BARE_MODE: "In MODE=0, PPN must be 0; non-zero PPN with MODE=0 causes UNDEFINED_LEGAL_DETERMINISTIC return"
```

---

## RISC-V DEBUG CSR EXTRACTION

For dcsr (Debug Control and Status), a critical and complex CSR:

**Always extract (all 18 fields):**

1. **DCSR_XDEBUGVER_FIELD_MEANING**: "Debug implementation version (read-only)"
2. **DCSR_EBREAKM_CONTROLS**: "When 1, EBREAK in M-mode enters debugger. When 0, raises exception"
3. **DCSR_EBREAKS_CONTROLS**: "When 1, EBREAK in S-mode enters debugger. When 0, raises exception"
4. **DCSR_EBREAKU_CONTROLS**: "When 1, EBREAK in U-mode enters debugger. When 0, raises exception"
5. **DCSR_STOPCYCLE_CONTROLS**: "When 1, cycle counter stops during debug mode"
6. **DCSR_STOPTIME_CONTROLS**: "When 1, time register stops during debug mode"
7. **DCSR_CAUSE_FIELD_LEGAL_VALUES**: "Cause codes: 1=EBREAK, 2=Trigger, 3=Halt, 4=Restart, 5=Step, 6=Reset"
8. **DCSR_V_FIELD_MEANING**: "Indicates virtualization context (V-extension or Hypervisor)"
9. **DCSR_MPRVEN_CONTROLS**: "When 1, apply MPP privilege level to memory protection checks"
10. **DCSR_NMIP_FIELD_MEANING**: "NMI pending flag (read-only from debug, set by external interrupt)"
11. **DCSR_STEP_CONTROLS**: "When 1, hart single-steps after resuming from debug mode"
12. **DCSR_PRV_FIELD_LEGAL_VALUES**: "Privilege level before debug: 0=U, 1=S, 3=M"
13. **DCSR_DPC_FIELD_MEANING**: "Debug PC: address of instruction that caused debug entry or is being stepped"
14. **DCSR_DSCRATCH_FIELD_PURPOSE**: "Debug scratch register for debugger use (read-write, no side effects)"




**Extract in this EXACT order** (most to least important):

### PRIORITY 0: RISC-V Architectural Categories (NEW - Before all others)

**These must be extracted for MAXIMUM agreement:**

1. **CSR Class & Privilege Level** (Which privilege mode owns this CSR?)
   - Machine-level CSRs: mXXX (0x3xx addresses)
   - Supervisor-level CSRs: sXXX (0x1xx addresses)
   - User-level CSRs: uXXX (0x0xx addresses)
   - Hypervisor CSRs: hXXX (0x6xx addresses)
   - Debug CSRs: dXXX (special addresses)
   
2. **Field Width Behavior**
   - 32-bit and 64-bit variance (location_rv32 vs location_rv64)
   - If location changes between RV32/RV64, extract BOTH

3. **Type Classification (MUST BE EXACT)**
   - Is this truly RO, RW, RO-H, RW-H, RW-RH, RW-R, WARL, or WLRL?
   - Extract actual type, NOT generic assumption

4. **WARL/WLRL Presence**
   - Does field have sw_write()? → WARL field
   - Does field reject writes? → WARL field
   - Is type RW-R, RW-RH, or similar? → Restricted field
   - Extract mapping rules EXACTLY from sw_write() logic

### PRIORITY 1: WARL Parameters (Write-Any-Read-Legal)
If field has `sw_write()` or type is `RW-*`:
1. What values are **legally accepted**? (LEGAL_VALUES)
2. What values are **rejected/transformed**? (ILLEGAL_VALUES or TRANSFORMATION)
3. If transformation occurs, what's the mapping?

**Confidence: Always 4-5 for WARL (explicit in code)**

### PRIORITY 2: Access Type & Reset Value
For EVERY field:
- What's the access type? (RO, RW, RO-H, RW-H, RW-RH, RW-R)
- What's the reset value?

**Confidence: Always 5 (explicit in YAML)**

### PRIORITY 3: Legal Values (if not WARL)
If field doesn't have WARL logic but description mentions valid values:
- What specific values/ranges are valid?
- Quote must use: "must be", "valid values are", "legal", "permitted"

**Confidence: 4-5 only if explicitly listed**

### PRIORITY 4: Behavioral Parameters
If field description mentions behavior (controls, enables, affects):
- Use ONLY if description explicitly states behavior
- Must be tied to actual CSR operation (trap, interrupt, memory, execution)

**Confidence: 3-4 (reasonable inference)**

### PRIORITY 5: Don't Extract
- Implementation-specific details
- Generic documentation filler
- Invented parameters without spec support


---

## EXTRACTION PRIORITY (CRITICAL FOR CONSISTENCY)

**Use ONLY these categories** (no others):

| Category | Definition | Extract When | Confidence |
|----------|-----------|-------------|-----------|
| **TRAP** | Field affects exception/interrupt/trap behavior | Description mentions "trap", "exception", "interrupt", "handler", "cause" | 5 |
| **MEMORY** | Field affects address translation or memory access semantics | Description mentions "translation", "memory", "page", "address", "physical" | 5 |
| **EXECUTION** | Field affects instruction execution (not memory) | Description mentions "instruction", "execute", "operation", "behavior" | 4 |
| **STATE** | Field affects processor state/status | Description mentions "status", "state", "mode", "privilege" | 4 |
| **ACCESS** | Field controls read/write access permissions | Description mentions "readable", "writable", "accessible", "permission" | 5 |
| **CONSTRAINT** | Field constrains values but no execution impact | Field type is RO or reset_value specified, no behavioral keywords | 5 |
| **SIDEEFFECT** | Field write triggers implicit hardware actions (TLB flush, memory barriers) | Code mentions `invalidate_translations()`, `order_pgtbl_writes()`, `sfence.vma`, or "implicit" behavior | 5 |

**DO NOT USE:**
- NONE (always pick a category)
- SEMANTIC (too vague)
- OTHER (use exact category)
- Multiple categories (pick ONE most specific—though SIDEEFFECT can pair with others)

**Example Distinctions:**
- mcause.CAUSE describes WHY trap occurred → **TRAP** (not STATE)
- mstatus.MIE controls if interrupts happen → **TRAP** (not STATE)
- satp.MODE controls translation mechanism → **MEMORY** (not STATE)
- satp.MODE write invalidates TLB (implicit sfence.vma) → **SIDEEFFECT** (in addition to MEMORY)
- frm.ROUNDINGMODE affects math behavior → **EXECUTION** (not STATE)

---

## CONFIDENCE SCORING - EXPLICIT RUBRIC

**Score 5 (CERTAIN):** Use for:
- Access type (RO/RW explicitly in type field)
- Reset value (reset_value explicitly stated)
- WARL logic (sw_write() code present)
- Explicit list in description: "Valid values are: 0, 1, 2"

**Score 4 (CONFIDENT):** Use for:
- Legal values inferred from sw_write() logic but not explicitly listed
- Behavioral impact clearly stated: "controls X", "enables X"
- WARL transformation logic clearly present
- Type is conditional (type(): ...) with clear logic

**Score 3 (REASONABLE):** Use for:
- Legal values partially documented: "typically 0 or 1, but implementation-dependent"
- Behavioral impact strongly implied: description mentions "affects" or "impacts"
- Alignment requirements inferred from location field
- DO NOT go below 3 for any extraction

**Score 2 or Below:** DO NOT EXTRACT
- High inference required
- Ambiguous or contradictory spec text
- Implementation-dependent without clear guidance

**When in doubt:** Extract at confidence 3, not higher. Don't invent certainty.

---

## LEGAL VALUES - DISAMBIGUATION RULES

When spec is ambiguous about legal values, use this priority:

**Priority A: Explicit Enumeration** (Confidence 5)
```
"Valid values are: 0=OFF, 1=ON, 2=AUTO"
```
→ Extract exactly: 0, 1, 2

**Priority B: Range + Constraints** (Confidence 4)
```
"0 to 63, must be power-of-2 aligned"
```
→ Extract: 0, 2, 4, 8, 16, 32, etc. (if deterministic)
→ OR extract as: "power-of-2 multiples from 0 to 63"

**Priority C: WARL Logic** (Confidence 4)
```
sw_write() shows: if (value > 31) return 0; else return value;
```
→ Extract: "0 to 31 are legal, >31 map to 0"

**Priority D: Description Only** (Confidence 3)
```
"Should be non-zero for most implementations"
```
→ Extract: "implementation-dependent, typically non-zero"
→ OR skip if too vague

**Priority E: Don't Extract** (Confidence < 3)
```
"May be vendor-specific"
```
→ Skip entirely

---

## PATTERN EMPHASIS ORDER

### Most Important (Extract ALL if present)
1. WARL validation in sw_write()
2. Reset values
3. Access type (RO vs RW)
4. Explicitly enumerated legal values
5. Mode/privilege-dependent behavior

### Important (Extract if clear)
6. Alignment requirements
7. Field aliases to other CSRs
8. Extension-conditional access
9. Hardware update behavior
10. Trap/exception control

### Nice-to-Have (Extract only if explicit)
11. Transformation logic (not just reject)
12. Cross-CSR constraints
13. Counter/enable relationships
14. Indirect CSR access

### Never Extract (Even if mentioned)
- Implementation vendor details
- Micro-architecture specifics
- Informal suggestions ("should", "typically")
- Generic documentation ("this field controls X" without detail)

---

## CONSISTENCY CHECKLIST - ENFORCE THIS

Before outputting JSON, verify:

**For EACH field:**
- [ ] Has at least 1 parameter (ideally 2-3)
- [ ] At least one parameter is CONSTRAINT or WARL (not just behavioral)
- [ ] Confidence scores realistic (not all 5s)
- [ ] Behavioral_impact from defined list only
- [ ] No invented parameter names

**For EVERY parameter:**
- [ ] Name follows {CSR}_{FIELD}_{SEMANTIC} exactly
- [ ] Semantic_suffix in allowed list
- [ ] Spec_quote contains imperative verb (must, may, shall, required, controls, enables, affects)
- [ ] Confidence >= 3 (confidence < 3 → skip)
- [ ] No paraphrasing (exact quote or don't extract)
- [ ] Not duplicate of another parameter in list

**Overall:**
- [ ] Minimum count: 1.5 × number of fields
- [ ] satp (3 fields) = minimum 5 parameters
- [ ] pmpcfg0 (8 fields) = minimum 12 parameters
- [ ] dcsr (18 fields) = minimum 27 parameters
- [ ] Max parameters: never exceed 4 × number of fields

### STEP 1: List All Fields
Look at the `fields:` section in the YAML. List every field exactly as shown.

**Example - satp.yaml:**
```yaml
fields:
  MODE:          ← Field 1
  ASID:          ← Field 2  
  PPN:           ← Field 3
```
**You MUST extract a parameter for EVERY field listed.**

### STEP 2: Extract Core Parameters for Each Field
For each field, ALWAYS extract:
1. **Field existence** - Name, location (bit position), access type (RO/RW/etc)
2. **Legal values** - What values can the field hold?
3. **Reset value** - What is the default?
4. **Access permissions** - Is it read-only, write-only, or read-write?

### STEP 3: Extract WARL Parameters (if field is Write-Any-Read-Legal)
If field has `sw_write()` function or type contains "RW-":
- What writes are accepted?
- What writes are rejected or transformed?
- How do illegal values map to legal ones?

### STEP 4: Extract Behavioral Parameters (if applicable)
If field description mentions:
- "controls...", "enables...", "affects..." → Extract behavioral impact
- "required", "must", "shall" → Extract constraint

### STEP 5: Validate Completeness
**CHECKSUM:** Expected parameter count = (1.5-3 × number of fields)

For satp (3 fields): Extract 5-9 parameters  
For dcsr (18 fields): Extract 27-54 parameters  
For pmpcfg0 (8 fields): Extract 12-24 parameters

---

## PARAMETER NAMING RULES

Parameter names MUST follow: **{CSR_NAME}_{FIELD_NAME}_{SEMANTIC_SUFFIX}**

**CSR_NAME:** Exact uppercase name from YAML (e.g., MEPC, MSTATUS, MTVEC)

**FIELD_NAME:** Exact uppercase field name from YAML, or "ALL" for CSR-level

**SEMANTIC_SUFFIX - ALLOWED ONLY (in priority order):**
1. RESET_VALUE - Default/initial value
2. ACCESS_TYPE - RO, RW, RO-H, RW-H, RW-RH, RW-R
3. LEGAL_VALUES - Valid range/set of values
4. ILLEGAL_VALUES - Invalid values (if documented)
5. ALIGNMENT_REQUIREMENT - Bit or byte alignment needed
6. ENABLES_X - Enables feature X (e.g., INTERRUPTS, TRANSLATION)
7. CONTROLS_X - Controls behavior X (e.g., EXCEPTION_HANDLING)
8. REQUIRES_X - Prerequisite X required (e.g., EXTENSION_IMPLEMENTED)

**CORRECT EXAMPLES:**
- SATP_MODE_LEGAL_VALUES (not SATP_MODE_CONSTRAINT)
- SATP_MODE_CONTROLS_TRANSLATION (not SATP_MODE_BEHAVIOR)
- PMPCFG0_PMP0CFG_RESET_VALUE (not PMPCFG0_CONFIG_RESET)
- DCSR_CAUSE_LEGAL_VALUES (not DCSR_CAUSE_OPTIONS)

**CRITICAL NAMING PATTERNS FOR HIGH AGREEMENT:**

**For Counter CSRs (mcycle, minstret, etc.):**
- `{COUNTER}_{FIELD}_WIDTH_RV32` (e.g., MCYCLE_ALL_WIDTH_RV32)
- `{COUNTER}_{FIELD}_WIDTH_RV64` (e.g., MCYCLE_ALL_WIDTH_RV64)
- `{COUNTER}_{FIELD}_HARDWARE_UPDATE` (e.g., MCYCLE_ALL_HARDWARE_UPDATE)

**For PMPxx CSRs (pmpcfg0, pmpcfg4, etc.):**
- `{CSR}_PMPX_TYPE_LEGAL_VALUES` (e.g., PMPCFG0_PMP0_TYPE_LEGAL_VALUES)
- `{CSR}_PMPX_R_ENABLES_READ` (e.g., PMPCFG0_PMP0_R_ENABLES_READ)
- `{CSR}_PMPX_W_ENABLES_WRITE` (e.g., PMPCFG0_PMP0_W_ENABLES_WRITE)
- `{CSR}_PMPX_X_ENABLES_EXECUTE` (e.g., PMPCFG0_PMP0_X_ENABLES_EXECUTE)
- `{CSR}_PMPX_L_CONTROLS_LOCK` (e.g., PMPCFG0_PMP0_L_CONTROLS_LOCK)

**For Hypervisor CSRs (hstatus, etc.):**
- `{CSR}_VSXL_LEGAL_VALUES` (e.g., HSTATUS_VSXL_LEGAL_VALUES)
- `{CSR}_VTSR_CONTROLS_TRAP` (e.g., HSTATUS_VTSR_CONTROLS_TRAP)
- `{CSR}_VTW_CONTROLS_WAIT` (e.g., HSTATUS_VTW_CONTROLS_WAIT)
- `{CSR}_VTVM_CONTROLS_MEMORY` (e.g., HSTATUS_VTVM_CONTROLS_MEMORY)

**For Debug CSR (dcsr):**
- `DCSR_{FIELD}_RESET_VALUE` (e.g., DCSR_CAUSE_RESET_VALUE)
- `DCSR_{FIELD}_LEGAL_VALUES` (e.g., DCSR_CAUSE_LEGAL_VALUES)
- `DCSR_{FIELD}_CONTROLS_BEHAVIOR` (e.g., DCSR_STEP_CONTROLS_SINGLE_STEP)

**For Virtual Memory (satp):**
- `SATP_MODE_LEGAL_VALUES_RV32` (e.g., "0 (Bare), 1 (Sv32 if implemented)")
- `SATP_MODE_LEGAL_VALUES_RV64` (e.g., "0 (Bare), 8 (Sv39 if implemented), 9, 10")
- `SATP_ASID_LEGAL_VALUES` (e.g., "0 to implementation-defined maximum")
- `SATP_PPN_MEANING` (e.g., "Physical page number of root page table")

**WRONG (DO NOT USE):**
- SATP_MODE_CONSTRAINT (vague suffix)
- SATP_LEGAL (incomplete name)
- SATP_ALL (incomplete)
- satp_mode_legal_values (lowercase)
- PMPCFG0_ENTRY0_TYPE (wrong - use PMPCFG0_PMP0_TYPE)
- HSTATUS_BITS (too generic)
- DCSR_ALL_CONTROLS (incomplete - name specific field)

---

## EXTRACTION RULES

---

## CORE EXTRACTION RULES

### RULE 1: Extract Every Field's Basic Parameters
For each field in `fields:` section:
1. Field existence (FIELD_NAME, location, type)
2. Reset value (from `reset_value:`)
3. Access type (from `type:`)
4. Legal values (from `description:`)

### RULE 2: Use Exact Names from YAML
- CSR_NAME: Exact uppercase from filename (satp, dcsr, pmpcfg0)
- FIELD_NAME: Exact uppercase from `fields:` key (MODE, ASID, CAUSE, DEBUGVER)
- DO NOT abbreviate, rename, or invent field names

### RULE 3: Write Spec Quote First
For every parameter:
1. Find exact text in YAML
2. Quote must contain a verb: must, may, shall, required, controls, enables, affects
3. Quote must support the parameter claim
4. Copy quote exactly (no paraphrasing)

### RULE 4: Identify Parameter Name Before Extracting
For each parameter:
1. Select CSR name from filename
2. Select field name from YAML fields section
3. Choose semantic suffix from allowed list (top of this section)
4. Verify combination matches format: CSR_FIELD_SEMANTIC
5. Verify semantic suffix is in allowed list
6. ONLY THEN extract parameters matching this name

### RULE 5: Stop Hallucinating Behavioral Parameters
DO NOT EXTRACT if:
- Parameter name is not in specification (invented)
- Spec quote doesn't actually mention the behavior
- You're inferring without explicit evidence
- Field is just documentation filler

**INSTEAD:** Focus on what's EXPLICITLY stated:
- "The valid values are X, Y, Z" → Extract LEGAL_VALUES
- "Reset to zero" → Extract RESET_VALUE
- "Read-only" → Extract ACCESS_TYPE
- "Controls interrupt handling" → Extract CONTROLS_INTERRUPTS (only if spec says so)

---

## OUTPUT SCHEMA

JSON array of objects:

```json
[
  {
    "name": "string (CSR_FIELD_SEMANTIC format)",
    "csr_name": "string (uppercase)",
    "field_name": "string (uppercase) or ALL",
    "description": "1-2 sentence summary",
    "type": "WARL_LEGAL_VALUES | WARL_ILLEGAL_VALUES | WARL_MAPPING | WARL_CONSTRAINT | WARL_SIDEEFFECT | CONSTRAINT | BEHAVIORAL | UNDEFINED_LEGAL",
    "behavioral_impact": "TRAP | ACCESS | STATE | EXECUTION | MEMORY | CONSTRAINT | SIDEEFFECT",
    "spec_quote": "exact quote from YAML specification",
    "spec_location": "YAML file path or section reference",
    "confidence": 1-5 (5=certain, 1=uncertain),
    "is_explicit": true (named in spec) or false (derived),
    "cross_field_constraints": "if applicable, describe dependencies on other fields",
    "side_effects": "if applicable, describe hardware actions triggered (TLB_INVALIDATION, MEMORY_BARRIER, etc.)"
  }
]
```

### Field Definitions

| Field | Meaning | Example |
|-------|---------|---------|
| name | Parameter identifier | MEPC_ALL_LEGAL_VALUES or SATP_MODE_CROSS_FIELD_CONSTRAINT |
| csr_name | CSR this belongs to | MEPC, SATP |
| field_name | Field within CSR | ALL, PC, MIE, MODE |
| description | What constraint/behavior it defines | "Legal MEPC values must be instruction-aligned" |
| type | Category of parameter | WARL_LEGAL_VALUES, WARL_CONSTRAINT, BEHAVIORAL, UNDEFINED_LEGAL |
| behavioral_impact | Execution impact | TRAP, STATE, MEMORY, SIDEEFFECT |
| spec_quote | Exact spec text (no edits) | "Written with the PC of an instruction on exception" |
| spec_location | Where in YAML | mepc.yaml fields.PC.description |
| confidence | Extraction certainty | 5 (certain), 3 (clear), 2 (inferred) |
| is_explicit | Named vs derived | true (spec says "legal values"), false (inferred) |
| cross_field_constraints | Dependencies on OTHER fields | "SATP_MODE=0 requires ASID=0 AND PPN=0" (NEW) |
| side_effects | Implicit hardware actions | "TLB_INVALIDATION when transitioning FROM Bare mode" (NEW) |

---

## YAML FIELD STRUCTURE

CSR YAML files use this structure for each field:

```yaml
fields:
  FIELDNAME:
    location: start-end                # Bit positions in CSR
    location_rv32: bit_range_32bit     # Alternative for 32-bit RISC-V
    location_rv64: bit_range_64bit     # Alternative for 64-bit RISC-V
    alias: other_csr.FIELDNAME         # Shared storage with another CSR
    description: |                     # Field behavioral description
      Multi-line text describing...
    type: RW | RO | RW-H | RO-H | RW-RH | RW-R
    type(): |                          # Dynamic type (if varies by implementation)
      if (implemented?(ExtensionName::Sv39)) {
        return RW;
      }
      return RO;
    reset_value: hex_or_integer        # Fixed reset/initial value
    reset_value(): |                   # Dynamic reset (if varies by configuration)
      return computed_reset_value
    sw_write(csr_value): |             # WARL write mapping logic
      # Most IMPORTANT section: defines which writes are legal and how they map
      if (<condition_for_legal_value>) {
        return csr_value.FIELDNAME;    # Accept write as-is
      } else if (<condition_for_alternative>) {
        return <mapped_value>;         # Transform write to legal value
      } else {
        return CSR[name].FIELDNAME;    # Reject write, keep current value
      }
    sw_read(): |                       # Read-side logic (less common)
      if (mode() == PrivilegeMode::U) {
        raise(ExceptionCode::IllegalInstruction);
      }
      return read_counter();           # May call built-in functions
```

**Field Type Legend:**
- RO: Read-Only
- RW: Read-Write
- RO-H: Read-Only (hardware updates)
- RW-H: Read-Write (hardware updates)
- RW-RH: Read-Write, hardware clears read portion
- RW-R: Read-Write, hardware resets

**Key extraction points:**
1. `description:` field contains behavioral spec quotes
2. `sw_write():` contains WARL mapping logic (write-any-read-legal)
3. `type:` or `type():` defines read/write access model
4. `reset_value:` specifies initialization
5. `location` fields specify bit positions (important for ALIGNMENT constraints)

### Step 2: Extract CSR-Level Parameters
Look for CSR-wide constraints in description:
- Reset value requirements
- Initialization constraints
- Privilege level implications
- Alignment/width constraints

Name as: **{CSR_NAME}_ALL_{SEMANTIC}**

Example:
```
Name: MEPC_ALL_LEGAL_VALUES
From: mepc.yaml description saying "legal values must be instruction addresses"
```

### Step 3: Extract Field-Level Parameters
For EACH field under `fields:` section:

#### PRIORITY 1: WARL Fields (Highest)
Look for ANY of these indicators:
- `sw_write():` function present → Contains WARL mapping logic
- `type: RW-RH` or `type: RW-R` → Read-Write with restrictions
- Description mentions "write-any-read-legal" or "WARL"
- Description mentions "may be" or "implementation-specific" → Indicates legal value variation

Extract from field:
1. **LEGAL_VALUES**: From description, what values are valid?
   - Example: "Only values 0 or 1 are legal"
   - Example: "Values must be 4-byte aligned"
2. **ILLEGAL_VALUES**: What values are NOT legal?
   - Extract from sw_write() logic showing what's rejected
3. **MAPPING**: From sw_write(), how do illegal values transform?
   - Example: "Illegal values round down to nearest aligned address"

Name as: **{CSR_NAME}_{FIELD_NAME}_{SEMANTIC}**

#### PRIORITY 2: Behavioral Fields
If field description indicates behavior changes:
- "...controls..." → Use CONTROLS_X
- "...enables/disables..." → Use ENABLES_X or AFFECTS_X
- "...impacts exception..." → Use AFFECTS_TRAP or CONTROLS_TRAP
- State transitions, trap generation, permission changes

#### PRIORITY 3: Constraint Fields
If field has constraints but no behavior:
- Alignment requirements → ALIGNMENT_REQUIREMENT
- Reset values → RESET_VALUE
- Access type (RO vs RW) → ACCESS_TYPE
- Width constraints → WIDTH

### Step 4: Verify Spec Quotes
For EVERY parameter:
- Copy exact text from `description:` field or `sw_write()` logic
- Must contain imperative language (must, may, shall, required, allowed)
- NO paraphrasing or interpretation

### Step 5: Assign Confidence
- 5: Explicit in description with clear imperative language
- 4: Clearly implied by sw_write() logic or field behavior
- 3: Reasonable interpretation of description
- 2: Inferred from context with some ambiguity
- 1: High inference required (EXCLUDE these)

---

## YAML STRUCTURE QUICK REFERENCE

Every CSR field has structure:
```yaml
fields:
  FIELDNAME:
    location: 7-0           # Which bits (e.g., bits 7-0)
    type: RW               # Access: RW, RO, RW-H, RO-H, RW-RH, RW-R
    description: |         # Behavioral description
      Multi-line text...
    reset_value: 0         # Fixed reset value
    reset_value(): |       # OR dynamic reset logic
      return 0;
    sw_write(csr_value): | # Write validation (WARL logic)
      if (condition) {
        return valid_value;
      }
      return illegal_transform_or_reject;
    sw_read(): |           # Read logic (if special)
      return modified_value;
```

**Extract from THESE sections:**
1. `description:` → Behavioral constraints, legal values
2. `type:` → Access type (RO, RW, etc)
3. `reset_value:` → Default value
4. `location:` → Bit positions (use for ALIGNMENT_REQUIREMENT)
5. `sw_write()` → WARL rules (legal/illegal values, transformations)
6. `sw_read()` → Read-side special behavior

---

## COMMON PATTERNS & HOW TO EXTRACT

Look for these patterns in the YAML:

### PATTERN 1: Static Field with Reset Value
```yaml
fields:
  FIELD:
    type: RW
    reset_value: 0
    description: |
      Description of what field controls.
```
**Extract:**
- FIELDNAME_RESET_VALUE = 0
- FIELDNAME_ACCESS_TYPE = RW
- FIELDNAME_LEGAL_VALUES = (from description)

### PATTERN 2: Write-Any-Read-Legal (WARL) with Validation
```yaml
fields:
  FIELD:
    type: RW-R
    sw_write(csr_value): |
      if (IS_LEGAL(csr_value)) {
        return csr_value;  // Accept
      } else {
        return 0;          // Reject, use default
      }
```
**Extract:**
- FIELDNAME_ACCESS_TYPE = RW-R
- FIELDNAME_LEGAL_VALUES = (from sw_write condition)
- FIELDNAME_ILLEGAL_VALUES = (what's rejected)

### PATTERN 3: Read-Only or Hardware-Updated
```yaml
fields:
  FIELD:
    type: RO-H
    description: |
      Hardware updates this field on events.
```
**Extract:**
- FIELDNAME_ACCESS_TYPE = RO-H
- FIELDNAME_BEHAVIORAL_IMPACT = (what events update it)

### PATTERN 4: Conditional Based on Extension
```yaml
fields:
  FIELD:
    type(): |
      if (implemented?(Extension::Sv39)) {
        return RW;
      }
      return RO;
```
**Extract:**
- FIELDNAME_ACCESS_TYPE_CONDITIONAL = depends on extension
- FIELDNAME_REQUIRES_EXTENSION = Sv39

### PATTERN 5: Field Alias to Another CSR
```yaml
fields:
  FIELD:
    alias: other_csr.OTHER_FIELD
    type: RW
```
**Extract:**
- FIELDNAME_ALIASES_TO = OTHER_CSR.OTHER_FIELD

### PATTERN 6: Value Transformation Instead of Reject
```yaml
fields:
  FIELD:
    sw_write(csr_value): |
      if ((csr_value & MASK) != 0) {
        return align_down(csr_value, GRANULE);
      }
      return csr_value;
```
**Extract:**
- FIELDNAME_TRANSFORMATION = aligns/rounds values
- FIELDNAME_ALIGNMENT_REQUIREMENT = GRANULE

---

## STEP-BY-STEP EXTRACTION PROCESS (REVISED)

---

## REAL EXAMPLES WITH DISAGREEMENT RESOLUTION

### Example 1: SATP (Where Models Previously Disagreed)

**Actual satp.yaml has 3 fields:**
```yaml
fields:
  MODE:        # bits 63-60 in RV64
    type: RW-R
    description: Translation mode
  ASID:        # bits 59-44 in RV64
    type: RW-R
    description: Address Space ID
  PPN:         # bits 43-0 in RV64
    type: RW-R
    description: Physical Page Number
```

**DISAGREEMENT POINTS (where models diverged before):**
- Model A might extract: "SATP_MODE_AFFECTS_TRANSLATION" (vague)
- Model B might extract: "SATP_MODE_CONTROLS_TRANSLATION" (better)
- **RULE:** Use CONTROLS_X not AFFECTS_X unless explicitly stated

**Expected extraction (minimum 5 parameters for 3 fields, after improvements):**
```json
[
  {
    "name": "SATP_MODE_RESET_VALUE",
    "csr_name": "SATP",
    "field_name": "MODE",
    "description": "SATP.MODE resets to 0 (bare translation)",
    "type": "CONSTRAINT",
    "spec_quote": "reset_value: 0",
    "confidence": 5
  },
  {
    "name": "SATP_MODE_LEGAL_VALUES",
    "csr_name": "SATP",
    "field_name": "MODE",
    "description": "MODE must support at least 0 (Bare)",
    "type": "CONSTRAINT",
    "spec_quote": "Supported modes are implementation-specific but must include 0 (Bare)",
    "confidence": 5
  },
  {
    "name": "SATP_MODE_CONTROLS_TRANSLATION",
    "csr_name": "SATP",
    "field_name": "MODE",
    "description": "MODE controls translation mechanism (Bare, Sv39, Sv48, etc)",
    "type": "BEHAVIORAL",
    "spec_quote": "Controls the current translation mode",
    "confidence": 5
  },
  {
    "name": "SATP_ASID_LEGAL_VALUES",
    "csr_name": "SATP",
    "field_name": "ASID",
    "description": "ASID must be zero when MODE is Bare",
    "type": "CONSTRAINT",
    "spec_quote": "When MODE == Bare, PPN and ASID must be zero",
    "confidence": 5
  },
  {
    "name": "SATP_PPN_LEGAL_VALUES",
    "csr_name": "SATP",
    "field_name": "PPN",
    "description": "PPN must be zero when MODE is Bare",
    "type": "CONSTRAINT",
    "spec_quote": "When MODE == Bare, PPN and ASID must be zero",
    "confidence": 5
  }
]
```

**What NOT to do:**
- Don't extract SATP_MODE_AFFECTS_MEMORY_SEMANTICS (too vague, not explicit)
- Don't extract SATP_ALL_ENABLES_VIRTUAL_ADDRESSING (generic, not field-specific)
- Don't extract invented parameters

---

### Example 2: PMPCFG0 (Where Both Models Previously Struggled)

**Actual pmpcfg0.yaml has 8 fields** (pmp0cfg through pmp7cfg, one per PMP entry):
```yaml
fields:
  pmp0cfg:    # bits 7-0
    type: RW-R
    description: Configuration for PMP entry 0
    # Contains L(lock), A(address mode), X, W, R flags
  pmp1cfg:    # bits 15-8
    type: RW-R
    description: Configuration for PMP entry 1
  ... (6 more similar fields)
```

**DISAGREEMENT POINT (before improvements):**
- Model A found 0 fields (complete failure)
- Model B found 7 fields (partial success)
- **WHY:** pmpcfg0 has 8 sub-fields (pmp0cfg-pmp7cfg) that weren't enumerated clearly

**RULE:** Extract parameter for EVERY listed field, even if similar to others

**Expected extraction (minimum 12 parameters for 8 fields):**

For each pmpXcfg field (0-7), extract at minimum:
1. PMPCFG0_PMPXCFG_RESET_VALUE (confidence 5)
2. PMPCFG0_PMPXCFG_ACCESS_TYPE (confidence 5)
3. PMPCFG0_PMPXCFG_LEGAL_VALUES (confidence 4, from sw_write logic showing bit validation)

**Do NOT extract:** Sub-bit parameters (L, A, X, W, R individually)—they're within the field, not separate fields.

---

### Example 3: DCSR (Debug CSR - Complex Field Set)

**Actual dcsr.yaml has 18 fields:**
DEBUGVER, EXTCAUSE, CETRIG, PELP, EBREAKVS, EBREAKVU, EBREAKM, EBREAKS, EBREAKU, STEPIE, STOPCOUNT, STOPTIME, CAUSE, V, MPRVEN, NMIP, STEP, PRV

**DISAGREEMENT POINTS (before improvements):**
- Model A extracted 7/18 fields (~39% coverage)
- Model B extracted 11/18 fields (~61% coverage)
- Only 7 fields matched → 100% agreement on those fields but incomplete overall
- **WHY:** Both models missed several fields, different subsets

**RULE:** Extract at least 1 parameter per field, minimum 3 for complex fields

**Expected extraction: minimum 27 parameters (1.5 × 18)**

Example extractions for multiple fields:
```json
[
  {
    "name": "DCSR_DEBUGVER_RESET_VALUE",
    "csr_name": "DCSR",
    "field_name": "DEBUGVER",
    "description": "Debug version field resets to implementation-defined value",
    "type": "CONSTRAINT",
    "behavioral_impact": "CONSTRAINT",
    "spec_quote": "reset_value: UNDEFINED_LEGAL",
    "confidence": 5
  },
  {
    "name": "DCSR_DEBUGVER_ACCESS_TYPE",
    "csr_name": "DCSR",
    "field_name": "DEBUGVER",
    "description": "DEBUGVER is read-only, not writable by software",
    "type": "CONSTRAINT",
    "behavioral_impact": "CONSTRAINT",
    "spec_quote": "type: RO",
    "confidence": 5
  },
  {
    "name": "DCSR_CAUSE_LEGAL_VALUES",
    "csr_name": "DCSR",
    "field_name": "CAUSE",
    "description": "CAUSE field encodes debug entry reason (values 1-5, 7)",
    "type": "CONSTRAINT",
    "behavioral_impact": "TRAP",
    "spec_quote": "Reason for Debug Mode entry: 1=ebreak, 2=trigger, 3=haltreq, 4=step, 5=resethaltreq, 7=other",
    "confidence": 5
  },
  {
    "name": "DCSR_CAUSE_ENABLES_DEBUG_DECISION",
    "csr_name": "DCSR",
    "field_name": "CAUSE",
    "description": "CAUSE determines why debugger halted the hart (affects debug mode entry reason)",
    "type": "BEHAVIORAL",
    "behavioral_impact": "TRAP",
    "spec_quote": "The reason for Debug Mode entry is determined by CAUSE: 1=ebreak, 2=trigger, 3=haltreq, 4=step, 5=resethaltreq",
    "confidence": 4
  },
  ...
  // Continue for STEP, V, MPRVEN, NMIP, other fields
]
```

**Completeness check:**
- 18 fields × 1.5 = 27 minimum parameters
- Each field should have: RESET_VALUE + ACCESS_TYPE + (optional behavioral or legal values)
- Make sure ALL 18 fields appear in at least one parameter

---

## WHEN MODELS DISAGREE - RESOLUTION RULES

If you see two models producing different parameters for same field:

**Case 1: One extracted, one didn't**
- If parameter has spec quote and follows naming format → **ACCEPT BOTH**
- If parameter has no spec quote or invents naming → **REJECT INVALID**

**Case 2: Different semantic suffix** (e.g., CONTROLS vs AFFECTS)
- Check spec text: Does it use "controls" or "affects"?
- If "controls" in spec → Use CONTROLS_X
- If "affects" in spec → Use AFFECTS_X (rare)
- If neither → Use ENABLES_X or just skip the behavioral parameter

**Case 3: Different confidence scores**
- Both score 5? One sure, one inferring? → **Use lower confidence** (don't inflate)
- One scores 3, one scores 5? → Check spec quote
  - If quote explicitly supports it → 5 is correct
  - If quote is vague → 3 is correct
- Resolve by: "If I had to explain to a colleague, would they immediately see it in the spec?"

**Case 4: Different legal values extracted**
- Model A: "0 and 1 are legal"
- Model B: "0-255 are legal"
- **RULE:** Use more restrictive (Model A) only if WARL logic explicitly rejects 2-255
- If spec is silent → Accept Model B's broader interpretation (confidence 3)

**Case 5: Behavioral_impact disagreement**
- Model A: MEMORY
- Model B: CONSTRAINT
- **RULE:** Use most specific impact (MEMORY > EXECUTION > STATE > TRAP > ACCESS > CONSTRAINT)
  - If field affects translation → MEMORY (not CONSTRAINT)
  - If field affects instruction → EXECUTION (not STATE)
  - If field affects privilege → STATE (not CONSTRAINT)

### Example: MTVEC (Trap Vector Control with Complex WARL)
```yaml
name: mtvec
long_name: Machine Trap Vector Control
description: Controls where traps jump.
fields:
  BASE:
    location_rv64: 63-2
    description: |
      Bits [MXLEN-1:2] of the exception vector physical address.
      The implementation physical memory map may restrict which values 
      are legal in this field.
    type(): return MTVEC_ACCESS == "ro" ? RO : RWR;
    reset_value: 0
  MODE:
    location: 1-0
    description: |
      Vectoring mode: 0=Direct, 1=Vectored
      Direct: all exceptions jump to (BASE<<2)
      Vectored: async interrupts jump to (BASE<<2 + mcause.CAUSE*4)
    type(): return (MTVEC_MODES size==1) ? RO : RWR;
```

**Extract:**
```json
[
  {
    "name": "MTVEC_BASE_LEGAL_VALUES",
    "csr_name": "MTVEC",
    "field_name": "BASE",
    "description": "BASE field contains exception vector physical address with implementation-specific restrictions",
    "type": "WARL_LEGAL_VALUES",
    "behavioral_impact": "TRAP",
    "spec_quote": "Bits [MXLEN-1:2] of the exception vector physical address. The implementation physical memory map may restrict which values are legal",
    "spec_location": "mtvec.yaml fields.BASE.description",
    "confidence": 5,
    "is_explicit": true
  },
  {
    "name": "MTVEC_MODE_CONTROLS_EXCEPTION_VECTORING",
    "csr_name": "MTVEC",
    "field_name": "MODE",
    "description": "MODE determines whether exceptions are vectored or direct",
    "type": "BEHAVIORAL",
    "behavioral_impact": "TRAP",
    "spec_quote": "Vectoring mode: 0=Direct, 1=Vectored. Direct: all exceptions jump to (BASE<<2). Vectored: async interrupts jump to (BASE<<2 + mcause.CAUSE*4)",
    "spec_location": "mtvec.yaml fields.MODE.description",
    "confidence": 5,
    "is_explicit": true
  }
]
```

### Example: MSTATUS.MIE (From YAML)
```yaml
fields:
  MIE:
    description: |
      Machine Interrupt Enable. When an exception is taken into M-mode, 
      MSTATUS.MIE is cleared, and prior value of MIE is preserved in MSTATUS.MPIE.
    type: RW
    reset_value: 0
```

**Extract:**
```json
[
  {
    "name": "MSTATUS_MIE_ENABLES_INTERRUPTS",
    "csr_name": "MSTATUS",
    "field_name": "MIE",
    "description": "MIE controls whether interrupts are enabled in M-mode",
    "type": "BEHAVIORAL",
    "behavioral_impact": "TRAP",
    "spec_quote": "Machine Interrupt Enable. When an exception is taken into M-mode, MSTATUS.MIE is cleared",
    "spec_location": "mstatus.yaml fields.MIE.description",
    "confidence": 5,
    "is_explicit": true
  }
]
```

---

## DETAILED WALKTHROUGH EXAMPLE

### Example: Extracting from mtvec.yaml

Given YAML field:
```yaml
fields:
  MODE:
    location: 1-0
    description: |
      Trap handler mode. When a trap is taken into M-mode, the pc is set to BASE with the low bits MODE appended. 
      For the base-only mode (MODE=0), the low bits are zeroed. 
      The supported modes are implementation-specific but must include 0 (base).
    type: RW
    reset_value(): |
      return 0;
    sw_write(csr_value): |
      if (((csr_value.MODE == 1) && !implemented?(ExtensionName::Vectored)) {
        return 0;  // Invalid mode, revert to Bare
      }
      return csr_value.MODE;
```

**Extraction Process:**

**Step 1:** Identify CSR and field
- CSR_NAME = MTVEC (from file name)
- FIELD_NAME = MODE (from fields section)

**Step 2:** Check for WARL indicators
- Has `sw_write()` function ✓ → Contains write validation logic
- Field accepts writes but validates them

**Step 3:** Extract WARL parameters

**Parameter 1 - Legal Values:**
```
Spec quote: "The supported modes are implementation-specific but must include 0 (base)"
Key phrase: "must include 0"
Extract as:
{
  "name": "MTVEC_MODE_LEGAL_VALUES",
  "csr_name": "MTVEC",
  "field_name": "MODE",
  "description": "MTVEC.MODE must support at least mode 0 (Bare/base-only)",
  "type": "WARL_LEGAL_VALUES",
  "behavioral_impact": "TRAP",
  "spec_quote": "The supported modes are implementation-specific but must include 0 (base)",
  "confidence": 5,
  "is_explicit": true
}
```

**Parameter 2 - Mode Validation:**
```
Spec quote: From sw_write() logic: "If mode==1 but Vectored not implemented, revert to 0"
Key insight: sw_write shows conditional acceptance
Extract as:
{
  "name": "MTVEC_MODE_VECTORED_REQUIRES_EXTENSION",
  "csr_name": "MTVEC",
  "field_name": "MODE",
  "description": "Mode 1 (Vectored) is only legal if Vectored extension is implemented",
  "type": "WARL_ILLEGAL_VALUES",
  "behavioral_impact": "TRAP",
  "spec_quote": "When sw_write receives MODE==1 but Vectored extension not implemented, it returns 0",
  "confidence": 4,
  "is_explicit": false
}
```

**Parameter 3 - Behavioral:**
```
Spec quote: "When a trap is taken into M-mode, the pc is set to BASE with the low bits MODE appended"
Key phrase: Affects trap PC calculation
Extract as:
{
  "name": "MTVEC_MODE_CONTROLS_TRAP_VECTOR_ADDRESS",
  "csr_name": "MTVEC",
  "field_name": "MODE",
  "description": "MTVEC.MODE determines how trap handler address is computed from BASE field",
  "type": "BEHAVIORAL",
  "behavioral_impact": "TRAP",
  "spec_quote": "When a trap is taken into M-mode, the pc is set to BASE with the low bits MODE appended",
  "confidence": 5,
  "is_explicit": true
}
```

**Step 4:** Continue with BASE field (if present), extract ALIGNMENT_REQUIREMENT

Final output would be JSON array with all 3+ parameters.

---

## CONFIDENCE SCORING GUIDE

| Score | When to Use |
|-------|------------|
| 5 | Spec explicitly states requirement with "must"/"shall"/"required" and unambiguous meaning |
| 4 | Spec clearly implies behavior; strong evidence in quote; minor ambiguity possible |
| 3 | Spec suggests behavior; reasonable interpretation; ambiguity exists but resolvable |
| 2 | Parameter inferred from context; weak evidence; multiple valid interpretations |
| 1 | Barely supported; requires significant inference; high uncertainty (EXCLUDE THESE) |

**Default:** If uncertain, extract only confidence >= 3

---

## REQUIREMENTS

1. Valid JSON array only (no markdown, no explanation)
2. Every parameter has spec quote with imperative language
3. Every parameter name follows format exactly
4. No hallucinated parameters
5. No external reference (UDB, GitHub, etc.)
6. WARL parameters extracted thoroughly
7. No duplicates

---

## CSR DOMAIN COVERAGE

This prompt covers all CSR domains in the RISC-V ISA across 389 CSR definitions organized by extension:

**Machine-Level Base CSRs** (80 files)
- Machine Status (mstatus, mstatush, mstateen*, mdelegext)
- Machine Traps (mtvec, mtval, mepc, mcause, mip, mie)
- Machine Interrupts (msip, mtip, meip)
- Machine Counters (mcycle, minstret, mhpmcounter*, mhpmevent*)
- Environment Configuration (menvcfg)
- Machine Info (mvendorid, marchid, mimpid, mconfigptr, mhartid)
- Debug (dcsr, dpc, dscratch, trigger CSRs)

**Supervisor-Level CSRs** (1 file, plus aliases in other files)
- Supervisor Status (sstatus, sie, sip, scause, stval, sepc)
- Supervisor Counters (scounteren)
- Supervisor Environment (senvcfg)
- Virtual Supervisor Indirect (vsiselect, vsireg0-vsireg5)

**Hypervisor-Level CSRs** (11 files)
- Hypervisor Status (hstatus)
- Hypervisor Counters (hcounteren)
- Hypervisor Traps (htval, hepc, hcause)
- Hypervisor Environment (henvcfg)
- Hypervisor State Enable (hstateen0-3)

**User-Level CSRs**
- Floating-Point Control (frm, fflags, fcsr) - F extension (3 files)
- Vector Control (vcsr, vl, vtype, vstart, vlenb, vxrm, vxsat) - V extension (7 files)
- User Counters (cycle, instret, cycleh, instreth) - Zicntr extension (1 file)
- User-Mode HPM Counters (hpmcounter3-31, hpmcounter3h-31h) - Zihpm extension (174 files)

**Privileged-Extension CSRs**
- PMP (Physical Memory Protection) - I extension (81 files)
  - pmpcfg0-15, pmpaddr0-63 with complex WARL and granularity constraints
- Debug & Trace - Sdext extension
- RNMi (Resumable NMI) - Smrnmi extension (4 files)
- Counter Profiling - Sscofpmf extension (1 file)
- CSR Indirect Access - Smcsrind extension (21 files)
  - Provides indirect access to extension state via select/register alias pairs
- QoS Identifiers - Ssqosid extension (1 file)

**Special Field Types Across Domains**
- 202 CSR fields with type: RW (read-write freely)
- 79 CSR fields with type: RO-H (read-only, hardware updates)
- 47 CSR fields with type: RW-H (read-write, hardware updates)
- 35 CSR fields with type: RO (read-only static)
- 15 CSR fields with type: RW-RH (read-write, hardware reads differ)
- 13 CSR fields with type: RW-R (read-write, reads reset)

**Pattern Coverage by Type**
- Lock-Based WARL: PMP CSRs (pmpcfg*, pmpaddr*)
- Mode-Conditional Type: satp.MODE, menvcfg fields, henvcfg fields
- Privilege-Dependent Read: cycle, sip, sie with mideleg/hideleg
- Hardware Counters: mcycle, minstret, mhpmcounter* with enable bits
- Hardware Exception Flags: fflags (accumulated by floating-point operations)
- Vector State: vtype with VILL flag, vl with dynamic length, vxrm with rounding
- Debug Mode: dcsr, dpc with special privilege and halt behavior
- Hypervisor: hstateen* with cascading parent constraints, hedeleg/medeleg delegation
- Aliases: frm→fcsr, fflags→fcsr, sip→mip, sstatus→mstatus, cycle→mcycle, vcsr→vxrm/vxsat
- Indirect Access: siselect/vsiselect with range constraints
- Indirect Alias CSRs: mireg*/hsireg*/vsireg* with indirect_csr_lookup()
- Counter Inhibit: mcountinhibit with *_EN[] configuration arrays
- Counter Enable: hcounteren, mcounteren with complex multi-CSR privilege tables
- Multi-CSR Delegation: medeleg, hideleg with cascading handler selection
- Implementation Config: Type and reset depend on HCOUNTENABLE_EN, COUNTINHIBIT_EN, PMP_GRANULARITY, PHYS_ADDR_WIDTH
- HPM Event Validation: mhpmevent* validates EVENT against HPM_EVENTS array (29 files)
- Cross-CSR Constraints: hstatus constrains fields based on mstatus values (227 files with field interdependencies)

**Pattern Families Covered**
- **Core WARL** (1-2): Lock-based, mode-conditional
- **Dynamic Configuration** (3, 9, 13, 19): Extension-gated, endianness-dependent, config-array-dependent
- **Aliases & Views** (4, 7, 12, 18): Single/multiple aliases, bit-range aliases, read-only views
- **Privilege & Delegation** (5, 10, 20): Privilege-conditional, cascading, multi-CSR behavior
- **Hardware State** (11, 14, 15): Accumulation, RO dynamic, conditional reads
- **Transformation & Masking** (6, 8): Value rounding, read modification
- **Indirect & Validation** (16, 21, 22): Indirect selectors, array validation, indirect CSR access
- **Cross-CSR Relationships** (23): Field constraints across different CSRs

**Implementation-Dependent Configuration Arrays Found**
- HCOUNTENABLE_EN[]: Controls which counter bits in hcounteren are writable
- MCOUNTENABLE_EN[]: Controls which counter bits in mcounteren are writable
- SCOUNTENABLE_EN[]: Controls which counter bits in scounteren are writable
- COUNTINHIBIT_EN[]: Controls which counter bits in mcountinhibit are writable
- HPM_COUNTER_EN[]: Controls which HPM counter enables are active
- FOLLOW_VTYPE_RESET_RECOMMENDATION: Vector reset behavior configuration

**Extraction Strategy**
1. Read the field's description, type(), reset_value(), sw_write(), sw_read()
2. Identify which patterns (1-23) apply to this field
3. Extract accordingly with proper CSR_FIELD_SEMANTIC naming
4. Confidence scores: 5 for explicit patterns, 4 for clear logic, 3 for reasonable inference

---

## QUICK REFERENCE CARD (Print This)

### Extraction Order (PRIORITY)
1. **Access Type** (RO/RW/RO-H/etc) → Confidence 5
2. **Reset Value** (explicit reset_value) → Confidence 5
3. **WARL Logic** (from sw_write()) → Confidence 4-5
4. **Legal Values** (explicit list) → Confidence 4-5
5. **Behavioral Impact** (controls/enables/affects) → Confidence 3-4
6. Skip everything else

### Parameter Naming
 SATP_MODE_LEGAL_VALUES  
 PMPCFG0_PMP0CFG_RESET_VALUE  
 DCSR_CAUSE_ENABLES_DEBUG_DECISION  
 SATP_CONSTRAINT  
 SATP_MODE_BEHAVIOR  
 SATP_CONTROLS_TRANSLATION  (use CONTROLS_TRANSLATION not AFFECTS)

### Behavioral_Impact Categories
- **TRAP:** Exception/interrupt/handler (use when spec says "trap", "exception", "interrupt")
- **MEMORY:** Address translation/memory (use when spec says "translation", "address", "memory")
- **EXECUTION:** Instruction behavior (use when spec says "instruction", "execute", "operation")
- **STATE:** Processor state/mode (use when spec says "status", "state", "mode", "privilege")
- **ACCESS:** Read/write permissions (use when spec says "readable", "writable", "permission")
- **CONSTRAINT:** Value limits only (use when field just constrains values)

### Confidence Scores
- **5:** Explicit in YAML (reset_value, type, access), WARL code, explicit lists
- **4:** Clear from sw_write() logic, behavioral description with explicit keywords
- **3:** Reasonable inference, partial documentation, valid but not explicit
- **Below 3:** DO NOT EXTRACT

### Minimum Parameter Count
- 3 fields (satp) = minimum 5 parameters
- 8 fields (pmpcfg0) = minimum 12 parameters
- 18 fields (dcsr) = minimum 27 parameters
- Formula: 1.5 × number of fields

### Common Mistakes to Avoid
✗ Extracting generic documentation ("this field is important")
✗ Using behavioral_impact from outside defined list (SEMANTIC, NONE, OTHER)
✗ Missing any field (every field must appear in at least one parameter)
✗ Inventing parameters without spec quotes
✗ Paraphrasing spec text (must be exact quote)
✗ Confidence > 3 without explicit evidence
✗ Using suffix not in allowed list (TYPE not TYPE_CONSTRAINT)

---

## CHALLENGE-SPECIFIC OPTIMIZATION

**To maximize agreement between evaluations:**

### 1. **Absolute Field Completeness**
- EVERY field in YAML `fields:` section MUST have at least 1 extracted parameter
- Count fields precisely: 3 fields = minimum 5 parameters, 8 fields = minimum 12, 18 fields = minimum 27
- Do NOT skip fields, even if description is minimal
- If field has no sw_write() but exists, extract at minimum: name, type, reset_value

### 2. **Type Classification is KING**
Models agree BEST when type classification is explicit:
- **RO fields:** Extract access_type + behavioral_impact of read-only nature
- **RW fields:** Extract access_type + reset_value + legal_values
- **RW-H fields:** Extract both user-write behavior AND hardware-update behavior
- **WARL fields (sw_write()):** Extract 3-4 parameters: legal_values, illegal_values, mapping, reset

### 3. **WARL Extraction Golden Rules**
For ANY sw_write() function:
1. **Condition TRUE branch:** Values returned unchanged = LEGAL (Confidence 5)
2. **Condition FALSE branch:** Values returned modified/0 = ILLEGAL (Confidence 5)
3. **Extracted example:**
   ```yaml
   sw_write(csr_value): |
     if ((csr_value >> 31) == 0 || (csr_value >> 31) == 8) {
       return csr_value;  // Legal: MODE 0 and 8 accepted
     }
     return CSR[satp].MODE;  // Illegal: anything else rejected (WARL, keep old value)
   ```
   **Extract:**
   - SATP_MODE_WARL_LEGAL_VALUES: "0 (bare) or 8 (Sv39)" [Confidence 5]
   - SATP_MODE_WARL_ILLEGAL_VALUES: "Any value other than 0 or 8" [Confidence 5]
   - SATP_MODE_WARL_BEHAVIOR: "Write-Any-Read-Legal: illegal writes rejected, keep current" [Confidence 5]

### 4. **Privilege-Level Specificity**
Agreement increases when privilege-level variants are explicit:
- If description shows behavior differs at M/S/U, extract SEPARATE parameters:
  - MSTATUS_SUM_MACHINE_MODE_BEHAVIOR (what M-mode sees)
  - MSTATUS_SUM_SUPERVISOR_MODE_BEHAVIOR (what S-mode sees)
  - MSTATUS_SUM_USER_MODE_BEHAVIOR (what U-mode sees)
- Even if some privileges don't support the field, extract that as "N/A" or "Always X"

### 5. **Extension-Conditional Extraction**
Agreement increases with explicit extension handling:
- If field has `type():` or `sw_write():` conditional on extension:
  - Extract WITH_EXTENSION_X: behavior when extension is implemented
  - Extract WITHOUT_EXTENSION_X: behavior when extension is NOT implemented
  - Example: FCSR with/without F extension has different access types

### 6. **Confidence Scoring Precision**
Models agree when confidence is consistently calibrated:
- **Confidence 5:** Explicit in YAML (reset_value:, type:, exact list in description, sw_write() logic)
- **Confidence 4:** Clear inference from code (sw_write() behavior, field aliases)
- **Confidence 3:** Reasonable but less explicit (description implies behavior)
- **NEVER use 1-2:** Skip extraction entirely if confidence < 3
- **AVOID all 5s:** Realistic CSR extractions have mix of 5, 4, and 3

### 7. **Counter CSR Special Case**
For mcycle, minstret, and similar hardware-updated counters:
- **ALWAYS extract 4 parameters minimum:**
  1. WIDTH_RV32: "32-bit (use MCYCLEHfor upper bits)"
  2. WIDTH_RV64: "64-bit single register"
  3. HARDWARE_UPDATE: "Incremented automatically on clock cycles"
  4. OVERFLOW_BEHAVIOR: "Wraps at 2^width"

### 8. **Interrupt/Exception CSR Special Case**
For mtvec, mie, mcause, mepc, mstatus[MIE]:
- **ALWAYS extract 4 parameters minimum:**
  1. VECTOR_BASE_ALIGNMENT: "Must be 4-byte aligned"
  2. MODE_LEGAL_VALUES: "Which modes are supported (0=direct, 1=vectored, etc.)"
  3. INTERRUPT_ENABLE_CONTROLS: "When set, enables this interrupt class"
  4. TRAP_DISPATCH_BEHAVIOR: "How this field directs exception handling"

### 9. **Memory Protection (PMP) Special Case**
For pmpcfg0/4/8, pmpaddr0-15:
- **ALWAYS extract per entry:**
  1. ENTRY_N_TYPE_LEGAL_VALUES: "0=OFF, 1=TOR, 2=NA4, 3=NAPOT"
  2. ENTRY_N_R_MEANING: "Read access permission bit"
  3. ENTRY_N_W_MEANING: "Write access permission bit"
  4. ENTRY_N_X_MEANING: "Execute access permission bit"
  5. ENTRY_N_L_CONTROLS_WRITE_PROTECTION: "When locked, entry read-only"

### 10. **Debug CSR (dcsr) Special Case**
For dcsr, extract ALL 18 field parameters:
- Group by category: breakpoint controls (ebreakm/s/u), execution controls (step, stopcycle), status fields (cause, prv, v)
- Each field minimum 2 parameters (one for meaning, one for how it controls behavior)
- Confidence 4-5 for dcsr (well-defined debug specification)

---

## FINAL INSTRUCTION

1. Read the CSR YAML specification provided
2. Identify all fields in `fields:` section
3. For EACH field, extract minimum 1.5-2 parameters using PRIORITY order above
4. Name parameters exactly as: {CSR}_{FIELD}_{SEMANTIC}
5. Use behavioral_impact ONLY from defined categories
6. Assign realistic confidence (not all 5s)
7. Include exact spec_quote for every parameter
8. Verify minimum count before submitting
9. Output ONLY valid JSON array with NO additional text
10. **CHALLENGE FOCUS:** Prioritize WARL logic, type classification, and field completeness for agreement
