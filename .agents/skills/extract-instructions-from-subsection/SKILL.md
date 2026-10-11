---
name: extract-instructions-from-subsection
description: Extract RISC-V instruction names from a named subsection of an AsciiDoc file and write them to /tmp/<subsection-title>.yaml.
argument-hint: <subsection-title> <adoc-file>
allowed-tools: Read, Bash, Write
---

Copyright (c) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear

Extract all RISC-V instruction names mentioned in the specified subsection of the given AsciiDoc file, then write them to `/tmp/<subsection-title>.yaml`, where `<subsection-title>` is argument 1 lowercased with spaces replaced by hyphens (e.g., `"Multiplication Operations"` → `/tmp/multiplication-operations.yaml`).

## Arguments

$ARGUMENTS

- **Argument 1**: The subsection title to search for (e.g., `"Multiplication Operations"` or `"Integer Register-Immediate Instructions"`).
- **Argument 2**: Path to the AsciiDoc file (e.g., `ext/riscv-isa-manual/src/m-st-ext.adoc`).

If either argument is missing, ask the user to provide it.

## Steps

### 1. Read the AsciiDoc file

Read the full content of the AsciiDoc file given as argument 2.

### 2. Locate the subsection

Find the subsection whose title matches argument 1. AsciiDoc section headings use `=` prefixes:
- `== Title` — level 1 (chapter)
- `=== Title` — level 2
- `==== Title` — level 3
- `===== Title` — level 4

Match the subsection title case-insensitively. The subsection's content starts on the line after the heading and ends just before the next heading of equal or higher level (i.e., same or fewer `=` characters).

### 3. Identify NOTE blocks to skip

Before scanning for instructions, mark all NOTE blocks in the subsection so they can be excluded. AsciiDoc NOTE blocks appear in two forms:

- **Delimited block**: starts with `[NOTE]` followed by `====` on the next line, and ends at the closing `====`.
- **Inline note**: a single line starting with `NOTE:` (no delimiter).

Any instruction name that appears **only** inside NOTE blocks — and nowhere else in the subsection — must be excluded from the output. If an instruction appears both inside and outside a NOTE block, include it.

### 4. Extract instruction names

Scan the non-NOTE text of the subsection for RISC-V instruction names. Instruction names appear as **uppercase tokens** in the prose. Use the following rules to identify them:

**Patterns that indicate an instruction name:**
- All-uppercase tokens of at least 2 characters that consist only of letters, and optionally digits or dots (e.g., `ADD`, `ADDI`, `MULHSU`, `FENCE.TSO`, `LR.W`, `SC.D`, `C.ADD`, `C.ADDI16SP`)
- Uppercase tokens inside backticks: `` `ADD` ``, `` `JALR` ``
- Uppercase tokens in AsciiDoc index entries: `(((MUL, MULH)))` — extract each comma-separated token
- Uppercase tokens in AsciiDoc comment lines like `//.Integer register-register` — skip these (they are labels, not instructions)
- Strip any surrounding AsciiDoc formatting characters (such as `*`, `_`, `+`, or `#`) before evaluating a token.
- Treat AsciiDoc structural elements consistently: consider instruction names appearing in AsciiDoc tables, but ignore instruction names that appear only within literal code blocks used for examples or diagrams.

**Exclude pseudoinstructions:**
The prose explicitly signals pseudoinstructions with the phrase "assembler pseudoinstruction" or "pseudoinstruction" adjacent to the name, e.g.:
- `assembler pseudoinstruction SNEZ _rd, rs_`
- `assembler pseudoinstruction MV _rd, rs1_`
- `assembler pseudoinstruction SEQZ _rd, rs_`
- `assembler pseudoinstruction NOT _rd, rs_`
- `assembler pseudoinstruction J`
- `assembler pseudoinstruction RET`
- `assembler pseudoinstruction JR`

Any token introduced by "pseudoinstruction" (with or without "assembler") must be excluded, even if it appears elsewhere in the subsection outside a pseudoinstruction context. Collect all pseudoinstruction names first, then exclude them from the final list.

**Definitive exclusion list — never treat these as instructions:**
`XLEN`, `RV32`, `RV64`, `RV32I`, `RV64I`, `RV128I`, `ISA`, `ABI`, `PC`, `CSR`, `IALIGN`, `BTB`, `RAS`, `FPGA`, `MIPS`, `RISC`, `RISCV`, `RISC-V`

Tokens that are register names (`x0`–`x31`, `rd`, `rs1`, `rs2`) — exclude them.

### 5. Deduplicate and normalize

- Convert all extracted names to **lowercase** (matching the RISC-V Unified Database YAML file naming convention, e.g., `ADD` → `add`, `MULHSU` → `mulhsu`, `FENCE.TSO` → `fence.tso`, `LR.W` → `lr.w`)
- Remove duplicates
- Sort alphabetically

### 6. Write the output

Derive the output filename from argument 1: lowercase it and replace spaces with hyphens (e.g., `"Multiplication Operations"` → `multiplication-operations`). Write `/tmp/<derived-name>.yaml` with the following format:

```yaml
instructions:
  - add
  - addi
  - mul
  - mulh
```

Use the Write tool to create the file.

### 7. Report

Print a summary:
- The subsection title found
- The number of instructions extracted
- The path written (e.g., `/tmp/multiplication-operations.yaml`)
- The list of instructions

## Example

For subsection `"Multiplication Operations"` in `ext/riscv-isa-manual/src/m-st-ext.adoc`, the output file is `/tmp/multiplication-operations.yaml`:

```yaml
instructions:
  - mul
  - mulh
  - mulhsu
  - mulhu
  - mulw
```
