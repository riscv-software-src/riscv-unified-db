# PROMPT V1: BASIC ARCHITECTURAL PARAMETER EXTRACTION

## TASK

Extract architectural parameters from the RISC-V specification text provided below.

An **architectural parameter** is any implementation-configurable value, choice, or setting that:
- Varies across different RISC-V processor implementations
- Is NOT mandated by the specification (i.e., left to the implementer)
- Affects the observable behavior or capabilities of the processor

Architectural parameters are typically described in specifications using phrases like:
- "implementation-defined"
- "may vary"
- "implementation choice"
- "optionally implemented"
- "configurable"

## EXAMPLES OF ARCHITECTURAL PARAMETERS

**Example 1: VLEN (Vector Register Length)**
- Type: Configuration-dependent
- Naming: Named (explicitly called "VLEN" in spec)
- Explicitness: Explicit
- Description: The number of bits in a single vector register
- Spec Quote: "The number of bits in a single vector register, VLEN, is an implementation choice made at design time."
- Valid Range: 64-65536 bits (power of 2)
- Why it's a parameter: Implementations can choose different vector register sizes

**Example 2: NUM_PMP_ENTRIES (Number of PMP Entries)**
- Type: Configuration-dependent
- Naming: Named (explicitly called "NUM_PMP_ENTRIES")
- Explicitness: Explicit
- Description: Number of implemented Physical Memory Protection register entries
- Spec Quote: "An implementation may have anywhere from 0 to 64 PMP entries."
- Valid Range: 0-64
- Why it's a parameter: Implementations choose how many PMP entries to support

**Example 3: ASID_WIDTH (ASID Field Width)**
- Type: Configuration-dependent
- Naming: Named (explicitly called "ASID_WIDTH")
- Explicitness: Explicit
- Description: Number of implemented ASID (Address Space IDentifier) bits
- Spec Quote: "Maximum is 16 for XLEN==64, and 9 for XLEN==32"
- Valid Range: RV32: 0-9 bits, RV64: 0-16 bits
- Why it's a parameter: Implementations choose ASID field width

## EXAMPLES OF NON-PARAMETERS (What NOT to extract)

**NOT a parameter: rd (destination register)**
- This is an INSTRUCTION OPERAND, not an architectural parameter
- Reason: All RISC-V implementations use rd the same way
- False positive risk: HIGH - rd appears throughout specs

**NOT a parameter: funct3 (function code field)**
- This is an INSTRUCTION ENCODING FIELD, not an architectural parameter
- Reason: Instruction encoding is fixed by the ISA spec
- False positive risk: HIGH - funct3 appears in every instruction definition

**NOT a parameter: Number of registers**
- This is a FIXED REQUIREMENT (always 32), not a parameter
- Reason: RISC-V mandates exactly 32 integer registers
- False positive risk: MEDIUM - seems like it could vary but it's fixed

## SPECIFICATION TEXT TO ANALYZE

[INSERT SPECIFICATION TEXT HERE]

## TASK INSTRUCTIONS

Extract all architectural parameters from the specification text above.

For EACH parameter you identify, provide:

```json
{
  "name": "PARAMETER_NAME",
  "description": "Brief description of what this parameter controls",
  "type": "Configuration-dependent or CSR-semantic-dependent",
  "naming": "Named (if explicitly mentioned) or Unnamed (if inferred)",
  "explicitness": "Explicit (clearly stated) or Implicit (inferred from context)",
  "spec_quote": "Direct quote from specification supporting this parameter",
  "confidence": "1-5 (1=low confidence, 5=high confidence)"
}
```

## OUTPUT FORMAT

Return results as valid JSON array containing extracted parameters:

```json
[
  {
    "name": "...",
    "description": "...",
    "type": "...",
    "naming": "...",
    "explicitness": "...",
    "spec_quote": "...",
    "confidence": 4
  },
  ...
]
```

## CONFIDENCE SCORING

- **5 (Highest)**: Explicitly named, clearly marked as implementation-defined, obvious parameter
- **4 (High)**: Named, clearly implementation-dependent, minor ambiguity
- **3 (Medium)**: Named or unnamed, some context clues, some ambiguity
- **2 (Low)**: Unnamed, inferred from context, significant ambiguity
- **1 (Lowest)**: Very uncertain, might be instruction field, might be hallucination

## IMPORTANT REMINDERS

1. **Ignore instruction operands** (rd, rs1, rs2, funct3, funct7, opcode, imm, etc.)
2. **Ignore fixed requirements** (things that must be the same across all implementations)
3. **Look for implementation choices** (things implementers decide)
4. **Include spec quotes** (directly support your answer)
5. **Provide confidence scores** (help us understand your certainty)

Now proceed with extraction from the specification text.