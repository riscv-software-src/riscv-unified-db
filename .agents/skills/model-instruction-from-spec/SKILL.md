---
name: model-instruction-from-spec
description: Generate an IDL operation() model for a RISC-V instruction from its YAML spec file.
argument-hint: <instruction-name>
allowed-tools: Read, Glob, Grep, Write, Edit
---

Copyright (c) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause-Clear

Given a RISC-V instruction name, locate its YAML spec file under `spec/std/isa/inst/`, read the instruction's description and encoding, then generate a correct IDL `operation()` body using the IDL language defined by the Treetop grammar in `tools/ruby-gems/idlc/lib/idlc/idl.treetop`.

Write the generated IDL code into the `operation()` key of the spec YAML file **only if that key is currently empty**. If `operation()` already has content, write the new IDL code to `/tmp/$ARGUMENT[0].yaml` instead.

## Arguments

$ARGUMENTS

- **Argument 1**: The instruction name (e.g., `vmv.v.i`, `mul`, `jalr`). The name must match the `name:` field in the YAML spec file.

If the argument is missing, ask the user to provide it.

## Steps

### 1. Locate the instruction YAML file

Search for the instruction's YAML spec file under `spec/std/isa/inst/`. The file is named `<instruction-name>.yaml` and may be in any subdirectory. Use the Glob tool with the pattern `spec/std/isa/inst/**/<instruction-name>.yaml`.

If no file is found, report the error and stop.

### 2. Read the instruction spec

Read the full YAML file. Pay close attention to:

- **`description`**: Natural-language description of what the instruction does.
- **`encoding`**: The bit-field layout, including `match` pattern and `variables` (operand names and bit positions).
- **`assembly`**: The assembly syntax (operand names used in the instruction).
- **`definedBy`**: The extension(s) that define this instruction.
- **`access`**: Privilege levels at which the instruction is accessible.
- **`operation()`**: The current value — check whether it is empty (just `|` with no following content before the next key) or already populated.

### 3. Study IDL patterns from reference files

Before writing IDL, read the following reference files to understand IDL syntax and conventions:

- `spec/std/isa/inst/M/mul.yaml` — simple arithmetic with extension check
- `spec/std/isa/inst/M/div.yaml` — arithmetic with special-case handling
- `spec/std/isa/inst/I/jalr.yaml` — control flow with register read/write
- `spec/std/isa/inst/V/vmv.v.i.yaml` — vector instruction with loop and CSR access

Key IDL language rules (from `tools/ruby-gems/idlc/lib/idlc/idl.treetop`):

**Types:**
- `XReg` — XLEN-wide integer register value
- `Bits<N>` — N-bit value
- `U32`, `U64` — unsigned integers
- `Boolean` — boolean value
- Custom struct/enum types (e.g., `VectorState`, `VmaOrderType`)

**Register access:**
- `X[reg_name]` — read/write integer register (e.g., `X[xs1]`, `X[xd]`)
- `f[reg_name]` — read/write floating-point register (e.g., `f[fs1]`, `f[fs2]`, `f[fd]`)
- `CSR[csr_name].FIELD` — read/write CSR field (e.g., `CSR[misa].M`, `CSR[vstart].VALUE`)
- `v[vd]` — vector register access

**Bit operations:**
- Bit slice: `expr[msb:lsb]` (e.g., `src1[MXLEN-1:0]`)
- Concatenation: `{a, b, c}` (Verilog-style)
- Replication: `{N{expr}}` (e.g., `{MXLEN{1'b1}}`)
- Sign cast: `$signed(expr)`
- Widening multiply: `` `* `` operator

**Integer literals:**
- Verilog-style: `32'h0`, `1'b1`, `MXLEN'1`
- C-style: `0`, `0xFF`, `0b1010`

**Control flow:**
- `if (cond) { ... } else if (cond) { ... } else { ... }`
- `for (Type i = start; i < end; i++) { ... }`

