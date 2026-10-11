# AsciiDoc Spec Chunker Full Analysis Report

## Executive Summary
- Total Files: 136
- Processed Files: 131
- Skipped Files: 5
- Total Raw Chunks: 10529
- Final Chunks (in dataset): 4311
- Reduction: 59.06%


## Filter Breakdown (Why chunks were dropped)
- low_signal: 3092
- truncated: 897
- non_normative: 461
- noise: 443
- note: 378
- bullet: 313
- instruction_description: 139
- doc_filtered: 93
- soft_rationale: 85
- profile_filtered: 83
- synopsis_header: 81
- broken_reference: 66
- formal_reference_tag: 42
- computation_description: 33
- formal_filtered: 12

## Confidence Distribution
- high: 3258 (75.6%)
- medium: 546 (12.7%)
- very_high: 507 (11.8%)

## Parameter Classification Summary
- unknown: 1637 (38.0%)
- CSR_controlled: 1382 (32.1%)
- non_CSR_parameter: 1038 (24.1%)
- SW_rule: 254 (5.9%)

## Parameter Type Summary
- enum: 2011 (46.6%)
- unknown: 1374 (31.9%)
- range: 569 (13.2%)
- binary: 357 (8.3%)

## Per-file Chunk Selection Analysis
| S.No | File | Raw Candidates | Selected Final Chunks | Dropped |
|---|---|---|---|---|
| 1 | `src/scalar-crypto.adoc` | 1075 | 233 | 842 |
| 2 | `src/v-st-ext.adoc` | 1440 | 625 | 815 |
| 3 | `src/vector-crypto.adoc` | 670 | 117 | 553 |
| 4 | `src/b-st-ext.adoc` | 591 | 40 | 551 |
| 5 | `src/unpriv/mm-explanatory.adoc` | 447 | 171 | 276 |
| 6 | `src/priv/machine.adoc` | 791 | 590 | 201 |
| 7 | `src/priv/hypervisor.adoc` | 585 | 426 | 159 |
| 8 | `src/unpriv/zcmp.adoc` | 200 | 51 | 149 |
| 9 | `src/intro.adoc` | 143 | 5 | 138 |
| 10 | `src/unpriv/cmo.adoc` | 202 | 64 | 138 |
| 11 | `src/priv/supervisor.adoc` | 403 | 286 | 117 |
| 12 | `src/unpriv/zcb.adoc` | 115 | 13 | 102 |
| 13 | `src/unpriv/mm-formal.adoc` | 248 | 148 | 100 |
| 14 | `src/unpriv/cfi.adoc` | 160 | 64 | 96 |
| 15 | `src/unpriv/zca.adoc` | 159 | 63 | 96 |
| 16 | `src/profiles/rva23.adoc` | 95 | 3 | 92 |
| 17 | `src/profiles/intro.adoc` | 116 | 25 | 91 |
| 18 | `src/profiles/rva22.adoc` | 87 | 3 | 84 |
| 19 | `src/rv32.adoc` | 152 | 71 | 81 |
| 20 | `src/profiles/rvb23.adoc` | 84 | 6 | 78 |
| 21 | `src/naming.adoc` | 82 | 8 | 74 |
| 22 | `src/priv/zpm.adoc` | 109 | 35 | 74 |
| 23 | `src/priv/preface.adoc` | 75 | 5 | 70 |
| 24 | `src/unpriv/preface.adoc` | 75 | 5 | 70 |
| 25 | `src/unpriv/rvwmo.adoc` | 167 | 99 | 68 |
| 26 | `src/priv/smctr.adoc` | 273 | 209 | 64 |
| 27 | `src/priv/csrs.adoc` | 126 | 65 | 61 |
| 28 | `src/profiles/rva20.adoc` | 60 | 2 | 58 |
| 29 | `src/unpriv/zcmt.adoc` | 71 | 23 | 48 |
| 30 | `src/unpriv/rationale.adoc` | 60 | 14 | 46 |
| 31 | `src/priv/intro.adoc` | 44 | 0 | 44 |
| 32 | `src/profiles/rvi20.adoc` | 43 | 1 | 42 |
| 33 | `src/unpriv/zclsd.adoc` | 44 | 9 | 35 |
| 34 | `src/unpriv/rv-32-64g.adoc` | 38 | 6 | 32 |
| 35 | `src/rv64.adoc` | 50 | 20 | 30 |
| 36 | `src/unpriv/zalasr.adoc` | 33 | 7 | 26 |
| 37 | `src/priv/cfi.adoc` | 69 | 44 | 25 |
| 38 | `src/unpriv/zilsd.adoc` | 38 | 15 | 23 |
| 39 | `src/unpriv/zvfbfmin.adoc` | 23 | 1 | 22 |
| 40 | `src/unpriv/zfbfmin.adoc` | 22 | 3 | 19 |
| 41 | `src/unpriv/zicond.adoc` | 36 | 17 | 19 |
| 42 | `src/priv/smstateen.adoc` | 94 | 76 | 18 |
| 43 | `src/unpriv/f-st-ext.adoc` | 84 | 66 | 18 |
| 44 | `src/unpriv/zacas.adoc` | 37 | 19 | 18 |
| 45 | `src/unpriv/zvfbfwma.adoc` | 19 | 1 | 18 |
| 46 | `src/priv/rationale.adoc` | 35 | 18 | 17 |
| 47 | `src/priv/ssqosid.adoc` | 28 | 12 | 16 |
| 48 | `src/unpriv/vector-examples.adoc` | 27 | 11 | 16 |
| 49 | `src/unpriv/zabha.adoc` | 20 | 4 | 16 |
| 50 | `src/priv/svpbmt.adoc` | 29 | 14 | 15 |
| 51 | `src/unpriv/zfa.adoc` | 49 | 34 | 15 |
| 52 | `src/priv/smepmp.adoc` | 20 | 6 | 14 |
| 53 | `src/unpriv/q-st-ext.adoc` | 19 | 5 | 14 |
| 54 | `src/unpriv/zalrsc.adoc` | 34 | 20 | 14 |
| 55 | `src/unpriv/zawrs.adoc` | 26 | 12 | 14 |
| 56 | `src/priv/smcdeleg.adoc` | 39 | 26 | 13 |
| 57 | `src/unpriv/bitmanip-examples.adoc` | 16 | 3 | 13 |
| 58 | `src/unpriv/zimop.adoc` | 17 | 4 | 13 |
| 59 | `src/unpriv/za.adoc` | 15 | 3 | 12 |
| 60 | `src/unpriv/zcmop.adoc` | 13 | 1 | 12 |
| 61 | `src/unpriv/zihintntl.adoc` | 21 | 9 | 12 |
| 62 | `src/unpriv/zfh.adoc` | 21 | 10 | 11 |
| 63 | `src/priv/smcntrpmf.adoc` | 24 | 15 | 9 |
| 64 | `src/unpriv/m-st-ext.adoc` | 18 | 9 | 9 |
| 65 | `src/unpriv/zcf.adoc` | 17 | 8 | 9 |
| 66 | `src/priv/smrnmi.adoc` | 50 | 42 | 8 |
| 67 | `src/priv/svinval.adoc` | 17 | 9 | 8 |
| 68 | `src/profiles/preface.adoc` | 9 | 1 | 8 |
| 69 | `src/unpriv/zaamo.adoc` | 16 | 8 | 8 |
| 70 | `src/unpriv/zf.adoc` | 8 | 0 | 8 |
| 71 | `src/unpriv/ziccif.adoc` | 11 | 3 | 8 |
| 72 | `src/priv/sscofpmf.adoc` | 39 | 32 | 7 |
| 73 | `src/unpriv/zcd.adoc` | 14 | 7 | 7 |
| 74 | `src/unpriv/zicntr.adoc` | 22 | 15 | 7 |
| 75 | `src/unpriv/zicsr.adoc` | 50 | 43 | 7 |
| 76 | `src/unpriv/zifencei.adoc` | 9 | 2 | 7 |
| 77 | `src/priv/smcsrind.adoc` | 58 | 53 | 5 |
| 78 | `src/unpriv/d-st-ext.adoc` | 27 | 22 | 5 |
| 79 | `src/unpriv/zc.adoc` | 7 | 2 | 5 |
| 80 | `src/images/graphviz/litmus_sample.adoc` | 4 | 0 | 4 |
| 81 | `src/priv/smdbltrp.adoc` | 7 | 3 | 4 |
| 82 | `src/priv/ssdbltrp.adoc` | 6 | 2 | 4 |
| 83 | `src/priv/svnapot.adoc` | 9 | 5 | 4 |
| 84 | `src/rv32e.adoc` | 5 | 1 | 4 |
| 85 | `src/unpriv/c-st-ext.adoc` | 6 | 2 | 4 |
| 86 | `src/unpriv/memory-models.adoc` | 4 | 0 | 4 |
| 87 | `src/unpriv/zfhmin.adoc` | 7 | 3 | 4 |
| 88 | `src/priv/insns.adoc` | 3 | 0 | 3 |
| 89 | `src/unpriv/zce.adoc` | 4 | 1 | 3 |
| 90 | `src/unpriv/zfinx.adoc` | 27 | 24 | 3 |
| 91 | `src/unpriv/zi.adoc` | 4 | 1 | 3 |
| 92 | `src/unpriv/zicclsm.adoc` | 5 | 2 | 3 |
| 93 | `src/unpriv/zmmul.adoc` | 3 | 0 | 3 |
| 94 | `src/unpriv/ztso.adoc` | 6 | 3 | 3 |
| 95 | `src/priv/sh.adoc` | 2 | 0 | 2 |
| 96 | `src/priv/sha.adoc` | 2 | 0 | 2 |
| 97 | `src/priv/sm.adoc` | 2 | 0 | 2 |
| 98 | `src/priv/ss.adoc` | 2 | 0 | 2 |
| 99 | `src/priv/sstc.adoc` | 7 | 5 | 2 |
| 100 | `src/priv/sv.adoc` | 2 | 0 | 2 |
| 101 | `src/priv/svadu.adoc` | 7 | 5 | 2 |
| 102 | `src/unpriv/zp.adoc` | 2 | 0 | 2 |
| 103 | `src/priv/svrsw60t59b.adoc` | 3 | 2 | 1 |
| 104 | `src/unpriv/a-st-ext.adoc` | 1 | 0 | 1 |
| 105 | `src/unpriv/code-examples.adoc` | 1 | 0 | 1 |
| 106 | `src/unpriv/mm-appendix.adoc` | 1 | 0 | 1 |
| 107 | `src/unpriv/zars.adoc` | 3 | 2 | 1 |
| 108 | `src/unpriv/zihpm.adoc` | 7 | 6 | 1 |
| 109 | `src/priv/priv.adoc` | 0 | 0 | 0 |
| 110 | `src/priv/shcounterenw.adoc` | 1 | 1 | 0 |
| 111 | `src/priv/shgatpa.adoc` | 2 | 2 | 0 |
| 112 | `src/priv/shtvala.adoc` | 1 | 1 | 0 |
| 113 | `src/priv/shvsatpa.adoc` | 1 | 1 | 0 |
| 114 | `src/priv/shvstvala.adoc` | 1 | 1 | 0 |
| 115 | `src/priv/shvstvecd.adoc` | 2 | 2 | 0 |
| 116 | `src/priv/ssccptr.adoc` | 1 | 1 | 0 |
| 117 | `src/priv/sscounterenw.adoc` | 1 | 1 | 0 |
| 118 | `src/priv/ssstrict.adoc` | 2 | 2 | 0 |
| 119 | `src/priv/sstvala.adoc` | 2 | 2 | 0 |
| 120 | `src/priv/sstvecd.adoc` | 2 | 2 | 0 |
| 121 | `src/priv/ssu64xl.adoc` | 1 | 1 | 0 |
| 122 | `src/priv/svvptc.adoc` | 1 | 1 | 0 |
| 123 | `src/profiles/profiles.adoc` | 0 | 0 | 0 |
| 124 | `src/symbols.adoc` | 0 | 0 | 0 |
| 125 | `src/unpriv.adoc` | 0 | 0 | 0 |
| 126 | `src/unpriv/zama.adoc` | 2 | 2 | 0 |
| 127 | `src/unpriv/zic64b.adoc` | 1 | 1 | 0 |
| 128 | `src/unpriv/ziccamoa.adoc` | 1 | 1 | 0 |
| 129 | `src/unpriv/ziccamoc.adoc` | 1 | 1 | 0 |
| 130 | `src/unpriv/ziccrse.adoc` | 1 | 1 | 0 |
| 131 | `src/unpriv/zihintpause.adoc` | 3 | 3 | 0 |