**Exception raising:**
- `raise(ExceptionCode::IllegalInstruction, mode(), $encoding);`
- `raise(ExceptionCode::VirtualInstruction, mode(), $encoding);`

**Extension check:**
- `implemented?(ExtensionName::M)` — check if extension is implemented

**Special variables:**
- `$pc` — program counter
- `$encoding` — current instruction encoding
- `MXLEN` — machine XLEN
- `VLEN` — vector register length

**Comments:** Use `#` for line comments.

### 4. Generate the IDL operation() body

Using the instruction's description and encoding variables, write the IDL `operation()` body. Follow these guidelines:

1. **Extension check first**: If the instruction is defined by an optional extension (not base I), add a check at the top:
   ```
   if (implemented?(ExtensionName::X) && (CSR[misa].X == 1'b0)) {
     raise (ExceptionCode::IllegalInstruction, mode(), $encoding);
   }
   ```

2. **Privilege checks**: If `access` restricts the instruction to certain modes, raise `IllegalInstruction` for unauthorized modes.

3. **Read operands**: Declare local variables for register operands before using them:
   ```
   XReg src1 = X[xs1];
   XReg src2 = X[xs2];
   ```

4. **Implement the behavior**: Translate the description into IDL statements. Use bit operations, arithmetic, and control flow as needed.

5. **Write results**: Assign to destination registers last:
   ```
   X[xd] = result;
   ```

6. **Vector instructions**: For vector instructions, iterate over elements using `CSR[vstart].VALUE` to `CSR[vl].VALUE`, access vector state via `vector_state()`, and reset `CSR[vstart].VALUE = 0` at the end.

7. **Comments**: Add `#` comments to explain non-obvious logic, special cases, and edge conditions.

The IDL body must be syntactically valid per the grammar in `tools/ruby-gems/idlc/lib/idlc/idl.treetop`. Do not use constructs not present in the grammar (e.g., no `switch`, no `while`, no `return` in operation bodies).

### 5. Determine where to write the output

Check the `operation()` key in the YAML file:

- **Empty** (the key exists but has no content — just `operation(): |` followed immediately by the next key or end of file): write the generated IDL directly into the YAML file using the Edit tool, replacing the empty `operation(): |` line with `operation(): |` followed by the indented IDL body (2-space indent per line).

- **Already populated** (the key has existing IDL content): do **not** modify the spec file. Instead, write the generated IDL to `/tmp/<instruction-name>.yaml` with the format:

  ```yaml
  operation(): |
    <generated IDL body, 2-space indented>
  ```

### 6. Write the output

**If writing to the spec YAML file:**

Use the Edit tool to replace the empty `operation(): |` block. The replacement must preserve the YAML structure — the IDL lines must be indented with 2 spaces, and the next top-level key must remain at column 0.

Example — replacing an empty operation():
```
operation(): |
  # IDL code here
  XReg src = X[xs1];
  X[xd] = src + 1;

```
(Leave a blank line before the next key to match YAML block scalar conventions.)

**If writing to /tmp:**

Use the Write tool to create `/tmp/<instruction-name>.yaml` with:
```yaml
operation(): |
  # IDL code here
  XReg src = X[xs1];
  X[xd] = src + 1;
```

### 7. Report

Print a summary:
- The instruction name
- The YAML file found
- Whether the IDL was written to the spec file or to `/tmp/<instruction-name>.yaml`
- The generated IDL code

## Example

For instruction `mul`:

The file `spec/std/isa/inst/M/mul.yaml` already has a populated `operation()` key, so the output goes to `/tmp/mul.yaml`:

```yaml
operation(): |
  if (implemented?(ExtensionName::M) && (CSR[misa].M == 1'b0)) {
    raise (ExceptionCode::IllegalInstruction, mode(), $encoding);
  }

  XReg src1 = X[xs1];
  XReg src2 = X[xs2];

  X[xd] = (src1 * src2)[MXLEN-1:0];
```