## Complete Extracted Parameters List (AsciiDoc)

> _Showing a randomized sample (up to 10 chunks per parameter class)._

| Section | Parameter_Class | Text | Confidence |
|---|---|---|---|
| Preamble > "H" Extension for Hypervisor Support, Version 1.0 > Traps > Trap Return | CSR_controlled | The MRET instruction is used to return from a trap taken into M-mode. MRET first determines what the new privilege mode will be according to the values of MPP and MPV in `mstatus` or `mstatush`, as en... | high |
| Preamble > "Sscofpmf" Extension for Count Overflow and Mode-Based Filtering, Version 1.0 > Count Overflow Control > Supervisor Count Overflow (`scountovf`) Register | CSR_controlled | This extension adds the `scountovf` CSR, a 32-bit read-only register that contains shadow copies of the OF bits in the 29 mhpmevent CSRs (mhpmevent3 - mhpmevent31) - where scountovf bit X corresponds ... | high |
| Preamble > "H" Extension for Hypervisor Support, Version 1.0 > Two-Stage Address Translation > Guest Physical Address Translation | CSR_controlled | When `hgatp`.MODE specifies a translation scheme of Sv32x4, Sv39x4, Sv48x4, or Sv57x4, G-stage address translation is a variation on the usual page-based virtual address translation scheme of Sv32, Sv... | high |
| Preamble > Supervisor-Level ISA, Version 1.13 > Supervisor CSRs > Supervisor Trap Value (`stval`) Register | CSR_controlled | The `stval` CSR is an SXLEN-bit read-write register formatted as shown in .... | high |
| Preamble > Supervisor-Level ISA, Version 1.13 > Supervisor CSRs > Supervisor Status (`sstatus`) Register > Double Trap Control in `sstatus` Register | CSR_controlled | The `mtval2` register is then set to what would be otherwise written into the `mcause` register by the unexpected trap.... | high |
| Preamble > "Smrnmi" Extension for Resumable Non-Maskable Interrupts, Version 1.0 > RNMI Interrupt Signals > RNMI Operation | CSR_controlled | If the hart encounters an exception while executing in M-mode with the `mnstatus`.NMIE bit clear, the actions taken are the same as if the exception had occurred while `mnstatus`.NMIE were set, except... | high |
| Preamble > "H" Extension for Hypervisor Support, Version 1.0 > Hypervisor and Virtual Supervisor CSRs | CSR_controlled | Some standard supervisor CSRs (`senvcfg`, `scounteren`, and `scontext`, possibly others) have no matching VS CSR.... | high |
| Preamble > "H" Extension for Hypervisor Support, Version 1.0 > Hypervisor and Virtual Supervisor CSRs > Virtual Supervisor Interrupt (`vsip` and `vsie`) Registers | CSR_controlled | If the Shlcofideleg extension is implemented, `hideleg` bit 13 is writable; otherwise, it is read-only zero.... | high |
| Preamble > Sscounterenw Extension for Counter-Enable Writability, Version 1.0 | CSR_controlled | If the Sscounterenw extension is implemented, then for any `hpmcounter` that is not read-only zero, the corresponding bit in `scounteren` must be writable.... | very_high |
| Preamble > Machine-Level ISA, Version 1.13 > Machine-Level CSRs > Machine Environment Configuration (`menvcfg`) Register | CSR_controlled | The Zicbom extension adds the `CBCFE` (Cache Block Clean and Flush instruction Enable) field to `menvcfg`.... | high |
| Preamble > RVWMO Explanatory Material > Why RVWMO? | SW_rule | However, these fences must remain present in the code if compatibility with non-Ztso implementations is desired.... | very_high |
| Preamble > Control and Status Registers (CSRs) > CSR Field Specifications > Reserved Writes Preserve Values, Reads Ignore Values (WPRI) | SW_rule | Software should ignore the values read from these fields, and should preserve the values held in these fields when writing values to other fields of the same register.... | high |
| Preamble > "Smstateen/Ssstateen" Extensions, Version 1.0 | SW_rule | The problem occurs when an extension adds processor state -- usually explicit registers, but possibly other forms of state -- that the main OS or hypervisor is unaware of (and hence won't context-swit... | high |
| Preamble > RVWMO Explanatory Material > Why RVWMO? > Beyond Main Memory > I/O Ordering | SW_rule | To enforce ordering between I/O operations and main memory operations, code must use a FENCE with PI, PO, SI, and/or SO, plus PR, PW, SR, and/or SW.... | very_high |
| Preamble > "Svrsw60t59b" Extension for PTE Reserved-for-Software Bits 60-59, Version 1.0 | SW_rule | If the Svrsw60t59b extension is implemented, then bits 60-59 of the page table entries (PTEs) are reserved for use by supervisor software and are ignored by the implementation.... | high |
| Preamble > Cache Management Operations (CMOs) > Pseudocode for instruction semantics > Background > Memory and Caches | SW_rule | Implementation techniques such as speculative execution or hardware prefetching may cause a given cache to allocate or deallocate a copy of a cache block at any time, provided the corresponding physic... | medium |
| Preamble > RVWMO Explanatory Material > Why RVWMO? > Explaining the RVWMO Rules > Explicit Synchronization (<<overlapping-ordering, Rules 5-8>>) | SW_rule | Using the same examples, the ordering between the loads and stores in the critical section and the "Arbitrary unrelated store" at the end of the code snippet is enforced only by the FENCE RW,W in , no... | medium |
| Preamble > Cryptography Extensions: Scalar & Entropy Source Instructions, Version 1.0.1 > Entropy Source Rationale and Recommendations > Security Controls and Health Tests | SW_rule | In almost all cases, a hardware entropy source must implement appropriate security controls to guarantee unpredictability, prevent leakage, detect attacks, and deny adversarial control over the entrop... | very_high |
| Preamble > "H" Extension for Hypervisor Support, Version 1.0 > Hypervisor and Virtual Supervisor CSRs > Hypervisor Status (`hstatus`) Register | SW_rule | When HU=0, all hypervisor instructions cause an illegal-instruction exception in U-mode.... | high |
| Preamble > Machine-Level ISA, Version 1.13 > Machine-Level CSRs > Machine Status (`mstatus` and `mstatush`) Registers > Extension Context Status in `mstatus` Register | SW_rule | To improve performance, the user-mode extension can define additional instructions to allow user-mode software to return the unit to an initial state or even to turn off the unit.... | high |
| Preamble > Shtvala Extension for Trap Value Reporting, Version 1.0 | non_CSR_parameter | If the Shtvala extension is implemented, `htval` must be written with the faulting guest physical address in all circumstances permitted by the ISA.... | very_high |
| Preamble > "V" Extension for Vector Operations, Version 1.0 > Vector Instruction Formats > Prestart, Active, Inactive, Body, and Tail Element Definitions | non_CSR_parameter | The active elements can raise exceptions and update the destination vector register group.... | high |
| Preamble > Cryptography Extensions: Scalar & Entropy Source Instructions, Version 1.0.1 > Entropy Source Rationale and Recommendations > Specific Rationale and Considerations > NIST SP 800-90B | non_CSR_parameter | If NIST SP 800-90B certification is chosen, the entropy source should implement at least the health tests defined in Section 4.4 of cite:[TuBaKe:18]: the repetition count test and adaptive proportion ... | high |
| Preamble > "Smcsrind/Sscsrind" Indirect CSR Access, Version 1.0 > Introduction > Machine-level CSRs | non_CSR_parameter | The `miselect` register may be read-only zero if there are no extensions implemented that utilize it.... | high |
| Preamble > Supervisor-Level ISA, Version 1.13 > Sv32: Page-Based 32-bit Virtual-Memory Systems > Addressing and Memory Protection | non_CSR_parameter | When two-stage address translation is in use, an explicit access may cause both VS-stage and G-stage PTEs to be updated.... | high |
| Preamble > Cryptography Extensions: Vector Instructions, Version 1.0 > Extensions Overview > `Zvkg` - Vector GCM/GMAC | non_CSR_parameter | To help avoid side-channel timing attacks, these instructions shall be implemented with data-independent timing.... | very_high |
| Preamble > ext:zcmp[] Extension for Compressed Prologues and Epilogues > PUSH/POP functional overview > cm.popret | non_CSR_parameter | switch (rlist){ case 4: \{reglist="ra"; xreglist="x1";} case 5: \{reglist="ra, s0"; xreglist="x1, x8";} case 6: \{reglist="ra, s0-s1"; xreglist="x1, x8-x9";} case 7: \{reglist="ra, s0-s2"; xreglist="x... | very_high |
| Preamble > RV64I Base Integer Instruction Set, Version 2.1 > Load and Store Instructions | non_CSR_parameter | The LW instruction loads a 32-bit value from memory and sign-extends this to 64 bits before storing it in register rd for RV64I.... | high |
| Preamble > ext:zcb[] Extension for Additional Compressed Instructions > c.lbu > c.zext.h | non_CSR_parameter | Zbb is also required. // //32-bit equivalent: // // from Zbb... | medium |
| Preamble > "Smctr" Control Transfer Records Extension, Version 1.0 > CSRs > Custom Extensions | non_CSR_parameter | All custom status fields, and standard status fields whose behavior is altered by the custom extension, must revert to standard behavior when the custom bits hold zero.... | very_high |
| Preamble > Introduction > Components of a Profile > RVA Profiles Rationale | unknown | The RISC-V International ISA extension ratification process ensures that all processor vendors have agreed to the specification of a standard extension if present.... | high |
| Preamble > "V" Extension for Vector Operations, Version 1.0 > Vector Permutation Instructions > Vector Slide Instructions > Vector Slide-1-down Instruction | unknown | If XLEN < SEW, the value is sign-extended to SEW bits.... | high |
| Preamble > Formal Memory Model Specifications, Version 0.1 > Formal Axiomatic Specification in Alloy > An Operational Memory Model | unknown | The term `acquire` refers to an instruction (or its memory operation) with the acquire-RCpc or acquire-RCsc annotation.... | medium |
| Preamble > Supervisor-Level ISA, Version 1.13 > Supervisor CSRs > Supervisor Trap Value (`stval`) Register | unknown | the actual faulting instruction * the first ILEN bits of the faulting instruction * the first SXLEN bits of the faulting instruction... | high |
| Preamble > "V" Extension for Vector Operations, Version 1.0 > Mapping of Vector Elements to Vector Register State > Mapping for LMUL = 1 | unknown | The element index is given in hexadecimal and is shown placed at the least-significant byte of the stored element.... | high |
| Preamble > Formal Memory Model Specifications, Version 0.1 > Formal Axiomatic Specification in Alloy > An Operational Memory Model > Instruction Instance State | unknown | Now, an instruction instance i is said to have fully determined data if for every register read r from regreads, the register writes that r reads from are fully determined.... | high |
| Preamble > "V" Extension for Vector Operations, Version 1.0 > Vector Permutation Instructions > Floating-Point Scalar Move Instructions | unknown | The floating-point scalar read/write instructions transfer a single value between a scalar `f` register and element 0 of a vector register.... | high |
| Preamble > "Zfinx", "Zdinx", "Zhinx", "Zhinxmin" Extensions for Floating-Point in Integer Registers, Version 1.0 > Processing of Narrower Values > Processing of Wider Values | unknown | Use of misaligned (odd-numbered) registers for double-width floating-point operands is reserved.... | high |
| Preamble > Cryptography Extensions: Vector Instructions, Version 1.0 > Instructions > vaesem.[vv,vs] | unknown | foreach (i from egstart to eglen-1) { let keyelem = if suffix "vv" then i else 0; let state : bits(128) = getvelem(vd, EGW=128, i); let rkey : bits(128) = getvelem(vs2, EGW=128, keyelem); let sb : bit... | high |
| Preamble > Machine-Level ISA, Version 1.13 > Machine-Level CSRs > Machine Counter-Enable (`mcounteren`) Register | unknown | The settings in this register only control accessibility.... | high |
